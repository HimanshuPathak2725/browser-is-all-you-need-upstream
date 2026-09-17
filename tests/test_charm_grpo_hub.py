"""Preflight/configuration/publisher contracts only: no jobs or real uploads."""
import importlib.util
import json
import os
import subprocess
import urllib.error
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("charm_hub", ROOT / "scripts/charm_grpo_hub.py")
hub = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hub)


def environment():
    return {"HF_TOKEN": "hf_TEST_SECRET", "MILES_HF_EXPECTED_USER": "HimanshuPathak",
            "MILES_HF_MODEL_REPO": "HimanshuPathak/Stackv2grpo", "WANDB_API_KEY": "WB_TEST_SECRET",
            "WANDB_ENTITY": "test-team", "MILES_WANDB_EXPECTED_USER": "test-wandb-user", "MILES_RUN_ID": "charm-test-run"}


def good_request(url, auth, body=None, **kwargs):
    if url.endswith("whoami-v2"):
        assert auth == "Bearer hf_TEST_SECRET"
        return {"name": "HimanshuPathak"}
    if url.endswith("auth-check/write"):
        assert kwargs["expect_json"] is False
        return {}
    assert url == "https://api.wandb.ai/graphql"
    assert body["query"].strip().startswith("query")
    assert "mutation" not in body["query"]
    if "ProjectDetails" in body["query"]:
        return {"data": {"model": {"name": hub.PROJECT}}}
    return {"data": {"viewer": {"username": "test-wandb-user", "entity": "test-wandb-user",
                              "teams": {"edges": [{"node": {"name": "test-team"}}]}}}}


def test_preflight_identity_write_endpoint_and_no_secrets(monkeypatch):
    calls = []
    def request(*a, **kw):
        calls.append(a[0])
        return good_request(*a, **kw)
    monkeypatch.setattr(hub, "request_json", request)
    result = hub.preflight(environment())
    assert result["status"] == "passed"
    assert result["hugging_face"]["write_access"]
    assert result["wandb"]["account"] == "test-wandb-user"
    assert result["wandb"]["project"] == hub.PROJECT
    assert result["wandb"]["project_write_tested"] is False
    assert len(calls) == 4
    assert "HF_TEST_SECRET" not in json.dumps(result)
    assert "WB_TEST_SECRET" not in json.dumps(result)


@pytest.mark.parametrize("code", [401, 403, 404, 429, 500])
def test_http_errors_redacted(monkeypatch, code):
    class Opener:
        def open(self, *args, **kwargs):
            raise urllib.error.HTTPError("https://huggingface.co", code, "hf_TEST_SECRET", {}, None)
    monkeypatch.setattr(hub.urllib.request, "build_opener", lambda *a: Opener())
    result = hub.preflight(environment())
    assert result["status"] == "failed"
    assert str(code) in json.dumps(result)
    assert "TEST_SECRET" not in json.dumps(result)


def test_read_token_cannot_pass_repo_write_gate(monkeypatch):
    def request(url, *args, **kwargs):
        if url.endswith("auth-check/write"):
            raise hub.GateError("authentication/permission request failed (HTTP 403)")
        return good_request(url, *args, **kwargs)
    monkeypatch.setattr(hub, "request_json", request)
    assert hub.preflight(environment())["hugging_face"]["status"] == "failed"


@pytest.mark.parametrize("key,value", [("MILES_HF_EXPECTED_USER", "wrong-user"),
                                      ("MILES_HF_MODEL_REPO", "../escape"),
                                      ("MILES_HF_MODEL_REPO", "TokenBender/Stackv2grpo"),
                                      ("WANDB_ENTITY", "other-team"),
                                      ("MILES_WANDB_EXPECTED_USER", "tirthahaque"),
                                      ("WANDB_BASE_URL", "https://untrusted.example"),
                                      ("HF_ENDPOINT", "https://untrusted.example")])
def test_wrong_identity_or_destination_fails(monkeypatch, key, value):
    monkeypatch.setattr(hub, "request_json", good_request)
    env = environment()
    env[key] = value
    assert hub.preflight(env)["status"] == "failed"


def test_wandb_graphql_error_is_not_printed(monkeypatch):
    def request(url, *a, **kw):
        return {"errors": [{"message": "WB_TEST_SECRET"}]} if "wandb.ai" in url else good_request(url, *a, **kw)
    monkeypatch.setattr(hub, "request_json", request)
    result = hub.preflight(environment())
    assert result["status"] == "failed"
    assert "WB_TEST_SECRET" not in json.dumps(result)


def test_explicit_token_sources_only(tmp_path, monkeypatch):
    with pytest.raises(hub.GateError):
        hub.hf_token({})
    (tmp_path / "token").write_text("explicit-test-token\n")
    assert hub.hf_token({"HF_HOME": str(tmp_path)}) == "explicit-test-token"
    assert hub.hf_token({"HF_TOKEN_PATH": str(tmp_path / "token")}) == "explicit-test-token"
    assert hub.hf_token({"HF_TOKEN": "preferred", "HF_HOME": str(tmp_path)}) == "preferred"


def test_no_redirects():
    assert hub.NoRedirect().redirect_request(None, None, 302, "", {}, "https://elsewhere") is None


def test_launcher_fails_before_any_snapshot_or_cloud_with_missing_credentials(tmp_path):
    # Real launcher control flow; missing keys cannot reach staging or SkyPilot.
    env = {k: v for k, v in os.environ.items() if k not in {
        "HF_TOKEN", "HF_HOME", "HF_TOKEN_PATH", "HUGGING_FACE_HUB_TOKEN",
        "WANDB_API_KEY", "WANDB_ENTITY", "MILES_HF_MODEL_REPO", "MILES_HF_EXPECTED_USER"}}
    # Explicit missing paths disable the approved real-credential defaults.
    env["HF_TOKEN_PATH"] = str(tmp_path / "missing-hf-token")
    env["MILES_WANDB_ENV_FILE"] = str(tmp_path / "missing-wandb-config")
    for mode in ("--preflight", "--check", "--launch"):
        result = subprocess.run(["bash", str(ROOT / "launch_stack_v2_charm_grpo.sh"), mode],
                                env=env, text=True, capture_output=True)
        assert result.returncode == 2
        assert json.loads(result.stdout)["status"] == "failed"
        assert "Frozen workdir" not in result.stdout


def test_exec_launch_forwards_only_via_environment(monkeypatch):
    monkeypatch.setattr(hub, "request_json", good_request)
    for k, v in environment().items():
        monkeypatch.setenv(k, v)
    captured = {}
    def fake_exec(file, command, env):
        captured.update(file=file, command=command, env=env)
        raise SystemExit(0)
    monkeypatch.setattr(hub.os, "execvpe", fake_exec)
    with pytest.raises(SystemExit):
        hub.main(["exec-launch", "--", "sky", "launch", "--secret", "HF_TOKEN", "--secret", "WANDB_API_KEY"])
    assert captured["env"]["HF_TOKEN"] == "hf_TEST_SECRET"
    assert "TEST_SECRET" not in " ".join(captured["command"])


def completed_checkpoint(tmp_path):
    env = environment()
    root = tmp_path / env["MILES_RUN_ID"]
    adapter = root / "checkpoints/grpo_lora_r16/iter_0000019/adapter"
    adapter.mkdir(parents=True)
    (adapter / "adapter_model.bin").write_bytes(b"test-adapter-bytes")
    (adapter / "adapter_config.json").write_text("{}")
    for i in range(4):
        (adapter / f"adapter_megatron_tp{i}_pp0.pt").write_bytes(b"native-test-shard")
    (adapter / "finiteness_receipt.json").write_text(json.dumps({"status": "passed", "nonfinite_tensors": 0,
                                  "adapter_model_sha256": hub.digest(adapter / "adapter_model.bin")}))
    (root / "grpo_lora_r16").mkdir()
    (root / "grpo_lora_r16/grpo_training_gate.json").write_text(json.dumps({
        "kind": "glm47-aider-grpo-training-gate", "status": "passed", "run_id": env["MILES_RUN_ID"],
        "num_rollout": 20, "latest_checkpoint": {"iteration": 19,
        "adapter_model_sha256": hub.digest(adapter / "adapter_model.bin"),
        "adapter_config_sha256": hub.digest(adapter / "adapter_config.json"),
        "native_shards": {p.name: hub.digest(p) for p in adapter.glob("adapter_megatron_*.pt")}}}))
    (root / "unrelated-secret.txt").write_text("MUST_NOT_UPLOAD")
    return root, env, adapter


class FakeHub:
    def __init__(self):
        self.operations = []
    def model_info(self, **kwargs):
        return SimpleNamespace(sha="parent-commit")
    def list_repo_files(self, **kwargs):
        return [op.path_in_repo for op in self.operations] if kwargs["revision"] == "new-commit" else []
    def create_commit(self, **kwargs):
        assert kwargs["parent_commit"] == "parent-commit"
        assert kwargs["repo_type"] == "model"
        self.operations = kwargs["operations"]
        return SimpleNamespace(oid="new-commit")


def test_publish_allowlist_immutable_commit_and_receipt(tmp_path, monkeypatch):
    monkeypatch.setattr(hub, "request_json", good_request)
    root, env, adapter = completed_checkpoint(tmp_path)
    fake = FakeHub()
    result = hub.publish(root, env, api=fake)
    assert len(fake.operations) == 7
    assert all(op.path_in_repo.startswith("runs/charm-test-run/iter_0000019/adapter/") for op in fake.operations)
    assert all(Path(op.path_or_fileobj).parent == adapter for op in fake.operations)
    assert result["commit"] == "new-commit"
    assert (root / "hf_publish_receipt.json").is_file()
    assert "TEST_SECRET" not in json.dumps(result)


def test_publish_refuses_remote_overwrite(tmp_path, monkeypatch):
    monkeypatch.setattr(hub, "request_json", good_request)
    root, env, adapter = completed_checkpoint(tmp_path)
    fake = FakeHub()
    fake.list_repo_files = lambda **kw: ["runs/charm-test-run/iter_0000019/adapter/adapter_model.bin"]
    with pytest.raises(hub.GateError, match="refusing overwrite"):
        hub.publish(root, env, api=fake)
    assert not fake.operations


@pytest.mark.parametrize("corruption", ["missing_shard", "model_changed", "native_changed", "config_changed", "bad_gate", "symlink"])
def test_bad_checkpoint_cannot_publish(tmp_path, corruption):
    root, env, adapter = completed_checkpoint(tmp_path)
    if corruption == "missing_shard":
        (adapter / "adapter_megatron_tp0_pp0.pt").unlink()
    elif corruption == "model_changed":
        (adapter / "adapter_model.bin").write_bytes(b"changed")
    elif corruption == "native_changed":
        (adapter / "adapter_megatron_tp0_pp0.pt").write_bytes(b"changed")
    elif corruption == "config_changed":
        (adapter / "adapter_config.json").write_text("{\"changed\": true}")
    elif corruption == "bad_gate":
        (root / "grpo_lora_r16/grpo_training_gate.json").write_text("{}")
    else:
        (adapter / "adapter_config.json").unlink()
        (adapter / "adapter_config.json").symlink_to(root / "unrelated-secret.txt")
    with pytest.raises(hub.GateError):
        hub.adapter_files(root, env)


def test_config_auth_before_training_and_publish_after_durable_sync():
    cfg = yaml.safe_load((ROOT / "Reward_GRPO/stack_v2_charm_grpo_skypilot.yaml").read_text())
    launcher = (ROOT / "launch_stack_v2_charm_grpo.sh").read_text()
    assert cfg["secrets"]["HF_TOKEN"] is None
    assert cfg["secrets"]["WANDB_API_KEY"] is None
    assert cfg["envs"]["MILES_HF_MODEL_REPO"] == "HimanshuPathak/Stackv2grpo"
    assert cfg["envs"]["MILES_HF_EXPECTED_USER"] == "HimanshuPathak"
    assert cfg["envs"]["MILES_WANDB_EXPECTED_USER"] == "himanshu2725pathak"
    assert launcher.index("charm_grpo_hub.py preflight") < launcher.index("stage-launch") < launcher.index("sky launch")
    assert "--secret HF_TOKEN" in launcher and "--secret WANDB_API_KEY" in launcher
    assert "${HF_TOKEN}" not in launcher and "${WANDB_API_KEY}" not in launcher
    assert cfg["setup"].index("charm_grpo_hub.py preflight") < cfg["setup"].index("nvidia-smi")
    run = cfg["run"]
    assert run.index("charm_grpo_hub.py preflight") < run.index("bash examples/grpo.sh")
    assert run.index("ARTIFACTS_PRESERVED") < run.index("charm_grpo_hub.py publish")
    assert 'if [ "${train_status}" -eq 0 ]; then' in run[run.index("ARTIFACTS_PRESERVED"):]
    assert 'echo "hf_publish_status=failed"' in run
    for script in (cfg["setup"], run, launcher):
        assert subprocess.run(["bash", "-n"], input=script, text=True, capture_output=True).returncode == 0

def test_wandb_explicit_file_is_parsed_not_sourced(tmp_path):
    path = tmp_path / ".env"
    marker = tmp_path / "must-not-be-created"
    path.write_text(f"touch {marker}\nWANDB_API_KEY='file-key' # comment\n")
    assert hub.wandb_key({"MILES_WANDB_ENV_FILE": str(path)}) == "file-key"
    assert not marker.exists()
    assert hub.wandb_key({"WANDB_API_KEY": "env-key", "MILES_WANDB_ENV_FILE": str(path)}) == "env-key"


@pytest.mark.parametrize("text", ["WANDB_API_KEY=a\nWANDB_API_KEY=b\n",
                                   "WANDB_API_KEY=\"$OTHER\"\n",
                                   "WANDB_API_KEY=\"$(anything)\"\n",
                                   "WANDB_API_KEY=\"\"\n"])
def test_ambiguous_or_dynamic_wandb_key_rejected(tmp_path, text):
    path = tmp_path / ".env"
    path.write_text(text)
    with pytest.raises(hub.GateError):
        hub.wandb_key({"MILES_WANDB_ENV_FILE": str(path)})


def test_missing_project_rejected_without_creation(monkeypatch):
    def request(url, auth, body=None, **kwargs):
        if body and "ProjectDetails" in body["query"]:
            return {"data": {"model": None}}
        return good_request(url, auth, body, **kwargs)
    monkeypatch.setattr(hub, "request_json", request)
    result = hub.preflight(environment())
    assert result["status"] == "failed"
    assert "project" in result["wandb"]["reason"]


def test_file_selected_key_forwarded_without_netrc(monkeypatch, tmp_path):
    monkeypatch.setattr(hub, "request_json", good_request)
    for key, value in environment().items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("WANDB_API_KEY")
    path = tmp_path / ".env"
    path.write_text("WANDB_API_KEY='WB_TEST_SECRET'\n")
    monkeypatch.setenv("MILES_WANDB_ENV_FILE", str(path))
    def fake_exec(file, command, env):
        assert env["WANDB_API_KEY"] == "WB_TEST_SECRET"
        assert "WB_TEST_SECRET" not in " ".join(command)
        raise SystemExit(0)
    monkeypatch.setattr(hub.os, "execvpe", fake_exec)
    with pytest.raises(SystemExit):
        hub.main(["exec-launch", "--", "sky", "launch", "--secret", "WANDB_API_KEY", "--secret", "HF_TOKEN"])

def test_launch_binds_exact_validated_credentials_despite_file_changes(monkeypatch, tmp_path):
    for key, value in environment().items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("HF_TOKEN")
    monkeypatch.delenv("WANDB_API_KEY")
    token_file = tmp_path / "token"
    key_file = tmp_path / ".env"
    token_file.write_text("hf_TEST_SECRET")
    key_file.write_text("WANDB_API_KEY=WB_TEST_SECRET\n")
    monkeypatch.setenv("HF_TOKEN_PATH", str(token_file))
    monkeypatch.setenv("MILES_WANDB_ENV_FILE", str(key_file))
    def request(*args, **kwargs):
        token_file.write_text("changed-token")
        key_file.write_text("WANDB_API_KEY=changed-key\n")
        return good_request(*args, **kwargs)
    monkeypatch.setattr(hub, "request_json", request)
    def fake_exec(file, command, env):
        assert env["HF_TOKEN"] == "hf_TEST_SECRET"
        assert env["WANDB_API_KEY"] == "WB_TEST_SECRET"
        raise SystemExit(0)
    monkeypatch.setattr(hub.os, "execvpe", fake_exec)
    with pytest.raises(SystemExit):
        hub.main(["exec-launch", "--", "sky", "launch", "--secret", "HF_TOKEN", "--secret", "WANDB_API_KEY"])

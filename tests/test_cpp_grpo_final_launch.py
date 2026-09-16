"""Launch admission must reject stale evidence before any paid operation."""
from collections import Counter
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from types import ModuleType, SimpleNamespace

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("final_launch", ROOT / "scripts/launch_cpp_grpo_final.py")
launch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launch)
DIGEST = "a" * 64
IMAGE_ID = "sha256:" + "b" * 64
COHORT = {"version": "cpp-grpo-final-v1", "train": ["clock"], "validation": ["factor-balance"]}
CATALOG = Counter({("clock", "reference", "reference"): 1})


def evidence(tmp_path):
    directory = tmp_path / "preflight"
    directory.mkdir()
    receipt = dict(status="passed", cases=1, matched=1, combined_reward_sha256=DIGEST,
                   train=COHORT["train"], validation=COHORT["validation"], sandbox_image_id=IMAGE_ID)
    case = dict(task="clock", kind="reference", control="reference", matched=True,
                result=dict(problem_id="clock", infrastructure_error=False,
                            combined_reward_sha256=DIGEST, sandbox_image_id=IMAGE_ID))
    launch.write_json(directory / "preflight.json", receipt)
    launch.write_json(directory / "case-001.json", case)
    return directory / "preflight.json"


def data(tmp_path):
    directory = tmp_path / "dataset"
    for relative, tasks in (("grpo/train.jsonl", COHORT["train"]), ("eval/validation.jsonl", COHORT["validation"])):
        target = directory / relative
        target.parent.mkdir(parents=True)
        target.write_text("".join(json.dumps({"metadata": {"problem_id": task,
            "combined_reward_sha256": DIGEST, "generalized_verifier_manifest_sha256": "c" * 64}}) + "\n" for task in tasks))
    hashes = {p.relative_to(directory).as_posix(): launch.sha256(p) for p in directory.rglob("*.jsonl")}
    launch.write_json(directory / "manifest.json", {"combined_reward_sha256": DIGEST, "file_sha256s": hashes})
    return directory


def reward():
    return SimpleNamespace(contract_digest=lambda: DIGEST, image_identity=lambda: IMAGE_ID)


@pytest.mark.parametrize("corruption", ["failed", "stale_digest", "stale_image", "missing", "duplicate", "infra", "wrong_task"])
def test_preflight_rejects_failed_stale_or_incomplete_evidence(tmp_path, corruption):
    receipt_path = evidence(tmp_path)
    receipt = json.loads(receipt_path.read_text())
    case_path = receipt_path.parent / "case-001.json"
    case = json.loads(case_path.read_text())
    if corruption == "failed": receipt["status"] = "failed"
    if corruption == "stale_digest": receipt["combined_reward_sha256"] = "d" * 64
    if corruption == "stale_image": receipt["sandbox_image_id"] = "sha256:" + "d" * 64
    if corruption == "missing": case_path.unlink()
    if corruption == "duplicate": launch.write_json(receipt_path.parent / "case-002.json", case)
    if corruption == "infra": case["result"]["infrastructure_error"] = True
    if corruption == "wrong_task": case["result"]["problem_id"] = "allergies"
    if case_path.exists(): launch.write_json(case_path, case)
    launch.write_json(receipt_path, receipt)
    with pytest.raises(RuntimeError):
        launch.validate_preflight(receipt_path, reward(), COHORT, CATALOG)


def test_complete_current_preflight_and_dataset_are_accepted(tmp_path):
    result = launch.validate_preflight(evidence(tmp_path), reward(), COHORT, CATALOG)
    assert result["matched"] == 1
    assert set(launch.validate_dataset(data(tmp_path), COHORT, DIGEST)) == {
        "manifest.json", "grpo/train.jsonl", "eval/validation.jsonl"}


@pytest.mark.parametrize("corruption", ["hash", "task", "reward"])
def test_dataset_bytes_and_row_bindings_are_enforced(tmp_path, corruption):
    directory = data(tmp_path)
    target = directory / "grpo/train.jsonl"
    row = json.loads(target.read_text())
    if corruption == "task": row["metadata"]["problem_id"] = "allergies"
    if corruption == "reward": row["metadata"]["combined_reward_sha256"] = "d" * 64
    target.write_text(json.dumps(row) + ("\n\n" if corruption == "hash" else "\n"))
    if corruption != "hash":
        manifest = json.loads((directory / "manifest.json").read_text())
        manifest["file_sha256s"]["grpo/train.jsonl"] = launch.sha256(target)
        launch.write_json(directory / "manifest.json", manifest)
    with pytest.raises(RuntimeError):
        launch.validate_dataset(directory, COHORT, DIGEST)


def test_pinned_launch_has_no_charm_or_data_regeneration_dependency():
    config = yaml.safe_load((ROOT / "Reward_GRPO/cpp_grpo_final_skypilot.yaml").read_text())
    r = SimpleNamespace(IMAGE="glm47-generalized-cpp-topics:final-v1", CURRICULUM="cpp-grpo-final-v1")
    assert launch.validate_launch_config(config, r) is config
    assert "docker load" in config["setup"]
    assert "fetch-data" in config["run"]
    assert "build-data" not in config["run"]
    assert "charm_bridge" not in config["setup"]
    config["resources"]["use_spot"] = False
    with pytest.raises(RuntimeError): launch.validate_launch_config(config, r)


def test_cli_dry_run_stages_only_committed_allowlist_without_launch(tmp_path, monkeypatch, capsys):
    from Reward_GRPO import generalized_cpp_topic_grpo as actual_reward
    repository = tmp_path / "repo"
    (repository / "Reward_GRPO").mkdir(parents=True)
    source_name = "Reward_GRPO/cpp_grpo_final_skypilot.yaml"
    (repository / source_name).write_text((ROOT / source_name).read_text())
    subprocess.run(["git", "init", "-q", str(repository)], check=True)
    browser_name = "src/w8_biayn/__init__.py"
    browser_path = repository / browser_name
    browser_path.parent.mkdir(parents=True)
    browser_path.write_text("# Existing browser package is preserved in the combined install.\n")
    subprocess.run(["git", "add", source_name, browser_name], cwd=repository, check=True)
    subprocess.run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "fixture"], cwd=repository, check=True)
    manifest_path, dataset = evidence(tmp_path), data(tmp_path)
    cohort_module = ModuleType("Reward_GRPO.generalized_cpp_cohort")
    cohort_module.load_cohort = lambda: COHORT
    monkeypatch.setitem(sys.modules, "Reward_GRPO.generalized_cpp_cohort", cohort_module)
    monkeypatch.setattr(actual_reward, "contract_digest", lambda: DIGEST)
    monkeypatch.setattr(actual_reward, "image_identity", lambda: IMAGE_ID)
    monkeypatch.setattr(actual_reward, "file_hashes", lambda: {source_name: launch.sha256(repository / source_name)})
    # Use an actual contract hash so stage can detect any post-gate source change.
    digest = launch.hashlib.sha256(json.dumps(actual_reward.file_hashes(), sort_keys=True).encode()).hexdigest()
    monkeypatch.setattr(actual_reward, "contract_digest", lambda: digest)
    receipt_data = json.loads(manifest_path.read_text())
    receipt_data["combined_reward_sha256"] = digest
    launch.write_json(manifest_path, receipt_data)
    case_path = manifest_path.parent / "case-001.json"
    case = json.loads(case_path.read_text())
    case["result"]["combined_reward_sha256"] = digest
    launch.write_json(case_path, case)
    for path in dataset.rglob("*.jsonl"):
        row = json.loads(path.read_text())
        row["metadata"]["combined_reward_sha256"] = digest
        path.write_text(json.dumps(row) + "\n")
    manifest = json.loads((dataset / "manifest.json").read_text())
    manifest["combined_reward_sha256"] = digest
    manifest["file_sha256s"] = {p.relative_to(dataset).as_posix(): launch.sha256(p) for p in dataset.rglob("*.jsonl")}
    launch.write_json(dataset / "manifest.json", manifest)
    monkeypatch.setattr(actual_reward, "IMAGE", "glm47-generalized-cpp-topics:final-v1")
    monkeypatch.setattr(actual_reward, "CURRICULUM", "cpp-grpo-final-v1")
    monkeypatch.setattr(actual_reward.base, "_registry", lambda: SimpleNamespace(resolve=lambda task: SimpleNamespace(manifest_sha256="c" * 64)))
    monkeypatch.setattr(launch, "ROOT", repository)
    monkeypatch.setattr(launch, "EXTRA_SOURCE_FILES", (source_name,))
    monkeypatch.setattr(launch, "expected_control_catalog", lambda r, c: CATALOG)
    monkeypatch.setattr(launch, "online_gates", lambda *a: pytest.fail("dry-run attempted online launch gates"))
    monkeypatch.setattr(sys, "argv", ["launcher", "--preflight-receipt", str(manifest_path), "--dataset-dir", str(dataset),
        "--dataset-repo", "test/final", "--dataset-revision", "e" * 40, "--out", str(tmp_path / "launch")])
    assert launch.main() == 0
    receipt = json.loads((tmp_path / "launch/launch-receipt.json").read_text())
    assert receipt["launch_requested"] is False and receipt["identities"]["status"] == "not_checked_dry_run"
    assert not (tmp_path / "launch/reward-image.tar").exists()
    staged = tmp_path / "launch/source"
    staged_manifest = launch.verify_stage(staged)
    assert staged_manifest["dataset"]["revision"] == "e" * 40
    assert staged_manifest["files"][browser_name] == launch.sha256(browser_path)
    assert (staged / browser_name).read_bytes() == browser_path.read_bytes()
    (staged / source_name).write_text("tampered")
    with pytest.raises(RuntimeError): launch.verify_stage(staged)
    assert "HF_TOKEN=" not in capsys.readouterr().out


def test_local_model_catalog_authenticates_hf_bytes_not_just_revision_marker(tmp_path):
    import hashlib
    directory = tmp_path / "model"
    directory.mkdir()
    revision = "e" * 40
    (directory / "MODEL_REVISION").write_text(revision)
    config = b'{"model_type":"glm4_moe_lite"}'
    weights = b"test weights"
    (directory / "config.json").write_bytes(config)
    (directory / "model.safetensors").write_bytes(weights)
    blob_id = hashlib.sha1(b"blob " + str(len(config)).encode() + b"\0" + config).hexdigest()
    info = SimpleNamespace(sha=revision, siblings=[
        SimpleNamespace(rfilename="config.json", lfs=None, blob_id=blob_id),
        SimpleNamespace(rfilename="model.safetensors", lfs={"sha256": hashlib.sha256(weights).hexdigest()}, blob_id=None)])
    result = launch.authenticate_model_catalog(directory, "test/model", revision, "gs://pinned/source", info)
    assert result["authentication"] == "huggingface-pinned-revision"
    assert result["files"]["model.safetensors"] == hashlib.sha256(weights).hexdigest()
    (directory / "model.safetensors").write_bytes(b"different weights")
    with pytest.raises(RuntimeError, match="differ"):
        launch.authenticate_model_catalog(directory, "test/model", revision, "gs://pinned/source", info)

"""Contract/integrity tests; native C++ controls are exercised by check-integration."""
import argparse
import asyncio
import copy
import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from Reward_GRPO import stack_v2_charm_grpo as adapter

def build_args(out):
    return argparse.Namespace(curriculum=adapter.CURRICULUM, out=out, train_limit=None,
                              eval_limit=None, profile=adapter.PROFILE, run_id="unit")

def oracle_sample(task_id=None):
    registry = adapter.Registry()
    task_id = task_id or adapter.PREFIX + "quorum-segment-assembler"
    manifest, root = registry.resolve(task_id)
    return {"metadata": registry.row(task_id)["metadata"],
            "response": adapter.control_response(manifest, root, "reference"),
            "rollout_id": 1}

def test_frozen_assets_match_materialization_and_certification():
    registry = adapter.Registry()
    materialized = adapter.read_json(adapter.ASSETS / "materialization.json")
    certified = adapter.read_json(adapter.ASSETS / "certification.json")
    assert adapter.sha(adapter.ASSETS / "materialization.json") == adapter.MATERIALIZATION_SHA256
    assert adapter.sha(adapter.ASSETS / "certification.json") == adapter.CERTIFICATION_SHA256
    assert adapter.sha(adapter.ASSETS / "source.jsonl") == adapter.SOURCE_JSONL_SHA256
    assert {p["task_id"] for p in certified["task_receipts"]} == set(registry.entries)
    for task in materialized["tasks"]:
        manifest, root = registry.resolve(task["task_id"])
        assert adapter.tree_hashes(root) == task["file_sha256s"] == manifest["files"]
        assert set(manifest["sources"]) == {n for n in manifest["root_files"] if n.endswith(".cpp")}

def test_data_contract_splits_and_no_task_answers(tmp_path):
    out = tmp_path / "data"
    result = adapter.build_data(build_args(out))
    manifest = adapter.read_json(Path(result["manifest"]))
    assert manifest["counts"] == {"available_shadow": 20, "train": 14, "validation": 5, "calibration": 1, "monitor": 14}
    ids = []
    for split, relative in (("train", "grpo/train.jsonl"), ("validation", "eval/validation.jsonl"),
                            ("calibration", "eval/calibration.jsonl")):
        for line in (out / relative).read_text().splitlines():
            row = json.loads(line)
            assert set(row) == {"prompt", "label", "task_id", "problem_id", "split", "metadata"}
            assert row["split"] == split
            assert row["prompt"][-1]["role"] == "user"
            assert all(set(m) == {"role", "content"} for m in row["prompt"])
            assert row["metadata"]["charm_registry_sha256"] == adapter.REGISTRY_SHA256
            assert (out / row["metadata"]["task_path"]).is_file()
            prompt = json.dumps(row["prompt"])
            assert not any(s in prompt for s in (".reference/", ".meta/", "source_provenance", "Private tests failed"))
            # Assistant context comes only from the repository's fixed Aider examples.
            assert all("charm-stack" not in m["content"] for m in row["prompt"] if m["role"] == "assistant")
            ids.append(row["problem_id"])
    assert len(ids) == len(set(ids)) == 20
    assert not (out / "sft").exists()
    assert manifest["split_contract"]["imitation_role"] == "none"
    for name, digest in manifest["file_sha256s"].items():
        assert adapter.sha(out / name) == digest
    with pytest.raises(FileExistsError):
        adapter.build_data(build_args(out))

def test_fixed_headers_are_context_not_editable():
    registry = adapter.Registry()
    task_id = adapter.PREFIX + "address-token-matcher"
    row = registry.row(task_id)
    assert "Read-only file: address-token-matcher.h" in row["prompt"][-1]["content"]
    assert "address-token-matcher.h" not in row["metadata"]["editable_files"]

@pytest.mark.parametrize("key,bad", [
    ("problem_id", "clock"), ("task_id", "wrong"), ("split", "validation"),
    ("charm_registry_sha256", "0"*64), ("charm_manifest_sha256", "0"*64),
    ("hidden_test_sha256", "0"*64), ("editable_files", ["wrong.cpp"]),
])
def test_bad_binding_is_infrastructure_failure(monkeypatch, key, bad):
    sample = oracle_sample()
    sample["metadata"][key] = bad
    monkeypatch.setattr(adapter, "execute", lambda *a: pytest.fail("untrusted binding executed"))
    result = adapter.score_sample(sample)
    assert result["infrastructure_error"]
    assert result["score"] == 0

@pytest.mark.parametrize("kind", ["forbidden", "early_exit"])
def test_candidate_policy_is_model_failure(monkeypatch, kind):
    registry = adapter.Registry()
    task_id = adapter.PREFIX + "quorum-segment-assembler"
    manifest, root = registry.resolve(task_id)
    sample = oracle_sample(task_id)
    sample["response"] = adapter.control_response(manifest, root, kind)
    monkeypatch.setattr(adapter, "execute", lambda *a: pytest.fail("policy violation executed"))
    result = adapter.score_sample(sample)
    assert not result["infrastructure_error"]
    assert result["score"] == -1

def test_duplicate_listings_rejected():
    sample = oracle_sample()
    sample["response"] += sample["response"]
    result = adapter.score_sample(sample)
    assert result["reason"] == "duplicate_file"
    assert result["score"] == -1

@pytest.mark.parametrize("text", [
    '#define CHECK(x) true', 'int charm_failures = 0;', '#include "../hidden_test.cpp"',
    '#include "/etc/passwd"', 'void f(){std::exit(0);}', 'asm("nop");',
])
def test_harness_bypass_primitives_rejected(text):
    with pytest.raises(adapter.CandidatePolicyError):
        adapter.check_source("solution.cpp", text)

def test_miles_sample_object_and_batch(monkeypatch):
    monkeypatch.setattr(adapter, "execute", lambda *a: {"status": "passed", "suite_passes": {"example": True, "hidden": True}})
    sample = SimpleNamespace(**oracle_sample())
    record = asyncio.run(adapter.reward_func(None, sample))
    assert record["score"] == record["reward"] == 1
    records = asyncio.run(adapter.reward_func(None, [sample, sample]))
    assert len(records) == 2
    assert all(r["score"] == 1 for r in records)

def test_infrastructure_neutralization_keeps_score_reward_equal(monkeypatch):
    monkeypatch.setattr(adapter, "execute", lambda *a: {"status": "passed"})
    good = oracle_sample()
    bad = copy.deepcopy(good)
    bad["metadata"]["charm_manifest_sha256"] = "0"*64
    records = asyncio.run(adapter.reward_func(None, [good, bad]))
    assert records[1]["infrastructure_error"]
    assert records[1]["score_neutralized"]
    assert records[1]["score"] == records[1]["reward"] == records[0]["score"]

def test_missing_registry_returns_invalid_records(monkeypatch):
    def broken():
        raise ValueError("missing registry")
    monkeypatch.setattr(adapter, "Registry", broken)
    records = asyncio.run(adapter.reward_func(None, [{"metadata": {"problem_id": "x"}}]))
    assert records[0]["infrastructure_error"]

def test_compiler_failure_not_positive(monkeypatch):
    monkeypatch.setattr(adapter, "execute", lambda *a: {"status": "compile_failed", "stage": "link"})
    result = adapter.score_sample(oracle_sample())
    assert result["score"] < 0 and not result["infrastructure_error"]

def test_no_assertion_fraction_invented(monkeypatch):
    monkeypatch.setattr(adapter, "execute", lambda *a: {"status": "tests_failed", "suite_passes": {"example": True, "hidden": False}})
    result = adapter.score_sample(oracle_sample())
    assert result["candidate_semantic_fraction"] is None
    assert result["score"] == -0.45
    assert result["test_count_unit"] == "suite"

def test_generalized_settings_cannot_select_old_tasks(monkeypatch):
    monkeypatch.setenv("GENERALIZED_CPP_VERIFIER_REGISTRY", "/nonexistent/old-registry")
    monkeypatch.setenv("GENERALIZED_CPP_VERIFIER_PROFILE", "full")
    assert len(adapter.Registry().entries) == 20
    assert "clock" not in adapter.Registry().entries

def test_corrupted_protected_file_fails_binding(tmp_path):
    shutil.copytree(adapter.ASSETS, tmp_path / "assets")
    registry = adapter.Registry(tmp_path / "assets/registry.json")
    task_id = next(iter(registry.entries))
    manifest, root = registry.resolve(task_id)
    (root / ".meta/hidden_test.cpp").write_text("tampered")
    with pytest.raises(ValueError, match="asset digest mismatch"):
        registry.resolve(task_id)

def test_hilbert_mutations_are_actual_header_edits():
    registry = adapter.Registry()
    manifest, root = registry.resolve(adapter.PREFIX + "hilbert-cell-codec")
    ref = adapter.control_response(manifest, root, "reference")
    for kind in ("negative", "mutation2"):
        response = adapter.control_response(manifest, root, kind)
        assert response != ref
        parsed = adapter.parse_whole_file_response(response, manifest["editable_files"])
        assert set(parsed.files) == set(manifest["editable_files"])

def test_source_limits_and_invalid_response_type():
    with pytest.raises(adapter.CandidatePolicyError):
        adapter.check_source("x.cpp", " " * (256*1024 + 1))
    sample = oracle_sample()
    sample["response"] = {"not": "text"}
    result = adapter.score_sample(sample)
    assert result["score"] == -1 and not result["infrastructure_error"]

def test_existing_generalized_hyperparameters_preserved():
    import yaml
    root = Path(__file__).resolve().parents[1]
    old = yaml.safe_load((root / "Reward_GRPO/generalized_cpp_grpo_skypilot.yaml").read_text())
    new = yaml.safe_load((root / "Reward_GRPO/stack_v2_charm_grpo_skypilot.yaml").read_text())
    for key in (
        "GLM47_MODEL_REVISION", "MILES_EXPECTED_SOURCE_ADAPTER_SHA256",
        "MILES_ROLLOUT_BATCH_SIZE", "MILES_N_SAMPLES_PER_PROMPT",
        "MILES_GLOBAL_BATCH_SIZE", "MILES_LR", "MILES_LR_DECAY_STYLE", "MILES_LR_WARMUP_FRACTION",
        "MILES_KL_LOSS_COEF", "MILES_USE_KL_LOSS", "MILES_NO_REF", "MILES_SEQ_LENGTH",
        "MILES_ROLLOUT_MAX_RESPONSE_LEN", "MILES_ROLLOUT_TEMPERATURE", "MILES_EVAL_INTERVAL",
        "MILES_SAVE_INTERVAL", "MILES_EVAL_N_SAMPLES_PER_PROMPT",
    ):
        assert old["envs"][key] == new["envs"][key], key
    for key in ("infra", "instance_type", "accelerators", "image_id", "use_spot"):
        assert old["resources"][key] == new["resources"][key]
    assert new["envs"]["MILES_EXPECTED_TRAIN_COUNT"] == "12"
    assert new["envs"]["MILES_NUM_ROLLOUT"] == "45"
    assert new["envs"]["MILES_CUSTOM_RM_PATH"] == "glm47_posttraining.integrations.stack_v2_charm_run.reward_func"
    assert "generalized_cpp_grpo" not in new["setup"] + new["run"]
    assert "--force" not in new["run"]
    assert "MILES_EVAL_PROMPT_DATA" in new["run"]

def test_launch_shell_blocks_parse_without_execution():
    import subprocess
    import yaml
    root = Path(__file__).resolve().parents[1]
    config = yaml.safe_load((root / "Reward_GRPO/stack_v2_charm_grpo_skypilot.yaml").read_text())
    for script in (config["setup"], config["run"],
                   (root / "launch_stack_v2_charm_grpo.sh").read_text()):
        result = subprocess.run(["bash", "-n"], input=script, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr

def test_execution_uses_restricted_docker_and_no_reference_mount(monkeypatch):
    import subprocess
    captured = {}
    registry = adapter.Registry()
    task_id = adapter.PREFIX + "quorum-segment-assembler"
    manifest, root = registry.resolve(task_id)
    files = adapter.parse_whole_file_response(adapter.control_response(manifest, root, "reference"),
                                              manifest["editable_files"]).files
    def fake_run(command, **kwargs):
        captured["command"] = command
        scratch = Path(command[command.index("-v") + 1].split(":/work")[0])
        assert not any(p.name in (".reference", ".provenance.json", "registry.json") for p in scratch.rglob("*"))
        assert sorted(p.name for p in (scratch / "src").iterdir()) == manifest["root_files"]
        return subprocess.CompletedProcess(command, 15, "", "")
    monkeypatch.setattr(adapter.subprocess, "run", fake_run)
    adapter.execute(manifest, root, files)
    command = captured["command"]
    assert command[:2] == ["docker", "run"]
    assert command[command.index("--network") + 1] == "none"
    assert "--read-only" in command
    assert command[command.index("--cap-drop") + 1] == "ALL"
    assert command.count("-v") == 1
    assert "/var/run/docker.sock" not in " ".join(command)

def test_training_limit_cannot_change_the_frozen_split(tmp_path):
    args = build_args(tmp_path / "data")
    args.train_limit = 20
    with pytest.raises(ValueError, match="silently truncated"):
        adapter.build_data(args)

def test_packaged_task_tree_matches_frozen_materialization():
    materialized = adapter.read_json(adapter.ASSETS / "materialization.json")
    for spec in materialized["tasks"]:
        source = adapter.ASSETS / "tasks" / spec["task_id"]
        assert adapter.tree_hashes(source) == spec["file_sha256s"]

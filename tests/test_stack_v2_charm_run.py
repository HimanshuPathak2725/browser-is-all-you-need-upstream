"""Experiment split/schedule tests; no task authoring or training."""
import argparse
import asyncio
import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from Reward_GRPO import stack_v2_charm_grpo as base
from glm47_posttraining.integrations import stack_v2_charm_run as run


def args(out):
    return argparse.Namespace(tasks_dir=str(base.ROOT), out=out, curriculum=run.CURRICULUM,
                              profile=run.PROFILE, run_id="split-test", sort_by_size=False,
                              train_limit=None, eval_limit=None)


def test_projection_preserves_every_task_prompt_and_certified_binding():
    original, projected = base.Registry(), run.Registry()
    counts = {"train": 0, "validation": 0, "calibration": 0}
    for task_id in original.entries:
        old, new = original.row(task_id), projected.row(task_id)
        counts[new["split"]] += 1
        assert old["prompt"] == new["prompt"]
        for key in ("charm_registry_sha256", "charm_manifest_sha256", "hidden_test_sha256", "editable_files"):
            assert old["metadata"][key] == new["metadata"][key]
        a, p = original.resolve(task_id)
        b, q = projected.resolve(task_id)
        assert p == q and a["files"] == b["files"]
    assert counts == {"train": 12, "validation": 7, "calibration": 1}
    assert len(run.VALIDATION - base.VALIDATION) == 2
    base.check_receipt()


def test_built_jsonls_and_descriptors_match_split_contract(tmp_path):
    output = tmp_path / "data"
    result = run.build_data(args(output))
    manifest = json.loads(Path(result["manifest"]).read_text())
    assert manifest["counts"] == {"available_shadow": 20, "train": 12, "validation": 7, "calibration": 1, "monitor": 12}
    assert manifest["reward_function"] == "glm47_posttraining.integrations.stack_v2_charm_run.reward_func"
    seen = set()
    for split, relative in (("train", "grpo/train.jsonl"), ("validation", "eval/validation.jsonl"), ("calibration", "eval/calibration.jsonl")):
        for line in (output / relative).read_text().splitlines():
            row = json.loads(line)
            assert row == run.Registry().row(row["problem_id"])
            assert row["split"] == split
            assert row["problem_id"] not in seen
            seen.add(row["problem_id"])
            descriptor = json.loads((output / row["metadata"]["task_path"]).read_text())
            assert descriptor["split"] == split
    assert len(seen) == 20
    assert base.tree_hashes(output) | {}  # directory contains only generated integration artifacts
    for name, digest in manifest["file_sha256s"].items():
        assert base.sha(output / name) == digest
    assert not (output / "baseline").exists()


def test_moved_holdout_scores_using_original_verifier(monkeypatch):
    registry = run.Registry()
    task_id = base.PREFIX + "coalescing-range-allocator"
    manifest, root = registry.resolve(task_id)
    row = registry.row(task_id)
    sample = SimpleNamespace(**row, response=base.control_response(manifest, root, "reference"))
    monkeypatch.setattr(base, "execute", lambda *a: {"status": "passed"})
    record = asyncio.run(run.reward_func(None, sample))
    assert record["score"] == 1 and record["split"] == "validation"
    assert not record["infrastructure_error"]


@pytest.mark.parametrize("key,value", [("split", "train"), ("charm_split_contract_sha256", "stale")])
def test_split_tampering_never_executes(monkeypatch, key, value):
    registry = run.Registry()
    sample = registry.row(base.PREFIX + "coalescing-range-allocator")
    sample["metadata"][key] = value
    monkeypatch.setattr(base, "execute", lambda *a: pytest.fail("bad binding executed"))
    assert run.score_sample(sample)["infrastructure_error"]


def test_exact_thirty_passes_and_final_checkpoint_contract():
    cfg = yaml.safe_load((base.ROOT / "stack_v2_charm_grpo_skypilot.yaml").read_text())
    env = cfg["envs"]
    assert int(env["MILES_NUM_ROLLOUT"]) * int(env["MILES_ROLLOUT_BATCH_SIZE"]) == 30 * 12
    assert int(env["MILES_N_SAMPLES_PER_PROMPT"]) * int(env["MILES_ROLLOUT_BATCH_SIZE"]) == 256
    assert int(env["MILES_NUM_ROLLOUT"]) - 1 == 44
    assert env["MILES_DATA_CURRICULUM"] == run.CURRICULUM
    assert env["MILES_CUSTOM_RM_PATH"] == "glm47_posttraining.integrations.stack_v2_charm_run.reward_func"
    assert cfg["resources"]["use_spot"] is True
    assert cfg["resources"]["accelerators"] == "H100:8"

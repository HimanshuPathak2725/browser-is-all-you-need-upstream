"""Approved 12/7/1, 30-pass experiment over unchanged certified CHARM tasks.

The original verifier, registry, task files, and integration receipt are reused.
Only experiment split metadata and data selection differ from the baseline.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Mapping

from Reward_GRPO import stack_v2_charm_grpo as base

CURRICULUM = "stack-v2-charm-12x30-v1"
PROFILE = "stack-v2-charm-12x30-grpo45"
RUNTIME_SCRIPTS = {
    "charm_grpo_hub.py",
    "check_runtime.py",
    "create_grpo_training_gate.py",
    "prepare_grpo_adapter.py",
    "publish_results.py",
    "train_grpo.sh",
}
VALIDATION = base.VALIDATION | {base.PREFIX + "coalescing-range-allocator", base.PREFIX + "route-window-enumerator"}
SPLIT = {"validation": sorted(VALIDATION), "calibration": [base.CALIBRATION],
         "train": "all remaining frozen registry tasks", "counts": [12, 7, 1]}
SPLIT_SHA256 = hashlib.sha256(base.canonical(SPLIT)).hexdigest()


def split_for(task_id: str) -> str:
    return "calibration" if task_id == base.CALIBRATION else "validation" if task_id in VALIDATION else "train"


class Registry(base.Registry):
    def resolve(self, task_id):
        manifest, root = super().resolve(task_id)
        return {**manifest, "split": split_for(task_id)}, root

    def row(self, task_id):
        row = super().row(task_id)
        row["metadata"]["charm_split_contract_sha256"] = SPLIT_SHA256
        return row


def build_data(args):
    base.check_receipt()
    if args.curriculum != CURRICULUM or args.train_limit is not None or args.eval_limit is not None:
        raise ValueError("the approved 12/7/1 experiment must not be truncated or substituted")
    if Path(args.tasks_dir).resolve() != base.ROOT:
        raise ValueError("incorrect CHARM tasks package")
    registry = Registry()
    output = args.out.resolve()
    if output.exists():
        raise FileExistsError("refusing to overwrite run data")
    if registry.root == output or registry.root in output.parents or output in registry.root.parents:
        raise ValueError("data output overlaps frozen assets")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="charm-12x30-data-", dir=output.parent) as tmp:
        stage = Path(tmp)
        # Reuse the canonical builder for its manifest contract, in a separate temp tree.
        original = argparse.Namespace(**vars(args))
        original.curriculum, original.out = base.CURRICULUM, stage / "baseline"
        built = base.build_data(original)
        manifest = base.read_json(Path(built["manifest"]))
        actual = stage / "projection"
        rows = [registry.row(task_id) for task_id in sorted(registry.entries)]
        groups = {s: [r for r in rows if r["split"] == s] for s in ("train", "validation", "calibration")}
        if [len(groups[s]) for s in ("train", "validation", "calibration")] != [12, 7, 1]:
            raise ValueError("incorrect split counts")
        if args.sort_by_size:
            for group in groups.values():
                group.sort(key=lambda r: (len(str(r["prompt"])), r["problem_id"]))
        for row in rows:
            base.write_json(actual / row["metadata"]["task_path"],
                            {"schema_version": 1, "kind": base.PROFILE, **row["metadata"], "prompt": row["prompt"]})
        for path, split in (("grpo/train.jsonl", "train"), ("eval/validation.jsonl", "validation"),
                            ("eval/train_monitor.jsonl", "train"), ("eval/calibration.jsonl", "calibration")):
            base.write_jsonl(actual / path, groups[split])
        manifest.update({"profile": args.profile, "run_id": args.run_id,
                         "reward_function": "glm47_posttraining.integrations.stack_v2_charm_run.reward_func",
                         "charm_split_contract_sha256": SPLIT_SHA256,
                         "source_tree_sha256": hashlib.sha256(base.canonical({"registry": registry.digest, "split": SPLIT_SHA256})).hexdigest(),
                         "counts": {"available_shadow": 20, "train": 12, "validation": 7, "calibration": 1, "monitor": 12},
                         "task_ids_by_split": {s: [r["problem_id"] for r in g] for s, g in groups.items()},
                         "file_sha256s": base.tree_hashes(actual),
                         "epoch_contract": {"dataset_passes": 30, "training_tasks": 12, "rollout_updates": 45,
                                            "prompts_per_update": 8, "samples_per_prompt": 32, "global_batch_size": 256}})
        manifest["split_contract"].update(train="12 frozen tasks", validation="7 task-disjoint lineages")
        base.write_json(actual / "manifest.json", manifest)
        os.rename(actual, output)
    return {"grpo_train": str(output / "grpo/train.jsonl"), "eval": str(output / "eval/validation.jsonl"),
            "manifest": str(output / "manifest.json"), "counts": manifest["counts"]}


def score_sample(sample, registry=None):
    registry = registry or Registry()
    metadata = base.value(sample, "metadata", {})
    if not isinstance(metadata, Mapping) or metadata.get("charm_split_contract_sha256") != SPLIT_SHA256:
        return {"score": 0.0, "reward": 0.0, "infrastructure_error": True, "reason": "experiment_split_binding_mismatch",
                "problem_id": metadata.get("problem_id") if isinstance(metadata, Mapping) else None,
                "rollout_id": base.value(sample, "rollout_id")}
    return base.score_sample(sample, registry)


async def reward_func(_args: Any, sample: Any, **_kwargs):
    registry = Registry()
    if not isinstance(sample, list):
        return await asyncio.to_thread(score_sample, sample, registry)
    semaphore = asyncio.Semaphore(max(1, min(int(os.environ.get("GLM47_CPP_REWARD_WORKERS", "4")), 24)))
    async def score(item):
        async with semaphore:
            return await asyncio.to_thread(score_sample, item, registry)
    records = base.neutralize_infrastructure_scores(await asyncio.gather(*(score(s) for s in sample)))
    for record in records:
        record["reward"] = record["score"]
    return records


def preflight():
    base.check_receipt()
    registry = Registry()
    samples = []
    for task_id in sorted(registry.entries):
        manifest, root = registry.resolve(task_id)
        samples.append({"metadata": registry.row(task_id)["metadata"], "response": base.control_response(manifest, root, "reference")})
    records = asyncio.run(reward_func(None, samples))
    if len(records) != 20 or any(r["score"] != 1 or r["infrastructure_error"] for r in records):
        raise RuntimeError("12/7/1 reward-worker preflight failed")
    return {"status": "passed", "tasks": 20, "counts": [12, 7, 1], "split_sha256": SPLIT_SHA256,
            "updates": 45, "dataset_passes": 30, "sandbox": base.sandbox_identity()}


def stage_launch(args):
    """Extend the frozen packager without changing its certified verifier code."""
    output = args.out.resolve()
    repo = base.ROOT.parent
    if output.exists():
        raise FileExistsError(output)
    if output == repo or output in repo.parents or any(
        protected == output or protected in output.parents
        for protected in (base.ASSETS, repo / "src", repo / "scripts", base.ROOT)
    ):
        raise ValueError("unsafe launch snapshot destination")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="charm-worker-launch-", dir=output.parent) as tmp:
        stage = Path(tmp) / "snapshot"
        base.stage_launch(argparse.Namespace(out=stage, run_id=args.run_id))
        for path in (stage / "scripts").iterdir():
            if path.name not in RUNTIME_SCRIPTS:
                shutil.rmtree(path) if path.is_dir() else path.unlink()
        # Python imports this top-level module at startup in each Ray worker.
        shutil.copy2(repo / "src/sitecustomize.py", stage / "src/sitecustomize.py")
        manifest = base.read_json(stage / "launch-manifest.json")
        manifest["files"] = {k: v for k, v in base.tree_hashes(stage).items()
                             if k != "launch-manifest.json"}
        manifest["worker_bootstrap"] = "src/sitecustomize.py"
        base.write_json(stage / "launch-manifest.json", manifest)
        from .charm_bridge_preflight import verify_package
        verify_package(stage)
        os.rename(stage, output)
    return {"workdir": str(output), "launch_manifest_sha256": base.sha(output / "launch-manifest.json")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("preflight")
    stage = sub.add_parser("stage-launch")
    stage.add_argument("--out", type=Path, required=True)
    stage.add_argument("--run-id", required=True)
    build = sub.add_parser("build-data")
    build.add_argument("--tasks-dir", required=True)
    build.add_argument("--out", type=Path, required=True)
    build.add_argument("--curriculum", default=CURRICULUM)
    build.add_argument("--profile", default=PROFILE)
    build.add_argument("--run-id")
    build.add_argument("--eval-splits", default="validation")
    build.add_argument("--sort-by-size", action="store_true")
    build.add_argument("--train-limit", type=int)
    build.add_argument("--eval-limit", type=int)
    args = parser.parse_args()
    import json
    result = (build_data(args) if args.command == "build-data" else
              stage_launch(args) if args.command == "stage-launch" else preflight())
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

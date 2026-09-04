"""Rebuild the generalized C++ GRPO registry and per-task trusted manifests.

Manifests follow the canary shape: candidate files are the fixture starter
pair, protected files pin every other fixture asset (including the starter
pair, which doubles as the rollout starting point), and policy entries stay
advisory and empty because the direct runner dispatches wrappers by policy id.
Each registry entry carries an oracle ``preflight_response`` rendered from the
fixture's ``.meta/example.*`` reference. For an official header-only solution,
the unchanged starter source completes the required whole-file response.
``preflight`` must score every rendered oracle 1.0.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
FIXTURES = ROOT / "multi_env_fixtures"
OUTPUT = ROOT / "generalized_cpp_grpo_tasks"
REGISTRY = ROOT / "generalized_cpp_grpo_registry.json"
CANARY = ROOT / "generalized_cpp_grpo_canary"

# Legacy curriculum from the September 1 run. These tasks remain in place so
# this change expands rather than silently redefines the experiment.
LEGACY_TRAIN_TASKS = [
    "clock",
    "complex-numbers",
    "crypto-square",
    "grade-school",
    "kindergarten-garden",
    "perfect-numbers",
]

# Added only after receipt-bound admission against four independent fixed-26
# trials of the actual warm start.  See generalized_cpp_midband_admission.json.
# robot-name and parallel-letter-frequency meet the numerical band but remain
# excluded because reward-worker concurrency makes their tests nondeterministic.
ADMITTED_MIDBAND_TASKS = [
    "allergies",
    "bank-account",
    "circular-buffer",
    "dnd-character",
    "queen-attack",
    "space-age",
    "spiral-matrix",
    "sublist",
    "yacht",
]
TRAIN_TASKS = [*LEGACY_TRAIN_TASKS, *ADMITTED_MIDBAND_TASKS]
VALIDATION_TASKS = [
    "columnar-code",
    "cyclic-schedule",
    "factor-balance",
    "league-table",
]
TASKS = [*TRAIN_TASKS, *VALIDATION_TASKS]
VALIDATION_FAMILIES = {
    "columnar-code": "string-grid-formatting",
    "cyclic-schedule": "modular-date-time",
    "factor-balance": "math-rules",
    "league-table": "deterministic-aggregation",
}
TRAIN_FAMILIES = {
    "allergies": "bitmask-query",
    "bank-account": "stateful-api",
    "circular-buffer": "generic-data-structure",
    "clock": "modular-time",
    "complex-numbers": "numeric-object-api",
    "crypto-square": "string-grid-formatting",
    "dnd-character": "numeric-rules-randomness",
    "grade-school": "ordered-aggregation",
    "kindergarten-garden": "indexed-mapping",
    "perfect-numbers": "math-classification",
    "queen-attack": "coordinate-validation",
    "space-age": "numeric-conversion",
    "spiral-matrix": "grid-algorithm",
    "sublist": "sequence-relation",
    "yacht": "combinatorial-scoring",
}

POLICY_IDS = ("G02", "G03", "G04", "G05", "G06", "G07")
POLYGLOT_COMMIT = "7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def aider_listing(name: str, text: str) -> str:
    return f"{name}\n```cpp\n{text.rstrip()}\n```\n"


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    tasks: dict[str, object] = {
        "portable-arithmetic": {
            "manifest": "generalized_cpp_grpo_canary/manifest.json",
            "manifest_sha256": sha256(CANARY / "manifest.json"),
            "fixture_dir": "generalized_cpp_grpo_canary/fixture",
            "starter_dir": "generalized_cpp_grpo_canary/fixture",
            "train": False,
            "preflight_response": (
                "arithmetic.h\n```cpp\n#pragma once\n"
                "namespace demo { int add(int, int); int multiply(int, int); }\n```\n\n"
                "arithmetic.cpp\n```cpp\n#include \"arithmetic.h\"\n"
                "namespace demo { int add(int a, int b) { return a + b; } "
                "int multiply(int a, int b) { return a * b; } }\n```\n"
            ),
        }
    }
    for task_id in TASKS:
        fixture = FIXTURES / task_id
        if not fixture.is_dir() or fixture.is_symlink():
            raise ValueError(f"missing fixture: {task_id}")
        stem = task_id.replace("-", "_")
        candidate_files = [f"{stem}.cpp", f"{stem}.h"]
        protected = {
            path.relative_to(fixture).as_posix(): sha256(path)
            for path in sorted(fixture.rglob("*"))
            if path.is_file()
        }
        missing = [name for name in candidate_files if name not in protected]
        if missing:
            raise ValueError(f"{task_id} is missing starter files: {missing}")
        manifest = {
            "schema_version": 1,
            "task_id": task_id,
            "source": (
                f"official:Aider-AI/polyglot-benchmark@{POLYGLOT_COMMIT}"
                f"/cpp/exercises/practice/{task_id}"
                if task_id in TRAIN_TASKS
                else f"repository:Reward_GRPO/multi_env_fixtures/{task_id}"
            ),
            "candidate_files": candidate_files,
            "protected_files": protected,
            "fixture_dir": f"multi_env_fixtures/{task_id}",
            "policies": {policy: [] for policy in POLICY_IDS},
        }
        destination = OUTPUT / f"{task_id}.json"
        destination.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        response_parts = []
        for name in candidate_files:
            suffix = Path(name).suffix
            reference = fixture / ".meta" / f"example{suffix}"
            source = reference if reference.is_file() else fixture / name
            response_parts.append(
                aider_listing(name, source.read_text(encoding="utf-8"))
            )
        preflight_response = "\n".join(response_parts)
        tasks[task_id] = {
            "manifest": f"generalized_cpp_grpo_tasks/{task_id}.json",
            "manifest_sha256": sha256(destination),
            "fixture_dir": f"multi_env_fixtures/{task_id}",
            "preflight_response": preflight_response,
            "train": task_id in TRAIN_TASKS,
            "validation": task_id in VALIDATION_TASKS,
            "family": (
                VALIDATION_FAMILIES.get(task_id)
                or TRAIN_FAMILIES.get(task_id)
                or task_id
            ),
            "lineage_id": (
                f"polyglot-cpp/{task_id}"
                if task_id in TRAIN_TASKS
                else f"heldout-analog-v1/{task_id}"
            ),
            "admission_evidence": (
                "phone-number-iter14-midband-v1"
                if task_id in ADMITTED_MIDBAND_TASKS
                else "legacy-september-1-curriculum"
                if task_id in LEGACY_TRAIN_TASKS
                else "heldout-monitor-v1"
            ),
        }
        print(f"{task_id} {sha256(destination)}")
    registry = {
        "schema_version": 1,
        "dataset": {
            "dataset_tag": "generalized-cpp-v2-heldout-monitor",
            "category": "generalized-cpp-curriculum",
            "objective_group": "aider-fixed26-transfer",
            "midband_admission": "phone-number-iter14-midband-v1",
            "source_locator": (
                "mixed:official-fixed26-training+repository-heldout-analogs"
            ),
            "official_task_id_overlap": TRAIN_TASKS,
            "official_training_authorized": True,
        },
        "tasks": tasks,
    }
    REGISTRY.write_text(
        json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"registry {sha256(REGISTRY)}")


if __name__ == "__main__":
    main()

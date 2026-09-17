from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from Reward_GRPO import generalized_cpp_grpo as adapter


ROOT = Path(__file__).parents[1]
CANARY = ROOT / "Reward_GRPO/generalized_cpp_grpo_canary"


def response(expression: str = "a + b") -> str:
    return (
        "arithmetic.h\n```cpp\n#pragma once\n"
        "namespace demo { int add(int, int); int multiply(int, int); }\n```\n\n"
        "arithmetic.cpp\n```cpp\n#include \"arithmetic.h\"\n"
        "namespace demo { int add(int a, int b) { return "
        f"{expression}; }} int multiply(int a, int b) {{ return a * b; }} }}\n```\n"
    )


def sample(text: str, *, digest: str | None = None) -> dict:
    metadata = {
        "task_id": "generalized-cpp/portable-arithmetic",
        "problem_id": "portable-arithmetic",
        "split": "train",
    }
    if digest is not None:
        metadata["generalized_verifier_manifest_sha256"] = digest
    return {
        "metadata": metadata,
        "response": text,
        "rollout_id": "rollout-1",
        "index": 0,
    }


def test_valid_response_runs_end_to_end() -> None:
    binding = adapter.TaskRegistry(adapter.DEFAULT_REGISTRY).resolve(
        "portable-arithmetic"
    )
    record = adapter.score_sample(sample(response(), digest=binding.manifest_sha256))
    assert record["infrastructure_error"] is False
    assert record["score"] == 1.0
    assert record["reason"] == "pass"
    assert record["format_valid"] is True
    assert record["candidate_source_unchanged"] is True
    assert record["policy_results"]
    assert record["kernel_results"]


def test_semantic_failure_is_model_failure_not_infrastructure() -> None:
    record = adapter.score_sample(sample(response("a - b")))
    assert record["infrastructure_error"] is False
    assert record["score"] == pytest.approx(-0.45 + 0.45 * 0.5)
    assert record["candidate_semantic_fraction"] == pytest.approx(0.5)
    assert record["reason"] == "fail"
    policies = {item["policy_id"]: item for item in record["policy_results"]}
    assert policies["G03"]["status"] == "fail"


def test_invalid_response_is_a_format_reward_not_worker_failure() -> None:
    record = adapter.score_sample(sample("unfinished response"))
    assert record["infrastructure_error"] is False
    assert record["score"] == pytest.approx(-1.0)
    assert record["reason"] == "invalid_format"
    assert record["integrity_verdict"] == "EMPTY"
    assert record["policy_results"] == []


@pytest.mark.parametrize(
    "wrapper",
    [
        lambda name: f"**{name}**",
        lambda name: f"*{name}*",
        lambda name: f"`{name}:`",
    ],
)
def test_markdown_wrapped_editable_names_are_semantically_verified(wrapper) -> None:
    decorated = response()
    for name in ("arithmetic.h", "arithmetic.cpp"):
        decorated = decorated.replace(f"{name}\n```", f"{wrapper(name)}\n```", 1)
    record = adapter.score_sample(sample(decorated))
    assert record["infrastructure_error"] is False
    assert record["format_valid"] is False
    assert record["reason"] == "pass"
    assert record["score"] == pytest.approx(0.975)
    policies = {item["policy_id"]: item for item in record["policy_results"]}
    assert policies["G03"]["status"] == "pass"
    assert policies["G05"]["status"] == "pass"


def test_salvageable_forbidden_listing_reaches_semantic_and_boundary_checks() -> None:
    output = (
        "CMakeLists.txt\n```cmake\nproject(do_not_apply)\n```\n\n"
        + response()
    )
    record = adapter.score_sample(sample(output))
    policies = {item["policy_id"]: item for item in record["policy_results"]}
    assert record["infrastructure_error"] is False
    assert record["format_valid"] is False
    assert record["score"] == pytest.approx(-0.05)
    assert policies["G03"]["status"] == "pass"
    assert policies["G05"]["status"] == "fail"


def test_salvageable_duplicate_listing_uses_last_edit_and_reaches_verifiers() -> None:
    duplicate_cpp = response().split("arithmetic.cpp\n", 1)[1]
    output = response() + "\narithmetic.cpp\n" + duplicate_cpp
    record = adapter.score_sample(sample(output))
    policies = {item["policy_id"]: item for item in record["policy_results"]}
    assert record["infrastructure_error"] is False
    assert record["format_valid"] is False
    assert record["score"] == pytest.approx(-0.05)
    assert policies["G03"]["status"] == "pass"
    assert policies["G05"]["status"] == "fail"


def test_only_forbidden_listing_remains_a_hard_model_failure() -> None:
    output = "CMakeLists.txt\n```cmake\nproject(do_not_apply)\n```\n"
    record = adapter.score_sample(sample(output))
    assert record["infrastructure_error"] is False
    assert record["reason"] == "forbidden_file"
    assert record["score"] == -1.0
    assert record["policy_results"] == []


def test_metadata_binding_mismatch_is_infrastructure_invalid() -> None:
    record = adapter.score_sample(sample(response(), digest="0" * 64))
    assert record["infrastructure_error"] is True
    assert record["score"] == 0.0
    assert record["reason"] == "metadata_binding_mismatch"


def test_registry_rejects_protected_fixture_tampering(tmp_path: Path) -> None:
    copied = tmp_path / "canary"
    shutil.copytree(CANARY, copied)
    registry_path = tmp_path / "registry.json"
    registry_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "tasks": {
                    "portable-arithmetic": {
                        "manifest": "canary/manifest.json",
                        "manifest_sha256": adapter._sha256(copied / "manifest.json"),
                        "fixture_dir": "canary/fixture",
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    (copied / "fixture/arithmetic_test.cpp").write_text(
        "// tampered\n", encoding="utf-8"
    )
    with pytest.raises(adapter.BindingError) as raised:
        adapter.TaskRegistry(registry_path).resolve("portable-arithmetic")
    assert raised.value.reason == "protected_file_mismatch"


def test_batch_neutralizes_infrastructure_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    binding = adapter.TaskRegistry(adapter.DEFAULT_REGISTRY).resolve(
        "portable-arithmetic"
    )
    valid = sample(response(), digest=binding.manifest_sha256)
    invalid = sample(response(), digest="0" * 64)
    invalid["index"] = 1
    monkeypatch.setenv(adapter.WORKERS_ENV, "2")
    records = asyncio.run(adapter.reward_func(None, [valid, invalid]))
    assert isinstance(records, list)
    assert records[0]["score"] == 1.0
    assert records[1]["infrastructure_error"] is True
    assert records[1]["score"] == 1.0
    assert records[1]["score_neutralized"] is True


def test_heldout_monitor_is_disjoint_and_starters_are_semantic_negatives() -> None:
    registry = adapter._registry()
    train_ids = set(adapter._curriculum_task_ids(registry))
    heldout_ids = set(adapter._validation_task_ids(registry))
    samples = adapter._heldout_negative_samples(registry)

    assert len(train_ids) == 16
    assert len(heldout_ids) == 4
    assert train_ids.isdisjoint(heldout_ids)
    assert {sample["metadata"]["problem_id"] for sample in samples} == heldout_ids

    records = asyncio.run(adapter.reward_func(None, samples))
    assert isinstance(records, list)
    for item, record in zip(samples, records):
        adapter._validate_heldout_negative_record(item, record)


def test_midband_admission_is_recomputed_from_bound_receipts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    registry = adapter._registry()
    adapter.validate_midband_admission(registry)
    assert set(adapter._admitted_midband_task_ids(registry)) == {
        "allergies",
        "bank-account",
        "circular-buffer",
        "dnd-character",
        "queen-attack",
        "space-age",
        "spiral-matrix",
        "sublist",
        "yacht",
    }

    tampered = json.loads(adapter.DEFAULT_MIDBAND_ADMISSION.read_text())
    tampered["admitted_tasks"]["allergies"]["pass_at_1"] = 3
    path = tmp_path / "tampered-admission.json"
    path.write_text(json.dumps(tampered), encoding="utf-8")
    monkeypatch.setattr(adapter, "DEFAULT_MIDBAND_ADMISSION", path)
    with pytest.raises(adapter.BindingError, match="advertised and observed"):
        adapter.validate_midband_admission(registry)


def test_preflight_runs_registered_canary(capsys: pytest.CaptureFixture[str]) -> None:
    adapter.preflight()
    output = capsys.readouterr().out
    assert "GENERALIZED_CPP_MUTATION_CONTROLS_READY tasks=16 cases=96" in output
    assert "GENERALIZED_CPP_HELDOUT_MONITOR_READY tasks=4 starter_controls=4" in output
    assert "GENERALIZED_CPP_GRPO_READY" in output


def test_dnd_reference_keeps_maximum_rand_draws_within_ability_range(tmp_path: Path) -> None:
    """Reference-only fault injection; candidates may use any legitimate RNG."""
    compiler = shutil.which("g++")
    if compiler is None:
        pytest.skip("g++ is required for the D&D reference boundary regression")
    fixture = ROOT / "Reward_GRPO/multi_env_fixtures/dnd-character"
    for suffix in ("h", "cpp"):
        shutil.copyfile(fixture / ".meta" / f"example.{suffix}",
                        tmp_path / f"dnd_character.{suffix}")
    driver = tmp_path / "reference_boundary.cpp"
    driver.write_text(
        '#include "dnd_character.h"\n'
        '#include <cstdlib>\n'
        'extern "C" int __wrap_rand() {\n'
        '    static int draws = 0;\n'
        '    return draws++ < 4 ? RAND_MAX : 0;\n'
        '}\n'
        'int main() {\n'
        '    const int result = dnd_character::ability();\n'
        '    return result >= 3 && result <= 18 ? 0 : 1;\n'
        '}\n',
        encoding="utf-8",
    )
    executable = tmp_path / "reference_boundary"
    build = subprocess.run(
        [compiler, "-std=c++17", "-Wall", "-Wextra", "-Wpedantic", "-Werror",
         str(driver), str(tmp_path / "dnd_character.cpp"), "-Wl,--wrap=rand",
         "-o", str(executable)],
        capture_output=True, text=True, timeout=60,
    )
    assert build.returncode == 0, build.stderr
    run = subprocess.run([str(executable)], capture_output=True, text=True, timeout=5)
    assert run.returncode == 0, run.stdout + run.stderr

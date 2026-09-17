from __future__ import annotations

import json
import shutil
import sys

import pytest

from Reward_GRPO.generalized_cpp_grpo import BindingError, DEFAULT_REGISTRY, _reconstruct
from Reward_GRPO.topic_coverage import runner
from Reward_GRPO.topic_coverage.__main__ import control_matches, main
from Reward_GRPO.topic_coverage.controls import controls
from Reward_GRPO.topic_coverage.specs import TOPICS


def command(stdout: str, code: int = 0) -> dict:
    return {"stdout_tail": stdout, "returncode": code, "timed_out": False}


def receipt(**fields) -> str:
    return runner.MARKER + json.dumps({
        "protocol": "topic-coverage-v1", "group": "case", "status": "pass", "checks": 1,
        **fields,
    })


def test_exact_scope_and_diagnostic_separation():
    assert set(TOPICS) == {
        "allergies", "bank-account", "circular-buffer", "complex-numbers",
        "dnd-character", "grade-school", "space-age", "sublist", "clock", "yacht", "perfect-numbers",
    }
    assert sum(len(topic.groups) for topic in TOPICS.values()) == 64
    assert sum(len(topic.diagnostics) for topic in TOPICS.values()) == 2
    for topic in TOPICS.values():
        assert not set(topic.groups) & set(topic.diagnostics)


def test_cli_requires_explicit_local_execution(tmp_path, monkeypatch):
    output = tmp_path / "must-not-exist"
    monkeypatch.setattr(sys, "argv", ["topic_coverage", "validate", "--output", str(output)])
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2
    assert not output.exists()


@pytest.mark.parametrize("fields", [
    {"protocol": "wrong"}, {"group": "wrong"}, {"status": "invalid"},
    {"checks": 0}, {"checks": True}, {"checks": -1}, {"checks": "100"},
])
def test_protocol_cannot_claim_false_success(fields):
    assert runner.parse_result(command(receipt(**fields)), "case")["status"] == "fail"


def test_protocol_requires_successful_exit_and_unique_receipt():
    assert runner.parse_result(command(receipt(), 1), "case")["status"] == "fail"
    assert runner.parse_result(command(receipt() + "\n" + receipt()), "case")["status"] == "fail"
    assert runner.parse_result(command("candidate debug line\n" + receipt()), "case")["status"] == "pass"
    assert runner.parse_result(command(""), "case")["status"] == "fail"


def test_protocol_distinguishes_launch_failure_and_timeout():
    assert runner.parse_result({"launch_error": "OSError"}, "case")["status"] == "invalid"
    assert runner.parse_result({"timed_out": True}, "case")["reason"] == "runtime_timeout"


def test_random_samples_need_not_fail_at_the_same_index():
    runs = [{"status": "fail", "checks": 7, "requirement": "hitpoints"},
            {"status": "fail", "checks": 35, "requirement": "hitpoints"}]
    random = runner.aggregate_group("character_rules", runs, variable_sampling=True)
    assert random["status"] == "fail"
    assert random["repeatable"] is False
    assert runner.aggregate_group("fixed_inputs", runs)["status"] == "fail"
    mixed = [{"status": "pass", "checks": 100}, runs[0]]
    assert runner.aggregate_group("ability_range", mixed, variable_sampling=True)["status"] == "fail"


def test_unknown_reference_failure_does_not_blame_candidate(tmp_path, monkeypatch):
    monkeypatch.setattr(runner.AuditSession, "_execute",
                        lambda *args: {"status": "fail", "reason": "reference_semantics"})
    with runner.AuditSession("allergies", tmp_path / "audit", allow_local_execution=True) as session:
        record = session.audit(runner.control_sources(session.binding, session.task_id))
    assert record["status"] == "invalid"
    assert record["reason"] == "reference_control_failed"


def test_source_reader_rejects_symlinks(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    (real / "allergies.h").write_text("// h")
    (real / "allergies.cpp").write_text("// cpp")
    linked = tmp_path / "linked"
    linked.symlink_to(real, target_is_directory=True)
    with pytest.raises(ValueError):
        runner.candidate_sources("allergies", linked)
    (real / "allergies.h").unlink()
    (real / "allergies.h").symlink_to(real / "allergies.cpp")
    with pytest.raises(ValueError):
        runner.candidate_sources("allergies", real)


def test_input_checks_do_not_launch(tmp_path):
    with pytest.raises(ValueError, match="acknowledgement"):
        runner.AuditSession("allergies", tmp_path / "out")
    with pytest.raises(ValueError, match="unsupported"):
        runner.AuditSession("phone-number", tmp_path / "out", allow_local_execution=True)
    with pytest.raises(ValueError, match="repeats"):
        runner.AuditSession("allergies", tmp_path / "out", repeats=0, allow_local_execution=True)
    with pytest.raises(ValueError, match="timeouts"):
        runner.AuditSession("allergies", tmp_path / "out", run_timeout=float("nan"),
                            allow_local_execution=True)
    assert not (tmp_path / "out").exists()


def test_output_is_never_overwritten(tmp_path):
    output = tmp_path / "existing"
    output.mkdir()
    with pytest.raises(ValueError, match="new directory"):
        runner.AuditSession("allergies", output, allow_local_execution=True)
    saved = output / "receipt.json"
    runner.write_json(saved, {"original": True})
    with pytest.raises(FileExistsError):
        runner.write_json(saved, {"original": False})
    assert json.loads(saved.read_text()) == {"original": True}


def test_dotdot_cannot_escape_protected_output_check():
    fixture = DEFAULT_REGISTRY.parent / "multi_env_fixtures" / "allergies"
    output = DEFAULT_REGISTRY.parent / "topic_coverage" / ".." / "multi_env_fixtures" / "allergies" / "not-created"
    with pytest.raises(ValueError, match="protected"):
        runner.AuditSession("allergies", output, allow_local_execution=True)
    assert not (fixture / "not-created").exists()


def test_other_topic_fixture_is_also_protected():
    output = DEFAULT_REGISTRY.parent / "multi_env_fixtures" / "bank-account" / "not-created"
    with pytest.raises(ValueError, match="protected"):
        runner.AuditSession("allergies", output, allow_local_execution=True)
    assert not output.exists()


def test_fixture_tampering_is_rejected_before_execution(tmp_path):
    root = DEFAULT_REGISTRY.parent
    entry = json.loads(DEFAULT_REGISTRY.read_text())["tasks"]["allergies"]
    fixture = tmp_path / entry["fixture_dir"]
    fixture.parent.mkdir(parents=True)
    shutil.copytree(root / entry["fixture_dir"], fixture)
    manifest = tmp_path / entry["manifest"]
    manifest.parent.mkdir(parents=True)
    shutil.copy2(root / entry["manifest"], manifest)
    registry = tmp_path / "registry.json"
    registry.write_text(json.dumps({"schema_version": 1, "tasks": {"allergies": entry}}))
    test = fixture / "allergies_test.cpp"
    test.write_text(test.read_text() + "\n// changed control\n")
    with pytest.raises(BindingError, match="allergies_test.cpp"):
        runner.AuditSession("allergies", tmp_path / "out", registry_path=registry,
                            allow_local_execution=True)
    assert not (tmp_path / "out").exists()


def test_missing_compiler_is_infrastructure_invalid(tmp_path):
    with runner.AuditSession("allergies", tmp_path / "audit", compiler="/nonexistent/topic-g++",
                             allow_local_execution=True) as session:
        record = session.audit(runner.control_sources(session.binding, session.task_id))
    assert record["status"] == "invalid"
    assert record["reason"] == "reference_control_failed"
    assert "candidate" not in record


@pytest.mark.skipif(shutil.which("g++") is None, reason="C++ compiler required")
@pytest.mark.parametrize("task", tuple(TOPICS))
def test_reference_alternative_and_semantic_mutant(task, tmp_path):
    with runner.AuditSession(task, tmp_path / task, allow_local_execution=True) as session:
        assert session.reference["status"] == "pass", session.reference
        positive, mutant, *_ = controls(task, runner.control_sources(session.binding, session.task_id))
        alternative = session.audit(positive.sources, "alternative")
        assert control_matches(alternative, positive), alternative
        bad = session.audit(mutant.sources, "mutant")
        assert control_matches(bad, mutant), bad
        assert bad["changes_grpo_reward"] is False
        assert bad["full_task_correctness_claim"] is False
        assert all(group["repeatable"] for group in bad["candidate"]["groups"])
        assert bad["candidate"]["candidate_source_unchanged"]


def test_diagnostic_warning_never_changes_topic_status(tmp_path):
    with runner.AuditSession("dnd-character", tmp_path / "audit", include_diagnostics=True,
                             allow_local_execution=True) as session:
        control = next(item for item in controls(
            "dnd-character", runner.control_sources(session.binding, session.task_id)
        ) if item.kind == "diagnostic")
        record = session.audit(control.sources)
        assert control_matches(record, control)
        assert record["status"] == "pass"
        assert record["changes_grpo_reward"] is False


def test_child_does_not_receive_credentials_and_is_bounded(tmp_path, monkeypatch):
    monkeypatch.setenv("HF_TOKEN", "unit-test-not-a-real-token")
    monkeypatch.setenv("WANDB_API_KEY", "unit-test-not-a-real-key")
    with runner.AuditSession("allergies", tmp_path / "audit",
                             allow_local_execution=True) as session:
        record = session._command(
            [sys.executable, "-c",
             "import os, shutil; assert shutil.which('g++'); assert 'HF_TOKEN' not in os.environ; "
             "assert 'WANDB_API_KEY' not in os.environ; print('clean')"],
            session.output, "environment", 5,
        )
        assert record["returncode"] == 0
        assert record["stdout_tail"].strip() == "clean"
        timed = session._command([sys.executable, "-c", "import time; time.sleep(10)"],
                                 session.output, "bounded", .1)
        assert timed["timed_out"]
        assert timed["elapsed_seconds"] < 5


def test_aider_response_reuses_existing_reconstruction(tmp_path):
    with runner.AuditSession("allergies", tmp_path / "audit", allow_local_execution=True) as session:
        response = runner.response_from_sources(runner.control_sources(session.binding, session.task_id))
        reconstructed = session.work / "response"
        assert _reconstruct(session.binding, response, reconstructed)
        sources = runner.candidate_sources("allergies", reconstructed)
        assert session.audit(sources)["status"] == "pass"


def test_added_coverage_beyond_generalized(tmp_path):
    with runner.AuditSession("allergies", tmp_path / "audit", allow_local_execution=True) as session:
        control = next(item for item in controls(
            "allergies", runner.control_sources(session.binding, session.task_id)
        ) if item.name == "high_bit_alias")
        extra = session.audit(control.sources)
        baseline = session.compare_generalized(control.sources)
        assert baseline["reason"] == "pass", baseline
        assert baseline["score"] == 1.0
        assert extra["status"] == "fail"
        assert extra["changes_grpo_reward"] is False


def test_yacht_rejects_fives_only_despite_old_benchmark_pass(tmp_path):
    """The archived trial-1 repair scored every yacht except five fives as zero."""
    from Reward_GRPO.topic_coverage.controls import edit
    with runner.AuditSession("yacht", tmp_path / "yacht-faces",
                             allow_local_execution=True) as session:
        sources = edit(
            runner.control_sources(session.binding, session.task_id), "yacht.cpp",
            "return is_yacht(dice) ? 50 : 0;",
            "return std::all_of(dice.begin(), dice.end(), [](int value) { return value == 5; }) ? 50 : 0;",
        )
        result = session.audit(sources)
        assert result["candidate"]["build"]["returncode"] == 0
        assert result["status"] == "fail"
        group = next(g for g in result["candidate"]["groups"] if g["group"] == "yacht")
        failure = group["runs"][0]
        assert failure["context"] == "dice=[1,1,1,1,1] category=yacht"
        assert failure["expected"] == "50" and failure["actual"] == "0"


@pytest.mark.parametrize("task,control_names", [
    ("clock", ["unpad_hour", "minutes_only_equality"]),
    ("complex-numbers", ["scalar_adds_imaginary", "scalar_subtracts_imaginary", "componentwise_scalar_division"]),
    ("bank-account", ["overdraft_mutates_balance"]),
    ("dnd-character", ["negative_even_overcorrection"]),
    ("circular-buffer", ["narrow_wide_storage", "only_int_string_instantiations"]),
])
def test_specific_failure_controls(task, control_names, tmp_path):
    with runner.AuditSession(task, tmp_path / task, allow_local_execution=True) as session:
        assert session.reference["status"] == "pass"
        available = {c.name: c for c in controls(task, runner.control_sources(session.binding, session.task_id))}
        for name in control_names:
            control = available[name]
            result = session.audit(control.sources, name)
            assert control_matches(result, control), result
            if task == "clock" and name == "unpad_hour":
                groups = {g["group"]: g["status"] for g in result["candidate"]["groups"]}
                assert groups["canonical_creation"] == "pass" and groups["formatting"] == "fail"


def test_reward_families_partition_requirements():
    from Reward_GRPO.topic_coverage.specs import Topic
    for topic in TOPICS.values():
        members = [member for _, family in topic.families for member in family]
        assert len(members) == len(set(members)) == len(topic.groups)
        assert set(members) == set(topic.groups)
    with pytest.raises(ValueError):
        Topic(("one", "two"), reward_families=(("incomplete", ("one",)),))


@pytest.mark.parametrize("runs", [
    [{"status": "fail", "checks": 4}, {"status": "fail", "reason": "probe_protocol_failure"}],
    [{"status": "pass", "checks": 40}, {"status": "fail", "reason": "runtime_timeout"}],
    [{"status": "pass", "checks": 40}, {"status": "pass", "checks": 39}],
])
def test_inconsistent_candidate_outcomes_are_failures(runs):
    result = runner.aggregate_group("fixed", runs)
    assert result["status"] == "fail" and not result["repeatable"]


def test_actual_launch_failure_stays_infrastructure_invalid():
    result = runner.aggregate_group("fixed", [{"status": "invalid"}, {"status": "fail"}])
    assert result["status"] == "invalid"



def test_sublist_preserves_all_original_empty_domain_pairs(tmp_path):
    with runner.AuditSession("sublist", tmp_path / "empty-domain", allow_local_execution=True) as session:
        group = next(g for g in session.reference["groups"] if g["group"] == "empty_lists")
        assert group["status"] == "pass"
        assert all(r["observations"]["bounded_empty_pairs"] == "681" for r in group["runs"])
        assert all(r["checks"] >= 681 * 3 for r in group["runs"])

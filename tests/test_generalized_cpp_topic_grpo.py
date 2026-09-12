import argparse
import asyncio
import json
from unittest.mock import patch

import pytest

from Reward_GRPO import generalized_cpp_topic_grpo as reward


@pytest.fixture(autouse=True)
def reward_runtime(tmp_path, monkeypatch):
    monkeypatch.setenv("MILES_RUN_ROOT", str(tmp_path))
    monkeypatch.delenv("GENERALIZED_CPP_FAILURE_DIR", raising=False)
    monkeypatch.setattr(reward, "_SCORING_POOL", None)
    yield
    if reward._SCORING_POOL is not None:
        reward._SCORING_POOL[2].shutdown(wait=True, cancel_futures=True)


def record(score=1.0):
    return dict(problem_id="allergies", score=score, reward=score, infrastructure_error=False)


def topic_receipt(task="allergies", failed=()):
    groups = [dict(group=name, status="fail" if name in failed else "pass")
              for name in reward.TOPICS[task].groups]
    status = "fail" if failed else "pass"
    return dict(status=status, reference_status="pass",
                candidate=dict(status=status, reason="topic_checks", build=dict(returncode=0), groups=groups))


def test_extra_failure_blocks_baseline_success():
    result = reward.compose(record(), topic_receipt(failed=("all_masks",)))
    assert result["generalized_score"] == 1
    assert result["score"] == result["reward"] == pytest.approx(-1 / 6)
    assert result["reason"] == "topic_correctness_failed"


@pytest.mark.parametrize("score", [-1.0, -0.85, -0.05, 0.975, 1.0])
def test_topic_pass_keeps_generalized_failures_nonpositive_and_preserves_full_pass(score):
    result = reward.compose(record(score), topic_receipt())
    assert result["score"] == result["reward"] == (score if score > 0 else score / 2)


def test_semantic_progress_is_not_flattened_and_never_becomes_positive():
    previous = -2
    for failures in [("all_masks", "higher_bits", "query_stability"),
                     ("all_masks", "higher_bits"), ("all_masks",), ()]:
        result = reward.compose(record(-0.25), topic_receipt(failed=failures))
        assert previous < result["score"] <= 0
        previous = result["score"]
    partial = topic_receipt(failed=("all_masks",))
    assert reward.compose(record(-0.05), partial)["score"] > reward.compose(record(-0.25), partial)["score"]


def test_yacht_category_repairs_receive_credit_without_face_count_dominance():
    task = "yacht"
    base = {**record(), "problem_id": task}
    before = reward.compose(base, topic_receipt(task, ("four_of_a_kind", "yacht")))
    after = reward.compose(base, topic_receipt(task, ("yacht",)))
    faces = reward.compose(base, topic_receipt(task, ("ones", "twos", "threes", "fours", "fives", "sixes")))
    assert before["score"] < after["score"] < 0
    assert after["score"] == pytest.approx(faces["score"])
    assert reward.compose(base, topic_receipt(task))["score"] == 1


def test_fail_fast_counts_and_diagnostics_cannot_increase_reward():
    receipt = topic_receipt(failed=("all_masks",))
    original = reward.compose(record(), receipt)["score"]
    for group in receipt["candidate"]["groups"]:
        group["checks"] = 10**20
    receipt["candidate"]["diagnostics"] = [dict(group="invented", status="pass")]
    assert reward.compose(record(), receipt)["score"] == original


@pytest.mark.parametrize("corruption", ["missing", "duplicate", "extra", "invalid", "verdict", "reference", "build"])
def test_incomplete_or_inconsistent_receipts_are_neutralized(corruption):
    receipt = topic_receipt(failed=("all_masks",))
    groups = receipt["candidate"]["groups"]
    if corruption == "missing": groups.pop()
    elif corruption == "duplicate": groups.append(groups[0])
    elif corruption == "extra": groups.append(dict(group="bonus", status="pass"))
    elif corruption == "invalid": groups[0]["status"] = "invalid"
    elif corruption == "verdict": receipt["status"] = "pass"
    elif corruption == "reference": receipt["reference_status"] = "fail"
    else: receipt["candidate"]["build"]["returncode"] = 1
    result = reward.compose(record(), receipt)
    assert result["infrastructure_error"] and result["score"] == result["reward"] == 0


def test_additional_build_failure_gets_zero_requirement_credit():
    receipt = dict(status="fail", reference_status="pass", candidate=dict(
        status="fail", reason="build_failure", build=dict(returncode=1), groups=[]))
    result = reward.compose(record(), receipt)
    assert not result["infrastructure_error"] and result["score"] == -0.5
    assert result["topic_requirement_score"]["fraction"] == 0


def test_invalid_topic_is_not_a_candidate_failure():
    result = reward.compose(record(), {"status": "invalid"})
    assert result["infrastructure_error"]
    assert result["score"] == result["reward"] == 0


def test_missing_contract_never_executes_candidate():
    with patch.object(reward, "docker_command", side_effect=AssertionError("must not execute")):
        result = reward.score_sample({"metadata": {"problem_id": "allergies"}, "response": ""})
    assert result["infrastructure_error"]


def test_container_has_no_host_mounts_or_network():
    with patch.object(reward, "image_identity", return_value="sha256:fixture"):
        command = reward.docker_command("test")
    assert command[command.index("--network") + 1] == "none"
    assert command[command.index("--user") + 1] == "65534:65534"
    assert "--read-only" in command and "--mount" not in command and "-v" not in command
    assert "WANDB_API_KEY" not in " ".join(command)


def test_forbidden_listing_never_reaches_compiler():
    with patch.object(reward.base, "score_sample", side_effect=AssertionError("must not execute")):
        result = reward.worker_score({"metadata": {"problem_id": "allergies"},
                                      "response": "CMakeLists.txt\n```\nproject(bypass)\n```\n"})
    assert result["score"] == -1 and result["reason"] == "forbidden_file"


@pytest.mark.parametrize("batch", [False, True])
def test_infrastructure_retries_without_fabricating_reward(batch):
    bad = dict(problem_id="allergies", score=0., reward=0., infrastructure_error=True)
    good = dict(problem_id="allergies", score=-0.5, reward=-0.5, infrastructure_error=False)
    with patch.object(reward, "score_sample", side_effect=[bad, bad, good]) as mocked:
        result = asyncio.run(reward.reward_func(None, [{}] if batch else {}))
    result = result[0] if batch else result
    assert result["score"] == result["reward"] == -0.5
    assert result["infrastructure_attempts"] == mocked.call_count == 3


@pytest.mark.parametrize("batch", [False, True])
def test_persistent_infrastructure_cannot_return_training_reward(batch):
    bad = dict(problem_id="allergies", score=0., reward=0., infrastructure_error=True)
    with patch.object(reward, "score_sample", return_value=bad) as mocked:
        with pytest.raises(reward.RewardInfrastructureError, match="no reward returned"):
            asyncio.run(reward.reward_func(None, [{}] if batch else {}))
    assert mocked.call_count == 3


def test_candidate_failure_is_not_retried():
    with patch.object(reward, "score_sample", return_value=record(-1.)) as mocked:
        result = asyncio.run(reward.reward_func(None, {}))
    assert result["score"] == -1. and mocked.call_count == 1


def test_combined_receipt_marks_reward_role_without_mutating_audit():
    topic = {**topic_receipt(), "audit_only": True, "changes_grpo_reward": False}
    result = reward.compose(record(), topic)
    assert result["topic_coverage"]["changes_grpo_reward"] is True
    assert result["topic_coverage"]["audit_only"] is False
    assert topic["audit_only"] is True and topic["changes_grpo_reward"] is False


def test_export_binds_all_15_train_and_four_heldout(tmp_path):
    args = argparse.Namespace(curriculum=reward.CURRICULUM, tasks_dir=str(reward.base.REWARD_ROOT),
                              out=tmp_path / "data", train_limit=None, eval_limit=None,
                              profile="test", run_id="test", sort_by_size=False, force=False)
    paths = reward.build_data(args)
    manifest = json.loads(open(paths["manifest"]).read())
    assert manifest["counts"]["train"] == 15 and manifest["counts"]["validation"] == 4
    assert manifest["topic_groups"] == 64
    assert manifest["reward_scoring_version"] == "topic-family-v3"
    assert "topic_failure_cap" not in manifest
    assert set(manifest["topic_reward_families"]) == set(reward.TOPICS)
    assert {"clock", "yacht"} <= set(manifest["topic_tasks"])
    for path in args.out.rglob("*.jsonl"):
        for line in path.read_text().splitlines():
            row = json.loads(line)
            assert row["metadata"]["combined_reward_sha256"] == reward.contract_digest()
            assert not row["metadata"]["problem_id"].startswith("charm-")
    assert manifest["reward_function"] == reward.MODULE + ".reward_func"


def semantic_engine():
    import importlib.util
    path = reward.ROOT / 'generalized_verifier_docs/04_differential_semantic_verifier.py'
    spec = importlib.util.spec_from_file_location('semantic_under_test', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('exit_code', [1, -11, 124])
def test_success_text_with_failed_exit_cannot_earn_correctness(exit_code):
    result = semantic_engine().parse_catch2_output('All tests passed (12 assertions in 3 test cases)', exit_code)
    assert result.score == 0
    assert result.as_dict()['returncode'] == exit_code


def test_fake_success_before_real_failure_uses_failure_summary():
    result = semantic_engine().parse_catch2_output(
        'All tests passed (999 assertions in 1 test case)\nassertions: 10 | 4 passed | 6 failed', 1)
    assert result.score == 0.4 and result.total == 10


def test_ambiguous_success_summaries_are_not_accepted():
    result = semantic_engine().parse_catch2_output(
        'All tests passed (10 assertions in 1 test case)\nAll tests passed (999 assertions in 1 test case)', 0)
    assert result.score == 0


def test_catch_exit_is_failed_case_count_not_only_one():
    result = semantic_engine().parse_catch2_output('assertions: 10 | 4 passed | 6 failed', 3)
    assert result.score == 0.4


def test_timeout_receipt_retains_failure_type_and_output():
    import subprocess
    engine = semantic_engine()
    with patch.object(engine.subprocess, "run", side_effect=subprocess.TimeoutExpired(
            "binary", 0.1, output=b"negative input started\n")):
        result = engine.run_test_binary("binary", timeout=0.1)
    data = result.as_dict()
    assert result.score == 0 and data["timed_out"]
    assert data["failure_kind"] == "runtime_timeout" and data["timeout_seconds"] == 0.1
    assert data["signal"] is None and "negative input started" in data["raw_tail"]


def test_signal_receipt_is_distinct_from_timeout():
    data = semantic_engine().parse_catch2_output("", -11).as_dict()
    assert data["failure_kind"] == "signal" and data["signal"] == 11
    assert data["timed_out"] is False


@pytest.mark.parametrize("output", [
    "assertions: unavailable", "assertions: 0 | 0 passed",
    "assertions: 10 | 9 passed | 9 failed", "assertions: 10 | 11 passed",
    "assertions: 10 | 3 passed | 4 passed | 6 failed",
    "assertions: 10 | 4 passed | six failed", "assertions: 10",
])
def test_malformed_summary_never_crashes_parser_or_earns_partial_credit(output):
    run = semantic_engine().parse_catch2_output(output, 1)
    assert run.score == 0 and run.crashed
    assert run.as_dict()["failure_kind"] == "incomplete_test_output"

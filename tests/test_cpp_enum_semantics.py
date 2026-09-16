"""Exercise semantic enum controls through the real compiler, G03 and topic runner."""
import json
import hashlib
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from Reward_GRPO import generalized_cpp_grpo as reward
from Reward_GRPO.topic_coverage.controls import enum_controls
from Reward_GRPO.topic_coverage.runner import AuditSession
from Reward_GRPO.topic_coverage.specs import TOPICS

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "Reward_GRPO/multi_env_fixtures"
CONTROL_NAMES = ("nonstandard_enum_values", "collapsed_enum_constant", "partially_aliased_enum")


def reference_sources(task):
    fixture = FIXTURES / task
    stem = task.replace("-", "_")
    return {stem + suffix: (fixture / ".meta" / ("example" + suffix)).read_text()
            for suffix in (".h", ".cpp")}


def control(task, name):
    return next(item for item in enum_controls(task, reference_sources(task)) if item.name == name)


@pytest.mark.parametrize("task", ["kindergarten-garden", "sublist"])
@pytest.mark.parametrize("name", CONTROL_NAMES)
def test_official_enum_controls_through_g03_reward(task, name, tmp_path):
    selected = control(task, name)
    for filename, content in selected.sources.items():
        (tmp_path / filename).write_text(content)
    from Reward_GRPO import global_cpp_verifier_runner as runner
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    for filename, content in selected.sources.items():
        (candidate / filename).write_text(content)
    manifest = {"schema_version": 1, "task_id": task, "fixture_dir": str(FIXTURES/task),
        "candidate_files": list(selected.sources), "policies": {f"G{i:02d}": [] for i in range(1, 6)},
        "response_text": reward._render_whole_file_response(selected.sources)}
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))
    output = tmp_path / "aggregate"
    runner.main(["--candidate-dir", str(candidate), "--manifest", str(path),
        "--expected-manifest-sha256", hashlib.sha256(path.read_bytes()).hexdigest(),
        "--output-dir", str(output), "--reward-root", str(ROOT/"Reward_GRPO"), "--profile", "live"])
    receipt = json.loads((output/runner.AGGREGATE_RECEIPT).read_text())
    policy = next(p for p in receipt["policy_results"] if p["policy_id"] == "G03")
    kernels, status, reason = policy["kernels"], receipt["status"], receipt.get("reason")
    score, infrastructure, reward_reason = reward.receipt_to_reward(receipt)
    (tmp_path / "verification.json").write_text(json.dumps(
        {"receipt": receipt, "score": score, "infrastructure_error": infrastructure,
         "reason": reason, "reward_reason": reward_reason}, indent=2))
    assert status == selected.expected
    assert not infrastructure
    assert kernels[0]["status"] == "pass"  # Actual reference compiled and completed.
    candidate = kernels[-1]["facts"]["candidate"]
    assert candidate["status"] == "RAN"  # A semantic rejection, not a broken control build.
    assert candidate["run"]["execution_completed"]
    assert candidate["run"]["verified_pass"] == (selected.expected == "pass")
    if selected.expected == "pass":
        assert score == 1.0
    else:
        assert score < 1.0
        assert candidate["run"]["failure_kind"] == "assertion_failure"


@pytest.mark.parametrize("name", CONTROL_NAMES)
def test_sublist_enum_controls_through_topic_execution(name, tmp_path):
    # Binding/hash admission is separately exercised by the cohort preflight.
    # This isolated session calls the same production compilation, process,
    # parser and group aggregation implementation without mutating registry pins.
    session = AuditSession.__new__(AuditSession)
    session.task_id, session.topic = "sublist", TOPICS["sublist"]
    session.work, session.output = tmp_path / "work", tmp_path / "output"
    session.work.mkdir()
    session.output.mkdir()
    session.compiler, session.compile_timeout, session.run_timeout = shutil.which("g++"), 90, 30
    session.groups, session.repeats = session.topic.groups, 2
    session.binding = SimpleNamespace(manifest={"candidate_files": ["sublist.h", "sublist.cpp"]})
    selected = control("sublist", name)
    result = session._execute(selected.sources, name)
    (tmp_path / "topic.json").write_text(json.dumps(result, indent=2))
    assert result["build"]["returncode"] == 0
    assert result["status"] == selected.expected
    assert result["reason"] == "topic_checks"
    assert len(result["groups"]) == len(session.topic.groups)
    assert all(group["status"] == selected.expected for group in result["groups"])
    if selected.expected == "pass":
        # Preserve the substantive exhaustive comparisons, including the
        # separate empty domain. Merely executing a domain-size check is insufficient.
        records = {group["group"]: group for group in result["groups"]}
        relation_checks = sum(records[group]["runs"][0]["checks"]
                              for group in session.topic.groups[:4])
        assert relation_checks >= 115600 * 3
        assert records["empty_lists"]["runs"][0]["checks"] >= 681 * 3
    else:
        assert all(group["runs"][0]["requirement"] == "named relations are distinct"
                   for group in result["groups"])

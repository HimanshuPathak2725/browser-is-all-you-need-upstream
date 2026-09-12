"""Replay previously reviewed, hash-bound first-attempt code; never repair it."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from Reward_GRPO.topic_coverage.runner import AuditSession, plain_directory, sha256, write_json
from Reward_GRPO.topic_coverage.specs import TOPICS


def extract(case: dict, binding) -> tuple[dict[str, str], list[dict]]:
    history = Path(case["history"])
    if history.is_symlink() or sha256(history) != case["history_sha256"]:
        raise ValueError("historical evidence hash mismatch")
    lines = history.read_text(encoding="utf-8").splitlines()
    sources, provenance = {}, []
    fence = chr(96) * 3
    names = set(binding.manifest["candidate_files"])
    for block in case["pretest_code"]:
        name, line = block["file"], block["history_first_line"]
        if name not in names or name in sources or type(line) is not int or not 2 <= line <= len(lines):
            raise ValueError("invalid or duplicate historical file boundary")
        start = line - 1
        if not lines[start - 1].strip().startswith(fence):
            raise ValueError("recorded source does not begin after an opening fence")
        end = next((i for i in range(start, len(lines)) if lines[i].strip() == fence), None)
        if end is None:
            raise ValueError("historical code block is incomplete")
        sources[name] = "\n".join(lines[start:end]) + "\n"
        provenance.append({"file": name, "history_first_line": line, "history_last_line": end})
    for name in names - set(sources):
        archived = history.parent / name
        starter = binding.starter_dir / name
        if archived.is_symlink() or not archived.is_file() or sha256(archived) != sha256(starter):
            raise ValueError("missing pre-test file cannot be authenticated as unchanged starter")
        sources[name] = starter.read_text(encoding="utf-8")
        provenance.append({"file": name, "unchanged_starter_sha256": sha256(starter)})
    return sources, provenance


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allow-local-execution", action="store_true")
    args = parser.parse_args()
    if not args.allow_local_execution:
        parser.error("review the code and acknowledge local execution before replay")
    evidence = json.loads(args.evidence.read_text(encoding="utf-8"))
    root = plain_directory(args.output)
    fixture_root = Path(__file__).resolve().parents[1] / "Reward_GRPO" / "multi_env_fixtures"
    if root == fixture_root or fixture_root in root.parents:
        parser.error("replay output must be outside all finalized fixtures")
    if root.exists():
        parser.error("replay output must be a new directory")
    root.mkdir(parents=True)
    selected = [case for case in evidence["cases"] if case["task"] in TOPICS]
    records = []
    for task in TOPICS:
        cases = [case for case in selected if case["task"] == task]
        if not cases:
            continue
        with AuditSession(task, root / task, allow_local_execution=True) as session:
            for index, case in enumerate(cases):
                sources, provenance = extract(case, session.binding)
                label = f"attempt-{index}"
                record = session.audit(sources, label)
                source = {"task_id": task, "trial": case["trial"], "history": case["history"],
                          "history_sha256": case["history_sha256"], "files": provenance,
                          "status": record["status"], "reason": record["reason"],
                          "audit_receipt": str(session.output / f"{label}.json")}
                write_json(session.output / f"{label}-provenance.json", source)
                records.append(source)
                print(task, case["trial"], record["status"], record["reason"], flush=True)
    summary = {
        "schema_version": 1, "source_evidence_sha256": sha256(args.evidence),
        "checkpoint": evidence.get("checkpoint"), "audit_only": True,
        "changes_grpo_reward": False, "attempts": len(records),
        "rejected": sum(record["status"] == "fail" for record in records),
        "invalid": sum(record["status"] == "invalid" for record in records),
        "build_rejections": sum(record["status"] == "fail" and record["reason"] == "build_failure"
                                for record in records),
        "behavior_rejections": sum(record["status"] == "fail" and record["reason"] == "topic_checks"
                                   for record in records),
        "records": records,
    }
    summary["status"] = "pass" if records and summary["rejected"] == len(records) else "fail"
    write_json(root / "replay.json", summary)
    return 0 if summary["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

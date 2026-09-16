# Infrastructure classification regression data

`harness-infra-r3-classification.jsonl` preserves all 320 inputs consumed by
`test_classifier_against_r3_ledger`; the expected 80 infrastructure failures and
41 semantic failures accompanied by thread-exhaustion text remain unchanged.
It excludes model responses, candidate source, reward metrics and other fields
that the regression never reads.

Source commit: `c4129bcd5e9d87a53ec3aff25954a04c8302efee`.
Source file: `docs/worklogs/issue110-r3-rollout-forensics/gate_records.jsonl`.
Source SHA-256: `1974605dfdcba46aaaf19ff55871576ea89c73e544a396d7d719be110685b963`.

Projection preserves `format_valid`, `compile_error`, `all_tests_pass` and
`logs.test` verbatim for every row, in source order. Missing `logs.test` uses the
same empty-string default as the original regression. This is frozen regression
input, not new evaluation evidence. The original historical ledger is unchanged.

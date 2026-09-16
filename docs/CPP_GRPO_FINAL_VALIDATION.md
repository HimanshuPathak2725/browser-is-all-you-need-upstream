# C++ cohort v1 engineering validation

## Status

The verifier, selected task assets and local pre-training gate are validated.
Dataset publication, the matched model baseline, GRPO training and checkpoint
evaluation are **not completed**. This document reports engineering validation;
it does not claim measured model improvement from a new training run.

The delivery is additive to Wootzapp `main` at
`af63124313bb0b2634e1f484d3439519b12131b1`. It preserves existing browser workflows.
The source integration was validated at `c4129bcd5e9d87a53ec3aff25954a04c8302efee`
and ported as `7c9ab51b1eb5e7bf53706e770967136d270f4f48`.
All 319 reward files were verified byte-identical across that port. Packaging,
CLI integration and evidence documentation do not change the reward digest.

## Frozen identities

| Component | Identity |
|---|---|
| Cohort | `cpp-grpo-final-v1` |
| Cohort SHA-256 | `97f5260e9d4d43ca990b987344419cd0ce9c2e68007f7db0b0a4e3a85d776733` |
| Combined reward SHA-256 | `4f242b156facd74870f1cf1f0da15fba26beeb3a1b1f0795c2119179364b6731` |
| Validated Docker image ID | `sha256:7af07b2afd4ff9d48e4ed6c59ecef2909d94e79866a85a671413babbcc1e6055` |
| Compiler image base | `gcc:13@sha256:3617a214e52a25bde5375dc9503b5e67f01b6c7322a30137e2790aa8e6db5d1f` |
| PR #6 reliability lineage | `6de7340b446ffbcce62b6dcea3418cd0fd49a5bc` |
| Perfect Numbers fixture | `ba1380edf161eb1ac48b80016d7d40e87a72c71a` |
| Frozen Perfect Numbers controls | `9b67660601a9143c2bfff0e61399c88916fca5b3` |

The launcher transports the exact validated evaluator image. Rebuilding an image
requires a fresh gate; a matching tag alone does not authenticate it. The current
image and complete machine receipts remain external artifacts pending publication.

## Completed gates

| Gate | Result |
|---|---|
| Standalone verifier controls | 14/14 |
| Topic structure self-check | 11 topics, 64 groups, 39 families |
| Shared reliability and enum regression run | 103 passed |
| Final C++ implementation suite | 168 passed |
| Combined Wootzapp/C++ suite | 229 passed, 1 optional Harbor test skipped |
| Optional Harbor test with declared browser extra | Passed separately; all 230 tests exercised |
| Reference/control Docker campaign | 153/153 expected outcomes |
| Selected reference executions | 14/14; full reward; no infrastructure failure |
| Missing-compiler Docker controls | 14/14 INVALID with zero reward |
| Registry/cohort and dataset identities | Authenticated |
| Compileall, CLI help, benchmark list, skill validation | Passed |
| New engineering diff whitespace | Passed |

The full additive diff retains pre-existing whitespace in pinned fixture/canary
assets, including Catch2 headers. Those authenticated bytes were not rewritten
for formatting. No existing Wootzapp files were removed. The historical classifier
regression uses a small provenance-tracked projection of its original 320 inputs;
model responses and unrelated rollout archives are not imported.

### Selected-task controls

Counts below include each reference and its applicable controls. FAIL is the
expected outcome for negative controls; it is not a validation failure.

| Task | Official assertions | Controls matched | Unexpected INVALID |
|---|---:|---:|---:|
| Bank Account | 25 | 19/19 | 0 |
| Circular Buffer | 60 | 13/13 | 0 |
| Clock | 60 | 17/17 | 0 |
| Complex Numbers | 83 | 22/22 | 0 |
| Crypto Square | 8 | 7/7 | 0 |
| Kindergarten Garden | 24 | 10/10 | 0 |
| Perfect Numbers | 19 | 17/17 | 0 |
| Spiral Matrix | 6 | 7/7 | 0 |
| Sublist | 24 | 17/17 | 0 |
| Yacht | 29 | 16/16 | 0 |
| Columnar Code (held out) | 12 | 2/2 | 0 |
| Cyclic Schedule (held out) | 13 | 2/2 | 0 |
| Factor Balance (held out) | 15 | 2/2 | 0 |
| League Table (held out) | 12 | 2/2 | 0 |

Controls cover forged summaries, equal-count forgery, rounding, completed semantic
failure, candidate compilation failure, infrastructure failure, genuine completion,
and bounded timeout cleanup with descendant-held pipes. Aggregate and process
completion evidence must agree before full reward. Arithmetic, domain and enum
controls retain both genuine positive paths and discriminating negative paths.

## Cohort and dataset

The [cohort guide](../Reward_GRPO/task_repairs/final_cohort.md) records all retention
and exclusion decisions. There are ten training rows, four held-out rows and ten
separately labeled training-monitor rows. The prepared dataset package has 62
files: prompts, starters, test assets and provenance; no reference answers.
Fixed26 task overlap is declared explicitly. Development performance must not be
reported as held-out transfer.

Grade School is held because its duplicate-rejection signaling remains ambiguous.
D&D Character is held because the deterministic gate does not authenticate its
required randomness. Allergies, Queen Attack and Space Age remain unchanged and
are excluded as saturated. Boost-dependent tasks are outside this cohort.

Perfect Numbers retains the existing archived replay evidence:
**historical PASS/PASS/PASS → repaired FAIL/PASS/FAIL; INVALID=0**.
This is a rescore of archived candidates, not new generation or a training result.
The repaired 19-test reference and preserved control identities authenticate.

## Remaining experimental evidence

Before training, publish and verify the final dataset at an immutable HF revision,
then use the [gated launcher](../Reward_GRPO/task_repairs/final_launch.md).
The planned experiment uses the pinned August 29 iteration-14 adapter, twenty
GRPO updates, and matched three-trial evaluations before and after training.
Both evaluations must retain per-task outcomes and INVALID counts. A baseline
INVALID blocks training. A failed or incomplete run must remain reported as such.

No trained checkpoint, new pass@1/pass@3, or measured training gain is claimed here.

# Final C++ GRPO cohort v1

The authoritative selection is `Reward_GRPO/cohorts/cpp-grpo-final-v1.json`.
Its registry, protected fixture files and verifier files are authenticated before
export and at the reward worker boundary. The resulting image ID is recorded in
a separate preflight receipt, avoiding a circular image/cohort digest.

## Selection

| Task | Historical September 11 trials | Decision and basis |
|---|---|---|
| Bank Account | FAIL / PASS / FAIL | Retain after non-positive transaction repair; validate its unchanged concurrency test in Docker. |
| Circular Buffer | PASS / FAIL / FAIL | Retain; semantics unchanged. |
| Clock | FAIL / FAIL / FAIL | Retain after safe signed arithmetic repair; historical failures were candidate API/normalization errors. |
| Complex Numbers | PASS / FAIL / FAIL | Retain after finite-scale numerical repair. |
| Crypto Square | FAIL / FAIL / FAIL | Retain; historical formatting/API/compiler failures are distinct from infrastructure failure; semantics unchanged. |
| Kindergarten Garden | FAIL / FAIL / FAIL | Retain after enum authentication; historical candidate API/plant decoding failures. |
| Perfect Numbers | PASS / PASS / PASS | Retain repaired 19-test fixture; archived replay is FAIL / PASS / FAIL, INVALID=0. |
| Spiral Matrix | PASS / FAIL / FAIL | Retain; semantics unchanged. |
| Sublist | PASS / PASS / FAIL | Retain after enum authentication; no invented score-moving semantics. |
| Yacht | FAIL / FAIL / PASS | Retain; semantics unchanged. |
| Grade School | PASS / PASS / PASS | Hold: duplicate rejection signaling is undefined by the pinned void API. |
| D&D Character | FAIL / FAIL / FAIL | Hold: die range repaired, but deterministic correctness checks do not enforce contractual randomness. |
| Allergies | PASS / PASS / PASS | Exclude from this learning cohort: saturated; no defensible semantic repair identified. |
| Queen Attack | PASS / PASS / PASS | Exclude: saturated; general valid candidates. |
| Space Age | PASS / PASS / PASS | Exclude: saturated; general valid candidates. |

Historical outcomes describe archived outputs against the historical fixture,
not scores measured under these repairs. Perfect Numbers alone has the preserved
post-repair archived replay. New baseline/checkpoint evaluation must use the same
frozen cohort and report development tasks separately from held-out tasks.

The validation cohort contains `columnar-code`, `cyclic-schedule`, `factor-balance`
and `league-table`. These tasks are never exported as training rows. Fixed26
training overlap is explicit; development-task performance is not held-out
benchmark transfer. Gigasecond and Meetup are outside this cohort; their earlier
Boost failures are environment failures, not model-difficulty evidence.

## Correctness contract

- Reuse PR #6 (`6de7340`) execution completion, classification and bounded cleanup.
- Require complete aggregate policy/kernel evidence and successful candidate and
  reference execution before full reward; assertion fractions only shape failure.
- Bank Account rejects zero and negative transactions with `runtime_error` and
  preserves balance. Clock normalizes the signed-int domain using wide arithmetic.
- Complex Numbers uses safe magnitude and scaled division on finite values;
  existing precision tolerances remain unchanged.
- Kindergarten Garden and Sublist require distinct named semantic outcomes,
  without fixing their underlying numeric representation. Sublist's oracle and
  coverage group routing use trusted labels.
- Perfect Numbers assets retain the exact `ba1380e` repair. Historical overflow
  controls retain `9b676606` frozen references; no mutable registry substitution.

No Grade School behavior was invented. D&D's deterministic die-boundary test is
reference validation only and is not misrepresented as a candidate randomness gate.

## Validation and provenance

```bash
uv sync --extra dev
PYTHONPATH=src:. uv run --extra dev pytest
uv run python -m compileall src tests
PYTHONPATH=src:. uv run python -m Reward_GRPO.generalized_cpp_cohort validate
PYTHONPATH=src:. uv run python generalized_verifier_docs/validation/self_check.py
PYTHONPATH=src:. uv run python Reward_GRPO/topic_coverage/self_check.py
PYTHONPATH=src:. uv run python -m Reward_GRPO.generalized_cpp_topic_grpo build-image
PYTHONPATH=src:. uv run python -m Reward_GRPO.generalized_cpp_topic_grpo preflight --output /tmp/cpp-final-preflight
```

Build/publish data only after the full campaign passes. The launch gate binds the
published dataset revision, complete control catalog and exact validated Docker
image. No historical receipt, checkpoint, or result directory is overwritten.

Upstream fixture bytes were imported from the pinned task branch. Inherited
whitespace in those authenticated assets is preserved deliberately; new engineering
changes must pass `git diff --check` against the import commit.

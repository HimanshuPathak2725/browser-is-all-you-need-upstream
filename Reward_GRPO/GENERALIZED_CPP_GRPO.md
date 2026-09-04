# Generalized C++ GRPO vertical integration

`Reward_GRPO/generalized_cpp_grpo.py` is the custom-reward adapter. It resolves
the rollout's `metadata.problem_id` through
`Reward_GRPO/generalized_cpp_grpo_registry.json`, authenticates the base
manifest and protected fixture files, reconstructs an Aider whole-file
response over the registered starter files, runs the aggregate verifier, and
projects its receipt into a Miles `score` / `reward` record.

The model reward is correctness-gated. An overall verifier pass receives
`+1.0`; every model-caused overall failure is constrained to `[-1.0, 0.0]`.
Failure shaping uses only candidate-owned kernels: API shape is 10%, candidate
compile/link is 40%, candidate semantic tests are 45%, and response
integrity/editable-boundary checks are 5% total. The trusted G03 reference
control authenticates the fixture but contributes no model reward.

Verifier kernels remain binary (`-1` or `+1`; genuinely unexecuted kernels are
`null`). On a semantic failure, the adapter validates G03's passed/total
assertion counts and uses the fraction only as continuous failure shaping.
Malformed, non-finite, crashed, build-failed, or reference-invalid facts get no
fractional credit. A recovered markdown filename scores `0.975` only when all
semantic gates pass; forbidden/duplicate listings still reach G05 and cannot
produce positive reward.

The checked-in `portable-arithmetic` entry is an end-to-end canary, not a
training curriculum. Run its import, registry, response, verifier, and reward
preflight with:

```bash
PYTHONPATH=src python3 -m Reward_GRPO.generalized_cpp_grpo preflight
```

Miles discovery variables for the adapter are:

```yaml
MILES_DATA_BUILD_MODULE: Reward_GRPO.generalized_cpp_grpo
MILES_CUSTOM_RM_PATH: Reward_GRPO.generalized_cpp_grpo.reward_func
MILES_REWARD_PREFLIGHT_MODULE: Reward_GRPO.generalized_cpp_grpo
GENERALIZED_CPP_VERIFIER_PROFILE: live
GENERALIZED_CPP_REWARD_WORKERS: "4"
```

`build-data` synthesizes an answer-free Aider shadow task tree from the
registry (starter files, official instructions, and the official test as the
integrity-pinned hidden test) and delegates to the repository's existing Aider
dataset builder, so the registry must contain every `problem_id` selected for
a run. The checked-in `generalized-cpp-v2` curriculum has 15 training tasks:
the six September-1 tasks plus nine additions admitted from four independent
fixed-26 trials of the actual phone-number iter-14 warm start. The admission
criterion is 1--3 pass@1 successes out of four; the recorded counts and eight
source-receipt hashes live in `generalized_cpp_midband_admission.json`; the
bound receipts are stored under the launch-owned
`Reward_GRPO/generalized_cpp_grpo_evidence/` tree and are recomputed during
preflight. They do not depend on the `.skyignore`-excluded `results/` tree.

The nine additions are `allergies`, `bank-account`, `circular-buffer`,
`dnd-character`, `queen-attack`, `space-age`, `spiral-matrix`, `sublist`, and
`yacht`. `robot-name` and `parallel-letter-frequency` meet the numerical band
but remain excluded because their tests are nondeterministic under concurrent
reward-worker load. The `portable-arithmetic` canary opts out of training.
Regenerate the registry and per-task manifests with:

```bash
python3 Reward_GRPO/build_generalized_cpp_grpo_manifests.py
```

These 15 training IDs are exact members of fixed-26. Therefore a later
fixed-26 score is an in-curriculum performance measure for those IDs, not a
clean generalization estimate. Report the disjoint four-task held-out monitor
separately and do not use fixed-26 alone to claim verifier transfer.

The launch configuration is `Reward_GRPO/generalized_cpp_grpo_skypilot.yaml`.
Infrastructure invalids are marked and neutralized within a rollout/problem
group; malformed or forbidden model responses remain model-caused numeric
failures.

Four repository-owned analog tasks are validation-only: `columnar-code`,
`cyclic-schedule`, `factor-balance`, and `league-table`. Their lineages are
disjoint from all training IDs. Preflight requires each reference to pass and
each starter to compile but fail semantics with a nonzero partial fraction.
Miles reads them from `eval/validation.jsonl` every five updates with four
samples per prompt; `eval/train_monitor.jsonl` remains trend-only.

Before a run, preflight also executes six deterministic controls per training
task: alternate-correct, API failure, compile failure, semantic mutation,
recoverable formatting, and editable-boundary failure. The current required
matrix is 15 tasks / 90 controls. Adding a task requires updating the bound
admission record, trusted fixture, oracle manifest, and mutation control; a
task that fails any of those gates is not launchable.

This vertical slice invokes the direct runner in the reward worker. Production
training must switch that invocation to the pinned offline sandbox launcher
before enabling untrusted rollouts outside an already-isolated worker.

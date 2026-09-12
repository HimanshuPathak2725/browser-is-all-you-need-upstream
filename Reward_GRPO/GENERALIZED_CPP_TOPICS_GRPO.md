# Old-task GRPO with topic coverage

`Reward_GRPO.generalized_cpp_topic_grpo.reward_func` combines the existing
G01–G05 live generalized policies with the targeted topic coverage package.
It trains the existing 15 old tasks and reserves the same four analog tasks
for checkpoint monitoring. Charm tasks are excluded.

The eleven covered training tasks are allergies, bank-account, circular-buffer,
clock, complex-numbers, dnd-character, grade-school, space-age, sublist, yacht, and perfect-numbers.
Their 64 behavioral groups, organized into 39 requirement families, become additional
correctness checks and a fixed-denominator partial-credit signal. The optional
concurrency and randomness observations remain diagnostics and do not affect
reward. The exclusions documented in `topic_coverage/README.md` still apply.

A positive reward requires passing both applicable layers. Scoring version
`topic-family-v3` replaces the historical -0.45 failure cap. Each topic group
contributes one all-or-nothing verdict; fractions are averaged within requirement
families, then equally across families. The number of assertions and fail-fast
progress never affect this fraction. Every required group executes independently.

If both layers pass, the generalized score is preserved, including 0.975 for
recoverable filename formatting. Otherwise, after a completed topic audit:

```
score = 0.5 * min(generalized_score, 0) + 0.5 * (topic_fraction - 1)
```

This yields nonpositive rewards for failures while preserving improvement in
either component. For example, a baseline-passing Yacht candidate failing both
four-of-a-kind and yacht scores -1/6; repairing four-of-a-kind raises it to -1/12;
passing every category restores +1. The six face categories collectively have
one family's weight, so their assertion volume cannot dominate multiplicity rules.
The equal blend is a chosen training hyperparameter, not an empirically optimized
weight. New rewards must not be compared numerically to the old training rewards.

Candidate base build failures retain the existing penalty without running topic
probes. An additional topic build failure receives zero topic requirement credit.
Malformed receipts are infrastructure-invalid. The scalar and batch training
entrypoints retry infrastructure failures up to three total attempts, then raise
an explicit error without returning a numeric reward. Candidate semantic failures,
crashes, timeouts and inconsistent outcomes with a healthy reference are failures,
not infrastructure retries. `reward` and `score` remain synchronized.

The combined adapter rejects forbidden/duplicate file listings before compilation,
and truncated parser-rejected answers receive -1. The shared Catch parser now
requires a successful process exit for full credit, rejects ambiguous successful
summaries, and records the process exit. Partial assertion counts retain their
existing shaping role; they are not a fixed denominator across execution paths.

Every untrusted reward runs inside an immutable GCC 13 image (`glm47-generalized-cpp-topics:v3`) as UID 65534, with
no network, host mounts, credentials, or Docker socket. The root filesystem is
read-only, scratch is a bounded temporary filesystem, and CPU, memory, PID,
file-size, and wall-time limits apply. The 2,048 PID limit accommodates the
existing bank-account test's 1,000 threads. The image contains the trusted
verifier/fixture package; the solver prompt contains no reference answers.
Image labels, dataset rows, and the launch snapshot bind the exact code and
asset hashes. The host invokes the image ID rather than a moving tag.

The completed September 9 run used eight topics; its frozen snapshot and receipts
remain the source of truth for those results. The current targeted extension adds
Clock and Yacht and observed-failure controls. The September 10 v2 update splits
requirements, adds buffer template/value coverage and longer sublist cases, and
replaces the cap with the partial-credit formula above. The generalized layer's
own weights and the 15-task training split are retained. No new training is launched
by these code updates.

The v3 update adds construction-state checks, reduces duplicate Bank Account and
Sublist penalties, adds Perfect Numbers coverage and its missing answer-free API
contract, improves runtime diagnostics, and fixes candidate/infra classification.
Pinned benchmark files remain unchanged. These are verifier fixes; improved
Pass@1 still requires a controlled training/evaluation comparison.

The launch configuration starts from August 29 Generalized C++ GRPO iter14 (the evaluated
selected-four 11.75/26 checkpoint), with 20 updates, 8 prompts per
update, 32 samples per prompt, temperature 0.7, 8,192 response tokens, a 12,288
sequence limit, LR 3e-5, and KL coefficient 0.1. This is 160 prompt
presentations / 15 tasks = 10.67 effective dataset passes and 5,120 sampled
training responses, excluding evaluation. Checkpoints and four-sample
held-out evaluation run every five updates. The runtime includes the existing
`sitecustomize.py` GLM bridge bootstrap and checks fresh Python/Ray workers
before training. Compute is one 8-H100 GCP Spot machine with idle teardown.

The v3 full campaign has 190 Docker controls: 20 reference controls (including
the nontraining canary), 90 generalized mutations, 76 topic controls, and four
held-out starter controls. A separate topic campaign includes diagnostics. The
Perfect Numbers positive controls use the overflow-safe implementation; the
pinned overflowing reference is retained as an explicit negative control. The launcher requires a passing
full campaign with the current code hash before allocating compute.

```bash
PYTHONPATH=src python3 -m Reward_GRPO.generalized_cpp_topic_grpo build-image
PYTHONPATH=src python3 -m Reward_GRPO.generalized_cpp_topic_grpo preflight \
  --output results/<new-control-directory>
python3 scripts/launch_generalized_cpp_topics.py \
  --preflight-receipt results/<new-control-directory>/preflight.json --launch
```

The launcher reads only the existing W&B API key through the credential helper,
checks the account/project, and freezes an independent package. It records each
launch under `results/generalized-cpp-topics-20260909/`. Training artifacts and
checkpoints persist to the existing GCS run bucket; this launcher does not publish
to the Charm model repository. A fixed-26 score after this training includes
15 trained tasks; report the four held-out monitor tasks separately.

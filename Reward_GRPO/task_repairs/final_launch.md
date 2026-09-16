# Final C++ GRPO launch

Use the committed final integration branch and its explicitly versioned cohort.
The launch reuses the pinned August 29 iteration-14 warm start, twenty updates,
and existing eight-H100 Spot Miles configuration. It requires the current full
cohort preflight, immutable Hugging Face data revision and exact validated reward
Docker image. A quick reference-only preflight cannot authorize a launch.

## Prerequisites and dry-run

Install the repository's `grpo-launch` Python extra (`uv sync --extra grpo-launch`) and
ensure the Docker daemon and SkyPilot CLI are available. The driver additionally
checks the full project-level SkyPilot permission set before a paid launch.
No command changes global gcloud authentication or configuration.

Set `HF_TOKEN` and `WANDB_API_KEY` through the existing secure environment. Supply
an explicit service-account JSON path; it is never copied into the staged source
or receipts. Use the HF commit returned by publication, not a moving branch name.

```bash
uv run --extra grpo-launch w8-biayn cpp-grpo \
  --preflight-receipt /path/to/full-preflight/preflight.json \
  --dataset-dir /path/to/validated-final-data \
  --dataset-repo ACCOUNT/DATASET --dataset-revision FULL_40_CHARACTER_COMMIT \
  --credentials /secure/path/service-account.json \
  --hf-user HF_ACCOUNT --wandb-user WANDB_ACCOUNT \
  --wandb-entity himanshu2725pathak-wootzapp \
  --out /tmp/cpp-final-dry-run
```

Dry-run writes a rendered YAML, source/evidence snapshot and launch receipt into
the new external output directory. It does not export the Docker image, download
weights, call online identity/IAM gates or launch cloud resources. The receipt
explicitly identifies online identity checks as not performed during dry-run.

After reviewing the dry-run, run the same command with `--launch` and a **new**
external output directory. It checks HF/W&B identities, verifies published file
bytes at the exact revision, checks GCP IAM, exports the exact preflight image by
its immutable ID, then invokes SkyPilot. A dirty worktree or failed/stale/missing
preflight case stops admission before launching.

The staged source is an explicit allowlist of tracked reward/runtime files and
launch dependencies. Every byte is hash-bound in `launch-manifest.json`. The
remote setup verifies the snapshot, loads the saved reward image and checks its
image ID/contract label. Runtime data comes from the pinned HF revision, with
file hashes, task IDs, row counts and task/verifier bindings checked again. The
run does not regenerate its dataset.

The cached GLM model is authenticated against Hugging Face's pinned revision:
LFS SHA-256 for weights and Git blob identities for other payloads. A revision
marker alone is insufficient. Its SHA-256 catalog is retained in the run evidence.
A matched three-trial baseline runs before training, and a matched evaluation of
the final checkpoint runs afterward, with identical tasks, seeds and generation
settings. Both adapter formats used by the project (`.bin` and `.safetensors`) are
supported by the evaluation driver. The existing preparation utility strips only
non-served MTP layers from evaluation copies; original checkpoints remain intact.
Any baseline INVALID blocks training. A final evaluation failure is preserved and
reported as incomplete; it cannot be presented as a successful measured result.

## Status, logs and teardown

The launch receipt records exact cluster-specific commands. Run them with the
same service-account file used to launch; the CLI constructs scoped credentials:

```bash
uv run w8-biayn status --cluster CLUSTER_FROM_RECEIPT --credentials /secure/path/service-account.json
uv run w8-biayn logs CLUSTER_FROM_RECEIPT --credentials /secure/path/service-account.json
uv run w8-biayn down CLUSTER_FROM_RECEIPT --credentials /secure/path/service-account.json
```

The job also requests teardown on completion and a 30-minute idle autostop.
Training/evaluation files are periodically copied to the existing run artifact
mount, including on failure. Receipts and generated staging files remain outside
the Git worktree. Preserve them with the final evidence package.

A launch receipt is authorization/provenance evidence, not evidence that training
or evaluation succeeded. Report actual completion status, checkpoint identities,
measured per-task outcomes and INVALID counts from the resulting run artifacts.

## Artifact durability before teardown

The run mount uses asynchronous write-back. At exit, the launcher stops its
periodic writer, writes local run status, performs one bounded final rsync, then
reads GCS object metadata directly until every regular local file matches server
size and MD5. It hashes local files again before success, records the verified
object generations, copies the receipt to the run prefix and separately
acknowledges that receipt. W&B convenience symlinks are explicitly excluded,
matching the existing `rsync --no-links`; real payload files remain verified.

The metadata barrier has a 600-second deadline and a 660-second outer process
limit; receipt acknowledgement has a 60-second deadline and 90-second outer
limit. Missing/wrong bytes, absent server MD5, authentication failures or timeout
produce an explicit nonzero durability failure. These checks perform no GCS
writes themselves and do not change model/checkpoint formats. Generation/checksum
metadata is also printed to SkyPilot logs if receipt upload cannot finish.

Remote credentials must support Application Default Credentials (the VM service
account, or an explicitly supplied credential file) and `storage.objects.get` on
the existing run bucket. Cached mount access alone does not establish this
permission. No global authentication is changed and credential contents are never
included in receipts. Abrupt VM preemption can still interrupt the final barrier;
periodic artifact copies remain the recovery mechanism for that case.

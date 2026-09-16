# Matched final-cohort evaluation

`scripts/evaluate_cpp_grpo_final.py` evaluates complete C++ source responses with
the final cohort's production Docker reward path. It preserves the dataset's
original chat messages, applies the pinned model's chat template once, and uses
the existing GLM47 bridge and SGLang shared-outer/virtual-expert LoRA settings.
It does not use the PIE optimization evaluator or generate training data.
`enable_thinking=True` is explicit, matching frozen v4/final training. All LoRA
target modules, rank and alpha come from the authenticated adapter configuration;
attention modules are not silently dropped. Decoding explicitly uses the frozen
v4 `stop_token_ids=[154820,154827,154829]` and `skip_special_tokens=True`; both
are recorded in generation identity rather than inherited from defaults.
Unsupported module names or a failed
adapter-load acknowledgement stop evaluation before generation.

## Requirements

Run inside the existing pinned GLM47 GPU runtime, with the repository and its
Python dependencies, SGLang, Transformers, Hugging Face access and the exact
final reward Docker image available. The driver installs nothing. Unsupported
revision, LoRA or per-request sampling-seed settings fail explicitly. Generation
requires a Hugging Face model identity plus immutable commit SHA. Use the HF
cache, or pass `--model-path` and `--model-file-manifest` for an existing mounted
copy. The latter catalog must come from the pinned model source and contain
`model`, `revision`, `source` (immutable source locator),
`authentication: huggingface-pinned-revision`, `hf_revision` and a `files` mapping
of relative paths to SHA-256 hashes. The launcher creates it only after comparing
local payloads with the pinned HF revision's LFS SHA-256 or Git blob SHA-1 metadata. Every local model file must match that catalog;
a revision marker alone is insufficient. Keep the catalog outside the model
directory and preserve its source/download receipt. This avoids downloading the
model a second time while recording the actual loaded weight identities.

The local dataset must have the final export's `manifest.json`, hash catalog,
`grpo/train.jsonl` and `eval/validation.jsonl`. The manifest must match its
published Hugging Face revision. Every prompt row must match the task manifest,
cohort and reward digests. The reward image must authenticate to that digest.
Run the full cohort preflight before either baseline or checkpoint evaluation.

## Matched baseline and trained-checkpoint commands

Set these values from the final dataset publication and checkpoint receipts;
`FINAL_DATASET_SHA` must be an immutable 40-character HF commit SHA. Baseline is
the actual August 29 warm-start PEFT adapter, not an unadapted base model. Both
adapters must contain `adapter_config.json` and exactly one of
`adapter_model.bin` or `adapter_model.safetensors`. Native Miles `.bin` adapters
are loaded directly; no speculative conversion is required.

```bash
PYTHONPATH=src:. python3 -B scripts/evaluate_cpp_grpo_final.py \
  --data-dir "$FINAL_DATASET_DIR" \
  --dataset-repo "$FINAL_DATASET_REPO" --dataset-revision "$FINAL_DATASET_SHA" \
  --model zai-org/GLM-4.7-Flash \
  --model-revision 7dd20894a642a0aa287e9827cb1a1f7f91386b67 \
  --model-path "$PINNED_LOCAL_MODEL" --model-file-manifest "$PINNED_MODEL_FILE_MANIFEST" \
  --adapter "$AUG29_WARMSTART_ADAPTER" --checkpoint-id "$WARMSTART_CHECKPOINT_ID" \
  --label warmstart --output-dir "$EVIDENCE_ROOT/warmstart" \
  --trials 3 --seed 20260916 --temperature 0.7 --max-tokens 8192 \
  --sandbox-image glm47-generalized-cpp-topics:final-v1

PYTHONPATH=src:. python3 -B scripts/evaluate_cpp_grpo_final.py \
  --data-dir "$FINAL_DATASET_DIR" \
  --dataset-repo "$FINAL_DATASET_REPO" --dataset-revision "$FINAL_DATASET_SHA" \
  --model zai-org/GLM-4.7-Flash \
  --model-revision 7dd20894a642a0aa287e9827cb1a1f7f91386b67 \
  --model-path "$PINNED_LOCAL_MODEL" --model-file-manifest "$PINNED_MODEL_FILE_MANIFEST" \
  --adapter "$FINAL_CHECKPOINT_ADAPTER" --checkpoint-id "$FINAL_CHECKPOINT_ID" \
  --label trained --output-dir "$EVIDENCE_ROOT/trained" \
  --trials 3 --seed 20260916 --temperature 0.7 --max-tokens 8192 \
  --sandbox-image glm47-generalized-cpp-topics:final-v1
```

These are new-generation experiments. Compare only results with identical
cohort, dataset, reward, image, model, trial and sampling identities; adapter
hashes distinguish baseline and trained checkpoints. Seeds fix requested sampling
state; they do not promise bitwise identical GPU execution across runtimes.

Scoring uses four independent Docker workers by default (`--score-workers 4`),
bounded between 1 and 24. Each completed result is persisted immediately under
`receipts/`; final `records.jsonl` stays in deterministic task/trial order. A
worker exception becomes INVALID with its diagnostic, never model FAIL.

The four held-out tasks in the frozen manifest are reported separately from
training/development tasks. This is not an official Fixed26 score: the excluded
Boost-dependent tasks are not silently reintroduced. Development scores measure
performance on training task identities and are not held-out generalization.

## Verdicts and accounting

PASS requires a healthy reference and authenticated completion of official tests,
plus a passing topic layer when required. Numeric reward alone cannot establish
PASS. Compile/link/runtime/assertion failures remain candidate FAIL; broken
execution or inconsistent receipts remain INVALID. Malformed source responses
remain candidate formatting/boundary failures.

`summary.json` contains every task's ordered trial outcomes, valid-trial pass@1
numerators/denominators, INVALID counts, per-trial counts and failure categories.
`direct_pass_at_k` is true if any valid trial passes, false if all trials validly
fail, and null if there is no pass and at least one INVALID. Split totals expose
known and unknown task counts. Do not treat the latter as model 0/3. With the
default three trials these are direct pass@3 observations, not an estimator.

Fresh output directories are mandatory. Files are never overwritten:

- `identity.json`: dataset/model/checkpoint/adapter/verifier/image provenance.
- `prompts.jsonl`: exact original chat messages and prompt hashes.
- `generated.jsonl`: every response, rendered-prompt hash, seed, token counts and truncation evidence.
- `records.jsonl`: complete production reward records and per-trial verdicts.
- `receipts/`: individually preserved results, including when scoring is interrupted.
- `summary.json`: completed task-level and split-level results.
- `evidence-sha256.json`: hashes of the evidence files.

Generation/scoring exceptions leave `incomplete.json` and preserve completed
outputs; no complete score is invented. Exit status 2 means completed scoring
contains INVALID trials; candidate failures alone do not make the command fail.

## Replay

Add `--generated /path/to/prior/generated.jsonl` with the same dataset, model and
checkpoint identities, a new label and a fresh output directory. The source
must include its sibling `identity.json`; hashes and the complete task/trial grid
must match. The driver records `archived_output_replay`, source provenance and
source output hash. Replay produces no new model outputs and is never labeled a
new model evaluation. It cannot silently rescore a different prompt/cohort version.

## Tests

```bash
PYTHONPATH=src:. python3 -B -m pytest -q -p no:cacheprovider \
  tests/test_cpp_final_evaluation.py
```

Tests exercise verdict authentication, candidate/infrastructure attribution,
INVALID accounting, incomplete/duplicate-grid rejection, prompt/hash admission,
and generation configuration using a fake engine. They do not claim a GPU
runtime smoke or a measured model outcome.

## Pinned SGLang API check

The archived September v4 package receipt identifies
`sglang==0.0.0.dev14408+g1eda2dabd`. Inspection of
[that exact source revision](https://github.com/sgl-project/sglang/tree/1eda2dabd/python/sglang/srt)
confirms request `sampling_seed`, scalar/list `lora_path`, dynamic
`load_lora_adapter(lora_name, lora_path)` with a success acknowledgement, and
server settings for revision, seed, all six GLM target modules, shared outer
LoRA and virtual experts. Runtime checks still reject incompatible installed
APIs; this source check does not claim a GPU generation smoke.

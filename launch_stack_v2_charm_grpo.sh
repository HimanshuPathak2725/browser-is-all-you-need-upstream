#!/usr/bin/env bash
# Default is packaging/check only. Training requires the explicit --launch flag.
set +x  # Never expand secrets into shell traces, including bash -x invocations.
set -euo pipefail
REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "${REPO_ROOT}"
MODE="${1:---check}"
case "${MODE}" in --preflight|--check|--launch) ;; *) echo "Usage: $0 [--preflight|--check|--launch]" >&2; exit 2;; esac
# Approved identities/destinations; only non-secret selectors are stored here.
export MILES_HF_MODEL_REPO="${MILES_HF_MODEL_REPO:-HimanshuPathak/Stackv2grpo}"
export MILES_HF_EXPECTED_USER="${MILES_HF_EXPECTED_USER:-HimanshuPathak}"
export MILES_WANDB_EXPECTED_USER="${MILES_WANDB_EXPECTED_USER:-himanshu2725pathak}"
export WANDB_ENTITY="${WANDB_ENTITY:-himanshu2725pathak-wootzapp}"
if [[ -z "${HF_TOKEN:-}${HUGGING_FACE_HUB_TOKEN:-}${HF_TOKEN_PATH:-}${HF_HOME:-}" ]]; then
  export HF_HOME="${XDG_CACHE_HOME:-${HOME}/.cache}/huggingface"
fi
# Supply WANDB_API_KEY or an explicit MILES_WANDB_ENV_FILE. The helper reads only
# the literal WANDB_API_KEY assignment; it never sources the file or reads netrc.
python3 scripts/charm_grpo_hub.py preflight
if [[ "${MODE}" == "--preflight" ]]; then exit 0; fi
STAMP="$(date -u +%Y%m%d-%H%M%S)"
export MILES_RUN_ID="${MILES_RUN_ID:-stack-v2-charm-12x30-grpo45-${STAMP}}"
[[ "${MILES_RUN_ID}" =~ ^[a-zA-Z0-9][a-zA-Z0-9._-]{0,100}$ ]] || { echo "Invalid run ID" >&2; exit 2; }
CLUSTER_NAME="stack-v2-charm-${STAMP}"

export GLM47_SOURCE_COMMIT="$(git rev-parse HEAD)"
SNAPSHOT="${REPO_ROOT}/.glm47-posttraining/stack-v2-charm/launches/${MILES_RUN_ID}"
PYTHONPATH="${REPO_ROOT}/src:${REPO_ROOT}" python3 -m glm47_posttraining.integrations.stack_v2_charm_run \
  stage-launch --out "${SNAPSHOT}" --run-id "${MILES_RUN_ID}"
echo "Frozen workdir: ${SNAPSHOT}"
echo "Run ID: ${MILES_RUN_ID}"
if [[ "${MODE}" == "--check" ]]; then
  echo "CHECK ONLY: no training or cloud job was started."
  exit 0
fi
python3 scripts/charm_grpo_hub.py exec-launch -- sky launch -y --retry-until-up --detach-run \
  -c "${CLUSTER_NAME}" \
  --workdir "${SNAPSHOT}" \
  "${SNAPSHOT}/Reward_GRPO/stack_v2_charm_grpo_skypilot.yaml" \
  --env "MILES_RUN_ID=${MILES_RUN_ID}" \
  --env "GLM47_SOURCE_COMMIT=${GLM47_SOURCE_COMMIT}" \
  --env "WANDB_ENTITY=${WANDB_ENTITY}" \
  --env "MILES_WANDB_EXPECTED_USER=${MILES_WANDB_EXPECTED_USER}" \
  --env "MILES_HF_MODEL_REPO=${MILES_HF_MODEL_REPO}" \
  --env "MILES_HF_EXPECTED_USER=${MILES_HF_EXPECTED_USER}" \
  --env "MILES_WANDB_PROJECT=glm47-stack-v2-charm-grpo" \
  --secret WANDB_API_KEY \
  --secret HF_TOKEN

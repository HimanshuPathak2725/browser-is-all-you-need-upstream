#!/usr/bin/env bash
# Generalized C++ GRPO training launch.
# Credentials may be placed in the git-ignored .env file or entered when asked.
set -euo pipefail

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SKY_CONFIG=Reward_GRPO/generalized_cpp_grpo_skypilot.yaml
cd "${REPO_ROOT}"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

if [[ -z "${WANDB_API_KEY:-}" ]]; then
  read -rs -p "Paste your W&B API key: " WANDB_API_KEY
  echo
fi

[[ ${#WANDB_API_KEY} -ge 20 ]] || {
  echo "ERROR: WANDB_API_KEY is missing or unexpectedly short"
  exit 1
}

if [[ -z "${WANDB_ENTITY:-}" ]]; then
  read -r -p "Your W&B entity/account name: " WANDB_ENTITY
fi

[[ -n "${WANDB_ENTITY}" ]] || {
  echo "ERROR: WANDB_ENTITY is required so the run cannot use another account"
  exit 1
}

MILES_WANDB_PROJECT="${MILES_WANDB_PROJECT:-glm47-generalized-cpp-v2-grpo}"

if ! rg -q '^  use_spot: true$' "${SKY_CONFIG}"; then
  echo "ERROR: ${SKY_CONFIG} is not configured for Spot capacity"
  exit 1
fi

STAMP="$(date -u +%Y%m%d-%H%M%S)"
RUN_ID="generalized-cpp-v2-kernel-grpo20-spot-${STAMP}"
CLUSTER_NAME="generalized-cpp-v2-grpo20-spot-${STAMP}"
SOURCE_COMMIT="$(git rev-parse HEAD)"

echo "Run ID:      ${RUN_ID}"
echo "Cluster:     ${CLUSTER_NAME}"
echo "Commit:      ${SOURCE_COMMIT}"
echo "W&B entity:  ${WANDB_ENTITY}"
echo "W&B project: ${MILES_WANDB_PROJECT}"
echo "Capacity:    Spot (enforced by ${SKY_CONFIG})"

sky launch -y --retry-until-up \
  -c "${CLUSTER_NAME}" \
  "${SKY_CONFIG}" \
  --env "MILES_RUN_ID=${RUN_ID}" \
  --env "GLM47_SOURCE_COMMIT=${SOURCE_COMMIT}" \
  --env "WANDB_ENTITY=${WANDB_ENTITY}" \
  --env "MILES_WANDB_PROJECT=${MILES_WANDB_PROJECT}" \
  --secret "WANDB_API_KEY=${WANDB_API_KEY}"

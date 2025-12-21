#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${SCRIPT_DIR}/.."
DEVCONTAINER_CONFIG="${REPO_ROOT}/.devcontainer/devcontainer.json"
ARTIFACT_DIR="${REPO_ROOT}/artifacts"
INSIDE_FLAG="${1-}"

run_inside_container() {
  cd "${REPO_ROOT}"
  mkdir -p "${ARTIFACT_DIR}"

  local build_log="${ARTIFACT_DIR}/simtest-build.log"
  local run_log="${ARTIFACT_DIR}/simtest-run.log"
  local report_file="${ARTIFACT_DIR}/simtest-report.txt"

  : >"${build_log}"
  : >"${run_log}"
  : >"${report_file}"

  local build_start
  local build_end
  local run_start
  local run_end

  build_start=$(date +%s)
  ./tools/simtest build 2>&1 | tee "${build_log}"
  build_end=$(date +%s)

  run_start=$(date +%s)
  SIM_DURATION="${SIM_DURATION:-20}" ./tools/simtest run 2>&1 | tee "${run_log}"
  run_end=$(date +%s)

  {
    printf 'build_seconds=%s\n' "$((build_end - build_start))"
    printf 'run_seconds=%s\n' "$((run_end - run_start))"
  } | tee "${report_file}"
}

if [[ "${INSIDE_FLAG}" != "--inside-devcontainer" ]]; then
  if ! command -v devcontainer >/dev/null 2>&1; then
    echo "error: devcontainer CLI not found. Install from https://aka.ms/devcontainer-cli" >&2
    exit 1
  fi

  devcontainer up \
    --workspace-folder "${REPO_ROOT}" \
    --config "${DEVCONTAINER_CONFIG}" >/dev/null

  devcontainer exec \
    --workspace-folder "${REPO_ROOT}" \
    --config "${DEVCONTAINER_CONFIG}" \
    -- /bin/bash -lc "./tools/run_ci.sh --inside-devcontainer"
else
  run_inside_container
fi

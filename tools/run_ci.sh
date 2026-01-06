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
  local qgc_build_log="${ARTIFACT_DIR}/qgc-build.log"
  local qgc_test_log="${ARTIFACT_DIR}/qgc-test.log"
  local qgc_stub_log="${ARTIFACT_DIR}/qgc-stub.log"

  : >"${build_log}"
  : >"${run_log}"
  : >"${report_file}"
  : >"${qgc_build_log}"
  : >"${qgc_test_log}"
  : >"${qgc_stub_log}"

  local build_start
  local build_end
  local run_start
  local run_end

  build_start=$(date +%s)
  ./tools/simtest build 2>&1 | tee "${build_log}"
  build_end=$(date +%s)

  run_start=$(date +%s)
  SIM_DURATION="${SIM_DURATION:-45}" ./tools/simtest run 2>&1 | tee "${run_log}"
  run_end=$(date +%s)

  {
    printf 'build_seconds=%s\n' "$((build_end - build_start))"
    printf 'run_seconds=%s\n' "$((run_end - run_start))"
  } | tee -a "${report_file}"

  if [[ "${SIMTEST_ENABLE_QGC:-0}" == "1" ]]; then
    local qgc_build_start
    local qgc_build_end
    local qgc_test_start
    local qgc_test_end
    local qgc_stub_start
    local qgc_stub_end

    qgc_build_start=$(date +%s)
    ./tools/simtest qgc build 2>&1 | tee "${qgc_build_log}"
    qgc_build_end=$(date +%s)

    qgc_test_start=$(date +%s)
    ./tools/simtest qgc test 2>&1 | tee "${qgc_test_log}"
    qgc_test_end=$(date +%s)

    export SIMTEST_QGC_SKIP_PARAM_CHECK="${SIMTEST_QGC_SKIP_PARAM_CHECK:-1}"
    export SIMTEST_QGC_SKIP_HEARTBEAT_CHECK="${SIMTEST_QGC_SKIP_HEARTBEAT_CHECK:-1}"

    qgc_stub_start=$(date +%s)
    ./tools/simtest qgc stub 2>&1 | tee "${qgc_stub_log}"
    qgc_stub_end=$(date +%s)

    ./tools/simtest qgc collect >>"${qgc_stub_log}" 2>&1 || true

    {
      printf 'qgc_build_seconds=%s\n' "$((qgc_build_end - qgc_build_start))"
      printf 'qgc_test_seconds=%s\n' "$((qgc_test_end - qgc_test_start))"
      printf 'qgc_stub_seconds=%s\n' "$((qgc_stub_end - qgc_stub_start))"
    } | tee -a "${report_file}"
  fi
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

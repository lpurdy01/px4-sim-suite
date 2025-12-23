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
  local doctor_log="${ARTIFACT_DIR}/simtest-doctor.log"

  : >"${build_log}"
  : >"${run_log}"
  : >"${report_file}"
  : >"${doctor_log}"

  ./tools/simtest doctor 2>&1 | tee "${doctor_log}"

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

  local canonical_log="${ARTIFACT_DIR}/latest_sitl.ulg"
  local fallback_log
  fallback_log=$(ls -1t "${ARTIFACT_DIR}"/*.ulg 2>/dev/null | head -n1 || true)
  local summary_json="${ARTIFACT_DIR}/takeoff_land_summary.json"
  local report_html="${ARTIFACT_DIR}/flight_report.html"

  if [[ ! -f "${canonical_log}" && -n "${fallback_log}" && -f "${fallback_log}" ]]; then
    cp "${fallback_log}" "${canonical_log}" 2>/dev/null || true
  fi

  if [[ -f "${canonical_log}" && -f "${summary_json}" ]]; then
    python3 "${REPO_ROOT}/tools/generate_flight_report.py" "${canonical_log}" \
      --summary "${summary_json}" \
      --output "${report_html}"
  else
    echo "warning: skipping flight report generation (missing log or summary)" | tee -a "${report_file}"
  fi

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

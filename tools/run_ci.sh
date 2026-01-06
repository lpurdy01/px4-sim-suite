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
  local qgc_stage5_log="${ARTIFACT_DIR}/qgc-stage5.log"

  : >"${build_log}"
  : >"${run_log}"
  : >"${report_file}"
  : >"${qgc_build_log}"
  : >"${qgc_test_log}"
  : >"${qgc_stub_log}"
  : >"${qgc_stage5_log}"

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

  local latest_ulog
  latest_ulog=$(python3 - "${ARTIFACT_DIR}" <<'PY'
from pathlib import Path
import sys
artifact_dir = Path(sys.argv[1])
logs = sorted(artifact_dir.glob("*.ulg"), key=lambda path: path.stat().st_mtime_ns, reverse=True)
if logs:
    print(logs[0])
PY
  ) || latest_ulog=""
  if [[ -n "${latest_ulog}" ]]; then
    local scenario_name
    scenario_name="${SIMTEST_SCENARIO:-takeoff_land}"
    local summary_path
    summary_path="${ARTIFACT_DIR}/${scenario_name}_summary.json"
    local report_html
    report_html="${ARTIFACT_DIR}/flight_report.html"
    if python3 "${REPO_ROOT}/tools/generate_flight_report.py" "${latest_ulog}" --output "${report_html}" --summary "${summary_path}"; then
      printf 'flight_report=%s\n' "${report_html}" | tee -a "${report_file}"
    else
      echo "warning: failed to generate flight report" | tee -a "${report_file}"
    fi
  else
    echo "warning: no ULog found; skipping flight report" | tee -a "${report_file}"
  fi

  if [[ "${SIMTEST_ENABLE_QGC:-0}" == "1" ]]; then
    local qgc_build_start
    local qgc_build_end
    local qgc_test_start
    local qgc_test_end
    local qgc_stub_start
    local qgc_stub_end
    local qgc_stage5_start
    local qgc_stage5_end

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

    local qgc_executable
    local qgc_default_binary="${REPO_ROOT}/build/qgc-simtest/AppDir/usr/bin/QGroundControl"
    local qgc_appimage_path="${ARTIFACT_DIR}/qgc/QGroundControl-x86_64.AppImage"
    if [[ -x "${qgc_appimage_path}" ]]; then
      qgc_executable="${qgc_appimage_path}"
    elif [[ -x "${qgc_default_binary}" ]]; then
      qgc_executable="${qgc_default_binary}"
    else
      echo "error: QGroundControl executable not found for stage 5 run" | tee -a "${qgc_stage5_log}"
      exit 1
    fi

    qgc_stage5_start=$(date +%s)
    QGC_APPIMAGE_PATH="${qgc_executable}" ./tools/run_stage5_qgc_with_px4.sh 2>&1 | tee "${qgc_stage5_log}"
    qgc_stage5_end=$(date +%s)

    local qgc_artifact_dir="${ARTIFACT_DIR}/qgc"
    mkdir -p "${qgc_artifact_dir}"
    local stage5_ulog
    stage5_ulog=$(python3 - "${REPO_ROOT}" <<'PY'
from pathlib import Path
import sys

repo_root = Path(sys.argv[1])
px4_root = repo_root / "px4"

candidates: list[Path] = []
for base in (
    px4_root / "build" / "px4_sitl_default" / "rootfs" / "log",
    px4_root / "log",
):
    if not base.exists():
        continue
    for directory in base.iterdir():
        if not directory.is_dir():
            continue
        candidates.extend(directory.glob("*.ulg"))

candidates.sort(key=lambda path: path.stat().st_mtime_ns, reverse=True)
if candidates:
    print(candidates[0])
PY
    ) || stage5_ulog=""

    if [[ -n "${stage5_ulog}" && -f "${stage5_ulog}" ]]; then
      local qgc_log_copy
      qgc_log_copy="${qgc_artifact_dir}/$(basename "${stage5_ulog}")"
      if cp "${stage5_ulog}" "${qgc_log_copy}" 2>/dev/null; then
        local qgc_report_html
        qgc_report_html="${qgc_artifact_dir}/qgc-flight_report.html"
        local qgc_summary_json
        qgc_summary_json="${qgc_artifact_dir}/qgc-mission-summary.json"
        if python3 "${REPO_ROOT}/tools/generate_flight_report.py" "${qgc_log_copy}" --output "${qgc_report_html}" --summary "${qgc_summary_json}"; then
          printf 'qgc_flight_report=%s\n' "${qgc_report_html}" | tee -a "${report_file}"
        else
          echo "warning: failed to generate QGC flight report" | tee -a "${report_file}"
        fi
      else
        echo "warning: unable to copy QGC flight log from ${stage5_ulog}" | tee -a "${report_file}"
      fi
    else
      echo "warning: no QGC flight log found after stage 5 run" | tee -a "${report_file}"
    fi

    ./tools/simtest qgc collect >>"${qgc_stage5_log}" 2>&1 || true

    {
      printf 'qgc_build_seconds=%s\n' "$((qgc_build_end - qgc_build_start))"
      printf 'qgc_test_seconds=%s\n' "$((qgc_test_end - qgc_test_start))"
      printf 'qgc_stub_seconds=%s\n' "$((qgc_stub_end - qgc_stub_start))"
      printf 'qgc_stage5_seconds=%s\n' "$((qgc_stage5_end - qgc_stage5_start))"
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

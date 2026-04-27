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
  local vision_log="${ARTIFACT_DIR}/vision-pipeline.log"
  local vision_enabled="${SIMTEST_ENABLE_VISION:-0}"

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

  if [[ "${vision_enabled}" == "1" ]]; then
    local vision_start
    local vision_end
    local vision_scenario="${SIMTEST_VISION_SCENARIO:-vision_lock_static}"
    local vision_check_mode="${SIMTEST_VISION_CHECK_MODE:-full-pipeline}"
    local vision_checker_status="UNKNOWN"
    local vision_lock_acquisition_s="n/a"
    local vision_lock_hold_ratio="n/a"
    local vision_max_dropout_gap_s="n/a"
    local vision_latency_min="n/a"
    local vision_latency_p50="n/a"
    local vision_latency_p95="n/a"
    local vision_latency_max="n/a"
    local required_vision_files=(
      "${ARTIFACT_DIR}/vision-pipeline.log"
      "${ARTIFACT_DIR}/check_vision_lock_metrics.log"
      "${ARTIFACT_DIR}/intercept_tracker_tracks.jsonl"
      "${ARTIFACT_DIR}/guidance_advisory.jsonl"
    )

    : >"${vision_log}"
    {
      echo "[vision-pipeline] context_begin"
      printf '[vision-pipeline] utc_start=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
      printf '[vision-pipeline] git_sha=%s\n' "$(git -C "${REPO_ROOT}" rev-parse --short HEAD 2>/dev/null || echo unknown)"
      printf '[vision-pipeline] scenario=%s\n' "${vision_scenario}"
      printf '[vision-pipeline] check_mode=%s\n' "${vision_check_mode}"
      printf '[vision-pipeline] artifact_dir=%s\n' "${ARTIFACT_DIR}"
      echo "[vision-pipeline] context_end"
    } | tee -a "${vision_log}"
    vision_start=$(date +%s)
    SIMTEST_VISION_SCENARIO="${vision_scenario}" \
    SIMTEST_VISION_CHECK_MODE="${vision_check_mode}" \
    ./tools/simtest vision 2>&1 | tee -a "${vision_log}"
    vision_end=$(date +%s)
    local vision_seconds="$((vision_end - vision_start))"
    {
      printf 'vision_enabled=1\n'
      printf 'vision_seconds=%s\n' "${vision_seconds}"
    } | tee -a "${report_file}"

    local missing_required=()
    local required_file
    for required_file in "${required_vision_files[@]}"; do
      if [[ ! -s "${required_file}" ]]; then
        missing_required+=("${required_file}")
      fi
    done
    if (( ${#missing_required[@]} > 0 )); then
      {
        echo "error: vision feedback artifact guard failed; missing or empty required files:"
        for required_file in "${missing_required[@]}"; do
          echo "error: missing required vision artifact: ${required_file}"
        done
      } | tee -a "${report_file}" >&2
      exit 1
    fi

    if [[ -f "${ARTIFACT_DIR}/check_vision_lock_metrics.log" ]]; then
      if grep -Eq '^\[vision-lock-check\] PASS$' "${ARTIFACT_DIR}/check_vision_lock_metrics.log"; then
        vision_checker_status="PASS"
      elif grep -Eq '^\[vision-lock-check\] FAIL$' "${ARTIFACT_DIR}/check_vision_lock_metrics.log"; then
        vision_checker_status="FAIL"
      fi
    fi

    local parsed_checker_metrics
    parsed_checker_metrics="$(python3 - "${ARTIFACT_DIR}/check_vision_lock_metrics.log" <<'PY'
from pathlib import Path
import re
import sys

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""

def pick(pattern: str, default: str = "n/a") -> str:
    match = re.search(pattern, text, re.MULTILINE)
    return match.group(1).strip() if match else default

print(pick(r"^\s*lock_acquisition_s:\s*(.+)$"))
print(pick(r"^\s*lock_hold_ratio:\s*(.+)$"))
print(pick(r"^\s*max_dropout_gap_s:\s*(.+)$"))
PY
)"
    mapfile -t checker_metrics_lines <<<"${parsed_checker_metrics}"
    if (( ${#checker_metrics_lines[@]} >= 3 )); then
      vision_lock_acquisition_s="${checker_metrics_lines[0]}"
      vision_lock_hold_ratio="${checker_metrics_lines[1]}"
      vision_max_dropout_gap_s="${checker_metrics_lines[2]}"
    fi

    local parsed_latency_summary
    parsed_latency_summary="$(python3 - "${ARTIFACT_DIR}/guidance_advisory.jsonl" <<'PY'
from pathlib import Path
import json
import math
import sys

path = Path(sys.argv[1])
latencies: list[float] = []
if path.exists():
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        row = raw.strip()
        if not row:
            continue
        try:
            payload = json.loads(row)
        except json.JSONDecodeError:
            continue
        value = payload.get("latency_s")
        if isinstance(value, (int, float)) and math.isfinite(float(value)):
            latencies.append(float(value))

if not latencies:
    print("n/a")
    print("n/a")
    print("n/a")
    print("n/a")
    raise SystemExit(0)

latencies.sort()

def percentile(p: float) -> float:
    if len(latencies) == 1:
        return latencies[0]
    rank = (len(latencies) - 1) * p
    low = math.floor(rank)
    high = math.ceil(rank)
    if low == high:
        return latencies[low]
    weight = rank - low
    return latencies[low] * (1.0 - weight) + latencies[high] * weight

print(f"{latencies[0]:.6f}")
print(f"{percentile(0.50):.6f}")
print(f"{percentile(0.95):.6f}")
print(f"{latencies[-1]:.6f}")
PY
)"
    mapfile -t latency_summary_lines <<<"${parsed_latency_summary}"
    if (( ${#latency_summary_lines[@]} >= 4 )); then
      vision_latency_min="${latency_summary_lines[0]}"
      vision_latency_p50="${latency_summary_lines[1]}"
      vision_latency_p95="${latency_summary_lines[2]}"
      vision_latency_max="${latency_summary_lines[3]}"
    fi

    {
      echo "vision_checker_key_lines_begin"
      if [[ -s "${ARTIFACT_DIR}/check_vision_lock_metrics.log" ]]; then
        grep -E "^\[vision-lock-check\]|^  lock_|^  - " "${ARTIFACT_DIR}/check_vision_lock_metrics.log" || true
      else
        echo "[vision-lock-check] missing checker log: ${ARTIFACT_DIR}/check_vision_lock_metrics.log"
      fi
      echo "vision_checker_key_lines_end"
      echo "vision_feedback_summary_begin"
      echo "vision_enabled=1"
      echo "vision_checker=${vision_checker_status}"
      echo "lock_acquisition_s=${vision_lock_acquisition_s}"
      echo "lock_hold_ratio=${vision_lock_hold_ratio}"
      echo "max_dropout_gap_s=${vision_max_dropout_gap_s}"
      echo "advisory_latency_s_min=${vision_latency_min}"
      echo "advisory_latency_s_p50=${vision_latency_p50}"
      echo "advisory_latency_s_p95=${vision_latency_p95}"
      echo "advisory_latency_s_max=${vision_latency_max}"
      echo "vision_feedback_summary_end"
    } | tee -a "${report_file}"
    {
      echo "[vision-pipeline] summary_begin"
      echo "[vision-pipeline] checker=${vision_checker_status}"
      echo "[vision-pipeline] lock_acquisition_s=${vision_lock_acquisition_s}"
      echo "[vision-pipeline] lock_hold_ratio=${vision_lock_hold_ratio}"
      echo "[vision-pipeline] max_dropout_gap_s=${vision_max_dropout_gap_s}"
      echo "[vision-pipeline] advisory_latency_s_min=${vision_latency_min}"
      echo "[vision-pipeline] advisory_latency_s_p50=${vision_latency_p50}"
      echo "[vision-pipeline] advisory_latency_s_p95=${vision_latency_p95}"
      echo "[vision-pipeline] advisory_latency_s_max=${vision_latency_max}"
      echo "[vision-pipeline] summary_end"
    } | tee -a "${vision_log}"
  else
    {
      printf 'vision_enabled=0\n'
      printf 'vision_skipped_reason=SIMTEST_ENABLE_VISION_not_set_to_1\n'
    } | tee -a "${report_file}"
  fi

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

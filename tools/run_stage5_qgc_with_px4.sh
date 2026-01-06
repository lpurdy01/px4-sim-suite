#!/usr/bin/env bash
set -euo pipefail

# Stage 5 helper: launch PX4 SITL (Gazebo) and drive a QGroundControl mission headlessly.

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${SCRIPT_DIR}/.."
PX4_ROOT="${REPO_ROOT}/px4"
LOG_DIR="${REPO_ROOT}/artifacts/qgc"
DEFAULT_APPIMAGE="${REPO_ROOT}/artifacts/qgc/QGroundControl-x86_64.AppImage"
QGC_APPIMAGE_PATH="${QGC_APPIMAGE_PATH:-${DEFAULT_APPIMAGE}}"
PX4_SIM_MODEL="${PX4_SIM_MODEL:-x500}"
SITL_READY_TIMEOUT="${SITL_READY_TIMEOUT:-120}"
MISSION_TIMEOUT="${MISSION_TIMEOUT:-180}"
LANDING_TIMEOUT="${LANDING_TIMEOUT:-90}"
QGC_RUN_DURATION="${QGC_RUN_DURATION:-240}"
QGC_PLAN_PATH="${QGC_PLAN_PATH:-${REPO_ROOT}/tests/qgc_plans/takeoff_land.plan}"
QT_LOGGING_RULES_DEFAULT="HeadlessMissionRunnerLog.info=true;HeadlessMissionRunnerLog.warning=true"
QT_LOGGING_RULES="${QT_LOGGING_RULES:-${QT_LOGGING_RULES_DEFAULT}}"
MISSION_SUMMARY="${LOG_DIR}/qgc-mission-summary.json"
export MISSION_SUMMARY

SITL_LOG="${LOG_DIR}/px4-sitl-console.log"
QGC_LOG="${LOG_DIR}/qgc-sitl-session.log"
MISSION_MARKER="Mission finished"
LANDING_PATTERN="Landing detected|Mission finished, landed"
UPLOAD_MARKER="Mission upload complete"

if [ ! -x "${PX4_ROOT}/build/px4_sitl_default/bin/px4" ]; then
  printf 'PX4 SITL binary not found at %s\n' "${PX4_ROOT}/build/px4_sitl_default/bin/px4" >&2
  exit 1
fi

if [ ! -f "${QGC_APPIMAGE_PATH}" ]; then
  printf 'QGroundControl AppImage not found at %s\n' "${QGC_APPIMAGE_PATH}" >&2
  exit 1
fi

if ! command -v xvfb-run >/dev/null 2>&1; then
  printf 'xvfb-run is required to run QGroundControl headlessly.\n' >&2
  exit 1
fi

if [ ! -f "${QGC_PLAN_PATH}" ]; then
  printf 'Mission plan not found at %s\n' "${QGC_PLAN_PATH}" >&2
  exit 1
fi

plan_abs=$(python3 -c 'import os,sys; print(os.path.abspath(sys.argv[1]))' "${QGC_PLAN_PATH}")
export plan_abs

mission_upload_success=false
mission_complete_success=false
landing_detected=false
vehicle_armed=false
vehicle_disarmed=false
export mission_upload_success mission_complete_success landing_detected

mkdir -p "${LOG_DIR}"
: >"${SITL_LOG}"
: >"${QGC_LOG}"
rm -f "${MISSION_SUMMARY}"

cleanup() {
  if [[ -n "${SITL_PID:-}" ]] && kill -0 "${SITL_PID}" 2>/dev/null; then
    kill "${SITL_PID}" 2>/dev/null || true
    wait "${SITL_PID}" 2>/dev/null || true
  fi
  pkill -f "px4_sitl_default/bin/px4" 2>/dev/null || true
  pkill -f "gz sim" 2>/dev/null || true
}
trap cleanup EXIT

wait_for_marker() {
  local file=$1
  local marker=$2
  local timeout_secs=$3
  local label=$4

  if ! timeout "${timeout_secs}" bash -c "while ! grep -Eq '${marker}' '${file}'; do sleep 2; done"; then
    printf '[stage5] %s not observed within %ss\n' "${label}" "${timeout_secs}" >&2
    return 1
  fi

  printf '[stage5] Observed %s\n' "${label}"
  return 0
}

printf '[stage5] Starting PX4 SITL (model: %s)\n' "${PX4_SIM_MODEL}"
(
  cd "${PX4_ROOT}"
  stdbuf -oL env HEADLESS=1 PX4_SIM_MODEL="${PX4_SIM_MODEL}" make px4_sitl "gz_${PX4_SIM_MODEL}"
) >"${SITL_LOG}" 2>&1 &
SITL_PID=$!

if ! timeout "${SITL_READY_TIMEOUT}" bash -c "while ! grep -Fq 'Ready for takeoff' '${SITL_LOG}'; do sleep 1; done"; then
  printf 'Timed out waiting for PX4 SITL readiness. See %s\n' "${SITL_LOG}" >&2
  exit 1
fi

printf '[stage5] PX4 SITL reported ready. Launching QGroundControl...\n'

set +e
(
  export APPIMAGE_EXTRACT_AND_RUN=1
  export QT_LOGGING_RULES
  timeout --signal=SIGTERM "${QGC_RUN_DURATION}" \
    xvfb-run -a "${QGC_APPIMAGE_PATH}" --logging --logoutput --auto-fly-plan "${plan_abs}"
) >>"${QGC_LOG}" 2>&1 &
QGC_WRAPPER_PID=$!
set -e

if ! wait_for_marker "${QGC_LOG}" "${UPLOAD_MARKER}" "${MISSION_TIMEOUT}" "mission upload"; then
  kill "${QGC_WRAPPER_PID}" 2>/dev/null || true
  wait "${QGC_WRAPPER_PID}" 2>/dev/null || true
  exit 1
fi
mission_upload_success=true

if ! wait_for_marker "${SITL_LOG}" "${MISSION_MARKER}" "${MISSION_TIMEOUT}" "mission completion"; then
  kill "${QGC_WRAPPER_PID}" 2>/dev/null || true
  wait "${QGC_WRAPPER_PID}" 2>/dev/null || true
  exit 1
fi
mission_complete_success=true

if wait_for_marker "${SITL_LOG}" "${LANDING_PATTERN}" "${LANDING_TIMEOUT}" "landing detection"; then
  landing_detected=true
  if grep -Fq "Landing detected" "${SITL_LOG}"; then
    printf '[stage5] Landing detected via commander event.\n'
  elif grep -Fq "Mission finished, landed" "${SITL_LOG}"; then
    printf '[stage5] Landing inferred from mission completion.\n'
  fi
else
  printf '[stage5] Landing confirmation not observed; continuing with caution.\n'
  landing_detected=false
fi

set +e
if kill "${QGC_WRAPPER_PID}" 2>/dev/null; then
  wait "${QGC_WRAPPER_PID}" 2>/dev/null || true
else
  wait "${QGC_WRAPPER_PID}" 2>/dev/null || true
fi
QGC_STATUS=$?
export QGC_STATUS
set -e

if [ ${QGC_STATUS} -ne 0 ] && [ ${QGC_STATUS} -ne 124 ] && [ ${QGC_STATUS} -ne 143 ]; then
  printf 'QGroundControl exited with status %s. See %s\n' "${QGC_STATUS}" "${QGC_LOG}" >&2
  exit ${QGC_STATUS}
fi

printf '[stage5] Mission run complete (QGC status: %s)\n' "${QGC_STATUS}"
vehicle_armed=$(grep -Fq "Vehicle armed state true" "${QGC_LOG}" && echo true || echo false)
vehicle_disarmed=$(grep -Fq "Vehicle armed state false" "${QGC_LOG}" && echo true || echo false)
export vehicle_armed vehicle_disarmed
export mission_upload_success mission_complete_success landing_detected

python3 - <<'PY'
import json
import os

summary_path = os.environ["MISSION_SUMMARY"]

data = {
  "mission_plan": os.environ["plan_abs"],
  "mission_upload": os.environ.get("mission_upload_success", "false") == "true",
  "mission_completed": os.environ.get("mission_complete_success", "false") == "true",
  "landing_detected": os.environ.get("landing_detected", "false") == "true",
  "vehicle_armed": os.environ.get("vehicle_armed", "false") == "true",
  "vehicle_disarmed": os.environ.get("vehicle_disarmed", "false") == "true",
  "qgc_status": int(os.environ["QGC_STATUS"]),
}

with open(summary_path, "w", encoding="utf-8") as handle:
  json.dump(data, handle, indent=2)

PY

trap - EXIT
cleanup
printf '[stage5] Artifacts available:\n  PX4 log: %s\n  QGC log: %s\n  Mission summary: %s\n' "${SITL_LOG}" "${QGC_LOG}" "${MISSION_SUMMARY}"

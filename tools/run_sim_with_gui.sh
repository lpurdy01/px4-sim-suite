#!/usr/bin/env bash
# Launch PX4 Gazebo simulation with visible GUI
# Usage: ./tools/run_sim_with_gui.sh [model] [duration]

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${SCRIPT_DIR}/.."
PX4_DIR="${REPO_ROOT}/px4"

# Configuration
SIM_MODEL="${1:-x500}"  # Default to x500 quadrotor (same as pipeline)
SIM_DURATION="${2:-120}" # Default to 120 seconds (longer for slower real-time)
SCENARIO="${3:-takeoff_land}" # Default scenario
SCENARIO_DELAY="${4:-12}" # Wait longer for sim to stabilize (was 8s in pipeline)

# Model target formatting
case "$SIM_MODEL" in
  gz_*) MODEL_TARGET="$SIM_MODEL" ;;
  *) MODEL_TARGET="gz_${SIM_MODEL}" ;;
esac

# Set up Gazebo paths
export PX4_GZ_MODEL_PATH="${REPO_ROOT}/px4-gazebo-models:${PX4_DIR}/Tools/simulation/gz/models"
export GZ_SIM_RESOURCE_PATH="${PX4_GZ_MODEL_PATH}:${PX4_DIR}/Tools/simulation/gz/worlds"
export PX4_SIM_MODEL="$MODEL_TARGET"

# DO NOT set HEADLESS=1 - we want the GUI visible!

echo "========================================="
echo "PX4 Gazebo Simulation with GUI"
echo "========================================="
echo "Model: $SIM_MODEL ($MODEL_TARGET)"
echo "Duration: ${SIM_DURATION}s"
echo "Scenario: $SCENARIO"
echo "Scenario delay: ${SCENARIO_DELAY}s"
echo "========================================="
echo ""
echo "NOTE: If sim real-time factor is <100%, increase"
echo "      SIM_DURATION or close other applications"
echo "========================================="

# Kill any existing sim processes
pkill -f "build/px4_sitl_default/bin/px4" >/dev/null 2>&1 || true
pkill -f "gz sim" >/dev/null 2>&1 || true
sleep 2

# Create artifacts directory
ARTIFACT_DIR="${REPO_ROOT}/artifacts"
mkdir -p "$ARTIFACT_DIR"

# Launch scenario script if provided
SCENARIO_PID=""
if [ "$SCENARIO" != "none" ]; then
  SCENARIO_SCRIPT="${REPO_ROOT}/tests/scenarios/${SCENARIO}.py"
  if [ -f "$SCENARIO_SCRIPT" ]; then
    SCENARIO_LOG="${ARTIFACT_DIR}/${SCENARIO}.log"
    SCENARIO_SUMMARY="${ARTIFACT_DIR}/${SCENARIO}_summary.json"
    echo "Starting scenario ${SCENARIO} (waiting ${SCENARIO_DELAY}s for sim startup)..."
    echo "You can monitor progress with: tail -f ${SCENARIO_LOG}"
    (
      sleep "$SCENARIO_DELAY"
      echo "[scenario] Starting takeoff/land sequence..."
      SIMTEST_SCENARIO_RESULT="$SCENARIO_SUMMARY" python3 -u "$SCENARIO_SCRIPT"
    ) > "$SCENARIO_LOG" 2>&1 &
    SCENARIO_PID=$!
  else
    echo "Warning: Scenario script not found at $SCENARIO_SCRIPT"
  fi
fi

# Launch simulation with GUI visible
echo "Launching Gazebo with GUI..."
cd "$PX4_DIR"

if timeout --foreground --signal=SIGINT --kill-after=30 "$SIM_DURATION" make px4_sitl "$MODEL_TARGET"; then
  echo "Simulation completed"
else
  status=$?
  if [ "$status" -eq 124 ] || [ "$status" -eq 137 ] || [ "$status" -eq 143 ]; then
    echo "Simulation stopped after ${SIM_DURATION}s"
  else
    echo "Simulation exited with status $status"
  fi
fi

# Cleanup
if [ -n "$SCENARIO_PID" ]; then
  wait "$SCENARIO_PID" 2>/dev/null || true
fi

pkill -f "build/px4_sitl_default/bin/px4" >/dev/null 2>&1 || true
pkill -f "gz sim" >/dev/null 2>&1 || true

echo "Done!"

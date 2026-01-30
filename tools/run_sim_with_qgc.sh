#!/usr/bin/env bash
# Launch PX4 Gazebo simulation with GUI + QGroundControl for manual control
# This runs the simulation indefinitely and launches QGC with virtual joystick support

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${SCRIPT_DIR}/.."
PX4_DIR="${REPO_ROOT}/px4"
QGC_BUILD_DIR="$REPO_ROOT/build/qgc-simtest"
QGC_BINARY="$QGC_BUILD_DIR/AppDir/usr/bin/QGroundControl"

# Configuration
SIM_MODEL="${1:-x500}"  # Default to x500 quadrotor
SIM_WORLD="${2:-lawn}"  # Default to lawn world (green grass, clouds)

# Model target formatting
case "$SIM_MODEL" in
  gz_*) MODEL_TARGET="$SIM_MODEL" ;;
  *) MODEL_TARGET="gz_${SIM_MODEL}" ;;
esac

# Set up Gazebo paths
export PX4_GZ_MODEL_PATH="${REPO_ROOT}/px4-gazebo-models:${PX4_DIR}/Tools/simulation/gz/models"
export GZ_SIM_RESOURCE_PATH="${PX4_GZ_MODEL_PATH}:${PX4_DIR}/Tools/simulation/gz/worlds:${REPO_ROOT}/px4-gazebo-models/worlds"
export PX4_SIM_MODEL="$MODEL_TARGET"
export PX4_GZ_WORLD="$SIM_WORLD"

# DO NOT set HEADLESS=1 - we want the GUI visible!

echo "========================================="
echo "PX4 Gazebo + QGroundControl Manual Control"
echo "========================================="
echo "Model: $SIM_MODEL ($MODEL_TARGET)"
echo "World: $SIM_WORLD"
echo "Mode: Manual control (no automated scenario)"
echo ""
echo "This will launch:"
echo "  1. Gazebo simulation with GUI"
echo "  2. QGroundControl with virtual joystick"
echo ""
echo "To enable virtual joystick in QGC:"
echo "  1. Click gear icon (Application Settings)"
echo "  2. Go to General tab"
echo "  3. Enable 'Virtual joystick' checkbox"
echo "  4. Virtual thumbsticks will appear in Fly View"
echo ""
echo "To control the drone:"
echo "  1. In QGC, set parameter COM_RC_IN_MODE = 1"
echo "  2. Arm the drone (via QGC or sticks)"
echo "  3. Use virtual thumbsticks to fly"
echo ""
echo "Press Ctrl+C to stop everything"
echo "========================================="

# Check if QGC is built
if [ ! -x "$QGC_BINARY" ]; then
  echo ""
  echo "Error: QGroundControl not found at $QGC_BINARY"
  echo "Please build it first with: ./tools/simtest qgc build"
  exit 1
fi

# Kill any existing sim processes
echo ""
echo "Cleaning up any existing processes..."
pkill -f "build/px4_sitl_default/bin/px4" >/dev/null 2>&1 || true
pkill -f "gz sim" >/dev/null 2>&1 || true
pkill -f "QGroundControl" >/dev/null 2>&1 || true
sleep 2

# Launch Gazebo simulation in background
echo "Launching Gazebo simulation..."
cd "$PX4_DIR"
make px4_sitl "$MODEL_TARGET" &
SIM_PID=$!
cd "$REPO_ROOT"

# Wait for simulation to start up
echo "Waiting 8 seconds for simulation to initialize..."
sleep 8

# Launch QGroundControl
echo ""
echo "Launching QGroundControl..."
echo "It should auto-connect to PX4 on UDP 14550"
echo ""
"$QGC_BINARY" &
QGC_PID=$!

# Cleanup function
cleanup() {
  echo ""
  echo "Shutting down..."
  kill "$QGC_PID" >/dev/null 2>&1 || true
  kill "$SIM_PID" >/dev/null 2>&1 || true
  pkill -f "build/px4_sitl_default/bin/px4" >/dev/null 2>&1 || true
  pkill -f "gz sim" >/dev/null 2>&1 || true
  pkill -f "QGroundControl" >/dev/null 2>&1 || true
  echo "Done!"
}

trap cleanup EXIT INT TERM

echo "========================================="
echo "Both Gazebo and QGroundControl are running"
echo "========================================="
echo ""
echo "Gazebo PID: $SIM_PID"
echo "QGC PID: $QGC_PID"
echo ""
echo "Running indefinitely until you press Ctrl+C"
echo ""

# Wait for both processes
wait

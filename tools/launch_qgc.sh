#!/usr/bin/env bash
# Launch QGroundControl to connect to running PX4 simulation
# Run this AFTER starting the simulation with run_sim_gui_manual.sh

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${SCRIPT_DIR}/.."
QGC_BUILD_DIR="$REPO_ROOT/build/qgc-simtest"
QGC_BINARY="$QGC_BUILD_DIR/AppDir/usr/bin/QGroundControl"

echo "========================================="
echo "Launching QGroundControl"
echo "========================================="

# Check if QGC is built
if [ ! -x "$QGC_BINARY" ]; then
  echo "QGroundControl not found at $QGC_BINARY"
  echo "Building QGroundControl first..."
  ./tools/simtest qgc build
fi

if [ ! -x "$QGC_BINARY" ]; then
  echo "Error: QGroundControl build failed"
  exit 1
fi

echo "Starting QGroundControl..."
echo "It should auto-connect to PX4 on UDP 14550"
echo ""

# Launch QGC (it will automatically connect to localhost:14550)
"$QGC_BINARY" &

echo "QGroundControl launched (PID: $!)"
echo "To close: Use File > Exit in QGC or kill the process"

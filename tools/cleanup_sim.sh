#!/usr/bin/env bash
# Cleanup script to kill all lingering simulation processes
# Run this after a simulation to ensure clean slate

set -euo pipefail

echo "========================================="
echo "Simulation Process Cleanup"
echo "========================================="
echo ""

# Function to kill processes matching a pattern
kill_processes() {
  local pattern=$1
  local description=$2

  # Find matching processes
  if pgrep -f "$pattern" >/dev/null 2>&1; then
    echo "Found $description processes:"
    pgrep -fa "$pattern" | sed 's/^/  /'
    echo ""
    echo "Killing $description processes..."
    pkill -9 -f "$pattern" || true
    sleep 0.5

    # Verify they're gone
    if pgrep -f "$pattern" >/dev/null 2>&1; then
      echo "  ⚠ Warning: Some $description processes still running"
    else
      echo "  ✓ All $description processes terminated"
    fi
  else
    echo "No $description processes found"
  fi
  echo ""
}

# Kill PX4 SITL instances
kill_processes "build/px4_sitl_default/bin/px4" "PX4 SITL"

# Kill Gazebo instances (multiple possible process names)
kill_processes "gz sim" "Gazebo"
kill_processes "gzserver" "Gazebo Server"
kill_processes "gzclient" "Gazebo Client"

# Kill QGroundControl instances
kill_processes "QGroundControl" "QGroundControl"

# Kill any Python scenario scripts
kill_processes "tests/scenarios/.*\.py" "Python scenario"

# Kill any virtual joystick scripts
kill_processes "python_virtual_joystick.py" "Virtual joystick"

# Kill any simple_takeoff scripts
kill_processes "simple_takeoff.py" "Simple takeoff"

echo "========================================="
echo "Cleanup Complete"
echo "========================================="
echo ""
echo "Verification:"

# Check if anything is still running
still_running=0

if pgrep -f "px4" >/dev/null 2>&1; then
  echo "  ⚠ Warning: Some px4 processes still running:"
  pgrep -fa "px4" | sed 's/^/    /'
  still_running=1
fi

if pgrep -f "gz" >/dev/null 2>&1; then
  echo "  ⚠ Warning: Some Gazebo processes still running:"
  pgrep -fa "gz" | sed 's/^/    /'
  still_running=1
fi

if pgrep -f "QGroundControl" >/dev/null 2>&1; then
  echo "  ⚠ Warning: QGroundControl still running:"
  pgrep -fa "QGroundControl" | sed 's/^/    /'
  still_running=1
fi

if [ $still_running -eq 0 ]; then
  echo "  ✓ All simulation processes cleaned up successfully"
  echo ""
  echo "You can now start a fresh simulation."
else
  echo ""
  echo "Some processes may require manual intervention."
  echo "If needed, you can try: sudo kill -9 <PID>"
fi

echo ""

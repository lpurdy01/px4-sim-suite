#!/usr/bin/env bash
set -euo pipefail

# Stage 1 helper: build and launch PX4 SITL with Gazebo (headless)
# Usage: ./tools/run_stage1_headless.sh [extra make args]

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PX4_ROOT="${SCRIPT_DIR}/../px4"

if [ ! -d "${PX4_ROOT}" ]; then
  echo "PX4 submodule not found at ${PX4_ROOT}" >&2
  exit 1
fi

export HEADLESS="${HEADLESS:-1}"
export PX4_SIM_MODEL="${PX4_SIM_MODEL:-x500}"

cd "${PX4_ROOT}"

# Build and launch PX4 SITL with Gazebo using the X500 model by default.
# Additional arguments are forwarded to make (e.g., VERBOSE=1).
make px4_sitl "gz_${PX4_SIM_MODEL}" "$@"

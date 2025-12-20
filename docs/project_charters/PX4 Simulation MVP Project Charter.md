# PX4 Simulation MVP Project Charter

## Overview and Goal
Set up a PX4 Software-In-The-Loop (SITL) simulation environment using Gazebo for a quadcopter UAV. The Minimum Viable Product (MVP) demonstrates a basic quadrotor taking off, hovering, and landing in simulation. The px4-sim-suite repository already includes PX4, Gazebo models, and QGroundControl sources; the goal is to prove that PX4 can control a virtual quadcopter in Gazebo as a foundation for further development.

## MVP Scope and Features
- **Vehicle**: Single quadrotor (use the standard X500 Gazebo model; analogous to the classic Iris).
- **Simulation environment**: PX4 runs in SITL on Ubuntu 24.04 (WSL) and connects to Gazebo (Ignition/Harmonic or newer). The included `px4-gazebo-models` submodule supplies required models and worlds.
- **Flight demonstration**: Perform an autonomous takeoff, brief hover, and landing to validate PX4 ↔ Gazebo integration. Trigger via PX4 shell commands (`commander takeoff`, `commander land`).
- **User interface**: Command-line control suffices. QGroundControl is optional for monitoring when a GUI is available.
- **Out of scope**: Multi-vehicle setups, non-quadrotor types, ROS integration, advanced missions, or payload testing.

## Repository Structure
- **PX4 Autopilot** (`px4/`): Full PX4 source; build in SITL mode.
- **Gazebo models** (`px4-gazebo-models/`): SDF models and worlds (including X500).
- **QGroundControl** (`qgroundcontrol/`): Ground control station source (optional for MVP).
- **Documentation and tools** (`docs/`, `tools/`, `tests/`): Guidance, scripts, and helper utilities. Review `AGENTS.md` for contribution rules.

## Development Environment Setup
1. **Install dependencies** using the PX4 setup script: `px4/Tools/setup/ubuntu.sh` (installs Gazebo/gz, CMake, Ninja, etc.). If Ubuntu 24.04 packages differ, install Gazebo manually via `apt` as needed.
2. **Verify Gazebo** with `gz --version` (Ignition/Harmonic or newer expected).
3. **Build and launch PX4 SITL** from `px4/`: `make px4_sitl gz_x500` to compile PX4 and start Gazebo with the X500 model.
4. **Headless mode (WSL-friendly)**: `HEADLESS=1 make px4_sitl gz_x500` to run without a Gazebo GUI while keeping the PX4 console interactive.
5. **Networking**: PX4 SITL broadcasts on UDP 14550. QGroundControl on the host typically auto-discovers the vehicle; ensure firewall rules allow it if using QGC.
6. **QGroundControl (optional)**: Use the Windows installer or build from source on Linux when a GUI is available; not required for MVP validation.

## Development Workflow
- **Branching**: Work on feature branches (e.g., `feature/<desc>`, `fix/<desc>`, `docs/<desc>`). Use platform-provided branch names if required.
- **Commits**: Prefer small, clear commits (Conventional Commit style when practical). Example: `feat: add SITL takeoff/land script`.
- **Pull requests**: Summarize changes and include test instructions. Example test flow: `HEADLESS=1 make px4_sitl gz_x500`, then run `commander takeoff` and `commander land` in the PX4 console.
- **Testing**: Run relevant scripts/tests locally; avoid adding large binaries. Update documentation alongside features.

## MVP Roadmap
### Stage 1 — Environment & SITL Bring-Up
- Prepare Ubuntu 24.04 WSL environment and install dependencies via `px4/Tools/setup/ubuntu.sh` (or manual `apt` as needed).
- Confirm Gazebo installation and availability of the X500 model from `px4-gazebo-models/`.
- Build and launch PX4 SITL with `HEADLESS=1 make px4_sitl gz_x500`; verify PX4 connects to Gazebo (PX4 shell shows simulator link messages).
- Troubleshoot connectivity if PX4 times out; confirm model paths and environment variables.

### Stage 2 — Basic Flight Test
- From the PX4 shell, run `commander takeoff`, allow a brief hover, then `commander land`.
- Success criteria: arms, lifts, hovers, lands cleanly without crashes or connection drops.

### Stage 3 — Automation & Documentation
- Automate the takeoff/land smoke test (e.g., MAVSDK or simple shell automation).
- Capture logs/console output for evidence.
- Document run steps in `README.md` or dedicated docs; ensure instructions are repeatable and lightweight.

## Additional Resources
- PX4 Gazebo (Ignition) guide: https://docs.px4.io/main/en/sim_gazebo_gz/
- PX4 Gazebo Classic guide: https://docs.px4.io/main/en/sim_gazebo_classic/
- General PX4 simulation overview: https://docs.px4.io/main/en/simulation/
- QGroundControl install guide: https://docs.qgroundcontrol.com/master/en/qgc-user-guide/getting_started/download_and_install.html
- MAVSDK documentation (optional automation): https://mavsdk.mavlink.io/

https://docs.qgroundcontrol.com/master/en/qgc-user-guide/getting_started/download_and_install.html

7


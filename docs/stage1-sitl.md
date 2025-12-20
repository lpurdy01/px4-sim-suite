# Stage 1 — PX4 SITL bring-up (Ubuntu 24.04 WSL2)

Use this runbook to complete Stage 1 of the MVP charter: get PX4 SITL running against Gazebo (Ignition/Harmonic or newer) on Ubuntu 24.04 inside WSL2. The focus is a headless, repeatable setup that also works in containers.

## 1) Host prerequisites
- **Windows 11 + WSL2** with virtualization enabled (BIOS and Windows features).
- **Ubuntu 24.04** distribution installed (`wsl --install -d Ubuntu-24.04`).
- Enable **systemd** inside WSL so Gazebo services and udev rules work:
  ```bash
  cat <<'EOT' | sudo tee /etc/wsl.conf
  [boot]
  systemd=true
  EOT
  wsl --shutdown
  ```
- Resource guidance: at least **4 vCPU / 8 GB RAM**, **10+ GB disk**; more is helpful for faster builds.
- If running inside a container, ensure GPU acceleration is not required (the Stage 1 flow is CPU/headless).

## 2) Repository checkout and submodules
From your workspace (e.g., `/mnt/c/work/`):
```bash
git clone https://github.com/<your-org>/px4-sim-suite.git
cd px4-sim-suite
git submodule update --init --recursive
```

## 3) Install dependencies (Ubuntu 24.04/WSL)
Run the PX4 dependency script. Non-interactive mode avoids tzdata prompts inside WSL/CI:
```bash
sudo apt update
DEBIAN_FRONTEND=noninteractive sudo -E bash px4/Tools/setup/ubuntu.sh
```
What this covers:
- GCC/Clang toolchains, CMake, Ninja
- Gazebo (Ignition/Harmonic or newer) and ignition-transport
- Development libraries used by PX4 SITL

Verification checks (run after the script completes):
```bash
which gz
gz --version
ninja --version
```
If `gz` is missing on 24.04, install from packages that ship with Ubuntu (Harmonic) or via Gazebo’s apt repo: https://gazebosim.org/docs/harmonic/install_ubuntu.

## 4) Build & launch PX4 SITL (headless)
Use the helper script added for Stage 1. It forces headless mode and defaults to the X500 Gazebo model.
```bash
./tools/run_stage1_headless.sh
```
Expected console markers (from PX4 shell):
- `Simulator connected on UDP port 14560` (or similar)
- `INFO  [simulator] Waiting for model `_` response` then `Got namespace: px4`
- A PX4 interactive shell prompt `pxh>` once running

If you prefer manual make commands:
```bash
cd px4
HEADLESS=1 make px4_sitl gz_x500
```

## 5) Basic smoke test (manual)
In the PX4 shell (`pxh>`):
```bash
commander takeoff
# wait ~5–10 seconds for hover
commander land
```
Watch for errors such as `Simulator not connected` or link timeout messages. In headless mode there is no Gazebo GUI; rely on PX4 logs.

## 6) Troubleshooting checklist
- **Gazebo not found**: re-run the setup script or install Gazebo Harmonic packages (`sudo apt install gz-harmonic`).
- **Link timeout**: confirm model paths are present in `px4-gazebo-models/` and that the `gz` command exists in `PATH`.
- **Display issues**: headless mode (`HEADLESS=1`) avoids GUI requirements; skip `gz sim` GUI flags.
- **Long builds**: enable compiler cache if desired (`sudo apt install ccache` then set `export CCACHE_DIR=~/.ccache`).

## 7) Containerization notes
- The headless command works in containers that expose `/dev/kvm` and allow UDP networking; no X server is required.
- Mount this repo into the container and run `./tools/run_stage1_headless.sh` from the container shell.
- Persist the `build/` directory between runs (volume mount) to avoid full rebuilds.
- Do **not** commit container images or build artifacts; keep instructions and scripts only.

## 8) Expected artifacts (human-only)
Stage 1 does not produce committed binaries. If you capture logs (`px4/logs/`), keep them local or attach to reviews as ad-hoc artifacts; do not commit them.

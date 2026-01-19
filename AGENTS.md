# AGENTS.md
Rules, constraints, and procedures for agentic AI systems and hybrid workflows.

This repository is explicitly designed for **mixed human + agentic AI development**.
Not all tools have the same permissions or capabilities.  
This document defines how work proceeds safely and traceably.

---

## 1. Repository authority model

There are **three classes of actors**:

### 1. Humans (full authority)
- Can modify any repository or submodule
- Can manage forks, remotes, and upstream merges
- Can apply patches across repos
- Can commit binary artifacts if needed

### 2. Agentic AI with single-repo scope (e.g. Codex)
- Has access to *this repository only*
- Can modify files tracked directly in this repo
- Cannot reliably push commits to submodule forks
- Cannot manage multi-repo PRs
- Cannot commit binary files

### 3. Agentic AI with local machine access (e.g. Copilot in WSL)
- Has broader context
- May apply patches to submodules under human supervision
- Still follows the same documentation and process rules

All workflows must assume **the weakest agent** by default.

---

## 2. Submodules: rules and reality

This repo uses git submodules for PX4, QGroundControl, and Gazebo models. All three point to forks maintained under the lpurdy01 GitHub account; treat those remotes as authoritative unless the human owner directs otherwise.

### Important facts agents must understand

- Submodules are **separate Git repositories**
- Updating a submodule pointer is a commit in *this* repo
- Changing code *inside* a submodule is a commit in *that submodule*
- Single-repo agents usually **cannot complete both steps**

Therefore:

> **Agents must not assume they can directly modify submodule code and push it.**

---

## 3. What agents MAY modify directly

Agents may directly edit and commit:

- Files under:
  - `tools/`
  - `tests/`
  - `docs/`
  - root-level config files
- Documentation
- Scripts
- Text-based configuration
- CI logic (when present)

Agents should prefer **minimal, local changes**.

### Shared environment manifest

- The single source of truth for host dependencies is `tools/environment_manifest.json`.
- The helper `tools/env_requirements.py` reads that manifest to install (`install`) or validate (`check`) tooling.
- `simtest doctor` simply runs the `check` action; update the manifest first, then rerun the command when new prerequisites are needed.
- The devcontainer post-create hook also calls the helper, so any manifest edits automatically flow into local and CI containers.
- Do **not** hard-code additional dependency lists in other scripts; reference or extend the manifest instead.

---

## 4. What agents MUST NOT modify directly

Agents must NOT directly push commits that:

- Modify submodule repositories (`px4/`, `qgroundcontrol/`, `px4-gazebo-models/`)
- Reconfigure `.gitmodules`
- Change submodule remotes
- Add or modify binary files
- Rewrite history
- Perform upstream merges

These actions require human involvement.

---

## 5. How agents propose submodule changes

If an agent determines that a change is required in a maintained fork
(e.g. PX4 or QGroundControl), it must follow this process:

### Step 1: Identify the exact change
- File paths
- Lines to modify
- Rationale
- Expected effect

### Step 2: Produce a patch or instructions

One of the following is required:

#### Option A — `.patch` file
Create a patch against the submodule codebase and place it under:

```text
docs/patches/<component>/<short-description>.patch
```

The patch must:

* Apply cleanly to the current submodule commit
* Be text-only
* Include sufficient context

#### Option B — Explicit step-by-step instructions

If a patch is not feasible, provide:

* Exact file paths
* Before/after code snippets
* Commit message suggestion
* Branch name suggestion

### Step 3: Reference the patch/instructions in the PR

The PR to this repo must clearly state:

* Which submodule is affected
* Where the patch/instructions are located
* That human action is required to complete the change

---

## 6. Human follow-up procedure (for context)

Humans will typically:

1. Apply the patch or instructions inside the relevant fork
2. Commit and push to the fork
3. Update the submodule pointer in this repo
4. Clean up patch artifacts if no longer needed
5. Merge the PR

Agents should not attempt to automate these steps.

---

## 7. Why this process exists

This is not bureaucracy — it reflects real constraints:

* Most agentic AI tools are **scoped to a single repo**
* Submodules are **intentionally isolated**
* PX4 and QGC are large, fast-moving upstream projects
* Silent submodule drift is dangerous

The patch/instruction model:

* Preserves traceability
* Prevents half-applied changes
* Allows humans to review cross-repo effects

---

## 8. Interaction with PX4’s internal submodules

PX4 itself contains many submodules (Gazebo, MAVLink, DDS, etc.).

Agents should assume:

* These are **vendor-managed**
* They are **not to be repointed or forked lightly**
* Custom behavior should be implemented:

  * in PX4 proper (when required), or
  * in this repo (preferred), or
  * via external models/plugins

Do **not** propose forking PX4’s internal submodules unless explicitly instructed.

---

## 9. Binary artifacts and generated files

Agentic systems must not attempt to commit:

* Compiled binaries
* Simulation outputs
* Logs
* Images generated from simulations

If such artifacts are relevant:

* Describe how to generate them
* Reference expected outputs
* Leave them for CI or human execution

---

## 10. Guiding principle for agents

When in doubt:

> **Prefer leaving a clear trail over making a partial change.**

A good agent contribution in this repo:

* Improves clarity
* Documents assumptions
* Leaves actionable instructions
* Avoids irreversible or opaque actions

---

## 11. MVP Development stages

This project follows a staged development approach defined in the project charter.

### Finding the stage documentation

**Start here**: `docs/project_charters/mvp_development_stages_context.md`

This document contains:
* The complete MVP project charter
* All 8 development stages (Stage 0 through Stage 8)
* Success criteria for each stage
* Agent suitability assessments
* Constraints and deliverables

### Current stage tracking

To determine which stage is currently active or completed:
1. Check recent git commits for stage-related messages
2. Review `README.md` for current implementation status
3. Verify deliverables listed in the charter against repository contents

### Stage-specific work

When assigned to work on a specific stage:
1. Read the stage definition in `docs/project_charters/mvp_development_stages_context.md`
2. Review the deliverables, constraints, and success conditions
3. Check what's already been implemented
4. Follow the permissions model (sections 3-4 above) for your changes
5. If the stage requires submodule changes, follow section 5 (patch process)

---

## Cross-reference

For overall project intent and structure, see:

* `README.md`
* `docs/project_charters/mvp_development_stages_context.md` (MVP stages and charter)

For upstream project context, see:

* PX4 documentation: [https://docs.px4.io/main/en/simulation/](https://docs.px4.io/main/en/simulation/)

---

## 12. GUI Simulation and Manual Control

This repository now supports visual simulation and manual control workflows in addition to headless CI testing.

### Available Modes

1. **Headless Automated** (CI/CD) - `./tools/simtest run`
   - Used by GitHub Actions
   - No GUI, fully automated
   - Minimal resource usage

2. **GUI with Automated Scenario** - `./tools/run_sim_with_gui.sh`
   - Visible Gazebo window
   - Automated flight test (takeoff_land by default)
   - Useful for visual verification of test scenarios

3. **GUI with Manual Control** - `./tools/run_sim_with_qgc.sh`
   - Visible Gazebo + QGroundControl
   - User flies manually with virtual joystick
   - Configurable world environments (lawn, baylands, etc.)

### Documentation

Detailed documentation for these tools is in:
- `tools/AGENTS.md` - Script reference and common workflows
- `tools/GAZEBO_WORLDS.md` - Available world environments
- `tools/setup_virtual_joystick.md` - QGC virtual joystick setup

### CI/CD Impact

The new GUI tools do NOT affect the CI/CD pipeline:
- GitHub Actions continues to use `./tools/simtest run`
- GUI scripts are development/testing tools only
- No changes to `.github/workflows/` are required


---

## 13. DevContainer Variants and Environment Setup

This repository provides **two devcontainer configurations** with different capabilities but shared installation infrastructure.

### Default DevContainer (`.devcontainer/devcontainer.json`)

**Agent considerations:**
- Use this for headless automation, CI/CD, and command-line workflows
- No GUI support - X11/Wayland display not available
- Minimal resource footprint
- Used by GitHub Actions

**When agents should recommend this:**
- User needs CI/CD compatible environment
- User wants headless testing
- User works in GitHub Codespaces without GUI
- Resource constraints (no X server needed)

**Scripts that work:**
- `./tools/simtest run` (headless)
- Any command-line workflow
- Background simulation without display

### WSL GUI DevContainer (`.devcontainer/wsl-gui/devcontainer.json`)

**Agent considerations:**
- Use this for visual simulation and interactive GUI workflows
- X11/Wayland forwarding enabled via WSLg
- Host networking for display access
- Larger resource footprint (X server + GUI apps)

**When agents should recommend this:**
- User wants to see Gazebo GUI
- User wants to use QGroundControl
- User needs visual debugging
- User is on Windows WSL2 with WSLg

**Scripts that work:**
- Everything from default devcontainer, PLUS:
- `./tools/run_sim_with_gui.sh` (visible Gazebo)
- `./tools/run_sim_with_qgc.sh` (Gazebo + QGC)
- `./tools/launch_qgc.sh` (QGroundControl)

### Shared Installation Infrastructure

**IMPORTANT for agents:** Both devcontainers use identical installation logic:

1. **Manifest:** `tools/environment_manifest.json`
   - Single source of truth for all dependencies
   - Defines versions, packages, Python requirements
   - **Do NOT** create duplicate dependency lists

2. **Installation script:** `tools/env_requirements.py`
   - Reads manifest
   - Installs system packages via apt
   - Installs Python packages via pip
   - Validates environment with `check` command

3. **PX4 setup:** `px4/Tools/setup/ubuntu.sh --no-nuttx`
   - Installs Gazebo Harmonic, MAVLink, etc.
   - Vendor-maintained by PX4 project
   - **Do NOT** duplicate this logic

**Divergence points (only two):**

1. **Docker mounts:** WSL GUI adds:
   ```json
   "mounts": [
     "source=/tmp/.X11-unix,target=/tmp/.X11-unix,type=bind",
     "source=/mnt/wslg,target=/mnt/wslg,type=bind"
   ]
   ```

2. **Environment variables:** WSL GUI adds:
   ```json
   "containerEnv": {
     "DISPLAY": ":0",
     "WAYLAND_DISPLAY": "wayland-0",
     "XDG_RUNTIME_DIR": "/mnt/wslg/runtime-dir",
     "PULSE_SERVER": "/mnt/wslg/PulseServer"
   }
   ```

**Everything else is identical.**

### Agent Decision Matrix

When a user reports an error:

| Error Message | Likely Cause | Recommendation |
|--------------|--------------|----------------|
| `cannot open display: :0` | Using default devcontainer | Switch to WSL GUI devcontainer |
| `Error: no DISPLAY variable set` | Using default devcontainer | Switch to WSL GUI devcontainer |
| `QGroundControl won't start` | Using default devcontainer | Switch to WSL GUI devcontainer |
| `Gazebo GUI blank/frozen` | Display forwarding issue | Check WSLg installation, verify DISPLAY set |
| Package not found | Manifest out of sync | Update `tools/environment_manifest.json` |

### Adding New Dependencies (Agent Workflow)

**Correct approach:**
1. Add package to `tools/environment_manifest.json`
2. Rebuild devcontainer (post-create hook runs automatically)
3. Users get new dependency transparently

**Incorrect approach (DO NOT DO THIS):**
- ❌ Add `apt-get install` to random scripts
- ❌ Add `pip install` to individual tools
- ❌ Create new installation scripts
- ❌ Modify devcontainer.json postCreateCommand

**Why:** Single source of truth prevents drift between:
- Local development
- CI/CD (GitHub Actions)
- Multiple devcontainer variants
- Documentation vs reality

### Recommending the Right DevContainer

When a user asks for help:

**User says:** "I want to see the drone flying"
**Agent recommends:** WSL GUI devcontainer + `./tools/run_sim_with_gui.sh`

**User says:** "Run automated tests"
**Agent recommends:** Default devcontainer + `./tools/simtest run`

**User says:** "Can I control the drone manually?"
**Agent recommends:** WSL GUI devcontainer + `./tools/run_sim_with_qgc.sh`

**User says:** "CI is failing"
**Agent checks:** Default devcontainer compatibility (CI uses this)

### Cross-Reference

For detailed devcontainer documentation:
- `README.md` - Section "DevContainer Variants"
- `tools/AGENTS.md` - Script compatibility with each devcontainer
- `tools/environment_manifest.json` - Dependency definitions
- `tools/env_requirements.py` - Installation and validation logic


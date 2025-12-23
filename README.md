# px4-sim-suite

A **simulation and development suite for PX4 firmware and custom aircraft**, designed to support:

- PX4 firmware development and customization
- Gazebo-based simulation (SITL)
- Mission- and scenario-level testing
- Hybrid human + agentic AI development workflows
- Portability across:
	- Ubuntu 24.04
	- WSL2 (Windows)
	- GitHub Codespaces
	- Headless CI (e.g., GitHub Actions)

This repository is **not a fork of PX4**.  
Instead, it is an **orchestration and integration layer** that wraps PX4 and related tools in a way that supports automation, testing, and iteration beyond what PX4 alone provides.

---

## Repository structure (high-level)

```text
px4-sim-suite/
├── px4/                 # PX4-Autopilot (fork, submodule)
├── qgroundcontrol/      # QGroundControl (fork, submodule)
├── px4-gazebo-models/   # Gazebo models (fork or upstream, submodule)
├── tools/               # Orchestration, runners, CI glue (owned here)
├── tests/               # Scenario / mission definitions (owned here)
├── docs/                # Design notes, references
├── AGENTS.md            # Rules and procedures for agentic AI
└── README.md
```

The **`px4/` directory already contains extensive simulation infrastructure** (Gazebo, FlightGear, jMAVSim, etc.) via PX4’s own submodules.
This repo intentionally **does not duplicate that functionality**, and instead layers testing, automation, and workflow management *around* PX4.

---

## Design intent

PX4 already functions as a **self-contained firmware + simulation engine**.
However, PX4 alone does **not** provide:

* A portable, container-friendly execution model
* Mission-level scenario testing as a first-class concept
* Artifact contracts (logs, reports) suitable for CI
* Clear separation between “engine” and “product/system testing”
* Agentic-AI-friendly contribution boundaries

This repository exists to fill those gaps **without modifying PX4’s internal structure unless necessary**.

Key architectural principle:

> **PX4 is treated as a vendor engine.
> This repository owns orchestration, scenarios, CI, and workflow.**

---

## Submodules and forks (overview)

This repository uses **git submodules** for large upstream projects that we intentionally fork and track:

| Component         | Location             | Ownership                     |
| ----------------- | -------------------- | ----------------------------- |
| PX4 Autopilot     | `px4/`               | Fork maintained by repo owner |
| QGroundControl    | `qgroundcontrol/`    | Fork maintained by repo owner |
| PX4 Gazebo Models | `px4-gazebo-models/` | Fork or upstream mirror       |

Each fork has:

* an `origin` remote (our fork)
* an `upstream` remote (canonical project)

Upstream merges are intentional and explicit.

See **`AGENTS.md`** for the exact rules governing submodules and how changes are proposed and applied.

---

## Human vs agent responsibilities

This is a **hybrid-managed repository**:

* Humans:

	* Own repo structure
	* Own submodule configuration
	* Perform upstream merges
	* Apply cross-repo changes
* Agentic AI (Codex, Copilot, etc.):

	* Propose changes
	* Modify code in-place where allowed
	* Leave structured instructions or patches when blocked by permissions

This division is intentional and documented in `AGENTS.md`.

---

## Important upstream sources (context)

These projects provide the underlying capabilities used here:

* PX4 Autopilot: [https://github.com/PX4/PX4-Autopilot](https://github.com/PX4/PX4-Autopilot)
* PX4 Simulation docs: [https://docs.px4.io/main/en/simulation/](https://docs.px4.io/main/en/simulation/)
* PX4 Gazebo models: [https://github.com/PX4/PX4-gazebo-models](https://github.com/PX4/PX4-gazebo-models)
* QGroundControl: [https://github.com/mavlink/qgroundcontrol](https://github.com/mavlink/qgroundcontrol)
* MAVLink: [https://github.com/mavlink/mavlink](https://github.com/mavlink/mavlink)

PX4 already vendors many simulation components internally via submodules; this repo does **not** attempt to replace that system.

---

## Scope boundaries (important)

This repository:

* ✔ Wraps PX4 for testing and automation
* ✔ Supports Gazebo-based simulation
* ✔ Supports human-in-the-loop and headless execution
* ✔ Supports agent-assisted development

This repository does **not**:

* ❌ Replace PX4’s internal simulation system
* ❌ Vendor PX4 dependencies manually
* ❌ Treat QGroundControl as a CI dependency
* ❌ Assume a single-developer workflow

---

## For agents and automation systems

If you are an automated agent or a human working with one:

👉 **Read `AGENTS.md` before making changes.**

That file defines:

* What can and cannot be modified directly
* How submodule changes are proposed
* How permissions and limitations are handled
* How work is handed off between agents and humans

---

## Stage 1 (MVP) quick start

Looking to bring up PX4 SITL on Ubuntu 24.04/WSL2 for the MVP? Follow the runbook in `docs/stage1-sitl.md` for dependency setup, headless launch, and a manual takeoff/land smoke test.

---

## Stage 1 CLI entry point (`tools/simtest`)

The unified CLI entry point for the simulation pipeline is provided as a Stage 1 stub at `tools/simtest`.
It is POSIX-shell-friendly and intended to run the same way on Ubuntu, WSL2, GitHub Actions, Codespaces, or a mounted Docker workspace.

```
Usage: simtest [build|run|collect|doctor|all|--help]
	build     Build PX4, models, dependencies
	run       Run the Gazebo simulation
	collect   Fetch artifacts (logs, flight results)
	doctor    Validate environment prerequisites against the manifest
	all       Execute build + run + collect
```

### `build` command (Stage 2)

The `build` subcommand now runs the PX4 SITL CMake flow for Gazebo Classic (non-ROS) targeting the default quadrotor airframe:

* Executes CMake from within `px4/` and configures `build/px4_sitl_default`
* Uses the Unix Makefiles generator with `make -j$(nproc)`
* Expects `cmake` and `make` to be installed; otherwise exits with a clear error

Troubleshooting tips:

* Ensure the `px4/` submodule is present (run `git submodule update --init --recursive` if needed)
* Install `cmake` and `make` via your system package manager before running `simtest build`

Examples:

```
sh tools/simtest build
sh tools/simtest all
```

### `run` command (Stage 4)

The `run` subcommand now launches a **headless** PX4 SITL + Gazebo Harmonic session using the built firmware:

* Ensures the PX4 build exists (invokes `build` automatically if missing)
* Uses the modern Gazebo Harmonic (`gz` CLI) flow, invoking `make px4_sitl gz_<model>` from `px4/`
* Defaults to the `x500` quadrotor (override with `PX4_SIM_MODEL`) and extends `PX4_GZ_MODEL_PATH`/`GZ_SIM_RESOURCE_PATH` with `px4-gazebo-models`
* Runs for a bounded duration (`SIM_DURATION` seconds; defaults to 45) before shutting down
* Executes the default Stage 5 scenario (`tests/scenarios/takeoff_land.py`) that arms, climbs to ~3 m, holds briefly, and lands via MAVLink commands

You can customize the duration or model:

```sh
SIM_DURATION=30 PX4_SIM_MODEL=x500 sh tools/simtest run
```

Use `sh tools/simtest all` to run both build and simulation in sequence.

### `doctor` command (Stage 2)

`simtest doctor` runs lightweight diagnostics that parse `tools/environment_manifest.json` and confirm the required executables, Python modules, and repo folders are present. It is safe to run repeatedly and provides a single-source-of-truth check that matches the packages installed by the dev container. The command exits non-zero if anything is missing so CI wrappers can gate expensive build steps.

If you want to disable automated flight control (for interactive debugging or manual testing), set `SIMTEST_SCENARIO=none` before invoking `simtest run`. To plug in a different scripted mission, drop a Python helper under `tests/scenarios/` and set `SIMTEST_SCENARIO=<name>`.

Each run persists its telemetry and summary artifacts under `artifacts/` (override with `SIMTEST_ARTIFACT_DIR`):

* `takeoff_land.log` — live scenario transcript (arm, hover, land events)
* `takeoff_land_summary.json` — hover/landing metrics in JSON
* `<timestamp>.ulg` — copy of the most recent PX4 flight log for post-flight analysis

Use `sh tools/simtest collect` to list the files produced in the selected artifact directory.

The `run` flow launches a lightweight MAVLink heartbeat helper implemented with `pymavlink` so PX4 no longer reports a missing GCS on startup. The dev container installs this dependency automatically; native environments should ensure `pymavlink` is available (for example via `pip install --user pymavlink`).

## Development container and CI build flow

A VS Code-compatible dev container is defined in `.devcontainer/devcontainer.json` to provide a consistent Ubuntu 24.04 base with CMake, Make, Python tooling, and PX4’s own Ubuntu setup script preinstalled. The container automatically initializes all submodules recursively, runs `tools/env_requirements.py install` to consume `tools/environment_manifest.json`, and executes PX4’s `Tools/setup/ubuntu.sh --no-nuttx` so the Gazebo Harmonic toolchain and other SITL dependencies are available. The repository mounts at `/workspaces/<repo>`, matching the default Dev Containers layout so commands like the update hook run in the right place. The post-create hook installs the Python packages defined in the manifest (including `pymavlink`) so the heartbeat helper is available everywhere.

For a single cross-platform entry point, use `tools/run_ci.sh`. Without arguments it builds (or updates) the dev container using the local `devcontainer` CLI and then runs the standard doctor/build/run sequence inside the container. GitHub Actions calls the same script with the `--inside-devcontainer` flag so both CI and local developers share identical orchestration. The workflow publishes four artifacts for traceability:

* `artifacts/simtest-doctor.log` — environment validation output
* `artifacts/simtest-build.log` — full build output
* `artifacts/simtest-run.log` — full headless run output
* `artifacts/simtest-report.txt` — build and run timing summary (in seconds)

These artifacts help triage build and runtime regressions across platforms while keeping the single `simtest` entry point consistent locally and in CI.

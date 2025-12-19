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

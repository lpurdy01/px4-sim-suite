Great — at this point you’re asking for a **project charter**, not an implementation plan or task list yet. That’s exactly the right abstraction layer before you start prompting Codex.

Below is an **MVP-focused project charter outline**, followed by a **stage breakdown** where:

* each stage is **narrow**
* each stage can be completed by **a single agent run**
* stages compose cleanly toward a working MVP
* everything orbits around the **single entry point** principle we discussed

I’ll stay deliberately high-signal and avoid implementation detail unless it belongs in the charter.

---

# Project Charter — `px4-sim-suite` (MVP)

## 1. Purpose & scope

### Purpose

Create a **portable, reproducible PX4 simulation development environment** that supports:

* Gazebo-based SITL
* Custom PX4 firmware development
* Scenario / mission-level testing
* Headless and interactive execution
* Hybrid human + agentic workflows

### Explicit non-goals (for MVP)

* No HITL
* No JSBSim
* No multi-vehicle simulation
* No real-time visualization requirement in CI
* No QGroundControl build integration (runtime only)

---

## 2. Supported execution targets (MVP contract)

The MVP must run identically (same commands, same behavior) on:

* Ubuntu 24.04 (bare metal)
* WSL2 on Windows
* GitHub Codespaces
* GitHub Actions runner (headless)

This requirement **drives every architectural decision**.

---

## 3. Architectural principles (charter-level)

These are *constraints*, not suggestions.

1. **Single entry point**

   * One command/script to build, run, test, and collect artifacts
   * CI, humans, and agents all invoke the same interface

2. **PX4 as engine, not orchestrator**

   * PX4 is treated as a vendor dependency
   * No rewriting PX4’s internal simulation system

3. **Headless-first**

   * GUI support is optional and never required for correctness

4. **Text-only agent outputs**

   * No binaries committed by agents
   * Artifacts are produced at runtime only

5. **Explicit artifacts**

   * Logs and results are written to a known location
   * CI uploads exactly that directory

---

## 4. MVP success criteria (definition of “done”)

The MVP is considered complete when **all** of the following are true:

1. A single command can:

   * build PX4 SITL
   * launch Gazebo headless
   * run a simple flight scenario
   * terminate cleanly
   * collect logs

2. The same command works on:

   * WSL
   * Codespaces
   * GitHub Actions

3. PX4 remains a clean fork:

   * no vendoring
   * no submodule rewiring

4. An agent can:

   * understand the repo
   * extend scenarios
   * propose PX4 changes via patch workflow

---

## 5. MVP stages (agent-sized tasks)

Each stage below is:

* **self-contained**
* **individually valuable**
* **completable by a single Codex-style agent**

They are ordered, but loosely coupled.

---

### Stage 0 — Charter & contracts (you are here)

**Deliverables**

* `README.md`
* `AGENTS.md`
* Project charter (this document, committed)

**Why it matters**

* Locks scope
* Prevents premature complexity
* Enables agent autonomy

---

### Stage 1 — Define the single entry point interface

**Goal**
Define *what* the entry point is, not how it works internally.

**Deliverables**

* `tools/simtest` (stub)
* Documented CLI contract, e.g.:

```text
simtest build
simtest run
simtest collect
simtest all
```

**Constraints**

* Must be callable from shell
* Must return nonzero on failure
* No PX4 logic yet

**Agent suitability**
✅ Pure text, pure structure

---

### Stage 2 — Environment normalization (no simulation yet)

**Goal**
Guarantee the same environment across all targets.

**Deliverables**

* Dockerfile (Ubuntu 24.04)
* `.devcontainer.json` referencing that image
* Minimal validation script (`simtest doctor`)

**Success condition**

* Container builds
* `simtest doctor` passes everywhere

**Agent suitability**
✅ Deterministic, infra-only

---

### Stage 3 — PX4 SITL build integration

**Goal**
Teach `simtest build` how to build PX4 SITL.

**Deliverables**

* Build logic that:

  * enters `px4/`
  * builds `px4_sitl`
* No Gazebo launch yet

**Success condition**

* PX4 builds successfully in container
* No runtime dependencies assumed

**Agent suitability**
✅ Single-repo logic

---

### Stage 4 — Headless Gazebo launch

**Goal**
Launch Gazebo SITL **headless**, controlled by the entry point.

**Deliverables**

* `simtest run` launches:

  * PX4 SITL
  * Gazebo (headless)
* Clean startup and shutdown

**Constraints**

* No GUI
* No user interaction

**Success condition**

* PX4 boots
* Gazebo runs
* MAVLink link established

**Agent suitability**
⚠️ Needs careful scripting, but still single-scope

---

### Stage 5 — Minimal flight scenario

**Goal**
Prove mission-level control.

**Deliverables**

* One scenario (e.g.:

  * arm
  * takeoff
  * hold
  * land)
* Scenario lives under `tests/`

**Constraints**

* No QGC dependency
* Scripted via MAVLink/MAVSDK

**Success condition**

* Scenario completes deterministically

**Agent suitability**
✅ Clear contract, no submodules touched

---

### Stage 6 — Artifact collection contract

**Goal**
Standardize outputs.

**Deliverables**

* Known artifact directory (e.g. `artifacts/`)
* Collected:

  * PX4 logs
  * scenario metadata (JSON)

**Success condition**

* CI can upload artifacts blindly

**Agent suitability**
✅ Simple filesystem logic

---

### Stage 7 — GitHub Actions integration

**Goal**
Prove portability.

**Deliverables**

* One workflow:

  * build container
  * run `simtest all`
  * upload artifacts

**Constraints**

* No CI-specific logic in `simtest`
* CI is a thin wrapper only

**Success condition**

* Green CI run with logs attached

**Agent suitability**
✅ YAML + shell only

---

### Stage 8 — Human-in-the-loop optional mode (non-blocking)

**Goal**
Allow interactive debugging without breaking headless flow.

**Deliverables**

* Optional flag (e.g. `--gui`)
* Documented but not required

**Success condition**

* Headless still works unchanged

**Agent suitability**
⚠️ Optional, defer if risky

---

## 6. Dependency & risk notes (charter-level)

### Known risks

* Gazebo version drift
* PX4 build time
* Headless timing issues

### Explicit mitigations

* Container pinning
* Minimal scenarios
* Timeouts and watchdogs

---

## 7. What this charter deliberately avoids

* No task breakdowns yet
* No file-level instructions
* No “how to implement”
* No performance optimization

Those come *after* the charter is accepted.

---

## 8. Why this charter works for agentic development

* Each stage is:

  * narrow
  * text-based
  * reversible
* Clear stop conditions
* Clear ownership boundaries
* No hidden state



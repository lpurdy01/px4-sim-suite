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

This repo uses git submodules for PX4, QGroundControl, and Gazebo models.

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

## Cross-reference

For overall project intent and structure, see:

* `README.md`

For upstream project context, see:

* PX4 documentation: [https://docs.px4.io/main/en/simulation/](https://docs.px4.io/main/en/simulation/)

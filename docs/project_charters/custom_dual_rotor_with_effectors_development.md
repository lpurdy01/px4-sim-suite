# Project Charter — Custom Rotorcraft Controls Sandbox

## 1. Purpose & Scope

### Purpose
Establish a reusable workflow for inventing and validating unconventional rotorcraft (e.g., Chinook-style tandem rotors with auxiliary thrust effectors) inside the px4-sim-suite. The charter pivots away from a quadplane airframe and instead targets a **controls-first sandbox** that proves the physics, visualization, and tooling required before strapping PX4 onto the vehicle.

### Outcomes
1. **Authoritative vehicle descriptor** that encodes rotor hubs, thrust vectors, point masses, inertia tensors, and optional nonlinear propeller curves.
2. **Paired physics back-ends** (lightweight analytic integrator + Gazebo-based model) that both ingest the descriptor so we can compare "our math" against an off-the-shelf rigid-body solver.
3. **Visualization and inspection tooling** for rotor disks, CG, and body axes to de-risk geometry/mass mistakes early.
4. **Direct stimulus harnesses** to poke the plant with scripted thrust/torque programs prior to PX4 involvement.
5. **PX4 interface layer** that reuses the same descriptor and plant model once feasibility is proven.

### Explicit Non-Goals
* No electrical system, ESC, or detailed motor thermal modeling.
* No commitment to a specific airframe geometry; the descriptor must generalize across exotic layouts.
* No autopilot tuning inside this stage—goal is plant readiness and instrumentation, not controller gains.

---

## 2. Reference Architecture

### 2.1 Vehicle Descriptor Schema
* Format: YAML or JSON stored under `docs/vehicles/<name>.yaml` (TBD in Stage 1).
* Core fields:
  * `mass_properties`: total mass, principal inertia, CG offset.
  * `point_masses[]`: location + optional inertia contributions for booms, payloads, batteries.
  * `actuators.rotors[]`: hub pose, thrust axis, moment arm, spin direction, thrust model (`linear`, `table`, or `nonlinear_poly`).
  * `actuators.effectors[]`: ducts, vanes, or other force-generating widgets.
  * `visualization`: colors, disk radii, labeling instructions.
* Validation script in `tools/vehicle_schema.py` ensures units, coordinate frames, and symmetry rules are respected.

### 2.2 Physics Back-Ends
* **Analytic Integrator (Stage 2 artifact)**
  * Python/NumPy state propagator living under `tools/dynamics/`. Computes translational and rotational dynamics via
    $$\dot{\mathbf{v}} = \frac{1}{m} \sum_i \mathbf{F}_i, \qquad \dot{\boldsymbol{\omega}} = I^{-1}\left( \sum_i \boldsymbol{\tau}_i - \boldsymbol{\omega} \times I \boldsymbol{\omega} \right).$$
  * Supports optional nonlinear thrust curves so we can study couplings before moving to a full simulator.
  * Emits CSV/Parquet traces for scripted stimuli.
* **Gazebo Plant (Stage 3 artifact)**
  * Auto-generated SDF in `px4-gazebo-models/models/<name>/` derived from the descriptor.
  * Custom visualization plugin renders rotor disks, CG marker, and principal axes for rapid QA.
  * Uses Ignition/Gazebo components (multicopter motor model, external wrench system) strictly as the integrator; no PX4 dependency yet.

### 2.3 Visualization & Mass-Property Tooling
* `tools/visualize_vehicle.py` loads the descriptor and:
  * Generates static SVG/GLB overlays of rotor placement.
  * Publishes a Gazebo GUI overlay (via transport topics) for in-sim inspection.
* Optional Jupyter notebook in `docs/notebooks/vehicle_mass_checks.ipynb` for plotly-based inertia sanity checks.

### 2.4 Stimulus & Scenario Pipelines
* Scenario definitions stored in `tests/scenarios/<vehicle>/<name>.yaml` describing thrust, torque, or state target sweeps.
* `tools/direct_stimulus.py` replays scenarios against either physics back-end, producing canonical logs for regression testing.
* Early focus on:
  * CG offset experiments (sweep thrust asymmetry, observe angular rates).
  * Coupled rotor vane tests (command small vane deflections with fixed thrust to validate torque models).

### 2.5 PX4 Integration Bridge
* When plant confidence is achieved, generate companion PX4 mixer definitions in `px4/ROMFS/.../airframes/` using the descriptor.
* Bridge layer maps descriptor actuators to `SIM_GZ_EC_FUNC*` / `SIM_GZ_SV_FUNC*` indices so the same Gazebo model services both direct stimuli and PX4 SITL.
* Keep plant execution identical by letting PX4 publish actuator commands onto the same transport topics consumed by the Gazebo model.

### 2.6 Alignment with px4-gazebo-models
* Launch path: lean on the upstream `simulation-gazebo` script in [px4-gazebo-models](px4-gazebo-models/README.md) so our experiments inherit PX4's tested Garden/Harmonic setup and automatic resource mirroring.
* Authoritative assets: instead of emitting raw SDF files, Stage 3 will generate parameter inputs for the existing `.sdf.jinja` templates (e.g., `standard_vtol.sdf.jinja`) so we automatically reuse PX4's meshes, collision tuning, and sensor noise definitions.
* Schema mapping: Stage 1's descriptor fields intentionally mirror the data that the templates expect (`link.pose`, `inertial`, rotor plugin constants, sensor blocks). Regenerating stock models like [models/x500/model.sdf](px4-gazebo-models/models/x500/model.sdf) becomes our regression test for the transpiler.
* Version safety: by consuming upstream templates untouched, we gain easy updates when PX4 publishes improvements; our generator simply re-runs with the refreshed template while keeping descriptor compatibility.

---

## 3. Bring-Up Stages

| Stage | Goal | Key Deliverables | Agent Suitability |
| --- | --- | --- | --- |
| 0 | Charter & rescope approval | This document, updated backlog | ✅ High |
| 1 | Descriptor schema + validation | Schema file, example vehicle, CLI validator script, CI check | ✅ High |
| 2 | Analytic physics harness | `tools/dynamics/` integrator, logging format, unit tests for force/moment bookkeeping | ✅ High |
| 3 | Gazebo model generator & visualizer | Descriptor→SDF transpiler, CG/rotor overlay plugin, smoke-test world | ⚠️ Moderate (requires SDF expertise) |
| 4 | Direct stimulus pipelines | Scenario spec, execution CLI, regression plots, baseline maneuver library | ✅ High |
| 5 | PX4 bridge (optional stretch) | Auto-generated mixer + params, SITL harness hooking into same stimuli | ⚠️ Moderate (uORB familiarity) |

Each stage should finish with a "descriptor lock"—the schema must stay back-compatible to avoid churning downstream artifacts.

---

## 4. Infrastructure & Tooling Requirements

* **Directory hygiene**
  * `docs/vehicles/` — canonical descriptors and supporting notes.
  * `tools/dynamics/` — analytic integrator, thrust models, logging utilities.
  * `tools/visualizers/` — Gazebo overlays, static diagram generators.
  * `tests/scenarios/` — stimulus definitions + expected log signatures.
* **Testing strategy**
  * Stage 1: schema unit tests plus JSON schema validation in CI.
  * Stage 2–4: pytest-based comparisons of analytic vs. Gazebo response for standard maneuvers; acceptable error tolerances documented per scenario.
* **Optional nonlinear prop modeling**
  * Provide coefficient slots or tabulated lookup tables in the descriptor, but keep them dormant until needed.
  * Include regression tests with and without nonlinear terms to guard against accidental coupling changes.
* **Observability**
  * Standard log bundle: descriptor hash, scenario id, integrator version, environment manifest version.
  * Dashboard notebook that overlays commanded vs. achieved forces/torques to highlight physics drift.

---

## 5. Risks & Mitigations

| Risk | Description | Mitigation |
| --- | --- | --- |
| Conflicting coordinate frames | Descriptor, analytic model, and Gazebo may disagree on axes conventions. | Formalize right-handed NED vs. body frames in schema docs; add automated frame-consistency tests. |
| Descriptor sprawl | Without guardrails every airframe becomes bespoke. | Enforce schema versioning and template generators; document patterns for tandem, coaxial, and ducted rotors. |
| Gazebo ↔ analytic divergence | Numerical drift may mask physics bugs. | Maintain golden stimulus cases; fail CI when error envelopes exceed published thresholds. |
| Premature PX4 coupling | Jumping into autopilot tuning before plant maturity. | Gate Stage 5 on signed-off checklists from Stages 1–4; require human approval before enabling PX4 bridge work. |

---

## 6. Next Actions
1. Finalize descriptor schema draft and circulate for review.
2. Build the validator CLI plus a simple tandem-rotor example to exercise the schema.
3. Stand up the analytic integrator skeleton so we can begin playing with thrust effectors immediately after schema sign-off.

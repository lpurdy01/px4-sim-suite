# Dual Chinook Implementation Tracker

## Overview
This tracker converts the custom rotorcraft charter into an actionable plan focused on a tandem-rotor "dual Chinook" demonstrator. Work occurs entirely inside the devcontainer (see `AGENTS.md`); no standalone Python virtual environments are permitted. The near-term objective is an automated throttle-up takeoff experiment that produces a Plotly HTML report.

## Milestones & Deliverables
| ID | Scope | Key Outputs | Dependencies | Status |
| --- | --- | --- | --- | --- |
| M1 | Descriptor schema instance | `docs/vehicles/dual_chinook.yaml` capturing mass, inertia, rotor geometry | Charter §2, px4-gazebo-models template study | ⚙️ In progress |
| M2 | Analytic plant harness | `tools/dynamics/dual_chinook_sim.py` + reusable scenario loader | M1 | ⚙️ In progress |
| M3 | Scenario + logging | `tests/scenarios/dual_chinook_throttle.yaml`, data serialization format, baseline artifact path | M1, M2 | ⚙️ In progress |
| M4 | Plotly reporting | `tools/dynamics/run_dual_chinook_throttle.py` emits HTML in `tests/artifacts/dual_chinook/` | M2, M3 | ⚙️ In progress |
| M5 | Gazebo integration plan | Instructions + template parameter mapping patch stub (future PR) | M1 | ⏳ Not started |
| M6 | PX4 bridge + SITL | Airframe script + scenario replay through PX4 (stretch) | M5 | ⏳ Not started |

_Status Legend_: ✅ done · ⚙️ in progress · ⏳ queued · ⚠️ blocked

## Execution Checklist
- [ ] Finalize descriptor fields/units + validator stub
- [ ] Implement dual-rotor analytic integrator with motor dynamics
- [ ] Define throttle-ramp scenario YAML and parser
- [ ] Generate Plotly HTML (altitude, velocity, rotor RPM, throttle)
- [ ] Document Gazebo template mapping + required submodule patch steps
- [ ] Add automated regression guard comparing analytic traces to future Gazebo logs

## Success Criteria (Phase 1)
1. Running `python3 tools/dynamics/run_dual_chinook_throttle.py \
   --descriptor docs/vehicles/dual_chinook.yaml \
   --scenario tests/scenarios/dual_chinook_throttle.yaml \
   --output tests/artifacts/dual_chinook/throttle_step_analytic.html` finishes without errors.
2. The generated HTML contains at least two stacked Plotly charts that show:
   * Rotor throttle command vs. achieved RPM
   * Altitude/vertical velocity vs. time demonstrating liftoff and stable hover when undisturbed
3. Instructions for extending the descriptor to Gazebo templates are captured (future milestone) so that a human can port the analytic configuration into `px4-gazebo-models` via the documented patch process.

## Notes & Risks
- Gazebo resource updates require a patch against the `px4-gazebo-models` submodule; track that work separately.
- Analytic model assumes perfect symmetry (two rotors exactly cancel yaw torque). Disturbance handling will require a controller phase not included here.
- Plotly HTML artifacts should remain in `tests/artifacts/`; do not commit large binary outputs—regenerate as needed following the instructions above.

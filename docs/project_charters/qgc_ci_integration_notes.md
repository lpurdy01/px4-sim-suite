# QGroundControl CI Integration Notes

## Summary of Findings

## Recent Progress (2025-12-24)
- Provisioning pathway finalized: Qt 6.5.3 declared in `tools/environment_manifest.json` and auto-installed via `env_requirements.py` with doctor validation (temporary pin until 6.10.x metadata stabilises in `aqt`).
- `simtest qgc` subcommands (`build`, `test`, `stub`, `collect`) now generate artifacts under `artifacts/qgc/` and expose headless CTest plus the virtual PX4 handshake.
- Optional CI wiring landed; `run_ci.sh` and the GitHub workflow honour `SIMTEST_ENABLE_QGC`, capture timing metrics alongside QGC logs, and require package construction so QGC tests execute against the installed binary rather than the build tree.
- Headless mission automation flow defined: [docs/patches/qgroundcontrol/headless-mission.patch](docs/patches/qgroundcontrol/headless-mission.patch) introduces the CLI entry point while [tools/simtest](tools/simtest) adds an autoplan helper that logs to [artifacts/qgc/auto_plan.log](artifacts/qgc/auto_plan.log).

### Current status
- `tools/env_requirements.py` now provisions Qt 6.5.3 through `aqt`, keyed off `tools/environment_manifest.json`, and the doctor step verifies `qt-cmake` availability.
- `tools/simtest qgc [build|test|stub|collect]` orchestrates a Debug/Test QGC build, runs `cmake --install` into a dedicated prefix, drives CTest headlessly, executes the installed `QGroundControl --unittest` harness, and runs a scripted handshake against `tools/qgc_virtual_px4.py`, emitting artifacts under `artifacts/qgc/`.
- `tools/run_ci.sh` and the GitHub Actions workflow honour `SIMTEST_ENABLE_QGC`, enabling the optional pipeline and timing metrics when the repository variable is set.
- [tests/qgc_plans/takeoff_land.plan](tests/qgc_plans/takeoff_land.plan) is the canonical PX4 SITL mission for CI; [tools/simtest](tools/simtest) autoplan dispatch uploads and executes it through headless QGC using the proposed CLI patch.

### QGC Test Hooks
- QGC enables its unit-test harness when `QGC_BUILD_TESTING=ON`; CMake auto-registers each test through `add_qgc_test`, allowing execution via `ctest` or `QGroundControl --unittest[:<filter>]`.
- The command-line parser recognizes `--unittest` and swaps the main event loop for the unit-test runner, so the same binary supports interactive and automated runs.
- `MockLink` already simulates a PX4 autopilot (heartbeats, parameters, missions, FTP); it is the canonical reference for message cadence when mirroring behaviour from outside the submodule.
- Existing GitHub Actions jobs invoke `xvfb-run ./QGroundControl --simple-boot-test` and `--unittest`, proving the app can exercise GUI-free flows.

### Python Stub Strategy
- Reuse `tools/mavlink_heartbeat.py` as the template for a "virtual PX4" UDP stub. Extend it to send PX4-compliant heartbeats, selected parameter updates, and autopilot version responses by following the logic in `MockLink::run10HzTasks`.
- Headless flow: start Xvfb, launch `QGroundControl --simple-boot-test --log-output --allow-multiple`, then run the stub for ~20 s on UDP 14550. Validate success either by parsing QGC stdout for `activeVehicle` messages or by having the stub assert that QGC requested parameters.
- Dependencies:
  - Install Qt SDK via `aqtinstall` (or cache a prebuilt Qt tree) so we can build a Debug/QGC_BUILD_TESTING=ON binary.
  - Ensure `xvfb`, Mesa, and GStreamer packages match `tools/setup/install-dependencies-debian.sh`; mirror the list in `tools/environment_manifest.json` so `simtest doctor` and the devcontainer remain the single source of truth.

### PX4 + Gazebo Integration
- `simtest run` already bootstraps PX4 SITL and Gazebo; PX4 listens on UDP 14540/14550.
- Start QGC headless under Xvfb using the autoconnect defaults from `AutoConnect.SettingsGroup.json`. Confirm the handshake by capturing QGC stdout and checking PX4 logs for the GCS connection line.
- Preserve artifacts:
  - QGC stdout/stderr logs.
  - Key PX4 log snippets or the full `.ulg` if debugging cross-sides interactions.
  - Optionally, the Python stub log for traceability.

### Stage 8 Scaffold
- Introduce `simtest qgc` with sub-steps:
  1. Run `tools/env_requirements.py install` (augmented manifest) to pull Qt, Xvfb, and other prerequisites.
  2. Configure QGC in Debug mode with `-DQGC_BUILD_TESTING=ON`.
  3. Build QGC (AppImage preferred) and run either `ctest` or targeted `--unittest` invocations.
  4. Execute the Python stub handshake and record logs under `artifacts/qgc/`.
- Extend `tools/run_ci.sh` so it can optionally call `simtest qgc` after the current doctor/build/run sequence (behind an env flag such as `SIMTEST_ENABLE_QGC=1`).
- Update `.github/workflows/simtest-build.yml` with a follow-on job that reuses the devcontainer image, installs Qt via `aqt`, runs the stub, and triggers the SITL+QGC integration check. Cache the Qt install directory (`~/.cache/aqt` or equivalent) to reduce download time.
- Document the knobs (env vars, optional targets) in Stage 8 guidance so agents know how to enable or skip QGC coverage locally and in CI.

## Environment & Packaging Decisions
- CI artifacts should include the AppImage emitted by QGC’s install step; this keeps dependencies self-contained and matches the deployment story for WSL users.
- Align `tools/environment_manifest.json` with QGC’s `install-dependencies-debian.sh` (Qt, GStreamer, SDL, PipeWire, etc.) to avoid drift between manual and automated setups.

## Proposed Task Breakdown
1. **Manifest & Tooling** *(Completed 2025-12-24)*
   - Add Qt/GStreamer/Xvfb requirements to the manifest.
   - Update `env_requirements.py` to support installing Qt via `aqt` (or fetch a prebuilt bundle) and to validate Qt presence during `doctor`.
2. **Build Orchestration** *(Completed 2025-12-24)*
   - Implement `simtest qgc` with subcommands (`build`, `test`, `stub`, `collect`).
   - Ensure outputs land in `artifacts/qgc/` and are referenced in documentation.
3. **Python Stub Prototype** *(Completed 2025-12-24)*
   - Create `tools/qgc_virtual_px4.py` (or similar) and validate against QGC locally with Xvfb.
   - Integrate stub invocation into the new simtest subcommand.
4. **CI Wiring** *(Completed 2025-12-24)*
   - Extend `run_ci.sh` to opt-in to QGC steps via env var.
   - Update GitHub Actions workflow with an additional job (Ubuntu AppImage build + stub test), relying on cached Qt installs.
5. **Documentation & Stage Tracking** *(In Progress)*
   - Record instructions in `docs/stage1-sitl.md` or Stage 8-specific notes.
   - Provide quickstart guidance for Windows users leveraging the AppImage through WSL.

## Outstanding Questions
- Will Qt installs be cached inside the devcontainer image, or do we rely on `aqt` at runtime? (Impacts manifest design.)
- Do we need to sign AppImages or simply archive them for regression triage?
- Should the Python stub also emit SITL telemetry to validate QGC widgets beyond connection state?

### Next Actions
1. Harden the virtual PX4 stub so default CI runs keep heartbeat/parameter validation enabled; capture a PX4+QGC session to tune timing and add assertions for `AUTOPILOT_VERSION`, `MISSION_REQUEST_LIST`, or other handshakes.
2. Validate the “QGC flies PX4” automation path: apply [docs/patches/qgroundcontrol/headless-mission.patch](docs/patches/qgroundcontrol/headless-mission.patch) inside the submodule, exercise [tools/simtest](tools/simtest) autoplan against PX4 SITL, and iterate on mission coverage as needed. Any upstream submission must continue to ship as patches under [docs/patches/qgroundcontrol](docs/patches/qgroundcontrol) per [AGENTS.md](docs/AGENTS.md).
3. Ensure package construction (AppImage or staged install) happens during `simtest qgc build`, and run all QGC tests against that installed binary instead of relying on ad-hoc binary discovery.
4. Investigate caching strategies for the Qt toolchain (`~/.local/Qt`) to reduce CI cold-start time, possibly via GitHub Actions cache.
5. Extend documentation for human operators (Stage 8 guide) with troubleshooting steps for QGC builds and the new CLI surface; sync remaining notes across Stage 8 references.
6. Monitor artifact growth with AppImage preservation and prune/rotate as required.

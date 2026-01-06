# QGroundControl Unit Test Notes

## Context
- Date: 2025-12-30
- Branch: stage5/minimal-flight-scenario
- Goal: ensure QGroundControl builds, installs, boots headlessly, and executes unit tests via simtest pipeline.

## Actions Completed
1. Cleared prior QGC build cache (rm -rf build/qgc-simtest) to guarantee a clean Debug rebuild.
2. Rebuilt QGC with unit tests enabled using `SIMTEST_QGC_ENABLE_TESTS=1 ./tools/simtest qgc build`.
   - simtest now forces `CMAKE_BUILD_TYPE=Debug` when unit tests are requested, ensuring the QGC AppImage exposes the `--unittest` entry point.
   - AppImage artifacts stored under `build/qgc-simtest/QGroundControl-x86_64.AppImage` and copied to `artifacts/qgc/`.
   - appimagelint still fails to mount (lack of FUSE); warning is non-blocking but captured in build log.
3. Ran the test suite with `SIMTEST_QGC_ENABLE_TESTS=1 ./tools/simtest qgc test`.
   - Simple boot smoke test passed inside Xvfb.
   - Unit tests passed inside Xvfb; logs archived in `artifacts/qgc/qgc-simple-boot-test.log` and `artifacts/qgc/qgc-unittest.log`.
4. Added `tools/run_stage5_qgc_with_px4.sh` to orchestrate PX4 SITL + QGC headless integration.
   - Script waits for PX4 to announce `Ready for takeoff!`, then runs the AppImage under Xvfb for a bounded window (default 45s).
   - Connection confirmed via `INFO  [mavlink] partner IP: 127.0.0.1` in `artifacts/qgc/px4-sitl-console.log`.
   - QGC console output captured in `artifacts/qgc/qgc-sitl-session.log`; timeout exit (124) is expected when the script stops the session.

## CI Follow-Up
- Promote the `SIMTEST_QGC_ENABLE_TESTS=1 ./tools/simtest qgc build test` workflow into CI once runner capacity is confirmed (Qt6, Xvfb, appimagetool availability required).
- Address appimagelint mount failure (likely needs FUSE or `--appimage-extract` fallback) before gating CI on lint success.
- Confirm artifact retention policy captures both AppImage and test logs for post-run inspection.
- Evaluate adding `./tools/run_stage5_qgc_with_px4.sh` to CI smoke tests once runners can host Gazebo; ensure cleanup handles lingering `gz` processes and that log files remain under the 50MB sync limit.

## Next Steps
- Integrate PX4 SITL + Gazebo with the installed QGC build to prove end-to-end control link.
- Document the observed Debug build requirement inside simtest README or stage notes once the workflow stabilizes.
- Investigate automating mission scripts (takeoff/land) using MAVLink tooling to validate closed-loop control during the SITL+QGC window.

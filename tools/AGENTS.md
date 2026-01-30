# Tooling Agents Guidance

- Use the repository-level AGENTS.md for global policies.
- Do **not** create Python virtual environments under `tools/`; the devcontainer already pins dependencies. Install Python packages system-wide (or with `pip --user`) when scripting support is needed.

## Simulation Scripts

### Entry Points

1. **Automated Testing (CI/CD)**
   - `./tools/simtest run` - Headless automated flight test
   - Used by: GitHub Actions pipeline
   - Headless: yes, Scenario: takeoff_land, Duration: 45s default

2. **GUI with Automated Scenario**
   - `./tools/run_sim_with_gui.sh [model] [duration] [scenario] [delay]`
   - Purpose: Visual observation of automated flight tests
   - Headless: no, Scenario: configurable (default: takeoff_land)
   - Example: `./tools/run_sim_with_gui.sh x500 120 takeoff_land 12`
   - Run without scenario: `./tools/run_sim_with_gui.sh x500 60 none`

3. **GUI with Manual Control (QGroundControl)**
   - `./tools/run_sim_with_qgc.sh [model] [world]`
   - Purpose: Manual flying with QGC virtual joystick
   - Headless: no, Scenario: none (user controls)
   - World: lawn (default), see GAZEBO_WORLDS.md for options
   - Example: `./tools/run_sim_with_qgc.sh x500 lawn`

4. **QGroundControl Standalone**
   - `./tools/launch_qgc.sh`
   - Purpose: Launch QGC alone (useful if sim already running)
   - Builds QGC if not present

5. **Cleanup Utility**
   - `./tools/cleanup_sim.sh`
   - Purpose: Kill all lingering sim processes (PX4, Gazebo, QGC)
   - Use after: Crashed sim, interrupted tests, stuck processes

### Python Scripts

- `./tools/simple_takeoff.py` - Example MAVLink script for arm/takeoff command sequence
  - Usage: `python3 tools/simple_takeoff.py --altitude 3.0 --link udp:127.0.0.1:14550`

### Documentation

- `./tools/GAZEBO_WORLDS.md` - Reference for available Gazebo world environments with visual comparisons
- `./tools/setup_virtual_joystick.md` - Guide for QGC virtual joystick configuration and usage

## Common Workflows

### Run automated test with GUI visible
```bash
./tools/run_sim_with_gui.sh x500 120 takeoff_land
```

### Manually fly the drone with QGC
```bash
./tools/run_sim_with_qgc.sh x500 lawn
# In QGC: Enable virtual joystick in Application Settings → General
# Set parameter COM_RC_IN_MODE = 1 in Vehicle Setup → Parameters
# Arm and fly using virtual thumbsticks in Fly View
```

### Run simulation without any scenario (just sit idle)
```bash
./tools/run_sim_with_gui.sh x500 0 none
```

### Clean up after crashed simulation
```bash
./tools/cleanup_sim.sh
```

### Test different world environments
```bash
./tools/run_sim_with_qgc.sh x500 baylands  # Park with water
./tools/run_sim_with_qgc.sh x500 rover     # Large green field
./tools/run_sim_with_qgc.sh x500 default   # Basic grey (lowest CPU)
```

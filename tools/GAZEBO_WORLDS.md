# Gazebo World Options

This document describes the available Gazebo world environments and how to use them.

## Quick Start

To use a specific world with the simulation:

```bash
# Default (lawn world - green grass with clouds)
./tools/run_sim_with_qgc.sh

# Specify a different world
./tools/run_sim_with_qgc.sh x500 baylands
./tools/run_sim_with_qgc.sh x500 default
```

## Available Worlds

All worlds are located in `/workspaces/px4-sim-suite/px4-gazebo-models/worlds/`

### Recommended for Visual Appeal (Low CPU)

#### **lawn** (Default - Recommended)
- **Visual**: Green grass ground plane, animated clouds
- **Ground Color**: Grass green (0.6, 1.0, 0.25)
- **Sky**: Clouds enabled (speed: 12)
- **Grid**: Enabled
- **CPU Load**: Low (~5-8% more than default)
- **Best For**: General flying, matches QGC satellite view aesthetic

#### **baylands**
- **Visual**: Outdoor park environment with water features
- **Sky**: Dynamic clouds
- **3D Models**: External "baylands" park and "Coast Water" models from Gazebo Fuel
- **Ambient**: Pinkish atmospheric tint (0.8, 0.5, 1)
- **Location**: San Francisco Bay Area coordinates
- **CPU Load**: Medium
- **Best For**: Realistic outdoor flying

### Other Worlds

#### **default**
- **Visual**: Basic grey ground plane
- **Ambient**: 0.4 0.4 0.4, Background: 0.7 0.7 0.7
- **Shadows**: Enabled
- **CPU Load**: Lowest
- **Best For**: Minimal resource usage, testing

#### **rover**
- **Visual**: Green ground plane (same as lawn)
- **Size**: 400x400m
- **Grid**: Enabled
- **CPU Load**: Low
- **Best For**: Large area operations, ground vehicles

#### **aruco**
- **Visual**: Semi-transparent ground (0.8 alpha)
- **Includes**: ArUco marker for visual localization
- **CPU Load**: Low
- **Best For**: Computer vision testing, marker tracking

#### **kthspacelab**
- **Visual**: Indoor lab environment with walls
- **Ambient**: Bright (0.8 0.8 0.8)
- **Background**: Dark (0.05 0.05 0.07)
- **CPU Load**: Low-Medium
- **Best For**: Indoor flight testing

#### **underwater**
- **Visual**: Cyan/blue underwater environment
- **Ambient**: Cyan (0.0, 1.0, 1.0)
- **Background**: Blue (0.0, 0.7, 0.8)
- **3D Models**: "Portuguese Ledge" underwater terrain
- **CPU Load**: Medium
- **Best For**: UUV/underwater vehicle simulation

#### **forest**
- **Visual**: Trees and vegetation
- **3D Models**: Oak trees, Pine trees, grass patches
- **CPU Load**: Medium-High
- **Best For**: Obstacle avoidance testing

#### **windy**
- **Visual**: Standard appearance with wind simulation
- **Wind**: 5 m/s linear velocity
- **CPU Load**: Low
- **Best For**: Testing flight stability in wind

#### **walls**
- **Visual**: Obstacle course with 4 walls
- **CPU Load**: Low-Medium
- **Best For**: Collision avoidance testing

#### **moving_platform**
- **Visual**: Dynamic platform for landing
- **CPU Load**: Low-Medium
- **Best For**: Landing/docking scenarios

#### **frictionless**
- **Visual**: Low friction surface
- **CPU Load**: Low
- **Best For**: Physics testing

## World Features Comparison

| World | Ground Color | Clouds | 3D Objects | CPU Load | QGC Visual Match |
|-------|-------------|--------|------------|----------|------------------|
| **lawn** | Green grass | Yes | None | Low | ★★★★★ |
| baylands | Varied | Yes | Park + Water | Medium | ★★★★☆ |
| rover | Green grass | No | None | Low | ★★★★☆ |
| default | Grey | No | None | Lowest | ★★☆☆☆ |
| aruco | Transparent | No | Marker | Low | ★★★☆☆ |
| kthspacelab | Dark | No | Walls | Low-Med | ★★☆☆☆ |
| underwater | Cyan/Blue | No | Terrain | Medium | ★☆☆☆☆ |
| forest | Brown | No | Trees | Med-High | ★★★☆☆ |

## Visual Enhancement Options

### Sky & Atmosphere
- **Clouds**: Animated clouds add realism with minimal CPU cost
- **Ambient Lighting**: Brighter = better visibility from above
- **Background Color**: Light blue/grey matches outdoor sky

### Ground Plane
- **Green grass** (lawn/rover): Best match for QGC satellite imagery
- **Grey** (default): Minimal, industrial look
- **Textured** (requires custom materials): Higher CPU cost

### Lighting
- **Shadows**: Enabled = more realistic, slight CPU cost
- **Dual lights** (lawn): Better visibility, minimal extra cost
- **Single light** (default): Most efficient

## Custom World Configuration

To create a custom world with specific visual settings:

1. Copy an existing world file:
   ```bash
   cp /workspaces/px4-sim-suite/px4-gazebo-models/worlds/lawn.sdf \
      /workspaces/px4-sim-suite/px4-gazebo-models/worlds/custom.sdf
   ```

2. Edit the world name and visual properties:
   ```xml
   <world name="custom">
     <scene>
       <ambient>0.95 0.95 0.95 1</ambient>  <!-- Bright ambient -->
       <background>0.3 0.3 0.3 1</background>  <!-- Blue-grey sky -->
       <sky>
         <clouds><speed>12</speed></clouds>  <!-- Animated clouds -->
       </sky>
     </scene>
     <model name="ground_plane">
       <visual>
         <material>
           <diffuse>0.6 1.0 0.25 0.5</diffuse>  <!-- Green grass -->
         </material>
       </visual>
     </model>
   </world>
   ```

3. Use it:
   ```bash
   ./tools/run_sim_with_qgc.sh x500 custom
   ```

## Performance Tips

1. **Disable shadows** if CPU constrained: `<shadows>false</shadows>`
2. **Use single light** instead of multiple directional lights
3. **Avoid 3D models** unless necessary (forest, yosemite)
4. **Keep cloud speed reasonable**: 12 is standard, higher = more CPU
5. **Green ground plane** is same CPU cost as grey (just color change)

## Troubleshooting

### World not loading
- Check world file exists in `px4-gazebo-models/worlds/`
- Verify `GZ_SIM_RESOURCE_PATH` includes worlds directory
- Check for syntax errors in .sdf file

### Performance issues
- Try `default` world (lowest resource usage)
- Disable shadows and clouds
- Reduce number of lights
- Remove 3D models

### Visual appearance doesn't match QGC
- Use `lawn` world for green grass
- Enable clouds for sky animation
- Increase ambient lighting for brighter overhead view

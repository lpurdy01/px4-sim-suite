# Virtual Joystick Setup Guide

## QGroundControl Virtual Joystick (On-Screen Thumbsticks)

### Enable Virtual Joystick in QGC:

1. Launch QGroundControl:
   ```bash
   ./tools/launch_qgc.sh
   ```

2. Go to **Application Settings** (gear icon, top toolbar)

3. Navigate to **General** tab

4. Enable **"Virtual joystick"** checkbox

5. The virtual thumbsticks will appear in the Fly View

### Configure PX4 for Joystick Input:

You need to tell PX4 to accept joystick/manual control input:

```bash
# In the PX4 console (pxh>), set this parameter:
param set COM_RC_IN_MODE 1
param save
```

Or via QGC:
1. Go to **Vehicle Setup** → **Parameters**
2. Search for `COM_RC_IN_MODE`
3. Set to `1` (Joystick/No RC Checks)
4. Restart the vehicle

### Using the Virtual Joystick:

Once enabled, you'll see two on-screen thumbsticks in the Fly View:

- **Left stick**: Throttle (up/down) and Yaw (left/right)
- **Right stick**: Pitch (up/down) and Roll (left/right)

The virtual joystick sends MAVLink MANUAL_CONTROL messages to PX4.

## Physical Joystick/Gamepad Support

QGC also supports physical USB joysticks/gamepads via SDL3:

**Supported controllers:**
- Sony PS3/PS4 DualShock
- Xbox controllers
- Logitech F310/F710
- Logitech Extreme 3D Pro
- FrSky Taranis transmitters

**Setup:**
1. Connect USB gamepad
2. Open QGC → **Vehicle Setup** → **Joystick**
3. Calibrate axes via **Calibrate** tab
4. Configure button actions

## Custom Python Virtual Joystick

You can also create custom joystick scripts using pymavlink to send MANUAL_CONTROL messages.

See `tools/simple_takeoff.py` for an example of sending MAVLink commands.

## Troubleshooting

### "No connection to GCS" warning:
- Ensure virtual joystick is enabled or a MAVLink GCS is connected
- The virtual joystick acts as a GCS connection

### Vehicle won't arm:
- Check `COM_RC_IN_MODE = 1` is set
- Verify MAVLink connection is active
- Try stick gesture: Move left stick to bottom-right corner to arm

### Virtual joystick not appearing:
- Make sure you're in **Fly View** (not Plan or Setup)
- Check that "Virtual joystick" is enabled in Application Settings → General

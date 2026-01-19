#!/usr/bin/env python3
"""Simple script to command PX4 to arm and takeoff via MAVLink"""

import time
import argparse
from pymavlink import mavutil

def main():
    parser = argparse.ArgumentParser(description="Simple arm and takeoff")
    parser.add_argument("--altitude", type=float, default=3.0, help="Takeoff altitude in meters")
    parser.add_argument("--link", default="udp:127.0.0.1:14550", help="MAVLink connection")
    args = parser.parse_args()

    print(f"Connecting to {args.link}...")
    master = mavutil.mavlink_connection(args.link, source_system=255, source_component=190)

    # Wait for heartbeat
    print("Waiting for heartbeat...")
    master.wait_heartbeat()
    print(f"Connected to system {master.target_system}, component {master.target_component}")

    # Send heartbeat to establish GCS connection
    print("Sending GCS heartbeat...")
    for _ in range(3):
        master.mav.heartbeat_send(
            mavutil.mavlink.MAV_TYPE_GCS,
            mavutil.mavlink.MAV_AUTOPILOT_INVALID,
            0, 0,
            mavutil.mavlink.MAV_STATE_ACTIVE
        )
        time.sleep(0.5)

    # Disable data link loss failsafe
    print("Disabling NAV_DLL_ACT...")
    master.mav.param_set_send(
        master.target_system,
        master.target_component,
        b"NAV_DLL_ACT",
        0.0,
        mavutil.mavlink.MAV_PARAM_TYPE_INT32
    )
    time.sleep(1)

    # Arm
    print("Arming...")
    master.mav.command_long_send(
        master.target_system,
        master.target_component,
        mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
        0,  # confirmation
        1,  # arm
        0, 0, 0, 0, 0, 0
    )

    # Wait for arm acknowledgment
    ack = master.recv_match(type='COMMAND_ACK', blocking=True, timeout=5)
    if ack and ack.result == mavutil.mavlink.MAV_RESULT_ACCEPTED:
        print("Armed successfully!")
    else:
        print(f"Arm failed: {ack}")
        return 1

    time.sleep(2)

    # Takeoff
    print(f"Taking off to {args.altitude}m...")
    master.mav.command_long_send(
        master.target_system,
        master.target_component,
        mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
        0,
        0, 0, 0, 0,
        float('nan'), float('nan'),  # current lat/lon
        args.altitude
    )

    # Monitor altitude
    print("Monitoring altitude...")
    while True:
        msg = master.recv_match(type='GLOBAL_POSITION_INT', blocking=True, timeout=1)
        if msg:
            alt = msg.relative_alt / 1000.0
            print(f"  Altitude: {alt:.2f}m", end='\r')
            if alt >= args.altitude * 0.9:
                print(f"\n✓ Reached target altitude: {alt:.2f}m")
                break

        # Keep sending heartbeat
        master.mav.heartbeat_send(
            mavutil.mavlink.MAV_TYPE_GCS,
            mavutil.mavlink.MAV_AUTOPILOT_INVALID,
            0, 0,
            mavutil.mavlink.MAV_STATE_ACTIVE
        )

    print("\nHovering... (Press Ctrl+C to land)")
    try:
        while True:
            master.mav.heartbeat_send(
                mavutil.mavlink.MAV_TYPE_GCS,
                mavutil.mavlink.MAV_AUTOPILOT_INVALID,
                0, 0,
                mavutil.mavlink.MAV_STATE_ACTIVE
            )
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\nLanding...")
        master.mav.command_long_send(
            master.target_system,
            master.target_component,
            mavutil.mavlink.MAV_CMD_NAV_LAND,
            0,
            0, 0, 0, 0,
            float('nan'), float('nan'), 0
        )
        print("Land command sent. Closing connection...")
        time.sleep(2)

    master.close()
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())

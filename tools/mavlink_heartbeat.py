#!/usr/bin/env python3
"""Minimal MAVLink helper that spoofs a GCS for headless sim runs."""

from __future__ import annotations

import argparse
import sys
import time

from pymavlink import mavutil


MAV_TYPE_GCS = mavutil.mavlink.MAV_TYPE_GCS
MAV_AUTOPILOT_INVALID = mavutil.mavlink.MAV_AUTOPILOT_INVALID
MAV_STATE_ACTIVE = mavutil.mavlink.MAV_STATE_ACTIVE
MAV_PARAM_TYPE_INT32 = mavutil.mavlink.MAV_PARAM_TYPE_INT32


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-host", default="127.0.0.1", help="PX4 UDP host")
    parser.add_argument("--target-port", type=int, default=18570, help="PX4 UDP port")
    parser.add_argument(
        "--source-port",
        type=int,
        default=14550,
        help="Local UDP port to mimic a GCS",
    )
    parser.add_argument("--rate", type=float, default=1.0, help="Heartbeat frequency (Hz)")
    parser.add_argument("--duration", type=float, default=30.0, help="Total runtime (seconds)")
    parser.add_argument("--sysid", type=int, default=255, help="MAVLink system id")
    parser.add_argument("--compid", type=int, default=190, help="MAVLink component id")

    args = parser.parse_args(argv)

    interval = 1.0 / max(args.rate, 0.1)
    end_time = time.monotonic() + max(args.duration, interval)
    param_stop = time.monotonic() + 2.0

    link = mavutil.mavlink_connection(
        f"udpout:{args.target_host}:{args.target_port}",
        source_system=args.sysid,
        source_component=args.compid,
        udp_bind_port=args.source_port,
    )

    try:
        while time.monotonic() < end_time:
            now = time.monotonic()

            if now < param_stop:
                link.mav.param_set_send(
                    1,
                    1,
                    b"NAV_DLL_ACT",
                    float(0),
                    MAV_PARAM_TYPE_INT32,
                )
                time.sleep(0.2)
                continue

            link.mav.heartbeat_send(
                MAV_TYPE_GCS,
                MAV_AUTOPILOT_INVALID,
                0,
                0,
                MAV_STATE_ACTIVE,
            )
            time.sleep(interval)
    finally:
        link.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())

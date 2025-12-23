#!/usr/bin/env python3
"""Minimal PX4 SITL scenario: arm, take off, hold, land."""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from typing import Callable, Tuple

from pymavlink import mavutil

MAV_COMP_AUTOPILOT = mavutil.mavlink.MAV_COMP_ID_AUTOPILOT1
HB_TYPE = mavutil.mavlink.MAV_TYPE_GCS
HB_AUTOPILOT = mavutil.mavlink.MAV_AUTOPILOT_INVALID
HB_STATE = mavutil.mavlink.MAV_STATE_ACTIVE
NAV_DLL_PARAM = b"NAV_DLL_ACT"
NAV_DLL_PARAM_TYPE = mavutil.mavlink.MAV_PARAM_TYPE_INT32
SUMMARY_PATH = os.getenv("SIMTEST_SCENARIO_RESULT")

class HeartbeatMaintainer:
    def __init__(self, master: mavutil.mavfile, rate_hz: float) -> None:
        self.master = master
        self.interval = 1.0 / max(rate_hz, 0.2)
        self._next_send = 0.0

    def tick(self) -> None:
        now = time.time()
        if now >= self._next_send:
            self.master.mav.heartbeat_send(
                HB_TYPE,
                HB_AUTOPILOT,
                0,
                0,
                HB_STATE,
            )
            self._next_send = now + self.interval


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PX4 takeoff/land scenario")
    parser.add_argument(
        "--link",
        default="udp:127.0.0.1:14550",
        help="MAVLink connection string (default: udp:127.0.0.1:14550)",
    )
    parser.add_argument(
        "--altitude",
        type=float,
        default=3.0,
        help="Target relative altitude in meters",
    )
    parser.add_argument(
        "--hold",
        type=float,
        default=4.0,
        help="Hold duration at cruise altitude in seconds",
    )
    parser.add_argument(
        "--pre-arm-wait",
        type=float,
        default=6.0,
        help="Seconds to wait after connection before arming",
    )
    parser.add_argument(
        "--post-land",
        type=float,
        default=3.0,
        help="Heartbeat duration after landing (seconds)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=60.0,
        help="Overall scenario timeout in seconds",
    )
    parser.add_argument(
        "--heartbeat-rate",
        type=float,
        default=1.0,
        help="Heartbeat frequency in Hz",
    )
    parser.add_argument("--sysid", type=int, default=255, help="MAVLink system id")
    parser.add_argument("--compid", type=int, default=190, help="MAVLink component id")
    return parser.parse_args()


def write_summary(status: str, **fields: float | str | int) -> None:
    if not SUMMARY_PATH:
        return
    payload = {"status": status, **fields}
    try:
        with open(SUMMARY_PATH, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, separators=(",", ":"))
    except OSError as error:  # best effort only
        print(f"[scenario] warning: failed to write summary ({error})")


def wait_heartbeat(master: mavutil.mavfile, heartbeat: HeartbeatMaintainer, timeout: float) -> Tuple[int, int]:
    deadline = time.time() + timeout
    while time.time() < deadline:
        heartbeat.tick()
        message = master.recv_match(type="HEARTBEAT", blocking=True, timeout=0.5)
        if message:
            master.target_system = message.get_srcSystem() or 1
            master.target_component = message.get_srcComponent() or MAV_COMP_AUTOPILOT
            return master.target_system, master.target_component
    raise TimeoutError("heartbeat timeout")


def send_nav_dll_act(master: mavutil.mavfile, heartbeat: HeartbeatMaintainer) -> None:
    target_system = master.target_system or 1
    target_component = master.target_component or MAV_COMP_AUTOPILOT
    for _ in range(3):
        heartbeat.tick()
        master.mav.param_set_send(
            target_system,
            target_component,
            NAV_DLL_PARAM,
            float(0),
            NAV_DLL_PARAM_TYPE,
        )
        time.sleep(0.2)


def send_command(
    master: mavutil.mavfile,
    heartbeat: HeartbeatMaintainer,
    command: int,
    params: Tuple[float, ...],
    timeout: float = 8.0,
    expect_ack: bool = True,
) -> None:
    master.mav.command_long_send(
        master.target_system,
        master.target_component,
        command,
        0,
        *params,
    )

    deadline = time.time() + timeout
    while time.time() < deadline:
        heartbeat.tick()
        ack = master.recv_match(type="COMMAND_ACK", blocking=True, timeout=0.5)
        if ack and ack.command == command:
            if ack.result == mavutil.mavlink.MAV_RESULT_ACCEPTED:
                return
            if ack.result == mavutil.mavlink.MAV_RESULT_IN_PROGRESS:
                continue
            if ack.result == mavutil.mavlink.MAV_RESULT_TEMPORARILY_REJECTED:
                time.sleep(0.5)
                continue
            raise RuntimeError(f"command {command} rejected with result {ack.result}")
    if expect_ack:
        raise TimeoutError(f"No COMMAND_ACK for {command}")


def wait_relative_altitude(
    master: mavutil.mavfile,
    heartbeat: HeartbeatMaintainer,
    target_alt: float,
    comparator: Callable[[float, float], bool],
    timeout: float,
) -> float:
    deadline = time.time() + timeout
    while time.time() < deadline:
        heartbeat.tick()
        message = master.recv_match(type="GLOBAL_POSITION_INT", blocking=True, timeout=0.5)
        if message:
            altitude = message.relative_alt / 1000.0
            if comparator(altitude, target_alt):
                return altitude
    raise TimeoutError("altitude check timed out")


def hold_with_heartbeat(heartbeat: HeartbeatMaintainer, duration: float) -> None:
    end_time = time.time() + duration
    while time.time() < end_time:
        heartbeat.tick()
        time.sleep(0.2)


def main() -> int:
    args = parse_args()

    start_time = time.time()
    master = mavutil.mavlink_connection(
        args.link,
        autoreconnect=True,
        source_system=args.sysid,
        source_component=args.compid,
    )
    heartbeat = HeartbeatMaintainer(master, args.heartbeat_rate)

    wait_heartbeat(master, heartbeat, timeout=min(30.0, args.timeout))
    send_nav_dll_act(master, heartbeat)

    if args.pre_arm_wait > 0:
        hold_with_heartbeat(heartbeat, args.pre_arm_wait)

    print("[scenario] Heartbeat received; arming...")
    send_command(
        master,
        heartbeat,
        mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
        (1, 0, 0, 0, 0, 0, 0),
        timeout=10.0,
    )

    wait_relative_altitude(
        master,
        heartbeat,
        0.2,
        lambda alt, target: alt <= target,
        timeout=10.0,
    )

    print(f"[scenario] Commanding takeoff to {args.altitude:.1f} m")
    send_command(
        master,
        heartbeat,
        mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
        (0, 0, 0, 0, math.nan, math.nan, args.altitude),
        timeout=15.0,
    )

    achieved_alt = wait_relative_altitude(
        master,
        heartbeat,
        args.altitude * 0.8,
        lambda alt, target: alt >= target,
        timeout=args.timeout,
    )
    print(f"[scenario] Hovering at {achieved_alt:.2f} m; holding for {args.hold:.1f} s")
    hold_with_heartbeat(heartbeat, args.hold)

    print("[scenario] Commanding land")
    send_command(
        master,
        heartbeat,
        mavutil.mavlink.MAV_CMD_NAV_LAND,
        (0, 0, 0, 0, math.nan, math.nan, 0),
        timeout=15.0,
        expect_ack=False,
    )

    landing_alt = wait_relative_altitude(
        master,
        heartbeat,
        0.3,
        lambda alt, target: alt <= target,
        timeout=args.timeout,
    )
    elapsed = time.time() - start_time
    print(f"[scenario] Landing confirmed (alt {landing_alt:.2f} m); elapsed {elapsed:.1f} s")

    write_summary(
        "success",
        target_altitude_m=round(args.altitude, 2),
        achieved_altitude_m=round(achieved_alt, 2),
        landing_altitude_m=round(landing_alt, 2),
        hold_duration_s=round(args.hold, 2),
        elapsed_s=round(elapsed, 2),
    )

    if args.post_land > 0:
        hold_with_heartbeat(heartbeat, args.post_land)

    master.close()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except TimeoutError as error:
        write_summary("timeout", error=str(error))
        print(f"[scenario] timeout: {error}")
        sys.exit(2)
    except RuntimeError as error:
        write_summary("failure", error=str(error))
        print(f"[scenario] failure: {error}")
        sys.exit(3)
    except Exception as error:  # pylint: disable=broad-except
        write_summary("unexpected", error=str(error))
        print(f"[scenario] unexpected: {error}")
        sys.exit(4)

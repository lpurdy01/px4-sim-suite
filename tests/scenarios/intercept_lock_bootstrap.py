#!/usr/bin/env python3
"""Stage-5 bootstrap scenario that keeps a GCS heartbeat lock without flying."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

from pymavlink import mavutil

MAV_COMP_AUTOPILOT = mavutil.mavlink.MAV_COMP_ID_AUTOPILOT1
HB_TYPE = mavutil.mavlink.MAV_TYPE_GCS
HB_AUTOPILOT = mavutil.mavlink.MAV_AUTOPILOT_INVALID
HB_STATE = mavutil.mavlink.MAV_STATE_ACTIVE
SUMMARY_PATH = os.getenv("SIMTEST_SCENARIO_RESULT")


class HeartbeatMaintainer:
    def __init__(self, master: mavutil.mavfile, rate_hz: float) -> None:
        self.master = master
        self.interval = 1.0 / max(rate_hz, 0.2)
        self._next_send = 0.0

    def tick(self) -> bool:
        now = time.time()
        if now >= self._next_send:
            self.master.mav.heartbeat_send(HB_TYPE, HB_AUTOPILOT, 0, 0, HB_STATE)
            self._next_send = now + self.interval
            return True
        return False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PX4 intercept lock bootstrap scenario")
    parser.add_argument(
        "--link",
        default="udp:127.0.0.1:14550",
        help="MAVLink connection string (default: udp:127.0.0.1:14550)",
    )
    parser.add_argument(
        "--heartbeat-rate",
        type=float,
        default=2.0,
        help="Heartbeat frequency in Hz",
    )
    parser.add_argument(
        "--bootstrap-seconds",
        type=float,
        default=18.0,
        help="How long to keep the heartbeat lock active",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="Connection timeout waiting for first heartbeat",
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


def wait_for_px4_heartbeat(master: mavutil.mavfile, timeout: float) -> tuple[int, int]:
    deadline = time.time() + timeout
    while time.time() < deadline:
        message = master.recv_match(type="HEARTBEAT", blocking=True, timeout=0.5)
        if message:
            system_id = message.get_srcSystem() or 1
            component_id = message.get_srcComponent() or MAV_COMP_AUTOPILOT
            master.target_system = system_id
            master.target_component = component_id
            return system_id, component_id
    raise TimeoutError("heartbeat timeout")


def run_bootstrap(heartbeat: HeartbeatMaintainer, seconds: float) -> int:
    sent = 0
    deadline = time.time() + max(0.0, seconds)
    while time.time() < deadline:
        if heartbeat.tick():
            sent += 1
        time.sleep(0.1)
    return sent


def main() -> int:
    args = parse_args()

    started = time.time()
    master = mavutil.mavlink_connection(
        args.link,
        autoreconnect=True,
        source_system=args.sysid,
        source_component=args.compid,
    )

    system_id, component_id = wait_for_px4_heartbeat(master, timeout=args.timeout)
    print(f"[scenario] PX4 heartbeat detected from sys={system_id} comp={component_id}")

    heartbeat = HeartbeatMaintainer(master, rate_hz=args.heartbeat_rate)
    sent = run_bootstrap(heartbeat, args.bootstrap_seconds)

    elapsed = time.time() - started
    print(
        f"[scenario] Bootstrap complete; sent {sent} heartbeats in {elapsed:.1f}s (no motion commands issued)"
    )

    write_summary(
        "success",
        mode="bootstrap",
        target_system=system_id,
        target_component=component_id,
        heartbeat_rate_hz=round(args.heartbeat_rate, 2),
        bootstrap_seconds=round(args.bootstrap_seconds, 2),
        heartbeats_sent=sent,
        elapsed_s=round(elapsed, 2),
    )

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

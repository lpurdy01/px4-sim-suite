#!/usr/bin/env python3
"""Minimal PX4-like MAVLink stub to exercise QGC handshakes."""

from __future__ import annotations

import argparse
import logging
import sys
import time
from dataclasses import dataclass
from typing import Tuple

from pymavlink import mavutil


@dataclass(frozen=True)
class Parameter:
    name: str
    value: float
    param_type: int


PARAMETERS: Tuple[Parameter, ...] = (
    Parameter("SYS_AUTOSTART", 4010.0, mavutil.mavlink.MAV_PARAM_TYPE_INT32),
    Parameter("MPC_XY_VEL_MAX", 12.0, mavutil.mavlink.MAV_PARAM_TYPE_REAL32),
    Parameter("COM_DISARM_LAND", 5.0, mavutil.mavlink.MAV_PARAM_TYPE_REAL32),
)

HEARTBEAT_INTERVAL = 0.5
STATUS_INTERVAL = 2.5


class VirtualPX4:
    def __init__(self, args: argparse.Namespace) -> None:
        self._args = args
        self._link = mavutil.mavlink_connection(
            f"udp:{args.bind_host}:{args.bind_port}",
            source_system=args.sysid,
            source_component=args.compid,
        )
        # Prime the UDP server socket with QGC as a known client so heartbeats
        # reach it before the first inbound packet arrives.
        target = (args.target_host, args.target_port)
        self._link.clients.add(target)
        self._link.clients_last_alive[target] = time.time()
        self._gcs_heartbeat_seen = False
        self._param_request_seen = False
        self._logger = logging.getLogger("virtual_px4")

    def run(self) -> None:
        end_time = time.monotonic() + max(self._args.duration, HEARTBEAT_INTERVAL)
        next_heartbeat = time.monotonic()
        next_status = time.monotonic() + STATUS_INTERVAL

        self._logger.info(
            "virtual PX4 listening for QGC (sysid=%s, compid=%s)",
            self._args.sysid,
            self._args.compid,
        )

        while time.monotonic() < end_time:
            now = time.monotonic()

            if now >= next_heartbeat:
                self._send_heartbeat()
                next_heartbeat = now + max(1.0 / max(self._args.rate, 0.1), HEARTBEAT_INTERVAL)

            if now >= next_status:
                self._send_status()
                next_status = now + STATUS_INTERVAL

            self._poll_messages()
            time.sleep(0.05)

        self._validate()

    def close(self) -> None:
        self._link.close()

    def _send_heartbeat(self) -> None:
        self._link.mav.heartbeat_send(
            mavutil.mavlink.MAV_TYPE_QUADROTOR,
            mavutil.mavlink.MAV_AUTOPILOT_PX4,
            mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
            0,
            mavutil.mavlink.MAV_STATE_ACTIVE,
        )

    def _send_status(self) -> None:
        self._link.mav.statustext_send(
            mavutil.mavlink.MAV_SEVERITY_INFO,
            b"simulated PX4 ready",
        )

    def _send_autopilot_version(self) -> None:
        version = mavutil.mavlink.mavlink_version_to_int(1, 14, 0)
        self._link.mav.autopilot_version_send(
            mavutil.mavlink.MAV_PROTOCOL_CAPABILITY_PARAM_FLOAT | mavutil.mavlink.MAV_PROTOCOL_CAPABILITY_MISSION_INT,
            version,
            version,
            0,
            0,
            0,
            0,
            bytes(8),
            bytes(8),
        )

    def _send_params(self) -> None:
        total = len(PARAMETERS)
        for index, param in enumerate(PARAMETERS):
            name_bytes = param.name.encode("ascii")
            self._link.mav.param_value_send(
                name_bytes,
                float(param.value),
                param.param_type,
                total,
                index,
            )

    def _poll_messages(self) -> None:
        message = self._link.recv_match(blocking=False, timeout=0)
        if not message:
            return

        msg_type = message.get_type()
        self._logger.debug("received %s", msg_type)

        if msg_type == "HEARTBEAT" and getattr(message, "type", None) == mavutil.mavlink.MAV_TYPE_GCS:
            self._gcs_heartbeat_seen = True
        elif msg_type == "PARAM_REQUEST_LIST":
            self._param_request_seen = True
            self._logger.info("QGC requested full parameter list")
            self._send_params()
        elif msg_type == "PARAM_REQUEST_READ":
            self._param_request_seen = True
            requested = getattr(message, "param_id", b"")
            self._logger.info("QGC requested parameter %s", requested)
            self._send_params()
        elif msg_type == "COMMAND_LONG" and getattr(message, "command", None) == mavutil.mavlink.MAV_CMD_REQUEST_AUTOPILOT_CAPABILITIES:
            self._logger.info("QGC requested autopilot capabilities")
            self._send_autopilot_version()

    def _validate(self) -> None:
        missing: list[str] = []
        if not self._gcs_heartbeat_seen and not self._args.skip_heartbeat_check:
            missing.append("ground control heartbeat")
        if not self._param_request_seen and not self._args.skip_param_check:
            missing.append("parameter request")
        if missing:
            raise RuntimeError("handshake incomplete: " + ", ".join(missing))


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-host", default="127.0.0.1", help="QGC UDP host")
    parser.add_argument("--target-port", type=int, default=14550, help="QGC UDP port")
    parser.add_argument("--bind-host", default="0.0.0.0", help="local bind address")
    parser.add_argument("--bind-port", type=int, default=14560, help="local UDP port")
    parser.add_argument("--sysid", type=int, default=1, help="autopilot system id")
    parser.add_argument("--compid", type=int, default=1, help="autopilot component id")
    parser.add_argument("--rate", type=float, default=2.0, help="heartbeat rate in Hz")
    parser.add_argument("--duration", type=float, default=25.0, help="runtime duration in seconds")
    parser.add_argument("--log-file", help="optional path to append log output")
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="logging level (e.g. DEBUG, INFO)",
    )
    parser.add_argument(
        "--skip-param-check",
        action="store_true",
        help="do not fail if QGC does not request parameters",
    )
    parser.add_argument(
        "--skip-heartbeat-check",
        action="store_true",
        help="do not fail if QGC heartbeat is not observed",
    )
    return parser.parse_args(argv)


def configure_logging(path: str | None, level: str) -> None:
    handlers = []
    formatter = logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s")

    if path:
        file_handler = logging.FileHandler(path)
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)
    else:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        handlers.append(stream_handler)

    try:
        log_level = getattr(logging, level.upper())
    except AttributeError as exc:  # noqa: B024 (python3.10 compat)
        raise ValueError(f"invalid log level: {level}") from exc

    logging.basicConfig(level=log_level, handlers=handlers)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(list(argv or sys.argv[1:]))
    configure_logging(args.log_file, args.log_level)

    stub = VirtualPX4(args)
    try:
        stub.run()
    except Exception as exc:  # noqa: BLE001
        logging.getLogger("virtual_px4").error("stub failed: %s", exc)
        return 1
    finally:
        stub.close()

    logging.getLogger("virtual_px4").info("handshake complete")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

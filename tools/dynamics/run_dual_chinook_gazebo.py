#!/usr/bin/env python3.12
"""Replay the dual Chinook throttle scenario directly into Gazebo."""
from __future__ import annotations

import argparse
import csv
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Dict, List

REPO_ROOT = Path(__file__).resolve().parents[2]
GAZEBO_PYTHON_PATH = "/usr/lib/python3/dist-packages"

if GAZEBO_PYTHON_PATH not in sys.path:
    sys.path.append(GAZEBO_PYTHON_PATH)
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.append(str(Path(__file__).resolve().parent))

from dual_chinook_sim import load_descriptor, load_scenario  # type: ignore  # noqa: E402
from gz import transport13  # type: ignore  # noqa: E402
import gz.msgs10.actuators_pb2 as actuators_pb2  # type: ignore  # noqa: E402
import gz.msgs10.pose_v_pb2 as pose_v_pb2  # type: ignore  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--descriptor", required=True, help="Vehicle descriptor YAML path")
    parser.add_argument("--scenario", required=True, help="Scenario YAML path")
    parser.add_argument("--world", required=True, help="SDF world to load in Gazebo")
    parser.add_argument("--output", required=True, help="Destination CSV for command-aligned samples")
    parser.add_argument(
        "--pose-log",
        help="Optional CSV path for high-rate pose samples (defaults to alongside output)",
    )
    parser.add_argument(
        "--command-topic",
        default="/dual_chinook/command/motor_speed",
        help="Gazebo motor command topic",
    )
    parser.add_argument(
        "--pose-topic",
        default="/world/dual_chinook_world/dynamic_pose/info",
        help="Gazebo pose topic to sample",
    )
    parser.add_argument("--model-name", default="dual_chinook", help="Model name to extract from pose topic")
    parser.add_argument("--settle-time", type=float, default=2.0, help="Seconds of zero thrust after scenario")
    parser.add_argument("--gz-bin", default="gz", help="Gazebo executable name")
    parser.add_argument("--log", help="Optional Gazebo stdout/stderr log path")
    parser.add_argument(
        "--topic-timeout",
        type=float,
        default=20.0,
        help="Seconds to wait for Gazebo topics to appear",
    )
    parser.add_argument(
        "--debug-topics",
        action="store_true",
        help="Print topic snapshots while waiting for Gazebo readiness",
    )
    return parser.parse_args()


def wait_for_topic(
    node: transport13.Node,
    topic: str,
    timeout: float,
    gz_proc: subprocess.Popen[bytes] | None,
    debug: bool,
) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        topics = node.topic_list()
        if topic in topics:
            return True
        if debug and topics:
            print(f"Observed topics ({len(topics)}): {sorted(topics)}")
        if gz_proc and gz_proc.poll() is not None:
            break
        time.sleep(0.2)
    return False


def main() -> None:
    args = parse_args()
    descriptor = load_descriptor(args.descriptor)
    scenario = load_scenario(args.scenario)
    dt = 1.0 / scenario.sample_rate_hz

    world_path = str(Path(args.world).resolve())
    log_file = open(args.log, "w") if args.log else subprocess.DEVNULL
    gz_cmd = [args.gz_bin, "sim", "-s", "-r", world_path]
    gz_proc = subprocess.Popen(gz_cmd, cwd=REPO_ROOT, stdout=log_file, stderr=log_file)

    node = transport13.Node()
    if not wait_for_topic(node, args.pose_topic, args.topic_timeout, gz_proc, args.debug_topics):
        gz_proc.terminate()
        raise RuntimeError(f"Topic {args.pose_topic} not available")

    pose_lock = threading.Lock()
    pose_event = threading.Event()
    pose_samples: List[Dict[str, float]] = []
    latest_pose = {"sim_time": 0.0, "altitude": float(descriptor.initial_position[2])}

    def pose_callback(msg: pose_v_pb2.Pose_V) -> None:
        stamp = msg.header.stamp
        sim_time = float(stamp.sec) + float(stamp.nsec) * 1e-9
        target_altitude = None
        for pose in msg.pose:
            if pose.name == args.model_name:
                target_altitude = float(pose.position.z)
                break
        if target_altitude is None:
            return
        with pose_lock:
            latest_pose["sim_time"] = sim_time
            latest_pose["altitude"] = target_altitude
            pose_samples.append({"sim_time": sim_time, "altitude": target_altitude})
        pose_event.set()

    node.subscribe(pose_v_pb2.Pose_V, args.pose_topic, pose_callback)
    if not pose_event.wait(timeout=args.topic_timeout):
        gz_proc.terminate()
        raise RuntimeError("No pose messages received")

    actuator_type = actuators_pb2.Actuators.DESCRIPTOR.full_name
    publisher = node.advertise(args.command_topic, actuators_pb2.Actuators)

    def publish_command(velocities: List[float]) -> None:
        msg = actuators_pb2.Actuators()
        msg.velocity.extend(velocities)
        if not publisher.publish_raw(msg.SerializeToString(), actuator_type):
            raise RuntimeError("Failed to publish actuator command")

    command_rows: List[Dict[str, float]] = []
    total_steps = int(scenario.duration / dt) + 1
    wall_start = time.perf_counter()

    try:
        for step in range(total_steps):
            sim_time = step * dt
            throttle = scenario.throttle_at(sim_time)
            velocities = [max(0.0, throttle * rotor.max_rot_speed) for rotor in descriptor.rotors]
            target_wall = wall_start + sim_time
            while True:
                now = time.perf_counter()
                remaining = target_wall - now
                if remaining <= 0:
                    break
                time.sleep(min(0.002, remaining))
            publish_command(velocities)
            with pose_lock:
                altitude = latest_pose["altitude"]
                sim_stamp = latest_pose["sim_time"]
            row: Dict[str, float] = {
                "time": round(sim_time, 6),
                "throttle_cmd": float(throttle),
                "sim_time": sim_stamp,
                "measured_altitude": altitude,
            }
            for idx, velocity in enumerate(velocities):
                row[f"rotor_{idx}_velocity"] = velocity
            command_rows.append(row)

        settle_deadline = wall_start + scenario.duration + args.settle_time
        zero_cmd = [0.0 for _ in descriptor.rotors]
        while time.perf_counter() < settle_deadline:
            publish_command(zero_cmd)
            time.sleep(0.05)

    finally:
        gz_proc.terminate()
        try:
            gz_proc.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            gz_proc.kill()
            gz_proc.wait()
        if log_file is not subprocess.DEVNULL:
            log_file.close()

    if not command_rows:
        raise RuntimeError("No command samples recorded")

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="") as csv_file:
        fieldnames = list(command_rows[0].keys())
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(command_rows)

    pose_path = Path(args.pose_log) if args.pose_log else output_path.with_name(output_path.stem + "_pose.csv")
    pose_path.parent.mkdir(parents=True, exist_ok=True)
    with pose_path.open("w", newline="") as pose_file:
        writer = csv.DictWriter(pose_file, fieldnames=["sim_time", "altitude"])
        writer.writeheader()
        writer.writerows(pose_samples)

    print(f"Wrote command-aligned samples to {output_path}")
    print(f"Wrote raw pose samples to {pose_path}")


if __name__ == "__main__":
    main()

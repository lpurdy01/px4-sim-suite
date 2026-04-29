#!/usr/bin/env python3
"""Orchestrate pre-Task-4 vision pipeline with bounded execution and artifacts."""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import TextIO


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-dir", type=Path, default=Path("artifacts"), help="Artifact output directory")
    parser.add_argument("--scenario", default="vision_lock_static", help="Scenario script name under tests/scenarios/")
    parser.add_argument("--scenario-duration-s", type=float, default=20.0, help="Scenario duration passed to scenario")
    parser.add_argument("--camera-id", default="sim_cam_front", help="Camera id for adapter stream")
    parser.add_argument("--camera-duration-s", type=float, default=20.0, help="Adapter simulate duration")
    parser.add_argument("--camera-fps", type=float, default=8.0, help="Adapter simulate FPS")
    parser.add_argument("--guidance-max-seconds", type=float, default=30.0, help="Bounded guidance runtime")
    parser.add_argument("--guidance-max-rows", type=int, default=4000, help="Bounded guidance row count")
    parser.add_argument("--guidance-exit-on-idle-seconds", type=float, default=2.0, help="Idle bound for guidance")
    parser.add_argument("--pipeline-timeout-s", type=float, default=60.0, help="Hard timeout for orchestration")
    parser.add_argument("--realtime", type=int, choices=[0,1], default=0, help="Pace camera/scenario to wall-clock when 1")
    parser.add_argument(
        "--checker-mode",
        choices=["scenario-only", "full-pipeline"],
        default="full-pipeline",
        help="Mode used by tools/check_vision_lock_metrics.py",
    )
    return parser.parse_args(argv)


def _open_log(path: Path) -> TextIO:
    path.parent.mkdir(parents=True, exist_ok=True)
    return path.open("w", encoding="utf-8")


def _terminate_processes(processes: list[subprocess.Popen[bytes]]) -> None:
    alive = [proc for proc in processes if proc.poll() is None]
    for proc in alive:
        proc.terminate()
    deadline = time.time() + 8.0
    for proc in alive:
        remaining = max(0.1, deadline - time.time())
        try:
            proc.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            proc.kill()
    for proc in alive:
        try:
            proc.wait(timeout=1.0)
        except subprocess.TimeoutExpired:
            pass


def _run_checker(
    repo_root: Path,
    *,
    mode: str,
    tracks_jsonl: Path,
    events_jsonl: Path,
    summary_json: Path,
    checker_log: Path,
) -> int:
    cmd = [
        sys.executable,
        str(repo_root / "tools/check_vision_lock_metrics.py"),
        "--mode",
        mode,
        "--tracks-jsonl",
        str(tracks_jsonl),
        "--events-jsonl",
        str(events_jsonl),
        "--scenario-summary-json",
        str(summary_json),
    ]
    with checker_log.open("w", encoding="utf-8") as handle:
        proc = subprocess.run(cmd, stdout=handle, stderr=subprocess.STDOUT, check=False)
    return proc.returncode


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    repo_root = Path(__file__).resolve().parent.parent
    artifact_dir = args.artifact_dir.resolve()
    artifact_dir.mkdir(parents=True, exist_ok=True)

    scenario_script = repo_root / "tests" / "scenarios" / f"{args.scenario}.py"
    if not scenario_script.exists():
        print(f"[vision-orchestrator] missing scenario script: {scenario_script}", file=sys.stderr)
        return 2

    tracks_jsonl = artifact_dir / "intercept_tracker_tracks.jsonl"
    events_jsonl = artifact_dir / "intercept_tracker_events.jsonl"
    advisory_jsonl = artifact_dir / "guidance_advisory.jsonl"
    summary_json = artifact_dir / f"{args.scenario}_summary.json"
    checker_log = artifact_dir / "check_vision_lock_metrics.log"

    log_paths = {
        "camera": artifact_dir / "camera_ingest_adapter.log",
        "tracker": artifact_dir / "intercept_tracker.log",
        "guidance": artifact_dir / "guidance_advisory.log",
        "scenario": artifact_dir / f"{args.scenario}.log",
    }

    for path in (tracks_jsonl, events_jsonl, advisory_jsonl, summary_json):
        path.write_text("", encoding="utf-8")

    logs = {name: _open_log(path) for name, path in log_paths.items()}
    processes: list[subprocess.Popen[bytes]] = []
    interrupted = False

    def _signal_handler(signum: int, _frame: object) -> None:
        nonlocal interrupted
        interrupted = True
        print(f"[vision-orchestrator] received signal {signum}, shutting down", file=sys.stderr)
        _terminate_processes(processes)

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    start = time.time()
    try:
        tracker_cmd = [
            sys.executable,
            str(repo_root / "tools/intercept_tracker.py"),
            "--input-stdin-jsonl",
            "--clear-output",
            "--output-jsonl",
            str(tracks_jsonl),
            "--events-jsonl",
            str(events_jsonl),
        ]
        tracker_proc = subprocess.Popen(
            tracker_cmd,
            stdin=subprocess.PIPE,
            stdout=logs["tracker"],
            stderr=subprocess.STDOUT,
        )
        processes.append(tracker_proc)

        guidance_cmd = [
            sys.executable,
            str(repo_root / "tools/guidance_advisory.py"),
            "--tracks-jsonl",
            str(tracks_jsonl),
            "--output-jsonl",
            str(advisory_jsonl),
            "--clear-output",
            "--max-seconds",
            str(args.guidance_max_seconds),
            "--max-rows",
            str(args.guidance_max_rows),
            "--exit-on-idle-seconds",
            str(args.guidance_exit_on_idle_seconds),
        ]
        guidance_proc = subprocess.Popen(guidance_cmd, stdout=logs["guidance"], stderr=subprocess.STDOUT)
        processes.append(guidance_proc)

        if tracker_proc.stdin is None:
            raise RuntimeError("tracker stdin unavailable for pipeline wiring")
        camera_cmd = [
            sys.executable,
            str(repo_root / "tools/camera_ingest_adapter.py"),
            "--simulate-camera-stream",
            "--camera-id",
            args.camera_id,
            "--duration-s",
            str(args.camera_duration_s),
            "--fps",
            str(args.camera_fps),
        ]
        if int(args.realtime) == 1:
            camera_cmd.append("--realtime")
        camera_proc = subprocess.Popen(
            camera_cmd,
            stdout=tracker_proc.stdin,
            stderr=logs["camera"],
        )
        processes.append(camera_proc)
        tracker_proc.stdin.close()

        scenario_cmd = [
            sys.executable,
            str(scenario_script),
            "--duration-s",
            str(args.scenario_duration_s),
            "--fps",
            str(max(1.0, args.camera_fps)),
        ]
        if int(args.realtime) == 1:
            scenario_cmd.append("--realtime")
        scenario_env = os.environ.copy()
        scenario_env["SIMTEST_SCENARIO_RESULT"] = str(summary_json)
        scenario_proc = subprocess.Popen(scenario_cmd, stdout=logs["scenario"], stderr=subprocess.STDOUT, env=scenario_env)
        processes.append(scenario_proc)

        camera_rc = camera_proc.wait(timeout=max(1.0, args.pipeline_timeout_s))
        if camera_rc != 0:
            print(f"[vision-orchestrator] camera ingest failed: exit={camera_rc}", file=sys.stderr)
            return 1

        tracker_rc = tracker_proc.wait(timeout=max(1.0, args.pipeline_timeout_s))
        if tracker_rc != 0:
            print(f"[vision-orchestrator] tracker failed: exit={tracker_rc}", file=sys.stderr)
            return 1

        scenario_rc = scenario_proc.wait(timeout=max(1.0, args.pipeline_timeout_s))
        if scenario_rc != 0:
            print(f"[vision-orchestrator] scenario failed: exit={scenario_rc}", file=sys.stderr)
            return 1

        guidance_budget = max(1.0, args.guidance_max_seconds + args.guidance_exit_on_idle_seconds + 2.0)
        guidance_rc = guidance_proc.wait(timeout=guidance_budget)
        if guidance_rc != 0:
            print(f"[vision-orchestrator] guidance advisory failed: exit={guidance_rc}", file=sys.stderr)
            return 1
    except subprocess.TimeoutExpired:
        print("[vision-orchestrator] timeout exceeded, terminating child processes", file=sys.stderr)
        return 124
    finally:
        _terminate_processes(processes)
        for handle in logs.values():
            handle.close()

    if advisory_jsonl.exists() and advisory_jsonl.stat().st_size == 0:
        advisory_jsonl.write_text("{\"type\":\"no_advisory\",\"reason\":\"no_rows_generated\"}\n", encoding="utf-8")

    checker_rc = _run_checker(
        repo_root,
        mode=args.checker_mode,
        tracks_jsonl=tracks_jsonl,
        events_jsonl=events_jsonl,
        summary_json=summary_json,
        checker_log=checker_log,
    )
    elapsed = time.time() - start
    print(f"[vision-orchestrator] completed in {elapsed:.2f}s")
    print(f"[vision-orchestrator] summary: {summary_json}")
    print(f"[vision-orchestrator] tracks: {tracks_jsonl}")
    print(f"[vision-orchestrator] events: {events_jsonl}")
    print(f"[vision-orchestrator] advisory: {advisory_jsonl}")
    print(f"[vision-orchestrator] checker_log: {checker_log}")

    if interrupted:
        return 130
    return checker_rc


if __name__ == "__main__":
    raise SystemExit(main())

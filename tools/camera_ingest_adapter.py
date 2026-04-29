#!/usr/bin/env python3
"""Camera ingest adapter that emits tracker-ready JSONL frames."""
from __future__ import annotations

import argparse, json, math, sys, time
from pathlib import Path
from typing import Any, Iterable
from intercept_adapter_contract import normalize_adapter_frame


def _iter_jsonl_stream(lines: Iterable[str], source_name: str) -> Iterable[dict[str, Any]]:
    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line:
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise SystemExit(f"Expected object JSON in {source_name} line {line_number}")
        frame = normalize_adapter_frame(payload, source_name=source_name, line_number=line_number)
        if frame is not None:
            yield frame


def _iter_simulated_camera_frames(camera_id: str, duration_s: float, fps: float, realtime: bool) -> Iterable[dict[str, Any]]:
    frame_count = max(1, int(max(duration_s, 0.01) * max(fps, 0.1)))
    start_ts = time.time()
    wall_start = time.monotonic()
    for step in range(frame_count):
        if realtime:
            target_elapsed = step / max(fps, 0.1)
            remaining = target_elapsed - (time.monotonic() - wall_start)
            if remaining > 0:
                time.sleep(remaining)
        timestamp = start_ts + step / max(fps, 0.1)
        phase = (step / max(1, frame_count - 1)) * math.tau
        cx = 320.0 + 48.0 * math.sin(phase)
        cy = 240.0 + 28.0 * math.cos(phase * 0.7)
        bbox = [cx - 24.0, cy - 24.0, cx + 24.0, cy + 24.0]
        confidence = 0.55 + 0.4 * (0.5 + 0.5 * math.sin(phase * 0.8))
        yield {"timestamp": timestamp, "camera_id": camera_id, "detections": [{"bbox": [round(v, 4) for v in bbox], "confidence": round(confidence, 4), "target_signature": "sim_target"}]}


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    g = p.add_mutually_exclusive_group()
    g.add_argument("--simulate-camera-stream", action="store_true")
    g.add_argument("--input-jsonl", type=Path)
    g.add_argument("--input-stdin-jsonl", action="store_true")
    p.add_argument("--camera-id", default="sim_cam_front")
    p.add_argument("--duration-s", type=float, default=20.0)
    p.add_argument("--fps", type=float, default=5.0)
    p.add_argument("--realtime", action="store_true", help="Pace emitted frames to wall-clock FPS.")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    if args.input_jsonl:
        with args.input_jsonl.open("r", encoding="utf-8") as h:
            for frame in _iter_jsonl_stream(h, str(args.input_jsonl)):
                if frame["camera_id"] == "unknown_camera":
                    frame["camera_id"] = args.camera_id
                sys.stdout.write(json.dumps(frame, separators=(",", ":")) + "\n")
        return 0
    if args.input_stdin_jsonl:
        for frame in _iter_jsonl_stream(sys.stdin, "stdin"):
            if frame["camera_id"] == "unknown_camera":
                frame["camera_id"] = args.camera_id
            sys.stdout.write(json.dumps(frame, separators=(",", ":")) + "\n")
        return 0
    mode = "realtime" if args.realtime else "fast"
    print(f"[camera-ingest-adapter] synthetic mode={mode} duration_s={args.duration_s:.2f} fps={args.fps:.2f}", file=sys.stderr)
    for frame in _iter_simulated_camera_frames(args.camera_id, args.duration_s, args.fps, args.realtime):
        sys.stdout.write(json.dumps(frame, separators=(",", ":")) + "\n")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

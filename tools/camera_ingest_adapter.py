#!/usr/bin/env python3
"""Camera ingest adapter that emits tracker-ready JSONL frames.

The adapter stays loosely coupled by only producing the shared minimal frame shape:
{timestamp, camera_id, detections}

Input modes:
- --simulate-camera-stream: synthetic single-camera detections (default)
- --input-jsonl: replay one JSON object per line from file
- --input-stdin-jsonl: replay one JSON object per line from stdin
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path
from typing import Any, Iterable

from intercept_adapter_contract import normalize_adapter_frame


def _iter_jsonl_stream(lines: Iterable[str], source_name: str) -> Iterable[dict[str, Any]]:
    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"Invalid JSON in {source_name} line {line_number}: {exc}") from exc
        if not isinstance(payload, dict):
            raise SystemExit(f"Expected object JSON in {source_name} line {line_number}")
        yield normalize_adapter_frame(payload)


def _iter_simulated_camera_frames(camera_id: str, duration_s: float, fps: float) -> Iterable[dict[str, Any]]:
    frame_count = max(1, int(max(duration_s, 0.01) * max(fps, 0.1)))
    start_ts = time.time()
    for step in range(frame_count):
        timestamp = start_ts + step / max(fps, 0.1)
        phase = (step / max(1, frame_count - 1)) * math.tau

        cx = 320.0 + 48.0 * math.sin(phase)
        cy = 240.0 + 28.0 * math.cos(phase * 0.7)
        half_w = 24.0
        half_h = 24.0
        bbox = [cx - half_w, cy - half_h, cx + half_w, cy + half_h]
        confidence = 0.55 + 0.4 * (0.5 + 0.5 * math.sin(phase * 0.8))

        yield {
            "timestamp": timestamp,
            "camera_id": camera_id,
            "detections": [
                {
                    "bbox": [round(v, 4) for v in bbox],
                    "confidence": round(confidence, 4),
                    "target_signature": "sim_target",
                }
            ],
        }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)

    source = parser.add_mutually_exclusive_group()
    source.add_argument(
        "--simulate-camera-stream",
        action="store_true",
        help="Emit a synthetic single-camera stream (default mode).",
    )
    source.add_argument(
        "--input-jsonl",
        type=Path,
        help="Read adapter-format JSONL from file.",
    )
    source.add_argument(
        "--input-stdin-jsonl",
        action="store_true",
        help="Read adapter-format JSONL from stdin.",
    )

    parser.add_argument("--camera-id", default="sim_cam_front", help="Camera id emitted by this adapter.")
    parser.add_argument("--duration-s", type=float, default=20.0, help="Duration in simulate mode.")
    parser.add_argument("--fps", type=float, default=5.0, help="Frames per second in simulate mode.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])

    if args.input_jsonl:
        with args.input_jsonl.open("r", encoding="utf-8") as handle:
            iterator = _iter_jsonl_stream(handle, str(args.input_jsonl))
            for frame in iterator:
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

    for frame in _iter_simulated_camera_frames(args.camera_id, args.duration_s, args.fps):
        sys.stdout.write(json.dumps(frame, separators=(",", ":")) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Tail tracker JSONL and emit guidance advisory JSONL rows.

Each advisory row includes:
- normalized image-plane error (ex, ey)
- suggested yaw_rate_cmd and pitch_rate_cmd
- gating_reason for suppressed commands
- latency metrics (now_ts - frame_ts)
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path
from typing import Any


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tracks-jsonl",
        type=Path,
        default=Path("artifacts/intercept_tracker_tracks.jsonl"),
        help="Path to intercept_tracker track JSONL input.",
    )
    parser.add_argument(
        "--output-jsonl",
        type=Path,
        default=Path("artifacts/guidance_advisory.jsonl"),
        help="Path to advisory JSONL output.",
    )
    parser.add_argument(
        "--clear-output",
        action="store_true",
        help="Truncate output file before writing.",
    )
    parser.add_argument(
        "--follow",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Follow input file for appended lines (default: true).",
    )
    parser.add_argument(
        "--poll-interval-s",
        type=float,
        default=0.2,
        help="Polling interval while following input file.",
    )
    parser.add_argument(
        "--stale-after-s",
        type=float,
        default=0.6,
        help="Mark records stale when latency exceeds this threshold.",
    )
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=0.65,
        help="Minimum confidence required for non-zero commands.",
    )
    parser.add_argument(
        "--min-lock-state",
        choices=["TRACKING", "LOCKED"],
        default="LOCKED",
        help="Minimum tracker lock_state required for non-zero commands.",
    )
    parser.add_argument(
        "--frame-width",
        type=float,
        default=640.0,
        help="Image width used to normalize centroid x error.",
    )
    parser.add_argument(
        "--frame-height",
        type=float,
        default=480.0,
        help="Image height used to normalize centroid y error.",
    )
    parser.add_argument(
        "--yaw-kp",
        type=float,
        default=0.8,
        help="Proportional gain for yaw_rate_cmd from ex.",
    )
    parser.add_argument(
        "--pitch-kp",
        type=float,
        default=0.8,
        help="Proportional gain for pitch_rate_cmd from ey.",
    )
    parser.add_argument(
        "--max-rate-cmd",
        type=float,
        default=0.7,
        help="Absolute clamp for yaw_rate_cmd and pitch_rate_cmd.",
    )
    parser.add_argument(
        "--max-seconds",
        type=float,
        default=None,
        help="Maximum runtime before exiting (disabled when omitted).",
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=None,
        help="Maximum advisory rows to emit before exiting (disabled when omitted).",
    )
    parser.add_argument(
        "--exit-on-idle-seconds",
        type=float,
        default=None,
        help="Exit after this many seconds without new input rows while following.",
    )
    return parser.parse_args(argv)


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_centroid(raw: Any) -> tuple[float, float] | None:
    if not isinstance(raw, list) or len(raw) != 2:
        return None
    cx = _as_float(raw[0])
    cy = _as_float(raw[1])
    if cx is None or cy is None:
        return None
    return (cx, cy)


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return min(maximum, max(minimum, value))


def _normalized_error(centroid: tuple[float, float], frame_width: float, frame_height: float) -> tuple[float, float]:
    cx, cy = centroid
    center_x = frame_width / 2.0
    center_y = frame_height / 2.0
    ex = (cx - center_x) / max(center_x, 1.0)
    ey = (cy - center_y) / max(center_y, 1.0)
    return (_clamp(ex, -1.0, 1.0), _clamp(ey, -1.0, 1.0))


def _gating_reason(
    lock_state: str,
    confidence: float,
    latency_s: float,
    stale_after_s: float,
    centroid: tuple[float, float] | None,
    min_lock_state: str,
    min_confidence: float,
) -> str:
    if centroid is None:
        return "NO_DETECTION"

    if min_lock_state == "LOCKED" and lock_state != "LOCKED":
        return "LOCK_LOST"

    if min_lock_state == "TRACKING" and lock_state not in {"TRACKING", "LOCKED"}:
        return "LOCK_LOST"

    if confidence < min_confidence:
        return "LOW_CONFIDENCE"

    if not math.isfinite(latency_s) or latency_s > stale_after_s:
        return "STALE_FRAME"

    return "OK"


def _advisory_from_track(row: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    now_ts = time.time()
    frame_ts = _as_float(row.get("timestamp"))
    latency_s = float("inf") if frame_ts is None else max(0.0, now_ts - frame_ts)

    camera_id = str(row.get("camera_id", "unknown_camera"))
    track_id = row.get("track_id")
    lock_state = str(row.get("lock_state", "SEARCHING"))

    confidence = _as_float(row.get("confidence"))
    if confidence is None:
        confidence = 0.0

    centroid = _parse_centroid(row.get("centroid"))
    if centroid is None:
        ex = 0.0
        ey = 0.0
    else:
        ex, ey = _normalized_error(centroid, args.frame_width, args.frame_height)

    gating_reason = _gating_reason(
        lock_state=lock_state,
        confidence=confidence,
        latency_s=latency_s,
        stale_after_s=args.stale_after_s,
        centroid=centroid,
        min_lock_state=args.min_lock_state,
        min_confidence=args.min_confidence,
    )

    yaw_rate_cmd = _clamp(args.yaw_kp * ex, -args.max_rate_cmd, args.max_rate_cmd)
    pitch_rate_cmd = _clamp(-args.pitch_kp * ey, -args.max_rate_cmd, args.max_rate_cmd)

    if gating_reason != "OK":
        yaw_rate_cmd = 0.0
        pitch_rate_cmd = 0.0

    return {
        "now_ts": round(now_ts, 6),
        "frame_ts": None if frame_ts is None else round(frame_ts, 6),
        "latency_s": round(latency_s, 6) if math.isfinite(latency_s) else None,
        "camera_id": camera_id,
        "track_id": track_id,
        "lock_state": lock_state,
        "confidence": round(confidence, 4),
        "centroid": None if centroid is None else [round(centroid[0], 4), round(centroid[1], 4)],
        "ex": round(ex, 6),
        "ey": round(ey, 6),
        "yaw_rate_cmd": round(yaw_rate_cmd, 6),
        "pitch_rate_cmd": round(pitch_rate_cmd, 6),
        "gating_reason": gating_reason,
    }


def _iter_jsonl_tail(path: Path, *, follow: bool, poll_interval_s: float):
    with path.open("r", encoding="utf-8") as handle:
        while True:
            position = handle.tell()
            raw_line = handle.readline()
            if raw_line:
                yield raw_line
                continue

            if not follow:
                break

            handle.seek(position)
            time.sleep(max(0.01, poll_interval_s))
            yield ""


def _write_jsonl(path: Path, record: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, separators=(",", ":")) + "\n")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])

    if args.frame_width <= 0 or args.frame_height <= 0:
        raise SystemExit("--frame-width and --frame-height must be > 0")
    if args.max_seconds is not None and args.max_seconds <= 0:
        raise SystemExit("--max-seconds must be > 0 when provided")
    if args.max_rows is not None and args.max_rows <= 0:
        raise SystemExit("--max-rows must be > 0 when provided")
    if args.exit_on_idle_seconds is not None and args.exit_on_idle_seconds <= 0:
        raise SystemExit("--exit-on-idle-seconds must be > 0 when provided")

    if not args.tracks_jsonl.exists():
        raise SystemExit(f"Missing tracker JSONL: {args.tracks_jsonl}")

    args.output_jsonl.parent.mkdir(parents=True, exist_ok=True)
    if args.clear_output:
        args.output_jsonl.write_text("", encoding="utf-8")

    processed = 0
    started_at = time.time()
    last_activity_at = started_at
    try:
        for line_number, raw_line in enumerate(_iter_jsonl_tail(args.tracks_jsonl, follow=args.follow, poll_interval_s=args.poll_interval_s), start=1):
            now = time.time()
            if args.max_seconds is not None and now - started_at >= args.max_seconds:
                print(f"Reached --max-seconds={args.max_seconds:.3f}, exiting.", file=sys.stderr)
                break
            if args.exit_on_idle_seconds is not None and now - last_activity_at >= args.exit_on_idle_seconds:
                print(f"Reached --exit-on-idle-seconds={args.exit_on_idle_seconds:.3f}, exiting.", file=sys.stderr)
                break

            line = raw_line.strip()
            if not line:
                continue

            try:
                row = json.loads(line)
            except json.JSONDecodeError as error:
                print(f"Skipping invalid JSON at {args.tracks_jsonl}:{line_number}: {error}", file=sys.stderr)
                continue

            if not isinstance(row, dict):
                print(f"Skipping non-object JSON at {args.tracks_jsonl}:{line_number}", file=sys.stderr)
                continue

            advisory = _advisory_from_track(row, args)
            _write_jsonl(args.output_jsonl, advisory)
            processed += 1
            last_activity_at = time.time()
            if args.max_rows is not None and processed >= args.max_rows:
                print(f"Reached --max-rows={args.max_rows}, exiting.", file=sys.stderr)
                break
    except KeyboardInterrupt:
        print("Interrupted, stopping tail loop.", file=sys.stderr)

    print(f"Guidance advisory output written to {args.output_jsonl} ({processed} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

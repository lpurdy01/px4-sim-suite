#!/usr/bin/env python3
"""Static-target lock scenario focused on acquisition + hold metrics."""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from pathlib import Path

SUMMARY_PATH = os.getenv("SIMTEST_SCENARIO_RESULT")

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
TOOLS_DIR = REPO_ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from intercept_tracker import Detection, InterceptTracker  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Static target lock acquisition/hold scenario")
    parser.add_argument("--duration-s", type=float, default=18.0, help="Scenario duration in seconds")
    parser.add_argument("--fps", type=float, default=10.0, help="Synthetic camera frame rate")
    parser.add_argument("--camera-id", default="sim_cam_down", help="Camera id")
    parser.add_argument("--target-signature", default="static_aruco", help="Target signature")
    parser.add_argument("--lock-threshold", type=float, default=0.72, help="Tracker lock threshold")
    parser.add_argument("--min-hits", type=int, default=4, help="Tracker hits required for LOCKED")
    parser.add_argument(
        "--warmup-s",
        type=float,
        default=2.5,
        help="Seconds spent in pre-lock confidence ramp",
    )
    parser.add_argument(
        "--dropout-every-s",
        type=float,
        default=5.5,
        help="Inject an empty-detection gap every N seconds after lock",
    )
    parser.add_argument(
        "--dropout-duration-s",
        type=float,
        default=0.5,
        help="Duration of each synthetic no-detection gap",
    )
    return parser.parse_args()


def write_summary(status: str, **fields: float | str | int | None) -> None:
    if not SUMMARY_PATH:
        return
    payload = {"status": status, **fields}
    try:
        with open(SUMMARY_PATH, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, separators=(",", ":"))
    except OSError as error:  # best effort only
        print(f"[scenario] warning: failed to write summary ({error})")


def make_detection(confidence: float, target_signature: str) -> Detection:
    bbox = (296.0, 216.0, 344.0, 264.0)  # static target in frame center
    return Detection(bbox=bbox, confidence=confidence, target_signature=target_signature)


def should_dropout(t_s: float, every_s: float, duration_s: float) -> bool:
    if every_s <= 0 or duration_s <= 0:
        return False
    phase = t_s % every_s
    return phase < duration_s


def main() -> int:
    args = parse_args()

    duration_s = max(1.0, float(args.duration_s))
    fps = max(1.0, float(args.fps))
    dt = 1.0 / fps
    frame_count = max(1, int(math.ceil(duration_s * fps)))

    tracker = InterceptTracker(
        lock_threshold=float(args.lock_threshold),
        iou_match_threshold=0.5,
        min_hits_for_lock=max(1, int(args.min_hits)),
    )

    started = time.time()
    first_track_s: float | None = None
    first_lock_s: float | None = None
    max_gap_s = 0.0
    locked_samples = 0
    total_samples_after_lock = 0
    unlocked_gap_start: float | None = None

    print(
        "[scenario] Starting static lock test "
        f"(duration={duration_s:.1f}s, fps={fps:.1f}, warmup={args.warmup_s:.1f}s)"
    )

    for step in range(frame_count):
        rel_t = step * dt
        timestamp = started + rel_t

        in_warmup = rel_t < max(0.0, args.warmup_s)
        warmup_ratio = 0.0 if args.warmup_s <= 0 else min(1.0, rel_t / args.warmup_s)
        confidence = 0.35 + 0.55 * warmup_ratio

        detections: list[Detection]
        if in_warmup:
            detections = [make_detection(confidence, args.target_signature)]
        else:
            in_dropout = should_dropout(
                rel_t - max(0.0, args.warmup_s),
                float(args.dropout_every_s),
                float(args.dropout_duration_s),
            )
            detections = [] if in_dropout else [make_detection(0.9, args.target_signature)]

        result, _events = tracker.update(timestamp, args.camera_id, detections)

        if first_track_s is None and result.get("track_id"):
            first_track_s = rel_t
        if first_lock_s is None and result.get("lock_state") == "LOCKED":
            first_lock_s = rel_t
            print(f"[scenario] first LOCKED at t={first_lock_s:.2f}s")

        if first_lock_s is not None and rel_t >= first_lock_s:
            total_samples_after_lock += 1
            if result.get("lock_state") == "LOCKED":
                locked_samples += 1
                if unlocked_gap_start is not None:
                    gap_s = rel_t - unlocked_gap_start
                    max_gap_s = max(max_gap_s, gap_s)
                    unlocked_gap_start = None
            elif unlocked_gap_start is None:
                unlocked_gap_start = rel_t

        if step % max(1, int(fps)) == 0:
            print(
                "[scenario] "
                f"t={rel_t:5.2f}s lock_state={result.get('lock_state')} "
                f"confidence={result.get('confidence', 0.0):.2f} "
                f"track_id={result.get('track_id')}"
            )

    end_rel_t = (frame_count - 1) * dt
    if unlocked_gap_start is not None and first_lock_s is not None:
        max_gap_s = max(max_gap_s, max(0.0, end_rel_t - unlocked_gap_start))

    if first_lock_s is None:
        lock_hold_ratio = 0.0
    else:
        lock_hold_ratio = locked_samples / max(1, total_samples_after_lock)

    summary = {
        "time_to_first_track_s": None if first_track_s is None else round(first_track_s, 3),
        "time_to_lock_s": None if first_lock_s is None else round(first_lock_s, 3),
        "lock_hold_ratio": round(lock_hold_ratio, 4),
        "max_gap_s": round(max_gap_s, 3),
        "duration_s": round(duration_s, 2),
        "fps": round(fps, 2),
    }

    write_summary("success", **summary)
    print(f"[scenario] summary: {json.dumps(summary, sort_keys=True)}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:  # pylint: disable=broad-except
        write_summary("unexpected", error=str(error))
        print(f"[scenario] unexpected: {error}")
        sys.exit(4)

#!/usr/bin/env python3
"""Static-target lock scenario focused on deterministic stimulus + metadata."""
from __future__ import annotations
import argparse, json, math, os, sys, time
from pathlib import Path
SUMMARY_PATH = os.getenv("SIMTEST_SCENARIO_RESULT")
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
TOOLS_DIR = REPO_ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))
from intercept_tracker import Detection, InterceptTracker  # noqa: E402

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--duration-s", type=float, default=18.0)
    p.add_argument("--fps", type=float, default=10.0)
    p.add_argument("--camera-id", default="sim_cam_down")
    p.add_argument("--target-signature", default="static_aruco")
    p.add_argument("--lock-threshold", type=float, default=0.72)
    p.add_argument("--min-hits", type=int, default=4)
    p.add_argument("--warmup-s", type=float, default=2.5)
    p.add_argument("--dropout-every-s", type=float, default=5.5)
    p.add_argument("--dropout-duration-s", type=float, default=0.5)
    p.add_argument("--realtime", action="store_true", help="Pace scenario to wall-clock.")
    return p.parse_args()

def write_summary(status: str, **fields):
    if SUMMARY_PATH:
        with open(SUMMARY_PATH, "w", encoding="utf-8") as h:
            json.dump({"status": status, **fields}, h, separators=(",", ":"))

def make_detection(confidence: float, target_signature: str) -> Detection:
    return Detection(bbox=(296.0, 216.0, 344.0, 264.0), confidence=confidence, target_signature=target_signature)

def should_dropout(t_s: float, every_s: float, duration_s: float) -> bool:
    return every_s > 0 and duration_s > 0 and (t_s % every_s) < duration_s

def main() -> int:
    a = parse_args(); duration_s=max(1.0,a.duration_s); fps=max(1.0,a.fps); dt=1.0/fps; frames=max(1,int(math.ceil(duration_s*fps)))
    tracker = InterceptTracker(lock_threshold=float(a.lock_threshold), iou_match_threshold=0.5, min_hits_for_lock=max(1, int(a.min_hits)))
    started=time.time(); mono_start=time.monotonic(); first_track_s=None; first_lock_s=None
    mode = "realtime" if a.realtime else "fast"
    print(f"[scenario] Starting static lock test mode={mode} duration={duration_s:.1f}s fps={fps:.1f}")
    for step in range(frames):
        rel_t = step*dt
        if a.realtime:
            rem = rel_t - (time.monotonic()-mono_start)
            if rem>0: time.sleep(rem)
        ts=started+rel_t
        in_warmup = rel_t < max(0.0, a.warmup_s)
        warmup_ratio = 0.0 if a.warmup_s <= 0 else min(1.0, rel_t / a.warmup_s)
        conf = 0.35 + 0.55 * warmup_ratio
        if in_warmup:
            detections=[make_detection(conf,a.target_signature)]
        else:
            in_dropout=should_dropout(rel_t-max(0.0,a.warmup_s),float(a.dropout_every_s),float(a.dropout_duration_s))
            detections=[] if in_dropout else [make_detection(0.9,a.target_signature)]
        result,_=tracker.update(ts,a.camera_id,detections)
        if first_track_s is None and result.get("track_id"): first_track_s=rel_t
        if first_lock_s is None and result.get("lock_state")=="LOCKED": first_lock_s=rel_t
    summary={"duration_s":round(duration_s,2),"fps":round(fps,2),"mode":mode,"frame_count":frames,
             "time_to_first_track_s_scenario_estimate": None,
             "time_to_lock_s_scenario_estimate": None,
             "lock_hold_ratio_scenario_estimate": None,
             "max_gap_s_scenario_estimate": None}
    write_summary("success", **summary)
    print(f"[scenario] summary: {json.dumps(summary, sort_keys=True)}")
    return 0
if __name__ == "__main__":
    sys.exit(main())

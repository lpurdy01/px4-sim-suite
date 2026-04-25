#!/usr/bin/env python3
"""Track intercept targets from simulated camera streams or logged frame metadata.

This tool emits a JSONL contract intended for future guidance/autonomy components.
Each output line includes:
- timestamp
- camera_id
- bbox
- centroid
- confidence
- track_id
- lock_state

It also writes lock-quality updates and camera handoff events under artifacts/.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from intercept_adapter_contract import normalize_adapter_frame


BBox = tuple[float, float, float, float]


@dataclass
class Detection:
    bbox: BBox
    confidence: float
    target_signature: str


@dataclass
class TrackState:
    track_id: str
    camera_id: str
    bbox: BBox
    confidence_ema: float
    lock_quality: float
    lock_state: str
    last_timestamp: float
    seen_count: int
    target_signature: str


class InterceptTracker:
    def __init__(
        self,
        lock_threshold: float,
        iou_match_threshold: float,
        min_hits_for_lock: int,
    ) -> None:
        self.lock_threshold = lock_threshold
        self.iou_match_threshold = iou_match_threshold
        self.min_hits_for_lock = min_hits_for_lock
        self._tracks_by_camera: dict[str, dict[str, TrackState]] = {}
        self._next_track_index = 1
        self._last_camera_by_signature: dict[str, str] = {}

    def update(
        self,
        timestamp: float,
        camera_id: str,
        detections: list[Detection],
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        camera_tracks = self._tracks_by_camera.setdefault(camera_id, {})
        best_detection = max(detections, key=lambda d: d.confidence) if detections else None

        if best_detection is None:
            result = {
                "timestamp": timestamp,
                "camera_id": camera_id,
                "bbox": None,
                "centroid": None,
                "confidence": 0.0,
                "track_id": None,
                "lock_state": "SEARCHING",
                "lock_quality": 0.0,
            }
            return result, []

        track, iou_prev = self._match_or_create_track(camera_id, best_detection, timestamp)
        track.seen_count += 1
        track.last_timestamp = timestamp
        track.camera_id = camera_id
        track.bbox = best_detection.bbox
        track.target_signature = best_detection.target_signature
        track.confidence_ema = 0.6 * track.confidence_ema + 0.4 * best_detection.confidence
        track.lock_quality = 0.5 * track.confidence_ema + 0.5 * iou_prev
        track.lock_state = self._determine_lock_state(track)

        events: list[dict[str, Any]] = []
        previous_camera = self._last_camera_by_signature.get(track.target_signature)
        if previous_camera and previous_camera != camera_id:
            events.append(
                {
                    "timestamp": timestamp,
                    "event": "handoff",
                    "track_id": track.track_id,
                    "target_signature": track.target_signature,
                    "from_camera": previous_camera,
                    "to_camera": camera_id,
                }
            )
        self._last_camera_by_signature[track.target_signature] = camera_id

        result = {
            "timestamp": timestamp,
            "camera_id": camera_id,
            "bbox": [round(v, 4) for v in track.bbox],
            "centroid": [round(v, 4) for v in _bbox_centroid(track.bbox)],
            "confidence": round(best_detection.confidence, 4),
            "track_id": track.track_id,
            "lock_state": track.lock_state,
            "lock_quality": round(track.lock_quality, 4),
        }
        return result, events

    def _match_or_create_track(
        self,
        camera_id: str,
        detection: Detection,
        timestamp: float,
    ) -> tuple[TrackState, float]:
        camera_tracks = self._tracks_by_camera.setdefault(camera_id, {})
        best_track: TrackState | None = None
        best_iou = -1.0
        for candidate in camera_tracks.values():
            iou = _iou(candidate.bbox, detection.bbox)
            if iou > best_iou:
                best_iou = iou
                best_track = candidate

        if best_track and best_iou >= self.iou_match_threshold:
            return best_track, best_iou

        track_id = f"trk_{self._next_track_index:05d}"
        self._next_track_index += 1
        created = TrackState(
            track_id=track_id,
            camera_id=camera_id,
            bbox=detection.bbox,
            confidence_ema=detection.confidence,
            lock_quality=detection.confidence,
            lock_state="TRACKING",
            last_timestamp=timestamp,
            seen_count=0,
            target_signature=detection.target_signature,
        )
        camera_tracks[track_id] = created
        return created, 0.0

    def _determine_lock_state(self, track: TrackState) -> str:
        if track.seen_count >= self.min_hits_for_lock and track.confidence_ema >= self.lock_threshold:
            return "LOCKED"
        if track.confidence_ema >= max(0.35, self.lock_threshold * 0.6):
            return "TRACKING"
        return "SEARCHING"


def _iou(a: BBox, b: BBox) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b

    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)

    inter_w = max(0.0, inter_x2 - inter_x1)
    inter_h = max(0.0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h
    if inter_area <= 0:
        return 0.0

    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter_area
    return inter_area / union if union > 0 else 0.0


def _bbox_centroid(bbox: BBox) -> tuple[float, float]:
    x1, y1, x2, y2 = bbox
    return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)


def _build_bbox_from_centroid(centroid: tuple[float, float], width: float, height: float) -> BBox:
    cx, cy = centroid
    half_w = width / 2.0
    half_h = height / 2.0
    return (cx - half_w, cy - half_h, cx + half_w, cy + half_h)


def _parse_bbox(raw: Any) -> BBox | None:
    if not isinstance(raw, list) or len(raw) != 4:
        return None
    try:
        vals = [float(v) for v in raw]
    except (TypeError, ValueError):
        return None
    x1, y1, x2, y2 = vals
    if x2 <= x1 or y2 <= y1:
        return None
    return (x1, y1, x2, y2)


def _frame_to_detections(frame: dict[str, Any]) -> list[Detection]:
    detections: list[Detection] = []

    for raw_detection in frame.get("detections", []):
        if not isinstance(raw_detection, dict):
            continue
        bbox = _parse_bbox(raw_detection.get("bbox"))
        if bbox is None and isinstance(raw_detection.get("centroid"), list):
            centroid_raw = raw_detection.get("centroid")
            if len(centroid_raw) == 2:
                try:
                    centroid = (float(centroid_raw[0]), float(centroid_raw[1]))
                except (TypeError, ValueError):
                    centroid = None
                if centroid:
                    bbox = _build_bbox_from_centroid(centroid, 40.0, 40.0)

        if bbox is None:
            continue

        conf_raw = raw_detection.get("confidence", 0.5)
        try:
            confidence = min(1.0, max(0.0, float(conf_raw)))
        except (TypeError, ValueError):
            confidence = 0.5

        signature = str(raw_detection.get("target_signature", frame.get("target_signature", "default_target")))
        detections.append(Detection(bbox=bbox, confidence=confidence, target_signature=signature))

    # Fallback for frame-level bbox and confidence.
    if not detections:
        bbox = _parse_bbox(frame.get("bbox"))
        if bbox is not None:
            conf_raw = frame.get("confidence", 0.5)
            try:
                confidence = min(1.0, max(0.0, float(conf_raw)))
            except (TypeError, ValueError):
                confidence = 0.5
            signature = str(frame.get("target_signature", "default_target"))
            detections.append(Detection(bbox=bbox, confidence=confidence, target_signature=signature))

    return detections


def _iter_logged_frames(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                frame = json.loads(line)
            except json.JSONDecodeError as exc:
                raise SystemExit(f"Invalid JSON in {path} line {line_number}: {exc}") from exc
            if not isinstance(frame, dict):
                raise SystemExit(f"Expected object JSON in {path} line {line_number}")
            normalized = normalize_adapter_frame(frame, source_name=str(path), line_number=line_number)
            if normalized is None:
                continue
            yield normalized


def _iter_stdin_frames() -> Iterable[dict[str, Any]]:
    for line_number, raw_line in enumerate(sys.stdin, start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            frame = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"Invalid JSON in stdin line {line_number}: {exc}") from exc
        if not isinstance(frame, dict):
            raise SystemExit(f"Expected object JSON in stdin line {line_number}")
        normalized = normalize_adapter_frame(frame, source_name="stdin", line_number=line_number)
        if normalized is None:
            continue
        yield normalized


def _iter_simulated_frames(cameras: list[str], duration_s: float, fps: float) -> Iterable[dict[str, Any]]:
    now = time.time()
    frame_count = max(1, int(duration_s * fps))
    for step in range(frame_count):
        timestamp = now + step / fps
        active_camera = cameras[0] if step < frame_count // 2 else cameras[-1]
        for index, camera_id in enumerate(cameras):
            if camera_id != active_camera:
                yield {
                    "timestamp": timestamp,
                    "camera_id": camera_id,
                    "detections": [],
                }
                continue
            phase = (step / max(1, frame_count - 1)) * math.tau + (index * 0.9)
            cx = 320 + 36 * math.sin(phase)
            cy = 240 + 24 * math.cos(phase)
            confidence = 0.55 + 0.4 * (0.5 + 0.5 * math.sin(phase * 0.7))
            bbox = _build_bbox_from_centroid((cx, cy), 46, 46)
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


def _write_jsonl(path: Path, record: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, separators=(",", ":")) + "\n")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--input-jsonl",
        type=Path,
        help="Logged frame metadata stream (one JSON object per line).",
    )
    source.add_argument(
        "--simulate-stream",
        action="store_true",
        help="Generate a synthetic multi-camera stream for integration testing.",
    )
    source.add_argument(
        "--input-stdin-jsonl",
        action="store_true",
        help="Read adapter-format frame JSONL from stdin.",
    )

    parser.add_argument(
        "--cameras",
        default="cam0,cam1",
        help="Comma-separated camera ids for simulated stream mode.",
    )
    parser.add_argument(
        "--duration-s",
        type=float,
        default=5.0,
        help="Duration used in --simulate-stream mode.",
    )
    parser.add_argument(
        "--fps",
        type=float,
        default=5.0,
        help="Frames per second used in --simulate-stream mode.",
    )
    parser.add_argument(
        "--output-jsonl",
        type=Path,
        default=Path("artifacts/intercept_tracker_tracks.jsonl"),
        help="Output JSONL records for tracking contract.",
    )
    parser.add_argument(
        "--events-jsonl",
        type=Path,
        default=Path("artifacts/intercept_tracker_events.jsonl"),
        help="Output JSONL events (handoff and lock transitions).",
    )
    parser.add_argument(
        "--lock-threshold",
        type=float,
        default=0.72,
        help="Confidence EMA threshold to consider target lock.",
    )
    parser.add_argument(
        "--iou-threshold",
        type=float,
        default=0.25,
        help="IOU threshold used for track association.",
    )
    parser.add_argument(
        "--min-hits",
        type=int,
        default=3,
        help="Minimum associated detections before entering LOCKED state.",
    )
    parser.add_argument(
        "--clear-output",
        action="store_true",
        help="Truncate output JSONL files before writing.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])

    args.output_jsonl.parent.mkdir(parents=True, exist_ok=True)
    args.events_jsonl.parent.mkdir(parents=True, exist_ok=True)
    if args.clear_output:
        args.output_jsonl.write_text("", encoding="utf-8")
        args.events_jsonl.write_text("", encoding="utf-8")

    tracker = InterceptTracker(
        lock_threshold=args.lock_threshold,
        iou_match_threshold=args.iou_threshold,
        min_hits_for_lock=args.min_hits,
    )

    if args.simulate_stream:
        cameras = [cam.strip() for cam in args.cameras.split(",") if cam.strip()]
        if not cameras:
            raise SystemExit("At least one camera id is required for --simulate-stream")
        frame_iter = _iter_simulated_frames(cameras, args.duration_s, args.fps)
    elif args.input_stdin_jsonl:
        frame_iter = _iter_stdin_frames()
    else:
        frame_iter = _iter_logged_frames(args.input_jsonl)

    last_lock_state_by_track: dict[str, str] = {}

    for frame in frame_iter:
        timestamp_raw = frame.get("timestamp", time.time())
        try:
            timestamp = float(timestamp_raw)
        except (TypeError, ValueError):
            print("[tracker] dropping frame with invalid timestamp from normalized stream", file=sys.stderr)
            continue

        camera_id = str(frame.get("camera_id", "unknown_camera"))
        detections = _frame_to_detections(frame)
        output, events = tracker.update(timestamp, camera_id, detections)
        _write_jsonl(args.output_jsonl, output)

        track_id = output.get("track_id")
        if track_id:
            previous_state = last_lock_state_by_track.get(track_id)
            if previous_state and previous_state != output["lock_state"]:
                events.append(
                    {
                        "timestamp": timestamp,
                        "event": "lock_state_transition",
                        "track_id": track_id,
                        "from": previous_state,
                        "to": output["lock_state"],
                        "lock_quality": output["lock_quality"],
                    }
                )
            last_lock_state_by_track[track_id] = output["lock_state"]

        for event in events:
            _write_jsonl(args.events_jsonl, event)

    print(f"Tracking output written to {args.output_jsonl}")
    print(f"Event log written to {args.events_jsonl}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

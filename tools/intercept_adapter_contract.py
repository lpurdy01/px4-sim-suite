#!/usr/bin/env python3
"""Shared adapter contract for intercept tracker inputs.

Adapters should emit one JSON object per line with:
- timestamp: float-like UNIX seconds
- camera_id: source camera identifier
- detections: list of detection objects
"""

from __future__ import annotations

from typing import Any, TypedDict


class AdapterDetection(TypedDict, total=False):
    bbox: list[float]
    centroid: list[float]
    confidence: float
    target_signature: str


class AdapterFrame(TypedDict):
    timestamp: float
    camera_id: str
    detections: list[AdapterDetection]


def normalize_adapter_frame(raw: dict[str, Any], *, default_camera_id: str = "unknown_camera") -> dict[str, Any]:
    """Normalize loosely-typed adapter payloads to the shared tracker contract."""
    timestamp_raw = raw.get("timestamp")
    try:
        timestamp = float(timestamp_raw)
    except (TypeError, ValueError):
        timestamp = 0.0

    camera_id = str(raw.get("camera_id") or default_camera_id)

    detections_raw = raw.get("detections")
    if isinstance(detections_raw, list):
        detections = detections_raw
    else:
        detections = []

    return {
        "timestamp": timestamp,
        "camera_id": camera_id,
        "detections": detections,
    }

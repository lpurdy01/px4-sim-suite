#!/usr/bin/env python3
"""Validate vision lock metrics from tracker artifacts and scenario summary."""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class Thresholds:
    max_lock_acquisition_s: float
    min_lock_hold_ratio: float
    max_dropout_count: int
    max_dropout_gap_s: float
    lock_quality_percentile: float
    min_lock_quality_at_percentile: float


@dataclass
class ComputedMetrics:
    lock_acquisition_s: float | None
    lock_hold_ratio: float
    dropout_count: int
    max_dropout_gap_s: float
    lock_quality_percentile_value: float | None
    lock_quality_samples: int


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError as error:
        raise SystemExit(f"Invalid float in ${name}: {value}") from error


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError as error:
        raise SystemExit(f"Invalid int in ${name}: {value}") from error


def _env_path(name: str, default: str) -> Path:
    return Path(os.getenv(name, default))


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tracks-jsonl",
        type=Path,
        default=_env_path("VISION_LOCK_TRACKS_JSONL", "artifacts/intercept_tracker_tracks.jsonl"),
        help="Path to tracker track stream JSONL",
    )
    parser.add_argument(
        "--events-jsonl",
        type=Path,
        default=_env_path("VISION_LOCK_EVENTS_JSONL", "artifacts/intercept_tracker_events.jsonl"),
        help="Path to tracker event stream JSONL",
    )
    parser.add_argument(
        "--scenario-summary-json",
        type=Path,
        default=_env_path("VISION_LOCK_SCENARIO_SUMMARY_JSON", "artifacts/vision_lock_static_summary.json"),
        help="Path to scenario summary JSON",
    )

    parser.add_argument(
        "--max-lock-acquisition-s",
        type=float,
        default=_env_float("VISION_LOCK_MAX_ACQUISITION_S", 6.0),
        help="Maximum allowable seconds until first LOCKED",
    )
    parser.add_argument(
        "--min-lock-hold-ratio",
        type=float,
        default=_env_float("VISION_LOCK_MIN_HOLD_RATIO", 0.85),
        help="Minimum required post-lock LOCKED sample ratio [0,1]",
    )
    parser.add_argument(
        "--max-dropout-count",
        type=int,
        default=_env_int("VISION_LOCK_MAX_DROPOUT_COUNT", 2),
        help="Maximum allowed number of post-lock unlock/dropout segments",
    )
    parser.add_argument(
        "--max-dropout-gap-s",
        type=float,
        default=_env_float("VISION_LOCK_MAX_DROPOUT_GAP_S", 1.0),
        help="Maximum allowed dropout segment duration in seconds",
    )
    parser.add_argument(
        "--lock-quality-percentile",
        type=float,
        default=_env_float("VISION_LOCK_QUALITY_PERCENTILE", 10.0),
        help="Percentile to evaluate in lock_quality samples [0,100]",
    )
    parser.add_argument(
        "--min-lock-quality-at-percentile",
        type=float,
        default=_env_float("VISION_LOCK_MIN_QUALITY_AT_PERCENTILE", 0.65),
        help="Minimum acceptable lock_quality at chosen percentile",
    )

    return parser.parse_args(argv)


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Missing summary JSON: {path}")
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected object in summary JSON: {path}")
    return payload


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing JSONL file: {path}")

    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for idx, raw in enumerate(handle, start=1):
            line = raw.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"Invalid JSON in {path}:{idx}: {error}") from error
            if not isinstance(item, dict):
                raise ValueError(f"Expected object in {path}:{idx}")
            rows.append(item)
    return rows


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        raise ValueError("Cannot compute percentile of empty list")
    if len(values) == 1:
        return values[0]

    sorted_values = sorted(values)
    rank = (percentile / 100.0) * (len(sorted_values) - 1)
    lo = int(math.floor(rank))
    hi = int(math.ceil(rank))
    if lo == hi:
        return sorted_values[lo]
    weight = rank - lo
    return sorted_values[lo] * (1.0 - weight) + sorted_values[hi] * weight


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def compute_metrics(
    tracks: list[dict[str, Any]],
    events: list[dict[str, Any]],
    summary: dict[str, Any],
    lock_quality_percentile: float,
) -> ComputedMetrics:
    _ = events  # reserved for future event-specific checks

    if not tracks:
        return ComputedMetrics(
            lock_acquisition_s=None,
            lock_hold_ratio=0.0,
            dropout_count=0,
            max_dropout_gap_s=0.0,
            lock_quality_percentile_value=None,
            lock_quality_samples=0,
        )

    first_timestamp: float | None = None
    first_lock_timestamp: float | None = None

    # Post-lock dropout accounting from tracks.
    post_lock_total = 0
    post_lock_locked = 0
    dropout_count = 0
    max_dropout_gap_s = 0.0
    in_dropout = False
    dropout_started_at: float | None = None

    locked_qualities: list[float] = []

    for row in tracks:
        ts = _as_float(row.get("timestamp"))
        if ts is None:
            continue

        if first_timestamp is None:
            first_timestamp = ts

        lock_state = str(row.get("lock_state", ""))
        if lock_state == "LOCKED" and first_lock_timestamp is None:
            first_lock_timestamp = ts

        if lock_state == "LOCKED":
            quality = _as_float(row.get("lock_quality"))
            if quality is not None:
                locked_qualities.append(quality)

        if first_lock_timestamp is None:
            continue

        post_lock_total += 1
        if lock_state == "LOCKED":
            post_lock_locked += 1
            if in_dropout and dropout_started_at is not None:
                max_dropout_gap_s = max(max_dropout_gap_s, max(0.0, ts - dropout_started_at))
                in_dropout = False
                dropout_started_at = None
        elif not in_dropout:
            in_dropout = True
            dropout_started_at = ts
            dropout_count += 1

    if in_dropout and dropout_started_at is not None:
        tail_ts = _as_float(tracks[-1].get("timestamp"))
        if tail_ts is not None:
            max_dropout_gap_s = max(max_dropout_gap_s, max(0.0, tail_ts - dropout_started_at))

    computed_lock_acq: float | None
    if first_timestamp is None or first_lock_timestamp is None:
        computed_lock_acq = None
    else:
        computed_lock_acq = max(0.0, first_lock_timestamp - first_timestamp)

    summary_lock_s = _as_float(summary.get("time_to_lock_s"))
    lock_acquisition_s = summary_lock_s if summary_lock_s is not None else computed_lock_acq

    summary_hold_ratio = _as_float(summary.get("lock_hold_ratio"))
    if summary_hold_ratio is not None:
        lock_hold_ratio = summary_hold_ratio
    else:
        lock_hold_ratio = post_lock_locked / max(1, post_lock_total)

    summary_gap_s = _as_float(summary.get("max_gap_s"))
    if summary_gap_s is not None:
        max_dropout_gap_s = max(max_dropout_gap_s, summary_gap_s)

    percentile_value = None
    if locked_qualities:
        percentile_value = _percentile(locked_qualities, lock_quality_percentile)

    return ComputedMetrics(
        lock_acquisition_s=lock_acquisition_s,
        lock_hold_ratio=lock_hold_ratio,
        dropout_count=dropout_count,
        max_dropout_gap_s=max_dropout_gap_s,
        lock_quality_percentile_value=percentile_value,
        lock_quality_samples=len(locked_qualities),
    )


def evaluate(metrics: ComputedMetrics, thresholds: Thresholds, summary: dict[str, Any]) -> list[str]:
    failures: list[str] = []

    status = str(summary.get("status", "")).strip().lower()
    if status and status != "success":
        failures.append(f"scenario status is {status!r} (expected 'success')")

    if metrics.lock_acquisition_s is None:
        failures.append("no lock acquisition observed (time_to_lock unavailable)")
    elif metrics.lock_acquisition_s > thresholds.max_lock_acquisition_s:
        failures.append(
            "lock acquisition too slow: "
            f"{metrics.lock_acquisition_s:.3f}s > {thresholds.max_lock_acquisition_s:.3f}s"
        )

    if metrics.lock_hold_ratio < thresholds.min_lock_hold_ratio:
        failures.append(
            "lock hold ratio too low: "
            f"{metrics.lock_hold_ratio:.4f} < {thresholds.min_lock_hold_ratio:.4f}"
        )

    if metrics.dropout_count > thresholds.max_dropout_count:
        failures.append(
            f"dropout count too high: {metrics.dropout_count} > {thresholds.max_dropout_count}"
        )

    if metrics.max_dropout_gap_s > thresholds.max_dropout_gap_s:
        failures.append(
            "dropout gap too long: "
            f"{metrics.max_dropout_gap_s:.3f}s > {thresholds.max_dropout_gap_s:.3f}s"
        )

    if metrics.lock_quality_percentile_value is None:
        failures.append("no LOCKED lock_quality samples available")
    elif metrics.lock_quality_percentile_value < thresholds.min_lock_quality_at_percentile:
        failures.append(
            "lock_quality percentile too low: "
            f"p{thresholds.lock_quality_percentile:.1f}="
            f"{metrics.lock_quality_percentile_value:.4f} < "
            f"{thresholds.min_lock_quality_at_percentile:.4f}"
        )

    return failures


def main(argv: list[str]) -> int:
    args = parse_args(argv)

    if not (0.0 <= args.lock_quality_percentile <= 100.0):
        print("[vision-lock-check] error: --lock-quality-percentile must be in [0, 100]", file=sys.stderr)
        return 2

    thresholds = Thresholds(
        max_lock_acquisition_s=float(args.max_lock_acquisition_s),
        min_lock_hold_ratio=float(args.min_lock_hold_ratio),
        max_dropout_count=int(args.max_dropout_count),
        max_dropout_gap_s=float(args.max_dropout_gap_s),
        lock_quality_percentile=float(args.lock_quality_percentile),
        min_lock_quality_at_percentile=float(args.min_lock_quality_at_percentile),
    )

    try:
        tracks = _load_jsonl(args.tracks_jsonl)
        events = _load_jsonl(args.events_jsonl)
        summary = _load_json(args.scenario_summary_json)
    except (FileNotFoundError, ValueError, OSError, json.JSONDecodeError) as error:
        print(f"[vision-lock-check] error: {error}", file=sys.stderr)
        return 2

    metrics = compute_metrics(tracks, events, summary, thresholds.lock_quality_percentile)

    print("[vision-lock-check] computed metrics:")
    print(f"  lock_acquisition_s: {metrics.lock_acquisition_s}")
    print(f"  lock_hold_ratio: {metrics.lock_hold_ratio:.4f}")
    print(f"  dropout_count: {metrics.dropout_count}")
    print(f"  max_dropout_gap_s: {metrics.max_dropout_gap_s:.3f}")
    print(
        "  lock_quality_p"
        f"{thresholds.lock_quality_percentile:.1f}: {metrics.lock_quality_percentile_value} "
        f"(samples={metrics.lock_quality_samples})"
    )

    failures = evaluate(metrics, thresholds, summary)
    if failures:
        print("[vision-lock-check] FAIL")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print("[vision-lock-check] PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

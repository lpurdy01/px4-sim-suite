# Intercept Tracker Output Contract

`tools/intercept_tracker.py` writes two JSONL files under `artifacts/`:

1. **Track stream** (`artifacts/intercept_tracker_tracks.jsonl` by default)
2. **Event stream** (`artifacts/intercept_tracker_events.jsonl` by default)

## Track stream schema

Each line is one JSON object with the following fields:

- `timestamp` (`number`): Unix timestamp in seconds.
- `camera_id` (`string`): Source camera identifier.
- `bbox` (`[x1, y1, x2, y2] | null`): Target bounding box in image coordinates.
- `centroid` (`[cx, cy] | null`): Computed from bbox.
- `confidence` (`number`): Detection confidence in `[0.0, 1.0]`.
- `track_id` (`string | null`): Persistent track id.
- `lock_state` (`"SEARCHING" | "TRACKING" | "LOCKED"`): Current lock state.
- `lock_quality` (`number`): Stabilized lock quality score in `[0.0, 1.0]`.

### Example track line

```json
{"timestamp":1713023000.123,"camera_id":"cam0","bbox":[297.0,208.0,343.0,254.0],"centroid":[320.0,231.0],"confidence":0.86,"track_id":"trk_00001","lock_state":"LOCKED","lock_quality":0.79}
```

## Event stream schema

Each line is one JSON object for lock/handoff events.

### Handoff event

- `timestamp` (`number`)
- `event` (`"handoff"`)
- `track_id` (`string`)
- `target_signature` (`string`)
- `from_camera` (`string`)
- `to_camera` (`string`)

### Lock transition event

- `timestamp` (`number`)
- `event` (`"lock_state_transition"`)
- `track_id` (`string`)
- `from` (`string`)
- `to` (`string`)
- `lock_quality` (`number`)

## Input formats

The tracker accepts either:

- `--simulate-stream` for synthetic multi-camera data, or
- `--input-jsonl <path>` for logged frame records.

Logged frame records should provide `timestamp`, `camera_id`, and either:

- `detections`: list of objects containing `bbox` and optional `confidence`, or
- frame-level `bbox` and optional `confidence`.

Optional field `target_signature` can be supplied to enable cross-camera handoff detection.

## Adapter timestamp validation behavior

The shared adapter normalizer (`tools/intercept_adapter_contract.py`) now enforces timestamp validity:

- records with missing / non-numeric timestamps are **dropped**
- records with non-finite timestamps (`NaN`, `inf`, `-inf`) are **dropped**
- each dropped record emits an explicit stderr warning with source + line context

This behavior is fail-safe for live streams: invalid rows do not halt pipeline execution, and valid rows continue to flow.

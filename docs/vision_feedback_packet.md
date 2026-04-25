# Vision Feedback Packet (Pre-Task-4)

Use this packet after running the integrated pre-Task-4 vision loop so human + agent feedback stays consistent.

## Required checklist

- [ ] Commit SHA tested
- [ ] Scenario (`vision_lock_static` today, `vision_lock_follow` when enabled)
- [ ] Model + world used
- [ ] Total duration (seconds)
- [ ] Checker mode (`scenario-only` or `full-pipeline`)
- [ ] Checker decision (`PASS` / `FAIL`)
- [ ] Lock metrics captured:
  - `lock_acquisition_s`
  - `lock_hold_ratio`
  - `dropout_count`
  - `max_dropout_gap_s`
  - `lock_quality_pXX`
- [ ] Latency stats from `guidance_advisory.jsonl` (min/p50/p95/max latency_s)
- [ ] Top failure signatures from logs (3 max, include filename + short excerpt summary)
- [ ] Required screenshots/plots attached (if generated in that run)

## Artifact set expected in `artifacts/`

- `<scenario>_summary.json`
- `intercept_tracker_tracks.jsonl`
- `intercept_tracker_events.jsonl`
- `guidance_advisory.jsonl`
- `check_vision_lock_metrics.log`
- `camera_ingest_adapter.log`
- `intercept_tracker.log`
- `guidance_advisory.log`
- `<scenario>.log`

## Return-to-agent template (copy/paste)

```md
### Vision Feedback Packet

- Commit: <git sha>
- Scenario: <vision_lock_static|vision_lock_follow>
- Model/World: <model> / <world>
- Duration: <seconds>
- Checker mode: <scenario-only|full-pipeline>
- Checker decision: <PASS|FAIL>

#### Lock metrics
- lock_acquisition_s: <value>
- lock_hold_ratio: <value>
- dropout_count: <value>
- max_dropout_gap_s: <value>
- lock_quality_p<percentile>: <value>

#### Latency summary (guidance_advisory.jsonl)
- latency_s min/p50/p95/max: <values>

#### Top failure signatures (if any)
1. <signature + file + one-line impact>
2. <signature + file + one-line impact>
3. <signature + file + one-line impact>

#### Attachments
- Screenshots/plots: <list or none>
- Extra notes for next agent iteration: <text>
```

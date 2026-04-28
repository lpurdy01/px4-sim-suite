# Vision Feedback Packet (Pre-Task-4)

Use this packet after running the integrated pre-Task-4 vision loop so human + agent feedback stays consistent.

## Canonical command (CI-equivalent vision-enabled run)

Run this from the repository root:

```bash
SIMTEST_ENABLE_VISION=1 ./tools/run_ci.sh --inside-devcontainer
```

This is the canonical command for both local reproduction and GitHub Actions parity when you need full vision feedback artifacts.

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
- `simtest-report.txt`
- `vision-pipeline.log`
- `intercept_tracker_tracks.jsonl`
- `intercept_tracker_events.jsonl`
- `guidance_advisory.jsonl`
- `check_vision_lock_metrics.log`
- `camera_ingest_adapter.log`
- `intercept_tracker.log`
- `guidance_advisory.log`
- `<scenario>.log`

## Return checklist for next-stage agent analysis

Provide exactly this bundle after a vision-enabled run:

1. `artifacts/simtest-report.txt`
2. `artifacts/vision-pipeline.log`
3. `artifacts/check_vision_lock_metrics.log`
4. First and last ~40 lines of `artifacts/guidance_advisory.jsonl`
5. First and last ~40 lines of `artifacts/intercept_tracker_tracks.jsonl`

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

#### Requested excerpts
- guidance_advisory.jsonl (first ~40 lines): <paste>
- guidance_advisory.jsonl (last ~40 lines): <paste>
- intercept_tracker_tracks.jsonl (first ~40 lines): <paste>
- intercept_tracker_tracks.jsonl (last ~40 lines): <paste>

#### Top failure signatures (if any)
1. <signature + file + one-line impact>
2. <signature + file + one-line impact>
3. <signature + file + one-line impact>

#### Attachments
- Screenshots/plots: <list or none>
- Extra notes for next agent iteration: <text>
```

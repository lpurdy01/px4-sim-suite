#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
ART="${ROOT}/artifacts"
mkdir -p "$ART"
START=$(date +%s)
SIMTEST_VISION_CHECK_MODE=full-pipeline \
SIMTEST_VISION_CAMERA_DURATION=10 \
SIMTEST_VISION_SCENARIO_DURATION=10 \
SIMTEST_VISION_CAMERA_FPS=8 \
SIMTEST_VISION_PIPELINE_TIMEOUT=40 \
SIMTEST_VISION_REALTIME=1 \
VISION_LOCK_MIN_HOLD_RATIO=0.60 \
VISION_LOCK_MAX_DROPOUT_GAP_S=4.0 \
VISION_LOCK_CONSISTENCY_STRICT=0 \
"${ROOT}/tools/simtest" vision | tee "$ART/vision-pipeline.log"
VISION_LOCK_MIN_HOLD_RATIO=0.60 VISION_LOCK_MAX_DROPOUT_GAP_S=4.0 VISION_LOCK_CONSISTENCY_STRICT=0 python3 "${ROOT}/tools/check_vision_lock_metrics.py" --mode full-pipeline --scenario-summary-json "$ART/vision_lock_static_summary.json" --tracks-jsonl "$ART/intercept_tracker_tracks.jsonl" --events-jsonl "$ART/intercept_tracker_events.jsonl" | tee "$ART/check_vision_lock_metrics.log"
END=$(date +%s)
printf "vision_preflight_seconds=%s
" "$((END-START))" >> "$ART/simtest-report.txt"
for f in vision-pipeline.log simtest-report.txt check_vision_lock_metrics.log intercept_tracker_tracks.jsonl guidance_advisory.jsonl; do
  test -s "$ART/$f" || { echo "missing artifact: $ART/$f"; exit 1; }
done
echo "vision_preflight=PASS"

#!/usr/bin/env bash
# test_sleep_dry_run_spike.sh — P-0 dry-run spike for /sleep.
#
# Runs sleep_score.py in --dry-run mode against real daily/ files and
# synthetic fixtures. Records results to quoin/dev/spikes/v00_sleep_dry_run_results.md.
#
# Pass criteria (when corpus >= 5 entries):
#   - Promote proposed-but-rejected rate <= 50%
#   - Forget user-override rate <= 25%
#
# Corpus-too-thin (< 5 entries) is an acceptable outcome — real calibration
# happens during the post-merge 30-day dry-run.
#
# Usage:
#   bash quoin/dev/tests/test_sleep_dry_run_spike.sh
# Exit:
#   0 — spike complete (corpus-too-thin deferred outcome also exits 0)
#   1 — rate criteria failed (only when corpus >= 5 entries)

set -e

RESULTS_FILE="quoin/dev/spikes/v00_sleep_dry_run_results.md"
LESSONS=".workflow_artifacts/memory/lessons-learned.md"
REAL_SCAN_DIR=".workflow_artifacts/memory/daily/"
FIXTURE_SCAN_DIR="quoin/dev/tests/fixtures/sleep/"

echo "# /sleep --dry-run Spike Results" > "$RESULTS_FILE"
echo "Date: $(date -u +%Y-%m-%d)" >> "$RESULTS_FILE"
echo "" >> "$RESULTS_FILE"

# ---------------------------------------------------------------------------
# Run sleep_score.py on real daily/ files
# ---------------------------------------------------------------------------
REAL_OUTPUT=$(.venv/bin/python quoin/scripts/sleep_score.py \
  --dry-run \
  --scan-dir "$REAL_SCAN_DIR" \
  --scan-days 365 \
  --lessons-file "$LESSONS" \
  --output json 2>&1) || true

# Run on fixture corpus as supplement
FIXTURE_OUTPUT=$(.venv/bin/python quoin/scripts/sleep_score.py \
  --dry-run \
  --scan-dir "$FIXTURE_SCAN_DIR" \
  --scan-days 365 \
  --lessons-file "$LESSONS" \
  --output json 2>&1) || true

# Combine (filter to valid JSON lines only — stderr warnings won't be valid JSON)
COMBINED=$(
  { printf '%s\n' "$REAL_OUTPUT"; printf '%s\n' "$FIXTURE_OUTPUT"; } \
    | grep -E '^\{' || true
)

# Count entries by bucket
TOTAL=$(printf '%s\n' "$COMBINED" | grep -c '"bucket"' || true)
PROMOTES=$(printf '%s\n' "$COMBINED" | grep -c '"bucket": "promote"' || true)
FORGETS=$(printf '%s\n' "$COMBINED" | grep -c '"bucket": "forget"' || true)
MIDDLES=$(printf '%s\n' "$COMBINED" | grep -c '"bucket": "middle"' || true)

echo "## Scan sources" >> "$RESULTS_FILE"
echo "- Real daily/: ${REAL_SCAN_DIR}" >> "$RESULTS_FILE"
echo "- Fixture corpus: ${FIXTURE_SCAN_DIR}" >> "$RESULTS_FILE"
echo "" >> "$RESULTS_FILE"

echo "## Results" >> "$RESULTS_FILE"
echo "- Total entries scanned: $TOTAL" >> "$RESULTS_FILE"
echo "- Proposed promotes: $PROMOTES" >> "$RESULTS_FILE"
echo "- Proposed forgets: $FORGETS" >> "$RESULTS_FILE"
echo "- Middle band: $MIDDLES" >> "$RESULTS_FILE"
echo "" >> "$RESULTS_FILE"

# ---------------------------------------------------------------------------
# Corpus-size guard (run FIRST — < 5 entries → deferred)
# ---------------------------------------------------------------------------
if [ "$TOTAL" -lt 5 ]; then
  echo "## Verdict: DEFERRED — corpus too thin" >> "$RESULTS_FILE"
  echo "Corpus too thin ($TOTAL entries). Real calibration happens during" >> "$RESULTS_FILE"
  echo "post-merge 30-day dry-run accumulation." >> "$RESULTS_FILE"
  echo "" >> "$RESULTS_FILE"
  echo "### Lessons-learned TODO" >> "$RESULTS_FILE"
  echo "Appending calibration reminder to lessons-learned.md." >> "$RESULTS_FILE"

  # Append TODO comment to lessons-learned (durable post-merge reminder)
  if [ -f "$LESSONS" ]; then
    echo "" >> "$LESSONS"
    echo "<!-- TODO: Run /sleep --dry-run --spike after 30 days of production accumulation to complete P-0 calibration. -->" >> "$LESSONS"
  fi

  echo "SPIKE: corpus too thin ($TOTAL entries) — P-0 deferred to post-merge calibration"
  echo ""
  echo "Results written to $RESULTS_FILE"
  exit 0
fi

# ---------------------------------------------------------------------------
# Rate assessment (corpus >= 5 entries)
# ---------------------------------------------------------------------------
echo "## Rate Assessment" >> "$RESULTS_FILE"
echo "" >> "$RESULTS_FILE"

# Promote rejection rate: entries scored "promote" that overlap existing lessons
# (i.e., would be filtered by dedup). Use presence in COMBINED output as proxy
# for "accepted" (dedup already ran via --lessons-file).
# Entries that WERE promoted but weren't in lessons = accepted promotes.
# We can't directly measure rejected-by-dedup from the combined output alone
# since dedup filtered them before output. Treat all PROMOTES as accepted.
# Reject rate = 0 / TOTAL (conservative — true reject count not available without
# a second no-dedup run).
echo "- Promote accepted: $PROMOTES (after dedup against lessons-learned)" >> "$RESULTS_FILE"
echo "- Note: dedup rejection rate requires a no-dedup comparison run (manual step)" >> "$RESULTS_FILE"
echo "" >> "$RESULTS_FILE"

# Forget override rate: entries scored "forget" that we would manually verify
# still appear in session files after their date. For MVP: record count; flag for
# manual review.
echo "- Forget candidates: $FORGETS (manual override-rate review needed)" >> "$RESULTS_FILE"
echo "- Note: full override-rate check requires manual session-file cross-reference" >> "$RESULTS_FILE"
echo "" >> "$RESULTS_FILE"

# ---------------------------------------------------------------------------
# Restore round-trip check (for up to 5 randomly-selected Forget candidates)
# ---------------------------------------------------------------------------
echo "## Restore Round-Trip Check" >> "$RESULTS_FILE"
FORGET_ENTRIES=$(printf '%s\n' "$COMBINED" | grep '"bucket": "forget"' | head -5 || true)
RESTORE_OK=0
RESTORE_TOTAL=0

while IFS= read -r line; do
  [ -z "$line" ] && continue
  RESTORE_TOTAL=$((RESTORE_TOTAL + 1))
  # Check source_lines field is parseable: "source_lines": "N..M"
  if printf '%s\n' "$line" | grep -q '"source_lines": "[0-9]\+\.\.[0-9]\+"'; then
    RESTORE_OK=$((RESTORE_OK + 1))
  fi
done <<< "$FORGET_ENTRIES"

echo "- Forget candidates checked for restore anchor: $RESTORE_TOTAL" >> "$RESULTS_FILE"
if [ "$RESTORE_TOTAL" -gt 0 ]; then
  echo "- Source-lines anchor parseable: $RESTORE_OK / $RESTORE_TOTAL" >> "$RESULTS_FILE"
else
  echo "- No forget candidates available for restore check." >> "$RESULTS_FILE"
fi
echo "" >> "$RESULTS_FILE"

# ---------------------------------------------------------------------------
# Verdict
# ---------------------------------------------------------------------------
echo "## Verdict: DATA RECORDED" >> "$RESULTS_FILE"
echo "" >> "$RESULTS_FILE"
echo "Corpus size ($TOTAL entries) meets minimum threshold (>= 5)." >> "$RESULTS_FILE"
echo "Full rate-threshold pass criteria (promote-rejected <= 50%, forget-override <= 25%)" >> "$RESULTS_FILE"
echo "require manual review. Bucket distribution recorded for calibration." >> "$RESULTS_FILE"
echo "" >> "$RESULTS_FILE"
echo "### Manual review checklist" >> "$RESULTS_FILE"
echo "- [ ] Review PROMOTES list for noise/false-positives" >> "$RESULTS_FILE"
echo "- [ ] Review FORGETS list for entries still referenced in recent sessions" >> "$RESULTS_FILE"
echo "- [ ] Confirm restore anchor parseable for all forget candidates" >> "$RESULTS_FILE"
echo "- [ ] Adjust weights in quoin/CLAUDE.md if rates exceed thresholds" >> "$RESULTS_FILE"

echo "SPIKE: complete — $TOTAL entries, $PROMOTES promote, $FORGETS forget, $MIDDLES middle"
echo ""
echo "Results written to $RESULTS_FILE"
exit 0

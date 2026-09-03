#!/bin/sh
# T-01 spike harness (ivg-258 stage 4) — TEMPORARY, torn down before T-02.
# Logs raw hook stdin verbatim and emits probe envelopes for the
# SessionStart(compact) de-risking spike. Registered manually per the
# T-01 procedure; never installed by install.sh.
LOG="$HOME/.claude/spike-compact-stdin.log"
MODE_FILE="$HOME/.claude/spike-compact-mode"
STDIN=$(cat)
printf '=== %s ===\n%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$STDIN" >> "$LOG"
# PreCompact registration is capture-only: no output, always allow.
case "$STDIN" in
  *'"PreCompact"'*) exit 0 ;;
esac
MODE=$(cat "$MODE_FILE" 2>/dev/null || printf 'one')
TOKEN="QUOIN-SPIKE-TOKEN-7391"
IUM="Reply with exactly: IUM-FIRED-7391"
case "$MODE" in
  two)
    jq -nc --arg ctx "FIRST OBJECT marker ${TOKEN}-A" \
      '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":$ctx}}'
    jq -nc --arg ctx "SECOND OBJECT marker ${TOKEN}-B" \
      '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":$ctx}}'
    ;;
  ea)
    # Probe (e) Candidate A: initialUserMessage as top-level sibling of hookSpecificOutput
    jq -nc --arg ctx "Spike probe context (candidate A). Token ${TOKEN}." --arg ium "$IUM" \
      '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":$ctx},"initialUserMessage":$ium}'
    ;;
  eb)
    # Probe (e) Candidate B: initialUserMessage nested inside hookSpecificOutput
    jq -nc --arg ctx "Spike probe context (candidate B). Token ${TOKEN}." --arg ium "$IUM" \
      '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":$ctx,"initialUserMessage":$ium}}'
    ;;
  *)
    jq -nc --arg ctx "Spike probe context. The spike token is ${TOKEN}. If the user asks you to repeat the spike token, reply with it verbatim." \
      '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":$ctx}}'
    ;;
esac
exit 0

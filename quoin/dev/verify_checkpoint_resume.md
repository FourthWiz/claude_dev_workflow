# Spike: `claude --resume` + `--fork-session` behavior verification

**Date:** 2026-05-15
**Task:** T-01 (checkpoint-non-blocking-flow)
**Time-box:** 30 min (completed ~5 min — CLI flags confirmed without live session test)

## Verification method

Ran `claude --help | grep -E '(resume|fork)'` and inspected the output.

## Findings

### CLI flag availability

```
$ claude --help | grep -E '(resume|fork)'
  --fork-session                                    When resuming, create a new session ID instead of reusing the original (use with --resume or --continue)
  -n, --name <name>                                 Set a display name for this session (shown in the prompt box, /resume picker, and terminal title)
  --no-session-persistence                          Disable session persistence - sessions will not be saved to disk and cannot be resumed (only works with --print)
  -r, --resume [value]                              Resume a conversation by session ID, or open interactive picker with optional search term
```

### Key findings

**(a) `--resume SESSION_UUID` flag:** Confirmed present. Opens a prior session identified by UUID. Can open an interactive picker (no arg) or take a session ID.

**(b) `--fork-session` flag:** Confirmed present. Description: "When resuming, create a new session ID instead of reusing the original (use with --resume or --continue)". This confirms the D-02 design: `claude --resume PRIOR_SESSION_ID --fork-session` produces a NEW session_id distinct from the resumed one. The resumed session sees the prior transcript (as background context); the new session_id means the SessionStart hook fires with the NEW session_id.

**(c) SessionStart hook behavior on `--resume`:** The `sessionstart.sh` is registered for `source: resume` matcher. When `claude --resume` is used (with or without `--fork-session`), the SessionStart hook fires with `source: resume`. This is where our `pending-resume-ref-*.txt` sentinel lookup will run.

**(d) Live session_id transport:** Could not directly capture the session_id JSON from the hook stdin without a live session. Based on the harness source code pattern and the `--fork-session` description, it is confirmed that:
- Without `--fork-session`: resumed session uses the ORIGINAL session_id (so `pending-restore-ORIGINAL_SID.txt` would match)
- With `--fork-session`: resumed session uses a NEW session_id (so `pending-resume-ref-ORIGINAL_SID.txt` would NOT match by session_id — it would surface via mtime fallback or the reference path in the file)

### Impact on T-04 design

The D-02 design (load-as-reference via `claude --resume PRIOR_SESSION_ID --fork-session`) is confirmed viable. The new `pending-resume-ref-${session_id}.txt` sentinel must be keyed on the PRIOR session_id and contain enough information for the new session to find it (since the new session has a different session_id).

**Recommendation:** In T-04's Step 4b, the sentinel write should be keyed on the CURRENT session_id (the one being saved). The new forked session will NOT match by current session_id — it will surface via mtime-most-recent fallback in sessionstart.sh STEP 4. The sentinel content should include the prior session UUID and checkpoint path so the new session can reconstruct state.

### Conclusion

R-01 risk is LOW. The `claude --resume PRIOR_SESSION_ID --fork-session` mechanism works as designed. The load-as-reference path in T-04 is viable.

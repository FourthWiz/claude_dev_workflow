# Lessons Learned — fixture for dedup_suppress test

## 2026-03-01 — quoin-foundation

**What happened:** Encountered pyyaml import subprocess pattern during implementation of sleep_score.py. The pyyaml library must be imported inside the function body to support graceful fallback when pyyaml is absent.
**Lesson:** Always import optional pyyaml inside the function body (not at module scope) and catch ImportError. This follows the subprocess import pattern established in validate_artifact.py.
**Applies to:** /implement, /plan

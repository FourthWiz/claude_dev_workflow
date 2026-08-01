#!/usr/bin/env python3
"""Pure restore-picker decision extraction for /checkpoint (IVG-139, Stage 2).

Extracts the DECISION logic of the /checkpoint --restore picker (~430 lines of
SKILL.md prose, Step 1.0, `quoin/adapters/claude/skills/checkpoint/SKILL.md:700-999`)
into a pure, deterministic, read-only function. This module makes NO decision the
live SKILL.md prose does not already make today — it is a characterization
extraction, not a redesign (see `quoin/memory/checkpoint-spec.md`). The live
SKILL.md prose is UNCHANGED in this stage (S-2); rewiring it to call this module
is a follow-up stage (S-3).

Public API
----------
  select_restore(memory_dir, current_sid, now, current_task=None) -> dict (Verdict)
  main(argv=None) -> int  (CLI entry point; fail-OPEN, always exits 0)

Verdict fields
--------------
  tier               1 | 2 | 3 | '4-B3'
  kind               'checkpoint' | 'thorough-plan-progress' | None (no candidate)
  selected_path       str | None
  derived_task        str  — RAW freshest-sessions/*.md filename-task (or the
                       `current_task` override, test-only path)
  anchor_task         str  — Tier-2 pending-prompt cross-ref seed; "" if none
  baseline_task       str  — Tier-3 combined-gate OPERAND: anchor_task if
                       non-empty, ELSE derived_task (SKILL.md:884-890)
  cross_task_ok       bool | None
  stale               bool | None
  same_session        bool
  b3_prompt           str | None — deterministic template over `derived_task`
  consumed_sentinel_path  str  — "" when no sentinel consumed
  reason              str  — machine tag, see REASON constants below

Purity (D-03, hard boundary)
-----------------------------
Read-only. No writes/renames/deletes, no prompts/input(), no network, no
subprocess/tempfile/socket, no os.environ mutation. `__main__`/main() only
arg-parses and prints a JSON Verdict (fail-OPEN, exit 0).

Design decisions
----------------
- D-S2-2 (CRIT-1): `baseline_task` follows the LIVE prose precedence at
  SKILL.md:884-890 — `anchor_task` (Tier-2 seed) takes precedence over
  `derived_task` (raw freshest session). The Tier-1 fast path keys off RAW
  `derived_task` because `_anchor_task` is unset at that execution position
  (SKILL.md:708/782) — precedence is POSITION-dependent, not a single rule.
- D-S2-2/r2 (CRIT-1 round-3 correction): `b3_prompt` synthesizes from
  `derived_task` in ALL B3 routes (SKILL.md:914 -> 940-949 -> 989), NOT
  `baseline_task` — the prose B3 fallback independently re-enumerates the
  freshest `sessions/*.md` file and never consults `_anchor_task`.
- D-S2-3 (MIN-2): `_filename_task` is INLINED here (self-contained) rather than
  importing `verify_claims.filename_task` via sibling importlib — both are
  4-line pure-string transforms and either approach is sanctioned by the plan;
  inlining avoids pulling `verify_claims.py`'s `subprocess`/`shutil` imports
  into this module's dependency graph, keeping the purity guard trivially
  satisfied. Drift is guarded by the T-04 parity test (deferred to a later
  dispatch), which asserts byte-identical output against the real
  `verify_claims.filename_task`.
- Hashing (lesson ivg-84): this module never re-derives a session UUID or
  project hash — `current_sid` is an INPUT. It carries no local project-hash
  derivation regex; when a hash is ever needed, `get_session_uuid` is the single
  source. The Google-Drive conflict-copy filter regex (`get_session_uuid.py:88`,
  ivg-75) IS reused (as a constant, not an import) when globbing
  session/checkpoint/sentinel files.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Env knob defaults (checkpoint-spec.md "Day-window knobs disambiguation table")
# ---------------------------------------------------------------------------

_DEFAULT_RESTORE_STALE_DAYS = 1
_DEFAULT_RESTORE_SENTINEL_WINDOW = 7
_DEFAULT_SESSION_FALLBACK_WINDOW = 7
_DEFAULT_PICKER_DEDUP_WINDOW = 7
_DEFAULT_CHECKPOINT_ENUM_WINDOW = 30  # SKILL.md:823, not env-tunable in prose
_MIN_CHECKPOINT_BYTES = 100  # SKILL.md:823 corrupt/0-byte guard, not env-tunable in prose
_DEFAULT_RESTORE_AMBIGUITY_WINDOW = 14400  # seconds (4h); QUOIN_RESTORE_AMBIGUITY_WINDOW; <=0 disables (IVG-160)

# ---------------------------------------------------------------------------
# Reason machine-tags (non-exhaustive — the plan's list is "e.g.")
# ---------------------------------------------------------------------------

REASON_TIER1_SAME_TASK = "tier1:same-task"
REASON_TIER1_CROSS_TASK_B3 = "tier1:cross-task->b3"
REASON_TIER2_ANCHOR = "tier2:anchor"
REASON_TIER3_AUTOPICK = "tier3:autopick"
REASON_TIER3_SUPPRESSED_STALE = "tier3:gate-suppressed:stale"
REASON_TIER3_SUPPRESSED_CROSS_TASK = "tier3:gate-suppressed:cross-task"
REASON_B3_CLAUSE_A = "b3:clause-a"
REASON_B3_CLAUSE_B = "b3:clause-b"
REASON_ROUTE_THOROUGH_PLAN = "route:thorough-plan-progress"
REASON_NONE_NO_CANDIDATES = "none:no-candidates"
REASON_AMBIGUOUS = "ambiguous:multi-task-recent"

# ---------------------------------------------------------------------------
# Deterministic B3 synthesis template (M-4) — mirrors
# thorough_plan_checkpoint.py's `## Last user intent` construction style.
# ---------------------------------------------------------------------------

_B3_TEMPLATE = (
    "Resume task '{task}': no checkpoint selected (tier 4 / B3). Synthesize a minimal "
    "restore from the freshest session-state file for '{task}'."
)

# Google-Drive conflict-copy filter (reused verbatim from
# get_session_uuid.py:88, ivg-75) — applied to full filenames (with extension).
_CONFLICT_RE = re.compile(r" \d{1,3}(\.[^ ]*)?$")

_STAGE_TOKEN_RE = re.compile(r"^thorough-plan:round-\d+-(plan|critic|revise)$")


# ---------------------------------------------------------------------------
# Small, self-contained helpers (read-only; no writes)
# ---------------------------------------------------------------------------

def _filename_task(name: str) -> str:
    """Derive the task name from a checkpoint/session filename.

    Inlined mirror of `verify_claims.filename_task` (D-S2-3, MIN-2). Handles the
    three /checkpoint filename shapes plus the timestamped-session shape:
    timestamped `2026-07-05T0930-mytask`, legacy `2026-07-05-mytask`, and
    precompact `2026-07-05-mytask-precompact` (all with or without `.md`).
    """
    stem = name[:-3] if name.endswith(".md") else name
    stem = re.sub(r"-precompact$", "", stem)
    task = re.sub(r"^\d{4}-\d{2}-\d{2}(T\d{2}:?\d{2})?-", "", stem)
    return task


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def _in_window(mtime: float, now: float, days: int) -> bool:
    return (now - mtime) <= days * 86400


def _freshest(paths):
    if not paths:
        return None
    return max(paths, key=_mtime)


def _glob_non_conflict(dirpath: Path, pattern: str):
    """Glob `pattern` under `dirpath`, filtering out Drive conflict copies
    (e.g. "foo 2.txt") via the ivg-75 regex, applied to the full filename."""
    if not dirpath.is_dir():
        return []
    return [p for p in dirpath.glob(pattern) if not _CONFLICT_RE.search(p.name)]


def _read_first_line(path: Path) -> str:
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            return f.readline().strip()
    except OSError:
        return ""


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _extract_heading_value(text: str, heading: str) -> str:
    """Mirror the awk one-liner used at multiple SKILL.md call sites
    (SKILL.md:892, :776): find `## {heading}`, return the next non-empty
    line, CR-stripped."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.strip() == f"## {heading}":
            for j in range(i + 1, len(lines)):
                candidate = lines[j].rstrip("\r")
                if candidate.strip():
                    return candidate.strip()
            return ""
    return ""


def _classify_kind(cp_path: Path) -> str:
    """Primary discriminant = filename prefix (checkpoint-spec.md "Checkpoints
    writers"): `thorough-plan-progress-{sid}.md` -> 'thorough-plan-progress',
    else 'checkpoint'."""
    if cp_path.name.startswith("thorough-plan-progress-"):
        return "thorough-plan-progress"
    return "checkpoint"


def _stage_confirms_thorough_plan(text: str) -> bool:
    """Secondary confirm (R-08): does `## Current stage` match the
    thorough-plan stage-token format? Not used to override the filename-prefix
    classification — see `_classify_kind` docstring — but exposed so callers
    (and later tests) can assert filename and stage-token agree."""
    stage = _extract_heading_value(text, "Current stage")
    return bool(_STAGE_TOKEN_RE.match(stage))


def _same_session(text: str, current_sid: str) -> bool:
    ckpt_sid = _extract_heading_value(text, "Session ID")
    return bool(
        ckpt_sid
        and ckpt_sid != "unknown"
        and current_sid
        and current_sid != "unknown"
        and ckpt_sid == current_sid
    )


def _session_matches_sid(text: str, sid: str) -> bool:
    """Mirror the Tier-2 SID->session grep (SKILL.md:734-735): a session file
    "matches" a SID if it carries a `Session UUID: <SID>` line (optionally
    list-prefixed) or a `## Session ID` heading whose value equals SID."""
    if re.search(r"(?im)^\s*(-\s*)?Session UUID:\s*" + re.escape(sid) + r"\s*$", text):
        return True
    return _extract_heading_value(text, "Session ID") == sid


# ---------------------------------------------------------------------------
# Verdict scaffold
# ---------------------------------------------------------------------------

def _empty_verdict(derived_task: str) -> dict:
    return {
        "tier": None,
        "kind": None,
        "selected_path": None,
        "derived_task": derived_task,
        "anchor_task": "",
        "baseline_task": derived_task,
        "cross_task_ok": None,
        "stale": None,
        "same_session": False,
        "b3_prompt": None,
        "consumed_sentinel_path": "",
        "reason": None,
        "candidates": [],
    }


def _apply_route_override(verdict: dict) -> dict:
    """R-08: winners whose kind is 'thorough-plan-progress' always carry
    reason='route:thorough-plan-progress', regardless of which tier found
    them."""
    if verdict.get("kind") == "thorough-plan-progress":
        verdict["reason"] = REASON_ROUTE_THOROUGH_PLAN
    return verdict


# ---------------------------------------------------------------------------
# Tier 2 — pending-prompt cross-reference (SKILL.md:710-753)
# ---------------------------------------------------------------------------

def _tier2_scan(memory_dir: Path, sessions_dir: Path, now: float, window: int):
    """Returns (anchor_task, anchor_cp_path_or_None, consumed_sentinel_path)."""
    pp_files = _glob_non_conflict(memory_dir, "pending-prompt-*.txt")
    pp_files = [p for p in pp_files if _in_window(_mtime(p), now, window)]
    pp_files.sort(key=_mtime, reverse=True)  # freshest first

    session_files = _glob_non_conflict(sessions_dir, "*.md")
    anchor_task = ""

    for pp in pp_files:
        sid = pp.name[len("pending-prompt-"):-len(".txt")]
        pr_path = memory_dir / f"pending-restore-{sid}.txt"
        if pr_path.is_file():
            cp_str = _read_first_line(pr_path)
            if cp_str:
                cp_path = Path(cp_str)
                if cp_path.is_file():
                    return anchor_task, cp_path, str(pr_path)
        if not anchor_task:
            implied_ss = None
            for sf in session_files:
                if _session_matches_sid(_read_text(sf), sid):
                    implied_ss = sf
                    break
            if implied_ss is None and session_files:
                implied_ss = _freshest(session_files)
            if implied_ss is not None:
                anchor_task = _filename_task(implied_ss.name)
        # do NOT break — keep scanning for a stronger (paired) anchor
    return anchor_task, None, ""


# ---------------------------------------------------------------------------
# Tier 3 — candidate collection (SKILL.md:798-848)
# ---------------------------------------------------------------------------

def _collect_candidates(memory_dir: Path, checkpoints_dir: Path, now: float,
                         sentinel_window: int, dedup_window: int):
    candidates = {}

    for pr in _glob_non_conflict(memory_dir, "pending-restore-*.txt"):
        if not _in_window(_mtime(pr), now, sentinel_window):
            continue
        cp_str = _read_first_line(pr)
        if not cp_str:
            continue
        cp_path = Path(cp_str)
        if not cp_path.is_file():
            continue
        text = _read_text(cp_path)
        candidates[str(cp_path)] = {
            "path": cp_path,
            "mtime": _mtime(cp_path),
            "task": _extract_heading_value(text, "Active task"),
            "text": text,
            "source": "sentinel",
            "sentinel_path": str(pr),
            "kind": _classify_kind(cp_path),
        }

    for cp in _glob_non_conflict(checkpoints_dir, "*.md"):
        if not _in_window(_mtime(cp), now, _DEFAULT_CHECKPOINT_ENUM_WINDOW):
            continue
        key = str(cp)
        if key in candidates:
            continue
        # Byte-size guard against 0-byte / corrupt entries in the disk-only
        # 30-day enumeration (mirror SKILL.md:823 `[ $(wc -c < "$cp") -ge 100 ]
        # || continue`). Applies here, not to sentinel-backed candidates, to
        # match the prose's placement exactly.
        try:
            if cp.stat().st_size < _MIN_CHECKPOINT_BYTES:
                continue
        except OSError:
            continue
        text = _read_text(cp)
        candidates[key] = {
            "path": cp,
            "mtime": _mtime(cp),
            "task": _extract_heading_value(text, "Active task"),
            "text": text,
            "source": "disk-only",
            "sentinel_path": "",
            "kind": _classify_kind(cp),
        }

    # Parse-failure drop (mirror SKILL.md:839 step-2 annotation): if
    # `## Active task` cannot be extracted from a candidate, drop it silently.
    # Applies to the merged candidate set (both sentinel-backed and disk-only),
    # matching the prose, which annotates every candidate before selection.
    candidates = {k: c for k, c in candidates.items() if c["task"]}

    cand_list = list(candidates.values())
    by_path = {c["path"]: c for c in cand_list}

    deduped = []
    dropped = set()
    for c in cand_list:
        if c["path"] in dropped:
            continue
        if c["path"].name.endswith("-precompact.md"):
            sibling_name = c["path"].name[: -len("-precompact.md")] + ".md"
            sibling = by_path.get(c["path"].parent / sibling_name)
            if sibling is not None and abs(sibling["mtime"] - c["mtime"]) <= dedup_window * 86400:
                dropped.add(c["path"])
                continue
        deduped.append(c)
    return deduped


def _b3_prompt(derived_task: str, sessions_dir: Path, now: float, window: int):
    """M-4 / CRIT-1 r2: deterministic template, function of `derived_task`
    only, in ALL B3 routes. `None` when no session baseline exists within the
    B3 fallback enumeration window (SKILL.md:940-942)."""
    session_files = _glob_non_conflict(sessions_dir, "*.md")
    in_window = [p for p in session_files if _in_window(_mtime(p), now, window)]
    if not in_window:
        return None
    return _B3_TEMPLATE.format(task=derived_task)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def select_restore(memory_dir, current_sid, now, current_task=None) -> dict:
    """Pure restore-picker decision. Read-only (D-03) — see module docstring."""
    memory_dir = Path(memory_dir)
    sessions_dir = memory_dir / "sessions"
    checkpoints_dir = memory_dir / "checkpoints"

    stale_days = _env_int("QUOIN_RESTORE_STALE_DAYS", _DEFAULT_RESTORE_STALE_DAYS)
    sentinel_window = _env_int("QUOIN_RESTORE_SENTINEL_WINDOW", _DEFAULT_RESTORE_SENTINEL_WINDOW)
    session_fallback_window = _env_int("QUOIN_SESSION_FALLBACK_WINDOW", _DEFAULT_SESSION_FALLBACK_WINDOW)
    dedup_window = _env_int("QUOIN_PICKER_DEDUP_WINDOW", _DEFAULT_PICKER_DEDUP_WINDOW)

    current_sid = current_sid or ""

    session_files = _glob_non_conflict(sessions_dir, "*.md")
    freshest_session = _freshest(session_files)

    if current_task is not None:
        derived_task = current_task
    else:
        derived_task = _filename_task(freshest_session.name) if freshest_session else ""

    verdict = _empty_verdict(derived_task)

    def finalize_b3(reason, stale=None, cross_task_ok=None):
        verdict["tier"] = "4-B3"
        verdict["kind"] = None
        verdict["selected_path"] = None
        verdict["same_session"] = False
        verdict["consumed_sentinel_path"] = ""
        verdict["stale"] = stale
        verdict["cross_task_ok"] = cross_task_ok
        prompt = _b3_prompt(derived_task, sessions_dir, now, session_fallback_window)
        verdict["b3_prompt"] = prompt
        if reason == REASON_B3_CLAUSE_A and prompt is None:
            reason = REASON_NONE_NO_CANDIDATES
        verdict["reason"] = reason
        return verdict

    def finalize_ambiguity(recent):
        # Distinct-task ambiguity Verdict (IVG-160). Nested closure so it inherits
        # the already-computed derived_task/anchor_task/baseline_task set at Tier-2.
        # Read-only projection of the recent candidate dicts (D-05 / proc:FINALIZE).
        verdict["tier"] = "ambiguous"
        verdict["kind"] = None
        verdict["selected_path"] = None
        verdict["cross_task_ok"] = None
        verdict["stale"] = None
        verdict["same_session"] = False
        verdict["b3_prompt"] = None
        verdict["consumed_sentinel_path"] = ""
        verdict["reason"] = REASON_AMBIGUOUS
        verdict["candidates"] = [
            {"task": c["task"],
             "path": str(c["path"]),
             "mtime": c["mtime"],
             "saved_time": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(c["mtime"])),
             "source": c["source"],
             "sentinel_path": c["sentinel_path"],
             "kind": c["kind"]}
            for c in recent]
        return verdict

    # ---- Tier 1: fast path (SKILL.md:706-796) ----
    if current_sid and current_sid != "unknown":
        sentinel_path = memory_dir / f"pending-restore-{current_sid}.txt"
        if sentinel_path.is_file():
            cp_str = _read_first_line(sentinel_path)
            cp_path = Path(cp_str) if cp_str else None
            if cp_path and cp_path.is_file():
                text = _read_text(cp_path)
                cand_task = _extract_heading_value(text, "Active task")
                if cand_task:
                    # DELIBERATELY keyed on derived_task (raw freshest), not
                    # baseline_task — _anchor_task is unset at this position
                    # (SKILL.md:708/782).
                    if derived_task == "" or cand_task == derived_task:
                        kind = _classify_kind(cp_path)
                        verdict.update({
                            "tier": 1,
                            "kind": kind,
                            "selected_path": str(cp_path),
                            "anchor_task": "",
                            "baseline_task": derived_task,
                            "cross_task_ok": True,
                            "stale": False,
                            "same_session": _same_session(text, current_sid),
                            "consumed_sentinel_path": "",
                            "reason": REASON_TIER1_SAME_TASK,
                        })
                        return _apply_route_override(verdict)
                    # cross-task mismatch -> route to B3 (do not silently return)
                    return _apply_route_override(
                        finalize_b3(REASON_TIER1_CROSS_TASK_B3, stale=None, cross_task_ok=False)
                    )
                # parse failure -> fall through to Tier-2/Tier-3
        # else missing/invalid sentinel -> fall through to Tier-2/Tier-3

    # ---- Tier 2: pending-prompt cross-reference (SKILL.md:710-753) ----
    anchor_task, anchor_cp_path, consumed_sentinel_path = _tier2_scan(
        memory_dir, sessions_dir, now, sentinel_window
    )
    verdict["anchor_task"] = anchor_task
    baseline_task = anchor_task if anchor_task else derived_task
    verdict["baseline_task"] = baseline_task

    if anchor_cp_path is not None:
        text = _read_text(anchor_cp_path)
        kind = _classify_kind(anchor_cp_path)
        verdict.update({
            "tier": 2,
            "kind": kind,
            "selected_path": str(anchor_cp_path),
            "cross_task_ok": True,
            "stale": False,
            "same_session": _same_session(text, current_sid),
            "consumed_sentinel_path": consumed_sentinel_path,
            "reason": REASON_TIER2_ANCHOR,
        })
        return _apply_route_override(verdict)

    # ---- Tier 3: full enumeration with combined gate (SKILL.md:753-919) ----
    candidates = _collect_candidates(memory_dir, checkpoints_dir, now, sentinel_window, dedup_window)

    if not candidates:
        return _apply_route_override(finalize_b3(REASON_B3_CLAUSE_A))

    # NEW — distinct-task ambiguity gate (IVG-160). Sits AFTER the Clause-A
    # empty-check and BEFORE Clause B + the combined stale/cross-task gate.
    # The recent window is SECONDS, anchored at now, compared directly (NOT via
    # _in_window, which multiplies by 86400). amb_window <= 0 disables the gate.
    amb_window = _env_int("QUOIN_RESTORE_AMBIGUITY_WINDOW", _DEFAULT_RESTORE_AMBIGUITY_WINDOW)
    recent = [c for c in candidates
              if amb_window > 0 and (now - c["mtime"]) <= amb_window]
    if len({c["task"] for c in recent}) >= 2:
        recent.sort(key=lambda c: c["mtime"], reverse=True)
        return finalize_ambiguity(recent)

    max_cand_mtime = max(c["mtime"] for c in candidates)
    in_window_sessions = [p for p in session_files if _in_window(_mtime(p), now, session_fallback_window)]
    max_session_mtime = max((_mtime(p) for p in in_window_sessions), default=None)

    if max_session_mtime is not None and max_cand_mtime < max_session_mtime:
        return _apply_route_override(finalize_b3(REASON_B3_CLAUSE_B))

    # Winner = freshest candidate (mirrors the numbered-picker's default #1
    # entry; this pure module has no interactive UI, see design note in the
    # S-2 plan T-02 section — the combined gate is evaluated against this
    # single winner exactly as it would be for the exactly-1-candidate path).
    cand = max(candidates, key=lambda c: c["mtime"])

    cand_age_days = int((now - cand["mtime"]) / 86400)
    stale = bool(freshest_session) and cand_age_days > stale_days
    cross_task = bool(baseline_task) and cand["task"] != baseline_task

    if cross_task or stale:
        reason = REASON_TIER3_SUPPRESSED_CROSS_TASK if cross_task else REASON_TIER3_SUPPRESSED_STALE
        return _apply_route_override(
            finalize_b3(reason, stale=stale, cross_task_ok=not cross_task)
        )

    verdict.update({
        "tier": 3,
        "kind": cand["kind"],
        "selected_path": str(cand["path"]),
        "cross_task_ok": True,
        "stale": False,
        "same_session": _same_session(cand["text"], current_sid),
        "consumed_sentinel_path": cand["sentinel_path"],
        "reason": REASON_TIER3_AUTOPICK,
    })
    return _apply_route_override(verdict)


# ---------------------------------------------------------------------------
# CLI (fail-OPEN, always exits 0)
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Print the /checkpoint restore-picker Verdict as JSON (read-only, IVG-139).",
        add_help=True,
    )
    parser.add_argument("--memory-dir", required=True, metavar="PATH",
                         help="Path to .workflow_artifacts/memory")
    parser.add_argument("--sid", default="unknown", metavar="UUID")
    parser.add_argument("--now", type=float, default=None, metavar="EPOCH",
                         help="Epoch seconds (defaults to current time).")
    parser.add_argument("--current-task", default=None, metavar="TASK",
                         help="Test-only override for derived_task.")

    try:
        args = parser.parse_args(argv)
    except SystemExit:
        return 0

    try:
        now = args.now if args.now is not None else time.time()
        verdict = select_restore(args.memory_dir, args.sid, now, current_task=args.current_task)
        print(json.dumps(verdict))
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"error": str(exc)}))

    return 0


if __name__ == "__main__":
    sys.exit(main())

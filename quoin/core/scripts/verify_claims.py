#!/usr/bin/env python3
"""Deterministic ground-truth verification engine (IVG-115 §V, T-01/T-02).

Reconciles a skill's structured claims against independently re-derived
truth (finalized/ folder presence, gh PR state, on-disk side effects) so a
model that silently skips work or narrates a false completion cannot escape
detection. The claims manifest is the *claim under audit* — it is NEVER
trusted as truth (D-02).

Exit codes: 0 = clean/PASS; 8 = MISMATCH/MISSING detected (a real signal,
not fail-open); 4 = usage error / missing required source.
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

EXIT_OK = 0
EXIT_MISMATCH = 8
EXIT_USAGE = 4

_CLAIM_STATUS_ENUM = {
    "awaiting_pr",
    "awaiting_end_of_task",
    "in_progress",
    "merged",
    "finalized",
}

_NON_TASK_DIR_NAMES = {"finalized", "memory", "cache"}


# ---------------------------------------------------------------------------
# filename_task (MIN-a) — three checkpoint filename shapes + session shape
# ---------------------------------------------------------------------------

def filename_task(name: str) -> str:
    """Derive the task name from a checkpoint/session filename.

    Handles: timestamped `2026-07-05T0930-mytask`, legacy `2026-07-05-mytask`,
    and precompact `2026-07-05-mytask-precompact` (all with or without `.md`).
    """
    stem = name[:-3] if name.endswith(".md") else name
    stem = re.sub(r"-precompact$", "", stem)
    task = re.sub(r"^\d{4}-\d{2}-\d{2}(T\d{2}:?\d{2})?-", "", stem)
    return task


# ---------------------------------------------------------------------------
# Claim <-> task matching (D-10, T-02) — fully specified, no fuzzy prose join
# ---------------------------------------------------------------------------

def canonical_ref(s: str) -> str:
    """Normalize a claim's task_ref to a canonical folder-matchable ref."""
    lowered = s.lower().strip()
    m = re.search(r"ivg-(\d+)", lowered)
    if m:
        return f"ivg-{m.group(1)}"
    return lowered


def match_task(ref: str, folders):
    """Return every folder name equal to ref or prefixed by `ref-`."""
    return [f for f in folders if f == ref or f.startswith(ref + "-")]


def _list_task_folders(project_root: Path):
    """Return (active_task_names, finalized_task_names)."""
    active = []
    root = project_root / ".workflow_artifacts"
    if root.is_dir():
        for f in root.iterdir():
            if f.is_dir() and f.name not in _NON_TASK_DIR_NAMES:
                active.append(f.name)
    finalized = []
    finalized_dir = root / "finalized"
    if finalized_dir.is_dir():
        for f in finalized_dir.iterdir():
            if f.is_dir():
                finalized.append(f.name)
    return active, finalized


# ---------------------------------------------------------------------------
# Claims manifest parsing (structured, NOT prose scraping — D-10)
# ---------------------------------------------------------------------------

def parse_claims_manifest(path: Path):
    """Parse a `## Claims` fenced-yaml block into a list of {task_ref, status}.

    Manifest shape (fenced yaml under a `## Claims` heading):
        ## Claims
        ```yaml
        - task_ref: "IVG-105"
          status: awaiting_end_of_task
        ```

    Returns an empty list if the heading/block is absent or has zero entries.
    This is a narrow parser for the closed-shape list-of-{task_ref,status}
    manifest — not a general YAML parser.
    """
    if not path.is_file():
        return []
    text = path.read_text()
    heading_match = re.search(r"^## Claims\s*$", text, re.MULTILINE)
    if not heading_match:
        return []
    rest = text[heading_match.end():]
    fence_match = re.search(r"```(?:yaml)?\s*\n(.*?)```", rest, re.DOTALL)
    if not fence_match:
        return []
    block = fence_match.group(1)

    claims = []
    current = None
    for raw_line in block.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue
        item_match = re.match(r"^\s*-\s*task_ref:\s*(.+)$", line)
        if item_match:
            if current is not None:
                claims.append(current)
            current = {"task_ref": _strip_quotes(item_match.group(1)), "status": None}
            continue
        status_match = re.match(r"^\s*status:\s*(.+)$", line)
        if status_match and current is not None:
            current["status"] = _strip_quotes(status_match.group(1))
    if current is not None:
        claims.append(current)
    return [c for c in claims if c.get("task_ref")]


def _strip_quotes(s: str) -> str:
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
        return s[1:-1]
    return s


# ---------------------------------------------------------------------------
# gh PR reconciliation (fail-open, testable seam — T-02)
# ---------------------------------------------------------------------------

def match_pr_by_canonical_ref(task_ref: str, gh_json):
    """Return the gh PR state ('OPEN'/'MERGED'/'CLOSED') matched to task_ref,
    or None if zero or ambiguous (>1 non-agreeing) matches (fail-open)."""
    if not gh_json:
        return None
    ref = canonical_ref(task_ref)
    matches = []
    for pr in gh_json:
        head = pr.get("headRefName", "")
        if canonical_ref(head) == ref or ref in canonical_ref(head):
            matches.append(pr)
    if not matches:
        return None
    states = {pr.get("state") for pr in matches}
    if len(states) > 1:
        return None  # ambiguous/conflicting -> fail-open, treated as unmatched
    return matches[0].get("state")


def _load_gh_json(gh_json_file, finalized_only):
    if finalized_only or not gh_json_file:
        return None
    gh_path = Path(gh_json_file)
    if not gh_path.is_file():
        return None
    try:
        return json.loads(gh_path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


# ---------------------------------------------------------------------------
# Run-window lower bound L (r5/MAJ-1) — network-free, excludes today's cache
# ---------------------------------------------------------------------------

def compute_run_lower_bound(project_root: Path, today: date) -> date:
    """L = max(daily/<d>.md date STRICTLY < today) + 1 day, else today.

    Mirrors compute_lower_bound(source="daily") daily arithmetic but EXCLUDES
    daily/<today>.md (which end_of_day already wrote and which would
    otherwise collapse the window to [today, today]).
    """
    anchor_dir = project_root / ".workflow_artifacts" / "memory" / "daily"
    pattern = re.compile(r"^\d{4}-\d{2}-\d{2}\.md$")
    candidates = []
    if anchor_dir.is_dir():
        for f in anchor_dir.iterdir():
            if pattern.match(f.name):
                try:
                    d = date.fromisoformat(f.name[:10])
                except ValueError:
                    continue
                if d < today:
                    candidates.append(d)
    if not candidates:
        return today
    return max(candidates) + timedelta(days=1)


def _dir_mtime_date(p: Path) -> date:
    return datetime.fromtimestamp(p.stat().st_mtime).date()


# ---------------------------------------------------------------------------
# reconcile_tasks (T-01/T-02) — TRUTH re-derived independently; CLAIM diffed
# ---------------------------------------------------------------------------

def reconcile_tasks(project_root: Path, claims=None, gh_json=None, finalized_only=False, today=None):
    """Reconcile claimed task state against re-derived ground truth.

    Returns a dict:
        {
            "truth": {task: {"finalized": bool, "pr_status": str}},
            "results": [{"task_ref", "status", "verdict"}],
            "coverage": ["<task> no-claim", ...],
            "exit_code": 0 | 8,
            "reason": "" | "mismatch" | "empty-manifest",
            "mismatched_tasks": [...],
        }
    """
    today = today or date.today()
    # A claims manifest was "supplied" iff the caller passed a list (even empty) —
    # distinct from claims=None (no manifest concept in play at all). This
    # distinction gates the empty-manifest check below (only fires when a
    # --claims-file was actually given and parsed to zero entries).
    claims_supplied = claims is not None
    active, finalized = _list_task_folders(project_root)
    all_folders = list(dict.fromkeys(active + finalized))

    truth = {}
    for task in all_folders:
        is_finalized = task in finalized
        pr_status = "gh-unavailable"
        if not finalized_only and gh_json:
            state = match_pr_by_canonical_ref(task, gh_json)
            pr_status = state if state else "unmatched"
        truth[task] = {"finalized": is_finalized, "pr_status": pr_status}

    claims = claims or []
    results = []
    matched_folders = set()
    mismatched_tasks = []

    for claim in claims:
        ref = canonical_ref(claim["task_ref"])
        status = claim.get("status")
        candidates = match_task(ref, all_folders)
        if status not in _CLAIM_STATUS_ENUM:
            results.append({"task_ref": claim["task_ref"], "status": status, "verdict": "unmatched"})
            continue
        if len(candidates) == 0:
            results.append({"task_ref": claim["task_ref"], "status": status, "verdict": "unmatched"})
            continue
        if len(candidates) > 1:
            # All share the same issue number -> union truth; disagreement -> ambiguous (fail-open)
            finals = {truth[c]["finalized"] for c in candidates}
            prs = {truth[c]["pr_status"] for c in candidates}
            if len(finals) > 1 or len(prs) > 1:
                results.append({"task_ref": claim["task_ref"], "status": status, "verdict": "unmatched"})
                continue
        for c in candidates:
            matched_folders.add(c)
        t = truth[candidates[0]]
        mismatch = (
            (status in {"awaiting_end_of_task", "in_progress"} and t["finalized"])
            or (status == "awaiting_pr" and t["pr_status"] in {"MERGED", "CLOSED"})
            or (status in {"merged", "finalized"} and not (t["finalized"] or t["pr_status"] == "MERGED"))
        )
        verdict = "MISMATCH" if mismatch else "ok"
        results.append({"task_ref": claim["task_ref"], "status": status, "verdict": verdict})
        if mismatch:
            mismatched_tasks.append(candidates[0])

    # Coverage (MIN-c): folders with no claim resolving to them (advisory only)
    coverage = []
    if claims:
        for task in all_folders:
            if task not in matched_folders:
                coverage.append(f"coverage: {task} no-claim")

    # Empty-manifest check (MAJ-2 + r5/MAJ-1, window-scoped) — only applies when
    # a claims manifest was actually supplied (claims=[] from a real --claims-file
    # that parsed to zero entries), never when no manifest concept is in play.
    reason = ""
    exit_code = EXIT_OK
    parsed_claim_count = len(claims)
    if claims_supplied and parsed_claim_count == 0:
        L = compute_run_lower_bound(project_root, today)
        in_window_finalized = [
            t for t in finalized
            if _dir_mtime_date(project_root / ".workflow_artifacts" / "finalized" / t) >= L
        ]
        window_coverage = list(in_window_finalized)
        if window_coverage:
            exit_code = EXIT_MISMATCH
            reason = "empty-manifest"
            mismatched_tasks = window_coverage
    elif mismatched_tasks:
        exit_code = EXIT_MISMATCH
        reason = "mismatch"

    return {
        "truth": truth,
        "results": results,
        "coverage": coverage,
        "exit_code": exit_code,
        "reason": reason,
        "mismatched_tasks": mismatched_tasks,
    }


# ---------------------------------------------------------------------------
# check_side_effects (T-01) — skill-keyed required-side-effect predicates
# ---------------------------------------------------------------------------

def check_side_effects(project_root: Path, skill: str, checkpoint_file=None, today=None):
    """Return {"ok": bool, "missing": [predicate names]} for a skill."""
    today = today or date.today()
    missing = []

    if skill == "end_of_day":
        daily_path = project_root / ".workflow_artifacts" / "memory" / "daily" / f"{today.isoformat()}.md"
        if not (daily_path.is_file() and daily_path.stat().st_size > 0):
            missing.append("daily_written")

        L = compute_run_lower_bound(project_root, today)
        sessions_dir = project_root / ".workflow_artifacts" / "memory" / "sessions"
        if sessions_dir.is_dir():
            for f in sessions_dir.iterdir():
                if not f.name.endswith(".md"):
                    continue
                if _dir_mtime_date(f) < L:
                    continue
                text = f.read_text(errors="ignore")
                if "end_of_day_due: yes" in text:
                    missing.append(f"flags_flipped:{f.name}")
                    break

        cookie_path = project_root / ".workflow_artifacts" / "memory" / "resume-cookie.md"
        if not cookie_path.is_file():
            missing.append("cookie_present")

        lessons_path = project_root / ".workflow_artifacts" / "memory" / "lessons-learned.md"
        if lessons_path.is_file():
            entry_count = len(re.findall(r"^## \d{4}-\d{2}-\d{2}", lessons_path.read_text(), re.MULTILINE))
            if entry_count > 30:
                missing.append("prune_handled")

    elif skill == "checkpoint":
        if checkpoint_file is None:
            missing.append("checkpoint_file_required")
        else:
            cp_path = Path(checkpoint_file)
            if not cp_path.is_file():
                missing.append("checkpoint_file_missing")
            else:
                text = cp_path.read_text()
                for m in re.finditer(r"^- .+?:\s*(.+)$", _extract_section(text, "In-flight artifacts"), re.MULTILINE):
                    candidate = m.group(1).strip()
                    if candidate.startswith("(none") or not candidate:
                        continue
                    if not Path(candidate).is_file() and not (project_root / candidate).is_file():
                        missing.append(f"inflight_missing:{candidate}")

                ckpt_task = filename_task(cp_path.name)
                sessions_dir = project_root / ".workflow_artifacts" / "memory" / "sessions"
                freshest = None
                if sessions_dir.is_dir():
                    md_files = [f for f in sessions_dir.iterdir() if f.name.endswith(".md")]
                    if md_files:
                        freshest = max(md_files, key=lambda f: f.stat().st_mtime)
                if freshest is not None:
                    freshest_task = filename_task(freshest.name)
                    if ckpt_task != freshest_task:
                        missing.append(f"task_backstop:{ckpt_task}!={freshest_task}")
    else:
        return {"ok": True, "missing": [], "note": f"no predicate set defined for skill={skill}"}

    return {"ok": len(missing) == 0, "missing": missing}


def _extract_section(text: str, heading: str) -> str:
    pattern = rf"^## {re.escape(heading)}\s*$"
    m = re.search(pattern, text, re.MULTILINE)
    if not m:
        return ""
    rest = text[m.end():]
    next_heading = re.search(r"^## ", rest, re.MULTILINE)
    return rest[:next_heading.start()] if next_heading else rest


# ---------------------------------------------------------------------------
# Self-test (embedded fixtures, no external files/network)
# ---------------------------------------------------------------------------

def self_test() -> bool:
    import tempfile

    ok = True

    def check(label, cond):
        nonlocal ok
        if not cond:
            print(f"[self-test] FAIL: {label}")
            ok = False

    # filename_task — three shapes
    check("filename_task timestamped", filename_task("2026-07-05T0930-mytask") == "mytask")
    check("filename_task legacy", filename_task("2026-07-05-mytask") == "mytask")
    check("filename_task precompact", filename_task("2026-07-05-mytask-precompact.md") == "mytask")

    # canonical_ref / match_task
    check("canonical_ref ivg", canonical_ref("IVG-105") == "ivg-105")
    check("canonical_ref slug", canonical_ref(" some-slug ") == "some-slug")
    check("match_task prefix", match_task("ivg-105", ["ivg-105-foo", "ivg-999"]) == ["ivg-105-foo"])

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / ".workflow_artifacts" / "finalized" / "ivg-105-thing").mkdir(parents=True)
        (root / ".workflow_artifacts" / "ivg-999-other").mkdir(parents=True)

        # reconcile_tasks flags a claimed-active task whose finalized/<task>/ exists
        claims = [{"task_ref": "IVG-105", "status": "awaiting_end_of_task"}]
        report = reconcile_tasks(root, claims=claims, finalized_only=True)
        check("reconcile flags finalized mismatch", report["exit_code"] == EXIT_MISMATCH)
        check("reconcile mismatch reason", report["reason"] == "mismatch")

        # unmatched ref -> not a mismatch
        claims_unmatched = [{"task_ref": "IVG-777", "status": "awaiting_end_of_task"}]
        report2 = reconcile_tasks(root, claims=claims_unmatched, finalized_only=True)
        check("reconcile unmatched is not mismatch", report2["exit_code"] == EXIT_OK)

        # --finalized-only makes no gh call: pr_status stays gh-unavailable even with gh_json given
        report3 = reconcile_tasks(
            root,
            claims=[{"task_ref": "IVG-999", "status": "awaiting_pr"}],
            gh_json=[{"headRefName": "ivg-999-other", "state": "MERGED"}],
            finalized_only=True,
        )
        check("finalized_only ignores gh_json", report3["truth"]["ivg-999-other"]["pr_status"] == "gh-unavailable")
        check("finalized_only awaiting_pr not evaluated", report3["exit_code"] == EXIT_OK)

        # without finalized_only, the same gh claim IS evaluated
        report4 = reconcile_tasks(
            root,
            claims=[{"task_ref": "IVG-999", "status": "awaiting_pr"}],
            gh_json=[{"headRefName": "ivg-999-other", "state": "MERGED"}],
            finalized_only=False,
        )
        check("live gh flags merged-awaiting_pr mismatch", report4["exit_code"] == EXIT_MISMATCH)

        # empty-manifest: zero claims + in-window finalized folder -> exit 8
        report5 = reconcile_tasks(root, claims=[], finalized_only=True)
        check("empty manifest with in-window work exits 8", report5["exit_code"] == EXIT_MISMATCH)
        check("empty manifest reason token", report5["reason"] == "empty-manifest")

        # empty-manifest quiet day: no folders at all -> exit 0
        with tempfile.TemporaryDirectory() as tmp2:
            root2 = Path(tmp2)
            report6 = reconcile_tasks(root2, claims=[], finalized_only=True)
            check("empty manifest no folders exits 0", report6["exit_code"] == EXIT_OK)

        # parse_claims_manifest round-trip
        manifest_path = root / "manifest.md"
        manifest_path.write_text(
            "## Claims\n```yaml\n- task_ref: \"IVG-105\"\n  status: awaiting_end_of_task\n```\n"
        )
        parsed = parse_claims_manifest(manifest_path)
        check("parse_claims_manifest one entry", len(parsed) == 1 and parsed[0]["task_ref"] == "IVG-105")

        empty_manifest_path = root / "empty-manifest.md"
        empty_manifest_path.write_text("## Claims\n```yaml\n```\n")
        parsed_empty = parse_claims_manifest(empty_manifest_path)
        check("parse_claims_manifest zero entries", parsed_empty == [])

    return ok


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", default=None)
    parser.add_argument("--reconcile-tasks", action="store_true")
    parser.add_argument("--claims-file", default=None)
    parser.add_argument("--gh-json-file", default=None)
    parser.add_argument("--finalized-only", action="store_true")
    parser.add_argument("--check-side-effects", action="store_true")
    parser.add_argument("--skill", default=None)
    parser.add_argument("--checkpoint-file", default=None)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv=None) -> int:
    args = _build_parser().parse_args(argv)

    if args.self_test:
        return EXIT_OK if self_test() else 1

    project_root = Path(args.project_root or Path.cwd()).resolve()

    if args.check_side_effects:
        if not args.skill:
            print("--check-side-effects requires --skill <name>", file=sys.stderr)
            return EXIT_USAGE
        report = check_side_effects(project_root, args.skill, checkpoint_file=args.checkpoint_file)
        if args.json:
            print(json.dumps(report))
        else:
            print(f"ok={report['ok']} missing={report['missing']}")
        return EXIT_OK if report["ok"] else EXIT_MISMATCH

    if args.reconcile_tasks:
        claims = parse_claims_manifest(Path(args.claims_file)) if args.claims_file else None
        gh_json = _load_gh_json(args.gh_json_file, args.finalized_only)
        report = reconcile_tasks(
            project_root,
            claims=claims,
            gh_json=gh_json,
            finalized_only=args.finalized_only,
        )
        if args.json:
            print(json.dumps(report, default=str))
        else:
            print(f"exit_code={report['exit_code']} reason={report['reason']} mismatched={report['mismatched_tasks']}")
            for line in report["coverage"]:
                print(line)
        return report["exit_code"]

    print("no action specified (use --reconcile-tasks, --check-side-effects, or --self-test)", file=sys.stderr)
    return EXIT_USAGE


if __name__ == "__main__":
    sys.exit(main())

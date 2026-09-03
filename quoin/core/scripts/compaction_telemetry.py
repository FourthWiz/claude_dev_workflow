#!/usr/bin/env python3
"""compaction_telemetry.py — reader for the compaction-telemetry sink (IVG-258 S-5).

Reads the two-file, pair-boundary-rotated sink that ``precompact.sh`` and
``postcompact.sh`` append to (schema documented in
``quoin/memory/hooks-table.md``, section "Compaction telemetry sink"), joins
each session's "pre" and "post" halves into pairs, and reports counts. Never
raises on a malformed sink and always exits 0, mirroring ``run_state.py``.

Sink layout
-----------
``{project-root}/.workflow_artifacts/memory/telemetry/compaction-events.jsonl``
plus, once rotated, a single previous generation at the same path with a
``.1`` suffix. Both files are read — ``.1`` first, then the live file — into
one chronological stream, each record tagged with the file it came from.

Pairing
-------
Rotation resets ``event_seq`` to 0 per file (D-01 in the stage plan), and the
1 MiB tail window the hooks scan can do the same without rotation, so
``(session_id, event_seq)`` can legitimately recur. Pairing is therefore
scoped to a single source file, grouped per ``(file, session_id, event_seq)``:
exactly one "pre" and one "post" sharing that key in that file match; either
side occurring more than once diverts every record sharing that key in that
file — pres and posts alike — into the ``ambiguous`` bucket, uncounted as a
match or a pre/post-only; otherwise (one side present, the other absent)
becomes pre-only or post-only. A "post" record whose own ``event_seq`` is
``null`` (the hook found no eligible "pre" to adopt) is post-only
unconditionally, with no key grouping involved.

Filtering
---------
``--session`` and ``--task`` filter the *logical events* (a matched pair or
an unmatched half), not the raw line counts: ``pre``/``post``/``malformed``/
``schema_forward`` always describe the whole sink, while ``matched``,
``pre_only``, ``post_only``, and the task/phase groupings reflect only the
events that pass the filters. A "post" carries no run fields (D-02), so
``--task`` drops every post-only event (nothing to match against) and every
ambiguous group is excluded from event-level accounting entirely, matching
the divert-not-pair rule.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def _telemetry_paths(project_root: Path) -> tuple[Path, Path]:
    """Return (rotated_path, live_path) for the sink under project_root."""
    tel_dir = project_root / ".workflow_artifacts" / "memory" / "telemetry"
    live = tel_dir / "compaction-events.jsonl"
    rotated = tel_dir / "compaction-events.jsonl.1"
    return rotated, live


def _parse_file(path: Path, source: str, counters: dict[str, int]) -> list[dict[str, Any]]:
    """Parse one sink file into a list of valid records tagged with `_source`.

    Every malformed line increments counters["malformed"]; every well-formed
    but schema-forward record (v > 1) increments counters["schema_forward"]
    and is otherwise dropped — a reader never guesses at a version it does
    not know (mirrors the run-state schema rule).
    """
    records: list[dict[str, Any]] = []
    if not path.exists():
        return records
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return records
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except (ValueError, TypeError):
            counters["malformed"] += 1
            continue
        if not isinstance(obj, dict):
            counters["malformed"] += 1
            continue
        if "half" not in obj:
            counters["malformed"] += 1
            continue
        version = obj.get("v")
        if isinstance(version, (int, float)) and version > 1:
            counters["schema_forward"] += 1
            continue
        obj["_source"] = source
        records.append(obj)
    return records


def _since_ok(ts: Any, since: str | None) -> bool:
    if since is None:
        return True
    if not isinstance(ts, str) or len(ts) < 10:
        return False
    return ts[:10] >= since


def _pair_file(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Pair the records of a single source file. Returns per-file tallies
    and the lists of logical events (matched/pre_only/post_only)."""
    groups: dict[tuple[str, int], list[dict[str, Any]]] = {}
    matched: list[tuple[dict[str, Any], dict[str, Any]]] = []
    pre_only: list[dict[str, Any]] = []
    post_only: list[dict[str, Any]] = []
    ambiguous_pre = 0
    ambiguous_post = 0

    for rec in records:
        half = rec.get("half")
        sid = rec.get("session_id")
        seq = rec.get("event_seq")
        if half == "post" and (seq is None or not isinstance(sid, str)):
            # No eligible pre was ever adopted (or session_id is unusable) —
            # unconditionally post-only, no key grouping possible.
            post_only.append(rec)
            continue
        if not isinstance(sid, str) or not isinstance(seq, (int, float)):
            # A pre with a malformed identity key is still a valid record
            # (it survived _parse_file's checks) but cannot be grouped —
            # treat conservatively as its own kind of unmatched half.
            if half == "pre":
                pre_only.append(rec)
            else:
                post_only.append(rec)
            continue
        key = (sid, int(seq))
        groups.setdefault(key, []).append(rec)

    for group in groups.values():
        pres = [r for r in group if r.get("half") == "pre"]
        posts = [r for r in group if r.get("half") == "post"]
        if len(pres) == 1 and len(posts) == 1:
            matched.append((pres[0], posts[0]))
        elif len(pres) == 1 and len(posts) == 0:
            pre_only.append(pres[0])
        elif len(pres) == 0 and len(posts) == 1:
            post_only.append(posts[0])
        else:
            ambiguous_pre += len(pres)
            ambiguous_post += len(posts)

    return {
        "matched": matched,
        "pre_only": pre_only,
        "post_only": post_only,
        "ambiguous_pre": ambiguous_pre,
        "ambiguous_post": ambiguous_post,
    }


def build_report(
    project_root: Path,
    task: str | None = None,
    session: str | None = None,
    since: str | None = None,
) -> dict[str, Any]:
    rotated_path, live_path = _telemetry_paths(project_root)
    counters = {"malformed": 0, "schema_forward": 0}

    all_matched: list[tuple[dict[str, Any], dict[str, Any]]] = []
    all_pre_only: list[dict[str, Any]] = []
    all_post_only: list[dict[str, Any]] = []
    ambiguous_pre_total = 0
    ambiguous_post_total = 0
    pre_total = 0
    post_total = 0

    for path, source in ((rotated_path, "compaction-events.jsonl.1"), (live_path, "compaction-events.jsonl")):
        records = _parse_file(path, source, counters)
        records = [r for r in records if _since_ok(r.get("ts"), since)]
        for r in records:
            if r.get("half") == "pre":
                pre_total += 1
            elif r.get("half") == "post":
                post_total += 1
        per_file = _pair_file(records)
        all_matched.extend(per_file["matched"])
        all_pre_only.extend(per_file["pre_only"])
        all_post_only.extend(per_file["post_only"])
        ambiguous_pre_total += per_file["ambiguous_pre"]
        ambiguous_post_total += per_file["ambiguous_post"]

    def sess_ok(sid: Any) -> bool:
        return session is None or sid == session

    def task_ok(t: Any) -> bool:
        return task is None or t == task

    filtered_matched = [
        (pre, post) for pre, post in all_matched if sess_ok(pre.get("session_id")) and task_ok(pre.get("task"))
    ]
    filtered_pre_only = [r for r in all_pre_only if sess_ok(r.get("session_id")) and task_ok(r.get("task"))]
    filtered_post_only = [r for r in all_post_only if sess_ok(r.get("session_id")) and (task is None)]

    by_task: dict[str, int] = {}
    by_task_phase: dict[str, int] = {}

    def _tally(pre: dict[str, Any]) -> None:
        t = pre.get("task") or "(unattributed)"
        p = pre.get("phase") or "(unattributed)"
        by_task[t] = by_task.get(t, 0) + 1
        key = f"{t}/{p}"
        by_task_phase[key] = by_task_phase.get(key, 0) + 1

    for pre, _post in filtered_matched:
        _tally(pre)
    for pre in filtered_pre_only:
        _tally(pre)
    if filtered_post_only:
        by_task["(unattributed)"] = by_task.get("(unattributed)", 0) + len(filtered_post_only)

    est_before_sum = 0
    est_after_sum = 0
    est_pairs_counted = 0
    for pre, post in filtered_matched:
        eb = pre.get("est_tokens_before")
        ea = post.get("est_tokens_after")
        if isinstance(eb, (int, float)) and isinstance(ea, (int, float)):
            est_before_sum += eb
            est_after_sum += ea
            est_pairs_counted += 1

    return {
        "pre": pre_total,
        "post": post_total,
        "matched": len(filtered_matched),
        "ambiguous": ambiguous_pre_total + ambiguous_post_total,
        "pre_only": len(filtered_pre_only),
        "post_only": len(filtered_post_only),
        "malformed": counters["malformed"],
        "schema_forward": counters["schema_forward"],
        "est_tokens_before_sum": est_before_sum,
        "est_tokens_after_sum": est_after_sum,
        "est_tokens_reclaimed_sum": est_before_sum - est_after_sum,
        "est_pairs_counted": est_pairs_counted,
        "by_task": by_task,
        "by_task_phase": by_task_phase,
        "rotated_file_present": rotated_path.exists(),
    }


def _render_text(report: dict[str, Any]) -> str:
    lines = [
        f"pre: {report['pre']}",
        f"post: {report['post']}",
        f"matched: {report['matched']}",
        f"ambiguous: {report['ambiguous']}",
        f"pre_only: {report['pre_only']}",
        f"post_only: {report['post_only']}",
        f"malformed: {report['malformed']}",
        f"schema_forward: {report['schema_forward']}",
        f"est_tokens_before_sum: {report['est_tokens_before_sum']}",
        f"est_tokens_after_sum: {report['est_tokens_after_sum']}",
        f"est_tokens_reclaimed_sum: {report['est_tokens_reclaimed_sum']} (over {report['est_pairs_counted']} pairs)",
        f"rotated_file_present: {report['rotated_file_present']}",
        "by_task:",
    ]
    for t, n in sorted(report["by_task"].items()):
        lines.append(f"  {t}: {n}")
    lines.append("by_task_phase:")
    for tp, n in sorted(report["by_task_phase"].items()):
        lines.append(f"  {tp}: {n}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Report on the compaction-telemetry sink (pre/post pairing, counts, task grouping).",
    )
    parser.add_argument("--project-root", required=True, metavar="PATH", dest="project_root")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--task", default=None)
    parser.add_argument("--session", default=None, dest="session")
    parser.add_argument("--since", default=None, metavar="YYYY-MM-DD")
    args = parser.parse_args(argv)

    try:
        report = build_report(
            Path(args.project_root),
            task=args.task,
            session=args.session,
            since=args.since,
        )
    except Exception as exc:  # fail-OPEN: never raise, mirrors run_state.py
        print(f"[compaction_telemetry] WARNING: {exc}", file=sys.stderr)
        return 0

    if args.format == "json":
        print(json.dumps(report))
    else:
        print(_render_text(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())

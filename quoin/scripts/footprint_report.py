#!/usr/bin/env python3
"""footprint_report.py — corpus byte-footprint report (IVG-162 T-01).

Reports per-file and total byte sizes across three corpora:
  (a) deployed skill corpus:  <home>/.claude/skills/*/SKILL.md
  (b) CLAUDE.md:              <home>/.claude/CLAUDE.md (deployed) AND the quoin
                               SOURCE quoin/CLAUDE.md
  (c) memory files:           <home>/.claude/memory/*.md (deployed)

This is a read-only reporting tool — it never writes to the deployed tree, only
(optionally) to a JSON snapshot artifact under --baseline/--after.

Conservative default (D-05, architect carry-forward): any `*.pre-*` or `*.bak`
sibling of a tracked file is excluded from every corpus before summing — e.g.
the stale `<home>/.claude/skills/checkpoint/SKILL.md.pre-T11` deployed backup
left over from an earlier task. The exact-filename lookups used below
(`SKILL.md`, `CLAUDE.md`, `<name>.md` under memory/) already do not match such
suffixed files, but `_is_excluded_backup()` is applied defensively across every
corpus so a future backup-naming convention that DID collide with a glob would
still be filtered.

Snapshot capture:
  --baseline PATH   capture the corpus NOW, write a JSON snapshot to PATH,
                     print a single-snapshot report. Intended for the initial
                     wave baseline (`.workflow_artifacts/<task>/footprint-baseline.json`).
  --after PATH      same capture semantics as --baseline (used for the "after"
                     leg of a before/after diff); if PATH already exists it is
                     LOADED instead of re-captured, so an existing --after
                     snapshot is reusable across repeated report runs.
  --before PATH     load an existing JSON snapshot from PATH (must already
                     exist — exit 4 if missing) to use as the "before" side of
                     a diff.
  When both --before and --after resolve to a snapshot (loaded or freshly
  captured), a diff report (per-file delta + total delta) is printed in
  addition to the individual totals. Either flag alone just reports that one
  snapshot; with neither flag, the live corpus is measured and reported
  without writing anything to disk.

Output:
  --text (default)  human-readable report
  --json            machine-readable report (same data, JSON-encoded)

Exit codes:
  0  success
  2  argparse error (bad flags) — argparse's own exit code
  4  a required --before snapshot file is missing
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Backup-suffix exclusion (D-05)
# ---------------------------------------------------------------------------

_BACKUP_MARKERS = (".pre-", ".bak")


def _is_excluded_backup(path: Path) -> bool:
    """True if `path` looks like a stale backup sibling (*.pre-* / *.bak)."""
    name = path.name
    if name.endswith(".bak"):
        return True
    return ".pre-" in name


# ---------------------------------------------------------------------------
# Corpus capture
# ---------------------------------------------------------------------------


def _source_root() -> Path:
    """quoin/ source root (parent of this script's `scripts/` dir)."""
    return Path(__file__).resolve().parents[1]


def _file_bytes(path: Path) -> Optional[int]:
    if not path.exists() or not path.is_file() or _is_excluded_backup(path):
        return None
    return path.stat().st_size


def capture_snapshot(home_claude: Path) -> dict:
    """Capture the live corpus rooted at `home_claude` (<home>/.claude) plus the
    quoin SOURCE CLAUDE.md, and return a JSON-serializable snapshot dict.
    """
    now = datetime.now(timezone.utc).isoformat()

    # (a) deployed skill corpus
    skills_dir = home_claude / "skills"
    skill_files: dict[str, int] = {}
    if skills_dir.is_dir():
        for skill_dir in sorted(skills_dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            size = _file_bytes(skill_dir / "SKILL.md")
            if size is not None:
                skill_files[skill_dir.name] = size
    skills_total = sum(skill_files.values())

    # (b) CLAUDE.md — deployed + source
    deployed_claude_md = _file_bytes(home_claude / "CLAUDE.md")
    source_claude_md = _file_bytes(_source_root() / "CLAUDE.md")

    # (c) deployed memory files
    memory_dir = home_claude / "memory"
    memory_files: dict[str, int] = {}
    if memory_dir.is_dir():
        for f in sorted(memory_dir.glob("*.md")):
            size = _file_bytes(f)
            if size is not None:
                memory_files[f.name] = size
    memory_total = sum(memory_files.values())

    grand_total = (
        skills_total
        + (deployed_claude_md or 0)
        + (source_claude_md or 0)
        + memory_total
    )

    return {
        "captured_at": now,
        "home_claude": str(home_claude),
        "categories": {
            "skills": {"total_bytes": skills_total, "files": skill_files},
            "claude_md": {
                "deployed_bytes": deployed_claude_md,
                "source_bytes": source_claude_md,
            },
            "memory": {"total_bytes": memory_total, "files": memory_files},
        },
        "grand_total_bytes": grand_total,
    }


def load_snapshot(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_snapshot(snapshot: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def _render_snapshot_text(label: str, snapshot: dict) -> list[str]:
    lines = [f"== {label} (captured {snapshot['captured_at']}) =="]
    cats = snapshot["categories"]

    lines.append(f"-- skills ({len(cats['skills']['files'])} files) --")
    for name, size in sorted(cats["skills"]["files"].items()):
        lines.append(f"  {name:30s} {size:>8d} B")
    lines.append(f"  {'TOTAL skills':30s} {cats['skills']['total_bytes']:>8d} B")

    lines.append("-- CLAUDE.md --")
    dep = cats["claude_md"]["deployed_bytes"]
    src = cats["claude_md"]["source_bytes"]
    lines.append(f"  {'deployed':30s} {('' if dep is None else dep):>8} B")
    lines.append(f"  {'source':30s} {('' if src is None else src):>8} B")

    lines.append(f"-- memory ({len(cats['memory']['files'])} files) --")
    for name, size in sorted(cats["memory"]["files"].items()):
        lines.append(f"  {name:30s} {size:>8d} B")
    lines.append(f"  {'TOTAL memory':30s} {cats['memory']['total_bytes']:>8d} B")

    lines.append(f"GRAND TOTAL: {snapshot['grand_total_bytes']} B")
    return lines


def _diff_file_maps(before: dict, after: dict) -> list[tuple[str, Optional[int], Optional[int]]]:
    names = sorted(set(before) | set(after))
    return [(n, before.get(n), after.get(n)) for n in names]


def _render_diff_text(before: dict, after: dict) -> list[str]:
    lines = ["== Diff (before -> after) =="]

    for cat_key, label in (("skills", "skills"), ("memory", "memory")):
        b_files = before["categories"][cat_key]["files"]
        a_files = after["categories"][cat_key]["files"]
        lines.append(f"-- {label} deltas --")
        for name, b, a in _diff_file_maps(b_files, a_files):
            if b == a:
                continue
            b_disp = "—" if b is None else str(b)
            a_disp = "—" if a is None else str(a)
            delta = (a or 0) - (b or 0)
            lines.append(f"  {name:30s} {b_disp:>8s} -> {a_disp:>8s}  ({delta:+d} B)")
        b_total = before["categories"][cat_key]["total_bytes"]
        a_total = after["categories"][cat_key]["total_bytes"]
        lines.append(
            f"  {'TOTAL ' + label:30s} {b_total:>8d} -> {a_total:>8d}  ({a_total - b_total:+d} B)"
        )

    b_claude = before["categories"]["claude_md"]
    a_claude = after["categories"]["claude_md"]
    lines.append("-- CLAUDE.md deltas --")
    for key in ("deployed_bytes", "source_bytes"):
        b_v, a_v = b_claude[key], a_claude[key]
        if b_v == a_v:
            continue
        delta = (a_v or 0) - (b_v or 0)
        lines.append(f"  {key:30s} {b_v} -> {a_v}  ({delta:+d} B)")

    b_grand = before["grand_total_bytes"]
    a_grand = after["grand_total_bytes"]
    delta = a_grand - b_grand
    pct = (delta / b_grand * 100.0) if b_grand else 0.0
    lines.append(f"GRAND TOTAL: {b_grand} -> {a_grand}  ({delta:+d} B, {pct:+.1f}%)")
    return lines


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Byte-footprint report for the quoin deployed corpus + source CLAUDE.md.",
    )
    parser.add_argument(
        "--home",
        type=Path,
        default=Path.home() / ".claude",
        help="Deployed quoin home dir (default: ~/.claude).",
    )
    parser.add_argument("--baseline", type=Path, default=None,
                         help="Capture NOW and write a JSON snapshot to PATH.")
    parser.add_argument("--after", type=Path, default=None,
                         help="Capture (or load if already present) the 'after' snapshot at PATH.")
    parser.add_argument("--before", type=Path, default=None,
                         help="Load an existing JSON snapshot at PATH as the 'before' side of a diff.")
    fmt_group = parser.add_mutually_exclusive_group()
    fmt_group.add_argument("--text", action="store_const", dest="fmt", const="text")
    fmt_group.add_argument("--json", action="store_const", dest="fmt", const="json")
    parser.set_defaults(fmt="text")

    args = parser.parse_args(argv)

    before_snapshot: Optional[dict] = None
    after_snapshot: Optional[dict] = None
    output_lines: list[str] = []
    json_payload: dict = {}

    if args.before is not None:
        if not args.before.exists():
            print(f"error: --before snapshot not found: {args.before}", file=sys.stderr)
            return 4
        before_snapshot = load_snapshot(args.before)

    if args.baseline is not None:
        snap = capture_snapshot(args.home)
        write_snapshot(snap, args.baseline)
        after_snapshot = after_snapshot or snap
        if before_snapshot is None:
            output_lines.extend(_render_snapshot_text("baseline", snap))
            json_payload["baseline"] = snap

    if args.after is not None:
        if args.after.exists():
            after_snapshot = load_snapshot(args.after)
        else:
            after_snapshot = capture_snapshot(args.home)
            write_snapshot(after_snapshot, args.after)
        if before_snapshot is None:
            output_lines.extend(_render_snapshot_text("after", after_snapshot))
            json_payload["after"] = after_snapshot

    if before_snapshot is not None and after_snapshot is not None:
        output_lines = _render_diff_text(before_snapshot, after_snapshot)
        json_payload = {"before": before_snapshot, "after": after_snapshot}
    elif before_snapshot is not None and after_snapshot is None:
        output_lines = _render_snapshot_text("before", before_snapshot)
        json_payload = {"before": before_snapshot}

    if not output_lines and not json_payload:
        # No flags at all — just report the live corpus, no file write.
        snap = capture_snapshot(args.home)
        output_lines = _render_snapshot_text("live", snap)
        json_payload = {"live": snap}

    if args.fmt == "json":
        print(json.dumps(json_payload, indent=2))
    else:
        print("\n".join(output_lines))

    return 0


if __name__ == "__main__":
    sys.exit(main())

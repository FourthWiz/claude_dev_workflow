#!/usr/bin/env python3
# CLAUDE-ADAPTER-OWNED — this file reads Claude Code JSONL sessions (via
# cost_from_jsonl.py / agent_transcript_cost.py) to recover missing col-8
# cost attribution on historical (pre-stage-1) cost-ledger rows. Do NOT
# import this module from any file in quoin/core/. The portable cost-event
# schema (parse_row, CostEvent, classify_attribution) lives at
# quoin/core/scripts/cost_event.py — this module reuses it read-only.
#
# backfill_cost_attribution.py — idempotent historical backfill pass
# (IVG-111 stage 5 of ivg-111-cost-attribution).
#
# Walks NON-finalized `.workflow_artifacts/**/cost-ledger.md` files (via
# analyze_cost_ledger.discover_ledgers, which already excludes any path with
# a 'finalized' component) and, for each task row that is missing col 8 AND
# has exactly 7 fields, resolves ONLY the top-level <uuid>.jsonl transcript
# (never the nested subagent resolver — that stays scoped to
# agent_transcript_cost.resolve_attribution / the orchestrator-wiring stage)
# and appends the attribution micro-map string in place:
#   "usd=<float>;tok=<int>;src=backfill_session"  — resolved, priced
#   "tok=<int>;src=unresolved"                    — resolved, unpriceable
#   "src=unresolved"                              — unknown-*/shared/no-jsonl
#
# Recover-or-label only (R-09): a row is NEVER given a fabricated usd. The
# pricer used is agent_transcript_cost.price_agent_jsonl — the SAME guarded
# pricer stage 2 uses — which returns usd=None whenever the top-level
# session's model(s) are not in cost_from_jsonl.PRICES (or the transcript is
# empty / carries a model-less usage row). A raw parse_session call would
# silently report totalCost=0.0 for those sessions; using price_agent_jsonl
# instead means an unpriceable historical session is labeled
# "tok=<n>;src=unresolved" (tokens kept, no usd) rather than a fabricated
# "usd=0.0;src=backfill_session".
#
# Byte-identity (M-3 annotation exception): columns 1-7 of an annotated row
# are byte-for-byte unchanged — this module appends " | " + attribution to
# the RAW line text, and never round-trips a row through
# cost_event.parse_row -> cost_event.format_row (that would re-serialize and
# could normalize interior whitespace).
#
# Idempotent: any row already carrying col 8 is skipped unconditionally,
# including rows a previous run labeled "src=unresolved" — a later re-run
# never re-resolves them (one-shot per row). Re-running this script on an
# already-backfilled ledger is a strict no-op.
#
# Finalized ledgers (default): never read for mutation, never touched.
# Opt-in --include-finalized computes the same per-row attribution and
# writes it to a NON-mutating side-car `cost-backfill.json` next to the
# finalized ledger — the finalized `.md` itself is never opened for
# writing.
#
# Fail-open everywhere: a per-ledger error is caught, logged to stderr, and
# skipped — this script always exits 0 (best-effort, matches
# agent_transcript_cost.py's fail-open discipline).

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Sibling imports (same-dir adapter scripts)
# ---------------------------------------------------------------------------

def _load_sibling(name: str):
    """Load a sibling script from the same directory via spec_from_file_location.

    Copied verbatim (same-dir sibling pattern) from agent_transcript_cost.py.
    A bare `from cost_from_jsonl import ...` would pass the test suite (tests
    inject SCRIPTS_DIR onto sys.path) but raise ModuleNotFoundError in the
    deployed flat ~/.claude/scripts/ dir, which has no package structure.
    """
    path = Path(__file__).resolve().parent / f"{name}.py"
    if not path.exists():
        raise ImportError(f"Cannot load {name}: {path} not found")
    module_key = f"_backfill_cost_attribution_{name}"
    if module_key in sys.modules:
        return sys.modules[module_key]
    spec = importlib.util.spec_from_file_location(module_key, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot create spec for {name} at {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_key] = mod
    spec.loader.exec_module(mod)
    return mod


_cfj = _load_sibling("cost_from_jsonl")
jsonl_path_for = _cfj.jsonl_path_for
project_hash = _cfj.project_hash

_atc = _load_sibling("agent_transcript_cost")
price_agent_jsonl = _atc.price_agent_jsonl  # stage-2 GUARDED pricer — do NOT use raw parse_session

_acl = _load_sibling("analyze_cost_ledger")
discover_ledgers = _acl.discover_ledgers  # walks .workflow_artifacts/**/cost-ledger.md, excludes 'finalized'


# ---------------------------------------------------------------------------
# Adapter -> core sibling import (allowed direction; mirrors
# analyze_cost_ledger._load_core_cost_event)
# ---------------------------------------------------------------------------

_SCRIPTS_DIR = Path(__file__).resolve().parent
_CORE_SCRIPTS_DIR = _SCRIPTS_DIR.parent / "core" / "scripts"
_COST_EVENT_PATH = _CORE_SCRIPTS_DIR / "cost_event.py"


def _load_core_cost_event():
    """Import cost_event from core/scripts/ — works at source (relative
    traversal) and deployed (flat sibling dir, same shape as cost_from_jsonl).
    Fail-open: returns None on any load failure — callers must handle a
    None parse_row (this script cannot classify rows without it, so main()
    treats that as a fatal-but-fail-open no-op).
    """
    try:
        path = _COST_EVENT_PATH if _COST_EVENT_PATH.exists() else _SCRIPTS_DIR / "cost_event.py"
        if not path.exists():
            return None
        module_key = "_backfill_cost_attribution_cost_event"
        if module_key in sys.modules:
            return sys.modules[module_key]
        spec = importlib.util.spec_from_file_location(module_key, path)
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_key] = module
        spec.loader.exec_module(module)
        return module
    except (ImportError, OSError):
        return None


_ce = _load_core_cost_event()
parse_row = _ce.parse_row if _ce is not None else None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_finalized(path) -> bool:
    """True iff a 'finalized' path component is present. Exported for
    test_ledger_no_placeholder.py's forward-referenced immutability check
    (core/workflow/cost-ledger.md:34)."""
    return "finalized" in Path(path).parts


def _is_unknown(uuid: str) -> bool:
    return uuid.startswith("unknown-")


def _field_count(raw_line: str) -> int:
    """Bare-pipe field count — matches cost_event.parse_row's split
    discipline (split on '|', not ' | ')."""
    return len(raw_line.rstrip("\n").split("|"))


def _resolve(uuid: str, counts: dict, proj_hash: str, home) -> str:
    """proc:resolve — per-candidate verdict. Never returns a usd for an
    unpriceable or ambiguous/unknown session (R-09 label-don't-fabricate)."""
    if _is_unknown(uuid):
        return "src=unresolved"
    if counts.get(uuid, 0) > 1:
        return "src=unresolved"  # shared/parent UUID — avoid double-count
    jf = jsonl_path_for(uuid, proj_hash, home=home)
    if not jf.exists():
        return "src=unresolved"
    r = price_agent_jsonl(jf)
    tok = int(r["tok"])
    if not r["priceable"]:
        return f"tok={tok};src=unresolved"  # unpriceable model — keep tok, NEVER usd
    usd = round(float(r["usd"]), 6)
    return f"usd={usd};tok={tok};src=backfill_session"


def _candidate(raw_line: str):
    """Parse a raw ledger line and return its CostEvent iff it is a
    backfill CANDIDATE (task row, col 8 absent, exactly 7 fields).
    Returns None for header/blank/comment/non-task rows, already-annotated
    rows, and 6-column (or >7-column) legacy rows (D-4) — all of those are
    copied verbatim by the caller."""
    ev = parse_row(raw_line.rstrip("\n"))
    if ev is None:
        return None
    if ev.attribution != "":
        return None
    if _field_count(raw_line) != 7:
        return None
    return ev


# ---------------------------------------------------------------------------
# Non-finalized backfill (T-01)
# ---------------------------------------------------------------------------

def backfill_ledger(ledger_path: Path, project_root: Path, home, dry_run: bool = False) -> dict:
    """proc:backfill — two-pass in-place col-8 annotation for one NON-
    finalized ledger file. Returns a per-ledger counts dict. Cols 1-7 of
    every annotated row are byte-identical to the original; untouched rows
    (header/blank/comment/non-task/already-col-8/6-col) are copied verbatim.
    """
    st0 = ledger_path.stat()  # MAJ-2: snapshot BEFORE read
    lines = ledger_path.read_text(encoding="utf-8").splitlines(keepends=True)
    proj_hash = project_hash(str(project_root))

    # Pass 1: candidate census (uuid -> candidate-row count)
    counts: dict = {}
    for raw in lines:
        ev = _candidate(raw)
        if ev is None or _is_unknown(ev.uuid):
            continue
        counts[ev.uuid] = counts.get(ev.uuid, 0) + 1

    # Pass 2: rewrite
    out = []
    annotated = 0
    unresolved = 0
    skipped = 0
    for raw in lines:
        ev = _candidate(raw)
        if ev is None:
            out.append(raw)
            continue
        attr = _resolve(ev.uuid, counts, proj_hash, home)
        nl = "\n" if raw.endswith("\n") else ""
        out.append(raw.rstrip("\n") + " | " + attr + nl)
        if attr.endswith("src=backfill_session"):
            annotated += 1
        else:
            unresolved += 1

    # skipped = task rows that were NOT candidates (already col-8, or a
    # column count other than exactly 7) — informational only.
    for raw in lines:
        ev = parse_row(raw.rstrip("\n"))
        if ev is None:
            continue
        if ev.attribution != "" or _field_count(raw) != 7:
            skipped += 1

    changed = annotated + unresolved
    if changed and not dry_run:
        st1 = ledger_path.stat()  # MAJ-2: recheck IMMEDIATELY before replace
        if (st1.st_size, st1.st_mtime_ns) != (st0.st_size, st0.st_mtime_ns):
            print(
                f"backfill_cost_attribution: {ledger_path}: grew during backfill "
                "(live append?) -> SKIP; recover on re-run",
                file=sys.stderr,
            )
            return {"ledger": str(ledger_path), "annotated": 0, "unresolved": 0,
                     "skipped": skipped, "aborted": True}
        tmp_path = ledger_path.parent / (ledger_path.name + ".tmp")
        tmp_path.write_text("".join(out), encoding="utf-8")
        os.replace(tmp_path, ledger_path)  # atomic (Drive-synced fs safety)

    return {"ledger": str(ledger_path), "annotated": annotated,
             "unresolved": unresolved, "skipped": skipped, "aborted": False}


# ---------------------------------------------------------------------------
# Finalized ledgers — opt-in, non-mutating side-car (T-02)
# ---------------------------------------------------------------------------

def backfill_finalized(project_root: Path, home, dry_run: bool = False) -> list:
    """proc:finalized — only called under --include-finalized. Computes the
    same per-row attribution for each finalized ledger's candidate rows and
    writes it to a NON-mutating cost-backfill.json side-car in the same
    directory; the finalized .md is NEVER opened for writing."""
    wa = Path(project_root) / ".workflow_artifacts"
    if not wa.exists():
        return []
    results = []
    for ledger in sorted(wa.rglob("cost-ledger.md")):
        if not _is_finalized(ledger):
            continue
        text = ledger.read_text(encoding="utf-8")
        lines = text.splitlines()
        proj_hash = project_hash(str(project_root))

        counts: dict = {}
        for raw in lines:
            ev = _candidate(raw)
            if ev is None or _is_unknown(ev.uuid):
                continue
            counts[ev.uuid] = counts.get(ev.uuid, 0) + 1

        rows = []
        for raw in lines:
            ev = _candidate(raw)
            if ev is None:
                continue
            attr = _resolve(ev.uuid, counts, proj_hash, home)
            rows.append({"uuid": ev.uuid, "date": ev.date, "phase": ev.phase,
                          "attribution": attr})

        sidecar = ledger.parent / "cost-backfill.json"
        # MIN-3: no embedded 'generated' timestamp -> byte-idempotent side-car
        payload = {"ledger": str(ledger.resolve()), "rows": rows}
        if not dry_run:
            sidecar.write_text(
                json.dumps(payload, sort_keys=True, indent=2), encoding="utf-8"
            )
        results.append({"ledger": str(ledger), "sidecar": str(sidecar), "rows": len(rows)})
    return results


# ---------------------------------------------------------------------------
# CLI (T-06)
# ---------------------------------------------------------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="backfill_cost_attribution.py",
        description=(
            "Idempotent historical col-8 cost-attribution backfill for "
            "NON-finalized .workflow_artifacts/**/cost-ledger.md files. "
            "Recover-or-label only (R-09): never fabricates a precise cost — "
            "an unresolvable or unpriceable session is labeled "
            "'src=unresolved' (tokens kept when known), never a fake usd. "
            "Finalized ledgers are skipped by default; --include-finalized "
            "writes a non-mutating cost-backfill.json side-car next to each "
            "finalized ledger and never edits the finalized .md."
        ),
    )
    ap.add_argument("--project-root", metavar="PATH", default=None,
                     help="Project root containing .workflow_artifacts/ (default: cwd)")
    ap.add_argument("--home", metavar="PATH", default=None,
                     help="Override ~/.claude root for JSONL lookup (default: pathlib.Path.home())")
    ap.add_argument("--dry-run", action="store_true",
                     help="Compute and report counts only; write nothing")
    ap.add_argument("--include-finalized", action="store_true",
                     help="Also process finalized ledgers, writing a non-mutating side-car")
    ap.add_argument("--ledger", metavar="PATH", default=None,
                     help="Single non-finalized ledger file (overrides discovery)")
    args = ap.parse_args(argv)

    if parse_row is None:
        print("backfill_cost_attribution: core cost_event.py unavailable; no-op", file=sys.stderr)
        return 0

    project_root = Path(args.project_root).resolve() if args.project_root else Path.cwd()
    home = Path(args.home).resolve() if args.home else None

    if args.ledger:
        ledgers = [Path(args.ledger).resolve()]
    else:
        ledgers = discover_ledgers(project_root)

    for ledger in ledgers:
        try:
            result = backfill_ledger(ledger, project_root, home, dry_run=args.dry_run)
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            print(f"backfill_cost_attribution: {ledger}: error: {exc}", file=sys.stderr)
            continue
        print(
            f"{result['ledger']}: annotated {result['annotated']} backfill_session, "
            f"{result['unresolved']} unresolved, skipped {result['skipped']}"
        )

    if args.include_finalized:
        try:
            finalized_results = backfill_finalized(project_root, home, dry_run=args.dry_run)
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            print(f"backfill_cost_attribution: finalized pass error: {exc}", file=sys.stderr)
            finalized_results = []
        for fr in finalized_results:
            print(f"{fr['ledger']}: {fr['rows']} rows -> side-car {fr['sidecar']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

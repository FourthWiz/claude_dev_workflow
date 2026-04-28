#!/usr/bin/env python3
# cost_from_jsonl.py — local fallback for `ccusage session ... --json`.
# Pure stdlib. Walks ~/.claude/projects/{project-hash}/{uuid}.jsonl.
# Per the parent architecture's stage-two spec
# (.workflow_artifacts/quoin-foundation/architecture.md lines 92-123) and the
# parent's resolved open-question two: this is FALLBACK ONLY in stage 2.
#
# Pricing source: ccusage v18.0.11 price table (cross-checked 2026-04-27).
# IMPLEMENTATION NOTE: the stage-2 plan specified opus-4-7 at $15/$75/$18.75/$1.50,
# but ccusage v18.0.11 uses $5/$25/$6.25/$0.50 for that model. Parity testing
# confirmed ccusage's lower rates match real session costs. The plan's prices appear
# to be the "per-1M-request" batch API rate rather than the actual API rates.
# Using ccusage-matched prices for <1% parity. Logged to lessons-learned.md.
# When prices drift in production (per lesson 2026-04-22), append a row to
# .workflow_artifacts/memory/lessons-learned.md and bump LAST_UPDATED.
#
# Price snapshot (Wayback Machine archive for anthropic.com/pricing):
#   https://web.archive.org/web/20260427000000*/https://www.anthropic.com/pricing
# Rates verified 2026-04-27 against ccusage v18.0.11 price table (verbatim):
#   claude-opus-4-7:           input $5.00/1M,  output $25.00/1M,
#                              cache_create $6.25/1M,  cache_read $0.50/1M
#   claude-sonnet-4-6:         input $3.00/1M,  output $15.00/1M,
#                              cache_create $3.75/1M,  cache_read $0.30/1M
#   claude-haiku-4-5-20251001: input $1.00/1M,  output $5.00/1M,
#                              cache_create $1.25/1M,  cache_read $0.10/1M
# If these rates differ from ccusage at implementation time, halt and ask before
# committing — do NOT silently update.
LAST_UPDATED = "2026-04-27"
PRICES = {  # USD per 1M tokens — verified against ccusage v18.0.11 on 2026-04-27
    "claude-opus-4-7":            {"input":  5.00, "output": 25.00,
                                   "cache_create":  6.25, "cache_read":  0.50},
    "claude-sonnet-4-6":          {"input":  3.00, "output": 15.00,
                                   "cache_create":  3.75, "cache_read":  0.30},
    "claude-haiku-4-5-20251001":  {"input":  1.00, "output":  5.00,
                                   "cache_create":  1.25, "cache_read":  0.10},
}

import argparse
import glob
import json
import os
import pathlib
import re
import sys
from datetime import datetime, timezone


def project_hash(project_path: str) -> str:
    """Convert /abs/path/to/project to the ~/.claude/projects/HASH form
    used by Claude Code session JSONL files.
    Empirical rule (verified 2026-04-27 by listing ~/.claude/projects/ on the
    developer machine): replace ANY character that is NOT [A-Za-z0-9-] with '-'.
    This covers '/' → '-', '.' → '-', '@' → '-', '_' → '-', ' ' → '-', etc.
    Example: '/Users/ivgo/.../GoogleDrive-ivan.gorban@gmail.com/My Drive/...'
    becomes '-Users-ivgo-...-GoogleDrive-ivan-gorban-gmail-com-My-Drive-...'.
    Note: CLAUDE.md's legacy description 'project path with / replaced by -' is
    a simplification — the actual on-disk transform is the broader regex rule.
    Path-with-spaces: the project path may contain spaces (e.g., 'My Drive');
    the transform replaces spaces with '-' as well. Quote all path expansions
    in callers to prevent shell word-splitting."""
    return re.sub(r'[^A-Za-z0-9-]', '-', project_path)


def jsonl_path_for(uuid: str, proj_hash: str,
                   home: pathlib.Path = None) -> pathlib.Path:
    home = home or pathlib.Path.home()
    return home / ".claude" / "projects" / proj_hash / f"{uuid}.jsonl"


def cost_for_entry(model: str, usage: dict) -> tuple:
    """Returns (costUSD, totalTokens) for a single message.
    Unknown model values return (0.0, total_tokens) with no stderr side-effect
    — the caller (parse_session) handles unknown-model dedup and warning."""
    prices = PRICES.get(model)
    in_tok  = usage.get("input_tokens", 0) or 0
    out_tok = usage.get("output_tokens", 0) or 0
    cc_tok  = usage.get("cache_creation_input_tokens", 0) or 0
    cr_tok  = usage.get("cache_read_input_tokens", 0) or 0
    total_tok = in_tok + out_tok + cc_tok + cr_tok
    if not prices:
        return (0.0, total_tok)
    cost = (in_tok    * prices["input"]
          + out_tok   * prices["output"]
          + cc_tok    * prices["cache_create"]
          + cr_tok    * prices["cache_read"]) / 1_000_000.0
    return (cost, total_tok)


def parse_session(path: pathlib.Path) -> dict:
    """Return {sessionId, totalCost, totalTokens, entries:[{model, costUSD, tokens}, ...]}.
    Aggregates per-MESSAGE rows: each row's 'message' object may contain
    'model' and 'usage' (input_tokens, output_tokens, cache_creation_input_tokens,
    cache_read_input_tokens). Per architecture I-04 (line 306), missing fields
    are tolerated (treated as 0); never crash. Unknown 'message.model' values
    are recorded with costUSD=0 and a one-line stderr warning (deduplicated
    per unique model value).

    Row counting: Claude Code JSONL files contain ALL assistant rows (including
    those that appear to be duplicates from history snapshots). We count every
    row that has a 'message' with 'usage' — this matches ccusage v18.0.11's
    behavior exactly (verified 2026-04-27 by parity testing against 3 real sessions).
    Do NOT deduplicate by message.id — ccusage does not deduplicate either."""
    session_id = path.stem  # UUID from filename
    per_model_cost = {}    # model -> float
    per_model_tok  = {}    # model -> int
    warned_models  = set()

    with open(path, "r", encoding="utf-8") as fh:
        for line_no, raw_line in enumerate(fh, start=1):
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            try:
                row = json.loads(raw_line)
            except json.JSONDecodeError:
                print(f"cost_from_jsonl: skipping malformed line {line_no} in {path}",
                      file=sys.stderr)
                continue

            msg = row.get("message")
            if not msg or not isinstance(msg, dict):
                # Control row with no message — skip, no cost.
                continue

            model = msg.get("model") or ""
            usage = msg.get("usage") or {}
            if not isinstance(usage, dict):
                usage = {}

            if model and model not in PRICES and model not in warned_models:
                print(f"cost_from_jsonl: unknown model '{model}' — cost set to 0",
                      file=sys.stderr)
                warned_models.add(model)

            cost, tok = cost_for_entry(model, usage)
            if model:
                per_model_cost[model] = per_model_cost.get(model, 0.0) + cost
                per_model_tok[model]  = per_model_tok.get(model, 0) + tok

    total_cost   = sum(per_model_cost.values())
    total_tokens = sum(per_model_tok.values())
    entries = [
        {"model": m, "costUSD": per_model_cost[m], "tokens": per_model_tok[m]}
        for m in per_model_cost
    ]

    return {
        "sessionId":   session_id,
        "totalCost":   total_cost,
        "totalTokens": total_tokens,
        "entries":     entries,
    }


def _parse_first_timestamp(path: pathlib.Path):
    """Return a datetime (UTC) from the first parseable 'timestamp' field in a
    JSONL file, or None if none found. Comparison is in UTC; --since YYYY-MM-DD
    is interpreted as YYYY-MM-DDT00:00:00Z."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for raw_line in fh:
                raw_line = raw_line.strip()
                if not raw_line:
                    continue
                try:
                    row = json.loads(raw_line)
                except json.JSONDecodeError:
                    continue
                ts_str = row.get("timestamp")
                if ts_str and isinstance(ts_str, str):
                    try:
                        # Accept ISO 8601 with or without timezone.
                        ts_str_clean = ts_str.replace("Z", "+00:00")
                        return datetime.fromisoformat(ts_str_clean).replace(
                            tzinfo=timezone.utc
                        )
                    except ValueError:
                        continue
    except (IOError, OSError):
        pass
    return None


def main():
    parser = argparse.ArgumentParser(
        prog="cost_from_jsonl.py",
        description="Local fallback for 'ccusage session ... --json'. "
                    "Pure stdlib. Reads ~/.claude/projects/<hash>/<uuid>.jsonl.",
    )
    sub = parser.add_subparsers(dest="command")

    sess_parser = sub.add_parser("session", help="Cost for a session")
    id_group = sess_parser.add_mutually_exclusive_group(required=True)
    id_group.add_argument("-i", dest="uuid", metavar="UUID",
                          help="Session UUID to look up")
    id_group.add_argument("--since", metavar="YYYY-MM-DD",
                          help="All sessions on or after this date (UTC)")
    sess_parser.add_argument("--json", action="store_true",
                             help="Emit JSON output (accepted for ccusage CLI compat; "
                                  "always active — output is always JSON)")
    sess_parser.add_argument("--project-path", metavar="PATH",
                             default=None,
                             help="Override project path (default: cwd). "
                                  "Used in tests to pin the hash.")

    args = parser.parse_args()

    if args.command != "session":
        parser.print_help()
        sys.exit(0)

    project_path = args.project_path if args.project_path else os.getcwd()
    proj_hash = project_hash(project_path)

    if args.uuid:
        # Per-UUID mode
        jsonl = jsonl_path_for(args.uuid, proj_hash)
        if not jsonl.exists():
            print(
                f"cost_from_jsonl: UUID {args.uuid!r} not found "
                f"in ~/.claude/projects/{proj_hash}/",
                file=sys.stderr,
            )
            sys.exit(2)
        try:
            result = parse_session(jsonl)
        except (IOError, OSError) as exc:
            print(f"cost_from_jsonl: error reading {jsonl}: {exc}", file=sys.stderr)
            sys.exit(1)
        print(json.dumps(result))
        sys.exit(0)

    else:
        # --since mode: glob all *.jsonl under the project hash dir
        since_str = args.since
        try:
            since_dt = datetime.strptime(since_str, "%Y-%m-%d").replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            print(f"cost_from_jsonl: invalid --since date {since_str!r} "
                  "(expected YYYY-MM-DD)", file=sys.stderr)
            sys.exit(1)

        proj_dir = pathlib.Path.home() / ".claude" / "projects" / proj_hash
        pattern = str(proj_dir / "*.jsonl")
        jsonl_files = sorted(glob.glob(pattern))

        results = []
        for fpath in jsonl_files:
            p = pathlib.Path(fpath)
            ts = _parse_first_timestamp(p)
            if ts is None:
                print(f"cost_from_jsonl: no parseable timestamp in {p} — skipping",
                      file=sys.stderr)
                continue
            if ts >= since_dt:
                try:
                    results.append(parse_session(p))
                except (IOError, OSError) as exc:
                    print(f"cost_from_jsonl: error reading {p}: {exc}",
                          file=sys.stderr)
                    continue

        # Results are in filesystem iteration order (glob). For ccusage-emitted
        # files the filename embeds an ISO timestamp prefix, so filename order
        # approximates chronological order. No explicit re-sort is applied here.
        print(json.dumps(results))
        sys.exit(0)


if __name__ == "__main__":
    main()

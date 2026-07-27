"""Portable cost-event schema and ledger-row parser.

This module is runtime-neutral and does NOT participate in price computation,
session-UUID acquisition, or adapter-specific session-log parsing. It provides
a typed schema for cost-ledger rows and pure functions to parse and format them.

Warning prefix kept as 'cost_snapshot.WARN' for parity with existing consumers
(test_cost_ledger_7col_parser.py and cost_snapshot/SKILL.md); a future
SKILL.md-narrowing phase will decide whether to rename to 'cost_event.WARN'.

This module is runtime-neutral; it MUST NOT import from any Claude-adapter-owned
helper (the session-log-reading or session-age scripts under quoin/scripts/). The
portable cost-event schema lives here; runtime-specific cost collection lives in
the Claude adapter.

Schema alignment: the field names and parsing rules described here match the
expanded contract in quoin/core/workflow/cost-ledger.md. Both are kept
content-aligned; that document is the prose reference, this module is the
canonical typed implementation.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


class RowParseError(ValueError):
    """Raised when a row is structurally unrecoverable (not used for WARN path)."""


@dataclass(frozen=True)
class CostEvent:
    """A single parsed row from a cost ledger file.

    Field mapping from the 7-column ledger format:
        col 1: uuid            — session identifier (runtime-agnostic)
        col 2: date            — ISO YYYY-MM-DD
        col 3: phase           — workflow phase (e.g. plan, implement, review)
        col 4: model_or_effort — Claude model tier (opus/sonnet/haiku) or effort
                                 level (high/medium/low); field name is neutral
        col 5: category        — always "task" in current practice; skip-line if
                                 any other value
        col 6: note            — free-form note; double-quotes preserved verbatim
        col 7: fallback_fires  — int, defaults to 0 for 6-column rows
        col 8: attribution     — optional micro-map string; "" = none
    """

    uuid: str
    date: str
    phase: str
    model_or_effort: str
    category: str
    note: str
    fallback_fires: int = 0
    attribution: str = ""


def parse_row(
    line: str,
    *,
    source: str = "<unknown>",
    lineno: int = 0,
) -> CostEvent | None:
    """Parse one ledger row into a CostEvent.

    Returns None for rows that should be skipped (blank, comment, too-few
    columns, non-task category). Never raises for well-formed or tolerably
    malformed rows — emits a stderr warning instead and returns the best
    available CostEvent.

    Parsing discipline (bare-pipe-with-strip per D-05):
    - Split on bare '|' (NOT on ' | '), then strip each field.
    - This matches the existing cost_snapshot/SKILL.md Step 1 and
      test_cost_ledger_7col_parser.py parsing behavior.
    - Quoted notes (e.g. "quoted note") are preserved verbatim; the reader
      does NOT strip surrounding double-quotes.
    """
    stripped = line.strip()

    # Skip blank lines and comment lines
    if not stripped or stripped.startswith("#"):
        return None

    parts = stripped.split("|")

    # Too few columns to be a valid row
    if len(parts) < 6:
        return None

    # Extract the first 6 mandatory fields (strip each)
    uuid = parts[0].strip()
    date = parts[1].strip()
    phase = parts[2].strip()
    model_or_effort = parts[3].strip()
    category = parts[4].strip()
    note = parts[5].strip()

    # Defensive guard: skip non-task rows (mirrors test_cost_ledger_7col_parser.py:44)
    if category != "task":
        return None

    # Handle 7th column (fallback_fires) and 8th column (attribution).
    # Exactly 8 columns is first-class (no warning); >=9 columns emits the
    # extra-columns warning and ignores parts[8:].
    fallback_fires = 0
    attribution = ""
    if len(parts) >= 7:
        raw_7th = parts[6].strip()
        try:
            fallback_fires = int(raw_7th)
        except ValueError:
            print(
                f"cost_snapshot.WARN: malformed fallback_fires column at "
                f"{source}:{lineno}: {raw_7th!r}",
                file=sys.stderr,
            )
            fallback_fires = 0
    if len(parts) >= 8:
        attribution = parts[7].strip()
    if len(parts) >= 9:
        print(
            f"cost_snapshot.WARN: extra columns at {source}:{lineno} "
            f"(found {len(parts)}, expected ≤8)",
            file=sys.stderr,
        )

    return CostEvent(
        uuid=uuid,
        date=date,
        phase=phase,
        model_or_effort=model_or_effort,
        category=category,
        note=note,
        fallback_fires=fallback_fires,
        attribution=attribution,
    )


def format_row(event: CostEvent) -> str:
    """Emit the canonical ledger row for a CostEvent.

    Never appends a trailing newline; caller adds one if needed.
    Emits 8 columns only when event.attribution is non-empty; otherwise
    emits exactly the 7-column form (col 8 is omitted, not written as an
    empty trailing segment).

    Round-trip guarantee: format_row(parse_row(line)) == line.strip() for
    (a) every valid 6- or 7-column row (6-column rows upgrade one-way to
    7-column, appending ' | 0', per D-07) and (b) every valid 8-column row
    whose attribution is NON-EMPTY. An 8-column row with an EMPTY col 8
    normalizes one-way to the 7-column form (same class as the 6->7
    upgrade) — NOT a byte-identity case.
    """
    base = (
        f"{event.uuid} | {event.date} | {event.phase} | "
        f"{event.model_or_effort} | {event.category} | "
        f"{event.note} | {event.fallback_fires}"
    )
    if event.attribution:
        return f"{base} | {event.attribution}"
    return base


def parse_attribution(s: str) -> dict:
    """Parse an attribution micro-map string into a dict.

    Grammar: k=v(;k=v)* — semicolon-delimited key=value tokens, each side
    stripped of surrounding whitespace. Tolerant, pure, never raises:
    - Empty/whitespace-only input returns {}.
    - Tokens without '=' are skipped.
    - Tokens with an empty key after stripping (e.g. a lone '=') are
      skipped — this guard prevents a stray '=' from injecting a "" key.
    - Values are NOT coerced (stay str); numeric interpretation of 'usd'/
      'tok' is the reader-precedence stage's responsibility, not this
      module's.

    Canonical asserted cases:
        "usd=0.01;tok=45;src=<tag>" -> {"usd": "0.01", "tok": "45", "src": "<tag>"}
        ""                          -> {}
        "src=unresolved"            -> {"src": "unresolved"}
        "usd=;=;;foo;tok=9"         -> {"usd": "", "tok": "9"}
        " a = b ; c=d "             -> {"a": "b", "c": "d"}
    """
    out: dict = {}
    for tok in s.split(";"):
        tok = tok.strip()
        if not tok or "=" not in tok:
            continue
        k, v = tok.split("=", 1)
        if not k.strip():
            continue
        out[k.strip()] = v.strip()
    return out


def classify_attribution(attribution: str) -> tuple[str, float | None]:
    """Classify a raw col-8 attribution string into a precedence verdict.

    Provenance-agnostic: the verdict is keyed on usd-presence plus the
    neutral 'unresolved' sentinel, NOT a hand-maintained allowlist of
    resolved 'src' tags — a new resolved src auto-classifies without a
    code change here.

    Returns exactly one of:
        ("legacy", None)        — attribution is empty (no col 8); caller
                                   does its own legacy session-log resolution.
        ("resolved", usd_float) — col 8 present, a parseable 'usd' value
                                   is present, AND 'src' is NOT the
                                   unresolvable sentinel. Never returns
                                   ("resolved", 0.0) for an unresolvable row
                                   — a parsed 0.0 here is a genuine resolved
                                   zero, distinct from "no usd present".
        ("unresolvable", None)  — col 8 present but src == "unresolved",
                                   OR usd is absent/unparseable.

    Pure, tolerant, never raises — mirrors parse_attribution's discipline.

    Canonical asserted cases:
        classify_attribution("") -> ("legacy", None)
        classify_attribution("usd=0.0123;tok=45210;src=<tag>")
            -> ("resolved", 0.0123)
        classify_attribution("tok=45;src=unresolved") -> ("unresolvable", None)
        classify_attribution("src=unresolved") -> ("unresolvable", None)
        classify_attribution("usd=abc;src=<tag>") -> ("unresolvable", None)
        classify_attribution("usd=0.0;tok=9;src=<tag>") -> ("resolved", 0.0)
    """
    if not attribution.strip():
        return ("legacy", None)

    fields = parse_attribution(attribution)
    src = fields.get("src", "")
    if src == "unresolved":
        return ("unresolvable", None)

    raw_usd = fields.get("usd")
    if raw_usd is None:
        return ("unresolvable", None)
    try:
        usd = float(raw_usd)
    except ValueError:
        return ("unresolvable", None)

    return ("resolved", usd)


def iter_events(path: Path) -> Iterator[CostEvent]:
    """Open a ledger file and yield CostEvent for each parseable row.

    Convenience reader for callers that want to iterate over all task events
    in a ledger without dealing with blank lines, comments, or skip-line cases.
    Emits stderr warnings for malformed rows via parse_row but continues.
    """
    with open(path, encoding="utf-8") as fh:
        for lineno, raw_line in enumerate(fh, start=1):
            event = parse_row(raw_line, source=str(path), lineno=lineno)
            if event is not None:
                yield event

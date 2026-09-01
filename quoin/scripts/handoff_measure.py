#!/usr/bin/env python3
# CLAUDE-ADAPTER-OWNED — this instrument reads the nested Claude Code subagent
# transcript tree (~/.claude/projects/**/subagents/*.jsonl) to measure agent
# handoff payload sizes. Do NOT import this module from quoin/core/ — the
# adapter/core boundary is documented in quoin/docs/runtime-portability.md.
#
# handoff_measure.py — instrument for the agent-handoff-format stage 1
# baseline. Every filesystem root is a function parameter, never a module
# constant, so tests never touch the developer's live tree (mirrors
# agent_transcript_cost.py's home= / project_path= overrides).
#
# Published enumeration predicate, verbatim:
#   <home>/.claude/projects/**/subagents/*.jsonl   (recursive)

import argparse
import datetime
import hashlib
import json
import math
import re
import sys
from pathlib import Path

# Phases the /run orchestrator spawns as on-behalf subagents. Enumerated
# here rather than reached only through an appendix: a re-deriver who
# substitutes a plausible wrong set (e.g. adding "plan", "critic" or "gate" —
# all frequent skill-matched phases and none of them run-owned) silently
# gets a different population and a different median with no error raised.
RUN_OWNED_PHASES = frozenset({
    "discover",
    "enrich",
    "specify",
    "architect",
    "thorough_plan",
    "implement",
    "review",
    "end_of_task",
})

_PHASE_RE = re.compile(r"Invoke the /([a-z_]+) skill")
_DISPATCH_SNIFF_BYTES = 600


def _projects_root(home):
    """`<home>/.claude/projects` — the root every transcript path is
    relative to. `iter_transcripts`'s glob root and the ordinal-labeling
    functions (`_corpus_label_maps`, `stable_id`) all derive it from
    `home` the same way; folded into one place so the segment list isn't
    repeated at each call site.
    """
    return Path(home) / ".claude" / "projects"


def iter_transcripts(home, project_filter=None):
    """Yield subagent transcript paths under home/.claude/projects.

    Globs the published predicate verbatim: <home>/.claude/projects/**/subagents/*.jsonl,
    recursive. `home` is a required parameter (never a module constant) so
    tests operate on a fixture tree, never the developer's live tree.
    `project_filter`, if given, is matched as a substring of each path's
    project-hash directory component (the first path segment under
    `projects/`).
    """
    root = _projects_root(home)
    if not root.exists():
        return
    for path in sorted(root.glob("**/subagents/*.jsonl")):
        if project_filter is not None:
            try:
                rel = path.relative_to(root)
            except ValueError:
                continue
            if project_filter not in rel.parts[0]:
                continue
        yield path


def payload_text(content):
    """Extract the text payload from a transcript message's `content` field.

    `content` is a transcript row's `message.content` value — either a bare
    str, or a list of content blocks. Only blocks with `type == "text"`
    contribute; `thinking` / `tool_use` / `tool_result` blocks are dropped.
    Returns "" when no text is present (e.g. a tool_use-only assistant turn,
    or a thinking-only tail block) rather than raising.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text = block.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts)
    return ""


def detect_phase(dispatch_text):
    """Detect the skill name a dispatch payload invokes, or None.

    Applies `Invoke the /([a-z_]+) skill` to the first 600 BYTES (not
    characters) of the UTF-8-encoded dispatch payload, decoding with
    errors="ignore" so a multi-byte character straddling the boundary
    cannot raise. Bytes, not characters — the published predicate is
    byte-denominated and the two differ on non-ASCII prefixes.
    """
    if not dispatch_text:
        return None
    encoded = dispatch_text.encode("utf-8", errors="ignore")
    sniff = encoded[:_DISPATCH_SNIFF_BYTES].decode("utf-8", errors="ignore")
    match = _PHASE_RE.search(sniff)
    if match is None:
        return None
    return match.group(1)


def extract_payloads(path):
    """Read one subagent transcript and return its dispatch/return payloads.

    Returns a dict: `dispatch_text` (the first user message's text, "" if
    absent), `return_text` (the last assistant message's text, "" if absent
    or text-free), and `last_assistant` (that row's raw JSON dict, or None
    — so callers needing `usage` / `stop_reason`, e.g. the token
    cross-check, can read it without a second pass over the file).

    A malformed JSON line among otherwise-good lines is skipped, not
    raised (line-level tolerance). FileNotFoundError, PermissionError, and
    any other OSError raised while opening or reading `path` propagate to
    the caller unchanged — this function does not itself decide the
    corpus-wide skipped_unreadable tally; see `capture_corpus`.
    """
    dispatch_text = ""
    return_text = ""
    last_assistant = None
    dispatch_seen = False
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            message = row.get("message")
            if not isinstance(message, dict):
                continue
            role = message.get("role")
            if role == "user" and not dispatch_seen:
                dispatch_text = payload_text(message.get("content"))
                dispatch_seen = True
            elif role == "assistant":
                last_assistant = row
    if last_assistant is not None:
        return_text = payload_text(last_assistant.get("message", {}).get("content"))
    return {
        "dispatch_text": dispatch_text,
        "return_text": return_text,
        "last_assistant": last_assistant,
    }


def capture_corpus(home, project_filter=None):
    """Walk the published predicate once, returning per-transcript records
    plus corpus-level counters.

    File-level fail-open lives here: a transcript that vanishes between
    glob and open (FileNotFoundError), or that this process cannot read
    (PermissionError / other OSError), is skipped and tallied in
    `skipped_unreadable` rather than aborting the capture. The corpus is
    genuinely volatile by nature: a live capture can differ between two
    runs simply because new transcripts appeared or old ones were pruned.
    """
    records = []
    parsed = 0
    unreadable = 0
    skill_matched = 0
    run_owned = 0
    for path in iter_transcripts(home, project_filter=project_filter):
        try:
            payloads = extract_payloads(path)
        except (FileNotFoundError, PermissionError, OSError):
            unreadable += 1
            continue
        parsed += 1
        phase = detect_phase(payloads["dispatch_text"])
        is_run_owned = phase in RUN_OWNED_PHASES
        if phase is not None:
            skill_matched += 1
        if is_run_owned:
            run_owned += 1
        records.append({
            "path": str(path),
            "phase": phase,
            "run_owned": is_run_owned,
            "dispatch_text": payloads["dispatch_text"],
            "return_text": payloads["return_text"],
            "last_assistant": payloads["last_assistant"],
        })
    return {
        "records": records,
        "transcripts": parsed + unreadable,
        "parsed": parsed,
        "skipped_unreadable": unreadable,
        "skill_matched": skill_matched,
        "run_owned": run_owned,
    }



# ---------------------------------------------------------------------------
# Channels one and two — dispatch and return, bytes and tokens
# ---------------------------------------------------------------------------

# One percentile convention, named once and applied everywhere.
PERCENTILE_CONVENTION = "nearest-rank"

# The divisor is published at 8.0. Its only call site,
# compute_utilization() in quoin/quoin/hooks/_lib.sh, applies it to wc -c of
# the WHOLE session JSONL file (structural overhead, tool results, metadata),
# not to payload text bytes, which is what this instrument measures. Citing
# that call site names the constant's ORIGIN, not validation for this use —
# the category error is published alongside the number, never silently.
BYTES_PER_TOKEN_DIVISOR = 8.0

# Below this per-group n, a percentile is not reported as a percentile — the
# max is reported and labeled the max instead (per-phase n runs as low as 2
# in the live corpus, where p99 equals the max under every convention).
_MIN_N_FOR_PERCENTILE = 10


def _nearest_rank_from_sorted(xs_sorted, p):
    """`nearest_rank_percentile`'s index arithmetic over an ALREADY-sorted
    sequence. `nearest_rank_percentile` itself calls this after sorting
    once; `_series_stats` calls it directly so a group's values are
    sorted once per group rather than once per percentile it reports (up
    to three — p50, p90, p99 — over the same series).
    """
    if not xs_sorted:
        return None
    idx = max(0, math.ceil(p * len(xs_sorted)) - 1)
    return xs_sorted[idx]


def nearest_rank_percentile(values, p):
    """Nearest-rank percentile, the one fixed convention this module uses.

    `sorted(xs)[max(0, ceil(p * len(xs)) - 1)]`. `p` is a fraction in
    [0, 1]. Returns None for an empty `values` — callers decide how to
    report that rather than this function inventing a default.
    """
    return _nearest_rank_from_sorted(sorted(values), p)


def _byte_len(text):
    return len(text.encode("utf-8")) if text else 0


def dispatch_bytes(record):
    """Dispatch-payload byte count for one capture_corpus record.

    Also accepts a snapshot record, which carries the count directly as
    `dispatch_bytes` (never payload text, by design) rather than a
    `dispatch_text` field. Checking for the precomputed key first is what
    lets `channel_stats` run unmodified over either shape: the same
    statistics function, not a reimplementation, is what proves a live
    run and a snapshot replay agree.
    """
    if "dispatch_bytes" in record:
        return record["dispatch_bytes"]
    return _byte_len(record.get("dispatch_text", ""))


def return_bytes(record):
    """Return-payload byte count for one capture_corpus record.

    See `dispatch_bytes` — also accepts a snapshot record's precomputed
    `return_bytes`.
    """
    if "return_bytes" in record:
        return record["return_bytes"]
    return _byte_len(record.get("return_text", ""))


def _series_stats(values, group_n, include_p99):
    if not values:
        return {
            "n": 0, "mean": None, "max": None, "p50": None, "p90": None,
            "p99": None, "reported_as_max": False,
            "convention": PERCENTILE_CONVENTION,
        }
    # Sorted once here rather than once per percentile below — up to three
    # (p50, p90, p99) read the same series.
    xs_sorted = sorted(values)
    result = {
        "n": len(values),
        "mean": sum(values) / len(values),
        "max": xs_sorted[-1],
        "convention": PERCENTILE_CONVENTION,
    }
    if group_n < _MIN_N_FOR_PERCENTILE:
        result["p50"] = None
        result["p90"] = None
        result["reported_as_max"] = True
    else:
        result["p50"] = _nearest_rank_from_sorted(xs_sorted, 0.50)
        result["p90"] = _nearest_rank_from_sorted(xs_sorted, 0.90)
        result["reported_as_max"] = False
    result["p99"] = _nearest_rank_from_sorted(xs_sorted, 0.99) if include_p99 else None
    return result


def _group_channel_stats(group, include_p99):
    d = [dispatch_bytes(r) for r in group]
    rt = [return_bytes(r) for r in group]
    ratios = [b / a for a, b in zip(d, rt) if a > 0]
    n = len(group)
    return {
        "n": n,
        "dispatch": _series_stats(d, n, include_p99),
        "return": _series_stats(rt, n, include_p99),
        "ratio": _series_stats(ratios, n, include_p99),
    }


def channel_stats(records):
    """Per-phase and overall dispatch/return byte statistics.

    Groups `records` (each carrying `phase`, `dispatch_text`, `return_text`)
    by `phase`. Reports n, p50, p90 and mean of dispatch bytes, return
    bytes, and the return/dispatch ratio, per phase and overall, all under
    the nearest-rank convention. p99 is reported ONLY for the
    overall pool, never per phase — per-phase n can be as low as 2, where
    p99 equals the max under every convention and publishing it as a
    percentile overstates precision. Where a group's n is below
    `_MIN_N_FOR_PERCENTILE` (10), p50/p90 are withheld and the max is
    reported in their place, labeled `reported_as_max`.
    """
    by_phase = {}
    for r in records:
        by_phase.setdefault(r.get("phase"), []).append(r)
    per_phase = {
        phase: _group_channel_stats(group, include_p99=False)
        for phase, group in by_phase.items()
    }
    overall = _group_channel_stats(records, include_p99=True)
    return {
        "per_phase": per_phase,
        "overall": overall,
        "byte_divisor": BYTES_PER_TOKEN_DIVISOR,
        "byte_divisor_note": (
            "8.0 is the QUOIN_BYTES_PER_TOKEN default at "
            "quoin/quoin/hooks/_lib.sh:48 — that citation names the "
            "constant's origin, not evidence it fits this use; its only "
            "call site applies it to whole-session JSONL bytes, not "
            "payload text bytes."
        ),
    }


def token_validity(record):
    """Per-record token-cross-check fields, return direction only.

    `presence`: the last assistant message's `usage` carries an
    `output_tokens` field at all. `validity`:
    `stop_reason == "end_turn"` — presence is not validity, and treating
    presence as a proxy for validity was the round-1 defect this gates
    against. `thinking_tokens` is the raw
    `output_tokens_details.thinking_tokens` value when the field is
    present, else None — the missing-as-zero adjustment rule is applied by
    the aggregator (`token_cross_check`), not here, so this stays a pure
    per-record read.

    Also accepts a snapshot record (no `last_assistant` key, but
    `stop_reason` / `output_tokens` / `thinking_tokens` carried directly) —
    dispatched to `_token_validity_flat` — so callers built against this
    function's return shape work identically over a live capture or a
    `--from-snapshot` replay.
    """
    if "last_assistant" not in record:
        return _token_validity_flat(record)
    last = record.get("last_assistant") or {}
    message = last.get("message", {}) if isinstance(last, dict) else {}
    usage = message.get("usage") if isinstance(message, dict) else None
    if not isinstance(usage, dict):
        usage = {}
    stop_reason = message.get("stop_reason") if isinstance(message, dict) else None
    presence = "output_tokens" in usage
    output_tokens = usage.get("output_tokens") if presence else None
    validity = stop_reason == "end_turn"
    details = usage.get("output_tokens_details")
    thinking_present = isinstance(details, dict) and "thinking_tokens" in details
    thinking_tokens = details.get("thinking_tokens") if thinking_present else None
    return {
        "presence": presence,
        "validity": validity,
        "stop_reason": stop_reason,
        "output_tokens": output_tokens,
        "thinking_present": thinking_present,
        "thinking_tokens": thinking_tokens,
    }


def _token_validity_flat(record):
    """token_validity's flat-shape branch, for a snapshot record.

    A snapshot record carries `stop_reason` / `output_tokens` /
    `thinking_tokens` directly (extracted once at capture time) rather than
    a `last_assistant` row to re-derive them from. `None` on either field
    means "absent", exactly as the nested path's `presence` /
    `thinking_present` booleans do.
    """
    output_tokens = record.get("output_tokens")
    thinking_tokens = record.get("thinking_tokens")
    stop_reason = record.get("stop_reason")
    return {
        "presence": output_tokens is not None,
        "validity": stop_reason == "end_turn",
        "stop_reason": stop_reason,
        "output_tokens": output_tokens,
        "thinking_present": thinking_tokens is not None,
        "thinking_tokens": thinking_tokens,
    }


def token_cross_check(records):
    """Return-direction token cross-check over run-owned records.

    Reports presence, validity and thinking-coverage as three DISTINCT
    fractions — presence is not validity. The headline is the POOLED
    ratio (sum of return bytes over sum of output tokens across admitted
    rows), never a median of per-row ratios; per-row mean and median are
    reported alongside, over both the gated (`validity == True`) and
    ungated populations, so a reader can see the ungated distribution is
    pathological rather than merely noisy. The thinking-adjustment rule is
    named: MISSING MEANS ZERO — a row without
    `output_tokens_details.thinking_tokens` contributes its `output_tokens`
    unadjusted and stays in the population. Excluded (non-`end_turn`) rows
    are broken out by their `stop_reason` value. `output_tokens` counts the
    entire final API message including thinking and tool-use content while
    the byte count is text-only, so every ratio here is a lower bound by
    construction.
    """
    n = len(records)
    presence_n = 0
    validity_n = 0
    thinking_n = 0
    excluded_by_reason = {}

    gated_bytes = gated_tokens = gated_thinking_tokens = 0
    gated_ratios = []
    ungated_bytes = ungated_tokens = ungated_thinking_tokens = 0
    ungated_ratios = []

    for r in records:
        tv = token_validity(r)
        rb = return_bytes(r)
        if tv["presence"]:
            presence_n += 1
        if tv["thinking_present"]:
            thinking_n += 1
        if not tv["validity"]:
            excluded_by_reason[tv["stop_reason"]] = (
                excluded_by_reason.get(tv["stop_reason"], 0) + 1
            )
        else:
            validity_n += 1

        output_tokens = tv["output_tokens"]
        if output_tokens is None:
            continue
        thinking_tokens = tv["thinking_tokens"] if tv["thinking_tokens"] is not None else 0
        ratio = (rb / output_tokens) if output_tokens else None

        ungated_bytes += rb
        ungated_tokens += output_tokens
        ungated_thinking_tokens += output_tokens + thinking_tokens
        if ratio is not None:
            ungated_ratios.append(ratio)

        if tv["validity"]:
            gated_bytes += rb
            gated_tokens += output_tokens
            gated_thinking_tokens += output_tokens + thinking_tokens
            if ratio is not None:
                gated_ratios.append(ratio)

    def _pooled(bytes_total, tokens_total):
        return (bytes_total / tokens_total) if tokens_total else None

    def _mean(xs):
        return (sum(xs) / len(xs)) if xs else None

    def _population(bytes_total, tokens_total, thinking_tokens_total, ratios):
        return {
            "pooled_ratio": _pooled(bytes_total, tokens_total),
            "pooled_ratio_thinking_adjusted": _pooled(bytes_total, thinking_tokens_total),
            "mean_of_row_ratios": _mean(ratios),
            "median_of_row_ratios": nearest_rank_percentile(ratios, 0.50),
        }

    return {
        "n": n,
        "presence_fraction": (presence_n / n) if n else None,
        "validity_fraction": (validity_n / n) if n else None,
        "thinking_coverage_fraction": (thinking_n / n) if n else None,
        "excluded_by_stop_reason": excluded_by_reason,
        "gated": _population(gated_bytes, gated_tokens, gated_thinking_tokens, gated_ratios),
        "ungated": _population(ungated_bytes, ungated_tokens, ungated_thinking_tokens, ungated_ratios),
        "thinking_adjustment_rule": "missing-means-zero",
        "lower_bound_note": (
            "output_tokens counts the entire final API message including "
            "thinking and tool-use content, while the byte count is "
            "text-only, so the implied bytes-per-token ratio is a lower "
            "bound by construction."
        ),
        "percentile_convention": PERCENTILE_CONVENTION,
    }


# ---------------------------------------------------------------------------
# Snapshot mode — the reproducibility contract
# ---------------------------------------------------------------------------
#
# PARTIAL, same discipline the rest of this file already uses: the schema
# below carries every field the write/load/recompute contract names, but
# two of them ship as explicit `None` placeholders rather than real
# values — `channel_three` and `growth_bound`. `sentinel_bucket` is NOT
# one of them: `sentinel_bucket()` below builds the real label and it is
# wired into every record `_snapshot_record` produces, so it is non-null
# in every record. `channel_three` stays `None` at the per-record level
# because capture_corpus does not yet carry a spawn's own tool_use_id, so
# a per-spawn boundary-attribution slice cannot be joined onto a specific
# subagent-transcript record. `growth_bound` stays `None` for a different
# reason: the estimator itself is built and fixture-tested (see
# `growth_bound()` below), but it takes a whole `run_owned_records` list
# and produces one corpus-level figure, not a per-record value, so it has
# no natural single-record slot to fill. Recorded as NOT DONE rather than
# filled with fabricated values. Wiring `channel_three` per record and
# deferring live-corpus re-derivation to a later pass are still open work.

SNAPSHOT_SCHEMA_VERSION = 1

# Sentinel-bucket classification. The on-behalf sentinel marks an
# orchestrator-spawned phase, the closest available discriminator for the
# migrated population, but it is necessary-not-sufficient because
# /thorough_plan also spawns on-behalf.
_SENTINEL_MARKERS = (
    ("on_behalf", "[quoin-onbehalf]"),
    ("no_interactive", "[no-interactive]"),
    ("no_redispatch", "[no-redispatch]"),
)


def sentinel_bucket(dispatch_text):
    """Sentinel-bucket label for one dispatch payload's text.

    Returns a `+`-joined label of the sentinel markers present (checked in a
    fixed order: on_behalf, no_interactive, no_redispatch), or `"none"` when
    none are present. A record's `sentinel_bucket` is this label, not a
    boolean — the baseline reports the bucket distribution, not just the
    on-behalf count.
    """
    text = dispatch_text or ""
    present = [name for name, marker in _SENTINEL_MARKERS if marker in text]
    return "+".join(present) if present else "none"


# ---------------------------------------------------------------------------
# Envelope partition, envelope-anchored phase discriminator (D-07)
# ---------------------------------------------------------------------------

_ENVELOPE_MARKER_PREFIX = "[quoin-handoff"
_ENVELOPE_CLOSE_MARKER = "[/quoin-handoff]"
# Prefix-matches the version ("[quoin-handoff/1.0 dispatch]",
# "[quoin-handoff/1.1 dispatch]", ...) rather than a pinned literal, so a
# later minor-version envelope still resolves.
_ENVELOPE_DISPATCH_OPEN_RE = re.compile(r"\[quoin-handoff/[^\]\n]*\sdispatch\]")
_ENVELOPE_SKILL_FIELD_RE = re.compile(r"^\s*skill:\s*(\S+)\s*$", re.MULTILINE)
# Direction-anchored version capture (T-02): applied to dispatch_text and
# return_text SEPARATELY, never to the same text with the same pattern. A
# single record can legitimately carry a dispatch marker of one version and
# a return marker of another (e.g. run/SKILL.md appends the full 1.0 return
# template to every spawn prompt, so dispatch_text itself can contain both
# a versioned dispatch marker and a 1.0 return marker) — direction anchoring
# is what keeps the two from being conflated.
_ENVELOPE_DISPATCH_VERSION_RE = re.compile(r"\[quoin-handoff/(\d+)\.(\d+)\s+dispatch\]")
_ENVELOPE_RETURN_VERSION_RE = re.compile(r"\[quoin-handoff/(\d+)\.(\d+)\s+return\]")


def envelope_partition(records):
    """Per-record dispatch/return envelope-marker presence, plus aggregate
    and per-phase counts.

    Matches the bare marker prefix `[quoin-handoff`, never a version-pinned
    literal, so a `1.1` envelope still counts. Presence is a plain substring
    test, so surrounding whitespace/indentation before the marker never
    affects detection. Only run-owned records (per the legacy predicate)
    contribute to `per_phase` — this mirrors the corpus-wide per-phase
    counters `capture_corpus()` already reports.

    Also reports `dispatch_version`/`return_version` per record (T-02):
    `"{major}.{minor}"` when that direction's marker is present AND the
    direction-anchored regex matches, `None` when the direction's marker is
    absent OR present but unparseable (a major-only or malformed marker) —
    conflating "no marker" and "unparseable marker" into one bucket is a
    deliberate tradeoff. `per_dispatch_version`/`per_return_version` bucket
    ALL records (the same population `dispatch_envelope_count`/
    `return_envelope_count` use, not the run_owned-gated `per_phase`
    population); each bucket is `{"n": <count>}` only.
    """
    per_record = []
    dispatch_count = 0
    return_count = 0
    per_phase = {}
    per_dispatch_version = {}
    per_return_version = {}
    for r in records:
        dispatch_text = r.get("dispatch_text") or ""
        return_text = r.get("return_text") or ""
        has_dispatch = _ENVELOPE_MARKER_PREFIX in dispatch_text
        has_return = _ENVELOPE_MARKER_PREFIX in return_text
        if has_dispatch:
            dispatch_count += 1
        if has_return:
            return_count += 1
        dispatch_version_match = _ENVELOPE_DISPATCH_VERSION_RE.search(dispatch_text)
        return_version_match = _ENVELOPE_RETURN_VERSION_RE.search(return_text)
        dispatch_version = (
            f"{dispatch_version_match.group(1)}.{dispatch_version_match.group(2)}"
            if has_dispatch and dispatch_version_match else None
        )
        return_version = (
            f"{return_version_match.group(1)}.{return_version_match.group(2)}"
            if has_return and return_version_match else None
        )
        per_dispatch_version.setdefault(dispatch_version, {"n": 0})["n"] += 1
        per_return_version.setdefault(return_version, {"n": 0})["n"] += 1
        per_record.append({
            "path": r.get("path"),
            "dispatch_envelope": has_dispatch,
            "return_envelope": has_return,
            "dispatch_version": dispatch_version,
            "return_version": return_version,
        })
        if r.get("run_owned"):
            bucket = per_phase.setdefault(
                r.get("phase"), {"n": 0, "dispatch_envelope": 0, "return_envelope": 0},
            )
            bucket["n"] += 1
            if has_dispatch:
                bucket["dispatch_envelope"] += 1
            if has_return:
                bucket["return_envelope"] += 1
    return {
        "n": len(records),
        "dispatch_envelope_count": dispatch_count,
        "return_envelope_count": return_count,
        "per_phase": per_phase,
        "per_dispatch_version": per_dispatch_version,
        "per_return_version": per_return_version,
        "per_record": per_record,
    }


def envelope_phase(dispatch_text):
    """Migration-stable phase discriminator (D-07).

    Searches the FULL dispatch text (never sniff-limited, unlike
    `detect_phase()`) for a `[quoin-handoff/<ver> dispatch]` ...
    `[/quoin-handoff]` block and returns its `skill:` field value, or None
    when no such block (or no `skill:` field inside it) is found. This is
    a second, additive predicate published beside `detect_phase()` — it
    does not read or modify `_DISPATCH_SNIFF_BYTES`, and it never replaces
    the legacy detector (D-07).
    """
    if not dispatch_text:
        return None
    open_match = _ENVELOPE_DISPATCH_OPEN_RE.search(dispatch_text)
    if open_match is None:
        return None
    close_idx = dispatch_text.find(_ENVELOPE_CLOSE_MARKER, open_match.end())
    if close_idx == -1:
        return None
    block = dispatch_text[open_match.end():close_idx]
    skill_match = _ENVELOPE_SKILL_FIELD_RE.search(block)
    if skill_match is None:
        return None
    return skill_match.group(1)


def _ordinal_label_map(raw_values, prefix):
    """Deterministic ordinal labels for a set of raw identifier strings.

    Each raw value is assigned `<prefix>-1`, `<prefix>-2`, ... in the order
    of its own SHA-256 digest, never in input or filesystem order, so the
    assignment carries no information about which value sorts where beyond
    a random-looking tiebreak. The property that actually holds: nothing
    committed maps a label back to a raw value, and nothing committed
    confirms whether any given raw value is even a member of the set — the
    snapshot carries ordinal labels only, never raw values or their
    hashes. This is weaker than true non-invertibility, though: a party
    who already holds the real corpus values can compute the same SHA-256
    digest order over their own candidate set and localize a known raw
    value's label to within `O(sqrt(N))` ranks by digest collisions alone,
    without needing anything from the snapshot itself. A keyed HMAC was
    considered and rejected — an uncommitted key would make a second party's
    regenerated snapshot non-comparable to the committed one, which is the
    property the snapshot task exists to deliver.

    The label a given raw value receives is stable across two captures of
    the SAME set of raw values (same input set, same digest order, same
    label), but it is NOT stable across a changed set: the same raw value
    can receive a different ordinal on a different machine (a different
    set of sibling projects/sessions/spawns on disk), or after the corpus
    this set was drawn from grows or shrinks. Reproducibility is delivered
    by the committed snapshot file itself, not by a label that survives
    corpus churn.
    """
    ranked = sorted(raw_values, key=lambda v: hashlib.sha256(v.encode("utf-8")).hexdigest())
    return {v: f"{prefix}-{i + 1}" for i, v in enumerate(ranked)}


def _split_transcript_rel_path(rel):
    """Split a transcript path already relative to `_projects_root`,
    POSIX-separated, into its `(project_dir, sid, spawn_file)` triple —
    the same three components `_corpus_label_maps` and `stable_id` each
    used to derive independently. `sid` and `spawn_file` are `""` when
    `rel` has no path segment below the project directory.
    """
    project_dir, sep, remainder = rel.partition("/")
    if not sep:
        return project_dir, "", ""
    sid, _, tail = remainder.partition("/")
    spawn_file = tail.rsplit("/", 1)[-1]
    return project_dir, sid, spawn_file


def _corpus_label_maps(corpus, home):
    """Build the three ordinal label maps `stable_id` needs from a full
    `capture_corpus()` result — one map each for the project directory, the
    parent session id and the per-session spawn (subagent transcript file)
    component of every record's path. Built once per snapshot build (a
    "second pass" over the corpus, after the paths are known) so every
    record's `stable_id` call draws from the same, corpus-wide maps.
    """
    root = _projects_root(home)
    project_dirs = set()
    sids = set()
    spawns_by_sid = {}
    for r in corpus["records"]:
        rel = Path(r["path"]).relative_to(root).as_posix()
        project_dir, sid, spawn_file = _split_transcript_rel_path(rel)
        project_dirs.add(project_dir)
        sids.add(sid)
        spawns_by_sid.setdefault(sid, set()).add(spawn_file)

    project_map = _ordinal_label_map(project_dirs, "project")
    session_map = _ordinal_label_map(sids, "session")
    spawn_map = {}
    for sid, spawn_files in spawns_by_sid.items():
        for spawn_file, label in _ordinal_label_map(spawn_files, "spawn").items():
            spawn_map[(sid, spawn_file)] = label
    return project_map, session_map, spawn_map


def stable_id(path, home, project_map, session_map, spawn_map):
    """Per-record identifier: the transcript path relative to
    <home>/.claude/projects, with every component that carries a real
    identifier replaced by an opaque ordinal label.

    `project_map`, `session_map` and `spawn_map` come from
    `_corpus_label_maps` — a single pass over the whole corpus, built once
    per snapshot build, so every record's id draws from the same,
    consistently-ranked maps. The path has three real identifiers: the
    project directory (Claude Code's sanitized-absolute-path directory
    name, which embeds the real filesystem path of whatever project
    produced the transcript), the parent session UUID, and the subagent
    transcript's own UUID filename. All three are ordinal-labeled; none is
    carried verbatim or hashed into the id — a bare hash of a low-entropy
    value like a project name is dictionary-attackable, and carrying the
    real session/spawn UUIDs at all, hashed or not, would still let a
    holder of this project's own workflow-artifacts ledgers join back to
    this snapshot's real activity window.

    Stable across two captures of the SAME corpus (see `_ordinal_label_map`
    for the precise stability contract), NOT stable across live-corpus
    growth or shrinkage — a transcript present in one capture and gone by
    the next has no corresponding id in the other, and a project/session/
    spawn common to both captures can still receive a different label if
    the surrounding set changed. Reproducibility is delivered by the
    committed snapshot file itself, not by an id that survives corpus
    churn.
    """
    root = _projects_root(home)
    rel = Path(path).relative_to(root).as_posix()
    project_dir, sid, spawn_file = _split_transcript_rel_path(rel)
    project_label = project_map[project_dir]
    if not sid:
        return project_label
    session_label = session_map[sid]
    spawn_label = spawn_map[(sid, spawn_file)]
    return f"{project_label}/{session_label}/{spawn_label}"


def build_snapshot_record(record, home, project_map, session_map, spawn_map):
    """Assemble one snapshot record from a capture_corpus record.

    Carries counts and identifiers only, never payload text: the stable
    id, phase, run-owned flag, dispatch/return byte counts, and the
    token-cross-check's per-record fields (stop_reason, output_tokens,
    thinking_tokens) via `token_validity`. The real parent-session UUID is
    NOT carried as a separate field — it has no snapshot consumer (its only
    reads are inside the live growth-bound path over `capture_corpus`
    records, never over a loaded snapshot), and carrying it verbatim would
    undo the anonymization `stable_id`'s ordinal labels provide: a holder
    of a project's own workflow-artifacts cost-ledger files could join a
    real session UUID back to that project's activity window.
    `project_map`/`session_map`/`spawn_map` come from `_corpus_label_maps`
    and are threaded through to `stable_id` unchanged.

    See the module-level PARTIAL note above the snapshot-mode section
    header for why `channel_three` and `growth_bound` are still `None`
    placeholders (`sentinel_bucket` is real — see its own docstring).
    """
    tv = token_validity(record)
    return {
        "id": stable_id(record["path"], home, project_map, session_map, spawn_map),
        "phase": record.get("phase"),
        "run_owned": bool(record.get("run_owned", False)),
        "sentinel_bucket": sentinel_bucket(record.get("dispatch_text", "")),
        "dispatch_bytes": dispatch_bytes(record),
        "return_bytes": return_bytes(record),
        "output_tokens": tv["output_tokens"],
        "thinking_tokens": tv["thinking_tokens"],
        "stop_reason": tv["stop_reason"],
        "channel_three": None,
        "growth_bound": None,
    }


def build_snapshot(corpus, home):
    """Build a full snapshot dict from a capture_corpus() result.

    Records are sorted by their stable id, so two captures of an
    unchanged corpus — and a live capture versus a `--from-snapshot`
    replay of the file it wrote — emit byte-identical JSON. Corpus-level
    counters ride alongside so a snapshot consumer sees the same header a
    live run prints. The ordinal label maps are built once, in a single
    pass over the whole corpus, before any record is assembled, so every
    record's id draws from the same maps.
    """
    project_map, session_map, spawn_map = _corpus_label_maps(corpus, home)
    records = [
        build_snapshot_record(r, home, project_map, session_map, spawn_map)
        for r in corpus["records"]
    ]
    records.sort(key=lambda r: r["id"])
    return {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "transcripts": corpus["transcripts"],
        "parsed": corpus["parsed"],
        "skipped_unreadable": corpus["skipped_unreadable"],
        "skill_matched": corpus["skill_matched"],
        "run_owned": corpus["run_owned"],
        "records": records,
    }


def write_snapshot(path, snapshot):
    """Write a snapshot dict as deterministic JSON.

    `sort_keys=True` plus a fixed indent make two writes of an identical
    snapshot dict byte-identical — the property the ack's
    two-consecutive-runs requirement checks (via `--from-snapshot`
    replaying the same written file, not via re-writing it).
    """
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(snapshot, fh, sort_keys=True, indent=2)
        fh.write("\n")


_SNAPSHOT_REQUIRED_KEYS = (
    "schema_version",
    "transcripts",
    "parsed",
    "skipped_unreadable",
    "skill_matched",
    "run_owned",
    "records",
)


def load_snapshot(path):
    """Load a snapshot written by `write_snapshot`.

    Validates `schema_version` against `SNAPSHOT_SCHEMA_VERSION` and the
    presence of every key `build_snapshot` returns before handing the
    snapshot back. `corpus_captured_at` is CLI-only metadata added after
    `build_snapshot` runs (see `main`), so it is not in the required set —
    a snapshot written without `--snapshot`'s caller stamping it is still
    valid. Raises `ValueError` on either failure; the CLI maps that into
    the same invocation-error exit as a malformed file.
    """
    with open(path, "r", encoding="utf-8") as fh:
        snapshot = json.load(fh)
    version = snapshot.get("schema_version")
    if version != SNAPSHOT_SCHEMA_VERSION:
        raise ValueError(
            f"snapshot schema_version {version!r} does not match the "
            f"supported version {SNAPSHOT_SCHEMA_VERSION!r}"
        )
    missing = [key for key in _SNAPSHOT_REQUIRED_KEYS if key not in snapshot]
    if missing:
        raise ValueError(f"snapshot is missing required key(s): {', '.join(missing)}")
    return snapshot


def channel_stats_from_snapshot(snapshot):
    """`channel_stats` over a snapshot's records — no filesystem access.

    Reuses `channel_stats` unmodified: `dispatch_bytes` / `return_bytes`
    read a snapshot record's precomputed byte counts directly (see their
    docstrings), so this is the SAME statistics function a live run uses,
    not a reimplementation — which is what makes a live run and a
    `--from-snapshot` replay provably agree.
    """
    return channel_stats(snapshot["records"])


def token_cross_check_from_snapshot(snapshot):
    """`token_cross_check` over a snapshot's run-owned records — no
    filesystem access. See `channel_stats_from_snapshot`: same function,
    same agreement guarantee.
    """
    run_owned = [r for r in snapshot["records"] if r.get("run_owned")]
    return token_cross_check(run_owned)


# ---------------------------------------------------------------------------
# Channel three — orchestrator-side artifact re-read bytes
# ---------------------------------------------------------------------------

_WORKFLOW_ARTIFACTS_MARKER = ".workflow_artifacts"


def resolve_parent_transcript_path(transcript_path):
    """Resolve a subagent transcript's parent-session transcript path.

    `transcript_path` is `<home>/.claude/projects/<hash>/<sid>/subagents/<file>.jsonl`.
    The parent session id is `Path(transcript_path).parents[1].name` — the
    `<sid>` directory component, not `id` and not any other guess — and its
    transcript lives one level up, at `<home>/.claude/projects/<hash>/<sid>.jsonl`.
    """
    p = Path(transcript_path)
    sid = p.parents[1].name
    project_dir = p.parents[2]
    return project_dir / f"{sid}.jsonl"


def _tool_result_bytes(content):
    """Byte length of a `tool_result` block's `content`, str or block-list shape."""
    if isinstance(content, str):
        return _byte_len(content)
    if isinstance(content, list):
        total = 0
        for block in content:
            if not isinstance(block, dict):
                continue
            text = block.get("text")
            if isinstance(text, str):
                total += _byte_len(text)
        return total
    return 0


def iter_parent_tool_pairs(parent_transcript_path):
    """Walk a parent-session transcript, yielding paired tool_use/tool_result events.

    Builds `tool_use_id -> (name, input)` from assistant `tool_use` blocks and
    pairs each against a later user `tool_result` block on **`tool_use_id`**
    (not `id`, not `use_id` — the wrong key silently yields zero matches, which
    is why this behavior is pinned with an always-on test). A `tool_result` whose id
    matches no known `tool_use` contributes nothing and is not absorbed into
    any bucket. Returns an ordered list of dicts: `tool_use_id`, `name`,
    `input`, `result_bytes`.
    """
    pending = {}
    events = []
    with open(parent_transcript_path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            message = row.get("message")
            if not isinstance(message, dict):
                continue
            role = message.get("role")
            content = message.get("content")
            if role == "assistant" and isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        tid = block.get("id")
                        if tid is not None:
                            pending[tid] = (block.get("name"), block.get("input") or {})
            elif role == "user" and isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        tid = block.get("tool_use_id")
                        if tid is None or tid not in pending:
                            continue
                        name, tool_input = pending.pop(tid)
                        events.append({
                            "tool_use_id": tid,
                            "name": name,
                            "input": tool_input,
                            "result_bytes": _tool_result_bytes(block.get("content")),
                        })
    return events


def channel_three_for_session(parent_transcript_path, run_owned_tool_use_ids=None):
    """Channel-three extraction for one parent session.

    Sub-channel 3a is `Read` where `input.file_path` names a path under the
    workflow-artifacts tree; sub-channel 3b is `Bash` where `input.command`
    mentions that same tree. Also reports the `Agent` tool_result byte
    total as an independent cross-check on the subagent-transcript return
    figure.

    Per-boundary attribution: a 3a/3b call is attributed to the run-owned
    spawn whose `Agent` tool_result **immediately precedes it** in transcript
    order. Calls before the first run-owned spawn's return, and calls after
    the last, land in the `residual` bucket. `run_owned_tool_use_ids`
    restricts which `Agent` events count as boundaries (so a gate spawn's
    Agent return, interleaved between two run-owned ones, does not reset the
    boundary); pass None to treat every `Agent` return as a boundary.
    """
    events = iter_parent_tool_pairs(parent_transcript_path)

    boundary_indices = [
        i for i, ev in enumerate(events)
        if ev["name"] == "Agent"
        and (run_owned_tool_use_ids is None or ev["tool_use_id"] in run_owned_tool_use_ids)
    ]
    last_boundary_idx = boundary_indices[-1] if boundary_indices else -1

    sub_a_bytes = sub_a_calls = 0
    sub_b_bytes = sub_b_calls = 0
    agent_return_bytes = agent_return_calls = 0
    per_boundary = {}
    residual_bytes = residual_calls = 0
    current_boundary = None

    for i, ev in enumerate(events):
        name = ev["name"]
        if name == "Agent":
            agent_return_bytes += ev["result_bytes"]
            agent_return_calls += 1
            if i in boundary_indices:
                current_boundary = ev["tool_use_id"]
            continue
        tool_input = ev["input"]
        is_3a = name == "Read" and _WORKFLOW_ARTIFACTS_MARKER in str(tool_input.get("file_path", ""))
        is_3b = name == "Bash" and _WORKFLOW_ARTIFACTS_MARKER in str(tool_input.get("command", ""))
        if not (is_3a or is_3b):
            continue
        if is_3a:
            sub_a_bytes += ev["result_bytes"]
            sub_a_calls += 1
        if is_3b:
            sub_b_bytes += ev["result_bytes"]
            sub_b_calls += 1
        if current_boundary is None or i > last_boundary_idx:
            residual_bytes += ev["result_bytes"]
            residual_calls += 1
        else:
            b = per_boundary.setdefault(current_boundary, {"bytes": 0, "calls": 0})
            b["bytes"] += ev["result_bytes"]
            b["calls"] += 1

    return {
        "sub_a_bytes": sub_a_bytes, "sub_a_calls": sub_a_calls,
        "sub_b_bytes": sub_b_bytes, "sub_b_calls": sub_b_calls,
        "agent_return_bytes": agent_return_bytes, "agent_return_calls": agent_return_calls,
        "per_boundary": per_boundary,
        "residual_bytes": residual_bytes, "residual_calls": residual_calls,
    }


def _session_distribution(values):
    """Distribution stats for a list of per-session byte totals.

    Median and p90 are nearest-rank; reports mean, the zero-session
    count and the max alongside the ordered value list itself, so a reviewer
    can recompute under any convention.
    """
    ordered = sorted(values)
    n = len(ordered)
    return {
        "n": n,
        "values_ordered": ordered,
        "mean": (sum(ordered) / n) if n else None,
        "median": nearest_rank_percentile(ordered, 0.50),
        "p90": nearest_rank_percentile(ordered, 0.90),
        "zero_count": sum(1 for v in ordered if v == 0),
        "max": max(ordered) if ordered else None,
        "convention": PERCENTILE_CONVENTION,
    }


def channel_three_stats(session_results):
    """Aggregate channel-three figures across parent sessions.

    `session_results` is a list of `channel_three_for_session(...)` dicts,
    one per parent session carrying run-owned spawns. Reports both
    sub-channel totals with byte share and event share (byte share is the
    figure that matters here — the command bucket is high-count, low-byte
    traffic and a bare event share understates the read channel by roughly
    six times); per-call averages; the Agent-return cross-check total; the
    residual bucket's byte total and its share of the channel; and a
    per-session distribution for each sub-channel.
    """
    sub_a_bytes = sum(s["sub_a_bytes"] for s in session_results)
    sub_a_calls = sum(s["sub_a_calls"] for s in session_results)
    sub_b_bytes = sum(s["sub_b_bytes"] for s in session_results)
    sub_b_calls = sum(s["sub_b_calls"] for s in session_results)
    agent_return_bytes = sum(s["agent_return_bytes"] for s in session_results)
    residual_bytes = sum(s["residual_bytes"] for s in session_results)
    residual_calls = sum(s["residual_calls"] for s in session_results)
    total_bytes = sub_a_bytes + sub_b_bytes
    total_calls = sub_a_calls + sub_b_calls
    return {
        "sub_a_bytes": sub_a_bytes, "sub_a_calls": sub_a_calls,
        "sub_b_bytes": sub_b_bytes, "sub_b_calls": sub_b_calls,
        "sub_a_avg_bytes_per_call": (sub_a_bytes / sub_a_calls) if sub_a_calls else None,
        "sub_b_avg_bytes_per_call": (sub_b_bytes / sub_b_calls) if sub_b_calls else None,
        "byte_share_3a": (sub_a_bytes / total_bytes) if total_bytes else None,
        "event_share_3a": (sub_a_calls / total_calls) if total_calls else None,
        "sum_bytes": total_bytes,
        "agent_return_bytes": agent_return_bytes,
        "residual_bytes": residual_bytes,
        "residual_calls": residual_calls,
        "residual_share_of_sum": (residual_bytes / total_bytes) if total_bytes else None,
        "sub_a_per_session": _session_distribution([s["sub_a_bytes"] for s in session_results]),
        "sub_b_per_session": _session_distribution([s["sub_b_bytes"] for s in session_results]),
        "percentile_convention": PERCENTILE_CONVENTION,
        "stated_limits": (
            "Read calls with offset/limit count what was delivered, not file "
            "size; reads performed inside gate subagents are out of scope; "
            "Grep and Glob results are excluded."
        ),
    }


# ---------------------------------------------------------------------------
# Re-read growth-bound estimator
# ---------------------------------------------------------------------------

# proc:trigger's whole-envelope clamp. A spawn's "clamp-deleted bytes" — the
# ceiling the capped charge models below use — is max(0, return_bytes - this).
ENVELOPE_CLAMP_B = 1024

_GENERIC_ABS_PREFIXES = ("Users", "tmp", "private", "var", "opt", "etc")
_CANDIDATE_TRAILING_STRIP = " .,;:)]}"


def _candidate_path_regex(home, project_root):
    """Build the candidate-path regex for one (home, project_root) pair.

    An injectable-root prefix (home or project_root, regex-escaped) OR a
    generic absolute-path prefix not preceded by an alnum char, followed by
    a path body that admits spaces (this workspace's project root contains
    "My Drive") but excludes newline/tab/backtick/quote/angle-bracket/pipe/
    wildcard characters. Prose trailing a path is trimmed by the
    space-boundary resolver below, not by the regex itself.
    """
    roots = [re.escape(str(r)) for r in (home, project_root) if r]
    generic = "|".join(_GENERIC_ABS_PREFIXES)
    alts = roots + [rf"(?<![A-Za-z0-9])/(?:{generic})"]
    prefix = "(?:" + "|".join(alts) + ")"
    return re.compile(prefix + r"(?:/[^\n\r\t`\"'<>|*?]+)")


def _extract_raw_candidates(text, pattern):
    """Raw path candidates in `text`, right-stripped of trailing punctuation."""
    out = []
    for m in pattern.finditer(text or ""):
        s = m.group(0).rstrip(_CANDIDATE_TRAILING_STRIP)
        if s:
            out.append(s)
    return out


def _resolve_candidate(raw):
    """Resolve one raw candidate to the longest space-cut prefix that is an
    existing file, or None if no prefix resolves.
    """
    tokens = raw.split(" ")
    for cut in range(len(tokens), 0, -1):
        prefix = " ".join(tokens[:cut])
        if prefix and Path(prefix).is_file():
            return prefix
    return None


def _read_file_paths_in_session(parent_transcript_path):
    """Every `Read` tool_use `file_path` anywhere in a parent session,
    whole-session and regardless of pairing — this is the already-read rule.
    """
    paths = set()
    try:
        with open(parent_transcript_path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                message = row.get("message")
                if not isinstance(message, dict) or message.get("role") != "assistant":
                    continue
                content = message.get("content")
                if not isinstance(content, list):
                    continue
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_use" \
                            and block.get("name") == "Read":
                        fp = (block.get("input") or {}).get("file_path")
                        if isinstance(fp, str):
                            paths.add(fp)
    except (FileNotFoundError, PermissionError, OSError):
        pass
    return paths


def _bash_result_texts_in_session(parent_transcript_path):
    """Every Bash `tool_result` content string in a parent session, for the
    already-read rule widened to Bash-delivered reads.
    """
    texts = []
    try:
        with open(parent_transcript_path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                message = row.get("message")
                if not isinstance(message, dict) or message.get("role") != "user":
                    continue
                content = message.get("content")
                if not isinstance(content, list):
                    continue
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        c = block.get("content")
                        if isinstance(c, str):
                            texts.append(c)
                        elif isinstance(c, list):
                            for b2 in c:
                                if isinstance(b2, dict) and isinstance(b2.get("text"), str):
                                    texts.append(b2["text"])
    except (FileNotFoundError, PermissionError, OSError):
        pass
    return texts


def _self_written_paths_in_spawn(spawn_transcript_path):
    """`Write`/`Edit` tool_use `file_path` values in a spawn's OWN transcript
    (not the parent) — paths that spawn wrote and then, per the architecture's
    files-as-shared-workspace design, may have announced back to its parent.
    This is the self-written exclusion.
    """
    paths = set()
    try:
        with open(spawn_transcript_path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                message = row.get("message")
                if not isinstance(message, dict) or message.get("role") != "assistant":
                    continue
                content = message.get("content")
                if not isinstance(content, list):
                    continue
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_use" \
                            and block.get("name") in ("Write", "Edit"):
                        fp = (block.get("input") or {}).get("file_path")
                        if isinstance(fp, str):
                            paths.add(fp)
    except (FileNotFoundError, PermissionError, OSError):
        pass
    return paths


def contract_reads_in_spawn(spawn_transcript_path, contract_names=("handoff-format.md",)):
    """`Read` tool_use events in a SPAWN'S OWN transcript (not the parent)
    whose `input.file_path` ends in one of `contract_names` (MAJ-2's
    contract-read channel) — same file-open/JSON-line-tolerant/OSError-fail-
    open shape as `_self_written_paths_in_spawn`, reused rather than
    reimplemented.

    Returns True when the spawn's own transcript shows AT LEAST ONE such
    read, False otherwise. This is presence, not a count (MIN-14): a spawn
    that reads the contract twice reports the same True as one that reads
    it once, so a rate computed from this function's output is a LOWER
    BOUND on the true contract-read cost whenever any spawn re-reads.

    `contract_names` is passed straight to `str.endswith`, which requires
    a str or a tuple of str (a list raises TypeError) — coerced to a tuple
    here so either call shape works.
    """
    if isinstance(contract_names, list):
        contract_names = tuple(contract_names)
    try:
        with open(spawn_transcript_path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                message = row.get("message")
                if not isinstance(message, dict) or message.get("role") != "assistant":
                    continue
                content = message.get("content")
                if not isinstance(content, list):
                    continue
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_use" \
                            and block.get("name") == "Read":
                        fp = (block.get("input") or {}).get("file_path")
                        if isinstance(fp, str) and fp.endswith(contract_names):
                            return True
    except (FileNotFoundError, PermissionError, OSError):
        pass
    return False


def contract_read_partition(run_owned_records, contract_names=("handoff-format.md",)):
    """Over `run_owned_records`, report the count and fraction of spawns
    whose own transcript shows at least one `Read` of a name in
    `contract_names` (MAJ-2). Uses `contract_reads_in_spawn()` per record;
    `fraction` is None when `run_owned_records` is empty (never a
    ZeroDivisionError, mirroring `growth_bound()`'s `extraction_coverage`
    convention).
    """
    n = len(run_owned_records)
    hits = sum(1 for r in run_owned_records if contract_reads_in_spawn(r["path"], contract_names))
    return {"n": n, "hits": hits, "fraction": (hits / n) if n else None}


def growth_bound(run_owned_records, home, project_root,
                  already_read_scope="session",
                  path_filter="permissive",
                  exclude_self_written=False):
    """Re-read growth-bound estimator, one filter combination.

    `already_read_scope`: "session" (the published rule — whole parent
    session, any Read tool_use, paired or not), "session+bash" (widened to
    Bash-delivered reads), or "none" (filter removed entirely — a
    sensitivity variant).
    `path_filter`: "permissive" (published) or "workflow_artifacts_only".
    `exclude_self_written`: drop candidates the spawn's own transcript shows
    it wrote (the self-written-exclusion variant).

    Returns per-spawn detail (raw/resolved candidates, both charge models)
    plus aggregate figures: `charges` (charge instances) vs `distinct`
    (unique files) — the two differ whenever one file is charged by more
    than one spawn — `extraction_coverage` (fraction of return payloads
    yielding >=1 raw candidate, measured before resolution and before the
    already-read filter), and BOTH charge-model totals: whole on-disk file
    size (upper endpoint, `whole_*`) and clamp-deleted-bytes caps,
    per-candidate (`per_candidate_*`, the lower endpoint) and per-spawn
    (`per_spawn_cap_*`, reported alongside, not itself an endpoint). Per-spawn
    de-duplication is applied inline; `per_session_dedup_total` recomputes the
    whole-file model with de-duplication scoped to the parent session instead
    (a per-session-dedup sensitivity variant).
    """
    pattern = _candidate_path_regex(home, project_root)
    already_read_cache = {}
    bash_texts_cache = {}
    per_spawn = []
    coverage_hits = 0
    session_sizes = {}  # parent_session_id -> {path: size}, dedupes across spawns

    for record in run_owned_records:
        return_text = record.get("return_text", "")
        raw = _extract_raw_candidates(return_text, pattern)
        if raw:
            coverage_hits += 1

        parent_path = resolve_parent_transcript_path(record["path"])
        sid = parent_path.stem
        if sid not in already_read_cache:
            already_read_cache[sid] = _read_file_paths_in_session(parent_path)
        already_read = already_read_cache[sid] if already_read_scope != "none" else set()
        if already_read_scope == "session+bash":
            if sid not in bash_texts_cache:
                bash_texts_cache[sid] = _bash_result_texts_in_session(parent_path)
            bash_texts = bash_texts_cache[sid]
        else:
            bash_texts = []

        resolved = []
        seen = set()
        for r in raw:
            p = _resolve_candidate(r)
            if p is None:
                continue
            if path_filter == "workflow_artifacts_only" and _WORKFLOW_ARTIFACTS_MARKER not in p:
                continue
            if p in already_read:
                continue
            if bash_texts and any(p in t for t in bash_texts):
                continue
            if p in seen:
                continue
            seen.add(p)
            try:
                size = Path(p).stat().st_size
            except OSError:
                size = 0
            resolved.append({"path": p, "size": size})

        if exclude_self_written:
            self_written = _self_written_paths_in_spawn(record["path"])
            resolved = [r for r in resolved if r["path"] not in self_written]

        deleted_bytes = max(0, return_bytes(record) - ENVELOPE_CLAMP_B)
        whole_charge = sum(r["size"] for r in resolved)
        per_candidate_charge = sum(min(r["size"], deleted_bytes) for r in resolved)
        per_spawn_charge = min(whole_charge, deleted_bytes)

        per_spawn.append({
            "path": record["path"], "parent_session_id": sid,
            "raw_candidates": len(raw), "resolved": resolved,
            "deleted_bytes": deleted_bytes, "whole_charge": whole_charge,
            "per_candidate_charge": per_candidate_charge,
            "per_spawn_charge": per_spawn_charge,
        })
        for r in resolved:
            session_sizes.setdefault(sid, {})[r["path"]] = r["size"]

    n = len(run_owned_records)
    sessions = sorted({s["parent_session_id"] for s in per_spawn}) or \
        sorted({resolve_parent_transcript_path(r["path"]).stem for r in run_owned_records})
    n_sessions = len(sessions) or 1

    def _sum(key):
        return sum(s[key] for s in per_spawn)

    def _per_session(charge_key):
        totals = {sid: 0 for sid in sessions}
        for s in per_spawn:
            totals[s["parent_session_id"]] = totals.get(s["parent_session_id"], 0) + s[charge_key]
        return totals

    charges = sum(len(s["resolved"]) for s in per_spawn)
    distinct = len({r["path"] for s in per_spawn for r in s["resolved"]})
    dedup_total = sum(sum(sizes.values()) for sizes in session_sizes.values())

    return {
        "n_spawns": n, "n_sessions": n_sessions,
        "extraction_coverage": (coverage_hits / n) if n else None,
        "charges": charges, "distinct": distinct,
        "per_spawn": per_spawn,
        "whole_total": _sum("whole_charge"),
        "whole_per_run": (_sum("whole_charge") / n_sessions) if n_sessions else None,
        "per_candidate_total": _sum("per_candidate_charge"),
        "per_candidate_per_run": (_sum("per_candidate_charge") / n_sessions) if n_sessions else None,
        "per_spawn_cap_total": _sum("per_spawn_charge"),
        "per_spawn_cap_per_run": (_sum("per_spawn_charge") / n_sessions) if n_sessions else None,
        "per_session_dedup_total": dedup_total,
        "per_session_dedup_per_run": (dedup_total / n_sessions) if n_sessions else None,
        "per_session_whole": _per_session("whole_charge"),
        "per_session_lower": _per_session("per_candidate_charge"),
    }


def _print_channel_report(stats, tcc):
    """Print the channel one/two and token-cross-check summary shared by
    the live-capture and `--from-snapshot` code paths in `main()`.

    Takes an already-computed `channel_stats()`/`channel_stats_from_snapshot()`
    result and an already-computed `token_cross_check()`/
    `token_cross_check_from_snapshot()` result, so this function has no
    filesystem access of its own — the caller decides live vs. snapshot.

    Emits every field `token_cross_check()` returns, not a subset: the
    gated population is the headline figure, but the ungated population and
    the excluded-by-reason breakdown are published figures too, and every
    one of them needs to be printable from a loaded snapshot for the
    reproducibility scope statement to hold.
    """
    overall = stats["overall"]
    for label in ("dispatch", "return", "ratio"):
        s = overall[label]
        print(f"{label}: n={s['n']} p50={s['p50']} p90={s['p90']} p99={s['p99']} "
              f"mean={s['mean']} max={s['max']} reported_as_max={s['reported_as_max']} "
              f"convention={s['convention']}")
    print(f"byte_divisor={stats['byte_divisor']}")
    print(f"token_cross_check: n={tcc['n']} presence_fraction={tcc['presence_fraction']} "
          f"validity_fraction={tcc['validity_fraction']} "
          f"thinking_coverage_fraction={tcc['thinking_coverage_fraction']}")
    print(f"excluded_by_stop_reason={tcc['excluded_by_stop_reason']}")
    for population in ("gated", "ungated"):
        p = tcc[population]
        print(f"{population}_pooled_ratio={p['pooled_ratio']} "
              f"{population}_pooled_ratio_thinking_adjusted={p['pooled_ratio_thinking_adjusted']} "
              f"{population}_mean_of_row_ratios={p['mean_of_row_ratios']} "
              f"{population}_median_of_row_ratios={p['median_of_row_ratios']}")


def _build_arg_parser():
    parser = argparse.ArgumentParser(
        prog="handoff_measure.py",
        description="Measure agent handoff dispatch/return payload sizes "
                     "over the nested Claude Code subagent transcript tree "
                     "(IVG-248 stage 1 instrument).",
    )
    parser.add_argument(
        "--home", default=str(Path.home()),
        help="Root containing .claude/projects/ (default: the real home dir).",
    )
    parser.add_argument(
        "--project-filter", default=None,
        help="Only consider transcripts under a project-hash dir containing this substring.",
    )
    parser.add_argument(
        "--snapshot", default=None,
        help="Write a T-05 reproducibility snapshot JSON to this path after a live capture.",
    )
    parser.add_argument(
        "--from-snapshot", default=None,
        help="Recompute channel one/two dispatch/return statistics and the token "
             "cross-check from this snapshot file; no live filesystem access, --home and "
             "--project-filter are ignored. Channel three and the growth-bound estimator "
             "are not in the snapshot (see the baseline artifact's reproducibility scope "
             "statement) and are not recomputed by this flag.",
    )
    parser.add_argument(
        "--envelope-partition", action="store_true",
        help="Print dispatch/return envelope-marker partition counts and per-phase "
             "split over the live-captured corpus.",
    )
    parser.add_argument(
        "--envelope-phase-partition", action="store_true",
        help="Print run-owned counts under the envelope-anchored phase discriminator "
             "(D-07), beside the legacy detect_phase() counts, over the live-captured corpus.",
    )
    parser.add_argument(
        "--contract-read-partition", action="store_true",
        help="Print the count and fraction of run-owned (legacy-predicate) spawns whose "
             "own transcript shows a Read of handoff-format.md (the core), and separately "
             "of handoff-format-reference.md (the reference) (MAJ-2). Each file is measured "
             "via its own explicit single-element-tuple call, never a combined default.",
    )
    return parser


def main(argv=None):
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    if args.from_snapshot:
        try:
            snapshot = load_snapshot(args.from_snapshot)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            print(f"handoff_measure: invocation error: {exc}", file=sys.stderr)
            return 2
        print(f"snapshot_loaded={args.from_snapshot}")
        print(f"transcripts={snapshot['transcripts']} parsed={snapshot['parsed']} "
              f"skipped_unreadable={snapshot['skipped_unreadable']}")
        print(f"skill_matched={snapshot['skill_matched']} run_owned={snapshot['run_owned']}")
        if not snapshot["records"]:
            print("handoff_measure: empty snapshot; measurement refused", file=sys.stderr)
            return 1
        # Channel one/two is reported over the run-owned population (matching
        # the baseline's "n = 77 run-owned" convention), not every parsed
        # transcript — channel_stats_from_snapshot's own contract is to run
        # unmodified over whatever records it is given (see its docstring),
        # so the run-owned filter is applied here, at the call site, exactly
        # as the live path below applies it. `token_cross_check` runs
        # directly over the SAME filtered list rather than through
        # `token_cross_check_from_snapshot` (which re-derives its own
        # run-owned filter from the full snapshot) — one filtering pass,
        # not two.
        snapshot_run_owned = [r for r in snapshot["records"] if r.get("run_owned")]
        stats = channel_stats(snapshot_run_owned)
        tcc = token_cross_check(snapshot_run_owned)
        _print_channel_report(stats, tcc)
        return 0

    try:
        corpus = capture_corpus(args.home, project_filter=args.project_filter)
    except Exception as exc:  # invocation-level failure, not a per-file skip
        print(f"handoff_measure: invocation error: {exc}", file=sys.stderr)
        return 2
    captured_at = datetime.datetime.now().isoformat(timespec="seconds")
    print(f"corpus_captured_at={captured_at}")
    print(f"transcripts={corpus['transcripts']} parsed={corpus['parsed']} "
          f"skipped_unreadable={corpus['skipped_unreadable']}")
    print(f"skill_matched={corpus['skill_matched']} run_owned={corpus['run_owned']}")
    if args.snapshot:
        try:
            snapshot = build_snapshot(corpus, args.home)
            snapshot["corpus_captured_at"] = captured_at
            write_snapshot(args.snapshot, snapshot)
        except (OSError, KeyError, ValueError) as exc:
            print(f"handoff_measure: invocation error writing snapshot: {exc}", file=sys.stderr)
            return 2
        print(f"snapshot_written={args.snapshot}")
    if corpus["parsed"] == 0:
        print("handoff_measure: no transcripts matched the predicate; measurement refused",
              file=sys.stderr)
        return 1
    # Channel one/two is reported over the run-owned population (matching the
    # baseline's "n = 77 run-owned" convention), not every parsed transcript.
    run_owned = [r for r in corpus["records"] if r.get("run_owned")]
    stats = channel_stats(run_owned)
    tcc = token_cross_check(run_owned)
    _print_channel_report(stats, tcc)
    if args.envelope_partition:
        ep = envelope_partition(corpus["records"])
        print(f"envelope_partition: n={ep['n']} "
              f"dispatch_envelope_count={ep['dispatch_envelope_count']} "
              f"return_envelope_count={ep['return_envelope_count']}")
        for phase, counts in sorted(ep["per_phase"].items(), key=lambda kv: str(kv[0])):
            print(f"envelope_partition_phase={phase} n={counts['n']} "
                  f"dispatch_envelope={counts['dispatch_envelope']} "
                  f"return_envelope={counts['return_envelope']}")
        for version, counts in sorted(ep["per_dispatch_version"].items(), key=lambda kv: str(kv[0])):
            print(f"envelope_partition_dispatch_version={version} n={counts['n']}")
        for version, counts in sorted(ep["per_return_version"].items(), key=lambda kv: str(kv[0])):
            print(f"envelope_partition_return_version={version} n={counts['n']}")
    if args.envelope_phase_partition:
        envelope_run_owned = [
            r for r in corpus["records"]
            if envelope_phase(r.get("dispatch_text", "")) in RUN_OWNED_PHASES
        ]
        print(f"envelope_phase_run_owned={len(envelope_run_owned)} "
              f"(legacy run_owned={corpus['run_owned']} for comparison)")
    if args.contract_read_partition:
        crp_core = contract_read_partition(run_owned, ("handoff-format.md",))
        print(f"contract_read_partition_core: n={crp_core['n']} hits={crp_core['hits']} "
              f"fraction={crp_core['fraction']}")
        crp_reference = contract_read_partition(run_owned, ("handoff-format-reference.md",))
        print(f"contract_read_partition_reference: n={crp_reference['n']} "
              f"hits={crp_reference['hits']} fraction={crp_reference['fraction']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

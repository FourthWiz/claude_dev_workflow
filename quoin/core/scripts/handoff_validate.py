#!/usr/bin/env python3
"""handoff_validate.py — canonical validator for the inter-agent handoff envelope.

Validates a payload against the rules named quoin/core/workflow/handoff-format.md
(H-01..H-21). Portable core: stdlib-only, no imports from quoin/scripts/ (the
adapter layer) or from any third-party package.

Usage:
    handoff_validate.py [--direction dispatch|return] [--quiet] [--verbose] <payload-file>
    handoff_validate.py --self-test

Exit codes: 0 pass (no FATAL rule fired), 1 at least one FATAL rule fired,
2 invocation error (bad CLI usage, missing/unreadable file).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# ── Named module constants ────────────────────────────────────────────────

_MAX_VALUE_BYTES = 600
_MAX_ENVELOPE_BYTES = 1024
_SUPPORTED_MAJOR = 1
_SUPPORTED_MINORS = frozenset({0})

# Deliberate copy of context_bundle.py's SENTINEL_TOKENS (D-19): core cannot
# import the adapter-layer script, so the list is duplicated and a parity
# test (T-11) keeps both copies in lockstep. The envelope's own markers are
# included: a value quoting either marker literal is a sentinel-style token
# in its own right, so an embedded marker inside a field value is rejected
# by H-11 rather than silently accepted as prose.
_SENTINEL_TOKENS = (
    "[quoin-bundle]",
    "[/quoin-bundle]",
    "[autonomous]",
    "[no-redispatch]",
    "[no-redispatch:",  # counter form [no-redispatch:N]
    "[no-interactive]",
    "[quoin-onbehalf]",
    "[no-phase-budget]",
    "[no-session-age-guard]",
    "[quoin-handoff/",
    "[/quoin-handoff]",
)

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_BRACKET_GROUP = re.compile(r"\[([^\[\]]*)\]")

_OPEN_TOKEN_RE = re.compile(r"\[quoin-handoff/[^\]\n]*\]")
_OPEN_SHAPE_RE = re.compile(r"^\[quoin-handoff/(\d+)\.(\d+) (\S+)\]$")
_CLOSE_MARKER = "[/quoin-handoff]"
_ZONE_TOKEN_RE = re.compile(r"\[[^\]\n]*\]")  # no ^ anchor: .match(text, pos) already anchors at pos
_KEY_TOKEN_RE = re.compile(r"^([a-z_][a-z0-9_]*)(?:\[(\d+)\])?$")

_STATUS_ENUM = ("COMPLETE", "PARTIAL", "NEEDS-DECISION", "BLOCKED")
_VERDICT_ENUM = ("PASS", "REVISE", "APPROVED", "CHANGES_REQUESTED", "BLOCKED")

_DISPATCH_REQUIRED = ("skill", "task", "task_dir", "project_root", "return")
_DISPATCH_ORDER = (
    "skill", "task", "task_dir", "project_root", "profile", "inputs",
    "return", "spec", "bundle",
)
_DISPATCH_KNOWN = frozenset(_DISPATCH_ORDER)
_DISPATCH_LIST_KEYS = frozenset({"inputs"})

_RETURN_ORDER = (
    "status", "artifact", "verdict", "summary", "checkpoint", "phase",
    "reason", "remaining", "resume_hint", "artifacts",
)
_RETURN_KNOWN = frozenset(_RETURN_ORDER)
_RETURN_LIST_KEYS: frozenset = frozenset()

# D-30: required-field set per return status. NEEDS-DECISION additionally
# requires at least one of checkpoint/artifact, handled as a special case.
_STATUS_REQUIRED = {
    "COMPLETE": frozenset({"status", "artifact", "verdict", "summary"}),
    "PARTIAL": frozenset({"status", "checkpoint", "phase", "remaining", "resume_hint"}),
    "NEEDS-DECISION": frozenset({"status", "phase", "reason", "resume_hint"}),
    "BLOCKED": frozenset({"status", "phase", "reason", "resume_hint"}),
}


# ── Sentinel zone / marker location (D-22) ──────────────────────────────────


def _sentinel_zone_end(text: str) -> int:
    """Maximal leading run of whitespace + whitespace-separated bracket tokens,
    computed without reference to the [quoin-handoff/...] marker."""
    pos = 0
    n = len(text)
    while pos < n:
        while pos < n and text[pos].isspace():
            pos += 1
        if pos >= n or text[pos] != "[":
            return pos
        m = _ZONE_TOKEN_RE.match(text, pos)
        if m is None:
            return pos
        token = m.group(0)
        if token.startswith("[quoin-handoff/"):
            return pos
        pos = m.end()
    return pos


def _locate_open_marker(text: str):
    """Return (start, end, major, minor, direction_kw) or None if absent/malformed."""
    m = _OPEN_TOKEN_RE.search(text)
    if m is None:
        return None
    shape = _OPEN_SHAPE_RE.fullmatch(m.group(0))
    if shape is None:
        return None
    return (m.start(), m.end(), int(shape.group(1)), int(shape.group(2)), shape.group(3))


def _find_close_marker(text: str, start: int) -> int:
    """Return the index of the first close marker that is structurally a
    marker line of its own — immediately preceded by the start of the text
    or a newline, and immediately followed by a newline or the end of the
    text. A close-marker-shaped substring elsewhere on a line (for example
    quoted inside a field value) is not a match, since it is not the
    envelope's own close marker; the search continues past it. Returns -1
    if no structural match exists."""
    pos = start
    n = len(text)
    marker_len = len(_CLOSE_MARKER)
    while True:
        idx = text.find(_CLOSE_MARKER, pos)
        if idx == -1:
            return -1
        line_start_ok = idx == 0 or text[idx - 1] == "\n"
        end = idx + marker_len
        line_end_ok = end == n or text[end] == "\n"
        if line_start_ok and line_end_ok:
            return idx
        pos = idx + 1


# ── Envelope body parsing ────────────────────────────────────────────────────


class _TabularBlock:
    __slots__ = ("base_key", "declared_count", "header_fields", "rows", "line_no")

    def __init__(self, base_key, declared_count, header_fields, line_no):
        self.base_key = base_key
        self.declared_count = declared_count
        self.header_fields = header_fields
        self.rows: list[list[str]] = []
        self.line_no = line_no


def _parse_body(body_lines: list[str]):
    """Parse envelope body lines into a structured record.

    Returns a dict with:
      fields: ordered list of (base_key, value, line_no, is_tabular_header)
      first_seen: dict base_key -> line_no of first occurrence
      duplicates: set of base_keys seen more than once
      tabular_blocks: list of _TabularBlock
      shape_violations: list of line_no for lines that are neither a valid
        key:value line, nor a tabular row of a currently open block, nor
        (implicitly) blank — H-20 material.
      blank_lines: list of line_no that are blank inside the envelope — H-20.
    """
    fields = []
    first_seen: dict[str, int] = {}
    duplicates: set[str] = set()
    tabular_blocks: list[_TabularBlock] = []
    shape_violations: list[int] = []
    blank_lines: list[int] = []

    current_block: _TabularBlock | None = None

    for idx, line in enumerate(body_lines):
        line_no = idx + 1
        if line.strip() == "":
            blank_lines.append(line_no)
            current_block = None
            continue
        if line[0] == " " or line[0] == "\t":
            if current_block is not None:
                row_fields = [f.strip() for f in line.strip().split(" | ")]
                current_block.rows.append(row_fields)
                continue
            shape_violations.append(line_no)
            continue
        # column-0 candidate
        if ": " in line:
            key_part, value_part = line.split(": ", 1)
        elif line.endswith(":"):
            key_part, value_part = line[:-1], ""
        else:
            shape_violations.append(line_no)
            current_block = None
            continue
        m = _KEY_TOKEN_RE.fullmatch(key_part)
        if m is None:
            shape_violations.append(line_no)
            current_block = None
            continue
        base_key = m.group(1)
        bracket_count = m.group(2)
        if base_key not in first_seen:
            first_seen[base_key] = line_no
        else:
            duplicates.add(base_key)
        if bracket_count is not None:
            declared = int(bracket_count)
            header_fields = [f.strip() for f in value_part.split(" | ")]
            block = _TabularBlock(base_key, declared, header_fields, line_no)
            tabular_blocks.append(block)
            fields.append((base_key, value_part, line_no, True))
            current_block = block
        else:
            fields.append((base_key, value_part, line_no, False))
            current_block = None

    return {
        "fields": fields,
        "first_seen": first_seen,
        "duplicates": duplicates,
        "tabular_blocks": tabular_blocks,
        "shape_violations": shape_violations,
        "blank_lines": blank_lines,
    }


def _utf8_len(s: str) -> int:
    return len(s.encode("utf-8"))


def _contains_sentinel_token(value: str) -> bool:
    probe = _BRACKET_GROUP.sub(
        lambda m: "[" + re.sub(r"\s+", "", m.group(1)) + "]", value.lower()
    )
    return any(tok in probe for tok in _SENTINEL_TOKENS)


def _is_subsequence(seq: list[str], order: tuple[str, ...]) -> bool:
    idx = 0
    for item in seq:
        try:
            idx = order.index(item, idx) + 1
        except ValueError:
            return False
    return True


# ── Rule checks (one function per checkable ID) ─────────────────────────────


def check_h_13(text: str, marker_start: int, messages: list[str]) -> None:
    zone_end = _sentinel_zone_end(text)
    between = text[zone_end:marker_start]
    starts_line = marker_start == 0 or text[marker_start - 1] == "\n"
    if between.strip() != "" or not starts_line:
        messages.append(
            "FAIL H-13: envelope placement violates the sentinel-zone rule "
            "(prose before the open marker, or the marker does not start its own line)"
        )


def check_h_02_h_03(major: int, minor: int, messages: list[str]) -> bool:
    """Returns True if evaluation must STOP (unrecognised major)."""
    if major != _SUPPORTED_MAJOR:
        messages.append(
            f"WARN H-02: unrecognised major version {major}; envelope ignored"
        )
        return True
    if minor not in _SUPPORTED_MINORS:
        messages.append(f"WARN H-03: unrecognised minor version {minor}; processing continues")
    return False


def check_h_04(direction_kw: str, messages: list[str]) -> bool:
    """Returns True if direction keyword is valid (dispatch/return)."""
    if direction_kw not in ("dispatch", "return"):
        messages.append(
            f"FAIL H-04: marker direction keyword {direction_kw!r} is neither "
            "'dispatch' nor 'return'"
        )
        return False
    return True


def check_h_18(direction_kw: str, direction_arg: str | None, messages: list[str]) -> None:
    if direction_arg is not None and direction_arg != direction_kw:
        messages.append(
            f"FAIL H-18: --direction {direction_arg!r} disagrees with the marker's "
            f"own direction keyword {direction_kw!r}"
        )


def check_h_20(parsed: dict, messages: list[str]) -> None:
    for _ in parsed["blank_lines"]:
        messages.append("FAIL H-20: blank line inside the envelope is not permitted")
        return
    for _ in parsed["shape_violations"]:
        messages.append(
            "FAIL H-20: a line strictly between the markers is neither a "
            "column-0 key: value line nor an indented tabular row"
        )
        return


def check_h_12(parsed: dict, messages: list[str]) -> None:
    for key in sorted(parsed["duplicates"]):
        messages.append(f"WARN H-12: duplicate key {key!r}; first occurrence wins")


def check_h_15(parsed: dict, messages: list[str]) -> None:
    for block in parsed["tabular_blocks"]:
        header_count = len(block.header_fields)
        for row in block.rows:
            if len(row) != header_count:
                messages.append(
                    f"FAIL H-15: tabular block {block.base_key!r} row has "
                    f"{len(row)} fields, header declares {header_count}"
                )
                return


def check_h_19(parsed: dict, messages: list[str]) -> None:
    for block in parsed["tabular_blocks"]:
        if block.declared_count != len(block.rows):
            messages.append(
                f"FAIL H-19: tabular block {block.base_key!r} declares "
                f"[{block.declared_count}] but has {len(block.rows)} row(s)"
            )
            return


def check_h_17(parsed: dict, known_list_keys: frozenset, messages: list[str]) -> None:
    # A literal occurrence of the one-way escape sequence can never legitimately
    # appear in source text, regardless of value shape.
    for base_key, value, _line_no, is_header in parsed["fields"]:
        if not is_header and " ¦ " in value:
            messages.append(f"WARN H-17: value for {base_key!r} contains the literal escape sequence")
            return
    for block in parsed["tabular_blocks"]:
        for row in block.rows:
            for field in row:
                if " ¦ " in field:
                    messages.append(
                        f"WARN H-17: tabular block {block.base_key!r} row field contains "
                        "the literal escape sequence"
                    )
                    return
    # Unescaped list delimiter inside a non-list scalar value (MIN-9 pre-flight
    # amendment): tabular headers/rows are the structural separator, out of scope.
    for base_key, value, _line_no, is_header in parsed["fields"]:
        if is_header:
            continue
        if base_key in known_list_keys:
            continue
        if " | " in value:
            messages.append(
                f"WARN H-17: unescaped list delimiter inside scalar value for {base_key!r}"
            )
            return


def check_h_08_h_10_h_11(parsed: dict, messages: list[str]) -> None:
    """H-08 value byte bound, H-10 control characters, H-11 sentinel-in-value.
    Value-scoped rules read each tabular row FIELD as a value (MIN-5)."""
    values: list[tuple[str, str]] = []
    for base_key, value, _line_no, is_header in parsed["fields"]:
        if not is_header:
            values.append((base_key, value))
    for block in parsed["tabular_blocks"]:
        for row in block.rows:
            for field in row:
                values.append((f"{block.base_key}[row]", field))

    for label, value in values:
        if _utf8_len(value) > _MAX_VALUE_BYTES:
            messages.append(f"FAIL H-08: value for {label!r} exceeds {_MAX_VALUE_BYTES} bytes")
            return
    for label, value in values:
        if _CONTROL_CHARS.search(value):
            messages.append(f"FAIL H-10: value for {label!r} contains a control character")
            return
    for label, value in values:
        if _contains_sentinel_token(value):
            messages.append(f"FAIL H-11: value for {label!r} contains a sentinel-style bracket token")
            return


def check_h_09(text: str, envelope_start: int, envelope_end: int, messages: list[str]) -> None:
    span = text[envelope_start:envelope_end]
    if _utf8_len(span) > _MAX_ENVELOPE_BYTES:
        messages.append(f"FAIL H-09: envelope span exceeds {_MAX_ENVELOPE_BYTES} bytes")


def _direction_tables(direction_kw: str):
    if direction_kw == "dispatch":
        return _DISPATCH_ORDER, _DISPATCH_KNOWN, _DISPATCH_LIST_KEYS
    return _RETURN_ORDER, _RETURN_KNOWN, _RETURN_LIST_KEYS


def check_h_14(parsed: dict, known: frozenset, messages: list[str]) -> None:
    for base_key in parsed["first_seen"]:
        if base_key not in known:
            messages.append(f"WARN H-14: unknown key {base_key!r} ignored")
            return


def check_h_16(parsed: dict, order: tuple[str, ...], messages: list[str]) -> None:
    recognised = [k for k in order if k in parsed["first_seen"]]
    recognised.sort(key=lambda k: parsed["first_seen"][k])
    if not _is_subsequence(recognised, order):
        messages.append("FAIL H-16: recognised fields are not in canonical field order")


def check_h_06_h_07(direction_kw: str, parsed: dict, messages: list[str]) -> bool:
    """Returns True if status is present-and-valid (or n/a for dispatch)."""
    status_ok = True
    if direction_kw == "return" and "status" in parsed["first_seen"]:
        status_value = _field_value(parsed, "status")
        if status_value not in _STATUS_ENUM:
            messages.append(f"FAIL H-06: status {status_value!r} is not a recognised status")
            status_ok = False
    if "verdict" in parsed["first_seen"]:
        verdict_value = _field_value(parsed, "verdict")
        if verdict_value not in _VERDICT_ENUM:
            messages.append(f"FAIL H-07: verdict {verdict_value!r} is not a recognised verdict")
    return status_ok


def _field_value(parsed: dict, base_key: str) -> str | None:
    for k, value, line_no, is_header in parsed["fields"]:
        if k == base_key and line_no == parsed["first_seen"].get(base_key):
            return value
    return None


def check_h_05(direction_kw: str, parsed: dict, status_ok: bool, messages: list[str]) -> None:
    present = set(parsed["first_seen"].keys())
    if direction_kw == "dispatch":
        missing = [k for k in _DISPATCH_REQUIRED if k not in present]
        if missing:
            messages.append(f"FAIL H-05: dispatch payload missing required field(s): {missing}")
        return

    # return direction
    if "status" not in present:
        messages.append("FAIL H-05: return payload missing required field: status")
        return
    if not status_ok:
        # H-06 already fired; H-05 degrades to the direction-level set, which
        # is satisfied because status IS present.
        return
    status_value = _field_value(parsed, "status")
    required = _STATUS_REQUIRED.get(status_value)
    if required is None:
        return
    missing = [k for k in _RETURN_ORDER if k in required and k not in present]
    if status_value == "NEEDS-DECISION" and not ({"checkpoint", "artifact"} & present):
        missing.append("checkpoint-or-artifact")
    if missing:
        messages.append(
            f"FAIL H-05: return payload with status {status_value!r} missing "
            f"required field(s): {missing}"
        )


# ── Top-level validate() ─────────────────────────────────────────────────────


def validate(text: str, direction_arg: str | None) -> list[str]:
    messages: list[str] = []

    located = _locate_open_marker(text)
    if located is None:
        messages.append("FAIL H-01: no [quoin-handoff/...] open marker found in payload")
        return messages

    marker_start, marker_end, major, minor, direction_kw = located
    close_idx = _find_close_marker(text, marker_end)
    has_close = close_idx != -1

    if not has_close:
        messages.append("FAIL H-01: open marker has no matching [/quoin-handoff] close marker")
        if check_h_02_h_03(major, minor, messages):
            return messages
        direction_valid = check_h_04(direction_kw, messages)
        check_h_13(text, marker_start, messages)
        if direction_valid:
            check_h_18(direction_kw, direction_arg, messages)
        return messages

    if check_h_02_h_03(major, minor, messages):
        return messages

    check_h_13(text, marker_start, messages)

    envelope_start = marker_end
    if envelope_start < len(text) and text[envelope_start] == "\n":
        envelope_start += 1
    envelope_end = close_idx
    body_text = text[envelope_start:envelope_end]
    if body_text.endswith("\n"):
        body_text = body_text[:-1]
    body_lines = body_text.split("\n") if body_text else []

    parsed = _parse_body(body_lines)

    check_h_09(text, marker_end, envelope_end, messages)
    check_h_12(parsed, messages)
    check_h_15(parsed, messages)
    check_h_19(parsed, messages)
    check_h_20(parsed, messages)
    check_h_08_h_10_h_11(parsed, messages)

    direction_valid = check_h_04(direction_kw, messages)
    if direction_valid:
        check_h_18(direction_kw, direction_arg, messages)

    if direction_valid:
        order, known, list_keys = _direction_tables(direction_kw)
        check_h_14(parsed, known, messages)
        check_h_16(parsed, order, messages)
        status_ok = check_h_06_h_07(direction_kw, parsed, messages)
        check_h_05(direction_kw, parsed, status_ok, messages)
        check_h_17(parsed, list_keys, messages)
    else:
        # Direction-independent rules still run; no list-valued key is known,
        # so H-17's scalar/list partition falls back to "everything scalar".
        check_h_17(parsed, frozenset(), messages)

    return messages


# ── Embedded self-test fixtures (D-24 — never a file on disk) ───────────────

_SELF_TEST_DISPATCH = """[no-redispatch] [autonomous] [quoin-onbehalf]
[quoin-handoff/1.0 dispatch]
skill: architect
task: agent-handoff-format
task_dir: .workflow_artifacts/agent-handoff-format/
project_root: /abs/path/to/project
profile: Large
inputs: spec.md | enriched-prompt.md | memory/repos-inventory.md
return: envelope
spec: __QUOIN_HOME__/core/workflow/handoff-format.md
[/quoin-handoff]
<task-specific prose, unchanged>
"""

_SELF_TEST_RETURN = """[quoin-handoff/1.0 return]
status: COMPLETE
artifact: /abs/path/architecture.md
verdict: PASS
summary: architecture produced, all stages decomposed
[/quoin-handoff]
<no further prose>
"""


def _run_self_test(verbose: bool) -> int:
    ok = True
    for label, fixture, direction in (
        ("dispatch", _SELF_TEST_DISPATCH, "dispatch"),
        ("return", _SELF_TEST_RETURN, "return"),
    ):
        messages = validate(fixture, direction)
        if messages:
            ok = False
            print(f"SELF-TEST FAIL: {label}", file=sys.stderr)
            for m in messages:
                print(f"- {m}", file=sys.stderr)
        elif verbose:
            print(f"SELF-TEST PASS: {label}")
    if ok:
        print("PASS: --self-test (2 embedded fixtures)")
        return 0
    return 1


# ── CLI ──────────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("payload_file", nargs="?", help="Payload file to validate.")
    parser.add_argument(
        "--direction",
        choices=["dispatch", "return"],
        default=None,
        help="Optional assertion; disagreement with the marker's own direction is FATAL (H-18).",
    )
    parser.add_argument("--quiet", action="store_true", help="Suppress the PASS confirmation line.")
    parser.add_argument("--verbose", action="store_true", help="Emit per-fixture self-test detail.")
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Validate the two embedded conforming fixtures and exit.",
    )
    args = parser.parse_args()

    if args.self_test:
        return _run_self_test(args.verbose)

    if not args.payload_file:
        parser.error("payload file is required unless --self-test is used")

    path = Path(args.payload_file)
    if not path.is_file():
        print(f"handoff_validate: file not found: {path}", file=sys.stderr)
        return 2
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"handoff_validate: cannot read file: {exc}", file=sys.stderr)
        return 2

    messages = validate(text, args.direction)
    for m in messages:
        print(m, file=sys.stderr)
    if any(m.startswith("FAIL") for m in messages):
        return 1
    if not args.quiet:
        print(f"PASS: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

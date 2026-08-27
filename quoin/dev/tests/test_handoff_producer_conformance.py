"""
Black-box pytest tests for the run skill's handoff-envelope producer
prose (T-09, FR-10, AC-07).

FR-10 requires the validator be driven from REAL emitted payload values
rather than synthetic hand-constructed pairs. The producer here is
instruction text in adapter skill files, not executable code, so "real
emitted values" means the literal fenced blocks those files instruct the
orchestrator to emit. This file extracts those blocks and runs them
through the same core validator subprocess idiom test_handoff_validate.py
uses — no import of validator internals.

Mirrors test_handoff_validate.py's two-part pass condition throughout:
rc == 0 AND the filtered (blank-line-dropped) stderr line list is empty.
Exit 0 alone admits every advisory-severity rule, which is exactly where
version and key drift surface.
"""

import os
import re
import subprocess
import sys
import tempfile

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
DEV_DIR = os.path.dirname(TEST_DIR)                # quoin/dev/
QUOIN_DIR = os.path.dirname(DEV_DIR)                # quoin/
PROJECT_ROOT = os.path.dirname(QUOIN_DIR)           # project root

VALIDATOR = os.path.join(QUOIN_DIR, "core", "scripts", "handoff_validate.py")

RUN_SKILL = os.path.join(
    QUOIN_DIR, "adapters", "claude", "skills", "run", "SKILL.md"
)
# The three summary-mandating skills — at this commit they carry no
# literal handoff blocks of their own (T-07 lands later), so the
# extractor is expected to find zero blocks in each; they are scanned
# anyway so a future block landing in one of them is picked up for free.
SUMMARY_MANDATING_SKILLS = [
    os.path.join(QUOIN_DIR, "adapters", "claude", "skills", "implement", "SKILL.md"),
    os.path.join(QUOIN_DIR, "adapters", "claude", "skills", "review", "SKILL.md"),
    os.path.join(QUOIN_DIR, "adapters", "claude", "skills", "thorough_plan", "SKILL.md"),
]
PRODUCER_FILES = [RUN_SKILL] + SUMMARY_MANDATING_SKILLS

FENCE_RE = re.compile(r"```text\n(.*?)\n```", re.DOTALL)
MARKER_RE = re.compile(r"^\[quoin-handoff/\d+\.\d+ (dispatch|return)\]$")
STATUS_RE = re.compile(r"^status:\s*(\S+)\s*$", re.MULTILINE)


def run_validator(payload_text, direction):
    """Write payload_text to a temp file and run the core validator against it."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False
    ) as fh:
        fh.write(payload_text)
        path = fh.name
    try:
        cmd = [sys.executable, VALIDATOR, "--direction", direction, path]
        result = subprocess.run(cmd, capture_output=True, cwd=PROJECT_ROOT)
    finally:
        os.unlink(path)
    stderr = result.stderr.decode("utf-8", errors="replace")
    lines = [ln for ln in stderr.splitlines() if ln.strip()]
    return result.returncode, lines


def extract_blocks(path):
    """Return a list of (direction, block_text) for every marker-first fenced
    block in the file at path. block_text spans open marker through close
    marker inclusive — the first-line rule is what T-03's marker-first
    template shape exists to satisfy (D-14)."""
    with open(path, encoding="utf-8") as fh:
        content = fh.read()
    found = []
    for m in FENCE_RE.finditer(content):
        block = m.group(1)
        first_line = block.splitlines()[0] if block else ""
        marker_match = MARKER_RE.match(first_line)
        if marker_match:
            found.append((marker_match.group(1), block))
    return found


def all_producer_blocks():
    blocks = []
    for path in PRODUCER_FILES:
        blocks.extend(extract_blocks(path))
    return blocks


# ── Set-guards (a), (b), (c) — a zero-block sweep must FAIL loudly ─────────


def test_at_least_one_dispatch_and_one_return_block_found():
    blocks = all_producer_blocks()
    directions = {d for d, _ in blocks}
    assert "dispatch" in directions, "no dispatch block found across the producer file set"
    assert "return" in directions, "no return block found across the producer file set"


def test_return_blocks_cover_complete_and_partial_status():
    blocks = all_producer_blocks()
    statuses = set()
    for direction, block in blocks:
        if direction != "return":
            continue
        m = STATUS_RE.search(block)
        if m:
            statuses.add(m.group(1))
    assert "COMPLETE" in statuses
    assert "PARTIAL" in statuses


def test_dispatch_block_carries_return_envelope_field():
    blocks = all_producer_blocks()
    dispatch_blocks = [block for direction, block in blocks if direction == "dispatch"]
    assert dispatch_blocks, "no dispatch block found"
    assert any("return: envelope" in block for block in dispatch_blocks)


# ── Per-block validation — every extracted block validates clean ──────────


def test_every_extracted_block_validates_clean():
    blocks = all_producer_blocks()
    assert blocks, "producer file set yielded zero blocks"
    for direction, block in blocks:
        rc, lines = run_validator(block, direction)
        assert rc == 0, f"{direction} block failed validation: {lines}"
        assert lines == [], f"{direction} block warned: {lines}"


# ── Composed-payload case — AC-07 and the bundle-coexistence mechanism ────


def test_review_spawn_composed_payload_validates():
    """Build the review spawn's payload exactly as the skill instructs:
    a stacked sentinel line, then the dispatch block extracted from the
    run skill verbatim, then a prose line, then a wrapped bundle block
    with both bundle markers on their own lines. The whole payload must
    validate clean as a dispatch — this discharges the placement rule,
    the sentinel-stacking half of AC-07, and the bundle/envelope
    coexistence line all at once."""
    dispatch_blocks = [
        block for direction, block in extract_blocks(RUN_SKILL) if direction == "dispatch"
    ]
    assert dispatch_blocks, "run skill carries no dispatch block to compose with"
    dispatch_block = dispatch_blocks[0]

    payload = (
        "[no-redispatch] [autonomous]\n"
        + dispatch_block
        + "\n"
        + "Review the implementation against the converged plan.\n"
        + "[quoin-bundle]\n"
        + "path/to/current-plan.md | plan summary\n"
        + "[/quoin-bundle]\n"
    )

    rc, lines = run_validator(payload, "dispatch")
    assert rc == 0, f"composed payload failed validation: {lines}"
    assert lines == [], f"composed payload warned: {lines}"


def test_composed_payload_reds_on_prose_between_sentinel_and_marker():
    """Mutation-proof: inserting a prose line between the sentinel zone and
    the open marker must trip the placement rule (H-13), proving the
    composed case above is load-bearing rather than decorative."""
    dispatch_blocks = [
        block for direction, block in extract_blocks(RUN_SKILL) if direction == "dispatch"
    ]
    assert dispatch_blocks
    dispatch_block = dispatch_blocks[0]

    payload = (
        "[no-redispatch] [autonomous]\n"
        + "This prose line does not belong here.\n"
        + dispatch_block
        + "\n"
    )

    rc, lines = run_validator(payload, "dispatch")
    assert rc == 1
    assert any("H-13" in ln for ln in lines)

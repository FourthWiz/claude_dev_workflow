"""
Sentinel-token parity test across the core/adapter boundary (T-11, R-09).

quoin/core/scripts/handoff_validate.py is portable core: it cannot import
quoin/scripts/context_bundle.py (adapter-layer, no core twin), so its
_SENTINEL_TOKENS tuple is a deliberate literal copy of context_bundle.py's
SENTINEL_TOKENS (D-19). This test reads both files as TEXT — it never
imports either — and set-equates the two literal tuples, so the two copies
are forced to move together the moment either one changes.

Run: pytest quoin/dev/tests/test_handoff_sentinel_parity.py -v
"""

import os
import re

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
DEV_DIR = os.path.dirname(TEST_DIR)          # quoin/dev/
QUOIN_DIR = os.path.dirname(DEV_DIR)         # quoin/

BUNDLE_FILE = os.path.join(QUOIN_DIR, "scripts", "context_bundle.py")
VALIDATOR_FILE = os.path.join(QUOIN_DIR, "core", "scripts", "handoff_validate.py")

_STRING_LITERAL_RE = re.compile(r'"((?:[^"\\]|\\.)*)"')


def _extract_token_tuple(text, assign_name):
    """Extract the string-literal contents of a `NAME = (...)` tuple
    assignment, read as text only. Locates the assignment by name, then
    balances parentheses to find the tuple's closing `)` (comments and
    values after `#` are naturally excluded since only quoted strings are
    collected)."""
    marker = f"{assign_name} = ("
    start = text.index(marker)
    depth = 0
    pos = start + len(marker) - 1  # position of the opening "("
    end = None
    for i in range(pos, len(text)):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                end = i
                break
    assert end is not None, f"unbalanced parens for {assign_name} in text"
    block = text[pos:end]
    return tuple(_STRING_LITERAL_RE.findall(block))


def test_sentinel_token_literal_parity():
    bundle_text = open(BUNDLE_FILE, encoding="utf-8").read()
    validator_text = open(VALIDATOR_FILE, encoding="utf-8").read()

    bundle_tokens = _extract_token_tuple(bundle_text, "SENTINEL_TOKENS")
    validator_tokens = _extract_token_tuple(validator_text, "_SENTINEL_TOKENS")

    assert set(bundle_tokens) == set(validator_tokens), (
        f"sentinel-token literal drift — "
        f"only in context_bundle.py: {set(bundle_tokens) - set(validator_tokens)}, "
        f"only in handoff_validate.py: {set(validator_tokens) - set(bundle_tokens)}"
    )
    assert len(bundle_tokens) == 11, f"expected eleven entries in context_bundle.py, got {len(bundle_tokens)}"
    assert len(validator_tokens) == 11, f"expected eleven entries in handoff_validate.py, got {len(validator_tokens)}"


def test_sentinel_token_parity_mutation_sensitive():
    """Proves the equality check above is load-bearing rather than vacuous:
    mutating one copy's extracted set must fail the same comparison."""
    bundle_text = open(BUNDLE_FILE, encoding="utf-8").read()
    bundle_tokens = set(_extract_token_tuple(bundle_text, "SENTINEL_TOKENS"))
    mutated = bundle_tokens | {"[not-a-real-sentinel]"}
    assert mutated != bundle_tokens

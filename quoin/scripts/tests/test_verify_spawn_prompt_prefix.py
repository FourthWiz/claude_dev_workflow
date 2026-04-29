"""
Unit tests for verify_spawn_prompt_prefix.py — T-01 acceptance tests.

Three core deterministic tests using monkey-patched Agent dispatch:
  (a) Child returns matching SHA and matching range → script exits 0 with verdict PASS
  (b) Child returns mismatched SHA → script exits 1 with verdict FAIL
  (c) Agent dispatch raises a known harness error → script exits 2 with verdict HARNESS-UNAVAILABLE

Tests mock the spawn_agent_fn callable — do NOT actually spawn anything.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest

# Add parent to path so we can import the script directly.
sys.path.insert(0, str(Path(__file__).parent.parent))

import verify_spawn_prompt_prefix as vspp


def _honest_child(model: str, description: str, prompt: str) -> str:
    """Simulate an honest child that correctly reports SHA256/LINE1/BYTES on received prompt."""
    prompt_bytes = prompt.encode("utf-8")
    sha256 = hashlib.sha256(prompt_bytes[:5000]).hexdigest()
    line1 = prompt.splitlines()[0] if prompt else ""
    bytes_100_200 = prompt_bytes[100:200].decode("utf-8", errors="replace")
    return f"SHA256={sha256}\nLINE1={line1}\nBYTES100TO200={bytes_100_200}\n"


def _sha_mismatch_child(model: str, description: str, prompt: str) -> str:
    """Simulate a child that returns a wrong SHA (all other fields correct)."""
    honest = _honest_child(model=model, description=description, prompt=prompt)
    bad_hash = "0" * 64
    lines = []
    for line in honest.splitlines():
        if line.startswith("SHA256="):
            lines.append(f"SHA256={bad_hash}")
        else:
            lines.append(line)
    return "\n".join(lines) + "\n"


def _error_child(model: str, description: str, prompt: str) -> str:
    """Simulate a harness that raises (Agent dispatch unavailable)."""
    raise RuntimeError("Agent tool not available in this context")


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestVerifySpawnPromptPrefix:
    """T-01 unit tests — all deterministic, no live Agent spawns."""

    def test_pass_both_variants_match(self):
        """(a) Honest child returns matching SHA/line1/bytes → PASS (exit 0)."""
        verdict, sidecar = vspp.run(spawn_agent_fn=_honest_child)

        assert verdict == "PASS", f"Expected PASS, got {verdict}. Sidecar: {sidecar}"
        assert sidecar["harness_error"] is None

        for variant_key in ("variant_a", "variant_b"):
            v = sidecar[variant_key]
            assert v["sha_match"] is True, f"{variant_key} sha_match should be True"
            assert v["line1_match"] is True, f"{variant_key} line1_match should be True"
            assert v["byte_range_match"] is True, f"{variant_key} byte_range_match should be True"
            assert v["child_sha"] == v["parent_sha"], f"{variant_key} sha values differ"

    def test_fail_on_sha_mismatch(self):
        """(b) Child returns mismatched SHA → FAIL (exit 1)."""
        verdict, sidecar = vspp.run(spawn_agent_fn=_sha_mismatch_child)

        assert verdict == "FAIL", f"Expected FAIL, got {verdict}. Sidecar: {sidecar}"
        assert sidecar["harness_error"] is None

        # At least one variant must report sha_match=False.
        any_sha_mismatch = (
            not sidecar["variant_a"]["sha_match"]
            or not sidecar["variant_b"]["sha_match"]
        )
        assert any_sha_mismatch, "Expected at least one sha_match=False"

    def test_harness_unavailable_on_dispatch_error(self):
        """(c) Agent dispatch raises → HARNESS-UNAVAILABLE (exit 2)."""
        verdict, sidecar = vspp.run(spawn_agent_fn=_error_child)

        assert verdict == "HARNESS-UNAVAILABLE", (
            f"Expected HARNESS-UNAVAILABLE, got {verdict}. Sidecar: {sidecar}"
        )
        assert sidecar["harness_error"] is not None
        assert "Agent tool not available" in sidecar["harness_error"]

    def test_variant_a_has_random_hex_sentinel(self):
        """Variant A must use a random-hex sentinel (not the production '[preamble-inlined]')."""
        captured: list[tuple[str, str]] = []

        def capturing_child(model: str, description: str, prompt: str) -> str:
            captured.append((description, prompt))
            return _honest_child(model=model, description=description, prompt=prompt)

        verdict, _ = vspp.run(spawn_agent_fn=capturing_child)
        assert verdict == "PASS"

        # Two spawns: Variant A (index 0) and Variant B (index 1).
        assert len(captured) == 2
        prompt_a = captured[0][1]
        line1_a = prompt_a.splitlines()[0]
        # Variant A must contain the random-probe prefix form.
        assert line1_a.startswith("[preamble-inlined-probe:"), (
            f"Variant A line1 should start with '[preamble-inlined-probe:', got: {line1_a!r}"
        )
        # The hex suffix must be 64 chars (32 bytes in hex).
        assert line1_a.endswith("]"), f"Variant A line1 should end with ']', got: {line1_a!r}"
        hex_part = line1_a[len("[preamble-inlined-probe:"):-1]
        assert len(hex_part) == 64, f"Random hex should be 64 chars, got {len(hex_part)}"

    def test_variant_b_uses_production_sentinel(self):
        """Variant B must use exactly '[preamble-inlined]' (production form)."""
        captured: list[tuple[str, str]] = []

        def capturing_child(model: str, description: str, prompt: str) -> str:
            captured.append((description, prompt))
            return _honest_child(model=model, description=description, prompt=prompt)

        verdict, _ = vspp.run(spawn_agent_fn=capturing_child)
        assert verdict == "PASS"

        # Variant B is the second spawn.
        assert len(captured) == 2
        prompt_b = captured[1][1]
        line1_b = prompt_b.splitlines()[0]
        assert line1_b == "[preamble-inlined]", (
            f"Variant B line1 should be '[preamble-inlined]', got: {line1_b!r}"
        )

    def test_sentinel_body_length(self):
        """SENTINEL_BODY must be exactly 4096 bytes (UTF-8)."""
        assert len(vspp.SENTINEL_BODY.encode("utf-8")) == 4096

    def test_parent_sha256_correctness(self):
        """_parent_sha256 must match hashlib.sha256 on the first 5000 bytes."""
        sample = "hello world " * 500  # ~6000 chars
        expected = hashlib.sha256(sample.encode("utf-8")[:5000]).hexdigest()
        assert vspp._parent_sha256(sample) == expected

    def test_parent_byte_range_correctness(self):
        """_parent_byte_range must return the correct UTF-8 slice."""
        sample = "a" * 200
        result = vspp._parent_byte_range(sample, 100, 200)
        assert result == "a" * 100
        assert len(result) == 100

    def test_spawn_prompt_starts_with_sentinel(self):
        """The built spawn prompt must start with the sentinel line."""
        sentinel = "[preamble-inlined-probe:abcdef]"
        prompt = vspp._build_spawn_prompt(sentinel)
        assert prompt.startswith(f"{sentinel}\n"), (
            f"Prompt should start with sentinel+newline, got: {prompt[:60]!r}"
        )

    def test_no_spawn_fn_returns_harness_unavailable(self):
        """When _SPAWN_FN is None and no fn passed, should return HARNESS-UNAVAILABLE."""
        original = vspp._SPAWN_FN
        vspp._SPAWN_FN = None
        try:
            verdict, sidecar = vspp.run()
            assert verdict == "HARNESS-UNAVAILABLE"
            assert sidecar["harness_error"] is not None
        finally:
            vspp._SPAWN_FN = original

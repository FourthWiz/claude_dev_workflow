#!/usr/bin/env python3
"""
verify_spawn_prompt_prefix.py — T-01 harness round-trip verification.

Tests whether the Claude Code harness transmits spawn-prompt prefix bytes
byte-identical from parent to child agent. This is the HARD FORK POINT for
Stage 2 of pipeline-efficiency-improvements: if this test FAILs, the
preamble-inlined mechanism cannot ship.

Two probe variants are run in sequence; BOTH must PASS for an overall PASS:

  Variant A (random-suffix probe): spawn prompt starts with
    `[preamble-inlined-probe:<random-32-byte-hex>]\\n`
    followed by 4096 bytes of sentinel padding.
    Defends against memorized-content false positives.

  Variant B (production-literal probe): spawn prompt starts with
    `[preamble-inlined]\\n` (exactly 19 bytes including the newline)
    followed by the same 4096-byte sentinel padding.
    Defends against sentinel-specific harness behavior.

The spawn prompt for each variant is structured as:
  <sentinel-line>\\n<padding-4096-bytes>\\n\\n<child-instructions>

The child (model: haiku for cost) is instructed to:
  (a) print the SHA-256 of its received prompt's first 5000 bytes verbatim
  (b) print line 1 of its prompt verbatim
  (c) print bytes 100-200 of its prompt verbatim

The parent computes the same SHA-256 over the same first-5000-byte slice of
the prompt-as-sent and compares byte-for-byte against the child's report.

Exit codes:
  0 — PASS: all checks match for BOTH variants
  1 — FAIL: any mismatch in either variant
  2 — HARNESS-UNAVAILABLE: Agent dispatch unavailable or errored for either variant

Stdout: one verdict line PASS | FAIL | HARNESS-UNAVAILABLE, then a JSON sidecar.

Usage examples:
  python3 quoin/scripts/verify_spawn_prompt_prefix.py
  python3 quoin/scripts/verify_spawn_prompt_prefix.py --help

Decision rule:
  PASS  → T-01 fork point: PASS; proceed with Stage 2 production code.
  FAIL  → T-01 fork point: FAIL; Stage 2 reverts to alternate transport.
          Re-plan needed; do NOT ship preamble.md files.
  HARNESS-UNAVAILABLE → treat as FAIL for Stage 2 purposes.

Failure interpretation:
  If line1 matches but SHA does not:
    The harness is normalizing whitespace or content somewhere in the prompt
    body. See quoin/docs/spawn-bootstrap-audit-2026-04-28.md §Fork.
  If line1 does not match:
    The harness is re-ordering or stripping the prefix entirely.
  If bytes 100-200 mismatch:
    The harness is modifying prompt body content (not just the prefix).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import secrets
import sys
import textwrap
from typing import Any


# ── Sentinel body ─────────────────────────────────────────────────────────────
# Exactly 4096 bytes of deterministic padding (hex digits repeated).
_HEX_CHARS = "0123456789abcdef"
SENTINEL_BODY = (_HEX_CHARS * 256)[:4096]  # 4096 bytes, no randomness in body

# Child instructions embedded after the sentinel padding.
_CHILD_INSTRUCTIONS = textwrap.dedent("""\


    ===CHILD-INSTRUCTIONS-BEGIN===
    You are a byte-transparency test agent. Your ONLY job is to report
    information about the prompt you received, computed from the very first byte
    of this prompt (byte 0 is the start of the sentinel line above).

    Compute the following from YOUR ENTIRE RECEIVED PROMPT (starting from byte 0):

    Step 1 — SHA256: Compute SHA-256 of the first 5000 bytes of your prompt
    (UTF-8 encoded). Print EXACTLY this line:
      SHA256=<hex-digest>

    Step 2 — LINE1: Print the first line of your prompt verbatim (everything
    before the first newline character). Print EXACTLY this line:
      LINE1=<first line content>

    Step 3 — BYTES100TO200: Print bytes 100..199 (0-indexed, 100 bytes total)
    of your prompt (UTF-8 encoded), decoded back to string.
    Print EXACTLY this line:
      BYTES100TO200=<content>

    Output ONLY these three lines, nothing else. No explanation, no
    commentary, no markdown. Exactly three lines starting with SHA256=, LINE1=,
    BYTES100TO200= respectively.
    ===CHILD-INSTRUCTIONS-END===
""")


def _build_spawn_prompt(sentinel_line: str) -> str:
    """Compose the full spawn prompt for a probe variant.

    sentinel_line: e.g. '[preamble-inlined-probe:abc...]' (no trailing newline)

    Prompt structure:
      <sentinel-line>\\n<4096-byte padding>\\n<child instructions>
    """
    return f"{sentinel_line}\n{SENTINEL_BODY}{_CHILD_INSTRUCTIONS}"


def _parent_sha256(prompt: str, n: int = 5000) -> str:
    """Compute SHA-256 of the first n bytes of prompt (UTF-8 encoded)."""
    data = prompt.encode("utf-8")[:n]
    return hashlib.sha256(data).hexdigest()


def _parent_byte_range(prompt: str, start: int = 100, end: int = 200) -> str:
    """Return bytes start..end (exclusive) of the prompt as a UTF-8 string."""
    data = prompt.encode("utf-8")
    return data[start:end].decode("utf-8", errors="replace")


def _parse_child_output(output: str) -> dict[str, str | None]:
    """Parse child output into {sha256, line1, bytes100to200}."""
    result: dict[str, str | None] = {
        "sha256": None,
        "line1": None,
        "bytes100to200": None,
    }
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("SHA256="):
            result["sha256"] = line[len("SHA256="):]
        elif line.startswith("LINE1="):
            result["line1"] = line[len("LINE1="):]
        elif line.startswith("BYTES100TO200="):
            result["bytes100to200"] = line[len("BYTES100TO200="):]
    return result


def _run_variant(
    variant_name: str,
    sentinel_line: str,
    spawn_agent_fn: Any,
) -> dict[str, Any]:
    """Run one probe variant. Returns a result dict.

    spawn_agent_fn(model, description, prompt) -> str | raises
    """
    prompt = _build_spawn_prompt(sentinel_line)
    parent_sha = _parent_sha256(prompt)
    parent_line1 = sentinel_line  # line 1 is the sentinel line
    parent_bytes = _parent_byte_range(prompt)

    try:
        child_output = spawn_agent_fn(
            model="claude-haiku-4-5",
            description=f"Byte-transparency probe {variant_name}",
            prompt=prompt,
        )
    except Exception as exc:
        return {
            "harness_error": str(exc),
            "sha_match": False,
            "line1_match": False,
            "byte_range_match": False,
            "child_sha": None,
            "parent_sha": parent_sha,
            "child_line1": None,
            "parent_line1": parent_line1,
            "child_bytes": None,
            "parent_bytes": parent_bytes,
        }

    parsed = _parse_child_output(child_output)

    sha_match = parsed["sha256"] == parent_sha
    line1_match = parsed["line1"] == parent_line1
    byte_range_match = parsed["bytes100to200"] == parent_bytes

    return {
        "harness_error": None,
        "sha_match": sha_match,
        "line1_match": line1_match,
        "byte_range_match": byte_range_match,
        "child_sha": parsed["sha256"],
        "parent_sha": parent_sha,
        "child_line1": parsed["line1"],
        "parent_line1": parent_line1,
        "child_bytes": parsed["bytes100to200"],
        "parent_bytes": parent_bytes,
    }


def _make_spawn_fn() -> Any:
    """Return the real Agent spawn function, or raise if unavailable."""
    # Module-level override point — tests monkey-patch _SPAWN_FN.
    if _SPAWN_FN is not None:
        return _SPAWN_FN
    raise RuntimeError(
        "Agent dispatch unavailable: no spawn function configured. "
        "In the Claude Code harness, spawn is provided by the Agent tool. "
        "Outside the harness, set verify_spawn_prompt_prefix._SPAWN_FN before calling run()."
    )


# Module-level override point for tests (monkey-patching target).
_SPAWN_FN: Any = None


def run(spawn_agent_fn: Any = None) -> tuple[str, dict[str, Any]]:
    """Run both probe variants and return (verdict, sidecar).

    verdict: "PASS" | "FAIL" | "HARNESS-UNAVAILABLE"
    sidecar: JSON-serializable dict with per-variant results.

    spawn_agent_fn: optional override for the Agent spawn callable.
    """
    if spawn_agent_fn is None:
        try:
            spawn_agent_fn = _make_spawn_fn()
        except RuntimeError as exc:
            sidecar = {
                "variant_a": {
                    "sha_match": False, "line1_match": False,
                    "byte_range_match": False, "child_sha": None, "parent_sha": None,
                },
                "variant_b": {
                    "sha_match": False, "line1_match": False,
                    "byte_range_match": False, "child_sha": None, "parent_sha": None,
                },
                "harness_error": str(exc),
            }
            return "HARNESS-UNAVAILABLE", sidecar

    # Variant A: random-suffix probe
    random_hex = secrets.token_hex(32)
    sentinel_a = f"[preamble-inlined-probe:{random_hex}]"
    result_a = _run_variant("A", sentinel_a, spawn_agent_fn)

    if result_a.get("harness_error"):
        sidecar = {
            "variant_a": {
                "sha_match": False, "line1_match": False,
                "byte_range_match": False, "child_sha": None, "parent_sha": None,
            },
            "variant_b": {
                "sha_match": False, "line1_match": False,
                "byte_range_match": False, "child_sha": None, "parent_sha": None,
            },
            "harness_error": result_a["harness_error"],
        }
        return "HARNESS-UNAVAILABLE", sidecar

    # Variant B: production-literal probe
    sentinel_b = "[preamble-inlined]"
    result_b = _run_variant("B", sentinel_b, spawn_agent_fn)

    if result_b.get("harness_error"):
        sidecar = {
            "variant_a": {k: result_a[k] for k in ["sha_match", "line1_match", "byte_range_match", "child_sha", "parent_sha"]},
            "variant_b": {
                "sha_match": False, "line1_match": False,
                "byte_range_match": False, "child_sha": None, "parent_sha": None,
            },
            "harness_error": result_b["harness_error"],
        }
        return "HARNESS-UNAVAILABLE", sidecar

    sidecar = {
        "variant_a": {k: result_a[k] for k in ["sha_match", "line1_match", "byte_range_match", "child_sha", "parent_sha"]},
        "variant_b": {k: result_b[k] for k in ["sha_match", "line1_match", "byte_range_match", "child_sha", "parent_sha"]},
        "harness_error": None,
    }

    a_pass = result_a["sha_match"] and result_a["line1_match"] and result_a["byte_range_match"]
    b_pass = result_b["sha_match"] and result_b["line1_match"] and result_b["byte_range_match"]

    verdict = "PASS" if (a_pass and b_pass) else "FAIL"
    return verdict, sidecar


def main() -> int:
    parser = argparse.ArgumentParser(
        description="T-01 harness round-trip verification for Stage 2 preamble-inlined mechanism.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Exit codes:
              0 — PASS: all SHA/line1/byte-range checks match for BOTH variants
              1 — FAIL: any mismatch in either variant
              2 — HARNESS-UNAVAILABLE: Agent dispatch unavailable or errored

            Decision rule:
              PASS  → Proceed with Stage 2 production code (preamble-inlined mechanism).
              FAIL  → Stage 2 reverts to alternate transport. Re-plan needed.
              HARNESS-UNAVAILABLE → Treat as FAIL for Stage 2 purposes.

            Failure interpretation:
              If line1 matches but SHA does not:
                The harness is normalizing whitespace or content somewhere in
                the prompt body. See quoin/docs/spawn-bootstrap-audit-2026-04-28.md §Fork.
              If line1 does not match:
                The harness is re-ordering or stripping the prefix entirely.
              If bytes 100-200 mismatch:
                The harness is modifying prompt body content (not just the prefix).

            Alternate transport candidates (if FAIL):
              1. spawn-description field (metadata only; preamble hash, not bytes)
              2. parent-managed in-memory file cache (no spawn protocol change)
              3. on-disk shared-prefix file (child reads ~/.claude/skills/<skill>/preamble.md directly)
        """),
    )
    parser.parse_args()

    verdict, sidecar = run()
    print(verdict)
    print(json.dumps(sidecar, indent=2))

    if verdict == "PASS":
        return 0
    elif verdict == "HARNESS-UNAVAILABLE":
        return 2
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())

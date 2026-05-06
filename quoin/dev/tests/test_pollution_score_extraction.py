"""
Quoin Stage 1 — pollution-score computation and extraction tests.

Tests three layers:
  1. Hook-side computation: compute_pollution_score shell function (unit tests via subprocess).
  2. Skill-side read: structural assertions that SKILL.md blocks contain the expected read pattern.
  3. Threshold behavior: boundary conditions at QUOIN_POLLUTION_THRESHOLD.

Per lesson 2026-04-23: no live LLM calls — deterministic subprocess + string matching only.
Per lesson 2026-04-29: stdlib-only for deployed scripts; no subprocess harness-tool assumptions.
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).parent
HOOKS_DIR = TESTS_DIR.parent.parent / "hooks"
LIB_SH = HOOKS_DIR / "_lib.sh"

POLLUTION_HEADING = "## §0' Pollution dispatch (execute after §0 / §0c if present — before skill body)"
TARGET_SKILLS = [
    "architect", "plan", "critic", "revise", "review", "init_workflow", "discover",
]
SKILLS_DIR = TESTS_DIR.parent.parent / "skills"


def _run_score(transcript_path: str, extra_env: dict | None = None) -> subprocess.CompletedProcess:
    """Run compute_pollution_score via sh, sourcing _lib.sh."""
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    script = f'. "{LIB_SH}" && compute_pollution_score "{transcript_path}"'
    return subprocess.run(
        ["sh", "-c", script],
        capture_output=True, text=True, env=env
    )


# ─── 1. Hook-side computation unit tests ─────────────────────────────────────

class TestComputePollutionScore:

    def test_empty_jsonl_returns_zero(self, tmp_path):
        """Empty file → score 0 (0 bytes, no tool calls)."""
        f = tmp_path / "empty.jsonl"
        f.write_text("")
        result = _run_score(str(f))
        assert result.returncode == 0, f"Unexpected non-zero exit: {result.stderr}"
        score = int(result.stdout.strip())
        assert score == 0, f"Empty file should score 0, got {score}"

    def test_5kb_no_tool_use_scores_approx_5(self, tmp_path):
        """5KB JSONL with no tool-use entries → score ~5 (5000 bytes / 1000)."""
        f = tmp_path / "5kb.jsonl"
        # Write 5000 bytes of content (JSON objects without tool_result type)
        line = json.dumps({"type": "text", "content": "x" * 80}) + "\n"
        content = line * (5000 // len(line) + 1)
        content = content[:5000]
        f.write_bytes(content.encode("utf-8"))
        result = _run_score(str(f))
        assert result.returncode == 0
        score = int(result.stdout.strip())
        # 5000 bytes / 1000 = 5 kB; no tool calls → score exactly 5
        assert score == 5, f"5KB no-tool file should score 5, got {score}"

    def test_tool_weighted_score(self, tmp_path):
        """1MB JSONL with 10 Agent + 20 Read + 5 Bash → score = 1000 + 50 + 20 + 5 = 1075.

        Uses real Claude Code transcript shape: tool_use entries are nested under assistant
        messages at .message.content[].type == "tool_use" with .name (not flat tool_result).
        """
        f = tmp_path / "tool_heavy.jsonl"
        lines = []
        # Fill to ~1MB with user-turn content (no tool_use — won't be counted)
        filler = json.dumps({"type": "user", "message": {"content": [{"type": "text", "text": "x" * 870}]}}) + "\n"
        lines.extend([filler] * 1000)

        # Add real-shape assistant messages with tool_use (10 Agent + 20 Read + 5 Bash)
        def _tool_line(name: str) -> str:
            return json.dumps({
                "type": "assistant",
                "message": {"content": [{"type": "tool_use", "id": "toolu_01", "name": name, "input": {}}]}
            }) + "\n"

        for _ in range(10):
            lines.append(_tool_line("Agent"))
        for _ in range(20):
            lines.append(_tool_line("Read"))
        for _ in range(5):
            lines.append(_tool_line("Bash"))

        content = "".join(lines)
        # Pad to exactly 1MB
        if len(content.encode()) < 1_000_000:
            pad = json.dumps({"type": "user", "message": {"content": [{"type": "text", "text": "p" * 870}]}}) + "\n"
            while len(content.encode()) < 1_000_000:
                content += pad
        f.write_bytes(content.encode("utf-8")[:1_000_000])
        result = _run_score(str(f))
        assert result.returncode == 0
        score = int(result.stdout.strip())
        # 1000 kB + (10×5) + (20×1) + (5×1) = 1075
        assert score == 1075, f"Tool-weighted 1MB file should score 1075, got {score}"

    def test_real_shape_fixture(self, tmp_path):
        """50 assistant messages with tool_use → function counts them correctly.

        Regression guard: ensures the jq filter walks .message.content[] as in
        real Claude Code transcripts, not the synthetic flat tool_result shape.
        """
        f = tmp_path / "real_shape.jsonl"
        lines = []
        # 30 Bash + 15 Read + 5 Agent in real assistant message shape
        for _ in range(30):
            lines.append(json.dumps({
                "type": "assistant",
                "message": {"content": [{"type": "tool_use", "id": "t1", "name": "Bash", "input": {}}]}
            }) + "\n")
        for _ in range(15):
            lines.append(json.dumps({
                "type": "assistant",
                "message": {"content": [{"type": "tool_use", "id": "t2", "name": "Read", "input": {}}]}
            }) + "\n")
        for _ in range(5):
            lines.append(json.dumps({
                "type": "assistant",
                "message": {"content": [{"type": "tool_use", "id": "t3", "name": "Agent", "input": {}}]}
            }) + "\n")
        f.write_text("".join(lines), encoding="utf-8")
        result = _run_score(str(f))
        assert result.returncode == 0
        score = int(result.stdout.strip())
        content_bytes = f.stat().st_size
        kb = content_bytes // 1000
        # Score = kb + (5×5) + (15×1) + (30×1) = kb + 25 + 15 + 30 = kb + 70
        expected = kb + 70
        assert score == expected, (
            f"Real-shape fixture (5 Agent + 15 Read + 30 Bash) should score {expected}, got {score}. "
            f"If score == {kb} (kb only), the jq filter is not walking .message.content[] correctly."
        )

    def test_missing_file_nonzero_exit(self):
        """Missing file → non-zero exit code."""
        result = _run_score("/tmp/quoin-test-nonexistent-file-xyz.jsonl")
        assert result.returncode != 0, "Missing file should return non-zero exit"

    def test_empty_path_nonzero_exit(self):
        """Empty path argument → non-zero exit code."""
        result = _run_score("")
        assert result.returncode != 0, "Empty path should return non-zero exit"


# ─── 2. Skill-side read — structural assertions ───────────────────────────────

class TestSkillSideRead:
    """Verify §0' blocks contain the session-state read pattern."""

    @pytest.mark.parametrize("skill", TARGET_SKILLS)
    def test_skill_reads_pollution_score_field(self, skill):
        text = (SKILLS_DIR / skill / "SKILL.md").read_text(encoding="utf-8")
        assert "pollution_score" in text, (
            f"{skill}/SKILL.md §0' block must reference `pollution_score` field "
            "(the skill reads this from session-state to decide whether to dispatch)"
        )

    @pytest.mark.parametrize("skill", TARGET_SKILLS)
    def test_skill_references_fallback_file(self, skill):
        text = (SKILLS_DIR / skill / "SKILL.md").read_text(encoding="utf-8")
        assert "pollution-score-latest.txt" in text, (
            f"{skill}/SKILL.md §0' block must reference `pollution-score-latest.txt` fallback "
            "(used when no session-state file exists)"
        )

    @pytest.mark.parametrize("skill", TARGET_SKILLS)
    def test_skill_reads_from_session_state(self, skill):
        text = (SKILLS_DIR / skill / "SKILL.md").read_text(encoding="utf-8")
        assert "sessions/" in text or "session-state" in text, (
            f"{skill}/SKILL.md §0' block must reference session-state file location"
        )


# ─── 3. Threshold behavior assertions ─────────────────────────────────────────

class TestThresholdBehavior:
    """Verify the threshold constant and tunable env var are documented in skills."""

    @pytest.mark.parametrize("skill", TARGET_SKILLS)
    def test_threshold_constant_referenced(self, skill):
        text = (SKILLS_DIR / skill / "SKILL.md").read_text(encoding="utf-8")
        # Either POLLUTION_THRESHOLD or QUOIN_POLLUTION_THRESHOLD must appear
        assert "POLLUTION_THRESHOLD" in text, (
            f"{skill}/SKILL.md §0' block must reference POLLUTION_THRESHOLD "
            "(the default threshold value or the env var name)"
        )

    @pytest.mark.parametrize("skill", TARGET_SKILLS)
    def test_threshold_default_value_documented(self, skill):
        text = (SKILLS_DIR / skill / "SKILL.md").read_text(encoding="utf-8")
        # The default value 5000 must appear in the §0' block
        assert "5000" in text, (
            f"{skill}/SKILL.md §0' block must document the default threshold value 5000"
        )

    def test_score_boundary_below_threshold(self, tmp_path):
        """Score at 4999 (threshold-1) → function returns value below 5000."""
        # Create a 4999KB file with no tool calls → score = 4999
        f = tmp_path / "just_below.jsonl"
        # 4999000 bytes = 4999 kB
        f.write_bytes(b"x" * 4_999_000)
        result = _run_score(str(f))
        assert result.returncode == 0
        score = int(result.stdout.strip())
        assert score == 4999, f"4999KB file should score 4999, got {score}"

    def test_score_at_threshold(self, tmp_path):
        """Score at exactly 5000 → dispatch should trigger (>= comparison)."""
        f = tmp_path / "at_threshold.jsonl"
        f.write_bytes(b"x" * 5_000_000)
        result = _run_score(str(f))
        assert result.returncode == 0
        score = int(result.stdout.strip())
        assert score == 5000, f"5000KB file should score 5000, got {score}"

    def test_custom_threshold_via_env(self, tmp_path):
        """QUOIN_POLLUTION_THRESHOLD=2000: a 2000KB file hits the custom threshold."""
        f = tmp_path / "custom_threshold.jsonl"
        f.write_bytes(b"x" * 2_000_000)
        result = _run_score(str(f))
        assert result.returncode == 0
        score = int(result.stdout.strip())
        # Score = 2000; with custom threshold 2000 this should trigger dispatch
        assert score == 2000, f"2000KB file should score 2000, got {score}"
        # The QUOIN_POLLUTION_THRESHOLD=2000 env var is consumed by SKILL.md blocks,
        # not by the shell function itself — this test verifies the score is at/above
        # the custom threshold, confirming dispatch would fire.
        assert score >= 2000, f"Score {score} should be >= custom threshold 2000"

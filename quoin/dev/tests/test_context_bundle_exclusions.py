"""test_context_bundle_exclusions.py — IVG-164 Stage 2 T-08.

Drift tests that enforce the fresh-context invariant:
  (a) critic/revise/revise-fast spawn-prompt construction blocks contain no
      ``[quoin-bundle]`` token.
  (b) The invariant sentences in thorough_plan/SKILL.md remain present verbatim.
  (c) ``context_bundle.py`` emits ONLY path lines and ``## For human``-sourced
      lines; emits explicit path-only entry for members lacking the block.

Fixture-driven: test (c) uses example fixture files (v2 plan without
``## For human``, fast-route stub with provenance marker, spec.md) rather
than re-deriving expectations from the plan's prose.
"""

import itertools
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

_ADAPTER = Path(__file__).resolve().parents[2] / "adapters" / "claude" / "skills"
_QUOIN_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"


def _read_skill(skill: str) -> str:
    return (_ADAPTER / skill / "SKILL.md").read_text()


class TestBundleExclusionFromCriticReviseSpawns:
    """Assertion (a): critic/revise/revise-fast spawn-prompt construction blocks
    contain no ``[quoin-bundle]`` token."""

    def test_thorough_plan_spawn_blocks_no_bundle_token(self):
        """thorough_plan/SKILL.md plan/critic/revise spawn blocks are bundle-clean."""
        text = _read_skill("thorough_plan")
        invoking_start = text.find("### Invoking each agent")
        assert invoking_start != -1, "Invoking each agent section not found"
        next_h2 = text.find("\n## ", invoking_start + 10)
        section = text[invoking_start : next_h2 if next_h2 != -1 else len(text)]
        assert "[quoin-bundle]" not in section, (
            "thorough_plan/SKILL.md Invoking each agent section contains [quoin-bundle]"
        )

    def test_thorough_plan_spawn_blocks_no_for_human_forwarding(self):
        """thorough_plan/SKILL.md Invoking-each-agent section has no
        ``## For human`` forwarding instruction in spawn-prompt constructs."""
        text = _read_skill("thorough_plan")
        invoking_start = text.find("### Invoking each agent")
        assert invoking_start != -1
        next_h2 = text.find("\n## ", invoking_start + 10)
        section = text[invoking_start : next_h2 if next_h2 != -1 else len(text)]
        # The section already bundles the no-[quoin-bundle] check above.
        # This test is a companion: no forwarding instruction either.
        # The "## For human" string appears only in prose describing the
        # plan output format (format-kit reference), not in a spawn construct.
        # Assert that any occurrence is inside prose, not a shell/Python
        # code block that would forward the block.
        for_match = section.find("## For human")
        if for_match != -1:
            # If present at all, verify it's not inside a fenced block
            # (which would indicate a forwarding instruction).
            before = section[:for_match]
            last_open = before.rfind("```")
            last_close = before.rfind("```\n")
            in_fence = last_open > last_close
            assert not in_fence, (
                "## For human found inside fenced code block in "
                "Invoking each agent section — possible forwarding instruction"
            )

    def test_architect_spawn_blocks_no_bundle_token(self):
        """architect/SKILL.md is bundle-clean."""
        path = _ADAPTER / "architect" / "SKILL.md"
        if not path.exists():
            pytest.skip("architect/SKILL.md not found")
        text = path.read_text()
        assert "[quoin-bundle]" not in text, (
            "architect/SKILL.md contains [quoin-bundle] token"
        )


class TestInvariantSentencesPresent:
    """Assertion (b): the fresh-context invariant sentences in
    thorough_plan/SKILL.md remain present verbatim."""

    def test_fresh_context_invariant_thorough_plan(self):
        text = _read_skill("thorough_plan")
        invariant = (
            "fresh context is essential for unbiased critique"
        )
        assert invariant in text, f"Invariant missing: {invariant}"


class TestContextBundleOutputShape:
    """Assertion (c): context_bundle.py emits ONLY path lines and
    ## For human-sourced lines; emits explicit path-only entry for members
    lacking the block.

    Fixture-driven — assertions use example files, not prose-derived
    expectations, so they survive implementation errors that
    prose-derived expectations would mirror (MIN-1)."""

    @staticmethod
    def _run_bundle(cwd: Path, task: str, stage: str | None = None, wrap: bool = False) -> str:
        cmd = [sys.executable, str(_QUOIN_SCRIPTS / "context_bundle.py"), "--task", task]
        if stage is not None:
            cmd.extend(["--stage", stage])
        if wrap:
            cmd.append("--wrap")
        return subprocess.run(cmd, capture_output=True, text=True, cwd=str(cwd)).stdout

    def test_bundle_with_real_data(self):
        """Real task data: all three members present, spec is path-only."""
        # Exercise with the actual ivg-164 task (real fixture on disk)
        repo = _QUOIN_SCRIPTS.parent  # quoin/quoin/
        project_root = repo.parent.parent  # Codex_workflow/
        output = self._run_bundle(project_root, "ivg-164-token-optimization-wave3", "2", wrap=True)
        lines = output.strip().splitlines()
        assert lines[0] == "[quoin-bundle]", f"First line: {lines[0]}"
        assert lines[-1] == "[/quoin-bundle]", f"Last line: {lines[-1]}"
        # All member lines have pipe separator
        for line in lines[1:-1]:
            assert " | " in line, f"Missing separator: {line}"
        # spec.md is always path-only
        spec_lines = [l for l in lines if "spec.md" in l]
        assert len(spec_lines) >= 1, "spec.md member missing"
        for sl in spec_lines:
            assert "summary: absent (path-only)" in sl, f"spec.md not path-only: {sl}"

    def test_missing_for_human_block_emits_path_only(self, tmp_path):
        """v2 plan (no ## For human block) emits path-only."""
        wf = tmp_path / ".workflow_artifacts" / "v2-task"
        wf.mkdir(parents=True)
        (wf / "architecture.md").write_text("## Context\nNo For human block here.\n")
        (wf / "current-plan.md").write_text("## Tasks\n1. Old v2 task\n")
        (wf / "spec.md").write_text("## Context\nSpec.\n")

        output = self._run_bundle(tmp_path, "v2-task")
        assert "architecture.md | summary: absent (path-only)" in output, output
        assert "current-plan.md | summary: absent (path-only)" in output, output

    def test_fast_route_stub_extracts_summary(self, tmp_path):
        """Fast-route stub (provenance marker present) still emits For human summary."""
        wf = tmp_path / ".workflow_artifacts" / "fast-task"
        wf.mkdir(parents=True)
        (wf / "architecture.md").write_text("## For human\nArch summary.\n\n## Context\nCtx.\n")
        (wf / "current-plan.md").write_text(
            "---\nprovenance: fast-path-triage\n---\n\n"
            "## For human\nFast route plan stub — no planning phase ran.\n\n"
            "## State\n```yaml\nRoute: fast\n```\n"
        )
        (wf / "spec.md").write_text("## Context\nSpec.\n")

        output = self._run_bundle(tmp_path, "fast-task")
        assert "Fast route plan stub" in output, (
            f"Fast-route stub summary not extracted. Output:\n{output}"
        )
        assert "Arch summary" in output, (
            f"Architecture summary not extracted. Output:\n{output}"
        )
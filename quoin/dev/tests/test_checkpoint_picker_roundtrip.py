"""Characterization harness for checkpoint_picker.select_restore (IVG-139, S-2).

READ THIS FIRST — anti-circularity / authority hierarchy (T-01, MAJ-1)
-----------------------------------------------------------------------
This harness proves `module == S-1 spec` (`quoin/memory/checkpoint-spec.md`),
NOT `module == the live runtime SKILL.md prose`. The live
`quoin/adapters/claude/skills/checkpoint/SKILL.md` restore picker (Step 1.0,
lines ~700-999) is left UNCHANGED in this stage — rewiring it to call this
module is a follow-up stage (S-3). Spec fidelity is therefore the singly
-sourced assumption this harness rests on (S-2 plan T-08 corrected the one
known spec/prose divergence found in round 2, the CRIT-1 anchor-task
precedence).

Deriving expected values purely from the spec is NOT anti-circular with
respect to prose fidelity: the module is written to the spec and the golden
values are read from the same spec, so a spec blind spot is invisible to a
spec-only test. To mitigate this, every EXPECTED-table row below (and every
assertion in the corpus this file grows into, T-05) is tagged with one of
three independent authorities, in DECREASING trust:

  1. "incident"  — the expected Verdict is anchored to an observed
     wrong-then-right behavior resolution (a Linear issue, or a dated
     `fixtures/checkpoint_picker/` scenario) — independent of the spec's own
     prose restatement.
  2. "prose"     — the expected value is pinned to a QUOTED SKILL.md line
     (not a spec paraphrase), so a spec-vs-prose divergence would be caught,
     not encoded. Example (CRIT-1, SKILL.md:886):
       `freshest_task="${_anchor_task}"` (anchor-first; freshest-session is
       only the `-z` fallback at SKILL.md:887-890).
  3. "spec"      — the residual, WEAKEST anchor: cites only the
     `checkpoint-spec.md` section. Used only where no incident or prose line
     is available.

TODO(T-04/T-05): this file currently holds the harness scaffold, the fixture
builder, and a FOUNDATIONAL set of round-trip cases only (T-01/T-02/T-03 of
the S-2 plan). The full incident corpus (anchor-task precedence twin fixture,
B3 Clause-B, staleness-boundary, compact-ordering/dedup, same-sid collision,
etc. — S-2 plan T-05) and the hardened purity/parity guards (no-writes
snapshot, no-env-mutation, static side-effect grep, filename_task parity,
no-local-hash guard — S-2 plan T-04) are intentionally NOT implemented here
yet; a later dispatch extends this file. Search this file for
`# TODO(T-04/T-05)` markers for the exact extension points.
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Import the core module under test + the sibling writer used to build a
# REAL thorough-plan-progress fixture (lesson ivg-84 — direct package import
# raises ModuleNotFoundError from this test layout; use importlib instead).
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[3]
_CORE = REPO_ROOT / "quoin" / "core" / "scripts" / "checkpoint_picker.py"
_TPC_CORE = REPO_ROOT / "quoin" / "core" / "scripts" / "thorough_plan_checkpoint.py"
_WRAPPER = REPO_ROOT / "quoin" / "scripts" / "checkpoint_picker.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


_MOD = _load(_CORE, "_test_checkpoint_picker_core")
_TPC = _load(_TPC_CORE, "_test_checkpoint_picker_tpc")


# ---------------------------------------------------------------------------
# EXPECTED table (T-01) — one row per scenario, authority-tagged.
#
# TODO(T-04/T-05): this table is a STUB this round. The full incident corpus
# (each row anchored to its strongest available authority per the hierarchy
# above, including the CRIT-1 anchor-precedence row and the MIN-4
# int-truncation staleness-boundary row, both of which MUST be `prose`
# -pinned per the S-2 plan) lands in a later dispatch. The two rows below
# demonstrate the required shape and are exercised by the foundational test
# cases further down this file.
# ---------------------------------------------------------------------------

EXPECTED = [
    {
        "name": "tier1_same_task_fastpath",
        "authority": "spec",
        "citation": "checkpoint-spec.md 'Picker tiers' (Tier 1)",
        "expect": {"tier": 1, "reason": "tier1:same-task"},
    },
    {
        "name": "crit1_anchor_precedence_placeholder",
        "authority": "prose",
        "citation": (
            'freshest_task="${_anchor_task}" [SKILL.md:886] (anchor-first; '
            "freshest-session is only the -z fallback, SKILL.md:887-890) "
            "-- full twin fixture deferred to T-05"
        ),
        "expect": None,  # placeholder: real assertion added by T-05
    },
]


def test_expected_table_has_authority():
    """Meta-assertion (T-01 acceptance): every EXPECTED row carries a
    non-empty authority in {incident, prose, spec} and a citation."""
    seen_prose = False
    for row in EXPECTED:
        assert row["authority"] in {"incident", "prose", "spec"}, row["name"]
        assert row.get("citation"), row["name"]
        if row["authority"] == "prose":
            assert "SKILL.md:" in row["citation"], row["name"]
            seen_prose = True
    assert seen_prose, "at least one EXPECTED row must be prose-pinned (CRIT-1 lineage)"


# ---------------------------------------------------------------------------
# Fixture builder (T-01)
# ---------------------------------------------------------------------------

def _write(path: Path, content: str, mtime: float) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    os.utime(path, (mtime, mtime))
    return path


def _session_state_content(task: str, sid: str = "") -> str:
    body = f"## Active task: {task}\n\n## Current stage\nimplement\n\n"
    if sid:
        body += f"## Session ID\n{sid}\n\n## Cost\n- Session UUID: {sid}\n"
    return body


def _checkpoint_content(task: str, sid: str = "unknown", branch: str = "main") -> str:
    return (
        "## Status\nvoluntary\n\n"
        "## Current stage\nimplement\n\n"
        f"## Active task\n{task}\n\n"
        f"## Branch\n{branch}\n\n"
        f"## Session ID\n{sid}\n\n"
    )


def _build_memory(tmp_path: Path, spec: dict) -> Path:
    """Materialize a temp `.workflow_artifacts/memory/` tree per `spec`.

    `spec` keys (all optional, each a list of dicts unless noted):
      sessions:        [{"name", "mtime", "task", "sid"}]  -> sessions/*.md
      checkpoints:     [{"name", "mtime", "task", "sid", "branch"}] -> checkpoints/*.md
                        (all three /checkpoint filename shapes are just
                        different `name` values, e.g.
                        "2026-07-01T0930-my-task.md" (timestamped),
                        "2026-07-01-my-task.md" (legacy),
                        "2026-07-01-my-task-precompact.md" (precompact))
      pending_restore: [{"sid", "mtime", "points_to"}] -> pending-restore-<sid>.txt
                        ("points_to" is an absolute path string written as
                        the sentinel's one-line content)
      pending_prompt:  [{"sid", "mtime"}] -> pending-prompt-<sid>.txt (empty body)

    Returns the `memory_dir` Path (`tmp_path/.workflow_artifacts/memory`).
    """
    memory_dir = tmp_path / ".workflow_artifacts" / "memory"
    (memory_dir / "sessions").mkdir(parents=True, exist_ok=True)
    (memory_dir / "checkpoints").mkdir(parents=True, exist_ok=True)

    for s in spec.get("sessions", []):
        _write(
            memory_dir / "sessions" / s["name"],
            _session_state_content(s.get("task", ""), s.get("sid", "")),
            s["mtime"],
        )

    for c in spec.get("checkpoints", []):
        _write(
            memory_dir / "checkpoints" / c["name"],
            _checkpoint_content(c.get("task", ""), c.get("sid", "unknown"), c.get("branch", "main")),
            c["mtime"],
        )

    for pr in spec.get("pending_restore", []):
        _write(
            memory_dir / f"pending-restore-{pr['sid']}.txt",
            str(pr["points_to"]) + "\n",
            pr["mtime"],
        )

    for pp in spec.get("pending_prompt", []):
        _write(memory_dir / f"pending-prompt-{pp['sid']}.txt", "\n", pp["mtime"])

    return memory_dir


# A fixed, deterministic epoch (R-07 — no wall-clock). 2026-07-14 00:00:00 UTC.
NOW = 1784332800.0
DAY = 86400.0


# ---------------------------------------------------------------------------
# (a) Same-task Tier-1 fast-path hit -> tier=1
# ---------------------------------------------------------------------------

def test_tier1_same_task_fastpath_hit(tmp_path, monkeypatch):
    monkeypatch.setenv("QUOIN_RESTORE_STALE_DAYS", "1")
    monkeypatch.setenv("QUOIN_RESTORE_SENTINEL_WINDOW", "7")
    monkeypatch.setenv("QUOIN_SESSION_FALLBACK_WINDOW", "7")
    monkeypatch.setenv("QUOIN_PICKER_DEDUP_WINDOW", "7")

    sid = "SID-TIER1"
    task = "my-task"
    memory_dir = _build_memory(tmp_path, {
        "sessions": [{"name": "2026-07-13-my-task.md", "mtime": NOW - DAY, "task": task}],
        "checkpoints": [{"name": "2026-07-10T0900-my-task.md", "mtime": NOW - 3 * DAY,
                          "task": task, "sid": sid, "branch": "main"}],
    })
    cp_path = memory_dir / "checkpoints" / "2026-07-10T0900-my-task.md"
    _write(memory_dir / f"pending-restore-{sid}.txt", str(cp_path) + "\n", NOW - DAY)

    verdict = _MOD.select_restore(memory_dir, sid, NOW)

    assert verdict["tier"] == 1, verdict
    assert verdict["reason"] == "tier1:same-task", verdict
    assert verdict["selected_path"] == str(cp_path)
    assert verdict["cross_task_ok"] is True
    assert verdict["stale"] is False  # staleness NOT applied at Tier 1 (SKILL.md:708)
    assert verdict["derived_task"] == task
    assert verdict["kind"] == "checkpoint"


# ---------------------------------------------------------------------------
# (b) No-candidates case -> B3 (derived_task template, since a session
#     baseline exists within the fallback window)
# ---------------------------------------------------------------------------

def test_no_candidates_routes_to_b3_with_derived_task_prompt(tmp_path, monkeypatch):
    monkeypatch.setenv("QUOIN_RESTORE_STALE_DAYS", "1")
    monkeypatch.setenv("QUOIN_RESTORE_SENTINEL_WINDOW", "7")
    monkeypatch.setenv("QUOIN_SESSION_FALLBACK_WINDOW", "7")
    monkeypatch.setenv("QUOIN_PICKER_DEDUP_WINDOW", "7")

    task = "solo-task"
    memory_dir = _build_memory(tmp_path, {
        "sessions": [{"name": "2026-07-13-solo-task.md", "mtime": NOW - DAY, "task": task}],
        # no checkpoints, no sentinels -> Clause A (zero candidates)
    })

    verdict = _MOD.select_restore(memory_dir, "unknown", NOW)

    assert verdict["tier"] == "4-B3", verdict
    assert verdict["selected_path"] is None
    assert verdict["derived_task"] == task
    assert verdict["reason"] == "b3:clause-a"
    expected_prompt = (
        f"Resume task '{task}': no checkpoint selected (tier 4 / B3). Synthesize a minimal "
        f"restore from the freshest session-state file for '{task}'."
    )
    assert verdict["b3_prompt"] == expected_prompt


def test_no_candidates_and_no_sessions_b3_prompt_is_none(tmp_path, monkeypatch):
    """Total dead end (no candidates, no session baseline at all) -> b3_prompt
    is None and reason narrows to 'none:no-candidates'."""
    monkeypatch.setenv("QUOIN_RESTORE_STALE_DAYS", "1")
    monkeypatch.setenv("QUOIN_RESTORE_SENTINEL_WINDOW", "7")
    monkeypatch.setenv("QUOIN_SESSION_FALLBACK_WINDOW", "7")
    monkeypatch.setenv("QUOIN_PICKER_DEDUP_WINDOW", "7")

    memory_dir = _build_memory(tmp_path, {})

    verdict = _MOD.select_restore(memory_dir, "unknown", NOW)

    assert verdict["tier"] == "4-B3"
    assert verdict["b3_prompt"] is None
    assert verdict["reason"] == "none:no-candidates"


# ---------------------------------------------------------------------------
# (c) thorough-plan-progress routing case -> reason='route:thorough-plan-progress'
# ---------------------------------------------------------------------------

def test_thorough_plan_progress_routes_out(tmp_path, monkeypatch):
    monkeypatch.setenv("QUOIN_RESTORE_STALE_DAYS", "1")
    monkeypatch.setenv("QUOIN_RESTORE_SENTINEL_WINDOW", "7")
    monkeypatch.setenv("QUOIN_SESSION_FALLBACK_WINDOW", "7")
    monkeypatch.setenv("QUOIN_PICKER_DEDUP_WINDOW", "7")

    sid = "SID-TPPROGRESS"
    task = "ivg-139-checkpoint-picker"

    # Own session-state file (NOT the --session-state orchestrator file _TPC
    # would create — that filename carries a "-orchestrator" suffix which
    # would NOT match `task` after date-prefix stripping and would spuriously
    # trip the Tier-1 cross-task guard). Keeping this fixture's freshest
    # session filename-task exactly equal to `task` isolates the routing
    # assertion under test.
    memory_dir = _build_memory(tmp_path, {
        "sessions": [{"name": f"2026-07-14-{task}.md", "mtime": NOW, "task": task}],
    })

    # Build the REAL thorough-plan-progress-{sid}.md + pending-restore-{sid}.txt
    # by calling the actual writer (T-01 requirement: schema is real, not
    # hand-faked).
    rc = _TPC.main([
        "--project-root", str(tmp_path),
        "--task", task,
        "--round", "1",
        "--phase", "plan",
        "--sid", sid,
        "--branch", "main",
    ])
    assert rc == 0

    ckpt = memory_dir / "checkpoints" / f"thorough-plan-progress-{sid}.md"
    sentinel = memory_dir / f"pending-restore-{sid}.txt"
    assert ckpt.exists() and sentinel.exists()
    # Pin mtimes so this fixture is deterministic (R-07), not wall-clock-order-dependent.
    os.utime(ckpt, (NOW, NOW))
    os.utime(sentinel, (NOW, NOW))

    verdict = _MOD.select_restore(memory_dir, sid, NOW)

    assert verdict["kind"] == "thorough-plan-progress", verdict
    assert verdict["reason"] == "route:thorough-plan-progress", verdict
    assert verdict["selected_path"] == str(ckpt)


# ---------------------------------------------------------------------------
# (d) Wrapper re-exports select_restore (T-03 acceptance)
# ---------------------------------------------------------------------------

def test_wrapper_reexports_select_restore(tmp_path):
    # The wrapper loads its own copy of the core module via importlib
    # (parents[1]/core/scripts), so its `select_restore` is a DISTINCT object
    # from the harness's independently-loaded `_MOD.select_restore` — an `is`
    # identity check can never hold across two file-based importlib loads.
    # The T-03 contract is faithful RE-EXPORT: the wrapper must expose
    # `select_restore` + `main`, and its `select_restore` must be the same
    # function the wrapper itself loaded from core AND behave identically to
    # the core's on the same input.
    wrapper = _load(_WRAPPER, "_test_checkpoint_picker_wrapper")
    assert hasattr(wrapper, "select_restore")
    assert callable(wrapper.select_restore)
    assert hasattr(wrapper, "main")
    # Re-export fidelity: the wrapper's re-exported name IS the object it loaded
    # from core (same-load identity), and both cores share a qualified name.
    assert wrapper.select_restore is getattr(wrapper._CORE, "select_restore")
    assert wrapper.select_restore.__qualname__ == _MOD.select_restore.__qualname__
    # Behavioral parity: identical Verdict on the same empty-memory input.
    memory_dir = _build_memory(tmp_path, {"sessions": []})
    assert wrapper.select_restore(memory_dir, "unknown", NOW) == _MOD.select_restore(
        memory_dir, "unknown", NOW
    )

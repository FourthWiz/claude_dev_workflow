"""IVG-258 T-12: a live census of every /run and /thorough_plan run-state
writer call.

Never a frozen count -- everything here is derived from the live
`run/SKILL.md` / `thorough_plan/SKILL.md` text and cross-checked against
`quoin.supervisor.RESUMABLE_PHASES`, so a future added phase or escalation
site without a writer call fails CLOSED rather than being silently missed.
"""
from __future__ import annotations

import importlib
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
RUN_SKILL = REPO_ROOT / "quoin" / "adapters" / "claude" / "skills" / "run" / "SKILL.md"
THOROUGH_PLAN_SKILL = (
    REPO_ROOT / "quoin" / "adapters" / "claude" / "skills" / "thorough_plan" / "SKILL.md"
)

WRITE_CALL = "run_state.py --write"
CLEAR_CALL = "run_state.py --clear"
# The escalation rewind sets `phase` to the last phase whose output survives
# the escalation (fast_path_triage, since the rewind deletes the architect /
# thorough_plan / implement sentinels), never to the re-entry target
# (architect) itself -- see the "Field invariant" paragraph in
# run/SKILL.md's Resume Step 1.
ESCALATION_REWIND = "--phase fast_path_triage --phase-index 1"
REWIND_PHRASE = "rewind the run-state record"
REENTER_PHRASE = "re-enter at the architect phase"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Slice helpers -- definitions restated once, matching T-08/T-12's own prose.
# ---------------------------------------------------------------------------


def _phase_heading_slices(text: str) -> dict:
    """Slice the doc by its `## Phase N[.M] — ...` headings, in file order.

    Bounded to the NEXT `## ` (any) heading, or EOF for the last one. Zipped
    positionally against `quoin.supervisor.RESUMABLE_PHASES` -- both are
    ordered identically by construction (the doc's own Phase sequence).
    """
    supervisor = importlib.import_module("quoin.supervisor")
    phase_headings = [
        m.start() for m in re.finditer(r"^## Phase [\d.]+ — .*$", text, re.M)
    ]
    all_headings = [m.start() for m in re.finditer(r"^## .*$", text, re.M)]
    assert len(phase_headings) == len(supervisor.RESUMABLE_PHASES), (
        f"expected {len(supervisor.RESUMABLE_PHASES)} '## Phase' headings, "
        f"found {len(phase_headings)}"
    )
    slices = {}
    for name, start in zip(supervisor.RESUMABLE_PHASES, phase_headings):
        later = [h for h in all_headings if h > start]
        end = min(later) if later else len(text)
        slices[name] = text[start:end]
    return slices


def _escalation_slices(text: str) -> list:
    """The three escalation atomic units: from each `DELETE ...architect.done`
    occurrence forward to the first line matching `^Under `AUTONOMOUS``,
    `^\\*\\*If `, or `^## `. Definition restated verbatim from T-08/T-12.
    """
    delete_marker = "DELETE `autonomous-progress-{task}/architect.done`"
    starts = [m.start() for m in re.finditer(re.escape(delete_marker), text)]
    assert len(starts) == 3, f"expected 3 escalation DELETE sites, found {len(starts)}"
    boundary_re = re.compile(r"^(Under `AUTONOMOUS`|\*\*If |## )", re.M)
    slices = []
    for start in starts:
        m = boundary_re.search(text, start)
        end = m.start() if m else len(text)
        slices.append(text[start:end])
    return slices


def _autonomy_slices(text: str) -> list:
    """Every span from a line matching `^Under `AUTONOMOUS`` to the next
    blank line -- used to prove a writer call is never gated on autonomy.
    """
    lines = text.splitlines()
    slices = []
    i = 0
    while i < len(lines):
        if lines[i].startswith("Under `AUTONOMOUS`"):
            j = i
            while j < len(lines) and lines[j].strip() != "":
                j += 1
            slices.append("\n".join(lines[i:j]))
            i = j
        else:
            i += 1
    return slices


# ---------------------------------------------------------------------------
# Census
# ---------------------------------------------------------------------------


def test_every_stage_transition_site_calls_the_writer():
    text = _text(RUN_SKILL)
    slices = _phase_heading_slices(text)
    missing = [name for name, sl in slices.items() if WRITE_CALL not in sl]
    assert not missing, f"phases missing a {WRITE_CALL!r} call: {missing}"


def test_writer_call_is_not_gated_on_autonomous():
    text = _text(RUN_SKILL)
    for sl in _autonomy_slices(text):
        assert "run_state.py" not in sl, (
            "a run_state.py occurrence falls inside an 'Under `AUTONOMOUS`' "
            f"paragraph:\n{sl}"
        )


def test_escalation_sites_rewind_the_record():
    text = _text(RUN_SKILL)
    for sl in _escalation_slices(text):
        assert WRITE_CALL in sl, f"escalation slice has no rewind write:\n{sl}"
        assert ESCALATION_REWIND in sl, (
            f"escalation slice does not rewind phase to fast_path_triage:\n{sl}"
        )


def test_escalation_sites_frame_and_order_the_rewind():
    """Each escalation slice must (a) carry a framing sentence introducing the
    rewind -- not a bare code block -- and (b) perform the rewind BEFORE
    transferring control with "re-enter at the architect phase". A rewind
    ordered after the re-enter instruction is scheduled after control has
    already left the atomic unit and, on an interactive run with no
    sentinels, is never reached.
    """
    text = _text(RUN_SKILL)
    for sl in _escalation_slices(text):
        assert REWIND_PHRASE in sl, f"escalation slice has no rewind framing sentence:\n{sl}"
        assert REENTER_PHRASE in sl, f"escalation slice has no re-enter instruction:\n{sl}"
        assert sl.index(REWIND_PHRASE) < sl.index(REENTER_PHRASE), (
            f"rewind must precede re-enter in escalation slice:\n{sl}"
        )


def test_escalation_rewind_at_the_blocked_site_is_inline_on_one_line():
    text = _text(RUN_SKILL)
    slices = _escalation_slices(text)
    single_line = [sl for sl in slices if "\n" not in sl.strip()]
    assert len(single_line) == 1, (
        f"expected exactly one single-physical-line escalation site, found {len(single_line)}"
    )
    sl = single_line[0]
    assert WRITE_CALL in sl
    assert sl.strip() != ""


def test_phase_six_calls_clear():
    text = _text(RUN_SKILL)
    slices = _phase_heading_slices(text)
    assert CLEAR_CALL in slices["end_of_task"]


def test_phase_six_write_precedes_clear():
    text = _text(RUN_SKILL)
    slices = _phase_heading_slices(text)
    phase6 = slices["end_of_task"]
    assert phase6.index(WRITE_CALL) < phase6.index(CLEAR_CALL)


def test_thorough_plan_round_boundary_calls_writer():
    text = _text(THOROUGH_PLAN_SKILL)
    assert WRITE_CALL in text


def test_thorough_plan_writer_is_require_existing():
    tp_text = _text(THOROUGH_PLAN_SKILL)
    assert tp_text.count("run_state.py --write --require-existing") == 1
    run_text = _text(RUN_SKILL)
    assert "--require-existing" not in run_text


def test_thorough_plan_writer_call_follows_the_ivg98_checkpoint():
    text = _text(THOROUGH_PLAN_SKILL)
    checkpoint_idx = text.index("thorough_plan_checkpoint.py")
    writer_idx = text.index("run_state.py --write --require-existing")
    assert checkpoint_idx < writer_idx


def test_no_writer_call_uses_literal_tilde_claude():
    for path in (RUN_SKILL, THOROUGH_PLAN_SKILL):
        text = _text(path)
        for line in text.splitlines():
            if "run_state.py" in line:
                assert "~/.claude" not in line, f"{path}: literal tilde-claude in: {line}"

r"""Universal decision-gate classification-marker census (IVG-150, T-20 / AC-9).

Every GENUINE decision site across every adapter `SKILL.md` must carry a classification
marker; `fail-closed` sites must reference `decision_gate_guard.py` and the other classes must
not (set-equality); and each marker binds ONE-TO-ONE to its genuine token(s) (marker-token
adjacency / strict bijection — closes the round-2 absorption blind spot). Adversarial mutation
tests prove the census bites.

Census population derivation (D-03), implemented once in `_genuine_decision_sites`:
  1. STRUCTURALLY drop the generated dispatch-preamble H2 sections by the generator's OWN
     heading constants (SECTION0_HEADING / POLLUTION_HEADING / MINTIER_HEADING /
     MINTIER_SONNET_HEADING / ZC_HEADING) imported from inject_pollution_dispatch.py via the
     spec_from_file_location loader (the dotted `quoin.quoin.scripts.…` path does not resolve).
     Belt-and-suspenders: regex-strip residual `<!-- §0*-begin -->…<!-- §0*-end -->` fences.
  2. Enumerate genuine sites by CALL / INVOCATION syntax over the surviving text:
     `AskUserQuestion(` call-sites, the `session_age_guard.py` invocation, the gate-approval
     STOP (`### Step 4: STOP and wait`), and the `/sleep --purge` heading. Prose mentions
     (e.g. `present \`AskUserQuestion\`:` with no paren) are intentionally NOT counted.

Marker granularity = MARKER-TOKEN ADJACENCY (D-02): sort markers and tokens by position in the
surviving text; each marker OWNS the genuine tokens that follow it up to the next marker, and
the owned count must equal the marker's `tokens=N` (default 1). A token before the first marker
is unowned → coverage FAILS. A marker owning more tokens than declared → an absorbed extra gate
→ bijection FAILS. Fewer → a decorative/orphan marker → FAILS.
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
PKG_DIR = TESTS_DIR.parent.parent  # quoin/quoin/
SCRIPTS_DIR = PKG_DIR / "scripts"
ADAPTER_SKILLS_DIR = PKG_DIR / "adapters" / "claude" / "skills"

# ─── Import the FIVE generator heading constants (single-source discipline) ───
_spec = importlib.util.spec_from_file_location(
    "inject_pollution_dispatch", SCRIPTS_DIR / "inject_pollution_dispatch.py"
)
assert _spec is not None and _spec.loader is not None
_ipd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_ipd)

GENERATED_HEADINGS = {
    _ipd.SECTION0_HEADING,
    _ipd.POLLUTION_HEADING,
    _ipd.MINTIER_HEADING,
    _ipd.MINTIER_SONNET_HEADING,
    _ipd.ZC_HEADING,
}

# ─── Regexes ──────────────────────────────────────────────────────────────────
MARKER_RE = re.compile(
    r"<!--\s*decision-gate:\s*"
    r"(?P<cls>fail-closed|best-effort|out-of-scope|safe-degrade)\s+"
    r"(?P<attrs>[^>]*?)\s*-->"
)
_FENCE_RE = re.compile(r"<!-- §0[^>]*?-begin -->.*?<!-- §0[^>]*?-end -->", re.DOTALL)

# Genuine token detectors (call/invocation syntax over surviving text).
TOKEN_DETECTORS = (
    ("auq", lambda ln: "AskUserQuestion(" in ln),
    ("session-age", lambda ln: "session_age_guard.py" in ln),
    ("gate-stop", lambda ln: ln.strip().startswith("### Step 4: STOP and wait")),
    ("purge", lambda ln: ln.strip().startswith("## --purge --older-than")),
)

HELPER_TOKEN = "decision_gate_guard.py"


def _strip_generated(text: str) -> str:
    """Drop generated dispatch-preamble H2 sections + residual §0 fenced regions."""
    out: list[str] = []
    drop = False
    for ln in text.split("\n"):
        if ln.startswith("## "):
            drop = ln.strip() in GENERATED_HEADINGS
        if not drop:
            out.append(ln)
    return _FENCE_RE.sub("", "\n".join(out))


def _tokens(text: str) -> list[tuple[int, str]]:
    """Return [(line_index, kind), …] of genuine decision tokens in surviving text."""
    found = []
    for i, ln in enumerate(text.split("\n")):
        for kind, pred in TOKEN_DETECTORS:
            if pred(ln):
                found.append((i, kind))
                break
    return found


def _markers(text: str) -> list[dict]:
    """Return [{line, cls, site, tokens}, …] for each decision-gate marker."""
    markers = []
    for i, ln in enumerate(text.split("\n")):
        m = MARKER_RE.search(ln)
        if not m:
            continue
        attrs = m.group("attrs")
        site_m = re.search(r"site=(?P<s>[\w./-]+)", attrs)
        tok_m = re.search(r"tokens=(?P<t>\d+)", attrs)
        markers.append(
            {
                "line": i,
                "cls": m.group("cls"),
                "site": site_m.group("s") if site_m else None,
                "tokens": int(tok_m.group("t")) if tok_m else 1,
            }
        )
    return markers


def _genuine_decision_sites(skill_text: str) -> tuple[list[dict], list[tuple[int, str]]]:
    """Single source of derivation reused by every assertion: (markers, tokens) over
    the generator-stripped text."""
    stripped = _strip_generated(skill_text)
    return _markers(stripped), _tokens(stripped)


def _owned_ranges(markers: list[dict], end: int) -> list[tuple[dict, int, int]]:
    """Return [(marker, start_line_exclusive, stop_line_exclusive), …] ownership windows."""
    ranges = []
    for idx, mk in enumerate(markers):
        stop = markers[idx + 1]["line"] if idx + 1 < len(markers) else end
        ranges.append((mk, mk["line"], stop))
    return ranges


# ─── Violation finders (return lists; empty == clean) ─────────────────────────
def coverage_violations(text: str) -> list[str]:
    markers, tokens = _genuine_decision_sites(text)
    v = []
    first_marker = markers[0]["line"] if markers else None
    for tline, kind in tokens:
        if first_marker is None or tline < first_marker:
            v.append(f"token kind={kind} at line {tline} is not covered by any marker")
    return v


def bijection_violations(text: str) -> list[str]:
    markers, tokens = _genuine_decision_sites(text)
    end = len(text.split("\n")) if not markers else max(len(text.split("\n")), markers[-1]["line"] + 1)
    v = []
    for mk, start, stop in _owned_ranges(markers, end):
        owned = [t for (t, _k) in tokens if start < t < stop]
        if len(owned) != mk["tokens"]:
            v.append(
                f"marker site={mk['site']} cls={mk['cls']} declares tokens={mk['tokens']} "
                f"but owns {len(owned)} genuine token(s)"
            )
    return v


def wiring_violations(text: str) -> list[str]:
    markers, _tokens_ = _genuine_decision_sites(text)
    stripped_lines = _strip_generated(text).split("\n")
    end = len(stripped_lines)
    v = []
    for mk, start, stop in _owned_ranges(markers, end):
        scope_text = "\n".join(stripped_lines[start:stop])
        has_helper = HELPER_TOKEN in scope_text
        if mk["cls"] == "fail-closed" and not has_helper:
            v.append(f"fail-closed site={mk['site']} does NOT reference {HELPER_TOKEN}")
        if mk["cls"] != "fail-closed" and has_helper:
            v.append(f"{mk['cls']} site={mk['site']} unexpectedly references {HELPER_TOKEN}")
    return v


def _skill_files() -> list[Path]:
    return sorted(ADAPTER_SKILLS_DIR.glob("*/SKILL.md"))


# ─── Real-tree census (must be GREEN) ─────────────────────────────────────────
def test_every_decision_site_classified():
    """COVERAGE: every genuine token lies within some marker's ownership window."""
    problems = {}
    for f in _skill_files():
        v = coverage_violations(f.read_text(encoding="utf-8"))
        if v:
            problems[f.name] = v
    assert not problems, f"uncovered decision sites: {problems}"


def test_marker_token_bijection():
    """ADJACENCY/1:1: each marker owns EXACTLY tokens=N genuine tokens."""
    problems = {}
    for f in _skill_files():
        v = bijection_violations(f.read_text(encoding="utf-8"))
        if v:
            problems[f.name] = v
    assert not problems, f"marker-token bijection violations: {problems}"


def test_fail_closed_iff_helper_call():
    """SET-EQUALITY: fail-closed scopes reference the helper; others do not."""
    problems = {}
    for f in _skill_files():
        v = wiring_violations(f.read_text(encoding="utf-8"))
        if v:
            problems[f.name] = v
    assert not problems, f"wiring set-equality violations: {problems}"


def test_six_fail_closed_sites_present():
    """The 6 fail-closed sites + session-age are present tree-wide (roster sanity)."""
    sites = set()
    for f in _skill_files():
        markers, _ = _genuine_decision_sites(f.read_text(encoding="utf-8"))
        sites |= {mk["site"] for mk in markers if mk["cls"] == "fail-closed"}
    expected = {
        "garbage-files", "commit-decision", "archive-type",
        "gate-approval", "branch-hygiene", "destructive-undo", "session-age",
    }
    assert expected <= sites, f"missing fail-closed sites: {expected - sites}"


# ─── Adversarial mutation tests (must BITE) ───────────────────────────────────
_CLEAN = (
    "# Skill\n\n## Body\n"
    "<!-- decision-gate: fail-closed site=demo -->\n"
    "```\nAskUserQuestion(\n  question=\"x\"\n)\n```\n"
    "run decision_gate_guard.py fail-closed --site demo\n"
    "## Next\n"
)


def test_clean_synthetic_baseline_passes():
    assert coverage_violations(_CLEAN) == []
    assert bijection_violations(_CLEAN) == []
    assert wiring_violations(_CLEAN) == []


def test_guard_catches_unclassified_gate():
    tampered = _CLEAN + "\n## Sneaky\n```\nAskUserQuestion(\n  question=\"new\"\n)\n```\n"
    # The new gate is AFTER the last marker → absorbed → bijection bites
    # (and if it had preceded all markers, coverage would bite).
    assert bijection_violations(tampered), "an unclassified trailing gate must be caught"


def test_guard_catches_absorbed_gate():
    """Inject a gate INSIDE an existing tokens=1 marker's scope, AFTER its own token."""
    tampered = (
        "# Skill\n\n## Body\n"
        "<!-- decision-gate: best-effort site=lessons -->\n"
        "```\nAskUserQuestion(\n  question=\"a\"\n)\n```\n"
        "some prose\n"
        "```\nAskUserQuestion(\n  question=\"absorbed\"\n)\n```\n"  # 2nd token, no new marker
        "## Next\n"
    )
    v = bijection_violations(tampered)
    assert v and "owns 2" in " ".join(v), f"absorbed gate must trip bijection: {v}"


def test_guard_catches_fail_closed_marker_without_wiring():
    tampered = (
        "# Skill\n\n## Body\n"
        "<!-- decision-gate: fail-closed site=nowire -->\n"
        "```\nAskUserQuestion(\n  question=\"x\"\n)\n```\n"  # no decision_gate_guard.py
        "## Next\n"
    )
    assert wiring_violations(tampered), "fail-closed with no helper must trip set-equality"


def test_guard_catches_removed_helper_from_real_fail_closed_site():
    """Strip the helper ref from a REAL fail-closed scope (end_of_task) → set-equality bites."""
    text = (ADAPTER_SKILLS_DIR / "end_of_task" / "SKILL.md").read_text(encoding="utf-8")
    assert wiring_violations(text) == []  # green baseline
    tampered = text.replace(HELPER_TOKEN, "REMOVED_HELPER")
    assert wiring_violations(tampered), "removing the helper from a real fail-closed site must bite"

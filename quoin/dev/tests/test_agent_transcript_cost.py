"""test_agent_transcript_cost.py — fixture-only tests for agent_transcript_cost.py
(stage 2 of ivg-111-cost-attribution: nested subagent-transcript resolver + pricer).

All tests point resolvers at a SYNTHETIC fixture tree materialized under
<tmp_path>/.claude/projects/<hash>/<sid>/subagents/ (copied at test time from the
committed fixtures/agent_transcript_cost/projects/ source tree) via the
home=/project_path= override params — nothing here reads the developer's live
~/.claude (lessons 2026-06-16: subagent transcripts are not resolvable/portable
across machines, so tests must be fixture-only).

Note on fixture layout: the committed source tree under fixtures/agent_transcript_cost/
deliberately has NO literal ".claude" path segment, because quoin/.gitignore:3 ignores
any ".claude/" directory anywhere in the repo — a committed ".claude"-named fixture tree
would be silently invisible in a clean checkout (caught by
test_gitignore_no_source_shadow.py::test_no_shadowed_sources_in_quoin_dev). The
FIXTURES_HOME fixture below copies the source tree into a tmp_path-rooted
"<tmp>/.claude/projects/..." tree at test time instead, mirroring the established
pattern in test_dashboard_cost.py.

Cases (mirrors stage-2/current-plan.md T-07):
  (a) PRIMARY hit — resolve_by_agent_id + resolve_attribution -> nested_jsonl, priced
  (b) MODEL-LESS row — priceable=False path exercised via the model-less guard
  (c) MALFORMED-TOLERANCE — one junk line does not flip an otherwise-priceable transcript
  (d) FLUSH-guard -> unresolved — truncated last line
  (e) TOOLUSE secondary — resolve by tool_use_id when agent_id is omitted
  (f) MISSING transcript — absent id -> src=unresolved, no crash
  (g) UNKNOWN-model -> tok kept, no usd, no crash (parse_session's stderr warning expected)
  (h) PRICE-PARITY — price_agent_jsonl matches a hand computation via cost_for_entry
  (i) SYMMETRY — core.cost_event.parse_attribution(resolve_attribution(...)) round-trips
"""

import pathlib
import shutil
import sys

import pytest

# ---------------------------------------------------------------------------
# Path resolution helpers
# ---------------------------------------------------------------------------
REPO_ROOT = pathlib.Path(__file__).parent.parent.parent.parent  # quoin/ repo root
SCRIPTS_DIR = pathlib.Path(__file__).parent.parent.parent / "scripts"  # quoin/quoin/scripts/
CORE_SCRIPTS_DIR = pathlib.Path(__file__).parent.parent.parent / "core" / "scripts"

FIXTURES_SRC_PROJECTS = pathlib.Path(__file__).parent / "fixtures" / "agent_transcript_cost" / "projects"

sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(CORE_SCRIPTS_DIR))
import agent_transcript_cost as atc  # noqa: E402
from cost_event import parse_attribution  # noqa: E402

FAKE_PROJECT_PATH = "/fake/project"
FAKE_SID = "sess-test-uuid-001"

# Expected prices per PRICES table (quoin/quoin/scripts/cost_from_jsonl.py):
#   claude-opus-4-7:   input $5.00/1M,  output $25.00/1M
#   claude-sonnet-4-6: input $3.00/1M,  output $15.00/1M
# primary/malformed/toolusehit fixtures share this shape: opus row (1000 in / 200 out)
# + sonnet row (500 in / 100 out).
EXPECTED_USD = round(
    (1000 * 5.00 + 200 * 25.00) / 1_000_000.0
    + (500 * 3.00 + 100 * 15.00) / 1_000_000.0,
    6,
)
EXPECTED_TOK = 1000 + 200 + 500 + 100


@pytest.fixture(scope="module")
def fixtures_home(tmp_path_factory):
    """Materialize the committed fixture tree under <tmp>/.claude/projects/...
    so resolver functions (which hardcode the ".claude" path segment) can read
    it via home=<this fixture>, without any ".claude"-named path ever being
    committed to the repo (see module docstring)."""
    home = tmp_path_factory.mktemp("agent_transcript_cost_home")
    dest = home / ".claude" / "projects"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(FIXTURES_SRC_PROJECTS, dest)
    return home


def _resolve(home, **kwargs):
    kwargs.setdefault("project_path", FAKE_PROJECT_PATH)
    kwargs["home"] = home
    return atc.resolve_attribution(**kwargs)


# ---------------------------------------------------------------------------
# (a) PRIMARY hit + (h) PRICE-PARITY
# ---------------------------------------------------------------------------
def test_primary_hit_priced_and_matches_hand_computation(fixtures_home):
    jf = atc.resolve_by_agent_id(
        sid=FAKE_SID, agent_id="primary001",
        project_path=FAKE_PROJECT_PATH, home=fixtures_home,
    )
    assert jf is not None
    assert jf.name == "agent-primary001.jsonl"

    r = atc.price_agent_jsonl(jf)
    assert r["priceable"] is True
    assert r["tok"] == EXPECTED_TOK
    assert abs(r["usd"] - EXPECTED_USD) / EXPECTED_USD <= 0.01  # <=1% parity

    attr = _resolve(fixtures_home, sid=FAKE_SID, agent_id="primary001")
    assert attr == f"usd={EXPECTED_USD};tok={EXPECTED_TOK};src=nested_jsonl"


def test_resolve_by_agent_id_absent_id_returns_none(fixtures_home):
    jf = atc.resolve_by_agent_id(
        sid=FAKE_SID, agent_id="not-a-real-agent-id",
        project_path=FAKE_PROJECT_PATH, home=fixtures_home,
    )
    assert jf is None


# ---------------------------------------------------------------------------
# (b) MODEL-LESS
# ---------------------------------------------------------------------------
def test_modelless_row_forces_unpriceable(fixtures_home):
    jf = atc.resolve_by_agent_id(
        sid=FAKE_SID, agent_id="modelless001",
        project_path=FAKE_PROJECT_PATH, home=fixtures_home,
    )
    assert jf is not None
    r = atc.price_agent_jsonl(jf)
    assert r["priceable"] is False
    assert r["usd"] is None
    assert r["tok"] > 0  # tok kept even though unpriceable (only the priced row's tok)

    attr = _resolve(fixtures_home, sid=FAKE_SID, agent_id="modelless001")
    assert attr.startswith("tok=")
    assert attr.endswith(";src=unresolved")
    assert "usd=" not in attr


# ---------------------------------------------------------------------------
# (c) MALFORMED-TOLERANCE
# ---------------------------------------------------------------------------
def test_malformed_line_does_not_flip_priceable_transcript(fixtures_home):
    jf = atc.resolve_by_agent_id(
        sid=FAKE_SID, agent_id="malformed001",
        project_path=FAKE_PROJECT_PATH, home=fixtures_home,
    )
    assert jf is not None
    r = atc.price_agent_jsonl(jf)
    assert r["priceable"] is True
    assert r["tok"] == EXPECTED_TOK
    assert abs(r["usd"] - EXPECTED_USD) / EXPECTED_USD <= 0.01

    attr = _resolve(fixtures_home, sid=FAKE_SID, agent_id="malformed001")
    assert attr == f"usd={EXPECTED_USD};tok={EXPECTED_TOK};src=nested_jsonl"


# ---------------------------------------------------------------------------
# (d) FLUSH-guard -> unresolved
# ---------------------------------------------------------------------------
def test_truncated_last_line_fails_flush_guard(fixtures_home):
    jf = atc.resolve_by_agent_id(
        sid=FAKE_SID, agent_id="truncated001",
        project_path=FAKE_PROJECT_PATH, home=fixtures_home,
    )
    assert jf is not None
    assert atc.last_row_usage_present(jf) is False

    attr = _resolve(fixtures_home, sid=FAKE_SID, agent_id="truncated001")
    assert attr == "src=unresolved"


def test_empty_file_fails_flush_guard(tmp_path):
    empty = tmp_path / "agent-empty.jsonl"
    empty.write_text("")
    assert atc.last_row_usage_present(empty) is False


# ---------------------------------------------------------------------------
# (e) TOOLUSE secondary
# ---------------------------------------------------------------------------
def test_tooluse_secondary_resolver_hit(fixtures_home):
    jf = atc.resolve_by_tooluse(
        sid=FAKE_SID, tool_use_id="toolu_FIXTURE_TOOLUSE_HIT_001",
        project_path=FAKE_PROJECT_PATH, home=fixtures_home,
    )
    assert jf is not None
    assert jf.name == "agent-toolusehit001.jsonl"

    attr = _resolve(fixtures_home, sid=FAKE_SID, tool_use_id="toolu_FIXTURE_TOOLUSE_HIT_001")
    assert attr == f"usd={EXPECTED_USD};tok={EXPECTED_TOK};src=nested_jsonl"


def test_tooluse_secondary_resolver_no_match(fixtures_home):
    jf = atc.resolve_by_tooluse(
        sid=FAKE_SID, tool_use_id="toolu_DOES_NOT_EXIST",
        project_path=FAKE_PROJECT_PATH, home=fixtures_home,
    )
    assert jf is None

    attr = _resolve(fixtures_home, sid=FAKE_SID, tool_use_id="toolu_DOES_NOT_EXIST")
    assert attr == "src=unresolved"


# ---------------------------------------------------------------------------
# (f) MISSING transcript
# ---------------------------------------------------------------------------
def test_missing_transcript_no_agent_id_no_tooluse_id(fixtures_home):
    attr = _resolve(fixtures_home, sid=FAKE_SID)
    assert attr == "src=unresolved"


def test_missing_transcript_unknown_agent_id_no_crash(fixtures_home):
    attr = _resolve(fixtures_home, sid=FAKE_SID, agent_id="totally-absent-id")
    assert attr == "src=unresolved"


def test_missing_transcript_unknown_sid_no_crash(fixtures_home):
    attr = _resolve(fixtures_home, sid="sess-does-not-exist", agent_id="primary001")
    assert attr == "src=unresolved"


# ---------------------------------------------------------------------------
# (g) UNKNOWN-model
# ---------------------------------------------------------------------------
def test_unknown_model_keeps_tok_no_usd_stderr_warning_expected(fixtures_home, capsys):
    jf = atc.resolve_by_agent_id(
        sid=FAKE_SID, agent_id="unknownmodel001",
        project_path=FAKE_PROJECT_PATH, home=fixtures_home,
    )
    assert jf is not None
    r = atc.price_agent_jsonl(jf)
    assert r["priceable"] is False
    assert r["usd"] is None
    assert r["tok"] == 300 + 50
    assert r["models"] == ["claude-sonnet-5"]

    attr = _resolve(fixtures_home, sid=FAKE_SID, agent_id="unknownmodel001")
    assert attr == f"tok={300 + 50};src=unresolved"

    # parse_session (reused by price_agent_jsonl) emits a stderr warning for
    # unknown models — EXPECT it; do NOT assert clean stderr (MIN-3).
    captured = capsys.readouterr()
    assert "unknown model 'claude-sonnet-5'" in captured.err


# ---------------------------------------------------------------------------
# (i) SYMMETRY — adapter output parses under the core parser
# ---------------------------------------------------------------------------
def test_symmetry_with_core_parse_attribution(fixtures_home):
    attr = _resolve(fixtures_home, sid=FAKE_SID, agent_id="primary001")
    parsed = parse_attribution(attr)
    assert parsed == {"usd": str(EXPECTED_USD), "tok": str(EXPECTED_TOK), "src": "nested_jsonl"}


def test_symmetry_unresolved_case(fixtures_home):
    attr = _resolve(fixtures_home, sid=FAKE_SID, agent_id="does-not-exist")
    parsed = parse_attribution(attr)
    assert parsed == {"src": "unresolved"}


# ---------------------------------------------------------------------------
# subagents_dir path-building sanity
# ---------------------------------------------------------------------------
def test_subagents_dir_builds_expected_path(fixtures_home):
    d = atc.subagents_dir(project_path=FAKE_PROJECT_PATH, sid=FAKE_SID, home=fixtures_home)
    expected = fixtures_home / ".claude" / "projects" / "-fake-project" / FAKE_SID / "subagents"
    assert d == expected
    assert d.is_dir()


# ---------------------------------------------------------------------------
# fail-open on completely bogus input (never raise)
# ---------------------------------------------------------------------------
def test_resolve_attribution_never_raises_on_bogus_input(fixtures_home):
    attr = atc.resolve_attribution(
        sid=None, agent_id=None, tool_use_id=None,
        project_path=FAKE_PROJECT_PATH, home=fixtures_home,
    )
    assert attr == "src=unresolved"


def test_resolve_by_agent_id_fail_open_on_none_sid(fixtures_home):
    # sid=None makes the path-join fail internally (TypeError) — fail-open -> None.
    jf = atc.resolve_by_agent_id(
        sid=None, agent_id="primary001",
        project_path=FAKE_PROJECT_PATH, home=fixtures_home,
    )
    assert jf is None

    attr = atc.resolve_attribution(
        sid=None, agent_id="primary001",
        project_path=FAKE_PROJECT_PATH, home=fixtures_home,
    )
    assert attr == "src=unresolved"

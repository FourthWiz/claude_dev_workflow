"""test_handoff_measure.py — fixture-only tests for handoff_measure.py
(agent-handoff-format stage 1: instrument skeleton).

All tests point the instrument at a SYNTHETIC fixture tree materialized under
<tmp_path>/.claude/projects/<hash>/<sid>/subagents/ (copied at test time from the
committed fixtures/handoff_measure/projects/ source tree) via the home= override
param — nothing here reads the developer's live ~/.claude, mirroring the established
pattern in test_agent_transcript_cost.py.

Note on fixture layout: the committed source tree under fixtures/handoff_measure/
deliberately has NO literal ".claude" path segment, because quoin/.gitignore ignores
any ".claude/" directory anywhere in the repo — a committed ".claude"-named fixture
tree would be silently invisible in a clean checkout.

Cases (letters match the design doc):
  (a) run-owned marker in the first 100 B -> detect_phase + run_owned True
  (b) marker beginning at byte 640 -> no match (600-byte window)
  (c) marker naming a non-run-owned skill -> skill_matched, not run_owned
  (d) multi-byte prefix inside 600 chars but past 600 bytes -> no match
  (e) last assistant message is a tool_use block only -> zero-byte return
  (f) no assistant message -> return_text empty, last_assistant None
  (g) one malformed JSON line among good lines -> tolerated
  (h) assistant content list of thinking-block plus text-block -> only text counted
  (i) usage with output_tokens and thinking_tokens present
  (j) usage without either
  (o) a transcript path the enumerator yields but that does not exist when opened
      -> skipped, skipped_unreadable incremented, capture completes
  (k) final entry is a thinking-only block -> zero-byte return, distinct cause
      from case (e) (tool_use-only)
  (l) stop_reason: null partial carrying multi-kilobyte text against a
      single-digit output_tokens -> excluded from the token cross-check but
      counted in bytes
  (m) stop_reason: "tool_use" -> excluded from the token cross-check, tallied
      under its own excluded-reason bucket
  (n) stop_reason: "stop_sequence" -> excluded from the token cross-check,
      tallied under its own excluded-reason bucket
"""

import ast
import pathlib
import re
import shutil
import sys

import pytest

SCRIPTS_DIR = pathlib.Path(__file__).parent.parent.parent / "scripts"  # quoin/quoin/scripts/
FIXTURES_SRC_PROJECTS = pathlib.Path(__file__).parent / "fixtures" / "handoff_measure" / "projects"
BASELINE_SNAPSHOT_PATH = (
    pathlib.Path(__file__).parent / "fixtures" / "handoff_measure" / "baseline"
    / "handoff-baseline-snapshot.json"
)

# Ordinal-label id shape stable_id produces: a bare "project-N" (no session
# component), or the full "project-N/session-M/spawn-K".
_ORDINAL_ID_SHAPE = re.compile(r"^project-\d+(/session-\d+/spawn-\d+)?$")
_UUID_SHAPE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)

sys.path.insert(0, str(SCRIPTS_DIR))
import handoff_measure as hm  # noqa: E402


@pytest.fixture(scope="module")
def fixtures_home(tmp_path_factory):
    """Materialize the committed fixture tree under <tmp>/.claude/projects/...
    so iter_transcripts/capture_corpus (which hardcode the ".claude" path
    segment) can read it via home=<this fixture>, without any ".claude"-named
    path ever being committed to the repo (see module docstring)."""
    home = tmp_path_factory.mktemp("handoff_measure_home")
    dest = home / ".claude" / "projects"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(FIXTURES_SRC_PROJECTS, dest)
    return home


def _record_for(home, sid_substring):
    corpus = hm.capture_corpus(home)
    matches = [r for r in corpus["records"] if sid_substring in r["path"]]
    assert len(matches) == 1, f"expected exactly one record matching {sid_substring!r}, got {matches}"
    return matches[0]


# ---------------------------------------------------------------------------
# (a) run-owned marker in the first 100 B
# ---------------------------------------------------------------------------
def test_case_a_run_owned_marker_detected(fixtures_home):
    record = _record_for(fixtures_home, "sid-case-a")
    assert record["phase"] == "implement"
    assert record["run_owned"] is True


# ---------------------------------------------------------------------------
# (b) marker beginning at byte 640 -> no match
# ---------------------------------------------------------------------------
def test_case_b_marker_past_byte_window_not_detected(fixtures_home):
    record = _record_for(fixtures_home, "sid-case-b")
    assert record["phase"] is None
    assert record["run_owned"] is False


# ---------------------------------------------------------------------------
# (c) marker naming a non-run-owned skill -> skill_matched, not run_owned
# ---------------------------------------------------------------------------
def test_case_c_non_run_owned_skill_matched_but_not_run_owned(fixtures_home):
    record = _record_for(fixtures_home, "sid-case-c")
    assert record["phase"] == "gate"
    assert record["run_owned"] is False
    assert record["phase"] not in hm.RUN_OWNED_PHASES


# ---------------------------------------------------------------------------
# (d) multi-byte prefix: inside 600 chars, past 600 bytes -> no match
# ---------------------------------------------------------------------------
def test_case_d_multibyte_prefix_past_byte_window_not_detected(fixtures_home):
    record = _record_for(fixtures_home, "sid-case-d")
    assert record["phase"] is None
    assert record["run_owned"] is False


def test_detect_phase_is_byte_windowed_not_char_windowed():
    # Direct unit pin, independent of the fixture tree: 350 two-byte chars
    # is 350 chars (< 600) but 700 bytes (> 600), so the marker right after
    # must NOT be found.
    padded = ("é" * 350) + "Invoke the /implement skill"
    assert hm.detect_phase(padded) is None
    # Sanity: the same marker with no padding at all IS found.
    assert hm.detect_phase("Invoke the /implement skill") == "implement"


# ---------------------------------------------------------------------------
# (e) last assistant message is a tool_use block only -> zero-byte return
# ---------------------------------------------------------------------------
def test_case_e_tool_use_only_return_is_zero_byte(fixtures_home):
    record = _record_for(fixtures_home, "sid-case-e")
    assert record["return_text"] == ""
    assert record["last_assistant"] is not None  # the row exists, just carries no text


# ---------------------------------------------------------------------------
# (f) no assistant message at all
# ---------------------------------------------------------------------------
def test_case_f_no_assistant_message(fixtures_home):
    record = _record_for(fixtures_home, "sid-case-f")
    assert record["return_text"] == ""
    assert record["last_assistant"] is None


# ---------------------------------------------------------------------------
# (g) one malformed JSON line among good lines -> tolerated
# ---------------------------------------------------------------------------
def test_case_g_malformed_line_tolerated(fixtures_home):
    record = _record_for(fixtures_home, "sid-case-g")
    assert record["dispatch_text"].startswith("Invoke the /implement skill")
    assert "Done despite one bad line." in record["return_text"]


# ---------------------------------------------------------------------------
# (h) thinking-block plus text-block -> only text counted
# ---------------------------------------------------------------------------
def test_case_h_thinking_block_excluded_from_return_text(fixtures_home):
    record = _record_for(fixtures_home, "sid-case-h")
    assert record["return_text"] == "Only this text counts."
    assert "internal reasoning not counted" not in record["return_text"]


def test_payload_text_direct_block_filtering():
    content = [
        {"type": "thinking", "thinking": "not counted"},
        {"type": "text", "text": "a"},
        {"type": "tool_use", "id": "x", "name": "Bash", "input": {}},
        {"type": "text", "text": "b"},
    ]
    assert hm.payload_text(content) == "ab"
    assert hm.payload_text("bare string") == "bare string"
    assert hm.payload_text(None) == ""
    assert hm.payload_text([]) == ""


# ---------------------------------------------------------------------------
# (i) usage with output_tokens and thinking_tokens present
# (j) usage without either
# ---------------------------------------------------------------------------
def test_case_i_usage_with_thinking_tokens_present(fixtures_home):
    record = _record_for(fixtures_home, "sid-case-i")
    usage = record["last_assistant"]["message"]["usage"]
    assert usage["output_tokens"] == 15
    assert usage["output_tokens_details"]["thinking_tokens"] == 5


def test_case_j_usage_without_output_tokens_or_thinking(fixtures_home):
    record = _record_for(fixtures_home, "sid-case-j")
    usage = record["last_assistant"]["message"]["usage"]
    assert "output_tokens" not in usage
    assert "output_tokens_details" not in usage


# ---------------------------------------------------------------------------
# (o) a transcript deleted between glob and open -> skipped, counted, no raise
# ---------------------------------------------------------------------------
def test_case_o_transcript_deleted_between_glob_and_open(tmp_path):
    home = tmp_path / "deleted_home"
    dest = home / ".claude" / "projects"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(FIXTURES_SRC_PROJECTS, dest)

    # Delete one fixture transcript AFTER the tree is materialized but keep
    # its parent dirs, so iter_transcripts' glob would have yielded it had
    # this run started a moment earlier — simulating the live corpus's
    # documented volatility (round-3 re-derivation: a transcript already
    # gone by the time it was opened).
    victim = dest / "-fake-project" / "sid-case-a" / "subagents" / "agent-case-a.jsonl"
    assert victim.exists()

    original_extract = hm.extract_payloads

    def flaky_extract(path):
        if path == victim:
            raise FileNotFoundError(path)
        return original_extract(path)

    try:
        hm.extract_payloads = flaky_extract
        corpus = hm.capture_corpus(home)
    finally:
        hm.extract_payloads = original_extract

    assert corpus["skipped_unreadable"] == 1
    assert corpus["transcripts"] == corpus["parsed"] + 1
    # capture completed rather than raising, and every other fixture still parsed
    assert corpus["parsed"] >= 9


# ---------------------------------------------------------------------------
# (k) final entry is a thinking-only block -> zero-byte return, distinct
#     cause from case (e) (tool_use-only)
# ---------------------------------------------------------------------------
def test_case_k_thinking_only_return_is_zero_byte(fixtures_home):
    record = _record_for(fixtures_home, "sid-case-k")
    assert record["return_text"] == ""
    content = record["last_assistant"]["message"]["content"]
    block_types = {b["type"] for b in content}
    assert block_types == {"thinking"}  # distinct cause from case (e)'s tool_use-only


# ---------------------------------------------------------------------------
# (l) stop_reason: null, multi-KB text against single-digit output_tokens
#     -> excluded from the token cross-check but counted in bytes
# ---------------------------------------------------------------------------
def test_case_l_null_stop_reason_streaming_partial(fixtures_home):
    record = _record_for(fixtures_home, "sid-case-l")
    assert len(record["return_text"].encode("utf-8")) > 1024
    usage = record["last_assistant"]["message"]["usage"]
    assert usage["output_tokens"] < 10
    assert record["last_assistant"]["message"]["stop_reason"] is None
    tv = hm.token_validity(record)
    assert tv["presence"] is True
    assert tv["validity"] is False  # gated OUT of the token cross-check
    assert hm.return_bytes(record) > 1024  # but counted in bytes


# ---------------------------------------------------------------------------
# (m) stop_reason: "tool_use" -> excluded, own excluded-reason tally
# ---------------------------------------------------------------------------
def test_case_m_tool_use_stop_reason_excluded(fixtures_home):
    record = _record_for(fixtures_home, "sid-case-m")
    tv = hm.token_validity(record)
    assert tv["stop_reason"] == "tool_use"
    assert tv["validity"] is False
    assert record["return_text"] != ""  # has text, unlike case (e)


# ---------------------------------------------------------------------------
# (n) stop_reason: "stop_sequence" -> excluded, own excluded-reason tally
# ---------------------------------------------------------------------------
def test_case_n_stop_sequence_stop_reason_excluded(fixtures_home):
    record = _record_for(fixtures_home, "sid-case-n")
    tv = hm.token_validity(record)
    assert tv["stop_reason"] == "stop_sequence"
    assert tv["validity"] is False
    assert record["return_text"] != ""


def test_cases_m_and_n_land_in_distinct_excluded_buckets(fixtures_home):
    corpus = hm.capture_corpus(fixtures_home)
    m = [r for r in corpus["records"] if "sid-case-m" in r["path"]][0]
    n = [r for r in corpus["records"] if "sid-case-n" in r["path"]][0]
    l = [r for r in corpus["records"] if "sid-case-l" in r["path"]][0]
    result = hm.token_cross_check([m, n, l])
    assert result["excluded_by_stop_reason"] == {"tool_use": 1, "stop_sequence": 1, None: 1}
    assert result["validity_fraction"] == 0.0


# ---------------------------------------------------------------------------
# nearest_rank_percentile
# ---------------------------------------------------------------------------
def test_nearest_rank_percentile_basic():
    xs = [10, 20, 30, 40, 50]
    assert hm.nearest_rank_percentile(xs, 0.50) == 30
    assert hm.nearest_rank_percentile(xs, 0.90) == 50
    assert hm.nearest_rank_percentile(xs, 0.10) == 10


def test_nearest_rank_percentile_empty_returns_none():
    assert hm.nearest_rank_percentile([], 0.50) is None


def test_nearest_rank_percentile_unsorted_input_is_sorted_first():
    assert hm.nearest_rank_percentile([50, 10, 30, 20, 40], 0.50) == 30


# ---------------------------------------------------------------------------
# channel_stats — per-phase and overall dispatch/return byte stats
# ---------------------------------------------------------------------------
def _fake_record(phase, dispatch, return_):
    return {"phase": phase, "dispatch_text": dispatch, "return_text": return_}


def test_channel_stats_p99_only_on_overall_never_per_phase():
    records = [_fake_record("implement", "d" * 10, "r" * 10) for _ in range(3)]
    stats = hm.channel_stats(records)
    assert stats["overall"]["dispatch"]["p99"] is not None
    assert stats["per_phase"]["implement"]["dispatch"]["p99"] is None


def test_channel_stats_small_group_reports_max_not_percentile():
    # n=3 < _MIN_N_FOR_PERCENTILE(10): p50/p90 withheld, max reported instead.
    records = [_fake_record("gate", "d" * n, "r" * (n * 2)) for n in (1, 2, 3)]
    stats = hm.channel_stats(records)
    dispatch_stats = stats["per_phase"]["gate"]["dispatch"]
    assert dispatch_stats["p50"] is None
    assert dispatch_stats["p90"] is None
    assert dispatch_stats["reported_as_max"] is True
    assert dispatch_stats["max"] == 3


def test_channel_stats_ratio_and_divisor_present():
    records = [_fake_record("implement", "d" * 10, "r" * 20)] * 12
    stats = hm.channel_stats(records)
    assert stats["overall"]["ratio"]["mean"] == 2.0
    assert stats["byte_divisor"] == hm.BYTES_PER_TOKEN_DIVISOR
    assert "not evidence it fits this use" in stats["byte_divisor_note"]


# ---------------------------------------------------------------------------
# token_cross_check — gating, three fractions, pooled ratio
# ---------------------------------------------------------------------------
def test_token_cross_check_gates_on_stop_reason_end_turn():
    admitted = {
        "return_text": "x" * 20,
        "last_assistant": {"message": {"stop_reason": "end_turn",
                                        "usage": {"output_tokens": 10}}},
    }
    excluded = {
        "return_text": "y" * 2000,
        "last_assistant": {"message": {"stop_reason": "tool_use",
                                        "usage": {"output_tokens": 1}}},
    }
    result = hm.token_cross_check([admitted, excluded])
    assert result["validity_fraction"] == 0.5
    assert result["presence_fraction"] == 1.0
    # gated pooled ratio uses ONLY the admitted row: 20 / 10 = 2.0
    assert result["gated"]["pooled_ratio"] == 2.0
    # ungated pooled ratio uses BOTH rows: (20 + 2000) / (10 + 1)
    assert result["ungated"]["pooled_ratio"] == pytest.approx(2020 / 11)


def test_token_cross_check_missing_thinking_is_zero_not_dropped():
    row_with_thinking = {
        "return_text": "x" * 10,
        "last_assistant": {"message": {
            "stop_reason": "end_turn",
            "usage": {"output_tokens": 5,
                      "output_tokens_details": {"thinking_tokens": 5}},
        }},
    }
    row_missing_thinking = {
        "return_text": "y" * 10,
        "last_assistant": {"message": {
            "stop_reason": "end_turn",
            "usage": {"output_tokens": 5},  # no output_tokens_details at all
        }},
    }
    result = hm.token_cross_check([row_with_thinking, row_missing_thinking])
    assert result["thinking_coverage_fraction"] == 0.5
    # missing-means-zero: row_missing_thinking contributes output_tokens (5)
    # unadjusted, NOT dropped from the population.
    # thinking-adjusted denominator: (5+5) + (5+0) = 15; bytes: 10+10 = 20
    assert result["gated"]["pooled_ratio_thinking_adjusted"] == pytest.approx(20 / 15)


def test_token_cross_check_reports_mean_and_median_alongside_pooled():
    rows = [
        {"return_text": "x" * b,
         "last_assistant": {"message": {"stop_reason": "end_turn",
                                         "usage": {"output_tokens": t}}}}
        for b, t in [(10, 5), (20, 5), (30, 5)]
    ]
    result = hm.token_cross_check(rows)
    # per-row ratios: 2.0, 4.0, 6.0 -> mean 4.0, median (nearest-rank) 4.0
    assert result["gated"]["mean_of_row_ratios"] == pytest.approx(4.0)
    assert result["gated"]["median_of_row_ratios"] == pytest.approx(4.0)
    # pooled: (10+20+30) / (5+5+5) = 4.0 too, here, but computed independently
    assert result["gated"]["pooled_ratio"] == pytest.approx(4.0)


def test_token_cross_check_empty_input_does_not_raise():
    result = hm.token_cross_check([])
    assert result["n"] == 0
    assert result["presence_fraction"] is None
    assert result["gated"]["pooled_ratio"] is None


# Mutation proof for the two stop_reason-gating mutations (drop the
# stop_reason gate; invert the gate) is run directly against
# handoff_measure.py's source and pins on test_token_cross_check_gates_on_
# stop_reason_end_turn above.


# ---------------------------------------------------------------------------
# iter_transcripts: home is a required parameter, no module-level constant root
# ---------------------------------------------------------------------------
def test_iter_transcripts_requires_home_param(fixtures_home):
    paths = list(hm.iter_transcripts(fixtures_home))
    assert len(paths) == 15  # 14 cases (a)-(n) + sid-joint's subagent transcript
    assert all(p.name.startswith("agent-case-") or p.name == "agent-joint.jsonl" for p in paths)


def test_iter_transcripts_empty_when_no_claude_dir(tmp_path):
    assert list(hm.iter_transcripts(tmp_path / "nothing_here")) == []


# ---------------------------------------------------------------------------
# CLI smoke: --help works with no filesystem access, exit 0
# ---------------------------------------------------------------------------
def test_cli_help_exits_zero(capsys):
    with pytest.raises(SystemExit) as exc_info:
        hm.main(["--help"])
    assert exc_info.value.code == 0


def test_cli_main_reports_corpus_summary(fixtures_home, capsys):
    exit_code = hm.main(["--home", str(fixtures_home)])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "corpus_captured_at=" in captured.out
    assert "skipped_unreadable=" in captured.out
    assert "run_owned=" in captured.out


def test_cli_main_refuses_measurement_on_empty_corpus(tmp_path, capsys):
    exit_code = hm.main(["--home", str(tmp_path / "empty")])
    assert exit_code == 1


# ---------------------------------------------------------------------------
# Channel three — orchestrator-side artifact re-read bytes
# ---------------------------------------------------------------------------

def _write_parent_transcript(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(__import__("json").dumps(row) + "\n")


def _tool_use_row(tid, name, tool_input):
    return {"message": {"role": "assistant", "content": [
        {"type": "tool_use", "id": tid, "name": name, "input": tool_input},
    ]}}


def _tool_result_row(tid, text):
    return {"message": {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": tid, "content": [{"type": "text", "text": text}]},
    ]}}


def test_resolve_parent_transcript_path():
    sub = pathlib.Path("/h/.claude/projects/hash1/sid-abc/subagents/agent-x.jsonl")
    assert hm.resolve_parent_transcript_path(sub) == pathlib.Path(
        "/h/.claude/projects/hash1/sid-abc.jsonl")


def test_channel_three_classifies_3a_and_3b(tmp_path):
    p = tmp_path / "parent.jsonl"
    rows = [
        _tool_use_row("t1", "Read", {"file_path": "/x/.workflow_artifacts/plan.md"}),
        _tool_result_row("t1", "plan body"),
        _tool_use_row("t2", "Bash", {"command": "cat .workflow_artifacts/foo.md"}),
        _tool_result_row("t2", "foo body 12345"),
        _tool_use_row("t3", "Read", {"file_path": "/x/other/file.py"}),
        _tool_result_row("t3", "unrelated read"),
    ]
    _write_parent_transcript(p, rows)
    result = hm.channel_three_for_session(p)
    assert result["sub_a_calls"] == 1
    assert result["sub_a_bytes"] == len(b"plan body")
    assert result["sub_b_calls"] == 1
    assert result["sub_b_bytes"] == len(b"foo body 12345")


def test_channel_three_wrong_result_key_contributes_zero(tmp_path):
    p = tmp_path / "parent.jsonl"
    rows = [
        _tool_use_row("t1", "Read", {"file_path": ".workflow_artifacts/x.md"}),
        {"message": {"role": "user", "content": [
            {"type": "tool_result", "use_id": "t1", "content": [{"type": "text", "text": "ghost"}]},
        ]}},
    ]
    _write_parent_transcript(p, rows)
    result = hm.channel_three_for_session(p)
    assert result["sub_a_calls"] == 0
    assert result["sub_a_bytes"] == 0


def test_channel_three_per_boundary_attribution_and_residual(tmp_path):
    p = tmp_path / "parent.jsonl"
    rows = [
        # before any Agent return -> residual
        _tool_use_row("r0", "Read", {"file_path": ".workflow_artifacts/pre.md"}),
        _tool_result_row("r0", "pre"),
        _tool_use_row("a1", "Agent", {}),
        _tool_result_row("a1", "spawn1 return"),
        _tool_use_row("r1", "Read", {"file_path": ".workflow_artifacts/mid.md"}),
        _tool_result_row("r1", "mid-body"),
        _tool_use_row("a2", "Agent", {}),
        _tool_result_row("a2", "spawn2 return"),
        # after the last run-owned boundary -> residual
        _tool_use_row("r2", "Read", {"file_path": ".workflow_artifacts/post.md"}),
        _tool_result_row("r2", "post"),
    ]
    _write_parent_transcript(p, rows)
    result = hm.channel_three_for_session(p, run_owned_tool_use_ids={"a1", "a2"})
    assert result["residual_bytes"] == len(b"pre") + len(b"post")
    assert result["residual_calls"] == 2
    assert result["per_boundary"] == {"a1": {"bytes": len(b"mid-body"), "calls": 1}}
    assert result["agent_return_bytes"] == len(b"spawn1 return") + len(b"spawn2 return")
    assert result["agent_return_calls"] == 2


def test_channel_three_non_run_owned_agent_does_not_reset_boundary(tmp_path):
    p = tmp_path / "parent.jsonl"
    rows = [
        _tool_use_row("a1", "Agent", {}),
        _tool_result_row("a1", "run-owned spawn"),
        _tool_use_row("g1", "Agent", {}),
        _tool_result_row("g1", "gate spawn, not run-owned"),
        _tool_use_row("r1", "Bash", {"command": "ls .workflow_artifacts"}),
        _tool_result_row("r1", "listing"),
    ]
    _write_parent_transcript(p, rows)
    result = hm.channel_three_for_session(p, run_owned_tool_use_ids={"a1"})
    # r1 comes after g1's Agent return, but g1 isn't a run-owned boundary, and
    # r1's index is still <= the last run-owned boundary's index... actually
    # a1 IS the last run-owned boundary and r1 comes after it positionally,
    # so per the "after the last" rule this lands in residual.
    assert result["per_boundary"] == {}
    assert result["residual_bytes"] == len(b"listing")


def test_channel_three_stats_reports_byte_and_event_share(tmp_path):
    p1 = tmp_path / "s1.jsonl"
    p2 = tmp_path / "s2.jsonl"
    _write_parent_transcript(p1, [
        _tool_use_row("t1", "Read", {"file_path": ".workflow_artifacts/a.md"}),
        _tool_result_row("t1", "x" * 100),
    ])
    _write_parent_transcript(p2, [
        _tool_use_row("t2", "Bash", {"command": "cat .workflow_artifacts/b.md"}),
        _tool_result_row("t2", "y" * 20),
        _tool_use_row("t3", "Bash", {"command": "cat .workflow_artifacts/c.md"}),
        _tool_result_row("t3", "y" * 30),
    ])
    sessions = [hm.channel_three_for_session(p1), hm.channel_three_for_session(p2)]
    stats = hm.channel_three_stats(sessions)
    assert stats["sub_a_bytes"] == 100
    assert stats["sub_b_bytes"] == 50
    assert stats["byte_share_3a"] == pytest.approx(100 / 150)
    assert stats["event_share_3a"] == pytest.approx(1 / 3)
    assert stats["sub_b_avg_bytes_per_call"] == pytest.approx(25.0)


def test_channel_three_stats_per_session_distribution(tmp_path):
    paths = [tmp_path / f"s{i}.jsonl" for i in range(3)]
    sizes = [0, 10, 20]
    for path, size in zip(paths, sizes):
        rows = []
        if size:
            rows = [
                _tool_use_row("t", "Read", {"file_path": ".workflow_artifacts/f.md"}),
                _tool_result_row("t", "x" * size),
            ]
        _write_parent_transcript(path, rows)
    sessions = [hm.channel_three_for_session(p) for p in paths]
    stats = hm.channel_three_stats(sessions)
    dist = stats["sub_a_per_session"]
    assert dist["values_ordered"] == [0, 10, 20]
    assert dist["zero_count"] == 1
    assert dist["max"] == 20
    assert dist["mean"] == pytest.approx(10.0)


# ---------------------------------------------------------------------------
# Snapshot mode — the reproducibility contract
# ---------------------------------------------------------------------------

def test_stable_id_opaque_labels_every_path_component():
    # The project directory, the parent session id and the subagent
    # transcript's own filename must never carry a real name/UUID into a
    # committed snapshot — every one of the three is replaced by an
    # opaque ordinal label, not left as the raw sanitized path/UUID.
    home = pathlib.Path("/h")
    path = home / ".claude" / "projects" / "hash1" / "sid-abc" / "subagents" / "agent-x.jsonl"
    corpus = {"records": [{"path": path}]}
    maps = hm._corpus_label_maps(corpus, home)
    result = hm.stable_id(path, home, *maps)
    assert "hash1" not in result
    assert "sid-abc" not in result
    assert "agent-x" not in result
    project_label, session_label, spawn_label = result.split("/")
    assert project_label.startswith("project-")
    assert session_label.startswith("session-")
    assert spawn_label.startswith("spawn-")


def test_stable_id_labels_are_stable_and_distinguishing():
    home = pathlib.Path("/h")
    path_a1 = home / ".claude" / "projects" / "hash1" / "sid-abc" / "subagents" / "agent-x.jsonl"
    path_a2 = home / ".claude" / "projects" / "hash1" / "sid-def" / "subagents" / "agent-y.jsonl"
    path_b = home / ".claude" / "projects" / "hash2" / "sid-abc" / "subagents" / "agent-x.jsonl"
    corpus = {"records": [{"path": p} for p in (path_a1, path_a2, path_b)]}
    maps = hm._corpus_label_maps(corpus, home)
    label_a1 = hm.stable_id(path_a1, home, *maps).split("/", 1)[0]
    label_a2 = hm.stable_id(path_a2, home, *maps).split("/", 1)[0]
    label_b = hm.stable_id(path_b, home, *maps).split("/", 1)[0]
    # same project dir -> same label (stable across records / re-captures)
    assert label_a1 == label_a2
    # different project dir -> different label (still distinguishes projects)
    assert label_a1 != label_b
    # different sessions under the same project get different session labels
    id_a1 = hm.stable_id(path_a1, home, *maps)
    id_a2 = hm.stable_id(path_a2, home, *maps)
    assert id_a1.split("/")[1] != id_a2.split("/")[1]
    # re-running the map build over the SAME record set is deterministic
    maps_again = hm._corpus_label_maps(corpus, home)
    assert hm.stable_id(path_a1, home, *maps_again) == id_a1


def test_build_snapshot_record_carries_no_payload_text(fixtures_home):
    record = _record_for(fixtures_home, "sid-case-a")
    maps = hm._corpus_label_maps({"records": [record]}, fixtures_home)
    snap = hm.build_snapshot_record(record, fixtures_home, *maps)
    assert snap["dispatch_bytes"] == hm.dispatch_bytes(record)
    assert snap["return_bytes"] == hm.return_bytes(record)
    assert snap["phase"] == "implement"
    assert snap["run_owned"] is True
    # the real parent session UUID is not carried as a field at all — it
    # has no snapshot consumer, and carrying it would let a holder of this
    # project's own cost-ledger files join back to the real session
    assert "parent_session_id" not in snap
    assert "sid-case-a" not in str(snap)
    # never payload text
    dumped = str(snap)
    assert record["dispatch_text"] not in dumped
    assert record["return_text"] not in dumped
    # sentinel_bucket is filled for real; channel_three/growth_bound stay
    # explicit PARTIAL placeholders (see module note) rather than omitted.
    assert snap["sentinel_bucket"] == hm.sentinel_bucket(record.get("dispatch_text", ""))
    assert snap["channel_three"] is None
    assert snap["growth_bound"] is None


def test_sentinel_bucket_classifies_known_markers():
    assert hm.sentinel_bucket("") == "none"
    assert hm.sentinel_bucket("[no-interactive] hi") == "no_interactive"
    assert hm.sentinel_bucket("[quoin-onbehalf] [no-interactive] [no-redispatch]") == \
        "on_behalf+no_interactive+no_redispatch"


def test_build_snapshot_sorts_records_by_stable_id(fixtures_home):
    corpus = hm.capture_corpus(fixtures_home)
    snapshot = hm.build_snapshot(corpus, fixtures_home)
    ids = [r["id"] for r in snapshot["records"]]
    assert ids == sorted(ids)
    assert snapshot["schema_version"] == hm.SNAPSHOT_SCHEMA_VERSION
    assert snapshot["transcripts"] == corpus["transcripts"]
    assert len(snapshot["records"]) == len(corpus["records"])


def test_write_then_load_snapshot_round_trips(tmp_path, fixtures_home):
    corpus = hm.capture_corpus(fixtures_home)
    snapshot = hm.build_snapshot(corpus, fixtures_home)
    out = tmp_path / "snap.json"
    hm.write_snapshot(out, snapshot)
    loaded = hm.load_snapshot(out)
    assert loaded == snapshot


# ---------------------------------------------------------------------------
# load_snapshot schema/key validation, and the snapshot-write block's own
# try/except in main() (distinct from the corpus-capture try/except).
# ---------------------------------------------------------------------------
def test_load_snapshot_rejects_unsupported_schema_version(tmp_path):
    bad = {
        "schema_version": 99,
        "transcripts": 0, "parsed": 0, "skipped_unreadable": 0,
        "skill_matched": 0, "run_owned": 0, "records": [],
    }
    path = tmp_path / "bad-version.json"
    hm.write_snapshot(path, bad)
    with pytest.raises(ValueError, match="schema_version"):
        hm.load_snapshot(path)


def test_load_snapshot_rejects_missing_required_key(tmp_path):
    missing_records = {
        "schema_version": hm.SNAPSHOT_SCHEMA_VERSION,
        "transcripts": 0, "parsed": 0, "skipped_unreadable": 0,
        "skill_matched": 0, "run_owned": 0,
        # "records" omitted
    }
    path = tmp_path / "missing-key.json"
    hm.write_snapshot(path, missing_records)
    with pytest.raises(ValueError, match="records"):
        hm.load_snapshot(path)


def test_from_snapshot_cli_exits_2_on_unsupported_schema_version(tmp_path, capsys):
    bad = {
        "schema_version": 99,
        "transcripts": 0, "parsed": 0, "skipped_unreadable": 0,
        "skill_matched": 0, "run_owned": 0, "records": [],
    }
    path = tmp_path / "bad-version.json"
    hm.write_snapshot(path, bad)
    exit_code = hm.main(["--from-snapshot", str(path)])
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "handoff_measure: invocation error:" in captured.err
    assert "Traceback" not in captured.err


def test_from_snapshot_cli_exits_2_on_missing_required_key(tmp_path, capsys):
    missing_records = {
        "schema_version": hm.SNAPSHOT_SCHEMA_VERSION,
        "transcripts": 0, "parsed": 0, "skipped_unreadable": 0,
        "skill_matched": 0, "run_owned": 0,
    }
    path = tmp_path / "missing-key.json"
    hm.write_snapshot(path, missing_records)
    exit_code = hm.main(["--from-snapshot", str(path)])
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "handoff_measure: invocation error:" in captured.err
    assert "Traceback" not in captured.err


def test_snapshot_write_block_maps_relative_to_failure_to_exit_2(
    tmp_path, fixtures_home, monkeypatch, capsys
):
    """A record path outside `home` fails `relative_to` inside
    `build_snapshot` (via `_corpus_label_maps`/`stable_id`) — the
    snapshot-write try/except must map that to exit 2 with the
    snapshot-side message, distinct from the corpus-capture try/except's
    message, and never a raw traceback."""
    bad_record = dict(_record_for(fixtures_home, "sid-case-a"))
    bad_record["path"] = str(tmp_path / "outside-home.jsonl")
    bad_corpus = {
        "transcripts": 1, "parsed": 1, "skipped_unreadable": 0,
        "skill_matched": 1, "run_owned": 1, "records": [bad_record],
    }
    monkeypatch.setattr(hm, "capture_corpus", lambda home, project_filter=None: bad_corpus)
    snap_path = tmp_path / "snap.json"
    exit_code = hm.main(["--home", str(fixtures_home), "--snapshot", str(snap_path)])
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "handoff_measure: invocation error writing snapshot:" in captured.err
    assert "handoff_measure: invocation error: " not in captured.err
    assert "Traceback" not in captured.err
    assert not snap_path.exists()


def test_write_snapshot_is_byte_identical_across_two_writes(tmp_path, fixtures_home):
    corpus = hm.capture_corpus(fixtures_home)
    snapshot = hm.build_snapshot(corpus, fixtures_home)
    out1 = tmp_path / "snap1.json"
    out2 = tmp_path / "snap2.json"
    hm.write_snapshot(out1, snapshot)
    hm.write_snapshot(out2, snapshot)
    assert out1.read_bytes() == out2.read_bytes()


def test_from_snapshot_replay_is_byte_identical_across_two_runs(tmp_path, fixtures_home, capsys):
    corpus = hm.capture_corpus(fixtures_home)
    snapshot = hm.build_snapshot(corpus, fixtures_home)
    snap_path = tmp_path / "snap.json"
    hm.write_snapshot(snap_path, snapshot)

    exit_code_1 = hm.main(["--from-snapshot", str(snap_path)])
    out_1 = capsys.readouterr().out
    exit_code_2 = hm.main(["--from-snapshot", str(snap_path)])
    out_2 = capsys.readouterr().out

    assert exit_code_1 == exit_code_2 == 0
    assert out_1 == out_2


def test_channel_stats_from_snapshot_matches_live_channel_stats(fixtures_home):
    corpus = hm.capture_corpus(fixtures_home)
    snapshot = hm.build_snapshot(corpus, fixtures_home)
    live_stats = hm.channel_stats(corpus["records"])
    snap_stats = hm.channel_stats_from_snapshot(snapshot)
    assert snap_stats == live_stats


def test_token_cross_check_from_snapshot_matches_live_token_cross_check(fixtures_home):
    corpus = hm.capture_corpus(fixtures_home)
    run_owned_live = [r for r in corpus["records"] if r["run_owned"]]
    snapshot = hm.build_snapshot(corpus, fixtures_home)
    live_result = hm.token_cross_check(run_owned_live)
    snap_result = hm.token_cross_check_from_snapshot(snapshot)
    assert snap_result == live_result


def test_from_snapshot_cli_reports_header_without_filesystem_access(tmp_path, fixtures_home, capsys):
    corpus = hm.capture_corpus(fixtures_home)
    snapshot = hm.build_snapshot(corpus, fixtures_home)
    snap_path = tmp_path / "snap.json"
    hm.write_snapshot(snap_path, snapshot)

    exit_code = hm.main(["--from-snapshot", str(snap_path)])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "snapshot_loaded=" in captured.out
    assert f"transcripts={corpus['transcripts']}" in captured.out
    assert f"run_owned={corpus['run_owned']}" in captured.out

    # --from-snapshot must actually recompute and print statistics, not just
    # echo the header counters. Channel one/two is reported over the
    # run-owned population (the baseline's "n = N run-owned" convention), the
    # same population main()'s live path uses.
    run_owned_live = [r for r in corpus["records"] if r.get("run_owned")]
    live_stats = hm.channel_stats(run_owned_live)
    live_tcc = hm.token_cross_check(run_owned_live)
    lines = captured.out.splitlines()

    def _kv_line(prefix):
        for line in lines:
            if line.startswith(prefix):
                return dict(part.split("=", 1) for part in line.split(" ") if "=" in part)
        raise AssertionError(f"no printed line starts with {prefix!r}:\n{captured.out}")

    # Every printed dispatch/return/ratio figure is pinned to its own
    # statistic, not merely detected by a substring marker — a printer
    # defect that swaps two slots (e.g. p50 printed where p90 belongs)
    # must fail this test.
    for label in ("dispatch", "return", "ratio"):
        live = live_stats["overall"][label]
        printed = _kv_line(f"{label}: ")
        for field in ("n", "p50", "p90", "p99", "mean", "max", "reported_as_max", "convention"):
            assert printed[field] == str(live[field]), (
                f"{label}.{field}: printed {printed[field]!r} != live {live[field]!r}"
            )

    assert f"byte_divisor={live_stats['byte_divisor']}" in captured.out

    printed_tcc = _kv_line("token_cross_check: ")
    for field in ("n", "presence_fraction", "validity_fraction", "thinking_coverage_fraction"):
        assert printed_tcc[field] == str(live_tcc[field]), (
            f"token_cross_check.{field}: printed {printed_tcc[field]!r} != live {live_tcc[field]!r}"
        )

    # dict key insertion order can legitimately differ between the live
    # (glob order) and snapshot (id-sorted order) record iterations, so
    # compare parsed values rather than the raw printed string.
    excluded_line = next(
        line for line in lines if line.startswith("excluded_by_stop_reason=")
    )
    printed_excluded = ast.literal_eval(excluded_line[len("excluded_by_stop_reason="):])
    assert printed_excluded == live_tcc["excluded_by_stop_reason"]

    for population in ("gated", "ungated"):
        live_pop = live_tcc[population]
        printed_pop = _kv_line(f"{population}_pooled_ratio=")
        for field, printed_key in (
            ("pooled_ratio", f"{population}_pooled_ratio"),
            ("pooled_ratio_thinking_adjusted", f"{population}_pooled_ratio_thinking_adjusted"),
            ("mean_of_row_ratios", f"{population}_mean_of_row_ratios"),
            ("median_of_row_ratios", f"{population}_median_of_row_ratios"),
        ):
            assert printed_pop[printed_key] == str(live_pop[field]), (
                f"{printed_key}: printed {printed_pop[printed_key]!r} != live {live_pop[field]!r}"
            )


def test_from_snapshot_empty_records_refuses_measurement(tmp_path, capsys):
    empty = {
        "schema_version": hm.SNAPSHOT_SCHEMA_VERSION,
        "transcripts": 0, "parsed": 0, "skipped_unreadable": 0,
        "skill_matched": 0, "run_owned": 0, "records": [],
    }
    snap_path = tmp_path / "empty.json"
    hm.write_snapshot(snap_path, empty)
    exit_code = hm.main(["--from-snapshot", str(snap_path)])
    assert exit_code == 1


def test_cli_snapshot_flag_writes_a_loadable_snapshot(tmp_path, fixtures_home):
    snap_path = tmp_path / "written.json"
    exit_code = hm.main(["--home", str(fixtures_home), "--snapshot", str(snap_path)])
    assert exit_code == 0
    assert snap_path.exists()
    loaded = hm.load_snapshot(snap_path)
    assert loaded["run_owned"] > 0
    assert "corpus_captured_at" in loaded


def test_committed_baseline_snapshot_is_anonymized():
    """Guard the committed baseline snapshot fixture ITSELF, not a rebuilt
    copy — otherwise this large committed artifact is referenced only by
    affected_tests.py's selector row and nothing ever loads it. Written
    against the current anonymization scheme, so it fails hard against a
    pre-anonymization blob: a raw parent-session UUID, a bare absolute home
    path, or a record id that is not a pure ordinal-label shape.
    """
    raw = BASELINE_SNAPSHOT_PATH.read_text(encoding="utf-8")
    # Goes through load_snapshot's own schema/key validation (not a bare
    # json.load), so this also re-proves the fixture still satisfies it.
    snapshot = hm.load_snapshot(BASELINE_SNAPSHOT_PATH)
    assert snapshot["schema_version"] == hm.SNAPSHOT_SCHEMA_VERSION
    assert "parent_session_id" not in raw
    assert _UUID_SHAPE.search(raw) is None
    assert "/Users/" not in raw
    assert "/home/" not in raw
    assert snapshot["records"], "fixture must carry at least one record for this guard to mean anything"
    for record in snapshot["records"]:
        assert _ORDINAL_ID_SHAPE.match(record["id"]), record["id"]


# ---------------------------------------------------------------------------
# Always-on parent-side channel-three joint test, against a COMMITTED
# fixture transcript (not a synthetic tmp_path row set) — the producer
# (parent-transcript resolution + tool_use/tool_result pairing) and consumer
# (channel_three_for_session) must agree on a real file at the real resolved
# path, the shape this repo's own producer/consumer joint failures take.
# ---------------------------------------------------------------------------

_JOINT_PARENT_PATH = (
    FIXTURES_SRC_PROJECTS / "-fake-project" / "sid-joint.jsonl"
)
_JOINT_SUBAGENT_PATH = (
    FIXTURES_SRC_PROJECTS / "-fake-project" / "sid-joint" / "subagents" / "agent-joint.jsonl"
)


def test_joint_resolve_parent_transcript_path_matches_committed_fixture():
    # The real resolver, against the real committed subagent transcript path
    # — not a synthetic /h/.claude/... string.
    assert hm.resolve_parent_transcript_path(_JOINT_SUBAGENT_PATH) == _JOINT_PARENT_PATH


def test_joint_channel_three_sub_a_and_sub_b_byte_totals():
    result = hm.channel_three_for_session(_JOINT_PARENT_PATH)
    # r1 and r3 are both genuine workflow-artifacts Reads (r2 pairs to
    # nothing, see the wrong-key test below); b1 is the one Bash pair.
    assert result["sub_a_calls"] == 2
    assert result["sub_a_bytes"] == (
        len("joint plan body".encode("utf-8"))
        + len("tail read after last boundary".encode("utf-8"))
    )
    assert result["sub_b_calls"] == 1
    assert result["sub_b_bytes"] == len("grep output".encode("utf-8"))


def test_joint_channel_three_agent_return_cross_check():
    result = hm.channel_three_for_session(_JOINT_PARENT_PATH)
    assert result["agent_return_calls"] == 2
    assert result["agent_return_bytes"] == (
        len("run-owned spawn return payload for the joint test".encode("utf-8"))
        + len("second run-owned spawn return".encode("utf-8"))
    )


def test_joint_channel_three_boundary_window_attribution():
    result = hm.channel_three_for_session(
        _JOINT_PARENT_PATH, run_owned_tool_use_ids={"a1", "a2"}
    )
    # r1 and b1 land strictly between a1's return and a2's return, so both
    # attribute to a1. r3 lands after a2 — the LAST boundary — so it goes to
    # residual rather than a (nonexistent) window past the last boundary.
    # Asserted on the extractor's own per-boundary output, not a downstream
    # aggregate.
    assert result["per_boundary"] == {
        "a1": {
            "bytes": len("joint plan body".encode("utf-8")) + len("grep output".encode("utf-8")),
            "calls": 2,
        }
    }
    assert result["residual_calls"] == 1
    assert result["residual_bytes"] == len("tail read after last boundary".encode("utf-8"))


def test_joint_wrong_result_key_use_id_contributes_zero_not_absorbed():
    result = hm.channel_three_for_session(_JOINT_PARENT_PATH)
    # r2's Read is a genuine workflow-artifacts candidate, but its
    # tool_result is spelled "use_id" (not "tool_use_id") — it must NOT be
    # silently absorbed into sub_a's total. sub_a_calls is exactly 2 (r1 and
    # r3 only); if r2 were wrongly counted it would be 3.
    assert result["sub_a_calls"] == 2


def test_joint_unpaired_orphan_tool_result_is_ignored():
    # The trailing tool_result for "orphan-999" matches no tool_use anywhere
    # in the fixture and must not raise, and must not appear in any bucket
    # (already implied by the totals above staying exact, asserted directly
    # here via the raw event list).
    events = hm.iter_parent_tool_pairs(_JOINT_PARENT_PATH)
    assert all(ev["tool_use_id"] != "orphan-999" for ev in events)
    assert len(events) == 5  # a1, r1, b1, a2, r3 — r2 (wrong key) and the orphan pair to nothing


# Mutation proof, run and recorded — applied once each directly
# against handoff_measure.py's source, confirmed red, reverted. All three
# run against `-k "channel_three or joint"`; the fourth number is the count
# of tests in that filtered set that went red.
#   1. renamed iter_parent_tool_pairs' read of block.get("tool_use_id") to
#      block.get("use_id") -> RED (5): test_joint_channel_three_sub_a_and_sub_b_byte_totals,
#      test_joint_channel_three_agent_return_cross_check,
#      test_joint_channel_three_boundary_window_attribution,
#      test_joint_wrong_result_key_use_id_contributes_zero_not_absorbed,
#      test_joint_unpaired_orphan_tool_result_is_ignored — event count drops
#      to 1 (only r2, the one pair that happens to already use "use_id" as
#      its own key), so the committed fixture's five real "tool_use_id"
#      pairs vanish. Reverted; full suite green after revert.
#   2. dropped the workflow-artifacts filter from is_3a in
#      channel_three_for_session (`is_3a = name == "Read"`) -> RED (1):
#      test_channel_three_classifies_3a_and_3b, whose t3 Read of
#      "/x/other/file.py" now wrongly counts, moving sub_a_calls from 1 to
#      2. The joint fixture's own totals happened not to move (no unrelated
#      Read in it), which is why the tmp_path-based test — not the
#      committed-fixture one — is the discriminating assertion here.
#      Reverted; full suite green after revert.
#   3. collapsed the boundary-window attribution to a single fixed bucket
#      (replaced `per_boundary.setdefault(current_boundary, ...)` with a
#      constant key) -> RED (2): test_joint_channel_three_boundary_window_attribution
#      (per_boundary's key set and residual split no longer match) and
#      test_channel_three_per_boundary_attribution_and_residual (the
#      synthetic two-boundary case, which needs two distinct keys to pass).
#      Reverted; full suite green after revert.


# ---------------------------------------------------------------------------
# Opt-in live test — gated on QUOIN_HANDOFF_LIVE_CORPUS=1 and the real
# corpus existing; skips cleanly otherwise since subagent transcripts are
# not portable across machines.
# ---------------------------------------------------------------------------
import os


@pytest.mark.skipif(
    os.environ.get("QUOIN_HANDOFF_LIVE_CORPUS") != "1",
    reason="opt-in: set QUOIN_HANDOFF_LIVE_CORPUS=1 to run against the real ~/.claude corpus",
)
def test_live_corpus_smoke():
    home = pathlib.Path.home()
    corpus = hm.capture_corpus(home)
    if corpus["run_owned"] == 0:
        pytest.skip("no run-owned transcripts in the live corpus on this workstation")
    run_owned = [r for r in corpus["records"] if r["run_owned"]]
    assert any(hm.dispatch_bytes(r) > 0 and hm.return_bytes(r) > 0 for r in run_owned)
    resolvable = [
        r for r in run_owned
        if hm.resolve_parent_transcript_path(r["path"]).exists()
    ]
    assert resolvable, "expected at least one run-owned record with a resolvable parent transcript"


def test_channel_three_agent_return_cross_check(tmp_path):
    p = tmp_path / "parent.jsonl"
    rows = [
        _tool_use_row("a1", "Agent", {}),
        _tool_result_row("a1", "z" * 42),
    ]
    _write_parent_transcript(p, rows)
    result = hm.channel_three_for_session(p)
    assert result["agent_return_bytes"] == 42
    assert result["agent_return_calls"] == 1


# ---------------------------------------------------------------------------
# Re-read growth-bound estimator
#
# Deliberate deviation, recorded here rather than silently: cases (p)-(w)
# use tmp_path-generated transcripts and real on-disk files rather than the
# committed parent-session fixture tree used elsewhere in this file — every
# candidate path in these tests resolves against an actual file under
# tmp_path (which the candidate-path regex's generic /private or /tmp
# prefix matches on both macOS and Linux runners), so the resolution and
# charge-model mechanics under test are exercised exactly as they would be
# against a committed fixture, without adding nine more committed *.jsonl
# files and a selector row for each. The always-on property (no live-corpus
# gate) is preserved.
# ---------------------------------------------------------------------------

def _growth_home(tmp_path, sid="sid-growth"):
    home = tmp_path
    project_dir = home / ".claude" / "projects" / "hash-g"
    project_dir.mkdir(parents=True, exist_ok=True)
    return home, project_dir, sid


def _growth_record(project_dir, sid, spawn_name, return_text):
    sub = project_dir / sid / "subagents" / f"{spawn_name}.jsonl"
    sub.parent.mkdir(parents=True, exist_ok=True)
    sub.write_text("", encoding="utf-8")
    return {"path": str(sub), "return_text": return_text}


def _write_growth_parent(project_dir, sid, read_paths=None):
    p = project_dir / f"{sid}.jsonl"
    rows = []
    for i, fp in enumerate(read_paths or []):
        rows.append(_tool_use_row(f"rd{i}", "Read", {"file_path": fp}))
        rows.append(_tool_result_row(f"rd{i}", "x"))
    _write_parent_transcript(p, rows)
    return p


def test_growth_bound_case_p_new_candidate_contributes_its_size(tmp_path):
    home, project_dir, sid = _growth_home(tmp_path)
    target = tmp_path / "artifact-p.md"
    target.write_bytes(b"x" * 500)
    _write_growth_parent(project_dir, sid)
    record = _growth_record(project_dir, sid, "agent-p", f"see {target}")
    result = hm.growth_bound([record], home, None)
    assert result["whole_total"] == 500
    assert result["extraction_coverage"] == 1.0


def test_growth_bound_case_q_already_read_contributes_zero(tmp_path):
    home, project_dir, sid = _growth_home(tmp_path)
    target = tmp_path / "artifact-q.md"
    target.write_bytes(b"x" * 500)
    _write_growth_parent(project_dir, sid, read_paths=[str(target)])
    record = _growth_record(project_dir, sid, "agent-q", f"see {target}")
    result = hm.growth_bound([record], home, None)
    assert result["whole_total"] == 0
    # a raw candidate WAS extracted, so it still counts toward coverage —
    # a low bound must never disguise itself as low coverage.
    assert result["extraction_coverage"] == 1.0


def test_growth_bound_case_r_space_in_directory_resolves_full_path(tmp_path):
    home, project_dir, sid = _growth_home(tmp_path)
    spaced_dir = tmp_path / "My Drive"
    spaced_dir.mkdir()
    target = spaced_dir / "artifact-r.md"
    target.write_bytes(b"y" * 321)
    _write_growth_parent(project_dir, sid)
    record = _growth_record(project_dir, sid, "agent-r", f"see {target} for detail")
    result = hm.growth_bound([record], home, None)
    # A whitespace-delimited pattern would truncate at "My" and resolve to
    # nothing (the round-2 critic's failure against this workspace's own
    # "My Drive" root); the space-safe resolver must find the FULL path and
    # trim only the trailing prose.
    assert result["whole_total"] == 321
    assert result["per_spawn"][0]["resolved"][0]["path"] == str(target)


def test_growth_bound_case_s_missing_path_zero_bytes_still_counts_coverage(tmp_path):
    home, project_dir, sid = _growth_home(tmp_path)
    missing = tmp_path / "does-not-exist.md"
    _write_growth_parent(project_dir, sid)
    record = _growth_record(project_dir, sid, "agent-s", f"see {missing}")
    result = hm.growth_bound([record], home, None)
    assert result["whole_total"] == 0
    assert result["extraction_coverage"] == 1.0
    assert result["charges"] == 0


def test_growth_bound_case_t_duplicate_path_counted_once(tmp_path):
    home, project_dir, sid = _growth_home(tmp_path)
    target = tmp_path / "artifact-t.md"
    target.write_bytes(b"z" * 200)
    _write_growth_parent(project_dir, sid)
    record = _growth_record(project_dir, sid, "agent-t", f"see {target} and again {target}")
    result = hm.growth_bound([record], home, None)
    assert result["whole_total"] == 200
    assert result["charges"] == 1


def test_growth_bound_case_u_capped_model_caps_at_deleted_bytes(tmp_path):
    home, project_dir, sid = _growth_home(tmp_path)
    target = tmp_path / "artifact-u.md"
    target.write_bytes(b"q" * 5000)  # exceeds the clamp-deleted ceiling below
    _write_growth_parent(project_dir, sid)
    prefix = "small return referencing " + str(target) + " "
    return_text = prefix + "x" * max(0, 2000 - len(prefix))
    record = _growth_record(project_dir, sid, "agent-u", return_text)
    result = hm.growth_bound([record], home, None)
    deleted = result["per_spawn"][0]["deleted_bytes"]
    assert deleted < 5000  # the whole-file charge exceeds this spawn's ceiling
    assert result["whole_total"] == 5000
    assert result["per_candidate_total"] == deleted
    assert result["per_spawn_cap_total"] == deleted


def test_growth_bound_case_v_self_written_excluded_only_by_that_row(tmp_path):
    home, project_dir, sid = _growth_home(tmp_path)
    target = tmp_path / "artifact-v.md"
    target.write_bytes(b"w" * 400)
    _write_growth_parent(project_dir, sid)
    sub = project_dir / sid / "subagents" / "agent-v.jsonl"
    sub.parent.mkdir(parents=True, exist_ok=True)
    _write_parent_transcript(sub, [_tool_use_row("wr1", "Write", {"file_path": str(target)})])
    record = {"path": str(sub), "return_text": f"wrote {target}"}
    default_result = hm.growth_bound([record], home, None)
    excluded_result = hm.growth_bound([record], home, None, exclude_self_written=True)
    assert default_result["whole_total"] == 400
    assert excluded_result["whole_total"] == 0


def test_growth_bound_case_w_two_spawns_dedup_per_spawn_vs_per_session(tmp_path):
    home, project_dir, sid = _growth_home(tmp_path)
    target = tmp_path / "artifact-w.md"
    target.write_bytes(b"v" * 300)
    _write_growth_parent(project_dir, sid)
    r1 = _growth_record(project_dir, sid, "agent-w1", f"see {target}")
    r2 = _growth_record(project_dir, sid, "agent-w2", f"see {target}")
    result = hm.growth_bound([r1, r2], home, None)
    assert result["whole_total"] == 600  # charged twice, per-spawn de-duplication
    assert result["per_session_dedup_total"] == 300  # once, per-session de-duplication


def test_growth_bound_charges_vs_distinct_differ_when_two_spawns_share_a_path(tmp_path):
    home, project_dir, sid = _growth_home(tmp_path)
    target = tmp_path / "artifact-shared.md"
    target.write_bytes(b"u" * 111)
    _write_growth_parent(project_dir, sid)
    r1 = _growth_record(project_dir, sid, "agent-x1", f"see {target}")
    r2 = _growth_record(project_dir, sid, "agent-x2", f"see {target}")
    result = hm.growth_bound([r1, r2], home, None)
    assert result["charges"] == 2
    assert result["distinct"] == 1


def test_growth_bound_workflow_artifacts_only_filter_excludes_other_paths(tmp_path):
    home, project_dir, sid = _growth_home(tmp_path)
    outside = tmp_path / "artifact-outside.md"
    outside.write_bytes(b"o" * 90)
    _write_growth_parent(project_dir, sid)
    record = _growth_record(project_dir, sid, "agent-o", f"see {outside}")
    permissive = hm.growth_bound([record], home, None, path_filter="permissive")
    restricted = hm.growth_bound([record], home, None, path_filter="workflow_artifacts_only")
    assert permissive["whole_total"] == 90
    assert restricted["whole_total"] == 0


# Mutation proof, run and recorded — applied once each directly
# against handoff_measure.py's source, confirmed red, reverted:
#   1. replaced the space-safe resolver's per-token cut loop with a
#      whitespace-delimited `raw.split(" ")[0]` pattern -> RED (1):
#      test_growth_bound_case_r_space_in_directory_resolves_full_path (the
#      truncated first token "/private/.../My" is never an existing file, so
#      whole_total drops to 0 against the asserted 321). Reverted; full file
#      green after revert.
#   2. dropped the already-read filter (`if p in already_read: continue`)
#      from growth_bound's default "session" scope -> RED (1):
#      test_growth_bound_case_q_already_read_contributes_zero (whole_total
#      becomes 500, not the asserted 0). Reverted; full file green after
#      revert.
#   3. collapsed the two charge models onto the whole-file one
#      (`per_candidate_charge = whole_charge`) -> RED (1):
#      test_growth_bound_case_u_capped_model_caps_at_deleted_bytes
#      (per_candidate_total becomes 5000, not the asserted `deleted` value
#      below 5000). Reverted; full file green after revert.

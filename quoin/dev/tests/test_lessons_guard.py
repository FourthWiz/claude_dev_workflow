"""IVG-119 T-17: exit-code + fail-OPEN matrix for lessons_guard.py."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "core" / "scripts"))
import lessons_guard as lg  # noqa: E402
from lessons_guard import main, find_cross_project_duplicate  # noqa: E402


# A body with plenty of >=4-char tokens so Jaccard is meaningful.
_BODY = (
    "The bte-pricing regret notebook silently dropped rows when the pricing course "
    "aggregation ran before the currency normalization completed downstream forever."
)


def _project(tmp_path):
    """Create a project skeleton with .workflow_artifacts/memory/ and return (root, lessons_path)."""
    mem = tmp_path / ".workflow_artifacts" / "memory"
    mem.mkdir(parents=True)
    return tmp_path, mem / "lessons-learned.md"


def _write_lessons(lessons_path, slug, body):
    lessons_path.write_text(f"## 2026-06-18 — {slug}\n{body}\n", encoding="utf-8")


def _write_candidate(tmp_path, slug, body):
    c = tmp_path / "candidate.md"
    c.write_text(f"## 2026-07-22 — {slug}\n{body}\n", encoding="utf-8")
    return c


def test_foreign_verbatim_flags_exit_1(tmp_path):
    root, lessons = _project(tmp_path)
    _write_lessons(lessons, "bte-pricing-regret-notebook", _BODY)  # foreign, no local folder
    cand = _write_candidate(tmp_path, "job-scraper", _BODY)
    rc = main(["--candidate-file", str(cand), "--lessons-file", str(lessons),
               "--candidate-slug", "job-scraper", "--format", "json"])
    assert rc == 1


def test_same_project_slug_exit_0(tmp_path):
    root, lessons = _project(tmp_path)
    _write_lessons(lessons, "job-scraper", _BODY)  # same slug as candidate
    cand = _write_candidate(tmp_path, "job-scraper", _BODY)
    rc = main(["--candidate-file", str(cand), "--lessons-file", str(lessons),
               "--candidate-slug", "job-scraper", "--format", "json"])
    assert rc == 0


def test_strict_attrib_suppresses_when_local_folder_present(tmp_path):
    root, lessons = _project(tmp_path)
    _write_lessons(lessons, "pricing-course", _BODY)
    (root / ".workflow_artifacts" / "pricing-course").mkdir()  # local folder → real local task
    cand = _write_candidate(tmp_path, "job-scraper", _BODY)
    # strict on (default): suppressed → exit 0
    assert main(["--candidate-file", str(cand), "--lessons-file", str(lessons),
                 "--candidate-slug", "job-scraper", "--format", "json"]) == 0
    # strict off: base signal fires → exit 1
    assert main(["--candidate-file", str(cand), "--lessons-file", str(lessons),
                 "--candidate-slug", "job-scraper", "--no-strict-attrib",
                 "--format", "json"]) == 1


def test_none_slug_total_contract_exit_0(tmp_path):
    root, lessons = _project(tmp_path)
    _write_lessons(lessons, "bte-pricing-regret-notebook", _BODY)
    # Candidate with no heading and no --candidate-slug → undeterminable slug → skip.
    cand = tmp_path / "candidate.md"
    cand.write_text(_BODY + "\n", encoding="utf-8")
    rc = main(["--candidate-file", str(cand), "--lessons-file", str(lessons),
               "--format", "json"])
    assert rc == 0


def test_unreadable_lessons_exit_3(tmp_path):
    root, lessons = _project(tmp_path)
    cand = _write_candidate(tmp_path, "job-scraper", _BODY)
    missing = root / ".workflow_artifacts" / "memory" / "does-not-exist.md"
    rc = main(["--candidate-file", str(cand), "--lessons-file", str(missing),
               "--format", "json"])
    assert rc == 3


def test_disable_knob_exit_0(tmp_path, monkeypatch):
    root, lessons = _project(tmp_path)
    _write_lessons(lessons, "bte-pricing-regret-notebook", _BODY)
    cand = _write_candidate(tmp_path, "job-scraper", _BODY)
    monkeypatch.setenv("QUOIN_DISABLE_LESSONS_GUARD", "1")
    rc = main(["--candidate-file", str(cand), "--lessons-file", str(lessons),
               "--candidate-slug", "job-scraper"])
    assert rc == 0


def test_threshold_knob_tunes_match(tmp_path, monkeypatch):
    root, lessons = _project(tmp_path)
    _write_lessons(lessons, "bte-pricing-regret-notebook", _BODY)
    # Candidate shares only ~half the tokens → below 0.9 default, above a low threshold.
    partial = _BODY.split(".")[0] + ". Entirely unrelated words appended here padding tokens."
    cand = _write_candidate(tmp_path, "job-scraper", partial)
    base = ["--candidate-file", str(cand), "--lessons-file", str(lessons),
            "--candidate-slug", "job-scraper", "--format", "json"]
    assert main(base) == 0  # default 0.9 → no match
    monkeypatch.setenv("QUOIN_LESSONS_DUP_THRESHOLD", "0.1")
    assert main(base) == 1  # low threshold → match


def test_argparse_error_exit_2():
    with pytest.raises(SystemExit) as exc:
        main(["--candidate-file", "only-one-arg.md"])  # missing required --lessons-file
    assert exc.value.code == 2


def test_api_none_slug_returns_none():
    assert find_cross_project_duplicate("no heading body text here words", "## 2026-06-18 — foo\nbody") is None

"""
Unit tests for verify_claims.py (IVG-115 T-01/T-02 core engine).

Covers T-01's acceptance criteria: self-test, reconcile_tasks flagging a
claimed-active task whose finalized/<task>/ exists, --finalized-only making
no gh call, filename_task on all three checkpoint filename shapes, and the
window-scoped empty-manifest exit-8 rule (T-02/r5-MAJ-1).
"""

import os
import stat
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "core" / "scripts"))
from verify_claims import (  # noqa: E402
    EXIT_MISMATCH,
    EXIT_OK,
    canonical_ref,
    filename_task,
    match_task,
    parse_claims_manifest,
    reconcile_tasks,
    self_test,
)

_CORE_SCRIPT = Path(__file__).parent.parent.parent / "core" / "scripts" / "verify_claims.py"


def test_self_test_passes():
    assert self_test() is True


def test_filename_task_three_shapes():
    assert filename_task("2026-07-05T0930-mytask") == "mytask"
    assert filename_task("2026-07-05-mytask") == "mytask"
    assert filename_task("2026-07-05-mytask-precompact.md") == "mytask"
    assert filename_task("2026-07-05-mytask-precompact") == "mytask"


def test_canonical_ref_and_match_task():
    assert canonical_ref("IVG-105") == "ivg-105"
    assert canonical_ref("  some-Slug ") == "some-slug"
    assert match_task("ivg-105", ["ivg-105-foo", "ivg-999", "ivg-105"]) == ["ivg-105-foo", "ivg-105"]


def test_finalized_task_flagged_when_claimed_active(tmp_path):
    (tmp_path / ".workflow_artifacts" / "finalized" / "ivg-105-thing").mkdir(parents=True)
    claims = [{"task_ref": "IVG-105", "status": "awaiting_end_of_task"}]
    report = reconcile_tasks(tmp_path, claims=claims, finalized_only=True)
    assert report["exit_code"] == EXIT_MISMATCH
    assert report["reason"] == "mismatch"
    assert "ivg-105-thing" in report["mismatched_tasks"]


def test_unmatched_ref_is_not_a_mismatch(tmp_path):
    (tmp_path / ".workflow_artifacts" / "ivg-999-other").mkdir(parents=True)
    claims = [{"task_ref": "IVG-777", "status": "awaiting_end_of_task"}]
    report = reconcile_tasks(tmp_path, claims=claims, finalized_only=True)
    assert report["exit_code"] == EXIT_OK


def test_finalized_only_skips_gh(tmp_path):
    (tmp_path / ".workflow_artifacts" / "finalized" / "ivg-999-other").mkdir(parents=True)
    gh_json = [{"headRefName": "ivg-999-other", "state": "MERGED"}]
    claims = [{"task_ref": "IVG-999", "status": "awaiting_pr"}]

    report_finalized_only = reconcile_tasks(tmp_path, claims=claims, gh_json=gh_json, finalized_only=True)
    assert report_finalized_only["truth"]["ivg-999-other"]["pr_status"] == "gh-unavailable"
    assert report_finalized_only["exit_code"] == EXIT_OK  # awaiting_pr not evaluated without gh

    report_live_gh = reconcile_tasks(tmp_path, claims=claims, gh_json=gh_json, finalized_only=False)
    assert report_live_gh["exit_code"] == EXIT_MISMATCH  # merged PR contradicts awaiting_pr


def test_coverage_line_for_unclaimed_finalized(tmp_path):
    (tmp_path / ".workflow_artifacts" / "finalized" / "ivg-105-thing").mkdir(parents=True)
    (tmp_path / ".workflow_artifacts" / "finalized" / "ivg-200-other").mkdir(parents=True)
    claims = [{"task_ref": "IVG-105", "status": "finalized"}]
    report = reconcile_tasks(tmp_path, claims=claims, finalized_only=True)
    assert report["exit_code"] == EXIT_OK  # coverage gap alone does not force exit 8
    assert any("ivg-200-other" in line for line in report["coverage"])


def test_empty_manifest_with_in_window_coverage_exits_8(tmp_path):
    finalized_dir = tmp_path / ".workflow_artifacts" / "finalized" / "ivg-105-thing"
    finalized_dir.mkdir(parents=True)
    report = reconcile_tasks(tmp_path, claims=[], finalized_only=True, today=date.today())
    assert report["exit_code"] == EXIT_MISMATCH
    assert report["reason"] == "empty-manifest"


def test_empty_manifest_no_folders_exits_0(tmp_path):
    report = reconcile_tasks(tmp_path, claims=[], finalized_only=True)
    assert report["exit_code"] == EXIT_OK


def test_empty_manifest_out_of_window_finalized_exits_0(tmp_path):
    finalized_dir = tmp_path / ".workflow_artifacts" / "finalized" / "ivg-105-thing"
    finalized_dir.mkdir(parents=True)
    today = date.today()
    import os
    from datetime import datetime, time
    old_dt = datetime.combine(today - timedelta(days=10), time(12, 0))
    old_mtime = old_dt.timestamp()
    os.utime(finalized_dir, (old_mtime, old_mtime))

    daily_dir = tmp_path / ".workflow_artifacts" / "memory" / "daily"
    daily_dir.mkdir(parents=True)
    (daily_dir / f"{(today - timedelta(days=1)).isoformat()}.md").write_text("x")

    report = reconcile_tasks(tmp_path, claims=[], finalized_only=True, today=today)
    assert report["exit_code"] == EXIT_OK
    assert report["reason"] == ""


def test_no_claims_source_is_not_empty_manifest(tmp_path):
    (tmp_path / ".workflow_artifacts" / "finalized" / "ivg-105-thing").mkdir(parents=True)
    report = reconcile_tasks(tmp_path, claims=None, finalized_only=True)
    assert report["exit_code"] == EXIT_OK
    assert report["reason"] == ""


def test_parse_claims_manifest_round_trip(tmp_path):
    manifest = tmp_path / "manifest.md"
    manifest.write_text(
        '## Claims\n```yaml\n- task_ref: "IVG-105"\n  status: awaiting_end_of_task\n'
        "- task_ref: IVG-200\n  status: in_progress\n```\n"
    )
    parsed = parse_claims_manifest(manifest)
    assert parsed == [
        {"task_ref": "IVG-105", "status": "awaiting_end_of_task"},
        {"task_ref": "IVG-200", "status": "in_progress"},
    ]


def test_parse_claims_manifest_empty_block():
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        manifest = Path(tmp) / "empty.md"
        manifest.write_text("## Claims\n```yaml\n```\n")
        assert parse_claims_manifest(manifest) == []


def test_parse_claims_manifest_absent_file(tmp_path):
    assert parse_claims_manifest(tmp_path / "does-not-exist.md") == []


def test_ambiguous_candidate_ref_is_unmatched(tmp_path):
    # Two folders share the same issue number but disagree on finalized truth
    # -> len(candidates) > 1 with conflicting truth -> unmatched (fail-open),
    # never a MISMATCH (T-02 "ambiguous" branch).
    (tmp_path / ".workflow_artifacts" / "finalized" / "ivg-105-old-attempt").mkdir(parents=True)
    (tmp_path / ".workflow_artifacts" / "ivg-105-retry").mkdir(parents=True)
    claims = [{"task_ref": "IVG-105", "status": "awaiting_end_of_task"}]
    report = reconcile_tasks(tmp_path, claims=claims, finalized_only=True)
    assert report["exit_code"] == EXIT_OK
    assert report["results"][0]["verdict"] == "unmatched"
    assert report["mismatched_tasks"] == []


def _write_stub_gh(bin_dir, marker_path, canned_json):
    """Write a fake `gh` executable on PATH. Touches marker_path when invoked
    and prints canned_json to stdout, so tests can assert whether the live
    gh binary was actually shelled out to."""
    gh_path = bin_dir / "gh"
    gh_path.write_text(
        "#!/usr/bin/env python3\n"
        "import pathlib, sys\n"
        f"pathlib.Path({str(marker_path)!r}).write_text('called')\n"
        f"print({canned_json!r})\n"
    )
    gh_path.chmod(gh_path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return gh_path


def test_gh_json_file_bypasses_live_gh_call(tmp_path):
    # --gh-json-file is the testable seam: when supplied, the live `gh`
    # binary must never be invoked even if it's on PATH (T-02 acceptance).
    (tmp_path / ".workflow_artifacts" / "ivg-999-other").mkdir(parents=True)
    claims_file = tmp_path / "claims.md"
    claims_file.write_text(
        '## Claims\n```yaml\n- task_ref: "IVG-999"\n  status: awaiting_pr\n```\n'
    )
    gh_json_file = tmp_path / "gh.json"
    gh_json_file.write_text('[{"headRefName": "ivg-999-other", "state": "MERGED"}]')

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    marker = tmp_path / "gh-was-called.marker"
    _write_stub_gh(bin_dir, marker, "[]")

    env = dict(os.environ)
    env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"

    proc = subprocess.run(
        [sys.executable, str(_CORE_SCRIPT), "--project-root", str(tmp_path),
         "--reconcile-tasks", "--claims-file", str(claims_file),
         "--gh-json-file", str(gh_json_file)],
        capture_output=True, text=True, env=env, timeout=30,
    )
    assert proc.returncode == EXIT_MISMATCH  # merged PR contradicts awaiting_pr
    assert not marker.exists(), "live gh binary was invoked despite --gh-json-file being supplied"


def test_live_gh_call_invoked_when_no_json_file(tmp_path):
    # Without --gh-json-file and without --finalized-only, the CLI must
    # shell out to the real `gh pr list` once (T-02 truth side).
    (tmp_path / ".workflow_artifacts" / "ivg-999-other").mkdir(parents=True)
    claims_file = tmp_path / "claims.md"
    claims_file.write_text(
        '## Claims\n```yaml\n- task_ref: "IVG-999"\n  status: awaiting_pr\n```\n'
    )

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    marker = tmp_path / "gh-was-called.marker"
    canned = '[{"headRefName": "ivg-999-other", "state": "MERGED"}]'
    _write_stub_gh(bin_dir, marker, canned)

    env = dict(os.environ)
    env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"

    proc = subprocess.run(
        [sys.executable, str(_CORE_SCRIPT), "--project-root", str(tmp_path),
         "--reconcile-tasks", "--claims-file", str(claims_file)],
        capture_output=True, text=True, env=env, timeout=30,
    )
    assert marker.exists(), "live gh binary was never invoked"
    assert proc.returncode == EXIT_MISMATCH  # merged PR contradicts awaiting_pr, via live gh output

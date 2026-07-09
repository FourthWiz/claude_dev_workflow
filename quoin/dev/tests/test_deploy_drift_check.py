"""IVG-136 T-06: unit tests for compute_drift + installer helpers + the CLI.

compute_drift cases (a)-(e),(j); CLI cases (f)-(i) + scope/drift/disabled; and the
import-safety cases (k)/(l)/(m) that prove the deferred-import contract (plan D-11).

Loader pattern mirrors test_install_branch_hygiene_deployed.py: installer.py and the
adapter CLI are loaded via importlib.util.spec_from_file_location so the test does not
depend on the pip-installed `quoin` package for module collection.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]  # quoin/ repo root
INSTALLER_PY = REPO_ROOT / "src" / "quoin" / "installer.py"
DDC_PY = REPO_ROOT / "quoin" / "scripts" / "deploy_drift_check.py"


def _load(mod_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(mod_name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def installer():
    return _load("_ddc_installer", INSTALLER_PY)


@pytest.fixture
def ddc():
    return _load("_ddc_cli", DDC_PY)


# ---------------------------------------------------------------------------
# Helpers: build a minimal source tree + a deployed dest_root using the real
# installer helpers, with the manifests monkeypatched down to a small set.
# ---------------------------------------------------------------------------

def _build_trees(installer, tmp_path, monkeypatch):
    """Create source_dir + dest_root with one file per checked category, deployed
    via the real expected_deployed_content so compute_drift returns [] initially."""
    src = tmp_path / "src"
    dest = tmp_path / "dest"

    # memory (tier-1)
    (src / "memory").mkdir(parents=True)
    (src / "memory" / "m1.md").write_text("mem body\n", encoding="utf-8")
    # skills: one with an adapter SKILL.md, one stub-only + a preamble
    (src / "skills" / "alpha").mkdir(parents=True)
    (src / "skills" / "alpha" / "SKILL.md").write_text("alpha stub\n", encoding="utf-8")
    (src / "skills" / "alpha" / "preamble.md").write_text("alpha preamble\n", encoding="utf-8")
    (src / "adapters" / "claude" / "skills" / "alpha").mkdir(parents=True)
    (src / "adapters" / "claude" / "skills" / "alpha" / "SKILL.md").write_text(
        "alpha ADAPTER body\n", encoding="utf-8")
    # scripts
    (src / "scripts").mkdir(parents=True)
    (src / "scripts" / "s1.py").write_text("print('s1')\n", encoding="utf-8")
    # core-scripts
    (src / "core" / "scripts").mkdir(parents=True)
    (src / "core" / "scripts" / "c1.py").write_text("print('c1')\n", encoding="utf-8")

    monkeypatch.setattr(installer, "TIER1_MEMORY_FILES", ("m1.md",))
    monkeypatch.setattr(installer, "CANONICAL_SKILLS", ("alpha",))
    monkeypatch.setattr(installer, "DEPLOYED_SCRIPTS", ("s1.py",))
    monkeypatch.setattr(installer, "CORE_SCRIPTS", ("c1.py",))

    # Deploy each file: write expected_deployed_content to the dest path.
    def _deploy(src_path: Path, dest_path: Path):
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_path.write_bytes(installer.expected_deployed_content(src_path, dest))

    _deploy(src / "memory" / "m1.md", dest / "memory" / "m1.md")
    # skills: adapter-preferred SKILL.md is the source of record
    _deploy(src / "adapters" / "claude" / "skills" / "alpha" / "SKILL.md",
            dest / "skills" / "alpha" / "SKILL.md")
    _deploy(src / "skills" / "alpha" / "preamble.md",
            dest / "skills" / "alpha" / "preamble.md")
    _deploy(src / "scripts" / "s1.py", dest / "scripts" / "s1.py")
    _deploy(src / "core" / "scripts" / "c1.py", dest / "core" / "scripts" / "c1.py")

    return src, dest


# ---------------------------------------------------------------------------
# Installer helper tests
# ---------------------------------------------------------------------------

def test_expected_deployed_content_substitutes(installer, tmp_path):
    src = tmp_path / "f.md"
    src.write_text("path=__QUOIN_HOME__/x\n", encoding="utf-8")
    dest_root = tmp_path / "dest"
    out = installer.expected_deployed_content(src, dest_root)
    assert b"__QUOIN_HOME__" not in out
    assert str(dest_root.resolve()).encode("utf-8") in out


def test_expected_deployed_content_bytecopy_nontext(installer, tmp_path):
    src = tmp_path / "img.png"
    src.write_bytes(b"\x89PNG__QUOIN_HOME__")  # placeholder must NOT be substituted
    out = installer.expected_deployed_content(src, tmp_path / "dest")
    assert out == b"\x89PNG__QUOIN_HOME__"


def test_resolve_skill_source_md_adapter_preferred(installer, tmp_path):
    src_skills = tmp_path / "skills"
    src_adapter = tmp_path / "adapters" / "claude" / "skills"
    (src_skills / "alpha").mkdir(parents=True)
    (src_skills / "alpha" / "SKILL.md").write_text("stub", encoding="utf-8")
    (src_adapter / "alpha").mkdir(parents=True)
    (src_adapter / "alpha" / "SKILL.md").write_text("adapter", encoding="utf-8")
    resolved = installer.resolve_skill_source_md(src_skills, src_adapter, "alpha")
    assert resolved == src_adapter / "alpha" / "SKILL.md"


def test_resolve_skill_source_md_stub_fallback(installer, tmp_path):
    src_skills = tmp_path / "skills"
    src_adapter = tmp_path / "adapters" / "claude" / "skills"
    (src_skills / "beta").mkdir(parents=True)
    (src_skills / "beta" / "SKILL.md").write_text("stub", encoding="utf-8")
    resolved = installer.resolve_skill_source_md(src_skills, src_adapter, "beta")
    assert resolved == src_skills / "beta" / "SKILL.md"


# ---------------------------------------------------------------------------
# compute_drift cases (a)-(e),(j)
# ---------------------------------------------------------------------------

def test_compute_drift_clean_fresh_install(installer, tmp_path, monkeypatch):
    src, dest = _build_trees(installer, tmp_path, monkeypatch)
    assert installer.compute_drift(src, dest) == []


def test_compute_drift_a_stale_skill(installer, tmp_path, monkeypatch):
    src, dest = _build_trees(installer, tmp_path, monkeypatch)
    (dest / "skills" / "alpha" / "SKILL.md").write_text("MUTATED\n", encoding="utf-8")
    drift = installer.compute_drift(src, dest)
    assert any(d.reason == "stale" and d.category == "skills" for d in drift)


def test_compute_drift_b_missing_script(installer, tmp_path, monkeypatch):
    src, dest = _build_trees(installer, tmp_path, monkeypatch)
    (dest / "scripts" / "s1.py").unlink()
    drift = installer.compute_drift(src, dest)
    assert any(d.reason == "missing" and d.category == "scripts" for d in drift)


def test_compute_drift_c_substitution_parity(installer, tmp_path, monkeypatch):
    src, dest = _build_trees(installer, tmp_path, monkeypatch)
    # Source memory file uses the placeholder; deployed copy holds substituted path.
    (src / "memory" / "m1.md").write_text("go __QUOIN_HOME__/here\n", encoding="utf-8")
    (dest / "memory" / "m1.md").write_bytes(
        installer.expected_deployed_content(src / "memory" / "m1.md", dest))
    drift = installer.compute_drift(src, dest)
    assert not any(d.category == "memory" for d in drift), (
        "substituted deployed copy must NOT be flagged as drift")


def test_compute_drift_d_adapter_not_stub(installer, tmp_path, monkeypatch):
    src, dest = _build_trees(installer, tmp_path, monkeypatch)
    # Deployed copy matches the ADAPTER body (source of record). Mutating the stub
    # must NOT create drift because the adapter file is what is compared.
    (src / "skills" / "alpha" / "SKILL.md").write_text("stub CHANGED\n", encoding="utf-8")
    drift = installer.compute_drift(src, dest)
    assert not any(d.category == "skills" and "SKILL.md" in d.deployed_path for d in drift)


def test_compute_drift_e_untracked_memory_file_ignored(installer, tmp_path, monkeypatch):
    src, dest = _build_trees(installer, tmp_path, monkeypatch)
    # A memory file NOT in TIER1_MEMORY_FILES must not be compared.
    (src / "memory" / "not_tier1.md").write_text("x\n", encoding="utf-8")
    assert installer.compute_drift(src, dest) == []


def test_compute_drift_j_absent_source_skill_does_not_raise(installer, tmp_path, monkeypatch):
    src, dest = _build_trees(installer, tmp_path, monkeypatch)
    # Canonical skill with NO source SKILL.md on disk anywhere → must not raise (MIN-3).
    monkeypatch.setattr(installer, "CANONICAL_SKILLS", ("alpha", "ghost"))
    drift = installer.compute_drift(src, dest)  # must not raise
    assert isinstance(drift, list)


# ---------------------------------------------------------------------------
# Manifest registration (T-04)
# ---------------------------------------------------------------------------

def test_manifest_registration(installer):
    assert "deploy_drift_check.py" in installer.DEPLOYED_SCRIPTS
    assert "deploy_drift_check.py" not in installer.CORE_SCRIPTS


# ---------------------------------------------------------------------------
# CLI cases
# ---------------------------------------------------------------------------

def test_cli_disabled_env(ddc, monkeypatch):
    monkeypatch.setenv("QUOIN_DISABLE_DEPLOY_DRIFT", "1")
    assert ddc.main([]) == 0


def test_cli_h_argparse_usage_error_exit2(ddc):
    # (h) genuine argparse error on OWN flags → exit 2 propagates (not remapped to 3).
    with pytest.raises(SystemExit) as exc:
        ddc.main(["--format", "bogus"])
    assert exc.value.code == 2


def test_cli_f_compute_drift_raises_exit3(ddc, monkeypatch, tmp_path):
    # (f) compute_drift raises an arbitrary exception → exit 3, not Python default 1.
    import quoin.installer as qi
    monkeypatch.setattr(qi, "compute_drift", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    # Ensure dest_root exists so we reach compute_drift.
    dest = tmp_path / ".claude"
    dest.mkdir()
    monkeypatch.setattr(ddc, "_resolve_dest_root", lambda scope: dest)
    rc = ddc.main(["--no-scope-check", "--project-root", str(tmp_path)])
    assert rc == 3


def test_cli_g_unresolvable_source_exit3(ddc, tmp_path):
    # (g) --source-dir with no skills/ → _resolve_source_dir sys.exit(2) → remapped to 3.
    bad = tmp_path / "nosrc"
    bad.mkdir()
    rc = ddc.main(["--no-scope-check", "--source-dir", str(bad),
                   "--project-root", str(tmp_path)])
    assert rc == 3


def test_cli_k_quoin_unimportable_scope_in_exit3(ddc, monkeypatch, tmp_path):
    # (k) quoin import itself fails on a scope=IN run → exit 3 (not uncaught ImportError→1).
    monkeypatch.setitem(sys.modules, "quoin", None)
    monkeypatch.setitem(sys.modules, "quoin.installer", None)
    monkeypatch.setitem(sys.modules, "quoin.cli", None)
    rc = ddc.main(["--no-scope-check", "--project-root", str(tmp_path)])
    assert rc == 3


def test_cli_l_quoin_unimportable_scope_out_exit0(ddc, monkeypatch, tmp_path):
    # (l) scope=OUT with quoin unimportable → exit 0, proving scope gate runs BEFORE import.
    monkeypatch.setitem(sys.modules, "quoin", None)
    monkeypatch.setattr(ddc, "_scope_is_in", lambda pr, nsc: (False, "out"))
    rc = ddc.main(["--project-root", str(tmp_path)])
    assert rc == 0


def test_cli_m_module_import_no_module_top_quoin(ddc):
    # (m) module collection succeeds even with quoin=None (proves no module-top import).
    # `ddc` fixture already imported the module; re-import under quoin=None to be explicit.
    import importlib.util as _u
    saved = sys.modules.get("quoin")
    sys.modules["quoin"] = None
    try:
        spec = _u.spec_from_file_location("_ddc_reimport", DDC_PY)
        mod = _u.module_from_spec(spec)
        spec.loader.exec_module(mod)  # must NOT raise
    finally:
        if saved is not None:
            sys.modules["quoin"] = saved
        else:
            sys.modules.pop("quoin", None)


def test_cli_scope_out_exit0(ddc, monkeypatch, tmp_path):
    monkeypatch.setattr(ddc, "_scope_is_in", lambda pr, nsc: (False, "out"))
    rc = ddc.main(["--project-root", str(tmp_path)])
    assert rc == 0


def test_cli_git_error_exit3(ddc, monkeypatch, tmp_path):
    # Deferred MINOR (1): scope-gate git-error → exit 3 (WARN), never a false exit-0 PASS.
    monkeypatch.setattr(ddc, "_scope_is_in", lambda pr, nsc: (False, "git-error"))
    rc = ddc.main(["--project-root", str(tmp_path)])
    assert rc == 3


def test_cli_clean_pass_names_coverage(ddc, monkeypatch, tmp_path, capsys):
    # (i)-adjacent: clean PASS output MUST contain the "not covered" qualifier.
    import quoin.installer as qi
    dest = tmp_path / ".claude"
    dest.mkdir()
    monkeypatch.setattr(qi, "compute_drift", lambda *a, **k: [])
    monkeypatch.setattr(ddc, "_resolve_dest_root", lambda scope: dest)
    rc = ddc.main(["--no-scope-check", "--project-root", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "not covered" in out


def test_cli_drift_found_exit1(ddc, monkeypatch, tmp_path):
    import quoin.installer as qi
    dest = tmp_path / ".claude"
    dest.mkdir()
    fake = qi.DriftEntry("scripts", "/src/s1.py", "/dest/s1.py", "stale")
    monkeypatch.setattr(qi, "compute_drift", lambda *a, **k: [fake])
    monkeypatch.setattr(ddc, "_resolve_dest_root", lambda scope: dest)
    rc = ddc.main(["--no-scope-check", "--project-root", str(tmp_path)])
    assert rc == 1

"""Tests for the Codex installable feature scaffold.

Verifies:
- manifest exists, parses as JSON, references portable workflow metadata,
  avoids unsupported path claims
- generator produces AGENTS.md in a temp project root
- --check passes on matching output and fails on stale output
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

THIS_FILE = Path(__file__).resolve()
TESTS_DIR = THIS_FILE.parent
PKG_DIR = TESTS_DIR.parent.parent
CODEX_ADAPTER_DIR = PKG_DIR / "adapters" / "codex"
MANIFEST_PATH = CODEX_ADAPTER_DIR / "feature-manifest.json"
GENERATOR_PATH = CODEX_ADAPTER_DIR / "generate_codex_assets.py"
READINESS_PATH = CODEX_ADAPTER_DIR / "verify_codex_readiness.py"
CONTRACT_PATH = CODEX_ADAPTER_DIR / "installable-feature.md"
SKILLS_JSON_PATH = PKG_DIR / "core" / "workflow" / "skills.json"
REPO_ROOT = PKG_DIR.parent

GUESSED_GLOBAL_PATTERNS = [
    "~/." + "codex",
    "/usr/local/" + "codex",
    "codex install",
    "npm install" + " -g",
]


# ---------------------------------------------------------------------------
# Manifest tests
# ---------------------------------------------------------------------------


def test_manifest_exists():
    assert MANIFEST_PATH.is_file(), f"Missing {MANIFEST_PATH}"


def test_manifest_parses_as_json():
    text = MANIFEST_PATH.read_text(encoding="utf-8")
    manifest = json.loads(text)
    assert isinstance(manifest, dict), "Manifest must be a JSON object"


def test_manifest_has_required_keys():
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    required = {
        "schema_version", "feature_name", "adapter", "status",
        "entrypoints", "portable_inputs", "generated_outputs",
        "unsupported_outputs", "validation",
    }
    missing = required - set(manifest.keys())
    assert not missing, f"Manifest missing keys: {missing}"


def test_manifest_references_skills_json():
    """Manifest portable_inputs must reference skills.json by path."""
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    paths = [entry.get("path", "") for entry in manifest.get("portable_inputs", [])]
    assert any("skills.json" in p for p in paths), (
        "Manifest portable_inputs must reference skills.json"
    )


def test_manifest_exposes_readiness_check():
    """Manifest entrypoints and validation must include the repo-local readiness check."""
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    entrypoint_paths = [entry.get("path", "") for entry in manifest.get("entrypoints", [])]
    validation = "\n".join(manifest.get("validation", {}).get("commands", []))
    assert any("verify_codex_readiness.py" in path for path in entrypoint_paths)
    assert "verify_codex_readiness.py" in validation


def test_manifest_generated_output_is_repo_local():
    """Generated outputs must be repo-local (no global paths)."""
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    for entry in manifest.get("generated_outputs", []):
        scope = entry.get("scope", "")
        assert scope == "repo-local", (
            f"Generated output {entry.get('path')} must have scope=repo-local, got {scope!r}"
        )


def test_manifest_avoids_guessed_global_paths():
    """Manifest text must not contain known guessed global path patterns."""
    text = MANIFEST_PATH.read_text(encoding="utf-8")
    hits = [p for p in GUESSED_GLOBAL_PATTERNS if p in text]
    assert not hits, f"Manifest contains guessed global paths: {hits}"


def test_codex_adapter_active_files_avoid_guessed_global_paths():
    """Codex adapter files must not hardcode guessed global Codex paths."""
    active_files = [
        CODEX_ADAPTER_DIR / "README.md",
        CODEX_ADAPTER_DIR / "setup.md",
        CODEX_ADAPTER_DIR / "installable-feature.md",
        CODEX_ADAPTER_DIR / "feature-manifest.json",
        CODEX_ADAPTER_DIR / "generate_codex_assets.py",
        CODEX_ADAPTER_DIR / "verify_codex_readiness.py",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in active_files)
    hits = [p for p in GUESSED_GLOBAL_PATTERNS if p in combined]
    assert not hits, f"Codex adapter files contain guessed global paths: {hits}"


def test_manifest_documents_unsupported_global_install():
    """Manifest must explicitly document that global install is unsupported."""
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    unsupported_names = [e.get("name", "") for e in manifest.get("unsupported_outputs", [])]
    assert any("global" in n.lower() for n in unsupported_names), (
        "Manifest must list a global install as an unsupported output"
    )


# ---------------------------------------------------------------------------
# Generator tests
# ---------------------------------------------------------------------------


def test_generator_script_exists():
    assert GENERATOR_PATH.is_file(), f"Missing {GENERATOR_PATH}"


def test_readiness_script_exists():
    assert READINESS_PATH.is_file(), f"Missing {READINESS_PATH}"


def test_generator_writes_agents_md_to_project_root():
    """Generator must write AGENTS.md to <project-root>/AGENTS.md."""
    with tempfile.TemporaryDirectory() as tmpdir:
        result = subprocess.run(
            [sys.executable, str(GENERATOR_PATH), "--project-root", tmpdir],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, f"Generator failed: {result.stderr}"
        agents_md = Path(tmpdir) / "AGENTS.md"
        assert agents_md.exists(), "Generator did not create AGENTS.md"
        content = agents_md.read_text(encoding="utf-8")
        assert len(content) > 0, "Generated AGENTS.md is empty"


def test_generator_no_global_writes():
    """Generator must not write outside the project root."""
    with tempfile.TemporaryDirectory() as tmpdir:
        result = subprocess.run(
            [sys.executable, str(GENERATOR_PATH), "--project-root", tmpdir],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, f"Generator failed: {result.stderr}"
        # The only change should be AGENTS.md inside tmpdir
        written = list(Path(tmpdir).iterdir())
        assert len(written) == 1 and written[0].name == "AGENTS.md", (
            f"Generator wrote unexpected files: {written}"
        )


def test_generator_check_passes_on_matching_output():
    """--check must exit 0 when AGENTS.md matches rendered output."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Generate first
        subprocess.run(
            [sys.executable, str(GENERATOR_PATH), "--project-root", tmpdir],
            check=True, capture_output=True,
        )
        # --check must pass
        result = subprocess.run(
            [sys.executable, str(GENERATOR_PATH), "--project-root", tmpdir, "--check"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, (
            f"--check failed on matching output: {result.stderr}"
        )


def test_generator_check_fails_on_stale_output():
    """--check must exit nonzero when AGENTS.md is out of date."""
    with tempfile.TemporaryDirectory() as tmpdir:
        stale_path = Path(tmpdir) / "AGENTS.md"
        stale_path.write_text("stale content", encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(GENERATOR_PATH), "--project-root", tmpdir, "--check"],
            capture_output=True, text=True,
        )
        assert result.returncode != 0, (
            "--check must exit nonzero on stale AGENTS.md"
        )


def test_generated_agents_md_preserves_architectural_boundaries():
    """Generated AGENTS.md must preserve Quoin architectural boundaries."""
    with tempfile.TemporaryDirectory() as tmpdir:
        subprocess.run(
            [sys.executable, str(GENERATOR_PATH), "--project-root", tmpdir],
            check=True, capture_output=True,
        )
        content = (Path(tmpdir) / "AGENTS.md").read_text(encoding="utf-8")
        # Must not promise global install
        assert "global Codex install" not in content or "not" in content.lower(), (
            "Generated AGENTS.md must not promise global Codex install"
        )
        # Must mention .workflow_artifacts/
        assert ".workflow_artifacts/" in content, (
            "Generated AGENTS.md must describe .workflow_artifacts/ layout"
        )
        # Must not mention Claude slash commands as required
        assert "slash command" not in content.lower(), (
            "Generated AGENTS.md must not require Claude slash commands"
        )


def test_generated_agents_md_uses_skills_json():
    """Generated AGENTS.md must include skill names drawn from skills.json."""
    skills_data = json.loads(SKILLS_JSON_PATH.read_text(encoding="utf-8"))
    skill_names = [s["name"] for s in skills_data.get("skills", []) if s.get("user_facing")]
    with tempfile.TemporaryDirectory() as tmpdir:
        subprocess.run(
            [sys.executable, str(GENERATOR_PATH), "--project-root", tmpdir],
            check=True, capture_output=True,
        )
        content = (Path(tmpdir) / "AGENTS.md").read_text(encoding="utf-8")
        present = [name for name in skill_names if name in content]
        assert len(present) >= 5, (
            f"Generated AGENTS.md should include multiple skill names from skills.json; "
            f"found only: {present}"
        )


# ---------------------------------------------------------------------------
# Readiness tests
# ---------------------------------------------------------------------------


def test_readiness_check_passes_for_repo_root():
    """Readiness check must pass for this repo-local Codex setup."""
    result = subprocess.run(
        [sys.executable, str(READINESS_PATH), "--project-root", str(REPO_ROOT)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, (
        f"Readiness check failed:\nstdout={result.stdout}\nstderr={result.stderr}"
    )
    assert "READY: repo-local Codex setup contract is satisfied" in result.stdout


def test_readiness_check_fails_without_agents_md():
    """Readiness check must fail if the project root lacks AGENTS.md."""
    with tempfile.TemporaryDirectory() as tmpdir:
        result = subprocess.run(
            [sys.executable, str(READINESS_PATH), "--project-root", tmpdir],
            capture_output=True, text=True,
        )
        assert result.returncode != 0
        assert "agents-md" in result.stdout


def test_claude_install_remains_codex_free():
    """Claude install behavior stays isolated from the Codex setup flow."""
    install_sh = PKG_DIR / "install.sh"
    text = install_sh.read_text(encoding="utf-8").lower()
    assert "codex" not in text
    assert ".claude" in text


# ---------------------------------------------------------------------------
# Contract doc test
# ---------------------------------------------------------------------------


def test_contract_doc_exists():
    assert CONTRACT_PATH.is_file(), f"Missing {CONTRACT_PATH}"


def test_contract_doc_links_required_docs():
    """installable-feature.md must link to runtime-portability.md, setup.md, and skills.json."""
    text = CONTRACT_PATH.read_text(encoding="utf-8")
    assert "runtime-portability.md" in text, "Contract must link to runtime-portability.md"
    assert "setup.md" in text, "Contract must link to setup.md"
    assert "skills.json" in text, "Contract must link to skills.json"

import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]


def read_rel(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def test_runtime_portability_docs_exist():
    expected = [
        "AGENTS.md",
        "quoin/docs/runtime-portability.md",
        "quoin/docs/runtime-portability-status.md",
        "quoin/docs/effort-levels.md",
        "quoin/core/workflow/rules.md",
        "quoin/core/workflow/task-layout.md",
        "quoin/core/workflow/session-state.md",
        "quoin/core/workflow/cost-ledger.md",
        "quoin/core/workflow/skills.json",
        "quoin/core/workflow/skills.md",
        "quoin/adapters/README.md",
        "quoin/adapters/claude/README.md",
        "quoin/adapters/claude/models.md",
        "quoin/adapters/codex/README.md",
        "quoin/adapters/codex/effort.md",
        "quoin/adapters/codex/setup.md",
    ]
    missing = [path for path in expected if not (REPO_ROOT / path).is_file()]
    assert not missing, f"Missing runtime-portability docs: {missing}"


def test_runtime_boundary_classifies_portable_and_claude_files():
    text = read_rel("quoin/docs/runtime-portability.md")
    for portable in ["path_resolve.py", "validate_artifact.py"]:
        assert f"`{portable}` is portable" in text

    for claude_specific in [
        "cost_from_jsonl.py",
        "session_age_guard.py",
        "build_preambles.py",
    ]:
        assert f"`{claude_specific}` is Claude-specific" in text


def test_portable_scripts_have_core_implementation_and_wrappers():
    for name in [
        "path_resolve.py",
        "validate_artifact.py",
        "classify_critic_issues.py",
        "validate_adapter_drift.py",
    ]:
        core_path = REPO_ROOT / "quoin" / "core" / "scripts" / name
        wrapper_path = REPO_ROOT / "quoin" / "scripts" / name
        assert core_path.is_file(), f"Missing core script implementation: {core_path}"
        assert wrapper_path.is_file(), f"Missing compatibility wrapper: {wrapper_path}"
        assert "core\" / \"scripts" in wrapper_path.read_text(encoding="utf-8")


def test_core_workflow_docs_are_referenced_from_runtime_boundary_and_claude_rules():
    runtime = read_rel("quoin/docs/runtime-portability.md")
    claude = read_rel("quoin/CLAUDE.md")

    for name in ["rules.md", "task-layout.md", "session-state.md", "cost-ledger.md"]:
        assert name in runtime
        assert name in claude

    assert "quoin/core/workflow/" in runtime
    assert "quoin/core/workflow/" in claude
    assert "bash quoin/install.sh" in claude
    assert "active Claude Code runtime rules file" in claude


def test_skill_manifest_matches_current_claude_frontmatter():
    manifest = json.loads(read_rel("quoin/core/workflow/skills.json"))
    entries = manifest["skills"]
    by_name = {entry["name"]: entry for entry in entries}

    skill_paths = sorted((REPO_ROOT / "quoin" / "skills").glob("*/SKILL.md"))
    skill_names = {path.parent.name for path in skill_paths}
    assert set(by_name) == skill_names

    allowed_effort = {"low", "medium", "high", "max"}
    for path in skill_paths:
        text = path.read_text(encoding="utf-8")
        frontmatter = text.split("---", 2)[1]
        model = re.search(r"^model:\s*(\S+)", frontmatter, re.MULTILINE)
        assert model is not None, f"Missing model frontmatter in {path}"

        entry = by_name[path.parent.name]
        assert entry["claude_model"] == model.group(1)
        assert entry["effort"] in allowed_effort
        assert isinstance(entry["phase"], str) and entry["phase"]
        assert isinstance(entry["user_facing"], bool)

    assert by_name["revise-fast"]["user_facing"] is False
    assert all(
        entry["user_facing"] is True
        for name, entry in by_name.items()
        if name != "revise-fast"
    )


def test_skill_manifest_does_not_include_codex_model_names():
    manifest_text = read_rel("quoin/core/workflow/skills.json").lower()
    forbidden = ["gpt-", "codex-", "o3", "o4", "o5"]
    for token in forbidden:
        assert token not in manifest_text


def test_skill_manifest_readme_documents_all_fields():
    text = read_rel("quoin/core/workflow/skills.md")
    for field in [
        "schema_version",
        "skills",
        "name",
        "phase",
        "effort",
        "user_facing",
        "claude_model",
    ]:
        assert f"`{field}`" in text
    assert "`effort` is the portable field" in text
    assert "`claude_model` exists to keep the manifest auditable" in text


def test_adapter_model_docs_define_runtime_mappings():
    claude = read_rel("quoin/adapters/claude/models.md").lower()
    codex = read_rel("quoin/adapters/codex/effort.md").lower()

    for token in ["haiku", "sonnet", "opus"]:
        assert token in claude
    for effort in ["low", "medium", "high", "max"]:
        assert f"`{effort}`" in claude
        assert f"`{effort}`" in codex

    assert "model:" in claude
    assert "skill.md" in claude
    assert "native codex controls" in codex
    assert "should not consume `claude_model`" in codex


def test_codex_docs_do_not_hardcode_model_names():
    docs = [
        read_rel("quoin/adapters/codex/README.md"),
        read_rel("quoin/adapters/codex/effort.md"),
        read_rel("quoin/adapters/codex/setup.md"),
    ]
    combined = "\n".join(docs).lower()
    forbidden = ["gpt-", "codex-", "o3", "o4", "o5"]
    for token in forbidden:
        assert token not in combined


def test_codex_docs_do_not_guess_global_install_paths():
    docs = [
        read_rel("AGENTS.md"),
        read_rel("quoin/adapters/codex/README.md"),
        read_rel("quoin/adapters/codex/effort.md"),
        read_rel("quoin/adapters/codex/setup.md"),
        read_rel("quoin/docs/runtime-portability.md"),
        read_rel("quoin/docs/runtime-portability-status.md"),
        read_rel("quoin/docs/effort-levels.md"),
    ]
    combined = "\n".join(docs)
    forbidden = ["~/.codex"]
    for token in forbidden:
        assert token not in combined


def test_codex_setup_and_status_are_explicitly_not_installable():
    setup = read_rel("quoin/adapters/codex/setup.md").lower()
    status = read_rel("quoin/docs/runtime-portability-status.md").lower()

    assert "there is no codex installer" in setup
    assert "global install" in setup
    assert "native planning, approvals, sandboxing" in setup
    assert "status: scaffolded only" in status
    assert "no global codex paths are assumed" in status
    assert "claude code" in status
    assert "status: installable" in status


def test_codex_docs_pin_workflow_artifacts_to_project_root():
    docs = {
        "AGENTS.md": read_rel("AGENTS.md").lower(),
        "quoin/adapters/codex/README.md": read_rel("quoin/adapters/codex/README.md").lower(),
        "quoin/adapters/codex/setup.md": read_rel("quoin/adapters/codex/setup.md").lower(),
    }
    for path, text in docs.items():
        assert "project root" in text, f"{path} must pin the Quoin project root"
        assert ".workflow_artifacts/" in text, f"{path} must mention .workflow_artifacts/"

    setup = docs["quoin/adapters/codex/setup.md"]
    assert "not inside a nested application or package directory" in setup
    assert "nested subdirectory" in setup


def test_readme_preserves_claude_install_command():
    readme = read_rel("README.md")
    assert "bash quoin/install.sh" in readme
    assert "runtime-portability-status.md" in readme

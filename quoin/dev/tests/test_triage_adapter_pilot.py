from pathlib import Path

THIS_FILE = Path(__file__).resolve()
TESTS_DIR = THIS_FILE.parent
PKG_DIR = TESTS_DIR.parent.parent              # quoin/quoin/
CORE_SKILL_DOC = PKG_DIR / "core" / "skills" / "triage.md"
ADAPTER_SKILL_MD = PKG_DIR / "adapters" / "claude" / "skills" / "triage" / "SKILL.md"
LEGACY_SKILL_MD = PKG_DIR / "skills" / "triage" / "SKILL.md"
INSTALL_SH = PKG_DIR / "install.sh"

# Per architecture R-2: triage core doc forbids the slash token /triage,
# the deploy path ~/.claude, and Claude-specific model/dispatch tokens.
FORBIDDEN_TOKENS = ("~/.claude", "/triage", "Haiku", "Sonnet", "Opus", "Agent")
# Anchored on the input-root path (triage has no single output path; it
# reads workflow-state signals from this root).
REQUIRED_MENTION = ".workflow_artifacts/"


def test_core_skill_doc_exists():
    assert CORE_SKILL_DOC.is_file(), f"Missing {CORE_SKILL_DOC}"


def test_core_skill_doc_has_no_forbidden_tokens():
    text = CORE_SKILL_DOC.read_text(encoding="utf-8")
    hits = [t for t in FORBIDDEN_TOKENS if t in text]
    assert not hits, f"Core doc contains forbidden tokens: {hits}"


def test_core_skill_doc_mentions_workflow_artifacts_root():
    text = CORE_SKILL_DOC.read_text(encoding="utf-8")
    assert REQUIRED_MENTION in text, (
        f"Core doc must mention literal: {REQUIRED_MENTION}"
    )


def test_adapter_skill_md_exists():
    assert ADAPTER_SKILL_MD.is_file(), f"Missing {ADAPTER_SKILL_MD}"


def test_adapter_skill_md_declares_haiku():
    import yaml
    text = ADAPTER_SKILL_MD.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    assert len(parts) >= 3, "Adapter SKILL.md missing YAML frontmatter"
    fm = yaml.safe_load(parts[1])
    assert fm.get("model") == "haiku", (
        f"Adapter SKILL.md must declare model: haiku (got {fm.get('model')!r})"
    )
    assert fm.get("name") == "triage"


def test_adapter_skill_md_references_core_doc():
    text = ADAPTER_SKILL_MD.read_text(encoding="utf-8")
    assert "/triage" in text, (
        "Adapter SKILL.md should mention /triage"
    )
    assert "quoin/core/skills/triage.md" in text, (
        "Adapter SKILL.md must reference the portable intent doc path"
    )


def test_install_sh_has_triage_override():
    text = INSTALL_SH.read_text(encoding="utf-8")
    assert "ADAPTER_TRIAGE_SRC" in text, (
        "install.sh missing ADAPTER_TRIAGE_SRC variable"
    )
    assert 'elif [ "$skill_name" = "triage" ]' in text, (
        "install.sh missing per-skill override branch for triage"
    )
    # Pre-flight check must appear before the skills loop.
    preflight_idx = text.find("ADAPTER_TRIAGE_SRC=")
    loop_idx = text.find('for skill_dir in "$SCRIPT_DIR/skills"/*/')
    assert preflight_idx != -1 and loop_idx != -1
    assert preflight_idx < loop_idx, (
        "Pre-flight existence check must appear BEFORE the skills loop"
    )


def test_legacy_and_adapter_skill_md_differ():
    """Adapter must contain full body (incl. §0); legacy is a short stub."""
    legacy_bytes = LEGACY_SKILL_MD.read_bytes()
    adapter_bytes = ADAPTER_SKILL_MD.read_bytes()
    assert legacy_bytes != adapter_bytes, (
        "Legacy stub and adapter SKILL.md must differ — "
        "the legacy file should be a short deprecated pointer"
    )
    assert len(legacy_bytes) < len(adapter_bytes), (
        "Legacy stub should be shorter than the full adapter SKILL.md"
    )


def test_legacy_stub_frontmatter_byte_equals_adapter():
    """Per architecture R-7: stub frontmatter MUST byte-equal adapter
    frontmatter so that triage's runtime trigger-phrase stripping (which
    parses its own description: field) is independent of which file is
    read by tooling."""
    legacy_text = LEGACY_SKILL_MD.read_text(encoding="utf-8")
    adapter_text = ADAPTER_SKILL_MD.read_text(encoding="utf-8")
    legacy_fm = legacy_text.split("---", 2)[1]
    adapter_fm = adapter_text.split("---", 2)[1]
    assert legacy_fm == adapter_fm, (
        "Legacy stub frontmatter must byte-equal adapter frontmatter. "
        "Drift here causes silent runtime divergence."
    )

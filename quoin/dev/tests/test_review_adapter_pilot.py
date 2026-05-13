from pathlib import Path

THIS_FILE = Path(__file__).resolve()
TESTS_DIR = THIS_FILE.parent
PKG_DIR = TESTS_DIR.parent.parent              # quoin/quoin/
CORE_SKILL_DOC = PKG_DIR / "core" / "skills" / "review.md"
ADAPTER_SKILL_MD = PKG_DIR / "adapters" / "claude" / "skills" / "review" / "SKILL.md"
LEGACY_SKILL_MD = PKG_DIR / "skills" / "review" / "SKILL.md"
INSTALL_SH = PKG_DIR / "install.sh"

# review is Opus-tier — forbidden tokens mirror the existing pilot tests plus gh CLI.
FORBIDDEN_TOKENS = ("~/.claude", "/review", "Haiku", "Sonnet", "Opus", "Agent", "gh CLI")
# Load-bearing input/output anchor for the review skill.
REQUIRED_MENTION = ".workflow_artifacts/<task-name>/"


def test_core_skill_doc_exists():
    assert CORE_SKILL_DOC.is_file(), f"Missing {CORE_SKILL_DOC}"


def test_core_skill_doc_has_no_forbidden_tokens():
    text = CORE_SKILL_DOC.read_text(encoding="utf-8")
    hits = [t for t in FORBIDDEN_TOKENS if t in text]
    assert not hits, f"Core doc contains forbidden tokens: {hits}"


def test_core_skill_doc_mentions_task_artifact_anchor():
    text = CORE_SKILL_DOC.read_text(encoding="utf-8")
    assert REQUIRED_MENTION in text, (
        f"Core doc must mention literal: {REQUIRED_MENTION}"
    )


def test_adapter_skill_md_exists():
    assert ADAPTER_SKILL_MD.is_file(), f"Missing {ADAPTER_SKILL_MD}"


def test_adapter_skill_md_declares_opus():
    import yaml
    text = ADAPTER_SKILL_MD.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    assert len(parts) >= 3, "Adapter SKILL.md missing YAML frontmatter"
    fm = yaml.safe_load(parts[1])
    assert fm.get("model") == "opus", (
        f"Adapter SKILL.md must declare model: opus (got {fm.get('model')!r})"
    )
    assert fm.get("name") == "review"


def test_adapter_skill_md_references_core_doc():
    text = ADAPTER_SKILL_MD.read_text(encoding="utf-8")
    assert "quoin/core/skills/review.md" in text, (
        "Adapter SKILL.md must reference the portable intent doc path"
    )


def test_install_sh_has_review_override():
    text = INSTALL_SH.read_text(encoding="utf-8")
    assert "ADAPTER_REVIEW_SRC" in text, (
        "install.sh missing ADAPTER_REVIEW_SRC variable"
    )
    assert 'elif [ "$skill_name" = "review" ]' in text, (
        "install.sh missing per-skill override branch for review"
    )
    # Pre-flight check must appear before the skills loop.
    preflight_idx = text.find("ADAPTER_REVIEW_SRC=")
    loop_idx = text.find('for skill_dir in "$SCRIPT_DIR/skills"/*/')
    assert preflight_idx != -1 and loop_idx != -1
    assert preflight_idx < loop_idx, (
        "Pre-flight existence check must appear BEFORE the skills loop"
    )


def test_legacy_and_adapter_skill_md_differ():
    """Adapter must contain full body; legacy is a short stub."""
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
    """Stub frontmatter MUST byte-equal adapter frontmatter."""
    legacy_text = LEGACY_SKILL_MD.read_text(encoding="utf-8")
    adapter_text = ADAPTER_SKILL_MD.read_text(encoding="utf-8")
    legacy_fm = legacy_text.split("---", 2)[1]
    adapter_fm = adapter_text.split("---", 2)[1]
    assert legacy_fm == adapter_fm, (
        "Legacy stub frontmatter must byte-equal adapter frontmatter. "
        "Drift here causes silent runtime divergence."
    )


def test_adapter_skill_md_does_not_have_section_0_dispatch():
    """review is Opus-tier — MUST NOT carry the §0 Model dispatch block."""
    text = ADAPTER_SKILL_MD.read_text(encoding="utf-8")
    assert "§0 Model dispatch" not in text, (
        "review adapter SKILL.md must not carry §0 dispatch block (Opus-tier skill)"
    )
    assert "## §0" not in text, (
        "review adapter SKILL.md must not have a ## §0 heading (Opus-tier skill)"
    )

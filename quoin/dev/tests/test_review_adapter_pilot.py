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


# ── IVG-70: Branch-hygiene review backstop assertions ─────────────────────


def test_review_adapter_has_step_6a_branch_placement():
    """IVG-70 T-08 AC-1: review adapter SKILL.md must contain ### Step 6a branch placement backstop."""
    text = ADAPTER_SKILL_MD.read_text(encoding="utf-8")
    assert "### Step 6a" in text, (
        "review adapter SKILL.md must contain '### Step 6a' (branch placement backstop). "
        "IVG-70 T-06 edit is missing or was reverted."
    )


def test_review_adapter_step_6a_references_branch_hygiene():
    """IVG-70 T-08 AC-1: Step 6a must reference branch_hygiene.py."""
    text = ADAPTER_SKILL_MD.read_text(encoding="utf-8")
    assert "branch_hygiene.py" in text, (
        "review adapter SKILL.md must reference 'branch_hygiene.py' in the "
        "Step 6a backstop. IVG-70 T-06 edit is missing or was reverted."
    )


def test_review_adapter_step_6a_is_diff_independent():
    """IVG-70 T-08 AC-3: Step 6a must state it runs unconditionally/independently of the diff."""
    text = ADAPTER_SKILL_MD.read_text(encoding="utf-8")
    # The section must mention unconditional or independent execution
    assert "unconditionally" in text or "independently" in text, (
        "review adapter SKILL.md Step 6a must state it runs unconditionally / "
        "independently of the git diff basis. IVG-70 T-06 AC-3 guard failed."
    )


def test_review_adapter_step_6a_uses_pwd_root():
    """IVG-70 T-08 AC-1: Step 6a must use $(pwd) for root resolution (review runs inline)."""
    text = ADAPTER_SKILL_MD.read_text(encoding="utf-8")
    assert "$(pwd)" in text, (
        "review adapter SKILL.md Step 6a must use '$(pwd)' for project root "
        "(review runs inline at project-root cwd — no walk-up needed). "
        "IVG-70 T-06 AC-1 guard failed."
    )


def test_review_core_doc_has_placement_backstop_rule():
    """IVG-70 T-08 AC-2: core review.md Behavior contract must contain the backstop line."""
    text = CORE_SKILL_DOC.read_text(encoding="utf-8")
    assert "protected branch" in text, (
        "core/skills/review.md must mention 'protected branch' in the Behavior contract. "
        "IVG-70 T-06 core doc edit is missing or was reverted."
    )


def test_review_core_doc_no_adapter_specific_refs():
    """IVG-70 T-08: core review.md must NOT contain branch_hygiene.py or __QUOIN_HOME__."""
    text = CORE_SKILL_DOC.read_text(encoding="utf-8")
    assert "branch_hygiene.py" not in text, (
        "core/skills/review.md must NOT contain 'branch_hygiene.py' "
        "(adapter-specific). IVG-70 adapter/core boundary violated."
    )
    assert "__QUOIN_HOME__" not in text, (
        "core/skills/review.md must NOT contain '__QUOIN_HOME__' "
        "(adapter-specific). IVG-70 adapter/core boundary violated."
    )

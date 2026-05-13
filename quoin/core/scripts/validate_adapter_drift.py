#!/usr/bin/env python3
"""Adapter drift validator — Phase 22 runtime-portability work.

Reads quoin/core/workflow/skills.json and asserts per-skill structural
invariants across core/, adapters/claude/, and legacy skills/ trees.

Lives in core/scripts/ because the manifest and the artifact-path
conventions are runtime-neutral; references to ## §0 dispatch and
adapters/claude/ are Claude-specific by necessity — see Decisions D-09
in the Phase 22 plan.

revise-fast uses a See-also form for AD-PT because it shares the
revise.md intent doc; the substring check preserves the Phase 21 contract.
A future phase may tighten to a canonical single-line pointer.

capture_insight is the lead if-branch (Phase 6 migration) in install.sh.
Normalizing to elif would break bash control flow.

Usage:
    python3 validate_adapter_drift.py [--manifest PATH] [--repo-root PATH] [--json]

Exit codes:
    0   PASS — no violations
    2   DRIFT — one or more violations detected
    64  USAGE — bad CLI arguments
    65  DATA — manifest unreadable or malformed
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Invariant IDs (stable contract — tests assert by ID, not by prose)
#
# Violations are emitted as one of the following prefixes:
# DRIFT AD-CO  (core-doc-exists)
# DRIFT AD-AD  (adapter-doc-exists)
# DRIFT AD-LS  (legacy-stub-exists)
# DRIFT AD-FN  (frontmatter-name)
# DRIFT AD-FM  (frontmatter-model)
# DRIFT AD-PT  (pointer-text)
# DRIFT AD-FB  (frontmatter-byte-equal)
# DRIFT AD-SS  (stub-shorter)
# DRIFT AD-S0P (section-0-present)
# DRIFT AD-S0A (section-0-absent)
# DRIFT AD-PE  (preamble-present)
# DRIFT AD-PA  (preamble-absent-elsewhere)
# DRIFT AD-PX  (preamble-not-present-for-non-spawn)
# DRIFT AD-IV  (install.sh-variable)
# DRIFT AD-IE  (install.sh-branch)
# DRIFT AD-IO  (install.sh-ordering)
# ---------------------------------------------------------------------------
AD_CO = "AD-CO"   # core-doc-exists
AD_AD = "AD-AD"   # adapter-doc-exists
AD_LS = "AD-LS"   # legacy-stub-exists
AD_FN = "AD-FN"   # frontmatter-name
AD_FM = "AD-FM"   # frontmatter-model
AD_PT = "AD-PT"   # pointer-text (Phase 21 substring contract)
AD_FB = "AD-FB"   # frontmatter-byte-equal
AD_SS = "AD-SS"   # stub-shorter
AD_S0P = "AD-S0P" # section-0-present
AD_S0A = "AD-S0A" # section-0-absent
AD_PE = "AD-PE"   # preamble-present (spawn targets)
AD_PA = "AD-PA"   # preamble-absent-elsewhere (spawn targets: no preamble in adapter folder)
AD_PX = "AD-PX"   # preamble-not-present-for-non-spawn
AD_IV = "AD-IV"   # install.sh-variable
AD_IE = "AD-IE"   # install.sh-branch
AD_IO = "AD-IO"   # install.sh-ordering


# ---------------------------------------------------------------------------
# Section-0 regex (line-anchored per D-13)
# ---------------------------------------------------------------------------
_S0_PATTERN = re.compile(r"^## §0 Model dispatch \(FIRST STEP", re.MULTILINE)


def _default_repo_root() -> Path:
    """Two parents above this script puts us at the quoin package's parent (the repo root)."""
    return Path(__file__).resolve().parents[3]


def _default_manifest(repo_root: Path) -> Path:
    return repo_root / "quoin" / "core" / "workflow" / "skills.json"


# ---------------------------------------------------------------------------
# Manifest loading
# ---------------------------------------------------------------------------

def load_manifest(path: Path) -> Dict[str, Any]:
    """Load and minimally validate the skills manifest. Exit 65 on errors."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"DATA: cannot read manifest {path}: {exc}", file=sys.stderr)
        sys.exit(65)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"DATA: manifest is not valid JSON: {exc}", file=sys.stderr)
        sys.exit(65)
    if "skills" not in data or not isinstance(data["skills"], list):
        print("DATA: manifest missing 'skills' list", file=sys.stderr)
        sys.exit(65)
    return data


# ---------------------------------------------------------------------------
# Frontmatter helpers
# ---------------------------------------------------------------------------

def _extract_frontmatter(text: str) -> Optional[str]:
    """Extract the raw YAML between the first pair of --- fences."""
    parts = text.replace("\r\n", "\n").split("---", 2)
    if len(parts) < 3:
        return None
    return parts[1]


def _parse_frontmatter_field(frontmatter: str, field: str) -> Optional[str]:
    """Extract a simple scalar field from YAML frontmatter via regex."""
    m = re.search(rf"^{re.escape(field)}:\s*(\S+)", frontmatter, re.MULTILINE)
    return m.group(1) if m else None


# ---------------------------------------------------------------------------
# Per-skill check functions
# ---------------------------------------------------------------------------

def check_files_exist(
    name: str,
    repo_root: Path,
    violations: List[Dict[str, str]],
) -> Tuple[bool, bool, bool]:
    """AD-CO, AD-AD, AD-LS: verify all three files exist.

    Returns (core_ok, adapter_ok, stub_ok) so callers can skip dependent checks.
    """
    core_path = repo_root / "quoin" / "core" / "skills" / f"{name}.md"
    adapter_path = repo_root / "quoin" / "adapters" / "claude" / "skills" / name / "SKILL.md"
    stub_path = repo_root / "quoin" / "skills" / name / "SKILL.md"

    core_ok = core_path.is_file()
    adapter_ok = adapter_path.is_file()
    stub_ok = stub_path.is_file()

    if not core_ok:
        violations.append({
            "invariant": AD_CO,
            "skill": name,
            "detail": f"missing quoin/core/skills/{name}.md",
        })
    if not adapter_ok:
        violations.append({
            "invariant": AD_AD,
            "skill": name,
            "detail": f"missing quoin/adapters/claude/skills/{name}/SKILL.md",
        })
    if not stub_ok:
        violations.append({
            "invariant": AD_LS,
            "skill": name,
            "detail": f"missing quoin/skills/{name}/SKILL.md",
        })

    return core_ok, adapter_ok, stub_ok


def check_frontmatter(
    name: str,
    claude_model: str,
    repo_root: Path,
    violations: List[Dict[str, str]],
) -> None:
    """AD-FN, AD-FM: adapter frontmatter name and model fields."""
    adapter_path = repo_root / "quoin" / "adapters" / "claude" / "skills" / name / "SKILL.md"
    text = adapter_path.read_text(encoding="utf-8")
    fm = _extract_frontmatter(text)
    if fm is None:
        violations.append({
            "invariant": AD_FN,
            "skill": name,
            "detail": "adapter SKILL.md has no YAML frontmatter",
        })
        return

    fm_name = _parse_frontmatter_field(fm, "name")
    if fm_name != name:
        violations.append({
            "invariant": AD_FN,
            "skill": name,
            "detail": f"adapter frontmatter name={fm_name!r} expected {name!r}",
        })

    fm_model = _parse_frontmatter_field(fm, "model")
    if fm_model != claude_model:
        violations.append({
            "invariant": AD_FM,
            "skill": name,
            "detail": f"adapter frontmatter model={fm_model!r} expected {claude_model!r} (from manifest)",
        })


def check_pointer(
    name: str,
    repo_root: Path,
    violations: List[Dict[str, str]],
) -> None:
    """AD-PT: adapter body contains 'quoin/core/skills/<name>.md' as substring.

    This is the Phase 21 substring contract (relaxed from an exact pointer-line regex).
    For revise-fast, the substring appears on the See-also line, not on the primary
    pointer line (which points to quoin/core/skills/revise.md). Both are intentional.
    """
    adapter_path = repo_root / "quoin" / "adapters" / "claude" / "skills" / name / "SKILL.md"
    content = adapter_path.read_text(encoding="utf-8")
    needle = f"quoin/core/skills/{name}.md"
    if needle not in content:
        violations.append({
            "invariant": AD_PT,
            "skill": name,
            "detail": f"adapter does not contain substring {needle!r}",
        })


def check_stub_relationship(
    name: str,
    repo_root: Path,
    violations: List[Dict[str, str]],
) -> None:
    """AD-FB, AD-SS: stub frontmatter byte-equals adapter; stub is shorter than adapter."""
    adapter_path = repo_root / "quoin" / "adapters" / "claude" / "skills" / name / "SKILL.md"
    stub_path = repo_root / "quoin" / "skills" / name / "SKILL.md"

    adapter_text = adapter_path.read_text(encoding="utf-8").replace("\r\n", "\n")
    stub_text = stub_path.read_text(encoding="utf-8").replace("\r\n", "\n")

    adapter_fm = _extract_frontmatter(adapter_text)
    stub_fm = _extract_frontmatter(stub_text)

    if adapter_fm is None or stub_fm is None:
        violations.append({
            "invariant": AD_FB,
            "skill": name,
            "detail": "could not extract frontmatter from adapter or stub",
        })
    elif adapter_fm != stub_fm:
        violations.append({
            "invariant": AD_FB,
            "skill": name,
            "detail": "legacy stub frontmatter does not byte-equal adapter frontmatter",
        })

    if len(stub_text) >= len(adapter_text):
        violations.append({
            "invariant": AD_SS,
            "skill": name,
            "detail": (
                f"stub ({len(stub_text)} bytes) is not shorter than "
                f"adapter ({len(adapter_text)} bytes)"
            ),
        })


def check_section_0(
    name: str,
    section_0: bool,
    repo_root: Path,
    violations: List[Dict[str, str]],
) -> None:
    """AD-S0P / AD-S0A: section-0 presence matches manifest declaration."""
    adapter_path = repo_root / "quoin" / "adapters" / "claude" / "skills" / name / "SKILL.md"
    content = adapter_path.read_text(encoding="utf-8")
    has_s0 = bool(_S0_PATTERN.search(content))

    if section_0 and not has_s0:
        violations.append({
            "invariant": AD_S0P,
            "skill": name,
            "detail": (
                "manifest declares section_0=true but adapter is missing "
                "'## §0 Model dispatch (FIRST STEP' (line-anchored)"
            ),
        })
    elif not section_0 and has_s0:
        violations.append({
            "invariant": AD_S0A,
            "skill": name,
            "detail": (
                "manifest declares section_0=false but adapter contains "
                "'## §0 Model dispatch (FIRST STEP' at line start"
            ),
        })


def check_preamble(
    name: str,
    spawn_target: bool,
    repo_root: Path,
    violations: List[Dict[str, str]],
) -> None:
    """AD-PE, AD-PA, AD-PX: preamble presence matches spawn_target declaration."""
    stub_preamble = repo_root / "quoin" / "skills" / name / "preamble.md"
    adapter_preamble = repo_root / "quoin" / "adapters" / "claude" / "skills" / name / "preamble.md"

    if spawn_target:
        # AD-PE: preamble.md must exist in the legacy stub dir (install.sh copies from there)
        if not stub_preamble.is_file():
            violations.append({
                "invariant": AD_PE,
                "skill": name,
                "detail": f"spawn_target=true but missing quoin/skills/{name}/preamble.md",
            })
        # AD-PA: preamble.md must NOT exist in the adapter folder (would be a confusing duplicate)
        if adapter_preamble.is_file():
            violations.append({
                "invariant": AD_PA,
                "skill": name,
                "detail": (
                    f"spawn_target=true and preamble.md also exists at "
                    f"quoin/adapters/claude/skills/{name}/preamble.md (must not be there)"
                ),
            })
    else:
        # AD-PX: neither location should have a preamble.md
        if stub_preamble.is_file():
            violations.append({
                "invariant": AD_PX,
                "skill": name,
                "detail": (
                    f"spawn_target=false but preamble.md exists at "
                    f"quoin/skills/{name}/preamble.md"
                ),
            })
        if adapter_preamble.is_file():
            violations.append({
                "invariant": AD_PX,
                "skill": name,
                "detail": (
                    f"spawn_target=false but preamble.md exists at "
                    f"quoin/adapters/claude/skills/{name}/preamble.md"
                ),
            })


# ---------------------------------------------------------------------------
# install.sh checks
# ---------------------------------------------------------------------------

def _name_upper(name: str) -> str:
    """Convert skill name to UPPER_CASE var name (revise-fast → REVISE_FAST)."""
    return name.upper().replace("-", "_")


def check_install_sh(
    name: str,
    install_sh_content: str,
    violations: List[Dict[str, str]],
) -> bool:
    """AD-IV, AD-IE: install.sh has the preflight var and branch for this skill.

    Returns True if AD-IV passed (preflight var found), so check_install_sh_ordering
    knows whether to also check ordering for this skill.
    """
    name_up = _name_upper(name)

    # AD-IV: ADAPTER_<NAME_UPPER>_SRC= assignment exists
    iv_needle = f"ADAPTER_{name_up}_SRC="
    iv_ok = iv_needle in install_sh_content
    if not iv_ok:
        violations.append({
            "invariant": AD_IV,
            "skill": name,
            "detail": f"install.sh missing '{iv_needle}' preflight assignment",
        })

    # AD-IE: if/elif branch exists
    # capture_insight is the lead `if` (Phase 6); all others use `elif`
    ie_pattern = re.compile(
        rf'^\s*(if|elif) \[ "\$skill_name" = "{re.escape(name)}" \]',
        re.MULTILINE,
    )
    if not ie_pattern.search(install_sh_content):
        violations.append({
            "invariant": AD_IE,
            "skill": name,
            "detail": (
                f"install.sh missing if/elif branch for skill '{name}'. "
                f"Note: capture_insight is the lead if-branch (Phase 6 migration)."
            ),
        })

    return iv_ok


def check_install_sh_ordering(
    skills: List[Dict[str, Any]],
    install_sh_content: str,
    skills_with_iv: List[str],
    violations: List[Dict[str, str]],
) -> None:
    """AD-IO: each ADAPTER_<NAME>_SRC= assignment appears before the for-loop start.

    Only checked for skills that passed AD-IV (those in skills_with_iv).
    """
    for_loop_needle = 'for skill_dir in "$SCRIPT_DIR/skills"/*/'
    for_loop_offset = install_sh_content.find(for_loop_needle)
    if for_loop_offset == -1:
        # Cannot locate for-loop — skip ordering check
        return

    for name in skills_with_iv:
        name_up = _name_upper(name)
        iv_needle = f"ADAPTER_{name_up}_SRC="
        preflight_offset = install_sh_content.find(iv_needle)
        if preflight_offset == -1:
            # Should not happen if skills_with_iv is correct, but be safe
            continue
        if preflight_offset > for_loop_offset:
            violations.append({
                "invariant": AD_IO,
                "skill": name,
                "detail": (
                    f"preflight ADAPTER_{name_up}_SRC= at byte offset {preflight_offset} "
                    f"is after for-loop start at byte offset {for_loop_offset}"
                ),
            })


# ---------------------------------------------------------------------------
# Emit violations
# ---------------------------------------------------------------------------

def emit_violations(violations: List[Dict[str, str]], as_json: bool) -> None:
    if as_json:
        print(json.dumps({"violations": violations}, indent=2))
    else:
        for v in violations:
            print(
                f"DRIFT {v['invariant']} {v['skill']}: {v['detail']}",
                file=sys.stderr,
            )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate adapter drift across core/, adapters/claude/, and skills/ trees.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help="Path to skills.json manifest (default: auto-detected from repo root)",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Path to the quoin repo root (default: auto-detected from script location)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Emit violations as JSON to stdout instead of human-readable lines on stderr",
    )

    try:
        args = parser.parse_args(argv)
    except SystemExit:
        sys.exit(64)

    repo_root: Path = args.repo_root if args.repo_root is not None else _default_repo_root()
    manifest_path: Path = args.manifest if args.manifest is not None else _default_manifest(repo_root)

    manifest = load_manifest(manifest_path)

    # Load install.sh once for all per-skill checks
    install_sh_path = repo_root / "quoin" / "install.sh"
    try:
        install_sh_content = install_sh_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"DATA: cannot read install.sh at {install_sh_path}: {exc}", file=sys.stderr)
        sys.exit(65)

    violations: List[Dict[str, str]] = []
    skills_with_iv: List[str] = []  # skills that passed AD-IV (for AD-IO ordering check)

    for skill in manifest["skills"]:
        name: str = skill["name"]
        claude_model: str = skill["claude_model"]
        section_0: bool = bool(skill.get("section_0", False))
        spawn_target: bool = bool(skill.get("spawn_target", False))

        core_ok, adapter_ok, stub_ok = check_files_exist(name, repo_root, violations)

        if adapter_ok:
            check_frontmatter(name, claude_model, repo_root, violations)
            check_pointer(name, repo_root, violations)
            check_section_0(name, section_0, repo_root, violations)

        if adapter_ok and stub_ok:
            check_stub_relationship(name, repo_root, violations)

        check_preamble(name, spawn_target, repo_root, violations)

        iv_ok = check_install_sh(name, install_sh_content, violations)
        if iv_ok:
            skills_with_iv.append(name)

    check_install_sh_ordering(
        manifest["skills"], install_sh_content, skills_with_iv, violations
    )

    emit_violations(violations, args.json)

    return 2 if violations else 0


if __name__ == "__main__":
    sys.exit(main())

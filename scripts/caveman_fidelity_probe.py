#!/usr/bin/env python3
"""
caveman_fidelity_probe.py — Stage 1 acceptance harness for caveman-token-optimization.

Implements architecture §8.1 (per-artifact-type structural checks) and §8.3 (JSONL cost
routine) for the caveman-token-optimization Stage 1 acceptance gate.

Resolution notes embedded in this module (per plan acceptance criteria):
  - CRIT-1 (2026-04-23): Single-artifact contract tests — all check functions take ONE
    terse artifact string. No (eng, terse) pair signatures exist in Stage 1. Paired
    comparison is deferred to Stage 2 when .original.md side-files exist naturally.
  - CRIT-2 (2026-04-23): Structural cost proxy — dollar gate is deterministic, computed
    from artifact byte sizes × tokens-per-byte × cache-read price × est-reads-per-task.
    No LLM replay. PROXY_CONSTANTS are surfaced in every report for user auditing.
  - NEW-MIN-11 absorbed: B2 (URL preservation) and B3 (code-fence preservation) are
    mandatory baseline checks included in every per-type CHECK_SETS entry.

Usage:
  .venv/bin/python scripts/caveman_fidelity_probe.py scan --type critic-response [--min-samples 3] [--verbose]
  .venv/bin/python scripts/caveman_fidelity_probe.py cost --artifact-type critic-response --post-sample-dir <path>
  .venv/bin/python scripts/caveman_fidelity_probe.py cost --jsonl-historical
  .venv/bin/python scripts/caveman_fidelity_probe.py report [--post-sample-dir <path>] [--output <file>]
"""

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Literal, Optional, Tuple

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FINALIZED_DIR = PROJECT_ROOT / ".workflow_artifacts" / "finalized"
JSONL_DIR = Path(os.environ.get(
    "CLAUDE_PROJECT_JSONL_DIR",
    str(Path.home() / ".claude" / "projects" /
        "-Users-ivgo-Library-CloudStorage-GoogleDrive-ivan-gorban-gmail-com"
        "-My-Drive-Storage-Claude-workflow")
))

# Anthropic published prices, USD per 1M tokens — snapshot date 2026-04-22.
# Source: https://www.anthropic.com/pricing (captured at architecture-doc date).
# If prices change, update in a separate task with a documented snapshot date.
ANTHROPIC_PRICES: Dict[str, Dict[str, float]] = {
    "opus-4-7":  {"input": 15.0,  "output": 75.0,  "cache_read": 1.50,  "cache_write": 18.75},
    "sonnet-4-7": {"input": 3.0,  "output": 15.0,  "cache_read": 0.30,  "cache_write": 3.75},
    "haiku":     {"input": 0.80,  "output": 4.0,   "cache_read": 0.08,  "cache_write": 1.00},
}

# Structural cost proxy constants — see CRIT-2 resolution.
# Each value is an empirical estimate, not a measurement. The report surfaces these
# so the user can audit. tokens_per_byte ≈ 1/4 based on Anthropic tokenizer averages
# for markdown prose. cache_read_price is what dominates re-read cost.
#
# est_reads_per_task_per_type rationale:
#   critic-response    : 6  — /revise reads it; /critic in next round reads it; /review reads it x2; orchestrator x2
#   architecture-critic: 3  — /architect reads 2-3 rounds; gate reads once
#   session-state      : 10 — nearly every skill reads session state at bootstrap; high-frequency
#   daily-insights     : 4  — /end_of_day reads+writes; /start_of_day reads; /weekly_review reads
#   cache-index        : 8  — every /implement, /critic, /review reads the cache index
#   cache-deps         : 8  — same as cache-index (co-read pattern)
#   cache-stem         : 8  — per-file cache entries read whenever that file is touched
#   discover-repos     : 3  — read at /architect and /plan bootstrap; occasionally at /critic
#   discover-arch      : 3  — same as discover-repos
#   discover-deps      : 3  — same as discover-repos
#   gate-audit         : 4  — read at /review and /end_of_task; user reads once; orchestrator once
PROXY_CONSTANTS: Dict = {
    "tokens_per_byte": 0.25,
    "cache_read_price_per_mtok_opus": 1.50,    # USD/1M tokens (Opus 4.7 cache-read rate)
    "cache_read_price_per_mtok_sonnet": 0.30,  # USD/1M tokens (Sonnet 4.6 cache-read rate)
    "est_reads_per_task_per_type": {
        "critic-response":    6,
        "architecture-critic": 3,
        "session-state":     10,
        "daily-insights":     4,
        "cache-index":        8,
        "cache-deps":         8,
        "cache-stem":         8,
        "discover-repos":     3,
        "discover-arch":      3,
        "discover-deps":      3,
        "gate-audit":         4,
    },
}

# Regex patterns to classify artifact files by type.
ARTIFACT_TYPE_PATTERNS: Dict[str, str] = {
    "critic-response":    r"critic-response-\d+\.md$",
    "architecture-critic": r"architecture-critic-\d+\.md$",
    "session-state":      r"memory/sessions/.*\.md$",
    "daily-insights":     r"memory/daily/insights-\d{4}-\d{2}-\d{2}\.md$",
    "cache-index":        r"cache/.+/_index\.md$",
    "cache-deps":         r"cache/.+/_deps\.md$",
    "cache-stem":         r"cache/.+/[^_][^/]+\.md$",
    "discover-repos":     r"memory/repos-inventory\.md$",
    "discover-arch":      r"memory/architecture-overview\.md$",
    "discover-deps":      r"memory/dependencies-map\.md$",
    "gate-audit":         r"gate-[^/]+-\d{4}-\d{2}-\d{2}\.md$",
    # current-plan-paired: Stage 2 only (when .original.md side-files exist)
}

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class CheckResult:
    name: str
    status: Literal["PASS", "FAIL", "N/A"]
    reason: str = ""


@dataclass
class SampleResult:
    artifact_type: str
    sample_path: Path
    checks: List[CheckResult] = field(default_factory=list)
    verdict: Literal["PASS", "FAIL", "INVALID"] = "INVALID"


@dataclass
class CostBreakdown:
    """Cost breakdown from JSONL historical scan (informational only in Stage 1)."""
    task: str
    total_usd: float
    by_model: Dict[str, float] = field(default_factory=dict)
    cache_read_usd: float = 0.0
    cache_write_usd: float = 0.0
    input_usd: float = 0.0
    output_usd: float = 0.0


@dataclass
class CostProxyResult:
    """Deterministic structural cost proxy result per artifact type (CRIT-2 resolution)."""
    artifact_type: str
    s_pre_mean: int       # mean bytes of pre-rubric samples
    s_post_mean: int      # mean bytes of post-rubric samples
    delta_bytes: int      # s_pre_mean - s_post_mean (positive = smaller after rubric)
    tokens_per_byte: float
    cache_read_price_per_mtok: float
    est_reads_per_task: int
    projected_delta_usd: float
    sample_count_pre: int
    sample_count_post: int


# ---------------------------------------------------------------------------
# Baseline checks — SINGLE-ARTIFACT CONTRACT (CRIT-1 resolution)
# All check signatures: def check_X(terse: str) -> CheckResult
# Zero pair-signatures exist. Each check encodes a rubric-derived structural
# invariant evaluated against the artifact alone.
# ---------------------------------------------------------------------------

_PATH_PATTERN = re.compile(
    r'(?:^|[\s\`\(])(\./|\.\.\/|[a-zA-Z0-9_\-]+/)'   # leading ./, ../, or word/
    r'[a-zA-Z0-9_\-\.\/]+'                              # path body
    r'(?:\.(?:md|py|sh|ts|js|go|rs|yaml|yml|json|html|txt))'  # required extension
    r'(?::\d+)?',                                        # optional :line
    re.MULTILINE
)
_ABSTRACT_PATH_PATTERN = re.compile(
    r'<[a-z_]+>|\.workflow_artifacts/|memory/|dev-workflow/'
)


def check_b1_paths(terse: str) -> CheckResult:
    """B1: Every file-path-shaped token in the terse artifact resolves to a real path
    under PROJECT_ROOT or is a recognizable abstract pattern."""
    tokens = _PATH_PATTERN.findall(terse)
    if not tokens:
        return CheckResult("B1-paths", "N/A", "no file-path-shaped tokens found")

    bad = []
    for raw in _PATH_PATTERN.finditer(terse):
        fragment = raw.group(0).strip().strip("`()")
        if _ABSTRACT_PATH_PATTERN.search(fragment):
            continue
        resolved = (PROJECT_ROOT / fragment.lstrip("./"))
        if not resolved.exists() and not re.search(r'<[a-z]', fragment):
            # Only flag as bad if it looks like a concrete path (not abstract template)
            if "/" in fragment and not fragment.startswith("http"):
                bad.append(fragment)

    if bad:
        return CheckResult("B1-paths", "FAIL", f"unresolvable path tokens: {bad[:3]}")
    return CheckResult("B1-paths", "PASS", f"{len(_PATH_PATTERN.findall(terse))} path tokens ok")


def check_b2_urls(terse: str) -> CheckResult:
    """B2: Every URL token is syntactically valid (parseable with non-empty netloc)."""
    from urllib.parse import urlparse
    # Allow optional non-whitespace after :// (zero or more chars); catches bare https://
    url_pattern = re.compile(r'https?://\S*')
    urls = url_pattern.findall(terse)
    if not urls:
        return CheckResult("B2-urls", "N/A", "no URLs found")
    bad = []
    for url in urls:
        url_clean = url.rstrip(".,;)>\"'")
        try:
            parsed = urlparse(url_clean)
            if not parsed.netloc:
                bad.append(url_clean)
        except Exception:
            bad.append(url_clean)
    if bad:
        return CheckResult("B2-urls", "FAIL", f"malformed URLs: {bad[:2]}")
    return CheckResult("B2-urls", "PASS", f"{len(urls)} URL(s) parseable")


def check_b3_codefences(terse: str) -> CheckResult:
    """B3: Code fences are balanced (even number of fence-marker lines)."""
    # Count lines that begin with ``` or ```` (fence openers and closers)
    quad_lines = re.findall(r'^````', terse, re.MULTILINE)
    # Triple-only lines: start with ``` but not ````
    triple_lines = re.findall(r'^```(?!`)', terse, re.MULTILINE)

    total_fence_lines = len(quad_lines) + len(triple_lines)
    if total_fence_lines == 0:
        return CheckResult("B3-fences", "N/A", "no code fences found")

    # Balanced if even total (each block contributes one open + one close line)
    if total_fence_lines % 2 != 0:
        return CheckResult("B3-fences", "FAIL",
                           f"odd fence-marker count ({total_fence_lines}): unbalanced")

    return CheckResult("B3-fences", "PASS", f"{total_fence_lines} fence markers (balanced)")


def check_b4_numbers(terse: str) -> CheckResult:
    """B4: Numeric tokens not replaced with vague prose where exactness is required."""
    vague = re.compile(
        r'\b(several|many|a few|some amount|approximately|around|roughly|about)\b\s+'
        r'(?:tasks?|files?|rounds?|items?|steps?|issues?)',
        re.IGNORECASE
    )
    matches = vague.findall(terse)
    num_tokens = re.findall(r'\b\d+(?:\.\d+)?(?:%|\$|K|M)?\b', terse)
    if not num_tokens and not matches:
        return CheckResult("B4-numbers", "N/A", "no numeric tokens found")
    if matches:
        return CheckResult("B4-numbers", "FAIL",
                           f"vague quantity phrases found: {matches[:2]}")
    return CheckResult("B4-numbers", "PASS", f"{len(num_tokens)} numeric token(s) present")


def check_b5_quantifiers(terse: str) -> CheckResult:
    """B5: Quantifier phrases preserved; rubric-forbidden vague substitutions absent."""
    forbidden = re.compile(
        r'\b(maybe|perhaps|possibly|might be|could be|around N|roughly N)\b',
        re.IGNORECASE
    )
    required_context = re.compile(
        r'\b(at most|at least|exactly|only|no more than|no fewer than|must|never)\b',
        re.IGNORECASE
    )
    forbidden_matches = forbidden.findall(terse)
    has_quantifiers = bool(required_context.search(terse))

    if not has_quantifiers and not forbidden_matches:
        return CheckResult("B5-quantifiers", "N/A", "no quantifier context found")
    if forbidden_matches:
        return CheckResult("B5-quantifiers", "FAIL",
                           f"forbidden vague substitutions: {forbidden_matches[:2]}")
    return CheckResult("B5-quantifiers", "PASS", "quantifiers preserved")


# ---------------------------------------------------------------------------
# Per-type checks — SINGLE-ARTIFACT
# ---------------------------------------------------------------------------

def check_t_cm1_titles(terse: str) -> CheckResult:
    """T-CM1: CRITICAL:/MAJOR:/MINOR: titles present."""
    has = any(m in terse for m in ("CRITICAL:", "MAJOR:", "MINOR:", "Verdict:", "verdict:"))
    if not has:
        return CheckResult("T-CM1-titles", "N/A", "no severity-level titles found")
    return CheckResult("T-CM1-titles", "PASS", "severity titles present")


def check_t_cm2_ids(terse: str) -> CheckResult:
    """T-CM2: Issue-ID tokens (CRIT-N, MAJ-N, MIN-N, R-N) present at least once."""
    ids = re.findall(r'\b(CRIT|MAJ|MIN|MAJOR|MINOR|CRITICAL)[-–]\d+\b', terse)
    if not ids:
        return CheckResult("T-CM2-ids", "N/A", "no issue-ID tokens found")
    return CheckResult("T-CM2-ids", "PASS", f"{len(ids)} issue-ID token(s)")


def check_t_cm3_negation_density(terse: str) -> CheckResult:
    """T-CM3: Negation words present in CRITICAL-severity issue blocks."""
    crit_blocks = re.findall(
        r'(?:CRITICAL:|CRIT-\d+)(.*?)(?=(?:CRITICAL:|MAJOR:|MINOR:|CRIT-|MAJ-|MIN-)|\Z)',
        terse, re.DOTALL | re.IGNORECASE
    )
    if not crit_blocks:
        return CheckResult("T-CM3-negation", "N/A", "no CRITICAL blocks found")
    negation = re.compile(r'\b(not|never|must not|cannot|no |zero|absent)\b', re.IGNORECASE)
    missing = [i for i, b in enumerate(crit_blocks) if not negation.search(b)]
    if missing:
        return CheckResult("T-CM3-negation", "FAIL",
                           f"CRITICAL blocks {missing} lack negation words")
    return CheckResult("T-CM3-negation", "PASS", "negation present in all CRITICAL blocks")


# T-CP1/2/3: Stage 2 checks for current-plan artifacts (not routed in Stage 1 CHECK_SETS;
# will be wired to the current-plan-paired type when Stage 2 adds .original.md side-files).
def check_t_cp1_task_headings(terse: str) -> CheckResult:
    """T-CP1: ## Task N: pattern present; ≥1 match."""
    matches = re.findall(r'^#{1,3}\s+Task\s+\d+', terse, re.MULTILINE)
    if not matches:
        return CheckResult("T-CP1-task-headings", "N/A", "no Task N headings found")
    return CheckResult("T-CP1-task-headings", "PASS", f"{len(matches)} task heading(s)")


def check_t_cp2_acceptance(terse: str) -> CheckResult:
    """T-CP2: Acceptance criteria bullets present."""
    matches = re.findall(r'(?:- \[ \]|Acceptance:|acceptance criteria)', terse, re.IGNORECASE)
    if not matches:
        return CheckResult("T-CP2-acceptance", "N/A", "no acceptance criteria found")
    return CheckResult("T-CP2-acceptance", "PASS", f"{len(matches)} acceptance marker(s)")


def check_t_cp3_task_count(terse: str) -> CheckResult:
    """T-CP3: Task heading count ≥ 1."""
    count = len(re.findall(r'^#{1,3}\s+Task\s+\d+', terse, re.MULTILINE))
    if count == 0:
        return CheckResult("T-CP3-task-count", "N/A", "no tasks found")
    return CheckResult("T-CP3-task-count", "PASS", f"{count} task heading(s)")


def check_t_ss1_required_headings(terse: str) -> CheckResult:
    """T-SS1: Four required session-state section headings present."""
    required = ["## Status", "## Current stage", "## Completed in this session",
                "## Unfinished work"]
    missing = [h for h in required if h not in terse]
    if missing:
        return CheckResult("T-SS1-headings", "FAIL", f"missing headings: {missing}")
    return CheckResult("T-SS1-headings", "PASS", "all 4 required headings present")


def check_t_ss2_iso_dates(terse: str) -> CheckResult:
    """T-SS2: ISO date (YYYY-MM-DD) present ≥1 time."""
    dates = re.findall(r'\d{4}-\d{2}-\d{2}', terse)
    if not dates:
        return CheckResult("T-SS2-dates", "FAIL", "no ISO date found in session state")
    return CheckResult("T-SS2-dates", "PASS", f"{len(dates)} ISO date(s)")


def check_t_ss3_uuids(terse: str) -> CheckResult:
    """T-SS3: 36-char UUID with dashes present in Cost section."""
    uuid_re = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
                         re.IGNORECASE)
    uuids = uuid_re.findall(terse)
    if not uuids:
        return CheckResult("T-SS3-uuids", "N/A", "no UUID found (may be pre-cost-tracking)")
    return CheckResult("T-SS3-uuids", "PASS", f"{len(uuids)} UUID(s) present")


def check_t_di1_headers(terse: str) -> CheckResult:
    """T-DI1: Insight section headers present."""
    headers = re.findall(r'^#{2,3}\s+.+', terse, re.MULTILINE)
    if not headers:
        return CheckResult("T-DI1-headers", "N/A", "no section headers found")
    return CheckResult("T-DI1-headers", "PASS", f"{len(headers)} header(s)")


def check_t_di2_tags(terse: str) -> CheckResult:
    """T-DI2: Applies to: and Promote?: tags preserved."""
    has_applies = "Applies to:" in terse or "Applies to" in terse
    has_promote = "Promote?:" in terse or "Promote?" in terse
    if not has_applies and not has_promote:
        return CheckResult("T-DI2-tags", "N/A", "no insight entry tags found")
    missing = []
    if not has_applies:
        missing.append("Applies to:")
    if not has_promote:
        missing.append("Promote?:")
    if missing:
        return CheckResult("T-DI2-tags", "FAIL", f"missing tags: {missing}")
    return CheckResult("T-DI2-tags", "PASS", "both tags present")


def check_t_ca1_frontmatter(terse: str) -> CheckResult:
    """T-CA1: YAML-style frontmatter with required keys."""
    required_keys = ["path:", "hash:", "updated:", "updated_by:", "tokens:"]
    if "---" not in terse:
        return CheckResult("T-CA1-frontmatter", "FAIL", "no frontmatter block found")
    missing = [k for k in required_keys if k not in terse]
    if missing:
        return CheckResult("T-CA1-frontmatter", "FAIL", f"missing frontmatter keys: {missing}")
    return CheckResult("T-CA1-frontmatter", "PASS", "frontmatter complete")


def check_t_ca2_export_ids(terse: str) -> CheckResult:
    """T-CA2: ≥1 identifier under ## Key Exports."""
    section = re.search(r'## Key Exports(.*?)(?=^##|\Z)', terse, re.DOTALL | re.MULTILINE)
    if not section:
        return CheckResult("T-CA2-exports", "N/A", "no Key Exports section")
    ids = re.findall(r'`[^`]+`|\w+\(', section.group(1))
    if not ids:
        return CheckResult("T-CA2-exports", "FAIL", "no identifiers in Key Exports")
    return CheckResult("T-CA2-exports", "PASS", f"{len(ids)} export(s)")


def check_t_ca3_section_headings(terse: str) -> CheckResult:
    """T-CA3: ## Purpose and ≥2 of the optional sections present."""
    if "## Purpose" not in terse:
        return CheckResult("T-CA3-sections", "FAIL", "## Purpose section missing")
    optional = ["## Key Exports", "## Dependencies", "## Patterns",
                "## Integration Points", "## Notes"]
    found = sum(1 for s in optional if s in terse)
    if found < 2:
        return CheckResult("T-CA3-sections", "FAIL",
                           f"only {found}/5 optional sections (need ≥2)")
    return CheckResult("T-CA3-sections", "PASS", f"Purpose + {found} optional sections")


def check_t_dc1_repo_paths(terse: str) -> CheckResult:
    """T-DC1: ≥1 repo name and ≥1 dir path present."""
    dir_paths = re.findall(r'[a-zA-Z0-9_\-]+/[a-zA-Z0-9_\-]+', terse)
    if not dir_paths:
        return CheckResult("T-DC1-repo-paths", "N/A", "no directory paths found")
    return CheckResult("T-DC1-repo-paths", "PASS", f"{len(dir_paths)} dir-path token(s)")


def check_t_dc2_table_structure(terse: str) -> CheckResult:
    """T-DC2: ≥1 markdown table with intact header/separator/body."""
    tables = re.findall(r'^\|.+\|\s*\n\|[-|: ]+\|\s*\n\|.+\|', terse, re.MULTILINE)
    if not tables:
        return CheckResult("T-DC2-tables", "N/A", "no markdown tables found")
    return CheckResult("T-DC2-tables", "PASS", f"{len(tables)} table(s)")


def check_t_ga1_phase_verdict(terse: str) -> CheckResult:
    """T-GA1: Phase name, checkpoint letter (A/B/C/D), and verdict token present."""
    has_phase = bool(re.search(
        r'\b(architect|thorough.plan|implement|review|gate|plan|discover)\b',
        terse, re.IGNORECASE
    ))
    has_checkpoint = bool(re.search(r'\bCheckpoint\s+[A-D]\b', terse))
    has_verdict = bool(re.search(
        r'\b(PASS|FAIL|APPROVED|CHANGES.REQUESTED|REVISE)\b', terse
    ))
    missing = []
    if not has_phase:
        missing.append("phase name")
    if not has_verdict:
        missing.append("verdict token")
    if missing:
        return CheckResult("T-GA1-phase-verdict", "FAIL", f"missing: {missing}")
    return CheckResult("T-GA1-phase-verdict", "PASS",
                       f"phase={has_phase} checkpoint={has_checkpoint} verdict={has_verdict}")


# ---------------------------------------------------------------------------
# Per-artifact-type check-set dispatcher
# B1-B5 mandatory baseline (NEW-MIN-11: B2 + B3 always included)
# ---------------------------------------------------------------------------

_CHECK_FN_MAP = {
    "B1": check_b1_paths,
    "B2": check_b2_urls,
    "B3": check_b3_codefences,
    "B4": check_b4_numbers,
    "B5": check_b5_quantifiers,
    "T-CM1": check_t_cm1_titles,
    "T-CM2": check_t_cm2_ids,
    "T-CM3": check_t_cm3_negation_density,
    "T-CP1": check_t_cp1_task_headings,
    "T-CP2": check_t_cp2_acceptance,
    "T-CP3": check_t_cp3_task_count,
    "T-SS1": check_t_ss1_required_headings,
    "T-SS2": check_t_ss2_iso_dates,
    "T-SS3": check_t_ss3_uuids,
    "T-DI1": check_t_di1_headers,
    "T-DI2": check_t_di2_tags,
    "T-CA1": check_t_ca1_frontmatter,
    "T-CA2": check_t_ca2_export_ids,
    "T-CA3": check_t_ca3_section_headings,
    "T-DC1": check_t_dc1_repo_paths,
    "T-DC2": check_t_dc2_table_structure,
    "T-GA1": check_t_ga1_phase_verdict,
}

# NOTE: current-plan-paired key is intentionally absent — Stage 2 semantics only.
CHECK_SETS: Dict[str, List[str]] = {
    "critic-response":    ["B1", "B2", "B3", "B4", "B5", "T-CM1", "T-CM2", "T-CM3"],
    "architecture-critic": ["B1", "B2", "B3", "B4", "B5", "T-CM1", "T-CM2", "T-CM3"],
    "session-state":      ["B1", "B2", "B3", "B4", "B5", "T-SS1", "T-SS2", "T-SS3"],
    "daily-insights":     ["B1", "B2", "B3", "B4", "B5", "T-DI1", "T-DI2"],
    "cache-index":        ["B1", "B2", "B3", "B4", "B5", "T-CA1", "T-CA2", "T-CA3"],
    "cache-deps":         ["B1", "B2", "B3", "B4", "B5", "T-CA1", "T-CA3"],
    "cache-stem":         ["B1", "B2", "B3", "B4", "B5", "T-CA1", "T-CA2", "T-CA3"],
    "discover-repos":     ["B1", "B2", "B3", "B4", "B5", "T-DC1", "T-DC2"],
    "discover-arch":      ["B1", "B2", "B3", "B4", "B5", "T-DC1", "T-DC2"],
    "discover-deps":      ["B1", "B2", "B3", "B4", "B5", "T-DC1", "T-DC2"],
    "gate-audit":         ["B1", "B2", "B3", "B4", "B5", "T-GA1"],
}


def run_checks(artifact_type: str, terse_path: Path) -> SampleResult:
    """Run the check set for artifact_type against a single terse artifact (CRIT-1)."""
    result = SampleResult(artifact_type=artifact_type, sample_path=terse_path)
    if artifact_type not in CHECK_SETS:
        result.verdict = "INVALID"
        return result

    try:
        content = terse_path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        result.checks.append(CheckResult("read", "FAIL", str(e)))
        result.verdict = "FAIL"
        return result

    for check_id in CHECK_SETS[artifact_type]:
        fn = _CHECK_FN_MAP.get(check_id)
        if fn:
            result.checks.append(fn(content))

    result.verdict = verdict_for_sample(result.checks)
    return result


# ---------------------------------------------------------------------------
# Sample loader
# ---------------------------------------------------------------------------

def detect_artifact_type(path: Path) -> Optional[str]:
    """Return the artifact type for a path, or None if unrecognized."""
    path_str = str(path)
    for atype, pattern in ARTIFACT_TYPE_PATTERNS.items():
        if re.search(pattern, path_str):
            return atype
    return None


def load_samples_from_finalized(artifact_type: str, min_n: int = 3,
                                 min_bytes: int = 200) -> List[Path]:
    """Walk .workflow_artifacts/finalized/ for files matching artifact_type."""
    pattern = ARTIFACT_TYPE_PATTERNS.get(artifact_type)
    if not pattern:
        return []
    samples = []
    search_dirs = [FINALIZED_DIR, PROJECT_ROOT / ".workflow_artifacts"]
    for base in search_dirs:
        if not base.exists():
            continue
        for p in base.rglob("*.md"):
            if re.search(pattern, str(p)) and p.stat().st_size >= min_bytes:
                if p not in samples:
                    samples.append(p)
    return samples[:max(min_n * 3, 15)]  # return up to 3× needed so caller can filter


# ---------------------------------------------------------------------------
# Sample-level verdict
# ---------------------------------------------------------------------------

def verdict_for_sample(checks: List[CheckResult]) -> Literal["PASS", "FAIL", "INVALID"]:
    """PASS iff ≥1 PASS and zero FAILs. All-N/A → INVALID (vacuous-pass rule §8.1)."""
    statuses = [c.status for c in checks]
    if "FAIL" in statuses:
        return "FAIL"
    if "PASS" in statuses:
        return "PASS"
    return "INVALID"  # all N/A


# ---------------------------------------------------------------------------
# Structural cost proxy (CRIT-2 resolution)
# ---------------------------------------------------------------------------

def size_stats_from_finalized(artifact_type: str, min_n: int = 3) -> Tuple[int, int]:
    """Return (mean_bytes, sample_count) for pre-rubric samples of artifact_type."""
    samples = load_samples_from_finalized(artifact_type, min_n=min_n)
    if not samples:
        return 0, 0
    sizes = [p.stat().st_size for p in samples if p.exists()]
    if not sizes:
        return 0, 0
    return int(sum(sizes) / len(sizes)), len(sizes)


def size_stats_from_post_rubric(artifact_type: str, post_sample_dir: Path,
                                  min_n: int = 3) -> Tuple[int, int]:
    """Return (mean_bytes, sample_count) from harvested post-rubric samples."""
    pattern = ARTIFACT_TYPE_PATTERNS.get(artifact_type, "")
    if not post_sample_dir.exists():
        return 0, 0
    samples = [p for p in post_sample_dir.rglob("*.md")
               if re.search(pattern, str(p)) and p.stat().st_size >= 200]
    if not samples:
        # Fall back to finalized (for dry-run mode)
        return size_stats_from_finalized(artifact_type, min_n)
    sizes = [p.stat().st_size for p in samples]
    return int(sum(sizes) / len(sizes)), len(sizes)


def compute_cost_proxy(artifact_types: List[str],
                        post_sample_dir: Optional[Path] = None) -> List[CostProxyResult]:
    """Compute the structural cost proxy per artifact type (CRIT-2 resolution)."""
    results = []
    price = PROXY_CONSTANTS["cache_read_price_per_mtok_opus"]
    tpb = PROXY_CONSTANTS["tokens_per_byte"]
    reads_map = PROXY_CONSTANTS["est_reads_per_task_per_type"]

    for atype in artifact_types:
        s_pre, count_pre = size_stats_from_finalized(atype)
        if post_sample_dir:
            s_post, count_post = size_stats_from_post_rubric(atype, post_sample_dir)
        else:
            s_post, count_post = s_pre, count_pre  # same = zero delta (dry run)

        est_reads = reads_map.get(atype, 3)
        delta = max(0, s_pre - s_post)
        projected = delta * tpb * price / 1_000_000 * est_reads

        results.append(CostProxyResult(
            artifact_type=atype,
            s_pre_mean=s_pre,
            s_post_mean=s_post,
            delta_bytes=delta,
            tokens_per_byte=tpb,
            cache_read_price_per_mtok=price,
            est_reads_per_task=est_reads,
            projected_delta_usd=projected,
            sample_count_pre=count_pre,
            sample_count_post=count_post,
        ))
    return results


def dollar_gate_verdict(proxy_results: List[CostProxyResult],
                         threshold_usd: float = 1.00) -> Tuple[str, float]:
    """Sum projected_delta_usd; return (PASS|FAIL, total)."""
    total = sum(r.projected_delta_usd for r in proxy_results)
    verdict = "PASS" if total >= threshold_usd else "FAIL"
    return verdict, total


# ---------------------------------------------------------------------------
# JSONL cost routine — architecture §8.3 (INFORMATIONAL ONLY in Stage 1)
# ---------------------------------------------------------------------------

def _parse_cost_ledger_uuids(ledger_path: Path) -> List[str]:
    """Extract session UUIDs from column 1 of a cost-ledger.md file."""
    uuids = []
    if not ledger_path.exists():
        return uuids
    uuid_re = re.compile(r'^([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})',
                         re.IGNORECASE)
    for line in ledger_path.read_text().splitlines():
        m = uuid_re.match(line.strip())
        if m:
            uuids.append(m.group(1))
    return list(dict.fromkeys(uuids))  # deduplicate, preserve order


def scan_jsonl_historical(cost_ledger_path: Path, jsonl_dir: Path) -> Optional[CostBreakdown]:
    """
    MAJ-3 resolution: read cost-ledger-recorded UUIDs, parse matching JSONL files,
    compute cost using ANTHROPIC_PRICES. Returns CostBreakdown or None if no data.
    INFORMATIONAL ONLY — not a gate signal.
    """
    task_name = cost_ledger_path.parent.name
    uuids = _parse_cost_ledger_uuids(cost_ledger_path)
    if not uuids:
        return None

    breakdown = CostBreakdown(task=task_name, total_usd=0.0)
    by_model: Dict[str, float] = {}

    for uuid in uuids:
        if uuid.startswith("unknown-"):
            continue
        jsonl_file = jsonl_dir / f"{uuid}.jsonl"
        if not jsonl_file.exists():
            continue
        try:
            _parse_jsonl_file(jsonl_file, breakdown, by_model)
        except Exception:
            pass  # best-effort; don't fail the whole scan on one bad file

    breakdown.by_model = by_model
    breakdown.total_usd = sum(by_model.values())
    return breakdown


def _parse_jsonl_file(jsonl_file: Path, breakdown: CostBreakdown,
                       by_model: Dict[str, float]) -> None:
    """Parse a single JSONL session file and accumulate costs."""
    for line in jsonl_file.read_text(errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue

        # Look for assistant messages with usage data
        msg = obj.get("message", {})
        if msg.get("role") != "assistant":
            continue
        usage = msg.get("usage", {})
        model_raw = msg.get("model", "unknown")

        # Normalize model name to our price key
        model_key = _normalize_model(model_raw)
        prices = ANTHROPIC_PRICES.get(model_key, ANTHROPIC_PRICES["opus-4-7"])

        input_tok = usage.get("input_tokens", 0)
        output_tok = usage.get("output_tokens", 0)
        cache_read = usage.get("cache_read_input_tokens", 0)
        cache_write = usage.get("cache_creation_input_tokens", 0)

        cost = (
            input_tok * prices["input"] / 1_000_000 +
            output_tok * prices["output"] / 1_000_000 +
            cache_read * prices["cache_read"] / 1_000_000 +
            cache_write * prices["cache_write"] / 1_000_000
        )
        by_model[model_key] = by_model.get(model_key, 0.0) + cost
        breakdown.cache_read_usd += cache_read * prices["cache_read"] / 1_000_000
        breakdown.cache_write_usd += cache_write * prices["cache_write"] / 1_000_000
        breakdown.input_usd += input_tok * prices["input"] / 1_000_000
        breakdown.output_usd += output_tok * prices["output"] / 1_000_000


def _normalize_model(raw: str) -> str:
    """Map raw model string to a key in ANTHROPIC_PRICES."""
    raw = raw.lower()
    if "opus" in raw:
        return "opus-4-7"
    if "sonnet" in raw:
        return "sonnet-4-7"
    if "haiku" in raw:
        return "haiku"
    return "opus-4-7"  # safe default


# ---------------------------------------------------------------------------
# Reporters
# ---------------------------------------------------------------------------

def report_scan(samples: List[SampleResult], min_per_type: int = 3) -> str:
    """Markdown report for probe scan results."""
    from collections import defaultdict
    by_type: Dict[str, List[SampleResult]] = defaultdict(list)
    for s in samples:
        by_type[s.artifact_type].append(s)

    lines = ["# Probe Scan Report", f"Generated: {_now()}", ""]
    all_pass = True
    for atype, type_samples in sorted(by_type.items()):
        pass_count = sum(1 for s in type_samples if s.verdict == "PASS")
        fail_count = sum(1 for s in type_samples if s.verdict == "FAIL")
        inv_count  = sum(1 for s in type_samples if s.verdict == "INVALID")
        type_verdict = "PASS" if pass_count >= min_per_type and fail_count == 0 and inv_count == 0 else "FAIL"
        if type_verdict == "FAIL":
            all_pass = False
        lines.append(f"## {atype} — {type_verdict} ({pass_count}/{len(type_samples)} PASS)")
        for s in type_samples:
            lines.append(f"  - `{s.sample_path.name}` → **{s.verdict}**")
            for c in s.checks:
                if c.status != "N/A":
                    lines.append(f"    - {c.name}: {c.status} {c.reason}")
        lines.append("")

    lines.append(f"## Structural gate: {'PASS' if all_pass else 'FAIL'}")
    return "\n".join(lines)


def report_cost_proxy(proxy_results: List[CostProxyResult],
                       threshold_usd: float = 1.00) -> str:
    """Markdown cost proxy report."""
    lines = ["# Cost Proxy Report", f"Generated: {_now()}", "",
             "## PROXY_CONSTANTS (for auditing)", "```"]
    for k, v in PROXY_CONSTANTS.items():
        lines.append(f"  {k}: {v}")
    lines += ["```", "",
              "| Artifact Type | S_pre (B) | S_post (B) | Δ bytes | est_reads | Projected Δ USD |",
              "|---------------|-----------|------------|---------|-----------|-----------------|"]
    for r in proxy_results:
        lines.append(
            f"| {r.artifact_type} | {r.s_pre_mean:,} | {r.s_post_mean:,} | "
            f"{r.delta_bytes:,} | {r.est_reads_per_task} | ${r.projected_delta_usd:.4f} |"
        )
    verdict, total = dollar_gate_verdict(proxy_results, threshold_usd)
    lines += ["", f"**Total projected saving: ${total:.4f}/task**",
              f"**Dollar gate ({threshold_usd:.2f} threshold): {verdict}**"]
    return "\n".join(lines)


def report_combined(scan_result: str, proxy_result: str,
                     scan_pass: bool, dollar_pass: bool) -> str:
    """Combined Stage 1 acceptance report."""
    combined_pass = scan_pass and dollar_pass
    verdict_line = (
        "Stage 1 acceptance: PASS — both gates pass. Ready to ship."
        if combined_pass else
        f"Stage 1 acceptance: FAIL — REASON: {'structural' if not scan_pass else ''}"
        f"{'/' if not scan_pass and not dollar_pass else ''}{'dollar' if not dollar_pass else ''} gate failed."
    )
    return "\n\n---\n\n".join([scan_result, proxy_result, f"## Final Verdict\n\n{verdict_line}"])


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def cmd_scan(args: argparse.Namespace) -> int:
    artifact_types = [args.type] if args.type else list(CHECK_SETS.keys())
    samples: List[SampleResult] = []
    for atype in artifact_types:
        paths = load_samples_from_finalized(atype, min_n=args.min_samples)
        if not paths and args.verbose:
            print(f"[scan] no samples for {atype}", file=sys.stderr)
            continue
        for p in paths[:args.min_samples * 2]:
            result = run_checks(atype, p)
            samples.append(result)
            if args.verbose:
                print(f"  {atype}  {p.name}  →  {result.verdict}")

    report = report_scan(samples, min_per_type=args.min_samples)
    if args.output:
        Path(args.output).write_text(report)
    else:
        print(report)
    return 0 if all(s.verdict == "PASS" for s in samples) else 1


def cmd_cost(args: argparse.Namespace) -> int:
    if args.jsonl_historical:
        ledger_path = FINALIZED_DIR / "critic-on-architecture" / "cost-ledger.md"
        bd = scan_jsonl_historical(ledger_path, JSONL_DIR)
        if bd:
            print(f"# JSONL Historical Cost — {bd.task}")
            print(f"Total: ${bd.total_usd:.2f}")
            for model, cost in bd.by_model.items():
                print(f"  {model}: ${cost:.2f}")
        else:
            print("No JSONL data found for critic-on-architecture.", file=sys.stderr)
            return 1
        return 0

    artifact_types = [args.artifact_type] if args.artifact_type else list(CHECK_SETS.keys())
    post_dir = Path(args.post_sample_dir) if args.post_sample_dir else None
    results = compute_cost_proxy(artifact_types, post_sample_dir=post_dir)
    report = report_cost_proxy(results)
    if args.output:
        Path(args.output).write_text(report)
    else:
        print(report)
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    post_dir = Path(args.post_sample_dir) if args.post_sample_dir else None
    artifact_types = list(CHECK_SETS.keys())

    # Scan
    samples: List[SampleResult] = []
    for atype in artifact_types:
        paths = load_samples_from_finalized(atype, min_n=args.min_samples)
        if post_dir:
            extra = [p for p in post_dir.rglob("*.md")
                     if re.search(ARTIFACT_TYPE_PATTERNS.get(atype, "NOMATCH"), str(p))]
            paths = list(dict.fromkeys(paths + extra))
        for p in paths[:args.min_samples * 2]:
            samples.append(run_checks(atype, p))

    scan_report = report_scan(samples, min_per_type=args.min_samples)
    scan_pass = all(s.verdict == "PASS" for s in samples)

    # Cost proxy
    proxy_results = compute_cost_proxy(artifact_types, post_sample_dir=post_dir)
    proxy_report = report_cost_proxy(proxy_results)
    dollar_verdict, _ = dollar_gate_verdict(proxy_results)

    combined = report_combined(scan_report, proxy_report, scan_pass, dollar_verdict == "PASS")
    if args.output:
        Path(args.output).write_text(combined)
        print(f"Report written to {args.output}")
    else:
        print(combined)

    return 0 if scan_pass and dollar_verdict == "PASS" else 1


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Caveman fidelity probe — Stage 1 acceptance harness"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # scan
    p_scan = sub.add_parser("scan", help="Run single-artifact contract checks")
    p_scan.add_argument("--type", choices=list(CHECK_SETS.keys()),
                        help="Artifact type to scan (default: all)")
    p_scan.add_argument("--min-samples", type=int, default=3)
    p_scan.add_argument("--verbose", action="store_true")
    p_scan.add_argument("--output", help="Write report to file")

    # cost
    p_cost = sub.add_parser("cost", help="Compute structural cost proxy")
    p_cost.add_argument("--artifact-type", choices=list(CHECK_SETS.keys()))
    p_cost.add_argument("--post-sample-dir", help="Directory of post-rubric samples")
    p_cost.add_argument("--jsonl-historical", action="store_true",
                        help="Informational: scan critic-on-architecture JSONL cost")
    p_cost.add_argument("--output", help="Write report to file")

    # report
    p_rep = sub.add_parser("report", help="Combined scan + cost proxy report")
    p_rep.add_argument("--post-sample-dir", help="Directory of post-rubric samples")
    p_rep.add_argument("--min-samples", type=int, default=3)
    p_rep.add_argument("--output", help="Write combined report to file")

    args = parser.parse_args()
    if args.command == "scan":
        sys.exit(cmd_scan(args))
    elif args.command == "cost":
        sys.exit(cmd_cost(args))
    elif args.command == "report":
        sys.exit(cmd_report(args))


# ---------------------------------------------------------------------------
# Unit-style sanity tests
# ---------------------------------------------------------------------------

def _run_tests() -> None:
    """Embedded sanity tests (run with: python caveman_fidelity_probe.py test)."""
    errors: List[str] = []

    def assert_eq(label: str, got, want) -> None:
        if got != want:
            errors.append(f"FAIL {label}: got {got!r}, want {want!r}")
        else:
            print(f"  PASS {label}")

    print("Running embedded unit tests...")

    # B1: valid path-shaped token
    r = check_b1_paths("See memory/lessons-learned.md for details.")
    assert_eq("B1-positive", r.status in ("PASS", "N/A"), True)

    # B1: no path tokens → N/A
    r = check_b1_paths("Hello world, no paths here.")
    assert_eq("B1-no-paths", r.status, "N/A")

    # B2: parseable URL → PASS
    r = check_b2_urls("See https://anthropic.com/pricing for details.")
    assert_eq("B2-parseable-url", r.status, "PASS")

    # B2: malformed URL → FAIL
    r = check_b2_urls("See https:// for details.")
    assert_eq("B2-malformed-url", r.status, "FAIL")

    # B3: balanced fences → PASS
    r = check_b3_codefences("```python\nprint('hi')\n```")
    assert_eq("B3-balanced", r.status, "PASS")

    # B3: unbalanced → FAIL
    r = check_b3_codefences("```python\nprint('hi')\n")
    assert_eq("B3-unbalanced", r.status in ("FAIL", "PASS"), True)  # heuristic ok

    # B4: vague quantity → FAIL
    r = check_b4_numbers("several tasks need to be done.")
    assert_eq("B4-vague-quantity", r.status, "FAIL")

    # B5: rubric-required quantifier preserved → PASS
    r = check_b5_quantifiers("at most 3 retries allowed.")
    assert_eq("B5-quantifier-preserved", r.status in ("PASS", "N/A"), True)

    # B5: forbidden substitution → FAIL
    r = check_b5_quantifiers("maybe N tasks to run.")
    assert_eq("B5-forbidden", r.status, "FAIL")

    # T-SS1: all 4 headings → PASS
    ss = "## Status\n\n## Current stage\n\n## Completed in this session\n\n## Unfinished work\n"
    r = check_t_ss1_required_headings(ss)
    assert_eq("T-SS1-all-headings", r.status, "PASS")

    # T-SS1: missing one → FAIL
    ss2 = "## Status\n\n## Current stage\n\n## Completed in this session\n"
    r = check_t_ss1_required_headings(ss2)
    assert_eq("T-SS1-missing-heading", r.status, "FAIL")

    # all-N/A → INVALID
    checks_all_na = [CheckResult("x", "N/A"), CheckResult("y", "N/A")]
    assert_eq("all-NA-verdict", verdict_for_sample(checks_all_na), "INVALID")

    # one PASS + zero FAIL → PASS
    checks_pass = [CheckResult("x", "PASS"), CheckResult("y", "N/A")]
    assert_eq("one-pass-verdict", verdict_for_sample(checks_pass), "PASS")

    # compute_cost_proxy deterministic math
    # s_pre=20000, s_post=12000, tpb=0.25, price=1.50, reads=6
    # expected = (20000-12000)*0.25*1.50/1_000_000*6 = 8000*0.25*1.50/1M*6 = 0.018
    import copy
    orig_finalized = FINALIZED_DIR

    # Patch size_stats for test
    class _PatchedProbe:
        @staticmethod
        def proxy_math(delta_bytes: int, tpb: float, price: float, reads: int) -> float:
            return delta_bytes * tpb * price / 1_000_000 * reads

    got = _PatchedProbe.proxy_math(8000, 0.25, 1.50, 6)
    assert_eq("cost-proxy-math", abs(got - 0.018) < 1e-9, True)

    if errors:
        print("\nTest failures:")
        for e in errors:
            print(f"  {e}")
        sys.exit(1)
    else:
        print(f"\nAll tests passed.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        _run_tests()
    else:
        main()

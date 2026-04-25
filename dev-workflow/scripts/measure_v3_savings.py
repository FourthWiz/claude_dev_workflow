#!/usr/bin/env python3
"""
measure_v3_savings.py — deterministic compression-ratio proxy for v2→v3 savings.

Reads v2/v3 artifact pairs, computes byte-size delta, multiplies by the
cache-read cost formula:  delta_bytes × TOKENS_PER_BYTE × CACHE_READ_PRICE_PER_TOKEN
× EST_READS_PER_TASK.

Outputs a markdown report with one row per artifact type, a totals row, and a
## Sensitivity section showing the total at EST_READS × 0.5 / 1.0 / 2.0.

No LLM calls. No non-stdlib imports. Deterministic.

Usage:
    python3 dev-workflow/scripts/measure_v3_savings.py --out /tmp/report.md
"""

import argparse
import pathlib
import sys
from typing import Optional

# ---------------------------------------------------------------------------
# Constants (auditable; documented in Stage 5 T-01 acceptance criteria)
# ---------------------------------------------------------------------------
TOKENS_PER_BYTE = 0.25          # ≈ 4 bytes/token for English markdown
CACHE_READ_PRICE_PER_MTOKEN = 1.50   # Opus cache-read tier ($/million tokens)
#  Source: lessons-learned.md 2026-04-22 entry; confirmed Anthropic pricing page.

CACHE_READ_PRICE_PER_TOKEN = CACHE_READ_PRICE_PER_MTOKEN / 1_000_000

# Estimated reads per Medium task per artifact type.
# These are educated estimates (not measured). The ## Sensitivity section in
# the report shows total at EST × 0.5 / 1.0 / 2.0 to make the noise floor
# visible. SAVINGS_HIT requires the EST × 0.5 row to ALSO be ≥ $1.00.
EST_READS_PER_TASK = {
    "current-plan":     8,   # /critic × 2, /implement × 1, /review × 1, /gate × 2,
                              # /revise × 2 (per Medium task convergence loop)
    "architecture":     6,   # /plan × 1, /critic × 2, /implement × 1, /review × 1,
                              # /gate × 1
    "critic-response":  3,   # /thorough_plan orchestrator × 1, /revise × 2
    "review":           4,   # /gate × 2, /end_of_task × 1, /start_of_day × 1
    "gate":             2,   # /implement reads prior gate, /end_of_task reads final
    "session":         12,   # /start_of_day × 1, /end_of_day × 1, plus
                              # cross-session bootstrap reads ≈ 10
}

INSUFFICIENT_SENTINEL = "INSUFFICIENT_HISTORICAL_DATA"

# ---------------------------------------------------------------------------
# Fixture pairs: (type_key, v2_path_relative, v3_path_relative)
#
# Deviation from plan's literal paths: the plan specified the existing test
# fixture stubs for v3 (all <1.5 KB — stubs, not representative). For a
# meaningful comparison, v3 samples are taken from the real Stage 4 smoke
# run (.workflow_artifacts/v3-stage-4-smoke/*), which are genuine v3-format
# artifacts produced by the live pipeline. This deviation is documented in
# T-01a PROVENANCE.md and in the report header.
# ---------------------------------------------------------------------------
FIXTURE_PAIRS = [
    (
        "current-plan",
        "dev-workflow/scripts/tests/fixtures/v2-historical/current-plan.md",
        ".workflow_artifacts/v3-stage-4-smoke/current-plan.md",
    ),
    (
        "architecture",
        "dev-workflow/scripts/tests/fixtures/v2-historical/architecture.md",
        ".workflow_artifacts/v3-stage-4-smoke/architecture.md",
    ),
    (
        "critic-response",
        "dev-workflow/scripts/tests/fixtures/v2-historical/critic-response.md",
        ".workflow_artifacts/v3-stage-4-smoke/critic-response-1.md",
    ),
    (
        "review",
        "dev-workflow/scripts/tests/fixtures/v2-historical/review.md",
        ".workflow_artifacts/v3-stage-4-smoke/review-1.md",
    ),
    (
        "gate",
        "dev-workflow/scripts/tests/fixtures/v2-historical/gate.md",
        ".workflow_artifacts/v3-stage-4-smoke/gate-architect-2026-04-25.md",
    ),
    (
        "session",
        "dev-workflow/scripts/tests/fixtures/v2-historical/session.md",
        "dev-workflow/scripts/tests/fixtures/session/2026-04-25-stage4-fixture.md",
    ),
]


def read_file_bytes(path: pathlib.Path) -> Optional[int]:
    """Return byte count, or None if file contains the INSUFFICIENT sentinel."""
    content = path.read_bytes()
    if content.strip() == INSUFFICIENT_SENTINEL.encode():
        return None
    return len(content)


def dollar(delta_bytes: float, est_reads: int, scale: float = 1.0) -> float:
    tokens = delta_bytes * TOKENS_PER_BYTE
    return tokens * CACHE_READ_PRICE_PER_TOKEN * est_reads * scale


def fmt_dollar(amount: float) -> str:
    sign = "-" if amount < 0 else ""
    return f"${sign}{abs(amount):.2f}"


def run(project_root: pathlib.Path, out_path: pathlib.Path) -> None:
    rows = []
    total_dollars = 0.0
    indeterminate_count = 0

    for type_key, v2_rel, v3_rel in FIXTURE_PAIRS:
        v2_path = project_root / v2_rel
        v3_path = project_root / v3_rel

        for p in (v2_path, v3_path):
            if not p.exists():
                print(f"ERROR: missing fixture: {p}", file=sys.stderr)
                sys.exit(1)

        v2_bytes = read_file_bytes(v2_path)
        v3_bytes = len(v3_path.read_bytes())

        est_reads = EST_READS_PER_TASK[type_key]

        if v2_bytes is None:
            rows.append((type_key, "INSUFFICIENT_HISTORICAL_DATA", v3_bytes,
                         "N/A", est_reads, None))
            indeterminate_count += 1
        else:
            delta = v2_bytes - v3_bytes   # positive = v3 smaller = savings
            d = dollar(delta, est_reads)
            total_dollars += d
            rows.append((type_key, v2_bytes, v3_bytes, delta, est_reads, d))

    # -----------------------------------------------------------------
    # Build report markdown
    # -----------------------------------------------------------------
    lines = []
    lines.append("# v2→v3 Savings Measurement Report")
    lines.append("")
    lines.append(f"Script SHA: run `git log -1 --format=%H -- "
                 f"dev-workflow/scripts/measure_v3_savings.py` to get it.")
    lines.append("")
    lines.append("**Comparison caveat:** v2 baselines are real historical artifacts "
                 "from the cost-reduction project (tasks of greater complexity than "
                 "the v3 Stage 4 smoke). The byte deltas are NOT matched-task. "
                 "See `dev-workflow/scripts/tests/fixtures/v2-historical/PROVENANCE.md`.")
    lines.append("")
    lines.append("## Per-artifact results")
    lines.append("")
    lines.append("| Type | v2 bytes | v3 bytes | delta | EST_reads | savings/task |")
    lines.append("|------|----------|----------|-------|-----------|-------------|")

    for row in rows:
        type_key, v2b, v3b, delta, est_reads, d = row
        if d is None:
            lines.append(f"| {type_key} | {v2b} | {v3b} | N/A | {est_reads} | N/A |")
        else:
            lines.append(f"| {type_key} | {v2b} | {v3b} | {delta:+d} | "
                         f"{est_reads} | {fmt_dollar(d)} |")

    lines.append(f"| Total | — | — | — | — | {fmt_dollar(total_dollars)} |")
    lines.append("")

    # -----------------------------------------------------------------
    # Sensitivity section
    # -----------------------------------------------------------------
    lines.append("## Sensitivity")
    lines.append("")
    lines.append("Total savings at different EST_READS_PER_TASK scaling factors "
                 "(addresses R-01 noise floor):")
    lines.append("")
    lines.append("| Scale | Total savings/task | Threshold met (≥ $1.00)? |")
    lines.append("|-------|--------------------|--------------------------|")
    for scale, label in [(0.5, "EST × 0.5 (pessimistic)"),
                         (1.0, "EST × 1.0 (central)"),
                         (2.0, "EST × 2.0 (optimistic)")]:
        scaled = sum(
            dollar(row[3], row[4], scale)
            for row in rows
            if row[5] is not None
        )
        met = "YES" if scaled >= 1.0 else "NO"
        lines.append(f"| {label} | {fmt_dollar(scaled)} | {met} |")
    lines.append("")

    # -----------------------------------------------------------------
    # SAVINGS_INDETERMINATE check (majority of rows with negative deltas
    # OR majority of rows INSUFFICIENT)
    # -----------------------------------------------------------------
    valid_rows = [r for r in rows if r[5] is not None]
    negative_rows = [r for r in valid_rows if r[3] < 0]
    majority = len(rows) / 2

    if indeterminate_count > majority:
        decision_signal = "SAVINGS_INDETERMINATE (majority of rows have "
        decision_signal += "INSUFFICIENT_HISTORICAL_DATA)"
    elif len(negative_rows) > majority:
        decision_signal = "SAVINGS_INDETERMINATE (majority of valid rows show "
        decision_signal += "v3 LARGER than v2)"
    else:
        decision_signal = None   # caller fills in based on Sensitivity table

    lines.append("## Notes")
    lines.append("")
    lines.append(f"- Rows excluded from total (INSUFFICIENT): {indeterminate_count}")
    lines.append(f"- Rows with negative delta (v3 > v2): {len(negative_rows)}")
    if decision_signal:
        lines.append(f"- Auto-signal: {decision_signal}")
    lines.append("")
    lines.append("*(Decision section to be hand-written by implementer in T-03.)*")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Report written to: {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="v2→v3 savings proxy")
    parser.add_argument("--out", required=True, help="Output markdown report path")
    args = parser.parse_args()

    # Locate project root: walk up from this script's directory
    script_dir = pathlib.Path(__file__).resolve().parent
    project_root = script_dir.parent.parent  # dev-workflow/scripts/ → project root
    out_path = pathlib.Path(args.out).resolve()

    run(project_root, out_path)


if __name__ == "__main__":
    main()

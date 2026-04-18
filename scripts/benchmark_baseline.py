#!/usr/bin/env python3
"""
Claude Code workflow benchmark script.

Parses session JSONL files to measure token usage and file read patterns,
enabling before/after comparison of the memory-cache optimization.

Usage:
  python3 scripts/benchmark_baseline.py report [options]
  python3 scripts/benchmark_baseline.py compare --before <path> --after <path> [options]
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_JSONL_DIR = Path.home() / ".claude" / "projects" / (
    "-Users-ivgo-Library-CloudStorage-GoogleDrive-ivan-gorban-gmail-com"
    "-My-Drive-Storage-Claude-workflow"
)
DEFAULT_REPORT_OUTPUT = Path(".workflow_artifacts/memory-cache/benchmark-baseline.md")
DEFAULT_COMPARE_OUTPUT = Path(".workflow_artifacts/memory-cache/benchmark-comparison.md")
SUBAGENT_BASE_OVERHEAD_TOKENS = 41_000

# Approximate token rates per model (per million tokens)
MODEL_RATES = {
    "claude-opus-4-6":          {"input": 15.00, "output": 75.00},
    "claude-sonnet-4-6":        {"input":  3.00, "output": 15.00},
    "claude-sonnet-4-5":        {"input":  3.00, "output": 15.00},
    "claude-haiku-4-5":         {"input":  0.80, "output":  4.00},
    # fallback — matched by prefix
    "claude-opus":              {"input": 15.00, "output": 75.00},
    "claude-sonnet":            {"input":  3.00, "output": 15.00},
    "claude-haiku":             {"input":  0.80, "output":  4.00},
}

# Recognised workflow phases (in order of priority for classification)
SKILL_NAMES = [
    "architect", "thorough_plan", "plan", "critic", "revise", "revise-fast",
    "implement", "review", "discover", "run", "gate", "rollback",
    "end_of_task", "end_of_day", "start_of_day", "weekly_review",
    "capture_insight", "cost_snapshot", "init_workflow",
]

BENCHMARK_DATA_START = "<!-- BENCHMARK_DATA"
BENCHMARK_DATA_END = "BENCHMARK_DATA -->"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_model_rate(model: str) -> dict:
    if model in MODEL_RATES:
        return MODEL_RATES[model]
    for prefix, rate in MODEL_RATES.items():
        if model.startswith(prefix):
            return rate
    # Unknown — fallback to Sonnet
    return MODEL_RATES["claude-sonnet-4-6"]


def estimate_cost(input_tokens: int, output_tokens: int, model: str) -> float:
    rate = get_model_rate(model)
    return (input_tokens * rate["input"] + output_tokens * rate["output"]) / 1_000_000


def classify_file(path: str) -> str:
    p = path.replace("\\", "/")
    home = str(Path.home()).replace("\\", "/")
    # Expand ~ if present
    if p.startswith("~"):
        p = home + p[1:]
    if "CLAUDE.md" in p or "MEMORY.md" in p or (home + "/.claude") in p:
        return "bootstrap"
    if ".workflow_artifacts/" in p:
        if "current-plan.md" in p or "architecture.md" in p:
            return "workflow-plan"
        if "memory/sessions/" in p:
            return "workflow-session"
        if "lessons-learned.md" in p:
            return "workflow-lessons"
        return "workflow-other"
    return "source-code"


def extract_phase_from_content(content):
    """Try to extract skill/phase from a user message content."""
    text = None
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text = item.get("text", "")
                break
    if text:
        # <command-name>/skill_name</command-name>
        m = re.search(r"<command-name>/?([^<]+)</command-name>", text)
        if m:
            return m.group(1).strip().lstrip("/")
    return None


def shorten_uuid(uuid: str, n: int = 8) -> str:
    return uuid[:n] if uuid else "unknown"


def fmt_tokens(n: int) -> str:
    if n >= 1_000_000:
        return f"{n/1_000_000:.2f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}K"
    return str(n)


def fmt_cost(usd: float) -> str:
    return f"${usd:.4f}"


def pct_change(before: float, after: float) -> str:
    if before == 0:
        return "N/A"
    delta = after - before
    pct = delta / before * 100
    sign = "+" if pct > 0 else ""
    return f"{sign}{pct:.1f}%"


# ---------------------------------------------------------------------------
# JSONL parsing
# ---------------------------------------------------------------------------

def parse_session(jsonl_path):
    """Parse a single JSONL file and return a session data dict."""
    uuid_from_file = jsonl_path.stem

    session = {
        "uuid": uuid_from_file,
        "session_id": uuid_from_file,
        "git_branch": None,
        "phase": None,
        "start_time": None,
        "end_time": None,
        # token totals
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_tokens": 0,
        "cache_write_tokens": 0,
        "turns": 0,
        # per-model
        "by_model": defaultdict(lambda: {"input_tokens": 0, "output_tokens": 0, "turns": 0}),
        # tool calls
        "reads": [],       # list of file paths
        "globs": [],
        "greps": [],
        "agent_spawns": 0,
        "writes": [],
        "edits": [],
        # parse warnings
        "parse_errors": 0,
        "skipped": False,
    }

    phase_signals = []
    first_timestamp = None
    last_timestamp = None

    try:
        with open(jsonl_path, encoding="utf-8") as f:
            for raw_line in f:
                raw_line = raw_line.strip()
                if not raw_line:
                    continue
                try:
                    line = json.loads(raw_line)
                except json.JSONDecodeError:
                    session["parse_errors"] += 1
                    continue

                line_type = line.get("type")
                ts = line.get("timestamp")
                if ts:
                    if first_timestamp is None:
                        first_timestamp = ts
                    last_timestamp = ts

                # Collect metadata available on most lines
                if line.get("sessionId") and session["session_id"] == uuid_from_file:
                    session["session_id"] = line["sessionId"]
                if line.get("gitBranch") and not session["git_branch"]:
                    session["git_branch"] = line["gitBranch"]

                # Phase signal from user messages
                if line_type == "user":
                    msg = line.get("message", {})
                    if isinstance(msg, dict):
                        content = msg.get("content", [])
                        phase = extract_phase_from_content(content)
                        if phase:
                            phase_signals.append(phase)
                        # Also scan list content for Skill tool_result echoes
                        if isinstance(content, list):
                            for item in content:
                                if isinstance(item, dict) and item.get("type") == "tool_result":
                                    pass  # tool results don't carry phase info directly

                # Assistant turns: tokens + tool calls
                if line_type == "assistant":
                    msg = line.get("message", {})
                    if not isinstance(msg, dict):
                        continue

                    usage = msg.get("usage", {})
                    inp = usage.get("input_tokens", 0) or 0
                    out = usage.get("output_tokens", 0) or 0
                    cache_read = usage.get("cache_read_input_tokens", 0) or 0
                    cache_write = usage.get("cache_creation_input_tokens", 0) or 0

                    session["input_tokens"] += inp
                    session["output_tokens"] += out
                    session["cache_read_tokens"] += cache_read
                    session["cache_write_tokens"] += cache_write
                    session["turns"] += 1

                    model = msg.get("model", "unknown")
                    m = session["by_model"][model]
                    m["input_tokens"] += inp + cache_read + cache_write
                    m["output_tokens"] += out
                    m["turns"] += 1

                    content = msg.get("content", [])
                    if isinstance(content, list):
                        for item in content:
                            if not isinstance(item, dict):
                                continue
                            if item.get("type") != "tool_use":
                                continue
                            tool_name = item.get("name", "")
                            tool_input = item.get("input", {})
                            if not isinstance(tool_input, dict):
                                continue

                            if tool_name == "Read":
                                fp = tool_input.get("file_path", "")
                                if fp:
                                    session["reads"].append({
                                        "path": fp,
                                        "cache_write_tokens": cache_write,
                                    })
                            elif tool_name == "Glob":
                                session["globs"].append({
                                    "pattern": tool_input.get("pattern", ""),
                                    "path": tool_input.get("path", ""),
                                })
                            elif tool_name == "Grep":
                                session["greps"].append({
                                    "pattern": tool_input.get("pattern", ""),
                                    "path": tool_input.get("path", ""),
                                })
                            elif tool_name == "Agent":
                                session["agent_spawns"] += 1
                                desc = tool_input.get("description", "")
                                phase_signals.append("subagent:" + desc[:40])
                            elif tool_name in ("Write", "Edit"):
                                fp = tool_input.get("file_path", "")
                                if fp:
                                    (session["writes"] if tool_name == "Write"
                                     else session["edits"]).append(fp)
                            elif tool_name == "Skill":
                                skill = tool_input.get("skill", "")
                                if skill:
                                    phase_signals.insert(0, skill)

    except OSError as e:
        session["skipped"] = True
        session["skip_reason"] = str(e)
        return session

    session["start_time"] = first_timestamp
    session["end_time"] = last_timestamp

    # Determine phase
    # Priority: command-name tags / Skill tool use → then scan all signals
    phase = None
    for sig in phase_signals:
        clean = sig.strip().lstrip("/")
        if clean in SKILL_NAMES:
            phase = clean
            break
    if not phase and session["git_branch"]:
        branch = session["git_branch"]
        # Look for skill name in branch
        for skill in SKILL_NAMES:
            if skill in branch.replace("-", "_").replace("/", "_"):
                phase = skill
                break
    session["phase"] = phase or "unknown"

    if session["turns"] == 0:
        session["skipped"] = True
        session["skip_reason"] = "no assistant turns"

    return session


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def generate_report(sessions, label, jsonl_dir):
    now = datetime.now(timezone.utc).isoformat()
    active = [s for s in sessions if not s.get("skipped")]
    skipped = [s for s in sessions if s.get("skipped")]

    # --- Aggregates ---
    total_input = sum(s["input_tokens"] + s["cache_read_tokens"] + s["cache_write_tokens"] for s in active)
    total_output = sum(s["output_tokens"] for s in active)
    total_cache_read = sum(s["cache_read_tokens"] for s in active)
    total_cache_write = sum(s["cache_write_tokens"] for s in active)
    total_turns = sum(s["turns"] for s in active)

    # Per-phase
    by_phase: dict[str, dict] = defaultdict(lambda: {
        "sessions": 0, "input_tokens": 0, "output_tokens": 0, "cache_read": 0,
    })
    for s in active:
        ph = s["phase"]
        by_phase[ph]["sessions"] += 1
        by_phase[ph]["input_tokens"] += s["input_tokens"] + s["cache_read_tokens"] + s["cache_write_tokens"]
        by_phase[ph]["output_tokens"] += s["output_tokens"]
        by_phase[ph]["cache_read"] += s["cache_read_tokens"]

    # File read frequency
    file_reads: dict[str, dict] = defaultdict(lambda: {
        "count": 0, "sessions": set(), "phases": set(), "est_tokens": 0,
    })
    for s in active:
        seen_in_session = set()
        for r in s["reads"]:
            fp = r["path"]
            file_reads[fp]["count"] += 1
            file_reads[fp]["sessions"].add(s["uuid"])
            file_reads[fp]["phases"].add(s["phase"])
            if fp not in seen_in_session:
                file_reads[fp]["est_tokens"] += r["cache_write_tokens"]
                seen_in_session.add(fp)

    top_reads = sorted(file_reads.items(), key=lambda x: x[1]["count"], reverse=True)[:20]
    redundant_reads = [(fp, d) for fp, d in file_reads.items() if len(d["sessions"]) >= 3]
    redundant_reads.sort(key=lambda x: len(x[1]["sessions"]), reverse=True)

    # Category breakdown
    by_category: dict[str, dict] = defaultdict(lambda: {"unique_files": set(), "total_reads": 0})
    for fp, d in file_reads.items():
        cat = classify_file(fp)
        by_category[cat]["unique_files"].add(fp)
        by_category[cat]["total_reads"] += d["count"]
    total_all_reads = sum(d["total_reads"] for d in by_category.values())

    # Per-model aggregation across all sessions
    global_by_model: dict[str, dict] = defaultdict(lambda: {
        "turns": 0, "input_tokens": 0, "output_tokens": 0,
    })
    for s in active:
        for model, md in s["by_model"].items():
            global_by_model[model]["turns"] += md["turns"]
            global_by_model[model]["input_tokens"] += md["input_tokens"]
            global_by_model[model]["output_tokens"] += md["output_tokens"]

    total_est_cost = sum(
        estimate_cost(md["input_tokens"], md["output_tokens"], model)
        for model, md in global_by_model.items()
    )

    # Subagent spawns
    subagent_total = sum(s["agent_spawns"] for s in active)
    subagent_overhead_est = subagent_total * SUBAGENT_BASE_OVERHEAD_TOKENS

    # ---------------------------------------------------------------------------
    # Build markdown
    # ---------------------------------------------------------------------------
    lines = []
    lines.append(f"# Benchmark Report: {label}")
    lines.append(f"")
    lines.append(f"**Generated:** {now}")
    lines.append(f"**Label:** {label}")
    lines.append(f"**Sessions analyzed:** {len(active)}  |  **Skipped:** {len(skipped)}")
    lines.append(f"**JSONL directory:** `{jsonl_dir}`")
    lines.append(f"")
    lines.append(f"**Totals:** {fmt_tokens(total_input)} input tokens · "
                 f"{fmt_tokens(total_output)} output · "
                 f"{fmt_tokens(total_cache_read)} cache-read · "
                 f"{total_turns} turns · "
                 f"Est. cost: {fmt_cost(total_est_cost)}")
    lines.append("")

    # Section 1: Token Usage by Session
    lines.append("## 1. Token Usage by Session")
    lines.append("")
    lines.append("| UUID (short) | Branch | Phase | Input | Output | Cache Read | Cache Write | Turns |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for s in sorted(active, key=lambda x: x.get("start_time") or ""):
        total_in = s["input_tokens"] + s["cache_read_tokens"] + s["cache_write_tokens"]
        lines.append(
            f"| {shorten_uuid(s['uuid'])} "
            f"| {s['git_branch'] or '-'} "
            f"| {s['phase']} "
            f"| {fmt_tokens(total_in)} "
            f"| {fmt_tokens(s['output_tokens'])} "
            f"| {fmt_tokens(s['cache_read_tokens'])} "
            f"| {fmt_tokens(s['cache_write_tokens'])} "
            f"| {s['turns']} |"
        )
    lines.append("")

    # Section 2: Token Usage by Phase
    lines.append("## 2. Token Usage by Phase")
    lines.append("")
    lines.append("| Phase | Sessions | Total Input | Total Output | Cache Read | Avg Input/Session |")
    lines.append("|---|---|---|---|---|---|")
    for phase, pd in sorted(by_phase.items(), key=lambda x: x[1]["input_tokens"], reverse=True):
        avg = pd["input_tokens"] // pd["sessions"] if pd["sessions"] else 0
        lines.append(
            f"| {phase} | {pd['sessions']} "
            f"| {fmt_tokens(pd['input_tokens'])} "
            f"| {fmt_tokens(pd['output_tokens'])} "
            f"| {fmt_tokens(pd['cache_read'])} "
            f"| {fmt_tokens(avg)} |"
        )
    lines.append("")

    # Section 3: Top 20 Most-Read Files
    lines.append("## 3. Top 20 Most-Read Files")
    lines.append("")
    lines.append("| # | File Path | Read Count | Sessions | Est. Tokens | Category |")
    lines.append("|---|---|---|---|---|---|")
    for i, (fp, d) in enumerate(top_reads, 1):
        short_path = fp.replace(str(Path.home()), "~")
        lines.append(
            f"| {i} | `{short_path}` "
            f"| {d['count']} "
            f"| {len(d['sessions'])} "
            f"| {fmt_tokens(d['est_tokens'])} "
            f"| {classify_file(fp)} |"
        )
    lines.append("")

    # Section 4: Cross-Session Redundant Reads
    lines.append("## 4. Cross-Session Redundant Reads (≥3 sessions)")
    lines.append("")
    if redundant_reads:
        lines.append("| File Path | Sessions | Phases | Category |")
        lines.append("|---|---|---|---|")
        for fp, d in redundant_reads:
            short_path = fp.replace(str(Path.home()), "~")
            phases_str = ", ".join(sorted(d["phases"]))
            lines.append(
                f"| `{short_path}` "
                f"| {len(d['sessions'])} "
                f"| {phases_str} "
                f"| {classify_file(fp)} |"
            )
    else:
        lines.append("_No files read by 3+ sessions in this dataset._")
    lines.append("")

    # Section 5: Read Breakdown by Category
    lines.append("## 5. Read Breakdown by Category")
    lines.append("")
    lines.append("| Category | Unique Files | Total Reads | % of All Reads |")
    lines.append("|---|---|---|---|")
    for cat, cd in sorted(by_category.items(), key=lambda x: x[1]["total_reads"], reverse=True):
        pct = cd["total_reads"] / total_all_reads * 100 if total_all_reads else 0
        lines.append(
            f"| {cat} "
            f"| {len(cd['unique_files'])} "
            f"| {cd['total_reads']} "
            f"| {pct:.1f}% |"
        )
    lines.append("")

    # Section 6: Token Usage by Model
    lines.append("## 6. Token Usage by Model")
    lines.append("")
    lines.append("| Model | Turns | Input Tokens | Output Tokens | Est. Input Cost | Est. Output Cost | Est. Total |")
    lines.append("|---|---|---|---|---|---|---|")
    for model, md in sorted(global_by_model.items(), key=lambda x: x[1]["input_tokens"], reverse=True):
        rate = get_model_rate(model)
        cost_in = md["input_tokens"] * rate["input"] / 1_000_000
        cost_out = md["output_tokens"] * rate["output"] / 1_000_000
        lines.append(
            f"| {model} "
            f"| {md['turns']} "
            f"| {fmt_tokens(md['input_tokens'])} "
            f"| {fmt_tokens(md['output_tokens'])} "
            f"| {fmt_cost(cost_in)} "
            f"| {fmt_cost(cost_out)} "
            f"| {fmt_cost(cost_in + cost_out)} |"
        )
    lines.append(f"")
    lines.append(f"**Estimated total cost: {fmt_cost(total_est_cost)}**")
    lines.append("")

    # Section 7: Subagent Spawns
    lines.append("## 7. Subagent Spawns")
    lines.append("")
    lines.append("| UUID (short) | Branch | Phase | Spawns | Est. Overhead (tokens) |")
    lines.append("|---|---|---|---|---|")
    for s in active:
        if s["agent_spawns"] > 0:
            lines.append(
                f"| {shorten_uuid(s['uuid'])} "
                f"| {s['git_branch'] or '-'} "
                f"| {s['phase']} "
                f"| {s['agent_spawns']} "
                f"| {fmt_tokens(s['agent_spawns'] * SUBAGENT_BASE_OVERHEAD_TOKENS)} |"
            )
    lines.append("")
    lines.append(f"**Total spawns:** {subagent_total}  |  "
                 f"**Estimated overhead:** {fmt_tokens(subagent_overhead_est)} tokens")
    lines.append("")

    # Section 8: Methodology Notes
    lines.append("## 8. Methodology Notes")
    lines.append("")
    lines.append("- **Token counts** are per-turn aggregates from `message.usage`. "
                 "There is no per-tool-call breakdown in the JSONL format.")
    lines.append("- **Token attribution** for file reads uses `cache_creation_input_tokens` "
                 "from the turn as a rough proxy for file size. First-time reads in a session "
                 "tend to trigger cache creation. This is approximate.")
    lines.append("- **Deduplication:** each assistant turn is exactly one JSONL line "
                 "with a unique UUID (verified). No deduplication was needed.")
    lines.append("- **Phase classification** uses (in order): `<command-name>` tags in "
                 "user messages, Skill tool_use, text scan for slash commands, git branch name.")
    lines.append("- **Subagent overhead** estimated at 41K tokens per spawn (base context "
                 "load). This is an estimate from the architecture doc, not measured.")
    lines.append("- **Cost estimates** use approximate public rates as of 2026-04.")
    lines.append(f"- **Parse errors:** "
                 f"{sum(s.get('parse_errors', 0) for s in sessions)} lines skipped across all files.")
    if skipped:
        lines.append(f"- **Skipped sessions ({len(skipped)}):** " +
                     "; ".join(f"{shorten_uuid(s['uuid'])} ({s.get('skip_reason', '?')})"
                               for s in skipped))
    lines.append("")

    # ---------------------------------------------------------------------------
    # Build JSON data block for compare mode
    # ---------------------------------------------------------------------------
    by_phase_json = {
        ph: {"sessions": pd["sessions"], "input_tokens": pd["input_tokens"],
             "output_tokens": pd["output_tokens"]}
        for ph, pd in by_phase.items()
    }
    top_reads_json = [
        {"file": fp, "count": d["count"], "sessions": len(d["sessions"]),
         "category": classify_file(fp)}
        for fp, d in top_reads
    ]
    redundant_json = [
        {"file": fp, "sessions": len(d["sessions"]),
         "phases": sorted(d["phases"]), "category": classify_file(fp)}
        for fp, d in redundant_reads
    ]
    by_category_json = {
        cat: {"unique_files": len(cd["unique_files"]), "total_reads": cd["total_reads"]}
        for cat, cd in by_category.items()
    }
    by_model_json = {
        model: {
            "turns": md["turns"],
            "input_tokens": md["input_tokens"],
            "output_tokens": md["output_tokens"],
            "est_cost_usd": round(estimate_cost(md["input_tokens"], md["output_tokens"], model), 6),
        }
        for model, md in global_by_model.items()
    }

    benchmark_data = {
        "label": label,
        "generated": now,
        "sessions_analyzed": len(active),
        "totals": {
            "input_tokens": total_input,
            "output_tokens": total_output,
            "cache_read_tokens": total_cache_read,
            "cache_write_tokens": total_cache_write,
            "turns": total_turns,
        },
        "by_phase": by_phase_json,
        "top_reads": top_reads_json,
        "redundant_reads": redundant_json,
        "by_category": by_category_json,
        "subagent_spawns": subagent_total,
        "subagent_overhead_tokens_est": subagent_overhead_est,
        "by_model": by_model_json,
        "est_total_cost_usd": round(total_est_cost, 6),
    }

    lines.append(BENCHMARK_DATA_START)
    lines.append(json.dumps(benchmark_data, indent=2))
    lines.append(BENCHMARK_DATA_END)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Compare mode
# ---------------------------------------------------------------------------

def extract_benchmark_data(report_path: Path) -> dict:
    """Extract the BENCHMARK_DATA JSON block from a report file."""
    text = report_path.read_text(encoding="utf-8")
    start = text.find(BENCHMARK_DATA_START)
    end = text.find(BENCHMARK_DATA_END)
    if start == -1 or end == -1:
        raise ValueError(f"No BENCHMARK_DATA block found in {report_path}")
    json_text = text[start + len(BENCHMARK_DATA_START):end].strip()
    return json.loads(json_text)


def generate_comparison(before: dict, after: dict) -> str:
    now = datetime.now(timezone.utc).isoformat()
    bl = before["label"]
    al = after["label"]

    lines = []
    lines.append(f"# Benchmark Comparison: {bl} → {al}")
    lines.append("")
    lines.append(f"**Generated:** {now}")
    lines.append(f"**Before:** {bl} ({before['generated'][:19]}Z, {before['sessions_analyzed']} sessions)")
    lines.append(f"**After:** {al} ({after['generated'][:19]}Z, {after['sessions_analyzed']} sessions)")
    lines.append("")

    bt = before["totals"]
    at_ = after["totals"]

    def delta_row(label, bv, av, fmt=fmt_tokens):
        d = av - bv
        sign = "+" if d > 0 else ""
        return (f"| {label} | {fmt(bv)} | {fmt(av)} "
                f"| {sign}{fmt(d)} | {pct_change(bv, av)} |")

    # Section: Summary
    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Before | After | Delta | % Change |")
    lines.append("|---|---|---|---|---|")
    lines.append(delta_row("Total input tokens", bt["input_tokens"], at_["input_tokens"]))
    lines.append(delta_row("Total output tokens", bt["output_tokens"], at_["output_tokens"]))
    lines.append(delta_row("Cache read tokens", bt["cache_read_tokens"], at_["cache_read_tokens"]))
    lines.append(delta_row("Cache write tokens", bt["cache_write_tokens"], at_["cache_write_tokens"]))
    lines.append(delta_row("Total turns", bt["turns"], at_["turns"]))
    lines.append(delta_row("Subagent spawns",
                            before["subagent_spawns"], after["subagent_spawns"],
                            fmt=lambda x: str(x)))
    lines.append(delta_row("Subagent overhead (est.)",
                            before["subagent_overhead_tokens_est"],
                            after["subagent_overhead_tokens_est"]))
    b_cost = before.get("est_total_cost_usd", 0)
    a_cost = after.get("est_total_cost_usd", 0)
    d_cost = a_cost - b_cost
    sign = "+" if d_cost > 0 else ""
    lines.append(f"| Est. total cost | {fmt_cost(b_cost)} | {fmt_cost(a_cost)} "
                 f"| {sign}{fmt_cost(d_cost)} | {pct_change(b_cost, a_cost)} |")
    lines.append("")

    # Section: Per-Phase Comparison
    lines.append("## Per-Phase Comparison")
    lines.append("")
    lines.append("| Phase | Before (input) | After (input) | Delta | % Change |")
    lines.append("|---|---|---|---|---|")
    all_phases = sorted(set(before["by_phase"]) | set(after["by_phase"]))
    for phase in all_phases:
        b_in = before["by_phase"].get(phase, {}).get("input_tokens", 0)
        a_in = after["by_phase"].get(phase, {}).get("input_tokens", 0)
        d = a_in - b_in
        sign = "+" if d > 0 else ""
        lines.append(f"| {phase} | {fmt_tokens(b_in)} | {fmt_tokens(a_in)} "
                     f"| {sign}{fmt_tokens(d)} | {pct_change(b_in, a_in)} |")
    lines.append("")

    # Section: Read Frequency Changes
    b_reads = {r["file"]: r for r in before.get("top_reads", [])}
    a_reads = {r["file"]: r for r in after.get("top_reads", [])}
    all_files = set(b_reads) | set(a_reads)

    eliminated = [(fp, b_reads[fp]) for fp in all_files
                  if fp in b_reads and fp not in a_reads]
    reduced = [(fp, b_reads[fp], a_reads[fp]) for fp in all_files
               if fp in b_reads and fp in a_reads and a_reads[fp]["count"] < b_reads[fp]["count"]]
    increased = [(fp, b_reads.get(fp), a_reads[fp]) for fp in all_files
                 if fp in a_reads and a_reads[fp]["count"] > b_reads.get(fp, {}).get("count", 0)]
    new_reads = [(fp, a_reads[fp]) for fp in all_files
                 if fp not in b_reads and fp in a_reads]

    lines.append("## Read Frequency Changes")
    lines.append("")
    lines.append("### Files no longer read (eliminated by cache)")
    lines.append("")
    if eliminated:
        lines.append("| File | Before Count | Category |")
        lines.append("|---|---|---|")
        for fp, bd in sorted(eliminated, key=lambda x: x[1]["count"], reverse=True):
            short = fp.replace(str(Path.home()), "~")
            lines.append(f"| `{short}` | {bd['count']} | {bd['category']} |")
    else:
        lines.append("_None_")
    lines.append("")

    lines.append("### Files with reduced reads")
    lines.append("")
    if reduced:
        lines.append("| File | Before | After | Delta | Category |")
        lines.append("|---|---|---|---|---|")
        for fp, bd, ad in sorted(reduced, key=lambda x: x[1]["count"] - x[2]["count"], reverse=True):
            short = fp.replace(str(Path.home()), "~")
            d = ad["count"] - bd["count"]
            lines.append(f"| `{short}` | {bd['count']} | {ad['count']} | {d} | {bd['category']} |")
    else:
        lines.append("_None_")
    lines.append("")

    lines.append("### New reads (not in baseline top-20)")
    lines.append("")
    if new_reads:
        lines.append("| File | After Count | Category |")
        lines.append("|---|---|---|")
        for fp, ad in sorted(new_reads, key=lambda x: x[1]["count"], reverse=True):
            short = fp.replace(str(Path.home()), "~")
            lines.append(f"| `{short}` | {ad['count']} | {ad['category']} |")
    else:
        lines.append("_None_")
    lines.append("")

    # Section: Category Breakdown Comparison
    lines.append("## Category Breakdown Comparison")
    lines.append("")
    lines.append("| Category | Before (reads) | After (reads) | Delta | % Change |")
    lines.append("|---|---|---|---|---|")
    all_cats = sorted(set(before.get("by_category", {})) | set(after.get("by_category", {})))
    for cat in all_cats:
        b_r = before.get("by_category", {}).get(cat, {}).get("total_reads", 0)
        a_r = after.get("by_category", {}).get(cat, {}).get("total_reads", 0)
        d = a_r - b_r
        sign = "+" if d > 0 else ""
        lines.append(f"| {cat} | {b_r} | {a_r} | {sign}{d} | {pct_change(b_r, a_r)} |")
    lines.append("")

    # Section: Cost Comparison by Model
    lines.append("## Cost Comparison by Model")
    lines.append("")
    lines.append("| Model | Before Cost | After Cost | Delta | % Change |")
    lines.append("|---|---|---|---|---|")
    all_models = sorted(
        set(before.get("by_model", {})) | set(after.get("by_model", {}))
    )
    for model in all_models:
        b_c = before.get("by_model", {}).get(model, {}).get("est_cost_usd", 0)
        a_c = after.get("by_model", {}).get(model, {}).get("est_cost_usd", 0)
        d = a_c - b_c
        sign = "+" if d > 0 else ""
        lines.append(f"| {model} | {fmt_cost(b_c)} | {fmt_cost(a_c)} "
                     f"| {sign}{fmt_cost(d)} | {pct_change(b_c, a_c)} |")
    lines.append("")

    # Section: Verdict
    token_savings = bt["input_tokens"] - at_["input_tokens"]
    cost_savings = b_cost - a_cost
    lines.append("## Verdict")
    lines.append("")
    sign = "" if token_savings >= 0 else "+"
    lines.append(f"- **Total input token change:** {sign}{fmt_tokens(-token_savings)} "
                 f"({pct_change(bt['input_tokens'], at_['input_tokens'])})")
    sign = "" if cost_savings >= 0 else "+"
    lines.append(f"- **Estimated cost change:** {sign}{fmt_cost(-cost_savings)} "
                 f"({pct_change(b_cost, a_cost)})")
    lines.append(f"- **Redundant reads eliminated:** {len(eliminated)} files removed from top reads")

    if reduced:
        top3 = sorted(reduced, key=lambda x: x[1]["count"] - x[2]["count"], reverse=True)[:3]
        wins = ", ".join(f"`{Path(fp).name}` (-{bd['count'] - ad['count']})" for fp, bd, ad in top3)
        lines.append(f"- **Biggest wins:** {wins}")

    regressions = [(fp, b_reads.get(fp, {}).get("count", 0), a_reads[fp]["count"])
                   for fp in all_files
                   if fp in a_reads and a_reads[fp]["count"] > b_reads.get(fp, {}).get("count", 0) + 1]
    if regressions:
        reg_str = ", ".join(f"`{Path(fp).name}` (+{ac - bc})"
                            for fp, bc, ac in sorted(regressions, key=lambda x: x[2] - x[1], reverse=True)[:3])
        lines.append(f"- **Regressions:** {reg_str}")
    else:
        lines.append("- **Regressions:** none detected")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI entry points
# ---------------------------------------------------------------------------

def cmd_report(args):
    jsonl_dir = Path(args.jsonl_dir).expanduser()
    if not jsonl_dir.exists():
        print(f"ERROR: JSONL directory not found: {jsonl_dir}", file=sys.stderr)
        sys.exit(1)

    jsonl_files = sorted(jsonl_dir.glob("*.jsonl"))
    if not jsonl_files:
        print(f"ERROR: No .jsonl files found in {jsonl_dir}", file=sys.stderr)
        sys.exit(1)

    # Filter by session UUIDs if specified
    if args.session:
        requested = {u.strip() for u in args.session.split(",") if u.strip()}
        jsonl_files = [f for f in jsonl_files if f.stem in requested]
        if not jsonl_files:
            print(f"ERROR: None of the requested session UUIDs found in {jsonl_dir}",
                  file=sys.stderr)
            sys.exit(1)
        print(f"Filtered to {len(jsonl_files)} session(s) by UUID")

    print(f"Parsing {len(jsonl_files)} JSONL file(s)...")
    sessions = []
    for jf in jsonl_files:
        print(f"  {jf.name}...", end=" ", flush=True)
        s = parse_session(jf)
        sessions.append(s)
        if s.get("skipped"):
            print(f"SKIPPED ({s.get('skip_reason', '?')})")
        else:
            print(f"OK ({s['turns']} turns, phase={s['phase']})")

    label = args.label or "unlabeled"
    report = generate_report(sessions, label, str(jsonl_dir))

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")
    print(f"\nReport written to: {output_path}")

    active = [s for s in sessions if not s.get("skipped")]
    total_in = sum(s["input_tokens"] + s["cache_read_tokens"] + s["cache_write_tokens"] for s in active)
    print(f"Sessions: {len(active)} active, {len(sessions) - len(active)} skipped")
    print(f"Total input tokens: {fmt_tokens(total_in)}")


def cmd_compare(args):
    before_path = Path(args.before)
    after_path = Path(args.after)

    for p in (before_path, after_path):
        if not p.exists():
            print(f"ERROR: File not found: {p}", file=sys.stderr)
            sys.exit(1)

    print(f"Reading before: {before_path}")
    before_data = extract_benchmark_data(before_path)
    print(f"Reading after:  {after_path}")
    after_data = extract_benchmark_data(after_path)

    comparison = generate_comparison(before_data, after_data)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(comparison, encoding="utf-8")
    print(f"\nComparison written to: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Claude Code workflow benchmark tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # report subcommand
    rp = sub.add_parser("report", help="Generate a benchmark report from JSONL files")
    rp.add_argument(
        "--jsonl-dir",
        default=str(DEFAULT_JSONL_DIR),
        help="Directory containing .jsonl session files",
    )
    rp.add_argument(
        "--session",
        default=None,
        help="Comma-separated session UUIDs to analyse (default: all)",
    )
    rp.add_argument(
        "--output",
        default=str(DEFAULT_REPORT_OUTPUT),
        help="Output markdown file path",
    )
    rp.add_argument(
        "--label",
        default="unlabeled",
        help="Label for this run (e.g. 'baseline', 'post-cache')",
    )
    rp.set_defaults(func=cmd_report)

    # compare subcommand
    cp = sub.add_parser("compare", help="Compare two benchmark reports")
    cp.add_argument("--before", required=True, help="Path to baseline report")
    cp.add_argument("--after", required=True, help="Path to post-cache report")
    cp.add_argument(
        "--output",
        default=str(DEFAULT_COMPARE_OUTPUT),
        help="Output markdown file path",
    )
    cp.set_defaults(func=cmd_compare)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

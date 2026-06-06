#!/usr/bin/env python3
# CLAUDE-ADAPTER-OWNED — this file provides cost data for the dashboard by
# reading Claude Code JSONL sessions. Do NOT import this module from any file
# in quoin/core/. The portable cost model is dashboard_model.py. The adapter
# boundary: only this file and its siblings in quoin/scripts/ may import
# cost_from_jsonl.
#
# dashboard_cost.py — adapter cost provider for the workflow dashboard.
# Implements make_cost_provider(project_root, home=None) -> CostProvider.
# CostProvider signature: provider(task_name, rows) -> dict|None
#   where rows is a list of ledger-row dicts with keys:
#     {uuid, date, phase, model_or_effort, note, fallback_fires}
# Returns:
#   {"mode": "usd", "usd": float, "tokens": int,
#    "by_phase": {phase: {"usd": float}}}  # usd mode
#   {"mode": "tokens", "usd": None, "tokens": int,
#    "by_phase": {phase: {"tokens": int}}}  # tokens mode
#   None  # no JSONL found for any row UUID — caller stays in counts mode
#
# Per D-04/D-05: memo-cache keyed by (uuid, jsonl_mtime); missing JSONL cached
# as sentinel (uuid, None) to avoid repeated stat storms.

import importlib.util
import os
import pathlib
import sys

# ---------------------------------------------------------------------------
# Cross-load cost_from_jsonl (same-dir spec-load — adapter sibling)
# ---------------------------------------------------------------------------

def _load_sibling(name: str):
    """Load a sibling script from the same directory via spec_from_file_location."""
    path = pathlib.Path(__file__).resolve().parent / f"{name}.py"
    if not path.exists():
        raise ImportError(f"Cannot load {name}: {path} not found")
    module_key = f"_dashboard_cost_{name}"
    # Re-use cached module if already loaded to avoid re-exec
    if module_key in sys.modules:
        return sys.modules[module_key]
    spec = importlib.util.spec_from_file_location(module_key, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot create spec for {name} at {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_key] = mod
    spec.loader.exec_module(mod)
    return mod


_cfj = _load_sibling("cost_from_jsonl")

# Bind the three functions we need from cost_from_jsonl
project_hash = _cfj.project_hash
jsonl_path_for = _cfj.jsonl_path_for
parse_session = _cfj.parse_session


# ---------------------------------------------------------------------------
# Memo-cache (D-05)
# ---------------------------------------------------------------------------

def _make_cache():
    """Return a fresh memo-cache dict keyed by (uuid, mtime_or_None)."""
    return {}


def _lookup_cached(cache: dict, uuid: str, jsonl_path: pathlib.Path):
    """Return cached parse_session result, or _MISS sentinel if not cached.

    Cache key: (uuid, mtime_float_or_None).
    None mtime = file absent (sentinel: never re-stat a missing file for this uuid).
    """
    try:
        mtime = jsonl_path.stat().st_mtime if jsonl_path.exists() else None
    except OSError:
        mtime = None
    key = (uuid, mtime)
    if key in cache:
        return cache[key], key
    return _MISS, key


_MISS = object()  # sentinel for cache miss


# ---------------------------------------------------------------------------
# Core provider factory (D-04)
# ---------------------------------------------------------------------------

def make_cost_provider(project_root, home=None):
    """Return a CostProvider closure bound to project_root.

    project_root: str or pathlib.Path
    home: override for Path.home() (used in tests)

    The returned provider(task_name, rows) -> dict|None:
      - Iterates rows, resolves each row's UUID to a JSONL path
      - Parses each found JSONL (with memo-cache)
      - Aggregates: totalCost > 0 → mode=usd; totalTokens > 0 → mode=tokens; else None
      - by_phase is NESTED: {phase: {"usd": float}} or {phase: {"tokens": int}}
    """
    root = pathlib.Path(project_root).resolve()
    proj_hash = project_hash(str(root))
    cache = _make_cache()

    def provider(task_name, rows):
        """Resolve cost for a task given its ledger rows.

        Returns dict with mode/usd/tokens/by_phase, or None if no JSONL found.
        per D-04 ladder and D-14 nested by_phase contract.
        """
        total_usd = 0.0
        total_tokens = 0
        any_jsonl_found = False

        # Phase aggregators — values differ by mode but we build both and pick
        by_phase_usd = {}    # {phase: float}
        by_phase_tokens = {}  # {phase: int}

        for row in rows:
            uuid = row.get("uuid", "")
            phase = row.get("phase", "")
            if not uuid:
                continue

            jsonl_path = jsonl_path_for(uuid, proj_hash, home=home or pathlib.Path.home())
            cached_result, cache_key = _lookup_cached(cache, uuid, jsonl_path)

            if cached_result is _MISS:
                # Cache miss — parse or record absence
                if jsonl_path.exists():
                    try:
                        result = parse_session(jsonl_path)
                    except (IOError, OSError, Exception):
                        result = None
                else:
                    result = None
                cache[cache_key] = result
                cached_result = result

            if cached_result is None:
                # JSONL absent or unreadable — skip this row
                continue

            any_jsonl_found = True
            usd = cached_result.get("totalCost", 0.0) or 0.0
            tokens = cached_result.get("totalTokens", 0) or 0

            total_usd += usd
            total_tokens += tokens

            if phase:
                by_phase_usd[phase] = by_phase_usd.get(phase, 0.0) + usd
                by_phase_tokens[phase] = by_phase_tokens.get(phase, 0) + tokens

        if not any_jsonl_found:
            return None

        if total_usd > 0:
            # USD mode — nested by_phase: {phase: {"usd": float}}
            by_phase = {ph: {"usd": usd_val} for ph, usd_val in by_phase_usd.items()}
            return {
                "mode": "usd",
                "usd": total_usd,
                "tokens": total_tokens,
                "by_phase": by_phase,
            }
        elif total_tokens > 0:
            # Tokens mode — nested by_phase: {phase: {"tokens": int}}
            by_phase = {ph: {"tokens": tok_val} for ph, tok_val in by_phase_tokens.items()}
            return {
                "mode": "tokens",
                "usd": None,
                "tokens": total_tokens,
                "by_phase": by_phase,
            }
        else:
            # JSONL found but zero cost and zero tokens — treat as no data
            return None

    return provider

"""
cost.py — Cost estimation from pricing.json.

Exposes:
    load_pricing() -> dict
    estimate_cost(model, tokens_in, tokens_out, cache_write, cache_read, pricing) -> Decimal | None

For Claude cells:
    When runtime-reported cost is present, harness records BOTH the runtime
    value AND the estimated value plus their delta as a sanity check.

For Codex cells:
    Returns None. Harness writes cost: not_available in cost.json.
    No token-derived estimate. See quoin/adapters/codex/cost.md.
"""

from __future__ import annotations

import json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Optional

# Default path to pricing.json relative to repo root
_DEFAULT_PRICING_PATH = Path("quoin/benchmarks/harness/pricing.json")

# Codex model name prefix (any model starting with this should return None)
_CODEX_MODEL_PREFIXES = ("gpt-", "o1-", "o3-", "o4-", "codex-")


def load_pricing(pricing_path: Optional[Path] = None) -> dict:
    """
    Load the pricing.json card.

    Parameters
    ----------
    pricing_path:
        Optional path to pricing.json. Defaults to
        quoin/benchmarks/harness/pricing.json relative to cwd.

    Returns
    -------
    Parsed pricing dict, or empty dict on failure.
    """
    if pricing_path is None:
        pricing_path = _DEFAULT_PRICING_PATH

    if not pricing_path.exists():
        # Try relative to this file
        local_path = Path(__file__).parent / "pricing.json"
        if local_path.exists():
            pricing_path = local_path
        else:
            return {}

    try:
        return json.loads(pricing_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def estimate_cost(
    model: str,
    tokens_in: Optional[int],
    tokens_out: Optional[int],
    cache_write: Optional[int] = None,
    cache_read: Optional[int] = None,
    pricing: Optional[dict] = None,
) -> Optional[Decimal]:
    """
    Estimate cost in USD for a model invocation using the pricing card.

    For Codex models: always returns None (per D-12 and codex/cost.md).
    For Claude models: returns a Decimal cost estimate, or None if the model
      is not in the pricing card.

    Parameters
    ----------
    model:
        The model identifier (dated snapshot form for Claude; model name for Codex).
    tokens_in:
        Number of input tokens (excluding cached tokens).
    tokens_out:
        Number of output tokens.
    cache_write:
        Number of cache-write input tokens (prompt cache writes).
    cache_read:
        Number of cache-read input tokens (prompt cache hits).
    pricing:
        The loaded pricing dict from load_pricing(). If None, loads from disk.

    Returns
    -------
    Decimal cost in USD rounded to 6 decimal places, or None if not computable.
    """
    # Codex models: always return None (no token-derived estimates per codex/cost.md)
    model_lower = model.lower()
    if any(model_lower.startswith(prefix) for prefix in _CODEX_MODEL_PREFIXES):
        return None

    if pricing is None:
        pricing = load_pricing()

    models_section = pricing.get("models", {})

    # Look for exact match, then prefix match
    model_pricing = models_section.get(model)
    if model_pricing is None:
        # Try matching by prefix (strip date suffix)
        for key in models_section:
            if not key.startswith("_") and model.startswith(key.rsplit("-", 1)[0]):
                model_pricing = models_section[key]
                break

    if model_pricing is None:
        return None

    input_rate = Decimal(str(model_pricing.get("input_per_1m_usd", 0)))
    output_rate = Decimal(str(model_pricing.get("output_per_1m_usd", 0)))
    cache_write_rate = Decimal(str(model_pricing.get("cache_write_per_1m_usd", 0)))
    cache_read_rate = Decimal(str(model_pricing.get("cache_read_per_1m_usd", 0)))

    million = Decimal("1000000")

    cost = Decimal("0")
    if tokens_in:
        cost += Decimal(str(tokens_in)) / million * input_rate
    if tokens_out:
        cost += Decimal(str(tokens_out)) / million * output_rate
    if cache_write:
        cost += Decimal(str(cache_write)) / million * cache_write_rate
    if cache_read:
        cost += Decimal(str(cache_read)) / million * cache_read_rate

    return cost.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)

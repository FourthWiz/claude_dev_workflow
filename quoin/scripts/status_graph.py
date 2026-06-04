#!/usr/bin/env python3
"""Compatibility wrapper for quoin.core.scripts.status_graph."""

import importlib.util
import sys
from pathlib import Path


_CORE_PATH = Path(__file__).resolve().parents[1] / "core" / "scripts" / "status_graph.py"
_SPEC = importlib.util.spec_from_file_location("_quoin_core_status_graph", _CORE_PATH)
_CORE = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
# Register in sys.modules before exec so @dataclass can resolve cls.__module__
# (required for Python 3.8+ compatibility with dynamic module loading).
sys.modules["_quoin_core_status_graph"] = _CORE
_SPEC.loader.exec_module(_CORE)

for _name in dir(_CORE):
    if _name not in {"__name__", "__loader__", "__package__", "__spec__"}:
        globals()[_name] = getattr(_CORE, _name)


if __name__ == "__main__":
    sys.exit(_CORE.main())

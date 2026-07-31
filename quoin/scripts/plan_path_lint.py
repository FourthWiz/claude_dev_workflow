#!/usr/bin/env python3
"""Compatibility wrapper for quoin.core.scripts.plan_path_lint."""

import importlib.util
import sys
from pathlib import Path


_CORE_PATH = Path(__file__).resolve().parents[1] / "core" / "scripts" / "plan_path_lint.py"
_SPEC = importlib.util.spec_from_file_location("_quoin_core_plan_path_lint", _CORE_PATH)
_CORE = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
# The core module is self-contained (D-P4, no sibling-core import) — this insert is
# kept for pattern-parity with the twin (nested_root_check.py) only.
sys.path.insert(0, str(_CORE_PATH.parent))
_SPEC.loader.exec_module(_CORE)

for _name in dir(_CORE):
    if _name not in {"__name__", "__loader__", "__package__", "__spec__"}:
        globals()[_name] = getattr(_CORE, _name)


if __name__ == "__main__":
    sys.exit(_CORE.main())

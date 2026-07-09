#!/usr/bin/env python3
"""Compatibility wrapper for quoin.core.scripts.worktree_isolation."""

import importlib.util
import sys
from pathlib import Path


_CORE_PATH = Path(__file__).resolve().parents[1] / "core" / "scripts" / "worktree_isolation.py"
_SPEC = importlib.util.spec_from_file_location("_quoin_core_worktree_isolation", _CORE_PATH)
assert _SPEC is not None
_CORE = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(_CORE)

for _name in dir(_CORE):
    if _name not in {"__name__", "__loader__", "__package__", "__spec__"}:
        globals()[_name] = getattr(_CORE, _name)

# worktree_isolation.py is function-only (no @dataclass / metaclass), so sys.modules
# registration can be safely omitted (mirrors dispatch_config.py). The unique spec name
# "_quoin_core_worktree_isolation" prevents any sys.modules NAME COLLISION.


if __name__ == "__main__":
    sys.exit(_CORE.main())

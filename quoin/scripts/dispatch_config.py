#!/usr/bin/env python3
"""Compatibility wrapper for quoin.core.scripts.dispatch_config."""

import importlib.util
import sys
from pathlib import Path


_CORE_PATH = Path(__file__).resolve().parents[1] / "core" / "scripts" / "dispatch_config.py"
_SPEC = importlib.util.spec_from_file_location("_quoin_core_dispatch_config", _CORE_PATH)
assert _SPEC is not None
_CORE = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(_CORE)

for _name in dir(_CORE):
    if _name not in {"__name__", "__loader__", "__package__", "__spec__"}:
        globals()[_name] = getattr(_CORE, _name)

# NOTE on sys.modules registration:
# branch_hygiene.py registers `sys.modules[_SPEC.name] = _CORE` before exec_module
# SPECIFICALLY because it uses @dataclasses.dataclass — whose cls.__module__ resolution
# requires the module be findable in sys.modules at class-definition time.
# dispatch_config.py is function-only (no @dataclass, no metaclass), so sys.modules
# registration can be safely omitted here. The unique spec name
# "_quoin_core_dispatch_config" still prevents any sys.modules NAME COLLISION
# (lesson 2026-06-08), but that is not the reason registration is omitted.
# If a @dataclass is ever added to dispatch_config.py, switch to the
# branch_hygiene.py idiom: register before exec_module.


if __name__ == "__main__":
    sys.exit(_CORE.main())

#!/usr/bin/env python3
"""Compatibility wrapper for quoin.core.scripts.gate_fullsuite_sidecar."""

import importlib.util
import sys
from pathlib import Path


_MODULE_NAME = "_quoin_core_gate_fullsuite_sidecar"
_CORE_PATH = Path(__file__).resolve().parents[1] / "core" / "scripts" / "gate_fullsuite_sidecar.py"
_SPEC = importlib.util.spec_from_file_location(_MODULE_NAME, _CORE_PATH)
_CORE = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
# Register before exec so that imports within the core module resolve correctly
sys.modules[_MODULE_NAME] = _CORE
_SPEC.loader.exec_module(_CORE)

for _name in dir(_CORE):
    if _name not in {"__name__", "__loader__", "__package__", "__spec__"}:
        globals()[_name] = getattr(_CORE, _name)

if __name__ == "__main__":
    sys.exit(_CORE.main())

"""
conftest.py — Pytest configuration for quoin dev tests.

Adds the repo root to sys.path so that `quoin.benchmarks` and other
quoin sub-packages are importable without installation.
"""
import sys
from pathlib import Path

# Repo root is 3 levels up from this file: quoin/dev/tests/conftest.py → quoin/
REPO_ROOT = Path(__file__).parent.parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

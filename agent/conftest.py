"""Root conftest — makes the agent/ directory importable as a package root.

Pytest loads this file automatically before collecting tests from agent/tests/.
Inserting the parent of this file (i.e. agent/) into sys.path ensures that
sub-packages such as `core`, `providers`, `rag`, `server`, and `scripts` are
importable without any explicit sys.path manipulation in individual test files.
"""
import sys
from pathlib import Path

# Ensure agent/ is on sys.path so that `from core.agent import ...` works.
sys.path.insert(0, str(Path(__file__).resolve().parent))

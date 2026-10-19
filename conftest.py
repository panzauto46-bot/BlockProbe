"""Make the src-layout package importable without an install.

pytest's ``pythonpath = ["src"]`` setting only mutates the pytest process's
``sys.path``. A test that spawns ``python -m blockprobe`` as a subprocess does
not inherit it, so a bare checkout still fails with a confusing
``ModuleNotFoundError`` on the subprocess test.

Exporting ``PYTHONPATH`` as well makes child processes inherit the same path,
so the suite runs from a fresh checkout on Windows and Linux alike.
"""

import os
import sys
from pathlib import Path

SRC = str(Path(__file__).resolve().parent / "src")

if SRC not in sys.path:
    sys.path.insert(0, SRC)

existing = os.environ.get("PYTHONPATH", "")
parts = [p for p in existing.split(os.pathsep) if p]
if SRC not in parts:
    os.environ["PYTHONPATH"] = os.pathsep.join([SRC, *parts])

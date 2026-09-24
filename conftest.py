"""Put the repository root on sys.path for tests.

The project is installed editable with a finder restricted to the `src*`
packages, so `benchmarks.*` is not importable without this. Keeping it at the
root also means `pytest` works from any working directory.
"""

import sys
from pathlib import Path

_ROOT = str(Path(__file__).resolve().parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

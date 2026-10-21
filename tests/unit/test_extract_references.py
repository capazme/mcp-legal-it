"""scripts/corpus/extract_references.py is a one-shot migration kept for the record.

Run again after the migration it used to crash on a missing attribute; it must
say the migration is done, exit non-zero and leave content/references alone.
"""

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "corpus" / "extract_references.py"
REFERENCES = REPO / "content" / "references"


def test_rerun_explains_and_writes_nothing():
    before = {p.name: p.stat().st_mtime_ns for p in REFERENCES.glob("*.md")}
    done = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True, timeout=120)
    assert done.returncode == 2, done.stderr
    assert "migration already done" in done.stderr
    assert "Traceback" not in done.stderr
    assert {p.name: p.stat().st_mtime_ns for p in REFERENCES.glob("*.md")} == before

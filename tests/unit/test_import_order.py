"""Every tool module imports cleanly when it is the first thing imported.

A tool module imports `src.server`, which imports every tool module.
So a tool imported first runs server.py while it is itself half-initialised,
and a sibling that does `from src.tools.<that tool> import <name>` at
module level fails with ImportError. The server never sees it (server.py is
always its entry point), but a library user or a single test file does: that
is how `from src.tools.legal_citations import ...` broke.
"""

import ast
import subprocess
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[2] / "plugin" / "server" / "src" / "tools"
SERVER_DIR = TOOLS.parents[1]


def _sibling_name_imports(path: Path) -> list[str]:
    """Module-level `from src.tools.<x> import <name>` statements."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [
        f"line {node.lineno}: from {node.module} import ..."
        for node in tree.body
        if isinstance(node, ast.ImportFrom)
        and (node.module or "").startswith("src.tools.")
    ]


def test_no_tool_imports_a_name_from_a_sibling_tool():
    offenders = {
        path.name: found
        for path in sorted(TOOLS.glob("*.py"))
        if (found := _sibling_name_imports(path))
    }
    assert not offenders, (
        "import the sibling module (`from src.tools import x`) and "
        f"read the name at call time: {offenders}"
    )


@pytest.mark.parametrize("module", ["legal_citations", "parlamento"])
def test_tool_module_imports_first(module):
    done = subprocess.run(
        [sys.executable, "-c", f"import src.tools.{module}"],
        cwd=SERVER_DIR, capture_output=True, text=True, timeout=120,
    )
    assert done.returncode == 0, done.stderr[-2000:]

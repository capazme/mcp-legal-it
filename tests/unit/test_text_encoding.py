"""Every text file the package opens names its encoding (#76).

Without `encoding=` Python uses the locale's: cp1252 on Windows, where the server failed at
start with a UnicodeDecodeError on the bundled JSON tables (privacy_gdpr.py first). This scan
fails on any `open()` / `Path.open()` in text mode, `read_text()` or `write_text()` without it.
"""
from __future__ import annotations

import ast
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[2] / "plugin" / "server" / "mcp_legal_it"
TEXT_CALLS = {"open", "read_text", "write_text"}


def _mode(node: ast.Call) -> str | None:
    """The literal mode of an open() call ("" when absent); None when it is not a literal."""
    func = node.func
    position = 1 if isinstance(func, ast.Name) else 0   # open(path, mode) / path.open(mode)
    value = node.args[position] if len(node.args) > position else None
    for kw in node.keywords:
        if kw.arg == "mode":
            value = kw.value
    if value is None:
        return ""
    if isinstance(value, ast.Constant) and isinstance(value.value, str):
        return value.value
    return None


def text_calls_without_encoding(source: str) -> list[int]:
    """Lines of the text-mode open/read_text/write_text calls in *source* that name no encoding."""
    lines = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
        if name not in TEXT_CALLS or any(kw.arg == "encoding" for kw in node.keywords):
            continue
        if name == "open":
            mode = _mode(node)
            if mode is None or "b" in mode:   # binary, or a mode only known at run time
                continue
        lines.append(node.lineno)
    return lines


def test_every_text_open_names_its_encoding():
    missing = [
        f"{path.relative_to(PACKAGE.parents[1])}:{line}"
        for path in sorted(PACKAGE.rglob("*.py"))
        for line in text_calls_without_encoding(path.read_text(encoding="utf-8"))
    ]
    assert missing == [], "text I/O without encoding=: " + ", ".join(missing)


def test_the_scan_catches_each_form():
    src = (
        "open(p)\nopen(p, 'r')\np.open()\np.read_text()\np.write_text(s)\n"
        "open(p, 'rb')\nopen(p, encoding='utf-8')\np.read_text(encoding='utf-8')\np.open('wb')\n"
    )
    assert text_calls_without_encoding(src) == [1, 2, 3, 4, 5]


def test_importing_the_server_reads_nothing_in_the_locale_encoding():
    # The same check at run time: PEP 597's EncodingWarning, raised as an error when the
    # package itself opens text without an encoding while the server is built.
    import os
    import subprocess
    import sys

    env = {k: v for k, v in os.environ.items() if k not in ("LEGAL_PROFILE", "PYTHONWARNINGS")}
    out = subprocess.run(
        # `-W` matches the module name literally: the regex for the whole package goes in code.
        [sys.executable, "-X", "warn_default_encoding", "-c",
         "import warnings; warnings.filterwarnings('error', category=EncodingWarning, "
         "module=r'mcp_legal_it(\\..*)?$'); import mcp_legal_it.server"],
        cwd=PACKAGE.parent, env=env, capture_output=True, text=True,
    )
    assert out.returncode == 0, out.stderr[-2000:]

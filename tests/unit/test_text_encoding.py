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


# Modules whose `open(path, mode, ..., encoding=)` takes the path first, like the builtin.
_OPEN_MODULES = {"io", "codecs"}


def _open_aliases(tree: ast.AST) -> set[str]:
    """Names bound to an open function: `open`, `from io import open as o`, `o = open`."""
    names = {"open"}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module in _OPEN_MODULES:
            names |= {a.asname or a.name for a in node.names if a.name == "open"}
        elif isinstance(node, ast.Assign) and isinstance(node.value, ast.Name) and node.value.id in names:
            names |= {t.id for t in node.targets if isinstance(t, ast.Name)}
    return names


def _mode(node: ast.Call, position: int) -> str | None:
    """The literal mode of an open() call ("" when absent); None when it is not a literal."""
    value = node.args[position] if len(node.args) > position else None
    for kw in node.keywords:
        if kw.arg == "mode":
            value = kw.value
    if value is None:
        return ""
    if isinstance(value, ast.Constant) and isinstance(value.value, str):
        return value.value
    return None


def _names_encoding(node: ast.Call) -> bool:
    """`encoding=` given, and not None (None is the locale's encoding again)."""
    return any(
        kw.arg == "encoding" and not (isinstance(kw.value, ast.Constant) and kw.value.value is None)
        for kw in node.keywords
    )


def text_calls_without_encoding(source: str) -> list[int]:
    """Lines of the text-mode open/read_text/write_text calls in *source* that name no encoding.

    Covers the builtin `open`, `io.open`, `codecs.open`, an open bound to another name, and
    `Path.open`, `Path.read_text`, `Path.write_text`; `encoding=None` counts as missing.
    """
    tree = ast.parse(source)
    aliases = _open_aliases(tree)
    lines = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or _names_encoding(node):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id in aliases:
            position = 1                                    # open(path, mode)
        elif isinstance(func, ast.Attribute) and func.attr == "open":
            module = func.value.id if isinstance(func.value, ast.Name) else ""
            position = 1 if module in _OPEN_MODULES else 0  # io.open(path, mode) / path.open(mode)
        elif isinstance(func, ast.Attribute) and func.attr in ("read_text", "write_text"):
            lines.append(node.lineno)
            continue
        else:
            continue
        mode = _mode(node, position)
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


def test_the_scan_catches_io_codecs_aliases_and_encoding_none():
    # #76 review: io.open read the path as the mode, codecs.open and aliases were not seen,
    # encoding=None passed as named.
    src = (
        "import io, codecs\nfrom io import open as apri\nleggi = open\n"
        "io.open(p)\ncodecs.open(p, 'r')\napri(p)\nleggi(p)\nopen(p, encoding=None)\n"
        "io.open(p, 'rb')\ncodecs.open(p, 'r', encoding='utf-8')\napri(p, 'wb')\n"
    )
    assert text_calls_without_encoding(src) == [4, 5, 6, 7, 8]


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

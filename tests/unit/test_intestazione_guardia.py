"""Every Normattiva download point checks the page's heading against the URN it asked for.

Normattiva's resolver does not check what it is asked: the URN of a D.M. 7 agosto 1990,
n. 241 serves the page of L. 7 agosto 1990, n. 241. ``scraper.controlla_intestazione``
refuses such a page; this test fails when a function opens a Normattiva client without
calling it, unless the function is in ``SENZA_CONTROLLO`` with the reason it needs none.
"""

import ast
from pathlib import Path

VISUALEX = Path(__file__).resolve().parents[2] / "plugin" / "server" / "mcp_legal_it" / "lib" / "visualex"
FILE = ("scraper.py", "akn_fetch.py", "aggiornamenti.py")

#: The download points that need no heading check, each with why.
SENZA_CONTROLLO = {
    # The landing page of a year-only act: act_full_date reads its identity (title, heading,
    # ELI date) and with_full_date refuses another act's page for every type.
    "_act_metadata": "identity read by act_full_date",
    # The control act (L. 241/1990), accepted only when it reads with its own date.
    "normattiva_serves_acts": "the control act, checked by its date",
}


def _apre_normattiva(nodo: ast.AST) -> bool:
    for figlio in ast.walk(nodo):
        if (isinstance(figlio, ast.Call) and getattr(figlio.func, "id", getattr(figlio.func, "attr", "")) == "async_client"
                and figlio.args and isinstance(figlio.args[0], ast.Constant) and figlio.args[0].value == "normattiva"):
            return True
    return False


def _controlla(nodo: ast.AST) -> bool:
    return any(isinstance(f, ast.Call) and getattr(f.func, "id", getattr(f.func, "attr", "")) == "controlla_intestazione"
               for f in ast.walk(nodo))


def _punti() -> dict[str, bool]:
    punti = {}
    for nome in FILE:
        albero = ast.parse((VISUALEX / nome).read_text(encoding="utf-8"))
        for nodo in ast.walk(albero):
            if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)) and _apre_normattiva(nodo):
                punti[f"{nome}:{nodo.name}"] = _controlla(nodo)
    return punti


def test_every_download_point_checks_the_heading():
    punti = _punti()
    assert punti, "no Normattiva download point found: the scan is broken"
    scoperti = [p for p, ok in punti.items() if not ok and p.split(":")[1] not in SENZA_CONTROLLO]
    assert not scoperti, f"Normattiva download points without controlla_intestazione: {scoperti}"


def test_the_exceptions_are_still_download_points():
    # A stale exception would hide a new function with the same name.
    nomi = {p.split(":")[1] for p in _punti()}
    assert set(SENZA_CONTROLLO) <= nomi

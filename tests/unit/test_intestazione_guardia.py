"""Every Normattiva download point checks the page's heading against the URN it asked for.

Normattiva's resolver does not check what it is asked: the URN of a D.M. 7 agosto 1990,
n. 241 serves the page of L. 7 agosto 1990, n. 241. ``scraper.controlla_intestazione``
refuses such a page; this test fails when a function opens a Normattiva client without
calling it, unless the function is in ``SENZA_CONTROLLO`` with the reason it needs none.
"""

import ast
from pathlib import Path

PACCHETTO = Path(__file__).resolve().parents[2] / "plugin" / "server" / "mcp_legal_it"
#: The download points that need no heading check, each with why.
SENZA_CONTROLLO = {
    # The landing page of a year-only act: act_full_date reads its identity (title, heading,
    # ELI date) and with_full_date refuses another act's page for every type.
    "_act_metadata": "identity read by act_full_date",
    # The control act (L. 241/1990), accepted only when it reads with its own date.
    "normattiva_serves_acts": "the control act, checked by its date",
}


def _costanti(albero: ast.Module) -> dict[str, str]:
    """The module's string constants (``FONTE = "normattiva"``), to read a client's source."""
    return {t.id: n.value.value for n in albero.body if isinstance(n, ast.Assign) and isinstance(n.value, ast.Constant)
            and isinstance(n.value.value, str) for t in n.targets if isinstance(t, ast.Name)}


def _nome(chiamata: ast.Call) -> str:
    return getattr(chiamata.func, "id", getattr(chiamata.func, "attr", ""))


def _apre_normattiva(nodo: ast.AST, costanti: dict[str, str]) -> bool:
    def valore(arg: ast.AST) -> "str | None":
        if isinstance(arg, ast.Constant):
            return arg.value
        return costanti.get(arg.id) if isinstance(arg, ast.Name) else None

    for figlio in ast.walk(nodo):
        if isinstance(figlio, ast.Call) and _nome(figlio) == "async_client":
            fonti = [valore(a) for a in figlio.args[:1]] + [valore(k.value) for k in figlio.keywords if k.arg == "fonte"]
            if "normattiva" in fonti:
                return True
    return False


def _controlla(nodo: ast.AST) -> bool:
    return any(isinstance(f, ast.Call) and _nome(f) == "controlla_intestazione" for f in ast.walk(nodo))


def _punti() -> dict[str, bool]:
    """Every function of the package that opens a Normattiva client, and whether it checks."""
    punti = {}
    for percorso in sorted(PACCHETTO.rglob("*.py")):
        albero = ast.parse(percorso.read_text(encoding="utf-8"))
        costanti = _costanti(albero)
        for nodo in ast.walk(albero):
            if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)) and _apre_normattiva(nodo, costanti):
                punti[f"{percorso.relative_to(PACCHETTO)}:{nodo.name}"] = _controlla(nodo)
    return punti


def test_the_scan_reads_every_way_of_naming_the_source():
    sorgente = (
        'FONTE = "normattiva"\n'
        "async def a():\n    async with async_client(\"normattiva\") as c: ...\n"
        "async def b():\n    async with async_client(fonte=\"normattiva\") as c: ...\n"
        "async def c():\n    async with async_client(FONTE) as c: ...\n"
        "async def d():\n    async with async_client(\"eurlex\") as c: ...\n"
    )
    albero = ast.parse(sorgente)
    costanti = _costanti(albero)
    aperti = [n.name for n in albero.body if isinstance(n, ast.AsyncFunctionDef) and _apre_normattiva(n, costanti)]
    assert aperti == ["a", "b", "c"]


def test_every_download_point_checks_the_heading():
    punti = _punti()
    assert punti, "no Normattiva download point found: the scan is broken"
    scoperti = [p for p, ok in punti.items() if not ok and p.split(":")[1] not in SENZA_CONTROLLO]
    assert not scoperti, f"Normattiva download points without controlla_intestazione: {scoperti}"


def test_the_exceptions_are_still_download_points():
    # A stale exception would hide a new function with the same name.
    nomi = {p.split(":")[1] for p in _punti()}
    assert set(SENZA_CONTROLLO) <= nomi

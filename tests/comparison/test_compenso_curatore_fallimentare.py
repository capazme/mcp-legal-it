"""Comparison: compenso_curatore_fallimentare vs avvocatoandreani.it.

Page: https://www.avvocatoandreani.it/servizi/calcolo-compenso-curatore-fallimentare.php

Norm: DM 25 gennaio 2012 n. 30, art. 1 - the decree sets a MIN-MAX range of
percentages per bracket on the realised assets (comma 1: 12-14% up to
16.227,08; 10-12% up to 24.340,62; 8,5-9,5% up to 40.567,68; 7-8% up to
81.135,38; 5,5-6,5% up to 405.676,89; 4-5% up to 811.353,79; 0,90-1,80% up to
2.434.061,37; 0,45-0,90% beyond) and on the ascertained liabilities (comma 2:
0,19-0,94% on the first 81.131,38; 0,06-0,46% beyond), with an overall minimum
of 811,35 euro (art. 4).

The site returns three columns (Minimo / Medio / Massimo) plus a 5% flat
expense refund. The tool returns a single figure and declares (Precisione:
INDICATIVO) that it applies "percentuali medie semplificate": the comparable
site value is therefore the "Medio" column of "Compenso Totale" (before the 5%
flat expenses, which the tool does not compute). Each test also records the
site's min-max range in the failure message so phase 2 can see whether the
tool at least falls inside the decree's range.

Tolerance: 0,01 euro (brief). No wider tolerance is used.
"""

import sys

import pytest

sys.path.insert(0, "/Users/gpuzio/Desktop/CODE/server-infra2.0/mcp-legal-it")

import src.server  # noqa: E402,F401  (registers all tool modules)
from src.tools.parcelle_professionisti import compenso_curatore_fallimentare  # noqa: E402

from .conftest import accept_cookies, goto, parse_euro  # noqa: E402

_fn = getattr(compenso_curatore_fallimentare, "fn", compenso_curatore_fallimentare)

PAGE = "calcolo-compenso-curatore-fallimentare.php"
TOL = 0.01


def _fmt_it(value: float) -> str:
    return f"{value:.2f}".replace(".", ",")


def _row(tables_text: str, label: str) -> tuple[float, float, float] | None:
    """Return (min, medio, max) of the first line starting with `label`."""
    for line in tables_text.splitlines():
        if line.strip().startswith(label):
            cells = [c.strip() for c in line.split("\t") if "€" in c]
            if len(cells) >= 3:
                return tuple(parse_euro(c) for c in cells[-3:])
    return None


def _site(page, attivo: float, passivo: float) -> dict:
    goto(page, PAGE, wait_ms=1500)
    page.fill("#Attivo", _fmt_it(attivo))
    page.fill("#Passivo", _fmt_it(passivo))
    accept_cookies(page)
    # force=True: the consent overlay (re-injected after goto) can intercept
    # the click. A DOM-level .click() via evaluate did not post the form
    # reliably (the page never showed the result), a forced click does.
    page.click("#button1", force=True)
    page.wait_for_url("**#Res", timeout=60000)
    page.wait_for_timeout(2500)
    text = "\n".join(t.inner_text() for t in page.query_selector_all("table"))
    attivo_row = _row(text, "1) Compenso totale sull'Attivo")
    passivo_row = _row(text, "2) Compenso totale sul Passivo")
    # "Compenso Totale 1) + 2)" when there are liabilities, "Compenso Totale 1)"
    # when the liabilities are zero (no passivo table): the prefix covers both.
    totale = _row(text, "Compenso Totale 1)")
    adeguato = _row(text, "Compenso Totale adeguato al minimo")
    assert totale is not None, f"site result not found:\n{text[:1500]}"
    return {
        "attivo": attivo_row,
        "passivo": passivo_row,
        "totale": totale,
        "adeguato": adeguato,
        "finale": adeguato or totale,
    }


def _compare(page, attivo: float, passivo: float) -> None:
    tool = _fn(attivo_realizzato=attivo, passivo_accertato=passivo)
    site = _site(page, attivo, passivo)
    s_min, s_med, s_max = site["finale"]
    t = tool["totale_compenso"]
    in_range = s_min - TOL <= t <= s_max + TOL
    detail = (
        f"attivo={attivo} passivo={passivo} | tool totale={t:.2f} "
        f"(attivo {tool['compenso_su_attivo']:.2f}, passivo {tool['compenso_su_passivo']:.2f}) | "
        f"sito min/medio/max={s_min:.2f}/{s_med:.2f}/{s_max:.2f} "
        f"(attivo {site['attivo']}, passivo {site['passivo']}) | "
        f"tool dentro la forbice del DM: {in_range}"
    )
    assert abs(t - s_med) <= TOL, "Compenso totale (medio): " + detail


def test_confine_primo_scaglione_passivo_nullo(page):
    """Limit case: exactly the first bracket ceiling (16.227,08), no liabilities.

    Plan: art. 1 lett. a, 12-14% = 1.947,25-2.271,79 euro; the tool returns
    2.271,79 (the maximum, 14%). Site medio expected 2.109,52 (13%).
    """
    _compare(page, 16227.08, 0)


def test_procedura_media(page):
    """Plan: attivo 8.015,20-9.258,60; passivo 225,47-1.309,43; total
    8.240,67-10.568,03 (DM 30/2012 art. 1 commi 1-2). The tool gives 11.226,76,
    outside the range (passivo at half the asset rates).
    """
    _compare(page, 100000, 200000)


def test_procedura_piccola_soglia_minimo(page):
    """Limit case (minimum). Plan: attivo 600-700, passivo 19-94: total
    619-794, raised to the minimum of 811,35 (DM 30/2012 art. 4). The tool
    gives 1.400,00.
    """
    _compare(page, 5000, 10000)


def test_procedura_grande_scaglioni_alti(page):
    """Plan: attivo 58.205,59-83.713,63; passivo 3.105,47-23.389,43; total
    61.311,06-107.103,06 (DM 30/2012 art. 1). Tool: 91.536,18.
    """
    _compare(page, 3000000, 5000000)


def test_confine_scaglione_passivo(page):
    """Limit case: liabilities exactly at the 81.131,38 bracket ceiling
    (art. 1 comma 2: 0,19-0,94%) and assets exactly at the 81.135,38 ceiling
    of the 7-8% bracket (art. 1 comma 1). The tool's own brackets stop at
    81.131,36 instead.
    """
    _compare(page, 81135.38, 81131.38)


def test_massimo_dichiarato_dal_tool(page):
    """Limit case: very large procedure (attivo 100 mln). The tool caps the
    fee at the 'massimo' 405.656,80 declared in its docstring; DM 30/2012
    art. 1 has no such overall cap (only the art. 4 minimum), so the site is
    expected to apply 0,45-0,90% beyond 2.434.061,37 without a ceiling.
    """
    _compare(page, 100_000_000, 0)

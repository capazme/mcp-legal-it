"""Comparison: grado_parentela vs avvocatoandreani.it (calcolo-grado-di-parentela.php).

The site returns a single sentence, e.g.
  "Tra  e suo cugino vi è una parentela di 4° grado in linea collaterale."
It gives degree and line (art. 76 c.c.) and also handles affinity (art. 78 c.c.);
it does NOT give the inheritance-tax treatment, so the tool's
``imposta_successione`` field cannot be benchmarked here (see the notes of each case).
The site distinguishes "retta ascendente/discendente"; the tool only says
"retta", so the comparison checks the first word of the line.
"""

import re
import sys

import pytest

from tests.comparison.conftest import goto

sys.path.insert(0, "/Users/gpuzio/Desktop/CODE/server-infra2.0/mcp-legal-it")
import src.server  # noqa: E402,F401  (registers every tool module)
from src.tools.proprieta_successioni import grado_parentela  # noqa: E402

_fn = getattr(grado_parentela, "fn", grado_parentela)
PAGE = "calcolo-grado-di-parentela.php"
_RESULT_RE = re.compile(r"vi è una (parentela|affinità) di (\d+)° grado in linea (\w+)(?: (\w+))?")


def _site(page, option_value: str) -> dict:
    goto(page, PAGE)
    page.select_option("select[name='Parentela']", option_value)
    # A plain click (even force=True) does not submit after the CMP overlay is
    # removed by accept_cookies; requestSubmit keeps the "Op" submitter field.
    with page.expect_navigation(wait_until="domcontentloaded"):
        page.evaluate(
            "() => { const f = document.forms.CalcParentela;"
            " f.requestSubmit(f.querySelector('input[type=submit]')); }"
        )
    page.wait_for_timeout(2500)
    text = page.inner_text("body")
    m = _RESULT_RE.search(text)
    assert m, "result sentence not found on the site"
    return {"tipo": m.group(1), "grado": int(m.group(2)), "linea": m.group(3), "verso": m.group(4)}


def _compare(page, relazione: str, option_value: str, grado_atteso: int, linea_attesa: str):
    tool = _fn(relazione=relazione)
    assert "errore" not in tool, tool
    site = _site(page, option_value)
    assert site["tipo"] == "parentela"
    assert tool["grado"] == site["grado"], f"grado tool={tool['grado']} sito={site['grado']}"
    assert tool["linea"] == site["linea"], f"linea tool={tool['linea']} sito={site['linea']}"
    # sanity against the plan's expectation (art. 76 c.c.)
    assert site["grado"] == grado_atteso and site["linea"] == linea_attesa
    return tool, site


# Plan: "Quarto grado in linea collaterale (art. 76 c.c.); imposta 6% senza franchigia."
def test_cugino(page):
    _compare(page, "cugino", "17", 4, "collaterale")


# Plan: "Secondo grado in linea retta; imposta 4% con franchigia 1.000.000 (art. 7 TUS);
# il tool indica 6% senza franchigia." Site gives only grade/line (art. 76 c.c.).
def test_nonno(page):
    tool, _ = _compare(page, "nonno", "2", 2, "retta")
    # tax treatment not on the site: recorded in the report, not asserted here


# Plan: "Secondo grado collaterale; franchigia 100.000 e 6%; il tool indica 6% senza franchigia."
# Site option "fratello" (12). Art. 76 c.c.
def test_catena_fratello(page):
    _compare(page, "genitore,figlio", "12", 2, "collaterale")


# Plan: "Nessun vincolo oltre il sesto grado (art. 77 c.c.); imposta 8%."
# The site has no 7th-degree option (only cugino di 3° grado = 8th degree).
def test_settimo_grado(page):
    pytest.skip("Il sito non offre un rapporto di 7° grado (figlio del cugino di secondo grado)")


# Plan: "Errore atteso (la catena non individua un parente); il tool restituisce
# secondo grado collaterale." No site option corresponds to an up-down inconsistent chain.
def test_catena_incoerente(page):
    pytest.skip("Il sito lavora solo su rapporti nominati: nessuna catena libera da confrontare")


# Limit case: 6th degree, last one relevant under art. 77 c.c.
# Naming differs: the site's "cugino di 3° grado" (option 19, tree n. 1: common
# ancestor = bisnonno, 3 steps up + 3 down) is the tool's "cugino_secondo".
# The site's "cugino di 2° grado" is the 5th degree (see next test).
def test_cugino_secondo_limite_sesto(page):
    tool, _ = _compare(page, "cugino_secondo", "19", 6, "collaterale")
    assert tool["passi"] == ["genitore"] * 3 + ["figlio"] * 3
    assert tool["rilevanza_successoria"] == "Parentela rilevante per successione"


# 5th degree: site "cugino di 2° grado" (option 18, tree n. 1: bisnonno -> prozio ->
# cugino di 2° grado = 3 up + 2 down). The tool has no named relation: chain used.
def test_quinto_grado_catena(page):
    _compare(page, "genitore,genitore,genitore,figlio,figlio", "18", 5, "collaterale")


# Limit case beyond the 6th degree (art. 77 c.c.): the site stops at the 6th degree.
def test_oltre_sesto_grado(page):
    tool = _fn(relazione="genitore,genitore,genitore,genitore,figlio,figlio,figlio,figlio")
    assert tool["grado"] == 8 and tool["rilevanza_successoria"].startswith("Oltre il 6°")
    pytest.skip("Il sito non offre rapporti oltre il 6° grado (massimo: cugino di 3° grado = 6°)")


# Straight line, ascending, 3rd degree (art. 76 c.c.)
def test_bisnonno(page):
    _compare(page, "bisnonno", "3", 3, "retta")


# Straight line, ascending, 4th degree: tool has no named relation, chain used.
def test_trisnonno_catena(page):
    _compare(page, "genitore,genitore,genitore,genitore", "4", 4, "retta")


# Straight line, descending, 3rd degree
def test_pronipote(page):
    _compare(page, "pronipote", "8", 3, "retta")


# Enumerated option: "nipote" in straight line vs "nipote (di zio)" collateral
def test_nipote_figlio(page):
    _compare(page, "nipote_figlio", "6", 2, "retta")


def test_nipote_zio(page):
    _compare(page, "nipote_zio", "7", 3, "collaterale")


def test_zio(page):
    _compare(page, "zio", "14", 3, "collaterale")


def test_prozio(page):
    _compare(page, "prozio", "15", 4, "collaterale")


# Enumerated option: named "padre" is not accepted by the tool (only as a chain step);
# compared through "genitore".
def test_padre_genitore(page):
    _compare(page, "genitore", "0", 1, "retta")


# Affinity (art. 78 c.c.): the site computes it, the tool does not.
def test_suocero_affinita(page):
    tool = _fn(relazione="suocero")
    assert "errore" in tool
    pytest.skip("Affinità (art. 78 c.c.) non gestita dal tool: 'suocero' -> errore")

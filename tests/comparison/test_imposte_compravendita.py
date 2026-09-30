"""Comparison: imposte_compravendita vs avvocatoandreani.it.

Site page: https://www.avvocatoandreani.it/servizi/calcolo-imposte-compravendita-immobiliare.php

Form fields (catalogue):
  TipoImmobile  AP = prima casa, A = abitazione secondaria, A1 = lusso (A/1, A/8, A/9)
  Venditore     1 = privato, 2 = impresa costruttrice entro 5 anni,
                3 = impresa costruttrice oltre 5 anni, 4 = impresa non costruttrice
  PrezzoValore  checkbox (only for residential sales without VAT)
  CalcolaDaRendita checkbox (Valore = rendita non rivalutata instead of valore catastale)
  Valore        rendita / valore catastale / valore pattuito, depending on the checkboxes

The "Calcola" button click does not trigger the POST in headless Chromium (an ad
script swallows it), so the form is submitted natively via
HTMLFormElement.prototype.submit with the hidden Op=Calcola the button would send.

The site offers no option for 'terreno_agricolo' or 'commerciale': those plan
cases are skipped as not comparable.

Norms: DPR 131/1986, Tariffa parte I art. 1 (as replaced by art. 10 D.Lgs. 23/2011:
9%, 2% prima casa, minimum 1.000 euro, ipotecaria/catastale 50 + 50);
art. 1 co. 497 L. 266/2005 (prezzo-valore, rendita x 110 x 1,05 = 115,5 / x 120 x 1,05 = 126);
DPR 633/1972 Tabella A (IVA 4% / 10% / 22%); art. 26 D.Lgs. 104/2013 (imposte fisse 200).
"""

import re
import sys

import pytest

from tests.comparison.conftest import accept_cookies, assert_close, goto, parse_euro

sys.path.insert(0, "/Users/gpuzio/Desktop/CODE/server-infra2.0/mcp-legal-it")
import src.server  # noqa: E402,F401  (registers every tool module)
from src.tools.proprieta_successioni import imposte_compravendita  # noqa: E402

_fn = getattr(imposte_compravendita, "fn", imposte_compravendita)

PAGE = "calcolo-imposte-compravendita-immobiliare.php"
TOL = 0.01


def _fmt(v: float) -> str:
    return f"{v:.2f}".replace(".", ",")


def _site(page, tipo: str, venditore: str, valore: float,
          prezzo_valore: bool = False, da_rendita: bool = True) -> dict:
    goto(page, PAGE, wait_ms=1500)
    accept_cookies(page)
    page.select_option("#TipoImmobile", tipo)
    page.select_option("#Venditore", venditore)
    page.evaluate(
        """([pv, cr]) => {
            const f = document.Compravendita;
            if (!f.PrezzoValore.disabled) { f.PrezzoValore.checked = pv; OnClickPrezzoValore(); }
            if (pv && !f.CalcolaDaRendita.disabled) { f.CalcolaDaRendita.checked = cr; OnClickCalcolaDaRendita(); }
        }""",
        [prezzo_valore, da_rendita],
    )
    page.fill("#Valore", _fmt(valore))
    page.evaluate(
        """() => {
            const f = document.Compravendita;
            const h = document.createElement('input');
            h.type = 'hidden'; h.name = 'Op'; h.value = 'Calcola'; f.appendChild(h);
            HTMLFormElement.prototype.submit.call(f);
        }"""
    )
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(2500)
    body = page.inner_text("body")
    i = body.find("TOTALE IMPOSTE")
    assert i > 0, "result block not found on site"
    block = body[max(0, body.rfind("CALCOLO IMPOSTE di COMPRAVENDITA", 0, i)):i + 60]

    def amt(label):
        m = re.search(rf"{label}[^\n€]*€\s*([\d.,]+)", block)
        return parse_euro(m.group(1)) if m else None

    iva_line = re.search(r"\bIVA\b[^\n]*", block)
    return {
        "block": block,
        "valore_catastale": amt(r"Valore catastale calcolato"),
        "iva": amt(r"\bIVA\b"),
        "iva_testo": iva_line.group(0) if iva_line else "",
        "registro": amt(r"Imposta di Registro"),
        "ipotecaria": amt(r"Imposta Ipotecaria"),
        "catastale": amt(r"Imposta Catastale"),
        "totale": amt(r"TOTALE IMPOSTE"),
    }


def _compare(tool: dict, site: dict, label: str):
    # For VAT sales the site's TOTALE also includes imposta di bollo 230 and
    # diritti di trascrizione ipotecaria 90, which the tool does not compute:
    # the totals are compared as published, the gap is a genuine difference.
    assert "errore" not in tool, tool
    assert_close(tool["imposta_registro"], site["registro"], TOL, f"{label} registro")
    assert_close(tool["imposta_ipotecaria"], site["ipotecaria"], TOL, f"{label} ipotecaria")
    assert_close(tool["imposta_catastale"], site["catastale"], TOL, f"{label} catastale")
    assert_close(tool.get("iva", 0.0), site["iva"] or 0.0, TOL, f"{label} IVA")
    assert_close(tool["totale_imposte"], site["totale"], TOL, f"{label} totale")


# --- plan cases ------------------------------------------------------------

def test_prima_casa_privato_prezzo_valore(page):
    """Plan: base 1.000 x 115,5 = 115.500 (art. 1 co. 497 L. 266/2005); registro 2% = 2.310;
    ipotecaria 50, catastale 50; totale 2.410,00. Norm: Tariffa I art. 1 TUR, nota II-bis."""
    tool = _fn(prezzo=200000, tipo_immobile="abitazione", prima_casa=True,
               da_costruttore=False, rendita_catastale=1000)
    site = _site(page, "AP", "1", 1000, prezzo_valore=True, da_rendita=True)
    assert_close(tool["base_prezzo_valore"], site["valore_catastale"], TOL, "base prezzo-valore")
    _compare(tool, site, "prima casa PV")


def test_seconda_casa_privato_prezzo_valore(page):
    """Plan: base 126.000; registro 9% = 11.340; totale 11.440,00. Norm: Tariffa I art. 1 TUR."""
    tool = _fn(prezzo=200000, tipo_immobile="abitazione", prima_casa=False,
               rendita_catastale=1000)
    site = _site(page, "A", "1", 1000, prezzo_valore=True, da_rendita=True)
    assert_close(tool["base_prezzo_valore"], site["valore_catastale"], TOL, "base prezzo-valore")
    _compare(tool, site, "seconda casa PV")


def test_prima_casa_minimo_registro(page):
    """Plan (limit): 2% di 30.000 = 600 elevato al minimo di 1.000; totale 1.100,00.
    Norm: art. 10 co. 2 D.Lgs. 23/2011 (minimo 1.000)."""
    tool = _fn(prezzo=30000, tipo_immobile="abitazione", prima_casa=True)
    site = _site(page, "AP", "1", 30000, prezzo_valore=False)
    _compare(tool, site, "prima casa minimo")


# Phase 3 (open point, not a tool fix): the site adds imposta di bollo (230) and tasse ipotecarie
# (35 + 55) to sales subject to VAT. The tool leaves them out of totale_imposte; their amounts were
# not confirmed on a primary source (art. 10 co. 3 D.Lgs. 23/2011 only exempts sales taxed with
# proportional registro), so the difference stays documented and unresolved.
def test_prima_casa_da_costruttore(page):
    """Plan: IVA 4% = 10.000; registro, ipotecaria e catastale 200 ciascuna; totale 10.600,00.
    Norm: DPR 633/1972 Tab. A parte II n. 21; art. 26 D.Lgs. 104/2013."""
    tool = _fn(prezzo=250000, tipo_immobile="abitazione", prima_casa=True, da_costruttore=True)
    site = _site(page, "AP", "2", 250000)
    _compare(tool, site, "prima casa IVA 4%")


def test_lusso_privato_dichiarato_prima_casa(page):
    """Plan (limit, enumerated option): agevolazione esclusa per A/1, A/8, A/9 (nota II-bis,
    art. 1 Tariffa I TUR): registro 9% = 72.000, totale 72.100,00; il tool applica il 2%
    (16.100,00). Expected deviation."""
    tool = _fn(prezzo=800000, tipo_immobile="lusso", prima_casa=True)
    site = _site(page, "A1", "1", 800000, prezzo_valore=False)
    _compare(tool, site, "lusso prima casa")


def test_strumentale_da_impresa(page):
    """Plan: IVA 22% (se imponibile), registro 200, ipotecaria 3% = 9.000, catastale 1% = 3.000
    (art. 35 co. 10-ter DL 223/2006); il tool applica IVA 10% e imposte fisse (30.600,00)."""
    pytest.skip("Il sito non offre immobili strumentali/commerciali (solo AP, A, A1)")


def test_terreno_agricolo(page):
    """Plan: 15% di 5.000 = 750 elevato al minimo di 1.000; 50 + 50; totale 1.100,00."""
    pytest.skip("Il sito non offre terreni agricoli (solo AP, A, A1)")


# --- additional limit cases ------------------------------------------------

def test_lusso_privato_non_prima_casa(page):
    """Limit (enumerated option): lusso da privato senza agevolazione -> registro 9% = 72.000
    + 50 + 50 = 72.100,00. Norm: Tariffa I art. 1 TUR."""
    tool = _fn(prezzo=800000, tipo_immobile="lusso", prima_casa=False)
    site = _site(page, "A1", "1", 800000, prezzo_valore=False)
    _compare(tool, site, "lusso 9%")


def test_seconda_casa_soglia_minimo(page):
    """Limit: 9% di 11.111 = 999,99 -> minimo 1.000; totale 1.100,00.
    Norm: art. 10 co. 2 D.Lgs. 23/2011."""
    tool = _fn(prezzo=11111, tipo_immobile="abitazione", prima_casa=False)
    site = _site(page, "A", "1", 11111, prezzo_valore=False)
    _compare(tool, site, "seconda casa soglia")


def test_prima_casa_esattamente_al_minimo(page):
    """Limit: 2% di 50.000 = 1.000 esatti (= minimo); totale 1.100,00."""
    tool = _fn(prezzo=50000, tipo_immobile="abitazione", prima_casa=True)
    site = _site(page, "AP", "1", 50000, prezzo_valore=False)
    _compare(tool, site, "prima casa = minimo")


# Phase 3 verdict: convention. The site rounds the revalued rendita (987,65 x 1,05 = 1.037,03) before
# multiplying by 110; the tool multiplies 987,65 x 115,5 in one step (114.073,57 vs 114.073,30). The
# registro (2.281,47) is identical: art. 52 DPR 131/1986 does not prescribe an intermediate rounding.
def test_prima_casa_rendita_decimale(page):
    """Rounding: rendita 987,65 x 115,5 = 114.073,575 -> base 114.073,58; registro 2% = 2.281,47
    (2.281,4715); totale 2.381,47. Norm: art. 1 co. 497 L. 266/2005."""
    tool = _fn(prezzo=150000, tipo_immobile="abitazione", prima_casa=True, rendita_catastale=987.65)
    site = _site(page, "AP", "1", 987.65, prezzo_valore=True, da_rendita=True)
    # Taxes first, then the base: the site rounds the revalued rendita (987,65 x 1,05 =
    # 1.037,03) before multiplying by 110, the tool multiplies by 115,5 in one step.
    _compare(tool, site, "rendita decimale")
    assert_close(tool["base_prezzo_valore"], site["valore_catastale"], TOL, "base prezzo-valore")


# Phase 3 (open point, not a tool fix): the site adds imposta di bollo (230) and tasse ipotecarie
# (35 + 55) to sales subject to VAT. The tool leaves them out of totale_imposte; their amounts were
# not confirmed on a primary source (art. 10 co. 3 D.Lgs. 23/2011 only exempts sales taxed with
# proportional registro), so the difference stays documented and unresolved.
def test_seconda_casa_da_costruttore(page):
    """Enumerated option: IVA 10% di 300.000 = 30.000 + 200 x 3 = 30.600,00.
    Norm: DPR 633/1972 Tab. A parte III n. 127-undecies; art. 26 D.Lgs. 104/2013."""
    tool = _fn(prezzo=300000, tipo_immobile="abitazione", prima_casa=False, da_costruttore=True)
    site = _site(page, "A", "2", 300000)
    _compare(tool, site, "seconda casa IVA 10%")


# Phase 3 (open point, not a tool fix): the site adds imposta di bollo (230) and tasse ipotecarie
# (35 + 55) to sales subject to VAT. The tool leaves them out of totale_imposte; their amounts were
# not confirmed on a primary source (art. 10 co. 3 D.Lgs. 23/2011 only exempts sales taxed with
# proportional registro), so the difference stays documented and unresolved.
def test_lusso_da_costruttore(page):
    """Enumerated option: IVA 22% di 800.000 = 176.000 + 600 = 176.600,00.
    Norm: DPR 633/1972 (aliquota ordinaria, art. 16)."""
    tool = _fn(prezzo=800000, tipo_immobile="lusso", da_costruttore=True)
    site = _site(page, "A1", "2", 800000)
    _compare(tool, site, "lusso IVA 22%")

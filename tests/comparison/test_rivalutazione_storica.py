"""Benchmark rivalutazione_storica vs avvocatoandreani.it (rivalutazione-monetaria-storica.php).

Tool: coefficient = mean(FOI months of anno_arrivo) / mean(FOI months of anno_partenza),
series from 1990 (src/data/indici_foi.json, base 2015=100 raccordata; from 2026 base
2025=100 x 1,214).
Site: ISTAT historical index of consumer prices for blue- and white-collar households (FOI)
since 1861, annual values; capital in euro (TipoValuta=1). For the current year the
site chains the last annual index (2025) with the monthly FOI December 2025 -> last month.

Tolerance: 0,01 EUR on the revalued amount (brief). No wider tolerance is used.
"""

# Phase 3 verdict (2026-09-29): the pre-2020 FOI series was wrong and was rebuilt from the ISTAT
# monthly series (1990-1995 removed: no primary source, see indici_foi.json _note); the 1990 and
# 1985-1995 cases are now out of coverage. The remaining gaps are a CONVENTION: the tool averages
# the 12 published monthly indices (1 decimal), the page uses the ISTAT annual historical index
# and rounds the coefficient to 3-4 decimals (2015-2023: 1.18738 vs 1.187; 2010-2014: 1.07281 vs
# 1.072). For the current year the tool uses the partial mean (with a warning), the page chains
# the last published month. The cases stay failing as documented differences.


import os
import re

os.environ.setdefault("LEGAL_TODAY", "2026-09-25")

import pytest

from tests.comparison.conftest import accept_cookies, assert_close, goto, parse_euro

PAGE = "rivalutazione-monetaria-storica.php"


def _tool(**kwargs):
    import src.server  # noqa: F401  (registers modules, avoids circular imports)
    from src.tools.rivalutazioni_istat import rivalutazione_storica

    fn = getattr(rivalutazione_storica, "fn", rivalutazione_storica)
    return fn(**kwargs)


def _site(page, importo, anno_da, anno_a):
    """Drive the site in euro; return (final revalued capital, list of coefficients, text)."""
    goto(page, PAGE)
    accept_cookies(page)
    # The euro radio (value=1) does not toggle via click (overlay): set it directly.
    page.eval_on_selector("input[name='TipoValuta'][value='1']", "e => { e.checked = true }")
    page.fill("input[name='Capitale']", str(importo))
    page.fill("input[name='AnnoIniziale']", str(anno_da))
    page.fill("input[name='AnnoFinale']", str(anno_a))
    page.click("#btn-calc", force=True)
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(2000)
    body = page.inner_text("body")
    start = body.find("Rivalutazione storica dal")
    assert start >= 0, "site did not return a result block"
    text = body[start:start + 1500]
    amounts = re.findall(r"Capitale rivalutato[^:]*:\D*?([\d\.]+,\d+)", text)
    coeffs = re.findall(r"Coefficiente di rivalutazione:\s*([\d,]+)", text)
    assert amounts, f"no revalued capital found in: {text[:400]}"
    return parse_euro(amounts[-1]), coeffs, text


def _compare(page, importo, anno_da, anno_a):
    r = _tool(importo=importo, anno_partenza=anno_da, anno_arrivo=anno_a)
    assert "errore" not in r, r
    site_val, coeffs, _ = _site(page, importo, anno_da, anno_a)
    assert_close(
        r["importo_rivalutato"], site_val, tolerance=0.01,
        label=(f"{importo} {anno_da}->{anno_a}: tool coeff {r['coefficiente_rivalutazione']} "
               f"vs site coeff {coeffs}"),
    )


def test_2015_2023_anni_completi(page):
    """Piano: 10.000 EUR 2015->2023. Atteso: tool 1,18662 (11.866,20); con medie annue
    arrotondate 118,7/100,0 = 1,187 (11.870,00). Norma: indici FOI ISTAT (art. 150 disp.
    att. c.p.c. / art. 429 c.p.c. rinviano a FOI); coefficienti ISTAT 'Il valore della moneta'."""
    _compare(page, 10000, 2015, 2023)


def test_2020_2026_anno_parziale(page):
    """Piano (limite: anno in corso): 10.000 EUR 2020->2026. Atteso: tool media 2026 parziale
    su 8 mesi con avvertenza INDICATIVO (12.125,81). Il sito invece concatena l'indice annuo
    2025 con il FOI mensile dic 2025 -> ago 2026 (raccordo 1,214)."""
    r = _tool(importo=10000, anno_partenza=2020, anno_arrivo=2026)
    assert r.get("avvertenza") and "parziale" in r["avvertenza"]
    _compare(page, 10000, 2020, 2026)


def test_1985_fuori_serie(page):
    """Piano (limite: fuori serie): 1.000 EUR 1985->2025. Atteso: errore del tool (serie dal
    1990); il sito copre dal 1861 -> scostamento di copertura, non di calcolo."""
    r = _tool(importo=1000, anno_partenza=1985, anno_arrivo=2025)
    assert "errore" in r
    site_val, coeffs, _ = _site(page, 1000, 1985, 2025)
    pytest.skip(f"non confrontabile: tool senza indici prima del 1990; sito {site_val} "
                f"(coeff {coeffs})")


def test_1990_2025_primo_anno_serie(page):
    """Limite: primo anno della serie del tool (1990) -> ultimo anno completo (2025).
    Atteso: coefficiente ISTAT FOI 1990->2025."""
    _compare(page, 10000, 1990, 2025)


def test_2024_2025_ultimo_anno_completo(page):
    """Limite: anni consecutivi, 2025 = ultimo indice annuale disponibile sul sito.
    Atteso: variazione media annua FOI 2025 su 2024."""
    _compare(page, 10000, 2024, 2025)


def test_2001_2002_passaggio_euro(page):
    """Limite: a cavallo del passaggio lira/euro (1.1.2002). Atteso: variazione media annua
    FOI 2002 su 2001 (ISTAT: +2,4%)."""
    _compare(page, 10000, 2001, 2002)


def test_2010_2014_anni_serie_sospetta(page):
    """Limite: attraversa 2011-2013 (anni segnalati dal piano come affetti da errore della
    serie). Atteso: FOI base 2010: 2014 = 107,2 -> coefficiente 1,072."""
    _compare(page, 10000, 2010, 2014)


def test_1995_2020_cambio_base(page):
    """Attraversa piu' cambi di base (1995, 2010, 2015). Atteso: coefficiente ISTAT
    FOI 1995->2020."""
    _compare(page, 10000, 1995, 2020)

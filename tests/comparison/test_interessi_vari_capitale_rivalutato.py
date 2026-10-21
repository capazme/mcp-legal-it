"""Comparison: interessi_vari_capitale_rivalutato vs avvocatoandreani.it.

Site page: /servizi/calcolo-interessi-vari-capitale-rivalutato.php
("Calcolo interessi a tasso fisso, legali e moratori sul capitale rivalutato
annualmente").

Site settings used to mirror the tool:
- DiesAQuo unchecked (the tool excludes the starting day);
- Rivalutazione = Si, "Mese e anno iniziali", 100%, deflation NOT ignored;
- no maggiorazione, no anatocismo (the tool never capitalises);
- TipoCalcolo = 2 ("Anno di 365 o 366 giorni") - the tool divides by the
  actual length of each calendar year (_days_in_year).

Known methodological gap (recorded, not adapted): the site splits the period
at each anniversary of the start date and uses, for each annual slice, the
capital revalued to the END of that slice with a coefficient rounded to three
decimals; the tool splits by calendar year and revalues each year to December
(or to the final month) with the unrounded FOI ratio.

Norms: art. 1224 c.c. and art. 1284 c.c. (tasso legale by DM MEF per year);
Cass. SU 1712/1995 (interessi sul capitale rivalutato anno per anno);
indici FOI ISTAT senza tabacchi (art. 150 disp. att. c.p.c. reference series).

Tolerance: 0,01 EUR on every amount (brief). No widening.
"""

import os

os.environ.setdefault("LEGAL_TODAY", "2026-09-25")

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import src.server  # noqa: E402,F401  (registers all tool modules)
from src.tools.rivalutazioni_istat import (  # noqa: E402
    interessi_vari_capitale_rivalutato as _tool,
    rivalutazione_monetaria as _riv,
)

from tests.comparison.conftest import extract_amount, goto  # noqa: E402

TOOL = getattr(_tool, "fn", _tool)
RIV = getattr(_riv, "fn", _riv)
PAGE = "calcolo-interessi-vari-capitale-rivalutato.php"
TOL = 0.01


def _radio(page, name, value):
    """Select a radio via DOM (styled radios reject Playwright's check())."""
    page.evaluate(
        "([n, v]) => { const e = document.querySelector(`input[name='${n}'][value='${v}']`);"
        " e.checked = true; e.dispatchEvent(new Event('change', {bubbles: true})); }",
        [name, value],
    )


def _site(page, capitale, data_inizio, data_fine, tipo="1", tasso=None):
    """Drive the site form and return the parsed summary amounts."""
    goto(page, PAGE)
    page.fill("input[name='Capitale']", str(capitale).replace(".", ","))
    y, m, d = data_inizio.split("-")
    page.select_option("select[name='GiornoInizio']", d)
    page.select_option("select[name='MeseInizio']", m)
    page.select_option("select[name='AnnoInizio']", y)
    y, m, d = data_fine.split("-")
    page.select_option("select[name='GiornoFine']", d)
    page.select_option("select[name='MeseFine']", m)
    page.select_option("select[name='AnnoFine']", y)
    cb = page.locator("input[name='DiesAQuo']")
    if cb.is_checked():
        cb.click(force=True)
    _radio(page, "DoRival", "1")
    _radio(page, "TipoRival", "1")
    # PctRival keeps its default 100 (maxlength 2: filling "100" posts "10")
    _radio(page, "NoDeflaz", "0")
    page.select_option("select[name='TipoInteressi']", tipo)
    if tasso is not None:
        page.fill("input[name='Tasso']", str(tasso).replace(".", ","))
    _radio(page, "Anatocismo", "0")
    _radio(page, "TipoCalcolo", "2")
    # A late-loading overlay swallows the forced click on #btn-calc after
    # goto()'s wait: submit the form through the DOM, keeping the Op=Calcola
    # submitter in the POST body.
    with page.expect_navigation():
        page.evaluate(
            "() => document.getElementById('RivalutazioneTassiVari')"
            ".requestSubmit(document.getElementById('btn-calc'))"
        )
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(2500)
    text = page.inner_text("body")
    assert "Capitale Rivalutato + Interessi" in text, "site returned no result"

    def amount(label):
        value = extract_amount(text, label)
        assert value is not None, f"label not found on site: {label}"
        return value

    interessi_label = "Totale Interessi Legali:" if tipo == "1" else "Totale Interessi a Tasso Fisso:"
    return {
        "capitale_rivalutato": amount("Capitale Rivalutato:"),
        "totale_interessi": amount(interessi_label),
        "totale_dovuto": amount("Capitale Rivalutato + Interessi:"),
    }


def _compare(tool_res, site_res):
    assert "errore" not in tool_res, tool_res
    diffs = []
    for key in ("capitale_rivalutato", "totale_interessi", "totale_dovuto"):
        t, s = tool_res[key], site_res[key]
        if abs(t - s) > TOL:
            diffs.append(f"{key}: tool={t:.2f} site={s:.2f} diff={t - s:+.2f}")
    assert not diffs, "; ".join(diffs)


def test_legale_2019_2023_coerenza_rivalutazione_monetaria(page):
    """Plan case 1 - tasso legale, 10.000 EUR, 10/03/2019-10/03/2023.

    Atteso (piano): identico a rivalutazione_monetaria con interessi:
    interessi 324,57, totale 11.938,74; sul sito opzione interessi legali.
    Norma: art. 1284 c.c. (tassi 2019 0,8%, 2020 0,05%, 2021 0,01%,
    2022 1,25%, 2023 5%); Cass. SU 1712/1995.
    """
    args = dict(capitale=10000, data_inizio="2019-03-10", data_fine="2023-03-10")
    res = TOOL(**args, tasso_personalizzato=None)
    riv = RIV(**args, con_interessi_legali=True)
    # Internal coherence first (tool vs sibling tool), then tool vs site.
    assert abs(res["totale_interessi"] - riv["totale_interessi_legali"]) <= TOL
    assert abs(res["totale_dovuto"] - riv["totale_dovuto"]) <= TOL
    site = _site(page, **args, tipo="1")
    _compare(res, site)


def test_tasso_fisso_3_5_2019_2023(page):
    """Plan case 2 - tasso fisso 3,5%, 10.000 EUR, 10/03/2019-10/03/2023.

    Atteso (piano): tool interessi 1.485,01, totale 13.099,18; sito da
    leggere con tasso fisso 3,5% senza capitalizzazione.
    Norma: art. 1284 co. 3 c.c. (tasso convenzionale).
    """
    res = TOOL(capitale=10000, data_inizio="2019-03-10", data_fine="2023-03-10",
               tasso_personalizzato=3.5)
    site = _site(page, 10000, "2019-03-10", "2023-03-10", tipo="3", tasso=3.5)
    _compare(res, site)


def test_limite_anno_intero_31_12_giorno_perso(page):
    """Plan case 3 (limit: year boundary) - 5% fisso, 31/12/2024-31/12/2025.

    Atteso (piano): 365 giorni nel 2025 (dies a quo escluso):
    10.108,15 x 5% = 505,41; il tool conta 364 giorni e restituisce 504,02.
    Norma: art. 1284 c.c.; computo ex art. 2963 c.c. (dies a quo non computatur).
    """
    res = TOOL(capitale=10000, data_inizio="2024-12-31", data_fine="2025-12-31",
               tasso_personalizzato=5)
    site = _site(page, 10000, "2024-12-31", "2025-12-31", tipo="3", tasso=5)
    _compare(res, site)


def test_limite_bisestile_entro_anno(page):
    """Limit case: leap year, single calendar year, 4% fisso,
    01/02/2024-30/11/2024 (divisor 366 on both sides).

    Atteso: stessi giorni (303) e stesso divisore; eventuale differenza solo
    dal coefficiente FOI arrotondato a 3 decimali dal sito.
    Norma: art. 1284 c.c.; indici FOI ISTAT feb-nov 2024.
    """
    res = TOOL(capitale=10000, data_inizio="2024-02-01", data_fine="2024-11-30",
               tasso_personalizzato=4)
    site = _site(page, 10000, "2024-02-01", "2024-11-30", tipo="3", tasso=4)
    _compare(res, site)


def test_limite_ribasamento_2026_tasso_legale(page):
    """Limit case: period straddling the FOI base change (2025=100 from
    Jan 2026, raccordo 1,214) and two legal-rate years (2025 2%, 2026 1,6%),
    10.000 EUR, 10/06/2025-10/06/2026.

    Atteso: coefficiente FOI giu 2025 -> giu 2026 sulla serie raccordata;
    interessi legali 2% (2025) e 1,6% (2026).
    Norma: art. 1284 c.c.; DM MEF 10/12/2025; comunicato ISTAT GU 144/2026.
    """
    res = TOOL(capitale=10000, data_inizio="2025-06-10", data_fine="2026-06-10",
               tasso_personalizzato=None)
    site = _site(page, 10000, "2025-06-10", "2026-06-10", tipo="1")
    _compare(res, site)


def test_non_confrontabile_moratori():
    """Site option 'Moratori' (D.Lgs. 231/2002) and anatocismo have no
    counterpart in the tool (only tasso fisso or legale, no capitalisation)."""
    pytest.skip("il tool non offre interessi moratori ne' capitalizzazione: opzioni del sito non coperte")


# Phase 3 verdict (2026-09-29). Tool fixed: FOI series (ISTAT original bases) and day count of the last
# segment (art. 2963 c.c., dies a quo excluded: 365 days for 31/12/2024-31/12/2025). Residual differences
# are conventions: the site rounds the coefficient to 3 decimals (capital always a multiple of 10 euro on
# 10,000), works by anniversary years and divides the 2025 segment by 366 (a site error: the year is 365 days).

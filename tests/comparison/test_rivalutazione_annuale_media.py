"""Comparison: rivalutazione_annuale_media vs avvocatoandreani.it.

Page: https://www.avvocatoandreani.it/servizi/calcolo-rivalutazione-annuale-media.php
Form: Capitale (text), AnnoInizio / AnnoFine (select, 1947..last complete year),
submit #btn-calc. Result: "SVILUPPO del CALCOLO" table (one row per year pair,
variation rounded to 0.1%) + "Capitale rivalutato: € X".

Norm/source: ISTAT FOI index (senza tabacchi), annual averages; base 2015=100
raccordata, from 2026 base 2025=100 with official coefficient 1,214.

Known convention difference: the tool divides the two annual averages directly;
the site chains the official ISTAT annual average variations, each rounded to
one decimal (e.g. +8,1%), capitalising year by year. Tolerance stays 0,01 EUR as
per brief: any difference due to that rounding is a genuine divergence to be
judged in phase 2, not absorbed here.
"""

import os
import re

os.environ.setdefault("LEGAL_TODAY", "2026-09-25")

import pytest

from tests.comparison.conftest import assert_close, parse_euro

import src.server  # noqa: F401  (registers modules, avoids circular imports)
from src.tools.rivalutazioni_istat import rivalutazione_annuale_media as _tool

_fn = getattr(_tool, "fn", _tool)

PAGE = "https://www.avvocatoandreani.it/servizi/calcolo-rivalutazione-annuale-media.php"


def _open(page):
    """Open the page removing the Quantcast overlay only.

    conftest.goto() is not used: the forced click it pairs with (submit_form)
    does not submit this form once the page has settled; see _site().
    """
    page.goto(PAGE, timeout=60000, wait_until="domcontentloaded")
    page.evaluate(
        'document.querySelectorAll("#qc-cmp2-container, .qc-cmp2-container").forEach(e => e.remove())'
    )
    page.wait_for_timeout(1000)


def _site(page, capitale: float, anno_inizio: int, anno_fine: int) -> tuple[float | None, str]:
    """Drive the site; return (capitale rivalutato or None, body text)."""
    _open(page)
    page.fill("#Capitale", str(int(capitale)) if capitale == int(capitale) else f"{capitale:.2f}".replace(".", ","))
    page.select_option("#AnnoInizio", str(anno_inizio))
    page.select_option("#AnnoFine", str(anno_fine))
    # click(force=True) on #btn-calc is unreliable here: once ads load the button
    # sits outside the viewport and the forced click lands nowhere (no POST).
    # requestSubmit(submitter) sends exactly the form fields incl. Op=Calcola.
    with page.expect_navigation(timeout=30000):
        page.evaluate(
            'document.getElementById("CalcoloRivalutazioneMedia")'
            '.requestSubmit(document.getElementById("btn-calc"))'
        )
    page.wait_for_timeout(2000)
    body = page.inner_text("body")
    m = re.search(r"Capitale rivalutato:\s*€\s*([\-\d\.,]+)", body)
    return (parse_euro(m.group(1)) if m else None), body


def _site_years(page) -> list[str]:
    _open(page)
    return [o.get_attribute("value") for o in page.query_selector_all("#AnnoFine option")]


def test_anni_diversi_mesi_ignorati(page):
    """Plan case 1: 10.000 from 2015-06-15 to 2023-03-10 (only years count).
    Atteso (piano): tool 1,18662 -> 11.866,20; site chains annual average variations.
    Fonte: medie annue FOI ISTAT 2015 e 2023."""
    r = _fn(importo=10000, data_inizio="2015-06-15", data_fine="2023-03-10")
    site, _ = _site(page, 10000, 2015, 2023)
    assert site is not None, "site returned no result"
    assert_close(r["importo_rivalutato"], site, 0.01, "capitale rivalutato 2015->2023")


def test_stesso_anno(page):
    """Plan case 2 (limit): same year 2024 -> coefficient 1, 10.000,00.
    Fonte: rapporto media 2024 / media 2024 = 1."""
    r = _fn(importo=10000, data_inizio="2024-01-10", data_fine="2024-11-30")
    assert r["importo_rivalutato"] == 10000.0
    site, body = _site(page, 10000, 2024, 2024)
    if site is None:
        pytest.skip("site does not compute a same-year interval (no 'Capitale rivalutato')")
    assert_close(r["importo_rivalutato"], site, 0.01, "stesso anno 2024")


def test_anno_finale_parziale_2026(page):
    """Plan case 3 (limit): 2025 -> 2026 with 2026 partial (8 months).
    Atteso (piano): tool 10.222,08 INDICATIVO. The site states the average requires
    a complete year and offers years only up to the last complete one (2025)."""
    r = _fn(importo=10000, data_inizio="2025-01-01", data_fine="2026-08-31")
    assert "parziale" in (r.get("avvertenza") or "")
    years = _site_years(page)
    if "2026" not in years:
        pytest.skip("site offers AnnoFine only up to the last complete year (2025): 2026 not selectable")
    site, _ = _site(page, 10000, 2025, 2026)
    assert site is not None
    assert_close(r["importo_rivalutato"], site, 0.01, "2025->2026 parziale")


def test_un_solo_anno_2024_2025(page):
    """Limit: single step, last complete year of the site's table (2025).
    Tool: media 2025 / media 2024. Site: one row, ISTAT variation rounded to 0,1%."""
    r = _fn(importo=10000, data_inizio="2024-01-01", data_fine="2025-01-01")
    site, _ = _site(page, 10000, 2024, 2025)
    assert site is not None
    assert_close(r["importo_rivalutato"], site, 0.01, "capitale rivalutato 2024->2025")


def test_un_solo_anno_2021_2022(page):
    """Limit: single high-inflation step (2021 -> 2022, ISTAT +8,1%)."""
    r = _fn(importo=10000, data_inizio="2021-01-01", data_fine="2022-01-01")
    site, _ = _site(page, 10000, 2021, 2022)
    assert site is not None
    assert_close(r["importo_rivalutato"], site, 0.01, "capitale rivalutato 2021->2022")


def test_2011_2013(page):
    """Plan note: years 2011-2013 to be checked (series pre base 2015 raccordata)."""
    r = _fn(importo=10000, data_inizio="2011-01-01", data_fine="2013-01-01")
    site, _ = _site(page, 10000, 2011, 2013)
    assert site is not None
    assert_close(r["importo_rivalutato"], site, 0.01, "capitale rivalutato 2011->2013")


def test_intervallo_20_anni_2005_2025(page):
    """Limit: site maximum interval of 20 years (2005 -> 2025)."""
    r = _fn(importo=10000, data_inizio="2005-01-01", data_fine="2025-01-01")
    site, _ = _site(page, 10000, 2005, 2025)
    assert site is not None, "site refused a 20-year interval"
    assert_close(r["importo_rivalutato"], site, 0.01, "capitale rivalutato 2005->2025")


def test_intervallo_oltre_20_anni_1990_2025(page):
    """Limit: 35-year interval; the site declares a 20-year cap."""
    r = _fn(importo=10000, data_inizio="1990-01-01", data_fine="2025-01-01")
    assert "errore" not in r
    site, _ = _site(page, 10000, 1990, 2025)
    if site is None:
        pytest.skip("site refuses intervals over 20 years (declared limit)")
    assert_close(r["importo_rivalutato"], site, 0.01, "capitale rivalutato 1990->2025")


# Phase 3 verdict (2026-09-29). The FOI series was rebuilt from the ISTAT original bases. Residual differences
# are a convention: the site chains the official annual variations rounded to 0.1%, year by year, the tool
# divides the unrounded annual means once (ISTAT rounds the means to 1 decimal; gap up to about 0.1%).

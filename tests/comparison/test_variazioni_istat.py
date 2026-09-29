"""Comparison: variazioni_istat vs avvocatoandreani.it.

The plan's page (variazioni_indici_istat_rivalutazione.php) only publishes
MONTHLY variations (same month of the previous year / two years / previous
month / final month) and monthly coefficients: it has no annual-average
variation. The site's annual-average variation ("inflazione media", ratio of the
arithmetic mean of the 12 FOI indices of a year to the mean of the previous
year) is published by calcolo-rivalutazione-annuale-media.php, in the
"SVILUPPO del CALCOLO" table (column "Inflazione Media"). That is the page used
here.

Norm / source: ISTAT FOI index net of tobacco (art. 81 L. 392/1978), average
annual variation as published by ISTAT (computed on means rounded to one
decimal, result rounded to one decimal).

Tolerance: the site prints the rate with ONE decimal (e.g. "+8,1%"), so the
tool value (two decimals) can only be matched within half a unit of the site's
last digit: |tool - site| <= 0.05 percentage points. The brief's four-decimal
tolerance cannot apply to a one-decimal source.
"""

import os
import re
import sys

import pytest

os.environ.setdefault("LEGAL_TODAY", "2026-09-25")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import src.server  # noqa: E402,F401  (registers every tool module)
from src.tools.rivalutazioni_istat import variazioni_istat  # noqa: E402

_fn = getattr(variazioni_istat, "fn", variazioni_istat)
URL = "https://www.avvocatoandreani.it/servizi/calcolo-rivalutazione-annuale-media.php"
TOL_PP = 0.05  # half unit of the site's single decimal (see module docstring)


def _site_rates(page, anno_inizio: int, anno_fine: int) -> dict[int, float]:
    """Return {year: average annual variation %} from the site's table."""
    # conftest.goto() is NOT used here: its "#accept-btn" click leaves this
    # page in a state where the POST never lands (verified: no result table).
    # Navigate directly and drop the Quantcast overlay only.
    page.goto(URL, timeout=60000, wait_until="domcontentloaded")
    page.evaluate(
        'document.querySelectorAll("#qc-cmp2-container, .qc-cmp2-container")'
        ".forEach(el => el.remove())"
    )
    page.fill("#Capitale", "10000")
    page.select_option("#AnnoInizio", str(anno_inizio))
    page.select_option("#AnnoFine", str(anno_fine))
    page.click("#btn-calc", force=True)
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(2500)
    text = page.inner_text("body")
    rates = {}
    for m in re.finditer(r"(\d{4})\s*-\s*(\d{4})\s+([+-]?\d+(?:,\d+)?)%", text):
        rates[int(m.group(2))] = float(m.group(3).replace(",", "."))
    assert rates, "site returned no 'Inflazione Media' rows"
    return rates


def _tool_rates(anno_inizio: int, anno_fine: int) -> dict[int, float | None]:
    r = _fn(anno_inizio=anno_inizio, anno_fine=anno_fine)
    assert "errore" not in r, r
    return {row["anno"]: row["variazione_pct"] for row in r["tabella"]}


def _compare(tool: dict, site: dict, years):
    diffs = []
    for y in years:
        t, s = tool.get(y), site.get(y)
        if t is None or abs(t - s) > TOL_PP:
            diffs.append(f"{y}: tool={t} site={s}")
    assert not diffs, "annual average variation mismatch: " + "; ".join(diffs)


def test_2021_2024_rounding_convention(page):
    """Plan case 1. Expected (ISTAT FOI senza tabacchi): 2022 +8,1%, 2023 +5,4%,
    2024 +0,8% (means rounded to 104,2; 112,6; 118,7; 119,7). Tool: 8,01; 5,43; 0,88.
    """
    tool = _tool_rates(2021, 2024)
    site = _site_rates(page, 2021, 2024)
    _compare(tool, site, [2022, 2023, 2024])


def test_2011_2015_suspect_stretch(page):
    """Plan case 2. Expected official: 2012 +3,0%, 2013 +1,1%, 2014 +0,2%,
    2015 -0,1%. Tool: 2,17; 0,24; -0,55; -0,42 (suspected FOI series error).
    """
    tool = _tool_rates(2011, 2015)
    page.wait_for_timeout(1500)
    site = _site_rates(page, 2011, 2015)
    _compare(tool, site, [2012, 2013, 2014, 2015])


def test_2008_2011_across_base_change(page):
    """Edge case: straddles the base change 1995=100 -> 2010=100 (Jan 2011)
    and the 2009 deflation-near year. Official FOI: 2009 +0,7%, 2010 +1,6%, 2011 +2,7%.
    """
    tool = _tool_rates(2008, 2011)
    page.wait_for_timeout(1500)
    site = _site_rates(page, 2008, 2011)
    _compare(tool, site, [2009, 2010, 2011])


def test_1989_1992_start_out_of_series(page):
    """Plan case 4 (edge). Tool series starts in 1990: the 1990 variation must be
    unavailable (null) but the tool shows 0,0; cumulated variation null.
    The site covers 1947+ and gives 1990 +6,1%, so 1990 is compared too
    (tool 0,0 is an artefact, not a rate). 1991 and 1992 are fully comparable.
    """
    tool = _tool_rates(1989, 1992)
    page.wait_for_timeout(1500)
    site = _site_rates(page, 1989, 1992)
    _compare(tool, site, [1990, 1991, 1992])


def test_2024_2026_last_partial_year(page):
    """Plan case 3 (edge, table vintage). 2026 has only 8 months (Jan-Aug):
    tool flags mesi_disponibili=8 and variazione_cumulata_parziale; the site
    only offers complete years (last: 2025). 2025 (last complete year) is
    compared; 2026 is not comparable.
    """
    r = _fn(anno_inizio=2024, anno_fine=2026)
    row26 = [x for x in r["tabella"] if x["anno"] == 2026][0]
    assert row26.get("mesi_disponibili") == 8
    assert r.get("variazione_cumulata_parziale") is True
    tool = {row["anno"]: row["variazione_pct"] for row in r["tabella"]}
    page.wait_for_timeout(1500)
    site = _site_rates(page, 2024, 2025)
    assert 2026 not in site
    _compare(tool, site, [2025])

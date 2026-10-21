"""Comparison: inflazione_titoli_stato vs avvocatoandreani.it.

The site has no real-return calculator. The primary page
(grafico-andamento-inflazione-titoli-di-stato.php) publishes the year-on-year
FOI inflation per month (one decimal) for the last three years; the secondary
page (calcolo-inflazione.php) computes the FOI inflation between two months.
Only the inflation component of the tool is therefore comparable: nominal
montante and Fisher real return are checked by hand (not against the site).

Tolerance: the site publishes inflation with ONE decimal (it says so itself:
"si utilizza un solo decimale come nel calcolo della rivalutazione"), so the
tool's inflazione_totale_pct is rounded to one decimal before comparison and
must then coincide exactly (abs diff < 0.005). This is wider than the brief's
four decimals only because the site gives no more precision.

Source: ISTAT FOI (senza tabacchi) index, base 2015=100 chained; from 2026
base 2025=100 converted with the official coefficient 1,214.
"""

import os
import re

os.environ.setdefault("LEGAL_TODAY", "2026-09-25")

import pytest

from tests.comparison.conftest import accept_cookies

import src.server  # noqa: F401  (registers every tool module)
from src.tools.rivalutazioni_istat import inflazione_titoli_stato as _tool

_fn = getattr(_tool, "fn", _tool)

BASE = "https://www.avvocatoandreani.it/servizi/"
GRAFICO = BASE + "grafico-andamento-inflazione-titoli-di-stato.php"
CALCOLO = BASE + "calcolo-inflazione.php"

_MESI = ["Gen", "Feb", "Mar", "Apr", "Mag", "Giu", "Lug", "Ago", "Set", "Ott", "Nov", "Dic"]


def _site_calcolo_inflazione(page, m_da, a_da, m_a, a_a, capitale="10000,00"):
    """Drive calcolo-inflazione.php; return (inflation %, full result text)."""
    page.goto(CALCOLO, timeout=60000, wait_until="domcontentloaded")
    accept_cookies(page)
    page.wait_for_timeout(1000)
    page.fill("#Capitale", capitale)
    page.select_option("#MeseInizio", f"{m_da:02d}")
    page.select_option("#AnnoInizio", str(a_da))
    page.select_option("#MeseFine", f"{m_a:02d}")
    page.select_option("#AnnoFine", str(a_a))
    # A plain click on #btn-calc does not submit in headless mode (overlay);
    # requestSubmit with the submitter keeps the Op=Calcola field.
    with page.expect_navigation(timeout=60000):
        page.evaluate(
            'document.getElementById("CalcoloInflazione")'
            '.requestSubmit(document.getElementById("btn-calc"))'
        )
    page.wait_for_timeout(2000)
    body = page.inner_text("body")
    m = re.search(r"Inflazione calcolata con indici Istat:\s*(-?[\d.,]+)\s*%", body)
    if not m:
        return None, body
    return float(m.group(1).replace(".", "").replace(",", ".")), body


def _site_grafico_yoy(page, mese, anno):
    """Year-on-year FOI inflation published on the chart page for mese/anno."""
    page.goto(GRAFICO, timeout=60000, wait_until="domcontentloaded")
    accept_cookies(page)
    page.wait_for_timeout(1500)
    label = f"{_MESI[mese - 1]}-{str(anno)[2:]}"
    m = None
    for _ in range(3):  # the data table is rendered after load: poll briefly
        body = page.inner_text("body")
        m = re.search(rf"^{label}\t(-?[\d.]+)\t", body, re.M)
        if m:
            break
        page.wait_for_timeout(1500)
    return (float(m.group(1)) if m else None), body


def _tool(capitale, rend, da, a):
    r = _fn(
        capitale_investito=capitale,
        rendimento_lordo_annuo_pct=rend,
        data_inizio=da,
        data_fine=a,
    )
    assert "errore" not in r, r
    return r


def _assert_infl(tool_pct, site_pct, label):
    assert site_pct is not None, f"{label}: valore del sito non trovato"
    diff = abs(round(tool_pct, 1) - site_pct)
    assert diff < 0.005, f"{label}: tool {tool_pct} (1 dec {round(tool_pct, 1)}) vs sito {site_pct}"


def _fisher_ok(r):
    """Hand check of the Fisher equation and the nominal montante."""
    from datetime import date

    # exact duration as the tool computes it (days / 365.25), not the rounded "anni"
    anni = (date.fromisoformat(r["data_fine"]) - date.fromisoformat(r["data_inizio"])).days / 365.25
    i = r["rendimento_lordo_annuo_pct"] / 100
    pi = r["inflazione_media_annua_pct"] / 100
    assert abs(r["montante_nominale"] - r["capitale_investito"] * (1 + i) ** anni) < 0.02
    assert abs(r["rendimento_reale_annuo_pct"] - ((1 + i) / (1 + pi) - 1) * 100) < 0.01


# ---------------------------------------------------------------------------
# Plan cases (secondary page calcolo-inflazione.php)
# ---------------------------------------------------------------------------


def test_biennio_alta_inflazione_2021_2023(page):
    """Plan: FOI 118,3/102,9 - 1 = 14,97%, media 7,23%, Fisher 1,035/1,0723-1 = -3,48%.

    Norma/fonte: indici FOI ISTAT (Gen 2021 - Gen 2023).
    """
    r = _tool(10000, 3.5, "2021-01-01", "2023-01-01")
    site, _ = _site_calcolo_inflazione(page, 1, 2021, 1, 2023)
    _assert_infl(r["inflazione_totale_pct"], site, "Gen21-Gen23")
    _fisher_ok(r)
    assert r["potere_acquisto_preservato"] is False


def test_biennio_bassa_inflazione_2024_2026_cambio_base(page):
    """Limit: end month in the new base 2025=100 (coefficient 1,214).

    Plan: 121,9/119,3 - 1 = 2,18%, media 1,08%, montante 10.609,43, reale 1,90%.
    """
    r = _tool(10000, 3.0, "2024-01-01", "2026-01-01")
    site, _ = _site_calcolo_inflazione(page, 1, 2024, 1, 2026)
    _assert_infl(r["inflazione_totale_pct"], site, "Gen24-Gen26")
    assert r["montante_nominale"] == pytest.approx(10609.43, abs=0.01)
    _fisher_ok(r)


def test_soglia_rendimento_pari_inflazione(page):
    """Limit (threshold): return 1,08% = mean inflation 2024-2026.

    Plan: reale circa zero; tool shows -0,0 and potere_acquisto_preservato
    false. The site only checks the inflation component (same as above).
    """
    r = _tool(10000, 1.08, "2024-01-01", "2026-01-01")
    site, _ = _site_calcolo_inflazione(page, 1, 2024, 1, 2026)
    _assert_infl(r["inflazione_totale_pct"], site, "soglia Gen24-Gen26")
    assert abs(r["rendimento_reale_annuo_pct"]) < 0.01
    _fisher_ok(r)


def test_estate_ago25_ago26_calcolatore(page):
    """Limit: period across August, end on the last published month (Ago 2026)."""
    r = _tool(10000, 2.0, "2025-08-01", "2026-08-01")
    site, _ = _site_calcolo_inflazione(page, 8, 2025, 8, 2026)
    _assert_infl(r["inflazione_totale_pct"], site, "Ago25-Ago26 calcolatore")


# ---------------------------------------------------------------------------
# Primary page: published year-on-year inflation (grafico)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "mese,anno",
    [
        (8, 2026),   # last published month (limit)
        (1, 2026),   # first month of base 2025=100 (limit)
        (12, 2023),  # year-end, older table year
    ],
)
def test_grafico_inflazione_tendenziale(page, mese, anno):
    """Year-on-year FOI inflation published on the chart page vs the tool over
    the same 12 months (data_inizio = same month of previous year)."""
    r = _tool(10000, 2.0, f"{anno - 1}-{mese:02d}-01", f"{anno}-{mese:02d}-01")
    site, _ = _site_grafico_yoy(page, mese, anno)
    _assert_infl(r["inflazione_totale_pct"], site, f"YoY {mese:02d}/{anno}")


# ---------------------------------------------------------------------------
# Beyond the last published month
# ---------------------------------------------------------------------------


def test_mese_non_pubblicato_set_2026(page):
    """Limit: data_fine Set 2026, index not yet published (data to Ago 2026).

    The tool substitutes 08/2026 and warns (INDICATIVO); check what the site does.
    """
    r = _tool(10000, 2.0, "2026-08-01", "2026-09-01")
    assert r["avvertenza"] and "non disponibile" in r["avvertenza"]
    site, body = _site_calcolo_inflazione(page, 8, 2026, 9, 2026)
    if site is None:
        pytest.skip("Il sito non calcola con un indice FOI non ancora pubblicato (Set 2026)")
    _assert_infl(r["inflazione_totale_pct"], site, "Ago26-Set26")

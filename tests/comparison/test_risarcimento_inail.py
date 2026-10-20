"""Benchmark risarcimento_inail vs avvocatoandreani.it (Calcolo Risarcimento INAIL).

Page: servizi/calcolo_risarcimento_inail_infortunio_lavoro.php
Site fields: Punti (6-64 only), Eta (14-75), Inquadramento (enabled from 16%),
Retribuzione (enabled from 16%), QuoteIntegrative. No sex field, no temporary
disability section. Site tables: Tabella indennizzo danno biologico in force
from 01/07/2025 (Circ. INAIL 45/2025), minimale/massimale 2025 (Circ. INAIL
37/2025). The tool takes no age: the site is driven with a 40-year-old worker
("Industria: tutti i lavoratori", no quote integrative).

Norms: D.Lgs. 38/2000 art. 13 (capital 6-15%, annuity from 16% = biological
quota + patrimonial quota = retribuzione x coefficiente x grado);
DPR 1124/1965 artt. 68, 116 (temporary disability, minimale/massimale).
"""

import os

os.environ.setdefault("LEGAL_TODAY", "2026-09-25")

import re

import pytest

from tests.comparison.conftest import accept_cookies, assert_close, extract_amount, parse_euro

URL = "https://www.avvocatoandreani.it/servizi/calcolo_risarcimento_inail_infortunio_lavoro.php"
ETA_SITO = "40"
INQUADRAMENTO = "10"  # Industria: tutti i lavoratori


def _tool(**kwargs):
    import src.server  # noqa: F401  (registers modules, avoids circular imports)
    from src.tools.risarcimento_danni import risarcimento_inail

    fn = getattr(risarcimento_inail, "fn", risarcimento_inail)
    return fn(**kwargs)


def _site(page, punti: int, retribuzione: float) -> str:
    page.goto(URL, timeout=60000, wait_until="domcontentloaded")
    page.wait_for_timeout(1500)
    # On this page the result is rendered only after the Quantcast consent is
    # actually accepted: removing the overlay via JS (accept_cookies) is not enough.
    try:
        page.click("#qc-cmp2-container button[mode='primary']", timeout=5000)
        page.wait_for_timeout(500)
    except Exception:
        pass
    accept_cookies(page)
    page.select_option("select[name='Punti']", str(punti))
    page.select_option("select[name='Eta']", ETA_SITO)
    if page.is_enabled("select[name='Inquadramento']"):
        page.select_option("select[name='Inquadramento']", INQUADRAMENTO)
    if page.is_enabled("input[name='Retribuzione']"):
        page.fill("input[name='Retribuzione']", f"{retribuzione:.2f}".replace(".", ","))
    page.click("form#DannoInail input[type=submit]", force=True)
    page.wait_for_timeout(3000)
    text = page.inner_text("body")
    assert "RIEPILOGO INFORMAZIONI" in text, "site did not return a result"
    return text


def _amount(text: str, label_regex: str) -> float:
    m = re.search(label_regex + r"[^\n€]*€\s*([\d.,]+)", text)
    assert m, f"label not found on site: {label_regex}"
    return parse_euro(m.group(1))


# ---------------------------------------------------------------- capital ---

def test_permanente_5_franchigia():
    """Plan: no indemnity below 6% (art. 13 co. 2 lett. a D.Lgs. 38/2000).
    Site does not offer degrees below 6 (Punti starts at 6)."""
    r = _tool(retribuzione_annua=30000, percentuale_invalidita=5, tipo="permanente")
    assert r.get("esito") == "Nessun indennizzo"
    pytest.skip("sito_non_calcola: the site's Punti select starts at 6%; tool says 'Nessun indennizzo' (consistent with art. 13)")


def test_permanente_6_capitale(page):
    """Plan: capital from Tabella indennizzo danno biologico for 6 points, age
    (and formerly sex), independent of pay (art. 13 co. 2 lett. a). Tool: 12.600
    (42% of pay). Limit case: first degree in capital."""
    r = _tool(retribuzione_annua=30000, percentuale_invalidita=6, tipo="permanente")
    text = _site(page, 6, 30000)
    site = _amount(text, r"Risarcimento danno biologico in capitale")
    assert_close(r["indennizzo_capitale"], site, tolerance=0.01, label="capitale_6")


def test_permanente_15_capitale(page):
    """Plan: last degree in capital, from INAIL table; tool gives 31.500 (> annual pay).
    Limit case: 15/16 boundary, capital side."""
    r = _tool(retribuzione_annua=30000, percentuale_invalidita=15, tipo="permanente")
    text = _site(page, 15, 30000)
    site = _amount(text, r"Risarcimento danno biologico in capitale")
    assert_close(r["indennizzo_capitale"], site, tolerance=0.01, label="capitale_15")


# ---------------------------------------------------------------- annuity ---

def _check_rendita(page, retribuzione, punti, label):
    r = _tool(retribuzione_annua=retribuzione, percentuale_invalidita=punti, tipo="permanente")
    text = _site(page, punti, retribuzione)
    site_bio = _amount(text, r"Rendita annuale per danno biologico")
    site_pat = _amount(text, r"Rendita annuale per danno patrimoniale")
    site_tot = _amount(text, r"Rendita vitalizia annuale")
    site_rif = extract_amount(text, "Retribuzione di riferimento")
    detail = (f"tool bio={r['quota_danno_biologico']} pat={r['quota_danno_patrimoniale']} "
              f"tot={r['rendita_annua']} | site bio={site_bio} pat={site_pat} tot={site_tot} rif={site_rif}")
    print(detail)
    assert_close(r["rendita_annua"], site_tot, tolerance=0.01, label=f"{label}_totale ({detail})")
    assert_close(r["quota_danno_biologico"], site_bio, tolerance=0.01, label=f"{label}_bio")
    assert_close(r["quota_danno_patrimoniale"], site_pat, tolerance=0.01, label=f"{label}_pat")


def test_permanente_16_rendita(page):
    """Plan: annuity = tabular biological quota + patrimonial quota (pay within
    massimale x coefficient x 16%), art. 13 co. 2 lett. b; tool gives 1.920/yr with
    patrimonial quota zero. Limit case: first degree in annuity."""
    _check_rendita(page, 30000, 16, "rendita_16")


def test_permanente_21_rendita_cambio_coefficiente(page):
    """Added limit case: 20/21 boundary of the Tabella dei coefficienti
    (grade A: 0,4 for 16-20%, 0,5 for 21-25%), art. 13 co. 2 lett. b."""
    _check_rendita(page, 30000, 21, "rendita_21")


def test_permanente_20_retribuzione_sotto_minimale(page):
    """Added limit case: pay 10.000 below the INAIL minimale (art. 116 DPR
    1124/1965); the site raises it to the 2025 minimale (20.426,70)."""
    _check_rendita(page, 10000, 20, "rendita_20_minimale")


def test_permanente_50_oltre_massimale(page):
    """Plan: patrimonial quota on pay capped at the year's massimale (art. 116
    DPR 1124/1965); tool uses 60.000 and gives 24.240/yr."""
    _check_rendita(page, 60000, 50, "rendita_50_massimale")


# -------------------------------------------------------------- temporary ---

def test_temporanea():
    """Plan: 60% of average daily pay from day 4 to 90, 75% from day 91
    (art. 68 DPR 1124/1965); tool: 49,32 and 61,64 on 30.000/365.
    The site page has no temporary-disability section."""
    r = _tool(retribuzione_annua=30000, percentuale_invalidita=0, tipo="temporanea")
    assert r["dal_4_al_90_giorno"]["indennita_giornaliera"] == 49.32
    pytest.skip("non_confrontabile: the site computes only permanent damage (art. 13), not inabilita' temporanea")

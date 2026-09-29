"""Benchmark danno_biologico_macro vs avvocatoandreani.it (Tabella Unica Nazionale).

Site page: /servizi/calcolo-danno-biologico-macropermanenti-tabella-unica.php
(TUN, DPR 13 gennaio 2025 n. 12, tables 2026 and 2025).

Norm: art. 138 D.Lgs. 209/2005 (Cod. Ass.); co. 3 caps the further
personalisation at 30%. The TUN is NOT transcribed in the tool (declared
STIMATO): its point values and decade age steps are indicative, so large
deviations from the site are expected and are recorded as genuine failures.

Comparison basis: the tool computes a pure biological amount
(punto x punti x coeff_eta) plus an optional personalisation on it. On the
site we therefore switch OFF the moral component (DoPersMorale=0) and read
"Danno biologico permanente"; the personalisation case uses the site's
"Ulteriore personalizzazione" applied to "solo danno permanente" (line B,
"Aumento ex art. 138, comma 3 CAP").
Site table year: 2026 (the tool's data vintage is 2026-09-03; the macro
values carry no year of their own).
Tolerance: 0.01 EUR (brief).
"""

import os
import re
import sys

import pytest

from .conftest import accept_cookies, parse_euro, assert_close

os.environ.setdefault("LEGAL_TODAY", "2026-09-25")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import src.server  # noqa: E402,F401  (registers all modules)
from src.tools.risarcimento_danni import danno_biologico_macro as _tool  # noqa: E402

_fn = getattr(_tool, "fn", _tool)

URL = "https://www.avvocatoandreani.it/servizi/calcolo-danno-biologico-macropermanenti-tabella-unica.php"
TOL = 0.01


def _site(page, punti: int, eta: int, pers_pct: int = 0, anno: str = "2026") -> dict:
    """Drive the TUN calculator with the moral component off; return parsed amounts."""
    page.goto(URL, timeout=60000, wait_until="domcontentloaded")
    page.wait_for_timeout(2000)
    accept_cookies(page)
    # Each select triggers an ajax refresh (dtu-getdata) of the read-only point fields.
    page.select_option("#Anno", anno)
    page.wait_for_timeout(1200)
    page.select_option("#Eta", str(eta))
    page.wait_for_timeout(1200)
    page.select_option("#Punti", str(punti))
    page.wait_for_timeout(1200)
    page.check("#DoPersMorale-0", force=True)
    page.wait_for_timeout(800)
    if pers_pct:
        page.check("#TipoPersTot-1", force=True)
        page.evaluate(
            """(v)=>{for (const id of ['PctPersTot','PctPersVal']) {
                 const e=document.getElementById(id); e.value=String(v);
                 e.dispatchEvent(new Event('input',{bubbles:true}));
                 e.dispatchEvent(new Event('change',{bubbles:true}));}}""",
            pers_pct,
        )
        page.wait_for_timeout(800)
    # A plain click on #create does not submit in headless Chromium: submit the
    # form natively with the Op=Calcola field the button would have posted.
    with page.expect_navigation(timeout=30000):
        page.evaluate(
            """()=>{const f=document.getElementById('DannoTabellaUnica');
               const h=document.createElement('input');h.type='hidden';h.name='Op';
               h.value='Calcola';f.appendChild(h);HTMLFormElement.prototype.submit.call(f);}"""
        )
    page.wait_for_timeout(2000)
    body = page.inner_text("body")
    start = body.find("Percentuale di invalidit")
    text = body[start:start + 3000]

    def amount(pattern):
        m = re.search(pattern + r"[^\n]*?€\s*([\d.,]+)\s*$", text, re.MULTILINE)
        return parse_euro(m.group(1)) if m else None

    coeff = re.search(r"Coefficiente di riduzione per et[àa]\s*([\d,]+)", text)
    return {
        "text": text,
        "biologico": amount(r"^(?:A\) )?Danno (?:biologico permanente|non patrimoniale complessivo) \("),
        "totale": amount(r"^TOTALE GENERALE"),
        "punto_bio": amount(r"^Punto danno biologico permanente"),
        "coeff": float(coeff.group(1).replace(",", ".")) if coeff else None,
    }


def _tool_call(**kw) -> dict:
    r = _fn(**kw)
    assert "errore" not in r, r
    return r


# Plan: 10 points at 40 -- first TUN degree. Tool 32.160 (2.680 x 10 x 1,20), STIMATO.
# Norm: art. 138 co. 2 Cod. Ass. + DPR 12/2025.
def test_10_punti_40_anni(page):
    t = _tool_call(percentuale_invalidita=10, eta_vittima=40)
    s = _site(page, 10, 40)
    print("SITE", s["punto_bio"], s["coeff"], s["biologico"], s["totale"], "TOOL", t["totale_risarcimento"])
    assert_close(t["totale_risarcimento"], s["biologico"], TOL, "10pt/40a danno biologico")


# Limit case: age 41 crosses the tool's decade step (31-40 -> 1.2, 41-50 -> 1.1);
# the TUN reduces by single year (art. 138 co. 2 lett. d). Norm: art. 138 co. 2.
def test_10_punti_41_anni_gradino_eta(page):
    t = _tool_call(percentuale_invalidita=10, eta_vittima=41)
    s = _site(page, 10, 41)
    print("SITE", s["punto_bio"], s["coeff"], s["biologico"], s["totale"], "TOOL", t["totale_risarcimento"])
    assert_close(t["totale_risarcimento"], s["biologico"], TOL, "10pt/41a danno biologico")


# Plan: 20 points at 30 with personalisation at the 30% cap (art. 138 co. 3).
# Tool 132.600 + 39.780 = 172.380. Site: biological + 30% "solo danno permanente".
def test_20_punti_30_anni_personalizzazione_30(page):
    t = _tool_call(percentuale_invalidita=20, eta_vittima=30, personalizzazione_pct=30)
    s = _site(page, 20, 30, pers_pct=30)
    print("SITE", s["punto_bio"], s["coeff"], s["biologico"], s["totale"], "TOOL", t["danno_base"], t["totale_risarcimento"])
    assert_close(t["danno_base"], s["biologico"], TOL, "20pt/30a danno biologico (base)")
    assert_close(t["totale_risarcimento"], s["totale"], TOL, "20pt/30a totale con pers. 30%")


# Limit case: 12 points, interpolated by the tool between 10 and 15; age 40.
# Norm: art. 138 co. 2 (TUN point grows with each degree).
def test_12_punti_interpolato(page):
    t = _tool_call(percentuale_invalidita=12, eta_vittima=40)
    s = _site(page, 12, 40)
    print("SITE", s["punto_bio"], s["coeff"], s["biologico"], s["totale"], "TOOL", t["totale_risarcimento"])
    assert_close(t["totale_risarcimento"], s["biologico"], TOL, "12pt/40a danno biologico")


# Plan: 50 points at 55. Tool 925.000 (declared overestimate). Norm: art. 138 co. 2.
def test_50_punti_55_anni(page):
    t = _tool_call(percentuale_invalidita=50, eta_vittima=55)
    s = _site(page, 50, 55)
    print("SITE", s["punto_bio"], s["coeff"], s["biologico"], s["totale"], "TOOL", t["totale_risarcimento"])
    assert_close(t["totale_risarcimento"], s["biologico"], TOL, "50pt/55a danno biologico")


# Plan: 100 points at 20 -- maximum. Tool 10.640.000, expected an order of
# magnitude above the TUN. Norm: art. 138 co. 2.
def test_100_punti_20_anni(page):
    t = _tool_call(percentuale_invalidita=100, eta_vittima=20)
    s = _site(page, 100, 20)
    print("SITE", s["punto_bio"], s["coeff"], s["biologico"], s["totale"], "TOOL", t["totale_risarcimento"])
    assert_close(t["totale_risarcimento"], s["biologico"], TOL, "100pt/20a danno biologico")


# Plan: personalisation 31% -> error (art. 138 co. 3 caps it at 30%).
# Site: the personalisation slider stops at max=30, so it cannot express 31%.
def test_personalizzazione_31_oltre_tetto(page):
    r = _fn(percentuale_invalidita=20, eta_vittima=30, personalizzazione_pct=31)
    assert "errore" in r
    page.goto(URL, timeout=60000, wait_until="domcontentloaded")
    page.wait_for_timeout(1500)
    accept_cookies(page)
    site_max = page.get_attribute("#PctPersTot", "max")
    assert site_max == "30", site_max

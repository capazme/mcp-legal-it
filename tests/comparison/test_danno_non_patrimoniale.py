"""Benchmark danno_non_patrimoniale vs avvocatoandreani.it.

Pages:
- https://www.avvocatoandreani.it/servizi/calcolo_danno_non_patrimoniale.php (plan page):
  tribunal tables (Milano 2024 ... Roma 2025, "Tabella Generica"), points 0-100. Used for
  the degrees >= 10 because the tool declares "Tabelle Milano 2024" as its source.
- https://www.avvocatoandreani.it/servizi/calcolo_danno_biologico.php (secondary page):
  art. 139 D.Lgs. 209/2005 (Cod. Ass.) micropermanenti, Anno 2026 = DM MIMIT 20/07/2026
  (punto 988,45 euro, ITT 57,64 euro/giorno), the same table the tool reads for 1-9 points.

Norms: art. 139 co. 2 lett. a) and b), co. 3 (cap 20%), co. 6 Cod. Ass.; art. 138 co. 2-3
Cod. Ass. + DPR 12/2025 (TUN); Cass. SU 26972/2008 (unitary non-pecuniary damage).
The plan expects genuine deviations: the tool still sums the point values of the lower
degrees for 1-9 points, uses an interpolated estimate from 10 points, applies the art. 139
daily ITT amount everywhere and allows up to 50% moral + 50% "existential" add-ons.
These failures are recorded as such (Fase 2 judges them); the tolerance is NOT widened.
Tolerance: 0,01 euro (brief). Site table year: 2026 (micro), Milano 2024 (tribunal page).
"""

import os
import re
import sys

import pytest

from tests.comparison.conftest import accept_cookies, assert_close, goto, parse_euro

os.environ.setdefault("LEGAL_TODAY", "2026-09-25")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import src.server  # noqa: E402,F401  (registers all modules, avoids circular imports)
from src.tools.risarcimento_danni import danno_non_patrimoniale as _t  # noqa: E402

_fn = getattr(_t, "fn", _t)

MICRO = "calcolo_danno_biologico.php"
DNP = "https://www.avvocatoandreani.it/servizi/calcolo_danno_non_patrimoniale.php"
TOL = 0.01


def _tool(**kw):
    r = _fn(**kw)
    assert "errore" not in r, r
    return r


def _amount(body, label):
    m = re.search(re.escape(label) + r"[^\n€]*€\s*([\d.]+,\d{2})", body, re.IGNORECASE)
    return parse_euro(m.group(1)) if m else None


def _site_micro(page, punti, eta, itt=0, spese_mediche=0.0, pct_morale=0.0, morale_su_temporaneo=False):
    """Art. 139 calculator, Anno 2026. PctDM is the art. 139 co. 3 personalisation."""
    goto(page, MICRO)
    accept_cookies(page)
    page.select_option("select[name='Anno']", "2026")
    page.select_option("select[name='Punti']", str(punti))
    page.select_option("select[name='Decimali']", "0")
    page.fill("input[name='Eta']", str(eta))
    page.fill("input[name='GgAss']", str(itt))
    page.fill("input[name='PctDM']", f"{pct_morale:.2f}".replace(".", ","))
    page.check(f"input[name='CalcoloDannoMorale'][value='{1 if morale_su_temporaneo else 2}']", force=True)
    if spese_mediche:
        page.fill("input[name='SpeseMediche']", f"{spese_mediche:.2f}".replace(".", ","))
    page.click("#btn-calc", force=True)
    page.wait_for_load_state("domcontentloaded")
    try:
        page.wait_for_selector("text=TOTALE GENERALE", timeout=15000)
    except Exception:
        pass
    page.wait_for_timeout(1500)
    body = page.inner_text("body")
    res = {
        "tabella": (re.search(r"Tabella di riferimento\s*([\d-]+)", body) or [None, None])[1],
        "permanente": _amount(body, "Danno biologico permanente"),
        "temporaneo": _amount(body, "Totale danno biologico temporaneo"),
        "morale": _amount(body, "Danno morale"),
        "spese_mediche": _amount(body, "Spese mediche"),
        "totale": _amount(body, "TOTALE GENERALE"),
    }
    if res["permanente"] is None or res["totale"] is None:
        raise AssertionError(f"Risultato non leggibile dal sito: {body[:1500]}")
    print("SITE micro", {k: v for k, v in res.items()})
    return res


def _site_tribunale(page, punti, eta, tabella="1-2024", sofferenza=True, itt=0):
    """Tribunal-table calculator. A plain click on #btn-calc does not submit in headless
    Chromium: submit natively with the Op=Calcola field the button would post."""
    page.goto(DNP, timeout=60000, wait_until="domcontentloaded")
    page.wait_for_timeout(1500)
    accept_cookies(page)
    page.select_option("select[name='IdTabella']", tabella)
    page.wait_for_timeout(1500)  # ajax dnp-inittab refreshes ITT base and limits
    page.select_option("select[name='Punti']", str(punti))
    page.select_option("select[name='Eta']", str(eta))
    if not sofferenza:
        page.uncheck("input[name='IncrementoSofferenza']", force=True)
    if itt:
        page.fill("input[name='GgAss']", str(itt))
    with page.expect_navigation(timeout=30000):
        page.evaluate(
            """()=>{const f=document.forms['DannoNonPatrimoniale'];const h=document.createElement('input');
               h.type='hidden';h.name='Op';h.value='Calcola';f.appendChild(h);
               HTMLFormElement.prototype.submit.call(f);}"""
        )
    page.wait_for_timeout(2000)
    body = page.inner_text("body")
    start = body.find("Tabella di riferimento")
    text = body[start:start + 3000]
    res = {
        "tabella": (re.search(r"Tabella di riferimento:\s*([^\n]+)", text) or [None, None])[1],
        "punto_bio": _amount(text, "Punto danno biologico"),
        # With the suffering increment off the site prints only "Danno non patrimoniale
        # risarcibile", which is then the pure biological amount.
        "biologico": _amount(text, "Danno biologico risarcibile")
        or (None if sofferenza else _amount(text, "Danno non patrimoniale risarcibile")),
        "non_patrimoniale": _amount(text, "Danno non patrimoniale risarcibile"),
        "temporaneo": _amount(text, "Totale danno biologico temporaneo"),
        "totale": _amount(text, "Totale generale"),
        "text": text,
    }
    if res["totale"] is None:
        raise AssertionError(f"Risultato non leggibile dal sito: {body[:2000]}")
    print("SITE tribunale", {k: v for k, v in res.items() if k != "text"})
    print(text[:1500])
    return res


# Plan case 1 (limit: highest micro degree, last age without reduction).
# Atteso del piano: biologico 20.460,92 (988,45 x 2,3 x 9, art. 139 co. 2 lett. a e co. 6);
# il tool da' 13.937,15 (somma dei valori punto dei gradi inferiori): scostamento 6.523,77.
def test_9_punti_10_anni(page):
    t = _tool(percentuale_invalidita=9, eta_vittima=10)
    s = _site_micro(page, 9, 10)
    print("TOOL", t["componenti"]["danno_biologico"], t["totale_risarcimento"])
    assert s["tabella"] == "2026-2027"
    assert_close(t["componenti"]["danno_biologico"], s["permanente"], TOL, "biologico 9pt/10a")
    assert_close(t["totale_risarcimento"], s["totale"], TOL, "totale 9pt/10a")


# Limit case added: 1 point at 10 years with 10 days ITT. With a single degree the tool's
# summation equals the correct formula (988,45 x 1,0), and the ITT is 10 x 57,64 = 576,40
# (art. 139 co. 2 lett. b). Expected to coincide: control case for the driver.
def test_1_punto_10_anni_itt(page):
    t = _tool(percentuale_invalidita=1, eta_vittima=10, giorni_itt=10)
    s = _site_micro(page, 1, 10, itt=10)
    print("TOOL", t["componenti"], t["totale_risarcimento"])
    assert_close(t["componenti"]["danno_biologico"], s["permanente"], TOL, "biologico 1pt/10a")
    assert_close(t["componenti"]["danno_patrimoniale_emergente"]["itt"]["importo"], s["temporaneo"], TOL, "ITT 10 gg")
    assert_close(t["totale_risarcimento"], s["totale"], TOL, "totale 1pt/10a")


# Limit case added: 2 points at 11 years (first degree with a coefficient > 1 and first
# year of age reduction). Correct: 988,45 x 1,1 x 2 x 0,995 = 2.163,72; tool's summation
# 988,45 x (1,0 + 1,1) x 0,995 = 2.065,36. Art. 139 co. 2 lett. a.
def test_2_punti_11_anni(page):
    t = _tool(percentuale_invalidita=2, eta_vittima=11)
    s = _site_micro(page, 2, 11)
    print("TOOL", t["componenti"]["danno_biologico"])
    assert_close(t["componenti"]["danno_biologico"], s["permanente"], TOL, "biologico 2pt/11a")


# Plan case 2. Atteso: permanente 6.486,70 (988,45 x 1,5 x 5 x 0,875); temporaneo 1.729,20
# (30 x 57,64, art. 139 co. 2 lett. b: danno biologico temporaneo, non patrimoniale
# emergente); spese mediche 1.000; totale 9.215,90. Tool: 5.275,85 bio, totale 8.005,05.
def test_5_punti_35_anni_itt_spese(page):
    t = _tool(percentuale_invalidita=5, eta_vittima=35, giorni_itt=30, spese_mediche=1000)
    s = _site_micro(page, 5, 35, itt=30, spese_mediche=1000)
    c = t["componenti"]
    print("TOOL", c, t["totale_risarcimento"])
    # ITT amount (same per-day value, different classification) is compared first.
    assert_close(c["danno_patrimoniale_emergente"]["itt"]["importo"], s["temporaneo"], TOL, "ITT 30 gg")
    assert_close(c["danno_biologico"], s["permanente"], TOL, "biologico 5pt/35a")
    assert_close(t["totale_risarcimento"], s["totale"], TOL, "totale 5pt/35a")


# Plan case 3 (limit: personalisation cap). Atteso: biologico 4.625,95 (988,45 x 1,3 x 4 x
# 0,90); aumento massimo 20% (art. 139 co. 3) = 925,19 sul solo permanente, totale 5.551,14.
# Tool: 4.092,18 + 2.046,09 (morale 50%) + 2.046,09 (esistenziale 50%) = 8.184,37; il danno
# esistenziale non e' voce autonoma (Cass. SU 26972/2008). Site: PctDM 20, solo permanente.
def test_4_punti_30_anni_morale_esistenziale_50(page):
    t = _tool(percentuale_invalidita=4, eta_vittima=30, tipo_danno="morale",
              danno_morale_pct=50, danno_esistenziale_pct=50)
    s = _site_micro(page, 4, 30, pct_morale=20, morale_su_temporaneo=False)
    c = t["componenti"]
    print("TOOL", c, t["totale_risarcimento"])
    assert_close(c["danno_biologico"], s["permanente"], TOL, "biologico 4pt/30a")
    personalizzazione = c["danno_morale"]["importo"] + c["danno_esistenziale"]["importo"]
    assert_close(personalizzazione, s["morale"], TOL, "personalizzazione (tetto 20%)")
    assert_close(t["totale_risarcimento"], s["totale"], TOL, "totale 4pt/30a")


# Plan case 4. Atteso: biologico dalla TUN per 20 punti a 40 anni, gia' comprensivo della
# componente morale (art. 138 co. 2 lett. e), personalizzazione fino al 30% (co. 3). Tool:
# 122.400 + 36.720 = 159.120. The tool cites "Tabelle Milano 2024": compared with Milano 2024
# on the plan page (bio without "sofferenza" vs tool bio; tool total vs the site's total
# non-pecuniary damage with the Milano suffering increment).
def test_20_punti_40_anni_morale_30_milano_2024(page):
    t = _tool(percentuale_invalidita=20, eta_vittima=40, danno_morale_pct=30)
    s = _site_tribunale(page, 20, 40, "1-2024", sofferenza=True)
    print("TOOL", t["componenti"]["danno_biologico"], t["totale_risarcimento"])
    assert "Milano 2024" in (s["tabella"] or "")
    assert_close(t["componenti"]["danno_biologico"], s["biologico"], TOL, "biologico 20pt/40a Milano 2024")
    assert_close(t["totale_risarcimento"], s["totale"], TOL, "totale non patrimoniale 20pt/40a")


# Plan case 5 (limit: boundary 9 -> 10, first macro degree). Atteso: biologico dalla TUN /
# tabella del tribunale; ITT con i valori dell'art. 138 o del tribunale, non 57,64 euro.
# Tool: 32.160 + 1.152,80 = 33.312,80. Site: Milano 2024, sofferenza off, 20 gg ITT at the
# table's default daily base (115,00 euro, minimum of the Milano range 115-173).
def test_10_punti_40_anni_itt_milano_2024(page):
    t = _tool(percentuale_invalidita=10, eta_vittima=40, giorni_itt=20)
    s = _site_tribunale(page, 10, 40, "1-2024", sofferenza=False, itt=20)
    c = t["componenti"]
    print("TOOL", c, t["totale_risarcimento"])
    assert_close(c["danno_biologico"], s["biologico"], TOL, "biologico 10pt/40a Milano 2024")
    assert_close(c["danno_patrimoniale_emergente"]["itt"]["importo"], s["temporaneo"], TOL, "ITT 20 gg")
    assert_close(t["totale_risarcimento"], s["totale"], TOL, "totale 10pt/40a")

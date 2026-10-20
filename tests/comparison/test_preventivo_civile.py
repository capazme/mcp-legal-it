"""Comparison: preventivo_civile vs avvocatoandreani.it.

Main page: servizi/preventivo-avvocato-civile.php (redattore del preventivo, cause civili).
The site proposes the DM 55/2014 (as amended by DM 147/2022) mean value per phase for the
chosen band, lets the user move each phase by a percentage (slider -100..+100, importo =
medio + Round(pct * medio / 100)) and adds the legal accessories (spese generali 15%, Cassa
4%, IVA 22%). The generated document lists every phase, the total fee, each accessory and
"TOTALE PREVENTIVO"; with no expense lines entered, that total equals the tool's
`totale_onorari`.

What the site does NOT do on this page: it does not compute the contributo unificato (the
expense lines are free text, filled by the lawyer) and has no notion of the tool's
estimated out-of-pocket costs (PEC notification 3,54, bailiff notification 27, copies 15:
estimates without a normative basis, excluded by the plan). The contributo unificato is
therefore checked against the site's own calculator (servizi/calcolo_contributo_unificato.php)
and the tool's `totale_preventivo` is not comparable.

Levels: the tool's 'min'/'max' are the table values medio -50% / +50% (parametri_forensi.json,
transcribed from this same site). They are checked twice: on the main page with the -50/+50
slider, and on the secondary page calcolo-compenso-avvocati-parametri-civili-2014.php (tables
"2022 (vigenti)"), whose Min/Med/Max columns are read directly.

Norme: DM 55/2014 art. 4 co. 1 e tabella 2 (giudizi di cognizione innanzi al tribunale) come
modificati dal DM 147/2022; art. 2 co. 2 DM 55/2014 (spese generali 15%); art. 11 L. 576/1980
(CPA 4%); DPR 633/1972 (IVA 22%); art. 13 co. 1 DPR 115/2002 (contributo unificato).

Tolerance: 0,01 euro on every amount (brief).
"""

import os
import re
import sys

import pytest

os.environ.setdefault("LEGAL_TODAY", "2026-09-25")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import src.server  # noqa: E402,F401  (registers every tool module)
from src.tools.fatturazione_avvocati import preventivo_civile as _pc  # noqa: E402
from tests.comparison.conftest import accept_cookies, assert_close, goto, parse_euro  # noqa: E402

_fn = getattr(_pc, "fn", _pc)

PAGE = "preventivo-avvocato-civile.php"
PARAMETRI_PAGE = "calcolo-compenso-avvocati-parametri-civili-2014.php"
CU_PAGE = "calcolo_contributo_unificato.php"
TOL = 0.01

FASI = ["studio", "introduttiva", "istruttoria", "decisionale"]
SITE_FASE_LABEL = {
    "studio": "Fase di studio della controversia",
    "introduttiva": "Fase introduttiva del giudizio",
    "istruttoria": "Fase istruttoria e/o di trattazione",
    "decisionale": "Fase decisionale",
}
# DM 55/2014 value bands -> option value of the site's "Scaglione" select
SCAGLIONI = [
    (1_100, "10"), (5_200, "20"), (26_000, "30"), (52_000, "40"), (260_000, "50"),
    (520_000, "60"), (1_000_000, "70"), (2_000_000, "80"), (4_000_000, "90"),
    (8_000_000, "100"), (16_000_000, "110"), (32_000_000, "120"),
]
LEVEL_PCT = {"min": -50, "medio": 0, "max": 50}
LEVEL_COL = {"min": 1, "medio": 2, "max": 3}


def _scaglione_code(valore: float) -> str:
    for fino_a, code in SCAGLIONI:
        if valore <= fino_a:
            return code
    raise ValueError(f"valore {valore} oltre l'ultimo scaglione del redattore")


# --------------------------------------------------------------------------- tool

def _tool(**kwargs) -> dict:
    out = _fn(**kwargs)
    assert "errore" not in out, f"tool error for {kwargs}: {out.get('errore')}"
    return out["dettaglio_calcoli"]


# --------------------------------------------------------------------------- site (redattore)

def _site_preventivo(page, valore: float, fasi: list[str], livello: str,
                     spese_generali: bool, cpa: bool, iva: bool) -> dict:
    """Fill the preventivo form and return the amounts of the generated document.

    Checkbox/radio clicks are intermittently swallowed by the ad/consent handlers, so the
    fields are set in JS and the page's own handlers (App.OnClickSelFase,
    App.OnClickDoAccessori) are called; the form is posted with requestSubmit.
    """
    goto(page, PAGE, wait_ms=1500)
    f = lambda n, v: page.fill(f"[name='{n}']", v)  # noqa: E731
    # mandatory header data (fictitious, only to let the site generate the document)
    f("ARagSoc-0", "Avv. Mario Rossi")
    f("AIndir-0", "Via Roma 1, Roma")
    f("ACodFis-0", "RSSMRA80A01H501U")
    page.select_option("[name='AOrdine-0']", "Roma")
    f("APolizza-0", "Polizza n. 1")
    f("PRagSoc-0", "Sig. Luigi Bianchi")
    f("PCodFis-0", "BNCLGU70A01H501Y")
    f("DescrCausa", "Causa civile di prova")
    f("Controparti", "Sig. Tizio Caio")
    f("LuogoUfficio", "Roma")
    f("Luogo", "Roma")

    page.select_option("select[name='Scaglione']", _scaglione_code(valore))
    page.wait_for_timeout(2000)  # ajax reload of the phase mean values
    pct = LEVEL_PCT[livello]
    for i, fase in enumerate(FASI):
        page.evaluate(
            "([id, v]) => { const e = document.getElementById(id);"
            " if (e.checked !== v) { e.checked = v; App.OnClickSelFase(e); } }",
            [f"SelFase-{i}", fase in fasi],
        )
        if fase in fasi and pct:
            f(f"PctFaseVal-{i}", str(pct))
            page.press(f"[name='PctFaseVal-{i}']", "Tab")
            page.wait_for_timeout(300)

    accessori = spese_generali or cpa or iva
    page.evaluate(
        "v => { const r = [...document.querySelectorAll('input[name=DoAccessori]')]"
        ".find(x => x.value === v); r.checked = true; App.OnClickDoAccessori(r); }",
        "1" if accessori else "0",
    )
    if accessori:
        page.evaluate(
            "([sg, cpa, iva]) => { const g = document.getElementById('DoSpeseGen');"
            " if (g.checked !== sg) { g.checked = sg; App.OnClickDoSpeseGen(g); }"
            " document.getElementById('DoCassa').checked = cpa;"
            " document.getElementById('DoIva').checked = iva; }",
            [spese_generali, cpa, iva],
        )

    with page.expect_navigation(wait_until="domcontentloaded", timeout=60000):
        page.eval_on_selector(
            "form#PreventivoAvvocatoCivile input[type=submit]", "b => b.form.requestSubmit(b)"
        )
    page.wait_for_timeout(2000)
    body = page.inner_text("body")
    start = body.find("1.1) Compenso:")
    end = body.find("TOTALE PREVENTIVO")
    assert start >= 0 and end > start, "the site did not generate the preventivo (form errors?)"
    block = body[start:end + 200]

    def amount(label: str):
        m = re.search(rf"{re.escape(label)}[^\n€]*€\s*([\d.]+,\d{{2}})", block)
        return parse_euro(m.group(1)) if m else None

    return {
        "fasi": {fase: amount(SITE_FASE_LABEL[fase]) for fase in FASI},
        "compensi": amount("Totale compenso:"),
        "spese_generali": amount("Spese generali") or 0.0,
        "cpa": amount("Cassa Avvocati") or 0.0,
        "iva": amount("IVA (") or 0.0,
        "totale": amount("TOTALE PREVENTIVO:"),
    }


def _compare(tool: dict, site: dict, fasi: list[str]):
    for d in tool["fasi"]:
        assert_close(d["importo"], site["fasi"][d["fase"]], TOL, f"fase {d['fase']}")
    for fase in FASI:
        if fase not in fasi:
            assert site["fasi"][fase] is None, f"site listed unselected phase {fase}"
    assert_close(tool["totale_compensi"], site["compensi"], TOL, "totale compensi")
    assert_close(tool["spese_generali_15pct"], site["spese_generali"], TOL, "spese generali 15%")
    assert_close(tool["cpa_4pct"], site["cpa"], TOL, "CPA 4%")
    assert_close(tool["iva_22pct"], site["iva"], TOL, "IVA 22%")
    # no expense lines entered on the site: its TOTALE PREVENTIVO = compensi + accessori
    assert_close(tool["totale_onorari"], site["totale"], TOL, "totale onorari")


# --------------------------------------------------------------------------- site (tabella parametri)

def _site_parametri(page, valore: float) -> dict:
    """Min/Med/Max per phase from the parametri page, tables '2022 (vigenti)', tribunale."""
    goto(page, PARAMETRI_PAGE, wait_ms=1500)
    page.select_option("select[name='Anno']", "2022")
    page.wait_for_timeout(1000)
    page.select_option("select[name='Competenza']", "110")
    page.wait_for_timeout(1500)
    page.select_option("select[name='Scaglione']", _scaglione_code(valore))
    page.wait_for_timeout(2000)
    out = {}
    for i, fase in enumerate(FASI, start=1):
        out[fase] = {
            lvl: parse_euro(page.inner_text(f"[id='v{i}.{col}']")) for lvl, col in LEVEL_COL.items()
        }
    return out


# --------------------------------------------------------------------------- site (contributo unificato)

def _site_cu(page, valore: float) -> float:
    """Contributo unificato, civile primo grado, valore determinato (site calculator)."""
    goto(page, CU_PAGE, wait_ms=1500)
    page.evaluate(
        """(val) => { const f = document.ContributoUnificato;
            f.Processo.value = "1"; f.Giudizio.value = "1";
            for (const r of f.TipoValore) r.checked = (r.value === "0");
            OnClickTipoValore();
            f.ValoreCausa.value = val; f.Riduzione.checked = false; }""",
        f"{valore:.2f}".replace(".", ","),
    )
    with page.expect_navigation(wait_until="domcontentloaded", timeout=60000):
        page.eval_on_selector("#btn-calc", "b => b.form.requestSubmit(b)")
    page.wait_for_timeout(2000)
    echo = page.evaluate("() => document.ContributoUnificato.ValoreCausa.value")
    assert abs(parse_euro(echo) - valore) < 0.005, f"site read {echo!r} for {valore}"
    for t in (e.inner_text() for e in page.query_selector_all(".result")):
        m = re.search(r"contributo\s+è\s+€\s*([\d.]+,\d{2})", t, re.IGNORECASE)
        if m:
            return parse_euro(m.group(1))
    raise AssertionError(f"no contributo unificato in the site result for {valore}")


# =========================================================================== tests (redattore)

# Plan case 1 -- upper bound of band 5.201-26.000, livello medio, all accessories.
# Atteso: compensi 5.077; SG 761,55; CPA 233,54; IVA 1.335,86; totale onorari 7.407,95.
# DM 55/2014 tab. 2 (DM 147/2022), art. 2 co. 2; art. 11 L. 576/1980; DPR 633/1972.
def test_confine_26000_medio_accessori(page):
    kw = dict(valore_causa=26000, fasi=None, livello="medio", spese_generali=True, cpa=True, iva=True)
    _compare(_tool(**kw), _site_preventivo(page, 26000, FASI, "medio", True, True, True), FASI)


# Plan case 2 -- upper bound of band 1.101-5.200 (also the CU band limit), livello medio.
# Atteso: compensi 2.552; totale onorari 3.723,67. DM 55/2014 tab. 2.
def test_confine_5200_medio_accessori(page):
    kw = dict(valore_causa=5200, fasi=None, livello="medio", spese_generali=True, cpa=True, iva=True)
    _compare(_tool(**kw), _site_preventivo(page, 5200, FASI, "medio", True, True, True), FASI)


# Plan case 3 -- first band (fino a 1.100), livello min, only studio + introduttiva.
# Atteso: compensi 66 + 66 = 132; totale onorari 192,60. DM 55/2014 art. 4 co. 1 (riduzione 50%).
def test_primo_scaglione_min_due_fasi(page):
    fasi = ["studio", "introduttiva"]
    kw = dict(valore_causa=1100, fasi=fasi, livello="min", spese_generali=True, cpa=True, iva=True)
    _compare(_tool(**kw), _site_preventivo(page, 1100, fasi, "min", True, True, True), fasi)


# Plan case 4 -- just above 520.000 (band 520.001-1.000.000), livello max, no accessories.
# Atteso: compensi 43.791 (6.911 + 4.559 + 20.301 + 12.020 = medio +50%). The plan's "+30%"
# wording is not what the table does: the band is the ordinary DM 147/2022 band 520.001-1.000.000.
def test_oltre_520000_max_senza_accessori(page):
    kw = dict(valore_causa=520000.01, fasi=None, livello="max", spese_generali=False, cpa=False, iva=False)
    _compare(_tool(**kw), _site_preventivo(page, 520000.01, FASI, "max", False, False, False), FASI)


# Extra -- first euro above 26.000: band 26.001-52.000, livello medio.
# Atteso (tabella): 1.701 + 1.204 + 1.806 + 2.905 = 7.616. DM 55/2014 tab. 2.
def test_confine_26000_01_scaglione_successivo(page):
    kw = dict(valore_causa=26000.01, fasi=None, livello="medio", spese_generali=True, cpa=True, iva=True)
    _compare(_tool(**kw), _site_preventivo(page, 26000.01, FASI, "medio", True, True, True), FASI)


# Extra -- enumerated option: IVA off (spese generali and CPA on), 50.000 livello medio.
# Atteso: compensi 7.616; SG 1.142,40; CPA 350,34 (4% su compensi + SG); IVA 0; totale 9.108,74.
def test_senza_iva_50000(page):
    kw = dict(valore_causa=50000, fasi=None, livello="medio", spese_generali=True, cpa=True, iva=False)
    _compare(_tool(**kw), _site_preventivo(page, 50000, FASI, "medio", True, True, False), FASI)


# Extra -- istruttoria + decisionale only, livello max, band 52.001-260.000 with accessories.
# Atteso (tabella): 8.505 + 6.380 = 14.885. DM 55/2014 art. 4 co. 1 (aumento 50% per il tool).
def test_max_due_fasi_150000(page):
    fasi = ["istruttoria", "decisionale"]
    kw = dict(valore_causa=150000, fasi=fasi, livello="max", spese_generali=True, cpa=True, iva=True)
    _compare(_tool(**kw), _site_preventivo(page, 150000, fasi, "max", True, True, True), fasi)


# =========================================================================== tests (tabella parametri)

# Riscontro of the tool's min/medio/max phase values on the site's parametri page
# (tabelle 2022 vigenti, giudizi di cognizione innanzi al tribunale), band limits included.
@pytest.mark.parametrize("valore", [1100, 26000, 520000.01])
def test_valori_min_medio_max_tabella(page, valore):
    site = _site_parametri(page, valore)
    for livello in ("min", "medio", "max"):
        tool = _tool(valore_causa=valore, livello=livello, spese_generali=False, cpa=False, iva=False)
        for d in tool["fasi"]:
            assert_close(d["importo"], site[d["fase"]][livello], TOL, f"{valore} {d['fase']} {livello}")


# =========================================================================== tests (contributo unificato)

# Contributo unificato among the tool's spese vive vs the site's CU calculator.
# Atteso (art. 13 co. 1 DPR 115/2002): 43 (lett. a), 98 (lett. b), 237 (lett. c), 518 (lett. d),
# 1.686 (lett. g, oltre 520.000).
@pytest.mark.parametrize("valore,atteso", [
    (1100, 43.0), (5200, 98.0), (26000, 237.0), (26000.01, 518.0), (520000.01, 1686.0),
])
def test_contributo_unificato_spese_vive(page, valore, atteso):
    tool = _tool(valore_causa=valore)["spese_vive"]["contributo_unificato"]
    site = _site_cu(page, valore)
    assert_close(tool, site, TOL, f"contributo unificato {valore}")


# =========================================================================== not comparable

def test_totale_preventivo_con_spese_stimate_non_confrontabile():
    """totale_preventivo adds estimated costs (PEC 3,54, ufficiale giudiziario 27, copie 15)
    with no normative basis; the site's redattore has only free-text expense lines."""
    pytest.skip("il sito non stima le spese vive: totale_preventivo non confrontabile (escluso dal piano)")


def test_giudice_diverso_dal_tribunale_non_confrontabile():
    """The site offers Giudice di pace, Corte d'Appello etc.; the tool always uses the
    tribunale table (no `competenza` parameter)."""
    pytest.skip("il tool non distingue il giudice (sempre tribunale): altre competenze non confrontabili")

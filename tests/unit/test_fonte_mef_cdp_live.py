"""Live gate: MEF (Dipartimento del Tesoro) and CDP/Poste against `rendimento_btp` and
`rendimento_buoni_postali`.

Phase 4 of the avvocatoandreani.it benchmark, strategy `fonte_ufficiale`, group `mef_cdp`.
Neither tool has a calculator on the benchmark site (the BFP page only links to the CDP
simulator), so the tools are compared with the issuer's own documents.

What it checks (sources consulted on 2026-09-25):

* `rendimento_btp`
  - the 12,50% rate on the vigente text: art. 2 co. 1 and 3 D.Lgs. 239/1996, art. 3
    co. 1, 2 lett. a) and 5 lett. a) D.L. 66/2014 (26% everywhere except titoli di Stato
    ed equiparati; their capital gains count at 48,08%, i.e. 26% x 48,08% = 12,5%);
  - the tool's arithmetic (cedole, scarto, imposta) on the plan cases;
  - the MEF "Risultati Asta" of 10 September 2026 (BTP 3y IT0005716839, 7y IT0005722845,
    50y IT0005441883): the gross IRR rebuilt from price, coupon and dates reproduces the
    MEF "Rendimento Lordo" (validating the method), then the tool's simple net yield is
    compared with the net IRR of the same flows and with the MEF gross yield.
* `rendimento_buoni_postali`
  - series in placement (Buono ordinario, 3x4 con premio, dedicati ai minori): the link to
    the current foglio informativo is scraped from the product page on poste.it, the PDF is
    read in memory with `pdftotext` (poppler) and its coefficients are compared with the
    tool's montante (0,01 euro);
  - the 12,50% rate, cross-checked on every lordo/netto coefficient pair of the foglio;
  - products no longer issued (Buono 3x4 plain, Buono 4x4): poste.it lists them as
    "serie non più in emissione" (checked live); the conditions of their last series are
    frozen by hand from the scheda di sintesi (URL and date next to the values).

A failing test is a genuine divergence of the tool from the source: do not soften it.

Run:
    .venv/bin/pytest tests/unit/test_fonte_mef_cdp_live.py -m live -q -p no:cacheprovider -rfEs
Needs the network and the `pdftotext` binary (poppler): without it the PDF tests skip.
"""

from __future__ import annotations

import functools
import json
import re
import shutil
import subprocess
from datetime import date

import httpx
import pytest
from bs4 import BeautifulSoup

import src.server  # noqa: F401  (registers every tool module first: avoids a circular import)
from src.tools.investimenti import rendimento_btp, rendimento_buoni_postali
from tests.unit._norme_live import assert_parole

pytestmark = pytest.mark.live

OGGI = "2026-09-25"
ALIQUOTA = 0.125

_HEADERS = {"User-Agent": "Mozilla/5.0 (mcp-legal-it live benchmark)"}

_btp = getattr(rendimento_btp, "fn", rendimento_btp)
_bfp = getattr(rendimento_buoni_postali, "fn", rendimento_buoni_postali)


# --- plumbing --------------------------------------------------------------------------

def _get(url: str) -> httpx.Response:
    resp = httpx.get(url, headers=_HEADERS, timeout=45, follow_redirects=True)
    resp.raise_for_status()
    return resp


@functools.lru_cache(maxsize=None)
def _pdf_text(url: str) -> str:
    """Text of a PDF read in memory (stdin -> stdout of pdftotext): nothing touches the disk."""
    if not shutil.which("pdftotext"):
        pytest.skip("pdftotext (poppler) non installato: i fogli CDP e gli esiti MEF sono PDF")
    content = _get(url).content
    assert content[:4] == b"%PDF", f"{url} non restituisce un PDF"
    out = subprocess.run(["pdftotext", "-layout", "-", "-"], input=content,
                         capture_output=True, check=True)
    return out.stdout.decode("utf-8", "replace")


def _num(testo: str) -> float:
    return float(testo.replace(".", "").replace(",", "."))


_MESI = {m: i for i, m in enumerate(
    ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto",
     "settembre", "ottobre", "novembre", "dicembre"], start=1)}


def _data_it(testo: str) -> date:
    g, m, a = testo.split()
    return date(int(a), _MESI[m.lower()], int(g))


def _add_months(d: date, months: int) -> date:
    y, m = divmod(d.month - 1 + months, 12)
    return date(d.year + y, m + 1, d.day)


def _tir(flussi: list[tuple[float, float]]) -> float:
    """Annual effective IRR (percent) of (years, amount) flows, by bisection."""
    lo, hi = -0.5, 1.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if sum(c / (1 + mid) ** t for t, c in flussi) > 0:
            lo = mid
        else:
            hi = mid
    return mid * 100


def _tir_netto_btp(nominale, prezzo, cedola_pct, anni, freq):
    """Net IRR of a BTP bought at issue date, coupons and scarto taxed at 12,5%."""
    k = nominale * cedola_pct / 100 / freq * (1 - ALIQUOTA)
    flussi = [(0.0, -prezzo)] + [((i + 1) / freq, k) for i in range(anni * freq)]
    scarto = nominale - prezzo
    rimborso = nominale - (scarto * ALIQUOTA if scarto > 0 else 0.0)
    flussi[-1] = (flussi[-1][0], flussi[-1][1] + rimborso)
    return _tir(flussi)


# --- rendimento_btp: the 12,5% rate on the vigente text --------------------------------

def test_aliquota_12_50_titoli_di_stato_art2_dlgs_239_1996_art3_dl_66_2014():
    """Art. 2 co. 1 D.Lgs. 239/1996 sets 12,50% on titoli di Stato ed equiparati (co. 3 names
    the buoni postali); art. 3 D.L. 66/2014 raises everything else to 26% (co. 1), excludes
    titoli di Stato (co. 2 lett. a) and counts their capital gains at 48,08% (co. 5)."""
    assert_parole(
        "art. 2 D.Lgs. 239/1996",
        "nella misura del 12,50 per cento",
        "articolo 31 del decreto del presidente della repubblica 29 settembre 1973, n. 601",
        "per i buoni postali di risparmio",
    )
    assert_parole(
        "art. 3 D.L. 66/2014",
        "nella misura del 26 per cento",
        "obbligazioni e altri titoli di cui all'articolo 31 del decreto del presidente della "
        "repubblica 29 settembre 1973, n. 601 ed equiparati",
        "48,08 per cento",
    )
    r = _btp(valore_nominale=10000, prezzo_acquisto=9800, cedola_annua_pct=3.0, anni_scadenza=5)
    assert r["imposta_cedole"] == pytest.approx(r["totale_cedole_lordo"] * ALIQUOTA, abs=0.01)
    assert r["imposta_plusvalenza"] == pytest.approx(r["plusvalenza_lorda"] * ALIQUOTA, abs=0.01)
    b = _bfp(importo=10000, tipo="ordinario", anni=10)
    assert b["imposta_sostitutiva_pct"] == 12.5


# --- rendimento_btp: plan cases ----------------------------------------------------------

@pytest.mark.parametrize(
    "kwargs, atteso",
    [
        # Sotto la pari, cedola semestrale: cedole 1.500 (imposta 187,50), scarto 200 (imposta 25).
        ({"valore_nominale": 10000, "prezzo_acquisto": 9800, "cedola_annua_pct": 3.0,
          "anni_scadenza": 5, "frequenza_cedola": 2},
         {"totale_cedole_lordo": 1500.0, "imposta_cedole": 187.5, "plusvalenza_lorda": 200,
          "imposta_plusvalenza": 25.0, "guadagno_netto_totale": 1487.5,
          "rendimento_netto_annuo_pct": 3.0357}),
        # Sopra la pari: no tax on a negative difference (art. 2 D.Lgs. 239/1996 taxes proceeds).
        ({"valore_nominale": 10000, "prezzo_acquisto": 10300, "cedola_annua_pct": 4.0,
          "anni_scadenza": 3, "frequenza_cedola": 2},
         {"totale_cedole_netto": 1050.0, "imposta_plusvalenza": 0.0,
          "guadagno_netto_totale": 750.0, "rendimento_netto_annuo_pct": 2.4272}),
        # Alla pari, cedola annuale: 2,5 x 0,875 = 2,1875%.
        ({"valore_nominale": 1000, "prezzo_acquisto": 1000, "cedola_annua_pct": 2.5,
          "anni_scadenza": 10, "frequenza_cedola": 1},
         {"guadagno_netto_totale": 218.75, "rendimento_netto_annuo_pct": 2.1875}),
    ],
    ids=["sotto_la_pari", "sopra_la_pari", "alla_pari_annuale"],
)
def test_btp_casi_piano_aritmetica_e_tir(kwargs, atteso):
    r = _btp(**kwargs)
    for chiave, valore in atteso.items():
        tol = 0.0001 if chiave.endswith("_pct") else 0.01
        assert r[chiave] == pytest.approx(valore, abs=tol), chiave
    # INDICATIVO (declared): simple return instead of the IRR. Tolerance 0,05 percentage
    # points, motivated by that grade: it accepts the simple/compound gap near par
    # (measured 0,0008 / 0,0445 / 0 points on these cases), not a gap as large as the tax.
    tir = _tir_netto_btp(kwargs["valore_nominale"], kwargs["prezzo_acquisto"],
                         kwargs["cedola_annua_pct"], kwargs["anni_scadenza"],
                         kwargs["frequenza_cedola"])
    assert abs(r["rendimento_netto_annuo_pct"] - tir) <= 0.05, (r["rendimento_netto_annuo_pct"], tir)


def test_btp_frequenza_cedolare_nulla_errore():
    r = _btp(valore_nominale=1000, prezzo_acquisto=990, cedola_annua_pct=2.5,
             anni_scadenza=10, frequenza_cedola=0)
    assert "frequenza_cedola deve essere positiva" in r.get("errore", "")


# --- rendimento_btp: MEF auction results of 10 September 2026 --------------------------

_MEF = ("https://www.dt.mef.gov.it/export/sites/sitodt/modules/documenti_it/debito_pubblico/"
        "risultati_aste/")
# Values read on 2026-09-25 from the MEF PDFs below (the documents are immutable: the
# test re-reads them and fails if they ever change).
ASTE_MEF = {
    "btp_3y": {
        "url": _MEF + "risultati_aste_btp_3_anni/BTP-3-Anni-Risultati-Asta-10-11.09.2026.pdf",
        "isin": "IT0005716839", "cedola": 3.00, "prezzo": 98.86, "lordo": 3.43, "dietimi": 0,
        "regolamento": date(2026, 9, 15), "scadenza": date(2029, 9, 15),
    },
    "btp_7y": {
        "url": _MEF + "risultati_aste_btp_7_anni/BTP-7-Anni-Risultati-Asta-10-11.09.2026.pdf",
        "isin": "IT0005722845", "cedola": 3.35, "prezzo": 96.41, "lordo": 3.98, "dietimi": 0,
        "regolamento": date(2026, 9, 15), "scadenza": date(2033, 9, 15),
    },
    "btp_50y": {
        "url": _MEF + "risultati_aste_btp_50_anni/BTP-50-Anni-Risultati-Asta-10-11.09.2026.pdf",
        "isin": "IT0005441883", "cedola": 2.15, "prezzo": 53.94, "lordo": 4.61, "dietimi": 14,
        "regolamento": date(2026, 9, 15), "scadenza": date(2072, 3, 1),
    },
}


def _campo(testo: str, etichetta: str) -> str:
    m = re.search(rf"^\s*{re.escape(etichetta)}\S*\s+(.+?)\s*$", testo, re.M)
    assert m, f"campo '{etichetta}' assente dal prospetto MEF"
    return m.group(1)


def _leggi_asta(url: str) -> dict:
    t = _pdf_text(url)
    return {
        "isin": _campo(t, "Codice ISIN")[:12],
        "cedola": _num(_campo(t, "Cedola").rstrip("%")),
        "prezzo": _num(_campo(t, "Prezzo di Aggiudicazione")),
        "lordo": _num(_campo(t, "Rendimento Lordo").rstrip("%")),
        "dietimi": int(_campo(t, "Giorni dietimi")),
        "regolamento": _data_it(_campo(t, "Data Regolamento")),
        "scadenza": _data_it(_campo(t, "Data Scadenza")),
        "base_365": "Base Annua Rendimenti 365 gg" in t,
    }


def _flussi_asta(a: dict, netto: bool) -> list[tuple[float, float]]:
    """Semiannual flows from settlement to maturity, act/365 (the MEF 'base annua 365')."""
    t0, cedola = a["regolamento"], a["cedola"] / 2
    date_cedole, d = [], a["scadenza"]
    while d > t0:
        date_cedole.append(d)
        d = _add_months(d, -6)
    date_cedole.reverse()
    semestre = (date_cedole[0] - _add_months(date_cedole[0], -6)).days
    rateo = cedola * a["dietimi"] / semestre  # dietimi paid at settlement
    flussi = [(0.0, -(a["prezzo"] + rateo))]
    for i, dc in enumerate(date_cedole):
        c = cedola
        if netto:
            # art. 2 co. 1 D.Lgs. 239/1996: taxed "per la parte maturata nel periodo di possesso"
            c = cedola - (cedola - (rateo if i == 0 else 0.0)) * ALIQUOTA
        flussi.append(((dc - t0).days / 365, c))
    rimborso = 100.0 - ((100.0 - a["prezzo"]) * ALIQUOTA if netto else 0.0)
    flussi[-1] = (flussi[-1][0], flussi[-1][1] + rimborso)
    return flussi


@pytest.mark.parametrize("asta", list(ASTE_MEF), ids=list(ASTE_MEF))
def test_btp_asta_mef_10_settembre_2026(asta):
    atteso = ASTE_MEF[asta]
    letto = _leggi_asta(atteso["url"])
    for k in ("isin", "cedola", "prezzo", "lordo", "dietimi", "regolamento", "scadenza"):
        assert letto[k] == atteso[k], (k, letto[k], atteso[k])
    assert letto["base_365"]

    # 1) The method: gross IRR of the flows reproduces the MEF "Rendimento Lordo". Tolerance
    #    0,005 points because the MEF publishes two decimals.
    tir_lordo = _tir(_flussi_asta(letto, netto=False))
    assert abs(tir_lordo - letto["lordo"]) <= 0.005, (tir_lordo, letto["lordo"])

    # 2) The tool on the same bond. `anni_scadenza` is an int: the residual life is truncated
    #    to whole years (exact for 3y and 7y; 45,46 -> 45 for the 50y, dietimi not modelled).
    anni = (letto["scadenza"] - letto["regolamento"]).days // 365
    r = _btp(valore_nominale=100, prezzo_acquisto=letto["prezzo"],
             cedola_annua_pct=letto["cedola"], anni_scadenza=anni, frequenza_cedola=2)
    tool = r["rendimento_netto_annuo_pct"]
    tir_netto = _tir(_flussi_asta(letto, netto=True))
    # A net yield can never exceed the official gross yield of the same auction.
    assert tool < letto["lordo"], (
        f"{asta}: rendimento netto del tool {tool}% superiore al lordo MEF {letto['lordo']}% "
        f"(TIR netto {tir_netto:.4f}%)")
    # Same motivated tolerance as the plan cases (INDICATIVO: 0,05 percentage points).
    assert abs(tool - tir_netto) <= 0.05, (
        f"{asta}: tool {tool}% vs TIR netto {tir_netto:.4f}% (lordo MEF {letto['lordo']}%)")


# --- rendimento_buoni_postali: CDP/Poste fogli informativi -------------------------------

_POSTE = "https://buonielibretti.poste.it/buoni-fruttiferi-postali"


@functools.lru_cache(maxsize=None)
def _foglio_corrente(slug: str, documento: str = "Foglio Informativo") -> tuple[str, str, str]:
    """(serie, url, text) of the foglio informativo (or scheda di sintesi) linked from a
    poste.it product page: the page always links the series in placement."""
    soup = BeautifulSoup(_get(f"{_POSTE}/{slug}").text, "lxml")
    for a in soup.find_all("a", href=True):
        m = re.search(rf"{documento} Serie (T[FC]\d{{3}}A\d{{6}})", a.get_text(" ", strip=True), re.I)
        if m:
            return m.group(1), a["href"], _pdf_text(a["href"])
    pytest.fail(f"{_POSTE}/{slug}: nessun link a '{documento}'")


def _coefficienti_bimestrali(testo: str) -> dict[tuple[int, int], tuple[float, float]]:
    """Tabella B of the Buono ordinario: (anni, mesi) -> (coeff. lordo, coeff. netto)."""
    blocco = testo[testo.index("TABELLA B"):]
    return {(int(a), int(m)): (_num(lo), _num(ne)) for a, m, lo, ne in
            re.findall(r"(\d{1,2})\s+(\d{1,2})\s+(\d,\d{8})\s+(\d,\d{8})", blocco)}


def _coefficienti_annui(testo: str) -> dict[int, tuple[float, float]]:
    """Tabella A of the 3x4 con premio: anno -> (coeff. lordo, coeff. netto)."""
    blocco = testo[testo.index("Tabella A"):]
    return {int(a): (_num(lo), _num(ne)) for a, lo, ne in
            re.findall(r"^\s*(\d{1,2})\s+(\d,\d{8})\s+(\d,\d{8})\s*$", blocco, re.M)}


def test_bfp_aliquota_12_50_sui_coefficienti_netti_del_foglio_ordinario():
    """Every netto coefficient of the foglio is 1 + (lordo - 1) x 0,875: the 12,50% of
    D.Lgs. 239/1996 applied by the tool (imposta_sostitutiva_pct) matches the issuer."""
    serie, url, testo = _foglio_corrente("buono-ordinario/")
    coeff = _coefficienti_bimestrali(testo)
    assert len(coeff) == 121, (serie, len(coeff))  # 20 years x 6 bimesters + year 0
    for chiave, (lordo, netto) in coeff.items():
        assert netto == pytest.approx(1 + (lordo - 1) * (1 - ALIQUOTA), abs=2e-8), (serie, chiave)
    assert "12,50%" in testo
    assert _bfp(importo=1000, tipo="ordinario", anni=5)["imposta_sostitutiva_pct"] == 12.5


@pytest.mark.parametrize("anni", [1, 4, 10, 20])
def test_bfp_ordinario_montante_vs_foglio_informativo_cdp(anni):
    # Read on 2026-09-25: serie TF120A250624 (conditions from 24/06/2025, foglio of 24/07/2026)
    # https://www.media.poste.it/a9a92756-9cab-4690-b9fd-8085f5118386/file/fi-TF120A250624-240726
    # Tabella A, tasso nominale annuo lordo: 0,75% (1-4), 1,50 (5), 1,75 (6-7), 2,00 (8),
    # 2,25 (9), 2,50 (10-12), 3,00 (13), 3,40 (14), 3,50 (15-16), 4,00 (17-19), 5,00 (20).
    # Coefficients: 1a 1,0075/1,0065625; 4a 1,03033919/1,02654679; 10a 1,15745056/1,13776924;
    # 20a 1,63861891/1,55879154. The tool uses 0,50%...2,25% with no series reference.
    serie, url, testo = _foglio_corrente("buono-ordinario/")
    lordo, netto = _coefficienti_bimestrali(testo)[(anni, 0)]
    r = _bfp(importo=10000, tipo="ordinario", anni=anni)
    assert r["montante_lordo"] == pytest.approx(round(10000 * lordo, 2), abs=0.01), (serie, url)
    assert r["montante_netto"] == pytest.approx(round(10000 * netto, 2), abs=0.01), (serie, url)


def test_bfp_ordinario_durata_massima_venti_anni():
    serie, url, testo = _foglio_corrente("buono-ordinario/")
    assert "ventesimo anno" in testo, serie
    assert max(a for a, _ in _coefficienti_bimestrali(testo)) == 20
    assert _bfp(importo=10000, tipo="ordinario", anni=25)["anni"] == 20


def test_bfp_imposta_di_bollo_oltre_5000_euro_segnalata():
    """The foglio: esente from the imposta di bollo if the portfolio is <= 5.000 euro, above
    it 0,20% annuo (art. 13 co. 2-ter Tariffa DPR 642/1972, art. 19 D.L. 201/2011). The
    tool's 'montante_netto' for 10.000 euro neither applies nor mentions it."""
    serie, url, testo = _foglio_corrente("buono-ordinario/")
    assert "imposta di bollo" in testo and "5.000" in testo, serie
    sintesi = _foglio_corrente("buono-ordinario/", "Scheda di Sintesi")[2]
    assert re.search(r"0,20\s?%", sintesi), "aliquota del bollo assente dalla scheda di sintesi"
    r = _bfp(importo=10000, tipo="ordinario", anni=10)
    assert "bollo" in json.dumps(r, ensure_ascii=False).lower(), (
        "montante_netto senza imposta di bollo e senza avvertenza")


@pytest.mark.parametrize("anni, anni_riconosciuti", [(2, 0), (7, 6)])
def test_bfp_3x4_interessi_riconosciuti_solo_a_fine_triennio(anni, anni_riconosciuti):
    """Foglio 3x4 (con premio, in placement; same clause in the plain 3x4 series TF212A250211):
    'Gli interessi maturati nel corso del secondo triennio non sono corrisposti ... prima che
    siano trascorsi sei anni': the value at year 7 equals the value at year 6, and before year 3
    no interest is paid. The tool compounds every year, also inside the running triennio."""
    serie, url, testo = _foglio_corrente("buono-3x4-con-premio")
    coeff = _coefficienti_annui(testo)
    assert coeff[0] == (1.0, 1.0), serie
    assert coeff[anni] == coeff[anni_riconosciuti], (serie, coeff[anni], coeff[anni_riconosciuti])
    if anni_riconosciuti == 0:
        atteso = 5000.0
    else:
        atteso = _bfp(importo=5000, tipo="3x4", anni=anni_riconosciuti)["montante_lordo"]
    r = _bfp(importo=5000, tipo="3x4", anni=anni)
    assert r["montante_lordo"] == pytest.approx(atteso, abs=0.01), (serie, r["montante_lordo"])


# Last plain Buono 3x4: serie TF212A250211, conditions from 11/02/2025, in placement until
# 07/04/2026 (poste.it storico). Scheda di sintesi read on 2026-09-25:
# https://www.media.poste.it/7bcee125-d082-4d1a-a3fd-aa217f51a6ac/file/buoni-3x4-scheda-sintesi-TF212A250211-240625
# Tasso effettivo di rendimento annuo lordo: 3a 1,00%; 6a 1,50%; 9a 2,25%; 12a 3,00%.
TF212A250211 = {3: 1.00, 6: 1.50, 9: 2.25, 12: 3.00}
# Last Buono 4x4: serie TF116A221027, 27/10/2022 - 05/06/2023. Scheda di sintesi read on 2026-09-25:
# https://www.media.poste.it/ce788c0d-435e-4af9-907e-4b41a4a7b5f8/web/buoni-4x4-scheda-sintesi-tf116a221027
# Tasso effettivo annuo lordo: 4a 1,50%; 8a 2,00%; 12a 2,25%; 16a 3,00%; interest recognised
# only at the end of each quadriennio.
TF116A221027 = {4: 1.50, 8: 2.00, 12: 2.25, 16: 3.00}


@pytest.mark.parametrize(
    "tipo, storico, ultima_serie, tassi",
    [("3x4", "storico-buono-3x4", "TF212A250211", TF212A250211),
     ("4x4", "storico-buono-4x4", "TF116A221027", TF116A221027)],
    ids=["3x4", "4x4"],
)
def test_bfp_prodotti_non_piu_in_emissione_vs_ultima_serie(tipo, storico, ultima_serie, tassi):
    pagina = _get(f"{_POSTE}/{storico}").text
    titolo = BeautifulSoup(pagina, "lxml").title.get_text(strip=True)
    assert "non più in emissione" in titolo, titolo
    assert ultima_serie in pagina
    importo = 5000
    for anni, tasso in tassi.items():
        atteso = round(importo * (1 + tasso / 100) ** anni, 2)
        r = _bfp(importo=importo, tipo=tipo, anni=anni)
        assert r["montante_lordo"] == pytest.approx(atteso, abs=0.01), (
            f"{tipo} {anni} anni: tool {r['montante_lordo']} vs serie {ultima_serie} {atteso}")


def test_bfp_dedicato_minori_vs_foglio_informativo_cdp():
    # Read on 2026-09-25: serie TF118A260922 (from 22/09/2026, G.U. n. 220)
    # https://www.media.poste.it/67c59348-98ad-4eb7-aca9-455146fb5e7a/file/fi-TF118A260922
    # 5,00% annuo effettivo lordo a scadenza (18th birthday) for every age; 0,50% nominal on
    # early redemption. Newborn subscriber (18 years): coefficient 2,38712870 / 2,21373761.
    # The tool: 1,50% -> 3,50% by 4-year brackets.
    serie, url, testo = _foglio_corrente("buono-minori")
    m = re.search(r"N\.A\.\s*\(4\)\s+(\d,\d{8})\s+(\d,\d{8})\s+(\d+,\d{2})%", testo)
    assert m, serie
    lordo, netto, tasso = _num(m.group(1)), _num(m.group(2)), _num(m.group(3))
    r = _bfp(importo=1000, tipo="dedicato_minori", anni=18)
    assert r["anni"] == 18
    assert r["montante_lordo"] == pytest.approx(round(1000 * lordo, 2), abs=0.01), (
        f"{serie}: tasso a scadenza {tasso}%, tool {r['montante_lordo']} vs {round(1000 * lordo, 2)}")
    assert r["montante_netto"] == pytest.approx(round(1000 * netto, 2), abs=0.01), serie


def test_bfp_tipo_non_ammesso_errore():
    r = _bfp(importo=10000, tipo="inesistente", anni=5)
    assert "tipo non valido" in r.get("errore", "")

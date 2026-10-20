"""Benchmark interessi_acconti vs avvocatoandreani.it/servizi/calcolo-interessi-acconti.php.

Norma: art. 1284 c.c. (tassi legali per anno); art. 1194 c.c. (imputazione
dei pagamenti: prima gli interessi, poi il capitale).

Convenzioni: il sito ha per default la spunta "Art. 1194 c.c." (acconto imputato
prima agli interessi maturati); il tool imputa SEMPRE al capitale. Il confronto
diretto e' quindi fatto con la spunta TOLTA (`test_*_capitale`); i test `*_1194`
registrano la distanza dal default del sito (imputazione art. 1194).
Tolleranza: 0,01 euro (brief). Il sito e' un benchmark, non una fonte.
"""

import os

os.environ.setdefault("LEGAL_TODAY", "2026-09-25")

import re
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import src.server  # noqa: F401,E402
from src.tools.tassi_interessi import interessi_acconti  # noqa: E402

from tests.comparison.conftest import accept_cookies, assert_close  # noqa: E402

_fn = getattr(interessi_acconti, "fn", interessi_acconti)
URL = "https://www.avvocatoandreani.it/servizi/calcolo-interessi-acconti.php"


def _euro(text, label, required=True):
    m = re.search(re.escape(label) + r"\s*:?\s*€\s*([\d\.]+,\d{2})", text)
    if not m and not required:
        return None
    assert m, f"etichetta non trovata: {label!r}"
    return float(m.group(1).replace(".", "").replace(",", "."))


def _sito(page, capitale, inizio, fine, acconti, art_1194):
    page.goto(URL, timeout=60000, wait_until="domcontentloaded")
    accept_cookies(page)
    page.fill("input[name='Capitale']", f"{capitale:.2f}".replace(".", ","))
    for pre, d in (("Inizio", inizio), ("Fine", fine)):
        y, m, dd = d.split("-")
        page.select_option(f"select[name='Giorno{pre}']", dd)
        page.select_option(f"select[name='Mese{pre}']", m)
        page.select_option(f"select[name='Anno{pre}']", y)
    page.select_option("select[name='TipInt']", "1")  # al tasso legale
    # la spunta ha onclick="return false": un click non la modifica, si imposta via DOM
    page.evaluate("v => { document.getElementById('ApplicaCC').checked = v; }", art_1194)
    for k, a in enumerate(acconti):
        if k > 0:  # "Nuova riga (acconto/credito)" aggiunge la riga k
            page.click("#I-Tip-1", force=True)
            page.wait_for_timeout(500)
        y, m, dd = a["data"].split("-")
        page.select_option(f"select[name='TipoMovimento-{k}']", "2")  # acconto
        page.select_option(f"select[name='GiornoMovimento-{k}']", dd)
        page.select_option(f"select[name='MeseMovimento-{k}']", m)
        page.select_option(f"select[name='AnnoMovimento-{k}']", y)
        page.fill(f"input[name='ImportoMovimento-{k}']", f"{a['importo']:.2f}".replace(".", ","))
    page.click("form#Intacc input[type=submit]", force=True)
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(3000)
    txt = page.inner_text("body")
    err = page.evaluate(
        "[...document.querySelectorAll('[class*=ferror]')].map(e => e.innerText).join(' | ')"
    )
    if "supera il credito totale" in err:
        pytest.skip("il sito rifiuta l'input: " + err)
    assert "Totale interessi legali" in txt, "il sito non ha calcolato: " + txt[-600:]
    return {
        "interessi": _euro(txt, "Totale interessi legali"),
        "residuo": _euro(txt, "Credito residuo", required=False),
        "interessi_residui": _euro(txt, "Interessi residui", required=False),
        "dovuto": _euro(txt, "Credito + interessi residui"),
        "acconti": _euro(txt, "Totale acconti versati", required=False),
    }


def _confronta(page, capitale, inizio, fine, acconti, art_1194, campi):
    # The tool now imputes per art. 1194 c.c. by default (interest first); the site's unchecked
    # box corresponds to imputation to capital (creditor's consent).
    t = _fn(capitale=capitale, data_inizio=inizio, acconti=acconti, data_fine=fine,
            imputazione="interessi" if art_1194 else "capitale")
    assert "errore" not in t, t
    s = _sito(page, capitale, inizio, fine, acconti, art_1194)
    tv = {
        "interessi": t["totale_interessi"],
        "residuo": t["capitale_residuo_finale"],
        "dovuto": t["totale_dovuto"],
        "interessi_residui": t["totale_interessi"],
    }
    print("TOOL", tv, "SITO", s)
    for c in campi:
        # 0,01 euro + 1e-9: `abs(148.41 - 148.40)` vale 0.010000000000218 in floating point,
        # quindi una differenza di UN centesimo (il sito arrotonda per periodo) non sarebbe
        # accettata dalla tolleranza nominale di 0,01.
        assert_close(tv[c], s[c], 0.01 + 1e-9, c)


# Per l'imputazione al capitale il sito riporta gli interessi in "Interessi residui"
# solo con la spunta 1194; qui si confrontano gli interessi totali e il dovuto.
_CAP = ("interessi", "dovuto")
_1194 = ("dovuto",)

A1 = dict(capitale=10000, inizio="2023-01-01", fine="2024-01-01",
          acconti=[{"data": "2023-07-01", "importo": 5000}])
A2 = dict(capitale=10000, inizio="2025-01-01", fine="2025-12-31",
          acconti=[{"data": "2025-12-31", "importo": 2000}])
A3 = dict(capitale=10000, inizio="2025-06-30", fine="2026-06-30",
          acconti=[{"data": "2025-10-01", "importo": 2000}, {"data": "2026-02-15", "importo": 1000}])
A4 = dict(capitale=20000, inizio="2023-06-15", fine="2024-08-20",
          acconti=[{"data": "2024-02-29", "importo": 3000}])
A5 = dict(capitale=10000, inizio="2023-01-01", fine="2024-06-30",
          acconti=[{"data": "2023-12-31", "importo": 4000}, {"data": "2024-01-01", "importo": 1000}])
A6 = dict(capitale=3000, inizio="2024-03-01", fine="2024-12-31",
          acconti=[{"data": "2024-08-15", "importo": 4000}])
A7 = dict(capitale=15000, inizio="2024-07-20", fine="2024-09-10",
          acconti=[{"data": "2024-08-15", "importo": 6000}])


# Piano caso 1: art. 1194 -> interessi 247,95 + 131,92, dovuto 5.379,86 (sito con spunta);
# imputazione al capitale: interessi 373,63, dovuto 5.373,63 (tool).
def test_un_acconto_capitale(page):
    _confronta(page, **A1, art_1194=False, campi=_CAP)


def test_un_acconto_1194(page):
    _confronta(page, **A1, art_1194=True, campi=_1194)


# Piano caso 2 (limite): acconto nella data finale. Atteso 1194: interessi 199,45 (364 gg al 2%),
# dovuto 8.199,45; il tool non riduce il capitale e da' 10.199,45.
def test_acconto_data_finale_capitale(page):
    _confronta(page, **A2, art_1194=False, campi=_CAP)


def test_acconto_data_finale_1194(page):
    _confronta(page, **A2, art_1194=True, campi=_1194)


# Piano caso 3 (limite: cambio tasso 2025-2026): capitale: interessi 148,41, dovuto 7.148,41;
# art. 1194: residuo 7.107,34, interessi residui 42,06, dovuto 7.149,40.
def test_due_acconti_cambio_tasso_capitale(page):
    _confronta(page, **A3, art_1194=False, campi=_CAP)


def test_due_acconti_cambio_tasso_1194(page):
    _confronta(page, **A3, art_1194=True, campi=_1194)


# Limite: anno bisestile 2024 (divisore 365/366), acconto il 29 febbraio, tasso 5% -> 2,5%.
def test_bisestile_acconto_29_febbraio_capitale(page):
    _confronta(page, **A4, art_1194=False, campi=_CAP)


# Limite: acconti a cavallo del cambio d'anno (31/12 e 01/01), tasso 5% -> 2,5%.
def test_acconti_cambio_anno_capitale(page):
    _confronta(page, **A5, art_1194=False, campi=_CAP)


# Limite: acconto (4.000) superiore al residuo (3.000): both the site (validation message)
# and the tool (errore) refuse the input; the tool no longer drops the excess silently.
def test_acconto_superiore_al_capitale(page):
    t = _fn(capitale=3000, data_inizio="2024-03-01", data_fine="2024-12-31",
            acconti=[{"data": "2024-08-15", "importo": 4000}], imputazione="capitale")
    assert "errore" in t


# Limite: periodo a cavallo di agosto (2024, bisestile, tasso 2,5%), acconto il 15 agosto.
def test_agosto_bisestile_capitale(page):
    _confronta(page, **A7, art_1194=False, campi=_CAP)

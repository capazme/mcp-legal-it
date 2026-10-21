"""Benchmark termini_deposito_ctu vs avvocatoandreani.it/servizi/calcolo-termini-deposito-ctu.php.

Norma: art. 195 co. 3 c.p.c. (D.Lgs. 149/2022), termini fissati dal giudice (art. 193);
sospensione feriale L. 742/1969; proroga art. 155 c.p.c.
Il sito usa come data iniziale l'inizio delle operazioni peritali, il tool il conferimento:
stesso calcolo. Date esatte (nessuna tolleranza).
"""
import os
import re
import sys
from datetime import date

import pytest

os.environ.setdefault("LEGAL_TODAY", "2026-09-25")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import src.server  # noqa: F401,E402
from src.tools.scadenze_termini import termini_deposito_ctu  # noqa: E402

from .conftest import accept_cookies  # noqa: E402

fn = getattr(termini_deposito_ctu, "fn", termini_deposito_ctu)
URL = "https://www.avvocatoandreani.it/servizi/calcolo-termini-deposito-ctu.php"
MESI = {m: i + 1 for i, m in enumerate(
    "gennaio febbraio marzo aprile maggio giugno luglio agosto settembre ottobre novembre dicembre".split())}


def _sito(page, conferimento, t1=60, t2=15, t3=15, feriale=True):
    y, m, d = conferimento.split("-")
    page.goto(URL, timeout=60000, wait_until="domcontentloaded")
    accept_cookies(page)
    page.select_option("#GiornoInizio", d)
    page.select_option("#MeseInizio", m)
    page.select_option("#AnnoInizio", y)
    page.fill("#Termine1", str(t1))
    page.fill("#Termine2", str(t2))
    page.fill("#Termine3", str(t3))
    cb = page.locator("#SospensioneFeriale")
    if cb.is_checked() != feriale:
        cb.set_checked(feriale, force=True)
    page.click("#btn-calc", force=True)
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(2500)
    txt = page.inner_text("body")
    found = re.findall(r"entro:\s*\w+\s+(\d+)\s+(\w+)\s+(\d{4})", txt)
    assert len(found) >= 3, f"risultato non leggibile: {txt[:400]}"
    out = [date(int(a), MESI[me.lower()], int(g)).isoformat() for g, me, a in found[:3]]
    page.wait_for_timeout(1500)
    return out


def _tool(conferimento, t1=60, t2=15, t3=15, feriale=True):
    r = fn(data_conferimento=conferimento, giorni_termine=t1, giorni_osservazioni=t2,
           giorni_replica=t3, sospensione_feriale=feriale)
    assert "errore" not in r, r
    return [s["scadenza"] if "scadenza" in s else s["data"] for s in r["scadenze"]]


def _confronta(page, conf, **kw):
    t = _tool(conf, **kw)
    s = _sito(page, conf, **kw)
    assert t == s, f"tool={t} sito={s}"


def test_prassi_60_15_15_senza_agosto(page):
    # Piano: 2025-06-30, 2025-07-15, 2025-07-30 (art. 195 co. 3 c.p.c.)
    _confronta(page, "2025-05-01")


def test_luglio_con_sospensione_feriale(page):
    # Piano: 2025-09-30, 2025-10-15, 2025-10-30 (agosto escluso, L. 742/1969). Limite: agosto.
    _confronta(page, "2025-07-01")


def test_luglio_senza_sospensione_weekend(page):
    # Piano: 2025-09-01 (30/8 sabato), 2025-09-15 (14/9 domenica), 2025-09-29; termini dalle scadenze non prorogate. Limite.
    _confronta(page, "2025-07-01", feriale=False)


def test_primo_termine_2_giugno(page):
    # Piano: 2025-06-03; osservazioni 06-17 (tool, da scadenza non prorogata) o 06-18. Limite: festivo.
    _confronta(page, "2025-04-03")


def test_giorni_personalizzati(page):
    # Piano: 2025-10-09, 2025-10-29, 2025-11-10 (8/11 sabato)
    _confronta(page, "2025-06-10", t1=90, t2=20, t3=10)


def test_conferimento_31_luglio_agosto(page):
    # Limite: conferimento a fine luglio, termini che attraversano agosto.
    _confronta(page, "2025-07-31", t1=30, t2=15, t3=15)


def test_anno_2026_default_sito(page):
    # Limite: anno diverso (2026), 20/15/15 come default del sito.
    _confronta(page, "2026-09-25", t1=20)


# CONVENTION (phase 2-3): the two failing cases differ only in the dies a quo of the follow-up
# terms. The tool counts observations and reply from the unextended deadline, the site from the
# extended one. Art. 195 co. 3 c.p.c. leaves the terms to the judge's order (art. 193), and art.
# 155 co. 4-5 extends only the deadline itself, so both readings are defensible: no change.

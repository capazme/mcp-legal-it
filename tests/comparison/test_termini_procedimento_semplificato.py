"""Benchmark termini_procedimento_semplificato vs avvocatoandreani.it.

Il sito calcola SOLO i termini in avanti dall'udienza (memoria integrativa e
replica, art. 281-duodecies c.p.c.); non calcola i termini a ritroso (notifica
del ricorso 40/60 giorni liberi, costituzione del convenuto 10 giorni prima,
art. 281-undecies): quelli non sono confrontabili.

Convenzione: il tool conta la replica dal termine della memoria NON prorogato
(art. 155 c.p.c. non applicato al termine intermedio) = "modalita' prudenziale"
del sito. Per questo i confronti usano prudenziale=True; un test dedicato
verifica anche la modalita' non prudenziale, dove i due possono divergere.
"""

import json
import os
import re
import sys

os.environ["LEGAL_TODAY"] = "2026-09-25"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest

import src.server  # noqa: F401
from src.tools.scadenze_termini import termini_procedimento_semplificato

from .conftest import accept_cookies

_fn = getattr(termini_procedimento_semplificato, "fn", termini_procedimento_semplificato)

URL = "https://www.avvocatoandreani.it/servizi/calcolo-termini-procedimento-semplificato.php"
MESI = {
    "gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4, "maggio": 5, "giugno": 6,
    "luglio": 7, "agosto": 8, "settembre": 9, "ottobre": 10, "novembre": 11, "dicembre": 12,
}


def _iso(giorno, mese, anno):
    return f"{int(anno):04d}-{MESI[mese.lower()]:02d}-{int(giorno):02d}"


def _sito(page, udienza, t1=20, t2=10, feriale=True, prudenziale=False):
    y, m, d = udienza.split("-")
    page.goto(URL, timeout=60000, wait_until="domcontentloaded")
    accept_cookies(page)
    page.select_option("select[name=GiornoInizio]", d)
    page.select_option("select[name=MeseInizio]", m)
    page.select_option("select[name=AnnoInizio]", y)
    page.select_option("select[name=Termine1]", str(t1))
    page.select_option("select[name=Termine2]", str(t2))
    page.set_checked("input[name=SospensioneFeriale]", feriale, force=True)
    page.set_checked("input[name=Prudenziale]", prudenziale, force=True)
    page.click("form input[type=submit]", force=True)
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(2500)
    text = page.inner_text("body")
    pat = r"{}[^\n]*\n\([^)]*\)\s*\n\s*\w+\s+(\d{{1,2}})\s+(\w+)\s+(\d{{4}})"
    out = []
    for label in ("Termine per precisare", "Termine per replicare"):
        mt = re.search(pat.format(label), text)
        assert mt, f"risultato non leggibile per '{label}'"
        out.append(_iso(*mt.groups()))
    return tuple(out)


def _tool(udienza, gm=20, gr=10, feriale=True):
    r = _fn(data_udienza=udienza, giorni_memoria=gm, giorni_replica=gr, sospensione_feriale=feriale)
    assert "errore" not in r, r
    s = {x["termine"]: x["scadenza"] for x in r["scadenze"]}
    return s["memoria_integrativa"], s["replica_prova_contraria"]


def _confronta(page, udienza, gm=20, gr=10, feriale=True, prudenziale=True):
    t = _tool(udienza, gm, gr, feriale)
    s = _sito(page, udienza, gm, gr, feriale, prudenziale)
    assert t == s, f"tool={t} sito={s} input={json.dumps(dict(u=udienza, gm=gm, gr=gr, fer=feriale, prud=prudenziale))}"


def test_udienza_ottobre_con_sospensione(page):
    # Piano: memoria 2025-10-21, replica 2025-10-31 (20+10 giorni, art. 281-duodecies).
    assert _tool("2025-10-01") == ("2025-10-21", "2025-10-31")
    _confronta(page, "2025-10-01")


def test_udienza_ottobre_senza_sospensione(page):
    # Piano: stesse date senza sospensione feriale (agosto non interessa).
    assert _tool("2025-10-01", feriale=False) == ("2025-10-21", "2025-10-31")
    _confronta(page, "2025-10-01", feriale=False)


def test_luglio_memorie_attraversano_agosto(page):
    # LIMITE. Piano: memoria 2025-09-11 (9 gg luglio + 11 settembre), replica 2025-09-22
    # (21 settembre domenica, proroga art. 155 c.p.c.). Sospensione feriale L. 742/1969.
    assert _tool("2025-07-22") == ("2025-09-11", "2025-09-22")
    _confronta(page, "2025-07-22")


def test_luglio_senza_sospensione_feriale(page):
    # LIMITE. Stessa udienza senza sospensione: agosto si conta (memoria 11 agosto, replica 21 agosto).
    _confronta(page, "2025-07-22", feriale=False)


def test_memoria_su_sabato_prorogata_replica_dal_termine_non_prorogato(page):
    # LIMITE. Udienza 2025-10-05: memoria 25 ottobre (sabato) -> lunedi' 27 (art. 155 co. 5).
    # Replica: il tool conta i 10 giorni dal 25 (non prorogato) = 4 novembre.
    # Modalita' prudenziale del sito = stesso criterio.
    assert _tool("2025-10-05") == ("2025-10-27", "2025-11-04")
    _confronta(page, "2025-10-05", prudenziale=True)


def test_memoria_su_sabato_modalita_non_prudenziale(page):
    # LIMITE. Stessa data, modalita' non prudenziale del sito: replica contata dal 27 ottobre
    # (termine prorogato) = 6 novembre; il tool da' 4 novembre (criterio prudenziale:
    # scelta di convenzione sul termine intermedio). Scostamento genuino, lasciato fallire.
    _confronta(page, "2025-10-05", prudenziale=False)


def test_fine_anno_cambio_anno(page):
    # LIMITE. Udienza 2025-12-15: memoria 4 gennaio 2026 (domenica) -> 5 gennaio; replica dal 4/1 = 14 gennaio.
    _confronta(page, "2025-12-15")


def test_udienza_fine_luglio_sospensione_agosto(page):
    # LIMITE. Udienza 2025-07-30: il 20 gg conta 1 giorno a luglio, poi sospensione, restanti a settembre.
    _confronta(page, "2025-07-30")


def test_termini_ridotti_concessi_dal_giudice(page):
    # Memoria 15 giorni e replica 5 giorni (massimi 20/10, il giudice puo' concedere meno).
    _confronta(page, "2026-03-10", gm=15, gr=5)


def test_notifica_e_costituzione_a_ritroso_non_confrontabili():
    # Piano: notifica_ricorso_italia 2025-07-21 (40 gg liberi), estero 2025-07-01 (60),
    # costituzione 2025-09-19 (10 gg prima). Il sito non calcola i termini a ritroso.
    r = _tool("2025-10-01")
    assert r
    pytest.skip("il sito calcola solo memoria integrativa e replica; i termini a ritroso (art. 281-undecies) non sono offerti")


def test_memoria_oltre_massimo_errore_tool():
    # Piano: giorni_memoria=21 -> errore (max 20, art. 281-duodecies). Il sito non offre valori > 20.
    r = _fn(data_udienza="2025-10-01", giorni_memoria=21)
    assert "errore" in r
    pytest.skip("il sito limita Termine1 a 1-20: rifiuto non confrontabile, verificato solo sul tool")


# CONVENTION (phase 2-3): art. 281-duodecies co. 4 gives the reply term as "ulteriore" without
# saying whether it runs from the extended memoria deadline. The tool counts from the unextended
# one (the site's prudential mode); the site's other mode counts from the extended one. Both
# defensible: no change. Comma references were checked on Normattiva (10 days: 281-undecies
# co. 2; 20+10 days: 281-duodecies co. 4).

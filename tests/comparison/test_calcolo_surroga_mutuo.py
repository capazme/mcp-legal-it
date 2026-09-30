# FASE 3 (verdetto: convenzione). The new loan (rata, interessi) matches the site to the cent. The gap
# (up to ~1 euro on 239 rates) is on the OLD loan: the tool takes the rata actually paid, rounded to the
# cent (rata_attuale x mesi - residuo), the site rebuilds it from the original loan with the unrounded
# instalment. Both defensible; no statutory formula fixes it (art. 120-quater TUB gives no calculation
# rule). The 0,01 euro tolerance therefore cannot hold on the residual-interest and total-saving lines.
"""Benchmark calcolo_surroga_mutuo vs avvocatoandreani.it/servizi/calcolo-surroga-mutuo.php

Norma: art. 120-quater TUB (surroga per volonta' del debitore); DL 7/2007 conv. L. 40/2007;
art. 1202 c.c. Ammortamento alla francese a rata costante.

Convenzione del sito: si inseriscono i dati del mutuo ORIGINARIO (mese di stipula,
capitale, tasso, durata) e quelli della surroga (mese, nuovo tasso, durata "Residua").
Il sito ricostruisce da solo capitale residuo, rata e durata residua; il tool invece
riceve gia' il residuo. Il test quindi guida il sito, legge dalla sezione "Situazione del
mutuo" il capitale residuo / la rata / i mesi residui, li passa al tool e confronta
rata nuova, interessi del nuovo mutuo, interessi residui del vecchio, risparmio di rata
e risparmio complessivo degli interessi.
"""

import os

os.environ.setdefault("LEGAL_TODAY", "2026-09-25")

import re
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
import src.server  # noqa: F401,E402
from src.tools.tassi_interessi import calcolo_surroga_mutuo  # noqa: E402

from tests.comparison.conftest import accept_cookies, parse_euro, assert_close  # noqa: E402

_tool = getattr(calcolo_surroga_mutuo, "fn", calcolo_surroga_mutuo)

URL = "https://www.avvocatoandreani.it/servizi/calcolo-surroga-mutuo.php"
TOL = 0.01


def _eur(sec, label):
    m = re.search(re.escape(label) + r"\s*\n?\s*€\s*([\d\.]+,\d{2})", sec)
    assert m, f"etichetta non trovata: {label!r}"
    return parse_euro(m.group(1))


def _site(page, mese_ini, anno_ini, capitale, tasso, anni, mese_sur, anno_sur, tasso_sur):
    page.goto(URL, timeout=60000, wait_until="domcontentloaded")
    page.wait_for_timeout(1500)
    accept_cookies(page)
    page.select_option("select[name='MeseInizio']", mese_ini)
    page.select_option("select[name='AnnoInizio']", str(anno_ini))
    page.fill("input[name='Capitale']", str(capitale))
    page.fill("input[name='Tasso']", str(tasso).replace(".", ","))
    page.select_option("select[name='DurataAnni']", str(anni))
    page.select_option("select[name='MeseSurroga']", mese_sur)
    page.select_option("select[name='AnnoSurroga']", str(anno_sur))
    page.fill("input[name='TassoSurroga']", str(tasso_sur).replace(".", ","))
    page.select_option("select[name='DurataAnniSurroga']", "0")
    page.click("#btn-calc", force=True)
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(3000)
    txt = page.inner_text("body")
    if "Simulazione Calcolo Surroga" not in txt:
        return None
    a = txt.index("Situazione del mutuo")
    b = txt.index("Nuovo mutuo con l'operazione di surroga")
    c = txt.index("Valutazione Finale")
    old, new, fin = txt[a:b], txt[b:c], txt[c:]
    mesi = int(re.search(r"\((\d+)\s*rate mensili\)", new).group(1))
    rata_att = _eur(txt[:a], "Importo rata del mutuo:")
    res = {
        "capitale_residuo": _eur(old, "Capitale residuo:"),
        "rata_attuale": rata_att,
        "mesi_residui": mesi,
        "interessi_residui_attuali": _eur(old, "Interessi residui:"),
        "interessi_nuovi": _eur(new, "Interessi:"),
        "rata_nuova": _eur(new, "Importo nuova rata:"),
    }
    m = re.search(r"(più bassa|più alta) di\s*€\s*([\d\.]+,\d{2})", fin)
    r = parse_euro(m.group(2))
    res["risparmio_rata"] = r if m.group(1) == "più bassa" else -r
    m = re.search(r"(risparmi complessivamente|aumenteranno di)\s*€\s*([\d\.]+,\d{2})", fin)
    r = parse_euro(m.group(2))
    res["risparmio_totale"] = r if m.group(1).startswith("risparmi") else -r
    return res


def _confronta(page, mese_ini, anno_ini, capitale, tasso, anni, mese_sur, anno_sur, tasso_sur):
    s = _site(page, mese_ini, anno_ini, capitale, tasso, anni, mese_sur, anno_sur, tasso_sur)
    if s is None:
        pytest.skip("il sito non produce il calcolo per questi parametri")
    t = _tool(
        debito_residuo=s["capitale_residuo"],
        rata_attuale=s["rata_attuale"],
        tasso_attuale=float(str(tasso).replace(",", ".")),
        tasso_nuovo=float(str(tasso_sur).replace(",", ".")),
        mesi_residui=s["mesi_residui"],
    )
    assert "errore" not in t, t
    pairs = [
        ("rata nuova", t["mutuo_surrogato"]["rata_mensile"], s["rata_nuova"]),
        ("interessi nuovo mutuo", t["mutuo_surrogato"]["interessi_residui"], s["interessi_nuovi"]),
        ("interessi residui attuali", t["mutuo_attuale"]["interessi_residui"], s["interessi_residui_attuali"]),
        ("risparmio rata", t["risparmio_rata_mensile"], s["risparmio_rata"]),
        ("risparmio totale interessi", t["risparmio_totale_interessi"], s["risparmio_totale"]),
    ]
    falliti = []
    for label, tv, sv in pairs:
        try:
            assert_close(tv, sv, TOL, label)
        except AssertionError as e:
            falliti.append(f"{label}: tool={tv} sito={sv} diff={round(tv - sv, 2)}")
    assert not falliti, "; ".join(falliti)


def test_piano_1_surroga_conveniente(page):
    # Piano: 150.000 / 4,5% / 240 mesi -> 3%: rata 831,90; risparmio mensile 117,07;
    # risparmio totale 28.097,66 (art. 120-quater TUB). Il sito esige che la stipula
    # preceda la surroga, quindi si usa un mutuo 20 anni stipulato 09/2016 con surroga
    # 09/2026 (120 rate residue, 10 anni): stessa formula, residuo ricostruito dal sito.
    _confronta(page, "09", 2016, 150000, "4,5", 20, "09", 2026, "3")


def test_piano_2_tasso_nuovo_zero(page):
    # Piano: tasso nuovo 0 -> rata = residuo/mesi, interessi 0 (art. 120-quater TUB).
    # Il sito non calcola con nuovo tasso 0: se rifiuta, caso non confrontabile.
    s = _site(page, "08", 2016, 60000, "3", 20, "09", 2026, "0")
    if s is None:
        pytest.skip("il sito rifiuta il nuovo tasso 0 (nessun risultato)")
    t = _tool(s["capitale_residuo"], s["rata_attuale"], 3.0, 0.0, s["mesi_residui"])
    assert_close(t["mutuo_surrogato"]["rata_mensile"], s["rata_nuova"], TOL, "rata nuova")


def test_limite_tasso_nuovo_minimo_0_01(page):
    # Limite: tasso nuovo 0,01% (il piu' vicino a zero che il sito accetta). Atteso: rata
    # ~ residuo/mesi, interessi quasi nulli (formula della rata costante).
    _confronta(page, "08", 2016, 60000, "3", 20, "09", 2026, "0,01")


def test_piano_3_rata_incoerente():
    # Piano: rata 500 incoerente col tasso 2% su 120 mesi (920,13): atteso errore/avviso;
    # il tool restituisce interessi residui negativi. Il sito ricostruisce la rata da solo,
    # quindi non ammette una rata incoerente: caso non confrontabile.
    pytest.skip("il sito calcola la rata dai dati originari: non accetta una rata incoerente")


def test_limite_surroga_non_conveniente_agosto(page):
    # Limite: nuovo tasso (3,5%) superiore al vecchio (2%), surroga ad agosto 2026 su un
    # mutuo 30 anni stipulato 03/2019. Atteso: rata piu' alta, interessi in aumento
    # (segni negativi), art. 120-quater TUB.
    _confronta(page, "03", 2019, 200000, "2", 30, "08", 2026, "3,5")


def test_limite_mutuo_lungo_anno_2006(page):
    # Limite: mutuo 30 anni del 2006 (241 rate pagate, 119 residue, durata non multipla
    # di 12), tasso 5,75% -> 2,9% ad agosto 2026. Formula francese.
    _confronta(page, "07", 2006, 180000, "5,75", 30, "08", 2026, "2,9")


def test_limite_prima_rata_appena_pagata(page):
    # Limite: surroga al mese successivo alla stipula (1 rata pagata, 239 residue).
    _confronta(page, "08", 2026, 150000, "4,5", 20, "09", 2026, "3")

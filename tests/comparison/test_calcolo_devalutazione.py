"""Comparison: calcolo_devalutazione vs avvocatoandreani.it (calcolo_devalutazione_monetaria.php).

Norma/fonte: indici FOI ISTAT (senza tabacchi), base 2015=100 raccordata; dal 2026
base 2025=100 con coefficiente di raccordo 1,214. La devalutazione e' il reciproco
della rivalutazione per la stessa coppia di mesi (calcolo su base mensile).

Site form: "Dal" = MeseFine/AnnoFine (mese dell'importo attuale),
"Al" = MeseInizio/AnnoInizio (mese passato). The submit button does not
navigate under Playwright, so the form is submitted via JS (same approach as
test_eredita.py / test_irpef.py).
Tolerance: 0,01 EUR on amounts (brief). No wider tolerance is used.
"""

import os
import re

os.environ.setdefault("LEGAL_TODAY", "2026-09-25")

import pytest

import src.server  # noqa: F401  (registers every tool module)
from src.tools.rivalutazioni_istat import calcolo_devalutazione as _tool

from tests.comparison.conftest import accept_cookies, assert_close, parse_euro

URL = "https://www.avvocatoandreani.it/servizi/calcolo_devalutazione_monetaria.php"
_fn = getattr(_tool, "fn", _tool)


def _site(page, importo: str, mese_att: int, anno_att: int, mese_pass: int, anno_pass: int) -> dict:
    page.goto(URL, timeout=60000, wait_until="domcontentloaded")
    accept_cookies(page)
    page.wait_for_timeout(1500)
    # Set the values via JS: the site's auto-advance handlers on the 2-digit month
    # fields can wipe the year field when Playwright types into them in sequence.
    values = {
        "Capitale": importo,
        "MeseFine": f"{mese_att:02d}",
        "AnnoFine": str(anno_att),
        "MeseInizio": f"{mese_pass:02d}",
        "AnnoInizio": str(anno_pass),
    }
    page.evaluate(
        """(v) => {const f = document.forms['Devalutazione'];
        for (const [k, x] of Object.entries(v)) { f.elements[k].value = x; }}""",
        values,
    )
    got = page.evaluate(
        """(ks) => ks.map(k => document.forms['Devalutazione'].elements[k].value)""",
        list(values),
    )
    assert got == list(values.values()), got
    with page.expect_navigation(timeout=60000):
        page.evaluate(
        """() => {const f = document.forms['Devalutazione'];
        const i = document.createElement('input'); i.type = 'hidden';
        i.name = 'Calcola'; i.value = 'Calcola'; f.appendChild(i); f.submit();}"""
    )
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(2500)
    body = page.inner_text("body")
    out = {"body": body}
    m = re.search(r"Importo Devalutato:\s*€\s*([\d.,]+)", body)
    out["importo"] = parse_euro(m.group(1)) if m else None
    m = re.search(r"Indice di Devalutazione:\s*([\d.,]+)", body)
    out["indice_dev"] = m.group(1) if m else None
    out["indici"] = re.findall(r"Indice (\w+ \d{4}):\s*([\d.,]+)", body)
    m = re.search(r"Raccordo Indici:\s*([\d.,]+)", body)
    out["raccordo"] = m.group(1) if m else None
    return out


def _compare(page, importo, data_att, data_pass, label):
    r = _fn(importo_attuale=importo, data_attuale=data_att, data_passata=data_pass)
    assert "errore" not in r, r
    ya, ma = int(data_att[:4]), int(data_att[5:7])
    yp, mp = int(data_pass[:4]), int(data_pass[5:7])
    s = _site(page, f"{importo:.2f}".replace(".", ","), ma, ya, mp, yp)
    assert s["importo"] is not None, s["body"][-1500:]
    print(f"{label}: tool={r['importo_in_data_passata']} (FOI {r['foi_attuale']}/{r['foi_passata']}, "
          f"coeff {r['coefficiente_devalutazione']}) sito={s['importo']} "
          f"(indici {s['indici']}, raccordo {s['raccordo']}, indice dev {s['indice_dev']})")
    assert_close(r["importo_in_data_passata"], s["importo"], 0.01, label)


def test_dic2023_dic2013(page):
    """Piano: 8.410,43 = 10.000 / 1,189 (coeff. ISTAT dic.2013-dic.2023); tool atteso 8.469,30
    (serie FOI 2011-2013 sospetta). Fonte: indici FOI ISTAT."""
    _compare(page, 10000, "2023-12-01", "2013-12-01", "dic2023->dic2013")


def test_ago2026_ago2025_ribasamento(page):
    """Caso al limite (base 2025=100 dal 2026, raccordo 1,214). Piano: 9.674,34 =
    10.000 x 121,8 / 125,9 sulla serie raccordata."""
    _compare(page, 10000, "2026-08-01", "2025-08-01", "ago2026->ago2025")


def test_gen2026_dic2025_confine_base(page):
    """Caso al limite: un solo mese a cavallo del cambio base 2015 -> 2025 (dic 2025 / gen 2026)."""
    _compare(page, 10000, "2026-01-01", "2025-12-01", "gen2026->dic2025")


def test_ago2026_gen1990_inizio_serie(page):
    """Caso al limite: primo mese della serie del tool (gen 1990) contro l'ultimo pubblicato (ago 2026)."""
    _compare(page, 10000, "2026-08-01", "1990-01-01", "ago2026->gen1990")


def test_giu2020_giu2015(page):
    """Caso ordinario interamente in base 2015=100 (nessun raccordo)."""
    _compare(page, 5000, "2020-06-01", "2015-06-01", "giu2020->giu2015")


def test_dic2012_dic2010_tratto_2011_2013(page):
    """Caso al limite: tratto 2011-2013 (serie FOI da riscontrare secondo il piano), a
    cavallo del raccordo base 2010 -> 2015."""
    _compare(page, 10000, "2012-12-01", "2010-12-01", "dic2012->dic2010")


def test_giu1985_fuori_serie(page):
    """Piano: il tool risponde con errore (serie dal 1990), il sito restituisce un valore:
    scostamento di copertura, non di calcolo."""
    r = _fn(importo_attuale=1000, data_attuale="2026-01-01", data_passata="1985-06-01")
    s = _site(page, "1000,00", 1, 2026, 6, 1985)
    print(f"giu1985: tool={r} sito={s['importo']} (indici {s['indici']}, raccordo {s['raccordo']})")
    assert "errore" in r
    assert s["importo"] is not None
    pytest.skip(f"non confrontabile: il tool copre dal 1990 (errore), il sito calcola {s['importo']}")


# Phase 3 verdict (2026-09-29). The FOI series was rebuilt from the ISTAT original bases (data errors fixed).
# The residual differences are conventions: (1) the site rounds the revaluation coefficient to 3 decimals
# (ISTAT practice) before dividing, the tool divides by the exact index ratio; (2) the site uses 1,374 as the
# 1995>2010 splicing coefficient, ISTAT states 1,373 (NM_variazioni_coefficienti.pdf: dec 2012 -> dec 2010
# gives 9464.89 with 1,373 and 9460.74 with the site's 1,374); (3) Jan 1990 is a with-tobacco index (base 1989)
# as in the ISTAT worked example 2.

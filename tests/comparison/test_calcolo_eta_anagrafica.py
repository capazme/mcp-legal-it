"""Comparison: calcolo_eta_anagrafica vs avvocatoandreani.it/servizi/calcolo-eta-anagrafica.php

The site shows "N anni, M mesi e G giorni" (singular forms, zero units omitted).
The form only submits reliably through requestSubmit() with the button as
submitter (the POST needs the "Calcola" field). Both sides always get an
explicit reference date, so no clock pinning is needed.

Norma: artt. 2 e 2963 c.c. (maggiore eta', computo ad anni e mesi).
Tolerance: exact integers (anni, mesi, giorni).

Known divergences of the SITE (phase 3, checked by hand against art. 2963 c.c. commi 4-5):
- 2008-09-25 -> 2026-09-24: the site says 17a 11m 29g, but 25/08 -> 24/09 is 30 calendar
  days (tool: 30). Site error.
- Born on 29/02: the tool applies the last-day-of-month rule by analogy (birthday 28/02,
  so 18a 0m 0g on 28/02/2026 and 18a 0m 1g on 01/03/2026); the site is inconsistent (it
  gives 17a 11m 28g on 28/02 but 18a 1g on 01/03). Documented convention, not a tool bug.
- 1990-01-31 -> 2025-02-28: the tool closes the month on the last day of February (art. 2963
  c. 5: 35a 1m 0g), the site says 35a 0m 28g. Convention: the site clamps only from the next
  day on (31/01 -> 01/03 is 1m 1g on both sides).
"""

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from .conftest import goto  # noqa: E402

PAGE = "calcolo-eta-anagrafica.php"


def _tool(data_nascita, data_riferimento):
    import src.server  # noqa: F401  (registers every module)
    from src.tools.varie import calcolo_eta_anagrafica

    fn = getattr(calcolo_eta_anagrafica, "fn", calcolo_eta_anagrafica)
    return fn(data_nascita=data_nascita, data_riferimento=data_riferimento)


def _parse_site(text: str) -> tuple[int, int, int]:
    def num(unit):
        m = re.search(rf"(\d+)\s+{unit}", text)
        return int(m.group(1)) if m else 0

    return num(r"anni?"), num(r"mes[ei]"), num(r"giorn[oi]")


def _site(page, nascita: str, rif: str):
    goto(page, PAGE, 1000)
    y, m, d = nascita.split("-")
    ry, rm, rd = rif.split("-")
    for name, val in dict(
        GiornoNascita=d, MeseNascita=m, AnnoNascita=y,
        GiornoRif=rd, MeseRif=rm, AnnoRif=ry,
    ).items():
        page.select_option(f"select[name={name}]", val)
    page.evaluate(
        "document.getElementById('CalcoloEta').requestSubmit(document.getElementById('btn-calc'))"
    )
    page.wait_for_timeout(2500)
    cells = [c.inner_text().strip() for c in page.query_selector_all("td.result")]
    return cells


def _compare(page, nascita, rif):
    cells = _site(page, nascita, rif)
    if len(cells) < 2:
        pytest.skip(f"il sito non produce risultato per {nascita} -> {rif}")
    site = _parse_site(cells[1])
    r = _tool(nascita, rif)
    assert "errore" not in r, r
    ours = (r["eta_anni"], r["eta_mesi"], r["eta_giorni"])
    assert ours == site, f"{nascita}->{rif}: tool={ours}, sito={site} ({cells[1]!r})"


class TestCalcoloEtaAnagrafica:

    def test_mese_precedente_piu_corto(self, page):
        # Piano: 35 anni, 1 mese, 1 giorno (mese compiuto il 28/02/2025); il tool dava -2 giorni.
        # LIMITE: nato il 31 gennaio, riferimento 1 marzo (febbraio piu' corto). Art. 2963 c.c.
        _compare(page, "1990-01-31", "2025-03-01")

    def test_nato_29_febbraio_riferimento_28_febbraio(self, page):
        # Piano: 18 anni compiuti il 28/02/2026 (art. 2963 co. 5 c.c. per analogia, art. 2 c.c.);
        # il tool dava 17 anni, 11 mesi, 30 giorni. LIMITE: bisestile.
        _compare(page, "2008-02-29", "2026-02-28")

    def test_vigilia_maggiore_eta(self, page):
        # Piano: 17 anni, 11 mesi, 30 giorni; maggiore eta' dal 25/09/2026 (art. 2 c.c.).
        # LIMITE: vigilia del compleanno.
        _compare(page, "2008-09-25", "2026-09-24")

    def test_giorno_compimento_maggiore_eta(self, page):
        # Atteso: 18 anni esatti il 25/09/2026 (art. 2 c.c.). LIMITE: giorno del compleanno.
        _compare(page, "2008-09-25", "2026-09-25")

    def test_nato_29_febbraio_primo_marzo(self, page):
        # Atteso: 18 anni e 1 giorno (dopo il compleanno del 28/02 o 29/02). LIMITE: bisestile.
        _compare(page, "2008-02-29", "2026-03-01")

    def test_nato_29_febbraio_anno_bisestile(self, page):
        # Atteso: 4 anni esatti il 29/02/2004. LIMITE: compleanno reale in anno bisestile.
        _compare(page, "2000-02-29", "2004-02-29")

    def test_31_gennaio_fine_febbraio(self, page):
        # Atteso: 35 anni e 28 giorni (mese non ancora compiuto il 28/02). LIMITE: fine mese.
        _compare(page, "1990-01-31", "2025-02-28")

    def test_capodanno(self, page):
        # Atteso: 40 anni e 1 giorno. LIMITE: attraversa l'anno.
        _compare(page, "1985-12-31", "2026-01-01")

    def test_nato_31_maggio_primo_luglio(self, page):
        # Atteso: 35 anni e 1 mese (31/05 -> 30/06 mese compiuto, poi 1 giorno);
        # il tool dice 0 giorni. LIMITE: mese precedente di 30 giorni.
        _compare(page, "1990-05-31", "2025-07-01")

    def test_stesso_giorno(self, page):
        # Atteso: 0 anni, 0 mesi, 0 giorni; il sito non mostra risultato con date uguali.
        _compare(page, "2020-03-15", "2020-03-15")

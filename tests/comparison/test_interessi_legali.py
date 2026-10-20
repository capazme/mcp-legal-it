"""Comparison tests: interessi_legali vs avvocatoandreani.it/servizi/interessi_legali.php.

Norma: art. 1284 c.c. (saggio legale fissato annualmente con DM MEF dal 1 gennaio),
L. 353/1990 per il 1990. Convenzione di sito e tool: anno civile
di 365 giorni anche nei bisestili. Tolleranza: 0,01 euro sugli importi; il valore
0.0101 evita solo il rumore della virgola mobile su una differenza di esattamente un
centesimo (il sito somma le righe gia' arrotondate, il tool arrotonda il totale).
"""

import os

os.environ["LEGAL_TODAY"] = "2026-09-29"

import re

import pytest

from tests.comparison.conftest import assert_close, goto, parse_euro

TOL = 0.0101


def _site_totale(page, capitale, data_inizio, data_fine, anatocismo="0"):
    """Drive the form; return the site's 'Totale interessi legali' or None if absent.

    anatocismo: '0' nessuna, '3' trimestrale, '6' semestrale, '12' annuale.
    """
    goto(page, "interessi_legali.php")
    # The CMP banner appears after the conftest helper has already looked for it:
    # wait for the accept button, otherwise the form submit is swallowed.
    try:
        page.locator("#accept-btn").click(timeout=8000)
    except Exception:
        pass
    ai, mi, gi = data_inizio.split("-")
    af, mf, gf = data_fine.split("-")
    page.fill("input[name='Capitale']", str(int(capitale)))
    page.fill("input[name='GiornoInizio']", gi)
    page.fill("input[name='MeseInizio']", mi)
    page.fill("input[name='AnnoInizio']", ai)
    page.fill("input[name='GiornoFine']", gf)
    page.fill("input[name='MeseFine']", mf)
    page.fill("input[name='AnnoFine']", af)
    page.click(f"input[name='Anatocismo'][value='{anatocismo}']", force=True)
    page.click("#btn-calc", force=True)
    try:
        page.wait_for_function(
            "document.body.innerText.includes('Totale interessi legali')", timeout=15000
        )
    except Exception:
        pass
    page.wait_for_timeout(1000)
    body = page.inner_text("body")
    m = re.search(r"Totale\s+interessi\s+legali[:\s]*€?\s*([\d.]+,\d{2})", body, re.I)
    page.wait_for_timeout(1000)
    return parse_euro(m.group(1)) if m else None


def _ours(capitale, data_inizio, data_fine, tipo="semplici"):
    import src.server  # noqa: F401
    from src.tools.tassi_interessi import interessi_legali

    fn = getattr(interessi_legali, "fn", interessi_legali)
    r = fn(capitale=capitale, data_inizio=data_inizio, data_fine=data_fine, tipo=tipo)
    assert "errore" not in r, r
    return r["totale_interessi"]


def _confronta(page, capitale, di, df, tipo="semplici", anatocismo="0", label=""):
    site = _site_totale(page, capitale, di, df, anatocismo)
    for _ in range(3):  # the site intermittently returns no result: retry
        if site is not None:
            break
        page.wait_for_timeout(3000)
        site = _site_totale(page, capitale, di, df, anatocismo)
    if site is None:
        pytest.skip(f"{label}: il sito non restituisce un totale per questo input")
    assert_close(_ours(capitale, di, df, tipo), site, tolerance=TOL, label=label)


class TestInteressiLegaliComparison:

    def test_cambio_tasso_1_gennaio_2026(self, page):
        """Piano: 179,62 = 183 gg al 2,0% (100,27) + 181 gg all'1,6% (79,34);
        art. 1284 co. 1 c.c., divisore 365. Sito atteso 179,61 (somma righe)."""
        _confronta(page, 10000, "2025-07-01", "2026-06-30", label="cambio_2026")

    def test_1990_cambio_tasso_infrannuale(self, page):
        """LIMITE (anno storico). Piano: 520,55 = 5% fino al 15/12/1990 e 10% dal
        16/12/1990 (L. 353/1990). Il tool applica il 10% dal 16/04/1990 (854,79)."""
        _confronta(page, 10000, "1990-01-01", "1990-12-31", label="1990")

    def test_anno_bisestile_divisore(self, page):
        """LIMITE (bisestile). Piano: 366 gg al 2,5% = 250,68 con anno di 365 gg
        (convenzione di sito e tool), 250,00 con divisore 366; la norma non fissa."""
        _confronta(page, 10000, "2023-12-31", "2024-12-31", label="bisestile")

    def test_composti_annuale_5_anni(self, page):
        """Piano: 5.586,55 (tool, capitalizzazione annuale al 31/12) da leggere dal
        sito con capitalizzazione annuale; art. 1283 c.c. sui limiti dell'anatocismo."""
        _confronta(page, 50000, "2021-01-01", "2026-01-01", tipo="composti",
                   anatocismo="12", label="composti_annuale")

    def test_oltre_copertura_2027(self, page):
        """LIMITE (oltre la tabella). Piano: senza decreto entro il 15/12/2026 resta
        l'1,6% (art. 1284 co. 1 c.c.): stima 159,56; il tool si ferma a 80,22."""
        _confronta(page, 10000, "2026-07-01", "2027-06-30", label="oltre_2027")

    def test_confine_anno_un_giorno(self, page):
        """LIMITE (confine 1 gennaio 2023, tasso 1,25% -> 5,0%). Un giorno a cavallo:
        31/12/2022 -> 01/01/2023, art. 1284 c.c. e DM MEF 13/12/2022."""
        _confronta(page, 10000, "2022-12-31", "2023-01-01", label="confine_2023")

    def test_agosto_stesso_tasso(self, page):
        """LIMITE (agosto). 01/07/2024 - 31/08/2024 al 2,5% (DM MEF 2023): nessuna
        sospensione feriale per gli interessi (art. 1284 c.c.), 62 gg."""
        _confronta(page, 20000, "2024-07-01", "2024-08-31", label="agosto")

    def test_composti_annuale_non_a_gennaio(self, page):
        """LIMITE (capitalizzazione). 01/07/2022 - 01/07/2025 composti: il tool capitalizza
        al 31/12, il sito ogni 12 mesi dalla data iniziale (art. 1283 c.c.)."""
        _confronta(page, 30000, "2022-07-01", "2025-07-01", tipo="composti",
                   anatocismo="12", label="composti_non_gennaio")

    def test_1990_confine_16_dicembre(self, page):
        """LIMITE (L. 353/1990). 01/12/1990 - 31/12/1990: 5% fino al 15/12 e 10% dal 16/12;
        il tool applica il 10% su tutto il periodo."""
        _confronta(page, 10000, "1990-12-01", "1990-12-31", label="1990_dicembre")

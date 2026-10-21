"""Benchmark: rivalutazione_mensile vs avvocatoandreani.it.

Site page: servizi/rivalutazione_mensile_assegni_importi_dovuti.php
("Rivalutazione Mensile Importi Dovuti e Non Pagati").

Driver: amount + split start/end dates, the "interessi legali" option is
unticked so only the revaluation share is compared (the tool computes no
interest). Compared values: number of monthly instalments, "Totale
Rivalutazioni Mensili" (tool: differenza_totale) and "Somma Importi
Rivalutati" (tool: totale_rivalutato).

Known method difference (documented, not smoothed over): the site compounds
the cumulative balance month by month with the ISTAT monthly variation
rounded to 0.1%, rounding each row to the cent; the tool applies to each
instalment the exact ratio FOI(final month) / FOI(instalment month). Both
give coefficient 1 to the last instalment.

Norm/source: indici FOI ISTAT (base 2015=100 raccordata; from 2026 base
2025=100 with official coefficient 1,214).
"""

# Phase 3 verdict (2026-09-29): the FOI series of the tool was rebuilt from the ISTAT monthly
# series (SDMX dataflows 144_110, 169_15, 169_745, code 00ST), which fixes the 2012-2013 case.
# The remaining gaps are a METHOD CONVENTION, not a tool error: the tool revalues each rata
# with the full ratio of the published indices I(end)/I(month), the page chains the monthly
# variations rounded to 0.1%, which accumulates up to a few euros on 12 rate (2022: 611.11
# vs 625.39; sept. 2025-aug. 2026: 131.74 vs 134.12; jun. 2012-may. 2013: 48.03 vs 51.10).
# These cases stay failing on purpose: no norm prescribes the page's chaining.


import os

os.environ.setdefault("LEGAL_TODAY", "2026-09-25")

import pytest  # noqa: E402

from tests.comparison.conftest import accept_cookies, assert_close, extract_amount, goto  # noqa: E402

PAGE = "rivalutazione_mensile_assegni_importi_dovuti.php"


def _tool(**kwargs):
    import src.server  # noqa: F401  (registers all modules)
    from src.tools.rivalutazioni_istat import rivalutazione_mensile

    fn = getattr(rivalutazione_mensile, "fn", rivalutazione_mensile)
    return fn(**kwargs)


def _site(page, importo: str, inizio: str, fine: str) -> str:
    """Fill the form (dates YYYY-MM-DD) and return the page text."""
    goto(page, PAGE, wait_ms=1500)
    accept_cookies(page)
    yi, mi, di = inizio.split("-")
    yf, mf, df = fine.split("-")
    fields = {
        "Capitale": importo,
        "GiornoInizio": di, "MeseInizio": mi, "AnnoInizio": yi,
        "GiornoFine": df, "MeseFine": mf, "AnnoFine": yf,
    }
    for name, value in fields.items():
        page.fill(f"input[name='{name}']", value)
    if page.is_checked("input[name='OptInteressiLegali']"):
        page.uncheck("input[name='OptInteressiLegali']", force=True)
    if page.is_checked("input[name='OptRivalutazioneAnnuale']"):
        page.uncheck("input[name='OptRivalutazioneAnnuale']", force=True)
    page.click("#btn-calc", force=True)
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(2500)
    return page.inner_text("body")


def _site_values(text: str):
    import re

    if "Somma Importi Rivalutati" not in text:
        return None
    mesi = int(re.search(r"Periodo Mesi:\s*(\d+)", text).group(1))
    riv = extract_amount(text, "Totale Rivalutazioni Mensili")
    somma = extract_amount(text, "Somma Importi Rivalutati")
    return mesi, riv, somma


def _compare(page, importo_site, **kw):
    r = _tool(**kw)
    assert "errore" not in r, r
    text = _site(page, importo_site, kw["data_inizio"], kw["data_fine"])
    vals = _site_values(text)
    assert vals is not None, "site returned no result"
    mesi, riv, somma = vals
    print(f"tool: n={r['numero_mensilita']} riv={r['differenza_totale']} tot={r['totale_rivalutato']} | "
          f"site: n={mesi} riv={riv} tot={somma}")
    assert r["numero_mensilita"] == mesi
    assert_close(r["differenza_totale"], riv, tolerance=0.01, label="rivalutazione totale")
    assert_close(r["totale_rivalutato"], somma, tolerance=0.01, label="somma rivalutata")


def test_dodici_mensilita_2022(page):
    """Piano: 12 mensilita' 2022, totale 12.611,11 (1.000 x 118,2 / FOI del mese).
    Fonte: indici FOI 2022. Site: 625,39 / 12.625,39 (compounded rounded variations)."""
    _compare(page, "1000,00", importo_mensile=1000, data_inizio="2022-01-01", data_fine="2022-12-31")


def test_cavallo_ribasamento_2025(page):
    """Limite: a cavallo del ribasamento FOI 2025=100 (coefficiente 1,214).
    Piano: 12 mensilita', totale 6.131,74. Site: 134,12 / 6.134,12."""
    _compare(page, "500,00", importo_mensile=500, data_inizio="2025-09-01", data_fine="2026-08-31")


def test_una_mensilita(page):
    """Limite: una sola mensilita'. Piano: coefficiente 1, differenza 0,00."""
    _compare(page, "800,00", importo_mensile=800, data_inizio="2026-03-01", data_fine="2026-03-31")


def test_serie_2012_2013(page):
    """Limite: anni 2012-2013, dove il piano segnala l'errore della serie FOI
    (vedi rivalutazione_monetaria). Nessun atteso numerico nel piano."""
    _compare(page, "1000,00", importo_mensile=1000, data_inizio="2012-06-01", data_fine="2013-05-31")


def test_data_finale_oltre_ultimo_indice(page):
    """Limite: data finale oltre l'ultimo indice pubblicato (agosto 2026).
    Piano: tool INDICATIVO con agosto 2026 per set-dic, totale 12.117,76;
    il sito non accetta la data."""
    r = _tool(importo_mensile=1000, data_inizio="2026-01-01", data_fine="2026-12-31")
    assert r["numero_mensilita"] == 12
    assert r["avvertenza"] and "non disponibile" in r["avvertenza"]
    text = _site(page, "1000,00", "2026-01-01", "2026-12-31")
    if _site_values(text) is None and "Superiore al massimo" in text:
        pytest.skip("il sito rifiuta la data finale oltre agosto 2026 ('Superiore al massimo!'); "
                    f"tool {r['totale_rivalutato']} con avvertenza")
    _compare(page, "1000,00", importo_mensile=1000, data_inizio="2026-01-01", data_fine="2026-12-31")

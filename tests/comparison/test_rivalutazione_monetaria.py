"""Benchmark rivalutazione_monetaria vs avvocatoandreani.it (interessi_rivalutazione.php).

Norme: indici FOI ISTAT senza tabacchi (base 2015=100 raccordata; base 2025=100 dal
2026 con coefficiente 1,214; raccordo 2010-2015 pari a 1,071); art. 1284 c.c. e DM MEF
annuali per il tasso legale; Cass. SU 17/02/1995 n. 1712 per gli interessi sul capitale
rivalutato anno per anno.

Site options (radio TipoCalcolo): 1 = interessi legali sul capitale rivalutato
annualmente (con_interessi_legali=True), 2 = interessi senza rivalutazione (not this
tool), 3 = sola rivalutazione (con_interessi_legali=False).
The site accepts dates up to the last published FOI month (Aug 2026 at run time).

Tolerance: 0.01 EUR on amounts (brief). Mismatches are genuine and are left failing.
"""

import os
import re

os.environ.setdefault("LEGAL_TODAY", "2026-09-25")

import pytest

from tests.comparison.conftest import assert_close, goto, parse_euro

PAGE = "interessi_rivalutazione.php"
TOL = 0.01


def _tool(**kwargs):
    import src.server  # noqa: F401  (registers every module, avoids circular imports)
    from src.tools.rivalutazioni_istat import rivalutazione_monetaria

    fn = getattr(rivalutazione_monetaria, "fn", rivalutazione_monetaria)
    return fn(**kwargs)


def _site(page, capitale: str, data_inizio: str, data_fine: str, tipo: str) -> str:
    """Fill the Rivalutazione form and return the result page text."""
    goto(page, PAGE, wait_ms=1500)
    ai, mi, gi = data_inizio.split("-")
    af, mf, gf = data_fine.split("-")
    for name, value in [
        ("Capitale", capitale),
        ("GiornoInizio", gi), ("MeseInizio", mi), ("AnnoInizio", ai),
        ("GiornoFine", gf), ("MeseFine", mf), ("AnnoFine", af),
        ("PctRival", "100"),
    ]:
        # page.fill() leaves some of these fields empty after goto() (site JS on the
        # t-text inputs): assign the value directly.
        page.evaluate(
            "([n, v]) => { document.querySelector(`#Rivalutazione input[name='${n}']`).value = v; }",
            [name, value],
        )
    # The radio does not toggle with a (forced) click: set it via JS.
    page.evaluate(
        f"document.querySelector(\"input[name=TipoCalcolo][value='{tipo}']\").checked = true"
    )
    # A plain click on #btn-calc does not submit headless: use requestSubmit.
    with page.expect_navigation(wait_until="domcontentloaded", timeout=60000):
        page.evaluate(
            "document.getElementById('Rivalutazione')"
            ".requestSubmit(document.getElementById('btn-calc'))"
        )
    page.wait_for_timeout(2000)
    return page.inner_text("body")


def _amount(text: str, label_regex: str) -> float:
    m = re.search(label_regex + r"\s*€\s*([\d.]+,\d{2})", text)
    assert m, f"etichetta non trovata nel risultato del sito: {label_regex}"
    return parse_euro(m.group(1))


def _site_info(text: str) -> str:
    keys = ["Indice alla Decorrenza", "Indice alla Scadenza", "Raccordo Indici",
            "Coefficiente di Rivalutazione"]
    out = []
    for k in keys:
        m = re.search(re.escape(k) + r":\s*([\d.,]+)", text)
        out.append(f"{k}={m.group(1) if m else '?'}")
    return "; ".join(out)


def _compare(pairs, context):
    """pairs: list of (label, tool_value, site_value). Assert all within TOL."""
    errors = []
    for label, ours, site in pairs:
        try:
            assert_close(ours, site, tolerance=TOL, label=label)
        except AssertionError as exc:
            errors.append(str(exc))
    assert not errors, " | ".join(errors) + f" || sito: {context}"


# ---------------------------------------------------------------------------
# Sola rivalutazione (TipoCalcolo=3)
# ---------------------------------------------------------------------------

def test_sola_rivalutazione_2015_2023(page):
    """Piano caso 1. Atteso: da leggere dal sito; tool 118,9/99,7 = 11.925,78
    (11.930,00 con coefficiente a tre decimali). Norma: indici FOI ISTAT."""
    r = _tool(capitale=10000, data_inizio="2015-01-15", data_fine="2023-12-15",
              con_interessi_legali=False)
    text = _site(page, "10000,00", "2015-01-15", "2023-12-15", "3")
    site = _amount(text, r"Capitale Rivalutato \(s\.e\.o\):")
    _compare([("capitale_rivalutato", r["capitale_rivalutato"], site)], _site_info(text))


def test_sola_rivalutazione_partenza_dic_2013(page):
    """Piano caso 2 (limite: tratto sospetto della serie FOI). Atteso 11.890,00:
    coefficiente ISTAT 1,189 = 118,9 x 1,071 / 107,1 (FOI dic. 2013 base 2010 = 107,1)."""
    r = _tool(capitale=10000, data_inizio="2013-12-01", data_fine="2023-12-01",
              con_interessi_legali=False)
    text = _site(page, "10000,00", "2013-12-01", "2023-12-01", "3")
    site = _amount(text, r"Capitale Rivalutato \(s\.e\.o\):")
    _compare([("capitale_rivalutato", r["capitale_rivalutato"], site)], _site_info(text))


def test_sola_rivalutazione_ribasamento_2025(page):
    """Piano caso 4 (limite: a cavallo del ribasamento ISTAT 2025=100). Atteso
    10.336,62 (125,9/121,8; raccordo 1,214, GU n. 144 del 24/06/2026)."""
    r = _tool(capitale=10000, data_inizio="2025-08-01", data_fine="2026-08-31",
              con_interessi_legali=False)
    text = _site(page, "10000,00", "2025-08-01", "2026-08-31", "3")
    site = _amount(text, r"Capitale Rivalutato \(s\.e\.o\):")
    _compare([("capitale_rivalutato", r["capitale_rivalutato"], site)], _site_info(text))


def test_sola_rivalutazione_oltre_ultimo_indice(page):
    """Piano caso 5 (limite: data oltre l'ultimo indice). Atteso: tool usa agosto 2026
    con avvertenza INDICATIVO (10.362,14); il sito rifiuta la data."""
    r = _tool(capitale=10000, data_inizio="2025-12-01", data_fine="2026-12-31",
              con_interessi_legali=False)
    assert r["avvertenza"] and "INDICATIVO" in r["avvertenza"]
    text = _site(page, "10000,00", "2025-12-01", "2026-12-31", "3")
    if "Superiore al massimo" in text:
        pytest.skip("sito_non_calcola: Data Fine 'Superiore al massimo!' "
                    f"(tool {r['capitale_rivalutato']:.2f} INDICATIVO)")
    site = _amount(text, r"Capitale Rivalutato \(s\.e\.o\):")
    _compare([("capitale_rivalutato", r["capitale_rivalutato"], site)], _site_info(text))


def test_sola_rivalutazione_a_cavallo_di_agosto(page):
    """Caso aggiunto (limite: periodo breve a cavallo di agosto, stesso indice FOI
    luglio/settembre 2024 = 120,0). Atteso: nessuna rivalutazione, 10.000,00."""
    r = _tool(capitale=10000, data_inizio="2024-07-10", data_fine="2024-09-20",
              con_interessi_legali=False)
    text = _site(page, "10000,00", "2024-07-10", "2024-09-20", "3")
    site = _amount(text, r"Capitale Rivalutato \(s\.e\.o\):")
    _compare([("capitale_rivalutato", r["capitale_rivalutato"], site)], _site_info(text))


# ---------------------------------------------------------------------------
# Rivalutazione + interessi legali (TipoCalcolo=1)
# ---------------------------------------------------------------------------

def _compare_con_interessi(page, capitale, di, df):
    r = _tool(capitale=capitale, data_inizio=di, data_fine=df, con_interessi_legali=True)
    text = _site(page, f"{capitale:.2f}".replace(".", ","), di, df, "1")
    pairs = [
        ("capitale_rivalutato", r["capitale_rivalutato"],
         _amount(text, r"\nCapitale Rivalutato:")),
        ("totale_interessi_legali", r["totale_interessi_legali"],
         _amount(text, r"Totale Interessi:")),
        ("totale_dovuto", r["totale_dovuto"],
         _amount(text, r"Capitale Rivalutato \+ Interessi:")),
    ]
    _compare(pairs, _site_info(text))


def test_con_interessi_anno_intero_2025(page):
    """Piano caso 3 (limite: conteggio giorni dell'ultimo anno). Atteso: rivalutato
    10.108,15 (121,5/120,2); interessi 2,0% su 365 gg = 202,16; totale 10.310,31.
    Norma: art. 1284 c.c., DM MEF dicembre 2024 (2,0% dal 2025)."""
    _compare_con_interessi(page, 10000, "2024-12-31", "2025-12-31")


def test_con_interessi_bisestile_e_cambio_tasso(page):
    """Caso aggiunto (limite: attraversa il bisestile 2024 e tre tassi legali 5% /
    2,5% / 2%). Atteso: da leggere dal sito. Norma: art. 1284 c.c., DM MEF annuali;
    Cass. SU 1712/1995."""
    _compare_con_interessi(page, 10000, "2023-06-15", "2025-03-10")


def test_con_interessi_2016_2019(page):
    """Caso aggiunto (limite: anni interamente in base 2015, tassi legali 0,2% / 0,1% /
    0,3% / 0,8%). Atteso: da leggere dal sito. Norma: art. 1284 c.c., DM MEF annuali."""
    _compare_con_interessi(page, 10000, "2016-01-01", "2019-12-31")

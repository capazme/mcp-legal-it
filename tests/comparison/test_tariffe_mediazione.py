"""Benchmark: tariffe_mediazione vs avvocatoandreani.it (Fase 1).

Site page: calcolo-spese-di-mediazione.php ("nuove tariffe 2023", DM 150/2023).
The page named in the plan (calcolo-costi-e-tariffe-mediazione-civile.php) still
applies the DM 180/2010 table (base indennity 65 EUR for the first bracket, 1/3
reduction for mandatory matters) and links to "la nuova applicazione": it is
superseded, so the comparison uses the 2023 page.

Mapping tool <-> site (materia facoltativa, no reductions, IVA 22%):
- spese_avvio_per_parte           <-> "Spese di avvio" (art. 28 c. 1 DM 150/2023)
- spese_primo_incontro_per_parte  <-> "Indennita' per il primo incontro"
                                      (accordo = No, incontri = Uno)
- tabella_a.medio                 <-> 'Importo tabella "A" (valore medio)'
                                      (accordo = Si', incontri = Uno)
(phase 3: the tool now exposes these two components separately; before it returned the
DM 180/2010 indennity per bracket under esito_negativo/esito_positivo.indennita_per_parte)
- esito_negativo.totale_per_parte <-> "TOTALE GENERALE" (no accordo, one meeting)
- esito_positivo.totale_per_parte <-> "TOTALE GENERALE" (accordo at the first
                                      meeting: both add the 10% of art. 30
                                      DM 150/2023 on Tabella A minus the first meeting)
Tolerance: 0.01 EUR (brief). The site selects a bracket, not a value; the value
field is shown only for the "oltre 5.000.000" bracket.
"""

import re
import sys

import pytest

sys.path.insert(0, "/Users/gpuzio/Desktop/CODE/server-infra2.0/mcp-legal-it")
import src.server  # noqa: E402,F401  (registers every tool module)
from src.tools.parcelle_professionisti import tariffe_mediazione  # noqa: E402

from .conftest import accept_cookies, parse_euro  # noqa: E402

_fn = getattr(tariffe_mediazione, "fn", tariffe_mediazione)
PAGE = "calcolo-spese-di-mediazione.php"
TOL = 0.01


def _amount(text: str, label: str) -> float | None:
    m = re.search(re.escape(label) + r"[^\n€]*€\s*([\d\.,]+)", text)
    return parse_euro(m.group(1)) if m else None


def _radio(page, sel: str) -> None:
    page.check(sel, force=True)
    assert page.eval_on_selector(sel, "el => el.checked"), f"{sel} not checked"


def _open(page) -> None:
    # On this page conftest.goto() (which strips the Quantcast overlay via JS)
    # leaves the radio buttons unclickable; consenting through the CMP button
    # keeps the form working. Fallback: the shared helper.
    page.goto(f"https://www.avvocatoandreani.it/servizi/{PAGE}",
              timeout=60000, wait_until="domcontentloaded")
    page.wait_for_timeout(1500)
    try:
        page.click("#qc-cmp2-container button[mode='primary']", timeout=3000)
        page.wait_for_timeout(300)
    except Exception:
        accept_cookies(page)


def _site(page, scaglione: str, accordo: bool, valore: str | None = None) -> dict:
    _open(page)
    page.select_option("#Scaglione", scaglione)
    page.wait_for_timeout(400)
    if valore is not None and page.is_visible("#ValoreLite"):
        page.fill("#ValoreLite", valore)
    _radio(page, "#MedObb-0")  # materia facoltativa: no 20% reduction
    # Order matters on this page: meetings first, then outcome (the other
    # order leaves the form silently unsubmittable for "no agreement").
    _radio(page, "#Incontri-1")  # one meeting
    page.wait_for_timeout(300)
    _radio(page, "#Accordo-1" if accordo else "#Accordo-0")
    page.wait_for_timeout(300)
    # DOM click on the submit button: a coordinate click (force=True) can land
    # on an ad iframe covering the button and silently do nothing.
    page.eval_on_selector("#btn-calc", "b => b.click()")
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(2500)
    t = page.inner_text("body")
    assert "Esito della mediazione" in t, "site returned no result"
    return {
        "avvio": _amount(t, "Spese di avvio:"),
        "primo": _amount(t, "Indennità per il primo incontro:"),
        "tab_a": _amount(t, "(valore medio):"),
        "totale": _amount(t, "TOTALE GENERALE:"),
    }


def _compare(page, valore: float, scaglione: str, valore_sito: str | None = None,
             compare_tab_a: bool = True):
    r = _fn(valore_controversia=valore)
    neg = _site(page, scaglione, accordo=False, valore=valore_sito)
    page.wait_for_timeout(1500)
    pos = _site(page, scaglione, accordo=True, valore=valore_sito)
    pairs = [
        ("spese_avvio", r["spese_avvio_per_parte"], neg["avvio"]),
        ("indennita_negativo (primo incontro)", r["spese_primo_incontro_per_parte"], neg["primo"]),
        ("totale_negativo_per_parte", r["esito_negativo"]["totale_per_parte"], neg["totale"]),
    ]
    if compare_tab_a:
        pairs += [
            ("indennita_positivo (tabella A)", r["tabella_a"]["medio"], pos["tab_a"]),
            ("totale_positivo_per_parte", r["esito_positivo"]["totale_per_parte"], pos["totale"]),
        ]
    print(f"\nvalore={valore} tool/site:", [(l, a, b) for l, a, b in pairs])
    bad = [f"{l}: tool {a} vs site {b}" for l, a, b in pairs
           if b is None or abs(a - b) > TOL]
    assert not bad, "; ".join(bad)


def test_valore_1000_confine_prima_fascia(page):
    # Plan: spese di avvio 40 (art. 28 DM 150/2023); tool negativo 113,20, positivo 186,40.
    # Limit case: upper bound of the first bracket.
    _compare(page, 1000, "100")


def test_valore_1000_01_primo_centesimo_seconda_fascia(page):
    # Plan: spese di avvio 75 per parte (art. 28 DM 150/2023). Limit case.
    _compare(page, 1000.01, "110")


def test_valore_50000_confine_fascia_intermedia(page):
    # Plan: spese di avvio 75 (art. 28); Tabella A DM 150/2023; tool negativo 514,20,
    # positivo 953,40 per parte. Limit case.
    _compare(page, 50000, "140")


def test_valore_50000_01_primo_centesimo_fascia_alta(page):
    # Plan: spese di avvio 110 (art. 28); Tabella A; tool negativo 756,60,
    # positivo 1.403,20 per parte. Limit case.
    _compare(page, 50000.01, "150")


def test_valore_150000_01_scaglione_tabella_a(page):
    # Added limit case: Tabella A DM 150/2023 splits 50.000,01-150.000 and
    # 150.000,01-250.000; the tool keeps a single 50.000-250.000 bracket.
    _compare(page, 150000.01, "160")


def test_valore_30000_scaglione_intermedio(page):
    # Ordinary case (same value as tests/comparison/test_parcelle_prof.py):
    # bracket 25.000,01-50.000 of Tabella A, spese di avvio 75.
    _compare(page, 30000, "140")


def test_valore_oltre_5_milioni(page):
    # Added limit case: top bracket. The site shows no Tabella A amount for
    # "oltre 5.000.000" (only avvio 110 + first meeting 170), so only the
    # negative-outcome figures are comparable.
    _compare(page, 6_000_000, "210", valore_sito="6000000", compare_tab_a=False)

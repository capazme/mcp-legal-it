"""Comparison: spese_mediazione vs avvocatoandreani.it (calcolo-spese-di-mediazione.php).

Norma: D.Lgs. 28/2010 (art. 17) e DM 24 ottobre 2023 n. 150, artt. 28-31 e Tabella A.
The site implements DM 150/2023: spese di avvio (40/75/110 euro, art. 28), indennita' per il
primo incontro, Tabella A (valore minimo/medio/massimo) with the first-meeting amount deducted,
+10% for an agreement at the first meeting and +25% after it (art. 30), reduction for
mandatory mediation (MedObb). The tool follows the DM 180/2010 scheme (one amount per
scaglione, no spese di avvio, no increases): its docstring declares Precisione: INDICATIVO.

Site driving: the radio buttons do not react to Playwright clicks and the submit button does
not submit on click, so radios are set via JS and the form is submitted with requestSubmit().
All cases use "materia facoltativa" (MedObb=0) and the Tabella A "valore medio" (TipoVal=2),
the neutral options closest to the tool, which has neither parameter.
Tolerance: 0.01 euro (brief).
"""

import re

import pytest

from tests.comparison.conftest import assert_close, goto, parse_euro

PAGE = "calcolo-spese-di-mediazione.php"
TOL = 0.01


def _tool(**kwargs):
    import src.server  # noqa: F401  (registers all modules)
    from src.tools.parcelle_professionisti import spese_mediazione

    fn = getattr(spese_mediazione, "fn", spese_mediazione)
    r = fn(**kwargs)
    assert "errore" not in r, r
    return r


def _set_radio(page, id_):
    page.evaluate(
        "id=>{const e=document.getElementById(id); e.checked=true;"
        "e.dispatchEvent(new Event('click',{bubbles:true}));"
        "e.dispatchEvent(new Event('change',{bubbles:true}));}",
        id_,
    )


def _site(page, scaglione: str, obbligatoria: int = 0, incontri: int = 1, accordo: int = 1) -> dict:
    """Drive the site and return the labelled amounts of the result sheet."""
    goto(page, PAGE, wait_ms=1500)
    page.select_option("select[name='Scaglione']", scaglione)
    page.wait_for_timeout(400)
    for rid in (f"MedObb-{obbligatoria}", f"Incontri-{incontri}", f"Accordo-{accordo}", "TipoVal-2"):
        _set_radio(page, rid)
    page.wait_for_timeout(300)
    page.evaluate(
        "()=>document.getElementById('SpeseMediazione')"
        ".requestSubmit(document.getElementById('btn-calc'))"
    )
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(2500)
    text = page.inner_text("body")
    out = {}
    for label, key in [
        ("Spese di avvio:", "avvio"),
        ("Indennità per il primo incontro:", "primo_incontro"),
        ("Totale da versare alla domanda o all’adesione:", "totale_domanda"),
        ('Importo tabella "A" (valore medio):', "tabella_a_medio"),
        ("Totale IVA esclusa:", "totale_imponibile"),
        ("TOTALE GENERALE:", "totale_generale"),
    ]:
        m = re.search(re.escape(label) + r"\s*€\s*([\d.,]+)", text)
        if m:
            out[key] = parse_euro(m.group(1))
    assert "totale_domanda" in out, f"risultato non trovato sul sito: {text[:500]}"
    return out


def _site_total(s: dict) -> float:
    # With an agreement the site prints TOTALE GENERALE; at the first meeting without
    # agreement only the amount paid at filing is due (art. 28 DM 150/2023).
    return s.get("totale_generale", s["totale_domanda"])


def test_primo_scaglione_accordo_primo_incontro(page):
    """Piano: 1.000 euro, esito positivo.
    Atteso (piano): DM 150/2023 spese di avvio 40 (art. 28) + Tabella A +10% per accordo al
    primo incontro (art. 30) + IVA; il tool: 120 + IVA 26,40 = 146,40 per parte.
    """
    r = _tool(valore_controversia=1000, esito="positivo")
    s = _site(page, "100", incontri=1, accordo=1)
    assert_close(r["totale_per_parte"], _site_total(s), TOL, "totale per parte IVA inclusa")


def test_mancato_accordo_primo_incontro(page):
    """Piano: 15.000 euro, esito negativo.
    Atteso (piano): spese di avvio 75 + spese fisse del primo incontro, nulla di piu' (art. 28
    DM 150/2023); il tool: 240 (292,80 IVA inclusa) o 160 ridotta (195,20).
    """
    r = _tool(valore_controversia=15000, esito="negativo")
    s = _site(page, "130", incontri=1, accordo=0)
    assert_close(r["totale_per_parte"], _site_total(s), TOL, "totale per parte IVA inclusa")


def test_primo_centesimo_fascia_avvio_110(page):
    """Piano: 50.000,01 euro, esito positivo (caso al limite: primo scaglione con avvio 110).
    Atteso (piano): spese di avvio 110 (art. 28) + Tabella A; il tool: 1.060 + IVA = 1.293,20.
    """
    r = _tool(valore_controversia=50000.01, esito="positivo")
    s = _site(page, "150", incontri=1, accordo=1)
    assert_close(r["totale_per_parte"], _site_total(s), TOL, "totale per parte IVA inclusa")


def test_ultimo_euro_fascia_25_50k(page):
    """Caso al limite: 50.000,00 euro (ultimo valore dello scaglione 25.000,01-50.000, avvio 75).
    Atteso: DM 150/2023 art. 28 avvio 75 + primo incontro + Tabella A +10%; tool 720 + IVA.
    """
    r = _tool(valore_controversia=50000, esito="positivo")
    s = _site(page, "140", incontri=1, accordo=1)
    assert_close(r["totale_per_parte"], _site_total(s), TOL, "totale per parte IVA inclusa")


def test_accordo_dopo_primo_incontro(page):
    """Opzione enumerata: accordo raggiunto dopo il primo incontro (aumento 25%, art. 30 DM
    150/2023). Il tool non distingue il momento dell'accordo: 'positivo' = 146,40 per 1.000 euro.
    """
    r = _tool(valore_controversia=1000, esito="positivo")
    s = _site(page, "100", incontri=2, accordo=1)
    assert_close(r["totale_per_parte"], _site_total(s), TOL, "totale per parte IVA inclusa")


def test_tabella_a_componente_primo_scaglione(page):
    """Componente: importo della Tabella A (valore medio, DM 150/2023) fino a 1.000 euro
    confrontato con l'indennita' 'positivo' del tool (120)."""
    r = _tool(valore_controversia=1000, esito="positivo")
    s = _site(page, "100", incontri=1, accordo=1)
    assert_close(r["indennita_per_parte"], s["tabella_a_medio"], TOL, "Tabella A valore medio")


def test_tabella_a_componente_150k_250k(page):
    """Caso al limite: 150.000,01 euro. Il DM 150/2023 distingue gli scaglioni 50-150k e
    150-250k; il tool li fonde in un unico scaglione 50.000,01-250.000 (1.060 euro)."""
    r = _tool(valore_controversia=150000.01, esito="positivo")
    s = _site(page, "160", incontri=1, accordo=1)
    assert_close(r["indennita_per_parte"], s["tabella_a_medio"], TOL, "Tabella A valore medio")


def test_mediazione_obbligatoria(page):
    """Opzione enumerata del sito: materia obbligatoria (importi ridotti). Il tool non ha il
    parametro, quindi il caso non e' confrontabile."""
    pytest.skip(
        "non confrontabile: il tool non distingue la mediazione obbligatoria/demandata "
        "(il sito riduce gli importi: 1.000 euro, accordo al primo incontro -> avvio 32, "
        "primo incontro 48, Tabella A medio 96)"
    )

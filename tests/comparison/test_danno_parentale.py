"""Benchmark danno_parentale vs avvocatoandreani.it (Milano and Roma calculators).

The tool places an amount inside a min-max range (the pre-2022 Milan "forbice"
revalued by 1.162268, and a scaled estimate for Rome). The site implements the
point-based tables (Milan 2024: punto 3.911 EUR for parents/children/spouse,
1.698 EUR for siblings/grandparents/grandchildren; Rome 2025: punto 11.549,20).
The site asks for data the tool does not receive (ages, cohabitation, other
relatives, intensity), so point values are generally not comparable: the
comparable quantities are the range ceilings (the Milan "tetto massimo") and
the inclusion of the site's value inside the tool's range.

Norm: Cass. SU 26972/2008; Cass. 10579/2021 (point-based table required);
Osservatorio giustizia civile Milano, tabella perdita rapporto parentale 2024;
Tribunale di Roma, tabella perdita parentale 2025.

Site driving notes: the submit button click is intercepted by an ad overlay,
so the form is submitted with form.requestSubmit(); checkboxes are set via JS.
"""

import os
import re
import sys

os.environ.setdefault("LEGAL_TODAY", "2026-09-25")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import pytest

from tests.comparison.conftest import accept_cookies, assert_close, parse_euro

MILANO = "https://www.avvocatoandreani.it/servizi/calcolo-danno-perdita-parentale-tribunale-milano.php"
ROMA = "https://www.avvocatoandreani.it/servizi/calcolo-risarcimento-danno-perdita-parentale.php"


def _tool(**kwargs):
    import src.server  # noqa: F401  (registers all modules)
    from src.tools.risarcimento_danni import danno_parentale

    fn = getattr(danno_parentale, "fn", danno_parentale)
    return fn(**kwargs)


def _set_checkbox(page, name, value):
    page.evaluate(
        "([n, c]) => { const e = document.querySelector(`[name='${n}']`);"
        " e.checked = c; e.dispatchEvent(new Event('change', {bubbles: true})); }",
        [name, value],
    )


def _submit(page, form_id):
    page.evaluate(
        "f => document.getElementById(f).requestSubmit(document.getElementById('btn-calc'))",
        form_id,
    )
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(2500)
    return page.inner_text("body")


def _milano(page, parentela, eta_congiunto, eta_vittima, convivenza, altri, relazione, anno="2024"):
    """Drive the Milan calculator; returns dict with importo, minimo, massimo, punto."""
    page.goto(MILANO, timeout=60000, wait_until="domcontentloaded")
    accept_cookies(page)
    page.wait_for_timeout(1500)
    page.select_option("#Anno", anno)
    page.select_option("#Parentela", parentela)
    page.wait_for_timeout(400)
    page.select_option("#EtaCongiunto", str(eta_congiunto))
    page.select_option("#EtaVittima", str(eta_vittima))
    _set_checkbox(page, "Convivenza", convivenza)
    page.select_option("#AltriFamiliari", str(altri))
    page.select_option("#Relazione", str(relazione))
    text = _submit(page, "DannoParentaleMilano")
    m_imp = re.search(r"IMPORTO del RISARCIMENTO(?: \(\*\))?\s*€\s*([\d.,]+)", text)
    m_rng = re.search(r"minimo di €\s*([\d.,]+) ad un massimo di €\s*([\d.,]+)", text)
    m_pt = re.search(r"Valore del Punto Base:\s*€\s*([\d.,]+)", text)
    assert m_imp and m_rng, f"risultato non leggibile dal sito:\n{text[:1500]}"
    return {
        "importo": parse_euro(m_imp.group(1)),
        "minimo": parse_euro(m_rng.group(1)),
        "massimo": parse_euro(m_rng.group(2).rstrip(".")),
        "punto": parse_euro(m_pt.group(1)) if m_pt else None,
        "tetto": "tetto massimo" in text,
    }


def _roma(page, parentela, eta_vittima, eta_congiunto, convivenza, altri_conv, altri_nc, anno="2025"):
    page.goto(ROMA, timeout=60000, wait_until="domcontentloaded")
    accept_cookies(page)
    page.wait_for_timeout(1500)
    page.select_option("select[name='Anno']", anno)
    page.select_option("select[name='Parentela']", parentela)
    page.select_option("select[name='EtaVittima']", str(eta_vittima))
    page.select_option("select[name='EtaCongiunto']", str(eta_congiunto))
    _set_checkbox(page, "Convivenza", convivenza)
    _set_checkbox(page, "AltriConviventi", altri_conv)
    _set_checkbox(page, "AltriFamiliari", altri_nc)
    text = _submit(page, "DannoParentale")
    m_imp = re.search(r"IMPORTO del RISARCIMENTO\s*€\s*([\d.,]+)", text)
    m_rng = re.search(r"tra €\s*([\d.,]+) e €\s*([\d.,]+)", text)
    assert m_imp, f"risultato non leggibile dal sito:\n{text[:1500]}"
    return {
        "importo": parse_euro(m_imp.group(1)),
        "minimo": parse_euro(m_rng.group(1)) if m_rng else None,
        "massimo": parse_euro(m_rng.group(2).rstrip(".")) if m_rng else None,
    }


def test_milano_genitore_perde_figlio_mediana(page):
    """Piano caso 1: figlio/genitore, Milano, 50%. Tool 293.327,39 (range 195.551,59-391.103,18).
    Sito: vittima 20, genitore 50 convivente, nessun altro familiare, intensita' media (15 punti).
    Atteso del piano: il valore a punti cade nel range del tool (confronto di inclusione)."""
    r = _tool(vittima="figlio", superstite="genitore")
    s = _milano(page, "genitore", 50, 20, True, 0, 15)
    print(f"tool={r['importo_liquidato']} sito={s['importo']} range_sito={s['minimo']}-{s['massimo']}")
    assert r["importo_minimo"] <= s["importo"] <= r["importo_massimo"]


def test_milano_tetto_genitori_figli_coniuge(page):
    """Limite: tetto massimo della categoria genitori/figli/coniuge (Milano 2024).
    Tool pct=100 -> 391.103,18 (336.500 x 1,162268); il sito limita al tetto della tabella 2024."""
    r = _tool(vittima="figlio", superstite="genitore", personalizzazione_pct=100)
    s = _milano(page, "genitore", 50, 20, True, 0, 30)
    print(f"tool={r['importo_liquidato']} sito={s['importo']} massimo_sito={s['massimo']}")
    assert_close(r["importo_liquidato"], s["massimo"], tolerance=0.01, label="tetto genitori")


def test_milano_fratello_minimo(page):
    """Piano caso 2: fratello/fratello, Milano, pct=0 -> tool 28.301,23 (minimo del range).
    Sito: fratelli 45 e 40, non conviventi, 2 altri familiari, intensita' minima (0 punti).
    Confronto di inclusione: il valore a punti deve cadere nel range del tool."""
    r = _tool(vittima="fratello", superstite="fratello", tabella="milano", personalizzazione_pct=0)
    s = _milano(page, "fratello", 45, 40, False, 2, 0)
    print(f"tool={r['importo_liquidato']} sito={s['importo']}")
    assert r["importo_minimo"] <= s["importo"] <= r["importo_massimo"]


def test_milano_tetto_fratelli(page):
    """Piano caso 3 (limite): fratello/fratello, Milano, pct=100 -> tool 169.830,60.
    Sito: vittima 18, fratello 20 convivente, nessun altro familiare, intensita' massima
    (106 punti x 1.698 = 179.988, ridotto al tetto massimo)."""
    r = _tool(vittima="fratello", superstite="fratello", tabella="milano", personalizzazione_pct=100)
    s = _milano(page, "fratello", 20, 18, True, 0, 30)
    print(f"tool={r['importo_liquidato']} sito={s['importo']} tetto={s['tetto']}")
    assert_close(r["importo_liquidato"], s["importo"], tolerance=0.01, label="tetto fratelli")


def test_milano_figlio_configurazione_minima_sotto_range(page):
    """Limite: figlio di 70 anni che perde il genitore di 95, non convivente, oltre 3 familiari,
    intensita' minima. Il sistema a punti scende sotto il minimo della vecchia forbice
    (tool: minimo 195.551,59): il valore del sito deve cadere nel range del tool."""
    r = _tool(vittima="genitore", superstite="figlio", personalizzazione_pct=0)
    s = _milano(page, "figlio", 70, 95, False, 99, 0)
    print(f"tool_min={r['importo_minimo']} sito={s['importo']} range_sito={s['minimo']}-{s['massimo']}")
    assert r["importo_minimo"] <= s["importo"] <= r["importo_massimo"]


def test_roma_coniuge(page):
    """Piano caso 4: coniuge/coniuge, tabella Roma, 50% -> tool 285.747,39 (stima 2024).
    Sito (tabella Roma 2025, la piu' recente; il sito non offre il 2024): coniugi di 60 anni
    conviventi, nessun altro familiare. Confronto di inclusione nel range del tool."""
    r = _tool(vittima="coniuge", superstite="coniuge", tabella="roma")
    s = _roma(page, "coniuge", 60, 60, True, False, False)
    print(f"tool={r['importo_liquidato']} sito={s['importo']} range_sito={s['minimo']}-{s['massimo']}")
    assert r["importo_minimo"] <= s["importo"] <= r["importo_massimo"]


def test_roma_coniuge_aumento_senza_altri_familiari(page):
    """Limite: stessa configurazione del caso Roma. In assenza di altri familiari fino al 2 grado
    la tabella di Roma consente l'aumento da 1/3 a 1/2 del punteggio: il massimo del sito
    deve restare entro il massimo del tool (380.996,52)."""
    r = _tool(vittima="coniuge", superstite="coniuge", tabella="roma", personalizzazione_pct=100)
    s = _roma(page, "coniuge", 60, 60, True, False, False)
    print(f"tool_max={r['importo_massimo']} sito_max={s['massimo']}")
    assert s["massimo"] is not None
    assert s["massimo"] <= r["importo_massimo"] + 0.01


def test_coppia_non_prevista(page):
    """Piano caso 5: nonno/fratello -> errore con elenco coppie ammesse.
    Il sito offre figure che il tool non prevede (zio, convivente di fatto, parte dell'unione
    civile a Milano; avo, cugino, convivente a Roma): non confrontabile."""
    r = _tool(vittima="nonno", superstite="fratello")
    assert "errore" in r and "fratello/fratello" in r["rapporti_disponibili"]
    page.goto(MILANO, timeout=60000, wait_until="domcontentloaded")
    accept_cookies(page)
    opts = [o.get_attribute("value") for o in page.query_selector_all("#Parentela option")]
    extra = [o for o in opts if o and o not in {"genitore", "figlio", "fratello", "nonno", "nipote"}]
    pytest.skip(f"coppia non prevista dal tool; figure solo sul sito (Milano): {extra}")

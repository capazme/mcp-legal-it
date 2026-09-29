"""Benchmark detrazione_lavoro_dipendente vs avvocatoandreani.it (Fase 1).

Page: https://www.avvocatoandreani.it/servizi/calcolo-detrazione-redditi-lavoro-dipendente.php
(form ``CalcoloDetrazioneLavoroDipendente``: RedditoComplessivoDetrazione, DeduzioneAbitazionePrincipale,
TipoRedditoLavoroDipendente 1=tempo indeterminato / 2=tempo determinato, GiorniLavoroDipendente; submit #btn-calc).
The result is the "RN7 Col.1 Detrazione per lavoro dipendente" row of the "SVILUPPO del CALCOLO" table.

Norm: art. 13, co. 1, 1.1 and 6, TUIR (D.P.R. 917/1986), text in force for tax years 2025 and 2026
(lett. a) 1.955 euro as amended by D.Lgs. 216/2023 and made permanent by L. 207/2024).
- co. 1 lett. a): reddito <= 15.000 -> 1.955, but the amount actually due (after the days ratio) is never
  below 690 euro (1.380 euro for fixed-term contracts);
- co. 1 lett. b): 15.000 < reddito <= 28.000 -> 1.910 + 1.190 x (28.000 - reddito) / 13.000;
- co. 1 lett. c): 28.000 < reddito <= 50.000 -> 1.910 x (50.000 - reddito) / 22.000;
- co. 1.1: the co. 1 deduction is increased by 65 euro when 25.000 < reddito <= 35.000 (lett. b and c);
- co. 6: the ratios are taken at their first four decimals.

Year: the site declares "Periodo di imposta 2025 - Dichiarazione dei redditi 2026" and offers no year
selector; the tool declares the 2026 table. Art. 13 co. 1/1.1 has the same content for 2025 and 2026, so the
two are comparable.

Tolerance: 0,50 euro instead of the default 0,01. The site states that "gli importi inseriti e la detrazione
calcolata sono sempre arrotondati all'euro" (AdE convention: amounts in the return are in whole euros) while the
tool returns cents. The largest gap caused by that rounding alone is 0,50 euro (plus a few cents from the
four-decimal truncation of the ratio, art. 13 co. 6, which the tool does not apply). Every gap above 0,50 euro is
a genuine difference and must stay red.
"""

import re

import pytest

from tests.comparison.conftest import accept_cookies, assert_close, goto, parse_euro

PAGE = "calcolo-detrazione-redditi-lavoro-dipendente.php"
# Whole-euro rounding on the site (see module docstring).
TOL_ARROTONDAMENTO_EURO = 0.50


def _tool(reddito: float, giorni: int, tipo: str = "1") -> dict:
    import src.server  # noqa: F401  (registers every module, avoids circular imports)
    from src.tools.dichiarazione_redditi import detrazione_lavoro_dipendente

    fn = getattr(detrazione_lavoro_dipendente, "fn", detrazione_lavoro_dipendente)
    # site TipoRedditoLavoroDipendente "2" = fixed-term contract (art. 13 co. 1 lett. a, minimum 1,380)
    return fn(reddito_complessivo=reddito, giorni_lavoro=giorni, tempo_determinato=(tipo == "2"))


FORM = "CalcoloDetrazioneLavoroDipendente"


def _site(page, reddito: int, giorni: int, tipo: str = "1") -> tuple[float, str]:
    """Drive the site form and return (RN7 Col.1 amount, full 'SVILUPPO del CALCOLO' text).

    The Quantcast CMP overlay (#qc-cmp2-container) appears ~1-2 s after load, after ``goto`` has already
    removed it once: it traps focus (``page.fill`` then leaves the days field empty and the site shows no
    result) and intercepts clicks. So the overlay is removed again, the values are set on the DOM
    elements directly, checked, and the form is submitted with ``requestSubmit`` (the submitter keeps
    ``Op=Calcola`` in the POST).
    """
    goto(page, PAGE, wait_ms=2500)
    accept_cookies(page)
    valori = {
        "RedditoComplessivoDetrazione": str(reddito),
        "DeduzioneAbitazionePrincipale": "",
        "TipoRedditoLavoroDipendente": tipo,
        "GiorniLavoroDipendente": str(giorni),
    }
    letti = page.evaluate(
        """([formName, valori]) => {
            const f = document.forms[formName];
            for (const [k, v] of Object.entries(valori)) { f.elements[k].value = v; }
            return Object.fromEntries(Object.keys(valori).map(k => [k, f.elements[k].value]));
        }""",
        [FORM, valori],
    )
    assert letti == valori, f"form del sito non compilato come richiesto: {letti} != {valori}"
    with page.expect_navigation(timeout=60000):
        page.evaluate(
            "(formName) => document.forms[formName].requestSubmit(document.getElementById('btn-calc'))",
            FORM,
        )
    page.wait_for_timeout(1500)
    sviluppo = ""
    for table in page.query_selector_all("table"):
        text = table.inner_text().strip()
        if "SVILUPPO del CALCOLO" in text:
            sviluppo = text
            break
    if not sviluppo:
        pytest.fail(f"errore_sito: nessuna tabella 'SVILUPPO del CALCOLO' per reddito={reddito}, giorni={giorni}")
    m = re.search(r"RN7 Col\.1.*?€\s*([\d.]+,\d{2})", sviluppo, re.DOTALL)
    if not m:
        pytest.fail(f"errore_sito: riga RN7 Col.1 non trovata in:\n{sviluppo}")
    return parse_euro(m.group(1)), sviluppo


# (id, reddito, giorni, tipo contratto sul sito, atteso del piano / norma)
CASI = [
    # Plan: "Limite della prima fascia" -> 1.955,00 (art. 13 co. 1 lett. a TUIR).
    ("limite_prima_fascia_15000", 15000, 365, "1", "1.955,00 - art. 13 co. 1 lett. a"),
    # Plan: "Un euro sopra la prima fascia" -> 1.910 + 1.190 x 0,9999 = 3.099,88 with the ratio truncated
    # (co. 6); tool 3.099,91 (untruncated ratio). Jump from 1.955 to ~3.100 is wanted by the law (lett. b).
    ("sopra_prima_fascia_15001", 15001, 365, "1", "3.099,88 (co. 6: quoziente 0,9999) - art. 13 co. 1 lett. b"),
    # Plan: "Reddito 30.000: maggiorazione di 65 euro" -> 1.910 x 0,9090 = 1.736,19 + 65 (co. 1.1) = 1.801,19;
    # the tool returns 1.736,36 (no co. 1.1 increase).
    ("maggiorazione_65_reddito_30000", 30000, 365, "1", "1.801,19 - art. 13 co. 1 lett. c + co. 1.1"),
    # Plan: "Reddito 10.000 per 90 giorni: minimo di legge" -> 1.955 x 90/365 = 482,05 but never below
    # 690 (tempo indeterminato), art. 13 co. 1 lett. a: expected 690,00; tool 482,05.
    ("minimo_690_giorni_90", 10000, 90, "1", "690,00 - art. 13 co. 1 lett. a (minimo)"),
    # Plan: "Limite di azzeramento" -> 0,00 (art. 13 co. 1 lett. c: 50.000 gives ratio 0).
    ("azzeramento_50000", 50000, 365, "1", "0,00 - art. 13 co. 1 lett. c"),
    # Boundary (added): 25.000 is NOT above 25.000 -> no co. 1.1 increase.
    # 1.910 + 1.190 x 0,2307 = 2.184,53 (co. 6); lett. b.
    ("soglia_25000_senza_maggiorazione", 25000, 365, "1", "2.184,53 - art. 13 co. 1 lett. b, co. 1.1 non si applica"),
    # Boundary (added): 25.001 -> co. 1.1 increase of 65 euro applies.
    # 1.910 + 1.190 x 0,2306 = 2.184,41 + 65 = 2.249,41.
    ("soglia_25001_con_maggiorazione", 25001, 365, "1", "2.249,41 - art. 13 co. 1 lett. b + co. 1.1"),
    # Boundary (added): 28.000 closes lett. b -> 1.910 (+65 per co. 1.1) = 1.975,00.
    ("confine_scaglione_28000", 28000, 365, "1", "1.975,00 - art. 13 co. 1 lett. b + co. 1.1"),
    # Boundary (added): 35.000 still inside co. 1.1 -> 1.910 x 0,6818 = 1.302,24 + 65 = 1.367,24.
    ("soglia_35000_con_maggiorazione", 35000, 365, "1", "1.367,24 - art. 13 co. 1 lett. c + co. 1.1"),
    # Boundary (added): 35.001 is above 35.000 -> no increase. 1.910 x 0,6817 = 1.302,05.
    ("soglia_35001_senza_maggiorazione", 35001, 365, "1", "1.302,05 - art. 13 co. 1 lett. c"),
    # Added: lett. b with a days ratio. (1.910 + 1.190 x 0,6153) x 200/365 = 1.447,79.
    ("rapporto_giorni_20000_200gg", 20000, 200, "1", "1.447,79 - art. 13 co. 1 lett. b, rapportata ai giorni"),
    # Boundary (added): 1.955 x 129/365 = 690,95 is above the 690 floor -> floor not triggered.
    ("minimo_690_non_scatta_129gg", 10000, 129, "1", "690,95 - art. 13 co. 1 lett. a"),
    # Boundary (added): 1.955 x 128/365 = 685,59 is below the floor -> 690,00.
    ("minimo_690_scatta_128gg", 10000, 128, "1", "690,00 - art. 13 co. 1 lett. a (minimo)"),
    # Enumerated option (added): tempo determinato, full year -> 1.955 > 1.380, floor irrelevant.
    ("tempo_determinato_anno_intero", 10000, 365, "2", "1.955,00 - art. 13 co. 1 lett. a"),
    # Enumerated option (added): tempo determinato, 90 days -> 482,05 below the 1.380 floor -> 1.380,00.
    # The tool has no contract-type parameter, so it cannot apply this floor.
    ("tempo_determinato_minimo_1380", 10000, 90, "2", "1.380,00 - art. 13 co. 1 lett. a (minimo t.d.)"),
]


@pytest.mark.parametrize(
    "reddito,giorni,tipo,atteso",
    [c[1:] for c in CASI],
    ids=[c[0] for c in CASI],
)
def test_detrazione_lavoro_dipendente_vs_sito(page, reddito, giorni, tipo, atteso):
    tool = _tool(reddito, giorni, tipo)
    assert "errore" not in tool, tool
    tool_value = tool["detrazione_rapportata"]
    site_value, sviluppo = _site(page, reddito, giorni, tipo)
    page.wait_for_timeout(1500)  # be gentle with the site between cases
    print(f"CONFRONTO reddito={reddito} giorni={giorni} tipo={tipo}: tool={tool_value:.2f} sito={site_value:.2f}")
    assert_close(
        tool_value,
        site_value,
        tolerance=TOL_ARROTONDAMENTO_EURO,
        label=(
            f"reddito={reddito} giorni={giorni} tipo={tipo} (atteso piano/norma: {atteso}); "
            f"sviluppo sito: {' | '.join(line.strip() for line in sviluppo.splitlines() if line.strip())}"
        ),
    )

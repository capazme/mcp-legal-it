"""Benchmark detrazione_pensione vs avvocatoandreani.it (Fase 1).

Page: https://www.avvocatoandreani.it/servizi/calcolo-detrazione-redditi-pensione.php
(form ``CalcoloDetrazionePensione``: RedditoComplessivoDetrazione (RN1), DeduzioneAbitazionePrincipale (RN2),
GiorniPensione (RC6 Col.2); submit #btn-calc). The result is the "RN7 Col.2 Detrazione per redditi di pensione"
row of the "SVILUPPO del CALCOLO" table (its label may carry "( detrazione minima spettante )" or
"( rapportata a N giorni )" before the amount).

Norm: art. 13, co. 3, 3-bis, 6 and 6-bis, TUIR (D.P.R. 917/1986), text in force (checked via cite_law on
2026-09-25; same content for tax years 2025 and 2026, as amended by L. 234/2021):
- co. 3 lett. a): reddito <= 8.500 -> 1.955 "rapportata al periodo di pensione nell'anno"; the amount actually
  due is never below 713 euro;
- co. 3 lett. b): 8.500 < reddito <= 28.000 -> 700 + 1.255 x (28.000 - reddito) / 19.500;
- co. 3 lett. c): 28.000 < reddito <= 50.000 -> 700 x (50.000 - reddito) / 22.000;
- co. 3-bis: the co. 3 deduction is increased by 50 euro when 25.000 < reddito <= 29.000;
- co. 6: the ratios are taken at their first four decimals;
- co. 6-bis: reddito complessivo net of the main dwelling (the site's RN2 field; the tool has no such
  parameter, the caller passes the net income).

Year: the site declares "Periodo di imposta 2025 - Dichiarazione dei redditi 2026" and offers no year
selector; the tool has no year parameter and states "scaglioni invariati rispetto al 2024". Art. 13 co. 3/3-bis
has the same content for 2025 and 2026, so the two are comparable.

Tolerance: 0,50 euro instead of the default 0,01. The site states that "gli importi inseriti e la detrazione
calcolata sono sempre arrotondati all'euro superiore o inferiore come indicato dall'Agenzia delle entrate"
(amounts in the return are in whole euros) while the tool returns cents. The largest gap caused by that rounding
alone is 0,50 euro (plus a few cents from the four-decimal truncation of the ratio, co. 6, which the tool does
not apply). Every gap above 0,50 euro is a genuine difference and must stay red.
"""

import re

import pytest

from tests.comparison.conftest import accept_cookies, assert_close, goto, parse_euro, submit_form

PAGE = "calcolo-detrazione-redditi-pensione.php"
# Whole-euro rounding on the site (see module docstring).
TOL_ARROTONDAMENTO_EURO = 0.50


def _tool(reddito: float, giorni: int) -> dict:
    import src.server  # noqa: F401  (registers every module, avoids circular imports)
    from src.tools.dichiarazione_redditi import detrazione_pensione

    fn = getattr(detrazione_pensione, "fn", detrazione_pensione)
    return fn(reddito_complessivo=reddito, giorni=giorni)


def _site(page, reddito: int, giorni: int, deduzione_abitazione: int | None = None) -> tuple[float, str]:
    """Drive the site form and return (RN7 Col.2 amount, full 'SVILUPPO del CALCOLO' text)."""
    goto(page, PAGE, wait_ms=1500)
    # The cookie banner (#accept-btn) shows up after domcontentloaded, when goto() has already checked for it:
    # left open, it sits on top of #btn-calc and swallows the forced click, so the form is never submitted.
    accept_cookies(page)
    page.fill("input[name='RedditoComplessivoDetrazione']", str(reddito))
    page.fill(
        "input[name='DeduzioneAbitazionePrincipale']",
        "" if deduzione_abitazione is None else str(deduzione_abitazione),
    )
    page.fill("input[name='GiorniPensione']", str(giorni))
    submit_form(page, btn_selector="#btn-calc")
    sviluppo = ""
    for table in page.query_selector_all("table"):
        text = table.inner_text().strip()
        if "SVILUPPO del CALCOLO" in text:
            sviluppo = text
            break
    if not sviluppo:
        pytest.fail(f"errore_sito: nessuna tabella 'SVILUPPO del CALCOLO' per reddito={reddito}, giorni={giorni}")
    m = re.search(r"RN7 Col\.2.*?€\s*([\d.]+,\d{2})", sviluppo, re.DOTALL)
    if not m:
        pytest.fail(f"errore_sito: riga RN7 Col.2 non trovata in:\n{sviluppo}")
    return parse_euro(m.group(1)), sviluppo


# (id, reddito passed to the tool, giorni, reddito on the site (RN1), deduzione abitazione (RN2), atteso)
# "atteso" = value required by the norm (co. 6 truncation applied), then rounded to the euro as on the site.
CASI = [
    # Plan: "Limite della prima fascia" -> 1.955,00 (art. 13 co. 3 lett. a TUIR).
    ("limite_prima_fascia_8500", 8500, 365, 8500, None, "1.955,00 - art. 13 co. 3 lett. a"),
    # Plan: "Pensione per 100 giorni: minimo di legge" -> 1.955 x 100/365 = 535,62, but never below 713
    # (art. 13 co. 3 lett. a, second sentence): expected 713,00; tool 535,62.
    ("minimo_713_giorni_100", 8000, 100, 8000, None, "713,00 - art. 13 co. 3 lett. a (minimo)"),
    # Plan: "Reddito 27.000: maggiorazione di 50 euro" -> 700 + 1.255 x 0,0512 = 764,26 + 50 (co. 3-bis)
    # = 814,26 (814 on the site); tool 764,36 (no co. 3-bis increase, untruncated ratio).
    ("maggiorazione_50_reddito_27000", 27000, 365, 27000, None, "814,26 - art. 13 co. 3 lett. b + co. 3-bis"),
    # Plan: "Terza fascia" -> 700 x 0,4545 = 318,15 (co. 6); tool 318,18.
    ("terza_fascia_40000", 40000, 365, 40000, None, "318,15 - art. 13 co. 3 lett. c"),
    # Boundary (added): one euro above lett. a -> lett. b, ratio 19.499/19.500 = 0,9999 (co. 6):
    # 700 + 1.255 x 0,9999 = 1.954,87; the 713 floor belongs to lett. a only.
    ("sopra_prima_fascia_8501", 8501, 365, 8501, None, "1.954,87 - art. 13 co. 3 lett. b"),
    # Boundary (added): 25.000 is NOT above 25.000 -> no co. 3-bis increase.
    # 700 + 1.255 x 0,1538 = 893,02 (co. 6).
    ("soglia_25000_senza_maggiorazione", 25000, 365, 25000, None, "893,02 - art. 13 co. 3 lett. b, co. 3-bis non si applica"),
    # Boundary (added): 25.001 -> co. 3-bis applies. 700 + 1.255 x 0,1537 = 892,89 + 50 = 942,89; tool 893,01.
    ("soglia_25001_con_maggiorazione", 25001, 365, 25001, None, "942,89 - art. 13 co. 3 lett. b + co. 3-bis"),
    # Boundary (added): 28.000 closes lett. b -> 700 + 1.255 x 0 = 700 + 50 (co. 3-bis) = 750,00.
    ("confine_scaglione_28000", 28000, 365, 28000, None, "750,00 - art. 13 co. 3 lett. b + co. 3-bis"),
    # Boundary (added): 28.001 opens lett. c -> 700 x 0,9999 = 699,93 + 50 = 749,93.
    ("confine_scaglione_28001", 28001, 365, 28001, None, "749,93 - art. 13 co. 3 lett. c + co. 3-bis"),
    # Boundary (added): 29.000 still inside co. 3-bis -> 700 x 0,9545 = 668,15 + 50 = 718,15.
    ("soglia_29000_con_maggiorazione", 29000, 365, 29000, None, "718,15 - art. 13 co. 3 lett. c + co. 3-bis"),
    # Boundary (added): 29.001 is above 29.000 -> no increase. 700 x 0,9545 = 668,15.
    ("soglia_29001_senza_maggiorazione", 29001, 365, 29001, None, "668,15 - art. 13 co. 3 lett. c"),
    # Plan-adjacent boundary (added): 50.000 gives ratio 0 -> 0,00 (art. 13 co. 3 lett. c).
    ("azzeramento_50000", 50000, 365, 50000, None, "0,00 - art. 13 co. 3 lett. c"),
    # Boundary (added): 1.955 x 134/365 = 717,73 is above the 713 floor -> floor not triggered.
    ("minimo_713_non_scatta_134gg", 8000, 134, 8000, None, "717,73 - art. 13 co. 3 lett. a"),
    # Boundary (added): 1.955 x 133/365 = 712,37 is below the floor -> 713,00; tool 712,37.
    ("minimo_713_scatta_133gg", 8000, 133, 8000, None, "713,00 - art. 13 co. 3 lett. a (minimo)"),
    # Boundary (added): the 713 floor is written in lett. a only -> not applicable at 9.000.
    # (700 + 1.255 x 0,9743) x 100/365 = 526,78.
    ("minimo_non_applicabile_9000_100gg", 9000, 100, 9000, None, "526,78 - art. 13 co. 3 lett. b"),
    # Added: co. 3-bis with a days ratio. Co. 3 deduction rapportata: (700 + 1.255 x 0,0512) x 180/365 = 376,89;
    # co. 3-bis adds 50 euro to "la detrazione spettante ai sensi del comma 3" (the text does not scale the 50
    # by the days) -> 426,89. Tool 376,94.
    ("maggiorazione_con_rapporto_180gg", 27000, 180, 27000, None, "426,89 - art. 13 co. 3 lett. b rapportata + co. 3-bis"),
    # Enumerated option (added): RN2 "Deduzione abitazione principale" (co. 6-bis). The site nets 26.000 - 1.000;
    # the tool receives the net 25.000 directly. Expected as the 25.000 case: 893,02.
    ("deduzione_abitazione_principale_6bis", 25000, 365, 26000, 1000, "893,02 - art. 13 co. 3 lett. b + co. 6-bis"),
]


@pytest.mark.parametrize(
    "reddito_tool,giorni,reddito_sito,deduzione,atteso",
    [c[1:] for c in CASI],
    ids=[c[0] for c in CASI],
)
def test_detrazione_pensione_vs_sito(page, reddito_tool, giorni, reddito_sito, deduzione, atteso):
    tool = _tool(reddito_tool, giorni)
    assert "errore" not in tool, tool
    tool_value = tool["detrazione_rapportata"]
    site_value, sviluppo = _site(page, reddito_sito, giorni, deduzione)
    page.wait_for_timeout(1500)  # be gentle with the site between cases
    print(f"CONFRONTO reddito={reddito_sito} deduz={deduzione} giorni={giorni}: tool={tool_value:.2f} sito={site_value:.2f}")
    assert_close(
        tool_value,
        site_value,
        tolerance=TOL_ARROTONDAMENTO_EURO,
        label=(
            f"reddito tool={reddito_tool} sito={reddito_sito} deduz={deduzione} giorni={giorni} "
            f"(atteso piano/norma: {atteso}); "
            f"sviluppo sito: {' | '.join(line.strip() for line in sviluppo.splitlines() if line.strip())}"
        ),
    )

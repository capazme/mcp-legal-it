"""Comparison tests: compenso_ctu vs avvocatoandreani.it (Calcolo Compenso CTU).

Site page: https://www.avvocatoandreani.it/servizi/calcolo-compenso-onorario-ctu-liquidazione-tariffe.php
Server-side form ``OnorariCtu`` (POST). Two independent sections, totalised in a final
"RIEPILOGO degli ONORARI - DPR 115/2002":

- ONORARI a VACAZIONI: start/end date of the perizia (the page asks the server, via
  ``ajsvc.php?op=gen-getglav``, for the working days and caps the vacazioni at 4 per
  working day), ``VacazioniSuccessive`` = number of vacazioni. Every vacazione at
  EUR 14,68 (DM 30/05/2002 art. 1; after Corte cost. n. 16/2025 no reduced rate for the
  vacazioni after the first). Output: "Onorari a vacazione EUR x".
- ONORARI TABELLARI: ``ArticoloDpr`` = article of the DM 30/05/2002 (G.U. n. 182/2002),
  ``ValoreStimato`` (disabled for the fixed-fee articles), ``DefaultTar`` 1/2/3 =
  Minima/Media/Massima. Output: the scaglioni table with a "Totali:" row
  (Minimo/Medio/Massimo) or, for fixed fees, a "Minimo Medio Massimo" row; the
  RIEPILOGO line "Onorari tabellari EUR x" is the selected tariff after any reduction
  (e.g. art. 3: art. 2 halved, shown only for the selected tariff).

What the tool computes (src/tools/parcelle_professionisti.py, ``compenso_ctu``,
Precisione: INDICATIVO): market estimates, NOT the DM tables - a percentage band on
``valore_causa`` (``calcolo_a_percentuale``: compenso_min/compenso_max) and an hourly
band on ``ore_lavoro`` (``calcolo_orario``: compenso_min/compenso_max). The docstring
itself says the DM 30/05/2002 tables and the vacazioni ex art. 4 L. 319/1980 are not
reproduced, so the cases below document the gap type by type.

How tool and site are lined up (the tool gives a band, the site the legal tariff):
- percentage band  -> site tabellari: tool compenso_min == site liquidation at
  tariffa Minima, tool compenso_max == site liquidation at tariffa Massima (RIEPILOGO
  "Onorari tabellari", i.e. after the article's reduction and the site's floor);
- hourly band      -> site vacazioni: ore / 2 vacazioni (art. 4 co. 2 L. 319/1980,
  the vacazione is two hours; a residual fraction counts as half a vacazione up to
  1h15 and as a whole one beyond, art. 4 co. 4); both tool compenso_min and
  compenso_max must equal the single site amount.
- tipo_incarico -> DM 30/05/2002 article (our mapping, stated per test):
  perizia_immobiliare -> art. 13 co. 1 (estimo, scaglioni sull'importo stimato);
  perizia_contabile   -> art. 2 (materia amministrativa, contabile e fiscale);
  perizia_medica      -> art. 21 (accertamenti medici sulla persona, EUR 48,03-290,77);
  stima_danni         -> art. 3 (diritti a titolo di risarcimento di danni: art. 2 / 2);
  accertamenti_tecnici (ATP art. 696 c.p.c.) -> art. 11 (costruzioni edilizie e impianti:
  the DM has no ATP article, art. 11 is the usual one for building-defect ATPs).

Driver: the CMP overlay (qc-cmp2) is removed via JS before every interaction (no
consent given); the form is submitted with ``form.requestSubmit(#btn-calc)`` because
a forced click lands on the overlay and never posts. Each test uses a fresh browser
context: the site re-fills the form with the previous submission of the session.

Tolerance: 0.01 EUR (brief), compared in integer cents.
"""

import re

from tests.comparison.conftest import parse_euro

URL = "https://www.avvocatoandreani.it/servizi/calcolo-compenso-onorario-ctu-liquidazione-tariffe.php"

_RM_CMP = (
    'document.querySelectorAll("#qc-cmp2-container, .qc-cmp2-container")'
    ".forEach(el => el.remove())"
)

# 01/09/2026-15/09/2026: 12 working days on the site (end - start = 14 days minus the 2
# Sundays; Saturdays count) -> max 48 vacazioni. December 2024 below: 18 - 2 = 16.
PERIODO_2026 = ("01/09/2026", "15/09/2026")
# December 2024: a perizia wholly before Corte cost. n. 16/2025 (published 12/02/2025).
PERIODO_2024 = ("02/12/2024", "20/12/2024")

ART_ESTIMO = "Art.13 - Applicazione 1° comma"
ART_CONTABILE = "Art.2"
ART_DANNI = "Art.3"
ART_COSTRUZIONI = "Art.11"
ART_MEDICO = "Art.21"

_E = r"€\s*([\d.]+,\d{2})"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _tool(**kwargs) -> dict:
    import src.server  # noqa: F401  registers all tool modules
    from src.tools.parcelle_professionisti import compenso_ctu

    fn = getattr(compenso_ctu, "fn", compenso_ctu)
    return fn(**kwargs)


def _vacazioni_da_ore(ore: float) -> str:
    """Hours -> vacazioni as typed on the site (art. 4 co. 2 and 4 L. 319/1980).

    The vacazione is two hours; the residual fraction is paid as half a vacazione,
    and as a whole one once an hour and a quarter has passed.
    """
    intere = int(ore // 2)
    resto = ore - 2 * intere
    if resto == 0:
        n = float(intere)
    elif resto > 1.25:
        n = intere + 1.0
    else:
        n = intere + 0.5
    return str(int(n)) if n.is_integer() else f"{n:.1f}".replace(".", ",")


def _select_date(page, prefix: str, data: str) -> None:
    giorno, mese, anno = data.split("/")
    page.select_option(f"#Giorno{prefix}", giorno)
    page.select_option(f"#Mese{prefix}", mese)
    page.select_option(f"#Anno{prefix}", anno)


def _site(page, *, periodo=None, vacazioni=None, articolo=None, valore=None, tariffa="3") -> dict:
    """Drive the site once and return what its result page shows.

    Keys: errore (site validation message), giorni_lavorativi, n_vacazioni,
    vacazioni_totale, articolo, tab_min, tab_medio, tab_max (table row, before any
    reduction or floor), onorario_calcolato / onorario_ridotto / onorario_minimo (lines
    for the selected tariff), onorari_tabellari (RIEPILOGO, the liquidated amount).
    """
    page.goto(URL, timeout=60000, wait_until="domcontentloaded")
    page.wait_for_timeout(1500)
    page.evaluate(_RM_CMP)
    if periodo:
        _select_date(page, "Inizio", periodo[0])
        _select_date(page, "Fine", periodo[1])
        # the page asks the server for the working days (AJAX) and fills the hidden cap
        page.wait_for_function(
            "Number(document.getElementById('MaxVacazioniHidden').value) > 0", timeout=20000
        )
    if vacazioni is not None:
        page.fill("input[name='VacazioniSuccessive']", str(vacazioni))
    if articolo:
        page.select_option("select[name='ArticoloDpr']", articolo)
    if valore is not None:
        campo = page.locator("input[name='ValoreStimato']")
        assert campo.is_enabled(), f"{articolo}: il sito non accetta un valore stimato"
        campo.fill(f"{valore:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    page.select_option("select[name='DefaultTar']", tariffa)
    page.evaluate(_RM_CMP)
    with page.expect_navigation(timeout=60000):
        page.evaluate(
            "document.getElementById('OnorariCtu')"
            ".requestSubmit(document.getElementById('btn-calc'))"
        )
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(1500)

    body = page.inner_text("body")
    start = body.find("Calcolo Parcella CTU del")
    if start < 0:
        msg = "Un campo risulta errato o non compilato"
        return {"errore": msg if msg in body else "risultato assente"}
    end = body.find("Crea la Fattura", start)
    txt = body[start : end if end > 0 else len(body)]

    out: dict = {"errore": None}
    m = re.search(r"Giorni lavorativi:\s*(\d+)", txt)
    out["giorni_lavorativi"] = int(m.group(1)) if m else None
    m = re.search(r"Numero complessivo vacazioni\s*([\d,.]+)", txt)
    out["n_vacazioni"] = m.group(1) if m else None
    m = re.search(r"Onorari a vacazione\s*" + _E, txt)
    out["vacazioni_totale"] = parse_euro(m.group(1)) if m else None
    m = re.search(r"ONORARI TABELLARI - (.+?) - DM 182/2002", txt)
    out["articolo"] = m.group(1).strip() if m else None
    tre = r"\s*" + _E + r"\s*" + _E + r"\s*" + _E
    m = re.search(r"Totali:\s*" + _E + tre, txt)  # scaglioni, more than one
    if m:
        out["tab_min"], out["tab_medio"], out["tab_max"] = (parse_euro(m.group(i)) for i in (2, 3, 4))
    else:
        # scaglioni, a single row (no "Totali:"), or a fixed fee (no "Fino a" header)
        m = re.search(r"Fino a\s+Base calcolo\s+Minimo\s+Medio\s+Massimo\s*" + _E + r"\s*" + _E + tre, txt)
        if m:
            out["tab_min"], out["tab_medio"], out["tab_max"] = (parse_euro(m.group(i)) for i in (3, 4, 5))
        else:
            m = re.search(r"Minimo\s+Medio\s+Massimo" + tre, txt)
            if m:
                out["tab_min"], out["tab_medio"], out["tab_max"] = (parse_euro(m.group(i)) for i in (1, 2, 3))
            else:
                out["tab_min"] = out["tab_medio"] = out["tab_max"] = None
    m = re.search(r"Onorario calcolato:\s*" + _E, txt)
    out["onorario_calcolato"] = parse_euro(m.group(1)) if m else None
    m = re.search(r"Onorario ridotto[^:]*:\s*" + _E, txt)
    out["onorario_ridotto"] = parse_euro(m.group(1)) if m else None
    m = re.search(r"Onorario minimo:\s*" + _E, txt)
    out["onorario_minimo"] = parse_euro(m.group(1)) if m else None
    m = re.search(r"Onorari tabellari\s*" + _E, txt)
    out["onorari_tabellari"] = parse_euro(m.group(1)) if m else None
    return out


def _site_min_max(page, **kwargs) -> tuple[dict, dict]:
    """Two submissions, "Tariffa Predefinita" Minima then Massima.

    The liquidated amount is the RIEPILOGO line "Onorari tabellari", which applies the
    article's reduction (art. 3: half) and the DM floor when the scaglioni total is below
    it ("compenso non inferiore a euro 145,12", DM 30/05/2002 artt. 2, 3, 11 and 13; the
    site prints "Onorario minimo: EUR 145,12"); both are shown only for the selected
    tariff, hence one request per tariff.
    """
    s_min = _site(page, tariffa="1", **kwargs)
    assert s_min["errore"] is None, s_min["errore"]
    page.wait_for_timeout(2000)
    s_max = _site(page, tariffa="3", **kwargs)
    assert s_max["errore"] is None, s_max["errore"]
    assert s_min["onorari_tabellari"] is not None and s_max["onorari_tabellari"] is not None, (s_min, s_max)
    return s_min, s_max


def _confronta(label: str, coppie: list[tuple[str, float, float]]) -> None:
    """Assert tool == site for every (name, tool, site) pair, 0.01 EUR in cents."""
    diffs = [
        f"{nome}: tool={t:.2f} sito={s:.2f} diff={abs(t - s):.2f}"
        for nome, t, s in coppie
        if abs(round(t * 100) - round(s * 100)) > 1
    ]
    assert not diffs, f"{label} -> " + "; ".join(diffs)


# ---------------------------------------------------------------------------
# cases of the plan
# ---------------------------------------------------------------------------


def test_perizia_medica_10_ore_vacazioni(page):
    """Piano #1 - perizia medica a ore (10 ore, nessun valore).

    Atteso del piano: a vacazioni 10 ore = 5 vacazioni x 14,68 = 73,40 EUR (art. 4
    L. 319/1980, DM 30/05/2002 art. 1, Corte cost. n. 16/2025; con la regola previgente
    14,68 + 4 x 8,15 = 47,28). Il tool: 1.000-2.000 EUR (100-200 EUR/ora).
    """
    r = _tool(tipo_incarico="perizia_medica", ore_lavoro=10)
    s = _site(page, periodo=PERIODO_2026, vacazioni=_vacazioni_da_ore(10))
    assert s["errore"] is None, s["errore"]
    assert s["n_vacazioni"] == "5" and s["giorni_lavorativi"] == 12, s
    o = r["calcolo_orario"]
    _confronta(
        "perizia_medica 10 ore (5 vacazioni)",
        [
            ("orario min vs vacazioni", o["compenso_min"], s["vacazioni_totale"]),
            ("orario max vs vacazioni", o["compenso_max"], s["vacazioni_totale"]),
        ],
    )


def test_perizia_immobiliare_100000_estimo(page):
    """Piano #2 - stima immobiliare a percentuale, valore 100.000 EUR.

    Atteso del piano: onorario a percentuale per scaglioni della tabella del DM
    30/05/2002 per la stima di immobili (art. 13 co. 1, estimo, sull'importo stimato),
    da leggere dal sito. Il tool: 500-2.000 EUR (0,5-2%).
    """
    r = _tool(tipo_incarico="perizia_immobiliare", valore_causa=100000)
    s_min, s_max = _site_min_max(page, articolo=ART_ESTIMO, valore=100000)
    p = r["calcolo_a_percentuale"]
    _confronta(
        "perizia_immobiliare 100.000 (art. 13 co. 1)",
        [
            ("percentuale min vs Minima", p["compenso_min"], s_min["onorari_tabellari"]),
            ("percentuale max vs Massima", p["compenso_max"], s_max["onorari_tabellari"]),
        ],
    )


def test_perizia_contabile_500000_e_40_ore(page):
    """Piano #3 - perizia contabile con valore 500.000 EUR e 40 ore.

    Atteso del piano: tabella del DM 30/05/2002 per le perizie contabili (art. 2,
    materia amministrativa, contabile e fiscale, scaglioni) da leggere dal sito; a
    vacazioni 20 x 14,68 = 293,60 EUR. Il tool: 5.000-15.000 a percentuale e
    2.800-5.200 a ore. Una sola richiesta al sito con entrambe le sezioni (NOTA 1 della
    pagina: i due onorari sono indicati separatamente e poi totalizzati).
    """
    r = _tool(tipo_incarico="perizia_contabile", valore_causa=500000, ore_lavoro=40)
    s_min, s = _site_min_max(
        page, periodo=PERIODO_2026, vacazioni=_vacazioni_da_ore(40), articolo=ART_CONTABILE, valore=500000
    )
    assert s["n_vacazioni"] == "20" and s["giorni_lavorativi"] == 12, s
    p, o = r["calcolo_a_percentuale"], r["calcolo_orario"]
    _confronta(
        "perizia_contabile 500.000 / 40 ore (art. 2 + 20 vacazioni)",
        [
            ("percentuale min vs Minima", p["compenso_min"], s_min["onorari_tabellari"]),
            ("percentuale max vs Massima", p["compenso_max"], s["onorari_tabellari"]),
            ("orario min vs vacazioni", o["compenso_min"], s["vacazioni_totale"]),
            ("orario max vs vacazioni", o["compenso_max"], s["vacazioni_totale"]),
        ],
    )


def test_stima_danni_senza_dati(page):
    """Piano #4 - nessun dato di calcolo.

    Atteso del piano: errore "specificare almeno valore_causa o ore_lavoro". Il sito,
    inviato vuoto (nessuna vacazione, nessun articolo), risponde "Attenzione - Un campo
    risulta errato o non compilato" e non calcola: entrambi rifiutano.
    """
    r = _tool(tipo_incarico="stima_danni")
    assert "errore" in r and "valore_causa" in r["errore"], r
    s = _site(page)
    assert s["errore"] == "Un campo risulta errato o non compilato", s


# ---------------------------------------------------------------------------
# limit cases
# ---------------------------------------------------------------------------


def test_limite_perizia_immobiliare_confine_primo_scaglione(page):
    """Limite - valore pari al tetto del primo scaglione (5.164,57 EUR = 10 milioni di lire).

    Norma: DM 30/05/2002 art. 13 co. 1 (estimo), primo scaglione "fino a euro 5.164,57,
    dall'1,0264% al 2,0685%" (= 53,01-106,83), e ultimo periodo dell'art. 13: "E' in ogni
    caso dovuto un compenso non inferiore a euro 145,12" (testo del DM su giustizia.it).
    Il sito applica il primo scaglione e poi il minimo ("Onorario minimo" nel risultato):
    145,12 sia alla Minima sia alla Massima. Il tool: 0,5-2% = 25,82-103,29 EUR, senza
    minimo.
    """
    r = _tool(tipo_incarico="perizia_immobiliare", valore_causa=5164.57)
    s_min, s_max = _site_min_max(page, articolo=ART_ESTIMO, valore=5164.57)
    assert s_max["tab_max"] is not None, s_max  # a single scaglione row, no "Totali:"
    p = r["calcolo_a_percentuale"]
    _confronta(
        f"perizia_immobiliare 5.164,57 (art. 13 co. 1, primo scaglione; tabella sito "
        f"{s_max['tab_min']:.2f}-{s_max['tab_max']:.2f}, minimo {s_max['onorario_minimo']})",
        [
            ("percentuale min vs Minima", p["compenso_min"], s_min["onorari_tabellari"]),
            ("percentuale max vs Massima", p["compenso_max"], s_max["onorari_tabellari"]),
        ],
    )


def test_limite_stima_danni_art3_ridotto_meta(page):
    """Limite (opzione enumerata) - stima_danni, valore 50.000 EUR.

    Norma: DM 30/05/2002 art. 3 (valutazione di diritti a titolo di risarcimento di
    danni): onorario dell'art. 2 ridotto della meta'. Il sito mostra la riduzione solo
    per la tariffa selezionata: due richieste, Minima e Massima, lette dal RIEPILOGO.
    Il tool: 1-3% = 500-1.500 EUR.
    """
    r = _tool(tipo_incarico="stima_danni", valore_causa=50000)
    s_min, s_max = _site_min_max(page, articolo=ART_DANNI, valore=50000)
    p = r["calcolo_a_percentuale"]
    _confronta(
        "stima_danni 50.000 (art. 3 = art. 2 / 2)",
        [
            ("percentuale min vs Minima ridotta", p["compenso_min"], s_min["onorari_tabellari"]),
            ("percentuale max vs Massima ridotta", p["compenso_max"], s_max["onorari_tabellari"]),
        ],
    )


def test_limite_accertamenti_tecnici_art11(page):
    """Limite (opzione enumerata) - accertamenti_tecnici (ATP art. 696 c.p.c.), 200.000 EUR.

    Norma: il DM 30/05/2002 non ha un articolo per l'ATP; si usa l'art. 11 (costruzioni
    edilizie, impianti: scaglioni), l'articolo tipico dell'ATP sui vizi dell'immobile.
    Il tool: 1-2,5% = 2.000-5.000 EUR.
    """
    r = _tool(tipo_incarico="accertamenti_tecnici", valore_causa=200000)
    s_min, s_max = _site_min_max(page, articolo=ART_COSTRUZIONI, valore=200000)
    p = r["calcolo_a_percentuale"]
    _confronta(
        "accertamenti_tecnici 200.000 (art. 11)",
        [
            ("percentuale min vs Minima", p["compenso_min"], s_min["onorari_tabellari"]),
            ("percentuale max vs Massima", p["compenso_max"], s_max["onorari_tabellari"]),
        ],
    )


def test_limite_perizia_medica_onorario_fisso_art21(page):
    """Limite (opzione enumerata) - perizia_medica con valore 50.000 EUR.

    Norma: DM 30/05/2002 art. 21 (accertamenti medici e diagnostici sulla persona):
    onorario FISSO da 48,03 a 290,77 EUR, indipendente dal valore (sul sito il campo
    "Valore Stimato" e' disabilitato per l'art. 21). Atteso del piano: "onorario fisso
    dell'accertamento medico-legale da leggere dal sito". Il tool applica comunque una
    percentuale: 0,5-2,5% = 250-1.250 EUR.
    """
    r = _tool(tipo_incarico="perizia_medica", valore_causa=50000)
    s_min, s_max = _site_min_max(page, articolo=ART_MEDICO)
    p = r["calcolo_a_percentuale"]
    _confronta(
        "perizia_medica 50.000 (art. 21, onorario fisso)",
        [
            ("percentuale min vs Minima", p["compenso_min"], s_min["onorari_tabellari"]),
            ("percentuale max vs Massima", p["compenso_max"], s_max["onorari_tabellari"]),
        ],
    )


def test_limite_perizia_medica_5_ore_mezza_vacazione(page):
    """Limite (frazione di vacazione) - perizia_medica, 5 ore.

    Norma: art. 4 co. 4 L. 319/1980 "l'onorario per la vacazione non si divide che per
    meta'; trascorsa un'ora e un quarto e' dovuto interamente": 5 ore = 2 vacazioni + 1
    ora (meno di 1h15) = 2,5 vacazioni = 36,70 EUR. Al sito si digita "2,5": il sito
    arrotonda a 3 vacazioni (44,04 EUR). Il confronto e' con il valore del sito.
    Il tool: 100-200 EUR/ora = 500-1.000 EUR.
    """
    r = _tool(tipo_incarico="perizia_medica", ore_lavoro=5)
    vac = _vacazioni_da_ore(5)
    assert vac == "2,5"
    s = _site(page, periodo=PERIODO_2026, vacazioni=vac)
    assert s["errore"] is None, s["errore"]
    o = r["calcolo_orario"]
    _confronta(
        f"perizia_medica 5 ore (2,5 vacazioni; sito: {s['n_vacazioni']} vacazioni)",
        [
            ("orario min vs vacazioni", o["compenso_min"], s["vacazioni_totale"]),
            ("orario max vs vacazioni", o["compenso_max"], s["vacazioni_totale"]),
        ],
    )


def test_limite_perizia_medica_10_ore_prima_di_corte_cost_16_2025(page):
    """Limite (anno diverso) - perizia_medica, 10 ore, perizia svolta a dicembre 2024.

    Norma: Corte cost. n. 16/2025 (G.U. 12/02/2025) ha dichiarato illegittimo l'art. 4
    co. 2 L. 319/1980 nella parte in cui liquida le vacazioni successive alla prima in
    misura inferiore; il piano chiede di confermare 14,68 anche per le successive (regola
    previgente: 14,68 + 4 x 8,15 = 47,28). Il sito applica la tariffa piena anche a una
    perizia interamente anteriore alla sentenza. Il tool non ha date: 1.000-2.000 EUR.
    """
    r = _tool(tipo_incarico="perizia_medica", ore_lavoro=10)
    s = _site(page, periodo=PERIODO_2024, vacazioni=_vacazioni_da_ore(10))
    assert s["errore"] is None, s["errore"]
    assert s["n_vacazioni"] == "5", s
    o = r["calcolo_orario"]
    _confronta(
        f"perizia_medica 10 ore, dic. 2024 (sito: {s['vacazioni_totale']:.2f})",
        [
            ("orario min vs vacazioni", o["compenso_min"], s["vacazioni_totale"]),
            ("orario max vs vacazioni", o["compenso_max"], s["vacazioni_totale"]),
        ],
    )

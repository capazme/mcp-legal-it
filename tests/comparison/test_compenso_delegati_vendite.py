"""Comparison tests: compenso_delegati_vendite vs avvocatoandreani.it.

Site page: https://www.avvocatoandreani.it/servizi/calcolo-compenso-delegati-vendite-giudiziarie.php
Form ``#CompensoDelegati`` (POST to ``#Res``): radio ``TipoVendita`` (1 = beni immobili,
2 = beni mobili iscritti), ``Valore`` (prezzo di aggiudicazione / valore di riferimento),
four phase checkboxes with read-only amounts ``Compenso1..4`` that the page's JavaScript
fills on keyup from the scaglione of ``Valore``, ``NumDebit``, ``TipoVar``/``PctVar``
(aumento fino al 60%, riduzione fino al 25%). The live fields ``#CompensoTotale`` and
``#SpeseGenerali`` are recomputed client-side; the submitted page prints a result table
("Valore di riferimento", "Compenso tabellare" per fase, "Totale compenso", and, when the
cap applies, "Compenso con limitazione (art. 2, c. 5)", then "Spese generali 10%").

What the site computes (read from its inline data ``_c1.._c4`` and
``servizi/js/calcolo-compenso-delegati-vendite-giudiziarie.*.js``), DM 15 ottobre 2015
n. 227, art. 2 (beni immobili):
    - fixed amount per phase: EUR 1.000 (valore fino a 100.000), 1.500 (oltre 100.000 e
      fino a 500.000), 2.000 (oltre 500.000), for each of the four phases (attivita'
      preliminari, aggiudicazione, trasferimento, distribuzione) -> 4.000 / 6.000 / 8.000;
      scaglione test is ``valore > min && valore <= max`` (100.000 is still the first);
    - c. 3: aumento fino al 60% / riduzione fino al 25% (not used here);
    - c. 4: spese generali 10% of the compenso;
    - c. 5: compenso + spese generali capped at 40% of the valore di riferimento (the
      compenso is scaled by 0,4 * valore / (compenso * 1,1));
    - c. 7: 50% of the "trasferimento" phase (+ its spese generali) charged to the
      aggiudicatario.
Art. 3 (beni mobili iscritti) has its own table (200/250/400/500/1.000, cap 30%).
The per-phase amounts, the scaglione boundaries ("pari o inferiore a euro 100.000", "superiore
a euro 100.000 e pari o inferiore a euro 500.000", "superiore a euro 500.000") and cc. 3, 4, 5
and 7 coincide with the vigente text of art. 2 read on Normattiva on 2026-09-25
(urn:nir:stato:decreto.ministeriale:2015-10-15;227~art2, via cite_law); art. 3 likewise.

What the tool computes: a percentage schedule on the prezzo di aggiudicazione (2,6% with
a minimum of EUR 1.100 up to 100.000, 1,5% on the part from 100.000 to 500.000, 0,75%
beyond), declared Precisione: INDICATIVO because the decree uses fixed amounts per phase.
The spese generali 10% appear only as a note; the cap of c. 5, the variations of c. 3,
the number of debtors of c. 2 and the beni mobili of art. 3 are not modelled.

Compared value: tool ``compenso`` vs the site's liquidated compenso (``Compenso con
limitazione`` when the c. 5 cap applies, otherwise ``Totale compenso``), both net of
spese generali, IVA and cassa.

Tolerance: 0.01 EUR (brief), compared in integer cents.
"""

import re

import pytest

from tests.comparison.conftest import accept_cookies, get_tables_text, goto, parse_euro

PAGE = "calcolo-compenso-delegati-vendite-giudiziarie.php"

_AMOUNT = r"€\s*([\d.]+,\d{2})"
_FASI_IMMOBILI = (
    "Attività preliminari",
    "Aggiudicazione/assegnazione",
    "Trasferimento proprietà",
    "Distribuzione",
)


def _tool(prezzo: float) -> dict:
    import src.server  # noqa: F401  registers all tool modules
    from src.tools.parcelle_professionisti import compenso_delegati_vendite

    fn = getattr(compenso_delegati_vendite, "fn", compenso_delegati_vendite)
    return fn(prezzo_aggiudicazione=prezzo)


def _it(value: float) -> str:
    """Format a value the way a user types it in the site field (Italian decimal comma)."""
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.2f}".replace(".", ",")


def _find(pattern: str, text: str) -> float | None:
    m = re.search(pattern, text, re.S)
    return parse_euro(m.group(1)) if m else None


def _site(page, valore: float, tipo_vendita: str = "1") -> dict:
    """Drive the site once (all four phases, 1 debitore, no variation) and read the result."""
    goto(page, PAGE, wait_ms=2000)
    # The InMobi/Quantcast CMP is injected after the first cookie pass and steals focus
    # (and force-clicks): remove it again once the page has settled.
    accept_cookies(page)
    if tipo_vendita == "2":
        page.check("#I-Tip-2", force=True)
        page.wait_for_timeout(500)
    # typing fires the keyup handler that picks the scaglione and fills Compenso1..4
    page.locator("#Valore").press_sequentially(_it(valore))
    page.wait_for_timeout(1000)
    assert page.input_value("#Valore") == _it(valore), "il campo Valore non ha ricevuto il testo"
    live_totale = parse_euro(page.input_value("#CompensoTotale"))
    live_spese = parse_euro(page.input_value("#SpeseGenerali"))
    page.click("#CompensoDelegati input[type=submit]", force=True)
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(2500)

    text = "\n".join(get_tables_text(page))
    valore_rif = _find(r"Valore di riferimento\s*" + _AMOUNT, text)
    assert valore_rif is not None, "risultato del sito non trovato (Valore di riferimento)"
    tabellare = _find(r"Totale compenso.*?" + _AMOUNT, text)
    limitato = _find(r"Compenso con limitazione.*?" + _AMOUNT, text)
    spese = _find(r"Spese generali 10%.*?" + _AMOUNT, text)
    assert tabellare is not None, "Totale compenso non leggibile nel risultato del sito"
    fasi = {}
    for nome in _FASI_IMMOBILI:
        v = _find(re.escape(nome) + r"\s*" + _AMOUNT, text)
        if v is not None:
            fasi[nome] = v
    liquidato = limitato if limitato is not None else tabellare
    # the server-side result must agree with the live client-side fields
    assert round(liquidato * 100) == round(live_totale * 100), (
        f"sito incoerente: risultato {liquidato:.2f} vs campo CompensoTotale {live_totale:.2f}"
    )
    return {
        "valore": valore_rif,
        "fasi": fasi,
        "tabellare": tabellare,
        "limitato": limitato,
        "liquidato": liquidato,
        "spese_generali": spese if spese is not None else live_spese,
        "text": text,
    }


def _assert_cents(tool_value: float, site_value: float, label: str) -> None:
    diff_cents = abs(round(tool_value * 100) - round(site_value * 100))
    assert diff_cents <= 1, (
        f"{label}: tool={tool_value:.2f}, sito={site_value:.2f}, "
        f"diff={diff_cents / 100:.2f} (max 0.01)"
    )


def _confronta(page, prezzo: float, label: str) -> None:
    tool = _tool(prezzo)
    assert "errore" not in tool, tool
    site = _site(page, prezzo)
    assert round(site["valore"] * 100) == round(prezzo * 100), (
        f"il sito ha letto un valore diverso: {site['valore']:.2f} invece di {prezzo:.2f}"
    )
    _assert_cents(tool["compenso"], site["liquidato"], label)


# --- Piano: primo scaglione -------------------------------------------------------------


def test_primo_scaglione_40000(page):
    # Piano: "Compensi fissi per fase dello scaglione fino a 100.000 (art. 2 DM 227/2015):
    # da leggere dal sito. Il tool: 1.100 (minimo)."
    # Norma: DM 227/2015 art. 2 c. 1 (EUR 1.000 per ciascuna delle quattro fasi fino a 100.000).
    # Sito: 4 x 1.000 = 4.000 (cap c. 5: 4.400 <= 16.000, non opera). Tool: 1.100.
    _confronta(page, 40000, "delegati 40.000")


def test_ultimo_euro_primo_scaglione_100000(page):
    # Caso al limite. Piano: "Da leggere dal sito. Il tool: 2.600."
    # Norma: DM 227/2015 art. 2 c. 1, scaglione "fino a euro 100.000" (100.000 incluso).
    # Sito: 4.000 (100.000 resta nel primo scaglione). Tool: 2,6% = 2.600.
    _confronta(page, 100000, "delegati 100.000")


def test_primo_centesimo_secondo_scaglione_100000_01(page):
    # Caso al limite. Piano: "Da leggere dal sito, atteso un salto dei compensi fissi per
    # fase. Il tool: 2.600, senza salto."
    # Norma: DM 227/2015 art. 2 c. 1, scaglione "oltre 100.000 e fino a 500.000" (1.500 a fase).
    # Sito: 4 x 1.500 = 6.000 (salto di 2.000). Tool: 2.600 + 0,01 x 1,5% = 2.600.
    _confronta(page, 100000.01, "delegati 100.000,01")


def test_terzo_scaglione_600000(page):
    # Piano: "Scaglione oltre 500.000: da leggere dal sito, piu' rimborso forfettario delle
    # spese generali. Il tool: 9.350."
    # Norma: DM 227/2015 art. 2 c. 1 (2.000 a fase oltre 500.000) e c. 4 (spese generali 10%).
    # Sito: 8.000 + spese generali 800. Tool: 2.600 + 6.000 + 750 = 9.350 (spese solo in nota).
    _confronta(page, 600000, "delegati 600.000")


# --- Casi al limite aggiunti ------------------------------------------------------------


def test_ultimo_euro_secondo_scaglione_500000(page):
    # Caso al limite (aggiunto). Atteso: sito 4 x 1.500 = 6.000 (500.000 resta nel secondo
    # scaglione); tool 2.600 + 400.000 x 1,5% = 8.600.
    # Norma: DM 227/2015 art. 2 c. 1, scaglione "oltre 100.000 e fino a 500.000".
    _confronta(page, 500000, "delegati 500.000")


def test_primo_centesimo_terzo_scaglione_500000_01(page):
    # Caso al limite (aggiunto). Atteso: sito 4 x 2.000 = 8.000 (salto di 2.000); tool
    # 8.600 + 0,01 x 0,75% = 8.600, senza salto.
    # Norma: DM 227/2015 art. 2 c. 1, scaglione "oltre 500.000".
    _confronta(page, 500000.01, "delegati 500.000,01")


def test_soglia_limite_40_per_cento_11000(page):
    # Caso al limite (aggiunto): soglia esatta del limite di art. 2 c. 5. Compenso + spese
    # generali = 4.400 = 40% di 11.000: il sito non riduce (confronto stretto ">").
    # Atteso: sito 4.000; tool max(11.000 x 2,6%, 1.100) = 1.100.
    # Norma: DM 227/2015 art. 2 cc. 1, 4 e 5.
    _confronta(page, 11000, "delegati 11.000")


def test_limite_40_per_cento_applicato_10000(page):
    # Caso al limite (aggiunto): il limite di art. 2 c. 5 opera. Compenso + spese generali
    # (4.400) supera il 40% del valore (4.000): il sito liquida 4.000 x 4.000/4.400 =
    # 3.636,36 + spese generali 363,64. Il tool non modella il limite: 1.100 (minimo).
    # Norma: DM 227/2015 art. 2 cc. 4 e 5.
    _confronta(page, 10000, "delegati 10.000 (limite 40%)")


# --- Opzione enumerata del sito non offerta dal tool ------------------------------------


def test_beni_mobili_non_confrontabile(page):
    # Opzione enumerata "Vendita: BENI MOBILI" (DM 227/2015 art. 3: 400/500/400/500 per
    # valori da 25.000 a 40.000, limite 30%). Il tool calcola solo le vendite immobiliari
    # (docstring: "vendite giudiziarie immobiliari") e non ha un parametro per il tipo di
    # vendita: il caso non e' confrontabile. Il valore del sito resta a verbale nello skip.
    tool = _tool(30000)
    site = _site(page, 30000, tipo_vendita="2")
    assert "art. 3" in site["text"], "il sito non ha applicato la tabella dei beni mobili"
    pytest.skip(
        "non confrontabile: il tool non gestisce le vendite di beni mobili (art. 3 DM 227/2015); "
        f"sito (beni mobili, 30.000) compenso {site['liquidato']:.2f} + spese generali "
        f"{site['spese_generali']:.2f}; tool (schema immobili) {tool['compenso']:.2f}"
    )

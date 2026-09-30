"""Comparison tests: compenso_mediatore_familiare vs avvocatoandreani.it.

Site page: https://www.avvocatoandreani.it/servizi/calcolo-compenso-mediatore-familiare.php
Server-side calculator (POST to the same page, anchor ``#Res``). Inputs used here: the
``Complessita`` radio (``#Complessita-1`` Bassa, ``-2`` Media, ``-3`` Alta) and
``#NumIncontri``; no cassa, no regime semplificato. Output tables:
    "Parametri per il calcolo": Complessita', Compenso per ogni incontro, Numero incontri,
        "Compenso spettante[ per N incontri]" (the " per N incontri" part is missing for 1);
    "Dettaglio fattura": Compenso, Spese forfettarie 21% (art. 8, c. 6), Totale imponibile,
        IVA 22%, Totale documento;
    footer: "Il compenso di mediazione e' dovuto interamente per ciascuna parte."
Zero meetings are rejected with "Vi sono alcuni campi errati o non compilati."

Legal basis (D.M. 27 ottobre 2023 n. 151, read on Normattiva with cite_law):
- art. 8, c. 4: each "mediando" pays EUR 40,00 for every meeting actually held;
- art. 8, c. 5: multiplied by 1 / 1,5 / 2 for low / medium / high complexity;
- art. 8, c. 6: plus flat-rate costs of 21% of that amount;
- art. 8, c. 1: the compenso (c. 4-5) does NOT include the 21% nor oneri e contributi;
- art. 6, c. 10, lett. a): in a pending court case the mediator informs the parties
  "gratuitamente in via preliminare" -> the tool's free first (informative) meeting.

How tool and site are put on the same footing:
- the tool's ``n_incontri`` counts the free first meeting, the site counts only what is
  billed -> the site receives ``NumIncontri = n_incontri - 1``;
- the site is per party, the tool's ``tariffa_incontro`` is per meeting (both parties) ->
  the site value is doubled (two "mediandi", the ordinary family mediation);
- the tool has a free per-meeting rate and no 21% line: ``tariffa_incontro = 80 x coeff``
  reproduces the DM compenso (c. 4-5), ``80 x coeff x 1,21`` reproduces compenso + spese
  forfettarie (the site's "Totale imponibile"). The tool default 120,00 is 80 x 1,5, i.e.
  the medium-complexity compenso WITHOUT the 21%.
IVA, cassa and bollo are outside the tool and are not compared.

Tolerance: 0,01 EUR (brief), compared in integer cents to avoid float noise.
"""

import re

import pytest

from tests.comparison.conftest import accept_cookies, extract_amount, goto, parse_euro

PAGE = "calcolo-compenso-mediatore-familiare.php"

_LIVELLI = {"bassa": ("1", "Bassa", 1.0), "media": ("2", "Media", 1.5), "alta": ("3", "Alta", 2.0)}
_PARTI = 2  # two "mediandi": the site's amounts are per party (art. 8, c. 4)
_ERRORE_SITO = "campi errati o non compilati"
_COMPENSO_RE = re.compile(r"Compenso spettante[^:\n]*:\s*€\s*([\d.,]+)")


def _tool(**kwargs) -> dict:
    import src.server  # noqa: F401  registers all tool modules
    from src.tools.parcelle_professionisti import compenso_mediatore_familiare

    fn = getattr(compenso_mediatore_familiare, "fn", compenso_mediatore_familiare)
    return fn(**kwargs)


def _site_raw(page, livello: str, num_incontri: str) -> str:
    """Submit the site form once; return the whole body text."""
    radio, _, _ = _LIVELLI[livello]
    goto(page, PAGE, wait_ms=1500)
    # The Quantcast CMP is injected again after goto() removed it; a forced click would land
    # on its overlay (radio not selected, form never posted). Remove it again, set the radio
    # directly (the site echoes the complexity it received, checked in _site) and submit.
    accept_cookies(page)
    page.evaluate(f"document.querySelector('#Complessita-{radio}').checked = true")
    page.fill("#NumIncontri", num_incontri)
    accept_cookies(page)
    page.click("#btn-calc", force=True)
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(2500)
    return page.inner_text("body")


def _site(page, livello: str, incontri_pagati: int) -> dict:
    """Drive the site for ``incontri_pagati`` billed meetings; return per-party amounts."""
    body = _site_raw(page, livello, str(incontri_pagati))
    assert _ERRORE_SITO not in body, f"il sito ha rifiutato {incontri_pagati} incontri"
    _, etichetta, coeff = _LIVELLI[livello]
    assert re.search(rf"Complessità dell'incarico:\s*{etichetta}", body), "complessita' non letta dal sito"
    assert re.search(rf"Numero incontri:\s*{incontri_pagati}\b", body), "numero incontri non letto dal sito"
    per_incontro = extract_amount(body, "Compenso per ogni incontro")
    assert per_incontro == pytest.approx(40 * coeff), f"compenso per incontro inatteso: {per_incontro}"
    m = _COMPENSO_RE.search(body)
    assert m, "compenso spettante non leggibile nell'output del sito"
    imponibile = extract_amount(body, "Totale imponibile")
    assert imponibile is not None, "totale imponibile non leggibile nell'output del sito"
    assert "dovuto interamente per ciascuna parte" in body, "il sito non indica piu' il calcolo pro capite"
    return {"compenso": parse_euro(m.group(1)), "imponibile": imponibile}


def _assert_cents(tool_value: float, site_value: float, label: str) -> None:
    diff_cents = abs(round(tool_value * 100) - round(site_value * 100))
    assert diff_cents <= 1, (
        f"{label}: tool={tool_value:.2f}, sito={site_value:.2f}, diff={diff_cents / 100:.2f} (max 0.01)"
    )


# --- Plan cases ------------------------------------------------------------------------


def test_piano_solo_incontro_informativo(page):
    # Piano: n_incontri=1, tariffa 120 -> compenso 0 (primo incontro informativo gratuito).
    # Norma: D.M. 151/2023 art. 6, c. 10, lett. a) (informativa preliminare gratuita).
    # Il sito non modella l'incontro informativo gratuito: l'equivalente (0 incontri a
    # pagamento) viene rifiutato. Caso al limite (minimo ammesso dal tool).
    r = _tool(n_incontri=1, tariffa_incontro=120.0)
    assert "errore" not in r, r
    assert r["incontri_a_pagamento"] == 0
    assert r["compenso_totale"] == 0.0
    body = _site_raw(page, "media", "0")
    if _ERRORE_SITO in body:
        pytest.skip(
            "sito_non_calcola: 0 incontri a pagamento rifiutati ('Vi sono alcuni campi errati o "
            f"non compilati'); tool {r['compenso_totale']:.2f} EUR (solo incontro informativo gratuito)"
        )
    pytest.fail("il sito ha accettato 0 incontri: rivedere il confronto")


def test_piano_cinque_incontri_default_totale_dm(page):
    # Piano: n_incontri=5, tariffa 120 -> DM con due parti e 4 incontri a pagamento:
    # 320 x coefficiente + 21% = 387,20 / 580,80 / 774,40 (bassa/media/alta); il tool 480,00.
    # Norma: D.M. 151/2023 art. 8, c. 4, 5 e 6. Confronto con la complessita' media
    # (default del sito, e la sola di cui 120 = 80 x 1,5 riproduce il compenso): il tool
    # non aggiunge le spese forfettarie del 21% -> scostamento atteso di 100,80 EUR.
    # Phase 3 verdict (test_errato): `compenso_totale` is the compenso WITHOUT the 21% flat
    # expenses (art. 8 c. 1 DM 151/2023: the compenso of c. 4-5 does not include them), so it
    # must be compared with the site's "Compenso spettante" (see the default-120 test below).
    # The site's "Totale imponibile" corresponds to the tool's `totale_imponibile` (compenso + 21%).
    r = _tool(n_incontri=5, tariffa_incontro=120.0)
    assert "errore" not in r, r
    s = _site(page, "media", r["incontri_a_pagamento"])
    _assert_cents(r["totale_imponibile"], _PARTI * s["imponibile"], "5 incontri, 120 EUR vs imponibile DM media")


def test_piano_tariffa_bassa_complessita(page):
    # Piano: n_incontri=5, tariffa 96,80 (= 80 x 1,21) -> 387,20 EUR, pari al valore di
    # bassa complessita' del decreto. Norma: D.M. 151/2023 art. 8, c. 4, 5 lett. a) e 6.
    r = _tool(n_incontri=5, tariffa_incontro=96.8)
    assert "errore" not in r, r
    s = _site(page, "bassa", r["incontri_a_pagamento"])
    _assert_cents(r["compenso_totale"], _PARTI * s["imponibile"], "5 incontri bassa (imponibile x2)")


def test_piano_zero_incontri(page):
    # Piano: n_incontri=0 -> errore "numero incontri almeno 1". Anche il sito rifiuta
    # 0 incontri. Caso al limite (sotto il minimo).
    r = _tool(n_incontri=0, tariffa_incontro=120.0)
    assert "errore" in r, r
    body = _site_raw(page, "media", "0")
    assert _ERRORE_SITO in body, "il sito ha calcolato un compenso con 0 incontri"


# --- Cases added in phase 1 ------------------------------------------------------------


def test_default_120_compenso_media_senza_forfettario(page):
    # Stesso input del piano (5 incontri, tariffa di default): 120 = 2 parti x 40 x 1,5,
    # quindi il tool riproduce il COMPENSO di media complessita' (art. 8, c. 4-5), che per
    # l'art. 8, c. 1 non comprende le spese forfettarie. Atteso: 480,00 = 2 x 240,00 del sito.
    # Opzione enumerata: complessita' media.
    r = _tool(n_incontri=5)
    assert "errore" not in r, r
    assert r["tariffa_incontro"] == 120.0
    s = _site(page, "media", r["incontri_a_pagamento"])
    _assert_cents(r["compenso_totale"], _PARTI * s["compenso"], "5 incontri default vs compenso media x2")


def test_limite_primo_incontro_pagato_alta(page):
    # Limite: n_incontri=2 e' il primo caso con un incontro a pagamento (confine gratuito /
    # pagato); sul sito 1 incontro usa l'etichetta singolare "Compenso spettante:".
    # Alta complessita': tariffa 80 x 2 x 1,21 = 193,60 -> atteso 193,60 = 2 x 96,80.
    # Norma: D.M. 151/2023 art. 8, c. 4, 5 lett. c) e 6.
    r = _tool(n_incontri=2, tariffa_incontro=193.6)
    assert "errore" not in r, r
    assert r["incontri_a_pagamento"] == 1
    s = _site(page, "alta", 1)
    _assert_cents(r["compenso_totale"], _PARTI * s["imponibile"], "2 incontri alta (imponibile x2)")


def test_limite_percorso_lungo_media(page):
    # Limite: percorso di 12 incontri (estremo alto del "percorso tipico 8-12" del tool),
    # media complessita' con spese forfettarie: tariffa 80 x 1,5 x 1,21 = 145,20 ->
    # 11 x 145,20 = 1.597,20 = 2 x 798,60 del sito. Norma: D.M. 151/2023 art. 8, c. 4, 5 lett. b) e 6.
    r = _tool(n_incontri=12, tariffa_incontro=145.2)
    assert "errore" not in r, r
    s = _site(page, "media", r["incontri_a_pagamento"])
    _assert_cents(r["compenso_totale"], _PARTI * s["imponibile"], "12 incontri media (imponibile x2)")

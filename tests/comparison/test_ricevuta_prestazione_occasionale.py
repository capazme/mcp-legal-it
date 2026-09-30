"""Comparison tests: ricevuta_prestazione_occasionale vs avvocatoandreani.it.

Site page: https://www.avvocatoandreani.it/servizi/calcolo-ricevuta-prestazione-occasionale.php
The form ``RicevutaPrestazione`` is POSTed to the server, which answers with the
receipt itself (``table[summary="ricevuta prestazione occasionale"]``): one row per
compenso, then "Addebito imposta di bollo" (only when the stamp is charged and the
compenso exceeds 77,47 EUR, ``Data.Cfg.Mbl``), "RITENUTE" with
"Ritenuta d'acconto (20% sul compenso)", the INPS rows when the annual 5.000 EUR
franchise is exceeded, and "Netto a pagare:".

Site inputs that matter:
- ``DoRacc`` (checkbox, off by default): the committente is a sostituto d'imposta and
  withholds 20% (``PctRacc``). The tool always applies the 20% withholding (its
  docstring defines the committente as sostituto d'imposta), so every comparable case
  ticks it.
- ``DoBollo`` (checkbox): charge the 2 EUR stamp to the committente. When ticked, the
  stamp is added to "Totale documento" and therefore to "Netto a pagare". The tool
  instead lists the stamp separately and its ``netto_a_pagare`` is always
  compenso - ritenuta. So: the stamp threshold is read with ``DoBollo`` ticked, and the
  net amount is compared with ``DoBollo`` NOT ticked (same convention as the tool).
- ``CompPerc`` / ``TotCompPerc`` / ``TipoLav`` / ``AliqInps``: compensi occasionali
  already received in the year, INPS position (1 = only gestione separata, 35,03% in
  2026; 2 = pensioner / other fund, 24%). The site withholds 1/3 of the gestione
  separata contribution on the part of the year's compensi above 5.000 EUR
  (art. 44 co. 2 DL 269/2003). The tool has none of these parameters and never computes
  the INPS share.
- ``CodPrest`` / ``CodComm`` are validated server side (checksum). The test uses the
  textbook synthetic codice fiscale RSSMRA80A01H501U and the synthetic, checksum-valid
  partita IVA 12345678903: no real person or company.
- ``DataDoc`` pins the receipt year (2026) for the site's INPS parameters; the tool has
  no date parameter.

Legal basis (tool): art. 2222 c.c.; art. 67 co. 1 lett. l) TUIR; art. 25 DPR 600/1973
(ritenuta 20%); art. 13 Tariffa parte I DPR 642/1972 (bollo 2 EUR over 77,47 EUR);
art. 5 DPR 633/1972 (fuori campo IVA).

Tolerance: 0.01 EUR (brief), compared in integer cents so float noise cannot turn a
one-cent gap into a failure.
"""

import re

import pytest

from tests.comparison.conftest import goto, parse_euro

PAGE = "calcolo-ricevuta-prestazione-occasionale.php"

COMMITTENTE = "Beta S.r.l."
PRESTATORE = "Luca Bianchi"
# Synthetic, checksum-valid identifiers (the site rejects invalid ones).
CF_PRESTATORE = "RSSMRA80A01H501U"
PIVA_COMMITTENTE = "12345678903"
DATA_DOC = "25/09/2026"

_REMOVE_CMP = (
    'document.querySelectorAll("#qc-cmp2-container, .qc-cmp2-container")'
    ".forEach(el => el.remove())"
)


def _tool(compenso_lordo: float, descrizione: str = "Traduzione di un contratto") -> dict:
    import src.server  # noqa: F401  registers all tool modules
    from src.tools.parcelle_professionisti import ricevuta_prestazione_occasionale

    fn = getattr(ricevuta_prestazione_occasionale, "fn", ricevuta_prestazione_occasionale)
    r = fn(
        compenso_lordo=compenso_lordo,
        committente=COMMITTENTE,
        prestatore=PRESTATORE,
        descrizione=descrizione,
    )
    assert "errore" not in r, r
    return r


def _euro_it(value: float) -> str:
    """12345.6 -> '12345,60' (what a user types in the site's amount field)."""
    return f"{value:.2f}".replace(".", ",")


def _site(
    page,
    importo: float,
    *,
    ritenuta: bool = True,
    addebito_bollo: bool = False,
    descrizione: str = "Traduzione di un contratto",
    gia_percepiti: float | None = None,
    tipo_lav: str | None = None,
) -> dict:
    """Fill and POST the site form once; return the receipt rows and the full text.

    Returns ``{"righe": {label: text}, "testo": str}``.
    """
    page.set_default_timeout(15000)
    goto(page, PAGE, wait_ms=1500)
    page.fill("#Prestatore", PRESTATORE)
    page.fill("#CodPrest", CF_PRESTATORE)
    page.fill("#Committente", COMMITTENTE)
    page.fill("#CodComm", PIVA_COMMITTENTE)
    # The date field is bound to a calendar widget that clears a typed value: set it
    # directly (it is a plain text input posted as dd/mm/yyyy).
    page.evaluate(f"document.getElementById('DataDoc').value = '{DATA_DOC}'")
    page.fill("#Oggetto", descrizione)
    # Typed, not filled: the site recomputes the total and the INPS note on keyup.
    page.type("#DescrComp-0", descrizione, delay=5)
    page.click("#ImpComp-0")
    page.type("#ImpComp-0", _euro_it(importo), delay=30)
    # The consent overlay can be re-injected after load: remove it before real clicks.
    page.evaluate(_REMOVE_CMP)
    if ritenuta:
        page.locator("#DoRacc").check()
    if addebito_bollo:
        page.locator("#DoBollo").check()
    if gia_percepiti is not None:
        page.locator("#CompPerc-1").check()
        page.wait_for_timeout(600)
        page.click("#TotCompPerc")
        page.type("#TotCompPerc", _euro_it(gia_percepiti), delay=30)
    if tipo_lav is not None:
        page.wait_for_timeout(600)
        page.select_option("#TipoLav", tipo_lav)
    page.wait_for_timeout(500)
    assert page.input_value("#DataDoc") == DATA_DOC
    page.evaluate(_REMOVE_CMP)
    # requestSubmit with the real submitter: posts Op=Calcola and runs the page's own
    # submit handlers, without depending on the button's on-screen position (sticky
    # ad banners can cover it).
    with page.expect_navigation(timeout=30000):
        page.evaluate(
            "(()=>{const f=document.getElementById('RicevutaPrestazione');"
            "f.requestSubmit(document.getElementById('btn-calc'));})()"
        )
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(1500)

    table = page.locator('table[summary="ricevuta prestazione occasionale"]')
    if table.count() == 0:
        errors = [t.strip() for t in page.locator(".ferror").all_inner_texts() if t.strip()]
        pytest.fail(f"il sito non ha prodotto la ricevuta (errori modulo: {errors})")
    righe: dict[str, str] = {}
    for tr in table.locator("tr").all():
        cells = [c.strip() for c in tr.locator("th, td").all_inner_texts()]
        cells = [c for c in cells if c]
        if len(cells) == 2:
            righe[cells[0]] = cells[1]
        elif len(cells) == 1:
            righe[cells[0]] = ""
    return {"righe": righe, "testo": table.inner_text()}


def _row(righe: dict[str, str], prefix: str) -> float | None:
    """Amount of the first receipt row whose label starts with ``prefix`` (None if absent)."""
    for label, value in righe.items():
        if label.startswith(prefix) and value:
            return parse_euro(value)
    return None


def _ritenuta(righe):
    return _row(righe, "Ritenuta d’acconto")


def _netto(righe):
    return _row(righe, "Netto a pagare")


def _bollo(righe):
    return _row(righe, "Addebito imposta di bollo") or 0.0


def _inps(righe):
    return _row(righe, "Ritenuta INPS a carico del prestatore") or 0.0


def _assert_cents(tool_value: float, site_value: float | None, label: str) -> None:
    assert site_value is not None, f"{label}: valore non trovato nella ricevuta del sito"
    diff_cents = abs(round(tool_value * 100) - round(site_value * 100))
    assert diff_cents <= 1, (
        f"{label}: tool={tool_value:.2f}, sito={site_value:.2f}, "
        f"diff={diff_cents / 100:.2f} (max 0.01)"
    )


def _tool_text_amount(testo: str, label: str) -> float:
    """Amount printed by the tool after ``label`` (Italian format '1.234,56' since phase 3)."""
    m = re.search(rf"{re.escape(label)}:\s*-?€([\d.]+,\d{{2}})", testo)
    assert m, f"importo '{label}' non trovato nel testo del tool"
    return float(m.group(1).replace(".", "").replace(",", "."))


# --- Plan cases -------------------------------------------------------------------


def test_piano_soglia_bollo_7747(page):
    # Piano: 77,47 EUR -> ritenuta 15,49; netto 61,98; nessun bollo (importo non
    # superiore a 77,47). Norma: art. 25 DPR 600/1973 (20%); art. 13 Tariffa parte I
    # DPR 642/1972 (bollo solo oltre 77,47 EUR). Caso al limite (soglia del bollo).
    # Addebito bollo spuntato sul sito: se il sito lo ritenesse dovuto comparirebbe la riga.
    r = _tool(77.47)
    c = r["calcoli"]
    site = _site(page, 77.47, addebito_bollo=True)
    righe = site["righe"]
    _assert_cents(c["ritenuta_acconto_20pct"], _ritenuta(righe), "ritenuta 77,47")
    _assert_cents(c["bollo"], _bollo(righe), "bollo 77,47")
    # No stamp line on the site, so its net amount carries no charged stamp.
    _assert_cents(c["netto_a_pagare"], _netto(righe), "netto 77,47")


def test_piano_soglia_bollo_7748(page):
    # Piano: 77,48 EUR -> ritenuta 15,50; netto 61,98; bollo 2,00 (art. 13 Tariffa
    # parte I DPR 642/1972). Caso al limite (un centesimo sopra la soglia).
    # Addebito bollo spuntato: il sito aggiunge la riga "Addebito imposta di bollo"
    # e porta il bollo nel totale documento (e quindi nel netto): qui si confrontano
    # solo ritenuta e bollo; il netto e' confrontato nel test gemello senza addebito.
    r = _tool(77.48)
    c = r["calcoli"]
    site = _site(page, 77.48, addebito_bollo=True)
    righe = site["righe"]
    _assert_cents(c["ritenuta_acconto_20pct"], _ritenuta(righe), "ritenuta 77,48")
    _assert_cents(c["bollo"], _bollo(righe), "bollo 77,48")
    # Arithmetic identity on the site (documented convention, not a comparison value):
    # netto = compenso + bollo addebitato - ritenuta.
    assert abs(_netto(righe) - (77.48 + _bollo(righe) - _ritenuta(righe))) < 0.005


def test_piano_7748_netto_senza_addebito_bollo(page):
    # Gemello del caso 77,48 del piano: bollo NON addebitato al committente, cioe' la
    # convenzione del tool (netto = compenso - ritenuta, bollo esposto a parte).
    # Atteso del piano: netto 61,98. Norma: art. 25 DPR 600/1973.
    # Controlla anche i riferimenti del testo generato: art. 67 co. 1 lett. l) TUIR e
    # art. 5 DPR 633/1972 (fuori campo IVA) presenti in entrambe le ricevute.
    r = _tool(77.48)
    c = r["calcoli"]
    site = _site(page, 77.48, addebito_bollo=False)
    righe = site["righe"]
    _assert_cents(c["ritenuta_acconto_20pct"], _ritenuta(righe), "ritenuta 77,48 (no addebito)")
    _assert_cents(c["netto_a_pagare"], _netto(righe), "netto 77,48 (no addebito)")
    assert _bollo(righe) == 0.0, "il sito non deve esporre il bollo se non addebitato"

    testo_tool = r["testo_ricevuta"]
    _assert_cents(_tool_text_amount(testo_tool, "Compenso lordo"), 77.48, "testo tool: compenso")
    _assert_cents(_tool_text_amount(testo_tool, "Ritenuta d'acconto 20%"), _ritenuta(righe),
                  "testo tool: ritenuta")
    _assert_cents(_tool_text_amount(testo_tool, "Netto a pagare"), _netto(righe),
                  "testo tool: netto")
    assert "Art. 67, comma 1, lett. l) TUIR" in testo_tool
    assert "art. 5 DPR 633/1972" in testo_tool
    assert "2222" in testo_tool
    testo_sito = site["testo"]
    assert "art. 67, comma 1, lett. l), DPR 917/1986" in testo_sito
    assert "art. 5, comma 2, DPR 633/72" in testo_sito


def test_piano_6000_oltre_franchigia_inps(page):
    # Phase 3 verdict (sito_errato on the rate): INPS circular 8/2026, table row 09 "Rapporti
    # occasionali autonomi (L. 326/2003 art. 44)", gives 33,72% (33% + 0,50% + 0,22%); the
    # 1,31% DIS-COLL add-on (35,03%) belongs to the collaboratori rows (02, 05, 06, 11, ...) and
    # is not due on row 09. The tool follows the circular; the site applies 35,03%, so the net
    # differs by 1/3 x 1,31% x excess (4,37 on 6.000, 0,004 on 5.001). Hand check at 6.000:
    # 1.000 x 33,72% / 3 = 112,40 -> net 4.687,60 (site 4.683,23).
    # Piano: 6.000 EUR -> ritenuta 1.200,00; netto 4.800,00 "prima dei contributi";
    # se nell'anno i compensi occasionali superano 5.000 EUR, sui 1.000 eccedenti sono
    # dovuti i contributi della gestione separata (aliquota 2026), un terzo a carico del
    # prestatore, trattenuto dal committente. Il tool non li calcola.
    # Norma: art. 25 DPR 600/1973; art. 44 co. 2 DL 269/2003 conv. L. 326/2003;
    # art. 2 co. 26 L. 335/1995 (gestione separata). Caso al limite (franchigia).
    # Sito: nessun altro compenso nell'anno, iscritto solo alla gestione separata
    # (35,03% nel 2026), bollo non addebitato (convenzione del tool sul netto).
    r = _tool(6000, descrizione="Consulenza occasionale")
    c = r["calcoli"]
    site = _site(page, 6000, addebito_bollo=False, descrizione="Consulenza occasionale")
    righe = site["righe"]
    _assert_cents(c["ritenuta_acconto_20pct"], _ritenuta(righe), "ritenuta 6.000")
    # Genuine gap expected: the site withholds the prestatore's third of the INPS
    # contribution on the 1.000 EUR excess; the tool's net amount ignores it.
    _assert_cents(c["netto_a_pagare"], _netto(righe), "netto 6.000 (sito con quota INPS)")


# --- Additional edge cases ----------------------------------------------------------


def test_limite_franchigia_5000_esatti(page):
    # Caso al limite: 5.000,00 EUR esatti, primo compenso dell'anno. La franchigia
    # dell'art. 44 co. 2 DL 269/2003 e' "fino a 5.000 euro": nessun contributo INPS.
    # Atteso: ritenuta 1.000,00; netto 4.000,00 (tool e sito devono coincidere).
    # Norma: art. 25 DPR 600/1973; art. 44 co. 2 DL 269/2003.
    r = _tool(5000, descrizione="Consulenza occasionale")
    c = r["calcoli"]
    site = _site(page, 5000, addebito_bollo=False, descrizione="Consulenza occasionale")
    righe = site["righe"]
    assert _inps(righe) == 0.0, "a 5.000 EUR esatti il sito non deve trattenere contributi"
    _assert_cents(c["ritenuta_acconto_20pct"], _ritenuta(righe), "ritenuta 5.000")
    _assert_cents(c["netto_a_pagare"], _netto(righe), "netto 5.000")


def test_limite_franchigia_5001(page):
    # Phase 3 verdict (sito_errato on the rate): INPS circular 8/2026, table row 09 "Rapporti
    # occasionali autonomi (L. 326/2003 art. 44)", gives 33,72% (33% + 0,50% + 0,22%); the
    # 1,31% DIS-COLL add-on (35,03%) belongs to the collaboratori rows (02, 05, 06, 11, ...) and
    # is not due on row 09. The tool follows the circular; the site applies 35,03%, so the net
    # differs by 1/3 x 1,31% x excess (4,37 on 6.000, 0,004 on 5.001). Hand check at 6.000:
    # 1.000 x 33,72% / 3 = 112,40 -> net 4.687,60 (site 4.683,23).
    # Caso al limite: 5.001,00 EUR, un euro oltre la franchigia. Atteso normativo:
    # ritenuta 1.000,20; quota INPS del prestatore = 1/3 x 35,03% x 1,00 = 0,12;
    # netto 4.000,68. Il tool (senza INPS) da' 4.000,80: scostamento atteso di 0,12.
    # Norma: art. 25 DPR 600/1973; art. 44 co. 2 DL 269/2003.
    r = _tool(5001, descrizione="Consulenza occasionale")
    c = r["calcoli"]
    site = _site(page, 5001, addebito_bollo=False, descrizione="Consulenza occasionale")
    righe = site["righe"]
    _assert_cents(c["ritenuta_acconto_20pct"], _ritenuta(righe), "ritenuta 5.001")
    _assert_cents(c["netto_a_pagare"], _netto(righe), "netto 5.001 (sito con quota INPS)")


def test_opzione_committente_non_sostituto(page):
    # Opzione enumerata del sito: committente privato, non sostituto d'imposta
    # (DoRacc non spuntato) -> nessuna ritenuta. Il tool applica sempre il 20% (il suo
    # docstring definisce il committente come sostituto d'imposta, art. 23 e 25 DPR
    # 600/1973): opzione non offerta dal tool, caso non confrontabile.
    r = _tool(1000)
    site = _site(page, 1000, ritenuta=False, addebito_bollo=False)
    righe = site["righe"]
    pytest.skip(
        "non confrontabile: il tool non ha l'opzione 'committente non sostituto d'imposta'. "
        f"Sito (senza ritenuta): ritenuta {(_ritenuta(righe) or 0.0):.2f}, "
        f"netto {_netto(righe):.2f}; tool: ritenuta {r['calcoli']['ritenuta_acconto_20pct']:.2f}, "
        f"netto {r['calcoli']['netto_a_pagare']:.2f}"
    )


def test_opzione_compensi_gia_percepiti(page):
    # Opzione del sito: 4.000 EUR di compensi occasionali gia' percepiti nell'anno +
    # 3.000 EUR di questa ricevuta -> la franchigia di 5.000 EUR e' superata di 2.000
    # (art. 44 co. 2 DL 269/2003): quota INPS del prestatore 1/3 x 35,03% x 2.000 = 233,53.
    # Il tool non ha un parametro per i compensi gia' percepiti: non confrontabile.
    r = _tool(3000, descrizione="Consulenza occasionale")
    site = _site(page, 3000, addebito_bollo=False, descrizione="Consulenza occasionale",
                 gia_percepiti=4000)
    righe = site["righe"]
    pytest.skip(
        "non confrontabile: il tool non considera i compensi occasionali gia' percepiti "
        f"nell'anno. Sito: ritenuta {_ritenuta(righe):.2f}, quota INPS {_inps(righe):.2f}, "
        f"netto {_netto(righe):.2f}; tool: ritenuta {r['calcoli']['ritenuta_acconto_20pct']:.2f}, "
        f"netto {r['calcoli']['netto_a_pagare']:.2f}"
    )


def test_opzione_pensionato_aliquota_24(page):
    # Opzione enumerata del sito: TipoLav 2 (pensionato o iscritto ad altra forma
    # previdenziale), aliquota gestione separata 24% nel 2026. Su 6.000 EUR: quota INPS
    # del prestatore 1/3 x 24% x 1.000 = 80,00. Il tool non distingue la posizione
    # previdenziale (e non calcola l'INPS): non confrontabile.
    r = _tool(6000, descrizione="Consulenza occasionale")
    site = _site(page, 6000, addebito_bollo=False, descrizione="Consulenza occasionale",
                 tipo_lav="2")
    righe = site["righe"]
    pytest.skip(
        "non confrontabile: il tool non ha l'opzione posizione previdenziale. "
        f"Sito (pensionato, 24%): ritenuta {_ritenuta(righe):.2f}, quota INPS "
        f"{_inps(righe):.2f}, netto {_netto(righe):.2f}; tool: ritenuta "
        f"{r['calcoli']['ritenuta_acconto_20pct']:.2f}, netto {r['calcoli']['netto_a_pagare']:.2f}"
    )

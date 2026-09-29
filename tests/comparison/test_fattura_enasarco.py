"""Benchmark of fattura_enasarco against avvocatoandreani.it (Fase 1).

Site page: https://www.avvocatoandreani.it/servizi/calcolo_fattura_agente_enasarco.php
(form "FatturaEnasarco": Importo, IVA %, Contributo Enasarco % (agent share,
default 8,5), Ritenuta d'Acconto % (default 23), Inquadramento per ritenuta
(1 = senza collaboratori ne' dipendenti -> 23% sul 50%; 2 = con collaboratori
e/o dipendenti -> 23% sul 20%; 3 = vendita a domicilio -> 23% sul 78%),
Regime semplificato). Submit button: #button1.

The site result block ("DETTAGLIO FATTURA") lists: Importo Prestazione, Totale
imponibile, IVA 22%, Totale documento, Contributo obbligatorio Enasarco (only
the AGENT share, 8,5%), Ritenuta d'acconto, Netto a pagare. The preponente
share is never shown (art. 4 Regolamento Enasarco splits the 17% in equal
halves), so the tool's quota_agente is compared with the site's Enasarco row.

Massimale: the site does NOT cap a single invoice. Its own note ("I massimali
provvigionali", art. 5 Regolamento) tells the user to split the invoice when it
crosses the annual massimale: 1st part up to the massimale WITH the Enasarco
flag, 2nd part for the remainder WITHOUT it. The over-massimale cases follow
that documented procedure and sum the two site invoices.

Year: the site has no year selector; its aliquota is the editable Enasarco %
(8,5 = 17% total, in force since 2020 per the site's own table). For a year
whose aliquota differs (2019: 16,50% -> 8,25% agent), the site field is set to
that year's value, as the brief requires the same year's table on both sides.

The site keeps the option state in the server session (observed: an unticked
Enasarco flag survives a reload), so every option is set explicitly on each
submit.

Tolerance: 0.01 euro on amounts (brief). The half-cent cases compare at 0.005:
they exist to detect the cent-rounding convention, a one-cent gap is exactly
the finding there (same approach as test_fattura_avvocato.py).
"""

import re

import pytest

from tests.comparison.conftest import assert_close, goto, parse_euro

PAGE = "calcolo_fattura_agente_enasarco.php"
TOL = 0.01
TOL_MEZZO_CENTESIMO = 0.005

# Massimali provvigionali 2026 (art. 5 Regolamento Enasarco; site table and
# Fondazione Enasarco "Minimali e massimali 2026").
MASSIMALE_MONO_2026 = 45_717.00
MASSIMALE_PLURI_2026 = 30_478.00


def _call(**kwargs):
    import importlib

    import src.server  # noqa: F401  (registers every tool module)

    mod = importlib.import_module("src.tools.parcelle_professionisti")
    fn = getattr(mod, "fattura_enasarco")
    fn = getattr(fn, "fn", fn)
    return fn(**kwargs)


def _euro_in(value: float) -> str:
    return f"{value:.2f}".replace(".", ",")


def _consenso_cookie(page) -> None:
    """Click the site's consent button once it shows up.

    conftest.accept_cookies checks #accept-btn right after DOMContentLoaded,
    before the banner is rendered; until consent is given the form submit is
    ignored. Waiting for the banner here keeps conftest untouched.
    """
    btn = page.locator("#accept-btn")
    try:
        btn.wait_for(state="visible", timeout=6000)
        btn.click()
        page.wait_for_timeout(500)
    except Exception:
        pass  # no banner (consent already stored in this context)


def _set_checkbox(page, name: str, value: bool, handler: str | None = None) -> None:
    page.evaluate(
        "([n, v]) => { document.querySelector(`form#FatturaEnasarco input[name='${n}']`).checked = v; }",
        [name, value],
    )
    if handler:
        page.evaluate(f"{handler}()")  # the page's own onclick: enables/disables the % field
    assert page.is_checked(f"form#FatturaEnasarco input[name='{name}']") == value, name


def _site_fattura(
    page,
    importo: float,
    *,
    enasarco: bool = True,
    pct_enasarco: str = "8,5",
    categoria: str = "1",
) -> dict:
    """Fill and submit the site form; return {label: amount} of the result block."""
    goto(page, PAGE)
    _consenso_cookie(page)
    page.fill("input[name='Importo']", _euro_in(importo))
    _set_checkbox(page, "CalcolaDaVendite", False, "OnClickCalcolaDaVendite")
    _set_checkbox(page, "DoIva", True, "OnClickDoIva")
    page.fill("input[name='PctIva']", "22")
    _set_checkbox(page, "DoEnasarco", enasarco, "OnClickDoEnasarco")
    if enasarco:
        page.fill("input[name='PctEnasarco']", pct_enasarco)
    _set_checkbox(page, "DoRacc", True, "OnClickDoRacc")
    page.fill("input[name='PctRacc']", "23")
    page.evaluate(
        "(v) => { document.querySelector(`form#FatturaEnasarco input[name='Categoria'][value='${v}']`).checked = true; }",
        categoria,
    )
    _set_checkbox(page, "RegimeSempl", False, "OnClickRegimeSempl")
    # Trigger the submit button in JS (no coordinate clicks on a page full of
    # ad overlays) so the POST still carries Op=Calcola.
    page.evaluate("document.getElementById('button1').click()")
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(2500)
    body = page.inner_text("body")
    start = body.find("DETTAGLIO FATTURA")
    assert start >= 0, "risultato del sito non trovato (DETTAGLIO FATTURA)"
    end = body.find("Crea la Fattura", start)
    block = body[start:end if end > 0 else start + 2000]
    righe: dict[str, float] = {}
    for label, amount in re.findall(r"^(.+?)\t€\s*([\d.,]+)\s*$", block, re.MULTILINE):
        righe.setdefault(label.strip(), parse_euro(amount))
    page.wait_for_timeout(1500)  # be gentle with the site between submits
    return righe


def _riga(righe: dict, prefix: str) -> float:
    for label, value in righe.items():
        if label.startswith(prefix):
            return value
    return 0.0  # the site omits the Enasarco row when the flag is off


def _site_values(righe: dict) -> dict:
    return {
        "quota_agente": _riga(righe, "Contributo obbligatorio Enasarco"),
        "iva": _riga(righe, "IVA 22%"),
        "totale_documento": _riga(righe, "Totale documento"),
        "ritenuta": _riga(righe, "Ritenuta d'acconto"),
        "netto": _riga(righe, "Netto a pagare"),
    }


def _somma(*parti: dict) -> dict:
    return {k: round(sum(p[k] for p in parti), 2) for k in parti[0]}


def _tool_values(r: dict) -> dict:
    return {
        "quota_agente": r["contributo_enasarco"]["quota_agente"],
        "iva": r["iva_22pct"],
        "totale_documento": r["totale_fattura"],
        "ritenuta": r["ritenuta_acconto"]["importo"],
        "netto": r["netto_a_pagare"],
    }


def _confronta(tool: dict, site: dict, keys=None, tolerance=TOL):
    """Compare every key, then fail once listing all the gaps."""
    errori = []
    for key in keys or tool:
        try:
            assert_close(tool[key], site[key], tolerance=tolerance, label=key)
        except AssertionError as exc:
            errori.append(str(exc).splitlines()[0])
    assert not errori, "scostamenti tool/sito: " + "; ".join(errori)


class TestFatturaEnasarco:

    def test_mono_sotto_massimale(self, page):
        """Piano, caso 1 - monomandatario 2026, provvigioni 10.000 (sotto il massimale).

        Atteso (piano): contributo 1.700,00 (850 agente + 850 preponente, 17%
        art. 4 Regolamento Enasarco); IVA 2.200,00 (art. 16 DPR 633/1972);
        ritenuta 1.150,00 (23% sul 50%, art. 25-bis co. 1 DPR 600/1973); totale
        fattura 12.200,00; netto 10.200,00.
        """
        r = _call(provvigioni=10000, tipo_agente="monocommittente", anno=2026)
        site = _site_values(_site_fattura(page, 10000))
        _confronta(_tool_values(r), site)

    def test_mono_oltre_massimale_2026(self, page):
        """Piano, caso 2 - AL LIMITE: monomandatario 2026, provvigioni annue 50.000.

        Atteso (piano): il contributo e' dovuto entro il massimale provvigionale
        annuo per rapporto (art. 5 Regolamento Enasarco; 2026 monomandatari
        45.717): 7.771,89 in tutto, quota agente 3.885,95. Il tool: 4.250,00.
        Sito: procedura documentata nella pagina - fattura 1 di 45.717 con
        Enasarco + fattura 2 di 4.283 senza Enasarco, sommate.
        Ritenuta non confrontata: spezzare la fattura in due arrotonda due volte
        (5.257,46 + 492,55 = 5.750,01) - artefatto della divisione, non del tool.
        """
        r = _call(provvigioni=50000, tipo_agente="monocommittente", anno=2026)
        parte1 = _site_values(_site_fattura(page, MASSIMALE_MONO_2026, enasarco=True))
        parte2 = _site_values(_site_fattura(page, 50000 - MASSIMALE_MONO_2026, enasarco=False))
        site = _somma(parte1, parte2)
        _confronta(_tool_values(r), site, keys=("quota_agente", "iva", "totale_documento", "netto"))

    def test_pluri_oltre_massimale_2026(self, page):
        """Piano, caso 3 - AL LIMITE: plurimandatario 2026, provvigioni annue 40.000.

        Atteso (piano): massimale plurimandatari 2026 30.478 (art. 5 Regolamento
        Enasarco): contributo massimo 5.181,26, quota agente 2.590,63. Il tool:
        6.800,00 (quota agente 3.400,00): tipo_agente non incide. Sito: fattura
        1 di 30.478 con Enasarco + fattura 2 di 9.522 senza, sommate.
        """
        r = _call(provvigioni=40000, tipo_agente="pluricommittente", anno=2026)
        parte1 = _site_values(_site_fattura(page, MASSIMALE_PLURI_2026, enasarco=True))
        parte2 = _site_values(_site_fattura(page, 40000 - MASSIMALE_PLURI_2026, enasarco=False))
        site = _somma(parte1, parte2)
        _confronta(_tool_values(r), site, keys=("quota_agente", "iva", "totale_documento", "netto"))

    def test_pluri_al_massimale_2026(self, page):
        """AL LIMITE - plurimandatario 2026 esattamente al massimale (30.478).

        Atteso: fino al massimale compreso il contributo e' pieno (art. 5
        Regolamento Enasarco): quota agente 2.590,63 (8,5%), IVA 6.705,16,
        ritenuta 3.504,97 (23% su 15.239), totale 37.183,16, netto 31.087,56.
        Confine inferiore del caso 3: qui tool e sito devono coincidere.
        """
        r = _call(provvigioni=MASSIMALE_PLURI_2026, tipo_agente="pluricommittente", anno=2026)
        site = _site_values(_site_fattura(page, MASSIMALE_PLURI_2026))
        _confronta(_tool_values(r), site)

    def test_mono_al_massimale_ritenuta_mezzo_centesimo(self, page):
        """AL LIMITE - monomandatario 2026 esattamente al massimale (45.717).

        Atteso: quota agente 45.717 x 8,5% = 3.885,945 -> 3.885,95; ritenuta
        23% su 22.858,50 = 5.257,455 -> 5.257,46 con arrotondamento commerciale
        (meta' per eccesso); netto 46.631,33. Il tool usa round() su float:
        5.257,455 e' rappresentato 5.257,45499... e scende a 5.257,45 (netto
        46.631,34). Norme: art. 4-5 Regolamento Enasarco, art. 25-bis DPR
        600/1973. Tolleranza 0.005: il caso rileva la convenzione di
        arrotondamento al centesimo.
        """
        r = _call(provvigioni=MASSIMALE_MONO_2026, tipo_agente="monocommittente", anno=2026)
        site = _site_values(_site_fattura(page, MASSIMALE_MONO_2026))
        _confronta(_tool_values(r), site, tolerance=TOL_MEZZO_CENTESIMO)

    def test_iva_mezzo_centesimo(self, page):
        """AL LIMITE - IVA esattamente a meta' centesimo: 1.234,75 x 22% = 271,645.

        Atteso (aritmetica, arrotondamento commerciale): IVA 271,65, totale
        documento 1.506,40, quota agente 104,95 (8,5% = 104,95375), ritenuta
        142,00 (23% su 617,375 = 141,99625), netto 1.259,45. Il tool: IVA 271,64
        (float 271,64499...), totale 1.506,39, netto 1.259,44. Norme: art. 16
        DPR 633/1972 (IVA 22%). Tolleranza 0.005 come sopra.
        """
        r = _call(provvigioni=1234.75, tipo_agente="monocommittente", anno=2026)
        site = _site_values(_site_fattura(page, 1234.75))
        _confronta(_tool_values(r), site, tolerance=TOL_MEZZO_CENTESIMO)

    def test_pluri_anno_2025(self, page):
        """Piano, caso 4 - AL LIMITE (anno diverso): plurimandatario 2025, 1.000.

        Atteso (piano): contributo 170,00 (quota agente 85,00; aliquota 17%
        invariata dal 2020, art. 4 Regolamento Enasarco); IVA 220,00; ritenuta
        115,00; netto 1.020,00. Il sito non ha un selettore d'anno: la sua
        aliquota di default (8,5% agente) e' quella del 2025. Minimale e
        massimale 2025 non incidono su 1.000 euro.
        """
        r = _call(provvigioni=1000, tipo_agente="pluricommittente", anno=2025)
        site = _site_values(_site_fattura(page, 1000, pct_enasarco="8,5"))
        _confronta(_tool_values(r), site)

    def test_anno_2019_aliquota_16_50(self, page):
        """AL LIMITE (anno diverso della tabella) - monomandatario 2019, 1.000.

        Atteso: aliquota 2019 16,50% (8,25% agente), dalla scala di aumenti
        della delibera Enasarco n. 72/2012 che modifica l'art. 4 del
        Regolamento (tabella pubblicata nella pagina del sito): quota agente
        82,50, netto 1.022,50. Il tool dichiara 'anno: Anno di riferimento per
        le aliquote Enasarco' ma applica sempre il 17% (quota agente 85,00,
        netto 1.020,00). Sul sito si imposta il campo Enasarco a 8,25.
        """
        r = _call(provvigioni=1000, tipo_agente="monocommittente", anno=2019)
        site = _site_values(_site_fattura(page, 1000, pct_enasarco="8,25"))
        _confronta(_tool_values(r), site)

    def test_con_dipendenti_ritenuta_20pct(self, page):
        """NON CONFRONTABILE - agente con collaboratori e/o dipendenti, 10.000.

        Atteso (piano): ritenuta 23% sul 20% delle provvigioni (art. 25-bis
        co. 2 DPR 600/1973) = 460,00; netto 10.890,00. Il sito offre
        l'inquadramento; il tool no (ritenuta fissa al 23% sul 50%): il caso
        registra il valore del sito e viene saltato.
        """
        site = _site_values(_site_fattura(page, 10000, categoria="2"))
        r = _call(provvigioni=10000, tipo_agente="monocommittente", anno=2026)
        pytest.skip(
            "tool senza opzione 'con dipendenti' (art. 25-bis co. 2 DPR 600/1973): "
            f"sito ritenuta {site['ritenuta']:.2f} netto {site['netto']:.2f}; "
            f"tool (sempre 23% sul 50%) ritenuta {r['ritenuta_acconto']['importo']:.2f} "
            f"netto {r['netto_a_pagare']:.2f}"
        )

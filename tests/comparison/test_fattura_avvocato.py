"""Benchmark of fattura_avvocato against avvocatoandreani.it (Fase 1).

Site page: https://www.avvocatoandreani.it/servizi/calcolo_fattura_studio_legale.php
(form "Fattura": Onorari, Spese Generali, Ritenuta d'Acconto, Regime Semplificato
-> Tipo Regime / Addebito bollo). The site always applies the Cassa Forense 4%
and has no switch to drop it.

Site settings used to mirror the tool:
- Spese Generali unchecked (the tool has no 15% flat-rate expenses);
- ordinario: Ritenuta d'Acconto checked, Regime Semplificato unchecked;
- forfettario: Regime Semplificato checked, Tipo Regime = 1 ("Regime forfettario
  agevolato 2014"), Addebito bollo checked (the tool always charges the 2 euro
  stamp duty to the client when due), Ritenuta checked on purpose to verify
  that the site itself drops it (art. 1 co. 67 L. 190/2014).

Tolerance: 0.01 euro on amounts (brief), except the half-cent rounding cases,
which exist to detect the cent-rounding convention and so compare at the cent
(0.005): a one-cent gap is exactly the finding there.

TestNotaSpese below is the pre-existing arithmetic check of nota_spese and is
left untouched.
"""

import re

import pytest

from tests.comparison.conftest import assert_close, goto, parse_euro

PAGE = "calcolo_fattura_studio_legale.php"
TOL = 0.01


def _call(fn_name, **kwargs):
    import importlib
    mod = importlib.import_module("src.tools.fatturazione_avvocati")
    fn = getattr(mod, fn_name)
    fn = getattr(fn, "fn", fn)
    return fn(**kwargs)


def _euro_in(value: float) -> str:
    return f"{value:.2f}".replace(".", ",")


def _consenso_cookie(page) -> None:
    """Click the site's consent button once it shows up.

    conftest.accept_cookies checks #accept-btn right after DOMContentLoaded,
    before the banner is rendered; until consent is given the page ignores
    clicks and the form submit (observed: checkbox clicks without effect, no
    POST). Waiting for the banner here keeps conftest untouched.
    """
    btn = page.locator("#accept-btn")
    try:
        btn.wait_for(state="visible", timeout=10000)
        btn.click()
        page.wait_for_timeout(500)
    except Exception:
        pass  # no banner (consent already stored): nothing to do


def _set_checkbox(page, name: str, value: bool) -> None:
    page.evaluate(
        "([n, v]) => { document.querySelector(`form#Fattura input[name='${n}']`).checked = v; }",
        [name, value],
    )
    assert page.is_checked(f"form#Fattura input[name='{name}']") == value, name


def _site_fattura(page, onorari: float, *, forfettario: bool, addebito_bollo: bool = True) -> dict:
    """Fill and submit the site form; return {'righe': {label: amount}, 'testo': block}."""
    goto(page, PAGE)
    _consenso_cookie(page)
    page.fill("input[name='Importo']", _euro_in(onorari))
    # Set the checkbox states in JS (no coordinate clicks on a page full of ad
    # overlays) and run the page's own onclick handlers, which only show/hide
    # the dependent rows.
    _set_checkbox(page, "DoSpeseGen", False)
    page.evaluate("OnClickDoSpeseGen()")
    _set_checkbox(page, "DoRacc", True)
    _set_checkbox(page, "RegimeSempl", forfettario)
    page.evaluate("OnClickRegimeSempl()")
    if forfettario:
        page.select_option("select[name='TipoRegime']", "1")
        _set_checkbox(page, "DoBollo", addebito_bollo)
    # Trigger the submit button in JS so the POST still carries Op=Calcola.
    page.evaluate("document.getElementById('btn-calc').click()")
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
    return {"righe": righe, "testo": block}


def _riga(righe: dict, prefix: str) -> float:
    for label, value in righe.items():
        if label.startswith(prefix):
            return value
    return 0.0  # the site omits rows that do not apply (IVA, ritenuta, bollo)


def _confronta(pairs, tolerance=TOL):
    """Compare every (label, tool, site) pair, then fail once listing all gaps."""
    errori = []
    for label, ours, theirs in pairs:
        try:
            assert_close(ours, theirs, tolerance=tolerance, label=label)
        except AssertionError as exc:
            errori.append(str(exc).splitlines()[0])
    assert not errori, "scostamenti tool/sito: " + "; ".join(errori)


def _pairs_ordinario(r: dict, righe: dict):
    return [
        ("cpa", r["cpa_4pct"], _riga(righe, "Cassa Avvocati")),
        ("imponibile_iva", r["imponibile_iva"], _riga(righe, "Totale imponibile")),
        ("iva", r["iva_22pct"], _riga(righe, "IVA 22%")),
        # The tool has no 'totale documento' key: imponibile_iva + IVA is the
        # document total before the withholding (its totale_fattura is the net).
        ("totale_documento", round(r["imponibile_iva"] + r["iva_22pct"], 2), _riga(righe, "Totale documento")),
        ("ritenuta", r["ritenuta_acconto_20pct"], _riga(righe, "A dedurre ritenuta")),
        ("netto_a_pagare", r["netto_a_pagare"], _riga(righe, "Netto a pagare")),
        # totale_fattura is labelled as the invoice total but equals the net.
        ("totale_fattura(=netto)", r["totale_fattura"], _riga(righe, "Netto a pagare")),
    ]


def _pairs_forfettario(r: dict, righe: dict):
    return [
        ("cpa", r["cpa_4pct"], _riga(righe, "Cassa Avvocati")),
        ("bollo", r["bollo"], _riga(righe, "Imposta di bollo")),
        ("iva", r["iva_22pct"], _riga(righe, "IVA")),
        ("ritenuta", r["ritenuta_acconto_20pct"], _riga(righe, "A dedurre ritenuta")),
        ("totale_fattura", r["totale_fattura"], _riga(righe, "Totale documento")),
    ]


class TestFatturaAvvocato:

    def test_ordinario_con_cpa(self, page):
        """Piano, caso 1 - ordinario con CPA, compenso 1.000.

        Atteso (piano): CPA 40,00; imponibile IVA 1.040,00; IVA 228,80; ritenuta
        200,00 (20% del solo compenso, art. 25 DPR 600/1973); totale documento
        1.268,80; netto 1.068,80. Norme: art. 11 L. 576/1980 (CPA 4%), art. 16
        DPR 633/1972 (IVA 22%), art. 25 DPR 600/1973.
        """
        r = _call("fattura_avvocato", imponibile=1000, regime="ordinario", cpa=True)
        site = _site_fattura(page, 1000, forfettario=False)
        _confronta(_pairs_ordinario(r, site["righe"]))

    def test_ordinario_importo_non_tondo(self, page):
        """Ordinario, compenso 12.345,67 (arrotondamenti su importo non tondo).

        Atteso (aritmetica): CPA 493,83; imponibile IVA 12.839,50; IVA 2.824,69;
        ritenuta 2.469,13; netto 13.195,06. Norme come il caso 1.
        """
        r = _call("fattura_avvocato", imponibile=12345.67, regime="ordinario", cpa=True)
        site = _site_fattura(page, 12345.67, forfettario=False)
        _confronta(_pairs_ordinario(r, site["righe"]))

    def test_ordinario_iva_mezzo_centesimo_per_difetto(self, page):
        """AL LIMITE - IVA esattamente a meta' centesimo: 1.040,25 x 22% = 228,855.

        Compenso 1.000,24 -> CPA 40,01 -> imponibile IVA 1.040,25. Arrotondamento
        commerciale al centesimo (meta' per eccesso, criterio generale dell'euro,
        art. 5 Reg. CE 1103/97): IVA 228,86, netto 1.069,06. Il tool usa round()
        su float: 228.855 e' rappresentato 228.85499... e scende a 228,85.
        Tolleranza 0.005: il caso serve a vedere la convenzione di arrotondamento
        (con la tolleranza di 0,01 del brief fallirebbe comunque: in float la
        differenza vale 0.01000000000002).
        """
        r = _call("fattura_avvocato", imponibile=1000.24, regime="ordinario", cpa=True)
        site = _site_fattura(page, 1000.24, forfettario=False)
        _confronta(_pairs_ordinario(r, site["righe"]), tolerance=0.005)

    def test_ordinario_iva_mezzo_centesimo_per_eccesso(self, page):
        """AL LIMITE - IVA a meta' centesimo che il float del tool arrotonda in su.

        Compenso 1.000,72 -> CPA 40,03 -> imponibile IVA 1.040,75 -> IVA 228,965:
        qui round() sale a 228,97 come l'arrotondamento commerciale. Con il caso
        precedente mostra che l'esito del tool dipende dalla rappresentazione
        binaria, non da una regola. Atteso: IVA 228,97; netto 1.069,58.
        """
        r = _call("fattura_avvocato", imponibile=1000.72, regime="ordinario", cpa=True)
        site = _site_fattura(page, 1000.72, forfettario=False)
        _confronta(_pairs_ordinario(r, site["righe"]), tolerance=0.005)

    def test_forfettario_soglia_bollo_esclusa(self, page):
        """Piano, caso 2 - AL LIMITE: compenso 74,49 + CPA 2,98 = 77,47.

        Atteso (piano): nessun bollo perche' l'importo non supera 77,47 euro
        (art. 13 Tariffa parte I DPR 642/1972, nota 2); IVA e ritenuta a zero
        (art. 1 co. 54-89 e co. 67 L. 190/2014); totale 77,47.
        """
        r = _call("fattura_avvocato", imponibile=74.49, regime="forfettario", cpa=True)
        site = _site_fattura(page, 74.49, forfettario=True, addebito_bollo=True)
        assert "non soggetto a imposta di bollo" in site["testo"], site["testo"]
        assert "non soggetto a ritenuta" in site["testo"], site["testo"]
        _confronta(_pairs_forfettario(r, site["righe"]))

    def test_forfettario_soglia_bollo_base_compenso_piu_cpa(self, page):
        """AL LIMITE - compenso 74,50: la soglia di 77,47 si misura su compenso + CPA.

        Il compenso da solo (74,50) e' sotto soglia, compenso + CPA (77,48) la
        supera: bollo dovuto (art. 13 Tariffa parte I DPR 642/1972). Senza
        addebito al cliente il sito riporta "Imposta di bollo assolta
        sull'originale" e totale 77,48: si confrontano la base (imponibile_iva
        del tool) e la debenza del bollo, non il totale (il tool addebita sempre).
        """
        r = _call("fattura_avvocato", imponibile=74.5, regime="forfettario", cpa=True)
        site = _site_fattura(page, 74.5, forfettario=True, addebito_bollo=False)
        bollo_dovuto_sito = "Imposta di bollo assolta" in site["testo"]
        assert (r["bollo"] > 0) == bollo_dovuto_sito, (
            f"debenza bollo: tool={r['bollo']}, sito dovuto={bollo_dovuto_sito}"
        )
        _confronta([
            ("cpa", r["cpa_4pct"], _riga(site["righe"], "Cassa Avvocati")),
            ("compenso+cpa", r["imponibile_iva"], _riga(site["righe"], "Totale documento")),
        ])

    def test_forfettario_bollo_addebitato_sopra_soglia(self, page):
        """Piano, caso 3 - AL LIMITE: compenso 74,50, bollo addebitato al cliente.

        Atteso (piano): CPA 2,98; bollo 2,00; totale 79,48; nessuna IVA (art. 1
        co. 54-89 L. 190/2014), nessuna ritenuta (art. 1 co. 67). Il sito tratta
        il bollo riaddebitato come parte del compenso (richiama la risposta AdE
        n. 428/2022: non piu' spesa esente ex art. 15 DPR 633/1972, quindi nella
        base della rivalsa previdenziale) e calcola la CPA su compenso + bollo:
        76,50 x 4% = 3,06, totale 79,56.
        """
        r = _call("fattura_avvocato", imponibile=74.5, regime="forfettario", cpa=True)
        site = _site_fattura(page, 74.5, forfettario=True, addebito_bollo=True)
        _confronta(_pairs_forfettario(r, site["righe"]))

    def test_forfettario_importo_pieno(self, page):
        """Forfettario, compenso 2.000 con bollo addebitato (ex test aritmetico).

        Atteso (tool): CPA 80,00; bollo 2,00; totale 2.082,00; IVA e ritenuta
        zero (art. 1 co. 54-89 e 67 L. 190/2014; art. 13 Tariffa DPR 642/1972).
        Il vecchio test aritmetico attendeva 2.080,00 (senza bollo): superato
        dalla correzione dell'audit che ha introdotto il bollo.
        """
        r = _call("fattura_avvocato", imponibile=2000, regime="forfettario", cpa=True)
        site = _site_fattura(page, 2000, forfettario=True, addebito_bollo=True)
        _confronta(_pairs_forfettario(r, site["righe"]))

    def test_ordinario_senza_cpa(self):
        """Piano, caso 4 - ordinario senza CPA, compenso 1.000.

        Atteso (piano): IVA 220,00; ritenuta 200,00; netto 1.020,00.
        """
        r = _call("fattura_avvocato", imponibile=1000, regime="ordinario", cpa=False)
        assert r["iva_22pct"] == 220.0 and r["netto_a_pagare"] == 1020.0
        pytest.skip(
            "non confrontabile: il sito applica sempre la Cassa Avvocati 4% "
            "(\"calcolata automaticamente\") e non ha un'opzione per escluderla"
        )


class TestNotaSpese:

    def test_base(self):
        r = _call("nota_spese", voci=[
            {"descrizione": "Compenso fase studio", "importo": 500, "tipo": "compenso"},
            {"descrizione": "Compenso fase introduttiva", "importo": 300, "tipo": "compenso"},
        ])
        assert r["totale_compensi"] == 800.0
        # CPA on subtotale (compensi + spese generali)
        subtotale = 800.0
        cpa = round(subtotale * 0.04, 2)
        assert_close(r["cpa_4pct"], cpa, tolerance=0.01, label="cpa_nota")
        assert r["totale_nota_spese"] > 0

    def test_con_spese_generali(self):
        r = _call("nota_spese", voci=[
            {"descrizione": "Compenso", "importo": 1000, "tipo": "compenso"},
            {"descrizione": "Compenso base", "importo": 1000, "tipo": "spese_generali_15pct"},
        ])
        # spese_generali_15pct: 1000 * 0.15 = 150
        assert_close(r["totale_spese_generali_15pct"], 150.0, tolerance=0.01, label="sg_nota")
        # subtotale = 1000 (compensi) + 150 (sg) = 1150
        assert_close(r["subtotale_compensi"], 1150.0, tolerance=0.01, label="sub_nota")

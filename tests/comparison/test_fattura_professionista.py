"""Benchmark of fattura_professionista against avvocatoandreani.it (Fase 1).

Site page: https://www.avvocatoandreani.it/servizi/calcolo_fattura_generica_scorporo.php
(form "FatturaGenerica": Importo, IVA %, Contributo Previdenziale descrizione + %,
Ritenuta d'Acconto %, Regime Semplificato -> Tipo Regime / Addebito bollo).

How the site is driven to mirror the tool:
- the site has no list of professions: the contribution is a free "descrizione + %"
  row. The site includes it in the withholding base only when the description
  contains the word "Inps" (its own help text: rivalsa of the INPS gestione
  separata = compenso, subject to withholding; contributo integrativo of the
  professional funds = not subject). So gestione_separata -> "Rivalsa Inps",
  the funds -> their acronym ("Inarcassa", "CIPAG", "ENPAP");
- the percentage typed is the one of the tool, because the site does not fix it.
  For geometri the site's help text states 4% ("il 4% per la cassa previdenziale
  di avvocati, periti industriali e geometri") and the test also compares that
  statement with the tool's rate; for ENPAP the site says nothing, so the rate
  (and the IVA exemption of health services, art. 10 co. 1 n. 18 DPR 633/1972)
  cannot be benchmarked here: only the arithmetic is;
- ordinario: IVA 22% checked, Ritenuta 20% checked, Regime Semplificato off;
- forfettario: Regime Semplificato on, Tipo Regime = 1 ("Regime forfettario
  agevolato 2014", L. 190/2014), Addebito bollo on (the tool always charges the
  2 euro stamp duty to the client when due), Ritenuta left checked on purpose to
  verify that the site itself drops it (art. 1 co. 67 L. 190/2014).

Tolerance: 0.01 euro on amounts (brief). The two half-cent rounding cases exist
to detect the cent-rounding convention and so compare at the cent (0.005): a
one-cent gap is exactly the finding there.
"""

import re

from tests.comparison.conftest import assert_close, goto, parse_euro

PAGE = "calcolo_fattura_generica_scorporo.php"
FORM = "form#FatturaGenerica"
TOL = 0.01
TOL_CENT = 0.005  # half-cent cases only, see module docstring


def _call(**kwargs):
    import importlib
    mod = importlib.import_module("src.tools.parcelle_professionisti")
    fn = getattr(mod, "fattura_professionista")
    fn = getattr(fn, "fn", fn)
    return fn(**kwargs)


def _euro_in(value: float) -> str:
    return f"{value:.2f}".replace(".", ",")


def _pct_in(value: float) -> str:
    return f"{value:g}".replace(".", ",")


def _consenso_cookie(page) -> None:
    """Click the site's consent button once it shows up.

    conftest.accept_cookies checks #accept-btn right after DOMContentLoaded,
    before the banner is rendered; until consent is given the page ignores the
    form submit. Waiting for the banner here keeps conftest untouched.
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
        "([f, n, v]) => { document.querySelector(`${f} input[name='${n}']`).checked = v; }",
        [FORM, name, value],
    )
    assert page.is_checked(f"{FORM} input[name='{name}']") == value, name


def _site_fattura(page, importo: float, descrizione: str, pct_contributo: float, *,
                  forfettario: bool) -> dict:
    """Fill and submit the site form.

    Returns {'righe': {label: amount}, 'base_ritenuta': float|None,
    'testo': result block, 'pagina': whole page text}.
    """
    goto(page, PAGE)
    _consenso_cookie(page)
    pagina = page.inner_text("body")
    page.fill(f"{FORM} input[name='Importo']", _euro_in(importo))
    # Checkbox states set in JS (no coordinate clicks on a page full of ad
    # overlays), then the page's own onclick handlers, which enable the
    # dependent text fields (disabled fields would not be posted).
    _set_checkbox(page, "DoIva", True)
    page.evaluate("OnClickDoIva()")
    page.fill(f"{FORM} input[name='PctIva']", "22")
    _set_checkbox(page, "DoContr1", True)
    page.evaluate("OnClickDoContr1()")
    page.fill(f"{FORM} input[name='DesContr1']", descrizione)
    page.fill(f"{FORM} input[name='PctContr1']", _pct_in(pct_contributo))
    _set_checkbox(page, "DoContr2", False)
    page.evaluate("OnClickDoContr2()")
    _set_checkbox(page, "DoRacc", True)
    page.evaluate("OnClickDoRacc()")
    page.fill(f"{FORM} input[name='PctRacc']", "20")
    _set_checkbox(page, "IvaDifferita", False)
    _set_checkbox(page, "SplitPayment", False)
    _set_checkbox(page, "RegimeSempl", forfettario)
    page.evaluate("OnClickRegimeSempl()")
    if forfettario:
        page.select_option(f"{FORM} select[name='TipoRegime']", "1")
        _set_checkbox(page, "DoBollo", True)
    # Trigger the "Calcola" button in JS so the POST carries Calcola=Calcola
    # (not the "Scorpora & Calcola" button). Wait for the POST navigation
    # itself: a fixed pause read the old page once under heavy load.
    with page.expect_navigation(wait_until="domcontentloaded", timeout=60000):
        page.evaluate("document.getElementById('btn-calc').click()")
    page.wait_for_timeout(1500)
    body = page.inner_text("body")
    start = body.find("DETTAGLIO FATTURA")
    assert start >= 0, "risultato del sito non trovato (DETTAGLIO FATTURA)"
    end = body.find("Crea la Fattura", start)
    block = body[start:end if end > 0 else start + 2000]
    righe: dict[str, float] = {}
    for label, amount in re.findall(r"^(.+?)\t€\s*([\d.,]+)\s*$", block, re.MULTILINE):
        righe.setdefault(label.strip(), parse_euro(amount))
    m = re.search(r"ritenuta d'acconto [\d,]+% su €\s*([\d.,]+)", block)
    return {
        "righe": righe,
        "base_ritenuta": parse_euro(m.group(1)) if m else None,
        "testo": block,
        "pagina": pagina,
    }


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


def _pairs_ordinario(r: dict, site: dict, descrizione: str):
    righe = site["righe"]
    assert site["base_ritenuta"] is not None, "riga ritenuta assente sul sito: " + site["testo"]
    return [
        ("contributo", r["contributo_previdenziale"], _riga(righe, descrizione)),
        ("imponibile_iva", r["base_imponibile_iva"], _riga(righe, "Totale imponibile")),
        ("iva", r["iva"], _riga(righe, "IVA 22%")),
        ("totale_fattura", r["totale_fattura"], _riga(righe, "Totale documento")),
        ("base_ritenuta", r["base_ritenuta"], site["base_ritenuta"]),
        ("ritenuta", r["ritenuta_acconto"], _riga(righe, "A dedurre ritenuta")),
        ("netto_a_pagare", r["netto_a_pagare"], _riga(righe, "Netto a pagare")),
    ]


def _pairs_forfettario(r: dict, site: dict, descrizione: str):
    righe = site["righe"]
    return [
        ("contributo", r["contributo_previdenziale"], _riga(righe, descrizione)),
        ("bollo", r["bollo"], _riga(righe, "Imposta di bollo")),
        ("iva", r["iva"], _riga(righe, "IVA")),
        ("ritenuta", r["ritenuta_acconto"], _riga(righe, "A dedurre ritenuta")),
        ("totale_fattura", r["totale_fattura"], _riga(righe, "Totale documento")),
    ]


class TestFatturaProfessionistaOrdinario:

    def test_gestione_separata_ordinario(self, page):
        """Piano, caso 1 - gestione separata, regime ordinario, compenso 1.000.

        Atteso (piano): rivalsa INPS 40,00; imponibile IVA 1.040,00; IVA 228,80;
        ritenuta 208,00 (20% su compenso e rivalsa); totale fattura 1.268,80;
        netto 1.060,80. Norma: art. 1 co. 212 L. 662/1996 (rivalsa 4%, parte del
        compenso quindi soggetta a ritenuta); art. 25 DPR 600/1973; DPR 633/1972.
        """
        r = _call(imponibile=1000, tipo="gestione_separata", regime="ordinario")
        site = _site_fattura(page, 1000, "Rivalsa Inps", 4, forfettario=False)
        _confronta(_pairs_ordinario(r, site, "Rivalsa Inps"))

    def test_ingegnere_inarcassa_ordinario(self, page):
        """Piano, caso 2 - ingegnere (Inarcassa 4%), regime ordinario, 1.000.

        Atteso (piano): contributo integrativo 40,00 soggetto a IVA ma escluso
        dalla ritenuta: IVA 228,80; ritenuta 200,00; netto 1.068,80.
        Norma: L. 6/1981 (contributo integrativo Inarcassa); art. 25 DPR 600/1973.
        """
        r = _call(imponibile=1000, tipo="ingegnere", regime="ordinario")
        site = _site_fattura(page, 1000, "Inarcassa", 4, forfettario=False)
        _confronta(_pairs_ordinario(r, site, "Inarcassa"))

    def test_geometra_cipag_ordinario(self, page):
        """Piano, caso 3 - geometra (CIPAG), regime ordinario, 1.000.

        Atteso (piano): CIPAG 5% dal 01/01/2015 -> contributo 50,00; IVA 231,00;
        ritenuta 200,00; netto 1.081,00 ("da leggere dalla fonte"); il tool usa
        il 4% -> contributo 40,00, netto 1.068,80.
        The site does not fix the rate; its help text states 4% for geometri,
        so the site is driven at 4% and that statement is compared with the
        tool's rate. The CIPAG regulation itself is NOT benchmarked here.
        Norma: L. 773/1982 e regolamento di contribuzione CIPAG; art. 25 DPR 600/1973.
        """
        r = _call(imponibile=1000, tipo="geometra", regime="ordinario")
        site = _site_fattura(page, 1000, "CIPAG", 4, forfettario=False)
        m = re.search(r"il (\d+(?:,\d+)?)% per la cassa previdenziale di [^.]*geometri", site["pagina"])
        assert m, "testo di aiuto del sito sull'aliquota dei geometri non trovato"
        aliquota_sito = float(m.group(1).replace(",", "."))
        aliquota_tool = round(r["contributo_previdenziale"] / r["imponibile"] * 100, 4)
        pairs = [("aliquota_geometri_%", aliquota_tool, aliquota_sito)]
        pairs += _pairs_ordinario(r, site, "CIPAG")
        _confronta(pairs)

    def test_psicologo_enpap_ordinario(self, page):
        """Piano, caso 4 - psicologo (ENPAP), regime ordinario, 1.000.

        Atteso (piano): ENPAP 2% = 20,00; prestazione sanitaria esente IVA
        (art. 10 co. 1 n. 18 DPR 633/1972), nessuna IVA e bollo 2,00; ritenuta
        200,00 solo verso sostituto d'imposta. Il tool: contributo 50,00 (5%),
        IVA 231,00, netto 1.081,00.
        The site has no rate for ENPAP and no notion of health-service
        exemption: it is driven with the tool's own parameters (5%, IVA 22%), so
        only the arithmetic (contributo integrativo in the IVA base, out of the
        withholding base) is benchmarked; rate and IVA regime are not.
        """
        r = _call(imponibile=1000, tipo="psicologo", regime="ordinario")
        site = _site_fattura(page, 1000, "ENPAP", 5, forfettario=False)
        _confronta(_pairs_ordinario(r, site, "ENPAP"))

    def test_ingegnere_iva_mezzo_centesimo(self, page):
        """Aggiunto (al limite, arrotondamento) - ingegnere, compenso 1.000,24.

        Contributo 40,01; imponibile IVA 1.040,25 -> IVA esatta 228,855: the
        half-cent reveals the rounding convention (commercial half-up gives
        228,86; Python round() on the binary float gives 228,85).
        Compared at the cent (TOL_CENT) on purpose.
        Norma: DPR 633/1972 art. 21 (importi in fattura al centesimo).
        """
        r = _call(imponibile=1000.24, tipo="ingegnere", regime="ordinario")
        site = _site_fattura(page, 1000.24, "Inarcassa", 4, forfettario=False)
        _confronta(_pairs_ordinario(r, site, "Inarcassa"), tolerance=TOL_CENT)

    def test_psicologo_contributo_mezzo_centesimo(self, page):
        """Aggiunto (al limite, arrotondamento) - psicologo 5%, compenso 1.000,50.

        Contributo esatto 50,025: half-up gives 50,03 (imponibile IVA 1.050,53,
        IVA 231,12, totale 1.281,65, netto 1.081,55); Python round() on the
        binary float gives 50,02 and the gap cascades on IVA, totale and netto.
        Compared at the cent (TOL_CENT) on purpose.
        """
        r = _call(imponibile=1000.5, tipo="psicologo", regime="ordinario")
        site = _site_fattura(page, 1000.5, "ENPAP", 5, forfettario=False)
        _confronta(_pairs_ordinario(r, site, "ENPAP"), tolerance=TOL_CENT)


class TestFatturaProfessionistaForfettario:

    def test_forfettario_bollo_un_centesimo_sopra_soglia(self, page):
        """Piano, caso 5 (al limite) - forfettario, gestione separata, 74,50.

        Atteso (piano): rivalsa 2,98; importo 77,48 > 77,47: bollo 2,00; totale
        79,48; nessuna IVA e nessuna ritenuta.
        Norma: art. 1 co. 54-89 L. 190/2014 (niente IVA), co. 67 (niente
        ritenuta); art. 13 Tariffa DPR 642/1972 e art. 6 DM 17/06/2014 (bollo
        2,00 sopra 77,47). The site also applies AdE risposta 428/2022 (the
        stamp duty charged to the client is compenso and enters the base of the
        contribution): a difference there is the finding of this case.
        """
        r = _call(imponibile=74.5, tipo="gestione_separata", regime="forfettario")
        site = _site_fattura(page, 74.5, "Rivalsa Inps", 4, forfettario=True)
        assert "Imposta di bollo" in site["testo"], site["testo"]
        _confronta(_pairs_forfettario(r, site, "Rivalsa Inps"))

    def test_forfettario_bollo_non_dovuto_alla_soglia(self, page):
        """Aggiunto (al limite) - forfettario, gestione separata, 74,49.

        Atteso (piano, nota del caso 5): rivalsa 2,98; totale 77,47 = soglia,
        bollo non dovuto (dovuto solo sopra 77,47). Norma: art. 13 Tariffa
        DPR 642/1972.
        """
        r = _call(imponibile=74.49, tipo="gestione_separata", regime="forfettario")
        site = _site_fattura(page, 74.49, "Rivalsa Inps", 4, forfettario=True)
        assert "non soggetto a imposta di bollo" in site["testo"], site["testo"]
        _confronta(_pairs_forfettario(r, site, "Rivalsa Inps"))

    def test_forfettario_architetto_inarcassa(self, page):
        """Aggiunto (opzione enumerata) - forfettario, architetto, 1.000.

        Tool: contributo integrativo 40,00, bollo 2,00, totale 1.042,00, no IVA,
        no ritenuta. Norma: L. 190/2014 art. 1 co. 54-89 e co. 67; bollo DPR
        642/1972. Same bollo-in-base question as the 74,50 case (AdE risposta
        428/2022) on a contributo integrativo instead of the INPS rivalsa.
        """
        r = _call(imponibile=1000, tipo="architetto", regime="forfettario")
        site = _site_fattura(page, 1000, "Inarcassa", 4, forfettario=True)
        _confronta(_pairs_forfettario(r, site, "Inarcassa"))

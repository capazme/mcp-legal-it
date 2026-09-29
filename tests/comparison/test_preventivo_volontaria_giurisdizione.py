"""Comparison tests: preventivo_volontaria_giurisdizione vs avvocatoandreani.it.

Page: https://www.avvocatoandreani.it/servizi/calcolo-compenso-avvocati-parametri-civili-2014.php
with Tabelle = 2022 (vigenti) and Competenza = 160 "Volontaria giurisdizione".
For this competence the page loads (AJAX, ``ajsvcnpf.php``) a single
"Compenso" row per bracket with min / med / max -- no phases -- and the
bracket is picked by the user from the ``Scaglione`` select (option 25
"Fino a euro 5.200", 30 "Da euro 5.201 a euro 26.000", ...). The
"PROSPETTO FINALE" after "Calcola il Compenso" lists compenso tabellare,
spese generali, Cassa Avvocati, totale imponibile, IVA and the total
("IPOTESI DI COMPENSO LIQUIDABILE"). IVA and CPA are enabled by the
"Includi accessori" button (both on) and can then be switched off one by one;
spese generali have their own checkbox (15% by default).

The tool splits the single compenso of the table into two halves labelled
"studio" and "trattazione" (``parametri_forensi.json``: "compenso unico per
scaglione ripartito 50% studio / 50% trattazione"): only the total of the two
halves has a counterpart on the site and in the DM table, so the phases are
compared through their sum and a subset of phases is not comparable.

Norms: DM 10 marzo 2014 n. 55 as amended by DM 13 agosto 2022 n. 147 --
table of the procedimenti di volontaria giurisdizione (Tab. 7 in the tool);
art. 4 co. 1 (minimum and maximum = medium -/+ 50%); art. 2 co. 2 (spese
generali 15% of the compenso); art. 6 (value over 520.000 euro: "fino al 30
per cento in piu'" per bracket); art. 11 L. 576/1980 (CPA 4% on compensi and
spese generali); art. 16 DPR 633/1972 (IVA 22% on compensi, spese generali
and CPA).

Tolerance: 0.01 euro on every amount (the brief's default).
"""

import re

import pytest

from tests.comparison.conftest import assert_close, goto, parse_euro

_URL = "calcolo-compenso-avvocati-parametri-civili-2014.php"
_AJAX = "ajsvcnpf.php"
_TOL = 0.01
_COMPETENZA_VOLONTARIA = "160"
_LIVELLO_RADIO = {"min": 1, "medio": 2, "max": 3}
_LIVELLO_TESTO = {"min": "valore minimo", "medio": "valore medio", "max": "valore massimo"}

#: Upper bound of each bracket of the volontaria giurisdizione table mapped to
#: the site's ``Scaglione`` option. The site labels use integer lower bounds
#: ("Da euro 5.201"), the DM uses cents ("da euro 5.200,01"): the mapping
#: follows the DM, so 5.200,01 goes to the next bracket.
_SCAGLIONI_SITO = [
    (5_200, "25"),
    (26_000, "30"),
    (52_000, "40"),
    (260_000, "50"),
    (520_000, "60"),
    (1_000_000, "70"),
    (2_000_000, "80"),
    (4_000_000, "90"),
    (8_000_000, "100"),
    (16_000_000, "110"),
    (32_000_000, "120"),
]


# ---------------------------------------------------------------------------
# Tool side
# ---------------------------------------------------------------------------

def _tool(**kwargs) -> dict:
    import src.server  # noqa: F401  (registers every tool module first)
    from src.tools.fatturazione_avvocati import preventivo_volontaria_giurisdizione

    fn = getattr(preventivo_volontaria_giurisdizione, "fn", preventivo_volontaria_giurisdizione)
    res = fn(**kwargs)
    assert "errore" not in res, res
    return res


def _eur(x: float) -> str:
    """The tool's own rendering of an amount in ``testo_preventivo``."""
    return f"€{x:,.2f}"


# ---------------------------------------------------------------------------
# Site side
# ---------------------------------------------------------------------------

def _codice_scaglione(valore: float) -> str:
    for fino_a, codice in _SCAGLIONI_SITO:
        if valore <= fino_a:
            return codice
    return "130"


def _open_volontaria(page):
    goto(page, _URL, wait_ms=1500)
    # Default of the page: 2022 tables. Asserted rather than forced so that a
    # change of default on the site shows up as a failure.
    assert page.input_value("#Anno") == "2022"
    with page.expect_response(lambda r: _AJAX in r.url, timeout=20000):
        page.select_option("#Competenza", _COMPETENZA_VOLONTARIA)
    page.wait_for_timeout(1500)
    assert page.input_value("#Competenza") == _COMPETENZA_VOLONTARIA


def _select_scaglione(page, codice: str):
    if page.input_value("#Scaglione") != codice:
        with page.expect_response(lambda r: _AJAX in r.url, timeout=20000):
            page.select_option("#Scaglione", codice)
        page.wait_for_timeout(1500)
    assert page.input_value("#Scaglione") == codice
    # Volontaria giurisdizione: one "Compenso" row, no phases.
    righe = page.evaluate("document.querySelectorAll('[id^=rfase-]').length")
    assert righe == 1, f"attesa una sola riga 'Compenso', trovate {righe}"
    assert page.evaluate("document.getElementById('fase-1').innerText.trim()") == "Compenso"


# The page's controls are driven through the page's own onclick handlers
# (OnClickVsel, OnClickDoSpeseGen, OnClickAccessori, OnClickIva, OnClickCpa)
# rather than through mouse clicks: the ad scripts on the page intermittently
# swallow the first click on the form. Calling the handler is what the click
# would do, and the resulting state is asserted afterwards.


def _set_livello(page, livello: str) -> float:
    n = _LIVELLO_RADIO[livello]
    page.evaluate(f"document.forms.Parametri['Vsel1'][{n - 1}].checked = true; OnClickVsel(1, {n});")
    page.wait_for_timeout(500)
    stato = page.evaluate(
        """(n) => ({
            radio: document.forms.Parametri['Vsel1'][n - 1].checked,
            val: document.forms.Parametri['Val1'].value,
            cella: document.getElementById('v1.' + n).innerHTML
        })""",
        n,
    )
    assert stato["radio"], f"livello {livello} non selezionato sul sito"
    compenso = parse_euro(stato["val"])
    assert compenso == parse_euro(stato["cella"]), f"livello {livello} non copiato nel campo Compenso: {stato}"
    return compenso


def _set_accessori(page, spese_generali: bool, cpa: bool, iva: bool):
    page.evaluate(
        "(v) => { const f = document.forms.Parametri; f.DoSpeseGen.checked = v; OnClickDoSpeseGen(); }",
        spese_generali,
    )
    if cpa or iva:
        # "Includi accessori" switches IVA and CPA on together (and enables them).
        page.evaluate("OnClickAccessori()")
        page.wait_for_timeout(300)
        if not iva:
            page.evaluate("document.forms.Parametri.Iva.checked = false; OnClickIva();")
        if not cpa:
            page.evaluate("document.forms.Parametri.Cpa.checked = false; OnClickCpa();")
    page.wait_for_timeout(300)
    stato = page.evaluate(
        """() => { const f = document.forms.Parametri; return {
            sg: f.DoSpeseGen.checked, pct: f.PctSpeseGen.value,
            iva: f.Iva.checked && !f.Iva.disabled, cpa: f.Cpa.checked && !f.Cpa.disabled,
            racc: f.DoRacc.checked }; }"""
    )
    assert stato["sg"] == spese_generali, stato
    if spese_generali:
        assert stato["pct"].strip() == "15", stato
    assert stato["iva"] == iva, stato
    assert stato["cpa"] == cpa, stato
    assert stato["racc"] is False, stato  # no ritenuta d'acconto in the prospetto


def _submit(page):
    with page.expect_navigation(wait_until="domcontentloaded", timeout=60000):
        page.evaluate(
            "() => { const f = document.forms.Parametri;"
            " f.requestSubmit(document.getElementById('Btn-Calcola')); }"
        )
    page.wait_for_timeout(2000)


_VOCI = [
    ("compenso", re.compile(r"^Compenso tabellare\b")),
    ("spese_generali", re.compile(r"^Spese generali \( 15% sul compenso totale \)")),
    ("cpa", re.compile(r"^Cassa Avvocati \( 4% \)")),
    ("imponibile", re.compile(r"^Totale imponibile\b")),
    ("iva", re.compile(r"^IVA 22% su Imponibile")),
    ("totale", re.compile(r"^IPOTESI DI COMPENSO LIQUIDABILE")),
]


def _read_result(page, livello: str, con_accessori: bool) -> dict:
    body = page.inner_text("body")
    # Header line of the result: "Compenso, valore medio:  euro 425,00".
    m = re.search(rf"Compenso, {_LIVELLO_TESTO[livello]}:\s*€\s*([\d.,]+)", body)
    assert m, f"riga 'Compenso, {_LIVELLO_TESTO[livello]}' assente sul sito"
    out = {"_body": body, "_compenso_riga": parse_euro(m.group(1))}
    tabelle = [t.inner_text() for t in page.query_selector_all("table")]
    prospetto = next((t for t in tabelle if "PROSPETTO FINALE" in t), None)
    if not con_accessori:
        # With spese generali, CPA and IVA all off the site prints no
        # "PROSPETTO FINALE": the compenso line is the whole result.
        assert prospetto is None, prospetto
        out["_prospetto"] = ""
        out["compenso"] = out["totale"] = out["_compenso_riga"]
        return out
    assert prospetto is not None, "prospetto finale assente sul sito"
    out["_prospetto"] = prospetto
    for riga in prospetto.splitlines():
        riga = riga.strip()
        if "€" not in riga:
            continue
        for chiave, pattern in _VOCI:
            if pattern.search(riga):
                assert chiave not in out, f"voce {chiave} ripetuta nel prospetto: {prospetto}"
                out[chiave] = parse_euro(riga.rsplit("€", 1)[1])
    return out


def _site(page, valore: float, livello: str, spese_generali: bool, cpa: bool, iva: bool) -> dict:
    _open_volontaria(page)
    _select_scaglione(page, _codice_scaglione(valore))
    compenso_form = _set_livello(page, livello)
    _set_accessori(page, spese_generali, cpa, iva)
    _submit(page)
    res = _read_result(page, livello, spese_generali or cpa or iva)
    body = res["_body"]
    assert "Tabelle: 2022" in body
    assert "Competenza: volontaria giurisdizione" in body
    res["_compenso_form"] = compenso_form
    return res


def _compare(kwargs: dict, site: dict, label: str) -> dict:
    res = _tool(**kwargs)
    d = res["dettaglio_calcoli"]
    testo = res["testo_preventivo"]

    assert "compenso" in site, site["_prospetto"]
    assert_close(d["totale_compensi"], site["_compenso_form"], _TOL, f"{label}_compenso_tabella")
    assert_close(d["totale_compensi"], site["_compenso_riga"], _TOL, f"{label}_compenso_riga")
    assert_close(d["totale_compensi"], site["compenso"], _TOL, f"{label}_compenso")
    assert_close(d["spese_generali_15pct"], site.get("spese_generali", 0.0), _TOL, f"{label}_spese_generali")
    assert_close(d["cpa_4pct"], site.get("cpa", 0.0), _TOL, f"{label}_cpa")
    if "imponibile" in site:
        assert_close(d["imponibile_iva"], site["imponibile"], _TOL, f"{label}_imponibile")
    assert_close(d["iva_22pct"], site.get("iva", 0.0), _TOL, f"{label}_iva")
    assert_close(d["totale_onorari"], site["totale"], _TOL, f"{label}_totale")

    # The same site figures must be the ones written in the quotation text.
    assert f"Totale compensi: {_eur(site['compenso'])}" in testo, testo
    if "spese_generali" in site:
        assert f"Spese generali 15%: {_eur(site['spese_generali'])}" in testo, testo
    if "cpa" in site:
        assert f"CPA 4%: {_eur(site['cpa'])}" in testo, testo
    if "iva" in site:
        assert f"IVA 22%: {_eur(site['iva'])}" in testo, testo
    assert f"TOTALE ONORARI: {_eur(site['totale'])}" in testo, testo
    return res


# ---------------------------------------------------------------------------
# Cases of the plan
# ---------------------------------------------------------------------------

class TestCasiPiano:

    def test_confine_5200_tutti_accessori(self, page):
        """Upper bound of the first bracket (fino a 5.200), medium, all accessories (limit).

        Plan: compensi 425; spese generali 63,75; subtotale 488,75; CPA 19,55;
        imponibile IVA 508,30; IVA 111,83; totale 620,13. DM 147/2022 table of
        volontaria giurisdizione (medium 425); art. 2 co. 2 DM 55/2014; art. 11
        L. 576/1980; art. 16 DPR 633/1972.
        """
        kw = dict(valore_causa=5200, fasi=None, livello="medio", spese_generali=True, cpa=True, iva=True)
        site = _site(page, 5200, "medio", True, True, True)
        _compare(kw, site, "5200_medio_tutti")

    def test_max_26000_senza_spese_generali_senza_iva(self, page):
        """Upper bound of 5.200,01-26.000, maximum, CPA only (limit).

        Plan: compensi 1.064 + 1.063 = 2.127; CPA 85,08; totale 2.212,08;
        spese generali and IVA zero. Maximum = medium 1.418 + 50% (art. 4 co. 1
        DM 55/2014); CPA art. 11 L. 576/1980.
        """
        kw = dict(valore_causa=26000, fasi=None, livello="max", spese_generali=False, cpa=True, iva=False)
        site = _site(page, 26000, "max", False, True, False)
        assert "spese_generali" not in site and "iva" not in site, site["_prospetto"]
        _compare(kw, site, "26000_max_cpa")

    def test_min_100000_senza_cpa(self, page):
        """100.000 euro (bracket 52.000,01-260.000), minimum, no CPA.

        Plan: compensi 833 + 832 = 1.665; spese generali 249,75; imponibile
        1.914,75; IVA 421,25; totale 2.336,00. Minimum = medium 3.329 - 50%
        rounded to 1.665 (art. 4 co. 1 DM 55/2014); IVA art. 16 DPR 633/1972.
        """
        kw = dict(valore_causa=100000, fasi=None, livello="min", spese_generali=True, cpa=False, iva=True)
        site = _site(page, 100000, "min", True, False, True)
        assert "cpa" not in site, site["_prospetto"]
        _compare(kw, site, "100000_min_no_cpa")


# ---------------------------------------------------------------------------
# Additional limit cases
# ---------------------------------------------------------------------------

class TestCasiLimite:

    def test_primo_centesimo_5200_01_medio(self, page):
        """First cent of 5.200,01-26.000, medium, all accessories (limit).

        Expected: compenso 1.418 (DM 147/2022, "da euro 5.200,01 a euro
        26.000,00"); spese generali 212,70; CPA 65,23; imponibile 1.695,93;
        IVA 373,10; totale 2.069,03. The site has no value field for this
        bracket: the case checks the tool's bracket choice against the DM
        bound, read on the site's option "Da euro 5.201 a euro 26.000".
        """
        kw = dict(valore_causa=5200.01, livello="medio")
        site = _site(page, 5200.01, "medio", True, True, True)
        _compare(kw, site, "5200.01_medio_tutti")

    def test_confine_52000_min_nessun_accessorio(self, page):
        """Upper bound of 26.000,01-52.000, minimum, every accessory off (limit, options).

        Expected: compenso = totale = 1.168 (medium 2.336 - 50%, art. 4 co. 1
        DM 55/2014); no spese generali, CPA or IVA.
        """
        kw = dict(valore_causa=52000, livello="min", spese_generali=False, cpa=False, iva=False)
        site = _site(page, 52000, "min", False, False, False)
        assert not {"spese_generali", "cpa", "iva"} & set(site), site["_prospetto"]
        _compare(kw, site, "52000_min_nessuno")

    def test_confine_520000_max_tutti_accessori(self, page):
        """Upper bound of the last finite bracket (260.000,01-520.000), maximum (limit).

        Expected: compenso 6.804 (medium 4.536 + 50%); spese generali 1.020,60;
        CPA 312,98; imponibile 8.137,58; IVA 1.790,27; totale 9.927,85.
        """
        kw = dict(valore_causa=520000, livello="max")
        site = _site(page, 520000, "max", True, True, True)
        _compare(kw, site, "520000_max_tutti")

    def test_oltre_520000_medio(self, page):
        """600.000 euro, medium, all accessories: art. 6 DM 55/2014 (limit).

        Art. 6 (as amended by DM 147/2022): for values from 520.000 to
        1.000.000 euro the parameters of the bracket up to 520.000 are
        increased "fino al 30 per cento". The tool returns the 520.000 bracket
        unchanged (medium 4.536 -> totale 6.618,57); the site's option
        "Da euro 520.001 a euro 1.000.000" shows the increase it applies.
        """
        kw = dict(valore_causa=600000, livello="medio")
        site = _site(page, 600000, "medio", True, True, True)
        _compare(kw, site, "600000_medio_tutti")

    def test_fasi_solo_studio(self):
        """Subset of phases (fasi=['studio']): not comparable.

        The DM table of volontaria giurisdizione has a single compenso per
        bracket, and so has the site (one "Compenso" row, no phases, also on
        the published table tabella-parametri-forensi-volontaria-
        giurisdizione.html). The tool's "studio" half (213 of 425 at 5.200)
        has no counterpart to compare with.
        """
        res = _tool(valore_causa=5200, fasi=["studio"], livello="medio")
        assert res["dettaglio_calcoli"]["totale_compensi"] == 213
        pytest.skip(
            "non confrontabile: il sito (e la tabella del DM) ha un compenso unico per scaglione, "
            "senza fasi studio/trattazione"
        )

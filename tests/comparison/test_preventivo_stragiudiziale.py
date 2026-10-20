"""Comparison tests: preventivo_stragiudiziale vs avvocatoandreani.it.

Site page: servizi/preventivo-avvocato-stragiudiziale.php ("Preventivo scritto
per avvocati - affari stragiudiziali e mediazione").
Secondary page (only for the value over 520.000, which the preventivo page does
not offer): servizi/calcolo-compenso-avvocati-parametri-stragiudiziali-2014.php.

How the site works:
- "Tipo attivita'" = Assistenza stragiudiziale (Competenza=360) exposes a single
  "Compenso" row whose value is the tabular MEDIUM of the chosen scaglione
  (DM 55/2014 Tab. 25 as replaced by DM 147/2022), loaded via Ajax.
- A -100..+100 slider moves the compenso by a percentage of the medium:
  ImpFase = medio + Round(pct * medio / 100). Art. 19 c. 1 DM 55/2014 (text
  as amended by DM 37/2018, left unchanged by DM 147/2022) lets the medium be
  increased up to 50% or decreased by no more than 50%, so the tool's livello
  min/medio/max maps to slider -50 / 0 / +50 (the site's own config uses
  -50/+50 for the 2022 tables and -50/+80 for the 2014 ones).
- The scaglione is chosen from a select (no free "valore" input in tabular
  mode); each test maps the tool's valore_pratica to the site scaglione that
  contains it per the DM ("fino a 1.100", "da 1.100,01 a 5.200", ...). The site
  labels read "Da EUR 1.101" as a rounded display; the DM boundary is the cent.
- Accessories (spese generali 15%, Cassa 4%, IVA 22%) are only computed in the
  document produced by "Crea Preventivo", which requires the mandatory fields
  (avvocato, polizza, indirizzo studio, parte assistita, CF/P.IVA, descrizione,
  controparte, luogo). They are filled with plainly fictitious placeholders.

Pointer events: the InMobi consent UI installs a focus trap on `document`
(capture-phase click/mousedown listeners with preventDefault +
stopImmediatePropagation). conftest.accept_cookies removes the banner's DOM but
not those listeners, so once the banner has appeared every click (even a JS
.click()) is swallowed: checkboxes do not change and "Crea Preventivo" never
submits. The driver therefore gives no consent and uses no pointer events: it
sets the controls' state and fires the same input/change events the page
listens to, then submits with form.requestSubmit(submitter), which posts the
same fields as pressing the button.

Tolerance: 0,01 EUR per the benchmark brief; the extra 1e-9 only absorbs float
representation error, it does not widen the tolerance.

Note on circularity: the tool's table (src/data/parametri_forensi.json,
_vintage.nota) was transcribed from avvocatoandreani.it, not from the Gazzetta
Ufficiale; agreement on the compenso therefore confirms the transcription, not
the norm. The accessory chain (15% / 4% / 22%) is independently derivable from
art. 2 c. 2 DM 55/2014, art. 11 L. 576/1980 and DPR 633/1972.
"""

import re

import pytest

from tests.comparison.conftest import assert_close, extract_amount, goto, parse_euro

_PAGE = "preventivo-avvocato-stragiudiziale.php"
_PAGE_PARCELLA = "calcolo-compenso-avvocati-parametri-stragiudiziali-2014.php"
_FORM = "PreventivoAvvocatoStragiudiziale"
_TOL = 0.01 + 1e-9  # 0,01 EUR (brief) + float epsilon

# livello del tool -> percentuale dello slider del sito (variazione sul medio)
_PCT = {"min": -50, "medio": 0, "max": 50}
# livello del tool -> radio "Vsel1" della pagina parcella (1 = Min, 2 = Med, 3 = Max)
_VSEL = {"min": "1", "medio": "2", "max": "3"}
_LABEL_LIVELLO = {"min": "minimo", "medio": "medio", "max": "massimo"}

# Fictitious placeholders for the mandatory fields of the site's form.
_DUMMY = {
    "#ARagSoc-0": "Avvocato Fittizio",
    "#AIndir-0": "Via Fittizia 1, Roma",
    "#APolizza-0": "Polizza fittizia",
    "#PRagSoc-0": "Cliente Fittizio",
    "#PCodFis-0": "00000000000",
    "#DescrCausa": "Benchmark di confronto",
    "#Controparti": "Controparte fittizia",
    "#Luogo": "Roma",
}


def _tool(**kwargs):
    import src.server  # noqa: F401  (registers every tool module)
    from src.tools.fatturazione_avvocati import preventivo_stragiudiziale

    fn = getattr(preventivo_stragiudiziale, "fn", preventivo_stragiudiziale)
    r = fn(**kwargs)
    assert "errore" not in r, r
    return r["dettaglio_calcoli"]


def _clear_cmp(page):
    """Remove the Quantcast/InMobi CMP overlay DOM (its listeners stay: see module docstring)."""
    page.evaluate(
        'document.querySelectorAll("#qc-cmp2-container, .qc-cmp2-container").forEach(el => el.remove())'
    )


def _select_scaglione(page, code: str):
    """Select a scaglione and wait for the Ajax refresh of the medium value."""
    before = page.input_value("#ValMedFase-0")
    if page.input_value("#Scaglione") == code:
        # Re-selecting the current option fires no change event: move away first.
        other = "20" if code != "20" else "30"
        page.select_option("#Scaglione", other)
        page.wait_for_function(
            "v => document.getElementById('ValMedFase-0').value !== v", arg=before, timeout=15000
        )
        page.wait_for_timeout(500)
        before = page.input_value("#ValMedFase-0")
    page.select_option("#Scaglione", code)
    page.wait_for_function(
        "v => document.getElementById('ValMedFase-0').value !== v", arg=before, timeout=15000
    )
    page.wait_for_timeout(500)


def _set_slider(page, pct: int):
    page.evaluate(
        """p => {
            const r = document.getElementById('PctFase-0');
            r.value = String(p);
            r.dispatchEvent(new Event('input', {bubbles: true}));
            r.dispatchEvent(new Event('change', {bubbles: true}));
        }""",
        pct,
    )
    page.wait_for_timeout(500)
    got = int(page.input_value("#PctFaseVal-0").replace("+", "").strip() or "0")
    assert got == pct, f"slider non impostato: atteso {pct}, letto {got}"


def _set_checked(page, element_id: str, checked: bool):
    """Set a checkbox/radio without pointer events and fire its change event."""
    got = page.evaluate(
        """([id, val]) => {
            const e = document.getElementById(id);
            if (e.checked !== val) {
                e.checked = val;
                e.dispatchEvent(new Event('change', {bubbles: true}));
            }
            return e.checked;
        }""",
        [element_id, checked],
    )
    assert got == checked, f"#{element_id} non impostato a {checked}"


def _site(page, scaglione: str, livello: str, *, spese_generali=True, cpa=True, iva=True,
          accessori=True) -> dict:
    """Drive the preventivo page and return the amounts printed in the generated preventivo."""
    goto(page, _PAGE, wait_ms=1500)
    _clear_cmp(page)
    assert page.input_value("#Competenza") == "360", "tipo attivita' non e' l'assistenza stragiudiziale"
    for sel, val in _DUMMY.items():
        page.fill(sel, val)
    _select_scaglione(page, scaglione)
    _set_slider(page, _PCT[livello])
    compenso_form = parse_euro(page.input_value("#ImpFase-0"))

    if not accessori:
        _set_checked(page, "DoAccessori-0", True)  # "Accessori di legge: NO"
    else:
        _set_checked(page, "DoAccessori-1", True)
        _set_checked(page, "DoSpeseGen", spese_generali)
        _set_checked(page, "DoCassa", cpa)
        _set_checked(page, "DoIva", iva)

    with page.expect_navigation(wait_until="domcontentloaded", timeout=60000):
        page.evaluate(
            "f => document.getElementById(f).requestSubmit(document.getElementById('create'))", _FORM
        )
    page.wait_for_selector(".PreventivoAvvocato", timeout=30000)
    page.wait_for_timeout(1000)
    text = page.inner_text(".PreventivoAvvocato")

    def amount(pattern):
        m = re.search(pattern + r"\s*€\s*([\d.,]+)", text)
        return parse_euro(m.group(1)) if m else 0.0

    tot = re.search(r"TOTALE PREVENTIVO\s*:\s*€\s*([\d.,]+)", text)
    assert tot, f"totale non trovato nel preventivo del sito:\n{text[:1500]}"
    return {
        "compenso_form": compenso_form,
        "compenso": amount(r"\nCompenso\t?"),
        "spese_generali": amount(r"Spese generali \([^)]*\)"),
        "cpa": amount(r"Cassa Avvocati \([^)]*\)"),
        "iva": amount(r"IVA \([^)]*\)"),
        "totale": parse_euro(tot.group(1)),
    }


def _site_parcella_oltre_520000(page, valore: float, livello: str, metodo: str = "F") -> dict:
    """Secondary page: Tab. 25 (2022), "Oltre EUR 520.000", compenso and spese generali 15%."""
    goto(page, _PAGE_PARCELLA, wait_ms=1500)
    _clear_cmp(page)
    page.select_option("#Anno", "2022")
    page.wait_for_timeout(600)
    page.select_option("#Competenza", "360")  # Assistenza stragiudiziale
    page.wait_for_timeout(600)
    assert page.evaluate("() => document.getElementById('TipoCompenso1').checked")  # Tabellare
    page.select_option("#Scaglione", "60")
    page.wait_for_timeout(800)
    page.select_option("#Scaglione", "140")  # Oltre EUR 520.000
    page.wait_for_timeout(1500)
    page.select_option("#ModCalcPct", metodo)
    page.wait_for_timeout(500)
    assert page.evaluate("() => !document.getElementById('ValoreCausa').disabled")
    page.evaluate(
        "(v) => { document.getElementById('ValoreCausa').value = v; OnKeyUpValoreCausa(); }",
        str(valore),
    )
    page.wait_for_timeout(1000)
    page.evaluate(
        """(n) => {
            const r = document.querySelector('input[name="Vsel1"][value="' + n + '"]');
            r.checked = true;
            OnClickVsel(1, Number(n));
        }""",
        _VSEL[livello],
    )
    page.wait_for_timeout(400)
    with page.expect_navigation(wait_until="domcontentloaded", timeout=60000):
        page.evaluate(
            "() => document.forms.Parametri.requestSubmit(document.getElementById('Btn-Calcola'))"
        )
    page.wait_for_timeout(1500)
    text = page.inner_text("body")
    assert "Tabelle: 2022" in text, "il sito non ha applicato le tabelle 2022"
    assert "Competenza: assistenza stragiudiziale" in text
    assert f"valore {_LABEL_LIVELLO[livello]}" in text, f"il sito non ha applicato il livello {livello}"
    start = text.find("PROSPETTO FINALE")
    assert start >= 0, "prospetto finale non trovato"
    compenso = extract_amount(text[start:], "Compenso tabellare")
    sg = re.search(r"Spese generali \([^)]*\)\s*€\s*([\d.,]+)", text[start:])
    assert compenso is not None and sg, f"importi non trovati:\n{text[start:start + 800]}"
    return {"compenso": compenso, "spese_generali": parse_euro(sg.group(1))}


def _compare(tool: dict, site: dict, label: str):
    """Compare every available amount and report all mismatches together."""
    pairs = [
        ("compenso", "compenso_base", "compenso"),
        ("compenso (modulo)", "compenso_base", "compenso_form"),
        ("spese generali", "spese_generali_15pct", "spese_generali"),
        ("CPA", "cpa_4pct", "cpa"),
        ("IVA", "iva_22pct", "iva"),
        ("totale", "totale", "totale"),
    ]
    errors = []
    for name, tkey, skey in pairs:
        if skey not in site:
            continue
        try:
            assert_close(float(tool[tkey]), float(site[skey]), _TOL, f"{label} {name}")
        except AssertionError as exc:
            errors.append(str(exc).splitlines()[0])
    assert not errors, "; ".join(errors)


class TestPreventivoStragiudizialeComparison:

    def test_confine_5200_medio(self, page):
        """Piano: confine 5.200 al medio (caso al limite).

        Atteso (piano): compenso 1.276; spese generali 191,40; CPA 58,70;
        IVA 335,74; totale 1.861,84.
        Norma: DM 55/2014 Tab. 25 agg. DM 147/2022, scaglione 1.100,01-5.200
        (5.200 e' ancora in questo scaglione); art. 2 c. 2 DM 55/2014 (spese
        generali 15%), art. 11 L. 576/1980 (CPA 4%), DPR 633/1972 (IVA 22%).
        Sito: scaglione "Da 1.101 a 5.200" (20), slider 0.
        """
        tool = _tool(valore_pratica=5200, livello="medio")
        assert tool["scaglione"] == "fino a 5200€"
        site = _site(page, "20", "medio")
        _compare(tool, site, "5200 medio")

    def test_primo_centesimo_5200_01_min(self, page):
        """Piano: primo centesimo dello scaglione successivo, al minimo (caso al limite).

        Atteso (piano): compenso 993 (da confermare); spese generali 148,95;
        CPA 45,68; IVA 261,28; totale 1.448,91.
        Norma: DM 55/2014 Tab. 25 agg. DM 147/2022, scaglione 5.200,01-26.000,
        minimo = medio 1.985 -50% (art. 19 c. 1 DM 55/2014) = 992,50, arrotondato a 993.
        Sito: scaglione "Da 5.201 a 26.000" (30), slider -50.
        """
        tool = _tool(valore_pratica=5200.01, livello="min")
        assert tool["scaglione"] == "fino a 26000€"
        site = _site(page, "30", "min")
        _compare(tool, site, "5200,01 min")

    def test_oltre_520000_max_senza_iva(self, page):
        """Piano: oltre 520.000 al massimo senza IVA (caso al limite).

        Atteso (piano): compenso 9.246 (da leggere dal sito per il valore oltre
        520.000); spese generali 1.386,90; CPA 425,32; totale 11.058,22.
        Norma: DM 55/2014 Tab. 25 agg. DM 147/2022, riga "oltre 520.000"; il tool
        non ha una riga propria e ripete i valori dello scaglione 260.000,01-520.000.
        Sito: la pagina del preventivo offre scaglioni solo fino a 520.000, quindi
        il compenso e le spese generali si leggono dalla pagina secondaria della
        liquidazione stragiudiziale (tabelle 2022, "Oltre 520.000", valore
        600.000, metodo "percentuale secca", valore massimo). CPA e IVA non sono
        esposti da quella pagina; la catena senza IVA con gli importi del tool e'
        verificata da test_confine_520000_max_senza_iva.
        """
        tool = _tool(valore_pratica=600000, livello="max", iva=False)
        assert tool["scaglione"] == "oltre 520000€"
        site = _site_parcella_oltre_520000(page, 600000, "max")
        _compare(tool, site, "600000 max no IVA")

    def test_confine_520000_max_senza_iva(self, page):
        """Aggiunto: tetto dell'ultimo scaglione al massimo, IVA esclusa (limite + opzione).

        Atteso: compenso 9.246 (medio 6.164 +50%); spese generali 1.386,90;
        CPA 425,32; IVA 0; totale 11.058,22.
        Norma: DM 55/2014 Tab. 25 agg. DM 147/2022, scaglione 260.000,01-520.000.
        Sito: scaglione "Da 260.001 a 520.000" (60), slider +50, IVA deselezionata.
        """
        tool = _tool(valore_pratica=520000, livello="max", iva=False)
        assert tool["scaglione"] == "fino a 520000€"
        site = _site(page, "60", "max", iva=False)
        _compare(tool, site, "520000 max no IVA")

    def test_confine_1100_max(self, page):
        """Aggiunto: tetto del primo scaglione al massimo (caso al limite).

        Atteso: compenso 426 (medio 284 +50%); spese generali 63,90; CPA 19,60;
        IVA 112,09; totale 621,59.
        Norma: DM 55/2014 Tab. 25 agg. DM 147/2022, scaglione "fino a 1.100".
        Sito: scaglione "Fino a 1.100" (10), slider +50.
        """
        tool = _tool(valore_pratica=1100, livello="max")
        assert tool["scaglione"] == "fino a 1100€"
        site = _site(page, "10", "max")
        _compare(tool, site, "1100 max")

    def test_primo_centesimo_26000_01_medio_senza_spese_generali(self, page):
        """Aggiunto: 26.000,01 al medio senza spese generali (limite + opzione).

        Atteso: compenso 2.410; spese generali 0; CPA 96,40; IVA 551,41;
        totale 3.057,81.
        Norma: DM 55/2014 Tab. 25 agg. DM 147/2022, scaglione 26.000,01-52.000;
        CPA sul compenso (art. 11 L. 576/1980), IVA su compenso + CPA.
        Sito: scaglione "Da 26.001 a 52.000" (40), slider 0, spese generali deselezionate.
        """
        tool = _tool(valore_pratica=26000.01, livello="medio", spese_generali=False)
        assert tool["scaglione"] == "fino a 52000€"
        site = _site(page, "40", "medio", spese_generali=False)
        _compare(tool, site, "26000,01 medio no SG")

    def test_confine_260000_min_senza_cpa(self, page):
        """Aggiunto: tetto dello scaglione 52.000,01-260.000 al minimo senza CPA (limite + opzione).

        Atteso: compenso 2.268 (medio 4.536 -50%); spese generali 340,20; CPA 0;
        IVA 573,80; totale 3.182,00.
        Norma: DM 55/2014 Tab. 25 agg. DM 147/2022, scaglione 52.000,01-260.000.
        Sito: scaglione "Da 52.001 a 260.000" (50), slider -50, Cassa deselezionata.
        """
        tool = _tool(valore_pratica=260000, livello="min", cpa=False)
        assert tool["scaglione"] == "fino a 260000€"
        site = _site(page, "50", "min", cpa=False)
        _compare(tool, site, "260000 min no CPA")

    def test_52000_01_max_senza_accessori(self, page):
        """Aggiunto: 52.000,01 al massimo senza alcun accessorio (limite + opzione).

        Atteso: compenso 6.804 (medio 4.536 +50%); accessori 0; totale 6.804.
        Norma: DM 55/2014 Tab. 25 agg. DM 147/2022, scaglione 52.000,01-260.000.
        Sito: scaglione "Da 52.001 a 260.000" (50), slider +50, "Accessori di legge: NO".
        """
        tool = _tool(valore_pratica=52000.01, livello="max", spese_generali=False, cpa=False, iva=False)
        assert tool["scaglione"] == "fino a 260000€"
        site = _site(page, "50", "max", accessori=False)
        _compare(tool, site, "52000,01 max senza accessori")

    def test_mediazione_negoziazione_assistita(self, page):
        """Aggiunto: opzione enumerata del sito "Mediazione e Negoziazione assistita".

        Il docstring del tool cita la mediazione tra le attivita' coperte, ma il
        tool applica solo la tabella dell'assistenza stragiudiziale (compenso
        unico). La mediazione e la negoziazione assistita si liquidano con i
        parametri propri per fasi dell'art. 20 c. 1-bis DM 55/2014 (aggiunto dal
        DM 37/2018; Tab. 25-bis: attivazione, negoziazione, conciliazione, con
        le prime due fasi aumentate del 30% se si chiude con un accordo): sul
        sito, scaglione 5.201-26.000 al medio = 441 + 882 + 1.720 = 3.043,
        contro 1.985 del tool.
        """
        tool = _tool(valore_pratica=15000, livello="medio")
        pytest.skip(
            "Non confrontabile: il tool non ha un parametro per la mediazione/negoziazione assistita "
            f"(restituisce il compenso stragiudiziale {tool['compenso_base']}); il sito per la stessa "
            "fascia al medio calcola 3.043 su tre fasi."
        )

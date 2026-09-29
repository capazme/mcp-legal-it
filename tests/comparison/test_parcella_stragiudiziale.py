"""Comparison tests: parcella_stragiudiziale vs avvocatoandreani.it (parametri stragiudiziali).

Site page: https://www.avvocatoandreani.it/servizi/calcolo-compenso-avvocati-parametri-stragiudiziali-2014.php
Published table (cross-check): /servizi/tabella-parametri-forensi-assistenza-stragiudiziale.html

Norm: DM 55/2014, artt. 18-27 and Tab. 25 (attivita' stragiudiziale) as replaced by
DM 147/2022 (GU n. 236 of 8/10/2022, in force from 23/10/2022); min/max = medio -50% / +50%
(art. 19, c. 1 as amended by DM 147/2022).

How the site is driven
- Tables "2022 (vigenti)", competence "Assistenza stragiudiziale", compenso "Tabellare":
  the tool only carries the 2022 Tab. 25, so the site is pinned to the same year.
- For the six tabular brackets the site does NOT take a value: the "Valore" field is
  enabled only for "Oltre EUR 520.000". The test therefore selects the bracket the DM
  assigns to the value (fino a 1.100; 1.100,01-5.200; 5.200,01-26.000; 26.000,01-52.000;
  52.000,01-260.000; 260.000,01-520.000). The site labels them "Da EUR 1.101 a ..." as a
  rounded display; the DM boundary is the cent.
- For "Oltre EUR 520.000" the site asks for the value and offers two methods:
  "percentuale 'secca'" (F) and "a scaglioni" (S); both are read.
- The form is submitted ("Calcola il Compenso") and the amount is read from
  "Compenso tabellare" in the PROSPETTO FINALE: that is the bare fee, without the 15%
  spese generali, i.e. the same quantity as the tool's `compenso`.

Tolerance: 0,01 EUR (brief). Both sides work in whole euros (site _NdecTariffa_ = 0).
"""

import pytest

from tests.comparison.conftest import assert_close, extract_amount, goto

_URL = "calcolo-compenso-avvocati-parametri-stragiudiziali-2014.php"

# Site radio "Vsel1": 1 = Min, 2 = Med, 3 = Max
_VSEL = {"min": "1", "medio": "2", "max": "3"}
_LABEL_LIVELLO = {"min": "minimo", "medio": "medio", "max": "massimo"}


def _tool(valore_pratica, livello):
    import src.server  # noqa: F401  (registers every tool module, avoids circular imports)
    from src.tools.fatturazione_avvocati import parcella_stragiudiziale

    fn = getattr(parcella_stragiudiziale, "fn", parcella_stragiudiziale)
    out = fn(valore_pratica=valore_pratica, livello=livello)
    assert "errore" not in out, out
    return out


def _open_form(page):
    goto(page, _URL, wait_ms=1500)
    page.select_option("#Anno", "2022")
    page.wait_for_timeout(600)
    page.select_option("#Competenza", "360")  # Assistenza stragiudiziale
    page.wait_for_timeout(600)
    # "Tabellare" is the default; assert it instead of clicking (see the pointer-events note).
    assert page.evaluate("() => document.getElementById('TipoCompenso1').checked")


def _select_scaglione(page, scaglione):
    # The onchange handler (AJAX reload of min/med/max) does not fire when the
    # option is already selected: move away first.
    other = "10" if scaglione != "10" else "20"
    page.select_option("#Scaglione", other)
    page.wait_for_timeout(800)
    page.select_option("#Scaglione", scaglione)
    page.wait_for_timeout(1500)


# Note on pointer events: the InMobi consent UI installs a focus trap on `document`
# (capture-phase click/mousedown listeners calling preventDefault +
# stopImmediatePropagation). conftest.accept_cookies removes the banner's DOM but not
# those listeners, so any click, even a JS .click(), is swallowed once the banner has
# been shown (radio stays unchecked, submit never fires). The driver therefore gives no
# consent and uses no pointer events: it runs the same inline handlers the page wires
# to the controls and submits with form.requestSubmit(submitter), which posts the
# same fields as pressing "Calcola il Compenso".
def _choose_livello(page, livello):
    page.evaluate(
        """(n) => {
            const r = document.querySelector('input[name="Vsel1"][value="' + n + '"]');
            r.checked = true;
            OnClickVsel(1, Number(n));
        }""",
        _VSEL[livello],
    )
    page.wait_for_timeout(400)


def _submit_and_read(page, livello):
    _choose_livello(page, livello)
    with page.expect_navigation(wait_until="domcontentloaded", timeout=60000):
        page.evaluate(
            "() => document.forms.Parametri.requestSubmit(document.getElementById('Btn-Calcola'))"
        )
    page.wait_for_timeout(1500)
    text = page.inner_text("body")
    assert "Tabelle: 2022" in text, "site did not apply the 2022 tables"
    assert "Competenza: assistenza stragiudiziale" in text
    assert f"valore {_LABEL_LIVELLO[livello]}" in text, f"site did not apply livello {livello}"
    start = text.find("PROSPETTO FINALE")
    assert start >= 0, "result block not found"
    amount = extract_amount(text[start:], "Compenso tabellare")
    assert amount is not None, "Compenso tabellare not found"
    return amount, text


def _site_tabellare(page, scaglione, livello):
    _open_form(page)
    _select_scaglione(page, scaglione)
    amount, _ = _submit_and_read(page, livello)
    return amount


def _site_oltre_520000(page, valore, metodo, livello):
    _open_form(page)
    _select_scaglione(page, "140")  # Oltre EUR 520.000
    page.select_option("#ModCalcPct", metodo)
    page.wait_for_timeout(500)
    assert page.evaluate("() => !document.getElementById('ValoreCausa').disabled")
    # Same as typing the value: the field's onkeyup handler recomputes min/med/max.
    page.evaluate(
        """(v) => {
            document.getElementById('ValoreCausa').value = v;
            OnKeyUpValoreCausa();
        }""",
        str(valore),
    )
    page.wait_for_timeout(1000)
    amount, text = _submit_and_read(page, livello)
    return amount, text


# ---------------------------------------------------------------------------
# Tabular brackets: every bracket boundary (value at the upper limit and the first
# cent of the next bracket), covering the three levels min / medio / max.
# Norm for all rows: DM 55/2014 Tab. 25 as replaced by DM 147/2022; min/max art. 19 c. 1.
# ---------------------------------------------------------------------------
_CASI_TABELLARI = [
    # Plan case 1 - "Confine superiore del primo scaglione": atteso 284 EUR (tool); da leggere dal sito.
    pytest.param(1100, "medio", "10", id="1100-medio-confine-sup-1o-scaglione"),
    # Plan case 2 - "Primo centesimo del secondo scaglione": atteso 1.276 EUR (tool) per 1.100,01-5.200.
    pytest.param(1100.01, "medio", "20", id="1100_01-medio-primo-centesimo-2o-scaglione"),
    # Extra (limite): 5.200 is still bracket 1.100,01-5.200 -> min 638 (= 1.276 -50%).
    pytest.param(5200, "min", "20", id="5200-min-confine"),
    # Extra (limite): 5.200,01 opens bracket 5.200,01-26.000 -> min 993 (= 1.985 -50%, rounded).
    pytest.param(5200.01, "min", "30", id="5200_01-min-confine"),
    # Extra (limite): 26.000 still bracket 5.200,01-26.000 -> max 2.978 (= 1.985 +50%, rounded).
    pytest.param(26000, "max", "30", id="26000-max-confine"),
    # Extra (limite): 26.000,01 opens bracket 26.000,01-52.000 -> max 3.615 (= 2.410 +50%).
    pytest.param(26000.01, "max", "40", id="26000_01-max-confine"),
    # Extra (limite): 52.000 still bracket 26.000,01-52.000 -> medio 2.410.
    pytest.param(52000, "medio", "40", id="52000-medio-confine"),
    # Extra (limite): 52.000,01 opens bracket 52.000,01-260.000 -> medio 4.536.
    pytest.param(52000.01, "medio", "50", id="52000_01-medio-confine"),
    # Extra (limite): 260.000 still bracket 52.000,01-260.000 -> min 2.268 (= 4.536 -50%).
    pytest.param(260000, "min", "50", id="260000-min-confine"),
    # Extra (limite): 260.000,01 opens bracket 260.000,01-520.000 -> min 3.082 (= 6.164 -50%).
    pytest.param(260000.01, "min", "60", id="260000_01-min-confine"),
    # Plan case 3 - "Ultimo scaglione tabellare al massimo": atteso medio 6.164 +50% = 9.246 EUR (tool).
    pytest.param(520000, "max", "60", id="520000-max-ultimo-scaglione-tabellare"),
]


class TestParcellaStragiudizialeTabellare:

    @pytest.mark.parametrize("valore, livello, scaglione_sito", _CASI_TABELLARI)
    def test_scaglione(self, page, valore, livello, scaglione_sito):
        ours = _tool(valore, livello)["compenso"]
        site = _site_tabellare(page, scaglione_sito, livello)
        assert_close(ours, site, tolerance=0.01, label=f"strag_{valore}_{livello}")


# ---------------------------------------------------------------------------
# Value above EUR 520.000.
# Plan case 4 - "Valore oltre 520.000 euro": da leggere dal sito con entrambi i metodi; il tool
# restituisce 6.164, identico allo scaglione precedente.
# Norm: DM 55/2014 art. 22 (text in force, Normattiva): above EUR 520.000 the fee "e' liquidato
# sulla base di una percentuale progressivamente decrescente del valore dell'affare, secondo
# quanto previsto dalla allegata tabella n. 25" - a percentage of the value, not the
# 260.000,01-520.000 bracket repeated. The percentages themselves are in the Tab. 25 annex.
# Site (DM 147/2022 Tab. 25, row "oltre 520.000" as implemented by the site): 3% of the value,
# decreasing by 0,25 points every EUR 2.000.000 down to 0,25%; "secca" applies the band
# percentage to the whole value, "a scaglioni" applies each band percentage to its slice
# (the site says the latter is its own reading, not the DM's text).
# ---------------------------------------------------------------------------
_CASI_OLTRE = [
    # 600.000 lies in the first percentage band (3%): both methods give the same value.
    pytest.param(600000, "F", "medio", id="600000-medio-percentuale-secca"),
    pytest.param(600000, "S", "medio", id="600000-medio-a-scaglioni"),
    # Extra (limite): 3.000.000 crosses the 2.000.000 band -> the two site methods diverge
    # (secca: 2,75% on the whole value; a scaglioni: 3% on 2M + 2,75% on 1M).
    pytest.param(3000000, "F", "medio", id="3000000-medio-percentuale-secca"),
    pytest.param(3000000, "S", "medio", id="3000000-medio-a-scaglioni"),
]


class TestParcellaStragiudizialeOltre520000:

    @pytest.mark.parametrize("valore, metodo, livello", _CASI_OLTRE)
    def test_oltre_520000(self, page, valore, metodo, livello):
        ours = _tool(valore, livello)["compenso"]
        site, _ = _site_oltre_520000(page, valore, metodo, livello)
        assert_close(ours, site, tolerance=0.01, label=f"strag_oltre_{valore}_{metodo}_{livello}")


# ---------------------------------------------------------------------------
# Site options the tool does not expose.
# ---------------------------------------------------------------------------
class TestParcellaStragiudizialeNonConfrontabili:

    def test_tabelle_2014_2018(self):
        # Site "Tabelle: 2014-2018 (precedenti)" (DM 55/2014 original / DM 37/2018; min/max -50%/+80%).
        # Recorded during the benchmark: bracket 5.201-26.000 = 945 / 1.890 / 3.402.
        pytest.skip(
            "non confrontabile: il tool applica solo la Tab. 25 del DM 147/2022 e non ha un "
            "parametro per le tabelle 2014-2018 (fatti anteriori al 23/10/2022)"
        )

    def test_mediazione_negoziazione_assistita(self):
        # Site competence "Mediazione e Negoziazione assistita" (DM 147/2022 Tab. 25-bis, three
        # phases). Recorded during the benchmark, bracket 5.201-26.000 medio: attivazione 441,
        # negoziazione 882, conciliazione 1.720 (total 3.043) vs 1.985 of Tab. 25.
        pytest.skip(
            "non confrontabile: il tool non offre la Tab. 25-bis (mediazione e negoziazione "
            "assistita); calcola solo l'assistenza stragiudiziale della Tab. 25"
        )

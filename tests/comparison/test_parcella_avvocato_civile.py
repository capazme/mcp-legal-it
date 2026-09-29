"""Comparison tests: parcella_avvocato_civile vs avvocatoandreani.it.

Page: https://www.avvocatoandreani.it/servizi/calcolo-compenso-avvocati-parametri-civili-2014.php
(Tabelle = 2022 vigenti, Competenza = 110 "Giudizi di cognizione innanzi al
tribunale"). The site does not derive the bracket from the value: the user
picks it from the ``Scaglione`` select, and the page loads the min/med/max
per phase through an AJAX call. Only the last bracket ("Oltre 32.000.000")
takes the value of the case, entered in ``ValoreCausa`` and applied with the
"Ricalcola tabella" button.

Norm: DM 10 marzo 2014 n. 55 as amended by DM 13 agosto 2022 n. 147 --
tabella dei giudizi di cognizione innanzi al tribunale (allegato, par. 2);
art. 4 co. 1 (minimum and maximum = medium -/+ 50%); art. 6 (value over
520.000 euro: up to +30% per bracket, and "tale ultimo criterio puo' essere
utilizzato per ogni successivo raddoppio del valore della controversia").

Tolerance: 0.01 euro on every amount (the brief's default). Both sides work
in whole euros.
"""

import pytest

from tests.comparison.conftest import assert_close, goto, parse_euro

_URL = "calcolo-compenso-avvocati-parametri-civili-2014.php"
_AJAX = "ajsvcnpf.php"
_TOL = 0.01

_FASI = ["studio", "introduttiva", "istruttoria", "decisionale"]
_LIVELLO_RADIO = {"min": "1", "medio": "2", "max": "3"}

#: Upper bound of each bracket (DM 147/2022 table: "da X,01 a Y,00") mapped
#: to the site's ``Scaglione`` option value. The site labels use integer lower
#: bounds ("Da euro 26.001"), the DM uses cents ("da euro 26.000,01"): the
#: mapping follows the DM, so 26.000,01 goes to the next bracket.
_SCAGLIONI_SITO = [
    (1_100, "10"),
    (5_200, "20"),
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
_OLTRE_32M = "130"


# ---------------------------------------------------------------------------
# Tool side
# ---------------------------------------------------------------------------

def _tool(**kwargs) -> dict:
    from src.tools.fatturazione_avvocati import parcella_avvocato_civile

    fn = getattr(parcella_avvocato_civile, "fn", parcella_avvocato_civile)
    res = fn(**kwargs)
    assert "errore" not in res, res
    return res


def _tool_fasi(res: dict) -> dict:
    return {f["fase"]: f["importo"] for f in res["fasi"]}


# ---------------------------------------------------------------------------
# Site side
# ---------------------------------------------------------------------------

def _codice_scaglione(valore: float) -> str:
    for fino_a, codice in _SCAGLIONI_SITO:
        if valore <= fino_a:
            return codice
    return _OLTRE_32M


def _open(page):
    goto(page, _URL, wait_ms=1500)
    # Defaults of the page: 2022 tables, tribunal. Asserted rather than forced
    # so that a change of default on the site shows up as a failure.
    assert page.input_value("#Anno") == "2022"
    assert page.input_value("#Competenza") == "110"


# The page's controls are driven through the page's own onclick handlers
# (OnClickVselAll, OnClickFsel, OnClickAggiornaTabella) rather than through
# mouse or DOM clicks: the ad scripts on the page intermittently swallow the
# first click on the form (the radio reverted and the handler never ran), which
# made the level silently stay on "Med". Calling the handler is exactly what
# the click would do, and the resulting state is asserted afterwards.


def _select_scaglione(page, codice: str):
    if codice == _OLTRE_32M:
        # This bracket needs the value first: no AJAX call on selection.
        page.select_option("#Scaglione", codice)
        page.wait_for_timeout(1000)
        return
    with page.expect_response(lambda r: _AJAX in r.url, timeout=20000):
        page.select_option("#Scaglione", codice)
    page.wait_for_timeout(1500)


def _set_valore_oltre(page, valore: float):
    """Enter the value for the open-ended bracket and reload the table."""
    testo = f"{valore:.2f}".replace(".", ",")
    # fill() + the page's keyup handler: typed keystrokes were intermittently
    # lost (field left empty), the same interference as the clicks above.
    page.fill("#ValoreCausa", testo)
    page.evaluate("OnKeyUpValoreCausa()")
    page.wait_for_timeout(500)
    assert page.input_value("#ValoreCausa") == testo
    with page.expect_response(lambda r: _AJAX in r.url, timeout=20000):
        page.evaluate("OnClickAggiornaTabella()")
    page.wait_for_timeout(1500)


def _set_livello(page, livello: str):
    page.evaluate(f"OnClickVselAll({_LIVELLO_RADIO[livello]})")
    page.wait_for_timeout(500)
    n = _LIVELLO_RADIO[livello]
    assert page.is_checked(f'input[name="VselAll"][value="{n}"]')
    # The handler copied the chosen column into the "Compenso" fields.
    copiati = page.evaluate(
        """(n) => [1, 2, 3, 4].map(i =>
            document.getElementById('val-' + i + '0').value.replace(/\\./g, '') ===
            document.getElementById('v' + i + '.' + n).innerHTML.replace(/[^0-9]/g, ''))""",
        n,
    )
    assert all(copiati), f"livello {livello} non applicato sul sito: {copiati}"


def _set_fasi(page, fasi: list[str]):
    for i, fase in enumerate(_FASI, start=1):
        box = f'input[name="Fsel{i}"]'
        if page.is_checked(box) != (fase in fasi):
            page.evaluate(
                "([i, v]) => { document.forms.Parametri['Fsel' + i].checked = v; OnClickFsel(i); }",
                [i, fase in fasi],
            )
            page.wait_for_timeout(300)
        assert page.is_checked(box) == (fase in fasi), box


def _read_selected(page) -> dict:
    """Amounts in the 'Compenso' column (empty for unselected phases) + total."""
    raw = page.evaluate(
        """() => ({
            studio: document.getElementById('val-10').value,
            introduttiva: document.getElementById('val-20').value,
            istruttoria: document.getElementById('val-30').value,
            decisionale: document.getElementById('val-40').value,
            totale: document.getElementById('val-tot').value
        })"""
    )
    return {k: (parse_euro(v) if v.strip() else None) for k, v in raw.items()}


def _read_table(page) -> dict:
    """min/medio/max of every phase as shown in the bracket's table."""
    raw = page.evaluate(
        """() => { const r = {}; for (let i = 1; i <= 4; i++) {
            r[i] = [1, 2, 3].map(k => document.getElementById('v' + i + '.' + k).innerHTML);
        } return r; }"""
    )
    out = {}
    for i, fase in enumerate(_FASI, start=1):
        mn, md, mx = (parse_euro(x) for x in raw[str(i)])
        out[fase] = {"min": mn, "medio": md, "max": mx}
    return out


def _site(page, valore: float, livello: str, fasi: list[str] | None = None) -> dict:
    _open(page)
    codice = _codice_scaglione(valore)
    _select_scaglione(page, codice)
    if codice == _OLTRE_32M:
        _set_valore_oltre(page, valore)
    _set_livello(page, livello)
    _set_fasi(page, fasi or _FASI)
    return _read_selected(page)


def _compare(valore: float, livello: str, fasi, site: dict, label: str):
    kwargs = {"valore_causa": valore, "livello": livello}
    if fasi is not None:
        kwargs["fasi"] = fasi
    res = _tool(**kwargs)
    ours = _tool_fasi(res)
    for fase in fasi or _FASI:
        assert site[fase] is not None, f"{label}: fase {fase} non selezionata sul sito"
        assert_close(ours[fase], site[fase], _TOL, f"{label}_{fase}")
    for fase in set(_FASI) - set(fasi or _FASI):
        assert site[fase] is None, f"{label}: fase {fase} ancora selezionata sul sito"
    assert_close(res["totale_compenso"], site["totale"], _TOL, f"{label}_totale")


# ---------------------------------------------------------------------------
# Cases of the plan
# ---------------------------------------------------------------------------

class TestCasiPiano:

    def test_confine_26000_medio(self, page):
        """Upper bound of 5.200,01-26.000, medium level.

        Plan: 919 + 777 + 1.680 + 1.701 = 5.077 (DM 147/2022, tribunal table).
        """
        site = _site(page, 26000, "medio")
        _compare(26000, "medio", None, site, "26000_medio")

    def test_primo_centesimo_26000_01_medio(self, page):
        """First cent of 26.000,01-52.000 (limit).

        Plan: 1.701 + 1.204 + 1.806 + 2.905 = 7.616. The site has no value
        field for this bracket: the case checks the tool's bracket choice
        against the DM bound ("da euro 26.000,01"), read on the site's option
        "Da euro 26.001 a euro 52.000".
        """
        site = _site(page, 26000.01, "medio")
        _compare(26000.01, "medio", None, site, "26000.01_medio")

    def test_min_1100_01(self, page):
        """Minimum level just above 1.100 (limit).

        Plan: minimum = medium -50% (art. 4 co. 1 DM 55/2014): 212,50 and
        425,50 rounded up to 213 and 426 -> 213 + 213 + 426 + 426 = 1.278.
        """
        site = _site(page, 1100.01, "min")
        _compare(1100.01, "min", None, site, "1100.01_min")

    def test_oltre_520000_medio(self, page):
        """600.000 euro, medium level (art. 6 DM 55/2014, limit).

        Plan: bracket up to 520.000 (medium total 22.457) increased by 30%;
        the tool rounds phase by phase: 4.607 + 3.039 + 13.534 + 8.013 =
        29.193 (29.194,10 if the 30% were applied to the total). The site
        option "Da euro 520.001 a euro 1.000.000" shows which method it uses.
        """
        site = _site(page, 600000, "medio")
        _compare(600000, "medio", None, site, "600000_medio")

    def test_max_5200_solo_studio_introduttiva(self, page):
        """Subset of phases at the maximum level on the 5.200 bound (limit).

        Plan: maximum = medium +50%: 638 + 638 = 1.276, only studio and
        introduttiva selected on the site.
        """
        fasi = ["studio", "introduttiva"]
        site = _site(page, 5200, "max", fasi)
        _compare(5200, "max", fasi, site, "5200_max_2fasi")


# ---------------------------------------------------------------------------
# Additional limit cases
# ---------------------------------------------------------------------------

class TestCasiLimite:

    def test_min_1100_esatti(self, page):
        """1.100 exactly, minimum level: first bracket (limit).

        Plan note: 66 + 66 + 100 + 100 = 332 (medium 131/131/200/200 -50%,
        65,50 rounded up to 66).
        """
        site = _site(page, 1100, "min")
        _compare(1100, "min", None, site, "1100_min")

    def test_confine_520000_max(self, page):
        """520.000 exactly, maximum level: last bracket of the DM table (limit).

        Expected: 5.316 + 3.507 + 15.617 + 9.246 = 33.686 (medium +50%,
        art. 4 co. 1).
        """
        site = _site(page, 520000, "max")
        _compare(520000, "max", None, site, "520000_max")

    def test_520000_01_min(self, page):
        """520.000,01, minimum level: first art. 6 bracket (limit).

        Expected: medium of the 520.000 bracket +30% (art. 6), then -50%
        (art. 4 co. 1): 2.304 + 1.520 + 6.767 + 4.007 = 14.598.
        """
        site = _site(page, 520000.01, "min")
        _compare(520000.01, "min", None, site, "520000.01_min")

    def test_confine_32000000_medio(self, page):
        """32.000.000 exactly, medium level: last closed bracket (limit).

        Expected: art. 6, 16-32 milions bracket = +30% on the 8-16 milions
        one: 17.107 + 11.284 + 50.250 + 29.753 = 108.394.
        """
        site = _site(page, 32000000, "medio")
        _compare(32000000, "medio", None, site, "32000000_medio")

    def test_oltre_32000000_01_medio(self, page):
        """32.000.000,01, medium level: open-ended bracket (limit).

        Art. 6 DM 55/2014: over 8 milions "fino al 30 per cento in piu'"
        of the previous bracket, and "tale ultimo criterio puo' essere
        utilizzato per ogni successivo raddoppio del valore della
        controversia". Expected per the norm (full 30%, as the tool does for
        every other art. 6 bracket): 17.107 x 1,3 = 22.239, 11.284 x 1,3 =
        14.669, 50.250 x 1,3 = 65.325, 29.753 x 1,3 = 38.679 -> 140.912.
        The tool's "oltre" row repeats the 16-32 milions values (108.394).
        """
        site = _site(page, 32000000.01, "medio")
        _compare(32000000.01, "medio", None, site, "32000000.01_medio")

    def test_oltre_70000000_medio(self, page):
        """70.000.000, medium level: second doubling over 32 milions.

        Art. 6, "ogni successivo raddoppio": +30% on the 32-64 milions
        values, rounded per phase: 28.911 + 19.070 + 84.923 + 50.283 =
        183.187. The tool stops at 108.394.
        """
        site = _site(page, 70000000, "medio")
        _compare(70000000, "medio", None, site, "70000000_medio")

    def test_tabella_completa_tribunale(self, page):
        """All 12 closed brackets x min/medio/max x 4 phases (144 amounts).

        Checks the transcription of the tribunal table (DM 147/2022) and the
        art. 4 co. 1 (+/-50%) and art. 6 (+30%) derivations, bracket by
        bracket, on a single page (one AJAX call per bracket).
        """
        _open(page)
        errori = []
        for fino_a, codice in _SCAGLIONI_SITO:
            _select_scaglione(page, codice)
            site = _read_table(page)
            for livello in ("min", "medio", "max"):
                ours = _tool_fasi(_tool(valore_causa=fino_a, livello=livello))
                for fase in _FASI:
                    diff = abs(ours[fase] - site[fase][livello])
                    if diff > _TOL:
                        errori.append(
                            f"fino a {fino_a} {livello} {fase}: "
                            f"tool={ours[fase]} sito={site[fase][livello]}"
                        )
        assert not errori, "\n".join(errori)


# ---------------------------------------------------------------------------
# Options of the site the tool does not have
# ---------------------------------------------------------------------------

class TestNonConfrontabili:

    def test_tabelle_2014(self):
        """Site option Tabelle = 2014-2018 (DM 55/2014 original / DM 37/2018)."""
        pytest.skip(
            "Il tool non ha un parametro per l'anno delle tabelle: applica solo "
            "i valori DM 147/2022 (vigenti dal 23/10/2022); il sito offre anche "
            "le tabelle 2014-2018 per le prestazioni anteriori."
        )

    def test_competenza_diversa_dal_tribunale(self):
        """Site option Competenza (giudice di pace, corte d'appello, Cassazione...)."""
        pytest.skip(
            "Il tool usa sempre la tabella dei giudizi di cognizione innanzi al "
            "tribunale; non ha un parametro per giudice di pace, corte d'appello, "
            "Cassazione, TAR ecc., che il sito offre con tabelle proprie."
        )

    def test_valore_indeterminabile(self):
        """Site options 901-910 (valore indeterminabile, art. 5 co. 6)."""
        pytest.skip(
            "Il tool richiede un valore numerico e non gestisce le cause di valore "
            "indeterminabile (art. 5 co. 6 DM 55/2014), che il sito offre per "
            "complessita' bassa, media, alta e particolare importanza."
        )

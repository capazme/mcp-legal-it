"""Comparison tests: parcella_volontaria_giurisdizione vs avvocatoandreani.it.

Page: https://www.avvocatoandreani.it/servizi/calcolo-compenso-avvocati-parametri-civili-2014.php
with Tabelle = 2022 (vigenti) and Competenza = 160 "Volontaria giurisdizione".
Choosing the competenza reloads (AJAX, ``ajsvcnpf.php?op=2``) the bracket list
and the table; choosing a bracket reloads the table (``op=1``). For this
competenza the site shows ONE row, "Compenso", with min/med/max: there is no
split by phase and no "Totale" field, so the site value is the "Compenso"
input (``Val1``) after picking the level.

Secondary page: tabella-parametri-forensi-volontaria-giurisdizione.html, the
table the site publishes (5 brackets up to 520.000, one "Compenso" row,
min = -50%, max = +50%).

Norm: DM 10 marzo 2014 n. 55 as amended by DM 13 agosto 2022 n. 147, tabella
dei procedimenti di volontaria giurisdizione (Tab. 7 in the tool's naming);
art. 4 co. 1 (minimum and maximum = medium -/+ 50%); art. 6 (value over
520.000 euro: "fino al 30 per cento in piu'" of the previous bracket's
parameters, for 520.000-1.000.000 and for every following doubling).

Tool side: the tool splits the single compenso into "studio" + "trattazione"
(about 50/50, see the ``_note`` of parametri_forensi.json); only the TOTAL
(``totale_compenso``) is comparable with the site's "Compenso".

Tolerance: 0.01 euro on every amount (the brief's default). Both sides work
in whole euros.
"""

import re

import pytest

from tests.comparison.conftest import accept_cookies, assert_close, goto, parse_euro

_URL = "calcolo-compenso-avvocati-parametri-civili-2014.php"
_URL_TABELLA = (
    "https://www.avvocatoandreani.it/servizi/"
    "tabella-parametri-forensi-volontaria-giurisdizione.html"
)
_AJAX = "ajsvcnpf.php"
_TOL = 0.01
_COMPETENZA_VG = "160"
_LIVELLO_RADIO = {"min": "1", "medio": "2", "max": "3"}

#: Upper bound of each bracket mapped to the site's ``Scaglione`` option for
#: the volontaria giurisdizione competenza. Unlike the tribunal table there is
#: no "fino a 1.100" bracket: the first option is "Fino a euro 5.200" (code
#: 25). The site labels use integer lower bounds ("Da euro 5.201"), the DM
#: uses cents ("da euro 5.200,01"): the mapping follows the DM. Brackets over
#: 520.000 (codes 70-120) are the site's art. 6 brackets.
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
_OLTRE_32M = "130"


# ---------------------------------------------------------------------------
# Tool side
# ---------------------------------------------------------------------------

def _tool(**kwargs) -> dict:
    import src.server  # noqa: F401  (registers every module, avoids circular imports)
    from src.tools.fatturazione_avvocati import parcella_volontaria_giurisdizione

    fn = getattr(parcella_volontaria_giurisdizione, "fn", parcella_volontaria_giurisdizione)
    res = fn(**kwargs)
    assert "errore" not in res, res
    return res


# ---------------------------------------------------------------------------
# Site side (calculator)
# ---------------------------------------------------------------------------

def _codice_scaglione(valore: float) -> str:
    for fino_a, codice in _SCAGLIONI_SITO:
        if valore <= fino_a:
            return codice
    return _OLTRE_32M


def _open(page):
    goto(page, _URL, wait_ms=1500)
    # Default of the page: 2022 tables. Asserted rather than forced so that a
    # change of default on the site shows up as a failure.
    assert page.input_value("#Anno") == "2022"
    with page.expect_response(lambda r: _AJAX in r.url, timeout=20000):
        page.select_option("#Competenza", _COMPETENZA_VG)
    page.wait_for_timeout(1500)
    assert page.input_value("#Competenza") == _COMPETENZA_VG
    # The volontaria giurisdizione table has a single row, "Compenso".
    assert page.inner_text("#fase-1").strip() == "Compenso"
    assert page.query_selector("#fase-2") is None, "il sito mostra piu' di una fase"


def _select_scaglione(page, codice: str):
    if page.input_value("#Scaglione") == codice:
        # Already selected after the competenza change: no change event.
        return
    if codice == _OLTRE_32M:
        raise NotImplementedError("bracket over 32 milions not used by these tests")
    with page.expect_response(lambda r: _AJAX in r.url, timeout=20000):
        page.select_option("#Scaglione", codice)
    page.wait_for_timeout(1500)
    assert page.input_value("#Scaglione") == codice


# The level is set through the page's own onclick handler (OnClickVsel) rather
# than a mouse click: the ad scripts on the page intermittently swallow the
# first click on the form (same workaround as test_parcella_avvocato_civile).
# The resulting state is asserted afterwards.

def _set_livello(page, livello: str):
    n = _LIVELLO_RADIO[livello]
    page.evaluate(f"OnClickVsel(1, {n})")
    page.wait_for_timeout(500)
    assert page.is_checked(f'input[name="Vsel1"][value="{n}"]')
    cella = page.inner_text(f'[id="v1.{n}"]')
    campo = page.input_value('input[name="Val1"]')
    assert parse_euro(cella) == parse_euro(campo), (
        f"livello {livello} non applicato sul sito: tabella {cella}, compenso {campo}"
    )


def _site(page, valore: float, livello: str) -> dict:
    """Site 'Compenso' for the bracket of ``valore`` at ``livello``."""
    _open(page)
    codice = _codice_scaglione(valore)
    _select_scaglione(page, codice)
    _set_livello(page, livello)
    return {
        "scaglione": page.evaluate(
            "() => { const s = document.getElementById('Scaglione');"
            " return s.options[s.selectedIndex].text; }"
        ),
        "compenso": parse_euro(page.input_value('input[name="Val1"]')),
    }


def _compare(valore: float, livello: str, site: dict, label: str):
    res = _tool(valore_causa=valore, livello=livello)
    assert_close(
        res["totale_compenso"],
        site["compenso"],
        _TOL,
        f"{label} (tool {res['scaglione']}, sito {site['scaglione']})",
    )


# ---------------------------------------------------------------------------
# Cases of the plan
# ---------------------------------------------------------------------------

class TestCasiPiano:

    def test_confine_5200_medio(self, page):
        """Upper bound of the first bracket, medium level (limit).

        Plan: tool 213 + 212 = 425. DM 147/2022, volontaria giurisdizione,
        "fino a euro 5.200": compenso medio 425.
        """
        site = _site(page, 5200, "medio")
        _compare(5200, "medio", site, "5200_medio")

    def test_primo_centesimo_5200_01_medio(self, page):
        """First cent of 5.200,01-26.000, medium level (limit).

        Plan: tool 709 + 709 = 1.418. DM 147/2022: medio 1.418 for the
        bracket "da euro 5.200,01 a euro 26.000" (site option "Da euro 5.201").
        """
        site = _site(page, 5200.01, "medio")
        _compare(5200.01, "medio", site, "5200.01_medio")

    def test_sotto_1100_min(self, page):
        """1.000 euro, minimum level: is there a 'fino a 1.100' bracket? (limit)

        Plan: tool 106 + 107 = 213 (bracket "fino a 5.200"); different if the
        table had a 1.100 bracket. The site's volontaria table starts at
        "Fino a euro 5.200" (no 1.100 bracket): minimum = 425 -50% = 212,50,
        shown as 213 (art. 4 co. 1 DM 55/2014).
        """
        site = _site(page, 1000, "min")
        _compare(1000, "min", site, "1000_min")

    def test_oltre_520000_max(self, page):
        """600.000 euro, maximum level (art. 6 DM 55/2014, limit).

        Plan: tool 3.402 + 3.402 = 6.804, identical to the 520.000 bracket.
        Art. 6: for 520.000-1.000.000 "fino al 30 per cento in piu' dei
        parametri numerici previsti per le controversie di valore fino a euro
        520.000,00". The site applies the full 30% to the medium (4.536 x 1,3 =
        5.896,80 -> 5.897) and then +50% (art. 4): 8.845,50 -> 8.846.
        """
        site = _site(page, 600000, "max")
        _compare(600000, "max", site, "600000_max")


# ---------------------------------------------------------------------------
# Additional limit cases
# ---------------------------------------------------------------------------

class TestCasiLimite:

    def test_confine_26000_max(self, page):
        """26.000 exactly, maximum level: still 5.200,01-26.000 (limit).

        Expected: 1.418 +50% = 2.127 (tool 1.064 + 1.063), art. 4 co. 1.
        """
        site = _site(page, 26000, "max")
        _compare(26000, "max", site, "26000_max")

    def test_primo_centesimo_26000_01_min(self, page):
        """26.000,01, minimum level: first cent of 26.000,01-52.000 (limit).

        Expected: 2.336 -50% = 1.168 (tool 584 + 584), art. 4 co. 1.
        """
        site = _site(page, 26000.01, "min")
        _compare(26000.01, "min", site, "26000.01_min")

    def test_confine_520000_max(self, page):
        """520.000 exactly, maximum level: last bracket of the DM table (limit).

        Expected: 4.536 +50% = 6.804 (tool 3.402 + 3.402), art. 4 co. 1.
        """
        site = _site(page, 520000, "max")
        _compare(520000, "max", site, "520000_max")

    def test_primo_centesimo_oltre_520000_medio(self, page):
        """520.000,01, medium level: first cent of the art. 6 range (limit).

        Art. 6 DM 55/2014: "fino al 30 per cento in piu'" of the 520.000
        bracket. Site: 4.536 x 1,3 = 5.896,80 -> 5.897. The tool's "oltre
        520.000" row repeats the 520.000 values: 2.268 + 2.268 = 4.536.
        """
        site = _site(page, 520000.01, "medio")
        _compare(520000.01, "medio", site, "520000.01_medio")


# ---------------------------------------------------------------------------
# Published table (secondary page)
# ---------------------------------------------------------------------------

def _read_tabella_pubblicata(page) -> list[dict]:
    """The 5 brackets of the published table: upper bound + min/medio/max."""
    page.goto(_URL_TABELLA, timeout=60000, wait_until="domcontentloaded")
    accept_cookies(page)
    page.wait_for_timeout(1500)
    testo = None
    for t in page.query_selector_all("table"):
        s = t.inner_text()
        if "Compenso" in s and "Min:" in s and "Max:" in s:
            testo = s
            break
    assert testo, "tabella volontaria giurisdizione non trovata"
    importo = r"€\s*([\d.]+)"
    righe = testo.splitlines()
    riga_compenso = next(r for r in righe if r.strip().startswith("Compenso"))
    medi = [parse_euro(x) for x in re.findall(importo, riga_compenso)]
    minimi = [parse_euro(x) for x in re.findall(r"Min:\s*" + importo, testo)]
    massimi = [parse_euro(x) for x in re.findall(r"Max:\s*" + importo, testo)]
    # Upper bounds from the header ("Fino a € 5.200", "Da € 5.201 a € 26.000", ...).
    intestazione = testo[: testo.index("Compenso")]
    limiti = [parse_euro(x) for x in re.findall(r"\b(?:Fino a|a)\s*€\s*([\d.]+)", intestazione)]
    assert len(limiti) == len(medi) == len(minimi) == len(massimi) == 5, (
        limiti, medi, minimi, massimi,
    )
    return [
        {"fino_a": f, "min": mn, "medio": md, "max": mx}
        for f, mn, md, mx in zip(limiti, minimi, medi, massimi)
    ]


class TestTabellaPubblicata:

    def test_tabella_pubblicata_5_scaglioni_3_livelli(self, page):
        """All 5 brackets x min/medio/max of the published table (15 amounts).

        DM 147/2022, volontaria giurisdizione: medi 425 / 1.418 / 2.336 /
        3.329 / 4.536; min and max = medio -/+ 50% (art. 4 co. 1), rounded
        to the euro. Checks the transcription in parametri_forensi.json and
        that the tool's split studio + trattazione adds up to the table.
        """
        tabella = _read_tabella_pubblicata(page)
        assert [r["fino_a"] for r in tabella] == [5200, 26000, 52000, 260000, 520000]
        errori = []
        for riga in tabella:
            for livello in ("min", "medio", "max"):
                ours = _tool(valore_causa=riga["fino_a"], livello=livello)["totale_compenso"]
                if abs(ours - riga[livello]) > _TOL:
                    errori.append(
                        f"fino a {riga['fino_a']:.0f} {livello}: tool={ours} sito={riga[livello]}"
                    )
        assert not errori, "\n".join(errori)


# ---------------------------------------------------------------------------
# Options not comparable
# ---------------------------------------------------------------------------

class TestNonConfrontabili:

    def test_fasi_parziali_solo_studio(self):
        """Tool option fasi=['studio'] (10.000 euro, medio -> 709)."""
        pytest.skip(
            "Il sito (calcolatore e tabella pubblicata) per la volontaria "
            "giurisdizione ha un unico 'Compenso' per scaglione, senza fasi: la "
            "ripartizione studio/trattazione del tool non ha un corrispondente."
        )

    def test_valore_indeterminabile(self):
        """Site options 901-910 (valore indeterminabile, art. 5 co. 6)."""
        pytest.skip(
            "Il tool richiede un valore numerico e non gestisce il valore "
            "indeterminabile (art. 5 co. 6 DM 55/2014), che il sito offre per "
            "complessita' bassa, media, alta e particolare importanza."
        )

    def test_tabelle_2014(self):
        """Site option Tabelle = 2014-2018."""
        pytest.skip(
            "Il tool non ha un parametro per l'anno delle tabelle: applica solo "
            "i valori DM 147/2022; il sito offre anche le tabelle 2014-2018."
        )

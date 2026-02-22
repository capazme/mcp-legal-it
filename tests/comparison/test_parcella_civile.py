"""Comparison tests: parcella_avvocato_civile vs avvocatoandreani.it parametri civili 2014."""

import re
from tests.comparison.conftest import assert_close, goto, parse_euro


_URL = "calcolo-compenso-avvocati-parametri-civili-2014.php"


def _get_site_values(page, scaglione_val, vsel):
    """Select scaglione and level, return dict of 4 phase values from the form."""
    page.select_option("#Scaglione", scaglione_val)
    page.wait_for_timeout(500)

    # Click level radio for all phases (1=min, 2=medio, 3=max)
    page.click(f'input[name="VselAll"][value="{vsel}"]')
    page.wait_for_timeout(500)

    vals = page.evaluate("""() => ({
        studio: document.getElementById("val-10")?.value || "",
        introduttiva: document.getElementById("val-20")?.value || "",
        istruttoria: document.getElementById("val-30")?.value || "",
        decisionale: document.getElementById("val-40")?.value || ""
    })""")
    return {k: _parse_int(v) for k, v in vals.items()}


def _parse_int(text):
    """Parse '1.277' or '919' to int."""
    return int(text.replace(".", "").replace("€", "").strip()) if text.strip() else 0


def _our_parcella(valore_causa, livello="medio"):
    from src.tools.fatturazione_avvocati import parcella_avvocato_civile
    fn = getattr(parcella_avvocato_civile, "fn", parcella_avvocato_civile)
    return fn(valore_causa=valore_causa, livello=livello)


def _setup_page(page):
    goto(page, _URL)
    # Ensure Anno=2022, Competenza=110 (Tribunale)
    page.evaluate("""() => {
        document.getElementById('Anno').value = '2022';
        document.getElementById('Competenza').value = '110';
    }""")
    page.wait_for_timeout(500)


class TestParcellaCivileComparison:

    def test_scaglione_26000_medio(self, page):
        """Scaglione 5201-26000 medio — our most common test case."""
        _setup_page(page)
        site = _get_site_values(page, "30", "2")
        ours = _our_parcella(15000, "medio")  # 15000 falls in 5201-26000

        fasi_map = {f["fase"]: f["importo"] for f in ours["fasi"]}
        for fase in ["studio", "introduttiva", "istruttoria", "decisionale"]:
            assert_close(fasi_map[fase], site[fase], tolerance=1,
                         label=f"26k_medio_{fase}")

    def test_scaglione_5200_min(self, page):
        """Scaglione 1101-5200 min."""
        _setup_page(page)
        site = _get_site_values(page, "20", "1")
        ours = _our_parcella(3000, "min")

        fasi_map = {f["fase"]: f["importo"] for f in ours["fasi"]}
        for fase in ["studio", "introduttiva", "istruttoria", "decisionale"]:
            assert_close(fasi_map[fase], site[fase], tolerance=1,
                         label=f"5200_min_{fase}")

    def test_scaglione_52000_max(self, page):
        """Scaglione 26001-52000 max."""
        _setup_page(page)
        site = _get_site_values(page, "40", "3")
        ours = _our_parcella(40000, "max")

        fasi_map = {f["fase"]: f["importo"] for f in ours["fasi"]}
        for fase in ["studio", "introduttiva", "istruttoria", "decisionale"]:
            assert_close(fasi_map[fase], site[fase], tolerance=1,
                         label=f"52k_max_{fase}")

    def test_scaglione_260000_medio(self, page):
        """Scaglione 52001-260000 medio."""
        _setup_page(page)
        site = _get_site_values(page, "50", "2")
        ours = _our_parcella(100000, "medio")

        fasi_map = {f["fase"]: f["importo"] for f in ours["fasi"]}
        for fase in ["studio", "introduttiva", "istruttoria", "decisionale"]:
            assert_close(fasi_map[fase], site[fase], tolerance=1,
                         label=f"260k_medio_{fase}")

    def test_scaglione_1100_medio(self, page):
        """Scaglione fino a 1100 medio."""
        _setup_page(page)
        site = _get_site_values(page, "10", "2")
        ours = _our_parcella(500, "medio")

        fasi_map = {f["fase"]: f["importo"] for f in ours["fasi"]}
        for fase in ["studio", "introduttiva", "istruttoria", "decisionale"]:
            assert_close(fasi_map[fase], site[fase], tolerance=1,
                         label=f"1100_medio_{fase}")

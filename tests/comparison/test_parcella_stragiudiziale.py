"""Comparison tests: parcella_stragiudiziale vs avvocatoandreani.it parametri stragiudiziali 2014."""

from tests.comparison.conftest import assert_close, goto


_URL = "calcolo-compenso-avvocati-parametri-stragiudiziali-2014.php"


def _get_site_value(page, scaglione_val, vsel):
    """Select scaglione and level, return the single compenso value."""
    # Force JS change event: if requested value is already selected (e.g. first
    # option on page load), the browser won't fire 'change'. Pre-select a
    # different value to guarantee the handler runs.
    page.select_option("#Scaglione", "30")
    page.wait_for_timeout(300)
    page.select_option("#Scaglione", scaglione_val)
    page.wait_for_timeout(500)

    page.click(f'input[name="Vsel1"][value="{vsel}"]')
    page.wait_for_timeout(300)

    val = page.evaluate('() => document.getElementById("val-99")?.value || ""')
    return _parse_int(val)


def _parse_int(text):
    return int(text.replace(".", "").replace("\u20ac", "").strip()) if text.strip() else 0


def _our_stragiudiziale(valore_pratica, livello="medio"):
    from src.tools.fatturazione_avvocati import parcella_stragiudiziale
    fn = getattr(parcella_stragiudiziale, "fn", parcella_stragiudiziale)
    return fn(valore_pratica=valore_pratica, livello=livello)


class TestParcellaStragComparison:

    def test_scaglione_26000_medio(self, page):
        goto(page, _URL)
        site = _get_site_value(page, "30", "2")
        ours = _our_stragiudiziale(15000, "medio")
        assert_close(ours["compenso"], site, tolerance=1, label="strag_26k_medio")

    def test_scaglione_5200_min(self, page):
        goto(page, _URL)
        site = _get_site_value(page, "20", "1")
        ours = _our_stragiudiziale(3000, "min")
        assert_close(ours["compenso"], site, tolerance=1, label="strag_5200_min")

    def test_scaglione_52000_max(self, page):
        goto(page, _URL)
        site = _get_site_value(page, "40", "3")
        ours = _our_stragiudiziale(40000, "max")
        assert_close(ours["compenso"], site, tolerance=1, label="strag_52k_max")

    def test_scaglione_1100_medio(self, page):
        goto(page, _URL)
        site = _get_site_value(page, "10", "2")
        ours = _our_stragiudiziale(500, "medio")
        assert_close(ours["compenso"], site, tolerance=1, label="strag_1100_medio")

"""Comparison tests: parcella_avvocato_penale vs avvocatoandreani.it parametri penali 2014."""

from tests.comparison.conftest import assert_close, goto


_URL = "calcolo-compenso-avvocati-parametri-penali-2014.php"

# Map our competenza names to site Competenza select values
_COMP_MAP = {
    "giudice_pace": "500",
    "tribunale_monocratico": "570",
    "tribunale_collegiale": "580",
    "corte_assise": "590",
    "corte_appello": "600",
    "cassazione": "630",
}


def _get_site_values(page, competenza_val, vsel):
    """Select competenza and level, return dict of phase values."""
    page.select_option("select[name='Competenza']", competenza_val)
    page.wait_for_timeout(500)

    page.click(f'input[name="VselAll"][value="{vsel}"]')
    page.wait_for_timeout(500)

    vals = page.evaluate("""() => ({
        studio: document.getElementById("val-10")?.value || "",
        introduttiva: document.getElementById("val-20")?.value || "",
        istruttoria: document.getElementById("val-60")?.value || "",
        decisionale: document.getElementById("val-90")?.value || ""
    })""")
    return {k: _parse_int(v) for k, v in vals.items() if v.strip()}


def _parse_int(text):
    return int(text.replace(".", "").replace("\u20ac", "").strip()) if text.strip() else 0


def _our_parcella_penale(competenza, livello="medio"):
    from src.tools.fatturazione_avvocati import parcella_avvocato_penale
    fn = getattr(parcella_avvocato_penale, "fn", parcella_avvocato_penale)
    return fn(competenza=competenza, livello=livello)


def _setup_page(page):
    goto(page, _URL)
    page.evaluate("""() => {
        document.getElementById('Anno').value = '2022';
    }""")
    page.wait_for_timeout(500)


class TestParcellaPenaleComparison:

    def test_tribunale_monocratico_medio(self, page):
        _setup_page(page)
        site = _get_site_values(page, "570", "2")
        ours = _our_parcella_penale("tribunale_monocratico", "medio")

        fasi_map = {f["fase"]: f["importo"] for f in ours["fasi"]}
        for fase in ["studio", "introduttiva", "istruttoria", "decisionale"]:
            if fase in site:
                assert_close(fasi_map[fase], site[fase], tolerance=1,
                             label=f"trib_mono_medio_{fase}")

    def test_corte_assise_max(self, page):
        _setup_page(page)
        site = _get_site_values(page, "590", "3")
        ours = _our_parcella_penale("corte_assise", "max")

        fasi_map = {f["fase"]: f["importo"] for f in ours["fasi"]}
        for fase in ["studio", "introduttiva", "istruttoria", "decisionale"]:
            if fase in site:
                assert_close(fasi_map[fase], site[fase], tolerance=1,
                             label=f"corte_assise_max_{fase}")

    def test_giudice_pace_min(self, page):
        _setup_page(page)
        site = _get_site_values(page, "500", "1")
        ours = _our_parcella_penale("giudice_pace", "min")

        fasi_map = {f["fase"]: f["importo"] for f in ours["fasi"]}
        for fase in ["studio", "introduttiva", "istruttoria", "decisionale"]:
            if fase in site:
                assert_close(fasi_map[fase], site[fase], tolerance=1,
                             label=f"gdp_min_{fase}")

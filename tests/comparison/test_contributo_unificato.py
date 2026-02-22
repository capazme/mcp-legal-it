"""Comparison tests: contributo_unificato vs avvocatoandreani.it/servizi/calcolo_contributo_unificato.php."""

import re
from tests.comparison.conftest import goto, parse_euro


def _fill_and_calc(page, valore, processo="1", giudizio="1"):
    goto(page, "calcolo_contributo_unificato.php")

    page.click("input[name='TipoValore'][value='0']")  # valore determinato
    page.fill("input[name='ValoreCausa']", str(int(valore)))
    page.select_option("select[name='Processo']", processo)
    page.select_option("select[name='Giudizio']", giudizio)

    page.click("input[name='Button'][value='Calcola']")
    page.wait_for_timeout(2000)

    result_el = page.query_selector(".result")
    if result_el:
        text = result_el.inner_text()
        m = re.search(r"€?\s*([\d.]+,\d{2})", text)
        if m:
            return parse_euro(m.group(1))
    # Fallback
    body = page.inner_text("body")
    m = re.search(r"contributo\s+è\s+€?\s*([\d.]+,\d{2})", body, re.IGNORECASE)
    if m:
        return parse_euro(m.group(1))
    raise ValueError("Could not parse CU amount")


def _our_cu(valore, tipo="civile", grado="primo"):
    from src.tools.atti_giudiziari import contributo_unificato
    fn = getattr(contributo_unificato, "fn", contributo_unificato)
    return fn(valore_causa=valore, tipo_procedimento=tipo, grado=grado)


class TestContributoUnificatoComparison:

    def test_civile_primo_50k(self, page):
        site = _fill_and_calc(page, 50000, "1", "1")
        ours = _our_cu(50000)
        assert ours["importo_dovuto"] == site, f"CU: nostro={ours['importo_dovuto']}, sito={site}"

    def test_civile_primo_5k(self, page):
        site = _fill_and_calc(page, 5000, "1", "1")
        ours = _our_cu(5000)
        assert ours["importo_dovuto"] == site, f"CU: nostro={ours['importo_dovuto']}, sito={site}"

    def test_civile_primo_200k(self, page):
        site = _fill_and_calc(page, 200000, "1", "1")
        ours = _our_cu(200000)
        assert ours["importo_dovuto"] == site, f"CU: nostro={ours['importo_dovuto']}, sito={site}"

    def test_civile_primo_1k(self, page):
        site = _fill_and_calc(page, 1000, "1", "1")
        ours = _our_cu(1000)
        assert ours["importo_dovuto"] == site, f"CU: nostro={ours['importo_dovuto']}, sito={site}"

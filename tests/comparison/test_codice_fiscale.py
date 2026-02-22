"""Comparison tests: codice_fiscale vs avvocatoandreani.it/servizi/calcolo_codice_fiscale.php."""

import re
from tests.comparison.conftest import goto


def _fill_and_calc(page, cognome, nome, sesso, data_nascita_ddmmyyyy, comune, provincia=""):
    goto(page, "calcolo_codice_fiscale.php")

    page.fill("input[name='Cognome']", cognome)
    page.fill("input[name='Nome']", nome)
    page.select_option("select[name='Sesso']", sesso)
    page.fill("input[name='DataNascita']", data_nascita_ddmmyyyy)

    # Comune with autocomplete
    comune_input = page.locator("input[name='ComuneNascita']")
    comune_input.fill("")
    comune_input.type(comune, delay=100)
    page.wait_for_timeout(1500)

    # Try to click first autocomplete suggestion
    try:
        suggestion = page.locator("#ComuneNascita + ul li, .ui-autocomplete li, [role='option']").first
        if suggestion.is_visible(timeout=2000):
            suggestion.click()
            page.wait_for_timeout(500)
    except Exception:
        pass

    if provincia:
        page.fill("input[name='ProvinciaNascita']", provincia)

    page.click("#btn-calc")
    page.wait_for_timeout(2000)

    return _parse_cf(page)


def _parse_cf(page) -> str:
    body = page.inner_text("body")
    m = re.search(r"\b([A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z])\b", body)
    if m:
        return m.group(1)
    raise ValueError(f"Could not parse codice fiscale. Body excerpt: {body[:500]}")


def _our_cf(cognome, nome, sesso, data_nascita, comune):
    from src.tools.varie import codice_fiscale
    fn = getattr(codice_fiscale, "fn", codice_fiscale)
    return fn(cognome=cognome, nome=nome, sesso=sesso, data_nascita=data_nascita, comune_nascita=comune)


class TestCodiceFiscaleComparison:

    def test_rossi_mario(self, page):
        site = _fill_and_calc(page, "Rossi", "Mario", "M", "15/06/1985", "Roma")
        ours = _our_cf("Rossi", "Mario", "M", "1985-06-15", "Roma")
        assert ours["codice_fiscale"] == site, f"CF: nostro={ours['codice_fiscale']}, sito={site}"

    def test_bianchi_maria(self, page):
        site = _fill_and_calc(page, "Bianchi", "Maria", "F", "01/01/1990", "Milano")
        ours = _our_cf("Bianchi", "Maria", "F", "1990-01-01", "Milano")
        assert ours["codice_fiscale"] == site, f"CF: nostro={ours['codice_fiscale']}, sito={site}"

    def test_verdi_giuseppe(self, page):
        site = _fill_and_calc(page, "Verdi", "Giuseppe", "M", "25/12/1970", "Napoli")
        ours = _our_cf("Verdi", "Giuseppe", "M", "1970-12-25", "Napoli")
        assert ours["codice_fiscale"] == site, f"CF: nostro={ours['codice_fiscale']}, sito={site}"

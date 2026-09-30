"""Comparison tests: codice_fiscale vs avvocatoandreani.it/servizi/calcolo_codice_fiscale.php.

Norma: DM 12/03/1974 (Agenzia delle Entrate), DM 23/12/1976 per il carattere di
controllo. Tolleranza: il codice fiscale deve coincidere carattere per carattere.

Il sito legge il comune con un autocompletamento jQuery UI (la provincia e'
readonly e viene impostata dalla scelta del suggerimento): il driver digita il
nome e sceglie il suggerimento "NOME (PR)" esatto.
"""

import re
import time

import pytest

from tests.comparison.conftest import accept_cookies, goto

CF_RE = re.compile(r"\b([A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z])\b")


def _site_cf(page, cognome, nome, sesso, data_ddmmyyyy, comune):
    """Drive the site form; return (cf, suggestion label)."""
    time.sleep(1.5)
    goto(page, "calcolo_codice_fiscale.php")
    accept_cookies(page)
    page.fill("input[name='Cognome']", cognome)
    page.fill("input[name='Nome']", nome)
    page.select_option("select[name='Sesso']", sesso)
    page.fill("input[name='DataNascita']", data_ddmmyyyy)

    labels = []
    for _attempt in range(3):  # the autocomplete is asynchronous: retype if no suggestions arrive
        page.fill("#ComuneNascita", "")
        page.locator("#ComuneNascita").focus()
        page.keyboard.type(comune, delay=150)
        for _ in range(10):
            page.wait_for_timeout(700)
            labels = page.evaluate(
                "Array.from(document.querySelectorAll('ul.ui-autocomplete li')).map(e => e.innerText.trim())"
            )
            if labels:
                break
        if labels:
            break
    wanted = None
    for i, lab in enumerate(labels):
        if lab.upper().startswith(comune.upper() + " ("):
            wanted = i
            break
    if wanted is None:
        pytest.skip(f"sito: nessun suggerimento esatto per '{comune}': {labels[:5]}")
    page.locator("ul.ui-autocomplete li").nth(wanted).click(force=True)
    page.wait_for_timeout(800)
    if not page.input_value("#ProvinciaNascita"):
        # fallback: select the same item with the keyboard (arrow down x (wanted+1), Enter)
        page.locator("#ComuneNascita").focus()
        for _ in range(wanted + 1):
            page.keyboard.press("ArrowDown")
        page.keyboard.press("Enter")
        page.wait_for_timeout(800)
    if not page.input_value("#ProvinciaNascita"):
        pytest.skip("errore_sito: l'autocompletamento non ha impostato la provincia (flaky del driver/sito)")

    page.click("#btn-calc", force=True)
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(2500)
    body = page.inner_text("body")
    m = CF_RE.search(body)
    if not m:
        pytest.skip(f"sito non produce un CF (parsing): {body[:300]!r}")
    return m.group(1), labels[wanted]


def _tool(**kw):
    from src.tools.varie import codice_fiscale

    fn = getattr(codice_fiscale, "fn", codice_fiscale)
    return fn(**kw)


def _compare(page, cognome, nome, sesso, iso, ddmmyyyy, comune, **extra):
    site, _ = _site_cf(page, cognome, nome, sesso, ddmmyyyy, comune)
    ours = _tool(cognome=cognome, nome=nome, sesso=sesso, data_nascita=iso, comune_nascita=comune, **extra)
    assert "errore" not in ours, f"tool: {ours}"
    assert ours["codice_fiscale"] == site, f"tool={ours['codice_fiscale']} sito={site}"
    return ours, site


class TestCodiceFiscale:
    def test_base_maschile_roma(self, page):
        # Piano: RSSMRA85H15H501D (giugno=H, Roma=H501, controllo D)
        ours, site = _compare(page, "Rossi", "Mario", "M", "1985-06-15", "15/06/1985", "Roma")
        assert ours["codice_fiscale"] == "RSSMRA85H15H501D"

    def test_femminile_giorno_piu_40_gennaio(self, page):
        # Piano: BNCMRA90A41F205J (giorno 01+40=41, gennaio=A, Milano=F205). Limite: giorno +40.
        ours, _ = _compare(page, "Bianchi", "Maria", "F", "1990-01-01", "01/01/1990", "Milano")
        assert ours["codice_fiscale"] == "BNCMRA90A41F205J"

    def test_verdi_giuseppe_napoli(self, page):
        # Mese L (dicembre), Napoli F839.
        _compare(page, "Verdi", "Giuseppe", "M", "1970-12-25", "25/12/1970", "Napoli")

    def test_nome_vocale_accentata(self, page):
        # Piano: RSSNCL85H15H501M (o accentata = vocale; consonanti N,C,L). Limite: caratteri accentati.
        ours, _ = _compare(page, "Rossi", "Nicolò", "M", "1985-06-15", "15/06/1985", "Roma")
        assert ours["codice_fiscale"] == "RSSNCL85H15H501M"

    def test_cognome_corto_29_febbraio_estero(self, page):
        # Piano: FOXGUO00B29Z112N (cognome completato con X, Germania=Z112). Limite: 29/02 bisestile + stato estero.
        ours, _ = _compare(page, "Fo", "Ugo", "M", "2000-02-29", "29/02/2000", "Germania")
        assert ours["codice_fiscale"] == "FOXGUO00B29Z112N"

    def test_nome_quattro_consonanti(self, page):
        # Limite di regola (DM 1974): nome con >=4 consonanti -> 1a, 3a, 4a consonante (Francesco = F,N,C).
        _compare(page, "Esposito", "Francesco", "M", "1975-03-10", "10/03/1975", "Napoli")

    def test_comune_corretto_2_14_ercolano(self, page):
        # Limite di tabella: Ercolano H243 (codice corretto nella 2.14 dall'elenco ISTAT).
        ours, _ = _compare(page, "Russo", "Anna", "F", "1988-09-30", "30/09/1988", "Ercolano")
        assert ours["codice_fiscale"][11:15] == "H243"

    def test_comune_fuori_sottoinsieme_con_codice_dal_sito(self, page):
        # Piano: Monte San Pietro assente dalla tabella -> errore senza codice; con il codice letto
        # dal sito il CF e' RSSMRA80A01 + codice + controllo ricalcolato.
        site, _ = _site_cf(page, "Rossi", "Mario", "M", "01/01/1980", "Monte San Pietro")
        senza = _tool(
            cognome="Rossi", nome="Mario", sesso="M", data_nascita="1980-01-01", comune_nascita="Monte San Pietro"
        )
        if "errore" not in senza:
            # comune presente in tabella: confronto diretto
            assert senza["codice_fiscale"] == site, f"tool={senza['codice_fiscale']} sito={site}"
            return
        cod = site[11:15]
        con = _tool(
            cognome="Rossi",
            nome="Mario",
            sesso="M",
            data_nascita="1980-01-01",
            comune_nascita="Monte San Pietro",
            codice_catastale=cod,
        )
        assert con["codice_fiscale"] == site, f"tool={con['codice_fiscale']} sito={site}"

    def test_omocodia_non_confrontabile(self, page):
        # Il sito non offre un input per l'omocodia e il tool non la genera: nessun confronto possibile.
        pytest.skip("omocodia: ne' il sito ne' il tool espongono un'opzione confrontabile")

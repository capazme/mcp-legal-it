"""ANAC acts (issue #51): search, the page of an act, the latest acts.

The fixtures in tests/fixtures/anac/ are trimmed copies of the REAL markup served by
www.anticorruzione.it on 2026-10-22. Every request here goes through an httpx.MockTransport.
"""

from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from mcp_legal_it import api
from mcp_legal_it.lib.anac.client import (
    TIPOLOGIE,
    AnacPaginaInattesa,
    build_search_params,
    page_size,
    parse_atto,
    parse_search,
    path_atto,
    resolve_tipologia,
    titolo_corrisponde,
)
from mcp_legal_it.tools.anac import _cerca_atti_anac_impl, _leggi_atto_anac_impl, _ultimi_atti_anac_impl

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "anac"
SEARCH = (FIXTURES / "search_delibere.html").read_text(encoding="utf-8")
EMPTY = (FIXTURES / "search_empty.html").read_text(encoding="utf-8")
DELIBERA = (FIXTURES / "delibera_444_2025.html").read_text(encoding="utf-8")
SEARCH_444 = (FIXTURES / "search_delibera_444_2025.html").read_text(encoding="utf-8")
URL_444 = "https://www.anticorruzione.it/-/delibera-n.-444-del-11-novembre-2025"


def _portal(search: str = SEARCH, act: str = DELIBERA, status: int = 200):
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        if status != 200:
            return httpx.Response(status, text="errore")
        if request.url.path == "/consulta-i-documenti":
            return httpx.Response(200, text=search)
        return httpx.Response(200, text=act)

    def factory(fonte, **kwargs):
        assert fonte == "anac"
        return httpx.AsyncClient(transport=httpx.MockTransport(handler), **kwargs)

    return factory, sent


@pytest.fixture(autouse=True)
def _no_backoff(monkeypatch):
    async def no_sleep(_seconds):
        return None

    monkeypatch.setattr("mcp_legal_it.lib._http.asyncio.sleep", no_sleep)


class TestTipologie:
    @pytest.mark.parametrize("value,key", [
        ("delibere", "delibere"), ("Delibera", "delibere"), ("Pareri di precontenzioso", "pareri_precontenzioso"),
        ("precontenzioso", "pareri_precontenzioso"), ("pareri_normativa", "pareri_normativa"),
        ("parere sulla normativa", "pareri_normativa"), ("linee guida", "linee_guida"),
        ("Provvedimenti d’ordine", "provvedimenti_ordine"), ("", ""),
    ])
    def test_resolve(self, value, key):
        assert resolve_tipologia(value) == key

    def test_unknown_type_is_an_error(self):
        with pytest.raises(ValueError, match="tipologia ANAC non riconosciuta"):
            resolve_tipologia("sentenze")

    def test_every_type_has_a_numeric_portal_id(self):
        assert all(type_id.isdigit() for type_id, _label, _singular in TIPOLOGIE.values())


class TestSearchParams:
    def test_newest_first_with_type_page_size_and_page(self):
        p = build_search_params("rinnovo tacito", "delibere", rows=7, pagina=2)
        assert p == {"isDocumentSearchPortlet": "true", "q": "rinnovo tacito",
                     "sort": "ddm__Dataclu0__date_Number_sortableDESC", "delta": "10",
                     "type": "119160", "start": "2"}

    def test_number_within_type_and_year(self):
        p = build_search_params("444", "delibere", rows=50, anno="2025", tutte_le_parole=True)
        assert (p["q"], p["type"], p["year"], p["searchType"]) == ("444", "119160", "276731294", "and")

    def test_a_year_outside_the_filter_is_an_error(self):
        with pytest.raises(ValueError, match="anno ANAC non disponibile"):
            build_search_params("x", anno="1890")

    def test_first_page_and_no_type(self):
        p = build_search_params("x", rows=50)
        assert "type" not in p and "start" not in p and p["delta"] == "50"


class TestParse:
    def test_search_cards_and_total(self):
        risultati, totale = parse_search(SEARCH)
        assert totale == 6169
        assert [r.titolo for r in risultati] == ["Delibera n. 350 del 9 settembre 2026",
                                                  "Delibera n. 347 del 9 settembre 2026"]
        first = risultati[0]
        assert first.path == "/-/delibera-n.-350-del-9-settembre-2026"
        assert first.data == "09 set 2026"
        assert first.etichette == ["Contratti pubblici", "Vigilanza", "Delibere"]
        assert first.oggetto.startswith("Oggetto:")

    def test_no_result_is_an_empty_list(self):
        assert parse_search(EMPTY) == ([], 0)

    def test_a_page_without_results_block_is_not_no_results(self):
        with pytest.raises(AnacPaginaInattesa):
            parse_search("<html><body><h1>Manutenzione</h1></body></html>")

    def test_act_page(self):
        atto = parse_atto(DELIBERA, URL_444)
        assert atto.titolo == "Delibera n. 444 del 11 novembre 2025"
        assert atto.data == "11 nov 2025"
        assert atto.estremi == {"Anno": "2025", "Argomento": "Contratti pubblici", "Categorie": "Vigilanza",
                                "Tipologie": "Delibere", "Destinatari": "Amministrazioni Pubbliche"}
        assert atto.oggetto.startswith("Contratto per il servizio di elisoccorso")
        assert atto.riferimenti_normativi.startswith("art. 23 della Legge n. 62/2005")
        assert "Proroga tecnica" in atto.parole_chiave
        assert [a.nome for a in atto.allegati] == ["Delibera n. 444 del 11 novembre 2025.pdf"]
        assert atto.allegati[0].url.startswith("https://www.anticorruzione.it/documents/")
        assert atto.testo == ""

    def test_a_page_that_is_not_an_act(self):
        with pytest.raises(AnacPaginaInattesa):
            parse_atto(EMPTY, URL_444)


class TestReferences:
    @pytest.mark.parametrize("rif", [URL_444, "/-/delibera-n.-444-del-11-novembre-2025"])
    def test_path_from_search(self, rif):
        assert path_atto(rif) == "/-/delibera-n.-444-del-11-novembre-2025"

    @pytest.mark.parametrize("rif", ["https://evil.example/-/delibera", "/web/guest/home", "delibera 444",
                                     "/-/../../etc", "http://www.anticorruzione.it.evil.example/-/x",
                                     "/-/..", "/-/%2e%2e%2fadmin", "/-/a%2Fb", "/-/a%5cb", "/-/.hidden"])
    def test_anything_else_is_refused(self, rif):
        with pytest.raises(ValueError):
            path_atto(rif)

    @pytest.mark.parametrize("titolo,ok", [
        ("Delibera n. 444 del 11 novembre 2025", True),
        ("Delibera n. 4444 del 11 novembre 2025", False),
        ("Delibera n. 444 del 11 novembre 2024", False),
        ("Parere di precontenzioso n. 444 del 2 maggio 2025", True),
        # the act's own number is the first one, and the year must follow it
        ("Delibera n. 500 del 3 marzo 2025 - annullamento delibera n. 444 del 2025", False),
        ("Delibera 2025 - n. 444 del 3 marzo 2024", False),
        # the year is the one of the date right after the number (#82 review)
        ("Delibera n. 444 del 11 novembre 2025 - annullamento della delibera n. 12 del 2024", True),
        ("Delibera n. 444 del 11 novembre 2024 - annullamento della delibera n. 12 del 2025", False),
        ("Delibera n. 444 del 07/02/2025", True),
        ("Linee guida n. 444/2025", True),
    ])
    def test_title_matches_number_and_year(self, titolo, ok):
        assert titolo_corrisponde(titolo, "444", "2025") is ok


class TestTools:
    async def test_search(self):
        factory, sent = _portal()
        with api.configurazione(client_factory=factory):
            result = await _cerca_atti_anac_impl("vigilanza", "delibere", max_risultati=2)
        query = parse_qs(urlparse(str(sent[0].url)).query)
        assert query["type"] == ["119160"] and query["q"] == ["vigilanza"]
        text = result.to_str()
        assert result.success and "mostrati 2 su 6169" in text
        assert "`/-/delibera-n.-350-del-9-settembre-2026`" in text

    async def test_search_without_results(self):
        factory, _sent = _portal(search=EMPTY)
        with api.configurazione(client_factory=factory):
            result = await _cerca_atti_anac_impl("zzqxjvw")
        assert result.error_type == "no_results"

    async def test_unknown_type_sends_nothing(self):
        factory, sent = _portal()
        with api.configurazione(client_factory=factory):
            result = await _cerca_atti_anac_impl("x", "sentenze")
        assert sent == [] and result.error_type == "bad_input"

    async def test_unreadable_page_is_an_error_not_zero_results(self):
        factory, _sent = _portal(search="<html><body>Request Rejected</body></html>")
        with api.configurazione(client_factory=factory):
            result = await _cerca_atti_anac_impl("x")
        assert result.error_type == "source_error"
        assert "non equivale a zero risultati" in result.to_str()

    async def test_source_down(self):
        factory, sent = _portal(status=503)
        with api.configurazione(client_factory=factory):
            result = await _cerca_atti_anac_impl("x")
        assert result.error_type == "source_down" and len(sent) == 3

    async def test_read_by_reference(self):
        factory, sent = _portal()
        with api.configurazione(client_factory=factory):
            result = await _leggi_atto_anac_impl("/-/delibera-n.-444-del-11-novembre-2025")
        assert [str(r.url) for r in sent] == [URL_444]
        text = result.to_str()
        assert text.startswith("# Delibera n. 444 del 11 novembre 2025")
        assert "## Riferimenti normativi" in text and "Delibera n. 444 del 11 novembre 2025.pdf" in text
        assert "nel PDF ufficiale" in text and f"Fonte: {URL_444}" in text

    async def test_read_by_number_and_year(self):
        # The real answer of the portal to that search: one result (read 2026-10-22).
        factory, sent = _portal(search=SEARCH_444)
        with api.configurazione(client_factory=factory):
            result = await _leggi_atto_anac_impl(tipologia="delibera", numero="444", anno="2025")
        assert result.success
        assert str(sent[1].url) == URL_444
        query = parse_qs(urlparse(str(sent[0].url)).query)
        # the number within type and year: OR-ed over every delibera, newest first, the act is
        # buried among 6169 (#82 review)
        assert (query["q"], query["type"], query["year"], query["searchType"]) == (
            ["444"], ["119160"], ["276731294"], ["and"])

    async def test_number_not_found(self):
        factory, sent = _portal()
        with api.configurazione(client_factory=factory):
            result = await _leggi_atto_anac_impl(tipologia="delibere", numero="999", anno="2025")
        assert len(sent) == 1 and result.error_type == "no_results"
        assert "nessun atto ANAC «Delibere» n. 999 del 2025 tra gli atti del 2025" in result.to_str()

    async def test_number_without_type_or_reference(self):
        factory, sent = _portal()
        with api.configurazione(client_factory=factory):
            senza_tipo = await _leggi_atto_anac_impl(numero="444", anno="2025")
            niente = await _leggi_atto_anac_impl()
        assert sent == []
        assert senza_tipo.error_type == "bad_input" and niente.error_type == "bad_input"

    async def test_latest(self):
        factory, sent = _portal()
        with api.configurazione(client_factory=factory):
            result = await _ultimi_atti_anac_impl("pareri_precontenzioso", 5)
        query = parse_qs(urlparse(str(sent[0].url)).query)
        assert query["type"] == ["119168"] and query.get("q", [""]) == [""]
        assert result.success and "Ultimi atti ANAC" in result.to_str()


class TestReviewCases:
    """Cases from the independent review of the first version."""

    def test_page_size_rounds_up_to_what_the_portal_offers(self):
        assert [page_size(n) for n in (1, 5, 7, 15, 50, 99)] == [5, 5, 10, 20, 50, 75]

    def test_total_with_a_thousands_separator(self):
        _r, totale = parse_search(SEARCH.replace(">6169<", ">6.169<"))
        assert totale == 6169

    def test_an_absolute_link_to_the_same_site_becomes_a_path(self):
        page = SEARCH.replace('href="/-/delibera-n.-350', 'href="http://www.anticorruzione.it/-/delibera-n.-350')
        risultati, _t = parse_search(page)
        assert risultati[0].path == "/-/delibera-n.-350-del-9-settembre-2026"

    def test_a_heading_in_a_paragraph_of_its_own_keeps_its_body(self):
        page = DELIBERA.replace("<p><strong>Parole chiave</strong><br />",
                                "<p><strong>Parole chiave</strong></p><p>")
        assert "Proroga tecnica" in parse_atto(page, URL_444).parole_chiave

    def test_a_subject_with_bold_words_is_kept(self):
        page = DELIBERA.replace("Contratto per il servizio di elisoccorso",
                                "<strong>Contratto</strong> per il servizio di elisoccorso")
        assert parse_atto(page, URL_444).oggetto.startswith("Contratto per il servizio di elisoccorso")

    def test_a_card_without_title_is_unreadable(self):
        page = DELIBERA.replace("<h2>Delibera n. 444 del 11 novembre 2025</h2>", "")
        with pytest.raises(AnacPaginaInattesa):
            parse_atto(page, URL_444)

    @pytest.mark.parametrize("tipologia", ["relazioni_annuali", "audizioni", "comunicati_presidente",
                                           "linee_guida", "bandi_tipo"])
    async def test_types_without_a_number_cannot_be_looked_up_by_number(self, tipologia):
        factory, sent = _portal()
        with api.configurazione(client_factory=factory):
            result = await _leggi_atto_anac_impl(tipologia=tipologia, numero="1", anno="2025")
        assert sent == [] and result.error_type == "bad_input" and "cerca_atti_anac" in result.to_str()

    async def test_a_missing_page_is_not_the_source_down(self):
        factory, sent = _portal(status=404)
        with api.configurazione(client_factory=factory):
            result = await _leggi_atto_anac_impl("/-/delibera-n.-1-del-1-gennaio-1900")
        assert len(sent) == 1  # a 404 is not retried
        assert result.error_type == "no_results" and "non raggiungibile" not in result.to_str()

    async def test_page_two_follows_the_page_actually_read(self):
        factory, sent = _portal()
        with api.configurazione(client_factory=factory):
            await _cerca_atti_anac_impl("x", max_risultati=15, pagina=2)
        query = parse_qs(urlparse(str(sent[0].url)).query)
        assert query["delta"] == ["20"] and query["start"] == ["2"]

    async def test_not_found_says_how_far_it_looked(self):
        factory, _sent = _portal()
        with api.configurazione(client_factory=factory):
            result = await _leggi_atto_anac_impl(tipologia="delibere", numero="999", anno="2025")
        assert "tra gli atti del 2025 che contengono «999»" in result.to_str()


async def test_search_by_year():
    factory, sent = _portal(search=SEARCH_444)
    with api.configurazione(client_factory=factory):
        result = await _cerca_atti_anac_impl("444", "delibere", anno="2025")
    assert parse_qs(urlparse(str(sent[0].url)).query)["year"] == ["276731294"]
    assert result.success and "Delibera n. 444 del 11 novembre 2025" in result.to_str()


def test_the_real_search_for_444_2025_has_one_result():
    risultati, totale = parse_search(SEARCH_444)
    assert totale == 1 and [r.titolo for r in risultati] == ["Delibera n. 444 del 11 novembre 2025"]


async def test_a_year_outside_the_filter_falls_back_to_the_newest_and_says_so():
    # The portal's "Anno" filter starts at 1999: an older year cannot be filtered. The number and
    # the year are searched as words, newest first, and "not found" says how far it looked.
    factory, sent = _portal(search=EMPTY)
    with api.configurazione(client_factory=factory):
        result = await _leggi_atto_anac_impl(tipologia="delibere", numero="12", anno="1990")
    query = parse_qs(urlparse(str(sent[0].url)).query)
    assert "year" not in query and query["q"] == ["12 1990"] and query["searchType"] == ["and"]
    assert result.error_type == "no_results"
    text = result.to_str()
    assert "non è tra quelli del filtro del portale" in text and "cerca_atti_anac" in text

"""Unit tests for the CeRDEF client and tools (giurisprudenza tributaria, def.finanze.it).

No network: the portal is replaced by an httpx MockTransport answering with the
pages in tests/fixtures/cerdef/, except the @pytest.mark.live tests at the
bottom (skipped by default; run them with -m live).

The fixtures are trimmed copies of the REAL pages the portal served on
2026-09-28: the page chrome is cut, result lists are cut to a few items (the
counters -- contatoreGiurisprudenza, totaleProvvedimenti, ultimaPagina,
ulterioriRisultati -- still describe the full list the portal sent) and the
form's JSP indentation is collapsed, but every tag, attribute, JS escape and
text that remains is verbatim. Do not replace them with hand-written XML: the
previous fixtures were invented, kept passing after the portal changed its
search form, and let every CeRDEF search answer "nessun risultato" -- including
`ultime_sentenze_tributarie` in the weekly digest (issue #46).
"""

import re
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs

import httpx
import pytest
from bs4 import BeautifulSoup

from src.lib import _clock
from src.lib._result import SearchResult
from src.lib.cerdef.client import (
    CRITERI_RICERCA,
    ENTI,
    ORDINAMENTI,
    TIPO_ESTREMI,
    _FILTRI_ENTE,
    _FORM_URL,
    _HEADERS,
    CerdefError,
    CerdefSession,
    ProvvedimentoDetail,
    ProvvedimentoResult,
    _build_form,
    _extract_xml_from_js,
    _is_primo_grado,
    _parse_estremi,
    _parse_search_page,
    _portal_error,
    _strip_cdata_html,
    _unescape_js_string,
    fetch_provvedimento,
    format_detail,
    format_result,
    search_giurisprudenza,
)
from src.tools.cerdef import (
    _cerca_giurisprudenza_tributaria_impl,
    _cerdef_leggi_provvedimento_impl,
    _ultime_sentenze_tributarie_impl,
)


_FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "cerdef"

# Cass. ord. 14/09/2026 n. 25285 — first item of the Cassazione result page and
# the document of the detail fixture.
GUID_25285 = "{5015CDA0-0C00-CB4D-B9B4-CB4BA9689597}"
GUID_24972 = "{708FA9A0-0000-C21A-B71D-0D6E05342D7A}"
GUID_23488 = "{6021C79F-0000-C616-A682-D76B9E5C1CD6}"

# The portal's answer to an unknown detail id, verbatim (HTTP 500, 74 bytes).
_ERRORE_500 = "Error 500: javax.servlet.ServletException: java.lang.NullPointerException\n"


def _pagina(nome: str) -> str:
    return (_FIXTURES / nome).read_text(encoding="utf-8")


def _modulo_reale():
    return BeautifulSoup(_pagina("form_ricerca_avanzata.html"), "lxml").find("form", id="formRicAvanzG")


def _opzioni(nome: str) -> list[str]:
    return [o.get("value") for o in _modulo_reale().find("select", {"name": nome}).find_all("option")]


class _Portale:
    """A stand-in for def.finanze.it: answers requests in order and keeps them for inspection.

    Each answer is a page (HTTP 200), a ``(status, body)`` pair, or an exception
    instance to raise as a transport failure. An unexpected extra request fails
    the test (IndexError on the empty queue).
    """

    def __init__(self, *risposte):
        self.risposte = list(risposte)
        self.richieste: list[httpx.Request] = []

    def _rispondi(self, request: httpx.Request) -> httpx.Response:
        self.richieste.append(request)
        risposta = self.risposte.pop(0)
        if isinstance(risposta, Exception):
            raise risposta
        status, body = (200, risposta) if isinstance(risposta, str) else risposta
        return httpx.Response(status, text=body)

    def modulo(self, i: int = 0) -> dict[str, str]:
        """The form fields of the i-th request, as the portal receives them."""
        campi = parse_qs(self.richieste[i].content.decode(), keep_blank_values=True)
        return {k: v[0] for k, v in campi.items()}

    def attiva(self):
        """Route every httpx.AsyncClient the CeRDEF client opens to this portal."""
        reale = httpx.AsyncClient

        def _client(*args, **kwargs):
            kwargs["transport"] = httpx.MockTransport(self._rispondi)
            return reale(*args, **kwargs)

        return patch("src.lib.cerdef.client.httpx.AsyncClient", side_effect=_client)


def _senza_attese():
    """retry_request backs off between attempts: not in a unit test."""
    return patch("src.lib._http.asyncio.sleep", new_callable=AsyncMock)


def _risposta_secondo_grado(n: int, con_primo_grado: bool = False) -> str:
    """An answer listing n distinct second-instance items and announcing more.

    Built from the real markup of one item of risultati_cgt_primo_secondo.html
    (CGT II Piemonte) with the GUID varied, optionally preceded by the real
    first-instance item of CGT Modena: only the paginator's control flow is under
    test, so the counters are left as the portal sent them.
    """
    reale = _pagina("risultati_cgt_primo_secondo.html")
    item = re.search(r'<Provvedimento idProvvedimento=\\"\{CF773956.*?<\\/Provvedimento>', reale).group(0)
    items = "".join(
        item.replace("CF773956-BBA1-4D08-99A2-41FF861D997D", f"00000000-0000-0000-0000-{i:012d}")
        for i in range(n)
    )
    if con_primo_grado:
        modena = re.search(
            r'<Provvedimento idProvvedimento=[^>]*><estremi[^>]*>[^<]*primo grado di Modena.*?<\\/Provvedimento>', reale
        ).group(0)
        items = modena + items
    testa = reale[:reale.index("<Provvedimento ")].replace("<ulterioriRisultati>false", "<ulterioriRisultati>true")
    return testa + items + reale[reale.index("<\\/risultati>"):]


def _solo_secondo_grado() -> str:
    """The real CGT answer without its first-instance items (the portal's list is complete)."""
    return re.sub(
        r'<Provvedimento idProvvedimento=[^>]*><estremi[^>]*>[^<]*primo grado.*?<\\/Provvedimento>',
        "",
        _pagina("risultati_cgt_primo_secondo.html"),
    )


@pytest.fixture
def oggi(monkeypatch):
    monkeypatch.setenv("LEGAL_TODAY", "2026-09-28")


# ---------------------------------------------------------------------------
# JS string literals
# ---------------------------------------------------------------------------


class TestUnescapeJsString:
    def test_unescape_slash(self):
        assert _unescape_js_string("a\\/b") == "a/b"

    def test_unescape_unicode_hex(self):
        assert _unescape_js_string("Soggettivit\\u00e0") == "Soggettività"

    def test_unescape_unicode_uppercase_hex(self):
        # the detail page writes zero-width spaces as \u200B
        assert _unescape_js_string("\\u200B\\u200BIn tema") == "\u200b\u200bIn tema"

    def test_mixed_case_hex(self):
        assert _unescape_js_string("\\u00E0") == "à"
        assert _unescape_js_string("\\u00C0") == "À"

    def test_multiple_consecutive_unicode(self):
        assert _unescape_js_string("\\u0041\\u0042\\u0043") == "ABC"

    def test_combined_slash_and_unicode(self):
        assert _unescape_js_string("path\\/to\\u002Ffile") == "path/to/file"

    def test_unescape_multiple(self):
        assert _unescape_js_string("p\\/a\\u006e\\u006f") == "p/ano"

    def test_escaped_accented_letter_stands_for_itself(self):
        # the portal writes accented letters as \à, \è, \ò: JS reads each as the letter itself
        assert _unescape_js_string("societ\\à \\è pu\\ò cos\\ì") == "società è può così"

    def test_escaped_quotes_and_hyphen(self):
        assert _unescape_js_string("dell\\'art. 57 \\- \\\"IVA\\\"") == "dell'art. 57 - \"IVA\""

    def test_control_escapes(self):
        assert _unescape_js_string("a\\nb\\tc") == "a\nb\tc"

    def test_single_pass_escaped_backslash(self):
        # an escaped backslash never starts a second escape
        assert _unescape_js_string("\\\\u0041") == "\\u0041"

    def test_no_escapes(self):
        assert _unescape_js_string("hello world") == "hello world"

    def test_empty_string(self):
        assert _unescape_js_string("") == ""


class TestExtractXmlFromJs:
    def test_real_results_page(self):
        xml = _extract_xml_from_js(_pagina("risultati_cassazione.html"), "xmlResult")
        assert xml.startswith('<?xml version="1.0" encoding="UTF-8"?><risultatiRicerca>')
        assert f'idProvvedimento="{GUID_25285}"' in xml
        assert "soggettività passiva" in xml
        assert "dell'abitazione principale" in xml

    def test_real_detail_page(self):
        xml = _extract_xml_from_js(_pagina("dettaglio_ordinanza_25285_2026.html"), "xmlDettaglio")
        assert xml.startswith("<risultatiRicerca><risultati><Provvedimento")
        assert xml.endswith("</risultatiRicerca>")

    def test_returns_empty_when_var_missing(self):
        assert _extract_xml_from_js(_pagina("errore_ambito_non_valido.html"), "xmlResult") == ""

    def test_escaped_quote_before_semicolon_does_not_end_the_string(self):
        html = "<script>var xmlResult = '<a>dell\\';art</a>';</script>"
        assert _extract_xml_from_js(html, "xmlResult") == "<a>dell';art</a>"

    def test_multiline_xml_content(self):
        html = "<script>\nvar xmlResult = '<root><a>line1</a>\n<b>line2</b></root>';\n</script>"
        xml = _extract_xml_from_js(html, "xmlResult")
        assert "line1" in xml and "line2" in xml

    def test_extra_whitespace_around_assignment(self):
        html = "<script>\nvar   xmlResult   =   '<root>ok</root>'  ;\n</script>"
        assert _extract_xml_from_js(html, "xmlResult") == "<root>ok</root>"

    def test_does_not_match_wrong_var_name(self):
        html = "<script>var otherVar = '<data>test</data>';</script>"
        assert _extract_xml_from_js(html, "xmlResult") == ""


class TestPortalError:
    def test_rejected_search_with_the_old_field_names(self):
        # what the portal answered to every search of the old client (issue #46)
        assert _portal_error(_pagina("errore_ambito_non_valido.html")) == "Errore: Ambito di ricerca non valido"

    def test_search_without_criteria(self):
        assert _portal_error(_pagina("errore_almeno_un_campo.html")) == "Errore: Occorre compilare almeno un campo"

    def test_generic_error_page(self):
        assert _portal_error(_pagina("errore_generico.html")) == "Si è verificato un errore:"

    def test_results_page_has_no_error(self):
        assert _portal_error(_pagina("risultati_cassazione.html")) == ""


# ---------------------------------------------------------------------------
# Result list
# ---------------------------------------------------------------------------


class TestParseSearchPage:
    def test_real_results(self):
        pagina = _parse_search_page(_pagina("risultati_cassazione.html"))
        assert [d.guid for d in pagina.risultati] == [GUID_25285, GUID_24972, GUID_23488]
        primo = pagina.risultati[0]
        assert primo.estremi == "Ordinanza del 14/09/2026 n. 25285 - Corte di Cassazione - Sezione/Collegio 5"
        assert primo.titoli == "IVA - Rimborsi - Prova pagamento"
        assert primo.ente == "Corte di Cassazione"
        assert primo.data == "14/09/2026"
        assert pagina.altri is True
        assert pagina.totale == 37767

    def test_item_without_guid_is_skipped(self):
        html = _pagina("risultati_cassazione.html").replace(f'idProvvedimento=\\"{GUID_25285}\\"', "")
        pagina = _parse_search_page(html)
        assert [d.guid for d in pagina.risultati] == [GUID_24972, GUID_23488]

    def test_titles_are_decoded(self):
        titoli = [d.titoli for d in _parse_search_page(_pagina("risultati_cassazione.html")).risultati]
        assert titoli[1].startswith("Residenza in Italia e soggettività passiva IRPEF")
        assert titoli[2] == "ICI - Esenzione dell'abitazione principale"

    def test_genuine_zero_results(self):
        pagina = _parse_search_page(_pagina("risultati_zero.html"))
        assert pagina.risultati == []
        assert pagina.altri is False
        assert pagina.totale == 0

    def test_rejected_search_raises_issue_46(self):
        with pytest.raises(CerdefError, match="Ambito di ricerca non valido"):
            _parse_search_page(_pagina("errore_ambito_non_valido.html"))

    def test_search_without_criteria_raises(self):
        with pytest.raises(CerdefError, match="Occorre compilare almeno un campo"):
            _parse_search_page(_pagina("errore_almeno_un_campo.html"))

    def test_page_without_result_list_raises(self):
        with pytest.raises(CerdefError, match="formato"):
            _parse_search_page("<html><body><p>Servizio in manutenzione</p></body></html>")

    def test_renamed_result_element_raises_instead_of_zero(self):
        # the counter says 37767 but no item is readable: a format change, not "no results"
        html = _pagina("risultati_cassazione.html").replace("Provvedimento", "Documento")
        with pytest.raises(CerdefError, match="37767"):
            _parse_search_page(html)

    def test_unexpected_root_raises(self):
        html = _pagina("risultati_zero.html").replace("risultatiRicerca", "esito")
        with pytest.raises(CerdefError, match="esito"):
            _parse_search_page(html)

    def test_malformed_xml_raises(self):
        html = _pagina("risultati_cassazione.html").replace("<\\/risultatiRicerca>", "")
        with pytest.raises(CerdefError, match="non leggibile"):
            _parse_search_page(html)


class TestParseEstremi:
    @pytest.mark.parametrize("estremi, ente, data", [
        (
            "Ordinanza del 14/09/2026 n. 25285 - Corte di Cassazione - Sezione/Collegio 5",
            "Corte di Cassazione", "14/09/2026",
        ),
        (
            "Sentenza del 09/12/2015 n. 24823 - Corte di Cassazione - Sezione/Collegio Sezioni unite",
            "Corte di Cassazione", "09/12/2015",
        ),
        (
            "Sentenza del 17/12/2025 n. 582 - Corte di giustizia tributaria di primo grado di Modena"
            " - Sezione/Collegio 3",
            "Corte di giustizia tributaria di primo grado di Modena", "17/12/2025",
        ),
        (
            "Sentenza del 10/12/2025 n. 913 - Corte di giustizia tributaria di secondo grado del Piemonte",
            "Corte di giustizia tributaria di secondo grado del Piemonte", "10/12/2025",
        ),
        (
            "Sentenza del 01/02/2024 n. 12 bis - Corte di Cassazione - Sezione/Collegio 5",
            "Corte di Cassazione", "01/02/2024",
        ),
        ("Decreto del 1/2/2024 n. 7 - Corte di Cassazione", "Corte di Cassazione", "01/02/2024"),
        ("Provvedimento senza estremi", "", ""),
    ])
    def test_estremi(self, estremi, ente, data):
        assert _parse_estremi(estremi) == (ente, data)


class TestPrimoGrado:
    """The first-instance filter, checked on every tax court the real form lists."""

    def test_every_tax_court_of_the_form(self):
        tributari = [e for e in _opzioni("ente") if "tributaria" in e or e.startswith("Comm. Trib.")]
        assert len(tributari) == 251
        primo = [e for e in tributari if _is_primo_grado(e)]
        altri = [e for e in tributari if not _is_primo_grado(e)]
        assert len(primo) == 208
        for ente in primo:
            assert re.search(r"primo grado|Comm\. Trib\. Prov\.|Comm\. Trib\.\s+I grado", ente), ente
        for ente in altri:
            assert re.search(r"secondo grado|II grado|Comm\. Trib\. Reg\.|Comm\. Trib\. Centrale", ente), ente

    @pytest.mark.parametrize("ente, atteso", [
        ("Comm. Trib.  I grado di Bolzano", True),
        ("Comm. Trib. primo grado Ivrea", True),
        ("Comm. Trib. Prov. Como", True),
        ("Comm. Trib. II grado di Bolzano", False),
        ("Tribunale I grado Corte Giust. CE", False),
        ("Corte di Cassazione", False),
    ])
    def test_edge_names(self, ente, atteso):
        assert _is_primo_grado(ente) is atteso


# ---------------------------------------------------------------------------
# The search form
# ---------------------------------------------------------------------------


class TestFormContract:
    """What the client sends must be what the real form offers: the root cause of #46."""

    def test_field_names_exist_in_the_form(self):
        modulo = _modulo_reale()
        campi = {el.get("name") for el in modulo.find_all(["input", "select"]) if el.get("name")}
        inviati = set(_build_form(parole="IVA"))
        assert inviati <= campi, inviati - campi
        assert modulo.get("action") == "executeAdvancedGiurisprudenzaSearch.do"

    def test_hidden_fields_match_the_form(self):
        nascosti = {i.get("name"): i.get("value") for i in _modulo_reale().find_all("input", type="hidden")}
        inviati = _build_form(parole="IVA")
        for nome in ("tipoComplessitaRicerca", "ricercaAreaRiservata", "tipoRicerca", "device", "ambitoRicerca"):
            assert inviati[nome] == nascosti[nome], nome
        # the form's onsubmit handler sets js_enabled to 1 before posting
        assert inviati["js_enabled"] == "1"

    def test_court_values_are_options_of_the_form(self):
        # the portal answers a court it does not know with zero results, silently
        for chiave, filtro in _FILTRI_ENTE.items():
            assert filtro.valore in _opzioni(filtro.campo), chiave
        assert set(_FILTRI_ENTE) == set(ENTI)

    def test_other_values_are_options_of_the_form(self):
        assert set(TIPO_ESTREMI.values()) <= set(_opzioni("tipoEstremi"))
        assert set(CRITERI_RICERCA.values()) == set(_opzioni("tipoCriterioRicerca"))
        assert set(ORDINAMENTI.values()) == set(_opzioni("tipo_ord"))


class TestBuildForm:
    def test_all_criteria(self):
        modulo = _build_form(
            parole="IVA rimborso", tipo_criterio="frase_esatta", tipo_estremi="sentenza",
            numero="24823", data_da="01/12/2015", data_a="31/12/2015",
            ente="corte_suprema", ordinamento="data",
        )
        assert modulo["ambitoRicerca"] == "G"
        assert modulo["parole"] == "IVA rimborso"
        assert modulo["tipoCriterioRicerca"] == "2"
        assert modulo["tipoEstremi"] == "Sentenza"
        assert modulo["numero"] == "24823"
        assert (modulo["giornoDataEmissioneDa"], modulo["meseDataEmissioneDa"], modulo["annoDataEmissioneDa"]) == ("1", "12", "2015")
        assert (modulo["giornoDataEmissioneA"], modulo["meseDataEmissioneA"], modulo["annoDataEmissioneA"]) == ("31", "12", "2015")
        assert modulo["ente"] == "Corte di Cassazione"
        assert modulo["superEnte"] == ""
        assert modulo["tipo_ord"] == "DATA"

    def test_default_order_is_relevance(self):
        assert _build_form(parole="IVA")["tipo_ord"] == "RANK"

    def test_empty_criterion_and_order_fall_back_to_defaults(self):
        # as before the fix: an empty value means the default, not an error
        modulo = _build_form(parole="IVA", tipo_criterio="", ordinamento=" ")
        assert modulo["tipoCriterioRicerca"] == "0"
        assert modulo["tipo_ord"] == "RANK"

    def test_cgt_group_uses_super_ente(self):
        modulo = _build_form(ente="cgt_secondo_grado")
        assert modulo["superEnte"] == "Tutte le Corti di giustizia tributaria di secondo grado"
        assert modulo["ente"] == ""

    def test_iso_dates_accepted(self):
        modulo = _build_form(data_da="2025-09-28", data_a="2026-09-28")
        assert (modulo["giornoDataEmissioneDa"], modulo["meseDataEmissioneDa"], modulo["annoDataEmissioneDa"]) == ("28", "9", "2025")
        assert (modulo["giornoDataEmissioneA"], modulo["meseDataEmissioneA"], modulo["annoDataEmissioneA"]) == ("28", "9", "2026")

    @pytest.mark.parametrize("kwargs, messaggio", [
        ({"parole": "IVA", "ente": "cgt_terzo_grado"}, "corte_suprema"),
        ({"parole": "IVA", "tipo_estremi": "parere"}, "sentenza"),
        ({"parole": "IVA", "tipo_criterio": "qualsiasi"}, "tutti"),
        ({"parole": "IVA", "tipo_criterio": "codice"}, "numero"),
        ({"parole": "IVA", "ordinamento": "casuale"}, "rilevanza"),
        ({"parole": "IVA", "data_da": "31/02/2024"}, "data_da"),
        ({"parole": "IVA", "data_a": "2024/12/31"}, "data_a"),
        ({"data_da": "01/01/2025", "data_a": "01/01/2024"}, "successiva"),
        ({"numero": "24823/2015"}, "numero"),
        ({}, "almeno un criterio"),
        ({"ordinamento": "data"}, "almeno un criterio"),
        ({"parole": "IVA", "ente": "cgt_primo_grado"}, "data_da"),
    ])
    def test_invalid_input_is_refused(self, kwargs, messaggio):
        with pytest.raises(ValueError, match=messaggio):
            _build_form(**kwargs)


# ---------------------------------------------------------------------------
# search_giurisprudenza
# ---------------------------------------------------------------------------


class TestSearchGiurisprudenza:
    async def test_one_request_when_the_first_answer_suffices(self):
        portale = _Portale(_pagina("risultati_cassazione.html"))
        with portale.attiva():
            esito = await search_giurisprudenza(parole="IVA", rows=2)
        assert [d.guid for d in esito.risultati] == [GUID_25285, GUID_24972]
        assert esito.totale == 37767
        assert len(portale.richieste) == 1
        richiesta = portale.richieste[0]
        assert richiesta.method == "POST"
        assert richiesta.url.path.endswith("/executeAdvancedGiurisprudenzaSearch.do")
        assert portale.modulo()["parole"] == "IVA"

    async def test_more_results_come_from_the_paginator(self):
        # the paginator answers with the whole list so far plus the next items
        portale = _Portale(_pagina("risultati_cassazione.html"), _pagina("risultati_cassazione_pagina2.html"))
        with portale.attiva():
            esito = await search_giurisprudenza(ente="corte_suprema", data_a="28/09/2026", ordinamento="data", rows=5)
        risultati = esito.risultati
        assert len(risultati) == 5
        assert len({d.guid for d in risultati}) == 5
        assert [d.guid for d in risultati[:3]] == [GUID_25285, GUID_24972, GUID_23488]
        seconda = portale.richieste[1]
        assert seconda.method == "GET"
        assert seconda.url.path.endswith("/paginatorXml.do")

    async def test_stops_when_the_portal_has_nothing_more(self):
        portale = _Portale(_pagina("risultati_cgt_primo_secondo.html"))  # ulterioriRisultati=false
        with portale.attiva():
            esito = await search_giurisprudenza(parole="IVA", rows=10)
        assert len(esito.risultati) == 4
        assert len(portale.richieste) == 1

    async def test_stops_when_a_page_adds_nothing(self):
        portale = _Portale(
            _pagina("risultati_cassazione.html"),
            _pagina("risultati_cassazione_pagina2.html"),
            _pagina("risultati_cassazione_pagina2.html"),
        )
        with portale.attiva():
            esito = await search_giurisprudenza(parole="IVA", rows=250)
        assert len(esito.risultati) == 5
        assert len(portale.richieste) == 3

    async def test_rows_capped_at_250(self):
        portale = _Portale(*[_risposta_secondo_grado(50 * k) for k in range(1, 8)])
        with portale.attiva():
            esito = await search_giurisprudenza(parole="IVA", rows=999)
        assert len(esito.risultati) == 250
        assert len(portale.richieste) == 5

    async def test_first_instance_is_kept_client_side(self):
        portale = _Portale(_pagina("risultati_cgt_primo_secondo.html"))
        with portale.attiva():
            esito = await search_giurisprudenza(ente="cgt_primo_grado", data_da="28/09/2025", rows=10)
        assert [d.ente for d in esito.risultati] == [
            "Corte di giustizia tributaria di primo grado di Modena",
            "Corte di giustizia tributaria di primo grado di Imperia",
        ]
        assert esito.troncato is False
        assert portale.modulo()["superEnte"] == "Tutte le Corti di giustizia tributaria di primo e secondo grado"

    async def test_first_instance_scan_is_bounded(self):
        # every answer announces more items and none is of first instance: stop after
        # reading 250 items instead of paging through the whole archive
        portale = _Portale(*[_risposta_secondo_grado(50 * k) for k in range(1, 8)])
        with portale.attiva():
            esito = await search_giurisprudenza(ente="cgt_primo_grado", data_da="01/01/2024", rows=10)
        assert esito.risultati == []
        assert esito.esaminati == 250
        assert esito.troncato is True
        assert len(portale.richieste) == 5

    async def test_first_instance_complete_scan_is_not_truncated(self):
        portale = _Portale(_solo_secondo_grado())
        with portale.attiva():
            esito = await search_giurisprudenza(ente="cgt_primo_grado", data_da="28/09/2025", rows=10)
        assert esito.risultati == []
        assert esito.troncato is False

    async def test_rejected_search_is_an_error_issue_46(self):
        portale = _Portale(_pagina("errore_ambito_non_valido.html"))
        with portale.attiva(), pytest.raises(CerdefError, match="Ambito di ricerca non valido"):
            await search_giurisprudenza(parole="IVA")

    async def test_invalid_input_makes_no_request(self):
        portale = _Portale()
        with portale.attiva(), pytest.raises(ValueError):
            await search_giurisprudenza(parole="IVA", ente="tribunale")
        assert portale.richieste == []


# ---------------------------------------------------------------------------
# ultime_sentenze_tributarie
# ---------------------------------------------------------------------------


class TestUltimeSentenzeTributarieImpl:
    async def test_latest_of_the_last_twelve_months(self, oggi):
        portale = _Portale(_pagina("risultati_cassazione.html"))
        with portale.attiva():
            result = await _ultime_sentenze_tributarie_impl(max_risultati=3)
        assert result.success
        assert result.num_found == 3
        modulo = portale.modulo()
        assert (modulo["giornoDataEmissioneDa"], modulo["meseDataEmissioneDa"], modulo["annoDataEmissioneDa"]) == ("28", "9", "2025")
        assert (modulo["giornoDataEmissioneA"], modulo["meseDataEmissioneA"], modulo["annoDataEmissioneA"]) == ("28", "9", "2026")
        assert modulo["tipo_ord"] == "DATA"
        assert "dal 28/09/2025 al 28/09/2026" in result.results_text
        assert GUID_25285 in result.results_text

    async def test_rejected_search_is_not_no_news_issue_46(self, oggi):
        portale = _Portale(_pagina("errore_ambito_non_valido.html"))
        with portale.attiva():
            result = await _ultime_sentenze_tributarie_impl()
        assert not result.success
        assert result.error_type == "source_error"
        testo = result.to_str()
        assert testo.startswith("**Errore**")
        assert "Ambito di ricerca non valido" in testo
        assert "Nessuna sentenza" not in testo

    async def test_unrecognised_page_is_not_no_news(self, oggi):
        portale = _Portale("<html><body><p>Servizio in manutenzione</p></body></html>")
        with portale.attiva():
            result = await _ultime_sentenze_tributarie_impl()
        assert result.error_type == "source_error"
        assert result.to_str().startswith("**Errore**")

    async def test_genuine_zero_names_period_and_filters(self, oggi):
        portale = _Portale(_pagina("risultati_zero.html"))
        with portale.attiva():
            result = await _ultime_sentenze_tributarie_impl(ente="corte_suprema", tipo_provvedimento="sentenza")
        assert result.error_type == "no_results"
        testo = result.to_str()
        assert not testo.startswith("**Errore**")
        assert "dal 28/09/2025 al 28/09/2026" in testo
        assert "Corte di Cassazione" in testo
        assert "Sentenza" in testo

    async def test_network_failure_is_source_down(self, oggi):
        portale = _Portale(*[httpx.ConnectError("connection refused")] * 3)
        with portale.attiva(), _senza_attese():
            result = await _ultime_sentenze_tributarie_impl()
        assert result.error_type == "source_down"
        assert "non raggiungibile" in result.to_str()

    async def test_unknown_court_is_refused_without_asking_the_portal(self, oggi):
        portale = _Portale()
        with portale.attiva():
            result = await _ultime_sentenze_tributarie_impl(ente="tribunale")
        assert result.error_type == "bad_input"
        testo = result.to_str()
        assert testo.startswith("**Errore**")
        assert "corte_suprema" in testo
        assert portale.richieste == []

    async def test_first_instance_courts(self, oggi):
        portale = _Portale(_pagina("risultati_cgt_primo_secondo.html"))
        with portale.attiva():
            result = await _ultime_sentenze_tributarie_impl(ente="cgt_primo_grado")
        assert result.num_found == 2
        assert "Modena" in result.results_text
        assert "Imperia" in result.results_text
        assert "Piemonte" not in result.results_text


# ---------------------------------------------------------------------------
# cerca_giurisprudenza_tributaria
# ---------------------------------------------------------------------------


class TestCercaGiurisprudenzaTributariaImpl:
    async def test_returns_results(self):
        portale = _Portale(_pagina("risultati_cassazione.html"))
        with portale.attiva():
            result = await _cerca_giurisprudenza_tributaria_impl("IVA", max_risultati=3)
        assert result.success
        assert "Trovati 3 provvedimenti" in result.results_text
        assert GUID_25285 in result.results_text

    async def test_genuine_zero(self):
        portale = _Portale(_pagina("risultati_zero.html"))
        with portale.attiva():
            result = await _cerca_giurisprudenza_tributaria_impl("zqxjkvwpfh")
        assert result.error_type == "no_results"
        assert result.to_str().startswith("Nessun provvedimento CeRDEF trovato")

    async def test_rejected_search_is_an_error(self):
        portale = _Portale(_pagina("errore_ambito_non_valido.html"))
        with portale.attiva():
            result = await _cerca_giurisprudenza_tributaria_impl("IVA")
        assert result.error_type == "source_error"
        assert result.to_str().startswith("**Errore**")

    async def test_codice_criterion_points_to_numero(self):
        portale = _Portale()
        with portale.attiva():
            result = await _cerca_giurisprudenza_tributaria_impl("24823", criterio="codice")
        assert result.error_type == "bad_input"
        assert "numero" in result.to_str()

    async def test_first_instance_needs_a_start_date(self):
        portale = _Portale()
        with portale.attiva():
            result = await _cerca_giurisprudenza_tributaria_impl("IVA", ente="cgt_primo_grado")
        assert result.error_type == "bad_input"
        assert "data_da" in result.to_str()
        assert portale.richieste == []

    async def test_first_instance_zero_names_the_filter(self):
        # the portal's whole list was read and none is of first instance: a true zero, said as such
        portale = _Portale(_solo_secondo_grado())
        with portale.attiva():
            result = await _cerca_giurisprudenza_tributaria_impl("IVA", ente="cgt_primo_grado", data_da="28/09/2025")
        assert result.error_type == "no_results"
        testo = result.to_str()
        assert testo.startswith("Nessun provvedimento CeRDEF trovato per: _IVA_")
        assert "primo grado" in testo

    async def test_truncated_first_instance_scan_is_not_a_zero(self):
        portale = _Portale(*[_risposta_secondo_grado(50 * k) for k in range(1, 6)])
        with portale.attiva():
            result = await _cerca_giurisprudenza_tributaria_impl("IVA", ente="cgt_primo_grado", data_da="01/01/2024")
        testo = result.to_str()
        assert not testo.startswith("Nessun provvedimento CeRDEF trovato")
        assert "primi 250" in testo
        assert "non è stato esaminato per intero" in testo

    async def test_truncated_first_instance_scan_is_flagged_under_the_results(self):
        portale = _Portale(*[_risposta_secondo_grado(50 * k, con_primo_grado=True) for k in range(1, 6)])
        with portale.attiva():
            result = await _cerca_giurisprudenza_tributaria_impl("IVA", ente="cgt_primo_grado", data_da="01/01/2024")
        assert result.success
        assert result.num_found == 1
        assert "Modena" in result.results_text
        assert "non è stato esaminato per intero" in result.results_text


# ---------------------------------------------------------------------------
# Detail
# ---------------------------------------------------------------------------


class TestFetchProvvedimento:
    async def test_real_detail(self):
        portale = _Portale(_pagina("dettaglio_ordinanza_25285_2026.html"))
        with portale.attiva():
            dettaglio = await fetch_provvedimento(GUID_25285)
        richiesta = portale.richieste[0]
        assert richiesta.method == "GET"
        assert richiesta.url.path.endswith("/getGiurisprudenzaDetail.do")
        assert richiesta.url.params["id"] == GUID_25285
        assert dettaglio.guid == GUID_25285
        assert dettaglio.estremi == "Ordinanza del 14/09/2026 n. 25285 - Corte di Cassazione - Sezione/Collegio 5"
        assert dettaglio.oggetto == "IVA - Rimborsi - Prova pagamento"
        assert "In tema di rimborso IVA" in dettaglio.massima
        assert "l'amministrazione finanziaria" in dettaglio.massima
        assert "stabilito dall'articolo 57, DPR n. 633/1972, il potere di accertamento" in dettaglio.massima
        assert dettaglio.testo_integrale.startswith("FATTI DI CAUSA")
        assert "la società (che negli anni è stata" in dettaglio.testo_integrale
        assert "Depositato in Cancelleria il 14 settembre 2026." in dettaglio.testo_integrale
        assert "\\" not in dettaglio.massima + dettaglio.testo_integrale

    async def test_unknown_guid_http_500(self):
        portale = _Portale(*[(500, _ERRORE_500)] * 3)
        with portale.attiva(), _senza_attese(), pytest.raises(CerdefError, match="inesistente"):
            await fetch_provvedimento("{00000000-0000-4000-8000-000000000000}")

    async def test_error_page_instead_of_detail_raises(self):
        portale = _Portale(_pagina("errore_generico.html"))
        with portale.attiva(), pytest.raises(CerdefError, match="Si è verificato un errore"):
            await fetch_provvedimento(GUID_25285)

    async def test_renamed_text_elements_raise(self):
        # a portal that renames <testo> and <massima> must not yield an empty "success"
        html = (
            _pagina("dettaglio_ordinanza_25285_2026.html")
            .replace("<testo>", "<testoIntegrale>")
            .replace("<\\/testo>", "<\\/testoIntegrale>")
            .replace("massima>", "sommario>")
        )
        portale = _Portale(html)
        with portale.attiva(), pytest.raises(CerdefError, match="né testo né massima"):
            await fetch_provvedimento(GUID_25285)

    async def test_empty_text_elements_are_a_genuine_empty_detail(self):
        html = re.sub(
            r"<(massima|testo)><!\[CDATA\[.*?\]\]><\\/\1>", r"<\1><\\/\1>",
            _pagina("dettaglio_ordinanza_25285_2026.html"), flags=re.S,
        )
        portale = _Portale(html)
        with portale.attiva():
            dettaglio = await fetch_provvedimento(GUID_25285)
        assert dettaglio.massima == ""
        assert dettaglio.testo_integrale == ""
        assert "non riporta" in format_detail(dettaglio)

    async def test_detail_without_provvedimento_raises(self):
        html = _pagina("dettaglio_ordinanza_25285_2026.html").replace("Provvedimento", "Documento")
        portale = _Portale(html)
        with portale.attiva(), pytest.raises(CerdefError, match="inattesa"):
            await fetch_provvedimento(GUID_25285)

    async def test_empty_guid_is_refused(self):
        with pytest.raises(ValueError, match="GUID"):
            await fetch_provvedimento("   ")


class TestCerdefLeggiProvvedimentoImpl:
    async def test_returns_full_text(self):
        portale = _Portale(_pagina("dettaglio_ordinanza_25285_2026.html"))
        with portale.attiva():
            result = await _cerdef_leggi_provvedimento_impl(GUID_25285)
        assert result.success
        testo = result.results_text
        assert testo.startswith("# Ordinanza del 14/09/2026 n. 25285 - Corte di Cassazione")
        assert "**Oggetto**: IVA - Rimborsi - Prova pagamento" in testo
        assert "## Massima" in testo
        assert "## Testo Integrale" in testo

    async def test_unknown_guid_is_not_an_outage(self):
        portale = _Portale(*[(500, _ERRORE_500)] * 3)
        with portale.attiva(), _senza_attese():
            result = await _cerdef_leggi_provvedimento_impl("abc-123-def-456")
        assert result.error_type == "source_error"
        testo = result.to_str()
        assert testo.startswith("**Errore**")
        assert "inesistente" in testo
        assert "non raggiungibile" not in testo

    async def test_http_404_is_source_down(self):
        portale = _Portale((404, "Not Found"))
        with portale.attiva():
            result = await _cerdef_leggi_provvedimento_impl(GUID_25285)
        assert result.error_type == "source_down"

    async def test_empty_guid_is_bad_input(self):
        result = await _cerdef_leggi_provvedimento_impl("")
        assert result.error_type == "bad_input"
        assert result.to_str().startswith("**Errore**")


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


class TestSearchResultRendering:
    """How a CeRDEF failure reads to the caller: never like an empty result."""

    def test_source_error(self):
        testo = SearchResult(success=False, source="cerdef", error_type="source_error",
                             error_message="il portale ha rifiutato la ricerca").to_str()
        assert testo.startswith("**Errore**")
        assert "non equivale a zero risultati" in testo
        assert "il portale ha rifiutato la ricerca" in testo

    def test_source_error_without_text_is_still_an_error(self):
        # the "no results" fallback must not apply to a source that could not be read
        testo = SearchResult(success=False, source="cerdef", error_type="source_error").to_str()
        assert testo.startswith("**Errore**")

    def test_other_error_types_keep_their_own_text(self):
        # gazzetta and parlamento carry their message in results_text: unchanged
        testo = SearchResult(success=False, source="parlamento", error_type="invalid_input",
                             results_text="**Errore**: atto 'pippo' non riconosciuto").to_str()
        assert testo == "**Errore**: atto 'pippo' non riconosciuto"

    def test_source_down_unchanged(self):
        testo = SearchResult(success=False, source="cerdef", error_type="source_down", error_message="timeout").to_str()
        assert testo == "**Errore**: cerdef non raggiungibile. timeout"

    def test_no_results_shows_the_message(self):
        testo = SearchResult(success=False, source="cerdef", error_type="no_results", results_text="Nessun provvedimento.").to_str()
        assert testo == "Nessun provvedimento."


class TestFormatResult:
    def test_contains_estremi_and_guid(self):
        doc = ProvvedimentoResult(guid=GUID_25285, estremi="Ordinanza del 14/09/2026 n. 25285",
                                  titoli="IVA", ente="Corte di Cassazione", data="14/09/2026")
        text = format_result(doc)
        assert text.startswith("### Ordinanza del 14/09/2026 n. 25285")
        assert f"**GUID**: `{GUID_25285}`" in text
        assert "**Ente**: Corte di Cassazione" in text
        assert "**Data**: 14/09/2026" in text

    def test_long_titoli_truncated(self):
        doc = ProvvedimentoResult(guid="x", estremi="X", titoli="T" * 500, ente="E", data="")
        assert len(format_result(doc)) < 700

    def test_fallback_to_guid_when_no_estremi(self):
        doc = ProvvedimentoResult(guid="my-guid", estremi="", titoli="", ente="", data="")
        assert "my-guid" in format_result(doc)

    def test_empty_fields_are_omitted(self):
        text = format_result(ProvvedimentoResult(guid="g", estremi="E", titoli="", ente="", data=""))
        assert "Oggetto" not in text and "Ente" not in text and "Data" not in text


class TestFormatDetail:
    def test_contains_estremi_oggetto_and_massima(self):
        detail = ProvvedimentoDetail(guid="g", estremi="Sent. n. 1/2024", massima="Principio X.",
                                     testo_integrale="", oggetto="IVA - Rimborsi")
        text = format_detail(detail)
        assert text.startswith("# Sent. n. 1/2024")
        assert "**Oggetto**: IVA - Rimborsi" in text
        assert "## Massima\n\nPrincipio X." in text

    def test_truncation_at_25000(self):
        detail = ProvvedimentoDetail(guid="x", estremi="X", massima="", testo_integrale="a" * 30000)
        text = format_detail(detail)
        assert "Testo troncato a 25000 caratteri su 30000 totali" in text

    def test_truncation_boundary(self):
        detail = ProvvedimentoDetail(guid="g", estremi="E", massima="", testo_integrale="a" * 25000)
        assert "troncato" not in format_detail(detail)

    def test_includes_optional_fields(self):
        detail = ProvvedimentoDetail(guid="x", estremi="X", massima="", testo_integrale="",
                                     collegio="Dott. Rossi", udienza="01/01/2024", ricorsi="RG 1/2023")
        text = format_detail(detail)
        assert "Dott. Rossi" in text and "01/01/2024" in text and "RG 1/2023" in text

    def test_says_when_the_portal_has_no_text(self):
        text = format_detail(ProvvedimentoDetail(guid="g", estremi="E", massima="", testo_integrale=""))
        assert "## Massima" not in text and "## Testo Integrale" not in text
        assert "non riporta" in text


class TestStripCdataHtml:
    def test_empty_string(self):
        assert _strip_cdata_html("") == ""

    def test_strips_html_tags(self):
        result = _strip_cdata_html("<p>paragrafo <b>grassetto</b></p>")
        assert "<" not in result
        assert "paragrafo" in result and "grassetto" in result

    def test_preserves_text_entities(self):
        assert "IVA & IRES" in _strip_cdata_html("<p>IVA &amp; IRES</p>")

    def test_inline_tags_do_not_break_the_sentence(self):
        # the portal links every cited norm (<a>) and styles runs of text (<span>):
        # only block elements may start a new line
        html = '<p>stabilito dall\'<a href="decodeurn?urn=x">articolo 57</a>, il potere</p><p>Secondo <span>paragrafo</span>.</p>'
        assert _strip_cdata_html(html) == "stabilito dall'articolo 57, il potere\nSecondo paragrafo."


class TestCerdefSession:
    def test_client_raises_when_not_entered(self):
        with pytest.raises(RuntimeError, match="not entered"):
            _ = CerdefSession().client

    async def test_aexit_closes_and_forgets_the_client(self):
        with patch("src.lib.cerdef.client.httpx.AsyncClient") as MockClient:
            instance = AsyncMock()
            MockClient.return_value = instance
            session = CerdefSession()
            async with session:
                assert session.client is instance
            instance.aclose.assert_awaited_once()
            assert session._client is None


# ---------------------------------------------------------------------------
# Live: the real portal (network; run with -m live)
# ---------------------------------------------------------------------------

# Cass., Sez. Un., 9 dicembre 2015 n. 24823 (contraddittorio endoprocedimentale).
GUID_SSUU_24823_2015 = "{B0F76E21-B5FA-4415-9D1D-44FF7B5741C1}"
_DATA_BLOCCO = re.compile(r"\*\*Data\*\*: (\d{2}/\d{2}/\d{4})")


def _blocchi(testo: str) -> list[str]:
    """Split a result list into its '### ' blocks, one per provvedimento."""
    return [b for b in re.split(r"^### ", testo, flags=re.M)[1:] if b.strip()]


@pytest.mark.live
async def test_live_form_still_offers_what_the_client_sends():
    """Canary: if this fails the portal changed its form, and every other result is suspect."""
    async with httpx.AsyncClient(headers=_HEADERS, timeout=45, follow_redirects=True) as client:
        resp = await client.get(_FORM_URL)
    modulo = BeautifulSoup(resp.text, "lxml").find("form", id="formRicAvanzG")
    assert modulo is not None, "modulo di ricerca avanzata non trovato: pagina cambiata"
    campi = {el.get("name") for el in modulo.find_all(["input", "select"]) if el.get("name")}
    assert set(_build_form(parole="IVA")) <= campi

    def opzioni(nome):
        return {o.get("value") for o in modulo.find("select", {"name": nome}).find_all("option")}

    for chiave, filtro in _FILTRI_ENTE.items():
        assert filtro.valore in opzioni(filtro.campo), chiave
    assert set(TIPO_ESTREMI.values()) <= opzioni("tipoEstremi")
    assert set(CRITERI_RICERCA.values()) <= opzioni("tipoCriterioRicerca")
    assert set(ORDINAMENTI.values()) <= opzioni("tipo_ord")


@pytest.mark.live
async def test_live_ultime_senza_filtri():
    result = await _ultime_sentenze_tributarie_impl(max_risultati=5)
    testo = result.to_str()
    assert result.success, testo[:800]
    blocchi = _blocchi(testo)
    assert 1 <= len(blocchi) <= 5, testo[:800]
    date = []
    for blocco in blocchi:
        trovata = _DATA_BLOCCO.search(blocco)
        assert trovata, f"blocco senza data: {blocco[:300]}"
        date.append(datetime.strptime(trovata.group(1), "%d/%m/%Y").date())
    assert date == sorted(date, reverse=True), date
    oggi = _clock.today()
    assert all(oggi - timedelta(days=365) <= d <= oggi for d in date), date


@pytest.mark.live
async def test_live_ultime_cassazione():
    result = await _ultime_sentenze_tributarie_impl(ente="corte_suprema", max_risultati=5)
    assert result.success, result.to_str()[:800]
    assert all("**Ente**: Corte di Cassazione" in b for b in _blocchi(result.results_text))


@pytest.mark.live
@pytest.mark.parametrize("ente, grado", [("cgt_primo_grado", "primo grado"), ("cgt_secondo_grado", "secondo grado")])
async def test_live_ultime_cgt(ente, grado):
    result = await _ultime_sentenze_tributarie_impl(ente=ente, max_risultati=5)
    # the CGT are published with months of delay: an empty year is possible, an error is not
    assert result.success or result.error_type == "no_results", result.to_str()[:800]
    for blocco in _blocchi(result.results_text):
        assert grado in blocco, blocco[:300]


@pytest.mark.live
async def test_live_cerca_ssuu_24823_2015():
    result = await _cerca_giurisprudenza_tributaria_impl(
        "contraddittorio endoprocedimentale", ente="corte_suprema", tipo_provvedimento="sentenza",
        data_da="01/12/2015", data_a="31/12/2015",
    )
    assert result.success, result.to_str()[:800]
    assert GUID_SSUU_24823_2015 in result.results_text
    assert "n. 24823" in result.results_text


@pytest.mark.live
async def test_live_leggi_ssuu_24823_2015():
    result = await _cerdef_leggi_provvedimento_impl(GUID_SSUU_24823_2015)
    testo = result.to_str()
    assert result.success, testo[:800]
    assert "Sezioni unite" in testo
    assert "contraddittorio endoprocedimentale" in testo.lower()
    assert "Testo troncato a 25000 caratteri" in testo
    assert not re.search(r"\\[àèéìòù'/-]", testo), "escape JS non risolti nel testo"


@pytest.mark.live
async def test_live_guid_inesistente():
    result = await _cerdef_leggi_provvedimento_impl("{00000000-0000-4000-8000-000000000000}")
    assert result.error_type == "source_error", result.to_str()[:400]
    assert "inesistente" in result.to_str()

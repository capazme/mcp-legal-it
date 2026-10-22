"""Issue #52: queries the Giustizia Amministrativa portal refuses, and its 4xx answers.

Read live on 2026-10-22 (two serial searches): '"accordi tra pubbliche amministrazioni"
"rinnovo tacito"' -> 403 from the firewall in front of the portal (Azure Application Gateway),
'"rinnovo tacito" accordi tra pubbliche amministrazioni' -> 200, 50 results. Every request
here goes through an httpx.MockTransport: no socket is opened.
"""

import httpx
import pytest

from mcp_legal_it import api
from mcp_legal_it.lib.giustizia_amm.client import (
    PortaleRifiuta,
    QueryNonSupportata,
    check_query,
    search_provvedimenti_page,
)
from mcp_legal_it.tools.giurisprudenza_unificata import _cerca_amministrativa
from mcp_legal_it.tools.giustizia_amm import (
    _cerca_giurisprudenza_amministrativa_impl,
    _giurisprudenza_amm_su_norma_impl,
    _leggi_provvedimento_amm_impl,
)

from tests.unit.test_giustizia_amm import _SEARCH_HTML, _SEARCH_PAGE_HTML

DUE_FRASI = '"accordi tra pubbliche amministrazioni" "rinnovo tacito"'
UNA_FRASE = '"rinnovo tacito" accordi tra pubbliche amministrazioni'

# What the firewall serves (copied from the live answer, padding trimmed).
_AZURE_403 = (
    "<html>\n<head><title>403 Forbidden</title></head>\n<body>\n<center><h1>403 Forbidden</h1>"
    "</center>\n<hr><center>Microsoft-Azure-Application-Gateway/v2</center>\n</body>\n</html>\n"
)

# Nothing of the request URL may reach the user: it holds the portlet id and the CSRF token.
_URL_PIECES = ("p_auth", "6O8im78W", "p_p_id", "dcsnprr", "javax.portlet", "INSTANCE_")


def _portal(post_status: int = 200, get_doc_status: int = 200):
    """A client factory serving the search page, then *post_status* to the search POST."""
    sent: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(f"{request.method} {request.url}")
        if request.method == "POST":
            if post_status != 200:
                return httpx.Response(post_status, text=_AZURE_403)
            return httpx.Response(200, text=_SEARCH_HTML)
        if request.url.host.startswith("mdp."):
            return httpx.Response(get_doc_status, text=_AZURE_403)
        return httpx.Response(200, text=_SEARCH_PAGE_HTML)

    def factory(fonte, **kwargs):
        return httpx.AsyncClient(transport=httpx.MockTransport(handler), **kwargs)

    return factory, sent


@pytest.fixture(autouse=True)
def _no_backoff(monkeypatch):
    async def no_sleep(_seconds):
        return None

    monkeypatch.setattr("mcp_legal_it.lib._http.asyncio.sleep", no_sleep)


def _assert_clean(text: str) -> None:
    assert "non raggiungibile" not in text
    for piece in _URL_PIECES:
        assert piece not in text, piece


class TestCheckQuery:
    @pytest.mark.parametrize("query", ["", "rinnovo tacito", UNA_FRASE, '"rinnovo tacito"'])
    def test_at_most_one_phrase_passes(self, query):
        check_query(query)

    @pytest.mark.parametrize("query", [DUE_FRASI, '"a" "b" "c"', '"rinnovo tacito" "accordi'])
    def test_two_phrases_are_refused(self, query):
        with pytest.raises(QueryNonSupportata, match="una frase tra virgolette"):
            check_query(query)

    def test_the_refusal_is_a_value_error(self):
        # The api reads a ValueError as «richiesta_non_valida», not as a source failure.
        assert issubclass(QueryNonSupportata, ValueError)


class TestTwoPhrasesAreNeverSent:
    async def test_search_tool(self):
        factory, sent = _portal()
        with api.configurazione(client_factory=factory):
            result = await _cerca_giurisprudenza_amministrativa_impl(query=DUE_FRASI)
        assert sent == []
        assert result.success is False and result.error_type == "bad_input"
        text = result.to_str()
        assert "Ricerca non inviata" in text and "una sola frase tra virgolette" in text
        _assert_clean(text)

    async def test_norma_tool(self):
        factory, sent = _portal()
        with api.configurazione(client_factory=factory):
            result = await _giurisprudenza_amm_su_norma_impl(riferimento=DUE_FRASI)
        assert sent == [] and result.error_type == "bad_input"

    async def test_unified_search_with_years(self):
        factory, sent = _portal()

        async def unused(*args, **kwargs):  # the year branch calls the client directly
            raise AssertionError

        with api.configurazione(client_factory=factory):
            result = await _cerca_amministrativa(unused, DUE_FRASI, 2020, 2026, "", 10)
        assert sent == [] and result.error_type == "bad_input"
        _assert_clean(result.to_str())

    async def test_api(self):
        factory, sent = _portal()
        with api.configurazione(client_factory=factory):
            ricerca = await api.cerca_decisioni_amministrative(DUE_FRASI)
        assert sent == []
        assert ricerca.esito == "richiesta_non_valida"
        assert "una frase tra virgolette" in ricerca.errori["parametri"]

    async def test_one_phrase_is_sent(self):
        factory, sent = _portal()
        with api.configurazione(client_factory=factory):
            result = await _cerca_giurisprudenza_amministrativa_impl(query=UNA_FRASE)
        assert [s.split()[0] for s in sent] == ["GET", "POST"]
        assert result.success is True


class TestA403IsARefusalNotAnOutage:
    async def test_search_tool(self):
        factory, sent = _portal(post_status=403)
        with api.configurazione(client_factory=factory):
            result = await _cerca_giurisprudenza_amministrativa_impl(query="rinnovo tacito")
        assert [s.split()[0] for s in sent] == ["GET", "POST"]  # a 4xx is not retried
        assert result.success is False and result.error_type == "refused"
        text = result.to_str()
        assert "HTTP 403" in text and "riformulare" in text
        _assert_clean(text)

    async def test_client_raises_without_the_url(self):
        factory, _sent = _portal(post_status=403)
        with api.configurazione(client_factory=factory):
            with pytest.raises(PortaleRifiuta) as info:
                await search_provvedimenti_page(query="rinnovo tacito")
        _assert_clean(str(info.value))
        assert info.value.__cause__ is None and info.value.__suppress_context__

    async def test_reading_a_document(self):
        factory, _sent = _portal(get_doc_status=403)
        with api.configurazione(client_factory=factory):
            result = await _leggi_provvedimento_amm_impl("cds", "202301234", "202301234_11.xml")
        assert result.error_type == "refused"
        _assert_clean(result.to_str())

    async def test_api(self):
        factory, _sent = _portal(post_status=403)
        with api.configurazione(client_factory=factory):
            ricerca = await api.cerca_decisioni_amministrative("rinnovo tacito")
        assert ricerca.esito == "errore_fonte"
        _assert_clean(ricerca.errore)


class TestA5xxStaysAnOutageWithoutTheUrl:
    async def test_search_tool(self):
        factory, sent = _portal(post_status=502)
        with api.configurazione(client_factory=factory):
            result = await _cerca_giurisprudenza_amministrativa_impl(query="rinnovo tacito")
        assert sum(s.startswith("POST") for s in sent) == 3  # first try + 2 retries
        assert result.error_type == "source_down"
        text = result.to_str()
        assert "HTTP 502" in text
        for piece in _URL_PIECES:
            assert piece not in text, piece

    async def test_api_still_reads_it_as_the_source_down(self):
        factory, _sent = _portal(post_status=503)
        with api.configurazione(client_factory=factory):
            ricerca = await api.cerca_decisioni_amministrative("rinnovo tacito")
        assert ricerca.esito == "fonte_non_raggiungibile"
        for piece in _URL_PIECES:
            assert piece not in ricerca.errore, piece

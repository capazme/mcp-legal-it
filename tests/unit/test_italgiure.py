"""Unit tests for src/lib/italgiure/client.py and src/tools/italgiure.py.

HTTP calls are mocked — no real network access required.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.lib.italgiure.client import (
    build_lookup_params,
    build_norma_variants,
    build_search_params,
    format_estremi,
    format_full_text,
    format_summary,
    get_kind_filter,
    _first,
    _format_date,
)

# Import _impl functions at module level to avoid metaclass conflict when patching httpx
from src.tools.italgiure import (
    _cerca_giurisprudenza_impl,
    _giurisprudenza_su_norma_impl,
    _leggi_sentenza_impl,
    _ultime_pronunce_impl,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_solr_response(docs: list[dict], num_found: int | None = None, highlighting: dict | None = None) -> dict:
    return {
        "responseHeader": {"status": 0, "QTime": 1},
        "response": {"numFound": num_found or len(docs), "start": 0, "docs": docs},
        **({"highlighting": highlighting} if highlighting else {}),
    }


def _civile_doc(num: str = "24003", anno: str = "2025", sez: str = "3") -> dict:
    return {
        "id": f"snciv{anno}{sez}{num}O",
        "numdec": num,
        "anno": anno,
        "datdep": ["20250827"],
        "szdec": sez,
        "materia": ["REVOCATORIA ORDINARIA"],
        "tipoprov": "Ordinanza",
        "kind": "snciv",
        "ocrdis": ["P.Q.M La Corte rigetta il ricorso."],
        "ocr": ["PDFBox: 1 REPUBBLICA ITALIANA " + "x" * 100],
        "nomegiudice": ["MARIO ROSSI"],
    }


def _penale_doc(num: str = "1234", anno: str = "2024", sez: str = "1") -> dict:
    return {
        "id": f"snpen{anno}{sez}{num}S",
        "numdec": num,
        "anno": anno,
        "datdep": ["20240315"],
        "szdec": sez,
        "tipoprov": "Sentenza",
        "kind": "snpen",
        "ocrdis": ["P.Q.M. Dichiara inammissibile."],
    }


def _mock_httpx_client(homepage_resp: dict | None = None, solr_resp: dict | None = None):
    """Return a context manager mock for httpx.AsyncClient."""
    call_count = 0

    async def mock_get(url, **kwargs):
        resp = AsyncMock()
        resp.raise_for_status = MagicMock()
        resp.text = "<html>OK</html>"
        return resp

    async def mock_post(url, **kwargs):
        resp = AsyncMock()
        resp.raise_for_status = MagicMock()
        resp.json = MagicMock(return_value=solr_resp or _make_solr_response([]))
        return resp

    mock_client = AsyncMock()
    mock_client.get = mock_get
    mock_client.post = mock_post
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


# ---------------------------------------------------------------------------
# get_kind_filter
# ---------------------------------------------------------------------------

class TestGetKindFilter:
    def test_civile(self):
        assert get_kind_filter("civile") == ["snciv"]

    def test_penale(self):
        assert get_kind_filter("penale") == ["snpen"]

    def test_tutti(self):
        assert get_kind_filter("tutti") == ["snciv", "snpen"]

    def test_unknown_defaults_to_tutti(self):
        assert get_kind_filter("xyz") == ["snciv", "snpen"]


# ---------------------------------------------------------------------------
# _first helper
# ---------------------------------------------------------------------------

class TestFirst:
    def test_list_returns_first(self):
        assert _first(["a", "b"]) == "a"

    def test_empty_list(self):
        assert _first([]) == ""

    def test_string_passthrough(self):
        assert _first("hello") == "hello"

    def test_none(self):
        assert _first(None) == ""

    def test_int(self):
        assert _first(42) == "42"


# ---------------------------------------------------------------------------
# _format_date
# ---------------------------------------------------------------------------

class TestFormatDate:
    def test_yyyymmdd_list(self):
        assert _format_date(["20250827"]) == "27/08/2025"

    def test_yyyymmdd_string(self):
        assert _format_date("20250315") == "15/03/2025"

    def test_iso_fallback(self):
        assert _format_date(["2025-08-27T00:00:00Z"]) == "27/08/2025"

    def test_empty_list(self):
        assert _format_date([]) == ""

    def test_none(self):
        assert _format_date(None) == ""


# ---------------------------------------------------------------------------
# build_search_params
# ---------------------------------------------------------------------------

class TestBuildSearchParams:
    def test_basic_query(self):
        p = build_search_params("danno biologico")
        assert "danno biologico" in p["q"]
        assert 'kind:"snciv"' in p["q"] or 'kind:"snpen"' in p["q"]
        assert p["sort"] == "pd desc"
        assert p["rows"] == 10

    def test_archivio_civile(self):
        p = build_search_params("test", archivio="civile")
        assert 'kind:"snciv"' in p["q"]
        assert "snpen" not in p["q"]

    def test_archivio_penale(self):
        p = build_search_params("test", archivio="penale")
        assert 'kind:"snpen"' in p["q"]
        assert "snciv" not in p["q"]

    def test_materia_filter(self):
        p = build_search_params("test", materia="contratti")
        assert p.get("fq") and "materia:contratti" in p["fq"]

    def test_sezione_filter(self):
        p = build_search_params("test", sezione="3")
        assert p.get("fq") and "szdec:3" in p["fq"]

    def test_anno_range(self):
        p = build_search_params("test", anno_da=2020, anno_a=2025)
        assert p.get("fq") and "anno:[2020 TO 2025]" in p["fq"]

    def test_anno_da_only(self):
        p = build_search_params("test", anno_da=2022)
        assert p.get("fq") and "anno:[2022 TO *]" in p["fq"]

    def test_anno_a_only(self):
        p = build_search_params("test", anno_a=2023)
        assert p.get("fq") and "anno:[* TO 2023]" in p["fq"]

    def test_highlight_included_by_default(self):
        p = build_search_params("test")
        assert p.get("hl") == "true"
        assert p.get("hl.fl") == "ocr"

    def test_highlight_disabled(self):
        p = build_search_params("test", highlight=False)
        assert "hl" not in p

    def test_rows(self):
        p = build_search_params("test", rows=25)
        assert p["rows"] == 25

    def test_fl_includes_kind(self):
        p = build_search_params("test")
        assert "kind" in p["fl"]


# ---------------------------------------------------------------------------
# build_lookup_params
# ---------------------------------------------------------------------------

class TestBuildLookupParams:
    def test_basic(self):
        p = build_lookup_params(24003, 2025)
        assert "numdec:24003" in p["q"]
        assert "anno:2025" in p["q"]

    def test_archivio_civile(self):
        p = build_lookup_params(1, 2024, archivio="civile")
        assert 'kind:"snciv"' in p["q"]
        assert "snpen" not in p["q"]

    def test_sezione(self):
        p = build_lookup_params(24003, 2025, sezione="3")
        assert "szdec:3" in p["q"]

    def test_sezione_none_not_included(self):
        p = build_lookup_params(24003, 2025)
        assert "szdec" not in p["q"]

    def test_fl_includes_ocr(self):
        p = build_lookup_params(1, 2024)
        assert "ocr" in p["fl"]

    def test_fl_includes_kind(self):
        p = build_lookup_params(1, 2024)
        assert "kind" in p["fl"]

    def test_rows(self):
        p = build_lookup_params(1, 2024)
        assert p["rows"] == 5


# ---------------------------------------------------------------------------
# build_norma_variants
# ---------------------------------------------------------------------------

class TestBuildNormaVariants:
    def test_codice_civile(self):
        q = build_norma_variants("art. 2043 c.c.")
        assert '"art. 2043"' in q
        assert '"articolo 2043"' in q
        assert "c.c." in q or "cod. civ." in q or "codice civile" in q

    def test_codice_penale(self):
        q = build_norma_variants("art. 575 c.p.")
        assert '"art. 575"' in q
        assert "c.p." in q or "cod. pen." in q

    def test_no_match_fallback(self):
        q = build_norma_variants("GDPR art. 13")
        assert 'ocr:("GDPR art. 13")' == q

    def test_articolo_variant(self):
        q = build_norma_variants("articolo 2043 c.c.")
        assert '"art. 2043"' in q

    def test_bis_suffix(self):
        q = build_norma_variants("art. 649-bis c.p.")
        assert "649-bis" in q

    def test_returns_ocr_prefix(self):
        q = build_norma_variants("art. 2043 c.c.")
        assert q.startswith("ocr:(")


# ---------------------------------------------------------------------------
# format_estremi
# ---------------------------------------------------------------------------

class TestFormatEstremi:
    def test_civile_sez_3(self):
        doc = _civile_doc()
        result = format_estremi(doc)
        assert "Cass. civ." in result
        assert "sez. III" in result
        assert "n. 24003/2025" in result
        assert "27/08/2025" in result

    def test_penale(self):
        doc = _penale_doc()
        result = format_estremi(doc)
        assert "Cass. pen." in result

    def test_sezioni_unite(self):
        doc = {**_civile_doc(), "szdec": "SU"}
        result = format_estremi(doc)
        assert "SS.UU." in result

    def test_missing_datdep(self):
        doc = {**_civile_doc(), "datdep": []}
        result = format_estremi(doc)
        assert "dep." not in result

    def test_kind_as_string(self):
        doc = {**_civile_doc(), "kind": "snciv"}
        result = format_estremi(doc)
        assert "Cass. civ." in result


# ---------------------------------------------------------------------------
# format_summary
# ---------------------------------------------------------------------------

class TestFormatSummary:
    def test_includes_estremi(self):
        doc = _civile_doc()
        result = format_summary(doc)
        assert "### Cass. civ." in result

    def test_includes_materia(self):
        doc = _civile_doc()
        result = format_summary(doc)
        assert "REVOCATORIA ORDINARIA" in result

    def test_includes_highlight(self):
        doc = _civile_doc()
        result = format_summary(doc, highlight="estratto <em>danno</em> biologico")
        assert "estratto" in result
        assert "**Estratto**" in result

    def test_includes_dispositivo(self):
        doc = _civile_doc()
        result = format_summary(doc)
        assert "P.Q.M" in result

    def test_no_highlight_when_none(self):
        doc = _civile_doc()
        result = format_summary(doc)
        assert "**Estratto**" not in result

    def test_dispositivo_truncated(self):
        long_disp = "x" * 300
        doc = {**_civile_doc(), "ocrdis": [long_disp]}
        result = format_summary(doc)
        assert "…" in result


# ---------------------------------------------------------------------------
# format_full_text
# ---------------------------------------------------------------------------

class TestFormatFullText:
    def test_includes_heading(self):
        doc = _civile_doc()
        result = format_full_text(doc)
        assert result.startswith("# Cass. civ.")

    def test_includes_materia(self):
        doc = _civile_doc()
        result = format_full_text(doc)
        assert "REVOCATORIA ORDINARIA" in result

    def test_includes_relatore(self):
        doc = _civile_doc()
        result = format_full_text(doc)
        assert "MARIO ROSSI" in result

    def test_truncation(self):
        long_ocr = "T" * 10000
        doc = {**_civile_doc(), "ocr": [long_ocr]}
        result = format_full_text(doc)
        assert "Testo troncato" in result

    def test_no_truncation_when_short(self):
        doc = _civile_doc()
        result = format_full_text(doc)
        assert "Testo troncato" not in result

    def test_includes_dispositivo(self):
        doc = _civile_doc()
        result = format_full_text(doc)
        assert "P.Q.M" in result

    def test_missing_ocr(self):
        doc = {**_civile_doc(), "ocr": []}
        result = format_full_text(doc)
        assert "## Testo della decisione" not in result


# ---------------------------------------------------------------------------
# solr_query (mocked HTTP)
# ---------------------------------------------------------------------------

class TestSolrQuery:
    @pytest.mark.asyncio
    async def test_calls_homepage_first(self):
        """Ensures session cookie is obtained before Solr call."""
        get_urls = []
        post_urls = []

        async def mock_get(url, **kwargs):
            get_urls.append(url)
            resp = AsyncMock()
            resp.raise_for_status = MagicMock()
            return resp

        async def mock_post(url, **kwargs):
            post_urls.append(url)
            resp = AsyncMock()
            resp.raise_for_status = MagicMock()
            resp.json = MagicMock(return_value=_make_solr_response([]))
            return resp

        mock_client = AsyncMock()
        mock_client.get = mock_get
        mock_client.post = mock_post
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("src.lib.italgiure.client.httpx.AsyncClient", return_value=mock_client):
            from src.lib.italgiure.client import solr_query
            await solr_query({"q": "test"})

        assert any("sncass" in url and "isapi" not in url for url in get_urls), "Homepage not fetched"
        assert any("sn-collection" in url for url in post_urls), "Solr endpoint not called"

    @pytest.mark.asyncio
    async def test_returns_json(self):
        expected = _make_solr_response([_civile_doc()])
        mock_client = _mock_httpx_client(solr_resp=expected)

        with patch("src.lib.italgiure.client.httpx.AsyncClient", return_value=mock_client):
            from src.lib.italgiure.client import solr_query
            result = await solr_query({"q": "test"})

        assert result["response"]["numFound"] == 1
        assert result["response"]["docs"][0]["numdec"] == "24003"


# ---------------------------------------------------------------------------
# Tool: _leggi_sentenza_impl (mocked)
# ---------------------------------------------------------------------------

class TestLeggiSentenzaImpl:
    @pytest.mark.asyncio
    async def test_found(self):
        doc = _civile_doc()
        solr_resp = _make_solr_response([doc])
        mock_client = _mock_httpx_client(solr_resp=solr_resp)

        with patch("src.lib.italgiure.client.httpx.AsyncClient", return_value=mock_client):
            result = await _leggi_sentenza_impl(24003, 2025, archivio="civile")

        assert "24003/2025" in result
        assert "Cass. civ." in result
        assert "REVOCATORIA ORDINARIA" in result

    @pytest.mark.asyncio
    async def test_not_found(self):
        mock_client = _mock_httpx_client(solr_resp=_make_solr_response([]))

        with patch("src.lib.italgiure.client.httpx.AsyncClient", return_value=mock_client):
            result = await _leggi_sentenza_impl(99999, 2099)

        assert "non trovata" in result.lower()

    @pytest.mark.asyncio
    async def test_error_returns_message(self):
        async def raise_error(*args, **kwargs):
            raise Exception("connection refused")

        mock_client = AsyncMock()
        mock_client.get = raise_error
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("src.lib.italgiure.client.httpx.AsyncClient", return_value=mock_client):
            result = await _leggi_sentenza_impl(1, 2024)

        assert "Errore" in result


# ---------------------------------------------------------------------------
# Tool: _cerca_giurisprudenza_impl (mocked)
# ---------------------------------------------------------------------------

class TestCercaGiurisprudenzaImpl:
    @pytest.mark.asyncio
    async def test_returns_results(self):
        doc = _civile_doc()
        hl = {"snciv202532400 3O": {"ocr": ["estratto <em>danno</em> biologico"]}}
        solr_resp = _make_solr_response([doc], highlighting=hl)
        mock_client = _mock_httpx_client(solr_resp=solr_resp)

        with patch("src.lib.italgiure.client.httpx.AsyncClient", return_value=mock_client):
            result = await _cerca_giurisprudenza_impl("danno biologico")

        assert "Trovate" in result
        assert "Cass. civ." in result

    @pytest.mark.asyncio
    async def test_empty_result(self):
        mock_client = _mock_httpx_client(solr_resp=_make_solr_response([]))

        with patch("src.lib.italgiure.client.httpx.AsyncClient", return_value=mock_client):
            result = await _cerca_giurisprudenza_impl("xyz nessun risultato")

        assert "Nessuna" in result

    @pytest.mark.asyncio
    async def test_max_risultati_capped(self):
        captured = {}

        async def mock_get(url, **kwargs):
            resp = AsyncMock()
            resp.raise_for_status = MagicMock()
            return resp

        async def mock_post(url, content=None, **kwargs):
            captured["body"] = content
            resp = AsyncMock()
            resp.raise_for_status = MagicMock()
            resp.json = MagicMock(return_value=_make_solr_response([]))
            return resp

        mock_client = AsyncMock()
        mock_client.get = mock_get
        mock_client.post = mock_post
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("src.lib.italgiure.client.httpx.AsyncClient", return_value=mock_client):
            await _cerca_giurisprudenza_impl("test", max_risultati=999)

        assert "rows=50" in captured.get("body", ""), "max_risultati should be capped at 50"


# ---------------------------------------------------------------------------
# Tool: _giurisprudenza_su_norma_impl (mocked)
# ---------------------------------------------------------------------------

class TestGiurisprudenzaSuNormaImpl:
    @pytest.mark.asyncio
    async def test_builds_norma_variants(self):
        captured = {}

        async def mock_get(url, **kwargs):
            resp = AsyncMock()
            resp.raise_for_status = MagicMock()
            return resp

        async def mock_post(url, content=None, **kwargs):
            captured["body"] = content or ""
            resp = AsyncMock()
            resp.raise_for_status = MagicMock()
            resp.json = MagicMock(return_value=_make_solr_response([]))
            return resp

        mock_client = AsyncMock()
        mock_client.get = mock_get
        mock_client.post = mock_post
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("src.lib.italgiure.client.httpx.AsyncClient", return_value=mock_client):
            await _giurisprudenza_su_norma_impl("art. 2043 c.c.")

        body = captured.get("body", "")
        assert "2043" in body

    @pytest.mark.asyncio
    async def test_not_found_message(self):
        mock_client = _mock_httpx_client(solr_resp=_make_solr_response([]))

        with patch("src.lib.italgiure.client.httpx.AsyncClient", return_value=mock_client):
            result = await _giurisprudenza_su_norma_impl("art. 9999 c.c.")

        assert "Nessuna" in result


# ---------------------------------------------------------------------------
# Tool: _ultime_pronunce_impl (mocked)
# ---------------------------------------------------------------------------

class TestUltimePronunceImpl:
    @pytest.mark.asyncio
    async def test_returns_results(self):
        docs = [_civile_doc(str(i), "2025") for i in range(3)]
        mock_client = _mock_httpx_client(solr_resp=_make_solr_response(docs))

        with patch("src.lib.italgiure.client.httpx.AsyncClient", return_value=mock_client):
            result = await _ultime_pronunce_impl()

        assert "Ultime pronunce" in result
        assert "Cass. civ." in result

    @pytest.mark.asyncio
    async def test_empty(self):
        mock_client = _mock_httpx_client(solr_resp=_make_solr_response([]))

        with patch("src.lib.italgiure.client.httpx.AsyncClient", return_value=mock_client):
            result = await _ultime_pronunce_impl()

        assert "Nessuna" in result

    @pytest.mark.asyncio
    async def test_fq_with_materia(self):
        captured = {}

        async def mock_get(url, **kwargs):
            resp = AsyncMock()
            resp.raise_for_status = MagicMock()
            return resp

        async def mock_post(url, content=None, **kwargs):
            captured["body"] = content or ""
            resp = AsyncMock()
            resp.raise_for_status = MagicMock()
            resp.json = MagicMock(return_value=_make_solr_response([]))
            return resp

        mock_client = AsyncMock()
        mock_client.get = mock_get
        mock_client.post = mock_post
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("src.lib.italgiure.client.httpx.AsyncClient", return_value=mock_client):
            await _ultime_pronunce_impl(materia="contratti")

        body = captured.get("body", "")
        assert "materia" in body
        assert "contratti" in body

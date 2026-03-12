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
        "relatore": ["MARIO ROSSI"],
        "presidente": ["ANNA BIANCHI"],
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


def _capturing_mock_client(solr_resp: dict | None = None) -> tuple[AsyncMock, dict]:
    """Return (mock_client, captured) where captured['body'] has the POST body."""
    captured: dict = {}

    async def mock_get(url, **kwargs):
        resp = AsyncMock()
        resp.raise_for_status = MagicMock()
        return resp

    async def mock_post(url, content=None, **kwargs):
        captured["body"] = content or ""
        resp = AsyncMock()
        resp.raise_for_status = MagicMock()
        resp.json = MagicMock(return_value=solr_resp or _make_solr_response([]))
        return resp

    mock_client = AsyncMock()
    mock_client.get = mock_get
    mock_client.post = mock_post
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client, captured


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
# build_search_params — core
# ---------------------------------------------------------------------------

class TestBuildSearchParams:
    def test_basic_query(self):
        p = build_search_params("danno biologico")
        assert p["q"] == "danno biologico"
        assert p["defType"] == "edismax"
        assert "ocrdis^5" in p["qf"]
        fq_str = " ".join(p["fq"]) if isinstance(p["fq"], list) else p["fq"]
        assert 'kind:"snciv"' in fq_str or 'kind:"snpen"' in fq_str

    def test_default_sort_is_rilevanza(self):
        p = build_search_params("test")
        assert p["sort"] == "score desc"

    def test_default_rows_is_5(self):
        p = build_search_params("test")
        assert p["rows"] == 5

    def test_archivio_civile(self):
        p = build_search_params("test", archivio="civile")
        fq_str = " ".join(p["fq"]) if isinstance(p["fq"], list) else p["fq"]
        assert 'kind:"snciv"' in fq_str
        assert "snpen" not in fq_str

    def test_archivio_penale(self):
        p = build_search_params("test", archivio="penale")
        fq_str = " ".join(p["fq"]) if isinstance(p["fq"], list) else p["fq"]
        assert 'kind:"snpen"' in fq_str
        assert "snciv" not in fq_str

    def test_materia_filter(self):
        p = build_search_params("test", materia="contratti")
        fq = p.get("fq", [])
        assert any("materia:contratti" in f for f in fq)

    def test_sezione_filter(self):
        p = build_search_params("test", sezione="3")
        fq = p.get("fq", [])
        assert any("szdec:3" in f for f in fq)

    def test_anno_range(self):
        p = build_search_params("test", anno_da=2020, anno_a=2025)
        fq = p.get("fq", [])
        assert any("anno:[2020 TO 2025]" in f for f in fq)

    def test_anno_da_only(self):
        p = build_search_params("test", anno_da=2022)
        fq = p.get("fq", [])
        assert any("anno:[2022 TO *]" in f for f in fq)

    def test_anno_a_only(self):
        p = build_search_params("test", anno_a=2023)
        fq = p.get("fq", [])
        assert any("anno:[* TO 2023]" in f for f in fq)

    def test_highlight_included_by_default(self):
        p = build_search_params("test")
        assert p.get("hl") == "true"
        assert "ocr" in p.get("hl.fl", "")
        assert "ocrdis" in p.get("hl.fl", "")

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
# build_search_params — NEW: minimum match
# ---------------------------------------------------------------------------

class TestBuildSearchParamsMM:
    def test_mm_is_set(self):
        p = build_search_params("danno biologico responsabilita medica")
        assert "mm" in p
        assert p["mm"] == "2<75% 5<60%"

    def test_mm_present_for_single_term(self):
        p = build_search_params("danno")
        assert "mm" in p


# ---------------------------------------------------------------------------
# build_search_params — NEW: phrase boosting
# ---------------------------------------------------------------------------

class TestBuildSearchParamsPhraseBoosting:
    def test_pf_includes_ocr(self):
        p = build_search_params("danno biologico")
        assert "ocr^3" in p["pf"]
        assert "ocrdis^10" in p["pf"]

    def test_pf2_present(self):
        p = build_search_params("danno biologico")
        assert "pf2" in p
        assert "ocrdis^6" in p["pf2"]
        assert "ocr^2" in p["pf2"]

    def test_pf3_present(self):
        p = build_search_params("danno biologico grave")
        assert "pf3" in p
        assert "ocrdis^4" in p["pf3"]
        assert "ocr^1" in p["pf3"]


# ---------------------------------------------------------------------------
# build_search_params — NEW: ordinamento
# ---------------------------------------------------------------------------

class TestBuildSearchParamsOrdinamento:
    def test_rilevanza_default(self):
        p = build_search_params("test")
        assert p["sort"] == "score desc"

    def test_rilevanza_explicit(self):
        p = build_search_params("test", ordinamento="rilevanza")
        assert p["sort"] == "score desc"

    def test_data(self):
        p = build_search_params("test", ordinamento="data")
        assert p["sort"] == "pd desc"

    def test_unknown_ordinamento_falls_to_data(self):
        p = build_search_params("test", ordinamento="unknown")
        assert p["sort"] == "pd desc"


# ---------------------------------------------------------------------------
# build_search_params — NEW: tipo_provvedimento
# ---------------------------------------------------------------------------

class TestBuildSearchParamsTipoProv:
    def test_sentenza(self):
        p = build_search_params("test", tipo_provvedimento="sentenza")
        fq = p.get("fq", [])
        assert any("tipoprov:S" in f for f in fq)

    def test_ordinanza(self):
        p = build_search_params("test", tipo_provvedimento="ordinanza")
        fq = p.get("fq", [])
        assert any("tipoprov:O" in f for f in fq)

    def test_decreto(self):
        p = build_search_params("test", tipo_provvedimento="decreto")
        fq = p.get("fq", [])
        assert any("tipoprov:D" in f for f in fq)

    def test_invalid_tipo_not_added(self):
        p = build_search_params("test", tipo_provvedimento="invalid")
        fq = p.get("fq", [])
        assert not any("tipoprov" in f for f in fq)

    def test_no_tipo_default(self):
        p = build_search_params("test")
        fq = p.get("fq", [])
        assert not any("tipoprov" in f for f in fq)


# ---------------------------------------------------------------------------
# build_search_params — NEW: solo_sezioni_unite
# ---------------------------------------------------------------------------

class TestBuildSearchParamsSezioniUnite:
    def test_solo_sezioni_unite_true(self):
        p = build_search_params("test", solo_sezioni_unite=True)
        fq = p.get("fq", [])
        assert any("szdec:(SU OR U)" in f for f in fq)

    def test_solo_sezioni_unite_false(self):
        p = build_search_params("test", solo_sezioni_unite=False)
        fq = p.get("fq", [])
        assert not any("SU OR U" in f for f in fq)

    def test_sezioni_unite_with_sezione_both_present(self):
        """solo_sezioni_unite + sezione are independent filters."""
        p = build_search_params("test", sezione="3", solo_sezioni_unite=True)
        fq = p.get("fq", [])
        assert any("szdec:3" in f for f in fq)
        assert any("szdec:(SU OR U)" in f for f in fq)


# ---------------------------------------------------------------------------
# build_search_params — NEW: combined filters
# ---------------------------------------------------------------------------

class TestBuildSearchParamsCombined:
    def test_all_filters(self):
        p = build_search_params(
            "test",
            archivio="civile",
            materia="contratti",
            sezione="3",
            anno_da=2020,
            anno_a=2025,
            tipo_provvedimento="sentenza",
            solo_sezioni_unite=True,
            ordinamento="rilevanza",
            rows=3,
        )
        fq = p.get("fq", [])
        fq_joined = " ".join(fq)
        assert 'kind:"snciv"' in fq_joined
        assert "materia:contratti" in fq_joined
        assert "szdec:3" in fq_joined
        assert "szdec:(SU OR U)" in fq_joined
        assert "tipoprov:S" in fq_joined
        assert "anno:[2020 TO 2025]" in fq_joined
        assert p["sort"] == "score desc"
        assert p["rows"] == 3
        assert p["mm"] == "2<75% 5<60%"

    def test_minimal_call(self):
        p = build_search_params("test")
        assert p["q"] == "test"
        assert p["defType"] == "edismax"
        assert len(p["fq"]) == 1  # only kind filter


# ---------------------------------------------------------------------------
# build_lookup_params
# ---------------------------------------------------------------------------

class TestBuildLookupParams:
    def test_basic(self):
        p = build_lookup_params(24003, 2025)
        assert "numdec:24003" in p["q"]
        assert "anno:2025" in p["q"]

    def test_zero_padding(self):
        p = build_lookup_params(3806, 2026)
        assert "numdec:03806" in p["q"]

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
        hl = {"ocr": ["estratto <em>danno</em> biologico"]}
        result = format_summary(doc, highlights=hl)
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
        long_ocr = "T" * 40000
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
        mock_client, captured = _capturing_mock_client()

        with patch("src.lib.italgiure.client.httpx.AsyncClient", return_value=mock_client):
            await _cerca_giurisprudenza_impl("test", max_risultati=999)

        assert "rows=50" in captured.get("body", ""), "max_risultati should be capped at 50"

    @pytest.mark.asyncio
    async def test_default_ordinamento_rilevanza(self):
        mock_client, captured = _capturing_mock_client()

        with patch("src.lib.italgiure.client.httpx.AsyncClient", return_value=mock_client):
            await _cerca_giurisprudenza_impl("danno biologico")

        body = captured.get("body", "")
        assert "sort=score+desc" in body or "sort=score%20desc" in body or "sort=score desc" in body.replace("+", " ")

    @pytest.mark.asyncio
    async def test_ordinamento_data(self):
        mock_client, captured = _capturing_mock_client()

        with patch("src.lib.italgiure.client.httpx.AsyncClient", return_value=mock_client):
            await _cerca_giurisprudenza_impl("danno biologico", ordinamento="data")

        body = captured.get("body", "")
        assert "pd" in body

    @pytest.mark.asyncio
    async def test_output_shows_ordinamento_label(self):
        doc = _civile_doc()
        solr_resp = _make_solr_response([doc], num_found=100)
        mock_client = _mock_httpx_client(solr_resp=solr_resp)

        with patch("src.lib.italgiure.client.httpx.AsyncClient", return_value=mock_client):
            result = await _cerca_giurisprudenza_impl("test", ordinamento="rilevanza")
        assert "per rilevanza" in result

        mock_client = _mock_httpx_client(solr_resp=solr_resp)
        with patch("src.lib.italgiure.client.httpx.AsyncClient", return_value=mock_client):
            result = await _cerca_giurisprudenza_impl("test", ordinamento="data")
        assert "per data" in result

    @pytest.mark.asyncio
    async def test_tipo_provvedimento_sentenza(self):
        mock_client, captured = _capturing_mock_client()

        with patch("src.lib.italgiure.client.httpx.AsyncClient", return_value=mock_client):
            await _cerca_giurisprudenza_impl("test", tipo_provvedimento="sentenza")

        body = captured.get("body", "")
        assert "tipoprov" in body

    def test_tipo_provvedimento_invalid_not_in_params(self):
        """Invalid tipo_provvedimento should not produce a tipoprov fq filter."""
        p = build_search_params("test", tipo_provvedimento="invalid")
        fq = p.get("fq", [])
        assert not any("tipoprov" in f for f in fq)

    @pytest.mark.asyncio
    async def test_solo_sezioni_unite(self):
        mock_client, captured = _capturing_mock_client()

        with patch("src.lib.italgiure.client.httpx.AsyncClient", return_value=mock_client):
            await _cerca_giurisprudenza_impl("test", solo_sezioni_unite=True)

        body = captured.get("body", "")
        assert "SU" in body

    @pytest.mark.asyncio
    async def test_solo_sezioni_unite_false_no_filter(self):
        mock_client, captured = _capturing_mock_client()

        with patch("src.lib.italgiure.client.httpx.AsyncClient", return_value=mock_client):
            await _cerca_giurisprudenza_impl("test", solo_sezioni_unite=False)

        body = captured.get("body", "")
        # SU appears in kind filter but not as szdec filter
        assert "szdec" not in body or "SU+OR+U" not in body

    @pytest.mark.asyncio
    async def test_mm_present_in_body(self):
        mock_client, captured = _capturing_mock_client()

        with patch("src.lib.italgiure.client.httpx.AsyncClient", return_value=mock_client):
            await _cerca_giurisprudenza_impl("danno biologico responsabilita")

        body = captured.get("body", "")
        assert "mm=" in body

    @pytest.mark.asyncio
    async def test_pf2_present_in_body(self):
        mock_client, captured = _capturing_mock_client()

        with patch("src.lib.italgiure.client.httpx.AsyncClient", return_value=mock_client):
            await _cerca_giurisprudenza_impl("danno biologico")

        body = captured.get("body", "")
        assert "pf2=" in body

    @pytest.mark.asyncio
    async def test_default_max_risultati_is_5(self):
        mock_client, captured = _capturing_mock_client()

        with patch("src.lib.italgiure.client.httpx.AsyncClient", return_value=mock_client):
            await _cerca_giurisprudenza_impl("test")

        body = captured.get("body", "")
        assert "rows=5" in body

    @pytest.mark.asyncio
    async def test_pagination(self):
        mock_client, captured = _capturing_mock_client()

        with patch("src.lib.italgiure.client.httpx.AsyncClient", return_value=mock_client):
            await _cerca_giurisprudenza_impl("test", max_risultati=5, pagina=2)

        body = captured.get("body", "")
        assert "start=10" in body

    @pytest.mark.asyncio
    async def test_combined_filters(self):
        mock_client, captured = _capturing_mock_client()

        with patch("src.lib.italgiure.client.httpx.AsyncClient", return_value=mock_client):
            await _cerca_giurisprudenza_impl(
                "test",
                archivio="civile",
                materia="contratti",
                sezione="3",
                anno_da=2020,
                anno_a=2025,
                tipo_provvedimento="sentenza",
                solo_sezioni_unite=True,
                ordinamento="rilevanza",
                max_risultati=3,
            )

        body = captured.get("body", "")
        assert "snciv" in body
        assert "contratti" in body
        assert "tipoprov" in body
        assert "rows=3" in body


# ---------------------------------------------------------------------------
# Tool: _giurisprudenza_su_norma_impl (mocked)
# ---------------------------------------------------------------------------

class TestGiurisprudenzaSuNormaImpl:
    @pytest.mark.asyncio
    async def test_builds_norma_variants(self):
        mock_client, captured = _capturing_mock_client()

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

    @pytest.mark.asyncio
    async def test_solo_sezioni_unite(self):
        mock_client, captured = _capturing_mock_client()

        with patch("src.lib.italgiure.client.httpx.AsyncClient", return_value=mock_client):
            await _giurisprudenza_su_norma_impl("art. 2043 c.c.", solo_sezioni_unite=True)

        body = captured.get("body", "")
        assert "SU" in body

    @pytest.mark.asyncio
    async def test_anno_range(self):
        mock_client, captured = _capturing_mock_client()

        with patch("src.lib.italgiure.client.httpx.AsyncClient", return_value=mock_client):
            await _giurisprudenza_su_norma_impl("art. 2043 c.c.", anno_da=2020, anno_a=2025)

        body = captured.get("body", "")
        assert "2020" in body
        assert "2025" in body

    @pytest.mark.asyncio
    async def test_anno_da_only(self):
        mock_client, captured = _capturing_mock_client()

        with patch("src.lib.italgiure.client.httpx.AsyncClient", return_value=mock_client):
            await _giurisprudenza_su_norma_impl("art. 2043 c.c.", anno_da=2022)

        body = captured.get("body", "")
        assert "2022" in body

    @pytest.mark.asyncio
    async def test_anno_a_only(self):
        mock_client, captured = _capturing_mock_client()

        with patch("src.lib.italgiure.client.httpx.AsyncClient", return_value=mock_client):
            await _giurisprudenza_su_norma_impl("art. 2043 c.c.", anno_a=2023)

        body = captured.get("body", "")
        assert "2023" in body

    @pytest.mark.asyncio
    async def test_default_rows_5(self):
        mock_client, captured = _capturing_mock_client()

        with patch("src.lib.italgiure.client.httpx.AsyncClient", return_value=mock_client):
            await _giurisprudenza_su_norma_impl("art. 2043 c.c.")

        body = captured.get("body", "")
        assert "rows=5" in body

    @pytest.mark.asyncio
    async def test_returns_formatted_results(self):
        doc = _civile_doc()
        hl = {doc["id"]: {"ocr": ["art. 2043 codice civile"]}}
        solr_resp = _make_solr_response([doc], num_found=50, highlighting=hl)
        mock_client = _mock_httpx_client(solr_resp=solr_resp)

        with patch("src.lib.italgiure.client.httpx.AsyncClient", return_value=mock_client):
            result = await _giurisprudenza_su_norma_impl("art. 2043 c.c.")

        assert "Trovate 50 decisioni" in result
        assert "Cass. civ." in result

    @pytest.mark.asyncio
    async def test_no_fq_when_no_filters(self):
        mock_client, captured = _capturing_mock_client()

        with patch("src.lib.italgiure.client.httpx.AsyncClient", return_value=mock_client):
            await _giurisprudenza_su_norma_impl("art. 2043 c.c.")

        body = captured.get("body", "")
        # fq should not be present when no filters
        assert "fq=" not in body

    @pytest.mark.asyncio
    async def test_error_handling(self):
        async def raise_error(*args, **kwargs):
            raise Exception("timeout")

        mock_client = AsyncMock()
        mock_client.get = raise_error
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("src.lib.italgiure.client.httpx.AsyncClient", return_value=mock_client):
            result = await _giurisprudenza_su_norma_impl("art. 2043 c.c.")

        assert "Errore" in result


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
        mock_client, captured = _capturing_mock_client()

        with patch("src.lib.italgiure.client.httpx.AsyncClient", return_value=mock_client):
            await _ultime_pronunce_impl(materia="contratti")

        body = captured.get("body", "")
        assert "materia" in body
        assert "contratti" in body

    @pytest.mark.asyncio
    async def test_solo_sezioni_unite(self):
        mock_client, captured = _capturing_mock_client()

        with patch("src.lib.italgiure.client.httpx.AsyncClient", return_value=mock_client):
            await _ultime_pronunce_impl(solo_sezioni_unite=True)

        body = captured.get("body", "")
        assert "SU" in body

    @pytest.mark.asyncio
    async def test_solo_sezioni_unite_false(self):
        mock_client, captured = _capturing_mock_client()

        with patch("src.lib.italgiure.client.httpx.AsyncClient", return_value=mock_client):
            await _ultime_pronunce_impl(solo_sezioni_unite=False)

        body = captured.get("body", "")
        # No fq at all when no filters
        assert "fq=" not in body

    @pytest.mark.asyncio
    async def test_default_rows_5(self):
        mock_client, captured = _capturing_mock_client()

        with patch("src.lib.italgiure.client.httpx.AsyncClient", return_value=mock_client):
            await _ultime_pronunce_impl()

        body = captured.get("body", "")
        assert "rows=5" in body

    @pytest.mark.asyncio
    async def test_tipo_provvedimento(self):
        mock_client, captured = _capturing_mock_client()

        with patch("src.lib.italgiure.client.httpx.AsyncClient", return_value=mock_client):
            await _ultime_pronunce_impl(tipo_provvedimento="sentenza")

        body = captured.get("body", "")
        assert "tipoprov" in body

    @pytest.mark.asyncio
    async def test_combined_filters(self):
        mock_client, captured = _capturing_mock_client()

        with patch("src.lib.italgiure.client.httpx.AsyncClient", return_value=mock_client):
            await _ultime_pronunce_impl(
                materia="contratti",
                sezione="3",
                archivio="civile",
                tipo_provvedimento="ordinanza",
                solo_sezioni_unite=True,
                max_risultati=3,
            )

        body = captured.get("body", "")
        assert "contratti" in body
        assert "rows=3" in body

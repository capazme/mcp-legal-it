"""Unit tests for src/lib/italgiure/client.py and src/tools/italgiure.py.

HTTP calls are mocked — no real network access required.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.lib.italgiure.client import (
    SolrSession,
    build_explore_params,
    build_lookup_params,
    build_norma_variants,
    build_search_params,
    format_estremi,
    format_facets,
    format_full_text,
    format_summary,
    get_kind_filter,
    _first,
    _format_date,
)

# Import _impl functions at module level to avoid metaclass conflict when patching httpx
from src.tools.italgiure import (
    _cerca_giurisprudenza_impl,
    _filter_by_score,
    _giurisprudenza_articolo_impl,
    _giurisprudenza_su_norma_impl,
    _leggi_sentenza_impl,
    _parse_articolo_riferimento,
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
# build_norma_variants — expanded codes and act types
# ---------------------------------------------------------------------------

class TestBuildNormaVariantsExpanded:
    def test_dlgs_231_produces_decreto_legislativo_variant(self):
        q = build_norma_variants("art. 6 D.Lgs. 231/2001")
        assert '"art. 6"' in q
        assert '"articolo 6"' in q
        assert "decreto legislativo" in q.lower()

    def test_dlgs_numeric_identifier_included(self):
        q = build_norma_variants("art. 6 D.Lgs. 231/2001")
        assert "231" in q

    def test_regression_codice_civile(self):
        q = build_norma_variants("art. 2043 c.c.")
        assert '"art. 2043"' in q
        assert '"articolo 2043"' in q
        assert "codice civile" in q.lower() or "c.c." in q

    def test_codice_della_strada(self):
        q = build_norma_variants("art. 37 c.d.s.")
        assert '"art. 37"' in q
        assert "codice della strada" in q.lower() or "cod. strada" in q.lower()

    def test_testo_unico_bancario(self):
        q = build_norma_variants("art. 5 t.u.b.")
        assert '"art. 5"' in q
        assert "testo unico bancario" in q.lower() or "t.u.b." in q

    def test_legge_reference(self):
        q = build_norma_variants("art. 21 L. 241/1990")
        assert '"art. 21"' in q
        assert "legge" in q.lower() or "L." in q

    def test_decreto_legge_reference(self):
        q = build_norma_variants("art. 1 D.L. 78/2010")
        assert '"art. 1"' in q
        assert "decreto legge" in q.lower() or "D.L." in q

    def test_cpa_codice_del_processo_amministrativo(self):
        q = build_norma_variants("art. 120 c.p.a.")
        assert '"art. 120"' in q
        assert "codice del processo amministrativo" in q.lower() or "c.p.a." in q

    def test_tuf_testo_unico_finanza(self):
        q = build_norma_variants("art. 94 t.u.f.")
        assert '"art. 94"' in q
        assert "testo unico finanza" in q.lower() or "t.u.f." in q

    def test_ccii_codice_della_crisi(self):
        q = build_norma_variants("art. 7 c.c.i.i.")
        assert '"art. 7"' in q
        assert "codice della crisi" in q.lower() or "c.c.i.i." in q or "CCII" in q

    def test_returns_ocr_prefix_for_all_new_codes(self):
        for ref in ["art. 5 t.u.b.", "art. 37 c.d.s.", "art. 120 c.p.a.", "art. 94 t.u.f."]:
            q = build_norma_variants(ref)
            assert q.startswith("ocr:("), f"Expected ocr:( prefix for {ref!r}, got: {q}"


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

        assert result.success
        assert "24003/2025" in result.results_text
        assert "Cass. civ." in result.results_text
        assert "REVOCATORIA ORDINARIA" in result.results_text

    @pytest.mark.asyncio
    async def test_not_found(self):
        mock_client = _mock_httpx_client(solr_resp=_make_solr_response([]))

        with patch("src.lib.italgiure.client.httpx.AsyncClient", return_value=mock_client):
            result = await _leggi_sentenza_impl(99999, 2099)

        assert not result.success
        assert result.error_type == "no_results"
        assert "non trovata" in result.results_text.lower()

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

        assert not result.success
        assert result.error_type == "source_down"


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

        assert result.success
        assert "Trovate" in result.results_text
        assert "Cass. civ." in result.results_text

    @pytest.mark.asyncio
    async def test_empty_result(self):
        mock_client = _mock_httpx_client(solr_resp=_make_solr_response([]))

        with patch("src.lib.italgiure.client.httpx.AsyncClient", return_value=mock_client):
            result = await _cerca_giurisprudenza_impl("xyz nessun risultato")

        assert result.success
        assert "Nessuna" in result.results_text

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
        assert "per rilevanza" in result.results_text

        mock_client = _mock_httpx_client(solr_resp=solr_resp)
        with patch("src.lib.italgiure.client.httpx.AsyncClient", return_value=mock_client):
            result = await _cerca_giurisprudenza_impl("test", ordinamento="data")
        assert "per data" in result.results_text

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

        assert not result.success
        assert result.error_type == "no_results"
        assert "Nessuna" in result.results_text

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

        assert result.success
        assert "Trovate 50 decisioni" in result.results_text
        assert "Cass. civ." in result.results_text

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

        assert not result.success
        assert result.error_type == "source_down"


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

        assert result.success
        assert "Ultime pronunce" in result.results_text
        assert "Cass. civ." in result.results_text

    @pytest.mark.asyncio
    async def test_empty(self):
        mock_client = _mock_httpx_client(solr_resp=_make_solr_response([]))

        with patch("src.lib.italgiure.client.httpx.AsyncClient", return_value=mock_client):
            result = await _ultime_pronunce_impl()

        assert not result.success
        assert result.error_type == "no_results"
        assert "Nessuna" in result.results_text

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


# ---------------------------------------------------------------------------
# SolrSession
# ---------------------------------------------------------------------------

class TestSolrSession:
    @pytest.mark.asyncio
    async def test_session_reuses_client(self):
        """Session should call GET homepage once and allow multiple queries."""
        get_count = 0
        post_count = 0

        async def mock_get(url, **kwargs):
            nonlocal get_count
            get_count += 1
            resp = AsyncMock()
            resp.raise_for_status = MagicMock()
            return resp

        async def mock_post(url, content=None, **kwargs):
            nonlocal post_count
            post_count += 1
            resp = AsyncMock()
            resp.raise_for_status = MagicMock()
            resp.json = MagicMock(return_value=_make_solr_response([]))
            return resp

        mock_client = AsyncMock()
        mock_client.get = mock_get
        mock_client.post = mock_post
        mock_client.aclose = AsyncMock()

        with patch("src.lib.italgiure.client.httpx.AsyncClient", return_value=mock_client):
            async with SolrSession() as session:
                await session.query({"q": "test1"})
                await session.query({"q": "test2"})
                await session.query({"q": "test3"})

        assert get_count == 1, "Homepage should be fetched once"
        assert post_count == 3, "Three queries should produce three POSTs"

    @pytest.mark.asyncio
    async def test_session_not_entered_raises(self):
        session = SolrSession()
        with pytest.raises(RuntimeError, match="not entered"):
            await session.query({"q": "test"})

    @pytest.mark.asyncio
    async def test_solr_query_with_session(self):
        """solr_query(params, session=session) should delegate to session.query."""
        async def mock_get(url, **kwargs):
            resp = AsyncMock()
            resp.raise_for_status = MagicMock()
            return resp

        async def mock_post(url, content=None, **kwargs):
            resp = AsyncMock()
            resp.raise_for_status = MagicMock()
            resp.json = MagicMock(return_value=_make_solr_response([_civile_doc()]))
            return resp

        mock_client = AsyncMock()
        mock_client.get = mock_get
        mock_client.post = mock_post
        mock_client.aclose = AsyncMock()

        with patch("src.lib.italgiure.client.httpx.AsyncClient", return_value=mock_client):
            from src.lib.italgiure.client import solr_query as sq
            async with SolrSession() as session:
                result = await sq({"q": "test"}, session=session)

        assert result["response"]["docs"][0]["numdec"] == "24003"

    @pytest.mark.asyncio
    async def test_solr_query_without_session_backward_compat(self):
        """solr_query(params) without session should still work (backward compat)."""
        mock_client = _mock_httpx_client(solr_resp=_make_solr_response([_civile_doc()]))
        with patch("src.lib.italgiure.client.httpx.AsyncClient", return_value=mock_client):
            from src.lib.italgiure.client import solr_query as sq
            result = await sq({"q": "test"})
        assert result["response"]["numFound"] == 1


# ---------------------------------------------------------------------------
# build_search_params — campo
# ---------------------------------------------------------------------------

class TestBuildSearchParamsCampo:
    def test_default_tutto(self):
        p = build_search_params("test")
        assert "ocrdis^5" in p["qf"]
        assert "ocr^1" in p["qf"]

    def test_campo_dispositivo_qf(self):
        p = build_search_params("test", campo="dispositivo")
        assert p["qf"] == "ocrdis^1"
        assert "ocr^" not in p["qf"]

    def test_campo_dispositivo_pf(self):
        p = build_search_params("test", campo="dispositivo")
        assert p["pf"] == "ocrdis^3"
        assert "ocr^" not in p["pf"]

    def test_campo_dispositivo_pf2(self):
        p = build_search_params("test", campo="dispositivo")
        assert p["pf2"] == "ocrdis^2"

    def test_campo_dispositivo_pf3(self):
        p = build_search_params("test", campo="dispositivo")
        assert p["pf3"] == "ocrdis^1"


# ---------------------------------------------------------------------------
# build_search_params — include_facets
# ---------------------------------------------------------------------------

class TestBuildSearchParamsFacets:
    def test_no_facets_by_default(self):
        p = build_search_params("test")
        assert "facet" not in p

    def test_facets_enabled(self):
        p = build_search_params("test", include_facets=True)
        assert p["facet"] == "true"
        assert "materia" in p["facet.field"]
        assert "szdec" in p["facet.field"]
        assert "anno" in p["facet.field"]
        assert "tipoprov" in p["facet.field"]
        assert p["facet.limit"] == 10
        assert p["facet.mincount"] == 1

    def test_score_in_fl(self):
        p = build_search_params("test")
        assert "score" in p["fl"]


# ---------------------------------------------------------------------------
# build_search_params — mm override
# ---------------------------------------------------------------------------

class TestBuildSearchParamsMmOverride:
    def test_default_mm(self):
        p = build_search_params("test")
        assert p["mm"] == "2<75% 5<60%"

    def test_mm_override(self):
        p = build_search_params("test", mm="100%")
        assert p["mm"] == "100%"


# ---------------------------------------------------------------------------
# build_explore_params
# ---------------------------------------------------------------------------

class TestBuildExploreParams:
    def test_rows_zero(self):
        p = build_explore_params("test")
        assert p["rows"] == 0

    def test_facets_enabled(self):
        p = build_explore_params("test")
        assert p["facet"] == "true"
        assert "materia" in p["facet.field"]

    def test_campo_tutto(self):
        p = build_explore_params("test", campo="tutto")
        assert "ocr^1" in p["qf"]

    def test_campo_dispositivo(self):
        p = build_explore_params("test", campo="dispositivo")
        assert p["qf"] == "ocrdis^1"
        assert "ocr^" not in p["qf"]

    def test_archivio_civile(self):
        p = build_explore_params("test", archivio="civile")
        fq_str = " ".join(p["fq"]) if isinstance(p["fq"], list) else p["fq"]
        assert 'kind:"snciv"' in fq_str
        assert "snpen" not in fq_str

    def test_fl_minimal(self):
        p = build_explore_params("test")
        assert p["fl"] == "id"


# ---------------------------------------------------------------------------
# format_facets
# ---------------------------------------------------------------------------

class TestFormatFacets:
    def test_basic_formatting(self):
        facet_counts = {
            "facet_fields": {
                "materia": ["contratti", 45, "responsabilità", 23],
                "szdec": ["3", 30, "1", 20, "SU", 8],
                "anno": ["2024", 25, "2023", 15],
                "tipoprov": ["S", 40, "O", 15],
            }
        }
        result = format_facets(facet_counts, 15432)
        assert "15432 totali" in result
        assert "contratti (45)" in result
        assert "III (30)" in result  # szdec mapped
        assert "SS.UU. (8)" in result  # SU mapped
        assert "sentenza (40)" in result  # tipoprov mapped
        assert "ordinanza (15)" in result

    def test_empty_facets(self):
        result = format_facets({}, 0)
        assert result == ""

    def test_empty_facet_fields(self):
        result = format_facets({"facet_fields": {}}, 100)
        assert result == ""

    def test_partial_facets(self):
        facet_counts = {
            "facet_fields": {
                "materia": ["contratti", 10],
            }
        }
        result = format_facets(facet_counts, 10)
        assert "Materia" in result
        assert "contratti (10)" in result
        assert "Sezione" not in result  # szdec not present

    def test_section_mapping(self):
        facet_counts = {
            "facet_fields": {
                "szdec": ["L", 5, "T", 3, "U", 2],
            }
        }
        result = format_facets(facet_counts, 10)
        assert "lav. (5)" in result
        assert "trib. (3)" in result
        assert "sez. un. (2)" in result

    def test_tipoprov_mapping(self):
        facet_counts = {
            "facet_fields": {
                "tipoprov": ["D", 7],
            }
        }
        result = format_facets(facet_counts, 7)
        assert "decreto (7)" in result


# ---------------------------------------------------------------------------
# Score filtering
# ---------------------------------------------------------------------------

class TestScoreFiltering:
    def test_basic_threshold(self):
        docs = [
            {"id": "1", "score": 10.0},
            {"id": "2", "score": 8.0},
            {"id": "3", "score": 1.5},  # 15% of max, below 20%
        ]
        filtered, dropped = _filter_by_score(docs)
        assert len(filtered) == 2
        assert dropped == 1
        assert all(d["id"] in ("1", "2") for d in filtered)

    def test_all_above_threshold(self):
        docs = [
            {"id": "1", "score": 10.0},
            {"id": "2", "score": 5.0},
            {"id": "3", "score": 3.0},
        ]
        filtered, dropped = _filter_by_score(docs)
        assert len(filtered) == 3
        assert dropped == 0

    def test_no_score_passthrough(self):
        docs = [{"id": "1"}, {"id": "2"}]
        filtered, dropped = _filter_by_score(docs)
        assert len(filtered) == 2
        assert dropped == 0

    def test_empty_list(self):
        filtered, dropped = _filter_by_score([])
        assert filtered == []
        assert dropped == 0

    def test_zero_max_score(self):
        docs = [{"id": "1", "score": 0.0}]
        filtered, dropped = _filter_by_score(docs)
        assert len(filtered) == 1
        assert dropped == 0

    def test_exact_threshold(self):
        """Score exactly at 20% of max should be kept."""
        docs = [
            {"id": "1", "score": 10.0},
            {"id": "2", "score": 2.0},  # exactly 20%
        ]
        filtered, dropped = _filter_by_score(docs)
        assert len(filtered) == 2
        assert dropped == 0


# ---------------------------------------------------------------------------
# Modalità esplora
# ---------------------------------------------------------------------------

class TestModalitaEsplora:
    @pytest.mark.asyncio
    async def test_returns_facets_no_docs(self):
        solr_resp = {
            "responseHeader": {"status": 0},
            "response": {"numFound": 15000, "start": 0, "docs": []},
            "facet_counts": {
                "facet_fields": {
                    "materia": ["contratti", 500, "resp. civile", 300],
                    "szdec": ["3", 200],
                    "anno": ["2024", 400],
                    "tipoprov": ["S", 600, "O", 200],
                }
            },
        }
        mock_client = _mock_httpx_client(solr_resp=solr_resp)
        with patch("src.lib.italgiure.client.httpx.AsyncClient", return_value=mock_client):
            result = await _cerca_giurisprudenza_impl("responsabilità medica", modalita="esplora")
        assert "Esplorazione" in result
        assert "15000" in result
        assert "Suggerimento" in result
        assert "contratti" in result

    @pytest.mark.asyncio
    async def test_esplora_no_results(self):
        solr_resp = _make_solr_response([], num_found=0)
        mock_client = _mock_httpx_client(solr_resp=solr_resp)
        with patch("src.lib.italgiure.client.httpx.AsyncClient", return_value=mock_client):
            result = await _cerca_giurisprudenza_impl("xyz nessun risultato", modalita="esplora")
        assert "Nessuna" in result

    @pytest.mark.asyncio
    async def test_esplora_error(self):
        async def raise_error(*args, **kwargs):
            raise Exception("timeout")

        mock_client = AsyncMock()
        mock_client.get = raise_error
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("src.lib.italgiure.client.httpx.AsyncClient", return_value=mock_client):
            result = await _cerca_giurisprudenza_impl("test", modalita="esplora")
        assert "Errore" in result


# ---------------------------------------------------------------------------
# Auto-refinement
# ---------------------------------------------------------------------------

class TestAutoRefinement:
    def _make_faceted_response(self, docs, num_found):
        return {
            "responseHeader": {"status": 0},
            "response": {"numFound": num_found, "start": 0, "docs": docs},
            "highlighting": {},
            "facet_counts": {
                "facet_fields": {
                    "materia": ["contratti", num_found],
                    "szdec": ["3", num_found],
                    "anno": ["2024", num_found],
                    "tipoprov": ["S", num_found],
                }
            },
        }

    @pytest.mark.asyncio
    async def test_triggers_when_above_threshold(self):
        """When numFound > 50, auto-refinement should be attempted."""
        call_count = 0

        async def mock_get(url, **kwargs):
            resp = AsyncMock()
            resp.raise_for_status = MagicMock()
            return resp

        async def mock_post(url, content=None, **kwargs):
            nonlocal call_count
            call_count += 1
            resp = AsyncMock()
            resp.raise_for_status = MagicMock()
            if call_count == 1:
                # First call: too many results
                resp.json = MagicMock(return_value=self._make_faceted_response(
                    [_civile_doc()], 15000
                ))
            elif call_count == 2:
                # Second call (first refinement step mm=100%): success
                resp.json = MagicMock(return_value=self._make_faceted_response(
                    [_civile_doc()], 30
                ))
            else:
                resp.json = MagicMock(return_value=self._make_faceted_response([], 0))
            return resp

        mock_client = AsyncMock()
        mock_client.get = mock_get
        mock_client.post = mock_post
        mock_client.aclose = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("src.lib.italgiure.client.httpx.AsyncClient", return_value=mock_client):
            result = await _cerca_giurisprudenza_impl("responsabilità medica")

        assert result.success
        assert "Raffinamento automatico" in result.results_text
        assert "15000" in result.results_text
        assert "30" in result.results_text

    @pytest.mark.asyncio
    async def test_no_trigger_below_threshold(self):
        """When numFound <= 50, no auto-refinement."""
        doc = _civile_doc()
        doc["score"] = 10.0
        solr_resp = {
            "responseHeader": {"status": 0},
            "response": {"numFound": 30, "start": 0, "docs": [doc]},
            "highlighting": {},
            "facet_counts": {"facet_fields": {}},
        }
        mock_client = _mock_httpx_client(solr_resp=solr_resp)
        with patch("src.lib.italgiure.client.httpx.AsyncClient", return_value=mock_client):
            result = await _cerca_giurisprudenza_impl("test specifico")
        assert result.success
        assert "Raffinamento" not in result.results_text
        assert "Trovate 30" in result.results_text

    @pytest.mark.asyncio
    async def test_no_trigger_with_explicit_filters(self):
        """Auto-refinement should not trigger when user already applied filters."""
        call_count = 0

        async def mock_get(url, **kwargs):
            resp = AsyncMock()
            resp.raise_for_status = MagicMock()
            return resp

        async def mock_post(url, content=None, **kwargs):
            nonlocal call_count
            call_count += 1
            resp = AsyncMock()
            resp.raise_for_status = MagicMock()
            doc = _civile_doc()
            doc["score"] = 10.0
            resp.json = MagicMock(return_value={
                "responseHeader": {"status": 0},
                "response": {"numFound": 200, "start": 0, "docs": [doc]},
                "highlighting": {},
                "facet_counts": {"facet_fields": {"materia": ["contratti", 200]}},
            })
            return resp

        mock_client = AsyncMock()
        mock_client.get = mock_get
        mock_client.post = mock_post
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("src.lib.italgiure.client.httpx.AsyncClient", return_value=mock_client):
            result = await _cerca_giurisprudenza_impl("test", materia="contratti")

        # Only 1 POST (no refinement calls)
        assert call_count == 1
        assert "Raffinamento" not in result.results_text

    @pytest.mark.asyncio
    async def test_early_exit_on_success(self):
        """Refinement should stop at the first step that works."""
        call_count = 0

        async def mock_get(url, **kwargs):
            resp = AsyncMock()
            resp.raise_for_status = MagicMock()
            return resp

        async def mock_post(url, content=None, **kwargs):
            nonlocal call_count
            call_count += 1
            resp = AsyncMock()
            resp.raise_for_status = MagicMock()
            if call_count == 1:
                resp.json = MagicMock(return_value=self._make_faceted_response(
                    [_civile_doc()], 5000
                ))
            else:
                # First refinement step succeeds
                resp.json = MagicMock(return_value=self._make_faceted_response(
                    [_civile_doc()], 20
                ))
            return resp

        mock_client = AsyncMock()
        mock_client.get = mock_get
        mock_client.post = mock_post
        mock_client.aclose = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("src.lib.italgiure.client.httpx.AsyncClient", return_value=mock_client):
            result = await _cerca_giurisprudenza_impl("test generico")

        assert result.success
        assert "Raffinamento automatico" in result.results_text
        # 1 initial + 1 homepage + 1 successful refinement = max 3 posts
        # (homepage is a GET, so only 2 POSTs expected)
        assert call_count <= 3

    @pytest.mark.asyncio
    async def test_fallback_to_best_when_no_step_below_threshold(self):
        """When no step gets below threshold, use the step with fewest results."""
        call_count = 0

        async def mock_get(url, **kwargs):
            resp = AsyncMock()
            resp.raise_for_status = MagicMock()
            return resp

        async def mock_post(url, content=None, **kwargs):
            nonlocal call_count
            call_count += 1
            resp = AsyncMock()
            resp.raise_for_status = MagicMock()
            if call_count == 1:
                resp.json = MagicMock(return_value=self._make_faceted_response(
                    [_civile_doc()], 10000
                ))
            elif call_count == 2:
                resp.json = MagicMock(return_value=self._make_faceted_response(
                    [_civile_doc()], 500
                ))
            elif call_count == 3:
                resp.json = MagicMock(return_value=self._make_faceted_response(
                    [_civile_doc()], 200  # Best result
                ))
            elif call_count == 4:
                resp.json = MagicMock(return_value=self._make_faceted_response(
                    [_civile_doc()], 300
                ))
            else:
                resp.json = MagicMock(return_value=self._make_faceted_response([], 0))
            return resp

        mock_client = AsyncMock()
        mock_client.get = mock_get
        mock_client.post = mock_post
        mock_client.aclose = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("src.lib.italgiure.client.httpx.AsyncClient", return_value=mock_client):
            result = await _cerca_giurisprudenza_impl("test ampio")

        assert result.success
        assert "Raffinamento automatico" in result.results_text
        assert "200" in result.results_text  # Should use the best (200)


# ---------------------------------------------------------------------------
# cerca_giurisprudenza enhanced — campo + modalita + score e2e
# ---------------------------------------------------------------------------

class TestCercaGiurisprudenzaEnhanced:
    @pytest.mark.asyncio
    async def test_campo_dispositivo_passed(self):
        mock_client, captured = _capturing_mock_client()
        with patch("src.lib.italgiure.client.httpx.AsyncClient", return_value=mock_client):
            await _cerca_giurisprudenza_impl("test", campo="dispositivo")
        body = captured.get("body", "")
        # qf should only have ocrdis, not ocr
        assert "ocrdis" in body
        # In dispositivo mode, qf=ocrdis^1 (no ocr^1)
        assert "qf=ocrdis" in body

    @pytest.mark.asyncio
    async def test_backward_compat_defaults(self):
        """Default campo="tutto" and modalita="cerca" produce same output as before."""
        doc = _civile_doc()
        doc["score"] = 10.0
        solr_resp = {
            "responseHeader": {"status": 0},
            "response": {"numFound": 1, "start": 0, "docs": [doc]},
            "highlighting": {},
            "facet_counts": {"facet_fields": {}},
        }
        mock_client = _mock_httpx_client(solr_resp=solr_resp)
        with patch("src.lib.italgiure.client.httpx.AsyncClient", return_value=mock_client):
            result = await _cerca_giurisprudenza_impl("test")
        assert result.success
        assert "Trovate" in result.results_text
        assert "Cass. civ." in result.results_text

    @pytest.mark.asyncio
    async def test_score_filtering_applied(self):
        """Docs with low scores should be filtered out."""
        docs = [
            {**_civile_doc("1001", "2024"), "score": 50.0, "id": "doc1"},
            {**_civile_doc("1002", "2024"), "score": 40.0, "id": "doc2"},
            {**_civile_doc("1003", "2024"), "score": 1.0, "id": "doc3"},  # Below threshold
        ]
        solr_resp = {
            "responseHeader": {"status": 0},
            "response": {"numFound": 3, "start": 0, "docs": docs},
            "highlighting": {},
            "facet_counts": {"facet_fields": {}},
        }
        mock_client = _mock_httpx_client(solr_resp=solr_resp)
        with patch("src.lib.italgiure.client.httpx.AsyncClient", return_value=mock_client):
            result = await _cerca_giurisprudenza_impl("test")
        assert result.success
        assert "2 ad alta rilevanza" in result.results_text
        assert "1001" in result.results_text
        assert "1002" in result.results_text

    @pytest.mark.asyncio
    async def test_facets_shown_when_many_results(self):
        """Facets should appear in output when numFound > 50."""
        doc = _civile_doc()
        doc["score"] = 10.0
        solr_resp = {
            "responseHeader": {"status": 0},
            "response": {"numFound": 200, "start": 0, "docs": [doc]},
            "highlighting": {},
            "facet_counts": {
                "facet_fields": {
                    "materia": ["contratti", 100],
                    "szdec": ["3", 50],
                    "anno": ["2024", 80],
                    "tipoprov": ["S", 120],
                }
            },
        }
        mock_client = _mock_httpx_client(solr_resp=solr_resp)
        with patch("src.lib.italgiure.client.httpx.AsyncClient", return_value=mock_client):
            # Use explicit filter to avoid auto-refinement
            result = await _cerca_giurisprudenza_impl("test", materia="contratti")
        assert result.success
        assert "Distribuzione risultati" in result.results_text
        assert "Suggerimento" in result.results_text

    @pytest.mark.asyncio
    async def test_facets_not_shown_when_few_results(self):
        """Facets should not appear when numFound <= 50."""
        doc = _civile_doc()
        doc["score"] = 10.0
        solr_resp = {
            "responseHeader": {"status": 0},
            "response": {"numFound": 10, "start": 0, "docs": [doc]},
            "highlighting": {},
            "facet_counts": {"facet_fields": {"materia": ["contratti", 10]}},
        }
        mock_client = _mock_httpx_client(solr_resp=solr_resp)
        with patch("src.lib.italgiure.client.httpx.AsyncClient", return_value=mock_client):
            result = await _cerca_giurisprudenza_impl("test specifico")
        assert result.success
        assert "Distribuzione" not in result.results_text

    @pytest.mark.asyncio
    async def test_include_facets_in_params(self):
        mock_client, captured = _capturing_mock_client()
        with patch("src.lib.italgiure.client.httpx.AsyncClient", return_value=mock_client):
            await _cerca_giurisprudenza_impl("test")
        body = captured.get("body", "")
        assert "facet=true" in body


# ---------------------------------------------------------------------------
# _parse_articolo_riferimento
# ---------------------------------------------------------------------------

class TestParseArticoloRiferimento:
    def test_codice_civile(self):
        art, atto = _parse_articolo_riferimento("art. 2043 c.c.")
        assert art == "2043"
        assert atto == "c.c."

    def test_dlgs_number(self):
        art, atto = _parse_articolo_riferimento("art. 6 D.Lgs. 231/2001")
        assert art == "6"
        assert atto == "D.Lgs. 231/2001"

    def test_codice_procedura_civile(self):
        art, atto = _parse_articolo_riferimento("art. 132 c.p.c.")
        assert art == "132"
        assert atto == "c.p.c."

    def test_no_art_prefix_returns_empty_article(self):
        art, atto = _parse_articolo_riferimento("codice civile")
        assert art == ""
        assert atto == "codice civile"

    def test_articolo_extended(self):
        art, atto = _parse_articolo_riferimento("art. 2-ter D.Lgs. 196/2003")
        assert art == "2-ter"
        assert atto == "D.Lgs. 196/2003"


# ---------------------------------------------------------------------------
# _giurisprudenza_articolo_impl
# ---------------------------------------------------------------------------

def _make_massima(autorita: str, numero: str | None, anno: str | None, testo: str) -> "object":
    from src.lib.brocardi.client import Massima
    return Massima(autorita=autorita, numero=numero, anno=anno, testo=testo)


def _make_brocardi_result(massime: list) -> "object":
    from src.lib.brocardi.client import BrocardiResult
    return BrocardiResult(url="https://brocardi.it/codice-civile/art2043.html", massime=massime)


class TestGiurisprudenzaArticoloImpl:

    @pytest.mark.asyncio
    async def test_happy_path_brocardi_plus_italgiure(self):
        """Brocardi returns 2 massime; one Cassazione with number → direct lookup + text search."""
        m_cass = _make_massima("Cass. civ.", "12345", "2023", "Il danno ingiusto richiede la prova del nesso causale.")
        m_other = _make_massima("Trib. Milano", None, None, "Responsabilità extracontrattuale art 2043 cc.")
        brocardi_result = _make_brocardi_result([m_cass, m_other])

        doc = _civile_doc(num="12345", anno="2023")
        solr_resp = _make_solr_response([doc], num_found=1)
        mock_client = _mock_httpx_client(solr_resp=solr_resp)

        with (
            patch("src.tools.italgiure.fetch_brocardi", return_value=brocardi_result),
            patch("src.tools.italgiure.resolve_atto", return_value={"tipo_atto": "codice civile", "numero_atto": ""}),
            patch("src.lib.italgiure.client.httpx.AsyncClient", return_value=mock_client),
        ):
            result = await _giurisprudenza_articolo_impl("art. 2043 c.c.", max_risultati=3)

        assert result.success
        assert "Brocardi" in result.results_text
        assert "2 massime" in result.results_text

    @pytest.mark.asyncio
    async def test_brocardi_fails_falls_back_to_norma_search(self):
        """When fetch_brocardi raises an exception, fall back to _giurisprudenza_su_norma_impl."""
        doc = _civile_doc()
        solr_resp = _make_solr_response([doc], num_found=1)
        mock_client = _mock_httpx_client(solr_resp=solr_resp)

        with (
            patch("src.tools.italgiure.fetch_brocardi", side_effect=Exception("timeout")),
            patch("src.tools.italgiure.resolve_atto", return_value={"tipo_atto": "codice civile", "numero_atto": ""}),
            patch("src.lib.italgiure.client.httpx.AsyncClient", return_value=mock_client),
        ):
            result = await _giurisprudenza_articolo_impl("art. 2043 c.c.")

        assert result.success
        assert result.source == "italgiure"

    @pytest.mark.asyncio
    async def test_brocardi_empty_massime_falls_back(self):
        """BrocardiResult with empty massime list falls back to _giurisprudenza_su_norma_impl."""
        brocardi_result = _make_brocardi_result([])
        doc = _civile_doc()
        solr_resp = _make_solr_response([doc], num_found=2)
        mock_client = _mock_httpx_client(solr_resp=solr_resp)

        with (
            patch("src.tools.italgiure.fetch_brocardi", return_value=brocardi_result),
            patch("src.tools.italgiure.resolve_atto", return_value={"tipo_atto": "codice civile", "numero_atto": ""}),
            patch("src.lib.italgiure.client.httpx.AsyncClient", return_value=mock_client),
        ):
            result = await _giurisprudenza_articolo_impl("art. 2043 c.c.")

        assert result.success
        assert result.source == "italgiure"

    @pytest.mark.asyncio
    async def test_brocardi_error_field_falls_back(self):
        """BrocardiResult with error field set falls back to _giurisprudenza_su_norma_impl."""
        from src.lib.brocardi.client import BrocardiResult
        brocardi_result = BrocardiResult(error="articolo non trovato")
        doc = _civile_doc()
        solr_resp = _make_solr_response([doc], num_found=1)
        mock_client = _mock_httpx_client(solr_resp=solr_resp)

        with (
            patch("src.tools.italgiure.fetch_brocardi", return_value=brocardi_result),
            patch("src.tools.italgiure.resolve_atto", return_value={"tipo_atto": "codice civile", "numero_atto": ""}),
            patch("src.lib.italgiure.client.httpx.AsyncClient", return_value=mock_client),
        ):
            result = await _giurisprudenza_articolo_impl("art. 2043 c.c.")

        assert result.source == "italgiure"

    @pytest.mark.asyncio
    async def test_italgiure_down_returns_source_down(self):
        """When Italgiure is unreachable, all lookups fail and no_results is returned."""
        m_cass = _make_massima("Cass. civ.", "99999", "2022", "Principio di diritto test.")
        brocardi_result = _make_brocardi_result([m_cass])

        mock_client = _mock_httpx_client()

        async def failing_post(url, **kwargs):
            raise Exception("connection refused")

        mock_client.post = failing_post

        with (
            patch("src.tools.italgiure.fetch_brocardi", return_value=brocardi_result),
            patch("src.tools.italgiure.resolve_atto", return_value={"tipo_atto": "codice civile", "numero_atto": ""}),
            patch("src.lib.italgiure.client.httpx.AsyncClient", return_value=mock_client),
        ):
            result = await _giurisprudenza_articolo_impl("art. 2043 c.c.")

        assert not result.success

    @pytest.mark.asyncio
    async def test_unresolvable_act_falls_back_to_norma(self):
        """When resolve_atto returns None, falls back to _giurisprudenza_su_norma_impl."""
        doc = _civile_doc()
        solr_resp = _make_solr_response([doc], num_found=1)
        mock_client = _mock_httpx_client(solr_resp=solr_resp)

        with (
            patch("src.lib.italgiure.client.httpx.AsyncClient", return_value=mock_client),
            patch("src.tools.italgiure.resolve_atto", return_value=None),
        ):
            result = await _giurisprudenza_articolo_impl("art. 2043 c.c.")

        assert result.source == "italgiure"

    @pytest.mark.asyncio
    async def test_no_article_prefix_falls_back(self):
        """Reference without 'art.' prefix: resolve_atto path used with empty article → fallback."""
        doc = _civile_doc()
        solr_resp = _make_solr_response([doc], num_found=1)
        mock_client = _mock_httpx_client(solr_resp=solr_resp)

        with patch("src.lib.italgiure.client.httpx.AsyncClient", return_value=mock_client):
            result = await _giurisprudenza_articolo_impl("danno biologico")

        assert result.source == "italgiure"

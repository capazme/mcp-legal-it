"""Unit tests for parliamentary sources client and tools (dati.senato.it / dati.camera.it).

Tests run against mocked httpx responses — no real network calls. The JSON
fixtures in tests/fixtures/parlamento/ are verbatim captures of the real
Virtuoso endpoints (2026-08-25), per the lesson of issue #32 (invented
fixtures did not catch the giustizia-amministrativa breakage).

Endpoint quirks the tests pin down:
- Senato accepts ONLY GET (POST gets a 403 WAF page) — test_uses_get_not_post
- the Senato WAF also blocks bif:contains expressions with quoted 'or'/'and'
  operators (SQL-injection heuristics): title search MUST use plain SPARQL
  FILTER(CONTAINS(...)) with &&/|| — test_no_bif_contains_ever
- literals are typed xsd:string; plain-literal matching silently returns 0 rows
- dataLegge carries the sentinel 2100-01-01 for pending constitutional laws
"""

import copy
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.lib.parlamento.client import (
    LEGISLATURA_CORRENTE,
    STATI_PENDENTI,
    CameraIter,
    DdlFase,
    _build_camera_query,
    _build_search_query,
    _parse_camera_iter,
    _parse_fasi,
    _sanitize_phrase,
    camera_scheda_url,
    _title_filter_expr,
    format_fase,
    format_iter,
    parse_atto_input,
    scheda_senato_url,
)
from src.lib._result import SearchResult
from src.tools.parlamento import (
    _cerca_ddl_impl,
    _ddl_su_norma_impl,
    _iter_ddl_impl,
    _norma_search_groups,
)

_FIXTURES = Path(__file__).parents[1] / "fixtures" / "parlamento"

_SENATO_SEARCH = json.loads((_FIXTURES / "senato_search.json").read_text())
_SENATO_ITER = json.loads((_FIXTURES / "senato_iter.json").read_text())
_CAMERA_ATTO = json.loads((_FIXTURES / "camera_atto.json").read_text())

_EMPTY = {"head": {"vars": []}, "results": {"bindings": []}}


def _make_client(get_json=None, post_json=None, get_exc=None, post_exc=None):
    """Mock httpx.AsyncClient: Senato calls use GET, Camera calls use POST."""
    client = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)

    def _resp(payload):
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json = MagicMock(return_value=payload)
        return resp

    if get_exc is not None:
        client.get = AsyncMock(side_effect=get_exc)
    else:
        client.get = AsyncMock(return_value=_resp(get_json if get_json is not None else _EMPTY))
    if post_exc is not None:
        client.post = AsyncMock(side_effect=post_exc)
    else:
        client.post = AsyncMock(return_value=_resp(post_json if post_json is not None else _EMPTY))
    return client


# ---------------------------------------------------------------------------
# Tests: query building
# ---------------------------------------------------------------------------

class TestSanitizePhrase:
    def test_strips_double_quotes_and_backslashes(self):
        assert _sanitize_phrase('intelligenza "artificiale" \\x') == "intelligenza artificiale x"

    def test_preserves_apostrophes(self):
        """SPARQL double-quoted literals admit ' — stripping it breaks matching
        against real values like "all'esame assemblea" or "dell'ambiente"."""
        assert _sanitize_phrase("codice dell'ambiente") == "codice dell'ambiente"

    def test_collapses_whitespace(self):
        assert _sanitize_phrase("  codice   civile \n") == "codice civile"


class TestTitleFilterExpr:
    def test_single_phrase(self):
        expr = _title_filter_expr([["intelligenza artificiale"]])
        assert expr == '(CONTAINS(LCASE(STR(?titolo)), "intelligenza artificiale"))'

    def test_and_group(self):
        expr = _title_filter_expr([["196", "2003"]])
        assert expr == '(CONTAINS(LCASE(STR(?titolo)), "196") && CONTAINS(LCASE(STR(?titolo)), "2003"))'

    def test_or_of_groups(self):
        expr = _title_filter_expr([["300", "1970"], ["statuto dei lavoratori"]])
        assert " || " in expr
        assert expr.index('"300"') < expr.index('"statuto dei lavoratori"')

    def test_terms_are_lowercased(self):
        expr = _title_filter_expr([["Codice Civile"]])
        assert '"codice civile"' in expr

    def test_apostrophe_terms_survive(self):
        expr = _title_filter_expr([["codice dell'ambiente"]])
        assert '"codice dell\'ambiente"' in expr

    def test_terms_without_alphanumerics_dropped(self):
        """A bare "-" in a CONTAINS triggers the Senato WAF (403, observed
        live): terms with no alphanumeric content are discarded upstream."""
        assert _title_filter_expr([["-"]]) == ""
        assert _title_filter_expr([["covid-19"]]) != ""


class TestBuildSearchQuery:
    def test_basic_shape(self):
        q = _build_search_query([["intelligenza artificiale"]], legislatura=19, limit=10)
        assert "PREFIX osr: <http://dati.senato.it/osr/>" in q
        assert "osr:legislatura 19" in q
        assert 'CONTAINS(LCASE(STR(?titolo)), "intelligenza artificiale")' in q
        assert "LIMIT 10" in q

    def test_no_bif_contains_ever(self):
        """The Senato WAF 403s bif:contains expressions with quoted or/and
        operators (SQLi heuristics): title search must stay on FILTER CONTAINS."""
        q = _build_search_query([["codice della strada"], ["285", "1992"]], legislatura=19)
        assert "bif:contains" not in q
        assert "' or '" not in q and "' and '" not in q

    def test_stato_filter_is_typed_string(self):
        q = _build_search_query([["x"]], legislatura=19, stato="esame in comm.")
        assert '"esame in comm."^^xsd:string' in q

    def test_stato_filter_keeps_apostrophe(self):
        """"all'esame assemblea" is a real statoDdl value: stripping the
        apostrophe would make the exact-match filter silently return 0 rows."""
        q = _build_search_query([["x"]], legislatura=19, stato="all'esame assemblea")
        assert '"all\'esame assemblea"^^xsd:string' in q

    def test_all_junk_terms_raise_instead_of_unfiltered_dump(self):
        """A query whose terms all vanish in sanitisation must NOT degrade to
        an unfiltered listing presented as search results. The exception is a
        dedicated type: a bare ValueError would be indistinguishable from
        json.JSONDecodeError (its subclass) raised by a broken response."""
        from src.lib.parlamento.client import NoValidSearchTerms

        with pytest.raises(NoValidSearchTerms):
            _build_search_query([['"']], legislatura=19)

    def test_ramo_filter_is_typed_string(self):
        q = _build_search_query([["x"]], legislatura=19, ramo="S")
        assert '"S"^^xsd:string' in q

    def test_solo_pendenti_filter(self):
        q = _build_search_query([["x"]], legislatura=19, solo_pendenti=True)
        assert "FILTER(?stato IN (" in q
        assert '"esame in comm."^^xsd:string' in q

    def test_no_stato_filter_by_default(self):
        q = _build_search_query([["x"]], legislatura=19)
        assert "FILTER(?stato IN (" not in q

    def test_no_keywords_means_no_title_filter(self):
        q = _build_search_query([], legislatura=19)
        assert "CONTAINS(LCASE" not in q


class TestBuildIterQuery:
    def test_fase_branch_uses_typed_string_and_legislatura(self):
        from src.lib.parlamento.client import _build_iter_query

        q = _build_iter_query(fase="S.1939", legislatura=19)
        assert 'osr:fase "S.1939"^^xsd:string' in q
        assert "osr:legislatura 19" in q
        assert "?leg" in q  # legislatura read from the data, not echoed from input

    def test_idddl_branch_uses_bare_integer(self):
        """idDdl is xsd:integer in the store: quoting it ("55442"^^xsd:string)
        would silently return zero rows."""
        from src.lib.parlamento.client import _build_iter_query

        q = _build_iter_query(id_ddl="55442")
        assert "osr:idDdl 55442 ." in q
        assert '"55442"' not in q
        assert "?leg" in q


class TestParseAttoInput:
    def test_senato_fase(self):
        assert parse_atto_input("S.1939") == ("fase", "S.1939")

    def test_lowercase_with_space(self):
        assert parse_atto_input("s 1939") == ("fase", "S.1939")

    def test_as_prefix(self):
        assert parse_atto_input("AS 1939") == ("fase", "S.1939")

    def test_camera_fase(self):
        assert parse_atto_input("AC 3053") == ("fase", "C.3053")

    def test_camera_dotted(self):
        assert parse_atto_input("c.3053") == ("fase", "C.3053")

    def test_bare_digits_is_idddl(self):
        assert parse_atto_input("55442") == ("id_ddl", "55442")

    def test_navette_suffix(self):
        """Third readings carry a suffix in the real data: S.562-B, C.813-B."""
        assert parse_atto_input("S.562-B") == ("fase", "S.562-B")

    def test_single_letter_suffix_is_uppercased(self):
        """The navette marker is uppercase in the data: -b normalises to -B."""
        assert parse_atto_input("c 813-b") == ("fase", "C.813-B")

    def test_stralcio_suffix_stays_lowercase(self):
        """Stralci carry lowercase multi-letter suffixes in the data
        (S.926-bis, S.1689-ter, C.2112-quinquies — real leg-19 values):
        uppercasing them makes the exact typed-literal match return 0 rows."""
        assert parse_atto_input("S.926-bis") == ("fase", "S.926-bis")

    def test_multi_letter_suffix_normalised_to_lowercase(self):
        assert parse_atto_input("s.926-BIS") == ("fase", "S.926-bis")

    def test_unified_text_numbering(self):
        """Unified texts merge the numbers: S.93-338-353-B (real leg-19 value)."""
        assert parse_atto_input("S.93-338-353-B") == ("fase", "S.93-338-353-B")

    def test_garbage_raises(self):
        with pytest.raises(ValueError):
            parse_atto_input("pippo")


# ---------------------------------------------------------------------------
# Tests: Senato transport — the WAF regression guard
# ---------------------------------------------------------------------------

class TestExecuteSenato:
    async def test_uses_get_not_post(self):
        """dati.senato.it rejects POST with a 403 WAF page: the client MUST use GET."""
        from src.lib.parlamento.client import _execute_sparql_senato

        client = _make_client(get_json=_SENATO_SEARCH)
        with patch("src.lib.parlamento.client.httpx.AsyncClient", return_value=client):
            bindings = await _execute_sparql_senato("SELECT ?s WHERE { ?s ?p ?o }")

        assert client.get.await_count == 1
        client.post.assert_not_awaited()
        assert len(bindings) == 2

    async def test_transport_error_propagates(self):
        from src.lib.parlamento.client import _execute_sparql_senato

        client = _make_client(get_exc=httpx.RequestError("timeout"))
        with patch("src.lib.parlamento.client.httpx.AsyncClient", return_value=client):
            with pytest.raises(httpx.RequestError):
                await _execute_sparql_senato("SELECT ?s WHERE { ?s ?p ?o }")


# ---------------------------------------------------------------------------
# Tests: parsing Senato bindings (real fixture)
# ---------------------------------------------------------------------------

class TestParseFasi:
    def test_two_results(self):
        fasi = _parse_fasi(_SENATO_SEARCH["results"]["bindings"], legislatura=19)
        assert len(fasi) == 2

    def test_field_mapping(self):
        fase = _parse_fasi(_SENATO_SEARCH["results"]["bindings"], legislatura=19)[0]
        assert fase.fase == "C.2936"
        assert fase.ramo == "C"
        assert fase.id_ddl == "55393"
        assert fase.id_fase == "60151"  # last segment of http://dati.senato.it/ddl/60151
        assert fase.stato == "assegnato (no esame)"
        assert fase.data_stato == "2026-08-06"
        assert fase.data_presentazione == "2026-05-15"
        assert "intelligenza artificiale" in fase.titolo
        assert fase.legislatura == 19

    def test_iter_fixture_carries_legge(self):
        fasi = _parse_fasi(_SENATO_ITER["results"]["bindings"], legislatura=19)
        assert fasi[0].fase == "S.1939"
        assert fasi[0].numero_legge == "145"
        assert fasi[0].data_legge == "2026-08-07"
        assert fasi[1].fase == "C.3053"
        assert fasi[1].stato == "appr. definit. Legge"

    def test_sentinel_data_legge_blanked(self):
        """Constitutional laws pending referendum carry dataLegge=2100-01-01."""
        binding = copy.deepcopy(_SENATO_ITER["results"]["bindings"][0])
        binding["dataLegge"]["value"] = "2100-01-01"
        fase = _parse_fasi([binding], legislatura=19)[0]
        assert fase.data_legge == ""
        assert fase.numero_legge == "145"

    def test_missing_optionals_tolerated(self):
        binding = copy.deepcopy(_SENATO_SEARCH["results"]["bindings"][0])
        for key in ("iniziativa", "natura", "presTrasm", "dataPres", "prog"):
            binding.pop(key, None)
        fase = _parse_fasi([binding], legislatura=19)[0]
        assert fase.fase == "C.2936"
        assert fase.iniziativa == ""

    def test_legislatura_comes_from_data_when_present(self):
        """iter_ddl by idDdl has no legislature constraint: the official scheda
        links must be built from the data's legislature, never from the echoed
        parameter, or they point at the wrong (or missing) page."""
        binding = copy.deepcopy(_SENATO_SEARCH["results"]["bindings"][0])
        binding["leg"] = {"type": "typed-literal",
                          "datatype": "http://www.w3.org/2001/XMLSchema#integer",
                          "value": "18"}
        fase = _parse_fasi([binding], legislatura=19)[0]
        assert fase.legislatura == 18
        assert "/leg/18/" in scheda_senato_url(fase)

    def test_duplicate_bindings_deduped(self):
        """OPTIONAL fan-out can repeat rows (seen live on the Camera side):
        the same fase must not be listed twice nor inflate num_found."""
        binding = copy.deepcopy(_SENATO_SEARCH["results"]["bindings"][0])
        fasi = _parse_fasi([binding, copy.deepcopy(binding)], legislatura=19)
        assert len(fasi) == 1


class TestSchedaUrls:
    def test_senato_scheda(self):
        fase = _parse_fasi(_SENATO_SEARCH["results"]["bindings"], legislatura=19)[0]
        assert scheda_senato_url(fase) == "https://www.senato.it/leg/19/BGT/Schede/Ddliter/60151.htm"

    def test_camera_scheda(self):
        url = camera_scheda_url("3053", legislatura=19)
        assert url == (
            "https://www.camera.it/uri-res/N2Ls?"
            "urn:camera-it:parlamento:scheda.progetto.legge:camera;19.legislatura;3053"
        )


# ---------------------------------------------------------------------------
# Tests: formatting
# ---------------------------------------------------------------------------

class TestFormatFase:
    def test_contains_key_fields(self):
        fase = _parse_fasi(_SENATO_SEARCH["results"]["bindings"], legislatura=19)[0]
        text = format_fase(fase)
        assert "C.2936" in text
        assert "assegnato (no esame)" in text
        assert "2026-08-06" in text
        assert "Ddliter/60151.htm" in text

    def test_camera_fase_gets_camera_link(self):
        fase = _parse_fasi(_SENATO_SEARCH["results"]["bindings"], legislatura=19)[0]
        text = format_fase(fase)
        assert "camera;19.legislatura;2936" in text


class TestFormatIter:
    def test_full_navette(self):
        fasi = _parse_fasi(_SENATO_ITER["results"]["bindings"], legislatura=19)
        text = format_iter(fasi, {})
        assert text.index("S.1939") < text.index("C.3053")
        assert "145" in text  # became law 145/2026
        assert "2026-08-07" in text

    def test_camera_details_included(self):
        fasi = _parse_fasi(_SENATO_ITER["results"]["bindings"], legislatura=19)
        camera = _parse_camera_iter(_CAMERA_ATTO["results"]["bindings"])
        text = format_iter(fasi, {"3053": camera})
        assert "In corso di esame in Commissione" in text
        assert "19PDL0209460.pdf" in text


# ---------------------------------------------------------------------------
# Tests: Camera parsing (real fixture — 24 rows of cartesian product)
# ---------------------------------------------------------------------------

class TestParseCameraIter:
    def test_timeline_deduped_and_sorted(self):
        it = _parse_camera_iter(_CAMERA_ATTO["results"]["bindings"])
        assert len(it.timeline) == 6
        dates = [d for d, _ in it.timeline]
        assert dates == sorted(dates)
        assert it.timeline[0][0] == "2026-07-30"  # YYYYMMDD normalised to ISO

    def test_pdfs_deduped(self):
        it = _parse_camera_iter(_CAMERA_ATTO["results"]["bindings"])
        assert len(it.pdf_urls) == 2

    def test_title_cleaned(self):
        it = _parse_camera_iter(_CAMERA_ATTO["results"]["bindings"])
        assert not it.titolo.startswith(" S. 1939")
        assert not it.titolo.startswith('"')
        assert "Conversione in legge" in it.titolo

    def test_empty_bindings_gives_none(self):
        assert _parse_camera_iter([]) is None

    def test_camera_query_filters_on_string_identifier(self):
        q = _build_camera_query("3053", legislatura=19)
        assert 'FILTER(STR(?id) = "3053")' in q
        assert "legislatura.rdf/repubblica_19" in q

    def test_camera_query_keeps_navette_suffix(self):
        """The Camera identifies third readings as "813-B" (verified live on
        ac19_813-B): stripping non-digits would query the FIRST reading."""
        q = _build_camera_query("813-B", legislatura=19)
        assert 'FILTER(STR(?id) = "813-B")' in q


# ---------------------------------------------------------------------------
# Tests: constants
# ---------------------------------------------------------------------------

class TestConstants:
    def test_legislatura_corrente(self):
        assert LEGISLATURA_CORRENTE == 19

    def test_stati_pendenti_are_the_live_states(self):
        assert "esame in comm." in STATI_PENDENTI
        assert "all'esame assemblea" in STATI_PENDENTI
        assert "approvato" not in STATI_PENDENTI
        assert "respinto" not in STATI_PENDENTI


# ---------------------------------------------------------------------------
# Tests: _norma_search_groups
# ---------------------------------------------------------------------------

class TestNormaSearchGroups:
    def test_numbered_act(self):
        groups, resolved = _norma_search_groups("d.lgs. 196/2003")
        assert ["196", "2003"] in groups
        assert resolved is not None

    def test_codice(self):
        groups, resolved = _norma_search_groups("codice civile")
        assert ["codice civile"] in groups
        assert resolved is not None

    def test_article_reference_stripped(self):
        groups, resolved = _norma_search_groups("art. 2043 c.c.")
        assert ["codice civile"] in groups

    def test_named_act_keeps_both_forms(self):
        groups, resolved = _norma_search_groups("statuto dei lavoratori")
        assert ["300", "1970"] in groups
        assert ["statuto dei lavoratori"] in groups

    def test_unresolved_falls_back_to_literal(self):
        groups, resolved = _norma_search_groups("atto fantasioso delle meraviglie")
        assert resolved is None
        assert groups == [["atto fantasioso delle meraviglie"]]


# ---------------------------------------------------------------------------
# Tests: _cerca_ddl_impl
# ---------------------------------------------------------------------------

class TestCercaDdlImpl:
    async def test_returns_results(self):
        client = _make_client(get_json=_SENATO_SEARCH)
        with patch("src.lib.parlamento.client.httpx.AsyncClient", return_value=client):
            result = await _cerca_ddl_impl("intelligenza artificiale")

        assert isinstance(result, SearchResult)
        assert result.success
        assert "C.2936" in result.results_text
        assert "assegnato (no esame)" in result.results_text

    async def test_empty_results(self):
        client = _make_client(get_json=_EMPTY)
        with patch("src.lib.parlamento.client.httpx.AsyncClient", return_value=client):
            result = await _cerca_ddl_impl("inesistente")

        assert not result.success
        assert result.error_type == "no_results"

    async def test_source_down(self):
        client = _make_client(get_exc=httpx.RequestError("timeout"))
        with patch("src.lib.parlamento.client.httpx.AsyncClient", return_value=client):
            result = await _cerca_ddl_impl("intelligenza artificiale")

        assert not result.success
        assert result.error_type == "source_down"

    async def test_empty_query_rejected(self):
        result = await _cerca_ddl_impl("")
        assert not result.success

    async def test_all_junk_query_is_no_results_without_network(self):
        """Terms that vanish in sanitisation must not reach the endpoint and
        must not come back as an unfiltered listing."""
        client = _make_client(get_json=_SENATO_SEARCH)
        with patch("src.lib.parlamento.client.httpx.AsyncClient", return_value=client):
            result = await _cerca_ddl_impl('"')

        assert not result.success
        assert result.error_type == "no_results"
        client.get.assert_not_awaited()

    async def test_html_body_on_200_is_source_down_not_no_results(self):
        """A 200 with an HTML error page (the senato.it WAF failure mode, and
        the exact shape of issue #32) raises JSONDecodeError — a ValueError
        subclass. It must surface as source_down, never as a false
        'no results' that reads like the absence of pending reforms."""
        client = _make_client(get_json=_SENATO_SEARCH)
        client.get.return_value.json = MagicMock(
            side_effect=json.JSONDecodeError("Expecting value", "<html>", 0)
        )
        with patch("src.lib.parlamento.client.httpx.AsyncClient", return_value=client):
            result = await _cerca_ddl_impl("intelligenza artificiale")

        assert not result.success
        assert result.error_type == "source_down"


# ---------------------------------------------------------------------------
# Tests: _iter_ddl_impl
# ---------------------------------------------------------------------------

class TestIterDdlImpl:
    async def test_full_navette_with_camera_enrichment(self):
        client = _make_client(get_json=_SENATO_ITER, post_json=_CAMERA_ATTO)
        with patch("src.lib.parlamento.client.httpx.AsyncClient", return_value=client):
            result = await _iter_ddl_impl("S.1939")

        assert result.success
        assert "S.1939" in result.results_text
        assert "C.3053" in result.results_text
        assert "145" in result.results_text
        assert "In corso di esame in Commissione" in result.results_text

    async def test_camera_failure_is_fail_open(self):
        """Camera enrichment is a bonus: its failure must not sink the iter."""
        client = _make_client(get_json=_SENATO_ITER, post_exc=httpx.RequestError("down"))
        with patch("src.lib.parlamento.client.httpx.AsyncClient", return_value=client):
            result = await _iter_ddl_impl("S.1939")

        assert result.success
        assert "C.3053" in result.results_text

    async def test_idddl_input(self):
        client = _make_client(get_json=_SENATO_ITER, post_json=_CAMERA_ATTO)
        with patch("src.lib.parlamento.client.httpx.AsyncClient", return_value=client):
            result = await _iter_ddl_impl("55442")

        assert result.success
        assert "S.1939" in result.results_text

    async def test_invalid_input_is_reported_without_network(self):
        result = await _iter_ddl_impl("pippo")
        assert not result.success
        assert "pippo" in result.to_str()

    async def test_not_found(self):
        client = _make_client(get_json=_EMPTY)
        with patch("src.lib.parlamento.client.httpx.AsyncClient", return_value=client):
            result = await _iter_ddl_impl("S.99999")

        assert not result.success
        assert result.error_type == "no_results"


# ---------------------------------------------------------------------------
# Tests: _ddl_su_norma_impl
# ---------------------------------------------------------------------------

class TestDdlSuNormaImpl:
    async def test_resolved_reference(self):
        client = _make_client(get_json=_SENATO_SEARCH)
        with patch("src.lib.parlamento.client.httpx.AsyncClient", return_value=client):
            result = await _ddl_su_norma_impl("codice civile")

        assert result.success
        assert "C.2936" in result.results_text
        # best-effort caveat: only titles are indexed
        assert "titol" in result.results_text.lower()

    async def test_unresolved_reference_still_searches(self):
        client = _make_client(get_json=_SENATO_SEARCH)
        with patch("src.lib.parlamento.client.httpx.AsyncClient", return_value=client):
            result = await _ddl_su_norma_impl("atto fantasioso delle meraviglie")

        assert result.success
        assert "non riconosciuto" in result.results_text.lower() or "letteral" in result.results_text.lower()

    async def test_empty_results(self):
        client = _make_client(get_json=_EMPTY)
        with patch("src.lib.parlamento.client.httpx.AsyncClient", return_value=client):
            result = await _ddl_su_norma_impl("codice civile")

        assert not result.success
        assert result.error_type == "no_results"

    async def test_html_body_on_200_is_source_down(self):
        client = _make_client(get_json=_SENATO_SEARCH)
        client.get.return_value.json = MagicMock(
            side_effect=json.JSONDecodeError("Expecting value", "<html>", 0)
        )
        with patch("src.lib.parlamento.client.httpx.AsyncClient", return_value=client):
            result = await _ddl_su_norma_impl("codice civile")

        assert not result.success
        assert result.error_type == "source_down"


# ---------------------------------------------------------------------------
# Live tests — guard-rail against the next endpoint/WAF reorganisation
# (lesson of issue #32). Run with: pytest -m live tests/unit/test_parlamento.py
# ---------------------------------------------------------------------------

@pytest.mark.live
class TestLiveEndpoints:
    async def test_senato_get_answers_with_bindings(self):
        from src.lib.parlamento.client import search_ddl

        fasi = await search_ddl([["intelligenza artificiale"]], legislatura=19, limit=2)
        assert fasi
        assert all(f.fase[0] in "SC" for f in fasi)

    async def test_senato_post_is_still_blocked(self):
        """The GET-only design rests on this: if POST starts working, the WAF
        changed and the transport choice deserves a fresh look."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                "https://dati.senato.it/sparql",
                data={"query": "SELECT ?s WHERE { ?s ?p ?o } LIMIT 1"},
            )
        assert resp.status_code != 200

    async def test_iter_live_navette(self):
        from src.lib.parlamento.client import fetch_iter

        fasi = await fetch_iter("fase", "S.1939", legislatura=19)
        assert len(fasi) >= 2
        assert any(f.numero_legge == "145" for f in fasi)
        assert all(f.legislatura == 19 for f in fasi)

    async def test_camera_live_enrichment(self):
        from src.lib.parlamento.client import fetch_camera_iter

        camera = await fetch_camera_iter("3053", legislatura=19)
        assert camera is not None
        assert camera.timeline
        assert camera.pdf_urls

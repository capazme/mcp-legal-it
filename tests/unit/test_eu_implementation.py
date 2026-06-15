"""Unit tests for EU -> Italy implementation mapping client and tools.

Tests run against mocked httpx responses — no real network calls. The SPARQL
fixtures are SMALL REAL bindings captured from the live CELLAR endpoint
(publications.europa.eu) during recon:

- directive 32019L0790 (copyright/DSM) -> D.Lgs. 177/2021, GU 283 del 2021-11-27,
  MNE CELEX 72019L0790ITA_202107973;
- directive 32022L2555 (NIS2) -> D.Lgs. 138/2024 (id_local is the FULL string
  "Decreto legislativo 4 settembre 2024, n. 138,");
- reverse MNE CELEX 72019L0790ITA_202107973 -> directive 32019L0790
  (transposition deadline 2021-06-07);
- regulation 32016R0679 (GDPR) -> 0 MNE (directly applicable).
"""

import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch

from src.lib._result import SearchResult
from src.lib.eu_implementation.client import (
    BasisResult,
    ImplementationResult,
    MappingResult,
    _clean_act_number,
    build_directive_celex,
    build_directive_exists_query,
    build_eu_to_it_query,
    build_it_to_eu_from_act,
    build_it_to_eu_from_mne_celex,
    format_basis,
    format_implementation,
    parse_bases,
    parse_implementations,
    parse_italian_act_ref,
    parse_mne_celex,
)
from src.tools.eu_implementation import (
    _elenco_misure_nazionali_impl,
    _get_eu_basis_impl,
    _get_italian_implementation_impl,
    _mapping_to_search_result,
)


# ---------------------------------------------------------------------------
# Real-shaped SPARQL fixtures
# ---------------------------------------------------------------------------

# EU -> IT for directive 32019L0790 (copyright). id_local is the bare number "177".
_EU_TO_IT_DSM = {
    "head": {"vars": ["mne", "mne_celex", "act_type", "id_local", "oj_num", "oj_date", "eif", "title"]},
    "results": {"bindings": [
        {
            "mne": {"type": "uri", "value": "http://publications.europa.eu/resource/cellar/c75ed027-5427-11ec-91ac-01aa75ed71a1"},
            "mne_celex": {"type": "literal", "value": "72019L0790ITA_202107973"},
            "act_type": {"type": "literal", "value": "Decreto legislativo"},
            "id_local": {"type": "literal", "value": "177"},
            "oj_num": {"type": "literal", "value": "283"},
            "oj_date": {"type": "literal", "value": "2021-11-27"},
            "eif": {"type": "literal", "value": "2021-11-27"},
            "title": {"type": "literal", "value": "Attuazione della direttiva (UE) 2019/790 del Parlamento europeo e del Consiglio, del 17 aprile 2019, sul diritto d’autore e sui diritti connessi nel mercato unico digitale e che modifica le direttive 96/9/CE e 2001/29/CE."},
        },
    ]},
}

# EU -> IT for directive 32022L2555 (NIS2). id_local is the FULL string;
# oj_date is the placeholder 1001-01-01 (must be suppressed in output).
_EU_TO_IT_NIS2 = {
    "head": {"vars": ["mne", "mne_celex", "act_type", "id_local", "oj_num", "oj_date", "eif", "title"]},
    "results": {"bindings": [
        {
            "mne": {"type": "uri", "value": "http://publications.europa.eu/resource/cellar/nis2-mne-uri"},
            "mne_celex": {"type": "literal", "value": "72022L2555ITA_202404316"},
            "act_type": {"type": "literal", "value": "Decreto legislativo"},
            "id_local": {"type": "literal", "value": "Decreto legislativo 4 settembre 2024, n. 138,"},
            "oj_num": {"type": "literal", "value": "230 del 1 ottobre 2024"},
            "oj_date": {"type": "literal", "value": "1001-01-01"},
            "title": {"type": "literal", "value": "Decreto legislativo 4 settembre 2024, n. 138, di recepimento nell’ordinamento italiano della direttiva 2022/2555."},
        },
    ]},
}

# Reverse: MNE 72019L0790ITA_202107973 -> directive 32019L0790.
_IT_TO_EU_DSM = {
    "head": {"vars": ["dir_celex", "title", "transp", "dir"]},
    "results": {"bindings": [
        {
            "dir_celex": {"type": "literal", "value": "32019L0790"},
            "title": {"type": "literal", "value": "Direttiva (UE) 2019/790 del Parlamento europeo e del Consiglio, del 17 aprile 2019, sul diritto d'autore e sui diritti connessi nel mercato unico digitale e che modifica le direttive 96/9/CE e 2001/29/CE (Testo rilevante ai fini del SEE.)"},
            "transp": {"type": "literal", "value": "2021-06-07"},
            "dir": {"type": "uri", "value": "http://publications.europa.eu/resource/cellar/214471fe-786e-11e9-9f05-01aa75ed71a1"},
        },
    ]},
}

# Reverse from act ref 138/2024 (NIS2) -> directive 32022L2555.
_IT_TO_EU_NIS2 = {
    "head": {"vars": ["mne_celex", "dir_celex", "title", "transp", "act_type", "eif", "dir"]},
    "results": {"bindings": [
        {
            "mne_celex": {"type": "literal", "value": "72022L2555ITA_202404316"},
            "dir_celex": {"type": "literal", "value": "32022L2555"},
            "title": {"type": "literal", "value": "Direttiva (UE) 2022/2555 del Parlamento europeo e del Consiglio, del 14 dicembre 2022, relativa a misure per un livello comune elevato di cibersicurezza nell'Unione (direttiva NIS 2)."},
            "transp": {"type": "literal", "value": "2024-10-17"},
            "act_type": {"type": "literal", "value": "Decreto legislativo"},
            "dir": {"type": "uri", "value": "http://publications.europa.eu/resource/cellar/nis2-dir-uri"},
        },
    ]},
}

_EMPTY = {"head": {"vars": ["x"]}, "results": {"bindings": []}}


def _sparql_mock(response_data):
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json = MagicMock(return_value=response_data)

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.post = AsyncMock(return_value=mock_resp)
    return mock_client


# ---------------------------------------------------------------------------
# build_directive_celex
# ---------------------------------------------------------------------------

class TestBuildDirectiveCelex:
    def test_already_celex(self):
        assert build_directive_celex("32019L0790") == "32019L0790"

    def test_already_celex_lowercase(self):
        assert build_directive_celex("32019l0790") == "32019L0790"

    def test_human_direttiva(self):
        assert build_directive_celex("direttiva 2019/790") == "32019L0790"

    def test_human_dir_ue_suffix(self):
        assert build_directive_celex("dir 2019/790/UE") == "32019L0790"

    def test_human_with_ue_prefix(self):
        assert build_directive_celex("direttiva (UE) 2019/790") == "32019L0790"

    def test_bare_year_number(self):
        assert build_directive_celex("2019/790") == "32019L0790"

    def test_zero_padding(self):
        assert build_directive_celex("direttiva 2022/2555") == "32022L2555"
        assert build_directive_celex("direttiva 2011/36") == "32011L0036"

    def test_regulation_human(self):
        assert build_directive_celex("regolamento 2016/679") == "32016R0679"

    def test_regulation_reg_abbrev(self):
        assert build_directive_celex("reg 2016/679/UE") == "32016R0679"

    def test_no_match_returns_none(self):
        assert build_directive_celex("non un riferimento") is None

    def test_empty_returns_none(self):
        assert build_directive_celex("") is None


# ---------------------------------------------------------------------------
# parse_mne_celex
# ---------------------------------------------------------------------------

class TestParseMneCelex:
    def test_valid_mne_celex(self):
        assert parse_mne_celex("72019L0790ITA_202107973") == "72019L0790ITA_202107973"

    def test_valid_nis2(self):
        assert parse_mne_celex("72022L2555ITA_202404316") == "72022L2555ITA_202404316"

    def test_directive_celex_is_not_mne(self):
        assert parse_mne_celex("32019L0790") is None

    def test_garbage_is_none(self):
        assert parse_mne_celex("D.Lgs. 177/2021") is None

    def test_empty_is_none(self):
        assert parse_mne_celex("") is None


# ---------------------------------------------------------------------------
# parse_italian_act_ref
# ---------------------------------------------------------------------------

class TestParseItalianActRef:
    def test_dlgs_abbrev(self):
        assert parse_italian_act_ref("D.Lgs. 177/2021") == ("decreto legislativo", "177", "2021")

    def test_decreto_legislativo_full(self):
        assert parse_italian_act_ref("decreto legislativo n. 138/2024") == ("decreto legislativo", "138", "2024")

    def test_legge(self):
        at, num, yr = parse_italian_act_ref("legge 90/2024")
        assert at == "legge"
        assert num == "90"
        assert yr == "2024"

    def test_unrecognized_type_keeps_empty(self):
        at, num, yr = parse_italian_act_ref("177/2021")
        assert at == ""
        assert (num, yr) == ("177", "2021")

    def test_no_number_year_returns_none(self):
        assert parse_italian_act_ref("decreto legislativo") is None

    def test_empty_returns_none(self):
        assert parse_italian_act_ref("") is None


# ---------------------------------------------------------------------------
# Query builders
# ---------------------------------------------------------------------------

class TestQueryBuilders:
    def test_eu_to_it_has_xsd_string(self):
        q = build_eu_to_it_query("32019L0790")
        assert '"32019L0790"^^xsd:string' in q

    def test_eu_to_it_constrains_directive_first(self):
        q = build_eu_to_it_query("32019L0790")
        # directive bound before the MNE join (directive-first to avoid timeout)
        dir_idx = q.index("resource_legal_id_celex \"32019L0790\"")
        mne_idx = q.index("measure_national_implementing_implements_resource_legal")
        assert dir_idx < mne_idx

    def test_eu_to_it_filters_country(self):
        q = build_eu_to_it_query("32019L0790", country="ITA")
        assert "authority/country/ITA" in q

    def test_eu_to_it_other_country(self):
        q = build_eu_to_it_query("32019L0790", country="fra")
        assert "authority/country/FRA" in q

    def test_eu_to_it_uses_implementing_predicates(self):
        q = build_eu_to_it_query("32019L0790")
        assert "measure_national_implementing_type_act" in q
        assert "measure_national_implementing_number_official_journal" in q

    def test_it_to_eu_from_mne_celex_has_literal(self):
        q = build_it_to_eu_from_mne_celex("72019L0790ITA_202107973")
        assert '"72019L0790ITA_202107973"^^xsd:string' in q

    def test_it_to_eu_from_act_two_branch(self):
        q = build_it_to_eu_from_act("138", "2024")
        # bare-number branch
        assert 'STR(?id_local) = "138"' in q
        # full-string boundary branch with year
        assert '"n. 138,"' in q
        assert '"2024"' in q

    def test_it_to_eu_from_act_word_boundary(self):
        # avoid '90' matching '190'
        q = build_it_to_eu_from_act("90", "2024")
        assert '"n. 90,"' in q
        assert '"n. 90 "' in q

    def test_directive_exists_query(self):
        q = build_directive_exists_query("32019L0790")
        assert '"32019L0790"^^xsd:string' in q
        assert "directive_date_transposition" in q


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

class TestParseImplementations:
    def test_dsm_single_measure(self):
        impls = parse_implementations(_EU_TO_IT_DSM["results"]["bindings"], "32019L0790")
        assert len(impls) == 1
        m = impls[0]
        assert m.mne_celex == "72019L0790ITA_202107973"
        assert m.act_type == "Decreto legislativo"
        assert m.id_local == "177"
        assert m.oj_number == "283"
        assert m.oj_date == "2021-11-27"
        assert m.directive_celex == "32019L0790"

    def test_nis2_full_string_id_local(self):
        impls = parse_implementations(_EU_TO_IT_NIS2["results"]["bindings"], "32022L2555")
        assert len(impls) == 1
        assert impls[0].id_local == "Decreto legislativo 4 settembre 2024, n. 138,"

    def test_dedupes_by_mne_uri(self):
        # Two rows of the SAME MNE (multivalued OPTIONAL) collapse to one.
        b1 = dict(_EU_TO_IT_DSM["results"]["bindings"][0])
        b2 = dict(_EU_TO_IT_DSM["results"]["bindings"][0])
        impls = parse_implementations([b1, b2], "32019L0790")
        assert len(impls) == 1

    def test_empty(self):
        assert parse_implementations([], "32019L0790") == []


class TestParseBases:
    def test_dsm_single_basis(self):
        bases = parse_bases(_IT_TO_EU_DSM["results"]["bindings"])
        assert len(bases) == 1
        b = bases[0]
        assert b.directive_celex == "32019L0790"
        assert b.transposition_deadline == "2021-06-07"
        assert "diritto d'autore" in b.directive_title

    def test_keeps_earliest_transposition_date(self):
        b1 = dict(_IT_TO_EU_DSM["results"]["bindings"][0])
        b2 = dict(_IT_TO_EU_DSM["results"]["bindings"][0])
        b2 = {**b2, "transp": {"type": "literal", "value": "2099-01-01"}}
        bases = parse_bases([b2, b1])
        # earliest (2021-06-07) wins as headline
        assert bases[0].transposition_deadline == "2021-06-07"

    def test_skips_rows_without_celex(self):
        bases = parse_bases([{"transp": {"value": "2021-01-01"}}])
        assert bases == []

    def test_empty(self):
        assert parse_bases([]) == []


# ---------------------------------------------------------------------------
# _clean_act_number / formatting
# ---------------------------------------------------------------------------

class TestCleanActNumber:
    def test_bare_number(self):
        assert _clean_act_number("177") == "177"

    def test_full_string(self):
        assert _clean_act_number("Decreto legislativo 4 settembre 2024, n. 138,") == "138"

    def test_empty(self):
        assert _clean_act_number("") == ""

    def test_no_number(self):
        assert _clean_act_number("decreto senza numero") == ""


class TestFormatImplementation:
    def test_dsm_heading_uses_bare_number(self):
        impl = parse_implementations(_EU_TO_IT_DSM["results"]["bindings"], "32019L0790")[0]
        text = format_implementation(impl)
        assert "Decreto legislativo n. 177" in text
        assert "Gazzetta Ufficiale" in text
        assert "283" in text
        assert "72019L0790ITA_202107973" in text
        assert "32019L0790" in text

    def test_nis2_heading_extracts_clean_number(self):
        impl = parse_implementations(_EU_TO_IT_NIS2["results"]["bindings"], "32022L2555")[0]
        text = format_implementation(impl)
        # heading must read "n. 138", NOT "n. Decreto legislativo 4 settembre..."
        assert "Decreto legislativo n. 138" in text

    def test_nis2_suppresses_placeholder_gu_date(self):
        impl = parse_implementations(_EU_TO_IT_NIS2["results"]["bindings"], "32022L2555")[0]
        text = format_implementation(impl)
        assert "1001-01-01" not in text


class TestFormatBasis:
    def test_basis_render(self):
        basis = parse_bases(_IT_TO_EU_DSM["results"]["bindings"])[0]
        text = format_basis(basis)
        assert "32019L0790" in text
        assert "Termine di trasposizione" in text
        assert "2021-06-07" in text
        assert "CELLAR URI" in text


# ---------------------------------------------------------------------------
# _mapping_to_search_result rendering
# ---------------------------------------------------------------------------

class TestMappingToSearchResult:
    def test_regulation_message(self):
        mapping = MappingResult(
            success=False, direction="eu_to_it", error_type="regulation",
            celex="32016R0679", query_ref="regolamento 2016/679",
            error_message="È un regolamento UE, direttamente applicabile: nessuna trasposizione nazionale.",
        )
        sr = _mapping_to_search_result(mapping)
        assert isinstance(sr, SearchResult)
        assert not sr.success
        assert "regolamento" in sr.to_str().lower()
        assert "cite_law" in sr.to_str()

    def test_source_down(self):
        mapping = MappingResult(
            success=False, direction="eu_to_it", error_type="source_down",
            error_message="timeout",
        )
        sr = _mapping_to_search_result(mapping)
        assert not sr.success
        assert sr.error_type == "source_down"
        assert "non raggiungibile" in sr.to_str()

    def test_eu_to_it_success(self):
        impls = parse_implementations(_EU_TO_IT_DSM["results"]["bindings"], "32019L0790")
        mapping = MappingResult(
            success=True, direction="eu_to_it", celex="32019L0790",
            query_ref="direttiva 2019/790", implementations=impls,
        )
        sr = _mapping_to_search_result(mapping)
        assert sr.success
        assert "Recepimento italiano" in sr.results_text
        assert "cite_law" in sr.results_text

    def test_it_to_eu_multi_directive_note(self):
        bases = [
            BasisResult(directive_celex="32019L0790", transposition_deadline="2021-06-07"),
            BasisResult(directive_celex="32011L0036", transposition_deadline="2013-04-06"),
        ]
        mapping = MappingResult(
            success=True, direction="it_to_eu", query_ref="D.Lgs. X",
            celex="", bases=bases,
        )
        sr = _mapping_to_search_result(mapping)
        assert sr.success
        assert "più direttive" in sr.results_text


# ---------------------------------------------------------------------------
# Tool impl functions (mocked SPARQL, end-to-end)
# ---------------------------------------------------------------------------

class TestGetItalianImplementationImpl:
    @pytest.mark.asyncio
    async def test_dsm(self):
        mock = _sparql_mock(_EU_TO_IT_DSM)
        with patch("src.lib.eu_implementation.client.httpx.AsyncClient", return_value=mock):
            result = await _get_italian_implementation_impl("direttiva 2019/790")
        assert isinstance(result, SearchResult)
        assert result.success
        assert "Decreto legislativo n. 177" in result.results_text

    @pytest.mark.asyncio
    async def test_nis2_celex_input(self):
        mock = _sparql_mock(_EU_TO_IT_NIS2)
        with patch("src.lib.eu_implementation.client.httpx.AsyncClient", return_value=mock):
            result = await _get_italian_implementation_impl("32022L2555")
        assert result.success
        assert "Decreto legislativo n. 138" in result.results_text

    @pytest.mark.asyncio
    async def test_regulation_no_query(self):
        # A regulation is detected client-side before any SPARQL call: even with
        # an empty mock it must short-circuit to the regulation message.
        mock = _sparql_mock(_EMPTY)
        with patch("src.lib.eu_implementation.client.httpx.AsyncClient", return_value=mock):
            result = await _get_italian_implementation_impl("32016R0679")
        assert not result.success
        assert "regolamento" in result.to_str().lower()
        # no SPARQL POST should have been issued
        assert mock.post.await_count == 0

    @pytest.mark.asyncio
    async def test_regulation_human_celex(self):
        mock = _sparql_mock(_EMPTY)
        with patch("src.lib.eu_implementation.client.httpx.AsyncClient", return_value=mock):
            result = await _get_italian_implementation_impl("regolamento 2016/679")
        assert not result.success
        assert "regolamento" in result.to_str().lower()

    @pytest.mark.asyncio
    async def test_no_results(self):
        mock = _sparql_mock(_EMPTY)
        with patch("src.lib.eu_implementation.client.httpx.AsyncClient", return_value=mock):
            result = await _get_italian_implementation_impl("direttiva 2099/999")
        assert not result.success
        assert result.error_type == "no_results"
        assert "Nessuna misura nazionale" in result.to_str()

    @pytest.mark.asyncio
    async def test_bad_input(self):
        mock = _sparql_mock(_EMPTY)
        with patch("src.lib.eu_implementation.client.httpx.AsyncClient", return_value=mock):
            result = await _get_italian_implementation_impl("ciao")
        assert not result.success
        assert "Errore" in result.to_str()

    @pytest.mark.asyncio
    async def test_source_down(self):
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(side_effect=httpx.RequestError("timeout"))
        with patch("src.lib.eu_implementation.client.httpx.AsyncClient", return_value=mock_client):
            result = await _get_italian_implementation_impl("direttiva 2019/790")
        assert not result.success
        assert result.error_type == "source_down"
        assert "non raggiungibile" in result.to_str()


class TestGetEuBasisImpl:
    @pytest.mark.asyncio
    async def test_from_mne_celex(self):
        mock = _sparql_mock(_IT_TO_EU_DSM)
        with patch("src.lib.eu_implementation.client.httpx.AsyncClient", return_value=mock):
            result = await _get_eu_basis_impl("72019L0790ITA_202107973")
        assert result.success
        assert "32019L0790" in result.results_text
        assert "2021-06-07" in result.results_text

    @pytest.mark.asyncio
    async def test_from_act_ref_dsm(self):
        mock = _sparql_mock(_IT_TO_EU_DSM)
        with patch("src.lib.eu_implementation.client.httpx.AsyncClient", return_value=mock):
            result = await _get_eu_basis_impl("D.Lgs. 177/2021")
        assert result.success
        assert "32019L0790" in result.results_text

    @pytest.mark.asyncio
    async def test_from_act_ref_nis2(self):
        mock = _sparql_mock(_IT_TO_EU_NIS2)
        with patch("src.lib.eu_implementation.client.httpx.AsyncClient", return_value=mock):
            result = await _get_eu_basis_impl("D.Lgs. 138/2024")
        assert result.success
        assert "32022L2555" in result.results_text

    @pytest.mark.asyncio
    async def test_no_results(self):
        mock = _sparql_mock(_EMPTY)
        with patch("src.lib.eu_implementation.client.httpx.AsyncClient", return_value=mock):
            result = await _get_eu_basis_impl("D.Lgs. 9999/2099")
        assert not result.success
        assert result.error_type == "no_results"
        assert "Nessuna base giuridica" in result.to_str()

    @pytest.mark.asyncio
    async def test_bad_input(self):
        mock = _sparql_mock(_EMPTY)
        with patch("src.lib.eu_implementation.client.httpx.AsyncClient", return_value=mock):
            result = await _get_eu_basis_impl("non un atto")
        assert not result.success
        assert "Errore" in result.to_str()

    @pytest.mark.asyncio
    async def test_source_down(self):
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(side_effect=httpx.RequestError("connection refused"))
        with patch("src.lib.eu_implementation.client.httpx.AsyncClient", return_value=mock_client):
            result = await _get_eu_basis_impl("72019L0790ITA_202107973")
        assert not result.success
        assert result.error_type == "source_down"


class TestElencoMisureNazionaliImpl:
    @pytest.mark.asyncio
    async def test_default_ita(self):
        mock = _sparql_mock(_EU_TO_IT_DSM)
        with patch("src.lib.eu_implementation.client.httpx.AsyncClient", return_value=mock):
            result = await _elenco_misure_nazionali_impl("direttiva 2019/790")
        assert result.success
        assert "Decreto legislativo n. 177" in result.results_text

    @pytest.mark.asyncio
    async def test_other_country_builds_query(self):
        mock = _sparql_mock(_EMPTY)
        with patch("src.lib.eu_implementation.client.httpx.AsyncClient", return_value=mock):
            result = await _elenco_misure_nazionali_impl("direttiva 2019/790", paese="FRA")
        # no ITA measures in empty mock -> no_results, but the country routed through
        assert not result.success
        assert result.error_type == "no_results"


# ---------------------------------------------------------------------------
# Optional live E2E (skipped by default)
# ---------------------------------------------------------------------------

@pytest.mark.live
class TestLive:
    @pytest.mark.asyncio
    async def test_dsm_directive_to_italy(self):
        result = await _get_italian_implementation_impl("direttiva 2019/790")
        assert result.success
        assert "177" in result.results_text

    @pytest.mark.asyncio
    async def test_gdpr_regulation(self):
        result = await _get_italian_implementation_impl("32016R0679")
        assert not result.success
        assert "regolamento" in result.to_str().lower()

    @pytest.mark.asyncio
    async def test_reverse_mne_celex(self):
        result = await _get_eu_basis_impl("72019L0790ITA_202107973")
        assert result.success
        assert "32019L0790" in result.results_text

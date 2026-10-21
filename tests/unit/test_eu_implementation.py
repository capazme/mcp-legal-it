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
    build_it_to_eu_from_title,
    filter_title_matches,
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

# Title fallback for D.Lgs. 196/2003 (MNE 72002L0058ITA_117422 has NO resource_legal_id_local).
# The second row is the notice of ANOTHER act (D.Lgs. 69/2012, MNE 72009L0136ITA_191163) whose
# title merely cites "n. 196": the fallback must discard it. Both rows captured from CELLAR
# on 2026-09-28.
_IT_TO_EU_196_BY_TITLE = {
    "head": {"vars": ["mne_celex", "dir_celex", "title", "transp", "act_type", "dir", "wtitle"]},
    "results": {"bindings": [
        {
            "mne_celex": {"type": "literal", "value": "72002L0058ITA_117422"},
            "dir_celex": {"type": "literal", "value": "32002L0058"},
            "title": {"type": "literal", "value": "Direttiva 2002/58/CE del Parlamento europeo e del Consiglio, del 12 luglio 2002, relativa al trattamento dei dati personali e alla tutela della vita privata nel settore delle comunicazioni elettroniche (direttiva relativa alla vita privata e alle comunicazioni elettroniche)"},
            "act_type": {"type": "literal", "value": "Decreto legislativo"},
            "dir": {"type": "uri", "value": "http://publications.europa.eu/resource/cellar/cb5af945-9d9f-40e6-acee-bd0c5bb4ed0a"},
            "wtitle": {"type": "literal", "value": "Decreto legislativo 30/6/2003, n. 196-Codice in materia di protezione dei dati personali.  GURI  n° 174 del 29/7/2003 p. 11"},
        },
        {
            "mne_celex": {"type": "literal", "value": "72009L0136ITA_191163"},
            "dir_celex": {"type": "literal", "value": "32009L0136"},
            "act_type": {"type": "literal", "value": "Decreto legislativo"},
            "dir": {"type": "uri", "value": "http://publications.europa.eu/resource/cellar/dir-2009-136-uri"},
            "wtitle": {"type": "literal", "value": "Modifiche al decreto legislativo 30 giugno 2003, n. 196, recante codice in materia di protezione dei dati personali"},
        },
    ]},
}

# EU -> FR for directive 32019L0790: two of the eight French measures notified to CELLAR
# (read 2026-09-28). id_local is the French number "2019-775"; the JORF date is reported
# in the same field as the Italian GU date.
_EU_TO_FR_DSM = {
    "head": {"vars": ["mne", "mne_celex", "act_type", "id_local", "oj_num", "oj_date", "eif", "title"]},
    "results": {"bindings": [
        {
            "mne": {"type": "uri", "value": "http://publications.europa.eu/resource/cellar/fra-loi-2019-775"},
            "mne_celex": {"type": "literal", "value": "72019L0790FRA_278035"},
            "act_type": {"type": "literal", "value": "Loi"},
            "id_local": {"type": "literal", "value": "2019-775"},
            "oj_date": {"type": "literal", "value": "2019-07-26"},
            "eif": {"type": "literal", "value": "2019-07-26"},
            "title": {"type": "literal", "value": "LOI no 2019-775 du 24 juillet 2019 tendant à créer un droit voisin au profit des agences de presse et des éditeurs de presse (1)"},
        },
        {
            "mne": {"type": "uri", "value": "http://publications.europa.eu/resource/cellar/fra-ord-2021-580"},
            "mne_celex": {"type": "literal", "value": "72019L0790FRA_202103614"},
            "act_type": {"type": "literal", "value": "Ordonnance"},
            "id_local": {"type": "literal", "value": "2021-580"},
            "oj_date": {"type": "literal", "value": "2021-05-13"},
            "title": {"type": "literal", "value": "Ordonnance n° 2021-580 du 12 mai 2021 portant transposition du 6 de l'article 2 et des articles 17 à 23 de la directive 2019/790 (NOR : MICB2106674R) JORF n°0111 du 13 mai 2021"},
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


def _sparql_mock_sequence(*responses):
    """Like _sparql_mock, but each successive SPARQL POST returns the next response."""
    mocks = []
    for data in responses:
        r = MagicMock()
        r.raise_for_status = MagicMock()
        r.json = MagicMock(return_value=data)
        mocks.append(r)
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.post = AsyncMock(side_effect=mocks)
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

    def test_it_to_eu_from_title_word_boundary(self):
        # fallback for notices without id_local: number followed by a delimiter, plus the year
        q = build_it_to_eu_from_title("196", "2003")
        assert '"n. 196-"' in q and '"n. 196,"' in q and '"n. 196 "' in q and '"n. 196."' in q
        assert 'CONTAINS(STR(?wtitle), "2003")' in q
        assert "resource_legal_id_local" not in q

    def test_directive_exists_query(self):
        q = build_directive_exists_query("32019L0790")
        assert '"32019L0790"^^xsd:string' in q
        assert "directive_date_transposition" in q


class TestFilterTitleMatches:
    # D.Lgs. 30 giugno 2003, n. 196 (Codice privacy): MNE 72002L0058ITA_117422 for
    # directive 2002/58/CE (art. 17 par. 2 of the directive: Member States notify their measures).
    rows = _IT_TO_EU_196_BY_TITLE["results"]["bindings"]

    def test_keeps_the_act_itself(self):
        kept = filter_title_matches(self.rows, "decreto legislativo", "196", "2003")
        assert [_b["mne_celex"]["value"] for _b in kept] == ["72002L0058ITA_117422"]

    def test_discards_a_title_that_only_cites_the_act(self):
        # "Modifiche al decreto legislativo 30 giugno 2003, n. 196" is another act
        kept = filter_title_matches(self.rows[1:], "decreto legislativo", "196", "2003")
        assert kept == []

    def test_unknown_act_type_accepts_any_known_type_prefix(self):
        kept = filter_title_matches(self.rows, "", "196", "2003")
        assert [_b["mne_celex"]["value"] for _b in kept] == ["72002L0058ITA_117422"]

    def test_wrong_type_or_year_or_number_is_discarded(self):
        assert filter_title_matches(self.rows, "legge", "196", "2003") == []
        assert filter_title_matches(self.rows, "decreto legislativo", "196", "2004") == []
        # "19" must not match "n. 196"
        assert filter_title_matches(self.rows, "decreto legislativo", "19", "2003") == []


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
    def test_french_number_kept_whole(self):
        # CELLAR id_local of loi n° 2019-775 and ordonnance n° 2021-580
        assert _clean_act_number("2019-775") == "2019-775"
        assert _clean_act_number("Ordonnance n° 2021-580 du 12 mai 2021") == "2021-580"

    def test_spanish_number_kept_whole(self):
        # Real Decreto-ley 24/2021
        assert _clean_act_number("24/2021") == "24/2021"

    def test_italian_number_followed_by_title_is_not_extended(self):
        # "n. 196-Codice ..." must give 196, not swallow the hyphen
        assert _clean_act_number("Decreto legislativo 30/6/2003, n. 196-Codice in materia") == "196"

    def test_journal_reference_gives_no_number(self):
        assert _clean_act_number("BGBl. 2021 I S. 1204 ff.") == ""

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

    def test_dsm_gu_date_is_not_printed_as_entry_into_force(self):
        # D.Lgs. 8 novembre 2021 n. 177: CELLAR's entry-into-force field repeats the GU
        # date (2021-11-27), Normattiva gives 12/12/2021 (art. 73 co. 3 Cost.; art. 10
        # preleggi: fifteenth day after publication). It must not be labelled
        # "Entrata in vigore".
        impl = parse_implementations(_EU_TO_IT_DSM["results"]["bindings"], "32019L0790")[0]
        text = format_implementation(impl)
        assert "**Entrata in vigore**" not in text
        assert "**Data registrata in CELLAR (non è l'entrata in vigore)**: 2021-11-27" in text
        assert "art. 73 co. 3 Cost." in text and "Normattiva" in text

    def test_entry_into_force_different_from_gu_date_is_kept(self):
        # A date distinct from the GU date is not a copy of it: printed as CELLAR gives it.
        impl = ImplementationResult(
            act_type="Decreto legislativo", id_local="177", oj_number="283",
            oj_date="2021-11-27", entry_into_force="2021-12-12", directive_celex="32019L0790",
        )
        assert "**Entrata in vigore**: 2021-12-12" in format_implementation(impl)

    def test_entry_into_force_without_reliable_gu_date_is_not_asserted(self):
        # Placeholder GU date 1001-01-01: the CELLAR date cannot be told apart from the
        # publication date, so it is not asserted as the entry into force.
        impl = ImplementationResult(
            act_type="Decreto legislativo", oj_date="1001-01-01",
            entry_into_force="2024-10-16", directive_celex="32022L2555",
        )
        text = format_implementation(impl)
        assert "**Entrata in vigore**" not in text
        assert "2024-10-16" in text and "1001-01-01" not in text

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
    async def test_act_without_local_id_found_by_title(self):
        # D.Lgs. 196/2003: the id_local query returns nothing (the CELLAR notice has no
        # resource_legal_id_local), the title fallback finds directive 32002L0058 and
        # discards the notice of D.Lgs. 69/2012 that only cites "n. 196".
        mock = _sparql_mock_sequence(_EMPTY, _IT_TO_EU_196_BY_TITLE)
        with patch("src.lib.eu_implementation.client.httpx.AsyncClient", return_value=mock):
            result = await _get_eu_basis_impl("D.Lgs. 196/2003")
        assert result.success
        assert "### 32002L0058" in result.results_text
        assert "32009L0136" not in result.results_text
        assert mock.post.await_count == 2

    @pytest.mark.asyncio
    async def test_title_fallback_not_run_when_id_local_query_answers(self):
        mock = _sparql_mock_sequence(_IT_TO_EU_DSM)
        with patch("src.lib.eu_implementation.client.httpx.AsyncClient", return_value=mock):
            result = await _get_eu_basis_impl("D.Lgs. 177/2021")
        assert result.success
        assert mock.post.await_count == 1

    @pytest.mark.asyncio
    async def test_no_results_after_title_fallback_explains_coverage(self):
        # An act that transposes no directive (e.g. D.Lgs. 101/2018 adapts to a regulation)
        # gets an honest message that does not blame a correct number/year.
        mock = _sparql_mock_sequence(_EMPTY, _EMPTY)
        with patch("src.lib.eu_implementation.client.httpx.AsyncClient", return_value=mock):
            result = await _get_eu_basis_impl("D.Lgs. 101/2018")
        assert not result.success
        text = result.to_str()
        assert "Nessuna base giuridica" in text
        assert "identificativo locale" in text and "titolo" in text

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


class TestElencoMisureNazionaliOtherCountry:
    """paese other than ITA: wording, act number and journal label follow the Member State.

    Art. 29(1)-(2) of directive (UE) 2019/790: each Member State notifies the Commission
    of its OWN national measures (the CELEX suffix FRA_ marks them as French).
    """

    @pytest.mark.asyncio
    async def test_fra_header_names_france_not_italy(self):
        mock = _sparql_mock(_EU_TO_FR_DSM)
        with patch("src.lib.eu_implementation.client.httpx.AsyncClient", return_value=mock):
            result = await _elenco_misure_nazionali_impl("direttiva 2019/790", paese="FRA")
        assert result.success
        header = result.results_text.splitlines()[0]
        assert header == "**Recepimento in Francia (FRA) della direttiva 32019L0790** — 2 misura/e nazionale/i"
        assert "italian" not in result.results_text.lower()

    @pytest.mark.asyncio
    async def test_fra_headings_carry_the_french_act_number(self):
        mock = _sparql_mock(_EU_TO_FR_DSM)
        with patch("src.lib.eu_implementation.client.httpx.AsyncClient", return_value=mock):
            result = await _elenco_misure_nazionali_impl("direttiva 2019/790", paese="fra")
        headings = [ln for ln in result.results_text.splitlines() if ln.startswith("### ")]
        assert headings == ["### Loi n. 2019-775", "### Ordonnance n. 2021-580"]

    @pytest.mark.asyncio
    async def test_fra_publication_is_not_called_gazzetta_ufficiale(self):
        # the JORF is not the Italian Gazzetta Ufficiale
        mock = _sparql_mock(_EU_TO_FR_DSM)
        with patch("src.lib.eu_implementation.client.httpx.AsyncClient", return_value=mock):
            result = await _elenco_misure_nazionali_impl("direttiva 2019/790", paese="FRA")
        assert "Gazzetta Ufficiale" not in result.results_text
        assert "**Pubblicazione ufficiale**: del 2021-05-13" in result.results_text
        # Italian art. 73 Cost. does not apply to a French act
        assert "art. 73" not in result.results_text and "Normattiva" not in result.results_text

    @pytest.mark.asyncio
    async def test_no_measures_message_names_the_country(self):
        # GBR left the EU before the 7 June 2021 deadline of art. 29(1): no measures, and the
        # message must not say "italiana".
        mock = _sparql_mock(_EMPTY)
        with patch("src.lib.eu_implementation.client.httpx.AsyncClient", return_value=mock):
            result = await _elenco_misure_nazionali_impl("direttiva 2019/790", paese="GBR")
        assert not result.success
        assert result.to_str().startswith("Nessuna misura nazionale (GBR) trovata per la direttiva _32019L0790_")
        assert "italian" not in result.to_str().lower()

    @pytest.mark.asyncio
    async def test_ita_keeps_italian_wording(self):
        mock = _sparql_mock(_EMPTY)
        with patch("src.lib.eu_implementation.client.httpx.AsyncClient", return_value=mock):
            result = await _elenco_misure_nazionali_impl("direttiva 2019/790")
        assert result.to_str().startswith("Nessuna misura nazionale italiana trovata")

    @pytest.mark.asyncio
    async def test_unknown_country_code_falls_back_to_the_code(self):
        mock = _sparql_mock(_EU_TO_FR_DSM)
        with patch("src.lib.eu_implementation.client.httpx.AsyncClient", return_value=mock):
            result = await _elenco_misure_nazionali_impl("direttiva 2019/790", paese="XXX")
        assert result.results_text.startswith("**Recepimento in XXX della direttiva")


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

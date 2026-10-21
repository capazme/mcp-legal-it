"""Unit tests for F4 — orientamento giurisprudenziale (DESCRIPTIVE map only).

HTTP calls are mocked — no real network access. Fixtures mirror real Italgiure
Solr facet responses (facet_fields + facet_queries) captured live on 2026-06-15.

L. 132/2025 forbids predictive justice: the output must be a descriptive map,
never a holdings classifier or an overruling forecast. Tests assert the mandatory
disclaimer is present and that NO predictive phrasing leaks into the output.
"""

import pytest
from unittest.mock import AsyncMock, patch

from src.lib._result import SearchResult
from src.lib.brocardi.client import Massima
from src.lib.italgiure.client import (
    CONFLICT_SIGNALS,
    CONFORMITY_SIGNALS,
    build_orientamento_params,
    group_signal_facet_query,
)
from src.tools.orientamento import (
    _ARCHIVE_NOTE,
    _DISCLAIMER,
    _PRINCIPIO_MM,
    _cluster_by_sezione,
    _doc_key,
    _format_signal_block,
    _mappa_orientamento_impl,
    _orientamento_su_norma_impl,
    _orientamento_su_principio_impl,
    _signal_split,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _doc(num: str, anno: str = "2025", sez: str = "3", kind: str = "snciv") -> dict:
    return {
        "id": f"{kind}{anno}{sez}{num}O",
        "numdec": num,
        "anno": anno,
        "datdep": ["20250827"],
        "szdec": sez,
        "materia": ["RESPONSABILITA' CIVILE"],
        "tipoprov": "Sentenza",
        "ocrdis": "P.Q.M. La Corte rigetta il ricorso.",
        "kind": kind,
    }


# Real szdec:U (Sezioni Unite) doc captured live (ocrdis truncated for the fixture).
_SS_UU_DOC = {
    "id": "snciv2026U18626O",
    "numdec": "18626",
    "anno": "2026",
    "datdep": ["20260608"],
    "szdec": "U",
    "materia": ["*RIC.CONTRO DECISIONI DI GIUDICI SPECIALI"],
    "tipoprov": "Ordinanza",
    "ocrdis": "P.Q.M. La Corte dichiara inammissibile il ricorso.",
    "kind": "snciv",
}

# facet.query keys are the literal Solr query strings the helper emits.
# The group keys carry the DISTINCT decisions (one OR query per group): 12 + 3 = 15 phrase hits
# but 14 decisions (one uses both expressions); 40 + 18 = 58 hits but 55 decisions.
_FACET_QUERIES = {
    f'ocr:"{CONFLICT_SIGNALS[0]}"': 12,
    f'ocr:"{CONFLICT_SIGNALS[1]}"': 3,
    f'ocr:"{CONFORMITY_SIGNALS[0]}"': 40,
    f'ocr:"{CONFORMITY_SIGNALS[1]}"': 18,
    group_signal_facet_query(CONFLICT_SIGNALS): 14,
    group_signal_facet_query(CONFORMITY_SIGNALS): 55,
}

_FACET_FIELDS = {
    "szdec": ["3", 30, "2", 18, "1", 9, "U", 4],
    "anno": ["2025", 25, "2024", 20, "2023", 12, "2022", 4],
}


def _main_response(num_found: int = 61) -> dict:
    return {
        "responseHeader": {"status": 0, "QTime": 5},
        "response": {
            "numFound": num_found,
            "start": 0,
            "docs": [
                _doc("24003", sez="3"),
                _doc("24010", sez="3"),
                _doc("24011", sez="2"),
                _doc("24012", sez="1"),
                _doc("24013", sez="L", kind="snciv"),
            ],
        },
        "facet_counts": {
            "facet_fields": _FACET_FIELDS,
            "facet_queries": _FACET_QUERIES,
        },
    }


def _ss_uu_response(num_found: int = 4) -> dict:
    return {
        "responseHeader": {"status": 0},
        "response": {"numFound": num_found, "start": 0, "docs": [_SS_UU_DOC]},
        "facet_counts": {"facet_fields": {}, "facet_queries": {}},
    }


def _empty_response() -> dict:
    return {
        "responseHeader": {"status": 0},
        "response": {"numFound": 0, "start": 0, "docs": []},
        "facet_counts": {"facet_fields": {}, "facet_queries": {}},
    }


_PREDICTIVE_FORBIDDEN = [
    "previsione",
    "prevede",
    "probabil",          # probabilità / probabile
    "esito atteso",
    "verrà accolt",
    "overruling prevedibile",
    "decisioni conformi",   # holdings classifier, not allowed
    "decisioni difformi",   # holdings classifier, not allowed
]


def _body_without_disclaimer(text: str) -> str:
    """Strip the mandated footer (which legitimately negates 'previsione') so the
    predictive-phrasing scan checks only the generated body."""
    return text.split(_DISCLAIMER)[0]


def _patch_two_query(main: dict, ss_uu: dict):
    """Patch solr_query so the 1st call returns the main faceted response and the
    2nd call returns the SS.UU. block. Also patch SolrSession to a no-op."""
    call_count = {"n": 0}

    async def mock_solr_query(params, session=None):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return main
        return ss_uu

    cm_session = AsyncMock()
    cm_session.__aenter__ = AsyncMock(return_value=cm_session)
    cm_session.__aexit__ = AsyncMock(return_value=False)
    session_cls = patch("src.tools.orientamento.SolrSession", return_value=cm_session)
    query_patch = patch("src.tools.orientamento.solr_query", side_effect=mock_solr_query)
    return query_patch, session_cls, call_count


# ---------------------------------------------------------------------------
# build_orientamento_params — ONE faceted request, szdec:U, facet.query signals
# ---------------------------------------------------------------------------

class TestBuildOrientamentoParams:
    def test_single_faceted_request_shape(self):
        p = build_orientamento_params("responsabilita")
        assert p["defType"] == "edismax"
        assert p["facet"] == "true"
        assert p["facet.field"] == ["szdec", "anno"]
        # sort newest-first to surface LATER decisions (pd is the sortable date field;
        # datdep is NOT sortable on Italgiure → 400)
        assert p["sort"] == "pd desc"

    def test_field_query_mode_embeds_kind_in_q_no_edismax(self):
        # Norma mode: a fielded ocr:(...) query must go in q as plain lucene,
        # never as the edismax q (which 400s on Italgiure).
        p = build_orientamento_params(
            'ocr:("art. 2043" OR "articolo 2043")', field_query=True,
        )
        assert "defType" not in p
        assert "qf" not in p
        assert 'kind:"snciv"' in p["q"]
        assert 'ocr:("art. 2043"' in p["q"]
        assert p["sort"] == "pd desc"
        # facet.query still present in field-query mode (faceting is defType-independent)
        assert len(p["facet.query"]) == len(CONFLICT_SIGNALS) + len(CONFORMITY_SIGNALS) + 2

    def test_facet_query_emits_all_signals_in_one_request(self):
        p = build_orientamento_params("responsabilita")
        fq = p["facet.query"]
        # ALL conflict + conformity signals must be present in the SAME request,
        # plus one OR query per group for the DISTINCT decision count
        for phrase in CONFLICT_SIGNALS + CONFORMITY_SIGNALS:
            assert f'ocr:"{phrase}"' in fq
        assert group_signal_facet_query(CONFLICT_SIGNALS) in fq
        assert group_signal_facet_query(CONFORMITY_SIGNALS) in fq
        assert len(fq) == len(CONFLICT_SIGNALS) + len(CONFORMITY_SIGNALS) + 2

    def test_sezioni_unite_uses_szdec_U_not_SU(self):
        p = build_orientamento_params("x", sezione="U")
        joined = " ".join(p["fq"])
        assert "szdec:U" in joined
        # szdec:SU is DEAD (0 docs) — must never be used
        assert "szdec:SU" not in joined

    def test_anno_da_filter(self):
        p = build_orientamento_params("x", anno_da=2022)
        assert any("anno:[2022 TO *]" in f for f in p["fq"])

    def test_no_anno_da_no_filter(self):
        p = build_orientamento_params("x")
        assert not any("anno:[" in f for f in p["fq"])

    def test_campo_dispositivo_narrows_qf(self):
        p = build_orientamento_params("x", campo="dispositivo")
        assert p["qf"] == "ocrdis^1"

    def test_archivio_penale(self):
        p = build_orientamento_params("x", archivio="penale")
        assert 'kind:"snpen"' in p["fq"][0]
        assert 'kind:"snciv"' not in p["fq"][0]


# ---------------------------------------------------------------------------
# Signal split helper
# ---------------------------------------------------------------------------

class TestSignalSplit:
    def test_maps_facet_queries_back_to_phrases(self):
        conflict, conformity = _signal_split(_FACET_QUERIES)
        assert [p for p, _ in conflict] == CONFLICT_SIGNALS
        assert [p for p, _ in conformity] == CONFORMITY_SIGNALS
        assert dict(conflict)[CONFLICT_SIGNALS[0]] == 12
        assert dict(conformity)[CONFORMITY_SIGNALS[0]] == 40

    def test_missing_key_defaults_zero(self):
        conflict, conformity = _signal_split({})
        assert all(c == 0 for _, c in conflict)
        assert all(c == 0 for _, c in conformity)


# ---------------------------------------------------------------------------
# Dedup helpers
# ---------------------------------------------------------------------------

class TestDedup:
    def test_doc_key_uses_id(self):
        assert _doc_key(_doc("24003")) == "snciv2025324003O"

    def test_doc_key_list_id(self):
        assert _doc_key({"id": ["abc"]}) == "abc"

    def test_doc_key_fallback_num_anno(self):
        assert _doc_key({"numdec": "100", "anno": "2024"}) == "100/2024"

    def test_cluster_dedup_by_id(self):
        d = _doc("24003", sez="3")
        clusters = _cluster_by_sezione([d, d, _doc("24011", sez="2")])
        # The duplicate (same id) must be collapsed
        assert len(clusters["3"]) == 1
        assert len(clusters["2"]) == 1

    def test_cluster_groups_by_sezione(self):
        docs = [_doc("1", sez="3"), _doc("2", sez="3"), _doc("3", sez="2")]
        clusters = _cluster_by_sezione(docs)
        assert len(clusters["3"]) == 2
        assert len(clusters["2"]) == 1


# ---------------------------------------------------------------------------
# orientamento_su_norma — full descriptive map
# ---------------------------------------------------------------------------

class TestOrientamentoSuNorma:
    @pytest.mark.asyncio
    async def test_success_produces_full_map(self):
        query_patch, session_cls, calls = _patch_two_query(_main_response(), _ss_uu_response())
        with query_patch, session_cls:
            result = await _orientamento_su_norma_impl("art. 2043 c.c.")
        assert isinstance(result, SearchResult)
        assert result.success is True
        # Exactly TWO queries: main faceted + SS.UU. block (no N-per-signal requests)
        assert calls["n"] == 2

    @pytest.mark.asyncio
    async def test_map_order_and_sections(self):
        query_patch, session_cls, _ = _patch_two_query(_main_response(), _ss_uu_response())
        with query_patch, session_cls:
            result = await _orientamento_su_norma_impl("art. 2043 c.c.")
        text = result.results_text
        # (1) SS.UU. block first, (2) per-sezione clusters, (3) anno trend, (4) signals
        i_ssuu = text.find("Sezioni Unite")
        i_cluster = text.find("Cluster per sezione")
        i_trend = text.find("Andamento temporale")
        i_signals = text.find("Segnali testuali")
        assert -1 < i_ssuu < i_cluster < i_trend < i_signals

    @pytest.mark.asyncio
    async def test_ss_uu_uses_szdec_U(self):
        captured = {"params": []}

        async def mock_solr_query(params, session=None):
            captured["params"].append(params)
            if len(captured["params"]) == 1:
                return _main_response()
            return _ss_uu_response()

        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=cm)
        cm.__aexit__ = AsyncMock(return_value=False)
        with patch("src.tools.orientamento.solr_query", side_effect=mock_solr_query), \
             patch("src.tools.orientamento.SolrSession", return_value=cm):
            await _orientamento_su_norma_impl("art. 2043 c.c.")

        ss_uu_params = captured["params"][1]
        joined = " ".join(ss_uu_params["fq"])
        assert "szdec:U" in joined
        assert "szdec:SU" not in joined

    @pytest.mark.asyncio
    async def test_conflict_and_conformity_counts_in_output(self):
        query_patch, session_cls, _ = _patch_two_query(_main_response(), _ss_uu_response())
        with query_patch, session_cls:
            result = await _orientamento_su_norma_impl("art. 2043 c.c.")
        text = result.results_text
        # The self-flag signal phrases must surface with their counts
        assert CONFLICT_SIGNALS[0] in text
        assert CONFORMITY_SIGNALS[0] in text
        # Totals are DISTINCT decisions from the group OR query (14 and 55), not the sums of the
        # per-phrase hits (15 and 58): a decision using two expressions counts once.
        assert "contrasto/difformità** (14)" in text
        assert "consolidato/conforme** (55)" in text

    @pytest.mark.asyncio
    async def test_temporal_split_present(self):
        query_patch, session_cls, _ = _patch_two_query(_main_response(), _ss_uu_response())
        with query_patch, session_cls:
            result = await _orientamento_su_norma_impl("art. 2043 c.c.")
        text = result.results_text
        assert "Andamento temporale" in text
        assert "2025" in text and "2022" in text

    @pytest.mark.asyncio
    async def test_signals_labeled_as_textual_not_holdings(self):
        query_patch, session_cls, _ = _patch_two_query(_main_response(), _ss_uu_response())
        with query_patch, session_cls:
            result = await _orientamento_su_norma_impl("art. 2043 c.c.")
        text = result.results_text
        # Must be framed as a TEXTUAL signal ("decisioni che SEGNALANO ...")
        assert "SEGNALANO" in text
        # Must NOT classify decisions as conformi/difformi (holdings)
        assert "decisioni conformi" not in text.lower()
        assert "decisioni difformi" not in text.lower()

    @pytest.mark.asyncio
    async def test_mandatory_disclaimer_present(self):
        query_patch, session_cls, _ = _patch_two_query(_main_response(), _ss_uu_response())
        with query_patch, session_cls:
            result = await _orientamento_su_norma_impl("art. 2043 c.c.")
        assert "132/2025" in result.results_text
        assert _DISCLAIMER in result.results_text

    @pytest.mark.asyncio
    async def test_no_predictive_phrasing(self):
        query_patch, session_cls, _ = _patch_two_query(_main_response(), _ss_uu_response())
        with query_patch, session_cls:
            result = await _orientamento_su_norma_impl("art. 2043 c.c.")
        low = _body_without_disclaimer(result.results_text).lower()
        for forbidden in _PREDICTIVE_FORBIDDEN:
            assert forbidden not in low, f"predictive phrasing leaked: {forbidden!r}"

    @pytest.mark.asyncio
    async def test_archive_horizon_note(self):
        query_patch, session_cls, _ = _patch_two_query(_main_response(), _ss_uu_response())
        with query_patch, session_cls:
            result = await _orientamento_su_norma_impl("art. 2043 c.c.")
        # The archive is a rolling window of about five years (no decision of 2020 exists;
        # continuous coverage from 27/09/2021, read on Italgiure 2026-09-25).
        assert _ARCHIVE_NOTE in result.results_text
        assert "2020" not in result.results_text
        assert "27/09/2021" in result.results_text

    @pytest.mark.asyncio
    async def test_no_results(self):
        query_patch, session_cls, _ = _patch_two_query(_empty_response(), _empty_response())
        with query_patch, session_cls:
            result = await _orientamento_su_norma_impl("art. 99999 c.c.")
        assert result.success is False
        assert result.error_type == "no_results"
        # Disclaimer present even on empty result
        assert "132/2025" in result.results_text

    @pytest.mark.asyncio
    async def test_source_down(self):
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(side_effect=Exception("network"))
        with patch("src.tools.orientamento.SolrSession", return_value=cm):
            result = await _orientamento_su_norma_impl("art. 2043 c.c.")
        assert result.success is False
        assert result.error_type == "source_down"

    @pytest.mark.asyncio
    async def test_max_risultati_capped(self):
        captured = {"params": []}

        async def mock_solr_query(params, session=None):
            captured["params"].append(params)
            if len(captured["params"]) == 1:
                return _main_response()
            return _ss_uu_response()

        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=cm)
        cm.__aexit__ = AsyncMock(return_value=False)
        with patch("src.tools.orientamento.solr_query", side_effect=mock_solr_query), \
             patch("src.tools.orientamento.SolrSession", return_value=cm):
            await _orientamento_su_norma_impl("art. 2043 c.c.", max_risultati=999)
        assert captured["params"][0]["rows"] == 50


# ---------------------------------------------------------------------------
# orientamento_su_principio
# ---------------------------------------------------------------------------

class TestOrientamentoSuPrincipio:
    @pytest.mark.asyncio
    async def test_success(self):
        query_patch, session_cls, calls = _patch_two_query(_main_response(), _ss_uu_response())
        with query_patch, session_cls:
            result = await _orientamento_su_principio_impl("buona fede oggettiva recesso")
        assert result.success is True
        assert calls["n"] == 2
        assert _DISCLAIMER in result.results_text

    @pytest.mark.asyncio
    async def test_sezione_filter_passed(self):
        captured = {"params": []}

        async def mock_solr_query(params, session=None):
            captured["params"].append(params)
            if len(captured["params"]) == 1:
                return _main_response()
            return _ss_uu_response()

        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=cm)
        cm.__aexit__ = AsyncMock(return_value=False)
        with patch("src.tools.orientamento.solr_query", side_effect=mock_solr_query), \
             patch("src.tools.orientamento.SolrSession", return_value=cm):
            await _orientamento_su_principio_impl("danno biologico", sezione="3")
        assert any("szdec:3" in f for f in captured["params"][0]["fq"])

    @pytest.mark.asyncio
    async def test_no_predictive_phrasing(self):
        query_patch, session_cls, _ = _patch_two_query(_main_response(), _ss_uu_response())
        with query_patch, session_cls:
            result = await _orientamento_su_principio_impl("legittimo affidamento")
        low = _body_without_disclaimer(result.results_text).lower()
        for forbidden in _PREDICTIVE_FORBIDDEN:
            assert forbidden not in low


# ---------------------------------------------------------------------------
# mappa_orientamento — orchestrator (Brocardi anchor → orientation map)
# ---------------------------------------------------------------------------

class TestMappaOrientamento:
    @pytest.mark.asyncio
    async def test_brocardi_anchor_surfaced(self):
        massime = [
            Massima(autorita="Cass. civ.", numero="12345", anno="2023", testo="principio A"),
            Massima(autorita="Cass. civ.", numero="67890", anno="2022", testo="principio B"),
        ]

        async def fake_brocardi(*a, **k):
            from src.lib.brocardi.client import BrocardiResult
            return BrocardiResult(url="x", massime=massime)

        query_patch, session_cls, _ = _patch_two_query(_main_response(), _ss_uu_response())
        with query_patch, session_cls, \
             patch("src.tools.orientamento.fetch_brocardi", side_effect=fake_brocardi), \
             patch("src.tools.orientamento.resolve_atto", return_value={"tipo_atto": "codice civile", "numero_atto": ""}):
            result = await _mappa_orientamento_impl("art. 2043 c.c.")
        assert result.success is True
        text = result.results_text
        assert "Ancoraggio Brocardi" in text
        assert "12345/2023" in text
        # SS.UU. block (szdec:U) must still be present after the anchor
        assert "Sezioni Unite" in text
        assert _DISCLAIMER in text

    @pytest.mark.asyncio
    async def test_brocardi_failure_still_produces_map(self):
        async def boom(*a, **k):
            raise Exception("brocardi down")

        query_patch, session_cls, _ = _patch_two_query(_main_response(), _ss_uu_response())
        with query_patch, session_cls, \
             patch("src.tools.orientamento.fetch_brocardi", side_effect=boom), \
             patch("src.tools.orientamento.resolve_atto", return_value={"tipo_atto": "codice civile", "numero_atto": ""}):
            result = await _mappa_orientamento_impl("art. 2043 c.c.")
        # Map still produced (fail-open on Brocardi)
        assert result.success is True
        assert "Cluster per sezione" in result.results_text
        # ... and the missing anchor is declared, not silently dropped
        assert "## Ancoraggio Brocardi" in result.results_text
        assert "Brocardi non raggiungibile" in result.results_text

    @pytest.mark.asyncio
    async def test_no_predictive_phrasing(self):
        async def fake_brocardi(*a, **k):
            from src.lib.brocardi.client import BrocardiResult
            return BrocardiResult(url="x", massime=[])

        query_patch, session_cls, _ = _patch_two_query(_main_response(), _ss_uu_response())
        with query_patch, session_cls, \
             patch("src.tools.orientamento.fetch_brocardi", side_effect=fake_brocardi), \
             patch("src.tools.orientamento.resolve_atto", return_value={"tipo_atto": "codice civile", "numero_atto": ""}):
            result = await _mappa_orientamento_impl("art. 2043 c.c.")
        low = _body_without_disclaimer(result.results_text).lower()
        for forbidden in _PREDICTIVE_FORBIDDEN:
            assert forbidden not in low


# ---------------------------------------------------------------------------
# Optional live E2E (skipped unless -m live)
# ---------------------------------------------------------------------------

@pytest.mark.live
@pytest.mark.asyncio
async def test_live_orientamento_su_norma():
    result = await _orientamento_su_norma_impl("art. 2043 c.c.", anno_da=2020)
    assert isinstance(result, SearchResult)
    assert _DISCLAIMER in (result.results_text or "")



# ---------------------------------------------------------------------------
# Corrections of the italgiure_orientamento benchmark cluster (2026-09-29)
# ---------------------------------------------------------------------------

def _two_call_capture(main: dict, ss_uu: dict):
    captured: dict = {"params": []}

    async def mock_solr_query(params, session=None):
        captured["params"].append(params)
        return main if len(captured["params"]) == 1 else ss_uu

    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=cm)
    cm.__aexit__ = AsyncMock(return_value=False)
    return (
        patch("src.tools.orientamento.solr_query", side_effect=mock_solr_query),
        patch("src.tools.orientamento.SolrSession", return_value=cm),
        captured,
    )


class TestSegnaliDecisioniDistinte:
    """The 'SEGNALANO' headers count decisions, not phrase hits.

    Read on Italgiure 2026-09-25 (art. 1419 c.c., civile, dal 2021): conformity 37 as the sum of
    12 + 25 phrase hits, 33 distinct decisions (4 use both expressions).
    """

    def test_header_uses_group_query_not_sum(self):
        text = "\n".join(_format_signal_block(_FACET_QUERIES))
        assert "contrasto/difformità** (14)" in text  # not 12 + 3
        assert "consolidato/conforme** (55)" in text  # not 40 + 18
        # the single expressions keep their own counts
        assert f"_«{CONFLICT_SIGNALS[0]}»_: 12" in text

    def test_header_falls_back_to_sum_without_group_key(self):
        legacy = {k: v for k, v in _FACET_QUERIES.items() if k.startswith('ocr:"')}
        text = "\n".join(_format_signal_block(legacy))
        assert "contrasto/difformità** (15)" in text

    def test_group_query_is_one_or_over_the_phrases(self):
        assert group_signal_facet_query(["a b", "c"]) == 'ocr:("a b" OR "c")'

    def test_discostarsi_is_not_a_conflict_signal(self):
        # Read on Italgiure 2026-09-25: 13 of the 22 decisions on art. 1419 c.c. using
        # "discostarsi" use the negated formula "non vi sono ragioni per discostarsi", which
        # declares conformity (65% of the civil archive): it must not be filed as contrasto.
        assert "discostarsi" not in CONFLICT_SIGNALS


class TestOrizzonteArchivio:
    def test_footer_does_not_claim_2020(self):
        assert "2020" not in _ARCHIVE_NOTE
        assert "cinque anni" in _ARCHIVE_NOTE

    def test_disclaimer_quotes_art_15_as_reservation_to_the_magistrate(self):
        # Art. 15, co. 1, L. 132/2025: with AI used in the judicial activity, every decision
        # on interpretation, facts and measures is reserved to the magistrate; the text says
        # nothing about "giustizia predittiva".
        assert "(art. 15, L. 132/2025)" in _DISCLAIMER
        assert "riservate al magistrato" in _DISCLAIMER
        assert "predittiv" not in _DISCLAIMER.lower()


class TestDocstringsArt15:
    def test_wrappers_do_not_attribute_a_ban_to_l_132_2025(self):
        from src.tools import orientamento as mod

        for name in ("orientamento_su_norma", "orientamento_su_principio", "mappa_orientamento"):
            tool = getattr(mod, name)
            doc = (getattr(tool, "fn", tool).__doc__ or "").lower()
            assert "vietata la giustizia predittiva" not in doc, name
            assert "non è una previsione (l. 132/2025)" not in doc, name
            assert "riservat" in doc, name


class TestPrincipioPertinenza:
    """orientamento_su_principio: strict matching and a relevance-ordered SS.UU. block.

    Read on Italgiure 2026-09-29 for 'fideiussione omnibus schema ABI nullità parziale'
    (civile, dal 2021): with the default mm '2<75% 5<60%' 14 SS.UU. and 1598 decisions, the five
    most recent SS.UU. shown were unrelated (IVA, IRPEF) and SS.UU. 41994/2021 missing; with
    mm '3<90%' the SS.UU. are 2 (24825/2026 and 41994/2021) and the total 248.
    """

    @pytest.mark.asyncio
    async def test_strict_mm_and_score_sort_for_ss_uu_block(self):
        qp, sp, captured = _two_call_capture(_main_response(), _ss_uu_response())
        with qp, sp:
            await _orientamento_su_principio_impl("fideiussione omnibus schema ABI nullità parziale")
        main, ss_uu = captured["params"]
        assert main["mm"] == _PRINCIPIO_MM == "3<90%"
        assert ss_uu["mm"] == "3<90%"
        assert ss_uu["sort"] == "score desc"
        assert "pf" in ss_uu and "pf2" in ss_uu
        assert any("szdec:U" in f for f in ss_uu["fq"])
        assert main["sort"] == "pd desc"  # the sample of later decisions stays by date

    @pytest.mark.asyncio
    async def test_output_declares_total_semantics_and_shows_materia(self):
        qp, sp, _ = _two_call_capture(_main_response(), _ss_uu_response())
        with qp, sp:
            result = await _orientamento_su_principio_impl("fideiussione omnibus schema ABI")
        text = result.results_text
        assert "almeno il 90% dei termini" in text
        assert "per pertinenza al principio" in text
        assert "— *RIC.CONTRO DECISIONI DI GIUDICI SPECIALI" in text  # materia next to the SS.UU.

    @pytest.mark.asyncio
    async def test_relaxes_once_when_strict_matching_finds_nothing(self):
        calls: list = []

        async def mock_solr_query(params, session=None):
            calls.append(params)
            if len(calls) <= 2:  # strict main + strict SS.UU.
                return _empty_response()
            return _main_response() if len(calls) == 3 else _ss_uu_response()

        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=cm)
        cm.__aexit__ = AsyncMock(return_value=False)
        with patch("src.tools.orientamento.solr_query", side_effect=mock_solr_query), \
             patch("src.tools.orientamento.SolrSession", return_value=cm):
            result = await _orientamento_su_principio_impl("buona fede oggettiva recesso")
        assert result.success is True
        assert len(calls) == 4
        assert calls[2]["mm"] == "2<75% 5<60%"
        assert "criteri allargati" in result.results_text

    @pytest.mark.asyncio
    async def test_invalid_sezione_is_rejected_with_valid_codes(self):
        result = await _orientamento_su_principio_impl("danno biologico", sezione="9")
        assert result.success is False
        assert result.error_type == "bad_input"
        assert "1-7" in result.results_text and "U" in result.results_text

    @pytest.mark.asyncio
    async def test_sezione_su_becomes_u(self):
        qp, sp, captured = _two_call_capture(_main_response(), _ss_uu_response())
        with qp, sp:
            await _orientamento_su_principio_impl("danno biologico", sezione="SU")
        assert any("szdec:U" in f for f in captured["params"][0]["fq"])


class TestOrientamentoSuNormaGdpr:
    """The norma variants no longer OR the bare 'art. 13' for an act.

    Read on Italgiure 2026-09-29 (civile, anno 2022): bare 'art. 13' / 'articolo 13' 12966
    decisions (art. 13 co. 1-quater d.P.R. 115/2002), the same with a GDPR marker
    (2016/679, 679/2016, 679 del 2016, gdpr) anywhere in the decision: 2, none of which cites
    art. 13 of the Regulation. Since 2021 the proximity phrase 'art. 13 2016/679'~15 finds 7
    decisions, 5 of them pertinent.
    """

    @pytest.mark.asyncio
    async def test_query_for_gdpr_requires_act_markers(self):
        qp, sp, captured = _two_call_capture(_main_response(), _ss_uu_response())
        with qp, sp:
            await _orientamento_su_norma_impl("art. 13 GDPR", archivio="civile", anno_da=2022)
        q = captured["params"][0]["q"]
        assert '"art. 13"' not in q and '"articolo 13"' not in q
        for marker in ("2016/679", "679/2016", "679 del 2016", "gdpr"):
            assert f'"art. 13 {marker}"~15' in q
        assert q.count("(kind:") == 1


class TestMappaAncoraggio:
    """mappa_orientamento: the Brocardi anchor is honest about what it is and what it lacks."""

    @staticmethod
    def _run(massime, resolve=None):
        async def fake_brocardi(*a, **k):
            from src.lib.brocardi.client import BrocardiResult
            return BrocardiResult(url="x", massime=massime)

        qp, sp, _ = _patch_two_query(_main_response(), _ss_uu_response())
        return qp, sp, patch("src.tools.orientamento.fetch_brocardi", side_effect=fake_brocardi), \
            patch("src.tools.orientamento.resolve_atto",
                  return_value=resolve if resolve is not None
                  else {"tipo_atto": "codice civile", "numero_atto": ""})

    @pytest.mark.asyncio
    async def test_title_does_not_call_the_massime_consolidate(self):
        massime = [Massima(autorita="Cass. civ.", numero="31191", anno="2025", testo="x")]
        qp, sp, bp, rp = self._run(massime)
        with qp, sp, bp, rp:
            result = await _mappa_orientamento_impl("art. 2043 c.c.")
        assert "## Ancoraggio Brocardi\n" in result.results_text
        assert "massime consolidate" not in result.results_text

    @pytest.mark.asyncio
    async def test_reports_references_before_the_archive_window(self):
        # Read on Brocardi 2026-09-25: for art. 2043 c.c. 204 of the 500 Cassazione
        # references predate 2021 and cannot be read with leggi_sentenza.
        massime = [
            Massima(autorita="Cass. civ.", numero="31191", anno="2025", testo="a"),
            Massima(autorita="Cass. civ.", numero="100", anno="2019", testo="b"),
            Massima(autorita="Cass. civ.", numero="200", anno="2020", testo="c"),
        ]
        qp, sp, bp, rp = self._run(massime)
        with qp, sp, bp, rp:
            result = await _mappa_orientamento_impl("art. 2043 c.c.")
        assert "2 su 3 riferimenti precedono il 2021" in result.results_text

    @pytest.mark.asyncio
    async def test_declares_when_brocardi_has_no_massime(self):
        qp, sp, bp, rp = self._run([])
        with qp, sp, bp, rp:
            result = await _mappa_orientamento_impl("art. 2043 c.c.")
        assert "Brocardi non riporta massime per art. 2043 c.c." in result.results_text
        assert "Cluster per sezione" in result.results_text

    @pytest.mark.asyncio
    async def test_declares_when_the_act_is_not_recognised(self):
        qp, sp, bp, rp = self._run([], resolve=None)
        with qp, sp, bp, patch("src.tools.orientamento.resolve_atto", return_value=None):
            result = await _mappa_orientamento_impl("art. 2043 c.c.")
        assert "atto non riconosciuto" in result.results_text

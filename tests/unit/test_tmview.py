"""Unit tests for TMview (EUIPO/TMDN trademark database) client and tools.

Tests are written against mocked httpx responses — no real network calls.
Fixtures mirror the actual TMview JSON API structure (captured 2026-08-25).
"""

import httpx
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.lib.tmview.client import (
    STATI,
    STATO_LABELS_IT,
    TMviewBlockedError,
    TrademarkDetail,
    TrademarkResult,
    _build_search_payload,
    _normalize_name,
    _parse_date,
    _parse_detail_response,
    _parse_search_response,
    fetch_trademark,
    format_detail,
    format_result,
    search_trademarks,
)
from src.lib._result import SearchResult
from src.tools.tmview import (
    _cerca_marchi_impl,
    _leggi_marchio_impl,
    _verifica_anteriorita_marchio_impl,
)


# ---------------------------------------------------------------------------
# Fixtures — trimmed copies of real TMview API responses
# ---------------------------------------------------------------------------

_SEARCH_RESPONSE = {
    "tradeMarks": [
        {
            "ST13": "IT501999900797027",
            "markImageURI": "https://www.tmdn.org/tmview/api/trademark/thumbnail/IT501999900797027",
            "detailImageURI": "https://www.tmdn.org/tmview/api/trademark/image/IT501999900797027",
            "tmName": "FUORICORSO",
            "tmOffice": "IT",
            "tmOfficeURL": "http://tmview.uibm.gov.it/trademark/data/IT501999900797027",
            "tProtection": ["IT"],
            "applicationNumber": "1999900797027",
            "registrationNumber": "0000889526",
            "tradeMarkStatus": "Registered",
            "niceClass": [7, 9, 25],
            "applicantName": ["OSTELABORA 2 S.R.L. ORA NET-RESEARCH SRL"],
            "applicationDate": "1999-10-29T12:00:00.000Z",
            "tradeMarkType": "Other",
            "registrationDate": "2003-04-22T12:00:00.000Z",
            "seniorityClaimed": False,
        },
        {
            "ST13": "CH502024000017249",
            "tmName": "FUORICORSO",
            "tmOffice": "CH",
            "tmOfficeURL": "https://www.tmdn.org/tmdsview-cdc/trademark/data/CH502024000017249",
            "tProtection": ["CH"],
            "applicationNumber": "17249/2024",
            "registrationNumber": "826091",
            "tradeMarkStatus": "Registered",
            "niceClass": [25, 35, 38, 41, 43],
            "applicantName": ["TBTBC Sagl"],
            "applicationDate": "2024-12-10T12:00:00.000Z",
            "tradeMarkType": "Word",
            "registrationDate": "2025-02-03T12:00:00.000Z",
            "expirationDate": "2034-12-10T12:00:00.000Z",
        },
        {
            "ST13": "IT502024000072490",
            "tmName": 'Il marchio presenta il testo "FUORI CORSO" in blu scuro',
            "tmOffice": "IT",
            "tProtection": ["IT"],
            "applicationNumber": "2024000072490",
            "registrationNumber": "2024000072490",
            "tradeMarkStatus": "Filed",
            "niceClass": [41, 43],
            "applicantName": ["Zugan Luca"],
            "applicationDate": "2024-05-03T12:00:00.000Z",
            "tradeMarkType": "Figurative",
        },
    ],
    "page": 1,
    "totalPages": 1,
    "totalResults": 9,
}

_SEARCH_RESPONSE_EMPTY = {"tradeMarks": [], "page": 1, "totalPages": 0, "totalResults": 0}

_DETAIL_RESPONSE = {
    "officeUrl": "https://www.uibm.gov.it/bancadati/Number_search/type_url?type=wpn",
    "officeLastUpdateDate": "2026-08-22T00:00:00.000Z",
    "officeNumberOfTradeMark": "1277704",
    "ST13": "IT502013902128590",
    "tradeMark": {
        "markImageURI": "https://www.tmdn.org/tmview/api/trademark/image/IT502013902128590",
        "imageDescription": "MARCHIO FIGURATIVO : PROFILO DI DANTE ALIGHIERI IN FORMA STILIZZATA",
        "tmName": "FUORICORSO",
        "applicationNumber": "2013902128590",
        "applicationLanguageCode": "it",
        "applicationDate": "2013-02-19T00:00:00.000Z",
        "tmOffice": "Italy - UIBM",
        "registrationOfficeCode": "IT",
        "registrationNumber": "0001557431",
        "codeRegistrationDate": "2013-09-17T00:00:00.000Z",
        "designatedCountries": [],
        "markFeature": "Other",
        "kindMark": "Individual",
        "goodAndServices": [
            {"niceClass": "25", "goodsAndServices": "ARTICOLI DI ABBIGLIAMENTO, SCARPE, CAPPELLERIA"},
            {"niceClass": "43", "goodsAndServices": "SERVIZI DI RISTORAZIONE (ALIMENTAZIONE); ALLOGGI TEMPORANEI"},
        ],
        "markCurrentStatusCode": "Registered",
        "markCurrentStatusDate": "2013-09-17T00:00:00.000Z",
        "iprKind": "Trade mark",
        "niceClass": "25, 43",
    },
    "applicants": [
        {
            "identifier": "5298993",
            "fullName": "MENNUCCI LETIZIA",
            "legalEntity": "Physical person",
            "addressDetails": {"countryCode": "IT"},
        }
    ],
    "representatives": [],
    "priority": [],
    "publication": [
        {"identifier": "num.28 16/10/2013", "section": "Registration", "date": "2013-10-16T00:00:00.000Z"},
        {"identifier": "num.22 18/04/2013", "section": "Application", "date": "2013-04-18T00:00:00.000Z"},
    ],
    "oppositions": [],
    "cancellations": [],
    "renewals": [],
}


def _mock_http_client(get_response=None, post_response=None, post_side_effect=None, cookies=None):
    """Build a mocked httpx.AsyncClient usable as async context manager.

    `cookies` mimics the jar after the warm-up GET: a non-empty jar means the
    WAF handed out a session, an empty one means it turned us away.
    """
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.cookies = {"TS01919f74": "x"} if cookies is None else cookies
    if get_response is None:
        get_response = MagicMock()
        get_response.raise_for_status = MagicMock()
    mock_client.get = AsyncMock(return_value=get_response)
    if post_side_effect is not None:
        mock_client.post = AsyncMock(side_effect=post_side_effect)
    else:
        mock_client.post = AsyncMock(return_value=post_response)
    return mock_client


def _json_response(payload):
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json = MagicMock(return_value=payload)
    return resp


def _html_response(body="<!DOCTYPE html><html>challenge</html>"):
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json = MagicMock(side_effect=ValueError("Expecting value"))
    resp.text = body
    return resp


# ---------------------------------------------------------------------------
# Payload builder
# ---------------------------------------------------------------------------

class TestBuildSearchPayload:
    def test_basic_term_only(self):
        payload = _build_search_payload("FUORI CORSO", page=1, page_size=20)
        assert payload["basicSearch"] == "FUORI CORSO"
        assert payload["criteria"] == "C"
        assert payload["page"] == "1"
        assert payload["pageSize"] == "20"
        assert "offices" not in payload
        assert "niceClass" not in payload
        assert "tmStatus" not in payload

    def test_with_filters(self):
        payload = _build_search_payload(
            "BARILLA",
            offices=["IT", "EM"],
            nice_classes=["30"],
            statuses=["Registered"],
        )
        assert payload["offices"] == ["IT", "EM"]
        assert payload["niceClass"] == ["30"]
        assert payload["tmStatus"] == ["Registered"]


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

class TestParseSearchResponse:
    def test_parses_results(self):
        total, results = _parse_search_response(_SEARCH_RESPONSE)
        assert total == 9
        assert len(results) == 3
        first = results[0]
        assert isinstance(first, TrademarkResult)
        assert first.st13 == "IT501999900797027"
        assert first.name == "FUORICORSO"
        assert first.office == "IT"
        assert first.status == "Registered"
        assert first.nice_classes == [7, 9, 25]
        assert first.applicants == ["OSTELABORA 2 S.R.L. ORA NET-RESEARCH SRL"]
        assert first.application_date == "29/10/1999"
        assert first.registration_date == "22/04/2003"
        assert first.mark_type == "Other"

    def test_parses_expiry_date(self):
        _, results = _parse_search_response(_SEARCH_RESPONSE)
        assert results[1].expiry_date == "10/12/2034"
        assert results[0].expiry_date == ""

    def test_empty_response(self):
        total, results = _parse_search_response(_SEARCH_RESPONSE_EMPTY)
        assert total == 0
        assert results == []

    def test_missing_keys_tolerated(self):
        total, results = _parse_search_response({})
        assert total == 0
        assert results == []


class TestParseDetailResponse:
    def test_parses_detail(self):
        detail = _parse_detail_response(_DETAIL_RESPONSE)
        assert isinstance(detail, TrademarkDetail)
        assert detail.st13 == "IT502013902128590"
        assert detail.name == "FUORICORSO"
        assert detail.office_name == "Italy - UIBM"
        assert detail.application_number == "2013902128590"
        assert detail.application_date == "19/02/2013"
        assert detail.registration_number == "0001557431"
        assert detail.registration_date == "17/09/2013"
        assert detail.status == "Registered"
        assert detail.status_date == "17/09/2013"
        assert detail.kind_mark == "Individual"
        assert detail.mark_feature == "Other"
        assert "DANTE ALIGHIERI" in detail.image_description

    def test_parses_applicants_with_country(self):
        detail = _parse_detail_response(_DETAIL_RESPONSE)
        assert detail.applicants == ["MENNUCCI LETIZIA (IT)"]

    def test_parses_goods_services(self):
        detail = _parse_detail_response(_DETAIL_RESPONSE)
        assert len(detail.goods_services) == 2
        assert detail.goods_services[0][0] == "25"
        assert "ABBIGLIAMENTO" in detail.goods_services[0][1]
        assert detail.goods_services[1][0] == "43"

    def test_parses_publications(self):
        detail = _parse_detail_response(_DETAIL_RESPONSE)
        assert len(detail.publications) == 2
        assert "Registration" in detail.publications[0]

    def test_office_last_update(self):
        detail = _parse_detail_response(_DETAIL_RESPONSE)
        assert detail.office_last_update == "22/08/2026"


class TestParseDate:
    def test_iso_datetime(self):
        assert _parse_date("2013-02-19T00:00:00.000Z") == "19/02/2013"

    def test_empty(self):
        assert _parse_date("") == ""
        assert _parse_date(None) == ""

    def test_garbage_returned_verbatim(self):
        assert _parse_date("n/a") == "n/a"


class TestNormalizeName:
    def test_spaces_and_case_ignored(self):
        assert _normalize_name("FUORI CORSO") == _normalize_name("fuoricorso")

    def test_punctuation_ignored(self):
        assert _normalize_name("FUORI-CORSO!") == _normalize_name("FUORI CORSO")

    def test_different_names_differ(self):
        assert _normalize_name("FUORI CORSO") != _normalize_name("FUORI GIOCO")


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------

class TestFormatters:
    def test_format_result(self):
        _, results = _parse_search_response(_SEARCH_RESPONSE)
        text = format_result(results[0])
        assert "FUORICORSO" in text
        assert "IT501999900797027" in text
        assert "Registrato" in text  # Italian status label
        assert "29/10/1999" in text
        assert "7, 9, 25" in text
        assert "OSTELABORA" in text

    def test_format_result_unknown_status_verbatim(self):
        _, results = _parse_search_response(_SEARCH_RESPONSE)
        results[0].status = "SomethingNew"
        assert "SomethingNew" in format_result(results[0])

    def test_format_detail(self):
        detail = _parse_detail_response(_DETAIL_RESPONSE)
        text = format_detail(detail)
        assert "FUORICORSO" in text
        assert "IT502013902128590" in text
        assert "MENNUCCI LETIZIA (IT)" in text
        assert "Italy - UIBM" in text
        assert "Classe 25" in text
        assert "ABBIGLIAMENTO" in text
        assert "Registrato" in text
        assert "0001557431" in text


# ---------------------------------------------------------------------------
# Client HTTP functions (mocked httpx)
# ---------------------------------------------------------------------------

class TestSearchTrademarks:
    @pytest.mark.asyncio
    async def test_success(self):
        mock_client = _mock_http_client(post_response=_json_response(_SEARCH_RESPONSE))
        with patch("src.lib.tmview.client.httpx.AsyncClient", return_value=mock_client), \
             patch("src.lib.tmview.client._MIN_INTERVAL", 0):
            total, results = await search_trademarks("FUORI CORSO")
        assert total == 9
        assert len(results) == 3
        # warm-up GET on the home page happened before the API POST
        assert mock_client.get.await_count == 1
        payload = mock_client.post.await_args.kwargs["json"]
        assert payload["basicSearch"] == "FUORI CORSO"

    @pytest.mark.asyncio
    async def test_filters_forwarded(self):
        mock_client = _mock_http_client(post_response=_json_response(_SEARCH_RESPONSE_EMPTY))
        with patch("src.lib.tmview.client.httpx.AsyncClient", return_value=mock_client), \
             patch("src.lib.tmview.client._MIN_INTERVAL", 0):
            await search_trademarks(
                "BARILLA", offices=["IT"], nice_classes=["30"], statuses=["Registered"]
            )
        payload = mock_client.post.await_args.kwargs["json"]
        assert payload["offices"] == ["IT"]
        assert payload["niceClass"] == ["30"]
        assert payload["tmStatus"] == ["Registered"]

    @pytest.mark.asyncio
    async def test_waf_challenge_raises(self):
        mock_client = _mock_http_client(post_response=_html_response())
        with patch("src.lib.tmview.client.httpx.AsyncClient", return_value=mock_client), \
             patch("src.lib.tmview.client._MIN_INTERVAL", 0):
            with pytest.raises(TMviewBlockedError):
                await search_trademarks("FUORI CORSO")

    @pytest.mark.asyncio
    async def test_warmup_without_cookies_fails_fast(self):
        """No session cookie after warm-up = already turned away; don't POST."""
        mock_client = _mock_http_client(
            post_response=_json_response(_SEARCH_RESPONSE), cookies={}
        )
        with patch("src.lib.tmview.client.httpx.AsyncClient", return_value=mock_client), \
             patch("src.lib.tmview.client._MIN_INTERVAL", 0):
            with pytest.raises(TMviewBlockedError):
                await search_trademarks("FUORI CORSO")
        assert mock_client.post.await_count == 0


class TestFetchTrademark:
    @pytest.mark.asyncio
    async def test_success(self):
        detail_resp = _json_response(_DETAIL_RESPONSE)
        mock_client = _mock_http_client(get_response=detail_resp)
        # warm-up GET and detail GET share the mock; first call is home, second is API
        with patch("src.lib.tmview.client.httpx.AsyncClient", return_value=mock_client), \
             patch("src.lib.tmview.client._MIN_INTERVAL", 0):
            detail = await fetch_trademark("IT502013902128590")
        assert detail.name == "FUORICORSO"
        called_urls = [c.args[0] for c in mock_client.get.await_args_list]
        assert any("IT502013902128590" in u for u in called_urls)

    @pytest.mark.asyncio
    async def test_waf_challenge_raises(self):
        mock_client = _mock_http_client(get_response=_html_response())
        with patch("src.lib.tmview.client.httpx.AsyncClient", return_value=mock_client), \
             patch("src.lib.tmview.client._MIN_INTERVAL", 0):
            with pytest.raises(TMviewBlockedError):
                await fetch_trademark("IT502013902128590")

    @pytest.mark.asyncio
    async def test_warmup_without_cookies_fails_fast(self):
        mock_client = _mock_http_client(
            get_response=_json_response(_DETAIL_RESPONSE), cookies={}
        )
        with patch("src.lib.tmview.client.httpx.AsyncClient", return_value=mock_client), \
             patch("src.lib.tmview.client._MIN_INTERVAL", 0):
            with pytest.raises(TMviewBlockedError):
                await fetch_trademark("IT502013902128590")
        # only the warm-up GET happened, no detail request
        assert mock_client.get.await_count == 1


# ---------------------------------------------------------------------------
# Tool impl functions (client functions patched)
# ---------------------------------------------------------------------------

class TestCercaMarchiImpl:
    @pytest.mark.asyncio
    async def test_success(self):
        _, results = _parse_search_response(_SEARCH_RESPONSE)
        with patch("src.tools.tmview.search_trademarks", AsyncMock(return_value=(9, results))):
            result = await _cerca_marchi_impl("FUORI CORSO")
        assert isinstance(result, SearchResult)
        assert result.success is True
        assert result.source == "tmview"
        assert result.num_found == 9
        assert "FUORICORSO" in result.results_text
        assert "9" in result.results_text

    @pytest.mark.asyncio
    async def test_filters_translated(self):
        mock_search = AsyncMock(return_value=(0, []))
        with patch("src.tools.tmview.search_trademarks", mock_search):
            await _cerca_marchi_impl(
                "BARILLA", uffici="it, em", classi_nizza="30", stato="registrato"
            )
        kwargs = mock_search.await_args.kwargs
        assert kwargs["offices"] == ["IT", "EM"]
        assert kwargs["nice_classes"] == ["30"]
        assert kwargs["statuses"] == ["Registered"]

    @pytest.mark.asyncio
    async def test_invalid_stato(self):
        result = await _cerca_marchi_impl("X", stato="inesistente")
        assert result.success is False
        assert "registrato" in result.results_text  # lists valid values

    @pytest.mark.asyncio
    async def test_invalid_classe(self):
        result = await _cerca_marchi_impl("X", classi_nizza="99")
        assert result.success is False
        assert "1" in result.results_text and "45" in result.results_text

    @pytest.mark.asyncio
    async def test_no_results(self):
        with patch("src.tools.tmview.search_trademarks", AsyncMock(return_value=(0, []))):
            result = await _cerca_marchi_impl("XYZNONESISTE")
        assert result.success is False
        assert result.error_type == "no_results"

    @pytest.mark.asyncio
    async def test_source_down(self):
        with patch(
            "src.tools.tmview.search_trademarks",
            AsyncMock(side_effect=httpx.RequestError("timeout")),
        ):
            result = await _cerca_marchi_impl("FUORI CORSO")
        assert result.success is False
        assert result.error_type == "source_down"

    @pytest.mark.asyncio
    async def test_waf_block_message(self):
        with patch(
            "src.tools.tmview.search_trademarks",
            AsyncMock(side_effect=TMviewBlockedError("blocked")),
        ):
            result = await _cerca_marchi_impl("FUORI CORSO")
        assert result.success is False
        assert result.error_type == "source_down"
        assert "riprova" in result.to_str().lower()


class TestLeggiMarchioImpl:
    @pytest.mark.asyncio
    async def test_success(self):
        detail = _parse_detail_response(_DETAIL_RESPONSE)
        with patch("src.tools.tmview.fetch_trademark", AsyncMock(return_value=detail)):
            result = await _leggi_marchio_impl("IT502013902128590")
        assert result.success is True
        assert "MENNUCCI" in result.results_text

    @pytest.mark.asyncio
    async def test_source_down(self):
        with patch(
            "src.tools.tmview.fetch_trademark",
            AsyncMock(side_effect=httpx.RequestError("boom")),
        ):
            result = await _leggi_marchio_impl("IT502013902128590")
        assert result.success is False
        assert result.error_type == "source_down"


class TestVerificaAnterioritaImpl:
    @pytest.mark.asyncio
    async def test_classifies_identical_and_similar(self):
        _, results = _parse_search_response(_SEARCH_RESPONSE)
        with patch("src.tools.tmview.search_trademarks", AsyncMock(return_value=(9, results))):
            result = await _verifica_anteriorita_marchio_impl("FUORI CORSO")
        assert result.success is True
        text = result.results_text
        # the two word marks "FUORICORSO" normalize-match "FUORI CORSO" → identici
        assert "identic" in text.lower()
        assert "IT501999900797027" in text
        assert "CH502024000017249" in text
        # the figurative one whose tmName is a long description is only similar
        assert "IT502024000072490" in text

    @pytest.mark.asyncio
    async def test_reports_class_overlap(self):
        _, results = _parse_search_response(_SEARCH_RESPONSE)
        with patch("src.tools.tmview.search_trademarks", AsyncMock(return_value=(9, results))):
            result = await _verifica_anteriorita_marchio_impl("FUORI CORSO", classi_nizza="25")
        assert "25" in result.results_text

    @pytest.mark.asyncio
    async def test_no_results_is_green_light(self):
        with patch("src.tools.tmview.search_trademarks", AsyncMock(return_value=(0, []))):
            result = await _verifica_anteriorita_marchio_impl("XKCD9999")
        assert result.success is True
        assert "nessun" in result.results_text.lower()

    @pytest.mark.asyncio
    async def test_disclaimer_present(self):
        with patch("src.tools.tmview.search_trademarks", AsyncMock(return_value=(0, []))):
            result = await _verifica_anteriorita_marchio_impl("XKCD9999")
        assert "preliminare" in result.results_text.lower()

    @pytest.mark.asyncio
    async def test_source_down(self):
        with patch(
            "src.tools.tmview.search_trademarks",
            AsyncMock(side_effect=httpx.RequestError("timeout")),
        ):
            result = await _verifica_anteriorita_marchio_impl("FUORI CORSO")
        assert result.success is False
        assert result.error_type == "source_down"


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

class TestConstants:
    def test_stati_mapping(self):
        assert STATI["registrato"] == "Registered"
        assert STATI["depositato"] == "Filed"
        assert STATI["scaduto"] == "Expired"
        assert STATI["terminato"] == "Ended"

    def test_stato_labels_roundtrip(self):
        for code in STATI.values():
            assert code in STATO_LABELS_IT


# ---------------------------------------------------------------------------
# Live guard-rail (run before releases: pytest -m live)
# TMview's WAF blocks bursts: run these sparingly, not in tight loops.
# ---------------------------------------------------------------------------

@pytest.mark.live
class TestLive:
    @pytest.mark.asyncio
    async def test_search_live(self):
        total, results = await search_trademarks("FUORI CORSO", offices=["IT"])
        assert total >= 1
        assert results
        assert results[0].st13.startswith("IT")

    @pytest.mark.asyncio
    async def test_detail_live(self):
        detail = await fetch_trademark("IT502013902128590")
        assert detail.name == "FUORICORSO"
        assert detail.applicants
        assert any(nc == "25" for nc, _ in detail.goods_services)

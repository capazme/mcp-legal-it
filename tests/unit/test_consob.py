"""Unit tests for CONSOB (Commissione Nazionale per le Societa e la Borsa) scraper.

Tests are written against mocked httpx responses — no real network calls.
HTML fixtures mirror the actual Liferay portlet structure of consob.it.
"""

import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch

from src.lib.consob.client import (
    ARGOMENTI,
    TIPOLOGIE,
    DocResult,
    _build_search_params,
    _parse_doc,
    _parse_results,
    format_full,
    format_result,
)

from src.tools.consob import (
    _cerca_delibere_consob_impl,
    _leggi_delibera_consob_impl,
    _ultime_delibere_consob_impl,
)


# ---------------------------------------------------------------------------
# HTML fixtures
# ---------------------------------------------------------------------------

_SEARCH_HTML = """
<html><body>
<div class="ricercaBollettino">
<div class="container100">
<ul>

<li>
<div class="journal-content-article" data-analytics-asset-id="7421465" data-analytics-asset-title="Delibera n. 23257" data-analytics-asset-type="web-content">
<div class="div100 j">
<b>
<a href="https://www.consob.it/web/area-pubblica/-/delibera-n.-23257?redirect=%2Fweb%2Farea-pubblica%2Fbollettino">Delibera n. 23257, adozione di una sanzione amministrativa pecuniaria nei confronti della sig.ra Giorgia Volterrani per violazioni dell'art. 19 del Regolamento (UE) n. 596/2014 relativo agli abusi di mercato</a>
</b>
<p class="dwn">
		Data: 18/09/2024
	</p>
<p class="dwn">
		Data Pubblicazione: 09/10/2024
	</p>
</div>
</div>
</li>

<li>
<div class="journal-content-article" data-analytics-asset-id="7421470" data-analytics-asset-title="Delibera n. 23175" data-analytics-asset-type="web-content">
<div class="div100 j">
<b>
<a href="https://www.consob.it/web/area-pubblica/-/delibera-n.-23175?redirect=%2Fweb%2Farea-pubblica%2Fbollettino">Delibera n. 23175, applicazione di sanzioni amministrative nei confronti dei Sig.ri Giacomo Garbuglia e Giuseppe Roveda</a>
</b>
<p class="dwn">
		Data: 19/06/2024
	</p>
<p class="dwn">
		Data Pubblicazione: 08/10/2024
	</p>
</div>
</div>
</li>

</ul>
</div>
</div>

<div class="journal-content-article" data-analytics-asset-id="2023881" data-analytics-asset-title="footer" data-analytics-asset-type="web-content">
<div class="info-footer"><ul><li>CONSOB</li></ul></div>
</div>

</body></html>
"""

_SEARCH_HTML_EMPTY = """
<html><body>
<div class="ricercaBollettino">
<div class="container100"><ul></ul></div>
</div>
</body></html>
"""

_DOC_HTML = """
<html><body>
<script>var x = 1;</script>
<nav>Menu navigazione</nav>
<div class="journal-content-article" data-analytics-asset-id="7421465" data-analytics-asset-title="Delibera n. 23257" data-analytics-asset-type="web-content">
Bollettino &laquo; Indietro
Delibera n. 23257
Adozione di una sanzione amministrativa pecuniaria nei confronti della sig.ra
Giorgia Volterrani per violazioni dell'art. 19 del Regolamento (UE) n. 596/2014.

LA COMMISSIONE NAZIONALE PER LE SOCIETA E LA BORSA
VISTA la Legge 7 giugno 1974, n. 216;
VISTO il Regolamento (UE) n. 596/2014 del Parlamento europeo;
CONSIDERATO che la sig.ra Volterrani non ha comunicato operazioni sospette;
DELIBERA di irrogare una sanzione pecuniaria di euro 50.000.
</div>

<div class="journal-content-article" data-analytics-asset-id="2023881" data-analytics-asset-title="footer" data-analytics-asset-type="web-content">
<div class="info-footer">CONSOB</div>
</div>
</body></html>
"""

_DOC_HTML_VARIANT = """
<html><body>
<div class="journal-content-article" data-analytics-asset-id="1234" data-analytics-asset-title="Delibera n. 23256-1" data-analytics-asset-type="web-content">
Bollettino &laquo; Indietro
Delibera n. 23256-1
Testo della delibera variante.
</div>
</body></html>
"""


# ---------------------------------------------------------------------------
# Tests: _build_search_params
# ---------------------------------------------------------------------------

class TestBuildSearchParams:
    def test_basic_keywords(self):
        params = _build_search_params(keywords="abusi di mercato")
        assert params["_it_consob_BollettinoRicercaPortlet_keywords"] == "abusi di mercato"
        assert params["p_p_id"] == "it_consob_BollettinoRicercaPortlet"
        assert params["_it_consob_BollettinoRicercaPortlet_cur"] == "1"

    def test_pagination(self):
        params = _build_search_params(keywords="test", cur=3, delta=20)
        assert params["_it_consob_BollettinoRicercaPortlet_cur"] == "3"
        assert params["_it_consob_BollettinoRicercaPortlet_delta"] == "20"

    def test_date_filters(self):
        params = _build_search_params(start_date="2023-01-01", end_date="2024-12-31")
        assert params["_it_consob_BollettinoRicercaPortlet_startDate"] == "2023-01-01"
        assert params["_it_consob_BollettinoRicercaPortlet_endDate"] == "2024-12-31"

    def test_tipologia_filter(self):
        params = _build_search_params(tipologia="delibera")
        assert params["_it_consob_BollettinoRicercaPortlet_tipologia"] == "delibera"

    def test_argomento_filter(self):
        params = _build_search_params(argomento_id="4989535")
        assert params["_it_consob_BollettinoRicercaPortlet_argomento"] == "4989535"

    def test_mvcRenderCommandName(self):
        params = _build_search_params(keywords="test")
        assert params["_it_consob_BollettinoRicercaPortlet_mvcRenderCommandName"] == "/search"


# ---------------------------------------------------------------------------
# Tests: _parse_results
# ---------------------------------------------------------------------------

class TestParseResults:
    def test_parses_two_results(self):
        results = _parse_results(_SEARCH_HTML)
        assert len(results) == 2

    def test_first_result_fields(self):
        results = _parse_results(_SEARCH_HTML)
        doc = results[0]
        assert doc.numero == "23257"
        assert "Volterrani" in doc.title
        assert "abusi di mercato" in doc.title.lower()
        assert doc.date == "18/09/2024"
        assert doc.data_pubblicazione == "09/10/2024"

    def test_second_result_fields(self):
        results = _parse_results(_SEARCH_HTML)
        doc = results[1]
        assert doc.numero == "23175"
        assert "Garbuglia" in doc.title
        assert doc.date == "19/06/2024"

    def test_skips_footer(self):
        results = _parse_results(_SEARCH_HTML)
        numeri = [r.numero for r in results]
        assert all(n.isdigit() for n in numeri)

    def test_empty_html_returns_empty_list(self):
        results = _parse_results(_SEARCH_HTML_EMPTY)
        assert results == []

    def test_malformed_html(self):
        html = "<html><body><div class='journal-content-article'><p>No link</p></div></body></html>"
        results = _parse_results(html)
        assert results == []


# ---------------------------------------------------------------------------
# Tests: _parse_doc
# ---------------------------------------------------------------------------

class TestParseDoc:
    def test_extracts_title(self):
        title, text = _parse_doc(_DOC_HTML, "23257")
        assert "23257" in title

    def test_removes_scripts_and_nav(self):
        _, text = _parse_doc(_DOC_HTML, "23257")
        assert "var x" not in text
        assert "Menu navigazione" not in text

    def test_removes_breadcrumb(self):
        _, text = _parse_doc(_DOC_HTML, "23257")
        assert not text.startswith("Bollettino")

    def test_body_text_contains_content(self):
        _, text = _parse_doc(_DOC_HTML, "23257")
        assert "COMMISSIONE NAZIONALE" in text
        assert "50.000" in text
        assert "Volterrani" in text

    def test_variant_numero(self):
        title, text = _parse_doc(_DOC_HTML_VARIANT, "23256-1")
        assert "23256-1" in title
        assert "variante" in text.lower()

    def test_fallback_title_when_no_article(self):
        html = "<html><body><p>Solo testo</p></body></html>"
        title, _ = _parse_doc(html, "99999")
        assert "99999" in title

    def test_multiple_newlines_collapsed(self):
        html = """<html><body>
        <div class="journal-content-article" data-analytics-asset-title="Test">
        <p>a</p><p></p><p></p><p></p><p>b</p>
        </div></body></html>"""
        _, text = _parse_doc(html, "1")
        assert "\n\n\n" not in text

    def test_skips_footer_article(self):
        _, text = _parse_doc(_DOC_HTML, "23257")
        assert "info-footer" not in text


# ---------------------------------------------------------------------------
# Tests: format_result
# ---------------------------------------------------------------------------

class TestFormatResult:
    def test_contains_numero_and_title(self):
        doc = DocResult(
            numero="23257",
            title="Delibera n. 23257, sanzione per abusi di mercato",
            date="18/09/2024",
            data_pubblicazione="09/10/2024",
        )
        text = format_result(doc)
        assert "23257" in text
        assert "18/09/2024" in text
        assert "09/10/2024" in text
        assert "abusi di mercato" in text

    def test_url_in_output(self):
        doc = DocResult(numero="23175", title="T", date="")
        text = format_result(doc)
        assert "consob.it" in text
        assert "23175" in text

    def test_long_title_truncated(self):
        doc = DocResult(numero="1", title="x" * 500, date="")
        text = format_result(doc)
        # Title should be truncated to 300
        assert len(text) < 600


# ---------------------------------------------------------------------------
# Tests: format_full
# ---------------------------------------------------------------------------

class TestFormatFull:
    def test_basic_formatting(self):
        result = format_full("Delibera n. 23257", "Testo della delibera.", "23257")
        assert "# Delibera n. 23257" in result
        assert "23257" in result
        assert "Testo della delibera." in result

    def test_truncation_note(self):
        long_text = "a" * 9000
        result = format_full("T", long_text, "1")
        assert "Testo troncato" in result
        assert "8000" in result

    def test_no_truncation_note_for_short_text(self):
        result = format_full("T", "breve testo", "1")
        assert "troncato" not in result


# ---------------------------------------------------------------------------
# Tests: TIPOLOGIE and ARGOMENTI dicts
# ---------------------------------------------------------------------------

class TestDicts:
    def test_tipologie_has_delibere(self):
        assert "delibere" in TIPOLOGIE
        assert TIPOLOGIE["delibere"] == "delibera"

    def test_argomenti_has_abusi(self):
        assert "abusi_di_mercato" in ARGOMENTI
        assert ARGOMENTI["abusi_di_mercato"] == "4989535"

    def test_argomenti_has_10_entries(self):
        assert len(ARGOMENTI) == 10


# ---------------------------------------------------------------------------
# Tests: _impl functions (mocked httpx)
# ---------------------------------------------------------------------------

def _make_mock_response(html: str, status: int = 200):
    resp = MagicMock()
    resp.status_code = status
    resp.text = html
    resp.raise_for_status = MagicMock()
    return resp


class TestCercaDelibereImpl:
    @pytest.mark.asyncio
    async def test_returns_results(self):
        mock_resp = _make_mock_response(_SEARCH_HTML)
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("src.lib.consob.client.httpx.AsyncClient", return_value=mock_client):
            result = await _cerca_delibere_consob_impl("abusi di mercato")

        assert "Trovate" in result
        assert "Volterrani" in result

    @pytest.mark.asyncio
    async def test_empty_results(self):
        mock_resp = _make_mock_response(_SEARCH_HTML_EMPTY)
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("src.lib.consob.client.httpx.AsyncClient", return_value=mock_client):
            result = await _cerca_delibere_consob_impl("inesistente")

        assert "Nessuna" in result

    @pytest.mark.asyncio
    async def test_tipologia_filter(self):
        mock_resp = _make_mock_response(_SEARCH_HTML)
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("src.lib.consob.client.httpx.AsyncClient", return_value=mock_client):
            result = await _cerca_delibere_consob_impl("abusi", tipologia="delibere")

        # Tipologia is sent as search param, not filtered client-side
        assert "Trovate" in result or "Nessuna" in result

    @pytest.mark.asyncio
    async def test_argomento_resolution(self):
        mock_resp = _make_mock_response(_SEARCH_HTML)
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("src.lib.consob.client.httpx.AsyncClient", return_value=mock_client):
            await _cerca_delibere_consob_impl("test", argomento="abusi_di_mercato")

        # Should resolve "abusi_di_mercato" to "4989535" and pass to search
        mock_client.get.assert_called_once()
        call_args = mock_client.get.call_args
        # params passed as keyword arg to client.get(url, params=...)
        params = call_args.kwargs.get("params", {})
        if not params and len(call_args.args) > 1:
            params = call_args.args[1]
        # The argomento ID should appear somewhere in the URL or params
        url_called = call_args.args[0] if call_args.args else ""
        assert "4989535" in str(params) or "4989535" in url_called

    @pytest.mark.asyncio
    async def test_http_error_returns_message(self):
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(side_effect=httpx.RequestError("timeout"))

        with patch("src.lib.consob.client.httpx.AsyncClient", return_value=mock_client):
            result = await _cerca_delibere_consob_impl("test")

        assert "Errore" in result


class TestLeggiDeliberaImpl:
    @pytest.mark.asyncio
    async def test_returns_full_text(self):
        mock_resp = _make_mock_response(_DOC_HTML)
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("src.lib.consob.client.httpx.AsyncClient", return_value=mock_client):
            result = await _leggi_delibera_consob_impl("23257")

        assert "23257" in result
        assert "Volterrani" in result
        assert "50.000" in result

    @pytest.mark.asyncio
    async def test_http_error_returns_message(self):
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_404 = MagicMock()
        mock_404.status_code = 404
        mock_client.get = AsyncMock(side_effect=httpx.HTTPStatusError(
            "404", request=MagicMock(), response=mock_404
        ))

        with patch("src.lib.consob.client.httpx.AsyncClient", return_value=mock_client):
            result = await _leggi_delibera_consob_impl("99999")

        assert "Errore" in result


class TestUltimeDelibereImpl:
    @pytest.mark.asyncio
    async def test_returns_latest(self):
        mock_resp = _make_mock_response(_SEARCH_HTML)
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("src.lib.consob.client.httpx.AsyncClient", return_value=mock_client):
            result = await _ultime_delibere_consob_impl()

        assert "Ultime delibere" in result
        assert "Volterrani" in result

    @pytest.mark.asyncio
    async def test_http_error(self):
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(side_effect=httpx.RequestError("connection refused"))

        with patch("src.lib.consob.client.httpx.AsyncClient", return_value=mock_client):
            result = await _ultime_delibere_consob_impl()

        assert "Errore" in result


# ---------------------------------------------------------------------------
# Non-delibera documents of the Bollettino (comunicazioni, richiami, avvisi)
# ---------------------------------------------------------------------------
#
# Fixtures mirror the real markup of the Bollettino search page (checked on 2026-09-29): every
# href carries a long ?redirect= back-link to the search, and only some delibere live at
# /-/delibera-n.-<n>. The other documents have their own slug and their own numbering
# ("13/25", "0117520", none at all). Source: CONSOB, Bollettino elettronico,
# https://www.consob.it/web/area-pubblica/bollettino/ricerca

_BASE_DOC = "https://www.consob.it/web/area-pubblica/-/"
_REDIRECT = "?redirect=%2Fweb%2Farea-pubblica%2Fbollettino%2Fricerca%3Fp_p_id%3Dit_consob_BollettinoRicercaPortlet"


def _article(asset_title: str, slug: str, title: str, data: str, pub: str) -> str:
    return f"""
<li>
<div class="journal-content-article " data-analytics-asset-id="1" data-analytics-asset-title="{asset_title}" data-analytics-asset-type="web-content">
<div class="div100 j"><b><a href="{_BASE_DOC}{slug}{_REDIRECT}">{title}</a></b>
<p class="dwn">Data: {data}</p>
<p class="dwn">Data Pubblicazione: {pub}</p>
</div></div></li>"""


def _page(*articles: str) -> str:
    return "<html><body><ul>" + "".join(articles) + "</ul></body></html>"


_JULY_2025 = _page(
    _article("Richiamo di attenzione n. 14/25 del 7 luglio 2025",
             "richiamo-di-attenzione-n-14-25-del-7-luglio-2025",
             "Richiamo di attenzione n. 14/25 del 7 luglio 2025, prestiti obbligazionari convertibili",
             "07/07/2025", "07/07/2025"),
    _article("Comunicazione n. 13/25 del 4 luglio 2025",
             "comunicazione-n-13-25-del-4-luglio-2025",
             "Comunicazione n. 13/25 del 4 luglio 2025 - Operazioni di rafforzamento patrimoniale",
             "04/07/2025", "07/07/2025"),
    _article("Avviso Consob del 1 luglio 2025",
             "avviso-consob-del-1-luglio-2025",
             "Avviso Consob del 1° luglio 2025 in merito agli Orientamenti ESMA",
             "01/07/2025", "01/07/2025"),
)


class TestNonDeliberaDocuments:
    def test_comunicazione_keeps_type_full_number_and_real_href(self):
        # Bollettino: "Comunicazione n. 13/25 del 4 luglio 2025"; the page is
        # /-/comunicazione-n-13-25-del-4-luglio-2025 (HTTP 200), while /-/delibera-n.-13 is 404.
        docs = {d.numero: d for d in _parse_results(_JULY_2025) if d.numero}
        com = docs["13/25"]
        assert com.tipo == "Comunicazione"
        assert com.designazione == "Comunicazione n. 13/25"
        assert com.href == _BASE_DOC + "comunicazione-n-13-25-del-4-luglio-2025"
        assert "?" not in com.href
        assert com.date == "04/07/2025" and com.data_pubblicazione == "07/07/2025"

    def test_richiamo_di_attenzione_is_not_a_delibera(self):
        richiamo = _parse_results(_JULY_2025)[0]
        assert (richiamo.tipo, richiamo.numero) == ("Richiamo di attenzione", "14/25")
        assert richiamo.href == _BASE_DOC + "richiamo-di-attenzione-n-14-25-del-7-luglio-2025"

    def test_unnumbered_avviso_is_kept_and_designated_by_its_date(self):
        # The old parser dropped every result without "n. <digits>": the newest comunicazioni
        # of the Bollettino ("Avviso Consob del 1 luglio 2025") were silently missing.
        avviso = _parse_results(_JULY_2025)[2]
        assert avviso.numero == ""
        assert avviso.designazione == "Avviso Consob del 1° luglio 2025"
        assert avviso.href == _BASE_DOC + "avviso-consob-del-1-luglio-2025"

    def test_protocol_number_keeps_leading_zeros_and_year_suffix(self):
        html = _page(
            _article("Comunicazione n. 0117520 dell’11 dicembre 2025",
                     "comunicazione-n.-0117520-dell-11-dicembre-2025",
                     "Comunicazione n. 0117520 dell’11 dicembre 2025 - […società B…]",
                     "11/12/2025", "20/01/2026"),
            _article("Comunicazione n. 0104577/24 del 14 novembre 2024",
                     "comunicazione-n.-0104577/24-del-14-novembre-2024",
                     "Comunicazione n. 0104577/24 del 14 novembre 2024 - […società A…]",
                     "14/11/2024", "19/12/2024"),
        )
        first, second = _parse_results(html)
        assert first.numero == "0117520" and first.tipo == "Comunicazione"
        assert second.numero == "0104577/24"

    def test_placeholder_asset_title_is_replaced_by_the_real_title(self):
        # Older items carry the CMS placeholder "Comunicazione comunicazione cg n. 0" as asset
        # title; the visible title ("Avviso Consob del 27 settembre 2023 ...") is the real one.
        html = _page(_article(
            "Comunicazione comunicazione cg n. 0", "comunicazione-comunicazione-cg-n.-0-38",
            "Avviso Consob del 27 settembre 2023 in merito all'aggiornamento degli Orientamenti",
            "27/09/2023", "02/10/2023",
        ))
        (doc,) = _parse_results(html)
        assert doc.designazione == "Avviso Consob del 27 settembre 2023"
        assert doc.numero == ""

    def test_title_without_date_falls_back_to_a_clean_asset_title(self):
        html = _page(_article(
            "Orientamenti di vigilanza Consob-Banca d’Italia del 23 marzo 2026",
            "orientamenti-di-vigilanza-consob-banca-d-italia-del-23-marzo-2026-1",
            "Orientamenti di vigilanza Consob-Banca d’Italia in materia di Società quotate",
            "23/03/2026", "10/04/2026",
        ))
        (doc,) = _parse_results(html)
        assert doc.designazione == "Orientamenti di vigilanza Consob-Banca d’Italia del 23 marzo 2026"

    def test_delibera_with_undotted_slug_is_still_a_delibera(self):
        # In 2025 the Bollettino uses /-/delibera-n-23674 (no dot) for some delibere.
        html = _page(_article(
            "Delibera n. 23674", "delibera-n-23674",
            "Delibera n. 23674, ordine, ai sensi dell'art. 7-octies", "24/09/2025", "25/09/2025",
        ))
        (doc,) = _parse_results(html)
        assert (doc.tipo, doc.numero) == ("Delibera", "23674")
        assert doc.href == _BASE_DOC + "delibera-n-23674"

    def test_format_result_uses_the_real_link_and_type(self):
        com = _parse_results(_JULY_2025)[1]
        text = format_result(com)
        assert text.splitlines()[0] == "### Comunicazione n. 13/25"
        assert f"({_BASE_DOC}comunicazione-n-13-25-del-4-luglio-2025)" in text
        # The rebuilt /delibera-n.-13 answers HTTP 404: it must never be emitted.
        assert "delibera-n.-13" not in text
        assert "non e' una delibera" in text

    def test_format_result_of_a_delibera_is_unchanged(self):
        html = _page(_article(
            "Delibera n. 20307", "delibera-n.-20307",
            "Delibera n. 20307, regolamento recante norme di attuazione", "15/02/2018", "16/02/2018",
        ))
        text = format_result(_parse_results(html)[0])
        assert text.splitlines()[0] == "### Delibera n. 20307"
        assert f"({_BASE_DOC}delibera-n.-20307)" in text
        assert "non e' una delibera" not in text

    def test_format_result_legacy_docresult_still_builds_the_delibera_link(self):
        # A DocResult built without href/tipo (older callers) keeps the /delibera-n.- link.
        text = format_result(DocResult(numero="23175", title="T", date=""))
        assert text.splitlines()[0] == "### Delibera n. 23175"
        assert "https://www.consob.it/web/area-pubblica/-/delibera-n.-23175" in text


class TestNonDeliberaImpl:
    @staticmethod
    def _patched(html: str):
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=_make_mock_response(html))
        return patch("src.lib.consob.client.httpx.AsyncClient", return_value=mock_client)

    @pytest.mark.asyncio
    async def test_search_labels_comunicazioni_and_keeps_every_document(self):
        with self._patched(_JULY_2025):
            result = await _cerca_delibere_consob_impl("", tipologia="comunicazioni")
        assert "Trovati 3 documenti del Bollettino CONSOB" in result
        assert "### Comunicazione n. 13/25" in result
        assert "### Richiamo di attenzione n. 14/25" in result
        assert "### Avviso Consob del 1° luglio 2025" in result
        assert "### Delibera n." not in result
        assert "delibera-n.-13" not in result and "delibera-n.-14" not in result

    @pytest.mark.asyncio
    async def test_latest_labels_comunicazioni(self):
        with self._patched(_JULY_2025):
            result = await _ultime_delibere_consob_impl(tipologia="comunicazioni")
        assert "Ultimi documenti del Bollettino CONSOB" in result
        assert "### Comunicazione n. 13/25" in result

    @pytest.mark.asyncio
    async def test_same_number_in_different_years_is_not_merged(self):
        # "n. 13/24" and "n. 13/25" (and Delibera n. 13) are three documents: the old
        # deduplication on the truncated number "13" kept only the first.
        html = _page(
            _article("Comunicazione n. 13/25 del 4 luglio 2025", "comunicazione-n-13-25-del-4-luglio-2025",
                     "Comunicazione n. 13/25 del 4 luglio 2025 - A", "04/07/2025", "07/07/2025"),
            _article("Comunicazione n. 13/24 del 4 luglio 2024", "comunicazione-n-13-24-del-4-luglio-2024",
                     "Comunicazione n. 13/24 del 4 luglio 2024 - B", "04/07/2024", "07/07/2024"),
            _article("Delibera n. 13", "delibera-n.-13", "Delibera n. 13, C", "01/01/1990", "01/01/1990"),
        )
        with self._patched(html):
            result = await _cerca_delibere_consob_impl("13")
        assert "### Comunicazione n. 13/25" in result
        assert "### Comunicazione n. 13/24" in result
        assert "### Delibera n. 13\n" in result

    @pytest.mark.asyncio
    async def test_delibere_only_keeps_the_original_header(self):
        with self._patched(_SEARCH_HTML):
            result = await _cerca_delibere_consob_impl("abusi di mercato")
        assert result.startswith("**Trovate 2 delibere CONSOB per**")

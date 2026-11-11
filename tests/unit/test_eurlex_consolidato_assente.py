"""A consolidation CELLAR lists but does not serve (#163).

CELLAR's SPARQL lists, for reg. (UE) 2022/858 and 2025/1106, a consolidation that folds a
corrigendum in (``02022R0858-20220602``), whose sector-0 CELEX answers 404 in every language
(checked 11 November 2026), while the Official Journal text is there. ``cite_law`` answered
with httpx's raw «Client error '404 '» line. Now a consolidation the reader chose falls back
to the OJ text, said; a version the caller named is not replaced; anything else is a
readable error. CELLAR is faked here with the e-privacy fixtures (OJ and consolidated pages).
"""

from pathlib import Path

import httpx
import pytest

import mcp_legal_it.server  # noqa: F401  (registers every tool module first: avoids a circular import)
from mcp_legal_it.lib.visualex import eurlex_consolidate, scraper
from mcp_legal_it.lib.visualex.models import Norma, NormaVisitata
from mcp_legal_it.tools import legal_citations as lc

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "visualex" / "eurlex"
CELLAR = "https://publications.europa.eu/resource/celex/"
CONSOLIDATO = "02002L0058-20091219"
OJ = (FIXTURES / "eprivacy_oj_legacy.html").read_text(encoding="utf-8")
INFO = {"data_gu": "2002-07-31", "in_vigore_dal": "2002-07-31", "versioni": [
    {"celex": CONSOLIDATO, "data": "2009-12-19",
     "modifiche": [{"celex": "32009L0136", "atto": "direttiva 2009/136"}]}]}

pytestmark = pytest.mark.consolidazioni_reali  # the lookup is stubbed here, with INFO


def _cellar(monkeypatch, risposte: dict, *, consolidazioni=INFO):
    """CELLAR answering each CELEX of *risposte* with ``(status, page)`` or an exception."""
    chieste: list = []

    async def handler(request):
        url = str(request.url)
        chieste.append(url)
        risposta = risposte[url.removeprefix(CELLAR)]
        if isinstance(risposta, Exception):
            raise risposta
        status, testo = risposta
        return httpx.Response(status, text=testo)

    def factory(fonte, **kwargs):
        kwargs.pop("verify", None)
        return httpx.AsyncClient(transport=httpx.MockTransport(handler), **kwargs)

    async def info(celex_base):
        return consolidazioni

    monkeypatch.setattr(scraper, "async_client", factory)
    monkeypatch.setattr(eurlex_consolidate, "consolidazioni", info)
    return chieste


def _articolo(numero="5", **norma):
    return NormaVisitata(norma=Norma(tipo_atto="direttiva ue", data="2002", numero_atto="58", **norma),
                         numero_articolo=numero)


class TestRipiego:
    async def test_the_oj_text_is_served_with_its_notice(self, monkeypatch):
        chieste = _cellar(monkeypatch, {CONSOLIDATO: (404, ""), "32002L0058": (200, OJ)})
        r = await scraper.fetch_article(_articolo())
        assert r["text"].startswith("Articolo 5"), r
        assert r["consolidato"] is None and r["consolidato_verificato"] is True
        assert any("CELLAR non pubblica" in a and "direttiva 2009/136" in a for a in r["avvisi_ue"])
        assert chieste == [CELLAR + CONSOLIDATO, CELLAR + "32002L0058"]
        assert r["url"].endswith("CELEX:32002L0058")

    async def test_cite_law_says_it(self, monkeypatch):
        _cellar(monkeypatch, {CONSOLIDATO: (404, ""), "32002L0058": (200, OJ)})
        out = await lc._cite_law_impl("art. 5 direttiva 2002/58/CE")
        assert "Client error" not in out and "404 '" not in out
        assert "CELLAR non pubblica" in out and "Articolo 5" in out
        assert "Testo consolidato" not in out

    async def test_the_tree_falls_back_too(self, monkeypatch):
        _cellar(monkeypatch, {CONSOLIDATO: (404, ""), "32002L0058": (200, OJ)})
        r = await scraper.fetch_eurlex_tree(Norma(tipo_atto="direttiva ue", data="2002", numero_atto="58"))
        assert r.get("count") and not r.get("error"), r
        assert r["consolidato"] is None


class TestErroriLeggibili:
    async def test_the_oj_failing_too_is_a_readable_error(self, monkeypatch):
        _cellar(monkeypatch, {CONSOLIDATO: (404, ""), "32002L0058": (503, "")})
        r = await scraper.fetch_article(_articolo())
        assert r["text"] == "" and r["esito"] == scraper.CHECK_UNAVAILABLE
        assert "CELLAR risponde HTTP 503" in r["error"] and "32002L0058" in r["error"]
        assert "Client error" not in r["error"] and "Server error" not in r["error"]

    async def test_a_named_version_is_never_replaced(self, monkeypatch):
        chieste = _cellar(monkeypatch, {CONSOLIDATO: (404, "")})
        r = await scraper.fetch_article(_articolo(celex_consolidated=CONSOLIDATO))
        assert r["text"] == "" and r["esito"] == scraper.ARTICLE_NOT_FOUND
        assert f"CELEX {CONSOLIDATO}" in r["error"] and "non è pubblicata su CELLAR" in r["error"]
        assert chieste == [CELLAR + CONSOLIDATO]  # the OJ text is not read in its place

    async def test_a_timeout_is_a_readable_error(self, monkeypatch):
        _cellar(monkeypatch, {"32002L0058": httpx.ConnectTimeout("timed out")}, consolidazioni=None)
        r = await scraper.fetch_article(_articolo())
        assert r["esito"] == scraper.CHECK_UNAVAILABLE
        assert "CELLAR non risponde (ConnectTimeout)" in r["error"]

    async def test_cite_law_prints_the_readable_error(self, monkeypatch):
        _cellar(monkeypatch, {CONSOLIDATO: (404, ""), "32002L0058": (502, "")})
        out = await lc._cite_law_impl("art. 5 direttiva 2002/58/CE")
        assert out.startswith("**Errore**: testo di") and "Riprova più tardi" in out
        assert "developer.mozilla.org" not in out

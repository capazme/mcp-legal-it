"""A request without a date is the text in force today, even when Normattiva's undated page is not.

Measured live on 21/10/2026: the undated page of art. 3 d.P.R. 131/1986 states «Testo in vigore
dal: 01-01-2027» and holds «((ARTICOLO ABROGATO DAL D.LGS. 1 AGOSTO 2025, N. 123, COME
MODIFICATO DAL D.L. 31 DICEMBRE 2025, N. 200))»: tomorrow's text. Today the article is in
force; the page at today's date ("!vig=") serves it. No network: the pages are built in the
portal's markup (``validity_pages``), shaped like the real ones.
"""

import httpx
import pytest

from mcp_legal_it import api
from mcp_legal_it.lib.visualex import akn_fetch, pagine_normattiva, scraper
from mcp_legal_it.lib.visualex.akn_parser import ParsedAct

from .validity_pages import synthetic

pytestmark = pytest.mark.finestra_reale

OGGI = "2026-10-21"
DPR131 = "decreto.del.presidente.della.repubblica:1986-04-26;131~art3"

#: The undated page: the version in force from 2027, the repeal.
FUTURA = synthetic(dal="01-01-2027", label="Art. 3", updated="06/08/2026",
                   content='<div class="ins-akn art_abrogato-akn">((ARTICOLO ABROGATO DAL D.LGS. 1 AGOSTO '
                           "2025, N. 123, COME MODIFICATO DAL D.L. 31 DICEMBRE 2025, N. 200))</div>")
#: The page at today's date: the text in force today.
OGGI_PAGINA = synthetic(dal="30-12-2025", label="Art. 3", updated="06/08/2026",
                        content='<span class="art-just-text-akn">(Atti soggetti a registrazione). Sono '
                                "soggetti a registrazione gli atti indicati nella tariffa.</span>")


@pytest.fixture(autouse=True)
def _oggi(monkeypatch):
    monkeypatch.setenv("LEGAL_TODAY", OGGI)


def _serve(monkeypatch, pagine: dict, act=None):
    """Normattiva pages by the URN after "urn:nir:stato:" (a page, or an exception to raise)."""
    richieste: list[str] = []

    class _Risposta:
        def __init__(self, url, text):
            self.url, self.text, self.status_code = url, text, 200

        def raise_for_status(self):
            return None

    class _Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def get(self, url):
            richieste.append(url.split("urn:nir:stato:", 1)[-1])
            pagina = pagine.get(richieste[-1])
            if pagina is None:
                raise AssertionError(f"unexpected request: {url}")
            if isinstance(pagina, Exception):
                raise pagina
            return _Risposta(url, pagina)

    async def fake_akn(norma, data_vigenza=None):
        return act

    monkeypatch.delenv("AKN_DISABLED", raising=False)
    monkeypatch.setattr(scraper.httpx, "AsyncClient", _Client)
    monkeypatch.setattr(akn_fetch, "fetch_act_akn", fake_akn)
    pagine_normattiva.svuota_memoria()
    return richieste


def _dpr131():
    return api.riferimento_da_parametri("decreto del presidente della repubblica", "3", data="1986-04-26",
                                        numero_atto="131").norma_data[0]


class TestAFutureVersion:
    async def test_the_text_in_force_today_is_served(self, monkeypatch):
        richieste = _serve(monkeypatch, {DPR131: FUTURA, f"{DPR131}!vig={OGGI}": OGGI_PAGINA})
        t = await api.testo_articolo(_dpr131(), canale="html")
        assert richieste == [DPR131, f"{DPR131}!vig={OGGI}"]  # one request more, only here
        assert t.esito == "trovato" and t.fonte == "normattiva"
        assert "Sono soggetti a registrazione" in t.article_text and "ABROGATO" not in t.article_text
        assert t.url.endswith(f"~art3!vig={OGGI}")
        assert t.precisione == "ESATTO"
        assert t.validity.state == "current" and t.validity.valid_from == "2025-12-30"

    async def test_the_coming_version_is_said_and_its_successor_derived(self, monkeypatch):
        _serve(monkeypatch, {DPR131: FUTURA, f"{DPR131}!vig={OGGI}": OGGI_PAGINA})
        t = await api.testo_articolo(_dpr131(), canale="html")
        assert t.avvisi == (
            "Normattiva mostra senza data il testo in vigore dal 2027-01-01 (abrogato dal D.LGS. 1 AGOSTO "
            "2025, N. 123, COME MODIFICATO DAL D.L. 31 DICEMBRE 2025, N. 200): il testo riportato è quello "
            "in vigore oggi",)
        assert t.successione == {
            "abrogato_da": "D.LGS. 1 AGOSTO 2025, N. 123, COME MODIFICATO DAL D.L. 31 DICEMBRE 2025, N. 200",
            "dal": "2027-01-01", "precisione": "INDICATIVO", "fonte": "versione futura della pagina di Normattiva"}
        # VisuaLex's "upcoming", 1:1.
        assert t.upcoming == {"change": "abrogated", "valid_from": "2027-01-01", "version_number": None}

    async def test_any_window_starting_after_today_not_only_a_repeal(self, monkeypatch):
        modificata = synthetic(dal="01-03-2027", label="Art. 3",
                               content='<span class="art-just-text-akn">Il testo che verrà.</span>')
        _serve(monkeypatch, {DPR131: modificata, f"{DPR131}!vig={OGGI}": OGGI_PAGINA})
        t = await api.testo_articolo(_dpr131(), canale="html")
        assert "Sono soggetti a registrazione" in t.article_text and t.successione is None
        assert t.avvisi[0].startswith("Normattiva mostra senza data il testo in vigore dal 2027-03-01:")
        assert t.upcoming == {"change": "amended", "valid_from": "2027-03-01", "version_number": None}

    async def test_the_cache_serves_today_s_text_again_without_a_request(self, monkeypatch):
        richieste = _serve(monkeypatch, {DPR131: FUTURA, f"{DPR131}!vig={OGGI}": OGGI_PAGINA})
        await api.testo_articolo(_dpr131(), canale="html")
        again = await api.testo_articolo(_dpr131(), canale="html")
        assert len(richieste) == 2 and "Sono soggetti a registrazione" in again.article_text


class TestAWindowAlreadyStarted:
    async def test_the_undated_page_is_served_as_it_is(self, monkeypatch):
        richieste = _serve(monkeypatch, {DPR131: OGGI_PAGINA})
        t = await api.testo_articolo(_dpr131(), canale="html")
        assert richieste == [DPR131] and t.url.endswith("~art3")
        assert t.precisione == "ESATTO" and t.avvisi == () and t.successione is None and t.upcoming is None

    async def test_a_window_that_starts_today_is_today_s(self, monkeypatch):
        richieste = _serve(monkeypatch, {DPR131: synthetic(dal="21-10-2026", label="Art. 3")})
        await api.testo_articolo(_dpr131(), canale="html")
        assert richieste == [DPR131]


class TestFailClosed:
    """A page that states no window may be tomorrow's text: never served undated."""

    SENZA = OGGI_PAGINA.replace('<div class="vigore my-5">', '<div class="altro">')

    async def test_the_page_at_today_s_date_is_asked_for(self, monkeypatch):
        richieste = _serve(monkeypatch, {DPR131: self.SENZA, f"{DPR131}!vig={OGGI}": OGGI_PAGINA})
        t = await api.testo_articolo(_dpr131(), canale="html")
        assert richieste == [DPR131, f"{DPR131}!vig={OGGI}"]
        assert t.url.endswith(f"!vig={OGGI}") and t.precisione == "ESATTO"

    async def test_without_today_s_page_the_export_at_today_answers(self, monkeypatch):
        act = ParsedAct(title="TU registro", articles={"3": "### Art. 3.\n\n1. Testo dell'export."}, order=["3"])
        _serve(monkeypatch, {DPR131: self.SENZA, f"{DPR131}!vig={OGGI}": httpx.ConnectError("down")}, act=act)
        t = await api.testo_articolo(_dpr131(), canale="html")
        assert t.fonte == "normattiva-akn" and "Testo dell'export" in t.article_text
        assert t.precisione == "INDICATIVO"

    async def test_with_neither_nothing_is_served(self, monkeypatch):
        _serve(monkeypatch, {DPR131: self.SENZA, f"{DPR131}!vig={OGGI}": httpx.ConnectError("down")}, act=None)
        t = await api.testo_articolo(_dpr131(), canale="html")
        assert t.article_text == "" and t.esito != "trovato"


async def test_cite_law_tells_the_reader(monkeypatch):
    import mcp_legal_it.server  # noqa: F401  (registers the tool modules first)
    from mcp_legal_it.tools import legal_citations as lc

    _serve(monkeypatch, {DPR131: FUTURA, f"{DPR131}!vig={OGGI}": OGGI_PAGINA})
    out = await lc._cite_law_impl("art. 3 d.p.r. 26 aprile 1986, n. 131")
    assert "Sono soggetti a registrazione" in out and "ABROGATO" not in out.split("**Attenzione**")[0]
    assert ("**Attenzione**: Normattiva mostra senza data il testo in vigore dal 2027-01-01 (abrogato dal "
            "D.LGS. 1 AGOSTO 2025") in out

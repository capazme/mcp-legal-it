"""An article the act does not have is an error, never another article's text.

Normattiva answers a URN that names a missing article (``...;262:2~art99999``)
with HTTP 200 and the act's first article. ``cite_law("art. 99999 c.c.")`` took
that page at face value and answered with art. 1 of the R.D. 262/1942 ("È
approvato il testo del Codice civile...") under the URL of art. 99999: a typo in
the article number became a confident citation of a different article.

Existence is now decided by what identifies the article, never by the text
alone: the parsed Akoma Ntoso export of the act (its article keys), or the
number Normattiva gives the article it served (``<h2 class="article-num-akn"
id="art_N">``, or the "Art. N." head of a code article). Without either, the
answer is "verifica non disponibile" and no text is presented.

The HTML fixtures in ``tests/fixtures/normattiva/`` are the ``bodyTesto`` of real
Normattiva N2Ls responses, kept verbatim (see the README there); the AKN
fixtures are the existing exports in ``tests/fixtures/akn/``. No network.
"""

import json
from pathlib import Path

import httpx
import pytest

import src.server  # noqa: F401  (registers every tool module first: avoids a circular import)
from src.lib.visualex import akn_fetch, scraper
from src.lib.visualex.akn_parser import ParsedAct, parse_akn
from src.lib.visualex.models import Norma, NormaVisitata
from src.lib.visualex.scraper import ARTICLE_NOT_FOUND, CHECK_UNAVAILABLE, _article_identity, fetch_article
from src.tools import legal_citations as lc

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
N2LS = FIXTURES / "normattiva"

# Real dates of the acts cited with the year only, as their Normattiva page gives them.
_REAL_DATES = {"241": "1990-08-07", "36": "2023-03-31", "196": "2003-06-30"}

# The page Normattiva serves for each article URN the tests ask for.
_PAGES = {
    "regio.decreto:1942-03-16;262:2~art99999": "cc_n2ls_art99999.html",
    "regio.decreto:1942-03-16;262:2~art2043": "cc_n2ls_art2043.html",
    "regio.decreto:1942-03-16;262:2~art2059": "cc_n2ls_art2059.html",
    "regio.decreto:1942-03-16;262:2~art1": "cc_n2ls_art1.html",
    "legge:1990-08-07;241~art999": "l241_n2ls_art999.html",
    "legge:1990-08-07;241~art3": "l241_n2ls_art3.html",
    "decreto.legislativo:2023-03-31;36~art999": "dlgs36_n2ls_art999.html",
    "decreto.legislativo:2003-06-30;196~art2sexiesdecies": "dlgs196_n2ls_art2sexiesdecies.html",
    "decreto.legislativo:2003-06-30;196~art2quinquiesdecies": "dlgs196_n2ls_art2quinquiesdecies.html",
    "regio.decreto:1930-10-19;1398:1~art609undecies": "cp_n2ls_art609undecies.html",
    "regio.decreto:1930-10-19;1398:1~art416bis.1": "cp_n2ls_art416bis1.html",
    # A suffix the code does not know how to compare: the page names art. 609-undecies.
    "regio.decreto:1930-10-19;1398:1~art609duodecies": "cp_n2ls_art609undecies.html",
}

# A page that does not say which article it is (no bodyTesto heading, no "Art. N." head).
_UNIDENTIFIED_PAGE = (
    '<html><body><div class="bodyTesto"><p>Testo non strutturato restituito dalla fonte.</p>'
    "</div></body></html>"
)


def _load_akn(name: str) -> ParsedAct:
    return parse_akn((FIXTURES / "akn" / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def codice_civile() -> ParsedAct:
    return _load_akn("codice_civile.xml")


@pytest.fixture(scope="module")
def legge_241() -> ParsedAct:
    return _load_akn("legge_241_1990.xml")


@pytest.fixture(scope="module")
def codice_appalti() -> ParsedAct:
    return _load_akn("dlgs_36_2023_trimmed.xml")


class _Response:
    def __init__(self, url: str, text: str):
        self.url = url
        self.text = text
        self.status_code = 200

    def raise_for_status(self):
        return None


def _serve(monkeypatch, act: "ParsedAct | None", pages: "dict[str, str] | None" = None,
           fallback: "str | None" = None, error: "Exception | None" = None) -> list[str]:
    """Answer the AKN export with ``act`` and each article URN with its recorded page.

    Returns the list of URLs requested over HTTP, for the tests that care.
    """
    pages = _PAGES if pages is None else pages
    requested: list[str] = []

    async def fake_fetch_act_akn(norma, data_vigenza=None):
        return act

    async def fake_metadata(norma):
        date = _REAL_DATES.get(norma.numero_atto)
        return {"date": date} if date else {}

    class _Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def get(self, url):
            requested.append(url)
            if error is not None:
                raise error
            urn = url.split("urn:nir:stato:", 1)[-1]
            if urn in pages:
                return _Response(url, (N2LS / pages[urn]).read_text(encoding="utf-8"))
            if fallback is not None:
                return _Response(url, fallback)
            raise AssertionError(f"unexpected request: {url}")

    monkeypatch.delenv("AKN_DISABLED", raising=False)
    monkeypatch.setattr(akn_fetch, "fetch_act_akn", fake_fetch_act_akn)
    monkeypatch.setattr(scraper, "_act_metadata", fake_metadata)
    monkeypatch.setattr(scraper.httpx, "AsyncClient", _Client)
    return requested


def _nv(tipo: str, article: str, data: str = "", numero: str = "") -> NormaVisitata:
    return NormaVisitata(norma=Norma(tipo_atto=tipo, data=data, numero_atto=numero), numero_articolo=article)


_CC = ("codice civile", "", "")
_L241 = ("legge", "1990", "241")
_DLGS36 = ("decreto legislativo", "2023", "36")


def _assert_not_found(result: dict, article: str):
    assert result["text"] == "", result
    assert result["esito"] == ARTICLE_NOT_FOUND, result
    assert f"articolo {article} non trovato" in result["error"], result


# ---------------------------------------------------------------------------
# The reported case: art. 99999 c.c.
# ---------------------------------------------------------------------------

class TestCodiceCivile:
    @pytest.mark.asyncio
    async def test_missing_article_is_not_art_1_of_the_decree(self, monkeypatch, codice_civile):
        _serve(monkeypatch, codice_civile)
        result = await fetch_article(_nv(*_CC[:1], "99999"))
        _assert_not_found(result, "99999")

    @pytest.mark.asyncio
    async def test_missing_article_without_the_export(self, monkeypatch):
        # Source degraded: the AKN export is unreachable. The page Normattiva serves
        # still says it is art. 1, so the answer is "not found", not art. 1's text.
        _serve(monkeypatch, None)
        result = await fetch_article(_nv("codice civile", "99999"))
        _assert_not_found(result, "99999")
        assert "art. 1" in result["error"]

    @pytest.mark.asyncio
    async def test_cite_law_markdown(self, monkeypatch, codice_civile):
        _serve(monkeypatch, codice_civile)
        out = await lc._cite_law_impl("art. 99999 c.c.")
        assert out.startswith("**Errore**: articolo 99999 non trovato"), out
        assert "approvato il testo del Codice civile" not in out
        assert "**Fonte**" not in out

    @pytest.mark.asyncio
    async def test_cite_law_json(self, monkeypatch, codice_civile):
        _serve(monkeypatch, codice_civile)
        body = json.loads(await lc._cite_law_impl("art. 99999 c.c.", formato="json"))
        assert body["testo"] == ""
        assert "articolo 99999 non trovato" in body["errore"]

    @pytest.mark.asyncio
    async def test_fetch_law_article(self, monkeypatch, codice_civile):
        _serve(monkeypatch, codice_civile)
        out = await lc._fetch_law_article_impl("codice civile", "99999")
        assert out.startswith("**Errore**: articolo 99999 non trovato"), out

    @pytest.mark.asyncio
    async def test_no_brocardi_search_for_a_missing_article(self, monkeypatch, codice_civile):
        _serve(monkeypatch, codice_civile)

        async def boom(*a, **k):
            raise AssertionError("Brocardi must not be searched for an article that does not exist")

        monkeypatch.setattr(lc, "fetch_brocardi", boom)
        out = await lc._cite_law_impl("art. 99999 c.c.", include_annotations=True)
        assert out.startswith("**Errore**"), out


# ---------------------------------------------------------------------------
# An ordinary act and an act with annexes
# ---------------------------------------------------------------------------

class TestOtherActs:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("with_export", [True, False])
    async def test_ordinary_act(self, monkeypatch, legge_241, with_export):
        _serve(monkeypatch, legge_241 if with_export else None)
        result = await fetch_article(_nv(*_L241[:1], "999", _L241[1], _L241[2]))
        _assert_not_found(result, "999")

    @pytest.mark.asyncio
    @pytest.mark.parametrize("with_export", [True, False])
    async def test_act_with_annexes_body_article(self, monkeypatch, codice_appalti, with_export):
        _serve(monkeypatch, codice_appalti if with_export else None)
        result = await fetch_article(_nv(*_DLGS36[:1], "999", _DLGS36[1], _DLGS36[2]))
        _assert_not_found(result, "999")

    @pytest.mark.asyncio
    async def test_act_with_annexes_annex_article(self, monkeypatch, codice_appalti):
        _serve(monkeypatch, codice_appalti, pages={})
        result = await fetch_article(_nv(*_DLGS36[:1], "allegato I.7 art. 999", _DLGS36[1], _DLGS36[2]))
        assert result["text"] == "" and result["esito"] == ARTICLE_NOT_FOUND, result
        assert "non trovato" in result["error"]

    @pytest.mark.asyncio
    async def test_cite_law_on_the_codice_appalti(self, monkeypatch, codice_appalti):
        _serve(monkeypatch, codice_appalti)
        out = await lc._cite_law_impl("art. 999 D.Lgs. 36/2023")
        assert out.startswith("**Errore**: articolo 999 non trovato"), out
        assert "Articolo 1" not in out


# ---------------------------------------------------------------------------
# When existence cannot be established
# ---------------------------------------------------------------------------

class TestCheckUnavailable:
    @pytest.mark.asyncio
    async def test_unidentified_page_without_export(self, monkeypatch):
        _serve(monkeypatch, None, pages={}, fallback=_UNIDENTIFIED_PAGE)
        result = await fetch_article(_nv("codice civile", "2043"))
        assert result["text"] == "", result
        assert result["esito"] == CHECK_UNAVAILABLE
        assert "verifica non disponibile" in result["error"]

    @pytest.mark.asyncio
    async def test_cite_law_says_so(self, monkeypatch):
        _serve(monkeypatch, None, pages={}, fallback=_UNIDENTIFIED_PAGE)
        out = await lc._cite_law_impl("art. 2043 c.c.")
        assert out.startswith("**Errore**: verifica non disponibile"), out
        assert "Testo non strutturato" not in out

    @pytest.mark.asyncio
    async def test_unidentified_page_with_export_lacking_the_article(self, monkeypatch, legge_241):
        # The structure was read and lacks the article: that settles it.
        _serve(monkeypatch, legge_241, pages={}, fallback=_UNIDENTIFIED_PAGE)
        result = await fetch_article(_nv(*_L241[:1], "999", _L241[1], _L241[2]))
        _assert_not_found(result, "999")
        assert "Akoma Ntoso" in result["error"]


# ---------------------------------------------------------------------------
# Real articles still return their own text
# ---------------------------------------------------------------------------

class TestRealArticles:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("article,marker", [
        ("2043", "Risarcimento per fatto illecito"),
        ("2059", "Danni non patrimoniali"),
        ("1", "Capacita' giuridica"),
    ])
    async def test_from_the_export(self, monkeypatch, codice_civile, article, marker):
        _serve(monkeypatch, codice_civile, pages={})
        result = await fetch_article(_nv("codice civile", article))
        assert marker in result["text"], result
        assert not result.get("error")

    @pytest.mark.asyncio
    @pytest.mark.parametrize("article,marker", [
        ("2043", "Risarcimento per fatto illecito"),
        ("2059", "Danni non patrimoniali"),
        ("1", "Capacità giuridica"),
    ])
    async def test_from_the_page_without_export(self, monkeypatch, article, marker):
        _serve(monkeypatch, None)
        result = await fetch_article(_nv("codice civile", article))
        assert marker in result["text"], result
        assert not result.get("error")
        assert "approvato il testo del Codice civile" not in result["text"]

    @pytest.mark.asyncio
    async def test_body_article_of_an_ordinary_act_from_the_page(self, monkeypatch):
        _serve(monkeypatch, None)
        result = await fetch_article(_nv(*_L241[:1], "3", _L241[1], _L241[2]))
        assert "Motivazione del provvedimento" in result["text"], result
        assert not result.get("error")

    @pytest.mark.asyncio
    async def test_article_the_parser_missed_is_served_when_the_page_names_it(self, monkeypatch, legge_241):
        # The export is read but lacks art. 3 (a parser gap): Normattiva's page names
        # it as art. 3, so it exists and is served from the page.
        gap = ParsedAct(
            title=legge_241.title,
            articles={k: v for k, v in legge_241.articles.items() if k != "3"},
            order=[k for k in legge_241.order if k != "3"],
        )
        _serve(monkeypatch, gap)
        result = await fetch_article(_nv(*_L241[:1], "3", _L241[1], _L241[2]))
        assert "Motivazione del provvedimento" in result["text"], result
        assert result["source"] == "normattiva"

    @pytest.mark.asyncio
    async def test_cite_law_markdown_2043(self, monkeypatch, codice_civile):
        _serve(monkeypatch, codice_civile, pages={})
        out = await lc._cite_law_impl("art. 2043 c.c.")
        assert out.startswith("**Fonte**: Normattiva-Akn"), out
        assert "Risarcimento per fatto illecito" in out

    @pytest.mark.asyncio
    async def test_articolo_unico_answers_art_1(self, monkeypatch):
        page = ('<html><body><div class="bodyTesto"><h2 class="article-num-akn">Articolo unico</h2>'
                '<div class="art-comma-div-akn">1. Testo dell\'articolo unico.</div></div></body></html>')
        _serve(monkeypatch, None, pages={}, fallback=page)
        result = await fetch_article(_nv("legge", "1", "2020-01-01", "1"))
        assert "articolo unico" in result["text"], result


# ---------------------------------------------------------------------------
# verifica_citazioni
# ---------------------------------------------------------------------------

class TestVerificaCitazioni:
    @pytest.mark.asyncio
    async def test_missing_article_is_inesistente(self, monkeypatch, codice_civile):
        _serve(monkeypatch, codice_civile)
        verdetto, nota = await lc._verifica_norma("art. 99999 c.c.")
        assert verdetto == "inesistente", nota
        assert "non esiste" in nota

    @pytest.mark.asyncio
    async def test_real_article_is_verificata(self, monkeypatch, codice_civile):
        _serve(monkeypatch, codice_civile, pages={})
        verdetto, nota = await lc._verifica_norma("art. 2043 c.c.")
        assert verdetto == "verificata", nota
        assert "Normattiva-Akn — https://www.normattiva.it/uri-res/N2Ls?" in nota

    @pytest.mark.asyncio
    async def test_unidentified_page_is_non_verificata(self, monkeypatch):
        _serve(monkeypatch, None, pages={}, fallback=_UNIDENTIFIED_PAGE)
        verdetto, nota = await lc._verifica_norma("art. 2043 c.c.")
        assert verdetto == "non verificata", nota

    @pytest.mark.asyncio
    async def test_source_down_is_non_verificata_not_non_trovata(self, monkeypatch):
        _serve(monkeypatch, None, error=httpx.ConnectError("connection refused"))
        verdetto, nota = await lc._verifica_norma("art. 2043 c.c.")
        assert verdetto == "non verificata", nota

    @pytest.mark.asyncio
    async def test_unknown_act_stays_non_trovata(self):
        verdetto, _ = await lc._verifica_norma("art. 1 legge inventata del nulla")
        assert verdetto == "non trovata"


# ---------------------------------------------------------------------------
# EUR-Lex: a missing article is an error, not text
# ---------------------------------------------------------------------------

def _serve_eurlex(monkeypatch, html: str):
    async def fake(norma):
        return html, "https://eur-lex.europa.eu/legal-content/IT/TXT/?uri=CELEX:32024R1689"

    monkeypatch.setattr(scraper, "_fetch_eurlex_html", fake)


class TestEurLex:
    @pytest.mark.asyncio
    async def test_missing_article_of_the_ai_act(self, monkeypatch):
        _serve_eurlex(monkeypatch, (FIXTURES / "eurlex_ai_act_annex_trimmed.xhtml").read_text(encoding="utf-8"))
        out = await lc._cite_law_impl("art. 999 AI Act")
        assert out.startswith("**Errore**: Articolo 999 non trovato"), out
        verdetto, _ = await lc._verifica_norma("art. 999 AI Act")
        assert verdetto == "inesistente"

    @pytest.mark.asyncio
    async def test_article_9_is_not_article_90(self, monkeypatch):
        # A title that only starts with the number asked for ("Articolo 90") is another article.
        html = ('<html><body><div class="eli-subdivision"><p class="oj-ti-art">Articolo 90</p>'
                "<p>Testo dell'articolo 90.</p></div></body></html>")
        _serve_eurlex(monkeypatch, html)
        out = await lc._cite_law_impl("art. 9 AI Act")
        assert out.startswith("**Errore**: Articolo 9 non trovato"), out
        assert "articolo 90" not in out


# ---------------------------------------------------------------------------
# Suffixes: a real article spelled another way is never "missing"
# ---------------------------------------------------------------------------

_DLGS196 = ("decreto legislativo", "2003", "196")


class TestSuffixes:
    @pytest.mark.parametrize("a,b", [
        ("2-quinquiesdecies", "2-quindecies"),
        ("2-sexiesdecies", "2-sex-decies"),
        ("2-septiesdecies", "2-septies-decies"),
        ("416-bis.1", "416-bis.1"),
        ("609-undecies", "609 undecies"),
        ("1", "unico"),
        ("01", "1"),
    ])
    def test_same_identity(self, a, b):
        assert _article_identity(a) == _article_identity(b)

    @pytest.mark.parametrize("a,b", [("2-bis", "2-ter"), ("416-bis", "416-bis.1"), ("1", "10")])
    def test_different_identity(self, a, b):
        assert _article_identity(a) != _article_identity(b)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("article,marker", [
        # Normattiva labels them "Art. 2-sex-decies" (id art_2-sex-decies) and "Art. 2-quindecies".
        ("2-sexiesdecies", "Responsabile della protezione dei dati"),
        ("2-quinquiesdecies", "ARTICOLO ABROGATO"),
    ])
    async def test_privacy_code_latin_spellings(self, monkeypatch, article, marker):
        _serve(monkeypatch, None)
        result = await fetch_article(_nv(_DLGS196[0], article, _DLGS196[1], _DLGS196[2]))
        assert marker in result["text"], result
        assert not result.get("error")

    @pytest.mark.asyncio
    @pytest.mark.parametrize("article,marker", [
        ("609-undecies", "Adescamento di minorenni"),
        ("416-bis.1", "Circostanze aggravanti e attenuanti"),
    ])
    async def test_penal_code_suffixes_without_the_export(self, monkeypatch, article, marker):
        _serve(monkeypatch, None)
        result = await fetch_article(_nv("codice penale", article))
        assert marker in result["text"], result
        assert not result.get("error")

    @pytest.mark.asyncio
    async def test_same_number_other_suffix_is_unverifiable_not_missing(self, monkeypatch):
        # The page names art. 609-undecies for a request of 609-duodecies: same
        # number, another suffix. Without the act's structure nothing says the
        # article is missing, so the answer is "verifica non disponibile".
        _serve(monkeypatch, None)
        result = await fetch_article(_nv("codice penale", "609-duodecies"))
        assert result["text"] == ""
        assert result["esito"] == CHECK_UNAVAILABLE, result
        verdetto, _ = await lc._verifica_norma("art. 609-duodecies c.p.")
        assert verdetto == "non verificata"

    @pytest.mark.asyncio
    async def test_export_with_the_number_but_not_the_suffix_is_unverifiable(self, monkeypatch, legge_241):
        # Art. 21 exists in the L. 241/1990; "21-novies-decies" is not among the
        # export's keys, and the page says nothing: not enough to call it missing.
        _serve(monkeypatch, legge_241, pages={}, fallback=_UNIDENTIFIED_PAGE)
        result = await fetch_article(_nv(*_L241[:1], "21-noviesdecies", _L241[1], _L241[2]))
        assert result["esito"] == CHECK_UNAVAILABLE, result

    @pytest.mark.asyncio
    async def test_export_key_spelled_another_way_is_found_in_the_export(self, monkeypatch):
        # The export keys the article "2-sex-decies"; the request spells it "2-sexiesdecies".
        act = ParsedAct(title="Codice privacy", articles={"2-sex-decies": "### Art. 2-sexiesdecies\n\nTesto."},
                        order=["2-sex-decies"])
        _serve(monkeypatch, act, pages={})
        result = await fetch_article(_nv(_DLGS196[0], "2-sexiesdecies", _DLGS196[1], _DLGS196[2]))
        assert result["source"] == "normattiva-akn" and "Testo." in result["text"], result


@pytest.mark.parametrize("head,expected", [
    ("Art. 2043. (Risarcimento per fatto illecito).", "2043"),
    ("CODICE CIVILE Art. 1. (Capacità giuridica).", "1"),
    ("Art. 609-undecies. (Adescamento di minorenni).", "609-undecies"),
    ("Art. 416-bis.1 (Circostanze aggravanti)", "416-bis.1"),
    ("Art. 5. La legge dispone", "5"),
    ("ARTICOLO UNICO Testo", "unico"),
    # An editorial note before the head names another act's article, not this one.
    ("((ARTICOLO ABROGATO DALL'ART. 106 DEL D.LGS. 1/2020)) Art. 155-bis.", "155-bis"),
])
def test_head_of_a_code_article(head, expected):
    from bs4 import BeautifulSoup
    from src.lib.visualex.scraper import _served_article_key

    corpo = BeautifulSoup(f'<div class="bodyTesto"><span class="attachment-just-text">{head}</span></div>', "lxml")
    assert _served_article_key(corpo.find("div")) == expected

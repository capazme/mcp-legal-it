"""A testo unico approved as the annex of its decree, cited both ways (G-440).

D.Lgs. 14 novembre 2024, n. 175 has a one-article body («È approvato l'allegato testo
unico …», art. 1) and the testo unico della giustizia tributaria in an annex the export
names plainly «Allegato» («Allegato-art. N», no identifier). Two citations, two texts:

- «art. N d.lgs. 175/2024» names the decree: its own art. N when it has one (art. 1),
  else the testo unico's art. N labelled as the annex's, never the annex's art. 1 under
  the decree's URN without saying so;
- «art. N testo unico della giustizia tributaria» names the annex: its art. N.

The decree's page for ~art1 states no validity window, so the default channel drops it
and answers from the export: that fallback served the annex's art. 1 as the decree's,
unlabelled, because a bare «Allegato» has no identifier to label it with.
"""

import pytest

import mcp_legal_it.server  # noqa: F401  (registers every tool module first: avoids a circular import)
from mcp_legal_it.lib import _clock
from mcp_legal_it.lib.visualex.akn_parser import parse_akn
from mcp_legal_it.lib.visualex.map import resolve_atto
from mcp_legal_it.lib.visualex.models import Norma, NormaVisitata
from mcp_legal_it.lib.visualex.scraper import fetch_article
from mcp_legal_it.tools import legal_citations as lc

from .test_allegati import _serve_akn

# Markup copied from the real export (caricaAKN, consolidated 2026-08-26), trimmed to the
# decree's art. 1 and the testo unico's artt. 1-3.
_TU_IN_ALLEGATO = """<?xml version="1.0" encoding="UTF-8"?>
<akomaNtoso xmlns="http://docs.oasis-open.org/legaldocml/ns/akn/3.0"><act>
<preface><docTitle>Testo unico della giustizia tributaria.</docTitle></preface>
<body><article eId="art_1"><num>Art. 1.</num><heading/>
<paragraph eId="art_1__para_1"><num>1.</num><content><p>E' approvato l'allegato testo unico delle disposizioni legislative in materia di giustizia tributaria.</p></content></paragraph>
<paragraph eId="art_1__para_2"><num>2.</num><content><p>Il presente decreto entra in vigore il giorno successivo a quello della sua pubblicazione.</p></content></paragraph>
</article></body>
<attachments>
<attachment><doc name="Allegato-art. 1"><mainBody><paragraph><content><p>Art. 1. Le corti di giustizia tributaria di primo e secondo grado.</p></content></paragraph></mainBody></doc></attachment>
<attachment><doc name="Allegato-art. 2"><mainBody><paragraph><content><p>Art. 2. La giurisdizione tributaria.</p></content></paragraph></mainBody></doc></attachment>
<attachment><doc name="Allegato-art. 3"><mainBody><paragraph><content><p>Art. 3. La composizione delle corti di giustizia tributaria.</p></content></paragraph></mainBody></doc></attachment>
</attachments></act></akomaNtoso>"""

#: The decree's art. 1 as Normattiva's page serves it: labelled, but with no validity window.
_PAGINA_DECRETO_ART1 = (
    '<html><body><div class="bodyTesto"><h2 class="article-num-akn" id="art_1">Art. 1</h2>'
    '<div class="art-comma-div-akn">1. È approvato l\'allegato testo unico delle disposizioni '
    "legislative in materia di giustizia tributaria.</div></div></body></html>")

#: The same text without the article label: the page does not say which article it is.
_PAGINA_DECRETO_SENZA_TITOLO = (
    '<html><body><div class="bodyTesto"><span class="art-just-text-akn">'
    "È approvato l'allegato testo unico delle disposizioni legislative in materia di "
    "giustizia tributaria.</span></div></body></html>")


def _decreto(articolo: str) -> NormaVisitata:
    return NormaVisitata(
        norma=Norma(tipo_atto="decreto legislativo", data="2024-11-14", numero_atto="175"),
        numero_articolo=articolo,
    )


def _oggi(suffisso: str) -> str:
    return f"{suffisso}!vig={_clock.today().isoformat()}"


@pytest.fixture
def tu():
    return parse_akn(_TU_IN_ALLEGATO)


def test_the_export_reads_as_a_code_in_an_unnamed_annex(tu):
    # The shape the fix is about: main text in «Allegato» (position 1), the decree apart.
    assert tu.main_part == "Allegato" and tu.part_position() == 1
    assert tu.article_keys("Dispositivo") == ["1"]


class TestDecreeCitation:
    @pytest.mark.asyncio
    @pytest.mark.finestra_reale  # the page states no window, as the real one: it is dropped
    async def test_art_1_of_the_decree_is_the_decrees_when_its_page_is_dropped(self, monkeypatch, tu):
        """The page names art. 1 but no validity window, so it is dropped: the export answers,
        and the URN names the decree's art. 1, which the decree has. The annex's art. 1 under
        the decree's URN, unlabelled, was the wrong article."""
        _serve_akn(monkeypatch, tu, pagine={";175~art1": _PAGINA_DECRETO_ART1,
                                            _oggi(";175~art1"): _PAGINA_DECRETO_ART1})
        result = await fetch_article(_decreto("1"))
        assert "approvato" in result["text"], result
        assert "corti di giustizia" not in result["text"]
        assert not result.get("allegato")
        assert result["url"].endswith(";175~art1")

    @pytest.mark.asyncio
    async def test_akn_channel_art_1_is_the_decrees_too(self, monkeypatch, tu):
        _serve_akn(monkeypatch, tu)
        result = await fetch_article(_decreto("1"), canale="akn")
        assert "approvato" in result["text"], result
        assert not result.get("allegato")
        assert result["url"].endswith(";175~art1")

    @pytest.mark.asyncio
    async def test_an_article_the_decree_lacks_is_the_annexes_labelled(self, monkeypatch, tu):
        # ~art2 serves the decree's art. 1 (Normattiva's answer to a missing article).
        _serve_akn(monkeypatch, tu, pagine={";175~art2": _PAGINA_DECRETO_ART1,
                                            ";175:1~art2": _PAGINA_DECRETO_ART1})
        result = await fetch_article(_decreto("2"))
        assert "giurisdizione tributaria" in result["text"], result
        assert result["allegato"] == "Allegato"
        assert result["url"].endswith(";175:1~art2")

    @pytest.mark.asyncio
    @pytest.mark.finestra_reale
    async def test_an_unlabelled_page_of_the_decree_is_not_the_annexes_article(self, monkeypatch, tu):
        """~art3 answers with the decree's text and no label: it is not art. 3 of the testo
        unico. A bare «Allegato» has no identifier, which let the page through as the article."""
        _serve_akn(monkeypatch, tu, pagine={";175~art3": _PAGINA_DECRETO_SENZA_TITOLO,
                                            _oggi(";175~art3"): _PAGINA_DECRETO_SENZA_TITOLO})
        result = await fetch_article(_decreto("3"))
        assert "approvato" not in result["text"], result
        assert "composizione delle corti" in result["text"]
        assert result["allegato"] == "Allegato"
        assert result["url"].endswith(";175:1~art3")

    @pytest.mark.asyncio
    async def test_cite_law_says_the_text_is_the_annexes(self, monkeypatch, tu):
        _serve_akn(monkeypatch, tu, pagine={";175~art2": _PAGINA_DECRETO_ART1,
                                            ";175:1~art2": _PAGINA_DECRETO_ART1})
        out = await lc._cite_law_impl("art. 2 d.lgs. 175/2024")
        assert "Testo tratto dall'Allegato" in out.split("###")[0] or "Testo tratto dall'Allegato" in out


class TestTestoUnicoByName:
    @pytest.mark.parametrize("nome", [
        "testo unico della giustizia tributaria",
        "testo unico giustizia tributaria",
        "Testo unico della giustizia tributaria",
        "testo unico delle disposizioni legislative in materia di giustizia tributaria",
        "tu giustizia tributaria",
        "t.u. giustizia tributaria",
        "tugt",
        "T.U.G.T.",
    ])
    def test_names_resolve_to_the_annex(self, nome):
        assert resolve_atto(nome) == {"tipo_atto": "decreto legislativo", "data": "2024-11-14",
                                      "numero_atto": "175", "allegato": "1"}

    def test_the_urn_names_the_annex(self):
        info = resolve_atto("testo unico della giustizia tributaria")
        norma = Norma(tipo_atto=info["tipo_atto"], data=info["data"], numero_atto=info["numero_atto"],
                      allegato=info["allegato"])
        assert norma.url(article="1").endswith("decreto.legislativo:2024-11-14;175:1~art1")

    @pytest.mark.asyncio
    async def test_art_1_of_the_testo_unico_is_the_annexes(self, monkeypatch, tu):
        pagina = ('<html><body><div class="bodyTesto"><h2 class="article-num-akn" id="art_1">Art. 1</h2>'
                  '<div class="art-comma-div-akn">Le corti di giustizia tributaria di primo e secondo '
                  "grado.</div></div></body></html>")
        _serve_akn(monkeypatch, tu, pagine={";175:1~art1": pagina, _oggi(";175:1~art1"): pagina})
        out = await lc._cite_law_impl("art. 1 testo unico della giustizia tributaria")
        assert "corti di giustizia tributaria" in out, out
        assert "approvato" not in out

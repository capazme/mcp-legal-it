"""The article-by-article reading of a whole act (``fetch_normattiva_full_text`` without the
Akoma Ntoso export) reads every part of a split article and says what it could not read.

Issue #106: on L. 213/2023 the walk carried 188,540 characters against the export's 500,423 and
called itself complete. Art. 1 is split by Normattiva into six parts («1 (commi 1-100)» …
«1 (commi 501-561)»); the walk kept the first and dropped the other five as versions of the
same article. Some annexes are published as images only («Parte di provvedimento in formato
grafico»): their content is in no text, and the answer must say so.

Pages: real copies (``tests/fixtures/normattiva/atto_intero``, see the README one level up).
Network mocked.
"""

import re
import sys
import zlib
from pathlib import Path

import httpx
import pytest

from mcp_legal_it import api
from mcp_legal_it.lib.visualex import pagine_normattiva, scraper
from mcp_legal_it.lib.visualex.models import Norma
from mcp_legal_it.tools import legal_citations as lc

DIR = Path(__file__).resolve().parents[1] / "fixtures" / "normattiva" / "atto_intero"


def _pagina(nome: str) -> str:
    return (DIR / nome).read_text(encoding="utf-8")


ATTO = _pagina("l213_atto.html")
PARTI = {k: _pagina(f"l213_art1_parte{k}.html") for k in range(1, 7)}
ART2 = _pagina("l213_art2.html")
ALLEGATO_I = _pagina("l213_allegato_I.html")
ALLEGATO_II = _pagina("l213_allegato_II.html")
DLGS196 = _pagina("dlgs196_albero.html")

# The first comma each part of art. 1 serves (its first words, as the page writes them).
INIZIO_PARTE = {
    1: "1. I livelli massimi del saldo netto da finanziare",
    2: "101. Le imprese con sede legale in Italia",
    3: "202. Le risorse di cui all'",
    4: "301. Alle finalità dei commi 299 e 300",
    5: "401. Con decreto del Ministro per la protezione civile",
    6: "501. Con decreto del Ministero dell'interno",
}
L213 = Norma(tipo_atto="legge", data="2023-12-30", numero_atto="213")


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    monkeypatch.setenv("MCP_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("AKN_DISABLED", "1")
    monkeypatch.setattr(scraper, "_full_date_cache", {})
    monkeypatch.setattr(scraper, "_sessioni", {})
    lc._FULL_ACT_TEXTS.clear()
    lc._FULL_ACT_READINGS.clear()
    pagine_normattiva.svuota_memoria()
    api.configura()
    yield
    api.configura()
    lc._FULL_ACT_TEXTS.clear()
    lc._FULL_ACT_READINGS.clear()
    pagine_normattiva.svuota_memoria()


def _normattiva(chieste: list, *, guasti: dict | None = None):
    """Normattiva as it answers: the act page sets the session; a part needs it.

    Without the session cookie a part's address answers 200 with the first part, as
    Normattiva does with a dead session. *guasti* replaces the answer of a part
    (by progressivo) or of an annex (by its label).
    """
    guasti = guasti or {}

    def handler(request):
        url = str(request.url)
        cookie = request.headers.get("cookie", "")
        chieste.append(url)
        if "uri-res/N2Ls" in url:
            return httpx.Response(200, text=ATTO, headers={"set-cookie": "JSESSIONID=sessione-1; Path=/"})
        gruppo = re.search(r"art\.idGruppo=(\d+)", url).group(1)
        tipo = re.search(r"art\.flagTipoArticolo=(\d+)", url).group(1)
        if gruppo == "1":
            k = int(re.search(r"art\.progressivo=(\d+)", url).group(1))
            risposta = guasti.get(k, PARTI[k] if "sessione-1" in cookie else PARTI[1])
        elif gruppo == "2":
            risposta = guasti.get("art2", ART2)
        else:
            etichetta = {"1": "Allegato I", "2": "Allegato II"}[tipo]
            risposta = guasti.get(etichetta, {"Allegato I": ALLEGATO_I, "Allegato II": ALLEGATO_II}[etichetta])
        return risposta if isinstance(risposta, httpx.Response) else httpx.Response(200, text=risposta)

    def factory(fonte, **kwargs):
        kwargs.pop("verify", None)
        return httpx.AsyncClient(transport=httpx.MockTransport(handler), **kwargs)

    return factory


async def _leggi(chieste: list, **kw) -> dict:
    with api.configurazione(client_factory=_normattiva(chieste, **kw)):
        return await scraper.fetch_normattiva_full_text(L213)


class TestAlbero:
    def test_every_part_of_a_split_article_is_an_entry(self):
        voci = scraper._extract_article_ajax_urls(ATTO)
        progressivi = [re.search(r"art\.progressivo=(\d+)", v).group(1) for v in voci if "idGruppo=1&" in v]
        assert progressivi == ["1", "2", "3", "4", "5", "6"]
        assert len(voci) == 9  # six parts, art. 2, two annexes

    def test_older_versions_of_the_parts_are_not_entries(self):
        voci = scraper._extract_article_ajax_urls(ATTO)
        assert not [v for v in voci if "imUpdate=true" in v]
        assert {re.search(r"art\.versione=(\d+)", v).group(1) for v in voci if "idGruppo=1&" in v} == {"39"}

    def test_a_part_only_an_older_version_has_is_not_an_entry(self):
        # An older version split into more parts than today's: its seventh part is history,
        # never a part of the text in force. (The real «agg.37» entry of part 6, renumbered.)
        storica = re.search(r'<a href="" onclick="return showArticle\([^>]*art\.progressivo=6&art\.imUpdate=true[^>]*>'
                            r'agg\.37 \(commi 501-561\)</a>', ATTO).group(0)
        settima = storica.replace("progressivo=6", "progressivo=7").replace("501-561", "562-600")
        voci = scraper._extract_article_ajax_urls(ATTO.replace("</div>\n</body>", settima + "\n</div>\n</body>"))
        assert len(voci) == 9 and not [v for v in voci if "progressivo=7" in v]

    def test_an_older_version_under_another_group_is_not_an_entry(self):
        # D.Lgs. 196/2003: art. 3 today sits under art.idGruppo=4, its original text under
        # art.idGruppo=1. Keyed by group, the original text was read as one more article.
        voci = [v for v in scraper._extract_article_ajax_urls(DLGS196) if "art.idArticolo=3&" in v]
        assert len(voci) == 1 and "art.idGruppo=4&" in voci[0] and "art.versione=2&" in voci[0]

    def test_an_article_with_a_suffix_is_an_entry_of_its_own(self):
        # Arts. 2, 2-bis and 2-ter share art.idArticolo=2 (art.idSottoArticolo 1, 2, 3);
        # 2-quaterdecies and 2-quaterdecies.1 share art.idSottoArticolo=14 (art.idSottoArticolo1
        # 10 and 20). Keyed without them, every article after the first was dropped.
        etichette = [etichetta for _, etichetta in scraper._voci_albero(DLGS196)]
        assert etichette == ["2", "2 bis", "2 ter", "2 quaterdecies", "2 quaterdecies.1", "3"]


class TestLettura:
    async def test_every_part_is_read_in_order(self):
        chieste: list = []
        r = await _leggi(chieste)
        posizioni = [r["text"].index(INIZIO_PARTE[k]) for k in range(1, 7)]
        assert posizioni == sorted(posizioni)
        assert r["article_count"] == 9
        assert r["completo"] is True
        assert r["non_lette"] == []
        assert len(chieste) == 1 + 9  # the act page, then one request per entry

    async def test_a_page_that_is_not_the_part_is_not_read_and_is_named(self):
        # A part's address answering with another part (a dead session) is never taken for it.
        r = await _leggi([], guasti={3: PARTI[1]})
        assert INIZIO_PARTE[3] not in r["text"]
        assert r["text"].count(INIZIO_PARTE[1]) == 1
        assert r["completo"] is False
        assert r["non_lette"] == ["art. 1 (commi 201-300)"]
        assert any("art. 1 (commi 201-300)" in a and "non è l'atto intero" in a for a in r["avvisi"])

    @pytest.mark.parametrize("guasto", [httpx.Response(500), httpx.Response(200, text="Normattiva - Errore")])
    async def test_an_entry_that_fails_is_named(self, guasto):
        r = await _leggi([], guasti={4: guasto, "Allegato I": guasto})
        assert r["completo"] is False
        assert r["non_lette"] == ["art. 1 (commi 301-400)", "Allegato I"]
        assert any("2 parti dell'atto non sono state lette" in a for a in r["avvisi"])

    async def test_a_part_in_graphic_form_is_named(self):
        r = await _leggi([])
        assert r["parti_grafiche"] == ["Allegato II"]
        avviso = next(a for a in r["avvisi"] if "Allegato II" in a)
        assert "solo come immagine" in avviso and "formato grafico" in avviso
        # The page was read whole: the reading is complete, the annex has no text to read.
        assert r["completo"] is True

    async def test_a_part_whose_commi_the_tree_does_not_say_is_not_taken(self, monkeypatch):
        # The tree's label of part 3 in a form not read («(comma …)»): its page cannot be
        # checked, so it is never taken unchecked, not even when it is the right one.
        variata = ATTO.replace(">1 (commi 201-300)</a>", ">1 (comma 201-300)</a>")
        assert variata != ATTO
        monkeypatch.setattr(sys.modules[__name__], "ATTO", variata)
        r = await _leggi([])
        assert r["completo"] is False
        assert r["non_lette"] == ["art. 1 (comma 201-300)"]
        assert INIZIO_PARTE[3] not in r["text"] and INIZIO_PARTE[4] in r["text"]

    async def test_another_articles_part_with_the_same_commi_is_not_taken(self):
        # Made from the real page of part 3, the article changed to 2 in its visible line and its
        # heading: the page of another article split into the same commi (a stale session).
        altro = (PARTI[3].replace("art. 1 (commi 201-300)", "art. 2 (commi 201-300)")
                 .replace('<h2 class="article-num-akn" id="art_1">Art. 1</h2>',
                          '<h2 class="article-num-akn" id="art_2">Art. 2</h2>'))
        assert altro.count("art. 2 (commi 201-300)") == 1 and "id=\"art_2\"" in altro
        r = await _leggi([], guasti={3: altro})
        assert r["completo"] is False and r["non_lette"] == ["art. 1 (commi 201-300)"]
        assert INIZIO_PARTE[3] not in r["text"]

    async def test_a_page_with_an_empty_body_is_named_not_dropped(self):
        # Made from the real page of art. 2, its bodyTesto emptied: a page Normattiva answers 200
        # with nothing in it is an entry not read, never an entry with nothing to read.
        vuota = re.sub(r'(<div class="bodyTesto">).*?(</div>\s*</body>)', r"\1</div>\n</body>", ART2, flags=re.S)
        assert '<div class="bodyTesto"></div>' in vuota
        r = await _leggi([], guasti={"art2": vuota})
        assert r["completo"] is False and r["non_lette"] == ["art. 2"]
        assert any("art. 2" in a and "Lettura parziale" in a for a in r["avvisi"])

    async def test_without_a_tree_the_act_page_is_said_partial(self, monkeypatch):
        monkeypatch.setattr(sys.modules[__name__], "ATTO", re.sub(r"<div id=\"albero\">.*?</div>", "",
                                                                   ATTO, flags=re.S))
        r = await _leggi([])
        assert r["completo"] is False
        assert r["avvisi"] == ["Lettura parziale: la pagina dell'atto su Normattiva non ha un indice degli "
                               "articoli. Il testo è quello che la pagina dell'atto mostra (il primo articolo) "
                               "e può non essere l'atto intero."]

    async def test_a_reading_with_nothing_missing_has_no_notice(self):
        r = await _leggi([], guasti={"Allegato II": ALLEGATO_I})
        assert r["avvisi"] == [] and r["parti_grafiche"] == [] and r["completo"] is True


class TestRisposta:
    async def test_fetch_full_act_says_what_is_missing_in_every_window(self):
        with api.configurazione(client_factory=_normattiva([], guasti={3: PARTI[1]})):
            out = await lc._fetch_full_act_impl("legge 30 dicembre 2023, n. 213")
        testa, corpo = out.split(" caratteri\n", 1)
        assert "**Avviso**: Lettura parziale" in corpo.split(INIZIO_PARTE[1], 1)[0]
        assert "**Avviso**: Parti in formato grafico" in corpo.split(INIZIO_PARTE[1], 1)[0]
        assert "art. 1 (commi 201-300)" in out and "Allegato II" in out

    async def test_fetch_full_act_without_notices_is_unchanged(self):
        with api.configurazione(client_factory=_normattiva([], guasti={"Allegato II": ALLEGATO_I})):
            out = await lc._fetch_full_act_impl("legge 30 dicembre 2023, n. 213")
        assert "**Avviso**" not in out
        assert out.splitlines()[2].startswith("**Dimensione**")

    async def test_the_generated_pdf_carries_the_notices(self, monkeypatch, tmp_path):
        # The file travels without the tool's answer: the notices are printed in it.
        monkeypatch.setattr(lc, "_PDF_OUTPUT_DIR", str(tmp_path))
        with api.configurazione(client_factory=_normattiva([], guasti={3: PARTI[1]})):
            out = await lc._download_law_pdf_impl("legge 30 dicembre 2023, n. 213")
        assert "**Avviso**: Lettura parziale" in out and "**Avviso**: Parti in formato grafico" in out
        path = re.search(r"File: `([^`]+)`", out).group(1)
        testo = " ".join(re.findall(r"\(((?:\\.|[^\\)])*)\)\s*Tj", "".join(
            zlib.decompress(m.group(1)).decode("latin-1")
            for m in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", Path(path).read_bytes(), re.S))))
        assert "Avviso: Lettura parziale" in testo and "201-300" in testo
        assert testo.index("Avviso: Parti in formato grafico") < testo.index("101. Le imprese")

    async def test_testo_atto_carries_completeness_and_notices(self):
        with api.configurazione(client_factory=_normattiva([], guasti={3: PARTI[1]})):
            t = await api.testo_atto("legge 30 dicembre 2023, n. 213")
        assert t.esito == "trovato"
        assert t.completo is False
        assert any("art. 1 (commi 201-300)" in a for a in t.avvisi)
        assert any("Allegato II" in a for a in t.avvisi)

"""The «AGGIORNAMENTO (n)» notes of a Normattiva article page, beside VisuaLex's text.

VisuaLex's extractor drops the notes for an article in comma divs (art. 3 d.lgs. 23/2015:
the words C. cost. 194/2018 struck down stay in the text, the note saying so was lost) and
keeps them in the text of a code's attachment (art. 2327 c.c.). The text stays VisuaLex's;
the notes are read from the same page into their own field, and the MCP tools print them.
Pages: real copies (``tests/fixtures/normattiva``, see its README). Network mocked.
"""

import json
from pathlib import Path

import httpx
import pytest

from mcp_legal_it import api
from mcp_legal_it.core import norme
from mcp_legal_it.lib.visualex import normattiva_html as nh
from mcp_legal_it.lib.visualex import note_normattiva, pagine_normattiva, scraper
from mcp_legal_it.tools import legal_citations as lc

DIR = Path(__file__).resolve().parents[1] / "fixtures" / "normattiva"
ART3 = (DIR / "dlgs23_n2ls_art3.html").read_text(encoding="utf-8")
ART2327 = (DIR / "cc_n2ls_art2327.html").read_text(encoding="utf-8")
L241_ART3 = (DIR / "l241_n2ls_art3.html").read_text(encoding="utf-8")

ART3_URL = "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.legislativo:2015-03-04;23~art3"


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    monkeypatch.setenv("MCP_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("AKN_DISABLED", "1")
    monkeypatch.setattr(scraper, "_full_date_cache", {})
    pagine_normattiva.svuota_memoria()
    api.configura()
    yield
    api.configura()
    pagine_normattiva.svuota_memoria()


def _servi(pagina: str):
    """A client factory answering every Normattiva URL with *pagina* (the article asked)."""

    def handler(request):
        return httpx.Response(200, text=pagina)

    def factory(fonte, **kwargs):
        kwargs.pop("verify", None)
        return httpx.AsyncClient(transport=httpx.MockTransport(handler), **kwargs)

    return factory


def _lettura(pagina: str):
    corpo = nh.corpo_testo(nh.parse_document(pagina))
    testo = nh.estrai_da_corpo(corpo)
    return testo, note_normattiva.leggi_note(corpo, testo)


class TestLettura:
    def test_the_notes_an_article_in_comma_divs_dropped(self):
        testo, r = _lettura(ART3)
        assert "AGGIORNAMENTO" not in testo  # VisuaLex's text, unchanged: without them
        assert [(n["numero"], n["ordine"], n["corte_costituzionale"]) for n in r["note"]] == [
            ("1", 1, False), ("2", 2, True), ("3", 3, False), ("10", 4, True)]
        assert r["non_lette"] is False and r["nel_testo"] is False
        c194 = r["note"][1]["testo"]
        assert c194.startswith("La Corte Costituzionale, con sentenza 26 settembre - 8 novembre 2018 n. 194")
        assert "limitatamente alle parole «di importo pari a due mensilità" in c194
        # The note's own words: no separator, no heading, links as their text, no space added.
        assert r["note"][0]["testo"].startswith("Il D.L. 12 luglio 2018, n. 87, convertito con modificazioni")
        assert all("-----" not in n["testo"] and "AGGIORNAMENTO" not in n["testo"] for n in r["note"])

    def test_a_codes_text_carries_its_note_and_the_field_too(self):
        testo, r = _lettura(ART2327)
        assert testo == nh.estrai_da_html(ART2327) and "AGGIORNAMENTO (113)" in testo
        assert [(n["numero"], n["corte_costituzionale"]) for n in r["note"]] == [("113", False)]
        assert r["nel_testo"] is True

    def test_an_article_without_notes(self):
        _, r = _lettura(L241_ART3)
        assert r == {"note": [], "non_lette": False, "nel_testo": False}

    def test_a_note_block_without_its_number_is_unread(self):
        rotta = ART3.replace("AGGIORNAMENTO (2)", "AGGIORNAMENTO", 1)
        _, r = _lettura(rotta)
        assert [n["numero"] for n in r["note"]] == ["1", "3", "10"] and r["non_lette"] is True

    def test_a_double_call_without_its_note_is_unread(self):
        senza_10 = ART3.replace("AGGIORNAMENTO (10)", "AGGIORNAMENTO (11)", 1)
        _, r = _lettura(senza_10)
        assert r["non_lette"] is True  # «((10))» is in the body, note 10 is not

    def test_a_plain_call_never_names_a_missing_note(self):
        # «(1)» is ordinary text as well: only a note 1 makes it a call.
        senza_1 = ART3.replace("AGGIORNAMENTO (1)", "AGGIORNAMENTO (21)", 1)
        _, r = _lettura(senza_1)
        assert r["non_lette"] is False

    @pytest.mark.parametrize("testo, atteso", [
        ("La Corte Costituzionale, con sentenza 8 novembre 2018 n. 194, ha dichiarato", True),
        ("C. cost., sentenza n. 194/2018", True),
        ("La Corte costituzionale, con ordinanza n. 12", False),
        ("Il D.L. 12 luglio 2018, n. 87 ha disposto", False),
    ])
    def test_corte_costituzionale_is_a_word_match(self, testo, atteso):
        pagina = ART3.replace("La Corte Costituzionale, con sentenza 26 settembre - 8 novembre 2018 n. 194", testo, 1)
        _, r = _lettura(pagina)
        assert r["note"][1]["corte_costituzionale"] is atteso


class TestApi:
    async def test_the_text_is_visualex_s_and_the_notes_are_beside_it(self):
        with api.configurazione(client_factory=_servi(ART3)):
            t = await api.testo_articolo(api.riferimento_da_parametri("decreto legislativo", "3", "2015-03-04", "23")
                                         .norma_data[0], canale="html")
        assert t.esito == "trovato" and t.article_text == nh.estrai_da_html(ART3)
        assert [(n.numero, n.ordine, n.corte_costituzionale) for n in t.note_aggiornamento] == [
            ("1", 1, False), ("2", 2, True), ("3", 3, False), ("10", 4, True)]
        assert "194" in t.note_aggiornamento[1].testo and t.note_non_lette is False
        assert norme.AVVISO_NOTE_NON_LETTE not in t.avvisi

    async def test_a_page_without_notes_gives_an_empty_tuple(self):
        with api.configurazione(client_factory=_servi(L241_ART3)):
            t = await api.testo_articolo(api.riferimento_da_parametri("legge", "3", "1990-08-07", "241")
                                         .norma_data[0], canale="html")
        assert t.esito == "trovato" and t.note_aggiornamento == () and t.note_non_lette is False

    async def test_an_unread_note_is_said(self):
        rotta = ART3.replace("AGGIORNAMENTO (2)", "AGGIORNAMENTO", 1)
        with api.configurazione(client_factory=_servi(rotta)):
            t = await api.testo_articolo(api.riferimento_da_parametri("decreto legislativo", "3", "2015-03-04", "23")
                                         .norma_data[0], canale="html")
        assert t.note_non_lette is True and norme.AVVISO_NOTE_NON_LETTE in t.avvisi
        assert [n.numero for n in t.note_aggiornamento] == ["1", "3", "10"]

    async def test_an_eu_text_has_none(self):
        nd = api.leggi_riferimento("art. 6 GDPR").norma_data[0]
        t = api.TestoArticolo(esito="trovato", article_text="x", norma_data=nd, url="")
        assert t.note_aggiornamento is None  # the default: not a Normattiva page

    def test_a_text_not_from_a_page_has_none_and_no_notice(self):
        assert norme.note_della_pagina("normattiva-akn", "testo", ART3_URL) == (None, False, False)
        assert norme.note_della_pagina("eurlex", "testo", ART3_URL) == (None, False, False)

    def test_a_page_reading_lost_is_never_silent(self):
        # The record of the page served is gone: the notes cannot be said absent.
        assert norme.note_della_pagina("normattiva", "testo", ART3_URL + "~nessuno") == (None, True, False)


class TestStrumentiMcp:
    async def test_cite_law_prints_the_notes_under_the_text(self):
        with api.configurazione(client_factory=_servi(ART3)):
            out = await lc._fetch_law_article_impl("decreto legislativo", "3", "2015-03-04", "23")
        testo = nh.estrai_da_html(ART3)
        assert testo in out
        sezione = out.split(testo, 1)[1]
        assert sezione.startswith("\n\n**Aggiornamenti**\n\n(1) Il D.L. 12 luglio 2018, n. 87")
        assert "(2) La Corte Costituzionale, con sentenza 26 settembre - 8 novembre 2018 n. 194" in sezione
        assert "\n\n(10) La Corte Costituzionale, con sentenza 4 giugno - 16 luglio 2024 n. 128" in sezione
        assert "**Attenzione**: note di aggiornamento non lette" not in out

    async def test_a_codes_notes_are_not_printed_twice(self):
        with api.configurazione(client_factory=_servi(ART2327)):
            out = await lc._cite_law_impl("art. 2327 c.c.")
        assert out.count("AGGIORNAMENTO (113)") == 1 and "**Aggiornamenti**" not in out
        assert out.count("Il D.Lgs. 24 giugno 1998, n. 213") == 1

    async def test_an_unread_note_is_a_warning_before_the_text(self):
        rotta = ART3.replace("AGGIORNAMENTO (2)", "AGGIORNAMENTO", 1)
        with api.configurazione(client_factory=_servi(rotta)):
            out = await lc._fetch_law_article_impl("decreto legislativo", "3", "2015-03-04", "23")
        avviso = "**Attenzione**: note di aggiornamento non lette: verificare su Normattiva."
        assert avviso in out and out.index(avviso) < out.index("Art. 3")

    async def test_cite_law_json_carries_the_notes(self):
        with api.configurazione(client_factory=_servi(ART3)):
            j = json.loads(await lc._cite_law_impl("art. 3 d.lgs. 4 marzo 2015, n. 23", formato="json"))
        assert [(n["numero"], n["corte_costituzionale"]) for n in j["note_aggiornamento"]] == [
            ("1", False), ("2", True), ("3", False), ("10", True)]
        assert j["note_non_lette"] is False and j["note_nel_testo"] is False


class TestCache:
    def test_a_reading_without_notes_is_not_read(self, tmp_path):
        # Schema 2 kept the text without the notes: read now, it would serve art. 3 without
        # C. cost. 194/2018 for a day.
        pagine_normattiva.scrivi(ART3_URL, "testo", "3", None, {"note": [], "non_lette": False, "nel_testo": False})
        assert pagine_normattiva.leggi(ART3_URL) is not None
        pagine_normattiva.svuota_memoria()
        for path in (tmp_path / "cache" / "normattiva_pagine").glob("*.json"):
            rec = json.loads(path.read_text(encoding="utf-8"))
            rec["schema"] = 2
            path.write_text(json.dumps(rec), encoding="utf-8")
        assert pagine_normattiva.leggi(ART3_URL) is None

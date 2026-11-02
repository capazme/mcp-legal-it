"""The editorial notes of the Gazzetta («Note all'art. 13: …»), read beside the article (issue #119).

Normattiva keeps them on the original text and on the current text of an article never
amended, in a ``div.note-akn`` the page puts after the commi, and the Akoma Ntoso export in
an ``authorialNote`` after the paragraphs. Neither VisuaLex's extractor nor ``akn_parser``
reads them, so they never reached the reader. They are read into a field of their own,
never into ``article_text``, which stays VisuaLex's byte for byte.
Pages: real copies (``tests/fixtures/normattiva/redazionali``, see its README). Network mocked.
"""

import json
from pathlib import Path

import httpx
import pytest

from mcp_legal_it import api
from mcp_legal_it.core import norme
from mcp_legal_it.lib.visualex import akn_fetch, note_normattiva, note_redazionali, pagine_normattiva, scraper
from mcp_legal_it.lib.visualex import normattiva_html as nh
from mcp_legal_it.lib.visualex.akn_parser import parse_akn
from mcp_legal_it.tools import legal_citations as lc

FIX = Path(__file__).resolve().parents[1] / "fixtures"
DIR = FIX / "normattiva" / "redazionali"
L24_ART7 = (DIR / "l24_2017_art7.html").read_text(encoding="utf-8")
L132_ART1 = (DIR / "l132_2025_art1.html").read_text(encoding="utf-8")
DLGS58_ART1_ORIG = (DIR / "dlgs58_1998_art1_originale.html").read_text(encoding="utf-8")
DLGS231_ART4 = (DIR / "dlgs231_2001_art4.html").read_text(encoding="utf-8")
DLGS196_ART13_V1 = (FIX / "normattiva" / "aggiornamenti" / "dlgs196_art13_v1.html").read_text(encoding="utf-8")
DLGS23_ART3 = (FIX / "normattiva" / "dlgs23_n2ls_art3.html").read_text(encoding="utf-8")
ART2327 = (FIX / "normattiva" / "cc_n2ls_art2327.html").read_text(encoding="utf-8")
AKN_231 = (FIX / "akn" / "dlgs_231_2001.xml").read_text(encoding="utf-8")
AKN_CC = (FIX / "akn" / "codice_civile_trimmed.xml").read_text(encoding="utf-8")

L24_URL = "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:legge:2017-03-08;24~art7"


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


def _note(pagina: str) -> dict:
    return note_redazionali.leggi_html(nh.corpo_testo(nh.parse_document(pagina)))


def _l24():
    return api.riferimento_da_parametri("legge", "7", "2017-03-08", "24").norma_data[0]


class TestLettore:
    def test_a_current_article_never_amended_keeps_its_notes_beside_the_text(self):
        r = _note(L24_ART7)
        assert [(n["intestazione"], n["ordine"]) for n in r["note"]] == [("Note all'art. 7", 1)]
        assert r["note"][0]["testo"].startswith(
            "- Si riporta il testo degli articoli 1218 e 1228 del codice civile:\n"
            "«Art. 1218 (Responsabilità del debitore). - Il debitore che non esegue esattamente")
        assert r["nel_testo"] is False
        assert "Si riporta" not in nh.estrai_da_html(L24_ART7)  # VisuaLex's text: the commi only

    def test_links_become_their_text_with_no_space_added(self):
        # «n. 397</a>, vedi»: the page's own spacing, never «n. 397 , vedi».
        assert _note(DLGS196_ART13_V1)["note"] == [{
            "intestazione": "Nota all'art. 13",
            "testo": "- Per la legge 7 dicembre 2000, n. 397, vedi in nota all'art. 8.",
            "ordine": 1}]

    def test_the_banner_and_the_avvertenza_are_split_off(self):
        corpo = nh.corpo_testo(nh.parse_document(L132_ART1))
        tutte = note_redazionali.sezioni(note_redazionali._righe_html(corpo.find(class_="note-akn")))
        assert [n["intestazione"] for n in tutte] == ["Avvertenza", "Note all'art. 1"]
        avvertenza = tutte[0]["testo"]
        assert "N O T E" not in avvertenza
        assert "Restano invariati il valore e l'efficacia degli atti legislativi qui trascritti." in avvertenza
        # A line of the page stays a line.
        assert avvertenza.split("\n")[1].startswith("Per gli atti dell'Unione europea vengono forniti")
        # LI-058: only the notes to the article are kept.
        note = _note(L132_ART1)["note"]
        assert [(n["intestazione"], n["ordine"]) for n in note] == [("Note all'art. 1", 1)]
        assert note[0]["testo"].startswith("- Il regolamento (UE) 2024/1689 del Parlamento europeo e del Consiglio")

    def test_art_1_keeps_its_own_notes_not_those_to_the_preamble(self):
        corpo = nh.corpo_testo(nh.parse_document(DLGS58_ART1_ORIG))
        tutte = note_redazionali.sezioni(note_redazionali._righe_html(corpo.find(class_="note-akn")))
        assert [n["intestazione"] for n in tutte] == ["Avvertenza", "Note alle premesse", "Nota all'art. 1"]
        note = _note(DLGS58_ART1_ORIG)["note"]
        assert [(n["intestazione"], n["ordine"]) for n in note] == [("Nota all'art. 1", 1)]
        assert note[0]["testo"].startswith("- Per il testo dell'art. 107 del D.Lgs. 1 settembre 1993, n. 385")

    def test_a_line_naming_another_act_is_never_a_heading(self):
        # «Note al decreto …:» inside a note to the article stays its words: a heading there
        # would take the rest of the note away with the sections LI-058 drops.
        righe = ["Note all'art. 2:", "- Si riporta il testo dell'art. 3:",
                 "Note al decreto legislativo 30 giugno 2003, n. 196:", "«Art. 4. …»"]
        assert note_redazionali.dell_articolo(note_redazionali.sezioni(righe)) == [{
            "intestazione": "Note all'art. 2",
            "testo": "- Si riporta il testo dell'art. 3:\nNote al decreto legislativo 30 giugno 2003, n. 196:\n«Art. 4. …»",
            "ordine": 1}]

    def test_a_heading_with_its_words_on_the_same_line(self):
        assert note_redazionali.sezioni(["Nota all'art. 4: - Si riporta il testo X.", "seguito"]) == [
            {"intestazione": "Nota all'art. 4", "testo": "- Si riporta il testo X.\nseguito", "ordine": 1}]
        assert [n["intestazione"] for n in note_redazionali.sezioni(
            ["Avvertenza: Il testo delle note", "Note alla premesse:", "- x"])] == ["Avvertenza", "Note alla premesse"]
        # A heading alone on its line with a full stop (L. 132/2024 art. 1 writes «Note alle premesse.»).
        assert [n["intestazione"] for n in note_redazionali.sezioni(
            ["Avvertenza:", "x", "Note alle premesse.", "- y", "Note all'art. 1:", "- z"])] == [
            "Avvertenza", "Note alle premesse", "Note all'art. 1"]

    def test_only_the_notes_to_the_article(self):
        lette = [{"intestazione": h, "testo": "t", "ordine": i} for i, h in enumerate(
            ["", "Avvertenza", "Note alle premesse", "Note all'art. 2", "Nota all'articolo 2",
             "Note agli articoli 2 e 3", "NOTE ALL'ART. 2"], start=1)]
        assert [(n["intestazione"], n["ordine"]) for n in note_redazionali.dell_articolo(lette)] == [
            ("Note all'art. 2", 1), ("Nota all'articolo 2", 2), ("Note agli articoli 2 e 3", 3), ("NOTE ALL'ART. 2", 4)]

    def test_a_page_without_notes(self):
        assert _note(DLGS23_ART3) == {"note": [], "nel_testo": False}

    def test_the_fallback_shape_already_carries_them(self):
        # The same real page with its comma divs unrecognised: VisuaLex's fallback reads the
        # whole body, notes included, and the reader says so.
        pagina = DLGS196_ART13_V1.replace("art-comma-div-akn", "x").replace("art-just-text-akn", "x")
        assert "vedi in nota all'art. 8" in nh.estrai_da_html(pagina)
        r = _note(pagina)
        assert r["nel_testo"] is True and r["note"][0]["intestazione"] == "Nota all'art. 13"

    def test_the_attachment_shape_carries_them_only_inside_what_it_reads(self):
        # A code's real attachment page (art. 2327 c.c.) with the real block of art. 13 d.lgs.
        # 196/2003 put inside the span the extractor reads, then after it.
        blocco = str(nh.corpo_testo(nh.parse_document(DLGS196_ART13_V1)).find(class_="note-akn"))
        dentro = ART2327.replace('class="attachment-just-text">', 'class="attachment-just-text">' + blocco, 1)
        fuori = ART2327.replace('</div>\n</body>', blocco + '</div>\n</body>', 1)
        assert dentro != ART2327 and fuori != ART2327
        assert "vedi in nota all'art. 8" in nh.estrai_da_html(dentro)
        assert "vedi in nota all'art. 8" not in nh.estrai_da_html(fuori)
        assert _note(dentro)["nel_testo"] is True and _note(fuori)["nel_testo"] is False

    def test_headings_and_lines(self):
        righe = ["  parole prima  ", "Note all'art. 2:", "- Si riporta il testo dell'art. 3:", "", "«Art. 3. …»",
                 "Note agli articoli 4 e 5:"]
        assert note_redazionali.sezioni(righe) == [
            {"intestazione": "", "testo": "parole prima", "ordine": 1},
            # A line of a note ending with a colon is not a heading.
            {"intestazione": "Note all'art. 2", "testo": "- Si riporta il testo dell'art. 3:\n«Art. 3. …»", "ordine": 2},
            {"intestazione": "Note agli articoli 4 e 5", "testo": "", "ordine": 3}]


class TestAkn:
    def test_the_export_carries_the_same_notes_and_its_text_does_not(self):
        act = parse_akn(AKN_231)
        assert "4" in act.note_redazionali and "5" not in act.note_redazionali
        assert "Nota all'art. 4" not in act.article("4")
        # Art. 1 carries only the Avvertenza and the «Note alla premesse» (sic): none kept (LI-058).
        assert "1" not in act.note_redazionali
        assert act.note_redazionali["4"]["nel_testo"] is False
        # The act's «Entrata in vigore» note sits in the preamble, not in an article.
        assert not any("Entrata in vigore" in n["testo"] for v in act.note_redazionali.values() for n in v["note"])

    def test_html_and_export_agree(self):
        export, nel_testo = scraper._akn_note_redazionali(parse_akn(AKN_231), "4", None)
        assert nel_testo is False
        pagina = _note(DLGS231_ART4)["note"]
        assert [n["intestazione"] for n in export] == [n["intestazione"] for n in pagina] == ["Nota all'art. 4"]
        # The export transliterates accents («E'»): the same words otherwise.
        assert scraper._confronto(export[0]["testo"]) == scraper._confronto(pagina[0]["testo"])

    def test_an_article_without_notes_an_annex_and_a_code(self):
        act = parse_akn(AKN_231)
        assert scraper._akn_note_redazionali(act, "5", None) == ([], False)
        assert scraper._akn_note_redazionali(act, "4", "allegato 1") == (None, False)  # annexes are not read
        codice = parse_akn(AKN_CC)
        assert codice.note_redazionali is None
        assert scraper._akn_note_redazionali(codice, "2043", None) == (None, False)

    def test_an_article_never_takes_the_notes_of_another_of_the_same_identity(self):
        # The real export with art. 4 (with notes) relabelled «02»: art. 2 (without notes) has
        # the same identity, and its text is served for «art. 2». Its notes are its own: none.
        act = parse_akn(AKN_231.replace('eId="art_4"', 'eId="art_02"', 1))
        assert "02" in act.note_redazionali and act.article("2")
        assert scraper._akn_note_redazionali(act, "2", None) == ([], False)
        assert [n["intestazione"] for n in scraper._akn_note_redazionali(act, "02", None)[0]] == ["Nota all'art. 4"]

    def test_an_article_without_paragraphs_carries_them_in_its_text(self):
        # Art. 4 of the real export without its paragraphs: akn_parser renders all its content,
        # the note included, and the flag says so.
        from lxml import etree

        root = etree.fromstring(AKN_231.encode("utf-8"))
        art4 = next(a for a in root.iter("{*}article") if a.get("eId") == "art_4")
        for para in [c for c in art4 if c.tag.endswith("paragraph")]:
            art4.remove(para)
        act = parse_akn(etree.tostring(root, encoding="unicode"))
        assert "Nota all'art. 4" in act.article("4")
        note, nel_testo = scraper._akn_note_redazionali(act, "4", None)
        assert nel_testo is True and note[0]["intestazione"] == "Nota all'art. 4"

    def test_the_kept_export_keeps_them_and_an_older_one_has_none(self):
        act = parse_akn(AKN_231)
        dati = akn_fetch._act_to_dict(act)
        assert akn_fetch._act_from_dict(json.loads(json.dumps(dati))).note_redazionali == act.note_redazionali
        dati.pop("note_redazionali")
        assert akn_fetch._act_from_dict(dati).note_redazionali is None  # «not read», never «none»


class TestApi:
    async def test_the_notes_are_a_field_and_never_the_text(self):
        with api.configurazione(client_factory=_servi(L24_ART7)):
            t = await api.testo_articolo(_l24(), canale="html")
        assert t.esito == "trovato" and t.article_text == nh.estrai_da_html(L24_ART7)
        assert [(n.intestazione, n.ordine) for n in t.note_redazionali] == [("Note all'art. 7", 1)]
        assert isinstance(t.note_redazionali[0], api.NotaRedazionale)
        assert t.note_aggiornamento == () and t.note_non_lette is False

    async def test_a_page_without_them(self):
        with api.configurazione(client_factory=_servi(DLGS23_ART3)):
            t = await api.testo_articolo(api.riferimento_da_parametri("decreto legislativo", "3", "2015-03-04", "23")
                                         .norma_data[0], canale="html")
        assert t.note_redazionali == ()

    async def test_the_export_channel_reads_them_from_the_export(self, monkeypatch):
        monkeypatch.delenv("AKN_DISABLED")
        act = parse_akn(AKN_231)

        async def export(norma, vigenza=None):
            return act

        monkeypatch.setattr(akn_fetch, "fetch_act_akn", export)
        nd = api.riferimento_da_parametri("decreto legislativo", "4", "2001-06-08", "231").norma_data[0]
        with api.configurazione(client_factory=_servi(DLGS231_ART4)):
            t = await api.testo_articolo(nd, canale="akn")
        assert t.fonte == "normattiva-akn"
        assert [n.intestazione for n in t.note_redazionali] == ["Nota all'art. 4"]
        assert "Nota all'art. 4" not in t.article_text

    async def test_a_failure_of_this_reader_leaves_them_unread_and_the_rest_whole(self, monkeypatch):
        monkeypatch.setattr(note_redazionali, "leggi_html", lambda *a, **k: 1 / 0)
        with api.configurazione(client_factory=_servi(L24_ART7)):
            t = await api.testo_articolo(_l24(), canale="html")
        assert t.esito == "trovato" and t.article_text == nh.estrai_da_html(L24_ART7)
        assert t.note_redazionali is None
        assert t.note_aggiornamento == () and t.note_non_lette is False

    async def test_a_failure_of_the_update_notes_keeps_these(self, monkeypatch):
        monkeypatch.setattr(note_normattiva, "leggi_note", lambda *a, **k: 1 / 0)
        with api.configurazione(client_factory=_servi(L24_ART7)):
            t = await api.testo_articolo(_l24(), canale="html")
        assert t.note_non_lette is True and norme.AVVISO_NOTE_NON_LETTE in t.avvisi
        assert [n.intestazione for n in t.note_redazionali] == ["Note all'art. 7"]

    def test_a_malformed_or_missing_reading_is_unread(self):
        for note in ({"redazionali": {"note": [{"intestazione": "x"}], "nel_testo": False}},
                     {"redazionali": {"note": "x"}}, {"redazionali": ["x"]}, {"note": []}, None,
                     {"redazionali": {"note": [{"intestazione": "x", "testo": "t", "ordine": "1"}]}}):
            pagine_normattiva.scrivi(L24_URL, "testo", "7", None, note)
            assert norme.note_redazionali_del_testo("normattiva", "testo", L24_URL) == (None, False), note
        assert norme.note_redazionali_del_testo("normattiva", "testo", L24_URL + "~nessuno") == (None, False)

    def test_other_sources(self):
        assert norme.note_redazionali_del_testo("eurlex", "testo", L24_URL) == (None, False)
        assert norme.note_redazionali_del_testo("normattiva-akn", "testo", "", dall_export=None) == (None, False)
        assert norme.note_redazionali_del_testo("normattiva-akn", "testo", "", dall_export=[]) == ([], False)
        nota = [{"intestazione": "Nota all'art. 4", "testo": "t", "ordine": 1}]
        assert norme.note_redazionali_del_testo("normattiva-akn", "testo", "", dall_export=nota,
                                                export_nel_testo=True) == (nota, True)
        assert norme.note_redazionali_del_testo("normattiva", "", L24_URL) == (None, False)


class TestStrumentiMcp:
    async def test_cite_law_json_carries_them(self):
        with api.configurazione(client_factory=_servi(L24_ART7)):
            j = json.loads(await lc._cite_law_impl("art. 7 legge 8 marzo 2017, n. 24", formato="json"))
        assert [(n["intestazione"], n["ordine"]) for n in j["note_redazionali"]] == [("Note all'art. 7", 1)]
        assert j["note_redazionali_nel_testo"] is False
        assert "Si riporta" not in j["testo"]

    async def test_cite_law_json_without_them(self):
        with api.configurazione(client_factory=_servi(DLGS23_ART3)):
            j = json.loads(await lc._cite_law_impl("art. 3 d.lgs. 4 marzo 2015, n. 23", formato="json"))
        assert j["note_redazionali"] == [] and j["note_redazionali_nel_testo"] is False

    async def test_the_markdown_says_they_exist_in_one_line_never_their_words(self):
        # Decision LI-058: one line under the text, pointing at the JSON.
        with api.configurazione(client_factory=_servi(L24_ART7)):
            out = await lc._cite_law_impl("art. 7 legge 8 marzo 2017, n. 24")
        testo = nh.estrai_da_html(L24_ART7)
        assert testo in out
        assert out.split(testo, 1)[1].startswith("\n\n" + norme.riga_note_redazionali())
        assert out.count("**Note redazionali**") == 1
        assert "Si riporta il testo degli articoli 1218 e 1228" not in out
        riga = norme.riga_note_redazionali()
        assert "art. 10 d.P.R. 1092/1985" in riga and "prive di valore normativo" in riga
        assert "alla data di pubblicazione" in riga and 'cite_law(formato="json")' in riga

    async def test_fetch_law_article_says_it_too(self):
        with api.configurazione(client_factory=_servi(L24_ART7)):
            out = await lc._fetch_law_article_impl("legge", "7", "2017-03-08", "24")
        assert norme.riga_note_redazionali() in out

    async def test_no_line_without_them(self):
        with api.configurazione(client_factory=_servi(DLGS23_ART3)):
            out = await lc._cite_law_impl("art. 3 d.lgs. 4 marzo 2015, n. 23")
        assert "**Note redazionali**" not in out

    def test_the_line_when_the_text_already_ends_with_them(self):
        riga = norme.riga_note_redazionali(nel_testo=True)
        assert "sono riportate in coda al testo" in riga and "formato" not in riga

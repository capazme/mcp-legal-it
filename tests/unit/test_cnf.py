"""The codice deontologico forense, read from the CNF's PDF (mcp_legal_it/lib/cnf).

The PDFs here are built with fpdf2 in the CNF's typography (headings in bold italic,
text at 12 points, notes at 10 with smaller reference marks, «pagina N di M» at the
foot, the index on the first page): the reading depends on that typography, and on
nothing else. fpdf2's typography is not the CNF's own (Helvetica, «-», no dot leaders), so
``tests/fixtures/cnf/runs.json.gz`` keeps the runs pypdf extracts from the CNF's real PDF
(``scripts/cnf_runs_fixture.py``) and the suite reads them offline. The live test at the
end reads the PDF the CNF publishes today.
"""

import gzip
import json
from pathlib import Path

import httpx
import pytest
from fpdf import FPDF

from mcp_legal_it.lib.cnf import client as cnf
from mcp_legal_it.lib.cnf import parser
from mcp_legal_it.lib.cnf.parser import Codice, FormatoNonRiconosciuto, analizza, chiave_articolo

# ---------------------------------------------------------------------------
# A PDF in the CNF's layout
# ---------------------------------------------------------------------------

_SINISTRA, _BASSO, _ALTEZZA_RIGA = 57, 700, 21


def _articoli_base() -> list[dict]:
    """62 articles, a few of them shaped like the hard cases of the real code."""
    arts = []
    for n in range(1, 61):
        arts.append({"numero": str(n), "rubrica": f"Rubrica dell'articolo {n}",
                     "righe": [f"1. Primo comma dell'articolo {n}.", f"2. Secondo comma dell'articolo {n}."]})
        if n == 25:
            arts.append({"numero": "25-bis", "rubrica": "Violazioni in materia di equo compenso", "segno": "1",
                         "righe": ["1. L'avvocato non concorda compensi non equi in favore degli agenti della",
                                   ("riscossione", "2", "."),
                                   "2. La violazione comporta la censura."],
                         "note": {"1": ["Articolo aggiunto con delibera del 23 febbraio 2024,",
                                        "pubblicata nella Gazzetta Ufficiale."],
                                  "2": ["Comma modificato con delibera n. 959 del 23 gennaio 2026."]}})
    by_n = {a["numero"]: a for a in arts}
    by_n["3"].update(rubrica="Una rubrica lunga che va a capo|nella seconda riga")
    by_n["4"]["righe"] = ["1. Ai sensi della legge 31 dicembre 2012, n.",
                          "247. il consiglio provvede.", "2. Secondo comma."]
    by_n["5"]["righe"] = ["1. Si applica:", "a) agli avvocati;", "b) ai praticanti;", "2. Altro comma."]
    by_n["6"]["righe"] = ["1. Uno.", "1-bis. Uno bis.", "2. Due."]
    by_n["7"]["righe"] = ["1. Uno.", "2.Due senza spazio, come l'art. 50 del 2026."]
    # A note that goes on at the foot of the next page.
    by_n["30"].update(righe=[("1. Comma modificato", "3", "."), "2. Secondo comma."], pagina_dopo=True,
                      note={"3": (["Comma modificato con delibera del 21 marzo 2025,"],
                                  ["pubblicata nella Gazzetta Ufficiale n. 81."])})
    by_n["60"]["righe"] = ["Il presente codice entra in vigore decorsi sessanta giorni."]
    return arts


def _pdf(arts: list[dict], *, indice: "list[tuple[str, str]] | None" = None,
         titolo: str = "CODICE DEONTOLOGICO FORENSE", titoli: "dict[str, str] | None" = None,
         coda: str = "", coda_a_pagina_nuova: bool = False, testatina: str = "") -> bytes:
    """A PDF of *arts*; *indice* overrides the index entries; *titoli*: a title before an article;
    *coda*: a line of plain text after the last article, set apart on its page or, with
    *coda_a_pagina_nuova*, at the top of a new one; *testatina*: a small header at the top of
    the page where a note goes on. A ``None`` among an article's lines is a page break."""
    pdf = FPDF(unit="pt", format="A4")
    pdf.set_auto_page_break(False)
    pdf.add_page()
    pdf.set_font("helvetica", "B", 20)
    pdf.text(150, 80, titolo)
    pdf.set_font("helvetica", "", 11)
    y = 120
    for numero, rubrica in (indice if indice is not None
                            else [(a["numero"], a["rubrica"].replace("|", " ")) for a in arts]):
        if y > 800:
            pdf.add_page()
            y = 60
        pdf.text(_SINISTRA, y, f"Art. {numero} - {rubrica} ........ 3")
        y += 13

    note_pagina: list[tuple[str, list[str]]] = []
    riporto: list[str] = []  # the lines of a note that go on at the foot of the next page
    pagina = [0]

    def chiudi_pagina():
        yy = 760 - 11 * (len(riporto) + sum(len(r) for _, r in note_pagina))
        pdf.set_font("helvetica", "", 10)
        for riga in riporto:
            pdf.text(_SINISTRA + 4, yy, riga)
            yy += 11
        riporto.clear()
        for numero, righe in note_pagina:
            for i, riga in enumerate(righe):
                if i == 0:
                    pdf.set_font("helvetica", "", 6.7)
                    pdf.text(_SINISTRA, yy - 2, numero)
                pdf.set_font("helvetica", "", 10)
                pdf.text(_SINISTRA + 4, yy, riga)
                yy += 11
        note_pagina.clear()
        pdf.set_font("helvetica", "I", 10)
        pdf.text(280, 815, f"pagina {pagina[0]} di 99")

    def nuova_pagina():
        if pagina[0]:
            chiudi_pagina()
        pdf.add_page()
        pagina[0] += 1
        return 60

    def scrivi(yy, testo, stile, segno=None, dopo=""):
        pdf.set_font("helvetica", stile, 12)
        pdf.text(_SINISTRA, yy, testo)
        x = _SINISTRA + pdf.get_string_width(testo)
        if segno:
            pdf.set_font("helvetica", stile, 8)
            pdf.text(x + 1, yy - 3, segno)
            x += 6
        if dopo:
            pdf.set_font("helvetica", stile, 12)
            pdf.text(x, yy, dopo)

    y = nuova_pagina()
    riporto_dopo: list[str] = []
    for art in arts:
        if y > _BASSO - 6 * _ALTEZZA_RIGA:
            y = nuova_pagina()
        if titoli and art["numero"] in titoli:
            pdf.set_font("helvetica", "B", 12)
            pdf.text(250, y, titoli[art["numero"]])
            y += 2 * _ALTEZZA_RIGA
        prima, _, seconda = art["rubrica"].partition("|")
        scrivi(y, f"Art. {art['numero']} - {prima}", "BI", art.get("segno"))
        y += _ALTEZZA_RIGA
        if seconda:
            scrivi(y, seconda, "BI")
            y += _ALTEZZA_RIGA
        for riga in art["righe"]:
            if riga is None:
                y = nuova_pagina()
                continue
            if isinstance(riga, tuple):
                scrivi(y, riga[0], "", riga[1], riga[2])
            else:
                scrivi(y, riga, "")
            y += _ALTEZZA_RIGA
        for numero, righe in art.get("note", {}).items():
            if isinstance(righe, tuple):  # (this page's lines, the next page's)
                note_pagina.append((numero, righe[0]))
                riporto_dopo = righe[1]
            else:
                note_pagina.append((numero, righe))
                riporto_dopo = []
        y += _ALTEZZA_RIGA
        if art.get("pagina_dopo"):
            y = nuova_pagina()
            riporto.extend(riporto_dopo)
            if testatina:
                pdf.set_font("helvetica", "", 10)
                pdf.text(_SINISTRA, 40, testatina)
    if coda:
        if coda_a_pagina_nuova:
            y = nuova_pagina()
        scrivi(y, coda, "")
    chiudi_pagina()
    return bytes(pdf.output())


@pytest.fixture(scope="module")
def codice() -> Codice:
    return analizza(_pdf(_articoli_base()))


# ---------------------------------------------------------------------------
# Reading the PDF
# ---------------------------------------------------------------------------

def test_every_article_is_read_in_order(codice):
    numeri = list(codice.articoli)
    assert len(numeri) == 61
    assert numeri[:3] == ["1", "2", "3"] and numeri[25:27] == ["25-bis", "26"]


def test_a_heading_on_two_lines_is_one_heading(codice):
    assert codice.articolo("3").rubrica == "Una rubrica lunga che va a capo nella seconda riga"


def test_commi_and_letters_are_paragraphs(codice):
    assert codice.articolo("1").paragrafi == ["1. Primo comma dell'articolo 1.", "2. Secondo comma dell'articolo 1."]
    assert codice.articolo("5").paragrafi == ["1. Si applica:", "a) agli avvocati;", "b) ai praticanti;",
                                              "2. Altro comma."]
    assert "\n\n1. Si applica:\na) agli avvocati;\nb) ai praticanti;\n\n2. Altro comma." in codice.articolo("5").testo()


def test_a_number_that_wrapped_to_a_line_start_is_not_a_comma(codice):
    """«n.» / «247. il consiglio…»: 247 is not the next comma, so the line goes on the first."""
    assert codice.articolo("4").paragrafi == [
        "1. Ai sensi della legge 31 dicembre 2012, n. 247. il consiglio provvede.", "2. Secondo comma."]


def test_a_bis_comma_is_a_comma(codice):
    assert codice.articolo("6").paragrafi == ["1. Uno.", "1-bis. Uno bis.", "2. Due."]


def test_a_comma_without_a_space_after_its_number_is_a_comma(codice):
    """«2.L’avvocato» (art. 50 of the 2026 PDF): a comma, served as «2. L’avvocato»."""
    assert codice.articolo("7").paragrafi == ["1. Uno.", "2. Due senza spazio, come l'art. 50 del 2026."]


def test_a_note_that_goes_on_on_the_next_page(codice):
    assert codice.articolo("30").note == [{"numero": "3", "testo": "Comma modificato con delibera del 21 marzo "
                                                                    "2025, pubblicata nella Gazzetta Ufficiale n. 81."}]


def test_an_article_without_commi_is_one_paragraph(codice):
    assert codice.articolo("60").paragrafi == ["Il presente codice entra in vigore decorsi sessanta giorni."]


def test_notes_marks_and_page_footers(codice):
    art = codice.articolo("25 bis")
    assert art.rubrica == "Violazioni in materia di equo compenso"
    # The marks stay in the text, against the word before them, so the reader sees which comma
    # each note is about; the rubrica (compared with the index) has none, the heading shows it.
    assert art.paragrafi[0].endswith("in favore degli agenti della riscossione⁽²⁾.")
    assert art.testo().startswith("### Art. 25-bis – Violazioni in materia di equo compenso⁽¹⁾\n\n1. ")
    assert art.note == [
        {"numero": "1", "testo": "Articolo aggiunto con delibera del 23 febbraio 2024, pubblicata nella "
                                 "Gazzetta Ufficiale."},
        {"numero": "2", "testo": "Comma modificato con delibera n. 959 del 23 gennaio 2026."},
    ]
    assert not any("pagina" in p for a in codice.articoli.values() for p in a.paragrafi)


def test_a_title_ends_the_article_before_it():
    codice = analizza(_pdf(_articoli_base(), titoli={"11": "TITOLO II"}))
    assert codice.articolo("10").paragrafi[-1] == "2. Secondo comma dell'articolo 10."


def test_a_bold_line_that_is_not_an_upper_case_title_is_refused():
    with pytest.raises(FormatoNonRiconosciuto, match="grassetto"):
        analizza(_pdf(_articoli_base(), titoli={"11": "Una nota in grassetto"}))


def test_text_on_a_new_page_after_the_last_article_is_refused():
    """The last article ends a sentence on its page: a new page of plain text is not its own."""
    with pytest.raises(FormatoNonRiconosciuto, match="dopo l'ultimo articolo"):
        analizza(_pdf(_articoli_base(), coda="Roma, 23 gennaio 2026. Il Presidente", coda_a_pagina_nuova=True))


def test_the_last_article_may_go_on_to_a_new_page_mid_sentence():
    arts = _articoli_base()
    arts[-1]["righe"] = ["Il presente codice entra in vigore decorsi", None, "sessanta giorni."]
    assert analizza(_pdf(arts)).articolo("60").paragrafi == [
        "Il presente codice entra in vigore decorsi sessanta giorni."]


def test_the_last_article_may_go_on_to_a_new_page_with_its_next_comma():
    arts = _articoli_base()
    arts[-1]["righe"] = ["1. Il presente codice entra in vigore decorsi sessanta giorni.", None,
                         "2. Si applica ai procedimenti pendenti."]
    assert [p[:2] for p in analizza(_pdf(arts)).articolo("60").paragrafi] == ["1.", "2."]


def test_a_small_page_header_is_not_taken_for_a_note_going_on():
    """A note goes on at the foot of the next page, below its text: a small line above it is not
    the note's (it would end the amendment's history with the page's running header)."""
    with pytest.raises(FormatoNonRiconosciuto, match="testo in nota senza numero"):
        analizza(_pdf(_articoli_base(), testatina="Codice deontologico forense"))


def test_text_set_apart_after_the_last_article_is_refused():
    """An annex or a signature after the last article is not that article's text."""
    with pytest.raises(FormatoNonRiconosciuto, match="staccato dall'art. 60"):
        analizza(_pdf(_articoli_base(), coda="Roma, 23 gennaio 2026. Il Presidente"))


@pytest.mark.parametrize("numero, chiave", [("25-bis", "25-bis"), ("25 bis", "25-bis"), ("25Bis", "25-bis"),
                                            ("68", "68")])
def test_article_keys(numero, chiave):
    assert chiave_articolo(numero) == chiave


# ---------------------------------------------------------------------------
# Refusals: a PDF read wrong is refused, never served
# ---------------------------------------------------------------------------

def test_an_index_that_lists_other_articles_is_refused():
    arts = _articoli_base()
    indice = [(a["numero"], a["rubrica"].replace("|", " ")) for a in arts if a["numero"] != "7"]
    with pytest.raises(FormatoNonRiconosciuto, match="indice"):
        analizza(_pdf(arts, indice=indice))


def test_a_heading_that_differs_from_the_index_is_refused():
    arts = _articoli_base()
    indice = [(a["numero"], "Altra rubrica" if a["numero"] == "9" else a["rubrica"].replace("|", " "))
              for a in arts]
    with pytest.raises(FormatoNonRiconosciuto, match="rubrica dell'art. 9"):
        analizza(_pdf(arts, indice=indice))


def test_articles_out_of_order_are_refused():
    arts = _articoli_base()
    arts[10], arts[11] = arts[11], arts[10]
    with pytest.raises(FormatoNonRiconosciuto, match="fuori ordine"):
        analizza(_pdf(arts))


def _con_nota(arts, numero, **campi):
    arts = [dict(a) for a in arts]
    next(a for a in arts if a["numero"] == numero).update(campi)
    return arts


def test_a_mark_without_its_note_is_refused():
    arts = _con_nota(_articoli_base(), "12", righe=[("1. Comma", "9", "."), "2. Due."])
    with pytest.raises(FormatoNonRiconosciuto, match="nota 9, che non c'è"):
        analizza(_pdf(arts))


def test_a_note_claimed_by_two_articles_is_refused():
    arts = _con_nota(_articoli_base(), "12", righe=[("1. Comma", "1", "."), "2. Due."])
    with pytest.raises(FormatoNonRiconosciuto, match="nota 1 è richiamata"):
        analizza(_pdf(arts))


def test_two_notes_with_one_number_are_refused():
    arts = _con_nota(_articoli_base(), "50", righe=[("1. Comma", "1", "."), "2. Due."],
                     note={"1": ["Un'altra nota con lo stesso numero."]})
    with pytest.raises(FormatoNonRiconosciuto, match="due note con il numero 1"):
        analizza(_pdf(arts))


def test_an_encrypted_pdf_is_refused():
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("helvetica", "", 12)
    pdf.text(10, 10, "CODICE DEONTOLOGICO FORENSE")
    pdf.set_encryption(owner_password="o", user_password="u")
    with pytest.raises(FormatoNonRiconosciuto, match="cifrato"):
        analizza(bytes(pdf.output()))


def test_another_document_is_refused():
    with pytest.raises(FormatoNonRiconosciuto, match="non si presenta"):
        analizza(_pdf(_articoli_base(), titolo="REGOLAMENTO DEL CONDOMINIO"))


def test_too_few_articles_are_refused():
    with pytest.raises(FormatoNonRiconosciuto, match="meno di"):
        analizza(_pdf(_articoli_base()[:20]))


def test_too_many_pages_are_refused(monkeypatch):
    from mcp_legal_it.lib.cnf import parser

    monkeypatch.setattr(parser, "MAX_PAGINE", 2)
    with pytest.raises(FormatoNonRiconosciuto, match="pagine"):
        analizza(_pdf(_articoli_base()))


@pytest.mark.parametrize("dati", [b"<html>not a pdf</html>", b"%PDF-1.4 truncated garbage"])
def test_bytes_that_are_not_a_readable_pdf_are_refused(dati):
    with pytest.raises(FormatoNonRiconosciuto):
        analizza(dati)


# ---------------------------------------------------------------------------
# The CNF's page: which PDF is the code
# ---------------------------------------------------------------------------

_PDF_CODICE = "/documents/20182/40227/NUOVO+CODICE+DEONTOLOGICO+FORENSE++-+agg.+2026.pdf/8abe?t=17"
_PAGINA = f"""
<a href="{_PDF_CODICE}">Testo</a>
<a href="{_PDF_CODICE}">Scarica</a>
<a href="/documents/20182/40227/NUOVO+CODICE+DEONTOLOGICO+FORENSE++-+agg.+2026+-+con+sanzioni.pdf/4c17?t=1">S</a>
<a href="/documents/20182/40227/GU+2026-02-05+-+Comunicazione+modifica+Codice+Deontologico+Forense.pdf/b1ff">GU</a>
<a href="https://www.consiglionazionaleforense.it/documents/20182/0/N.+1-C-2026+-+Entrata+in+vigore+art.+25+bis+Codice+Deontologico+Forense.pdf/9bc6">C</a>
<p>Il Codice Deontologico Forense in vigore dal 7 aprile 2026. Testo del Codice, come da ultimo modificato
con delibera del Consiglio Nazionale Forense n. 959 del 23 gennaio 2026, pubblicata nella GU.</p>
"""


def test_the_code_pdf_is_the_one_named_as_the_code():
    assert cnf.link_del_pdf(_PAGINA) == "https://www.consiglionazionaleforense.it" + _PDF_CODICE


def test_a_page_without_the_code_pdf_is_refused():
    with pytest.raises(FormatoNonRiconosciuto, match="non collega"):
        cnf.link_del_pdf('<a href="/documents/x/Circolare.pdf/1">C</a>')


def test_two_code_pdfs_are_refused_rather_than_picked():
    altro = '<a href="/documents/20182/40227/CODICE+DEONTOLOGICO+FORENSE+-+2027.pdf/9">X</a>'
    with pytest.raises(FormatoNonRiconosciuto, match="2 PDF"):
        cnf.link_del_pdf(_PAGINA + altro)


def test_a_code_pdf_on_another_host_is_refused():
    with pytest.raises(FormatoNonRiconosciuto, match="non è sul sito del CNF"):
        cnf.link_del_pdf('<a href="https://example.org/NUOVO+CODICE+DEONTOLOGICO+FORENSE.pdf">X</a>')


def test_the_page_says_from_when_and_by_what_the_text_is_in_force():
    assert cnf._dalla_pagina(cnf._IN_VIGORE, _PAGINA) == "7 aprile 2026"
    assert cnf._dalla_pagina(cnf._DA_ULTIMO, _PAGINA) == (
        "delibera del Consiglio Nazionale Forense n. 959 del 23 gennaio 2026")


# ---------------------------------------------------------------------------
# Fetching: limits, outcomes, cache
# ---------------------------------------------------------------------------

async def _scarica(contenuto: bytes, headers: "dict | None" = None) -> bytes:
    transport = httpx.MockTransport(lambda req: httpx.Response(200, content=contenuto, headers=headers or {}))
    async with httpx.AsyncClient(transport=transport) as client:
        return await cnf._scarica_pdf(client, "https://www.consiglionazionaleforense.it/x.pdf")


async def test_a_pdf_past_the_size_limit_is_refused(monkeypatch):
    monkeypatch.setattr(cnf, "MAX_BYTES", 1000)
    with pytest.raises(FormatoNonRiconosciuto, match="limite"):
        await _scarica(b"%PDF-" + b"x" * 2000)


async def test_a_declared_size_past_the_limit_is_refused_before_reading(monkeypatch):
    monkeypatch.setattr(cnf, "MAX_BYTES", 1000)
    with pytest.raises(FormatoNonRiconosciuto, match="pesa"):
        await _scarica(b"%PDF-", headers={"content-length": "5000000"})


def _edizione(codice: Codice) -> cnf.Edizione:
    return cnf.Edizione(codice=codice, pdf_url="https://www.consiglionazionaleforense.it/documents/codice.pdf",
                        in_vigore_dal="7 aprile 2026", ultima_modifica="delibera n. 959 del 23 gennaio 2026",
                        salvato=cnf.time.time())


@pytest.fixture
def servito(monkeypatch, codice):
    async def edizione():
        return _edizione(codice)

    monkeypatch.setattr(cnf, "edizione", edizione)


async def test_an_article_is_served_with_its_notes_and_notices(servito):
    r = await cnf.fetch_articolo("25-bis")
    assert r["source"] == "cnf" and r["url"].endswith("codice.pdf")
    assert r["text"].startswith("### Art. 25-bis – Violazioni in materia di equo compenso⁽¹⁾\n\n1. ")
    assert [n["numero"] for n in r["note_aggiornamento"]] == ["1", "2"]
    assert "fanno fede le delibere pubblicate nella Gazzetta Ufficiale" in r["avvisi_cnf"][0]
    assert "in vigore dal 7 aprile 2026" in r["avvisi_cnf"][0]


@pytest.mark.parametrize("testo, data", [("7 aprile 2026", "2026-04-07"), ("1° luglio 2026", "2026-07-01"),
                                         ("1º Luglio 2026", "2026-07-01"), ("31 febbraio 2026", None),
                                         ("7 aprele 2026", None), ("", None), ("aprile 2026", None)])
def test_the_date_in_force_is_read(testo, data):
    letta = cnf.data_in_vigore(testo)
    assert (letta.isoformat() if letta else None) == data


def _servito_dal(monkeypatch, codice, in_vigore_dal: str) -> None:
    async def edizione():
        return cnf.Edizione(codice=codice, pdf_url="https://www.consiglionazionaleforense.it/documents/codice.pdf",
                            in_vigore_dal=in_vigore_dal, ultima_modifica="", salvato=cnf.time.time())

    monkeypatch.setattr(cnf, "edizione", edizione)


async def test_a_text_published_before_it_comes_into_force_is_not_served_as_in_force(monkeypatch, codice):
    monkeypatch.setenv("LEGAL_TODAY", "2026-03-01")
    _servito_dal(monkeypatch, codice, "7 aprile 2026")
    r = await cnf.fetch_articolo("7")
    assert r["text"] and r["not_in_force"] is True
    assert r["upcoming"] == {"change": None, "valid_from": "2026-04-07"}


async def test_a_text_in_force_since_a_past_day_is_in_force(monkeypatch, codice):
    monkeypatch.setenv("LEGAL_TODAY", "2026-04-07")
    _servito_dal(monkeypatch, codice, "7 aprile 2026")
    r = await cnf.fetch_articolo("7")
    assert r["text"] and "not_in_force" not in r and "upcoming" not in r


@pytest.mark.parametrize("in_vigore_dal", ["", "nei termini di legge"])
async def test_a_date_in_force_that_cannot_be_read_is_said(monkeypatch, codice, in_vigore_dal):
    _servito_dal(monkeypatch, codice, in_vigore_dal)
    r = await cnf.fetch_articolo("7")
    assert r["text"] and "not_in_force" not in r
    assert any("non indica in modo leggibile" in a for a in r["avvisi_cnf"]), r["avvisi_cnf"]


async def test_cite_law_and_verifica_say_a_text_not_in_force_yet(monkeypatch, codice):
    from mcp_legal_it.tools.legal_citations import _cite_law_impl, _verifica_citazioni_struct

    monkeypatch.setenv("LEGAL_TODAY", "2026-03-01")
    _servito_dal(monkeypatch, codice, "7 aprile 2026")
    j = json.loads(await _cite_law_impl("art. 7 codice deontologico forense", formato="json"))
    assert j["not_in_force"] is True and j["upcoming"]["valid_from"] == "2026-04-07"
    assert j["avvisi"][0].startswith("testo non ancora in vigore: entra in vigore il 2026-04-07")
    out = await _verifica_citazioni_struct("art. 7, comma 2, codice deontologico forense")
    assert out["citazioni"][0]["verdetto"] == "non in vigore", out


async def test_an_article_the_code_lacks_is_not_found(servito):
    r = await cnf.fetch_articolo("99")
    assert r["esito"] == "articolo_non_trovato" and not r["text"]


@pytest.mark.parametrize("errore, frammento", [
    (cnf.CnfNonDisponibile("sito del CNF non raggiungibile (ConnectError)"), "non raggiungibile"),
    (FormatoNonRiconosciuto("l'indice e il testo non elencano gli stessi articoli"), "non è nel formato atteso"),
])
async def test_a_site_or_pdf_that_cannot_be_read_serves_no_text(monkeypatch, errore, frammento):
    async def edizione():
        raise errore

    monkeypatch.setattr(cnf, "edizione", edizione)
    r = await cnf.fetch_articolo("68")
    assert r["esito"] == "verifica_non_disponibile" and not r["text"] and frammento in r["error"]


def test_the_code_read_is_kept_on_disk_for_a_day(monkeypatch, codice):
    e = _edizione(codice)
    cnf._scrivi(e)
    cnf.svuota_memoria()
    tenuta = cnf._tenuta()
    assert tenuta is not None and tenuta.codice.articolo("25-bis").note == codice.articolo("25-bis").note
    assert list(tenuta.codice.articoli) == list(codice.articoli)
    cnf.svuota_memoria()
    monkeypatch.setattr(cnf.time, "time", lambda: e.salvato + cnf.TTL_SECONDI + 1)
    assert cnf._tenuta() is None and not cnf._path().exists()


def test_a_damaged_record_is_dropped_and_the_site_read_again(codice):
    cnf._dir().mkdir(parents=True, exist_ok=True)
    cnf._path().write_bytes(b"\x1f\x8b not gzip at all")
    assert cnf._tenuta() is None and not cnf._path().exists()


def test_a_record_from_the_future_is_not_trusted(monkeypatch, codice):
    e = _edizione(codice)
    cnf._scrivi(e)
    cnf.svuota_memoria()
    monkeypatch.setattr(cnf.time, "time", lambda: e.salvato - 3600)
    assert cnf._tenuta() is None


def test_nothing_is_written_with_the_cache_off(monkeypatch, codice):
    monkeypatch.setenv("LEGAL_CACHE", "off")
    cnf._scrivi(_edizione(codice))
    assert not cnf._path().exists()


async def test_the_site_unreachable_is_said(monkeypatch):
    """The unit tests' network block stands for a site that does not answer."""
    r = await cnf.fetch_articolo("68")
    assert r["esito"] == "verifica_non_disponibile" and "non raggiungibile" in r["error"]


async def test_an_unexpected_failure_is_said_never_raised(monkeypatch):
    async def edizione():
        raise RuntimeError("boom")

    monkeypatch.setattr(cnf, "edizione", edizione)
    r = await cnf.fetch_articolo("68")
    assert r["esito"] == "verifica_non_disponibile" and "RuntimeError" in r["error"]


@pytest.fixture
def sito(monkeypatch):
    """The CNF's site, served from memory: the page, the PDF; *risposte* overrides by path."""
    richieste: list[str] = []
    risposte: dict[str, httpx.Response] = {}
    pdf = _pdf(_articoli_base())

    async def servi(self, request):
        richieste.append(request.url.path)
        if request.url.path in risposte:
            return risposte[request.url.path]
        if request.url.path == "/codice-deontologico-forense":
            return httpx.Response(200, html=_PAGINA)
        if request.url.path.endswith("/8abe"):
            return httpx.Response(200, content=pdf, headers={"content-type": "application/pdf"})
        return httpx.Response(404)

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", servi)
    return richieste, risposte


async def test_the_code_is_read_from_the_site_once_and_kept(sito):
    from mcp_legal_it.lib import _sources

    richieste, _ = sito
    with _sources.recording() as fonti:
        e = await cnf.edizione()
    assert e.in_vigore_dal == "7 aprile 2026" and e.pdf_url.endswith("/8abe?t=17")
    assert e.codice.articolo("25-bis") is not None
    assert {d for d, _ in fonti} == {"cnf"}
    assert len(richieste) == 2
    await cnf.edizione()
    cnf.svuota_memoria()
    await cnf.edizione()  # from disk
    assert len(richieste) == 2


async def test_a_site_down_is_shared_by_the_calls_that_follow(sito):
    richieste, risposte = sito
    risposte["/codice-deontologico-forense"] = httpx.Response(404)
    for _ in range(3):
        with pytest.raises(cnf.CnfNonDisponibile):
            await cnf.edizione()
    assert len(richieste) == 1


def test_one_lock_per_event_loop(sito):
    """The library may run several event loops one after the other: the lock is not shared."""
    import asyncio

    async def due():
        await asyncio.gather(cnf.edizione(), cnf.edizione())

    asyncio.run(due())
    cnf.svuota_memoria()
    cnf._path().unlink()
    asyncio.run(due())


# ---------------------------------------------------------------------------
# The tools
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("nome", ["codice deontologico forense", "del codice deontologico forense", "NCDF",
                                  "nuovo codice deontologico forense"])
def test_the_resolver_knows_the_code(nome):
    from mcp_legal_it.core.riferimenti import _resolve_act

    assert _resolve_act(nome)["tipo_atto"] == "codice deontologico forense"


def test_another_professions_code_is_not_taken_for_it():
    from mcp_legal_it.core.riferimenti import _resolve_act

    assert _resolve_act("codice deontologico") is None


def test_cdf_is_not_taken_for_the_code():
    """«CDF» may be the Carta dei diritti fondamentali: «art. 47 CDF» must not serve the code's art. 47."""
    from mcp_legal_it.core.riferimenti import _resolve_act

    assert _resolve_act("CDF") is None and _resolve_act("c.d.f.") is None


async def test_cite_law_serves_the_article(servito):
    from mcp_legal_it.tools.legal_citations import _cite_law_impl

    out = await _cite_law_impl("art. 25-bis codice deontologico forense", include_annotations=True)
    assert out.startswith("**Fonte**: Consiglio nazionale forense (PDF del codice deontologico) — https://")
    assert "**Attenzione**: testo consolidato pubblicato dal Consiglio nazionale forense" in out
    assert "### Art. 25-bis – Violazioni in materia di equo compenso" in out
    assert "**Aggiornamenti**\n\n(1) Articolo aggiunto" in out
    assert "**Annotazioni Brocardi**: non disponibili per il codice deontologico forense" in out


async def test_cite_law_json(servito):
    from mcp_legal_it.tools.legal_citations import _cite_law_impl

    j = json.loads(await _cite_law_impl("art. 6 ncdf", formato="json"))
    assert j["fonte"] == "cnf" and j["errore"] is None
    assert j["testo"].startswith("### Art. 6 – Rubrica dell'articolo 6")
    assert j["note_aggiornamento"] == [] and j["avvisi"][0].startswith("testo consolidato pubblicato")


@pytest.mark.parametrize("versione", ["originale", "futura"])
async def test_only_the_text_in_force_exists(servito, versione):
    from mcp_legal_it.tools.legal_citations import _cite_law_impl

    out = await _cite_law_impl("art. 68 codice deontologico forense", versione=versione)
    assert out.startswith("**Errore**")


@pytest.mark.parametrize("impl", ["_cerca_brocardi_impl", "_fetch_full_act_impl", "_fetch_act_index_impl",
                                  "_download_law_pdf_impl"])
async def test_the_other_norm_tools_point_to_cite_law(impl):
    from mcp_legal_it.tools import legal_citations

    out = await getattr(legal_citations, impl)("art. 68 codice deontologico forense")
    assert "solo il testo dei singoli articoli" in out and "cite_law" in out


async def test_the_library_refuses_the_whole_code():
    from mcp_legal_it.api import _norme

    assert _norme._atto("codice deontologico forense")[0] == "non_supportata"


async def test_storia_norma_refuses_the_code():
    from mcp_legal_it.api import modifiche_articolo

    r = await modifiche_articolo("art. 68 codice deontologico forense")
    assert r.esito == "non_supportata" and "non è su Normattiva" in r.errore


@pytest.mark.parametrize("articolo, campi, frammento", [
    ("allegato 1", {}, "non ha allegati"),
    ("", {}, "indicare l'articolo"),
    ("68", {"data_versione": "2020-01-01"}, "solo il testo vigente"),
    ("68", {"versione": "originale"}, "solo il testo vigente"),
])
async def test_the_reader_refuses_what_the_cnf_does_not_publish(articolo, campi, frammento):
    from mcp_legal_it.lib.visualex import Norma, NormaVisitata
    from mcp_legal_it.lib.visualex.scraper import fetch_article

    nv = NormaVisitata(norma=Norma(tipo_atto="codice deontologico forense"), numero_articolo=articolo, **campi)
    r = await fetch_article(nv)
    assert not r["text"] and frammento in r["error"]


async def test_verifica_citazioni_reads_the_code(servito):
    from mcp_legal_it.tools.legal_citations import _verifica_citazioni_struct

    out = await _verifica_citazioni_struct("art. 7, comma 2, codice deontologico forense\nart. 99 NCDF")
    verdetti = [c["verdetto"] for c in out["citazioni"]]
    assert verdetti[0] == "verificata" and verdetti[1] != "verificata", out


# ---------------------------------------------------------------------------
# The CNF's real layout, offline: the runs of the 2026 PDF
# ---------------------------------------------------------------------------

_FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "cnf" / "runs.json.gz"


def _runs_reali() -> tuple[list, str]:
    rec = json.loads(gzip.decompress(_FIXTURE.read_bytes()))
    return [parser._Run(**r) for r in rec["runs"]], rec["titolo"]


def _leggi(monkeypatch, runs, titolo="") -> Codice:
    monkeypatch.setattr(parser, "_runs", lambda dati, tempo=None: (runs, titolo))
    return analizza(b"%PDF-1.7 (runs from the fixture)")


@pytest.fixture
def reale(monkeypatch) -> Codice:
    return _leggi(monkeypatch, *_runs_reali())


def test_the_real_pdf_is_read_whole(reale):
    numeri = list(reale.articoli)
    assert len(numeri) == 75 and numeri[0] == "1" and numeri[-1] == "73"
    assert numeri.index("25-bis") == numeri.index("25") + 1 and numeri.index("62-bis") == numeri.index("62") + 1


def test_the_real_art_68(reale):
    art = reale.articolo("68")
    assert art.rubrica == "Assunzione di incarichi contro una parte già assistita"
    assert [p[:3] for p in art.paragrafi] == ["1. ", "2. ", "3. ", "4. ", "5. ", "6. "]
    assert not art.note


def test_the_real_art_25_bis_has_its_notes(reale):
    art = reale.articolo("25-bis")
    assert art.segni_rubrica == ["2"]
    assert [n["numero"] for n in art.note] == ["2", "3", "4", "5"]
    assert art.testo().startswith("### Art. 25-bis – ") and "⁽²⁾\n\n1. " in art.testo()


def test_a_note_on_a_title_belongs_to_no_article(reale):
    """Note 8 is on the heading of TITOLO IV: no article claims it."""
    assert all(n["numero"] != "8" for a in reale.articoli.values() for n in a.note)


def test_the_real_text_has_no_footers_nor_index(reale):
    testi = [p for a in reale.articoli.values() for p in a.paragrafi]
    assert not any("pagina" in p.lower() and " di " in p for p in testi)
    assert not any("....." in p for p in testi)


def test_a_note_line_far_from_its_note_is_refused(monkeypatch):
    """A note goes on below, or at the head of the next page's notes: a line of a page-13 note
    found on page 17, after page 15's notes, is not taken as the end of whichever note came last."""
    runs, titolo = _runs_reali()
    riga = next(r for r in parser._righe(runs) if r.pagina == 13 and r.corpo == 10.0
                and "".join(x.testo for x in r.runs).strip() == "forensi vigenti».")
    for run in riga.runs:
        run.pagina, run.y = 17, 80.0
    with pytest.raises(FormatoNonRiconosciuto, match="testo in nota senza numero"):
        _leggi(monkeypatch, runs, titolo)


# ---------------------------------------------------------------------------
# A PDF with far more text than the code: the extraction stops itself
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("tetto", ["MAX_RUN", "MAX_CARATTERI", "MAX_CHIAMATE"])
def test_more_text_than_the_code_stops_the_extraction(monkeypatch, tetto):
    monkeypatch.setattr(parser, tetto, 100)
    with pytest.raises(FormatoNonRiconosciuto, match="molto più testo"):
        analizza(_pdf(_articoli_base()))


def test_the_extraction_stops_at_its_time_limit():
    with pytest.raises(FormatoNonRiconosciuto, match="oltre 0 secondi"):
        analizza(_pdf(_articoli_base()), tempo=0)


def test_the_call_waits_a_little_longer_than_the_extraction():
    assert cnf.TIMEOUT_ANALISI > parser.TEMPO_MASSIMO


# ---------------------------------------------------------------------------
# Live: the CNF's own PDF
# ---------------------------------------------------------------------------

@pytest.mark.live
async def test_live_the_cnf_pdf_is_read_whole():
    cnf.svuota_memoria()
    e = await cnf.edizione()
    numeri = list(e.codice.articoli)
    assert numeri[0] == "1" and "25-bis" in numeri and "62-bis" in numeri and len(numeri) >= 75
    art = e.codice.articolo("68")
    assert art.rubrica == "Assunzione di incarichi contro una parte già assistita"
    assert [p[:2] for p in art.paragrafi] == ["1.", "2.", "3.", "4.", "5.", "6."]

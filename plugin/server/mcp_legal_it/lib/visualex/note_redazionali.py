"""The editorial notes of a Normattiva article («Note all'art. 13: …»), read beside its text.

When an act is published in the Gazzetta Ufficiale with notes, the competent administration
drafts them under art. 10, commi 2 and 3, d.P.R. 1092/1985, «al solo fine di facilitare la
lettura delle disposizioni di legge modificate o alle quali è operato il rinvio. Restano
invariati il valore e l'efficacia degli atti legislativi qui trascritti» (their own
Avvertenza). They name the acts the article cites and often transcribe the text of other
provisions **as it stood on the day of publication**: never the text in force of those
provisions, and never part of the article.

Normattiva keeps them on the versions of an article that were never replaced: the original
text (``@originale``) and the current text of an article never amended. Measured on
2 Nov 2026 (59 article pages): 12 of 21 original texts, 3 of 38 current ones; from 83 to
62,000 characters, median about 8,000.

- The page puts them in one ``div.note-akn`` inside ``div.bodyTesto``, after the commi;
  lines are split by ``<br>``. VisuaLex's extractor (``normattiva_html``, frozen byte for
  byte) reads the commi only, so its ``article_text`` never carries them in the comma and
  plain-text shapes; it does in the fallback shape, which reads the whole body.
- The Akoma Ntoso export puts the same notes in an ``authorialNote`` inside a ``section`` of
  the ``article``, after its paragraphs; lines are split by newlines. ``akn_parser`` renders
  the paragraphs only, so the export's text does not carry them either, but for an article
  without paragraphs, rendered from all its content.

A block holds one or more sections, each under its own heading line: «Avvertenza:», «Note
alle premesse:» (on art. 1 only: about the act's preamble, not the article), «Note all'art.
13:» or «Nota all'art. 13:». This module splits the block at those headings (``sezioni``) and
keeps the notes to the article only (``dell_articolo``, decision LI-058), each with its words
as Normattiva writes them: links become their text, whitespace is normalised inside each
line, line breaks are kept, nothing else.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

from bs4 import NavigableString, Tag

from . import normattiva_html as _nh

_BLOCCO_HTML = "note-akn"
# The «N O T E» banner over the first block of an act: a title, not a note.
_BANNER = re.compile(r"N\s*O\s*T\s*E")
# A heading opens a line and ends with a colon, in one of the three kinds a block holds:
# «Avvertenza:», «Note alle premesse:» (the Gazzetta also writes «Note alla premesse:») and the
# notes to the article, «Note all'art. 13:», «Nota all'art. 4:», «Note agli articoli 2 e 3:».
# Capitalised as the Gazzetta writes them. Any other line, «Note al decreto …:» inside a note
# included, is words of the section it sits in: never a heading, so never dropped with one.
# The words after the colon on the same line, if any, are the section's first line; a heading
# alone on its line may end with a full stop instead.
_INTESTAZIONE = re.compile(
    r"(Avvertenza|AVVERTENZA"
    r"|(?:Not[ae]|NOT[AE])\s+(?:all[ae]|ALL[AE])\s+(?:premesse|PREMESSE)"
    r"|(?:Not[ae]|NOT[AE])\s+(?:all['’]\s*|agli\s+|ALL['’]\s*|AGLI\s+)(?:art|ART)[^:]{0,120}?)"
    r"(?:\s*:\s*(.*)|\s*\.)"  # «Note alle premesse.»: a full stop, the heading alone on its line
)


def _righe_html(nodo: Tag) -> list[str]:
    """The lines of an HTML note block: ``<br>`` and block elements end a line, links are text."""
    pezzi: list[str] = []

    def visita(el) -> None:
        for figlio in el.children:
            if isinstance(figlio, NavigableString):
                pezzi.append(str(figlio))
            elif isinstance(figlio, Tag):
                if figlio.name == "br":
                    pezzi.append("\n")
                elif figlio.name in ("p", "div", "li"):
                    pezzi.append("\n")
                    visita(figlio)
                    pezzi.append("\n")
                else:
                    visita(figlio)

    visita(nodo)
    return "".join(pezzi).split("\n")


def _righe_akn(nodo) -> list[str]:
    """The lines of an Akoma Ntoso ``authorialNote``: its own newlines, ``<p>``/``<br>`` too."""
    pezzi: list[str] = []

    def visita(el) -> None:
        if el.text:
            pezzi.append(el.text)
        for figlio in el:
            n = _nome(figlio)
            if n == "br":
                pezzi.append("\n")
            elif n in ("p", "div", "li"):
                pezzi.append("\n")
                visita(figlio)
                pezzi.append("\n")
            elif n:
                visita(figlio)
            if figlio.tail:
                pezzi.append(figlio.tail)

    visita(nodo)
    return "".join(pezzi).split("\n")


def sezioni(righe: Iterable[str], ordine_da: int = 1) -> list[dict[str, Any]]:
    """Split the lines of a note block at their headings: ``[{intestazione, testo, ordine}]``.

    ``intestazione`` is the heading without its colon («Note all'art. 13»), ``""`` for words
    before the first heading; ``testo`` the section's lines, whitespace normalised, joined
    by ``\\n``; ``ordine`` the section's position, from *ordine_da*.
    """
    risultato: list[dict[str, Any]] = []
    corrente: "dict[str, Any] | None" = None
    for grezza in righe:
        riga = " ".join(grezza.split())
        if not riga or _BANNER.fullmatch(riga):
            continue
        m = _INTESTAZIONE.fullmatch(riga)
        if m:
            corrente = {"intestazione": " ".join(m.group(1).split()), "righe": [m.group(2)] if m.group(2) else []}
            risultato.append(corrente)
            continue
        if corrente is None:
            corrente = {"intestazione": "", "righe": []}
            risultato.append(corrente)
        corrente["righe"].append(riga)
    return [{"intestazione": s["intestazione"], "testo": "\n".join(s["righe"]), "ordine": i}
            for i, s in enumerate(risultato, start=ordine_da)]


# The notes to the article itself (LI-058: the only ones kept): «Note all'art. 13», «Nota
# all'articolo 4», «Note agli articoli 2 e 3». Not the Avvertenza, not the «Note alle premesse».
_DELL_ARTICOLO = re.compile(r"not[ae]\s+(?:all['’]\s*|agli\s+)art", re.IGNORECASE)


def dell_articolo(sezioni_lette: list[dict[str, Any]], ordine_da: int = 1) -> list[dict[str, Any]]:
    """Only the sections of notes to the article (``_DELL_ARTICOLO``), renumbered from *ordine_da*.

    Decision LI-058: the Avvertenza says what every such note is (and the tools say it in
    their own words); the «Note alle premesse» are about the act's preamble, not the article;
    words before any heading belong to no article.
    """
    tenute = [s for s in sezioni_lette if _DELL_ARTICOLO.match(s["intestazione"])]
    return [{**s, "ordine": i} for i, s in enumerate(tenute, start=ordine_da)]


def nel_testo(corpo: Tag, blocco: Tag) -> bool:
    """Whether VisuaLex's extractor already puts *blocco* in its text, following its dispatch.

    Never in the comma and plain-text shapes; always in the fallback shape, which reads the
    whole body. In a code's attachment shape (picked on the class, any tag) it reads the
    ``span`` of that class, every ``div.ins-akn`` and every ``div.art_aggiornamento-akn``:
    the block is in the text when it sits inside one of them.
    """
    if corpo.find(class_=_nh.AKN_COMMA_DIV) or corpo.find(class_=_nh.AKN_JUST_TEXT):
        return False
    if not corpo.find(class_=_nh.ATTACHMENT_TEXT):
        return True
    allegato = corpo.find("span", class_=_nh.ATTACHMENT_TEXT)
    for p in blocco.parents:
        if p is corpo:
            break
        classi = p.get("class") or []
        if (p is allegato or (p.name == "div" and ("ins-akn" in classi or "art_aggiornamento-akn" in classi))):
            return True
    return False


def leggi_html(corpo: Tag) -> dict[str, Any]:
    """The editorial notes of an article's ``div.bodyTesto``: ``{"note": [...], "nel_testo": bool}``.

    ``note`` is the notes to the article (``dell_articolo``) of every ``note-akn`` block, in
    page order (``[]`` when the page has none); ``nel_testo`` says the extractor's text already
    carries them, so a caller that prints the text does not print them twice.
    """
    note: list[dict[str, Any]] = []
    nel = False
    # Any element of the class; a block holding another is the other's shell.
    blocchi = [b for b in corpo.find_all(class_=_BLOCCO_HTML) if b.find(class_=_BLOCCO_HTML) is None]
    for blocco in blocchi:
        lette = dell_articolo(sezioni(_righe_html(blocco)), ordine_da=len(note) + 1)
        note.extend(lette)
        nel = nel or (bool(lette) and nel_testo(corpo, blocco))
    return {"note": note, "nel_testo": nel}


def _nome(el) -> str:
    return el.tag.rsplit("}", 1)[-1] if isinstance(el.tag, str) else ""


def leggi_akn(articolo) -> dict[str, Any]:
    """The editorial notes of an Akoma Ntoso ``<article>``: ``{"note": [...], "nel_testo": bool}``.

    ``note`` is the notes to the article (``dell_articolo``) of its ``authorialNote``s outside
    its paragraphs (a note inside one is already in the text the paragraph renders); ``[]``
    for an article without notes.
    ``nel_testo``: ``akn_parser`` renders an article without paragraphs from all its
    ``content``, notes included, so its text already carries them.
    """
    note: list[dict[str, Any]] = []
    for nota in articolo.iter("{*}authorialNote"):
        if any(_nome(a) == "paragraph" for a in nota.iterancestors()):
            continue
        note.extend(dell_articolo(sezioni(_righe_akn(nota)), ordine_da=len(note) + 1))
    senza_commi = not any(_nome(figlio) == "paragraph" for figlio in articolo)
    return {"note": note, "nel_testo": bool(note) and senza_commi}

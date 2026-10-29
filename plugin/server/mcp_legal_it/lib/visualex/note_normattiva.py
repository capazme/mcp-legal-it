"""The update notes of a Normattiva article page («AGGIORNAMENTO (n)»), read beside VisuaLex's text.

A Normattiva article page carries, after the article, one ``div.art_aggiornamento-akn``
per note: a separator line, the title «AGGIORNAMENTO (10)» and the note's own words
(``div.art_aggiornamento_testo-akn``). The body calls each note by its number, «((10))» or
«(1)». The notes say what the text alone does not: a Corte costituzionale declaration of
illegitimacy (art. 3 d.lgs. 23/2015, C. cost. 194/2018), a deferred effect, an exclusion.

VisuaLex's extractor (``normattiva_html``, frozen byte for byte) keeps them in its text for
two of its four page shapes (a code's attachment, the fallback) and drops them for the
other two (the article in comma divs, the plain text span). Its ``article_text`` must not
change, so the notes are read here, from the same ``div.bodyTesto``, into a field of their
own; ``nel_testo`` says whether the text already carries them.

A note this module reads is Normattiva's wording only: the separator and the heading are
dropped, links become their text, whitespace is normalised, nothing else.
"""

from __future__ import annotations

import re
from typing import Any

from bs4 import Tag

from . import normattiva_html as _nh

_BLOCCO = "art_aggiornamento-akn"
_TITOLO = "art_aggiornamento_title-akn"
_TESTO = "art_aggiornamento_testo-akn"
_NUMERO_TITOLO = re.compile(r"AGGIORNAMENTO\s*\((\d+[a-z]*)\)", re.IGNORECASE)
_SEPARATORE = re.compile(r"^-{3,}\s*")
# «((10))» in the body: the double brackets are Normattiva's call of a note, never prose.
_CHIAMATA_DOPPIA = re.compile(r"\(\((\d+[a-z]*)\)\)")
_CORTE = re.compile(r"corte\s+costituzionale|c\.\s*cost\.", re.IGNORECASE)
_SENTENZA = re.compile(r"\bsentenz[ae]\b", re.IGNORECASE)


def _testo(nodo: Tag) -> str:
    # No separator between the pieces: «n. 87</a>, convertito» stays «n. 87, convertito»;
    # the page's own spaces and line breaks are the only ones, then normalised.
    return " ".join(nodo.get_text("").split())


def note_nel_testo(corpo: Tag) -> bool:
    """Whether VisuaLex's extractor already puts the notes in its text (its shapes 3 and 4)."""
    if corpo.find(class_=_nh.AKN_COMMA_DIV) or corpo.find(class_=_nh.AKN_JUST_TEXT):
        return False
    return True


def leggi_note(corpo: Tag, testo: str) -> dict[str, Any]:
    """The update notes of an article's ``div.bodyTesto``, beside its extracted *testo*.

    Returns ``{"note": [{numero, testo, ordine, corte_costituzionale}], "non_lette": bool,
    "nel_testo": bool}``:

    - ``note``: in page order, ``ordine`` from 1; ``[]`` when the page has none;
    - ``non_lette``: a note block without a readable number or text, or a call «((n))» in
      the body with no note *n* read;
    - ``nel_testo``: the extractor's text already carries them (a code's attachment, the
      fallback shape): a caller that prints the text must not print them again.
    """
    note: list[dict[str, Any]] = []
    non_lette = False
    blocchi = corpo.find_all("div", class_=_BLOCCO)
    for blocco in blocchi:
        titolo = blocco.find(class_=_TITOLO)
        numero = _NUMERO_TITOLO.search(_testo(titolo)) if titolo is not None else None
        corpo_nota = blocco.find(class_=_TESTO)
        parole = _SEPARATORE.sub("", _testo(corpo_nota)) if corpo_nota is not None else ""
        if numero is None or not parole:
            non_lette = True
            continue
        note.append({
            "numero": numero.group(1),
            "testo": parole,
            "ordine": len(note) + 1,
            "corte_costituzionale": bool(_CORTE.search(parole) and _SENTENZA.search(parole)),
        })
    # A «((n))» call with no note n read: a note the reader cannot see. A plain «(n)» is a
    # call only when note n exists, so it can never name a missing one.
    if set(_CHIAMATA_DOPPIA.findall(testo or "")) - {n["numero"] for n in note}:
        non_lette = True
    return {"note": note, "non_lette": non_lette, "nel_testo": note_nel_testo(corpo)}

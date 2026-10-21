# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, You can obtain one at
# https://mozilla.org/MPL/2.0/.
#
# Imported from VisuaLex (MPL-2.0), services/visualex/visualex_api/services/normattiva_scraper.py at eca698dc.
# Adapted: the scraper's text extraction (``estrai_da_html`` and its four ``_estrai_testo_*``),
# moved from methods of ``NormattivaScraper`` to functions, with the selectors of
# ``tools/selectors.py`` inlined and without structlog. The extraction itself is unchanged:
# the same parser (``html.parser``), the same walk, the same clean-up.

"""Normattiva's HTML article page -> ``article_text``, as VisuaLex freezes it.

``article_text`` is a data contract, not a string: VisuaLex anchors highlights and
notes to character offsets in it, and its renderer drops an anchor in silence when
one character moves (VisuaLex's root CLAUDE.md, rule 23). So this module is
VisuaLex's extractor, kept byte for byte: ``html.parser`` and not ``lxml`` (the two
repair malformed markup differently, c.p. art. 524 comes out one space apart), the
four page shapes, the repealed-article notice outside the attachment span. Do not
"improve" it: a change here moves every anchor after it, for every reader.
``tests/unit/test_normattiva_html.py`` checks it against texts VisuaLex returned.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional, Tuple, Union

from bs4 import BeautifulSoup, NavigableString, Tag

# tools/selectors.py NormattivaSelectors
BODY_TESTO = "bodyTesto"
AKN_ARTICLE_NUMBER = "article-num-akn"
AKN_ARTICLE_TITLE = "article-heading-akn"
AKN_COMMA_DIV = "art-comma-div-akn"
AKN_JUST_TEXT = "art-just-text-akn"
ATTACHMENT_TEXT = "attachment-just-text"


class ParsingError(Exception):
    """The page is not an article page this extractor can read (no ``div.bodyTesto``, a broken shape)."""


def parse_document(atto: str) -> BeautifulSoup:
    return BeautifulSoup(atto, 'html.parser')


def corpo_testo(soup: BeautifulSoup) -> Optional[Tag]:
    """The page's ``div.bodyTesto``, the part every extractor reads; None when absent."""
    return soup.find('div', class_=BODY_TESTO)


def estrai_da_html(atto: str, comma: Optional[str] = None, get_link_dict: bool = False) -> Union[str, Dict[str, Any]]:
    try:
        soup: BeautifulSoup = parse_document(atto)
        corpo: Optional[Tag] = corpo_testo(soup)
        if corpo is None:
            raise ParsingError("Missing expected div.bodyTesto in Normattiva response")
        return estrai_da_corpo(corpo, get_link_dict=get_link_dict)
    except ParsingError:
        raise
    except Exception as e:
        raise ParsingError(f"Failed to extract text from HTML: {e}") from e


def estrai_da_corpo(corpo: Tag, get_link_dict: bool = False) -> Union[str, Dict[str, Any]]:
    """``estrai_da_html`` on a ``div.bodyTesto`` already parsed (one parse serves text and checks)."""
    if corpo.find(class_=AKN_COMMA_DIV):
        # SCENARIO 1: Formattazione AKN Dettagliata
        return _estrai_testo_akn_dettagliato(corpo, link=get_link_dict)
    elif corpo.find(class_=AKN_JUST_TEXT):
        # SCENARIO 2: Formattazione Semplice con `akn-just-text`
        return _estrai_testo_akn_semplice(corpo, link=get_link_dict)
    elif corpo.find(class_=ATTACHMENT_TEXT):
        # SCENARIO 3: Allegato o Testo senza Formattazione AKN
        return _estrai_testo_allegato(corpo, link=get_link_dict)
    else:
        # SCENARIO 4: Fallback - estrai tutto il testo visibile
        return _estrai_testo_fallback(corpo, link=get_link_dict)


def extract_text_recursive(
    element: Tag, link: bool = False, link_dict: Optional[Dict[str, str]] = None
) -> Tuple[str, Dict[str, str]]:
    if link_dict is None:
        link_dict = {}
    text_parts = []

    for child in element.children:
        if isinstance(child, NavigableString):
            text_parts.append(str(child))
        elif isinstance(child, Tag):
            if child.name == 'br':
                text_parts.append('\n')
            elif child.name == 'p':
                inner_text, _ = extract_text_recursive(child, link=link, link_dict=link_dict)
                text_parts.append(inner_text + '\n')
            elif child.name == 'li':
                inner_text, _ = extract_text_recursive(child, link=link, link_dict=link_dict)
                text_parts.append(' - ' + inner_text + '\n')
            elif child.name == 'a':
                link_text = ''.join(child.stripped_strings)
                link_url = child.get('href', '').strip()
                if link:
                    link_dict[link_text] = link_url
                inner_text, _ = extract_text_recursive(child, link=link, link_dict=link_dict)
                text_parts.append(inner_text)
            else:
                inner_text, _ = extract_text_recursive(child, link=link, link_dict=link_dict)
                text_parts.append(inner_text)
    return ''.join(text_parts), link_dict


def _estrai_testo_akn_dettagliato(corpo: Tag, link: bool = False) -> Union[str, Dict[str, Any]]:
    try:
        link_dict: Dict[str, str] = {}

        # Estrazione del numero e del titolo dell'articolo
        article_number_tag = corpo.find('h2', class_=AKN_ARTICLE_NUMBER)
        article_title_tag = corpo.find('div', class_=AKN_ARTICLE_TITLE)
        article_number = article_number_tag.get_text(strip=True) if article_number_tag else "Articolo non trovato"
        article_title = article_title_tag.get_text(strip=True) if article_title_tag else ""

        # Composizione del testo iniziale
        final_text = f"{article_number}\n{article_title}\n\n"

        # Estrazione dei commi
        commi = corpo.find_all('div', class_=AKN_COMMA_DIV)
        for comma_div in commi:
            comma_text, _ = extract_text_recursive(comma_div, link=link, link_dict=link_dict)
            final_text += comma_text.strip() + '\n\n'

        # Pulizia finale del testo
        final_text = re.sub(r'\n{3,}', '\n\n', final_text).strip()
        final_text = re.sub(r'[ \t]+', ' ', final_text)

        if link:
            return {"testo": final_text, "link": link_dict}
        return final_text
    except Exception as e:
        # Raise, never return a sentinel string: a returned "Error in ..." is truthy
        # and would be served as the text of the article.
        raise ParsingError(f"_estrai_testo_akn_dettagliato: {e}") from e


def _estrai_testo_akn_semplice(corpo: Tag, link: bool = False) -> Union[str, Dict[str, Any]]:
    try:
        link_dict: Dict[str, str] = {}

        # Estrazione del numero e del titolo dell'articolo
        article_number_tag = corpo.find('h2', class_=AKN_ARTICLE_NUMBER)
        article_title_tag = corpo.find('div', class_=AKN_ARTICLE_TITLE)
        article_number = article_number_tag.get_text(strip=True) if article_number_tag else ""
        article_title = article_title_tag.get_text(strip=True) if article_title_tag else ""

        final_text = f"{article_number}\n{article_title}\n\n"

        # Estrazione del contenuto del testo semplice
        just_text = corpo.find('span', class_=AKN_JUST_TEXT)
        if just_text:
            content_text, _ = extract_text_recursive(just_text, link=link, link_dict=link_dict)
            final_text += content_text.strip()

        final_text = re.sub(r'\n{3,}', '\n\n', final_text).strip()
        final_text = re.sub(r'[ \t]+', ' ', final_text)

        if link:
            return {"testo": final_text, "link": link_dict}
        return final_text
    except Exception as e:
        raise ParsingError(f"_estrai_testo_akn_semplice: {e}") from e


def _estrai_testo_allegato(corpo: Tag, link: bool = False) -> Union[str, Dict[str, Any]]:
    try:
        link_dict: Dict[str, str] = {}

        # Estrazione del contenuto dell'allegato
        attachment_text = corpo.find('span', class_=ATTACHMENT_TEXT)
        final_text = ""
        if attachment_text:
            content_text, _ = extract_text_recursive(attachment_text, link=link, link_dict=link_dict)
            final_text += content_text.strip()

        # A repealed article's notice normally sits INSIDE the attachment
        # span and is read with it (c.p. art. 544: "Art. 544. \n\n((ARTICOLO
        # ABROGATO ...))"). For c.p. art. 524 — and 523-526, 530, 539,
        # 541-543, 545-555 — Normattiva opens the span inside an <a> and
        # closes it after it; html.parser repairs that by closing the span
        # early, so the `div.ins-akn.art_abrogato-akn` lands in `corpo` as
        # a sibling of the span and the article came back as its label
        # alone ('Codice Penale-art. 524', HTTP 200). Read every ins-akn
        # block the span does not contain, in document order, appended the
        # way the in-span case already reads, so the text is never only
        # the act label. Blocks inside the span are untouched (frozen
        # output); `art_aggiornamento-akn` has its own pass.
        for block in corpo.find_all('div', class_='ins-akn'):
            if 'art_aggiornamento-akn' in (block.get('class') or []):
                continue
            if any(parent is attachment_text or 'ins-akn' in (parent.get('class') or [])
                   for parent in block.parents):
                continue
            block_text, _ = extract_text_recursive(block, link=link, link_dict=link_dict)
            if block_text.strip():
                final_text += '\n\n' + block_text.strip()

        # Estrazione degli aggiornamenti (se presenti)
        aggiornamenti = corpo.find_all('div', class_='art_aggiornamento-akn')
        for aggiornamento in aggiornamenti:
            agg_text, _ = extract_text_recursive(aggiornamento, link=link, link_dict=link_dict)
            final_text += '\n\n' + agg_text.strip()

        final_text = re.sub(r'\n{3,}', '\n\n', final_text).strip()
        final_text = re.sub(r'[ \t]+', ' ', final_text)

        if link:
            return {"testo": final_text, "link": link_dict}
        return final_text
    except Exception as e:
        raise ParsingError(f"_estrai_testo_allegato: {e}") from e


def _estrai_testo_fallback(corpo: Tag, link: bool = False) -> Union[str, Dict[str, Any]]:
    """
    Fallback extraction when no specific HTML pattern is recognized.
    Extracts all visible text from the body, useful for abrogated articles
    or articles with unusual structure.
    """
    try:
        link_dict: Dict[str, str] = {}

        # Extract all text content from corpo
        final_text, link_dict = extract_text_recursive(corpo, link=link, link_dict=link_dict)

        # Clean up the text
        final_text = re.sub(r'\n{3,}', '\n\n', final_text).strip()
        final_text = re.sub(r'[ \t]+', ' ', final_text)

        # If no text found, indicate the article may be empty/abrogated
        if not final_text.strip():
            final_text = "[Articolo senza contenuto o abrogato]"

        if link:
            return {"testo": final_text, "link": link_dict}
        return final_text
    except Exception as e:
        raise ParsingError(f"_estrai_testo_fallback: {e}") from e

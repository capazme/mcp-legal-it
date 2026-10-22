# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, You can obtain one at
# https://mozilla.org/MPL/2.0/.
#
# Imported from VisuaLex (MPL-2.0), services/visualex/visualex_api/services/eurlex_scraper.py at 493a8dd1
# (the consolidated-text reader, and ``extract_article_text`` with ``extract_table_text``) and
# services/visualex/visualex_api/tools/treextractor.py at 493a8dd1 (``strip_amendment_markers``).
# Adapted: the scraper's two methods are plain functions (no ``self``); structlog is a no-op
# ``log``, so the calls stay as they are; the Playwright fetch, the persistent cache and the
# recitals are left out (the page comes from CELLAR, ``scraper._fetch_eurlex_html``);
# ``DocumentNotFoundError`` is a local ``LookupError`` with VisuaLex's signature;
# ``normalize_article_key`` is this package's (VisuaLex's at 0f1477c2, linear: 493a8dd1 still
# carries the older quadratic one, with the same keys). The code is otherwise VisuaLex's, line
# for line: the article text it returns is frozen (docs/migration/visualex-inventory.md, rows
# 3.1 and 3.4).

"""EUR-Lex article text, as VisuaLex reads it: the Official Journal page and the consolidated one.

``extract_article_text(soup, article)`` is the entry point: a consolidated page
(``title-article-norm`` markup, a sector-0 CELEX) goes through ``extract_article_consolidated``,
any other page through the OJ strategies. It raises ``DocumentNotFoundError`` when the page
has no such article. The soup is VisuaLex's, ``html.parser``.
"""

import copy
import re

from .akn_parser import normalize_article_key


class _NoLog:
    """VisuaLex's structlog calls, kept as they are and doing nothing."""

    def __getattr__(self, name):
        return lambda *args, **kwargs: None


log = _NoLog()


class DocumentNotFoundError(LookupError):
    """VisuaLex's ``tools.exceptions.DocumentNotFoundError``, as the extractor raises it."""

    def __init__(self, message, urn=None):
        super().__init__(message)
        self.urn = urn


# A consolidated version's CELEX: sector 0, year, type letter, act number,
# then the consolidation date. "02002L0058-20091219" is Dir. 2002/58/CE as
# amended up to 19 December 2009. Sector 3 ("32002L0058") is the OJ act and
# is what the ELI URL already serves, so it is not accepted here. Matched
# with fullmatch and ASCII digits: `$` would let "…-20091219\n" through, and
# `\d` alone accepts other scripts' digits — neither belongs in a URL.
_CONSOLIDATED_CELEX = re.compile(r"0\d{4}[A-Z]\d{4}-\d{8}", re.ASCII)


# EUR-Lex marks amended passages inline as well as with block markers:
# "►M2 … ◄" (amending act), "►C2 … ◄" (corrigendum), "►B" (base act), and
# "▼M2" / "▼B" at the head of a replaced block. The glyphs are never part of
# the legal text.
_AMENDMENT_MARK = re.compile(r"\s*[►◄▼](?:[A-Z]\d*)?\s*")


def strip_amendment_markers(text: str) -> str:
    """Drop inline "►M2 … ◄" / "▼M2" markers and collapse the whitespace they leave."""
    return re.sub(r"[ \t\xa0]+", " ", _AMENDMENT_MARK.sub(" ", text or "")).strip()


# --- Consolidated texts ---------------------------------------------------
#
# EUR-Lex renders a consolidated version with a markup of its own: the number
# is <p class="title-article-norm">Articolo 5</p> (an ordinal suffix as
# <span class="norm">bis</span>), the rubrica <p class="stitle-article-norm">
# (bare, or inside <div class="eli-title">), the body in `norm` paragraphs or
# divs with `no-parag` numbers and `grid-list` tables for lettered points,
# and <p class="modref">▼M1</p> markers naming the amending act before each
# changed block. Recent consolidations wrap every article in
# <div class="eli-subdivision" id="art_N">; older ones are flat.
_CONS_ARTICLE_CLASS = "title-article-norm"
_CONS_RUBRICA_CLASS = "stitle-article-norm"
_CONS_SKIP_CLASSES = {"modref", "separator", "separator-short", "hd-modifiers", "footnote", "arrow"}
_CONS_BODY_CLASSES = {"norm", "grid-container", "grid-list", "list", "no-parag"}


def is_consolidated_markup(soup) -> bool:
    return soup.find("p", class_=_CONS_ARTICLE_CLASS) is not None


def _element_classes(element) -> set:
    return set(element.get("class", []) or [])


def _cons_text(element) -> str:
    # A `modref` marker ("▼M2", or "▼M2 —————" for a deleted point) is a
    # sibling of the article title only on older pages; a recent consolidation
    # nests it inside `div.norm` and the point grids, where a class check on
    # the sibling cannot see it. The soup is parsed per request, so removing
    # the markers in place is local to this call.
    for marker in element.find_all(class_="modref"):
        marker.decompose()
    # A separator between child nodes: "1." sits in its own span next to the
    # paragraph text, and NBSP is EUR-Lex's favourite space.
    text = strip_amendment_markers(element.get_text(" ", strip=True))
    # The separator also lands before punctuation when EUR-Lex closes a span
    # early: <span class="no-parag">1 <span class="italics">quater</span>. </span>
    # read "1 quater ." while "1 bis." elsewhere keeps the period inside the
    # span, and "lettera a )" / "articolo 14 bis , paragrafo 2" likewise.
    # Consolidated path only: the OJ extractor never comes through here.
    text = re.sub(r"\s+([.,;:)])", r"\1", text)
    # The same separator lands after an opening bracket: a footnote reference
    # is literal parens around a superscript link, (<a><span>1</span></a>),
    # and read "( 1 )" — the page shows "(1)".
    return re.sub(r"([(«])\s+", r"\1", text)


def _is_cons_point(element) -> bool:
    """A lettered or numbered point: a `grid-list` div on recent pages
    ("a) " in `grid-list-column-1`, the text in `grid-list-column-2`), a
    table row on older ones."""
    if element.name == "tr":
        return True
    return element.name == "div" and "grid-list" in _element_classes(element)


def _cons_points(element) -> list:
    """The outermost point containers below `element`, in document order.

    A point nested in another point (art. 3 n. 16 of eIDAS lists a) to d)
    inside the definition) belongs to that point's own lines, so the walk
    stops at the first point it meets on each branch.
    """
    points = []
    for child in element.find_all(recursive=False):
        if _is_cons_point(child):
            points.append(child)
        else:
            points.extend(_cons_points(child))
    return points


def _is_bare_point_wrapper(element) -> bool:
    """A class-less `<div style="margin-left: 24pt">` holding a `p.norm`: how
    the older flat pages (02002L0058) render "a) «utente»: …". Without it
    the 13 lettered points of art. 2, 4 and 10 of the ePrivacy directive were
    not text at all."""
    return (element.name == "div" and not _element_classes(element)
            and element.find(class_="norm") is not None)


def _cons_lines(element) -> list[str]:
    """One line per point, whatever the markup nests.

    A paragraph whose points sit inside its own `div.norm` yields its lead-in
    first ("3. Il quadro di interoperabilità risponde ai seguenti criteri:")
    and then one line per point; a point holding sub-points does the same;
    an element with no points is one line. This is the shape the OJ path
    gives through `extract_table_text` — one row, one line — and the archive
    anchors on it (gotcha 23), so it must not depend on where EUR-Lex chose
    to put the grid.
    """
    points = _cons_points(element)
    if not points:
        text = _cons_text(element)
        return [text] if text else []
    # The lead-in is the element's text with the points taken out. A copy is
    # detached from the soup, so the points stay in place for the lines below.
    lead = copy.copy(element)
    for point in _cons_points(lead):
        point.decompose()
    lines = []
    head = _cons_text(lead)
    if head:
        lines.append(head)
    for point in points:
        lines.extend(_cons_lines(point))
    return lines


def _heads_article(text, pattern) -> bool:
    """True when `text` opens with the heading `pattern` ("Articolo 1") and the
    number ends there: "Articolo 17" does not head article 1, or a request for a
    missing art. 1 would be served art. 17."""
    return text.startswith(pattern) and not text[len(pattern):len(pattern) + 1].isdigit()


def _cons_find_title(soup, article):
    wanted = normalize_article_key(str(article))
    for marker in soup.find_all("p", class_=_CONS_ARTICLE_CLASS):
        if normalize_article_key(marker.get_text(" ", strip=True)) == wanted:
            return marker
    return None


def extract_article_consolidated(soup, article) -> "str | None":
    """Article text from a consolidated page, or None when the page lacks it.

    Same line structure as the OJ extractor — "Articolo N", the rubrica, one
    line per paragraph, one line per lettered point — so a client sees the
    same shape whichever version it asked for. Modification markers are not
    text and are dropped.
    """
    title = _cons_find_title(soup, article)
    if title is None:
        return None
    lines = [_cons_text(title)]
    for sibling in title.find_next_siblings():
        classes = _element_classes(sibling)
        # Stop at the next article, the next chapter or annex heading, or
        # the amendments table. The `eli-subdivision` stop is for a flat page
        # whose next article is wrapped; on a subdivision page the walk ends
        # with the article's own div, since the title has no later siblings.
        if (_CONS_ARTICLE_CLASS in classes or "eli-subdivision" in classes
                or "hd-modifiers" in classes
                or any(c.startswith(("title-division", "title-annex")) for c in classes)):
            break
        if _CONS_RUBRICA_CLASS in classes:
            lines.append(_cons_text(sibling))
            continue
        if "eli-title" in classes:
            rubrica = sibling.find("p", class_=_CONS_RUBRICA_CLASS)
            if rubrica is not None:
                lines.append(_cons_text(rubrica))
            continue
        if classes & _CONS_SKIP_CLASSES:
            continue
        if (sibling.name == "table" or classes & _CONS_BODY_CLASSES
                or _is_bare_point_wrapper(sibling)):
            lines.extend(_cons_lines(sibling))
    return "\n".join(lines)


def extract_article_text(soup, article):
    log.info(f"Searching for article {article} in the document")

    if is_consolidated_markup(soup):
        text = extract_article_consolidated(soup, article)
        if text is None:
            log.warning(f"Article {article} not found in the consolidated document")
            raise DocumentNotFoundError(
                f"Article {article} not found in EUR-Lex consolidated document",
                urn=soup.find('link', rel='canonical')['href'] if soup.find('link', rel='canonical') else None
            )
        log.info(f"Article {article} text extracted from consolidated markup")
        return text

    # Multiple patterns to find article header (EUR-Lex structure may vary)
    search_patterns = [
        f"Articolo {article}",
        f"Article {article}",
        f"Art. {article}",
    ]

    article_section = None

    # Strategy 1: Look for <p class="ti-art"> (original selector)
    for pattern in search_patterns:
        article_section = soup.find(lambda tag: tag.name == 'p' and 'ti-art' in tag.get('class', []) and _heads_article(tag.get_text(strip=True), pattern))
        if article_section:
            log.debug(f"Found article with ti-art class using pattern: {pattern}")
            break

    # Strategy 2: Look for any element with class containing 'art' or 'title'
    if not article_section:
        for pattern in search_patterns:
            article_section = soup.find(lambda tag: tag.get('class') and any('art' in c.lower() or 'title' in c.lower() for c in tag.get('class', [])) and _heads_article(tag.get_text(strip=True), pattern))
            if article_section:
                log.debug(f"Found article with art/title class using pattern: {pattern}")
                break

    # Strategy 3: Look for any element whose text matches article pattern exactly
    if not article_section:
        article_regex = re.compile(rf'^Articolo\s+{re.escape(str(article))}\b', re.IGNORECASE)
        article_section = soup.find(lambda tag: tag.name in ['p', 'div', 'span', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'] and article_regex.match(tag.get_text(strip=True)))
        if article_section:
            log.debug("Found article using regex text match")

    # Strategy 4: Search in eli-subdivision divs (common EUR-Lex structure)
    if not article_section:
        subdivisions = soup.find_all('div', class_=lambda c: c and 'eli-subdivision' in c)
        for subdiv in subdivisions:
            title_elem = subdiv.find(['p', 'span', 'div'], string=lambda s: s and any(_heads_article(s.strip(), p) for p in search_patterns))
            if title_elem:
                article_section = subdiv
                log.debug("Found article in eli-subdivision")
                break

    if not article_section:
        log.warning(f"Article {article} not found in the document after all strategies")
        raise DocumentNotFoundError(
            f"Article {article} not found in EUR-Lex document",
            urn=soup.find('link', rel='canonical')['href'] if soup.find('link', rel='canonical') else None
        )

    log.debug("Article found, extracting text")
    full_text = [article_section.get_text(strip=True)]
    element = article_section.find_next_sibling()

    # Detect end of article by finding next article
    next_article_pattern = re.compile(r'^Articolo\s+\d+|^Article\s+\d+|^Art\.\s+\d+', re.IGNORECASE)

    while element:
        # Check if we've reached the next article
        if element.name == 'p' and 'ti-art' in element.get('class', []):
            log.debug("Next article section found (ti-art class), stopping extraction")
            break
        elem_text = element.get_text(strip=True) if element.name else ''
        if next_article_pattern.match(elem_text):
            log.debug("Next article section found (text pattern), stopping extraction")
            break
        if element.name in ['p', 'div', 'span']:
            text = element.get_text(strip=True)
            if text:
                full_text.append(text)
        elif element.name == 'table':
            full_text.extend(extract_table_text(element))
        element = element.find_next_sibling()

    log.info(f"Article {article} text extracted successfully")
    return "\n".join(full_text)

def extract_table_text(table):
    log.debug("Extracting text from table")
    rows = table.find_all('tr')
    table_text = []

    for row in rows:
        cells = row.find_all('td')
        row_text = ' '.join(cell.get_text(strip=True) for cell in cells)
        table_text.append(row_text)

    log.debug("Table text extracted successfully")
    return table_text

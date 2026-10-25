# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, You can obtain one at
# https://mozilla.org/MPL/2.0/.
#
# Imported from VisuaLex (MPL-2.0), services/visualex/visualex_api/services/eurlex_scraper.py at 02ebc80a
# (the recitals, the consolidated-text reader, ``extract_article_text`` with ``extract_table_text``)
# and services/visualex/visualex_api/tools/treextractor.py at 02ebc80a (``strip_amendment_markers``,
# ``is_quoted_heading`` to ``eurlex_heading_number``, the heading helpers);
# first at 493a8dd1. Generated, not edited: the scratch generator ``gen_eurlex.py`` rebuilds it for a
# re-pin. Adapted: the scraper's two methods are plain functions (no ``self``); structlog is a no-op
# ``log``, so the calls stay as they are; the Playwright fetch and the persistent cache are left out
# (the page comes from CELLAR, ``scraper._fetch_eurlex_html``); ``DocumentNotFoundError`` is a local
# ``LookupError`` with VisuaLex's signature. The code is otherwise VisuaLex's, line for line: the
# article text it returns is frozen (docs/migration/visualex-inventory.md, rows 3.1, 3.3 and 3.4).

"""EUR-Lex article text and recitals, as VisuaLex reads them: the Official Journal page and the
consolidated one.

``extract_article_text(soup, article)`` is the article entry point: a consolidated page
(``title-article-norm`` markup, a sector-0 CELEX) goes through ``extract_article_consolidated``,
any other page through the OJ strategies; it raises ``DocumentNotFoundError`` when the page has
no such article. ``extract_recitals(soup)`` gives every recital as ``{"number", "text"}``. The soup
is VisuaLex's, ``html.parser``.
"""

import copy
import re

from .akn_parser import normalize_article_key
from .article_suffixes import ARTICLE_SUFFIX_ALTERNATION


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
# A marker with the whitespace on both sides. The leading run is matched only from its first
# character (`(?<!\s)`), or a search restarted at every blank of a long run and scanned the
# rest of it each time: 0.85 s on 20,000 blanks. A marker right after an earlier match, whose
# trailing run took the blanks, is the second branch. Same matches as `\s*[►◄▼]…\s*`.
_AMENDMENT_MARK = re.compile(r"(?:(?<!\s)\s++)?[►◄▼](?:[A-Z]\d*)?\s*")


def strip_amendment_markers(text: str) -> str:
    """Drop inline "►M2 … ◄" / "▼M2" markers and collapse the whitespace they leave."""
    return re.sub(r"[ \t\xa0]+", " ", _AMENDMENT_MARK.sub(" ", text or "")).strip()


def is_quoted_heading(element) -> bool:
    """An article heading quoted inside the act's text, not one of its own articles.

    An amending act's OJ page sets the articles it replaces or inserts in another act in a
    table cell, the first of a run opening with «: dir. 2009/136 (six articles) quotes art.
    21, 22, 23, 23 bis and 27 of dir. 2002/22, and they were listed and served as its own.
    The act's own articles never sit in a table cell (checked on every EUR-Lex test page).
    """
    return (element.get_text(strip=True).startswith(("«", "“"))
            or element.find_parent("td") is not None)


# A legacy OJ page can glue an article's heading to the end of the paragraph before it: dir.
# 85/374 reads «… l'interruzione della prescrizione. Articolo 11</p>», so art. 11 was not listed,
# not found, and its text was served at the end of art. 10's.
_GLUED_HEADING = re.compile(r"[.;:]\s+((?:Articolo|Article)\s+(\d+))$")
_HEADING_TAGS = ['p', 'div', 'span', 'h1', 'h2', 'h3', 'h4']


def glued_headings(soup):
    """The article headings glued to the end of a class-less paragraph, as {number: (paragraph,
    where the heading starts in its stripped text)}. Only the article right after the one before
    it, and never one that an element of its own heads: a sentence ending «… Articolo 11» is
    otherwise a reference, not a heading."""
    own = set()
    for elem in soup.find_all(_HEADING_TAGS):
        number = None if is_quoted_heading(elem) else eurlex_heading_number(elem.get_text(strip=True))
        if number:
            own.add(number)
    found, previous = {}, None
    for elem in soup.find_all(_HEADING_TAGS):
        text = elem.get_text(strip=True)
        number = None if is_quoted_heading(elem) else eurlex_heading_number(text)
        if number:
            previous = number
            continue
        match = _GLUED_HEADING.search(text) if elem.name == 'p' and not elem.get('class') else None
        if (match and match.group(2) not in own and previous is not None and previous.isdigit()
                and int(match.group(2)) == int(previous) + 1):
            found[match.group(2)] = (elem, match.start(1))
            previous = match.group(2)
    return found


# An ordinal after a heading's number: a whole word («15 bis», «15 BIS», «15-bis»), or a lower-case
# ordinal glued to the capital that opens the text after it, as a class-less page whose heading and
# text share an element reads «Articolo 15 bisTesto». A capital after a lower-case ordinal never
# starts a word of it; «Articolo 1 Bisogna» and «Articolo 1Terzi» stay art. 1.
HEADING_ORDINAL = (rf"(?:(?:{ARTICLE_SUFFIX_ALTERNATION})(?![^\W\d_])"
                   rf"|(?-i:(?:{ARTICLE_SUFFIX_ALTERNATION})(?=[A-ZÀ-Ý])))")

# An OJ heading's number with its ordinal, read as one article: «Articolo 15 bis» is «15-bis».
_EURLEX_HEADING_NUMBER = re.compile(
    rf"^(?:Articolo|Article)\s+(\d+)(?:[\s\-]*+({HEADING_ORDINAL}))?", re.IGNORECASE)


def eurlex_heading_number(text):
    """The article an OJ heading names («15», «15-bis»), or None when it names none."""
    match = _EURLEX_HEADING_NUMBER.match(text)
    if not match:
        return None
    return f"{match.group(1)}-{match.group(2).lower()}" if match.group(2) else match.group(1)



# --- Recitals -------------------------------------------------------------
#
# Two markups. The modern OJ page (acts published since ~2014) wraps every
# recital in <div class="eli-subdivision" id="rct_N"> holding a two-cell table:
# "(N)" on the left, the text on the right. Older acts are served class-less:
# a run of <p>(N) …</p> between "considerando quanto segue:" and the enacting
# formula ("HA/HANNO ADOTTATO …"). Consolidated texts have no preamble at all.
_RECITAL_DIV_ID = re.compile(r"^rct_(\d+)$")
_RECITAL_NUMBER_ONLY = re.compile(r"^\(\d+\)$")
_LEGACY_RECITAL = re.compile(r"^\((\d+)\)\s+(.*)$", re.S)
_LEGACY_PREAMBLE_MARKER = re.compile(r"considerando quanto segue", re.I)
_LEGACY_ENACTING_FORMULA = re.compile(r"^HA(?:NNO)?\s+ADOTTAT[OA]\b", re.I)


def _strip_footnote_marks(element) -> None:
    """Remove "(18)"-style footnote call-outs in place.

    EUR-Lex renders them as <a>(<span class="oj-note-tag">18</span>)</a>; the
    anchor's whole text is the parenthesised number, so dropping the anchor
    leaves the sentence intact. The soup is built per request from the cached
    HTML, so mutating it here is local to this call.
    """
    for span in element.find_all("span", class_="oj-note-tag"):
        anchor = span.find_parent("a")
        target = anchor if anchor is not None else span
        if _RECITAL_NUMBER_ONLY.match(target.get_text(strip=True) or ""):
            target.decompose()


def _extract_recitals_modern(soup) -> list[dict]:
    recitals = []
    for div in soup.find_all("div", id=_RECITAL_DIV_ID):
        number = _RECITAL_DIV_ID.match(div["id"]).group(1)
        _strip_footnote_marks(div)
        paragraphs = []
        for p in div.find_all("p"):
            text = p.get_text(" ", strip=True)
            if not text or _RECITAL_NUMBER_ONLY.match(text):
                continue  # the "(N)" cell
            paragraphs.append(text)
        if paragraphs:
            recitals.append({"number": number, "text": "\n".join(paragraphs)})
    return recitals


def _extract_recitals_legacy(soup) -> list[dict]:
    marker = soup.find("p", string=_LEGACY_PREAMBLE_MARKER)
    if marker is None:
        return []
    recitals = []
    expected = 1
    for p in marker.find_all_next("p"):
        text = p.get_text(" ", strip=True)
        if _LEGACY_ENACTING_FORMULA.match(text):
            break
        match = _LEGACY_RECITAL.match(text)
        if not match:
            continue
        number, body = match.group(1), match.group(2).strip()
        # Footnote paragraphs also read "(4) …"; a recital number is the next
        # one in the sequence, nothing else.
        if int(number) != expected:
            continue
        recitals.append({"number": number, "text": body})
        expected += 1
    return recitals


def extract_recitals(soup) -> list[dict]:
    """Recitals of an EU act as ``[{"number": "1", "text": "…"}, …]``.

    Modern markup first; the legacy paragraph walk only when the page has no
    ``rct_N`` divs. A consolidated text yields ``[]``: it has no preamble.
    """
    recitals = _extract_recitals_modern(soup)
    if recitals:
        return recitals
    return _extract_recitals_legacy(soup)


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


# Blanks before closing punctuation, matched only from the run's first blank (see
# `_AMENDMENT_MARK` in treextractor): `\s+([.,;:)])` restarted at every blank of a long run.
_SPACE_BEFORE_PUNCTUATION = re.compile(r"(?<!\s)\s++([.,;:)])")


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
    text = _SPACE_BEFORE_PUNCTUATION.sub(r"\1", text)
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


# An ordinal right after a heading's number ("Articolo 15 bis", "Articolo 15bis", and glued to the
# text after it, "Articolo 15 bisTesto"), never the head of a word: "Articolo 1 Terzi" is art. 1
# with its rubrica run on (`HEADING_ORDINAL`).
_ORDINAL_AFTER_NUMBER = re.compile(rf"[\s\-]*+{HEADING_ORDINAL}", re.IGNORECASE)


def _number_ends_here(rest) -> bool:
    """True when the heading's number ends where `rest` starts: no digit and no ordinal follow."""
    return not rest[:1].isdigit() and not _ORDINAL_AFTER_NUMBER.match(rest)


def _heads_article(text, pattern) -> bool:
    """True when `text` opens with the heading `pattern` ("Articolo 1") and the
    number ends there: "Articolo 17" does not head article 1, or a request for a
    missing art. 1 would be served art. 17; nor does "Articolo 15 bis" head
    article 15 (the suffix served must be the one asked, none for none)."""
    return text.startswith(pattern) and _number_ends_here(text[len(pattern):])


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

    # A heading quoted inside the act (an amending act's replaced or inserted articles, in a
    # table cell) is another act's article: no strategy takes it (`is_quoted_heading`).

    # Strategy 1: Look for <p class="ti-art"> (original selector)
    for pattern in search_patterns:
        article_section = soup.find(lambda tag: tag.name == 'p' and 'ti-art' in tag.get('class', []) and _heads_article(tag.get_text(strip=True), pattern) and not is_quoted_heading(tag))
        if article_section:
            log.debug(f"Found article with ti-art class using pattern: {pattern}")
            break

    # Strategy 2: Look for any element with class containing 'art' or 'title'
    if not article_section:
        for pattern in search_patterns:
            article_section = soup.find(lambda tag: tag.get('class') and any('art' in c.lower() or 'title' in c.lower() for c in tag.get('class', [])) and _heads_article(tag.get_text(strip=True), pattern) and not is_quoted_heading(tag))
            if article_section:
                log.debug(f"Found article with art/title class using pattern: {pattern}")
                break

    # Strategy 3: Look for any element whose text matches article pattern exactly. The modern
    # OJ page writes "Articolo\xa0N", which only this one reads; the number must end there,
    # as in `_heads_article`, or art. 15 asked would be served "Articolo 15 bis". An article
    # asked with its suffix («15 bis», «15-bis», «15bis») reads "Articolo\xa015\xa0bis" too.
    if not article_section:
        asked = re.fullmatch(rf'(\d+)[\s\-]*({ARTICLE_SUFFIX_ALTERNATION})?', str(article).strip(), re.IGNORECASE)
        if asked:
            spelled = asked.group(1) + (rf'[\s\-]*{asked.group(2)}' if asked.group(2) else '')
        else:
            spelled = re.escape(str(article))
        article_regex = re.compile(rf'^Articolo\s+{spelled}\b', re.IGNORECASE)

        def heads_by_regex(text):
            match = article_regex.match(text)
            return bool(match) and _number_ends_here(text[match.end():])

        article_section = soup.find(lambda tag: tag.name in ['p', 'div', 'span', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'] and heads_by_regex(tag.get_text(strip=True)) and not is_quoted_heading(tag))
        if article_section:
            log.debug("Found article using regex text match")

    # Strategy 4: Search in eli-subdivision divs (common EUR-Lex structure)
    if not article_section:
        subdivisions = soup.find_all('div', class_=lambda c: c and 'eli-subdivision' in c)
        for subdiv in subdivisions:
            title_elem = subdiv.find(lambda tag: tag.name in ('p', 'span', 'div') and tag.string
                                     and any(_heads_article(tag.string.strip(), p) for p in search_patterns)
                                     and not is_quoted_heading(tag))
            if title_elem:
                article_section = subdiv
                log.debug("Found article in eli-subdivision")
                break

    # Strategy 5: a heading glued to the end of the paragraph before it (`glued_headings`). Only
    # a class-less page has one, so a page whose heading carries a class is not walked for it.
    glued = glued_headings(soup) if article_section is None or not article_section.get('class') else {}
    heading = None
    if not article_section and str(article).strip() in glued:
        article_section, start = glued[str(article).strip()]
        heading = article_section.get_text(strip=True)[start:]
        log.debug("Found article glued to the end of a paragraph")

    if not article_section:
        log.warning(f"Article {article} not found in the document after all strategies")
        raise DocumentNotFoundError(
            f"Article {article} not found in EUR-Lex document",
            urn=soup.find('link', rel='canonical')['href'] if soup.find('link', rel='canonical') else None
        )

    log.debug("Article found, extracting text")
    full_text = [heading or article_section.get_text(strip=True)]
    element = article_section.find_next_sibling()
    glued_at = {id(elem): start for elem, start in glued.values()}

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
        if id(element) in glued_at:
            # The paragraph is this article's, up to the next one's heading glued to its end.
            if elem_text[:glued_at[id(element)]].rstrip():
                full_text.append(elem_text[:glued_at[id(element)]].rstrip())
            log.debug("Next article glued to the end of a paragraph, stopping extraction")
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

# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, You can obtain one at
# https://mozilla.org/MPL/2.0/.
#
# Imported from VisuaLex (MPL-2.0), services/visualex/visualex_api/tools/treextractor.py at d067f710: the
# EUR-Lex half (``_parse_eurlex_tree`` to ``_sort_eurlex_results``); first at 36ed6942. Generated,
# not edited (scratch ``gen_eurlex.py``). Adapted: ``_parse_eurlex_tree`` awaited nothing and is a
# plain function; the records go to the standard ``logging`` module, configured by the caller
# (VisuaLex's ``basicConfig`` with a file handler is dropped); ``strip_amendment_markers`` and the
# heading helpers (``is_quoted_heading`` to ``eurlex_heading_number``) are ``eurlex_text``'s. No
# change of behaviour: the
# two this package carried until 36ed6942 (an OJ article keeps its ordinal; a heading an amending act
# quotes is not one of its articles) are VisuaLex's own since its PR #312.

"""The article tree, the rubriche and the title of an EU act, from its EUR-Lex page (OJ or consolidated)."""

import logging
import re

from .akn_parser import normalize_article_key
from .eurlex_text import _HEADING_TAGS, eurlex_heading_number, glued_headings, is_quoted_heading, strip_amendment_markers


def _parse_eurlex_tree(soup, normurn, link=False, details=False):
    """
    Parsa la struttura dell'albero degli articoli per Eur-Lex.

    Args:
        soup: BeautifulSoup object del documento
        normurn (str): URL base del documento EUR-Lex
        link (bool): Se includere i link agli articoli
        details (bool): Se includere i titoli di Capi/Sezioni/Titoli

    Returns:
        tuple: Lista di articoli estratti e conteggio
    """
    logging.info("Parsing Eur-Lex structure")
    result = []
    seen_articles = set()
    seen_sections = set()
    count_articles = 0

    # Estrai anno e numero dall'URL per generare link ELI
    eli_info = _extract_eli_info(normurn)

    if soup.find("p", class_="title-article-norm"):
        result, count_articles = _walk_consolidated_tree(soup, normurn, link, details, eli_info)
        rubriche = _extract_eurlex_rubriche(soup)
        logging.info(f"Consolidated EUR-Lex tree: {count_articles} articles, {len(rubriche)} rubriche")
        return result, count_articles, {"rubriche": rubriche, "title": _extract_eurlex_title(soup)}

    # Pattern per identificare strutture gerarchiche
    title_pattern = re.compile(r'^(TITOLO|TITLE)\s+([IVXLCDM]+|\d+)', re.IGNORECASE)
    chapter_pattern = re.compile(r'^(CAPO|CHAPTER)\s+([IVXLCDM]+|\d+)', re.IGNORECASE)
    section_pattern = re.compile(r'^(SEZIONE|SECTION)\s+(\d+|\w+)', re.IGNORECASE)

    # Strategia principale: cerca elementi ti-section (sezioni) e ti-art (articoli) in ordine di documento
    # Questo preserva l'ordine gerarchico: CAPO -> Sezione -> Articolo

    # Trova tutti gli elementi strutturali in ordine
    structure_elements = soup.find_all(['p', 'div', 'span'], class_=lambda c: c and any(x in str(c).lower() for x in ['ti-section', 'ti-art']))

    if structure_elements:
        logging.info(f"Found {len(structure_elements)} structure elements (ti-section/ti-art)")

        for elem in structure_elements:
            text = elem.get_text(strip=True)
            class_str = ' '.join(elem.get('class', []))

            # Verifica se è un header di sezione (CAPO, Sezione, TITOLO)
            if 'ti-section' in class_str.lower():
                # Estrai solo il titolo della sezione (CAPO I, Sezione 1, etc.)
                section_match = (title_pattern.match(text) or
                               chapter_pattern.match(text) or
                               section_pattern.match(text))
                if section_match and details:
                    section_title = section_match.group(0)
                    if section_title not in seen_sections:
                        seen_sections.add(section_title)
                        result.append(section_title)
                        logging.debug(f"Found section: {section_title}")

            # Verifica se è un articolo
            elif 'ti-art' in class_str.lower():
                article_num = None if is_quoted_heading(elem) else eurlex_heading_number(text)
                if article_num:
                    if article_num not in seen_articles:
                        seen_articles.add(article_num)
                        article_data = _format_eurlex_article(article_num, normurn, eli_info, link)
                        result.append(article_data)
                        count_articles += 1

    # Fallback: cerca nel documento con pattern matching se non trovato nulla
    if count_articles == 0:
        logging.info("ti-section/ti-art not found, falling back to pattern search")

        glued = {id(elem): number for number, (elem, _) in glued_headings(soup).items()}
        # Cerca tutti gli elementi che potrebbero contenere articoli o sezioni
        for elem in soup.find_all(_HEADING_TAGS):
            text = elem.get_text(strip=True)

            # Check for sections first (when details=True)
            if details:
                section_match = (title_pattern.match(text) or
                               chapter_pattern.match(text) or
                               section_pattern.match(text))
                if section_match:
                    section_title = section_match.group(0)
                    if section_title not in seen_sections:
                        seen_sections.add(section_title)
                        result.append(section_title)
                    continue

            # Check for articles
            article_num = None if is_quoted_heading(elem) else eurlex_heading_number(text)
            article_num = article_num or glued.get(id(elem))
            if article_num:
                if article_num not in seen_articles:
                    seen_articles.add(article_num)
                    article_data = _format_eurlex_article(article_num, normurn, eli_info, link)
                    result.append(article_data)
                    count_articles += 1

    logging.info(f"Extracted {count_articles} unique articles and {len(seen_sections)} sections from Eur-Lex")
    # Article titles come free with this page: EUR-Lex marks the number with
    # `oj-ti-art` ("Articolo 1") and the title with `oj-sti-art` ("Oggetto e
    # finalità") right after it. Unlike Normattiva — whose tree carries bare
    # numbers and whose titles live in a separate 10 MB export — here the whole
    # index can be labelled without a single extra request, so it is built
    # during the same parse rather than behind another fetch.
    rubriche = _extract_eurlex_rubriche(soup)
    logging.info(f"EUR-Lex rubriche extracted: {len(rubriche)} of {count_articles} articles")

    return result, count_articles, {"rubriche": rubriche, "title": _extract_eurlex_title(soup)}


_EURLEX_ARTICLE_NUM = re.compile(r"^(?:Articolo|Article)\s+([\w.-]+)", re.IGNORECASE)




def _next_non_modref_sibling(element):
    """The next sibling that is not a `modref` marker.

    EUR-Lex drops a "▼M2" / "▼B" paragraph before every block an amendment
    touched, so the element that logically follows a title — its rubrica,
    or the heading text after a heading number — may sit one marker away.
    """
    sibling = element.find_next_sibling()
    while sibling is not None and "modref" in (sibling.get("class", []) or []):
        sibling = sibling.find_next_sibling()
    return sibling


def _cons_rubrica_of(marker):
    """The rubrica element that follows a consolidated article marker.

    Bare `stitle-article-norm` (flat pages) or inside `div.eli-title`
    (subdivision pages); a `modref` marker may sit in between.
    """
    sibling = _next_non_modref_sibling(marker)
    if sibling is None:
        return None
    classes = sibling.get("class", []) or []
    if "stitle-article-norm" in classes:
        return sibling
    if "eli-title" in classes:
        return sibling.find("p", class_="stitle-article-norm")
    return None


def _extract_consolidated_rubriche(soup):
    rubriche = {}
    for marker in soup.find_all("p", class_="title-article-norm"):
        key = normalize_article_key(marker.get_text(" ", strip=True))
        if not key:
            continue
        rubrica = _cons_rubrica_of(marker)
        if rubrica is None:
            continue
        title = strip_amendment_markers(rubrica.get_text(" ", strip=True))
        if title:
            rubriche[key] = title
    return rubriche


def _walk_consolidated_tree(soup, normurn, link, details, eli_info):
    """Articles and (with details) chapter headings of a consolidated page.

    `title-division-1` is the heading number ("CAPO I", "SEZIONE 1") and the
    `title-division-2` right after it the heading text; both are kept so the
    index reads "CAPO I DISPOSIZIONI GENERALI". Article numbers are
    canonicalised through the shared suffix table: "Articolo 14 bis" is
    14-bis, not a second 14.
    """
    result = []
    seen = set()
    count = 0
    for elem in soup.find_all("p", class_=["title-division-1", "title-article-norm"]):
        classes = elem.get("class", []) or []
        if "title-division-1" in classes:
            if not details:
                continue
            heading = elem.get_text(" ", strip=True)
            nxt = _next_non_modref_sibling(elem)
            if nxt is not None and "title-division-2" in (nxt.get("class", []) or []):
                heading = f"{heading} {nxt.get_text(' ', strip=True)}"
            result.append(strip_amendment_markers(heading))
            continue
        key = normalize_article_key(elem.get_text(" ", strip=True))
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(_format_eurlex_article(key, normurn, eli_info, link))
        count += 1
    return result, count


def _extract_eurlex_rubriche(soup):
    """Article number -> title, from an EUR-Lex document.

    The title is the `oj-sti-art` sibling that follows each `oj-ti-art`. Some
    documents label it `eli-title` instead, so both are accepted; an article
    with neither is simply absent from the map.
    """
    if soup.find("p", class_="title-article-norm"):
        return _extract_consolidated_rubriche(soup)
    rubriche = {}
    for marker in soup.find_all(class_=lambda c: c and "ti-art" in str(c).lower()
                                and "sti-art" not in str(c).lower()):
        if is_quoted_heading(marker):
            continue
        heading = marker.get_text(" ", strip=True)
        number = eurlex_heading_number(heading)
        if not number:
            # A heading with no number in figures («Articolo unico») keeps its own word.
            match = _EURLEX_ARTICLE_NUM.match(heading)
            if not match:
                continue
            number = match.group(1)
        sibling = marker.find_next_sibling()
        if sibling is None:
            continue
        classes = " ".join(sibling.get("class", []) or []).lower()
        if "sti-art" not in classes and "eli-title" not in classes:
            continue
        title = sibling.get_text(" ", strip=True)
        if title:
            rubriche[number] = title
    return rubriche


# "del 27 aprile 2016", "dell'8 giugno 2000": the line between an act's name and its subject.
# A digit after it: «DEL PARLAMENTO EUROPEO…», an act's name split over two lines, is no date.
_EURLEX_DATE_LINE = re.compile(r"^dell?['’\s]\s*\d", re.IGNORECASE)
# The legacy page's description: "Direttiva 2002/58/CE del Parlamento europeo e del Consiglio, del 12 luglio 2002, relativa al …";
# an older act's has no commas round the date ("Direttiva 85/374/CEE del Consiglio del 25 luglio 1985 relativa al …").
# The blanks before "del" are matched only from a run's first one (`(?<!\s)`), or a search restarted
# at every blank of a long run and scanned the rest of it each time: 0.75 s on 20,000 blanks. Same
# matches as `(?:,\s*|\s+)del…`.
_EURLEX_DESCRIPTION_SUBJECT = re.compile(
    r"(?:,|(?<!\s)\s)\s*dell?['’\s]\s*\d{1,2}[°º]?\s+\S+\s+\d{4}\s*,?\s*(.+)$", re.IGNORECASE | re.DOTALL)


def _eurlex_subject(lines):
    """The subject among a title's lines: what follows the date, without a note in brackets
    such as "(Testo rilevante ai fini del SEE)"."""
    lines = [strip_amendment_markers(line) for line in lines if line]
    for i, line in enumerate(lines):
        if _EURLEX_DATE_LINE.match(line):
            lines = lines[i + 1:]
            break
    return " ".join(line for line in lines if not (line.startswith("(") and line.endswith(")")))


def _extract_eurlex_title(soup):
    """The act's title as Normattiva's `presentable_title` gives one: its subject ("relativo alla
    protezione delle persone fisiche …"), without the act's name, its date or the EEA note, which
    the dossier already shows in the act's heading. '' when the page does not say.

    The OJ page names the act in `oj-doc-ti` lines inside `eli-main-title` (an annex's heading uses
    the same class, so only the first consecutive run counts, and only when it holds the date); the
    consolidated page in `title-doc-first` and
    `title-doc-last` (printed twice, the first copy is enough; the subject in `title-doc-first`
    when `title-doc-last` holds only the EEA note); the legacy page in its
    `DC.description` meta, which the `/eli/` address of a legacy act does not carry (dir.
    2002/58): there the ELI metadata names the act in every language, and the Italian
    `eli:title` is read the same way. Never a title from another language.
    """
    container = soup.find(class_="eli-main-title")
    first = (container or soup).find("p", class_="oj-doc-ti")
    if first is not None:
        run = [first]
        for sibling in first.find_next_siblings():
            if sibling.name != "p" or "oj-doc-ti" not in (sibling.get("class") or []):
                break
            run.append(sibling)
        lines = [p.get_text(" ", strip=True) for p in run]
        # The subject is what follows the date: without one (a Treaty's page), no title rather
        # than the act's own name repeated under its heading.
        if not any(_EURLEX_DATE_LINE.match(line) for line in lines):
            return ""
        return _eurlex_subject(lines)
    last = soup.find("p", class_="title-doc-last")
    if last is not None:
        subject = _eurlex_subject([last.get_text(" ", strip=True)])
        if subject:
            return subject
        # The consolidated GDPR (02016R0679-20160504) has only the EEA note there: its subject is
        # in the `title-doc-first` run, after the date line, as on the OJ page.
        first = soup.find("p", class_="title-doc-first")
        run = [first] if first is not None else []
        for sibling in first.find_next_siblings() if first is not None else []:
            if sibling.name != "p" or "title-doc-first" not in (sibling.get("class") or []):
                break
            run.append(sibling)
        lines = [p.get_text(" ", strip=True) for p in run]
        return _eurlex_subject(lines) if any(_EURLEX_DATE_LINE.match(line) for line in lines) else ""
    # The Italian expression of the act: `about` names it (…/oj/ita), the language tag alone
    # could also sit on another resource's meta.
    eli_title = soup.find("meta", attrs={"property": "eli:title", "lang": "it",
                                         "about": lambda about: bool(about) and about.rstrip("/").endswith("/ita")})
    for meta in (soup.find("meta", attrs={"name": "DC.description"}), eli_title):
        match = _EURLEX_DESCRIPTION_SUBJECT.search((meta.get("content") or "") if meta else "")
        subject = " ".join(match.group(1).split()) if match else ""
        # A note in brackets after the date («(GU L 210 …)») is no subject, as in `_eurlex_subject`.
        if subject and not (subject.startswith("(") and subject.endswith(")")):
            return subject
    return ""


def _extract_eli_info(normurn):
    """
    Estrae informazioni ELI dall'URL per generare link agli articoli.

    Args:
        normurn (str): URL EUR-Lex

    Returns:
        dict: Dizionario con tipo, anno, numero dell'atto
    """
    eli_info = {'type': None, 'year': None, 'num': None, 'base_url': normurn}

    # Pattern ELI: /eli/reg/2016/679/oj o /eli/dir/2019/790/oj
    eli_match = re.search(r'/eli/(reg|dir)/(\d{4})/(\d+)', normurn)
    if eli_match:
        eli_info['type'] = eli_match.group(1)
        eli_info['year'] = eli_match.group(2)
        eli_info['num'] = eli_match.group(3)
        return eli_info

    # Pattern CELEX: CELEX:32016R0679 o CELEX:32019L0790
    celex_match = re.search(r'CELEX:3(\d{4})([RL])(\d+)', normurn)
    if celex_match:
        eli_info['year'] = celex_match.group(1)
        eli_info['type'] = 'reg' if celex_match.group(2) == 'R' else 'dir'
        eli_info['num'] = str(int(celex_match.group(3)))  # Rimuovi zeri iniziali
        return eli_info

    return eli_info


def _format_eurlex_article(article_num, normurn, eli_info, link):
    """
    Formatta i dati dell'articolo con o senza link.

    Args:
        article_num (str): Numero dell'articolo
        normurn (str): URL base
        eli_info (dict): Info ELI estratte
        link (bool): Se includere il link

    Returns:
        str or dict: Numero articolo o dizionario {numero: url}
    """
    article_data = {
        "numero": article_num
    }

    if link:
        # Genera URL ELI per l'articolo specifico
        if eli_info['type'] and eli_info['year'] and eli_info['num']:
            article_url = f"https://eur-lex.europa.eu/eli/{eli_info['type']}/{eli_info['year']}/{eli_info['num']}/art_{article_num}/oj"
        else:
            # Fallback: usa URL base con ancora
            article_url = f"{normurn}#art_{article_num}"
        article_data["url"] = article_url

    return article_data


def _sort_eurlex_results(results, link):
    """
    Ordina i risultati per numero articolo.

    Args:
        results (list): Lista di articoli
        link (bool): Se i risultati contengono link

    Returns:
        list: Lista ordinata
    """
    def get_sort_key(item):
        if isinstance(item, dict):
            key = list(item.keys())[0]
        else:
            key = item
        # Estrai numero per ordinamento
        match = re.match(r'(\d+)', str(key))
        return int(match.group(1)) if match else 0

    try:
        return sorted(results, key=get_sort_key)
    except Exception:
        return results

# Funzione principale per test

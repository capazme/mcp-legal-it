# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, You can obtain one at
# https://mozilla.org/MPL/2.0/.
#
# Imported from VisuaLex (MPL-2.0), services/visualex/visualex_api/tools/treextractor.py at eca698dc.
# Adapted: only the Normattiva half (``_narrow``, ``_parse_normattiva_tree``,
# ``_extract_normattiva_article``, ``_generate_article_url``), unchanged but for
# ``_parse_normattiva_tree``, which awaited nothing and is a plain function here, and the
# module's logging set-up (VisuaLex's ``basicConfig`` with a file handler), which is
# dropped: the records go to the standard ``logging`` module, configured by the caller. The EUR-Lex half and the Playwright fetch stay
# in VisuaLex. ``articolo_nell_albero`` and ``dove_altrove`` are VisuaLex's
# ``NormaController._article_exists_in_tree`` / ``_where_else_in_tree``
# (services/visualex/app.py at eca698dc) rewritten as pure functions over a tree.

"""Normattiva's article tree (the ``albero`` of an act's page), as VisuaLex reads it.

The tree lists every article of the act with the part it belongs to, numbered as
Normattiva numbers its parts: ``allegato`` is ``None`` for the act's own text and
``"1"``, ``"2"``… for the parts after it, the ``:k`` of the URN (the codice civile is
``"2"``, its preleggi ``"1"``). It carries no rubriche: those come from the Akoma
Ntoso export (``akn_parser``).
"""

import logging
import re

from .akn_parser import normalize_article_key

def _narrow(result, count, metadata, details, return_metadata):
    """A Normattiva tree as `get_tree(details, return_metadata)` answers it, from the widest
    one (`details=True, return_metadata=True`) of the same page and `link`. The parser builds
    the same article entries and the same metadata whatever `details` and `return_metadata`
    say; `details` only adds the section labels (bare strings) between them, so dropping the
    strings is the narrower parse (tests/test_tree_variants.py)."""
    if not details and isinstance(result, list):
        result = [entry for entry in result if isinstance(entry, dict)]
    if return_metadata:
        return result, count, metadata
    return result, count


def _parse_normattiva_tree(soup, normurn, link, details, return_metadata=False):
    """
    Parsa la struttura dell'albero degli articoli per Normattiva.

    La struttura di Normattiva per i codici (es. Codice Civile RD 262/1942) è:
    - box_articoli "Articoli" → inizio corpo dell'atto (legge di emanazione)
    - box_articoli "Allegati" → marker che indica inizio sezione allegati
    - box_allegati "Disposizioni sulla legge in generale" → Allegato 1 (Preleggi)
    - box_allegati_small "CODICE CIVILE" → Allegato 2 (Codice Civile vero e proprio)

    URN Normattiva usa :1, :2 per gli allegati:
    - urn:...;262~art2 → art. 2 del corpo dell'atto
    - urn:...;262:1~art2 → art. 2 del primo allegato
    - urn:...;262:2~art7 → art. 7 del secondo allegato
    """
    logging.info("Parsing Normattiva structure (flat stateful iteration)")
    tree_div = soup.find('div', id='albero')

    if not tree_div:
        logging.warning("Div with id 'albero' not found")
        if return_metadata:
            return "Div with id 'albero' not found", 0, {}
        return "Div with id 'albero' not found", 0

    result = []
    count_articles = 0
    annexes_metadata = {}
    annex_labels = {}  # Map annex number -> original label text
    current_attachment = None
    annex_counter = 0
    in_allegati_section = False  # True after we see box_articoli "Allegati"

    # Initialize main text (dispositivo) tracking - will be populated before annexes
    annexes_metadata[None] = {'articles': [], 'count': 0}
    annex_labels[None] = "Dispositivo"

    # Iteriamo su tutti gli elementi <li> nell'ordine in cui appaiono nel DOM
    for li in tree_div.find_all('li'):
        classes = li.get('class', [])

        # 0. Verifica se è un box_articoli (marker di sezione "Articoli" o "Allegati")
        if 'box_articoli' in classes:
            box_text = li.get_text(strip=True).lower()
            if 'allegat' in box_text:  # "Allegati" o simili
                in_allegati_section = True
                logging.info("Entered 'Allegati' section - subsequent box_allegati/box_allegati_small will create annexes")
            continue

        # 1. Verifica se è un'intestazione di allegato esplicita
        # Structure 1: <a class="link_allegato">
        allegato_tag = li.find('a', class_='link_allegato')
        if allegato_tag and allegato_tag.find_parent('li') == li:
            allegato_text = allegato_tag.get_text(strip=True)
            # Preserve the original label text
            original_label = allegato_text

            match = re.search(r'Allegato\s+(\d+)', allegato_text, re.IGNORECASE)
            if match:
                current_attachment = match.group(1)
                annex_counter = max(annex_counter, int(current_attachment))
            else:
                match = re.search(r'Allegato\s+([A-Z])', allegato_text, re.IGNORECASE)
                if match:
                    annex_counter += 1 # We use a numeric counter internally to sync with Normattiva URNs
                    current_attachment = str(annex_counter)
                else:
                    annex_counter += 1
                    current_attachment = str(annex_counter)

            logging.info(f"Detected link_allegato: {current_attachment} (label: {original_label})")
            if current_attachment not in annexes_metadata:
                annexes_metadata[current_attachment] = {'articles': [], 'count': 0}
                annex_labels[current_attachment] = original_label

            if details:
                result.append(allegato_tag.get_text(separator=" ", strip=True))
            continue

        # 2. Verifica se è un box_allegati (es. "Disposizioni sulla legge in generale")
        # Questo crea un NUOVO allegato solo se siamo nella sezione "Allegati"
        if 'box_allegati' in classes and 'box_allegati_small' not in classes:
            span_tag = li.find('span')
            if span_tag and span_tag.find_parent('li') == li:
                original_label = span_tag.get_text(separator=" ", strip=True)

                if in_allegati_section:
                    # Crea nuovo allegato
                    annex_counter += 1
                    current_attachment = str(annex_counter)
                    annexes_metadata[current_attachment] = {'articles': [], 'count': 0}
                    annex_labels[current_attachment] = original_label
                    logging.info(f"Detected box_allegati -> new Allegato {current_attachment}: {original_label}")
                else:
                    logging.info(f"Detected box_allegati (before Allegati section, ignoring): {original_label}")

                if details:
                    result.append(original_label)
                continue

        # 2b. Verifica se è un box_allegati_small (es. "CODICE CIVILE", "Codice Penale")
        # Questo crea SEMPRE un nuovo allegato (indica contenuto principale di un codice)
        if 'box_allegati_small' in classes:
            box_text = li.get_text(strip=True)
            original_label = box_text

            # Crea nuovo allegato
            annex_counter += 1
            current_attachment = str(annex_counter)
            annexes_metadata[current_attachment] = {'articles': [], 'count': 0}
            annex_labels[current_attachment] = original_label
            logging.info(f"Detected box_allegati_small -> new Allegato {current_attachment}: {original_label}")

            if details:
                result.append(original_label)
            continue

        # 3. Verifica se è un'intestazione di sezione
        if 'singolo_risultato_collapse' in li.get('class', []):
            if details:
                section_text = li.get_text(separator=" ", strip=True)
                result.append(section_text)
            continue

        # 4. Processa l'articolo
        a_tag = li.find('a', class_='numero_articolo')
        if a_tag and a_tag.find_parent('li') == li:
            text_content = a_tag.get_text(separator=" ", strip=True)
            # Rimuove "art. ", spazi e punti finali
            article_num = re.sub(r'^\s*art\.\s*', '', text_content, flags=re.IGNORECASE).strip().rstrip('.')

            # Skip invalid article numbers (e.g., "orig", empty strings, non-article text)
            if not article_num or not re.match(r'^[\dIVXLCDM]', article_num, re.IGNORECASE):
                logging.debug(f"Skipping invalid article number: '{article_num}'")
                continue

            article_data = _extract_normattiva_article(a_tag, normurn, link, attachment_number=current_attachment)
            if article_data:
                article_data["numero"] = article_num # Sync cleaned number
                result.append(article_data)
                count_articles += 1

                # Track in metadata
                if return_metadata:
                    key = current_attachment
                    if key not in annexes_metadata:
                        annexes_metadata[key] = {'articles': [], 'count': 0}
                    annexes_metadata[key]['count'] += 1
                    # Store all article numbers for navigation (was limited to 50)
                    annexes_metadata[key]['articles'].append(article_num)

    # Build structured metadata response
    metadata = {}
    if return_metadata and annexes_metadata:
        metadata['annexes'] = []
        # Sort: None (main text) first, then numeric annexes
        sorted_keys = sorted(annexes_metadata.keys(), key=lambda x: (x is not None, int(x) if (x and str(x).isdigit()) else 999))
        for annex_num in sorted_keys:
            data = annexes_metadata[annex_num]
            # Only include if there are articles or it's the main text
            if data['count'] == 0 and annex_num is not None:
                continue
            # Use preserved label or fallback
            label = annex_labels.get(annex_num, f"Allegato {annex_num}" if annex_num is not None else "Dispositivo")
            metadata['annexes'].append({
                'number': annex_num,
                'label': label,
                'article_count': data['count'],
                'article_numbers': data['articles']
            })

    if return_metadata:
        return result, count_articles, metadata
    return result, count_articles


def _extract_normattiva_article(a_tag, normurn, link, attachment_number=None):
    """
    Estrae i dettagli di un articolo da Normattiva, includendo il link se richiesto.

    Args:
        a_tag (bs4.element.Tag): Il tag <a> contenente il numero dell'articolo.
        normurn (str): URN base della norma.
        link (bool): Se includere il link all'articolo.
        attachment_number (int, optional): Numero dell'allegato se l'articolo appartiene a un allegato.

    Returns:
        dict or str: Dizionario con il numero dell'articolo e il link, oppure solo il numero dell'articolo.
    """
    # Rimuove eventuali prefissi come "art. " e spazi
    text_content = a_tag.get_text(separator=" ", strip=True)
    text_content = re.sub(r'^\s*art\.\s*', '', text_content, flags=re.IGNORECASE)

    article_data = {
        "numero": text_content,
        "allegato": attachment_number
    }

    if link:
        # Estrai eventuali estensioni dall'articolo
        match = re.match(r'^(\d+)([a-zA-Z.]*)$', text_content)
        if match:
            article_number = match.group(1)
            extension = match.group(2).replace('-', '').lower()  # Rimuovi trattini e abbassa il caso
            if extension:
                article_number += extension
        else:
            article_number = text_content  # In caso di formato inatteso

        modified_url = _generate_article_url(normurn, article_number, attachment_number=attachment_number)
        article_data["url"] = modified_url

    return article_data


def _generate_article_url(normurn, article_number, attachment_number=None):
    """
    Genera un URL per un articolo specifico basato sull'URN base, sul numero dell'articolo
    e, se presente, sul numero dell'allegato.

    Args:
        normurn (str): URN base della norma.
        article_number (str): Numero dell'articolo, possibili estensioni incluse (es. '27bis').
        attachment_number (int, optional): Numero dell'allegato se l'articolo appartiene a un allegato.

    Returns:
        str: URL completo per l'articolo specifico.
    """
    logging.info(f"Generating article URL for article_number: {article_number}, attachment_number: {attachment_number} based on normurn: {normurn}")

    # Normalize article_number: rimuovi spazi e trattini, converti in minuscolo.
    # "270 bis.1" -> art270bis.1, "19-bis.1" -> art19bis.1, "314/2" -> art314/2,
    # "135 sex decies" -> art135sexdecies. A bare digit after an ordinal is a
    # dotted sub-number in Normattiva's URN grammar: "171 octies 1" (l.
    # 633/1941) is ~art171octies.1 — ~art171octies1, which this used to build,
    # makes Normattiva answer Art. 1 (gotcha 24). Same rule as
    # text_op._canonicalise_article_token.
    article_number = article_number.lower()
    article_number = re.sub(r'(?<=[a-z])[\s-]+(?=\d+$)', '.', article_number)
    article_number = article_number.replace(' ', '').replace('-', '')

    # Regex per identificare i suffissi di versione e di articolo
    split_pattern = re.compile(r'([~@!])')

    parts = split_pattern.split(normurn, maxsplit=1)

    if len(parts) == 1:
        # Nessun suffisso presente, costruisci l'URN base
        base_urn = normurn
        suffix = ''
    else:
        # Suffisso presente, separa base e suffisso
        base_urn, sep, suffix = parts

    # Aggiungi il numero dell'allegato se fornito
    if attachment_number is not None:
        base_urn = f"{base_urn}:{attachment_number}"
        logging.info(f"Added attachment number to URN: {base_urn}")

    # Costruisci il nuovo URN con l'articolo
    new_urn = f"{base_urn}~art{article_number}{sep}{suffix}" if suffix else f"{base_urn}~art{article_number}"

    logging.info(f"Generated article URL: {new_urn}")
    return new_urn


# ---------------------------------------------------------------------------
# Is the article in the tree? Where else is it? (VisuaLex's controller, as functions)
# ---------------------------------------------------------------------------

def articolo_nell_albero(articoli, articolo: str, allegato=None) -> "bool | None":
    """Whether *articolo* is in the tree, in part *allegato* when given (``""`` is the act's own text).

    ``None`` when the tree cannot tell (a failure message, an empty tree): an outage
    is never "the article does not exist". Article numbers are compared through
    ``normalize_article_key`` on both sides ("1-bis" and "1 bis" are one article).
    """
    if isinstance(articoli, str) or not articoli:
        return None
    wanted = normalize_article_key(articolo)
    for entry in articoli:
        if not isinstance(entry, dict):
            continue  # section/annex labels are bare strings
        if allegato is not None and str(entry.get("allegato") or "") != str(allegato):
            continue
        if normalize_article_key(entry.get("numero", "")) == wanted:
            return True
    return False


def dove_altrove(articoli, articolo: str, allegato) -> str:
    """Where else in the act *articolo* is, as a sentence to append to a refusal, or ``""``.

    *allegato* is the part the caller looked in (``""`` for the act's own text); with
    ``None`` (no part named) the answer is ``""``.

    Normattiva numbers an act's annexes by position, not by the act's own wording (the
    c.p.a. is "Allegato 1" of d.lgs. 104/2010 and annex 2 on Normattiva), so a lawyer can
    name the annex the text names and miss: the refusal says where the article is.
    """
    if isinstance(articoli, str) or not articoli or allegato is None:
        # No part named: there is no "elsewhere" (VisuaLex gives the hint only for a part
        # the caller asked for, and str(None) would exclude nothing).
        return ""
    wanted = normalize_article_key(articolo)
    parts: list[str] = []
    for entry in articoli:
        if not isinstance(entry, dict) or normalize_article_key(entry.get("numero", "")) != wanted:
            continue
        part = str(entry.get("allegato") or "")
        if part != str(allegato) and part not in parts:
            parts.append(part)
    if not parts:
        return ""
    annexes = [p for p in parts if p]
    places = []
    if "" in parts:
        places.append("nel testo dell'atto")
    if annexes:
        places.append(("nell'allegato " if len(annexes) == 1 else "negli allegati ") + ", ".join(annexes))
    return f": su Normattiva l'art. {articolo} si trova {' e '.join(places)}"

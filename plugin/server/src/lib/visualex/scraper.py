"""Unified scraper for Normattiva, EUR-Lex, and Brocardi using httpx."""

import asyncio
import re
import warnings
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup, NavigableString, Tag, XMLParsedAsHTMLWarning

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

from .models import NormaVisitata
from .map import find_brocardi_url

# In-memory cache for Brocardi article URLs (base_url + article_num → article_url)
_brocardi_url_cache: dict[str, str] = {}

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def fetch_article(nv: NormaVisitata) -> dict:
    """Fetch article text from Normattiva or EUR-Lex.

    Returns: {"text": str, "url": str, "source": "normattiva"|"eurlex"}
    """
    is_eurlex = nv.norma._is_eurlex()
    source = "eurlex" if is_eurlex else "normattiva"

    if is_eurlex:
        html, url = await _fetch_eurlex_html(nv.norma)
        if not html:
            return {"text": "", "url": url, "source": source, "error": "Could not fetch EUR-Lex document"}
        text = _extract_eurlex_article(html, nv.numero_articolo)
    else:
        url = nv.url()
        if not url:
            return {"text": "", "url": "", "source": "", "error": "Could not generate URL for this act"}
        async with httpx.AsyncClient(headers=_HEADERS, timeout=_TIMEOUT, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            html = resp.text
        text = _extract_normattiva_article(html)

    return {"text": text, "url": url, "source": source}


async def fetch_annotations(nv: NormaVisitata) -> dict:
    """Fetch Brocardi annotations (ratio legis, spiegazione, massime).

    Returns: {"annotations": dict, "url": str, "source": "brocardi"}
    """
    brocardi_url = find_brocardi_url(nv.norma.tipo_atto_normalized, nv.norma.numero_atto)
    if not brocardi_url:
        return {"annotations": {}, "url": "", "source": "brocardi",
                "error": f"No Brocardi mapping for '{nv.norma.tipo_atto_normalized}'"}

    article_num = nv.numero_articolo.replace("-", "") if nv.numero_articolo else ""
    if not article_num:
        return {"annotations": {}, "url": brocardi_url, "source": "brocardi",
                "error": "Article number required for Brocardi annotations"}

    async with httpx.AsyncClient(headers=_HEADERS, timeout=_TIMEOUT, follow_redirects=True) as client:
        # Step 1: fetch main page and find article link
        article_url = await _find_brocardi_article_url(client, brocardi_url, article_num)
        if not article_url:
            return {"annotations": {}, "url": brocardi_url, "source": "brocardi",
                    "error": f"Article {nv.numero_articolo} not found on Brocardi"}

        # Step 2: fetch article page and extract sections
        resp = await client.get(article_url)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

    annotations = _extract_brocardi_sections(soup)
    return {"annotations": annotations, "url": article_url, "source": "brocardi"}


# ---------------------------------------------------------------------------
# Normattiva extraction (4 scenarios from original)
# ---------------------------------------------------------------------------

def _extract_normattiva_article(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    corpo = soup.find("div", class_="bodyTesto")
    if corpo is None:
        return soup.get_text(separator="\n", strip=True)

    # Scenario 1: AKN Detailed (art-comma-div-akn)
    if corpo.find(class_="art-comma-div-akn"):
        return _normattiva_akn_detailed(corpo)

    # Scenario 2: AKN Simple (art-just-text-akn)
    if corpo.find(class_="art-just-text-akn"):
        return _normattiva_akn_simple(corpo)

    # Scenario 3: Attachment (attachment-just-text)
    if corpo.find(class_="attachment-just-text"):
        return _normattiva_attachment(corpo)

    # Scenario 4: Fallback
    return _normattiva_fallback(corpo)


def _normattiva_akn_detailed(corpo: Tag) -> str:
    article_num_tag = corpo.find("h2", class_="article-num-akn")
    article_title_tag = corpo.find("div", class_="article-heading-akn")
    article_num = article_num_tag.get_text(strip=True) if article_num_tag else ""
    article_title = article_title_tag.get_text(strip=True) if article_title_tag else ""

    text = f"{article_num}\n{article_title}\n\n"
    for comma_div in corpo.find_all("div", class_="art-comma-div-akn"):
        comma_text = _extract_text_recursive(comma_div)
        text += comma_text.strip() + "\n\n"

    return _clean_normattiva_text(text)


def _normattiva_akn_simple(corpo: Tag) -> str:
    article_num_tag = corpo.find("h2", class_="article-num-akn")
    article_title_tag = corpo.find("div", class_="article-heading-akn")
    article_num = article_num_tag.get_text(strip=True) if article_num_tag else ""
    article_title = article_title_tag.get_text(strip=True) if article_title_tag else ""

    text = f"{article_num}\n{article_title}\n\n"
    just_text = corpo.find("span", class_="art-just-text-akn")
    if just_text:
        text += _extract_text_recursive(just_text).strip()

    return _clean_normattiva_text(text)


def _normattiva_attachment(corpo: Tag) -> str:
    text = ""
    attachment = corpo.find("span", class_="attachment-just-text")
    if attachment:
        text += _extract_text_recursive(attachment).strip()

    for agg in corpo.find_all("div", class_="art_aggiornamento-akn"):
        text += "\n\n" + _extract_text_recursive(agg).strip()

    return _clean_normattiva_text(text)


def _normattiva_fallback(corpo: Tag) -> str:
    text = _extract_text_recursive(corpo)
    text = _clean_normattiva_text(text)
    return text if text.strip() else "[Articolo senza contenuto o abrogato]"


def _extract_text_recursive(element: Tag) -> str:
    parts = []
    for child in element.children:
        if isinstance(child, NavigableString):
            parts.append(str(child))
        elif isinstance(child, Tag):
            if child.name == "br":
                parts.append("\n")
            elif child.name == "p":
                parts.append(_extract_text_recursive(child) + "\n")
            elif child.name == "li":
                parts.append(" - " + _extract_text_recursive(child) + "\n")
            else:
                parts.append(_extract_text_recursive(child))
    return "".join(parts)


def _clean_normattiva_text(text: str) -> str:
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    text = re.sub(r"(?<=\S)[ \t]+", " ", text)
    return text


# ---------------------------------------------------------------------------
# EUR-Lex fetch + extraction
# ---------------------------------------------------------------------------

_CELLAR_BASE = "https://publications.europa.eu/resource/celex/"


def _build_celex(norma) -> str | None:
    """Build CELEX identifier from Norma. Returns None for treaties."""
    from .map import EURLEX
    norm = norma.tipo_atto_normalized.lower()
    eurlex_val = EURLEX.get(norm)
    if not eurlex_val or eurlex_val.startswith("https"):
        return None
    type_letter = {"reg": "R", "dir": "L"}.get(eurlex_val, "R")
    year = norma.data.split("-")[0] if norma.data and "-" in norma.data else norma.data
    number = norma.numero_atto.zfill(4)
    return f"3{year}{type_letter}{number}"


async def _fetch_eurlex_html(norma) -> tuple[str, str]:
    """Fetch EUR-Lex HTML via EU Publications Office Cellar (bypasses WAF).

    For treaties (TUE, TFUE, CDFUE) falls back to direct EUR-Lex URL.
    Returns (html, url). On failure returns ("", url).
    """
    from .map import EURLEX
    norm = norma.tipo_atto_normalized.lower()
    eurlex_val = EURLEX.get(norm)
    if not eurlex_val:
        return "", ""

    # Treaties: direct URL (no CELEX)
    if eurlex_val.startswith("https"):
        url = eurlex_val
    else:
        celex = _build_celex(norma)
        if not celex:
            return "", ""
        url = f"{_CELLAR_BASE}{celex}"

    async with httpx.AsyncClient(
        headers={
            **_HEADERS,
            "Accept": "application/xhtml+xml,text/html",
            "Accept-Language": "it-IT,it;q=0.9",
        },
        timeout=httpx.Timeout(60.0, connect=10.0),
        follow_redirects=True,
    ) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        html = resp.text

    # Detect WAF challenge (202 + tiny body)
    if resp.status_code == 202 or (len(html) < 5000 and "WAF" in html):
        return "", url

    final_url = str(resp.url) if hasattr(resp, "url") else url
    return html, final_url


def _extract_eurlex_article(html: str, article: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    if not article:
        return soup.get_text(separator="\n", strip=True)

    # Strategy 1: semantic id — div#art_N (most reliable on Cellar XHTML)
    art_id = f"art_{article}"
    article_div = soup.find("div", id=art_id)
    if article_div:
        return _extract_eurlex_subdivision(article_div)

    search_patterns = [f"Articolo {article}", f"Article {article}", f"Art. {article}"]

    # Strategy 2: <p class="oj-ti-art"> (Cellar/OJ format)
    for pattern in search_patterns:
        for p_tag in soup.find_all("p", class_=lambda c: c and "ti-art" in c):
            if p_tag.get_text(strip=True).startswith(pattern):
                # Check if parent is eli-subdivision — if so, extract the whole block
                parent_sub = p_tag.find_parent("div", class_=lambda c: c and "eli-subdivision" in c)
                if parent_sub:
                    return _extract_eurlex_subdivision(parent_sub)
                # Fallback: collect siblings until next article
                return _extract_eurlex_siblings(p_tag)

    # Strategy 3: eli-subdivision containing article text
    for subdiv in soup.find_all("div", class_=lambda c: c and "eli-subdivision" in c):
        title_elem = subdiv.find(
            ["p", "span", "div"],
            string=lambda s: s and any(s.strip().startswith(p) for p in search_patterns),
        )
        if title_elem:
            return _extract_eurlex_subdivision(subdiv)

    # Strategy 4: regex text match anywhere
    article_regex = re.compile(rf"^Articolo\s+{re.escape(str(article))}\b", re.IGNORECASE)
    for tag in soup.find_all(["p", "div", "span", "h1", "h2", "h3", "h4"]):
        if article_regex.match(tag.get_text(strip=True)):
            parent_sub = tag.find_parent("div", class_=lambda c: c and "eli-subdivision" in c)
            if parent_sub:
                return _extract_eurlex_subdivision(parent_sub)
            return _extract_eurlex_siblings(tag)

    return f"[Articolo {article} non trovato nel documento EUR-Lex]"


def _extract_eurlex_subdivision(div: Tag) -> str:
    """Extract text from an eli-subdivision div, handling nested structure."""
    parts: list[str] = []
    for child in div.children:
        if isinstance(child, NavigableString):
            t = str(child).strip()
            if t:
                parts.append(t)
        elif isinstance(child, Tag):
            # Skip nested article subdivisions (they are separate articles)
            if child.get("class") and any("eli-subdivision" in c for c in child.get("class", [])):
                child_id = child.get("id", "")
                if child_id.startswith("art_"):
                    continue
            if child.name == "table":
                for row in child.find_all("tr"):
                    cells = row.find_all("td")
                    row_text = " ".join(c.get_text(strip=True) for c in cells)
                    if row_text:
                        parts.append(row_text)
            else:
                t = child.get_text(strip=True)
                if t:
                    parts.append(t)
    return "\n".join(parts)


def _extract_eurlex_siblings(start_tag: Tag) -> str:
    """Collect text from start_tag and siblings until next article header."""
    full_text = [start_tag.get_text(strip=True)]
    next_article_pat = re.compile(r"^Articolo\s+\d+|^Article\s+\d+|^Art\.\s+\d+", re.IGNORECASE)
    element = start_tag.find_next_sibling()
    while element:
        classes = element.get("class", []) if hasattr(element, "get") else []
        if any("ti-art" in c for c in classes):
            break
        elem_text = element.get_text(strip=True) if hasattr(element, "get_text") else ""
        if next_article_pat.match(elem_text):
            break
        if element.name in ["p", "div", "span"]:
            if elem_text:
                full_text.append(elem_text)
        elif element.name == "table":
            for row in element.find_all("tr"):
                cells = row.find_all("td")
                row_text = " ".join(c.get_text(strip=True) for c in cells)
                if row_text:
                    full_text.append(row_text)
        element = element.find_next_sibling()
    return "\n".join(full_text)


# ---------------------------------------------------------------------------
# Brocardi extraction
# ---------------------------------------------------------------------------

async def _find_brocardi_article_url(client: httpx.AsyncClient, base_url: str, article_num: str) -> str | None:
    """Navigate Brocardi to find the article page URL."""
    cache_key = f"{base_url}#{article_num}"
    if cache_key in _brocardi_url_cache:
        return _brocardi_url_cache[cache_key]

    resp = await client.get(base_url)
    resp.raise_for_status()
    html = resp.text

    pattern = re.compile(rf'href=["\']([^"\']*art{re.escape(article_num)}\.html)["\']')

    # Direct match in main page — use base_url (not domain root) so relative
    # hrefs like "libro-quarto/titolo-ix/art2043.html" resolve correctly
    page_url = str(resp.url) if hasattr(resp, "url") else base_url
    if not page_url.endswith("/"):
        page_url += "/"
    matches = pattern.findall(html)
    if matches:
        result = urljoin(page_url, matches[0])
        _brocardi_url_cache[cache_key] = result
        return result

    # Search in section-title links (sub-pages)
    soup = BeautifulSoup(html, "lxml")
    max_sub_pages = 15
    fetched = 0
    for section in soup.find_all("div", class_="section-title"):
        if fetched >= max_sub_pages:
            break
        for a_tag in section.find_all("a", href=True):
            if fetched >= max_sub_pages:
                break
            sub_url = urljoin(page_url, a_tag.get("href", ""))
            if not sub_url.startswith("https://www.brocardi.it"):
                continue
            fetched += 1
            await asyncio.sleep(0.5)
            try:
                sub_resp = await client.get(sub_url)
                sub_resp.raise_for_status()
                sub_page_url = str(sub_resp.url) if hasattr(sub_resp, "url") else sub_url
                if not sub_page_url.endswith("/"):
                    sub_page_url += "/"
                sub_matches = pattern.findall(sub_resp.text)
                if sub_matches:
                    result = urljoin(sub_page_url, sub_matches[0])
                    _brocardi_url_cache[cache_key] = result
                    return result
            except httpx.HTTPError:
                continue

    return None


def _extract_brocardi_sections(soup: BeautifulSoup) -> dict:
    """Extract Ratio, Spiegazione, Brocardi, Massime from a Brocardi article page."""
    info: dict = {}

    corpo = soup.find("div", class_="panes-condensed panes-w-ads content-ext-guide content-mark")
    if not corpo:
        # Fallback: try the whole body
        corpo = soup.find("body") or soup
        if not corpo:
            return info

    # Brocardi (adagi/proverbi)
    brocardi_sections = corpo.find_all("div", class_="brocardi-content")
    if brocardi_sections:
        info["Brocardi"] = [_clean_text(s.get_text()) for s in brocardi_sections]

    # Ratio Legis
    ratio_section = corpo.find("div", class_="container-ratio")
    if ratio_section:
        ratio_text = ratio_section.find("div", class_="corpoDelTesto")
        if ratio_text:
            info["Ratio"] = _clean_text(ratio_text.get_text())

    # Spiegazione
    spiegazione_header = corpo.find("h3", string=lambda t: t and "Spiegazione dell'art" in t)
    if spiegazione_header:
        spiegazione_content = spiegazione_header.find_next_sibling("div", class_="text")
        if spiegazione_content:
            info["Spiegazione"] = _clean_text(spiegazione_content.get_text())

    # Massime giurisprudenziali
    massime_header = corpo.find("h3", string=lambda t: t and "Massime relative all'art" in t)
    if massime_header:
        massime_content = massime_header.find_next_sibling("div", class_="text")
        if massime_content:
            sentenze = massime_content.find_all("div", class_="sentenza")
            massime = []
            for sentenza_div in sentenze:
                header = sentenza_div.find("strong")
                header_text = header.get_text(strip=True) if header else ""
                body_text = _clean_text(sentenza_div.get_text())
                if body_text:
                    massime.append({"header": header_text, "text": body_text})
            if massime:
                info["Massime"] = massime

    return info


def _clean_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# ---------------------------------------------------------------------------
# Full act download (for PDF generation)
# ---------------------------------------------------------------------------

async def download_eurlex_pdf(norma: "Norma") -> bytes:
    """Download the official PDF from EUR-Lex.

    Returns raw PDF bytes.
    """
    from .map import EURLEX

    norm = norma.tipo_atto_normalized.lower()
    eurlex_val = EURLEX.get(norm)
    if not eurlex_val:
        raise ValueError(f"No EUR-Lex mapping for '{norma.tipo_atto}'")
    if eurlex_val.startswith("https"):
        raise ValueError(f"PDF not available for EU treaties ({norm})")

    type_letter = {"reg": "R", "dir": "L"}.get(eurlex_val, "R")
    year = norma.data.split("-")[0] if "-" in norma.data else norma.data
    number = norma.numero_atto.zfill(4)
    celex = f"3{year}{type_letter}{number}"
    url = f"https://eur-lex.europa.eu/legal-content/IT/TXT/PDF/?uri=CELEX:{celex}"

    async with httpx.AsyncClient(
        headers={**_HEADERS, "Accept": "application/pdf,*/*"},
        timeout=httpx.Timeout(60.0, connect=10.0),
        follow_redirects=True,
    ) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        if not resp.content[:5] == b"%PDF-":
            raise ValueError("EUR-Lex did not return a PDF")
        return resp.content


async def fetch_act_index(norma: "Norma") -> dict:
    """Fetch the structured index (rubriche) of a Normattiva act.

    Uses /atto/vediRubriche endpoint to get article titles without full text.
    Returns: {"index": list[str], "codice_redazionale": str, "url": str} or {"error": str}
    """
    act_url = norma.url()
    if not act_url:
        return {"index": [], "url": "", "error": "Could not generate URL"}

    async with httpx.AsyncClient(
        headers=_HEADERS,
        timeout=httpx.Timeout(60.0, connect=10.0),
        follow_redirects=True,
    ) as client:
        resp = await client.get(act_url)
        resp.raise_for_status()
        html = resp.text

        # Extract codiceRedazionale from ELI meta tags
        soup = BeautifulSoup(html, "lxml")
        codice_redaz = ""
        data_gu = ""
        for meta in soup.find_all("meta", attrs={"property": "eli:id_local"}):
            codice_redaz = meta.get("content", "")
            break
        # Extract dataPubblicazioneGazzetta from the page
        gu_match = re.search(r'dataPubblicazioneGazzetta=(\d{4}-\d{2}-\d{2})', html)
        if gu_match:
            data_gu = gu_match.group(1)

        if not codice_redaz or not data_gu:
            # Try to extract from the canonical URL or other patterns
            redaz_match = re.search(r'codiceRedazionale=([A-Z0-9]+)', html)
            if redaz_match:
                codice_redaz = redaz_match.group(1)
            gu_match2 = re.search(r'atto\.dataPubblicazioneGazzetta=(\d{4}-\d{2}-\d{2})', html)
            if gu_match2:
                data_gu = gu_match2.group(1)

        if not codice_redaz or not data_gu:
            return {"index": [], "url": act_url, "error": "Could not extract codiceRedazionale or dataGU from page"}

        # Fetch rubriche
        rub_url = f"https://www.normattiva.it/atto/vediRubriche?atto.dataPubblicazioneGazzetta={data_gu}&atto.codiceRedazionale={codice_redaz}"
        resp2 = await client.get(rub_url)
        resp2.raise_for_status()

    rub_soup = BeautifulSoup(resp2.text, "lxml")
    entries: list[str] = []
    for li in rub_soup.find_all("li"):
        text = li.get_text(strip=True)
        if text:
            entries.append(text)

    if not entries:
        # Fallback: extract from the raw text
        raw = rub_soup.get_text(separator="\n", strip=True)
        entries = [line.strip() for line in raw.splitlines() if line.strip()]

    return {
        "index": entries,
        "codice_redazionale": codice_redaz,
        "data_gu": data_gu,
        "url": act_url,
    }


async def fetch_normattiva_full_text(norma: "Norma") -> dict:
    """Fetch the complete text of a Normattiva act by loading all articles via AJAX.

    Normattiva only renders Art. 1 in the static DOM. All other articles are loaded
    on-demand via /atto/caricaArticolo. This function extracts all article URLs from
    the sidebar tree (#albero) and fetches each one.

    Returns: {"text": str, "title": str, "url": str, "article_count": int} or {"error": str}
    """
    act_url = norma.url()
    if not act_url:
        return {"text": "", "title": "", "url": "", "error": "Could not generate URL"}

    ajax_headers = {**_HEADERS, "X-Requested-With": "XMLHttpRequest"}

    async with httpx.AsyncClient(
        headers=_HEADERS,
        timeout=httpx.Timeout(120.0, connect=15.0),
        follow_redirects=True,
    ) as client:
        resp = await client.get(act_url)
        resp.raise_for_status()
        html = resp.text
        soup = BeautifulSoup(html, "lxml")

        title_tag = soup.find("h1") or soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else str(norma)

        # Extract first article already in the DOM
        first_body = soup.find("div", class_="bodyTesto")
        first_article_text = ""
        if first_body:
            first_article_text = _extract_text_recursive(first_body)
            first_article_text = _clean_normattiva_text(first_article_text)

        # Extract all article AJAX URLs from the sidebar tree
        article_urls = _extract_article_ajax_urls(html)

        if not article_urls:
            # Fallback: return just the first article (old behavior)
            return {"text": first_article_text, "title": title, "url": act_url, "article_count": 1}

        # Fetch all articles via AJAX, preserving order
        all_parts: list[str] = []
        seen_urls: set[str] = set()
        for ajax_path in article_urls:
            if ajax_path in seen_urls:
                continue
            seen_urls.add(ajax_path)
            ajax_url = f"https://www.normattiva.it{ajax_path}"
            try:
                art_resp = await client.get(ajax_url, headers=ajax_headers)
                art_resp.raise_for_status()
                art_html = art_resp.text
                # Skip error pages
                if "Normattiva - Errore" in art_html or len(art_html) < 50:
                    continue
                art_soup = BeautifulSoup(art_html, "lxml")
                body = art_soup.find("div", class_="bodyTesto")
                if body:
                    text = _extract_text_recursive(body)
                    text = _clean_normattiva_text(text)
                    if text and text != "[Articolo senza contenuto o abrogato]":
                        all_parts.append(text)
            except httpx.HTTPError:
                continue

    if not all_parts:
        return {"text": first_article_text, "title": title, "url": act_url, "article_count": 1}

    full_text = "\n\n---\n\n".join(all_parts)
    return {"text": full_text, "title": title, "url": act_url, "article_count": len(all_parts)}


def _extract_article_ajax_urls(html: str) -> list[str]:
    """Extract /atto/caricaArticolo URLs from onclick handlers in the sidebar tree.

    Normattiva sidebar lists multiple versions (art.versione) for articles that
    have been amended. We keep only the first occurrence per article (idGruppo +
    idArticolo + flagTipoArticolo), which is the current/vigente version.
    """
    pattern = re.compile(r"showArticle\('(/atto/caricaArticolo\?[^']+)'")
    matches = pattern.findall(html)
    # Deduplicate by article identity (keep first = vigente version).
    # Params can appear in any order, so extract each individually.
    seen_articles: set[str] = set()
    unique: list[str] = []
    for raw_url in matches:
        url_clean = raw_url.replace("&amp;", "&")
        grp = re.search(r"art\.idGruppo=(\d+)", url_clean)
        art = re.search(r"art\.idArticolo=(\d+)", url_clean)
        flag = re.search(r"art\.flagTipoArticolo=(\d+)", url_clean)
        if grp and art and flag:
            article_key = f"{grp.group(1)}_{art.group(1)}_{flag.group(1)}"
            if article_key in seen_articles:
                continue
            seen_articles.add(article_key)
        elif url_clean in seen_articles:
            continue
        else:
            seen_articles.add(url_clean)
        unique.append(url_clean)
    return unique

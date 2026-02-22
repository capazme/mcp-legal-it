"""Unified scraper for Normattiva, EUR-Lex, and Brocardi using httpx."""

import asyncio
import re
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup, NavigableString, Tag

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
    url = nv.url()
    if not url:
        return {"text": "", "url": "", "source": "", "error": "Could not generate URL for this act"}

    is_eurlex = nv.norma._is_eurlex()
    source = "eurlex" if is_eurlex else "normattiva"

    async with httpx.AsyncClient(headers=_HEADERS, timeout=_TIMEOUT, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        html = resp.text

    if is_eurlex:
        text = _extract_eurlex_article(html, nv.numero_articolo)
    else:
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
        return soup.get_text(separator="\n", strip=True)[:5000]

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
# EUR-Lex extraction (4 strategies from original)
# ---------------------------------------------------------------------------

def _extract_eurlex_article(html: str, article: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    if not article:
        return soup.get_text(separator="\n", strip=True)[:5000]

    search_patterns = [f"Articolo {article}", f"Article {article}", f"Art. {article}"]
    article_section = None

    # Strategy 1: <p class="ti-art">
    for pattern in search_patterns:
        article_section = soup.find(
            lambda tag: tag.name == "p"
            and "ti-art" in tag.get("class", [])
            and tag.get_text(strip=True).startswith(pattern)
        )
        if article_section:
            break

    # Strategy 2: class containing 'art' or 'title'
    if not article_section:
        for pattern in search_patterns:
            article_section = soup.find(
                lambda tag: tag.get("class")
                and any("art" in c.lower() or "title" in c.lower() for c in tag.get("class", []))
                and tag.get_text(strip=True).startswith(pattern)
            )
            if article_section:
                break

    # Strategy 3: regex text match
    if not article_section:
        article_regex = re.compile(rf"^Articolo\s+{re.escape(str(article))}\b", re.IGNORECASE)
        article_section = soup.find(
            lambda tag: tag.name in ["p", "div", "span", "h1", "h2", "h3", "h4"]
            and article_regex.match(tag.get_text(strip=True))
        )

    # Strategy 4: eli-subdivision divs
    if not article_section:
        for subdiv in soup.find_all("div", class_=lambda c: c and "eli-subdivision" in c):
            title_elem = subdiv.find(
                ["p", "span", "div"],
                string=lambda s: s and any(s.strip().startswith(p) for p in search_patterns),
            )
            if title_elem:
                article_section = subdiv
                break

    if not article_section:
        return f"[Articolo {article} non trovato nel documento EUR-Lex]"

    # Collect text until next article
    full_text = [article_section.get_text(strip=True)]
    element = article_section.find_next_sibling()
    next_article_pat = re.compile(r"^Articolo\s+\d+|^Article\s+\d+|^Art\.\s+\d+", re.IGNORECASE)

    while element:
        if element.name == "p" and "ti-art" in element.get("class", []):
            break
        elem_text = element.get_text(strip=True) if element.name else ""
        if next_article_pat.match(elem_text):
            break
        if element.name in ["p", "div", "span"]:
            text = element.get_text(strip=True)
            if text:
                full_text.append(text)
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

    # Direct match in main page
    matches = pattern.findall(html)
    if matches:
        result = urljoin("https://www.brocardi.it", matches[0])
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
            sub_url = urljoin("https://www.brocardi.it", a_tag.get("href", ""))
            if not sub_url.startswith("https://www.brocardi.it"):
                continue
            fetched += 1
            await asyncio.sleep(0.5)
            try:
                sub_resp = await client.get(sub_url)
                sub_resp.raise_for_status()
                sub_matches = pattern.findall(sub_resp.text)
                if sub_matches:
                    result = urljoin("https://www.brocardi.it", sub_matches[0])
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


async def fetch_normattiva_full_text(norma: "Norma") -> dict:
    """Fetch the complete text of a Normattiva act via /esporta/attoCompleto.

    Returns: {"text": str, "title": str, "url": str} or {"error": str}
    """
    act_url = norma.url()
    if not act_url:
        return {"text": "", "title": "", "url": "", "error": "Could not generate URL"}

    async with httpx.AsyncClient(
        headers=_HEADERS,
        timeout=httpx.Timeout(60.0, connect=10.0),
        follow_redirects=True,
    ) as client:
        resp = await client.get(act_url)
        resp.raise_for_status()
        html = resp.text

        # Try to find the /esporta/attoCompleto link in the page
        export_match = re.search(r'(/esporta/attoCompleto\?[^"\'>\s]+)', html)
        final_url = act_url

        if export_match:
            export_path = export_match.group(1).replace("&amp;", "&")
            export_url = f"https://www.normattiva.it{export_path}"
            resp = await client.get(export_url)
            resp.raise_for_status()
            html = resp.text
            final_url = export_url

    soup = BeautifulSoup(html, "lxml")

    title_tag = soup.find("h1") or soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else str(norma)

    body = soup.find("div", class_="bodyTesto") or soup.find("body")
    if body:
        text = _extract_text_recursive(body)
        text = _clean_normattiva_text(text)
    else:
        text = soup.get_text(separator="\n", strip=True)

    return {"text": text, "title": title, "url": final_url}

"""Client for CONSOB (Commissione Nazionale per le Societa e la Borsa).

Endpoint: https://www.consob.it/web/area-pubblica/bollettino/ricerca

Il sito usa Liferay Portal — nessuna API pubblica JSON. Scraping HTML via BeautifulSoup.
Documenti identificati da numero delibera (es. "23257", "23256-1").
"""

import re
from dataclasses import dataclass

import httpx
from bs4 import BeautifulSoup

_BASE = "https://www.consob.it"
_SEARCH_PATH = "/web/area-pubblica/bollettino/ricerca"
_DOC_PATH = "/web/area-pubblica/-/delibera-n."
_PORTLET = "it_consob_BollettinoRicercaPortlet"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": _BASE + "/",
}

_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
_MAX_TEXT_LENGTH = 8000
_RESULTS_PER_PAGE = 50

# Top tipologie (valori interni Liferay)
TIPOLOGIE: dict[str, str] = {
    "delibere": "delibera",
    "comunicazioni": "comunicazione",
    "provvedimenti_urgenti": "provvedimento",
    "altre_decisioni": "ric114|opael|oicvmcom|prospel|oicrprosp|rapmag|verisp",
    "opa": "opael",
    "appendice": "decmef|decca|dectar|dectc",
    "tutti": "delibera|comunicazione|provvedimento|quesito|ric114|opael|oicvmcom|prospel|oicrprosp|rapmag|verisp|decmef|decca|dectar|dectc|cca",
}

# Top 10 argomenti con ID Liferay
ARGOMENTI: dict[str, str] = {
    "abusi_di_mercato": "4989535",
    "intermediari": "4989527",
    "emittenti": "4989652",
    "mercati": "4989656",
    "offerte_acquisto": "4989740",
    "offerte_vendita": "4989736",
    "gestione_collettiva": "4989796",
    "servizi_investimento": "4989660",
    "cripto_attivita": "10135520",
    "crowdfunding": "4989491",
}


@dataclass
class DocResult:
    numero: str                  # e.g. "23257", "23256-1"
    title: str
    date: str                    # DD/MM/YYYY (data della delibera)
    data_pubblicazione: str = "" # DD/MM/YYYY


def _build_search_params(
    keywords: str = "",
    tipologia: str = "",
    argomento_id: str = "",
    start_date: str = "",
    end_date: str = "",
    delta: int = 50,
    cur: int = 1,
) -> dict:
    prefix = f"_{_PORTLET}_"
    return {
        "p_p_id": _PORTLET,
        "p_p_lifecycle": "0",
        "p_p_state": "normal",
        "p_p_mode": "view",
        f"{prefix}mvcRenderCommandName": "/search",
        f"{prefix}keywords": keywords,
        f"{prefix}tipologia": tipologia,
        f"{prefix}argomento": argomento_id,
        f"{prefix}startDate": start_date,
        f"{prefix}endDate": end_date,
        f"{prefix}delta": str(delta),
        f"{prefix}cur": str(cur),
    }


def _parse_results(html: str) -> list[DocResult]:
    """Parse search results HTML into DocResult list.

    Each result is a <div class="journal-content-article" data-analytics-asset-title="...">
    containing a <b><a href="...">title</a></b> and <p class="dwn"> date fields.
    """
    soup = BeautifulSoup(html, "lxml")
    results = []

    for article in soup.find_all("div", class_="journal-content-article"):
        asset_title = article.get("data-analytics-asset-title", "")
        if not asset_title or "footer" in asset_title.lower():
            continue

        link = article.find("a", href=True)
        if not link:
            continue

        href = link.get("href", "")
        # Extract numero from URL slug: /delibera-n.-23257 or /delibera-n.-23256-1
        num_match = re.search(r"/delibera-n\.-(\d+(?:-\d+)?)", href)
        if not num_match:
            # Try from asset title: "Delibera n. 23257"
            num_match = re.search(r"n\.\s*(\d+(?:-\d+)?)", asset_title)
        if not num_match:
            continue

        numero = num_match.group(1)
        title = link.get_text(strip=True)

        # Dates from <p class="dwn">
        date_str = ""
        pub_date_str = ""
        for p in article.find_all("p", class_="dwn"):
            text = p.get_text(strip=True)
            date_match = re.search(r"(\d{2}/\d{2}/\d{4})", text)
            if date_match:
                if "Pubblicazione" in text:
                    pub_date_str = date_match.group(1)
                else:
                    date_str = date_match.group(1)

        results.append(DocResult(
            numero=numero,
            title=title,
            date=date_str,
            data_pubblicazione=pub_date_str,
        ))

    return results


def _parse_doc(html: str, numero: str) -> tuple[str, str]:
    """Parse document detail page HTML. Returns (title, body_text)."""
    soup = BeautifulSoup(html, "lxml")

    for tag in soup(["script", "style", "nav"]):
        tag.decompose()

    # Find the content article (not the footer)
    content = None
    for article in soup.find_all("div", class_="journal-content-article"):
        asset_title = article.get("data-analytics-asset-title", "")
        if asset_title and "footer" not in asset_title.lower():
            content = article
            break

    if not content:
        content = soup.find("body") or soup

    title_attr = content.get("data-analytics-asset-title", "") if content else ""
    title = title_attr or f"Delibera n. {numero}"

    text = content.get_text("\n", strip=True) if content else ""
    # Remove breadcrumb prefix "Bollettino « Indietro"
    text = re.sub(r"^Bollettino\s*«\s*Indietro\s*", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return title, text


def format_result(doc: DocResult) -> str:
    """Format a single DocResult as markdown block."""
    url = f"{_BASE}{_DOC_PATH}-{doc.numero}"
    lines = [f"### Delibera n. {doc.numero}"]
    lines.append(f"**Titolo**: {doc.title[:300]}")
    if doc.date:
        lines.append(f"**Data**: {doc.date}")
    if doc.data_pubblicazione:
        lines.append(f"**Pubblicazione**: {doc.data_pubblicazione}")
    lines.append(f"**Link**: [Delibera n. {doc.numero}]({url})")
    return "\n".join(lines)


def format_full(title: str, text: str, numero: str) -> str:
    """Format full document as markdown."""
    url = f"{_BASE}{_DOC_PATH}-{numero}"
    truncated = len(text) > _MAX_TEXT_LENGTH
    body = text[:_MAX_TEXT_LENGTH] if truncated else text
    lines = [f"# {title}", f"**Link**: [Delibera n. {numero}]({url})", "", body]
    if truncated:
        lines.append(
            f"\n---\n*[Testo troncato a {_MAX_TEXT_LENGTH} caratteri su {len(text)} totali]*"
        )
    return "\n".join(lines)


async def search_delibere(
    keywords: str = "",
    tipologia: str = "",
    argomento_id: str = "",
    start_date: str = "",
    end_date: str = "",
    rows: int = 20,
) -> list[DocResult]:
    """Search CONSOB bollettino. Fetches multiple pages if rows > 50."""
    rows = min(rows, 100)
    results: list[DocResult] = []
    cur = 1
    delta = min(rows, _RESULTS_PER_PAGE)

    async with httpx.AsyncClient(
        timeout=_TIMEOUT, headers=_HEADERS, follow_redirects=True
    ) as client:
        while len(results) < rows:
            params = _build_search_params(
                keywords=keywords,
                tipologia=tipologia,
                argomento_id=argomento_id,
                start_date=start_date,
                end_date=end_date,
                delta=delta,
                cur=cur,
            )
            resp = await client.get(_BASE + _SEARCH_PATH, params=params)
            resp.raise_for_status()

            page_results = _parse_results(resp.text)
            if not page_results:
                break

            results.extend(page_results)
            cur += 1

            if len(page_results) < delta:
                break

    return results[:rows]


async def fetch_delibera(numero: str) -> tuple[str, str]:
    """Fetch full delibera text. Returns (title, text)."""
    url = f"{_BASE}{_DOC_PATH}-{numero}"
    async with httpx.AsyncClient(
        timeout=_TIMEOUT, headers=_HEADERS, follow_redirects=True
    ) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return _parse_doc(resp.text, numero)

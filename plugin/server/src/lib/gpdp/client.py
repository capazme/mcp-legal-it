"""Client for Garante per la Protezione dei Dati Personali (GPDP).

Endpoint: https://www.garanteprivacy.it/web/guest/home/ricerca
          https://www.garanteprivacy.it/web/guest/home/docweb/-/docweb-display/print/{ID}

Il sito usa Liferay Portal — nessuna API pubblica JSON. Scraping HTML via BeautifulSoup.
Documenti identificati da DocWeb ID (interi sequenziali, es. 9677876 per cookie guidelines 2021).
"""

import re
from dataclasses import dataclass, field

import httpx
from bs4 import BeautifulSoup

_BASE = "https://www.garanteprivacy.it"
_SEARCH_PATH = "/web/guest/home/ricerca"
_PRINT_PATH = "/web/guest/home/docweb/-/docweb-display/print"
_DOC_PATH = "/web/guest/home/docweb/-/docweb-display/docweb"
_PORTLET = "g_gpdp5_search_GGpdp5SearchPortlet"

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
_MAX_TEXT_LENGTH = 6000
_RESULTS_PER_PAGE = 10


@dataclass
class DocResult:
    docweb_id: int
    title: str
    date: str           # DD/MM/YYYY
    tipologia: str
    argomenti: list[str] = field(default_factory=list)
    abstract: str = ""


def _build_search_params(
    query: str,
    data_da: str = "",
    data_a: str = "",
    tipologia_id: str = "",
    argomento_id: str = "",
    page: int = 1,
    sort_by: str = "data",
) -> dict:
    prefix = f"_{_PORTLET}_"
    return {
        "p_p_id": _PORTLET,
        "p_p_lifecycle": "0",
        "p_p_state": "normal",
        "p_p_mode": "view",
        f"{prefix}mvcRenderCommandName": "/renderSearch",
        f"{prefix}text": query,
        f"{prefix}dataInizio": data_da,
        f"{prefix}dataFine": data_a,
        f"{prefix}idsTipologia": tipologia_id,
        f"{prefix}idsArgomenti": argomento_id,
        f"{prefix}ordinamentoPer": "DESC",
        f"{prefix}ordinamentoTipo": sort_by,
        f"{prefix}cur": str(page),
    }


def _parse_results(html: str) -> list[DocResult]:
    """Parse search results HTML into DocResult list.

    Real page uses Bootstrap card layout (Liferay portlet):
    - Result container: <div class="card-risultato">
    - Title link:       <a class="titolo-risultato ...">
    - Date:             <div class="data-risultato"><p>DD/MM/YYYY</p>
    - Abstract:         <p class="estratto-risultato ...">
    - Tipologia/Args:   <p class="ricercaArgomentiPar"> labels + badge links in next sibling
    """
    soup = BeautifulSoup(html, "lxml")
    results = []

    for card in soup.find_all("div", class_="card-risultato"):
        # Title and docweb ID
        link = card.find("a", class_="titolo-risultato")
        if not link:
            continue
        href = link.get("href", "")
        id_match = re.search(r"/docweb/(\d+)", href)
        if not id_match:
            continue

        docweb_id = int(id_match.group(1))
        title = link.get_text(strip=True)
        # Strip trailing [ID] suffix from title (e.g. "Provvedimento ... [10211780]")
        title = re.sub(r"\s*\[\d+\]\s*$", "", title).strip()

        # Date
        date_div = card.find("div", class_="data-risultato")
        date_p = date_div.find("p") if date_div else None
        date_str = date_p.get_text(strip=True) if date_p else ""

        # Abstract
        abstract_p = card.find("p", class_="estratto-risultato")
        abstract = abstract_p.get_text(" ", strip=True) if abstract_p else ""
        abstract = re.sub(r"\[…\]|\[\.\.\.\]|\[\.{3}\]", "", abstract).strip()

        # Tipologia and Argomenti — parsed from <p class="ricercaArgomentiPar"> labels
        tipologia = ""
        argomenti = []

        for label_p in card.find_all("p", class_="ricercaArgomentiPar"):
            label_text = label_p.get_text(strip=True)
            # Badges are in the next column div (sibling of label_p.parent)
            parent_col = label_p.parent
            next_col = parent_col.find_next_sibling("div") if parent_col else None
            badges = []
            if next_col:
                badges = [
                    a.get_text(strip=True)
                    for a in next_col.find_all("a")
                    if a.get_text(strip=True)
                ]
            if "Tipologia" in label_text:
                tipologia = badges[0] if badges else ""
            elif "Argomenti" in label_text or "Argomento" in label_text:
                argomenti = badges

        results.append(DocResult(
            docweb_id=docweb_id,
            title=title,
            date=date_str,
            tipologia=tipologia,
            argomenti=argomenti,
            abstract=abstract,
        ))

    return results


def _parse_doc(html: str, docweb_id: int) -> tuple[str, str]:
    """Parse document print page HTML. Returns (title, body_text)."""
    soup = BeautifulSoup(html, "lxml")

    for tag in soup(["script", "style", "nav", "header", "footer"]):
        tag.decompose()
    # Remove Liferay social sharing / toolbar sections
    for cls in ["azioni", "condivisione", "taglib-social-bookmarks", "print-button"]:
        for el in soup.find_all(class_=lambda c: c and cls in c.lower()):
            el.decompose()

    heading = soup.find("h1") or soup.find("h2")
    raw_title = heading.get_text(strip=True) if heading else f"Documento DocWeb {docweb_id}"
    # Strip trailing [ID] suffix
    title = re.sub(r"\s*\[\d+\]\s*$", "", raw_title).strip() or raw_title

    body = soup.find("body")
    text = body.get_text("\n", strip=True) if body else ""
    text = re.sub(r"\n{3,}", "\n\n", text)

    return title, text


def format_result(doc: DocResult) -> str:
    """Format a single DocResult as markdown block."""
    url = f"{_DOC_PATH}/{doc.docweb_id}"
    lines = [f"### {doc.title}"]
    if doc.tipologia:
        lines.append(f"**Tipo**: {doc.tipologia}")
    if doc.date:
        lines.append(f"**Data**: {doc.date}")
    lines.append(f"**DocWeb**: [{doc.docweb_id}]({url})")
    if doc.argomenti:
        lines.append(f"**Argomenti**: {', '.join(doc.argomenti)}")
    if doc.abstract:
        disp = doc.abstract[:300]
        if len(doc.abstract) > 300:
            disp += "…"
        lines.append(f"**Estratto**: {disp}")
    return "\n".join(lines)


def format_full(title: str, text: str, docweb_id: int) -> str:
    """Format full document as markdown."""
    url = f"{_DOC_PATH}/{docweb_id}"
    truncated = len(text) > _MAX_TEXT_LENGTH
    body = text[:_MAX_TEXT_LENGTH] if truncated else text
    lines = [f"# {title}", f"**DocWeb**: [{docweb_id}]({url})", "", body]
    if truncated:
        lines.append(
            f"\n---\n*[Testo troncato a {_MAX_TEXT_LENGTH} caratteri su {len(text)} totali]*"
        )
    return "\n".join(lines)


async def search_docs(
    query: str = "",
    data_da: str = "",
    data_a: str = "",
    tipologia_id: str = "",
    argomento_id: str = "",
    rows: int = 10,
    sort_by: str = "data",
) -> list[DocResult]:
    """Search GPDP documents. Fetches multiple pages if rows > 10."""
    rows = min(rows, 50)
    results: list[DocResult] = []
    page = 1

    async with httpx.AsyncClient(
        timeout=_TIMEOUT, headers=_HEADERS, follow_redirects=True
    ) as client:
        while len(results) < rows:
            params = _build_search_params(
                query=query,
                data_da=data_da,
                data_a=data_a,
                tipologia_id=tipologia_id,
                argomento_id=argomento_id,
                page=page,
                sort_by=sort_by,
            )
            resp = await client.get(_BASE + _SEARCH_PATH, params=params)
            resp.raise_for_status()

            page_results = _parse_results(resp.text)
            if not page_results:
                break

            results.extend(page_results)
            page += 1

            if len(page_results) < _RESULTS_PER_PAGE:
                break

    return results[:rows]


async def fetch_doc(docweb_id: int) -> tuple[str, str]:
    """Fetch full document text via print URL. Returns (title, text)."""
    url = f"{_BASE}{_PRINT_PATH}/{docweb_id}"
    async with httpx.AsyncClient(
        timeout=_TIMEOUT, headers=_HEADERS, follow_redirects=True
    ) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return _parse_doc(resp.text, docweb_id)

"""Client for CONSOB (Commissione Nazionale per le Societa e la Borsa).

Endpoint: https://www.consob.it/web/area-pubblica/bollettino/ricerca

Il sito usa Liferay Portal — nessuna API pubblica JSON. Scraping HTML via BeautifulSoup.
Le delibere sono identificate dal numero (es. "23257", "23256-1") e hanno la pagina
/-/delibera-n.-<numero>. Gli altri documenti del Bollettino (comunicazioni, richiami di
attenzione, avvisi, orientamenti, sentenze in appendice) hanno pagine con slug propri e
numerazioni diverse ("13/25", "0117520", nessun numero): per loro fa fede l'href del risultato.
"""

import re
from dataclasses import dataclass
from urllib.parse import urljoin

import httpx

from src.lib._http import retry_request
from src.lib._paging import page, resume_hint
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
    numero: str                  # e.g. "23257", "23256-1", "13/25", "0117520"; "" if none
    title: str
    date: str                    # DD/MM/YYYY (data dell'atto)
    data_pubblicazione: str = "" # DD/MM/YYYY
    href: str = ""               # real page of the document, without the ?redirect= query
    tipo: str = ""               # "Delibera", "Comunicazione", "Richiamo di attenzione", ...
    designazione: str = ""       # heading: "Comunicazione n. 13/25", "Avviso Consob del 4 settembre 2025"


# Leading "<tipo> n. <numero>" of a result title: "Comunicazione n. 13/25 del 4 luglio 2025 - ...",
# "Richiamo di attenzione n. 1/23 - ...", "Delibera n. 24140, ordine ...". The number keeps its
# year suffix ("13/25") and protocol zeros ("0117520"): truncating it made "13/25" collide with
# "13/24" and with Delibera n. 13.
_TIPO_NUMERO_RE = re.compile(
    r"^(?P<tipo>[A-Za-zÀ-ÿ'’ ]{3,40}?)\s+n\.\s*(?P<num>\d(?:[\d./-]*\d)?)"
)
# Unnumbered items are designated by their date: "Avviso Consob del 1° luglio 2025 in merito ...".
_DESIGNAZIONE_DATA_RE = re.compile(
    r"^(?P<d>.{3,80}?\bdel(?:l['’])?\s*\d{1,2}°?\s+[a-zà-ù]+\s+\d{4})", re.I
)
_DELIBERA_HREF_RE = re.compile(r"/delibera-n\.-(\d+(?:-\d+)?)(?:$|[/?#])")


def _asset_title_is_clean(asset_title: str) -> bool:
    """Liferay asset titles are sometimes internal slugs ("ca_roma_20230113_patalano") or
    placeholders ("Comunicazione comunicazione cg n. 0"): never show those as a heading."""
    t = asset_title.strip().lower()
    return bool(t) and "_" not in t and "comunicazione cg" not in t and not re.search(r"n\.\s*0$", t)


def _identify(title: str, asset_title: str, href: str) -> tuple[str, str, str]:
    """Return (tipo, numero, designazione) of a Bollettino result."""
    m = _DELIBERA_HREF_RE.search(href)
    if m:
        return "Delibera", m.group(1), f"Delibera n. {m.group(1)}"
    clean_asset = _asset_title_is_clean(asset_title)
    for text in (title, asset_title if clean_asset else ""):
        m = _TIPO_NUMERO_RE.match(text.strip())
        if m:
            tipo = re.sub(r"\s+", " ", m.group("tipo")).strip()
            tipo = tipo[:1].upper() + tipo[1:]
            return tipo, m.group("num"), f"{tipo} n. {m.group('num')}"
    m = _DESIGNAZIONE_DATA_RE.match(title.strip())
    if m:
        return "", "", re.sub(r"\s+", " ", m.group("d")).strip()
    if clean_asset:
        return "", "", asset_title.strip()
    return "", "", title.strip()[:100]


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

        # The real page of the document, without the ?redirect= back-link to the search. Only
        # delibere live at /delibera-n.-<n>; every other item has its own slug.
        href = urljoin(_BASE + "/", link.get("href", "").split("?", 1)[0].split("#", 1)[0])
        title = link.get_text(" ", strip=True)
        tipo, numero, designazione = _identify(title, asset_title, href)

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
            href=href,
            tipo=tipo,
            designazione=designazione,
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


def is_delibera(doc: DocResult) -> bool:
    """True for a delibera, the only document leggi_delibera_consob() can read by number."""
    return (doc.tipo or "Delibera") == "Delibera" and bool(doc.numero)


def format_result(doc: DocResult) -> str:
    """Format a single DocResult as markdown block, with its real type, number and link."""
    heading = doc.designazione or f"{doc.tipo or 'Delibera'} n. {doc.numero}"
    # The href of the result is the only reliable link: /delibera-n.-<n> exists for delibere
    # only (a Comunicazione n. 13/25 rebuilt as /delibera-n.-13 answers 404).
    url = doc.href or f"{_BASE}{_DOC_PATH}-{doc.numero}"
    lines = [f"### {heading}"]
    lines.append(f"**Titolo**: {doc.title[:300]}")
    if doc.date:
        lines.append(f"**Data**: {doc.date}")
    if doc.data_pubblicazione:
        lines.append(f"**Pubblicazione**: {doc.data_pubblicazione}")
    lines.append(f"**Link**: [{heading}]({url})")
    if not is_delibera(doc):
        lines.append(
            "**Nota**: non e' una delibera: leggi_delibera_consob() non la legge per numero, "
            "il testo e' alla pagina del link."
        )
    return "\n".join(lines)


def format_full(title: str, text: str, numero: str, da_carattere: int = 1) -> str:
    """Format full document as markdown.

    Positions in the notes count `text`, the body of the page. `da_carattere` > 1 renders
    the window of `text` that starts there.
    """
    url = f"{_BASE}{_DOC_PATH}-{numero}"
    lines = [f"# {title}", f"**Link**: [Delibera n. {numero}]({url})", ""]
    if da_carattere > 1:
        body, note = page(text, da_carattere, _MAX_TEXT_LENGTH)
        lines.append(body)
        lines.append(f"\n---\n{note}")
        return "\n".join(lines)
    truncated = len(text) > _MAX_TEXT_LENGTH
    lines.append(text[:_MAX_TEXT_LENGTH] if truncated else text)
    if truncated:
        lines.append(
            f"\n---\n*[Testo troncato a {_MAX_TEXT_LENGTH} caratteri su {len(text)} totali: "
            f"{resume_hint(_MAX_TEXT_LENGTH + 1)}]*"
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
    rows = max(1, min(rows, 100))
    results: list[DocResult] = []
    seen: set[str] = set()
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
            resp = await retry_request(client, "GET", _BASE + _SEARCH_PATH, dataset="consob", params=params)

            page_results = _parse_results(resp.text)
            if not page_results:
                break

            for doc in page_results:
                # Deduplicate on the page of the document, not on the number: "n. 13/24",
                # "n. 13/25" and Delibera n. 13 are three different documents, and items
                # without a number (Avvisi, Orientamenti) must not collapse into one.
                key = doc.href or f"{doc.tipo}|{doc.numero}|{doc.title}"
                if key in seen:
                    continue
                seen.add(key)
                results.append(doc)
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
        resp = await retry_request(client, "GET", url, dataset="consob")
        return _parse_doc(resp.text, numero)

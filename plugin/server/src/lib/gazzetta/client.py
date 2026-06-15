"""Client for the Gazzetta Ufficiale della Repubblica Italiana.

Endpoint: https://www.gazzettaufficiale.it (the ``www`` host is REQUIRED).

The site is a Java/Spring application that uses a ``jsessionid`` cookie. There is
NO XML / Akoma Ntoso layer for the Gazzetta — only HTML pages, ELI RDFa metadata
in the page head, RSS feeds for the "latest" view, and an official PDF.

Access strategy (mirrors the recon mapping):

* "latest" → RSS feed ``/rss/{SG|S1..S5|P2}`` (stable, no session needed).
* parametric / full-text search → GET ``/eli/ricerca`` to seed the jsessionid on
  the SAME client, then POST ``/do/ricerca/atto/{serie}/originario/{page}`` with
  the COMPLETE field set (omitting any field returns HTTP 500). Page index is
  0-based.
* fetch one atto → ELI permalink ``/eli/id/{yyyy}/{mm}/{dd}/{codice}/sg`` (RDFa
  head) + ``vediMenuHTML`` (harvest the exact ``caricaArticolo`` URLs — building
  them blindly returns a "in fase di caricamento" stub) + the harvested article
  pages (text lives in ``div.dettaglio_atto_testo``).
* sommario of a gazzetta → ``/eli/gu/{yyyy}/{mm}/{dd}/{numeroGazzetta}/sg``.
* PDF → ``/eli/gu/{yyyy}/{mm}/{dd}/{numeroGazzetta}/sg/pdf`` (URL returned, never
  inlined).
"""

import re
from dataclasses import dataclass, field
from email.utils import parsedate_to_datetime

import httpx
from bs4 import BeautifulSoup

from src.lib._http import retry_request

_BASE = "https://www.gazzettaufficiale.it"
_RICERCA_SEED_PATH = "/eli/ricerca"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": _BASE + "/",
}
_RSS_HEADERS = {**_HEADERS, "Accept": "application/rss+xml,application/xml;q=0.9,*/*;q=0.8"}

_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
_MAX_TEXT_LENGTH = 25000

# Human-friendly serie keys -> path segment used in the search/fetch URLs.
SERIE: dict[str, str] = {
    "serie_generale": "serie_generale",
    "unione_europea": "unione_europea",
    "regioni": "regioni",
    "corte_costituzionale": "corte_costituzionale",
    "parte_seconda": "parte_seconda",
    "contratti": "contratti",
    "concorsi": "concorsi",
}

# Human-friendly serie keys -> RSS feed code.
RSS_CODE: dict[str, str] = {
    "serie_generale": "SG",
    "unione_europea": "S1",
    "regioni": "S2",
    "corte_costituzionale": "S3",
    "contratti": "S4",
    "concorsi": "S5",
    "parte_seconda": "P2",
}

# Title-match radio values exposed by the search form.
_TIPO_RICERCA_DEFAULT = "ALL_WORDS"


@dataclass
class AttoResult:
    codice_redazionale: str          # e.g. "26A02808"
    data_pubblicazione: str          # YYYY-MM-DD
    title: str = ""                  # subject / oggetto of the atto
    emettitore: str = ""             # issuer (e.g. "MINISTERO ...")
    tipo: str = ""                   # provvedimento type (e.g. "DECRETO")
    riferimento: str = ""            # e.g. "(GU n.105 del 8-5-2026)"
    eli_url: str = ""                # ELI permalink
    pub_date: str = ""               # RFC822 -> ISO (RSS only)


@dataclass
class AttoDetail:
    codice_redazionale: str
    data_pubblicazione: str
    serie: str
    title: str = ""
    emettitore: str = ""
    tipo: str = ""                   # eli:type_document
    data_documento: str = ""         # eli:date_document
    data_pubblicazione_eli: str = "" # eli:date_publication
    eli_url: str = ""
    text: str = ""
    metadata_only: bool = False
    article_urls: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# URL builders
# ---------------------------------------------------------------------------

def _eli_atto_url(data_pub: str, codice: str) -> str:
    """ELI permalink for a single atto. ``data_pub`` is YYYY-MM-DD."""
    y, m, d = data_pub.split("-")
    return f"{_BASE}/eli/id/{y}/{m}/{d}/{codice}/sg"


def _detail_url(serie_path: str, data_pub: str, codice: str) -> str:
    return (
        f"{_BASE}/atto/{serie_path}/caricaDettaglioAtto/originario"
        f"?atto.dataPubblicazioneGazzetta={data_pub}&atto.codiceRedazionale={codice}"
    )


def _menu_url(serie_path: str, data_pub: str, codice: str) -> str:
    return (
        f"{_BASE}/atto/vediMenuHTML"
        f"?atto.dataPubblicazioneGazzetta={data_pub}&atto.codiceRedazionale={codice}"
        f"&tipoSerie={serie_path}&tipoVigenza=originario"
    )


def _sommario_url(data_pub: str, numero_gazzetta: str) -> str:
    y, m, d = data_pub.split("-")
    return f"{_BASE}/eli/gu/{y}/{m}/{d}/{numero_gazzetta}/sg"


_DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")


def pdf_url(data_pub: str, numero_gazzetta: str) -> str:
    """Official PDF URL for a whole gazzetta. ``data_pub`` is YYYY-MM-DD."""
    m = _DATE_RE.match(data_pub.strip())
    if not m:
        raise ValueError(f"data_pubblicazione attesa in formato YYYY-MM-DD, ricevuto: {data_pub!r}")
    y, mo, d = m.group(1), m.group(2), m.group(3)
    return f"{_BASE}/eli/gu/{y}/{mo}/{d}/{numero_gazzetta}/sg/pdf"


# ---------------------------------------------------------------------------
# Regex / parsing helpers
# ---------------------------------------------------------------------------

# ELI RDFa is emitted as <meta ... property="eli:X" content="..."/> or resource="...#TOKEN".
_ELI_LOCAL_RE = re.compile(r'property="eli:id_local"\s+content="(?P<v>[A-Z0-9]+)"', re.IGNORECASE)
_ELI_DATE_DOC_RE = re.compile(r'property="eli:date_document"\s+content="(?P<v>[0-9-]+)"', re.IGNORECASE)
_ELI_DATE_PUB_RE = re.compile(r'property="eli:date_publication"\s+content="(?P<v>[0-9-]+)"', re.IGNORECASE)
_ELI_TYPE_RE = re.compile(r'property="eli:type_document"\s+resource="[^"#]*#(?P<v>[A-Z0-9_]+)"', re.IGNORECASE)
_ELI_PASSED_RE = re.compile(r'property="eli:passed_by"\s+resource="[^"#]*#(?P<v>[A-Z0-9_]+)"', re.IGNORECASE)
_CODICE_IN_TITLE_RE = re.compile(r"\(([0-9]{2}[A-Z][0-9]{4,6})\)")
_ELI_ID_FROM_LINK_RE = re.compile(r"/eli/id/(\d{4})/(\d{2})/(\d{2})/([A-Z0-9]+)/", re.IGNORECASE)


def _clean_text(value: str) -> str:
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def _build_search_data(
    *,
    titolo: str = "",
    testo: str = "",
    numero_provvedimento: str = "",
    codice_tipo_provvedimento: str = "",
    descrizione_tipo_provvedimento: str = "",
    codice_emettitore: str = "",
    descrizione_emettitore: str = "",
    codice_materia: str = "",
    descrizione_materia: str = "",
    anno_da: str = "",
    anno_a: str = "",
) -> dict:
    """Build the COMPLETE search form payload.

    Every field must be present (even if empty) or the Spring controller returns
    HTTP 500. ``tipoRicercaTitolo`` / ``tipoRicercaTesto`` use the form radio
    values (``ALL_WORDS`` by default).
    """
    return {
        "numeroProvvedimento": numero_provvedimento,
        "giornoProvvedimento": "",
        "meseProvvedimento": "",
        "annoProvvedimento": "",
        "attiNumerati": "false",
        "descrizioneTipoProvvedimento": descrizione_tipo_provvedimento,
        "codiceTipoProvvedimento": codice_tipo_provvedimento,
        "descrizioneEmettitore": descrizione_emettitore,
        "codiceEmettitore": codice_emettitore,
        "descrizioneMateria": descrizione_materia,
        "codiceMateria": codice_materia,
        "tipoRicercaTitolo": _TIPO_RICERCA_DEFAULT,
        "titolo": titolo,
        "titoloNot": "",
        "tipoRicercaTesto": _TIPO_RICERCA_DEFAULT,
        "testo": testo,
        "testoNot": "",
        "giornoPubblicazioneDa": "",
        "mesePubblicazioneDa": "",
        "annoPubblicazioneDa": anno_da,
        "giornoPubblicazioneA": "",
        "mesePubblicazioneA": "",
        "annoPubblicazioneA": anno_a,
        "cerca": "cerca",
    }


def _parse_rss(xml: str) -> list[AttoResult]:
    """Parse an RSS feed into AttoResult list (latest atti)."""
    soup = BeautifulSoup(xml, "xml")
    results: list[AttoResult] = []

    for item in soup.find_all("item"):
        link_tag = item.find("link")
        link = link_tag.get_text(strip=True) if link_tag else ""
        m = _ELI_ID_FROM_LINK_RE.search(link)
        if not m:
            continue
        y, mo, d, codice = m.group(1), m.group(2), m.group(3), m.group(4)
        data_pub = f"{y}-{mo}-{d}"

        title_tag = item.find("title")
        rss_title = title_tag.get_text(strip=True) if title_tag else ""
        # title is "ISSUER - TYPE date" — split on first " - " for issuer.
        emettitore = ""
        tipo = ""
        if " - " in rss_title:
            emettitore, rest = rss_title.split(" - ", 1)
            tipo = rest.strip()
        else:
            tipo = rss_title

        desc_tag = item.find("encoded") or item.find("description")
        subject = _clean_text(desc_tag.get_text(" ", strip=True)) if desc_tag else ""
        # strip the trailing "(codice)" marker from the subject for readability.
        subject = _CODICE_IN_TITLE_RE.sub("", subject).strip()

        pub_iso = ""
        pubdate_tag = item.find("pubDate")
        if pubdate_tag:
            try:
                pub_iso = parsedate_to_datetime(pubdate_tag.get_text(strip=True)).strftime("%Y-%m-%d")
            except (TypeError, ValueError):
                pub_iso = ""

        results.append(AttoResult(
            codice_redazionale=codice.upper(),
            data_pubblicazione=data_pub,
            title=subject,
            emettitore=emettitore.strip(),
            tipo=tipo.strip(),
            eli_url=f"{_BASE}/eli/id/{y}/{mo}/{d}/{codice}/SG",
            pub_date=pub_iso,
        ))

    return results


def _parse_search_results(html: str) -> list[AttoResult]:
    """Parse the parametric-search results page.

    Each result is a ``<span class="risultato">`` carrying two anchors to the
    same ``caricaDettaglioAtto`` URL (type span + title text), optionally
    preceded by ``<span class="emettitore">``.
    """
    soup = BeautifulSoup(html, "lxml")
    results: list[AttoResult] = []
    current_emettitore = ""

    container = soup.find("div", class_="risultati_ricerca") or soup
    for node in container.descendants:
        if getattr(node, "name", None) != "span":
            continue
        classes = node.get("class") or []
        if "emettitore" in classes:
            current_emettitore = node.get_text(strip=True)
            continue
        if "risultato" not in classes:
            continue

        link = node.find("a", href=True)
        if not link or "caricaDettaglioAtto" not in link.get("href", ""):
            continue
        href = link["href"]
        data_m = re.search(r"dataPubblicazioneGazzetta=([0-9-]+)", href)
        cod_m = re.search(r"codiceRedazionale=([A-Z0-9]+)", href)
        if not (data_m and cod_m):
            continue

        # tipo: the first anchor's <span class="data"> (collapse all whitespace —
        # the GU markup pads "DECRETO" + date across several blank lines)
        tipo = ""
        data_span = node.find("span", class_="data")
        if data_span:
            tipo = re.sub(r"\s+", " ", data_span.get_text(" ", strip=True)).strip()

        # riferimento: <span class="riferimento">(GU n... del ...)</span>
        riferimento = ""
        rif_span = node.find("span", class_="riferimento")
        if rif_span:
            riferimento = rif_span.get_text(" ", strip=True)

        # title: the second anchor's text (the one that is NOT just the type span)
        title = ""
        for a in node.find_all("a", href=True):
            if a.find("span", class_="data"):
                continue
            title = a.get_text(" ", strip=True)
            if title:
                break
        if rif_span and riferimento:
            title = title.replace(riferimento, "").strip()
        title = _CODICE_IN_TITLE_RE.sub("", title)
        title = _clean_text(title)

        data_pub = data_m.group(1)
        codice = cod_m.group(1).upper()
        y, mo, d = data_pub.split("-")
        results.append(AttoResult(
            codice_redazionale=codice,
            data_pubblicazione=data_pub,
            title=title,
            emettitore=current_emettitore,
            tipo=tipo,
            riferimento=riferimento,
            eli_url=f"{_BASE}/eli/id/{y}/{mo}/{d}/{codice}/SG",
        ))

    return results


def _search_result_count(html: str) -> int:
    m = re.search(r"Risultati della ricerca:\s*([\d.]+)\s*atti", html)
    if m:
        return int(m.group(1).replace(".", ""))
    return 0


def _parse_eli_metadata(html: str) -> dict:
    """Extract ELI RDFa metadata from an atto head."""
    out: dict[str, str] = {}
    for key, rx in (
        ("id_local", _ELI_LOCAL_RE),
        ("date_document", _ELI_DATE_DOC_RE),
        ("date_publication", _ELI_DATE_PUB_RE),
        ("type_document", _ELI_TYPE_RE),
        ("passed_by", _ELI_PASSED_RE),
    ):
        m = rx.search(html)
        if m:
            out[key] = m.group("v")
    return out


def _parse_atto_header(html: str) -> tuple[str, str, str]:
    """Extract (emettitore, tipo, oggetto) from the atto detail body.

    The header block sits in ``div.testo_atto`` / page top. We read the first
    visible header lines: issuer (upper-case), provvedimento line, then subject.
    """
    soup = BeautifulSoup(html, "lxml")
    emettitore = tipo = oggetto = ""

    em = soup.find(class_="emettitore")
    if em:
        emettitore = em.get_text(" ", strip=True)

    tip = soup.find(class_="tipo_provvedimento") or soup.find(class_="tipoProvvedimento")
    if tip:
        tipo = tip.get_text(" ", strip=True)

    ogg = soup.find(class_="titoloAtto") or soup.find(class_="titolo_atto")
    if ogg:
        oggetto = _clean_text(ogg.get_text(" ", strip=True))

    return emettitore, tipo, oggetto


def _parse_menu_article_urls(html: str) -> list[str]:
    """Harvest the exact caricaArticolo URLs from a vediMenuHTML page."""
    soup = BeautifulSoup(html, "lxml")
    urls: list[str] = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "caricaArticolo?" not in href:
            continue
        href = href.split("#", 1)[0]
        full = href if href.startswith("http") else _BASE + href
        if full not in seen:
            seen.add(full)
            urls.append(full)
    return urls


def _parse_article_text(html: str) -> str:
    """Extract article body text from a caricaArticolo page."""
    soup = BeautifulSoup(html, "lxml")
    body = soup.find(class_="dettaglio_atto_testo")
    if not body:
        return ""
    for tag in body(["script", "style"]):
        tag.decompose()
    return _clean_text(body.get_text("\n", strip=True))


def _parse_sommario(html: str) -> tuple[str, list[AttoResult]]:
    """Parse a gazzetta sommario page. Returns (heading, atti)."""
    soup = BeautifulSoup(html, "lxml")
    heading = ""
    h = soup.find(class_="testata") or soup.find("h2") or soup.find("h1")
    if h:
        heading = h.get_text(" ", strip=True)

    atti: list[AttoResult] = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "caricaDettaglioAtto" not in href:
            continue
        data_m = re.search(r"dataPubblicazioneGazzetta=([0-9-]+)", href)
        cod_m = re.search(r"codiceRedazionale=([A-Z0-9]+)", href)
        if not (data_m and cod_m):
            continue
        codice = cod_m.group(1).upper()
        if codice in seen:
            continue
        seen.add(codice)
        title = _CODICE_IN_TITLE_RE.sub("", a.get_text(" ", strip=True)).strip()
        title = _clean_text(title)
        data_pub = data_m.group(1)
        y, mo, d = data_pub.split("-")
        atti.append(AttoResult(
            codice_redazionale=codice,
            data_pubblicazione=data_pub,
            title=title,
            eli_url=f"{_BASE}/eli/id/{y}/{mo}/{d}/{codice}/SG",
        ))
    return heading, atti


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------

def format_result(atto: AttoResult) -> str:
    """Format a single AttoResult as a markdown block."""
    header = atto.tipo or "Atto"
    if atto.emettitore:
        header = f"{atto.emettitore} — {header}"
    lines = [f"### {header}"]
    if atto.title:
        lines.append(f"**Oggetto**: {atto.title[:400]}")
    lines.append(f"**Codice redazionale**: {atto.codice_redazionale}")
    lines.append(f"**Pubblicazione**: {atto.data_pubblicazione}")
    if atto.riferimento:
        lines.append(f"**Riferimento**: {atto.riferimento}")
    if atto.eli_url:
        lines.append(f"**Link**: [{atto.codice_redazionale}]({atto.eli_url})")
    return "\n".join(lines)


def format_detail(detail: AttoDetail) -> str:
    """Format an AttoDetail (metadata + optional full text) as markdown."""
    title = detail.title or f"Atto {detail.codice_redazionale}"
    lines = [f"# {title}"]
    if detail.emettitore:
        lines.append(f"**Emettitore**: {detail.emettitore}")
    if detail.tipo:
        lines.append(f"**Tipo**: {detail.tipo}")
    if detail.data_documento:
        lines.append(f"**Data atto**: {detail.data_documento}")
    pub = detail.data_pubblicazione_eli or detail.data_pubblicazione
    if pub:
        lines.append(f"**Pubblicazione**: {pub}")
    lines.append(f"**Codice redazionale**: {detail.codice_redazionale}")
    if detail.eli_url:
        lines.append(f"**Link**: [{detail.codice_redazionale}]({detail.eli_url})")
    lines.append("")

    if detail.metadata_only:
        lines.append("*[Solo metadati richiesti — testo non recuperato]*")
        return "\n".join(lines)

    text = detail.text or ""
    truncated = len(text) > _MAX_TEXT_LENGTH
    body = text[:_MAX_TEXT_LENGTH] if truncated else text
    lines.append(body)
    if truncated:
        lines.append(
            f"\n---\n*[Testo troncato a {_MAX_TEXT_LENGTH} caratteri su {len(text)} totali]*"
        )
    return "\n".join(lines)


def format_sommario(heading: str, atti: list[AttoResult]) -> str:
    """Format a gazzetta sommario as markdown."""
    lines = [f"# {heading or 'Sommario Gazzetta Ufficiale'}", ""]
    lines.append(f"**Atti**: {len(atti)}\n")
    for atto in atti:
        title = atto.title or atto.codice_redazionale
        lines.append(f"- **{atto.codice_redazionale}** — {title[:300]}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Network entry points
# ---------------------------------------------------------------------------

async def fetch_latest(rss_code: str, rows: int = 10) -> list[AttoResult]:
    """Read the RSS feed for the given serie code (SG, S1.. , P2)."""
    url = f"{_BASE}/rss/{rss_code}"
    async with httpx.AsyncClient(
        timeout=_TIMEOUT, headers=_RSS_HEADERS, follow_redirects=True
    ) as client:
        resp = await retry_request(client, "GET", url)
        return _parse_rss(resp.text)[:rows]


async def search_atti(
    serie_path: str,
    *,
    titolo: str = "",
    testo: str = "",
    numero_provvedimento: str = "",
    codice_tipo_provvedimento: str = "",
    descrizione_tipo_provvedimento: str = "",
    codice_emettitore: str = "",
    descrizione_emettitore: str = "",
    codice_materia: str = "",
    descrizione_materia: str = "",
    anno_da: str = "",
    anno_a: str = "",
    rows: int = 20,
) -> tuple[int, list[AttoResult]]:
    """Parametric / full-text search. Returns (total_count, results)."""
    rows = min(rows, 100)
    data = _build_search_data(
        titolo=titolo,
        testo=testo,
        numero_provvedimento=numero_provvedimento,
        codice_tipo_provvedimento=codice_tipo_provvedimento,
        descrizione_tipo_provvedimento=descrizione_tipo_provvedimento,
        codice_emettitore=codice_emettitore,
        descrizione_emettitore=descrizione_emettitore,
        codice_materia=codice_materia,
        descrizione_materia=descrizione_materia,
        anno_da=anno_da,
        anno_a=anno_a,
    )

    results: list[AttoResult] = []
    total = 0
    page = 0  # the form action is 0-based

    async with httpx.AsyncClient(
        timeout=_TIMEOUT, headers=_HEADERS, follow_redirects=True
    ) as client:
        # Seed the jsessionid on the same client first.
        await retry_request(client, "GET", _BASE + _RICERCA_SEED_PATH)

        while len(results) < rows:
            url = f"{_BASE}/do/ricerca/atto/{serie_path}/originario/{page}"
            resp = await retry_request(client, "POST", url, data=data)
            if page == 0:
                total = _search_result_count(resp.text)
            page_results = _parse_search_results(resp.text)
            if not page_results:
                break
            results.extend(page_results)
            page += 1

    if total == 0:
        total = len(results)
    return total, results[:rows]


async def fetch_atto(
    serie_path: str,
    data_pubblicazione: str,
    codice_redazionale: str,
    metadata_only: bool = False,
) -> AttoDetail:
    """Fetch one atto: ELI metadata + (optionally) the assembled article text."""
    detail = AttoDetail(
        codice_redazionale=codice_redazionale,
        data_pubblicazione=data_pubblicazione,
        serie=serie_path,
        eli_url=_eli_atto_url(data_pubblicazione, codice_redazionale),
        metadata_only=metadata_only,
    )

    async with httpx.AsyncClient(
        timeout=_TIMEOUT, headers=_HEADERS, follow_redirects=True
    ) as client:
        # 1. ELI permalink head -> RDFa metadata + body header.
        head_resp = await retry_request(client, "GET", detail.eli_url)
        meta = _parse_eli_metadata(head_resp.text)
        detail.tipo = meta.get("type_document", "")
        detail.emettitore = meta.get("passed_by", "")
        detail.data_documento = meta.get("date_document", "")
        detail.data_pubblicazione_eli = meta.get("date_publication", "")

        em, tip, ogg = _parse_atto_header(head_resp.text)
        detail.emettitore = em or detail.emettitore
        detail.tipo = tip or detail.tipo
        detail.title = ogg

        if metadata_only:
            return detail

        # 2. Menu page -> harvest exact caricaArticolo URLs.
        menu_resp = await retry_request(
            client, "GET", _menu_url(serie_path, data_pubblicazione, codice_redazionale)
        )
        article_urls = _parse_menu_article_urls(menu_resp.text)
        detail.article_urls = article_urls

        # 3. Fetch each article and assemble.
        parts: list[str] = []
        for art_url in article_urls:
            art_resp = await retry_request(client, "GET", art_url)
            art_text = _parse_article_text(art_resp.text)
            if art_text:
                parts.append(art_text)
        detail.text = "\n\n".join(parts)

    return detail


async def fetch_sommario(
    data_pubblicazione: str,
    numero_gazzetta: str,
) -> tuple[str, list[AttoResult]]:
    """Fetch a gazzetta sommario. Returns (heading, atti)."""
    url = _sommario_url(data_pubblicazione, numero_gazzetta)
    async with httpx.AsyncClient(
        timeout=_TIMEOUT, headers=_HEADERS, follow_redirects=True
    ) as client:
        resp = await retry_request(client, "GET", url)
        return _parse_sommario(resp.text)

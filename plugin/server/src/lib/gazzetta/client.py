"""Client for the Gazzetta Ufficiale della Repubblica Italiana.

Endpoint: https://www.gazzettaufficiale.it (the ``www`` host is REQUIRED).

The site is a Java/Spring application that uses a ``jsessionid`` cookie. There is
NO XML / Akoma Ntoso layer for the Gazzetta — only HTML pages, ELI RDFa metadata
in the page head, RSS feeds for the "latest" view, and an official PDF.

Access strategy (mirrors the recon mapping):

* "latest" → RSS feed ``/rss/{SG|S1..S5|P2}`` (stable, no session needed).
* parametric / full-text search → GET ``/eli/ricerca`` to seed the jsessionid on
  the SAME client, then POST ``/do/ricerca/atto/{serie}/originario/{page}`` with
  the COMPLETE field set (omitting any field returns HTTP 500). Result pages are
  numbered from 1 (page 0 renders the same page as page 1). A search with exactly
  ONE hit is answered with a redirect to that atto's ``caricaDettaglioAtto`` page
  instead of a result list.
* fetch one atto → ELI permalink ``/eli/id/{yyyy}/{mm}/{dd}/{codice}/{seg}`` (RDFa
  head + ``h2/h3.consultazione`` with estremi, oggetto and GU reference) +
  ``vediMenuHTML`` (harvest the exact ``caricaArticolo`` URLs — building them
  blindly returns a "in fase di caricamento" stub; the special series carry the
  text inline in ``div.stampami`` and have no such links) + the harvested article
  pages (text lives in ``div.dettaglio_atto_testo``).
* sommario of a gazzetta → ``/eli/gu/{yyyy}/{mm}/{dd}/{numeroGazzetta}/{seg}``.
* PDF → ``/eli/gu/{yyyy}/{mm}/{dd}/{numeroGazzetta}/{seg}/pdf`` (URL returned, never
  inlined).

``{seg}`` is the ELI segment of the series (``ELI_SEGMENT``): sg, s1 (Corte
costituzionale), s2 (Unione europea), s3 (Regioni), s4 (Concorsi ed esami), s5
(Contratti pubblici), p2 (Parte seconda). Asking a special-series atto or fascicolo
with ``sg`` returns an empty page (or ``/gazzetta/pdf/notFound`` for the PDF).
"""

import re
from dataclasses import dataclass, field
from email.utils import parsedate_to_datetime

import httpx
from bs4 import BeautifulSoup

from src.lib._paging import page, resume_hint

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
_PAGE_SIZE = 100  # results per page of the parametric search
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

# Human-friendly serie keys -> RSS feed code. The numbering is the official one
# printed in the channel titles of https://www.gazzettaufficiale.it/rss/{code}:
# 1a Corte Costituzionale, 2a Unione Europea, 3a Regioni, 4a Concorsi ed esami,
# 5a Contratti Pubblici (read on 2026-09-29).
RSS_CODE: dict[str, str] = {
    "serie_generale": "SG",
    "corte_costituzionale": "S1",
    "unione_europea": "S2",
    "regioni": "S3",
    "concorsi": "S4",
    "contratti": "S5",
    "parte_seconda": "P2",
}

# Serie key -> ELI path segment (same numbering as the RSS codes, lower case).
# /eli/id/{y}/{m}/{d}/{codice}/{seg} and /eli/gu/{y}/{m}/{d}/{numero}/{seg}[/pdf]
# answer only for the atto's own series.
ELI_SEGMENT: dict[str, str] = {code_key: code.lower() for code_key, code in RSS_CODE.items()}

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
    estremi: str = ""                # e.g. "DECRETO LEGISLATIVO 10 ottobre 2022, n. 149"
    riferimento: str = ""            # e.g. "(GU Serie Generale n.243 del 17-10-2022 ...)"
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

_DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")


def _split_date(data_pub: str) -> tuple[str, str, str]:
    """Split a YYYY-MM-DD date, or raise a readable ValueError."""
    m = _DATE_RE.match((data_pub or "").strip())
    if not m:
        raise ValueError(
            f"data_pubblicazione attesa in formato YYYY-MM-DD, ricevuto: {data_pub!r}"
        )
    return m.group(1), m.group(2), m.group(3)


def _eli_segment(serie_path: str) -> str:
    """ELI path segment of a series (unknown keys fall back to the Serie generale)."""
    return ELI_SEGMENT.get(serie_path, "sg")


def _eli_atto_url(data_pub: str, codice: str, serie_path: str = "serie_generale") -> str:
    """ELI permalink for a single atto. ``data_pub`` is YYYY-MM-DD."""
    y, m, d = _split_date(data_pub)
    return f"{_BASE}/eli/id/{y}/{m}/{d}/{codice}/{_eli_segment(serie_path)}"


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


def _sommario_url(data_pub: str, numero_gazzetta: str, serie_path: str = "serie_generale") -> str:
    y, m, d = _split_date(data_pub)
    return f"{_BASE}/eli/gu/{y}/{m}/{d}/{numero_gazzetta}/{_eli_segment(serie_path)}"


def pdf_url(data_pub: str, numero_gazzetta: str, serie_path: str = "serie_generale") -> str:
    """Official PDF URL for a whole gazzetta of the given series.

    ``data_pub`` is YYYY-MM-DD. The ELI segment must be the series' own (s1..s5,
    p2, sg): a special-series fascicolo asked with ``sg`` is redirected by the site
    to its "pdf non trovato" page.
    """
    y, mo, d = _split_date(data_pub)
    return f"{_BASE}/eli/gu/{y}/{mo}/{d}/{numero_gazzetta}/{_eli_segment(serie_path)}/pdf"


# ---------------------------------------------------------------------------
# Regex / parsing helpers
# ---------------------------------------------------------------------------

# ELI RDFa is emitted as <meta ... property="eli:X" content="..."/> or resource="...#TOKEN".
_ELI_LOCAL_RE = re.compile(r'property="eli:id_local"\s+content="(?P<v>[A-Z0-9]+)"', re.IGNORECASE)
_ELI_DATE_DOC_RE = re.compile(r'property="eli:date_document"\s+content="(?P<v>[0-9-]+)"', re.IGNORECASE)
_ELI_DATE_PUB_RE = re.compile(r'property="eli:date_publication"\s+content="(?P<v>[0-9-]+)"', re.IGNORECASE)
_ELI_TYPE_RE = re.compile(r'property="eli:type_document"\s+resource="[^"#]*#(?P<v>[A-Z0-9_]+)"', re.IGNORECASE)
_ELI_PASSED_RE = re.compile(r'property="eli:passed_by"\s+resource="[^"#]*#(?P<v>[A-Z0-9_]+)"', re.IGNORECASE)
# "(26A02808)", and the 2a Serie speciale codes "(26CE2412)" (two letters).
_CODICE_IN_TITLE_RE = re.compile(r"\(([0-9]{2}[A-Z]{1,2}[0-9]{4,6})\)")
_ELI_ID_FROM_LINK_RE = re.compile(
    r"/eli/id/(\d{4})/(\d{2})/(\d{2})/([A-Z0-9]+)/([A-Za-z0-9]+)", re.IGNORECASE,
)
# The 2a Serie speciale (Unione europea) feed links to the paginated PDF, not to an ELI page.
_PDFPAG_DATE_RE = re.compile(r"dataPubblicazioneGazzetta=(\d{4})(\d{2})(\d{2})")
_SERIE_FROM_HREF_RE = re.compile(r"/atto/([a-z_]+)/caricaDettaglioAtto")


def _clean_text(value: str) -> str:
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def _one_line(value: str) -> str:
    """Collapse every run of whitespace (the GU pads titles with blanks and newlines)."""
    return re.sub(r"\s+", " ", value).strip()


def _eli_id_url(data_pub: str, codice: str, serie_path: str = "serie_generale") -> str:
    """ELI permalink of an atto, with the ELI segment of its own series."""
    y, mo, d = _split_date(data_pub)
    return f"{_BASE}/eli/id/{y}/{mo}/{d}/{codice}/{_eli_segment(serie_path)}"


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
    """Parse an RSS feed into AttoResult list (latest atti).

    The feed link is kept as the atto's permalink, with its own series segment
    (``/SG``, ``/S1``, ``/S3``...): rebuilding it with ``/SG`` opens a page without
    the atto for the special series. The 2a Serie speciale (Unione europea) feed
    links each item to the paginated PDF instead, so the code comes from the
    trailing ``(26CE2412)`` of the description and the date from the link.
    """
    soup = BeautifulSoup(xml, "xml")
    results: list[AttoResult] = []

    for item in soup.find_all("item"):
        link_tag = item.find("link")
        link = link_tag.get_text(strip=True) if link_tag else ""

        title_tag = item.find("title")
        rss_title = title_tag.get_text(strip=True) if title_tag else ""
        desc_tag = item.find("encoded") or item.find("description")
        raw_subject = desc_tag.get_text(" ", strip=True) if desc_tag else ""

        m = _ELI_ID_FROM_LINK_RE.search(link)
        if m:
            y, mo, d, codice = m.group(1), m.group(2), m.group(3), m.group(4)
            eli_url = link.replace("http://", "https://", 1)
        else:
            pdf_m = _PDFPAG_DATE_RE.search(link)
            codice_m = _CODICE_IN_TITLE_RE.search(raw_subject)
            if not (pdf_m and codice_m):
                continue
            y, mo, d = pdf_m.group(1), pdf_m.group(2), pdf_m.group(3)
            codice = codice_m.group(1)
            eli_url = link.replace("http://", "https://", 1)
        data_pub = f"{y}-{mo}-{d}"

        # title is "ISSUER - TYPE date" — split on first " - " for issuer.
        emettitore = ""
        tipo = ""
        if " - " in rss_title:
            emettitore, rest = rss_title.split(" - ", 1)
            tipo = rest.strip()
        else:
            tipo = rss_title

        subject = _one_line(raw_subject)
        # strip the trailing "(codice)" marker from the subject for readability, and the
        # filler dots the special-series feeds put where they cut a long text.
        subject = _CODICE_IN_TITLE_RE.sub("", subject).strip()
        subject = re.sub(r"\s*\.{5,}$", " [...]", subject)

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
            eli_url=eli_url,
            pub_date=pub_iso,
        ))

    return results


def _parse_search_results(html: str) -> list[AttoResult]:
    """Parse the parametric-search results page (also used by the sommario page).

    Each result is a ``<span class="risultato">`` carrying two anchors to the
    same ``caricaDettaglioAtto`` URL (type span + title text), optionally
    preceded by ``<span class="emettitore">``. A ``<span class="rubrica">`` (sommario
    section heading) starts a new block, so it resets the issuer. The series comes
    from the anchor path (``/atto/{serie}/caricaDettaglioAtto``).
    """
    soup = BeautifulSoup(html, "lxml")
    results: list[AttoResult] = []
    current_emettitore = ""

    container = soup.find("div", class_="risultati_ricerca") or soup
    for node in container.descendants:
        if getattr(node, "name", None) != "span":
            continue
        classes = node.get("class") or []
        if "rubrica" in classes:
            current_emettitore = ""
            continue
        if "emettitore" in classes:
            current_emettitore = _one_line(node.get_text(strip=True))
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
        serie_m = _SERIE_FROM_HREF_RE.search(href)
        serie_path = serie_m.group(1) if serie_m else "serie_generale"

        # tipo: the first anchor's <span class="data"> (collapse all whitespace —
        # the GU markup pads "DECRETO" + date across several blank lines)
        tipo = ""
        data_span = node.find("span", class_="data")
        if data_span:
            tipo = _one_line(data_span.get_text(" ", strip=True))

        # riferimento: <span class="riferimento">(GU n... del ...)</span>
        riferimento = ""
        rif_span = node.find("span", class_="riferimento")
        if rif_span:
            riferimento = _one_line(rif_span.get_text(""))

        # title: the second anchor's text (the one that is NOT just the type span),
        # without the riferimento and the "Pag. N" spans it carries.
        title = ""
        for a in node.find_all("a", href=True):
            if a.find("span", class_="data"):
                continue
            for extra in a.find_all("span", class_=("riferimento", "pagina")):
                extra.decompose()
            title = a.get_text("")
            if title.strip():
                break
        title = _one_line(title)
        title = _CODICE_IN_TITLE_RE.sub("", title)
        title = _clean_text(title)

        data_pub = data_m.group(1)
        codice = cod_m.group(1).upper()
        results.append(AttoResult(
            codice_redazionale=codice,
            data_pubblicazione=data_pub,
            title=title,
            emettitore=current_emettitore,
            tipo=tipo,
            riferimento=riferimento,
            eli_url=_eli_id_url(data_pub, codice, serie_path),
        ))

    return results


def _parse_detail_redirect(html: str, url: str) -> list[AttoResult]:
    """Build the single result of a search the site answered with the atto's own page.

    A search with exactly one hit is not rendered as a list: the site redirects to
    ``/atto/{serie}/caricaDettaglioAtto/originario?atto.dataPubblicazioneGazzetta=...
    &atto.codiceRedazionale=...``. The code, the date and the series come from that
    URL; the estremi, the oggetto and the GU reference from the page header.
    """
    data_m = re.search(r"dataPubblicazioneGazzetta=([0-9-]+)", url)
    cod_m = re.search(r"codiceRedazionale=([A-Z0-9]+)", url)
    if not (data_m and cod_m):
        return []
    serie_m = _SERIE_FROM_HREF_RE.search(url)
    serie_path = serie_m.group(1) if serie_m else "serie_generale"
    estremi, oggetto, riferimento = _parse_atto_header(html)
    codice = cod_m.group(1).upper()
    data_pub = data_m.group(1)
    return [AttoResult(
        codice_redazionale=codice,
        data_pubblicazione=data_pub,
        title=oggetto,
        tipo=estremi,
        riferimento=riferimento,
        eli_url=_eli_id_url(data_pub, codice, serie_path),
    )]


# "Risultati della ricerca: 223 atti" (short lists) or, for long ones, "Sono stati
# trovati 715 atti.(È possibile visualizzare solo i primi 500 atti)".
_COUNT_RES = (
    re.compile(r"Risultati della ricerca:\s*([\d.]+)\s*atti"),
    re.compile(r"Sono stati trovati\s*([\d.]+)\s*atti"),
)


def _search_result_count(html: str) -> int:
    for rx in _COUNT_RES:
        m = rx.search(html)
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
    """Extract (estremi, oggetto, riferimento) from an atto page.

    The header of the ELI / caricaDettaglioAtto page is ``h2.consultazione`` (type,
    date and number, e.g. "DECRETO LEGISLATIVO 10 ottobre 2022, n. 149") followed by
    ``h3.consultazione`` (the oggetto, ending with the "(codice)") that contains
    ``span.riferimento`` (the GU reference).
    """
    soup = BeautifulSoup(html, "lxml")
    estremi = oggetto = riferimento = ""

    h2 = soup.find("h2", class_="consultazione")
    if h2:
        estremi = _one_line(h2.get_text(" ", strip=True))

    h3 = soup.find("h3", class_="consultazione")
    if h3:
        rif = h3.find("span", class_="riferimento")
        if rif:
            riferimento = _one_line(rif.get_text(""))
            rif.decompose()
        oggetto = _CODICE_IN_TITLE_RE.sub("", _one_line(h3.get_text(""))).strip()

    return estremi, oggetto, riferimento


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


def _parse_menu_inline_text(html: str) -> str:
    """Extract the atto text carried inline by a vediMenuHTML page.

    The special series (and any atto without articles) have no ``caricaArticolo``
    links: the whole text sits in ``div.stampami`` (a ``<pre>`` block).
    """
    soup = BeautifulSoup(html, "lxml")
    body = soup.find("div", class_="stampami")
    if not body:
        return ""
    for tag in body(["script", "style"]):
        tag.decompose()
    return _clean_text(body.get_text("\n", strip=True))


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
    """Parse a gazzetta sommario page. Returns (heading, atti).

    The heading is the fascicolo's ``div.intestazione`` ("Serie Generale n. 205 del
    4-9-2018"); each atto has the same ``span.risultato`` + ``span.emettitore``
    structure as a search result (estremi, oggetto, issuer), so the result parser is
    shared. Duplicate codes are kept once.
    """
    soup = BeautifulSoup(html, "lxml")
    heading = ""
    box = soup.find(class_="intestazione")
    if box:
        heading = _one_line(box.get_text(""))
    if not heading:
        h = soup.find("h2") or soup.find("h1")
        if h:
            heading = h.get_text(" ", strip=True)

    atti: list[AttoResult] = []
    seen: set[str] = set()
    for atto in _parse_search_results(html):
        if atto.codice_redazionale in seen:
            continue
        seen.add(atto.codice_redazionale)
        atti.append(atto)
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


def format_detail(detail: AttoDetail, da_carattere: int = 1) -> str:
    """Format an AttoDetail (metadata + optional full text) as markdown.

    Positions count ``detail.text``, the assembled text of the atto. With
    ``da_carattere`` > 1 the body is the window of that text starting there.
    """
    title = detail.estremi or detail.title or f"Atto {detail.codice_redazionale}"
    lines = [f"# {title}"]
    if detail.estremi and detail.title:
        lines.append(f"**Oggetto**: {detail.title}")
    if detail.riferimento:
        lines.append(f"**Riferimento**: {detail.riferimento}")
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
    if da_carattere > 1:
        body, note = page(text, da_carattere, _MAX_TEXT_LENGTH)
        lines.append(body)
        lines.append(f"\n---\n{note}")
        return "\n".join(lines)
    truncated = len(text) > _MAX_TEXT_LENGTH
    body = text[:_MAX_TEXT_LENGTH] if truncated else text
    lines.append(body)
    if truncated:
        lines.append(
            f"\n---\n*[Testo troncato a {_MAX_TEXT_LENGTH} caratteri su {len(text)} totali: "
            f"{resume_hint(_MAX_TEXT_LENGTH + 1)}]*"
        )
    return "\n".join(lines)


def format_sommario(heading: str, atti: list[AttoResult]) -> str:
    """Format a gazzetta sommario as markdown (codice, estremi, issuer, oggetto)."""
    lines = [f"# {heading or 'Sommario Gazzetta Ufficiale'}", ""]
    lines.append(f"**Atti**: {len(atti)}\n")
    for atto in atti:
        line = f"- **{atto.codice_redazionale}** — {atto.tipo or atto.title or atto.codice_redazionale}"
        if atto.emettitore:
            line += f" ({atto.emettitore})"
        if atto.tipo and atto.title:
            line += f": {atto.title[:300]}"
        lines.append(line)
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
        resp = await retry_request(client, "GET", url, dataset="gazzetta")
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
    seen: set[str] = set()
    total = 0
    page = 1  # result pages are numbered from 1 (0 renders the same page as 1)

    async with httpx.AsyncClient(
        timeout=_TIMEOUT, headers=_HEADERS, follow_redirects=True
    ) as client:
        # Seed the jsessionid on the same client first.
        await retry_request(client, "GET", _BASE + _RICERCA_SEED_PATH, dataset="gazzetta")

        while len(results) < rows:
            url = f"{_BASE}/do/ricerca/atto/{serie_path}/originario/{page}"
            resp = await retry_request(client, "POST", url, dataset="gazzetta", data=data)
            if "caricaDettaglioAtto" in str(resp.url):
                # exactly one hit: the site answers with the atto's own page
                page_results = _parse_detail_redirect(resp.text, str(resp.url))
                total = len(page_results)
            else:
                page_results = _parse_search_results(resp.text)
                if page == 1:
                    total = _search_result_count(resp.text)
            new: list[AttoResult] = []
            for r in page_results:
                if r.codice_redazionale not in seen:
                    seen.add(r.codice_redazionale)
                    new.append(r)
            if not new:
                break
            results.extend(new)
            if len(page_results) < _PAGE_SIZE:
                break  # a short page is the last one
            page += 1

    if total < len(results):
        total = len(results)
    return total, results[:rows]


async def fetch_atto(
    serie_path: str,
    data_pubblicazione: str,
    codice_redazionale: str,
    metadata_only: bool = False,
) -> AttoDetail:
    """Fetch one atto: ELI metadata + (optionally) the assembled article text.

    The permalink and the menu use the atto's own series (``s1``..``s5``, ``p2``,
    ``sg``); for the special series the text is carried inline by ``vediMenuHTML``.
    """
    detail = AttoDetail(
        codice_redazionale=codice_redazionale,
        data_pubblicazione=data_pubblicazione,
        serie=serie_path,
        eli_url=_eli_atto_url(data_pubblicazione, codice_redazionale, serie_path),
        metadata_only=metadata_only,
    )

    async with httpx.AsyncClient(
        timeout=_TIMEOUT, headers=_HEADERS, follow_redirects=True
    ) as client:
        # 1. ELI permalink head -> RDFa metadata + body header.
        head_resp = await retry_request(client, "GET", detail.eli_url, dataset="gazzetta")
        meta = _parse_eli_metadata(head_resp.text)
        detail.tipo = meta.get("type_document", "")
        detail.emettitore = meta.get("passed_by", "")
        detail.data_documento = meta.get("date_document", "")
        detail.data_pubblicazione_eli = meta.get("date_publication", "")

        detail.estremi, detail.title, detail.riferimento = _parse_atto_header(head_resp.text)

        if metadata_only:
            return detail

        # 2. Menu page -> harvest exact caricaArticolo URLs.
        menu_resp = await retry_request(
            client, "GET", _menu_url(serie_path, data_pubblicazione, codice_redazionale),
            dataset="gazzetta",
        )
        article_urls = _parse_menu_article_urls(menu_resp.text)
        detail.article_urls = article_urls
        if not article_urls:
            # special series: no article links, the whole text is inline in the menu
            detail.text = _parse_menu_inline_text(menu_resp.text)
            return detail

        # 3. Fetch each article and assemble.
        parts: list[str] = []
        for art_url in article_urls:
            art_resp = await retry_request(client, "GET", art_url, dataset="gazzetta")
            art_text = _parse_article_text(art_resp.text)
            if art_text:
                parts.append(art_text)
        detail.text = "\n\n".join(parts)

    return detail


async def fetch_sommario(
    data_pubblicazione: str,
    numero_gazzetta: str,
    serie_path: str = "serie_generale",
) -> tuple[str, list[AttoResult]]:
    """Fetch a gazzetta sommario. Returns (heading, atti)."""
    url = _sommario_url(data_pubblicazione, numero_gazzetta, serie_path)
    async with httpx.AsyncClient(
        timeout=_TIMEOUT, headers=_HEADERS, follow_redirects=True
    ) as client:
        resp = await retry_request(client, "GET", url, dataset="gazzetta")
        return _parse_sommario(resp.text)

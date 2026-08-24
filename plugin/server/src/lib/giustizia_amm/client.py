"""Client for Giustizia Amministrativa (giustizia-amministrativa.it).

Search:    https://www.giustizia-amministrativa.it/web/guest/dcsnprr
Full text: https://mdp.giustizia-amministrativa.it/visualizza/ (XML <GA> format)

Il sito usa Liferay Portal — nessuna API pubblica JSON. Scraping HTML via BeautifulSoup.

TLS: entrambi i domini presentano una catena valida verificabile con il bundle di
certifi, quindi la verifica resta ATTIVA. Storicamente era disabilitata (come per
Italgiure, dove serve tuttora perché la sua CA non è in certifi): non reintrodurre
verify=False senza aver prima verificato che il certificato sia davvero
irrecuperabile — senza verifica un intermediario può sostituire l'XML dei
provvedimenti che il client tratta come autentici.

NOTA (issue #32) — il portale è stato riorganizzato nel 2026:
  - il vecchio path `/web/guest/-/ricerca-giurisprudenza` restituisce 404;
  - la portlet ha un id `..._INSTANCE_<hash>` che può cambiare: viene letto a
    runtime dalla pagina, mai hardcodato come unica fonte;
  - le sedi sul filo sono nomi di città ("Roma"), non più codici ("TARLAZ");
  - il testo integrale non sta più su `/mdp/atti/<file>` — quel path risponde
    200 con una pagina di errore 404, quindi va riconosciuto esplicitamente.
"""

import re
from dataclasses import dataclass, field
from urllib.parse import parse_qs, urlencode, urlparse
from xml.etree import ElementTree

import httpx

from src.lib._http import retry_request
from bs4 import BeautifulSoup

_BASE_SEARCH = "https://www.giustizia-amministrativa.it"
_BASE_MDP = "https://mdp.giustizia-amministrativa.it"
_SEARCH_PATH = "/web/guest/dcsnprr"
_DOCUMENT_PATH = "/visualizza/"

# Fallback only: the live page is the authoritative source for this id.
_PORTLET = "decisioni_pareri_web_DecisioniPareriWebPortlet_INSTANCE_XKc17mrB8J10"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": f"{_BASE_SEARCH}{_SEARCH_PATH}",
}

_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
_MAX_TEXT_LENGTH = 15000

# Friendly key -> value accepted by the portal's `sedeProvvedimenti` select.
# Regional aliases map to the main seat; second seats are addressable explicitly.
SEDI: dict[str, str] = {
    "consiglio_di_stato": "Consiglio di Stato",
    "cgars": "C.G.A.R.S",
    "tar_lazio": "Roma",
    "tar_lazio_roma": "Roma",
    "tar_lazio_latina": "Latina",
    "tar_lombardia": "Milano",
    "tar_lombardia_milano": "Milano",
    "tar_lombardia_brescia": "Brescia",
    "tar_campania": "Napoli",
    "tar_campania_napoli": "Napoli",
    "tar_campania_salerno": "Salerno",
    "tar_sicilia": "Palermo",
    "tar_sicilia_palermo": "Palermo",
    "tar_sicilia_catania": "Catania",
    "tar_veneto": "Venezia",
    "tar_piemonte": "Torino",
    "tar_emilia_romagna": "Bologna",
    "tar_emilia_romagna_bologna": "Bologna",
    "tar_emilia_romagna_parma": "Parma",
    "tar_toscana": "Firenze",
    "tar_puglia": "Bari",
    "tar_puglia_bari": "Bari",
    "tar_puglia_lecce": "Lecce",
    "tar_calabria": "Catanzaro",
    "tar_calabria_catanzaro": "Catanzaro",
    "tar_calabria_reggio": "Reggio Calabria",
    "tar_liguria": "Genova",
    "tar_sardegna": "Cagliari",
    "tar_friuli": "Trieste",
    "tar_marche": "Ancona",
    "tar_abruzzo": "L'Aquila",
    "tar_abruzzo_laquila": "L'Aquila",
    "tar_abruzzo_pescara": "Pescara",
    "tar_umbria": "Perugia",
    "tar_molise": "Campobasso",
    "tar_basilicata": "Potenza",
    "tar_trentino": "Trento",
    "tar_trentino_trento": "Trento",
    "tar_trentino_bolzano": "Bolzano",
    "tar_valle_aosta": "Aosta",
}

# `schema` code carried by each result -> human label. Also the value used to
# build the full-text URL.
_SCHEMA_LABELS: dict[str, str] = {
    "cds": "Consiglio di Stato",
    "cgagiur": "C.G.A.R.S.",
    "tar_rm": "TAR Lazio - Roma",
    "tar_lt": "TAR Lazio - Latina",
    "tar_mi": "TAR Lombardia - Milano",
    "tar_bs": "TAR Lombardia - Brescia",
    "tar_na": "TAR Campania - Napoli",
    "tar_sa": "TAR Campania - Salerno",
    "tar_pa": "TAR Sicilia - Palermo",
    "tar_ct": "TAR Sicilia - Catania",
    "tar_ve": "TAR Veneto",
    "tar_to": "TAR Piemonte",
    "tar_bo": "TAR Emilia-Romagna - Bologna",
    "tar_pr": "TAR Emilia-Romagna - Parma",
    "tar_fi": "TAR Toscana",
    "tar_ba": "TAR Puglia - Bari",
    "tar_le": "TAR Puglia - Lecce",
    "tar_cz": "TAR Calabria - Catanzaro",
    "tar_rc": "TAR Calabria - Reggio Calabria",
    "tar_ge": "TAR Liguria",
    "tar_ca": "TAR Sardegna",
    "tar_ts": "TAR Friuli-Venezia Giulia",
    "tar_an": "TAR Marche",
    "tar_aq": "TAR Abruzzo - L'Aquila",
    "tar_pe": "TAR Abruzzo - Pescara",
    "tar_pg": "TAR Umbria",
    "tar_cb": "TAR Molise",
    "tar_pz": "TAR Basilicata",
    "tar_tn": "TRGA Trentino-Alto Adige - Trento",
    "tar_bz": "TRGA Trentino-Alto Adige - Bolzano",
    "tar_ao": "TAR Valle d'Aosta",
}

_CITY_TO_SCHEMA: dict[str, str] = {
    "consiglio di stato": "cds",
    "c.g.a.r.s": "cgagiur",
    "roma": "tar_rm",
    "latina": "tar_lt",
    "milano": "tar_mi",
    "brescia": "tar_bs",
    "napoli": "tar_na",
    "salerno": "tar_sa",
    "palermo": "tar_pa",
    "catania": "tar_ct",
    "venezia": "tar_ve",
    "torino": "tar_to",
    "bologna": "tar_bo",
    "parma": "tar_pr",
    "firenze": "tar_fi",
    "bari": "tar_ba",
    "lecce": "tar_le",
    "catanzaro": "tar_cz",
    "reggio calabria": "tar_rc",
    "genova": "tar_ge",
    "cagliari": "tar_ca",
    "trieste": "tar_ts",
    "ancona": "tar_an",
    "l'aquila": "tar_aq",
    "pescara": "tar_pe",
    "perugia": "tar_pg",
    "campobasso": "tar_cb",
    "potenza": "tar_pz",
    "trento": "tar_tn",
    "bolzano": "tar_bz",
    "aosta": "tar_ao",
}

# Codes emitted by the pre-2026 portal (and still quoted by LLMs from memory).
_LEGACY_SEDE_CODES: dict[str, str] = {
    "CDS": "cds",
    "CGARS": "cgagiur",
    "TARLAZ": "tar_rm",
    "TARLOM": "tar_mi",
    "TARCAM": "tar_na",
    "TARCAMSAL": "tar_sa",
    "TARSIC": "tar_pa",
    "TARSICCAT": "tar_ct",
    "TARVEN": "tar_ve",
    "TARPIE": "tar_to",
    "TAREMI": "tar_bo",
    "TARTOS": "tar_fi",
    "TARPUG": "tar_ba",
    "TARPUGLEC": "tar_le",
    "TARCAL": "tar_cz",
    "TARCALREG": "tar_rc",
    "TARLIG": "tar_ge",
    "TARSAR": "tar_ca",
    "TARFRI": "tar_ts",
    "TARMAR": "tar_an",
    "TARABR": "tar_pe",
    "TARABRLAQ": "tar_aq",
    "TARUMB": "tar_pg",
    "TARMOL": "tar_cb",
    "TARBAS": "tar_pz",
    "TARBOL": "tar_bz",
    "TARTRETN": "tar_tn",
    "TARVDA": "tar_ao",
}

TIPI_PROVVEDIMENTO: dict[str, str] = {
    "sentenza": "Sentenza",
    "ordinanza": "Ordinanza",
    "decreto": "Decreto",
    "parere": "Parere",
    "adunanza_plenaria": "P",
    "adunanza_generale": "C",
}

# XML sections carrying the body, in reading order. `motivazione` is often empty
# and the reasoning sits in `premessa` instead — emit whichever is populated.
_EPIGRAFE_FIELDS = ("adunanza", "oggetto", "ricorrenti", "resistenti", "altro", "visto", "esaminato")
_BODY_SECTIONS = ("premessa", "motivazione", "dispositivo")


@dataclass
class ProvvedimentoResult:
    sede: str             # schema code, e.g. "cds", "tar_rm" — feeds the doc URL
    sede_label: str       # e.g. "Consiglio di Stato", "TAR Lazio - Roma"
    nrg: str              # numero registro generale (ricorso)
    tipo: str             # SENTENZA, ORDINANZA, DECRETO, PARERE
    anno: str             # year of the provvedimento
    nome_file: str        # filename on the mdp subdomain
    data_deposito: str    # DD/MM/YYYY — no longer exposed by the portal, kept ""
    oggetto: str          # snippet returned by the search engine
    numero: str = ""      # numero provvedimento, e.g. "202614035"
    sezione: str = ""     # e.g. "SEZIONE 3Q"
    ecli: str = ""        # e.g. "ECLI:IT:TARLAZ:2026:14035SENT"


def _resolve_schema(sede: str) -> str:
    """Normalise any sede spelling to the portal `schema` code."""
    if not sede:
        return ""
    raw = sede.strip()
    if raw in _SCHEMA_LABELS:
        return raw
    if raw.upper() in _LEGACY_SEDE_CODES:
        return _LEGACY_SEDE_CODES[raw.upper()]
    key = raw.lower().replace(" ", "_")
    if key in SEDI:
        return _CITY_TO_SCHEMA.get(SEDI[key].lower(), raw)
    if raw.lower() in _CITY_TO_SCHEMA:
        return _CITY_TO_SCHEMA[raw.lower()]
    return raw


def _resolve_sede_filter(sede: str) -> str:
    """Normalise any sede spelling to the value accepted by the search form."""
    if not sede:
        return ""
    raw = sede.strip()
    key = raw.lower().replace(" ", "_")
    if key in SEDI:
        return SEDI[key]
    schema = _resolve_schema(raw)
    for city, code in _CITY_TO_SCHEMA.items():
        if code == schema:
            # Recover the exact casing used by the <select>.
            for value in SEDI.values():
                if value.lower() == city:
                    return value
    return raw


def _compose_numero(anno: str, numero: str) -> str:
    """Build the number the portal matches on: YYYY + 5-digit sequence.

    The portal dropped the standalone year filter, so a year without a number
    yields nothing — better than silently returning unfiltered results.
    """
    numero = (numero or "").strip()
    anno = (anno or "").strip()
    if not numero:
        return ""
    if not anno or not numero.isdigit():
        return numero
    if len(numero) >= 8:  # already a full YYYYNNNNN number
        return numero
    return f"{anno}{int(numero):05d}"


def _extract_portlet_id(html: str) -> str:
    """Read the (instance-scoped) portlet id from the search page."""
    m = re.search(r"p_p_id=(decisioni_pareri_web[A-Za-z0-9_]*)", html)
    if m:
        return m.group(1)
    m = re.search(r"_(decisioni_pareri_web[A-Za-z0-9_]*?)_provvedimentiForm", html)
    if m:
        return m.group(1)
    return _PORTLET


def _extract_form_action(html: str) -> str:
    """Return the search form's action URL verbatim (carries p_auth + lifecycle)."""
    soup = BeautifulSoup(html, "lxml")
    for form in soup.find_all("form"):
        action = form.get("action", "") or ""
        if "javax.portlet.action" in action and "decisioni_pareri_web" in action:
            return action
    return ""


def _extract_p_auth(html: str) -> str:
    """Extract CSRF p_auth token from Liferay page HTML."""
    soup = BeautifulSoup(html, "lxml")

    for form in soup.find_all("form"):
        action = form.get("action", "") or ""
        m = re.search(r"[?&]p_auth=([A-Za-z0-9_-]+)", action)
        if m:
            return m.group(1)

    inp = soup.find("input", {"name": "p_auth"})
    if inp and inp.get("value"):
        return inp["value"]

    return ""


def _build_action_url(portlet: str, p_auth: str = "") -> str:
    """Fallback action URL, used when the form can't be read from the page."""
    params = {
        "p_p_id": portlet,
        "p_p_lifecycle": "1",
        "p_p_state": "normal",
        "p_p_mode": "view",
        f"_{portlet}_javax.portlet.action": "search",
    }
    if p_auth:
        params["p_auth"] = p_auth
    return f"{_BASE_SEARCH}{_SEARCH_PATH}?{urlencode(params)}"


def _build_search_params(
    portlet: str,
    query: str = "",
    tipo: str = "",
    sede: str = "",
    numero: str = "",
    page_size: int = 20,
) -> dict:
    """Build the POST body. Every field the form declares must be present."""
    prefix = f"_{portlet}_"
    return {
        f"{prefix}searchtextProvvedimenti": query,
        f"{prefix}searchAllWords": "",
        f"{prefix}searchAnyWords": "",
        f"{prefix}searchNotWords": "",
        f"{prefix}searchPhrase": "",
        f"{prefix}pageSize": str(page_size),
        f"{prefix}TipoProvvedimentoItem": tipo,
        f"{prefix}sedeProvvedimenti": sede,
        f"{prefix}searchModeRadio": "provv",
        f"{prefix}DataYearItem": "",
        f"{prefix}numeroProvvedimenti": numero,
        f"{prefix}DataNrgItem": "",
        f"{prefix}numeroNrg": "",
        f"{prefix}isAdvancedSearch": "false",
        f"{prefix}asSearchMode": "provv",
    }


def build_document_url(sede: str, nrg: str, nome_file: str) -> str:
    """URL of the full text on the mdp subdomain."""
    params = {
        "nodeRef": "",
        "schema": _resolve_schema(sede),
        "nrg": nrg,
        "nomeFile": nome_file,
        "subDir": "Provvedimenti",
    }
    return f"{_BASE_MDP}{_DOCUMENT_PATH}?{urlencode(params)}"


_RE_NUMERO = re.compile(r"numero\s+provv\.?\s*:?\s*(\d+)", re.IGNORECASE)
_RE_TIPO = re.compile(r"([A-ZÀ-Ù][A-ZÀ-Ù' ]+?)\s+sede di", re.UNICODE)
# Case-sensitive on purpose: the label is lowercase ", sezione", while the
# heading repeats the value uppercase ("(ROMA, SEZIONE 3Q)") earlier in the item.
_RE_SEZIONE = re.compile(r",\s*sezione\s+([^,]+?)\s*,\s*numero\s+provv")
_RE_ECLI = re.compile(r"ECLI:[A-Z]{2}:[A-Z]+:\d{4}:\w+")


def _parse_results(html: str) -> list[ProvvedimentoResult]:
    """Parse search results HTML into ProvvedimentoResult list.

    Each hit is an <article class="ricerca--item"> whose identifying data lives
    on an inner <a data-sede data-nrg href=...>. The pagination footer shares
    that class but has no such link, so requiring it also skips the footer.
    """
    soup = BeautifulSoup(html, "lxml")
    results = []

    for article in soup.find_all("article", class_="ricerca--item"):
        link = article.find("a", attrs={"data-sede": True})
        if link is None:
            continue

        schema = (link.get("data-sede") or "").strip()
        nrg = (link.get("data-nrg") or "").strip()
        if not schema:
            continue

        href = link.get("href", "") or ""
        qs = parse_qs(urlparse(href).query)
        nome_file = (qs.get("nomeFile") or [""])[0]
        if not nrg:
            nrg = (qs.get("nrg") or [""])[0]

        text = " ".join(article.stripped_strings)

        numero = ""
        m = _RE_NUMERO.search(text)
        if m:
            numero = m.group(1)

        tipo = ""
        m = _RE_TIPO.search(text)
        if m:
            tipo = m.group(1).strip()

        sezione = ""
        m = _RE_SEZIONE.search(text)
        if m:
            sezione = m.group(1).strip()

        ecli = ""
        m = _RE_ECLI.search(text)
        if m:
            ecli = m.group(0)

        snippet_el = article.find(class_="snippet")
        oggetto = " ".join(snippet_el.stripped_strings) if snippet_el else ""

        anno = numero[:4] if len(numero) >= 8 and numero[:4].isdigit() else ""

        results.append(ProvvedimentoResult(
            sede=schema,
            sede_label=_SCHEMA_LABELS.get(schema, schema),
            nrg=nrg,
            tipo=tipo,
            anno=anno,
            nome_file=nome_file,
            data_deposito="",
            oggetto=oggetto,
            numero=numero,
            sezione=sezione,
            ecli=ecli,
        ))

    return results


def _is_error_page(content: bytes) -> bool:
    """True when mdp answered 200 with an HTML error page instead of the XML.

    A stale document URL does NOT return a 404 status — it returns a styled
    "404 - Pagina non trovata" HTML body, which would otherwise be parsed into
    plausible-looking garbage.
    """
    head = content[:2048].decode("utf-8", errors="replace").lower()
    if "<?xml" in head or "<ga" in head:
        return False
    return (
        "pagina non trovata" in head
        or "<!doctype html" in head
        or "404" in head
    )


def _element_text(element) -> str:
    """Flatten an element's text, including namespaced HTML children."""
    return " ".join(t.strip() for t in element.itertext() if t and t.strip())


def _parse_xml_text(xml_bytes: bytes) -> tuple[str, str]:
    """Parse XML <GA> from mdp subdomain. Returns (title, body_text)."""
    if _is_error_page(xml_bytes):
        return ("", "")

    try:
        root = ElementTree.fromstring(xml_bytes)
    except ElementTree.ParseError:
        text = xml_bytes.decode("utf-8", errors="replace")
        return ("Provvedimento", re.sub(r"<[^>]+>", " ", text).strip())

    parts: list[str] = []
    title = ""

    # Sections sit under <Provvedimento>, not directly under <GA> — search deep.
    epigrafe = root.find(".//epigrafe")
    if epigrafe is not None:
        header_parts = []
        for name in _EPIGRAFE_FIELDS:
            child = epigrafe.find(name)
            if child is None:
                continue
            text = _element_text(child)
            if text:
                header_parts.append(text)
        if header_parts:
            title = header_parts[0]
            parts.append("\n\n".join(header_parts))

    for name in _BODY_SECTIONS:
        section = root.find(f".//{name}")
        if section is None:
            continue
        text = _element_text(section)
        if not text:
            continue
        heading = "DISPOSITIVO" if name == "dispositivo" else "MOTIVAZIONE"
        parts.append(f"{heading}\n\n{text}")

    body_text = "\n\n".join(parts) if parts else ""

    if not title:
        meta = root.find(".//meta")
        if meta is not None and meta.get("descrizione"):
            title = meta.get("descrizione", "")
    if not title:
        title = "Provvedimento"

    return title, body_text


def format_result(doc: ProvvedimentoResult) -> str:
    """Format a single ProvvedimentoResult as markdown block."""
    numero = doc.numero or doc.nrg
    header = f"### {doc.sede_label} — {doc.tipo or 'Provvedimento'} n. {numero}"
    if doc.anno:
        header += f" ({doc.anno})"
    lines = [header]
    if doc.sezione:
        lines.append(f"**Sezione**: {doc.sezione}")
    if doc.oggetto:
        lines.append(f"**Estratto**: {doc.oggetto[:300]}")
    if doc.ecli:
        lines.append(f"**ECLI**: {doc.ecli}")
    lines.append(
        f"**Testo integrale**: `leggi_provvedimento_amm(sede=\"{doc.sede}\", "
        f"nrg=\"{doc.nrg}\", nome_file=\"{doc.nome_file}\")`"
    )
    return "\n".join(lines)


def format_full(title: str, text: str, sede: str, nrg: str) -> str:
    """Format full provvedimento as markdown with truncation at _MAX_TEXT_LENGTH."""
    schema = _resolve_schema(sede)
    sede_label = _SCHEMA_LABELS.get(schema, sede)
    truncated = len(text) > _MAX_TEXT_LENGTH
    body = text[:_MAX_TEXT_LENGTH] if truncated else text
    lines = [
        f"# {title}",
        f"**Sede**: {sede_label} ({schema}) — NRG: {nrg}",
        "",
        body,
    ]
    if truncated:
        lines.append(
            f"\n---\n*[Testo troncato a {_MAX_TEXT_LENGTH} caratteri su {len(text)} totali]*"
        )
    return "\n".join(lines)


class GASession:
    """Async context manager for Giustizia Amministrativa HTTP session."""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None
        self._p_auth: str = ""
        self._action: str = ""
        self.portlet_id: str = _PORTLET

    async def __aenter__(self) -> "GASession":
        self._client = httpx.AsyncClient(
            timeout=_TIMEOUT,
            headers=_HEADERS,
            follow_redirects=True,
        )
        resp = await retry_request(self._client, "GET", _BASE_SEARCH + _SEARCH_PATH)
        html = resp.text
        self.portlet_id = _extract_portlet_id(html)
        self._p_auth = _extract_p_auth(html)
        # The form action already carries p_p_id, lifecycle and p_auth — reuse it
        # verbatim so a future rename of any of those keeps working.
        self._action = _extract_form_action(html) or _build_action_url(
            self.portlet_id, self._p_auth
        )
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def search(self, params: dict) -> str:
        if self._client is None:
            raise RuntimeError("GASession not entered — use `async with`")
        resp = await retry_request(self._client, "POST", self._action, data=params)
        return resp.text

    async def fetch_text(self, sede: str, nrg: str, nome_file: str) -> bytes:
        if self._client is None:
            raise RuntimeError("GASession not entered — use `async with`")
        url = build_document_url(sede, nrg, nome_file)
        resp = await retry_request(self._client, "GET", url)
        return resp.content


async def search_provvedimenti(
    query: str = "",
    tipo: str = "",
    sede: str = "",
    anno: str = "",
    numero: str = "",
    rows: int = 20,
) -> list[ProvvedimentoResult]:
    """Search Giustizia Amministrativa. Returns list of ProvvedimentoResult."""
    rows = min(rows, 60)
    tipo_val = TIPI_PROVVEDIMENTO.get(tipo.lower().replace(" ", "_"), tipo) if tipo else ""
    sede_val = _resolve_sede_filter(sede)
    numero_val = _compose_numero(anno, numero)

    async with GASession() as session:
        params = _build_search_params(
            session.portlet_id,
            query=query,
            tipo=tipo_val,
            sede=sede_val,
            numero=numero_val,
            page_size=rows,
        )
        html = await session.search(params)

    return _parse_results(html)[:rows]


async def fetch_provvedimento_text(sede: str, nrg: str, nome_file: str) -> tuple[str, str]:
    """Fetch full text from mdp subdomain. Returns (title, body_text)."""
    async with GASession() as session:
        xml_bytes = await session.fetch_text(sede, nrg, nome_file)
    return _parse_xml_text(xml_bytes)

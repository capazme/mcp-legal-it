"""Client for Giustizia Amministrativa (giustizia-amministrativa.it).

Endpoint: https://www.giustizia-amministrativa.it/web/guest/-/ricerca-giurisprudenza
Full text: https://mdp.giustizia-amministrativa.it (XML <GA> format)

Il sito usa Liferay Portal — nessuna API pubblica JSON. Scraping HTML via BeautifulSoup.
I testi integrali sono su sottodominio mdp in formato XML strutturato.
SSL non valido su entrambi i domini — verify=False necessario (come Italgiure).
"""

import re
from dataclasses import dataclass
from xml.etree import ElementTree

import httpx

from src.lib._http import retry_request
from bs4 import BeautifulSoup

_BASE_SEARCH = "https://www.giustizia-amministrativa.it"
_BASE_MDP = "https://mdp.giustizia-amministrativa.it"
_SEARCH_PATH = "/web/guest/-/ricerca-giurisprudenza"
_PORTLET = "decisioni_pareri_web_WAR_decisioni_pareri_webportlet"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://www.giustizia-amministrativa.it/",
}

_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
_MAX_TEXT_LENGTH = 15000

SEDI: dict[str, str] = {
    "consiglio_di_stato": "CDS",
    "cgars": "CGARS",
    "tar_lazio": "TARLAZ",
    "tar_lombardia": "TARLOM",
    "tar_campania_napoli": "TARCAM",
    "tar_campania_salerno": "TARCAMSAL",
    "tar_sicilia_palermo": "TARSIC",
    "tar_sicilia_catania": "TARSICCAT",
    "tar_veneto": "TARVEN",
    "tar_piemonte": "TARPIE",
    "tar_emilia_romagna": "TAREMI",
    "tar_toscana": "TARTOS",
    "tar_puglia_bari": "TARPUG",
    "tar_puglia_lecce": "TARPUGLEC",
    "tar_calabria_catanzaro": "TARCAL",
    "tar_calabria_reggio": "TARCALREG",
    "tar_liguria": "TARLIG",
    "tar_sardegna": "TARSAR",
    "tar_friuli": "TARFRI",
    "tar_marche": "TARMAR",
    "tar_abruzzo_pescara": "TARABR",
    "tar_abruzzo_laquila": "TARABRLAQ",
    "tar_umbria": "TARUMB",
    "tar_molise": "TARMOL",
    "tar_basilicata": "TARBAS",
    "tar_trentino_bolzano": "TARBOL",
    "tar_trentino_trento": "TARTRETN",
    "tar_valle_aosta": "TARVDA",
}

# Reverse map: code -> human label
_SEDE_LABELS: dict[str, str] = {
    "CDS": "Consiglio di Stato",
    "CGARS": "CGARS",
    "TARLAZ": "TAR Lazio",
    "TARLOM": "TAR Lombardia",
    "TARCAM": "TAR Campania - Napoli",
    "TARCAMSAL": "TAR Campania - Salerno",
    "TARSIC": "TAR Sicilia - Palermo",
    "TARSICCAT": "TAR Sicilia - Catania",
    "TARVEN": "TAR Veneto",
    "TARPIE": "TAR Piemonte",
    "TAREMI": "TAR Emilia-Romagna",
    "TARTOS": "TAR Toscana",
    "TARPUG": "TAR Puglia - Bari",
    "TARPUGLEC": "TAR Puglia - Lecce",
    "TARCAL": "TAR Calabria - Catanzaro",
    "TARCALREG": "TAR Calabria - Reggio",
    "TARLIG": "TAR Liguria",
    "TARSAR": "TAR Sardegna",
    "TARFRI": "TAR Friuli-Venezia Giulia",
    "TARMAR": "TAR Marche",
    "TARABR": "TAR Abruzzo - Pescara",
    "TARABRLAQ": "TAR Abruzzo - L'Aquila",
    "TARUMB": "TAR Umbria",
    "TARMOL": "TAR Molise",
    "TARBAS": "TAR Basilicata",
    "TARBOL": "TAR Trentino-Alto Adige - Bolzano",
    "TARTRETN": "TAR Trentino-Alto Adige - Trento",
    "TARVDA": "TAR Valle d'Aosta",
}

TIPI_PROVVEDIMENTO: dict[str, str] = {
    "sentenza": "Sentenza",
    "ordinanza": "Ordinanza",
    "decreto": "Decreto",
    "parere": "Parere",
}


@dataclass
class ProvvedimentoResult:
    sede: str             # code e.g. "CDS", "TARLAZ"
    sede_label: str       # e.g. "Consiglio di Stato", "TAR Lazio"
    nrg: str              # numero registro generale
    tipo: str             # sentenza, ordinanza, decreto
    anno: str             # year
    nome_file: str        # filename for mdp subdomain
    data_deposito: str    # DD/MM/YYYY
    oggetto: str          # subject matter


def _extract_p_auth(html: str) -> str:
    """Extract CSRF p_auth token from Liferay page HTML."""
    soup = BeautifulSoup(html, "lxml")

    # Try hidden input first
    inp = soup.find("input", {"name": "p_auth"})
    if inp and inp.get("value"):
        return inp["value"]

    # Try form action URL: ?p_auth=TOKEN
    for form in soup.find_all("form"):
        action = form.get("action", "")
        m = re.search(r"[?&]p_auth=([A-Za-z0-9_-]+)", action)
        if m:
            return m.group(1)

    return ""


def _build_search_params(
    query: str = "",
    tipo: str = "",
    sede: str = "",
    anno: str = "",
    numero: str = "",
    page_size: int = 20,
    p_auth: str = "",
) -> dict:
    prefix = f"_{_PORTLET}_"
    params: dict = {
        "p_p_id": _PORTLET,
        "p_p_lifecycle": "1",
        "p_p_state": "normal",
        "p_p_mode": "view",
        f"{prefix}javax.portlet.action": "ricerca",
    }
    if p_auth:
        params["p_auth"] = p_auth
    if query:
        params[f"{prefix}testolibero"] = query
    if tipo:
        params[f"{prefix}tipoProvvedimento"] = tipo
    if sede:
        params[f"{prefix}sede"] = sede
    if anno:
        params[f"{prefix}anno"] = anno
    if numero:
        params[f"{prefix}numero"] = numero
    params[f"{prefix}rows"] = str(page_size)
    return params


def _parse_results(html: str) -> list[ProvvedimentoResult]:
    """Parse search results HTML into ProvvedimentoResult list.

    Each result is an <article class="ricerca--item"> with data- attributes.
    """
    soup = BeautifulSoup(html, "lxml")
    results = []

    for article in soup.find_all("article", class_="ricerca--item"):
        sede_code = article.get("data-sede", "").strip()
        nrg = article.get("data-nrg", "").strip()
        tipo = article.get("data-tipo", "").strip()
        anno = article.get("data-anno", "").strip()
        nome_file = article.get("data-nomefile", "").strip()
        data_deposito = article.get("data-datadeposito", "").strip()
        oggetto = article.get("data-oggetto", "").strip()

        if not sede_code or not nrg:
            continue

        sede_label = _SEDE_LABELS.get(sede_code, sede_code)

        results.append(ProvvedimentoResult(
            sede=sede_code,
            sede_label=sede_label,
            nrg=nrg,
            tipo=tipo,
            anno=anno,
            nome_file=nome_file,
            data_deposito=data_deposito,
            oggetto=oggetto,
        ))

    return results


def _parse_xml_text(xml_bytes: bytes) -> tuple[str, str]:
    """Parse XML <GA> from mdp subdomain. Returns (title, body_text)."""
    try:
        root = ElementTree.fromstring(xml_bytes)
    except ElementTree.ParseError:
        # Fallback: treat as plain text
        text = xml_bytes.decode("utf-8", errors="replace")
        return ("Provvedimento", re.sub(r"<[^>]+>", " ", text).strip())

    parts = []
    title = ""

    # Epigrafe (intestazioni)
    epigrafe = root.find("epigrafe")
    if epigrafe is not None:
        header_parts = []
        for child in epigrafe:
            t = (child.text or "").strip()
            if t:
                header_parts.append(t)
        if header_parts:
            title = header_parts[0]
            parts.append("\n".join(header_parts))

    # Motivazione
    motivazione = root.find("motivazione")
    if motivazione is not None:
        mot_parts = []
        for child in motivazione:
            t = (child.text or "").strip()
            if t:
                mot_parts.append(t)
        if mot_parts:
            parts.append("MOTIVAZIONE\n\n" + "\n\n".join(mot_parts))

    # Dispositivo
    dispositivo = root.find("dispositivo")
    if dispositivo is not None:
        dis_parts = []
        for child in dispositivo:
            t = (child.text or "").strip()
            if t:
                dis_parts.append(t)
        if dis_parts:
            parts.append("DISPOSITIVO\n\n" + "\n\n".join(dis_parts))

    body_text = "\n\n".join(parts) if parts else ""

    # Fallback title from nomeFile attribute or root text
    if not title:
        title = root.get("id", "") or "Provvedimento"

    return title, body_text


def format_result(doc: ProvvedimentoResult) -> str:
    """Format a single ProvvedimentoResult as markdown block."""
    lines = [f"### {doc.sede_label} — {doc.tipo} n. {doc.nrg}/{doc.anno}"]
    if doc.oggetto:
        lines.append(f"**Oggetto**: {doc.oggetto[:300]}")
    if doc.data_deposito:
        lines.append(f"**Data deposito**: {doc.data_deposito}")
    lines.append(f"**Sede**: {doc.sede_label} ({doc.sede})")
    if doc.nome_file:
        lines.append(f"**File**: `{doc.nome_file}`")
    return "\n".join(lines)


def format_full(title: str, text: str, sede: str, nrg: str) -> str:
    """Format full provvedimento as markdown with truncation at _MAX_TEXT_LENGTH."""
    sede_label = _SEDE_LABELS.get(sede, sede)
    truncated = len(text) > _MAX_TEXT_LENGTH
    body = text[:_MAX_TEXT_LENGTH] if truncated else text
    lines = [
        f"# {title}",
        f"**Sede**: {sede_label} ({sede}) — NRG: {nrg}",
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

    async def __aenter__(self) -> "GASession":
        self._client = httpx.AsyncClient(
            verify=False,
            timeout=_TIMEOUT,
            headers=_HEADERS,
            follow_redirects=True,
        )
        resp = await retry_request(self._client, "GET", _BASE_SEARCH + _SEARCH_PATH)
        self._p_auth = _extract_p_auth(resp.text)
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def search(self, params: dict) -> str:
        if self._client is None:
            raise RuntimeError("GASession not entered — use `async with`")
        resp = await retry_request(self._client, "POST", _BASE_SEARCH + _SEARCH_PATH, data=params)
        return resp.text

    async def fetch_text(self, nome_file: str) -> bytes:
        if self._client is None:
            raise RuntimeError("GASession not entered — use `async with`")
        url = f"{_BASE_MDP}/mdp/atti/{nome_file}"
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
    rows = min(rows, 50)
    tipo_val = TIPI_PROVVEDIMENTO.get(tipo.lower(), tipo) if tipo else ""
    sede_val = SEDI.get(sede.lower().replace(" ", "_"), sede) if sede else ""

    async with GASession() as session:
        params = _build_search_params(
            query=query,
            tipo=tipo_val,
            sede=sede_val,
            anno=anno,
            numero=numero,
            page_size=rows,
            p_auth=session._p_auth,
        )
        html = await session.search(params)

    return _parse_results(html)


async def fetch_provvedimento_text(sede: str, nrg: str, nome_file: str) -> tuple[str, str]:
    """Fetch full text from mdp subdomain. Returns (title, body_text)."""
    async with GASession() as session:
        xml_bytes = await session.fetch_text(nome_file)
    return _parse_xml_text(xml_bytes)

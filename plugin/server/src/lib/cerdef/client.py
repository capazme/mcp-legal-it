"""Client for CeRDEF (Banca Dati Giurisprudenza Tributaria — def.finanze.it).

Endpoint: https://def.finanze.it/DocTribFrontend/
- Search: POST to executeAdvancedGiurisprudenzaSearch.do (form-encoded)
- Results: XML embedded in JS variable `var xmlResult = '...'` in HTML response
- Detail: GET to getGiurisprudenzaDetail.do?id={GUID}
- Pagination: session cookie-based via paginatorXml.do?paginaRichiesta=N

No auth, no captcha, standard SSL.
"""

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass

import httpx
from bs4 import BeautifulSoup

_BASE = "https://def.finanze.it/DocTribFrontend/"
_SEARCH_URL = _BASE + "executeAdvancedGiurisprudenzaSearch.do"
_DETAIL_URL = _BASE + "getGiurisprudenzaDetail.do"
_PAGINATOR_URL = _BASE + "paginatorXml.do"
_TIMEOUT = httpx.Timeout(45.0, connect=15.0)
_MAX_TEXT_LENGTH = 25000
_MAX_RESULTS = 250

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://def.finanze.it/DocTribFrontend/",
}

TIPO_ESTREMI: dict[str, str] = {
    "sentenza": "Sentenza",
    "ordinanza": "Ordinanza",
    "decreto": "Decreto",
}

ENTI: dict[str, str] = {
    "corte_suprema": "Corte Suprema di Cassazione",
    "cgt_primo_grado": "CGT I grado",
    "cgt_secondo_grado": "CGT II grado",
}

CRITERI_RICERCA: dict[str, str] = {
    "tutti": "T",
    "frase_esatta": "E",
    "almeno_uno": "O",
    "codice": "C",
}


@dataclass
class ProvvedimentoResult:
    guid: str
    estremi: str
    titoli: str
    ente: str
    data: str


@dataclass
class ProvvedimentoDetail:
    guid: str
    estremi: str
    massima: str
    testo_integrale: str
    collegio: str = ""
    udienza: str = ""
    ricorsi: str = ""


class CerdefSession:
    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "CerdefSession":
        self._client = httpx.AsyncClient(
            timeout=_TIMEOUT, headers=_HEADERS, follow_redirects=True
        )
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("CerdefSession not entered")
        return self._client


def _unescape_js_string(raw: str) -> str:
    """Unescape JS string escapes: \\/ → / and \\uXXXX → char (4-digit standard JS)."""
    result = raw.replace("\\/", "/")
    result = re.sub(
        r"\\u([0-9a-fA-F]{4})",
        lambda m: chr(int(m.group(1), 16)),
        result,
    )
    return result


def _extract_xml_from_js(html: str, var_name: str) -> str:
    """Extract XML string embedded in a JS variable assignment.

    Handles: var xmlResult = '<...>';
    Unescapes \\/ and \\uXX sequences.
    """
    pattern = rf"var\s+{re.escape(var_name)}\s*=\s*'(.*?)'\s*;"
    match = re.search(pattern, html, re.DOTALL)
    if not match:
        return ""
    raw = match.group(1)
    return _unescape_js_string(raw)


def _parse_search_xml(xml_str: str) -> list[ProvvedimentoResult]:
    """Parse XML search results into ProvvedimentoResult list."""
    if not xml_str.strip():
        return []
    try:
        root = ET.fromstring(xml_str)
    except ET.ParseError:
        return []

    results = []
    for item in root.findall("risultato"):
        guid = (item.findtext("guid") or "").strip()
        if not guid:
            continue
        results.append(ProvvedimentoResult(
            guid=guid,
            estremi=(item.findtext("estremi") or "").strip(),
            titoli=(item.findtext("titoli") or "").strip(),
            ente=(item.findtext("ente") or "").strip(),
            data=(item.findtext("data") or "").strip(),
        ))
    return results


def _strip_cdata_html(text: str) -> str:
    """Strip HTML tags from CDATA content using BeautifulSoup."""
    if not text:
        return ""
    soup = BeautifulSoup(text, "lxml")
    return soup.get_text("\n", strip=True)


def _parse_detail_xml(xml_str: str) -> ProvvedimentoDetail:
    """Parse XML detail response into ProvvedimentoDetail."""
    if not xml_str.strip():
        return ProvvedimentoDetail(guid="", estremi="", massima="", testo_integrale="")
    try:
        root = ET.fromstring(xml_str)
    except ET.ParseError:
        return ProvvedimentoDetail(guid="", estremi="", massima="", testo_integrale="")

    def _text(tag: str) -> str:
        return (root.findtext(tag) or "").strip()

    massima_raw = _text("massima")
    testo_raw = _text("testoIntegrale")

    return ProvvedimentoDetail(
        guid=_text("guid"),
        estremi=_text("estremi"),
        massima=_strip_cdata_html(massima_raw),
        testo_integrale=_strip_cdata_html(testo_raw),
        collegio=_text("collegio"),
        udienza=_text("udienza"),
        ricorsi=_text("ricorsi"),
    )


def format_result(doc: ProvvedimentoResult) -> str:
    """Format a single ProvvedimentoResult as markdown block."""
    lines = [f"### {doc.estremi or doc.guid}"]
    if doc.titoli:
        lines.append(f"**Oggetto**: {doc.titoli[:300]}")
    if doc.ente:
        lines.append(f"**Ente**: {doc.ente}")
    if doc.data:
        lines.append(f"**Data**: {doc.data}")
    lines.append(f"**GUID**: `{doc.guid}`")
    return "\n".join(lines)


def format_detail(detail: ProvvedimentoDetail) -> str:
    """Format a ProvvedimentoDetail as markdown with truncation."""
    lines = [f"# {detail.estremi or detail.guid}"]

    if detail.collegio:
        lines.append(f"**Collegio**: {detail.collegio}")
    if detail.udienza:
        lines.append(f"**Udienza**: {detail.udienza}")
    if detail.ricorsi:
        lines.append(f"**Ricorsi**: {detail.ricorsi}")

    if detail.massima:
        lines.append("\n## Massima\n")
        lines.append(detail.massima)

    if detail.testo_integrale:
        lines.append("\n## Testo Integrale\n")
        testo = detail.testo_integrale
        truncated = len(testo) > _MAX_TEXT_LENGTH
        lines.append(testo[:_MAX_TEXT_LENGTH] if truncated else testo)
        if truncated:
            lines.append(
                f"\n---\n*[Testo troncato a {_MAX_TEXT_LENGTH} caratteri su {len(testo)} totali]*"
            )

    return "\n".join(lines)


async def search_giurisprudenza(
    parole: str = "",
    tipo_criterio: str = "tutti",
    tipo_estremi: str = "",
    numero: str = "",
    data_da: str = "",
    data_a: str = "",
    ente: str = "",
    ordinamento: str = "rilevanza",
    rows: int = 10,
) -> list[ProvvedimentoResult]:
    """Search CeRDEF giurisprudenza tributaria.

    Uses session to maintain cookies between POST search and GET pagination.
    """
    rows = min(rows, _MAX_RESULTS)

    form_data = {
        "paroleChiave": parole,
        "tipoCriterio": CRITERI_RICERCA.get(tipo_criterio, "T"),
        "tipoEstremi": TIPO_ESTREMI.get(tipo_estremi, ""),
        "numero": numero or "",
        "dataDa": data_da or "",
        "dataA": data_a or "",
        "ente": ENTI.get(ente, ""),
        "ordinamento": ordinamento or "rilevanza",
    }

    results: list[ProvvedimentoResult] = []

    async with CerdefSession() as session:
        resp = await session.client.post(_SEARCH_URL, data=form_data)
        resp.raise_for_status()

        xml_str = _extract_xml_from_js(resp.text, "xmlResult")
        page_results = _parse_search_xml(xml_str)
        results.extend(page_results)

        page = 2
        while len(results) < rows and len(page_results) > 0:
            resp = await session.client.get(
                _PAGINATOR_URL, params={"paginaRichiesta": page}
            )
            resp.raise_for_status()

            xml_str = _extract_xml_from_js(resp.text, "xmlResult")
            page_results = _parse_search_xml(xml_str)
            if not page_results:
                break
            results.extend(page_results)
            page += 1

    return results[:rows]


async def fetch_provvedimento(guid: str) -> ProvvedimentoDetail:
    """Fetch full detail of a provvedimento by GUID."""
    async with httpx.AsyncClient(
        timeout=_TIMEOUT, headers=_HEADERS, follow_redirects=True
    ) as client:
        resp = await client.get(_DETAIL_URL, params={"id": guid})
        resp.raise_for_status()
        xml_str = _extract_xml_from_js(resp.text, "xmlDettaglio")
        return _parse_detail_xml(xml_str)

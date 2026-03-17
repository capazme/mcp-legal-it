"""Client for CGUE (Court of Justice of the European Union) case law.

Data sources:
- SPARQL endpoint: https://publications.europa.eu/webapi/rdf/sparql (CELLAR CDM ontology)
- Full text: CELLAR content negotiation via expression URI (Accept: text/html)

CELEX format for case law: 6{year}{court_code}{case_number_padded}
  CJ = Court of Justice judgment
  CC = Court of Justice order
  TJ = General Court judgment
  TO = General Court order
  CO = Court of Justice opinion of AG
"""

import re
from dataclasses import dataclass

import httpx
from bs4 import BeautifulSoup

_SPARQL_URL = "https://publications.europa.eu/webapi/rdf/sparql"
_TIMEOUT = httpx.Timeout(45.0, connect=15.0)
_MAX_TEXT_LENGTH = 25000
_LANG_ITA = "http://publications.europa.eu/resource/authority/language/ITA"

_HEADERS_SPARQL = {
    "Accept": "application/sparql-results+json",
    "User-Agent": "Mozilla/5.0 (compatible; mcp-legal-it/2.1)",
}

_HEADERS_HTML = {
    "Accept": "text/html,application/xhtml+xml",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept-Language": "it-IT,it;q=0.9",
}

# Resource type URIs
_RTYPE_JUDG = "http://publications.europa.eu/resource/authority/resource-type/JUDG"
_RTYPE_ORDER = "http://publications.europa.eu/resource/authority/resource-type/ORDER"
_RTYPE_OPIN_AG = "http://publications.europa.eu/resource/authority/resource-type/OPIN_AG"

CORTI: dict[str, str] = {
    "corte_di_giustizia": "CJ",
    "tribunale": "TJ",
    "tutte": "",
}

TIPI_DOCUMENTO: dict[str, str] = {
    "sentenza": "JUDG",
    "ordinanza": "ORDER",
    "conclusioni_ag": "OPIN_AG",
    "tutti": "",
}

MATERIE_KEYWORDS: dict[str, list[str]] = {
    "iva": ["iva", "imposta sul valore aggiunto", "sesta direttiva"],
    "concorrenza": ["concorrenza", "aiuti di stato", "intesa", "abuso di posizione dominante"],
    "ambiente": ["ambiente", "rifiuti", "emissioni", "valutazione impatto ambientale"],
    "lavoro": ["lavoro", "lavoratore", "contratto di lavoro", "licenziamento"],
    "protezione_dati": ["dati personali", "protezione dei dati", "gdpr", "vita privata"],
    "appalti": ["appalto", "appalti pubblici", "gara", "aggiudicazione"],
    "consumatori": ["consumatore", "clausola abusiva", "garanzia"],
}


@dataclass
class CaseResult:
    celex: str        # "62024CJ0008"
    ecli: str         # "ECLI:EU:C:2026:210"
    case_number: str  # "C-8/2024"
    date: str         # "2026-03-17"
    title: str        # Italian title from expression
    court: str        # "CJ" or "TJ"
    doc_type: str     # "JUDG", "ORDER", "OPIN_AG"
    cellar_uri: str   # URI for fetching full text


def _build_search_query(
    keywords: list[str],
    court_code: str = "",
    doc_type: str = "",
    year_from: str = "",
    year_to: str = "",
    limit: int = 10,
) -> str:
    keyword_filters = ""
    if keywords:
        conditions = " || ".join(
            f'CONTAINS(LCASE(?title), "{kw.lower()}")'
            for kw in keywords
        )
        keyword_filters = f"  FILTER({conditions})"

    court_filters = ""
    if court_code == "CJ":
        court_filters = '  FILTER(?type_code IN ("CJ", "CC", "CO"))'
    elif court_code == "TJ":
        court_filters = '  FILTER(?type_code IN ("TJ", "TO"))'

    type_filters = ""
    if doc_type == "JUDG":
        type_filters = f"  ?work cdm:work_has_resource-type <{_RTYPE_JUDG}> ."
    elif doc_type == "ORDER":
        type_filters = f"  ?work cdm:work_has_resource-type <{_RTYPE_ORDER}> ."
    elif doc_type == "OPIN_AG":
        type_filters = f"  ?work cdm:work_has_resource-type <{_RTYPE_OPIN_AG}> ."

    date_filters_parts = []
    if year_from:
        date_filters_parts.append(
            f'  FILTER(?date >= "{year_from}-01-01"^^xsd:date)'
        )
    if year_to:
        date_filters_parts.append(
            f'  FILTER(?date <= "{year_to}-12-31"^^xsd:date)'
        )
    date_filters = "\n".join(date_filters_parts)

    query = f"""PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

SELECT DISTINCT ?celex ?ecli ?date ?title ?type_code ?year ?case_num ?court ?cellar_exp
WHERE {{
  ?work cdm:resource_legal_id_celex ?celex .
  ?work cdm:work_date_document ?date .
  ?work cdm:resource_legal_type ?type_code .
  ?work cdm:resource_legal_year ?year .
  ?work cdm:resource_legal_number_natural_celex ?case_num .
  ?work cdm:work_created_by_agent ?court .
  OPTIONAL {{ ?work cdm:case-law_ecli ?ecli . }}

  ?exp cdm:expression_belongs_to_work ?work .
  ?exp cdm:expression_uses_language <{_LANG_ITA}> .
  ?exp cdm:expression_title ?title .
  BIND(STR(?exp) AS ?cellar_exp)

  FILTER(STRSTARTS(STR(?celex), "6"))
  FILTER(!CONTAINS(STR(?celex), "_"))
{keyword_filters}
{court_filters}
{type_filters}
{date_filters}
}}
ORDER BY DESC(?date)
LIMIT {limit}"""

    return query


async def _execute_sparql(query: str) -> list[dict]:
    async with httpx.AsyncClient(timeout=_TIMEOUT, headers=_HEADERS_SPARQL) as client:
        resp = await client.post(_SPARQL_URL, data={"query": query})
        resp.raise_for_status()
        data = resp.json()
        return data["results"]["bindings"]


def _parse_results(bindings: list[dict]) -> list[CaseResult]:
    results = []
    for binding in bindings:
        celex = binding.get("celex", {}).get("value", "")
        ecli = binding.get("ecli", {}).get("value", "")
        date = binding.get("date", {}).get("value", "")
        title_raw = binding.get("title", {}).get("value", "")
        type_code = binding.get("type_code", {}).get("value", "")
        year = binding.get("year", {}).get("value", "")
        case_num = binding.get("case_num", {}).get("value", "")
        court_uri = binding.get("court", {}).get("value", "")
        cellar_uri = binding.get("cellar_exp", {}).get("value", "")

        # Construct case number: C-8/2024 or T-100/2023
        prefix = "C" if type_code.startswith("C") else "T"
        case_number = f"{prefix}-{case_num}/{year}" if case_num and year else celex

        # Extract court code from URI last segment
        court = court_uri.split("/")[-1] if court_uri else type_code

        # Determine doc_type from type_code
        if type_code in ("CJ", "TJ"):
            doc_type = "JUDG"
        elif type_code in ("CC", "TO"):
            doc_type = "ORDER"
        elif type_code == "CO":
            doc_type = "OPIN_AG"
        else:
            doc_type = type_code

        # Parse title for clean display
        header, parties, subject = _parse_title(title_raw)
        if parties and subject:
            title = f"{header} | {parties} | {subject}"
        elif parties:
            title = f"{header} | {parties}"
        elif subject:
            title = f"{header} | {subject}"
        else:
            title = header

        results.append(CaseResult(
            celex=celex,
            ecli=ecli,
            case_number=case_number,
            date=date,
            title=title,
            court=court,
            doc_type=doc_type,
            cellar_uri=cellar_uri,
        ))

    return results


def _parse_title(raw_title: str) -> tuple[str, str, str]:
    """Split title on # or ## separators.

    Returns (header, parties, subject).
    Title format: "Header.##Parti.#Materia – Sottomateria"
    """
    parts = re.split(r"#{1,2}", raw_title)
    header = parts[0].strip() if len(parts) > 0 else raw_title
    parties = parts[1].strip() if len(parts) > 1 else ""
    subject = parts[2].strip() if len(parts) > 2 else ""
    return header, parties, subject


async def _fetch_html(cellar_uri: str) -> str:
    async with httpx.AsyncClient(timeout=_TIMEOUT, headers=_HEADERS_HTML, follow_redirects=True) as client:
        resp = await client.get(cellar_uri)
        resp.raise_for_status()
        return resp.text


def _parse_html_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style"]):
        tag.decompose()
    return soup.get_text("\n", strip=True)


def format_result(doc: CaseResult) -> str:
    lines = [f"### {doc.case_number}"]
    lines.append(f"**CELEX**: {doc.celex}")
    if doc.ecli:
        lines.append(f"**ECLI**: {doc.ecli}")
    lines.append(f"**Data**: {doc.date}")
    lines.append(f"**Corte**: {doc.court} | **Tipo**: {doc.doc_type}")
    lines.append(f"**Titolo**: {doc.title[:400]}")
    lines.append(f"**CELLAR URI**: `{doc.cellar_uri}`")
    return "\n".join(lines)


def format_full(case_number: str, text: str, ecli: str) -> str:
    truncated = len(text) > _MAX_TEXT_LENGTH
    body = text[:_MAX_TEXT_LENGTH] if truncated else text
    lines = [f"# {case_number}"]
    if ecli:
        lines.append(f"**ECLI**: {ecli}")
    lines.append("")
    lines.append(body)
    if truncated:
        lines.append(
            f"\n---\n*[Testo troncato a {_MAX_TEXT_LENGTH} caratteri su {len(text)} totali]*"
        )
    return "\n".join(lines)


async def search_giurisprudenza(
    keywords: list[str],
    court: str = "",
    doc_type: str = "",
    year_from: str = "",
    year_to: str = "",
    materia: str = "",
    limit: int = 10,
) -> list[CaseResult]:
    effective_keywords = list(keywords)
    if materia and materia in MATERIE_KEYWORDS:
        effective_keywords = effective_keywords + MATERIE_KEYWORDS[materia]

    court_code = CORTI.get(court, "")
    doc_type_code = TIPI_DOCUMENTO.get(doc_type, doc_type)

    query = _build_search_query(
        keywords=effective_keywords,
        court_code=court_code,
        doc_type=doc_type_code,
        year_from=year_from,
        year_to=year_to,
        limit=limit,
    )
    bindings = await _execute_sparql(query)
    return _parse_results(bindings)


async def fetch_sentenza_text(cellar_uri: str) -> str:
    html = await _fetch_html(cellar_uri)
    return _parse_html_text(html)

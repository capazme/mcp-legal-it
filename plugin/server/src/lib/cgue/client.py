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
import warnings
from dataclasses import dataclass

import httpx

from src.lib._http import retry_request
from src.lib._paging import page, resume_hint
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

_SPARQL_URL = "https://publications.europa.eu/webapi/rdf/sparql"
_TIMEOUT = httpx.Timeout(45.0, connect=15.0)
_MAX_TEXT_LENGTH = 25000
# Longest operative part kept when a judgment is cut ("Per questi motivi ..." to the end).
_MAX_TAIL_LENGTH = 8000
# Titles are one long summary line (parties + subject headnote with the norms applied).
_MAX_TITLE_LENGTH = 1000
# A work can have several Italian expressions (and CELLAR lists each decision more than once),
# so the query asks for more rows than wanted and the parser keeps one row per CELEX.
_OVERFETCH = 3
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


def _sparql_literal(text: str) -> str:
    """Escape `text` for use inside a double-quoted SPARQL string."""
    return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ").replace("\r", " ")


# "articolo 101" / "articolo 101 bis": an article number the title must cite.
_ARTICLE_TERM = re.compile(r"^articolo (\d+)(?: (bis|ter|quater|quinquies))?$")
_SUFFIXES = "bis|ter|quater|quinquies"
# The same alternation as it appears in a title ("Articolo 7 bis"), for the SPARQL regex.
_SUFFIXES_SPACED = " bis| ter| quater| quinquies"


def _term_filter(term: str, var: str = "?title") -> str:
    """One FILTER condition that requires `term` in the (lowercased) title.

    Article numbers and short acronyms cannot be plain substrings: "articolo 7" would
    match "articolo 70", and "iva" would match every "direttiva". An article term must
    be one of the numbers listed right after "Articolo"/"Articoli" ("Articolo 101,
    paragrafo 2, TFUE" cites 101 and not 2; "Articoli 7, 8 e 47" cites all three);
    acronyms of up to four characters need non-alphanumeric neighbours. Anything else
    is a substring.
    """
    # CELLAR titles use no-break spaces here and there ("europea\xa0- Diritto"): read them as spaces.
    text = f'REPLACE(LCASE(STR({var})), "\xa0", " ")'
    m = _ARTICLE_TERM.match(term)
    if m:
        number, suffix = m.group(1), m.group(2)
        tail = f" {suffix}" if suffix else f"({_SUFFIXES_SPACED})?"
        pattern = f"articol[oi] ([0-9]+({_SUFFIXES_SPACED})?(, | e | ed |-))*{number}{tail}([^0-9a-z]|$)"
        return f'REGEX({text}, "{_sparql_literal(pattern)}")'
    if len(term) <= 4 and re.fullmatch(r"[a-z0-9]+", term):
        return f'REGEX({text}, "(^|[^a-z0-9]){term}([^a-z0-9]|$)")'
    return f'CONTAINS({text}, "{_sparql_literal(term)}")'


# Sigle che i titoli CELLAR non usano: si cerca l'estremo o la denominazione ufficiale.
_ACRONYMS: dict[str, str] = {
    "gdpr": "2016/679",
    "cdfue": "carta dei diritti fondamentali",
}
_STOPWORDS = frozenset({
    "a", "al", "alla", "alle", "ai", "agli", "allo", "con", "da", "dal", "dalla", "dei", "del",
    "della", "delle", "dello", "degli", "di", "e", "ed", "gli", "i", "il", "in", "la", "le",
    "lo", "nel", "nella", "per", "su", "sul", "sulla", "sui", "un", "una", "uno",
})
_ART_MARKER = re.compile(r"\b(?:artt?\.?|articol[oi])\s*(?=\d)")
_ART_NUMBER = re.compile(rf"(\d+)(?:\s*(?:-\s*)?({_SUFFIXES})\b)?")
_ART_LIST_SEP = re.compile(r"\s*(?:,|\be\b|\bed\b|-)\s*(?=\d)")
_ACT_NUMBER = re.compile(
    r"\b(?:direttiva|regolamento|decisione)\s*(?:\(\s*(?:ue|ce|cee|euratom|ue,\s*euratom)\s*\)\s*)?"
    r"(?:n\.?\s*)?(\d{1,4}/\d{1,4})(?:/(?:ue|ce|cee|euratom))?",
)
_BARE_ACT_NUMBER = re.compile(r"\b(\d{2,4}/\d{1,4})(?:/(?:ue|ce|cee|euratom))?\b")


def normalize_riferimento(riferimento: str) -> list[str]:
    """Split a norm reference into the terms every matching title must contain.

    CELLAR titles write "Articolo 101 TFUE" and "direttiva 2006/112/CE", never
    "art. 101 TFUE". "art."/"artt."/"articolo" become "articolo N" ("artt. 7 e 8"
    gives two terms), an act with its number ("direttiva 2006/112/CE") gives the
    number alone, well-known acronyms are replaced by their official number or
    name (GDPR -> 2016/679), and the remaining words are kept once stopwords are
    dropped. The terms are ANDed by the caller.
    """
    # No-break space and non-breaking hyphen (U+2011) are what EU texts use in "art.\xa07", "C‑11/18".
    text = riferimento.lower().replace("\xa0", " ").replace("‑", "-")
    terms: list[str] = []

    def take_articles(m: re.Match) -> str:
        pos = m.end()
        while True:
            n = _ART_NUMBER.match(text, pos)
            if not n:
                break
            terms.append(f"articolo {n.group(1)}" + (f" {n.group(2)}" if n.group(2) else ""))
            pos = n.end()
            sep = _ART_LIST_SEP.match(text, pos)
            if not sep:
                break
            pos = sep.end()
        return text[:m.start()] + " " * (pos - m.start()) + text[pos:]

    # Blank out what each rule consumed so the later rules see only the rest.
    while True:
        m = _ART_MARKER.search(text)
        if not m:
            break
        text = take_articles(m)
    for pattern in (_ACT_NUMBER, _BARE_ACT_NUMBER):
        for m in pattern.finditer(text):
            terms.append(m.group(1))
        text = pattern.sub(" ", text)
    for word in re.findall(r"[\w'’]+", text):
        word = word.strip("'’")
        if not word or word in _STOPWORDS:
            continue
        terms.append(_ACRONYMS.get(word, word))
    unique: list[str] = []
    for term in terms:
        if term not in unique:
            unique.append(term)
    return unique


def _build_search_query(
    keywords: list[str],
    court_code: str = "",
    doc_type: str = "",
    year_from: str = "",
    year_to: str = "",
    limit: int = 10,
    required_groups: list[list[str]] | None = None,
) -> str:
    """Build the CELLAR SPARQL query.

    `keywords` are alternatives (any one in the title). Each group of
    `required_groups` is a further condition ANDed with them: the title must
    contain at least one term of every group (a single-term group is a plain
    "must contain").
    """
    filters = []
    if keywords:
        conditions = " || ".join(
            f'CONTAINS(LCASE(?title), "{_sparql_literal(kw.lower())}")'
            for kw in keywords
        )
        filters.append(f"  FILTER({conditions})")
    for group in required_groups or []:
        if group:
            filters.append("  FILTER(" + " || ".join(_term_filter(t.lower()) for t in group) + ")")
    keyword_filters = "\n".join(filters)

    # cdm:resource_legal_type is an xsd:string literal: a plain "CJ" is not equal to it
    # in Virtuoso, so the comparison has to go through STR().
    # Without a court, only the decisions themselves (judgments, orders, AG opinions of the
    # two courts): CELLAR also holds the Official Journal notices of each decision (types
    # CA, CB, TA, TB), which repeat it under another CELEX and carry no ECLI.
    if court_code == "CJ":
        court_filters = '  FILTER(STR(?type_code) IN ("CJ", "CC", "CO"))'
    elif court_code == "TJ":
        court_filters = '  FILTER(STR(?type_code) IN ("TJ", "TO"))'
    else:
        court_filters = '  FILTER(STR(?type_code) IN ("CJ", "CC", "CO", "TJ", "TO"))'

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

    # No ?court in the projection: cdm:work_created_by_agent has one value per body plus a
    # CELLAR UUID, so it multiplied every decision (and printed the UUID as the "court").
    # The court is derived from the CELEX type code instead.
    query = f"""PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

SELECT DISTINCT ?celex ?ecli ?date ?title ?type_code ?year ?case_num ?cellar_exp
WHERE {{
  ?work cdm:resource_legal_id_celex ?celex .
  ?work cdm:work_date_document ?date .
  ?work cdm:resource_legal_type ?type_code .
  ?work cdm:resource_legal_year ?year .
  ?work cdm:resource_legal_number_natural_celex ?case_num .
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
ORDER BY DESC(?date) ?celex ?cellar_exp
LIMIT {limit}"""

    return query


async def _execute_sparql(query: str) -> list[dict]:
    async with httpx.AsyncClient(timeout=_TIMEOUT, headers=_HEADERS_SPARQL) as client:
        resp = await retry_request(client, "POST", _SPARQL_URL, dataset="cgue", data={"query": query})
        data = resp.json()
        return data["results"]["bindings"]


def official_case_number(type_code: str, case_num: str, year: str) -> str:
    """Case number as the Court writes it: "C-311/18" (two-digit year), "T-100/23"."""
    prefix = "C" if type_code.startswith("C") else "T"
    return f"{prefix}-{case_num}/{year[-2:]}"


def _court_of(type_code: str) -> str:
    if type_code in ("CJ", "CC", "CO"):
        return "CJ"
    if type_code in ("TJ", "TO"):
        return "TJ"
    return type_code


def _parse_results(bindings: list[dict]) -> list[CaseResult]:
    results = []
    seen: set[str] = set()
    for binding in bindings:
        celex = binding.get("celex", {}).get("value", "")
        # CELLAR returns a decision once per Italian expression: keep the first
        # (rows are ordered by date, CELEX, expression URI, so the choice is stable).
        if celex in seen:
            continue
        if celex:
            seen.add(celex)
        ecli = binding.get("ecli", {}).get("value", "")
        date = binding.get("date", {}).get("value", "")
        title_raw = binding.get("title", {}).get("value", "")
        type_code = binding.get("type_code", {}).get("value", "")
        year = binding.get("year", {}).get("value", "")
        case_num = binding.get("case_num", {}).get("value", "")
        cellar_uri = binding.get("cellar_exp", {}).get("value", "")

        case_number = official_case_number(type_code, case_num, year) if case_num and year else celex
        court = _court_of(type_code)

        # Determine doc_type from type_code
        if type_code in ("CJ", "TJ"):
            doc_type = "JUDG"
        elif type_code in ("CO", "TO"):
            doc_type = "ORDER"
        elif type_code == "CC":
            # CELEX CC = Advocate General's opinion ("Conclusioni dell'avvocato generale"),
            # CO = order of the Court ("Ordinanza della Corte"): checked on CELLAR titles
            # of 62022CC0769 and 62024CO0491.
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


# The last segment of a CELLAR title is often only the case reference ("Causa C-311/18.").
_CASE_REFERENCE_SEGMENT = re.compile(r"^caus[ae]\b.*\d+\s*/\s*\d+", re.IGNORECASE)


def _parse_title(raw_title: str) -> tuple[str, str, str]:
    """Split title on # or ## separators.

    Returns (header, parties, subject).
    Title format: "Header.##Parti.#Materia – Sottomateria"

    Preliminary references have more segments: header, parties, the referring court, the
    headnote (subject and norms applied) and the case reference ("Causa C-311/18."). The
    subject is everything after the parties, minus the trailing case reference, so the
    headnote with the norms is not lost.
    """
    parts = re.split(r"#{1,2}", raw_title)
    header = parts[0].strip() if len(parts) > 0 else raw_title
    parties = parts[1].strip() if len(parts) > 1 else ""
    rest = [p.strip() for p in parts[2:] if p.strip()]
    if rest and _CASE_REFERENCE_SEGMENT.match(rest[-1]):
        rest.pop()
    subject = " ".join(rest)
    return header, parties, subject


async def _fetch_html(cellar_uri: str) -> str:
    async with httpx.AsyncClient(timeout=_TIMEOUT, headers=_HEADERS_HTML, follow_redirects=True) as client:
        resp = await retry_request(client, "GET", cellar_uri, dataset="cgue")
        return resp.text


def _parse_html_text(html: str) -> str:
    with warnings.catch_warnings():
        # CELLAR serves XHTML: the HTML parser reads it correctly but warns on every call.
        warnings.simplefilter("ignore", XMLParsedAsHTMLWarning)
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
    lines.append(f"**Titolo**: {doc.title[:_MAX_TITLE_LENGTH]}")
    lines.append(f"**CELLAR URI**: `{doc.cellar_uri}`")
    return "\n".join(lines)


# The operative part of a judgment or order opens with this formula (art. 87, lett. i),
# Regolamento di procedura della Corte di giustizia): it is the part that carries the decision.
_OPERATIVE_PART = re.compile(r"Per (?:questi|tali) motivi", re.IGNORECASE)
# The opinion of an Advocate General has no operative part: it closes with the answer it
# proposes to the Court, in the first person and in several wordings ("propongo alla Corte
# di rispondere", "Propongo quindi alla Corte di dichiarare", "suggerisco alla Corte di
# rispondere", "propongo di rispondere"). The kept tail starts at the beginning of that line;
# when the wording is unknown, at the last "Conclusione"/"Conclusioni" heading.
_AG_PROPOSAL = re.compile(
    r"\b(?:propongo|suggerisco)\b[^.\n]{0,40}?\bdi\s+"
    r"(?:rispondere|dichiarare|statuire|risolvere|accogliere|respingere|annullare|constatare)\b",
    re.IGNORECASE,
)
_AG_CONCLUSION_HEADING = re.compile(r"^[ \t]*Conclusion[ei][ \t]*$", re.IGNORECASE | re.MULTILINE)


def _operative_start(text: str) -> int | None:
    """Where the decisive final part starts, or None when the text has none.

    The latest of: the last "Per questi motivi" (judgments, orders) and the line of the last
    proposal of an Advocate General (else the last "Conclusione" heading). The latest wins
    because an opinion can say "Per tali motivi" in its reasoning, long before its proposal,
    while a judgment that quotes the Advocate General does so before its own operative part.
    """
    candidates = [m.start() for m in _OPERATIVE_PART.finditer(text)][-1:]
    proposals = [m.start() for m in _AG_PROPOSAL.finditer(text)]
    if proposals:
        candidates.append(text.rfind("\n", 0, proposals[-1]) + 1)
    else:
        candidates.extend(m.start() for m in list(_AG_CONCLUSION_HEADING.finditer(text))[-1:])
    return max(candidates) if candidates else None


def _excerpt(text: str, da_carattere: int = 1) -> tuple[str, str]:
    """Cut `text` to the size limit without losing the operative part.

    Returns (body, note). A text within the limit comes back whole with an empty note.
    A longer one keeps its beginning and, when it has an operative part ("Per questi
    motivi") or, for an Advocate General's opinion, the proposed answer, that final part
    (up to _MAX_TAIL_LENGTH characters), so the decision always reaches the reader. Every
    note on a cut says from which character to resume; `da_carattere` > 1 returns the plain
    window of the text that starts there (see src/lib/_paging.py).
    """
    if da_carattere > 1:
        return page(text, da_carattere, _MAX_TEXT_LENGTH)
    total = len(text)
    if total <= _MAX_TEXT_LENGTH:
        return text, ""
    start = _operative_start(text)
    if start is None:
        return text[:_MAX_TEXT_LENGTH], (
            f"*[Testo troncato a {_MAX_TEXT_LENGTH} caratteri su {total} totali: "
            f"{resume_hint(_MAX_TEXT_LENGTH + 1)}]*"
        )
    end = min(total, start + _MAX_TAIL_LENGTH)
    if start < _MAX_TEXT_LENGTH:
        # The operative part begins inside the first block: extend the block to cover it.
        cut = max(_MAX_TEXT_LENGTH, end)
        if cut >= total:
            return text, ""
        return text[:cut], f"*[Testo troncato a {cut} caratteri su {total} totali: {resume_hint(cut + 1)}]*"
    omitted = (
        f"*[Omessi i caratteri {_MAX_TEXT_LENGTH + 1}-{start} su {total} totali: il testo riprende "
        f"dalla parte finale; {resume_hint(_MAX_TEXT_LENGTH + 1)}]*"
    )
    body = text[:_MAX_TEXT_LENGTH] + "\n\n---\n" + omitted + "\n\n" + text[start:end]
    if end < total:
        return body, (
            f"*[Testo troncato a {end} caratteri su {total} totali dopo la parte finale: "
            f"{resume_hint(end + 1)}]*"
        )
    return body, ""


def format_full(
    case_number: str,
    text: str,
    ecli: str,
    *,
    case_ref: str = "",
    date: str = "",
    da_carattere: int = 1,
) -> str:
    """Render a decision: header and text.

    `case_number` is the first heading (the CELEX for the tools); `case_ref` is the
    official case number ("C-311/18") and `date` the decision date, when known.
    `da_carattere` > 1 renders the window of the text that starts there.
    """
    body, note = _excerpt(text, da_carattere)
    lines = [f"# {case_number}"]
    if case_ref:
        lines.append(f"**Causa**: {case_ref}")
    if ecli:
        lines.append(f"**ECLI**: {ecli}")
    if date:
        lines.append(f"**Data**: {date}")
    lines.append("")
    lines.append(body)
    if note:
        lines.append(f"\n---\n{note}")
    return "\n".join(lines)


async def search_giurisprudenza(
    keywords: list[str],
    court: str = "",
    doc_type: str = "",
    year_from: str = "",
    year_to: str = "",
    materia: str = "",
    limit: int = 10,
    required_terms: list[str] | None = None,
) -> list[CaseResult]:
    """Search CELLAR titles.

    `keywords` are alternatives (OR). `materia` and every entry of `required_terms`
    narrow the search (AND): the title must also contain one keyword of the materia
    and every required term. One row per decision is returned, newest first.
    """
    required_groups: list[list[str]] = []
    if materia and materia in MATERIE_KEYWORDS:
        required_groups.append(MATERIE_KEYWORDS[materia])
    required_groups.extend([term] for term in (required_terms or []))

    court_code = CORTI.get(court, "")
    doc_type_code = TIPI_DOCUMENTO.get(doc_type, doc_type)

    query = _build_search_query(
        keywords=list(keywords),
        court_code=court_code,
        doc_type=doc_type_code,
        year_from=year_from,
        year_to=year_to,
        limit=limit * _OVERFETCH,
        required_groups=required_groups,
    )
    bindings = await _execute_sparql(query)
    return _parse_results(bindings)[:limit]


async def fetch_sentenza_text(cellar_uri: str) -> str:
    html = await _fetch_html(cellar_uri)
    return _parse_html_text(html)


_CELEX_RE = r"6\d{4}[A-Z]{2}\d{4}"
_CELEX_IN_URI = re.compile(rf"/resource/celex/({_CELEX_RE})\b")
_CELEX_AT_START = re.compile(rf"\A\s*({_CELEX_RE})\b")


def celex_of(cellar_uri: str, text: str = "") -> str:
    """CELEX of a decision, from a `/resource/celex/` alias or from the first line of its text."""
    m = _CELEX_IN_URI.search(cellar_uri) or _CELEX_AT_START.match(text)
    return m.group(1) if m else ""


async def fetch_case_metadata(celex: str) -> dict[str, str]:
    """Official case number, ECLI and date of a decision, read from CELLAR by CELEX.

    Best effort: the text is shown even when this lookup fails, so any failure
    returns an empty dict.
    """
    if not re.fullmatch(_CELEX_RE, celex):
        return {}
    query = f"""PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

SELECT ?ecli ?date ?type_code ?year ?case_num
WHERE {{
  ?work cdm:resource_legal_id_celex "{celex}"^^xsd:string .
  ?work cdm:work_date_document ?date .
  ?work cdm:resource_legal_type ?type_code .
  ?work cdm:resource_legal_year ?year .
  ?work cdm:resource_legal_number_natural_celex ?case_num .
  OPTIONAL {{ ?work cdm:case-law_ecli ?ecli . }}
}}
LIMIT 10"""
    try:
        rows = await _execute_sparql(query)
        # A CELEX can have several works, only some with the ECLI: prefer one that has it.
        row = next((r for r in rows if r.get("ecli", {}).get("value")), rows[0])
        meta = {
            "case_ref": official_case_number(
                row["type_code"]["value"], row["case_num"]["value"], row["year"]["value"]
            ),
            "date": row["date"]["value"],
            "ecli": row.get("ecli", {}).get("value", ""),
        }
    except Exception:
        return {}
    return {k: v for k, v in meta.items() if isinstance(v, str)}

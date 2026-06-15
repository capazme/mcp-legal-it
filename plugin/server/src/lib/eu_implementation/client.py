"""Client for EU -> Italy implementation mapping (national transposition measures).

Data source:
- SPARQL endpoint: https://publications.europa.eu/webapi/rdf/sparql (CELLAR CDM ontology)

This reuses the same CELLAR SPARQL infrastructure as the CGUE client. It maps EU
directives to the Italian acts that transpose them (and back), via the CDM
"national implementing measure" (MNE) predicates.

Key predicate:
  cdm:measure_national_implementing_implements_resource_legal
    links an MNE (national implementing measure) work -> the EU directive work.

MNE metadata predicates:
  measure_national_implementing_implemented_by_country -> country authority URI
  measure_national_implementing_type_act               -> e.g. "Decreto legislativo"
  resource_legal_id_local                              -> BEST-EFFORT (often the act
                                                          number "177", sometimes a
                                                          full ref string)
  measure_national_implementing_number_official_journal -> Gazzetta Ufficiale number
  measure_national_implementing_date_official_journal   -> GU date (unreliable)
  resource_legal_date_entry-into-force                  -> entry into force date
  work_title                                            -> title (IT for ITA MNE)
  resource_legal_id_celex                               -> MNE CELEX
                                                          7{YYYY}L{NNNN}{COUNTRY}_{nimId}

Directive metadata:
  resource_legal_id_celex      -> directive CELEX 3{YYYY}L{NNNN}
  directive_date_transposition -> transposition deadline (may be multi-valued)
  expression_title (IT)        -> canonical Italian title

CAVEATS handled here:
- One MNE can transpose MANY directives (return all, no 1:1 assumption).
- The SPARQL join is constrained via the directive work FIRST (an unconstrained
  ?mne join times out).
- An MNE is metadata only — use cite_law for the actual act text.
- A REGULATION (e.g. 32016R0679 GDPR) has no MNE -> directly applicable, no
  transposition.

CELEX literals REQUIRE ^^xsd:string in SPARQL.
"""

import re
from dataclasses import dataclass, field

import httpx

from src.lib._http import retry_request

_SPARQL_URL = "https://publications.europa.eu/webapi/rdf/sparql"
_TIMEOUT = httpx.Timeout(45.0, connect=15.0)

_LANG_ITA = "http://publications.europa.eu/resource/authority/language/ITA"
_COUNTRY_BASE = "http://publications.europa.eu/resource/authority/country/"

_HEADERS_SPARQL = {
    "Accept": "application/sparql-results+json",
    "User-Agent": "Mozilla/5.0 (compatible; mcp-legal-it/2.1)",
}

# Italian act-type keywords -> canonical label used to disambiguate human refs.
# Maps common abbreviations to the substring expected in MNE titles / type_act.
_ACT_TYPE_ALIASES: dict[str, str] = {
    "d.lgs.": "decreto legislativo",
    "d.lgs": "decreto legislativo",
    "dlgs": "decreto legislativo",
    "decreto legislativo": "decreto legislativo",
    "d.l.": "decreto-legge",
    "dl": "decreto-legge",
    "decreto-legge": "decreto-legge",
    "decreto legge": "decreto-legge",
    "legge": "legge",
    "l.": "legge",
    "dpr": "decreto del presidente della repubblica",
    "d.p.r.": "decreto del presidente della repubblica",
}


@dataclass
class ImplementationResult:
    """An Italian national implementing measure (MNE) transposing an EU directive."""

    mne_celex: str = ""          # "72019L0790ITA_202107973"
    act_type: str = ""           # "Decreto legislativo"
    id_local: str = ""           # "177" (best-effort)
    oj_number: str = ""          # Gazzetta Ufficiale number
    oj_date: str = ""            # GU date (often unreliable)
    entry_into_force: str = ""   # entry-into-force date
    title: str = ""              # IT title
    directive_celex: str = ""    # the directive this row transposes
    cellar_uri: str = ""         # MNE work URI


@dataclass
class BasisResult:
    """An EU directive that is the legal basis of an Italian implementing measure."""

    directive_celex: str = ""              # "32019L0790"
    directive_title: str = ""              # IT title from expression
    transposition_deadline: str = ""       # earliest directive_date_transposition
    cellar_uri: str = ""                   # directive work URI


@dataclass
class MappingResult:
    """Outcome of an EU<->IT mapping lookup."""

    success: bool
    direction: str  # "eu_to_it" or "it_to_eu"
    error_type: str | None = None  # "source_down", "no_results", "regulation", "bad_input", None
    error_message: str = ""
    query_ref: str = ""
    celex: str = ""  # the resolved CELEX that was queried
    implementations: list[ImplementationResult] = field(default_factory=list)
    bases: list[BasisResult] = field(default_factory=list)


# ---------------------------------------------------------------------------
# CELEX / reference parsing
# ---------------------------------------------------------------------------

_DIRECTIVE_CELEX_RE = re.compile(r"^3\d{4}[LR]\d{4}$", re.IGNORECASE)
_MNE_CELEX_RE = re.compile(r"^7\d{4}[LR]\d{4}[A-Z]{3}_\d+$", re.IGNORECASE)
# Human directive ref: "direttiva 2019/790", "dir 2019/790/UE", "2019/790"
_HUMAN_DIR_RE = re.compile(
    r"(?:dirett?iva|dir\.?|regolamento|reg\.?)?\s*\(?(?:ue|ce|cee|euratom)?\)?\s*"
    r"(?:n\.?\s*)?(\d{4})/(\d{1,4})",
    re.IGNORECASE,
)
# Italian act ref: "D.Lgs. 177/2021", "decreto legislativo n. 138/2024", "legge 90/2024"
_HUMAN_ACT_RE = re.compile(
    r"(?:n\.?\s*)?(\d{1,5})\s*(?:/|del\s+\d{1,2}\s+\w+\s+|,?\s*)(\d{4})",
)


def build_directive_celex(ref: str) -> str | None:
    """Build a directive/regulation CELEX from a human ref or accept an existing CELEX.

    Accepts:
      - "32019L0790" (already a directive CELEX) -> returned uppercased
      - "direttiva 2019/790", "dir 2019/790/UE", "2019/790" -> "32019L0790"
      - "regolamento 2016/679", "reg 2016/679/UE" -> "32016R0679"

    Reuses the 3{year}{L|R}{number.zfill(4)} convention (cf. visualex _build_celex).
    Returns None if no year/number pair can be parsed.
    """
    if not ref:
        return None
    candidate = ref.strip()

    # Already a directive/regulation CELEX?
    if _DIRECTIVE_CELEX_RE.match(candidate):
        return candidate.upper()

    low = candidate.lower()
    is_regulation = bool(re.search(r"regolament|reg\.|reg\b|\bR\d", low)) and not re.search(
        r"dirett|dir\.|dir\b", low
    )
    type_letter = "R" if is_regulation else "L"

    m = _HUMAN_DIR_RE.search(candidate)
    if not m:
        return None
    year, number = m.group(1), m.group(2)
    return f"3{year}{type_letter}{number.zfill(4)}"


def parse_mne_celex(ref: str) -> str | None:
    """Return the ref if it is a valid MNE CELEX (7YYYY[LR]NNNNCCC_nimId), else None."""
    if ref and _MNE_CELEX_RE.match(ref.strip()):
        return ref.strip().upper()
    return None


def parse_italian_act_ref(ref: str) -> tuple[str, str, str] | None:
    """Parse an Italian act ref like 'D.Lgs. 177/2021' or 'legge n. 90/2024'.

    Returns (act_type_keyword, number, year), or None if not parseable.
    act_type_keyword is a canonical substring ("decreto legislativo", "legge", ...)
    or "" when the type is not recognised.
    """
    if not ref:
        return None
    low = ref.strip().lower()

    act_type = ""
    for alias, canonical in _ACT_TYPE_ALIASES.items():
        if low.startswith(alias):
            act_type = canonical
            break

    m = _HUMAN_ACT_RE.search(ref)
    if not m:
        return None
    number, year = m.group(1), m.group(2)
    if len(year) != 4:
        return None
    return act_type, number, year


# ---------------------------------------------------------------------------
# SPARQL query builders
# ---------------------------------------------------------------------------

_PREFIXES = (
    "PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>\n"
    "PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>"
)


def build_eu_to_it_query(directive_celex: str, country: str = "ITA", limit: int = 50) -> str:
    """MNE rows for the given directive CELEX, filtered to one country.

    The join is constrained via the directive work FIRST (an unconstrained ?mne
    join times out). The MNE CELEX is optionally pulled and filtered to the rows
    whose CELEX prefix matches "7{dir-body}{COUNTRY}" so we don't surface CELEX
    values that belong to OTHER directives the same MNE transposes.
    """
    country = country.upper()
    country_uri = f"{_COUNTRY_BASE}{country}"
    # MNE CELEX prefix: directive CELEX with leading 3 -> 7, then country.
    mne_prefix = f"7{directive_celex[1:]}{country}"
    return f"""{_PREFIXES}

SELECT DISTINCT ?mne ?mne_celex ?act_type ?id_local ?oj_num ?oj_date ?eif ?title
WHERE {{
  ?dir cdm:resource_legal_id_celex "{directive_celex}"^^xsd:string .
  ?mne cdm:measure_national_implementing_implements_resource_legal ?dir .
  ?mne cdm:measure_national_implementing_implemented_by_country <{country_uri}> .
  OPTIONAL {{ ?mne cdm:measure_national_implementing_type_act ?act_type . }}
  OPTIONAL {{ ?mne cdm:resource_legal_id_local ?id_local . }}
  OPTIONAL {{ ?mne cdm:measure_national_implementing_number_official_journal ?oj_num . }}
  OPTIONAL {{ ?mne cdm:measure_national_implementing_date_official_journal ?oj_date . }}
  OPTIONAL {{ ?mne cdm:resource_legal_date_entry-into-force ?eif . }}
  OPTIONAL {{ ?mne cdm:work_title ?title . }}
  OPTIONAL {{
    ?mne cdm:resource_legal_id_celex ?mne_celex .
    FILTER(STRSTARTS(STR(?mne_celex), "{mne_prefix}"))
  }}
}}
LIMIT {limit}"""


def build_it_to_eu_from_mne_celex(mne_celex: str, limit: int = 20) -> str:
    """Directives that an MNE (given by its CELEX) transposes."""
    return f"""{_PREFIXES}

SELECT DISTINCT ?dir_celex ?title ?transp ?dir
WHERE {{
  ?mne cdm:resource_legal_id_celex "{mne_celex}"^^xsd:string .
  ?mne cdm:measure_national_implementing_implements_resource_legal ?dir .
  ?dir cdm:resource_legal_id_celex ?dir_celex .
  OPTIONAL {{ ?dir cdm:directive_date_transposition ?transp . }}
  OPTIONAL {{
    ?exp cdm:expression_belongs_to_work ?dir .
    ?exp cdm:expression_uses_language <{_LANG_ITA}> .
    ?exp cdm:expression_title ?title .
  }}
}}
LIMIT {limit}"""


def build_it_to_eu_from_act(number: str, year: str, country: str = "ITA", limit: int = 30) -> str:
    """Directives transposed by an Italian act identified by number + year.

    The MNE's resource_legal_id_local is BEST-EFFORT and comes in two shapes,
    so the match is two-branch (both year-constrained to avoid false positives):
      - bare number ("177") -> require the year to appear in work_title or
        entry-into-force (otherwise a bare "138" of a different year matches);
      - full string ("Decreto legislativo 4 settembre 2024, n. 138,") -> require
        an "n. {number}," / "n. {number} " word boundary AND the year, so "90"
        does not match "190".
    Both shapes were confirmed against live CELLAR during recon (177/2021,
    138/2024 NIS2). The join is anchored on the MNE (id_local is indexed), which
    stays fast (~0.2s) even without the directive-first constraint.
    """
    country = country.upper()
    country_uri = f"{_COUNTRY_BASE}{country}"
    return f"""{_PREFIXES}

SELECT DISTINCT ?mne_celex ?dir_celex ?title ?transp ?act_type ?eif ?dir
WHERE {{
  ?mne cdm:measure_national_implementing_implemented_by_country <{country_uri}> .
  ?mne cdm:resource_legal_id_local ?id_local .
  OPTIONAL {{ ?mne cdm:work_title ?wtitle . }}
  OPTIONAL {{ ?mne cdm:resource_legal_date_entry-into-force ?eif . }}
  FILTER(
    (STR(?id_local) = "{number}" && (CONTAINS(STR(COALESCE(?wtitle, "")), "{year}") || CONTAINS(STR(COALESCE(?eif, "")), "{year}")))
    || (CONTAINS(LCASE(STR(?id_local)), "n. {number},") && CONTAINS(STR(?id_local), "{year}"))
    || (CONTAINS(LCASE(STR(?id_local)), "n. {number} ") && CONTAINS(STR(?id_local), "{year}"))
  )
  ?mne cdm:measure_national_implementing_implements_resource_legal ?dir .
  ?dir cdm:resource_legal_id_celex ?dir_celex .
  OPTIONAL {{ ?mne cdm:resource_legal_id_celex ?mne_celex . }}
  OPTIONAL {{ ?mne cdm:measure_national_implementing_type_act ?act_type . }}
  OPTIONAL {{ ?dir cdm:directive_date_transposition ?transp . }}
  OPTIONAL {{
    ?exp cdm:expression_belongs_to_work ?dir .
    ?exp cdm:expression_uses_language <{_LANG_ITA}> .
    ?exp cdm:expression_title ?title .
  }}
}}
LIMIT {limit}"""


def build_directive_exists_query(directive_celex: str) -> str:
    """Probe whether a CELEX work exists and its IT title + transposition deadline."""
    return f"""{_PREFIXES}

SELECT DISTINCT ?dir ?title ?transp
WHERE {{
  ?dir cdm:resource_legal_id_celex "{directive_celex}"^^xsd:string .
  OPTIONAL {{ ?dir cdm:directive_date_transposition ?transp . }}
  OPTIONAL {{
    ?exp cdm:expression_belongs_to_work ?dir .
    ?exp cdm:expression_uses_language <{_LANG_ITA}> .
    ?exp cdm:expression_title ?title .
  }}
}}
LIMIT 5"""


# ---------------------------------------------------------------------------
# SPARQL execution + parsing
# ---------------------------------------------------------------------------

async def _execute_sparql(query: str) -> list[dict]:
    async with httpx.AsyncClient(timeout=_TIMEOUT, headers=_HEADERS_SPARQL) as client:
        resp = await retry_request(client, "POST", _SPARQL_URL, data={"query": query})
        data = resp.json()
        return data["results"]["bindings"]


def _val(binding: dict, key: str) -> str:
    return binding.get(key, {}).get("value", "")


def parse_implementations(bindings: list[dict], directive_celex: str) -> list[ImplementationResult]:
    """Collapse MNE bindings into ImplementationResult, deduped by MNE work URI.

    A single MNE can appear in several rows (multi-valued OPTIONAL fields). We
    key on the MNE work URI and keep the first non-empty value for each field.
    """
    by_mne: dict[str, ImplementationResult] = {}
    order: list[str] = []
    for b in bindings:
        mne_uri = _val(b, "mne")
        key = mne_uri or _val(b, "mne_celex") or str(len(order))
        if key not in by_mne:
            by_mne[key] = ImplementationResult(directive_celex=directive_celex, cellar_uri=mne_uri)
            order.append(key)
        row = by_mne[key]
        row.mne_celex = row.mne_celex or _val(b, "mne_celex")
        row.act_type = row.act_type or _val(b, "act_type")
        row.id_local = row.id_local or _val(b, "id_local")
        row.oj_number = row.oj_number or _val(b, "oj_num")
        row.oj_date = row.oj_date or _val(b, "oj_date")
        row.entry_into_force = row.entry_into_force or _val(b, "eif")
        row.title = row.title or _val(b, "title")
    return [by_mne[k] for k in order]


def parse_bases(bindings: list[dict]) -> list[BasisResult]:
    """Collapse directive bindings into BasisResult, deduped by directive CELEX.

    directive_date_transposition can be multi-valued; we keep the EARLIEST date
    (the binding deadline) as the headline.
    """
    by_celex: dict[str, BasisResult] = {}
    order: list[str] = []
    transp_dates: dict[str, list[str]] = {}
    for b in bindings:
        celex = _val(b, "dir_celex")
        if not celex:
            continue
        if celex not in by_celex:
            by_celex[celex] = BasisResult(directive_celex=celex, cellar_uri=_val(b, "dir"))
            order.append(celex)
            transp_dates[celex] = []
        row = by_celex[celex]
        row.directive_title = row.directive_title or _val(b, "title")
        row.cellar_uri = row.cellar_uri or _val(b, "dir")
        transp = _val(b, "transp")
        if transp:
            transp_dates[celex].append(transp)
    for celex in order:
        dates = sorted(d for d in transp_dates[celex] if d)
        if dates:
            by_celex[celex].transposition_deadline = dates[0]
    return [by_celex[k] for k in order]


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

def _clean_act_number(id_local: str) -> str:
    """Best-effort act number from a messy id_local.

    "177" -> "177"; "Decreto legislativo 4 settembre 2024, n. 138," -> "138".
    Returns "" if nothing usable can be extracted.
    """
    if not id_local:
        return ""
    raw = id_local.strip()
    if raw.isdigit():
        return raw
    m = re.search(r"\bn\.?\s*(\d{1,5})", raw, re.IGNORECASE)
    if m:
        return m.group(1)
    return ""


def format_implementation(impl: ImplementationResult) -> str:
    lines: list[str] = []
    heading = impl.act_type or "Misura nazionale di attuazione"
    number = _clean_act_number(impl.id_local)
    if number:
        heading = f"{heading} n. {number}"
    lines.append(f"### {heading}")
    if impl.title:
        lines.append(f"**Titolo**: {impl.title}")
    gu_parts = []
    if impl.oj_number:
        gu_parts.append(f"n. {impl.oj_number}")
    if impl.oj_date and not impl.oj_date.startswith("1001"):
        gu_parts.append(f"del {impl.oj_date}")
    if gu_parts:
        lines.append(f"**Gazzetta Ufficiale**: {' '.join(gu_parts)}")
    if impl.entry_into_force:
        lines.append(f"**Entrata in vigore**: {impl.entry_into_force}")
    if impl.mne_celex:
        lines.append(f"**CELEX misura nazionale**: {impl.mne_celex}")
    lines.append(f"**Direttiva recepita**: {impl.directive_celex}")
    return "\n".join(lines)


def format_basis(basis: BasisResult) -> str:
    lines = [f"### {basis.directive_celex}"]
    if basis.directive_title:
        lines.append(f"**Titolo**: {basis.directive_title}")
    if basis.transposition_deadline:
        lines.append(f"**Termine di trasposizione**: {basis.transposition_deadline}")
    if basis.cellar_uri:
        lines.append(f"**CELLAR URI**: `{basis.cellar_uri}`")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# High-level operations
# ---------------------------------------------------------------------------

async def get_italian_implementation(directive_ref: str, country: str = "ITA", limit: int = 50) -> MappingResult:
    """Resolve a directive ref/CELEX -> Italian transposing act(s)."""
    celex = build_directive_celex(directive_ref)
    if not celex:
        return MappingResult(
            success=False, direction="eu_to_it", error_type="bad_input",
            query_ref=directive_ref,
            error_message="Riferimento non riconosciuto. Usare un CELEX (es. 32019L0790) o un riferimento umano (es. 'direttiva 2019/790').",
        )

    # Regulation -> no national transposition.
    if celex[5].upper() == "R":
        return MappingResult(
            success=False, direction="eu_to_it", error_type="regulation",
            query_ref=directive_ref, celex=celex,
            error_message="È un regolamento UE, direttamente applicabile: nessuna trasposizione nazionale.",
        )

    try:
        bindings = await _execute_sparql(build_eu_to_it_query(celex, country=country, limit=limit))
    except Exception as exc:
        return MappingResult(
            success=False, direction="eu_to_it", error_type="source_down",
            query_ref=directive_ref, celex=celex, error_message=str(exc),
        )

    impls = parse_implementations(bindings, celex)
    if not impls:
        return MappingResult(
            success=False, direction="eu_to_it", error_type="no_results",
            query_ref=directive_ref, celex=celex,
        )
    return MappingResult(
        success=True, direction="eu_to_it", query_ref=directive_ref,
        celex=celex, implementations=impls,
    )


async def get_eu_basis(act_ref: str, country: str = "ITA", limit: int = 30) -> MappingResult:
    """Resolve an Italian act ref or MNE CELEX -> EU directive(s) it transposes."""
    mne_celex = parse_mne_celex(act_ref)
    if mne_celex:
        try:
            bindings = await _execute_sparql(build_it_to_eu_from_mne_celex(mne_celex, limit=limit))
        except Exception as exc:
            return MappingResult(
                success=False, direction="it_to_eu", error_type="source_down",
                query_ref=act_ref, celex=mne_celex, error_message=str(exc),
            )
        bases = parse_bases(bindings)
        if not bases:
            return MappingResult(
                success=False, direction="it_to_eu", error_type="no_results",
                query_ref=act_ref, celex=mne_celex,
            )
        return MappingResult(
            success=True, direction="it_to_eu", query_ref=act_ref,
            celex=mne_celex, bases=bases,
        )

    parsed = parse_italian_act_ref(act_ref)
    if not parsed:
        return MappingResult(
            success=False, direction="it_to_eu", error_type="bad_input",
            query_ref=act_ref,
            error_message="Riferimento non riconosciuto. Usare un atto italiano (es. 'D.Lgs. 177/2021') o un CELEX di misura nazionale (es. 72019L0790ITA_202107973).",
        )
    _act_type, number, year = parsed
    try:
        bindings = await _execute_sparql(build_it_to_eu_from_act(number, year, country=country, limit=limit))
    except Exception as exc:
        return MappingResult(
            success=False, direction="it_to_eu", error_type="source_down",
            query_ref=act_ref, error_message=str(exc),
        )
    bases = parse_bases(bindings)
    if not bases:
        return MappingResult(
            success=False, direction="it_to_eu", error_type="no_results",
            query_ref=act_ref,
        )
    return MappingResult(
        success=True, direction="it_to_eu", query_ref=act_ref, bases=bases,
    )


async def elenco_misure_nazionali(directive_ref: str, country: str = "ITA", limit: int = 50) -> MappingResult:
    """Alias of get_italian_implementation for an arbitrary country (default ITA)."""
    return await get_italian_implementation(directive_ref, country=country, limit=limit)

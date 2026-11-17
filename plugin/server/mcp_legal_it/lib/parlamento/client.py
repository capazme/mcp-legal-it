"""Client for Italian parliamentary open data (dati.senato.it / dati.camera.it).

Data sources:
- Senato SPARQL: https://dati.senato.it/sparql (Virtuoso, OSR ontology).
  GET ONLY — POST receives a 403 WAF error page regardless of User-Agent.
- Camera SPARQL: https://dati.camera.it/sparql (Virtuoso, OCD ontology).

Data model: each osr:Ddl resource is one *fase* (a reading in one chamber,
e.g. S.1939 then C.3053) and osr:idDdl is the shared identity linking the fasi
of the same bill across the navette. The Senato dataset indexes the fasi of
BOTH chambers, so it alone reconstructs the full bicameral iter; the Camera
endpoint adds detail (statoIter timeline, stampato PDFs) for C.* fasi.

Quirks verified live (2026-08-25):
- The Senato WAF blocks bif:contains expressions combining quoted terms with
  'or'/'and' operators (403, SQL-injection heuristics) and Virtuoso rejects
  the UNION workarounds (SP031/5xx). Title search therefore uses plain
  FILTER(CONTAINS(LCASE(...))) with &&/|| — ~2-3s on a legislature, reliable.
- Senato literals are typed xsd:string (dates included): plain-literal
  matching silently returns zero rows — always compare with ^^xsd:string.
- osr:dataLegge carries the sentinel 2100-01-01 for constitutional laws
  awaiting confirmation/referendum: blank it, never sort on it.
- senato.it scheda pages answer HTTP 202 (WAF challenge, like EUR-Lex):
  scheda links are emitted for the human reader, never fetched.
- Camera dc:date is YYYYMMDD; dc:title embeds the fase prefix ("S. 1939. -"),
  surrounding quotes and HTML entities.
- Twin bills are NOT a navette: C.1084 and S.1116 share the title but have
  different idDdl. Only idDdl links the fasi of one bill.
- Third readings carry a suffix and unified texts merge the numbers —
  "S.562-B", "C.813-B", "S.93-338-353-B" are real osr:fase values, and the
  Camera identifies the -B reading as dc:identifier "813-B" (a distinct atto).

Verified live 2026-11-17 (issue #185):
- The Senato WAF answers 403 to any GET whose request target (path plus the
  percent-encoded query string) exceeds 2048 bytes: 2048 answers 200, 2049
  answers 403, whatever the query says. With POST refused too, a search has
  to fit in the URL: queries are sent with their whitespace collapsed and a
  longer one is refused locally (QueryTooLong) instead of reaching the WAF.
- Virtuoso on dati.senato.it rejects BIND (SP030), so LCASE(STR(?titolo))
  cannot be computed once and is repeated in every CONTAINS.
"""

import html
import re
from dataclasses import dataclass, field

import httpx
from mcp_legal_it.core._http import async_client

from mcp_legal_it.lib._http import retry_request

SENATO_SPARQL_URL = "https://dati.senato.it/sparql"
CAMERA_SPARQL_URL = "https://dati.camera.it/sparql"
_TIMEOUT = httpx.Timeout(30.0, connect=10.0)

_HEADERS = {
    "Accept": "application/sparql-results+json",
    "User-Agent": "Mozilla/5.0 (compatible; mcp-legal-it/2.12)",
}

#: Bump when a new legislature starts (data update, PATCH release).
LEGISLATURA_CORRENTE = 19

#: osr:statoDdl values of a fase still moving through parliament. The other
#: 12 observed values (approvato, respinto, ritirato, assorbito, D-L decaduto,
#: appr. definit. Legge, ...) are terminal for that fase.
STATI_PENDENTI: frozenset[str] = frozenset({
    "da assegn. a commis.",
    "assegnato (no esame)",
    "esame in comm.",
    "in relazione",
    "concluso l'esame",
    "all'esame assemblea",
    "rinviato ass.->comm.",
})

_SENTINEL_DATA_LEGGE = "2100-01-01"
_MAX_TITLE_LENGTH = 300

#: Longest request target (path + percent-encoded query string) the Senato
#: WAF lets through: one byte more and it answers 403 (verified 2026-11-17).
SENATO_MAX_REQUEST_TARGET = 2048


class NoValidSearchTerms(ValueError):
    """Every search term vanished in sanitisation.

    A dedicated type: catching bare ValueError would also swallow
    json.JSONDecodeError (its subclass) from a broken endpoint response,
    turning a source failure into a false "no results".
    """


class QueryTooLong(ValueError):
    """The query would not fit in the URL the Senato WAF accepts.

    Raised before any request: sent anyway, it would come back as a 403 page
    and read as "Senato unreachable", while the cause is the search itself.
    """


@dataclass
class DdlFase:
    """One reading of a bill in one chamber (an osr:Ddl resource)."""

    fase: str                 # "S.1939" / "C.3053"
    ramo: str                 # "S" | "C"
    id_ddl: str               # shared bill identity across fasi ("55442")
    id_fase: str              # last segment of the ddl URI — keys the scheda page
    titolo: str
    stato: str                # osr:statoDdl ("esame in comm.", "appr. definit. Legge", ...)
    data_stato: str           # ISO date of the current stato
    data_presentazione: str = ""
    iniziativa: str = ""
    natura: str = ""
    presentato_trasmesso: str = ""   # "presentato" | "trasmesso"
    progressivo: str = ""            # position in the navette ("1", "2", ...)
    numero_legge: str = ""           # set when the bill became law
    data_legge: str = ""
    legislatura: int = LEGISLATURA_CORRENTE


@dataclass
class CameraIter:
    """Camera-side detail for a C.* fase (from dati.camera.it)."""

    numero: str               # AC number ("3053")
    titolo: str
    data_presentazione: str = ""
    timeline: list[tuple[str, str]] = field(default_factory=list)  # (ISO date, label)
    pdf_urls: list[str] = field(default_factory=list)


def _sanitize_phrase(text: str) -> str:
    """Strip characters that would break out of a double-quoted SPARQL literal.

    Apostrophes are legal inside "..." literals and appear in the real data
    ("all'esame assemblea", "codice dell'ambiente") — removing them would make
    exact-match filters and title searches silently return zero rows.
    """
    cleaned = re.sub(r'["\\\x00-\x1f]', " ", text)
    return re.sub(r"\s+", " ", cleaned).strip()


def _title_filter_expr(groups: list[list[str]]) -> str:
    """FILTER body for the title search: OR (||) of AND-groups (&&).

    Deliberately NOT bif:contains: the Senato WAF 403s expressions that mix
    quoted terms with 'or'/'and' operators (SQL-injection heuristics), and
    Virtuoso rejects the UNION workarounds. Plain CONTAINS over one
    legislature's titles answers in ~2-3s.
    """
    parts = []
    for group in groups:
        terms = [
            t for t in (_sanitize_phrase(term).lower() for term in group)
            # A term with no alphanumeric content (e.g. a bare "-") trips the
            # Senato WAF (403, observed live) and matches nothing useful.
            if t and re.search(r"[0-9a-zà-ÿ]", t)
        ]
        if terms:
            parts.append(
                "(" + " && ".join(f'CONTAINS(LCASE(STR(?titolo)), "{t}")' for t in terms) + ")"
            )
    return " || ".join(parts)


_SELECT_FASI = """\
SELECT DISTINCT ?ddl ?fase ?ramo ?idDdl ?leg ?prog ?titolo ?stato ?dataStato ?dataPres ?iniziativa ?natura ?presTrasm ?numeroLegge ?dataLegge
WHERE {{
{where_head}
  ?ddl a osr:Ddl ;
       osr:fase ?fase ;
       osr:ramo ?ramo ;
       osr:idDdl ?idDdl ;
       osr:legislatura ?leg ;
       osr:titolo ?titolo ;
       osr:statoDdl ?stato ;
       osr:dataStatoDdl ?dataStato .
  OPTIONAL {{ ?ddl osr:progressivoIter ?prog }}
  OPTIONAL {{ ?ddl osr:dataPresentazione ?dataPres }}
  OPTIONAL {{ ?ddl osr:descrIniziativa ?iniziativa }}
  OPTIONAL {{ ?ddl osr:natura ?natura }}
  OPTIONAL {{ ?ddl osr:presentatoTrasmesso ?presTrasm }}
  OPTIONAL {{ ?ddl osr:numeroLegge ?numeroLegge . ?ddl osr:dataLegge ?dataLegge }}
{filters}
}}
{tail}"""

_PREFIXES = """\
PREFIX osr: <http://dati.senato.it/osr/>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
"""

_LITERAL_OR_SPACE = re.compile(r'("[^"]*")|\s+')


def _compact(query: str) -> str:
    """Collapse whitespace outside string literals.

    Every byte of the query counts against the 2048-byte request target the
    Senato WAF accepts: the indentation of the templates alone costs ~110
    bytes once percent-encoded. Literals are left untouched.
    """
    return _LITERAL_OR_SPACE.sub(lambda m: m.group(1) or " ", query).strip()


def _build_search_query(
    groups: list[list[str]],
    legislatura: int,
    ramo: str = "",
    stato: str = "",
    solo_pendenti: bool = False,
    limit: int = 10,
) -> str:
    if isinstance(groups, str) or any(isinstance(group, str) for group in groups):
        # A bare string iterates as characters: "codice della strada" became
        # 17 one-letter CONTAINS clauses OR-ed together, and a 403 (#185).
        raise TypeError("groups must be a list of term lists, e.g. [['codice della strada']]")
    filters = []
    expr = _title_filter_expr(groups)
    if groups and not expr:
        # All terms vanished in sanitisation: without this guard the query
        # would run unfiltered and present the latest DDL as search results.
        raise NoValidSearchTerms("Nessun termine di ricerca valido dopo la sanificazione.")
    if expr:
        filters.append(f"  FILTER({expr})")
    if ramo:
        filters.append(f'  FILTER(?ramo = "{_sanitize_phrase(ramo)}"^^xsd:string)')
    if stato:
        filters.append(f'  FILTER(?stato = "{_sanitize_phrase(stato)}"^^xsd:string)')
    if solo_pendenti:
        stati = ", ".join(f'"{s}"^^xsd:string' for s in sorted(STATI_PENDENTI))
        filters.append(f"  FILTER(?stato IN ({stati}))")

    body = _SELECT_FASI.format(
        where_head=f"  ?ddl osr:legislatura {int(legislatura)} .",
        filters="\n".join(filters),
        tail=f"ORDER BY DESC(?dataStato) LIMIT {int(limit)}",
    )
    return _compact(_PREFIXES + body)


def _build_iter_query(
    fase: str = "",
    id_ddl: str = "",
    legislatura: int = LEGISLATURA_CORRENTE,
) -> str:
    """All fasi of one bill, joined through idDdl in a single query."""
    if fase:
        where_head = (
            f"  ?rif a osr:Ddl ;\n"
            f"       osr:legislatura {int(legislatura)} ;\n"
            f'       osr:fase "{_sanitize_phrase(fase)}"^^xsd:string ;\n'
            f"       osr:idDdl ?idDdl .\n"
        )
    else:
        where_head = f"  ?ddl osr:idDdl {int(id_ddl)} .\n"
    body = _SELECT_FASI.format(where_head=where_head, filters="", tail="ORDER BY ?prog")
    return _compact(_PREFIXES + body)


def parse_atto_input(atto: str) -> tuple[str, str]:
    """Normalize user input to ("fase", "S.1939") or ("id_ddl", "55442").

    Accepts "S.1939", "s 1939", "AS 1939", "C.3053", "AC 3053"; bare digits
    are read as an idDdl. Raises ValueError on anything else.
    """
    text = atto.strip()
    if re.fullmatch(r"\d+", text):
        return ("id_ddl", text)
    # The body admits navette suffixes and unified-text numbering, both real:
    # "S.562-B", "C.813-B", "S.93-338-353-B", "S.926-bis". Matching is exact
    # on typed literals, so casing must mirror the dataset: single-letter
    # suffixes are uppercase (-B), multi-letter stralcio suffixes lowercase
    # (-bis, -ter, -quater, -quinquies).
    match = re.fullmatch(r"(?i)\s*A?\s*([SC])[.\s]*(\d+(?:-[0-9A-Za-z]+)*)\s*", text)
    if match:
        segments = [
            seg if seg.isdigit() else (seg.upper() if len(seg) == 1 else seg.lower())
            for seg in match.group(2).split("-")
        ]
        return ("fase", f"{match.group(1).upper()}.{'-'.join(segments)}")
    raise ValueError(
        f"Atto '{atto}' non riconosciuto: usare 'S.1939', 'C.3053', 'AS 1939', "
        "'AC 3053', 'S.562-B' oppure un idDdl numerico."
    )


def _senato_params(query: str) -> dict[str, str]:
    return {"query": query, "format": "application/sparql-results+json"}


def senato_request_target(query: str) -> bytes:
    """Path plus percent-encoded query string of the GET that carries *query*."""
    return httpx.Request("GET", SENATO_SPARQL_URL, params=_senato_params(query)).url.raw_path


async def _execute_sparql_senato(query: str) -> list[dict]:
    """GET only: dati.senato.it answers POST with a 403 WAF page.

    A request target over SENATO_MAX_REQUEST_TARGET bytes gets a 403 too, so
    it is refused here, before the request, with the reason spelled out.
    """
    size = len(senato_request_target(query))
    if size > SENATO_MAX_REQUEST_TARGET:
        raise QueryTooLong(
            f"Ricerca troppo lunga per dati.senato.it: la richiesta occuperebbe {size} byte "
            f"e il sito ne accetta al massimo {SENATO_MAX_REQUEST_TARGET}. "
            "Usare meno termini, o termini più brevi, oppure togliere un filtro."
        )
    async with async_client("parlamento_senato", timeout=_TIMEOUT, headers=_HEADERS) as client:
        resp = await retry_request(
            client, "GET", SENATO_SPARQL_URL, dataset="parlamento_senato",
            params=_senato_params(query),
        )
        return resp.json()["results"]["bindings"]


async def _execute_sparql_camera(query: str) -> list[dict]:
    async with async_client("parlamento_camera", timeout=_TIMEOUT, headers=_HEADERS) as client:
        resp = await retry_request(
            client, "POST", CAMERA_SPARQL_URL, dataset="parlamento_camera", data={"query": query},
        )
        return resp.json()["results"]["bindings"]


def _val(binding: dict, key: str) -> str:
    return binding.get(key, {}).get("value", "")


def _parse_fasi(bindings: list[dict], legislatura: int) -> list[DdlFase]:
    fasi = []
    seen: set[str] = set()
    for binding in bindings:
        uri = _val(binding, "ddl")
        if uri in seen:  # OPTIONAL fan-out can repeat rows
            continue
        seen.add(uri)
        data_legge = _val(binding, "dataLegge")
        if data_legge == _SENTINEL_DATA_LEGGE:
            data_legge = ""
        # The scheda links are official citations: the legislature must come
        # from the data when available, never from the echoed parameter.
        try:
            leg = int(_val(binding, "leg"))
        except ValueError:
            leg = int(legislatura)
        fasi.append(DdlFase(
            fase=_val(binding, "fase"),
            ramo=_val(binding, "ramo"),
            id_ddl=_val(binding, "idDdl"),
            id_fase=uri.rstrip("/").rsplit("/", 1)[-1],
            titolo=_val(binding, "titolo"),
            stato=_val(binding, "stato"),
            data_stato=_val(binding, "dataStato"),
            data_presentazione=_val(binding, "dataPres"),
            iniziativa=_val(binding, "iniziativa"),
            natura=_val(binding, "natura"),
            presentato_trasmesso=_val(binding, "presTrasm"),
            progressivo=_val(binding, "prog"),
            numero_legge=_val(binding, "numeroLegge"),
            data_legge=data_legge,
            legislatura=leg,
        ))
    return fasi


def scheda_senato_url(fase: DdlFase) -> str:
    """Official Senato iter page. Emit for the reader — never fetch (WAF 202)."""
    return f"https://www.senato.it/leg/{fase.legislatura}/BGT/Schede/Ddliter/{fase.id_fase}.htm"


def camera_scheda_url(numero: str, legislatura: int) -> str:
    """Official Camera page via the URN resolver (verified to answer 200)."""
    return (
        "https://www.camera.it/uri-res/N2Ls?"
        f"urn:camera-it:parlamento:scheda.progetto.legge:camera;{legislatura}.legislatura;{numero}"
    )


def format_fase(fase: DdlFase) -> str:
    lines = [f"### {fase.fase} — {fase.stato}"]
    lines.append(f"**Titolo**: {fase.titolo[:_MAX_TITLE_LENGTH]}")
    if fase.iniziativa:
        lines.append(f"**Iniziativa**: {fase.iniziativa}")
    meta = []
    if fase.data_presentazione:
        meta.append(f"presentato il {fase.data_presentazione}")
    if fase.data_stato:
        meta.append(f"stato al {fase.data_stato}")
    if fase.natura:
        meta.append(f"natura: {fase.natura}")
    if meta:
        lines.append("**Estremi**: " + " | ".join(meta))
    if fase.numero_legge:
        legge = f"**Divenuto legge**: n. {fase.numero_legge}"
        if fase.data_legge:
            legge += f" del {fase.data_legge}"
        lines.append(legge)
    lines.append(f"**Scheda Senato**: {scheda_senato_url(fase)}")
    if fase.ramo == "C" and "." in fase.fase:
        numero = fase.fase.split(".", 1)[1]
        lines.append(f"**Scheda Camera**: {camera_scheda_url(numero, fase.legislatura)}")
    return "\n".join(lines)


def _iter_sort_key(fase: DdlFase) -> tuple:
    try:
        prog = int(fase.progressivo)
    except ValueError:
        prog = 999
    return (prog, fase.data_presentazione)


def format_camera_detail(camera: CameraIter) -> str:
    lines = ["**Iter alla Camera** (statoIter):"]
    for date, label in camera.timeline:
        lines.append(f"- {date} — {label}")
    for url in camera.pdf_urls:
        lines.append(f"**Stampato (PDF)**: {url}")
    return "\n".join(lines)


def format_iter(fasi: list[DdlFase], camera_details: dict[str, CameraIter]) -> str:
    """Full navette of one bill. camera_details is keyed by AC number."""
    ordered = sorted(fasi, key=_iter_sort_key)
    first = ordered[0]
    lines = [f"# Iter DDL — {first.titolo[:_MAX_TITLE_LENGTH]}"]
    lines.append(f"**idDdl**: {first.id_ddl} | **Legislatura**: {first.legislatura} | **Fasi**: {len(ordered)}")
    lines.append("")
    for posizione, fase in enumerate(ordered, start=1):
        ramo_nome = "Senato" if fase.ramo == "S" else "Camera"
        # Positional numbering: osr:progressivoIter repeats across rami in the
        # real data (S.562=1 and C.1805=1 on the same bill), so it cannot label
        # the sequence for the reader.
        lines.append(f"## Fase {posizione} — {fase.fase} ({ramo_nome}, {fase.presentato_trasmesso or 'n.d.'})")
        lines.append(f"**Stato**: {fase.stato} @ {fase.data_stato}")
        if fase.numero_legge:
            legge = f"**Divenuto legge**: n. {fase.numero_legge}"
            if fase.data_legge:
                legge += f" del {fase.data_legge}"
            lines.append(legge)
        lines.append(f"**Scheda Senato**: {scheda_senato_url(fase)}")
        if fase.ramo == "C" and "." in fase.fase:
            numero = fase.fase.split(".", 1)[1]
            lines.append(f"**Scheda Camera**: {camera_scheda_url(numero, fase.legislatura)}")
            camera = camera_details.get(numero)
            if camera:
                lines.append(format_camera_detail(camera))
        lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Camera enrichment
# ---------------------------------------------------------------------------

def _build_camera_query(numero: str, legislatura: int) -> str:
    # Keep suffixes: the Camera identifies third readings as "813-B"
    # (ac19_813-B, verified live) — stripping non-digits would silently
    # query the FIRST reading instead.
    numero_clean = re.sub(r"[^0-9A-Za-z-]", "", numero)
    return f"""\
PREFIX ocd: <http://dati.camera.it/ocd/>
PREFIX dc: <http://purl.org/dc/elements/1.1/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?atto ?titolo ?dataPres ?statoLabel ?statoData ?pdf
WHERE {{
  ?atto a ocd:atto ;
        ocd:rif_leg <http://dati.camera.it/ocd/legislatura.rdf/repubblica_{int(legislatura)}> ;
        dc:identifier ?id ;
        dc:title ?titolo .
  FILTER(STR(?id) = "{numero_clean}")
  OPTIONAL {{ ?atto dc:date ?dataPres }}
  OPTIONAL {{ ?atto ocd:rif_statoIter ?st . ?st rdfs:label ?statoLabel ; dc:date ?statoData }}
  OPTIONAL {{ ?atto dc:relation ?pdf }}
}}"""


def _iso_date(raw: str) -> str:
    """Camera dc:date is YYYYMMDD — normalise to ISO."""
    if re.fullmatch(r"\d{8}", raw):
        return f"{raw[0:4]}-{raw[4:6]}-{raw[6:8]}"
    return raw


def _clean_camera_title(raw: str) -> str:
    text = html.unescape(raw).strip()
    text = re.sub(r"^[SC]\.?\s*\d+\.?\s*-\s*", "", text)  # drop "S. 1939. - " prefix
    return text.strip().strip('"').strip()


def _parse_camera_iter(bindings: list[dict]) -> CameraIter | None:
    if not bindings:
        return None
    first = bindings[0]
    timeline = sorted({
        (_iso_date(_val(b, "statoData")), _val(b, "statoLabel"))
        for b in bindings if _val(b, "statoLabel")
    })
    pdf_urls = sorted({_val(b, "pdf") for b in bindings if _val(b, "pdf")})
    return CameraIter(
        numero=_val(first, "atto").rsplit("_", 1)[-1],
        titolo=_clean_camera_title(_val(first, "titolo")),
        data_presentazione=_iso_date(_val(first, "dataPres")),
        timeline=timeline,
        pdf_urls=pdf_urls,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def search_ddl(
    groups: list[list[str]],
    legislatura: int = LEGISLATURA_CORRENTE,
    ramo: str = "",
    stato: str = "",
    solo_pendenti: bool = False,
    limit: int = 10,
) -> list[DdlFase]:
    query = _build_search_query(
        groups, legislatura=legislatura, ramo=ramo, stato=stato,
        solo_pendenti=solo_pendenti, limit=limit,
    )
    bindings = await _execute_sparql_senato(query)
    return _parse_fasi(bindings, legislatura)


async def fetch_iter(
    kind: str,
    value: str,
    legislatura: int = LEGISLATURA_CORRENTE,
) -> list[DdlFase]:
    """All fasi of one bill; kind/value come from parse_atto_input()."""
    if kind == "fase":
        query = _build_iter_query(fase=value, legislatura=legislatura)
    else:
        query = _build_iter_query(id_ddl=value, legislatura=legislatura)
    bindings = await _execute_sparql_senato(query)
    return sorted(_parse_fasi(bindings, legislatura), key=_iter_sort_key)


async def fetch_camera_iter(
    numero: str,
    legislatura: int = LEGISLATURA_CORRENTE,
) -> CameraIter | None:
    bindings = await _execute_sparql_camera(_build_camera_query(numero, legislatura))
    return _parse_camera_iter(bindings)

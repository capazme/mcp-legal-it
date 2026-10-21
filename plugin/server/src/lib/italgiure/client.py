"""Italgiure Solr client — async access to Corte di Cassazione decisions.

Endpoint: POST sncass/isapi/hc.dll/sn.solr/sn-collection/select?app.query
Auth: session cookie from homepage (anti-bot check).
SSL: verify=False (invalid cert on www.italgiure.giustizia.it).
Collections: snciv (civile), snpen (penale) — filtered via kind field in query.
"""

from __future__ import annotations

import re
import urllib.parse

import httpx

from src.lib._http import retry_request
from src.lib._paging import page, resume_hint

_BASE = "https://www.italgiure.giustizia.it/sncass"
_SOLR_URL = f"{_BASE}/isapi/hc.dll/sn.solr/sn-collection/select?app.query"
_HOMEPAGE = f"{_BASE}/"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": _HOMEPAGE,
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest",
}

_KIND_FILTER = {
    "civile": ["snciv"],
    "penale": ["snpen"],
    "tutti": ["snciv", "snpen"],
}

TIPO_PROV = {"sentenza": "Sentenza", "ordinanza": "Ordinanza", "decreto": "Decreto"}

_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
_MAX_OCR_LENGTH = 30000
# Long decisions keep their head (parties, facts) AND their tail: the holding (rigetto,
# accoglimento, principio di diritto, P.Q.M.) sits at the end of the OCR text, and for many
# decisions the `ocrdis` field is empty at the source, so a head-only cut loses the decision.
_OCR_HEAD_LENGTH = 12000
_OCR_TAIL_LENGTH = _MAX_OCR_LENGTH - _OCR_HEAD_LENGTH

# The public SentenzeWeb archive is a rolling window of about five years, NOT "2020+":
# read 2026-09-25, no decision of 2020 exists, the oldest civil decision is of 17/02/2021 and
# the continuous coverage starts on 27/09/2021.
ARCHIVE_START_YEAR = 2021
ARCHIVE_WINDOW_NOTE = (
    "l'archivio pubblico SentenzeWeb è una finestra mobile di circa cinque anni "
    "(a settembre 2026 le decisioni depositate dal 27/09/2021 in poi): le decisioni "
    "anteriori non sono consultabili"
)

_FACET_FIELDS = ["materia", "szdec", "anno", "tipoprov"]

# Textual signals a decision uses to FLAG a divergence in the case law.
# These are SELF-DECLARED markers in the decision text — NOT a holding classifier.
# "discostarsi" is deliberately NOT a signal: in the decisions it appears mostly in the negated
# formula "non vi sono ragioni per discostarsi", which declares conformity (read 2026-09-25: 13 of
# the 22 decisions on art. 1419 c.c., 65% of the civil archive).
CONFLICT_SIGNALS = [
    "contrasto giurisprudenziale",
    "difforme orientamento",
]
# Textual signals a decision uses to ALIGN with settled case law.
CONFORMITY_SIGNALS = [
    "orientamento consolidato",
    "in senso conforme",
]

_SEZIONI = {
    "1": "I",
    "2": "II",
    "3": "III",
    "4": "IV",
    "5": "V",
    "6": "VI",
    "7": "VII",
    "L": "lav.",
    "T": "trib.",
    "SU": "SS.UU.",
    "U": "sez. un.",
    "F": "fer.",
}

_TIPO_LABELS = {
    "S": "sentenza", "O": "ordinanza", "D": "decreto",
    "Sentenza": "sentenza", "Ordinanza": "ordinanza", "Decreto": "decreto",
    "Ordinanza Interlocutoria": "ord. int.",
}

_RAMO = {"snciv": "civ.", "snpen": "pen."}

# Keys ordered longest-first to avoid short-prefix false matches (e.g. "c.p." before "c.p.a.").
_CODICI = {
    "c.c.i.i.": ["c.c.i.i.", "CCII", "codice della crisi"],
    "c.p.c.": ["c.p.c.", "cod. proc. civ."],
    "c.p.p.": ["c.p.p.", "cod. proc. pen."],
    "c.p.a.": ["c.p.a.", "codice del processo amministrativo"],
    "c.d.s.": ["c.d.s.", "cod. strada", "codice della strada"],
    "c.cons.": ["c.cons.", "codice del consumo"],
    "t.u.b.": ["t.u.b.", "testo unico bancario"],
    "t.u.f.": ["t.u.f.", "testo unico finanza", "testo unico intermediazione finanziaria"],
    "cost.": ["cost.", "costituzione"],
    "c.c.": ["c.c.", "cod. civ.", "codice civile"],
    "c.p.": ["c.p.", "cod. pen.", "codice penale"],
    "c.n.": ["c.n.", "cod. nav.", "codice della navigazione"],
}

# Keys ordered longest-first to avoid "l." matching inside "d.l." or "d.lgs.".
_TIPI_ATTO = {
    "d.lgs.": ["D.Lgs.", "decreto legislativo", "d.lgs."],
    "d.p.r.": ["DPR", "D.P.R.", "decreto del Presidente della Repubblica"],
    "d.l.": ["D.L.", "decreto legge", "d.l."],
    "d.m.": ["D.M.", "decreto ministeriale", "d.m."],
    "reg.": ["Reg.", "regolamento"],
    "l.": ["L.", "legge", "l."],
}


def get_kind_filter(archivio: str) -> list[str]:
    return _KIND_FILTER.get(archivio, _KIND_FILTER["tutti"])


# Section codes of the `szdec` field, read from the index facet on 2026-09-25: 1-7 (simple
# sections, 7 = sez. VII penale), L (lavoro), U (Sezioni Unite), F (feriale). "SU" and "T" do
# not exist in the index: tributaria is civil section 5.
VALID_SEZIONI = ("1", "2", "3", "4", "5", "6", "7", "L", "U", "F")
_SEZIONE_ALIAS = {
    "SU": "U", "SSUU": "U", "S.U.": "U", "SS.UU.": "U", "UNITE": "U", "SEZIONIUNITE": "U",
    "T": "5", "TRIB": "5", "TRIBUTARIA": "5",
    "LAV": "L", "LAVORO": "L",
    "FER": "F", "FERIALE": "F",
    "I": "1", "II": "2", "III": "3", "IV": "4", "V": "5", "VI": "6", "VII": "7",
}
_TRIBUTARIA_KEYS = ("T", "TRIB", "TRIBUTARIA")


def resolve_sezione(sezione: str | None, archivio: str = "tutti") -> tuple[str, str]:
    """Map a user-facing section token to the `szdec` code and the effective archive.

    Accepts the documented spellings (SU, T, L, roman numerals) and the index codes
    (1-7, L, U, F). "T" (tributaria) is civil section 5, so with archivio="tutti" the
    search is narrowed to the civil archive. Raises ValueError, listing the valid codes,
    for anything else: an unknown code would otherwise match nothing and read as "no
    decisions found".
    """
    raw = (sezione or "").strip()
    if not raw:
        return "", archivio
    key = raw.upper().replace(" ", "")
    code = _SEZIONE_ALIAS.get(key, key)
    if code not in VALID_SEZIONI:
        raise ValueError(
            f"Sezione '{raw}' non valida. Codici ammessi: 1-7 (sezioni semplici, 7 = sez. VII penale), "
            "L (lavoro), U (Sezioni Unite, anche SU), F (feriale); T = tributaria = sezione 5 civile."
        )
    if key in _TRIBUTARIA_KEYS:
        if archivio == "penale":
            raise ValueError("La sezione tributaria (T) è solo civile: usare archivio 'civile' o 'tutti'.")
        archivio = "civile"
    return code, archivio


def quote_fq_value(value: str) -> str:
    """Quote a free-text filter value as one Solr phrase (escaping backslash and double quote).

    Unquoted, `materia:responsabilita' civile` binds only the first word to the field and
    the second is searched in the default field, so the filter widens instead of narrowing.
    """
    escaped = value.strip().replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _first(val) -> str:
    """Return first element if val is a list, else val as string."""
    if isinstance(val, list):
        return val[0] if val else ""
    return str(val) if val is not None else ""


class SolrSession:
    """Reusable Solr session — fetches homepage cookie once, reuses for N queries."""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> SolrSession:
        self._client = httpx.AsyncClient(verify=False, timeout=_TIMEOUT, headers=_HEADERS)
        await self._client.get(_HOMEPAGE)
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def query(self, params: dict) -> dict:
        if self._client is None:
            raise RuntimeError("SolrSession not entered — use `async with`")
        body = urllib.parse.urlencode({**params, "wt": "json", "indent": "off"}, doseq=True)
        resp = await retry_request(self._client, "POST", _SOLR_URL, dataset="italgiure", content=body)
        return resp.json()


async def solr_query(params: dict, session: SolrSession | None = None) -> dict:
    """Execute Solr query against Italgiure unified endpoint.

    Uses POST to /sn-collection/select?app.query with form-encoded body.
    Fetches homepage first to obtain session cookie. verify=False for invalid SSL.
    Handles list-valued params (e.g. multiple fq) via urlencode(doseq=True).

    If *session* is provided, reuses its client (no extra homepage fetch).
    """
    if session is not None:
        return await session.query(params)
    async with httpx.AsyncClient(verify=False, timeout=_TIMEOUT, headers=_HEADERS) as client:
        await client.get(_HOMEPAGE)
        body = urllib.parse.urlencode({**params, "wt": "json", "indent": "off"}, doseq=True)
        resp = await retry_request(client, "POST", _SOLR_URL, dataset="italgiure", content=body)
        return resp.json()


def build_search_params(
    query: str,
    archivio: str = "tutti",
    materia: str | None = None,
    sezione: str | None = None,
    anno_da: int | None = None,
    anno_a: int | None = None,
    tipo_provvedimento: str | None = None,
    solo_sezioni_unite: bool = False,
    ordinamento: str = "rilevanza",
    rows: int = 5,
    start: int = 0,
    highlight: bool = True,
    campo: str = "tutto",
    include_facets: bool = False,
    mm: str | None = None,
    fq_extra: list[str] | None = None,
) -> dict:
    """Build eDisMax params for full-text search.

    ordinamento: "rilevanza" (score desc) or "data" (pd desc).
    campo: "tutto" (ocrdis+ocr, default) or "dispositivo" (solo ocrdis).
    include_facets: if True, adds facet params for materia/szdec/anno/tipoprov.
    mm: override minimum-should-match (default "2<75% 5<60%").
    fq_extra: extra filter queries, AND-ed in verbatim (e.g. an article anchor).
    """
    kinds = get_kind_filter(archivio)
    kind_clause = " OR ".join(f'kind:"{k}"' for k in kinds)
    sort = "score desc" if ordinamento == "rilevanza" else "pd desc"
    if campo == "dispositivo":
        qf = "ocrdis^1"
        pf = "ocrdis^3"
        pf2 = "ocrdis^2"
        pf3 = "ocrdis^1"
    else:
        qf = "ocrdis^5 ocr^1"
        pf = "ocrdis^10 ocr^3"
        pf2 = "ocrdis^6 ocr^2"
        pf3 = "ocrdis^4 ocr^1"
    params: dict = {
        "defType": "edismax",
        "q": query,
        "qf": qf,
        "pf": pf,
        "pf2": pf2,
        "pf3": pf3,
        "mm": mm or "2<75% 5<60%",
        "fq": [f"({kind_clause})"],
        "sort": sort,
        "rows": rows,
        "start": start,
        "fl": "id,numdec,anno,datdep,szdec,materia,tipoprov,ocrdis,kind,score",
    }
    if materia:
        params["fq"].append(f"materia:{quote_fq_value(materia)}")
    if sezione:
        params["fq"].append(f"szdec:{sezione}")
    if solo_sezioni_unite:
        params["fq"].append("szdec:(SU OR U)")
    if tipo_provvedimento and tipo_provvedimento in TIPO_PROV:
        params["fq"].append(f"tipoprov:{TIPO_PROV[tipo_provvedimento]}")
    if anno_da and anno_a:
        params["fq"].append(f"anno:[{anno_da} TO {anno_a}]")
    elif anno_da:
        params["fq"].append(f"anno:[{anno_da} TO *]")
    elif anno_a:
        params["fq"].append(f"anno:[* TO {anno_a}]")
    if fq_extra:
        params["fq"].extend(fq_extra)
    if include_facets:
        params["facet"] = "true"
        params["facet.field"] = _FACET_FIELDS
        params["facet.limit"] = 10
        params["facet.mincount"] = 1
    if highlight:
        params.update({
            "hl": "true",
            "hl.fl": "ocr,ocrdis",
            "hl.fragsize": "400",
            "hl.snippets": "2",
        })
    return params


def build_explore_params(
    query: str,
    archivio: str = "tutti",
    campo: str = "tutto",
) -> dict:
    """Build params for facet-only exploration (rows=0, no documents).

    Returns distribution by materia, sezione, anno, tipo provvedimento.
    """
    kinds = get_kind_filter(archivio)
    kind_clause = " OR ".join(f'kind:"{k}"' for k in kinds)
    if campo == "dispositivo":
        qf = "ocrdis^1"
    else:
        qf = "ocrdis^5 ocr^1"
    return {
        "defType": "edismax",
        "q": query,
        "qf": qf,
        "mm": "2<75% 5<60%",
        "fq": [f"({kind_clause})"],
        "rows": 0,
        "fl": "id",
        "facet": "true",
        "facet.field": _FACET_FIELDS,
        "facet.limit": 15,
        "facet.mincount": 1,
    }


def _signal_facet_query(phrase: str) -> str:
    """Return the Solr facet.query string for a self-flag signal phrase."""
    return f'ocr:"{phrase}"'


def group_signal_facet_query(phrases: list[str]) -> str:
    """Return the facet.query counting DISTINCT decisions that use ANY phrase of a group.

    Summing the per-phrase counts counts twice every decision that uses two of the
    expressions; a single OR query counts each decision once.
    """
    return "ocr:(" + " OR ".join(f'"{p}"' for p in phrases) + ")"


def build_orientamento_params(
    q: str,
    archivio: str = "tutti",
    anno_da: int = 0,
    sezione: str = "",
    rows: int = 10,
    campo: str = "tutto",
    field_query: bool = False,
    sort: str = "pd desc",
    mm: str | None = None,
) -> dict:
    """Build ONE faceted query for a descriptive orientation map.

    Single round-trip: returns the LATER decisions sorted by deposit date (newest
    first via the sortable `pd` field) plus three facet axes computed server-side
    in the same request:
      - facet.field szdec  → per-sezione clustering (incl. szdec:U = Sezioni Unite)
      - facet.field anno   → temporal trend
      - facet.query × N    → count of decisions whose text SELF-FLAGS a
        contrasto/difforme signal vs an orientamento consolidato/conforme signal

    The facet.query counts are a TEXTUAL SIGNAL, never a holdings classifier
    (L. 132/2025 reserves legal interpretation to magistrates — descriptive only).

    Two query modes:
      - *field_query=False* (default, free-text principle): edismax over qf, with
        the kind clause as an fq. Use for `orientamento_su_principio`.
      - *field_query=True* (fielded norma query, e.g. `ocr:("art. 2043" OR ...)`
        from `build_norma_variants`): plain lucene `q` with the kind clause AND-ed
        in; no defType/qf/mm (passing a fielded ocr:(...) clause as the edismax q
        triggers a 400 on Italgiure). Use for `orientamento_su_norma`.

    *q* is passed verbatim (caller normalises / builds variants). *campo*
    "dispositivo" narrows the qf to the operative part (free-text mode only).
    *sort* is "pd desc" (default) or a relevance sort such as "score desc" (free-text mode
    only: a fielded lucene query has no meaningful score); *mm* overrides the edismax
    minimum-should-match (free-text mode only, default "2<75% 5<60%").
    Faceting (incl. facet.query) is independent of defType, so it works in both
    modes. Never issues N separate requests.
    """
    kinds = get_kind_filter(archivio)
    kind_clause = " OR ".join(f'kind:"{k}"' for k in kinds)
    facet_queries = (
        [_signal_facet_query(p) for p in CONFLICT_SIGNALS]
        + [_signal_facet_query(p) for p in CONFORMITY_SIGNALS]
        + [group_signal_facet_query(CONFLICT_SIGNALS), group_signal_facet_query(CONFORMITY_SIGNALS)]
    )
    params: dict = {
        "rows": rows,
        "start": 0,
        "sort": "pd desc" if field_query else sort,
        "fl": "id,numdec,anno,datdep,szdec,materia,tipoprov,ocrdis,kind,score",
        "facet": "true",
        "facet.field": ["szdec", "anno"],
        "facet.limit": 30,
        "facet.mincount": 1,
        "facet.query": facet_queries,
    }
    if field_query:
        # Lucene mode: embed kind clause in q, fielded query AND-ed in.
        params["q"] = f"({kind_clause}) AND {q}"
        fq: list[str] = []
    else:
        # Edismax mode: free-text scored over qf, kind clause as fq.
        if campo == "dispositivo":
            qf = "ocrdis^1"
        else:
            qf = "ocrdis^5 ocr^1"
        params.update({
            "defType": "edismax",
            "q": q,
            "qf": qf,
            "mm": mm or "2<75% 5<60%",
        })
        if sort.startswith("score"):
            # Phrase boosts only reorder the score: the decisions that use the principle's
            # words together outrank those that merely share a few of them.
            params.update({
                "pf": "ocrdis^10 ocr^3", "pf2": "ocrdis^6 ocr^2", "pf3": "ocrdis^4 ocr^1",
            })
        fq = [f"({kind_clause})"]
    if sezione:
        fq.append(f"szdec:{sezione}")
    if anno_da:
        fq.append(f"anno:[{anno_da} TO *]")
    if fq:
        params["fq"] = fq
    return params


def format_facets(facet_counts: dict, num_found: int) -> str:
    """Format Solr facet_counts into readable markdown.

    Maps szdec codes to section names, tipoprov codes to type names.
    Returns empty string if no facet data.
    """
    facet_fields = facet_counts.get("facet_fields", {})
    if not facet_fields:
        return ""
    lines = [f"**Distribuzione risultati** ({num_found} totali):"]
    field_labels = {
        "materia": "Materia",
        "szdec": "Sezione",
        "anno": "Anno",
        "tipoprov": "Tipo",
    }
    for field_name, label in field_labels.items():
        raw = facet_fields.get(field_name, [])
        pairs = list(zip(raw[0::2], raw[1::2]))
        if not pairs:
            continue
        formatted = []
        for name, count in pairs:
            if field_name == "szdec":
                name = _SEZIONI.get(str(name), str(name))
            elif field_name == "tipoprov":
                name = _TIPO_LABELS.get(str(name), str(name))
            formatted.append(f"{name} ({count})")
        lines.append(f"- **{label}**: {', '.join(formatted)}")
    return "\n".join(lines)


def build_lookup_params(
    numero: int,
    anno: int,
    archivio: str = "tutti",
    sezione: str | None = None,
) -> dict:
    kinds = get_kind_filter(archivio)
    kind_clause = " OR ".join(f'kind:"{k}"' for k in kinds)
    numdec_str = str(numero).zfill(5)
    q = f"({kind_clause}) AND numdec:{numdec_str} AND anno:{anno}"
    if sezione:
        q += f" AND szdec:{sezione}"
    return {
        "q": q,
        "rows": 5,
        "fl": "id,numdec,anno,datdep,szdec,materia,tipoprov,ocr,ocrdis,relatore,presidente,kind",
    }


# Slop of the proximity phrases that tie an article number to the act it belongs to:
# "art. 13 ... 2016/679" within this many tokens. Read on Italgiure 2026-09-29 (civile, dal 2021,
# art. 13 GDPR): slop 5 -> 5 decisions (4 cite art. 13 of the Regulation within 250 characters),
# slop 15 -> 7 (5), slop 30 -> 10 (5); AND-ing the article with the act anywhere in the decision
# gave 47 decisions of which 1 pertinent, the bare "art. 13" 12966 in 2022 alone.
_NORMA_PROXIMITY = 15


def _act_identity_markers(rest: str) -> list[str]:
    """Plain phrases that identify the ACT named after the article number.

    "231/2001" -> "231/2001", "2001/231", "231 del 2001" (the form in the text depends on the
    source: "regolamento (UE) 2016/679", "n. 679/2016", "679 del 2016"). When the reference
    carries no number (e.g. "GDPR", "statuto dei lavoratori") the act is resolved by name and the
    name itself is also a marker.
    """
    markers: list[str] = []
    pair = re.search(r"(\d+)\s*(?:/|del)\s*(\d{2,4})", rest)
    if pair:
        a, b = pair.group(1), pair.group(2)
    else:
        a = b = ""
        try:  # lazy: keeps the client free of a hard import-time dependency on visualex
            from src.lib.visualex import resolve_atto

            atto = resolve_atto(rest) or {}
        except Exception:  # noqa: BLE001 - identity by number is best effort
            atto = {}
        numero = str(atto.get("numero_atto") or "")
        anno = str(atto.get("data") or "")[:4]
        if numero.isdigit() and anno.isdigit():
            a, b = numero, anno
    if a and b:
        markers += [f"{a}/{b}", f"{b}/{a}", f"{a} del {b}"]
    if not any(ch.isdigit() for ch in rest):
        markers.append(rest)
    return list(dict.fromkeys(markers))


def build_norma_variants(riferimento: str, strict: bool = False) -> str:
    """Convert 'art. 2043 c.c.' to a Solr query with common text variants.

    Codes ('art. 2043 c.c.'): the bare "art. N" / "articolo N" plus the code-qualified forms
    ("2043 c.c.", "2043 cod. civ.", ...). With *strict* the bare forms are dropped, leaving
    only the code-qualified ones (used to ANCHOR a search to one article).

    Acts ('art. 13 GDPR', 'art. 6 D.Lgs. 231/2001'): the bare forms are NOT ORed in, because
    they match every decision that cites ANY article N (art. 13 co. 1-quater d.P.R. 115/2002
    sits in almost every dispositivo). The article is tied to the act by a PROXIMITY phrase
    instead ("art. 13 2016/679"~15: the identity of the act, number/year or name, within a few
    tokens of the article). AND-ing article and act anywhere in the decision is not enough: it
    matched 47 decisions with 1 pertinent. Qualified forms are kept as an alternative.

    A reference with no code and no act ('art. 13') keeps the bare forms (low precision).
    """
    rif = riferimento.strip().lower()

    match = re.match(
        r"(?:art\.?|articolo)\s+(\d+(?:-(?:bis|ter|quater|quinquies|sexies|septies|octies|novies|decies))?)",
        rif,
    )
    if not match:
        return f'ocr:("{riferimento}")'

    num = match.group(1)
    rest = rif[match.end():].strip()

    bare = [f'"art. {num}"', f'"articolo {num}"']
    qualified: list[str] = []

    matched_code = False
    for abbrev, expansions in _CODICI.items():
        if rest.startswith(abbrev) or rest == abbrev.rstrip("."):
            for exp in expansions:
                qualified.append(f'"{num} {exp}"')
            matched_code = True
            break

    if matched_code:
        variants = qualified if strict else bare + qualified
        return "ocr:(" + " OR ".join(variants) + ")"

    if not rest:
        return "ocr:(" + " OR ".join(bare) + ")"

    # Legislative act: e.g. "D.Lgs. 231/2001". Extract the numeric identifier
    # ("231/2001" or "231") from rest.
    num_year_match = re.search(r"(\d+(?:/\d+)?)", rest)
    act_num_str = num_year_match.group(1) if num_year_match else ""

    matched_tipo = False
    for abbrev, tipo_variants in _TIPI_ATTO.items():
        if rest.startswith(abbrev) or any(rest.startswith(v.lower()) for v in tipo_variants):
            for v in tipo_variants:
                if act_num_str:
                    # Only forms carrying the act number identify the act: "art. 6 D.Lgs."
                    # alone matches any legislative decree.
                    qualified.append(f'"art. {num} {v} {act_num_str}"')
                    qualified.append(f'"art. {num} {v} n. {act_num_str}"')
                else:
                    qualified.append(f'"art. {num} {v}"')
            matched_tipo = True
            break

    if not matched_tipo:
        qualified.append(f'"art. {num} {rest}"')

    markers = _act_identity_markers(rest)
    if not markers:
        # No way to tell the act apart: keep the historical (low precision) OR of bare forms.
        return "ocr:(" + " OR ".join(bare + qualified) + ")"
    # Only "art." and "articolo": phrase queries on "artt." make the Solr highlighter answer
    # 500 on some decisions (read 2026-09-29).
    near = [
        f'"{art} {num} {marker}"~{_NORMA_PROXIMITY}'
        for art in ("art.", "articolo")
        for marker in markers
    ]
    return "ocr:(" + " OR ".join(qualified + near) + ")"


def norma_is_qualified(riferimento: str) -> bool:
    """True when the reference names a code or an act after the article number."""
    rif = riferimento.strip().lower()
    m = re.match(
        r"(?:art\.?|articolo)\s+\d+(?:-(?:bis|ter|quater|quinquies|sexies|septies|octies|novies|decies))?",
        rif,
    )
    return bool(m and rif[m.end():].strip())


def _format_date(datdep) -> str:
    raw = _first(datdep)
    if not raw:
        return ""
    # Format: "20250827" → "27/08/2025"
    raw = raw.strip()
    if len(raw) == 8 and raw.isdigit():
        return f"{raw[6:8]}/{raw[4:6]}/{raw[0:4]}"
    # ISO "2025-08-27T..." fallback
    try:
        parts = raw[:10].split("-")
        if len(parts) == 3:
            return f"{parts[2]}/{parts[1]}/{parts[0]}"
    except (IndexError, ValueError):
        pass
    return raw


_TIPO_ABBR = {
    "sentenza": "sent.", "ordinanza": "ord.", "decreto": "decr.", "ord. int.": "ord. int.",
}


def format_estremi(doc: dict, con_tipo: bool = False) -> str:
    """Estremi of a decision; with *con_tipo* the type (sent./ord./decr.) is appended."""
    kind = _first(doc.get("kind", "snciv"))
    ramo = _RAMO.get(kind, "civ.")
    sez = _first(doc.get("szdec", ""))
    sez_fmt = _SEZIONI.get(sez, sez)
    num = _first(doc.get("numdec", "?"))
    anno = _first(doc.get("anno", "?"))
    datdep = _format_date(doc.get("datdep"))

    parts = [f"Cass. {ramo}"]
    if sez_fmt:
        # Some _SEZIONI values already carry the "sez." prefix (e.g. "U" -> "sez. un.");
        # avoid producing "sez. sez. un.".
        parts.append(sez_fmt if sez_fmt.lower().startswith("sez") else f"sez. {sez_fmt}")
    parts.append(f"n. {num}/{anno}")
    if datdep:
        parts.append(f"dep. {datdep}")

    estremi = ", ".join(parts)
    if con_tipo:
        raw = _first(doc.get("tipoprov", ""))
        tipo = _TIPO_ABBR.get(_TIPO_LABELS.get(raw, raw.lower()), "")
        if tipo:
            estremi += f" ({tipo})"
    return estremi


def format_summary(
    doc: dict, highlights: dict[str, list[str]] | None = None, con_tipo: bool = False,
) -> str:
    estremi = format_estremi(doc, con_tipo=con_tipo)
    materia = _first(doc.get("materia", ""))
    ocrdis = _first(doc.get("ocrdis", ""))

    lines = [f"### {estremi}"]
    if materia:
        lines.append(f"**Materia**: {materia}")
    if highlights:
        hl_dis = highlights.get("ocrdis", [])
        hl_ocr = highlights.get("ocr", [])
        if hl_dis:
            lines.append(f"**Dispositivo (match)**: ...{hl_dis[0]}...")
        if hl_ocr:
            lines.append(f"**Estratto**: ...{hl_ocr[0]}...")
    if ocrdis and not (highlights and highlights.get("ocrdis")):
        disp = ocrdis[:200].strip()
        if len(ocrdis) > 200:
            disp += "…"
        lines.append(f"**Dispositivo**: {disp}")

    return "\n".join(lines)


def format_full_text(doc: dict, da_carattere: int = 1) -> str:
    """Render a decision. Positions in the notes count the characters of the ``ocr`` text.

    ``da_carattere`` > 1 renders the plain window of the ``ocr`` text that starts there
    (src/lib/_paging.py), without the Dispositivo field already given by the first answer.
    """
    estremi = format_estremi(doc)
    materia = _first(doc.get("materia", ""))
    relatore = _first(doc.get("relatore", ""))
    presidente = _first(doc.get("presidente", ""))
    ocr = _first(doc.get("ocr", ""))
    ocrdis = _first(doc.get("ocrdis", ""))

    lines = [f"# {estremi}"]
    if materia:
        lines.append(f"**Materia**: {materia}")
    if relatore:
        lines.append(f"**Relatore**: {relatore}")
    if presidente:
        lines.append(f"**Presidente**: {presidente}")
    lines.append("")

    if da_carattere > 1:
        body, note = page(ocr, da_carattere, _MAX_OCR_LENGTH)
        lines.append("## Testo della decisione")
        if body:
            lines.append(body)
        lines.append(f"\n---\n{note}")
        return "\n".join(lines)

    if ocr:
        truncated = len(ocr) > _MAX_OCR_LENGTH
        lines.append("## Testo della decisione")
        if truncated:
            omitted = len(ocr) - _MAX_OCR_LENGTH
            resume = _OCR_HEAD_LENGTH + 1
            lines.append(ocr[:_OCR_HEAD_LENGTH])
            lines.append(
                f"\n[... omessi {omitted} caratteri della parte centrale "
                f"(caratteri {resume}-{len(ocr) - _OCR_TAIL_LENGTH}): {resume_hint(resume)} ...]\n"
            )
            lines.append(ocr[-_OCR_TAIL_LENGTH:])
            lines.append(
                f"\n---\n*[Testo troncato a {_MAX_OCR_LENGTH} caratteri su {len(ocr)} totali: "
                f"{resume_hint(resume)}]* "
                f"Mostrati i primi {_OCR_HEAD_LENGTH} e gli ultimi {_OCR_TAIL_LENGTH} caratteri; la parte "
                f"centrale è omessa. La decisione (rigetto, accoglimento, P.Q.M.) sta in genere in coda."
            )
        else:
            lines.append(ocr)

    if ocrdis:
        lines.append("\n## Dispositivo")
        lines.append(ocrdis)
    elif ocr:
        lines.append(
            "\n*[Il campo Dispositivo non è valorizzato alla fonte per questa decisione: "
            "il dispositivo, se presente, è nella parte finale del testo]*"
        )

    return "\n".join(lines)

"""Cassazione (Italgiure) logic shared by the MCP tools and the library API.

Pure logic per ADR-001: how a decision is found by number and year, and the
queries behind the searches. The Solr calls go through this module's
``solr_query`` / ``SolrSession`` names, so the tools and the API share one
binding (and tests patch one place). Formatting stays in ``tools/italgiure.py``.
"""

import re

from mcp_legal_it.lib import _clock
from mcp_legal_it.lib.italgiure.client import (
    SolrSession,
    build_lookup_params,
    build_norma_variants,
    build_search_params,
    get_kind_filter,
    solr_query,
)

__all__ = [
    "SolrSession",
    "lookup_decisione",
    "params_su_norma",
    "query_con_ripiego",
    "solr_query",
]

_IT_STOPWORDS = frozenset({
    "di", "del", "della", "dello", "delle", "dei", "degli",
    "per", "con", "in", "da", "dal", "dalla", "dalle",
    "che", "il", "la", "lo", "le", "li", "un", "una", "uno",
    "al", "alla", "alle", "allo", "ai", "agli",
    "su", "sul", "sulla", "sulle", "sullo", "sui", "sugli",
    "tra", "fra", "nel", "nella", "nelle", "nello", "nei", "negli",
    "ed", "si", "se", "non", "come", "anche", "sono", "essere",
    "ha", "hanno", "è", "e", "o", "a",
})


def _normalize_query(query: str) -> str:
    """Preprocess LLM query for better Solr matching.

    Addresses common LLM query patterns that cause zero results:
    - Quotes around normative references force exact OCR match (often fails)
    - Single-word quotes are pointless
    - Too many terms with default mm cause over-filtering
    - Stopwords dilute relevance in long queries
    """
    if not query or not query.strip():
        return query

    q = query.strip()

    # 1. Remove quotes around normative references like "art. 1-bis"
    q = re.sub(
        r'"((?:art(?:icol[oi])?\.?\s+\d+(?:-\w+)?))"',
        r'\1',
        q,
    )
    # Remove quotes around D.Lgs./D.L./L. references
    q = re.sub(
        r'"((?:D\.?(?:Lgs|L|P\.R|M)\.?|[Ll]egge|[Dd]ecreto\s+legislativo)\s*(?:n\.?\s*)?\d+(?:/\d+)?)"',
        r'\1',
        q,
    )

    # 2. Remove quotes around single words (pointless, same as unquoted)
    q = re.sub(r'"(\w+)"', r'\1', q)

    # 3. Drop Italian stopwords if query has 6+ terms (to reduce mm pressure)
    terms = q.split()
    if len(terms) >= 6:
        filtered = []
        for t in terms:
            # Keep quoted phrases intact, keep operators, keep non-stopwords
            if t.startswith('"') or t in ("AND", "OR", "NOT") or t.startswith("-"):
                filtered.append(t)
            elif t.lower().rstrip(".,;:") not in _IT_STOPWORDS:
                filtered.append(t)
        # Ensure we keep at least 3 terms
        if len(filtered) >= 3:
            terms = filtered

    q = " ".join(terms)

    # 4. Collapse multiple spaces
    q = re.sub(r"\s{2,}", " ", q).strip()

    return q


# The Italgiure archive is a MOVING window, not "from 2020": on 2026-09-25 the civil archive
# started on 17/02/2021 (2021 holds ~16k decisions against 35-38k of a full year, and nothing is
# indexed for 2020), and the start advances every day. Decisions before the start cannot be
# confirmed as existent or not; the first year is only partly covered, so a miss there proves
# nothing either. The start is READ from the archive (oldest deposited decision, cached per day)
# by `_italgiure_archive_start`, the single definition shared by verifica_citazioni and
# cerca_brocardi. If that probe fails, the window is assumed to be at least this many years wide.
_ITALGIURE_WINDOW_YEARS = 5

_archive_start_cache: dict[tuple[str, str], tuple[int, str]] = {}


def _italgiure_window_year() -> int:
    """Newest year that can lie before, or on the edge of, the archive start.

    A decision of a LATER year is always inside the archive window, so it needs no probe.
    """
    return _clock.today().year - _ITALGIURE_WINDOW_YEARS


async def _italgiure_archive_start(archivio: str = "tutti") -> tuple[int, str]:
    """First year and first deposit date ("YYYY-MM-DD") of the Italgiure archive.

    Read as the oldest decision of the archive (sort by deposit date, one row) and cached for
    the day. If the archive cannot be queried, returns the assumed window
    (``today.year - 5``, no date) without caching it.
    """
    today = _clock.today()
    key = (archivio, today.isoformat())
    if key in _archive_start_cache:
        return _archive_start_cache[key]
    fallback = (_italgiure_window_year(), "")
    try:
        kind_clause = " OR ".join(f'kind:"{k}"' for k in get_kind_filter(archivio))
        data = await solr_query(
            {"q": f"({kind_clause})", "rows": 1, "sort": "pd asc", "fl": "id,anno,datdep,kind"}
        )
        docs = data.get("response", {}).get("docs", [])
        if not docs:
            return fallback
        raw = docs[0].get("datdep")
        raw = str(raw[0] if isinstance(raw, list) else raw or "").strip()
        m = re.match(r"^(\d{4})-?(\d{2})-?(\d{2})", raw)
        if not m:
            return fallback
        start = (int(m.group(1)), f"{m.group(1)}-{m.group(2)}-{m.group(3)}")
    except Exception:  # noqa: BLE001 - the probe is best effort; the caller keeps the fallback rule
        return fallback
    _archive_start_cache[key] = start
    return start


#: Fields read for a decision found by number.
_LOOKUP_FIELDS = "id,numdec,anno,datdep,szdec,materia,tipoprov,ocr,ocrdis,relatore,presidente,kind"


async def lookup_decisione(numero: int, anno: int, sezione: str, archivio: str) -> tuple[list[dict], bool]:
    """Find decision *numero*/*anno* in the archive, in four steps.

    Returns ``(docs, omonimi)``: ``docs[0]`` is the decision and ``omonimi`` says
    whether the other entries of ``docs`` are same-number decisions worth a note
    (False for the full-text step, whose other hits merely cite the number).
    Returns ``([], False)`` when no step finds it. Source failures raise.

    *sezione* and *archivio* are already resolved (``resolve_sezione``).
    """
    async with SolrSession() as session:
        # Step 1: Standard lookup (zero-padded + sezione)
        params = build_lookup_params(numero, anno, archivio=archivio, sezione=sezione or None)
        data = await solr_query(params, session=session)
        docs = data.get("response", {}).get("docs", [])
        if docs:
            return docs, True

        # Step 2: Retry without sezione filter (if provided)
        if sezione:
            params = build_lookup_params(numero, anno, archivio=archivio, sezione=None)
            data = await solr_query(params, session=session)
            docs = data.get("response", {}).get("docs", [])
            if docs:
                return docs, True

        # Step 3: Retry with raw number (no zero-padding)
        kinds = get_kind_filter(archivio)
        kind_clause = " OR ".join(f'kind:"{k}"' for k in kinds)
        raw_params = {
            "q": f"({kind_clause}) AND numdec:{numero} AND anno:{anno}",
            "rows": 5,
            "fl": _LOOKUP_FIELDS,
        }
        data = await solr_query(raw_params, session=session)
        docs = data.get("response", {}).get("docs", [])
        if docs:
            return docs, True

        # Step 4: Full-text search for "n. {numero}/{anno}"
        ft_query = f'"n. {numero}/{anno}" OR "n. {numero} del {anno}"'
        ft_params = build_search_params(
            ft_query, archivio=archivio, rows=3, start=0, campo="tutto",
        )
        data = await solr_query(ft_params, session=session)
        docs = data.get("response", {}).get("docs", [])
        # Validate that a returned doc actually IS the requested decision —
        # a full-text hit merely citing "n. {numero}/{anno}" in its OCR text
        # would otherwise be returned as the authoritative text (wrong ruling).
        numdec_candidates = {str(numero), str(numero).zfill(5)}
        for doc in docs:
            if str(doc.get("numdec")) in numdec_candidates and str(doc.get("anno")) == str(anno):
                return [doc], False
    return [], False


def params_su_norma(
    riferimento: str,
    archivio: str = "tutti",
    solo_sezioni_unite: bool = False,
    anno_da: int = 0,
    anno_a: int = 0,
    max_risultati: int = 5,
    pagina: int = 0,
) -> dict:
    """Solr parameters for the decisions that cite *riferimento* (``giurisprudenza_su_norma``)."""
    kinds = get_kind_filter(archivio)
    kind_clause = " OR ".join(f'kind:"{k}"' for k in kinds)
    norma_q = build_norma_variants(riferimento)
    fq_parts: list[str] = []
    if solo_sezioni_unite:
        fq_parts.append("szdec:(SU OR U)")
    if anno_da and anno_a:
        fq_parts.append(f"anno:[{anno_da} TO {anno_a}]")
    elif anno_da:
        fq_parts.append(f"anno:[{anno_da} TO *]")
    elif anno_a:
        fq_parts.append(f"anno:[* TO {anno_a}]")
    params: dict = {
        "q": f"({kind_clause}) AND {norma_q}",
        "sort": "score desc",
        "rows": max_risultati,
        "start": pagina * max_risultati,
        "fl": "id,numdec,anno,datdep,szdec,materia,tipoprov,ocrdis,kind",
        "hl": "true",
        "hl.fl": "ocr,ocrdis",
        "hl.fragsize": "400",
        "hl.snippets": "2",
    }
    if fq_parts:
        params["fq"] = fq_parts
    return params


async def query_con_ripiego(params: dict) -> dict:
    """``solr_query`` that retries once without highlighting when the highlighter fails.

    The Solr highlighter answers 500 on some decisions matched by phrase queries
    (read 2026-09-29): the retry keeps a highlighter fault from reading as
    "source down". A failure of the plain query raises.
    """
    try:
        return await solr_query(params)
    except Exception:
        plain = {k: v for k, v in params.items() if not k.startswith("hl")}
        return await solr_query(plain)

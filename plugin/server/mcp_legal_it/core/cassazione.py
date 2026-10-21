"""Cassazione (Italgiure) logic shared by the MCP tools and the library API.

Pure logic per ADR-001: how a decision is found by number and year, and the
queries behind the searches. The Solr calls go through this module's
``solr_query`` / ``SolrSession`` names, so the tools and the API share one
binding (and tests patch one place). Formatting stays in ``tools/italgiure.py``.
"""

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

"""MCP tools for searching Italian Supreme Court (Cassazione) decisions via Italgiure.

TRIGGER: usa questi tool quando l'utente menziona una sentenza con numero e anno espliciti.
Non fare web search per sentenze già identificate — il testo ufficiale è su Italgiure.
"""

from src.server import mcp
from src.lib.italgiure.client import (
    TIPO_PROV,
    build_lookup_params,
    build_norma_variants,
    build_search_params,
    format_full_text,
    format_summary,
    get_kind_filter,
    solr_query,
)


# ---------------------------------------------------------------------------
# Impl functions (testable without MCP context)
# ---------------------------------------------------------------------------

async def _leggi_sentenza_impl(
    numero: int,
    anno: int,
    sezione: str = "",
    archivio: str = "tutti",
) -> str:
    params = build_lookup_params(numero, anno, archivio=archivio, sezione=sezione or None)
    try:
        data = await solr_query(params)
        docs = data.get("response", {}).get("docs", [])
        if docs:
            return format_full_text(docs[0])
    except Exception as exc:
        return f"Errore nel recupero della decisione n. {numero}/{anno}: {exc}"
    return f"Decisione n. {numero}/{anno} non trovata negli archivi della Cassazione."


async def _cerca_giurisprudenza_impl(
    query: str,
    archivio: str = "tutti",
    materia: str = "",
    sezione: str = "",
    anno_da: int = 0,
    anno_a: int = 0,
    max_risultati: int = 10,
) -> str:
    max_risultati = min(max_risultati, 50)
    params = build_search_params(
        query,
        archivio=archivio,
        materia=materia or None,
        sezione=sezione or None,
        anno_da=anno_da or None,
        anno_a=anno_a or None,
        rows=max_risultati,
    )
    try:
        data = await solr_query(params)
    except Exception as exc:
        return f"Errore nella ricerca: {exc}"
    docs = data.get("response", {}).get("docs", [])
    highlighting = data.get("highlighting", {})
    if not docs:
        return "Nessuna decisione trovata per la ricerca indicata."
    lines = [f"**Trovate {len(docs)} decisioni della Cassazione per**: _{query}_\n"]
    for doc in docs:
        doc_id = doc.get("id", "")
        hl_fragments = highlighting.get(doc_id, {}).get("ocr", [])
        hl = hl_fragments[0] if hl_fragments else None
        lines.append(format_summary(doc, hl))
        lines.append("")
    return "\n".join(lines)


async def _giurisprudenza_su_norma_impl(
    riferimento: str,
    archivio: str = "tutti",
    max_risultati: int = 10,
) -> str:
    max_risultati = min(max_risultati, 50)
    kinds = get_kind_filter(archivio)
    kind_clause = " OR ".join(f'kind:"{k}"' for k in kinds)
    norma_q = build_norma_variants(riferimento)
    params: dict = {
        "q": f"({kind_clause}) AND {norma_q}",
        "sort": "score desc",
        "rows": max_risultati,
        "fl": "id,numdec,anno,datdep,szdec,materia,tipoprov,ocrdis,kind",
        "hl": "true",
        "hl.fl": "ocr",
        "hl.fragsize": "400",
        "hl.snippets": "1",
    }
    try:
        data = await solr_query(params)
    except Exception as exc:
        return f"Errore nella ricerca per norma: {exc}"
    docs = data.get("response", {}).get("docs", [])
    highlighting = data.get("highlighting", {})
    if not docs:
        return f"Nessuna decisione trovata per il riferimento: {riferimento}"
    lines = [f"**Giurisprudenza su**: _{riferimento}_\n"]
    for doc in docs:
        doc_id = doc.get("id", "")
        hl_fragments = highlighting.get(doc_id, {}).get("ocr", [])
        hl = hl_fragments[0] if hl_fragments else None
        lines.append(format_summary(doc, hl))
        lines.append("")
    return "\n".join(lines)


async def _ultime_pronunce_impl(
    materia: str = "",
    sezione: str = "",
    archivio: str = "tutti",
    tipo_provvedimento: str = "",
    max_risultati: int = 10,
) -> str:
    max_risultati = min(max_risultati, 50)
    kinds = get_kind_filter(archivio)
    kind_clause = " OR ".join(f'kind:"{k}"' for k in kinds)
    params: dict = {
        "q": f"({kind_clause})",
        "sort": "pd desc",
        "rows": max_risultati,
        "fl": "id,numdec,anno,datdep,szdec,materia,tipoprov,ocrdis,kind",
    }
    fq_parts = []
    if materia:
        fq_parts.append(f"materia:{materia}")
    if sezione:
        fq_parts.append(f"szdec:{sezione}")
    if tipo_provvedimento and tipo_provvedimento in TIPO_PROV:
        fq_parts.append(f"tipoprov:{TIPO_PROV[tipo_provvedimento]}")
    if fq_parts:
        params["fq"] = " AND ".join(fq_parts)
    try:
        data = await solr_query(params)
    except Exception as exc:
        return f"Errore nel recupero ultime pronunce: {exc}"
    docs = data.get("response", {}).get("docs", [])
    if not docs:
        return "Nessuna decisione recente trovata con i filtri specificati."
    lines = ["**Ultime pronunce della Cassazione**\n"]
    for doc in docs:
        lines.append(format_summary(doc))
        lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# MCP tool wrappers
# ---------------------------------------------------------------------------

@mcp.tool(tags={"giurisprudenza"})
async def leggi_sentenza(
    numero: int,
    anno: int,
    sezione: str = "",
    archivio: str = "tutti",
) -> str:
    """Legge il testo completo di una specifica sentenza della Cassazione da Italgiure (fonte ufficiale).

    USARE SEMPRE quando l'utente menziona una sentenza con numero e anno già noti
    (es. "Cass. n. 10787/2024", "Sez. III n. 10787 del 22 aprile 2024").
    NON usare web search per sentenze identificate — questo tool è diretto e ufficiale.
    Restituisce: testo completo della sentenza con dispositivo, massima ufficiale, e metadati.

    Args:
        numero: Numero della decisione (es. 10787)
        anno: Anno della decisione (es. 2024)
        sezione: Sezione della Corte (opzionale: 1-6, L=lavoro, T=tributaria, SU=sezioni unite)
        archivio: "civile", "penale", o "tutti" (default)
    """
    return await _leggi_sentenza_impl(numero, anno, sezione=sezione, archivio=archivio)


@mcp.tool(tags={"giurisprudenza"})
async def cerca_giurisprudenza(
    query: str,
    archivio: str = "tutti",
    materia: str = "",
    sezione: str = "",
    anno_da: int = 0,
    anno_a: int = 0,
    max_risultati: int = 10,
) -> str:
    """Ricerca full-text nelle sentenze della Cassazione su Italgiure (fonte ufficiale).

    Usare per trovare decisioni su un tema quando non si conosce il numero specifico.
    Una volta trovato il numero, usare leggi_sentenza() per il testo completo.
    Dopo questo tool: leggi_sentenza() per leggere il testo integrale delle decisioni trovate.
    Restituisce: lista di decisioni con numero, data, sezione, dispositivo e snippet matching.

    Args:
        query: Testo da cercare nel corpo delle decisioni
        archivio: "civile", "penale", o "tutti" (default)
        materia: Filtro per materia (es. "contratti", "responsabilita' civile")
        sezione: Filtro sezione (1-6, L=lavoro, T=tributaria, SU=sezioni unite)
        anno_da: Anno di inizio (incluso)
        anno_a: Anno di fine (incluso)
        max_risultati: Numero massimo di risultati (default 10, max 50)
    """
    return await _cerca_giurisprudenza_impl(
        query, archivio=archivio, materia=materia, sezione=sezione,
        anno_da=anno_da, anno_a=anno_a, max_risultati=max_risultati,
    )


@mcp.tool(tags={"giurisprudenza"})
async def giurisprudenza_su_norma(
    riferimento: str,
    archivio: str = "tutti",
    max_risultati: int = 10,
) -> str:
    """Trova sentenze della Cassazione che citano uno specifico articolo di legge.

    Workflow Brocardi→Italgiure: usa cerca_brocardi() per ottenere le massime con
    riferimenti strutturati, poi questo tool per leggere le sentenze complete.
    Dopo questo tool: leggi_sentenza() per il testo completo delle decisioni trovate.
    Restituisce: decisioni della Cassazione che citano la norma, con numero e snippet.

    Args:
        riferimento: Riferimento normativo (es. "art. 2043 c.c.", "art. 13 GDPR", "art. 6 D.Lgs. 231/2001")
        archivio: "civile", "penale", o "tutti" (default)
        max_risultati: Numero massimo di risultati (default 10)
    """
    return await _giurisprudenza_su_norma_impl(riferimento, archivio=archivio, max_risultati=max_risultati)


@mcp.tool(tags={"giurisprudenza"})
async def ultime_pronunce(
    materia: str = "",
    sezione: str = "",
    archivio: str = "tutti",
    tipo_provvedimento: str = "",
    max_risultati: int = 10,
) -> str:
    """Ultime pronunce depositate dalla Cassazione, con filtri opzionali.

    Dopo questo tool: leggi_sentenza() per leggere il testo integrale di una decisione specifica.
    Restituisce: lista cronologica delle ultime decisioni depositate con metadati e dispositivo.

    Args:
        materia: Filtro per materia
        sezione: Filtro sezione (1-6, L=lavoro, T=tributaria, SU=sezioni unite)
        archivio: "civile", "penale", o "tutti" (default)
        tipo_provvedimento: "sentenza", "ordinanza", o "decreto"
        max_risultati: Numero massimo di risultati (default 10)
    """
    return await _ultime_pronunce_impl(
        materia=materia, sezione=sezione, archivio=archivio,
        tipo_provvedimento=tipo_provvedimento, max_risultati=max_risultati,
    )

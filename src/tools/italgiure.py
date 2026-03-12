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
    tipo_provvedimento: str = "",
    solo_sezioni_unite: bool = False,
    ordinamento: str = "rilevanza",
    max_risultati: int = 5,
    pagina: int = 0,
) -> str:
    max_risultati = min(max_risultati, 50)
    params = build_search_params(
        query,
        archivio=archivio,
        materia=materia or None,
        sezione=sezione or None,
        anno_da=anno_da or None,
        anno_a=anno_a or None,
        tipo_provvedimento=tipo_provvedimento or None,
        solo_sezioni_unite=solo_sezioni_unite,
        ordinamento=ordinamento,
        rows=max_risultati,
        start=pagina * max_risultati,
    )
    try:
        data = await solr_query(params)
    except Exception as exc:
        return f"Errore nella ricerca: {exc}"
    docs = data.get("response", {}).get("docs", [])
    num_found = data.get("response", {}).get("numFound", 0)
    highlighting = data.get("highlighting", {})
    if not docs:
        return "Nessuna decisione trovata per la ricerca indicata."
    start_idx = pagina * max_risultati + 1
    end_idx = start_idx + len(docs) - 1
    ord_label = "per rilevanza" if ordinamento == "rilevanza" else "per data"
    lines = [f"**Trovate {num_found} decisioni** per: _{query}_ (mostro {start_idx}-{end_idx}, {ord_label})\n"]
    for doc in docs:
        doc_id = doc.get("id", "")
        hl = highlighting.get(doc_id)
        lines.append(format_summary(doc, hl))
        lines.append("")
    return "\n".join(lines)


async def _giurisprudenza_su_norma_impl(
    riferimento: str,
    archivio: str = "tutti",
    solo_sezioni_unite: bool = False,
    anno_da: int = 0,
    anno_a: int = 0,
    max_risultati: int = 5,
    pagina: int = 0,
) -> str:
    max_risultati = min(max_risultati, 50)
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
    try:
        data = await solr_query(params)
    except Exception as exc:
        return f"Errore nella ricerca per norma: {exc}"
    docs = data.get("response", {}).get("docs", [])
    num_found = data.get("response", {}).get("numFound", 0)
    highlighting = data.get("highlighting", {})
    if not docs:
        return f"Nessuna decisione trovata per il riferimento: {riferimento}"
    start_idx = pagina * max_risultati + 1
    end_idx = start_idx + len(docs) - 1
    lines = [f"**Trovate {num_found} decisioni su**: _{riferimento}_ (mostro {start_idx}-{end_idx})\n"]
    for doc in docs:
        doc_id = doc.get("id", "")
        hl = highlighting.get(doc_id)
        lines.append(format_summary(doc, hl))
        lines.append("")
    return "\n".join(lines)


async def _ultime_pronunce_impl(
    materia: str = "",
    sezione: str = "",
    archivio: str = "tutti",
    tipo_provvedimento: str = "",
    solo_sezioni_unite: bool = False,
    max_risultati: int = 5,
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
    fq_parts: list[str] = []
    if materia:
        fq_parts.append(f"materia:{materia}")
    if sezione:
        fq_parts.append(f"szdec:{sezione}")
    if solo_sezioni_unite:
        fq_parts.append("szdec:(SU OR U)")
    if tipo_provvedimento and tipo_provvedimento in TIPO_PROV:
        fq_parts.append(f"tipoprov:{TIPO_PROV[tipo_provvedimento]}")
    if fq_parts:
        params["fq"] = fq_parts
    try:
        data = await solr_query(params)
    except Exception as exc:
        return f"Errore nel recupero ultime pronunce: {exc}"
    docs = data.get("response", {}).get("docs", [])
    num_found = data.get("response", {}).get("numFound", 0)
    if not docs:
        return "Nessuna decisione recente trovata con i filtri specificati."
    lines = [f"**Ultime pronunce della Cassazione** ({num_found} totali)\n"]
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
    tipo_provvedimento: str = "",
    solo_sezioni_unite: bool = False,
    ordinamento: str = "rilevanza",
    max_risultati: int = 5,
    pagina: int = 0,
) -> str:
    """Ricerca full-text nelle sentenze della Cassazione su Italgiure (fonte ufficiale).

    Usare per trovare decisioni su un tema quando non si conosce il numero specifico.
    Una volta trovato il numero, usare leggi_sentenza() per il testo completo.
    Dopo questo tool: leggi_sentenza() per leggere il testo integrale delle decisioni trovate.
    Restituisce: lista di decisioni con numero, data, sezione, dispositivo e snippet matching.
    L'output mostra il totale trovato e il range visualizzato. Usare pagina>0 per navigare.

    Args:
        query: Testo da cercare nel corpo delle decisioni
        archivio: "civile", "penale", o "tutti" (default)
        materia: Filtro per materia (es. "contratti", "responsabilita' civile")
        sezione: Filtro sezione (1-6, L=lavoro, T=tributaria, SU=sezioni unite)
        anno_da: Anno di inizio (incluso)
        anno_a: Anno di fine (incluso)
        tipo_provvedimento: "sentenza", "ordinanza", o "decreto" (default: tutti)
        solo_sezioni_unite: Se True, filtra solo decisioni delle Sezioni Unite (default: False)
        ordinamento: "rilevanza" (score desc, default) o "data" (più recenti prima)
        max_risultati: Numero massimo di risultati per pagina (default 5, max 50)
        pagina: Pagina dei risultati, 0-indexed (default 0 = prima pagina)
    """
    return await _cerca_giurisprudenza_impl(
        query, archivio=archivio, materia=materia, sezione=sezione,
        anno_da=anno_da, anno_a=anno_a, tipo_provvedimento=tipo_provvedimento,
        solo_sezioni_unite=solo_sezioni_unite, ordinamento=ordinamento,
        max_risultati=max_risultati, pagina=pagina,
    )


@mcp.tool(tags={"giurisprudenza"})
async def giurisprudenza_su_norma(
    riferimento: str,
    archivio: str = "tutti",
    solo_sezioni_unite: bool = False,
    anno_da: int = 0,
    anno_a: int = 0,
    max_risultati: int = 5,
    pagina: int = 0,
) -> str:
    """Trova sentenze della Cassazione che citano uno specifico articolo di legge.

    Workflow Brocardi→Italgiure: usa cerca_brocardi() per ottenere le massime con
    riferimenti strutturati, poi questo tool per leggere le sentenze complete.
    Dopo questo tool: leggi_sentenza() per il testo completo delle decisioni trovate.
    Restituisce: decisioni della Cassazione che citano la norma, con numero e snippet.

    Args:
        riferimento: Riferimento normativo (es. "art. 2043 c.c.", "art. 13 GDPR", "art. 6 D.Lgs. 231/2001")
        archivio: "civile", "penale", o "tutti" (default)
        solo_sezioni_unite: Se True, filtra solo decisioni delle Sezioni Unite (default: False)
        anno_da: Anno di inizio (incluso, es. 2020)
        anno_a: Anno di fine (incluso, es. 2025)
        max_risultati: Numero massimo di risultati per pagina (default 5)
        pagina: Pagina dei risultati, 0-indexed (default 0 = prima pagina)
    """
    return await _giurisprudenza_su_norma_impl(
        riferimento, archivio=archivio, solo_sezioni_unite=solo_sezioni_unite,
        anno_da=anno_da, anno_a=anno_a, max_risultati=max_risultati, pagina=pagina,
    )


@mcp.tool(tags={"giurisprudenza"})
async def ultime_pronunce(
    materia: str = "",
    sezione: str = "",
    archivio: str = "tutti",
    tipo_provvedimento: str = "",
    solo_sezioni_unite: bool = False,
    max_risultati: int = 5,
) -> str:
    """Ultime pronunce depositate dalla Cassazione, con filtri opzionali.

    Dopo questo tool: leggi_sentenza() per leggere il testo integrale di una decisione specifica.
    Restituisce: lista cronologica delle ultime decisioni depositate con metadati e dispositivo.

    Args:
        materia: Filtro per materia
        sezione: Filtro sezione (1-6, L=lavoro, T=tributaria, SU=sezioni unite)
        archivio: "civile", "penale", o "tutti" (default)
        tipo_provvedimento: "sentenza", "ordinanza", o "decreto"
        solo_sezioni_unite: Se True, filtra solo decisioni delle Sezioni Unite (default: False)
        max_risultati: Numero massimo di risultati (default 5)
    """
    return await _ultime_pronunce_impl(
        materia=materia, sezione=sezione, archivio=archivio,
        tipo_provvedimento=tipo_provvedimento, solo_sezioni_unite=solo_sezioni_unite,
        max_risultati=max_risultati,
    )

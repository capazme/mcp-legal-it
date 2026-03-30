"""MCP tools for searching Italian Supreme Court (Cassazione) decisions via Italgiure.

TRIGGER: usa questi tool quando l'utente menziona una sentenza con numero e anno espliciti.
Non fare web search per sentenze già identificate — il testo ufficiale è su Italgiure.
"""

from src.server import mcp
from src.lib._result import SearchResult
from src.lib.italgiure.client import (
    TIPO_PROV,
    SolrSession,
    build_explore_params,
    build_lookup_params,
    build_norma_variants,
    build_search_params,
    format_facets,
    format_full_text,
    format_summary,
    get_kind_filter,
    solr_query,
)

_SCORE_RATIO_THRESHOLD = 0.2
_REFINEMENT_THRESHOLD = 50

_REFINEMENT_STEPS = [
    {"mm": "100%", "label": "tutti i termini richiesti"},
    {"campo": "dispositivo", "label": "solo nel dispositivo"},
    {"tipo_provvedimento": "sentenza", "label": "solo sentenze"},
]


# ---------------------------------------------------------------------------
# Score filtering
# ---------------------------------------------------------------------------

def _filter_by_score(docs: list[dict]) -> tuple[list[dict], int]:
    """Keep only docs with score > 20% of the maximum. Passthrough if score absent."""
    if not docs:
        return docs, 0
    scores = [d.get("score") for d in docs]
    if scores[0] is None:
        return docs, 0
    max_score = max(float(s) for s in scores if s is not None)
    if max_score == 0:
        return docs, 0
    threshold = max_score * _SCORE_RATIO_THRESHOLD
    filtered = [d for d in docs if float(d.get("score", 0)) >= threshold]
    return filtered, len(docs) - len(filtered)


# ---------------------------------------------------------------------------
# Impl functions (testable without MCP context)
# ---------------------------------------------------------------------------

async def _leggi_sentenza_impl(
    numero: int,
    anno: int,
    sezione: str = "",
    archivio: str = "tutti",
) -> SearchResult:
    params = build_lookup_params(numero, anno, archivio=archivio, sezione=sezione or None)
    try:
        data = await solr_query(params)
        docs = data.get("response", {}).get("docs", [])
        if docs:
            return SearchResult(success=True, source="italgiure", num_found=1, results_text=format_full_text(docs[0]))
    except Exception as exc:
        return SearchResult(success=False, source="italgiure", error_type="source_down", error_message=str(exc))
    return SearchResult(success=False, source="italgiure", error_type="no_results", results_text=f"Decisione n. {numero}/{anno} non trovata negli archivi della Cassazione.")


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
    campo: str = "tutto",
    modalita: str = "cerca",
) -> SearchResult | str:
    # --- Explore mode: facets only, no documents — returns plain str ---
    if modalita == "esplora":
        return await _esplora_impl(query, archivio=archivio, campo=campo)

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
        campo=campo,
        include_facets=True,
    )
    try:
        data = await solr_query(params)
    except Exception as exc:
        return SearchResult(success=False, source="italgiure", error_type="source_down", error_message=str(exc))

    num_found = data.get("response", {}).get("numFound", 0)
    facet_counts = data.get("facet_counts", {})

    # --- Auto-refinement when too many results ---
    if (
        num_found > _REFINEMENT_THRESHOLD
        and ordinamento == "rilevanza"
        and pagina == 0
        and not any([materia, sezione, tipo_provvedimento, solo_sezioni_unite])
    ):
        refined = await _auto_refine(
            query, archivio, anno_da, anno_a, max_risultati,
            num_found, facet_counts, data,
        )
        if refined is not None:
            return SearchResult(success=True, source="italgiure", num_found=num_found, results_text=refined)

    text = _format_search_results(
        data, query, ordinamento, pagina, max_risultati, num_found, facet_counts,
    )
    return SearchResult(success=True, source="italgiure", num_found=num_found, results_text=text)


async def _esplora_impl(
    query: str,
    archivio: str = "tutti",
    campo: str = "tutto",
) -> str:
    """Facet-only exploration: returns distribution without documents."""
    params = build_explore_params(query, archivio=archivio, campo=campo)
    try:
        data = await solr_query(params)
    except Exception as exc:
        return f"Errore nell'esplorazione: {exc}"
    num_found = data.get("response", {}).get("numFound", 0)
    if num_found == 0:
        return "Nessuna decisione trovata per la ricerca indicata."
    facet_counts = data.get("facet_counts", {})
    lines = [f"**Esplorazione**: _{query}_ — {num_found} decisioni trovate\n"]
    facets_text = format_facets(facet_counts, num_found)
    if facets_text:
        lines.append(facets_text)
    lines.append("")
    lines.append("> **Suggerimento**: usa `modalita=\"cerca\"` con filtri specifici (materia, sezione, anno, tipo_provvedimento) per ottenere risultati mirati.")
    return "\n".join(lines)


async def _auto_refine(
    query: str,
    archivio: str,
    anno_da: int,
    anno_a: int,
    max_risultati: int,
    original_num_found: int,
    original_facets: dict,
    original_data: dict,
) -> str | None:
    """Try progressive refinement steps to reduce results below threshold.

    Returns formatted output if refinement succeeded, None to fall back to original.
    """
    best_data = None
    best_count = original_num_found
    best_label = ""

    try:
        async with SolrSession() as session:
            for step in _REFINEMENT_STEPS:
                step_params = build_search_params(
                    query,
                    archivio=archivio,
                    anno_da=anno_da or None,
                    anno_a=anno_a or None,
                    rows=max_risultati,
                    start=0,
                    campo=step.get("campo", "tutto"),
                    mm=step.get("mm"),
                    tipo_provvedimento=step.get("tipo_provvedimento"),
                    include_facets=True,
                )
                step_data = await solr_query(step_params, session=session)
                step_count = step_data.get("response", {}).get("numFound", 0)
                if 0 < step_count <= _REFINEMENT_THRESHOLD:
                    return _format_search_results(
                        step_data, query, "rilevanza", 0, max_risultati,
                        step_count,
                        step_data.get("facet_counts", {}),
                        refinement_note=f"Raffinamento automatico: {step['label']} ({original_num_found} → {step_count})",
                    )
                if 0 < step_count < best_count:
                    best_data = step_data
                    best_count = step_count
                    best_label = step["label"]
    except Exception:
        return None

    if best_data is not None and best_count < original_num_found:
        return _format_search_results(
            best_data, query, "rilevanza", 0, max_risultati,
            best_count,
            best_data.get("facet_counts", {}),
            refinement_note=f"Raffinamento automatico: {best_label} ({original_num_found} → {best_count})",
        )
    return None


def _format_search_results(
    data: dict,
    query: str,
    ordinamento: str,
    pagina: int,
    max_risultati: int,
    num_found: int,
    facet_counts: dict,
    refinement_note: str = "",
) -> str:
    """Format Solr search results into markdown output."""
    docs = data.get("response", {}).get("docs", [])
    highlighting = data.get("highlighting", {})

    if not docs:
        return "Nessuna decisione trovata per la ricerca indicata."

    # Score filtering
    docs, dropped = _filter_by_score(docs)
    if not docs:
        return "Nessuna decisione trovata per la ricerca indicata."

    start_idx = pagina * max_risultati + 1
    end_idx = start_idx + len(docs) - 1
    ord_label = "per rilevanza" if ordinamento == "rilevanza" else "per data"

    if dropped > 0:
        lines = [f"**Trovate {num_found} decisioni** ({len(docs)} ad alta rilevanza) per: _{query}_ (mostro {start_idx}-{end_idx}, {ord_label})\n"]
    else:
        lines = [f"**Trovate {num_found} decisioni** per: _{query}_ (mostro {start_idx}-{end_idx}, {ord_label})\n"]

    if refinement_note:
        lines.append(f"*{refinement_note}*\n")

    for doc in docs:
        doc_id = doc.get("id", "")
        hl = highlighting.get(doc_id)
        lines.append(format_summary(doc, hl))
        lines.append("")

    # Append facets if many results
    if num_found > _REFINEMENT_THRESHOLD and facet_counts:
        facets_text = format_facets(facet_counts, num_found)
        if facets_text:
            lines.append("---")
            lines.append(facets_text)
            lines.append("")
            lines.append('> **Suggerimento**: restringi con filtri specifici (materia, sezione, anno, tipo_provvedimento)')

    return "\n".join(lines)


async def _giurisprudenza_su_norma_impl(
    riferimento: str,
    archivio: str = "tutti",
    solo_sezioni_unite: bool = False,
    anno_da: int = 0,
    anno_a: int = 0,
    max_risultati: int = 5,
    pagina: int = 0,
) -> SearchResult:
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
        return SearchResult(success=False, source="italgiure", error_type="source_down", error_message=str(exc))
    docs = data.get("response", {}).get("docs", [])
    num_found = data.get("response", {}).get("numFound", 0)
    highlighting = data.get("highlighting", {})
    if not docs:
        return SearchResult(success=False, source="italgiure", error_type="no_results", results_text=f"Nessuna decisione trovata per il riferimento: {riferimento}")
    start_idx = pagina * max_risultati + 1
    end_idx = start_idx + len(docs) - 1
    lines = [f"**Trovate {num_found} decisioni su**: _{riferimento}_ (mostro {start_idx}-{end_idx})\n"]
    for doc in docs:
        doc_id = doc.get("id", "")
        hl = highlighting.get(doc_id)
        lines.append(format_summary(doc, hl))
        lines.append("")
    return SearchResult(success=True, source="italgiure", num_found=num_found, results_text="\n".join(lines))


async def _ultime_pronunce_impl(
    materia: str = "",
    sezione: str = "",
    archivio: str = "tutti",
    tipo_provvedimento: str = "",
    solo_sezioni_unite: bool = False,
    max_risultati: int = 5,
) -> SearchResult:
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
        return SearchResult(success=False, source="italgiure", error_type="source_down", error_message=str(exc))
    docs = data.get("response", {}).get("docs", [])
    num_found = data.get("response", {}).get("numFound", 0)
    if not docs:
        return SearchResult(success=False, source="italgiure", error_type="no_results", results_text="Nessuna decisione recente trovata con i filtri specificati.")
    lines = [f"**Ultime pronunce della Cassazione** ({num_found} totali)\n"]
    for doc in docs:
        lines.append(format_summary(doc))
        lines.append("")
    return SearchResult(success=True, source="italgiure", num_found=num_found, results_text="\n".join(lines))


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
    result = await _leggi_sentenza_impl(numero, anno, sezione=sezione, archivio=archivio)
    return result.to_str() if isinstance(result, SearchResult) else result


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
    campo: str = "tutto",
    modalita: str = "cerca",
) -> str:
    """Ricerca full-text nelle sentenze della Cassazione su Italgiure (fonte ufficiale, archivio 2020+).

    **Strategia consigliata**:
    1. Prima esplora: `modalita="esplora"` per vedere distribuzione risultati (materia, sezione, anno, tipo)
    2. Poi cerca con filtri: usa i filtri suggeriti per restringere a <50 risultati
    3. Leggi i testi: `leggi_sentenza()` per il testo completo delle decisioni trovate

    **Sintassi query Solr** (campo `query`):
    - `"frase esatta"` — virgolette per match esatto
    - `AND` / `OR` — operatori booleani (default: OR tra i termini)
    - `-termine` — esclude termine
    - `"frase esatta"~3` — prossimità (termini entro 3 parole)
    - `termin*` — wildcard (prefisso)

    Con query generiche (es. "responsabilità medica") il sistema tenta un raffinamento automatico
    per ridurre i risultati. Se i risultati sono >50, mostra anche la distribuzione per facet.
    Con `modalita="esplora"` non restituisce documenti, solo la distribuzione.

    Args:
        query: Testo da cercare nel corpo delle decisioni (supporta sintassi Solr eDisMax)
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
        campo: "tutto" (testo+dispositivo, default) o "dispositivo" (cerca solo nel dispositivo — più preciso, meno recall)
        modalita: "cerca" (default — restituisce documenti) o "esplora" (solo distribuzione facet, nessun documento)
    """
    result = await _cerca_giurisprudenza_impl(
        query, archivio=archivio, materia=materia, sezione=sezione,
        anno_da=anno_da, anno_a=anno_a, tipo_provvedimento=tipo_provvedimento,
        solo_sezioni_unite=solo_sezioni_unite, ordinamento=ordinamento,
        max_risultati=max_risultati, pagina=pagina, campo=campo, modalita=modalita,
    )
    return result.to_str() if isinstance(result, SearchResult) else result


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
    result = await _giurisprudenza_su_norma_impl(
        riferimento, archivio=archivio, solo_sezioni_unite=solo_sezioni_unite,
        anno_da=anno_da, anno_a=anno_a, max_risultati=max_risultati, pagina=pagina,
    )
    return result.to_str() if isinstance(result, SearchResult) else result


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
    result = await _ultime_pronunce_impl(
        materia=materia, sezione=sezione, archivio=archivio,
        tipo_provvedimento=tipo_provvedimento, solo_sezioni_unite=solo_sezioni_unite,
        max_risultati=max_risultati,
    )
    return result.to_str() if isinstance(result, SearchResult) else result

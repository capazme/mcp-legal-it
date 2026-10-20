"""MCP tools for searching Italian Supreme Court (Cassazione) decisions via Italgiure.

TRIGGER: usa questi tool quando l'utente menziona una sentenza con numero e anno espliciti.
Non fare web search per sentenze già identificate — il testo ufficiale è su Italgiure.
"""

import asyncio
import re

from src.server import mcp
from src.lib._paging import invalid_start
from src.lib._result import SearchResult
from src.lib.brocardi.client import fetch_brocardi, parse_massime_references
from src.lib.visualex import resolve_atto
from src.lib.italgiure.client import (
    ARCHIVE_START_YEAR,
    ARCHIVE_WINDOW_NOTE,
    TIPO_PROV,
    SolrSession,
    build_explore_params,
    build_lookup_params,
    build_norma_variants,
    build_search_params,
    format_estremi,
    format_facets,
    format_full_text,
    format_summary,
    get_kind_filter,
    norma_is_qualified,
    quote_fq_value,
    resolve_sezione,
    solr_query,
)

_SCORE_RATIO_THRESHOLD = 0.2
_REFINEMENT_THRESHOLD = 50

_REFINEMENT_STEPS = [
    {"mm": "100%", "label": "tutti i termini richiesti"},
    {"campo": "dispositivo", "label": "solo nel dispositivo"},
    {"tipo_provvedimento": "sentenza", "label": "solo sentenze"},
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
    # Treat docs with a missing/None score as passthrough rather than coercing to 0,
    # aligning the per-doc filter with the None-skipping max computation above.
    filtered = [d for d in docs if d.get("score") is None or float(d["score"]) >= threshold]
    return filtered, len(docs) - len(filtered)


# ---------------------------------------------------------------------------
# Impl functions (testable without MCP context)
# ---------------------------------------------------------------------------

def _omonimi_note(docs: list[dict], chosen: dict, archivio: str, numero: int, anno: int) -> str:
    """Warn when the same number/year names several decisions (e.g. a civil and a criminal one).

    Italgiure numbers decisions per branch: with archivio="tutti", n. 10579/2022 is both a
    civil (sez. V) and a criminal (sez. VII) decision. The first hit is returned; the caller
    must be told that others exist, and how to choose.
    """
    chosen_id = _first_value(chosen.get("id"))
    others = [d for d in docs if _first_value(d.get("id")) != chosen_id]
    if not others:
        return ""
    elenco = "; ".join(format_estremi(d) for d in others)
    return (
        f"\n\n---\n*Attenzione: con archivio='{archivio}' esistono più decisioni n. {numero}/{anno}; "
        f"restituita {format_estremi(chosen)}. Esiste anche: {elenco}. "
        f"Indicare archivio='civile' o 'penale' (o la sezione) per sceglierne una.*"
    )


def _first_value(val) -> str:
    if isinstance(val, list):
        return str(val[0]) if val else ""
    return str(val) if val is not None else ""


async def _leggi_sentenza_impl(
    numero: int,
    anno: int,
    sezione: str = "",
    archivio: str = "tutti",
    formatter=format_full_text,
    da_carattere: int = 1,
) -> SearchResult:
    """Read one decision. *formatter* renders the document (full text by default).

    *da_carattere* > 1 reads the window of the ``ocr`` text that starts there (full-text
    formatter only: other formatters are always called with the default).
    """
    if (error := invalid_start(da_carattere)) is not None:
        return SearchResult(success=False, source="italgiure", error_type="bad_input", results_text=error)
    if da_carattere > 1:
        base_formatter = formatter

        def formatter(doc: dict) -> str:  # noqa: F811 - bind the window start
            return base_formatter(doc, da_carattere=da_carattere)

    try:
        sezione, archivio = resolve_sezione(sezione, archivio)
    except ValueError as exc:
        return SearchResult(success=False, source="italgiure", error_type="bad_input", results_text=str(exc))

    def _found(docs: list[dict]) -> SearchResult:
        text = formatter(docs[0]) + _omonimi_note(docs, docs[0], archivio, numero, anno)
        return SearchResult(success=True, source="italgiure", num_found=1, results_text=text)

    try:
        async with SolrSession() as session:
            # Step 1: Standard lookup (zero-padded + sezione)
            params = build_lookup_params(numero, anno, archivio=archivio, sezione=sezione or None)
            data = await solr_query(params, session=session)
            docs = data.get("response", {}).get("docs", [])
            if docs:
                return _found(docs)

            # Step 2: Retry without sezione filter (if provided)
            if sezione:
                params = build_lookup_params(numero, anno, archivio=archivio, sezione=None)
                data = await solr_query(params, session=session)
                docs = data.get("response", {}).get("docs", [])
                if docs:
                    return _found(docs)

            # Step 3: Retry with raw number (no zero-padding)
            kinds = get_kind_filter(archivio)
            kind_clause = " OR ".join(f'kind:"{k}"' for k in kinds)
            raw_params = {
                "q": f"({kind_clause}) AND numdec:{numero} AND anno:{anno}",
                "rows": 5,
                "fl": "id,numdec,anno,datdep,szdec,materia,tipoprov,ocr,ocrdis,relatore,presidente,kind",
            }
            data = await solr_query(raw_params, session=session)
            docs = data.get("response", {}).get("docs", [])
            if docs:
                return _found(docs)

            # Step 4: Full-text search for "n. {numero}/{anno}"
            ft_query = f'"n. {numero}/{anno}" OR "n. {numero} del {anno}"'
            ft_params = build_search_params(
                ft_query, archivio=archivio, rows=3, start=0, campo="tutto",
            )
            data = await solr_query(ft_params, session=session)
            docs = data.get("response", {}).get("docs", [])
            if docs:
                # Validate that a returned doc actually IS the requested decision —
                # a full-text hit merely citing "n. {numero}/{anno}" in its OCR text
                # would otherwise be returned as the authoritative text (wrong ruling).
                numdec_candidates = {str(numero), str(numero).zfill(5)}
                for doc in docs:
                    if str(doc.get("numdec")) in numdec_candidates and str(doc.get("anno")) == str(anno):
                        return SearchResult(
                            success=True, source="italgiure", num_found=1, results_text=formatter(doc),
                        )

    except Exception as exc:
        return SearchResult(success=False, source="italgiure", error_type="source_down", error_message=str(exc))

    return SearchResult(
        success=False,
        source="italgiure",
        error_type="no_results",
        results_text=(
            f"Decisione n. {numero}/{anno} non trovata negli archivi della Cassazione.\n\n"
            f"**Possibili cause**: sentenza non ancora indicizzata (lag archivio), "
            f"numero o anno errato, oppure decisione anteriore alla finestra dell'archivio: "
            f"{ARCHIVE_WINDOW_NOTE}.\n"
            f"**Suggerimento**: prova `cerca_giurisprudenza()` con il tema della sentenza."
        ),
    )


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
    ancora_norma: str = "",
    auto_refine: bool = True,
) -> SearchResult | str:
    """Full-text search. *ancora_norma* (a reference such as "art. 2043 c.c.") restricts the
    results to decisions that cite that article; *auto_refine=False* disables the automatic
    narrowing of broad queries (used with an anchor, where narrowing to the dispositivo only
    latches onto boilerplate)."""
    # --- Explore mode: facets only, no documents — returns plain str ---
    if modalita == "esplora":
        return await _esplora_impl(query, archivio=archivio, campo=campo)

    try:
        sezione, archivio = resolve_sezione(sezione, archivio)
    except ValueError as exc:
        return SearchResult(success=False, source="italgiure", error_type="bad_input", results_text=str(exc))

    # Normalize query to improve Solr matching
    query = _normalize_query(query)

    fq_extra = [build_norma_variants(ancora_norma, strict=True)] if ancora_norma else None
    max_risultati = min(max_risultati, 50)
    params = build_search_params(
        query,
        archivio=archivio,
        materia=materia or None,
        sezione=sezione or None,
        fq_extra=fq_extra,
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

    # --- Auto-relaxation when zero results ---
    if num_found == 0 and pagina == 0:
        relaxed = await _auto_relax(
            query, archivio, materia, sezione, anno_da, anno_a,
            tipo_provvedimento, solo_sezioni_unite, max_risultati, campo,
            fq_extra=fq_extra,
        )
        if relaxed is not None:
            return SearchResult(success=True, source="italgiure", num_found=0, results_text=relaxed)

    # --- Auto-refinement when too many results ---
    if (
        auto_refine
        and num_found > _REFINEMENT_THRESHOLD
        and ordinamento == "rilevanza"
        and pagina == 0
        and not any([materia, sezione, tipo_provvedimento, solo_sezioni_unite])
    ):
        refined = await _auto_refine(
            query, archivio, anno_da, anno_a, max_risultati,
            num_found, facet_counts, data,
        )
        if refined is not None:
            # Report the refined count printed in the text, not the original one.
            refined_text, refined_count = refined
            return SearchResult(success=True, source="italgiure", num_found=refined_count, results_text=refined_text)

    text = _format_search_results(
        data, query, ordinamento, pagina, max_risultati, num_found, facet_counts,
    )
    return SearchResult(success=True, source="italgiure", num_found=num_found, results_text=text)


_SEZIONE_NAMES = {
    "L": "Lavoro", "T": "Tributaria", "SU": "Sezioni Unite", "U": "Sezioni Unite", "F": "Feriale",
    "1": "I", "2": "II", "3": "III", "4": "IV", "5": "V", "6": "VI", "7": "VII",
}

_BROAD_THRESHOLD = 10000


def _smart_suggestions(facet_counts: dict, num_found: int) -> list[str]:
    """Generate actionable filter suggestions from facet data."""
    facet_fields = facet_counts.get("facet_fields", {})
    suggestions = []

    # Suggest top sezione if discriminant
    sez_raw = facet_fields.get("szdec", [])
    sez_pairs = list(zip(sez_raw[0::2], sez_raw[1::2]))
    if sez_pairs:
        top_sez, top_count = sez_pairs[0]
        sez_name = _SEZIONE_NAMES.get(str(top_sez), str(top_sez))
        if top_count < num_found * 0.8:  # Only suggest if it filters out >20%
            suggestions.append(
                f'Aggiungi `sezione="{top_sez}"` per filtrare Sezione {sez_name} ({top_count} risultati)'
            )

    # Suggest anno range
    anno_raw = facet_fields.get("anno", [])
    anno_pairs = list(zip(anno_raw[0::2], anno_raw[1::2]))
    if len(anno_pairs) >= 3:
        recent_count = sum(c for _, c in anno_pairs[:2])
        suggestions.append(
            f"Aggiungi `anno_da={anno_pairs[0][0]}` per limitare agli ultimi 2 anni ({recent_count} risultati)"
        )

    # Suggest tipo provvedimento
    tipo_raw = facet_fields.get("tipoprov", [])
    tipo_pairs = list(zip(tipo_raw[0::2], tipo_raw[1::2]))
    for tipo_code, tipo_count in tipo_pairs:
        if str(tipo_code) == "Sentenza" and tipo_count < num_found * 0.5:
            suggestions.append(
                f'Aggiungi `tipo_provvedimento="sentenza"` per solo sentenze ({tipo_count} risultati)'
            )
            break

    # Always suggest query reform
    suggestions.append("Riformula la query con 2-3 termini specifici e usa i filtri strutturati")

    return suggestions


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

    # Smart suggestions for broad queries
    if num_found > _BROAD_THRESHOLD:
        suggestions = _smart_suggestions(facet_counts, num_found)
        lines.append(f"> **Query troppo generica** ({num_found} risultati). Suggerimenti per restringere:")
        for s in suggestions:
            lines.append(f"> - {s}")
    else:
        lines.append("> **Suggerimento**: usa `modalita=\"cerca\"` con filtri specifici (materia, sezione, anno, tipo_provvedimento) per ottenere risultati mirati.")

    return "\n".join(lines)


_RELAXATION_STEPS = [
    {"strip_quotes": True, "label": "senza virgolette"},
    {"mm": "2<50% 5<40%", "label": "corrispondenza rilassata"},
    {"max_terms": 4, "label": "termini chiave ridotti"},
]


def _strip_all_quotes(query: str) -> str:
    """Remove all double quotes from query."""
    return query.replace('"', '')


def _keep_top_terms(query: str, n: int) -> str:
    """Keep only the first N non-stopword, non-operator terms."""
    terms = query.split()
    kept = []
    for t in terms:
        if t in ("AND", "OR", "NOT") or t.startswith("-"):
            continue
        if t.lower().rstrip(".,;:") in _IT_STOPWORDS:
            continue
        kept.append(t)
        if len(kept) >= n:
            break
    return " ".join(kept) if kept else query


async def _auto_relax(
    query: str,
    archivio: str,
    materia: str,
    sezione: str,
    anno_da: int,
    anno_a: int,
    tipo_provvedimento: str,
    solo_sezioni_unite: bool,
    max_risultati: int,
    campo: str,
    fq_extra: list[str] | None = None,
) -> str | None:
    """Try progressive query relaxation when num_found == 0.

    Returns formatted output if relaxation found results, None otherwise.
    """
    try:
        async with SolrSession() as session:
            for step in _RELAXATION_STEPS:
                step_query = query
                step_mm = None
                step_campo = campo

                if step.get("strip_quotes"):
                    step_query = _strip_all_quotes(step_query)
                    if step_query == query:
                        continue  # No quotes to strip, skip
                if step.get("mm"):
                    step_mm = step["mm"]
                if step.get("max_terms"):
                    step_query = _keep_top_terms(step_query, step["max_terms"])
                    if step_query == query:
                        continue  # Query unchanged, skip

                step_params = build_search_params(
                    step_query,
                    archivio=archivio,
                    materia=materia or None,
                    sezione=sezione or None,
                    anno_da=anno_da or None,
                    anno_a=anno_a or None,
                    tipo_provvedimento=tipo_provvedimento or None,
                    solo_sezioni_unite=solo_sezioni_unite,
                    rows=max_risultati,
                    start=0,
                    campo=step_campo,
                    mm=step_mm,
                    include_facets=True,
                    fq_extra=fq_extra,
                )
                step_data = await solr_query(step_params, session=session)
                step_count = step_data.get("response", {}).get("numFound", 0)
                if step_count > 0:
                    return _format_search_results(
                        step_data, step_query, "rilevanza", 0, max_risultati,
                        step_count,
                        step_data.get("facet_counts", {}),
                        refinement_note=f"Rilassamento automatico: {step['label']} (0 → {step_count} risultati)",
                    )
    except Exception:
        return None

    # All relaxation steps failed — return explore suggestion
    try:
        explore_result = await _esplora_impl(
            _keep_top_terms(query, 3), archivio=archivio, campo=campo,
        )
        if "decisioni trovate" in explore_result:
            return (
                "Nessuna decisione trovata con la query originale.\n\n"
                f"**Suggerimento**: prova a riformulare con 2-3 termini chiave e usa i filtri strutturati "
                f"(sezione, anno_da, tipo_provvedimento).\n\n"
                f"Distribuzione con termini ridotti:\n{explore_result}"
            )
    except Exception:
        pass

    return None


async def _auto_refine(
    query: str,
    archivio: str,
    anno_da: int,
    anno_a: int,
    max_risultati: int,
    original_num_found: int,
    original_facets: dict,
    original_data: dict,
) -> tuple[str, int] | None:
    """Try progressive refinement steps to reduce results below threshold.

    Returns (formatted output, refined result count) if refinement succeeded, None to fall
    back to the original.
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
                    ), step_count
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
        ), best_count
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
        try:
            data = await solr_query(params)
        except Exception:
            # The Solr highlighter answers 500 on some decisions matched by phrase queries
            # (read 2026-09-29): retry once without highlighting, so a highlighter fault is not
            # reported as "source down".
            plain = {k: v for k, v in params.items() if not k.startswith("hl")}
            data = await solr_query(plain)
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
    if not norma_is_qualified(riferimento):
        lines.append(
            "*Attenzione: il riferimento non indica il codice o l'atto. La ricerca trova ogni "
            "decisione che cita un qualsiasi \"art. N\": precisione bassa e totale gonfiato. "
            "Indicare l'atto (es. \"art. 13 GDPR\", \"art. 2043 c.c.\").*\n"
        )
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
    try:
        sezione, archivio = resolve_sezione(sezione, archivio)
    except ValueError as exc:
        return SearchResult(success=False, source="italgiure", error_type="bad_input", results_text=str(exc))
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
        fq_parts.append(f"materia:{quote_fq_value(materia)}")
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
        lines.append(format_summary(doc, con_tipo=True))
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
    da_carattere: int = 1,
) -> str:
    """Legge il testo completo di una specifica sentenza della Cassazione da Italgiure (fonte ufficiale).

    USARE SEMPRE quando l'utente menziona una sentenza con numero e anno già noti
    (es. "Cass. n. 10787/2024", "Sez. III n. 10787 del 22 aprile 2024").
    NON usare web search per sentenze identificate — questo tool è diretto e ufficiale.
    Restituisce: estremi, relatore e presidente, testo della decisione e, quando la fonte lo
    valorizza, il dispositivo. Italgiure NON fornisce una massima ufficiale.

    ATTENZIONE: il testo oltre 30000 caratteri è abbreviato (primi 12000 e ultimi 18000, parte
    centrale omessa, dichiarato in coda) e il campo Dispositivo può mancare alla fonte: in quel
    caso la decisione (rigetto, accoglimento, principio di diritto) è nella parte finale del testo.
    La parte omessa si legge ripetendo la chiamata con il da_carattere indicato nella nota: le
    posizioni contano i caratteri del testo della decisione (esclusi intestazione e Dispositivo)
    e con da_carattere > 1 si ottengono i 30000 caratteri che partono da quella posizione.
    L'archivio pubblico è una finestra mobile di circa cinque anni (a settembre 2026 dal
    27/09/2021): le decisioni anteriori risultano "non trovate". Con archivio="tutti" un numero
    può indicare una decisione civile e una penale: il tool restituisce la prima e segnala le altre;
    indicare archivio per scegliere.

    Args:
        numero: Numero della decisione (es. 10787)
        anno: Anno della decisione (es. 2024)
        sezione: Sezione della Corte (opzionale: 1-7, L=lavoro, U o SU=sezioni unite, F=feriale, T=tributaria=sezione 5 civile)
        archivio: "civile", "penale", o "tutti" (default)
        da_carattere: Carattere da cui leggere (1 = inizio, default). Se il testo supera il limite,
            la nota indica il valore con cui ripetere la chiamata per leggere il seguito
    """
    result = await _leggi_sentenza_impl(numero, anno, sezione=sezione, archivio=archivio, da_carattere=da_carattere)
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
    """Ricerca full-text nelle sentenze della Cassazione su Italgiure (fonte ufficiale, archivio pubblico a finestra mobile di circa 5 anni: a settembre 2026 dal 27/09/2021).

    **BEST PRACTICE per query efficaci**:
    - Usa 2-4 termini chiave, NON frasi lunghe o riferimenti normativi completi
    - EVITA virgolette salvo per espressioni fisse consolidate ("danno biologico", "legittimo affidamento")
    - USA i filtri strutturati (sezione, anno_da, tipo_provvedimento) invece di aggiungere termini alla query
    - Il sistema normalizza automaticamente la query (rimuove virgolette da riferimenti normativi, stopwords)
    - Se 0 risultati, il sistema tenta automaticamente rilassamento progressivo della query

    **Esempi**:
    - SBAGLIATO: query='"art. 1-bis" D.Lgs. 152/1997 collaboratori coordinati etero-organizzati'
    - CORRETTO: query="collaboratori coordinati monitoraggio automatizzato", sezione="L", anno_da=2022
    - SBAGLIATO: query='"art. 4" L. 300/1970 collaboratori autonomi monitoraggio controllo'
    - CORRETTO: query="controllo distanza lavoratori piattaforma", sezione="L", tipo_provvedimento="sentenza"

    **Strategia consigliata**:
    1. Prima esplora: `modalita="esplora"` con 2-3 termini → distribuzione risultati
    2. Poi cerca con filtri strutturati → risultati mirati (<50)
    3. Poi `leggi_sentenza()` → testo completo

    Con query generiche il sistema tenta raffinamento automatico.
    Con `modalita="esplora"` non restituisce documenti, solo la distribuzione.

    Args:
        query: 2-4 termini chiave (il sistema normalizza automaticamente). Supporta: "frase esatta", AND/OR, -esclusione, "frase"~3 prossimità, termin* wildcard
        archivio: "civile", "penale", o "tutti" (default)
        materia: Filtro per materia, cercata come frase (es. "contratti", "responsabilita' civile")
        sezione: Filtro sezione (1-7, L=lavoro, U o SU=sezioni unite, F=feriale, T=tributaria=sezione 5 civile; un codice sconosciuto è rifiutato con l'elenco dei validi). PREFERIRE questo ai termini nella query
        anno_da: Anno di inizio (incluso). PREFERIRE questo a scrivere l'anno nella query
        anno_a: Anno di fine (incluso)
        tipo_provvedimento: "sentenza", "ordinanza", o "decreto" (default: tutti). PREFERIRE questo a "solo sentenze" nella query
        solo_sezioni_unite: Se True, filtra solo decisioni delle Sezioni Unite (default: False)
        ordinamento: "rilevanza" (score desc, default) o "data" (più recenti prima)
        max_risultati: Numero massimo di risultati per pagina (default 5, max 50)
        pagina: Pagina dei risultati, 0-indexed (default 0 = prima pagina)
        campo: "tutto" (testo+dispositivo, default) o "dispositivo" (solo dispositivo — più preciso, meno recall)
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

    Genera automaticamente varianti del riferimento per massimizzare i risultati
    (es. "art. 2043 c.c." → cerca anche "articolo 2043", "2043 codice civile", "2043 cod. civ.").

    Il riferimento deve indicare il codice o l'atto ("art. 13 GDPR", "art. 6 D.Lgs. 231/2001"):
    per gli atti la ricerca richiede l'articolo N insieme agli estremi dell'atto (numero/anno o
    nome) nella stessa decisione, perché il solo "art. 13" trova ogni decisione che cita un
    qualsiasi art. 13 (in primis il d.P.R. 115/2002 sul contributo unificato). Un riferimento
    senza codice né atto è cercato in forma nuda e segnalato a bassa precisione.

    **Quando usare**: per trovare giurisprudenza su un articolo specifico.
    **Quando NON usare**: per ricerche per tema/concetto → usa cerca_giurisprudenza.
    **Dopo**: leggi_sentenza() per il testo completo delle decisioni trovate.

    Args:
        riferimento: Riferimento normativo breve (es. "art. 2043 c.c.", "art. 13 GDPR", "art. 6 D.Lgs. 231/2001"). NON aggiungere tema o parole chiave
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


def _parse_articolo_riferimento(riferimento: str) -> tuple[str, str]:
    """Extract (articolo, atto) from a legal reference like 'art. 2043 c.c.'.

    Returns (article_number, act_name_remainder) or ("", riferimento) on failure.
    """
    m = re.match(
        r"(?:articol[oi]|art)\.?\s*(\d+(?:[-/.]\w+)*)\s+(.+)",
        riferimento.strip(),
        re.IGNORECASE,
    )
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return "", riferimento.strip()


def _riferimenti_note(esclusi_intervallo: int, fuori_finestra: list[dict], non_reperiti: list[dict]) -> str:
    """One line per class of Brocardi references that did not reach the report."""
    notes = []
    if esclusi_intervallo:
        notes.append(f"{esclusi_intervallo} fuori dall'intervallo di anni richiesto")
    if fuori_finestra:
        elenco = ", ".join(f"n. {r['numero']}/{r['anno']}" for r in fuori_finestra[:5])
        notes.append(
            f"{len(fuori_finestra)} anteriori al {ARCHIVE_START_YEAR}, fuori dalla finestra dell'archivio "
            f"e non leggibili con leggi_sentenza ({elenco}{', ...' if len(fuori_finestra) > 5 else ''})"
        )
    if non_reperiti:
        elenco = ", ".join(f"n. {r['numero']}/{r['anno']}" for r in non_reperiti)
        notes.append(f"{len(non_reperiti)} non reperiti su Italgiure ({elenco})")
    if not notes:
        return ""
    return "*Riferimenti di Cassazione citati da Brocardi non riportati: " + "; ".join(notes) + ".*"


async def _giurisprudenza_articolo_impl(
    riferimento: str,
    archivio: str = "tutti",
    anno_da: int = 0,
    anno_a: int = 0,
    max_risultati: int = 5,
) -> SearchResult:
    articolo, atto_str = _parse_articolo_riferimento(riferimento)

    # Attempt Brocardi lookup only when we can resolve act + article
    brocardi_result = None
    if articolo and atto_str:
        act_info = resolve_atto(atto_str)
        if act_info:
            try:
                brocardi_result = await fetch_brocardi(
                    act_info["tipo_atto"],
                    articolo,
                    act_info.get("numero_atto", ""),
                    act_info.get("data", ""),
                )
                if brocardi_result.error:
                    brocardi_result = None
            except Exception:
                brocardi_result = None

    # Fallback: no Brocardi data -> delegate to _giurisprudenza_su_norma_impl, and say so.
    if brocardi_result is None or not brocardi_result.massime:
        fallback = await _giurisprudenza_su_norma_impl(
            riferimento,
            archivio=archivio,
            anno_da=anno_da,
            anno_a=anno_a,
            max_risultati=max_risultati,
        )
        if fallback.success:
            fallback.results_text = (
                f"*Brocardi: nessuna massima disponibile per {riferimento} (o fonte non raggiungibile): "
                f"ricerca per citazione dell'articolo su Italgiure.*\n\n{fallback.results_text}"
            )
        return fallback

    # --- Direct references from parse_massime_references, restricted to the requested years
    #     and to the archive window (older ones cannot be read) and reported when dropped ---
    all_refs = parse_massime_references(brocardi_result.massime)

    def _anno_ok(anno: int) -> bool:
        return (not anno_da or anno >= anno_da) and (not anno_a or anno <= anno_a)

    in_intervallo = [r for r in all_refs if _anno_ok(int(r["anno"]))]
    esclusi_intervallo = len(all_refs) - len(in_intervallo)
    fuori_finestra = [r for r in in_intervallo if int(r["anno"]) < ARCHIVE_START_YEAR]
    cass_refs = [r for r in in_intervallo if int(r["anno"]) >= ARCHIVE_START_YEAR][:3]

    # --- Text queries from massima testo (up to 3), anchored to the article ---
    query_massime = [m for m in brocardi_result.massime if m.testo][:3]

    # Launch all lookups in parallel
    async def _safe_lookup(numero: int, anno: int) -> SearchResult:
        try:
            # A summary (estremi, materia), not the full text: the full text of three
            # decisions makes the report tens of thousands of characters long.
            return await _leggi_sentenza_impl(numero, anno, archivio=archivio, formatter=format_summary)
        except Exception as exc:
            return SearchResult(success=False, source="italgiure", error_type="source_down", error_message=str(exc))

    async def _safe_search(query: str) -> SearchResult:
        try:
            # ancora_norma: only decisions that cite the article; auto_refine off: narrowing a
            # massima query "to the dispositivo" latches onto boilerplate formulas.
            result = await _cerca_giurisprudenza_impl(
                query,
                archivio=archivio,
                anno_da=anno_da,
                anno_a=anno_a,
                max_risultati=max_risultati,
                ancora_norma=riferimento,
                auto_refine=False,
            )
            return result if isinstance(result, SearchResult) else SearchResult(success=False, source="italgiure", error_type="no_results")
        except Exception as exc:
            return SearchResult(success=False, source="italgiure", error_type="source_down", error_message=str(exc))

    lookup_coros = [_safe_lookup(ref["numero"], ref["anno"]) for ref in cass_refs]
    search_coros = [_safe_search(m.testo[:300]) for m in query_massime]

    all_results = await asyncio.gather(*lookup_coros, *search_coros, return_exceptions=False)
    lookup_results = list(all_results[:len(lookup_coros)])
    search_results = list(all_results[len(lookup_coros):])

    # Deduplicate by (numdec, anno)
    seen_keys: set[str] = set()

    direct_lines: list[str] = []
    non_reperiti: list[dict] = []
    for i, sr in enumerate(lookup_results):
        ref = cass_refs[i]
        if not sr.success:
            if sr.error_type == "no_results":
                non_reperiti.append(ref)
            continue
        key = f"{ref['numero']}/{ref['anno']}"
        if key in seen_keys:
            continue
        seen_keys.add(key)
        direct_lines.append(sr.results_text or "")

    # For search results, extract individual docs to deduplicate
    search_lines: list[str] = []
    for sr in search_results:
        if not sr.success or not sr.results_text:
            continue
        # The results_text may contain multiple docs; append whole block
        # Dedup at block level by a simple hash
        block_key = sr.results_text[:80]
        if block_key in seen_keys:
            continue
        seen_keys.add(block_key)
        search_lines.append(sr.results_text)

    if not direct_lines and not search_lines:
        return SearchResult(
            success=False,
            source="italgiure",
            error_type="no_results",
            results_text=f"Nessuna sentenza trovata per {riferimento} (Brocardi: {len(brocardi_result.massime)} massime, nessuna risolubile su Italgiure).",
        )

    parts: list[str] = [
        f"## Giurisprudenza sull'{riferimento}\n",
        f"**Fonte Brocardi**: {len(brocardi_result.massime)} massime trovate per {riferimento}\n",
    ]
    nota = _riferimenti_note(esclusi_intervallo, fuori_finestra, non_reperiti)
    if nota:
        parts.append(nota + "\n")

    if direct_lines:
        parts.append("### Sentenze con riferimento diretto")
        parts.extend(direct_lines)
        parts.append("")

    if search_lines:
        parts.append("### Sentenze per principio di diritto")
        parts.extend(search_lines)

    total = len(direct_lines) + sum(
        (sr.num_found or 0) for sr in search_results if sr.success
    )
    return SearchResult(
        success=True,
        source="italgiure",
        num_found=total,
        results_text="\n".join(parts),
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
    Restituisce: lista cronologica delle ultime decisioni depositate con metadati (estremi, tipo
    sent./ord./decr., materia) e dispositivo quando presente. L'indicizzazione ha un ritardo di
    alcuni giorni rispetto al deposito.

    Args:
        materia: Filtro per materia, cercata come frase (es. "responsabilita' civile")
        sezione: Filtro sezione (1-7, L=lavoro, U o SU=sezioni unite, F=feriale, T=tributaria=sezione 5 civile; un codice sconosciuto è rifiutato)
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


@mcp.tool(tags={"giurisprudenza"})
async def giurisprudenza_articolo(
    riferimento: str,
    archivio: str = "tutti",
    anno_da: int = 0,
    anno_a: int = 0,
    max_risultati: int = 5,
) -> str:
    """Cerca giurisprudenza su un articolo usando le massime Brocardi come guida.

    Workflow: recupera le massime giurisprudenziali da Brocardi per l'articolo indicato,
    poi usa il testo dei principi di diritto come query di ricerca su Italgiure, limitata alle
    decisioni che citano l'articolo (senza raffinamento automatico). Inoltre elenca (estremi e
    materia, non il testo: usare leggi_sentenza) le sentenze Cassazione citate nelle massime.
    Le sentenze citate da Brocardi anteriori alla finestra dell'archivio (a settembre 2026 dal
    27/09/2021) o fuori dall'intervallo anno_da/anno_a sono escluse e segnalate; senza massime
    Brocardi il tool ripiega su giurisprudenza_su_norma e lo dichiara.

    USARE quando il tema riguarda un articolo specifico (es. "art. 2043 c.c.").
    Per ricerche generiche per tema, usare cerca_giurisprudenza.

    Args:
        riferimento: Riferimento normativo (es. "art. 2043 c.c.", "art. 6 D.Lgs. 231/2001")
        archivio: Collezione Italgiure: 'civile', 'penale' o 'tutti' (default)
        anno_da: Anno minimo (es. 2022), applicato anche ai riferimenti diretti. 0 = nessun filtro.
        anno_a: Anno massimo (es. 2025), applicato anche ai riferimenti diretti. 0 = nessun filtro.
        max_risultati: Numero massimo sentenze per tipo di ricerca (default 5)
    """
    result = await _giurisprudenza_articolo_impl(
        riferimento=riferimento, archivio=archivio,
        anno_da=anno_da, anno_a=anno_a, max_risultati=max_risultati,
    )
    return result.to_str() if isinstance(result, SearchResult) else result

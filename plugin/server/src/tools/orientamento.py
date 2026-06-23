"""MCP tools per la MAPPATURA DESCRITTIVA degli orientamenti giurisprudenziali.

LIMITE NORMATIVO (L. 132/2025): è vietata la "giustizia predittiva" — questi tool
NON prevedono esiti, overruling o probabilità di accoglimento. Producono solo una
MAPPA DESCRITTIVA di ciò che gli archivi della Cassazione contengono: intervento
delle Sezioni Unite, distribuzione per sezione, andamento temporale e il NUMERO di
decisioni che SEGNALANO nel proprio testo un contrasto/difformità oppure un
orientamento consolidato/conforme. Questi conteggi sono un SEGNALE TESTUALE, mai una
classificazione di merito delle decisioni come "conformi" o "difformi".

Orizzonte archivio Italgiure: ~2020 in poi.
"""

import re

from src.server import mcp
from src.lib._result import SearchResult
from src.lib.brocardi.client import fetch_brocardi, parse_massime_references
from src.lib.visualex import resolve_atto
from src.lib.italgiure.client import (
    CONFLICT_SIGNALS,
    CONFORMITY_SIGNALS,
    SolrSession,
    build_norma_variants,
    build_orientamento_params,
    format_estremi,
    format_summary,
    get_kind_filter,
    solr_query,
)

_DISCLAIMER = (
    "_Mappa descrittiva degli orientamenti, NON una previsione di overruling "
    "(art. 13, L. 132/2025)._"
)
_ARCHIVE_NOTE = "_Orizzonte archivio Italgiure: decisioni dal ~2020 in poi._"

_SEZIONI_LABELS = {
    "1": "Sezione I", "2": "Sezione II", "3": "Sezione III", "4": "Sezione IV",
    "5": "Sezione V", "6": "Sezione VI", "7": "Sezione VII",
    "L": "Sezione Lavoro", "T": "Sezione Tributaria",
    "U": "Sezioni Unite", "SU": "Sezioni Unite",
}

# Default per-section sample of LATER decisions surfaced in the cluster output.
_PER_SEZIONE_SAMPLE = 3
# Sezioni Unite docs fetched for the dedicated SS.UU. block.
_SS_UU_ROWS = 5


def _pairs(raw: list) -> list[tuple[str, int]]:
    """Convert a Solr facet_fields flat list [name, count, ...] into pairs."""
    return list(zip(raw[0::2], raw[1::2]))


def _signal_split(facet_queries: dict) -> tuple[list[tuple[str, int]], list[tuple[str, int]]]:
    """Map facet.query counts back to (conflict_signals, conformity_signals).

    facet_queries keys are the literal Solr facet.query strings (ocr:"phrase").
    Returns two ordered lists of (phrase, count).
    """
    conflict = []
    for phrase in CONFLICT_SIGNALS:
        key = f'ocr:"{phrase}"'
        conflict.append((phrase, int(facet_queries.get(key, 0))))
    conformity = []
    for phrase in CONFORMITY_SIGNALS:
        key = f'ocr:"{phrase}"'
        conformity.append((phrase, int(facet_queries.get(key, 0))))
    return conflict, conformity


def _format_signal_block(facet_queries: dict) -> list[str]:
    """Render the self-flag signal split as a TEXTUAL-signal section (never holdings)."""
    conflict, conformity = _signal_split(facet_queries)
    total_conflict = sum(c for _, c in conflict)
    total_conformity = sum(c for _, c in conformity)
    lines = ["## Segnali testuali nelle decisioni"]
    lines.append(
        "> I conteggi sotto indicano quante decisioni **usano nel testo** le seguenti "
        "espressioni. Sono un SEGNALE TESTUALE di come la decisione si autoqualifica, "
        "NON una classificazione di merito dell'esito."
    )
    lines.append("")
    lines.append(f"**Decisioni che SEGNALANO un contrasto/difformità** ({total_conflict}):")
    for phrase, count in conflict:
        lines.append(f"- _«{phrase}»_: {count}")
    lines.append("")
    lines.append(f"**Decisioni che SEGNALANO un orientamento consolidato/conforme** ({total_conformity}):")
    for phrase, count in conformity:
        lines.append(f"- _«{phrase}»_: {count}")
    return lines


def _format_anno_trend(facet_fields: dict) -> list[str]:
    """Render the temporal (anno) distribution."""
    anno_pairs = _pairs(facet_fields.get("anno", []))
    if not anno_pairs:
        return []
    # Solr returns anno facet sorted by count; present chronologically descending.
    anno_pairs = sorted(anno_pairs, key=lambda p: str(p[0]), reverse=True)
    lines = ["## Andamento temporale"]
    formatted = [f"{anno} ({count})" for anno, count in anno_pairs]
    lines.append("- " + ", ".join(formatted))
    return lines


async def _fetch_ss_uu(
    q: str,
    archivio: str,
    anno_da: int,
    campo: str,
    session: SolrSession,
    field_query: bool = False,
) -> tuple[int, list[dict]]:
    """Fetch the dedicated Sezioni Unite (szdec:U) block in ONE query."""
    params = build_orientamento_params(
        q, archivio=archivio, anno_da=anno_da, sezione="U", rows=_SS_UU_ROWS,
        campo=campo, field_query=field_query,
    )
    data = await solr_query(params, session=session)
    num = data.get("response", {}).get("numFound", 0)
    docs = data.get("response", {}).get("docs", [])
    return num, docs


def _doc_key(doc: dict) -> str:
    """Stable dedup key for a decision document."""
    doc_id = doc.get("id")
    if isinstance(doc_id, list):
        doc_id = doc_id[0] if doc_id else ""
    if doc_id:
        return str(doc_id)
    num = doc.get("numdec")
    anno = doc.get("anno")
    num = num[0] if isinstance(num, list) else num
    anno = anno[0] if isinstance(anno, list) else anno
    return f"{num}/{anno}"


def _cluster_by_sezione(docs: list[dict]) -> dict[str, list[dict]]:
    """Group later decisions by szdec code, deduplicated by document id."""
    clusters: dict[str, list[dict]] = {}
    seen: set[str] = set()
    for doc in docs:
        key = _doc_key(doc)
        if key in seen:
            continue
        seen.add(key)
        sez = doc.get("szdec")
        sez = sez[0] if isinstance(sez, list) else (sez or "?")
        clusters.setdefault(str(sez), []).append(doc)
    return clusters


def _format_sezione_clusters(docs: list[dict], szdec_raw: list | None = None) -> list[str]:
    """Render per-sezione clusters of LATER decisions (SS.UU. excluded — own block).

    Per-section counts come from the szdec facet (true distribution), while the
    sample docs per section are illustrative examples drawn from the limited
    document sample.
    """
    sez_counts = {
        sez: count
        for sez, count in _pairs(szdec_raw or [])
        if sez not in ("U", "SU")
    }
    clusters = _cluster_by_sezione(docs)
    sample_clusters = {s: d for s, d in clusters.items() if s not in ("U", "SU")}
    lines = ["## Cluster per sezione (decisioni successive)"]
    # The full section set is the union of facet sections and sampled sections.
    all_sez = set(sez_counts) | set(sample_clusters)
    if not all_sez:
        lines.append("_Solo decisioni delle Sezioni Unite (vedi blocco dedicato)._")
        return lines
    # Order sezioni by facet count desc (fall back to sample size), keeping SS.UU. out.
    ordered = sorted(
        all_sez,
        key=lambda s: sez_counts.get(s, len(sample_clusters.get(s, []))),
        reverse=True,
    )
    for sez in ordered:
        sample = sample_clusters.get(sez, [])
        count = sez_counts.get(sez, len(sample))
        label = _SEZIONI_LABELS.get(sez, f"Sezione {sez}")
        lines.append(f"### {label} ({count})")
        for doc in sample[:_PER_SEZIONE_SAMPLE]:
            lines.append(format_summary(doc))
            lines.append("")
    return lines


def _format_ss_uu_block(num: int, docs: list[dict]) -> list[str]:
    """Render the Sezioni Unite (szdec:U) block at the top of the map."""
    lines = ["## Intervento delle Sezioni Unite (szdec:U)"]
    if not docs:
        lines.append(
            "_Nessuna pronuncia delle Sezioni Unite trovata negli archivi per questo tema._"
        )
        return lines
    seen: set[str] = set()
    deduped: list[dict] = []
    for doc in docs:
        key = _doc_key(doc)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(doc)
    lines.append(f"**{num} pronunce delle Sezioni Unite** (mostro {min(len(deduped), _SS_UU_ROWS)}):")
    lines.append("")
    for doc in deduped:
        lines.append(f"- {format_estremi(doc)}")
    return lines


def _assemble_map(
    titolo: str,
    base_q: str,
    num_found: int,
    facet_counts: dict,
    docs: list[dict],
    ss_uu_num: int,
    ss_uu_docs: list[dict],
) -> str:
    """Assemble the descriptive orientation map in the mandated order."""
    facet_fields = facet_counts.get("facet_fields", {})
    facet_queries = facet_counts.get("facet_queries", {})

    parts: list[str] = [f"# {titolo}", ""]
    parts.append(f"**{num_found} decisioni** negli archivi della Cassazione per: _{base_q}_")
    parts.append("")
    # (1) SS.UU. block
    parts.extend(_format_ss_uu_block(ss_uu_num, ss_uu_docs))
    parts.append("")
    # (2) per-sezione clusters of LATER decisions
    parts.extend(_format_sezione_clusters(docs, facet_fields.get("szdec", [])))
    parts.append("")
    # (3) anno trend
    parts.extend(_format_anno_trend(facet_fields))
    parts.append("")
    # (4) self-flag signal split (TEXTUAL signal only)
    parts.extend(_format_signal_block(facet_queries))
    parts.append("")
    # Mandatory footer
    parts.append("---")
    parts.append(_ARCHIVE_NOTE)
    parts.append(_DISCLAIMER)
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Impl functions (testable without MCP context)
# ---------------------------------------------------------------------------

async def _orientamento_su_norma_impl(
    riferimento: str,
    archivio: str = "tutti",
    anno_da: int = 0,
    max_risultati: int = 10,
) -> SearchResult:
    """Descriptive orientation map for a specific article reference.

    Builds Solr norma variants then issues ONE faceted query for the LATER
    decisions, plus ONE more for the dedicated SS.UU. block.
    """
    max_risultati = max(1, min(max_risultati, 50))
    norma_q = build_norma_variants(riferimento)
    try:
        async with SolrSession() as session:
            params = build_orientamento_params(
                norma_q, archivio=archivio, anno_da=anno_da, rows=max_risultati,
                field_query=True,
            )
            data = await solr_query(params, session=session)
            ss_uu_num, ss_uu_docs = await _fetch_ss_uu(
                norma_q, archivio, anno_da, "tutto", session, field_query=True,
            )
    except Exception as exc:
        return SearchResult(
            success=False, source="italgiure",
            error_type="source_down", error_message=str(exc),
        )

    num_found = data.get("response", {}).get("numFound", 0)
    facet_counts = data.get("facet_counts", {})
    docs = data.get("response", {}).get("docs", [])

    if num_found == 0 and ss_uu_num == 0:
        return SearchResult(
            success=False, source="italgiure", error_type="no_results",
            results_text=(
                f"Nessuna decisione trovata per il riferimento: {riferimento}.\n\n"
                f"{_ARCHIVE_NOTE}\n{_DISCLAIMER}"
            ),
        )

    text = _assemble_map(
        titolo=f"Orientamento giurisprudenziale — {riferimento}",
        base_q=riferimento,
        num_found=num_found,
        facet_counts=facet_counts,
        docs=docs,
        ss_uu_num=ss_uu_num,
        ss_uu_docs=ss_uu_docs,
    )
    return SearchResult(
        success=True, source="italgiure", num_found=num_found, results_text=text,
    )


async def _orientamento_su_principio_impl(
    principio: str,
    archivio: str = "tutti",
    anno_da: int = 0,
    sezione: str = "",
    max_risultati: int = 10,
) -> SearchResult:
    """Descriptive orientation map for a legal principle (free-text)."""
    max_risultati = max(1, min(max_risultati, 50))
    # Reuse italgiure query normalization for principle text.
    from src.tools.italgiure import _normalize_query

    q = _normalize_query(principio)
    try:
        async with SolrSession() as session:
            params = build_orientamento_params(
                q, archivio=archivio, anno_da=anno_da, sezione=sezione or "",
                rows=max_risultati, campo="tutto",
            )
            data = await solr_query(params, session=session)
            ss_uu_num, ss_uu_docs = await _fetch_ss_uu(
                q, archivio, anno_da, "tutto", session,
            )
    except Exception as exc:
        return SearchResult(
            success=False, source="italgiure",
            error_type="source_down", error_message=str(exc),
        )

    num_found = data.get("response", {}).get("numFound", 0)
    facet_counts = data.get("facet_counts", {})
    docs = data.get("response", {}).get("docs", [])

    if num_found == 0 and ss_uu_num == 0:
        return SearchResult(
            success=False, source="italgiure", error_type="no_results",
            results_text=(
                f"Nessuna decisione trovata per il principio: {principio}.\n\n"
                f"{_ARCHIVE_NOTE}\n{_DISCLAIMER}"
            ),
        )

    text = _assemble_map(
        titolo=f"Orientamento giurisprudenziale — {principio}",
        base_q=principio,
        num_found=num_found,
        facet_counts=facet_counts,
        docs=docs,
        ss_uu_num=ss_uu_num,
        ss_uu_docs=ss_uu_docs,
    )
    return SearchResult(
        success=True, source="italgiure", num_found=num_found, results_text=text,
    )


def _parse_articolo_riferimento(riferimento: str) -> tuple[str, str]:
    """Extract (articolo, atto) from a legal reference like 'art. 2043 c.c.'."""
    m = re.match(
        r"(?:articol[oi]|art)\.?\s*(\d+(?:[-/.]\w+)*)\s+(.+)",
        riferimento.strip(),
        re.IGNORECASE,
    )
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return "", riferimento.strip()


async def _mappa_orientamento_impl(
    riferimento: str,
    archivio: str = "tutti",
    anno_da: int = 0,
) -> SearchResult:
    """Orchestrator: Brocardi anchor → SS.UU. references → orientation map.

    1. fetch_brocardi for the article (anchor of the established case law)
    2. parse_massime_references → Cassazione decisions cited as massime
    3. build the descriptive orientation map via _orientamento_su_norma_impl
    4. surface any SS.UU. (szdec:U) anchor references at the top
    """
    articolo, atto_str = _parse_articolo_riferimento(riferimento)

    # --- Brocardi anchor (best-effort; map still produced if it fails) ---
    anchor_refs: list[dict] = []
    n_massime = 0
    if articolo and atto_str:
        act_info = resolve_atto(atto_str)
        if act_info:
            try:
                brocardi_result = await fetch_brocardi(
                    act_info["tipo_atto"],
                    articolo,
                    act_info.get("numero_atto", ""),
                )
                if brocardi_result and not brocardi_result.error and brocardi_result.massime:
                    n_massime = len(brocardi_result.massime)
                    anchor_refs = parse_massime_references(brocardi_result.massime)
            except Exception:
                anchor_refs = []

    # --- Descriptive orientation map (core) ---
    base = await _orientamento_su_norma_impl(
        riferimento, archivio=archivio, anno_da=anno_da,
    )

    parts: list[str] = []
    if anchor_refs:
        parts.append("## Ancoraggio Brocardi (massime consolidate)")
        parts.append(
            f"_Brocardi riporta {n_massime} massime per {riferimento}; "
            f"{len(anchor_refs)} riferimenti Cassazione estratti come ancoraggio:_"
        )
        for ref in anchor_refs[:5]:
            autorita = ref.get("autorita") or "Cass."
            parts.append(f"- {autorita} n. {ref['numero']}/{ref['anno']}")
        parts.append("")

    if not base.success:
        # Still attach the Brocardi anchor info if any, but propagate no_results.
        if parts:
            anchor_block = "\n".join(parts)
            base_text = base.results_text or ""
            base.results_text = (
                f"{anchor_block}\n{base_text}" if base_text else anchor_block
            )
        return base

    if parts:
        # Inject the anchor block right after the title line of the base map.
        base_text = base.results_text or ""
        anchor_block = "\n".join(parts)
        nl = base_text.find("\n\n")
        if nl != -1:
            merged = base_text[: nl + 2] + anchor_block + "\n" + base_text[nl + 2 :]
        else:
            merged = anchor_block + "\n" + base_text
        return SearchResult(
            success=True, source="italgiure",
            num_found=base.num_found, results_text=merged,
        )

    return base


# ---------------------------------------------------------------------------
# MCP tool wrappers
# ---------------------------------------------------------------------------

@mcp.tool(tags={"giurisprudenza"})
async def orientamento_su_norma(
    riferimento: str,
    archivio: str = "tutti",
    anno_da: int = 0,
    max_risultati: int = 10,
) -> str:
    """Mappa DESCRITTIVA degli orientamenti della Cassazione su un articolo di legge.

    Produce una mappa (NON una previsione): intervento delle Sezioni Unite,
    cluster per sezione delle decisioni successive, andamento temporale e il
    numero di decisioni che SEGNALANO nel testo un contrasto/difformità oppure
    un orientamento consolidato/conforme. I conteggi dei segnali sono un SEGNALE
    TESTUALE, non una classificazione di merito.

    LIMITE L. 132/2025: vietata la giustizia predittiva — nessuna stima di esito
    o probabilità di overruling.

    Usa una sola query Solr faceted per i dati principali + una per il blocco SS.UU.

    Args:
        riferimento: Riferimento normativo breve (es. "art. 2043 c.c.", "art. 13 GDPR")
        archivio: "civile", "penale", o "tutti" (default)
        anno_da: Anno minimo delle decisioni successive (0 = nessun filtro; archivio ~2020+)
        max_risultati: Numero massimo di decisioni successive analizzate (default 10, max 50)
    """
    result = await _orientamento_su_norma_impl(
        riferimento, archivio=archivio, anno_da=anno_da, max_risultati=max_risultati,
    )
    return result.to_str() if isinstance(result, SearchResult) else result


@mcp.tool(tags={"giurisprudenza"})
async def orientamento_su_principio(
    principio: str,
    archivio: str = "tutti",
    anno_da: int = 0,
    sezione: str = "",
    max_risultati: int = 10,
) -> str:
    """Mappa DESCRITTIVA degli orientamenti della Cassazione su un principio di diritto.

    Come `orientamento_su_norma` ma a partire da un principio in linguaggio libero
    (es. "buona fede oggettiva nel recesso contrattuale"). Restituisce intervento
    SS.UU., cluster per sezione, andamento temporale e segnali testuali di
    contrasto/conformità. NON è una previsione (L. 132/2025).

    Args:
        principio: Principio o massima in linguaggio libero (2-6 termini chiave)
        archivio: "civile", "penale", o "tutti" (default)
        anno_da: Anno minimo (0 = nessun filtro; archivio ~2020+)
        sezione: Filtro sezione (1-7, L=lavoro, T=tributaria, U=sezioni unite). Default: tutte
        max_risultati: Numero massimo di decisioni successive (default 10, max 50)
    """
    result = await _orientamento_su_principio_impl(
        principio, archivio=archivio, anno_da=anno_da,
        sezione=sezione, max_risultati=max_risultati,
    )
    return result.to_str() if isinstance(result, SearchResult) else result


@mcp.tool(tags={"giurisprudenza"})
async def mappa_orientamento(
    riferimento: str,
    archivio: str = "tutti",
    anno_da: int = 0,
) -> str:
    """Mappa DESCRITTIVA completa: ancoraggio Brocardi + orientamenti Cassazione su un articolo.

    Workflow orchestrato:
    1. recupera le massime consolidate da Brocardi per l'articolo (ancoraggio)
    2. estrae i riferimenti Cassazione citati come massime
    3. costruisce la mappa descrittiva degli orientamenti (intervento SS.UU.,
       cluster per sezione, andamento temporale, segnali testuali di
       contrasto/conformità)

    NON è una previsione di overruling né una giustizia predittiva (L. 132/2025).

    Args:
        riferimento: Riferimento normativo (es. "art. 2043 c.c.", "art. 2087 c.c.")
        archivio: "civile", "penale", o "tutti" (default)
        anno_da: Anno minimo delle decisioni successive (0 = nessun filtro; archivio ~2020+)
    """
    result = await _mappa_orientamento_impl(
        riferimento, archivio=archivio, anno_da=anno_da,
    )
    return result.to_str() if isinstance(result, SearchResult) else result

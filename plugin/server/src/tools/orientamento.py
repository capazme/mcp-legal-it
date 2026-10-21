"""MCP tools per la MAPPATURA DESCRITTIVA degli orientamenti giurisprudenziali.

RISERVA AL MAGISTRATO (art. 15, co. 1, L. 132/2025): quando l'intelligenza artificiale è
impiegata nell'attività giudiziaria, ogni decisione sull'interpretazione e applicazione della
legge, sulla valutazione dei fatti e delle prove e sull'adozione dei provvedimenti è sempre
riservata al magistrato. La norma non vieta la "giustizia predittiva" e non disciplina gli
strumenti usati dagli avvocati (per quelli rileva l'art. 13); per scelta di progetto questi tool
NON prevedono esiti, overruling o probabilità di accoglimento: producono solo una
MAPPA DESCRITTIVA di ciò che gli archivi della Cassazione contengono: intervento
delle Sezioni Unite, distribuzione per sezione, andamento temporale e il NUMERO di
decisioni DISTINTE che SEGNALANO nel proprio testo un contrasto/difformità oppure un
orientamento consolidato/conforme. Questi conteggi sono un SEGNALE TESTUALE, mai una
classificazione di merito delle decisioni come "conformi" o "difformi".

Orizzonte archivio Italgiure: finestra mobile di circa cinque anni (a settembre 2026 dal
27/09/2021), non "dal 2020".
"""

import re

from src.server import mcp
from src.lib._result import SearchResult
from src.lib.brocardi.client import fetch_brocardi, parse_massime_references
from src.lib.visualex import resolve_atto
from src.lib.italgiure.client import (
    ARCHIVE_START_YEAR,
    CONFLICT_SIGNALS,
    CONFORMITY_SIGNALS,
    SolrSession,
    build_norma_variants,
    build_orientamento_params,
    resolve_sezione,
    format_estremi,
    format_summary,
    get_kind_filter,
    group_signal_facet_query,
    solr_query,
)

_DISCLAIMER = (
    "_Mappa descrittiva degli orientamenti, non una previsione di esito né di overruling: "
    "nell'attività giudiziaria le decisioni restano riservate al magistrato (art. 15, L. 132/2025)._"
)
_ARCHIVE_NOTE = (
    "_Orizzonte archivio Italgiure: finestra mobile di circa gli ultimi cinque anni "
    "(a settembre 2026 dal 27/09/2021); le decisioni anteriori non sono consultabili._"
)

# Free-text principle: with the default edismax mm ("2<75% 5<60%") six terms need only three,
# so unrelated decisions sharing three words (e.g. "schema", "nullità", "parziale") flood the
# totals and the Sezioni Unite block. "3<90%": up to three terms must all be present, above
# three at least 90% of them (5 of 6).
_PRINCIPIO_MM = "3<90%"
_PRINCIPIO_MM_NOTE = (
    "_I totali contano le decisioni che contengono almeno il 90% dei termini del principio "
    "(tutti, fino a tre termini)._"
)
_PRINCIPIO_MM_RELAXED_NOTE = (
    "_Nessuna decisione contiene almeno il 90% dei termini: criteri allargati (almeno il 60-75% "
    "dei termini), i totali sono meno selettivi._"
)

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


def _distinct_total(facet_queries: dict, phrases: list[str], per_phrase: list[tuple[str, int]]) -> int:
    """Number of DISTINCT decisions using any phrase of the group.

    Read from the group facet.query (one OR query, each decision counted once). A response
    without it (older mocks) falls back to the sum of the per-phrase counts.
    """
    key = group_signal_facet_query(phrases)
    if key in facet_queries:
        return int(facet_queries[key])
    return sum(c for _, c in per_phrase)


def _format_signal_block(facet_queries: dict) -> list[str]:
    """Render the self-flag signal split as a TEXTUAL-signal section (never holdings)."""
    conflict, conformity = _signal_split(facet_queries)
    total_conflict = _distinct_total(facet_queries, CONFLICT_SIGNALS, conflict)
    total_conformity = _distinct_total(facet_queries, CONFORMITY_SIGNALS, conformity)
    lines = ["## Segnali testuali nelle decisioni"]
    lines.append(
        "> I conteggi sotto indicano quante decisioni **usano nel testo** le seguenti "
        "espressioni. Sono un SEGNALE TESTUALE di come la decisione si autoqualifica, "
        "NON una classificazione di merito dell'esito. Il totale di ogni gruppo conta "
        "decisioni distinte: una decisione che usa più espressioni compare in ciascuna riga "
        "ma è contata una sola volta nel totale."
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
    sort: str = "pd desc",
    mm: str | None = None,
) -> tuple[int, list[dict]]:
    """Fetch the dedicated Sezioni Unite (szdec:U) block in ONE query.

    *sort* "score desc" (free-text principle only) lists the most pertinent decisions instead
    of the most recent ones that merely share a few words with the query.
    """
    params = build_orientamento_params(
        q, archivio=archivio, anno_da=anno_da, sezione="U", rows=_SS_UU_ROWS,
        campo=campo, field_query=field_query, sort=sort, mm=mm,
    )
    data = await solr_query(params, session=session)
    num = data.get("response", {}).get("numFound", 0)
    docs = data.get("response", {}).get("docs", [])
    return num, docs


def _first_str(val) -> str:
    if isinstance(val, list):
        return str(val[0]) if val else ""
    return str(val) if val else ""


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


def _format_ss_uu_block(num: int, docs: list[dict], ordine: str = "le più recenti") -> list[str]:
    """Render the Sezioni Unite (szdec:U) block at the top of the map.

    Each line carries the materia, so an unrelated decision that shares a few words with the
    query is recognisable at a glance. *ordine* says how the shown decisions were picked.
    """
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
    lines.append(
        f"**{num} pronunce delle Sezioni Unite** (mostro {min(len(deduped), _SS_UU_ROWS)}, {ordine}):"
    )
    lines.append("")
    for doc in deduped:
        materia = _first_str(doc.get("materia"))
        suffix = f" — {materia}" if materia else ""
        lines.append(f"- {format_estremi(doc)}{suffix}")
    return lines


def _assemble_map(
    titolo: str,
    base_q: str,
    num_found: int,
    facet_counts: dict,
    docs: list[dict],
    ss_uu_num: int,
    ss_uu_docs: list[dict],
    extra_notes: list[str] | None = None,
    ss_uu_ordine: str = "le più recenti",
) -> str:
    """Assemble the descriptive orientation map in the mandated order."""
    facet_fields = facet_counts.get("facet_fields", {})
    facet_queries = facet_counts.get("facet_queries", {})

    parts: list[str] = [f"# {titolo}", ""]
    parts.append(f"**{num_found} decisioni** negli archivi della Cassazione per: _{base_q}_")
    for note in extra_notes or []:
        parts.append(note)
    parts.append("")
    # (1) SS.UU. block
    parts.extend(_format_ss_uu_block(ss_uu_num, ss_uu_docs, ss_uu_ordine))
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

    try:
        sezione, archivio = resolve_sezione(sezione, archivio)
    except ValueError as exc:
        return SearchResult(success=False, source="italgiure", error_type="bad_input", results_text=str(exc))

    q = _normalize_query(principio)

    async def _run(mm: str | None):
        async with SolrSession() as session:
            params = build_orientamento_params(
                q, archivio=archivio, anno_da=anno_da, sezione=sezione or "",
                rows=max_risultati, campo="tutto", mm=mm,
            )
            data = await solr_query(params, session=session)
            # The SS.UU. block lists the MOST PERTINENT decisions (score), not the most recent
            # ones sharing a few words with the principle.
            ss = await _fetch_ss_uu(q, archivio, anno_da, "tutto", session, sort="score desc", mm=mm)
        return data, ss

    relaxed = False
    try:
        data, (ss_uu_num, ss_uu_docs) = await _run(_PRINCIPIO_MM)
        if data.get("response", {}).get("numFound", 0) == 0 and ss_uu_num == 0:
            # Strict matching found nothing: retry once with the default (looser) matching.
            relaxed = True
            data, (ss_uu_num, ss_uu_docs) = await _run(None)
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
        extra_notes=[_PRINCIPIO_MM_RELAXED_NOTE if relaxed else _PRINCIPIO_MM_NOTE],
        ss_uu_ordine="per pertinenza al principio",
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

    1. fetch_brocardi for the article (anchor of the case law Brocardi reports)
    2. parse_massime_references → Cassazione decisions cited as massime
    3. build the descriptive orientation map via _orientamento_su_norma_impl
    4. surface any SS.UU. (szdec:U) anchor references at the top

    The anchor never disappears silently: when Brocardi is unreachable, has no massime or the
    act is not recognised, the map says so.
    """
    articolo, atto_str = _parse_articolo_riferimento(riferimento)

    # --- Brocardi anchor (best-effort; map still produced if it fails) ---
    anchor_refs: list[dict] = []
    n_massime = 0
    anchor_status = ""  # human-readable reason when there is no anchor
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
                if brocardi_result and not brocardi_result.error and brocardi_result.massime:
                    n_massime = len(brocardi_result.massime)
                    anchor_refs = parse_massime_references(brocardi_result.massime)
                    if not anchor_refs:
                        anchor_status = (
                            f"Brocardi riporta {n_massime} massime per {riferimento}, ma nessuna "
                            "cita una decisione della Cassazione con numero e anno"
                        )
                elif brocardi_result and not brocardi_result.error:
                    anchor_status = f"Brocardi non riporta massime per {riferimento}"
                else:
                    anchor_status = "Brocardi non ha restituito la pagina dell'articolo"
            except Exception:
                anchor_refs = []
                anchor_status = "Brocardi non raggiungibile"
        else:
            anchor_status = "atto non riconosciuto: nessun ancoraggio Brocardi"
    else:
        anchor_status = "riferimento senza articolo e atto: nessun ancoraggio Brocardi"

    # --- Descriptive orientation map (core) ---
    base = await _orientamento_su_norma_impl(
        riferimento, archivio=archivio, anno_da=anno_da,
    )

    parts: list[str] = []
    if anchor_refs:
        parts.append("## Ancoraggio Brocardi")
        parts.append(
            f"_Brocardi riporta {n_massime} massime per {riferimento}; "
            f"{len(anchor_refs)} riferimenti Cassazione estratti come ancoraggio:_"
        )
        for ref in anchor_refs[:5]:
            autorita = ref.get("autorita") or "Cass."
            parts.append(f"- {autorita} n. {ref['numero']}/{ref['anno']}")
        prima = sum(1 for r in anchor_refs if int(r["anno"]) < ARCHIVE_START_YEAR)
        if prima:
            parts.append(
                f"_{prima} su {len(anchor_refs)} riferimenti precedono il {ARCHIVE_START_YEAR}: sono "
                "fuori dalla finestra dell'archivio Italgiure e non si leggono con leggi_sentenza. "
                "Le massime di Brocardi non misurano il consolidamento dell'orientamento._"
            )
        parts.append("")
    elif anchor_status:
        parts.append("## Ancoraggio Brocardi")
        parts.append(f"_{anchor_status}: la mappa che segue è costruita solo sugli archivi Italgiure._")
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
    numero di decisioni DISTINTE che SEGNALANO nel testo un contrasto/difformità
    oppure un orientamento consolidato/conforme. I conteggi dei segnali sono un
    SEGNALE TESTUALE, non una classificazione di merito.

    Art. 15, co. 1, L. 132/2025: nell'attività giudiziaria l'IA non sostituisce il
    magistrato, cui è sempre riservata ogni decisione su interpretazione e applicazione
    della legge, fatti e prove. Per scelta di progetto il tool produce solo una mappa
    descrittiva, senza stime di esito o probabilità di overruling.

    Il riferimento deve indicare codice o atto: per gli atti ("art. 13 GDPR") sono contate le
    decisioni che citano l'articolo insieme agli estremi dell'atto, non ogni "art. 13".
    L'archivio Italgiure è una finestra mobile di circa cinque anni (a settembre 2026 dal
    27/09/2021).

    Usa una sola query Solr faceted per i dati principali + una per il blocco SS.UU.

    Args:
        riferimento: Riferimento normativo breve (es. "art. 2043 c.c.", "art. 13 GDPR")
        archivio: "civile", "penale", o "tutti" (default)
        anno_da: Anno minimo delle decisioni successive (0 = nessun filtro; l'archivio parte da settembre 2021)
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
    SS.UU. (le più pertinenti al principio, con la materia), cluster per sezione, andamento
    temporale e segnali testuali di contrasto/conformità. È una mappa descrittiva, non una
    previsione di esito: nell'attività giudiziaria le decisioni restano riservate al
    magistrato (art. 15 L. 132/2025). I totali contano le decisioni con almeno il 90% dei
    termini del principio (tutti, fino a tre termini).

    Args:
        principio: Principio o massima in linguaggio libero (2-6 termini chiave)
        archivio: "civile", "penale", o "tutti" (default)
        anno_da: Anno minimo (0 = nessun filtro; l'archivio parte da settembre 2021)
        sezione: Filtro sezione (1-7, L=lavoro, U o SU=sezioni unite, F=feriale, T=tributaria=sezione 5 civile). Default: tutte
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
    1. recupera le massime riportate da Brocardi per l'articolo (ancoraggio; le massime di
       Brocardi non misurano il consolidamento; se Brocardi non risponde o non ha massime
       la mappa lo dichiara)
    2. estrae i riferimenti Cassazione citati come massime e segnala quanti sono anteriori
       alla finestra dell'archivio (non leggibili con leggi_sentenza)
    3. costruisce la mappa descrittiva degli orientamenti (intervento SS.UU.,
       cluster per sezione, andamento temporale, segnali testuali di
       contrasto/conformità)

    È una mappa descrittiva, non una previsione di esito né di overruling: nell'attività
    giudiziaria le decisioni restano riservate al magistrato (art. 15 L. 132/2025).

    Args:
        riferimento: Riferimento normativo (es. "art. 2043 c.c.", "art. 2087 c.c.")
        archivio: "civile", "penale", o "tutti" (default)
        anno_da: Anno minimo delle decisioni successive (0 = nessun filtro; l'archivio parte da settembre 2021)
    """
    result = await _mappa_orientamento_impl(
        riferimento, archivio=archivio, anno_da=anno_da,
    )
    return result.to_str() if isinstance(result, SearchResult) else result

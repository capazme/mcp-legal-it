"""Unified cross-source jurisprudence search across Italgiure, CeRDEF, Giustizia Amministrativa and CGUE.

Launches parallel searches on all (or selected) sources and merges results with source provenance.
"""

import asyncio
import re

from src.server import mcp
from src.lib._result import SearchResult

# The Giustizia Amministrativa portal has no server-side year filter: the year is applied to the
# rows we get back, ordered newest first. With a year filter we ask for more rows, then truncate.
_GA_YEAR_ROWS = 50


def _get_fonti() -> dict:
    from src.tools.italgiure import _cerca_giurisprudenza_impl
    from src.tools.cerdef import _cerca_giurisprudenza_tributaria_impl
    from src.tools.giustizia_amm import _cerca_giurisprudenza_amministrativa_impl
    from src.tools.cgue import _cerca_giurisprudenza_cgue_impl
    return {
        "cassazione": ("Cassazione (Italgiure)", _cerca_giurisprudenza_impl),
        "tributaria": ("Tributaria (CeRDEF)", _cerca_giurisprudenza_tributaria_impl),
        "amministrativa": ("Amministrativa (TAR/CdS)", _cerca_giurisprudenza_amministrativa_impl),
        "ue": ("CGUE", _cerca_giurisprudenza_cgue_impl),
    }


def _safe_year(v) -> int:
    try:
        return int(v) if str(v).strip() else 0
    except ValueError:
        return 0


async def _cerca_amministrativa(
    fn, query: str, anno_da: int, anno_a: int, tipo: str, max_risultati: int,
) -> SearchResult:
    """Giustizia Amministrativa with a year RANGE.

    The source tool takes one exact year (and drops the rest): passing `anno=anno_da` reduced
    2025-2026 to 2025 and lost every 2026 decision. Without years the source tool is used as is;
    with years the portal is asked for more rows and the range is applied here.
    """
    if not (anno_da or anno_a):
        return await fn(query, tipo=tipo, max_risultati=max_risultati)

    from src.lib.giustizia_amm.client import format_result, search_provvedimenti
    from src.tools.giustizia_amm import _NO_YEAR_FILTER_NOTE

    try:
        docs = await search_provvedimenti(query=query, tipo=tipo, rows=_GA_YEAR_ROWS)
    except Exception as exc:
        return SearchResult(
            success=False, source="giustizia_amm", error_type="source_down", error_message=str(exc),
        )

    def _in_range(doc) -> bool:
        anno = str(getattr(doc, "anno", "") or "")
        if not anno.isdigit():
            return False
        return (not anno_da or int(anno) >= anno_da) and (not anno_a or int(anno) <= anno_a)

    docs = [d for d in docs if _in_range(d)][:max_risultati]
    if not docs:
        return SearchResult(
            success=False, source="giustizia_amm", error_type="no_results",
            results_text=f"Nessun provvedimento amministrativo trovato per: _{query}_{_NO_YEAR_FILTER_NOTE}",
        )
    lines = [f"**Trovati {len(docs)} provvedimenti TAR/CdS per**: _{query}_\n"]
    for doc in docs:
        lines.append(format_result(doc))
        lines.append("")
    lines.append(_NO_YEAR_FILTER_NOTE)
    return SearchResult(
        success=True, source="giustizia_amm", num_found=len(docs), results_text="\n".join(lines),
    )


async def _cerca_ue(
    fn, query: str, anno_da: str, anno_a: str, tipo: str, max_risultati: int,
) -> SearchResult:
    """CGUE: the query is ONE title substring (commas mean OR), so a natural phrase of several
    words finds nothing although CELLAR titles contain each word. When the whole phrase gives
    zero results the words are searched in AND in the title (the answer says so)."""
    outcome = await fn(
        query, anno_da=anno_da, anno_a=anno_a, tipo_documento=tipo, max_risultati=max_risultati,
    )
    if not (
        isinstance(outcome, SearchResult)
        and not outcome.success
        and outcome.error_type == "no_results"
        and "," not in query
    ):
        return outcome

    from src.lib.cgue.client import format_result, search_giurisprudenza
    from src.tools.italgiure import _IT_STOPWORDS

    words = [
        w for w in (re.sub(r'["\\]', "", t) for t in query.split())
        if len(w) > 2 and w.lower() not in _IT_STOPWORDS
    ]
    if len(words) < 2:
        return outcome
    try:
        docs = await search_giurisprudenza(
            # no OR keywords: every word is a required term (AND) of the same title
            keywords=[], required_terms=words, doc_type=tipo, year_from=anno_da, year_to=anno_a,
            limit=max(1, min(max_risultati, 50)),
        )
    except Exception:
        return outcome  # keep the original "no results" answer
    if not docs:
        return outcome
    lines = [
        f"**Trovate {len(docs)} sentenze CGUE** (nessun titolo contiene la frase intera: "
        f"cercate le parole {', '.join(words)} tutte insieme nel titolo)\n"
    ]
    for doc in docs:
        lines.append(format_result(doc))
        lines.append("")
    return SearchResult(
        success=True, source="cgue", num_found=len({d.celex for d in docs}), results_text="\n".join(lines),
    )


def _count_results(outcome: SearchResult) -> int:
    """Number of DISTINCT decisions a source reported (CGUE: rows can repeat a CELEX)."""
    if outcome.source == "cgue" and outcome.results_text:
        celex = set(re.findall(r"^\*\*CELEX\*\*: (\S+)", outcome.results_text, re.M))
        if celex:
            return len(celex)
    return outcome.num_found


async def _cerca_giurisprudenza_unificata_impl(
    query: str,
    fonti: str = "tutte",
    anno_da: str = "",
    anno_a: str = "",
    tipo_provvedimento: str = "",
    max_risultati: int = 5,
) -> str:
    # Clamp max_risultati to the documented contract (default 5, max 20)
    max_risultati = max(1, min(max_risultati, 20))
    # Parse years defensively so an invalid value cannot crash the whole search
    anno_da_int = _safe_year(anno_da)
    anno_a_int = _safe_year(anno_a)
    # Determine which sources to query
    _FONTI = _get_fonti()
    if fonti.strip().lower() == "tutte":
        fonti_selezionate = list(_FONTI.keys())
    else:
        fonti_selezionate = [f.strip().lower() for f in fonti.split(",") if f.strip().lower() in _FONTI]
        if not fonti_selezionate:
            fonti_selezionate = list(_FONTI.keys())

    # Build coroutines per source
    coros = []
    ordine = []
    for chiave in fonti_selezionate:
        label, fn = _FONTI[chiave]
        ordine.append((chiave, label))
        if chiave == "cassazione":
            coros.append(fn(
                query,
                anno_da=anno_da_int,
                anno_a=anno_a_int,
                tipo_provvedimento=tipo_provvedimento,
                max_risultati=max_risultati,
            ))
        elif chiave == "tributaria":
            coros.append(fn(
                query,
                data_da=f"01/01/{anno_da}" if anno_da else "",
                data_a=f"31/12/{anno_a}" if anno_a else "",
                tipo_provvedimento=tipo_provvedimento,
                max_risultati=max_risultati,
            ))
        elif chiave == "amministrativa":
            coros.append(_cerca_amministrativa(
                fn, query, anno_da_int, anno_a_int, tipo_provvedimento, max_risultati,
            ))
        elif chiave == "ue":
            coros.append(_cerca_ue(
                fn, query, anno_da, anno_a, tipo_provvedimento, max_risultati,
            ))

    outcomes = await asyncio.gather(*coros, return_exceptions=True)

    sections = []
    footer_parts = []

    for (chiave, label), outcome in zip(ordine, outcomes):
        if isinstance(outcome, Exception):
            body = f"errore: {outcome}"
            footer_parts.append(f"{label} (errore)")
        elif isinstance(outcome, SearchResult):
            if not outcome.success and outcome.error_type == "source_down":
                body = "non raggiungibile"
                footer_parts.append(f"{label} (non raggiungibile)")
            elif not outcome.success and outcome.error_type == "no_results":
                # Keep the source's own explanation (e.g. the note on the year filter, "Nessuna
                # sentenza CGUE trovata per ..."): a bare "0 risultati" hides why.
                body = outcome.results_text or "0 risultati"
                footer_parts.append(f"{label} (0 risultati)")
            elif not outcome.success:
                # A source that answered with something unreadable failed: it is not "0 risultati".
                body = outcome.to_str()
                footer_parts.append(f"{label} (errore)")
            elif outcome.success and outcome.num_found == 0 and outcome.results_text.strip():
                # Source auto-relaxed a zero-hit query (e.g. Italgiure): body has results
                # despite num_found==0, so avoid the misleading "(0 risultati)" footer.
                body = outcome.results_text
                footer_parts.append(f"{label} (risultati con criteri ampliati)")
            else:
                body = outcome.results_text
                footer_parts.append(f"{label} ({_count_results(outcome)} risultati)")
        else:
            # Plain string (e.g. esplora mode or legacy return)
            body = str(outcome)
            footer_parts.append(f"{label} (risultati)")

        sections.append(f"## {label}\n\n{body}")

    output_parts = [f"# Ricerca giurisprudenziale unificata: {query}", ""]
    output_parts.extend(sections)
    output_parts.append("---")
    output_parts.append(f"**Fonti consultate**: {', '.join(footer_parts)}")

    return "\n\n".join(output_parts)


@mcp.tool(tags={"giurisprudenza", "giurisprudenza_amm", "giurisprudenza_ue", "fiscale"})
async def cerca_giurisprudenza_unificata(
    query: str,
    fonti: str = "tutte",
    anno_da: str = "",
    anno_a: str = "",
    tipo_provvedimento: str = "",
    max_risultati: int = 5,
) -> str:
    """Cerca giurisprudenza su tutte le fonti disponibili in parallelo.

    Lancia ricerche simultanee su Cassazione (Italgiure), giurisprudenza tributaria (CeRDEF),
    giustizia amministrativa (TAR/CdS) e Corte di Giustizia UE (CGUE).
    Restituisce risultati aggregati con indicazione della fonte per ciascuno.

    USARE per ricerche trasversali che possono coinvolgere piu' giurisdizioni.
    Per ricerche mirate su una singola fonte, usare i tool specifici.

    Comportamento per fonte: Cassazione, archivio a finestra mobile di circa cinque anni (a
    settembre 2026 dal 27/09/2021); giustizia amministrativa, il portale non filtra per anno e
    l'intervallo anno_da-anno_a è applicato sulle 50 decisioni più recenti; CGUE, la query è
    cercata come sottostringa del titolo (le virgole valgono OR) e, se una frase di più parole non
    trova nulla, le parole sono cercate tutte insieme nel titolo. Il riepilogo "Fonti consultate"
    conta le decisioni distinte e riporta il conteggio mostrato nella sezione.

    Args:
        query: Testo da cercare (es. "responsabilita' medica", "appalto pubblico")
        fonti: Fonti da interrogare: 'tutte' (default), oppure lista separata da virgola
            (es. 'cassazione,tributaria', 'amministrativa,ue')
        anno_da: Anno inizio ricerca (es. "2020")
        anno_a: Anno fine ricerca (es. "2025")
        tipo_provvedimento: Tipo: 'sentenza', 'ordinanza', 'decreto' (applicato dove supportato)
        max_risultati: Massimo risultati PER FONTE (default 5, max 20)
    """
    return await _cerca_giurisprudenza_unificata_impl(
        query=query,
        fonti=fonti,
        anno_da=anno_da,
        anno_a=anno_a,
        tipo_provvedimento=tipo_provvedimento,
        max_risultati=max_risultati,
    )

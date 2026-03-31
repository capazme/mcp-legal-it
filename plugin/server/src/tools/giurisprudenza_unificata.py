"""Unified cross-source jurisprudence search across Italgiure, CeRDEF, Giustizia Amministrativa and CGUE.

Launches parallel searches on all (or selected) sources and merges results with source provenance.
"""

import asyncio

from src.server import mcp
from src.lib._result import SearchResult


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


async def _cerca_giurisprudenza_unificata_impl(
    query: str,
    fonti: str = "tutte",
    anno_da: str = "",
    anno_a: str = "",
    tipo_provvedimento: str = "",
    max_risultati: int = 5,
) -> str:
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
                anno_da=int(anno_da) if anno_da else 0,
                anno_a=int(anno_a) if anno_a else 0,
                tipo_provvedimento=tipo_provvedimento,
                max_risultati=max_risultati,
            ))
        elif chiave == "tributaria":
            coros.append(fn(
                query,
                data_da=f"{anno_da}-01-01" if anno_da else "",
                data_a=f"{anno_a}-12-31" if anno_a else "",
                tipo_provvedimento=tipo_provvedimento,
                max_risultati=max_risultati,
            ))
        elif chiave == "amministrativa":
            coros.append(fn(
                query,
                anno=anno_da,
                tipo=tipo_provvedimento,
                max_risultati=max_risultati,
            ))
        elif chiave == "ue":
            coros.append(fn(
                query,
                anno_da=anno_da,
                anno_a=anno_a,
                tipo_documento=tipo_provvedimento,
                max_risultati=max_risultati,
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
                body = "0 risultati"
                footer_parts.append(f"{label} (0 risultati)")
            else:
                body = outcome.results_text
                footer_parts.append(f"{label} ({outcome.num_found} risultati)")
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

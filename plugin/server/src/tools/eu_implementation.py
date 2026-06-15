"""MCP tools for EU -> Italy implementation mapping (national transposition).

TRIGGER: usare quando l'utente chiede come una direttiva UE è stata recepita in Italia,
quale decreto legislativo attua una direttiva, qual è la base giuridica UE di un atto
italiano, qual è il termine di trasposizione di una direttiva, o se un atto UE richiede
recepimento (direttiva) o è direttamente applicabile (regolamento).

Fonte: CELLAR SPARQL (publications.europa.eu), predicati "national implementing measure".
La misura nazionale (MNE) è SOLO metadato: per il testo dell'atto usare cite_law.
"""

from src.lib._result import SearchResult
from src.server import mcp
from src.lib.eu_implementation.client import (
    MappingResult,
    format_basis,
    format_implementation,
    get_eu_basis as _client_get_eu_basis,
    get_italian_implementation as _client_get_italian_implementation,
)


# ---------------------------------------------------------------------------
# Impl functions (testable without MCP context)
# ---------------------------------------------------------------------------

def _mapping_to_search_result(mapping: MappingResult) -> SearchResult:
    """Render a MappingResult into the shared SearchResult contract."""
    source = "eu_implementation"

    if not mapping.success:
        if mapping.error_type == "source_down":
            return SearchResult(
                success=False, source=source, error_type="source_down",
                error_message=mapping.error_message,
            )
        if mapping.error_type == "bad_input":
            return SearchResult(
                success=False, source=source, error_type="no_results",
                results_text=f"**Errore**: {mapping.error_message}",
            )
        if mapping.error_type == "regulation":
            return SearchResult(
                success=False, source=source, error_type="no_results",
                results_text=(
                    f"**{mapping.celex}** — {mapping.error_message}\n\n"
                    f"Un regolamento UE non viene recepito da un atto nazionale: "
                    f"si applica direttamente. Per il testo usare `cite_law`."
                ),
            )
        if mapping.error_type == "no_results":
            if mapping.direction == "eu_to_it":
                ref = mapping.celex or mapping.query_ref
                return SearchResult(
                    success=False, source=source, error_type="no_results",
                    results_text=(
                        f"Nessuna misura nazionale italiana trovata per la direttiva _{ref}_ "
                        f"nel database CELLAR. Possibili cause: trasposizione non ancora "
                        f"notificata, recepimento tramite atto non mappato, o termine non scaduto."
                    ),
                )
            return SearchResult(
                success=False, source=source, error_type="no_results",
                results_text=(
                    f"Nessuna base giuridica UE trovata per _{mapping.query_ref}_ nel database "
                    f"CELLAR. Verificare il numero/anno dell'atto o usare il CELEX della misura "
                    f"nazionale (es. 72019L0790ITA_202107973)."
                ),
            )
        return SearchResult(
            success=False, source=source, error_type="no_results",
            results_text=f"Nessun risultato per _{mapping.query_ref}_.",
        )

    if mapping.direction == "eu_to_it":
        impls = mapping.implementations
        lines = [
            f"**Recepimento italiano della direttiva {mapping.celex}** — "
            f"{len(impls)} misura/e nazionale/i\n",
            "_Le misure nazionali sono metadati: per il testo usare `cite_law`._\n",
        ]
        for impl in impls:
            lines.append(format_implementation(impl))
            lines.append("")
        return SearchResult(
            success=True, source=source, num_found=len(impls),
            results_text="\n".join(lines),
        )

    bases = mapping.bases
    ref = mapping.celex or mapping.query_ref
    header = f"**Base giuridica UE di {ref}** — {len(bases)} direttiva/e recepita/e\n"
    lines = [header]
    if len(bases) > 1:
        lines.append("_Questa misura nazionale recepisce più direttive._\n")
    for basis in bases:
        lines.append(format_basis(basis))
        lines.append("")
    return SearchResult(
        success=True, source=source, num_found=len(bases),
        results_text="\n".join(lines),
    )


async def _get_italian_implementation_impl(direttiva: str) -> SearchResult:
    try:
        mapping = await _client_get_italian_implementation(direttiva)
    except Exception as exc:
        return SearchResult(
            success=False, source="eu_implementation",
            error_type="source_down", error_message=str(exc),
        )
    return _mapping_to_search_result(mapping)


async def _get_eu_basis_impl(atto: str) -> SearchResult:
    try:
        mapping = await _client_get_eu_basis(atto)
    except Exception as exc:
        return SearchResult(
            success=False, source="eu_implementation",
            error_type="source_down", error_message=str(exc),
        )
    return _mapping_to_search_result(mapping)


async def _elenco_misure_nazionali_impl(direttiva: str, paese: str = "ITA") -> SearchResult:
    try:
        mapping = await _client_get_italian_implementation(direttiva, country=paese)
    except Exception as exc:
        return SearchResult(
            success=False, source="eu_implementation",
            error_type="source_down", error_message=str(exc),
        )
    return _mapping_to_search_result(mapping)


# ---------------------------------------------------------------------------
# MCP tool wrappers
# ---------------------------------------------------------------------------

@mcp.tool(tags={"normativa", "giurisprudenza_ue"})
async def get_italian_implementation(direttiva: str) -> str:
    """Trova l'atto italiano che recepisce una direttiva UE (mappatura UE -> Italia).

    USARE quando si chiede: "come è stata recepita in Italia la direttiva X?",
    "quale decreto legislativo attua la direttiva Y?", "qual è la legge di recepimento?".
    Restituisce: tipo atto (es. Decreto legislativo), numero, Gazzetta Ufficiale n./data,
    entrata in vigore, titolo e CELEX della misura nazionale.
    La misura nazionale è SOLO metadato — per il testo dell'atto usare `cite_law`.
    Per un regolamento UE (direttamente applicabile) viene spiegato che non c'è trasposizione.

    Args:
        direttiva: CELEX della direttiva (es. "32019L0790") oppure riferimento umano
            (es. "direttiva 2019/790", "dir 2019/790/UE", "2019/790")
    """
    result = await _get_italian_implementation_impl(direttiva)
    return result.to_str() if isinstance(result, SearchResult) else result


@mcp.tool(tags={"normativa", "giurisprudenza_ue"})
async def get_eu_basis(atto: str) -> str:
    """Trova la direttiva UE recepita da un atto italiano (mappatura Italia -> UE).

    USARE quando si chiede: "qual è la base giuridica europea del D.Lgs. X?",
    "quale direttiva UE attua questo decreto?", "da quale direttiva deriva la legge Y?".
    Restituisce: CELEX della direttiva, titolo in italiano, termine di trasposizione,
    CELLAR URI. Un atto nazionale può recepire PIÙ direttive (vengono elencate tutte).
    Per il testo della direttiva usare `cite_law`.

    Args:
        atto: Atto italiano (es. "D.Lgs. 177/2021", "decreto legislativo n. 138/2024",
            "legge 90/2024") oppure CELEX della misura nazionale
            (es. "72019L0790ITA_202107973")
    """
    result = await _get_eu_basis_impl(atto)
    return result.to_str() if isinstance(result, SearchResult) else result


@mcp.tool(tags={"normativa", "giurisprudenza_ue"})
async def elenco_misure_nazionali(direttiva: str, paese: str = "ITA") -> str:
    """Elenca le misure nazionali di recepimento di una direttiva UE in un Paese.

    Come get_italian_implementation ma con scelta del Paese (default ITA).
    USARE per confrontare il recepimento in diversi Stati membri.
    Le misure nazionali sono SOLO metadati — per il testo usare `cite_law`.

    Args:
        direttiva: CELEX della direttiva (es. "32019L0790") o riferimento umano
            (es. "direttiva 2019/790")
        paese: Codice ISO-3 del Paese (default "ITA"; es. "FRA", "DEU", "ESP")
    """
    result = await _elenco_misure_nazionali_impl(direttiva, paese=paese)
    return result.to_str() if isinstance(result, SearchResult) else result

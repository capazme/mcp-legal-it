"""MCP tools for searching CeRDEF (Banca Dati Giurisprudenza Tributaria MEF).

TRIGGER: usare quando l'utente chiede di giurisprudenza tributaria, sentenze CTP/CTR/CGT,
Cassazione tributaria, IVA, IRES, IRPEF, accertamento, riscossione, contenzioso tributario.
"""

from src.server import mcp
from src.lib.cerdef.client import (
    search_giurisprudenza,
    fetch_provvedimento,
    format_result,
    format_detail,
)


# ---------------------------------------------------------------------------
# Impl functions (testable without MCP context)
# ---------------------------------------------------------------------------


async def _cerca_giurisprudenza_tributaria_impl(
    query: str,
    tipo_provvedimento: str = "",
    ente: str = "",
    data_da: str = "",
    data_a: str = "",
    numero: str = "",
    criterio: str = "tutti",
    ordinamento: str = "rilevanza",
    max_risultati: int = 10,
) -> str:
    max_risultati = min(max_risultati, 250)

    try:
        docs = await search_giurisprudenza(
            parole=query,
            tipo_criterio=criterio,
            tipo_estremi=tipo_provvedimento,
            numero=numero,
            data_da=data_da,
            data_a=data_a,
            ente=ente,
            ordinamento=ordinamento,
            rows=max_risultati,
        )
    except Exception as exc:
        return f"Errore nella ricerca CeRDEF: {exc}"

    if not docs:
        return f"Nessun provvedimento CeRDEF trovato per: _{query}_"

    lines = [f"**Trovati {len(docs)} provvedimenti CeRDEF per**: _{query}_\n"]
    for doc in docs:
        lines.append(format_result(doc))
        lines.append("")
    return "\n".join(lines)


async def _cerdef_leggi_provvedimento_impl(guid: str) -> str:
    try:
        detail = await fetch_provvedimento(guid)
        return format_detail(detail)
    except Exception as exc:
        return f"Errore nel recupero del provvedimento CeRDEF (GUID {guid}): {exc}"


async def _ultime_sentenze_tributarie_impl(
    ente: str = "",
    tipo_provvedimento: str = "",
    max_risultati: int = 10,
) -> str:
    max_risultati = min(max_risultati, 250)

    try:
        docs = await search_giurisprudenza(
            tipo_estremi=tipo_provvedimento,
            ente=ente,
            ordinamento="data",
            rows=max_risultati,
        )
    except Exception as exc:
        return f"Errore nel recupero delle ultime sentenze tributarie CeRDEF: {exc}"

    if not docs:
        return "Nessuna sentenza tributaria recente trovata su CeRDEF."

    lines = ["**Ultime sentenze tributarie CeRDEF**\n"]
    for doc in docs:
        lines.append(format_result(doc))
        lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# MCP tool wrappers
# ---------------------------------------------------------------------------


@mcp.tool(tags={"giurisprudenza", "fiscale"})
async def cerca_giurisprudenza_tributaria(
    query: str,
    tipo_provvedimento: str = "",
    ente: str = "",
    data_da: str = "",
    data_a: str = "",
    numero: str = "",
    criterio: str = "tutti",
    ordinamento: str = "rilevanza",
    max_risultati: int = 10,
) -> str:
    """Cerca sentenze e provvedimenti nella banca dati CeRDEF (MEF — def.finanze.it).

    USARE quando si parla di: giurisprudenza tributaria, sentenze CTP/CTR/CGT,
    Cassazione tributaria, IVA, IRES, IRPEF, accertamento fiscale, riscossione,
    contenzioso tributario, sanzioni tributarie, rimborsi fiscali.
    Dopo aver trovato un provvedimento, usare cerdef_leggi_provvedimento() per il testo completo.
    Restituisce: lista provvedimenti con estremi, oggetto, ente, data e GUID.

    Args:
        query: Testo da cercare (es. "IVA soggettivita passiva", "accertamento sintetico")
        tipo_provvedimento: Filtra per tipo (es. "sentenza", "ordinanza", "decreto")
        ente: Filtra per ente (es. "corte_suprema", "cgt_primo_grado", "cgt_secondo_grado")
        data_da: Data inizio in formato DD/MM/YYYY (es. "01/01/2023")
        data_a: Data fine in formato DD/MM/YYYY (es. "31/12/2024")
        numero: Numero specifico del provvedimento
        criterio: Criterio di ricerca ("tutti", "frase_esatta", "almeno_uno", "codice")
        ordinamento: Ordinamento risultati ("rilevanza" o "data")
        max_risultati: Numero massimo di risultati (default 10, max 250)
    """
    return await _cerca_giurisprudenza_tributaria_impl(
        query=query,
        tipo_provvedimento=tipo_provvedimento,
        ente=ente,
        data_da=data_da,
        data_a=data_a,
        numero=numero,
        criterio=criterio,
        ordinamento=ordinamento,
        max_risultati=max_risultati,
    )


@mcp.tool(tags={"giurisprudenza", "fiscale"})
async def cerdef_leggi_provvedimento(guid: str) -> str:
    """Legge il testo completo di un provvedimento CeRDEF tramite GUID.

    Usare dopo cerca_giurisprudenza_tributaria() o ultime_sentenze_tributarie()
    per leggere massima e testo integrale del provvedimento.
    Il GUID e riportato in ogni risultato della ricerca.
    Restituisce: massima e testo integrale del provvedimento tributario.

    Args:
        guid: GUID del provvedimento (es. "abc-123-def-456")
    """
    return await _cerdef_leggi_provvedimento_impl(guid)


@mcp.tool(tags={"giurisprudenza", "fiscale"})
async def ultime_sentenze_tributarie(
    ente: str = "",
    tipo_provvedimento: str = "",
    max_risultati: int = 10,
) -> str:
    """Ultime sentenze e provvedimenti tributari da CeRDEF (MEF), con filtro opzionale.

    Dopo questo tool: cerdef_leggi_provvedimento() con il GUID per il testo completo.
    Restituisce: lista cronologica delle ultime sentenze tributarie con estremi, ente e data.

    Args:
        ente: Filtra per ente (es. "corte_suprema", "cgt_primo_grado", "cgt_secondo_grado")
        tipo_provvedimento: Filtra per tipo (es. "sentenza", "ordinanza", "decreto")
        max_risultati: Numero massimo di risultati (default 10, max 250)
    """
    return await _ultime_sentenze_tributarie_impl(
        ente=ente,
        tipo_provvedimento=tipo_provvedimento,
        max_risultati=max_risultati,
    )

"""MCP tools for searching CONSOB (Commissione Nazionale per le Societa e la Borsa) documents.

TRIGGER: usare quando l'utente chiede di delibere/provvedimenti CONSOB, sanzioni mercati
finanziari, abusi di mercato, intermediari, emittenti, OPA, crowdfunding, cripto-attivita.
"""

from src.server import mcp
from src.lib.consob.client import (
    ARGOMENTI,
    TIPOLOGIE,
    fetch_delibera,
    format_full,
    format_result,
    search_delibere,
)


# ---------------------------------------------------------------------------
# Impl functions (testable without MCP context)
# ---------------------------------------------------------------------------

async def _cerca_delibere_consob_impl(
    query: str,
    tipologia: str = "",
    argomento: str = "",
    data_da: str = "",
    data_a: str = "",
    max_risultati: int = 20,
) -> str:
    max_risultati = min(max_risultati, 100)

    # Resolve tipologia key to Liferay value
    tipologia_val = TIPOLOGIE.get(tipologia.lower(), tipologia) if tipologia else ""

    # Resolve argomento key to Liferay ID
    argomento_id = ARGOMENTI.get(argomento.lower().replace(" ", "_"), argomento) if argomento else ""

    try:
        docs = await search_delibere(
            keywords=query,
            tipologia=tipologia_val,
            argomento_id=argomento_id,
            start_date=data_da,
            end_date=data_a,
            rows=max_risultati,
        )
    except Exception as exc:
        return f"Errore nella ricerca CONSOB: {exc}"

    if not docs:
        return f"Nessuna delibera CONSOB trovata per: _{query}_"

    lines = [f"**Trovate {len(docs)} delibere CONSOB per**: _{query}_\n"]
    for doc in docs:
        lines.append(format_result(doc))
        lines.append("")
    return "\n".join(lines)


async def _leggi_delibera_consob_impl(numero: str) -> str:
    try:
        title, text = await fetch_delibera(numero)
        return format_full(title, text, numero)
    except Exception as exc:
        return f"Errore nel recupero della delibera CONSOB n. {numero}: {exc}"


async def _ultime_delibere_consob_impl(
    tipologia: str = "",
    argomento: str = "",
    max_risultati: int = 10,
) -> str:
    max_risultati = min(max_risultati, 100)

    tipologia_val = TIPOLOGIE.get(tipologia.lower(), tipologia) if tipologia else ""
    argomento_id = ARGOMENTI.get(argomento.lower().replace(" ", "_"), argomento) if argomento else ""

    try:
        docs = await search_delibere(
            tipologia=tipologia_val,
            argomento_id=argomento_id,
            rows=max_risultati,
        )
    except Exception as exc:
        return f"Errore nel recupero delle ultime delibere CONSOB: {exc}"

    if not docs:
        return "Nessuna delibera CONSOB recente trovata."

    lines = ["**Ultime delibere CONSOB**\n"]
    for doc in docs:
        lines.append(format_result(doc))
        lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# MCP tool wrappers
# ---------------------------------------------------------------------------

@mcp.tool(tags={"consob"})
async def cerca_delibere_consob(
    query: str,
    tipologia: str = "",
    argomento: str = "",
    data_da: str = "",
    data_a: str = "",
    max_risultati: int = 20,
) -> str:
    """Cerca delibere e provvedimenti CONSOB nel bollettino ufficiale.

    USARE quando si parla di: delibere CONSOB, sanzioni mercati finanziari, abusi di mercato,
    intermediari, emittenti, OPA, crowdfunding, cripto-attivita, regolamenti CONSOB.
    Dopo aver trovato una delibera, usare leggi_delibera_consob() per il testo completo.
    Restituisce: lista delibere con numero, titolo, data e link.

    Args:
        query: Testo da cercare (es. "abusi di mercato", "sanzione intermediario", "OPA")
        tipologia: Filtra per tipo (es. "delibere", "comunicazioni", "provvedimenti_urgenti", "opa")
        argomento: Filtra per argomento (es. "abusi_di_mercato", "intermediari", "emittenti",
            "mercati", "offerte_acquisto", "gestione_collettiva", "servizi_investimento",
            "cripto_attivita", "crowdfunding") oppure ID Liferay diretto
        data_da: Data inizio in formato YYYY-MM-DD (es. "2023-01-01")
        data_a: Data fine in formato YYYY-MM-DD (es. "2024-12-31")
        max_risultati: Numero massimo di risultati (default 20, max 100)
    """
    return await _cerca_delibere_consob_impl(
        query=query, tipologia=tipologia, argomento=argomento,
        data_da=data_da, data_a=data_a, max_risultati=max_risultati,
    )


@mcp.tool(tags={"consob"})
async def leggi_delibera_consob(numero: str) -> str:
    """Legge il testo completo di una delibera CONSOB tramite numero.

    Usare dopo cerca_delibere_consob() o ultime_delibere_consob() per leggere
    il testo completo. Il numero delibera e riportato in ogni risultato della ricerca.
    Restituisce: testo integrale della delibera con titolo e link alla fonte CONSOB.

    Args:
        numero: Numero della delibera (es. "23257", "23256-1")
    """
    return await _leggi_delibera_consob_impl(numero)


@mcp.tool(tags={"consob"})
async def ultime_delibere_consob(
    tipologia: str = "",
    argomento: str = "",
    max_risultati: int = 10,
) -> str:
    """Ultime delibere e provvedimenti pubblicati dalla CONSOB, con filtro opzionale.

    Dopo questo tool: leggi_delibera_consob() con il numero per il testo completo.
    Restituisce: lista cronologica delle ultime delibere con numero, titolo e data.

    Args:
        tipologia: Filtra per tipo (es. "delibere", "comunicazioni", "provvedimenti_urgenti")
        argomento: Filtra per argomento (es. "abusi_di_mercato", "intermediari", "emittenti")
        max_risultati: Numero massimo di risultati (default 10, max 100)
    """
    return await _ultime_delibere_consob_impl(
        tipologia=tipologia, argomento=argomento, max_risultati=max_risultati,
    )

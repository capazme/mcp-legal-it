"""MCP tools for searching GPDP (Garante per la Protezione dei Dati Personali) documents.

TRIGGER: usare quando l'utente chiede di provvedimenti/sanzioni del Garante Privacy,
linee guida GPDP, data breach, cookie policy, profilazione, videosorveglianza,
trattamento dati personali, intelligenza artificiale e privacy.
"""

from src.server import mcp
from src.lib.gpdp.client import (
    fetch_doc,
    format_full,
    format_result,
    search_docs,
)


# ---------------------------------------------------------------------------
# Impl functions (testable without MCP context)
# ---------------------------------------------------------------------------

async def _cerca_provvedimenti_garante_impl(
    query: str,
    tipologia: str = "",
    data_da: str = "",
    data_a: str = "",
    max_risultati: int = 10,
) -> str:
    max_risultati = min(max_risultati, 50)
    try:
        docs = await search_docs(
            query=query,
            data_da=data_da,
            data_a=data_a,
            rows=max_risultati if not tipologia else min(max_risultati * 3, 50),
        )
    except Exception as exc:
        return f"Errore nella ricerca: {exc}"

    if tipologia:
        tip_lower = tipologia.lower()
        docs = [d for d in docs if tip_lower in d.tipologia.lower()]

    docs = docs[:max_risultati]
    if not docs:
        return f"Nessun provvedimento trovato per: _{query}_"

    lines = [f"**Trovati {len(docs)} provvedimenti del Garante per**: _{query}_\n"]
    for doc in docs:
        lines.append(format_result(doc))
        lines.append("")
    return "\n".join(lines)


async def _leggi_provvedimento_garante_impl(docweb_id: int) -> str:
    try:
        title, text = await fetch_doc(docweb_id)
        return format_full(title, text, docweb_id)
    except Exception as exc:
        return f"Errore nel recupero del provvedimento DocWeb {docweb_id}: {exc}"


async def _ultimi_provvedimenti_garante_impl(
    tipologia: str = "",
    max_risultati: int = 10,
) -> str:
    max_risultati = min(max_risultati, 50)
    try:
        docs = await search_docs(
            rows=max_risultati if not tipologia else min(max_risultati * 3, 50),
            sort_by="data",
        )
    except Exception as exc:
        return f"Errore nel recupero degli ultimi provvedimenti: {exc}"

    if tipologia:
        tip_lower = tipologia.lower()
        docs = [d for d in docs if tip_lower in d.tipologia.lower()]

    docs = docs[:max_risultati]
    if not docs:
        return "Nessun provvedimento recente trovato."

    lines = ["**Ultimi provvedimenti del Garante Privacy**\n"]
    for doc in docs:
        lines.append(format_result(doc))
        lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# MCP tool wrappers
# ---------------------------------------------------------------------------

@mcp.tool(tags={"privacy"})
async def cerca_provvedimenti_garante(
    query: str,
    tipologia: str = "",
    data_da: str = "",
    data_a: str = "",
    max_risultati: int = 10,
) -> str:
    """Cerca provvedimenti, linee guida e pareri del Garante Privacy (GPDP) dalla fonte ufficiale.

    USARE quando si parla di: sanzioni GDPR, provvedimenti del Garante, cookie policy,
    data breach, profilazione, videosorveglianza, trattamento dati, AI e privacy.
    Dopo aver trovato un documento, usare leggi_provvedimento_garante() per il testo completo.
    Dopo questo tool: leggi_provvedimento_garante() con il DocWeb ID per il testo completo.
    Restituisce: lista provvedimenti con DocWeb ID, data, tipologia, oggetto e snippet.

    Args:
        query: Testo da cercare (es. "data breach notifica", "cookie consenso", "intelligenza artificiale")
        tipologia: Filtra per tipo documento (es. "provvedimento", "ordinanza", "parere", "linee guida")
        data_da: Data inizio in formato DD/MM/YYYY (es. "01/01/2023")
        data_a: Data fine in formato DD/MM/YYYY (es. "31/12/2024")
        max_risultati: Numero massimo di risultati (default 10, max 50)
    """
    return await _cerca_provvedimenti_garante_impl(
        query=query, tipologia=tipologia, data_da=data_da,
        data_a=data_a, max_risultati=max_risultati,
    )


@mcp.tool(tags={"privacy"})
async def leggi_provvedimento_garante(docweb_id: int) -> str:
    """Legge il testo completo di un provvedimento del Garante Privacy tramite DocWeb ID.

    Usare dopo cerca_provvedimenti_garante() o ultimi_provvedimenti_garante() per leggere
    il testo completo. Il DocWeb ID è riportato in ogni risultato della ricerca.
    Restituisce: testo integrale del provvedimento con titolo, data, e link alla fonte GPDP.

    Esempi di DocWeb ID noti:
    - 9677876: Linee guida cookie 2021
    - 9870832: Linee guida AI 2023
    - 10000069: Provvedimento ChatGPT 2023

    Args:
        docweb_id: ID numerico del documento Garante (es. 9677876)
    """
    return await _leggi_provvedimento_garante_impl(docweb_id)


@mcp.tool(tags={"privacy"})
async def ultimi_provvedimenti_garante(
    tipologia: str = "",
    max_risultati: int = 10,
) -> str:
    """Ultimi provvedimenti depositati dal Garante Privacy, con filtro opzionale per tipologia.

    Dopo questo tool: leggi_provvedimento_garante() con il DocWeb ID per il testo completo.
    Restituisce: lista cronologica degli ultimi provvedimenti con DocWeb ID e metadati.

    Args:
        tipologia: Filtra per tipo (es. "provvedimento", "ordinanza", "parere", "linee guida")
        max_risultati: Numero massimo di risultati (default 10, max 50)
    """
    return await _ultimi_provvedimenti_garante_impl(
        tipologia=tipologia, max_risultati=max_risultati,
    )

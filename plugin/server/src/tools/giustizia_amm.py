"""MCP tools for searching Giustizia Amministrativa (TAR/Consiglio di Stato).

TRIGGER: usare quando l'utente chiede di sentenze TAR, Consiglio di Stato, giustizia
amministrativa, appalti pubblici, urbanistica, edilizia, PA, accesso atti, silenzio-assenso,
annullamento atti amministrativi, ricorso al TAR, CGARS.
"""

from src.server import mcp
from src.lib.giustizia_amm.client import (
    fetch_provvedimento_text,
    format_full,
    format_result,
    search_provvedimenti,
)


# ---------------------------------------------------------------------------
# Impl functions (testable without MCP context)
# ---------------------------------------------------------------------------

async def _cerca_giurisprudenza_amministrativa_impl(
    query: str,
    sede: str = "",
    tipo: str = "",
    anno: str = "",
    numero: str = "",
    max_risultati: int = 10,
) -> str:
    max_risultati = min(max_risultati, 50)

    try:
        docs = await search_provvedimenti(
            query=query,
            tipo=tipo,
            sede=sede,
            anno=anno,
            numero=numero,
            rows=max_risultati,
        )
    except Exception as exc:
        return f"Errore nella ricerca Giustizia Amministrativa: {exc}"

    if not docs:
        return f"Nessun provvedimento amministrativo trovato per: _{query}_"

    lines = [f"**Trovati {len(docs)} provvedimenti TAR/CdS per**: _{query}_\n"]
    for doc in docs:
        lines.append(format_result(doc))
        lines.append("")
    return "\n".join(lines)


async def _leggi_provvedimento_amm_impl(sede: str, nrg: str, nome_file: str) -> str:
    try:
        title, text = await fetch_provvedimento_text(sede, nrg, nome_file)
        return format_full(title, text, sede, nrg)
    except Exception as exc:
        return f"Errore nel recupero del provvedimento {sede} NRG {nrg}: {exc}"


async def _giurisprudenza_amm_su_norma_impl(
    riferimento: str,
    sede: str = "",
    anno_da: str = "",
    max_risultati: int = 10,
) -> str:
    max_risultati = min(max_risultati, 50)

    try:
        docs = await search_provvedimenti(
            query=riferimento,
            sede=sede,
            anno=anno_da,
            rows=max_risultati,
        )
    except Exception as exc:
        return f"Errore nella ricerca giurisprudenza amministrativa su norma: {exc}"

    if not docs:
        return f"Nessun provvedimento amministrativo trovato per la norma: _{riferimento}_"

    lines = [f"**Provvedimenti TAR/CdS che citano**: _{riferimento}_\n"]
    for doc in docs:
        lines.append(format_result(doc))
        lines.append("")
    return "\n".join(lines)


async def _ultimi_provvedimenti_amm_impl(
    sede: str = "",
    tipo: str = "",
    max_risultati: int = 10,
) -> str:
    max_risultati = min(max_risultati, 50)

    try:
        docs = await search_provvedimenti(
            sede=sede,
            tipo=tipo,
            rows=max_risultati,
        )
    except Exception as exc:
        return f"Errore nel recupero degli ultimi provvedimenti amministrativi: {exc}"

    if not docs:
        return "Nessun provvedimento amministrativo recente trovato."

    lines = ["**Ultimi provvedimenti TAR/Consiglio di Stato**\n"]
    for doc in docs:
        lines.append(format_result(doc))
        lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# MCP tool wrappers
# ---------------------------------------------------------------------------

@mcp.tool(tags={"giurisprudenza_amm", "normativa"})
async def cerca_giurisprudenza_amministrativa(
    query: str,
    sede: str = "",
    tipo: str = "",
    anno: str = "",
    numero: str = "",
    max_risultati: int = 10,
) -> str:
    """Cerca sentenze e provvedimenti di TAR e Consiglio di Stato.

    USARE quando si parla di: sentenze TAR, Consiglio di Stato, giustizia amministrativa,
    appalti pubblici, urbanistica, edilizia, PA, accesso atti, silenzio-assenso,
    annullamento provvedimenti amministrativi, ricorso TAR, CGARS.
    Dopo aver trovato un provvedimento, usare leggi_provvedimento_amm() per il testo completo.
    Restituisce: lista provvedimenti con sede, NRG, tipo, data e oggetto.

    Args:
        query: Testo da cercare (es. "appalto pubblico esclusione", "silenzio-assenso", "DIA SCIA")
        sede: Filtra per sede (es. "consiglio_di_stato", "tar_lazio", "tar_lombardia")
            Valori disponibili: consiglio_di_stato, cgars, tar_lazio, tar_lombardia,
            tar_campania_napoli, tar_veneto, tar_piemonte, tar_emilia_romagna, tar_toscana,
            tar_puglia_bari, tar_sicilia_palermo, tar_liguria, tar_sardegna, tar_friuli,
            tar_marche, tar_umbria, tar_molise, tar_basilicata e altri TARs regionali
        tipo: Filtra per tipo (es. "sentenza", "ordinanza", "decreto", "parere")
        anno: Filtra per anno (es. "2024", "2023")
        numero: Numero del provvedimento (es. "1234") per ricerca per numero specifico
        max_risultati: Numero massimo di risultati (default 10, max 50)
    """
    return await _cerca_giurisprudenza_amministrativa_impl(
        query=query, sede=sede, tipo=tipo, anno=anno, numero=numero, max_risultati=max_risultati,
    )


@mcp.tool(tags={"giurisprudenza_amm", "normativa"})
async def leggi_provvedimento_amm(sede: str, nrg: str, nome_file: str) -> str:
    """Legge il testo completo di un provvedimento amministrativo (TAR/CdS) dal sottodominio mdp.

    Usare dopo cerca_giurisprudenza_amministrativa() o ultimi_provvedimenti_amm()
    per leggere il testo integrale. I parametri sede, nrg e nome_file sono riportati
    in ogni risultato della ricerca.
    Restituisce: testo integrale del provvedimento (motivazione + dispositivo).

    Args:
        sede: Codice sede (es. "CDS", "TARLAZ", "TARLOM") — da risultati ricerca
        nrg: Numero registro generale (es. "202301234") — da risultati ricerca
        nome_file: Nome file XML sul sottodominio mdp (es. "202301234_11.xml") — da risultati ricerca
    """
    return await _leggi_provvedimento_amm_impl(sede, nrg, nome_file)


@mcp.tool(tags={"giurisprudenza_amm", "normativa"})
async def giurisprudenza_amm_su_norma(
    riferimento: str,
    sede: str = "",
    anno_da: str = "",
    max_risultati: int = 10,
) -> str:
    """Trova provvedimenti TAR/CdS che citano una norma specifica.

    USARE quando si vuole trovare giurisprudenza amministrativa su un articolo di legge
    specifico: CPA, Codice Appalti, L. 241/1990, TU Edilizia, TUEL, ecc.
    Dopo aver trovato i provvedimenti, usare leggi_provvedimento_amm() per il testo completo.
    Restituisce: lista provvedimenti che citano il riferimento normativo.

    Args:
        riferimento: Riferimento normativo (es. "art. 21 L. 241/1990", "art. 83 D.Lgs. 36/2023",
            "art. 36 CPA", "art. 10-bis L. 241/1990")
        sede: Filtra per sede (opzionale, es. "consiglio_di_stato", "tar_lazio")
        anno_da: Anno di partenza della ricerca (es. "2022")
        max_risultati: Numero massimo di risultati (default 10, max 50)
    """
    return await _giurisprudenza_amm_su_norma_impl(
        riferimento=riferimento, sede=sede, anno_da=anno_da, max_risultati=max_risultati,
    )


@mcp.tool(tags={"giurisprudenza_amm", "normativa"})
async def ultimi_provvedimenti_amm(
    sede: str = "",
    tipo: str = "",
    max_risultati: int = 10,
) -> str:
    """Ultimi provvedimenti depositati da TAR e Consiglio di Stato, con filtro opzionale.

    Dopo questo tool: leggi_provvedimento_amm() con sede, nrg e nome_file per il testo completo.
    Restituisce: lista cronologica degli ultimi provvedimenti amministrativi.

    Args:
        sede: Filtra per sede (es. "consiglio_di_stato", "tar_lazio", "tar_lombardia")
        tipo: Filtra per tipo (es. "sentenza", "ordinanza", "decreto", "parere")
        max_risultati: Numero massimo di risultati (default 10, max 50)
    """
    return await _ultimi_provvedimenti_amm_impl(
        sede=sede, tipo=tipo, max_risultati=max_risultati,
    )

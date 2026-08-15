"""MCP tools for searching Giustizia Amministrativa (TAR/Consiglio di Stato).

TRIGGER: usare quando l'utente chiede di sentenze TAR, Consiglio di Stato, giustizia
amministrativa, appalti pubblici, urbanistica, edilizia, PA, accesso atti, silenzio-assenso,
annullamento atti amministrativi, ricorso al TAR, CGARS.
"""

from src.server import mcp
from src.lib._result import SearchResult
from src.lib.giustizia_amm.client import (
    ProvvedimentoResult,
    fetch_provvedimento_text,
    format_full,
    format_result,
    search_provvedimenti,
)

# The portal dropped the standalone year filter in the 2026 reorganisation: a
# year is only honoured server-side when paired with a provvedimento number.
# Anything else has to be filtered here, on the page we got back.
_NO_YEAR_FILTER_NOTE = (
    "\n\n---\n*Nota: il portale della Giustizia Amministrativa non espone più un filtro "
    "per anno indipendente dal numero del provvedimento. Il filtro è stato applicato sui "
    "risultati restituiti (ordinati dal più recente); per anni remoti indicare anche "
    "`numero`, oppure restringere la query.*"
)


# ---------------------------------------------------------------------------
# Impl functions (testable without MCP context)
# ---------------------------------------------------------------------------

def _filter_by_anno(
    docs: list[ProvvedimentoResult], anno: str, *, since: bool = False
) -> list[ProvvedimentoResult]:
    """Client-side year filter. `since=True` keeps anno >= the given year."""
    anno = (anno or "").strip()
    if not anno.isdigit():
        return docs
    if since:
        return [d for d in docs if d.anno and d.anno >= anno]
    return [d for d in docs if d.anno == anno]

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
        return SearchResult(success=False, source="giustizia_amm", error_type="source_down", error_message=str(exc))

    # A year without a number can only be honoured client-side.
    filtered_by_year = bool(anno) and not numero
    if filtered_by_year:
        docs = _filter_by_anno(docs, anno)

    if not docs:
        detail = f"Nessun provvedimento amministrativo trovato per: _{query}_"
        if filtered_by_year:
            detail += _NO_YEAR_FILTER_NOTE
        return SearchResult(success=False, source="giustizia_amm", error_type="no_results",
                          results_text=detail)

    lines = [f"**Trovati {len(docs)} provvedimenti TAR/CdS per**: _{query}_\n"]
    for doc in docs:
        lines.append(format_result(doc))
        lines.append("")
    if filtered_by_year:
        lines.append(_NO_YEAR_FILTER_NOTE)
    return SearchResult(success=True, source="giustizia_amm", num_found=len(docs), results_text="\n".join(lines))


async def _leggi_provvedimento_amm_impl(sede: str, nrg: str, nome_file: str) -> str:
    try:
        title, text = await fetch_provvedimento_text(sede, nrg, nome_file)
        if not text.strip():
            return SearchResult(success=False, source="giustizia_amm", error_type="no_results",
                              results_text=(
                                  f"Testo del provvedimento {sede}/{nrg} non recuperabile: il portale "
                                  f"ha risposto con una pagina di errore. Verificare che sede, nrg e "
                                  f"nome_file provengano da una ricerca recente (i riferimenti presi "
                                  f"da risultati datati non sono più validi)."
                              ))
        return SearchResult(success=True, source="giustizia_amm", num_found=1,
                          results_text=format_full(title, text, sede, nrg))
    except Exception as exc:
        return SearchResult(success=False, source="giustizia_amm", error_type="source_down",
                          error_message=str(exc))


async def _giurisprudenza_amm_su_norma_impl(
    riferimento: str,
    sede: str = "",
    anno_da: str = "",
    max_risultati: int = 10,
) -> str:
    max_risultati = min(max_risultati, 50)

    try:
        # anno_da is applied below: the portal has no server-side year filter.
        docs = await search_provvedimenti(
            query=riferimento,
            sede=sede,
            rows=max_risultati,
        )
    except Exception as exc:
        return SearchResult(success=False, source="giustizia_amm", error_type="source_down", error_message=str(exc))

    if anno_da:
        docs = _filter_by_anno(docs, anno_da, since=True)

    if not docs:
        return SearchResult(success=False, source="giustizia_amm", error_type="no_results",
                          results_text=f"Nessun provvedimento amministrativo trovato per la norma: _{riferimento}_")

    lines = [f"**Provvedimenti TAR/CdS che citano**: _{riferimento}_\n"]
    for doc in docs:
        lines.append(format_result(doc))
        lines.append("")
    return SearchResult(success=True, source="giustizia_amm", num_found=len(docs), results_text="\n".join(lines))


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
        return SearchResult(success=False, source="giustizia_amm", error_type="source_down", error_message=str(exc))

    if not docs:
        return SearchResult(success=False, source="giustizia_amm", error_type="no_results",
                          results_text="Nessun provvedimento amministrativo recente trovato.")

    lines = ["**Ultimi provvedimenti TAR/Consiglio di Stato**\n"]
    for doc in docs:
        lines.append(format_result(doc))
        lines.append("")
    return SearchResult(success=True, source="giustizia_amm", num_found=len(docs), results_text="\n".join(lines))


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
            Valori disponibili: consiglio_di_stato, cgars, tar_lazio (Roma),
            tar_lazio_latina, tar_lombardia (Milano), tar_lombardia_brescia,
            tar_campania_napoli, tar_campania_salerno, tar_veneto, tar_piemonte,
            tar_emilia_romagna (Bologna), tar_emilia_romagna_parma, tar_toscana,
            tar_puglia_bari, tar_puglia_lecce, tar_sicilia_palermo, tar_sicilia_catania,
            tar_calabria_catanzaro, tar_calabria_reggio, tar_liguria, tar_sardegna,
            tar_friuli, tar_marche, tar_abruzzo_laquila, tar_abruzzo_pescara,
            tar_umbria, tar_molise, tar_basilicata, tar_trentino_trento,
            tar_trentino_bolzano, tar_valle_aosta
        tipo: Filtra per tipo (es. "sentenza", "ordinanza", "decreto", "parere",
            "adunanza_plenaria", "adunanza_generale")
        anno: Anno del provvedimento (es. "2024"). Il portale filtra per anno solo
            insieme a `numero`; da solo il filtro viene applicato sui risultati
            restituiti (ordinati dal più recente), quindi per anni remoti conviene
            indicare anche `numero` o restringere la query.
        numero: Numero del provvedimento (es. "1234"); con `anno` individua il
            provvedimento esatto (es. anno="2023" + numero="1234")
        max_risultati: Numero massimo di risultati (default 10, max 50)
    """
    result = await _cerca_giurisprudenza_amministrativa_impl(
        query=query, sede=sede, tipo=tipo, anno=anno, numero=numero, max_risultati=max_risultati,
    )
    return result.to_str() if isinstance(result, SearchResult) else result


@mcp.tool(tags={"giurisprudenza_amm", "normativa"})
async def leggi_provvedimento_amm(sede: str, nrg: str, nome_file: str) -> str:
    """Legge il testo completo di un provvedimento amministrativo (TAR/CdS) dal sottodominio mdp.

    Usare dopo cerca_giurisprudenza_amministrativa() o ultimi_provvedimenti_amm()
    per leggere il testo integrale. I parametri sede, nrg e nome_file sono riportati
    in ogni risultato della ricerca.
    Restituisce: testo integrale del provvedimento (motivazione + dispositivo).

    Args:
        sede: Codice sede restituito dalla ricerca (es. "cds", "tar_rm", "tar_mi").
            Sono accettati anche i vecchi codici ("CDS", "TARLAZ") e le chiavi
            estese ("consiglio_di_stato", "tar_lazio").
        nrg: Numero registro generale del ricorso (es. "202510565") — da risultati ricerca
        nome_file: Nome file sul sottodominio mdp (es. "202614035_01.html") — da risultati ricerca
    """
    result = await _leggi_provvedimento_amm_impl(sede, nrg, nome_file)
    return result.to_str() if isinstance(result, SearchResult) else result


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
        anno_da: Anno di partenza (es. "2022"); scarta i provvedimenti anteriori
            dai risultati restituiti, che sono ordinati dal più recente
        max_risultati: Numero massimo di risultati (default 10, max 50)
    """
    result = await _giurisprudenza_amm_su_norma_impl(
        riferimento=riferimento, sede=sede, anno_da=anno_da, max_risultati=max_risultati,
    )
    return result.to_str() if isinstance(result, SearchResult) else result


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
    result = await _ultimi_provvedimenti_amm_impl(
        sede=sede, tipo=tipo, max_risultati=max_risultati,
    )
    return result.to_str() if isinstance(result, SearchResult) else result

"""MCP tools for searching CeRDEF (Banca Dati Giurisprudenza Tributaria MEF).

TRIGGER: usare quando l'utente chiede di giurisprudenza tributaria, sentenze CTP/CTR/CGT,
Cassazione tributaria, IVA, IRES, IRPEF, accertamento, riscossione, contenzioso tributario.
"""

from datetime import timedelta

from src.server import mcp
from src.lib import _clock
from src.lib._result import SearchResult
from src.lib.cerdef.client import (
    ENTI,
    TIPO_ESTREMI,
    CerdefError,
    CerdefNonTrovato,
    EsitoRicerca,
    search_giurisprudenza,
    fetch_provvedimento,
    format_result,
    format_detail,
)

# CeRDEF refuses a search without criteria, and ordering a whole CGT group by date
# takes 20-100 s: "latest" means the latest decisions of the last twelve months.
_ULTIME_FINESTRA_GIORNI = 365


# ---------------------------------------------------------------------------
# Impl functions (testable without MCP context)
# ---------------------------------------------------------------------------


def _errore(exc: Exception) -> SearchResult:
    """The failure of a CeRDEF call, typed so that it can never read as "no results" (#46)."""
    if isinstance(exc, ValueError):
        return SearchResult(
            success=False, source="cerdef", error_type="bad_input", error_message=str(exc),
            results_text=f"**Errore**: parametri non validi per CeRDEF. {exc}",
        )
    if isinstance(exc, CerdefNonTrovato):
        # The portal does not know the id: neither an outage nor a failed read.
        return SearchResult(
            success=False, source="cerdef", error_type="not_found", error_message=str(exc),
            results_text=f"**Errore**: {exc}.",
        )
    error_type = "source_error" if isinstance(exc, CerdefError) else "source_down"
    return SearchResult(success=False, source="cerdef", error_type=error_type, error_message=str(exc))


def _descrivi_filtri(ente: str, tipo_provvedimento: str) -> str:
    parti = []
    if tipo_provvedimento:
        parti.append(TIPO_ESTREMI.get(tipo_provvedimento.strip().lower(), tipo_provvedimento))
    if ente:
        parti.append(ENTI.get(ente.strip().lower(), ente))
    return f" ({', '.join(parti)})" if parti else ""


def _esame_parziale(esito: EsitoRicerca) -> str:
    """Why fewer first-instance results than asked do not mean the portal has no more."""
    su = f" dei {esito.totale}" if esito.totale is not None else ""
    return (
        f"il filtro primo grado ha esaminato solo i primi {esito.esaminati}{su} provvedimenti delle "
        "Corti di giustizia tributaria trovati da CeRDEF: l'elenco non è stato esaminato per intero, "
        "restringere l'intervallo di date (data_da/data_a) per esaminarlo tutto"
    )


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
) -> SearchResult:
    max_risultati = min(max_risultati, 250)

    try:
        esito = await search_giurisprudenza(
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
        return _errore(exc)

    docs = esito.risultati
    filtri = _descrivi_filtri(ente, tipo_provvedimento)
    if not docs:
        if esito.troncato:
            testo = f"Nessun provvedimento di primo grado tra quelli esaminati per: _{query}_ — {_esame_parziale(esito)}."
        else:
            testo = f"Nessun provvedimento CeRDEF trovato per: _{query}_{filtri}."
        return SearchResult(success=False, source="cerdef", error_type="no_results", results_text=testo)

    lines = [f"**Trovati {len(docs)} provvedimenti CeRDEF per**: _{query}_{filtri}\n"]
    for doc in docs:
        lines.append(format_result(doc))
        lines.append("")
    if esito.troncato:
        lines.append(f"_Nota: {_esame_parziale(esito)}._")
    return SearchResult(success=True, source="cerdef", num_found=len(docs), results_text="\n".join(lines))


async def _cerdef_leggi_provvedimento_impl(guid: str) -> SearchResult:
    try:
        detail = await fetch_provvedimento(guid)
    except Exception as exc:
        return _errore(exc)
    return SearchResult(success=True, source="cerdef", num_found=1, results_text=format_detail(detail))


async def _ultime_sentenze_tributarie_impl(
    ente: str = "",
    tipo_provvedimento: str = "",
    max_risultati: int = 10,
) -> SearchResult:
    max_risultati = min(max_risultati, 250)
    fine = _clock.today()
    inizio = fine - timedelta(days=_ULTIME_FINESTRA_GIORNI)
    periodo = f"dal {inizio:%d/%m/%Y} al {fine:%d/%m/%Y}"

    try:
        esito = await search_giurisprudenza(
            tipo_estremi=tipo_provvedimento,
            ente=ente,
            data_da=f"{inizio:%d/%m/%Y}",
            data_a=f"{fine:%d/%m/%Y}",
            ordinamento="data",
            rows=max_risultati,
        )
    except Exception as exc:
        return _errore(exc)

    docs = esito.risultati
    filtri = _descrivi_filtri(ente, tipo_provvedimento)
    if not docs:
        if esito.troncato:
            testo = f"Nessun provvedimento di primo grado tra quelli esaminati, emessi {periodo} — {_esame_parziale(esito)}."
        else:
            testo = f"Nessun provvedimento tributario su CeRDEF emesso {periodo}{filtri}."
        return SearchResult(success=False, source="cerdef", error_type="no_results", results_text=testo)

    lines = [f"**Ultime sentenze tributarie CeRDEF** — provvedimenti emessi {periodo}{filtri}, dal più recente\n"]
    for doc in docs:
        lines.append(format_result(doc))
        lines.append("")
    if esito.troncato:
        lines.append(f"_Nota: {_esame_parziale(esito)}._")
    return SearchResult(success=True, source="cerdef", num_found=len(docs), results_text="\n".join(lines))


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
        ente: Filtra per ente (es. "corte_suprema", "cgt_primo_grado", "cgt_secondo_grado");
            con "cgt_primo_grado" indicare anche data_da (il portale non ha un filtro
            per il solo primo grado: senza limite di date la ricerca e' troppo lenta)
        data_da: Data inizio in formato DD/MM/YYYY (es. "01/01/2023")
        data_a: Data fine in formato DD/MM/YYYY (es. "31/12/2024")
        numero: Numero specifico del provvedimento (solo cifre)
        criterio: Criterio di ricerca ("tutti", "almeno_uno", "frase_esatta",
            "parole_adiacenti", "operatori_logici")
        ordinamento: Ordinamento risultati ("rilevanza" o "data")
        max_risultati: Numero massimo di risultati (default 10, max 250)
    """
    result = await _cerca_giurisprudenza_tributaria_impl(
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
    return result.to_str() if isinstance(result, SearchResult) else result


@mcp.tool(tags={"giurisprudenza", "fiscale"})
async def cerdef_leggi_provvedimento(guid: str) -> str:
    """Legge il testo completo di un provvedimento CeRDEF tramite GUID.

    Usare dopo cerca_giurisprudenza_tributaria() o ultime_sentenze_tributarie()
    per leggere massima e testo integrale del provvedimento.
    Il GUID e riportato in ogni risultato della ricerca. Un GUID inesistente o
    malformato e' segnalato come "provvedimento non trovato o GUID non valido",
    non come fonte irraggiungibile. Il testo integrale e' troncato a 25000 caratteri
    (la nota indica la lunghezza totale).
    Restituisce: massima e testo integrale del provvedimento tributario.

    Args:
        guid: GUID del provvedimento, tra graffe come lo riporta la ricerca
            (es. "{B0F76E21-B5FA-4415-9D1D-44FF7B5741C1}")
    """
    result = await _cerdef_leggi_provvedimento_impl(guid)
    return result.to_str() if isinstance(result, SearchResult) else result


@mcp.tool(tags={"giurisprudenza", "fiscale"})
async def ultime_sentenze_tributarie(
    ente: str = "",
    tipo_provvedimento: str = "",
    max_risultati: int = 10,
) -> str:
    """Ultime sentenze e provvedimenti tributari da CeRDEF (MEF), con filtro opzionale.

    Copre i provvedimenti emessi negli ultimi 12 mesi, dal piu' recente (per data di
    emissione: CeRDEF non espone la data di pubblicazione, e le decisioni delle CGT
    possono arrivarvi con mesi di ritardo). Se CeRDEF risponde in modo anomalo il tool
    restituisce un **Errore** esplicito, mai una lista vuota: "Nessun provvedimento"
    significa che il portale non ne ha nel periodo.
    Dopo questo tool: cerdef_leggi_provvedimento() con il GUID per il testo completo.
    Restituisce: lista cronologica delle ultime sentenze tributarie con estremi, ente e data.

    Args:
        ente: Filtra per ente (es. "corte_suprema", "cgt_primo_grado", "cgt_secondo_grado")
        tipo_provvedimento: Filtra per tipo (es. "sentenza", "ordinanza", "decreto")
        max_risultati: Numero massimo di risultati (default 10, max 250)
    """
    result = await _ultime_sentenze_tributarie_impl(
        ente=ente,
        tipo_provvedimento=tipo_provvedimento,
        max_risultati=max_risultati,
    )
    return result.to_str() if isinstance(result, SearchResult) else result

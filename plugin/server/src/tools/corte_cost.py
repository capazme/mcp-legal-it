"""MCP tools for Corte Costituzionale (Italian Constitutional Court) case law.

TRIGGER: usare quando l'utente chiede sentenze o ordinanze della Corte
Costituzionale, pronunce di legittimità costituzionale, illegittimità
costituzionale, giudizio in via incidentale o principale, ECLI:IT:COST,
parametri costituzionali, norme dichiarate incostituzionali.

Fonte dati: open-data ufficiale dati.cortecostituzionale.it (dump JSON per
decennio, con cache locale di 7 giorni). Il sito www.cortecostituzionale.it
è protetto e non viene mai interrogato.
"""

from datetime import date

from src.lib._result import SearchResult
from src.server import mcp
from src.lib.corte_cost.client import (
    TIPOLOGIE,
    fetch_pronuncia,
    format_full,
    format_massima_hit,
    format_result,
    pronunce_su_norma,
    search_pronunce,
    ultime_pronunce,
)

_SOURCE = "corte_cost"


# ---------------------------------------------------------------------------
# Impl functions (testable without MCP context)
# ---------------------------------------------------------------------------

async def _cerca_pronuncia_costituzionale_impl(
    query: str,
    tipo: str = "",
    anno_da: int = 0,
    anno_a: int = 0,
    max_risultati: int = 10,
) -> SearchResult:
    max_risultati = min(max_risultati, 50)
    terms = [t.strip().lower() for t in query.split(",") if t.strip()] if query else []
    tipo_code = TIPOLOGIE.get(tipo, "")
    current_year = date.today().year

    try:
        docs = await search_pronunce(
            terms=terms,
            tipo_code=tipo_code,
            year_from=anno_da,
            year_to=anno_a,
            limit=max_risultati,
            current_year=current_year,
        )
    except Exception as exc:
        return SearchResult(
            success=False, source=_SOURCE, error_type="source_down",
            error_message=str(exc),
            results_text=f"Errore nel recupero dei dati Corte Costituzionale: {exc}",
        )

    if not docs:
        q_desc = query or tipo or "recenti"
        scope = "" if (anno_da or anno_a) else f" (anno {current_year}; specificare anno_da/anno_a per cercare in altri anni)"
        return SearchResult(
            success=False, source=_SOURCE, error_type="no_results",
            results_text=f"Nessuna pronuncia costituzionale trovata per: _{q_desc}_{scope}",
        )

    lines = [f"**Trovate {len(docs)} pronunce della Corte Costituzionale**\n"]
    for doc in docs:
        lines.append(format_result(doc))
        lines.append("")
    return SearchResult(success=True, source=_SOURCE, num_found=len(docs), results_text="\n".join(lines))


async def _leggi_pronuncia_costituzionale_impl(numero: int, anno: int) -> SearchResult:
    try:
        doc = await fetch_pronuncia(numero, anno)
    except Exception as exc:
        return SearchResult(
            success=False, source=_SOURCE, error_type="source_down",
            error_message=str(exc),
            results_text=f"Errore nel recupero della pronuncia {numero}/{anno}: {exc}",
        )

    if doc is None:
        return SearchResult(
            success=False, source=_SOURCE, error_type="no_results",
            results_text=f"Pronuncia n. {numero}/{anno} non trovata nell'archivio Corte Costituzionale.",
        )

    return SearchResult(success=True, source=_SOURCE, num_found=1, results_text=format_full(doc))


async def _pronunce_cost_su_norma_impl(
    riferimento: str,
    anno_da: int = 0,
    anno_a: int = 0,
    max_risultati: int = 10,
) -> SearchResult:
    max_risultati = min(max_risultati, 50)

    try:
        hits = await pronunce_su_norma(
            riferimento=riferimento,
            year_from=anno_da,
            year_to=anno_a,
            limit=max_risultati,
        )
    except Exception as exc:
        return SearchResult(
            success=False, source=_SOURCE, error_type="source_down",
            error_message=str(exc),
            results_text=f"Errore nel recupero delle massime Corte Costituzionale: {exc}",
        )

    if not hits:
        return SearchResult(
            success=False, source=_SOURCE, error_type="no_results",
            results_text=(
                f"Nessuna pronuncia costituzionale trovata che invochi come parametro: _{riferimento}_. "
                "Indicare articolo e/o numero dell'atto (es. 'art. 23 legge 87/1953')."
            ),
        )

    lines = [f"**Pronunce costituzionali che invocano**: _{riferimento}_\n"]
    for numero, anno, massima in hits:
        lines.append(format_massima_hit(numero, anno, massima))
        lines.append("")
    return SearchResult(success=True, source=_SOURCE, num_found=len(hits), results_text="\n".join(lines))


async def _ultime_pronunce_cost_impl(
    tipo: str = "",
    max_risultati: int = 10,
) -> SearchResult:
    max_risultati = min(max_risultati, 50)
    tipo_code = TIPOLOGIE.get(tipo, "")
    current_year = date.today().year

    try:
        docs = await ultime_pronunce(
            tipo_code=tipo_code,
            current_year=current_year,
            limit=max_risultati,
        )
    except Exception as exc:
        return SearchResult(
            success=False, source=_SOURCE, error_type="source_down",
            error_message=str(exc),
            results_text=f"Errore nel recupero delle ultime pronunce Corte Costituzionale: {exc}",
        )

    if not docs:
        return SearchResult(
            success=False, source=_SOURCE, error_type="no_results",
            results_text=f"Nessuna pronuncia costituzionale depositata trovata per l'anno {current_year}.",
        )

    lines = [f"**Ultime pronunce della Corte Costituzionale ({current_year})**\n"]
    for doc in docs:
        lines.append(format_result(doc))
        lines.append("")
    return SearchResult(success=True, source=_SOURCE, num_found=len(docs), results_text="\n".join(lines))


# ---------------------------------------------------------------------------
# MCP tool wrappers
# ---------------------------------------------------------------------------

@mcp.tool(tags={"giurisprudenza", "costituzionale"})
async def cerca_pronuncia_costituzionale(
    query: str,
    tipo: str = "",
    anno_da: int = 0,
    anno_a: int = 0,
    max_risultati: int = 10,
) -> str:
    """Cerca sentenze e ordinanze della Corte Costituzionale per parole chiave.

    USARE quando si parla di: pronunce Corte Costituzionale, sentenze/ordinanze
    costituzionali, illegittimità costituzionale, giudizio di legittimità,
    questione di costituzionalità. Dopo aver trovato una pronuncia, usare
    leggi_pronuncia_costituzionale(numero, anno) per il testo completo.
    Restituisce: lista pronunce con numero, anno, ECLI, date e oggetto.

    Nota: senza anno_da/anno_a la ricerca copre solo l'anno corrente (i dati
    sono organizzati per anno). Indicare un intervallo per cercare nello storico.

    Args:
        query: Parole chiave da cercare nel testo (virgola-separate per più
            termini in AND, es. "pensioni, perequazione" o "ne bis in idem")
        tipo: Filtra per tipo ("sentenza" o "ordinanza") — default entrambi
        anno_da: Anno di inizio (es. 2020) — 0 = solo anno corrente
        anno_a: Anno di fine (es. 2024) — 0 = come anno_da
        max_risultati: Numero massimo di risultati (default 10, max 50)
    """
    result = await _cerca_pronuncia_costituzionale_impl(
        query=query, tipo=tipo, anno_da=anno_da, anno_a=anno_a, max_risultati=max_risultati,
    )
    return result.to_str() if isinstance(result, SearchResult) else result


@mcp.tool(tags={"giurisprudenza", "costituzionale"})
async def leggi_pronuncia_costituzionale(numero: int, anno: int) -> str:
    """Legge il testo completo di una pronuncia della Corte Costituzionale.

    Usare quando si conosce già numero e anno (es. "sentenza 1/2024"), oppure
    dopo cerca_pronuncia_costituzionale(). Restituisce epigrafe, testo e
    dispositivo (max 25000 caratteri) dall'archivio open-data ufficiale.

    Args:
        numero: Numero della pronuncia (es. 1, 162, 238)
        anno: Anno della pronuncia (es. 2024)
    """
    result = await _leggi_pronuncia_costituzionale_impl(numero, anno)
    return result.to_str() if isinstance(result, SearchResult) else result


@mcp.tool(tags={"giurisprudenza", "costituzionale"})
async def pronunce_cost_su_norma(
    riferimento: str,
    anno_da: int = 0,
    anno_a: int = 0,
    max_risultati: int = 10,
) -> str:
    """Cerca pronunce costituzionali che invocano una norma come parametro.

    Usa l'archivio delle massime, dove ogni massima elenca le norme invocate
    come parametro di costituzionalità. Indicare l'articolo e/o il numero
    dell'atto. Dopo aver trovato una pronuncia, usare
    leggi_pronuncia_costituzionale(numero, anno) per il testo completo.
    Restituisce: massime con titolo, testo e parametri normativi.

    Args:
        riferimento: Norma invocata come parametro (es. "art. 23 legge 87/1953",
            "art. 3 Costituzione", "art. 117"). Si estraggono articolo e numero atto.
        anno_da: Anno di inizio (default copre l'intero archivio massime)
        anno_a: Anno di fine
        max_risultati: Numero massimo di risultati (default 10, max 50)
    """
    result = await _pronunce_cost_su_norma_impl(
        riferimento=riferimento, anno_da=anno_da, anno_a=anno_a, max_risultati=max_risultati,
    )
    return result.to_str() if isinstance(result, SearchResult) else result


@mcp.tool(tags={"giurisprudenza", "costituzionale"})
async def ultime_pronunce_cost(tipo: str = "", max_risultati: int = 10) -> str:
    """Ultime pronunce depositate dalla Corte Costituzionale (anno corrente).

    Restituisce le decisioni più recenti per data di deposito. Dopo questo tool
    usare leggi_pronuncia_costituzionale(numero, anno) per il testo completo.

    Args:
        tipo: Filtra per tipo ("sentenza" o "ordinanza") — default entrambi
        max_risultati: Numero massimo di risultati (default 10, max 50)
    """
    result = await _ultime_pronunce_cost_impl(tipo=tipo, max_risultati=max_risultati)
    return result.to_str() if isinstance(result, SearchResult) else result

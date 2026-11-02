"""MCP tools for searching CONSOB (Commissione Nazionale per le Societa e la Borsa) documents.

TRIGGER: usare quando l'utente chiede di delibere/provvedimenti CONSOB, sanzioni mercati
finanziari, abusi di mercato, intermediari, emittenti, OPA, crowdfunding, cripto-attivita.
"""

from typing import Annotated, Literal

from pydantic import BeforeValidator

from mcp_legal_it.server import mcp
from mcp_legal_it.lib._paging import invalid_start
from mcp_legal_it.lib.consob.client import (
    ARGOMENTI,
    TIPOLOGIE,
    fetch_delibera,
    format_full,
    format_result,
    is_delibera,
    search_delibere,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normalize_key(value):
    """"Intermediari", " delibere", "abusi di mercato" -> the canonical key (as before the enum)."""
    return value.strip().lower().replace(" ", "_") if isinstance(value, str) else value


# The valid filter keys, declared as an enum in the tools' input schema so a model cannot send
# a key the portal does not know (LI-062). Case and spaces are normalised before the check, as
# the tools did before the enum. The lists must stay equal to the client's tables:
# tests/unit/test_consob.py pins the two together.
TipologiaConsob = Annotated[
    Literal[
        "", "delibere", "comunicazioni", "provvedimenti_urgenti", "altre_decisioni", "opa",
        "appendice", "tutti",
    ],
    BeforeValidator(_normalize_key),
]
ArgomentoConsob = Annotated[
    Literal[
        "", "abusi_di_mercato", "intermediari", "emittenti", "mercati", "offerte_acquisto",
        "offerte_vendita", "gestione_collettiva", "servizi_investimento", "cripto_attivita",
        "crowdfunding",
    ],
    BeforeValidator(_normalize_key),
]


def _resolve_consob_filters(
    tipologia: str, argomento: str,
) -> tuple[str, str, str]:
    """Resolve the tipologia/argomento keys to Liferay values.

    Returns ``(tipologia_val, argomento_id, error)``. An unknown key is refused with an
    error instead of being forwarded to the portal, where it would run as a meaningless
    filter and come back as "no delibera".
    """
    tip_key = _normalize_key(tipologia) if tipologia else ""
    arg_key = _normalize_key(argomento) if argomento else ""
    if tip_key and tip_key not in TIPOLOGIE:
        return "", "", (
            f"Chiave non valida per tipologia: «{tipologia}». "
            f"Valori ammessi: {', '.join(TIPOLOGIE)}."
        )
    if arg_key and arg_key not in ARGOMENTI:
        return "", "", (
            f"Chiave non valida per argomento: «{argomento}». "
            f"Valori ammessi: {', '.join(ARGOMENTI)}."
        )
    return TIPOLOGIE.get(tip_key, ""), ARGOMENTI.get(arg_key, ""), ""


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
    max_risultati = max(1, min(max_risultati, 100))

    tipologia_val, argomento_id, error = _resolve_consob_filters(tipologia, argomento)
    if error:
        return error

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

    # The Bollettino also lists comunicazioni, richiami di attenzione and avvisi: say so
    # instead of calling every hit a "delibera".
    if all(is_delibera(d) for d in docs):
        lines = [f"**Trovate {len(docs)} delibere CONSOB per**: _{query}_\n"]
    else:
        lines = [f"**Trovati {len(docs)} documenti del Bollettino CONSOB per**: _{query}_\n"]
    for doc in docs:
        lines.append(format_result(doc))
        lines.append("")
    return "\n".join(lines)


async def _leggi_delibera_consob_impl(numero: str, da_carattere: int = 1) -> str:
    if (error := invalid_start(da_carattere)) is not None:
        return f"Errore nel recupero della delibera CONSOB n. {numero}: {error}"
    try:
        title, text = await fetch_delibera(numero)
        return format_full(title, text, numero, da_carattere)
    except Exception as exc:
        return f"Errore nel recupero della delibera CONSOB n. {numero}: {exc}"


async def _ultime_delibere_consob_impl(
    tipologia: str = "",
    argomento: str = "",
    max_risultati: int = 10,
) -> str:
    max_risultati = max(1, min(max_risultati, 100))

    tipologia_val, argomento_id, error = _resolve_consob_filters(tipologia, argomento)
    if error:
        return error

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

    if all(is_delibera(d) for d in docs):
        lines = ["**Ultime delibere CONSOB**\n"]
    else:
        lines = ["**Ultimi documenti del Bollettino CONSOB**\n"]
    for doc in docs:
        lines.append(format_result(doc))
        lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# MCP tool wrappers
# ---------------------------------------------------------------------------

@mcp.tool(tags={"autorita", "consob"}, output_schema=None)
async def cerca_delibere_consob(
    query: str,
    tipologia: TipologiaConsob = "",
    argomento: ArgomentoConsob = "",
    data_da: str = "",
    data_a: str = "",
    max_risultati: int = 20,
) -> str:
    """Cerca delibere e provvedimenti CONSOB nel bollettino ufficiale.

    USARE quando si parla di: delibere CONSOB, sanzioni mercati finanziari, abusi di mercato,
    intermediari, emittenti, OPA, crowdfunding, cripto-attivita, regolamenti CONSOB.
    Dopo aver trovato una delibera, usare leggi_delibera_consob() per il testo completo.
    Restituisce: lista di documenti del Bollettino con tipo effettivo (Delibera, Comunicazione,
    Richiamo di attenzione, Avviso...), numero completo (es. "13/25"), titolo, data e link
    alla pagina reale del documento. Solo le delibere si leggono con leggi_delibera_consob():
    per gli altri documenti il testo e' alla pagina del link.
    Avvertenza: il filtro argomento segue la tassonomia del Bollettino, che non e' applicata in modo
    uniforme (es. "abusi_di_mercato" non e' assegnato ai documenti dopo il 2017): per i temi recenti
    usare la ricerca testuale in query e i filtri di data.

    Args:
        query: Testo da cercare (es. "abusi di mercato", "sanzione intermediario", "OPA")
        tipologia: Filtra per tipo di documento (vuoto = nessun filtro)
        argomento: Filtra per argomento del Bollettino (vuoto = nessun filtro)
        data_da: Data inizio in formato YYYY-MM-DD (es. "2023-01-01")
        data_a: Data fine in formato YYYY-MM-DD (es. "2024-12-31")
        max_risultati: Numero massimo di risultati (default 20, max 100)
    """
    return await _cerca_delibere_consob_impl(
        query=query, tipologia=tipologia, argomento=argomento,
        data_da=data_da, data_a=data_a, max_risultati=max_risultati,
    )


@mcp.tool(tags={"autorita", "consob"}, output_schema=None)
async def leggi_delibera_consob(numero: str, da_carattere: int = 1) -> str:
    """Legge il testo completo di una delibera CONSOB tramite numero.

    Usare dopo cerca_delibere_consob() o ultime_delibere_consob() per leggere
    il testo completo. Il numero delibera e riportato in ogni risultato della ricerca.
    Restituisce: testo della delibera con titolo e link alla fonte CONSOB. Oltre 8000 caratteri
    il testo e' troncato; la parte omessa si legge ripetendo la chiamata con il da_carattere
    indicato nella nota. Le posizioni contano i caratteri del testo della pagina (senza titolo e link).
    Con da_carattere > 1 restituisce gli 8000 caratteri che partono da quella posizione.

    Args:
        numero: Numero della delibera (es. "23257", "23256-1")
        da_carattere: Carattere da cui leggere (1 = inizio, default). Se il testo supera il limite,
            la nota indica il valore con cui ripetere la chiamata per leggere il seguito
    """
    return await _leggi_delibera_consob_impl(numero, da_carattere)


@mcp.tool(tags={"autorita", "consob"}, output_schema=None)
async def ultime_delibere_consob(
    tipologia: TipologiaConsob = "",
    argomento: ArgomentoConsob = "",
    max_risultati: int = 10,
) -> str:
    """Ultime delibere e provvedimenti pubblicati dalla CONSOB, con filtro opzionale.

    Dopo questo tool: leggi_delibera_consob() con il numero per il testo completo.
    Restituisce: lista dei documenti piu' recenti del Bollettino, in ordine di data di pubblicazione
    decrescente (non di data dell'atto), con tipo effettivo (Delibera, Comunicazione, Richiamo di
    attenzione, Avviso...), numero completo, titolo, date e link alla pagina reale del documento.

    Args:
        tipologia: Filtra per tipo di documento (vuoto = nessun filtro)
        argomento: Filtra per argomento del Bollettino (vuoto = nessun filtro)
        max_risultati: Numero massimo di risultati (default 10, max 100)
    """
    return await _ultime_delibere_consob_impl(
        tipologia=tipologia, argomento=argomento, max_risultati=max_risultati,
    )

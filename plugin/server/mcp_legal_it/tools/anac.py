"""MCP tools for ANAC (Autorità Nazionale Anticorruzione) acts.

TRIGGER: usare quando l'utente chiede di delibere ANAC, pareri di precontenzioso, pareri sulla
normativa, linee guida, bandi tipo, comunicati del Presidente ANAC, vigilanza su contratti
pubblici, affidamenti diretti, proroghe tecniche, rinnovi, conflitto di interessi,
inconferibilità e incompatibilità, whistleblowing, trasparenza amministrativa.
"""

from mcp_legal_it.server import mcp
from mcp_legal_it.lib._result import SearchResult
from mcp_legal_it.lib.anac.client import (
    TIPOLOGIE,
    AnacNonTrovato,
    AnacPaginaInattesa,
    fetch_atto,
    find_atto,
    format_atto,
    format_result,
    search_atti,
)

_SOURCE = "anac"


def _errore(exc: Exception) -> SearchResult:
    """A failure as the right kind of answer: bad input, nothing found, unreadable page or source down."""
    if isinstance(exc, ValueError):
        return SearchResult(success=False, source=_SOURCE, error_type="bad_input",
                            results_text=f"**Errore**: {exc}")
    if isinstance(exc, AnacNonTrovato):
        return SearchResult(success=False, source=_SOURCE, error_type="no_results",
                            results_text=f"Nessun risultato: {exc}.")
    if isinstance(exc, AnacPaginaInattesa):
        return SearchResult(success=False, source=_SOURCE, error_type="source_error", error_message=str(exc))
    return SearchResult(success=False, source=_SOURCE, error_type="source_down", error_message=str(exc))


def _elenco(intestazione: str, risultati, totale: int) -> SearchResult:
    header = intestazione
    if totale > len(risultati):
        header += f" (mostrati {len(risultati)} su {totale} indicati dal portale, dal più recente)"
    lines = [header + "\n"]
    for r in risultati:
        lines += [format_result(r), ""]
    lines.append("*Dopo la ricerca: leggi_atto_anac() con il riferimento indicato per la scheda completa.*")
    return SearchResult(success=True, source=_SOURCE, num_found=len(risultati), results_text="\n".join(lines))


# ---------------------------------------------------------------------------
# Impl functions (testable without MCP context)
# ---------------------------------------------------------------------------

async def _cerca_atti_anac_impl(
    query: str, tipologia: str = "", max_risultati: int = 10, pagina: int = 1,
) -> SearchResult:
    max_risultati = max(1, min(max_risultati, 50))
    if not isinstance(pagina, int) or pagina < 1:
        return _errore(ValueError("pagina deve essere un intero maggiore o uguale a 1"))
    try:
        risultati, totale = await search_atti(query, tipologia, max_risultati, pagina)
    except Exception as exc:  # noqa: BLE001 - errors are answers
        return _errore(exc)
    if not risultati:
        return SearchResult(success=False, source=_SOURCE, error_type="no_results",
                            results_text=f"Nessun atto ANAC trovato per: _{query}_")
    return _elenco(f"**Trovati {len(risultati)} atti ANAC per**: _{query}_", risultati, totale)


async def _leggi_atto_anac_impl(
    riferimento: str = "", tipologia: str = "", numero: str = "", anno: str = "",
) -> SearchResult:
    try:
        if not riferimento:
            if not (numero and anno):
                raise ValueError("indicare il riferimento restituito dalla ricerca, oppure tipologia, numero e anno")
            riferimento = (await find_atto(tipologia, numero, anno)).path
        atto = await fetch_atto(riferimento)
    except Exception as exc:  # noqa: BLE001 - errors are answers
        return _errore(exc)
    return SearchResult(success=True, source=_SOURCE, num_found=1, results_text=format_atto(atto))


async def _ultimi_atti_anac_impl(tipologia: str = "", max_risultati: int = 10) -> SearchResult:
    max_risultati = max(1, min(max_risultati, 50))
    try:
        risultati, totale = await search_atti("", tipologia, max_risultati)
    except Exception as exc:  # noqa: BLE001 - errors are answers
        return _errore(exc)
    if not risultati:
        return SearchResult(success=False, source=_SOURCE, error_type="no_results",
                            results_text="Nessun atto ANAC recente trovato.")
    etichetta = f" ({tipologia})" if tipologia else " (tutte le tipologie)"
    return _elenco(f"**Ultimi atti ANAC**{etichetta}", risultati, totale)


# ---------------------------------------------------------------------------
# MCP tool wrappers
# ---------------------------------------------------------------------------


@mcp.tool(tags={"autorita", "anac"})
async def cerca_atti_anac(
    query: str,
    tipologia: str = "",
    max_risultati: int = 10,
    pagina: int = 1,
) -> str:
    """Cerca delibere, pareri, linee guida e altri atti dell'ANAC (Autorità Nazionale Anticorruzione).

    USARE quando si parla di: contratti pubblici (affidamenti, proroghe tecniche, rinnovi,
    in house, varianti), pareri di precontenzioso, vigilanza ANAC, anticorruzione,
    inconferibilità e incompatibilità, conflitto di interessi, whistleblowing, trasparenza.
    Dopo la ricerca: leggi_atto_anac() con il riferimento di ogni risultato.
    Restituisce: atti dal più recente, con titolo (tipo, numero e data), data, classificazione
    (argomento, categoria, tipologia), oggetto e riferimento per la lettura; il conteggio indica
    anche il totale riportato dal portale.
    La ricerca del portale cerca le parole nelle pagine e nei documenti (anche negli allegati).
    Vigenza: fonte ufficiale www.anticorruzione.it, letta al momento della chiamata.
    Precisione: INDICATIVO (ricerca testuale del portale, una pagina di risultati).

    Args:
        query: Testo da cercare (es. "rinnovo tacito", "proroga tecnica", "affidamento in house")
        tipologia: Filtra per tipo di atto. Valori: delibere, pareri_precontenzioso,
            pareri_normativa, linee_guida, bandi_tipo, comunicati_presidente, atti_presidente,
            regolamenti, provvedimenti_ordine, segnalazioni, protocolli_vigilanza,
            protocolli_intesa, audizioni, relazioni_annuali, relazioni_vigilanza
            (accettati anche "delibera", "precontenzioso", "parere sulla normativa", ...)
        max_risultati: Numero massimo di risultati (default 10, max 50)
        pagina: Pagina dei risultati (1 = prima, default)
    """
    result = await _cerca_atti_anac_impl(query, tipologia, max_risultati, pagina)
    return result.to_str()


@mcp.tool(tags={"autorita", "anac"})
async def leggi_atto_anac(
    riferimento: str = "",
    tipologia: str = "",
    numero: str = "",
    anno: str = "",
) -> str:
    """Legge la scheda di un atto ANAC: estremi, oggetto, riferimenti normativi, parole chiave e PDF.

    Usare dopo cerca_atti_anac() o ultimi_atti_anac() con il riferimento del risultato, oppure
    direttamente con tipologia, numero e anno (es. tipologia="delibere", numero="444",
    anno="2025"): l'atto viene cercato sul portale e letto.
    Restituisce: titolo, data, anno, argomento, categoria, tipologia, destinatari, oggetto,
    riferimenti normativi, parole chiave e link al PDF ufficiale. NON restituisce il testo
    integrale, che ANAC pubblica solo nel PDF: il link al PDF è nella risposta. La scheda non
    indica se l'atto è stato superato o annullato in sede giurisdizionale.
    Un atto inesistente è un errore esplicito ("nessun atto ANAC ..."), mai una scheda vuota.
    Vigenza: fonte ufficiale www.anticorruzione.it, letta al momento della chiamata.
    Precisione: ESATTO (scheda ufficiale dell'atto).

    Args:
        riferimento: Percorso restituito dalla ricerca (es. "/-/delibera-n.-444-del-11-novembre-2025")
            o URL completo su www.anticorruzione.it
        tipologia: Tipo di atto, con numero e anno (es. "delibere", "pareri_precontenzioso")
        numero: Numero dell'atto (es. "444")
        anno: Anno dell'atto (es. "2025")
    """
    result = await _leggi_atto_anac_impl(riferimento, tipologia, numero, anno)
    return result.to_str()


@mcp.tool(tags={"autorita", "anac"})
async def ultimi_atti_anac(tipologia: str = "", max_risultati: int = 10) -> str:
    """Ultimi atti pubblicati dall'ANAC, dal più recente, con filtro opzionale per tipologia.

    Senza tipologia elenca ogni tipo di atto insieme (delibere, pareri, comunicati, ...).
    Dopo questo tool: leggi_atto_anac() con il riferimento di ogni risultato.
    Restituisce: atti con titolo (tipo, numero e data), classificazione, oggetto e riferimento.
    Vigenza: fonte ufficiale www.anticorruzione.it, letta al momento della chiamata.
    Precisione: INDICATIVO (ordine per data del portale).

    Args:
        tipologia: Filtra per tipo (es. "delibere", "pareri_precontenzioso", "pareri_normativa",
            "linee_guida", "comunicati_presidente")
        max_risultati: Numero massimo di risultati (default 10, max 50)
    """
    result = await _ultimi_atti_anac_impl(tipologia, max_risultati)
    return result.to_str()

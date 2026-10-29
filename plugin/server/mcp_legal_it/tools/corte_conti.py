"""MCP tools for the Corte dei conti: deliberazioni and pareri of the control sections.

TRIGGER: usare quando l'utente chiede di deliberazioni o pareri della Corte dei conti in sede di
controllo: pareri delle sezioni regionali di controllo agli enti locali, controllo preventivo di
legittimità (visto e registrazione), controllo sui bilanci e rendiconti degli enti, contratti
pubblici e spesa di personale degli enti, sezione delle autonomie, sezioni riunite in sede di
controllo.
"""

from mcp_legal_it.server import mcp
from mcp_legal_it.lib._paging import invalid_start
from mcp_legal_it.lib._result import SearchResult
from mcp_legal_it.lib.corte_conti.client import (
    MAX_DOCUMENTI,
    CorteContiErrore,
    CorteContiNonRaggiungibile,
    CorteContiNonTrovato,
    fetch_deliberazione,
    format_deliberazione,
    format_result,
    search_deliberazioni,
)

_SOURCE = "Corte dei conti"


def _errore(exc: Exception) -> SearchResult:
    """A failure as the right kind of answer: bad input, nothing found, unusable answer or source down.

    Only this module's own messages reach the answer: never a request, its headers or the credentials.
    """
    if isinstance(exc, ValueError):
        return SearchResult(success=False, source=_SOURCE, error_type="bad_input",
                            results_text=f"**Errore**: {exc}")
    if isinstance(exc, CorteContiNonTrovato):
        return SearchResult(success=False, source=_SOURCE, error_type="no_results",
                            results_text=f"Nessun risultato: {exc}.")
    if isinstance(exc, CorteContiNonRaggiungibile):
        return SearchResult(success=False, source=_SOURCE, error_type="source_down", error_message=str(exc))
    if isinstance(exc, CorteContiErrore):
        return SearchResult(success=False, source=_SOURCE, error_type="source_error", error_message=str(exc))
    return SearchResult(success=False, source=_SOURCE, error_type="source_down", error_message=type(exc).__name__)


def _elenco(intestazione: str, risultati, totale: int) -> SearchResult:
    header = intestazione
    if totale > len(risultati):
        header += (f" (mostrate {len(risultati)} su {totale}: il servizio pubblico della Corte ne restituisce "
                   f"al più {MAX_DOCUMENTI} per ricerca; per vederne altre restringere con parole più precise, "
                   "anno o sezione)")
    lines = [header + "\n"]
    for r in risultati:
        lines += [format_result(r), ""]
    lines.append("*Dopo la ricerca: leggi_deliberazione_corte_conti() con l'identificativo indicato "
                 "per testo integrale e scheda.*")
    return SearchResult(success=True, source=_SOURCE, num_found=len(risultati), results_text="\n".join(lines))


# ---------------------------------------------------------------------------
# Impl functions (testable without MCP context)
# ---------------------------------------------------------------------------


async def _cerca_deliberazioni_corte_conti_impl(
    query: str = "", sezione: str = "", anno: str = "", numero: str = "", max_risultati: int = MAX_DOCUMENTI,
) -> SearchResult:
    if not (query or "").strip() and not (numero or "").strip():
        return _errore(ValueError("indicare le parole da cercare oppure il numero della deliberazione "
                                  "(per le più recenti: ultime_deliberazioni_corte_conti)"))
    try:
        n = max(1, min(int(max_risultati), MAX_DOCUMENTI))
        risultati, totale = await search_deliberazioni(query, numero=numero, anno=anno, sezione=sezione, n=n)
    except Exception as exc:  # noqa: BLE001 - errors are answers
        return _errore(exc)
    criterio = query.strip() or f"n. {numero}" + (f"/{anno}" if anno else "")
    if not risultati:
        return SearchResult(success=False, source=_SOURCE, error_type="no_results",
                            results_text=f"Nessuna deliberazione della Corte dei conti trovata per: _{criterio}_")
    return _elenco(f"**Trovate {totale} deliberazioni della Corte dei conti per**: _{criterio}_", risultati, totale)


async def _leggi_deliberazione_corte_conti_impl(
    id_deliberazione: str = "", numero: str = "", anno: str = "", sezione: str = "", da_carattere: int = 1,
) -> SearchResult:
    if (error := invalid_start(da_carattere)) is not None:
        return SearchResult(success=False, source=_SOURCE, error_type="bad_input", results_text=error)
    try:
        if id_deliberazione.strip():
            d = await fetch_deliberazione(id_deliberazione)
        else:
            if not (numero.strip() and anno.strip()):
                raise ValueError("indicare l'identificativo restituito dalla ricerca (es. SRCCAM/29/2025/PREV), "
                                 "oppure numero e anno, con la sezione se il numero si ripete")
            risultati, totale = await search_deliberazioni(numero=numero, anno=anno, sezione=sezione)
            if not risultati:
                raise CorteContiNonTrovato(f"nessuna deliberazione n. {numero}/{anno}"
                                           + (f" della sezione {sezione}" if sezione else ""))
            if totale > 1:
                return _elenco(
                    f"**{totale} deliberazioni hanno il n. {numero}/{anno}**: indicare la sezione, oppure "
                    "leggere quella giusta con il suo identificativo", risultati, totale)
            d = await fetch_deliberazione(risultati[0].id_locale, chiave=risultati[0].chiave)
    except Exception as exc:  # noqa: BLE001 - errors are answers
        return _errore(exc)
    return SearchResult(success=True, source=_SOURCE, num_found=1, results_text=format_deliberazione(d, da_carattere))


async def _ultime_deliberazioni_corte_conti_impl(sezione: str = "", max_risultati: int = MAX_DOCUMENTI) -> SearchResult:
    try:
        n = max(1, min(int(max_risultati), MAX_DOCUMENTI))
        risultati, totale = await search_deliberazioni(sezione=sezione, per_data=True, n=n)
    except Exception as exc:  # noqa: BLE001 - errors are answers
        return _errore(exc)
    if not risultati:
        return SearchResult(success=False, source=_SOURCE, error_type="no_results",
                            results_text="Nessuna deliberazione recente della Corte dei conti trovata.")
    etichetta = f" ({sezione})" if sezione else " (tutte le sezioni di controllo)"
    lines = [f"**Ultime deliberazioni depositate della Corte dei conti**{etichetta}, dalla più recente\n"]
    for r in risultati:
        lines += [format_result(r), ""]
    lines.append("*Dopo questo tool: leggi_deliberazione_corte_conti() con l'identificativo indicato.*")
    return SearchResult(success=True, source=_SOURCE, num_found=len(risultati), results_text="\n".join(lines))


# ---------------------------------------------------------------------------
# MCP tool wrappers
# ---------------------------------------------------------------------------


@mcp.tool(tags={"giurisprudenza", "giurisprudenza_conti"}, output_schema=None)
async def cerca_deliberazioni_corte_conti(
    query: str = "",
    sezione: str = "",
    anno: str = "",
    numero: str = "",
    max_risultati: int = 5,
) -> str:
    """Cerca deliberazioni e pareri delle sezioni di controllo della Corte dei conti.

    USARE quando si parla di: pareri della Corte dei conti agli enti locali (art. 7, comma 8,
    l. 131/2003), controllo preventivo di legittimità, rendiconti e bilanci degli enti, spesa di
    personale, contratti e convenzioni della PA (es. "rinnovo tacito convenzione"), sezione delle
    autonomie, sezioni riunite in sede di controllo.
    Cerca le pagine che contengono TUTTE le parole indicate, in ordine di pertinenza; con numero
    (e anno) trova una deliberazione per estremi. Dopo la ricerca:
    leggi_deliberazione_corte_conti() con l'identificativo di ogni risultato.
    Restituisce: al più 5 deliberazioni (limite del servizio pubblico della Corte) con sezione,
    numero, anno, data di deposito, esito, oggetto, il passo che contiene le parole, identificativo
    e link al PDF ufficiale; il conteggio indica il totale trovato.
    NON copre le sentenze delle sezioni giurisdizionali: il servizio pubblico non le restituisce.
    Vigenza: banca dati ufficiale della Corte dei conti, letta al momento della chiamata.
    Precisione: INDICATIVO (ricerca testuale della banca dati, prime 5 per pertinenza).

    Args:
        query: Parole da cercare (es. "rinnovo tacito convenzione", "fondo salario accessorio")
        sezione: Sezione che ha deliberato, anche in parte (es. "Campania", "Lombardia",
            "Sezione delle autonomie", "Sezioni riunite"): un nome ambiguo è segnalato con le scelte
        anno: Anno della deliberazione (es. "2025")
        numero: Numero della deliberazione (es. "29"); con anno e sezione individua un atto
        max_risultati: Numero di risultati (default e massimo 5, il limite del servizio)
    """
    result = await _cerca_deliberazioni_corte_conti_impl(query, sezione, anno, numero, max_risultati)
    return result.to_str()


@mcp.tool(tags={"giurisprudenza", "giurisprudenza_conti"}, output_schema=None)
async def leggi_deliberazione_corte_conti(
    id_deliberazione: str = "",
    numero: str = "",
    anno: str = "",
    sezione: str = "",
    da_carattere: int = 1,
) -> str:
    """Legge una deliberazione della Corte dei conti (sezioni di controllo): scheda e testo integrale.

    Usare dopo cerca_deliberazioni_corte_conti() o ultime_deliberazioni_corte_conti() con
    l'identificativo del risultato (es. "SRCCAM/29/2025/PREV", deliberazione n. 29/2025/PREV della
    Sezione regionale di controllo per la Campania), oppure con numero, anno e sezione: se più
    sezioni hanno usato lo stesso numero nell'anno, il tool le elenca invece di sceglierne una.
    Restituisce: sezione, numero, anno, tipo, date di adunanza e deposito, esito, presidente,
    relatore, enti destinatari, materie, oggetto, link al PDF ufficiale e alla scheda nella banca
    dati, e il testo integrale come lo riporta la banca dati (25000 caratteri per risposta; la nota
    finale indica il da_carattere con cui leggere il seguito). Il PDF ufficiale fa fede.
    Un identificativo inesistente è un errore esplicito ("nessuna deliberazione ..."), mai una
    scheda vuota.
    Vigenza: banca dati ufficiale della Corte dei conti, letta al momento della chiamata.
    Precisione: ESATTO (testo della deliberazione dalla banca dati ufficiale).

    Args:
        id_deliberazione: Identificativo restituito dalla ricerca (es. "SRCCAM/29/2025/PREV")
        numero: Numero della deliberazione (es. "29"), con anno
        anno: Anno della deliberazione (es. "2025")
        sezione: Sezione che ha deliberato (es. "Campania"), quando il numero si ripete
        da_carattere: Carattere da cui leggere (1 = inizio, default). Se il testo supera il limite, la
            nota finale indica il valore con cui ripetere la chiamata per leggere il seguito
    """
    result = await _leggi_deliberazione_corte_conti_impl(id_deliberazione, numero, anno, sezione, da_carattere)
    return result.to_str()


@mcp.tool(tags={"giurisprudenza", "giurisprudenza_conti"}, output_schema=None)
async def ultime_deliberazioni_corte_conti(sezione: str = "", max_risultati: int = 5) -> str:
    """Ultime deliberazioni depositate dalle sezioni di controllo della Corte dei conti.

    Dalla più recente per data di deposito, con filtro opzionale per sezione.
    Dopo questo tool: leggi_deliberazione_corte_conti() con l'identificativo di ogni risultato.
    Restituisce: al più 5 deliberazioni (limite del servizio pubblico) con sezione, numero, anno,
    data di deposito, esito, oggetto, identificativo e link al PDF ufficiale.
    Vigenza: banca dati ufficiale della Corte dei conti, letta al momento della chiamata.
    Precisione: INDICATIVO (ordine per data di deposito della banca dati).

    Args:
        sezione: Sezione che ha deliberato (es. "Lombardia", "Sezione delle autonomie")
        max_risultati: Numero di risultati (default e massimo 5, il limite del servizio)
    """
    result = await _ultime_deliberazioni_corte_conti_impl(sezione, max_risultati)
    return result.to_str()

"""MCP tools for searching GPDP (Garante per la Protezione dei Dati Personali) documents.

TRIGGER: usare quando l'utente chiede di provvedimenti/sanzioni del Garante Privacy,
linee guida GPDP, data breach, cookie policy, profilazione, videosorveglianza,
trattamento dati personali, intelligenza artificiale e privacy.
"""

from src.server import mcp
from src.lib._paging import invalid_start
from src.lib.gpdp.client import (
    DocNotAvailable,
    fetch_doc,
    format_full,
    format_result,
    normalize_date,
    resolve_tipologia,
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
        # the portal reads only AAAA-MM-GG and filters tipologia by node id (idsTipologia)
        data_da = normalize_date(data_da, "data_da")
        data_a = normalize_date(data_a, "data_a")
        tipologia_ids = ",".join(resolve_tipologia(tipologia))
    except ValueError as exc:
        return f"Errore: {exc}"
    try:
        docs = await search_docs(
            query=query,
            data_da=data_da,
            data_a=data_a,
            tipologia_id=tipologia_ids,
            rows=max_risultati,
        )
    except Exception as exc:
        return f"Errore nella ricerca: {exc}"

    docs = docs[:max_risultati]
    if not docs:
        return f"Nessun provvedimento trovato per: _{query}_"

    lines = [f"**Trovati {len(docs)} provvedimenti del Garante per**: _{query}_\n"]
    for doc in docs:
        lines.append(format_result(doc))
        lines.append("")
    return "\n".join(lines)


async def _leggi_provvedimento_garante_impl(docweb_id: int, da_carattere: int = 1) -> str:
    if (error := invalid_start(da_carattere)) is not None:
        return f"Errore: {error}"
    try:
        title, text = await fetch_doc(docweb_id)
        return format_full(title, text, docweb_id, da_carattere=da_carattere)
    except DocNotAvailable:
        return (
            f"Errore: DocWeb {docweb_id} non disponibile: il portale risponde "
            "«Il contenuto o il file richiesto non è disponibile» "
            "(ID inesistente o documento non pubblicato come pagina di testo, "
            "ad esempio un allegato PDF)."
        )
    except Exception as exc:
        return f"Errore nel recupero del provvedimento DocWeb {docweb_id}: {exc}"


async def _ultimi_provvedimenti_garante_impl(
    tipologia: str = "",
    max_risultati: int = 10,
) -> str:
    max_risultati = min(max_risultati, 50)
    try:
        tipologia_ids = ",".join(resolve_tipologia(tipologia))
    except ValueError as exc:
        return f"Errore: {exc}"
    try:
        docs = await search_docs(
            tipologia_id=tipologia_ids,
            rows=max_risultati,
            sort_by="data",
        )
    except Exception as exc:
        return f"Errore nel recupero degli ultimi provvedimenti: {exc}"

    docs = docs[:max_risultati]
    if not docs:
        return "Nessun provvedimento recente trovato."

    if tipologia:
        titolo = f"**Ultimi provvedimenti del Garante Privacy** (tipologia: {tipologia})\n"
    else:
        # without a filter the portal lists everything it publishes: press reviews, news,
        # newsletters and provvedimenti together
        titolo = (
            "**Ultimi documenti pubblicati dal Garante Privacy** (tutte le tipologie: "
            "per i soli provvedimenti usare tipologia=\"provvedimento\")\n"
        )
    lines = [titolo]
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

    Il filtro tipologia e le date sono applicati dal portale del Garante: "provvedimento"
    comprende tutte le tipologie sotto "Provvedimenti" (ordinanze ingiunzione, pareri,
    prescrizioni, ammonimenti, linee guida, decisioni su ricorso, ...). Una data o una
    tipologia non riconosciuta e' un errore esplicito, mai un elenco vuoto.

    Args:
        query: Testo da cercare (es. "data breach notifica", "cookie consenso", "intelligenza artificiale")
        tipologia: Filtra per tipo documento (es. "provvedimento", "ordinanza", "parere", "linee guida", "prescrizioni", "ammonimento", "autorizzazione")
        data_da: Data inizio in formato GG/MM/AAAA (es. "01/01/2023"; accettato anche AAAA-MM-GG)
        data_a: Data fine in formato GG/MM/AAAA (es. "31/12/2024"; accettato anche AAAA-MM-GG)
        max_risultati: Numero massimo di risultati (default 10, max 50)
    """
    return await _cerca_provvedimenti_garante_impl(
        query=query, tipologia=tipologia, data_da=data_da,
        data_a=data_a, max_risultati=max_risultati,
    )


@mcp.tool(tags={"privacy"})
async def leggi_provvedimento_garante(docweb_id: int, da_carattere: int = 1) -> str:
    """Legge il testo completo di un provvedimento del Garante Privacy tramite DocWeb ID.

    Usare dopo cerca_provvedimenti_garante() o ultimi_provvedimenti_garante() per leggere
    il testo completo. Il DocWeb ID è riportato in ogni risultato della ricerca.
    Restituisce: testo del provvedimento con titolo, data, e link alla fonte GPDP. Oltre 6000
    caratteri il testo e' abbreviato: la parte omessa si legge ripetendo la chiamata con il
    da_carattere indicato nella nota. Con da_carattere > 1 restituisce i 6000 caratteri che
    partono da quella posizione; le posizioni contano il testo del documento (titolo e link esclusi).

    Un DocWeb ID inesistente o non pubblicato come pagina di testo (ad esempio un allegato PDF)
    restituisce un errore esplicito, non un documento.

    Esempi di DocWeb ID noti:
    - 9677876: Linee guida cookie 2021
    - 9870832: Provvedimento 30 marzo 2023 (n. 112), limitazione provvisoria ChatGPT (OpenAI)
    - 9874702: Provvedimento 11 aprile 2023 (n. 114), prescrizioni a OpenAI (ChatGPT)

    Args:
        docweb_id: ID numerico del documento Garante (es. 9677876)
        da_carattere: Carattere da cui leggere (1 = inizio, default). Se il testo supera il limite,
            la nota indica il valore con cui ripetere la chiamata per leggere il seguito
    """
    return await _leggi_provvedimento_garante_impl(docweb_id, da_carattere)


@mcp.tool(tags={"privacy"})
async def ultimi_provvedimenti_garante(
    tipologia: str = "",
    max_risultati: int = 10,
) -> str:
    """Ultimi documenti del Garante Privacy in ordine di data, con filtro opzionale per tipologia.

    Senza tipologia elenca tutto cio' che il portale pubblica (rassegne stampa, news,
    newsletter e provvedimenti insieme): per i soli provvedimenti usare tipologia="provvedimento".
    Il filtro e' applicato dal portale sull'intero archivio, non sugli ultimi risultati.
    Dopo questo tool: leggi_provvedimento_garante() con il DocWeb ID per il testo completo.
    Restituisce: lista cronologica degli ultimi documenti con DocWeb ID e metadati.

    Args:
        tipologia: Filtra per tipo (es. "provvedimento", "ordinanza", "parere", "linee guida", "prescrizioni", "ammonimento"; "provvedimento" comprende tutte le tipologie sotto "Provvedimenti")
        max_risultati: Numero massimo di risultati (default 10, max 50)
    """
    return await _ultimi_provvedimenti_garante_impl(
        tipologia=tipologia, max_risultati=max_risultati,
    )

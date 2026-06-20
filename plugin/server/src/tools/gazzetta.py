"""MCP tools for the Gazzetta Ufficiale della Repubblica Italiana.

TRIGGER: usare quando l'utente chiede di atti pubblicati in Gazzetta Ufficiale,
decreti, leggi, ordinanze ministeriali, comunicati, novita normative italiane,
testo di un atto pubblicato in GU, sommario di una gazzetta o il PDF ufficiale.

Workflow tipico:
- ultime_gazzette() per le novita normative (via RSS).
- cerca_gazzetta_ufficiale() per ricerca parametrica/full-text.
- leggi_atto_gazzetta(codice, data) per il testo completo di un atto.
- sommario_gazzetta(numero, data) per l'indice di un fascicolo.
- scarica_pdf_gazzetta(numero, data) per il PDF ufficiale (restituisce l'URL).
"""

from src.lib._result import SearchResult
from src.server import mcp
from src.lib.gazzetta.client import (
    RSS_CODE,
    SERIE,
    fetch_atto,
    fetch_latest,
    fetch_sommario,
    format_detail,
    format_result,
    format_sommario,
    pdf_url,
    search_atti,
)

_SOURCE = "gazzetta_ufficiale"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_serie_path(serie: str) -> str:
    """Map a human-friendly serie key to its URL path segment.

    Unknown keys default to serie_generale (the most common case).
    """
    return SERIE.get(serie.lower().strip().replace(" ", "_"), "serie_generale")


def _resolve_rss_code(serie: str) -> str:
    return RSS_CODE.get(serie.lower().strip().replace(" ", "_"), "SG")


# ---------------------------------------------------------------------------
# Impl functions (testable without MCP context) -> SearchResult
# ---------------------------------------------------------------------------

async def _cerca_gazzetta_ufficiale_impl(
    query: str = "",
    titolo: str = "",
    testo: str = "",
    tipo_provvedimento: str = "",
    emettitore: str = "",
    materia: str = "",
    serie: str = "serie_generale",
    anno_da: str = "",
    anno_a: str = "",
    max_risultati: int = 20,
) -> SearchResult:
    max_risultati = max(1, min(max_risultati, 100))
    serie_path = _resolve_serie_path(serie)

    # `query` is a convenience alias: search it in the title unless `titolo`/`testo`
    # are explicitly provided.
    titolo_q = titolo or query
    testo_q = testo

    try:
        total, docs = await search_atti(
            serie_path,
            titolo=titolo_q,
            testo=testo_q,
            descrizione_tipo_provvedimento=tipo_provvedimento,
            descrizione_emettitore=emettitore,
            descrizione_materia=materia,
            anno_da=anno_da,
            anno_a=anno_a,
            rows=max_risultati,
        )
    except Exception as exc:
        return SearchResult(
            success=False, source=_SOURCE, error_type="source_down",
            error_message=str(exc),
        )

    if not docs:
        q_desc = titolo_q or testo_q or query or "ricerca"
        return SearchResult(
            success=False, source=_SOURCE, error_type="no_results",
            results_text=f"Nessun atto trovato in Gazzetta Ufficiale per: _{q_desc}_",
        )

    head = f"**Trovati {total} atti in Gazzetta Ufficiale**"
    if total > len(docs):
        head += f" (mostrati i primi {len(docs)})"
    lines = [head + "\n"]
    for doc in docs:
        lines.append(format_result(doc))
        lines.append("")
    return SearchResult(
        success=True, source=_SOURCE, num_found=total, results_text="\n".join(lines),
    )


async def _leggi_atto_gazzetta_impl(
    codice_redazionale: str,
    data_pubblicazione: str,
    serie: str = "serie_generale",
    solo_metadati: bool = False,
) -> SearchResult:
    serie_path = _resolve_serie_path(serie)
    try:
        detail = await fetch_atto(
            serie_path, data_pubblicazione, codice_redazionale,
            metadata_only=solo_metadati,
        )
    except ValueError as exc:
        return SearchResult(
            success=False, source=_SOURCE, error_type="bad_input",
            error_message=f"Data non valida: {exc}",
            results_text=f"**Errore**: data non valida. {exc}",
        )
    except Exception as exc:
        return SearchResult(
            success=False, source=_SOURCE, error_type="source_down",
            error_message=str(exc),
        )

    if not solo_metadati and not detail.text:
        return SearchResult(
            success=False, source=_SOURCE, error_type="no_results",
            results_text=(
                f"Testo non disponibile per l'atto {codice_redazionale} "
                f"({data_pubblicazione}). Metadati:\n\n{format_detail(detail)}"
            ),
        )

    return SearchResult(
        success=True, source=_SOURCE, num_found=1,
        results_text=format_detail(detail),
    )


async def _sommario_gazzetta_impl(
    numero_gazzetta: str,
    data_pubblicazione: str,
    serie: str = "serie_generale",
) -> SearchResult:
    try:
        heading, atti = await fetch_sommario(data_pubblicazione, numero_gazzetta)
    except ValueError as exc:
        return SearchResult(
            success=False, source=_SOURCE, error_type="bad_input",
            error_message=f"Data non valida: {exc}",
            results_text=f"**Errore**: data non valida. {exc}",
        )
    except Exception as exc:
        return SearchResult(
            success=False, source=_SOURCE, error_type="source_down",
            error_message=str(exc),
        )

    if not atti:
        return SearchResult(
            success=False, source=_SOURCE, error_type="no_results",
            results_text=(
                f"Nessun atto trovato nel sommario della Gazzetta n. {numero_gazzetta} "
                f"del {data_pubblicazione}."
            ),
        )

    return SearchResult(
        success=True, source=_SOURCE, num_found=len(atti),
        results_text=format_sommario(heading, atti),
    )


async def _ultime_gazzette_impl(
    serie: str = "serie_generale",
    max_risultati: int = 10,
) -> SearchResult:
    max_risultati = max(1, min(max_risultati, 100))
    rss_code = _resolve_rss_code(serie)
    try:
        docs = await fetch_latest(rss_code, rows=max_risultati)
    except Exception as exc:
        return SearchResult(
            success=False, source=_SOURCE, error_type="source_down",
            error_message=str(exc),
        )

    if not docs:
        return SearchResult(
            success=False, source=_SOURCE, error_type="no_results",
            results_text="Nessun atto recente trovato nella Gazzetta Ufficiale.",
        )

    lines = ["**Ultimi atti pubblicati in Gazzetta Ufficiale**\n"]
    for doc in docs:
        lines.append(format_result(doc))
        lines.append("")
    return SearchResult(
        success=True, source=_SOURCE, num_found=len(docs), results_text="\n".join(lines),
    )


async def _scarica_pdf_gazzetta_impl(
    numero_gazzetta: str,
    data_pubblicazione: str,
    serie: str = "serie_generale",
) -> SearchResult:
    try:
        url = pdf_url(data_pubblicazione, numero_gazzetta)
    except Exception as exc:
        return SearchResult(
            success=False, source=_SOURCE, error_type="source_down",
            error_message=f"Data non valida: {exc}",
        )
    text = (
        f"**PDF ufficiale Gazzetta Ufficiale n. {numero_gazzetta} "
        f"del {data_pubblicazione}**\n\n[Scarica il PDF]({url})\n\n{url}"
    )
    return SearchResult(success=True, source=_SOURCE, num_found=1, results_text=text)


# ---------------------------------------------------------------------------
# MCP tool wrappers
# ---------------------------------------------------------------------------

@mcp.tool(tags={"normativa"})
async def cerca_gazzetta_ufficiale(
    query: str = "",
    titolo: str = "",
    testo: str = "",
    tipo_provvedimento: str = "",
    emettitore: str = "",
    materia: str = "",
    serie: str = "serie_generale",
    anno_da: str = "",
    anno_a: str = "",
    max_risultati: int = 20,
) -> str:
    """Cerca atti pubblicati nella Gazzetta Ufficiale (ricerca parametrica/full-text).

    USARE quando si cerca: decreti, leggi, ordinanze, comunicati o altri atti
    pubblicati in GU per titolo, testo, tipo provvedimento, emettitore o periodo.
    Dopo aver trovato un atto, usare leggi_atto_gazzetta(codice, data) per il testo.
    Restituisce: lista atti con emettitore, tipo, oggetto, codice redazionale e link.

    Args:
        query: Parole da cercare nel titolo (alias rapido di `titolo`)
        titolo: Parole da cercare nel titolo dell'atto
        testo: Parole da cercare nel testo integrale dell'atto
        tipo_provvedimento: Descrizione tipo (es. "DECRETO", "LEGGE", "ORDINANZA")
        emettitore: Descrizione emettitore (es. "MINISTERO DELLA SALUTE")
        materia: Descrizione materia
        serie: Serie (serie_generale, unione_europea, regioni, corte_costituzionale,
            parte_seconda, contratti, concorsi)
        anno_da: Anno di pubblicazione iniziale (es. "2024")
        anno_a: Anno di pubblicazione finale (es. "2026")
        max_risultati: Numero massimo di risultati (default 20, max 100)
    """
    result = await _cerca_gazzetta_ufficiale_impl(
        query=query, titolo=titolo, testo=testo,
        tipo_provvedimento=tipo_provvedimento, emettitore=emettitore,
        materia=materia, serie=serie, anno_da=anno_da, anno_a=anno_a,
        max_risultati=max_risultati,
    )
    return result.to_str()


@mcp.tool(tags={"normativa"})
async def leggi_atto_gazzetta(
    codice_redazionale: str,
    data_pubblicazione: str,
    serie: str = "serie_generale",
    solo_metadati: bool = False,
) -> str:
    """Legge il testo completo di un atto pubblicato in Gazzetta Ufficiale.

    Usare dopo cerca_gazzetta_ufficiale(), ultime_gazzette() o sommario_gazzetta()
    indicando il codice redazionale e la data di pubblicazione del risultato.
    Restituisce: metadati ELI (tipo, emettitore, date) + testo integrale assemblato.

    Args:
        codice_redazionale: Codice dell'atto (es. "26A02808")
        data_pubblicazione: Data pubblicazione in formato YYYY-MM-DD (es. "2026-06-13")
        serie: Serie dell'atto (default serie_generale)
        solo_metadati: Se True, restituisce solo i metadati senza scaricare il testo
    """
    result = await _leggi_atto_gazzetta_impl(
        codice_redazionale=codice_redazionale,
        data_pubblicazione=data_pubblicazione,
        serie=serie, solo_metadati=solo_metadati,
    )
    return result.to_str()


@mcp.tool(tags={"normativa"})
async def sommario_gazzetta(
    numero_gazzetta: str,
    data_pubblicazione: str,
    serie: str = "serie_generale",
) -> str:
    """Restituisce il sommario (indice degli atti) di un fascicolo di Gazzetta Ufficiale.

    Usare per vedere tutti gli atti pubblicati in una specifica gazzetta.
    Da ogni atto del sommario si puo poi usare leggi_atto_gazzetta() per il testo.
    Restituisce: elenco degli atti con codice redazionale e oggetto.

    Args:
        numero_gazzetta: Numero del fascicolo (es. "135")
        data_pubblicazione: Data pubblicazione in formato YYYY-MM-DD (es. "2026-06-13")
        serie: Serie della gazzetta (default serie_generale)
    """
    result = await _sommario_gazzetta_impl(
        numero_gazzetta=numero_gazzetta,
        data_pubblicazione=data_pubblicazione, serie=serie,
    )
    return result.to_str()


@mcp.tool(tags={"normativa"})
async def ultime_gazzette(
    serie: str = "serie_generale",
    max_risultati: int = 10,
) -> str:
    """Ultimi atti pubblicati nella Gazzetta Ufficiale (novita normative, via RSS).

    USARE per le novita normative italiane piu recenti. Percorso stabile (RSS).
    Da ogni risultato usare leggi_atto_gazzetta(codice, data) per il testo completo.
    Restituisce: lista cronologica degli ultimi atti con emettitore, tipo e oggetto.

    Args:
        serie: Serie (serie_generale, unione_europea, regioni, corte_costituzionale,
            parte_seconda, contratti, concorsi)
        max_risultati: Numero massimo di risultati (default 10, max 100)
    """
    result = await _ultime_gazzette_impl(serie=serie, max_risultati=max_risultati)
    return result.to_str()


@mcp.tool(tags={"normativa"})
async def scarica_pdf_gazzetta(
    numero_gazzetta: str,
    data_pubblicazione: str,
    serie: str = "serie_generale",
) -> str:
    """Restituisce l'URL del PDF ufficiale di un fascicolo di Gazzetta Ufficiale.

    Restituisce il link al PDF ufficiale (non scarica il file inline).

    Args:
        numero_gazzetta: Numero del fascicolo (es. "135")
        data_pubblicazione: Data pubblicazione in formato YYYY-MM-DD (es. "2026-06-13")
        serie: Serie della gazzetta (default serie_generale)
    """
    result = await _scarica_pdf_gazzetta_impl(
        numero_gazzetta=numero_gazzetta,
        data_pubblicazione=data_pubblicazione, serie=serie,
    )
    return result.to_str()

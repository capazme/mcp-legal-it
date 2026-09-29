"""MCP tools for searching CGUE (Court of Justice of the European Union) case law.

TRIGGER: usare quando l'utente chiede di sentenze CGUE, Corte di Giustizia UE, Tribunale UE,
rinvio pregiudiziale, diritto UE, direttive europee interpretate, regolamenti UE,
conclusioni avvocato generale, ECLI europeo.
"""

from src.lib._result import SearchResult
from src.server import mcp
from src.lib.cgue.client import (
    celex_of,
    fetch_case_metadata,
    fetch_sentenza_text,
    format_full,
    format_result,
    normalize_riferimento,
    search_giurisprudenza,
)


# ---------------------------------------------------------------------------
# Impl functions (testable without MCP context)
# ---------------------------------------------------------------------------

async def _cerca_giurisprudenza_cgue_impl(
    query: str,
    corte: str = "",
    tipo_documento: str = "",
    anno_da: str = "",
    anno_a: str = "",
    materia: str = "",
    max_risultati: int = 10,
) -> SearchResult:
    max_risultati = max(1, min(max_risultati, 50))
    keywords = [kw.strip() for kw in query.split(",") if kw.strip()] if query else []

    try:
        docs = await search_giurisprudenza(
            keywords=keywords,
            court=corte,
            doc_type=tipo_documento,
            year_from=anno_da,
            year_to=anno_a,
            materia=materia,
            limit=max_risultati,
        )
    except Exception as exc:
        return SearchResult(success=False, source="cgue", error_type="source_down", error_message=str(exc))

    if not docs:
        q_desc = query or materia or "recenti"
        return SearchResult(
            success=False,
            source="cgue",
            error_type="no_results",
            results_text=f"Nessuna sentenza CGUE trovata per: _{q_desc}_",
        )

    lines = [f"**Trovate {len(docs)} sentenze CGUE**\n"]
    for doc in docs:
        lines.append(format_result(doc))
        lines.append("")
    return SearchResult(success=True, source="cgue", num_found=len(docs), results_text="\n".join(lines))


async def _leggi_sentenza_cgue_impl(cellar_uri: str) -> SearchResult:
    try:
        text = await fetch_sentenza_text(cellar_uri)
        stripped = text.strip()
        if not stripped or len(stripped) < 200:
            return SearchResult(
                success=False,
                source="cgue",
                error_type="no_results",
                results_text=f"Testo non disponibile da CELLAR per {cellar_uri} (risposta vuota o pagina non valida).",
            )
        # The header carries the official case number and the ECLI, which the HTML text does not
        # contain: they are read from CELLAR by CELEX (best effort, the text is shown anyway).
        celex = celex_of(cellar_uri, stripped)
        meta = await fetch_case_metadata(celex) if celex else {}
        return SearchResult(
            success=True,
            source="cgue",
            num_found=1,
            results_text=format_full(
                celex or cellar_uri.split("/")[-1],
                text,
                meta.get("ecli", ""),
                case_ref=meta.get("case_ref", ""),
                date=meta.get("date", ""),
            ),
        )
    except Exception as exc:
        return SearchResult(
            success=False,
            source="cgue",
            error_type="source_down",
            error_message=str(exc),
            results_text=f"Errore nel recupero del testo da CELLAR ({cellar_uri}): {exc}",
        )


async def _giurisprudenza_cgue_su_norma_impl(
    riferimento: str,
    corte: str = "",
    anno_da: str = "",
    max_risultati: int = 10,
) -> SearchResult:
    max_risultati = max(1, min(max_risultati, 50))

    # "art. 101 TFUE" -> ["articolo 101", "tfue"]: the titles write "Articolo 101 TFUE", and
    # every term must be in the title (AND), not the reference as one substring.
    terms = normalize_riferimento(riferimento)
    if not terms:
        return SearchResult(
            success=False,
            source="cgue",
            error_type="bad_input",
            results_text='Indicare una norma UE da cercare (es. "art. 101 TFUE", "direttiva 2006/112").',
        )

    try:
        docs = await search_giurisprudenza(
            keywords=[],
            required_terms=terms,
            court=corte,
            year_from=anno_da,
            limit=max_risultati,
        )
    except Exception as exc:
        return SearchResult(success=False, source="cgue", error_type="source_down", error_message=str(exc))

    if not docs:
        return SearchResult(
            success=False,
            source="cgue",
            error_type="no_results",
            results_text=f"Nessuna sentenza CGUE trovata per la norma: _{riferimento}_",
        )

    lines = [f"**Sentenze CGUE che citano**: _{riferimento}_\n"]
    for doc in docs:
        lines.append(format_result(doc))
        lines.append("")
    return SearchResult(success=True, source="cgue", num_found=len(docs), results_text="\n".join(lines))


async def _ultime_sentenze_cgue_impl(
    corte: str = "",
    tipo_documento: str = "",
    materia: str = "",
    max_risultati: int = 10,
) -> SearchResult:
    max_risultati = max(1, min(max_risultati, 50))

    try:
        docs = await search_giurisprudenza(
            keywords=[],
            court=corte,
            doc_type=tipo_documento,
            materia=materia,
            limit=max_risultati,
        )
    except Exception as exc:
        return SearchResult(success=False, source="cgue", error_type="source_down", error_message=str(exc))

    if not docs:
        return SearchResult(
            success=False,
            source="cgue",
            error_type="no_results",
            results_text="Nessuna sentenza CGUE recente trovata.",
        )

    lines = ["**Ultime sentenze CGUE**\n"]
    for doc in docs:
        lines.append(format_result(doc))
        lines.append("")
    return SearchResult(success=True, source="cgue", num_found=len(docs), results_text="\n".join(lines))


# ---------------------------------------------------------------------------
# MCP tool wrappers
# ---------------------------------------------------------------------------

@mcp.tool(tags={"giurisprudenza_ue", "normativa"})
async def cerca_giurisprudenza_cgue(
    query: str,
    corte: str = "",
    tipo_documento: str = "",
    anno_da: str = "",
    anno_a: str = "",
    materia: str = "",
    max_risultati: int = 10,
) -> str:
    """Cerca sentenze e decisioni della Corte di Giustizia UE (CGUE) e del Tribunale UE via SPARQL CELLAR.

    USARE quando si parla di: sentenze CGUE, Corte di Giustizia UE, Tribunale UE, rinvio pregiudiziale,
    diritto UE interpretato, direttive europee, regolamenti UE, conclusioni avvocato generale, ECLI europeo.
    Dopo aver trovato una sentenza, usare leggi_sentenza_cgue(cellar_uri) per il testo.
    Restituisce: lista sentenze con CELEX, ECLI, numero di causa (forma ufficiale, es. C-311/18),
    data, titolo in italiano (parti, materia e norme applicate) e CELLAR URI; una riga per decisione.

    Args:
        query: Parole da cercare nei titoli italiani. La virgola separa alternative in OR: basta che
            il titolo contenga una qualunque delle parole (es. "IVA, sesta direttiva" o
            "rinvio pregiudiziale, consumatore"); per restringere usare corte, anno, tipo e materia
        corte: Filtra per corte (es. "corte_di_giustizia", "tribunale") — default tutte
        tipo_documento: Filtra per tipo (es. "sentenza", "ordinanza", "conclusioni_ag") — default tutti
        anno_da: Anno di inizio in formato YYYY (es. "2020") — filtra per data decisione
        anno_a: Anno di fine in formato YYYY (es. "2024")
        materia: Restringe (AND con la query) alle decisioni il cui titolo contiene almeno una delle
            parole della materia predefinita ("iva", "concorrenza", "ambiente", "lavoro",
            "protezione_dati", "appalti", "consumatori")
        max_risultati: Numero massimo di decisioni distinte (default 10, max 50)
    """
    result = await _cerca_giurisprudenza_cgue_impl(
        query=query, corte=corte, tipo_documento=tipo_documento,
        anno_da=anno_da, anno_a=anno_a, materia=materia, max_risultati=max_risultati,
    )
    return result.to_str() if isinstance(result, SearchResult) else result


@mcp.tool(tags={"giurisprudenza_ue", "normativa"})
async def leggi_sentenza_cgue(cellar_uri: str) -> str:
    """Legge il testo completo di una sentenza CGUE tramite CELLAR URI.

    Il dispositivo ("Per questi motivi") e' incluso anche nelle sentenze lunghe: oltre 25000 caratteri
    si abbrevia il corpo, non la parte finale.
    Usare dopo cerca_giurisprudenza_cgue() o ultime_sentenze_cgue() per leggere il testo.
    Il CELLAR URI è riportato in ogni risultato della ricerca come "CELLAR URI".
    Recupera il testo direttamente dall'archivio CELLAR (bypassa EUR-Lex WAF).
    Restituisce: testo della sentenza in italiano, preceduto da CELEX, numero di causa (es. C-311/18),
    ECLI e data. Oltre 25000 caratteri il testo e' abbreviato: si conservano l'inizio e il
    dispositivo (dal "Per questi motivi", fino a 8000 caratteri) con l'indicazione dei caratteri omessi.

    Args:
        cellar_uri: URI CELLAR della sentenza
            (es. "http://publications.europa.eu/resource/cellar/abc123.0006")
    """
    result = await _leggi_sentenza_cgue_impl(cellar_uri)
    return result.to_str() if isinstance(result, SearchResult) else result


@mcp.tool(tags={"giurisprudenza_ue", "normativa"})
async def giurisprudenza_cgue_su_norma(
    riferimento: str,
    corte: str = "",
    anno_da: str = "",
    max_risultati: int = 10,
) -> str:
    """Cerca sentenze CGUE e Tribunale UE che interpretano una specifica norma del diritto UE.

    Usare per trovare la giurisprudenza CGUE su un articolo del TFUE, una direttiva,
    un regolamento UE o un principio generale. Dopo aver trovato le sentenze, usare
    leggi_sentenza_cgue(cellar_uri) per leggere il testo.
    Restituisce: lista sentenze il cui titolo cita il riferimento normativo indicato (una riga per
    decisione). La ricerca e' sul titolo ufficiale, che riporta gli articoli e gli atti applicati
    ("Articolo 101 TFUE", "direttiva 2006/112/CE"): una norma citata solo nel corpo della sentenza
    non e' trovata. Articolo e atto sono termini indipendenti del titolo: "art. 7 GDPR" trova anche
    le decisioni che citano l'articolo 7 di un'altra norma (es. la Carta) e il regolamento 2016/679;
    verificare sempre il testo con leggi_sentenza_cgue().

    Args:
        riferimento: Norma UE da cercare (es. "art. 101 TFUE", "art. 7 GDPR",
            "direttiva 2006/112", "art. 34 TFUE libera circolazione merci"). "art."/"artt." sono
            riportati ad "articolo", "GDPR" a 2016/679; tutti i termini devono comparire nel titolo (AND)
        corte: Filtra per corte (es. "corte_di_giustizia", "tribunale") — default tutte
        anno_da: Anno di inizio in formato YYYY (es. "2020")
        max_risultati: Numero massimo di risultati (default 10, max 50)
    """
    result = await _giurisprudenza_cgue_su_norma_impl(
        riferimento=riferimento, corte=corte, anno_da=anno_da, max_risultati=max_risultati,
    )
    return result.to_str() if isinstance(result, SearchResult) else result


@mcp.tool(tags={"giurisprudenza_ue", "normativa"})
async def ultime_sentenze_cgue(
    corte: str = "",
    tipo_documento: str = "",
    materia: str = "",
    max_risultati: int = 10,
) -> str:
    """Ultime sentenze e decisioni pubblicate dalla Corte di Giustizia UE e dal Tribunale UE.

    Dopo questo tool: leggi_sentenza_cgue(cellar_uri) con il CELLAR URI per il testo.
    Restituisce: lista cronologica (dalla piu' recente, una riga per decisione) con CELEX, ECLI,
    numero di causa (forma ufficiale, es. C-369/25), data e titolo.

    Args:
        corte: Filtra per corte (es. "corte_di_giustizia", "tribunale") — default tutte
        tipo_documento: Filtra per tipo (es. "sentenza", "ordinanza", "conclusioni_ag")
        materia: Filtra per materia (es. "iva", "concorrenza", "ambiente", "lavoro",
            "protezione_dati", "appalti", "consumatori")
        max_risultati: Numero massimo di risultati (default 10, max 50)
    """
    result = await _ultime_sentenze_cgue_impl(
        corte=corte, tipo_documento=tipo_documento, materia=materia, max_risultati=max_risultati,
    )
    return result.to_str() if isinstance(result, SearchResult) else result

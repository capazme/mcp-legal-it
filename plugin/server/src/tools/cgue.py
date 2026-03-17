"""MCP tools for searching CGUE (Court of Justice of the European Union) case law.

TRIGGER: usare quando l'utente chiede di sentenze CGUE, Corte di Giustizia UE, Tribunale UE,
rinvio pregiudiziale, diritto UE, direttive europee interpretate, regolamenti UE,
conclusioni avvocato generale, ECLI europeo.
"""

from src.server import mcp
from src.lib.cgue.client import (
    CORTI,
    MATERIE_KEYWORDS,
    TIPI_DOCUMENTO,
    fetch_sentenza_text,
    format_full,
    format_result,
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
) -> str:
    max_risultati = min(max_risultati, 50)
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
        return f"Errore nella ricerca CGUE: {exc}"

    if not docs:
        q_desc = query or materia or "recenti"
        return f"Nessuna sentenza CGUE trovata per: _{q_desc}_"

    lines = [f"**Trovate {len(docs)} sentenze CGUE**\n"]
    for doc in docs:
        lines.append(format_result(doc))
        lines.append("")
    return "\n".join(lines)


async def _leggi_sentenza_cgue_impl(cellar_uri: str) -> str:
    try:
        text = await fetch_sentenza_text(cellar_uri)
        # Extract ECLI from URI if not already available — just use cellar_uri as reference
        return format_full(cellar_uri.split("/")[-1], text, "")
    except Exception as exc:
        return f"Errore nel recupero del testo da CELLAR ({cellar_uri}): {exc}"


async def _giurisprudenza_cgue_su_norma_impl(
    riferimento: str,
    corte: str = "",
    anno_da: str = "",
    max_risultati: int = 10,
) -> str:
    max_risultati = min(max_risultati, 50)

    # Normalize reference to keywords: "art. 101 TFUE" → ["art. 101", "tfue"] or similar
    keywords = [riferimento.strip()] if riferimento.strip() else []

    try:
        docs = await search_giurisprudenza(
            keywords=keywords,
            court=corte,
            year_from=anno_da,
            limit=max_risultati,
        )
    except Exception as exc:
        return f"Errore nella ricerca CGUE su norma '{riferimento}': {exc}"

    if not docs:
        return f"Nessuna sentenza CGUE trovata per la norma: _{riferimento}_"

    lines = [f"**Sentenze CGUE che citano**: _{riferimento}_\n"]
    for doc in docs:
        lines.append(format_result(doc))
        lines.append("")
    return "\n".join(lines)


async def _ultime_sentenze_cgue_impl(
    corte: str = "",
    tipo_documento: str = "",
    materia: str = "",
    max_risultati: int = 10,
) -> str:
    max_risultati = min(max_risultati, 50)

    try:
        docs = await search_giurisprudenza(
            keywords=[],
            court=corte,
            doc_type=tipo_documento,
            materia=materia,
            limit=max_risultati,
        )
    except Exception as exc:
        return f"Errore nel recupero delle ultime sentenze CGUE: {exc}"

    if not docs:
        return "Nessuna sentenza CGUE recente trovata."

    lines = ["**Ultime sentenze CGUE**\n"]
    for doc in docs:
        lines.append(format_result(doc))
        lines.append("")
    return "\n".join(lines)


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
    Dopo aver trovato una sentenza, usare leggi_sentenza_cgue(cellar_uri) per il testo completo.
    Restituisce: lista sentenze con CELEX, ECLI, data, titolo in italiano e CELLAR URI.

    Args:
        query: Keywords da cercare nei titoli italiani (virgola-separati per più termini,
            es. "IVA, sesta direttiva" o "rinvio pregiudiziale, consumatore")
        corte: Filtra per corte (es. "corte_di_giustizia", "tribunale") — default tutte
        tipo_documento: Filtra per tipo (es. "sentenza", "ordinanza", "conclusioni_ag") — default tutti
        anno_da: Anno di inizio in formato YYYY (es. "2020") — filtra per data decisione
        anno_a: Anno di fine in formato YYYY (es. "2024")
        materia: Filtra per materia predefinita (es. "iva", "concorrenza", "ambiente", "lavoro",
            "protezione_dati", "appalti", "consumatori")
        max_risultati: Numero massimo di risultati (default 10, max 50)
    """
    return await _cerca_giurisprudenza_cgue_impl(
        query=query, corte=corte, tipo_documento=tipo_documento,
        anno_da=anno_da, anno_a=anno_a, materia=materia, max_risultati=max_risultati,
    )


@mcp.tool(tags={"giurisprudenza_ue", "normativa"})
async def leggi_sentenza_cgue(cellar_uri: str) -> str:
    """Legge il testo completo di una sentenza CGUE tramite CELLAR URI.

    Usare dopo cerca_giurisprudenza_cgue() o ultime_sentenze_cgue() per leggere il testo completo.
    Il CELLAR URI è riportato in ogni risultato della ricerca come "CELLAR URI".
    Recupera il testo direttamente dall'archivio CELLAR (bypassa EUR-Lex WAF).
    Restituisce: testo integrale della sentenza (max 25000 caratteri) in italiano.

    Args:
        cellar_uri: URI CELLAR della sentenza
            (es. "http://publications.europa.eu/resource/cellar/abc123.0006")
    """
    return await _leggi_sentenza_cgue_impl(cellar_uri)


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
    leggi_sentenza_cgue(cellar_uri) per leggere il testo completo.
    Restituisce: lista sentenze che citano il riferimento normativo indicato.

    Args:
        riferimento: Norma UE da cercare (es. "art. 101 TFUE", "art. 7 GDPR",
            "direttiva 2006/112", "art. 34 TFUE libera circolazione merci")
        corte: Filtra per corte (es. "corte_di_giustizia", "tribunale") — default tutte
        anno_da: Anno di inizio in formato YYYY (es. "2020")
        max_risultati: Numero massimo di risultati (default 10, max 50)
    """
    return await _giurisprudenza_cgue_su_norma_impl(
        riferimento=riferimento, corte=corte, anno_da=anno_da, max_risultati=max_risultati,
    )


@mcp.tool(tags={"giurisprudenza_ue", "normativa"})
async def ultime_sentenze_cgue(
    corte: str = "",
    tipo_documento: str = "",
    materia: str = "",
    max_risultati: int = 10,
) -> str:
    """Ultime sentenze e decisioni pubblicate dalla Corte di Giustizia UE e dal Tribunale UE.

    Dopo questo tool: leggi_sentenza_cgue(cellar_uri) con il CELLAR URI per il testo completo.
    Restituisce: lista cronologica delle ultime sentenze con CELEX, ECLI, data e titolo.

    Args:
        corte: Filtra per corte (es. "corte_di_giustizia", "tribunale") — default tutte
        tipo_documento: Filtra per tipo (es. "sentenza", "ordinanza", "conclusioni_ag")
        materia: Filtra per materia (es. "iva", "concorrenza", "ambiente", "lavoro",
            "protezione_dati", "appalti", "consumatori")
        max_risultati: Numero massimo di risultati (default 10, max 50)
    """
    return await _ultime_sentenze_cgue_impl(
        corte=corte, tipo_documento=tipo_documento, materia=materia, max_risultati=max_risultati,
    )

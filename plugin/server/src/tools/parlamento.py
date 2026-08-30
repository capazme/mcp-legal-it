"""MCP tools for pending bills and legislative iter (dati.senato.it / dati.camera.it).

TRIGGER: usare quando l'utente chiede di DDL, disegni o proposte di legge,
riforme pendenti, iter parlamentare, navette, stato di un provvedimento in
Parlamento, norme in corso di modifica.

Legal Grounding: ogni risultato riporta numero atto, stato datato e link alla
scheda ufficiale — una riforma pendente si segnala SOLO con questi estremi.
"""

import re

from src.lib._result import SearchResult
from src.server import mcp
from src.lib.parlamento.client import (
    LEGISLATURA_CORRENTE,
    STATI_PENDENTI,
    CameraIter,
    NoValidSearchTerms,
    fetch_camera_iter,
    fetch_iter,
    format_fase,
    format_iter,
    parse_atto_input,
    search_ddl,
    _sanitize_phrase,
)
from src.tools.legal_citations import _resolve_act

_CAVEAT_TITOLI = (
    "_Ricerca best-effort sui **titoli** dei DDL (i testi non sono indicizzati): "
    "un DDL che incide sulla norma senza citarla nel titolo non viene trovato._"
)

_ART_PREFIX = re.compile(
    r"^\s*art(?:t)?(?:icol[oi])?\.?\s*\d+\w*(?:[-‑]\w+)?\s*"
    r"(?:,?\s*comma\s*\S+\s*)?"
    r"(?:del(?:la|lo|le)?|dei|degli|di)?\s*",
    re.IGNORECASE,
)


def _norma_search_groups(riferimento: str) -> tuple[list[list[str]], dict | None]:
    """Expand a norm reference into title-filter AND-groups.

    Returns (groups, resolved) where resolved is the _resolve_act() dict or
    None. Never guesses: an unresolved reference degrades to a literal search
    on the cleaned text, and the caller says so in the output.
    """
    text = riferimento.strip()
    act_part = _ART_PREFIX.sub("", text) or text

    resolved = _resolve_act(act_part)
    groups: list[list[str]] = []
    if resolved:
        tipo = resolved.get("tipo_atto", "")
        numero = resolved.get("numero_atto", "")
        anno = (resolved.get("data") or "")[:4]
        if "codice" in tipo or "costituzione" in tipo:
            groups.append([tipo])
        if numero and anno:
            groups.append([numero, anno])

    literal = _sanitize_phrase(act_part.lower())
    has_real_word = bool(re.search(r"[a-zàèéìòù]{4,}", literal))
    if literal and has_real_word and [literal] not in groups:
        groups.append([literal])

    return groups, resolved


# ---------------------------------------------------------------------------
# Impl functions (testable without MCP context)
# ---------------------------------------------------------------------------

async def _cerca_ddl_impl(
    query: str,
    legislatura: int = LEGISLATURA_CORRENTE,
    ramo: str = "",
    stato: str = "",
    solo_pendenti: bool = False,
    max_risultati: int = 10,
) -> SearchResult:
    max_risultati = max(1, min(max_risultati, 50))
    groups = [[chunk.strip()] for chunk in query.split(",") if chunk.strip()]
    if not groups:
        return SearchResult(
            success=False,
            source="parlamento",
            error_type="no_results",
            results_text="Indicare almeno una parola chiave da cercare nei titoli dei DDL.",
        )

    try:
        fasi = await search_ddl(
            groups,
            legislatura=legislatura,
            ramo=ramo,
            stato=stato,
            solo_pendenti=solo_pendenti,
            limit=max_risultati,
        )
    except NoValidSearchTerms as exc:
        return SearchResult(
            success=False, source="parlamento", error_type="no_results", results_text=str(exc),
        )
    except Exception as exc:
        return SearchResult(success=False, source="parlamento", error_type="source_down", error_message=str(exc))

    if not fasi:
        return SearchResult(
            success=False,
            source="parlamento",
            error_type="no_results",
            results_text=f"Nessun DDL trovato per: _{query}_ (legislatura {legislatura}).",
        )

    lines = [f"**Trovate {len(fasi)} fasi di DDL** (legislatura {legislatura})\n"]
    for fase in fasi:
        lines.append(format_fase(fase))
        lines.append("")
    lines.append("Per l'iter completo di un atto: `iter_ddl(atto)` con il numero (es. \"S.1939\").")
    return SearchResult(success=True, source="parlamento", num_found=len(fasi), results_text="\n".join(lines))


async def _iter_ddl_impl(
    atto: str,
    legislatura: int = LEGISLATURA_CORRENTE,
) -> SearchResult:
    try:
        kind, value = parse_atto_input(atto)
    except ValueError as exc:
        return SearchResult(
            success=False,
            source="parlamento",
            error_type="invalid_input",
            results_text=f"**Errore**: {exc}",
        )

    try:
        fasi = await fetch_iter(kind, value, legislatura=legislatura)
    except Exception as exc:
        return SearchResult(success=False, source="parlamento", error_type="source_down", error_message=str(exc))

    if not fasi:
        return SearchResult(
            success=False,
            source="parlamento",
            error_type="no_results",
            results_text=f"Nessun DDL trovato per _{atto}_ (legislatura {legislatura}).",
        )

    # Camera enrichment is a bonus: its failure must never sink the iter.
    # The legislature comes from the fase (data), not from the parameter.
    camera_details: dict[str, CameraIter] = {}
    for fase in fasi:
        if fase.ramo == "C" and "." in fase.fase:
            numero = fase.fase.split(".", 1)[1]
            try:
                camera = await fetch_camera_iter(numero, legislatura=fase.legislatura)
            except Exception:
                camera = None
            if camera:
                camera_details[numero] = camera

    return SearchResult(
        success=True,
        source="parlamento",
        num_found=len(fasi),
        results_text=format_iter(fasi, camera_details),
    )


async def _ddl_su_norma_impl(
    riferimento: str,
    legislatura: int = LEGISLATURA_CORRENTE,
    max_risultati: int = 10,
) -> SearchResult:
    max_risultati = max(1, min(max_risultati, 50))
    if not riferimento.strip():
        return SearchResult(
            success=False,
            source="parlamento",
            error_type="no_results",
            results_text="Indicare la norma di cui cercare i DDL modificativi.",
        )

    groups, resolved = _norma_search_groups(riferimento)
    if not groups:
        return SearchResult(
            success=False,
            source="parlamento",
            error_type="no_results",
            results_text=f"Impossibile derivare termini di ricerca da: _{riferimento}_.",
        )

    try:
        fasi = await search_ddl(groups, legislatura=legislatura, limit=max_risultati)
    except NoValidSearchTerms as exc:
        return SearchResult(
            success=False, source="parlamento", error_type="no_results", results_text=str(exc),
        )
    except Exception as exc:
        return SearchResult(success=False, source="parlamento", error_type="source_down", error_message=str(exc))

    if not fasi:
        return SearchResult(
            success=False,
            source="parlamento",
            error_type="no_results",
            results_text=(
                f"Nessun DDL trovato che citi nel titolo: _{riferimento}_ "
                f"(legislatura {legislatura}).\n{_CAVEAT_TITOLI}"
            ),
        )

    lines = [f"**DDL che citano nel titolo**: _{riferimento}_ (legislatura {legislatura})\n"]
    if resolved is None:
        lines.append(
            "_Riferimento non riconosciuto dal resolver: ricerca letterale sul testo indicato._\n"
        )
    lines.append(_CAVEAT_TITOLI + "\n")
    for fase in fasi:
        lines.append(format_fase(fase))
        lines.append("")
    return SearchResult(success=True, source="parlamento", num_found=len(fasi), results_text="\n".join(lines))


# ---------------------------------------------------------------------------
# MCP tool wrappers
# ---------------------------------------------------------------------------

@mcp.tool(tags={"parlamento", "normativa"})
async def cerca_ddl(
    query: str,
    legislatura: int = LEGISLATURA_CORRENTE,
    ramo: str = "",
    stato: str = "",
    solo_pendenti: bool = False,
    max_risultati: int = 10,
) -> str:
    """Cerca disegni di legge (DDL) per parole chiave nei titoli — dati.senato.it (entrambi i rami).

    USARE quando si parla di: DDL, disegni/proposte di legge, riforme pendenti,
    provvedimenti in Parlamento, iter legislativo su un tema. L'endpoint del Senato
    indicizza le fasi di ENTRAMBI i rami (S.* e C.*), quindi copre anche la Camera.
    Dopo aver trovato un atto, usare iter_ddl(atto) per la navette completa.
    Restituisce: fasi con numero atto, stato datato, iniziativa e link alle schede ufficiali.

    Args:
        query: Parole chiave da cercare nei titoli (virgola-separate per più frasi
            in OR, es. "intelligenza artificiale" o "affitti brevi, locazione turistica")
        legislatura: Legislatura (default 19, la corrente)
        ramo: Filtra per ramo in cui pende la fase ("S" Senato, "C" Camera) — default entrambi
        stato: Filtra per stato esatto (es. "esame in comm.", "all'esame assemblea",
            "approvato", "appr. definit. Legge")
        solo_pendenti: True per escludere le fasi concluse (approvate, respinte,
            ritirate, decadute) e vedere solo ciò che è ancora in corso
        max_risultati: Numero massimo di risultati (default 10, max 50)
    """
    result = await _cerca_ddl_impl(
        query=query, legislatura=legislatura, ramo=ramo, stato=stato,
        solo_pendenti=solo_pendenti, max_risultati=max_risultati,
    )
    return result.to_str() if isinstance(result, SearchResult) else result


@mcp.tool(tags={"parlamento", "normativa"})
async def iter_ddl(
    atto: str,
    legislatura: int = LEGISLATURA_CORRENTE,
) -> str:
    """Ricostruisce l'iter parlamentare completo (navette) di un disegno di legge.

    USARE dopo cerca_ddl() o quando si conosce già il numero dell'atto, per sapere
    a che punto è un DDL: fasi in ciascun ramo, stato datato di ognuna, estremi
    della legge se l'iter è concluso. Per le fasi alla Camera aggiunge la timeline
    di dettaglio (statoIter) e il PDF dello stampato da dati.camera.it.
    Restituisce: sequenza delle fasi con stati, date e link alle schede ufficiali.

    Args:
        atto: Numero dell'atto in un ramo (es. "S.1939", "C.3053", "AS 1939",
            "AC 3053") oppure l'idDdl numerico riportato da iter_ddl stesso
        legislatura: Legislatura (default 19, la corrente)
    """
    result = await _iter_ddl_impl(atto=atto, legislatura=legislatura)
    return result.to_str() if isinstance(result, SearchResult) else result


@mcp.tool(tags={"parlamento", "normativa"})
async def ddl_su_norma(
    riferimento: str,
    legislatura: int = LEGISLATURA_CORRENTE,
    max_risultati: int = 10,
) -> str:
    """Cerca DDL pendenti o conclusi che citano una norma nel titolo (riforme in corso).

    USARE per rispondere a "questa norma sta per cambiare?": trova i DDL il cui
    titolo cita l'atto indicato. Il riferimento è espanso tramite il resolver
    (nomi comuni, codici, estremi numerici). BEST-EFFORT dichiarato: è indicizzato
    solo il TITOLO dei DDL, non il testo — un DDL che modifica la norma senza
    citarla nel titolo non viene trovato; l'assenza di risultati NON prova
    l'assenza di riforme pendenti.
    Restituisce: fasi di DDL con stato datato e link alle schede ufficiali.

    Args:
        riferimento: Norma da cercare (es. "codice civile", "d.lgs. 196/2003",
            "statuto dei lavoratori", "art. 2043 c.c." — l'articolo viene ignorato
            nella ricerca, che avviene per atto)
        legislatura: Legislatura (default 19, la corrente)
        max_risultati: Numero massimo di risultati (default 10, max 50)
    """
    result = await _ddl_su_norma_impl(
        riferimento=riferimento, legislatura=legislatura, max_risultati=max_risultati,
    )
    return result.to_str() if isinstance(result, SearchResult) else result

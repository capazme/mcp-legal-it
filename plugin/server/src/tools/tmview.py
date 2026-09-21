"""MCP tools for searching TMview — the EUIPO/TMDN trademark database.

TRIGGER: usare quando l'utente chiede di marchi registrati, ricerca marchi,
anteriorità di un marchio, disponibilità di un nome/brand, marchi UIBM,
marchi UE (EUIPO), marchi internazionali (WIPO), classi di Nizza.
"""

from src.lib._result import SearchResult
from src.server import mcp
from src.lib.tmview.client import (
    STATI,
    TMviewBlockedError,
    _normalize_name,
    fetch_trademark,
    format_detail,
    format_result,
    search_trademarks,
)

_WAF_HINT = (
    "TMview sta limitando le richieste automatiche (protezione anti-bot). "
    "Riprova tra circa un minuto."
)

_DISCLAIMER_ANTERIORITA = (
    "*Verifica preliminare su denominazione (ricerca testuale TMview): non valuta "
    "somiglianza fonetica, concettuale o grafica né i marchi figurativi senza "
    "denominazione. Non sostituisce una ricerca di anteriorità professionale.*"
)


def _parse_uffici(uffici: str) -> list[str]:
    return [u.strip().upper() for u in uffici.split(",") if u.strip()]


def _parse_classi(classi_nizza: str) -> tuple[list[str] | None, str]:
    """Returns (classes, error). Nice classes run from 1 to 45."""
    classi = [c.strip() for c in classi_nizza.split(",") if c.strip()]
    for c in classi:
        if not c.isdigit() or not 1 <= int(c) <= 45:
            return None, (
                f"Classe di Nizza non valida: '{c}'. "
                "Le classi vanno da 1 a 45 (es. \"25\" abbigliamento, \"30\" alimentari)."
            )
    return classi, ""


def _parse_stato(stato: str) -> tuple[list[str] | None, str]:
    """Returns (statuses, error). Accepts Italian names or raw TMview codes."""
    if not stato.strip():
        return [], ""
    key = stato.strip().lower()
    if key in STATI:
        return [STATI[key]], ""
    if stato.strip() in STATI.values():
        return [stato.strip()], ""
    valid = ", ".join(STATI)
    return None, f"Stato non valido: '{stato}'. Valori ammessi: {valid}."


# ---------------------------------------------------------------------------
# Impl functions (testable without MCP context)
# ---------------------------------------------------------------------------

async def _cerca_marchi_impl(
    query: str,
    uffici: str = "",
    classi_nizza: str = "",
    stato: str = "",
    max_risultati: int = 20,
) -> SearchResult:
    max_risultati = max(1, min(max_risultati, 50))
    classi, err = _parse_classi(classi_nizza)
    if err:
        return SearchResult(success=False, source="tmview", error_type="no_results", results_text=err)
    statuses, err = _parse_stato(stato)
    if err:
        return SearchResult(success=False, source="tmview", error_type="no_results", results_text=err)

    try:
        total, docs = await search_trademarks(
            query,
            offices=_parse_uffici(uffici),
            nice_classes=classi,
            statuses=statuses,
            page_size=max_risultati,
        )
    except TMviewBlockedError:
        return SearchResult(success=False, source="tmview", error_type="source_down", error_message=_WAF_HINT)
    except Exception as exc:
        return SearchResult(success=False, source="tmview", error_type="source_down", error_message=str(exc))

    if not docs:
        return SearchResult(
            success=False,
            source="tmview",
            error_type="no_results",
            results_text=f"Nessun marchio trovato su TMview per: _{query}_",
        )

    lines = [f"**Trovati {total} marchi su TMview** (mostrati {len(docs)})\n"]
    for doc in docs:
        lines.append(format_result(doc))
        lines.append("")
    lines.append("*Per la scheda completa: leggi_marchio(st13).*")
    return SearchResult(success=True, source="tmview", num_found=total, results_text="\n".join(lines))


async def _leggi_marchio_impl(st13: str) -> SearchResult:
    try:
        detail = await fetch_trademark(st13.strip())
    except TMviewBlockedError:
        return SearchResult(success=False, source="tmview", error_type="source_down", error_message=_WAF_HINT)
    except Exception as exc:
        return SearchResult(success=False, source="tmview", error_type="source_down", error_message=str(exc))

    if not detail.name and not detail.application_number:
        return SearchResult(
            success=False,
            source="tmview",
            error_type="no_results",
            results_text=f"Nessun marchio trovato su TMview con ST13 `{st13}`.",
        )
    return SearchResult(success=True, source="tmview", num_found=1, results_text=format_detail(detail))


async def _verifica_anteriorita_marchio_impl(
    nome: str,
    classi_nizza: str = "",
    uffici: str = "",
    max_risultati: int = 50,
) -> SearchResult:
    max_risultati = max(1, min(max_risultati, 50))
    classi, err = _parse_classi(classi_nizza)
    if err:
        return SearchResult(success=False, source="tmview", error_type="no_results", results_text=err)

    try:
        total, docs = await search_trademarks(
            nome,
            offices=_parse_uffici(uffici),
            nice_classes=classi,
            page_size=max_risultati,
        )
    except TMviewBlockedError:
        return SearchResult(success=False, source="tmview", error_type="source_down", error_message=_WAF_HINT)
    except Exception as exc:
        return SearchResult(success=False, source="tmview", error_type="source_down", error_message=str(exc))

    if not docs:
        scope = f" nelle classi {classi_nizza}" if classi_nizza else ""
        lines = [
            f"**Nessun marchio anteriore trovato su TMview per** _{nome}_{scope}.",
            "",
            _DISCLAIMER_ANTERIORITA,
        ]
        return SearchResult(success=True, source="tmview", num_found=0, results_text="\n".join(lines))

    target = _normalize_name(nome)
    identici = [d for d in docs if _normalize_name(d.name) == target]
    simili = [d for d in docs if _normalize_name(d.name) != target]

    lines = [f"**Verifica anteriorità per** _{nome}_ — {total} marchi trovati su TMview\n"]
    if identici:
        lines.append(f"## Marchi identici ({len(identici)}) — rischio alto")
        for doc in identici:
            lines.append(format_result(doc))
            lines.append("")
    if simili:
        lines.append(f"## Marchi simili o contenenti il termine ({len(simili)})")
        for doc in simili:
            lines.append(format_result(doc))
            lines.append("")
    if total > len(docs):
        lines.append(f"*Mostrati i primi {len(docs)} di {total} risultati: restringere con classi_nizza o uffici.*")
    lines.append(_DISCLAIMER_ANTERIORITA)
    return SearchResult(success=True, source="tmview", num_found=total, results_text="\n".join(lines))


# ---------------------------------------------------------------------------
# MCP tool wrappers
# ---------------------------------------------------------------------------

@mcp.tool(tags={"marchi", "normativa"})
async def cerca_marchi(
    query: str,
    uffici: str = "",
    classi_nizza: str = "",
    stato: str = "",
    max_risultati: int = 20,
) -> str:
    """Cerca marchi registrati o depositati su TMview (EUIPO/TMDN) — UIBM, EUIPO, WIPO e ~75 uffici nazionali.

    USARE quando si parla di: ricerca marchi, marchio registrato, brand, marchi UIBM,
    marchi UE, marchi internazionali, chi è il titolare di un marchio, classi di Nizza.
    Dopo aver trovato un marchio, usare leggi_marchio(st13) per la scheda completa.
    Per valutare la disponibilità di un nome usare verifica_anteriorita_marchio(nome).
    Restituisce: lista marchi con ST13, ufficio, stato, titolare, classi di Nizza e date.

    Args:
        query: Denominazione o termine da cercare (es. "FUORI CORSO", "BARILLA")
        uffici: Codici ufficio separati da virgola (es. "IT" UIBM, "EM" EUIPO, "WO" WIPO,
            "IT,EM" per marchi efficaci in Italia) — default tutti gli uffici
        classi_nizza: Classi di Nizza separate da virgola (es. "25" abbigliamento,
            "30" alimentari, "25,43") — default tutte
        stato: Filtra per stato: "registrato", "depositato", "scaduto", "terminato" — default tutti
        max_risultati: Numero massimo di risultati (default 20, max 50)
    """
    result = await _cerca_marchi_impl(
        query=query, uffici=uffici, classi_nizza=classi_nizza, stato=stato, max_risultati=max_risultati,
    )
    return result.to_str() if isinstance(result, SearchResult) else result


@mcp.tool(tags={"marchi", "normativa"})
async def leggi_marchio(st13: str) -> str:
    """Legge la scheda completa di un marchio da TMview tramite identificativo ST13.

    Usare dopo cerca_marchi() o verifica_anteriorita_marchio() per i dettagli completi:
    titolare con nazionalità, rappresentante, descrizione prodotti/servizi per classe
    di Nizza, pubblicazioni, date di deposito/registrazione/scadenza, stato corrente.
    Restituisce: scheda completa del marchio dall'ufficio di origine.

    Args:
        st13: Identificativo ST13 del marchio, riportato in ogni risultato di ricerca
            (es. "IT502013902128590", "EM500000018203824")
    """
    result = await _leggi_marchio_impl(st13)
    return result.to_str() if isinstance(result, SearchResult) else result


@mcp.tool(tags={"marchi", "normativa"})
async def verifica_anteriorita_marchio(
    nome: str,
    classi_nizza: str = "",
    uffici: str = "",
    max_risultati: int = 50,
) -> str:
    """Verifica preliminare di anteriorità: cerca su TMview marchi identici o simili a un nome.

    USARE quando si parla di: disponibilità di un nome o brand, registrare un marchio,
    conflitto tra marchi, anteriorità, rischio di opposizione. Separa i marchi IDENTICI
    (denominazione coincidente, ignorando maiuscole/spazi/punteggiatura) dai SIMILI.
    NON valuta somiglianza fonetica/concettuale né marchi figurativi senza denominazione:
    è uno screening preliminare, non sostituisce la ricerca di anteriorità professionale.
    Restituisce: marchi identici (rischio alto) e simili, con classi di Nizza per valutare
    l'affinità merceologica.

    Args:
        nome: Denominazione da verificare (es. "FUORI CORSO")
        classi_nizza: Classi di Nizza di interesse separate da virgola (es. "25,43") —
            restringe la ricerca alle classi in cui si vuole depositare
        uffici: Codici ufficio separati da virgola (es. "IT,EM,WO" per l'Italia) —
            default tutti gli uffici
        max_risultati: Numero massimo di risultati esaminati (default 50, max 50)
    """
    result = await _verifica_anteriorita_marchio_impl(
        nome=nome, classi_nizza=classi_nizza, uffici=uffici, max_risultati=max_risultati,
    )
    return result.to_str() if isinstance(result, SearchResult) else result

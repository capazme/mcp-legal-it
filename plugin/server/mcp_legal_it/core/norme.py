"""Norm lookup logic shared by the MCP tools and the library API.

Pure logic per ADR-001: reference parsing, act resolution and the structured
article lookup. Nothing here imports FastMCP or ``mcp_legal_it.server``; the
tools in ``mcp_legal_it.tools.legal_citations`` add the Markdown on top.
Parsing and resolution live in ``core.riferimenti`` (stdlib only); their names
stay importable from here.
"""

import asyncio
import re

import httpx

from mcp_legal_it.lib import _clock
from mcp_legal_it.lib.visualex import Norma, NormaVisitata
from mcp_legal_it.lib.visualex.models import intervallo_articoli
from mcp_legal_it.lib.visualex.scraper import CHECK_UNAVAILABLE, fetch_article
from mcp_legal_it.core.riferimenti import (  # noqa: F401 - re-exported
    _ACT_FIRST_PATTERN,
    _ANNEX_AFTER_ARTICLE,
    _ANNEX_FIRST_PATTERN,
    _ANNEX_LAST,
    _EU_PATTERN,
    _IT_LONG_PATTERN,
    _IT_SHORT_PATTERN,
    _PARAGRAPH_PATTERN,
    _TIPO_CANONICO,
    _canonical_tipo,
    _parse_reference,
    _resolve_act,
    _split_eu_year_number,
    _strip_annex_link,
    _strip_paragraphs,
    _suggest_acts,
    _unresolved_act_error,
)


def _build_nv(act_info: dict, article: str) -> NormaVisitata:
    """Build a NormaVisitata from resolved act info + article number."""
    norma = Norma(
        tipo_atto=act_info["tipo_atto"],
        data=act_info.get("data", ""),
        numero_atto=act_info.get("numero_atto", ""),
        allegato=act_info.get("allegato", ""),  # Normattiva's ":k", VisuaLex's allegato (api._norme)
    )
    return NormaVisitata(norma=norma, numero_articolo=article)


def _urn_from_url(url: str) -> str | None:
    """Extract the URN from a Normattiva ``uri-res`` URL, else None.

    Normattiva citable URLs look like
    ``https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:...`` — the URN is
    the substring after the ``?``. Any other URL (EUR-Lex, etc.) has no URN.
    """
    if "normattiva.it/uri-res/N2Ls?" not in url:
        return None
    return url.split("?", 1)[1] or None


def _source_failure(exc: Exception) -> bool:
    """Whether an exception says the source is down, slow or limiting us (not that the norm is absent)."""
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code if exc.response is not None else 0
        return status == 429 or status >= 500
    return isinstance(exc, (httpx.TransportError, asyncio.TimeoutError))


def _failed_fetch(nv: NormaVisitata, exc: Exception) -> dict:
    result = {"text": "", "url": nv.url(), "source": "", "error": str(exc)}
    if _source_failure(exc):
        result["esito"] = CHECK_UNAVAILABLE
    return result


async def fetch_norma(nv: NormaVisitata, *, canale: str = "html") -> dict:
    """``fetch_article`` with a failure turned into the scraper's error shape, never raised."""
    try:
        return await fetch_article(nv, canale=canale)
    except Exception as e:
        return _failed_fetch(nv, e)


async def _cite_law_struct(reference: str) -> dict:
    """Structured article lookup (no Brocardi): the JSON face of cite_law."""
    return (await _cite_law_lookup(reference))[0]


async def _cite_law_lookup(reference: str, *, canale: str = "html") -> tuple[dict, str | None]:
    """The JSON face of cite_law, plus the outcome of the existence check.

    The outcome is ``ARTICLE_NOT_FOUND`` (the article is not in the act),
    ``CHECK_UNAVAILABLE`` (the source could not tell) or None.
    """
    base = _lookup_base(reference)
    article, act_name = _parse_reference(reference)
    if not act_name:
        base["errore"] = (f"impossibile interpretare il riferimento '{reference}'. "
                          "Formato atteso: 'art. <numero> <atto>'")
        return base, None
    act_info = _resolve_act(act_name)
    if not act_info:
        base["errore"] = _unresolved_act_error(act_name).replace("**Errore**: ", "")
        return base, None
    if (motivo := intervallo_articoli(article)) is not None:
        base["errore"] = motivo
        return base, None

    return await _lookup_visitata(base, _build_nv(act_info, article), act_info, canale=canale)


def _lookup_base(reference: str) -> dict:
    """The JSON face of cite_law before any lookup: every key, empty."""
    return {
        "formato": "json", "riferimento": reference, "articolo": "",
        "atto": {"tipo_atto": "", "data": "", "numero_atto": "", "descrizione": ""},
        "url": "", "urn": None, "fonte": "", "allegato": None, "testo": "", "errore": None,
        "data_consultazione": _clock.today().isoformat(),
        # What the reader must know about the text (the coming version Normattiva showed
        # without a date, the export's text, an unread window) and VisuaLex's "upcoming".
        "avvisi": [], "upcoming": None,
    }


async def lookup_parametri(act_info: dict, article: str, *, canale: str = "html") -> tuple[dict, str | None]:
    """``_cite_law_lookup`` for an act already resolved to ``{tipo_atto, data, numero_atto}``."""
    if (motivo := intervallo_articoli(article)) is not None:
        return {**_lookup_base(f"art. {article}"), "errore": motivo}, None
    reference = str(_build_nv(act_info, article))
    return await _lookup_visitata(_lookup_base(reference), _build_nv(act_info, article), act_info, canale=canale)


async def _lookup_visitata(base: dict, nv: NormaVisitata, act_info: dict, *,
                           canale: str = "html") -> tuple[dict, str | None]:
    """Fetch *nv* and fill *base* (see ``_cite_law_lookup``)."""
    article = nv.numero_articolo
    base["articolo"] = article or ""
    base["atto"] = {
        "tipo_atto": nv.norma.tipo_atto_normalized,
        "data": act_info.get("data", ""),
        "numero_atto": act_info.get("numero_atto", ""),
        "descrizione": str(nv.norma),
    }
    result = await fetch_norma(nv, canale=canale)
    base["url"] = result.get("url", "") or nv.url()
    base["urn"] = _urn_from_url(base["url"])
    # Cited with the year only, the act is queried as YYYY-01-01. The scraper replaces that
    # with the act's real date (from the Normattiva page); when it could not, the URL still
    # works but its date is a placeholder, so no URN is presented as the act's own.
    full_date = result.get("data_atto") or ""
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", full_date):
        base["atto"]["data"] = full_date
        base["atto"]["descrizione"] = str(Norma(tipo_atto=nv.norma.tipo_atto, data=full_date,
                                                numero_atto=nv.norma.numero_atto))
    elif base["urn"] and re.fullmatch(r"\d{4}", act_info.get("data", "") or ""):
        base["urn"] = None
    base["fonte"] = result.get("source", "") or ""
    base["allegato"] = result.get("allegato") or None
    base["testo"] = result.get("text", "") or ""
    if result.get("error"):
        base["errore"] = result["error"]
    elif not base["testo"]:
        base["errore"] = "nessun testo trovato"
    q = qualita_testo(base)
    base["avvisi"], base["upcoming"] = q["avvisi"], q["upcoming"]
    return base, result.get("esito")


def qualita_testo(base: dict) -> dict:
    """``{validita, precisione, avvisi, successione, upcoming}`` of a served text, with no request.

    LI-031: ESATTO only for the text of Normattiva's page whose validity the page states;
    the Akoma Ntoso export's text, or a page that does not say, is INDICATIVO. When the
    page without a date showed a version not in force yet, the text served is today's (the
    scraper asked for it) and the coming version is said: an avviso, and its repealing act
    as ``successione``, INDICATIVO, with the day Normattiva gives for it.
    """
    from mcp_legal_it.lib.visualex.scraper import abrogato_da as _abrogato_da
    from mcp_legal_it.lib.visualex.scraper import avviso_versione_futura, validita_pagina, versione_futura

    testo, fonte, url = base.get("testo") or "", base.get("fonte") or "", base.get("url") or ""
    if not testo or fonte not in ("normattiva", "normattiva-akn"):
        return {"validita": None, "precisione": None, "avvisi": [], "successione": None, "upcoming": None}
    # The validity is the served text's: the page's for the page's text, none for the export's.
    validita = validita_pagina(url) if fonte == "normattiva" else None
    avvisi: list[str] = []
    if fonte == "normattiva":
        precisione = "ESATTO" if validita else "INDICATIVO"
        if validita is None:
            avvisi.append("la pagina di Normattiva non indica la vigenza del testo: data di vigenza non verificata")
    else:
        precisione = "INDICATIVO"
        avvisi.append("testo dall'export Akoma Ntoso di Normattiva: vigenza non verificata sulla pagina")
    successione = None
    if (atto := _abrogato_da(testo)) is not None:
        successione = {"abrogato_da": atto, "precisione": "INDICATIVO", "fonte": "avviso di abrogazione nel testo"}
    futura = versione_futura(url)
    upcoming = ({"change": futura["change"], "valid_from": futura["valid_from"],
                 "version_number": futura["version_number"]} if futura else None)
    if futura:
        atto_futuro = _abrogato_da(futura["testo"])
        avvisi.append(avviso_versione_futura(futura))
        if atto_futuro and successione is None:
            successione = {"abrogato_da": atto_futuro, "dal": futura["valid_from"], "precisione": "INDICATIVO",
                           "fonte": "versione futura della pagina di Normattiva"}
    return {"validita": validita, "precisione": precisione, "avvisi": avvisi, "successione": successione,
            "upcoming": upcoming}


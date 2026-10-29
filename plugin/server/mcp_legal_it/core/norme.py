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
from mcp_legal_it.lib.visualex.models import intervallo_articoli, split_annex
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
        celex_consolidated=act_info.get("celex_consolidated", ""),  # an EU consolidation (api._norme)
    )
    # The text asked for: in force on a date, or the original (api._norme validates them).
    return NormaVisitata(norma=norma, numero_articolo=article, versione=act_info.get("versione", ""),
                         data_versione=act_info.get("data_versione", ""))


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


async def _cite_law_struct(reference: str, versione: str = "vigente") -> dict:
    """Structured article lookup (no Brocardi): the JSON face of cite_law."""
    return (await _cite_law_lookup(reference, versione=versione))[0]


async def _cite_law_lookup(reference: str, *, canale: str = "html",
                           versione: str = "vigente") -> tuple[dict, str | None]:
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

    if versione == "originale":
        act_info = {**act_info, "versione": "originale"}
    elif versione == "futura":
        act_info = {**act_info, "futura": True}
    from mcp_legal_it.lib.visualex.parti_normattiva import comma_richiesto

    return await _lookup_visitata(base, _build_nv(act_info, article), act_info, canale=canale,
                                  comma=comma_richiesto(reference))


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
        # VisuaLex's not_in_force: the text is the later one, asked for (versione="futura").
        "not_in_force": False,
        # The page's «AGGIORNAMENTO (n)» notes ([{numero, testo, ordine, corte_costituzionale}],
        # [] for none, None when the text is not a Normattiva page's), whether some could not be
        # read, and whether the text already carries them (note_aggiornamento below).
        "note_aggiornamento": None, "note_non_lette": False, "note_nel_testo": False,
        # An article Normattiva splits into parts («1 (commi 1-100)» …): the parts
        # ([{progressivo, commi_dal, commi_al, url}], [] when not split, None when the text is
        # not a Normattiva page's), the part the text is, and whether the text is one part only.
        "parti": None, "parte": None, "testo_parziale": False, "parte_non_letta": False,
        # An EU act's text: the consolidation read ({celex, data, modificato_da}, None for the
        # Official Journal text), and whether CELLAR was asked (False: it could not say).
        "consolidato": None, "consolidato_verificato": None,
    }


async def lookup_parametri(act_info: dict, article: str, *, canale: str = "html",
                           progressivo: int | None = None, comma: str | None = None) -> tuple[dict, str | None]:
    """``_cite_law_lookup`` for an act already resolved to ``{tipo_atto, data, numero_atto}``, for the library.

    *progressivo* or *comma*: the part to read of an article Normattiva splits (``con_parte``).
    """
    if (motivo := intervallo_articoli(article)) is not None:
        return {**_lookup_base(f"art. {article}"), "errore": motivo}, None
    reference = str(_build_nv(act_info, article))
    return await _lookup_visitata(_lookup_base(reference), _build_nv(act_info, article), act_info, canale=canale,
                                  progressivo=progressivo, comma=comma, per="api")


async def _lookup_visitata(base: dict, nv: NormaVisitata, act_info: dict, *,
                           canale: str = "html", comma: str | None = None,
                           progressivo: int | None = None, per: str = "mcp") -> tuple[dict, str | None]:
    """Fetch *nv* and fill *base* (see ``_cite_law_lookup``)."""
    article = nv.numero_articolo
    base["articolo"] = article or ""
    base["atto"] = {
        "tipo_atto": nv.norma.tipo_atto_normalized,
        "data": act_info.get("data", ""),
        "numero_atto": act_info.get("numero_atto", ""),
        "descrizione": str(nv.norma),
    }
    if act_info.get("futura"):
        # The text not in force yet, asked for explicitly (api._norme, versione="futura").
        result = await _fetch_futura(nv, act_info.get("futura_entro"))
    else:
        result = await fetch_norma(nv, canale=canale)
    result = await con_parte(result, nv.numero_articolo, comma=comma, progressivo=progressivo, per=per)
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
    base["consolidato"] = result.get("consolidato")
    base["consolidato_verificato"] = result.get("consolidato_verificato")
    if result.get("error"):
        base["errore"] = result["error"]
    elif not base["testo"]:
        base["errore"] = "nessun testo trovato"
    if result.get("not_in_force") and base["testo"]:
        # A text not in force yet is judged as a text at the day it comes into force, never as
        # the text in force: INDICATIVO, and said first.
        base["not_in_force"] = True
        act_info = futura_datata(act_info, result["upcoming"])
    q = qualita_testo(base, act_info, article)
    if base.get("not_in_force"):
        q = {**q, "precisione": "INDICATIVO", "avvisi": [avviso_non_in_vigore(result["upcoming"])] + q["avvisi"]}
    # An EU text's own notices (a consolidation not applicable yet, a day before the act
    # was in force) come from the lookup, after the notice of what the text is.
    base["avvisi"] = q["avvisi"] + (list(result.get("avvisi_ue") or []) if base["testo"] else [])
    if result.get("avviso_assenza"):
        # An article missing from the consolidation read: the outcome is «not found», and the
        # reader is told why and where the OJ text is.
        base["avvisi"].append(result["avviso_assenza"])
    # The source's own ``upcoming``: an EU consolidation to come, or a later Normattiva text
    # served (not_in_force).
    base["upcoming"] = q["upcoming"] or (result.get("upcoming") if base["testo"] else None)
    base["parti"], base["parte"] = result.get("parti"), result.get("parte")
    base["testo_parziale"] = bool(result.get("testo_parziale"))
    base["parte_non_letta"] = bool(result.get("parte_non_letta"))
    base["avvisi"] = list(base["avvisi"]) + list(result.get("avvisi_parti") or [])
    base["chiave_pagina"] = result.get("chiave_pagina")
    if result.get("errore_parte"):
        base["errore"], base["esito_parte"] = result["errore_parte"], result.get("esito_parte")
    note_aggiornamento(base)
    base.pop("chiave_pagina", None)
    return base, result.get("esito")


#: Said whenever a page's update notes could not all be read: the text alone may carry words
#: the Corte costituzionale struck down (art. 3 d.lgs. 23/2015 without C. cost. 194/2018).
AVVISO_NOTE_NON_LETTE = "note di aggiornamento non lette: verificare su Normattiva"


def note_della_pagina(fonte: str, testo: str, url: str,
                      chiave: str | None = None) -> "tuple[list[dict] | None, bool, bool]":
    """``(note, non_lette, nel_testo)`` of the Normattiva page a text was served from.

    Read with the page (``pagine_normattiva``, the record of the URL served): the page's
    «AGGIORNAMENTO (n)» notes as ``{numero, testo, ordine, corte_costituzionale}``, ``[]``
    for a page without notes. None when the text is not a Normattiva page's (an EU act,
    the Akoma Ntoso export, which carries its notes in the text). ``non_lette`` when a note,
    or the page's notes, could not be read; ``nel_testo`` when the text already carries them
    (a code's attachment), so a caller printing both does not print them twice.
    """
    if fonte != "normattiva" or not testo:
        return None, False, False
    from mcp_legal_it.lib.visualex import pagine_normattiva

    # *chiave*: the reading of the part served, for an article Normattiva splits.
    rec = pagine_normattiva.leggi(chiave or url or "")
    note = rec.get("note") if rec else None
    if not _note_ben_formate(note):
        return None, True, False  # a reading lost, or a record of another shape: unread, and said
    # A record missing a flag says «unread», never «nothing to read».
    return list(note["note"]), bool(note.get("non_lette", True)), bool(note.get("nel_testo", False))


def _note_ben_formate(note) -> bool:
    """Whether a kept reading's notes have the shape ``note_normattiva.leggi_note`` gives."""
    if not isinstance(note, dict) or not isinstance(note.get("note"), list):
        return False
    tipi = {"numero": str, "testo": str, "ordine": int, "corte_costituzionale": bool}
    return all(isinstance(n, dict) and set(n) == set(tipi) and all(isinstance(n[k], t) for k, t in tipi.items())
               for n in note["note"])


def note_aggiornamento(base: dict) -> None:
    """Put the served page's notes on *base* (``note_della_pagina``), with the notice when unread."""
    (base["note_aggiornamento"], base["note_non_lette"],
     base["note_nel_testo"]) = note_della_pagina(base.get("fonte", ""), base.get("testo", ""), base.get("url", ""),
                                                 base.get("chiave_pagina"))
    if base["note_non_lette"]:
        base["avvisi"] = list(base.get("avvisi") or []) + [AVVISO_NOTE_NON_LETTE]


async def _fetch_futura(nv: NormaVisitata, entro: "str | None") -> dict:
    """``fetch_article_futura`` with a failure turned into the scraper's error shape, never raised."""
    from mcp_legal_it.lib.visualex.scraper import fetch_article_futura

    try:
        return await fetch_article_futura(nv, entro)
    except Exception as e:
        return _failed_fetch(nv, e)


def futura_datata(act_info: dict, upcoming: dict) -> dict:
    """*act_info* of a text not in force yet, dated to the day it comes into force (as VisuaLex's
    ``norma_data``: ``versione`` "vigente", ``data_versione`` that day)."""
    info = {k: v for k, v in act_info.items() if k not in ("futura", "futura_entro")}
    return {**info, "versione": "vigente", "data_versione": upcoming["valid_from"]}


def avviso_non_in_vigore(upcoming: dict) -> str:
    """The first notice of a text not in force yet."""
    cambio = {"inserted": "inserito", "abrogated": "abrogato", "amended": "modificato"}.get(upcoming.get("change") or "")
    return (f"testo non ancora in vigore: entra in vigore il {upcoming['valid_from']}"
            + (f" (articolo {cambio} da quella data)" if cambio else "")
            + "; non è il testo vigente oggi")


def non_ancora_vigente(validita: dict, data_rich: "str | None") -> str:
    """The sentence for a page that says its article did not exist yet on the day asked for."""
    giorno = f"il {data_rich}" if data_rich else "alla data richiesta"
    entra = f": entra in vigore dopo il {validita['valid_to']}" if validita.get("valid_to") else ""
    return f"l'articolo non esisteva {giorno}{entra}"


def _qualita_ue(base: dict, act_info: "dict | None", article: str) -> dict:
    """``qualita_testo`` of an EU text (issue #50): ESATTO for the Official Journal text, which
    is authentic; INDICATIVO for a consolidation (EUR-Lex's documentation), for the OJ text
    when CELLAR could not say whether a consolidation exists, and for an OJ annex of an act
    that may have been amended. A treaty is unchanged (no precision)."""
    from mcp_legal_it.lib.visualex import eurlex_consolidate as ec
    from mcp_legal_it.lib.visualex.map import EURLEX_TREATY_CELEX

    vuoto = {"validita": None, "precisione": None, "avvisi": [], "successione": None, "upcoming": None}
    if ((base.get("atto") or {}).get("tipo_atto") or "").lower() in EURLEX_TREATY_CELEX:
        return vuoto
    consolidato, verificato = base.get("consolidato"), base.get("consolidato_verificato")
    allegato_oj = bool(split_annex(article)) and not consolidato
    avvisi = ec.avvisi(consolidato, verificato, (act_info or {}).get("data_versione") or None, allegato_oj)
    precisione = "INDICATIVO" if (consolidato or verificato is False or allegato_oj) else "ESATTO"
    return {**vuoto, "precisione": precisione, "avvisi": avvisi}


def qualita_testo(base: dict, act_info: "dict | None" = None, article: str = "") -> dict:
    """``{validita, precisione, avvisi, successione, upcoming}`` of a served text, with no request.

    LI-031: ESATTO only for the text of Normattiva's page whose validity the page states
    (and, for a text at a date, whose window holds that date); the Akoma Ntoso export's
    text, or a page that does not say, is INDICATIVO. Each channel is checked against the
    other wherever the other is already at hand (the page kept a day, the export in its
    cache, given *act_info* and *article*): a disagreement on the repeal is said, and so is
    an export consolidated at another day than the page's. When the page without a date
    showed a version not in force yet, the text served is today's (the scraper asked for
    it) and the coming version is said: an avviso, and its repealing act as
    ``successione``, INDICATIVO, with the day Normattiva gives for it.
    """
    from mcp_legal_it.lib.visualex import akn_fetch
    from mcp_legal_it.lib.visualex.akn_parser import is_abrogato
    from mcp_legal_it.lib.visualex.scraper import _akn_article, _vigenza_akn, senza_export
    from mcp_legal_it.lib.visualex.scraper import abrogato_da as _abrogato_da
    from mcp_legal_it.lib.visualex.scraper import avviso_versione_futura, validita_pagina, versione_futura
    from mcp_legal_it.lib.visualex.normattiva_validity import versions_between

    testo, fonte, url = base.get("testo") or "", base.get("fonte") or "", base.get("url") or ""
    if testo and fonte == "eurlex":
        return _qualita_ue(base, act_info, article)
    if not testo or fonte not in ("normattiva", "normattiva-akn"):
        return {"validita": None, "precisione": None, "avvisi": [], "successione": None, "upcoming": None}
    data_rich = (act_info or {}).get("data_versione") or None
    # The page's validity, kept with the page: the served text's when the text is the page's.
    validita_letta = validita_pagina(url, data_rich)
    validita = validita_letta if fonte == "normattiva" else None
    act = None
    if act_info is not None:
        nv = _build_nv(dict(act_info, data=(base.get("atto") or {}).get("data") or act_info.get("data", "")), article)
        act = None if senza_export(nv) else akn_fetch.cached_act(nv.norma, _vigenza_akn(nv))
    avvisi: list[str] = []
    if fonte == "normattiva":
        precisione = "ESATTO" if validita else "INDICATIVO"
        if validita is None:
            avvisi.append("la pagina di Normattiva non indica la vigenza del testo: data di vigenza non verificata")
        elif validita["state"] == "not_yet":
            # «NON ANCORA ESISTENTE O VIGENTE»: the page's text is a notice, not the article.
            precisione = "INDICATIVO"
            avvisi.append(non_ancora_vigente(validita, data_rich))
        elif data_rich and validita.get("request_in_window") is False:
            precisione = "INDICATIVO"
            avvisi.append(f"la pagina serve il testo in vigore dal {validita.get('valid_from') or '?'} al "
                          f"{validita.get('valid_to') or 'oggi'}, che non comprende il {data_rich}")
        akn_testo = _akn_article(act, nv.numero_articolo, None) if act is not None else None
        pagina_abrogata = validita is not None and validita["state"] == "abrogated"
        export_abrogato = is_abrogato(akn_testo) if akn_testo else None
    else:
        precisione = "INDICATIVO"
        consolidato = act.consolidato if act is not None else ""
        avvisi.append("testo dall'export Akoma Ntoso di Normattiva"
                      + (f" (consolidato al {consolidato})" if consolidato else "")
                      + ": vigenza non verificata sulla pagina")
        aggiornato = (validita_letta or {}).get("act_updated")
        if aggiornato and consolidato and aggiornato != consolidato:
            avvisi.append(f"l'export è consolidato al {consolidato}, la pagina dell'atto è aggiornata al "
                          f"{aggiornato}: i due testi possono non coincidere")
        pagina_abrogata = None if validita_letta is None else validita_letta["state"] == "abrogated"
        export_abrogato = is_abrogato(testo)
    if pagina_abrogata is not None and export_abrogato is not None and pagina_abrogata != export_abrogato:
        avvisi.append("i due canali di Normattiva non concordano sull'abrogazione: "
                      + ("la pagina dà l'articolo come abrogato, l'export Akoma Ntoso no"
                         if pagina_abrogata else "l'export Akoma Ntoso dà l'articolo come abrogato, la pagina no"))
    successione = None
    if (atto := _abrogato_da(testo)) is not None:
        successione = {"abrogato_da": atto, "precisione": "INDICATIVO", "fonte": "avviso di abrogazione nel testo"}
    futura = versione_futura(url) if not data_rich else None
    upcoming = ({"change": futura["change"], "valid_from": futura["valid_from"],
                 "version_number": futura["version_number"]} if futura else None)
    if futura and (tra := versions_between(futura["validita"], validita_letta)):
        # Other versions not in force yet come before it: Normattiva does not show them on their own.
        upcoming["versions_between"] = tra
    if futura:
        atto_futuro = _abrogato_da(futura["testo"])
        avvisi.append(avviso_versione_futura(futura))
        if atto_futuro and successione is None:
            successione = {"abrogato_da": atto_futuro, "dal": futura["valid_from"], "precisione": "INDICATIVO",
                           "fonte": "versione futura della pagina di Normattiva"}
    return {"validita": validita, "precisione": precisione, "avvisi": avvisi, "successione": successione,
            "upcoming": upcoming}



_COME_LEGGERE = {
    # The MCP tools read the comma from the reference.
    "mcp": "; per un comma, citarlo nel riferimento (es. «art. 1, comma 773, L. 296/2006»)",
    # The library: a reference string carries it too, else the part is read by its index.
    "api": ("; per un comma, indicarlo nel riferimento (es. «art. 1, comma 773, L. 296/2006») oppure "
            "leggerne la parte con parte_del_comma(parti, comma) e parte_articolo(riferimento, progressivo)"),
}


def avviso_parziale(parte: "dict | None", parti: list[dict], *, comma: bool, per: str = "mcp") -> str:
    """The notice of a text that is one part of an article Normattiva splits."""
    totale = parti[-1]["commi_al"] if parti else "?"
    if parte is None:
        quale = "una sola parte"
    else:
        quale = f"commi {parte['commi_dal']}-{parte['commi_al']}"
    testo = f"testo parziale: {quale} di {totale} (l'articolo è diviso in {len(parti)} parti su Normattiva)"
    if not comma:
        testo += _COME_LEGGERE[per]
    return testo


async def con_parte(result: dict, articolo: str, *, comma: str | None = None,
                    progressivo: int | None = None, per: str = "mcp") -> dict:
    """*result* with the part of a split article it should be, and what the reader must know.

    Normattiva serves a very long article in parts (art. 1 L. 296/2006: 14 pages of 100
    commi); the article's page is the first. With *comma*, the part holding it is read (one
    request more, none when it is the part served); with *progressivo* (``api.parte_articolo``)
    that part. Adds ``parti`` (the tree's parts, with their URL: they need the article page's
    session), ``parte``, ``testo_parziale`` and the notice; ``chiave_pagina`` names the
    reading of the part read, for its notes. A part that cannot be read leaves the text served,
    with a notice and ``parte_non_letta`` (a verifier then says «non verificata», never that
    the comma is missing); never another part's text in silence. A part read that does not
    show the comma's own line («773. …») is said too. *per* picks the notice's hint: the MCP
    tools (``"mcp"``) or the library (``"api"``).
    """
    if result.get("source") != "normattiva" or not result.get("text"):
        return {**result, "parti": None, "testo_parziale": False}
    from mcp_legal_it.lib.visualex import pagine_normattiva, parti_normattiva, scraper

    rec = pagine_normattiva.leggi(result.get("url") or "")
    if rec is None:
        return {**result, "parti": None, "testo_parziale": False}
    parti = list(rec.get("parti") or [])
    if not parti:
        out = {**result, "parti": [], "testo_parziale": False}
        if progressivo is not None:
            out.update(text="", esito_parte="riferimento_non_valido",
                       errore_parte=f"l'art. {articolo} non è diviso in parti su Normattiva")
        return out
    pubbliche = [{k: p[k] for k in ("progressivo", "commi_dal", "commi_al")}
                 | {"url": "https://www.normattiva.it" + p["path"]} for p in parti]
    servita = next((p for p in parti if p["progressivo"] == rec.get("parte_servita")), None)
    avvisi: list[str] = []
    voluta = None
    if progressivo is not None:
        voluta = next((p for p in parti if p["progressivo"] == progressivo), None)
        if voluta is None:
            return {**result, "text": "", "parti": pubbliche, "testo_parziale": False,
                    "esito_parte": "riferimento_non_valido",
                    "errore_parte": (f"l'art. {articolo} ha le parti {parti[0]['progressivo']}-"
                                     f"{parti[-1]['progressivo']} su Normattiva, non la {progressivo}")}
    elif comma:
        voluta = parti_normattiva.parte_del_comma(parti, comma)
        if voluta is None:
            avvisi.append(f"il comma {comma} non è in nessuna parte dell'art. {articolo} su Normattiva "
                          f"(commi {parti[0]['commi_dal']}-{parti[-1]['commi_al']})")
    out = {**result, "parti": pubbliche, "testo_parziale": True}
    parte = servita
    if voluta is not None and (servita is None or voluta["progressivo"] != servita["progressivo"]):
        try:
            letta = await scraper.leggi_parte(result["url"], voluta, articolo)
        except Exception as exc:  # noqa: BLE001 - the part asked for is missing: said, never another part's text
            if progressivo is not None:
                return {**out, "text": "", "esito_parte": "verifica_non_disponibile",
                        "errore_parte": (f"commi {voluta['commi_dal']}-{voluta['commi_al']} "
                                         f"dell'art. {articolo} non letti ({type(exc).__name__})")}
            avvisi.append(f"commi {voluta['commi_dal']}-{voluta['commi_al']} non letti ({type(exc).__name__}): "
                          "il testo è un'altra parte dell'articolo")
            out["parte_non_letta"] = True
        else:
            out.update(text=letta["text"], chiave_pagina=letta["chiave"])
            parte = voluta
    if comma and parte is not None and voluta is not None and parte is voluta \
            and not parti_normattiva.contiene_comma(out["text"], comma):
        # A «-bis» on a part's edge, or a tree that moved: the part read lacks the comma's line.
        avvisi.append(f"il comma {comma} non compare nella parte letta (commi {parte['commi_dal']}-"
                      f"{parte['commi_al']}): verificare su Normattiva")
    out["parte"] = ({k: parte[k] for k in ("progressivo", "commi_dal", "commi_al")}
                    | {"url": "https://www.normattiva.it" + parte["path"]}) if parte else None
    out["avvisi_parti"] = [avviso_parziale(parte, parti, comma=bool(comma) or progressivo is not None, per=per)] + avvisi
    return out

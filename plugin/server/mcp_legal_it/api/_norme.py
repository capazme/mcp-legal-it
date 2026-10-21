"""Norm functions of ``mcp_legal_it.api`` (see ``docs/api.md``)."""

from __future__ import annotations

import asyncio
import re
from typing import Iterable

from mcp_legal_it.api._comune import fonte_giu, registra
from mcp_legal_it.api.tipi import (
    AnnotazioniBrocardi,
    Canale,
    CatalogoAlias,
    EsitoRiferimento,
    IndiceAtto,
    MassimaBrocardi,
    NormaDati,
    TestoArticolo,
    TestoAtto,
)
from mcp_legal_it.core import norme
from mcp_legal_it.lib import _brocardi_switch, _clock
from mcp_legal_it.lib.visualex.map import (
    ATTI_NOTI,
    EURLEX,
    NORMATTIVA_SEARCH,
    codice_urn,
    known_act_names,
    normalize_act_type,
)
from mcp_legal_it.lib.visualex.article_suffixes import ARTICLE_SUFFIX_ALTERNATION as _ALTERNANZA_SUFFISSI
from mcp_legal_it.lib.visualex.models import Norma, annex_reference, intervallo_articoli, split_annex
from mcp_legal_it.lib.visualex.scraper import (
    ARTICLE_NOT_FOUND,
    CHECK_UNAVAILABLE,
    fetch_act_index,
    fetch_normattiva_full_text,
)

#: Latin ordinals that follow an article number, in the order of the law
#: (``bis`` = 2nd ... ``vicies`` = 20th), each with the other spellings Normattiva
#: prints. Built from the one table (``lib/visualex/article_suffixes.py``, imported
#: from VisuaLex and pinned to it); ``semel`` ("vicies semel", 21st) is in the
#: alternation below but is no ordinal of its own.
SUFFISSI_ARTICOLO: tuple[tuple[str, ...], ...] = (
    ("bis",), ("ter",), ("quater",), ("quinquies",), ("sexies",), ("septies",),
    ("octies",), ("novies", "nonies"), ("decies",), ("undecies",), ("duodecies",),
    ("terdecies",), ("quaterdecies",), ("quinquiesdecies", "quindecies"),
    ("sexiesdecies", "sexdecies"), ("septiesdecies",), ("octiesdecies", "duodevicies"),
    ("noviesdecies", "undevicies"), ("vicies", "vices"),
)

#: Regex alternation of every spelling, longest first (so ``quinquies`` never
#: shadows ``quinquiesdecies``): VisuaLex's, verbatim. Close the group with ``\b``:
#: ``rf"(\d+)-?({ARTICLE_SUFFIX_ALTERNATION})\b"``.
ARTICLE_SUFFIX_ALTERNATION: str = _ALTERNANZA_SUFFISSI

#: Italian act types Normattiva addresses by date and number (codes are known by name).
_TIPI_NOTI = frozenset(v.lower() for v in NORMATTIVA_SEARCH.values()) | frozenset(norme._TIPO_CANONICO.values())

_BROCARDI_SPENTO = (
    "Brocardi disattivato (LEGAL_BROCARDI=off nell'ambiente, o configurazione(brocardi=False)): "
    "nessuna richiesta a brocardi.it"
)

_NON_SUPPORTATA_HTML = (
    "canale 'html' (il lettore HTML congelato di VisuaLex): previsto dalla fase di migrazione, "
    "non ancora disponibile in questa versione"
)


# ---------------------------------------------------------------------------
# Reference reading (no network)
# ---------------------------------------------------------------------------


_ALLEGATO_URN = re.compile(r";[^;:~]+:(\w+)$")


def _allegato_predefinito(tipo_atto: str) -> str | None:
    """The annex a code's URN points at ("2" for the c.c., "1" for c.p. and c.p.c.), else None.

    VisuaLex keys a saved norm on urn|allegato|article, so the annex is given even
    when the citation does not name it.
    """
    urn = codice_urn(normalize_act_type(tipo_atto or "").lower())
    m = _ALLEGATO_URN.search(urn or "")
    return m.group(1) if m else None


def _con_allegato(tipo_atto: str, allegato: str | None, numero_articolo: str) -> str:
    """The article string for a lookup: an annex of the act, unless it is the code's own default annex."""
    if allegato and allegato != _allegato_predefinito(tipo_atto):
        return annex_reference(allegato, numero_articolo)
    return numero_articolo or ""


def _norma_dati(act_info: dict, article: str, *, data_atto: str = "", url: str = "",
                urn: str | None = None) -> NormaDati:
    """The NormaDati of a resolved act. A lookup passes the full date it read, its URL and URN."""
    info = dict(act_info)
    if data_atto:
        info["data"] = data_atto
    nv = norme._build_nv(info, article)
    url = url or nv.url()
    annex = split_annex(article)
    data = info.get("data", "") or ""
    eu = nv.norma._is_eurlex()
    if urn is None and not eu:
        # VisuaLex always gives the URN. An act cited with the year only whose date
        # could not be read keeps the one derived from its URL: its date is then a
        # placeholder, which data_risolta=False says.
        urn = norme._urn_from_url(url)
    return NormaDati(
        tipo_atto=nv.norma.tipo_atto_normalized,
        data=data,
        numero_atto=info.get("numero_atto", "") or "",
        url=url,
        allegato=annex[0] if annex else _allegato_predefinito(info.get("tipo_atto", "")),
        numero_articolo=annex[1] if annex else (article or ""),
        urn=urn,
        descrizione=str(nv.norma),
        # EU acts are cited by year by design; an Italian act's year alone is a placeholder.
        data_risolta=eu or not re.fullmatch(r"\d{4}", data),
    )


def _senza_tool(messaggio: str) -> str:
    """The resolver's message, pointing to this API instead of an MCP tool."""
    return messaggio.replace("**Errore**: ", "").replace(
        "usa fetch_law_article() con parametri espliciti", "usa riferimento_da_parametri()")


def _leggi(testo: str) -> tuple[dict, str] | EsitoRiferimento:
    """``(act_info, article)`` of a citation, or the EsitoRiferimento that says why not."""
    if not isinstance(testo, str):
        raise TypeError("il riferimento deve essere una stringa")
    article, act_name = norme._parse_reference(testo)
    if not act_name:
        return EsitoRiferimento(
            esito="riferimento_non_valido",
            errore=f"impossibile interpretare il riferimento '{testo}'. Formato atteso: 'art. <numero> <atto>'",
        )
    act_info = norme._resolve_act(act_name)
    if not act_info:
        return EsitoRiferimento(
            esito="atto_non_riconosciuto",
            errore=_senza_tool(norme._unresolved_act_error(act_name)),
        )
    if (motivo := intervallo_articoli(article)) is not None:
        return EsitoRiferimento(esito="riferimento_non_valido", errore=motivo)
    return act_info, article


def leggi_riferimento(testo: str) -> EsitoRiferimento:
    """Read a citation ("art. 2043 c.c.", "art. 6 GDPR") into a NormaDati. No network.

    Esiti: ``trovato`` (the act is identified; the article is not checked:
    ``testo_articolo`` does that), ``riferimento_non_valido``, ``atto_non_riconosciuto``.
    """
    letto = _leggi(testo)
    if isinstance(letto, EsitoRiferimento):
        return letto
    act_info, article = letto
    return EsitoRiferimento(esito="trovato", norma_data=(_norma_dati(act_info, article),))


def riferimento_da_parametri(
    tipo_atto: str,
    numero_articolo: str = "",
    data: str = "",
    numero_atto: str = "",
    allegato: str | None = None,
    versione: str = "vigente",
    data_versione: str | None = None,
) -> EsitoRiferimento:
    """A NormaDati from explicit fields (VisuaLex request body: act_type, article, ...). No network.

    Only ``versione="vigente"`` without ``data_versione`` is served in this version;
    other versions answer ``non_supportata`` (vigenza phase).
    """
    if versione != "vigente" or data_versione:
        return EsitoRiferimento(
            esito="non_supportata",
            errore="versioni diverse dalla vigente: previste dalla fase vigenza, non ancora disponibili",
        )
    if not tipo_atto or not tipo_atto.strip():
        return EsitoRiferimento(esito="riferimento_non_valido", errore="tipo_atto mancante")
    norm = normalize_act_type(tipo_atto.strip()).lower()
    if not (norm in EURLEX or codice_urn(norm) or norm in _TIPI_NOTI):
        return EsitoRiferimento(
            esito="atto_non_riconosciuto",
            errore=f"tipo d'atto '{tipo_atto}' non riconosciuto: usa il nome esteso ('decreto legislativo') "
                   "o leggi_riferimento() con la citazione",
        )
    if norm in ("regolamento ue", "direttiva ue") and not (data and numero_atto):
        return EsitoRiferimento(esito="riferimento_non_valido",
                                errore="per un atto UE servono anno (data) e numero_atto")
    if (motivo := intervallo_articoli(numero_articolo)) is not None:
        return EsitoRiferimento(esito="riferimento_non_valido", errore=motivo)
    article = _con_allegato(tipo_atto, allegato, numero_articolo)
    act_info = {"tipo_atto": tipo_atto.strip(), "data": data or "", "numero_atto": numero_atto or ""}
    nv = norme._build_nv(act_info, article)
    if not nv.url():
        return EsitoRiferimento(
            esito="riferimento_non_valido",
            errore=f"nessun indirizzo per '{nv.norma}': indicare data e numero dell'atto",
        )
    return EsitoRiferimento(esito="trovato", norma_data=(_norma_dati(act_info, article),))


def _act_info(norma: NormaDati) -> tuple[dict, str]:
    article = _con_allegato(norma.tipo_atto, norma.allegato, norma.numero_articolo)
    return {"tipo_atto": norma.tipo_atto, "data": norma.data, "numero_atto": norma.numero_atto}, article


# ---------------------------------------------------------------------------
# Article text
# ---------------------------------------------------------------------------


def _esito_lookup(base: dict, esito: str | None) -> str:
    if not base.get("errore"):
        return "trovato"
    if esito == ARTICLE_NOT_FOUND:
        return "articolo_non_trovato"
    if esito == CHECK_UNAVAILABLE:
        return "verifica_non_disponibile"
    if base["errore"] == "nessun testo trovato":
        return "testo_assente"
    return "errore_fonte"


async def testo_articolo(riferimento: str | NormaDati, *, canale: Canale) -> TestoArticolo:
    """The text in force of one article, from Normattiva or EUR-Lex.

    *canale* is required: ``"akn"`` is mcp-legal-it's pipeline (``fonte`` says whether
    the Akoma Ntoso export or the HTML reader served the text); ``"html"`` (VisuaLex's
    frozen reader) answers ``non_supportata`` until the migration phase.

    Esiti: ``trovato``, ``riferimento_non_valido``, ``atto_non_riconosciuto``,
    ``articolo_non_trovato``, ``verifica_non_disponibile``, ``testo_assente``,
    ``errore_fonte``, ``non_supportata``. ``validity`` is ``None`` until the vigenza phase.
    """
    if canale not in ("akn", "html"):
        raise ValueError(f"canale sconosciuto: {canale!r} (attesi 'akn' o 'html')")
    oggi = _clock.today().isoformat()
    if isinstance(riferimento, NormaDati):
        act_info, article = _act_info(riferimento)
    else:
        letto = _leggi(riferimento)
        if isinstance(letto, EsitoRiferimento):
            return TestoArticolo(esito=letto.esito, article_text="", norma_data=None, url="",
                                 canale=canale, data_consultazione=oggi, errore=letto.errore)
        act_info, article = letto
    if canale == "html":
        nd = _norma_dati(act_info, article)
        return TestoArticolo(esito="non_supportata", article_text="", norma_data=nd, url=nd.url, urn=nd.urn,
                             canale=canale, data_consultazione=oggi, errore=_NON_SUPPORTATA_HTML)
    with registra() as registro:
        base, esito = await norme.lookup_parametri(act_info, article)
        nd = _norma_dati(act_info, article, data_atto=base["atto"]["data"], url=base["url"], urn=base["urn"])
        return TestoArticolo(
            esito=_esito_lookup(base, esito),
            article_text=base["testo"],
            norma_data=nd,
            url=base["url"],
            validity=None,
            urn=nd.urn,
            fonte=base["fonte"],
            canale=canale,
            data_consultazione=base["data_consultazione"],
            errore=base["errore"],
            fonti=registro.fonti(),
        )


async def testi_articoli(
    riferimenti: Iterable[str | NormaDati], *, canale: Canale, concorrenza: int = 4,
) -> list[TestoArticolo]:
    """``testo_articolo`` for many articles, in input order, at most *concorrenza* at a time.

    Articles of the same act share one download of the act (in-flight dedupe).
    """
    if concorrenza < 1:
        raise ValueError("concorrenza deve essere almeno 1")
    semaforo = asyncio.Semaphore(concorrenza)

    async def uno(rif):
        async with semaforo:
            return await testo_articolo(rif, canale=canale)

    return list(await asyncio.gather(*(uno(r) for r in riferimenti)))


# ---------------------------------------------------------------------------
# Whole act, index
# ---------------------------------------------------------------------------

#: "1-  Soggetti", "2-bis- Titolo": an index line that is an article and its heading.
_VOCE_ARTICOLO = re.compile(rf"^(\d+(?:-(?:{ARTICLE_SUFFIX_ALTERNATION}))?)-\s*(.*\S)\s*$", re.IGNORECASE)


def _atto(atto: str | NormaDati) -> Norma | tuple[str, str]:
    """The Norma of an act given by name or NormaDati, or ``(esito, errore)``."""
    if isinstance(atto, NormaDati):
        info, _ = _act_info(atto)
    else:
        _, act_name = norme._parse_reference(atto)
        if not act_name:
            return "riferimento_non_valido", f"impossibile interpretare il riferimento '{atto}'."
        info = norme._resolve_act(act_name)
        if not info:
            return "atto_non_riconosciuto", _senza_tool(norme._unresolved_act_error(act_name))
    return Norma(tipo_atto=info["tipo_atto"], data=info.get("data", ""), numero_atto=info.get("numero_atto", ""))


async def indice_atto(atto: str | NormaDati) -> IndiceAtto:
    """The article headings of an Italian act (Normattiva ``vediRubriche``).

    ``rubriche`` maps each article key to its heading where the index line reads as one;
    ``voci`` keeps every line as served. ``abrogati`` and ``parts`` are planned (migration).
    Esiti: ``trovato``, ``riferimento_non_valido``, ``atto_non_riconosciuto``,
    ``non_supportata`` (EU acts), ``verifica_non_disponibile``, ``errore_fonte``, ``testo_assente``.
    """
    norma = _atto(atto)
    if isinstance(norma, tuple):
        return IndiceAtto(esito=norma[0], errore=norma[1])
    if norma._is_eurlex():
        return IndiceAtto(esito="non_supportata", errore="indice disponibile solo per gli atti su Normattiva")
    with registra() as registro:
        try:
            result = await fetch_act_index(norma)
        except Exception as exc:  # noqa: BLE001 - errors are data
            esito = "verifica_non_disponibile" if fonte_giu(exc) else "errore_fonte"
            return IndiceAtto(esito=esito, url=norma.url(), errore=str(exc), fonti=registro.fonti())
        voci = tuple(result.get("index", []) or [])
        if result.get("error"):
            return IndiceAtto(esito="errore_fonte", url=result.get("url", ""), errore=result["error"],
                              fonti=registro.fonti())
        rubriche: dict[str, str] = {}
        for voce in voci:
            m = _VOCE_ARTICOLO.match(voce)
            if m:
                rubriche.setdefault(m.group(1).lower(), m.group(2))
        return IndiceAtto(
            esito="trovato" if voci else "testo_assente",
            rubriche=rubriche,
            count=len(rubriche),
            voci=voci,
            codice_redazionale=result.get("codice_redazionale", ""),
            data_gu=result.get("data_gu", ""),
            url=result.get("url", ""),
            errore=None if voci else "indice vuoto",
            fonti=registro.fonti(),
        )


async def testo_atto(atto: str | NormaDati) -> TestoAtto:
    """The whole text of an Italian act from Normattiva (EU acts: ``non_supportata``)."""
    norma = _atto(atto)
    if isinstance(norma, tuple):
        return TestoAtto(esito=norma[0], errore=norma[1])
    if norma._is_eurlex():
        return TestoAtto(esito="non_supportata", errore="testo integrale disponibile solo per gli atti su Normattiva")
    with registra() as registro:
        try:
            result = await fetch_normattiva_full_text(norma)
        except Exception as exc:  # noqa: BLE001 - errors are data
            esito = "verifica_non_disponibile" if fonte_giu(exc) else "errore_fonte"
            return TestoAtto(esito=esito, url=norma.url(), errore=str(exc), fonti=registro.fonti())
        if result.get("error"):
            return TestoAtto(esito="errore_fonte", url=result.get("url", ""), errore=result["error"],
                             fonti=registro.fonti())
        testo = result.get("text", "") or ""
        if len(testo) < 50:
            return TestoAtto(esito="testo_assente", url=result.get("url", ""), errore="testo insufficiente",
                             fonti=registro.fonti())
        return TestoAtto(esito="trovato", testo=testo, titolo=result.get("title", str(norma)),
                         url=result.get("url", ""), fonti=registro.fonti())


# ---------------------------------------------------------------------------
# Brocardi, aliases
# ---------------------------------------------------------------------------


async def annotazioni_brocardi(riferimento: str) -> AnnotazioniBrocardi:
    """Brocardi notes on an article: ratio, explanation, brocardi, case-law abstracts.

    Third-party editorial content, never the norm. Honours the Brocardi switch:
    off (``LEGAL_BROCARDI=off``, ``configurazione(brocardi=False)``) answers
    ``brocardi_disattivato`` without any request.
    """
    from mcp_legal_it.lib.brocardi.client import fetch_brocardi

    letto = _leggi(riferimento)
    if isinstance(letto, EsitoRiferimento):
        return AnnotazioniBrocardi(esito=letto.esito, errore=letto.errore)
    act_info, article = letto
    if not article:
        return AnnotazioniBrocardi(esito="riferimento_non_valido", errore="specificare un articolo")
    if split_annex(article):
        return AnnotazioniBrocardi(esito="non_supportata", errore="Brocardi non annota gli allegati")
    if not _brocardi_switch.enabled():
        return AnnotazioniBrocardi(esito="brocardi_disattivato", errore=_BROCARDI_SPENTO)
    with registra() as registro:
        try:
            r = await fetch_brocardi(act_info["tipo_atto"], article, act_info.get("numero_atto", ""),
                                     act_info.get("data", ""))
        except Exception as exc:  # noqa: BLE001 - errors are data
            return AnnotazioniBrocardi(esito="errore_fonte", errore=str(exc), fonti=registro.fonti())
        if r.error:
            esito = "brocardi_disattivato" if not _brocardi_switch.enabled() else "errore_fonte"
            return AnnotazioniBrocardi(esito=esito, url=r.url, errore=r.error, fonti=registro.fonti())
        massime = tuple(
            MassimaBrocardi(autorita=m.autorita or "", numero=m.numero or "", anno=m.anno or "", testo=m.testo)
            for m in r.massime
        )
        vuoto = not (r.ratio or r.spiegazione or r.brocardi or massime)
        return AnnotazioniBrocardi(
            esito="testo_assente" if vuoto else "trovato",
            url=r.url, ratio=r.ratio, spiegazione=r.spiegazione, brocardi=tuple(r.brocardi), massime=massime,
            fonti=registro.fonti(),
        )


def catalogo_alias() -> CatalogoAlias:
    """The act names the resolver knows (VisuaLex ``/fetch_alias_catalog`` shape). No network.

    ``presets`` are the hand-verified short names (GDPR, AI Act, TUB ...) with their
    act; ``known_acts`` every name ``leggi_riferimento`` recognises.
    """
    presets: dict[str, dict[str, str]] = {}
    for trigger, info in sorted(ATTI_NOTI.items()):
        voce = {"act_type": info["tipo_atto"]}
        if info.get("numero_atto"):
            voce["act_number"] = info["numero_atto"]
        if info.get("data"):
            voce["date"] = info["data"]
        presets[trigger] = voce
    return CatalogoAlias(presets=presets, known_acts=tuple(sorted(known_act_names())))


__all__ = [
    "ARTICLE_SUFFIX_ALTERNATION",
    "SUFFISSI_ARTICOLO",
    "annotazioni_brocardi",
    "catalogo_alias",
    "indice_atto",
    "leggi_riferimento",
    "riferimento_da_parametri",
    "testi_articoli",
    "testo_articolo",
    "testo_atto",
]

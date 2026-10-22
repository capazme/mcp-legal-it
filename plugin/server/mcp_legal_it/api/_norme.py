"""Norm functions of ``mcp_legal_it.api`` (see ``docs/api.md``)."""

from __future__ import annotations

import asyncio
import re
from typing import Iterable

from mcp_legal_it.api._comune import fonte_giu, registra
from mcp_legal_it.api.tipi import (
    AlberoAtto,
    AnnotazioniBrocardi,
    Canale,
    CatalogoAlias,
    EsitoRiferimento,
    IndiceAtto,
    MassimaBrocardi,
    NormaDati,
    TestoArticolo,
    TestoAtto,
    Vigenza,
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
from mcp_legal_it.lib.visualex import albero_normattiva as _albero
from mcp_legal_it.lib.visualex.article_suffixes import ARTICLE_SUFFIX_ALTERNATION as _ALTERNANZA_SUFFISSI
from mcp_legal_it.lib.visualex.models import Norma, annex_reference, intervallo_articoli, split_annex
from mcp_legal_it.lib.visualex.scraper import (
    ARTICLE_NOT_FOUND,
    CHECK_UNAVAILABLE,
    fetch_act_index,
    fetch_act_tree,
    fetch_normattiva_full_text,
)

#: Latin ordinals that follow an article number, in the order of the law
#: (``bis`` = 2nd ... ``vicies`` = 20th), each with the other spellings Normattiva
#: prints: the spellings of the one table (``lib/visualex/article_suffixes.py``,
#: imported from VisuaLex and pinned to it) grouped by ordinal, which
#: ``tests/unit/test_article_suffixes.py`` checks; ``semel`` ("vicies semel", 21st)
#: is in the alternation below but is no ordinal of its own.
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

# ---------------------------------------------------------------------------
# Reference reading (no network)
# ---------------------------------------------------------------------------


_ALLEGATO_URN = re.compile(r";[^;:~]+:(\w+)$")


#: PROVISIONAL (depends on a decision open on VisuaLex's side, see docs/api.md §8).
#: Codes whose URN gained its ":1" on 21/10/2026 (their articles sit in an annex of the
#: approving decree; the row served the decree's own articles). VisuaLex's table still has
#: them without it, so its saved norms carry no allegato: norma_data mirrors that, and the
#: part is in the URN only. The three acts of ARTICOLATO_IN_ALLEGATO (c.p.p. minorile,
#: TULPS, TU successioni) are not codes of the table and carry none either. Nor do the two
#: military codes added on 21/10/2026 (di pace :1, di guerra :2): VisuaLex has no row for
#: them, so no saved norm of its carries an allegato.
_PARTE_SOLO_NELL_URN = frozenset({
    "codice del turismo",
    "codici penali militari di pace e di guerra",
    "codice penale militare di pace",
    "codice penale militare di guerra",
    "norme di attuazione, di coordinamento e transitorie del codice di procedura penale",
    "approvazione del regolamento per l'esecuzione del codice della navigazione (navigazione marittima)",
})


def _allegato_predefinito(tipo_atto: str) -> str | None:
    """The annex a code's URN points at ("2" for the c.c., "1" for c.p. and c.p.c.), else None.

    VisuaLex keys a saved norm on urn|allegato|article, so the annex is given even
    when the citation does not name it — as VisuaLex gives it today, nothing more
    (``_PARTE_SOLO_NELL_URN``).
    """
    norm = normalize_act_type(tipo_atto or "").lower()
    if norm in _PARTE_SOLO_NELL_URN:
        return None
    urn = codice_urn(norm)
    m = _ALLEGATO_URN.search(urn or "")
    return m.group(1) if m else None


def _normattiva(tipo_atto: str) -> bool:
    return normalize_act_type(tipo_atto or "").lower() not in EURLEX


def _posizionale(tipo_atto: str, allegato: str | None) -> bool:
    """Whether *allegato* is Normattiva's number for a part (the URN's ``:k``), not an annex's name.

    VisuaLex's ``allegato`` is that number (``generate_urn`` writes ``;104:2``), and so is
    this API's: d.lgs. 104/2010 ``allegato="2"`` is the codice del processo amministrativo,
    the act's "Allegato 1". A name the act gives ("I.7") stays a name, and so does any
    allegato of an EU act: EUR-Lex URLs have no part, an EU annex is read by its name.
    """
    return bool(allegato) and allegato.isdigit() and _normattiva(tipo_atto)


#: A part number as Normattiva writes it: a positive integer, no leading zero.
_NUMERO_PARTE = re.compile(r"[1-9]\d*")


def _allegato_non_valido(tipo_atto: str, allegato: str | None) -> str | None:
    """The error for a positional allegato Normattiva cannot have ("0", "02"), else None."""
    if _posizionale(tipo_atto, allegato) and not _NUMERO_PARTE.fullmatch(allegato):
        return (f"allegato '{allegato}' non valido: il numero della parte dell'atto su Normattiva "
                "è un intero da 1 in su, senza zeri iniziali")
    return None


def _con_allegato(tipo_atto: str, allegato: str | None, numero_articolo: str) -> str:
    """The article string for a lookup: an annex the act names, unless it is the code's own default annex.

    A positional ``allegato`` is not in the article string: it goes into the URL (``_parte``).
    """
    if allegato and not _posizionale(tipo_atto, allegato) and allegato != _allegato_predefinito(tipo_atto):
        return annex_reference(allegato, numero_articolo)
    return numero_articolo or ""


def _parte(tipo_atto: str, allegato: str | None) -> str:
    """The positional part to put in the URL (``Norma.allegato``), "" for the act's default."""
    if _posizionale(tipo_atto, allegato) and allegato != _allegato_predefinito(tipo_atto):
        return allegato
    return ""



def _norma_dati(act_info: dict, article: str, *, data_atto: str = "", url: str = "",
                urn: str | None = None) -> NormaDati:
    """The NormaDati of a resolved act. A lookup passes the full date it read, its URL and URN."""
    info = dict(act_info)
    if data_atto:
        info["data"] = data_atto
    nv = norme._build_nv(info, article)
    url = url or nv.url()
    annex = split_annex(article)
    # allegato mirrors what VisuaLex gives the norm: the position the caller asked for, a
    # code's default part, or none. The part an answer was served from is in url and urn
    # only (";104:2~art120" for art. 120 d.lgs. 104/2010): putting it here would change
    # the key VisuaLex files the norm under.
    if annex and _posizionale(info.get("tipo_atto", ""), annex[0]):
        # "allegato 1 al d.lgs. 104/2010" names the act's own Allegato 1, which Normattiva
        # numbers :2. Read back as an allegato it would be taken for position 1, so the
        # reference keeps the annex in the article until a lookup gives the position.
        allegato, numero = None, article
    elif annex:
        allegato, numero = annex
    else:
        allegato = info.get("allegato") or _allegato_predefinito(info.get("tipo_atto", ""))
        numero = article or ""
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
        allegato=allegato,
        numero_articolo=numero,
        versione=info.get("versione") or "vigente",
        data_versione=info.get("data_versione") or None,
        urn=urn,
        celex_consolidated=info.get("celex_consolidated") or None,
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
    celex_consolidated: str | None = None,
) -> EsitoRiferimento:
    """A NormaDati from explicit fields (VisuaLex request body: act_type, article, ...). No network.

    ``celex_consolidated`` names a consolidated version of an EU regulation or directive by
    its sector-0 CELEX ("02002L0058-20091219"); it must be that act's (year, type, number).

    ``data_versione`` ("YYYY-MM-DD", or the Italian long form) asks for the text in force on
    that day, with ``versione`` "vigente" or None alike; ``versione="originale"`` for the
    original text. A future day, a date with "originale", another ``versione`` are
    ``riferimento_non_valido``; a version of an EU act or of an annex is ``non_supportata``.
    """
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
    if (motivo := _allegato_non_valido(tipo_atto, allegato)) is not None:
        return EsitoRiferimento(esito="riferimento_non_valido", errore=motivo)
    letta = _versione(tipo_atto, versione, data_versione)
    if isinstance(letta, EsitoRiferimento):
        return letta
    consolidato = _consolidato(tipo_atto, data, numero_atto, celex_consolidated)
    if isinstance(consolidato, EsitoRiferimento):
        return consolidato
    article = _con_allegato(tipo_atto, allegato, numero_articolo)
    if letta and split_annex(article):
        return EsitoRiferimento(esito="non_supportata", errore=_ALLEGATO_A_UNA_DATA)
    if consolidato and (motivo := _non_nel_consolidato(article)):
        return EsitoRiferimento(esito="non_supportata", errore=motivo)
    act_info = {"tipo_atto": tipo_atto.strip(), "data": data or "", "numero_atto": numero_atto or ""}
    if parte := _parte(tipo_atto, allegato):
        act_info["allegato"] = parte
    act_info.update(letta)
    if consolidato:
        act_info["celex_consolidated"] = consolidato
    nv = norme._build_nv(act_info, article)
    if not nv.url():
        return EsitoRiferimento(
            esito="riferimento_non_valido",
            errore=f"nessun indirizzo per '{nv.norma}': indicare data e numero dell'atto",
        )
    return EsitoRiferimento(esito="trovato", norma_data=(_norma_dati(act_info, article),))


_ALLEGATO_A_UNA_DATA = "il testo di un allegato a una data non è ancora disponibile"


def _versione(tipo_atto: str, versione: str | None, data_versione: str | None) -> dict | EsitoRiferimento:
    """``{"versione", "data_versione"}`` for a lookup ({} for today's text), or the refusal.

    A date always means "the text in force on that day" (``!vig=``), with or without
    ``versione="vigente"``. VisuaLex's ``generate_urn`` reads the date only together with
    "vigente", and a date sent without it gets today's text under the date asked for
    (art. 1284 c.c. "at 2010-01-01" came back with the 4th and 5th commi of 2014). This
    API does not follow it there until VisuaLex #276 lands, which adopts the same rule
    (docs/api.md).
    """
    from mcp_legal_it.lib.visualex.normattiva_validity import _iso_day

    nome = (versione or "vigente").strip().lower()
    if nome not in ("vigente", "originale"):
        return EsitoRiferimento(esito="riferimento_non_valido",
                                errore=f"versione '{versione}' non valida: attese 'vigente' o 'originale'")
    if not data_versione and nome == "vigente":
        return {}
    if not _normattiva(tipo_atto):
        return EsitoRiferimento(esito="non_supportata",
                                errore="versioni a una data disponibili solo per gli atti su Normattiva")
    if nome == "originale":
        if data_versione:
            return EsitoRiferimento(esito="riferimento_non_valido",
                                    errore="data_versione e versione 'originale' si escludono")
        return {"versione": "originale"}
    giorno = _iso_day(data_versione)
    if giorno is None:
        return EsitoRiferimento(esito="riferimento_non_valido",
                                errore=f"data_versione '{data_versione}' non è una data (atteso AAAA-MM-GG)")
    if giorno > _clock.today().isoformat():
        # Normattiva answers a future date with today's text and says nothing.
        return EsitoRiferimento(esito="riferimento_non_valido",
                                errore=("data_versione non può essere futura: Normattiva restituirebbe il "
                                        "testo attuale, non quello alla data richiesta"))
    return {"versione": "vigente", "data_versione": giorno}


def _act_info(norma: NormaDati) -> "tuple[dict, str] | EsitoRiferimento":
    """The lookup's act info and article for *norma*, or the refusal of its version."""
    letta = _versione(norma.tipo_atto, norma.versione, norma.data_versione)
    if isinstance(letta, EsitoRiferimento):
        return letta
    consolidato = _consolidato(norma.tipo_atto, norma.data, norma.numero_atto, norma.celex_consolidated)
    if isinstance(consolidato, EsitoRiferimento):
        return consolidato
    article = _con_allegato(norma.tipo_atto, norma.allegato, norma.numero_articolo)
    if letta and split_annex(article):
        return EsitoRiferimento(esito="non_supportata", errore=_ALLEGATO_A_UNA_DATA)
    if consolidato and (motivo := _non_nel_consolidato(article)):
        return EsitoRiferimento(esito="non_supportata", errore=motivo)
    info = {"tipo_atto": norma.tipo_atto, "data": norma.data, "numero_atto": norma.numero_atto}
    if parte := _parte(norma.tipo_atto, norma.allegato):
        info["allegato"] = parte
    info.update(letta)
    if consolidato:
        info["celex_consolidated"] = consolidato
    return info, article


def _non_nel_consolidato(article: str) -> "str | None":
    """Why *article* is not served from a consolidated EU version, or None.

    A consolidated text has no preamble: asked for a recital, the page's only «(N)»
    paragraphs are its footnotes («(2) GU L 204 del 21.7.1998…»), which a lookup would
    serve as the recital. Its annexes are not read yet.
    """
    if (article or "").startswith("rec_"):
        return ("i considerando non sono nel testo consolidato UE: chiederli senza celex_consolidated "
                "(versione della Gazzetta ufficiale)")
    if split_annex(article):
        return "gli allegati di una versione consolidata UE non sono ancora disponibili"
    return None


def _consolidato(tipo_atto: str, data: str, numero_atto: str, celex: str | None) -> "str | EsitoRiferimento":
    """The consolidated CELEX asked for ("" for the Official Journal text), or the refusal.

    VisuaLex checks the shape (sector 0, ``fullmatch`` with ASCII digits: a trailing newline
    or another script's digits never reach a URL) and that the act is an EU regulation or
    directive. This also checks it is the act's own: «02016R0679-…» under directive 2002/58
    would serve another act's text under this one's name.
    """
    from mcp_legal_it.lib.visualex.eurlex_text import _CONSOLIDATED_CELEX

    if not celex:
        return ""
    norm = normalize_act_type((tipo_atto or "").strip()).lower()
    if norm not in ("regolamento ue", "direttiva ue"):
        return EsitoRiferimento(esito="riferimento_non_valido",
                                errore="celex_consolidated vale solo per atti EUR-Lex (regolamento ue, direttiva ue)")
    if not isinstance(celex, str) or not _CONSOLIDATED_CELEX.fullmatch(celex):
        return EsitoRiferimento(esito="riferimento_non_valido",
                                errore=(f"celex_consolidated non valido: {celex!r} (atteso il CELEX di una "
                                        "versione consolidata, es. 02002L0058-20091219)"))
    anno = (data or "").split("-")[0]
    atteso = f"0{anno}{'L' if norm == 'direttiva ue' else 'R'}{(numero_atto or '').zfill(4)}"
    if celex[:10] != atteso:
        return EsitoRiferimento(esito="riferimento_non_valido",
                                errore=f"celex_consolidated {celex} non è una versione di questo atto (atteso {atteso}-AAAAMMGG)")
    return celex


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

    *canale* is required. ``"html"``: the article page read by VisuaLex's frozen
    extractor, byte for byte VisuaLex's ``article_text`` (the Akoma Ntoso export only
    when the page cannot be read, and ``fonte`` then says ``normattiva-akn``).
    ``"akn"``: the Akoma Ntoso export first, the page as fallback: accents
    transliterated, no «(( … ))» amendment markers, never VisuaLex's display text.

    Esiti: ``trovato``, ``riferimento_non_valido``, ``atto_non_riconosciuto``,
    ``articolo_non_trovato``, ``verifica_non_disponibile``, ``testo_assente``,
    ``errore_fonte``, ``non_supportata``.
    """
    if canale not in ("akn", "html"):
        raise ValueError(f"canale sconosciuto: {canale!r} (attesi 'akn' o 'html')")
    oggi = _clock.today().isoformat()
    if isinstance(riferimento, NormaDati):
        if (motivo := _allegato_non_valido(riferimento.tipo_atto, riferimento.allegato)) is not None:
            return TestoArticolo(esito="riferimento_non_valido", article_text="", norma_data=None, url="",
                                 canale=canale, data_consultazione=oggi, errore=motivo)
        letto = _act_info(riferimento)
        if isinstance(letto, EsitoRiferimento):
            return TestoArticolo(esito=letto.esito, article_text="", norma_data=None, url="",
                                 canale=canale, data_consultazione=oggi, errore=letto.errore)
        act_info, article = letto
    else:
        letto = _leggi(riferimento)
        if isinstance(letto, EsitoRiferimento):
            return TestoArticolo(esito=letto.esito, article_text="", norma_data=None, url="",
                                 canale=canale, data_consultazione=oggi, errore=letto.errore)
        act_info, article = letto
    with registra() as registro:
        base, esito = await norme.lookup_parametri(act_info, article, canale=canale)
        nd = _norma_dati(act_info, article, data_atto=base["atto"]["data"], url=base["url"], urn=base["urn"])
        validita, precisione, avvisi, successione, upcoming = _qualita(base, act_info, article)
        if validita is not None and validita.state == "not_yet":
            # «NON ANCORA ESISTENTE O VIGENTE»: the article did not exist on the day asked
            # for. Its page's notice is not the article's text.
            motivo = norme.non_ancora_vigente({"valid_to": validita.valid_to}, act_info.get("data_versione"))
            return TestoArticolo(
                esito="articolo_non_trovato", article_text="", norma_data=nd, url=base["url"],
                validity=validita, urn=nd.urn, fonte=base["fonte"], canale=canale,
                data_consultazione=base["data_consultazione"], errore=motivo, fonti=registro.fonti(),
            )
        return TestoArticolo(
            esito=_esito_lookup(base, esito),
            article_text=base["testo"],
            norma_data=nd,
            url=base["url"],
            validity=validita,
            urn=nd.urn,
            fonte=base["fonte"],
            canale=canale,
            data_consultazione=base["data_consultazione"],
            errore=base["errore"],
            fonti=registro.fonti(),
            precisione=precisione,
            avvisi=avvisi,
            successione=successione,
            upcoming=upcoming,
        )


def _qualita(base: dict, act_info: dict, article: str):
    """``(validity, precisione, avvisi, successione, upcoming)`` of a served text (``norme.qualita_testo``)."""
    q = norme.qualita_testo(base, act_info, article)
    validita = q["validita"]
    vigenza = Vigenza(**{k: validita[k] for k in ("state", "valid_from", "valid_to", "version_number",
                                                   "act_updated", "request_in_window")}) if validita else None
    return vigenza, q["precisione"], tuple(q["avvisi"]), q["successione"], q["upcoming"]


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
        letto = _act_info(atto)
        if isinstance(letto, EsitoRiferimento):
            return letto.esito, letto.errore
        info, _ = letto
        if info.get("versione"):
            # The whole act and its index are today's: never served under a date asked for.
            return "non_supportata", "l'atto intero e il suo indice a una data non sono ancora disponibili"
    else:
        _, act_name = norme._parse_reference(atto)
        if not act_name:
            return "riferimento_non_valido", f"impossibile interpretare il riferimento '{atto}'."
        info = norme._resolve_act(act_name)
        if not info:
            return "atto_non_riconosciuto", _senza_tool(norme._unresolved_act_error(act_name))
    return Norma(tipo_atto=info["tipo_atto"], data=info.get("data", ""), numero_atto=info.get("numero_atto", ""))


async def indice_atto(atto: str | NormaDati) -> IndiceAtto:
    """The article headings of an Italian act: VisuaLex's ``/fetch_rubriche``.

    From the act's Akoma Ntoso export: ``title`` (presentable), ``rubriche`` of the act's
    main text (``count`` is ``len(rubriche)``), ``abrogati``, and ``parts``, one dict per
    part (``name``, ``keys``, ``rubriche``, ``abrogati``, plus ``allegato``, its Normattiva
    number). The export is the act's own (two requests cold, none warm). When it cannot be
    read, Normattiva's ``vediRubriche`` answers: ``rubriche`` and ``voci`` (its lines),
    without abrogati or parts.
    Esiti: ``trovato``, ``riferimento_non_valido``, ``atto_non_riconosciuto``,
    ``non_supportata`` (EU acts), ``verifica_non_disponibile``, ``errore_fonte``, ``testo_assente``.
    """
    norma = _atto(atto)
    if isinstance(norma, tuple):
        return IndiceAtto(esito=norma[0], errore=norma[1])
    if norma._is_eurlex():
        return IndiceAtto(esito="non_supportata", errore="indice disponibile solo per gli atti su Normattiva")
    with registra() as registro:
        act = await _export_atto(norma)
        if act is not None:
            return _indice_da_export(act, norma, registro.fonti())
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


async def _export_atto(norma: Norma):
    """The act's parsed Akoma Ntoso export (with its real date when cited by year), or None."""
    from mcp_legal_it.lib.visualex import akn_fetch
    from mcp_legal_it.lib.visualex.scraper import _akn_disabled, with_full_date

    if _akn_disabled():
        return None
    try:
        return await akn_fetch.fetch_act_akn(await with_full_date(norma))
    except Exception:  # noqa: BLE001 - the export is one source: its failure is "no export"
        return None


def _indice_da_export(act, norma: Norma, fonti) -> IndiceAtto:
    from mcp_legal_it.lib.visualex import akn_fetch
    from mcp_legal_it.lib.visualex.akn_parser import presentable_title

    rubriche = act.rubriche()
    parts = tuple(
        {
            "name": name,
            "keys": list(part.order),
            "rubriche": act.rubriche(name),
            "abrogati": act.abrogati(name),
            "allegato": str(act.part_position(name)) if act.part_position(name) else None,
        }
        for name, part in act.parts.items()
    )
    codice, data_gu = akn_fetch._get_url_params(norma.url()) or ("", "")
    return IndiceAtto(
        esito="trovato" if act.article_count else "testo_assente",
        title=presentable_title(act.title),
        rubriche=rubriche,
        abrogati=tuple(act.abrogati()),
        parts=parts,
        count=len(rubriche),
        codice_redazionale=codice,
        data_gu=data_gu,
        url=norma.url(),
        errore=None if act.article_count else "export senza articoli",
        fonti=fonti,
    )


async def albero_atto(atto: str | NormaDati, *, link: bool = False, dettagli: bool = False) -> AlberoAtto:
    """Normattiva's article tree of an Italian act: VisuaLex's ``/fetch_tree``.

    Every article with the part it belongs to (``allegato``, Normattiva's number; ``None``
    for the act's own text), its URL when *link*, the section labels between them when
    *dettagli*, and ``metadata["annexes"]``. One request (the act's page), kept a day.
    Esiti: ``trovato``, ``riferimento_non_valido``, ``atto_non_riconosciuto``,
    ``non_supportata`` (EU acts), ``verifica_non_disponibile``, ``errore_fonte``.
    """
    norma = _atto(atto)
    if isinstance(norma, tuple):
        return AlberoAtto(esito=norma[0], errore=norma[1])
    if norma._is_eurlex():
        return AlberoAtto(esito="non_supportata", errore="albero disponibile solo per gli atti su Normattiva")
    with registra() as registro:
        try:
            result = await fetch_act_tree(norma, link=link, details=dettagli)
        except Exception as exc:  # noqa: BLE001 - errors are data
            esito = "verifica_non_disponibile" if fonte_giu(exc) else "errore_fonte"
            return AlberoAtto(esito=esito, url=norma.url(), errore=str(exc), fonti=registro.fonti())
        if result.get("error"):
            return AlberoAtto(esito="errore_fonte", url=result.get("url", ""), errore=result["error"],
                              fonti=registro.fonti())
        return AlberoAtto(esito="trovato", articles=tuple(result["articles"]), count=result["count"],
                          metadata=result["metadata"], url=result["url"], fonti=registro.fonti())


def articolo_nell_albero(albero: AlberoAtto, articolo: str, allegato: str | None = None) -> bool | None:
    """Whether *articolo* is in the act's tree, in part *allegato* when given ("" = the act's own text).

    ``None`` when the tree could not be read: an outage is never "the article does not exist".
    VisuaLex's existence check, before an article is fetched. No network.
    """
    if albero.esito != "trovato":
        return None
    return _albero.articolo_nell_albero(list(albero.articles), articolo, allegato)


def dove_altrove(albero: AlberoAtto, articolo: str, allegato: str | None) -> str:
    """Where else in the act *articolo* is, as a sentence for a refusal (``""`` if nowhere). No network."""
    if albero.esito != "trovato":
        return ""
    return _albero.dove_altrove(list(albero.articles), articolo, allegato)


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

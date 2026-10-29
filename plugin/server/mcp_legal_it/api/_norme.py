"""Norm functions of ``mcp_legal_it.api`` (see ``docs/api.md``)."""

from __future__ import annotations

import asyncio
import dataclasses
import re
from typing import Iterable

import httpx

from mcp_legal_it.api._comune import fonte_giu, registra
from mcp_legal_it.api.tipi import (
    AlberoAtto,
    AnnotazioniBrocardi,
    AttoRisolto,
    Canale,
    CatalogoAlias,
    ConsiderandiAtto,
    EsitoRiferimento,
    IndiceAtto,
    MassimaBrocardi,
    NormaDati,
    NotaAggiornamento,
    ParteArticolo,
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
    act_full_date,
    fetch_act_index,
    fetch_act_tree,
    fetch_normattiva_full_text,
    normattiva_serves_acts,
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

#: The act types whose date and number ``risolvi_atto`` reads from the Normattiva page's
#: title (``precisione="ESATTO"``), as ``normalize_act_type`` names them. Any other type
#: it accepts (DPCM, decreto ministeriale, d.lgs. luogotenenziale) is dated by the page's
#: ELI date, ``INDICATIVO``. ``tests/unit/test_api_risolvi_atto.py`` ties it to the titles' table.
TIPI_ATTO_VERIFICATI: tuple[str, ...] = (
    "legge",
    "decreto legislativo",
    "decreto legge",
    "decreto del presidente della repubblica",
    "regio decreto",
    "regio decreto legge",
    "legge costituzionale",
)

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


def _allegato_predefinito(tipo_atto: str) -> str | None:
    """The annex a code's URN points at ("2" for the c.c., "1" for c.p. and c.p.c.), else None.

    VisuaLex keys a saved norm on urn|allegato|article, so the annex is given even
    when the citation does not name it, as VisuaLex gives it: since 4aa59a9d also for the
    codes approved as a decree's annex (codice del turismo, norme di attuazione del c.p.p.,
    regolamento della navigazione marittima, codici penali militari).
    """
    norm = normalize_act_type(tipo_atto or "").lower()
    urn = codice_urn(norm)
    m = _ALLEGATO_URN.search(urn or "")
    return m.group(1) if m else None


def _allegato_dell_atto(info: dict) -> str | None:
    """The annex an act cited by its own number is keyed by when its articles are that annex's
    (``map.ARTICOLATO_IN_ALLEGATO``: c.p.p. minorile, TULPS, TU successioni), matched on type,
    year and number; else None. VisuaLex keys them so in its ``ANNEXED_ACTS`` (the TULPS at
    4aa59a9d; the other two are being added there, after its G-350)."""
    from mcp_legal_it.lib.visualex.map import articolato_in_allegato

    tipo = normalize_act_type(info.get("tipo_atto") or "").lower().replace(" ", ".")
    return articolato_in_allegato(tipo, info.get("data") or "", str(info.get("numero_atto") or ""))


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
        allegato = (info.get("allegato") or _allegato_predefinito(info.get("tipo_atto", ""))
                    or _allegato_dell_atto(info))
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
        # versione="futura" stays as asked, its data_versione the latest day it may start.
        versione="futura" if info.get("futura") else info.get("versione") or "vigente",
        data_versione=(info.get("futura_entro") if info.get("futura") else info.get("data_versione")) or None,
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
    if consolidato and letta:
        return EsitoRiferimento(esito="riferimento_non_valido", errore=_CONSOLIDATO_E_VERSIONE)
    article = _con_allegato(tipo_atto, allegato, numero_articolo)
    if letta and split_annex(article):
        return EsitoRiferimento(esito="non_supportata", errore=_allegato_non_servito(letta))
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


# A Normattiva answer without an act that says nothing about the act (scraper.normattiva_page_problem).
_PROBLEMI_TRANSITORI = {
    "sessione": "sessione scaduta",
    "manutenzione": "sito in manutenzione",
    "illeggibile": "risposta senza atto né pagina di errore",
}


def _atto_esito(esito: str, errore: str, tipo: str = "", numero: str = "", fonti=None) -> AttoRisolto:
    return AttoRisolto(esito=esito, tipo_atto=tipo, numero_atto=numero, errore=errore, fonti=fonti)


async def risolvi_atto(tipo_atto: str, numero_atto: str, anno_o_data: str) -> AttoRisolto:
    """The full date and NIR URN of an Italian act, from its Normattiva page.

    *anno_o_data* is the year ("1993") or the date ("1993-09-01", "1 settembre 1993"). The
    act's own page is read (the act, not its art. 1), with the library's limits and
    configuration; a date found from the page's title is kept on disk a year
    (``act_dates.json`` in the cache directory) and in memory for the process.

    Esiti: ``trovato``, ``atto_non_trovato``, ``ambiguo`` (a full date whose day is not the
    act's: ``data`` and ``urn`` are those of the act with that type, year and number),
    ``fonte_non_raggiungibile`` and ``errore_fonte`` (both transient, never kept),
    ``riferimento_non_valido``, ``atto_non_riconosciuto``, ``non_supportata`` (an EU act, a
    codice). Normattiva's error page is ``atto_non_trovato`` only when a known act reads
    right after it (``scraper.normattiva_serves_acts``): the same page answers a session or
    server problem.
    """
    from mcp_legal_it.lib.visualex.normattiva_validity import _iso_day

    for nome, valore in (("tipo_atto", tipo_atto), ("numero_atto", numero_atto), ("anno_o_data", anno_o_data)):
        if not isinstance(valore, str):
            raise TypeError(f"{nome} deve essere una stringa")
    if not tipo_atto.strip():
        return _atto_esito("riferimento_non_valido", "tipo_atto mancante")
    tipo = normalize_act_type(tipo_atto.strip()).lower()
    if tipo in EURLEX or tipo in ("regolamento ue", "direttiva ue"):
        return _atto_esito("non_supportata", "risolvi_atto serve gli atti italiani su Normattiva, non gli atti UE")
    if codice_urn(tipo) or tipo == "costituzione":
        return _atto_esito("non_supportata", f"'{tipo_atto}' ha già data e URN fissi: usa leggi_riferimento()")
    if tipo not in _TIPI_NOTI:
        return _atto_esito("atto_non_riconosciuto",
                           f"tipo d'atto '{tipo_atto}' non riconosciuto: usa il nome esteso ('decreto legislativo')")
    numero = numero_atto.strip()
    if not re.fullmatch(r"\d{1,6}", numero) or int(numero) == 0:
        return _atto_esito("riferimento_non_valido", f"numero_atto '{numero_atto}' non valido: atteso un numero",
                           tipo)
    numero = str(int(numero))
    # "1° settembre 1993", "1°settembre 1993": the long form's reader takes the day without
    # its ordinal sign, and a space before the month.
    testo = re.sub(r"(\d)\s*[°º]\s*", r"\1 ", anno_o_data.strip())
    citata = None
    if re.fullmatch(r"\d{4}", testo):
        anno = testo
    elif re.fullmatch(r"\d{4}-\d{2}-\d{2}|\d{1,2}\s+[^\W\d_]+\s+\d{4}", testo) and (citata := _iso_day(testo)):
        anno = citata[:4]
    else:
        return _atto_esito("riferimento_non_valido",
                           f"anno_o_data '{anno_o_data}' non valido: atteso AAAA o AAAA-MM-GG", tipo, numero)
    norma = Norma(tipo_atto=tipo, data=anno, numero_atto=numero)
    with registra() as registro:
        try:
            data, modo, pagina = await act_full_date(norma)
        except Exception as exc:  # noqa: BLE001 - every failure of the source is an outcome
            stato = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) and exc.response is not None \
                else None
            if fonte_giu(exc) or stato == 403:
                # A 403 is a WAF or rate block, not a fact about the act.
                motivo = f"HTTP {stato}" if stato else type(exc).__name__
                return _atto_esito("fonte_non_raggiungibile", f"Normattiva non raggiungibile ({motivo})",
                                   tipo, numero, registro.fonti())
            if stato == 404:
                return _atto_esito("atto_non_trovato", f"nessun atto «{tipo} n. {numero} del {anno}» su Normattiva",
                                   tipo, numero, registro.fonti())
            motivo = f"HTTP {stato}" if stato else type(exc).__name__
            return _atto_esito("errore_fonte", f"Normattiva ha risposto con un errore ({motivo})",
                               tipo, numero, registro.fonti())
        if not data:
            problema = pagina.get("problema")
            if problema in _PROBLEMI_TRANSITORI:
                return _atto_esito("fonte_non_raggiungibile",
                                   f"Normattiva non raggiungibile ({_PROBLEMI_TRANSITORI[problema]})",
                                   tipo, numero, registro.fonti())
            if problema == "errore" and not await normattiva_serves_acts():
                # The same error page answers a missing act and a session or server failure:
                # it is about the act only when Normattiva serves a known act right now.
                return _atto_esito("fonte_non_raggiungibile",
                                   "Normattiva non raggiungibile (pagina di errore, e l'atto di controllo non si legge)",
                                   tipo, numero, registro.fonti())
            intestazione = pagina.get("heading", "")
            altro = f": la pagina restituita è «{intestazione}»" if intestazione and not problema else ""
            return _atto_esito("atto_non_trovato", f"nessun atto «{tipo} n. {numero} del {anno}» su Normattiva{altro}",
                               tipo, numero, registro.fonti())
        url = dataclasses.replace(norma, data=data).url()
        esito, errore = "trovato", None
        if citata is not None and citata != data:
            esito = "ambiguo"
            errore = (f"«{tipo} n. {numero} del {anno}» su Normattiva è del {data}, non del {citata}: "
                      "sbagliato il giorno o il numero")
        return AttoRisolto(
            esito=esito, tipo_atto=tipo, numero_atto=numero, data=data, urn=norme._urn_from_url(url), url=url,
            precisione="ESATTO" if modo == "titolo" else "INDICATIVO", errore=errore, fonti=registro.fonti(),
        )


_ALLEGATO_A_UNA_DATA = "il testo di un allegato a una data non è ancora disponibile"


def _allegato_non_servito(letta: dict) -> str:
    """Why an annex is not served in the version *letta* asks for."""
    return ("la versione futura di un allegato non è ancora disponibile" if letta.get("futura")
            else _ALLEGATO_A_UNA_DATA)


def _versione(tipo_atto: str, versione: str | None, data_versione: str | None) -> dict | EsitoRiferimento:
    """``{"versione", "data_versione"}`` for a lookup ({} for today's text), or the refusal.

    A date always means "the text in force on that day" (``!vig=``), with or without
    ``versione="vigente"``. VisuaLex's ``generate_urn`` reads the date only together with
    "vigente", and a date sent without it gets today's text under the date asked for
    (art. 1284 c.c. "at 2010-01-01" came back with the 4th and 5th commi of 2014). Since
    4aa59a9d VisuaLex follows the same rule (its #276). ``versione="futura"`` is the text
    not in force yet (``_versione_futura``).
    """
    from mcp_legal_it.lib.visualex.normattiva_validity import _iso_day

    nome = (versione or "vigente").strip().lower()
    if nome not in ("vigente", "originale", "futura"):
        return EsitoRiferimento(esito="riferimento_non_valido",
                                errore=f"versione '{versione}' non valida: attese 'vigente', 'originale' o 'futura'")
    if nome == "futura":
        return _versione_futura(tipo_atto, data_versione)
    if not data_versione and nome == "vigente":
        return {}
    if not _normattiva(tipo_atto) and normalize_act_type((tipo_atto or "").strip()).lower() not in (
            "regolamento ue", "direttiva ue"):
        return EsitoRiferimento(esito="non_supportata",
                                errore="versioni a una data disponibili per gli atti su Normattiva e per "
                                       "regolamenti e direttive UE")
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


def _versione_futura(tipo_atto: str, data_versione: str | None) -> dict | EsitoRiferimento:
    """``versione="futura"``: the text Normattiva has published and not in force yet (VisuaLex's
    ``upcoming: true``). *data_versione*, optional, is the latest day it may come into force:
    after today, or the request is an ordinary dated one."""
    from mcp_legal_it.lib.visualex.normattiva_validity import _iso_day

    if not _normattiva(tipo_atto):
        return EsitoRiferimento(esito="non_supportata",
                                errore="versione 'futura' disponibile per gli atti su Normattiva")
    if not data_versione:
        return {"futura": True}
    giorno = _iso_day(data_versione)
    if giorno is None:
        return EsitoRiferimento(esito="riferimento_non_valido",
                                errore=f"data_versione '{data_versione}' non è una data (atteso AAAA-MM-GG)")
    if giorno <= _clock.today().isoformat():
        return EsitoRiferimento(esito="riferimento_non_valido",
                                errore=("con versione 'futura' data_versione dev'essere successiva a oggi, o "
                                        "assente: il testo in vigore fino a oggi è quello a una data"))
    return {"futura": True, "futura_entro": giorno}


def _act_info(norma: NormaDati) -> "tuple[dict, str] | EsitoRiferimento":
    """The lookup's act info and article for *norma*, or the refusal of its version."""
    letta = _versione(norma.tipo_atto, norma.versione, norma.data_versione)
    if isinstance(letta, EsitoRiferimento):
        return letta
    consolidato = _consolidato(norma.tipo_atto, norma.data, norma.numero_atto, norma.celex_consolidated)
    if isinstance(consolidato, EsitoRiferimento):
        return consolidato
    if consolidato and letta:
        return EsitoRiferimento(esito="riferimento_non_valido", errore=_CONSOLIDATO_E_VERSIONE)
    article = _con_allegato(norma.tipo_atto, norma.allegato, norma.numero_articolo)
    if letta and split_annex(article):
        return EsitoRiferimento(esito="non_supportata", errore=_allegato_non_servito(letta))
    if consolidato and (motivo := _non_nel_consolidato(article)):
        return EsitoRiferimento(esito="non_supportata", errore=motivo)
    info = {"tipo_atto": norma.tipo_atto, "data": norma.data, "numero_atto": norma.numero_atto}
    if parte := _parte(norma.tipo_atto, norma.allegato):
        info["allegato"] = parte
    info.update(letta)
    if consolidato:
        info["celex_consolidated"] = consolidato
    return info, article


_CONSOLIDATO_E_VERSIONE = ("celex_consolidated nomina già una versione: non va insieme a data_versione né a "
                           "versione 'originale'")


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
    if esito == "riferimento_non_valido":  # an EU act asked at a day before its own date
        return "riferimento_non_valido"
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
    return await _testo_articolo(riferimento, canale=canale)


async def parte_articolo(riferimento: str | NormaDati, progressivo: int, *, canale: Canale) -> TestoArticolo:
    """One part of an article Normattiva splits into parts («1 (commi 701-800)»).

    *progressivo* is a ``ParteArticolo.progressivo`` from ``testo_articolo(...).parti``:
    Normattiva's index in the act's tree as it is today (an amendment can split the article
    again: read the parts again rather than keep the index). ``article_text`` is that part's
    page, read by VisuaLex's extractor, with the part's own notes; ``parti`` is the whole
    list, ``testo_parziale`` is True. Two requests (the article's page, then the part's),
    one when the part is the page's own; a part read is kept a day under its commi.

    Esiti: those of ``testo_articolo``; ``riferimento_non_valido`` also for an article not
    split or a progressivo it does not have; ``verifica_non_disponibile`` for a part that
    could not be read.
    """
    if not isinstance(progressivo, int) or isinstance(progressivo, bool):
        raise TypeError("progressivo deve essere un intero")
    return await _testo_articolo(riferimento, canale=canale, progressivo=progressivo)


def parte_del_comma(parti: Iterable[ParteArticolo], comma: str) -> ParteArticolo | None:
    """The part whose commi hold *comma* («773», «773-bis»), or None. No network.

    A comma with a suffix sits after its number («100-bis» in the part ending at «100»).
    """
    from mcp_legal_it.lib.visualex.parti_normattiva import _canonico, parte_del_comma as _del_comma

    elenco = list(parti or ())
    trovata = _del_comma([{"commi_dal": p.commi_dal, "commi_al": p.commi_al, "i": i} for i, p in enumerate(elenco)],
                         _canonico(str(comma)))
    return elenco[trovata["i"]] if trovata else None


async def _testo_articolo(riferimento: str | NormaDati, *, canale: Canale,
                          progressivo: int | None = None) -> TestoArticolo:
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
        base, esito = await norme.lookup_parametri(act_info, article, canale=canale, progressivo=progressivo)
        parti = (tuple(ParteArticolo(**p) for p in base["parti"]) if base.get("parti") is not None else None)
        if base.get("esito_parte"):
            nd = _norma_dati(act_info, article, data_atto=base["atto"]["data"], url=base["url"], urn=base["urn"])
            return TestoArticolo(esito=base["esito_parte"], article_text="", norma_data=nd, url=base["url"],
                                 urn=nd.urn, canale=canale, data_consultazione=oggi, errore=base["errore"],
                                 fonti=registro.fonti(), parti=parti)
        if base.get("not_in_force") and act_info.get("futura"):
            # The later text asked for: dated to the day it comes into force, as VisuaLex's
            # norma_data. An inserted article asked without a date keeps the request's key.
            act_info = norme.futura_datata(act_info, base["upcoming"])
        nd = _norma_dati(act_info, article, data_atto=base["atto"]["data"], url=base["url"], urn=base["urn"])
        validita, precisione, avvisi, successione, upcoming = _qualita(base, act_info, article)
        # The lookup already joined the source's own notices (an EU consolidation to come).
        avvisi, upcoming = tuple(base.get("avvisi") or avvisi), base.get("upcoming") or upcoming
        if base.get("not_in_force"):
            precisione = "INDICATIVO"
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
            not_in_force=bool(base.get("not_in_force")),
            consolidato=base.get("consolidato"),
            consolidato_verificato=base.get("consolidato_verificato"),
            note_aggiornamento=(tuple(NotaAggiornamento(**n) for n in base["note_aggiornamento"])
                                if base.get("note_aggiornamento") is not None else None),
            note_non_lette=bool(base.get("note_non_lette")),
            parti=parti,
            testo_parziale=bool(base.get("testo_parziale")),
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
        if info.get("versione") or info.get("futura"):
            # The whole act and its index are today's: never served under a date asked for,
            # nor as the text not in force yet (versione="futura").
            return "non_supportata", "l'atto intero e il suo indice a una data non sono ancora disponibili"
    else:
        _, act_name = norme._parse_reference(atto)
        if not act_name:
            return "riferimento_non_valido", f"impossibile interpretare il riferimento '{atto}'."
        info = norme._resolve_act(act_name)
        if not info:
            return "atto_non_riconosciuto", _senza_tool(norme._unresolved_act_error(act_name))
    return Norma(tipo_atto=info["tipo_atto"], data=info.get("data", ""), numero_atto=info.get("numero_atto", ""),
                 celex_consolidated=info.get("celex_consolidated", ""))


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
        return await _indice_ue(norma)
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
        return await _albero_ue(norma, link=link, dettagli=dettagli)
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


async def _albero_eurlex(norma: Norma, *, link: bool, dettagli: bool):
    from mcp_legal_it.lib.visualex.scraper import fetch_eurlex_tree

    with registra() as registro:
        try:
            result = await fetch_eurlex_tree(norma, link=link, details=dettagli)
        except Exception as exc:  # noqa: BLE001 - errors are data
            return {"error": str(exc), "url": norma.url(), "giu": fonte_giu(exc)}, registro.fonti()
        return result, registro.fonti()


def _esito_ue(result: dict) -> str:
    if result.get("esito") == "riferimento_non_valido":
        return "riferimento_non_valido"
    return "verifica_non_disponibile" if result.get("giu") else "errore_fonte"


async def _indice_ue(norma: Norma) -> IndiceAtto:
    """An EU act's rubriche and title, from the page of its text in force (VisuaLex's EU tree)."""
    result, fonti = await _albero_eurlex(norma, link=False, dettagli=False)
    if result.get("error"):
        return IndiceAtto(esito=_esito_ue(result), url=result.get("url", ""), errore=result["error"], fonti=fonti,
                          consolidato=result.get("consolidato"),
                          consolidato_verificato=result.get("consolidato_verificato"))
    rubriche = dict(result["metadata"].get("rubriche") or {})
    if result["count"] and not rubriche:
        # The legacy class-less OJ page (dir. 2002/58) has its articles but prints no rubriche:
        # never an empty «trovato», which would read as an act without articles.
        errore = (f"la pagina dell'atto non riporta le rubriche dei suoi {result['count']} articoli "
                  "(l'elenco degli articoli è in albero_atto)")
    else:
        errore = None if result["count"] else "pagina senza articoli"
    return IndiceAtto(
        esito="trovato" if rubriche else "testo_assente",
        title=result["metadata"].get("title") or "",
        rubriche=rubriche,
        count=len(rubriche),
        url=result["url"],
        errore=errore,
        fonti=fonti,
        consolidato=result.get("consolidato"),
        consolidato_verificato=result.get("consolidato_verificato"),
    )


async def _albero_ue(norma: Norma, *, link: bool, dettagli: bool) -> AlberoAtto:
    """An EU act's article tree, from the page of its text in force (VisuaLex's EU tree)."""
    result, fonti = await _albero_eurlex(norma, link=link, dettagli=dettagli)
    if result.get("error"):
        return AlberoAtto(esito=_esito_ue(result), url=result.get("url", ""), errore=result["error"], fonti=fonti,
                          consolidato=result.get("consolidato"),
                          consolidato_verificato=result.get("consolidato_verificato"))
    return AlberoAtto(esito="trovato" if result["count"] else "testo_assente", articles=tuple(result["articles"]),
                      count=result["count"], metadata=result["metadata"], url=result["url"], fonti=fonti,
                      consolidato=result.get("consolidato"),
                      consolidato_verificato=result.get("consolidato_verificato"))


async def considerando(atto: str | NormaDati) -> ConsiderandiAtto:
    """Every recital of an EU regulation or directive: VisuaLex's ``/fetch_recitals``.

    ``considerando`` is ``({"number": "1", "text": "…"}, …)``, VisuaLex's reader on the Official
    Journal page (a consolidated text has no preamble): the text without its «(N)» (a
    legacy page keeps its footnote calls). One request, kept a day with the act's page.
    A ``NormaDati`` with ``celex_consolidated`` is ``non_supportata``, before any request.
    Esiti: ``trovato``, ``testo_assente`` (no recital on the page), ``riferimento_non_valido``,
    ``atto_non_riconosciuto``, ``non_supportata`` (an Italian act, a treaty),
    ``verifica_non_disponibile``, ``errore_fonte``.
    """
    from mcp_legal_it.lib.visualex.map import EURLEX_TREATY_CELEX
    from mcp_legal_it.lib.visualex.scraper import fetch_eurlex_recitals

    norma = _atto(atto)
    if isinstance(norma, tuple):
        return ConsiderandiAtto(esito=norma[0], errore=norma[1])
    if not norma._is_eurlex() or norma.tipo_atto_normalized.lower() in EURLEX_TREATY_CELEX:
        return ConsiderandiAtto(esito="non_supportata",
                                errore="considerando disponibili per regolamenti e direttive UE")
    if norma.celex_consolidated:
        # A consolidation has no preamble: its «(N)» are footnotes (testo_articolo refuses it alike).
        return ConsiderandiAtto(esito="non_supportata", errore=_non_nel_consolidato("rec_1"))
    with registra() as registro:
        try:
            result = await fetch_eurlex_recitals(norma)
        except Exception as exc:  # noqa: BLE001 - errors are data
            esito = "verifica_non_disponibile" if fonte_giu(exc) else "errore_fonte"
            return ConsiderandiAtto(esito=esito, url=norma.url(), errore=str(exc), fonti=registro.fonti())
        if result.get("error"):
            return ConsiderandiAtto(esito="errore_fonte", url=result.get("url", ""), errore=result["error"],
                                    fonti=registro.fonti())
        recitals = tuple(result["recitals"])
        return ConsiderandiAtto(esito="trovato" if recitals else "testo_assente", considerando=recitals,
                                url=result["url"], errore=None if recitals else "nessun considerando nella pagina",
                                fonti=registro.fonti())


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

"""The amendments of an Italian article: ``modifiche_articolo`` (see ``docs/api.md``)."""

from __future__ import annotations

import dataclasses
import re

from mcp_legal_it.api._comune import registra
from mcp_legal_it.api._norme import _act_info, _leggi, _norma_dati
from mcp_legal_it.api.tipi import (
    AttoModificante,
    EsitoRiferimento,
    Modifica,
    ModificheArticolo,
    NormaDati,
    VersioneArticolo,
)
from mcp_legal_it.core import norme
from mcp_legal_it.lib import _clock
from mcp_legal_it.lib.visualex import aggiornamenti, scraper
from mcp_legal_it.lib.visualex.models import Norma, split_annex

_AVVISO_VERSIONE_1 = ("la versione 1 è il testo con cui l'articolo è entrato nell'atto: l'atto che lo ha "
                      "introdotto non compare nella tabella degli aggiornamenti")


def _atto(dati: dict) -> AttoModificante:
    urn = None
    if dati["tipo_atto"] and dati["data"] and dati["numero_atto"]:
        url = Norma(tipo_atto=dati["tipo_atto"], data=dati["data"], numero_atto=dati["numero_atto"]).url()
        urn = norme._urn_from_url(url)
    return AttoModificante(tipo_atto=dati["tipo_atto"], data=dati["data"], numero_atto=dati["numero_atto"],
                           urn=urn, gazzetta=dati["gazzetta"], descrizione=dati["descrizione"])


def _modifiche(versioni: dict, righe: dict) -> list[Modifica]:
    """Every amendment of the tables read, oldest version first; identical rows once."""
    out, viste = [], set()
    for k in sorted(righe):
        finestra = versioni.get(k)
        inizio = finestra[0] if finestra else None
        for riga in righe[k]:
            for voce in riga["atti"]:
                atto = _atto(voce["atto"])
                letto = bool(atto.tipo_atto and atto.data and atto.numero_atto)
                for d in voce["disposizioni"]:
                    # Only an identical row is the same amendment: a decree-law and its
                    # conversion law «con modificazioni» are two (the law may change the text).
                    chiave = (atto.descrizione, d["disposizione"], d["testo"], d["tipo"], d["parti"])
                    if chiave in viste:
                        continue
                    viste.add(chiave)
                    out.append(Modifica(
                        atto=atto, tipo=d["tipo"], disposizione=d["disposizione"], parti=d["parti"],
                        in_vigore_dal=inizio, versione=k, data_gu=riga["data_gu"],
                        precisione="ESATTO" if letto and inizio else "INDICATIVO", testo=d["testo"],
                    ))
    return out


def _nel_periodo(m: Modifica, dal: str | None, al: str | None) -> bool:
    giorno = m.in_vigore_dal or m.data_gu
    if giorno is None:
        return True  # undated: never dropped on a guess
    return (dal is None or giorno >= dal) and (al is None or giorno <= al)


def _giorno(valore: str | None, nome: str) -> "str | EsitoRiferimento | None":
    if valore is None:
        return None
    if not isinstance(valore, str):
        raise TypeError(f"{nome} deve essere una stringa o None")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", valore.strip()):
        return EsitoRiferimento(esito="riferimento_non_valido", errore=f"{nome} '{valore}' non valido: atteso AAAA-MM-GG")
    from mcp_legal_it.lib.visualex.normattiva_validity import _iso_day

    giorno = _iso_day(valore.strip())
    if giorno is None:
        return EsitoRiferimento(esito="riferimento_non_valido", errore=f"{nome} '{valore}' non è un giorno")
    return giorno


async def modifiche_articolo(
    riferimento: str | NormaDati, *, dal: str | None = None, al: str | None = None, max_versioni: int = 20,
) -> ModificheArticolo:
    """The versions of an Italian article and the amendments that produced them, from Normattiva.

    Each version's page states its window, and each version's update table lists the
    amendments that produced it: an amendment's ``in_vigore_dal`` is the start of the
    version it produced, read, not deduced. *dal* and *al* ("YYYY-MM-DD", both inclusive)
    filter on ``in_vigore_dal``, never on the Gazzetta date (they differ by days and would
    flip results); an amendment without it is filtered on ``data_gu`` and is INDICATIVO.
    The newest *max_versioni* versions are read at most: past the ceiling, and when a
    version cannot be read, ``completa`` is False and ``avvisi`` says which (a failure is
    transient: ask again). ``Modifica.testo`` is Normattiva's wording only.

    Esiti: ``trovato``, ``riferimento_non_valido``, ``atto_non_riconosciuto``,
    ``articolo_non_trovato``, ``verifica_non_disponibile`` (transient), ``errore_fonte``,
    ``non_supportata`` (an EU act, the whole act without an article, an annex named by the act).
    """
    if not isinstance(max_versioni, int) or isinstance(max_versioni, bool) or max_versioni < 1:
        raise ValueError("max_versioni deve essere un intero almeno 1")
    giorni = {}
    for nome, valore in (("dal", dal), ("al", al)):
        letto = _giorno(valore, nome)
        if isinstance(letto, EsitoRiferimento):
            return ModificheArticolo(esito=letto.esito, errore=letto.errore)
        giorni[nome] = letto
    dal, al = giorni["dal"], giorni["al"]
    if dal and al and dal > al:
        return ModificheArticolo(esito="riferimento_non_valido", errore=f"dal ({dal}) è dopo al ({al})")
    letto = _act_info(riferimento) if isinstance(riferimento, NormaDati) else _leggi(riferimento)
    if isinstance(letto, EsitoRiferimento):
        return ModificheArticolo(esito=letto.esito, errore=letto.errore)
    act_info, article = letto
    info = {k: act_info[k] for k in ("tipo_atto", "data", "numero_atto", "allegato") if act_info.get(k)}
    nv = norme._build_nv(info, article)
    if nv.norma._is_eurlex():
        return ModificheArticolo(esito="non_supportata",
                                 errore="modifiche_articolo legge le tabelle degli aggiornamenti di Normattiva: "
                                        "non serve gli atti UE")
    if not article:
        return ModificheArticolo(esito="non_supportata",
                                 errore="serve un articolo: le modifiche si leggono per articolo, mai per l'atto "
                                        "intero (e mai dall'art. 1 al suo posto)")
    if split_annex(article):
        return ModificheArticolo(esito="non_supportata",
                                 errore="le modifiche di un articolo di un allegato non sono ancora disponibili")
    oggi = _clock.today().isoformat()
    with registra() as registro:
        # A year-only act gets its date (one request, cached), so the URN and the cache key are the act's.
        nv = dataclasses.replace(nv, norma=await scraper.with_full_date(nv.norma))
        url = nv.url()
        letta = await aggiornamenti.leggi_aggiornamenti(url, article, dal=dal, al=al, max_versioni=max_versioni,
                                                        oggi=oggi)
        nd = _norma_dati(info | {"data": nv.norma.data}, article, url=url, urn=norme._urn_from_url(url))
        if letta["esito"] != "trovato":
            return ModificheArticolo(esito=letta["esito"], norma_data=nd, url=url, errore=letta["errore"],
                                     fonti=registro.fonti())
        versioni = letta["versioni"]
        tutte = [VersioneArticolo(k, *(versioni[k] or (None, None))) for k in sorted(versioni)]
        modifiche = _modifiche(versioni, letta["righe"])
        avvisi = []
        if len(tutte) > 1:
            avvisi.append(_AVVISO_VERSIONE_1)
        for v in tutte:
            if v.valid_from and v.valid_from > oggi:
                avvisi.append(f"la versione {v.version_number} entra in vigore il {v.valid_from}: non è ancora in "
                              "vigore (Normattiva la mostra già come testo dell'articolo)")
        scelte = [m for m in modifiche if _nel_periodo(m, dal, al)]
        if (dal or al) and any(m.in_vigore_dal is None for m in scelte):
            scelte = [dataclasses.replace(m, precisione="INDICATIVO") if m.in_vigore_dal is None else m
                      for m in scelte]
            avvisi.append("per alcune modifiche la data di entrata in vigore non si legge: il periodo dal/al è "
                          "stato applicato alla data di pubblicazione in Gazzetta (data_gu), che può precederla")
        mancanti, oltre = letta["mancanti"], letta["oltre_tetto"]
        if oltre:
            avvisi.append(f"lette le ultime {max_versioni} versioni su {len(tutte)}: per le precedenti "
                          f"({', '.join(map(str, sorted(oltre)))}) restringere dal/al o alzare max_versioni")
        if mancanti:
            avvisi.append(f"versioni non lette per un errore della fonte: {', '.join(map(str, sorted(mancanti)))} "
                          f"({letta['errore']}); è un problema transitorio: riprovare")
        completa = not mancanti and not oltre
        # A Modifica is ESATTO only with its version's window read: an unread window shows there.
        precisione = "ESATTO" if completa and all(m.precisione == "ESATTO" for m in scelte) else "INDICATIVO"
        return ModificheArticolo(
            esito="trovato", norma_data=nd, versioni=tuple(tutte), modifiche=tuple(scelte), url=url,
            completa=completa, precisione=precisione, avvisi=tuple(avvisi),
            versioni_non_lette=len(set(mancanti) | set(oltre)), errore=None, fonti=registro.fonti(),
        )

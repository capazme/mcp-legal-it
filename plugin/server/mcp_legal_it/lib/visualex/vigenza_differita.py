"""Amendments Normattiva serves as in force whose entry into force a later act deferred (#172).

Art. 27 of d.lgs. 13 luglio 2017, n. 116 rewrites art. 7 c.p.c. (and some twenty articles of
the c.p.c. and the c.c.). Its art. 32, comma 3 deferred that article's entry into force again
and again (31/10/2021, 2025, 2026, 2027). Normattiva dated the version carrying the amendments
by a date of that chain, now superseded, and serves it as the text in force; only the
article's update notes, «AGGIORNAMENTO (183)», say «Le disposizioni dell'articolo 27 entrano
in vigore il 31 ottobre 2027».

This module reads those notes (no request): :func:`rinvio` finds a dated entry-into-force
clause, the latest one of each provision, that falls after today. :func:`caso` then reads,
from the article's table of updates, whether the deferred amendments are already in the text
and which version is in force:

- ``"A"``: the latest version carries only the deferred act and the acts that deferred it
  (all named by the notes), so the previous version is the text in force;
- ``"non_in_vigore"``: the article itself was inserted by the deferred act, so nothing of it
  is in force yet;
- ``"B"``: other amendments were laid on top of the deferred ones, so no version Normattiva
  shows is the text in force (art. 543 c.p.c.).

Only clauses with an explicit date are read; nothing is inferred from the notes' prose.
"""

from __future__ import annotations

import re

_MESI = {"gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4, "maggio": 5, "giugno": 6, "luglio": 7,
         "agosto": 8, "settembre": 9, "ottobre": 10, "novembre": 11, "dicembre": 12}
_MESE = "|".join(_MESI)

#: An act as the notes write it: «D.Lgs. 13 luglio 2017, n. 116», «D.L. 8 agosto 2025, n. 117».
_ATTO = re.compile(
    rf"\b(?P<tipo>D\.Lgs\.|D\.L\.|D\.P\.R\.|L\.)\s*(?P<g>\d{{1,2}})[°º]?\s+(?P<m>{_MESE})\s+(?P<a>\d{{4}}),\s*n\.\s*(?P<n>\d+)",
    re.IGNORECASE)
_TIPI = {"d.lgs.": "decreto legislativo", "d.l.": "decreto legge", "d.p.r.": "decreto del presidente della repubblica",
         "l.": "legge"}
#: «ha disposto (con l'art. 32, comma 3) che»: the provision that sets the date.
_DISPOSIZIONE = re.compile(r"ha disposto\s*\(con l['’]art\.\s*([^)]+?)\)\s*che", re.IGNORECASE)
#: The dated entry into force, after «ha disposto».
_ENTRATA = re.compile(
    rf"(?:entra(?:no)?\s+in\s+vigore\s+(?:il|dal)|hanno\s+effetto\s+a\s+decorrere\s+dal)\s+"
    rf"(?P<g>\d{{1,2}})[°º]?\s+(?P<m>{_MESE})\s+(?P<a>\d{{4}})", re.IGNORECASE)
#: «Le disposizioni dell'articolo 27 entrano in vigore»: the article of the act deferred.
_ARTICOLO_RINVIATO = re.compile(r"disposizioni\s+dell['’]articolo\s+(\d+(?:-[a-z]+)?)", re.IGNORECASE)


def _iso(g: str, m: str, a: str) -> str:
    return f"{a}-{_MESI[m.lower()]:02d}-{int(g):02d}"


def _atto(m: "re.Match") -> tuple[str, str, str]:
    return _TIPI[m["tipo"].lower()], _iso(m["g"], m["m"], m["a"]), m["n"]


def clausola(nota: dict) -> "dict | None":
    """The dated entry-into-force clause of one update note, else None.

    ``{numero, atto, atto_testo, rinviano, disposizione, data, articolo}``: *atto* the act
    whose provision sets the date, as ``(tipo, data, numero)``; *rinviano* the acts that
    amended that provision («come modificato dal …»); *data* ISO; *articolo* the article of
    *atto* the clause names («Le disposizioni dell'articolo 27»), None when it names none.
    """
    testo = " ".join((nota.get("testo") or "").split())
    disp = _DISPOSIZIONE.search(testo)
    if disp is None:
        return None
    entrata = _ENTRATA.search(testo, disp.end())
    atti = list(_ATTO.finditer(testo, 0, disp.start()))
    if entrata is None or not atti:
        return None
    articolo = _ARTICOLO_RINVIATO.search(testo, disp.end())
    return {"numero": str(nota.get("numero") or ""), "atto": _atto(atti[0]), "atto_testo": atti[0].group(0),
            "rinviano": [_atto(m) for m in atti[1:]], "disposizione": " ".join(disp.group(1).split()),
            "data": _iso(entrata["g"], entrata["m"], entrata["a"]),
            "articolo": articolo.group(1) if articolo else None}


def _ordine(c: dict) -> int:
    return int(c["numero"]) if c["numero"].isdigit() else -1


def rinvio(note: "list[dict] | None", oggi: str) -> "dict | None":
    """The deferred entry into force the article's notes state, when it falls after *oggi*.

    The notes of each provision (same act, same «con l'art. …») form a chain: the latest
    note (the highest number) gives the date in force. Of the chains whose date is after
    *oggi*, the latest date. ``{data, nota, atto, atto_testo, articolo, catena, superate}``:
    *catena* every act of the chain (the deferred act and those that deferred it), *superate*
    the earlier dates of the chain. None without such a clause.
    """
    catene: dict[tuple, list[dict]] = {}
    for nota in note or []:
        c = clausola(nota)
        if c is not None:
            catene.setdefault((c["atto"], c["disposizione"]), []).append(c)
    trovati = []
    for clausole in catene.values():
        ultima = max(clausole, key=_ordine)
        if ultima["data"] > oggi:
            atti = {ultima["atto"]} | {a for c in clausole for a in c["rinviano"]}
            superate = sorted({c["data"] for c in clausole} - {ultima["data"]})
            articolo = next((c["articolo"] for c in sorted(clausole, key=_ordine, reverse=True) if c["articolo"]), None)
            trovati.append({"data": ultima["data"], "nota": ultima["numero"], "atto": ultima["atto"],
                            "atto_testo": ultima["atto_testo"], "articolo": articolo, "catena": atti,
                            "superate": superate})
    return max(trovati, key=lambda r: r["data"]) if trovati else None


def _atti_della_versione(righe: "list[dict] | None") -> set[tuple[str, str, str]]:
    """The acts of one version's table of updates (``aggiornamenti.leggi_aggiornamenti``)."""
    atti = set()
    for riga in righe or []:
        for voce in riga.get("atti") or []:
            a = voce.get("atto") or {}
            if a.get("tipo_atto") and a.get("data") and a.get("numero_atto"):
                atti.add((a["tipo_atto"], a["data"], str(a["numero_atto"])))
    return atti


def caso(r: dict, versioni: dict, righe: dict) -> "tuple[str | None, dict]":
    """Which case the article is, from its versions and their tables of updates.

    *versioni* ``{k: (valid_from, valid_to) | None}`` and *righe* ``{k: [rows]}`` as
    ``aggiornamenti.leggi_aggiornamenti`` gives them. ``(None, {})`` when no version in force
    before ``r["data"]`` carries the deferred act: the text does not contain the deferred
    amendments, and nothing is said. Otherwise ``("A", {"precedente": (k, from, to),
    "servita": (k, from)})``, ``("non_in_vigore", {"servita": (k, from)})`` or ``("B", {...})``.
    A case A is never assumed: the latest version must carry the deferred act and only acts
    of the chain, and the previous version's window must be known.
    """
    finestre = {k: v for k, v in versioni.items() if v}
    con_atto = [k for k, rr in righe.items()
                if r["atto"] in _atti_della_versione(rr) and finestre.get(k) and finestre[k][0] < r["data"]]
    if not con_atto:
        return None, {}
    ultima = max(versioni)
    servita = (ultima, finestre[ultima][0]) if finestre.get(ultima) else (ultima, None)
    prima = min(con_atto)  # the version Normattiva gave the deferred amendments to first
    rinviate_dal = finestre[prima][0]
    atti_ultima = _atti_della_versione(righe.get(ultima))
    solo_catena = bool(atti_ultima) and r["atto"] in atti_ultima and atti_ultima <= r["catena"]
    if solo_catena and ultima == 1:
        return "non_in_vigore", {"servita": servita, "rinviate_dal": rinviate_dal}
    precedente = finestre.get(ultima - 1)
    if solo_catena and prima == ultima and precedente and precedente[1]:
        return "A", {"precedente": (ultima - 1, precedente[0], precedente[1]), "servita": servita,
                     "rinviate_dal": rinviate_dal}
    return "B", {"servita": servita, "rinviate_dal": rinviate_dal}


def avviso(r: dict) -> str:
    """The notice of a deferred entry into force, by case (``r["caso"]``)."""
    atto = r["atto_testo"] + (f", art. {r['articolo']}" if r.get("articolo") else "")
    nota = f"la nota ({r['nota']}) di Normattiva rinvia al {r['data']} l'entrata in vigore delle modifiche del {atto}"
    servita = (r.get("servita") or (None, None))[1]
    if r.get("caso") == "A":
        k, dal, al = r["precedente"]
        return (f"{nota}, ma Normattiva dà come vigente dal {servita} la versione che le contiene: il testo "
                f"riportato è la versione precedente, in vigore dal {dal} (Normattiva la chiude il {al})")
    if r.get("caso") == "non_in_vigore":
        return f"{nota}, che hanno inserito l'articolo: Normattiva lo dà come vigente dal {servita}"
    if r.get("caso") == "B":
        return (f"{nota}, ma il testo riportato le contiene già (Normattiva le dà come vigenti dal "
                f"{r.get('rinviate_dal') or servita}) e nessuna versione di Normattiva corrisponde al testo in vigore "
                "oggi: verificarlo prima di citarlo")
    return (f"{nota}: non è stato possibile verificare se il testo riportato le contiene già; "
            "verificarlo prima di citarlo")


def sintesi(r: dict) -> dict:
    """What an answer carries of *r*, JSON-ready: ``{data, nota, atto, articolo, caso}``."""
    return {"data": r["data"], "nota": r["nota"], "atto": r["atto_testo"], "articolo": r.get("articolo"),
            "caso": r.get("caso")}

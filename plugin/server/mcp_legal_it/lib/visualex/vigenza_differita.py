"""Amendments Normattiva serves as in force whose entry into force a later act deferred (#172).

Art. 27 of d.lgs. 13 luglio 2017, n. 116 rewrites art. 7 c.p.c. (and some twenty articles of
the c.p.c. and the c.c.). Its art. 32, comma 3 deferred that article's entry into force again
and again (31/10/2021, 2025, 2026, 2027). Normattiva dated the version carrying the amendments
by a date of that chain, now superseded, and serves it as the text in force; only the
article's update notes, «AGGIORNAMENTO (183)», say «Le disposizioni dell'articolo 27 entrano
in vigore il 31 ottobre 2027».

This module reads those notes (no request): :func:`rinvio` finds a dated entry-into-force
clause, the latest one of each provision, that falls after today. A deferred repeal is read
too: «la proroga al 31 ottobre 2027 dell'entrata in vigore della presente abrogazione» (art.
73-bis disp. att. c.c.). The notes can stop behind the provision: art. 765 c.p.c.'s last note
gives 31/10/2026, never updated to 2027. :func:`rinvio_scaduto` finds such a chain (a date
moved later, now past), and the caller reads the provision itself (:func:`stato_disposizione` on
the page of art. 32 d.lgs. 116/2017, ``scraper.rinvio_dalla_disposizione``). :func:`caso`
then reads, from the article's table of updates, whether the deferred amendments are already
in the text and which version is in force:

- ``"A"``: every version from the first carrying the deferred act to the latest carries only
  the deferred act and the acts that deferred it, so the version before them is the text in
  force (art. 7 c.p.c.: version 9; art. 765 c.p.c.: version 3, before versions 4 and 5);
- ``"non_in_vigore"``: the article itself was inserted by the deferred act, so nothing of it
  is in force yet;
- ``"B"``: other amendments were laid on top of the deferred ones (art. 543 c.p.c.), or
  rewrote them (art. 518 c.p.c., d.lgs. 164/2024): what the text holds of them is not known,
  and no version is said to be the text in force.

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
#: A deferred repeal: «ha disposto (con l'art. 32, comma 3) [che] la proroga al 31 ottobre 2027
#: dell'entrata in vigore della presente abrogazione» (art. 73-bis disp. att. c.c.).
_PROROGA = re.compile(
    rf"ha disposto\s*\(con l['’]art\.\s*(?P<disp>[^)]+?)\)\s*(?:che\s+)?la\s+proroga\s+al\s+"
    rf"(?P<g>\d{{1,2}})[°º]?\s+(?P<m>{_MESE})\s+(?P<a>\d{{4}})\s+dell['’]entrata\s+in\s+vigore\s+della\s+"
    rf"presente\s+abrogazione", re.IGNORECASE)
#: «32, comma 3»: the article and comma of the provision that sets the date.
_ARTICOLO_COMMA = re.compile(r"^\s*(?P<art>\d+(?:-[a-z]+)?)\b(?:\s*,\s*comma\s+(?P<comma>\d+(?:-[a-z]+)?))?",
                             re.IGNORECASE)
#: A line opening a comma: «3. », «3-bis. », or «3.» alone on its line.
_INIZIO_COMMA = re.compile(r"^\s*\d+(?:-[a-z]+)?\s*\.(?:\s|$)")
#: A comma (or article) Normattiva gives as repealed: «3. COMMA ABROGATO DAL …».
_ABROGATO = re.compile(r"^(?:\d+(?:-[a-z]+)?\s*\.\s*)?(?:COMMA|ARTICOLO)\s+(?:ABROGAT|SOPPRESS)[OA]\b")
#: A comma whose date may not be the whole provision's: an exception or a derogation.
_ECCEZIONE = re.compile(r"\b(?:salvo|ad\s+eccezione|eccetto|limitatamente|tranne|in\s+deroga)\b", re.IGNORECASE)
#: A comma that defers only part of an article: «articolo 27, comma 1», «dei commi 1 e 2».
_PARTE_DI_ARTICOLO = re.compile(
    r"\barticol[oi]\s+\d+(?:-[a-z]+)?\s*,\s*(?:comm[ai]|letter[ae]|numer[oi])\b"
    r"|\b(?:del|dei|della|delle|al|ai|alla|alle)\s+(?:comm[ai]|letter[ae]|numer[oi])\b", re.IGNORECASE)
#: The list of commi a row's parts name: «comma 3», «commi 1, 2 e 3-bis».
_COMMI = re.compile(r"\bcomm[ai]\s+(\d+(?:-[a-z]+)?(?:(?:\s*,\s*|\s+e\s+)\d+(?:-[a-z]+)?)*)(?![\w-])",
                    re.IGNORECASE)


def _iso(g: str, m: str, a: str) -> str:
    return f"{a}-{_MESI[m.lower()]:02d}-{int(g):02d}"


def _atto(m: "re.Match") -> tuple[str, str, str]:
    return _TIPI[m["tipo"].lower()], _iso(m["g"], m["m"], m["a"]), m["n"]


def clausola(nota: dict) -> "dict | None":
    """The dated entry-into-force clause of one update note, else None.

    ``{numero, atto, atto_testo, rinviano, disposizione, data, articolo, abrogazione}``: *atto*
    the act whose provision sets the date, as ``(tipo, data, numero)``; *rinviano* the acts
    that amended that provision («come modificato dal …»); *data* ISO; *articolo* the article
    of *atto* the clause names («Le disposizioni dell'articolo 27»), None when it names none;
    *abrogazione* True when the clause defers the article's repeal («la proroga al 31 ottobre
    2027 dell'entrata in vigore della presente abrogazione», with or without «che»).
    """
    testo = " ".join((nota.get("testo") or "").split())
    disp = _DISPOSIZIONE.search(testo)
    if disp is not None:
        entrata = _ENTRATA.search(testo, disp.end())
        atti = list(_ATTO.finditer(testo, 0, disp.start()))
        if entrata is not None and atti:
            articolo = _ARTICOLO_RINVIATO.search(testo, disp.end())
            return _clausola(nota, atti, disp.group(1), _iso(entrata["g"], entrata["m"], entrata["a"]),
                             articolo.group(1) if articolo else None, abrogazione=False)
    proroga = _PROROGA.search(testo)
    if proroga is not None:
        atti = list(_ATTO.finditer(testo, 0, proroga.start()))
        if atti:
            return _clausola(nota, atti, proroga["disp"], _iso(proroga["g"], proroga["m"], proroga["a"]), None,
                             abrogazione=True)
    return None


def _clausola(nota: dict, atti: list, disposizione: str, data: str, articolo: "str | None", *,
              abrogazione: bool) -> dict:
    return {"numero": str(nota.get("numero") or ""), "atto": _atto(atti[0]), "atto_testo": atti[0].group(0),
            "rinviano": [_atto(m) for m in atti[1:]], "disposizione": " ".join(disposizione.split()),
            "data": data, "articolo": articolo, "abrogazione": abrogazione}


def _ordine(c: dict) -> int:
    return int(c["numero"]) if c["numero"].isdigit() else -1


def _catene(note: "list[dict] | None") -> "list[list[dict]]":
    """The clauses of the notes, by provision (same act, same «con l'art. …»)."""
    catene: dict[tuple, list[dict]] = {}
    for nota in note or []:
        c = clausola(nota)
        if c is not None:
            catene.setdefault((c["atto"], c["disposizione"]), []).append(c)
    return list(catene.values())


def _riassunto(clausole: "list[dict]") -> dict:
    """One chain: its latest clause (the highest note number) gives the date."""
    ultima = max(clausole, key=_ordine)
    atti = {ultima["atto"]} | {a for c in clausole for a in c["rinviano"]}
    superate = sorted({c["data"] for c in clausole} - {ultima["data"]})
    articolo = next((c["articolo"] for c in sorted(clausole, key=_ordine, reverse=True) if c["articolo"]), None)
    return {"data": ultima["data"], "nota": ultima["numero"], "atto": ultima["atto"],
            "atto_testo": ultima["atto_testo"], "articolo": articolo, "catena": atti, "superate": superate,
            "disposizione": ultima["disposizione"], "abrogazione": ultima["abrogazione"]}


def rinvio(note: "list[dict] | None", oggi: str) -> "dict | None":
    """The deferred entry into force the article's notes state, when it falls after *oggi*.

    The notes of each provision (same act, same «con l'art. …») form a chain: the latest
    note (the highest number) gives the date in force. Of the chains whose date is after
    *oggi*, the latest date. ``{data, nota, atto, atto_testo, articolo, catena, superate,
    disposizione, abrogazione}``: *catena* every act of the chain (the deferred act and those
    that deferred it), *superate* the earlier dates of the chain. None without such a clause.
    """
    trovati = [r for r in map(_riassunto, _catene(note)) if r["data"] > oggi]
    return max(trovati, key=lambda r: r["data"]) if trovati else None


def rinvio_scaduto(note: "list[dict] | None", oggi: str) -> "dict | None":
    """A deferral the notes may have stopped telling (#177), else None.

    A chain whose latest note moved the date later (the closest earlier note with another date
    gives an earlier one) and whose latest date has passed: the provision that sets it may have moved it again
    without Normattiva adding the note (art. 765 c.p.c.: notes up to 31/10/2026, art. 32,
    comma 3 of d.lgs. 116/2017 at 31/10/2027). A date brought forward, or never moved, is not
    one. Of several, the latest. Shaped as :func:`rinvio`; the provision is read by the caller.
    """
    trovati = []
    for clausole in _catene(note):
        r = _riassunto(clausole)
        # Moved later by the latest note: the closest earlier note giving another date gave an
        # earlier one (2020, 2025, 2023 is a date brought forward, review of #179).
        prima = [c["data"] for c in sorted(clausole, key=_ordine)[:-1] if c["data"] != r["data"]]
        if r["data"] <= oggi and prima and prima[-1] < r["data"]:
            trovati.append(r)
    return max(trovati, key=lambda r: r["data"]) if trovati else None


def articolo_e_comma(disposizione: str) -> "tuple[str | None, str | None]":
    """``("32", "3")`` for «32, comma 3», ``("32", None)`` for «32», ``(None, None)`` otherwise."""
    m = _ARTICOLO_COMMA.match(disposizione or "")
    return (m["art"], m["comma"]) if m else (None, None)


def _blocco_comma(testo: str, comma: "str | None") -> "str | None":
    """The text of *comma* in the provision's article (the whole article without *comma*), on
    one line, amendment markers dropped; None when the comma is not found."""
    righe = (testo or "").replace("((", "").replace("))", "").splitlines()
    if comma:
        inizio = re.compile(rf"^\s*{re.escape(comma)}\s*\.(?:\s|$)")
        blocco, dentro = [], False
        for riga in righe:
            if inizio.match(riga):
                dentro = True
            elif dentro and _INIZIO_COMMA.match(riga):
                break
            if dentro:
                blocco.append(riga)
        if not blocco:
            return None
        righe = blocco
    return " ".join(" ".join(righe).split())


def stato_disposizione(testo: str, comma: "str | None", oggi: str,
                       articolo: "str | None" = None) -> "tuple[str, str | None]":
    """What the provision that sets the date says today, in *comma* of its article.

    *testo* is the article as Normattiva serves it («3. Le disposizioni dell'articolo 27
    entrano in vigore il ((31 ottobre 2027)).»); without *comma*, the whole article.

    - ``("rinvio", data)``: it states one date after *oggi*;
    - ``("in_vigore", None)``: every date it states has passed, or the comma is repealed
      (spent): nothing is deferred any more;
    - ``("ignoto", None)``: the comma is not found, states no date, or more than one date
      after *oggi*; or its date may not be the one of what the chain defers: an exception
      («salvo», «ad eccezione», «in deroga» …), only part of an article («articolo 27, comma
      1», «dei commi 1 e 2»), or another article than *articolo* (the one the chain names).
      Never a guess.
    """
    blocco = _blocco_comma(testo, comma)
    if blocco is None:
        return "ignoto", None
    if _ABROGATO.match(blocco):
        return "in_vigore", None
    if _ECCEZIONE.search(blocco) or _PARTE_DI_ARTICOLO.search(blocco):
        return "ignoto", None
    if articolo and not re.search(rf"\barticol[oi]\s+{re.escape(articolo)}(?![\w-])", blocco, re.IGNORECASE):
        return "ignoto", None
    date = {_iso(m["g"], m["m"], m["a"]) for m in _ENTRATA.finditer(blocco)}
    future = {d for d in date if d > oggi}
    if not date or len(future) > 1:
        return "ignoto", None
    if not future:
        return "in_vigore", None
    return "rinvio", future.pop()


def atti_del_comma(righe: "list[dict] | None", comma: "str | None") -> set[tuple[str, str, str]]:
    """The acts of a version's table of updates whose rows touch *comma* (all rows without it,
    and a row that names no part): the acts that gave the provision its current wording."""
    atti = set()
    for riga in righe or []:
        for voce in riga.get("atti") or []:
            a = voce.get("atto") or {}
            if not (a.get("tipo_atto") and a.get("data") and a.get("numero_atto")):
                continue
            parti = [d.get("parti") for d in voce.get("disposizioni") or []] or [None]
            if comma is None or any(p is None or comma in _commi_nominati(p) for p in parti):
                atti.add((a["tipo_atto"], a["data"], str(a["numero_atto"])))
    return atti


def _commi_nominati(parti: str) -> set[str]:
    """The commi a row's parts name: «commi 1, 2 e 3» -> {1, 2, 3}; never a «numero 3)» or a
    «lettera b)» that follows them."""
    return {c.lower() for m in _COMMI.finditer(parti) for c in re.split(r"\s*,\s*|\s+e\s+", m.group(1))}


def riaperto(s: dict, data: "str | None", atti: "set[tuple[str, str, str]]") -> dict:
    """*s* (:func:`rinvio_scaduto`) with the date its provision states today, read live.

    *data* None: the provision could not be read, or its date is not known (``stato_disposizione``
    «ignoto»). *atti*: the acts
    that gave the provision its current wording, added to the chain. ``data_nota`` keeps the
    date the latest note gives.
    """
    superate = sorted(set(s["superate"]) | {s["data"]}) if data else list(s["superate"])
    return {**s, "data": data, "data_nota": s["data"], "catena": set(s["catena"]) | set(atti),
            "superate": superate}


def _atti_della_versione(righe: "list[dict] | None") -> set[tuple[str, str, str]]:
    """The acts of one version's table of updates (``aggiornamenti.leggi_aggiornamenti``)."""
    atti = set()
    for riga in righe or []:
        for voce in riga.get("atti") or []:
            a = voce.get("atto") or {}
            if a.get("tipo_atto") and a.get("data") and a.get("numero_atto"):
                atti.add((a["tipo_atto"], a["data"], str(a["numero_atto"])))
    return atti


def porta_atto_rinviato(r: dict, righe: dict) -> bool:
    """True when any version read carries the deferred act (``r["atto"]``): the text served may
    hold the deferred amendments, under later ones or not (review of #179)."""
    return any(r["atto"] in _atti_della_versione(rr) for rr in righe.values())


def caso(r: dict, versioni: dict, righe: dict) -> "tuple[str | None, dict]":
    """Which case the article is, from its versions and their tables of updates.

    *versioni* ``{k: (valid_from, valid_to) | None}`` and *righe* ``{k: [rows]}`` as
    ``aggiornamenti.leggi_aggiornamenti`` gives them. ``(None, {})`` when no version in force
    before ``r["data"]`` carries the deferred act (the text does not contain the deferred
    amendments, and nothing is said), or when the date is unknown. Otherwise ``("A",
    {"precedente": (k, from, to), "servita": (k, from), "rinviate_dal", "prima"})``,
    ``("non_in_vigore", {...})`` or ``("B", {...})``, *prima* the version Normattiva gave the
    deferred amendments to first.

    A case A is never assumed: the deferred act must be in one version only (*prima*), which
    carries only acts of the chain, every later version must carry only the acts that deferred
    it (art. 765 c.p.c.: version 4, then version 5 by d.l. 162/2019, so version 3 is in force),
    and the window of the version before *prima* must be known.
    """
    if not r.get("data"):
        return None, {}
    finestre = {k: v for k, v in versioni.items() if v}
    tutte_con_atto = [k for k, rr in righe.items() if r["atto"] in _atti_della_versione(rr)]
    con_atto = [k for k in tutte_con_atto if finestre.get(k) and finestre[k][0] < r["data"]]
    if not con_atto:
        return None, {}
    ultima = max(versioni)
    servita = (ultima, finestre[ultima][0]) if finestre.get(ultima) else (ultima, None)
    prima = min(con_atto)  # the version Normattiva gave the deferred amendments to first
    info = {"servita": servita, "rinviate_dal": finestre[prima][0], "prima": prima}
    rinviano = r["catena"] - {r["atto"]}

    def solo(k: int, ammessi: set) -> bool:
        atti = _atti_della_versione(righe.get(k))
        return bool(atti) and atti <= ammessi

    # The deferred act in one version only (review of #179: a version it made by a provision
    # already in force must not be dropped), and after it only the acts that deferred it.
    solo_catena = (len(tutte_con_atto) == 1 and solo(prima, r["catena"])
                   and all(solo(k, rinviano) for k in range(prima + 1, ultima + 1)))
    if solo_catena and prima == 1:
        return "non_in_vigore", info
    precedente = finestre.get(prima - 1)
    if solo_catena and precedente and precedente[1]:
        return "A", {**info, "precedente": (prima - 1, precedente[0], precedente[1])}
    return "B", info


def _oggetto(r: dict) -> str:
    atto = r["atto_testo"] + (f", art. {r['articolo']}" if r.get("articolo") else "")
    if r.get("abrogazione"):
        return f"l'abrogazione dell'articolo disposta dal {atto}"
    return f"l'entrata in vigore delle modifiche del {atto}"


def _premessa(r: dict) -> str:
    """Who defers what to when: the note, or the provision read live when the notes stopped."""
    oggetto = _oggetto(r)
    if "data_nota" not in r:
        return f"la nota ({r['nota']}) di Normattiva rinvia al {r['data']} {oggetto}"
    disposizione = f"l'art. {r['disposizione']} del {r['atto_testo']}"
    if r.get("data") is None:
        return (f"la nota ({r['nota']}) di Normattiva fissa al {r['data_nota']} {oggetto}, ma non è stato possibile "
                f"leggere sull'art. {r['disposizione']} del {r['atto_testo']} se quella data è stata rinviata ancora")
    return (f"{disposizione} rinvia al {r['data']} {_oggetto_proprio(r)} (l'ultima nota di Normattiva, la "
            f"({r['nota']}), dà ancora il {r['data_nota']})")


def _oggetto_proprio(r: dict) -> str:
    """What the provision defers, said of its own act («le sue modifiche»)."""
    if r.get("abrogazione"):
        return "l'abrogazione dell'articolo da esso disposta"
    if r.get("articolo"):
        return f"l'entrata in vigore del suo art. {r['articolo']}"
    return "l'entrata in vigore delle sue modifiche"


def _piu_versioni(r: dict) -> bool:
    """Case A over more than one version (art. 765 c.p.c.: versions 4 and 5)."""
    servita = r.get("servita") or (None, None)
    return r.get("prima") is not None and servita[0] is not None and r["prima"] < servita[0]


def avviso(r: dict) -> str:
    """The notice of a deferred entry into force, by case (``r["caso"]``)."""
    premessa = _premessa(r)
    servita = (r.get("servita") or (None, None))[1]
    if r.get("caso") == "A":
        k, dal, al = r["precedente"]
        if r.get("abrogazione"):
            stato = f"Normattiva dà l'articolo come abrogato dal {servita}"
        elif _piu_versioni(r):
            stato = (f"Normattiva dà come vigenti dal {r['rinviate_dal']} le versioni che le contengono, fino alla "
                     f"{r['servita'][0]}")
        else:
            stato = f"Normattiva dà come vigente dal {servita} la versione che le contiene"
        quale = f"la versione {k}" if _piu_versioni(r) else "la versione precedente"
        return (f"{premessa}, ma {stato}: il testo riportato è {quale}, in vigore dal {dal} (Normattiva la chiude il "
                f"{al})")
    if r.get("caso") == "non_in_vigore":
        return f"{premessa}, che hanno inserito l'articolo: Normattiva lo dà come vigente dal {servita}"
    if r.get("abrogazione") and r.get("caso") in ("B", None):
        # A deferred repeal not resolved (table or previous version unread): the text served is
        # Normattiva's repeal notice. Its date not known: whether the repeal is in force is not.
        if r.get("data") is None:
            return (f"{premessa}: Normattiva dà l'articolo come abrogato, e non è verificato se l'abrogazione sia già "
                    "in vigore; verificarlo prima di citarlo")
        return (f"{premessa}, ma Normattiva dà già l'articolo come abrogato e il testo in vigore fino a quella data non "
                "è stato letto: verificarlo prima di citarlo")
    if r.get("caso") == "B":
        if r.get("precedente_non_letta"):
            return (f"{premessa}, ma Normattiva dà come vigente dal {servita} la versione che le contiene e la "
                    "versione precedente non è stata letta: il testo riportato non è quello in vigore oggi; "
                    "verificarlo prima di citarlo")
        # #177: Normattiva may have laid later amendments over the deferred ones, or rewritten
        # them (art. 518 c.p.c., d.lgs. 164/2024): what the text holds of them is not known.
        return (f"{premessa}, ma Normattiva le dà come vigenti dal {r.get('rinviate_dal') or servita} e vi ha "
                "applicato modifiche successive: il testo riportato può contenerle in tutto o in parte, e non è "
                "verificato che sia il testo in vigore oggi: verificarlo prima di citarlo")
    if "data_nota" in r and r.get("data") is None:
        return (f"{premessa}: il testo riportato può contenere modifiche non ancora in vigore; verificarlo prima di "
                "citarlo")
    return (f"{premessa}: non è stato possibile verificare se il testo riportato le contiene già; "
            "verificarlo prima di citarlo")


def sintesi(r: dict) -> dict:
    """What an answer carries of *r*, JSON-ready: ``{data, nota, atto, articolo, caso}``, plus
    ``abrogazione`` (and ``abrogato_da``) for a deferred repeal, and ``data_nota`` and
    ``disposizione`` when the date was read in the provision because the notes stopped."""
    out = {"data": r["data"], "nota": r["nota"], "atto": r["atto_testo"], "articolo": r.get("articolo"),
           "caso": r.get("caso")}
    if r.get("abrogazione"):
        out["abrogazione"] = True
        if r.get("abrogato_da"):
            out["abrogato_da"] = r["abrogato_da"]
    if "data_nota" in r:
        out["data_nota"], out["disposizione"] = r["data_nota"], f"art. {r['disposizione']}"
    return out


def nota_verifica(s: dict) -> str:
    """What ``verifica_citazioni`` says of a deferral, from :func:`sintesi`."""
    oggetto = ("l'abrogazione dell'articolo disposta dal" if s.get("abrogazione")
               else "l'entrata in vigore di modifiche del")
    if "data_nota" not in s:
        base = f"la nota ({s['nota']}) di Normattiva rinvia al {s['data']} {oggetto} {s['atto']}"
    elif s.get("data") is None:
        base = (f"la nota ({s['nota']}) di Normattiva fissa al {s['data_nota']} {oggetto} {s['atto']}, ma non è "
                f"stato possibile leggere sull'{s['disposizione']} se quella data è stata rinviata ancora")
    else:
        proprio = ("l'abrogazione dell'articolo da esso disposta" if s.get("abrogazione")
                   else "l'entrata in vigore di sue modifiche")
        base = (f"l'{s['disposizione']} del {s['atto']} rinvia al {s['data']} {proprio} (la nota ({s['nota']}) di "
                f"Normattiva dà ancora il {s['data_nota']})")
    if s.get("abrogazione"):
        if s.get("caso") == "A":
            return base + ": l'articolo è ancora in vigore, nella versione precedente all'abrogazione"
        if s.get("data") is None:
            return base + ": non è verificato se l'abrogazione sia già in vigore"
        return base + ": l'articolo è in vigore fino a quella data, e il suo testo non è stato letto"
    return base + {
        "A": ": il testo in vigore è la versione precedente a quella che Normattiva dà come vigente",
        "B": (": Normattiva le dà come vigenti e vi ha applicato modifiche successive, e non è verificato che il "
              "suo testo sia quello in vigore"),
        "non_in_vigore": ": l'articolo, inserito da quelle modifiche, non è ancora in vigore",
    }.get(s.get("caso"), ": il testo può contenere modifiche non ancora in vigore" if "data_nota" in s
          else ": non è stato possibile verificare se il testo le contiene già")


def avviso_storia(r: dict, caso: "str | None", info: dict) -> str:
    """The notice of a deferral on an article's history (``api.modifiche_articolo``)."""
    premessa = _premessa(r)
    servita = info.get("servita") or (None, None)
    if caso == "A":
        k, dal, _al = info["precedente"]
        if r.get("abrogazione"):
            return (f"{premessa}: Normattiva dà l'articolo come abrogato dal {servita[1]} (versione {servita[0]}), ma "
                    f"l'abrogazione non è in vigore; il testo in vigore è la versione {k}, dal {dal}")
        if _piu_versioni(info):
            return (f"{premessa}: Normattiva dà come vigenti dal {info['rinviate_dal']} le versioni dalla "
                    f"{info['prima']} alla {servita[0]}, ma non sono in vigore; il testo in vigore è la versione {k}, "
                    f"dal {dal}")
        return (f"{premessa}: Normattiva dà la versione {servita[0]} come vigente dal {servita[1]}, ma non è in "
                f"vigore; il testo in vigore è la versione {k}, dal {dal}")
    if caso == "non_in_vigore":
        return (f"{premessa}, che hanno inserito l'articolo: non è ancora in vigore (Normattiva lo dà come vigente "
                f"dal {servita[1]})")
    if r.get("abrogazione"):
        if r.get("data") is None:
            return f"{premessa}: non è verificato se l'abrogazione sia già in vigore"
        return f"{premessa}: non è stato possibile verificare quale versione dell'articolo è in vigore"
    if caso == "B":
        return (f"{premessa}: Normattiva le dà come vigenti dal {info.get('rinviate_dal')} e vi ha applicato le "
                f"versioni successive, fino alla {servita[0]}: possono contenerle in tutto o in parte, e non è "
                "verificato quale sia il testo in vigore")
    if "data_nota" in r and r.get("data") is None:
        return (f"{premessa}: le versioni che Normattiva dà come vigenti possono contenere modifiche non ancora in "
                "vigore")
    return f"{premessa}: non è stato possibile verificare quali versioni le contengono"

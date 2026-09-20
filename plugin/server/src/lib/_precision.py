"""The precision a tool claims, and what an unverified or expired table does to it.

Most tools declare, in their own docstring, how precise their answer is --
`Precisione: ESATTO per gli indici FOI applicati`, `Precisione: INDICATIVO
(ricerca per keyword)`. Until now that line was prose in the tool description and
nothing observed it: a table that stopped being maintained, or that nobody ever
sourced, made the claim false without anything in the server noticing.

This module turns the claim into something the server acts on, using the three
words the tools already use:

* `ESATTO` -- the answer asserts a figure;
* `INDICATIVO` -- the answer orients and says so;
* `STIMATO` -- the answer is a forecast.

A tool resting on a table that is `non_verificata` (nobody established where it
comes from) or `scaduta` (its covered period has ended) cannot keep claiming what
it declared. Two things can happen, and neither is a footnote: the grade drops a
step and the answer says so structurally, or the tool refuses to compute at all
and explains what would unblock it.

A refusal is also a starting point, not a wall. The caller can accept a lower
grade for that call (`accetta_precisione`): the answer is then given at the grade
the table can support, and it says the acceptance is what allowed it. What the
acceptance cannot do is restore the withdrawn claim -- asking to keep `ESATTO` on
a table nobody sources is refused with the highest grade that *is* available --
and it cannot make a wrong number right: an expired table under a figure about
today stays a refusal whatever grade the caller accepts, because "less precise"
and "computed from a period that has ended" are not the same failure. That is the
line this module draws, and it is the reason `decide` takes the acceptance as an
input rather than the caller taking the answer as an output.

The two states are deliberately not symmetric, because they fail differently:

* an unverified table is a hole in provenance and no date can fill it, so an
  exact claim resting on it is not downgraded but withdrawn -- a downgraded
  "ESATTO" would still be the tool asserting a figure it cannot back;
* an expired table is a hole in coverage, and a calculation about a *closed*
  period does not become wrong the day the table stops being refreshed. Only an
  answer anchored to the present would pass stale numbers off as current, and
  that is what `_clock.consulted()` reveals: whether the call asked what day it
  is. A tool that never reads the clock is answering about a period it already
  knows, so it degrades; a tool that does is answering about today, so it stops.

Nothing here is hand-maintained per tool: the grade comes from the docstring the
tool already carries, `scripts/audit_tool_annotations.py` fails the suite when a
tool that applies a table declares no grade (or declares one that is not a word
this module knows), and the tables come from `_data`.
"""

from __future__ import annotations

import contextvars
import re
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator

#: The grades, strongest first. The same three words the tools already declare.
ESATTO = "ESATTO"
INDICATIVO = "INDICATIVO"
STIMATO = "STIMATO"

GRADI = (ESATTO, INDICATIVO, STIMATO)

#: Strongest first: what a lower grade costs, and what an acceptance may grant.
SCALA: dict[str, int] = {ESATTO: 3, INDICATIVO: 2, STIMATO: 1}

#: The next honest grade down, or None when there is nothing left to claim.
_DECLINO: dict[str, str | None] = {ESATTO: INDICATIVO, INDICATIVO: STIMATO, STIMATO: None}

#: The line a tool's docstring carries, e.g.
#: `Precisione: ESATTO per tassi legali storici e indici FOI ufficiali`.
_RIGA = re.compile(r"^[ \t]*Precisione:[ \t]*([A-Za-zÀ-ÿ]+)[ \t]*(.*)$", re.MULTILINE)

#: An out-of-vocabulary grade in the docstring is not a reason to be lenient:
#: reading it as the strongest claim is what makes the audit's failure the only
#: thing standing between a new word and an unexamined exactness claim.
_UNKNOWN = ESATTO


@dataclass(frozen=True)
class Dichiarata:
    """What a tool's docstring claims, and what the claim rests on."""

    grado: str
    #: The tool's own words after the grade ("per indici FOI"), quoted back in a
    #: refusal so the tool says which claim it is withdrawing.
    qualificatore: str = ""
    riga: str = ""


@dataclass(frozen=True)
class Esito:
    """What the answer is worth, given the tables it rests on."""

    dichiarata: str
    #: A grade, or `"nessuna"` when the tool must not compute.
    effettiva: str
    #: `"piena"`, `"ridotta"` or `"rifiuta"`.
    esito: str
    #: The states that caused it, e.g. `("non_verificata",)`.
    motivi: tuple[str, ...] = ()
    #: False when no acceptance can unlock the computation -- a stale table under
    #: a figure about today is wrong, not imprecise.
    negoziabile: bool = False
    #: The highest grade a caller's acceptance can buy, when there is a refusal.
    concedibile: str | None = None
    #: The grade the caller accepted, when that is what let the answer stand.
    accettata: str | None = None

    @property
    def rifiuta(self) -> bool:
        return self.esito == "rifiuta"

    def to_dict(self, nota: str = "") -> dict:
        out = {"dichiarata": self.dichiarata, "effettiva": self.effettiva}
        if self.motivi:
            out["motivo"] = "una tabella applicata risulta " + " e ".join(self.motivi)
        if nota:
            out["nota"] = nota
        if self.concedibile:
            out["concedibile"] = self.concedibile
        if self.accettata:
            out["accettata"] = self.accettata
        return out


def declared(fn: object) -> Dichiarata | None:
    """The grade a tool declares in its docstring, or None when it declares none.

    Parsed rather than looked up: the docstring is what the calling model reads
    before choosing the tool, so it is the one place the claim can live without
    a second copy drifting away from it.
    """
    doc = getattr(fn, "__doc__", None) or ""
    found = _RIGA.search(doc)
    if found is None:
        return None
    grado, qualificatore = found.group(1).upper(), found.group(2).strip()
    return Dichiarata(grado=grado, qualificatore=qualificatore, riga=found.group(0).strip())


def _tetto(effettiva: str, accettata: str | None) -> str:
    """An acceptance also acts as a ceiling on what the answer claims.

    A caller who says "I only want this at `STIMATO`" gets `STIMATO` even where the
    table would have supported `INDICATIVO`: being more cautious than necessary is
    always allowed, and the field that records the answer's worth should say what
    the caller asked for.
    """
    if accettata in SCALA and SCALA[accettata] < SCALA[effettiva]:
        return accettata
    return effettiva


def _concedibile(grado: str) -> str:
    """The highest grade an acceptance can buy for a table that stays as it is.

    One step below the declared claim, and never below `STIMATO` -- past that
    there is no word left for "this is a guess", and a tool that already offers a
    forecast has nothing to trade.
    """
    return _DECLINO.get(grado) or STIMATO


def _negoziato(grado: str, flag: tuple[str, ...], accettata: str | None) -> Esito:
    """A refusal, or the reduced answer an explicit acceptance buys.

    The caller cannot buy back the claim: an acceptance above what the table
    supports is itself refused, and the answer names the grade that would have
    worked, so the caller retries with something the server can honour. An
    acceptance *below* what is available is honoured as given -- being more
    cautious than necessary is always allowed.
    """
    concedibile = _concedibile(grado)
    if accettata is not None and accettata in SCALA:
        if SCALA[accettata] <= SCALA[concedibile]:
            return Esito(grado, accettata, "ridotta", flag, accettata=accettata)
    return Esito(
        grado,
        "nessuna",
        "rifiuta",
        flag,
        negoziabile=True,
        concedibile=concedibile,
        accettata=accettata,
    )


def decide(
    dichiarata: str | None,
    stati: "list[str] | tuple[str, ...]",
    ancorata_al_presente: bool = False,
    accettata: str | None = None,
) -> Esito:
    """What the answer is worth, given the states of the tables it applied.

    `stati` are the states among the applied tables that go beyond "in order"
    (`_data.warnings`), and `ancorata_al_presente` says whether the call read the
    clock. No state means the declared grade stands, and the caller adds nothing
    to the answer. `accettata` is the grade the caller declared acceptable for
    this call; it only matters where the answer would otherwise be refused, and
    only where the failure is about *how well* the table is known rather than
    about whether it is out of date for the question being asked.
    """
    grado = dichiarata if dichiarata in GRADI else _UNKNOWN
    flag = tuple(sorted(set(stati)))
    if not flag:
        return Esito(grado, grado, "piena")

    if "non_verificata" in flag:
        # Nobody vouched for the table: an exact claim is withdrawn, an
        # indicative one steps down, and a forecast has nothing left to trade.
        if grado == INDICATIVO:
            return Esito(grado, _tetto(STIMATO, accettata), "ridotta", flag, accettata=accettata)
        return _negoziato(grado, flag, accettata)

    # Only coverage: a stale table is fatal for a figure about today, and merely
    # a caveat for a figure about a period that has already closed.
    if ancorata_al_presente:
        return Esito(grado, "nessuna", "rifiuta", flag, negoziabile=False)
    piu_basso = _DECLINO.get(grado)
    if piu_basso is None:
        return _negoziato(grado, flag, accettata)
    return Esito(grado, _tetto(piu_basso, accettata), "ridotta", flag, accettata=accettata)


@dataclass
class _Box:
    """The outcome of one call, in an object the recorder can mutate.

    A shared object rather than a value set on the context variable, because the
    framework may run the tool in a child context: a `.set()` there would never
    reach the middleware that reports it, while a mutation of an object created
    before the call is visible to both. `src/lib/_tables_open.py` works the same
    way for the same reason, and the wire test is what caught this one.
    """

    esito: Esito | None = None


#: The box of the call in flight, for the middleware that reports it in `_meta`
#: (the only channel a tool returning a string has).
CURRENT: contextvars.ContextVar[_Box | None] = contextvars.ContextVar(
    "legal_it_precision_outcome", default=None
)


def note(esito: Esito) -> None:
    """Record the outcome for the current call (a no-op outside one)."""
    box = CURRENT.get()
    if box is not None and box.esito is None:
        box.esito = esito


def current() -> Esito | None:
    """The outcome recorded for the current call, if any."""
    box = CURRENT.get()
    return box.esito if box is not None else None


@contextmanager
def recording() -> Iterator[_Box]:
    """Keep each call's outcome to itself."""
    box = _Box()
    token = CURRENT.set(box)
    try:
        yield box
    finally:
        CURRENT.reset(token)

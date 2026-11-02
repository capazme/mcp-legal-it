"""A rule that still governs today and stops on a known date.

`_regime.py` flags tools that compute under a rule already replaced. This module
covers the step before that: the rule a tool applies is the one in force today,
but the law has already fixed the day it stops applying. The D.P.R. 131/1986
(imposta di registro) is the case in point: art. 204 co. 1 lett. f of the testo
unico in D.Lgs. 123/2025 abrogates its articles, tariffa and prospetto dei
coefficienti from the date of art. 205, which art. 4 co. 5 d.l. 200/2025 moved to
1 January 2027 (decision LI-061).

Until that date the answer is right and keeps the grade the tool declares; it
only has to say that the rule has an end date, because a model computing today
for an act with effects next year would otherwise take the figure as final.
From that date on the tool must not apply the old rule in silence. It refuses,
and the refusal is not negotiable through `accetta_precisione`: a figure computed
under a rule that no longer governs the date of the calculation is wrong, not
imprecise -- the same line `_precision.py` draws for an expired table under a
figure about today.

The date is the calculation date, read through `_clock.today()`, so a pinned
`LEGAL_TODAY` moves it. Reading it is a recorded consult on purpose: which rule
applies is a question about today, and that is what the consult means.

    @mcp.tool(tags={"calcolo", "proprieta"})
    @transitoria(DPR_131_1986)
    @sourced("tassi_legali")
    def imposta_registro_locazioni(...):
        ...

Applied under `@mcp.tool(...)` and outside `@sourced`, like `@previgente`:
`wraps` carries the signature and the markers `@sourced` set, so the schema and
the audit see the tool unchanged.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from datetime import date
from functools import wraps

from . import _clock, _precision

#: The field the notice lands in, in a dict answer.
CAMPO_AVVISO = "avviso_disciplina"
#: The error code of the refusal.
ERRORE = "disciplina_non_applicabile"


@dataclass(frozen=True)
class Disciplina:
    """A rule in force today with a fixed last day."""

    #: How the answer names the rule, e.g. "D.P.R. 131/1986".
    nome: str
    #: The last day the rule applies; from the next day the tool refuses.
    ultimo_giorno: date
    #: What applies from the day after, with the provision that fixes the date.
    subentra: str
    #: A pending change to the rule that follows, named until it is final; empty
    #: when there is none. Only what an official source states (LI-062).
    in_corso: str = ""

    @property
    def avviso(self) -> str:
        """The fixed notice a computed answer carries."""
        return (
            f"Calcolo secondo il {self.nome}, applicabile fino al "
            f"{self.ultimo_giorno.strftime('%d/%m/%Y')}. Dal "
            f"{_giorno_esteso(self._primo_giorno_dopo)} si applica {self.subentra}: "
            "per atti con effetti da quella data il calcolo va rifatto."
            + (f" {self.in_corso}" if self.in_corso else "")
        )

    @property
    def _primo_giorno_dopo(self) -> date:
        return date.fromordinal(self.ultimo_giorno.toordinal() + 1)

    def applicabile(self, giorno: date) -> bool:
        return giorno <= self.ultimo_giorno

    def rifiuto(self, giorno: date, grado: str | None) -> dict:
        """The answer when the calculation date is past the rule's last day."""
        return {
            "errore": ERRORE,
            "messaggio": (
                f"Calcolo non eseguito: il tool applica il {self.nome}, applicabile fino al "
                f"{self.ultimo_giorno.strftime('%d/%m/%Y')}, e la data del calcolo è il "
                f"{giorno.strftime('%d/%m/%Y')}. Dal {_giorno_esteso(self._primo_giorno_dopo)} "
                f"si applica {self.subentra}, che il tool non implementa ancora: nessun importo "
                "viene fornito secondo una disciplina che non si applica più."
            ),
            "data_calcolo": giorno.isoformat(),
            "disciplina": {
                "applicata_dal_tool": self.nome,
                "applicabile_fino_al": self.ultimo_giorno.isoformat(),
                "subentra": self.subentra,
            },
            "precisione": {
                "dichiarata": grado if grado in _precision.GRADI else _precision.ESATTO,
                "effettiva": "nessuna",
                "motivo": f"il {self.nome} non si applica alla data del calcolo",
            },
        }


_MESI = (
    "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
    "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre",
)


def _giorno_esteso(giorno: date) -> str:
    """«1° gennaio 2027»: the ordinal on the first of the month, as the law writes it."""
    numero = "1°" if giorno.day == 1 else str(giorno.day)
    return f"{numero} {_MESI[giorno.month - 1]} {giorno.year}"


#: The imposta di registro rule (decision LI-061). Art. 204 co. 1 lett. f D.Lgs.
#: 123/2025 abrogates its articles 1-50, 54-68, 77, 79-81, the tariffa, the tabella
#: and the prospetto dei coefficienti from the date of art. 205 co. 1, which art. 4
#: co. 5 d.l. 200/2025 set to 1 January 2027 (both read on Normattiva, 2 Nov 2026).
#: `in_corso` is the Consiglio dei ministri press release n. 192 of 13 Oct 2026
#: (governo.it): a correttivo of the testi unici, registro included, approved in
#: preliminary examination. Drop it once that decree is final or abandoned.
DPR_131_1986 = Disciplina(
    nome="D.P.R. 131/1986",
    ultimo_giorno=date(2026, 12, 31),
    subentra=(
        "il testo unico di cui al D.Lgs. 123/2025 (art. 205, come modificato dall'art. 4, "
        "comma 5, del d.l. 200/2025)"
    ),
    in_corso=(
        "Uno schema di decreto legislativo correttivo dei testi unici, che riguarda anche "
        "l'imposta di registro, è stato approvato in esame preliminare dal Consiglio dei "
        "ministri il 13/10/2026: non ancora in vigore."
    ),
)


def _attach(result: object, disciplina: Disciplina) -> object:
    """The notice on a computed answer; an input error carries none."""
    if isinstance(result, dict):
        if "errore" in result:
            return result
        return {**result, CAMPO_AVVISO: disciplina.avviso}
    if isinstance(result, str):
        return result + f"\n\n> **Disciplina applicata**: {disciplina.avviso}"
    return result


def transitoria(disciplina: Disciplina):
    """Mark a tool as applying a rule that stops on `disciplina.ultimo_giorno`."""

    def decorate(fn):
        grado = _precision.declared(fn)
        dichiarata = grado.grado if grado else None

        if inspect.iscoroutinefunction(fn):
            @wraps(fn)
            async def wrapper(*args, **kwargs):
                giorno = _clock.today()
                if not disciplina.applicabile(giorno):
                    return disciplina.rifiuto(giorno, dichiarata)
                return _attach(await fn(*args, **kwargs), disciplina)
        else:
            @wraps(fn)
            def wrapper(*args, **kwargs):
                giorno = _clock.today()
                if not disciplina.applicabile(giorno):
                    return disciplina.rifiuto(giorno, dichiarata)
                return _attach(fn(*args, **kwargs), disciplina)

        # `wraps` copies `__dict__`: `__signature__`, `__sourced_datasets__` and the
        # other markers travel with the wrapper, so the schema does not change.
        wrapper.__disciplina_transitoria__ = disciplina
        return wrapper

    return decorate

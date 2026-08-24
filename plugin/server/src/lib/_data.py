"""Load the hand-maintained legal tables and carry their vintage with them.

Every calculation in this server ultimately rests on a JSON table someone typed
by hand: IRPEF brackets, forensic parameters, ISTAT indices, usury thresholds.
Each is correct when written and silently wrong some months later, and a tool
that prints a number without saying how old its source is leaves the reader no
way to notice. So each table declares a `_vintage` block, this module reads it,
and `footer()` renders it as a line the tool appends to its answer.

`verifica: "da_verificare"` is a deliberate value, not an oversight: it means
nobody has established the table's currency yet, and it renders as an explicit
warning. Inventing a plausible date would be worse than admitting the gap.

`scripts/update-data.py --strict` fails CI on a table whose covered period has
elapsed or whose vintage is still unverified, so a gap cannot sit unnoticed.
"""

from __future__ import annotations

import inspect
import json
from dataclasses import dataclass
from datetime import date, timedelta
from functools import lru_cache, wraps
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

#: Nobody has established this table's currency yet.
UNVERIFIED = "da_verificare"
#: A scheduled job refreshes this table from an official source.
AUTOMATIC = "automatica"
#: A human transcribes this table from its source.
MANUAL = "manuale"


@dataclass(frozen=True)
class Vintage:
    """What a table says about its own currency.

    Two distinct facts, rarely the same date. `aggiornato_al` is when a human
    last reconciled the table with its source — always in the past.
    `copre_fino_a` is the last period the table actually covers, which for a
    bracket or rate table is usually in the future. For a reader deciding
    whether a number applies to their case the second is what matters, so it
    wins when both are present. Some tables (a Milan damages edition, a set of
    ATECO codes) have neither: they state a source and no period, and say so.
    """

    dataset: str
    aggiornato_al: date | None
    copre_fino_a: date | None
    fonte: str
    verifica: str
    nota: str = ""
    #: Grace period after `copre_fino_a`, for sources that publish in arrears.
    #: ISTAT posts a month's FOI index about a month later, so the series
    #: trailing the calendar by a few weeks is normal, not stale.
    tolleranza_giorni: int = 0

    @property
    def verificato(self) -> bool:
        """True once a human has declared where this table comes from."""
        return self.verifica != UNVERIFIED

    def scaduto(self, oggi: date | None = None) -> bool:
        """True when the covered period has already ended."""
        if self.copre_fino_a is None:
            return False
        limite = self.copre_fino_a + timedelta(days=self.tolleranza_giorni)
        return limite < (oggi or date.today())

    def to_line(self) -> str:
        """One human-readable line, in Italian, for a tool's answer."""
        label = self.dataset.replace("_", " ")
        coda = f" — {self.nota}" if self.nota else ""

        if not self.verificato:
            return (
                f"{label}: provenienza e data non verificate{coda}. "
                "Controllare la fonte prima dell'uso in un atto."
            )
        if self.copre_fino_a is not None:
            fino = self.copre_fino_a.strftime("%d/%m/%Y")
            avviso = " — PERIODO SCADUTO, verificare la fonte" if self.scaduto() else ""
            return f"{label}: copre fino al {fino} ({self.fonte}){avviso}{coda}"
        if self.aggiornato_al is not None:
            giorno = self.aggiornato_al.strftime("%d/%m/%Y")
            return f"{label}: aggiornati al {giorno} ({self.fonte}){coda}"
        return f"{label}: {self.fonte} — periodo di validità non dichiarato{coda}"


def _parse_date(raw: object) -> date | None:
    return date.fromisoformat(str(raw)) if raw else None


@lru_cache(maxsize=None)
def load(dataset: str) -> dict | list:
    """Read `<dataset>.json` from the data directory."""
    return json.loads((DATA_DIR / f"{dataset}.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=None)
def vintage(dataset: str) -> Vintage:
    """Read the `_vintage` block of a table.

    A table without the block reads as unverified rather than raising, so adding
    a table never breaks a tool at runtime — `scripts/update-data.py --strict`
    is what refuses to let it stay undeclared.
    """
    payload = load(dataset)
    block = payload.get("_vintage", {}) if isinstance(payload, dict) else {}
    return Vintage(
        dataset=dataset,
        aggiornato_al=_parse_date(block.get("aggiornato_al")),
        copre_fino_a=_parse_date(block.get("copre_fino_a")),
        fonte=block.get("fonte", "fonte non dichiarata"),
        verifica=block.get("verifica", UNVERIFIED),
        nota=block.get("nota", ""),
        tolleranza_giorni=int(block.get("tolleranza_giorni", 0)),
    )


def footer(*datasets: str) -> str:
    """A markdown block naming the tables a tool applied and how current they are.

    Append it to a tool's answer so the age of the numbers travels with the
    numbers, instead of the reader having to go and ask.
    """
    if not datasets:
        return ""
    righe = "\n".join(f"> - {vintage(d).to_line()}" for d in datasets)
    return f"\n\n> **Dati applicati**\n{righe}"


def all_datasets() -> list[str]:
    """Every table shipped with the server, by name."""
    return sorted(p.stem for p in DATA_DIR.glob("*.json"))


def _attach(result: object, datasets: tuple[str, ...]) -> object:
    """Carry the vintage alongside whatever shape a tool returns."""
    if isinstance(result, str):
        return result + footer(*datasets)
    if isinstance(result, dict):
        return {**result, "dati_applicati": [vintage(d).to_line() for d in datasets]}
    return result  # a bare float/int/date has nowhere to put it; left untouched


def sourced(*datasets: str):
    """Declare which hand-maintained tables a tool reads, and say so in its answer.

    Applied under `@mcp.tool(...)` so FastMCP registers the wrapper; `wraps`
    keeps the signature it builds the schema from. Every return path is covered,
    which a footer appended by hand at each `return` would not be.

        @mcp.tool(tags={"interessi"})
        @sourced("tassi_legali")
        def interessi_legali(...) -> dict:
            ...
    """
    def decorate(fn):
        if inspect.iscoroutinefunction(fn):
            @wraps(fn)
            async def wrapper(*args, **kwargs):
                return _attach(await fn(*args, **kwargs), datasets)
        else:
            @wraps(fn)
            def wrapper(*args, **kwargs):
                return _attach(fn(*args, **kwargs), datasets)
        wrapper.__sourced_datasets__ = datasets  # read by the coverage test
        return wrapper
    return decorate

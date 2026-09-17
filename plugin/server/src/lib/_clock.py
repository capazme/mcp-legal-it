"""The only place in this server that reads the wall clock.

Several tools are "as of today" by design: prescriptions, deadlines, current
IRPEF brackets, the running year for the Consulta dumps, the analysis date
stamped on a supplier report. That makes them non-reproducible, which is a
problem for exactly two kinds of caller:

* a test that wants to know whether a *number* changed -- if the output moves
  with the calendar, a golden-value test either rots or has to give up on the
  interesting half of the surface;
* a document drafted today that has to be reproducible tomorrow (a quote, a
  report, a deadline computation someone re-runs to check it).

`LEGAL_TODAY` / `LEGAL_NOW` pin the clock for those callers:

    LEGAL_TODAY=2026-09-15                 # date.today() equivalent
    LEGAL_NOW=2026-09-15T12:00:00          # datetime.now() equivalent

with `LEGAL_NOW` also serving `today()` (its date part). Both are unset in
normal operation, and then these helpers return the real clock.

This module is the single reader of either variable, so `date.today()` and
`datetime.now()` must not be called anywhere else: the audit fails when a new
call site appears, which is what makes a pinned run actually reproducible.

Being the single reader also makes this module the place that can say *whether a
call read the calendar at all*, which is a different fact from which day it is:
see `recording()`. `src/lib/_data.py` uses it to decide what an expired table
means, because an answer computed for a closed period does not become wrong when
a rate table stops being refreshed, while an answer anchored to today does.
"""

from __future__ import annotations

import contextvars
import os
from contextlib import contextmanager
from datetime import date, datetime
from typing import Iterator

TODAY_ENV = "LEGAL_TODAY"
NOW_ENV = "LEGAL_NOW"

#: Names read in the current call (`today`, `now`), or None outside one.
CURRENT: contextvars.ContextVar[set[str] | None] = contextvars.ContextVar(
    "legal_it_clock_reads", default=None
)


def _note(name: str) -> None:
    """Record that the current call asked for the current date or time."""
    active = CURRENT.get()
    if active is not None:
        active.add(name)


@contextmanager
def recording() -> Iterator[set[str]]:
    """Collect, for the duration of the block, how the clock was consulted."""
    reads: set[str] = set()
    token = CURRENT.set(reads)
    try:
        yield reads
    finally:
        CURRENT.reset(token)


def consulted() -> list[str]:
    """What the current call has asked the clock for, sorted; empty outside one."""
    return sorted(CURRENT.get() or ())


def _parse(raw: str) -> datetime | None:
    text = raw.strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        # A malformed override is a bug in the caller's environment, not a
        # reason to make the server unpredictable: say so and use the clock.
        print(
            "[_clock] ignoring %r: expected an ISO date or datetime" % raw,
            flush=True,
        )
        return None


def now() -> datetime:
    """The current time, or `LEGAL_NOW` when it is set."""
    _note("now")
    pinned = _parse(os.environ.get(NOW_ENV, ""))
    return pinned if pinned is not None else datetime.now()


def today() -> date:
    """Today, or the pinned date (`LEGAL_TODAY`, else the date part of `LEGAL_NOW`).

    Reading this is the signal that an answer is anchored to the present, which
    is what turns an expired table from a footnote into a refusal. It goes
    through `now()` as it always did, so a caller that asks the date is recorded
    as having read the clock -- which is the only question `_data` asks of it.
    """
    _note("today")
    override = _parse(os.environ.get(TODAY_ENV, ""))
    return override.date() if override is not None else now().date()

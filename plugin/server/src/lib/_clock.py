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
"""

from __future__ import annotations

import os
from datetime import date, datetime

TODAY_ENV = "LEGAL_TODAY"
NOW_ENV = "LEGAL_NOW"


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
    pinned = _parse(os.environ.get(NOW_ENV, ""))
    return pinned if pinned is not None else datetime.now()


def today() -> date:
    """Today, or the pinned date (`LEGAL_TODAY`, else the date part of `LEGAL_NOW`)."""
    override = _parse(os.environ.get(TODAY_ENV, ""))
    return override.date() if override is not None else now().date()

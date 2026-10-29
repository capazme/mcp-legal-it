# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, You can obtain one at
# https://mozilla.org/MPL/2.0/.
#
# Imported from VisuaLex (MPL-2.0), services/visualex/visualex_api/services/act_dates.py at eca698dc.
# Adapted: only the reading of a page's title (``_MESI``, ``_TITLES``, ``_TITLE_TAG``,
# ``_TITLE_DATE``, ``date_from_title``), unchanged. The network half (``_resolve_one``,
# ``resolve_many``, ``complete_year``) is this package's ``scraper.with_full_date``, which
# reads the page it already fetches; the found dates are kept on disk a year here too
# (``leggi`` / ``scrivi``), in ``${MCP_CACHE_DIR}/act_dates.json``.

"""The full date of an act cited by year only, read from its Normattiva page's title.

Normattiva's resolver answers a year-only URN with the act's page, whose title carries
the type, the date and the number ("LEGGE 4 maggio 1983, n. 184 - Normattiva"). The
resolver does not check what it is asked (a regional law's URN comes back as the page of
the State's act with the same year and number), so a date is taken from the title only
when its type, year and number are all the act's: never another act's day.
"""

from __future__ import annotations

import html
import json
import os
import re
import sys
import threading
import time
from datetime import date
from pathlib import Path
from typing import Optional

from .._cache import cache_enabled, cache_root

_MESI = {
    "gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4, "maggio": 5, "giugno": 6,
    "luglio": 7, "agosto": 8, "settembre": 9, "ottobre": 10, "novembre": 11, "dicembre": 12,
}
# The URN's kind -> the type a Normattiva page title opens with. Any other kind is not resolved.
_TITLES = {
    "legge": "LEGGE",
    "decreto.legislativo": "DECRETO LEGISLATIVO",
    "decreto.legge": "DECRETO-LEGGE",
    "decreto.del.presidente.della.repubblica": "DECRETO DEL PRESIDENTE DELLA REPUBBLICA",
    "regio.decreto": "REGIO DECRETO",
    "regio.decreto.legge": "REGIO DECRETO-LEGGE",
    "regio.decreto.legislativo": "REGIO DECRETO LEGISLATIVO",
    "legge.costituzionale": "LEGGE COSTITUZIONALE",
    "decreto": "DECRETO",
}
# Bounded on both sides, so a hostile page costs a constant per "<title", not a rescan of the rest.
_TITLE_TAG = re.compile(r"<title[^>]{0,200}>([^<]{0,400})</title>", re.IGNORECASE)
# The type is followed by a space and the day's digit: "DECRETO" never matches
# "DECRETO LEGISLATIVO ..." and "LEGGE" never matches "LEGGE COSTITUZIONALE ...".
_TITLE_DATE = {
    kind: re.compile(
        re.escape(title_type)
        + r" ([0-9]{1,2})[º°]? ((?i:" + "|".join(_MESI) + r")) ([0-9]{4}), n\. ([0-9]{1,6})\b"
    )
    for kind, title_type in _TITLES.items()
}


def date_from_title(page: str, kind: str, year: str, number: str) -> Optional[str]:
    """The ISO date in the page's title, when it names the act of that kind, year and number."""
    pattern = _TITLE_DATE.get(kind)
    tag = _TITLE_TAG.search(page)
    if pattern is None or tag is None:
        return None
    title = " ".join(html.unescape(tag.group(1)).split())
    found = pattern.match(title)
    if found is None:
        return None
    day, month, found_year, found_number = found.groups()
    if int(found_year) != int(year) or int(found_number) != int(number):
        return None
    try:
        return date(int(found_year), _MESI[month.lower()], int(day)).isoformat()
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Found dates, kept a year (dates do not change; a miss is never kept)
# ---------------------------------------------------------------------------

TTL_SECONDI = 365 * 86400
_memoria: dict[str, dict] = {}
_caricato = False
_lock = threading.Lock()


def _path() -> Path:
    return cache_root() / "act_dates.json"


def _carica() -> None:
    global _caricato
    if _caricato:
        return
    _caricato = True
    if not cache_enabled():
        return
    try:
        dati = json.loads(_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    if isinstance(dati, dict):
        for chiave, rec in dati.items():
            # A record is kept only whole: a date, and the moment it was saved as a number
            # (a broken "salvato" would make every later read of the act fail).
            salvato = rec.get("salvato") if isinstance(rec, dict) else None
            if (isinstance(salvato, (int, float)) and not isinstance(salvato, bool)
                    and re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(rec.get("data", "")))):
                _memoria.setdefault(chiave, rec)


def chiave(kind: str, year: str, number: str) -> str:
    """The year-only URN of an act: ``urn:nir:stato:legge:1990;241``."""
    return f"urn:nir:stato:{kind}:{year};{int(number) if str(number).isdigit() else number}"


def leggi(chiave_atto: str) -> Optional[str]:
    """The full date found for *chiave_atto* within a year, or None."""
    with _lock:
        _carica()
        rec = _memoria.get(chiave_atto)
    if rec is None or time.time() - rec.get("salvato", 0) >= TTL_SECONDI:
        return None
    return rec["data"]


def scrivi(chiave_atto: str, data_atto: str) -> None:
    """Keep a found date (best effort: an unwritable directory only warns)."""
    with _lock:
        _carica()
        _memoria[chiave_atto] = {"data": data_atto, "salvato": time.time()}
        if not cache_enabled():
            return
        try:
            path = _path()
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_name(f"{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
            tmp.write_text(json.dumps(_memoria, ensure_ascii=False), encoding="utf-8")
            os.replace(tmp, path)
        except OSError as exc:
            print(f"mcp-legal-it: cache delle date degli atti non scrivibile ({exc})", file=sys.stderr)


def svuota_memoria() -> None:
    """Forget the dates kept in memory, and read the disk again next time (tests)."""
    global _caricato
    with _lock:
        _memoria.clear()
        _caricato = False

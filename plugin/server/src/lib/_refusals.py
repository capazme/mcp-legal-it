"""The refusal ledger: what the vintage policy actually blocked, as data.

`update-data.py` can rank the tables needing reconciliation by what they cost
statically (who reads them, at what declared grade), but a static ranking cannot
say what really happens in a studio: which refusals a caller actually hits,
which are negotiated away with `accetta_precisione`, and which never matter
because the caller supplies the alternative parameter every time. That is the
difference between *what could block* and *what blocked*, and it is the only
honest way to order a reconciliation backlog.

The middleware records one line per refusal and one per acceptance in a JSONL
file under the cache root (per-day, one JSON object per line, append-only):

    refuse:   {"ts": ..., "tool": ..., "tables": [...], "stati": [...],
               "dichiarata": ..., "concedibile": ...}
    accept:   {"ts": ..., "tool": ..., "accettata": ..., "dichiarata": ...}

The record is deliberately minimal: the tool, the tables that caused it, the
grade claimed and what happened. It is a counter, not a log of the studio's
work -- no case data ever reaches the file, so the ledger needs no
confidentiality regime of its own and can sit next to the cache.

Opt-in, like the cache. `LEGAL_REFUSAL_LEDGER=on` (also `1`/`yes`/`true`/
`enabled`) turns it on; the default is off, so a read-only tool that refuses
writes nothing to disk and a host opts in to telemetry it decides it wants.
Writing is best-effort exactly like the cache: an unwritable ledger must never
turn a refusal into an error, because the refusal is the answer; the ledger is
only the memory of it.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from . import _cache, _clock

#: Switch that turns the refusal ledger on; off by default.
ENABLE_ENV = "LEGAL_REFUSAL_LEDGER"
ENABLED_VALUES = frozenset({"on", "1", "yes", "true", "enabled"})

#: File name under the cache root, rotated per day by suffix.
LEDGER_NAME = "refusals.jsonl"


def ledger_enabled() -> bool:
    """True when the host asked for refusal telemetry."""
    return os.environ.get(ENABLE_ENV, "").strip().lower() in ENABLED_VALUES


def ledger_path() -> Path:
    """Where the ledger lives: `<cache root>/refusals.jsonl`."""
    return _cache.cache_root() / LEDGER_NAME


def record(entry: dict) -> None:
    """Append one entry, best-effort, when the ledger is on.

    Any failure -- ledger off, unwritable directory, disk full -- leaves the
    call's answer untouched: the return value the caller sees is never worth
    less than it would have been without the ledger.
    """
    if not ledger_enabled():
        return
    try:
        path = ledger_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        # Through `_clock`, like every calendar read in this server: the audit
        # enforces it, and a pinned `LEGAL_NOW` makes the ledger deterministic
        # in tests. The read happens after the call's precision decision was
        # taken, so it cannot change what the call was worth.
        line = json.dumps(
            {"ts": _clock.now().isoformat(timespec="seconds"), **entry},
            ensure_ascii=False,
            sort_keys=True,
        )
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


def summarize(limit: int = 50) -> dict:
    """What the ledger says, if the host asked for it.

    Reads `<cache root>/refusals.jsonl` (the same file `record` writes, wherever
    `MCP_CACHE_DIR` points it), counts refusals per tool and per table, and
    counts the acceptances that bought a number anyway. Returns
    `{"disponibile": False, "motivo": ...}` when the ledger is off or absent,
    so a reader can tell "nothing happened" from "nobody was watching".
    """
    if not ledger_enabled():
        return {
            "disponibile": False,
            "motivo": "verbale non attivo: impostare LEGAL_REFUSAL_LEDGER=on",
        }
    path = ledger_path()
    if not path.exists():
        return {"disponibile": True, "rifiuti": {}, "accettazioni": {}, "totale": 0}
    rifiuti: dict[str, int] = {}
    accettazioni: dict[str, int] = {}
    tabelle: dict[str, int] = {}
    totale = 0
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    voce = json.loads(line)
                except ValueError:
                    continue  # a truncated line is skipped, not fatal
                totale += 1
                tool = voce.get("tool") or "?"
                if voce.get("evento") == "accettazione":
                    accettazioni[tool] = accettazioni.get(tool, 0) + 1
                    continue
                rifiuti[tool] = rifiuti.get(tool, 0) + 1
                for tabella in voce.get("tables") or []:
                    tabelle[tabella] = tabelle.get(tabella, 0) + 1
    except OSError:
        return {"disponibile": False, "motivo": "verbale illeggibile"}
    top_rifiuti = dict(sorted(rifiuti.items(), key=lambda kv: -kv[1])[:limit])
    top_tabelle = dict(sorted(tabelle.items(), key=lambda kv: -kv[1])[:limit])
    return {
        "disponibile": True,
        "totale": totale,
        "rifiuti": top_rifiuti,
        "tabelle": top_tabelle,
        "accettazioni": accettazioni,
    }

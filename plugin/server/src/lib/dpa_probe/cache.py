"""On-disk cache of DPA determinations, bounded by a TTL.

Only determinations are persisted. Transient failures are never written: a
timeout today must not become a truth for 90 days.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

from src.lib.dpa_probe.client import EsitoSonda, normalizza_dominio
from src.lib.dpa_probe.judge import (
    VERDETTO_CLAUSOLA,
    VERDETTO_DEDICATO,
    VERDETTO_NON_TROVATO,
)

TTL_GIORNI = 90
VERDETTI_PERSISTIBILI = frozenset({VERDETTO_DEDICATO, VERDETTO_CLAUSOLA, VERDETTO_NON_TROVATO})

_NOME_FILE = "dpa_probe.json"


def percorso_cache() -> Path:
    base = Path(os.environ.get("MCP_CACHE_DIR", Path.home() / ".cache" / "mcp-legal-it"))
    return base / _NOME_FILE


def _carica() -> dict:
    percorso = percorso_cache()
    if not percorso.exists():
        return {}
    try:
        dati = json.loads(percorso.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {}
    return dati if isinstance(dati, dict) else {}


def leggi(dominio: str, adesso: datetime) -> dict | None:
    """Return the cached determination, or None on miss / expiry / corruption."""
    voce = _carica().get(normalizza_dominio(dominio))
    if not isinstance(voce, dict):
        return None
    try:
        verificato = datetime.fromisoformat(voce["verificato_il"])
    except (KeyError, TypeError, ValueError):
        return None
    if (adesso - verificato).days > TTL_GIORNI:
        return None
    return voce


def scrivi(dominio: str, esito: EsitoSonda, adesso: datetime) -> None:
    """Persist a determination. No-op for transient failures.

    A cache that cannot be written must degrade to "no cache", never to a
    failed analysis: any OSError (unwritable MCP_CACHE_DIR, read-only home,
    full disk, a permissions change) is swallowed here, symmetric with the
    OSError handling already in `_carica()` on the read side.
    """
    if esito.verdetto not in VERDETTI_PERSISTIBILI:
        return
    percorso = percorso_cache()
    dati = _carica()
    dati[normalizza_dominio(dominio)] = {
        "verdetto": esito.verdetto,
        "url_evidenza": esito.url_evidenza,
        "marcatori": esito.marcatori,
        "evidenza": esito.evidenza,
        "verificato_il": adesso.date().isoformat(),
    }
    try:
        percorso.parent.mkdir(parents=True, exist_ok=True)
        percorso.write_text(json.dumps(dati, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError as exc:
        print(f"[dpa_probe] cache write failed: {exc}", file=sys.stderr)

"""The EUR-Lex page of an act, kept for a day: one fetch serves every article of the act.

VisuaLex keeps every EUR-Lex page it fetched for 24 hours (its persistent ``eurlex``
namespace, ``PERSISTENT_CACHE_TTL``), because one page carries the whole act and the
WAF is crossed once. mcp-legal-it reads the same page from CELLAR (no WAF, the same
bytes for VisuaLex's extractor: Q1 in docs/migration/visualex-inventory.md), and keeps
it the same way, keyed by the CELLAR URL asked:

- in memory, an LRU of ``MAX_IN_MEMORIA`` pages (an act's page is 60 KB to 1.7 MB);
- on disk, ``${MCP_CACHE_DIR:-~/.cache/mcp-legal-it}/eurlex_pagine/<sha256 of the URL>.json.gz``,
  read back for ``TTL_SECONDI`` (24 h) after the fetch; an expired or unreadable record
  is deleted when met, and past ``MAX_SU_DISCO`` files the oldest go;
- ``LEGAL_CACHE=off`` (``lib/_cache.py``): nothing is read from or written to disk.

A page is kept only when it was read: a failed fetch or a WAF challenge is never kept.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import sys
import threading
import time
from collections import OrderedDict
from pathlib import Path

from .._cache import cache_enabled, cache_root

#: How long a page is reused: VisuaLex's PERSISTENT_CACHE_TTL.
TTL_SECONDI = 86400
MAX_IN_MEMORIA = 8
MAX_SU_DISCO = 100
#: Raised when the record's shape changes, so records written before are not read.
SCHEMA = 1

_memoria: "OrderedDict[str, dict]" = OrderedDict()
_lock = threading.Lock()


def _dir() -> Path:
    return cache_root() / "eurlex_pagine"


def _path(url: str) -> Path:
    return _dir() / f"{hashlib.sha256(url.encode('utf-8')).hexdigest()}.json.gz"


def leggi(url: str) -> "tuple[str, str] | None":
    """``(page, the URL CELLAR served it from)`` for *url* if younger than a day, else None.

    The served URL is the redirect's end (``…/resource/cellar/<id>/DOC_1``): the provenance
    an answer reports is the same whether the page was fetched or kept.
    """
    adesso = time.time()
    with _lock:
        rec = _memoria.get(url)
        if rec is not None:
            if adesso - rec["salvato"] < TTL_SECONDI:
                _memoria.move_to_end(url)
                return rec["html"], rec["servito"]
            del _memoria[url]
    if not cache_enabled():
        return None
    path = _path(url)
    try:
        rec = json.loads(gzip.decompress(path.read_bytes()).decode("utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError, EOFError):
        rec = None
    # A record that is not one is dropped like a stale one: it would otherwise fail on
    # every read of that URL, for ever.
    if (not isinstance(rec, dict) or rec.get("schema") != SCHEMA or rec.get("url") != url
            or not isinstance(rec.get("html"), str) or not isinstance(rec.get("servito"), str)
            or not isinstance(rec.get("salvato"), (int, float))
            or adesso - rec["salvato"] >= TTL_SECONDI):
        try:
            path.unlink()
        except OSError:
            pass
        return None
    _ricorda(url, rec)
    return rec["html"], rec["servito"]


def scrivi(url: str, html: str, servito: str = "") -> None:
    """Keep the page fetched from *url*, served from *servito* (best effort: an unwritable
    directory only warns)."""
    rec = {"schema": SCHEMA, "url": url, "salvato": time.time(), "html": html, "servito": servito or url}
    _ricorda(url, rec)
    if not cache_enabled():
        return
    try:
        cartella = _dir()
        cartella.mkdir(parents=True, exist_ok=True)
        path = _path(url)
        tmp = path.with_name(f"{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
        tmp.write_bytes(gzip.compress(json.dumps(rec, ensure_ascii=False).encode("utf-8")))
        os.replace(tmp, path)
        _sfoltisci(cartella)
    except OSError as exc:
        print(f"mcp-legal-it: cache delle pagine EUR-Lex non scrivibile ({exc})", file=sys.stderr)


def _ricorda(url: str, rec: dict) -> None:
    with _lock:
        _memoria[url] = rec
        _memoria.move_to_end(url)
        while len(_memoria) > MAX_IN_MEMORIA:
            _memoria.popitem(last=False)


def _sfoltisci(cartella: Path) -> None:
    adesso = time.time()
    for tmp in cartella.glob("*.tmp"):  # left by a crash between write and rename
        try:
            if adesso - tmp.stat().st_mtime > 3600:
                tmp.unlink()
        except OSError:
            pass
    files = list(cartella.glob("*.json.gz"))
    if len(files) <= MAX_SU_DISCO:
        return
    files.sort(key=lambda p: p.stat().st_mtime)
    for p in files[: len(files) - MAX_SU_DISCO]:
        try:
            p.unlink()
        except OSError:
            pass


def svuota_memoria() -> None:
    """Forget the in-memory pages (tests)."""
    with _lock:
        _memoria.clear()

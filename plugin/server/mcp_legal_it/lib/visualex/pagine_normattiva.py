"""What a Normattiva article page said, kept for a day: the HTML channel's cache.

VisuaLex keeps every Normattiva page it fetched for 24 hours (its persistent
``normattiva`` namespace, ``PERSISTENT_CACHE_TTL``), so an article asked again the
same day costs no request. This is that cache for the HTML channel, with one
difference: it keeps what the page said, not the page. A code's article page is
about 2.6 MB of HTML; the record is the extracted ``article_text`` (VisuaLex's
extractor, ``normattiva_html``) and the article number the page gives it, a few KB.

- in memory, an LRU of ``MAX_IN_MEMORIA`` records, each with the validity the page
  states for its text (``validita``: window, version, repeal), read from the same page;
- on disk, ``${MCP_CACHE_DIR:-~/.cache/mcp-legal-it}/normattiva_pagine/<sha256 of the URL>.json``,
  read back for ``TTL_SECONDI`` (24 h) after the fetch; an expired record is deleted
  when met, and past ``MAX_SU_DISCO`` files the oldest go;
- ``LEGAL_CACHE=off`` (``lib/_cache.py``): nothing is read from or written to disk.

A record is written only when the page was read: a failed fetch, a page with no
article body, are never kept.

The act's article tree (``albero_normattiva``, read from the act's own page) is kept
here too, under its own key (``albero|`` + the act's URL), for the same day: VisuaLex
keeps its trees 24 hours as well. A failed or empty tree is never kept.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import threading
import time
from collections import OrderedDict
from pathlib import Path

from .._cache import cache_enabled, cache_root

#: How long a page's reading is reused: VisuaLex's PERSISTENT_CACHE_TTL.
TTL_SECONDI = 86400
MAX_IN_MEMORIA = 256
MAX_SU_DISCO = 2000
#: Raised when the record's shape changes, so records written before are not read.
#: 2: the record keeps what the page says of its own validity (``validita``).
SCHEMA = 2

_memoria: "OrderedDict[str, dict]" = OrderedDict()
#: The disk is pruned once every this many writes, not at each one (a glob of up to 2000 files).
OGNI_QUANTE_SCRITTURE = 50
_scritture = 0


def _dir() -> Path:
    return cache_root() / "normattiva_pagine"


def _chiave(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def leggi(url: str) -> dict | None:
    """The record of *url* if it is younger than a day, else None."""
    adesso = time.time()
    rec = _memoria.get(url)
    if rec is not None:
        if adesso - rec["salvato"] < TTL_SECONDI:
            _memoria.move_to_end(url)
            return rec
        del _memoria[url]
    if not cache_enabled():
        return None
    path = _dir() / f"{_chiave(url)}.json"
    try:
        rec = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    # A record that is not one ("[]", a dict without its text) is dropped like a stale
    # one: it would otherwise fail on every read of that URL, for ever.
    pagina = isinstance(rec, dict) and isinstance(rec.get("testo"), str) and "servito" in rec
    tree = rec.get("albero") if isinstance(rec, dict) else None
    albero = (url.startswith("albero|") and isinstance(tree, dict) and isinstance(tree.get("result"), list)
              and isinstance(tree.get("count"), int) and isinstance(tree.get("metadata"), dict))
    if (not (pagina or albero)
            or rec.get("schema") != SCHEMA or rec.get("url") != url
            or not isinstance(rec.get("salvato", 0), (int, float)) or adesso - rec.get("salvato", 0) >= TTL_SECONDI):
        try:
            path.unlink()
        except OSError:
            pass
        return None
    _ricorda(url, rec)
    return rec


def scrivi(url: str, testo: str, servito: str | None, validita: dict | None = None) -> None:
    """Keep what the page at *url* said (best effort: an unwritable directory only warns).

    *validita* is what the page states of the text's validity (``normattiva_validity``),
    read from the same page: the window, the version, the repeal.
    """
    _scrivi({"schema": SCHEMA, "url": url, "salvato": time.time(), "testo": testo, "servito": servito,
             "validita": validita})


def _chiave_albero(url: str) -> str:
    return f"albero|{url}"


def leggi_albero(url: str) -> dict | None:
    """The tree of the act at *url* (``{"result", "count", "metadata"}``) if younger than a day."""
    rec = leggi(_chiave_albero(url))
    return rec.get("albero") if rec is not None else None


def scrivi_albero(url: str, albero: dict) -> None:
    """Keep the act's widest tree (links, section labels, metadata)."""
    _scrivi({"schema": SCHEMA, "url": _chiave_albero(url), "salvato": time.time(), "albero": albero})


def _scrivi(rec: dict) -> None:
    url = rec["url"]
    _ricorda(url, rec)
    if not cache_enabled():
        return
    try:
        cartella = _dir()
        cartella.mkdir(parents=True, exist_ok=True)
        path = cartella / f"{_chiave(url)}.json"
        tmp = path.with_name(f"{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
        tmp.write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, path)
        global _scritture
        _scritture += 1
        if _scritture % OGNI_QUANTE_SCRITTURE == 0:
            _sfoltisci(cartella)
    except OSError as exc:
        print(f"mcp-legal-it: cache delle pagine Normattiva non scrivibile ({exc})", file=sys.stderr)


def _ricorda(url: str, rec: dict) -> None:
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
    files = list(cartella.glob("*.json"))
    if len(files) <= MAX_SU_DISCO:
        return
    files.sort(key=lambda p: p.stat().st_mtime)
    for p in files[: len(files) - MAX_SU_DISCO]:
        try:
            p.unlink()
        except OSError:
            pass


def svuota_memoria() -> None:
    """Forget the in-memory records (tests)."""
    _memoria.clear()

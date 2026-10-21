"""The on-disk caches, where they live, and the switch that turns them off.

Three clients persist state under `${MCP_CACHE_DIR:-~/.cache/mcp-legal-it}`:

    akn_acts/{codice}_{data_gu}_{data_vigenza}.json   parsed acts (cite_law,
    akn_acts/akn_hits.json                            fetch_full_act, ...)
    akn_acts/akn_url_params.json                      URL -> export params index
    normattiva_pagine/<sha256 of the URL>.json        an article page's text, 24 h
    brocardi_urls.json                                article URL map
    corte_cost/{kind}/{year}.json                     Consulta massime, 7-day TTL

Everything else the server keeps between calls is in memory only (the LRU in
`visualex.akn_fetch`, the URL dictionaries, `lru_cache` over the bundled JSON
tables). These are the only files this server ever creates, and
`scripts/audit_tool_annotations.py` fails when a new write site appears that is
not declared as one of them.

The writes are best-effort -- an unwritable cache directory is reported on
stderr and the tool still answers -- but they are still writes, on a machine
whose owner may not expect a legal lookup to leave anything behind.

`LEGAL_CACHE=off` (also `no`/`false`/`0`/`none`/`disabled`) is the switch for
that: nothing is read from or written to the cache directory, the caches stay in
memory for the life of the process, and the directory is never created.
`MCP_CACHE_DIR` only relocates the files; it does not stop them.

This module is the single place that reads either variable, so the audit can
find the switch by looking at one function. A library caller can set both in
code (``mcp_legal_it.api.configurazione(cache_dir=..., cache=False)``); the
variable ``LEGAL_CACHE=off`` still wins over ``cache=True``.
"""

from __future__ import annotations

import os
from pathlib import Path

from mcp_legal_it.core import _config

#: Directory holding every cache file, if the caller does not relocate it.
DIR_ENV = "MCP_CACHE_DIR"
#: Switch that disables on-disk caching entirely.
DISABLE_ENV = "LEGAL_CACHE"
DISABLED_VALUES = frozenset({"off", "no", "false", "0", "none", "disabled"})
DEFAULT_DIR = Path.home() / ".cache" / "mcp-legal-it"


def cache_enabled() -> bool:
    """False when `LEGAL_CACHE` (or the library configuration) asks for no on-disk caching."""
    if os.environ.get(DISABLE_ENV, "").strip().lower() in DISABLED_VALUES:
        return False
    return _config.attuale().cache is not False


def cache_root() -> Path:
    """Base cache directory; each client appends its own subdirectory."""
    configured = _config.attuale().cache_dir
    if configured:
        return Path(configured)
    return Path(os.environ.get(DIR_ENV) or DEFAULT_DIR)


def cache_root_display() -> str:
    """`str(cache_root())` for state reports: describes the directory, opens nothing."""
    return str(cache_root())

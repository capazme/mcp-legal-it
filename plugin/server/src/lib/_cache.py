"""The on-disk caches, where they live, and the switch that turns them off.

Three clients persist state under `${MCP_CACHE_DIR:-~/.cache/mcp-legal-it}`:

    akn_acts/{codice}_{data_gu}_{data_vigenza}.json   parsed acts (cite_law,
    akn_acts/akn_hits.json                            fetch_full_act, ...)
    akn_acts/akn_url_params.json                      URL -> export params index
    brocardi_urls.json                                article URL map
    corte_cost/{kind}/{year}.json                     Consulta massime, 7-day TTL

Everything else the server keeps between calls is in memory only (the LRU in
`visualex.akn_fetch`, the URL dictionaries, `lru_cache` over the bundled JSON
tables). These four are the only files this server ever creates, and
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
find the switch by looking at one function.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

#: Directory holding every cache file, if the caller does not relocate it.
DIR_ENV = "MCP_CACHE_DIR"
#: Switch that disables on-disk caching entirely.
DISABLE_ENV = "LEGAL_CACHE"
DISABLED_VALUES = frozenset({"off", "no", "false", "0", "none", "disabled"})
DEFAULT_DIR = Path.home() / ".cache" / "mcp-legal-it"


def cache_enabled() -> bool:
    """False when `LEGAL_CACHE` asks for no on-disk caching."""
    return os.environ.get(DISABLE_ENV, "").strip().lower() not in DISABLED_VALUES


_warned_relative = False


def cache_root() -> Path:
    """Base cache directory; each client appends its own subdirectory.

    A relative `MCP_CACHE_DIR` would be read against the server's working directory,
    which the launchers set to the extension's or plugin's own folder: it is ignored,
    with one line on stderr, and the default is used. `~` is expanded; a `~user` that
    cannot be expanded counts as relative.
    """
    global _warned_relative
    value = os.environ.get(DIR_ENV)
    if not value:
        return DEFAULT_DIR
    try:
        path = Path(value).expanduser()
    except RuntimeError:  # "~user" for a user that does not exist
        path = Path(value)
    if path.is_absolute():
        return path
    if not _warned_relative:
        _warned_relative = True
        print(f"mcp-legal-it: {DIR_ENV}={value!r} is not an absolute path; "
              f"the cache stays in {DEFAULT_DIR}", file=sys.stderr)
    return DEFAULT_DIR


def cache_root_display() -> str:
    """`str(cache_root())` for state reports: describes the directory, opens nothing."""
    return str(cache_root())

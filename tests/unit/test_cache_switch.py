"""`LEGAL_CACHE=off`: the caches stay in memory, the disk is never touched.

The annotation policy promises that the 12 cache writers touch nothing but
`${MCP_CACHE_DIR:-~/.cache/mcp-legal-it}`. This is the other half of that
promise: the cache itself is optional, and with `LEGAL_CACHE=off` the directory
is not read and not even created.

The audit half -- that no module starts writing a cache without declaring it,
and that no cache writer forgets the switch -- lives in
`test_tool_annotations.py` (see `test_the_cache_audit_is_clean`).
"""

import pathlib
import sys

import pytest

from src.lib._cache import cache_enabled
from src.lib.brocardi import client as brocardi
from src.lib.corte_cost import client as corte_cost
from src.lib.visualex import akn_fetch

REPO = pathlib.Path(__file__).resolve().parents[2]

KEY = ("C1", "20240101", "20240101")


@pytest.fixture()
def cache_dir(tmp_path, monkeypatch):
    """A private cache directory, with the switch off by default."""
    target = tmp_path / "cache"
    monkeypatch.setenv("MCP_CACHE_DIR", str(target))
    monkeypatch.setenv("LEGAL_CACHE", "off")
    # The parsed-act caches keep in-memory state across calls; start clean.
    akn_fetch._lru.clear()
    akn_fetch._url_params.clear()
    akn_fetch._url_params_loaded = False
    return target


def _write_every_cache() -> None:
    brocardi._save_url_cache({"article": "https://www.brocardi.it/example"})
    corte_cost._write_cache(corte_cost._cache_path("massime", 2024), [{"x": 1}])
    akn_fetch._set_url_params("https://www.normattiva.it/x", "C1", "20240101")
    akn_fetch._bump_hits(KEY)
    akn_fetch._disk_store(
        KEY,
        akn_fetch.ParsedAct(title="t", articles={}, order=[], structure="flat"),
    )


def test_disabled_caches_never_create_the_directory(cache_dir):
    _write_every_cache()

    assert sorted(path.name for path in cache_dir.parent.iterdir()) == []


def test_disabled_caches_do_not_answer_from_disk(cache_dir, monkeypatch):
    """With the switch off, a cache file left behind is not read either."""
    cache_dir.mkdir(parents=True)
    (cache_dir / "brocardi_urls.json").write_text('{"a": "b"}', encoding="utf-8")

    assert brocardi._load_url_cache() == {}
    assert corte_cost._cache_fresh(cache_dir / "missing.json") is False
    assert akn_fetch._disk_load(KEY) is None


def test_enabled_caches_still_write(cache_dir, monkeypatch):
    """Positive control: without the switch the same calls do hit the disk."""
    monkeypatch.delenv("LEGAL_CACHE", raising=False)

    _write_every_cache()

    assert (cache_dir / "brocardi_urls.json").exists()
    assert (cache_dir / "corte_cost" / "massime" / "2024.json").exists()
    assert (cache_dir / "akn_acts" / "akn_hits.json").exists()
    assert akn_fetch._disk_path(KEY).exists()


@pytest.mark.parametrize("value", ["off", "OFF", " no ", "false", "0", "none", "disabled"])
def test_switch_values_that_disable(value, monkeypatch):
    monkeypatch.setenv("LEGAL_CACHE", value)
    assert cache_enabled() is False


@pytest.mark.parametrize("value", ["on", "1", "true", "yes", ""])
def test_switch_values_that_keep_caching(value, monkeypatch):
    monkeypatch.setenv("LEGAL_CACHE", value)
    assert cache_enabled() is True


def test_unset_switch_keeps_caching(monkeypatch):
    monkeypatch.delenv("LEGAL_CACHE", raising=False)
    assert cache_enabled() is True


def test_only_the_shared_module_reads_the_cache_directory():
    """One module resolves the cache, so `LEGAL_CACHE=off` cannot be bypassed."""
    src = REPO / "plugin/server/src"
    readers = []
    for py in sorted(src.rglob("*.py")):
        if "__pycache__" in str(py):
            continue
        relative = py.relative_to(src).as_posix()
        if relative == "lib/_cache.py":
            continue
        for line in py.read_text(encoding="utf-8").splitlines():
            if "MCP_CACHE_DIR" in line and "environ" in line:
                readers.append("%s: %s" % (relative, line.strip()))
    assert readers == []


def test_cache_writers_are_declared_in_the_audit():
    """The tools that write a cache must be exactly the ones the audit derives."""
    sys.path.insert(0, str(REPO / "scripts"))
    try:
        from audit_tool_annotations import Audit, verify_caches  # type: ignore[import-not-found]

        audit = Audit(pathlib.Path(REPO / "plugin/server/src"))
        problems = verify_caches(audit)
    finally:
        sys.path.pop(0)

    assert problems == []
    cache_tools = {tool for fq, tool in audit.tools.items() if audit.is_cache_only(fq)}
    from src.tool_annotations import CACHE_WRITES

    assert cache_tools == set(CACHE_WRITES)

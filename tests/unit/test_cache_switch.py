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

from mcp_legal_it.lib._cache import cache_enabled
from mcp_legal_it.lib.brocardi import client as brocardi
from mcp_legal_it.lib.corte_cost import client as corte_cost
from mcp_legal_it.lib.visualex import akn_fetch

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
    src = REPO / "plugin/server/mcp_legal_it"
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

        audit = Audit(pathlib.Path(REPO / "plugin/server/mcp_legal_it"))
        problems = verify_caches(audit)
    finally:
        sys.path.pop(0)

    assert problems == []
    cache_tools = {tool for fq, tool in audit.tools.items() if audit.is_cache_only(fq)}
    from mcp_legal_it.tool_annotations import CACHE_WRITES

    assert cache_tools == set(CACHE_WRITES)


class TestCacheDirMustBeAbsolute:
    """The launchers start the server from its own folder: a relative MCP_CACHE_DIR would
    land there, not where the user meant. It is ignored, said once on stderr."""

    def test_an_absolute_dir_is_used(self, tmp_path, monkeypatch):
        from mcp_legal_it.lib import _cache

        monkeypatch.setenv("MCP_CACHE_DIR", str(tmp_path))
        assert _cache.cache_root() == tmp_path

    def test_a_home_dir_is_expanded(self, monkeypatch):
        from mcp_legal_it.lib import _cache

        monkeypatch.setenv("MCP_CACHE_DIR", "~/legal-it-cache")
        assert _cache.cache_root() == pathlib.Path.home() / "legal-it-cache"

    def test_a_relative_dir_is_ignored_and_said_once(self, monkeypatch, capsys):
        from mcp_legal_it.lib import _cache

        monkeypatch.setattr(_cache, "_RELATIVI_SEGNALATI", set())
        monkeypatch.setenv("MCP_CACHE_DIR", "cache-relativa")
        assert _cache.cache_root() == _cache.DEFAULT_DIR
        assert _cache.cache_root() == _cache.DEFAULT_DIR
        err = capsys.readouterr().err
        assert err.count("MCP_CACHE_DIR deve essere un percorso assoluto") == 1
        assert str(_cache.DEFAULT_DIR) in err

    def test_an_unknown_users_home_falls_back_to_the_default(self, monkeypatch, capsys):
        from mcp_legal_it.lib import _cache

        monkeypatch.setattr(_cache, "_RELATIVI_SEGNALATI", set())
        monkeypatch.setenv("MCP_CACHE_DIR", "~utente-che-non-esiste-7f3a/cache")
        assert _cache.cache_root() == _cache.DEFAULT_DIR  # never a RuntimeError at start
        assert "MCP_CACHE_DIR deve essere un percorso assoluto" in capsys.readouterr().err

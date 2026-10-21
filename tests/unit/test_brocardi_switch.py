"""LEGAL_BROCARDI=off: no Brocardi tool listed, no request to brocardi.it, mixed tools say so.

Brocardi.it is the server's only private source. A deployment that must not use it
switches it off; these tests hold the three promises of lib/_brocardi_switch.py:

* the `solo_brocardi` tools are not listed (stock server, crea_server);
* nothing reaches brocardi.it: the network is mocked and every request recorded,
  and any request to a Brocardi host fails the test, whichever tool sent it;
* every tool that can return Brocardi content is tagged `brocardi`, checked
  statically on the call graph of the tool modules, so a new tool that reaches the
  scrapers without the tag fails here.
"""
from __future__ import annotations

import ast
import asyncio
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import httpx
import pytest
from fastmcp import Client

from mcp_legal_it.lib import _brocardi_switch as switch
from mcp_legal_it.lib import _egress

REPO = Path(__file__).resolve().parents[2]
PKG = REPO / "plugin" / "server" / "mcp_legal_it"

#: One realistic call per Brocardi-tagged tool. A tool tagged `brocardi` without an
#: entry here fails `test_every_brocardi_tool_is_exercised`.
CALLS = {
    "cite_law": {"reference": "art. 2043 c.c.", "include_annotations": True},
    "cerca_brocardi": {"reference": "art. 2043 c.c."},
    "fetch_law_annotations": {"act_type": "codice civile", "article": "2043"},
    "giurisprudenza_articolo": {"riferimento": "art. 2043 c.c."},
    "mappa_orientamento": {"riferimento": "art. 2043 c.c."},
}

#: Where the Brocardi scrapers start: a tool reaching one of these returns Brocardi content.
SINKS = {"fetch_brocardi", "fetch_annotations", "find_article_url", "_find_brocardi_article_url"}


class Network:
    """Stands in for the internet: records every request, answers none."""

    def __init__(self) -> None:
        self.urls: list[str] = []

    @property
    def brocardi(self) -> list[str]:
        return [u for u in self.urls if switch.is_brocardi_url(u)]

    def install(self, monkeypatch) -> "Network":
        network = self

        async def send(client, request, *args, **kwargs):
            network.urls.append(str(request.url))
            raise httpx.ConnectError("network disabled in tests", request=request)

        def send_sync(client, request, *args, **kwargs):
            network.urls.append(str(request.url))
            raise httpx.ConnectError("network disabled in tests", request=request)

        async def no_sleep(*args, **kwargs):
            return None

        monkeypatch.setattr(httpx.AsyncClient, "send", send)
        monkeypatch.setattr(httpx.Client, "send", send_sync)
        monkeypatch.setattr("mcp_legal_it.lib._http.asyncio.sleep", no_sleep)
        monkeypatch.setattr("mcp_legal_it.lib.visualex.scraper.asyncio.sleep", no_sleep)
        return self


@pytest.fixture
def network(monkeypatch):
    monkeypatch.setenv("LEGAL_CACHE", "off")
    # The Brocardi URL caches would answer a known article without a request:
    # empty them so that the "switch on" control really reaches the network.
    monkeypatch.setattr("mcp_legal_it.lib.brocardi.client._url_cache", {})
    monkeypatch.setattr("mcp_legal_it.lib.visualex.scraper._brocardi_url_cache", {})
    return Network().install(monkeypatch)


def _text(result) -> str:
    return "\n".join(getattr(c, "text", "") for c in result.content)


async def _call_all(server, names=CALLS) -> dict[str, str]:
    out = {}
    async with Client(server) as client:
        for name in names:
            result = await client.call_tool(name, CALLS[name], raise_on_error=False)
            out[name] = _text(result)
    return out


# --- the switch itself ---------------------------------------------------------

@pytest.mark.parametrize("value,off", [
    ("off", True), ("OFF", True), (" 0 ", True), ("false", True), ("no", True),
    ("on", False), ("1", False), ("", False), (None, False),
])
def test_environment_values(value, off, monkeypatch):
    if value is None:
        monkeypatch.delenv(switch.ENV_SWITCH, raising=False)
    else:
        monkeypatch.setenv(switch.ENV_SWITCH, value)
    assert switch.off_by_environment() is off
    assert switch.enabled() is (not off)


def test_default_is_on(monkeypatch):
    monkeypatch.delenv(switch.ENV_SWITCH, raising=False)
    assert switch.enabled()


def test_the_context_manager_and_the_process_default(monkeypatch):
    monkeypatch.delenv(switch.ENV_SWITCH, raising=False)
    with switch.disabled():
        assert not switch.enabled()
    assert switch.enabled()
    try:
        switch.set_default(False)
        assert not switch.enabled()
    finally:
        switch.set_default(None)
    assert switch.enabled()


def test_code_cannot_switch_back_on_what_the_environment_switched_off(monkeypatch):
    monkeypatch.setenv(switch.ENV_SWITCH, "off")
    with pytest.raises(ValueError):
        switch.set_default(True)
    token = switch.set_for_context(True)
    try:
        assert not switch.enabled()
    finally:
        switch.reset(token)


def test_the_egress_list_refuses_brocardi_when_off(monkeypatch):
    monkeypatch.delenv(switch.ENV_SWITCH, raising=False)
    assert _egress.is_allowed("https://www.brocardi.it/codice-civile/")
    monkeypatch.setenv(switch.ENV_SWITCH, "off")
    assert not _egress.is_allowed("https://www.brocardi.it/codice-civile/")
    assert _egress.is_allowed("https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:legge")


# --- no request reaches brocardi.it -------------------------------------------

def test_the_scrapers_send_nothing_when_off(network, monkeypatch):
    from mcp_legal_it.lib.brocardi.client import fetch_brocardi, find_article_url
    from mcp_legal_it.lib.visualex.models import Norma, NormaVisitata
    from mcp_legal_it.lib.visualex.scraper import _find_brocardi_article_url, fetch_annotations

    monkeypatch.setenv(switch.ENV_SWITCH, "off")
    result = asyncio.run(fetch_brocardi("codice civile", "2043"))
    assert result.error == switch.DISABLED_NOTE
    annotations = asyncio.run(fetch_annotations(NormaVisitata(norma=Norma(tipo_atto="codice civile"), numero_articolo="2043")))
    assert annotations["error"] == switch.DISABLED_NOTE

    async def low_level():
        async with httpx.AsyncClient() as client:
            for finder in (find_article_url, _find_brocardi_article_url):
                with pytest.raises(switch.BrocardiDisabled):
                    await finder(client, "https://www.brocardi.it/codice-civile/", "2043")

    asyncio.run(low_level())
    assert network.urls == []


def test_the_control_without_the_switch_does_reach_brocardi(network, monkeypatch):
    # Proves the mock sees Brocardi traffic: with the switch on, cerca_brocardi tries.
    from mcp_legal_it.server import mcp

    monkeypatch.delenv(switch.ENV_SWITCH, raising=False)
    asyncio.run(_call_all(mcp, ["cerca_brocardi"]))
    assert network.brocardi


def test_no_brocardi_tool_reaches_brocardi_when_off(network, monkeypatch):
    from mcp_legal_it.server import mcp

    monkeypatch.setenv(switch.ENV_SWITCH, "off")
    answers = asyncio.run(_call_all(mcp))
    assert network.brocardi == [], network.brocardi
    # The mixed tools whose core needs the (mocked, down) network answer with the
    # core's error; the note is checked on a reachable core below.
    for name in ("cite_law", "cerca_brocardi", "fetch_law_annotations"):
        assert "Brocardi disattivato" in answers[name], (name, answers[name][:400])


async def _italgiure_up(*args, **kwargs):
    from mcp_legal_it.lib._result import SearchResult

    return SearchResult(success=True, source="italgiure", num_found=1, results_text="risultati Italgiure")


def test_giurisprudenza_articolo_says_brocardi_is_off(network, monkeypatch):
    from mcp_legal_it.tools import italgiure

    monkeypatch.setattr(italgiure, "_giurisprudenza_su_norma_impl", _italgiure_up)
    monkeypatch.setenv(switch.ENV_SWITCH, "off")
    result = asyncio.run(italgiure._giurisprudenza_articolo_impl("art. 2043 c.c."))
    assert switch.DISABLED_NOTE in result.results_text
    assert "risultati Italgiure" in result.results_text
    assert network.urls == []


def test_mappa_orientamento_says_brocardi_is_off(network, monkeypatch):
    from mcp_legal_it.tools import orientamento

    monkeypatch.setattr(orientamento, "_orientamento_su_norma_impl", _italgiure_up)
    monkeypatch.setenv(switch.ENV_SWITCH, "off")
    result = asyncio.run(orientamento._mappa_orientamento_impl("art. 2043 c.c."))
    assert switch.DISABLED_NOTE in result.results_text
    assert "risultati Italgiure" in result.results_text
    assert network.urls == []


def test_crea_server_switches_brocardi_off_for_its_calls_only(network, monkeypatch):
    from mcp_legal_it.server import crea_server, mcp

    monkeypatch.delenv(switch.ENV_SWITCH, raising=False)
    server = crea_server(brocardi=False)

    async def listed(s):
        async with Client(s) as client:
            return {t.name for t in await client.list_tools()}

    names = asyncio.run(listed(server))
    assert not names & {"cerca_brocardi", "fetch_law_annotations"}
    assert {"cite_law", "giurisprudenza_articolo", "mappa_orientamento"} <= names
    answers = asyncio.run(_call_all(server, ["cite_law", "giurisprudenza_articolo", "mappa_orientamento"]))
    assert network.brocardi == []
    assert "Brocardi disattivato" in answers["cite_law"], answers["cite_law"]
    # The stock server, in the same process, still has Brocardi.
    assert switch.enabled()
    assert {"cerca_brocardi", "fetch_law_annotations"} <= asyncio.run(listed(mcp))


def test_every_brocardi_tool_is_exercised():
    from mcp_legal_it.server import mcp

    tagged = {t.name for t in asyncio.run(mcp.list_tools()) if switch.TAG in t.tags}
    assert tagged == set(CALLS)


# --- the tag follows the code --------------------------------------------------

def _tool_reach() -> dict[str, tuple[bool, set[str]]]:
    """For every tool: whether its code path reaches a Brocardi scraper, and its tags.

    A call graph over mcp_legal_it/tools/*.py: module-level functions, the names
    they reference, and `from mcp_legal_it.tools.X import f` imports (also inside
    functions) resolved to the function they name.
    """
    functions: dict[tuple[str, str], ast.AST] = {}
    imports: dict[str, dict[str, tuple[str, str]]] = {}
    tools: dict[tuple[str, str], set[str]] = {}
    for path in sorted((PKG / "tools").glob("*.py")):
        mod = path.stem
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports[mod] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("mcp_legal_it.tools."):
                for alias in node.names:
                    imports[mod][alias.asname or alias.name] = (node.module.rsplit(".", 1)[1], alias.name)
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions[(mod, node.name)] = node
                for dec in node.decorator_list:
                    if isinstance(dec, ast.Call) and getattr(dec.func, "attr", "") == "tool":
                        tags = set()
                        for kw in dec.keywords:
                            if kw.arg == "tags":
                                tags = {e.value for e in kw.value.elts}
                        tools[(mod, node.name)] = tags

    def refs(key):
        mod, _ = key
        out = set()
        for node in ast.walk(functions[key]):
            name = node.id if isinstance(node, ast.Name) else node.attr if isinstance(node, ast.Attribute) else None
            if name is None:
                continue
            if name in SINKS:
                out.add(("sink", name))
            elif (mod, name) in functions:
                out.add((mod, name))
            elif name in imports[mod] and imports[mod][name] in functions:
                out.add(imports[mod][name])
        return out

    def reaches(key, seen):
        for ref in refs(key):
            if ref[0] == "sink":
                return True
            if ref not in seen:
                seen.add(ref)
                if reaches(ref, seen):
                    return True
        return False

    return {name: (reaches((mod, name), {(mod, name)}), tags) for (mod, name), tags in tools.items()}


def test_every_tool_reaching_brocardi_carries_the_tag():
    reach = _tool_reach()
    assert len(reach) == 228
    reaching = {n for n, (r, _) in reach.items() if r}
    tagged = {n for n, (_, tags) in reach.items() if switch.TAG in tags}
    assert reaching == tagged == set(CALLS)


def test_only_the_scrapers_name_a_brocardi_url():
    # A Brocardi URL literal outside the two scrapers, the static URL table of
    # visualex/map.py and the egress list would be a request path the switch does not
    # guard. (Prose that names the host, as in a docstring, is not a URL.)
    allowed = {
        PKG / "lib" / "brocardi" / "client.py",
        PKG / "lib" / "visualex" / "scraper.py",
        PKG / "lib" / "visualex" / "map.py",
        PKG / "lib" / "_brocardi_switch.py",
    }
    offenders = [
        str(p.relative_to(REPO)) for p in PKG.rglob("*.py")
        if p not in allowed and "://www.brocardi.it" in p.read_text(encoding="utf-8")
    ]
    assert offenders == []


# --- the stock server under LEGAL_BROCARDI=off --------------------------------

def test_the_stock_server_hides_the_solo_brocardi_tools(tmp_path):
    snippet = (
        "import asyncio, json\n"
        "from fastmcp import Client\n"
        "from mcp_legal_it.server import mcp\n"
        "async def main():\n"
        "    async with Client(mcp) as c:\n"
        "        instructions = getattr(c, 'instructions', None) or c.initialize_result.instructions\n"
        "        return {'tools': sorted(t.name for t in await c.list_tools()), 'instructions': instructions}\n"
        "print(json.dumps(asyncio.run(main())))\n"
    )
    env = {**os.environ, "LEGAL_BROCARDI": "off", "HOME": str(tmp_path), "LEGAL_CACHE": "off"}
    env.pop("LEGAL_PROFILE", None)
    out = subprocess.run([sys.executable, "-c", snippet], cwd=REPO / "plugin" / "server", env=env,
                         capture_output=True, text=True, check=True)
    surface = json.loads(out.stdout.strip().splitlines()[-1])
    names = set(surface["tools"])
    assert len(names) == 226
    assert not names & {"cerca_brocardi", "fetch_law_annotations"}
    assert "cite_law" in names
    # The instructions never send the model to a tool the server does not list.
    assert named_tools(surface["instructions"]) <= names
    assert "cite_law → giurisprudenza_su_norma" in surface["instructions"]
    assert "Brocardi per dottrina" not in surface["instructions"]


def named_tools(text: str) -> set[str]:
    from mcp_legal_it.server import _ALL_TOOL_NAMES

    return set(re.findall(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b", text)) & _ALL_TOOL_NAMES


def test_the_stock_instructions_are_untouched_with_brocardi_on():
    from mcp_legal_it.server import _STOCK_INSTRUCTIONS, crea_server, mcp

    assert mcp.instructions == _STOCK_INSTRUCTIONS
    assert "cerca_brocardi" in mcp.instructions
    assert crea_server().instructions == _STOCK_INSTRUCTIONS


@pytest.mark.parametrize("kwargs", [
    {"brocardi": False},
    {"include_tags": {"normativa", "giurisprudenza"}, "brocardi": False},
    {"include_tags": {"calcolo"}},
    {"include_tags": {"privacy"}},
    {"exclude_tags": {"brocardi"}},
    {"include_tags": {"diagnostica"}},
])
def test_crea_server_instructions_name_only_listed_tools(kwargs):
    from mcp_legal_it.server import crea_server

    server = crea_server(**kwargs)

    async def surface():
        async with Client(server) as c:
            instructions = getattr(c, "instructions", None) or c.initialize_result.instructions
            return instructions, {t.name for t in await c.list_tools()}

    instructions, names = asyncio.run(surface())
    assert instructions == server.instructions
    assert named_tools(instructions) <= names, named_tools(instructions) - names

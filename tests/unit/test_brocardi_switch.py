"""Brocardi is off by default (LI-079): no Brocardi tool listed, no request to brocardi.it.

Brocardi.it is the server's only private source. It is off unless the operator sets
``LEGAL_BROCARDI=on`` or code switches it on; an operator's off (``off``, or a value
the switch does not recognise) wins over code. These tests hold the promises of
lib/_brocardi_switch.py:

* the environment values: unset is off, ``on`` is on, ``off`` is off, anything else
  is off and named;
* the ``solo_brocardi`` tools are not listed nor callable while Brocardi is off for
  the request (stock server, crea_server), and are listed and callable where code
  or the environment switched it on: 233 and 235 tools;
* nothing reaches brocardi.it while it is off: the network is mocked and every
  request recorded, and any request to a Brocardi host fails the test, whichever
  tool sent it;
* every tool that can return Brocardi content is tagged ``brocardi``, checked
  statically on the call graph of the tool modules, so a new tool that reaches the
  scrapers without the tag fails here.

No fixture here (or anywhere) switches Brocardi on for every test: each test that
needs it on says so.
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
SOLO = {"cerca_brocardi", "fetch_law_annotations"}
MIXED = set(CALLS) - SOLO

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
    # empty them so that the "switch on" controls really reach the network.
    monkeypatch.setattr("mcp_legal_it.lib.brocardi.client._url_cache", {})
    monkeypatch.setattr("mcp_legal_it.lib.visualex.scraper._brocardi_url_cache", {})
    return Network().install(monkeypatch)


@pytest.fixture
def unset(monkeypatch):
    """The environment says nothing: Brocardi is off by default."""
    monkeypatch.delenv(switch.ENV_SWITCH, raising=False)


@pytest.fixture(autouse=True)
def _no_process_default():
    """A test that sets the process default must not leak it to the next one."""
    switch.set_default(None)
    yield
    switch.set_default(None)


def _text(result) -> str:
    return "\n".join(getattr(c, "text", "") for c in result.content)


async def _call_all(server, names=CALLS) -> dict[str, str]:
    out = {}
    async with Client(server) as client:
        for name in names:
            result = await client.call_tool(name, CALLS[name], raise_on_error=False)
            out[name] = _text(result)
    return out


async def _listed(server) -> set[str]:
    async with Client(server) as client:
        return {t.name for t in await client.list_tools()}


def listed(server) -> set[str]:
    return asyncio.run(_listed(server))


# --- the switch itself ---------------------------------------------------------

@pytest.mark.parametrize("value,state", [
    (None, "unset"), ("", "unset"), ("   ", "unset"),
    ("on", "on"), ("ON", "on"), (" 1 ", "on"), ("true", "on"), ("Yes", "on"),
    ("off", "off"), ("OFF", "off"), (" 0 ", "off"), ("false", "off"), ("no", "off"),
    ("si", "unrecognised"), ("sì", "unrecognised"), ("of", "unrecognised"),
    ("enabled", "unrecognised"), ("2", "unrecognised"),
])
def test_environment_values(value, state, monkeypatch):
    if value is None:
        monkeypatch.delenv(switch.ENV_SWITCH, raising=False)
    else:
        monkeypatch.setenv(switch.ENV_SWITCH, value)
    assert switch.environment_state() == state
    # Only an accepted «on» switches Brocardi on: unset, off and anything else are off.
    assert switch.enabled() is (state == "on")
    assert switch.off_by_environment() is (state in ("off", "unrecognised"))
    assert switch.unrecognised_value() == (value.strip() if state == "unrecognised" else None)


def test_default_is_off(unset):
    assert not switch.enabled()
    assert switch.environment_state() == "unset"


def test_the_note_is_neutral():
    # Off is the normal state: the note never says how to switch Brocardi on.
    assert switch.DISABLED_NOTE == (
        "Brocardi non attivo in questa installazione: "
        "nessuna annotazione dottrinale né massima da brocardi.it"
    )
    assert "LEGAL_BROCARDI" not in switch.DISABLED_NOTE and "\n" not in switch.DISABLED_NOTE


def test_code_can_switch_it_on_when_the_environment_is_unset(unset):
    from mcp_legal_it.core._config import configurazione

    with configurazione(brocardi=True):
        assert switch.enabled()
    assert not switch.enabled()
    switch.set_default(True)
    assert switch.enabled()
    with switch.disabled():
        assert not switch.enabled()
    assert switch.enabled()


def test_code_can_switch_it_off_when_the_environment_says_on(monkeypatch):
    from mcp_legal_it.core._config import configurazione

    monkeypatch.setenv(switch.ENV_SWITCH, "on")
    assert switch.enabled()
    with switch.disabled():
        assert not switch.enabled()
    with configurazione(brocardi=False):
        assert not switch.enabled()
    switch.set_default(False)
    assert not switch.enabled()


@pytest.mark.parametrize("value", ["off", "0", "si", "of"])
def test_code_cannot_switch_back_on_what_the_environment_switched_off(value, monkeypatch):
    from mcp_legal_it.core._config import configura, configurazione
    from mcp_legal_it.server import crea_server

    monkeypatch.setenv(switch.ENV_SWITCH, value)
    attempts = (
        lambda: switch.set_default(True),
        lambda: configura(brocardi=True),
        lambda: configurazione(brocardi=True).__enter__(),
        lambda: crea_server(brocardi=True),
    )
    for attempt in attempts:
        with pytest.raises(ValueError) as refused:
            attempt()
        # The message names the value it got and, when it does not recognise it, the accepted ones.
        assert repr(value) in str(refused.value)
        if value in ("si", "of"):
            assert "on, 1, true, yes" in str(refused.value) and "off, 0, false, no" in str(refused.value)
    token = switch.set_for_context(True)
    try:
        assert not switch.enabled()
    finally:
        switch.reset(token)


def test_the_egress_list_refuses_brocardi_unless_on(monkeypatch):
    monkeypatch.delenv(switch.ENV_SWITCH, raising=False)
    assert not _egress.is_allowed("https://www.brocardi.it/codice-civile/")
    monkeypatch.setenv(switch.ENV_SWITCH, "on")
    assert _egress.is_allowed("https://www.brocardi.it/codice-civile/")
    monkeypatch.setenv(switch.ENV_SWITCH, "off")
    assert not _egress.is_allowed("https://www.brocardi.it/codice-civile/")
    assert _egress.is_allowed("https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:legge")


# --- no request reaches brocardi.it -------------------------------------------

@pytest.mark.parametrize("value", [None, "off", "si"])
def test_the_scrapers_send_nothing_when_off(value, network, monkeypatch):
    from mcp_legal_it.lib.brocardi.client import fetch_brocardi, find_article_url
    from mcp_legal_it.lib.visualex.models import Norma, NormaVisitata
    from mcp_legal_it.lib.visualex.scraper import _find_brocardi_article_url, fetch_annotations

    if value is None:
        monkeypatch.delenv(switch.ENV_SWITCH, raising=False)
    else:
        monkeypatch.setenv(switch.ENV_SWITCH, value)
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


def test_the_control_with_the_switch_on_does_reach_brocardi(network, monkeypatch):
    # Proves the mock sees Brocardi traffic: with the switch on, cerca_brocardi tries.
    from mcp_legal_it.server import mcp

    monkeypatch.setenv(switch.ENV_SWITCH, "on")
    asyncio.run(_call_all(mcp, ["cerca_brocardi"]))
    assert network.brocardi


@pytest.mark.parametrize("value", [None, "off", "si"])
def test_no_brocardi_tool_reaches_brocardi_by_default_or_when_off(value, network, monkeypatch):
    from mcp_legal_it.server import mcp

    if value is None:
        monkeypatch.delenv(switch.ENV_SWITCH, raising=False)
    else:
        monkeypatch.setenv(switch.ENV_SWITCH, value)
    answers = asyncio.run(_call_all(mcp))
    assert network.brocardi == [], network.brocardi
    # The solo_brocardi tools are not there to call; cite_law answers with the note in
    # the place of the Brocardi section (the other mixed tools need their mocked, down,
    # core and are checked on a reachable one below).
    for name in SOLO:
        assert "Unknown tool" in answers[name], (name, answers[name][:200])
    assert f"**Annotazioni Brocardi**: {switch.DISABLED_NOTE}" in answers["cite_law"], answers["cite_law"][-400:]


async def _italgiure_up(*args, **kwargs):
    from mcp_legal_it.lib._result import SearchResult

    return SearchResult(success=True, source="italgiure", num_found=1, results_text="risultati Italgiure")


def test_giurisprudenza_articolo_says_brocardi_is_off(network, unset, monkeypatch):
    from mcp_legal_it.tools import italgiure

    monkeypatch.setattr(italgiure, "_giurisprudenza_su_norma_impl", _italgiure_up)
    result = asyncio.run(italgiure._giurisprudenza_articolo_impl("art. 2043 c.c."))
    assert switch.DISABLED_NOTE in result.results_text
    assert "risultati Italgiure" in result.results_text
    # One line, before the Italgiure results.
    assert result.results_text.count(switch.DISABLED_NOTE) == 1
    assert result.results_text.splitlines()[0].count("Brocardi") == 1
    assert network.urls == []


def test_mappa_orientamento_says_brocardi_is_off(network, unset, monkeypatch):
    from mcp_legal_it.tools import orientamento

    monkeypatch.setattr(orientamento, "_orientamento_su_norma_impl", _italgiure_up)
    result = asyncio.run(orientamento._mappa_orientamento_impl("art. 2043 c.c."))
    assert switch.DISABLED_NOTE in result.results_text
    assert result.results_text.count(switch.DISABLED_NOTE) == 1
    assert "risultati Italgiure" in result.results_text
    assert network.urls == []


def test_cite_law_without_annotations_says_nothing_about_brocardi(network, unset):
    # The note appears only where a Brocardi section would have been.
    from mcp_legal_it.server import mcp

    answer = asyncio.run(_call_all(mcp, ["cite_law"]))  # with annotations: the note
    assert switch.DISABLED_NOTE in answer["cite_law"]

    async def plain():
        async with Client(mcp) as client:
            return _text(await client.call_tool("cite_law", {"reference": "art. 2043 c.c."}, raise_on_error=False))

    assert "Brocardi" not in asyncio.run(plain())
    assert network.brocardi == []


# --- what is listed, and that listing and calling agree ------------------------

def test_the_stock_server_lists_233_by_default_and_235_with_on(unset, monkeypatch):
    from mcp_legal_it.server import mcp

    names = listed(mcp)
    assert len(names) == 233 and not names & SOLO and MIXED <= names
    monkeypatch.setenv(switch.ENV_SWITCH, "on")
    names = listed(mcp)
    assert len(names) == 235 and SOLO <= names
    monkeypatch.setenv(switch.ENV_SWITCH, "off")
    assert len(listed(mcp)) == 233


def test_listing_and_calling_agree_on_the_stock_server(network, unset):
    # Off for the request: the tool is neither listed nor callable, in the same session.
    from mcp_legal_it.server import mcp

    async def session():
        async with Client(mcp) as client:
            names = {t.name for t in await client.list_tools()}
            result = await client.call_tool("cerca_brocardi", CALLS["cerca_brocardi"], raise_on_error=False)
            return names, result

    names, result = asyncio.run(session())
    assert "cerca_brocardi" not in names
    assert result.is_error and "Unknown tool" in _text(result)
    assert network.urls == []


def test_crea_server_true_lists_and_calls_the_solo_tools_with_the_environment_unset(network, unset):
    from mcp_legal_it.server import crea_server, mcp

    server = crea_server(brocardi=True)

    async def session():
        async with Client(server) as client:
            names = {t.name for t in await client.list_tools()}
            result = await client.call_tool("cerca_brocardi", CALLS["cerca_brocardi"], raise_on_error=False)
            return names, result

    names, result = asyncio.run(session())
    assert len(names) == 235 and SOLO <= names
    # Callable: the call ran and tried brocardi.it (the mocked network is down).
    assert "Unknown tool" not in _text(result)
    assert network.brocardi
    # The instructions keep the Brocardi line, since the tool is listed.
    assert "cerca_brocardi" in server.instructions
    # The stock server, in the same process, is still off.
    assert not switch.enabled()
    assert not listed(mcp) & SOLO


def test_crea_server_follows_the_process_by_default(unset, monkeypatch):
    from mcp_legal_it.server import crea_server

    server = crea_server()
    assert not listed(server) & SOLO
    assert "cerca_brocardi" not in server.instructions
    switch.set_default(True)
    assert SOLO <= listed(server)
    switch.set_default(None)
    monkeypatch.setenv(switch.ENV_SWITCH, "on")
    assert SOLO <= listed(crea_server())


def test_crea_server_switches_brocardi_off_for_its_calls_only(network, monkeypatch):
    from mcp_legal_it.server import crea_server, mcp

    monkeypatch.setenv(switch.ENV_SWITCH, "on")
    server = crea_server(brocardi=False)
    names = listed(server)
    assert not names & SOLO
    assert MIXED <= names
    answers = asyncio.run(_call_all(server, sorted(MIXED)))
    assert network.brocardi == []
    assert switch.DISABLED_NOTE in answers["cite_law"], answers["cite_law"]
    # The stock server, in the same process, still has Brocardi.
    assert switch.enabled()
    assert SOLO <= listed(mcp)


def test_every_brocardi_tool_is_exercised(monkeypatch):
    from mcp_legal_it.server import mcp

    monkeypatch.setenv(switch.ENV_SWITCH, "on")
    tagged = {t.name for t in asyncio.run(mcp.list_tools()) if switch.TAG in t.tags}
    assert tagged == set(CALLS)
    assert {t.name for t in asyncio.run(mcp.list_tools()) if switch.TAG_SOLO in t.tags} == SOLO


# --- stato_server says which case applies --------------------------------------

@pytest.mark.parametrize("value,stato,attivo", [
    (None, "spento_per_default", False),
    ("on", "acceso", True),
    ("off", "spento_esplicito", False),
    ("si", "valore_non_riconosciuto", False),
])
def test_stato_server_reports_the_case(value, stato, attivo, monkeypatch):
    from mcp_legal_it.server import mcp

    if value is None:
        monkeypatch.delenv(switch.ENV_SWITCH, raising=False)
    else:
        monkeypatch.setenv(switch.ENV_SWITCH, value)

    async def stato_server():
        async with Client(mcp) as client:
            return json.loads(_text(await client.call_tool("stato_server", {})))

    report = asyncio.run(stato_server())
    assert report["brocardi"]["stato"] == stato
    assert report["brocardi"]["attivo"] is attivo
    assert report["brocardi"]["valore_non_riconosciuto"] == ("si" if value == "si" else None)
    assert report["tools_attivi"] == (235 if attivo else 233)
    # stato_server describes the state; it never tells how to switch Brocardi on.
    assert "=on" not in report["brocardi"]["nota"]


def test_stato_server_inside_crea_server_true_counts_the_stock_surface(unset):
    from mcp_legal_it.server import crea_server

    async def stato_server():
        async with Client(crea_server(brocardi=True)) as client:
            return json.loads(_text(await client.call_tool("stato_server", {})))

    report = asyncio.run(stato_server())
    assert report["brocardi"]["attivo"] is True
    assert report["brocardi"]["stato"] == "spento_per_default"
    assert report["tools_attivi"] == 233


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
    assert len(reach) == 235
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


# --- the stock server as it starts: listing, instructions, start-up warning ----

_SNIPPET = (
    "import asyncio, json\n"
    "from fastmcp import Client\n"
    "from mcp_legal_it.server import mcp\n"
    "async def main():\n"
    "    async with Client(mcp) as c:\n"
    "        instructions = getattr(c, 'instructions', None) or c.initialize_result.instructions\n"
    "        return {'tools': sorted(t.name for t in await c.list_tools()), 'instructions': instructions}\n"
    "print(json.dumps(asyncio.run(main())))\n"
)


def _stock_server(tmp_path, value: str | None) -> tuple[dict, str]:
    env = {**os.environ, "HOME": str(tmp_path), "LEGAL_CACHE": "off"}
    env.pop("LEGAL_PROFILE", None)
    env.pop(switch.ENV_SWITCH, None)
    if value is not None:
        env[switch.ENV_SWITCH] = value
    out = subprocess.run([sys.executable, "-c", _SNIPPET], cwd=REPO / "plugin" / "server", env=env,
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1]), out.stderr


def named_tools(text: str) -> set[str]:
    from mcp_legal_it.server import _ALL_TOOL_NAMES

    return set(re.findall(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b", text)) & _ALL_TOOL_NAMES


@pytest.mark.parametrize("value", [None, "off"])
def test_the_stock_server_starts_without_brocardi(value, tmp_path):
    surface, stderr = _stock_server(tmp_path, value)
    names = set(surface["tools"])
    assert len(names) == 233
    assert not names & SOLO
    assert "cite_law" in names
    # The instructions never send the model to a tool the server does not list,
    # and the Italgiure path is the norm workflow.
    assert named_tools(surface["instructions"]) <= names
    assert "Norma → cite_law → giurisprudenza_su_norma → leggi_sentenza" in surface["instructions"]
    assert "DOTTRINA" not in surface["instructions"]
    assert "LEGAL_BROCARDI" not in stderr


def test_the_stock_server_starts_with_brocardi_on(tmp_path):
    from mcp_legal_it.server import _STOCK_INSTRUCTIONS

    surface, _ = _stock_server(tmp_path, "on")
    assert len(surface["tools"]) == 235
    assert surface["instructions"] == _STOCK_INSTRUCTIONS
    assert "cerca_brocardi" in surface["instructions"]


def test_an_unrecognised_value_is_off_and_reported_on_stderr(tmp_path):
    surface, stderr = _stock_server(tmp_path, "si")
    assert len(surface["tools"]) == 233
    assert "LEGAL_BROCARDI='si'" in stderr and "on, 1, true, yes" in stderr
    # stderr only: the tool listing and the instructions say nothing about it.
    assert "'si'" not in surface["instructions"]


def test_the_stock_literal_keeps_the_brocardi_line_for_a_server_that_lists_it():
    from mcp_legal_it.server import _STOCK_INSTRUCTIONS

    assert "cerca_brocardi" in _STOCK_INSTRUCTIONS
    assert "Norma → cite_law → giurisprudenza_su_norma → leggi_sentenza" in _STOCK_INSTRUCTIONS


@pytest.mark.parametrize("kwargs", [
    {},
    {"brocardi": True},
    {"brocardi": False},
    {"include_tags": {"normativa", "giurisprudenza"}, "brocardi": False},
    {"include_tags": {"normativa", "giurisprudenza"}, "brocardi": True},
    {"include_tags": {"calcolo"}},
    {"include_tags": {"privacy"}},
    {"exclude_tags": {"brocardi"}},
    {"include_tags": {"diagnostica"}},
])
def test_crea_server_instructions_name_only_listed_tools(kwargs, unset):
    from mcp_legal_it.server import crea_server

    server = crea_server(**kwargs)

    async def surface():
        async with Client(server) as c:
            instructions = getattr(c, "instructions", None) or c.initialize_result.instructions
            return instructions, {t.name for t in await c.list_tools()}

    instructions, names = asyncio.run(surface())
    assert instructions == server.instructions
    assert named_tools(instructions) <= names, named_tools(instructions) - names

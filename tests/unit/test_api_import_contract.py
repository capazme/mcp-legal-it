"""Import contract of ``mcp_legal_it.api``: no FastMCP, no server, no tools, no network.

Each check runs in a fresh interpreter, so nothing another test imported can
hide a dependency. FastMCP (and the MCP SDK) are made to fail on import, and
every socket connection and DNS lookup raises.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[2] / "plugin" / "server"

_GUARDS = r'''
import socket, sys

class _Blocked:
    """Any import of FastMCP, the MCP SDK, the server or the tool modules fails."""

    def find_spec(self, name, path=None, target=None):
        blocked = ("fastmcp", "mcp", "mcp_legal_it.server", "mcp_legal_it.tools")
        if any(name == b or name.startswith(b + ".") for b in blocked):
            raise ImportError("blocked by the import-contract test: " + name)
        return None

sys.meta_path.insert(0, _Blocked())

def _no_network(*args, **kwargs):
    raise OSError("network blocked by the import-contract test")

socket.socket.connect = _no_network
socket.socket.connect_ex = _no_network
socket.create_connection = _no_network
socket.getaddrinfo = _no_network
'''


def _run(body: str) -> dict:
    code = _GUARDS + body
    env = {**os.environ, "PYTHONPATH": str(PACKAGE_ROOT), "LEGAL_CACHE": "off"}
    out = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout.strip().splitlines()[-1])


def test_import_pulls_in_neither_fastmcp_nor_the_server():
    result = _run(r'''
import json
import mcp_legal_it.api as api
mods = sorted(sys.modules)
print(json.dumps({
    "names": len(api.__all__),
    "fastmcp": [m for m in mods if m == "fastmcp" or m.startswith("fastmcp.") or m == "mcp" or m.startswith("mcp.")],
    "server": [m for m in mods if m == "mcp_legal_it.server" or m.startswith("mcp_legal_it.tools")],
}))
''')
    assert result["names"] > 0
    assert result["fastmcp"] == []
    assert result["server"] == []


def test_constants_and_offline_functions_work_with_the_network_blocked():
    result = _run(r'''
import json, re
from mcp_legal_it.api import ARTICLE_SUFFIX_ALTERNATION, SUFFISSI_ARTICOLO, catalogo_alias, leggi_riferimento
r = leggi_riferimento("art. 2-bis D.Lgs. 196/2003")
print(json.dumps({
    "suffix": bool(re.fullmatch(rf"(?:{ARTICLE_SUFFIX_ALTERNATION})", "quinquiesdecies")),
    "groups": len(SUFFISSI_ARTICOLO),
    "esito": r.esito,
    "urn": r.norma_data[0].urn,
    "gdpr": catalogo_alias().presets["gdpr"],
}))
''')
    assert result["suffix"] is True
    assert result["groups"] == 19  # bis (2nd) ... vicies (20th)
    assert result["esito"] == "trovato"
    assert result["urn"] == "urn:nir:stato:decreto.legislativo:2003-06-30;196~art2bis"
    assert result["gdpr"] == {"act_type": "regolamento ue", "act_number": "679", "date": "2016"}


def test_a_network_call_with_the_network_blocked_is_an_outcome_not_an_exception():
    result = _run(r'''
import asyncio, json
from mcp_legal_it import api
t = asyncio.run(api.testo_articolo("art. 2043 c.c.", canale="akn"))
d = asyncio.run(api.leggi_decisione(api.RiferimentoDecisione(corte="cassazione", numero=1, anno=2024)))
print(json.dumps({"articolo": t.esito, "decisione": d.esito}))
''')
    assert result["articolo"] in ("verifica_non_disponibile", "errore_fonte")
    assert result["decisione"] in ("fonte_non_raggiungibile", "errore_fonte")


def test_the_stock_server_still_registers_every_tool_after_the_api_is_imported():
    # Importing the API first must not change what the server registers.
    out = subprocess.run(
        [sys.executable, "-c",
         "import asyncio, mcp_legal_it.api\n"
         "from fastmcp import Client\n"
         "from mcp_legal_it.server import mcp\n"
         "async def n():\n"
         "    async with Client(mcp) as c:\n"
         "        return len(await c.list_tools())\n"
         "print(asyncio.run(n()))"],
        env={**os.environ, "PYTHONPATH": str(PACKAGE_ROOT)}, capture_output=True, text=True, timeout=120,
    )
    assert out.returncode == 0, out.stderr
    assert int(out.stdout.strip().splitlines()[-1]) == 234

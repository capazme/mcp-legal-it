"""Frozen registration surface: 221 tools, 23 prompts, 15 resources.

Uses the in-process fastmcp Client (FastMCP 3.4.7 — get_tools() no longer exists).
Requires LEGAL_PROFILE unset/full (the default test environment).
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))

EXPECTED_RESOURCE_URIS = {
    "legal://riferimenti/procedura-civile", "legal://riferimenti/termini-processuali",
    "legal://riferimenti/contributo-unificato", "legal://riferimenti/irpef-detrazioni",
    "legal://riferimenti/interessi-legali", "legal://riferimenti/checklist-decreto-ingiuntivo",
    "legal://riferimenti/fonti-diritto-italiano", "legal://riferimenti/codici-e-leggi-principali",
    "legal://riferimenti/gdpr-checklist", "legal://riferimenti/consob-delibere",
    "legal://riferimenti/ricerca-giurisprudenziale", "legal://riferimenti/cerdef-giurisprudenza",
    "legal://riferimenti/modelli-atti-catalogo", "legal://riferimenti/giustizia-amministrativa",
    "legal://riferimenti/cgue-giurisprudenza",
}

def test_registration_surface():
    from fastmcp import Client
    from src.server import mcp
    from tests.unit.test_prompt_surface import EXPECTED as EXPECTED_PROMPTS

    async def run():
        async with Client(mcp) as c:
            return (
                await c.list_tools(), await c.list_prompts(), await c.list_resources()
            )

    tools, prompts, resources = asyncio.run(run())
    assert len(tools) == 221, f"tool count changed: {len(tools)}"
    assert {p.name for p in prompts} == set(EXPECTED_PROMPTS)
    assert {str(r.uri) for r in resources} == EXPECTED_RESOURCE_URIS


def test_tool_vocabulary_matches_server():
    import json

    from fastmcp import Client
    from src.server import mcp

    async def run():
        async with Client(mcp) as c:
            return sorted(t.name for t in await c.list_tools())

    vocab = json.loads((Path(__file__).parents[2] / "content" / "tool-vocabulary.json").read_text())
    assert asyncio.run(run()) == vocab, "content/tool-vocabulary.json drifted — rerun scripts/corpus/dump_vocabulary.py"

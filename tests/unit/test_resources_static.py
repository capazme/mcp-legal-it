"""Static resources are file-backed and byte-identical to the corpus."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))

REPO = Path(__file__).parents[2]

def test_static_resources_serve_the_reference_files():
    from fastmcp import Client
    from src.server import mcp

    async def run():
        async with Client(mcp) as c:
            out = {}
            for uri in [u for u, *_ in _table()]:
                res = await c.read_resource(uri)
                out[uri] = res[0].text
            return out

    def _table():
        from src.resources import _STATIC_RESOURCES
        return _STATIC_RESOURCES

    served = asyncio.run(run())
    assert len(served) == 12
    for uri, fname, _n, _d in _table():
        expected = (REPO / "content" / "references" / fname).read_text(encoding="utf-8")
        assert served[uri] == expected, uri

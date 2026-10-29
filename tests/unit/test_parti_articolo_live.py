"""Live gate: a comma of an article Normattiva splits into parts is read from its part. 3 requests.

Art. 1 L. 296/2006 is 14 parts of up to 100 commi; comma 773 is in part 8 (commi 701-800).
Without a date Normattiva serves a version not in force yet (from 2027), so the article's
page is read twice (undated, then at today's date), then part 8 with that page's session:
3 requests, one at a time; the count is printed before the first. The expected words are
the ones Normattiva gave on 2026-10-29.

    .venv/bin/pytest tests/unit/test_parti_articolo_live.py -m live -q -s -p no:cacheprovider
"""

import pytest

from mcp_legal_it.lib.visualex import pagine_normattiva, scraper
from mcp_legal_it.tools import legal_citations as lc

pytestmark = pytest.mark.live

RICHIESTE = 3


async def test_comma_773_of_art_1_l_296_2006(monkeypatch, tmp_path):
    monkeypatch.setenv("MCP_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(scraper, "_full_date_cache", {})
    monkeypatch.setattr(scraper, "_sessioni", {})
    pagine_normattiva.svuota_memoria()
    print(f"\nparti dell'articolo: {RICHIESTE} richieste a Normattiva, una alla volta")
    out = await lc._cite_law_impl("art. 1, comma 773, legge 27 dicembre 2006, n. 296")
    if out.startswith("**Errore**"):
        pytest.skip(f"Normattiva non ha risposto: {out[:200]}")
    assert "complessivamente rideterminata nel 10 per cento" in out
    assert "**Commi 701-800** (parte 8 di 14 dell'articolo su Normattiva)" in out
    assert "testo parziale: commi 701-800 di 1364" in out

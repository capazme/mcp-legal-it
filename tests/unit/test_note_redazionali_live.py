"""Live gate: the Gazzetta's editorial notes of Normattiva article pages are read beside the text. 4 requests.

One request per article, one at a time with a 2-second pause; the count is printed before the
first. The expected sections are the ones Normattiva gave on 2026-11-02 (issue #119): the
current text of an article never amended keeps them, an amended one does not.

    .venv/bin/pytest tests/unit/test_note_redazionali_live.py -m live -q -s -p no:cacheprovider
"""

import asyncio

import pytest

from mcp_legal_it import api
from mcp_legal_it.lib.visualex import pagine_normattiva, scraper

pytestmark = pytest.mark.live

# (tipo, articolo, data, numero) -> the headings of its editorial notes, in order
CASI = [
    (("legge", "7", "2017-03-08", "24"), ["Note all'art. 7"]),
    (("legge", "1", "2025-09-23", "132"), ["Note all'art. 1"]),  # not the Avvertenza (LI-058)
    (("decreto legislativo", "4", "2001-06-08", "231"), ["Nota all'art. 4"]),
    (("decreto legislativo", "5", "2001-06-08", "231"), []),
]


async def test_the_editorial_notes_are_read_beside_the_text(monkeypatch, tmp_path):
    monkeypatch.setenv("MCP_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("AKN_DISABLED", "1")
    monkeypatch.setattr(scraper, "_full_date_cache", {})
    pagine_normattiva.svuota_memoria()
    print(f"\nnote redazionali: {len(CASI)} richieste a Normattiva, una alla volta")
    letti = []
    for i, (parametri, _atteso) in enumerate(CASI):
        if i:
            await asyncio.sleep(2)
        letti.append(await api.testo_articolo(api.riferimento_da_parametri(*parametri).norma_data[0], canale="html"))
    for (parametri, intestazioni), t in zip(CASI, letti):
        if t.esito != "trovato":
            pytest.skip(f"Normattiva non ha servito {parametri}: {t.errore}")
        assert t.fonte == "normattiva", parametri
        assert [n.intestazione for n in t.note_redazionali] == intestazioni, parametri
        for n in t.note_redazionali:
            assert n.testo and n.testo not in t.article_text, parametri

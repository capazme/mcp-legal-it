"""Live gate: the «AGGIORNAMENTO (n)» notes of Normattiva article pages reach the reader. 5 requests.

One request per article, one at a time with a 2-second pause; the count is printed before the
first. The cite_law output of each is then built from the same reading (no request). The
expected notes are the ones Normattiva gave on 2026-10-29: the Corte costituzionale
declarations are marked, by number of the sentence. Art. 3 d.lgs. 23/2015 is the case that
broke: VisuaLex's text keeps the words C. cost. 194/2018 struck down, and the note saying so
must be there.

    .venv/bin/pytest tests/unit/test_note_aggiornamento_live.py -m live -q -s -p no:cacheprovider
"""

import asyncio
import re

import pytest

from mcp_legal_it import api
from mcp_legal_it.lib.visualex import pagine_normattiva, scraper
from mcp_legal_it.tools import legal_citations as lc

pytestmark = pytest.mark.live

# (tipo, articolo, data, numero, MCP reference) -> (note numbers, {note: sentence of the Corte}, notes in the text)
CASI = [
    (("decreto legislativo", "3", "2015-03-04", "23"), "art. 3 d.lgs. 4 marzo 2015, n. 23",
     ["1", "2", "3", "10"], {"2": "194", "10": "128"}, False),
    (("decreto legislativo", "9", "2015-03-04", "23"), "art. 9 d.lgs. 4 marzo 2015, n. 23",
     ["11"], {"11": "118"}, False),
    (("legge", "6", "1966-07-15", "604"), "art. 6 legge 15 luglio 1966, n. 604",
     ["10", "12", "15", "27"], {"15": "212", "27": "111"}, False),
    (("legge", "18", "1970-05-20", "300"), "art. 18 legge 20 maggio 1970, n. 300",
     ["9", "23", "28", "30"], {"28": "59", "30": "125"}, False),
    (("codice civile", "2327", "", ""), "art. 2327 c.c.", ["113"], {}, True),
]


async def test_the_notes_reach_the_reader(monkeypatch, tmp_path):
    monkeypatch.setenv("MCP_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(scraper, "_full_date_cache", {})
    pagine_normattiva.svuota_memoria()
    print(f"\nnote di aggiornamento: {len(CASI)} richieste a Normattiva, una alla volta")
    letti = []
    for i, (parametri, riferimento, *_atteso) in enumerate(CASI):
        if i:
            await asyncio.sleep(2)
        t = await api.testo_articolo(api.riferimento_da_parametri(*parametri).norma_data[0], canale="html")
        out = await lc._cite_law_impl(riferimento)  # the same page, from the reading just kept
        letti.append((t, out))
    for (parametri, riferimento, numeri, corte, nel_testo), (t, out) in zip(CASI, letti):
        if t.esito != "trovato":
            pytest.skip(f"Normattiva non ha servito {riferimento}: {t.errore}")
        assert t.fonte == "normattiva" and not t.note_non_lette, riferimento
        assert [n.numero for n in t.note_aggiornamento] == numeri, riferimento
        dichiarate = {n.numero: re.search(r"\bn\. ?(\d+)", n.testo).group(1)
                      for n in t.note_aggiornamento if n.corte_costituzionale}
        assert dichiarate == corte, riferimento
        if nel_testo:
            assert "**Aggiornamenti**" not in out and out.count(f"AGGIORNAMENTO ({numeri[0]})") == 1, riferimento
        else:
            sezione = out.split("**Aggiornamenti**", 1)[1]
            for numero in numeri:
                assert f"\n({numero}) " in sezione, (riferimento, numero)
    art3 = letti[0][1].split("**Aggiornamenti**", 1)[1]
    assert "(2) La Corte Costituzionale, con sentenza 26 settembre - 8 novembre 2018 n. 194" in art3
    assert "limitatamente alle parole «di importo pari a due mensilità" in art3

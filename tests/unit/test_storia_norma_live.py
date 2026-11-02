"""Live gate of ``storia_norma`` on Normattiva: 23 requests, one at a time.

Three articles, a 2-second pause between them; inside each walk the requests are serial
(one client, one session) under the library's Normattiva limits. The count is printed
before the first request. The expected versions are the ones Normattiva gave on
2026-10-29 and 2026-11-02 (the copies in ``tests/fixtures/normattiva/aggiornamenti``).
The disk cache is off, so every version is read. One article is asked in ``json``.

    .venv/bin/pytest tests/unit/test_storia_norma_live.py -m live -q -s -p no:cacheprovider
"""

import asyncio
import json
import re

import pytest

from mcp_legal_it import api
from mcp_legal_it.lib.visualex import act_dates, scraper
from mcp_legal_it.tools.vigenza import _storia_norma_impl

pytestmark = pytest.mark.live

# (riferimento, formato, requests, the "In vigore" column, version by version)
CASI = [
    ("art. 2-ter d.lgs. 196/2003", "json", 6,
     [(1, "2018-09-19", "2021-10-08"), (2, "2021-10-09", "2021-12-07"), (3, "2021-12-08", None)]),
    ("art. 64-bis d.lgs. 14/2019", "testo", 7,
     ["15/07/2022 – 27/09/2024", "28/09/2024 – 11/08/2026", "dal 12/08/2026"]),
    ("art. 612-bis c.p.", "testo", 10,
     ["25/02/2009 – 19/08/2013", "20/08/2013 – 15/10/2013", "16/10/2013 – 08/08/2019",
      "09/08/2019 – 16/12/2025", "dal 17/12/2025"]),
]
RICHIESTE = sum(caso[2] for caso in CASI)


def _incompleta(out: str, formato: str) -> bool:
    if formato == "json":
        dati = json.loads(out)
        return dati["esito"] == "verifica_non_disponibile" or (dati["esito"] == "trovato" and not dati["completa"])
    return "(verifica_non_disponibile)" in out or "storia incompleta" in out.splitlines()[0]


async def test_storia_norma_on_normattiva(monkeypatch, tmp_path):
    monkeypatch.setenv("MCP_CACHE_DIR", str(tmp_path / "cache"))  # never the user's cache
    monkeypatch.setattr(scraper, "_full_date_cache", {})
    act_dates.svuota_memoria()
    print(f"\nstoria_norma: {RICHIESTE} richieste a Normattiva, una alla volta")
    ottenuti = []
    with api.configurazione(cache=False):
        for i, (rif, formato, *_resto) in enumerate(CASI):
            if i:
                await asyncio.sleep(2)
            ottenuti.append(await _storia_norma_impl(rif, formato=formato))
    for (rif, formato, _, atteso), out in zip(CASI, ottenuti):
        if _incompleta(out, formato):
            pytest.skip(f"Normattiva non ha risposto per intero: {out[:300]}")
        if formato == "json":
            dati = json.loads(out)
            assert dati["esito"] == "trovato" and dati["precisione"] == "ESATTO", (rif, dati["errore"])
            assert [(v["version_number"], v["valid_from"], v["valid_to"]) for v in dati["versioni"]] == atteso
        else:
            assert "storia completa (ESATTO)" in out.splitlines()[0], (rif, out[:300])
            righe = [r for r in out.splitlines() if re.match(r"\| \d+ \|", r)]
            assert [r.split(" | ")[1] for r in righe] == atteso, rif
            assert "Vigenza non è applicabilità" in out

"""Live gate of ``api.modifiche_articolo`` on Normattiva: 12 requests, one at a time.

Four articles, a 2-second pause between them; inside each walk the requests are serial
(one client, one session) under the library's Normattiva limits. The count is printed
before the first request. The expected versions and amendments are the ones Normattiva
gave on 2026-10-29 (the copies in ``tests/fixtures/normattiva/aggiornamenti``). The disk
cache is off, so every version is read.

    .venv/bin/pytest tests/unit/test_api_modifiche_articolo_live.py -m live -q -s -p no:cacheprovider
"""

import asyncio

import pytest

from mcp_legal_it import api
from mcp_legal_it.lib.visualex import act_dates, scraper

pytestmark = pytest.mark.live

# (riferimento, requests, versions, amendments as (versione, in_vigore_dal, tipo, numero dell'atto))
CASI = [
    ("art. 2-ter d.lgs. 196/2003", 5,
     [(1, "2018-09-19", "2021-10-08"), (2, "2021-10-09", "2021-12-07"), (3, "2021-12-08", None)],
     [(2, "2021-10-09", "inserimento", "139"), (2, "2021-10-09", "modifica", "139"),
      (3, "2021-12-08", "modifica", "139"), (3, "2021-12-08", "modifica", "139"),
      (3, "2021-12-08", "conversione", "205")]),
    ("art. 2 c.c.", 3,
     [(1, "1942-04-19", "1975-03-09"), (2, "1975-03-10", None)],
     [(2, "1975-03-10", "modifica", "39")]),
    (("decreto del presidente della repubblica", "1", "1986-04-26", "131"), 3,
     [(1, "1986-07-01", "2026-12-31"), (2, "2027-01-01", None)],
     [(2, "2027-01-01", "abrogazione", "123")]),
    ("art. 2740 c.c.", 1, [(1, "1942-04-19", None)], []),
]
RICHIESTE = sum(caso[1] for caso in CASI)


async def test_modifiche_articolo_on_normattiva(monkeypatch):
    monkeypatch.setattr(scraper, "_full_date_cache", {})
    act_dates.svuota_memoria()
    print(f"\nmodifiche_articolo: {RICHIESTE} richieste a Normattiva, una alla volta")
    ottenuti = []
    with api.configurazione(cache=False):
        for i, (rif, *_resto) in enumerate(CASI):
            if i:
                await asyncio.sleep(2)
            if isinstance(rif, tuple):
                rif = api.riferimento_da_parametri(*rif).norma_data[0]
            ottenuti.append(await api.modifiche_articolo(rif))
    for (rif, _, versioni, modifiche), r in zip(CASI, ottenuti):
        if r.esito == "verifica_non_disponibile" or (r.esito == "trovato" and not r.completa):
            pytest.skip(f"Normattiva non ha risposto per intero: {r.errore or r.avvisi}")
        assert r.esito == "trovato" and r.completa, (rif, r.errore)
        assert [(v.version_number, v.valid_from, v.valid_to) for v in r.versioni] == versioni, rif
        assert [(m.versione, m.in_vigore_dal, m.tipo, m.atto.numero_atto) for m in r.modifiche] == modifiche, rif

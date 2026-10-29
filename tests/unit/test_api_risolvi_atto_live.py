"""Live gate of ``api.risolvi_atto`` on Normattiva: 6 requests, one at a time.

One request per act, each a distinct act, with a 2-second pause between calls, plus the
check on L. 241/1990 that the missing act's error page triggers; the count is printed
before the first one. The expected dates are the ones Normattiva gave on
2026-10-29 (page titles «DECRETO LEGISLATIVO 1 settembre 1993, n. 385», «LEGGE 7 agosto
1990, n. 241», «DECRETO 10 marzo 2014, n. 55» with ELI date 2014-03-10, «DECRETO DEL
PRESIDENTE DELLA REPUBBLICA 22 dicembre 1986, n. 917», and «Normattiva - Errore» for an
act it does not have). The disk cache is off and the memory caches are emptied, so every
case reaches the source.

    .venv/bin/pytest tests/unit/test_api_risolvi_atto_live.py -m live -q -s -p no:cacheprovider
"""

import asyncio

import pytest

from mcp_legal_it import api
from mcp_legal_it.lib.visualex import act_dates, scraper

pytestmark = pytest.mark.live

# (tipo_atto, numero_atto, anno_o_data) -> (esito, data, urn, precisione)
CASI = [
    (("d.lgs.", "385", "1993"),
     ("trovato", "1993-09-01", "urn:nir:stato:decreto.legislativo:1993-09-01;385", "ESATTO")),
    (("legge", "241", "7 agosto 1990"),
     ("trovato", "1990-08-07", "urn:nir:stato:legge:1990-08-07;241", "ESATTO")),
    (("decreto ministeriale", "55", "2014"),
     ("trovato", "2014-03-10", "urn:nir:stato:decreto.ministeriale:2014-03-10;55", "INDICATIVO")),
    (("legge", "99999", "1990"),
     ("atto_non_trovato", None, None, None)),
    (("d.P.R.", "917", "1986-12-23"),
     ("ambiguo", "1986-12-22", "urn:nir:stato:decreto.del.presidente.della.repubblica:1986-12-22;917", "ESATTO")),
]


# One per case, plus the known act read after the error page of L. 99999/1990.
RICHIESTE = len(CASI) + 1


async def test_risolvi_atto_on_normattiva(monkeypatch):
    monkeypatch.setattr(scraper, "_full_date_cache", {})
    monkeypatch.setattr(scraper, "_controllo_valido_fino", 0.0)
    act_dates.svuota_memoria()
    print(f"\nrisolvi_atto: {RICHIESTE} richieste a Normattiva, una alla volta")
    ottenuti = []
    with api.configurazione(cache=False):
        for i, (args, _) in enumerate(CASI):
            if i:
                await asyncio.sleep(2)
            ottenuti.append(await api.risolvi_atto(*args))
    act_dates.svuota_memoria()
    for (args, atteso), r in zip(CASI, ottenuti):
        if r.esito == "fonte_non_raggiungibile":
            pytest.skip(f"Normattiva non raggiungibile: {r.errore}")
        assert (r.esito, r.data, r.urn, r.precisione) == atteso, (args, r.errore)

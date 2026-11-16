"""A version Normattiva dates by an entry into force that a later act deferred (#172).

Art. 27 of d.lgs. 13 luglio 2017, n. 116 rewrites, among others, art. 7 and art. 543 c.p.c.
(the giudice di pace reform). Its art. 32, comma 3, deferred its entry into force several
times: 31/10/2021, 31/10/2025, 31/10/2026 and, by d.l. 12 giugno 2026, n. 100, 31/10/2027.
Normattiva dates the version that carries those amendments by an earlier date of that chain
and still serves it as the text in force; only the article's update notes say otherwise:

- art. 7: version 10, «in vigore dal 31-10-2025», with notes (179) «entrano in vigore il
  31 ottobre 2026» and (183) «… il 31 ottobre 2027». The text in force is version 9
  (01/01/2023-30/10/2025);
- art. 543: the deferred «giudice competente» entered version 7 (31-10-2021); versions 8 and
  9 (d.lgs. 164/2024) were laid on top of it, so no version is the text in force.

Pages: trimmed copies of what Normattiva served on 16 November 2026 (``tests/fixtures/
normattiva``). These tests fail until #172 is fixed: a text carrying amendments whose entry
into force the notes put after today is never ESATTO, and the answer says so.
"""

from pathlib import Path

import pytest

from mcp_legal_it import api
from mcp_legal_it.lib.visualex import akn_fetch, pagine_normattiva, scraper

NORMATTIVA = Path(__file__).resolve().parents[1] / "fixtures" / "normattiva"
OGGI = "2026-11-16"
ART7 = (NORMATTIVA / "cpc_art7_vig_2026-11-16_rinvio_2027_trimmed.html").read_text(encoding="utf-8")
ART543 = (NORMATTIVA / "cpc_art543_vig_2026-11-16_rinvio_2027_trimmed.html").read_text(encoding="utf-8")
CPC = "regio.decreto:1940-10-28;1443:1~art"

pytestmark = pytest.mark.finestra_reale  # the pages carry their own «Testo in vigore dal» block


@pytest.fixture(autouse=True)
def _oggi(monkeypatch):
    monkeypatch.setenv("LEGAL_TODAY", OGGI)


def _serve(monkeypatch, pagine: dict):
    """Normattiva pages by the URN after «urn:nir:stato:», ignoring a «!vig=» suffix."""

    class _Risposta:
        def __init__(self, url, text):
            self.url, self.text, self.status_code = url, text, 200

        def raise_for_status(self):
            return None

    class _Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def get(self, url):
            urn = url.split("urn:nir:stato:", 1)[-1].split("!vig=")[0]
            if urn not in pagine:
                raise AssertionError(f"unexpected request: {url}")
            return _Risposta(url, pagine[urn])

    async def nessun_export(norma, data_vigenza=None):
        return None

    monkeypatch.delenv("AKN_DISABLED", raising=False)
    monkeypatch.setattr(scraper.httpx, "AsyncClient", _Client)
    monkeypatch.setattr(akn_fetch, "fetch_act_akn", nessun_export)
    pagine_normattiva.svuota_memoria()


def _cpc(articolo: str):
    return api.leggi_riferimento(f"art. {articolo} c.p.c.").norma_data[0]


@pytest.mark.parametrize("articolo, pagina", [("7", ART7), ("543", ART543)], ids=["art7", "art543"])
async def test_the_fixture_is_the_bug(monkeypatch, articolo, pagina):
    """What Normattiva serves: a window holding today, and a note deferring to 31/10/2027."""
    _serve(monkeypatch, {CPC + articolo: pagina})
    t = await api.testo_articolo(_cpc(articolo), canale="html")
    assert t.esito == "trovato" and t.validity.state == "current"
    assert any("31 ottobre 2027" in n.testo for n in t.note_aggiornamento)


@pytest.mark.parametrize("articolo, pagina", [("7", ART7), ("543", ART543)], ids=["art7", "art543"])
async def test_a_deferred_entry_into_force_is_never_exact(monkeypatch, articolo, pagina):
    _serve(monkeypatch, {CPC + articolo: pagina})
    t = await api.testo_articolo(_cpc(articolo), canale="html")
    assert t.precisione != "ESATTO", t.precisione
    assert any("2027" in a for a in t.avvisi), t.avvisi

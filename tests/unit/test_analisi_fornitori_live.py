"""Live smoke gate for the two online tools of `src/tools/analisi_fornitori.py`.

What it checks, one real call per tool on a known document:

* `verifica_partita_iva_vies` against the VIES REST service of the European
  Commission (reg. (UE) 904/2010, art. 31: electronic confirmation of the
  validity of a VAT number and of the name and address attached to it).
  Known document: Google Ireland Limited, IE 6388047V. "valido" in VIES means
  that the number is in the archive of operators carrying out intra-EU
  transactions, not merely that it exists: an Italian P.IVA enters that archive
  only through the option of art. 35, co. 2, lett. e-bis) and co. 7-bis DPR
  633/1972, so an active Italian P.IVA without the option reads as not valid.
  The Italian checksum case runs offline and proves VIES is never queried.
* `verifica_dpa_fornitore` against the supplier's own site (art. 28 GDPR).
  Known document: the Stripe Data Processing Agreement at
  https://stripe.com/legal/dpa. The cache is redirected to a temporary
  directory, so the first call is a guaranteed miss and nothing is left in the
  user's real cache; the second call must be served from it. The refusals of
  non-public destinations (an IP address, a reserved name) run offline and must
  not resolve or request anything.

It needs the network and is excluded from the default suite:

    .venv/bin/pytest tests/unit/test_analisi_fornitori_live.py -m live -q -p no:cacheprovider -rfEs
"""

from __future__ import annotations

import asyncio
import json
import re
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import src.server  # noqa: F401  (registers every tool module first: avoids a circular import)
from src.lib import _clock
from src.lib.dpa_probe import cache as dpa_cache
from src.lib.dpa_probe import client as dpa_client
from src.tools import analisi_fornitori

pytestmark = pytest.mark.live


def _fn(tool):
    return getattr(tool, "fn", tool)


VIES = _fn(analisi_fornitori.verifica_partita_iva_vies)
DPA = _fn(analisi_fornitori.verifica_dpa_fornitore)

#: VIES userError values that mean "the service or the member state is down right
#: now" -- a temporary unavailability of the source, not a defect of the tool.
_VIES_TEMPORANEO = ("MS_UNAVAILABLE", "SERVICE_UNAVAILABLE", "TIMEOUT", "MS_MAX_CONCURRENT_REQ",
                    "GLOBAL_MAX_CONCURRENT_REQ", "non raggiungibile")


# ---------------------------------------------------------------------------
# verifica_partita_iva_vies -- reg. (UE) 904/2010 art. 31; art. 35 DPR 633/1972
# ---------------------------------------------------------------------------


def test_vies_google_ireland_reg_ue_904_2010_art_31():
    """Known document: IE 6388047V is Google Ireland Limited, Gordon House, Barrow Street, Dublin 4.

    Values read on the VIES REST API (POST check-vat-number) on 2026-09-25:
    valid=true, name "GOOGLE IRELAND LIMITED",
    address "3RD FLOOR, GORDON HOUSE, BARROW STREET, DUBLIN 4".
    """
    out = asyncio.run(VIES(partita_iva="6388047V", codice_paese="IE"))

    if out.get("disponibile") is False and any(k in (out.get("errore") or "") for k in _VIES_TEMPORANEO):
        pytest.skip(f"VIES temporaneamente non disponibile (sito_non_disponibile): {out}")

    assert out["partita_iva"] == "6388047V"
    assert out["codice_paese"] == "IE"
    assert out["checksum_valido"] is None, "il checksum locale vale solo per le P.IVA italiane"
    assert out["errore"] is None, out
    assert out["disponibile"] is True, out
    assert out["valido"] is True, out
    assert out["denominazione"] == "GOOGLE IRELAND LIMITED", out
    assert "GORDON HOUSE, BARROW STREET, DUBLIN 4" in (out["indirizzo"] or ""), out


def test_vies_checksum_italiano_errato_nessuna_chiamata_art_35_dpr_633_1972():
    """00743110158 fails the Italian check digit (00743110157 would pass): VIES is never queried."""
    with patch.object(analisi_fornitori, "check_vat", new=AsyncMock()) as vies:
        out = asyncio.run(VIES(partita_iva="00743110158"))
    vies.assert_not_awaited()
    assert out == {
        "partita_iva": "00743110158",
        "codice_paese": "IT",
        "checksum_valido": False,
        "disponibile": None,
        "valido": False,
        "denominazione": None,
        "indirizzo": None,
        "errore": "checksum non valido — VIES non interrogato",
    }


# ---------------------------------------------------------------------------
# verifica_dpa_fornitore -- art. 28 GDPR
# ---------------------------------------------------------------------------

#: Stripe localises by visitor: /legal/dpa redirects to /it/legal/dpa, /en-it/legal/dpa ...
#: The tool reports the FINAL url, so the locale segment is optional here.
_URL_DPA_STRIPE = re.compile(r"^https://stripe\.com/(?:[a-z]{2}(?:-[a-z]{2})?/)?legal/dpa/?$")


@pytest.fixture(scope="module")
def stripe(tmp_path_factory):
    """ONE network probe of stripe.com, then one call that must come from the cache."""
    cache_dir = tmp_path_factory.mktemp("dpa_cache")
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("MCP_CACHE_DIR", str(cache_dir))
        mp.delenv("LEGAL_CACHE", raising=False)
        primo = asyncio.run(DPA(dominio="stripe.com", nome_fornitore="Stripe"))
        secondo = None
        # A transient outcome is never cached: asking again would be a second probe.
        if primo["verdetto"] in dpa_cache.VERDETTI_PERSISTIBILI:
            secondo = asyncio.run(DPA(dominio="https://www.stripe.com/", nome_fornitore="Stripe"))
        file_cache = cache_dir / "dpa_probe.json"
        contenuto = json.loads(file_cache.read_text(encoding="utf-8")) if file_cache.exists() else None
    return {"primo": primo, "secondo": secondo, "cache": contenuto}


def test_dpa_stripe_dpa_dedicato_art_28_gdpr(stripe):
    """Stripe publishes a dedicated DPA (art. 28 GDPR) at https://stripe.com/legal/dpa.

    `bloccato` / `dominio_irraggiungibile` are not a "no": they mean the source
    could not be read, and the case is skipped. `non_trovato` on a vendor that
    does publish a DPA is a false negative of the tool, and fails.
    """
    r = stripe["primo"]
    if r["verdetto"] in ("bloccato", "dominio_irraggiungibile"):
        pytest.skip(f"fonte non leggibile dal probe (non vale come 'no'): {r}")
    assert r["dominio"] == "stripe.com"
    assert r["nome_fornitore"] == "Stripe"
    # Diagnosis on 2026-09-25: without an Accept-Language header Stripe geo-redirects an
    # Italian client to /it/legal/dpa, titled "Accordo sul trattamento dei dati", which
    # no strong marker of src/lib/dpa_probe/judge.py recognises; the English page
    # (/en-it/legal/dpa, "Data Processing Agreement") is judged dpa_dedicato.
    assert r["verdetto"] == "dpa_dedicato", (
        "Stripe pubblica un DPA dedicato (https://stripe.com/legal/dpa) ma la sonda risponde "
        f"{r['verdetto']!r}: {r}"
    )
    assert _URL_DPA_STRIPE.match(r["url_evidenza"] or ""), r
    assert r["errore"] is None, r


def test_dpa_stripe_cache_90_giorni(stripe):
    """First call probes (da_cache false), the second -- same domain written differently -- is cached."""
    primo, secondo = stripe["primo"], stripe["secondo"]
    if secondo is None:
        pytest.skip(f"esito transitorio non persistito, la cache non si puo' verificare: {primo}")
    oggi = _clock.today().isoformat()
    assert primo["da_cache"] is False, primo
    assert primo["verificato_il"] == oggi
    assert secondo["da_cache"] is True, secondo
    assert secondo["dominio"] == "stripe.com"
    for campo in ("verdetto", "url_evidenza", "marcatori", "evidenza", "verificato_il"):
        assert secondo[campo] == primo[campo], campo
    assert stripe["cache"] is not None and "stripe.com" in stripe["cache"], stripe["cache"]
    assert dpa_cache.TTL_GIORNI == 90


@pytest.mark.parametrize(
    ("dominio", "errore"),
    [
        ("127.0.0.1", "indirizzo IP invece di un dominio"),
        ("example.invalid", "nome locale o riservato"),
    ],
)
def test_dpa_destinazione_non_pubblica_rifiutata_senza_rete(dominio, errore, tmp_path, monkeypatch):
    """A non-public destination is refused before any DNS lookup or HTTP request, and nothing is cached.

    The probe swallows every exception, so the guards record calls instead of raising:
    a raise would come back as `errore: "AssertionError"` and hide the check.
    """
    monkeypatch.setenv("MCP_CACHE_DIR", str(tmp_path))
    monkeypatch.delenv("LEGAL_CACHE", raising=False)
    risoluzioni: list[str] = []

    async def risolvi(host):
        risoluzioni.append(host)
        return ["93.184.216.34"]

    monkeypatch.setattr(dpa_client, "_risolvi", risolvi)
    client = MagicMock()
    with patch.object(dpa_client.httpx, "AsyncClient", client):
        out = asyncio.run(DPA(dominio=dominio))

    assert out["verdetto"] == "dominio_irraggiungibile", out
    assert out["errore"] == errore, out
    assert out["da_cache"] is False
    assert out["url_evidenza"] is None and out["marcatori"] == []
    assert risoluzioni == [], "nessuna risoluzione DNS attesa"
    client.assert_not_called()
    assert not (tmp_path / "dpa_probe.json").exists(), "un rifiuto non va in cache"

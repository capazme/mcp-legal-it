"""Live smoke gate for the Corte dei conti tools (banchedati.corteconti.it, LI-054).

Tools under test: `cerca_deliberazioni_corte_conti`, `leggi_deliberazione_corte_conti`,
`ultime_deliberazioni_corte_conti` (mcp_legal_it/tools/corte_conti.py over
mcp_legal_it/lib/corte_conti/client.py).

Polite and serial: the tests run one after the other, the site's configuration is read once for
the whole module, and the source's own limit holds (one request at a time, 1 s apart). About
nine requests in all. Checked on a known act, deliberazione n. 29/2025/PREV of the Sezione
regionale di controllo per la Campania (deposited 23/01/2025, read on 2026-10-29):

* a search by words finds deliberazioni, at most five, with id and PDF link;
* the act is read by id and by number, year and section, with its full text;
* its public PDF link answers with a PDF, without credentials;
* the credentials the site hands out appear in no answer and in no stored fixture.

Needs the network, so it is excluded from the default run. Launch it with:

    .venv/bin/pytest tests/unit/test_corte_conti_live.py -m live -q -p no:cacheprovider -rfEs
"""

from __future__ import annotations

import base64
from pathlib import Path

import httpx
import pytest

import mcp_legal_it.server  # noqa: F401  (registers every tool module first)
from mcp_legal_it.lib.corte_conti import client as cc
from mcp_legal_it.tools.corte_conti import (
    cerca_deliberazioni_corte_conti,
    leggi_deliberazione_corte_conti,
    ultime_deliberazioni_corte_conti,
)

pytestmark = pytest.mark.live

ID_CAMPANIA = "SRCCAM/29/2025/PREV"
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "corte_conti"
_ANSWERS: list[str] = []


def _fn(tool):
    return getattr(tool, "fn", tool)


async def test_search_by_words():
    out = await _fn(cerca_deliberazioni_corte_conti)("rinnovo tacito")
    _ANSWERS.append(out)
    assert "deliberazioni della Corte dei conti per" in out, out[:500]
    assert out.count("\n### ") <= cc.MAX_DOCUMENTI
    assert "downloadDocument/deliberazioni_pu/" in out


async def test_read_by_id():
    out = await _fn(leggi_deliberazione_corte_conti)(ID_CAMPANIA)
    _ANSWERS.append(out)
    assert "Sezione Controllo Regione Campania, deliberazione n. 29/2025" in out, out[:500]
    assert "depositata il 23/01/2025" in out
    assert "### Testo" in out and "CORTE DEI CONTI" in out


async def test_read_by_number_year_and_section():
    out = await _fn(leggi_deliberazione_corte_conti)(numero="29", anno="2025", sezione="Campania")
    _ANSWERS.append(out)
    assert f"Corte dei conti — {ID_CAMPANIA}" in out, out[:500]


async def test_latest():
    out = await _fn(ultime_deliberazioni_corte_conti)()
    _ANSWERS.append(out)
    assert "Ultime deliberazioni depositate" in out, out[:500]
    assert 1 <= out.count("\n### ") <= cc.MAX_DOCUMENTI


async def test_the_pdf_link_is_public():
    assert cc._ACCESSO is not None, "run with the other live tests: the access is read by them"
    d = cc.Deliberazione(id_locale=ID_CAMPANIA)
    cc._link(cc._ACCESSO, d)
    # A plain client, without the credentials: the link must work for anyone who clicks it.
    async with httpx.AsyncClient(headers=cc._HEADERS, timeout=30) as client:
        async with client.stream("GET", d.url_pdf) as resp:
            assert resp.status_code == 200
            assert "application/pdf" in resp.headers.get("content-type", "")
            first = b""
            async for chunk in resp.aiter_bytes():
                first = chunk[:5]
                break
    assert first == b"%PDF-"


def test_the_credentials_appear_nowhere():
    acc = cc._ACCESSO
    assert acc is not None, "run with the other live tests: the access is read by them"
    token = acc.intestazioni()["Authorization"].split()[1]
    utente, password = base64.b64decode(token).decode().split(":", 1)
    secrets = (token, utente, password)
    # Booleans only: a failing assert must not print the values it compares.
    assert _ANSWERS and not any(s in a for s in secrets for a in _ANSWERS), "a credential is in an answer"
    leaked = [p.name for p in FIXTURES.iterdir() if any(s in p.read_text(encoding="utf-8") for s in secrets)]
    assert not leaked, f"a credential is in the fixtures: {leaked}"

"""Live smoke gate for the CONSOB tools (Bollettino, www.consob.it, Liferay portlet).

Tools under test: `cerca_delibere_consob`, `leggi_delibera_consob`, `ultime_delibere_consob`
(src/tools/consob.py over src/lib/consob/client.py).

What it checks, one real call per case on a known document:

* the Bollettino search form still offers every tipologia value and every argomento Liferay ID
  the client hard-codes (TIPOLOGIE / ARGOMENTI) — a canary that tells a portal rework apart
  from a broken tool;
* the search tool finds Delibera n. 20307 del 15/02/2018 (adoption of the Regolamento
  Intermediari) with the AAAA-MM-GG date filter actually applied (plan case 1);
* the argomento + date filter never lets a date outside the requested year through (plan case 2;
  on 2026-09-25 the Bollettino has no item tagged "Abusi di mercato" after Delibera n. 19925 del
  22/03/2017, so the expected answer is an empty list);
* the reader returns the title and the text of Delibera n. 20307 with the declared 8000-character
  truncation, and reports an unknown number (99999, HTTP 404) as an error rather than as a
  delibera;
* the "latest" tool returns five delibere in descending order of publication date, and recent;
* KNOWN DEFECT (fails on purpose until fixed): results that are not delibere (Comunicazione
  n. 13/25, Richiamo di attenzione n. 14/25, protocol-numbered comunicazioni) are labelled
  "Delibera n. <n>" with a link to /delibera-n.-<n>, which the portal answers with 404.

Needs the network, so it is excluded from the default run. Launch it with:

    .venv/bin/pytest tests/unit/test_consob_live.py -m live -q -p no:cacheprovider -rfEs
"""

from __future__ import annotations

import asyncio
import re
import time
from datetime import date, datetime

import httpx
import pytest
from bs4 import BeautifulSoup

import src.server  # noqa: F401  (registers every tool module first: avoids a circular import)
from src.lib.consob.client import _BASE, _HEADERS, _SEARCH_PATH, ARGOMENTI, TIPOLOGIE
from src.tools.consob import (
    cerca_delibere_consob,
    leggi_delibera_consob,
    ultime_delibere_consob,
)

pytestmark = pytest.mark.live

_PORTLET_PREFIX = "_it_consob_BollettinoRicercaPortlet_"
_DATE_RE = re.compile(r"\b(\d{2})/(\d{2})/(\d{4})\b")
_LINK_RE = re.compile(r"\*\*Link\*\*: \[[^\]]*\]\((https://[^)]+)\)")


def _fn(tool):
    return getattr(tool, "fn", tool)


def _run(tool, **kwargs) -> str:
    return asyncio.run(_fn(tool)(**kwargs))


def _blocchi(risultato: str) -> list[str]:
    """Split a markdown result list into its '### ' blocks (one per document)."""
    return [b for b in re.split(r"^### ", risultato, flags=re.M)[1:] if b.strip()]


def _campo(blocco: str, etichetta: str) -> str:
    m = re.search(rf"^\*\*{re.escape(etichetta)}\*\*: (.*)$", blocco, flags=re.M)
    return m.group(1).strip() if m else ""


def _data(testo: str) -> date | None:
    m = _DATE_RE.search(testo or "")
    return date(int(m.group(3)), int(m.group(2)), int(m.group(1))) if m else None


@pytest.fixture(autouse=True)
def _pausa_tra_le_chiamate():
    """Space the requests to consob.it: one page at a time, never a burst."""
    yield
    time.sleep(1.5)


# ---------------------------------------------------------------------------
# Canary on the source (not on the tool)
# ---------------------------------------------------------------------------


def test_modulo_bollettino_offre_tipologie_e_argomenti_del_client():
    """Every TIPOLOGIE value and ARGOMENTI ID must still be an <option> of the search form."""
    with httpx.Client(headers=_HEADERS, follow_redirects=True, timeout=30) as client:
        resp = client.get(_BASE + _SEARCH_PATH)
    assert resp.status_code == 200, resp.status_code
    soup = BeautifulSoup(resp.text, "lxml")

    def opzioni(nome: str) -> set[str]:
        sel = soup.find("select", attrs={"name": _PORTLET_PREFIX + nome})
        assert sel is not None, f"select {nome} sparita dal modulo del Bollettino"
        return {o.get("value", "") for o in sel.find_all("option")}

    tipologie_sito = opzioni("tipologia")
    argomenti_sito = opzioni("argomento")
    mancanti_tip = {k: v for k, v in TIPOLOGIE.items() if v not in tipologie_sito}
    mancanti_arg = {k: v for k, v in ARGOMENTI.items() if v not in argomenti_sito}
    assert not mancanti_tip, f"tipologie non piu' offerte dal Bollettino: {mancanti_tip}"
    assert not mancanti_arg, f"ID argomento non piu' offerti dal Bollettino: {mancanti_arg}"
    # The date inputs are HTML5 <input type="date">: the wire format is AAAA-MM-GG, the one the
    # tool asks for in its docstring.
    for nome in ("startDate", "endDate"):
        campo = soup.find("input", attrs={"name": _PORTLET_PREFIX + nome})
        assert campo is not None and campo.get("type") == "date", nome


# ---------------------------------------------------------------------------
# cerca_delibere_consob
# ---------------------------------------------------------------------------


def test_cerca_delibera_20307_regolamento_intermediari_febbraio_2018():
    """Plan case 1: Delibera n. 20307 del 15/02/2018 among the February 2018 delibere."""
    r = _run(
        cerca_delibere_consob,
        query="regolamento intermediari", tipologia="delibere",
        data_da="2018-02-01", data_a="2018-02-28", max_risultati=20,
    )
    assert not r.startswith("Errore"), r
    blocchi = {b.splitlines()[0].strip(): b for b in _blocchi(r)}
    assert "Delibera n. 20307" in blocchi, r
    b = blocchi["Delibera n. 20307"]
    assert "in materia di intermediari" in _campo(b, "Titolo"), b
    assert _campo(b, "Data") == "15/02/2018", b
    assert "https://www.consob.it/web/area-pubblica/-/delibera-n.-20307" in b, b
    # The AAAA-MM-GG filter is really applied: no delibera dated outside February 2018.
    fuori = [(t, _campo(x, "Data")) for t, x in blocchi.items()
             if not (date(2018, 2, 1) <= (_data(_campo(x, "Data")) or date.min) <= date(2018, 2, 28))]
    assert not fuori, f"delibere fuori dall'intervallo richiesto: {fuori}"


def test_cerca_argomento_abusi_di_mercato_2025_non_esce_dall_anno():
    """Plan case 2: argomento + date filter; no result may carry a date outside 2025.

    Verified by hand on 2026-09-25: the argomento "Abusi di mercato" (Liferay ID 4989535) is
    last assigned to Delibera n. 19925 del 22/03/2017 — recent market-abuse sanctions (e.g.
    Delibera n. 23257 del 18/09/2024) are not tagged with it — so the Bollettino itself answers
    an empty list for 2025, and so does the tool.
    """
    r = _run(
        cerca_delibere_consob,
        query="abusi di mercato", argomento="abusi_di_mercato",
        data_da="2025-01-01", data_a="2025-12-31", max_risultati=5,
    )
    assert not r.startswith("Errore"), r
    date_fuori = [d for d in (_data(_campo(b, "Data")) for b in _blocchi(r))
                  if d is not None and d.year != 2025]
    assert not date_fuori, f"date fuori dal 2025: {date_fuori}\n{r}"


def test_cerca_comunicazioni_etichetta_e_link_corretti():
    """Boundary case (enumerated tipologia "comunicazioni", advertised in the docstring).

    On 2026-09-25 the Bollettino lists, for July 2025, "Richiamo di attenzione n. 14/25" and
    "Comunicazione n. 13/25"; their real pages are /-/richiamo-di-attenzione-n-14-25-del-7-luglio-2025
    and /-/comunicazione-n-13-25-del-4-luglio-2025. The tool labels them "Delibera n. 14" and
    "Delibera n. 13" and links /delibera-n.-14 and /delibera-n.-13, both HTTP 404.
    KNOWN DEFECT: this test fails until format_result uses the href of the result.
    """
    r = _run(
        cerca_delibere_consob,
        query="", tipologia="comunicazioni",
        data_da="2025-07-01", data_a="2025-07-31", max_risultati=10,
    )
    assert not r.startswith("Errore"), r
    blocchi = _blocchi(r)
    assert any("13/25" in _campo(b, "Titolo") for b in blocchi), r

    difetti = []
    with httpx.Client(headers=_HEADERS, follow_redirects=True, timeout=30) as client:
        for b in blocchi:
            titolo = _campo(b, "Titolo")
            intestazione = b.splitlines()[0].strip()
            if not titolo.lower().startswith("delibera") and intestazione.startswith("Delibera n."):
                difetti.append(f"{titolo[:60]!r} presentato come {intestazione!r}")
            m = _LINK_RE.search(b)
            assert m, b
            stato = client.get(m.group(1)).status_code
            if stato != 200:
                difetti.append(f"{titolo[:60]!r}: link {m.group(1)} -> HTTP {stato}")
            time.sleep(1.0)
    assert not difetti, "risultati non-delibera etichettati e linkati come delibere:\n" + "\n".join(difetti)


# ---------------------------------------------------------------------------
# leggi_delibera_consob
# ---------------------------------------------------------------------------


def test_leggi_delibera_20307_regolamento_intermediari():
    """Plan case 1: title and text of Delibera n. 20307, truncated at 8000 characters."""
    r = _run(leggi_delibera_consob, numero="20307")
    assert not r.startswith("Errore"), r
    assert r.startswith("# Delibera n. 20307"), r[:200]
    assert "**Link**: [Delibera n. 20307](https://www.consob.it/web/area-pubblica/-/delibera-n.-20307)" in r
    # The Bollettino writes "d.lgs." where the plan paraphrased "decreto legislativo".
    assert ("Regolamento recante norme di attuazione del d.lgs. 24 febbraio 1998, n. 58 "
            "in materia di intermediari") in r, r[:1500]
    assert "La Commissione Nazionale per le Società e la Borsa" in r
    assert "Bollettino « Indietro" not in r[:300], "breadcrumb del portale non rimosso"
    m = re.search(r"\[Testo troncato a 8000 caratteri su (\d+) totali\]", r)
    assert m and int(m.group(1)) > 8000, r[-300:]


def test_leggi_delibera_inesistente_99999_segnala_errore():
    """Plan case 2: an unknown number is an explicit error, never portal text shown as a delibera."""
    r = _run(leggi_delibera_consob, numero="99999")
    assert r.startswith("Errore nel recupero della delibera CONSOB n. 99999"), r[:300]
    assert "404" in r, r
    assert "# Delibera n. 99999" not in r, r[:300]


# ---------------------------------------------------------------------------
# ultime_delibere_consob
# ---------------------------------------------------------------------------


def test_ultime_cinque_delibere_in_ordine_di_pubblicazione():
    """Plan case: five latest delibere with number, title, dates; newest publication first.

    The Bollettino orders by publication date, not by the date of the delibera (e.g. Delibera
    n. 24121 del 08/09/2026, published 18/09/2026, precedes n. 24132 del 15/09/2026, published
    16/09/2026): the monotonic field is "Pubblicazione".
    """
    r = _run(ultime_delibere_consob, tipologia="delibere", max_risultati=5)
    assert not r.startswith("Errore"), r
    blocchi = _blocchi(r)
    assert len(blocchi) == 5, r
    pubblicazioni = []
    for b in blocchi:
        intestazione = b.splitlines()[0].strip()
        assert re.fullmatch(r"Delibera n\. \d+(?:-\d+)?", intestazione), intestazione
        assert _campo(b, "Titolo").startswith(intestazione), b
        assert _data(_campo(b, "Data")) is not None, b
        pub = _data(_campo(b, "Pubblicazione"))
        assert pub is not None, b
        pubblicazioni.append(pub)
    assert pubblicazioni == sorted(pubblicazioni, reverse=True), pubblicazioni
    # The Bollettino is published several times a month: the newest item cannot be older than
    # 45 days (wide on purpose, to survive the August slowdown).
    assert (datetime.now().date() - pubblicazioni[0]).days <= 45, pubblicazioni[0]


def test_ultime_comunicazioni_non_etichettate_come_delibere():
    """Same defect as the search tool, reached through the advertised "comunicazioni" filter.

    On 2026-09-25 the three latest comunicazioni are n. 0117520 dell'11/12/2025, n. 16/25 del
    04/12/2025 and n. 0086303 del 10/09/2025; the tool shows them as "Delibera n. 0117520",
    "Delibera n. 16", "Delibera n. 0086303", with /delibera-n.-<n> links that answer 404.
    KNOWN DEFECT: this test fails until format_result uses the href of the result.
    """
    r = _run(ultime_delibere_consob, tipologia="comunicazioni", max_risultati=3)
    assert not r.startswith("Errore"), r
    difetti = [
        f"{_campo(b, 'Titolo')[:60]!r} presentato come {b.splitlines()[0].strip()!r}"
        for b in _blocchi(r)
        if not _campo(b, "Titolo").lower().startswith("delibera")
        and b.splitlines()[0].strip().startswith("Delibera n.")
    ]
    assert not difetti, "comunicazioni etichettate come delibere:\n" + "\n".join(difetti)

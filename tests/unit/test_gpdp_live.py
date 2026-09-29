"""Live smoke gate for the Garante privacy tools (www.garanteprivacy.it, Liferay portlet).

Tools under test: `cerca_provvedimenti_garante`, `leggi_provvedimento_garante`,
`ultimi_provvedimenti_garante` (src/tools/gpdp.py over src/lib/gpdp/client.py).

What it checks, one real call per case on a known document (reads are cached per session):

* canary on the search portlet: the date inputs are HTML5 ``<input type="date">`` (the portal
  expects AAAA-MM-GG on the wire) and the tipologia tree still carries the leaf names the
  docstrings hint at ("Linee guida", "Ordinanza ingiunzione o revoca", "Parere del Garante",
  "Prescrizioni del Garante") under the parent "Provvedimenti";
* the search finds DocWeb 9677876 (Linee guida cookie, 10/06/2021) and DocWeb 9870832
  (Provvedimento del 30 marzo 2023, limitazione provvisoria ChatGPT) when the dates travel in the
  format the portal accepts, with the results in descending date order inside the range;
* the reader returns DocWeb 9677876 with title, registry number (n. 231 del 10 giugno 2021) and
  the declared 6000-character truncation, and DocWeb 9870832 as the OpenAI/ChatGPT provvedimento;
* the "latest" tool returns five documents in descending date order, none after today, recent.

Defects found on 2026-09-25 and fixed in this branch (each case below is the regression guard):

* dates: the tools document GG/MM/AAAA but the portal reads only AAAA-MM-GG, so the client now
  converts them (any other format is an explicit error, not an empty result);
* tipologia: the client no longer filters locally on the leaf label; it sends the portal's own
  node ids (`idsTipologia`), and "provvedimento" expands to the "Provvedimenti" node and all its
  descendants, which the portal does not do on its own;
* `leggi_provvedimento_garante`: the docstring labels of 9870832 and 10000069 were wrong, an
  unavailable DocWeb id is an error (not a pseudo-document), links are absolute and the page
  toolbar is stripped from the text.

Needs the network, so it is excluded from the default run. Launch it with:

    .venv/bin/pytest tests/unit/test_gpdp_live.py -m live -q -p no:cacheprovider -rfEs
"""

from __future__ import annotations

import asyncio
import functools
import inspect
import json
import re
import time
from datetime import date

import httpx
import pytest
from bs4 import BeautifulSoup

import src.server  # noqa: F401  (registers every tool module first: avoids a circular import)
from src.lib import _clock
from src.lib.gpdp.client import (
    _BASE,
    _HEADERS,
    _SEARCH_PATH,
    TIPOLOGIE,
    _build_search_params,
    tipologie_provvedimenti,
)
from src.tools.gpdp import (
    cerca_provvedimenti_garante,
    leggi_provvedimento_garante,
    ultimi_provvedimenti_garante,
)

pytestmark = pytest.mark.live

_PREFIX = "_g_gpdp5_search_GGpdp5SearchPortlet_"
_DATE_RE = re.compile(r"\b(\d{2})/(\d{2})/(\d{4})\b")
_DOCWEB_URL = "https://www.garanteprivacy.it/web/guest/home/docweb/-/docweb-display/docweb/{}"


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


def _docweb_ids(risultato: str) -> list[int]:
    return [int(x) for x in re.findall(r"\*\*DocWeb\*\*: \[(\d+)\]", risultato)]


@functools.lru_cache(maxsize=None)
def _leggi(docweb_id: int) -> str:
    """One fetch per DocWeb id per session, shared by the tests that read the same document."""
    time.sleep(2)
    return _run(leggi_provvedimento_garante, docweb_id=docweb_id)


@pytest.fixture(autouse=True)
def _pausa_tra_le_chiamate():
    """Space the requests to garanteprivacy.it: one page at a time, never a burst."""
    yield
    time.sleep(2)


# ---------------------------------------------------------------------------
# Canary: the portlet the client scrapes
# ---------------------------------------------------------------------------

def test_canary_modulo_ricerca_date_iso_e_tipologie():
    """The search form uses <input type=date> and the tipologia tree still has the known leaves."""
    params = _build_search_params(query="", data_da="", data_a="")
    resp = httpx.get(_BASE + _SEARCH_PATH, params=params, headers=_HEADERS,
                     follow_redirects=True, timeout=30)
    assert resp.status_code == 200
    soup = BeautifulSoup(resp.text, "lxml")
    for campo in ("dataInizio", "dataFine"):
        el = soup.find("input", attrs={"name": _PREFIX + campo})
        assert el is not None, f"campo {campo} scomparso dal modulo"
        assert el.get("type") == "date", f"{campo}: type={el.get('type')!r}"
        # an HTML5 date input always submits AAAA-MM-GG (empty here: no date was requested)
        assert re.fullmatch(r"(\d{4}-\d{2}-\d{2})?", el.get("value") or ""), el.get("value")

    m = re.search(r"\$\('#jsTreeTipologia'\)\.jstree\(\{\s*'core'\s*:\s*\{\s*'data'\s*:\s*(\[.*?\])\s*,",
                  resp.text, re.S)
    assert m, "albero delle tipologie non trovato nella pagina"
    nodi = json.loads(m.group(1))
    per_id = {n["id"]: n for n in nodi}
    nome = lambda n: re.sub(r"\(\d+\)$", "", n["text"]).strip()  # noqa: E731
    radice = {nome(n): n["id"] for n in nodi if n["parent"] == "#"}
    assert "Provvedimenti" in radice, sorted(radice)
    figli = {nome(n) for n in nodi if n["parent"] == radice["Provvedimenti"]}
    for foglia in ("Linee guida", "Ordinanza ingiunzione o revoca", "Parere del Garante",
                   "Prescrizioni del Garante"):
        assert foglia in figli, (foglia, sorted(figli))
    # The client keeps a copy of this tree (TIPOLOGIE) to build `idsTipologia`: it must match
    # the portal exactly, otherwise "provvedimento" would silently miss or add a node.
    live = {n["id"]: (nome(n), "" if n["parent"] == "#" else n["parent"]) for n in nodi}
    copia = {i: (name, parent) for i, name, parent in TIPOLOGIE}
    assert copia == live, {
        "mancanti_nel_client": sorted(set(live) - set(copia)),
        "in_piu_nel_client": sorted(set(copia) - set(live)),
        "diversi": sorted(i for i in set(live) & set(copia) if live[i] != copia[i]),
    }


# ---------------------------------------------------------------------------
# cerca_provvedimenti_garante
# ---------------------------------------------------------------------------

def test_cerca_linee_guida_cookie_date_gg_mm_aaaa_documentate():
    """Plan case 1 as documented (GG/MM/AAAA): DocWeb 9677876 must be among the results.

    Regression: the portal ignores GG/MM/AAAA, so the client converts it to AAAA-MM-GG.
    """
    r = _run(cerca_provvedimenti_garante, query="linee guida cookie",
             data_da="01/06/2021", data_a="30/06/2021", max_risultati=10)
    assert 9677876 in _docweb_ids(r), r[:600]


def test_cerca_linee_guida_cookie_date_iso_trova_9677876():
    """Same search with the dates in the format the portal accepts: the tool chain works."""
    r = _run(cerca_provvedimenti_garante, query="linee guida cookie",
             data_da="2021-06-01", data_a="2021-06-30", max_risultati=10)
    blocchi = _blocchi(r)
    assert blocchi, r[:600]
    trovato = [b for b in blocchi if "[9677876]" in b]
    assert trovato, r[:1500]
    b = trovato[0]
    assert b.startswith("Linee guida cookie e altri strumenti di tracciamento - 10 giugno 2021"), b[:200]
    assert _campo(b, "Data") == "10/06/2021"
    assert _campo(b, "Tipo") == "Linee guida"
    for blocco in blocchi:
        d = _data(_campo(blocco, "Data"))
        assert d is None or date(2021, 6, 1) <= d <= date(2021, 6, 30), blocco[:200]


def test_cerca_openai_chatgpt_ordinato_per_data_trova_9870832():
    """Query + ISO dates: 9870832 (30/03/2023) is found, results in descending date order."""
    r = _run(cerca_provvedimenti_garante, query="OpenAI ChatGPT",
             data_da="2023-03-01", data_a="2023-04-30", max_risultati=20)
    blocchi = _blocchi(r)
    assert len(blocchi) >= 11, r[:600]
    date_ = [_data(_campo(b, "Data")) for b in blocchi]
    assert all(date_), date_
    assert date_ == sorted(date_, reverse=True), date_
    assert all(date(2023, 3, 1) <= d <= date(2023, 4, 30) for d in date_), date_
    b = next((b for b in blocchi if "[9870832]" in b), "")
    assert b, r[:2000]
    assert b.startswith("Provvedimento del 30 marzo 2023"), b[:200]
    assert _campo(b, "Data") == "30/03/2023"
    # the portal's leaf tipologia for the ChatGPT limitation order
    assert _campo(b, "Tipo") == "Prescrizioni del Garante"


def test_cerca_openai_chatgpt_tipologia_provvedimento():
    """Plan case 2 as documented: tipologia "provvedimento" must keep the 30/03/2023 order.

    Regression: its tipologia is "Prescrizioni del Garante", a child of "Provvedimenti"; the old
    local substring filter dropped it. Both orders against OpenAI (9870832 of 30/03/2023 and
    9874702 of 11/04/2023) are expected.
    """
    r = _run(cerca_provvedimenti_garante, query="OpenAI ChatGPT",
             data_da="01/03/2023", data_a="30/04/2023", tipologia="provvedimento")
    ids = _docweb_ids(r)
    assert 9870832 in ids, r[:600]
    assert 9874702 in ids, r[:600]
    famiglia = set(tipologie_provvedimenti()) | {"Provvedimenti"}
    for b in _blocchi(r):
        assert _campo(b, "Tipo") in famiglia, b[:200]


# ---------------------------------------------------------------------------
# leggi_provvedimento_garante
# ---------------------------------------------------------------------------

def test_leggi_linee_guida_cookie_9677876():
    """Plan case 1: title, registry number, body and the declared 6000-character truncation."""
    r = _leggi(9677876)
    assert not r.startswith("Errore"), r[:300]
    prima = r.splitlines()[0]
    assert prima == "# Linee guida cookie e altri strumenti di tracciamento - 10 giugno 2021", prima
    assert "[9677876]" in r
    assert "[doc. web n. 9677876]" in r
    assert "n. 231 del 10 giugno 2021" in r
    assert "Gazzetta Ufficiale n. 163 del 9 luglio 2021" in r
    m = re.search(r"\[Testo troncato a 6000 caratteri su (\d+) totali\]", r)
    assert m, r[-300:]
    assert int(m.group(1)) > 6000


def test_leggi_9870832_provvedimento_chatgpt_30_marzo_2023():
    """Plan case 2: DocWeb 9870832 is the 30/03/2023 order against OpenAI on ChatGPT."""
    r = _leggi(9870832)
    assert not r.startswith("Errore"), r[:300]
    assert r.splitlines()[0] == "# Provvedimento del 30 marzo 2023", r[:200]
    assert "[doc. web n. 9870832]" in r
    assert "n. 112 del 30 marzo 2023" in r
    assert "OpenAI" in r and "ChatGPT" in r
    assert "Linee guida" not in r.splitlines()[0]


def test_leggi_etichette_esempi_docstring():
    """Every DocWeb example in the docstring must resolve to a document matching its label.

    Regression: 9870832 was labelled "Linee guida AI 2023" (it is the ChatGPT order of
    30/03/2023) and 10000069 "Provvedimento ChatGPT 2023" (not available on the portal).
    """
    doc = inspect.getdoc(_fn(leggi_provvedimento_garante)) or ""
    esempi = {int(i): lab.strip() for i, lab in re.findall(r"^- (\d{7,9}): (.+)$", doc, flags=re.M)}
    assert 9677876 in esempi, doc
    errori = []
    for docweb_id, etichetta in esempi.items():
        r = _leggi(docweb_id)
        titolo = r.splitlines()[0] if r else ""
        if "non è disponibile" in r or r.startswith("Errore") or titolo.startswith("# Documento DocWeb"):
            errori.append(f"{docweb_id} ({etichetta!r}): documento non disponibile")
        elif etichetta.lower().startswith("linee guida") and "linee guida" not in titolo.lower():
            errori.append(f"{docweb_id} ({etichetta!r}): il titolo e' {titolo!r}")
        elif etichetta.lower().startswith("provvedimento") and "provvedimento" not in titolo.lower():
            errori.append(f"{docweb_id} ({etichetta!r}): il titolo e' {titolo!r}")
    assert not errori, errori


def test_leggi_id_non_disponibile_e_un_errore():
    """An unavailable DocWeb id must come back as an error, not as a pseudo-document.

    Regression: the tool used to answer "# Documento DocWeb 10000069 ... Il contenuto o il file
    richiesto non è disponibile", formatted like a real document with a DocWeb link.
    """
    r = _leggi(10000069)
    assert r.startswith("Errore: DocWeb 10000069 non disponibile"), r[:300]
    assert "non è disponibile" in r, r[:300]  # the portal's own message
    assert not r.startswith("# Documento DocWeb"), r[:300]


def test_leggi_link_docweb_assoluto():
    """The DocWeb link must be absolute (plan case 1 expects the garanteprivacy.it URL).

    Regression: format_full/format_result used to emit the path only (/web/guest/home/docweb/...).
    """
    r = _leggi(9677876)
    assert _DOCWEB_URL.format(9677876) in r, r.splitlines()[1]


# ---------------------------------------------------------------------------
# ultimi_provvedimenti_garante
# ---------------------------------------------------------------------------

def test_ultimi_cinque_in_ordine_di_data():
    """Plan case 1: five documents, descending dates, none after today, the first recent."""
    r = _run(ultimi_provvedimenti_garante, max_risultati=5)
    blocchi = _blocchi(r)
    assert len(blocchi) == 5, r[:600]
    oggi = _clock.today()
    date_ = [_data(_campo(b, "Data")) for b in blocchi]
    assert all(date_), date_
    assert date_ == sorted(date_, reverse=True), date_
    assert all(d <= oggi for d in date_), date_
    assert (oggi - date_[0]).days <= 30, date_[0]
    for b in blocchi:
        assert re.search(r"\*\*DocWeb\*\*: \[\d+\]\(", b), b[:200]


def test_ultimi_tipologia_provvedimento():
    """Plan case 2: tipologia "provvedimento" (docstring example) must return provvedimenti.

    Regression: the filter used to run locally on the 15 most recent cards (press reviews,
    news, podcasts on 2026-09-25) and "provvedimento" matched no leaf tipologia, so the tool
    answered "Nessun provvedimento recente trovato" although the portal published an
    "Ordinanza ingiunzione o revoca" on 06/08/2026 and "Provvedimenti" on 14/07/2026.
    "Provvedimenti" is a family of tipologie: every card must carry the parent node or one of
    its children, in descending date order. (The earlier assertion looked for the substring
    "provvediment" in the leaf label, which is wrong for children such as "Ordinanza
    ingiunzione o revoca" or "Prescrizioni del Garante".)
    """
    r = _run(ultimi_provvedimenti_garante, tipologia="provvedimento", max_risultati=5)
    blocchi = _blocchi(r)
    assert len(blocchi) == 5, r[:300]
    famiglia = set(tipologie_provvedimenti()) | {"Provvedimenti"}
    for b in blocchi:
        assert _campo(b, "Tipo") in famiglia, b[:200]
    date_ = [_data(_campo(b, "Data")) for b in blocchi]
    assert date_ == sorted(date_, reverse=True), date_
    assert all(d <= _clock.today() for d in date_), date_

"""Live smoke gate for the Gazzetta Ufficiale tools (www.gazzettaufficiale.it).

Tools under test (src/tools/gazzetta.py over src/lib/gazzetta/client.py):
`cerca_gazzetta_ufficiale`, `leggi_atto_gazzetta`, `scarica_pdf_gazzetta`,
`sommario_gazzetta`, `ultime_gazzette`.

What it checks, one real call per case on a known, permanently published document:

* D.Lgs. 10 ottobre 2022 n. 149 (riforma Cartabia del processo civile), codice redazionale
  22G00158, GU Serie generale n. 243 del 17-10-2022, S.O. n. 38 — search by title, search with
  the "tipo provvedimento" filter (plan case 1), ELI metadata (plan case 1 of leggi_atto_gazzetta);
* D.P.R. 13 gennaio 2025 n. 12 (plan case 2 of the search): its GU title is "tabella unica del
  valore pecuniario ... art. 138, comma 1, lettera b)" (25G00019, GU n. 40 del 18-02-2025,
  S.O. n. 4, read on 2026-09-25), so a title search on "menomazioni integrità psicofisica" has
  no match at the source either;
* GU Serie generale n. 205 del 4-9-2018 (D.Lgs. 101/2018, 18G00129): sommario and official PDF;
* D.M. Difesa 9 agosto 2018 (18A05725), a two-article atto: full text assembled article by article;
* 4a Serie speciale Concorsi ed esami n. 10 del 6-2-2026 and the 1a Serie speciale atto 26C00185
  (ordinanza n. 230 del 2026, Tribunale di Verona): the special series, whose ELI path segment is
  s1..s5 (checked on 2026-09-25), not "sg";
* the RSS feeds: the latest Serie generale atti and the 1a Serie speciale (Corte costituzionale).

Canaries on the source (not on the tool) pin down the site's own behaviour the tool relies on:
a search with exactly one hit answers with a redirect to that atto's page; the result pages are
numbered from 1 (page 0 and page 1 are the same page); the RSS feeds S1..S5 follow the official
numbering of the special series (1a Corte costituzionale, 2a Unione europea, 3a Regioni,
4a Concorsi, 5a Contratti pubblici).

Tests that fail here record a genuine defect of the tool (see the per-test docstrings), not a
source outage: the canaries tell the two apart.

Needs the network, so it is excluded from the default run. Launch it with:

    .venv/bin/pytest tests/unit/test_gazzetta_live.py -m live -q -p no:cacheprovider -rfEs
"""

from __future__ import annotations

import asyncio
import re
import shutil
import subprocess
import tempfile
import time
from datetime import date, datetime
from pathlib import Path

import httpx
import pytest

import src.server  # noqa: F401  (registers every tool module first: avoids a circular import)
from src.lib.gazzetta.client import (
    _BASE,
    _HEADERS,
    _RSS_HEADERS,
    _build_search_data,
    _parse_search_results,
)
from src.tools.gazzetta import (
    cerca_gazzetta_ufficiale,
    leggi_atto_gazzetta,
    scarica_pdf_gazzetta,
    sommario_gazzetta,
    ultime_gazzette,
)

pytestmark = pytest.mark.live

# D.Lgs. 10 ottobre 2022, n. 149 — GU Serie generale n. 243 del 17-10-2022, S.O. n. 38.
DLGS_149_2022 = "22G00158"
# D.Lgs. 10 agosto 2018, n. 101 — GU Serie generale n. 205 del 4-9-2018.
DLGS_101_2018 = "18G00129"
# D.M. Difesa 9 agosto 2018 (paghe nette allievi scuole militari) — same fascicolo, two articles.
DM_DIFESA_2018 = "18A05725"
# 1a Serie speciale, GU n. 38 del 23-9-2026: ordinanza n. 230 (Tribunale di Verona, 4 agosto 2025).
ORDINANZA_S1 = "26C00185"

_CODICE_RE = re.compile(r"\*\*Codice redazionale\*\*: ([0-9]{2}[A-Z][0-9A-Z]+)")
_PUB_RE = re.compile(r"\*\*Pubblicazione\*\*: (\d{4}-\d{2}-\d{2})")


def _fn(tool):
    return getattr(tool, "fn", tool)


def _run(tool, **kwargs) -> str:
    return asyncio.run(_fn(tool)(**kwargs))


def _blocchi(risultato: str) -> list[str]:
    """Split a markdown result list into its '### ' blocks (one per atto)."""
    return [b for b in re.split(r"^### ", risultato, flags=re.M)[1:] if b.strip()]


def _get(url: str, *, rss: bool = False) -> httpx.Response:
    with httpx.Client(
        timeout=httpx.Timeout(60.0, connect=15.0),
        headers=_RSS_HEADERS if rss else _HEADERS,
        follow_redirects=True,
    ) as client:
        return client.get(url)


def _pdf_head(url: str) -> tuple[int, str, str, bytes]:
    """(status, final url, content-type, first bytes) without downloading the whole file."""
    with httpx.Client(
        timeout=httpx.Timeout(60.0, connect=15.0), headers=_HEADERS, follow_redirects=True,
    ) as client:
        with client.stream("GET", url) as resp:
            first = b""
            for chunk in resp.iter_bytes():
                first += chunk
                if len(first) >= 1024:
                    break
            return resp.status_code, str(resp.url), resp.headers.get("content-type", ""), first


# ---------------------------------------------------------------------------
# One real call per tool case, shared by the asserts that read it
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def cerca_per_titolo() -> str:
    return _run(cerca_gazzetta_ufficiale, titolo="processo civile", anno_da="2022", anno_a="2022")


@pytest.fixture(scope="module")
def metadati_dlgs_149() -> str:
    return _run(
        leggi_atto_gazzetta, codice_redazionale=DLGS_149_2022,
        data_pubblicazione="2022-10-17", solo_metadati=True,
    )


@pytest.fixture(scope="module")
def sommario_205_2018() -> str:
    return _run(sommario_gazzetta, numero_gazzetta="205", data_pubblicazione="2018-09-04")


# ---------------------------------------------------------------------------
# Canaries on the source (not on the tool)
# ---------------------------------------------------------------------------

def test_fonte_ricerca_con_un_solo_risultato_reindirizza_all_atto():
    """The GU search answers a query with exactly one hit by redirecting to that atto's page.

    Plan case 1 of cerca_gazzetta_ufficiale (title "processo civile", tipo "DECRETO LEGISLATIVO",
    2022) matches only the D.Lgs. 149/2022: the site does not render a result list, it redirects
    to caricaDettaglioAtto for 22G00158.
    """
    with httpx.Client(timeout=httpx.Timeout(30.0, connect=10.0), headers=_HEADERS,
                      follow_redirects=True) as client:
        client.get(_BASE + "/eli/ricerca")
        data = _build_search_data(
            titolo="processo civile", descrizione_tipo_provvedimento="DECRETO LEGISLATIVO",
            anno_da="2022", anno_a="2022",
        )
        resp = client.post(_BASE + "/do/ricerca/atto/serie_generale/originario/0", data=data)
    assert resp.status_code == 200
    assert "caricaDettaglioAtto" in str(resp.url), resp.url
    assert f"codiceRedazionale={DLGS_149_2022}" in str(resp.url), resp.url
    assert "Risultati della ricerca" not in resp.text


def test_fonte_pagine_dei_risultati_numerate_da_uno():
    """Result pages are 1-based: /originario/0 and /originario/1 render the same first page.

    The site's own pager links a two-page result set as .../originario/1 and .../originario/2.
    """
    with httpx.Client(timeout=httpx.Timeout(30.0, connect=10.0), headers=_HEADERS,
                      follow_redirects=True) as client:
        client.get(_BASE + "/eli/ricerca")
        data = _build_search_data(titolo="processo civile", anno_da="2022", anno_a="2022")
        pagine = []
        for page in (0, 1, 2):
            resp = client.post(
                _BASE + f"/do/ricerca/atto/serie_generale/originario/{page}", data=data,
            )
            pagine.append([r.codice_redazionale for r in _parse_search_results(resp.text)])
            time.sleep(1)
    assert DLGS_149_2022 in pagine[0], pagine
    assert pagine[0] == pagine[1], pagine
    assert pagine[2] == [], pagine


def test_fonte_feed_rss_seguono_la_numerazione_ufficiale_delle_serie_speciali():
    """The RSS feeds S1..S5 carry the official numbering of the special series.

    1a Corte costituzionale, 2a Unione europea, 3a Regioni, 4a Concorsi ed esami,
    5a Contratti pubblici (channel titles read on 2026-09-25).
    """
    attesi = {
        "S1": "1a Serie Speciale - Corte Costituzionale",
        "S2": "2a Serie Speciale - Unione Europea",
        "S3": "3a Serie Speciale - Regioni",
        "S4": "4a Serie Speciale - Concorsi",
        "S5": "5a Serie Speciale - Contratti",
    }
    for code, titolo in attesi.items():
        resp = _get(f"{_BASE}/rss/{code}", rss=True)
        assert resp.status_code == 200, (code, resp.status_code)
        canale = re.search(r"<channel>.*?<title>(.*?)</title>", resp.text, re.S)
        assert canale and titolo.lower() in canale.group(1).lower(), (code, canale and canale.group(1))
        time.sleep(1)


# ---------------------------------------------------------------------------
# cerca_gazzetta_ufficiale
# ---------------------------------------------------------------------------

def test_cerca_per_titolo_trova_il_dlgs_149_2022(cerca_per_titolo):
    """Title search "processo civile" (2022) returns the D.Lgs. 149/2022 with its GU estremi."""
    r = cerca_per_titolo
    assert "Errore" not in r, r
    assert DLGS_149_2022 in r, r
    assert "DECRETO LEGISLATIVO 10 ottobre 2022, n. 149" in r, r
    assert "GU n.243 del 17-10-2022" in r, r
    assert "Suppl. Ordinario n. 38" in r, r
    assert "**Pubblicazione**: 2022-10-17" in r, r


def test_cerca_non_ripete_gli_stessi_atti(cerca_per_titolo):
    """Each atto appears once. DEFECT: the tool pages from /originario/0, but the site numbers
    pages from 1, so page 0 and page 1 are the same page and every result set smaller than
    `max_risultati` is listed twice ("Trovati 2 atti" followed by four blocks)."""
    blocchi = _blocchi(cerca_per_titolo)
    codici = [m.group(1) for b in blocchi for m in [_CODICE_RE.search(b)] if m]
    assert len(codici) == len(set(codici)), codici


def test_cerca_con_tipo_provvedimento_caso_piano_1():
    """Plan case 1: title "processo civile", tipo "DECRETO LEGISLATIVO", 2022.

    The source finds exactly one atto (see the redirect canary). DEFECT: the tool parses only
    result lists, so a single hit, which the site answers with the atto page, is reported as
    "Nessun atto trovato".
    """
    r = _run(
        cerca_gazzetta_ufficiale, titolo="processo civile",
        tipo_provvedimento="DECRETO LEGISLATIVO", anno_da="2022", anno_a="2022",
    )
    assert DLGS_149_2022 in r, r


def test_cerca_caso_piano_2_titolo_senza_menomazioni():
    """Plan case 2: title "menomazioni integrità psicofisica", 2025.

    The D.P.R. 13 gennaio 2025 n. 12 (25G00019) is titled "tabella unica del valore pecuniario
    ... art. 138, comma 1, lettera b)": the source has no 2025 title with those words, so a clean
    "no results" (not an error) is the correct answer.
    """
    r = _run(
        cerca_gazzetta_ufficiale, titolo="menomazioni integrità psicofisica",
        anno_da="2025", anno_a="2025",
    )
    assert "non raggiungibile" not in r, r
    assert "Nessun atto trovato" in r, r


# ---------------------------------------------------------------------------
# leggi_atto_gazzetta
# ---------------------------------------------------------------------------

def test_leggi_metadati_eli_del_dlgs_149_2022(metadati_dlgs_149):
    """Plan case 1: ELI metadata (type, date of the act, publication date, permalink)."""
    r = metadati_dlgs_149
    assert "Errore" not in r, r
    assert "**Tipo**: DECRETO_LEGISLATIVO" in r, r
    assert "**Data atto**: 2022-10-10" in r, r
    assert "**Pubblicazione**: 2022-10-17" in r, r
    assert f"https://www.gazzettaufficiale.it/eli/id/2022/10/17/{DLGS_149_2022}/sg" in r, r
    assert "Solo metadati" in r, r


def test_leggi_metadati_riportano_l_oggetto_dell_atto(metadati_dlgs_149):
    """The header carries the atto's title. DEFECT: `_parse_atto_header` looks for classes
    (titoloAtto, emettitore, tipo_provvedimento) that the ELI page does not use — the page puts
    the estremi and the oggetto in h2.consultazione — so the result is headed "# Atto 22G00158"
    and never says what the act is about."""
    assert "Attuazione della legge 26 novembre 2021, n. 206" in metadati_dlgs_149, metadati_dlgs_149


def test_leggi_data_in_formato_errato_caso_piano_2():
    """Plan case 2: a date not in YYYY-MM-DD is a bad input, reported as such (no network)."""
    r = _run(leggi_atto_gazzetta, codice_redazionale=DLGS_149_2022, data_pubblicazione="17/10/2022")
    assert "data non valida" in r.lower(), r
    assert "non raggiungibile" not in r, r


def test_leggi_testo_integrale_di_un_atto_breve():
    """Full text assembled article by article (D.M. Difesa 9 agosto 2018, two articles)."""
    r = _run(leggi_atto_gazzetta, codice_redazionale=DM_DIFESA_2018, data_pubblicazione="2018-09-04")
    assert "Errore" not in r and "Testo non disponibile" not in r, r
    assert "**Tipo**: DECRETO" in r, r
    assert "**Data atto**: 2018-08-09" in r, r
    assert "IL MINISTRO DELLA DIFESA" in r, r
    assert "Art. 1" in r and "Art. 2" in r, r
    assert "euro 3,83" in r, r
    assert len(r) > 1500, len(r)


def test_leggi_atto_di_serie_speciale():
    """A 1a Serie speciale atto (ordinanza n. 230/2026, 26C00185).

    DEFECT: the permalink is always built with "/sg" (the right segment is "/s1": the "/sg"
    page does not contain the atto) and the text is harvested only from caricaArticolo links,
    while for the special series vediMenuHTML carries the text inline: the tool returns
    "Testo non disponibile" with empty metadata.
    """
    r = _run(
        leggi_atto_gazzetta, codice_redazionale=ORDINANZA_S1,
        data_pubblicazione="2026-09-23", serie="corte_costituzionale",
    )
    assert "Testo non disponibile" not in r, r
    assert "TRIBUNALE ORDINARIO DI VERONA" in r.upper(), r


# ---------------------------------------------------------------------------
# scarica_pdf_gazzetta
# ---------------------------------------------------------------------------

def test_pdf_del_fascicolo_205_2018_caso_piano_1():
    """Plan case 1: the URL is the official PDF of GU Serie generale n. 205 del 4-9-2018."""
    r = _run(scarica_pdf_gazzetta, numero_gazzetta="205", data_pubblicazione="2018-09-04")
    url = "https://www.gazzettaufficiale.it/eli/gu/2018/09/04/205/sg/pdf"
    assert url in r, r

    resp = _get(url)
    assert resp.status_code == 200, resp.status_code
    assert resp.headers.get("content-type", "").startswith("application/pdf"), resp.headers
    assert resp.content[:5] == b"%PDF-", resp.content[:20]
    assert len(resp.content) > 1_000_000, len(resp.content)

    pdftotext = shutil.which("pdftotext")
    if pdftotext:  # optional: read the masthead of page 1 when poppler is installed
        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp) / "gu.pdf"
            pdf.write_bytes(resp.content)
            prima = subprocess.run(
                [pdftotext, "-f", "1", "-l", "1", str(pdf), "-"],
                capture_output=True, text=True, timeout=60,
            ).stdout
        assert "Numero 205" in prima, prima[:500]
        assert "4 settembre 2018" in prima, prima[:500]
        assert "DECRETO LEGISLATIVO 10 agosto 2018, n. 101" in prima, prima[:1500]


def test_pdf_data_in_formato_errato_caso_piano_2():
    """Plan case 2: a malformed date is a bad input. DEFECT: `_scarica_pdf_gazzetta_impl`
    classifies the ValueError as `source_down`, so the user reads "gazzetta_ufficiale non
    raggiungibile" for a typo in the date."""
    r = _run(scarica_pdf_gazzetta, numero_gazzetta="205", data_pubblicazione="04/09/2018")
    assert "data non valida" in r.lower(), r
    assert "non raggiungibile" not in r, r


def test_pdf_serie_concorsi_caso_piano_3():
    """Plan case 3: 4a Serie speciale Concorsi n. 10 del 6-2-2026.

    DEFECT: `serie` is ignored and the URL always ends in "/sg/pdf"; the site answers it with
    its "Il pdf selezionato non é stato trovato" page. The official PDF is ".../s4/pdf".
    """
    r = _run(
        scarica_pdf_gazzetta, numero_gazzetta="10", data_pubblicazione="2026-02-06",
        serie="concorsi",
    )
    corretto = "https://www.gazzettaufficiale.it/eli/gu/2026/02/06/10/s4/pdf"
    status, _, ctype, first = _pdf_head(corretto)  # canary: the right URL is a PDF
    assert status == 200 and ctype.startswith("application/pdf") and first[:5] == b"%PDF-"

    url = re.search(r"https://\S+/pdf", r).group(0)
    status, finale, ctype, first = _pdf_head(url)
    assert ctype.startswith("application/pdf") and first[:5] == b"%PDF-", (url, finale, ctype)


# ---------------------------------------------------------------------------
# sommario_gazzetta
# ---------------------------------------------------------------------------

def test_sommario_205_2018_caso_piano_1(sommario_205_2018):
    """Plan case 1: the 23 atti of GU Serie generale n. 205/2018, D.Lgs. 101/2018 first."""
    r = sommario_205_2018
    assert "Errore" not in r, r
    assert "**Atti**: 23" in r, r
    assert f"**{DLGS_101_2018}** — DECRETO LEGISLATIVO 10 agosto 2018, n. 101" in r, r


def test_sommario_riporta_l_oggetto_degli_atti(sommario_205_2018):
    """The docstring promises "codice redazionale e oggetto". DEFECT: `_parse_sommario` keeps
    the first anchor of each atto (the estremi, "DECRETO 9 agosto 2018") and drops the second
    (the oggetto) as a duplicate codice; the issuer (span.emettitore) is not read either, and
    the heading is just "Sommario" without number and date of the fascicolo."""
    assert "regolamento (UE) 2016/679" in sommario_205_2018, sommario_205_2018


def test_sommario_con_supplemento_ordinario_caso_piano_2():
    """Plan case 2: GU n. 243 del 17-10-2022 lists the atti of S.O. n. 38 (D.Lgs. 149-151/2022)."""
    r = _run(sommario_gazzetta, numero_gazzetta="243", data_pubblicazione="2022-10-17")
    assert "Errore" not in r, r
    for codice in (DLGS_149_2022, "22G00159", "22G00160"):
        assert f"**{codice}**" in r, (codice, r)


def test_sommario_serie_speciale_concorsi():
    """4a Serie speciale Concorsi n. 10 del 6-2-2026 (50 atti, codici 26E...).

    DEFECT: `serie` is ignored and the page requested is ".../sg", which the site shows as
    "Gazzetta in fase di caricamento": the tool answers "Nessun atto trovato".
    """
    r = _run(
        sommario_gazzetta, numero_gazzetta="10", data_pubblicazione="2026-02-06", serie="concorsi",
    )
    assert "Nessun atto trovato" not in r, r
    assert re.search(r"\*\*26E\d{5}\*\*", r), r


# ---------------------------------------------------------------------------
# ultime_gazzette
# ---------------------------------------------------------------------------

def test_ultime_serie_generale_caso_piano_1():
    """Plan case 1: five recent Serie generale atti, each with codice, date and ELI link."""
    r = _run(ultime_gazzette, serie="serie_generale", max_risultati=5)
    assert "Errore" not in r, r
    blocchi = _blocchi(r)
    assert len(blocchi) == 5, r
    oggi = datetime.now().date()
    for b in blocchi:
        codice = _CODICE_RE.search(b)
        pub = _PUB_RE.search(b)
        assert codice and pub, b
        assert codice.group(1).startswith(pub.group(1)[2:4]), (codice.group(1), pub.group(1))
        giorni = (oggi - date.fromisoformat(pub.group(1))).days
        assert 0 <= giorni <= 10, pub.group(1)
        assert f"/eli/id/{pub.group(1).replace('-', '/')}/{codice.group(1)}/SG" in b, b


def test_ultime_corte_costituzionale_caso_piano_2():
    """Plan case 2: the 1a Serie speciale (Corte costituzionale) — codici with "C" (26C...).

    DEFECT: RSS_CODE maps corte_costituzionale to S3, which is the 3a Serie speciale (Regioni):
    the tool returns regional laws (codici 26R...). All five special series are shifted
    (see the RSS canary); and the links are rebuilt with "/SG", which for a special-series atto
    opens a page without the atto.
    """
    r = _run(ultime_gazzette, serie="corte_costituzionale", max_risultati=5)
    assert "Errore" not in r, r
    codici = _CODICE_RE.findall(r)
    assert codici, r
    assert all(c[2] == "C" for c in codici), codici
    assert "REGIONE" not in r, r

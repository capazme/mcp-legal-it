"""Smoke live of the four Giustizia Amministrativa tools against the official portal.

What it checks, on provvedimenti whose identifiers are fixed and public:

- `cerca_giurisprudenza_amministrativa`: Consiglio di Stato, Adunanza plenaria,
  sentenza n. 17/2021 (proroga ex lege delle concessioni demaniali marittime),
  found by anno + numero (portal number 202100017): sede `cds`, sezione P,
  ECLI:IT:CDS:2021:17APLE, ricorso NRG 202105584, file 202100017_11.html; and
  whether the date of publication (09/11/2021, `<dataPubblicazione>` of the
  official XML) reaches the user, as the docstring promises ("lista
  provvedimenti con sede, NRG, tipo, data e oggetto"). Year without number (TAR
  Lazio, "silenzio assenso", 2019): the portal ignores its `DataYearItem` field
  when no number is given (checked 2026-09-25: 4399 hits, all of 2026), so the
  tool filters the returned page and has to say so.
- `giurisprudenza_amm_su_norma`: "art. 21-octies L. 241/1990", Consiglio di
  Stato, anno_da 2025: every result from the CdS and not older than 2025, every
  excerpt on the cited norm, and the full text of the first three XML results
  citing art. 21-octies of L. 241/1990.
- `leggi_provvedimento_amm`: full text of AP 17/2021 (header, subject matter,
  declared truncation), whether the operative part ("P.Q.M.") reaches the
  reader, a CdS judgment the portal publishes only as PDF (sez. VII, n.
  6915/2026, NRG 202508523, file 202606915_11.pdf), and a non-existent
  reference (the mdp host answers HTTP 200 with an HTML error page).
- `ultimi_provvedimenti_amm`: latest judgments of the TAR Lombardia, seat of
  Milan: seat, type, year, descending numbers, ECLI, and freshness of the first
  one (`<dataPubblicazione>` of its XML within 30 days of `_clock.today()`).

Reference values: the search page https://www.giustizia-amministrativa.it/web/guest/dcsnprr
and the XML/PDF served by https://mdp.giustizia-amministrativa.it/visualizza/,
read on 2026-09-25 (AP 17/2021: `<dataPubblicazione>09/11/2021`, deliberated in
camera di consiglio on 20/10/2021, ricorso n. 14/2021 A.P., appeal against TAR
Sicilia - Catania n. 504/2021; the XML body is 106,448 characters and the
"P.Q.M." starts at character 104,513).

Every test that parses a tool answer is a real network call. Calls are cached
per session (`_call`), so each distinct input hits the portal once. A network
failure of the source ("non raggiungibile") skips the test instead of failing
it: that is the source being down, not the tool being wrong.

    .venv/bin/pytest tests/unit/test_giustizia_amm_live.py -m live -q -p no:cacheprovider -rfEs

Excluded from the default run (pyproject sets `-m 'not live'`). The older live
guard-rails for issue #32 stay in `tests/unit/test_giustizia_amm.py`.
"""

from __future__ import annotations

import asyncio
import functools
import re
from datetime import datetime, timedelta

import httpx
import pytest

import src.server  # noqa: F401  (registers every tool module first: avoids a circular import)
from src.lib import _clock
from src.lib.giustizia_amm.client import GASession, _parse_xml_text
from src.tools import giustizia_amm as ga_tools

pytestmark = pytest.mark.live

# Consiglio di Stato, Adunanza plenaria, sentenza 9 novembre 2021 n. 17.
AP17_QUERY = dict(
    query="concessioni demaniali marittime",
    sede="consiglio_di_stato",
    tipo="adunanza_plenaria",
    anno="2021",
    numero="17",
)
AP17_NUMERO = "202100017"
AP17_NRG = "202105584"
AP17_FILE = "202100017_11.html"
AP17_ECLI = "ECLI:IT:CDS:2021:17APLE"
AP17_DATA = ("09/11/2021", "9 novembre 2021", "2021-11-09")

# Consiglio di Stato, sez. VII, sentenza n. 6915/2026 — published only as PDF.
PDF_NRG = "202508523"
PDF_FILE = "202606915_11.pdf"

_OCTIES = re.compile(r"21\s*[-–]?\s*octies", re.I)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@functools.lru_cache(maxsize=None)
def _call_cached(name: str, items: tuple) -> str:
    tool = getattr(ga_tools, name)
    fn = getattr(tool, "fn", tool)
    return asyncio.run(fn(**dict(items)))


def _call(name: str, **kwargs) -> str:
    """Run a tool once per distinct input; skip when the portal is unreachable."""
    out = _call_cached(name, tuple(sorted(kwargs.items())))
    if out.startswith("**Errore**") and "non raggiungibile" in out:
        pytest.skip(f"portale non raggiungibile per {name}{kwargs}: {out[:300]}")
    return out


def _fetch_raw(sede: str, pairs: tuple[tuple[str, str], ...]) -> list[bytes]:
    """Raw documents from the mdp host, one portal session for all of them."""

    async def run() -> list[bytes]:
        async with GASession() as session:
            return [await session.fetch_text(sede, nrg, nome_file) for nrg, nome_file in pairs]

    try:
        return asyncio.run(run())
    except httpx.HTTPError as exc:  # the source being down, not the tool being wrong
        pytest.skip(f"mdp non raggiungibile: {exc}")


_HEADER = re.compile(r"^(?P<label>.+?) — (?P<tipo>.+?) n\. (?P<numero>\S+)(?: \((?P<anno>\d{4})\))?$")
_FIELD = re.compile(r"^\*\*(Sezione|ECLI)\*\*: (.*)$", re.M)
_LEGGI = re.compile(r'leggi_provvedimento_amm\(sede="([^"]*)", nrg="([^"]*)", nome_file="([^"]*)"\)')


def _parse(out: str) -> list[dict]:
    """Split a search answer into one dict per '### <seat> — <type> n. <number>' block."""
    docs = []
    for block in re.split(r"^### ", out, flags=re.M)[1:]:
        head = block.split("\n", 1)[0].strip()
        m = _HEADER.match(head)
        assert m, f"intestazione non riconosciuta: {head!r}"
        doc = {k: (v or "") for k, v in m.groupdict().items()}
        doc["block"] = block
        for key, value in _FIELD.findall(block):
            doc[key] = value.strip()
        m = _LEGGI.search(block)
        if m:
            doc["sede"], doc["nrg"], doc["nome_file"] = m.groups()
        docs.append(doc)
    return docs


# ---------------------------------------------------------------------------
# cerca_giurisprudenza_amministrativa
# ---------------------------------------------------------------------------


def test_cerca_adunanza_plenaria_17_2021_metadati():
    """Plan case 1: anno + numero pick exactly Ad. plen. n. 17/2021 with the portal metadata."""
    docs = _parse(_call("cerca_giurisprudenza_amministrativa", **AP17_QUERY))
    assert len(docs) == 1, [d["block"][:200] for d in docs]
    doc = docs[0]
    assert doc["label"] == "Consiglio di Stato"
    assert doc["tipo"] == "SENTENZA"
    assert doc["numero"] == AP17_NUMERO
    assert doc["anno"] == "2021"
    assert doc.get("Sezione") == "SEZIONE P"  # P = Adunanza plenaria on the portal
    assert doc.get("ECLI") == AP17_ECLI
    assert (doc.get("sede"), doc.get("nrg"), doc.get("nome_file")) == ("cds", AP17_NRG, AP17_FILE)
    assert "demaniali" in doc["block"] and "marittime" in doc["block"]


def test_cerca_adunanza_plenaria_17_2021_data_del_provvedimento():
    """The docstring promises 'sede, NRG, tipo, data e oggetto': the date must be in the answer.

    AP 17/2021 was published on 09/11/2021 (`<dataPubblicazione>` of the official
    XML). The search page of the portal carries no date, and the tool fills
    `data_deposito` with "" for every result, so the promise is never kept: either
    the docstring stops promising a date or the tool reads it from the XML.
    """
    out = _call("cerca_giurisprudenza_amministrativa", **AP17_QUERY)
    assert any(d in out for d in AP17_DATA), (
        "data del provvedimento assente dalla risposta (il docstring la promette): " + out[:600]
    )


def test_cerca_anno_senza_numero_filtrato_sui_risultati_e_dichiarato():
    """Plan case 2: a year without a number is filtered client-side and the answer says so."""
    out = _call("cerca_giurisprudenza_amministrativa", query="silenzio assenso", sede="tar_lazio", anno="2019")
    assert "non espone più un filtro per anno" in out, out[:600]
    for doc in _parse(out):
        assert doc["anno"] == "2019", doc["block"][:200]
        assert doc.get("sede") == "tar_rm", doc["block"][:200]


# ---------------------------------------------------------------------------
# giurisprudenza_amm_su_norma
# ---------------------------------------------------------------------------


def _su_norma_21_octies() -> list[dict]:
    out = _call(
        "giurisprudenza_amm_su_norma",
        riferimento="art. 21-octies L. 241/1990",
        sede="consiglio_di_stato",
        anno_da="2025",
        max_risultati=10,
    )
    assert "Nessun provvedimento" not in out, out[:600]
    return _parse(out)


def test_su_norma_21_octies_consiglio_di_stato_dal_2025():
    """Plan case: CdS provvedimenti from 2025 on, each excerpt on art. 21-octies / L. 241/1990."""
    docs = _su_norma_21_octies()
    assert 1 <= len(docs) <= 10
    for doc in docs:
        assert doc.get("sede") == "cds", doc["block"][:200]
        assert doc["label"] == "Consiglio di Stato"
        assert doc["anno"] and doc["anno"] >= "2025", doc["block"][:200]
        # The excerpt is the portal's highlight of the query terms.
        assert _OCTIES.search(doc["block"]) or "241" in doc["block"], doc["block"][:300]


def test_su_norma_21_octies_testo_dei_primi_tre_cita_la_norma():
    """Plan case: the first three XML results, read in full, cite art. 21-octies L. 241/1990.

    Read through the client (full body) rather than through `leggi_provvedimento_amm`,
    whose 15,000-character cut hides the citation of some of them (CdS n. 7047/2026
    cites it at character 34,081 of 41,578). PDF-only results are skipped here:
    `leggi_provvedimento_amm` cannot read them (see the PDF test below).
    """
    docs = [d for d in _su_norma_21_octies() if d.get("nome_file", "").endswith(".html")][:3]
    assert len(docs) == 3, f"meno di tre risultati XML: {[d.get('nome_file') for d in docs]}"
    raws = _fetch_raw("cds", tuple((d["nrg"], d["nome_file"]) for d in docs))
    for doc, raw in zip(docs, raws):
        _title, body = _parse_xml_text(raw)
        assert body, f"testo vuoto per {doc['nome_file']}"
        m = _OCTIES.search(body)
        assert m, f"{doc['numero']} non cita l'art. 21-octies"
        assert re.search(r"241\s*/\s*(19)?90", body), f"{doc['numero']} non cita la L. 241/1990"


# ---------------------------------------------------------------------------
# leggi_provvedimento_amm
# ---------------------------------------------------------------------------


def _ap17_full() -> str:
    return _call("leggi_provvedimento_amm", sede="cds", nrg=AP17_NRG, nome_file=AP17_FILE)


def test_leggi_ap_17_2021_intestazione_testo_e_troncamento_dichiarato():
    """Plan case 1: header with seat and NRG, text on the concessions, truncation declared."""
    out = _ap17_full()
    assert f"**Sede**: Consiglio di Stato (cds) — NRG: {AP17_NRG}" in out, out[:600]
    assert "(Adunanza Plenaria)" in out
    assert "registro generale 14 di A.P. del 2021" in out  # ricorso n. 14/2021 A.P.
    assert "n. 504/2021" in out  # appeal against TAR Sicilia - Catania n. 504/2021
    assert "concessioni demaniali marittime" in out
    assert "2006/123" in out  # art. 12 of the services directive
    m = re.search(r"Testo troncato a 15000 caratteri su (\d+) totali", out)
    assert m and int(m.group(1)) > 15000, out[-300:]


def test_leggi_ap_17_2021_dispositivo_raggiunge_il_lettore():
    """The docstring promises 'motivazione + dispositivo': the P.Q.M. must reach the reader.

    The XML body of AP 17/2021 is 106,448 characters and the P.Q.M. starts at
    104,513; the tool keeps the first 15,000, so the operative part (principles of
    law enunciated, remittal to the CGARS) is always cut from long decisions.
    """
    out = _ap17_full()
    assert "P.Q.M." in out and "enuncia i principi di diritto" in out, (
        "dispositivo assente: "
        + (re.search(r"Testo troncato[^*]*", out) or re.search(r"$", out)).group(0)
    )


def test_leggi_provvedimento_pubblicato_solo_in_pdf():
    """A PDF-only provvedimento must yield readable text or a clear message, never raw PDF bytes.

    CdS sez. VII n. 6915/2026: the portal links only `202606915_11.pdf` (the .html
    and .xml names answer with the error page). About 30% of the latest 50 CdS
    provvedimenti (15/50 on 2026-09-25) are PDF-only.
    """
    out = _call("leggi_provvedimento_amm", sede="cds", nrg=PDF_NRG, nome_file=PDF_FILE)
    assert "%PDF-" not in out and "endobj" not in out, (
        "il tool restituisce i byte grezzi del PDF come testo integrale: " + out[:300]
    )


def test_leggi_riferimento_inesistente_pagina_di_errore_riconosciuta():
    """Plan case 2: a wrong reference is reported as 'non recuperabile', not as the source down."""
    out = _call("leggi_provvedimento_amm", sede="cds", nrg="202500000", nome_file="202500000_01.html")
    assert "non recuperabile" in out and "pagina di errore" in out, out[:400]
    assert "non raggiungibile" not in out


# ---------------------------------------------------------------------------
# ultimi_provvedimenti_amm
# ---------------------------------------------------------------------------


def _ultimi_tar_milano() -> list[dict]:
    out = _call("ultimi_provvedimenti_amm", sede="tar_lombardia", tipo="sentenza", max_risultati=5)
    assert "Nessun provvedimento" not in out, out[:600]
    return _parse(out)


def test_ultimi_sentenze_tar_lombardia_milano():
    """Plan case: five judgments of the TAR Lombardia (Milan), newest first, with section and ECLI."""
    docs = _ultimi_tar_milano()
    assert len(docs) == 5
    today = _clock.today()
    # Early January the newest judgments can still carry last year's number.
    anni = {str(today.year), str(today.year - 1)}
    for doc in docs:
        assert doc["label"] == "TAR Lombardia - Milano", doc["block"][:200]
        assert doc["tipo"].startswith("SENTENZA"), doc["block"][:200]
        assert doc.get("sede") == "tar_mi"
        assert doc["anno"] in anni, doc["block"][:200]
        assert doc.get("Sezione", "").startswith("SEZIONE"), doc["block"][:200]
        assert re.fullmatch(r"ECLI:IT:TARMI:\d{4}:\d+SENT", doc.get("ECLI", "")), doc["block"][:200]
        assert doc.get("nrg") and doc.get("nome_file")
    numeri = [int(d["numero"]) for d in docs]
    assert numeri == sorted(numeri, reverse=True) and len(set(numeri)) == 5, numeri


def test_ultimi_sentenze_tar_lombardia_milano_sono_recenti():
    """'Ultimi' holds only if the newest result was published recently (dataPubblicazione of its XML)."""
    first = _ultimi_tar_milano()[0]
    if not first["nome_file"].endswith(".html"):
        pytest.skip(f"primo risultato pubblicato solo in PDF: {first['nome_file']}")
    (raw,) = _fetch_raw("tar_mi", ((first["nrg"], first["nome_file"]),))
    m = re.search(rb"<dataPubblicazione>(\d{2}/\d{2}/\d{4})</dataPubblicazione>", raw)
    assert m, raw[:400]
    pubblicato = datetime.strptime(m.group(1).decode(), "%d/%m/%Y").date()
    assert _clock.today() - timedelta(days=30) <= pubblicato <= _clock.today(), pubblicato

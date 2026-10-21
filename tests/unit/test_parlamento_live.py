"""Live smoke tests of the parliamentary tools: cerca_ddl, iter_ddl, ddl_su_norma.

Each tool is called once per case of the benchmark plan
(docs/benchmark/piano-benchmark-andreani.json) against the real endpoints
(dati.senato.it SPARQL, GET only; dati.camera.it SPARQL for the Camera
enrichment) on bills whose outcome is known, and the metadata the tool prints
(fase numbers, stati, dates, idDdl, law number and date) are checked. The law
estremi are then cross-checked on independent official sources: Normattiva
(art. 1 of the resulting law, via cite_law) and the Camera scheda of AC 3053.

Known bills used (verified 2026-09-25):
- AI bill: S.1146 -> C.2316 -> S.1146-B, became L. 23 settembre 2025, n. 132.
- Road-safety bill: C.1435 -> S.1086, became L. 25 novembre 2024, n. 177.
- Conversion of D.L. 12 giugno 2026, n. 100: S.1939 -> C.3053 (idDdl 55442),
  became L. 7 agosto 2026, n. 145 (GU n. 183 dell'8 agosto 2026).

Run with:
    .venv/bin/pytest tests/unit/test_parlamento_live.py -m live -q -p no:cacheprovider -rfEs
"""

from __future__ import annotations

import asyncio
import functools
import re
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

import src.server  # noqa: F401  (registers every tool module first: avoids a circular import)
from src.lib.parlamento.client import STATI_PENDENTI
from src.tools.parlamento import _CAVEAT_TITOLI, _norma_search_groups, cerca_ddl, ddl_su_norma, iter_ddl
from tests.unit._norme_live import cite_law_json, contiene

pytestmark = pytest.mark.live

_TOOLS = {"cerca_ddl": cerca_ddl, "iter_ddl": iter_ddl, "ddl_su_norma": ddl_su_norma}
_TITLE_CAP = 300  # format_fase / format_iter truncate titles at 300 chars
_CAMERA_SPARQL = "https://dati.camera.it/sparql"
_CAMERA_SCHEDA_3053 = (
    "https://www.camera.it/uri-res/N2Ls?"
    "urn:camera-it:parlamento:scheda.progetto.legge:camera;19.legislatura;3053"
)


@functools.lru_cache(maxsize=None)
def _call(tool: str, **kwargs) -> str:
    """One real call per (tool, arguments): tests sharing a case share the answer."""
    fn = getattr(_TOOLS[tool], "fn", _TOOLS[tool])
    return asyncio.run(fn(**kwargs))


def _blocchi_ricerca(text: str) -> dict[str, dict]:
    """Parse the '### <fase> — <stato>' blocks printed by format_fase."""
    out: dict[str, dict] = {}
    for chunk in re.split(r"\n(?=### )", text):
        m = re.match(r"### (\S+) — (.+)", chunk)
        if not m:
            continue
        titolo = re.search(r"\*\*Titolo\*\*: (.*)", chunk)
        data_stato = re.search(r"stato al (\d{4}-\d{2}-\d{2})", chunk)
        legge = re.search(r"\*\*Divenuto legge\*\*: n\. (\d+)(?: del (\d{4}-\d{2}-\d{2}))?", chunk)
        out[m.group(1)] = {
            "stato": m.group(2).strip(),
            "titolo": titolo.group(1).strip() if titolo else "",
            "data_stato": data_stato.group(1) if data_stato else "",
            "legge": (legge.group(1), legge.group(2) or "") if legge else None,
            "testo": chunk,
        }
    return out


def _ordine_ricerca(text: str) -> list[str]:
    return re.findall(r"^### (\S+) — ", text, flags=re.MULTILINE)


def _titolo_cita(titolo: str, *alternative: tuple[str, ...]) -> bool:
    """True if the title carries one of the AND-groups, or was truncated before it."""
    low = titolo.lower()
    if len(titolo) >= _TITLE_CAP:
        return True
    return any(all(term in low for term in gruppo) for gruppo in alternative)


# ---------------------------------------------------------------------------
# cerca_ddl
# ---------------------------------------------------------------------------

def test_cerca_ddl_intelligenza_artificiale_legge_132_2025():
    """Plan case 1: the AI bill navette (S.1146, C.2316, S.1146-B) with L. 132/2025."""
    out = _call("cerca_ddl", query="intelligenza artificiale", legislatura=19, max_risultati=50)
    assert "**Errore**" not in out, out[:500]
    m = re.search(r"\*\*Trovate (\d+) fasi di DDL\*\* \(legislatura 19\)", out)
    assert m, out[:500]
    blocchi = _blocchi_ricerca(out)
    assert int(m.group(1)) == len(_ordine_ricerca(out)) <= 50

    attesi = {"S.1146": "approvato", "C.2316": "appr. con modificaz", "S.1146-B": "appr. definit. Legge"}
    for fase, stato in attesi.items():
        assert fase in blocchi, f"{fase} assente: {list(blocchi)}"
        assert blocchi[fase]["stato"] == stato, (fase, blocchi[fase]["stato"])
        assert blocchi[fase]["legge"] == ("132", "2025-09-23"), (fase, blocchi[fase]["legge"])

    # Ordering declared by the query: ORDER BY DESC(?dataStato).
    date = [blocchi[f]["data_stato"] for f in _ordine_ricerca(out)]
    assert all(date), date
    assert date == sorted(date, reverse=True), date

    # Title-only search: every hit carries the phrase (unless its title was cut at 300 chars).
    fuori = [f for f, b in blocchi.items() if not _titolo_cita(b["titolo"], ("intelligenza artificiale",))]
    assert not fuori, fuori


def test_cerca_ddl_solo_pendenti():
    """Plan case 2: solo_pendenti keeps only the seven in-progress stati of STATI_PENDENTI."""
    out = _call(
        "cerca_ddl", query="intelligenza artificiale", legislatura=19, solo_pendenti=True, max_risultati=20,
    )
    assert "**Errore**" not in out, out[:500]
    blocchi = _blocchi_ricerca(out)
    assert blocchi, out[:500]
    stati = {b["stato"] for b in blocchi.values()}
    assert stati <= STATI_PENDENTI, stati - STATI_PENDENTI
    assert not any(b["legge"] for b in blocchi.values())
    for fase in ("S.1146", "C.2316", "S.1146-B"):
        assert fase not in blocchi


def test_legge_132_2025_su_normattiva():
    """Official cross-check: L. 23 settembre 2025, n. 132 exists on Normattiva and is the AI law."""
    payload = cite_law_json("art. 1 legge 23 settembre 2025, n. 132")
    assert not payload.get("errore"), payload
    assert payload["atto"]["data"] == "2025-09-23"
    assert payload["atto"]["numero_atto"] == "132"
    assert not contiene(payload["testo"], "intelligenza artificiale")


# ---------------------------------------------------------------------------
# iter_ddl
# ---------------------------------------------------------------------------

def _fasi_iter(out: str) -> dict[str, str]:
    blocchi = {}
    for chunk in re.split(r"\n(?=## Fase )", out):
        m = re.match(r"## Fase \d+ — (\S+) \(", chunk)
        if m:
            blocchi[m.group(1)] = chunk
    return blocchi


def test_iter_ddl_s1939_conversione_dl_100_2026():
    """Plan case 1: S.1939 -> C.3053, idDdl 55442, L. 7 agosto 2026, n. 145.

    Passes even when dati.camera.it is down: the Senato dataset alone carries
    the bicameral navette, and the Camera enrichment is fail-open by design.
    """
    out = _call("iter_ddl", atto="S.1939", legislatura=19)
    assert "**Errore**" not in out, out[:500]
    assert "Conversione in legge del decreto-legge 12 giugno 2026, n. 100" in out
    assert "**idDdl**: 55442 | **Legislatura**: 19 | **Fasi**: 2" in out
    fasi = _fasi_iter(out)
    assert list(fasi) == ["S.1939", "C.3053"], list(fasi)
    assert "(Senato, presentato)" in fasi["S.1939"]
    assert "**Stato**: approvato @ 2026-07-30" in fasi["S.1939"]
    assert "(Camera, trasmesso)" in fasi["C.3053"]
    assert "**Stato**: appr. definit. Legge @ 2026-08-05" in fasi["C.3053"]
    for fase, testo in fasi.items():
        assert "**Divenuto legge**: n. 145 del 2026-08-07" in testo, fase
        assert "https://www.senato.it/leg/19/BGT/Schede/Ddliter/" in testo, fase
    assert "scheda.progetto.legge:camera;19.legislatura;3053" in fasi["C.3053"]


def test_iter_ddl_arricchimento_camera():
    """Camera enrichment of C.3053: statoIter timeline and stampato PDF.

    Absent enrichment is a tool defect only if dati.camera.it answers: when the
    endpoint itself is down the fail-open path is the documented behaviour.
    """
    out = _call("iter_ddl", atto="S.1939", legislatura=19)
    if "**Iter alla Camera** (statoIter):" not in out:
        try:
            resp = httpx.post(
                _CAMERA_SPARQL,
                data={"query": "SELECT ?s WHERE { ?s ?p ?o } LIMIT 1"},
                headers={"Accept": "application/sparql-results+json"},
                timeout=30.0,
            )
            stato_endpoint = resp.status_code
        except httpx.HTTPError as exc:
            stato_endpoint = repr(exc)
        if not isinstance(stato_endpoint, int) or stato_endpoint >= 500:
            pytest.skip(
                f"dati.camera.it/sparql non disponibile ({stato_endpoint}): arricchimento Camera "
                "assente, iter ricostruito comunque dal Senato (fail-open verificato)"
            )
        pytest.fail(f"dati.camera.it risponde {stato_endpoint} ma l'iter non ha la timeline Camera")
    fasi = _fasi_iter(out)
    camera = fasi["C.3053"]
    assert re.search(r"^- 2026-0[78]-\d{2} — ", camera, flags=re.MULTILINE), camera
    assert "**Stampato (PDF)**: http" in camera


def test_iter_ddl_da_numero_camera():
    """Plan case 2: the same navette starting from the Camera number."""
    out = _call("iter_ddl", atto="AC 3053", legislatura=19)
    assert "**Errore**" not in out, out[:500]
    assert "**idDdl**: 55442" in out
    assert list(_fasi_iter(out)) == ["S.1939", "C.3053"]
    assert out.count("**Divenuto legge**: n. 145 del 2026-08-07") == 2


def test_iter_ddl_formato_non_riconosciuto_senza_rete():
    """Plan case 3: 'DDL 1939' is rejected before any network call."""
    with patch("src.lib.parlamento.client.httpx.AsyncClient", side_effect=AssertionError("rete usata")):
        out = asyncio.run(getattr(iter_ddl, "fn", iter_ddl)(atto="DDL 1939"))
    assert out.startswith("**Errore**"), out
    assert "non riconosciuto" in out


def test_legge_145_2026_su_normattiva():
    """Official cross-check: art. 1 L. 7 agosto 2026, n. 145 converts D.L. 12 giugno 2026, n. 100."""
    payload = cite_law_json("art. 1 legge 7 agosto 2026, n. 145")
    assert not payload.get("errore"), payload
    assert payload["atto"]["data"] == "2026-08-07"
    assert not contiene(payload["testo"], "convertito in legge il decreto-legge 12 giugno 2026, n. 100")


def test_scheda_camera_ac3053():
    """Official cross-check on camera.it: law n. 145 of 7 August 2026, final vote on 5 August 2026."""
    resp = httpx.get(_CAMERA_SCHEDA_3053, timeout=30.0, follow_redirects=True,
                     headers={"User-Agent": "Mozilla/5.0"})
    assert resp.status_code == 200, resp.status_code
    testo = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", resp.text))
    mancanti = contiene(
        testo,
        "Legge n. 145 del 7 agosto 2026",
        "conclusa il 5 agosto 2026. Approvato definitivamente",
        "trasmesso dal Senato il 30 luglio 2026",
    )
    assert not mancanti, mancanti


# ---------------------------------------------------------------------------
# ddl_su_norma
# ---------------------------------------------------------------------------

def test_ddl_su_norma_codice_della_strada():
    """Plan case 1: 'codice della strada' expands to the code name and to D.Lgs. 285/1992."""
    assert _norma_search_groups("codice della strada")[0] == [["codice della strada"], ["285", "1992"]]
    out = _call("ddl_su_norma", riferimento="codice della strada", legislatura=19, max_risultati=50)
    assert "**Errore**" not in out, out[:500]
    assert out.startswith("**DDL che citano nel titolo**: _codice della strada_ (legislatura 19)")
    assert _CAVEAT_TITOLI in out
    assert "Riferimento non riconosciuto" not in out
    blocchi = _blocchi_ricerca(out)
    assert 0 < len(blocchi) <= 50

    # The road-safety bill: S.1086 is the final reading. Its first reading C.1435
    # (stato 'approvato' @ 2024-03-27, same idDdl 53126) sorts past the 50 cap.
    assert blocchi["S.1086"]["stato"] == "appr. definit. Legge"
    assert blocchi["S.1086"]["legge"] == ("177", "2024-11-25")
    assert "sicurezza stradale" in blocchi["S.1086"]["titolo"].lower()

    date = [blocchi[f]["data_stato"] for f in _ordine_ricerca(out)]
    assert date == sorted(date, reverse=True), date
    fuori = [
        f for f, b in blocchi.items()
        if not _titolo_cita(b["titolo"], ("codice della strada",), ("285", "1992"))
    ]
    assert not fuori, fuori


def test_legge_177_2024_su_normattiva():
    """Official cross-check: L. 25 novembre 2024, n. 177 amends the codice della strada."""
    payload = cite_law_json("art. 1 legge 25 novembre 2024, n. 177")
    assert not payload.get("errore"), payload
    assert payload["atto"]["data"] == "2024-11-25"
    assert not contiene(payload["testo"], "codice della strada")


def test_ddl_su_norma_articolo_ignorato():
    """Plan case 2: 'art. 2043 c.c.' searches the act (codice civile), not the article."""
    assert _norma_search_groups("art. 2043 c.c.")[0] == [["codice civile"]]
    out = _call("ddl_su_norma", riferimento="art. 2043 c.c.", legislatura=19)
    assert "**Errore**" not in out, out[:500]
    assert _CAVEAT_TITOLI in out
    blocchi = _blocchi_ricerca(out)
    if blocchi:
        assert len(blocchi) <= 10
        fuori = [f for f, b in blocchi.items() if not _titolo_cita(b["titolo"], ("codice civile",))]
        assert not fuori, fuori


def test_ddl_su_norma_avvertenza_anche_senza_risultati():
    """The title-only caveat is printed with zero results too (mocked empty answer, no network)."""
    client = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.status_code = 200
    resp.json = MagicMock(return_value={"head": {"vars": []}, "results": {"bindings": []}})
    client.get = AsyncMock(return_value=resp)
    client.request = AsyncMock(return_value=resp)
    with patch("src.lib.parlamento.client.httpx.AsyncClient", return_value=client):
        out = asyncio.run(getattr(ddl_su_norma, "fn", ddl_su_norma)(riferimento="art. 2043 c.c."))
    assert out.startswith("Nessun DDL trovato che citi nel titolo"), out
    assert _CAVEAT_TITOLI in out

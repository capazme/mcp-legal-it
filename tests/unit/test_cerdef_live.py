"""Live smoke gate for the CeRDEF tools (Dipartimento delle finanze, def.finanze.it/DocTribFrontend).

Tools under test: `cerca_giurisprudenza_tributaria`, `cerdef_leggi_provvedimento`,
`ultime_sentenze_tributarie` (src/tools/cerdef.py over src/lib/cerdef/client.py).

What it checks, one real call per case on a known document:

* the portal itself still exposes Cass., Sez. Un., 9 dicembre 2015 n. 24823 (contraddittorio
  endoprocedimentale) through the advanced search form as it stands on 2026-09-25 — a canary
  that tells a source outage apart from a broken tool;
* the search tool finds that sentenza by keywords (plan case 1) and by number (plan case 2),
  with estremi, date and GUID;
* the detail tool returns its estremi and full text from the GUID, and reports an unknown GUID
  as "not found" rather than as the source being down;
* the "latest" tool returns second-instance CGT sentenze in descending date order, each with GUID.

Needs the network, so it is excluded from the default run. Launch it with:

    .venv/bin/pytest tests/unit/test_cerdef_live.py -m live -q -p no:cacheprovider -rfEs
"""

from __future__ import annotations

import re
from datetime import datetime

import httpx
import pytest

import src.server  # noqa: F401  (registers every tool module first: avoids a circular import)
from src.lib.cerdef.client import _BASE, _HEADERS, _SEARCH_URL, _extract_xml_from_js
from src.tools.cerdef import (
    cerca_giurisprudenza_tributaria,
    cerdef_leggi_provvedimento,
    ultime_sentenze_tributarie,
)

pytestmark = pytest.mark.live

# Cass., Sez. Un., 9 dicembre 2015 n. 24823 — identifier assigned by CeRDEF, read from the
# portal's own result list on 2026-09-25 (search: numero=24823, ente="Corte di Cassazione",
# anno 2015). A CeRDEF GUID is the permanent id of the document in the banca dati.
GUID_SSUU_24823_2015 = "{B0F76E21-B5FA-4415-9D1D-44FF7B5741C1}"
_GUID_CORE = GUID_SSUU_24823_2015.strip("{}").lower()

_UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)
_DATE_RE = re.compile(r"\b(\d{2})/(\d{2})/(\d{4})\b")


def _fn(tool):
    return getattr(tool, "fn", tool)


def _blocchi(risultato: str) -> list[str]:
    """Split a markdown result list into its '### ' blocks (one per provvedimento)."""
    return [b for b in re.split(r"^### ", risultato, flags=re.M)[1:] if b.strip()]


# ---------------------------------------------------------------------------
# Canary on the source (not on the tool)
# ---------------------------------------------------------------------------


def test_portale_cerdef_espone_ssuu_24823_2015():
    """The portal answers the advanced search (form of 2026-09-25) with Cass. SS.UU. 24823/2015.

    Field names read from callRicAvanzataGiurisprudenza.do on 2026-09-25: `ambitoRicerca=G`,
    `parole`, `tipoCriterioRicerca` (0-4), `tipo_ord` (DATA|RANK), `tipoEstremi`, `numero`,
    `{giorno,mese,anno}DataEmissione{Da,A}`, `ente` / `superEnte` (mutually exclusive).
    The result is XML in `var xmlResult`, shaped
    `<risultatiRicerca><risultati><Provvedimento idProvvedimento="{GUID}"><estremi>…`.
    If this test fails the source changed or is down, and the tool tests below say nothing.
    """
    form = {
        "js_enabled": "1", "tipoComplessitaRicerca": "avanzata", "ricercaAreaRiservata": "false",
        "tipoRicerca": "RA", "device": "D", "ambitoRicerca": "G",
        "parole": "", "tipoCriterioRicerca": "0", "tipo_ord": "DATA", "tipoEstremi": "",
        "numero": "24823",
        "giornoDataEmissioneDa": "", "meseDataEmissioneDa": "", "annoDataEmissioneDa": "2015",
        "dataEmissioneDa": "",
        "giornoDataEmissioneA": "", "meseDataEmissioneA": "", "annoDataEmissioneA": "2015",
        "dataEmissioneA": "",
        "ente": "Corte di Cassazione", "superEnte": "", "materiaFiscale": "",
        "classificazioneArgomento": "",
    }
    with httpx.Client(headers=_HEADERS, follow_redirects=True, timeout=45) as client:
        client.get(_BASE + "callRicAvanzataGiurisprudenza.do")
        resp = client.post(_SEARCH_URL, data=form)
    assert resp.status_code == 200, resp.status_code
    xml = _extract_xml_from_js(resp.text, "xmlResult")
    assert xml, "risposta del portale senza var xmlResult (formato cambiato?)"
    assert GUID_SSUU_24823_2015 in xml, xml[:1500]
    assert "Sentenza del 09/12/2015 n. 24823 - Corte di Cassazione" in xml, xml[:1500]
    assert "Sezioni unite" in xml, xml[:1500]


# ---------------------------------------------------------------------------
# cerca_giurisprudenza_tributaria
# ---------------------------------------------------------------------------


async def test_cerca_giurisprudenza_tributaria_ssuu_24823_2015_per_parole():
    """Plan case 1: keywords + Cassazione + sentenza + December 2015 finds SS.UU. 24823/2015."""
    out = await _fn(cerca_giurisprudenza_tributaria)(
        query="contraddittorio endoprocedimentale",
        ente="corte_suprema",
        tipo_provvedimento="sentenza",
        data_da="01/12/2015",
        data_a="31/12/2015",
        max_risultati=10,
    )
    assert "Errore" not in out and not out.startswith("Nessun"), out[:800]
    assert "24823" in out, out[:1500]
    assert "09/12/2015" in out, out[:1500]
    assert _GUID_CORE in out.lower(), out[:1500]
    assert all(_UUID_RE.search(b) for b in _blocchi(out)), "blocco risultato senza GUID"


async def test_cerca_giurisprudenza_tributaria_ssuu_24823_2015_per_numero():
    """Plan case 2: the number alone (Cassazione, year 2015) identifies SS.UU. 24823/2015."""
    out = await _fn(cerca_giurisprudenza_tributaria)(
        query="",
        numero="24823",
        ente="corte_suprema",
        data_da="01/01/2015",
        data_a="31/12/2015",
    )
    assert "Errore" not in out and not out.startswith("Nessun"), out[:800]
    assert "24823" in out, out[:1500]
    assert _GUID_CORE in out.lower(), out[:1500]


# ---------------------------------------------------------------------------
# cerdef_leggi_provvedimento
# ---------------------------------------------------------------------------


async def test_cerdef_leggi_provvedimento_ssuu_24823_2015():
    """Detail of SS.UU. 24823/2015: estremi, full text on the contraddittorio, truncation at 25000.

    The source text (read on 2026-09-25) is ~56 000 characters, has an empty <massima/> and ends
    with "Depositato in Cancelleria il 9 dicembre 2015"; the tool must therefore show the
    Testo Integrale section and the truncation note. The JS string escapes accented letters as
    `\\à`: the rendered text must not keep the backslash ("societ\\à").
    """
    out = await _fn(cerdef_leggi_provvedimento)(guid=GUID_SSUU_24823_2015)
    assert "Errore" not in out, out[:800]
    assert "n. 24823" in out, out[:800]
    assert "09/12/2015" in out, out[:800]
    assert "sezioni unite" in out.lower(), out[:800]
    assert "## Testo Integrale" in out, out[:800]
    assert "contraddittorio endoprocedimentale" in out.lower(), out[:800]
    assert "armonizzat" in out.lower(), out[:800]
    assert len(out) > 20000, len(out)
    assert "Testo troncato a 25000 caratteri" in out, out[-400:]
    assert not re.search(r"\\[àèéìòù]", out), "escape JS non risolti nel testo (es. societ\\à)"


async def test_cerdef_leggi_provvedimento_guid_inesistente():
    """Plan case 2: an unknown GUID must be reported as not found, not as an empty success or an outage.

    On 2026-09-25 the portal answers an unknown id with HTTP 500 and a 74-byte body.
    """
    out = await _fn(cerdef_leggi_provvedimento)(guid="abc-123-def-456")
    assert out.strip() not in ("#", ""), "risposta di successo vuota per un GUID inesistente"
    assert "non raggiungibile" not in out.lower(), out[:400]
    assert re.search(r"non trovat|inesistent|non valid", out, re.I), out[:400]


async def test_cerdef_leggi_provvedimento_guid_ben_formato_ma_inesistente():
    """A well-formed GUID the portal does not know (HTTP 500 + NullPointerException) is "not found".

    Not an outage and not a malformed input: the portal is reachable and the id has the right shape.
    """
    out = await _fn(cerdef_leggi_provvedimento)(guid="{00000000-0000-0000-0000-000000000000}")
    assert "provvedimento non trovato o GUID non valido" in out, out[:400]
    assert "non raggiungibile" not in out.lower(), out[:400]


# ---------------------------------------------------------------------------
# ultime_sentenze_tributarie
# ---------------------------------------------------------------------------


async def test_ultime_sentenze_tributarie_cgt_secondo_grado():
    """Plan case: latest 5 sentenze of the CGT di secondo grado, newest first, each with GUID.

    Source on 2026-09-25 (superEnte "Tutte le Corti di giustizia tributaria di secondo grado",
    tipo Sentenza, ordered by date): newest is CGT II Piemonte, 10/12/2025 n. 913.
    """
    out = await _fn(ultime_sentenze_tributarie)(
        ente="cgt_secondo_grado", tipo_provvedimento="sentenza", max_risultati=5
    )
    assert "Errore" not in out and not out.startswith("Nessun"), out[:800]
    blocchi = _blocchi(out)
    assert 1 <= len(blocchi) <= 5, out[:1500]
    date = []
    for b in blocchi:
        assert _UUID_RE.search(b), f"blocco senza GUID: {b[:300]}"
        assert "secondo grado" in b.lower() or "ii grado" in b.lower(), f"ente non di secondo grado: {b[:300]}"
        m = _DATE_RE.search(b)
        assert m, f"blocco senza data: {b[:300]}"
        date.append(datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))))
    assert date == sorted(date, reverse=True), date

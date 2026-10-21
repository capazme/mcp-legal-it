"""Smoke live of the four Corte costituzionale tools against the Court's open data.

Source: dati.cortecostituzionale.it, the Court's own open-data distribution
(pronunce: P_json1956_1980.zip and P_json2001_oggi.zip; massime:
CC_M_1956_1980_json.zip and CC_M_2001_2015_json.zip, which the download page
labels "dal 2001 ad oggi"). The bundles are regenerated daily (Last-Modified
25/09/2026 when this file was written). The www.cortecostituzionale.it site is
Radware-protected and is never touched.

What it checks, on decisions whose identifiers are fixed and public:

- `leggi_pronuncia_costituzionale`: sentenza 194/2018 (ECLI:IT:COST:2018:194,
  decided 26/09/2018, deposited 08/11/2018, president Lattanzi, relatore
  Sciarra; GU 1a Serie speciale n. 45 del 14/11/2018 reads "SENTENZA
  26 settembre - 8 novembre 2018"), sentenza 1/1956, a missing decision, and
  whether the operative part (dispositivo) of the source record reaches the user.
- `cerca_pronuncia_costituzionale`: 194/2018 found by "licenziamento,
  indennità" (accented term, comma = AND), and the current-year default.
- `pronunce_cost_su_norma`: art. 23 L. 87/1953 in 1956, art. 3 Cost. in 2018
  (massime after 2015), the default year range, and whether "Costituzione"
  in the reference restricts the match to the Constitution.
- `ultime_pronunce_cost`: latest sentenze of the current year; in 2026 the
  last Court decisions published in GU 1a Serie speciale are those of n. 30
  del 29/07/2026 (sentenze 142-146 and 148-153, ordinanza 147; 153/2026
  decided 08/07/2026, deposited 24/07/2026); issues 35-38 of September 2026
  carry only referral orders (read on 2026-09-25).

The corte_cost cache is pointed at a fresh temporary directory for the module,
so every decade bundle really comes from the source (four downloads, ~86 MB,
once per run); calls are memoised per distinct input. A source failure
("non raggiungibile") skips the test instead of failing it: that is the source
being down, not the tool being wrong.

    .venv/bin/pytest tests/unit/test_corte_cost_live.py -m live -q -p no:cacheprovider -rfEs

Excluded from the default run (pyproject sets `-m 'not live'`).
"""

from __future__ import annotations

import asyncio
import functools
import re
from datetime import date

import pytest

import src.server  # noqa: F401  (registers every tool module first: avoids a circular import)
from src.lib import _clock
from src.lib.corte_cost import client as cc_client
from src.tools import corte_cost as cc_tools

pytestmark = pytest.mark.live

SOURCE_DOWN = "non raggiungibile"

# Sentenza 194/2018 (contratto a tutele crescenti), as published by the Court and in GU.
S194_ECLI = "ECLI:IT:COST:2018:194"
S194_DECISIONE = "26/09/2018"
S194_DEPOSITO = "08/11/2018"
S194_DISPOSITIVO = (
    "di importo pari a due mensilità dell'ultima retribuzione di riferimento per il calcolo "
    "del trattamento di fine rapporto per ogni anno di servizio"
)

# Sentenze of 2018 containing both "licenziamento" and "indennità" (epigrafe, testo or
# dispositivo), read from Cc_Opendata_Pronunce_2018.json on 2026-09-25.
S2018_LICENZIAMENTO_INDENNITA = {"77", "86", "158", "194", "248"}

# Last Court decision of 2026 published in GU 1a Serie speciale n. 30 del 29/07/2026.
LAST_2026 = {"numero": 153, "decisione": "08/07/2026", "deposito": "24/07/2026"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module", autouse=True)
def _fresh_cache(tmp_path_factory):
    """Empty cache directory for the module: the bundles are downloaded, not read from ~/.cache."""
    mp = pytest.MonkeyPatch()
    mp.setenv("MCP_CACHE_DIR", str(tmp_path_factory.mktemp("corte_cost_cache")))
    mp.delenv("LEGAL_CACHE", raising=False)  # cache on: otherwise each call re-downloads a decade
    _call_cached.cache_clear()
    yield
    _call_cached.cache_clear()
    mp.undo()


@functools.lru_cache(maxsize=None)
def _call_cached(name: str, items: tuple) -> str:
    tool = getattr(cc_tools, name)
    fn = getattr(tool, "fn", tool)
    return asyncio.run(fn(**dict(items)))


def _call(name: str, **kwargs) -> str:
    """Run a tool once per distinct input; skip when the open-data portal is unreachable."""
    out = _call_cached(name, tuple(sorted(kwargs.items())))
    if out.startswith("**Errore**") and SOURCE_DOWN in out:
        pytest.skip(f"dati.cortecostituzionale.it non raggiungibile per {name}{kwargs}: {out[:300]}")
    return out


_FIELD = re.compile(r"^\*\*(ECLI|Deposito|Decisione|Presidente|Relatore|Oggetto)\*\*: (.*)$", re.M)
_HEAD = re.compile(r"^(Sentenza|Ordinanza|Pronuncia) n\. (\d+)/(\d{4})")
_MASSIMA_HEAD = re.compile(r"^Massima \(pronuncia n\. (\d+)/(\d{4})\)")


def _parse(out: str) -> list[dict]:
    """Split a search answer into one dict per '### <Tipo> n. N/AAAA' block."""
    docs = []
    for block in out.split("\n### ")[1:]:
        head = block.split("\n", 1)[0].strip()
        m = _HEAD.match(head)
        doc = {"head": head}
        if m:
            doc.update(tipo=m.group(1), numero=m.group(2), anno=m.group(3))
        for key, value in _FIELD.findall(block):
            doc[key] = value.strip()
        docs.append(doc)
    return docs


def _parse_massime(out: str) -> list[dict]:
    """Split a pronunce_cost_su_norma answer into one dict per massima block."""
    hits = []
    for block in out.split("\n### ")[1:]:
        m = _MASSIMA_HEAD.match(block)
        params = re.search(r"^\*\*Parametri\*\*: (.*)$", block, re.M)
        hits.append({
            "numero": m.group(1) if m else "",
            "anno": m.group(2) if m else "",
            "parametri": params.group(1) if params else "",
        })
    return hits


def _dmy(value: str) -> date:
    d, m, y = (int(x) for x in value.split("/"))
    return date(y, m, d)


def _source_record(numero: int, anno: int) -> cc_client.PronunciaCost:
    """The decoded source record (already in the module cache after the tool call)."""
    doc = asyncio.run(cc_client.fetch_pronuncia(numero, anno))
    assert doc is not None, f"{numero}/{anno} assente dal dump open data"
    return doc


# ---------------------------------------------------------------------------
# leggi_pronuncia_costituzionale
# ---------------------------------------------------------------------------


def test_leggi_pronuncia_costituzionale_194_2018_metadati():
    """Plan case 1: ECLI, dates, president and relatore of sentenza 194/2018 (GU 1a s.s. n. 45/2018)."""
    out = _call("leggi_pronuncia_costituzionale", numero=194, anno=2018)
    assert out.startswith("# Sentenza Corte Costituzionale n. 194/2018"), out[:200]
    fields = dict(_FIELD.findall(out))
    assert fields.get("ECLI") == S194_ECLI
    assert fields.get("Decisione") == S194_DECISIONE
    assert fields.get("Deposito") == S194_DEPOSITO
    assert fields.get("Presidente", "").casefold() == "lattanzi"
    assert fields.get("Relatore") == "Silvana Sciarra"
    # latin-1 decoding of the source: accented words must come through intact.
    assert "legittimità costituzionale" in out
    assert "decreto legislativo 4 marzo 2015, n. 23" in out


def test_leggi_pronuncia_costituzionale_194_2018_dispositivo():
    """Plan case 1: the dispositivo strikes out the 'two months per year of service' words of art. 3 co. 1 D.Lgs. 23/2015."""
    out = _call("leggi_pronuncia_costituzionale", numero=194, anno=2018)
    source = _source_record(194, 2018)
    assert S194_DISPOSITIVO in source.dispositivo, "il dump non riporta il dispositivo atteso"
    assert "## Dispositivo" in out and S194_DISPOSITIVO in out, (
        f"dispositivo assente dalla risposta: epigrafe {len(source.epigrafe)} + testo "
        f"{len(source.testo)} + dispositivo {len(source.dispositivo)} caratteri, corpo troncato a "
        f"{cc_client._MAX_TEXT_LENGTH} (troncato: {'troncato' in out}); il dispositivo sta in coda"
    )


@pytest.mark.parametrize(("numero", "anno"), [(1, 1956), (153, 2026)])
def test_leggi_pronuncia_costituzionale_dispositivo_integrale(numero, anno):
    """The operative part of the source record must reach the user in full, whatever the length of the reasons."""
    out = _call("leggi_pronuncia_costituzionale", numero=numero, anno=anno)
    source = _source_record(numero, anno)
    assert source.dispositivo, f"{numero}/{anno}: dispositivo vuoto nel dump"
    assert source.dispositivo in out, (
        f"{numero}/{anno}: dispositivo ({len(source.dispositivo)} caratteri) non integro nella risposta; "
        f"epigrafe {len(source.epigrafe)} + testo {len(source.testo)} caratteri, "
        f"troncamento a {cc_client._MAX_TEXT_LENGTH}"
    )


def test_leggi_pronuncia_costituzionale_1_1956():
    """Plan case 2: the first decision of the Court (decided 05/06/1956, deposited 14/06/1956)."""
    out = _call("leggi_pronuncia_costituzionale", numero=1, anno=1956)
    assert out.startswith("# Sentenza Corte Costituzionale n. 1/1956"), out[:200]
    fields = dict(_FIELD.findall(out))
    assert fields.get("ECLI") == "ECLI:IT:COST:1956:1"
    assert fields.get("Decisione") == "05/06/1956"
    assert fields.get("Deposito") == "14/06/1956"
    assert fields.get("Relatore") == "Gaetano Azzariti"
    testo = out.split("## Testo", 1)[1] if "## Testo" in out else ""
    assert len(testo.strip()) > 100
    assert "art. 113" in out


def test_leggi_pronuncia_costituzionale_inesistente():
    """Plan case 3: a number the Court never reached in 2018 gives a clear 'non trovata'."""
    out = _call("leggi_pronuncia_costituzionale", numero=9999, anno=2018)
    assert "Pronuncia n. 9999/2018 non trovata" in out
    assert "## Testo" not in out and "ECLI" not in out


# ---------------------------------------------------------------------------
# cerca_pronuncia_costituzionale
# ---------------------------------------------------------------------------


def _search_2018(query: str) -> list[dict]:
    return _parse(_call(
        "cerca_pronuncia_costituzionale",
        query=query, tipo="sentenza", anno_da=2018, anno_a=2018, max_risultati=50,
    ))


def test_cerca_pronuncia_costituzionale_194_2018():
    """Plan case 1: 'licenziamento, indennità' in 2018 finds 194/2018 with its metadata."""
    docs = _search_2018("licenziamento, indennità")
    assert docs, "nessun risultato"
    assert all(d.get("tipo") == "Sentenza" and d.get("anno") == "2018" for d in docs), docs
    hit = [d for d in docs if d.get("numero") == "194"]
    assert hit, f"194/2018 assente: {[d['head'] for d in docs]}"
    assert hit[0].get("ECLI") == S194_ECLI
    assert hit[0].get("Decisione") == S194_DECISIONE
    assert hit[0].get("Deposito") == S194_DEPOSITO


def test_cerca_pronuncia_costituzionale_virgola_e_and_con_accenti():
    """Comma-separated terms are AND'ed, and the accented 'indennità' is matched (latin-1 decoding)."""
    both = {d["numero"] for d in _search_2018("licenziamento, indennità")}
    one = {d["numero"] for d in _search_2018("licenziamento")}
    assert both == S2018_LICENZIAMENTO_INDENNITA, both
    assert both < one, (both, one)


def test_cerca_pronuncia_costituzionale_senza_anni_solo_anno_corrente():
    """Plan case 2: with no years the search covers only the current year."""
    year = _clock.today().year
    out = _call("cerca_pronuncia_costituzionale", query="licenziamento")
    docs = _parse(out)
    if not docs:
        assert f"anno {year}" in out and "anno_da" in out, out
        return
    assert all(d.get("anno") == str(year) for d in docs), [d["head"] for d in docs]
    assert all(d.get("ECLI", "").startswith(f"ECLI:IT:COST:{year}:") for d in docs)


def test_cerca_pronuncia_costituzionale_senza_anni_lo_dichiara():
    """Plan note: with no years the answer must say it looked only at the current year, also when it finds something."""
    year = _clock.today().year
    out = _call("cerca_pronuncia_costituzionale", query="licenziamento")
    if not _parse(out):
        pytest.skip("nessun risultato: il ramo 'no_results' dichiara già l'anno")
    header = out.split("\n### ", 1)[0]
    assert str(year) in header, (
        f"l'intestazione {header.strip()!r} non dice che la ricerca ha coperto solo il {year}: "
        "chi legge 'Trovate N pronunce' la prende per l'intero archivio"
    )


# ---------------------------------------------------------------------------
# pronunce_cost_su_norma
# ---------------------------------------------------------------------------


def test_pronunce_cost_su_norma_art_23_legge_87_1953_nel_1956():
    """Plan case 1: massime of 1956 invoking art. 23 L. 11 marzo 1953, n. 87."""
    out = _call("pronunce_cost_su_norma", riferimento="art. 23 legge 87/1953", anno_da=1956, anno_a=1956)
    hits = _parse_massime(out)
    assert hits, out[:300]
    assert all(h["anno"] == "1956" for h in hits), hits
    assert all(re.search(r"legge n\. 87 del 11/03/1953 art\. 23(?!\d)", h["parametri"]) for h in hits), hits
    assert any(h["numero"] == "1" for h in hits)


def test_pronunce_cost_su_norma_massime_dopo_il_2015():
    """Plan case 2: the massime bundle named '2001_2015' actually runs to today; 2018 is covered."""
    out = _call("pronunce_cost_su_norma", riferimento="art. 3 Costituzione", anno_da=2018, anno_a=2018,
                max_risultati=50)
    hits = _parse_massime(out)
    assert hits, out[:300]
    assert all(h["anno"] == "2018" for h in hits), hits


def test_pronunce_cost_su_norma_default_copre_archivio_intero():
    """Docstring: 'default copre l'intero archivio massime' - the archive runs to the current year, not to 2015."""
    out = _call("pronunce_cost_su_norma", riferimento="art. 3 Costituzione")
    hits = _parse_massime(out)
    assert hits, out[:300]
    years = sorted({int(h["anno"]) for h in hits})
    assert max(years) > 2015, (
        f"senza anni il tool legge solo fino al 2015 (anni dei risultati: {years}), "
        "mentre l'archivio delle massime copre 2016-oggi (verificato con anno_da=2018)"
    )


def test_pronunce_cost_su_norma_art_3_costituzione_solo_costituzione():
    """'art. 3 Costituzione' must not return massime whose only art. 3 is of another act (statuto, norme integrative)."""
    out = _call("pronunce_cost_su_norma", riferimento="art. 3 Costituzione", anno_da=2018, anno_a=2018,
                max_risultati=50)
    hits = _parse_massime(out)
    assert hits
    wrong = [
        (f"{h['numero']}/{h['anno']}", h["parametri"])
        for h in hits
        if not re.search(r"(?:^|; )Costituzione art\. 3(?!\d)", h["parametri"])
    ]
    assert not wrong, f"{len(wrong)}/{len(hits)} massime senza art. 3 Cost. tra i parametri: {wrong[:5]}"


# ---------------------------------------------------------------------------
# ultime_pronunce_cost
# ---------------------------------------------------------------------------


def test_ultime_pronunce_cost_sentenze():
    """Plan case 1: five sentenze of the current year, newest deposit first, not behind the GU."""
    today = _clock.today()
    year = today.year
    out = _call("ultime_pronunce_cost", tipo="sentenza", max_risultati=5)
    if "Nessuna pronuncia costituzionale depositata" in out and today.month == 1:
        pytest.skip(f"inizio anno: nessuna pronuncia ancora depositata nel {year}")
    assert out.startswith(f"**Ultime pronunce della Corte Costituzionale ({year})**"), out[:200]
    docs = _parse(out)
    assert len(docs) == 5, [d["head"] for d in docs]
    for d in docs:
        assert d.get("tipo") == "Sentenza" and d.get("anno") == str(year), d["head"]
        assert d.get("ECLI") == f"ECLI:IT:COST:{year}:{d['numero']}", d
    keys = [(_dmy(d["Deposito"]), int(d["numero"])) for d in docs]
    assert keys == sorted(keys, reverse=True), keys
    if year == 2026:
        first = docs[0]
        assert int(first["numero"]) >= LAST_2026["numero"], first
        assert _dmy(first["Deposito"]) >= _dmy(LAST_2026["deposito"]), first
        s153 = [d for d in docs if d["numero"] == str(LAST_2026["numero"])]
        if s153:  # still among the latest five
            assert s153[0].get("Decisione") == LAST_2026["decisione"]
            assert s153[0].get("Deposito") == LAST_2026["deposito"]
            assert s153[0].get("Relatore") == "Francesco Saverio Marini"

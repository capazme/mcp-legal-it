"""Smoke live of `cerca_giurisprudenza_unificata` against the four real sources.

The tool fans one query out to Italgiure (Cassazione), CeRDEF (tributaria),
Giustizia Amministrativa (TAR/CdS) and CELLAR (CGUE), then prints one section
per source and a final "Fonti consultate" line. What this file checks, on
documents whose identifiers are fixed and public:

- plan case 1 ("clausole abusive", cassazione + ue, 2022, sentenza, 20 per
  source): Cassazione decisions of 2022 only; the CGUE section must carry
  SPV Project 1503 (C-693/19, CELEX 62019CJ0693, ECLI:EU:C:2022:395,
  17 May 2022, Grand Chamber); the footer must count decisions, not rows.
- plan case 2 ("concessioni demaniali marittime", amministrativa, 2021): the
  portal still holds Cons. Stato, Ad. plen., 9 November 2021 n. 17
  (ECLI:IT:CDS:2021:17APLE, nrg 202105584) — canary — while the tool, which
  filters the year client-side on the few most recent hits, finds nothing; the
  answer must at least say why.
- `anno_a`: a 2025-2026 range reaches the administrative source as the exact
  year 2025 (`anno=anno_da`, `anno_a` dropped), so 2026 decisions vanish.
- all four sources in one call: four sections, four footer entries, and the
  Cassazione footer count equal to the count printed in its own section.
- tributaria: Cass. SS.UU. 9 December 2015 n. 24823, which the CeRDEF portal
  exposes (canary in `test_cerdef_live.py::test_portale_cerdef_espone_ssuu_24823_2015`).
- CGUE: a three-word query without commas becomes one title substring, so
  "clausole abusive consumatori" finds nothing although CELLAR titles read
  "Clausole abusive nei contratti stipulati con i consumatori" (canary on the
  source through `src.lib.cgue.search_giurisprudenza`); document types must
  match the title ("Ordinanza della Corte" is an order, not an AG opinion).
- the footer branch "risultati con criteri ampliati" (Italgiure auto-relaxation).

Reference values read on 2026-09-25 from the CELLAR SPARQL endpoint, the
Giustizia Amministrativa search form (sede Consiglio di Stato, numero
202100017) and the CeRDEF advanced search.

Each distinct input hits the network once per session (`_call`). A source
reported "non raggiungibile" skips the test: that is the source being down,
not the tool being wrong.

    .venv/bin/pytest tests/unit/test_giurisprudenza_unificata_live.py -m live -q -p no:cacheprovider -rfEs

Excluded from the default run (pyproject sets `-m 'not live'`).
"""

from __future__ import annotations

import asyncio
import functools
import re

import pytest

import src.server  # noqa: F401  (registers every tool module first: avoids a circular import)
from src.tools import giurisprudenza_unificata as gu_tools

pytestmark = pytest.mark.live

CASS = "Cassazione (Italgiure)"
TRIB = "Tributaria (CeRDEF)"
AMM = "Amministrativa (TAR/CdS)"
CGUE = "CGUE"

# SPV Project 1503 — Grand Chamber judgment of 17 May 2022 (joined C-693/19, C-831/19).
SPV_CELEX = "62019CJ0693"
SPV_ECLI = "ECLI:EU:C:2022:395"
SPV_DATE = "2022-05-17"

# Cons. Stato, Adunanza plenaria, sentenza 9 novembre 2021 n. 17 (concessioni balneari).
AP17_ECLI = "ECLI:IT:CDS:2021:17APLE"

# Plan case 1.
CASO_1 = dict(
    query="clausole abusive", fonti="cassazione,ue", anno_da="2022", anno_a="2022",
    tipo_provvedimento="sentenza", max_risultati=20,
)
# Plan case 2.
CASO_2 = dict(query="concessioni demaniali marittime", fonti="amministrativa", anno_da="2021", anno_a="2021")
# All four sources, with a two-year range.
TUTTE = dict(query="concessioni demaniali marittime", fonti="tutte", anno_da="2025", anno_a="2026")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@functools.lru_cache(maxsize=None)
def _call_cached(items: tuple) -> str:
    tool = gu_tools.cerca_giurisprudenza_unificata
    fn = getattr(tool, "fn", tool)
    return asyncio.run(fn(**dict(items)))


def _call(**kwargs) -> str:
    return _call_cached(tuple(sorted(kwargs.items())))


def _sezioni(out: str) -> dict[str, str]:
    """Map each '## <label>' heading to its body (footer stripped from the last one)."""
    out = out.split("**Fonti consultate**", 1)[0]
    sezioni = {}
    for chunk in re.split(r"^## ", out, flags=re.M)[1:]:
        label, _, body = chunk.partition("\n")
        body = body.strip()
        if body.endswith("---"):
            body = body[: -len("---")].strip()
        sezioni[label.strip()] = body
    return sezioni


def _footer(out: str) -> str:
    m = re.search(r"\*\*Fonti consultate\*\*: (.*)$", out, re.M)
    assert m, f"riga 'Fonti consultate' assente: {out[-400:]!r}"
    return m.group(1)


def _footer_voce(out: str, label: str) -> str | None:
    m = re.search(re.escape(label) + r" \(([^)]*)\)", _footer(out))
    return m.group(1) if m else None


def _body(out: str, label: str) -> str:
    """Body of one source's section; skip when that source was unreachable."""
    sezioni = _sezioni(out)
    assert label in sezioni, f"sezione '{label}' assente: {list(sezioni)}"
    body = sezioni[label]
    if body == "non raggiungibile" or body.startswith("errore:"):
        pytest.skip(f"{label} non raggiungibile: {body[:200]}")
    return body


_CGUE_FIELD = re.compile(r"^\*\*(CELEX|ECLI|Data|Titolo)\*\*: (.*)$", re.M)
_CGUE_TIPO = re.compile(r"^\*\*Corte\*\*: .*? \| \*\*Tipo\*\*: (\S+)", re.M)


def _cgue_docs(body: str) -> list[dict]:
    docs = []
    for block in body.split("\n### ")[1:]:
        doc = {"case_number": block.split("\n", 1)[0].strip()}
        for key, value in _CGUE_FIELD.findall(block):
            doc[key] = value.strip()
        m = _CGUE_TIPO.search(block)
        if m:
            doc["Tipo"] = m.group(1)
        docs.append(doc)
    return docs


_CASS_HEAD = re.compile(r"^### Cass\. .*?n\. \d+/(\d{4}), dep\. \d{2}/\d{2}/(\d{4})", re.M)
_GA_HEAD = re.compile(r"^### .* \((\d{4})\)\s*$", re.M)


# ---------------------------------------------------------------------------
# Plan case 1 — "clausole abusive", Cassazione + CGUE, 2022
# ---------------------------------------------------------------------------


def test_caso1_sezioni_cassazione_e_cgue_con_riepilogo():
    """Both requested sources get a section and a counted footer entry; no other source is queried."""
    out = _call(**CASO_1)
    assert out.startswith("# Ricerca giurisprudenziale unificata: clausole abusive"), out[:200]
    assert set(_sezioni(out)) == {CASS, CGUE}, list(_sezioni(out))
    for label in (CASS, CGUE):
        voce = _footer_voce(out, label)
        assert voce and re.fullmatch(r"\d+ risultati", voce), f"{label}: voce di riepilogo {voce!r}"


def test_caso1_cassazione_solo_decisioni_2022():
    """Italgiure honours anno_da/anno_a: every listed decision is of 2022 and deposited in 2022."""
    body = _body(_call(**CASO_1), CASS)
    heads = _CASS_HEAD.findall(body)
    assert heads, body[:800]
    assert all(anno == "2022" and dep == "2022" for anno, dep in heads), heads
    assert "sentenza" in body.lower()


def test_caso1_cgue_spv_project_1503():
    """SPV Project 1503 (C-693/19) matches 'clausole abusive' in 2022 and must be in the CGUE section.

    CELLAR lists 15 distinct 2022 judgments whose Italian title contains the words; SPV is
    the 12th by date (read 2026-09-25), so it fits in max_risultati=20.
    """
    docs = _cgue_docs(_body(_call(**CASO_1), CGUE))
    hits = [d for d in docs if d.get("CELEX") == SPV_CELEX]
    assert hits, (
        f"{SPV_CELEX} assente: {len(docs)} blocchi per {len({d.get('CELEX') for d in docs})} "
        f"decisioni distinte {[d.get('case_number') for d in docs]}"
    )
    assert hits[0].get("ECLI") == SPV_ECLI and hits[0].get("Data") == SPV_DATE


def test_caso1_cgue_riepilogo_conta_decisioni_distinte():
    """'CGUE (N risultati)' must count judgments, not SPARQL rows (one row per court agent/title)."""
    out = _call(**CASO_1)
    docs = _cgue_docs(_body(out, CGUE))
    distinte = {d.get("CELEX") for d in docs}
    assert _footer_voce(out, CGUE) == f"{len(distinte)} risultati", (
        f"riepilogo {_footer_voce(out, CGUE)!r}, blocchi {len(docs)}, decisioni distinte {len(distinte)}"
    )


# ---------------------------------------------------------------------------
# Plan case 2 — "concessioni demaniali marittime", Giustizia amministrativa, 2021
# ---------------------------------------------------------------------------


def test_portale_ga_espone_adunanza_plenaria_17_2021():
    """Canary on the source: Ad. plen. 17/2021 is reachable with sede + numero (2021 + 00017)."""
    from src.lib.giustizia_amm.client import search_provvedimenti

    try:
        docs = asyncio.run(search_provvedimenti(
            query="concessioni demaniali marittime", sede="consiglio_di_stato",
            anno="2021", numero="17", rows=20,
        ))
    except Exception as exc:  # network / portal failure: the source, not the tool
        pytest.skip(f"portale GA non raggiungibile: {exc}")
    assert any(d.ecli == AP17_ECLI for d in docs), [(d.numero, d.ecli) for d in docs]


def test_caso2_anno_2021_spiega_lo_zero():
    """With anno 2021 the administrative section is empty (client-side year filter on the newest hits).

    That limit is the portal's, but the source tool says so in a note ("non espone più un
    filtro per anno ..."); the unified tool must not replace that explanation with a bare
    "0 risultati".
    """
    body = _body(_call(**CASO_2), AMM)
    if _GA_HEAD.findall(body):
        assert all(a == "2021" for a in _GA_HEAD.findall(body)), body[:800]
        return
    assert "filtro" in body.lower() and "anno" in body.lower(), (
        f"zero risultati senza spiegazione del filtro per anno: {body!r}"
    )


# ---------------------------------------------------------------------------
# All four sources, 2025-2026
# ---------------------------------------------------------------------------


def test_tutte_quattro_sezioni_e_quattro_voci_di_riepilogo():
    """fonti='tutte' queries the four sources and reports each one in the footer."""
    out = _call(**TUTTE)
    assert list(_sezioni(out)) == [CASS, TRIB, AMM, CGUE], list(_sezioni(out))
    for label in (CASS, TRIB, AMM, CGUE):
        voce = _footer_voce(out, label)
        assert voce is not None, f"{label} assente dal riepilogo: {_footer(out)!r}"
        if voce in ("non raggiungibile", "errore"):
            pytest.skip(f"{label}: {voce}")


def test_tutte_amministrativa_intervallo_include_anno_a():
    """anno_da=2025, anno_a=2026: the administrative source must not be cut to the exact year 2025.

    The same query without years returns 2026 decisions (TAR Lazio, e.g. n. 202615210), so a
    2025-2026 range cannot legitimately be empty.
    """
    senza_anni = _body(_call(query=TUTTE["query"], fonti="amministrativa"), AMM)
    anni_disponibili = set(_GA_HEAD.findall(senza_anni))
    if not anni_disponibili & {"2025", "2026"}:
        pytest.skip(f"la fonte non restituisce decisioni 2025-2026 per la query: {anni_disponibili}")
    body = _body(_call(**TUTTE), AMM)
    anni = _GA_HEAD.findall(body)
    assert anni, (
        f"sezione amministrativa vuota per 2025-2026 mentre la fonte ha {sorted(anni_disponibili)}: {body!r}"
    )
    assert all("2025" <= a <= "2026" for a in anni), anni


def test_tutte_cassazione_riepilogo_coerente_con_la_sezione():
    """The footer count for Cassazione must equal the 'Trovate N decisioni' printed in its section."""
    out = _call(**TUTTE)
    body = _body(out, CASS)
    m = re.search(r"\*\*Trovate (\d+) decisioni\*\*", body)
    if not m:
        pytest.skip(f"sezione Cassazione senza conteggio: {body[:300]!r}")
    assert _footer_voce(out, CASS) == f"{m.group(1)} risultati", (
        f"riepilogo {_footer_voce(out, CASS)!r} contro 'Trovate {m.group(1)} decisioni' nella sezione"
        f" ({re.search(r'Raffinamento automatico[^*]*', body).group(0) if 'Raffinamento' in body else ''})"
    )


def test_tutte_cgue_tipo_coerente_col_titolo():
    """A block titled 'Ordinanza della Corte' is an ORDER, 'Sentenza' a JUDG, 'Conclusioni' an OPIN_AG.

    CELEX descriptors (sector 6): CJ judgment, CO order, CC Advocate General's opinion.
    """
    atteso = {"Ordinanza": "ORDER", "Sentenza": "JUDG", "Conclusioni": "OPIN_AG"}
    docs = _cgue_docs(_body(_call(**TUTTE), CGUE)) + _cgue_docs(_body(_call(**CASO_1), CGUE))
    errati = []
    for d in docs:
        primo = d.get("Titolo", "").split(" ", 1)[0]
        if primo in atteso and d.get("Tipo") != atteso[primo]:
            errati.append((d.get("CELEX"), d.get("Tipo"), d.get("Titolo", "")[:60]))
    assert not errati, f"tipo in contrasto col titolo: {sorted(set(errati))}"


# ---------------------------------------------------------------------------
# Tributaria — Cass. SS.UU. 24823/2015 (CeRDEF)
# ---------------------------------------------------------------------------


def test_tributaria_ssuu_24823_2015():
    """CeRDEF exposes Cass. SS.UU. 9.12.2015 n. 24823 on 'contraddittorio endoprocedimentale' (2015).

    The portal canary is test_cerdef_live.py::test_portale_cerdef_espone_ssuu_24823_2015.
    """
    out = _call(
        query="contraddittorio endoprocedimentale", fonti="tributaria", anno_da="2015", anno_a="2015",
        tipo_provvedimento="sentenza", max_risultati=10,
    )
    body = _body(out, TRIB)
    assert "24823" in body, f"riepilogo {_footer_voce(out, TRIB)!r}, sezione {body[:400]!r}"


# ---------------------------------------------------------------------------
# CGUE — a natural three-word query
# ---------------------------------------------------------------------------


def test_cgue_frase_di_tre_parole():
    """'clausole abusive consumatori' must reach the 2022 judgments on directive 93/13/EEC.

    Canary: CELLAR titles of 2022 judgments contain "Clausole abusive nei contratti stipulati
    con i consumatori" (SPV Project 1503 among them). The unified tool forwards the query to
    CGUE unchanged, where it becomes a single title substring.
    """
    from src.lib.cgue import search_giurisprudenza

    try:
        canary = asyncio.run(search_giurisprudenza(
            keywords=["clausole abusive nei contratti stipulati con i consumatori"],
            doc_type="sentenza", year_from="2022", year_to="2022", limit=50,
        ))
    except Exception as exc:
        pytest.skip(f"CELLAR non raggiungibile: {exc}")
    assert canary, "canary vuoto: la fonte non ha piu' titoli con quella dicitura"

    body = _body(_call(
        query="clausole abusive consumatori", fonti="ue", anno_da="2022", anno_a="2022",
        tipo_provvedimento="sentenza", max_risultati=20,
    ), CGUE)
    assert _cgue_docs(body), (
        f"zero risultati CGUE per una frase di tre parole mentre CELLAR ha "
        f"{len({c.celex for c in canary})} sentenze 2022 in tema: {body!r}"
    )


# ---------------------------------------------------------------------------
# Footer branch — Italgiure auto-relaxation
# ---------------------------------------------------------------------------


def test_riepilogo_criteri_ampliati():
    """A zero-hit quoted query relaxed by Italgiure is reported as 'risultati con criteri ampliati'."""
    out = _call(
        query='"clausole abusive" "concessioni demaniali marittime"', fonti="cassazione",
        anno_da="2022", anno_a="2022", max_risultati=3,
    )
    body = _body(out, CASS)
    if "Rilassamento automatico" not in body:
        pytest.skip(f"la fonte ha risposto senza rilassamento: {body[:300]!r}")
    assert _footer_voce(out, CASS) == "risultati con criteri ampliati", _footer(out)
    heads = _CASS_HEAD.findall(body)
    assert heads and all(a == "2022" for a, _ in heads), heads

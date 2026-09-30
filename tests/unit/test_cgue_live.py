"""Smoke live of the four CGUE tools against CELLAR (Publications Office of the EU).

What it checks, on documents whose identifiers are fixed and public:

- `cerca_giurisprudenza_cgue`: Schrems II (C-311/18, CELEX 62018CJ0311,
  ECLI:EU:C:2020:559, 16 July 2020, Grand Chamber) and SPV Project 1503
  (C-693/19, CELEX 62019CJ0693, ECLI:EU:C:2022:395, 17 May 2022): metadata,
  the official case-number form, duplicates, the `corte` filter, the OR
  semantics of comma-separated words and of `materia`.
- `giurisprudenza_cgue_su_norma`: directive 2006/112/EC (VAT) since 2025, and
  Article 101 TFEU written as "art. 101 TFUE" (the docstring's own example)
  versus "Articolo 101 TFUE" (the wording of CELLAR titles).
- `leggi_sentenza_cgue`: Italian text of Schrems II through the CELEX alias
  URI, including whether the operative part ("Per questi motivi ...
  dichiara") reaches the user.
- `ultime_sentenze_cgue`: latest judgments of the Court of Justice, and the
  lag of CELLAR against today (`src.lib._clock`).

Reference values: the CELLAR SPARQL notice and the CELLAR Italian HTML of each
decision (EUR-Lex answers automated requests with a WAF challenge, InfoCuria
is a JavaScript application: neither is readable here), read on 2026-09-25.

Every test that parses a tool answer is a real network call. Calls are cached
per session (`_call`), so each distinct input hits CELLAR once. A network
failure of the source ("non raggiungibile") skips the test instead of
failing it: that is the source being down, not the tool being wrong.

    .venv/bin/pytest tests/unit/test_cgue_live.py -m live -q -p no:cacheprovider -rfEs

Excluded from the default run (pyproject sets `-m 'not live'`).
"""

from __future__ import annotations

import asyncio
import functools
import re
from datetime import date, timedelta

import pytest

import src.server  # noqa: F401  (registers every tool module first: avoids a circular import)
from src.lib import _clock
from src.tools import cgue as cgue_tools

pytestmark = pytest.mark.live

NO_RESULTS = "Nessuna sentenza CGUE"

# Schrems II — Grand Chamber judgment of 16 July 2020.
SCHREMS_CELEX = "62018CJ0311"
SCHREMS_ECLI = "ECLI:EU:C:2020:559"
SCHREMS_DATE = "2020-07-16"
SCHREMS_CASE_OFFICIAL = "C-311/18"

# SPV Project 1503 — Grand Chamber judgment of 17 May 2022 (joined C-693/19, C-831/19).
SPV_CELEX = "62019CJ0693"
SPV_ECLI = "ECLI:EU:C:2022:395"
SPV_DATE = "2022-05-17"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@functools.lru_cache(maxsize=None)
def _call_cached(name: str, items: tuple) -> str:
    tool = getattr(cgue_tools, name)
    fn = getattr(tool, "fn", tool)
    return asyncio.run(fn(**dict(items)))


def _call(name: str, **kwargs) -> str:
    """Run a tool once per distinct input; skip when CELLAR is unreachable."""
    out = _call_cached(name, tuple(sorted(kwargs.items())))
    if out.startswith("**Errore**") and "non raggiungibile" in out:
        pytest.skip(f"CELLAR non raggiungibile per {name}{kwargs}: {out[:300]}")
    return out


_FIELD = re.compile(r"^\*\*(CELEX|ECLI|Data|Titolo|CELLAR URI)\*\*: (.*)$", re.M)
_COURT = re.compile(r"^\*\*Corte\*\*: (.*?) \| \*\*Tipo\*\*: (\S+)", re.M)


def _parse(out: str) -> list[dict]:
    """Split a search answer into one dict per '### <case number>' block."""
    docs = []
    for block in out.split("\n### ")[1:]:
        doc = {"case_number": block.split("\n", 1)[0].strip()}
        for key, value in _FIELD.findall(block):
            doc[key] = value.strip().strip("`")
        m = _COURT.search(block)
        if m:
            doc["Corte"], doc["Tipo"] = m.group(1), m.group(2)
        docs.append(doc)
    return docs


def _celex_set(docs: list[dict]) -> set[str]:
    return {d.get("CELEX", "") for d in docs}


def _normalize(text: str) -> str:
    # EU texts write case numbers with U+2011 (non-breaking hyphen): "C‑311/18".
    # Dates use U+00A0 (no-break space): "16 luglio 2020".
    return text.replace("\u2011", "-").replace("\u2010", "-").replace("\xa0", " ")


# ---------------------------------------------------------------------------
# cerca_giurisprudenza_cgue
# ---------------------------------------------------------------------------


def _schrems_search() -> str:
    return _call(
        "cerca_giurisprudenza_cgue",
        query="Schrems", tipo_documento="sentenza", anno_da="2020", anno_a="2020",
    )


def test_cerca_giurisprudenza_cgue_schrems_ii_metadati():
    """Plan case 1: Schrems II is found with CELEX, ECLI, date, parties and a CELLAR URI."""
    docs = _parse(_schrems_search())
    hits = [d for d in docs if d.get("CELEX") == SCHREMS_CELEX]
    assert hits, f"{SCHREMS_CELEX} assente: {docs}"
    doc = hits[0]
    assert doc.get("ECLI") == SCHREMS_ECLI
    assert doc.get("Data") == SCHREMS_DATE
    assert doc.get("Tipo") == "JUDG"
    assert "Grande Sezione" in doc.get("Titolo", "")
    assert "Data Protection Commissioner contro Facebook Ireland" in doc.get("Titolo", "")
    assert "Schrems" in doc.get("Titolo", "")
    assert doc.get("CELLAR URI", "").startswith("http://publications.europa.eu/resource/cellar/")


def test_cerca_giurisprudenza_cgue_numero_di_causa_in_forma_ufficiale():
    """The Court numbers cases 'C-311/18' (two-digit year); the tool prints 'C-311/2018'."""
    docs = [d for d in _parse(_schrems_search()) if d.get("CELEX") == SCHREMS_CELEX]
    assert docs, "Schrems II assente"
    assert docs[0]["case_number"] == SCHREMS_CASE_OFFICIAL, (
        f"numero di causa reso come {docs[0]['case_number']!r}, forma ufficiale {SCHREMS_CASE_OFFICIAL!r}"
    )


def test_cerca_giurisprudenza_cgue_nessun_duplicato():
    """One judgment must be listed once: 'Trovate N' has to count decisions, not SPARQL rows."""
    out = _schrems_search()
    docs = _parse(out)
    keys = [(d.get("CELEX"), d.get("CELLAR URI")) for d in docs]
    assert len(keys) == len(set(keys)), (
        f"{len(keys)} blocchi per {len(set(keys))} decisioni distinte; corti mostrate: "
        f"{[d.get('Corte') for d in docs]} — intestazione: {out.splitlines()[0]!r}"
    )


def test_cerca_giurisprudenza_cgue_filtro_corte_di_giustizia():
    """Plan case 2: SPV Project 1503 (C-693/19) with corte='corte_di_giustizia'."""
    out = _call(
        "cerca_giurisprudenza_cgue",
        query="clausole abusive, ingiunzione", corte="corte_di_giustizia",
        tipo_documento="sentenza", anno_da="2022", anno_a="2022", max_risultati=50,
    )
    assert NO_RESULTS not in out, (
        "il filtro corte='corte_di_giustizia' azzera la ricerca: "
        f"{out[:200]!r} (cfr. test_cerca_giurisprudenza_cgue_virgola_e_or, stessa ricerca senza corte)"
    )
    docs = [d for d in _parse(out) if d.get("CELEX") == SPV_CELEX]
    assert docs and docs[0].get("ECLI") == SPV_ECLI and docs[0].get("Data") == SPV_DATE


def test_cerca_giurisprudenza_cgue_virgola_e_or():
    """Comma-separated words are OR'ed: the two-word search is a superset of the one-word search."""
    both = _parse(_call(
        "cerca_giurisprudenza_cgue",
        query="clausole abusive, ingiunzione", tipo_documento="sentenza",
        anno_da="2022", anno_a="2022", max_risultati=50,
    ))
    one = _parse(_call(
        "cerca_giurisprudenza_cgue",
        query="clausole abusive", tipo_documento="sentenza",
        anno_da="2022", anno_a="2022", max_risultati=50,
    ))
    assert one, "nessun risultato per 'clausole abusive' nel 2022"
    assert _celex_set(one) <= _celex_set(both)
    assert len(_celex_set(both)) >= len(_celex_set(one))
    spv = [d for d in both if d.get("CELEX") == SPV_CELEX]
    assert spv, f"{SPV_CELEX} assente"
    assert spv[0].get("ECLI") == SPV_ECLI
    assert spv[0].get("Data") == SPV_DATE


def test_cerca_giurisprudenza_cgue_materia_restringe():
    """The docstring says `materia` 'Filtra per materia': adding it must not widen a search."""
    base = _celex_set(_parse(_schrems_search()))
    out = _call(
        "cerca_giurisprudenza_cgue",
        query="Schrems", tipo_documento="sentenza", anno_da="2020", anno_a="2020",
        materia="protezione_dati", max_risultati=50,
    )
    with_materia = _celex_set(_parse(out))
    assert with_materia <= base, (
        f"materia='protezione_dati' allarga la ricerca (parole in OR): {len(base)} decisione/i "
        f"senza materia, {len(with_materia)} con materia — es. {sorted(with_materia - base)[:5]}"
    )


# ---------------------------------------------------------------------------
# giurisprudenza_cgue_su_norma
# ---------------------------------------------------------------------------


def _check_result_list(docs: list[dict], anno_da: str) -> None:
    dates = [d.get("Data", "") for d in docs]
    assert all(d >= f"{anno_da}-01-01" for d in dates), dates
    assert dates == sorted(dates, reverse=True), dates
    for d in docs:
        assert d.get("CELEX", "").startswith("6"), d
        assert d.get("ECLI", "").startswith("ECLI:EU:"), d
        assert d.get("CELLAR URI", "").startswith("http://publications.europa.eu/resource/cellar/"), d


def test_giurisprudenza_cgue_su_norma_direttiva_iva_corte_di_giustizia():
    """Plan case 1: directive 2006/112/EC, Court of Justice only, since 2025."""
    out = _call(
        "giurisprudenza_cgue_su_norma",
        riferimento="direttiva 2006/112", corte="corte_di_giustizia", anno_da="2025", max_risultati=5,
    )
    assert NO_RESULTS not in out, (
        f"il filtro corte='corte_di_giustizia' azzera la ricerca: {out[:200]!r} "
        "(cfr. test_giurisprudenza_cgue_su_norma_direttiva_iva_senza_filtro_corte)"
    )
    docs = _parse(out)
    _check_result_list(docs, "2025")
    assert all(d.get("CELEX", "")[5:7] in ("CJ", "CC", "CO") for d in docs), docs


def test_giurisprudenza_cgue_su_norma_direttiva_iva_senza_filtro_corte():
    """Control for the case above: the same reference without `corte` does return decisions."""
    out = _call(
        "giurisprudenza_cgue_su_norma",
        riferimento="direttiva 2006/112", anno_da="2025", max_risultati=5,
    )
    assert NO_RESULTS not in out, out[:200]
    docs = _parse(out)
    assert docs
    _check_result_list(docs, "2025")


def test_giurisprudenza_cgue_su_norma_art_abbreviato():
    """Plan case 2: 'art. 101 TFUE' (docstring example) must find what 'Articolo 101 TFUE' finds."""
    out = _call("giurisprudenza_cgue_su_norma", riferimento="art. 101 TFUE", anno_da="2020")
    assert NO_RESULTS not in out, (
        "'art. 101 TFUE' non trova nulla: il riferimento e' cercato tale e quale come sottostringa "
        "del titolo, che scrive 'Articolo 101 TFUE' (cfr. test_giurisprudenza_cgue_su_norma_articolo_esteso)"
    )


def test_giurisprudenza_cgue_su_norma_articolo_esteso():
    """Control: the wording used by CELLAR titles returns decisions since 2020."""
    out = _call("giurisprudenza_cgue_su_norma", riferimento="Articolo 101 TFUE", anno_da="2020")
    assert NO_RESULTS not in out, out[:200]
    docs = _parse(out)
    assert docs
    _check_result_list(docs, "2020")
    assert any("articolo 101" in d.get("Titolo", "").lower() for d in docs), docs


# ---------------------------------------------------------------------------
# leggi_sentenza_cgue
# ---------------------------------------------------------------------------


def _schrems_text() -> str:
    return _call(
        "leggi_sentenza_cgue",
        cellar_uri=f"http://publications.europa.eu/resource/celex/{SCHREMS_CELEX}",
    )


def test_leggi_sentenza_cgue_schrems_ii_testo_italiano():
    """Plan case: CELEX alias resolves to the Italian text of Schrems II."""
    out = _normalize(_schrems_text())
    assert not out.startswith("**Errore**"), out[:300]
    assert "Testo non disponibile" not in out, out[:300]
    assert out.startswith(f"# {SCHREMS_CELEX}")
    assert len(out) >= 20000, len(out)
    for phrase in (
        "SENTENZA DELLA CORTE (Grande Sezione)",
        "16 luglio 2020",
        "Nella causa C-311/18",
        "Data Protection Commissioner",
        "Maximillian Schrems",
        "Decisione di esecuzione (UE) 2016/1250",
        "Decisione 2010/87/UE",
    ):
        assert phrase in out, f"{phrase!r} assente dal testo"


def test_leggi_sentenza_cgue_schrems_ii_dispositivo():
    """The operative part (invalidity of decision 2016/1250) must reach the reader."""
    out = _schrems_text()
    m = re.search(r"Testo troncato a (\d+) caratteri su (\d+) totali", out)
    assert "Per questi motivi" in out and "invalida" in out.split("Per questi motivi")[-1], (
        "dispositivo assente: "
        + (f"testo troncato a {m.group(1)} caratteri su {m.group(2)}, il dispositivo sta in coda"
           if m else "nessuna nota di troncamento")
    )


# ---------------------------------------------------------------------------
# ultime_sentenze_cgue
# ---------------------------------------------------------------------------


def test_ultime_sentenze_cgue_corte_di_giustizia():
    """Plan case: five latest judgments of the Court of Justice."""
    out = _call(
        "ultime_sentenze_cgue", corte="corte_di_giustizia", tipo_documento="sentenza", max_risultati=5,
    )
    assert NO_RESULTS not in out, (
        f"il filtro corte='corte_di_giustizia' azzera l'elenco: {out[:200]!r} "
        "(cfr. test_ultime_sentenze_cgue_senza_filtro_corte)"
    )
    docs = _parse(out)
    assert all(d.get("CELEX", "")[5:7] == "CJ" for d in docs), docs
    assert all(d.get("ECLI", "").startswith("ECLI:EU:C:") for d in docs), docs


def test_ultime_sentenze_cgue_senza_filtro_corte():
    """Control: latest judgments, newest first, not after today and at most 30 days old."""
    out = _call("ultime_sentenze_cgue", tipo_documento="sentenza", max_risultati=10)
    assert NO_RESULTS not in out, out[:200]
    docs = _parse(out)
    assert docs
    dates = [d.get("Data", "") for d in docs]
    assert dates == sorted(dates, reverse=True), dates
    today: date = _clock.today()
    newest = date.fromisoformat(dates[0])
    assert newest <= today, (newest, today)
    # CELLAR usually lists a judgment the day after delivery; 30 days only flags a stalled feed.
    assert newest >= today - timedelta(days=30), f"ultima sentenza del {newest}, oggi {today}"
    assert all(d.get("Tipo") == "JUDG" for d in docs), docs

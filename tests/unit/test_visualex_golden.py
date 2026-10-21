"""VisuaLex's source convention (``conventions/sources/golden.json``), copied as a fixture.

VisuaLex stays the source of the golden file: the copy is pinned by its sha256 to
the VisuaLex commit it was read at, so a change there shows up here as a failing
pin, to be copied over on purpose (``tests/fixtures/visualex/README.md``).

The norms whose identity mcp-legal-it builds already must match it; the others
are listed in ``LACUNE`` with the migration step that closes them. A gap that
closes makes its test fail: remove it from the list.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from mcp_legal_it.lib.visualex.models import Norma, NormaVisitata

GOLDEN = Path(__file__).resolve().parents[1] / "fixtures" / "visualex" / "golden.json"
#: VisuaLexAPI conventions/sources/golden.json read at eca698dc (last changed in 65ee1aa7).
GOLDEN_SHA256 = "b05e9c511751b39ab7107e98b8c6b98073041e57a5e9ba35c32d7ba93eda288e"

#: Norm ids whose identity mcp-legal-it does not build yet, and why.
LACUNE = {
    "dlgs-81-2008-annex-a": "the annex in the act's URN (:A): Normattiva channel PR",
    "l-184-1983-6-year-only": "a year-only act has no URN in the convention: dates PR",
    "dpcm-2020-03-08-1": "an act with no number keeps a trailing ';': URN PR",
    "gdpr-5": "EU identity as celex:… (sources.eu_identity): citations/URN PR",
    "nis2-21": "EU identity as celex:…: citations/URN PR",
    "tfue-101": "EU identity as celex:…: citations/URN PR",
}


def _golden() -> dict:
    return json.loads(GOLDEN.read_text(encoding="utf-8"))


def _confronti(norma: dict) -> list[tuple[str, str | None, str]]:
    """``(kind, expected, built)`` for the act and the article identity the file asserts."""
    i = norma["input"]
    ide = norma.get("identity", {})
    n = Norma(i["tipo_atto"], i.get("data", ""), i.get("numero_atto", ""))
    out = []
    for kind in ("act", "article"):
        atteso = ide.get(kind)
        if not atteso or atteso["status"] not in ("decided", "current", "proposed"):
            continue
        if kind == "article" and not i.get("numero_articolo"):
            continue
        costruito = NormaVisitata(n, i["numero_articolo"]).url() if kind == "article" else n.url()
        out.append((kind, atteso["value"], costruito or None))
    return out


def test_the_copy_is_visualex_s_file():
    assert hashlib.sha256(GOLDEN.read_bytes()).hexdigest() == GOLDEN_SHA256


def test_every_gap_names_a_norm_of_the_file():
    ids = {n["id"] for n in _golden()["norms"]}
    assert set(LACUNE) <= ids


@pytest.mark.parametrize("norma", _golden()["norms"], ids=lambda n: n["id"])
def test_norm_identity(norma):
    confronti = _confronti(norma)
    if not confronti:
        pytest.skip("no identity asserted for this norm")
    diversi = [(k, a, c) for k, a, c in confronti if a != c]
    if norma["id"] in LACUNE:
        assert diversi, f"gap closed, remove it from LACUNE: {norma['id']}"
        pytest.xfail(LACUNE[norma["id"]])
    assert not diversi, diversi

"""Act types: every key of the search table is reachable, and VisuaLex's rows are all here.

``normalize_act_type`` follows VisuaLex's (``tools/text_op.py`` at ``eca698dc``,
MPL-2.0): literal key, then case-insensitive, then without spaces. The table keeps
VisuaLex's rows, the source convention's short forms among them: before them
"d.l. 18/2020" built ``urn:nir:stato:d.l.:…`` and "l. cost." built ``l..cost.``.
"""

from __future__ import annotations

import pytest

from mcp_legal_it.lib.visualex.map import (
    NORMATTIVA_SEARCH,
    NORMATTIVA_URN_CODICI,
    codice_urn,
    normalize_act_type,
)
from mcp_legal_it.lib.visualex.models import Norma, NormaVisitata

#: The rows VisuaLex's NORMATTIVA_SEARCH had and this table lacked (at eca698dc).
RIGHE_VISUALEX_RICERCA = {
    "c.p.a": "codice del processo amministrativo",
    "c.p.a.": "codice del processo amministrativo",
    "codice del Terzo settore": "codice del Terzo settore",
    "disposizioni per l'attuazione del Codice civile e disposizioni transitorie":
        "disposizioni per l'attuazione del Codice civile e disposizioni transitorie",
    "disposizioni per l'attuazione del Codice di procedura civile e disposizioni transitorie":
        "disposizioni per l'attuazione del Codice di procedura civile e disposizioni transitorie",
    "d.l.": "decreto legge",
    "decreto-legge": "decreto legge",
    "l. cost.": "legge costituzionale",
    "l.cost.": "legge costituzionale",
    "l.cost": "legge costituzionale",
    "legge cost.": "legge costituzionale",
    "l. costituzionale": "legge costituzionale",
    "legge costituzionale": "legge costituzionale",
    "r.d.l.": "regio decreto legge",
    "regio decreto legge": "regio decreto legge",
    "regio decreto-legge": "regio decreto legge",
    "d.lgs.lgt.": "decreto legislativo luogotenenziale",
    "decreto legislativo luogotenenziale": "decreto legislativo luogotenenziale",
}

RIGHE_VISUALEX_CODICI = {
    "regolamento per l'esecuzione del codice di procedura penale": "decreto.ministeriale:1989-09-30;334",
    "regolamento di attuazione del Codice della proprietà industriale": "decreto.ministeriale:2010-01-13;33",
}


class TestNothingOfVisuaLexIsMissing:
    @pytest.mark.parametrize("key,value", sorted(RIGHE_VISUALEX_RICERCA.items()))
    def test_search_rows(self, key, value):
        assert NORMATTIVA_SEARCH.get(key) == value

    @pytest.mark.parametrize("key,value", sorted(RIGHE_VISUALEX_CODICI.items()))
    def test_code_rows(self, key, value):
        assert NORMATTIVA_URN_CODICI.get(key) == value
        assert codice_urn(key.lower()) == value


class TestReachability:
    def test_no_key_is_unreachable(self):
        unreachable = [k for k in NORMATTIVA_SEARCH if normalize_act_type(k) != NORMATTIVA_SEARCH[k]]
        assert not unreachable, unreachable[:5]

    @pytest.mark.parametrize("raw,expected", [
        ("D.L.", "decreto legge"),
        ("Codice del terzo settore", "codice del Terzo settore"),
        ("cc", "codice civile"),
        ("TFUE", "TFUE"),
        ("legge", "legge"),
    ])
    def test_case_and_spacing_do_not_matter(self, raw, expected):
        assert normalize_act_type(raw) == expected


class TestUrns:
    @pytest.mark.parametrize("tipo,data,numero,urn", [
        ("d.l.", "2020-03-17", "18", "urn:nir:stato:decreto.legge:2020-03-17;18~art1"),
        ("decreto-legge", "2020-03-17", "18", "urn:nir:stato:decreto.legge:2020-03-17;18~art1"),
        ("l. cost.", "2001-10-18", "3", "urn:nir:stato:legge.costituzionale:2001-10-18;3~art1"),
        ("r.d.l.", "1938-11-17", "1728", "urn:nir:stato:regio.decreto.legge:1938-11-17;1728~art1"),
        ("d.lgs.lgt.", "1944-09-27", "159", "urn:nir:stato:decreto.legislativo.luogotenenziale:1944-09-27;159~art1"),
    ])
    def test_short_forms_build_the_act_s_urn(self, tipo, data, numero, urn):
        assert NormaVisitata(Norma(tipo, data, numero), "1").url().endswith(urn)

    def test_the_new_codes_build_their_urn(self):
        nv = NormaVisitata(Norma("regolamento di attuazione del Codice della proprietà industriale", "", ""), "1")
        assert nv.url().endswith("urn:nir:stato:decreto.ministeriale:2010-01-13;33~art1")


def test_the_tourism_code_is_the_decree_s_annex():
    """D.Lgs. 79/2011 approves the Codice del turismo as Allegato 1: without ":1"
    Normattiva serves the decree's own art. 3 («Abrogazioni») for the code's art. 3."""
    nv = NormaVisitata(Norma("codice del turismo", "", ""), "3")
    assert nv.url().endswith("urn:nir:stato:decreto.legislativo:2011-05-23;79:1~art3")

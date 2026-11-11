"""The act types of 1944-1948 can be cited (G-440).

Decreti luogotenenziali, decreti and decreti legislativi del Capo provvisorio dello Stato:
the library refused them once their headings were known (a «d.lgs. 1577/1947» is the
D.Lgs.C.P.S. 14 dicembre 1947, n. 1577, the legge Basevi), but had no spelling to cite
them. Each URN kind is the one Normattiva's own export gives the act (FRBRalias urn:nir,
measured 11 November 2026); each type is checked against its own heading.
"""

import pytest

from mcp_legal_it.core.riferimenti import _resolve_act
from mcp_legal_it.lib.visualex.models import Norma

DLGSCPS = "decreto legislativo del capo provvisorio dello stato"
DCPS = "decreto del capo provvisorio dello stato"
DLGT = "decreto luogotenenziale"


@pytest.mark.parametrize("citazione, tipo, data, numero", [
    ("D.Lgs.C.P.S. 1577/1947", DLGSCPS, "1947", "1577"),
    ("d.lgs.c.p.s. 14 dicembre 1947, n. 1577", DLGSCPS, "1947-12-14", "1577"),
    ("decreto legislativo del Capo provvisorio dello Stato 13 settembre 1946, n. 233", DLGSCPS, "1946-09-13", "233"),
    ("D.C.P.S. 659/1946", DCPS, "1946", "659"),
    ("d.c.p.s. 6 settembre 1946, n. 659", DCPS, "1946-09-06", "659"),
    ("decreto del Capo provvisorio dello Stato 6 settembre 1946, n. 659", DCPS, "1946-09-06", "659"),
    ("D.Lgt. 512/1946", DLGT, "1946", "512"),
    ("d. lgt. 30 marzo 1946, n. 512", DLGT, "1946-03-30", "512"),
    ("decreto luogotenenziale 10 agosto 1944, n. 208", DLGT, "1944-08-10", "208"),
])
def test_the_types(citazione, tipo, data, numero):
    assert _resolve_act(citazione) == {"tipo_atto": tipo, "data": data, "numero_atto": numero}


@pytest.mark.parametrize("citazione, tipo", [
    ("D.Lgs.Lgt. 98/1946", "decreto legislativo luogotenenziale"),
    ("d.l.lgt. 151/1944", "decreto legislativo luogotenenziale"),
    ("D.Lgs. 81/2008", "decreto legislativo"),
    ("D.L. 18/2020", "decreto legge"),
    ("D.P.C.M. 159/2013", "decreto del presidente del consiglio dei ministri"),
    ("r.d.lgs. 511/1946", "regio decreto legislativo"),
])
def test_the_neighbouring_types_are_unchanged(citazione, tipo):
    assert _resolve_act(citazione)["tipo_atto"] == tipo


@pytest.mark.parametrize("tipo, urn", [
    (DLGSCPS, "decreto.legislativo.del.capo.provvisorio.dello.stato:1947-12-14;1577"),
    (DCPS, "decreto.del.capo.provvisorio.dello.stato:1947-12-14;1577"),
    (DLGT, "decreto.luogotenenziale:1947-12-14;1577"),
])
def test_the_urn_kinds_are_normattivas(tipo, urn):
    assert Norma(tipo_atto=tipo, data="1947-12-14", numero_atto="1577").url().endswith(f"urn:nir:stato:{urn}")


def test_the_legge_basevi():
    assert _resolve_act("legge Basevi") == {"tipo_atto": DLGSCPS, "data": "1947-12-14", "numero_atto": "1577"}

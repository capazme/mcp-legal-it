"""Codes whose articles sit in an annex of the approving decree.

Without the annex suffix Normattiva serves the decree's own articles: "art. 3
codice del turismo" came back as the decree's art. 3 «Abrogazioni». Found live
on 21/10/2026 for seven rows (see test_codici_urn_live.py, the gate).
"""

import pytest

from mcp_legal_it.lib.visualex import map as m
from mcp_legal_it.lib.visualex.models import Norma, NormaVisitata


@pytest.mark.parametrize("nome, urn", [
    ("codice del turismo", "decreto.legislativo:2011-05-23;79:1"),
    ("codici penali militari di pace e di guerra", "regio.decreto:1941-02-20;303:1"),
    ("norme di attuazione, di coordinamento e transitorie del codice di procedura penale",
     "decreto.legislativo:1989-07-28;271:1"),
    ("approvazione del Regolamento per l'esecuzione del Codice della navigazione (Navigazione marittima)",
     "decreto.del.presidente.della.repubblica:1952-02-15;328:1"),
])
def test_code_urn_names_the_annex(nome, urn):
    assert m.NORMATTIVA_URN_CODICI[nome] == urn


@pytest.mark.parametrize("tipo, data, numero, atteso", [
    ("decreto del presidente della repubblica", "1988-09-22", "448", ";448:1~art3"),
    ("decreto del presidente della repubblica", "1988", "448", ";448:1~art3"),  # year only
    ("regio decreto", "1931-06-18", "773", ";773:1~art3"),
    ("decreto legislativo", "1990-10-31", "346", ";346:1~art3"),
])
def test_article_of_an_act_whose_text_is_annexed(tipo, data, numero, atteso):
    url = NormaVisitata(norma=Norma(tipo_atto=tipo, data=data, numero_atto=numero), numero_articolo="3").url()
    assert url.endswith(atteso), url


def test_other_acts_and_annex_references_are_untouched():
    assert Norma(tipo_atto="decreto legislativo", data="2003-06-30", numero_atto="196").url(article="13") \
        .endswith(";196~art13")
    # the act itself, and an annex cited by name, keep the bare URN
    assert Norma(tipo_atto="regio decreto", data="1931-06-18", numero_atto="773").url().endswith(";773")
    assert ":1~" not in Norma(tipo_atto="decreto legislativo", data="1990-10-31", numero_atto="346").url(
        article="allegato A")


@pytest.mark.parametrize("reference, urn", [
    ("art. 3 c.p.m.p.", "regio.decreto:1941-02-20;303:1~art3"),
    ("art. 47 cpmp", "regio.decreto:1941-02-20;303:1~art47"),
    ("art. 3 c.p.m.g.", "regio.decreto:1941-02-20;303:2~art3"),
    ("art. 3 codice penale militare di guerra", "regio.decreto:1941-02-20;303:2~art3"),
    ("art. 4 disp. att. c.p.p.", "decreto.legislativo:1989-07-28;271:1~art4"),
    ("art. 4 att. c.p.p.", "decreto.legislativo:1989-07-28;271:1~art4"),
    # unchanged neighbours
    ("art. 125 disp. att. c.p.c.", "regio.decreto:1941-12-18;1368:1~art125"),
    ("art. 3 c.p.p.", "decreto.del.presidente.della.repubblica:1988-09-22;447~art3"),
])
def test_abbreviations_resolve_to_the_right_code(reference, urn):
    import mcp_legal_it.server  # noqa: F401
    from mcp_legal_it.core.norme import _build_nv, _parse_reference, _resolve_act

    article, act = _parse_reference(reference)
    assert _build_nv(_resolve_act(act), article).url().endswith(urn)


@pytest.mark.parametrize("tipo, part", [
    ("codice penale militare di guerra", "codice penale militare di guerra"),
    ("codice penale militare di pace", "codice penale militare di pace"),
    ("preleggi", "preleggi"),
    ("codice civile", None),
])
def test_akn_part_of_the_military_codes(tipo, part):
    # R.D. 303/1941 exports both codes as parts: without the hint the dominant one
    # (di pace) answered "art. 3 c.p.m.g." with the art. 3 of the code of peace.
    from mcp_legal_it.lib.visualex.scraper import _akn_part_hint

    assert _akn_part_hint(Norma(tipo_atto=tipo)) == part

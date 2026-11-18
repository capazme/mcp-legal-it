"""Codes whose articles sit in an annex of the approving decree.

Without the annex suffix Normattiva serves the decree's own articles: "art. 3
codice del turismo" came back as the decree's art. 3 «Abrogazioni». Found live
on 21/10/2026 for seven rows (see test_codici_urn_live.py, the gate).
"""

import pytest

from src.lib.visualex import map as m
from src.lib.visualex.models import Norma, NormaVisitata


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
    ("regio decreto", "1942-03-16", "267", ";267:1~art3"),  # legge fallimentare
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


def test_legge_fallimentare_reads_the_annexed_law_not_the_approving_decree():
    # Without the annex the AKN fallback read ;267~art1, the decree's own art. 1,
    # and answered «inesistente» from art. 3 on.
    norma = Norma(tipo_atto="regio decreto", data="1942-03-16", numero_atto="267")
    assert norma.url(article="1").endswith("regio.decreto:1942-03-16;267:1~art1")
    assert m.articolato_in_allegato("regio.decreto", "1942-03-16", "267") == "1"

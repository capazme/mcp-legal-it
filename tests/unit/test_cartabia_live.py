"""Live gate: the numbers the deadline tools hard-code are the ones the vigente c.p.c. states.

The procedural tools in `src/tools/scadenze_termini.py` and `src/tools/procedura_civile.py`
encode day counts (40/20/10 for the memorie ex art. 171-ter, 60/30/15 for the atti ex art.
189, 10 and 70 for the costituzione ex artt. 165-166, 30/60 and six months ex artt. 325-327,
10 and 40 for the rito semplificato ex art. 281-undecies, 20+10 ex art. 281-duodecies) and the
1-31 August window of L. 742/1969. A correttivo can move any of them without touching this
repository, so this file reads each article through `cite_law()` (Normattiva, vigente text)
and checks the words the code relies on. It needs the network and is skipped by default:

    pytest tests/unit/test_cartabia_live.py -m live -q
"""

from __future__ import annotations

import asyncio
import json
import re

import pytest

pytestmark = pytest.mark.live


def _testo(reference: str) -> str:
    import src.server  # noqa: F401  (registers every tool module first: avoids a circular import)
    from src.tools.legal_citations import cite_law

    fn = getattr(cite_law, "fn", cite_law)
    raw = asyncio.run(fn(reference=reference, formato="json"))
    payload = json.loads(raw)
    assert not payload.get("errore"), payload
    testo = payload.get("testo") or ""
    assert testo, payload
    return re.sub(r"\s+", " ", testo).lower()


def _assert_words(reference: str, *words: str) -> None:
    testo = _testo(reference)
    missing = [w for w in words if w.lower() not in testo]
    assert not missing, f"{reference}: il testo vigente non contiene {missing}"


def test_memorie_171_ter_sono_40_20_10_giorni():
    _assert_words("art. 171-ter c.p.c.", "quaranta giorni", "venti giorni", "dieci giorni")


def test_atti_per_la_decisione_189_sono_60_30_15_giorni():
    _assert_words("art. 189 c.p.c.", "sessanta giorni", "trenta giorni", "quindici giorni")


def test_art_190_e_abrogato():
    import src.server  # noqa: F401
    from src.tools.legal_citations import cite_law

    fn = getattr(cite_law, "fn", cite_law)
    raw = asyncio.run(fn(reference="art. 190 c.p.c.", formato="json"))
    payload = json.loads(raw)
    testo = re.sub(r"\s+", " ", (payload.get("testo") or "")).lower()
    assert payload.get("errore") or "abrogat" in testo, payload


def test_costituzione_attore_e_convenuto_165_166():
    _assert_words("art. 165 c.p.c.", "dieci giorni")
    _assert_words("art. 166 c.p.c.", "settanta giorni")


def test_appello_347_rinvia_ai_termini_del_tribunale():
    _assert_words("art. 347 c.p.c.", "tribunale")
    _assert_words("art. 343 c.p.c.", "comparsa di risposta")


def test_impugnazioni_325_327():
    _assert_words("art. 325 c.p.c.", "trenta giorni", "sessanta giorni")
    _assert_words("art. 327 c.p.c.", "sei mesi")
    _assert_words("art. 47 c.p.c.", "trenta giorni")


def test_rito_semplificato_281_undecies_e_duodecies():
    _assert_words("art. 281-undecies c.p.c.", "quaranta giorni", "dieci giorni")
    _assert_words("art. 281-duodecies c.p.c.", "venti giorni", "dieci giorni")


def test_sospensione_feriale_1_31_agosto():
    _assert_words("art. 1 L. 742/1969", "1° agosto", "31 agosto")


def test_competenza_giudice_di_pace_art_7():
    _assert_words("art. 7 c.p.c.", "diecimila", "venticinquemila")


def test_mediazione_obbligatoria_art_5_dlgs_28_2010():
    _assert_words(
        "art. 5 D.Lgs. 28/2010",
        "condominio", "franchising", "subfornitura", "societ", "somministrazione",
    )


def test_art_155_proroga_al_giorno_non_festivo():
    _assert_words("art. 155 c.p.c.", "festivo", "sabato")


def test_prescrizione_penale_161_bis_e_344_bis():
    _assert_words("art. 161-bis c.p.", "primo grado")
    _assert_words("art. 344-bis c.p.p.", "due anni", "un anno")


def test_pignoramento_pensioni_art_545():
    _assert_words("art. 545 c.p.c.", "assegno sociale", "1.000 euro")


def test_contributo_unificato_art_13_e_art_9():
    _assert_words("art. 13 DPR 115/2002", "43", "518", "1.686")
    _assert_words("art. 9 DPR 115/2002", "tre volte")

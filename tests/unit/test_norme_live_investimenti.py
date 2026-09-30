"""Live gate (strategy `solo_norma`, group `investimenti`): the norms behind
`confronto_investimenti`.

Phase 4 of the avvocatoandreani.it benchmark. The site has no equivalent calculator, so the
tool is checked against the vigente text of the norms it applies (read on Normattiva through
`cite_law`, consulted on 2026-09-25) and against hand arithmetic on the plan cases:

* 26% on interest and other capital income: art. 3 co. 1 D.L. 66/2014, also for bank and
  postal deposits (co. 7 lett. b), i.e. `_ALIQUOTA_ALTRO` / tipo_tassazione 'altro';
* 12,50% on titoli di Stato ed equiparati: art. 2 co. 1 D.Lgs. 239/1996, which art. 3 co. 2
  lett. a) D.L. 66/2014 leaves out of the 26% (titoli of art. 31 D.P.R. 601/1973: debito
  pubblico, buoni postali di risparmio), i.e. `_ALIQUOTA_TITOLI_STATO` / 'titoli_stato';
* the tax falls on positive income only: art. 45 co. 1 TUIR (reddito di capitale =
  "interessi, utili o altri proventi percepiti"), art. 3 co. 1 D.L. 66/2014 (ritenute and
  imposte sostitutive "sugli interessi, premi e ogni altro provento").

Two divergences were genuine and are fixed in the tool (phase 3); their tests stay as
regression guards: a negative gross yield used to produce a negative tax (a refund no norm
grants), and a titolo di Stato whose `tipo_tassazione` was not spelt exactly 'titoli_stato'
was silently taxed at 26% instead of 12,50%. Since the fix an unknown regime (e.g. 'esente')
is refused with an `errore` instead of falling back to 26%, so the conto deposito case below
uses the recognised 'altro'.

Run:
    .venv/bin/pytest tests/unit/test_norme_live_investimenti.py -m live -q -p no:cacheprovider -rfEs
Needs the network (Normattiva).
"""

from __future__ import annotations

import functools

import pytest

import src.server  # noqa: F401  (registers every tool module first: avoids a circular import)
from src.tools import investimenti as modulo
from src.tools.investimenti import confronto_investimenti
from tests.unit import _norme_live  # module import: a bare `testo_vigente` would be collected as a test

pytestmark = pytest.mark.live

_confronto = getattr(confronto_investimenti, "fn", confronto_investimenti)

DL_66_2014 = "art. 3 D.L. 66/2014"
DLGS_239_1996 = "art. 2 D.Lgs. 239/1996"
DPR_601_1973 = "art. 31 D.P.R. 601/1973"
TUIR_45 = "art. 45 TUIR"


@functools.lru_cache(maxsize=None)
def _testo(reference: str) -> str:
    """One Normattiva request per norm for the whole module."""
    return _norme_live.testo_vigente(reference)


def _assert_testo(reference: str, *frasi: str) -> None:
    missing = _norme_live.contiene(_testo(reference), *frasi)
    assert not missing, f"{reference}: il testo vigente non contiene {missing}"


def _voce(risultato: dict, nome: str) -> dict:
    assert "errore" not in risultato, risultato
    return {v["nome"]: v for v in risultato["classifica"]}[nome]


def _atteso(importo: float, lordo_pct: float, aliquota_pct: float, anni: int) -> dict:
    """Hand arithmetic: compound gross amount, one substitute tax on the interest at maturity."""
    montante_lordo = importo * (1 + lordo_pct / 100) ** anni
    imposta = (montante_lordo - importo) * aliquota_pct / 100
    return {
        "rendimento_netto_pct": lordo_pct * (1 - aliquota_pct / 100),
        "montante_lordo": montante_lordo,
        "imposta": imposta,
        "montante_netto": montante_lordo - imposta,
        "guadagno_netto": montante_lordo - imposta - importo,
    }


def _assert_voce(voce: dict, atteso: dict) -> None:
    assert voce["rendimento_netto_pct"] == pytest.approx(atteso["rendimento_netto_pct"], abs=1e-4)
    for chiave in ("montante_lordo", "imposta", "montante_netto", "guadagno_netto"):
        assert voce[chiave] == pytest.approx(atteso[chiave], abs=0.01), chiave


# --- the rates on the vigente text ------------------------------------------------------

def test_aliquota_26_art3_co1_dl_66_2014():
    """Art. 3 co. 1 D.L. 66/2014: ritenute and imposte sostitutive on the income of art. 44
    TUIR "sono stabilite nella misura del 26 per cento" -> tipo_tassazione 'altro'."""
    _assert_testo(
        DL_66_2014,
        "le ritenute e le imposte sostitutive sugli interessi, premi e ogni altro provento di cui "
        "all'articolo 44 del testo unico delle imposte sui redditi",
        "sono stabilite nella misura del 26 per cento",
    )
    assert modulo._ALIQUOTA_ALTRO == 26.0
    r = _confronto(importo=10000, investimenti=[
        {"nome": "Corp", "rendimento_lordo_pct": 4.0, "tipo_tassazione": "altro", "durata_anni": 1},
    ])
    assert _voce(r, "Corp")["aliquota_pct"] == 26.0


def test_aliquota_12_50_art2_co1_dlgs_239_1996_art3_co2_lett_a_dl_66_2014():
    """Art. 2 co. 1 D.Lgs. 239/1996 taxes titoli art. 31 D.P.R. 601/1973 ed equiparati "nella
    misura del 12,50 per cento"; art. 3 co. 2 lett. a) D.L. 66/2014 keeps them out of the 26%;
    art. 31 D.P.R. 601/1973 lists titoli del debito pubblico and buoni postali di risparmio."""
    _assert_testo(
        DLGS_239_1996,
        "nella misura del 12,50 per cento",
        "articolo 31 del decreto del presidente della repubblica 29 settembre 1973, n. 601, ed equiparati",
    )
    _assert_testo(
        DL_66_2014,
        "la disposizione di cui al comma 1 non si applica",
        "obbligazioni e altri titoli di cui all'articolo 31 del decreto del presidente della "
        "repubblica 29 settembre 1973, n. 601 ed equiparati",
        "obbligazioni emesse dagli stati inclusi nella lista",
    )
    _assert_testo(DPR_601_1973, "titoli del debito pubblico", "buoni postali di risparmio")
    assert modulo._ALIQUOTA_TITOLI_STATO == 12.5
    r = _confronto(importo=10000, investimenti=[
        {"nome": "BTP", "rendimento_lordo_pct": 4.0, "tipo_tassazione": "titoli_stato", "durata_anni": 1},
    ])
    assert _voce(r, "BTP")["aliquota_pct"] == 12.5


def test_conto_deposito_26_art3_co7_lett_b_dl_66_2014():
    """Plan case 3: 'Conto deposito'. Interest on bank and postal deposits is taxed at 26%
    (art. 3 co. 7 lett. b D.L. 66/2014), i.e. tipo_tassazione 'altro': 10.000 x 1,03^2 =
    10.609, imposta 158,34, netto 10.450,66. The plan wrote the regime as 'esente', which is
    no regime the tool knows: it expects an explicit error or warning, and the tool now
    refuses it instead of silently applying 26% (that would be wrong on a truly exempt
    instrument)."""
    _assert_testo(
        DL_66_2014,
        "interessi e agli altri proventi derivanti da conti correnti e depositi bancari e postali",
    )
    r = _confronto(importo=10000, investimenti=[
        {"nome": "Conto deposito", "rendimento_lordo_pct": 3.0, "tipo_tassazione": "altro", "durata_anni": 2},
    ])
    voce = _voce(r, "Conto deposito")
    assert voce["aliquota_pct"] == 26.0
    _assert_voce(voce, _atteso(10000, 3.0, 26.0, 2))
    assert voce["montante_netto"] == pytest.approx(10450.66, abs=0.01)
    esente = _confronto(importo=10000, investimenti=[
        {"nome": "Conto deposito", "rendimento_lordo_pct": 3.0, "tipo_tassazione": "esente", "durata_anni": 2},
    ])
    assert "tipo_tassazione" in esente.get("errore", ""), esente


# --- plan cases: arithmetic with the norm rates -----------------------------------------

def test_caso_piano_btp_contro_obbligazione_art2_dlgs_239_1996_art3_dl_66_2014():
    """Plan case 1: BTP 3,5% (12,50%) against a corporate bond 4% (26%), 100.000 for 5 years.
    Net 3,5 x 0,875 = 3,0625% and 4 x 0,74 = 2,96%; montanti netti 116.422,55 and 116.032,31."""
    r = _confronto(importo=100000, investimenti=[
        {"nome": "BTP", "rendimento_lordo_pct": 3.5, "tipo_tassazione": "titoli_stato", "durata_anni": 5},
        {"nome": "Obbligazione societaria", "rendimento_lordo_pct": 4.0, "tipo_tassazione": "altro",
         "durata_anni": 5},
    ])
    btp = _voce(r, "BTP")
    corp = _voce(r, "Obbligazione societaria")
    _assert_voce(btp, _atteso(100000, 3.5, 12.5, 5))
    _assert_voce(corp, _atteso(100000, 4.0, 26.0, 5))
    assert btp["montante_netto"] == pytest.approx(116422.55, abs=0.01)
    assert corp["montante_netto"] == pytest.approx(116032.31, abs=0.01)
    assert r["migliore"] == "BTP"


def test_caso_piano_durate_diverse_valori_art2_dlgs_239_1996():
    """Plan case 2: two titoli di Stato (12,50%), A 3% for 10 years, B 3,1% for 1 year.
    Net 2,625% and 2,7125%; guadagni netti 3.009,27 and 271,25. Only the values are checked:
    the ranking by annual net rate (B before A although A earns more) is a documented limit of
    the tool, not a question of norm."""
    r = _confronto(importo=10000, investimenti=[
        {"nome": "A", "rendimento_lordo_pct": 3.0, "tipo_tassazione": "titoli_stato", "durata_anni": 10},
        {"nome": "B", "rendimento_lordo_pct": 3.1, "tipo_tassazione": "titoli_stato", "durata_anni": 1},
    ])
    a = _voce(r, "A")
    b = _voce(r, "B")
    _assert_voce(a, _atteso(10000, 3.0, 12.5, 10))
    _assert_voce(b, _atteso(10000, 3.1, 12.5, 1))
    assert a["guadagno_netto"] == pytest.approx(3009.27, abs=0.01)
    assert b["guadagno_netto"] == pytest.approx(271.25, abs=0.01)


# --- genuine divergences (expected to fail until the tool is fixed) ---------------------

def test_rendimento_negativo_nessuna_imposta_art45_tuir_art3_dl_66_2014():
    """Art. 45 co. 1 TUIR: the reddito di capitale is the amount of "interessi, utili o altri
    proventi percepiti"; art. 3 co. 1 D.L. 66/2014 and art. 2 co. 1 D.Lgs. 239/1996 tax the
    interest and proventi. A negative gross yield (BOT and Bund auctions of 2020-2021) gives no
    provento: the substitute tax is zero, it is never refunded. The sister tools
    `rendimento_bot` / `rendimento_btp` already clip the tax at zero.

    Tool today: -0,5% for 2 years on 10.000 at 26% -> imposta -25,93 and a montante netto
    (9.926,18) higher than the montante lordo (9.900,25)."""
    _assert_testo(TUIR_45, "ammontare degli interessi, utili o altri proventi percepiti")
    _assert_testo(DL_66_2014, "sugli interessi, premi e ogni altro provento")
    r = _confronto(importo=10000, investimenti=[
        {"nome": "Titolo a rendimento negativo", "rendimento_lordo_pct": -0.5, "tipo_tassazione": "altro",
         "durata_anni": 2},
    ])
    voce = _voce(r, "Titolo a rendimento negativo")
    assert voce["imposta"] >= 0, f"imposta negativa: {voce['imposta']}"
    assert voce["montante_netto"] <= voce["montante_lordo"] + 0.01
    assert voce["montante_netto"] == pytest.approx(10000 * 0.995 ** 2, abs=0.01)


def test_titolo_di_stato_tipo_tassazione_non_canonico_art2_co1_dlgs_239_1996():
    """A titolo di Stato bears 12,50% (art. 2 co. 1 D.Lgs. 239/1996; art. 3 co. 2 lett. a D.L.
    66/2014). Written 'Titoli_Stato' (or with a stray space) the value is not recognised and the
    tool silently applies 26%, ranking and 'migliore' included, with only a boolean flag. The
    plan expects an explicit error or warning; either an `errore` or the 12,50% rate passes."""
    _assert_testo(DLGS_239_1996, "nella misura del 12,50 per cento")
    r = _confronto(importo=10000, investimenti=[
        {"nome": "BTP", "rendimento_lordo_pct": 3.0, "tipo_tassazione": "Titoli_Stato", "durata_anni": 1},
    ])
    if "errore" in r:
        return
    voce = _voce(r, "BTP")
    assert voce["aliquota_pct"] == 12.5, f"titolo di Stato tassato al {voce['aliquota_pct']}%"

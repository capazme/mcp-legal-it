"""`rendimento_btp` reports the yield to maturity (TIR), gross and net, as the MEF does (LI-059).

The MEF publishes, for every BTP auction, a «Rendimento Lordo» on a «Base Annua Rendimenti
365 gg»: the annual compound rate that discounts coupons and redemption, at actual days / 365
from settlement, to the auction price plus the accrued interest («giorni dietimi»). The table
below is copied from the MEF «Risultati Asta» PDFs (fixture with the source URL of each row,
read on 2026-11-02): the tool's gross TIR must reproduce every published figure within 0,01
percentage points. The simple (non-compound) yield survives only as a secondary field named
as such.

The reference IRR used for the net checks is rebuilt here from the same flows, independently
of the tool's code (bisection on the present value).
"""

from __future__ import annotations

import json
import pathlib
from datetime import date

import pytest

import mcp_legal_it.server  # noqa: F401  (registers every tool module first: avoids a circular import)
from mcp_legal_it.tools.investimenti import rendimento_btp

_btp = getattr(rendimento_btp, "fn", rendimento_btp)

_FIXTURE = pathlib.Path(__file__).resolve().parents[1] / "fixtures" / "mef" / "aste_btp_2026-09_2026-11.json"
_ASTE = json.loads(_FIXTURE.read_text(encoding="utf-8"))["aste"]
ALIQUOTA = 0.125


def _tir(flussi: list[tuple[float, float]]) -> float:
    """Annual effective IRR, percent, of (years, amount) flows; bisection, independent of the tool."""
    lo, hi = -0.99, 2.0
    for _ in range(300):
        mid = (lo + hi) / 2
        if sum(c / (1 + mid) ** t for t, c in flussi) > 0:
            lo = mid
        else:
            hi = mid
    return mid * 100


def _id(asta: dict) -> str:
    return f"{asta['titolo']} {asta['data_regolamento']}"


# --- the MEF table ------------------------------------------------------------------------

@pytest.mark.parametrize("asta", _ASTE, ids=[_id(a) for a in _ASTE])
def test_tir_lordo_riproduce_il_rendimento_lordo_mef(asta):
    r = _btp(valore_nominale=100, prezzo_acquisto=asta["prezzo"], cedola_annua_pct=asta["cedola_pct"],
             data_regolamento=asta["data_regolamento"], data_scadenza=asta["data_scadenza"])
    assert "errore" not in r, r
    assert abs(r["rendimento_effettivo_lordo_pct"] - asta["rendimento_lordo_pct"]) <= 0.01, (
        r["rendimento_effettivo_lordo_pct"], asta["rendimento_lordo_pct"], asta["url"])
    # The accrued days the tool counts are the MEF's «giorni dietimi»; a short first coupon
    # (new issue) is not modelled: the tool counts from the regular previous coupon date.
    if not asta["prima_cedola_irregolare"]:
        assert r["giorni_rateo"] == asta["giorni_dietimi"], (r["giorni_rateo"], asta["giorni_dietimi"])
    assert r["rendimento_effettivo_netto_pct"] < r["rendimento_effettivo_lordo_pct"]


def test_btp_50_anni_asta_10_settembre_2026():
    """The case of B-36: cedola 2,15%, prezzo 53,94, scadenza 01/03/2072, regolamento 15/09/2026.

    MEF gross 4,61%. Before LI-059 the tool answered a simple net 5,15%, above the gross.
    """
    r = _btp(valore_nominale=100, prezzo_acquisto=53.94, cedola_annua_pct=2.15,
             data_regolamento="2026-09-15", data_scadenza="2072-03-01")
    assert r["rendimento_effettivo_lordo_pct"] == pytest.approx(4.61, abs=0.005)
    assert r["giorni_rateo"] == 14
    assert r["rateo_cedolare"] == pytest.approx(1.075 * 14 / 181, abs=0.005)
    # LI-062: the tel-quel price (clean price + accrued coupon), 54,023 here.
    assert r["prezzo_tel_quel"] == pytest.approx(54.023, abs=0.001)
    assert "esborso_totale" not in r
    assert r["anni_residui"] == pytest.approx((date(2072, 3, 1) - date(2026, 9, 15)).days / 365, abs=1e-4)

    # Net: coupons taxed at 12,5% on the part accrued while held (the first one less the
    # accrued interest paid at purchase), 12,5% on the 46,06 discount at maturity.
    t0, rateo = date(2026, 9, 15), 1.075 * 14 / 181
    cedole = [date(2027 + k // 2, 3 if k % 2 == 0 else 9, 1) for k in range(91)]
    assert cedole[-1] == date(2072, 3, 1)
    flussi = [(0.0, -(53.94 + rateo))]
    for i, d in enumerate(cedole):
        imponibile = 1.075 - (rateo if i == 0 else 0.0)
        flussi.append(((d - t0).days / 365, 1.075 - imponibile * ALIQUOTA))
    flussi[-1] = (flussi[-1][0], flussi[-1][1] + 100 - (100 - 53.94) * ALIQUOTA)
    assert r["rendimento_effettivo_netto_pct"] == pytest.approx(_tir(flussi), abs=1e-4)
    assert r["rendimento_effettivo_netto_pct"] < 4.61

    # The simple yield is still there, secondary and named for what it is.
    assert r["rendimento_semplice_netto_pct"] > r["rendimento_effettivo_lordo_pct"]
    assert "rendimento_netto_annuo_pct" not in r
    assert "rendimento semplice (non composto)" in r["nota_rendimento_semplice"]


# --- conventions --------------------------------------------------------------------------

def test_alla_pari_cedola_annuale_tir_uguale_alla_cedola():
    r = _btp(valore_nominale=1000, prezzo_acquisto=1000, cedola_annua_pct=2.5, anni_scadenza=10,
             frequenza_cedola=1)
    assert r["rendimento_effettivo_lordo_pct"] == pytest.approx(2.5, abs=1e-6)
    assert r["rendimento_effettivo_netto_pct"] == pytest.approx(2.5 * (1 - ALIQUOTA), abs=1e-6)


def test_alla_pari_cedola_semestrale_tasso_annuo_composto():
    """Annual compounding (MEF «base annua»): 5% paid 2,5% twice a year is 5,0625% a year."""
    r = _btp(valore_nominale=10000, prezzo_acquisto=10000, cedola_annua_pct=5.0, anni_scadenza=10)
    assert r["rendimento_effettivo_lordo_pct"] == pytest.approx(5.0625, abs=1e-6)
    assert r["rendimento_semplice_netto_pct"] == pytest.approx(4.375, abs=1e-4)


def test_sopra_la_pari_nessuna_imposta_sulla_differenza_negativa():
    r = _btp(valore_nominale=10000, prezzo_acquisto=10300, cedola_annua_pct=4.0, anni_scadenza=3)
    assert r["imposta_plusvalenza"] == 0.0
    netta = 200 * (1 - ALIQUOTA)
    flussi = [(0.0, -10300.0)] + [((k + 1) / 2, netta) for k in range(6)]
    flussi[-1] = (3.0, netta + 10000)
    assert r["rendimento_effettivo_netto_pct"] == pytest.approx(_tir(flussi), abs=1e-4)
    assert r["rendimento_effettivo_lordo_pct"] < 4.0


def test_ultimo_periodo_cedolare():
    """One flow left: 101,5 on 15/09/2026, bought on 15/08/2026 at 99,90 plus 153/181 of 1,5."""
    r = _btp(valore_nominale=100, prezzo_acquisto=99.90, cedola_annua_pct=3.0,
             data_regolamento="2026-08-15", data_scadenza="2026-09-15")
    rateo = 1.5 * 153 / 184  # previous coupon 15/03/2026, period 15/03-15/09 = 184 days
    assert r["giorni_rateo"] == 153
    atteso = ((101.5 / (99.90 + rateo)) ** (365 / 31) - 1) * 100
    assert r["rendimento_effettivo_lordo_pct"] == pytest.approx(atteso, abs=1e-4)
    assert len(r["flusso_cedole"]) == 1 and r["flusso_cedole"][0]["data"] == "2026-09-15"


def test_regolamento_in_data_di_stacco_nessun_rateo():
    r = _btp(valore_nominale=100, prezzo_acquisto=98.86, cedola_annua_pct=3.0,
             data_regolamento="2026-09-15", data_scadenza="2029-09-15")
    assert r["giorni_rateo"] == 0 and r["rateo_cedolare"] == 0.0
    assert len(r["flusso_cedole"]) == 6
    assert r["flusso_cedole"][0]["data"] == "2027-03-15"


def test_senza_cedola_come_zero_coupon():
    r = _btp(valore_nominale=100, prezzo_acquisto=96.0, cedola_annua_pct=0.0,
             data_regolamento="2026-10-14", data_scadenza="2028-10-14")
    giorni = (date(2028, 10, 14) - date(2026, 10, 14)).days
    assert r["rendimento_effettivo_lordo_pct"] == pytest.approx(((100 / 96.0) ** (365 / giorni) - 1) * 100, abs=1e-4)
    netto = 100 - 4.0 * ALIQUOTA
    assert r["rendimento_effettivo_netto_pct"] == pytest.approx(((netto / 96.0) ** (365 / giorni) - 1) * 100, abs=1e-4)


def test_senza_date_regolamento_a_una_data_di_stacco():
    r = _btp(valore_nominale=1000, prezzo_acquisto=980, cedola_annua_pct=3.5, anni_scadenza=5)
    assert r["giorni_rateo"] == 0 and r["rateo_cedolare"] == 0.0
    assert "data di stacco" in r["convenzione"]
    flussi = [(0.0, -980.0)] + [((k + 1) / 2, 17.5) for k in range(10)]
    flussi[-1] = (5.0, 1017.5)
    assert r["rendimento_effettivo_lordo_pct"] == pytest.approx(_tir(flussi), abs=1e-4)


def test_la_convenzione_e_dichiarata():
    r = _btp(valore_nominale=100, prezzo_acquisto=53.94, cedola_annua_pct=2.15,
             data_regolamento="2026-09-15", data_scadenza="2072-03-01")
    assert "capitalizzazione composta annua" in r["convenzione"]
    assert "giorni effettivi/365" in r["convenzione"]
    assert "prezzo tel quel (corso secco più rateo)" in r["convenzione"]
    assert "rateo Act/Act ICMA" in r["convenzione"]
    # Only the gross figure is checked against the MEF (its auction results publish no net yield).
    assert "lordo con la convenzione del MEF" in r["convenzione"]
    assert "netto calcolato" in r["convenzione"]
    # A short first coupon of a new issue is not modelled: the answer says so.
    assert "prima cedola corta" in r["convenzione"]


def test_riapertura_scarto_e_plusvalenza_segnalati():
    """LI-062: the 10/09/2026 auction of the BTP 2,15% 01/03/2072 is a reopening (issued
    01/03/2021, tranches 8-9, prezzo fiscale 99,467 in the MEF PDF): of the 46,06 to par only
    0,533 is scarto di emissione, the rest is a plusvalenza (reddito diverso). Same 12,5% at
    maturity, but only the plusvalenza is compensable with minusvalenze: the tool says so."""
    asta = next(a for a in _ASTE if a["isin"] == "IT0005441883")
    assert asta["data_emissione"] == "2021-03-01" and asta["prezzo_fiscale"] == 99.467
    r = _btp(valore_nominale=100, prezzo_acquisto=53.94, cedola_annua_pct=2.15,
             data_regolamento="2026-09-15", data_scadenza="2072-03-01")
    avviso = " ".join(r["avvertenze"])
    for frammento in ("riapertura", "scarto di emissione", "prezzo fiscale",
                      "art. 67 co. 1 lett. c-ter) TUIR", "art. 68 co. 5 TUIR", "minusvalenze"):
        assert frammento in avviso, frammento


def test_nessun_avviso_di_scarto_sopra_la_pari():
    r = _btp(valore_nominale=10000, prezzo_acquisto=10300, cedola_annua_pct=4.0, anni_scadenza=3)
    assert "avvertenze" not in r


def test_non_e_il_parametro_del_maggior_danno():
    """SS.UU. 19499/2008 (art. 1224 co. 2 c.c.) uses State securities up to twelve months: the
    tool description must not let a long BTP yield pass for that parameter."""
    doc = rendimento_btp.__doc__ if not hasattr(rendimento_btp, "fn") else rendimento_btp.fn.__doc__
    assert "art. 1224 co. 2 c.c." in doc and "19499/2008" in doc and "dodici mesi" in doc


def test_date_e_anni_insieme_prevalgono_le_date():
    r = _btp(valore_nominale=100, prezzo_acquisto=98.86, cedola_annua_pct=3.0, anni_scadenza=7,
             data_regolamento="2026-09-15", data_scadenza="2029-09-15")
    assert r["anni_residui"] == pytest.approx(3.0, abs=0.01)
    assert any("anni_scadenza" in a for a in r["avvertenze"])


# --- input errors -------------------------------------------------------------------------

@pytest.mark.parametrize("kwargs, messaggio", [
    ({"anni_scadenza": 0}, "anni_scadenza"),
    ({"data_regolamento": "2026-09-15"}, "insieme"),
    ({"data_scadenza": "2029-09-15"}, "insieme"),
    ({"data_regolamento": "15/09/2026", "data_scadenza": "2029-09-15"}, "AAAA-MM-GG"),
    ({"data_regolamento": "2029-09-15", "data_scadenza": "2029-09-15"}, "precedere"),
    ({"data_regolamento": "2026-09-15", "data_scadenza": "2029-09-15", "frequenza_cedola": 5}, "frequenza_cedola"),
    ({"data_regolamento": "0001-03-01", "data_scadenza": "0001-06-15"}, "tra il 1900 e il 2200"),
    ({"data_regolamento": "2026-09-14", "data_scadenza": "2026-09-15", "prezzo_acquisto": 95.0}, "fuori scala"),
    ({"data_regolamento": "2026-09-15", "data_scadenza": "2199-09-15", "prezzo_acquisto": 1e-9}, "fuori scala"),
])
def test_errori_di_input(kwargs, messaggio):
    base = {"valore_nominale": 100, "prezzo_acquisto": 98.0, "cedola_annua_pct": 3.0}
    r = _btp(**{**base, **kwargs})
    assert messaggio in r.get("errore", ""), r


def test_la_scelta_actual_365_e_documentata():
    """LI-062: ICMA for the accrued interest, actual/365 for discounting, with the measured deviations."""
    doc = getattr(rendimento_btp, "fn", rendimento_btp).__doc__
    assert "Act/Act ICMA vale per il rateo" in doc
    assert "0,0077" in doc and "0,0101" in doc

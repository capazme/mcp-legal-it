import asyncio
import importlib
import inspect

import pytest


def _call(fn_name: str, **kwargs):
    mod = importlib.import_module("src.tools.investimenti")
    fn = getattr(mod, fn_name)
    actual = fn.fn if hasattr(fn, "fn") else fn
    if inspect.iscoroutinefunction(actual):
        return asyncio.run(actual(**kwargs))
    return actual(**kwargs)


# ---------------------------------------------------------------------------
# rendimento_bot
# ---------------------------------------------------------------------------

class TestRendimentoBot:
    def test_happy_path_basic(self):
        r = _call("rendimento_bot", valore_nominale=10000, prezzo_acquisto=9800, giorni_scadenza=182)
        assert r["valore_nominale"] == 10000
        assert r["prezzo_acquisto"] == 9800
        assert r["giorni_scadenza"] == 182
        assert r["plusvalenza_lorda"] == pytest.approx(200.0)
        assert r["imposta_sostitutiva_pct"] == 12.5
        assert r["imposta"] == pytest.approx(200 * 0.125, abs=0.01)
        assert r["commissione"] == 0.0
        assert r["guadagno_netto"] == pytest.approx(200 - 200 * 0.125, abs=0.01)
        assert r["rendimento_lordo_annuo_pct"] > 0
        assert r["rendimento_netto_annuo_pct"] > 0
        assert r["rendimento_netto_annuo_pct"] < r["rendimento_lordo_annuo_pct"]
        assert "D.Lgs. 239/1996" in r["riferimento_normativo"]

    def test_with_commissione(self):
        r = _call("rendimento_bot", valore_nominale=10000, prezzo_acquisto=9800,
                  giorni_scadenza=182, commissione_pct=0.15)
        expected_commissione = 10000 * 0.15 / 100
        assert r["commissione"] == pytest.approx(expected_commissione, abs=0.01)
        assert r["guadagno_netto"] < _call(
            "rendimento_bot", valore_nominale=10000, prezzo_acquisto=9800, giorni_scadenza=182
        )["guadagno_netto"]

    def test_no_plusvalenza_when_price_above_nominal(self):
        r = _call("rendimento_bot", valore_nominale=10000, prezzo_acquisto=10100, giorni_scadenza=90)
        assert r["plusvalenza_lorda"] == pytest.approx(-100.0)
        assert r["imposta"] == 0.0
        assert r["guadagno_netto"] < 0

    def test_annualized_rendimento_formula(self):
        r = _call("rendimento_bot", valore_nominale=10000, prezzo_acquisto=9800, giorni_scadenza=365)
        expected_lordo = (200 / 9800) * 100
        assert r["rendimento_lordo_annuo_pct"] == pytest.approx(expected_lordo, rel=1e-4)

    def test_error_giorni_zero(self):
        r = _call("rendimento_bot", valore_nominale=10000, prezzo_acquisto=9800, giorni_scadenza=0)
        assert "errore" in r

    def test_error_giorni_negative(self):
        r = _call("rendimento_bot", valore_nominale=10000, prezzo_acquisto=9800, giorni_scadenza=-5)
        assert "errore" in r

    def test_error_prezzo_zero(self):
        r = _call("rendimento_bot", valore_nominale=10000, prezzo_acquisto=0, giorni_scadenza=90)
        assert "errore" in r

    def test_error_prezzo_negative(self):
        r = _call("rendimento_bot", valore_nominale=10000, prezzo_acquisto=-100, giorni_scadenza=90)
        assert "errore" in r

    def test_net_yield_on_total_outlay(self):
        # MEF scheda BOT: the 12,5% tax is withheld at subscription, so the cash laid out is
        # price + tax (+ commission). 10.000 nominal at 9.700, 365 days, no commission:
        # tax 37,50, net 262,50, outlay 9.737,50, net yield 262,50 / 9.737,50 = 2,6958%.
        r = _call("rendimento_bot", valore_nominale=10000, prezzo_acquisto=9700, giorni_scadenza=365)
        assert r["esborso_totale"] == 9737.5
        assert r["guadagno_netto"] == 262.5
        assert r["rendimento_netto_annuo_pct"] == pytest.approx(2.6958, abs=1e-4)
        assert r["rendimento_lordo_annuo_pct"] == pytest.approx(3.0928, abs=1e-4)

    def test_commissione_zero_at_or_above_par(self):
        # D.M. 15/1/2015 (scheda MEF): price at or above 100, no commission to the client.
        r = _call("rendimento_bot", valore_nominale=10000, prezzo_acquisto=10020,
                  giorni_scadenza=91, commissione_pct=0.05)
        assert r["commissione"] == 0.0
        assert r["guadagno_netto"] == -20.0
        assert r["rendimento_netto_annuo_pct"] == pytest.approx(-20 / 10020 * 365 / 91 * 100, abs=1e-4)

    def test_commissione_capped_to_keep_total_price_within_par(self):
        # D.M. 15/1/2015: price 99,90 -> gain 10, tax 1,25; room left for the commission is
        # 10 - 1,25 = 8,75 euro, below the 0,15% x 10.000 = 15 asked.
        r = _call("rendimento_bot", valore_nominale=10000, prezzo_acquisto=9990,
                  giorni_scadenza=300, commissione_pct=0.15)
        assert r["commissione"] == 8.75
        assert r["guadagno_netto"] == 0.0
        assert "avvertenze" in r

    def test_commissione_above_dm_maximum_is_flagged(self):
        # D.M. 15/1/2015: max 0,10% for 141-270 days; the amount is still computed as asked.
        r = _call("rendimento_bot", valore_nominale=10000, prezzo_acquisto=9800,
                  giorni_scadenza=180, commissione_pct=0.20)
        assert r["commissione"] == 20.0
        assert any("massimo" in a for a in r["avvertenze"])

    def test_short_duration_bot(self):
        r = _call("rendimento_bot", valore_nominale=5000, prezzo_acquisto=4980, giorni_scadenza=91)
        assert isinstance(r["rendimento_netto_annuo_pct"], float)
        assert r["guadagno_netto"] > 0


# ---------------------------------------------------------------------------
# rendimento_btp
# ---------------------------------------------------------------------------

class TestRendimentoBtp:
    def test_happy_path_semestrale(self):
        r = _call("rendimento_btp", valore_nominale=1000, prezzo_acquisto=980,
                  cedola_annua_pct=3.5, anni_scadenza=5)
        assert r["valore_nominale"] == 1000
        assert r["frequenza_cedola"] == 2
        n_cedole = 5 * 2
        cedola_singola = 1000 * 0.035 / 2
        totale_lordo = cedola_singola * n_cedole
        assert r["totale_cedole_lordo"] == pytest.approx(totale_lordo, abs=0.01)
        assert r["imposta_cedole"] == pytest.approx(totale_lordo * 0.125, abs=0.01)
        assert r["totale_cedole_netto"] == pytest.approx(totale_lordo * 0.875, abs=0.01)
        assert r["plusvalenza_lorda"] == pytest.approx(20.0)
        assert r["imposta_plusvalenza"] == pytest.approx(20 * 0.125, abs=0.01)
        assert len(r["flusso_cedole"]) == n_cedole
        assert "D.Lgs. 239/1996" in r["riferimento_normativo"]

    def test_cedola_annuale(self):
        r = _call("rendimento_btp", valore_nominale=1000, prezzo_acquisto=1000,
                  cedola_annua_pct=4.0, anni_scadenza=3, frequenza_cedola=1)
        assert r["frequenza_cedola"] == 1
        assert len(r["flusso_cedole"]) == 3
        cedola = r["flusso_cedole"][0]
        assert cedola["lorda"] == pytest.approx(40.0)
        assert cedola["netta"] == pytest.approx(40.0 * 0.875, abs=0.01)

    def test_no_plusvalenza_at_par(self):
        r = _call("rendimento_btp", valore_nominale=1000, prezzo_acquisto=1000,
                  cedola_annua_pct=2.0, anni_scadenza=2)
        assert r["plusvalenza_lorda"] == pytest.approx(0.0)
        assert r["imposta_plusvalenza"] == pytest.approx(0.0)
        assert r["guadagno_netto_totale"] == pytest.approx(r["totale_cedole_netto"], abs=0.01)

    def test_negative_plusvalenza_no_tax(self):
        r = _call("rendimento_btp", valore_nominale=1000, prezzo_acquisto=1050,
                  cedola_annua_pct=2.0, anni_scadenza=3)
        assert r["plusvalenza_lorda"] == pytest.approx(-50.0)
        assert r["imposta_plusvalenza"] == pytest.approx(0.0)
        assert r["plusvalenza_netta"] == pytest.approx(-50.0)

    def test_rendimento_netto_annuo_formula(self):
        r = _call("rendimento_btp", valore_nominale=1000, prezzo_acquisto=950,
                  cedola_annua_pct=3.0, anni_scadenza=10)
        guadagno = r["guadagno_netto_totale"]
        expected = (guadagno / 950 / 10) * 100
        assert r["rendimento_netto_annuo_pct"] == pytest.approx(expected, rel=1e-4)

    def test_error_anni_zero(self):
        r = _call("rendimento_btp", valore_nominale=1000, prezzo_acquisto=980,
                  cedola_annua_pct=3.5, anni_scadenza=0)
        assert "errore" in r

    def test_error_anni_negative(self):
        r = _call("rendimento_btp", valore_nominale=1000, prezzo_acquisto=980,
                  cedola_annua_pct=3.5, anni_scadenza=-2)
        assert "errore" in r

    def test_error_prezzo_zero(self):
        r = _call("rendimento_btp", valore_nominale=1000, prezzo_acquisto=0,
                  cedola_annua_pct=3.5, anni_scadenza=5)
        assert "errore" in r


# ---------------------------------------------------------------------------
# pronti_termine
# ---------------------------------------------------------------------------

class TestProntiTermine:
    def test_titoli_stato_aliquota_125(self):
        r = _call("pronti_termine", capitale=10000, tasso_lordo_pct=3.0, giorni=90,
                  tipo_sottostante="titoli_stato")
        interessi_lordi = 10000 * 0.03 * 90 / 365
        imposta = interessi_lordi * 0.125
        assert r["aliquota_pct"] == 12.5
        assert r["interessi_lordi"] == pytest.approx(interessi_lordi, abs=0.01)
        assert r["imposta"] == pytest.approx(imposta, abs=0.01)
        assert r["interessi_netti"] == pytest.approx(interessi_lordi - imposta, abs=0.01)
        assert "D.Lgs. 239/1996" in r["riferimento_normativo"]

    def test_altro_aliquota_26(self):
        r = _call("pronti_termine", capitale=10000, tasso_lordo_pct=3.0, giorni=90,
                  tipo_sottostante="altro")
        assert r["aliquota_pct"] == 26.0
        interessi_lordi = 10000 * 0.03 * 90 / 365
        imposta = interessi_lordi * 0.26
        assert r["imposta"] == pytest.approx(imposta, abs=0.01)

    def test_default_tipo_sottostante(self):
        r = _call("pronti_termine", capitale=5000, tasso_lordo_pct=2.5, giorni=30)
        assert r["tipo_sottostante"] == "titoli_stato"
        assert r["aliquota_pct"] == 12.5

    def test_rendimento_netto_annuo_formula(self):
        r = _call("pronti_termine", capitale=10000, tasso_lordo_pct=3.0, giorni=365,
                  tipo_sottostante="titoli_stato")
        assert r["rendimento_netto_annuo_pct"] == pytest.approx(3.0 * 0.875, rel=1e-4)

    def test_error_giorni_zero(self):
        r = _call("pronti_termine", capitale=10000, tasso_lordo_pct=2.0, giorni=0)
        assert "errore" in r

    def test_error_giorni_negative(self):
        r = _call("pronti_termine", capitale=10000, tasso_lordo_pct=2.0, giorni=-1)
        assert "errore" in r

    def test_error_capitale_zero(self):
        r = _call("pronti_termine", capitale=0, tasso_lordo_pct=2.0, giorni=30)
        assert "errore" in r

    def test_error_capitale_negative(self):
        r = _call("pronti_termine", capitale=-1000, tasso_lordo_pct=2.0, giorni=30)
        assert "errore" in r

    def test_higher_tax_for_altro(self):
        r_stato = _call("pronti_termine", capitale=10000, tasso_lordo_pct=3.0, giorni=180,
                        tipo_sottostante="titoli_stato")
        r_altro = _call("pronti_termine", capitale=10000, tasso_lordo_pct=3.0, giorni=180,
                        tipo_sottostante="altro")
        assert r_altro["imposta"] > r_stato["imposta"]
        assert r_altro["interessi_netti"] < r_stato["interessi_netti"]


# ---------------------------------------------------------------------------
# rendimento_buoni_postali
# ---------------------------------------------------------------------------

class TestRendimentoBuoniPostali:
    def test_ordinario_10_anni(self):
        r = _call("rendimento_buoni_postali", importo=10000, tipo="ordinario", anni=10)
        assert r["tipo"] == "ordinario"
        assert r["anni"] == 10
        assert r["importo"] == 10000
        assert r["montante_lordo"] > 10000
        assert r["interessi_lordi"] > 0
        assert r["imposta"] == pytest.approx(r["interessi_lordi"] * 0.125, abs=0.01)
        assert r["montante_netto"] == pytest.approx(r["montante_lordo"] - r["imposta"], abs=0.01)
        assert r["interessi_netti"] == pytest.approx(r["interessi_lordi"] - r["imposta"], abs=0.01)
        assert r["rendimento_netto_annuo_pct"] > 0
        assert len(r["dettaglio_annuale"]) == 10
        assert "D.Lgs. 239/1996" in r["riferimento_normativo"]

    def test_tipo_3x4(self):
        r = _call("rendimento_buoni_postali", importo=5000, tipo="3x4", anni=12)
        assert r["tipo"] == "3x4"
        assert r["anni"] == 12

    def test_tipo_4x4(self):
        r = _call("rendimento_buoni_postali", importo=5000, tipo="4x4", anni=8)
        assert r["anni"] == 8
        assert r["montante_lordo"] > 5000

    def test_tipo_dedicato_minori(self):
        r = _call("rendimento_buoni_postali", importo=1000, tipo="dedicato_minori", anni=18)
        assert r["anni"] == 18
        assert len(r["dettaglio_annuale"]) == 18

    def test_anni_capped_at_max(self):
        r = _call("rendimento_buoni_postali", importo=1000, tipo="ordinario", anni=100)
        assert r["anni"] == 20

    def test_anni_capped_3x4(self):
        r = _call("rendimento_buoni_postali", importo=1000, tipo="3x4", anni=99)
        assert r["anni"] == 12

    def test_dettaglio_yearly_compounding(self):
        r = _call("rendimento_buoni_postali", importo=10000, tipo="ordinario", anni=3)
        d = r["dettaglio_annuale"]
        assert d[0]["anno"] == 1
        assert d[1]["anno"] == 2
        assert d[2]["anno"] == 3
        assert d[1]["montante_lordo"] > d[0]["montante_lordo"]

    def test_error_importo_zero(self):
        r = _call("rendimento_buoni_postali", importo=0, tipo="ordinario", anni=5)
        assert "errore" in r

    def test_error_importo_negative(self):
        r = _call("rendimento_buoni_postali", importo=-500, tipo="ordinario", anni=5)
        assert "errore" in r

    def test_error_anni_zero(self):
        r = _call("rendimento_buoni_postali", importo=1000, tipo="ordinario", anni=0)
        assert "errore" in r

    def test_error_tipo_invalido(self):
        r = _call("rendimento_buoni_postali", importo=1000, tipo="inesistente", anni=5)
        assert "errore" in r
        assert "inesistente" in r["errore"]

    def test_rendimento_netto_annuo_formula(self):
        r = _call("rendimento_buoni_postali", importo=10000, tipo="ordinario", anni=5)
        expected = ((r["montante_netto"] / 10000) ** (1 / 5) - 1) * 100
        assert r["rendimento_netto_annuo_pct"] == pytest.approx(expected, rel=1e-4)

    # -- corrections from the phase 3 audit: coefficients of the CDP series -------------
    # Values are importo x coefficient of the foglio informativo (read on 2026-09-28/29), rounded
    # half up to the cent. Tax: art. 2 co. 1 and 3 D.Lgs. 239/1996 (12,50%), coefficienti netti
    # = 1 + (lordo - 1) x 0,875.

    @pytest.mark.parametrize(
        "anni, lordo, netto",
        [
            (1, 10075.00, 10065.63),   # Tabella B TF120A250624: 1,00750000 / 1,00656250
            (4, 10303.39, 10265.47),   # 1,03033919 / 1,02654679
            (10, 11574.51, 11377.69),  # 1,15745056 / 1,13776924
            (20, 16386.19, 15587.92),  # 1,63861891 / 1,55879154
        ],
    )
    def test_ordinario_coefficienti_tabella_b_tf120a250624(self, anni, lordo, netto):
        r = _call("rendimento_buoni_postali", importo=10000, tipo="ordinario", anni=anni)
        assert r["serie"] == "TF120A250624"
        assert r["montante_lordo"] == pytest.approx(lordo, abs=0.01)
        assert r["montante_netto"] == pytest.approx(netto, abs=0.01)

    def test_ordinario_oltre_venti_anni_infruttifero(self):
        # Foglio TF120A250624: "diventano infruttiferi dal giorno successivo alla scadenza del ventesimo anno".
        r = _call("rendimento_buoni_postali", importo=10000, tipo="ordinario", anni=25)
        assert r["anni"] == 20
        assert r["montante_lordo"] == pytest.approx(16386.19, abs=0.01)
        assert any("infruttifero" in a for a in r["avvertenze"])

    @pytest.mark.parametrize(
        "anni, lordo, netto",
        [
            (2, 5000.00, 5000.00),     # nothing paid before 3 years: coefficient 1,00000000
            (3, 5151.51, 5132.57),     # 1,03030100 / 1,02651338
            (7, 5467.22, 5408.81),     # year 7 = year 6: 1,09344326 / 1,08176286 (triennio in corso non corrisposto)
            (12, 7124.44, 6858.89),    # 1,42488882 / 1,37177772 with the 8% premio (7% net)
        ],
    )
    def test_3x4_con_premio_interessi_solo_a_triennio_compiuto(self, anni, lordo, netto):
        # Foglio TF012A260724, "Interessi e Premio" and Tabella A.
        r = _call("rendimento_buoni_postali", importo=5000, tipo="3x4_con_premio", anni=anni)
        assert r["serie"] == "TF012A260724"
        assert r["montante_lordo"] == pytest.approx(lordo, abs=0.01)
        assert r["montante_netto"] == pytest.approx(netto, abs=0.01)

    @pytest.mark.parametrize(
        "anni, lordo",
        [(3, 5151.51), (6, 5467.22), (9, 6108.57), (12, 7128.80)],
    )
    def test_3x4_storico_tassi_effettivi_tf212a250211(self, anni, lordo):
        # Scheda di sintesi TF212A250211: tasso effettivo annuo lordo 1,00 / 1,50 / 2,25 / 3,00%
        # at the 3rd, 6th, 9th, 12th year: 5.000 x (1 + t)^n. The series is no longer in placement.
        r = _call("rendimento_buoni_postali", importo=5000, tipo="3x4", anni=anni)
        assert r["serie"] == "TF212A250211"
        assert r["in_emissione"] is False
        assert r["montante_lordo"] == pytest.approx(lordo, abs=0.01)
        assert any("non più in emissione" in a for a in r["avvertenze"])

    @pytest.mark.parametrize(
        "anni, lordo",
        [(3, 5000.00), (4, 5306.82), (7, 5306.82), (8, 5858.30), (12, 6530.25), (16, 8023.53)],
    )
    def test_4x4_storico_interessi_a_quadriennio_compiuto_tf116a221027(self, anni, lordo):
        # Scheda di sintesi TF116A221027: 1,50 / 2,00 / 2,25 / 3,00% at 4/8/12/16 years, interest
        # recognised only at the end of each quadriennio; no interest before the fourth year.
        r = _call("rendimento_buoni_postali", importo=5000, tipo="4x4", anni=anni)
        assert r["montante_lordo"] == pytest.approx(lordo, abs=0.01)

    def test_dedicato_minori_alla_nascita_scadenza_a_18_anni(self, monkeypatch):
        # Foglio TF118A260922, Tabella A: birthday after 1 agosto 2044 -> 2,38712870 / 2,21373761
        # (5,00% effettivo annuo lordo a scadenza): 1.000 euro -> 2.387,13 lordo, 2.213,74 netto.
        monkeypatch.setenv("LEGAL_TODAY", "2026-09-29")
        r = _call("rendimento_buoni_postali", importo=1000, tipo="dedicato_minori", anni=18)
        assert r["serie"] == "TF118A260922"
        assert r["anni"] == 18
        assert r["montante_lordo"] == pytest.approx(2387.13, abs=0.01)
        assert r["montante_netto"] == pytest.approx(2213.74, abs=0.01)
        assert len(r["dettaglio_annuale"]) == 18
        assert r["dettaglio_annuale"][-1]["scadenza"] is True

    def test_dedicato_minori_otto_anni_scade_nel_bimestre_agosto_2036(self, monkeypatch):
        # Minor aged 8 today (2026-09-29): 18th birthday in 10 years, Tabella A row "1 agosto 2036 -
        # 30 settembre 2036": 1,61570266 / 1,53873983 -> 1.615,70 / 1.538,74.
        monkeypatch.setenv("LEGAL_TODAY", "2026-09-29")
        r = _call("rendimento_buoni_postali", importo=1000, tipo="dedicato_minori", anni=10, eta_minore=8)
        assert r["montante_lordo"] == pytest.approx(1615.70, abs=0.01)
        assert r["montante_netto"] == pytest.approx(1538.74, abs=0.01)

    @pytest.mark.parametrize(
        "anni, lordo, netto",
        [
            (1, 1000.00, 1000.00),   # nothing before 18 months: 1,00000000
            (5, 1025.25, 1022.09),   # Tabella C: 1,02525125 / 1,02209485 (0,50% nominale)
            (10, 1051.14, 1044.75),  # 1,05114013 / 1,04474762
        ],
    )
    def test_dedicato_minori_rimborso_anticipato_tabella_c(self, monkeypatch, anni, lordo, netto):
        monkeypatch.setenv("LEGAL_TODAY", "2026-09-29")
        r = _call("rendimento_buoni_postali", importo=1000, tipo="dedicato_minori", anni=anni)
        assert r["montante_lordo"] == pytest.approx(lordo, abs=0.01)
        assert r["montante_netto"] == pytest.approx(netto, abs=0.01)
        assert any("giudice tutelare" in a for a in r["avvertenze"])

    def test_dedicato_minori_eta_non_ammessa(self):
        # Foglio TF118A260922: no subscription for holders over 16 years and 6 months.
        assert "errore" in _call("rendimento_buoni_postali", importo=1000, tipo="dedicato_minori",
                                 anni=1, eta_minore=17)

    def test_eta_minore_solo_per_dedicato_minori(self):
        assert "errore" in _call("rendimento_buoni_postali", importo=1000, tipo="ordinario", anni=5,
                                 eta_minore=3)

    def test_serie_esplicita_e_serie_sconosciuta(self):
        ok = _call("rendimento_buoni_postali", importo=10000, tipo="ordinario", anni=1, serie="TF120A250624")
        assert ok["montante_lordo"] == pytest.approx(10075.00, abs=0.01)
        ko = _call("rendimento_buoni_postali", importo=10000, tipo="ordinario", anni=1, serie="TF999")
        assert "serie non disponibile" in ko["errore"]

    def test_imposta_di_bollo_oltre_5000_euro_segnalata_e_stimata(self):
        # Schede di sintesi CDP: esente se il portafoglio buoni e' <= 5.000 euro, altrimenti 0,20% annuo
        # sul capitale investito (art. 13 co. 2-ter Tariffa D.P.R. 642/1972; art. 19 D.L. 201/2011):
        # 10.000 euro x 0,20% x 10 anni = 200 euro, riportati a parte dal montante netto.
        r = _call("rendimento_buoni_postali", importo=10000, tipo="ordinario", anni=10)
        bollo = r["imposta_bollo"]
        assert bollo["dovuta"] is True
        assert bollo["aliquota_annua_pct"] == 0.20
        assert bollo["stima_totale"] == pytest.approx(200.00, abs=0.01)
        assert r["montante_netto"] == pytest.approx(11377.69, abs=0.01)
        assert r["montante_netto_dopo_bollo"] == pytest.approx(11177.69, abs=0.01)

    def test_bollo_esente_sotto_soglia_e_soglia_del_portafoglio(self):
        # Nota 3-ter, art. 19 co. 3 lett. b) D.L. 201/2011: esenti i buoni postali fruttiferi di valore di
        # rimborso complessivamente non superiore a 5.000 euro; the threshold is on the whole portfolio.
        piccolo = _call("rendimento_buoni_postali", importo=3000, tipo="ordinario", anni=2)
        assert piccolo["imposta_bollo"]["dovuta"] is False
        assert piccolo["imposta_bollo"]["stima_totale"] == 0.0
        assert piccolo["montante_netto_dopo_bollo"] == piccolo["montante_netto"]
        con_altri = _call("rendimento_buoni_postali", importo=3000, tipo="ordinario", anni=2,
                          valore_portafoglio_buoni=6000)
        assert con_altri["imposta_bollo"]["dovuta"] is True
        assert con_altri["imposta_bollo"]["stima_totale"] == pytest.approx(12.00, abs=0.01)  # 3.000 x 0,2% x 2

    def test_montante_lordo_meno_imposta_uguale_netto(self):
        for tipo, anni in (("ordinario", 7), ("3x4_con_premio", 9), ("4x4", 8)):
            r = _call("rendimento_buoni_postali", importo=12345.67, tipo=tipo, anni=anni)
            assert r["montante_lordo"] - r["imposta"] == pytest.approx(r["montante_netto"], abs=0.005)
            assert r["imposta"] == pytest.approx(r["interessi_lordi"] * 0.125, abs=0.01)

    def test_tabella_buoni_postali_netto_uguale_lordo_meno_12_5_per_cento(self):
        # Every netto coefficient of the table is 1 + (lordo - 1) x 0,875 (12,50%, D.Lgs. 239/1996),
        # as in the fogli; the historical series derive it the same way.
        from src.lib import _data

        for cfg in _data.load("buoni_postali")["tipi"].values():
            for serie in cfg["serie"].values():
                righe = list(serie.get("coefficienti", {}).values())
                righe += list(serie.get("rimborso_anticipato", {}).values())
                righe += [r[1:] for r in serie.get("maturita", [])]
                assert righe
                for lordo, netto in righe:
                    assert netto == pytest.approx(1 + (lordo - 1) * 0.875, abs=2e-8)

    def test_tabella_buoni_postali_dichiara_la_provenienza(self):
        from src.lib import _data

        v = _data.vintage("buoni_postali")
        assert v.verificato
        assert "TF120A250624" in v.fonte and "TF118A260922" in v.fonte

    def test_risposta_riporta_i_dati_applicati(self):
        r = _call("rendimento_buoni_postali", importo=10000, tipo="ordinario", anni=5)
        assert any("buoni postali" in riga for riga in r["dati_applicati"])

    def test_aggiungi_anni_29_febbraio(self):
        from datetime import date

        from src.tools.investimenti import _aggiungi_anni

        assert _aggiungi_anni(date(2028, 2, 29), 1) == date(2029, 2, 28)
        assert _aggiungi_anni(date(2028, 2, 29), 4) == date(2032, 2, 29)


# ---------------------------------------------------------------------------
# confronto_investimenti
# ---------------------------------------------------------------------------

class TestConfronto:
    _INVESTIMENTI_BASE = [
        {"nome": "BOT", "rendimento_lordo_pct": 3.0, "tipo_tassazione": "titoli_stato", "durata_anni": 1},
        {"nome": "Obbligazione", "rendimento_lordo_pct": 4.0, "tipo_tassazione": "altro", "durata_anni": 1},
    ]

    def test_happy_path_two_instruments(self):
        r = _call("confronto_investimenti", importo=10000, investimenti=self._INVESTIMENTI_BASE)
        assert r["importo"] == 10000
        assert len(r["classifica"]) == 2
        assert r["migliore"] is not None
        assert "nota" in r

    def test_titoli_stato_vs_altro_tax_impact(self):
        r = _call("confronto_investimenti", importo=10000, investimenti=[
            {"nome": "BTP", "rendimento_lordo_pct": 3.0, "tipo_tassazione": "titoli_stato", "durata_anni": 1},
            {"nome": "Corp", "rendimento_lordo_pct": 3.0, "tipo_tassazione": "altro", "durata_anni": 1},
        ])
        classifica = {x["nome"]: x for x in r["classifica"]}
        assert classifica["BTP"]["aliquota_pct"] == 12.5
        assert classifica["Corp"]["aliquota_pct"] == 26.0
        assert classifica["BTP"]["rendimento_netto_pct"] > classifica["Corp"]["rendimento_netto_pct"]
        assert r["migliore"] == "BTP"

    def test_sorted_by_rendimento_netto_desc(self):
        r = _call("confronto_investimenti", importo=10000, investimenti=[
            {"nome": "A", "rendimento_lordo_pct": 2.0, "tipo_tassazione": "altro", "durata_anni": 1},
            {"nome": "B", "rendimento_lordo_pct": 5.0, "tipo_tassazione": "titoli_stato", "durata_anni": 1},
            {"nome": "C", "rendimento_lordo_pct": 1.0, "tipo_tassazione": "titoli_stato", "durata_anni": 1},
        ])
        rendimenti = [x["rendimento_netto_pct"] for x in r["classifica"]]
        assert rendimenti == sorted(rendimenti, reverse=True)

    def test_montante_netto_formula(self):
        r = _call("confronto_investimenti", importo=10000, investimenti=[
            {"nome": "X", "rendimento_lordo_pct": 4.0, "tipo_tassazione": "titoli_stato", "durata_anni": 2},
        ])
        item = r["classifica"][0]
        expected_lordo = 10000 * (1.04 ** 2)
        expected_imposta = (expected_lordo - 10000) * 0.125
        expected_netto = expected_lordo - expected_imposta
        assert item["montante_lordo"] == pytest.approx(expected_lordo, abs=0.01)
        assert item["imposta"] == pytest.approx(expected_imposta, abs=0.01)
        assert item["montante_netto"] == pytest.approx(expected_netto, abs=0.01)
        assert item["guadagno_netto"] == pytest.approx(expected_netto - 10000, abs=0.01)

    def test_default_tipo_tassazione_altro(self):
        r = _call("confronto_investimenti", importo=5000, investimenti=[
            {"nome": "Z", "rendimento_lordo_pct": 3.0},
        ])
        assert r["classifica"][0]["aliquota_pct"] == 26.0

    def test_single_instrument_migliore(self):
        r = _call("confronto_investimenti", importo=1000, investimenti=[
            {"nome": "Solo", "rendimento_lordo_pct": 2.5, "tipo_tassazione": "titoli_stato", "durata_anni": 1},
        ])
        assert r["migliore"] == "Solo"
        assert len(r["classifica"]) == 1

    def test_error_importo_zero(self):
        r = _call("confronto_investimenti", importo=0, investimenti=self._INVESTIMENTI_BASE)
        assert "errore" in r

    def test_error_importo_negative(self):
        r = _call("confronto_investimenti", importo=-100, investimenti=self._INVESTIMENTI_BASE)
        assert "errore" in r

    def test_error_empty_list(self):
        r = _call("confronto_investimenti", importo=10000, investimenti=[])
        assert "errore" in r

    def test_guadagno_netto_correct(self):
        r = _call("confronto_investimenti", importo=10000, investimenti=[
            {"nome": "T", "rendimento_lordo_pct": 3.0, "tipo_tassazione": "titoli_stato", "durata_anni": 1},
        ])
        item = r["classifica"][0]
        assert item["guadagno_netto"] == pytest.approx(item["montante_netto"] - 10000, abs=0.01)

    # -- corrections from the phase 3 audit (no mocks: pure arithmetic) ------------------

    def test_rendimento_negativo_imposta_zero_art45_tuir(self):
        # Art. 45 co. 1 TUIR: only interest "percepiti" is taxable; art. 3 co. 1 D.L. 66/2014 taxes
        # income, never a loss. -0,5% for 2 years on 10.000: montante 9.900,25, tax 0, no refund.
        r = _call("confronto_investimenti", importo=10000, investimenti=[
            {"nome": "Neg", "rendimento_lordo_pct": -0.5, "tipo_tassazione": "altro", "durata_anni": 2},
        ])
        voce = r["classifica"][0]
        assert voce["montante_lordo"] == pytest.approx(9900.25, abs=0.01)
        assert voce["imposta"] == 0.0
        assert voce["montante_netto"] == pytest.approx(9900.25, abs=0.01)
        assert voce["rendimento_netto_pct"] == pytest.approx(-0.5, abs=1e-4)
        assert voce["guadagno_netto"] == pytest.approx(-99.75, abs=0.01)

    def test_rendimento_negativo_titoli_stato_imposta_zero(self):
        # Art. 2 co. 1 D.Lgs. 239/1996: 12,50% on proceeds, none when there are none.
        r = _call("confronto_investimenti", importo=10000, investimenti=[
            {"nome": "Neg", "rendimento_lordo_pct": -0.5, "tipo_tassazione": "titoli_stato", "durata_anni": 1},
        ])
        voce = r["classifica"][0]
        assert voce["imposta"] == 0.0
        assert voce["montante_netto"] == pytest.approx(9950.0, abs=0.01)

    def test_rendimento_zero_nessuna_imposta(self):
        r = _call("confronto_investimenti", importo=10000, investimenti=[
            {"nome": "Zero", "rendimento_lordo_pct": 0.0, "tipo_tassazione": "altro", "durata_anni": 3},
        ])
        voce = r["classifica"][0]
        assert voce["imposta"] == 0.0
        assert voce["montante_netto"] == pytest.approx(10000.0, abs=0.01)

    @pytest.mark.parametrize("scritto", ["Titoli_Stato", " titoli_stato ", "TITOLI-STATO", "titoli stato"])
    def test_tipo_tassazione_normalizzato_titoli_stato(self, scritto):
        # Art. 2 co. 1 D.Lgs. 239/1996 + art. 3 co. 2 lett. a) D.L. 66/2014: a titolo di Stato pays
        # 12,50% however the caller spells the regime: 3% on 10.000, 1 year -> tax 37,50, net 10.262,50.
        r = _call("confronto_investimenti", importo=10000, investimenti=[
            {"nome": "BTP", "rendimento_lordo_pct": 3.0, "tipo_tassazione": scritto, "durata_anni": 1},
        ])
        voce = r["classifica"][0]
        assert voce["aliquota_pct"] == 12.5
        assert voce["imposta"] == pytest.approx(37.5, abs=0.01)
        assert voce["montante_netto"] == pytest.approx(10262.5, abs=0.01)

    @pytest.mark.parametrize("valore", ["esente", "", "pir", None])
    def test_tipo_tassazione_sconosciuto_errore(self, valore):
        # Art. 3 co. 1 D.L. 66/2014 (26%) and art. 2 co. 1 D.Lgs. 239/1996 (12,50%) are the two
        # regimes the tool knows: an unknown one is refused, never silently taxed at 26%.
        r = _call("confronto_investimenti", importo=10000, investimenti=[
            {"nome": "X", "rendimento_lordo_pct": 3.0, "tipo_tassazione": valore, "durata_anni": 1},
        ])
        assert "errore" in r
        assert "tipo_tassazione" in r["errore"]
        assert "classifica" not in r

    @pytest.mark.parametrize("durata", [-2, 0, 2.9, 0.5])
    def test_durata_non_valida_errore(self, durata):
        # A negative or fractional horizon has no meaning for a whole-year compounding model.
        r = _call("confronto_investimenti", importo=10000, investimenti=[
            {"nome": "X", "rendimento_lordo_pct": 3.0, "tipo_tassazione": "titoli_stato", "durata_anni": durata},
        ])
        assert "durata_anni" in r.get("errore", "")

    def test_durata_intera_come_float_accettata(self):
        r = _call("confronto_investimenti", importo=10000, investimenti=[
            {"nome": "X", "rendimento_lordo_pct": 3.0, "tipo_tassazione": "titoli_stato", "durata_anni": 2.0},
        ])
        assert r["classifica"][0]["durata_anni"] == 2

    def test_rendimento_annualizzato_coerente_con_montante_netto(self):
        # Plan case 1: BTP 3,5% (12,50%) 5 years on 100.000: montante netto 116.422,55, hence
        # (1,1642255)^(1/5) - 1 = 3,0878%, against the 3,0625% of the annual-tax approximation.
        r = _call("confronto_investimenti", importo=100000, investimenti=[
            {"nome": "BTP", "rendimento_lordo_pct": 3.5, "tipo_tassazione": "titoli_stato", "durata_anni": 5},
        ])
        voce = r["classifica"][0]
        assert voce["montante_netto"] == pytest.approx(116422.55, abs=0.01)
        assert voce["rendimento_netto_pct"] == pytest.approx(3.0625, abs=1e-4)
        assert voce["rendimento_netto_annualizzato_pct"] == pytest.approx(3.0878, abs=1e-4)

    def test_rendimento_meno_cento_errore(self):
        r = _call("confronto_investimenti", importo=10000, investimenti=[
            {"nome": "X", "rendimento_lordo_pct": -100, "tipo_tassazione": "altro", "durata_anni": 1},
        ])
        assert "errore" in r

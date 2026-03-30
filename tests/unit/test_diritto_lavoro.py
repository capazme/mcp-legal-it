import importlib

import pytest


def _call(fn_name, **kwargs):
    mod = importlib.import_module("src.tools.diritto_lavoro")
    fn = getattr(mod, fn_name)
    actual = fn.fn if hasattr(fn, "fn") else fn
    return actual(**kwargs)


# ---------------------------------------------------------------------------
# indennita_licenziamento
# ---------------------------------------------------------------------------

class TestIndennitaLicenziamento:
    def test_grande_standard(self):
        r = _call("indennita_licenziamento", anni_servizio=5.0, retribuzione_mensile=2000.0)
        assert r["mensilita"] == 10.0
        assert r["importo"] == 20000.0
        assert r["dimensione_azienda"] == "grande"
        assert r["tipo"] == "indennitario"

    def test_grande_floor_applicato(self):
        # 1 anno × 2 = 2, ma floor è 6
        r = _call("indennita_licenziamento", anni_servizio=1.0, retribuzione_mensile=2000.0)
        assert r["mensilita"] == 6.0
        assert r["importo"] == 12000.0

    def test_grande_cap_applicato(self):
        # 20 anni × 2 = 40, ma cap è 36
        r = _call("indennita_licenziamento", anni_servizio=20.0, retribuzione_mensile=1000.0)
        assert r["mensilita"] == 36.0
        assert r["importo"] == 36000.0

    def test_piccola_floor_applicato(self):
        # 1 anno × 2 = 2, floor piccola = 3
        r = _call("indennita_licenziamento", anni_servizio=1.0, retribuzione_mensile=2000.0, dimensione_azienda="piccola")
        assert r["mensilita"] == 3.0
        assert r["importo"] == 6000.0

    def test_piccola_cap_applicato(self):
        # 20 anni × 2 = 40, cap piccola = 18
        r = _call("indennita_licenziamento", anni_servizio=20.0, retribuzione_mensile=1000.0, dimensione_azienda="piccola")
        assert r["mensilita"] == 18.0
        assert r["importo"] == 18000.0

    def test_reintegra(self):
        r = _call("indennita_licenziamento", anni_servizio=8.0, retribuzione_mensile=3000.0, tipo="reintegra")
        assert r["mensilita"] == 12.0  # capped at 12
        assert r["importo"] == 36000.0

    def test_reintegra_basso_anzianita(self):
        r = _call("indennita_licenziamento", anni_servizio=3.0, retribuzione_mensile=2000.0, tipo="reintegra")
        assert r["mensilita"] == 6.0  # 3 × 2 = 6
        assert r["importo"] == 12000.0

    def test_errore_anni_zero(self):
        with pytest.raises(ValueError, match="anni_servizio"):
            _call("indennita_licenziamento", anni_servizio=0, retribuzione_mensile=2000.0)

    def test_errore_retrib_negativa(self):
        with pytest.raises(ValueError, match="retribuzione_mensile"):
            _call("indennita_licenziamento", anni_servizio=5.0, retribuzione_mensile=-100.0)

    def test_errore_dimensione_invalida(self):
        with pytest.raises(ValueError, match="dimensione_azienda"):
            _call("indennita_licenziamento", anni_servizio=5.0, retribuzione_mensile=2000.0, dimensione_azienda="media")

    def test_riferimento_normativo(self):
        r = _call("indennita_licenziamento", anni_servizio=3.0, retribuzione_mensile=2000.0)
        assert "D.Lgs. 23/2015" in r["riferimento_normativo"]
        assert "C.Cost." in r["riferimento_normativo"]


# ---------------------------------------------------------------------------
# indennita_preavviso
# ---------------------------------------------------------------------------

class TestIndennitaPreavviso:
    def test_commercio_2_3_fino5_licenziamento(self):
        r = _call("indennita_preavviso", ccnl="commercio", livello="2_3", anzianita_anni=3.0, retribuzione_mensile=1800.0)
        assert r["giorni_preavviso"] == 30
        assert r["importo"] == round(1800.0 / 30 * 30, 2)
        assert r["fascia_anzianita"] == "fino_5"

    def test_commercio_quadri_5_10_licenziamento(self):
        r = _call("indennita_preavviso", ccnl="commercio", livello="quadri_1", anzianita_anni=7.0, retribuzione_mensile=4000.0)
        assert r["giorni_preavviso"] == 90
        assert r["fascia_anzianita"] == "5_10"

    def test_commercio_dimissioni(self):
        r = _call("indennita_preavviso", ccnl="commercio", livello="quadri_1", anzianita_anni=3.0, retribuzione_mensile=4000.0, tipo="dimissioni")
        assert r["giorni_preavviso"] == 45
        assert r["tipo"] == "dimissioni"

    def test_oltre_10_anni(self):
        r = _call("indennita_preavviso", ccnl="commercio", livello="4_5", anzianita_anni=12.0, retribuzione_mensile=2000.0)
        assert r["giorni_preavviso"] == 45
        assert r["fascia_anzianita"] == "oltre_10"

    def test_metalmeccanici_B1(self):
        r = _call("indennita_preavviso", ccnl="metalmeccanici", livello="B1_C2_C3", anzianita_anni=6.0, retribuzione_mensile=2200.0)
        assert r["giorni_preavviso"] == 60
        assert r["fascia_anzianita"] == "5_10"

    def test_studi_professionali(self):
        r = _call("indennita_preavviso", ccnl="studi_professionali", livello="3S_3", anzianita_anni=2.0, retribuzione_mensile=1500.0)
        assert r["giorni_preavviso"] == 30

    def test_errore_ccnl_non_trovato(self):
        with pytest.raises(ValueError, match="CCNL"):
            _call("indennita_preavviso", ccnl="inesistente", livello="1", anzianita_anni=3.0, retribuzione_mensile=2000.0)

    def test_errore_livello_non_trovato(self):
        with pytest.raises(ValueError, match="Livello"):
            _call("indennita_preavviso", ccnl="commercio", livello="99", anzianita_anni=3.0, retribuzione_mensile=2000.0)

    def test_errore_retrib_zero(self):
        with pytest.raises(ValueError, match="retribuzione_mensile"):
            _call("indennita_preavviso", ccnl="commercio", livello="2_3", anzianita_anni=3.0, retribuzione_mensile=0.0)

    def test_importo_calcolato_correttamente(self):
        r = _call("indennita_preavviso", ccnl="studi_professionali", livello="1", anzianita_anni=11.0, retribuzione_mensile=3000.0)
        # oltre_10 → 150 giorni licenziamento
        assert r["giorni_preavviso"] == 150
        expected = round(3000.0 / 30 * 150, 2)
        assert r["importo"] == expected


# ---------------------------------------------------------------------------
# calcolo_naspi
# ---------------------------------------------------------------------------

class TestCalcoloNaspi:
    def test_sotto_soglia(self):
        r = _call("calcolo_naspi", retribuzione_media_mensile=1000.0, settimane_contributive=104, eta_anni=40)
        assert r["importo_mensile_iniziale"] == round(0.75 * 1000.0, 2)
        assert r["durata_mesi"] == 12.0  # 104 / 2 / 4.33 ≈ 12

    def test_sopra_soglia(self):
        # 2000 > 1456.72
        r = _call("calcolo_naspi", retribuzione_media_mensile=2000.0, settimane_contributive=208, eta_anni=45)
        expected = round(0.75 * 1456.72 + 0.25 * (2000.0 - 1456.72), 2)
        assert r["importo_mensile_iniziale"] == expected
        assert r["durata_mesi"] == 24.0  # capped

    def test_massimale_applicato(self):
        r = _call("calcolo_naspi", retribuzione_media_mensile=5000.0, settimane_contributive=208, eta_anni=50)
        assert r["importo_mensile_iniziale"] == 1584.70

    def test_decalage_da_mese_55(self):
        r = _call("calcolo_naspi", retribuzione_media_mensile=1000.0, settimane_contributive=104, eta_anni=55)
        assert r["decalage_da_mese"] == 8

    def test_decalage_da_mese_normale(self):
        r = _call("calcolo_naspi", retribuzione_media_mensile=1000.0, settimane_contributive=104, eta_anni=40)
        assert r["decalage_da_mese"] == 6

    def test_piano_mensile_decalage(self):
        r = _call("calcolo_naspi", retribuzione_media_mensile=1000.0, settimane_contributive=208, eta_anni=40)
        piano = r["piano_mensile"]
        # First 6 months: no decalage
        for entry in piano[:6]:
            assert entry["importo"] == r["importo_mensile_iniziale"]

    def test_errore_retrib_zero(self):
        with pytest.raises(ValueError, match="retribuzione_media_mensile"):
            _call("calcolo_naspi", retribuzione_media_mensile=0.0, settimane_contributive=104, eta_anni=40)

    def test_errore_settimane_zero(self):
        with pytest.raises(ValueError, match="settimane_contributive"):
            _call("calcolo_naspi", retribuzione_media_mensile=1000.0, settimane_contributive=0, eta_anni=40)

    def test_riferimento_normativo(self):
        r = _call("calcolo_naspi", retribuzione_media_mensile=1500.0, settimane_contributive=104, eta_anni=42)
        assert "D.Lgs. 22/2015" in r["riferimento_normativo"]


# ---------------------------------------------------------------------------
# scadenze_licenziamento
# ---------------------------------------------------------------------------

class TestScadenzeLicenziamento:
    def test_calcolo_date(self):
        r = _call("scadenze_licenziamento", data_licenziamento="2025-01-01")
        s = r["scadenze"]
        assert s["impugnazione_stragiudiziale"]["data"] == "2025-03-02"  # +60
        assert s["deposito_ricorso"]["termine_giorni"] == 180
        assert s["post_conciliazione"]["termine_giorni"] == 60

    def test_deposito_ricorso_decorre_da_impugnazione(self):
        r = _call("scadenze_licenziamento", data_licenziamento="2025-01-01")
        from datetime import date
        dt_imp = date.fromisoformat(r["scadenze"]["impugnazione_stragiudiziale"]["data"])
        dt_dep = date.fromisoformat(r["scadenze"]["deposito_ricorso"]["data"])
        assert (dt_dep - dt_imp).days == 180

    def test_post_conciliazione_decorre_da_deposito(self):
        r = _call("scadenze_licenziamento", data_licenziamento="2025-06-01")
        from datetime import date
        dt_dep = date.fromisoformat(r["scadenze"]["deposito_ricorso"]["data"])
        dt_post = date.fromisoformat(r["scadenze"]["post_conciliazione"]["data"])
        assert (dt_post - dt_dep).days == 60

    def test_struttura_output(self):
        r = _call("scadenze_licenziamento", data_licenziamento="2025-03-15")
        assert "scadenze" in r
        assert "avvertimenti" in r
        assert "nota" in r
        assert "impugnazione_stragiudiziale" in r["scadenze"]
        assert "deposito_ricorso" in r["scadenze"]
        assert "post_conciliazione" in r["scadenze"]

    def test_riferimento_normativo(self):
        r = _call("scadenze_licenziamento", data_licenziamento="2025-01-01")
        assert "L. 604/1966" in r["riferimento_normativo"]
        assert "L. 183/2010" in r["riferimento_normativo"]


# ---------------------------------------------------------------------------
# costo_lavoro
# ---------------------------------------------------------------------------

class TestCostoLavoro:
    def test_dipendente_standard(self):
        r = _call("costo_lavoro", retribuzione_lorda_annua=30000.0)
        assert r["lordo_annuo"] == 30000.0
        assert r["tipo_contratto"] == "dipendente"
        assert r["costo_azienda_totale"] > 30000.0
        assert r["netto_stimato"] < 30000.0
        assert 0 < r["cuneo_fiscale_pct"] < 100

    def test_netto_minore_di_lordo(self):
        r = _call("costo_lavoro", retribuzione_lorda_annua=25000.0)
        assert r["netto_stimato"] < r["lordo_annuo"]

    def test_costo_totale_maggiore_di_lordo(self):
        r = _call("costo_lavoro", retribuzione_lorda_annua=40000.0)
        assert r["costo_azienda_totale"] > r["lordo_annuo"]

    def test_apprendista_contributi_ridotti(self):
        r_dip = _call("costo_lavoro", retribuzione_lorda_annua=20000.0, tipo_contratto="dipendente")
        r_app = _call("costo_lavoro", retribuzione_lorda_annua=20000.0, tipo_contratto="apprendista")
        assert r_app["contributi_datore"] < r_dip["contributi_datore"]

    def test_dirigente(self):
        r = _call("costo_lavoro", retribuzione_lorda_annua=80000.0, tipo_contratto="dirigente")
        assert r["tipo_contratto"] == "dirigente"
        assert r["costo_azienda_totale"] > 80000.0

    def test_errore_lordo_zero(self):
        with pytest.raises(ValueError, match="retribuzione_lorda_annua"):
            _call("costo_lavoro", retribuzione_lorda_annua=0.0)

    def test_errore_tipo_invalido(self):
        with pytest.raises(ValueError, match="tipo_contratto"):
            _call("costo_lavoro", retribuzione_lorda_annua=30000.0, tipo_contratto="freelance")

    def test_campi_output_presenti(self):
        r = _call("costo_lavoro", retribuzione_lorda_annua=30000.0)
        for campo in ["contributi_dipendente", "irpef_stimata", "netto_stimato",
                      "contributi_datore", "tfr_annuo", "irap_stimata",
                      "costo_azienda_totale", "cuneo_fiscale_pct"]:
            assert campo in r, f"Campo mancante: {campo}"


# ---------------------------------------------------------------------------
# offerta_conciliativa
# ---------------------------------------------------------------------------

class TestOffertaConciliativa:
    def test_grande_standard(self):
        r = _call("offerta_conciliativa", anni_servizio=5.0, retribuzione_mensile=2000.0)
        assert r["mensilita"] == 5.0
        assert r["importo"] == 10000.0
        assert r["detassato"] is True

    def test_grande_floor(self):
        # 1 anno ma floor = 3
        r = _call("offerta_conciliativa", anni_servizio=1.0, retribuzione_mensile=2000.0)
        assert r["mensilita"] == 3.0
        assert r["importo"] == 6000.0

    def test_grande_cap(self):
        # 30 anni ma cap = 27
        r = _call("offerta_conciliativa", anni_servizio=30.0, retribuzione_mensile=1000.0)
        assert r["mensilita"] == 27.0
        assert r["importo"] == 27000.0

    def test_piccola_floor(self):
        r = _call("offerta_conciliativa", anni_servizio=1.0, retribuzione_mensile=2000.0, dimensione_azienda="piccola")
        assert r["mensilita"] == 1.5
        assert r["importo"] == 3000.0

    def test_piccola_cap(self):
        r = _call("offerta_conciliativa", anni_servizio=20.0, retribuzione_mensile=1000.0, dimensione_azienda="piccola")
        assert r["mensilita"] == 13.5
        assert r["importo"] == 13500.0

    def test_errore_anni_zero(self):
        with pytest.raises(ValueError, match="anni_servizio"):
            _call("offerta_conciliativa", anni_servizio=0.0, retribuzione_mensile=2000.0)

    def test_errore_retrib_negativa(self):
        with pytest.raises(ValueError, match="retribuzione_mensile"):
            _call("offerta_conciliativa", anni_servizio=5.0, retribuzione_mensile=-1.0)

    def test_errore_dimensione_invalida(self):
        with pytest.raises(ValueError, match="dimensione_azienda"):
            _call("offerta_conciliativa", anni_servizio=5.0, retribuzione_mensile=2000.0, dimensione_azienda="media")

    def test_riferimento_normativo(self):
        r = _call("offerta_conciliativa", anni_servizio=5.0, retribuzione_mensile=2000.0)
        assert "D.Lgs. 23/2015 art. 6" in r["riferimento_normativo"]

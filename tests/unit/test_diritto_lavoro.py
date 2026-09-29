import importlib

import pytest

from .mcp_harness import tool_body


def _call(fn_name, **kwargs):
    mod = importlib.import_module("src.tools.diritto_lavoro")
    return tool_body(getattr(mod, fn_name))(**kwargs)


def _call_full(fn_name, **kwargs):
    """The tool under `@sourced` (table vintage and precision policy), as a host runs it."""
    from src.lib import _clock, _precision, _tables_open

    mod = importlib.import_module("src.tools.diritto_lavoro")
    fn = getattr(mod, fn_name)
    fn = getattr(fn, "fn", fn)
    with _tables_open.recording(), _clock.recording(), _precision.recording():
        return fn(**kwargs)


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
        # Art. 3 co. 2 D.Lgs. 23/2015: the damages for the period before the ruling are
        # capped at twelve mensilita whatever the seniority (3 years is not 3 x 2 = 6).
        r = _call("indennita_licenziamento", anni_servizio=3.0, retribuzione_mensile=2000.0, tipo="reintegra")
        assert r["mensilita"] == 12
        assert r["massimo_mensilita"] == 12
        assert r["importo"] == 24000.0
        assert "anzianità" in r["dettaglio_formula"]

    def test_reintegra_tetto_indipendente_dall_anzianita(self):
        # Art. 3 co. 2: no link between seniority and the reinstatement damages ceiling.
        r1 = _call("indennita_licenziamento", anni_servizio=0.5, retribuzione_mensile=1500.0, tipo="reintegra")
        r30 = _call("indennita_licenziamento", anni_servizio=30.0, retribuzione_mensile=1500.0, tipo="reintegra")
        assert r1["mensilita"] == r30["mensilita"] == 12
        assert r1["importo"] == r30["importo"] == 18000.0

    def test_reintegra_esclusa_per_datore_sotto_soglia(self):
        # Art. 9 co. 1 D.Lgs. 23/2015: below the art. 18 St. lav. threshold "non si applica
        # l'articolo 3, comma 2": the reinstatement branch is refused, not computed.
        with pytest.raises(ValueError, match="art. 9 co. 1"):
            _call("indennita_licenziamento", anni_servizio=3.0, retribuzione_mensile=2000.0,
                  dimensione_azienda="piccola", tipo="reintegra")

    def test_piccola_indennitario_resta_dimezzato_3_18(self):
        # The same small employer keeps the halved indemnity of art. 9 co. 1 (3-18 after
        # C.Cost. 118/2025): 3 years -> 3 mensilita = 6.000 euro.
        r = _call("indennita_licenziamento", anni_servizio=3.0, retribuzione_mensile=2000.0,
                  dimensione_azienda="piccola")
        assert (r["minimo_mensilita"], r["massimo_mensilita"]) == (3, 18)
        assert r["mensilita"] == 3.0 and r["importo"] == 6000.0

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

    def test_nessun_doppio_arrotondamento(self):
        # Art. 2118 co. 2 c.c.: 150 days of calendar are five months, so on 1.000 euro the
        # indemnity is 5.000,00 (art. 146 CCNL studi professionali, level I, over 10 years).
        # The daily rate 33,3333 multiplied by 150 gave 4.999,99.
        r = _call("indennita_preavviso", ccnl="studi_professionali", livello="1", anzianita_anni=11.0, retribuzione_mensile=1000.0)
        assert r["giorni_preavviso"] == 150
        assert r["importo"] == 5000.0

    @pytest.mark.parametrize(
        "anzianita, mensilita, importo",
        [
            # CCNL industria metalmeccanica 5/2/2021, Sez. IV Tit. VIII art. 1, second table
            # (indennita' in mensilita'): levels D1, D2, C1 = 0,33 / 0,67 / 1 mensilita.
            (5.0, 0.33, 726.00),
            (10.0, 0.67, 1474.00),
            (10.5, 1, 2200.00),
        ],
    )
    def test_metalmeccanici_c1_d1_d2_indennita_in_mensilita_del_ccnl(self, anzianita, mensilita, importo):
        r = _call("indennita_preavviso", ccnl="metalmeccanici", livello="C1_D1_D2", anzianita_anni=anzianita, retribuzione_mensile=2200.0)
        assert r["importo"] == importo
        assert f"{mensilita} mensilità" in r["base_importo"]

    def test_metalmeccanici_altri_livelli_invariati(self):
        # Same table: B1_C2_C3 over 10 years = 2,5 mensilita = 75 days (the two tables agree).
        r = _call("indennita_preavviso", ccnl="metalmeccanici", livello="B1_C2_C3", anzianita_anni=10.5, retribuzione_mensile=2200.0)
        assert r["giorni_preavviso"] == 75
        assert r["importo"] == 5500.0

    def test_metalmeccanici_dimissioni_stessa_indennita(self):
        # The term binds "nessuna delle due parti" (art. 1): the same indemnity is due on resignation.
        r = _call("indennita_preavviso", ccnl="metalmeccanici", livello="C1_D1_D2", anzianita_anni=3.0,
                  retribuzione_mensile=2200.0, tipo="dimissioni")
        assert r["importo"] == 726.0

    @pytest.mark.parametrize("livello", ["quadri", "quadri_1"])
    def test_studi_professionali_quadri_come_livello_1(self, livello):
        # Art. 146 lett. A and B CCNL studi professionali 16/2/2024: Quadri have the periods of level I
        # (licenziamento 90/120/150, dimissioni 75/105/135 days).
        r = _call("indennita_preavviso", ccnl="studi_professionali", livello=livello, anzianita_anni=11.0, retribuzione_mensile=3000.0)
        assert r["giorni_preavviso"] == 150 and r["importo"] == 15000.0
        r = _call("indennita_preavviso", ccnl="studi_professionali", livello=livello, anzianita_anni=11.0,
                  retribuzione_mensile=3000.0, tipo="dimissioni")
        assert r["giorni_preavviso"] == 135 and r["importo"] == 13500.0

    def test_riferimento_terziario_artt_251_252_256(self):
        # TU CCNL Terziario 3/2/2026: terms in art. 251 (licenziamento) and 256 (dimissioni), indemnity in
        # art. 252; art. 254 is "Decesso del dipendente" and must not be cited.
        r = _call("indennita_preavviso", ccnl="commercio", livello="2_3", anzianita_anni=3.0, retribuzione_mensile=1800.0)
        assert "251" in r["riferimento_normativo"] and "256" in r["riferimento_normativo"]
        assert "254" not in r["riferimento_normativo"]


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
        # Art. 4 co. 3 D.Lgs. 22/2015: the reduction starts on the first day of the SIXTH month,
        # so months 1-5 are paid in full and month 6 is already reduced by 3%.
        for entry in piano[:5]:
            assert entry["importo"] == r["importo_mensile_iniziale"]
        assert piano[5]["importo"] == 727.50  # 750,00 x 0,97

    def test_decalage_dal_sesto_mese_art_4_co_3(self, monkeypatch):
        monkeypatch.setenv("LEGAL_TODAY", "2026-09-29")
        r = _call("calcolo_naspi", retribuzione_media_mensile=1000.0, settimane_contributive=104, eta_anni=40)
        piano = {m["mese"]: m["importo"] for m in r["piano_mensile"]}
        assert piano[5] == 750.00
        assert piano[6] == 727.50  # 750 x 0,97
        assert piano[12] == 605.99  # 750 x 0,97^7 (each month 3% less than the month before)
        assert r["decalage_da_mese"] == 6

    def test_decalage_dall_ottavo_mese_da_55_anni(self, monkeypatch):
        # Art. 4 co. 3: for who is 55 at the application the reduction starts from the eighth month.
        monkeypatch.setenv("LEGAL_TODAY", "2026-09-29")
        r = _call("calcolo_naspi", retribuzione_media_mensile=3500.0, settimane_contributive=208, eta_anni=55)
        piano = {m["mese"]: m["importo"] for m in r["piano_mensile"]}
        assert piano[6] == 1584.70  # massimale 2026 (circ. INPS 4/2026), still in full
        assert piano[24] == 944.21  # 1.584,70 x 0,97^17
        r54 = _call("calcolo_naspi", retribuzione_media_mensile=3500.0, settimane_contributive=208, eta_anni=54)
        assert {m["mese"]: m["importo"] for m in r54["piano_mensile"]}[24] == 888.40  # 1.584,70 x 0,97^19 (from month 6)

    def test_requisito_tredici_settimane_art_3_co_1_lett_b(self, monkeypatch):
        # Art. 3 co. 1 lett. b D.Lgs. 22/2015: at least 13 weeks of contribution in the four years,
        # otherwise the NASpI is not due. Plan case 5: 12 weeks, 1.200 euro, 30 years.
        monkeypatch.setenv("LEGAL_TODAY", "2026-09-29")
        r = _call("calcolo_naspi", retribuzione_media_mensile=1200.0, settimane_contributive=12, eta_anni=30)
        assert r["esito"] == "non_spettante"
        assert r["importo_mensile_iniziale"] == 0.0
        assert r["durata_mesi"] == 0
        assert r["totale_stimato"] == 0.0
        assert "lett. b" in r["motivo"]

    def test_tredici_settimane_bastano(self, monkeypatch):
        # Boundary of the same requirement: 13 weeks -> 75% of 1.200 = 900,00 for 13/2 weeks = 1,5 months
        # (art. 5: half of the weeks; art. 4 co. 1: 4,33 weeks per month), total 900 + 450.
        monkeypatch.setenv("LEGAL_TODAY", "2026-09-29")
        r = _call("calcolo_naspi", retribuzione_media_mensile=1200.0, settimane_contributive=13, eta_anni=30)
        assert r["esito"] == "calcolato"
        assert r["importo_mensile_iniziale"] == 900.00
        assert r["durata_mesi"] == 1.5
        assert r["totale_stimato"] == 1350.00

    def test_parametri_2026_da_tabella_circolare_inps_4_2026(self, monkeypatch):
        # Circ. INPS n. 4 del 28-01-2026 par. 6: retribuzione di riferimento 1.456,72, massimo mensile 1.584,70.
        monkeypatch.setenv("LEGAL_TODAY", "2026-09-29")
        r = _call_full("calcolo_naspi", retribuzione_media_mensile=2000.0, settimane_contributive=104, eta_anni=40)
        assert r["anno_parametri"] == 2026
        assert r["soglia_2026"] == 1456.72 and r["massimale_2026"] == 1584.70
        assert any("inps parametri" in riga for riga in r["dati_applicati"])

    def test_dal_2027_i_valori_2026_non_vengono_applicati_in_silenzio(self, monkeypatch):
        # The 2026 values cover up to 2026-12-31: in 2027 the tool refuses instead of applying them.
        monkeypatch.setenv("LEGAL_TODAY", "2027-01-15")
        r = _call_full("calcolo_naspi", retribuzione_media_mensile=2000.0, settimane_contributive=104, eta_anni=40)
        assert r["errore"] == "dati_non_affidabili"
        assert "inps_parametri" in {t["tabella"] for t in r["tabelle"]}

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

    def test_post_conciliazione_solo_con_data_rifiuto(self):
        r = _call("scadenze_licenziamento", data_licenziamento="2025-06-01")
        assert r["scadenze"]["post_conciliazione"]["data"] is None
        r2 = _call("scadenze_licenziamento", data_licenziamento="2025-06-01",
                   data_rifiuto_conciliazione="2025-10-01")
        # Art. 6 co. 2 L. 604/1966: 60 giorni dal rifiuto o dal mancato accordo
        assert r2["scadenze"]["post_conciliazione"]["data"] == "2025-11-30"

    def test_deposito_decorre_dall_impugnazione_effettiva(self):
        r = _call("scadenze_licenziamento", data_licenziamento="2025-06-01", data_impugnazione="2025-06-10")
        assert r["scadenze"]["deposito_ricorso"]["data"] == "2025-12-07"
        assert r["scadenze"]["deposito_ricorso"]["decorre_da"] == "2025-06-10"
        tardiva = _call("scadenze_licenziamento", data_licenziamento="2025-06-01", data_impugnazione="2025-09-01")
        assert any("decadenza" in a for a in tardiva["avvertimenti"])

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
        # Piccole imprese: dimezzamento ×0,5 (art. 9 c.1, NON toccato dalla Corte). Il tetto di
        # 6 mensilità è stato abrogato da Corte Cost. 118/2025 e ricostruito come 13,5 (=27/2).
        # 30 anni × 0,5 = 15 → cap 13,5.
        r = _call("offerta_conciliativa", anni_servizio=30.0, retribuzione_mensile=1000.0, dimensione_azienda="piccola")
        assert r["mensilita"] == 13.5
        assert r["importo"] == 13500.0
        assert r["cap_mensilita"] == 13.5

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
        assert "D.Lgs. 23/2015" in r["riferimento_normativo"]
        assert "118/2025" in r["riferimento_normativo"]

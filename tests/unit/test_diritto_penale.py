import importlib

import pytest


def _call(fn_name: str, **kwargs):
    mod = importlib.import_module("src.tools.diritto_penale")
    fn = getattr(mod, fn_name)
    actual = fn.fn if hasattr(fn, "fn") else fn
    return actual(**kwargs)


# ---------------------------------------------------------------------------
# aumenti_riduzioni_pena
# ---------------------------------------------------------------------------

class TestAumentiRiduzioniPena:
    def test_pena_base_senza_modifiche(self):
        result = _call("aumenti_riduzioni_pena", pena_base_mesi=24)
        assert result["pena_base_mesi"] == 24
        assert result["pena_risultante_mesi"] == 24
        assert result["pena_risultante_formato"] == "2 anni e 0 mesi"
        assert result["recidiva_applicata"] is False
        assert len(result["dettaglio"]) == 1

    def test_recidiva_applica_un_terzo(self):
        result = _call("aumenti_riduzioni_pena", pena_base_mesi=12, recidiva=True)
        assert result["pena_risultante_mesi"] == 16.0
        assert result["recidiva_applicata"] is True
        assert any("Recidiva" in s["step"] for s in result["dettaglio"])

    def test_aggravante_percentuale(self):
        aggravanti = [{"tipo": "art. 61 n.1", "aumento_pct": 33.33}]
        result = _call("aumenti_riduzioni_pena", pena_base_mesi=12, aggravanti=aggravanti)
        assert result["pena_risultante_mesi"] == pytest.approx(16.0, abs=0.1)

    def test_attenuante_riduce_pena(self):
        attenuanti = [{"tipo": "art. 62 n.6", "riduzione_pct": 33.33}]
        result = _call("aumenti_riduzioni_pena", pena_base_mesi=12, attenuanti=attenuanti)
        assert result["pena_risultante_mesi"] == pytest.approx(8.0, abs=0.1)

    def test_recidiva_poi_aggravante_poi_attenuante(self):
        aggravanti = [{"tipo": "aggravante_test", "aumento_pct": 50}]
        attenuanti = [{"tipo": "attenuante_test", "riduzione_pct": 50}]
        result = _call(
            "aumenti_riduzioni_pena",
            pena_base_mesi=12,
            recidiva=True,
            aggravanti=aggravanti,
            attenuanti=attenuanti,
        )
        # 12 -> 16 (recidiva +1/3) -> 24 (aggravante +50%) -> 12 (attenuante -50%)
        assert result["pena_risultante_mesi"] == pytest.approx(12.0, abs=0.01)
        assert len(result["dettaglio"]) == 4

    def test_pena_solo_mesi_formato(self):
        result = _call("aumenti_riduzioni_pena", pena_base_mesi=6)
        assert "anni" not in result["pena_risultante_formato"]
        assert "mesi" in result["pena_risultante_formato"]

    def test_pena_anni_e_mesi_formato(self):
        result = _call("aumenti_riduzioni_pena", pena_base_mesi=30)
        assert "2 anni" in result["pena_risultante_formato"]
        assert "6" in result["pena_risultante_formato"]

    def test_aggravanti_none_non_aggiunge_steps(self):
        result = _call("aumenti_riduzioni_pena", pena_base_mesi=24, aggravanti=None, attenuanti=None)
        assert len(result["dettaglio"]) == 1

    def test_piu_aggravanti_applicate_in_sequenza(self):
        aggravanti = [
            {"tipo": "prima", "aumento_pct": 10},
            {"tipo": "seconda", "aumento_pct": 10},
        ]
        result = _call("aumenti_riduzioni_pena", pena_base_mesi=100, aggravanti=aggravanti)
        # 100 -> 110 -> 121
        assert result["pena_risultante_mesi"] == pytest.approx(121.0, abs=0.01)

    def test_riferimento_normativo_presente(self):
        result = _call("aumenti_riduzioni_pena", pena_base_mesi=12)
        assert "63" in result["riferimento_normativo"]


# ---------------------------------------------------------------------------
# conversione_pena
# ---------------------------------------------------------------------------

class TestConversionePena:
    def test_detentiva_a_pecuniaria_base(self):
        result = _call("conversione_pena", importo=10, direzione="detentiva_a_pecuniaria")
        assert result["giorni_detentivi"] == 10
        assert result["importo_pecuniario_euro"] == 2500.0
        assert result["tasso_conversione"] == "€250/giorno"

    def test_pecuniaria_a_detentiva_base(self):
        result = _call("conversione_pena", importo=1000, direzione="pecuniaria_a_detentiva")
        assert result["importo_pecuniario_euro"] == 1000
        assert result["giorni_detentivi"] == 4

    def test_pecuniaria_a_detentiva_arrotondamento_ceil(self):
        # 300 / 250 = 1.2 -> ceil = 2
        result = _call("conversione_pena", importo=300, direzione="pecuniaria_a_detentiva")
        assert result["giorni_detentivi"] == 2

    def test_tipo_pena_arresto(self):
        result = _call(
            "conversione_pena", importo=5, direzione="detentiva_a_pecuniaria", tipo_pena="arresto"
        )
        assert result["tipo_pena"] == "arresto"
        assert result["importo_pecuniario_euro"] == 1250.0

    def test_direzione_default_e_tipo_default(self):
        result = _call("conversione_pena", importo=1)
        assert result["direzione"] == "detentiva_a_pecuniaria"
        assert result["tipo_pena"] == "reclusione"

    def test_conversione_zero_giorni(self):
        result = _call("conversione_pena", importo=0, direzione="detentiva_a_pecuniaria")
        assert result["importo_pecuniario_euro"] == 0.0

    def test_riferimento_normativo_art135(self):
        result = _call("conversione_pena", importo=1)
        assert "135" in result["riferimento_normativo"]

    def test_pecuniaria_esatta_divisione(self):
        result = _call("conversione_pena", importo=2500, direzione="pecuniaria_a_detentiva")
        assert result["giorni_detentivi"] == 10


# ---------------------------------------------------------------------------
# fine_pena
# ---------------------------------------------------------------------------

class TestFinePena:
    def test_fine_pena_base_senza_benefici(self):
        result = _call(
            "fine_pena",
            data_inizio_pena="2024-01-01",
            pena_totale_mesi=12,
            liberazione_anticipata=False,
            giorni_presofferto=0,
        )
        assert result["data_fine_pena"] == "2025-01-01"
        assert "liberazione_anticipata" not in result

    def test_fine_pena_con_presofferto(self):
        result = _call(
            "fine_pena",
            data_inizio_pena="2024-01-01",
            pena_totale_mesi=12,
            liberazione_anticipata=False,
            giorni_presofferto=30,
        )
        # inizio effettivo = 2023-12-02; fine = 2024-12-02
        assert result["data_inizio_effettiva"] == "2023-12-02"
        assert result["data_fine_pena"] == "2024-12-02"

    def test_liberazione_anticipata_calcola_sconto(self):
        result = _call(
            "fine_pena",
            data_inizio_pena="2024-01-01",
            pena_totale_mesi=24,
            liberazione_anticipata=True,
            giorni_presofferto=0,
        )
        la = result["liberazione_anticipata"]
        # 24 mesi ~ 730 giorni -> 4 semestri -> 180 giorni di sconto
        assert la["semestri_scontati"] == 4
        assert la["sconto_giorni"] == 180

    def test_presofferto_riduce_inizio_effettivo(self):
        result = _call(
            "fine_pena",
            data_inizio_pena="2024-06-01",
            pena_totale_mesi=6,
            liberazione_anticipata=False,
            giorni_presofferto=60,
        )
        assert result["giorni_presofferto"] == 60
        assert result["data_inizio_effettiva"] == "2024-04-02"

    def test_fine_pena_data_formato_iso(self):
        result = _call(
            "fine_pena",
            data_inizio_pena="2023-03-15",
            pena_totale_mesi=6,
            liberazione_anticipata=False,
        )
        dt = result["data_fine_pena"]
        assert len(dt) == 10 and dt[4] == "-" and dt[7] == "-"

    def test_riferimento_normativo_l354(self):
        result = _call(
            "fine_pena",
            data_inizio_pena="2024-01-01",
            pena_totale_mesi=12,
        )
        assert "354" in result["riferimento_normativo"]

    def test_pena_frazionaria_mesi(self):
        result = _call(
            "fine_pena",
            data_inizio_pena="2024-01-01",
            pena_totale_mesi=12.5,
            liberazione_anticipata=False,
        )
        # 12.5 mesi: 12 interi + 15 giorni frazionari
        assert result["data_fine_pena"] == "2025-01-16"


# ---------------------------------------------------------------------------
# prescrizione_reato
# ---------------------------------------------------------------------------

class TestPrescrizioneReato:
    def test_delitto_minimo_sei_anni(self):
        result = _call(
            "prescrizione_reato",
            pena_massima_anni=2.0,
            data_commissione="2010-01-01",
            tipo_reato="delitto",
        )
        assert result["termine_base_anni"] == 6

    def test_contravvenzione_minimo_quattro_anni(self):
        result = _call(
            "prescrizione_reato",
            pena_massima_anni=0.5,
            data_commissione="2010-01-01",
            tipo_reato="contravvenzione",
        )
        assert result["termine_base_anni"] == 4

    def test_pena_superiore_al_minimo_usata(self):
        result = _call(
            "prescrizione_reato",
            pena_massima_anni=10.0,
            data_commissione="2010-01-01",
            tipo_reato="delitto",
        )
        assert result["termine_base_anni"] == 10

    def test_interruzione_aggiunge_un_quarto(self):
        result = _call(
            "prescrizione_reato",
            pena_massima_anni=8.0,
            data_commissione="2010-01-01",
            interruzioni_giorni=1,
        )
        assert result["aumento_interruzione_anni"] == pytest.approx(2.0, abs=0.01)
        assert result["termine_totale_anni"] == pytest.approx(10.0, abs=0.01)

    def test_sospensione_sposta_data(self):
        result_no_sosp = _call(
            "prescrizione_reato",
            pena_massima_anni=6.0,
            data_commissione="2010-01-01",
            sospensioni_giorni=0,
        )
        result_sosp = _call(
            "prescrizione_reato",
            pena_massima_anni=6.0,
            data_commissione="2010-01-01",
            sospensioni_giorni=100,
        )
        from datetime import date
        dt_no = date.fromisoformat(result_no_sosp["data_prescrizione"])
        dt_si = date.fromisoformat(result_sosp["data_prescrizione"])
        assert (dt_si - dt_no).days == 100

    def test_reato_prescritto_recente(self):
        result = _call(
            "prescrizione_reato",
            pena_massima_anni=2.0,
            data_commissione="2000-01-01",
            tipo_reato="delitto",
        )
        assert result["prescritto"] is True
        assert result["giorni_alla_prescrizione"] == 0

    def test_reato_non_prescritto_futuro(self):
        result = _call(
            "prescrizione_reato",
            pena_massima_anni=30.0,
            data_commissione="2025-01-01",
            tipo_reato="delitto",
        )
        assert result["prescritto"] is False
        assert result["giorni_alla_prescrizione"] > 0

    def test_riferimento_normativo_art157(self):
        result = _call(
            "prescrizione_reato",
            pena_massima_anni=5.0,
            data_commissione="2020-01-01",
        )
        assert "157" in result["riferimento_normativo"]

    def test_senza_interruzioni_aumento_zero(self):
        result = _call(
            "prescrizione_reato",
            pena_massima_anni=6.0,
            data_commissione="2020-01-01",
            interruzioni_giorni=0,
        )
        assert result["aumento_interruzione_anni"] == 0.0

    def test_tipo_reato_default_delitto(self):
        result = _call(
            "prescrizione_reato",
            pena_massima_anni=2.0,
            data_commissione="2010-01-01",
        )
        assert result["tipo_reato"] == "delitto"


# ---------------------------------------------------------------------------
# pena_concordata
# ---------------------------------------------------------------------------

class TestPenaConcordata:
    def test_tutte_riduzioni_applicate(self):
        result = _call(
            "pena_concordata",
            pena_base_mesi=36,
            attenuanti_generiche=True,
            diminuente_rito=True,
        )
        # 36 -> 24 (-1/3) -> 16 (-1/3)
        assert result["pena_finale_mesi"] == pytest.approx(16.0, abs=0.01)
        assert result["pena_finale_formato"] == "1 anni e 4.0 mesi"

    def test_solo_attenuanti_generiche(self):
        result = _call(
            "pena_concordata",
            pena_base_mesi=36,
            attenuanti_generiche=True,
            diminuente_rito=False,
        )
        assert result["pena_finale_mesi"] == pytest.approx(24.0, abs=0.01)

    def test_solo_diminuente_rito(self):
        result = _call(
            "pena_concordata",
            pena_base_mesi=36,
            attenuanti_generiche=False,
            diminuente_rito=True,
        )
        assert result["pena_finale_mesi"] == pytest.approx(24.0, abs=0.01)

    def test_nessuna_riduzione(self):
        result = _call(
            "pena_concordata",
            pena_base_mesi=36,
            attenuanti_generiche=False,
            diminuente_rito=False,
        )
        assert result["pena_finale_mesi"] == 36.0

    def test_patteggiamento_possibile_sotto_60_mesi(self):
        result = _call("pena_concordata", pena_base_mesi=36)
        assert result["patteggiamento_possibile"] is True

    def test_patteggiamento_non_possibile_sopra_60_mesi(self):
        # Con sole riduzioni di 1/3+1/3, da 120 -> 80 -> 53.3 -> ancora possibile
        # Usiamo pena alta senza riduzioni
        result = _call(
            "pena_concordata",
            pena_base_mesi=200,
            attenuanti_generiche=False,
            diminuente_rito=False,
        )
        assert result["patteggiamento_possibile"] is False

    def test_sospendibile_sotto_24_mesi(self):
        result = _call(
            "pena_concordata",
            pena_base_mesi=24,
            attenuanti_generiche=False,
            diminuente_rito=False,
        )
        assert result["sospendibile"] is True

    def test_sospendibile_false_sopra_24_mesi(self):
        result = _call(
            "pena_concordata",
            pena_base_mesi=100,
            attenuanti_generiche=False,
            diminuente_rito=False,
        )
        assert result["sospendibile"] is False

    def test_dettaglio_steps_con_entrambe_riduzioni(self):
        result = _call("pena_concordata", pena_base_mesi=36)
        assert len(result["dettaglio"]) == 3  # base + 2 riduzioni

    def test_dettaglio_steps_senza_riduzioni(self):
        result = _call(
            "pena_concordata",
            pena_base_mesi=36,
            attenuanti_generiche=False,
            diminuente_rito=False,
        )
        assert len(result["dettaglio"]) == 1

    def test_nota_sospensione_presente(self):
        result = _call("pena_concordata", pena_base_mesi=12)
        assert "nota_sospensione" in result

    def test_riferimento_normativo_444cpp(self):
        result = _call("pena_concordata", pena_base_mesi=24)
        assert "444" in result["riferimento_normativo"]

    def test_pena_solo_mesi_formato(self):
        result = _call(
            "pena_concordata",
            pena_base_mesi=6,
            attenuanti_generiche=False,
            diminuente_rito=False,
        )
        assert "anni" not in result["pena_finale_formato"]

    def test_pena_default_riduzioni_abilitate(self):
        result = _call("pena_concordata", pena_base_mesi=36)
        assert result["attenuanti_generiche"] is True
        assert result["diminuente_rito"] is True

import importlib

import pytest


def _call(fn_name: str, **kwargs):
    mod = importlib.import_module("src.tools.diritto_societario")
    fn = getattr(mod, fn_name)
    actual = fn.fn if hasattr(fn, "fn") else fn
    return actual(**kwargs)


# ---------------------------------------------------------------------------
# quorum_assembleari
# ---------------------------------------------------------------------------

class TestQuorumAssembleari:
    def test_spa_ordinaria_quorum_raggiunto(self):
        result = _call(
            "quorum_assembleari",
            tipo_societa="spa",
            tipo_delibera="ordinaria",
            capitale_totale=1_000_000,
            capitale_presente=600_000,
            voti_favorevoli=400_000,
        )
        assert result["tipo_societa"] == "spa"
        assert result["tipo_delibera"] == "ordinaria"
        assert result["raggiunto_costitutivo"] is True
        assert result["raggiunto_deliberativo"] is True
        assert result["delibera_valida"] is True
        assert "2368" in result["riferimento_normativo"]

    def test_spa_ordinaria_quorum_non_raggiunto(self):
        result = _call(
            "quorum_assembleari",
            tipo_societa="spa",
            tipo_delibera="ordinaria",
            capitale_totale=1_000_000,
            capitale_presente=400_000,  # < 50%
            voti_favorevoli=300_000,
        )
        assert result["raggiunto_costitutivo"] is False

    def test_spa_straordinaria_deliberativo_2_terzi(self):
        result = _call(
            "quorum_assembleari",
            tipo_societa="spa",
            tipo_delibera="straordinaria",
            capitale_totale=1_000_000,
            capitale_presente=800_000,
            voti_favorevoli=600_000,  # 75% dei presenti >= 66.67%
        )
        assert result["raggiunto_deliberativo"] is True

    def test_spa_straordinaria_deliberativo_sotto_soglia(self):
        result = _call(
            "quorum_assembleari",
            tipo_societa="spa",
            tipo_delibera="straordinaria",
            capitale_totale=1_000_000,
            capitale_presente=800_000,
            voti_favorevoli=400_000,  # 50% dei presenti < 66.67%
        )
        assert result["raggiunto_deliberativo"] is False

    def test_srl_ordinaria_maggioranza_capitale(self):
        result = _call(
            "quorum_assembleari",
            tipo_societa="srl",
            tipo_delibera="ordinaria",
            capitale_totale=100_000,
            capitale_presente=0,
            voti_favorevoli=60_000,  # 60% del totale > 50%
        )
        assert result["tipo_societa"] == "srl"
        # SRL: no quorum costitutivo
        assert result["raggiunto_costitutivo"] is True
        assert result["raggiunto_deliberativo"] is True

    def test_srl_scioglimento_due_terzi(self):
        result = _call(
            "quorum_assembleari",
            tipo_societa="srl",
            tipo_delibera="scioglimento",
            capitale_totale=100_000,
            capitale_presente=0,
            voti_favorevoli=70_000,  # 70% >= 66.67%
        )
        assert result["raggiunto_deliberativo"] is True

    def test_srl_scioglimento_sotto_due_terzi(self):
        result = _call(
            "quorum_assembleari",
            tipo_societa="srl",
            tipo_delibera="scioglimento",
            capitale_totale=100_000,
            capitale_presente=0,
            voti_favorevoli=50_000,  # 50% < 66.67%
        )
        assert result["raggiunto_deliberativo"] is False

    def test_cooperativa_voto_per_teste(self):
        result = _call(
            "quorum_assembleari",
            tipo_societa="cooperativa",
            tipo_delibera="ordinaria",
            capitale_totale=200,   # numero soci
            capitale_presente=120,  # soci presenti (60% > 50%)
            voti_favorevoli=80,    # 80/120 = 66.7% dei presenti > 50%
        )
        assert result["tipo_societa"] == "cooperativa"
        assert result["raggiunto_costitutivo"] is True
        assert result["raggiunto_deliberativo"] is True
        assert "2538" in result["riferimento_normativo"]

    def test_senza_valori_presenti_delibera_non_valida(self):
        # Without capital_presente/voti_favorevoli, all quorum checks return False
        result = _call(
            "quorum_assembleari",
            tipo_societa="spa",
            tipo_delibera="ordinaria",
            capitale_totale=1_000_000,
        )
        assert result["raggiunto_costitutivo"] is False
        assert result["delibera_valida"] is False
        assert result["percentuale_presente"] == "n/a"

    def test_tipo_societa_invalido(self):
        with pytest.raises(ValueError):
            _call(
                "quorum_assembleari",
                tipo_societa="sapa",
                tipo_delibera="ordinaria",
                capitale_totale=100_000,
            )

    def test_tipo_delibera_invalido(self):
        with pytest.raises(ValueError):
            _call(
                "quorum_assembleari",
                tipo_societa="srl",
                tipo_delibera="speciale",
                capitale_totale=100_000,
            )

    def test_capitale_presente_supera_totale(self):
        with pytest.raises(ValueError):
            _call(
                "quorum_assembleari",
                tipo_societa="spa",
                tipo_delibera="ordinaria",
                capitale_totale=100_000,
                capitale_presente=200_000,
            )

    def test_voti_favorevoli_superano_presenti(self):
        with pytest.raises(ValueError):
            _call(
                "quorum_assembleari",
                tipo_societa="spa",
                tipo_delibera="ordinaria",
                capitale_totale=100_000,
                capitale_presente=60_000,
                voti_favorevoli=70_000,
            )

    def test_spa_scioglimento_deliberativo_su_totale(self):
        # Scioglimento SPA: deliberativo sulla maggioranza del capitale totale
        result = _call(
            "quorum_assembleari",
            tipo_societa="spa",
            tipo_delibera="scioglimento",
            capitale_totale=1_000_000,
            capitale_presente=700_000,
            voti_favorevoli=550_000,  # 55% del totale > 50%
        )
        assert result["raggiunto_deliberativo"] is True


# ---------------------------------------------------------------------------
# soglie_organo_controllo_srl
# ---------------------------------------------------------------------------

class TestSoglieOrganoControlloSrl:
    def test_sotto_tutte_le_soglie(self):
        result = _call(
            "soglie_organo_controllo_srl",
            ricavi=1_000_000,
            attivo=2_000_000,
            dipendenti=5,
        )
        assert result["obbligo_nomina"] is False
        assert result["limiti_superati"] == []
        assert result["numero_limiti_superati"] == 0

    def test_supera_soglia_ricavi(self):
        result = _call(
            "soglie_organo_controllo_srl",
            ricavi=5_000_000,
            attivo=2_000_000,
            dipendenti=10,
        )
        assert result["obbligo_nomina"] is True
        assert "ricavi" in result["limiti_superati"]
        assert result["numero_limiti_superati"] == 1

    def test_supera_soglia_attivo(self):
        result = _call(
            "soglie_organo_controllo_srl",
            ricavi=1_000_000,
            attivo=5_000_000,
            dipendenti=10,
        )
        assert result["obbligo_nomina"] is True
        assert "attivo" in result["limiti_superati"]

    def test_supera_soglia_dipendenti(self):
        result = _call(
            "soglie_organo_controllo_srl",
            ricavi=1_000_000,
            attivo=2_000_000,
            dipendenti=25,
        )
        assert result["obbligo_nomina"] is True
        assert "dipendenti" in result["limiti_superati"]

    def test_supera_tutti_e_tre_i_limiti(self):
        result = _call(
            "soglie_organo_controllo_srl",
            ricavi=6_000_000,
            attivo=6_000_000,
            dipendenti=30,
        )
        assert result["obbligo_nomina"] is True
        assert set(result["limiti_superati"]) == {"ricavi", "attivo", "dipendenti"}
        assert result["numero_limiti_superati"] == 3

    def test_esattamente_sulla_soglia_non_supera(self):
        # > non >=: 4.000.000 esatti NON supera
        result = _call(
            "soglie_organo_controllo_srl",
            ricavi=4_000_000,
            attivo=4_000_000,
            dipendenti=20,
        )
        assert result["obbligo_nomina"] is False
        assert result["limiti_superati"] == []

    def test_valore_negativo_solleva_errore(self):
        with pytest.raises(ValueError):
            _call(
                "soglie_organo_controllo_srl",
                ricavi=-1,
                attivo=1_000_000,
                dipendenti=10,
            )

    def test_soglie_nel_result(self):
        result = _call(
            "soglie_organo_controllo_srl",
            ricavi=0,
            attivo=0,
            dipendenti=0,
        )
        assert result["soglie"]["ricavi_euro"] == 4_000_000.0
        assert result["soglie"]["attivo_euro"] == 4_000_000.0
        assert result["soglie"]["dipendenti"] == 20
        assert "2477" in result["riferimento_normativo"]


# ---------------------------------------------------------------------------
# scadenze_societarie
# ---------------------------------------------------------------------------

class TestScadenzeSocietarie:
    def test_termine_ordinario_120_giorni(self):
        result = _call(
            "scadenze_societarie",
            data_chiusura_esercizio="2024-12-31",
            bilancio_differito=False,
        )
        s = result["scadenze"]
        assert s["termine_approvazione_bilancio"]["giorni_dalla_chiusura"] == 120
        assert s["termine_approvazione_bilancio"]["data"] == "2025-04-30"
        assert "2364" in result["riferimento_normativo"]

    def test_termine_differito_180_giorni(self):
        result = _call(
            "scadenze_societarie",
            data_chiusura_esercizio="2024-12-31",
            bilancio_differito=True,
        )
        s = result["scadenze"]
        assert s["termine_approvazione_bilancio"]["giorni_dalla_chiusura"] == 180
        assert s["termine_approvazione_bilancio"]["data"] == "2025-06-29"

    def test_deposito_cciaa_30_giorni_dopo_approvazione(self):
        result = _call(
            "scadenze_societarie",
            data_chiusura_esercizio="2024-12-31",
        )
        s = result["scadenze"]
        # approvazione 2025-04-30, deposito +30 = 2025-05-30
        assert s["deposito_cciaa"]["data"] == "2025-05-30"
        assert s["deposito_cciaa"]["giorni_dall_approvazione"] == 30

    def test_convocazione_spa_15_giorni_prima(self):
        result = _call(
            "scadenze_societarie",
            data_chiusura_esercizio="2024-12-31",
        )
        s = result["scadenze"]
        # approvazione 2025-04-30, convocazione SPA -15 = 2025-04-15
        assert s["convocazione_assemblea_spa"]["data"] == "2025-04-15"

    def test_convocazione_srl_8_giorni_prima(self):
        result = _call(
            "scadenze_societarie",
            data_chiusura_esercizio="2024-12-31",
        )
        s = result["scadenze"]
        # approvazione 2025-04-30, convocazione SRL -8 = 2025-04-22
        assert s["convocazione_assemblea_srl"]["data"] == "2025-04-22"

    def test_result_contiene_tutte_le_chiavi(self):
        result = _call(
            "scadenze_societarie",
            data_chiusura_esercizio="2023-06-30",
        )
        expected_keys = {
            "termine_approvazione_bilancio",
            "convocazione_assemblea_spa",
            "convocazione_assemblea_srl",
            "deposito_bilancio_sede_sociale",
            "deposito_cciaa",
            "iscrizione_verbale_assemblea",
        }
        assert expected_keys.issubset(result["scadenze"].keys())


# ---------------------------------------------------------------------------
# costi_costituzione
# ---------------------------------------------------------------------------

class TestCostiCostituzione:
    def test_srl_ha_capitale_minimo_1_euro(self):
        result = _call("costi_costituzione", tipo_societa="srl")
        assert result["tipo_societa"] == "srl"
        assert result["capitale_minimo"] == 1.0
        assert result["totale_stimato_min"] > 0
        assert result["totale_stimato_max"] >= result["totale_stimato_min"]
        assert "2463" in result["riferimento_normativo"]

    def test_srls_notaio_gratuito(self):
        result = _call("costi_costituzione", tipo_societa="srls")
        notaio = next(v for v in result["voci_costo"] if v["voce"] == "Onorario notarile")
        assert notaio["min"] == 0.0
        assert notaio["max"] == 0.0

    def test_spa_capitale_minimo_50000(self):
        result = _call("costi_costituzione", tipo_societa="spa")
        assert result["capitale_minimo"] == 50_000.0
        assert result["totale_stimato_min"] >= 3000

    def test_sas_nessun_atto_obbligo_notaio_indicativo(self):
        result = _call("costi_costituzione", tipo_societa="sas")
        assert result["capitale_minimo"] == 0.0

    def test_snc_costi_inferiori_a_srl(self):
        srl = _call("costi_costituzione", tipo_societa="srl")
        snc = _call("costi_costituzione", tipo_societa="snc")
        assert snc["totale_stimato_max"] < srl["totale_stimato_min"]

    def test_ditta_individuale_senza_notaio(self):
        result = _call("costi_costituzione", tipo_societa="ditta_individuale")
        assert result["capitale_minimo"] == 0.0
        voci_nomi = [v["voce"] for v in result["voci_costo"]]
        assert not any("notaio" in v.lower() for v in voci_nomi)
        assert result["totale_stimato_max"] < 200

    def test_tipo_invalido_solleva_errore(self):
        with pytest.raises(ValueError):
            _call("costi_costituzione", tipo_societa="ltd")

    def test_case_insensitive(self):
        result = _call("costi_costituzione", tipo_societa="SRL")
        assert result["tipo_societa"] == "srl"

    def test_avvertenza_indicativo_presente(self):
        result = _call("costi_costituzione", tipo_societa="srl")
        assert "INDICATIVO" in result["avvertenza"]

    def test_totale_coerente_con_voci(self):
        result = _call("costi_costituzione", tipo_societa="spa")
        somma_min = sum(v["min"] for v in result["voci_costo"])
        somma_max = sum(v["max"] for v in result["voci_costo"])
        assert result["totale_stimato_min"] == round(somma_min, 2)
        assert result["totale_stimato_max"] == round(somma_max, 2)

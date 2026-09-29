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
            voti_favorevoli=600_000,  # 60% of the capital > 50% (art. 2368 co. 2, first period, closed s.p.a.)
        )
        assert result["raggiunto_deliberativo"] is True

    def test_spa_straordinaria_deliberativo_sotto_soglia(self):
        result = _call(
            "quorum_assembleari",
            tipo_societa="spa",
            tipo_delibera="straordinaria",
            capitale_totale=1_000_000,
            capitale_presente=800_000,
            voti_favorevoli=400_000,  # 40% of the capital, not more than half (art. 2368 co. 2)
        )
        assert result["raggiunto_deliberativo"] is False

    def test_srl_ordinaria_maggioranza_assoluta_dei_presenti(self):
        # Art. 2479-bis co. 3 c.c.: assembly constituted with at least half of the capital,
        # decides by absolute majority of those present (40k of 60k present = 66.7%).
        result = _call(
            "quorum_assembleari",
            tipo_societa="srl",
            tipo_delibera="ordinaria",
            capitale_totale=100_000,
            capitale_presente=60_000,
            voti_favorevoli=40_000,
        )
        assert result["tipo_societa"] == "srl"
        assert result["raggiunto_costitutivo"] is True
        assert result["raggiunto_deliberativo"] is True
        assert result["delibera_valida"] is True

    def test_srl_ordinaria_senza_quorum_costitutivo(self):
        # Art. 2479-bis co. 3 c.c.: 40% of the capital present, the assembly is not constituted.
        result = _call(
            "quorum_assembleari",
            tipo_societa="srl",
            tipo_delibera="ordinaria",
            capitale_totale=100_000,
            capitale_presente=40_000,
            voti_favorevoli=40_000,
        )
        assert result["raggiunto_costitutivo"] is False
        assert result["delibera_valida"] is False

    def test_srl_modifica_almeno_meta_del_capitale(self):
        # Art. 2479-bis co. 3 with art. 2479 co. 2 n. 4: "almeno la metà" (50,000 of 100,000 is enough).
        result = _call(
            "quorum_assembleari",
            tipo_societa="srl",
            tipo_delibera="modifica_statuto",
            capitale_totale=100_000,
            capitale_presente=100_000,
            voti_favorevoli=50_000,
        )
        assert result["delibera_valida"] is True
        below = _call(
            "quorum_assembleari",
            tipo_societa="srl",
            tipo_delibera="modifica_statuto",
            capitale_totale=100_000,
            capitale_presente=100_000,
            voti_favorevoli=49_999,
        )
        assert below["raggiunto_deliberativo"] is False

    def test_srl_scioglimento_senza_due_terzi(self):
        # Art. 2484 fixes no majority; art. 2487 co. 1 refers to the majority of the amendments
        # of the atto costitutivo (at least half of the capital): 60% is enough, no 2/3 rule.
        result = _call(
            "quorum_assembleari",
            tipo_societa="srl",
            tipo_delibera="scioglimento",
            capitale_totale=100_000,
            capitale_presente=100_000,
            voti_favorevoli=60_000,
        )
        assert result["raggiunto_deliberativo"] is True
        assert "2/3" not in result["quorum_deliberativo"]
        assert "2487" in result["riferimento_normativo"]
        under = _call(
            "quorum_assembleari",
            tipo_societa="srl",
            tipo_delibera="scioglimento",
            capitale_totale=100_000,
            capitale_presente=100_000,
            voti_favorevoli=40_000,
        )
        assert under["raggiunto_deliberativo"] is False

    def test_spa_chiusa_straordinaria_piu_della_meta_del_capitale(self):
        # Art. 2368 co. 2, first period: closed s.p.a., first convocation, more than half of the
        # capital sociale in favour. 45k of 100k: rejected; 55k of 100k: approved.
        rejected = _call(
            "quorum_assembleari", tipo_societa="spa", tipo_delibera="straordinaria",
            capitale_totale=100_000, capitale_presente=60_000, voti_favorevoli=45_000,
        )
        assert rejected["delibera_valida"] is False
        approved = _call(
            "quorum_assembleari", tipo_societa="spa", tipo_delibera="straordinaria",
            capitale_totale=100_000, capitale_presente=90_000, voti_favorevoli=55_000,
        )
        assert approved["delibera_valida"] is True

    def test_spa_mercato_capitale_rischio_due_terzi_del_rappresentato(self):
        # Art. 2368 co. 2, second period: 2/3 of the represented capital only for market companies
        # (constituted with at least half of the capital). 60k present, 45k in favour = 75%.
        market = _call(
            "quorum_assembleari", tipo_societa="spa", tipo_delibera="straordinaria",
            capitale_totale=100_000, capitale_presente=60_000, voti_favorevoli=45_000,
            ricorso_mercato_capitale_rischio=True,
        )
        assert market["delibera_valida"] is True
        # 90k present, 55k in favour = 61.1% < 2/3: rejected for a market company
        market_ko = _call(
            "quorum_assembleari", tipo_societa="spa", tipo_delibera="straordinaria",
            capitale_totale=100_000, capitale_presente=90_000, voti_favorevoli=55_000,
            ricorso_mercato_capitale_rischio=True,
        )
        assert market_ko["delibera_valida"] is False

    def test_spa_scioglimento_seconda_convocazione_oltre_un_terzo(self):
        # Art. 2369 co. 3 and 5: second convocation, constituted with over one third of the capital,
        # 2/3 of the represented capital and more than one third of the capital sociale in favour.
        # 40k present and in favour: approved (40% > 1/3), not half of the capital.
        r = _call(
            "quorum_assembleari", tipo_societa="spa", tipo_delibera="scioglimento",
            capitale_totale=100_000, capitale_presente=40_000, voti_favorevoli=40_000,
            convocazione="seconda",
        )
        assert r["delibera_valida"] is True
        assert "terzo" in r["quorum_costitutivo_seconda_conv"].lower()
        # 33,333 of 100,000 is not "più di un terzo" (needs 33,334): not constituted
        edge = _call(
            "quorum_assembleari", tipo_societa="spa", tipo_delibera="scioglimento",
            capitale_totale=100_000, capitale_presente=33_333, voti_favorevoli=33_333,
            convocazione="seconda",
        )
        assert edge["raggiunto_costitutivo"] is False
        # first convocation: 40% is not more than half, rejected
        first = _call(
            "quorum_assembleari", tipo_societa="spa", tipo_delibera="scioglimento",
            capitale_totale=100_000, capitale_presente=40_000, voti_favorevoli=40_000,
        )
        assert first["delibera_valida"] is False

    def test_spa_unica_convocazione_solo_mercato(self):
        # Art. 2369 co. 1 and 7: single convocation only for market companies; extraordinary
        # assembly constituted with one fifth of the capital, 2/3 of the represented capital.
        r = _call(
            "quorum_assembleari", tipo_societa="spa", tipo_delibera="straordinaria",
            capitale_totale=100_000, capitale_presente=20_000, voti_favorevoli=14_000,
            convocazione="unica", ricorso_mercato_capitale_rischio=True,
        )
        assert r["raggiunto_costitutivo"] is True
        assert r["delibera_valida"] is True
        with pytest.raises(ValueError):
            _call(
                "quorum_assembleari", tipo_societa="spa", tipo_delibera="straordinaria",
                capitale_totale=100_000, convocazione="unica",
            )

    def test_convocazione_invalida(self):
        with pytest.raises(ValueError):
            _call(
                "quorum_assembleari", tipo_societa="spa", tipo_delibera="ordinaria",
                capitale_totale=100_000, convocazione="terza",
            )

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
        # Art. 2538 co. 5 c.c.: the quorums are set by the atto costitutivo, not by a legal "metà più uno"
        assert "atto costitutivo" in result["quorum_costitutivo_prima_conv"].lower()
        assert "più uno" not in result["quorum_costitutivo_prima_conv"].lower()

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
        # Art. 2477 co. 2 lett. c): one esercizio only, the obligation is not ascertainable
        assert result["obbligo_nomina"] is None
        assert result["limite_superato_ultimo_esercizio"] is True
        assert "ricavi" in result["limiti_superati"]
        assert result["numero_limiti_superati"] == 1

    def test_supera_soglia_attivo(self):
        result = _call(
            "soglie_organo_controllo_srl",
            ricavi=1_000_000,
            attivo=5_000_000,
            dipendenti=10,
        )
        assert result["obbligo_nomina"] is None  # art. 2477 co. 2 lett. c): needs two esercizi
        assert "attivo" in result["limiti_superati"]

    def test_supera_soglia_dipendenti(self):
        result = _call(
            "soglie_organo_controllo_srl",
            ricavi=1_000_000,
            attivo=2_000_000,
            dipendenti=25,
        )
        assert result["obbligo_nomina"] is None  # art. 2477 co. 2 lett. c): needs two esercizi
        assert "dipendenti" in result["limiti_superati"]

    def test_supera_tutti_e_tre_i_limiti(self):
        result = _call(
            "soglie_organo_controllo_srl",
            ricavi=6_000_000,
            attivo=6_000_000,
            dipendenti=30,
        )
        assert result["obbligo_nomina"] is None  # art. 2477 co. 2 lett. c): needs two esercizi
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

    def test_due_esercizi_consecutivi_stesso_limite(self):
        # Art. 2477 co. 2 lett. c): the same limit (ricavi 4,000,000.01 and 5,000,000) over two
        # consecutive esercizi makes the nomina compulsory.
        result = _call(
            "soglie_organo_controllo_srl",
            ricavi=4_000_000.01, attivo=1_000_000, dipendenti=5,
            ricavi_precedente=5_000_000, attivo_precedente=1_000_000, dipendenti_precedente=5,
        )
        assert result["obbligo_nomina"] is True

    def test_superamento_solo_in_un_esercizio_non_fa_sorgere_l_obbligo(self):
        # Art. 2477 co. 2 lett. c): limit exceeded in the last esercizio only, not in the previous one.
        result = _call(
            "soglie_organo_controllo_srl",
            ricavi=5_000_000, attivo=1_000_000, dipendenti=5,
            ricavi_precedente=3_000_000, attivo_precedente=1_000_000, dipendenti_precedente=5,
        )
        assert result["obbligo_nomina"] is False

    def test_lettere_a_e_b_obbligano_a_prescindere_dai_limiti(self):
        # Art. 2477 co. 2 lett. a) (bilancio consolidato) and b) (controls a company subject to audit)
        for kw in ({"bilancio_consolidato": True}, {"controlla_societa_revisione": True}):
            result = _call("soglie_organo_controllo_srl", ricavi=100_000, attivo=100_000, dipendenti=1, **kw)
            assert result["obbligo_nomina"] is True
            assert result["obbligo_lettere_a_b"] is True

    def test_esercizio_precedente_parziale_solleva_errore(self):
        with pytest.raises(ValueError):
            _call("soglie_organo_controllo_srl", ricavi=1, attivo=1, dipendenti=1, ricavi_precedente=1)

    def test_riferimento_normativo_cita_dl_32_2019(self):
        # The 4 / 4 / 20 limits come from art. 2-bis co. 2 D.L. 32/2019 (art. 379 D.Lgs. 14/2019: 2 / 2 / 10)
        result = _call("soglie_organo_controllo_srl", ricavi=0, attivo=0, dipendenti=0)
        assert "32/2019" in result["riferimento_normativo"]
        assert "co. 3" in result["note"]

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

    def test_verbale_depositato_con_il_bilancio_art_2435_non_2436(self):
        # Art. 2435 co. 1 c.c.: the verbale of approval is filed with the bilancio within 30 days of
        # the approval (same date as the deposit); art. 2436 concerns amendments of the statute.
        result = _call("scadenze_societarie", data_chiusura_esercizio="2025-12-31")
        s = result["scadenze"]
        assert s["iscrizione_verbale_assemblea"]["data"] == s["deposito_cciaa"]["data"] == "2026-05-30"
        nota = s["iscrizione_verbale_assemblea"]["nota"]
        assert "2435" in nota and "2478-bis" in nota
        assert "2436" not in result["riferimento_normativo"]

    def test_comunicazione_bilancio_organo_controllo_30_giorni_prima(self):
        # Art. 2429 co. 1 c.c.: bilancio communicated to sindaci and revisore at least 30 days before
        # the assembly (assembly on 2026-04-30 -> 2026-03-31).
        result = _call("scadenze_societarie", data_chiusura_esercizio="2025-12-31")
        assert result["scadenze"]["comunicazione_bilancio_organo_controllo"]["data"] == "2026-03-31"

    def test_segnala_scadenza_di_sabato(self):
        # 2026-05-30 is a Saturday: the deposit term is flagged, not shifted (art. 2435 co. 1 c.c.)
        result = _call("scadenze_societarie", data_chiusura_esercizio="2025-12-31")
        assert result["scadenze"]["deposito_cciaa"]["giorno_settimana"] == "sabato"
        assert any("deposito_cciaa" in a and "sabato" in a for a in result["avvertenze"])


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

    def test_srls_totale_629_87_con_tcg(self):
        # Art. 3 co. 3 DL 1/2012 esenta solo bollo, diritti di segreteria e onorari:
        # la TCG (art. 23 Tariffa DPR 641/1972, 309,87) resta dovuta.
        # Verificato a mano: 200 + 120 + 309,87 = 629,87.
        result = _call("costi_costituzione", tipo_societa="srls")
        assert result["totale_stimato_min"] == 629.87
        assert result["totale_stimato_max"] == 629.87

    def test_sas_snc_con_diritti_segreteria_90(self):
        # D.M. 17/7/2012 Tab. A: 90 euro. sas 1000+200+156+120+90 = 1566; snc 800+...=1366.
        sas = _call("costi_costituzione", tipo_societa="sas")
        snc = _call("costi_costituzione", tipo_societa="snc")
        assert sas["totale_stimato_min"] == 1566.0
        assert sas["totale_stimato_max"] == 2066.0
        assert snc["totale_stimato_min"] == 1366.0
        assert snc["totale_stimato_max"] == 1766.0
        assert "55/2014" not in _call("costi_costituzione", tipo_societa="srl")["riferimento_normativo"]

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

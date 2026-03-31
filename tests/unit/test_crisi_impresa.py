import importlib

import pytest


def _call(fn_name: str, **kwargs):
    mod = importlib.import_module("src.tools.crisi_impresa")
    fn = getattr(mod, fn_name)
    actual = fn.fn if hasattr(fn, "fn") else fn
    return actual(**kwargs)


# ---------------------------------------------------------------------------
# test_crisi_impresa
# ---------------------------------------------------------------------------

class TestCrisiImpresa:
    def test_nessun_indicatore_dscr_alto(self):
        result = _call("test_crisi_impresa", dscr=1.5)
        assert result["alert"] is False
        assert result["severita"] == "nessuno"
        assert result["numero_indicatori"] == 0
        assert result["indicatori_attivati"] == []

    def test_dscr_basso_alert(self):
        result = _call("test_crisi_impresa", dscr=0.5)
        assert result["alert"] is True
        assert result["severita"] == "moderato"
        assert result["numero_indicatori"] == 1
        assert any("DSCR" in s for s in result["indicatori_attivati"])

    def test_tre_indicatori_critico(self):
        result = _call(
            "test_crisi_impresa",
            dscr=0.8,
            giorni_ritardo_inps=120,
            giorni_ritardo_ade=100,
        )
        assert result["alert"] is True
        assert result["severita"] == "critico"
        assert result["numero_indicatori"] == 3

    def test_due_indicatori_significativo(self):
        result = _call(
            "test_crisi_impresa",
            dscr=0.9,
            esposizioni_scadute_pct=10.0,
        )
        assert result["severita"] == "significativo"
        assert result["numero_indicatori"] == 2

    def test_tutti_cinque_indicatori(self):
        result = _call(
            "test_crisi_impresa",
            dscr=0.5,
            giorni_ritardo_inps=100,
            giorni_ritardo_ade=95,
            esposizioni_scadute_pct=8.0,
            debiti_vs_attivo_pct=85.0,
        )
        assert result["numero_indicatori"] == 5
        assert result["severita"] == "critico"

    def test_soglia_dscr_esattamente_1(self):
        result = _call("test_crisi_impresa", dscr=1.0)
        assert result["alert"] is False

    def test_giorni_ritardo_inps_sotto_soglia(self):
        result = _call("test_crisi_impresa", dscr=1.2, giorni_ritardo_inps=90)
        assert result["alert"] is False

    def test_giorni_ritardo_inps_sopra_soglia(self):
        result = _call("test_crisi_impresa", dscr=1.2, giorni_ritardo_inps=91)
        assert result["alert"] is True
        assert any("INPS" in s for s in result["indicatori_attivati"])

    def test_esposizioni_soglia_5(self):
        result_sotto = _call("test_crisi_impresa", dscr=1.2, esposizioni_scadute_pct=5.0)
        result_sopra = _call("test_crisi_impresa", dscr=1.2, esposizioni_scadute_pct=5.1)
        assert result_sotto["alert"] is False
        assert result_sopra["alert"] is True

    def test_dscr_negativo_errore(self):
        with pytest.raises(ValueError):
            _call("test_crisi_impresa", dscr=-0.1)

    def test_riferimento_normativo(self):
        result = _call("test_crisi_impresa", dscr=1.0)
        assert "Art. 3" in result["riferimento_normativo"]
        assert "CCII" in result["riferimento_normativo"]

    def test_raccomandazione_presente(self):
        result = _call("test_crisi_impresa", dscr=0.5)
        assert isinstance(result["raccomandazione"], str)
        assert len(result["raccomandazione"]) > 0


# ---------------------------------------------------------------------------
# composizione_negoziata
# ---------------------------------------------------------------------------

class TestComposizioneNegoziata:
    def test_commerciale_sempre_ammissibile(self):
        result = _call(
            "composizione_negoziata",
            fatturato=500_000.0,
            attivo=800_000.0,
            dipendenti=10,
            debito_totale=300_000.0,
            tipo_impresa="commerciale",
        )
        assert result["ammissibile"] is True
        assert "commerciale" in result["tipo_impresa"]

    def test_agricola_ammissibile(self):
        result = _call(
            "composizione_negoziata",
            fatturato=150_000.0,
            attivo=400_000.0,
            dipendenti=3,
            debito_totale=100_000.0,
            tipo_impresa="agricola",
        )
        assert result["ammissibile"] is True
        assert any("25-quater" in r for r in result["requisiti_soddisfatti"])

    def test_sotto_soglia_attivo_ammissibile(self):
        result = _call(
            "composizione_negoziata",
            fatturato=250_000.0,
            attivo=250_000.0,
            dipendenti=2,
            debito_totale=600_000.0,
            tipo_impresa="sotto_soglia",
        )
        assert result["ammissibile"] is True

    def test_sotto_soglia_ricavi_ammissibile(self):
        result = _call(
            "composizione_negoziata",
            fatturato=180_000.0,
            attivo=400_000.0,
            dipendenti=2,
            debito_totale=600_000.0,
            tipo_impresa="sotto_soglia",
        )
        assert result["ammissibile"] is True

    def test_sotto_soglia_nessuna_soglia_non_ammissibile(self):
        result = _call(
            "composizione_negoziata",
            fatturato=400_000.0,
            attivo=500_000.0,
            dipendenti=5,
            debito_totale=600_000.0,
            tipo_impresa="sotto_soglia",
        )
        assert result["ammissibile"] is False

    def test_indicatori_debito_fatturato(self):
        result = _call(
            "composizione_negoziata",
            fatturato=500_000.0,
            attivo=1_000_000.0,
            dipendenti=10,
            debito_totale=800_000.0,
        )
        assert result["indicatori"]["rapporto_debito_fatturato"] == pytest.approx(1.6, abs=0.01)

    def test_risanamento_ragionevole_debito_sotto_2x_fatturato(self):
        result = _call(
            "composizione_negoziata",
            fatturato=500_000.0,
            attivo=800_000.0,
            dipendenti=10,
            debito_totale=900_000.0,
        )
        assert result["indicatori"]["risanamento_ragionevole"] is True

    def test_risanamento_non_ragionevole_debito_sopra_2x_fatturato(self):
        result = _call(
            "composizione_negoziata",
            fatturato=300_000.0,
            attivo=500_000.0,
            dipendenti=5,
            debito_totale=700_000.0,
        )
        assert result["indicatori"]["risanamento_ragionevole"] is False

    def test_misure_protettive_presenti(self):
        result = _call(
            "composizione_negoziata",
            fatturato=500_000.0,
            attivo=800_000.0,
            dipendenti=10,
            debito_totale=300_000.0,
        )
        assert len(result["misure_protettive"]) >= 3

    def test_tipo_non_valido_errore(self):
        with pytest.raises(ValueError):
            _call(
                "composizione_negoziata",
                fatturato=500_000.0,
                attivo=800_000.0,
                dipendenti=5,
                debito_totale=300_000.0,
                tipo_impresa="invalido",
            )

    def test_valore_negativo_errore(self):
        with pytest.raises(ValueError):
            _call(
                "composizione_negoziata",
                fatturato=-100.0,
                attivo=800_000.0,
                dipendenti=5,
                debito_totale=300_000.0,
            )

    def test_riferimento_normativo(self):
        result = _call(
            "composizione_negoziata",
            fatturato=500_000.0,
            attivo=800_000.0,
            dipendenti=10,
            debito_totale=300_000.0,
        )
        assert "art. 12" in result["riferimento_normativo"].lower() or "Artt. 12" in result["riferimento_normativo"]


# ---------------------------------------------------------------------------
# concordato_preventivo
# ---------------------------------------------------------------------------

class TestConcordatoPreventivo:
    def test_liquidatorio_15pct_non_ammissibile(self):
        result = _call(
            "concordato_preventivo",
            creditori_privilegiati=200_000.0,
            creditori_chirografari=500_000.0,
            proposta_pct_chirografari=15.0,
            tipo="liquidatorio",
        )
        assert result["ammissibile"] is False
        assert result["soglia_minima_pct"] == 20.0

    def test_liquidatorio_25pct_ammissibile(self):
        result = _call(
            "concordato_preventivo",
            creditori_privilegiati=200_000.0,
            creditori_chirografari=500_000.0,
            proposta_pct_chirografari=25.0,
            tipo="liquidatorio",
        )
        assert result["ammissibile"] is True
        assert result["proposta_chirografari_euro"] == pytest.approx(125_000.0)

    def test_liquidatorio_esattamente_20pct_ammissibile(self):
        result = _call(
            "concordato_preventivo",
            creditori_privilegiati=100_000.0,
            creditori_chirografari=300_000.0,
            proposta_pct_chirografari=20.0,
            tipo="liquidatorio",
        )
        assert result["ammissibile"] is True

    def test_continuita_no_soglia_minima(self):
        result = _call(
            "concordato_preventivo",
            creditori_privilegiati=100_000.0,
            creditori_chirografari=400_000.0,
            proposta_pct_chirografari=5.0,
            tipo="continuita",
        )
        assert result["ammissibile"] is True
        assert result["soglia_minima_pct"] == 0.0

    def test_calcolo_totale_debito(self):
        result = _call(
            "concordato_preventivo",
            creditori_privilegiati=200_000.0,
            creditori_chirografari=800_000.0,
            proposta_pct_chirografari=30.0,
        )
        assert result["totale_debito"] == pytest.approx(1_000_000.0)

    def test_calcolo_proposta_totale(self):
        result = _call(
            "concordato_preventivo",
            creditori_privilegiati=100_000.0,
            creditori_chirografari=200_000.0,
            proposta_pct_chirografari=50.0,
            proposta_pct_privilegiati=100.0,
        )
        assert result["proposta_privilegiati_euro"] == pytest.approx(100_000.0)
        assert result["proposta_chirografari_euro"] == pytest.approx(100_000.0)
        assert result["proposta_totale"] == pytest.approx(200_000.0)

    def test_privilegiati_parziali_nota(self):
        result = _call(
            "concordato_preventivo",
            creditori_privilegiati=200_000.0,
            creditori_chirografari=500_000.0,
            proposta_pct_chirografari=25.0,
            proposta_pct_privilegiati=80.0,
        )
        assert "degradazione" in result["nota_privilegiati"].lower()

    def test_percentuale_fuori_range_errore(self):
        with pytest.raises(ValueError):
            _call(
                "concordato_preventivo",
                creditori_privilegiati=100_000.0,
                creditori_chirografari=200_000.0,
                proposta_pct_chirografari=110.0,
            )

    def test_tipo_non_valido_errore(self):
        with pytest.raises(ValueError):
            _call(
                "concordato_preventivo",
                creditori_privilegiati=100_000.0,
                creditori_chirografari=200_000.0,
                proposta_pct_chirografari=25.0,
                tipo="invalido",
            )

    def test_voto_requisito_presente(self):
        result = _call(
            "concordato_preventivo",
            creditori_privilegiati=100_000.0,
            creditori_chirografari=200_000.0,
            proposta_pct_chirografari=25.0,
        )
        assert isinstance(result["voto_requisito"], str)
        assert len(result["voto_requisito"]) > 0

    def test_riferimento_normativo(self):
        result = _call(
            "concordato_preventivo",
            creditori_privilegiati=100_000.0,
            creditori_chirografari=200_000.0,
            proposta_pct_chirografari=25.0,
        )
        assert "84" in result["riferimento_normativo"]
        assert "CCII" in result["riferimento_normativo"]


# ---------------------------------------------------------------------------
# compenso_occ
# ---------------------------------------------------------------------------

class TestCompensoOcc:
    def test_passivo_piccolo_minimo_ristrutturazione(self):
        result = _call("compenso_occ", passivo=10_000.0, tipo="ristrutturazione")
        # 10.000 * 5% = 500 < minimo 1.500
        assert result["compenso"] == 1_500.0
        assert result["minimo_applicato"] is True

    def test_passivo_piccolo_minimo_liquidazione(self):
        result = _call("compenso_occ", passivo=20_000.0, tipo="liquidazione")
        # 20.000 * 7% = 1.400 < minimo 2.000
        assert result["compenso"] == 2_000.0
        assert result["minimo_applicato"] is True

    def test_passivo_50000_ristrutturazione(self):
        result = _call("compenso_occ", passivo=50_000.0, tipo="ristrutturazione")
        # 50.000 * 5% = 2.500
        assert result["compenso"] == pytest.approx(2_500.0)
        assert result["minimo_applicato"] is False

    def test_passivo_100000_ristrutturazione(self):
        result = _call("compenso_occ", passivo=100_000.0, tipo="ristrutturazione")
        # 100.000 * 5% = 5.000
        assert result["compenso"] == pytest.approx(5_000.0)
        assert result["minimo_applicato"] is False

    def test_passivo_300000_progressivo_ristrutturazione(self):
        result = _call("compenso_occ", passivo=300_000.0, tipo="ristrutturazione")
        # 100.000 * 5% = 5.000
        # 200.000 * 3% = 6.000
        # totale = 11.000
        assert result["compenso"] == pytest.approx(11_000.0)
        assert len(result["dettaglio_fasce"]) == 2

    def test_passivo_600000_tre_fasce_ristrutturazione(self):
        result = _call("compenso_occ", passivo=600_000.0, tipo="ristrutturazione")
        # 100.000 * 5% = 5.000
        # 400.000 * 3% = 12.000
        # 100.000 * 1% = 1.000
        # totale = 18.000
        assert result["compenso"] == pytest.approx(18_000.0)
        assert len(result["dettaglio_fasce"]) == 3

    def test_passivo_300000_liquidazione(self):
        result = _call("compenso_occ", passivo=300_000.0, tipo="liquidazione")
        # 100.000 * 7% = 7.000
        # 200.000 * 4% = 8.000
        # totale = 15.000
        assert result["compenso"] == pytest.approx(15_000.0)

    def test_passivo_zero_minimo(self):
        result = _call("compenso_occ", passivo=0.0, tipo="ristrutturazione")
        assert result["compenso"] == 1_500.0
        assert result["minimo_applicato"] is True

    def test_passivo_negativo_errore(self):
        with pytest.raises(ValueError):
            _call("compenso_occ", passivo=-1.0)

    def test_tipo_non_valido_errore(self):
        with pytest.raises(ValueError):
            _call("compenso_occ", passivo=100_000.0, tipo="invalido")

    def test_dettaglio_fasce_struttura(self):
        result = _call("compenso_occ", passivo=300_000.0)
        for fascia in result["dettaglio_fasce"]:
            assert "fascia" in fascia
            assert "imponibile" in fascia
            assert "aliquota_pct" in fascia
            assert "importo" in fascia

    def test_riferimento_normativo(self):
        result = _call("compenso_occ", passivo=100_000.0)
        assert "D.M. 202/2014" in result["riferimento_normativo"]
        assert "OCC" in result["riferimento_normativo"]

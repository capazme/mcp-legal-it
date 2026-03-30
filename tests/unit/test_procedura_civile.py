import importlib

import pytest


def _call(fn_name: str, **kwargs):
    mod = importlib.import_module("src.tools.procedura_civile")
    fn = getattr(mod, fn_name)
    actual = fn.fn if hasattr(fn, "fn") else fn
    return actual(**kwargs)


# ---------------------------------------------------------------------------
# competenza_giudice
# ---------------------------------------------------------------------------

class TestCompetenzaGiudice:
    def test_valore_3000_civile_gdp(self):
        result = _call("competenza_giudice", valore_causa=3000.0)
        assert result["giudice_competente"] == "Giudice di Pace"
        assert "7" in result["articolo"]
        assert result["materia_riservata"] is False

    def test_valore_esatto_soglia_5000_gdp(self):
        result = _call("competenza_giudice", valore_causa=5000.0)
        assert result["giudice_competente"] == "Giudice di Pace"

    def test_valore_10000_civile_tribunale(self):
        result = _call("competenza_giudice", valore_causa=10_000.0)
        assert result["giudice_competente"] == "Tribunale"
        assert "9" in result["articolo"]

    def test_circolazione_15000_gdp(self):
        result = _call("competenza_giudice", valore_causa=15_000.0, materia="circolazione_stradale")
        assert result["giudice_competente"] == "Giudice di Pace"
        assert "7" in result["articolo"]

    def test_circolazione_esatta_soglia_gdp(self):
        result = _call("competenza_giudice", valore_causa=20_000.0, materia="circolazione_stradale")
        assert result["giudice_competente"] == "Giudice di Pace"

    def test_circolazione_25000_tribunale(self):
        result = _call("competenza_giudice", valore_causa=25_000.0, materia="circolazione_stradale")
        assert result["giudice_competente"] == "Tribunale"

    def test_lavoro_tribunale_sezione_lavoro(self):
        result = _call("competenza_giudice", valore_causa=500.0, materia="lavoro")
        assert "Tribunale" in result["giudice_competente"]
        assert "Lavoro" in result["giudice_competente"] or "lavoro" in result["note"].lower()
        assert result["materia_riservata"] is True

    def test_locazione_tribunale_riservata(self):
        result = _call("competenza_giudice", valore_causa=1000.0, materia="locazione")
        assert result["giudice_competente"] == "Tribunale"
        assert result["materia_riservata"] is True

    def test_condominio_tribunale_riservata(self):
        result = _call("competenza_giudice", valore_causa=500.0, materia="condominio")
        assert result["giudice_competente"] == "Tribunale"
        assert result["materia_riservata"] is True

    def test_famiglia_tribunale_riservata(self):
        result = _call("competenza_giudice", valore_causa=0.0, materia="famiglia")
        assert result["giudice_competente"] == "Tribunale"
        assert result["materia_riservata"] is True

    def test_fallimento_tribunale_specializzata(self):
        result = _call("competenza_giudice", valore_causa=100_000.0, materia="fallimento")
        assert "Tribunale" in result["giudice_competente"]
        assert result["materia_riservata"] is True

    def test_crisi_impresa_tribunale_specializzata(self):
        result = _call("competenza_giudice", valore_causa=50_000.0, materia="crisi_impresa")
        assert "Tribunale" in result["giudice_competente"]
        assert result["materia_riservata"] is True

    def test_valore_negativo_errore(self):
        with pytest.raises(ValueError):
            _call("competenza_giudice", valore_causa=-100.0)

    def test_valore_zero_gdp(self):
        result = _call("competenza_giudice", valore_causa=0.0)
        assert result["giudice_competente"] == "Giudice di Pace"

    def test_campi_risposta_presenti(self):
        result = _call("competenza_giudice", valore_causa=3000.0)
        for campo in ("giudice_competente", "articolo", "valore_causa", "materia", "materia_riservata", "note", "soglia_gdp_euro"):
            assert campo in result


# ---------------------------------------------------------------------------
# verifica_mediazione_obbligatoria
# ---------------------------------------------------------------------------

class TestVerificaMediazione:
    def test_condominio_obbligatoria(self):
        result = _call("verifica_mediazione_obbligatoria", materia="condominio")
        assert result["obbligatoria"] is True
        assert result["materia_trovata"] == "condominio"
        assert "2010" in result["fonte"]

    def test_locazione_obbligatoria(self):
        result = _call("verifica_mediazione_obbligatoria", materia="locazione")
        assert result["obbligatoria"] is True

    def test_franchising_obbligatoria_cartabia(self):
        result = _call("verifica_mediazione_obbligatoria", materia="franchising")
        assert result["obbligatoria"] is True
        assert "Cartabia" in result["fonte"]

    def test_contratti_bancari_obbligatoria(self):
        result = _call("verifica_mediazione_obbligatoria", materia="contratti_bancari")
        assert result["obbligatoria"] is True

    def test_responsabilita_medica_obbligatoria(self):
        result = _call("verifica_mediazione_obbligatoria", materia="responsabilita_medica")
        assert result["obbligatoria"] is True

    def test_societa_di_persone_cartabia(self):
        result = _call("verifica_mediazione_obbligatoria", materia="societa_di_persone")
        assert result["obbligatoria"] is True
        assert "Cartabia" in result["fonte"]

    def test_lavoro_non_obbligatoria(self):
        result = _call("verifica_mediazione_obbligatoria", materia="lavoro")
        assert result["obbligatoria"] is False
        assert result["materia_trovata"] is None

    def test_appalti_non_obbligatoria(self):
        result = _call("verifica_mediazione_obbligatoria", materia="appalti")
        assert result["obbligatoria"] is False

    def test_case_insensitive(self):
        result = _call("verifica_mediazione_obbligatoria", materia="CONDOMINIO")
        assert result["obbligatoria"] is True

    def test_spazi_normalizzati(self):
        result = _call("verifica_mediazione_obbligatoria", materia="patti di famiglia")
        assert result["obbligatoria"] is True

    def test_esclusioni_sempre_presenti(self):
        result = _call("verifica_mediazione_obbligatoria", materia="condominio")
        assert isinstance(result["esclusioni_applicabili"], list)
        assert len(result["esclusioni_applicabili"]) > 0

    def test_riferimento_normativo(self):
        result = _call("verifica_mediazione_obbligatoria", materia="locazione")
        assert "28/2010" in result["riferimento_normativo"]

    def test_materia_generica_non_trovata(self):
        result = _call("verifica_mediazione_obbligatoria", materia="diritto_sportivo")
        assert result["obbligatoria"] is False
        assert "volontaria" in result["note"].lower()


# ---------------------------------------------------------------------------
# gratuito_patrocinio
# ---------------------------------------------------------------------------

class TestGratuitoPatrocinio:
    def test_reddito_basso_ammesso(self):
        result = _call("gratuito_patrocinio", reddito_richiedente=10_000.0)
        assert result["ammesso"] is True
        assert result["margine"] > 0

    def test_reddito_alto_non_ammesso(self):
        result = _call("gratuito_patrocinio", reddito_richiedente=20_000.0)
        assert result["ammesso"] is False
        assert result["margine"] < 0

    def test_reddito_esatto_soglia_ammesso(self):
        result = _call("gratuito_patrocinio", reddito_richiedente=13_659.64)
        assert result["ammesso"] is True
        assert result["margine"] == pytest.approx(0.0, abs=0.01)

    def test_reddito_sopra_soglia_di_un_cent_non_ammesso(self):
        result = _call("gratuito_patrocinio", reddito_richiedente=13_659.65)
        assert result["ammesso"] is False

    def test_penale_soglia_maggiorata_con_familiari(self):
        # 13659.64 + 2*1032.91 = 15725.46
        result = _call(
            "gratuito_patrocinio",
            reddito_richiedente=15_000.0,
            n_familiari_conviventi=2,
            ambito="penale",
        )
        assert result["ammesso"] is True
        assert result["soglia_applicata"] == pytest.approx(15_725.46, abs=0.01)

    def test_penale_senza_familiari_soglia_base(self):
        result = _call(
            "gratuito_patrocinio",
            reddito_richiedente=10_000.0,
            n_familiari_conviventi=0,
            ambito="penale",
        )
        assert result["soglia_applicata"] == pytest.approx(13_659.64, abs=0.01)

    def test_redditi_familiari_sommati(self):
        result = _call(
            "gratuito_patrocinio",
            reddito_richiedente=5_000.0,
            redditi_familiari=[4_000.0, 3_000.0],
        )
        assert result["reddito_totale_nucleo"] == pytest.approx(12_000.0, abs=0.01)
        assert result["ammesso"] is True

    def test_redditi_familiari_sopra_soglia(self):
        result = _call(
            "gratuito_patrocinio",
            reddito_richiedente=5_000.0,
            redditi_familiari=[5_000.0, 5_000.0],
        )
        assert result["reddito_totale_nucleo"] == pytest.approx(15_000.0, abs=0.01)
        assert result["ammesso"] is False

    def test_vittima_violenza_sempre_ammessa(self):
        result = _call(
            "gratuito_patrocinio",
            reddito_richiedente=100_000.0,
            vittima_violenza=True,
        )
        assert result["ammesso"] is True
        assert result["vittima_violenza"] is True
        assert "automatica" in result["note"].lower()

    def test_vittima_violenza_reddito_zero(self):
        result = _call(
            "gratuito_patrocinio",
            reddito_richiedente=0.0,
            vittima_violenza=True,
        )
        assert result["ammesso"] is True

    def test_reddito_negativo_errore(self):
        with pytest.raises(ValueError):
            _call("gratuito_patrocinio", reddito_richiedente=-1.0)

    def test_riferimento_normativo_presente(self):
        result = _call("gratuito_patrocinio", reddito_richiedente=10_000.0)
        assert "DPR 115/2002" in result["riferimento_normativo"]
        assert "13.659,64" in result["riferimento_normativo"]

    def test_campi_risposta_presenti(self):
        result = _call("gratuito_patrocinio", reddito_richiedente=10_000.0)
        for campo in ("ammesso", "vittima_violenza", "reddito_richiedente", "reddito_totale_nucleo",
                      "soglia_applicata", "margine", "ambito", "note", "riferimento_normativo"):
            assert campo in result

    def test_ambito_default_civile(self):
        result = _call("gratuito_patrocinio", reddito_richiedente=10_000.0)
        assert result["ambito"] == "civile"

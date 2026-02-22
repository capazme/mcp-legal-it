"""Arithmetic verification tests for Sezione 8 — Diritto Penale."""

from tests.comparison.conftest import assert_close


def _call(fn_name, **kwargs):
    import importlib
    mod = importlib.import_module("src.tools.diritto_penale")
    fn = getattr(mod, fn_name)
    fn = getattr(fn, "fn", fn)
    return fn(**kwargs)


class TestAumentiRiduzioniPena:

    def test_base_36_mesi(self):
        r = _call("aumenti_riduzioni_pena", pena_base_mesi=36)
        assert_close(r["pena_risultante_mesi"], 36.0, tolerance=0.01, label="base_36")

    def test_recidiva(self):
        r = _call("aumenti_riduzioni_pena", pena_base_mesi=36, recidiva=True)
        # 36 + 36/3 = 48
        assert_close(r["pena_risultante_mesi"], 48.0, tolerance=0.01, label="recidiva_36")

    def test_aggravante_attenuante(self):
        r = _call("aumenti_riduzioni_pena", pena_base_mesi=36,
                   aggravanti=[{"tipo": "art. 61 n.7", "aumento_pct": 33.33}],
                   attenuanti=[{"tipo": "generiche", "riduzione_pct": 33.33}])
        # 36 + 12 = 48, then 48 - 16 = 32
        assert 30 < r["pena_risultante_mesi"] < 34

    def test_format_anni_mesi(self):
        r = _call("aumenti_riduzioni_pena", pena_base_mesi=30)
        assert "2 anni" in r["pena_risultante_formato"]


class TestConversionePena:

    def test_detentiva_a_pecuniaria(self):
        r = _call("conversione_pena", importo=30, direzione="detentiva_a_pecuniaria")
        # 30 giorni * 250€ = 7500€
        assert_close(r["importo_pecuniario_euro"], 7500.0, tolerance=0.01, label="det_to_pec")

    def test_pecuniaria_a_detentiva(self):
        r = _call("conversione_pena", importo=7500, direzione="pecuniaria_a_detentiva")
        # 7500 / 250 = 30 giorni
        assert r["giorni_detentivi"] == 30

    def test_pecuniaria_arrotondamento(self):
        r = _call("conversione_pena", importo=600, direzione="pecuniaria_a_detentiva")
        # 600 / 250 = 2.4 → ceil = 3
        assert r["giorni_detentivi"] == 3


class TestFinePena:

    def test_senza_liberazione(self):
        r = _call("fine_pena", data_inizio_pena="2024-01-01", pena_totale_mesi=24,
                   liberazione_anticipata=False)
        assert r["data_fine_pena"] == "2026-01-01"

    def test_con_liberazione(self):
        r = _call("fine_pena", data_inizio_pena="2024-01-01", pena_totale_mesi=24,
                   liberazione_anticipata=True)
        la = r["liberazione_anticipata"]
        # 730 days / 180 = 4 semesters → 4 * 45 = 180 days off
        assert la["semestri_scontati"] == 4
        assert la["sconto_giorni"] == 180

    def test_con_presofferto(self):
        r = _call("fine_pena", data_inizio_pena="2024-06-01", pena_totale_mesi=12,
                   giorni_presofferto=30, liberazione_anticipata=False)
        # Effective start: 2024-05-02, end: 2025-05-02
        assert r["data_inizio_effettiva"] == "2024-05-02"


class TestPenaConcordata:

    def test_patteggiamento_completo(self):
        r = _call("pena_concordata", pena_base_mesi=36, attenuanti_generiche=True, diminuente_rito=True)
        # 36 - 12 = 24, 24 - 8 = 16
        assert_close(r["pena_finale_mesi"], 16.0, tolerance=0.01, label="patteggiamento")
        assert r["sospendibile"] is True  # <= 24

    def test_pena_alta_non_sospendibile(self):
        r = _call("pena_concordata", pena_base_mesi=72, attenuanti_generiche=True, diminuente_rito=True)
        # 72 - 24 = 48, 48 - 16 = 32
        assert_close(r["pena_finale_mesi"], 32.0, tolerance=0.01, label="pena_alta")
        assert r["sospendibile"] is False

    def test_solo_diminuente(self):
        r = _call("pena_concordata", pena_base_mesi=36, attenuanti_generiche=False, diminuente_rito=True)
        # 36 - 12 = 24
        assert_close(r["pena_finale_mesi"], 24.0, tolerance=0.01, label="solo_dim")


class TestPrescrizioneReato:

    def test_delitto_6_anni(self):
        r = _call("prescrizione_reato", pena_massima_anni=6, data_commissione="2020-01-01")
        assert r["termine_base_anni"] == 6

    def test_delitto_3_anni_minimo_6(self):
        r = _call("prescrizione_reato", pena_massima_anni=3, data_commissione="2020-01-01")
        # Minimum 6 years for delitti
        assert r["termine_base_anni"] == 6

    def test_contravvenzione_minimo_4(self):
        r = _call("prescrizione_reato", pena_massima_anni=2, data_commissione="2020-01-01",
                   tipo_reato="contravvenzione")
        assert r["termine_base_anni"] == 4

    def test_con_interruzione(self):
        r = _call("prescrizione_reato", pena_massima_anni=6, data_commissione="2020-01-01",
                   interruzioni_giorni=1)
        # 6 + 6/4 = 7.5
        assert_close(r["termine_totale_anni"], 7.5, tolerance=0.01, label="interruzione")

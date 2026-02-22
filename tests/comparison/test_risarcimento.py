"""Arithmetic verification tests for Sezione 7 — Risarcimento Danni."""

from tests.comparison.conftest import assert_close


def _call(fn_name, **kwargs):
    import importlib
    mod = importlib.import_module("src.tools.risarcimento_danni")
    fn = getattr(mod, fn_name)
    fn = getattr(fn, "fn", fn)
    return fn(**kwargs)


class TestMenomazioniPlurime:

    def test_balthazard_15_10(self):
        r = _call("menomazioni_plurime", percentuali=[15, 10])
        # IT = 1 - (1-0.15)*(1-0.10) = 1 - 0.85*0.90 = 1 - 0.765 = 0.235 → 23.5%
        assert_close(r["invalidita_complessiva_pct"], 23.5, tolerance=0.01, label="balth_15_10")
        assert_close(r["somma_aritmetica_pct"], 25.0, tolerance=0.01, label="balth_somma")

    def test_balthazard_20_10_5(self):
        r = _call("menomazioni_plurime", percentuali=[20, 10, 5])
        # IT = 1 - 0.80*0.90*0.95 = 1 - 0.684 = 0.316 → 31.6%
        expected = (1 - 0.80 * 0.90 * 0.95) * 100
        assert_close(r["invalidita_complessiva_pct"], round(expected, 2), tolerance=0.01, label="balth_3")

    def test_riduzione_vs_somma(self):
        r = _call("menomazioni_plurime", percentuali=[30, 20])
        assert r["invalidita_complessiva_pct"] < r["somma_aritmetica_pct"]


class TestDannoBiologicoMacro:

    def test_50pct_40anni(self):
        r = _call("danno_biologico_macro", percentuale_invalidita=50, eta_vittima=40)
        assert r["danno_base"] > 0
        assert r["percentuale_invalidita"] == 50

    def test_personalizzazione(self):
        r_base = _call("danno_biologico_macro", percentuale_invalidita=30, eta_vittima=35,
                        personalizzazione_pct=0)
        r_pers = _call("danno_biologico_macro", percentuale_invalidita=30, eta_vittima=35,
                        personalizzazione_pct=50)
        assert r_pers["totale_risarcimento"] > r_base["totale_risarcimento"]
        expected_magg = r_base["danno_base"] * 50 / 100
        assert_close(r_pers["maggiorazione_morale"], round(expected_magg, 2), tolerance=0.01, label="macro_pers")


class TestDannoParentale:

    def test_genitore_figlio_milano(self):
        # Parent dies, child claims damages
        r = _call("danno_parentale", vittima="genitore", superstite="figlio", tabella="milano")
        assert r["importo_minimo"] > 0
        assert r["importo_massimo"] > r["importo_minimo"]
        # 50% personalizzazione (default) → midpoint
        expected = r["importo_minimo"] + (r["importo_massimo"] - r["importo_minimo"]) * 50 / 100
        assert_close(r["importo_liquidato"], round(expected, 2), tolerance=0.01, label="parent_mil")

    def test_minimo_e_massimo(self):
        r_min = _call("danno_parentale", vittima="figlio", superstite="genitore",
                       tabella="milano", personalizzazione_pct=0)
        r_max = _call("danno_parentale", vittima="figlio", superstite="genitore",
                       tabella="milano", personalizzazione_pct=100)
        assert_close(r_min["importo_liquidato"], r_min["importo_minimo"], tolerance=0.01, label="parent_min")
        assert_close(r_max["importo_liquidato"], r_max["importo_massimo"], tolerance=0.01, label="parent_max")


class TestRisarcimentoInail:

    def test_temporanea(self):
        r = _call("risarcimento_inail", retribuzione_annua=30000, percentuale_invalidita=0,
                   tipo="temporanea")
        giornaliera = 30000 / 365
        assert_close(r["retribuzione_giornaliera"], round(giornaliera, 2), tolerance=0.01, label="inail_giorn")
        assert_close(r["dal_4_al_90_giorno"]["indennita_giornaliera"],
                     round(giornaliera * 0.60, 2), tolerance=0.01, label="inail_60")

    def test_permanente_sotto_6(self):
        r = _call("risarcimento_inail", retribuzione_annua=30000, percentuale_invalidita=3,
                   tipo="permanente")
        assert r["esito"] == "Nessun indennizzo"

    def test_permanente_capitale(self):
        r = _call("risarcimento_inail", retribuzione_annua=30000, percentuale_invalidita=10,
                   tipo="permanente")
        assert r["forma"] == "capitale"

    def test_permanente_rendita(self):
        r = _call("risarcimento_inail", retribuzione_annua=30000, percentuale_invalidita=20,
                   tipo="permanente")
        assert r["forma"] == "rendita"
        assert r["rendita_annua"] > 0


class TestDannoNonPatrimoniale:

    def test_micro_5pct(self):
        r = _call("danno_non_patrimoniale", percentuale_invalidita=5, eta_vittima=35,
                   giorni_itt=30, spese_mediche=1000)
        assert "micropermanenti" in r["tipo_calcolo"]
        assert r["componenti"]["danno_biologico"] > 0
        assert r["componenti"]["danno_patrimoniale_emergente"]["spese_mediche"] == 1000.0

    def test_macro_20pct(self):
        r = _call("danno_non_patrimoniale", percentuale_invalidita=20, eta_vittima=40,
                   danno_morale_pct=30)
        assert "macropermanenti" in r["tipo_calcolo"]
        expected_morale = r["componenti"]["danno_biologico"] * 30 / 100
        assert_close(r["componenti"]["danno_morale"]["importo"],
                     round(expected_morale, 2), tolerance=0.01, label="dnp_morale")


class TestEquoIndennizzo:

    def test_categoria_5(self):
        r = _call("equo_indennizzo", categoria_tabella="5", percentuale_invalidita=35,
                   stipendio_annuo=30000)
        expected = 30000 * 3.0 * 35 / 100
        assert_close(r["equo_indennizzo"], round(expected, 2), tolerance=0.01, label="equo_5")

    def test_categoria_1_pensione(self):
        r = _call("equo_indennizzo", categoria_tabella="1", percentuale_invalidita=90,
                   stipendio_annuo=40000)
        assert r["pensione_privilegiata"] is True

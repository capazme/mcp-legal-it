"""Arithmetic verification tests for Sezione 11 — detrazioni IRPEF."""

from tests.comparison.conftest import assert_close


def _call(fn_name, **kwargs):
    import importlib
    mod = importlib.import_module("src.tools.dichiarazione_redditi")
    fn = getattr(mod, fn_name)
    fn = getattr(fn, "fn", fn)
    return fn(**kwargs)


class TestDetrazioneFigli:

    def test_reddito_30k_2figli(self):
        r = _call("detrazione_figli", reddito_complessivo=30000, n_figli_over21=2)
        # 950 * (95000-30000)/95000 = 950 * 0.6842 = 650.0 per figlio
        expected = 950 * (95000 - 30000) / 95000
        assert_close(r["dettaglio"][0]["importo"], round(expected, 2), tolerance=0.01, label="figlio_1")
        assert_close(r["detrazione_totale"], round(expected * 2, 2), tolerance=0.01, label="totale")

    def test_reddito_over_soglia(self):
        r = _call("detrazione_figli", reddito_complessivo=100000, n_figli_over21=1)
        assert r["detrazione_totale"] == 0.0

    def test_figlio_disabile(self):
        r = _call("detrazione_figli", reddito_complessivo=40000, n_figli_over21=1, n_figli_disabili=1)
        expected = 1350 * (95000 - 40000) / 95000
        assert_close(r["detrazione_totale"], round(expected, 2), tolerance=0.01, label="disabile")


class TestDetrazioneConiuge:

    def test_reddito_10k(self):
        r = _call("detrazione_coniuge", reddito_complessivo=10000)
        expected = max(800 - (110 * 10000 / 15000), 0)
        assert_close(r["detrazione"], round(expected, 2), tolerance=0.01, label="coniuge_10k")

    def test_reddito_25k(self):
        r = _call("detrazione_coniuge", reddito_complessivo=25000)
        assert_close(r["detrazione"], 690.0, tolerance=0.01, label="coniuge_25k")

    def test_reddito_60k(self):
        r = _call("detrazione_coniuge", reddito_complessivo=60000)
        expected = 690 * (80000 - 60000) / 40000
        assert_close(r["detrazione"], round(expected, 2), tolerance=0.01, label="coniuge_60k")

    def test_reddito_over_80k(self):
        r = _call("detrazione_coniuge", reddito_complessivo=90000)
        assert r["detrazione"] == 0.0


class TestDetrazioneAltriFamiliari:

    def test_reddito_40k_2fam(self):
        r = _call("detrazione_altri_familiari", reddito_complessivo=40000, n_familiari=2)
        coeff = (80000 - 40000) / 80000
        expected = round(750 * coeff, 2) * 2
        assert_close(r["detrazione_totale"], round(expected, 2), tolerance=0.01, label="altri_fam")


class TestDetrazioneLavoroDipendente:

    def test_reddito_10k(self):
        r = _call("detrazione_lavoro_dipendente", reddito_complessivo=10000)
        assert_close(r["detrazione_rapportata"], 1955.0, tolerance=0.01, label="lav_dip_10k")

    def test_reddito_20k(self):
        r = _call("detrazione_lavoro_dipendente", reddito_complessivo=20000)
        expected = 1910 + 1190 * (28000 - 20000) / (28000 - 15000)
        assert_close(r["detrazione_rapportata"], round(expected, 2), tolerance=0.01, label="lav_dip_20k")

    def test_reddito_60k(self):
        r = _call("detrazione_lavoro_dipendente", reddito_complessivo=60000)
        assert r["detrazione_rapportata"] == 0.0


class TestDetrazionePensione:

    def test_reddito_7k(self):
        r = _call("detrazione_pensione", reddito_complessivo=7000)
        assert_close(r["detrazione_rapportata"], 1955.0, tolerance=0.01, label="pens_7k")

    def test_reddito_15k(self):
        r = _call("detrazione_pensione", reddito_complessivo=15000)
        expected = 700 + 1255 * (28000 - 15000) / (28000 - 8500)
        assert_close(r["detrazione_rapportata"], round(expected, 2), tolerance=0.01, label="pens_15k")


class TestDetrazioneAssegnoConiuge:

    def test_reddito_4k(self):
        r = _call("detrazione_assegno_coniuge", reddito_complessivo=4000)
        assert_close(r["detrazione"], 1265.0, tolerance=0.01, label="assegno_4k")

    def test_reddito_20k(self):
        r = _call("detrazione_assegno_coniuge", reddito_complessivo=20000)
        expected = 500 + 765 * (28000 - 20000) / (28000 - 5500)
        assert_close(r["detrazione"], round(expected, 2), tolerance=0.01, label="assegno_20k")


class TestDetrazioneCanoneLocazione:

    def test_libero_reddito_basso(self):
        r = _call("detrazione_canone_locazione", reddito_complessivo=10000, tipo_contratto="libero")
        assert_close(r["detrazione"], 300.0, tolerance=0.01, label="canone_lib_10k")

    def test_concordato_reddito_basso(self):
        r = _call("detrazione_canone_locazione", reddito_complessivo=10000, tipo_contratto="concordato")
        assert_close(r["detrazione"], 495.80, tolerance=0.01, label="canone_conc_10k")

    def test_giovani_under31(self):
        r = _call("detrazione_canone_locazione", reddito_complessivo=10000, tipo_contratto="giovani_under31")
        assert_close(r["detrazione"], 2000.0, tolerance=0.01, label="canone_giovani")

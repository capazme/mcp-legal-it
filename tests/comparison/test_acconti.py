"""Arithmetic verification tests for acconti IRPEF, cedolare secca, rateizzazione."""

from tests.comparison.conftest import assert_close


def _call(fn_name, **kwargs):
    import importlib
    mod = importlib.import_module("src.tools.dichiarazione_redditi")
    fn = getattr(mod, fn_name)
    fn = getattr(fn, "fn", fn)
    return fn(**kwargs)


class TestAccontoIrpef:

    def test_acconto_1000(self):
        r = _call("acconto_irpef", imposta_anno_precedente=1000)
        assert r["acconto_dovuto"] is True
        assert_close(r["primo_acconto"]["importo"], 400.0, tolerance=0.01, label="primo_acc")
        assert_close(r["secondo_acconto"]["importo"], 600.0, tolerance=0.01, label="secondo_acc")

    def test_sotto_soglia(self):
        r = _call("acconto_irpef", imposta_anno_precedente=50)
        assert r["acconto_dovuto"] is False

    def test_acconto_5000(self):
        r = _call("acconto_irpef", imposta_anno_precedente=5000)
        assert_close(r["primo_acconto"]["importo"], 2000.0, tolerance=0.01, label="primo_5k")
        assert_close(r["secondo_acconto"]["importo"], 3000.0, tolerance=0.01, label="secondo_5k")


class TestAccontoCedolareSecca:

    def test_acconto_2000(self):
        r = _call("acconto_cedolare_secca", imposta_anno_precedente=2000)
        assert r["acconto_dovuto"] is True
        assert_close(r["primo_acconto"]["importo"], 800.0, tolerance=0.01, label="ced_primo")
        assert_close(r["secondo_acconto"]["importo"], 1200.0, tolerance=0.01, label="ced_secondo")

    def test_sotto_soglia(self):
        r = _call("acconto_cedolare_secca", imposta_anno_precedente=40)
        assert r["acconto_dovuto"] is False


class TestRateizzazioneImposte:

    def test_3_rate(self):
        r = _call("rateizzazione_imposte", importo_totale=3000, n_rate=3, data_prima_rata="2024-06-30")
        assert len(r["piano_rate"]) == 3
        # First rata has no interest
        assert r["piano_rate"][0]["interessi"] == 0
        # Sum of capital portions equals total
        total_cap = sum(rata["importo_capitale"] for rata in r["piano_rate"])
        assert_close(total_cap, 3000.0, tolerance=0.01, label="sum_cap")


class TestRegimeForfettario:

    def test_professionista_startup(self):
        r = _call("regime_forfettario", ricavi=50000, coefficiente_redditivita=78, anni_attivita=1)
        reddito_lordo = 50000 * 78 / 100  # 39000
        assert_close(r["reddito_lordo"], reddito_lordo, tolerance=0.01, label="redd_lordo")
        assert r["aliquota_pct"] == 5  # startup
        imposta = reddito_lordo * 5 / 100  # 1950
        assert_close(r["imposta_sostitutiva"], imposta, tolerance=0.01, label="imposta_forf")

    def test_professionista_ordinario(self):
        r = _call("regime_forfettario", ricavi=60000, coefficiente_redditivita=78, anni_attivita=6)
        assert r["aliquota_pct"] == 15  # not startup

    def test_over_limit(self):
        r = _call("regime_forfettario", ricavi=100000)
        assert "errore" in r


class TestCalcoloTfr:

    def test_base(self):
        r = _call("calcolo_tfr", retribuzione_annua_lorda=30000, anni_servizio=10)
        accantonamento = 30000 / 13.5
        assert_close(r["accantonamento_annuo"], round(accantonamento, 2), tolerance=0.01, label="accantonamento")
        assert r["tfr_lordo"] > accantonamento * 10  # rivalutato > nominale
        assert r["tfr_netto"] < r["tfr_lordo"]  # tassazione riduce


class TestRavvedimentoOperoso:

    def test_sprint_5_giorni(self):
        r = _call("ravvedimento_operoso", imposta_dovuta=1000, giorni_ritardo=5)
        # Sprint D.Lgs. 87/2024: 12.5/15*5/10 = 0.4167% → €4.17
        expected = round(1000 * 12.5 / 15 * 5 / 10 / 100, 2)
        assert_close(r["sanzione"], expected, tolerance=0.01, label="sprint_5gg")
        assert r["tipo_ravvedimento"] == "sprint (entro 14 giorni)"

    def test_breve_20_giorni(self):
        r = _call("ravvedimento_operoso", imposta_dovuta=1000, giorni_ritardo=20)
        # Breve D.Lgs. 87/2024: 12.5/10 = 1.25% → €12.50
        assert_close(r["sanzione"], 12.50, tolerance=0.01, label="breve_20gg")

    def test_lungo_180_giorni(self):
        r = _call("ravvedimento_operoso", imposta_dovuta=1000, giorni_ritardo=180)
        # Lungo D.Lgs. 87/2024: 25/8 = 3.125% → €31.25
        assert_close(r["sanzione"], 31.25, tolerance=0.01, label="lungo_180gg")

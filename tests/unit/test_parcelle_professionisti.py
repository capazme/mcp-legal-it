import importlib

import pytest


def _call(fn_name: str, **kwargs):
    mod = importlib.import_module("src.tools.parcelle_professionisti")
    fn = getattr(mod, fn_name)
    actual = fn.fn if hasattr(fn, "fn") else fn
    return actual(**kwargs)


# ---------------------------------------------------------------------------
# fattura_professionista
# ---------------------------------------------------------------------------


class TestFatturaProfessionista:
    def test_ordinario_ingegnere(self):
        r = _call("fattura_professionista", imponibile=1000.0, tipo="ingegnere")
        assert r["tipo_professionista"] == "ingegnere"
        assert r["regime"] == "ordinario"
        assert r["rivalsa_inps"] == pytest.approx(40.0)
        assert r["base_imponibile_iva"] == pytest.approx(1040.0)
        assert r["iva"] == pytest.approx(228.80)
        assert r["ritenuta_acconto"] == pytest.approx(200.0)
        assert r["totale_fattura"] == pytest.approx(1268.80)
        assert r["netto_a_pagare"] == pytest.approx(1068.80)

    def test_psicologo_rivalsa_5pct(self):
        r = _call("fattura_professionista", imponibile=1000.0, tipo="psicologo")
        assert r["rivalsa_inps"] == pytest.approx(50.0)
        assert r["base_imponibile_iva"] == pytest.approx(1050.0)

    def test_forfettario_con_bollo(self):
        r = _call("fattura_professionista", imponibile=200.0, tipo="commercialista", regime="forfettario")
        assert r["regime"] == "forfettario"
        assert r["iva"] == 0.0
        assert r["ritenuta_acconto"] == 0.0
        assert r["bollo"] == 2.0
        assert r["totale_fattura"] == pytest.approx(200.0 + 200.0 * 4 / 100 + 2.0)

    def test_forfettario_senza_bollo_sotto_soglia(self):
        r = _call("fattura_professionista", imponibile=50.0, tipo="medico", regime="forfettario")
        assert r["bollo"] == 0.0
        assert r["iva"] == 0.0

    def test_tipo_non_valido(self):
        r = _call("fattura_professionista", imponibile=1000.0, tipo="avvocato")
        assert "errore" in r

    def test_regime_non_valido(self):
        r = _call("fattura_professionista", imponibile=1000.0, regime="flat")
        assert "errore" in r

    def test_tutti_i_tipi_validi(self):
        tipi = ["ingegnere", "architetto", "geometra", "commercialista", "consulente_lavoro", "psicologo", "medico"]
        for t in tipi:
            r = _call("fattura_professionista", imponibile=500.0, tipo=t)
            assert "errore" not in r

    def test_voci_ordinario(self):
        r = _call("fattura_professionista", imponibile=1000.0)
        voci_nomi = [v["voce"] for v in r["voci"]]
        assert any("Compenso" in n for n in voci_nomi)
        assert any("integrativo" in n for n in voci_nomi)  # ingegnere: Inarcassa
        assert any("IVA" in n for n in voci_nomi)
        assert any("Ritenuta" in n for n in voci_nomi)

    def test_gestione_separata_ritenuta_sulla_rivalsa(self):
        # Rivalsa INPS 4%: e' compenso, quindi concorre alla base della ritenuta (1040 x 20% = 208);
        # il contributo integrativo di cassa invece no (1000 x 20% = 200)
        inps = _call("fattura_professionista", imponibile=1000.0, tipo="gestione_separata")
        assert inps["ritenuta_acconto"] == pytest.approx(208.0)
        assert inps["base_ritenuta"] == pytest.approx(1040.0)
        cassa = _call("fattura_professionista", imponibile=1000.0, tipo="ingegnere")
        assert cassa["ritenuta_acconto"] == pytest.approx(200.0)
        assert cassa["contributo_previdenziale"] == pytest.approx(40.0)

    def test_forfettario_bollo_esattamente_sulla_soglia(self):
        # base_imponibile_iva = 77.47 (not strictly greater) → no bollo
        # imponibile = 77.47 / 1.04 for ingegnere (rivalsa 4%) to get base == 77.47
        imponibile = round(77.47 / 1.04, 2)
        r = _call("fattura_professionista", imponibile=imponibile, tipo="ingegnere", regime="forfettario")
        assert r["bollo"] == 0.0

    def test_arrotondamento_mezzo_centesimo_iva(self):
        # Rounding convention (no tax rule on the cent): half a cent goes up. Hand check:
        # 1.000,24 x 4% = 40,0096 -> 40,01; base 1.040,25; IVA 22% = 228,855 -> 228,86;
        # total 1.269,11; withholding 20% x 1.000,24 = 200,048 -> 200,05; net 1.069,06.
        r = _call("fattura_professionista", imponibile=1000.24, tipo="ingegnere")
        assert r["iva"] == pytest.approx(228.86)
        assert r["totale_fattura"] == pytest.approx(1269.11)
        assert r["ritenuta_acconto"] == pytest.approx(200.05)
        assert r["netto_a_pagare"] == pytest.approx(1069.06)

    def test_arrotondamento_mezzo_centesimo_contributo(self):
        # ENPAP-style 5% on 1.000,50 = 50,025 -> 50,03; base 1.050,53; IVA = 231,1166 -> 231,12.
        r = _call("fattura_professionista", imponibile=1000.5, tipo="psicologo")
        assert r["contributo_previdenziale"] == pytest.approx(50.03)
        assert r["iva"] == pytest.approx(231.12)
        assert r["totale_fattura"] == pytest.approx(1281.65)


# ---------------------------------------------------------------------------
# compenso_ctu
# ---------------------------------------------------------------------------


class TestCompensoCtu:
    # DM 30/05/2002 (GU 182/2002), tabelle allegate; vacazioni art. 4 L. 319/1980.
    def test_perizia_immobiliare_art_13_scaglioni(self):
        # art. 13 estimo, valore 100.000, progressive brackets: minimum 53,01 + 48,11 + 129,67 + 146,78
        # + 183,26 = 560,83; maximum 1.121,62 (rates 1,0264-2,0685% ... 0,3790-0,7579%)
        r = _call("compenso_ctu", tipo_incarico="perizia_immobiliare", valore_causa=100_000.0)
        assert r["calcolo_a_percentuale"]["compenso_min"] == pytest.approx(560.83, abs=0.01)
        assert r["calcolo_a_percentuale"]["compenso_max"] == pytest.approx(1_121.62, abs=0.01)

    def test_minimo_145_12(self):
        # art. 13: value at the top of the first bracket 5.164,57 => 53,01-106,83, raised to the 145,12 minimum
        r = _call("compenso_ctu", tipo_incarico="perizia_immobiliare", valore_causa=5_164.57)
        assert r["calcolo_a_percentuale"]["compenso_min"] == pytest.approx(145.12)
        assert r["calcolo_a_percentuale"]["compenso_max"] == pytest.approx(145.12)

    def test_perizia_contabile_art_2(self):
        # art. 2, valore 500.000 => 5.038,36 - 10.100,42
        r = _call("compenso_ctu", tipo_incarico="perizia_contabile", valore_causa=500_000.0)
        assert r["calcolo_a_percentuale"]["compenso_min"] == pytest.approx(5_038.36, abs=0.01)
        assert r["calcolo_a_percentuale"]["compenso_max"] == pytest.approx(10_100.42, abs=0.01)

    def test_stima_danni_art_3_meta_art_2(self):
        # art. 3: art. 2 halved; art. 2 on 50.000 = 1.440,57 - 2.880,57 => 720,29 - 1.440,29
        r = _call("compenso_ctu", tipo_incarico="stima_danni", valore_causa=50_000.0)
        assert r["calcolo_a_percentuale"]["compenso_min"] == pytest.approx(720.29, abs=0.01)
        assert r["calcolo_a_percentuale"]["compenso_max"] == pytest.approx(1_440.29, abs=0.01)

    def test_accertamenti_tecnici_art_11(self):
        # art. 11, valore 200.000 => 3.760,83 - 7.542,66
        r = _call("compenso_ctu", tipo_incarico="accertamenti_tecnici", valore_causa=200_000.0)
        assert r["calcolo_a_percentuale"]["compenso_min"] == pytest.approx(3_760.83, abs=0.01)
        assert r["calcolo_a_percentuale"]["compenso_max"] == pytest.approx(7_542.66, abs=0.01)

    def test_perizia_medica_art_21_onorario_fisso(self):
        # art. 21: from 48,03 to 290,77 euro, independent of the value
        for v in (1_000.0, 50_000.0):
            r = _call("compenso_ctu", tipo_incarico="perizia_medica", valore_causa=v)
            assert r["calcolo_a_percentuale"]["compenso_min"] == pytest.approx(48.03)
            assert r["calcolo_a_percentuale"]["compenso_max"] == pytest.approx(290.77)

    def test_vacazioni_10_ore(self):
        # art. 4 L. 319/1980: 10 h = 5 vacazioni of 2 h; 14,68 each (Corte cost. 16/2025) = 73,40
        r = _call("compenso_ctu", tipo_incarico="perizia_medica", ore_lavoro=10.0)
        assert r["calcolo_orario"]["vacazioni"] == 5
        assert r["calcolo_orario"]["compenso_min"] == pytest.approx(73.40)

    def test_vacazione_divisa_per_meta(self):
        # art. 4 c. 4: 5 h = 2 vacazioni + 1 h (not above 1 h 15) = half vacazione => 2,5 x 14,68 = 36,70
        r = _call("compenso_ctu", tipo_incarico="perizia_medica", ore_lavoro=5.0)
        assert r["calcolo_orario"]["vacazioni"] == 2.5
        assert r["calcolo_orario"]["compenso_max"] == pytest.approx(36.70)

    def test_vacazione_oltre_un_ora_e_un_quarto_intera(self):
        # art. 4 c. 4: beyond 1 h 15 the vacazione is due in full: 3,5 h = 1 + 1 h 30 => 2 vacazioni
        r = _call("compenso_ctu", tipo_incarico="perizia_medica", ore_lavoro=3.5)
        assert r["calcolo_orario"]["vacazioni"] == 2
        assert r["calcolo_orario"]["compenso_min"] == pytest.approx(29.36)

    def test_tetto_quattro_vacazioni_al_giorno(self):
        # art. 4 c. 5: at most four vacazioni per day: 20 h on 2 days => 8 vacazioni = 117,44
        r = _call("compenso_ctu", tipo_incarico="perizia_medica", ore_lavoro=20.0, giorni_lavorativi=2)
        assert r["calcolo_orario"]["vacazioni"] == 8
        assert r["calcolo_orario"]["compenso_min"] == pytest.approx(117.44)

    def test_entrambi_valore_e_ore(self):
        r = _call("compenso_ctu", tipo_incarico="perizia_medica", valore_causa=50_000.0, ore_lavoro=5.0)
        assert "calcolo_a_percentuale" in r
        assert "calcolo_orario" in r

    def test_tipo_non_valido(self):
        r = _call("compenso_ctu", tipo_incarico="tipo_inesistente", valore_causa=1000.0)
        assert "errore" in r

    def test_nessun_parametro_calcolo(self):
        r = _call("compenso_ctu", tipo_incarico="stima_danni")
        assert "errore" in r

    def test_tutti_i_tipi_validi(self):
        tipi = ["perizia_immobiliare", "perizia_contabile", "perizia_medica", "stima_danni", "accertamenti_tecnici"]
        for t in tipi:
            r = _call("compenso_ctu", tipo_incarico=t, ore_lavoro=1.0)
            assert "errore" not in r
            assert "note" in r

    def test_note_presenti(self):
        r = _call("compenso_ctu", tipo_incarico="perizia_medica", ore_lavoro=2.0)
        assert isinstance(r["note"], list)
        assert len(r["note"]) >= 1


# ---------------------------------------------------------------------------
# spese_mediazione
# ---------------------------------------------------------------------------


class TestSpeseMediazione:
    # Reference: DM 24 ottobre 2023 n. 150, art. 28 (avvio 40/75/110; primo incontro 60/120/170),
    # art. 30 (Tabella A meno primo incontro, +10% accordo al primo incontro, +25% dopo),
    # Tabella A (minimi/massimi; 'medio' is the midpoint convention). VAT 22% on the whole indennita'.
    def test_primo_scaglione_accordo_primo_incontro(self):
        # 1.000 euro, Tabella A medio 120: avvio 40 + primo 60 + (120-60) x 1,10 = 66 -> 166;
        # VAT 36,52; total 202,52.
        r = _call("spese_mediazione", valore_controversia=1000.0, esito="positivo")
        assert r["dettaglio_per_parte"]["spese_avvio"] == pytest.approx(40.0)
        assert r["dettaglio_per_parte"]["spese_mediazione_primo_incontro"] == pytest.approx(60.0)
        assert r["dettaglio_per_parte"]["spese_mediazione_ulteriori"] == pytest.approx(66.0)
        assert r["indennita_per_parte"] == pytest.approx(166.0)
        assert r["iva_22_per_parte"] == pytest.approx(36.52)
        assert r["totale_per_parte"] == pytest.approx(202.52)
        assert r["totale_organismo_2_parti"] == pytest.approx(405.04)

    def test_mancato_accordo_primo_incontro(self):
        # Art. 28 co. 6: only avvio 75 + primo incontro 120 = 195; VAT 42,90; total 237,90.
        r = _call("spese_mediazione", valore_controversia=15_000.0, esito="negativo")
        assert r["indennita_per_parte"] == pytest.approx(195.0)
        assert r["totale_per_parte"] == pytest.approx(237.90)

    def test_prosecuzione_senza_accordo_niente_maggiorazione(self):
        # Art. 30 co. 3: 15.000 sits in 10.001-25.000 (Tabella A 440-720, medio 580);
        # avvio 75 + primo 120 + (580-120) = 655, no surcharge; VAT 144,10; total 799,10.
        r = _call("spese_mediazione", valore_controversia=15_000.0, esito="negativo", momento="incontri_successivi")
        assert r["indennita_per_parte"] == pytest.approx(655.0)
        assert r["totale_per_parte"] == pytest.approx(799.10)

    def test_accordo_incontri_successivi_25pct(self):
        # Art. 30 co. 2: 1.000 euro: 40 + 60 + (120-60) x 1,25 = 75 -> 175; VAT 38,50; total 213,50.
        r = _call("spese_mediazione", valore_controversia=1000.0, esito="positivo", momento="incontri_successivi")
        assert r["indennita_per_parte"] == pytest.approx(175.0)
        assert r["totale_per_parte"] == pytest.approx(213.50)

    def test_confine_50000_01_avvio_110(self):
        # 50.000,01 euro: avvio 110, primo 170, Tabella A 1.200-1.500 medio 1.350;
        # (1.350-170) x 1,10 = 1.298 -> 1.578; VAT 347,16; total 1.925,16.
        r = _call("spese_mediazione", valore_controversia=50_000.01, esito="positivo")
        assert r["dettaglio_per_parte"]["spese_avvio"] == pytest.approx(110.0)
        assert r["indennita_per_parte"] == pytest.approx(1_578.0)
        assert r["totale_per_parte"] == pytest.approx(1_925.16)

    def test_confine_50000_avvio_75(self):
        # 50.000 euro (inclusive): avvio 75, primo 120, Tabella A 720-1.200 medio 960;
        # (960-120) x 1,10 = 924 -> 1.119; VAT 246,18; total 1.365,18.
        r = _call("spese_mediazione", valore_controversia=50_000.0, esito="positivo")
        assert r["dettaglio_per_parte"]["spese_avvio"] == pytest.approx(75.0)
        assert r["totale_per_parte"] == pytest.approx(1_365.18)

    def test_scaglioni_distinti_150000(self):
        # Tabella A keeps 50.001-150.000 (1.200-1.500) and 150.001-250.000 (1.500-2.500) apart:
        # 150.000,01 -> medio 2.000; 110 + 170 + (2.000-170) x 1,10 = 2.013 -> 2.293;
        # VAT 504,46; total 2.797,46.
        r = _call("spese_mediazione", valore_controversia=150_000.01, esito="positivo")
        assert r["tabella_a"]["medio"] == pytest.approx(2_000.0)
        assert r["totale_per_parte"] == pytest.approx(2_797.46)

    def test_mediazione_obbligatoria_meno_un_quinto(self):
        # Art. 28 co. 8 and art. 30 co. 4: everything reduced by one fifth: 1.000 euro,
        # avvio 32, primo 48, ulteriori (60 x 1,10) x 0,8 = 52,80 -> 132,80; VAT 29,22; total 162,02.
        r = _call("spese_mediazione", valore_controversia=1000.0, esito="positivo", mediazione_obbligatoria=True)
        assert r["dettaglio_per_parte"]["spese_avvio"] == pytest.approx(32.0)
        assert r["dettaglio_per_parte"]["spese_mediazione_primo_incontro"] == pytest.approx(48.0)
        assert r["indennita_per_parte"] == pytest.approx(132.80)
        assert r["totale_per_parte"] == pytest.approx(162.02)

    def test_importo_tabella_minimo_e_massimo(self):
        # 1.000 euro, Tabella A 80-160: minimo -> 40 + 60 + 20 x 1,10 = 122; massimo -> 40 + 60 + 100 x 1,10 = 210.
        mn = _call("spese_mediazione", valore_controversia=1000.0, importo_tabella="minimo")
        mx = _call("spese_mediazione", valore_controversia=1000.0, importo_tabella="massimo")
        assert mn["indennita_per_parte"] == pytest.approx(122.0)
        assert mx["indennita_per_parte"] == pytest.approx(210.0)

    def test_oltre_5_milioni_coefficienti(self):
        # Tabella A note: above 5.000.000 euro 0,2% (min) and 0,3% (max) of the value:
        # 6.000.000 -> 12.000-18.000, medio 15.000; 110 + 170 + (15.000-170) x 1,10 = 16.313 -> 16.593.
        r = _call("spese_mediazione", valore_controversia=6_000_000.0, esito="positivo")
        assert r["tabella_a"]["minimo"] == pytest.approx(12_000.0)
        assert r["tabella_a"]["massimo"] == pytest.approx(18_000.0)
        assert r["indennita_per_parte"] == pytest.approx(16_593.0)

    def test_esito_non_valido(self):
        r = _call("spese_mediazione", valore_controversia=1000.0, esito="invalido")
        assert "errore" in r

    def test_parametri_non_validi(self):
        assert "errore" in _call("spese_mediazione", valore_controversia=1000.0, momento="mai")
        assert "errore" in _call("spese_mediazione", valore_controversia=1000.0, importo_tabella="alto")
        assert "errore" in _call("spese_mediazione", valore_controversia=0.0)

    def test_agevolazioni_presenti(self):
        r = _call("spese_mediazione", valore_controversia=5000.0, esito="positivo")
        assert isinstance(r["agevolazioni"], list)
        assert len(r["agevolazioni"]) >= 1


# ---------------------------------------------------------------------------
# compenso_orario
# ---------------------------------------------------------------------------


class TestCompensoOrario:
    def test_arrotondamento_mezz_ora(self):
        r = _call("compenso_orario", tariffa_oraria=100.0, ore=2, minuti=10)
        assert r["tempo_arrotondato_ore"] == pytest.approx(2.5)
        assert r["compenso"] == pytest.approx(250.0)

    def test_arrotondamento_quarto_ora(self):
        r = _call("compenso_orario", tariffa_oraria=80.0, ore=1, minuti=5, arrotondamento="quarto_ora")
        assert r["tempo_arrotondato_ore"] == pytest.approx(1.25)
        assert r["compenso"] == pytest.approx(100.0)

    def test_arrotondamento_ora(self):
        r = _call("compenso_orario", tariffa_oraria=120.0, ore=1, minuti=1, arrotondamento="ora")
        assert r["tempo_arrotondato_ore"] == pytest.approx(2.0)
        assert r["compenso"] == pytest.approx(240.0)

    def test_minuti_zero_nessun_arrotondamento(self):
        r = _call("compenso_orario", tariffa_oraria=100.0, ore=3, minuti=0)
        assert r["tempo_arrotondato_ore"] == pytest.approx(3.0)
        assert r["compenso"] == pytest.approx(300.0)

    def test_arrotondamento_non_valido(self):
        r = _call("compenso_orario", tariffa_oraria=100.0, ore=1, arrotondamento="anno")
        assert "errore" in r

    def test_minuti_fuori_range(self):
        r = _call("compenso_orario", tariffa_oraria=100.0, ore=1, minuti=60)
        assert "errore" in r

    def test_minuti_negativi(self):
        r = _call("compenso_orario", tariffa_oraria=100.0, ore=1, minuti=-1)
        assert "errore" in r

    def test_output_keys(self):
        r = _call("compenso_orario", tariffa_oraria=100.0, ore=1, minuti=30)
        for k in ("compenso", "tempo_effettivo", "tempo_arrotondato"):
            assert k in r


# ---------------------------------------------------------------------------
# ritenuta_acconto
# ---------------------------------------------------------------------------


class TestRitenutaAcconto:
    def test_aliquota_default_20pct(self):
        r = _call("ritenuta_acconto", compenso_lordo=1000.0)
        assert r["ritenuta"] == pytest.approx(200.0)
        assert r["netto_percepito"] == pytest.approx(800.0)

    def test_aliquota_personalizzata(self):
        r = _call("ritenuta_acconto", compenso_lordo=1000.0, aliquota=30.0)
        assert r["ritenuta"] == pytest.approx(300.0)
        assert r["netto_percepito"] == pytest.approx(700.0)

    def test_certificazione_unica_keys(self):
        r = _call("ritenuta_acconto", compenso_lordo=500.0)
        cu = r["certificazione_unica"]
        for k in ("punto_4_compensi", "punto_8_ritenute", "punto_9_netto", "codice_tributo_f24"):
            assert k in cu

    def test_codice_tributo_1040(self):
        r = _call("ritenuta_acconto", compenso_lordo=1000.0)
        assert r["certificazione_unica"]["codice_tributo_f24"] == "1040"

    def test_lordo_uguale_cu_punto4(self):
        r = _call("ritenuta_acconto", compenso_lordo=750.0)
        assert r["certificazione_unica"]["punto_4_compensi"] == 750.0

    def test_somma_corretta(self):
        r = _call("ritenuta_acconto", compenso_lordo=1234.56)
        assert r["ritenuta"] + r["netto_percepito"] == pytest.approx(r["compenso_lordo"])


# ---------------------------------------------------------------------------
# compenso_curatore_fallimentare
# ---------------------------------------------------------------------------


class TestCompensoCuratoreFallimentare:
    def test_piccola_procedura_minimo(self):
        # DM 30/2012 art. 4 c. 1: compenso complessivo non inferiore a 811,35
        r = _call("compenso_curatore_fallimentare", attivo_realizzato=1000.0, passivo_accertato=0.0)
        assert r["totale_compenso"] == pytest.approx(811.35)
        assert r["totale_compenso_min"] == pytest.approx(811.35)
        assert r["totale_compenso_max"] == pytest.approx(811.35)

    def test_minimo_sul_totale_attivo_e_passivo(self):
        # attivo 5.000 (12-14% = 600-700) + passivo 10.000 (0,19-0,94% = 19-94) = 619-794 < 811,35
        r = _call("compenso_curatore_fallimentare", attivo_realizzato=5_000.0, passivo_accertato=10_000.0)
        assert r["totale_prima_dei_limiti"] == pytest.approx(650.0 + 56.5)
        assert r["totale_compenso"] == pytest.approx(811.35)

    def test_procedura_media_forbice_art_1(self):
        # Hand computed from art. 1 c. 1 (attivo 100.000): 12-14% on 16.227,08; 10-12% on 8.113,54;
        # 8,5-9,5% on 16.227,06; 7-8% on 40.567,70; 5,5-6,5% on 18.864,62 => 8.015,19 - 9.258,60.
        # art. 1 c. 2 (passivo 200.000): 0,19-0,94% on 81.131,38; 0,06-0,46% on 118.868,62 => 225,47 - 1.309,43.
        r = _call("compenso_curatore_fallimentare", attivo_realizzato=100_000.0, passivo_accertato=200_000.0)
        assert r["totale_compenso_min"] == pytest.approx(8_240.66)
        assert r["totale_compenso_max"] == pytest.approx(10_568.03)
        assert r["totale_compenso_min"] <= r["totale_compenso"] <= r["totale_compenso_max"]
        assert r["compenso_su_attivo"] > 0
        assert r["compenso_su_passivo"] > 0

    def test_nessun_massimo_complessivo(self):
        # The decree has no overall ceiling (only the art. 4 minimum): 0,45-0,90% beyond 2.434.061,37
        r = _call("compenso_curatore_fallimentare", attivo_realizzato=100_000_000.0, passivo_accertato=0.0)
        assert r["totale_compenso_max"] > 405_656.80
        assert "massimo" not in r

    def test_dettaglio_attivo_presente(self):
        r = _call("compenso_curatore_fallimentare", attivo_realizzato=50_000.0, passivo_accertato=20_000.0)
        assert isinstance(r["dettaglio_attivo"], list)
        assert len(r["dettaglio_attivo"]) >= 1

    def test_passivo_zero(self):
        r = _call("compenso_curatore_fallimentare", attivo_realizzato=50_000.0, passivo_accertato=0.0)
        assert r["compenso_su_passivo"] == 0.0

    def test_valori_negativi(self):
        assert "errore" in _call("compenso_curatore_fallimentare", attivo_realizzato=-1.0, passivo_accertato=0.0)

    def test_struttura_output(self):
        r = _call("compenso_curatore_fallimentare", attivo_realizzato=10_000.0, passivo_accertato=5_000.0)
        for k in ("attivo_realizzato", "passivo_accertato", "compenso_su_attivo", "compenso_su_passivo", "totale_compenso"):
            assert k in r

    def test_primo_scaglione_forbice(self):
        # art. 1 c. 1 lett. a: 12-14% up to 16.227,08 => 1.947,25 - 2.271,79 (medio 2.109,52)
        r = _call("compenso_curatore_fallimentare", attivo_realizzato=16_227.08, passivo_accertato=0.0)
        assert r["totale_compenso_min"] == pytest.approx(1_947.25, abs=0.01)
        assert r["totale_compenso_max"] == pytest.approx(2_271.79, abs=0.01)
        assert r["totale_compenso"] == pytest.approx(2_109.52, abs=0.01)

    def test_confine_scaglioni_art_1(self):
        # attivo 81.135,38 (top of lett. d) and passivo 81.131,38 (top of c. 2 first bracket):
        # attivo 6.977,64 - 8.032,40 and passivo 154,15 - 762,63 => 7.131,79 - 8.795,03
        r = _call("compenso_curatore_fallimentare", attivo_realizzato=81_135.38, passivo_accertato=81_131.38)
        assert r["totale_compenso_min"] == pytest.approx(7_131.79)
        assert r["totale_compenso_max"] == pytest.approx(8_795.03)

    def test_procedura_grande_scaglioni_alti(self):
        # attivo 3.000.000 (58.205,59 - 83.713,64) + passivo 5.000.000 (3.105,47 - 23.389,43)
        r = _call("compenso_curatore_fallimentare", attivo_realizzato=3_000_000.0, passivo_accertato=5_000_000.0)
        assert r["totale_compenso_min"] == pytest.approx(61_311.06)
        assert r["totale_compenso_max"] == pytest.approx(107_103.07)

    def test_spese_generali_5_per_cento(self):
        # art. 4 c. 2: 5% general expenses on the compenso
        r = _call("compenso_curatore_fallimentare", attivo_realizzato=1000.0, passivo_accertato=0.0)
        assert r["spese_generali_5pct"] == pytest.approx(40.57)


# ---------------------------------------------------------------------------
# compenso_delegati_vendite
# ---------------------------------------------------------------------------


class TestCompensoDelegatiVendite:
    # DM 227/2015 art. 2 c. 1: fixed amount per phase (4 phases), by price bracket.
    def test_primo_scaglione_importo_fisso(self):
        # art. 2 c. 1 lett. a: 4 x 1.000 = 4.000; 40% cap = 16.000, not binding
        r = _call("compenso_delegati_vendite", prezzo_aggiudicazione=40_000.0)
        assert r["compenso"] == pytest.approx(4_000.0)
        assert r["spese_generali_10pct"] == pytest.approx(400.0)
        assert r["limite_applicato"] is False

    def test_esatto_100k_resta_nel_primo_scaglione(self):
        # "pari o inferiore a euro 100.000" (art. 2 c. 1 lett. a)
        r = _call("compenso_delegati_vendite", prezzo_aggiudicazione=100_000.0)
        assert r["compenso"] == pytest.approx(4_000.0)

    def test_primo_centesimo_secondo_scaglione(self):
        # art. 2 c. 1 lett. b: 4 x 1.500 = 6.000
        r = _call("compenso_delegati_vendite", prezzo_aggiudicazione=100_000.01)
        assert r["compenso"] == pytest.approx(6_000.0)

    def test_500k_secondo_scaglione_e_terzo(self):
        assert _call("compenso_delegati_vendite", prezzo_aggiudicazione=500_000.0)["compenso"] == pytest.approx(6_000.0)
        # art. 2 c. 1 lett. c: 4 x 2.000 = 8.000
        r = _call("compenso_delegati_vendite", prezzo_aggiudicazione=600_000.0)
        assert r["compenso"] == pytest.approx(8_000.0)
        assert r["spese_generali_10pct"] == pytest.approx(800.0)

    def test_tetto_40_per_cento_soglia_esatta(self):
        # art. 2 c. 5: compenso + spese generali 4.400 = 40% of 11.000, not exceeded
        r = _call("compenso_delegati_vendite", prezzo_aggiudicazione=11_000.0)
        assert r["compenso"] == pytest.approx(4_000.0)
        assert r["limite_applicato"] is False

    def test_tetto_40_per_cento_applicato(self):
        # art. 2 c. 5: cap 4.000 on compenso + 10%; 4.000 / 1,10 = 3.636,36 + 363,64
        r = _call("compenso_delegati_vendite", prezzo_aggiudicazione=10_000.0)
        assert r["limite_applicato"] is True
        assert r["compenso"] == pytest.approx(3_636.36)
        assert r["spese_generali_10pct"] == pytest.approx(363.64)

    def test_quota_aggiudicatario(self):
        # art. 2 c. 7: half of the transfer phase (1.500 in the 100-500k bracket) plus 10% general expenses
        r = _call("compenso_delegati_vendite", prezzo_aggiudicazione=200_000.0)
        assert r["compenso"] == pytest.approx(6_000.0)
        assert r["quota_a_carico_aggiudicatario"] == pytest.approx(825.0)  # 1.500 / 2 * 1,10

    def test_beni_mobili_registrati(self):
        # art. 3 c. 1: 200 + 250 + 200 + 250 = 900; c. 2 doubles it between 25.000 and 40.000
        assert _call("compenso_delegati_vendite", prezzo_aggiudicazione=20_000.0, tipo_vendita="mobili_registrati")["compenso"] == pytest.approx(900.0)
        r = _call("compenso_delegati_vendite", prezzo_aggiudicazione=30_000.0, tipo_vendita="mobili_registrati")
        assert r["compenso"] == pytest.approx(1_800.0)
        assert r["spese_generali_10pct"] == pytest.approx(180.0)

    def test_beni_mobili_tetto_30_per_cento(self):
        # art. 3 c. 5: cap 30% of 2.000 = 600; 600 / 1,10 = 545,45 + 54,55
        r = _call("compenso_delegati_vendite", prezzo_aggiudicazione=2_000.0, tipo_vendita="mobili_registrati")
        assert r["limite_applicato"] is True
        assert r["compenso"] == pytest.approx(545.45)

    def test_beni_mobili_oltre_40k_si_applica_art_2(self):
        # art. 3 c. 4: above 40.000 the criteria of art. 2 c. 1 lett. a apply (4 x 1.000)
        r = _call("compenso_delegati_vendite", prezzo_aggiudicazione=50_000.0, tipo_vendita="mobili_registrati")
        assert r["compenso"] == pytest.approx(4_000.0)

    def test_tipo_vendita_non_valido(self):
        assert "errore" in _call("compenso_delegati_vendite", prezzo_aggiudicazione=1_000.0, tipo_vendita="x")

    def test_output_keys(self):
        r = _call("compenso_delegati_vendite", prezzo_aggiudicazione=200_000.0)
        assert "compenso" in r
        assert "percentuale_effettiva" in r
        assert "fasi" in r

    def test_percentuale_effettiva_presente(self):
        r = _call("compenso_delegati_vendite", prezzo_aggiudicazione=300_000.0)
        assert r["percentuale_effettiva"] > 0


# ---------------------------------------------------------------------------
# compenso_mediatore_familiare
# ---------------------------------------------------------------------------


class TestCompensoMediatoreFamiliare:
    def test_solo_incontro_informativo(self):
        r = _call("compenso_mediatore_familiare", n_incontri=1)
        assert r["incontri_a_pagamento"] == 0
        assert r["compenso_totale"] == 0.0

    def test_percorso_standard(self):
        r = _call("compenso_mediatore_familiare", n_incontri=10, tariffa_incontro=120.0)
        assert r["incontri_a_pagamento"] == 9
        assert r["compenso_totale"] == pytest.approx(1080.0)

    def test_tariffa_personalizzata(self):
        r = _call("compenso_mediatore_familiare", n_incontri=5, tariffa_incontro=150.0)
        assert r["compenso_totale"] == pytest.approx(600.0)

    def test_n_incontri_zero(self):
        r = _call("compenso_mediatore_familiare", n_incontri=0)
        assert "errore" in r

    def test_n_incontri_negativo(self):
        r = _call("compenso_mediatore_familiare", n_incontri=-3)
        assert "errore" in r

    def test_output_keys(self):
        r = _call("compenso_mediatore_familiare", n_incontri=6)
        for k in ("n_incontri_totali", "incontri_a_pagamento", "compenso_totale"):
            assert k in r

    def test_primo_incontro_gratuito_label(self):
        r = _call("compenso_mediatore_familiare", n_incontri=3)
        assert r["primo_incontro"] == "gratuito (informativo)"

    # DM 27/10/2023 n. 151 art. 8: 40 euro per meeting and per party (c. 4), x 1 / 1,5 / 2 (c. 5),
    # plus 21% flat expenses on the compenso (c. 6) which the compenso does not include (c. 1).
    def test_default_parametri_dm_media_due_parti(self):
        # 4 paid meetings x 40 x 1,5 x 2 parties = 480; 21% = 100,80; imponibile 580,80
        r = _call("compenso_mediatore_familiare", n_incontri=5)
        assert r["compenso_totale"] == pytest.approx(480.0)
        assert r["spese_forfettarie_21pct"] == pytest.approx(100.80)
        assert r["totale_imponibile"] == pytest.approx(580.80)

    def test_complessita_bassa_e_alta(self):
        # 4 x 40 x 1 x 2 = 320 (+21% = 387,20); 4 x 40 x 2 x 2 = 640 (+21% = 774,40)
        bassa = _call("compenso_mediatore_familiare", n_incontri=5, complessita="bassa")
        alta = _call("compenso_mediatore_familiare", n_incontri=5, complessita="alta")
        assert bassa["compenso_totale"] == pytest.approx(320.0)
        assert bassa["totale_imponibile"] == pytest.approx(387.20)
        assert alta["compenso_totale"] == pytest.approx(640.0)
        assert alta["totale_imponibile"] == pytest.approx(774.40)

    def test_compenso_per_mediando(self):
        # art. 8 c. 4: the amount is owed by each party: 240 each on 4 meetings, media
        r = _call("compenso_mediatore_familiare", n_incontri=5)
        assert r["compenso_per_mediando"] == pytest.approx(240.0)

    def test_tariffa_libera_sostituisce_il_decreto(self):
        r = _call("compenso_mediatore_familiare", n_incontri=5, tariffa_incontro=100.0)
        assert r["compenso_totale"] == pytest.approx(400.0)
        assert "libera" in r["fonte_tariffa"]

    def test_complessita_non_valida(self):
        assert "errore" in _call("compenso_mediatore_familiare", n_incontri=3, complessita="x")


# ---------------------------------------------------------------------------
# fattura_enasarco
# ---------------------------------------------------------------------------


class TestFatturaEnasarco:
    def test_monocommittente_base(self):
        r = _call("fattura_enasarco", provvigioni=1000.0)
        assert r["tipo_agente"] == "monocommittente"
        enasarco = r["contributo_enasarco"]
        assert enasarco["contributo_totale"] == pytest.approx(170.0)
        assert enasarco["quota_agente"] == pytest.approx(85.0)
        assert enasarco["quota_preponente"] == pytest.approx(85.0)

    def test_pluricommittente(self):
        r = _call("fattura_enasarco", provvigioni=2000.0, tipo_agente="pluricommittente")
        assert r["tipo_agente"] == "pluricommittente"
        assert "errore" not in r

    def test_iva_22pct(self):
        r = _call("fattura_enasarco", provvigioni=1000.0)
        assert r["iva_22pct"] == pytest.approx(220.0)

    def test_ritenuta_23pct_su_50pct(self):
        r = _call("fattura_enasarco", provvigioni=1000.0)
        assert r["ritenuta_acconto"]["base"] == pytest.approx(500.0)
        assert r["ritenuta_acconto"]["aliquota"] == pytest.approx(23.0)
        assert r["ritenuta_acconto"]["importo"] == pytest.approx(115.0)

    def test_totale_fattura(self):
        r = _call("fattura_enasarco", provvigioni=1000.0)
        assert r["totale_fattura"] == pytest.approx(1220.0)

    def test_tipo_non_valido(self):
        r = _call("fattura_enasarco", provvigioni=1000.0, tipo_agente="dipendente")
        assert "errore" in r

    def test_output_keys(self):
        r = _call("fattura_enasarco", provvigioni=500.0)
        for k in ("contributo_enasarco", "iva_22pct", "ritenuta_acconto", "totale_fattura", "netto_a_pagare"):
            assert k in r

    def test_massimale_monomandatario_2026(self):
        # Enasarco RAI art. 5: the contribution is due up to the annual ceiling per agency
        # relationship (2026 monomandatario: 45.717 euro, enasarco.it). 50.000 euro of commissions:
        # 45.717 x 8,5% = 3.885,945 -> 3.885,95 agent share (half cent up); the 4.283 euro above
        # the ceiling carries no contribution. Net = 61.000 - 5.750 (23% x 50% x 50.000) - 3.885,95.
        r = _call("fattura_enasarco", provvigioni=50_000.0, tipo_agente="monocommittente", anno=2026)
        e = r["contributo_enasarco"]
        assert e["provvigioni_soggette_a_contributo"] == pytest.approx(45_717.0)
        assert e["provvigioni_oltre_massimale"] == pytest.approx(4_283.0)
        assert e["quota_agente"] == pytest.approx(3_885.95)
        assert e["contributo_totale"] == pytest.approx(7_771.89)
        assert r["ritenuta_acconto"]["importo"] == pytest.approx(5_750.0)
        assert r["totale_fattura"] == pytest.approx(61_000.0)
        assert r["netto_a_pagare"] == pytest.approx(51_364.05)

    def test_massimale_plurimandatario_2026(self):
        # Same rule, plurimandatario ceiling 30.478 euro: 30.478 x 8,5% = 2.590,63 agent share.
        r = _call("fattura_enasarco", provvigioni=40_000.0, tipo_agente="pluricommittente", anno=2026)
        e = r["contributo_enasarco"]
        assert e["massimale_annuo"] == pytest.approx(30_478.0)
        assert e["minimale_annuo"] == pytest.approx(515.0)
        assert e["quota_agente"] == pytest.approx(2_590.63)

    def test_massimale_residuo_con_provvigioni_gia_fatturate(self):
        # The ceiling is annual and not divisible (RAI art. 5 co. 1): with 40.000 already invoiced
        # to a monomandatario, only 5.717 euro of a new invoice enter the ceiling.
        r = _call(
            "fattura_enasarco", provvigioni=10_000.0, tipo_agente="monocommittente",
            provvigioni_gia_fatturate_anno=40_000.0,
        )
        assert r["contributo_enasarco"]["provvigioni_soggette_a_contributo"] == pytest.approx(5_717.0)
        assert r["contributo_enasarco"]["quota_agente"] == pytest.approx(485.95)  # 5.717 x 8,5% = 485,945

    def test_aliquota_2019_16_50(self):
        # RAI art. 4 co. 2 (delibera CdA 73/2012): 16,50% in 2019, 8,25% agent share.
        r = _call("fattura_enasarco", provvigioni=1000.0, anno=2019)
        assert r["contributo_enasarco"]["aliquota_totale"] == pytest.approx(16.5)
        assert r["contributo_enasarco"]["quota_agente"] == pytest.approx(82.5)
        assert r["netto_a_pagare"] == pytest.approx(1_022.5)

    def test_anno_prima_del_2012_rifiutato(self):
        assert "errore" in _call("fattura_enasarco", provvigioni=1000.0, anno=2011)

    def test_ritenuta_20pct_con_collaboratori(self):
        # Art. 25-bis co. 2 DPR 600/1973: 20% (not 50%) of the commissions when the agent declares
        # a continuous use of employees or third parties: 23% x 20% x 10.000 = 460.
        r = _call("fattura_enasarco", provvigioni=10_000.0, agente_con_collaboratori=True)
        assert r["ritenuta_acconto"]["base"] == pytest.approx(2_000.0)
        assert r["ritenuta_acconto"]["importo"] == pytest.approx(460.0)
        assert r["netto_a_pagare"] == pytest.approx(10_890.0)

    def test_arrotondamento_mezzo_centesimo_per_eccesso(self):
        # 23% x 50% x 45.717 = 5.257,455 -> 5.257,46; 22% x 1.234,75 = 271,645 -> 271,65 (half up,
        # not the binary-float round() that gave ...,45 and ...,64).
        assert _call("fattura_enasarco", provvigioni=45_717.0)["ritenuta_acconto"]["importo"] == pytest.approx(5_257.46)
        assert _call("fattura_enasarco", provvigioni=1_234.75)["iva_22pct"] == pytest.approx(271.65)


# ---------------------------------------------------------------------------
# ricevuta_prestazione_occasionale
# ---------------------------------------------------------------------------


class TestRicevutaPrestazioneOccasionale:
    def test_ricevuta_sopra_soglia_bollo(self):
        r = _call(
            "ricevuta_prestazione_occasionale",
            compenso_lordo=500.0,
            committente="Azienda SRL",
            prestatore="Mario Rossi",
            descrizione="Consulenza informatica",
        )
        assert r["calcoli"]["ritenuta_acconto_20pct"] == pytest.approx(100.0)
        assert r["calcoli"]["netto_a_pagare"] == pytest.approx(400.0)
        assert r["calcoli"]["bollo"] == 2.0
        assert "bollo" in r["testo_ricevuta"].lower()

    def test_ricevuta_sotto_soglia_bollo(self):
        r = _call(
            "ricevuta_prestazione_occasionale",
            compenso_lordo=50.0,
            committente="Privato",
            prestatore="Luigi Verdi",
            descrizione="Ripetizioni",
        )
        assert r["calcoli"]["bollo"] == 0.0
        assert "bollo" not in r["testo_ricevuta"].lower()

    def test_testo_contiene_committente_e_prestatore(self):
        r = _call(
            "ricevuta_prestazione_occasionale",
            compenso_lordo=200.0,
            committente="Studio ABC",
            prestatore="Anna Bianchi",
            descrizione="Servizio",
        )
        assert "Studio ABC" in r["testo_ricevuta"]
        assert "Anna Bianchi" in r["testo_ricevuta"]

    def test_output_keys(self):
        r = _call(
            "ricevuta_prestazione_occasionale",
            compenso_lordo=100.0,
            committente="X",
            prestatore="Y",
            descrizione="Z",
        )
        for k in ("testo_ricevuta", "calcoli", "committente", "prestatore"):
            assert k in r

    def test_compenso_esattamente_77_47(self):
        r = _call(
            "ricevuta_prestazione_occasionale",
            compenso_lordo=77.47,
            committente="A",
            prestatore="B",
            descrizione="C",
        )
        assert r["calcoli"]["bollo"] == 0.0

    def test_ritenuta_e_netto_corretti(self):
        r = _call(
            "ricevuta_prestazione_occasionale",
            compenso_lordo=1234.56,
            committente="Cliente",
            prestatore="Professionista",
            descrizione="Attività varia",
        )
        calcoli = r["calcoli"]
        assert calcoli["ritenuta_acconto_20pct"] + calcoli["netto_a_pagare"] == pytest.approx(calcoli["compenso_lordo"])

    def test_inps_gestione_separata_oltre_franchigia_2026(self):
        # Art. 44 co. 2 DL 269/2003: contribution only on the excess over 5.000 euro a year.
        # INPS circular 8/2026, type 09 (occasional self-employed): 33,72%; 1/3 on the worker
        # (circular par. 4.1). 6.000 euro: excess 1.000 x 33,72% = 337,20; worker 1/3 = 112,40;
        # withholding 20% x 6.000 = 1.200; net = 6.000 - 1.200 - 112,40 = 4.687,60.
        r = _call(
            "ricevuta_prestazione_occasionale",
            compenso_lordo=6000.0, committente="Beta", prestatore="Luca", descrizione="Consulenza",
        )
        inps = r["calcoli"]["inps_gestione_separata"]
        assert inps["aliquota"] == pytest.approx(33.72)
        assert inps["base_contributiva"] == pytest.approx(1000.0)
        assert inps["quota_prestatore_1_3"] == pytest.approx(112.40)
        assert inps["quota_committente_2_3"] == pytest.approx(224.80)
        assert r["calcoli"]["ritenuta_acconto_20pct"] == pytest.approx(1200.0)
        assert r["calcoli"]["netto_a_pagare"] == pytest.approx(4687.60)
        assert "112,40" in r["testo_ricevuta"]  # Italian number format

    def test_inps_franchigia_esatta_5000_nessun_contributo(self):
        r = _call(
            "ricevuta_prestazione_occasionale",
            compenso_lordo=5000.0, committente="Beta", prestatore="Luca", descrizione="Consulenza",
        )
        assert r["calcoli"]["inps_gestione_separata"]["quota_prestatore_1_3"] == 0.0
        assert r["calcoli"]["netto_a_pagare"] == pytest.approx(4000.0)

    def test_inps_franchigia_cumulativa_sui_compensi_gia_percepiti(self):
        # 4.000 already received in the year: 1.000 of the 5.000 franchigia is left, so of a new
        # 2.000 the excess is 1.000 -> 33,72% x 1.000 / 3 = 112,40 (the franchigia is annual and
        # cumulative across committenti).
        r = _call(
            "ricevuta_prestazione_occasionale",
            compenso_lordo=2000.0, committente="Beta", prestatore="Luca", descrizione="Consulenza",
            compensi_occasionali_gia_percepiti_anno=4000.0,
        )
        assert r["calcoli"]["inps_gestione_separata"]["base_contributiva"] == pytest.approx(1000.0)
        assert r["calcoli"]["inps_gestione_separata"]["quota_prestatore_1_3"] == pytest.approx(112.40)

    def test_inps_un_euro_oltre_franchigia(self):
        # 1 euro of excess: 33,72% x 1 / 3 = 0,1124 -> 0,11; net = 5.001 - 1.000,20 - 0,11 = 4.000,69.
        r = _call(
            "ricevuta_prestazione_occasionale",
            compenso_lordo=5001.0, committente="Beta", prestatore="Luca", descrizione="Consulenza",
        )
        assert r["calcoli"]["inps_gestione_separata"]["quota_prestatore_1_3"] == pytest.approx(0.11)
        assert r["calcoli"]["netto_a_pagare"] == pytest.approx(4000.69)

    def test_inps_aliquota_24_pensionato(self):
        # Circular 8/2026 / art. 1 co. 79 L. 247/2007: 24% for pensioners or workers insured elsewhere.
        # 6.000 euro: 1.000 x 24% / 3 = 80,00.
        r = _call(
            "ricevuta_prestazione_occasionale",
            compenso_lordo=6000.0, committente="Beta", prestatore="Luca", descrizione="Consulenza",
            altra_previdenza_o_pensionato=True,
        )
        assert r["calcoli"]["inps_gestione_separata"]["quota_prestatore_1_3"] == pytest.approx(80.0)

    def test_committente_non_sostituto_niente_ritenuta(self):
        # Art. 25 DPR 600/1973 binds only sostituti d'imposta: without one there is no withholding.
        r = _call(
            "ricevuta_prestazione_occasionale",
            compenso_lordo=1000.0, committente="Privato", prestatore="Luca", descrizione="Lezioni",
            committente_sostituto_imposta=False,
        )
        assert r["calcoli"]["ritenuta_acconto_20pct"] == 0.0
        assert r["calcoli"]["netto_a_pagare"] == pytest.approx(1000.0)

    def test_anno_senza_aliquote_tabulate_niente_quota_inps(self):
        r = _call(
            "ricevuta_prestazione_occasionale",
            compenso_lordo=6000.0, committente="Beta", prestatore="Luca", descrizione="Consulenza", anno=2024,
        )
        assert "inps_gestione_separata" not in r["calcoli"]
        assert any("Quota INPS non calcolata" in n for n in r["note"])


# ---------------------------------------------------------------------------
# tariffe_mediazione
# ---------------------------------------------------------------------------


class TestTariffeMediazione:
    # Reference: DM 150/2023 art. 28 co. 4-6, art. 30, Tabella A (see TestSpeseMediazione).
    def test_primo_scaglione(self):
        # 800 euro: avvio 40, primo 60; Tabella A 80-160 medio 120.
        r = _call("tariffe_mediazione", valore_controversia=800.0)
        assert r["spese_avvio_per_parte"] == 40
        assert r["spese_primo_incontro_per_parte"] == 60
        assert r["tabella_a"]["minimo"] == 80
        assert r["tabella_a"]["massimo"] == 160
        assert r["tabella_a"]["medio"] == 120

    def test_scenari_1000(self):
        # Art. 28 co. 6: negative at first meeting = 40 + 60 = 100, VAT 22, total 122.
        # Art. 30 co. 1: positive at first meeting = 166 (+10% on 60), total 202,52.
        # Art. 30 co. 2: positive after = 175 (+25% on 60), total 213,50.
        # Art. 30 co. 3: continued without agreement = 40 + 60 + 60 = 160, total 195,20.
        r = _call("tariffe_mediazione", valore_controversia=1000.0)
        assert r["esito_negativo"]["totale_per_parte"] == pytest.approx(122.0)
        assert r["esito_positivo"]["totale_per_parte"] == pytest.approx(202.52)
        assert r["esito_positivo_incontri_successivi"]["totale_per_parte"] == pytest.approx(213.50)
        assert r["esito_negativo_incontri_successivi"]["totale_per_parte"] == pytest.approx(195.20)

    def test_iva_anche_sulle_spese_di_avvio(self):
        # Art. 28 co. 2: the indennita' includes the avvio; VAT applies to the whole: 100 x 22% = 22.
        r = _call("tariffe_mediazione", valore_controversia=1000.0)
        neg = r["esito_negativo"]
        assert neg["indennita_per_parte"] == pytest.approx(100.0)
        assert neg["iva_22pct"] == pytest.approx(22.0)

    def test_scaglione_25000_50000(self):
        # 30.000 euro: avvio 75, primo 120, Tabella A 720-1.200 medio 960: positive first meeting
        # 75 + 120 + (960-120) x 1,10 = 1.119 -> 1.365,18 with VAT; negative 195 -> 237,90.
        r = _call("tariffe_mediazione", valore_controversia=30_000.0)
        assert r["tabella_a"]["medio"] == pytest.approx(960.0)
        assert r["esito_positivo"]["totale_per_parte"] == pytest.approx(1_365.18)
        assert r["esito_negativo"]["totale_per_parte"] == pytest.approx(237.90)

    def test_oltre_50000_avvio_110_primo_170(self):
        # 50.000,01 euro: avvio 110, primo 170; positive first meeting 1.925,16 (see spese_mediazione).
        r = _call("tariffe_mediazione", valore_controversia=50_000.01)
        assert r["spese_avvio_per_parte"] == 110
        assert r["spese_primo_incontro_per_parte"] == 170
        assert r["esito_positivo"]["totale_per_parte"] == pytest.approx(1_925.16)
        assert r["esito_negativo"]["totale_per_parte"] == pytest.approx(341.60)  # (110+170) x 1,22

    def test_scaglione_massimo(self):
        r = _call("tariffe_mediazione", valore_controversia=10_000_000.0)
        assert "oltre" in r["scaglione"]
        assert r["tabella_a"]["minimo"] == pytest.approx(20_000.0)  # 0,2% x 10.000.000
        assert r["tabella_a"]["massimo"] == pytest.approx(30_000.0)  # 0,3% x 10.000.000

    def test_tabella_completa_12_scaglioni(self):
        # Tabella A has 11 bounded brackets plus 'oltre 5.000.000'.
        r = _call("tariffe_mediazione", valore_controversia=5_000.0)
        assert isinstance(r["tabella_completa"], list)
        assert len(r["tabella_completa"]) == 12
        medi = [row["tabella_a_medio"] for row in r["tabella_completa"][:11]]
        assert medi == [120, 225, 365, 580, 960, 1_350, 2_000, 3_200, 4_250, 5_550, 8_250]

    def test_mediazione_obbligatoria(self):
        # Art. 28 co. 8: 1.000 euro reduced by one fifth: avvio 32, primo 48.
        r = _call("tariffe_mediazione", valore_controversia=1000.0, mediazione_obbligatoria=True)
        assert r["spese_avvio_per_parte"] == pytest.approx(32.0)
        assert r["spese_primo_incontro_per_parte"] == pytest.approx(48.0)
        assert r["esito_negativo"]["indennita_per_parte"] == pytest.approx(80.0)

    def test_totale_2_parti_doppio(self):
        r = _call("tariffe_mediazione", valore_controversia=1_000.0)
        pos = r["esito_positivo"]
        assert pos["totale_2_parti"] == pytest.approx(pos["totale_per_parte"] * 2)

    def test_note_e_agevolazioni_presenti(self):
        r = _call("tariffe_mediazione", valore_controversia=5_000.0)
        assert isinstance(r["note"], list)
        assert isinstance(r["agevolazioni"], list)

    def test_valore_non_valido(self):
        assert "errore" in _call("tariffe_mediazione", valore_controversia=0.0)

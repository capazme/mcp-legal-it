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
        assert any("Rivalsa" in n for n in voci_nomi)
        assert any("IVA" in n for n in voci_nomi)
        assert any("Ritenuta" in n for n in voci_nomi)

    def test_forfettario_bollo_esattamente_sulla_soglia(self):
        # base_imponibile_iva = 77.47 (not strictly greater) → no bollo
        # imponibile = 77.47 / 1.04 for ingegnere (rivalsa 4%) to get base == 77.47
        imponibile = round(77.47 / 1.04, 2)
        r = _call("fattura_professionista", imponibile=imponibile, tipo="ingegnere", regime="forfettario")
        assert r["bollo"] == 0.0


# ---------------------------------------------------------------------------
# compenso_ctu
# ---------------------------------------------------------------------------


class TestCompensoCtu:
    def test_perizia_immobiliare_per_valore(self):
        r = _call("compenso_ctu", tipo_incarico="perizia_immobiliare", valore_causa=200_000.0)
        assert "calcolo_a_percentuale" in r
        assert r["calcolo_a_percentuale"]["compenso_min"] == pytest.approx(1000.0)
        assert r["calcolo_a_percentuale"]["compenso_max"] == pytest.approx(4000.0)

    def test_perizia_contabile_per_ore(self):
        r = _call("compenso_ctu", tipo_incarico="perizia_contabile", ore_lavoro=10.0)
        assert "calcolo_orario" in r
        assert r["calcolo_orario"]["compenso_min"] == pytest.approx(700.0)
        assert r["calcolo_orario"]["compenso_max"] == pytest.approx(1300.0)

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
    def test_primo_scaglione_positivo(self):
        r = _call("spese_mediazione", valore_controversia=500.0, esito="positivo")
        assert r["indennita_per_parte"] == 120
        assert r["iva_22_per_parte"] == pytest.approx(26.40)
        assert r["totale_per_parte"] == pytest.approx(146.40)
        assert r["totale_organismo_2_parti"] == pytest.approx(292.80)

    def test_primo_scaglione_negativo(self):
        r = _call("spese_mediazione", valore_controversia=500.0, esito="negativo")
        assert r["indennita_per_parte"] == 60
        assert "nota_riduzione" in r

    def test_scaglione_medio(self):
        r = _call("spese_mediazione", valore_controversia=30_000.0, esito="positivo")
        assert r["indennita_per_parte"] == 720

    def test_scaglione_massimo(self):
        r = _call("spese_mediazione", valore_controversia=10_000_000.0, esito="positivo")
        assert r["indennita_per_parte"] == 5_600

    def test_esito_non_valido(self):
        r = _call("spese_mediazione", valore_controversia=1000.0, esito="invalido")
        assert "errore" in r

    def test_esito_negativo_riduzione_un_terzo(self):
        r = _call("spese_mediazione", valore_controversia=500.0, esito="negativo")
        assert "1/3" in r["nota_riduzione"]

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
        r = _call("compenso_curatore_fallimentare", attivo_realizzato=1000.0, passivo_accertato=0.0)
        assert r["totale_compenso"] == pytest.approx(811.31)

    def test_procedura_media(self):
        r = _call("compenso_curatore_fallimentare", attivo_realizzato=100_000.0, passivo_accertato=50_000.0)
        assert r["totale_compenso"] >= 811.31
        assert r["totale_compenso"] <= 405_656.80
        assert r["compenso_su_attivo"] > 0
        assert r["compenso_su_passivo"] > 0

    def test_massimale_non_superato(self):
        r = _call("compenso_curatore_fallimentare", attivo_realizzato=100_000_000.0, passivo_accertato=100_000_000.0)
        assert r["totale_compenso"] == pytest.approx(405_656.80)

    def test_dettaglio_attivo_presente(self):
        r = _call("compenso_curatore_fallimentare", attivo_realizzato=50_000.0, passivo_accertato=20_000.0)
        assert isinstance(r["dettaglio_attivo"], list)
        assert len(r["dettaglio_attivo"]) >= 1

    def test_passivo_zero(self):
        r = _call("compenso_curatore_fallimentare", attivo_realizzato=50_000.0, passivo_accertato=0.0)
        assert r["compenso_su_passivo"] == 0.0

    def test_struttura_output(self):
        r = _call("compenso_curatore_fallimentare", attivo_realizzato=10_000.0, passivo_accertato=5_000.0)
        for k in ("attivo_realizzato", "passivo_accertato", "compenso_su_attivo", "compenso_su_passivo", "totale_compenso"):
            assert k in r

    def test_compenso_attivo_progressivo_prima_fascia(self):
        # 16_227.08 * 14% = 2271.79
        r = _call("compenso_curatore_fallimentare", attivo_realizzato=16_227.08, passivo_accertato=0.0)
        assert r["compenso_su_attivo"] == pytest.approx(2271.79, abs=0.01)
        assert r["totale_compenso"] == pytest.approx(2271.79, abs=0.01)


# ---------------------------------------------------------------------------
# compenso_delegati_vendite
# ---------------------------------------------------------------------------


class TestCompensoDelegatiVendite:
    def test_sotto_100k_minimo_applicato(self):
        r = _call("compenso_delegati_vendite", prezzo_aggiudicazione=10_000.0)
        assert r["compenso"] == pytest.approx(1_100.0)

    def test_sotto_100k_normale(self):
        r = _call("compenso_delegati_vendite", prezzo_aggiudicazione=80_000.0)
        assert r["compenso"] == pytest.approx(2_080.0)

    def test_esatto_100k(self):
        r = _call("compenso_delegati_vendite", prezzo_aggiudicazione=100_000.0)
        assert r["compenso"] == pytest.approx(2_600.0)

    def test_seconda_fascia(self):
        r = _call("compenso_delegati_vendite", prezzo_aggiudicazione=300_000.0)
        expected = round(100_000 * 2.6 / 100 + 200_000 * 1.5 / 100, 2)
        assert r["compenso"] == pytest.approx(expected)

    def test_terza_fascia(self):
        r = _call("compenso_delegati_vendite", prezzo_aggiudicazione=700_000.0)
        expected = round(100_000 * 2.6 / 100 + 400_000 * 1.5 / 100 + 200_000 * 0.75 / 100, 2)
        assert r["compenso"] == pytest.approx(expected)

    def test_output_keys(self):
        r = _call("compenso_delegati_vendite", prezzo_aggiudicazione=200_000.0)
        assert "compenso" in r
        assert "percentuale_effettiva" in r
        assert "scaglioni" in r

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


# ---------------------------------------------------------------------------
# tariffe_mediazione
# ---------------------------------------------------------------------------


class TestTariffeMediazione:
    def test_primo_scaglione(self):
        r = _call("tariffe_mediazione", valore_controversia=800.0)
        assert r["esito_positivo"]["indennita_per_parte"] == 120
        assert r["esito_negativo"]["indennita_per_parte"] == 60
        assert r["spese_avvio_per_parte"] == 40

    def test_scaglione_25000(self):
        r = _call("tariffe_mediazione", valore_controversia=20_000.0)
        assert r["esito_positivo"]["indennita_per_parte"] == 480
        assert r["esito_negativo"]["indennita_per_parte"] == 240

    def test_scaglione_massimo(self):
        r = _call("tariffe_mediazione", valore_controversia=10_000_000.0)
        assert r["esito_positivo"]["indennita_per_parte"] == 5_600
        assert "oltre" in r["scaglione"]

    def test_tabella_completa_presente(self):
        r = _call("tariffe_mediazione", valore_controversia=5_000.0)
        assert isinstance(r["tabella_completa"], list)
        assert len(r["tabella_completa"]) == 10

    def test_totale_2_parti_doppio(self):
        r = _call("tariffe_mediazione", valore_controversia=1_000.0)
        pos = r["esito_positivo"]
        assert pos["totale_2_parti"] == pytest.approx(pos["totale_per_parte"] * 2)

    def test_iva_22pct_su_indennita(self):
        r = _call("tariffe_mediazione", valore_controversia=500.0)
        ind = r["esito_positivo"]["indennita_per_parte"]
        iva = r["esito_positivo"]["iva_22pct"]
        assert iva == pytest.approx(ind * 22 / 100)

    def test_totale_include_spese_avvio(self):
        r = _call("tariffe_mediazione", valore_controversia=500.0)
        ind = r["esito_positivo"]["indennita_per_parte"]
        iva = r["esito_positivo"]["iva_22pct"]
        avvio = r["spese_avvio_per_parte"]
        assert r["esito_positivo"]["totale_per_parte"] == pytest.approx(avvio + ind + iva)

    def test_note_e_agevolazioni_presenti(self):
        r = _call("tariffe_mediazione", valore_controversia=5_000.0)
        assert isinstance(r["note"], list)
        assert isinstance(r["agevolazioni"], list)

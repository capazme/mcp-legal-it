"""Hybrid tests for document generation tools: structural + arithmetic consistency."""

import re

from tests.comparison.conftest import assert_close


def _call_atti(fn_name, **kwargs):
    import importlib
    mod = importlib.import_module("src.tools.atti_giudiziari")
    fn = getattr(mod, fn_name)
    fn = getattr(fn, "fn", fn)
    return fn(**kwargs)


def _call_fatt(fn_name, **kwargs):
    import importlib
    mod = importlib.import_module("src.tools.fatturazione_avvocati")
    fn = getattr(mod, fn_name)
    fn = getattr(fn, "fn", fn)
    return fn(**kwargs)


def _call_riv(fn_name, **kwargs):
    import importlib
    mod = importlib.import_module("src.tools.rivalutazioni_istat")
    fn = getattr(mod, fn_name)
    fn = getattr(fn, "fn", fn)
    return fn(**kwargs)


def _call_parc(fn_name, **kwargs):
    import importlib
    mod = importlib.import_module("src.tools.parcelle_professionisti")
    fn = getattr(mod, fn_name)
    fn = getattr(fn, "fn", fn)
    return fn(**kwargs)


def _find_euro(text: str) -> list[float]:
    """Extract all Euro amounts from text (formats: Euro 1,234.56 or €1,234.56)."""
    # Match patterns like "Euro 15,000.00" or "€15,000.00"
    pattern = r'(?:Euro|€)\s*([\d,]+\.\d{2})'
    matches = re.findall(pattern, text)
    return [float(m.replace(",", "")) for m in matches]


# ============================================================================
# 1. Sollecito Pagamento
# ============================================================================

class TestSollecitoPagamento:

    def _make(self, **overrides):
        defaults = dict(
            creditore="Studio Legale Rossi", debitore="Bianchi S.r.l.",
            importo=15000, data_scadenza="2024-06-15", data_sollecito="2025-01-15",
        )
        defaults.update(overrides)
        return _call_atti("sollecito_pagamento", **defaults)

    def test_structural_elements(self):
        r = self._make()
        testo = r["testo_lettera"]
        assert "Bianchi S.r.l." in testo
        assert "Studio Legale Rossi" in testo
        assert "15/06/2024" in testo
        assert "Distinti saluti" in testo
        assert "vie legali" in testo

    def test_calcoli_correctness(self):
        r = self._make()
        c = r["calcoli"]
        assert c["importo_originale"] == 15000
        assert c["giorni_ritardo"] == 214
        assert_close(c["totale_dovuto"], c["importo_originale"] + c["interessi_mora"],
                     tolerance=0.01, label="soll_totale")

    def test_amounts_in_text_match_calcoli(self):
        r = self._make()
        testo = r["testo_lettera"]
        c = r["calcoli"]
        # The total and capital amounts must appear in the text
        assert f"{c['importo_originale']:,.2f}" in testo
        assert f"{c['totale_dovuto']:,.2f}" in testo
        assert f"{c['interessi_mora']:,.2f}" in testo

    def test_custom_tasso_mora(self):
        r = self._make(tasso_mora=8.0)
        c = r["calcoli"]
        assert c["tasso_mora_pct"] == 8.0
        expected = round(15000 * 8 / 100 * 214 / 366, 2)  # 2024 is leap year
        assert_close(c["interessi_mora"], expected, tolerance=0.01, label="soll_custom")

    def test_error_date_order(self):
        r = self._make(data_sollecito="2024-01-01")
        assert "errore" in r


# ============================================================================
# 2. Decreto Ingiuntivo
# ============================================================================

class TestDecretoIngiuntivo:

    def _make(self, **overrides):
        defaults = dict(
            creditore="Mario Rossi", debitore="Verdi S.p.A.", importo=25000,
            tipo_credito="ordinario", provvisoria_esecuzione=False,
        )
        defaults.update(overrides)
        return _call_atti("decreto_ingiuntivo", **defaults)

    def test_structural_sections(self):
        r = self._make()
        bozza = r["bozza_ricorso"]
        assert "RICORSO PER DECRETO INGIUNTIVO" in bozza
        assert "633" in bozza  # art. 633
        assert "ESPONE" in bozza
        assert "CHIEDE" in bozza
        assert "Procura alle liti" in bozza
        assert "Mario Rossi" in bozza
        assert "Verdi S.p.A." in bozza

    def test_competenza_gdp(self):
        r = self._make(importo=3000)
        assert r["riepilogo"]["giudice_competente"] == "Giudice di Pace"
        assert "GIUDICE DI PACE" in r["bozza_ricorso"]

    def test_competenza_gdp_soglia_10k(self):
        """D.Lgs. 116/2017: soglia GdP innalzata a €10.000."""
        r = self._make(importo=7000)
        assert r["riepilogo"]["giudice_competente"] == "Giudice di Pace"

    def test_competenza_tribunale(self):
        r = self._make(importo=25000)
        assert r["riepilogo"]["giudice_competente"] == "Tribunale"
        assert "TRIBUNALE" in r["bozza_ricorso"]

    def test_provvisoria_esecuzione_professionale(self):
        r = self._make(tipo_credito="professionale", provvisoria_esecuzione=True)
        bozza = r["bozza_ricorso"]
        assert "642" in bozza  # art. 642
        assert "parcella professionale" in bozza
        assert r["riepilogo"]["provvisoria_esecuzione"] is True

    def test_provvisoria_esecuzione_condominiale(self):
        r = self._make(tipo_credito="condominiale", provvisoria_esecuzione=True)
        assert "delibera assembleare" in r["bozza_ricorso"]

    def test_importo_in_text(self):
        r = self._make(importo=42000)
        assert "42,000.00" in r["bozza_ricorso"]
        assert r["riepilogo"]["importo"] == 42000

    def test_cu_calculated(self):
        r = self._make(importo=25000)
        assert r["riepilogo"]["contributo_unificato"] > 0


# ============================================================================
# 3. Fascicolo di Parte
# ============================================================================

class TestFascicoloDiParte:

    def test_structural_elements(self):
        r = _call_atti("fascicolo_di_parte",
                       avvocato="Avv. Bianchi", parte="Mario Rossi",
                       controparte="Luigi Verdi", tribunale="Tribunale di Milano",
                       rg_numero="12345/2025")
        testo = r["testo"]
        assert "TRIBUNALE DI MILANO" in testo
        assert "MARIO ROSSI" in testo
        assert "LUIGI VERDI" in testo
        assert "Avv. Bianchi" in testo
        assert "12345/2025" in testo
        assert "CONTRO" in testo
        assert "Procura alle liti" in testo

    def test_without_rg(self):
        r = _call_atti("fascicolo_di_parte",
                       avvocato="Avv. Bianchi", parte="Mario Rossi",
                       controparte="Luigi Verdi", tribunale="Tribunale di Roma")
        assert "___/____" in r["testo"]


# ============================================================================
# 4. Procura alle Liti
# ============================================================================

class TestProcuraAlleLiti:

    def _make(self, **overrides):
        defaults = dict(
            parte="Mario Rossi", avvocato="Marco Bianchi",
            cf_avvocato="BNCMRC80A01H501X", foro="Milano",
            oggetto_causa="Recupero credito", tipo="generale",
        )
        defaults.update(overrides)
        return _call_atti("procura_alle_liti", **defaults)

    def test_structural_generale(self):
        r = self._make(tipo="generale")
        testo = r["testo"]
        assert "PROCURA ALLE LITI" in testo
        assert "Mario Rossi" in testo
        assert "Marco Bianchi" in testo
        assert "BNCMRC80A01H501X" in testo
        assert "Milano" in testo
        assert "Recupero credito" in testo
        assert "GDPR" in testo or "2016/679" in testo

    def test_structural_speciale(self):
        r = self._make(tipo="speciale")
        testo = r["testo"]
        assert "SPECIALE" in testo
        assert "presente giudizio" in testo

    def test_structural_appello(self):
        r = self._make(tipo="appello")
        testo = r["testo"]
        assert "APPELLO" in testo

    def test_art_83(self):
        r = self._make()
        assert "83" in r["riferimento_normativo"]


# ============================================================================
# 5. Preventivo Civile
# ============================================================================

class TestPreventivoCivile:

    def _make(self, **overrides):
        defaults = dict(valore_causa=50000, livello="medio")
        defaults.update(overrides)
        return _call_fatt("preventivo_civile", **defaults)

    def test_structural_sections(self):
        r = self._make()
        testo = r["testo_preventivo"]
        assert "PREVENTIVO CAUSA CIVILE" in testo
        assert "COMPENSI PROFESSIONALI" in testo
        assert "SPESE VIVE STIMATE" in testo
        assert "TOTALE PREVENTIVO" in testo

    def test_arithmetic_consistency(self):
        r = self._make()
        d = r["dettaglio_calcoli"]
        # totale_compensi = sum of fasi
        assert_close(d["totale_compensi"], sum(f["importo"] for f in d["fasi"]),
                     tolerance=0.01, label="prev_comp")
        # spese_generali = 15% of compensi
        assert_close(d["spese_generali_15pct"], round(d["totale_compensi"] * 0.15, 2),
                     tolerance=0.01, label="prev_sg")
        # subtotale = compensi + sg
        assert_close(d["subtotale"], round(d["totale_compensi"] + d["spese_generali_15pct"], 2),
                     tolerance=0.01, label="prev_sub")
        # cpa = 4% of subtotale
        assert_close(d["cpa_4pct"], round(d["subtotale"] * 0.04, 2),
                     tolerance=0.01, label="prev_cpa")
        # iva = 22% of imponibile_iva
        assert_close(d["iva_22pct"], round(d["imponibile_iva"] * 0.22, 2),
                     tolerance=0.01, label="prev_iva")
        # totale_preventivo = totale_onorari + totale_spese_vive
        assert_close(d["totale_preventivo"],
                     round(d["totale_onorari"] + d["totale_spese_vive"], 2),
                     tolerance=0.01, label="prev_tot")

    def test_totale_in_text(self):
        r = self._make()
        d = r["dettaglio_calcoli"]
        testo = r["testo_preventivo"]
        assert f"{d['totale_preventivo']:,.2f}" in testo


# ============================================================================
# 6. Preventivo Stragiudiziale
# ============================================================================

class TestPreventivoStragiudiziale:

    def _make(self, **overrides):
        defaults = dict(valore_pratica=30000, livello="medio")
        defaults.update(overrides)
        return _call_fatt("preventivo_stragiudiziale", **defaults)

    def test_structural(self):
        r = self._make()
        testo = r["testo_preventivo"]
        assert "STRAGIUDIZIALE" in testo
        assert "TOTALE" in testo

    def test_arithmetic(self):
        r = self._make()
        d = r["dettaglio_calcoli"]
        assert_close(d["spese_generali_15pct"], round(d["compenso_base"] * 0.15, 2),
                     tolerance=0.01, label="strag_sg")
        assert_close(d["subtotale"], round(d["compenso_base"] + d["spese_generali_15pct"], 2),
                     tolerance=0.01, label="strag_sub")
        assert_close(d["cpa_4pct"], round(d["subtotale"] * 0.04, 2),
                     tolerance=0.01, label="strag_cpa")
        assert_close(d["totale"], round(d["imponibile_iva"] + d["iva_22pct"], 2),
                     tolerance=0.01, label="strag_tot")


# ============================================================================
# 7. Modello Notula
# ============================================================================

class TestModelloNotula:

    def _make(self, **overrides):
        defaults = dict(
            tipo_procedimento="decreto_ingiuntivo", avvocato="Marco Bianchi",
            cliente="Mario Rossi", valore_causa=30000, livello="medio",
        )
        defaults.update(overrides)
        return _call_fatt("modello_notula", **defaults)

    def test_structural_sections(self):
        r = self._make()
        testo = r["testo_notula"]
        assert "NOTULA" in testo
        assert "Marco Bianchi" in testo
        assert "Mario Rossi" in testo
        assert "COMPENSI PROFESSIONALI" in testo
        assert "SPESE VIVE" in testo
        assert "TOTALE NOTULA" in testo
        assert "DM 55/2014" in testo or "DM 147/2022" in testo

    def test_arithmetic(self):
        r = self._make()
        d = r["dettaglio_calcoli"]
        # compensi = sum of fasi
        assert_close(d["totale_compensi"], sum(f["importo"] for f in d["fasi"]),
                     tolerance=0.01, label="not_comp")
        # sg 15%
        assert_close(d["spese_generali_15pct"], round(d["totale_compensi"] * 0.15, 2),
                     tolerance=0.01, label="not_sg")
        # totale_notula = totale_onorari + totale_spese_vive
        assert_close(d["totale_notula"],
                     round(d["totale_onorari"] + d["totale_spese_vive"], 2),
                     tolerance=0.01, label="not_tot")

    def test_decreto_ingiuntivo_fasi(self):
        r = self._make(tipo_procedimento="decreto_ingiuntivo")
        fasi = [f["fase"] for f in r["dettaglio_calcoli"]["fasi"]]
        assert fasi == ["studio", "introduttiva"]

    def test_esecuzione_immobiliare_fasi(self):
        r = self._make(tipo_procedimento="esecuzione_immobiliare")
        fasi = [f["fase"] for f in r["dettaglio_calcoli"]["fasi"]]
        assert fasi == ["studio", "introduttiva", "istruttoria", "decisionale"]

    def test_totale_in_text(self):
        r = self._make()
        d = r["dettaglio_calcoli"]
        testo = r["testo_notula"]
        assert f"{d['totale_notula']:,.2f}" in testo


# ============================================================================
# 8. Lettera Adeguamento Canone
# ============================================================================

class TestLetteraAdeguamentoCanone:

    def _make(self, **overrides):
        defaults = dict(
            locatore="Giovanni Rossi", conduttore="Maria Bianchi",
            indirizzo_immobile="Via Roma 10, Milano",
            canone_attuale=800, data_stipula="2020-01-01",
            data_adeguamento="2024-01-01",
        )
        defaults.update(overrides)
        return _call_riv("lettera_adeguamento_canone", **defaults)

    def test_structural_elements(self):
        r = self._make()
        lettera = r["lettera"]
        assert "Maria Bianchi" in lettera
        assert "Giovanni Rossi" in lettera
        assert "Via Roma 10, Milano" in lettera
        assert "art. 32" in lettera
        assert "392/1978" in lettera
        assert "FOI" in lettera
        assert "Distinti saluti" in lettera

    def test_arithmetic(self):
        r = self._make()
        # variazione_applicata_pct is rounded to 2dp; canone_nuovo uses raw FOI values
        expected_nuovo = round(r["canone_attuale"] * (1 + r["variazione_applicata_pct"] / 100), 2)
        assert_close(r["canone_nuovo"], expected_nuovo, tolerance=0.05, label="lett_can")
        assert_close(r["aumento_mensile"], round(r["canone_nuovo"] - r["canone_attuale"], 2),
                     tolerance=0.01, label="lett_aum")

    def test_canone_in_text(self):
        r = self._make()
        lettera = r["lettera"]
        assert f"{r['canone_nuovo']:.2f}" in lettera
        assert f"{r['canone_attuale']:.2f}" in lettera

    def test_variazione_75_vs_100(self):
        r75 = self._make(percentuale_istat=75)
        r100 = self._make(percentuale_istat=100)
        assert r100["canone_nuovo"] > r75["canone_nuovo"]


# ============================================================================
# 9. Ricevuta Prestazione Occasionale
# ============================================================================

class TestRicevutaPrestazioneOccasionale:

    def _make(self, **overrides):
        defaults = dict(
            compenso_lordo=2000, committente="Azienda S.r.l.",
            prestatore="Luca Verdi", descrizione="Consulenza tecnica",
        )
        defaults.update(overrides)
        return _call_parc("ricevuta_prestazione_occasionale", **defaults)

    def test_structural_elements(self):
        r = self._make()
        testo = r["testo_ricevuta"]
        assert "RICEVUTA PER PRESTAZIONE OCCASIONALE" in testo
        assert "Luca Verdi" in testo
        assert "Azienda S.r.l." in testo
        assert "Consulenza tecnica" in testo
        assert "2222" in testo  # art. 2222 c.c.
        assert "fuori campo IVA" in testo

    def test_arithmetic(self):
        r = self._make()
        c = r["calcoli"]
        assert_close(c["ritenuta_acconto_20pct"], round(c["compenso_lordo"] * 0.20, 2),
                     tolerance=0.01, label="ric_rit")
        assert_close(c["netto_a_pagare"],
                     round(c["compenso_lordo"] - c["ritenuta_acconto_20pct"], 2),
                     tolerance=0.01, label="ric_net")

    def test_bollo_over_77(self):
        r = self._make(compenso_lordo=100)
        assert r["calcoli"]["bollo"] == 2.0

    def test_bollo_under_77(self):
        r = self._make(compenso_lordo=50)
        assert r["calcoli"]["bollo"] == 0.0

    def test_amounts_in_text(self):
        r = self._make()
        c = r["calcoli"]
        testo = r["testo_ricevuta"]
        assert f"{c['compenso_lordo']:,.2f}" in testo
        assert f"{c['ritenuta_acconto_20pct']:,.2f}" in testo
        assert f"{c['netto_a_pagare']:,.2f}" in testo


# ============================================================================
# 10. Diritti di Copia
# ============================================================================

class TestDirittiCopia:

    def _call(self, **kwargs):
        return _call_atti("diritti_copia", **kwargs)

    def test_digitale_semplice_gratuita(self):
        r = self._call(n_pagine=50, tipo="semplice", formato="digitale")
        assert r["totale"] == 0.0

    def test_digitale_autentica_forfettaria(self):
        r = self._call(n_pagine=10, tipo="autentica", formato="digitale")
        assert r["totale"] == 4.05

    def test_cartaceo_semplice(self):
        r = self._call(n_pagine=10, tipo="semplice", formato="cartaceo")
        assert_close(r["totale"], 3.0, tolerance=0.01, label="copia_cart")

    def test_cartaceo_urgente(self):
        r = self._call(n_pagine=10, tipo="semplice", formato="cartaceo", urgente=True)
        assert_close(r["totale"], 4.5, tolerance=0.01, label="copia_urg")

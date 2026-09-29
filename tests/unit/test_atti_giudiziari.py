"""Unit tests for src/tools/atti_giudiziari.py."""

import importlib

import pytest

from .mcp_harness import tool_body


def _call(fn_name, **kwargs):
    mod = importlib.import_module("src.tools.atti_giudiziari")
    return tool_body(getattr(mod, fn_name))(**kwargs)


# ---------------------------------------------------------------------------
# contributo_unificato
# ---------------------------------------------------------------------------


class TestContributoUnificato:

    def test_cognizione_primo_grado_scaglione_basso(self):
        r = _call("contributo_unificato", valore_causa=1000, tipo_procedimento="cognizione", grado="primo")
        assert r["importo_dovuto"] == 43
        assert r["moltiplicatore"] == 1.0

    def test_cognizione_primo_grado_scaglione_alto(self):
        # 30000 rientra nello scaglione fino_a=52000 → 518
        r = _call("contributo_unificato", valore_causa=30000, tipo_procedimento="cognizione", grado="primo")
        assert r["importo_dovuto"] == 518

    def test_monitorio_dimezzato(self):
        r = _call("contributo_unificato", valore_causa=5000, tipo_procedimento="monitorio", grado="primo")
        assert r["importo_dovuto"] == 49

    def test_esecuzione_immobiliare_fisso(self):
        r = _call("contributo_unificato", valore_causa=0, tipo_procedimento="esecuzione_immobiliare", grado="primo")
        assert r["importo_dovuto"] == 278

    def test_esecuzione_mobiliare_fisso(self):
        r = _call("contributo_unificato", valore_causa=0, tipo_procedimento="esecuzione_mobiliare", grado="primo")
        assert r["importo_dovuto"] == 43

    def test_esecuzione_mobiliare_oltre_2500(self):
        # art. 13, c. 2: fisso 139 per valore superiore o uguale a 2.500 euro
        r = _call("contributo_unificato", valore_causa=2500, tipo_procedimento="esecuzione_mobiliare", grado="primo")
        assert r["importo_dovuto"] == 139

    def test_separazione_consensuale_fisso(self):
        r = _call("contributo_unificato", valore_causa=0, tipo_procedimento="separazione_consensuale", grado="primo")
        assert r["importo_dovuto"] == 43

    def test_divorzio_giudiziale_fisso(self):
        r = _call("contributo_unificato", valore_causa=0, tipo_procedimento="divorzio_giudiziale", grado="primo")
        assert r["importo_dovuto"] == 98

    def test_cautelari_ridotti_per_valore(self):
        # I procedimenti cautelari sono ridotti del 50% degli scaglioni ordinari
        # per valore (art. 13, c. 2): 5.200 -> 98 * 0,5; 26.000 -> 237 * 0,5.
        r = _call("contributo_unificato", valore_causa=5200, tipo_procedimento="cautelari", grado="primo")
        assert r["importo_dovuto"] == 49
        r = _call("contributo_unificato", valore_causa=26000, tipo_procedimento="cautelari", grado="primo")
        assert r["importo_dovuto"] == 118.5

    def test_lavoro_primo_grado_esente(self):
        r = _call("contributo_unificato", valore_causa=50000, tipo_procedimento="lavoro", grado="primo")
        assert r["importo_dovuto"] == 0.0

    def test_tributario_scaglione(self):
        r = _call("contributo_unificato", valore_causa=10000, tipo_procedimento="tributario", grado="primo")
        assert r["importo_dovuto"] == 120

    def test_tar_fisso(self):
        r = _call("contributo_unificato", valore_causa=0, tipo_procedimento="tar", grado="primo")
        assert r["importo_dovuto"] == 650

    def test_appello_moltiplicatore(self):
        # 30000 → scaglione 518, appello × 1.5 = 777
        r = _call("contributo_unificato", valore_causa=30000, tipo_procedimento="cognizione", grado="appello")
        assert r["moltiplicatore"] == 1.5
        assert r["importo_dovuto"] == pytest.approx(518 * 1.5, abs=0.01)

    def test_cassazione_raddoppio(self):
        # 30000 → scaglione 518, cassazione × 2.0 = 1036
        r = _call("contributo_unificato", valore_causa=30000, tipo_procedimento="cognizione", grado="cassazione")
        assert r["moltiplicatore"] == 2.0
        assert r["importo_dovuto"] == pytest.approx(518 * 2.0, abs=0.01)

    def test_lavoro_appello_fascia_zero(self):
        r = _call("contributo_unificato", valore_causa=2000, tipo_procedimento="lavoro", grado="appello")
        assert r["importo_dovuto"] == 0

    def test_lavoro_esente_sotto_soglia_anche_in_appello(self):
        # Art. 9 co. 1-bis DPR 115/2002: esente fino a tre volte la soglia dell'art. 76
        r = _call("contributo_unificato", valore_causa=10000, tipo_procedimento="lavoro", grado="appello")
        assert r["importo_dovuto"] == 0
        assert r["reddito_oltre_soglia_lavoro"] is False

    def test_lavoro_oltre_soglia_meta_scaglione(self):
        # Oltre soglia: meta' dello scaglione ordinario (art. 13 co. 3): 237 / 2 in primo grado,
        # poi +50% in appello (co. 1-bis)
        r = _call("contributo_unificato", valore_causa=10000, tipo_procedimento="lavoro",
                  reddito_oltre_soglia_lavoro=True)
        assert r["importo_dovuto"] == 118.5
        r = _call("contributo_unificato", valore_causa=10000, tipo_procedimento="lavoro", grado="appello",
                  reddito_oltre_soglia_lavoro=True)
        assert r["importo_dovuto"] == 177.75

    def test_previdenza_oltre_soglia_43_euro(self):
        r = _call("contributo_unificato", valore_causa=100000, tipo_procedimento="previdenza",
                  reddito_oltre_soglia_lavoro=True)
        assert r["importo_dovuto"] == 43

    def test_tributario_appello_stessi_importi(self):
        # Art. 13 co. 6-quater: gli importi valgono per i ricorsi in primo e in secondo grado
        r = _call("contributo_unificato", valore_causa=50000, tipo_procedimento="tributario", grado="appello")
        assert r["importo_dovuto"] == 250

    def test_opposizione_decreto_ingiuntivo_meta(self):
        r = _call("contributo_unificato", valore_causa=20000, tipo_procedimento="opposizione_decreto_ingiuntivo")
        assert r["importo_dovuto"] == 118.5

    def test_opposizione_atti_esecutivi_fisso(self):
        r = _call("contributo_unificato", valore_causa=20000, tipo_procedimento="opposizione_atti_esecutivi")
        assert r["importo_dovuto"] == 168

    def test_valore_indeterminabile(self):
        assert _call("contributo_unificato", valore_causa=0, tipo_procedimento="valore_indeterminabile")["importo_dovuto"] == 518
        assert _call("contributo_unificato", valore_causa=0, tipo_procedimento="valore_indeterminabile_gdp")["importo_dovuto"] == 237

    def test_tipo_sconosciuto_rifiutato(self):
        r = _call("contributo_unificato", valore_causa=1000, tipo_procedimento="inesistente")
        assert "errore" in r and "valori_ammessi" in r

    def test_returns_normativo(self):
        r = _call("contributo_unificato", valore_causa=5000, tipo_procedimento="cognizione", grado="primo")
        assert "DPR 115/2002" in r["riferimento_normativo"]

    def test_oltre_soglia_massima(self):
        r = _call("contributo_unificato", valore_causa=1_000_000, tipo_procedimento="cognizione", grado="primo")
        assert r["importo_dovuto"] == 1686


# ---------------------------------------------------------------------------
# diritti_copia
# ---------------------------------------------------------------------------


class TestDirittiCopia:

    def test_digitale_semplice_gratuita(self):
        # Art. 269 co. 1-bis DPR 115/2002: no diritto for a plain copy taken from the fascicolo informatico
        r = _call("diritti_copia", n_pagine=10, tipo="semplice", formato="digitale")
        assert r["totale"] == 0.0

    def test_digitale_autentica_non_calcolata(self):
        # The digital authentic copy right is not established from a primary source (Annex 8 flat
        # 8.00 euro is for uncountable files; the D.I. 9.7.2021 table has per-page bands), so the
        # tool refuses rather than returning a probably wrong amount.
        for tipo in ("autentica", "esecutiva"):
            for n in (4, 10, 100):
                r = _call("diritti_copia", n_pagine=n, tipo=tipo, formato="digitale")
                assert "errore" in r and "non e' calcolato" in r["errore"]
                assert "totale" not in r

    def test_digitale_semplice_gratuita_anche_se_urgente(self):
        # Art. 269 co. 1-bis DPR 115/2002: no right for the plain copy taken from the electronic file
        r = _call("diritti_copia", n_pagine=8, tipo="semplice", formato="digitale", urgente=True)
        assert r["totale"] == 0.0

    def test_cartaceo_semplice_fasce(self):
        # Allegato 6 (D.I. 9 luglio 2021) + 50% (art. 4 co. 5 DL 193/2009): 0,98 -> 1,47 ... 15,72 -> 23,58
        attesi = {1: 1.47, 4: 1.47, 5: 2.96, 10: 2.96, 11: 5.88, 20: 5.88, 21: 11.79, 50: 11.79, 51: 23.58, 100: 23.58}
        for n, atteso in attesi.items():
            assert _call("diritti_copia", n_pagine=n, tipo="semplice", formato="cartaceo")["totale"] == atteso

    def test_cartaceo_semplice_oltre_100(self):
        # Allegato 6: 23,58 + 9,83 for each further 100 pages or fraction
        assert _call("diritti_copia", n_pagine=101, tipo="semplice", formato="cartaceo")["totale"] == 33.41
        assert _call("diritti_copia", n_pagine=200, tipo="semplice", formato="cartaceo")["totale"] == 33.41
        assert _call("diritti_copia", n_pagine=201, tipo="semplice", formato="cartaceo")["totale"] == 43.24

    def test_cartaceo_autentica_fasce(self):
        # Allegato 7 (copy + certification) + 50%: 7,86 -> 11,80 ; 9,18 -> 13,78 ; 10,47 -> 15,71
        attesi = {4: 11.80, 5: 13.78, 10: 13.78, 11: 15.71, 20: 15.71, 21: 19.66, 51: 29.48}
        for n, atteso in attesi.items():
            assert _call("diritti_copia", n_pagine=n, tipo="autentica", formato="cartaceo")["totale"] == atteso

    def test_cartaceo_esecutiva_come_autentica(self):
        r = _call("diritti_copia", n_pagine=3, tipo="esecutiva", formato="cartaceo")
        assert r["totale"] == 11.80

    def test_cartaceo_urgente_triplicato(self):
        # Art. 270 DPR 115/2002: release within two days, the right is tripled (not +50%)
        r = _call("diritti_copia", n_pagine=4, tipo="semplice", formato="cartaceo", urgente=True)
        assert r["totale"] == 4.41
        assert r["maggiorazione_urgenza"] == 2.94
        r = _call("diritti_copia", n_pagine=11, tipo="autentica", formato="cartaceo", urgente=True)
        assert r["totale"] == 47.13

    def test_formato_non_valido(self):
        r = _call("diritti_copia", n_pagine=10, tipo="semplice", formato="fax")
        assert "errore" in r

    def test_tipo_non_valido(self):
        r = _call("diritti_copia", n_pagine=10, tipo="notarile", formato="cartaceo")
        assert "errore" in r


# ---------------------------------------------------------------------------
# pignoramento_stipendio
# ---------------------------------------------------------------------------


class TestPignoramentoStipendio:

    def test_ordinario_un_quinto(self):
        r = _call("pignoramento_stipendio", stipendio_netto_mensile=2000, tipo_credito="ordinario")
        assert r["importo_pignorabile"] == pytest.approx(400.0, abs=0.01)
        assert r["quota_pignorabile"] == pytest.approx(0.2, abs=0.0001)

    def test_alimentare_un_terzo(self):
        r = _call("pignoramento_stipendio", stipendio_netto_mensile=3000, tipo_credito="alimentare")
        assert r["importo_pignorabile"] == pytest.approx(1000.0, abs=0.01)

    def test_fiscale_scaglione_basso(self):
        r = _call("pignoramento_stipendio", stipendio_netto_mensile=2000, tipo_credito="fiscale")
        assert r["importo_pignorabile"] == pytest.approx(200.0, abs=0.01)
        assert "1/10" in r["descrizione"]

    def test_fiscale_scaglione_medio(self):
        r = _call("pignoramento_stipendio", stipendio_netto_mensile=3500, tipo_credito="fiscale")
        assert r["importo_pignorabile"] == pytest.approx(3500 / 7, abs=0.01)
        assert "1/7" in r["descrizione"]

    def test_fiscale_scaglione_alto(self):
        r = _call("pignoramento_stipendio", stipendio_netto_mensile=6000, tipo_credito="fiscale")
        assert r["importo_pignorabile"] == pytest.approx(6000 / 5, abs=0.01)
        assert "1/5" in r["descrizione"]

    def test_concorso_crediti_meta(self):
        r = _call("pignoramento_stipendio", stipendio_netto_mensile=4000, tipo_credito="concorso_crediti")
        assert r["importo_pignorabile"] == pytest.approx(2000.0, abs=0.01)

    def test_non_pignorabile_complementare(self):
        r = _call("pignoramento_stipendio", stipendio_netto_mensile=2000, tipo_credito="ordinario")
        assert r["importo_non_pignorabile"] == pytest.approx(1600.0, abs=0.01)

    def test_tipo_invalido(self):
        r = _call("pignoramento_stipendio", stipendio_netto_mensile=2000, tipo_credito="speciale")
        assert "errore" in r

    def test_contiene_minimo_impignorabile_pensioni(self):
        r = _call("pignoramento_stipendio", stipendio_netto_mensile=1000, tipo_credito="ordinario")
        # Assegno sociale 2026: 546,24 euro/month (INPS circular 153 of 19/12/2025,
        # 7.101,12 / 13). Art. 545 co. 7 c.p.c.: twice the assegno sociale, minimum 1.000 euro.
        assert r["assegno_sociale_mensile"] == 546.24
        assert r["minimo_impignorabile_pensioni"] == 1092.48

    def test_pensione_quota_solo_sull_eccedenza(self):
        r = _call("pignoramento_stipendio", stipendio_netto_mensile=1500, tipo_credito="ordinario", pensione=True)
        # 1.500 - 2 x 546,24 = 407,52; 1/5 = 81,504 -> 81,50 (art. 545 co. 7 and 4 c.p.c.)
        assert r["base_di_calcolo"] == 407.52
        assert r["importo_pignorabile"] == 81.50
        assert "avvertenza" in r

    def test_arrotondamento_mezzo_centesimo_per_eccesso(self):
        # 1.107,53 - 1.092,48 = 15,05; 1/10 (art. 72-ter DPR 602/1973) = 1,505 -> 1,51.
        # Binary floats give 15,04999... and 1,50: the base is now computed in Decimal.
        r = _call("pignoramento_stipendio", stipendio_netto_mensile=1107.53, tipo_credito="fiscale",
                  pensione=True)
        assert r["base_di_calcolo"] == 15.05
        assert r["importo_pignorabile"] == 1.51
        assert r["importo_non_pignorabile"] == 1106.02

    def test_pensione_sotto_il_minimo_impignorabile(self):
        r = _call("pignoramento_stipendio", stipendio_netto_mensile=900, tipo_credito="ordinario", pensione=True)
        assert r["importo_pignorabile"] == 0.0

    def test_pensione_con_assegno_sociale_fornito(self):
        r = _call("pignoramento_stipendio", stipendio_netto_mensile=2000, pensione=True,
                  assegno_sociale_mensile=400.0)
        # 2 x 400 = 800 < 1.000: vale il minimo di legge
        assert r["minimo_impignorabile_pensioni"] == 1000.0
        assert r["importo_pignorabile"] == 200.0
        assert "avvertenza" not in r


# ---------------------------------------------------------------------------
# sollecito_pagamento
# ---------------------------------------------------------------------------


class TestSollecitoPagemento:

    def test_genera_testo(self):
        r = _call(
            "sollecito_pagamento",
            creditore="Rossi SRL",
            debitore="Bianchi SPA",
            importo=5000.0,
            data_scadenza="2024-01-01",
            data_sollecito="2024-04-01",
            tasso_mora=10.0,
        )
        assert "testo_lettera" in r
        assert "Bianchi SPA" in r["testo_lettera"]
        assert "Rossi SRL" in r["testo_lettera"]

    def test_calcoli_interessi_tasso_personalizzato(self):
        r = _call(
            "sollecito_pagamento",
            creditore="A",
            debitore="B",
            importo=10000.0,
            data_scadenza="2024-01-01",
            data_sollecito="2024-07-01",
            tasso_mora=10.0,
        )
        interessi = r["calcoli"]["interessi_mora"]
        assert interessi > 0
        assert r["calcoli"]["totale_dovuto"] == pytest.approx(10000 + interessi, abs=0.01)

    def test_tasso_mora_default(self):
        r = _call(
            "sollecito_pagamento",
            creditore="A",
            debitore="B",
            importo=1000.0,
            data_scadenza="2024-01-01",
            data_sollecito="2024-04-01",
        )
        assert r["calcoli"]["interessi_mora"] > 0
        assert r["calcoli"]["giorni_ritardo"] == 91

    def test_data_non_successiva_errore(self):
        r = _call(
            "sollecito_pagamento",
            creditore="A",
            debitore="B",
            importo=1000.0,
            data_scadenza="2024-06-01",
            data_sollecito="2024-01-01",
        )
        assert "errore" in r

    def test_stessa_data_errore(self):
        r = _call(
            "sollecito_pagamento",
            creditore="A",
            debitore="B",
            importo=1000.0,
            data_scadenza="2024-01-01",
            data_sollecito="2024-01-01",
        )
        assert "errore" in r

    @staticmethod
    def _soll(**kw):
        return _call("sollecito_pagamento", creditore="A", debitore="B", **kw)

    def test_regime_7_punti_scadenza_2012(self):
        # Art. 5 D.Lgs. 231/2002 in the text before D.Lgs. 192/2012 (art. 3 co. 1): BCE 1,00% + 7
        # points = 8,00% for a transaction concluded by 31/12/2012. 77 days (16/10-31/12/2012),
        # 2012 leap year: 5000 x 8% x 77 / 366 = 84,15.
        r = self._soll(importo=5000, data_scadenza="2012-10-15", data_sollecito="2012-12-31")
        assert r["calcoli"]["maggiorazione_punti"] == 7
        assert r["calcoli"]["tasso_mora_pct"] == 8.0
        assert r["calcoli"]["interessi_mora"] == pytest.approx(84.15, abs=0.01)

    def test_data_contratto_2012_scadenza_2013_usa_7_punti(self):
        # Art. 3 co. 1 D.Lgs. 192/2012: transaction concluded before 01/01/2013 keeps BCE + 7.
        # 91 days at 7,75% + 92 days at 7,50% on 10.000 (365-day year):
        # 193,22 + 189,04 = 382,26.
        r = self._soll(importo=10000, data_scadenza="2013-03-31", data_sollecito="2013-09-30",
                       data_contratto="2012-12-31")
        assert r["calcoli"]["interessi_mora"] == pytest.approx(382.26, abs=0.01)

    def test_senza_data_contratto_scadenza_2013_usa_8_punti(self):
        # Without a contract date, a 2013 due date is assumed to be a post-2012 transaction (8 points).
        r = self._soll(importo=10000, data_scadenza="2013-03-31", data_sollecito="2013-09-30")
        assert r["calcoli"]["maggiorazione_punti"] == 8
        assert r["calcoli"]["interessi_mora"] == pytest.approx(432.40, abs=0.01)

    def test_contratto_ante_agosto_2002_errore(self):
        # Art. 11 co. 1 D.Lgs. 231/2002: not applicable to contracts concluded before 08/08/2002.
        r = self._soll(importo=1000, data_scadenza="2002-10-01", data_sollecito="2002-12-01",
                       data_contratto="2002-08-07")
        assert "errore" in r

    def test_inizio_tabella_primo_giorno_di_mora(self):
        # Due 31/08/2002: first day of mora is 01/09/2002, covered by the table. BCE 3,35% + 7 =
        # 10,35% x 122 days (365-day year) on 10.000 = 345,95 (art. 5 original text).
        r = self._soll(importo=10000, data_scadenza="2002-08-31", data_sollecito="2002-12-31")
        assert "errore" not in r
        assert r["calcoli"]["interessi_mora"] == pytest.approx(345.95, abs=0.01)

    def test_oltre_fine_tabella_rifiuta(self):
        # Art. 5 co. 2: the rate for the first half of 2027 is the BCE rate at 01/01/2027, not
        # yet in the table: the tool refuses instead of silently counting 31 of 62 days.
        r = self._soll(importo=10000, data_scadenza="2026-11-30", data_sollecito="2027-01-31")
        assert "errore" in r
        assert "2026" in r["errore"]

    def test_tasso_convenzionale_divisore_per_anno(self):
        # Agreed rate 8,5% from 30/06/2024 to 30/06/2025 on 10.000, actual/actual by calendar
        # year: 184 days of 2024 (/366) + 181 days of 2025 (/365) = 427,32 + 421,51 = 848,83
        # (art. 1284 c.c.; no rule fixes the divisor, the tool uses each year's own length).
        r = self._soll(importo=10000, data_scadenza="2024-06-30", data_sollecito="2025-06-30",
                       tasso_mora=8.5)
        assert r["calcoli"]["interessi_mora"] == pytest.approx(848.83, abs=0.01)

    def test_lettera_importi_formato_italiano(self):
        r = self._soll(importo=10000, data_scadenza="2026-03-31", data_sollecito="2026-09-30")
        assert "Euro 10.000,00" in r["testo_lettera"]
        assert "10,000.00" not in r["testo_lettera"]

    def test_lettera_messa_in_mora_e_forfettario(self):
        # Art. 1219 c.c. (constitution in mora) and art. 6 co. 2 D.Lgs. 231/2002 (40 euro lump sum)
        r = self._soll(importo=10000, data_scadenza="2026-03-31", data_sollecito="2026-09-30")
        assert "messa in mora" in r["testo_lettera"]
        assert "40,00" in r["testo_lettera"]

    def test_forfettario_omesso_per_contratti_ante_2013(self):
        # Art. 6 co. 2 D.Lgs. 231/2002 (40 euro) comes from D.Lgs. 192/2012 art. 3, transactions concluded
        # from 1/1/2013: for a contract of 2010 (7-point regime) the lump sum is not due.
        r = self._soll(importo=10000, data_scadenza="2012-03-31", data_sollecito="2012-09-30",
                       data_contratto="2010-05-01")
        assert "40,00" not in r["testo_lettera"]


# ---------------------------------------------------------------------------
# decreto_ingiuntivo
# ---------------------------------------------------------------------------


class TestDecretoIngiuntivo:

    def test_importo_basso_giudice_pace(self):
        r = _call("decreto_ingiuntivo", creditore="A", debitore="B", importo=5000)
        assert r["riepilogo"]["giudice_competente"] == "Giudice di Pace"

    def test_importo_alto_tribunale(self):
        r = _call("decreto_ingiuntivo", creditore="A", debitore="B", importo=50000)
        assert r["riepilogo"]["giudice_competente"] == "Tribunale"

    def test_contributo_unificato_presente(self):
        r = _call("decreto_ingiuntivo", creditore="A", debitore="B", importo=5000)
        assert r["riepilogo"]["contributo_unificato"] > 0

    def test_provvisoria_esecuzione_professionale(self):
        r = _call(
            "decreto_ingiuntivo",
            creditore="A",
            debitore="B",
            importo=5000,
            tipo_credito="professionale",
            provvisoria_esecuzione=True,
        )
        assert r["riepilogo"]["provvisoria_esecuzione"] is True
        assert len(r["riepilogo"]["motivi_pe"]) == 1
        assert "parcella" in r["riepilogo"]["motivi_pe"][0]

    def test_parcella_non_e_titolo_art_642_co_1(self):
        # art. 636 c.p.c. (parere dell'Ordine) is the written proof; art. 642 co. 1 lists cambiale, assegni,
        # certificato di borsa, atti pubblici: the clause rests on art. 642 co. 2
        r = _call("decreto_ingiuntivo", creditore="A", debitore="B", importo=5000,
                  tipo_credito="professionale", provvisoria_esecuzione=True)
        motivo = r["riepilogo"]["motivi_pe"][0]
        assert "636" in motivo and "642 co. 2" in motivo and "642 co. 1" not in motivo

    def test_retribuzioni_cu_condizionato_art_9_co_1bis(self):
        # art. 9 co. 1-bis DPR 115/2002: labour credits pay the CU only above three times the art. 76 threshold
        r = _call("decreto_ingiuntivo", creditore="A", debitore="B", importo=8000, tipo_credito="retribuzioni")
        assert r["riepilogo"]["contributo_unificato"] == 0
        r = _call("decreto_ingiuntivo", creditore="A", debitore="B", importo=8000, tipo_credito="retribuzioni",
                  reddito_oltre_soglia_lavoro=True)
        assert r["riepilogo"]["contributo_unificato"] == pytest.approx(118.5, abs=0.01)  # 237 / 2, art. 13 co. 3

    def test_dichiarazione_di_valore_art_14(self):
        # art. 14 co. 2 DPR 115/2002: value declared in the conclusions of the introductory act
        r = _call("decreto_ingiuntivo", creditore="A", debitore="B", importo=5000)
        assert "art. 14 co. 2 DPR 115/2002" in r["bozza_ricorso"]

    def test_tipo_credito_sconosciuto(self):
        r = _call("decreto_ingiuntivo", creditore="A", debitore="B", importo=5000, tipo_credito="inesistente")
        assert "errore" in r

    def test_provvisoria_esecuzione_cambiale(self):
        r = _call(
            "decreto_ingiuntivo",
            creditore="A",
            debitore="B",
            importo=5000,
            tipo_credito="cambiale",
            provvisoria_esecuzione=True,
        )
        assert "cambiale" in r["riepilogo"]["motivi_pe"][0]

    def test_senza_pe_motivi_none(self):
        r = _call("decreto_ingiuntivo", creditore="A", debitore="B", importo=5000)
        assert r["riepilogo"]["motivi_pe"] is None

    def test_bozza_contiene_importo(self):
        r = _call("decreto_ingiuntivo", creditore="Creditor SRL", debitore="Debtor SPA", importo=12345.67)
        # Python {:,.2f} usa separatore US: "12,345.67"
        assert "12,345.67" in r["bozza_ricorso"]

    def test_condominiale_pe_motivo(self):
        r = _call(
            "decreto_ingiuntivo",
            creditore="Condominio",
            debitore="B",
            importo=3000,
            tipo_credito="condominiale",
            provvisoria_esecuzione=True,
        )
        assert "delibera" in r["riepilogo"]["motivi_pe"][0]


# ---------------------------------------------------------------------------
# calcolo_hash
# ---------------------------------------------------------------------------


class TestCalcoloHash:

    def test_deterministico(self):
        r1 = _call("calcolo_hash", testo="ciao")
        r2 = _call("calcolo_hash", testo="ciao")
        assert r1["hash"] == r2["hash"]

    def test_sha256_noto(self):
        r = _call("calcolo_hash", testo="abc")
        assert r["hash"] == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
        assert r["algoritmo"] == "SHA-256"

    def test_lunghezza_input(self):
        testo = "hello world"
        r = _call("calcolo_hash", testo=testo)
        assert r["lunghezza_input"] == len(testo)

    def test_hash_diverso_per_testi_diversi(self):
        r1 = _call("calcolo_hash", testo="documento1")
        r2 = _call("calcolo_hash", testo="documento2")
        assert r1["hash"] != r2["hash"]


# ---------------------------------------------------------------------------
# tassazione_atti
# ---------------------------------------------------------------------------


class TestTassazioneAtti:

    def test_sentenza_condanna_proporzionale(self):
        r = _call("tassazione_atti", tipo_atto="sentenza_condanna", valore=10000)
        assert r["imposta_registro"] == pytest.approx(300.0, abs=0.01)
        assert r["aliquota_pct"] == 3.0

    def test_sentenza_condanna_minimo(self):
        # 3% x 5.000 = 150 < minimo 200 (art. 41 co. 2 DPR 131/1986; art. 26 DL 104/2013);
        # a value of 100 would be exempt (art. 46 L. 374/1991)
        r = _call("tassazione_atti", tipo_atto="sentenza_condanna", valore=5000)
        assert r["imposta_registro"] == 200.0

    def test_sentenza_condanna_valore_zero(self):
        r = _call("tassazione_atti", tipo_atto="sentenza_condanna", valore=0)
        assert r["imposta_registro"] == 200.0
        assert r["aliquota_pct"] == 0

    def test_decreto_ingiuntivo_3pct(self):
        r = _call("tassazione_atti", tipo_atto="decreto_ingiuntivo", valore=20000)
        assert r["imposta_registro"] == pytest.approx(600.0, abs=0.01)

    def test_verbale_conciliazione_ordinario(self):
        r = _call("tassazione_atti", tipo_atto="verbale_conciliazione", valore=10000)
        assert r["imposta_registro"] == pytest.approx(300.0, abs=0.01)

    def test_verbale_conciliazione_prima_casa(self):
        r = _call("tassazione_atti", tipo_atto="verbale_conciliazione", valore=100000, prima_casa=True)
        assert r["aliquota_pct"] == 2.0
        assert r["imposta_registro"] == pytest.approx(2000.0, abs=0.01)

    def test_verbale_conciliazione_prima_casa_minimo(self):
        # art. 8 lett. a Tariffa I + art. 10 co. 2 D.Lgs. 23/2011: 2% = 800 < minimo 1.000
        r = _call("tassazione_atti", tipo_atto="verbale_conciliazione", valore=40000, prima_casa=True)
        assert r["imposta_registro"] == 1000.0

    def test_ordinanza_senza_condanna_fissa(self):
        # Tariffa I art. 8 lett. d: no condanna, accertamento or transfer -> fixed 200 (art. 26 DL 104/2013)
        r = _call("tassazione_atti", tipo_atto="ordinanza", valore=0)
        assert r["imposta_registro"] == 200.0
        assert r["aliquota_pct"] == 0

    def test_ordinanza_con_condanna_3pct(self):
        # Tariffa I art. 8 co. 1 lett. b: taxed by content, 3% x 20.000 = 600
        r = _call("tassazione_atti", tipo_atto="ordinanza", valore=20000)
        assert r["imposta_registro"] == pytest.approx(600.0, abs=0.01)

    def test_ordinanza_contenuto_nessuno_fissa(self):
        r = _call("tassazione_atti", tipo_atto="ordinanza", valore=999999, contenuto="nessuno")
        assert r["imposta_registro"] == 200.0

    def test_causa_fino_a_1033_esente(self):
        # art. 46 co. 1 L. 374/1991: only contributo unificato up to 1.033,00 euro
        for tipo in ("sentenza_condanna", "decreto_ingiuntivo"):
            assert _call("tassazione_atti", tipo_atto=tipo, valore=1000)["imposta_registro"] == 0
        assert _call("tassazione_atti", tipo_atto="decreto_ingiuntivo", valore=1033)["imposta_registro"] == 0
        # 1.033,01: 3% = 30,99 -> minimum 200 (art. 41 co. 2 DPR 131/1986)
        assert _call("tassazione_atti", tipo_atto="decreto_ingiuntivo", valore=1033.01)["imposta_registro"] == 200.0

    def test_valore_causa_distinto_dal_valore(self):
        # art. 46 refers to the value of the cause, not to the amount of the measure
        r = _call("tassazione_atti", tipo_atto="sentenza_condanna", valore=5000, valore_causa=1000)
        assert r["imposta_registro"] == 0

    def test_nota_II_iva_misura_fissa(self):
        # Nota II art. 8 Tariffa I + art. 40 DPR 131/1986: condanna for IVA consideration pays 200
        r = _call("tassazione_atti", tipo_atto="decreto_ingiuntivo", valore=50000, credito_soggetto_iva=True)
        assert r["imposta_registro"] == 200.0

    def test_nota_I_decreto_sostitutivo_fisso(self):
        # Nota I art. 8 Tariffa I: decree issued in substitution (art. 644 c.p.c.) pays the fixed tax
        r = _call("tassazione_atti", tipo_atto="decreto_ingiuntivo", valore=50000, decreto_sostitutivo=True)
        assert r["imposta_registro"] == 200.0

    def test_trasferimento_non_prima_casa_9pct(self):
        # art. 8 lett. a + art. 1 Tariffa I (art. 10 D.Lgs. 23/2011): 9% x 100.000 = 9.000
        r = _call("tassazione_atti", tipo_atto="verbale_conciliazione", valore=100000, contenuto="trasferimento")
        assert r["imposta_registro"] == pytest.approx(9000.0, abs=0.01)
        # minimum 1.000 (art. 10 co. 2): 9% x 5.000 = 450
        r = _call("tassazione_atti", tipo_atto="verbale_conciliazione", valore=5000, contenuto="trasferimento")
        assert r["imposta_registro"] == 1000.0

    def test_accertamento_1pct(self):
        # art. 8 lett. c Tariffa I: 1% x 100.000 = 1.000
        r = _call("tassazione_atti", tipo_atto="sentenza_condanna", valore=100000, contenuto="accertamento")
        assert r["imposta_registro"] == pytest.approx(1000.0, abs=0.01)

    def test_mediazione_esente_fino_a_100000(self):
        # art. 17 co. 2 D.Lgs. 28/2010: exempt up to 100.000, tax on the excess only
        r = _call("tassazione_atti", tipo_atto="verbale_conciliazione", valore=40000, mediazione=True)
        assert r["imposta_registro"] == 0
        r = _call("tassazione_atti", tipo_atto="verbale_conciliazione", valore=110000, mediazione=True)
        assert r["imposta_registro"] == 300.0  # 3% x 10.000 = 300

    def test_valore_negativo_errore(self):
        assert "errore" in _call("tassazione_atti", tipo_atto="decreto_ingiuntivo", valore=-500)

    def test_tipo_invalido(self):
        r = _call("tassazione_atti", tipo_atto="inesistente", valore=1000)
        assert "errore" in r


# ---------------------------------------------------------------------------
# copie_processo_tributario
# ---------------------------------------------------------------------------


class TestCopieProcessoTributario:
    # DM MEF 27 dicembre 2011, allegato 1 (copia semplice per fascia) e art. 2 co. 2 (+9 euro conformita')

    def test_semplice_fasce(self):
        attesi = {1: 1.50, 4: 1.50, 5: 3.00, 10: 3.00, 11: 6.00, 20: 6.00, 21: 12.00, 50: 12.00, 51: 25.00, 100: 25.00}
        for n, atteso in attesi.items():
            assert _call("copie_processo_tributario", n_pagine=n, tipo="semplice")["totale"] == atteso

    def test_semplice_oltre_100(self):
        # 25,00 + 15,00 for each further 100 pages or fraction
        assert _call("copie_processo_tributario", n_pagine=101, tipo="semplice")["totale"] == 40.00
        assert _call("copie_processo_tributario", n_pagine=201, tipo="semplice")["totale"] == 55.00

    def test_autentica_aggiunge_9_euro(self):
        assert _call("copie_processo_tributario", n_pagine=5, tipo="autentica")["totale"] == 12.00
        assert _call("copie_processo_tributario", n_pagine=21, tipo="autentica")["totale"] == 21.00

    def test_urgente_nessuna_maggiorazione(self):
        # The DM 27/12/2011 provides no urgency surcharge
        r = _call("copie_processo_tributario", n_pagine=21, tipo="autentica", urgente=True)
        assert r["totale"] == 21.00
        assert "maggiorazione_urgenza" not in r

    def test_tipo_non_ammesso(self):
        assert "errore" in _call("copie_processo_tributario", n_pagine=10, tipo="esecutiva")

    def test_non_urgente_no_maggiorazione_key(self):
        r = _call("copie_processo_tributario", n_pagine=10, tipo="semplice", urgente=False)
        assert "maggiorazione_urgenza" not in r


# ---------------------------------------------------------------------------
# note_iscrizione_ruolo
# ---------------------------------------------------------------------------


class TestNoteIscrizioneRuolo:

    def test_cognizione_ordinaria(self):
        r = _call("note_iscrizione_ruolo", tipo_procedimento="cognizione_ordinaria", valore_causa=5000)
        assert r["contributo_unificato"] > 0
        assert r["tipo_procedimento"] == "cognizione_ordinaria"

    def test_monitorio_cu(self):
        r = _call("note_iscrizione_ruolo", tipo_procedimento="monitorio", valore_causa=5000)
        assert r["contributo_unificato"] == 49

    def test_lavoro_cu_zero(self):
        r = _call("note_iscrizione_ruolo", tipo_procedimento="lavoro", valore_causa=10000)
        assert r["contributo_unificato"] == 0.0

    def test_locazione_ha_codici(self):
        r = _call("note_iscrizione_ruolo", tipo_procedimento="locazione", valore_causa=5000)
        assert isinstance(r["codici_oggetto_suggeriti"], list)

    def test_senza_valore_non_crasha(self):
        r = _call("note_iscrizione_ruolo", tipo_procedimento="cognizione_ordinaria")
        assert "contributo_unificato" in r

    def test_sfratto_cu_dimezzato(self):
        # Art. 13 co. 3 DPR 115/2002: half the contribution for the special proceedings of
        # book IV, title I, c.p.c. (convalida di sfratto, artt. 657-669). 3.000 euro: 98 -> 49
        ordinaria = _call("note_iscrizione_ruolo", tipo_procedimento="locazione", valore_causa=3000)
        assert ordinaria["contributo_unificato"] == 98
        sfratto = _call("note_iscrizione_ruolo", tipo_procedimento="locazione", valore_causa=3000,
                        convalida_sfratto=True)
        assert sfratto["contributo_unificato"] == 49

    def test_lavoro_oltre_soglia_dimezzato(self):
        # Art. 9 co. 1-bis + art. 13 co. 3: above three times the art. 76 threshold the CU is due,
        # halved. 20.000 euro: scaglione 237 -> 118,50
        r = _call("note_iscrizione_ruolo", tipo_procedimento="lavoro", valore_causa=20000,
                  reddito_oltre_soglia_lavoro=True)
        assert r["contributo_unificato"] == 118.5

    def test_esecuzione_mobiliare_richiede_il_valore(self):
        # Art. 13 co. 2: 43 euro below 2.500, 139 from 2.500: without the value the CU is not decidable
        r = _call("note_iscrizione_ruolo", tipo_procedimento="esecuzione_mobiliare")
        assert r["contributo_unificato"] is None
        assert _call("note_iscrizione_ruolo", tipo_procedimento="esecuzione_mobiliare",
                     valore_causa=2500)["contributo_unificato"] == 139
        assert _call("note_iscrizione_ruolo", tipo_procedimento="esecuzione_mobiliare",
                     valore_causa=2499.99)["contributo_unificato"] == 43


# ---------------------------------------------------------------------------
# codici_iscrizione_ruolo
# ---------------------------------------------------------------------------


class TestCodiciIscrizioneRuolo:

    def test_contratto_restituisce_risultati(self):
        r = _call("codici_iscrizione_ruolo", materia="contratto")
        assert r["totale"] > 0
        assert len(r["risultati"]) > 0

    def test_keyword_case_insensitive(self):
        r_lower = _call("codici_iscrizione_ruolo", materia="contratto")
        r_upper = _call("codici_iscrizione_ruolo", materia="CONTRATTO")
        assert r_lower["totale"] == r_upper["totale"]

    def test_materia_inesistente(self):
        r = _call("codici_iscrizione_ruolo", materia="xyznonexistent999")
        assert r["totale"] == 0
        assert r["risultati"] == []

    def test_accenti_ignorati(self):
        # The ministerial search does not tell accented from unaccented vowels: the same
        # keyword gives the same codes with or without the accent or the apostrophe
        senza = _call("codici_iscrizione_ruolo", materia="responsabilita")
        con = _call("codici_iscrizione_ruolo", materia="responsabilit\u00e0")
        apostrofo = _call("codici_iscrizione_ruolo", materia="responsabilita'")
        assert senza["totale"] > 6
        assert {c["codice"] for c in senza["risultati"]} == {c["codice"] for c in con["risultati"]}
        assert {c["codice"] for c in senza["risultati"]} == {c["codice"] for c in apostrofo["risultati"]}
        assert {"145001", "145011", "151110", "152110"} <= {c["codice"] for c in senza["risultati"]}

    def test_proprieta_con_e_senza_accento(self):
        a = _call("codici_iscrizione_ruolo", materia="proprieta")
        b = _call("codici_iscrizione_ruolo", materia="propriet\u00e0")
        assert a["totale"] == b["totale"] > 0

    def test_risultati_hanno_codice(self):
        r = _call("codici_iscrizione_ruolo", materia="locazione")
        if r["totale"] > 0:
            assert "codice" in r["risultati"][0]


# ---------------------------------------------------------------------------
# fascicolo_di_parte
# ---------------------------------------------------------------------------


class TestFascicoloDiParte:

    def test_contiene_parti(self):
        r = _call(
            "fascicolo_di_parte",
            avvocato="Mario Rossi",
            parte="Tizio",
            controparte="Caio",
            tribunale="Tribunale di Milano",
        )
        assert "TIZIO" in r["testo"]
        assert "CAIO" in r["testo"]
        assert "TRIBUNALE DI MILANO" in r["testo"]

    def test_con_rg_numero(self):
        r = _call(
            "fascicolo_di_parte",
            avvocato="Mario Rossi",
            parte="Tizio",
            controparte="Caio",
            tribunale="Tribunale di Roma",
            rg_numero="1234/2025",
        )
        assert "R.G. n. 1234/2025" in r["testo"]

    def test_senza_rg_placeholder(self):
        r = _call(
            "fascicolo_di_parte",
            avvocato="Mario Rossi",
            parte="Tizio",
            controparte="Caio",
            tribunale="Tribunale di Roma",
        )
        assert "R.G. n. ___/____" in r["testo"]

    def test_tipo_atto(self):
        r = _call(
            "fascicolo_di_parte",
            avvocato="A",
            parte="B",
            controparte="C",
            tribunale="T",
        )
        assert r["tipo_atto"] == "fascicolo_di_parte"


# ---------------------------------------------------------------------------
# procura_alle_liti
# ---------------------------------------------------------------------------


class TestProcuraAlleLiti:

    def test_generale_intestazione(self):
        r = _call(
            "procura_alle_liti",
            parte="Mario Rossi",
            avvocato="Avv. Luigi Bianchi",
            cf_avvocato="BNCLLG80A01H501X",
            foro="Milano",
            oggetto_causa="risarcimento danni",
        )
        assert "PROCURA ALLE LITI" in r["testo"]
        assert r["tipo_procura"] == "generale"

    def test_speciale_intestazione(self):
        r = _call(
            "procura_alle_liti",
            parte="Mario Rossi",
            avvocato="Avv. Luigi Bianchi",
            cf_avvocato="BNCLLG80A01H501X",
            foro="Milano",
            oggetto_causa="risarcimento danni",
            tipo="speciale",
        )
        assert "PROCURA SPECIALE ALLE LITI" in r["testo"]
        assert r["tipo_procura"] == "speciale"

    def test_appello_intestazione(self):
        r = _call(
            "procura_alle_liti",
            parte="Mario Rossi",
            avvocato="Avv. Luigi Bianchi",
            cf_avvocato="BNCLLG80A01H501X",
            foro="Milano",
            oggetto_causa="appello causa civile",
            tipo="appello",
        )
        assert "APPELLO" in r["testo"]

    def test_contiene_gdpr(self):
        r = _call(
            "procura_alle_liti",
            parte="Mario Rossi",
            avvocato="Avv. Luigi Bianchi",
            cf_avvocato="BNCLLG80A01H501X",
            foro="Roma",
            oggetto_causa="recupero credito",
        )
        assert "GDPR" in r["testo"] or "2016/679" in r["testo"]

    def test_contiene_avvocato(self):
        r = _call(
            "procura_alle_liti",
            parte="Sig. Tizio",
            avvocato="Avv. Caio Verde",
            cf_avvocato="CF123456",
            foro="Napoli",
            oggetto_causa="locazione",
        )
        assert "Avv. Caio Verde" in r["testo"]
        assert "Napoli" in r["testo"]


# ---------------------------------------------------------------------------
# attestazione_conformita
# ---------------------------------------------------------------------------


class TestAttestazioneDiConformita:

    def test_estratto_default(self):
        r = _call(
            "attestazione_conformita",
            avvocato="Mario Rossi",
            tipo_documento="verbale di causa",
            estremi_originale="R.G. 1234/2024, pag. 1-3",
        )
        assert "ATTESTAZIONE DI CONFORMITA'" in r["testo"]
        assert r["modalita"] == "estratto"

    def test_copia_informatica(self):
        r = _call(
            "attestazione_conformita",
            avvocato="Mario Rossi",
            tipo_documento="sentenza",
            estremi_originale="Trib. Milano n. 100/2024",
            modalita="copia_informatica",
        )
        assert "analogico" in r["testo"]
        assert r["modalita"] == "copia_informatica"

    def test_duplicato(self):
        r = _call(
            "attestazione_conformita",
            avvocato="Mario Rossi",
            tipo_documento="atto notarile",
            estremi_originale="Rep. 500/2024",
            modalita="duplicato",
        )
        assert "duplicato informatico" in r["testo"]

    def test_contiene_avvocato(self):
        r = _call(
            "attestazione_conformita",
            avvocato="Avv. Anna Neri",
            tipo_documento="doc",
            estremi_originale="R.G. 1/2024",
        )
        assert "Avv. Anna Neri" in r["testo"]

    def test_copia_informatica_art_196_novies(self):
        # art. 196-novies disp. att. c.p.c.: copy of an analog act deposited by the lawyer
        # (art. 196-decies is the copy sent to the ufficiale giudiziario)
        r = _call("attestazione_conformita", avvocato="A", tipo_documento="d", estremi_originale="e",
                  modalita="copia_informatica")
        assert "196-novies" in r["testo"] and "196-decies" not in r["testo"]
        assert "196-novies" in r["riferimento_normativo"]

    def test_riferimento_senza_norme_abrogate(self):
        # artt. 16-bis and 16-undecies DL 179/2012 are repealed by D.Lgs. 149/2022
        r = _call("attestazione_conformita", avvocato="A", tipo_documento="d", estremi_originale="e")
        assert "179/2012" not in r["riferimento_normativo"]
        assert "196-octies" in r["riferimento_normativo"] and "196-undecies" in r["riferimento_normativo"]


# ---------------------------------------------------------------------------
# relata_notifica_pec
# ---------------------------------------------------------------------------


class TestRelataNoficaPec:

    def test_genera_testo(self):
        r = _call(
            "relata_notifica_pec",
            avvocato="Mario Rossi",
            destinatario="Bianchi SPA",
            pec_destinatario="bianchi@pec.it",
            atto_notificato="ricorso per decreto ingiuntivo",
            data_invio="2024-03-15",
        )
        assert "RELATA DI NOTIFICAZIONE" in r["testo"]
        assert "bianchi@pec.it" in r["testo"]

    def test_data_formattata(self):
        r = _call(
            "relata_notifica_pec",
            avvocato="A",
            destinatario="B",
            pec_destinatario="b@pec.it",
            atto_notificato="atto",
            data_invio="2024-06-01",
        )
        assert "01/06/2024" in r["testo"]

    def test_campi_risultato(self):
        r = _call(
            "relata_notifica_pec",
            avvocato="A",
            destinatario="Dest",
            pec_destinatario="d@pec.it",
            atto_notificato="atto",
            data_invio="2024-01-01",
        )
        assert r["tipo_atto"] == "relata_notifica_pec"
        assert r["pec_destinatario"] == "d@pec.it"
        assert r["destinatario"] == "Dest"


# ---------------------------------------------------------------------------
# indice_documenti
# ---------------------------------------------------------------------------


class TestIndiceDocumenti:

    def test_base(self):
        docs = [
            {"numero": 1, "descrizione": "Contratto", "pagine": 5},
            {"numero": 2, "descrizione": "Fattura", "pagine": 3},
        ]
        r = _call("indice_documenti", documenti=docs)
        assert r["totale_documenti"] == 2
        assert r["totale_pagine"] == 8

    def test_testo_contiene_descrizioni(self):
        docs = [{"numero": 1, "descrizione": "Verbale assemblea", "pagine": 2}]
        r = _call("indice_documenti", documenti=docs)
        assert "Verbale assemblea" in r["testo"]

    def test_lista_vuota(self):
        r = _call("indice_documenti", documenti=[])
        assert r["totale_documenti"] == 0
        assert r["totale_pagine"] == 0

    def test_tipo_atto(self):
        r = _call("indice_documenti", documenti=[])
        assert r["tipo_atto"] == "indice_documenti"


# ---------------------------------------------------------------------------
# note_trattazione_scritta
# ---------------------------------------------------------------------------


class TestNoteTrattazioneScritta:

    def test_genera_bozza(self):
        r = _call(
            "note_trattazione_scritta",
            avvocato="Mario Rossi",
            parte="Tizio",
            tribunale="Tribunale di Milano",
            rg_numero="1234/2025",
            giudice="Dott. Verdi",
            conclusioni="Si chiede il rigetto.",
        )
        assert "NOTE DI TRATTAZIONE SCRITTA" in r["testo"]
        assert "127-ter" in r["testo"]

    def test_contiene_conclusioni(self):
        r = _call(
            "note_trattazione_scritta",
            avvocato="A",
            parte="B",
            tribunale="T",
            rg_numero="10/2025",
            giudice="G",
            conclusioni="Piaccia al Tribunale accogliere la domanda.",
        )
        assert "Piaccia al Tribunale accogliere la domanda." in r["testo"]

    def test_rg_numero_in_risposta(self):
        r = _call(
            "note_trattazione_scritta",
            avvocato="A",
            parte="B",
            tribunale="T",
            rg_numero="999/2024",
            giudice="G",
            conclusioni="Conclusioni.",
        )
        assert r["rg_numero"] == "999/2024"
        assert "999/2024" in r["testo"]

    def test_tribunale_uppercase_in_testo(self):
        r = _call(
            "note_trattazione_scritta",
            avvocato="A",
            parte="B",
            tribunale="tribunale di roma",
            rg_numero="1/2025",
            giudice="G",
            conclusioni="ok",
        )
        assert "TRIBUNALE DI ROMA" in r["testo"]


# ---------------------------------------------------------------------------
# sfratto_morosita
# ---------------------------------------------------------------------------


class TestSfrattoMorosita:

    def test_totale_dovuto(self):
        r = _call(
            "sfratto_morosita",
            locatore="Luigi Rossi",
            conduttore="Mario Bianchi",
            immobile="Via Roma 1, Milano",
            canone_mensile=800.0,
            mensilita_insolute=3,
            data_contratto="2020-01-15",
        )
        assert r["totale_dovuto"] == pytest.approx(2400.0, abs=0.01)

    def test_dati_nel_testo(self):
        r = _call(
            "sfratto_morosita",
            locatore="Luigi Rossi",
            conduttore="Mario Bianchi",
            immobile="Via Verdi 10",
            canone_mensile=600.0,
            mensilita_insolute=2,
            data_contratto="2021-06-01",
        )
        assert "Mario Bianchi" in r["testo"]
        assert "Luigi Rossi" in r["testo"]

    def test_data_contratto_formattata(self):
        r = _call(
            "sfratto_morosita",
            locatore="A",
            conduttore="B",
            immobile="C",
            canone_mensile=500.0,
            mensilita_insolute=1,
            data_contratto="2022-03-10",
        )
        assert "10/03/2022" in r["testo"]

    def test_tipo_atto(self):
        r = _call(
            "sfratto_morosita",
            locatore="A",
            conduttore="B",
            immobile="C",
            canone_mensile=500.0,
            mensilita_insolute=1,
            data_contratto="2022-01-01",
        )
        assert r["tipo_atto"] == "sfratto_morosita"


# ---------------------------------------------------------------------------
# atto_di_precetto
# ---------------------------------------------------------------------------


class TestAttoDiPrecetto:

    def test_totale_calcolato(self):
        r = _call(
            "atto_di_precetto",
            creditore="Banca X",
            debitore="Mario Rossi",
            titolo_esecutivo="Sentenza Trib. Milano n. 100/2024",
            importo_capitale=10000.0,
            interessi=500.0,
            spese=200.0,
        )
        assert r["totale_intimato"] == pytest.approx(10700.0, abs=0.01)

    def test_testo_contiene_totale(self):
        r = _call(
            "atto_di_precetto",
            creditore="A",
            debitore="B",
            titolo_esecutivo="Decreto ingiuntivo n. 50/2024",
            importo_capitale=5000.0,
            interessi=100.0,
            spese=50.0,
        )
        # Python {:,.2f} usa separatore US: "5,150.00"
        assert "5,150.00" in r["testo"]

    def test_solo_capitale_senza_accessori(self):
        r = _call(
            "atto_di_precetto",
            creditore="A",
            debitore="B",
            titolo_esecutivo="Sent. n. 1/2024",
            importo_capitale=3000.0,
        )
        assert r["totale_intimato"] == 3000.0

    def test_tipo_atto(self):
        r = _call(
            "atto_di_precetto",
            creditore="A",
            debitore="B",
            titolo_esecutivo="T",
            importo_capitale=1000.0,
        )
        assert r["tipo_atto"] == "atto_di_precetto"

    def test_requisiti_art_480(self):
        # art. 480 co. 2 c.p.c.: date of notification of the title (a pena di nullita') and the warning
        # with the assistance of the OCC; art. 480 co. 3: the court competent for the execution
        r = _call("atto_di_precetto", creditore="A", debitore="B", titolo_esecutivo="T", importo_capitale=1000.0)
        t = r["testo"]
        assert "notificato in data" in t
        assert "organismo di composizione della crisi" in t
        assert "Giudice competente per l'esecuzione" in t


# ---------------------------------------------------------------------------
# nota_precisazione_credito
# ---------------------------------------------------------------------------


class TestNotaPrecisazioneCredito:

    def test_totale_sommato(self):
        r = _call(
            "nota_precisazione_credito",
            creditore="Banca Y",
            debitore="Sig. X",
            procedura_esecutiva="R.G.E. 100/2024",
            capitale=8000.0,
            interessi=400.0,
            spese_legali=300.0,
            spese_esecuzione=100.0,
        )
        assert r["totale_credito"] == pytest.approx(8800.0, abs=0.01)

    def test_testo_contiene_procedura(self):
        r = _call(
            "nota_precisazione_credito",
            creditore="A",
            debitore="B",
            procedura_esecutiva="R.G.E. 999/2024",
            capitale=1000.0,
            interessi=0.0,
            spese_legali=0.0,
            spese_esecuzione=0.0,
        )
        assert "R.G.E. 999/2024" in r["testo"]

    def test_tipo_atto(self):
        r = _call(
            "nota_precisazione_credito",
            creditore="A",
            debitore="B",
            procedura_esecutiva="R.G.E. 1/2024",
            capitale=100.0,
            interessi=0.0,
            spese_legali=0.0,
            spese_esecuzione=0.0,
        )
        assert r["tipo_atto"] == "nota_precisazione_credito"

    def test_zero_accessori(self):
        r = _call(
            "nota_precisazione_credito",
            creditore="A",
            debitore="B",
            procedura_esecutiva="R.G.E. 1/2024",
            capitale=5000.0,
            interessi=0.0,
            spese_legali=0.0,
            spese_esecuzione=0.0,
        )
        assert r["totale_credito"] == 5000.0


# ---------------------------------------------------------------------------
# dichiarazione_553_cpc
# ---------------------------------------------------------------------------


class TestDichiarazione553Cpc:

    def test_conto_corrente_default(self):
        r = _call(
            "dichiarazione_553_cpc",
            terzo_pignorato="Banca ABC",
            debitore="Mario Rossi",
            procedura="R.G.E. 200/2024",
        )
        assert r["tipo_rapporto"] == "conto_corrente"
        assert "Conto corrente" in r["testo"]

    def test_stipendio(self):
        r = _call(
            "dichiarazione_553_cpc",
            terzo_pignorato="Azienda SRL",
            debitore="Mario Rossi",
            procedura="R.G.E. 200/2024",
            tipo_rapporto="stipendio",
        )
        assert "dipendente" in r["testo"]
        assert r["tipo_rapporto"] == "stipendio"

    def test_altro(self):
        r = _call(
            "dichiarazione_553_cpc",
            terzo_pignorato="Terzo",
            debitore="Debitore",
            procedura="R.G.E. 300/2024",
            tipo_rapporto="altro",
        )
        assert r["tipo_rapporto"] == "altro"

    def test_contiene_procedura(self):
        r = _call(
            "dichiarazione_553_cpc",
            terzo_pignorato="Banca",
            debitore="Sig.",
            procedura="R.G.E. 555/2025",
        )
        assert "R.G.E. 555/2025" in r["testo"]


# ---------------------------------------------------------------------------
# testimonianza_scritta
# ---------------------------------------------------------------------------


class TestTestimonianzaScritta:

    def test_numero_capitoli(self):
        r = _call(
            "testimonianza_scritta",
            teste="Giovanni Verdi",
            capitoli_prova=["Il 01/01/2024 ero presente.", "Ho firmato il contratto."],
        )
        assert r["numero_capitoli"] == 2

    def test_testo_contiene_teste(self):
        r = _call(
            "testimonianza_scritta",
            teste="Anna Bianchi",
            capitoli_prova=["Capitolo di prova."],
        )
        assert "Anna Bianchi" in r["testo"]

    def test_capitoli_nel_testo(self):
        r = _call(
            "testimonianza_scritta",
            teste="T",
            capitoli_prova=["Il teste era presente alle ore 10."],
        )
        assert "Il teste era presente alle ore 10." in r["testo"]

    def test_tipo_atto(self):
        r = _call(
            "testimonianza_scritta",
            teste="T",
            capitoli_prova=["Vero che..."],
        )
        assert r["tipo_atto"] == "testimonianza_scritta"

    def test_lista_vuota_capitoli(self):
        r = _call(
            "testimonianza_scritta",
            teste="T",
            capitoli_prova=[],
        )
        # Art. 257-bis co. 2 c.p.c.: the model must transcribe the admitted questions,
        # so an empty list is a handled error.
        assert "errore" in r


# ---------------------------------------------------------------------------
# istanza_visibilita_fascicolo
# ---------------------------------------------------------------------------


class TestIstanzaVisibilitaFascicolo:

    def test_costituzione_default(self):
        r = _call(
            "istanza_visibilita_fascicolo",
            avvocato="Mario Rossi",
            parte="Tizio",
            tribunale="Tribunale di Milano",
            rg_numero="1234/2025",
        )
        assert r["motivo"] == "costituzione"
        assert "1234/2025" in r["testo"]

    def test_consultazione(self):
        r = _call(
            "istanza_visibilita_fascicolo",
            avvocato="A",
            parte="B",
            tribunale="T",
            rg_numero="10/2024",
            motivo="consultazione",
        )
        assert r["motivo"] == "consultazione"

    def test_intervento(self):
        r = _call(
            "istanza_visibilita_fascicolo",
            avvocato="A",
            parte="B",
            tribunale="T",
            rg_numero="10/2024",
            motivo="intervento",
        )
        assert "art. 105 c.p.c." in r["testo"]

    def test_rg_in_testo(self):
        r = _call(
            "istanza_visibilita_fascicolo",
            avvocato="A",
            parte="B",
            tribunale="T",
            rg_numero="777/2025",
        )
        assert "777/2025" in r["testo"]

    def test_riferimento_senza_norma_abrogata(self):
        # art. 16-bis DL 179/2012 is repealed; art. 76 co. 2 and art. 196-quater disp. att. c.p.c. apply
        r = _call("istanza_visibilita_fascicolo", avvocato="A", parte="B", tribunale="T", rg_numero="1/2025")
        assert "16-bis" not in r["riferimento_normativo"]
        assert "76" in r["riferimento_normativo"] and "196-quater" in r["riferimento_normativo"]

    def test_motivo_non_previsto_errore(self):
        r = _call("istanza_visibilita_fascicolo", avvocato="A", parte="B", tribunale="T", rg_numero="1/2025",
                  motivo="altro")
        assert "errore" in r


class TestDichiarazioneTerzoArt547:

    @pytest.mark.parametrize("rapporto", ["conto_corrente", "stipendio", "altro"])
    def test_contenuto_art_547_in_ogni_variante(self, rapporto):
        # art. 547 c.p.c.: raccomandata or PEC to the creditor; sequestri and cessioni; when payment is due
        r = _call("dichiarazione_553_cpc", terzo_pignorato="T", debitore="D", procedura="R.G.E. 1/2025",
                  tipo_rapporto=rapporto)
        t = r["testo"].lower()
        assert "sequestri" in t and "cessioni" in t
        assert "raccomandata" in t and "pec" in t
        assert "pagamento o la consegna" in t


# ---------------------------------------------------------------------------
# cerca_ufficio_giudiziario
# ---------------------------------------------------------------------------


class TestCercaUfficioGiudiziario:

    def test_roma_trovato(self):
        r = _call("cerca_ufficio_giudiziario", comune="Roma")
        assert r["trovato"] is True
        assert "Roma" in r["ufficio_competente"]

    def test_milano_trovato(self):
        r = _call("cerca_ufficio_giudiziario", comune="Milano")
        assert r["trovato"] is True
        assert "Milano" in r["ufficio_competente"]

    def test_giudice_pace(self):
        r = _call("cerca_ufficio_giudiziario", comune="Roma", tipo="giudice_pace")
        assert r["trovato"] is True
        assert "Pace" in r["ufficio_competente"]

    def test_comune_non_trovato(self):
        r = _call("cerca_ufficio_giudiziario", comune="Comuneinesistente99")
        assert r["trovato"] is False

    def test_case_insensitive(self):
        r = _call("cerca_ufficio_giudiziario", comune="ROMA")
        assert r["trovato"] is True

    def test_suggerimenti_su_parziale(self):
        r = _call("cerca_ufficio_giudiziario", comune="mil")
        if not r["trovato"]:
            assert "suggerimenti" in r
        else:
            assert r["trovato"] is True

    @pytest.mark.parametrize("comune", [
        "Torino di Sangro", "Bari Sardo", "Lucca Sicula", "Romano di Lombardia", "Pisano",
        "Forlì del Sannio", "Bolzano Novarese",
    ])
    def test_nome_che_contiene_un_capoluogo_non_suggerisce_il_capoluogo(self, comune):
        # A comune whose name merely contains a capoluogo's belongs to another circondario
        # (R.D. 12/1941 tab. A as replaced by D.Lgs. 155/2012): never suggest the wrong tribunal.
        r = _call("cerca_ufficio_giudiziario", comune=comune)
        assert r["trovato"] is False
        assert "suggerimenti" not in r

    @pytest.mark.parametrize("comune,atteso", [
        ("Reggio nell'Emilia", "Tribunale di Reggio Emilia"),
        ("Reggio di Calabria", "Tribunale di Reggio Calabria"),
        ("Bolzano/Bozen", "Tribunale di Bolzano"),
        ("Reggio nell\u2019Emilia", "Tribunale di Reggio Emilia"),
    ])
    def test_denominazione_istat_dei_capoluoghi(self, comune, atteso):
        r = _call("cerca_ufficio_giudiziario", comune=comune)
        assert r["trovato"] is True
        assert r["ufficio_competente"] == atteso

    def test_tipo_non_supportato_errore(self):
        # 'corte_appello' used to return the Tribunale with trovato=True
        r = _call("cerca_ufficio_giudiziario", comune="Milano", tipo="corte_appello")
        assert r["trovato"] is False
        assert "errore" in r
        assert "ufficio_competente" not in r


# ---------------------------------------------------------------------------
# esporta_atto_docx (modelli_atti)
# ---------------------------------------------------------------------------


def _call_modelli(fn_name, **kwargs):
    import importlib
    mod = importlib.import_module("src.tools.modelli_atti")
    return tool_body(getattr(mod, fn_name))(**kwargs)


class TestEsportaAttoDocx:

    def test_basic_export(self):
        result = _call_modelli("esporta_atto_docx", testo="# Titolo\n\nParagrafo di testo.", titolo="Test")
        assert "docx" in result.lower()
        assert "errore" not in result.lower()

    def test_empty_text_error(self):
        result = _call_modelli("esporta_atto_docx", testo="", titolo="Vuoto")
        assert "errore" in result.lower()

    def test_markdown_formatting(self):
        md = "# Intestazione\n\n## Sottotitolo\n\n**Grassetto** e *corsivo*.\n\n- Punto 1\n- Punto 2"
        result = _call_modelli("esporta_atto_docx", testo=md, titolo="Format Test")
        assert "docx" in result.lower()

    def test_file_created(self):
        import os
        result = _call_modelli("esporta_atto_docx", testo="# Atto\n\nContenuto.", titolo="Atto Prova")
        # Result contains the file path
        assert "File salvato" in result
        path = result.split("File salvato: ")[1].split(" (")[0]
        assert os.path.isfile(path)

    def test_numbered_list(self):
        md = "1. Prima voce\n2. Seconda voce\n3. Terza voce"
        result = _call_modelli("esporta_atto_docx", testo=md, titolo="Lista Numerata")
        assert "docx" in result.lower()

    def test_blockquote(self):
        md = "> Citazione normativa art. 2043 c.c."
        result = _call_modelli("esporta_atto_docx", testo=md, titolo="Blockquote Test")
        assert "docx" in result.lower()

    def test_autore_nei_metadati(self):
        result = _call_modelli(
            "esporta_atto_docx",
            testo="# Test\n\nTesto.",
            titolo="Parere",
            autore="Avv. Mario Rossi",
        )
        assert "docx" in result.lower()
        assert "errore" not in result.lower()


class TestNotaPrecisazioneCreditoNorme:
    def test_assegnazione_cita_art_553_non_543(self):
        # Art. 553 c.p.c. (assegnazione e vendita di crediti) governs assignment;
        # art. 543 c.p.c. is the form of the garnishment deed, not assignment.
        r = _call(
            "nota_precisazione_credito",
            creditore="A", debitore="B", procedura_esecutiva="R.G.E. 1/2024",
            capitale=5000.0, interessi=125.5, spese_legali=800.0, spese_esecuzione=150.75,
        )
        assert r["totale_credito"] == pytest.approx(6076.25, abs=0.01)
        assert "Artt. 510, 553 e 596 c.p.c." in r["riferimento_normativo"]
        assert "553" in r["testo"] and "543" not in r["testo"]


class TestProcuraAlleLitiNorme:
    def test_antiriciclaggio_e_privacy_corrette(self):
        # D.Lgs. 231/2007: adeguata verifica in artt. 17 ss. (art. 4 abrogated by D.Lgs. 90/2017);
        # GDPR art. 6 par. 1 lett. b and art. 9 par. 2 lett. f, not consent.
        r = _call(
            "procura_alle_liti",
            parte="Mario Rossi", avvocato="Anna Bianchi", cf_avvocato="BNCNNA80A41H501Z",
            foro="Roma", oggetto_causa="recupero credito",
        )
        t = r["testo"]
        assert "art. 4 co. 3" not in t
        assert "artt. 17 ss." in t and "art. 3 co. 4 lett. c)" in t
        assert "Presta il consenso" not in t
        assert "art. 6 par. 1 lett. b" in t and "art. 9 par. 2 lett. f" in t
        assert "art. 13" in t


class TestRelataNotificaPecNorme:
    def _base(self, **kw):
        return _call(
            "relata_notifica_pec",
            avvocato="Anna Bianchi", destinatario="Dest", pec_destinatario="d@pec.it",
            atto_notificato="atto di citazione", data_invio="2026-10-05", **kw,
        )

    def test_contenuto_art_3bis_co5_co6(self):
        # L. 53/1994 art. 3-bis co. 5 lett. a, c, f, g and co. 6 (ruolo data).
        r = self._base(
            cf_avvocato="BNCNNA80A41H501Z", parte_assistita="Mario Rossi", cf_parte="RSSMRA70A01H501X",
            elenco_pubblico="INI-PEC", atto_analogico=True,
            ufficio_giudiziario="Tribunale di Roma", sezione="III", numero_ruolo="1234/2026",
        )
        t = r["testo"]
        for needle in ("BNCNNA80A41H501Z", "Mario Rossi", "RSSMRA70A01H501X", "INI-PEC",
                       "196-undecies", "Tribunale di Roma", "1234/2026", "05/10/2026"):
            assert needle in t

    def test_data_inesistente_errore_gestito(self):
        # 2026-02-30 does not exist: handled error, not ValueError.
        assert "errore" in _call(
            "relata_notifica_pec", avvocato="A", destinatario="D", pec_destinatario="d@pec.it",
            atto_notificato="x", data_invio="2026-02-30",
        )


class TestNoteTrattazioneScrittaNorme:
    def test_solo_istanze_e_conclusioni(self):
        # Art. 127-ter co. 1 c.p.c.: notes contain only istanze and conclusioni;
        # co. 2: perentory term of at least 15 days assigned by the substituting order.
        r = _call(
            "note_trattazione_scritta",
            avvocato="A", parte="P", tribunale="Tribunale di Milano", rg_numero="1/2026",
            giudice="G", conclusioni="Si chiede il rigetto.",
            data_provvedimento="01/10/2026", termine_deposito="20/10/2026",
        )
        t = r["testo"]
        assert "si osserva quanto segue" not in t
        assert "Si producono" not in t
        assert "ISTANZE" in t and "CONCLUSIONI" in t and "Si chiede il rigetto." in t
        assert "01/10/2026" in t and "20/10/2026" in t and "termine perentorio" in t


class TestSfrattoMorositaNorme:
    def _call_s(self, **kw):
        args = dict(locatore="L", conduttore="C", immobile="Via X 1", canone_mensile=750.0,
                    mensilita_insolute=4, data_contratto="2020-01-01")
        args.update(kw)
        return _call("sfratto_morosita", **args)

    def test_avvertimento_660_co3_e_ingiunzione(self):
        # Art. 660 co. 3 c.p.c. (D.Lgs. 164/2024): warning on legal aid; arts. 658 co. 1 and
        # 664 co. 1: request is an injunction to pay, not a condemnation. 750 x 4 = 3000.
        r = self._call_s()
        assert r["totale_dovuto"] == pytest.approx(3000.0)
        t = r["testo"]
        assert "patrocinio a spese dello Stato" in t and "art. 660 co. 3" in t
        assert "ingiunzione di pagamento" in t and "664" in t
        assert "condanna" not in t

    def test_nessuna_mensilita_errore(self):
        assert "errore" in self._call_s(mensilita_insolute=0)


class TestTestimonianzaScrittaNorme:
    def test_contenuto_art_103_bis(self):
        # Art. 103-bis disp. att. c.p.c. co. 1 (content), co. 3 (authentication by segretario
        # comunale or cancelliere); art. 251 co. 2 after Corte cost. 149/1995 (duty to tell the truth).
        r = _call("testimonianza_scritta", teste="T", capitoli_prova=["Vero che...", "Vero che..."])
        t = r["testo"]
        assert r["numero_capitoli"] == 2
        assert "importanza morale" not in t
        assert "obbligo di dire la verità" in t
        assert "non è possibile deporre" not in t.lower()
        assert "diretta" in t and "indiretta" in t
        assert "segretario comunale o del cancelliere" in t
        assert "Ordinanza di ammissione" in t and "Domicilio" in t and "artt. 200, 201 e 202" in t

    def test_nessun_capitolo_errore(self):
        assert "errore" in _call("testimonianza_scritta", teste="T", capitoli_prova=[])

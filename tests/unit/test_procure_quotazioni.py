"""Test per mcp_legal_it/tools/procure_quotazioni.py — procura alle liti e quotazioni DOCX.

I valori attesi dei prospetti sono quelli validati su pratiche reali di recupero
crediti seriale (D.M. 55/2014 agg. D.M. 147/2022): monitorio scaglione fino a
€ 5.200 → totale documento € 377,90; scaglione € 5.201-26.000 → € 452,98
(minimi = medio / 2 esatto, art. 4 co. 1 D.M. 55/2014: 236,50 e 283,50);
opposizione a valori medi su € 55.898,69 → € 22.534,57; esecuzione forzata
(minimi Tabella 17 D.M. 147/2022, scaglione base 165,50 + 283,50) → liquidabile € 655,14.
"""

import importlib
import os

_mod = importlib.import_module("mcp_legal_it.tools.procure_quotazioni")


def _call(fn_name, **kwargs):
    fn = getattr(_mod, fn_name)
    fn = getattr(fn, "fn", fn)
    return fn(**kwargs)


def _leggi_docx(result: str) -> str:
    from docx import Document

    path = result.split("File salvato: ")[1].split(" (")[0]
    assert os.path.isfile(path)
    doc = Document(path)
    parti = [p.text for p in doc.paragraphs]
    for tabella in doc.tables:
        for riga in tabella.rows:
            parti.append(" | ".join(cella.text for cella in riga.cells))
    return "\n".join(parti)


_PROCURA_KWARGS = dict(
    mandante_denominazione="Esempio S.r.l.",
    mandante_sede="via Roma n. 1 – 20100 Milano (MI)",
    mandante_cf_piva="00000000000",
    firmatario_nome="Mario Rossi",
    firmatario_cf="RSSMRA70A01F205X",
    controparte=(
        "Delta S.r.l., in persona del proprio legale rappresentante pro tempore, "
        "con sede legale in via Verdi n. 2 – 20100 Milano (MI), Cod. Fiscale e "
        "Partita IVA 11111111111"
    ),
    difensori=[
        {"nome": "Giulia Bianchi", "cf": "BNCGLI80A41F205Y"},
        {"nome": "Paolo Verdi", "cf": "VRDPLA75B02F205Z"},
    ],
    domicilio_studio="corso Esempio n. 10 – 20100 Milano (MI)",
    pec="g.bianchi@pec.esempio.it e p.verdi@pec.esempio.it",
)

_QUOTAZIONE_KWARGS = dict(
    cliente_denominazione="Esempio S.r.l.",
    cliente_indirizzo="via Roma n. 1; 20100 - Milano",
    difensori=["Avv. Giulia Bianchi", "Avv. Paolo Verdi"],
)


class TestGeneraProcuraLitiDocx:

    def test_generazione_base(self):
        result = _call("genera_procura_liti_docx", **_PROCURA_KWARGS)
        assert "File salvato" in result
        assert "errore" not in result.lower()

    def test_contenuto_verbatim_e_struttura(self):
        result = _call("genera_procura_liti_docx", **_PROCURA_KWARGS, data_documento="22/07/2026")
        testo = _leggi_docx(result)
        assert "PROCURA ALLE LITI" in testo
        assert "ART. 83, COMMA 3, C.P.C." in testo
        # clausola controparte verbatim
        assert "Partita IVA 11111111111" in testo
        # conversione data GG/MM/AAAA -> forma estesa
        assert "22 luglio 2026" in testo
        # entrambi i difensori con autentica
        assert "Avv. Giulia Bianchi" in testo
        assert "Avv. Paolo Verdi" in testo
        assert "È vera e autentica" in testo
        assert "congiuntamente e disgiuntamente" in testo

    def test_qualifica_firmatario(self):
        kwargs = dict(_PROCURA_KWARGS)
        kwargs["firmatario_qualifica"] = "presidente del consiglio di amministrazione e legale rappresentante"
        testo = _leggi_docx(_call("genera_procura_liti_docx", **kwargs))
        assert "presidente del consiglio di amministrazione" in testo

    def test_difensore_singolo(self):
        kwargs = dict(_PROCURA_KWARGS)
        kwargs["difensori"] = [{"nome": "Paolo Verdi", "cf": "VRDPLA75B02F205Z"}]
        testo = _leggi_docx(_call("genera_procura_liti_docx", **kwargs))
        assert "congiuntamente e disgiuntamente" not in testo
        assert "conferendogli all’uopo" in testo
        assert "per rato e valido il suo operato" in testo
        assert "Elegge domicilio presso il nominato difensore con studio" in testo
        assert "polizza assicurativa professionale del proprio difensore" in testo
        for plurale in ("conferendo loro", "il loro operato", "difensori"):
            assert plurale not in testo, plurale

    def test_difensore_singolo_donna_dal_codice_fiscale(self):
        # BNCGLI80A41F205Y: birth day 41 = 1 + 40, a woman
        kwargs = dict(_PROCURA_KWARGS)
        kwargs["difensori"] = [{"nome": "Giulia Bianchi", "cf": "BNCGLI80A41F205Y"}]
        testo = _leggi_docx(_call("genera_procura_liti_docx", **kwargs))
        assert "conferendole all’uopo" in testo
        assert "per rato e valido il suo operato" in testo
        assert "Elegge domicilio presso la nominata difensora con studio" in testo
        assert "polizza assicurativa professionale della propria difensora" in testo
        assert "il nominato difensore" not in testo
        assert "difensori" not in testo

    def test_due_difensori_plurale(self):
        testo = _leggi_docx(_call("genera_procura_liti_docx", **_PROCURA_KWARGS))
        assert "congiuntamente e disgiuntamente tra loro" in testo
        assert "conferendo loro all’uopo" in testo
        assert "per rato e valido il loro operato" in testo
        # one woman and one man: masculine plural
        assert "Elegge domicilio presso i nominati difensori con studio" in testo
        assert "polizza assicurativa professionale dei propri difensori" in testo
        assert "dei suoi difensori" not in testo

    def test_due_difensore_donne_plurale_femminile(self):
        kwargs = dict(_PROCURA_KWARGS)
        kwargs["difensori"] = [
            {"nome": "Giulia Bianchi", "cf": "BNCGLI80A41F205Y"},
            {"nome": "Laura Neri", "genere": "F"},
        ]
        testo = _leggi_docx(_call("genera_procura_liti_docx", **kwargs))
        assert "conferendo loro all’uopo" in testo
        assert "Elegge domicilio presso le nominate difensore con studio" in testo
        assert "polizza assicurativa professionale delle proprie difensore" in testo

    def test_firmatario_maschile_e_femminile(self):
        testo = _leggi_docx(_call("genera_procura_liti_docx", **_PROCURA_KWARGS))
        assert testo.count("Il sottoscritto Mario Rossi") == 1
        assert "di essere stato informato" in testo
        assert "stata informata" not in testo

        kwargs = dict(_PROCURA_KWARGS)
        kwargs["firmatario_nome"] = "Anna Rossi"
        kwargs["firmatario_cf"] = "RSSNNA70A41F205X"
        testo = _leggi_docx(_call("genera_procura_liti_docx", **kwargs))
        assert "La sottoscritta Anna Rossi" in testo
        assert testo.count("di essere stata informata") == 3
        assert testo.count("di essere stata resa edotta") == 2
        assert "stato informato" not in testo and "reso edotto" not in testo

    def test_privacy_gdpr_senza_consenso(self):
        testo = _leggi_docx(_call("genera_procura_liti_docx", **_PROCURA_KWARGS))
        assert "ai sensi dell’art. 13 del Regolamento (UE) 2016/679" in testo
        assert "categorie particolari di dati di cui all’art. 9 del Regolamento" in testo
        assert "art. 6, par. 1, lett. b)" in testo
        assert "art. 9, par. 2, lett. f)" in testo
        assert "D.Lgs. n. 196/2003, come modificato dal D.Lgs. n. 101/2018" in testo
        for vecchio in ("sensibili", "autorizzando", "consenso"):
            assert vecchio not in testo, vecchio

    def test_dichiarazioni_mediazione_e_negoziazione_mantenute(self):
        testo = _leggi_docx(_call("genera_procura_liti_docx", **_PROCURA_KWARGS))
        assert "art. 4, co. 3, D.Lgs. n. 28/2010" in testo
        assert "art. 2, co. 7, D.L. n. 132/2014" in testo


class TestGenere:

    def test_codice_fiscale(self):
        assert _mod._genere("VRDPLA75B02F205Z") == "M"
        assert _mod._genere("BNCGLI80A41F205Y") == "F"
        assert _mod._genere("bncgli80a41f205y ") == "F"

    def test_omocodia(self):
        # day digits replaced by omocodia letters: Q = 4, M = 1 -> 41
        assert _mod._genere("BNCGLI80AQMF205Y") == "F"
        assert _mod._genere("VRDPLA75BLNF205Z") == "M"

    def test_esplicito_e_fallback(self):
        assert _mod._genere("VRDPLA75B02F205Z", "F") == "F"
        assert _mod._genere("", "femminile") == "F"
        assert _mod._genere("") == "M"
        assert _mod._genere("01234567890") == "M"

    def test_errore_senza_difensori(self):
        kwargs = dict(_PROCURA_KWARGS)
        kwargs["difensori"] = []
        result = _call("genera_procura_liti_docx", **kwargs)
        assert "errore" in result.lower()

    def test_errore_controparte_vuota(self):
        kwargs = dict(_PROCURA_KWARGS)
        kwargs["controparte"] = "  "
        result = _call("genera_procura_liti_docx", **kwargs)
        assert "errore" in result.lower()


class TestGeneraQuotazioneDocx:

    def test_monitorio_scaglione_base(self):
        result = _call(
            "genera_quotazione_docx",
            tipo="monitorio", valore_causa=3633.77, debitore="Delta S.r.l.",
            **_QUOTAZIONE_KWARGS,
        )
        testo = _leggi_docx(result)
        # Tabella 8 D.M. 147/2022: medio 473; minimo = 473 x 50% = 236,50 (art. 4 co. 1 D.M. 55/2014).
        # 236,50 + 30% (art. 4 co. 1-bis) = 307,45; SG 15% 46,12; CPA 4% 14,14; IVA 22% 80,90;
        # liquidabile 448,61; ritenuta 20% su 353,57 = 70,71; totale documento 377,90
        assert "€ 236,50" in testo          # fase unica, minimo
        assert "€ 377,90" in testo          # totale documento
        assert "€ 49,00" in testo           # CU dimezzato
        assert "€ 524,61" in testo          # complessivo con oneri (448,61 + CU 49 + marca 27)
        assert "Per integrale accettazione" in testo

    def test_monitorio_secondo_scaglione(self):
        result = _call(
            "genera_quotazione_docx",
            tipo="monitorio", valore_causa=7428.04, debitore="Delta S.r.l.",
            **_QUOTAZIONE_KWARGS,
        )
        testo = _leggi_docx(result)
        # Tabella 8, scaglione 5.200,01-26.000: medio 567, minimo 283,50; totale documento 452,98
        assert "€ 283,50" in testo
        assert "€ 452,98" in testo
        assert "€ 118,50" in testo          # CU dimezzato scaglione 5.201-26.000

    def test_monitorio_medi_usa_tabella_ministeriale(self):
        result = _call(
            "genera_quotazione_docx",
            tipo="monitorio", valore_causa=3000, debitore="Delta S.r.l.",
            livello="medi", **_QUOTAZIONE_KWARGS,
        )
        testo = _leggi_docx(result)
        assert "valore medio" in testo
        assert "€ 473,00" in testo          # medio ministeriale (non 237 x 2 = 474)

    def test_monitorio_scaglione_esteso_520k(self):
        result = _call(
            "genera_quotazione_docx",
            tipo="monitorio", valore_causa=300000, debitore="Delta S.r.l.",
            **_QUOTAZIONE_KWARGS,
        )
        testo = _leggi_docx(result)
        assert "€ 2.197,00" in testo        # minimo scaglione 260.001-520.000
        assert "€ 607,00" in testo          # CU dalla tabella canonica

    def test_opposizione_medi(self):
        result = _call(
            "genera_quotazione_docx",
            tipo="opposizione", valore_causa=55898.69, debitore="Gamma S.r.l.",
            livello="medi", **_QUOTAZIONE_KWARGS,
        )
        testo = _leggi_docx(result)
        assert "art. 645 c.p.c." in testo
        assert "€ 14.103,00" in testo       # somma 4 fasi valori medi
        assert "€ 22.534,57" in testo       # totale documento
        assert "a carico della parte opponente" in testo

    def test_opposizione_minimi_scaglione_basso(self):
        result = _call(
            "genera_quotazione_docx",
            tipo="opposizione", valore_causa=918.29, debitore="Gamma S.r.l.",
            **_QUOTAZIONE_KWARGS,
        )
        testo = _leggi_docx(result)
        # Tabella 2: medi fino a 1.100 = 131+131+200+200; minimi = medio / 2 = 65,50+65,50+100+100 = 331
        assert "€ 331,00" in testo
        assert "€ 528,89" in testo          # totale documento

    def test_esecuzione(self):
        result = _call(
            "genera_quotazione_docx",
            tipo="esecuzione", valore_causa=1937.67, debitore="Delta S.r.l.",
            **_QUOTAZIONE_KWARGS,
        )
        testo = _leggi_docx(result)
        # Tabella 17 D.M. 147/2022, scaglione 1.100,01-5.200: minimi 165,50 + 283,50 = 449,00
        assert "€ 449,00" in testo
        assert "€ 655,14" in testo          # liquidabile
        # CU esecuzione mobiliare sotto 2.500 euro: 43 (art. 13 co. 2 DPR 115/2002) + marca 27 + forfait 120
        assert "€ 845,14" in testo
        assert "€ 43,00" in testo
        assert "pignoramento" in testo
        assert "ritenuta" not in testo.lower()   # il prospetto esecuzione non ha RA
        assert "PCT" not in testo                # e nessun aumento 30%

    def test_accettazione_personalizzata_senza_persona(self):
        result = _call(
            "genera_quotazione_docx",
            tipo="monitorio", valore_causa=1000, debitore="Delta S.r.l.",
            accettazione_denominazione="Esempio S.r.l. (Brand)",
            **_QUOTAZIONE_KWARGS,
        )
        testo = _leggi_docx(result)
        assert "Esempio S.r.l. (Brand)" in testo
        assert "Mario Rossi" not in testo   # nel blocco accettazione niente persone fisiche

    def test_cu_override(self):
        result = _call(
            "genera_quotazione_docx",
            tipo="monitorio", valore_causa=1000, debitore="Delta S.r.l.",
            contributo_unificato=21.50, **_QUOTAZIONE_KWARGS,
        )
        testo = _leggi_docx(result)
        assert "€ 21,50" in testo

    def test_errori_input(self):
        base = dict(valore_causa=1000, debitore="X", **_QUOTAZIONE_KWARGS)
        assert "errore" in _call("genera_quotazione_docx", tipo="cautelare", **base).lower()
        assert "errore" in _call(
            "genera_quotazione_docx", tipo="monitorio", livello="massimi",
            valore_causa=1000, debitore="X", **_QUOTAZIONE_KWARGS,
        ).lower()
        assert "errore" in _call(
            "genera_quotazione_docx", tipo="monitorio",
            valore_causa=0, debitore="X", **_QUOTAZIONE_KWARGS,
        ).lower()
        assert "errore" in _call(
            "genera_quotazione_docx", tipo="monitorio",
            valore_causa=600000, debitore="X", **_QUOTAZIONE_KWARGS,
        ).lower()

    def test_esecuzione_guardie_default(self):
        # default (minimi scaglione base) + livello medi -> errore, non etichetta falsa
        r = _call(
            "genera_quotazione_docx", tipo="esecuzione",
            valore_causa=3000, debitore="X", livello="medi", **_QUOTAZIONE_KWARGS,
        )
        assert "errore" in r.lower()
        # default + valore oltre lo scaglione base -> errore, non quotazione fuori scaglione
        r = _call(
            "genera_quotazione_docx", tipo="esecuzione",
            valore_causa=50000, debitore="X", **_QUOTAZIONE_KWARGS,
        )
        assert "errore" in r.lower()
        # compensi negativi -> errore
        r = _call(
            "genera_quotazione_docx", tipo="esecuzione",
            valore_causa=3000, debitore="X",
            compenso_fase_introduttiva=-166, compenso_fase_trattazione=-284,
            **_QUOTAZIONE_KWARGS,
        )
        assert "errore" in r.lower()
        # override esplicito per scaglione alto -> funziona
        r = _call(
            "genera_quotazione_docx", tipo="esecuzione",
            valore_causa=50000, debitore="X",
            compenso_fase_introduttiva=482, compenso_fase_trattazione=925,
            **_QUOTAZIONE_KWARGS,
        )
        assert "File salvato" in r


    def test_esecuzione_default_sotto_1100_tabella_17(self):
        """Tabella 17 D.M. 147/2022, scaglione fino a 1.100: minimi 55 + 118 = 173 (non 449)."""
        testo = _leggi_docx(_call(
            "genera_quotazione_docx", tipo="esecuzione",
            valore_causa=1000, debitore="Delta S.r.l.", **_QUOTAZIONE_KWARGS,
        ))
        assert "€ 55,00" in testo and "€ 118,00" in testo
        assert "€ 173,00" in testo
        assert "€ 449,00" not in testo

    def test_etichetta_aumento_pct_fino_al_30(self):
        """Art. 4 co. 1-bis D.M. 55/2014 vigente: aumento 'fino al 30 per cento'."""
        testo = _leggi_docx(_call(
            "genera_quotazione_docx", tipo="monitorio", valore_causa=3633.77,
            debitore="Delta S.r.l.", **_QUOTAZIONE_KWARGS,
        ))
        assert "fino al 30%" in testo and "D.M. 55/2014" in testo

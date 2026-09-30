"""Comparison tests: diritti_copia vs avvocatoandreani.it/servizi/calcolo_diritti_copia_cancelleria.php.

Norma: DPR 115/2002 artt. 267-270 e allegati 6 (copia senza certificazione), 7 (copia
autentica) e 8 (supporti non cartacei); art. 274 (adeguamento triennale); art. 4 co. 5
DL 193/2009 conv. L. 24/2010 (+50% sugli allegati 6 e 7); art. 269 co. 1-bis (DL 90/2014:
nessun diritto per la copia senza certificazione estratta dal fascicolo informatico);
L. 207/2024 (dal 01/01/2025 nuovo allegato 8 forfettario e art. 269 riscritto).

Il sito calcola a fasce di pagine (allegati 6 e 7 nel testo del D.M. 9 luglio 2021) e
triplica il diritto per l'urgenza (art. 270); il tool applica una tariffa per pagina
(0,30 / 0,70 euro) e una maggiorazione d'urgenza del 50%. Il modulo del sito non ha una
voce "anno": gli importi sono quelli dell'ultimo adeguamento che la pagina dichiara
(D.M. 9 luglio 2021); il tool non legge una tabella con _vintage (importi nel codice).

Mappatura dei parametri:
- tool formato='cartaceo'  -> sito Formato=C (Cartaceo)
- tool tipo='autentica'/'esecutiva' -> sito Autentica spuntata (il sito non distingue la
  copia esecutiva: dopo la riforma dell'art. 475 c.p.c. e' una copia attestata conforme)
- tool urgente -> sito Urgente
- Ufficio Giudiziario = Tribunale, Numero Copie = 1 (il tool non ha ne' ufficio ne' copie)
- tool formato='digitale' (PCT, copia estratta dal fascicolo informatico) NON corrisponde
  al formato Elettronico del sito (copia rilasciata dalla cancelleria su CD, USB, e-mail a
  pagine predeterminabili); il sito inoltre disabilita "Autentica" in formato Elettronico.
  Per le copie non cartacee a pagine non predeterminabili la pagina rinvia a un PDF
  ("tabella-diritti-di-copia-2021-formato-non-cartaceo.pdf", allegato 8 nel testo 2021,
  prima della L. 207/2024): non e' un calcolatore e non e' usato dal test.

Tolleranza: 0,01 euro (brief del benchmark).
"""

import re

import pytest

from tests.comparison.conftest import accept_cookies, assert_close, goto, parse_euro

_PAGE = "calcolo_diritti_copia_cancelleria.php"
_TOL = 0.01


def _site(page, n_pagine, formato="C", autentica=False, urgente=False, competenza="0"):
    """Compila il modulo del sito e restituisce (importo_totale, testo_risultato, stato)."""
    goto(page, _PAGE, wait_ms=1500)
    # il banner CMP (inmobi) arriva dopo il domcontentloaded e, se resta, blocca l'invio
    # del modulo: lo si rimuove di nuovo quando e' comparso
    accept_cookies(page)
    page.select_option("select[name='Competenza']", competenza)
    page.fill("input[name='NumeroCopie']", "1")
    page.fill("input[name='NumeroPagine']", str(n_pagine))
    # il click sul radio scatena chkFormato(), che disabilita "Autentica" per l'Elettronico
    page.click(f"input[name='Formato'][value='{formato}']", force=True)
    aut = page.locator("input[name='Autentica']")
    if aut.is_enabled() and aut.is_checked() != autentica:
        aut.click(force=True)
    urg = page.locator("input[name='Urgente']")
    if urg.is_checked() != urgente:
        urg.click(force=True)
    stato = page.evaluate(
        """() => ({
            formato: document.querySelector("input[name='Formato']:checked").value,
            autentica: document.querySelector("input[name='Autentica']").checked,
            autentica_disabilitata: document.querySelector("input[name='Autentica']").disabled,
            urgente: document.querySelector("input[name='Urgente']").checked,
        })"""
    )
    page.click("input[name='Button'][value='Calcola Diritti']", force=True)
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(2500)
    el = page.query_selector("td.result")
    assert el is not None, "risultato del sito non trovato (td.result)"
    testo = el.inner_text().strip()
    # "Diritti di copia dovuti: € 23,58 + € 9,83 = € 33,41" -> ultimo importo = totale
    importi = re.findall(r"€\s*([\d.]+,\d{2})", testo)
    assert importi, f"importo non leggibile nel risultato del sito: {testo!r}"
    return parse_euro(importi[-1]), testo, stato


def _tool(**kwargs):
    import src.server  # noqa: F401  registra i moduli (evita import circolari)
    from src.tools.atti_giudiziari import diritti_copia

    fn = getattr(diritti_copia, "fn", diritti_copia)
    r = fn(**kwargs)
    assert "errore" not in r, r
    return r


class TestDirittiCopiaComparison:
    # ---- casi del piano -------------------------------------------------------------

    def test_semplice_cartacea_4_pagine(self, page):
        """Piano #1 - copia semplice cartacea, fascia 1-4 pagine dell'allegato 6.
        Atteso del piano: da leggere dal sito; il tool da' 1,20 euro.
        Norma: DPR 115/2002 art. 267 e allegato 6 (+50% art. 4 co. 5 DL 193/2009)."""
        site, testo, stato = _site(page, 4)
        assert stato["formato"] == "C" and not stato["autentica"] and not stato["urgente"]
        ours = _tool(n_pagine=4, tipo="semplice", formato="cartaceo", urgente=False)
        assert_close(ours["totale"], site, _TOL, f"semplice cartacea 4 pp ({testo})")

    def test_autentica_cartacea_5_pagine_confine_fascia(self, page):
        """Piano #2 - LIMITE: 5 pagine, primo valore della fascia 5-10 dell'allegato 7
        (diritto forfettizzato comprensivo della certificazione di conformita').
        Atteso del piano: da leggere dal sito; il tool da' 3,50 euro.
        Norma: DPR 115/2002 art. 268 e allegato 7."""
        site, testo, stato = _site(page, 5, autentica=True)
        assert stato["formato"] == "C" and stato["autentica"] and not stato["urgente"]
        ours = _tool(n_pagine=5, tipo="autentica", formato="cartaceo", urgente=False)
        assert_close(ours["totale"], site, _TOL, f"autentica cartacea 5 pp ({testo})")

    def test_autentica_cartacea_urgente_11_pagine(self, page):
        """Piano #3 - LIMITE: 11 pagine (primo valore della fascia 11-20) con urgenza.
        Atteso del piano: triplo dell'importo della fascia 11-20 dell'allegato 7
        (art. 270 DPR 115/2002); il tool da' 11,55 euro (+50%).
        Norma: DPR 115/2002 artt. 268 e 270, allegato 7."""
        site, testo, stato = _site(page, 11, autentica=True, urgente=True)
        assert stato["formato"] == "C" and stato["autentica"] and stato["urgente"]
        ours = _tool(n_pagine=11, tipo="autentica", formato="cartaceo", urgente=True)
        assert_close(ours["totale"], site, _TOL, f"autentica cartacea urgente 11 pp ({testo})")

    def test_semplice_digitale_30_pagine(self, page):
        """Piano #4 - copia semplice digitale (PCT).
        Atteso del piano: 0,00 euro, nessun diritto per la copia senza certificazione
        estratta dal fascicolo informatico dai soggetti abilitati (art. 269 co. 1-bis DPR
        115/2002, DL 90/2014; testo L. 207/2024).
        Il formato "Elettronico" del sito e' la copia rilasciata dalla cancelleria su
        supporto (CD, USB, e-mail) a pagine predeterminabili (art. 4 co. 5 DL 193/2009),
        non l'estrazione dal fascicolo informatico: scenario diverso. Si legge il valore
        del sito solo per registrarlo, poi il caso e' saltato."""
        site, testo, stato = _site(page, 30, formato="E")
        ours = _tool(n_pagine=30, tipo="semplice", formato="digitale", urgente=False)
        testo_pagina = page.inner_text("body")
        cita_269 = "estratta dal fascicolo informatico" in testo_pagina
        pytest.skip(
            "non confrontabile: il sito non calcola la copia estratta dal fascicolo "
            f"informatico (tool={ours['totale']:.2f}); formato Elettronico del sito, "
            f"copia rilasciata dalla cancelleria = {site:.2f} ({testo}); "
            f"la pagina cita l'art. 269 co. 1-bis: {cita_269}"
        )

    def test_autentica_digitale_101_pagine_urgente(self, page):
        """Piano #5 - copia autentica digitale oltre 100 pagine con urgenza.
        Atteso del piano: forfait dell'allegato 8 (8 euro trasmissione telematica, 25 per
        supporto fisico) piu' l'eventuale diritto di certificazione, senza urgenza
        (art. 270 solo per il cartaceo); il tool da' 11,75 euro.
        Il sito disabilita "Autentica" quando si sceglie il formato Elettronico: non
        calcola la copia autentica non cartacea. Si verifica la disabilitazione e si salta."""
        site, testo, stato = _site(page, 101, formato="E", autentica=True, urgente=True)
        ours = _tool(n_pagine=101, tipo="autentica", formato="digitale", urgente=True)
        assert stato["autentica_disabilitata"] and not stato["autentica"], stato
        pytest.skip(
            "sito_non_calcola: in formato Elettronico il sito disabilita 'Autentica' "
            f"(tool={ours['totale']:.2f}); il sito calcola solo la copia elettronica "
            f"semplice urgente = {site:.2f} ({testo})"
        )

    def test_esecutiva_cartacea_3_pagine(self, page):
        """Piano #6 - LIMITE (opzione enumerata): tipo 'esecutiva' dopo la riforma
        dell'art. 475 c.p.c. (formula esecutiva soppressa: copia attestata conforme).
        Atteso del piano: stesso importo della copia autentica, allegato 7 fascia 1-4
        pagine, da leggere dal sito; il tool da' 2,10 euro.
        Norma: art. 475 c.p.c. (D.Lgs. 149/2022); DPR 115/2002 art. 268 e allegato 7."""
        site, testo, stato = _site(page, 3, autentica=True)
        assert stato["formato"] == "C" and stato["autentica"] and not stato["urgente"]
        ours = _tool(n_pagine=3, tipo="esecutiva", formato="cartaceo", urgente=False)
        assert_close(ours["totale"], site, _TOL, f"esecutiva(=autentica) cartacea 3 pp ({testo})")

    # ---- casi al limite aggiunti ----------------------------------------------------

    def test_semplice_cartacea_10_pagine_fine_fascia(self, page):
        """LIMITE: 10 pagine, ultimo valore della fascia 5-10 dell'allegato 6.
        Atteso: importo della fascia 5-10 letto dal sito; il tool da' 3,00 euro (0,30 x 10).
        Norma: DPR 115/2002 art. 267 e allegato 6."""
        site, testo, stato = _site(page, 10)
        assert stato["formato"] == "C" and not stato["autentica"] and not stato["urgente"]
        ours = _tool(n_pagine=10, tipo="semplice", formato="cartaceo", urgente=False)
        assert_close(ours["totale"], site, _TOL, f"semplice cartacea 10 pp ({testo})")

    def test_semplice_cartacea_11_pagine_inizio_fascia(self, page):
        """LIMITE: 11 pagine, primo valore della fascia 11-20 dell'allegato 6.
        Atteso: importo della fascia 11-20 letto dal sito; il tool da' 3,30 euro.
        Norma: DPR 115/2002 art. 267 e allegato 6."""
        site, testo, stato = _site(page, 11)
        assert stato["formato"] == "C" and not stato["autentica"] and not stato["urgente"]
        ours = _tool(n_pagine=11, tipo="semplice", formato="cartaceo", urgente=False)
        assert_close(ours["totale"], site, _TOL, f"semplice cartacea 11 pp ({testo})")

    def test_semplice_cartacea_101_pagine_oltre_100(self, page):
        """LIMITE: 101 pagine, fascia 'oltre 100' dell'allegato 6 (importo della fascia
        51-100 piu' la quota per ogni ulteriori 100 pagine o frazione).
        Atteso: importo letto dal sito; il tool da' 30,30 euro (0,30 x 101).
        Norma: DPR 115/2002 art. 267 e allegato 6."""
        site, testo, stato = _site(page, 101)
        assert stato["formato"] == "C" and not stato["autentica"] and not stato["urgente"]
        ours = _tool(n_pagine=101, tipo="semplice", formato="cartaceo", urgente=False)
        assert_close(ours["totale"], site, _TOL, f"semplice cartacea 101 pp ({testo})")

    def test_semplice_cartacea_urgente_4_pagine(self, page):
        """LIMITE (opzione urgenza sulla copia semplice): fascia 1-4 dell'allegato 6.
        Atteso: triplo della fascia 1-4 (art. 270 DPR 115/2002) letto dal sito; il tool
        da' 1,80 euro (1,20 + 50%).
        Norma: DPR 115/2002 artt. 267 e 270, allegato 6."""
        site, testo, stato = _site(page, 4, urgente=True)
        assert stato["formato"] == "C" and not stato["autentica"] and stato["urgente"]
        ours = _tool(n_pagine=4, tipo="semplice", formato="cartaceo", urgente=True)
        assert_close(ours["totale"], site, _TOL, f"semplice cartacea urgente 4 pp ({testo})")

    def test_semplice_cartacea_201_pagine_frazione(self, page):
        """LIMITE: 201 pagine, seconda quota "per ogni ulteriori 100 pagine o frazione"
        dell'allegato 6 (fascia 51-100 piu' due quote: 101-200 e 201-300).
        Atteso: importo letto dal sito; il tool da' 60,30 euro (0,30 x 201).
        Norma: DPR 115/2002 art. 267 e allegato 6."""
        site, testo, stato = _site(page, 201)
        assert stato["formato"] == "C" and not stato["autentica"] and not stato["urgente"]
        ours = _tool(n_pagine=201, tipo="semplice", formato="cartaceo", urgente=False)
        assert_close(ours["totale"], site, _TOL, f"semplice cartacea 201 pp ({testo})")

    def test_autentica_cartacea_50_pagine_fine_fascia(self, page):
        """LIMITE: 50 pagine, ultimo valore della fascia 21-50 dell'allegato 7.
        Atteso: importo della fascia 21-50 letto dal sito; il tool da' 35,00 euro
        (0,70 x 50).
        Norma: DPR 115/2002 art. 268 e allegato 7."""
        site, testo, stato = _site(page, 50, autentica=True)
        assert stato["formato"] == "C" and stato["autentica"] and not stato["urgente"]
        ours = _tool(n_pagine=50, tipo="autentica", formato="cartaceo", urgente=False)
        assert_close(ours["totale"], site, _TOL, f"autentica cartacea 50 pp ({testo})")

    def test_autentica_cartacea_101_pagine_oltre_100(self, page):
        """LIMITE: 101 pagine, fascia 'oltre 100' dell'allegato 7 (fascia 51-100 piu' la
        quota per ogni ulteriori 100 pagine o frazione).
        Atteso: importo letto dal sito; il tool da' 70,70 euro (0,70 x 101).
        Norma: DPR 115/2002 art. 268 e allegato 7."""
        site, testo, stato = _site(page, 101, autentica=True)
        assert stato["formato"] == "C" and stato["autentica"] and not stato["urgente"]
        ours = _tool(n_pagine=101, tipo="autentica", formato="cartaceo", urgente=False)
        assert_close(ours["totale"], site, _TOL, f"autentica cartacea 101 pp ({testo})")

    def test_giudice_di_pace_non_modellato(self, page):
        """LIMITE (opzione enumerata del sito): Ufficio Giudiziario = Giudice di Pace.
        Il tool non ha un parametro per l'ufficio giudiziario: non confrontabile. Si legge
        il valore del sito solo per registrarlo."""
        site, testo, stato = _site(page, 4, competenza="1")
        ours = _tool(n_pagine=4, tipo="semplice", formato="cartaceo", urgente=False)
        pytest.skip(
            "non confrontabile: il tool non distingue l'ufficio giudiziario "
            f"(tool={ours['totale']:.2f}); sito Giudice di Pace, semplice cartacea 4 pp "
            f"= {site:.2f} ({testo})"
        )

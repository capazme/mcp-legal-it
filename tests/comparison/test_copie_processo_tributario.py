"""Comparison tests: copie_processo_tributario vs
avvocatoandreani.it/servizi/calcolo_diritti_copia_processo_tributario.php.

The site computes the copy fees of the tax process under DM 27/12/2011 (MEF,
"determinazione delle spese per il rilascio delle copie di atti e documenti
relativi al processo tributario"; the page cites it with the MEF circolare
2/DF of 26/03/2012 and DPR 115/2002): paper copies by page bracket
(allegato 1) plus a fixed 9 euro per document for the certified copy
(art. 2, comma 2, allegato 2); electronic copies by KB or by page (allegati
3 and 4). The site has no urgency option and no copy type other than
"with/without certificate of conformity".

Allegato 1 of the DM, as reported by two secondary sources (fiscoetasse.com
"Riepilogo delle spese per le copie di atti e documenti relativi al processo
tributario"; professionegiustizia.it "Tabelle Diritti di Copia Processo
tributario"), reads: 1-4 pages 1.50; 5-10 3.00; 11-20 6.00; 21-50 12.00;
51-100 25.00; over 100 pages 25.00 + 15.00 for every further 100 pages or
fraction. The site stays at 25.00 above 100 pages (observed at 101 and 201),
so above 100 pages the site itself looks wrong: see the two tests there.
Art. 270 DPR 115/2002 (read on Normattiva) triples the fee for paper copies
issued within two days; whether it reaches the tax process, where the DM sets
the fees, is left to phase 2.

The tool applies a flat 0.25 euro/page (simple) or 0.50 euro/page (certified)
and +50% for urgency. Only the paper, single-copy, non-urgent path is
comparable; the rest is skipped with the reason.

Tolerance: 0.01 euro (benchmark brief).
"""

import re

import pytest

from tests.comparison.conftest import accept_cookies, assert_close, goto, parse_euro

_PAGE = "calcolo_diritti_copia_processo_tributario.php"
_TOL = 0.01


_RESULT_OR_ERROR = "text=/Diritti di copia dovuti|Un campo risulta errato/"


def _submit(page, n_pagine: int, autentica: bool = False) -> str:
    """Drive the site form (1 copy, paper format, n pages, optional conformity)
    and return the visible page text: the result, or the site's own
    validation message ("Un campo risulta errato o non compilato")."""
    goto(page, _PAGE, wait_ms=1500)
    # The site's own consent banner (#accept-btn) appears only after the first
    # scripts run: goto() checks it right after domcontentloaded and may miss
    # it, and while it is open the form POST never leaves the page. Retry now.
    accept_cookies(page)
    page.fill("#NumeroCopie", "1")
    page.check("#Formato1", force=True)  # Cartaceo
    page.fill("#PagineKB", str(n_pagine))
    if autentica:
        page.check("#Autentica", force=True)
    page.click("form[name='DirittiTrib'] input[type=submit]", force=True)
    page.wait_for_selector(_RESULT_OR_ERROR, timeout=20000)
    page.wait_for_timeout(1500)
    return page.inner_text("body")


def _site(page, n_pagine: int, autentica: bool = False) -> float:
    """Amount shown by the site as 'Diritti di copia dovuti'."""
    text = _submit(page, n_pagine, autentica)
    m = re.search(r"Diritti di copia dovuti:\s*€\s*([\d.]+,\d{2})", text)
    if not m:
        raise ValueError("Could not parse 'Diritti di copia dovuti' from the site")
    return parse_euro(m.group(1))


def _tool(**kwargs) -> dict:
    import src.server  # noqa: F401  (registers every module, avoids circular imports)
    from src.tools.atti_giudiziari import copie_processo_tributario

    fn = getattr(copie_processo_tributario, "fn", copie_processo_tributario)
    return fn(**kwargs)


class TestCopieProcessoTributarioComparison:

    # --- casi del piano -----------------------------------------------------

    def test_semplice_4_pagine_prima_fascia(self, page):
        """Piano: copia semplice, prima fascia (1-4 pagine), cartacea senza
        certificazione. Atteso: da leggere dal sito; il tool da' 1,00 euro.
        Norma: DM 27/12/2011 all. 1 (fascia 1-4 pagine); DPR 115/2002 art. 40."""
        ours = _tool(n_pagine=4, tipo="semplice", urgente=False)
        site = _site(page, 4, autentica=False)
        assert_close(ours["totale"], site, _TOL, "semplice 4 pagine")

    def test_autentica_5_pagine_confine_fascia(self, page):
        """Piano (limite): copia autentica al confine di fascia (5 pagine).
        Atteso: da leggere dal sito (fascia 5-10 con certificazione); il tool
        da' 2,50 euro. Norma: DM 27/12/2011 all. 1 (fascia 5-10) + art. 2 c. 2
        e all. 2 (diritto aggiuntivo fisso di 9 euro per documento)."""
        ours = _tool(n_pagine=5, tipo="autentica", urgente=False)
        site = _site(page, 5, autentica=True)
        assert_close(ours["totale"], site, _TOL, "autentica 5 pagine")

    def test_autentica_21_pagine_urgente(self):
        """Piano: copia autentica urgente, fascia 21-50. Atteso: triplo della
        fascia se si applica l'art. 270 DPR 115/2002; il tool da' 15,75 euro
        (+50%). Norma: DPR 115/2002 art. 270; DM 27/12/2011 all. 1-2.
        Non confrontabile: il calcolatore tributario del sito non ha alcuna
        opzione di urgenza (le fonti sul DM 27/12/2011 non la riportano). La
        componente non urgente e' confrontata in
        test_autentica_21_pagine_non_urgente: il sito da' 21,00, che triplicato
        ex art. 270 (copie cartacee rilasciate entro due giorni, senza e con
        certificazione) farebbe 63,00, contro i 15,75 del tool."""
        ours = _tool(n_pagine=21, tipo="autentica", urgente=True)
        pytest.skip(
            "Il sito non offre l'opzione di urgenza nel processo tributario "
            f"(tool: totale {ours.get('totale')}, maggiorazione "
            f"{ours.get('maggiorazione_urgenza')})"
        )

    def test_tipo_non_ammesso_esecutiva(self):
        """Piano (opzione enumerata): tipo 'esecutiva' non ammesso. Atteso:
        errore per tipo non ammesso; il tool calcola 2,50 euro come copia
        semplice. Norma: DM 27/12/2011 art. 2 (solo copia senza certificazione,
        autentica, elettronica). Non confrontabile: il sito offre solo la
        casella 'Conformita'' e non accetta un tipo libero."""
        ours = _tool(n_pagine=10, tipo="esecutiva", urgente=False)
        esito_tool = ours.get("errore") or f"totale {ours.get('totale')}, nessun errore"
        pytest.skip(
            "Il sito non ha un tipo 'esecutiva' (solo la casella 'Conformita''); "
            f"tool: {esito_tool}"
        )

    # --- casi aggiuntivi (confini di fascia) -------------------------------

    def test_autentica_21_pagine_non_urgente(self, page):
        """Limite: 21 pagine con certificazione, primo valore della fascia
        21-50. Atteso: fascia 21-50 del DM + 9 euro fissi; il tool da' 10,50.
        Norma: DM 27/12/2011 all. 1 e 2."""
        ours = _tool(n_pagine=21, tipo="autentica", urgente=False)
        site = _site(page, 21, autentica=True)
        assert_close(ours["totale"], site, _TOL, "autentica 21 pagine")

    def test_semplice_1_pagina_minimo(self, page):
        """Limite: una sola pagina (minimo ammesso). Atteso: fascia 1-4 del DM;
        il tool da' 0,25. Norma: DM 27/12/2011 all. 1."""
        ours = _tool(n_pagine=1, tipo="semplice", urgente=False)
        site = _site(page, 1)
        assert_close(ours["totale"], site, _TOL, "semplice 1 pagina")

    def test_semplice_10_pagine_fine_fascia(self, page):
        """Limite: ultima pagina della fascia 5-10. Il tool da' 2,50.
        Norma: DM 27/12/2011 all. 1."""
        ours = _tool(n_pagine=10, tipo="semplice", urgente=False)
        site = _site(page, 10)
        assert_close(ours["totale"], site, _TOL, "semplice 10 pagine")

    def test_semplice_11_pagine_inizio_fascia(self, page):
        """Limite: prima pagina della fascia 11-20. Il tool da' 2,75.
        Norma: DM 27/12/2011 all. 1."""
        ours = _tool(n_pagine=11, tipo="semplice", urgente=False)
        site = _site(page, 11)
        assert_close(ours["totale"], site, _TOL, "semplice 11 pagine")

    def test_semplice_50_pagine_fine_fascia(self, page):
        """Limite: ultima pagina della fascia 21-50. Il tool da' 12,50.
        Norma: DM 27/12/2011 all. 1."""
        ours = _tool(n_pagine=50, tipo="semplice", urgente=False)
        site = _site(page, 50)
        assert_close(ours["totale"], site, _TOL, "semplice 50 pagine")

    def test_semplice_51_pagine_inizio_fascia(self, page):
        """Limite: prima pagina della fascia 51-100. Il tool da' 12,75.
        Norma: DM 27/12/2011 all. 1."""
        ours = _tool(n_pagine=51, tipo="semplice", urgente=False)
        site = _site(page, 51)
        assert_close(ours["totale"], site, _TOL, "semplice 51 pagine")

    def test_semplice_100_pagine_fine_fascia(self, page):
        """Limite: ultima pagina della fascia 51-100. Il tool da' 25,00
        (100 x 0,25), la fascia 51-100 del DM vale 25,00: qui i due modelli
        si incrociano per pura coincidenza aritmetica, non perche' il tool
        applichi la fascia. Norma: DM 27/12/2011 all. 1."""
        ours = _tool(n_pagine=100, tipo="semplice", urgente=False)
        site = _site(page, 100)
        assert_close(ours["totale"], site, _TOL, "semplice 100 pagine")

    def test_zero_pagine_rifiutate(self, page):
        """Limite: zero pagine, sotto il minimo. Il tool risponde con un errore
        ('n_pagine deve essere un intero positivo'); il confronto verifica che
        anche il sito rifiuti il calcolo invece di esporre un importo."""
        ours = _tool(n_pagine=0, tipo="semplice", urgente=False)
        text = _submit(page, 0)
        assert "errore" in ours, f"il tool calcola 0 pagine: {ours}"
        assert "Diritti di copia dovuti" not in text, "il sito calcola 0 pagine"
        assert "Un campo risulta errato" in text

    def test_semplice_101_pagine_oltre_100(self, page):
        """Limite: oltre le 100 pagine. Il tool da' 25,25. Secondo l'all. 1
        del DM (fonti secondarie citate in testa al file) spettano 25,00 +
        15,00 per ogni ulteriori 100 pagine o frazione = 40,00: se il sito
        resta a 25,00, sbaglia anche il sito. Norma: DM 27/12/2011 all. 1."""
        ours = _tool(n_pagine=101, tipo="semplice", urgente=False)
        site = _site(page, 101)
        assert_close(ours["totale"], site, _TOL, "semplice 101 pagine")

    def test_semplice_201_pagine_oltre_200(self, page):
        """Limite: oltre le 200 pagine, per vedere se il sito applica un
        incremento per ogni ulteriore centinaio di pagine. Il tool da' 50,25.
        Secondo l'all. 1 del DM spettano 25,00 + 2 x 15,00 = 55,00.
        Norma: DM 27/12/2011 all. 1."""
        ours = _tool(n_pagine=201, tipo="semplice", urgente=False)
        site = _site(page, 201)
        assert_close(ours["totale"], site, _TOL, "semplice 201 pagine")

    def test_multi_copia_non_supportata(self):
        """Opzione enumerata: il sito accetta il numero di copie (campo
        'Numero Copie'), il tool no (calcola sempre una copia). Non
        confrontabile."""
        pytest.skip("Il tool non ha un parametro per il numero di copie")

    def test_formato_elettronico_non_supportato(self):
        """Opzione enumerata: copie in formato elettronico (DM 27/12/2011
        all. 3 per KB, all. 4 per pagine da archivio). Il tool non distingue
        il formato. Non confrontabile."""
        pytest.skip("Il tool non gestisce le copie in formato elettronico (all. 3-4 DM 27/12/2011)")

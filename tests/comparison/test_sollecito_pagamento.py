"""Comparison tests: sollecito_pagamento vs avvocatoandreani.it.

Il tool (``src/tools/atti_giudiziari.py``) genera la bozza della lettera di sollecito e
calcola gli interessi di mora sul ritardo:
- senza ``tasso_mora``: tasso D.Lgs. 231/2002 per semestre (tabella ``tassi_mora.json``,
  BCE + 8 punti, copre fino al 31/12/2026), decorrenza dal giorno successivo alla scadenza
  (art. 4 co. 1), divisore = giorni dell'anno solare di ciascun semestre (365/366);
- con ``tasso_mora``: tasso convenzionale su tutto il periodo, divisore = giorni dell'anno
  della SCADENZA.

Pagine del sito usate
---------------------
- ``lettera-sollecito-pagamento.php`` (pagina del piano): redattore della lettera. NON calcola
  interessi (elenco crediti, acconti, termine di versamento, "vale come messa in mora"):
  il confronto riguarda solo il capitale riportato nella lettera.
- ``interessi_moratori.php`` (pagina secondaria del piano): riscontro numerico degli interessi
  D.Lgs. 231/2002. "Data Inizio" = data di scadenza (il sito conta dal giorno successivo:
  31/03 -> 30/06 = 91 giorni), un rigo per semestre. La casella "Transazione conclusa entro il
  31/12/2012" (maggiorazione di 7 punti, art. 5 D.Lgs. 231/2002 nel testo anteriore al
  D.Lgs. 192/2012) e' FORZATA dal sito quando la data iniziale e' anteriore al 2013 e resta
  selezionabile per le date successive.
- ``interessi_tasso_fisso.php``: riscontro per il tasso convenzionale (``tasso_mora``).

Convenzioni del sito osservate: divisore 365 anche negli anni bisestili (2012, 2024), sia
sugli interessi moratori sia sul tasso fisso; arrotondamento al centesimo per rigo; oltre
l'ultimo semestre pubblicato il sito prosegue con l'ultimo tasso noto.

Tolleranza: 0,01 euro (brief). Il sito e' un benchmark, non una fonte: gli scostamenti
restano registrati come tali e li giudica la fase 2.
"""

import os
import re
import time

import pytest

os.environ.setdefault("LEGAL_TODAY", "2026-09-25")

from tests.comparison.conftest import assert_close, goto, parse_euro  # noqa: E402

_TOL = 0.01
_HIDE_CMP = (
    ".qc-cmp2-container,#qc-cmp2-container"
    "{display:none !important;pointer-events:none !important}"
)
_EURO = r"([\d.]+,\d{2})"


# ---------------------------------------------------------------------------
# Tool
# ---------------------------------------------------------------------------

def _tool(**kw) -> dict:
    import src.server  # noqa: F401  (registra i moduli, evita import circolari)
    from src.tools.atti_giudiziari import sollecito_pagamento

    fn = getattr(sollecito_pagamento, "fn", sollecito_pagamento)
    return fn(creditore="Alfa S.r.l.", debitore="Beta S.p.A.", **kw)


def _calcoli(r: dict) -> dict:
    assert "errore" not in r, f"il tool rifiuta il caso: {r.get('errore')}"
    return r["calcoli"]


# ---------------------------------------------------------------------------
# Driver del sito
# ---------------------------------------------------------------------------

def _open(page, path: str):
    time.sleep(1.5)  # cortesia verso il sito tra una richiesta e l'altra
    goto(page, path)
    # il banner Quantcast ricompare dopo accept_cookies e intercetta i click:
    # lo si nasconde (nessun consenso prestato) e si invia il modulo via requestSubmit.
    page.add_style_tag(content=_HIDE_CMP)
    page.wait_for_timeout(800)


def _submit(page, form_name: str):
    with page.expect_navigation(wait_until="domcontentloaded", timeout=60000):
        page.evaluate(
            f"document.forms['{form_name}'].requestSubmit(document.getElementById('btn-calc'))"
        )
    page.wait_for_timeout(1500)


def _select_dates(page, data_inizio: str, data_fine: str):
    ai, mi, gi = data_inizio.split("-")
    af, mf, gf = data_fine.split("-")
    for name, val in (
        ("GiornoInizio", gi), ("MeseInizio", mi), ("AnnoInizio", ai),
        ("GiornoFine", gf), ("MeseFine", mf), ("AnnoFine", af),
    ):
        page.select_option(f"select[name='{name}']", val)


def _parse_righe(body: str) -> list[tuple]:
    righe = re.findall(
        r"(\d{2}/\d{2}/\d{4})\t(\d{2}/\d{2}/\d{4})\t€ " + _EURO
        + r"\t([\d,]+)%[^\t]*\t(\d+)\t€ " + _EURO,
        body,
    )
    return [
        (dal, al, float(tasso.replace(",", ".")), int(gg), parse_euro(imp))
        for dal, al, _cap, tasso, gg, imp in righe
    ]


def _mora_sito(page, capitale: str, data_inizio: str, data_fine: str,
               previgente: bool | None = None) -> dict:
    """interessi_moratori.php: Data Inizio = scadenza, Data Fine = sollecito."""
    _open(page, "interessi_moratori.php")
    page.fill("input[name='Capitale']", capitale)
    _select_dates(page, data_inizio, data_fine)
    if previgente is not None:
        # Il click simulato non cambia lo stato della casella (stile personalizzato del sito;
        # il suo onclick chkNormativaPrevigente() e' vuoto): la si imposta direttamente.
        # Per le date iniziali anteriori al 2013 il sito la seleziona da se' (chkDataInizio).
        page.evaluate(
            "document.getElementById('NormativaPrevigente').checked = "
            + ("true" if previgente else "false")
        )
    previgente_effettivo = page.is_checked("#NormativaPrevigente")
    _submit(page, "InteressiMora")
    body = page.inner_text("body")
    tot = re.search(r"Totale interessi moratori:\s*€\s*" + _EURO, body)
    gg = re.search(r"Totale colonna giorni:\s*(\d+)", body)
    assert tot and gg, "risultato del sito non trovato (interessi_moratori.php)"
    return {
        "totale": parse_euro(tot.group(1)),
        "giorni": int(gg.group(1)),
        "righe": _parse_righe(body),
        "previgente": previgente_effettivo,
    }


def _fisso_sito(page, capitale: str, tasso: str, data_inizio: str, data_fine: str) -> dict:
    """interessi_tasso_fisso.php, nessuna capitalizzazione."""
    _open(page, "interessi_tasso_fisso.php")
    page.fill("input[name='Tasso']", tasso)
    page.fill("input[name='Capitale']", capitale)
    _select_dates(page, data_inizio, data_fine)
    _submit(page, "InteressiTassoFisso")
    body = page.inner_text("body")
    tot = re.search(r"Totale interessi:\s*€\s*" + _EURO, body)
    gg = re.search(r"Totale colonna giorni:\s*(\d+)", body)
    assert tot and gg, "risultato del sito non trovato (interessi_tasso_fisso.php)"
    return {"totale": parse_euro(tot.group(1)), "giorni": int(gg.group(1)),
            "righe": _parse_righe(body)}


_LETTERA: dict = {}


def _lettera_sito(page) -> str:
    """lettera-sollecito-pagamento.php con i dati del caso 1 del piano (una sola richiesta)."""
    if "testo" not in _LETTERA:
        _open(page, "lettera-sollecito-pagamento.php")
        page.select_option("#TipoMitt", "2")  # legale rappresentante del creditore
        page.wait_for_timeout(500)
        page.fill("#NomeMitt", "Mario Rossi")
        page.fill("#PRagSoc", "Alfa S.r.l.")
        page.select_option("#TitoloDest", "1")  # Spett.le
        page.fill("#NomeDest", "Beta S.p.A.")
        page.fill("#IndirDest", "Via Esempio 1\n00100 Roma")
        page.fill("#DescrComp-0", "Fattura scaduta il 31/03/2026")
        page.fill("#ImpComp-0", "10000,00")
        page.fill("#Giorni", "15")
        page.fill("#DataDoc", "30/09/2026")
        _submit(page, "LetteraSollecitoPagamento")
        body = page.inner_text("body")
        k = body.find("Oggetto: Sollecito di pagamento")
        assert k >= 0, "lettera del sito non trovata"
        _LETTERA["testo"] = re.sub(r"[ \t\xa0]+", " ", body[k:k + 2000])
    return _LETTERA["testo"]


def _assert_mora(ours: dict, site: dict, label: str):
    assert_close(ours["interessi_mora"], site["totale"], tolerance=_TOL,
                 label=f"{label} (righe sito: {site['righe']}; spunta ante 2013: {site['previgente']})")
    assert ours["giorni_ritardo"] == site["giorni"], (
        f"{label}: giorni tool={ours['giorni_ritardo']} sito={site['giorni']}")
    assert_close(ours["totale_dovuto"], ours["importo_originale"] + site["totale"],
                 tolerance=_TOL, label=f"{label} totale dovuto")


# ---------------------------------------------------------------------------
# Casi del piano
# ---------------------------------------------------------------------------

class TestSollecitoPianoBenchmark:

    def test_due_semestri_2026(self, page):
        """Piano, caso 1 (al limite: confine di semestre 30/06-01/07).
        Atteso: 515,19 = 91 gg al 10,15% (I sem. 2026) + 92 gg al 10,40% (II sem.), anno di
        365 giorni; totale 10.515,19. Norma: artt. 4 co. 1 e 5 D.Lgs. 231/2002 (BCE + 8 punti).
        """
        ours = _calcoli(_tool(importo=10000, data_scadenza="2026-03-31", data_sollecito="2026-09-30"))
        site = _mora_sito(page, "10000", "2026-03-31", "2026-09-30", previgente=False)
        _assert_mora(ours, site, "due_semestri_2026")
        assert [r[2] for r in site["righe"]] == [10.15, 10.40]
        assert abs(ours["tasso_mora_pct"] - site["righe"][0][2]) < 1e-4

    def test_contratto_ante_2013(self, page):
        """Piano, caso 2 (al limite: regime previgente al D.Lgs. 192/2012).
        Atteso dal piano: BCE 1,00% + 7 punti = 8,00% su 77 giorni (il piano stimava 84,15 con
        divisore 366; il sito usa 365 e da' 84,38); il tool applica sempre 8 punti (9,00%) e
        divide per 366: 94,67. Norma: art. 5 D.Lgs. 231/2002 nel testo anteriore al D.Lgs.
        192/2012 (maggiorazione di 7 punti per le transazioni concluse entro il 31/12/2012).
        Il sito forza la casella "Transazione conclusa entro il 31/12/2012" per date del 2012.
        """
        ours = _calcoli(_tool(importo=5000, data_scadenza="2012-10-15", data_sollecito="2012-12-31"))
        site = _mora_sito(page, "5000", "2012-10-15", "2012-12-31", previgente=True)
        _assert_mora(ours, site, "contratto_ante_2013")

    def test_tasso_convenzionale_2024(self, page):
        """Piano, caso 3 (al limite: anno bisestile, tasso convenzionale 8,5%).
        Atteso dal piano: da leggere sul sito; con divisore 366 850,00, il tool divide per 365
        (anno della scadenza 2023) e da' 852,33. Il sito divide per 365 anche nel 2024.
        Norma: tasso convenzionale pattuito (art. 5 co. 1 D.Lgs. 231/2002; art. 1284 c.c.).
        """
        ours = _calcoli(_tool(importo=10000, data_scadenza="2023-12-31",
                              data_sollecito="2024-12-31", tasso_mora=8.5))
        site = _fisso_sito(page, "10000", "8,5", "2023-12-31", "2024-12-31")
        _assert_mora(ours, {**site, "previgente": None}, "tasso_convenzionale_2024")

    def test_oltre_fine_tabella_2027(self, page):
        """Piano, caso 4 (al limite: sollecito oltre il 31/12/2026, fine della tabella).
        Atteso: 62 giorni di ritardo; a tasso invariato (10,40%) 176,66; il tool calcola solo i
        31 giorni di dicembre 2026 (88,33) senza avvisare. Il sito prosegue con 10,40%.
        Norma: art. 5 co. 2 D.Lgs. 231/2002 (tasso del I semestre 2027 = BCE al 01/01/2027,
        non ancora pubblicato alla data della tabella).
        """
        ours = _calcoli(_tool(importo=10000, data_scadenza="2026-11-30", data_sollecito="2027-01-31"))
        site = _mora_sito(page, "10000", "2026-11-30", "2027-01-31", previgente=False)
        _assert_mora(ours, site, "oltre_fine_tabella_2027")


# ---------------------------------------------------------------------------
# Casi al limite aggiunti
# ---------------------------------------------------------------------------

class TestSollecitoCasiLimite:

    def test_confine_anno_2023_2024(self, page):
        """Al limite: ritardo a cavallo del 31/12/2023 (anno comune -> bisestile).
        Atteso: 16 gg al 12,00% (II sem. 2023) + 15 gg al 12,50% (I sem. 2024) su 100.000.
        Il tool divide per 366 i giorni del 2024 (1.038,32), il sito per 365 (1.039,73).
        Norma: artt. 4 e 5 D.Lgs. 231/2002 (saggio annuo; nessuna regola sul divisore).
        """
        ours = _calcoli(_tool(importo=100000, data_scadenza="2023-12-15", data_sollecito="2024-01-15"))
        site = _mora_sito(page, "100000", "2023-12-15", "2024-01-15", previgente=False)
        _assert_mora(ours, site, "confine_anno_2023_2024")

    def test_pluriennale_2023_2025(self, page):
        """Ritardo di 486 giorni su quattro semestri (12,00 / 12,50 / 12,25 / 11,15%) su 50.000,
        attraverso l'intero 2024 bisestile. Norma: artt. 4 e 5 D.Lgs. 231/2002.
        """
        ours = _calcoli(_tool(importo=50000, data_scadenza="2023-10-31", data_sollecito="2025-02-28"))
        site = _mora_sito(page, "50000", "2023-10-31", "2025-02-28", previgente=False)
        _assert_mora(ours, site, "pluriennale_2023_2025")

    def test_tasso_convenzionale_scadenza_bisestile(self, page):
        """Al limite: tasso convenzionale 8,5% con scadenza nel 2024 (bisestile) e periodo quasi
        tutto nel 2025. Il tool divide l'intero periodo per 366 (anno della scadenza): 847,68;
        il sito per 365: 850,00. Norma: tasso convenzionale (art. 1284 c.c.).
        """
        ours = _calcoli(_tool(importo=10000, data_scadenza="2024-06-30",
                              data_sollecito="2025-06-30", tasso_mora=8.5))
        site = _fisso_sito(page, "10000", "8,5", "2024-06-30", "2025-06-30")
        _assert_mora(ours, {**site, "previgente": None}, "tasso_conv_scadenza_bisestile")

    def test_inizio_tabella_agosto_2002(self, page):
        """Al limite: scadenza 31/08/2002, primo giorno di mora 01/09/2002 (= inizio della
        tabella del tool). Il tool rifiuta ("scadenze anteriori al 01/09/2002") benche' il
        periodo di mora sia coperto; il sito applica 3,35% + 7 = 10,35% su 122 giorni: 345,95.
        Norma: art. 11 D.Lgs. 231/2002 (contratti conclusi dall'08/08/2002); art. 5 nel testo
        originario (BCE + 7 punti).
        """
        r = _tool(importo=10000, data_scadenza="2002-08-31", data_sollecito="2002-12-31")
        site = _mora_sito(page, "10000", "2002-08-31", "2002-12-31", previgente=True)
        assert "errore" not in r, f"tool: {r.get('errore')} | sito: {site['totale']} {site['righe']}"
        _assert_mora(r["calcoli"], site, "inizio_tabella_2002")

    def test_regime_nuovo_2013(self, page):
        """Al limite: primo semestre di applicazione del D.Lgs. 192/2012 (transazione conclusa
        dal 01/01/2013, casella non selezionata): 91 gg all'8,75% + 92 gg all'8,50% su 10.000,
        anno comune. Norma: art. 5 D.Lgs. 231/2002 come modificato dal D.Lgs. 192/2012.
        """
        ours = _calcoli(_tool(importo=10000, data_scadenza="2013-03-31", data_sollecito="2013-09-30"))
        site = _mora_sito(page, "10000", "2013-03-31", "2013-09-30", previgente=False)
        _assert_mora(ours, site, "regime_nuovo_2013")

    def test_transazione_2012_scadenza_2013(self, page):
        """Al limite: stessa scadenza del caso precedente ma transazione conclusa entro il
        31/12/2012 (casella selezionata): il sito applica BCE + 7 punti (7,75% / 7,50%); il tool
        non ha un parametro per la data del contratto e applica sempre 8 punti.
        Norma: art. 3 co. 1 D.Lgs. 192/2012 (nuove regole per le transazioni concluse dal
        01/01/2013); art. 5 D.Lgs. 231/2002 nel testo previgente.
        """
        ours = _calcoli(_tool(importo=10000, data_scadenza="2013-03-31", data_sollecito="2013-09-30"))
        site = _mora_sito(page, "10000", "2013-03-31", "2013-09-30", previgente=True)
        assert site["previgente"], "il sito non ha accettato la casella 'transazione entro il 31/12/2012'"
        _assert_mora(ours, site, "transazione_2012_scadenza_2013")

    def test_maggiorazione_agroalimentare(self):
        """Opzione enumerata del sito: maggiorazione di 2 o 4 punti per la cessione di prodotti
        agricoli e agroalimentari (art. 4 co. 2 D.Lgs. 198/2021). Il tool non ha un parametro
        equivalente (solo tasso_mora libero)."""
        pytest.skip("non confrontabile: il tool non prevede la maggiorazione D.Lgs. 198/2021 "
                    "(opzione PctMaggiorazione 2/4 del sito)")


# ---------------------------------------------------------------------------
# Lettera (redattore del sito): riferimenti numerici del testo
# ---------------------------------------------------------------------------

class TestSollecitoLettera:

    def test_lettera_capitale_valore(self, page):
        """Il capitale riportato nella lettera del sito (unico importo: il sito non calcola
        interessi) coincide con il capitale del tool, letto ciascuno nel proprio formato."""
        ours = _tool(importo=10000, data_scadenza="2026-03-31", data_sollecito="2026-09-30")
        testo_sito = _lettera_sito(page)
        m_sito = re.search(r"€\s*" + _EURO, testo_sito)
        assert m_sito, "importo non trovato nella lettera del sito"
        m_tool = re.search(r"Capitale: Euro ([\d.,]+)", ours["testo_lettera"])
        assert m_tool, "capitale non trovato nella lettera del tool"
        tool_val = float(m_tool.group(1).replace(",", ""))  # formato del tool: 10,000.00
        assert_close(tool_val, parse_euro(m_sito.group(1)), tolerance=_TOL, label="capitale lettera")
        assert re.search(r"entro\s+e\s+non\s+oltre\s+15\s+giorni\s+dal\s+ricevimento", testo_sito), (
            f"termine non trovato nella lettera del sito: {testo_sito[:600]!r}")
        assert "entro e non oltre 15 giorni dal ricevimento" in ours["testo_lettera"]

    def test_lettera_capitale_formato(self, page):
        """La lettera del sito scrive gli importi in formato italiano (€ 10.000,00); il tool
        scrive "Euro 10,000.00", che in una lettera italiana si legge come dieci euro con
        separatori invertiti. Si confronta la stringa dell'importo nei due testi."""
        ours = _tool(importo=10000, data_scadenza="2026-03-31", data_sollecito="2026-09-30")
        testo_sito = _lettera_sito(page)
        importo_sito = re.search(r"€\s*" + _EURO, testo_sito).group(1)
        m_tool = re.search(r"Capitale: Euro ([\d.,]+)", ours["testo_lettera"])
        assert m_tool.group(1) == importo_sito, (
            f"formato importo: tool='{m_tool.group(1)}' sito='{importo_sito}'")

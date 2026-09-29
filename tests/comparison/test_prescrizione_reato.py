"""Comparison tests: prescrizione_reato vs avvocatoandreani.it.

Il tool (``src/tools/diritto_penale.py``) calcola il termine base dell'art. 157 c.p. (massimo
edittale, minimo 6 anni per i delitti e 4 per le contravvenzioni), lo porta al massimo
dell'art. 161 co. 2 c.p. quando ``interruzioni_giorni > 0`` (un quarto; la meta' con recidiva
aggravata, due terzi con recidiva reiterata, il doppio con abitualita'), somma i giorni di
sospensione e restituisce ``data_prescrizione``. Il regime (ordinario fino al 02/08/2017,
Orlando fino al 31/12/2019, blocco dopo il primo grado dal 2020) cambia solo le avvertenze e,
per i fatti dal 2020, aggiunge i termini di improcedibilita' dell'art. 344-bis c.p.p.:
``data_prescrizione`` resta la data "teorica" calcolata sugli artt. 157-161 c.p.

Pagina del sito
---------------
``calcolo-prescrizione-reati.php`` (modulo ``CalcoloPrescrizione``; il vecchio file
``test_prescrizione.py`` lo dava come riservato agli utenti registrati: al 25/09/2026 calcola
senza login). Campi: data del reato e data dell'ultimo atto interruttivo (tre select
giorno/mese/anno ciascuna, anni 2006-2046), ``TipoPena`` (Ammenda, Arresto, Multa,
Reclusione, Sostitutiva), ``PenaEdittale`` in anni interi 1-30 (abilitata SOLO per la
reclusione), checkbox ``Raddoppio`` (art. 157 co. 6 c.p.), ``Recidiva1`` (art. 99 co. 2),
``Recidiva2`` (art. 99 co. 4), ``Abitualita`` (artt. 102, 103, 105), e ``NormativaPrevigente``
(riga di confronto ANTE L. 251/2005, lasciata al default: si legge solo la riga EX).
Il risultato e' una tabella a due colonne per riga:
- "DAL REATO": termine massimo dalla data del reato con l'aumento dell'art. 161 co. 2;
- "DALL'ULTIMO ATTO INTERRUTTIVO": termine base dell'art. 157 riavviato dall'ultimo atto
  (art. 160 co. 3), a titolo informativo.

Convenzioni del sito osservate (Playwright, 25/09/2026):
- il modulo non viene inviato finche' il banner dei cookie (Quantcast) resta senza risposta:
  e' probabilmente l'origine del "richiede la registrazione" di ``test_prescrizione.py``;
  il driver risponde "RIFIUTA TUTTO", che sblocca il calcolo;
- senza data dell'atto interruttivo il sito non restituisce nulla; il suo JavaScript
  (``OnChangeDataReato``) copia la data del reato nella data dell'atto, e con le due date
  uguali la seconda colonna e' il termine base dalla data del reato (nessuna interruzione):
  e' la colonna usata per i casi del tool con ``interruzioni_giorni = 0``;
- la prima colonna applica sempre l'aumento massimo dell'art. 161 co. 2 (anche con atto
  interruttivo coincidente col reato): e' la colonna usata per ``interruzioni_giorni > 0``;
- le sospensioni (art. 159 c.p.) NON sono calcolate: la nota del sito chiede all'utente di
  aggiungerle dopo il calcolo; il test aggiunge i giorni alla data del sito, come prescritto;
- nessuna distinzione di regime (Orlando, blocco dal 2020, improcedibilita' 344-bis c.p.p.);
- la recidiva qualificata rileva solo nell'aumento per le interruzioni, non nel termine
  base (art. 157 co. 2 c.p. non applicato), come nel tool;
- fine mese: 29/02/2016 + 6 anni = 28/02/2022 e 31/08/2015 + 90 mesi = 28/02/2023
  (giorno portato all'ultimo del mese, come ``_add_months`` del tool);
- arresto e ammenda senza anni: termine minimo di 4 anni; multa: 6 anni; sostitutiva: 3 anni
  (art. 157 co. 5 c.p.).
- la seconda colonna puo' precedere la prima (es. reato 01/03/2021, reclusione 10 anni, atto
  01/01/2023: 1 settembre 2033 dal reato, 1 gennaio 2033 dall'atto): il sito stesso qualifica
  la prima come termine massimo "a prescindere" dalla seconda; il tool non chiede la data
  dell'ultimo atto e, con ``interruzioni_giorni > 0``, restituisce sempre quel massimo;
- la nota "Aggiornamento 2020" del sito cita solo la L. 3/2019 (art. 159 co. 2 c.p.), non la
  L. 134/2021 (art. 161-bis c.p., art. 344-bis c.p.p.) ne' il regime Orlando.

Mappatura: delitto -> Reclusione (o Multa con ``pena_massima_anni = 0``); contravvenzione ->
Arresto/Ammenda (il sito non accetta anni per l'arresto: solo pene sotto il minimo).
``LEGAL_TODAY`` e' fissato al 2026-09-25 (``prescritto`` e ``giorni_alla_prescrizione``
dipendono dalla data corrente; la data di prescrizione no).
Tolleranza: date esatte.

Il sito e' un benchmark, non una fonte: gli scostamenti restano registrati e li giudica la
fase 2.
"""

import re
import time
from datetime import date, timedelta

import pytest
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

URL = "https://www.avvocatoandreani.it/servizi/calcolo-prescrizione-reati.php"
OGGI = "2026-09-25"

_MESI = {
    "gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4, "maggio": 5, "giugno": 6,
    "luglio": 7, "agosto": 8, "settembre": 9, "ottobre": 10, "novembre": 11, "dicembre": 12,
}
_DATA = r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})"
_RIGA_EX = re.compile(r"EX L\. 251/2005\s*:\s*" + _DATA + r"\s+" + _DATA)


@pytest.fixture(autouse=True)
def _oggi(monkeypatch):
    """Pin the tool clock so the case is reproducible (only 'prescritto' depends on it)."""
    monkeypatch.setenv("LEGAL_TODAY", OGGI)


# ---------------------------------------------------------------------------
# Tool
# ---------------------------------------------------------------------------

def _tool(**kw) -> dict:
    import src.server  # noqa: F401  (registra i moduli, evita import circolari)
    from src.tools.diritto_penale import prescrizione_reato

    fn = getattr(prescrizione_reato, "fn", prescrizione_reato)
    return fn(**kw)


# ---------------------------------------------------------------------------
# Sito
# ---------------------------------------------------------------------------

def _to_date(g: str, m: str, a: str) -> date:
    return date(int(a), _MESI[m.lower()], int(g))


def _apri_pagina(page) -> None:
    """Open the calculator and answer the consent banner with 'RIFIUTA TUTTO'.

    Finche' il banner Quantcast resta senza risposta il modulo non viene inviato (il click
    su Calcola non produce alcuna navigazione): per questo non basta ``goto`` del conftest,
    che controlla il banner prima che compaia. Si sceglie il rifiuto (opzione piu'
    rispettosa della riservatezza), che sblocca il calcolatore come l'accettazione.
    """
    page.goto(URL, timeout=60000, wait_until="domcontentloaded")
    try:
        page.locator("#more-options-btn").click(timeout=15000)
        page.locator("#reject-all-btn").click(timeout=15000)
    except PlaywrightTimeoutError:
        pass  # banner non comparso (consenso gia' espresso): nulla da rifiutare
    page.wait_for_timeout(1000)


def _select_date(page, prefix: str, iso: str) -> None:
    anno, mese, giorno = iso.split("-")
    page.select_option(f"select[name='Giorno{prefix}']", giorno)
    page.select_option(f"select[name='Mese{prefix}']", mese)
    page.select_option(f"select[name='Anno{prefix}']", anno)


def _site(page, reato: str, tipo_pena: str, anni: int | None = None,
          atto_interruttivo: str | None = None, spunte: tuple[str, ...] = ()) -> dict:
    """Run the site's calculator and return the two dates of the 'EX L. 251/2005' row.

    ``atto_interruttivo`` None reproduces the site's own JavaScript, which copies the date of
    the offence into the date of the last interrupting act.
    """
    time.sleep(1.5)  # rispetto del sito tra una richiesta e l'altra
    _apri_pagina(page)
    _select_date(page, "Reato", reato)
    _select_date(page, "AttoInterr", atto_interruttivo or reato)
    page.select_option("select[name='TipoPena']", tipo_pena)
    page.wait_for_timeout(300)
    if anni is not None:
        page.select_option("select[name='PenaEdittale']", str(anni))
    for nome in spunte:
        page.check(f"input[name='{nome}']", force=True)
    page.click("form[name='CalcoloPrescrizione'] input[type=submit]", force=True)
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(2500)
    assert page.url.endswith("#Res"), f"modulo non inviato (url {page.url})"
    testo = page.inner_text("body")
    m = _RIGA_EX.search(testo)
    assert m, "riga 'EX L. 251/2005' non trovata nel risultato del sito"
    return {
        "dal_reato": _to_date(*m.group(1, 2, 3)),
        "dall_atto": _to_date(*m.group(4, 5, 6)),
    }


def _assert_date(tool_iso: str, sito: date, label: str) -> None:
    assert date.fromisoformat(tool_iso) == sito, (
        f"{label}: tool={tool_iso}, sito={sito.isoformat()}, "
        f"diff={(date.fromisoformat(tool_iso) - sito).days} giorni"
    )


# ---------------------------------------------------------------------------
# Casi del piano
# ---------------------------------------------------------------------------

class TestCasiPiano:

    def test_delitto_sotto_minimo_con_interruzioni(self, page):
        # Piano: termine base 6 anni (minimo per i delitti, art. 157 co. 1 c.p.) prolungato di
        # un quarto per le interruzioni (art. 161 co. 2 c.p.) a 7 anni e 6 mesi: 2023-09-10.
        r = _tool(pena_massima_anni=5, data_commissione="2016-03-10", interruzioni_giorni=1)
        s = _site(page, "2016-03-10", "Reclusione", anni=5, atto_interruttivo="2018-01-01")
        _assert_date(r["data_prescrizione"], s["dal_reato"], "delitto 5 anni + 1/4")

    def test_ultimo_giorno_regime_ordinario_con_sospensioni(self, page):
        # Caso al limite (ultimo giorno prima della L. 103/2017, fatti fino al 02/08/2017;
        # pena sotto il minimo). Piano: regime ordinario, 6 anni (art. 157 co. 1 c.p.) piu'
        # 60 giorni di sospensione (art. 159 c.p.): 2023-10-01.
        # Il sito accetta solo anni interi: 4 al posto di 4,5 (entrambi sotto il minimo di 6
        # anni, stesso termine base). Senza interruzioni si legge la seconda colonna con l'atto
        # coincidente col reato; le sospensioni si aggiungono a mano, come chiede il sito.
        r = _tool(pena_massima_anni=4.5, data_commissione="2017-08-02", sospensioni_giorni=60)
        s = _site(page, "2017-08-02", "Reclusione", anni=4)
        _assert_date(r["data_prescrizione"], s["dall_atto"] + timedelta(days=60),
                     "6 anni + 60 giorni di sospensione")
        assert r["regime"]["nome"].startswith("ordinario")

    def test_periodo_orlando_con_primo_grado(self, page):
        # Piano: 7 anni e 6 mesi: 2025-12-01; dopo la condanna di primo grado il corso e'
        # sospeso fino all'appello per non oltre 1 anno e 6 mesi (art. 159 co. 2 n. 1 c.p. nel
        # testo della L. 103/2017): al piu' tardi 2027-06-01. Il sito non conosce la
        # sospensione Orlando: si confronta la data degli artt. 157-161 c.p.
        r = _tool(pena_massima_anni=6, data_commissione="2018-06-01", interruzioni_giorni=1,
                  data_sentenza_primo_grado="2022-01-10")
        s = _site(page, "2018-06-01", "Reclusione", anni=6, atto_interruttivo="2020-01-01")
        _assert_date(r["data_prescrizione"], s["dal_reato"], "Orlando 6 anni + 1/4")

    def test_contravvenzione_dal_2020_regime_transitorio(self, page):
        # Caso al limite (tipo_reato enumerato: contravvenzione, minimo 4 anni). Piano:
        # 4 anni (art. 157 co. 1 c.p.) + un quarto = 5 anni, 2026-05-15, fermata dalla sentenza
        # di primo grado (art. 161-bis c.p.); improcedibilita' in appello 3 anni (art. 2 co. 5
        # L. 134/2021) dal 2024-05-16: 2027-05-16 (non confrontabile, vedi test dedicato).
        r = _tool(pena_massima_anni=1, data_commissione="2021-05-15", tipo_reato="contravvenzione",
                  interruzioni_giorni=1, data_sentenza_primo_grado="2024-02-01",
                  data_impugnazione="2024-03-01")
        s = _site(page, "2021-05-15", "Arresto", atto_interruttivo="2023-01-01")
        _assert_date(r["data_prescrizione"], s["dal_reato"], "contravvenzione 4 anni + 1/4")

    def test_delitto_dal_2020_regime_ordinario_improcedibilita(self, page):
        # Piano: data di prescrizione teorica 2033-09-01 (10 anni + 1/4, artt. 157 e 161 c.p.),
        # cessata con il primo grado (art. 161-bis c.p.); appello 2 anni dal 2025-10-13 =
        # 2027-10-13, Cassazione 1 anno dal 2027-04-30 = 2028-04-30 (art. 344-bis c.p.p.,
        # non confrontabili).
        r = _tool(pena_massima_anni=10, data_commissione="2021-03-01", interruzioni_giorni=1,
                  data_sentenza_primo_grado="2025-06-30", data_sentenza_appello="2027-01-15",
                  data_impugnazione="2025-09-15")
        s = _site(page, "2021-03-01", "Reclusione", anni=10, atto_interruttivo="2023-01-01")
        _assert_date(r["data_prescrizione"], s["dal_reato"], "delitto 10 anni + 1/4")

    def test_recidiva_reiterata(self, page):
        # Caso al limite (opzione enumerata recidiva). Piano: aumento di due terzi per le
        # interruzioni (art. 161 co. 2 c.p., recidiva art. 99 co. 4): 10 anni, 2025-05-10;
        # l'alternativa del piano (art. 157 co. 2 c.p.: base 9 anni, massimo 15, 2030-05-10)
        # e' da leggere sul sito, che la applica o no.
        r = _tool(pena_massima_anni=6, data_commissione="2015-05-10", interruzioni_giorni=1,
                  recidiva="reiterata")
        s = _site(page, "2015-05-10", "Reclusione", anni=6, atto_interruttivo="2018-01-01",
                  spunte=("Recidiva2",))
        _assert_date(r["data_prescrizione"], s["dal_reato"], "recidiva reiterata +2/3")


# ---------------------------------------------------------------------------
# Casi al limite aggiunti
# ---------------------------------------------------------------------------

class TestCasiLimite:

    def test_recidiva_aggravata(self, page):
        # Opzione enumerata: recidiva aggravata (art. 99 co. 2 c.p.) -> aumento della meta'
        # (art. 161 co. 2 c.p.): 6 anni + 3 = 9 anni dal 10/05/2015 = 2024-05-10.
        r = _tool(pena_massima_anni=6, data_commissione="2015-05-10", interruzioni_giorni=1,
                  recidiva="aggravata")
        s = _site(page, "2015-05-10", "Reclusione", anni=6, atto_interruttivo="2018-01-01",
                  spunte=("Recidiva1",))
        _assert_date(r["data_prescrizione"], s["dal_reato"], "recidiva aggravata +1/2")

    def test_abitualita(self, page):
        # Opzione enumerata: abitualita' o professionalita' (artt. 102, 103, 105 c.p.) ->
        # il doppio (art. 161 co. 2 c.p.): 12 anni dal 10/05/2015 = 2027-05-10.
        r = _tool(pena_massima_anni=6, data_commissione="2015-05-10", interruzioni_giorni=1,
                  recidiva="abituale")
        s = _site(page, "2015-05-10", "Reclusione", anni=6, atto_interruttivo="2018-01-01",
                  spunte=("Abitualita",))
        _assert_date(r["data_prescrizione"], s["dal_reato"], "abitualita' x2")

    def test_soglia_sopra_minimo_7_anni(self, page):
        # Confine del minimo di 6 anni (art. 157 co. 1 c.p.): con 7 anni vale il massimo
        # edittale; + un quarto = 8 anni e 9 mesi dal 10/03/2016 = 2024-12-10.
        r = _tool(pena_massima_anni=7, data_commissione="2016-03-10", interruzioni_giorni=1)
        s = _site(page, "2016-03-10", "Reclusione", anni=7, atto_interruttivo="2018-01-01")
        _assert_date(r["data_prescrizione"], s["dal_reato"], "delitto 7 anni + 1/4")

    def test_delitto_punito_con_sola_multa(self, page):
        # Opzione del sito "Multa": delitto con pena pecuniaria, termine minimo di 6 anni
        # (art. 157 co. 1 c.p.) -> tool con pena_massima_anni = 0; + 1/4 = 2023-09-10.
        r = _tool(pena_massima_anni=0, data_commissione="2016-03-10", interruzioni_giorni=1)
        s = _site(page, "2016-03-10", "Multa", atto_interruttivo="2018-01-01")
        _assert_date(r["data_prescrizione"], s["dal_reato"], "multa: 6 anni + 1/4")

    def test_contravvenzione_punita_con_sola_ammenda(self, page):
        # Opzione del sito "Ammenda": contravvenzione con pena pecuniaria, minimo 4 anni
        # (art. 157 co. 1 c.p.) -> tool contravvenzione con pena 0; + 1/4 = 5 anni, 2021-03-10.
        r = _tool(pena_massima_anni=0, data_commissione="2016-03-10",
                  tipo_reato="contravvenzione", interruzioni_giorni=1)
        s = _site(page, "2016-03-10", "Ammenda", atto_interruttivo="2018-01-01")
        _assert_date(r["data_prescrizione"], s["dal_reato"], "ammenda: 4 anni + 1/4")

    def test_29_febbraio_senza_interruzioni(self, page):
        # Aritmetica delle date: 29/02/2016 + 6 anni (art. 157 co. 1 c.p., nessuna
        # interruzione) cade in un anno non bisestile -> 2022-02-28 (ultimo giorno del mese).
        # Seconda colonna del sito con atto interruttivo coincidente col reato.
        r = _tool(pena_massima_anni=6, data_commissione="2016-02-29")
        s = _site(page, "2016-02-29", "Reclusione", anni=6)
        _assert_date(r["data_prescrizione"], s["dall_atto"], "29/02 + 6 anni")

    def test_31_agosto_fine_mese(self, page):
        # Data di agosto a fine mese: 31/08/2015 + 7 anni e 6 mesi (6 + 1/4, art. 161 co. 2
        # c.p.) = 90 mesi -> febbraio 2023, giorno portato al 28: 2023-02-28.
        r = _tool(pena_massima_anni=6, data_commissione="2015-08-31", interruzioni_giorni=1)
        s = _site(page, "2015-08-31", "Reclusione", anni=6, atto_interruttivo="2017-01-10")
        _assert_date(r["data_prescrizione"], s["dal_reato"], "31/08 + 90 mesi")

    def test_pena_massima_30_anni_limite_superiore(self, page):
        # Limite superiore del menu PenaEdittale del sito (30 anni): nessun tetto al termine
        # base (art. 157 co. 1 c.p., massimo edittale) ne' all'aumento di un quarto per le
        # interruzioni (art. 161 co. 2 c.p.): 30 + 7,5 = 37 anni e 6 mesi (450 mesi) dal
        # 15/01/2010 = 2047-07-15.
        r = _tool(pena_massima_anni=30, data_commissione="2010-01-15", interruzioni_giorni=1)
        s = _site(page, "2010-01-15", "Reclusione", anni=30, atto_interruttivo="2012-01-01")
        _assert_date(r["data_prescrizione"], s["dal_reato"], "reclusione 30 anni + 1/4")


# ---------------------------------------------------------------------------
# Casi non confrontabili
# ---------------------------------------------------------------------------

class TestNonConfrontabili:

    def test_improcedibilita_344_bis(self):
        # Tool: appello 2027-05-16 (transitorio 3 anni) nel caso contravvenzione 2021 e
        # appello 2027-10-13 / Cassazione 2028-04-30 nel caso delitto 2021 (art. 344-bis
        # c.p.p.; art. 2 co. 5 L. 134/2021). Il sito non calcola l'improcedibilita'.
        pytest.skip("il sito non calcola l'improcedibilita' dell'art. 344-bis c.p.p.")

    def test_sospensione_orlando(self):
        # Tool: sospensione fino a 18 mesi dopo la condanna di primo grado (art. 159 co. 2
        # n. 1 c.p., L. 103/2017), al piu' tardi 2027-06-01 per il fatto del 01/06/2018.
        pytest.skip("il sito non distingue il regime Orlando ne' calcola le sospensioni")

    def test_raddoppio_termini(self):
        # Sito (Reclusione 5, reato 10/03/2016, spunta Raddoppio): 10/03/2031 (12 anni + 1/4).
        # Il tool non gestisce il raddoppio dell'art. 157 co. 6 c.p. (lo esclude nel docstring).
        pytest.skip("il tool non gestisce il raddoppio dei termini (art. 157 co. 6 c.p.)")

    def test_pena_sostitutiva(self):
        # Sito (Sostitutiva, reato 10/03/2016): 10/12/2019 (3 anni + 1/4, art. 157 co. 5 c.p.).
        # Il tool non ha un'opzione per le pene diverse da detentiva e pecuniaria.
        pytest.skip("il tool non gestisce il termine di 3 anni dell'art. 157 co. 5 c.p.")

"""Comparison tests: interessi_mora vs avvocatoandreani.it/servizi/interessi_moratori.php.

Norma: art. 5 D.Lgs. 231/2002 (tasso di riferimento BCE semestrale, gennaio e luglio)
+ 8 punti (art. 5 co. 2 D.Lgs. 231/2002 come modificato dal D.Lgs. 192/2012; per le
transazioni concluse fino al 31/12/2012 la maggiorazione era di 7 punti).
Convenzione osservata: anno civile di 365 giorni anche nei bisestili (formula del sito
I = D x S x N / 36500), dies a quo non computatur, niente anatocismo.
Tolleranza: 0,01 euro sugli importi. Il valore 0.0101 evita solo il rumore della
virgola mobile su una differenza di esattamente un centesimo (il sito somma righe gia'
arrotondate, il tool arrotonda il totale).
"""

import os

os.environ.setdefault("LEGAL_TODAY", "2026-09-25")

import re

import pytest

from tests.comparison.conftest import assert_close, goto, parse_euro

TOL = 0.0101
URL = "interessi_moratori.php"


def _site(page, capitale, data_inizio, data_fine, previgente=False):
    """Drive the form; return (totale, righe) or (None, []) if no result.

    previgente=True ticks 'Transazione conclusa entro il 31/12/2012' (maggiorazione +7).
    Rows are (dal, al, tasso_pct, giorni, interessi).

    Site quirks handled here: (1) the Quantcast footer overlays the submit button, so the
    click sends no POST -> the real form is submitted programmatically; (2) the form keeps
    state between submissions (a stale '+7' note carried into a 2026 calculation), so every
    call runs in a brand-new browser context; (3) the capital field is only parsed reliably
    after a blur (without it 10000 was echoed back as 1.000,00), so we Tab out of it and
    check the 'Capitale:' echo of the result page against the input.
    """
    ctx = page.context.browser.new_context()
    pg = ctx.new_page()
    try:
        goto(pg, URL, wait_ms=3000)  # let the page scripts settle before touching the form
        ai, mi, gi = data_inizio.split("-")
        af, mf, gf = data_fine.split("-")
        pg.fill("input[name='Capitale']", str(int(capitale)))
        pg.press("input[name='Capitale']", "Tab")
        for name, val in [("GiornoInizio", gi), ("MeseInizio", mi), ("AnnoInizio", ai),
                          ("GiornoFine", gf), ("MeseFine", mf), ("AnnoFine", af)]:
            pg.select_option(f"select[name='{name}']", val, timeout=5000)
        if previgente:
            pg.check("input[name='NormativaPrevigente']", force=True)
        pg.evaluate(
            "document.forms.InteressiMora.requestSubmit(document.getElementById('btn-calc'))"
        )
        pg.wait_for_timeout(3000)
        body = pg.inner_text("body")
        m = re.search(r"Totale\s+interessi\s+moratori[:\s]*€?\s*([\d.]+,\d{2})", body, re.I)
        cap = re.search(r"Capitale:\s*€\s*([\d.]+,\d{2})", body)
        if m and cap:
            assert parse_euro(cap.group(1)) == float(capitale), (
                f"il sito ha letto un capitale diverso: {cap.group(1)}"
            )
        rows = re.findall(
            r"(\d{2}/\d{2}/\d{4})\t(\d{2}/\d{2}/\d{4})\t€ [\d.,]+\t([\d,]+)%[^\t]*\t(\d+)\t€ ([\d.,]+)",
            body,
        )
        pg.wait_for_timeout(1000)
        return (parse_euro(m.group(1)) if m else None), rows
    finally:
        ctx.close()


def _ours(capitale, data_inizio, data_fine):
    import src.server  # noqa: F401
    from src.tools.tassi_interessi import interessi_mora

    fn = getattr(interessi_mora, "fn", interessi_mora)
    return fn(capitale=capitale, data_inizio=data_inizio, data_fine=data_fine)


def _confronta(page, capitale, di, df, label, previgente=False):
    site, rows = _site(page, capitale, di, df, previgente)
    if site is None:
        pytest.skip(f"{label}: il sito non restituisce un totale per questo input")
    r = _ours(capitale, di, df)
    assert "errore" not in r, r
    assert_close(r["totale_interessi"], site, TOL, label)
    return r, rows


class TestInteressiMoraComparison:

    def test_cambio_semestre_2026(self, page):
        # Piano: 515,19 = 91 gg al 10,15% (BCE 2,15+8) + 92 gg al 10,40% (BCE 2,40+8,
        # comunicato MEF GU n. 163 del 16/07/2026). Art. 5 D.Lgs. 231/2002. [limite: cambio semestre]
        r, rows = _confronta(page, 10000, "2026-03-31", "2026-09-30", "cambio_semestre_2026")
        assert [(float(t.replace(",", ".")), int(g)) for _, _, t, g, _ in rows] == [
            (p["tasso_mora_pct"], p["giorni"]) for p in r["periodi"]
        ]

    def test_anno_2023_salti_bce(self, page):
        # Piano: 1.126,16 = 180 gg al 10,50%, 184 al 12,00%, 1 al 12,50%. Art. 5 D.Lgs. 231/2002.
        _confronta(page, 10000, "2023-01-01", "2024-01-01", "anno_2023")

    def test_anno_bisestile_2024(self, page):
        # Piano: 1.237,40 con divisore 365, 1.234,02 con 366 (convenzione da leggere dal sito).
        # Sito: formula I = D x S x N / 36500 -> divisore 365. [limite: bisestile]
        _confronta(page, 10000, "2024-01-01", "2024-12-31", "bisestile_2024")

    def test_anno_2012_regime_previgente_inferito_dal_sito(self, page):
        # Anno 2012 con la casella "entro il 31/12/2012" SPENTA (default): il sito applica
        # comunque BCE 1,00% + 7 = 8,00% (infera il regime dalla data di inizio <= 31/12/2012,
        # art. 3 co. 1 D.Lgs. 192/2012); atteso 800,00 (piano). Il tool applica sempre +8
        # (9,00%) e da' 900,00. [limite: anno di tabella 2012]
        _confronta(page, 10000, "2012-01-01", "2012-12-31", "2012_default")

    def test_anno_2012_casella_previgente_accesa(self, page):
        # Piano: transazione conclusa prima del 01/01/2013 -> BCE 1,00% + 7 = 8,00% per
        # 365 gg = 800,00 (art. 5 D.Lgs. 231/2002 ante D.Lgs. 192/2012). Casella accesa sul
        # sito. Il tool non ha il parametro e da' 900,00. [limite: regime previgente]
        _confronta(page, 10000, "2012-01-01", "2012-12-31", "2012_previgente", previgente=True)

    def test_confine_31_12_2012_01_01_2013(self, page):
        # Confine del regime: data inizio 31/12/2012 (ancora +7 sul sito, 7,75% nel 2013)
        # contro il tool che applica 8,75%. D.Lgs. 192/2012 art. 3: +8 per le transazioni
        # concluse dal 01/01/2013. [limite: confine di regime]
        _confronta(page, 10000, "2012-12-31", "2013-01-31", "confine_2012_2013")

    def test_anno_2013_regime_vigente(self, page):
        # Dal 01/01/2013 BCE + 8: 2013 = 8,75% (180 gg) e 8,50% (184 gg) = 860,00.
        # Art. 5 D.Lgs. 231/2002 come modificato dal D.Lgs. 192/2012. [limite: primo anno del +8]
        _confronta(page, 10000, "2013-01-01", "2013-12-31", "anno_2013")

    def test_anno_2003_regime_previgente(self, page):
        # Anno 2003 (BCE 2,85% e 2,10% per semestre): D.Lgs. 231/2002 nel testo originale, +7.
        # Atteso sito 944,49 (9,85% e 9,10%); il tool applica +8 -> 1.044,22.
        _confronta(page, 10000, "2003-01-01", "2003-12-31", "anno_2003")

    def test_periodo_a_cavallo_di_agosto(self, page):
        # Periodo intra-semestre che attraversa agosto (nessun rilievo per la mora,
        # tasso di luglio 2025). Art. 5 co. 2 lett. b D.Lgs. 231/2002. [limite: agosto]
        _confronta(page, 25000, "2025-07-15", "2025-08-31", "agosto_2025")

    def test_capodanno_un_giorno(self, page):
        # Un solo giorno a cavallo di anno (dies a quo escluso): 01/01/2026 al tasso
        # del I semestre 2026. [limite: confine di anno e di semestre della tabella]
        _confronta(page, 10000, "2025-12-31", "2026-01-01", "capodanno_1g")

    def test_oltre_fine_tabella_2027(self, page):
        # Periodo che supera il 31/12/2026 (fine della tabella del tool): il sito prosegue
        # con l'ultimo tasso (10,40%: 88,33), il tool smette di contare in silenzio (0,00).
        # [limite: oltre la tabella]
        _confronta(page, 10000, "2026-12-31", "2027-01-31", "oltre_tabella")

    def test_esordio_2002(self, page):
        # Piano: periodi anteriori all'08/08/2002 fuori ambito (art. 11 D.Lgs. 231/2002).
        # Il sito parte dal 2002; dal 01/09/2002 BCE 3,35% +7 = 10,35% (sito 343,11),
        # il tool +8 = 11,35% (376,26). [limite: primo anno della tabella]
        _confronta(page, 10000, "2002-09-01", "2002-12-31", "esordio_2002")

    def test_data_anteriore_2002_non_selezionabile(self, page):
        # Piano: 2001-01-01 -> 2002-12-31, il tool applica il 10,40% dell'ultima riga (2.077,15).
        # Il sito non offre anni anteriori al 2002 (art. 11 D.Lgs. 231/2002).
        pytest.skip("Il sito offre solo anni dal 2002: caso non confrontabile")

    def test_maggiorazione_prodotti_agricoli(self, page):
        pytest.skip("Il sito offre la maggiorazione art. 4 co. 2 D.Lgs. 198/2021 (2% o 4%) "
                    "per prodotti agricoli/agroalimentari; il tool non ha il parametro")

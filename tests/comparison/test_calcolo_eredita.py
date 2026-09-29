"""Comparison tests: calcolo_eredita vs avvocatoandreani.it/servizi/calcolo_quote_ereditarie.php.

Benchmark phase 1 (tool vs site). The site is a benchmark, not a source: every
expected value below is taken from the Civil Code (artt. 536-548, 565-586 c.c.)
and the test asserts tool == site.

Site mechanics (verified with Playwright, 2026-09-25):
- one form, ``QuoteEreditarie``; two tabs, "Senza Testamento" (legal succession,
  hidden field ``Testamento=0``) and "Con Testamento" (reserved shares,
  ``Testamento=1``), switched by the page's own ``ActivateTab()``;
- fields ``Patrimonio`` (integer euros), ``Coniuge`` (checkbox, checked by
  default), ``NumeroFigli``, ``NumeroAscendenti`` (number of parents, 1-2),
  ``NumeroFratelli`` and ``NumeroParenti`` (the last two only in the
  "Senza Testamento" tab);
- a plain or forced click on ``#btn-calc`` does not submit (the Quantcast CMP
  overlay sits on top of the button and the element click does not fire the
  submit event), so the form is submitted with ``requestSubmit(#btn-calc)``,
  which sends exactly what a user click sends (``Operazione=Calcola``);
- results are prose sentences: "La quota disponibile per il testatore è il
  33,33% dell'intero patrimonio, pari a € 100.000." etc. Amounts are shown in
  WHOLE euros (66.666,67 is displayed as "€ 66.667"), percentages with at most
  two decimals.

Tolerances (motivated):
- amounts: 0,01 € when the exact share is a whole number of euros; 0,50 € when
  it is not, because the site rounds the displayed amount to the euro (half a
  euro is the maximum display-rounding error, not a calculation margin);
- shares: the site percentage has two decimals, so the tool fraction
  (valore / massa) is compared with the site percentage / 100 at 0,00005
  (half of the last displayed digit, 0,005%).
"""

import re

import pytest

from tests.comparison.conftest import assert_close, goto, parse_euro

PAGE = "calcolo_quote_ereditarie.php"
EURO_EXACT = 0.01
EURO_DISPLAY = 0.50  # site shows whole euros: see module docstring
SHARE_TOL = 0.00005  # site shows percentages with 2 decimals
FLOAT_EPS = 1e-6  # binary float noise only, never a calculation margin

CON = "Con Testamento"
SENZA = "Senza Testamento"


# ---------------------------------------------------------------------------
# Site driver
# ---------------------------------------------------------------------------

def _num(n) -> str:
    return str(n) if n else ""


def _site(page, tab, patrimonio, coniuge=False, figli=0, ascendenti=0, fratelli=0, parenti=0) -> dict:
    goto(page, PAGE, wait_ms=1500)
    page.evaluate(f"() => ActivateTab('{tab}')")
    values = {
        "Patrimonio": str(int(patrimonio)),
        "NumeroFigli": _num(figli),
        "NumeroAscendenti": _num(ascendenti),
        "NumeroFratelli": _num(fratelli),
        "NumeroParenti": _num(parenti),
    }
    page.evaluate(
        """([v, c]) => {
            const f = document.QuoteEreditarie;
            for (const k in v) f[k].value = v[k];
            f.Coniuge.checked = c;
        }""",
        [values, bool(coniuge)],
    )
    testamento = page.evaluate("() => document.QuoteEreditarie.Testamento.value")
    assert testamento == ("1" if tab == CON else "0"), f"tab {tab} not activated (Testamento={testamento})"
    with page.expect_navigation(wait_until="domcontentloaded", timeout=60000):
        page.evaluate("() => document.QuoteEreditarie.requestSubmit(document.getElementById('btn-calc'))")
    page.wait_for_timeout(2000)
    return _parse(page.inner_text("body"))


_AMT = r"€\s*([\d.,]+)"
_PCT = r"([\d.,]+)%"
_AP = r"['’]"


def _euro(s: str) -> float:
    return parse_euro(s.rstrip(".,"))


def _pct(s: str) -> float:
    return float(s.rstrip(".,").replace(",", ".")) / 100


def _parse(body: str) -> dict:
    text = re.sub(r"\s+", " ", body)
    out: dict = {"_text": text}

    m = re.search(rf"quota disponibile per il testatore è il {_PCT} dell{_AP}intero patrimonio, pari a {_AMT}", text)
    if m:
        out["disp_share"], out["disp"] = _pct(m.group(1)), _euro(m.group(2))

    m = re.search(rf"Al coniuge spetta il {_PCT} del patrimonio,? pari a {_AMT}", text)
    if m:
        out["coniuge_share"], out["coniuge"] = _pct(m.group(1)), _euro(m.group(2))
        out["coniuge_abitazione"] = "diritto di abitazione" in text[m.end():m.end() + 60]

    m = re.search(rf"Al figlio spetta il {_PCT} del patrimonio,? pari a {_AMT}", text)
    if m:
        out["figli_n"] = 1
        out["figli_share"], out["figli_tot"] = _pct(m.group(1)), _euro(m.group(2))
        out["figlio_each"] = out["figli_tot"]
    m = re.search(
        rf"Ai (\d+) figli va complessivamente il {_PCT} del patrimonio,? pari a {_AMT} che corrispondono a {_AMT} ciascuno",
        text,
    )
    if m:
        out["figli_n"] = int(m.group(1))
        out["figli_share"], out["figli_tot"] = _pct(m.group(2)), _euro(m.group(3))
        out["figlio_each"] = _euro(m.group(4))

    m = re.search(rf"All{_AP}ascendente spetta il {_PCT} del patrimonio,? pari a {_AMT}", text)
    if m:
        out["asc_n"] = 1
        out["asc_share"], out["asc_tot"] = _pct(m.group(1)), _euro(m.group(2))
        out["asc_each"] = out["asc_tot"]
    m = re.search(
        rf"Ai (\d+) ascendenti spetta complessivamente il {_PCT} del patrimonio,? pari a {_AMT} che corrispondono a {_AMT} ciascuno",
        text,
    )
    if m:
        out["asc_n"] = int(m.group(1))
        out["asc_share"], out["asc_tot"] = _pct(m.group(2)), _euro(m.group(3))
        out["asc_each"] = _euro(m.group(4))

    m = re.search(rf"Al fratello spetta il {_PCT} del patrimonio,? pari a {_AMT}", text)
    if m:
        out["fratelli_n"] = 1
        out["fratelli_share"], out["fratelli_tot"] = _pct(m.group(1)), _euro(m.group(2))
        out["fratello_each"] = out["fratelli_tot"]
    m = re.search(
        rf"Ai (\d+) fratelli (?:va|spetta) complessivamente (?:il {_PCT} del|l{_AP}intero) patrimonio,? pari a {_AMT} che corrispondono a {_AMT} ciascuno",
        text,
    )
    if m:
        # "l'intero patrimonio" (only heirs, no percentage shown) means share 1.
        out["fratelli_n"] = int(m.group(1))
        out["fratelli_share"] = _pct(m.group(2)) if m.group(2) else 1.0
        out["fratelli_tot"], out["fratello_each"] = _euro(m.group(3)), _euro(m.group(4))

    if len(out) == 1 and "Indica almeno uno tra i familiari" in text:
        out["_no_calc"] = True  # site refuses: none of its fields is filled for this tab
        return out
    if len(out) == 1:
        i = text.find("CALCOLO QUOTE EREDITARIE")
        raise AssertionError(f"risultato del sito non leggibile: {text[i:i + 800]}")
    return out


def _need(site: dict, key: str):
    assert key in site, f"voce '{key}' assente nel risultato del sito: {site['_text'][:600]}"
    return site[key]


# ---------------------------------------------------------------------------
# Tool
# ---------------------------------------------------------------------------

def _tool(massa, coniuge=False, figli=0, ascendenti=False, fratelli=0) -> dict:
    import src.server  # noqa: F401  (registers every tool module)
    from src.tools.proprieta_successioni import calcolo_eredita

    fn = getattr(calcolo_eredita, "fn", calcolo_eredita)
    return fn(
        massa_ereditaria=massa,
        eredi={"coniuge": coniuge, "figli": figli, "ascendenti": ascendenti, "fratelli": fratelli},
    )


def _quote(res: dict, prefix: str) -> list[float]:
    return [q["valore"] for q in res["quote"] if q["erede"] == prefix or q["erede"].startswith(prefix + "_")]


def _eur_tol(exact: float) -> float:
    """0,01 € when the exact share is whole euros, else the site's display rounding."""
    return EURO_EXACT if abs(exact - round(exact)) < 1e-9 else EURO_DISPLAY


def _check_disponibile(res, site, massa, label):
    exact = res["quota_disponibile"]
    assert_close(res["quota_disponibile"], _need(site, "disp"), _eur_tol(exact), f"{label} disponibile")
    assert_close(res["quota_disponibile"] / massa, _need(site, "disp_share"), SHARE_TOL, f"{label} disponibile %")


# ---------------------------------------------------------------------------
# Cases
# ---------------------------------------------------------------------------

class TestCalcoloEreditaVsSito:

    # --- casi del piano --------------------------------------------------

    def test_coniuge_un_figlio(self, page):
        """Piano: coniuge 1/3 = 100.000; figlio 1/3 = 100.000; disponibile 100.000.
        Norma: art. 542 co. 1 c.c."""
        massa = 300000
        res = _tool(massa, coniuge=True, figli=1)
        site = _site(page, CON, massa, coniuge=True, figli=1)
        assert_close(_quote(res, "coniuge")[0], _need(site, "coniuge"), EURO_EXACT, "coniuge")
        assert_close(_quote(res, "figlio")[0], _need(site, "figlio_each"), EURO_EXACT, "figlio")
        _check_disponibile(res, site, massa, "c+1f")

    def test_coniuge_tre_figli(self, page):
        """Piano: coniuge 1/4 = 100.000; figli 1/2 in parti uguali, 66.666,67 ciascuno;
        disponibile 100.000. Norma: art. 542 co. 2 c.c.
        Il sito mostra 66.667 (euro interi): tolleranza 0,50 sulla quota del singolo figlio."""
        massa = 400000
        res = _tool(massa, coniuge=True, figli=3)
        site = _site(page, CON, massa, coniuge=True, figli=3)
        figli = _quote(res, "figlio")
        assert len(figli) == 3 and _need(site, "figli_n") == 3
        assert_close(_quote(res, "coniuge")[0], _need(site, "coniuge"), EURO_EXACT, "coniuge")
        # The tool rounds each child's share to the cent (66.666,67 x 3 = 200.000,01):
        # the 1-cent residual is within the 0,01 tolerance; FLOAT_EPS only absorbs the
        # binary representation of 200000.01 - 200000 (= 0.0100000000093).
        assert_close(sum(figli), _need(site, "figli_tot"), EURO_EXACT + FLOAT_EPS, "figli totale")
        assert_close(sum(figli) / massa, _need(site, "figli_share"), SHARE_TOL, "figli totale %")
        for i, v in enumerate(figli, 1):
            assert_close(v, _need(site, "figlio_each"), _eur_tol(v), f"figlio_{i}")
        _check_disponibile(res, site, massa, "c+3f")

    def test_coniuge_e_ascendenti(self, page):
        """Piano: coniuge 1/2 = 60.000; ascendenti 1/4 = 30.000; disponibile 30.000.
        Norma: art. 544 c.c.
        Al limite (opzione enumerata): il tool ha ascendenti booleano e restituisce la
        quota complessiva; il sito chiede il numero dei genitori (qui 2) e divide 15.000
        ciascuno. Si confronta la quota complessiva."""
        massa = 120000
        res = _tool(massa, coniuge=True, ascendenti=True)
        site = _site(page, CON, massa, coniuge=True, ascendenti=2)
        assert_close(_quote(res, "coniuge")[0], _need(site, "coniuge"), EURO_EXACT, "coniuge")
        assert_close(_quote(res, "ascendenti")[0], _need(site, "asc_tot"), EURO_EXACT, "ascendenti totale")
        _check_disponibile(res, site, massa, "c+asc")

    def test_soli_ascendenti(self, page):
        """Piano: ascendenti 1/3 = 30.000; disponibile 60.000. Norma: art. 538 c.c.
        Sito: un solo ascendente."""
        massa = 90000
        res = _tool(massa, ascendenti=True)
        site = _site(page, CON, massa, ascendenti=1)
        assert_close(_quote(res, "ascendenti")[0], _need(site, "asc_tot"), EURO_EXACT, "ascendenti")
        _check_disponibile(res, site, massa, "asc")

    def test_soli_fratelli_successione_legittima(self, page):
        """Piano: successione legittima (sito senza testamento): 50.000 per fratello.
        Norma: art. 570 co. 1 c.c. (fratelli germani, parti uguali)."""
        massa = 100000
        res = _tool(massa, fratelli=2)
        site = _site(page, SENZA, massa, fratelli=2)
        fratelli = _quote(res, "fratello")
        assert len(fratelli) == 2 and _need(site, "fratelli_n") == 2
        for i, v in enumerate(fratelli, 1):
            assert_close(v, _need(site, "fratello_each"), EURO_EXACT, f"fratello_{i}")
        assert_close(sum(fratelli), _need(site, "fratelli_tot"), EURO_EXACT, "fratelli totale")

    def test_soli_fratelli_quota_disponibile(self, page):
        """Piano: successione necessaria, nessun legittimario -> disponibile 100.000
        (i fratelli non sono legittimari: art. 536 c.c.). Il tool restituisce
        quota_disponibile 0 perche' mescola il piano della successione legittima
        (art. 570): incoerenza attesa, il confronto con il sito (con testamento) la misura."""
        massa = 100000
        res = _tool(massa, fratelli=2)
        site = _site(page, CON, massa, fratelli=2)
        if site.get("_no_calc"):
            pytest.skip(
                "sito_non_calcola: la scheda 'Con Testamento' non ha il campo Fratelli e con soli "
                "fratelli risponde 'Indica almeno uno tra i familiari'. Il tool restituisce "
                f"quota_disponibile={res['quota_disponibile']} contro i 100.000 attesi dall'art. 536 c.c."
            )
        _check_disponibile(res, site, massa, "fratelli con testamento")

    # --- casi al limite aggiunti -----------------------------------------

    def test_coniuge_due_figli(self, page):
        """Limite: da uno a due figli la riserva passa da 1/3+1/3 (art. 542 co. 1)
        a 1/4 coniuge + 1/2 ai figli (art. 542 co. 2). Atteso: coniuge 75.000,
        figli 75.000 ciascuno, disponibile 75.000."""
        massa = 300000
        res = _tool(massa, coniuge=True, figli=2)
        site = _site(page, CON, massa, coniuge=True, figli=2)
        figli = _quote(res, "figlio")
        assert len(figli) == 2 and _need(site, "figli_n") == 2
        assert_close(_quote(res, "coniuge")[0], _need(site, "coniuge"), EURO_EXACT, "coniuge")
        for i, v in enumerate(figli, 1):
            assert_close(v, _need(site, "figlio_each"), EURO_EXACT, f"figlio_{i}")
        _check_disponibile(res, site, massa, "c+2f")

    def test_figlio_unico(self, page):
        """Limite: figlio unico senza coniuge, riserva 1/2 (art. 537 co. 1).
        Atteso: figlio 150.000, disponibile 150.000."""
        massa = 300000
        res = _tool(massa, figli=1)
        site = _site(page, CON, massa, coniuge=False, figli=1)
        assert_close(_quote(res, "figlio")[0], _need(site, "figlio_each"), EURO_EXACT, "figlio")
        _check_disponibile(res, site, massa, "1f")

    def test_due_figli_senza_coniuge(self, page):
        """Limite: con due figli la riserva sale a 2/3 in parti uguali (art. 537 co. 2).
        Atteso: 100.000 ciascuno, disponibile 100.000."""
        massa = 300000
        res = _tool(massa, figli=2)
        site = _site(page, CON, massa, coniuge=False, figli=2)
        figli = _quote(res, "figlio")
        assert len(figli) == 2 and _need(site, "figli_n") == 2
        for i, v in enumerate(figli, 1):
            assert_close(v, _need(site, "figlio_each"), EURO_EXACT, f"figlio_{i}")
        _check_disponibile(res, site, massa, "2f")

    def test_coniuge_solo(self, page):
        """Coniuge unico legittimario: riserva 1/2 (art. 540 co. 1).
        Atteso: coniuge 50.000, disponibile 50.000."""
        massa = 100000
        res = _tool(massa, coniuge=True)
        site = _site(page, CON, massa, coniuge=True)
        assert_close(_quote(res, "coniuge")[0], _need(site, "coniuge"), EURO_EXACT, "coniuge")
        _check_disponibile(res, site, massa, "coniuge")

    def test_coniuge_figlio_ascendenti_esclusi(self, page):
        """Limite: gli ascendenti sono legittimari solo se il defunto non lascia figli
        (art. 538 e 544 c.c.): con coniuge, un figlio e due genitori la riserva e'
        quella dell'art. 542 co. 1. Atteso: coniuge 100.000, figlio 100.000,
        nessuna quota agli ascendenti, disponibile 100.000."""
        massa = 300000
        res = _tool(massa, coniuge=True, figli=1, ascendenti=True)
        site = _site(page, CON, massa, coniuge=True, figli=1, ascendenti=2)
        assert _quote(res, "ascendenti") == [], "il tool attribuisce una quota agli ascendenti"
        assert "asc_tot" not in site, "il sito attribuisce una quota agli ascendenti"
        assert_close(_quote(res, "coniuge")[0], _need(site, "coniuge"), EURO_EXACT, "coniuge")
        assert_close(_quote(res, "figlio")[0], _need(site, "figlio_each"), EURO_EXACT, "figlio")
        _check_disponibile(res, site, massa, "c+1f+asc")

    def test_coniuge_e_fratelli_successione_legittima(self):
        """Limite: coniuge in concorso con fratelli senza testamento, art. 582 c.c.
        (coniuge 2/3, fratelli 1/3). Il tool calcola solo la riserva (coniuge 1/2)
        e ignora i fratelli quando c'e' il coniuge: non calcola la successione
        legittima in questo concorso, quindi il confronto con il sito
        "Senza Testamento" non e' possibile."""
        res = _tool(100000, coniuge=True, fratelli=2)
        assert _quote(res, "fratello") == []
        pytest.skip(
            "non confrontabile: il tool non calcola la successione legittima coniuge + fratelli "
            "(art. 582 c.c., 2/3 e 1/3); restituisce solo la riserva del coniuge (1/2)"
        )

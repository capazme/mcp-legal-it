"""Comparison tests: pignoramento_stipendio vs avvocatoandreani.it.

Site page: https://www.avvocatoandreani.it/servizi/calcolo-pignoramento-stipendio-pensione.php
(form ``PignoramentoStipendioPensione``, POST to itself, results in two tables:
"Parametri per il calcolo" echoes the inputs, "Calcolo dello stipendio/della
pensione mensile pignorabile" carries the figures).

Norms: art. 545 c.p.c. (co. 3 alimentari, co. 4 un quinto, co. 5 concorso,
co. 7 pensioni: impignorabile il doppio dell'assegno sociale con un minimo di
1.000 euro, testo dell'art. 21-bis DL 115/2022 conv. L. 142/2022); art. 72-ter
DPR 602/1973 (agente della riscossione: 1/10 fino a 2.500, 1/7 fino a 5.000,
1/5 oltre).

Driver notes:
- The site remembers the last submitted radio values across page loads, so
  every radio is set explicitly on each run and the echoed parameters are
  asserted before reading the figures.
- Clicks on this page are unreliable: a coordinate click on ``#btn-calc`` hits an
  ad overlay, and when the consent banner is dismissed before the CMP has
  settled (as ``conftest.goto`` does, and intermittently even after a wait) every
  click event is swallowed, so no POST is ever sent. The driver therefore sets
  the form controls directly and posts the form with ``HTMLFormElement.submit``
  plus the ``Op=Calcola`` pair the submit button would add. The server-side
  calculation, which is what is compared, is unchanged.
- The site uses the 2026 assegno sociale (546,24 euro, impignorabile
  1.092,48) and does not let the user change it; the "Credito alimentare"
  option takes a free fraction (default 1/5), which the tests set to 1/3 to
  mirror the tool's fixed maximum.
"""

import re

import pytest

from tests.comparison.conftest import assert_close, goto, parse_euro

PAGE = "calcolo-pignoramento-stipendio-pensione.php"

# Brief tolerance: 0,01 euro on amounts. The 1e-9 only absorbs binary float
# noise in the difference (e.g. |1.50 - 1.51| = 0.010000000000000009); it does
# not widen the tolerance.
TOL = 0.01 + 1e-9

ASSEGNO_SOCIALE_2026 = 546.24


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _tool(**kwargs) -> dict:
    import src.server  # noqa: F401 - registers every tool module (avoids circular imports)
    from src.tools.atti_giudiziari import pignoramento_stipendio

    fn = getattr(pignoramento_stipendio, "fn", pignoramento_stipendio)
    r = fn(**kwargs)
    assert "errore" not in r, r
    return r


def _it(amount: float) -> str:
    """Italian input format: 2500.01 -> '2500,01'."""
    return f"{amount:.2f}".replace(".", ",")


_SET_RADIO = """([name, value]) => {
    const el = document.querySelector(`form#PignoramentoStipendioPensione input[name=${name}][value="${value}"]`);
    el.checked = true;
}"""

_SUBMIT = """() => {
    const f = document.forms['PignoramentoStipendioPensione'];
    let op = f.querySelector('input[type=hidden][name=Op]');
    if (!op) { op = document.createElement('input'); op.type = 'hidden'; op.name = 'Op'; f.appendChild(op); }
    op.value = 'Calcola';
    HTMLFormElement.prototype.submit.call(f);
}"""


def _radio(page, name: str, value: str) -> None:
    page.evaluate(_SET_RADIO, [name, value])


def _rows(table_text: str) -> dict:
    """'Label:\\tvalue' lines -> {label without trailing colon: value}."""
    out = {}
    for line in table_text.splitlines():
        if "\t" not in line:
            continue
        label, value = line.split("\t", 1)
        out[label.strip().rstrip(":").strip()] = value.strip()
    return out


def _site(page, importo: float, *, pensione: bool = False, fiscale: bool = False,
          alimentare: str | None = None) -> dict:
    """Drive the site form and return the parsed result.

    Keys: pignorabile, disponibile, frazione, minimo, assegno, eccedenza
    (None when the site omits the row), params (echo table).
    """
    goto(page, PAGE, wait_ms=1500)
    page.fill("#TotalePignoramento", "")
    _radio(page, "TipoImporto", "2" if pensione else "1")
    _radio(page, "FreqImporto", "1")           # mensile
    _radio(page, "AccreditoConto", "0")        # no accredito su CC (co. 8 not modelled)
    _radio(page, "CreditoAlimentare", "1" if alimentare else "0")
    _radio(page, "TipoCreditore", "2" if fiscale else "1")
    # FrazPers sits in a collapsed block unless "Credito alimentare" is shown: set it directly.
    page.evaluate("v => { document.querySelector('#FrazPers').value = v; }", alimentare or "1/5")
    page.fill("#Importo", _it(importo))
    with page.expect_navigation(wait_until="domcontentloaded", timeout=60000):
        page.evaluate(_SUBMIT)
    page.wait_for_timeout(1200)

    params, calc = None, None
    for t in page.query_selector_all("table"):
        tx = t.inner_text().strip()
        if tx.startswith("Parametri per il calcolo"):
            params = _rows(tx)
        elif tx.startswith("Calcolo dell"):
            calc = _rows(tx)
    assert params is not None and calc is not None, "risultato del sito non trovato"

    # Guard against the site's remembered form state: the echo must match the inputs.
    kind = "Pensione" if pensione else "Stipendio"
    assert parse_euro(params[f"{kind} mensile"]) == pytest.approx(importo, abs=0.001), params
    if alimentare:
        assert params.get("Credito alimentare", "").startswith("Si"), params
    else:
        expected_cred = "Agenzia delle Entrate" if fiscale else "Ordinario"
        assert params.get("Creditore") == expected_cred, params

    low = kind.lower()
    res = {
        "params": params,
        "pignorabile": parse_euro(calc[f"{kind} mensile pignorabile"]),
        "disponibile": (parse_euro(calc[f"{kind} mensile disponibile"])
                        if f"{kind} mensile disponibile" in calc else None),
        "frazione": calc.get(f"Frazione di {low} pignorabile"),
        "minimo": None, "assegno": None, "eccedenza": None,
    }
    for label, value in calc.items():
        if label.startswith("Minimo vitale non pignorabile"):
            res["minimo"] = parse_euro(value)
            m = re.search(r"€\s*([\d.,]+)\s*x\s*2", label)
            res["assegno"] = parse_euro(m.group(1)) if m else None
        elif label == "Quota eccedente il minimo":
            res["eccedenza"] = parse_euro(value)
    return res


def _fraction(quota: float) -> str:
    return {0.1: "1/10", 0.1429: "1/7", 0.2: "1/5", 0.3333: "1/3", 0.5: "1/2"}[round(quota, 4)]


def _compare(r: dict, s: dict, *, pensione: bool) -> None:
    assert_close(r["importo_pignorabile"], s["pignorabile"], TOL, "importo pignorabile")
    if s["frazione"] is not None:
        assert _fraction(r["quota_pignorabile"]) == s["frazione"], (r["quota_pignorabile"], s["frazione"])
    if s["disponibile"] is not None:
        assert_close(r["importo_non_pignorabile"], s["disponibile"], TOL, "importo disponibile")
    if pensione:
        assert_close(r["minimo_impignorabile_pensioni"], s["minimo"], TOL, "minimo impignorabile")
        assert_close(r["base_di_calcolo"], s["eccedenza"], TOL, "eccedenza sul minimo")


# ---------------------------------------------------------------------------
# cases
# ---------------------------------------------------------------------------

class TestPignoramentoStipendio:

    def test_stipendio_ordinario_1500(self, page):
        """Piano: 300,00 euro (un quinto, art. 545 co. 4 c.p.c.)."""
        r = _tool(stipendio_netto_mensile=1500, tipo_credito="ordinario", pensione=False,
                  assegno_sociale_mensile=None)
        s = _site(page, 1500)
        _compare(r, s, pensione=False)

    def test_pensione_ordinario_assegno_2026(self, page):
        """Piano: 81,50 euro - impignorabile 1.092,48 (doppio di 546,24), base 407,52,
        un quinto (art. 545 co. 7 e co. 4 c.p.c.)."""
        r = _tool(stipendio_netto_mensile=1500, tipo_credito="ordinario", pensione=True,
                  assegno_sociale_mensile=ASSEGNO_SOCIALE_2026)
        s = _site(page, 1500, pensione=True)
        assert s["assegno"] == pytest.approx(ASSEGNO_SOCIALE_2026)
        _compare(r, s, pensione=True)

    def test_pensione_ordinario_default_assegno(self, page):
        """Piano: 81,50 euro con l'assegno sociale 2026; il tool senza parametro usa
        l'assegno 2024 (534,41, minimo 1.068,82) e da' 86,24: scostamento atteso di 4,74
        (art. 545 co. 7 c.p.c.). Resta rosso finche' il default non segue l'anno."""
        r = _tool(stipendio_netto_mensile=1500, tipo_credito="ordinario", pensione=True,
                  assegno_sociale_mensile=None)
        s = _site(page, 1500, pensione=True)
        assert_close(
            r["importo_pignorabile"], s["pignorabile"], TOL,
            f"importo pignorabile (minimo tool {r['minimo_impignorabile_pensioni']:.2f}, "
            f"sito {s['minimo']:.2f})",
        )
        _compare(r, s, pensione=True)

    def test_pensione_minimo_1000_prevale(self):
        """Piano: 0,00 euro (2 x 480 = 960, sotto il minimo di 1.000 dell'art. 545 co. 7).
        Non confrontabile: il sito non lascia scegliere l'assegno sociale (usa 546,24 del
        2026, minimo 1.092,48 > 1.000), quindi il pavimento di 1.000 euro non e' raggiungibile."""
        r = _tool(stipendio_netto_mensile=1000, tipo_credito="ordinario", pensione=True,
                  assegno_sociale_mensile=480)
        assert r["minimo_impignorabile_pensioni"] == 1000.0 and r["importo_pignorabile"] == 0.0
        pytest.skip("sito: assegno sociale fisso 2026 (546,24), il minimo di 1.000 euro "
                    "dell'art. 545 co. 7 non e' esercitabile")

    @pytest.mark.parametrize(
        "importo, atteso",
        [
            # Piano: 250,00 (un decimo fino a 2.500, art. 72-ter DPR 602/1973) - confine incluso
            (2500.00, 250.00),
            # Piano: 357,14 (un settimo oltre 2.500 e fino a 5.000)
            (2500.01, 357.14),
            # Aggiunto: 714,29 (un settimo, 5.000 e' ancora nella seconda fascia)
            (5000.00, 714.29),
            # Piano: 1.000,00 (un quinto oltre 5.000, art. 72-ter che rinvia all'art. 545 co. 4)
            (5000.01, 1000.00),
        ],
        ids=["2500_00", "2500_01", "5000_00", "5000_01"],
    )
    def test_fiscale_stipendio_confini(self, page, importo, atteso):
        """Scaglioni dell'agente della riscossione sullo stipendio (art. 72-ter DPR 602/1973)."""
        r = _tool(stipendio_netto_mensile=importo, tipo_credito="fiscale", pensione=False,
                  assegno_sociale_mensile=None)
        s = _site(page, importo, fiscale=True)
        _compare(r, s, pensione=False)
        assert_close(r["importo_pignorabile"], atteso, TOL, "atteso del piano")

    def test_fiscale_pensione_3000(self, page):
        """Piano: da leggere dal sito - il tool sceglie la fascia sull'importo lordo (3.000 ->
        1/7) e la applica all'eccedenza di 1.907,52: 272,50 (con la fascia scelta
        sull'eccedenza sarebbe 1/10 = 190,75). Art. 545 co. 7 c.p.c. + art. 72-ter DPR 602/1973."""
        r = _tool(stipendio_netto_mensile=3000, tipo_credito="fiscale", pensione=True,
                  assegno_sociale_mensile=ASSEGNO_SOCIALE_2026)
        s = _site(page, 3000, pensione=True, fiscale=True)
        _compare(r, s, pensione=True)

    def test_fiscale_pensione_confine_2500_01(self, page):
        """Aggiunto (confine): pensione 2.500,01 -> fascia 1/7 sull'importo lordo, applicata
        all'eccedenza 1.407,53 = 201,08 (art. 545 co. 7 c.p.c. + art. 72-ter DPR 602/1973)."""
        r = _tool(stipendio_netto_mensile=2500.01, tipo_credito="fiscale", pensione=True,
                  assegno_sociale_mensile=ASSEGNO_SOCIALE_2026)
        s = _site(page, 2500.01, pensione=True, fiscale=True)
        _compare(r, s, pensione=True)

    def test_fiscale_pensione_arrotondamento_mezzo_centesimo(self, page):
        """Aggiunto (arrotondamento): pensione 1.107,53, eccedenza 15,05, un decimo = 1,505.
        Arrotondamento commerciale: 1,51. Il tool calcola l'eccedenza in binario
        (15,049999...) e ottiene 1,50; il sito mostra 1,51 (ma disponibile 1.106,03, cioe'
        sottrae l'importo non arrotondato). Differenza di 1 centesimo, dentro la tolleranza
        del brief. Art. 545 co. 7 c.p.c. + art. 72-ter DPR 602/1973."""
        r = _tool(stipendio_netto_mensile=1107.53, tipo_credito="fiscale", pensione=True,
                  assegno_sociale_mensile=ASSEGNO_SOCIALE_2026)
        s = _site(page, 1107.53, pensione=True, fiscale=True)
        _compare(r, s, pensione=True)

    @pytest.mark.parametrize(
        "importo",
        [1092.48, 1092.49, 1100.00],
        ids=["1092_48_soglia", "1092_49_un_centesimo", "1100_00"],
    )
    def test_pensione_soglia_minimo_vitale(self, page, importo):
        """Aggiunto (confine del co. 7): alla soglia 1.092,48 nulla e' pignorabile; a 1.092,49
        l'eccedenza e' 0,01 e il quinto (0,002) si arrotonda a 0,00; a 1.100 il quinto di
        7,52 e' 1,50 (art. 545 co. 7 e co. 4 c.p.c.)."""
        r = _tool(stipendio_netto_mensile=importo, tipo_credito="ordinario", pensione=True,
                  assegno_sociale_mensile=ASSEGNO_SOCIALE_2026)
        s = _site(page, importo, pensione=True)
        _compare(r, s, pensione=True)

    def test_alimentare_stipendio_un_terzo(self, page):
        """Aggiunto (opzione enumerata 'alimentare'): il tool applica il massimo di 1/3 -
        500,00 su 1.500; il sito chiede la frazione (default 1/5), impostata a 1/3.
        Art. 545 co. 3 c.p.c. (misura rimessa al presidente del tribunale)."""
        r = _tool(stipendio_netto_mensile=1500, tipo_credito="alimentare", pensione=False,
                  assegno_sociale_mensile=None)
        s = _site(page, 1500, alimentare="1/3")
        _compare(r, s, pensione=False)

    def test_alimentare_pensione_un_terzo(self, page):
        """Aggiunto: credito alimentare su pensione, 1/3 dell'eccedenza 407,52 = 135,84
        (art. 545 co. 3 e co. 7 c.p.c.)."""
        r = _tool(stipendio_netto_mensile=1500, tipo_credito="alimentare", pensione=True,
                  assegno_sociale_mensile=ASSEGNO_SOCIALE_2026)
        s = _site(page, 1500, pensione=True, alimentare="1/3")
        _compare(r, s, pensione=True)

    def test_concorso_crediti(self):
        """Aggiunto (opzione enumerata 'concorso_crediti'): il tool restituisce 1/2
        (art. 545 co. 5 c.p.c., limite complessivo). Non confrontabile: il sito non ha
        un'opzione per il concorso di crediti."""
        r = _tool(stipendio_netto_mensile=1500, tipo_credito="concorso_crediti", pensione=False,
                  assegno_sociale_mensile=None)
        assert r["importo_pignorabile"] == 750.0
        pytest.skip("sito: nessuna opzione per il concorso di crediti (art. 545 co. 5)")

"""Comparison tests: gratuito_patrocinio vs avvocatoandreani.it.

Site page: https://www.avvocatoandreani.it/servizi/verifica-requisiti-gratuito-patrocinio.php
(form ``VerificaGratuitoPatrocinio``, POST to itself; the result is a set of
tables: "Parametri Inseriti" echoes the inputs, "Familiari Conviventi Indicati"
lists the household, "Sviluppo del Calcolo" carries the income and the limit,
"Conclusioni" states whether the income requirement is met and by how much the
income is under or over the limit).

Norms: DPR 115/2002 art. 76 co. 1 (reddito imponibile non superiore alla
soglia), co. 2 (somma dei redditi del nucleo convivente), co. 3 (redditi esenti
e soggetti a ritenuta a titolo d'imposta), co. 4 (solo reddito personale per i
diritti della personalita' e per gli interessi in conflitto con i familiari),
co. 4-ter (persona offesa dai reati ivi elencati: ammissione in deroga ai limiti
di reddito); art. 92 (processo penale: soglia elevata di 1.032,91 euro per ogni
familiare convivente); D.M. 22 aprile 2025 (GU n. 159 dell'11/07/2025): soglia
13.659,64 euro.

Driver notes:
- Every test gets a fresh browser context (fixture ``page``); the site keeps the
  last submitted form in the session and re-renders it (household included), so
  a reused context would carry the previous household into the next run. The
  echo table is asserted on every run to catch that.
- The household blocks are created by the page script (``App.AddFamConvivente``,
  the same handler the "Nuovo familiare convivente" button calls); the driver
  waits for ``App`` before touching the form.
- The form is posted with ``HTMLFormElement.submit`` plus the ``Op=Verifica``
  pair the submit button would add (same technique as
  test_pignoramento_stipendio.py: button clicks on this site can be swallowed by
  the ad/CMP overlays). The server-side calculation is unchanged.
- The site takes the income year (default 2025, the current one on 2026-09-25)
  and applies the limit of that year: 2025 -> 13.659,64 (D.M. 22 aprile 2025).
  The tool has a single limit (13.659,64), so every comparable case uses 2025.
"""

import re

import pytest

from tests.comparison.conftest import assert_close, goto, parse_euro

PAGE = "verifica-requisiti-gratuito-patrocinio.php"

# Brief tolerance: 0,01 euro on amounts. The 1e-9 only absorbs binary float
# noise in the difference; it does not widen the tolerance.
TOL = 0.01 + 1e-9

SOGLIA_2025 = 13_659.64
AUMENTO_PENALE = 1_032.91

MATERIA = {"civile": "1", "penale": "2"}
RAPPORTO = {"coniuge": "1", "unito": "2", "figlio": "3", "genitore": "4", "fratello": "5", "altro": "9"}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _tool(**kwargs) -> dict:
    import src.server  # noqa: F401 - registers every tool module (avoids circular imports)
    from src.tools.procedura_civile import gratuito_patrocinio

    fn = getattr(gratuito_patrocinio, "fn", gratuito_patrocinio)
    r = fn(**kwargs)
    assert "errore" not in r, r
    return r


def _it(amount: float) -> str:
    """Italian input format: 13659.64 -> '13659,64'."""
    return f"{amount:.2f}".replace(".", ",")


_SET_RADIO = """([name, value]) => {
    const el = document.querySelector(`form#VerificaGratuitoPatrocinio input[name="${name}"][value="${value}"]`);
    el.checked = true;
}"""

_SUBMIT = """() => {
    const f = document.forms['VerificaGratuitoPatrocinio'];
    let op = f.querySelector('input[type=hidden][name=Op]');
    if (!op) { op = document.createElement('input'); op.type = 'hidden'; op.name = 'Op'; f.appendChild(op); }
    op.value = 'Verifica';
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


def _site(page, reddito: float, *, materia: str = "civile", anno: str = "2025",
          familiari: tuple = (), diritti_personalita: bool = False,
          aumento_penale: bool = True) -> dict:
    """Drive the site form and return the parsed result.

    ``familiari`` is a tuple of (rapporto, reddito_imponibile, in_conflitto).
    Keys: ammesso, reddito (reddito complessivo), limite (limite complessivo
    applicato), limite_base, aumento_penale (None if absent), margine (signed:
    positive under the limit, negative over it), params, calc.
    """
    goto(page, PAGE, wait_ms=1500)
    page.wait_for_function(
        "() => typeof App !== 'undefined' && App.FamConvivente && App.AddFamConvivente",
        timeout=30000,
    )
    page.select_option("#Materia", MATERIA[materia])
    page.evaluate("() => App.HideShowFields()")
    page.select_option("#AnnoReddito", anno)
    _radio(page, "DirittiPersonalita", "1" if diritti_personalita else "0")
    _radio(page, "ApplicaAumentoPenale", "1" if aumento_penale else "0")
    page.fill("#RichRedditoImponibile", _it(reddito))
    for i, (rapporto, red, conflitto) in enumerate(familiari):
        if i > 0:
            page.evaluate("() => App.AddFamConvivente()")
            page.wait_for_selector(f"#FamNome-{i}", state="attached", timeout=10000)
        page.fill(f"#FamNome-{i}", f"Familiare {i + 1}")
        page.select_option(f"#FamRapporto-{i}", RAPPORTO[rapporto])
        page.fill(f"#FamRedditoImponibile-{i}", _it(red))
        _radio(page, f"FamInConflitto-{i}", "1" if conflitto else "0")
    with page.expect_navigation(wait_until="domcontentloaded", timeout=60000):
        page.evaluate(_SUBMIT)
    page.wait_for_timeout(1200)

    params, calc, concl = None, None, None
    for t in page.query_selector_all("table"):
        tx = t.inner_text().strip()
        if tx.startswith("Parametri Inseriti"):
            params = _rows(tx)
        elif tx.startswith("Sviluppo del Calcolo"):
            calc = _rows(tx)
        elif tx.startswith("Conclusioni"):
            concl = tx
    assert params is not None and calc is not None and concl is not None, "risultato del sito non trovato"

    # Guard against the site's remembered form state: the echo must match the inputs.
    assert params["Materia del procedimento"] == materia.capitalize(), params
    assert params["Anno dei redditi"] == anno, params
    n_attesi = str(len(familiari)) if familiari else "Nessuno"
    assert params["Familiari conviventi indicati"] == n_attesi, params
    assert parse_euro(calc["Richiedente - reddito imponibile"]) == pytest.approx(reddito, abs=0.001), calc

    reddito_label = next(k for k in calc if k.startswith("Reddito complessivo"))
    aumento = next((v for k, v in calc.items() if k.startswith("Aumento penale")), None)
    limite_base = next(v for k, v in calc.items() if k.startswith("Limite di reddito"))

    if "Requisito reddituale non rispettato" in concl:
        ammesso = False
    elif "Requisito reddituale rispettato" in concl:
        ammesso = True
    else:
        raise AssertionError(f"conclusione del sito non riconosciuta: {concl!r}")
    m = re.search(r"(inferiore al|supera il) limite applicato di €\s*([\d.,]+)", concl)
    assert m, concl
    margine = parse_euro(m.group(2)) * (-1 if m.group(1).startswith("supera") else 1)

    return {
        "ammesso": ammesso,
        "reddito": parse_euro(calc[reddito_label]),
        "limite": parse_euro(calc["Limite complessivo applicato"]),
        "limite_base": parse_euro(limite_base),
        "aumento_penale": parse_euro(aumento) if aumento else None,
        "margine": margine,
        "params": params,
        "calc": calc,
    }


def _compare(r: dict, s: dict) -> None:
    """tool == sito on outcome, household income, applied limit and margin.

    All the differences are collected first so that a failing case reports the
    whole picture, not only the first field that differs.
    """
    diffs = []
    if r["ammesso"] != s["ammesso"]:
        diffs.append(f"ammesso: tool={r['ammesso']} sito={s['ammesso']}")
    for key_t, key_s, label in (
        ("reddito_totale_nucleo", "reddito", "reddito complessivo"),
        ("soglia_applicata", "limite", "limite applicato"),
        ("margine", "margine", "margine"),
    ):
        if abs(r[key_t] - s[key_s]) > TOL:
            diffs.append(f"{label}: tool={r[key_t]:.2f} sito={s[key_s]:.2f}")
    assert not diffs, "; ".join(diffs)


# ---------------------------------------------------------------------------
# cases
# ---------------------------------------------------------------------------

class TestGratuitoPatrocinio:

    def test_reddito_pari_alla_soglia(self, page):
        """Piano: ammesso true, margine 0 (art. 76 co. 1 DPR 115/2002: reddito non
        superiore a 13.659,64 euro, D.M. 22 aprile 2025). Caso al limite."""
        r = _tool(reddito_richiedente=13659.64)
        s = _site(page, 13659.64)
        assert_close(s["limite_base"], SOGLIA_2025, TOL, "soglia 2025 del sito")
        _compare(r, s)

    def test_un_centesimo_sopra_la_soglia(self, page):
        """Piano: ammesso false, margine -0,01 (art. 76 co. 1 DPR 115/2002).
        Caso al limite."""
        r = _tool(reddito_richiedente=13659.65)
        s = _site(page, 13659.65)
        _compare(r, s)

    def test_penale_due_familiari_conviventi(self, page):
        """Piano: ammesso true; reddito del nucleo 15.000 (art. 76 co. 2), soglia
        13.659,64 + 2 x 1.032,91 = 15.725,46 (art. 92), margine 725,46."""
        r = _tool(reddito_richiedente=7000.0, n_familiari_conviventi=2,
                  redditi_familiari=[5000.0, 3000.0], ambito="penale")
        s = _site(page, 7000.0, materia="penale",
                  familiari=(("coniuge", 5000.0, False), ("figlio", 3000.0, False)))
        assert s["aumento_penale"] is not None
        assert_close(s["aumento_penale"], 2 * AUMENTO_PENALE, TOL, "aumento penale del sito")
        _compare(r, s)

    def test_civile_stesso_nucleo(self, page):
        """Piano: ammesso false; soglia 13.659,64 senza maggiorazione (l'art. 92 vale
        solo nel processo penale), margine -1.340,36 (art. 76 co. 1-2)."""
        r = _tool(reddito_richiedente=7000.0, n_familiari_conviventi=2,
                  redditi_familiari=[5000.0, 3000.0], ambito="civile")
        s = _site(page, 7000.0, materia="civile",
                  familiari=(("coniuge", 5000.0, False), ("figlio", 3000.0, False)))
        assert s["aumento_penale"] is None
        _compare(r, s)

    def test_penale_limite_esatto_familiare_senza_reddito(self, page):
        """Caso al limite aggiunto: penale, un familiare convivente con reddito zero.
        Soglia 13.659,64 + 1.032,91 = 14.692,55 (art. 92 DPR 115/2002: l'aumento
        spetta per ogni familiare convivente, a prescindere dal suo reddito);
        reddito del nucleo 14.692,55 -> ammesso, margine 0 (art. 76 co. 1)."""
        r = _tool(reddito_richiedente=14692.55, n_familiari_conviventi=1,
                  redditi_familiari=[0.0], ambito="penale")
        s = _site(page, 14692.55, materia="penale", familiari=(("figlio", 0.0, False),))
        _compare(r, s)

    def test_interessi_in_conflitto_con_il_coniuge(self, page):
        """Piano: ammesso con il solo reddito personale di 9.000 euro quando gli
        interessi sono in conflitto con quelli del familiare convivente (art. 76 co. 4
        DPR 115/2002); il tool somma 39.000 euro e risponde false perche' non ha
        l'opzione, che il sito offre (FamInConflitto). Opzione enumerata del sito.
        Resta rosso finche' il tool non modella l'art. 76 co. 4."""
        r = _tool(reddito_richiedente=9000.0, n_familiari_conviventi=1,
                  redditi_familiari=[30000.0], ambito="civile")
        s = _site(page, 9000.0, materia="civile", familiari=(("coniuge", 30000.0, True),))
        _compare(r, s)

    def test_diritti_della_personalita(self, page):
        """Caso aggiunto (opzione enumerata del sito): causa sui diritti della
        personalita' -> si tiene conto del solo reddito personale (art. 76 co. 4
        DPR 115/2002, prima ipotesi). Atteso: 9.000 <= 13.659,64, ammesso, margine
        4.659,64. Il tool non ha il parametro e somma il reddito del coniuge
        (39.000, non ammesso). Resta rosso finche' il tool non modella l'art. 76 co. 4."""
        r = _tool(reddito_richiedente=9000.0, n_familiari_conviventi=1,
                  redditi_familiari=[30000.0], ambito="civile")
        s = _site(page, 9000.0, materia="civile", diritti_personalita=True,
                  familiari=(("coniuge", 30000.0, False),))
        _compare(r, s)

    def test_persona_offesa_reati_violenza(self, page):
        """Piano: ammesso true in deroga ai limiti di reddito (art. 76 co. 4-ter
        DPR 115/2002 per i reati elencati, tra cui artt. 572, 609-bis e 612-bis c.p.).
        Il sito non ha l'opzione: non confrontabile."""
        r = _tool(reddito_richiedente=40000.0, ambito="penale", vittima_violenza=True)
        assert r["ammesso"] is True and r["margine"] is None
        pytest.skip(
            "non confrontabile: il sito non offre l'ammissione in deroga dell'art. 76 "
            "co. 4-ter (persona offesa); verifica solo il requisito reddituale"
        )

    def test_anno_redditi_2024_soglia_diversa(self, page):
        """Caso al limite aggiunto (anno diverso della tabella): redditi 2024, reddito
        13.000. Il tool ha una sola soglia (13.659,64, D.M. 22 aprile 2025) e non
        prende l'anno; il sito applica la soglia dell'anno selezionato. Non
        confrontabile per regola del brief (stesso anno della tabella del tool):
        il test registra i due valori nel motivo dello skip."""
        r = _tool(reddito_richiedente=13000.0)
        s = _site(page, 13000.0, anno="2024")
        pytest.skip(
            "non confrontabile (anno della tabella diverso): sito redditi 2024 -> "
            f"limite {s['limite']:.2f}, ammesso={s['ammesso']}, margine {s['margine']:.2f} "
            f"({s['calc'].get('Riferimento limite per redditi del 2024', '')}); "
            f"tool -> soglia {r['soglia_applicata']:.2f}, ammesso={r['ammesso']}, "
            f"margine {r['margine']:.2f}"
        )

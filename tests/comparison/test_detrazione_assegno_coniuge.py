"""Benchmark fase 1: detrazione_assegno_coniuge vs avvocatoandreani.it.

Pagina: https://www.avvocatoandreani.it/servizi/calcolo-detrazione-assegno-coniuge.php
Modulo ``CalcoloDetrazioneAssegnoConiuge`` (POST): ``RedditoComplessivoDetrazione``
(rigo RN1 col. 1) e ``DeduzioneAbitazionePrincipale`` (rigo RN2); pulsante
``#btn-calc``. Il click sul pulsante non parte (overlay pubblicitari e CMP): il modulo
si invia con ``requestSubmit``.

Risultato: blocco "SVILUPPO del CALCOLO -- Periodo di imposta 2025 - Dichiarazione dei
redditi 2026" con Reddito netto (RN1 - RN2), Detrazione base, Quoziente (quattro
decimali), "Formula applicata" -- ``(700 + (1255 x Quoziente))`` oppure
``(700 x Quoziente)`` oppure "La detrazione e' stabilita in misura fissa" -- e
"RN7 Col.4 Detrazione spettante", arrotondata all'unita' di euro (nota della pagina:
"la detrazione calcolata [e'] sempre arrotondata all'euro superiore o inferiore come
indicato dall'Agenzia delle entrate").

Confronto: ``detrazione`` del tool (in centesimi) contro la detrazione del sito prima
dell'arrotondamento dichiarativo, ricostruita dai valori che il sito stesso mostra
(base + moltiplicatore x quoziente, oppure base x quoziente, oppure la misura fissa).
Il driver verifica che il rigo RN7 del sito sia l'arrotondamento all'euro (half-up) di
quel valore, cosi' la ricostruzione non introduce nulla di suo. Il valore del rigo RN7
e' riportato nei messaggi di errore.

Norma (testo vigente letto con cite_law, Normattiva, 25 settembre 2026):
- art. 13, co. 5-bis, TUIR (D.P.R. 917/1986): per gli assegni periodici dell'art. 10,
  co. 1, lett. c), "spetta una detrazione dall'imposta lorda [...] in misura pari a
  quelle di cui al comma 3, non rapportate ad alcun periodo nell'anno";
- art. 13, co. 3, TUIR (redditi di pensione): a) 1.955 euro se il reddito complessivo
  non supera 8.500; b) 700 + 1.255 x (28.000 - RC) / 19.500 oltre 8.500 e fino a
  28.000; c) 700 x (50.000 - RC) / 22.000 oltre 28.000 e fino a 50.000;
- art. 13, co. 5, TUIR (1.265; 500 + 765 x (28.000 - RC) / 22.500; 500 x (50.000 -
  RC) / 22.000) riguarda gli altri redditi "ad esclusione di quelli derivanti dagli
  assegni periodici indicati nell'articolo 10, comma 1, lettera c)"; la maggiorazione
  di 50 euro del co. 5-ter (11.000-17.000) e' riferita al solo co. 5;
- art. 13, co. 6: il rapporto maggiore di zero "si assume nelle prime quattro cifre
  decimali"; co. 6-bis: reddito complessivo al netto dell'abitazione principale.

Il sito applica gli importi del co. 3 (pensioni), come dispone il co. 5-bis vigente.
Il tool applica gli importi del co. 5 (lavoro autonomo e altri redditi), che il co. 5
esclude espressamente per gli assegni periodici del coniuge: da qui gli scostamenti
attesi in tutte le fasce, tranne oltre i 50.000 euro (entrambi 0). Il tool usa
inoltre il coefficiente a precisione piena, senza il troncamento del co. 6.

Punto aperto (non deciso qui): il co. 3-bis aumenta di 50 euro "la detrazione
spettante ai sensi del comma 3" tra 25.000 e 29.000; il sito non la applica
all'assegno del coniuge (caso 26.000). Il rinvio del co. 5-bis e' alla sola "misura"
del co. 3: la questione resta alla fase 2.

Anno: il sito calcola per il periodo d'imposta 2025 (nessuna scelta dell'anno); il
tool non ha tabelle annuali (importi del co. 3 invariati dalla L. 234/2021). Il tool
non dipende dalla data corrente (nessun LEGAL_TODAY).

Tolleranza: 0,01 euro (brief di benchmark).
"""

import re
import time
from decimal import ROUND_HALF_UP, Decimal

from tests.comparison.conftest import assert_close, extract_amount, goto, parse_euro

PAGE = "calcolo-detrazione-assegno-coniuge.php"
FORM = "CalcoloDetrazioneAssegnoConiuge"
TOL = 0.01

_HIDE_CMP = (
    ".qc-cmp2-container,#qc-cmp2-container"
    "{display:none !important;pointer-events:none !important}"
)


# ---------------------------------------------------------------------------
# Tool
# ---------------------------------------------------------------------------

def _tool(reddito: float) -> dict:
    import src.server  # noqa: F401  -- registra i moduli (evita import circolari)
    from src.tools.dichiarazione_redditi import detrazione_assegno_coniuge

    fn = getattr(detrazione_assegno_coniuge, "fn", detrazione_assegno_coniuge)
    r = fn(reddito_complessivo=reddito)
    assert "errore" not in r, r
    return r


# ---------------------------------------------------------------------------
# Sito
# ---------------------------------------------------------------------------

def _dec(text: str) -> Decimal:
    return Decimal(text.replace(".", "").replace(",", "."))


def _site(page, rn1: str, rn2: str = "") -> dict:
    """Compila RN1/RN2, invia il modulo e legge lo sviluppo del calcolo."""
    time.sleep(1.5)  # cortesia verso il sito tra una richiesta e l'altra
    goto(page, PAGE)
    page.add_style_tag(content=_HIDE_CMP)
    page.wait_for_timeout(500)
    page.fill("input[name='RedditoComplessivoDetrazione']", rn1)
    page.fill("input[name='DeduzioneAbitazionePrincipale']", rn2)
    with page.expect_navigation(wait_until="domcontentloaded", timeout=60000):
        page.evaluate(
            f"document.forms['{FORM}'].requestSubmit(document.getElementById('btn-calc'))"
        )
    page.wait_for_timeout(1500)
    body = page.inner_text("body")

    start = body.find("SVILUPPO del CALCOLO")
    if start < 0:
        return {"calcolato": False, "body": body}
    end = body.find("Pubblicit", start)
    block = body[start:end if end > 0 else start + 1500]

    spett = re.search(r"Detrazione spettante\s+€\s*([\d.,]+)", block)
    base = re.search(r"Detrazione base\s+€\s*([\d.,]+)", block)
    quoz = re.search(r"Quoziente\s+(-?[\d.,]+)", block)
    formula = re.search(r"Formula applicata:\s*\((.*?)\)\s*$", block, re.MULTILINE)
    fissa = "misura fissa" in block

    rn7 = _dec(spett.group(1))
    # Detrazione prima dell'arrotondamento all'euro, dai valori mostrati dal sito.
    if base is None:  # oltre 50.000: il sito mostra solo il rigo RN7
        valore = rn7
        forma = "nessuna (oltre soglia)"
    elif fissa:
        valore = _dec(base.group(1))
        forma = "misura fissa"
    else:
        q = _dec(quoz.group(1))
        f = formula.group(1).replace(" ", "")
        m_add = re.fullmatch(r"(\d+)\+\((\d+)xQuoziente\)\)?", f)
        m_mul = re.fullmatch(r"(\d+)xQuoziente\)?", f)
        if m_add:
            valore = Decimal(m_add.group(1)) + Decimal(m_add.group(2)) * q
        elif m_mul:
            valore = Decimal(m_mul.group(1)) * q
        else:  # formula nuova: il driver va aggiornato, non indovinato
            raise AssertionError(f"formula del sito non riconosciuta: {formula.group(1)!r}")
        forma = formula.group(1).strip()

    return {
        "calcolato": True,
        "block": block,
        "anno": re.search(r"Periodo di imposta (\d{4})", block).group(1),
        "reddito_netto": extract_amount(block, "Reddito netto"),
        "base": parse_euro(base.group(1)) if base else None,
        "quoziente": float(_dec(quoz.group(1))) if quoz else None,
        "formula": forma,
        "valore": float(valore.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
        "valore_pieno": valore,
        "rn7": float(rn7),
    }


def _confronta(page, reddito: float, rn1: str | None = None, rn2: str = "",
               label: str = "") -> tuple[dict, dict]:
    t = _tool(reddito)
    s = _site(page, rn1 if rn1 is not None else str(int(reddito)), rn2)
    assert s["calcolato"], f"{label}: il sito non ha prodotto lo sviluppo del calcolo"
    # il driver ha davvero passato i dati al sito
    assert_close(reddito, s["reddito_netto"], 0.01, f"{label} reddito netto")
    assert s["anno"] == "2025", f"{label}: periodo d'imposta del sito {s['anno']}"
    # la ricostruzione del valore in centesimi e' coerente con il rigo RN7 del sito
    rn7_atteso = s["valore_pieno"].quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    assert float(rn7_atteso) == s["rn7"], (
        f"{label}: ricostruzione {s['valore_pieno']} non coerente con RN7 {s['rn7']}"
    )
    assert_close(
        float(t["detrazione"]),
        s["valore"],
        TOL,
        f"{label} detrazione (tool fascia {t['fascia']}; sito formula {s['formula']}, "
        f"quoziente {s['quoziente']}, RN7 {s['rn7']:.2f})",
    )
    return t, s


# ---------------------------------------------------------------------------
# Casi del piano
# ---------------------------------------------------------------------------

def test_piano_limite_prima_fascia_5500(page):
    """Piano: "Da leggere dal sito; il tool applica 1.265,00" (limite della prima fascia).

    Art. 13, co. 5-bis e co. 3, lett. a), TUIR: 5.500 <= 8.500 -> 1.955,00 in misura
    fissa. Sito: 1.955,00. Tool: 1.265,00 (co. 5, lett. a). Scostamento atteso.
    """
    _confronta(page, 5500, label="5.500")


def test_piano_fascia_intermedia_12000(page):
    """Piano: "il tool restituisce 1.044,00 senza la maggiorazione del co. 5.1".

    Art. 13, co. 5-bis e co. 3, lett. b), TUIR: quoziente (28.000 - 12.000) / 19.500
    = 0,82051 -> 0,8205 (co. 6); 700 + 1.255 x 0,8205 = 1.729,73 (RN7 1.730). La
    maggiorazione di 50 euro tra 11.000 e 17.000 (oggi co. 5-ter) riguarda il solo
    co. 5, che esclude gli assegni: non si applica. Tool: 1.044,00. Scostamento atteso.
    """
    _confronta(page, 12000, label="12.000")


def test_piano_fascia_intermedia_20000(page):
    """Piano: "il tool restituisce 772,00 (771,96 con coefficiente troncato)".

    Art. 13, co. 5-bis e co. 3, lett. b), TUIR: quoziente 8.000 / 19.500 = 0,41025
    -> 0,4102; 700 + 1.255 x 0,4102 = 1.214,80 (RN7 1.215). Tool: 772,00.
    Scostamento atteso.
    """
    _confronta(page, 20000, label="20.000")


def test_piano_terza_fascia_40000(page):
    """Piano: "il tool restituisce 227,27 (227,25 con coefficiente troncato)".

    Art. 13, co. 5-bis e co. 3, lett. c), TUIR: quoziente 10.000 / 22.000 = 0,45454
    -> 0,4545; 700 x 0,4545 = 318,15 (RN7 318). Tool: 500 x 0,454545 = 227,27.
    Scostamento atteso.
    """
    _confronta(page, 40000, label="40.000")


# ---------------------------------------------------------------------------
# Casi aggiunti (limiti di fascia del co. 3 e opzione RN2 del sito)
# ---------------------------------------------------------------------------

def test_limite_misura_fissa_8500(page):
    """Reddito 8.500: ultimo euro della misura fissa (caso al limite).

    Art. 13, co. 3, lett. a), TUIR: "se il reddito complessivo non supera 8.500
    euro" -> 1.955,00. Tool: 500 + 765 x 19.500 / 22.500 = 1.163,00.
    """
    _confronta(page, 8500, label="8.500")


def test_limite_un_euro_oltre_misura_fissa_8501(page):
    """Reddito 8.501: primo euro della fascia b) (caso al limite).

    Art. 13, co. 3, lett. b), e co. 6 TUIR: quoziente 19.499 / 19.500 = 0,99995 ->
    0,9999; 700 + 1.255 x 0,9999 = 1.954,87 (RN7 1.955). Tool: 1.162,97.
    """
    _confronta(page, 8501, label="8.501")


def test_banda_maggiorazione_co3bis_26000(page):
    """Reddito 26.000: banda 25.000-29.000 del co. 3-bis (caso al limite).

    Art. 13, co. 3, lett. b): quoziente 2.000 / 19.500 = 0,10256 -> 0,1025; 700 +
    1.255 x 0,1025 = 828,64 (RN7 829). Il sito non aggiunge i 50 euro del co. 3-bis
    ("la detrazione spettante ai sensi del comma 3"); se il rinvio del co. 5-bis li
    comprendesse la detrazione sarebbe 878,64: punto aperto per la fase 2.
    Tool: 500 + 765 x 2.000 / 22.500 = 568,00.
    """
    _confronta(page, 26000, label="26.000")


def test_limite_fine_fascia_b_28000(page):
    """Reddito 28.000: ultimo euro della fascia b) (caso al limite).

    Art. 13, co. 3, lett. b): quoziente 0 -> 700,00 (RN7 700). Tool: 500,00.
    """
    _confronta(page, 28000, label="28.000")


def test_limite_inizio_fascia_c_28001(page):
    """Reddito 28.001: primo euro della fascia c) (caso al limite).

    Art. 13, co. 3, lett. c), e co. 6: quoziente 21.999 / 22.000 = 0,99995 -> 0,9999;
    700 x 0,9999 = 699,93 (RN7 700). Tool: 500 x 0,99995 = 499,98.
    """
    _confronta(page, 28001, label="28.001")


def test_limite_soglia_50000(page):
    """Reddito 50.000: quoziente zero (caso al limite).

    Art. 13, co. 3, lett. c): (50.000 - 50.000) / 22.000 = 0 -> 0,00. Tool: 0,00.
    Atteso: coincide.
    """
    _confronta(page, 50000, label="50.000")


def test_oltre_soglia_60000(page):
    """Reddito 60.000: oltre 50.000 nessuna detrazione.

    Art. 13, co. 3, lett. c): la detrazione spetta solo fino a 50.000 -> 0,00; il
    sito mostra solo il rigo RN7. Tool: 0 ("oltre 50.000"). Atteso: coincide.
    """
    _confronta(page, 60000, label="60.000")


def test_deduzione_abitazione_principale_rn2(page):
    """RN1 45.000 e RN2 5.000: il sito calcola sul reddito netto 40.000.

    Art. 13, co. 6-bis, TUIR: reddito complessivo al netto dell'abitazione principale.
    Il tool non ha il campo RN2: riceve direttamente il reddito gia' al netto (40.000).
    Atteso secondo norma: 700 x 0,4545 = 318,15 (RN7 318). Tool: 227,27.
    """
    _confronta(page, 40000, rn1="45000", rn2="5000", label="45.000 - 5.000")

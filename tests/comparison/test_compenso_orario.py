"""Comparison tests: compenso_orario vs avvocatoandreani.it (compenso a tempo).

Site page: https://www.avvocatoandreani.it/servizi/calcolo-somma-ore-minuti-compensi-a-tempo.php
The page is a client-side calculator (no server round trip): it takes "Tariffa Oraria"
(optional), "Ore" and "Minuti", and the "+" area of the ``#img-p`` image map adds the
time to a running total. Output: ``#R-Output-Tempo`` ("HH:MM") and
``#R-Output-Compenso`` ("€ 1234,56": decimal comma, no thousands separator).

What the site computes (read from its own JavaScript, ``CalcolaCompenso``):
    compenso = tariffa * (minuti_totali / 60), displayed by ``FmtDec`` =
    ``Number.toFixed(2)`` with the dot replaced by a comma.
It never rounds the time. The tool instead rounds the time UP to the chosen unit
(``quarto_ora`` 15 min, ``mezz_ora`` 30 min, ``ora`` 60 min) before multiplying.

Legal basis: none. ``compenso_orario`` has no Vigenza line (pure arithmetic,
Precisione: ESATTO); the rounding unit is a contractual convention, not a rule of law.

How the cases are split:
- time already a multiple of the unit -> the two computations must coincide;
- time NOT a multiple of the unit -> the site offers no rounding option, so the
  comparison on the effective time is not meaningful. It is recorded (the site value
  is read and put in the skip reason) and skipped as non-comparable; a twin test then
  feeds the site the tool's rounded time and asserts the two amounts coincide, which
  checks the multiplication and the cent rounding on the same billed time.

Tolerance: 0.01 EUR (brief), compared in integer cents so that float noise
(``abs(153.12 - 153.13) == 0.0100000000000193``) cannot turn a one-cent gap into a
failure. Times must match exactly.
"""

import re

import pytest

from tests.comparison.conftest import accept_cookies, goto, parse_euro

PAGE = "calcolo-somma-ore-minuti-compensi-a-tempo.php"

_HHMM_RE = re.compile(r"(\d+):(\d{2})")
_TOOL_TIME_RE = re.compile(r"(\d+)h\s*(\d+)min")


def _tool(**kwargs) -> dict:
    import src.server  # noqa: F401  registers all tool modules
    from src.tools.parcelle_professionisti import compenso_orario

    fn = getattr(compenso_orario, "fn", compenso_orario)
    return fn(**kwargs)


def _site(page, tariffa: str, ore: int, minuti: int, righe_attese: int = 1) -> tuple[int, float]:
    """Drive the site calculator once; return (total minutes, compenso in EUR).

    ``tariffa`` is typed as the user would type it (Italian decimal comma).
    ``righe_attese`` is the number of rows the site's time log (``#Undo``) must show
    afterwards: 1 normally, 0 when the time is zero (the site ignores a 0:00 entry).
    """
    goto(page, PAGE, wait_ms=1500)
    page.fill("#Tariffa", tariffa)
    page.fill("#Ore", str(ore))
    page.fill("#Minuti", str(minuti))
    # The Quantcast CMP overlay is injected after page load and intercepts the click:
    # remove it again right before clicking.
    accept_cookies(page)
    # "somma" is the first 24x24 area of the image map on #img-p (onclick ExecuteOp('+')).
    page.click("#img-p", position={"x": 12, "y": 12}, force=True)
    page.wait_for_timeout(2000)  # the result fades in over 700 ms
    assert page.locator("#Undo tr").count() == righe_attese, "il sito non ha registrato il tempo atteso"
    m = _HHMM_RE.search(page.inner_text("#R-Output-Tempo"))
    assert m, "tempo non leggibile nell'output del sito"
    minuti_sito = int(m.group(1)) * 60 + int(m.group(2))
    compenso_sito = parse_euro(page.inner_text("#R-Output-Compenso"))
    return minuti_sito, compenso_sito


def _tool_minutes(tempo: str) -> int:
    m = _TOOL_TIME_RE.fullmatch(tempo.strip())
    assert m, f"formato tempo inatteso nel tool: {tempo!r}"
    return int(m.group(1)) * 60 + int(m.group(2))


def _assert_cents(tool_value: float, site_value: float, label: str) -> None:
    diff_cents = abs(round(tool_value * 100) - round(site_value * 100))
    assert diff_cents <= 1, (
        f"{label}: tool={tool_value:.2f}, sito={site_value:.2f}, diff={diff_cents / 100:.2f} (max 0.01)"
    )


def _compare_same_time(page, tariffa_sito: str, **tool_args) -> None:
    """Assert tool == site when the site is fed the tool's rounded time."""
    r = _tool(**tool_args)
    assert "errore" not in r, r
    minuti_arr = _tool_minutes(r["tempo_arrotondato"])
    minuti_sito, compenso_sito = _site(page, tariffa_sito, minuti_arr // 60, minuti_arr % 60)
    assert minuti_sito == minuti_arr, f"tempo: tool={minuti_arr} min, sito={minuti_sito} min"
    _assert_cents(r["compenso"], compenso_sito, "compenso")


def _record_effective_time(page, tariffa_sito: str, **tool_args) -> None:
    """Read the site on the EFFECTIVE time and skip: the site has no rounding option."""
    r = _tool(**tool_args)
    assert "errore" not in r, r
    ore, minuti = tool_args["ore"], tool_args.get("minuti", 0)
    minuti_sito, compenso_sito = _site(page, tariffa_sito, ore, minuti)
    assert minuti_sito == ore * 60 + minuti, "il sito ha letto un tempo diverso da quello inserito"
    pytest.skip(
        f"non confrontabile: il sito non arrotonda il tempo. Tool {r['compenso']:.2f} "
        f"su {r['tempo_arrotondato']} ({tool_args['arrotondamento']}); sito {compenso_sito:.2f} "
        f"su {ore}h {minuti}min effettivi (differenza di convenzione, "
        f"{r['compenso'] - compenso_sito:.2f} EUR)"
    )


# --- Plan cases: time already a multiple of the unit -------------------------------


def test_piano_2h30_mezz_ora(page):
    # Piano: 100 EUR/h, 2h30, mezz_ora -> 250,00 EUR (2,5 ore esatte), coincide con il sito.
    # Norma: nessuna (calcolo aritmetico, Precisione ESATTO).
    r = _tool(tariffa_oraria=100, ore=2, minuti=30, arrotondamento="mezz_ora")
    assert r["tempo_arrotondato"] == "2h 30min"
    minuti_sito, compenso_sito = _site(page, "100", 2, 30)
    assert minuti_sito == 150
    _assert_cents(r["compenso"], compenso_sito, "2h30 mezz_ora")


def test_piano_1h45_quarto_ora(page):
    # Piano: 90 EUR/h, 1h45, quarto_ora -> 157,50 EUR sia nel tool sia sul sito.
    # Norma: nessuna (calcolo aritmetico, Precisione ESATTO).
    r = _tool(tariffa_oraria=90, ore=1, minuti=45, arrotondamento="quarto_ora")
    assert r["tempo_arrotondato"] == "1h 45min"
    minuti_sito, compenso_sito = _site(page, "90", 1, 45)
    assert minuti_sito == 105
    _assert_cents(r["compenso"], compenso_sito, "1h45 quarto_ora")


# --- Plan cases: rounding up (site has no rounding option) ------------------------


def test_piano_2h10_mezz_ora_tempo_effettivo(page):
    # Piano: 100 EUR/h, 2h10, mezz_ora -> tool 250,00 (arrotondato a 2h30); il sito senza
    # arrotondamento 216,67: differenza di convenzione, documentata e non corretta.
    # Norma: nessuna (convenzione contrattuale sull'unita' di tempo fatturata).
    _record_effective_time(page, "100", tariffa_oraria=100, ore=2, minuti=10, arrotondamento="mezz_ora")


def test_piano_2h10_mezz_ora_tempo_arrotondato(page):
    # Stesso caso del piano, ma il sito riceve il tempo gia' arrotondato dal tool (2h30):
    # atteso 250,00 EUR da entrambi.
    _compare_same_time(page, "100", tariffa_oraria=100, ore=2, minuti=10, arrotondamento="mezz_ora")


def test_piano_1min_ora_tempo_effettivo(page):
    # Piano: 80 EUR/h, 0h01, ora -> tool 80,00; sito 1,33: differenza di convenzione.
    # Limite: il minimo tempo non nullo fa scattare un'intera unita' (1 ora).
    _record_effective_time(page, "80", tariffa_oraria=80, ore=0, minuti=1, arrotondamento="ora")


def test_piano_1min_ora_tempo_arrotondato(page):
    # Stesso caso del piano con il tempo arrotondato dal tool (1h00) passato al sito:
    # atteso 80,00 EUR da entrambi.
    _compare_same_time(page, "80", tariffa_oraria=80, ore=0, minuti=1, arrotondamento="ora")


# --- Boundary cases added in phase 1 ----------------------------------------------


def test_limite_3h00_ora_multiplo_esatto(page):
    # Limite: tempo esattamente pari a 3 unita' 'ora' -> il ceil non deve saltare a 4h.
    # Atteso: 75 EUR/h x 3h = 225,00 EUR, tool e sito.
    r = _tool(tariffa_oraria=75, ore=3, minuti=0, arrotondamento="ora")
    assert r["tempo_arrotondato"] == "3h 0min"
    minuti_sito, compenso_sito = _site(page, "75", 3, 0)
    assert minuti_sito == 180
    _assert_cents(r["compenso"], compenso_sito, "3h00 ora")


def test_limite_0h16_quarto_ora_tempo_effettivo(page):
    # Limite: un minuto oltre il quarto d'ora -> il tool fattura 0h30 (60 EUR/h -> 30,00),
    # il sito 16 minuti effettivi (16,00). Differenza di convenzione, non confrontabile.
    _record_effective_time(page, "60", tariffa_oraria=60, ore=0, minuti=16, arrotondamento="quarto_ora")


def test_limite_0h16_quarto_ora_tempo_arrotondato(page):
    # Stesso caso con il tempo arrotondato dal tool (0h30) passato al sito: atteso 30,00 EUR.
    _compare_same_time(page, "60", tariffa_oraria=60, ore=0, minuti=16, arrotondamento="quarto_ora")


def test_limite_centesimo_in_parita(page):
    # Limite sull'arrotondamento al centesimo: 87,50 EUR/h x 1,75 h = 153,125 esatti
    # (rappresentabile in binario). Il tool usa round() di Python (meta' al pari -> 153,12),
    # il sito Number.toFixed(2) (meta' per eccesso -> 153,13). Differenza di 0,01 EUR,
    # entro la tolleranza del brief: il test passa ma lo scarto e' riportato nell'esito.
    r = _tool(tariffa_oraria=87.5, ore=1, minuti=45, arrotondamento="quarto_ora")
    minuti_sito, compenso_sito = _site(page, "87,50", 1, 45)
    assert minuti_sito == 105
    _assert_cents(r["compenso"], compenso_sito, "87,50 x 1h45")


def test_limite_tempo_zero(page):
    # Limite: tempo nullo (0h00). Tool: ceil(0/15)*15 = 0 minuti -> compenso 0,00 per ogni
    # unita'. Il sito scarta la riga 0:00 (HM2M == 0) e resta su "00:00" / "€ 0,00".
    # Atteso: 0,00 EUR da entrambi. Norma: nessuna (calcolo aritmetico).
    r = _tool(tariffa_oraria=120, ore=0, minuti=0, arrotondamento="ora")
    assert r["tempo_arrotondato"] == "0h 0min"
    minuti_sito, compenso_sito = _site(page, "120", 0, 0, righe_attese=0)
    assert minuti_sito == 0
    _assert_cents(r["compenso"], compenso_sito, "0h00 ora")


def test_limite_importo_oltre_mille_tariffa_sei_cifre(page):
    # Limite sul formato: tariffa 999,99 (6 caratteri, il massimo del campo Tariffa del sito)
    # x 10h45 in quarti d'ora (645 min, multiplo esatto) = 10.749,8925 -> 10.749,89 EUR.
    # Il sito formatta con Number.toFixed(2) SENZA separatore delle migliaia ("€ 10749,89"):
    # verifica che la lettura dell'importo resti corretta sopra i mille euro.
    # Norma: nessuna (calcolo aritmetico).
    r = _tool(tariffa_oraria=999.99, ore=10, minuti=45, arrotondamento="quarto_ora")
    assert r["tempo_arrotondato"] == "10h 45min"
    minuti_sito, compenso_sito = _site(page, "999,99", 10, 45)
    assert minuti_sito == 645
    _assert_cents(r["compenso"], compenso_sito, "999,99 x 10h45")


def test_limite_minuti_oltre_59(page):
    # Limite sul dominio dell'input: 1h75. Il tool rifiuta minuti fuori da 0-59 (errore
    # esplicito, per scelta: i minuti sono la parte residua dell'ora); il sito invece somma
    # 60*ore + minuti e calcola su 2h15. Nessun confronto possibile sull'importo: si registra
    # il valore del sito e si salta. Norma: nessuna.
    r = _tool(tariffa_oraria=100, ore=1, minuti=75, arrotondamento="quarto_ora")
    assert "errore" in r, r
    minuti_sito, compenso_sito = _site(page, "100", 1, 75)
    assert minuti_sito == 135, f"il sito ha letto {minuti_sito} minuti"
    pytest.skip(
        f"non confrontabile: il tool rifiuta minuti=75 ({r['errore']}); il sito lo accetta "
        f"come 2h15 e calcola {compenso_sito:.2f} EUR"
    )

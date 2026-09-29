"""Comparison: conversione_pena vs avvocatoandreani.it (ragguaglio art. 135 c.p.).

Site page: /servizi/calcolo-conversione-pena-detentiva-pecuniaria.php
Form "ConversionePena": two tabs -
  * "Da pecuniaria a detentiva" (tab PD, default): text field PenaPecuniaria;
  * "Da detentiva a pecuniaria" (tab DP, button #B-DP): selects Anni1/Mesi1/Giorni1
    (max 30 anni / 48 mesi / 90 giorni);
  * ValoreGiornaliero (default 250, site range 250-2.500), submit #btn-calc.
Result: table.result with rows "Pena ragguagliata (€ 250 / giorno)" and, from one
month up, "Totale giorni".

Site conventions observed (2026-09-25):
  * PD direction TRUNCATES the fraction of 250 euro (600 -> 2 giorni, 249 -> "-"),
    and drops the cents (its instructions say so; "500,50" is shown as "€ 501").
  * Months are 30 days and years 360 days, both when it formats the converted
    penalty (91.250 -> "1 anno, 5 giorni", Totale giorni 365) and when it reads
    the input (1 anno -> 90.000 euro).

Art. 135 c.p. (text in force, Normattiva): "il computo ha luogo calcolando euro 250,
o frazione di euro 250, di pena pecuniaria per un giorno di pena detentiva" - the
tool counts every fraction as one day (ceil). Divergences on the fraction are
genuine and are left failing for phase 2 to judge.

Tolerances: 0,01 euro on amounts; days must match exactly.
"""

import re

import pytest

from tests.comparison.conftest import (
    accept_cookies,
    assert_close,
    goto,
    parse_euro,
    submit_form,
)

PAGE = "calcolo-conversione-pena-detentiva-pecuniaria.php"

# Site day-count convention used only to read a result shown as anni/mesi/giorni
# without the "Totale giorni" row (the site shows that row from 30 days up).
_SITE_UNIT_DAYS = {"ann": 360, "mes": 30, "gio": 1}


def _tool(**kwargs) -> dict:
    import src.server  # noqa: F401  (registers every module, avoids circular imports)
    from src.tools.diritto_penale import conversione_pena

    fn = getattr(conversione_pena, "fn", conversione_pena)
    return fn(**kwargs)


def _result_rows(page) -> dict[str, str]:
    rows: dict[str, str] = {}
    table = page.query_selector("table.result")
    if table is None:
        return rows
    for tr in table.query_selector_all("tr"):
        cells = [
            c.inner_text().replace("\xa0", " ").strip()
            for c in tr.query_selector_all("td")
        ]
        cells = [c for c in cells if c]
        if len(cells) >= 2:
            rows[cells[0]] = cells[1]
    return rows


def _row(rows: dict[str, str], prefix: str) -> tuple[str, str]:
    for label, value in rows.items():
        if label.startswith(prefix):
            return label, value
    raise AssertionError(f"riga '{prefix}' assente nel risultato del sito: {rows}")


def _site_days(rows: dict[str, str]) -> int:
    if "Totale giorni" in rows:
        return int(rows["Totale giorni"].replace(".", ""))
    _, value = _row(rows, "Pena ragguagliata")
    if value.strip() == "-":
        return 0
    total = 0
    for n, unit in re.findall(r"(\d+)\s+(anni|anno|mesi|mese|giorni|giorno)", value):
        total += int(n) * _SITE_UNIT_DAYS[unit[:3]]
    return total


def _open(page):
    # The Quantcast CMP overlay is injected after goto() has already dismissed the
    # site banner and would swallow the clicks: wait, then dismiss/remove it again.
    goto(page, PAGE)
    page.wait_for_timeout(1500)
    accept_cookies(page)


def _submit(page):
    accept_cookies(page)
    submit_form(page)


def _site_pecuniaria_a_detentiva(page, importo: str) -> tuple[int, dict[str, str]]:
    _open(page)
    page.fill("input[name='PenaPecuniaria']", importo)
    _submit(page)
    rows = _result_rows(page)
    assert rows, f"il sito non ha prodotto il risultato per PenaPecuniaria={importo}"
    label, _ = _row(rows, "Pena ragguagliata")
    assert "250 / giorno" in label, f"tasso del sito diverso da 250 euro/giorno: {label}"
    return _site_days(rows), rows


def _site_detentiva_a_pecuniaria(page, anni=None, mesi=None, giorni=None) -> tuple[float, dict[str, str]]:
    _open(page)
    page.click("#B-DP")  # tab "Da detentiva a pecuniaria"
    page.wait_for_selector("select[name='Giorni1']", state="visible", timeout=10000)
    for name, value in (("Anni1", anni), ("Mesi1", mesi), ("Giorni1", giorni)):
        if value:
            page.select_option(f"select[name='{name}']", str(value))
    _submit(page)
    rows = _result_rows(page)
    assert rows, "il sito non ha prodotto il risultato (detentiva a pecuniaria)"
    label, value = _row(rows, "Pena ragguagliata")
    assert "250 / giorno" in label, f"tasso del sito diverso da 250 euro/giorno: {label}"
    return parse_euro(value), rows


class TestDetentivaAPecuniaria:

    def test_30_giorni(self, page):
        # Piano: 30 giorni -> 7.500 euro (art. 135 c.p.: 250 euro per ogni giorno).
        r = _tool(importo=30, direzione="detentiva_a_pecuniaria")
        site_euro, _ = _site_detentiva_a_pecuniaria(page, giorni=30)
        assert_close(r["importo_pecuniario_euro"], site_euro, tolerance=0.01, label="30 giorni")

    def test_90_giorni_massimo_select(self, page):
        # Limite: 90 giorni e' il valore massimo della select Giorni1 (il sito lo mostra
        # come "3 mesi"). Atteso: 90 x 250 = 22.500 euro (art. 135 c.p.).
        r = _tool(importo=90, direzione="detentiva_a_pecuniaria")
        site_euro, _ = _site_detentiva_a_pecuniaria(page, giorni=90)
        assert_close(r["importo_pecuniario_euro"], site_euro, tolerance=0.01, label="90 giorni")

    def test_un_anno_convenzione_360(self, page):
        # Limite (convenzione): il tool accetta solo giorni; 1 anno secondo il calendario
        # comune (art. 14 c.p.) = 365 giorni -> 91.250 euro. Il sito legge "1 anno" come
        # 360 giorni (90.000 euro). Input non omogenei: caso non confrontabile.
        r = _tool(importo=365, direzione="detentiva_a_pecuniaria")
        site_euro, _ = _site_detentiva_a_pecuniaria(page, anni=1)
        pytest.skip(
            "non confrontabile: il tool prende la pena solo in giorni; il sito converte "
            f"1 anno = 360 giorni ({site_euro:.2f} euro) mentre 365 giorni nel tool danno "
            f"{r['importo_pecuniario_euro']:.2f} euro"
        )


class TestPecuniariaADetentiva:

    def test_600_euro_frazione(self, page):
        # Piano: 600 euro -> 3 giorni ("250 euro o frazione di 250 euro" valgono un
        # giorno, art. 135 c.p.); se il sito tronca la frazione ottiene 2.
        # Il sito tronca (2 giorni) pur citando in pagina lo stesso art. 135 ("euro 250,
        # o frazione di euro 250"); le sue istruzioni: centesimi ignorati, nessuna
        # frazione di giorno.
        r = _tool(importo=600, direzione="pecuniaria_a_detentiva")
        site_days, rows = _site_pecuniaria_a_detentiva(page, "600")
        assert r["giorni_detentivi"] == site_days, (
            f"600 euro: tool={r['giorni_detentivi']} giorni, sito={site_days} ({rows})"
        )

    def test_250_euro_confine_esatto(self, page):
        # Piano: confine esatto di 250 euro -> 1 giorno (art. 135 c.p.).
        r = _tool(importo=250, direzione="pecuniaria_a_detentiva")
        site_days, rows = _site_pecuniaria_a_detentiva(page, "250")
        assert r["giorni_detentivi"] == site_days, (
            f"250 euro: tool={r['giorni_detentivi']} giorni, sito={site_days} ({rows})"
        )

    def test_251_euro_appena_oltre_confine(self, page):
        # Limite: 251 euro = 250 + frazione di 1 euro -> 2 giorni per art. 135 c.p.
        # (la frazione vale un giorno); un calcolo che tronca da' 1.
        r = _tool(importo=251, direzione="pecuniaria_a_detentiva")
        site_days, rows = _site_pecuniaria_a_detentiva(page, "251")
        assert r["giorni_detentivi"] == site_days, (
            f"251 euro: tool={r['giorni_detentivi']} giorni, sito={site_days} ({rows})"
        )

    def test_249_euro_sotto_confine(self, page):
        # Limite: 249 euro e' solo una "frazione di euro 250" -> 1 giorno per art. 135 c.p.
        # Il sito, che tronca, non restituisce alcuna pena ("-", letto come 0 giorni).
        r = _tool(importo=249, direzione="pecuniaria_a_detentiva")
        site_days, rows = _site_pecuniaria_a_detentiva(page, "249")
        assert r["giorni_detentivi"] == site_days, (
            f"249 euro: tool={r['giorni_detentivi']} giorni, sito={site_days} ({rows})"
        )

    def test_centesimi_500_50(self, page):
        # Limite: 500,50 euro = 2 x 250 + frazione di 0,50 -> 3 giorni per art. 135 c.p.
        # Il sito dichiara di ignorare i centesimi (mostra "€ 501") e tronca: 2 giorni.
        r = _tool(importo=500.50, direzione="pecuniaria_a_detentiva")
        site_days, rows = _site_pecuniaria_a_detentiva(page, "500,50")
        assert r["giorni_detentivi"] == site_days, (
            f"500,50 euro: tool={r['giorni_detentivi']} giorni, sito={site_days} ({rows})"
        )

    def test_91250_euro_arresto(self, page):
        # Piano: 91.250 euro, tipo_pena=arresto -> 365 giorni (tipo_pena non incide).
        # Il sito esprime il risultato come "1 anno, 5 giorni" (anno di 360 giorni) e
        # riporta "Totale giorni 365": si confronta il totale in giorni.
        r = _tool(importo=91250, direzione="pecuniaria_a_detentiva", tipo_pena="arresto")
        site_days, rows = _site_pecuniaria_a_detentiva(page, "91250")
        assert r["giorni_detentivi"] == site_days, (
            f"91.250 euro: tool={r['giorni_detentivi']} giorni, sito={site_days} ({rows})"
        )

    def test_100000_euro_oltre_un_anno(self, page):
        # Limite (anni/mesi): 100.000 / 250 = 400 giorni esatti (art. 135 c.p.); il sito
        # lo formatta come "1 anno, 1 mese, 10 giorni" (360/30) con "Totale giorni 400".
        r = _tool(importo=100000, direzione="pecuniaria_a_detentiva")
        site_days, rows = _site_pecuniaria_a_detentiva(page, "100000")
        assert r["giorni_detentivi"] == site_days, (
            f"100.000 euro: tool={r['giorni_detentivi']} giorni, sito={site_days} ({rows})"
        )


def test_valore_giornaliero_diverso_da_250():
    # Opzione enumerata del sito: ValoreGiornaliero (250-2.500 euro). Il tool usa il
    # tasso fisso di 250 euro dell'art. 135 c.p. e non offre un valore giornaliero
    # variabile (quello della pena pecuniaria sostitutiva, art. 56-quater L. 689/1981,
    # va da 5 a 2.500 euro): caso non confrontabile.
    # Il range del sito e' quello del vecchio art. 53, secondo comma, L. 689/1981
    # (testo in vigore dal 29-6-2003 al 2-2-2022: minimo = importo dell'art. 135,
    # massimo = dieci volte); Corte cost. n. 28/2022 ha portato il minimo a 75 euro e
    # il D.Lgs. 150/2022 ha spostato la regola nell'art. 56-quater (5-2.500 euro).
    pytest.skip(
        "non confrontabile: il tool non accetta un valore giornaliero diverso da 250 euro "
        "(art. 135 c.p.); il sito lo consente tra 250 e 2.500 euro"
    )

"""Live gate: INPS official sources against `calcolo_naspi` and `costo_lavoro`.

Phase 4 of the avvocatoandreani.it benchmark, strategy `fonte_ufficiale`, group `inps`.
Neither tool has a calculator on the benchmark site, so each value the tool hard-codes
is compared with the INPS document that fixes it, and the formula with the vigente
text of the norm (Normattiva, through `cite_law`).

What it checks (sources consulted on 2026-09-25):

* `calcolo_naspi`
  - soglia (retribuzione di riferimento) and massimale 2026 against INPS circolare
    n. 4 del 28-01-2026, par. 6, read from the machine-readable content fragment
    behind the circular's page;
  - formula, decalage and duration against artt. 4 and 5 D.Lgs. 22/2015;
  - the 13-week contribution requirement of art. 3 co. 1 lett. b D.Lgs. 22/2015.
* `costo_lavoro`
  - worker IVS share 9,19% (INPS page on the ex-ENPALS funds, which states the
    33% = 23,81% + 9,19% split of the general scheme) and the 33% IVS rate of the
    FPLD (INPS page "Aliquote contributive");
  - apprentice share 5,84% (INPS circolare n. 128 del 02-11-2012) and employer
    rate 10% of art. 1 co. 773 L. 296/2006;
  - 1% additional contribution above the prima fascia pensionabile 2026
    (56.224 euro, INPS circolare n. 6 del 30-01-2026, par. 5);
  - INPDAI suppressed (art. 42 L. 289/2002), IRAP deduction of the permanent staff
    (art. 11 co. 4-octies D.Lgs. 446/1997), TFR (art. 2120 c.c., art. 3 L. 297/1982),
    IRPEF 2026 brackets (art. 11 TUIR), employee deductions (art. 13 co. 1 and 1.1
    TUIR) and the cuneo fiscale measures (art. 1 co. 4-6 L. 207/2024).

A failing test is a genuine divergence of the tool from the source: do not soften it.

Run:
    .venv/bin/pytest tests/unit/test_fonte_inps_live.py -m live -q -p no:cacheprovider -rfEs
"""

from __future__ import annotations

import functools
import re
import urllib.parse
from decimal import ROUND_HALF_UP, Decimal

import httpx
import pytest
from bs4 import BeautifulSoup

from tests.unit._norme_live import assert_parole, normalizza

pytestmark = pytest.mark.live

OGGI = "2026-09-25"

# --- INPS documents (consulted 2026-09-25) -----------------------------------------
CIRC_4_2026 = (
    "https://www.inps.it/it/it/inps-comunica/atti/circolari-messaggi-e-normativa/"
    "dettaglio.circolari-e-messaggi.2026.01.circolare-numero-4-del-28-01-2026_15147.html"
)
CIRC_6_2026 = (
    "https://www.inps.it/it/it/inps-comunica/atti/circolari-messaggi-e-normativa/"
    "dettaglio.circolari-e-messaggi.2026.01.circolare-numero-6-del-30-01-2026_15151.html"
)
CIRC_128_2012 = (
    "https://www.inps.it/it/it/inps-comunica/atti/circolari-messaggi-e-normativa/"
    "dettaglio.circolari-e-messaggi.2012.11.circolare-numero-128-del-02-11-2012_1211.html"
)
PAGINA_ALIQUOTE = (
    "https://www.inps.it/it/it/inps-comunica/diritti-e-obblighi-in-materia-di-sicurezza-"
    "sociale-nell-unione-e/per-le-imprese/aliquote-contributive.html"
)
PAGINA_EX_ENPALS = (
    "https://www.inps.it/it/it/dettaglio-scheda.it.schede-servizio-strumento.schede-servizi."
    "50286.denuncia-e-versamento-dei-contributi-ex-enpals-fondo-pensioni-lavoratori-dello-"
    "spettacolo-e-fondo-pensioni-sportivi-professionisti-.html"
)

_HEADERS = {"User-Agent": "Mozilla/5.0 (mcp-legal-it live benchmark)"}
_IMPORTO = r"(\d{1,3}(?:\.\d{3})*,\d{2})"


def _euro(testo: str) -> float:
    return float(testo.replace(".", "").replace(",", "."))


def _r2(x: float) -> float:
    """Round half up to the cent, as a payroll does (Python's round() is binary)."""
    return float(Decimal(repr(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


# 0,01 euro, plus a float epsilon so that a difference of exactly one cent passes.
CENT = 0.01 + 1e-6


@functools.lru_cache(maxsize=None)
def _circolare_inps(url_pagina: str) -> str:
    """Normalised full text of an INPS circular.

    The circular's HTML page is filled by JavaScript; the text itself comes from the
    AEM content fragment (`dettaglio.content-fragment-detail...json`), whose
    `testoCompleto.value` is URL-encoded HTML.
    """
    url_json = (
        url_pagina.replace(
            "/dettaglio.circolari-e-messaggi.",
            "/dettaglio.content-fragment-detail.circolari-e-messaggi.",
        ).removesuffix(".html")
        + ".json"
    )
    r = httpx.get(url_json, headers=_HEADERS, timeout=30, follow_redirects=True)
    r.raise_for_status()
    html = urllib.parse.unquote(r.json()["testoCompleto"]["value"])
    testo = normalizza(BeautifulSoup(html, "lxml").get_text(" "))
    assert len(testo) > 1000, f"testo della circolare vuoto o troncato: {url_json}"
    return testo


@functools.lru_cache(maxsize=None)
def _pagina_inps(url: str) -> str:
    r = httpx.get(url, headers=_HEADERS, timeout=30, follow_redirects=True)
    r.raise_for_status()
    return normalizza(BeautifulSoup(r.text, "lxml").get_text(" "))


def _cerca(pattern: str, testo: str, fonte: str) -> re.Match:
    m = re.search(pattern, testo)
    assert m, f"{fonte}: formato cambiato, non trovo /{pattern}/"
    return m


def _tool(nome: str):
    import src.server  # noqa: F401  (registers every tool module first)
    from src.tools import diritto_lavoro

    fn = getattr(diritto_lavoro, nome)
    return getattr(fn, "fn", fn)


@pytest.fixture(autouse=True)
def _oggi(monkeypatch):
    # costo_lavoro picks the IRPEF brackets of the current year: pin it.
    monkeypatch.setenv("LEGAL_TODAY", OGGI)


@pytest.fixture(scope="module")
def naspi_2026() -> dict:
    """Soglia and massimale NASpI 2026 as written in INPS circ. n. 4/2026, par. 6."""
    testo = _circolare_inps(CIRC_4_2026)
    soglia = _cerca(
        r"calcolo delle indennità di disoccupazione naspi è pari, secondo i criteri già "
        r"indicati nella circolare n\. 94 del 12 maggio 2015, a " + _IMPORTO + r" euro per il 2026",
        testo,
        "circ. INPS 4/2026 par. 6",
    )
    massimale = _cerca(
        r"non può in ogni caso superare, per il 2026,\s*" + _IMPORTO + r" euro",
        testo,
        "circ. INPS 4/2026 par. 6",
    )
    # Art. 4 co. 4 D.Lgs. 22/2015: no art. 26 L. 41/1986 reduction on the NASpI.
    _cerca(
        r"per la quale non opera la riduzione di cui all[’']articolo 26 della legge n\. 41/1986",
        testo,
        "circ. INPS 4/2026 par. 6",
    )
    return {"soglia": _euro(soglia.group(1)), "massimale": _euro(massimale.group(1))}


# ==================================================================================
# calcolo_naspi
# ==================================================================================


def test_naspi_soglia_e_massimale_2026_circolare_inps_4_2026(naspi_2026):
    """Circ. INPS n. 4 del 28-01-2026, par. 6: 1.456,72 and 1.584,70 euro for 2026."""
    r = _tool("calcolo_naspi")(retribuzione_media_mensile=2000, settimane_contributive=104, eta_anni=40)
    assert r["soglia_2026"] == naspi_2026["soglia"]
    assert r["massimale_2026"] == naspi_2026["massimale"]
    assert "Circ. INPS n. 4/2026" in r["riferimento_normativo"]
    # Both values revalue the 2015 amounts (1.195 and 1.300 euro, art. 4 co. 2) by the
    # same ISTAT index: the two ratios must agree to the fourth decimal.
    assert abs(naspi_2026["soglia"] / 1195 - naspi_2026["massimale"] / 1300) < 1e-4


@pytest.mark.parametrize(
    "retribuzione, settimane, eta, atteso_iniziale, controlli_mese",
    [
        # plan case 1: under the threshold, 75% (art. 4 co. 2); decalage from month 6
        (1000, 104, 40, 750.00, {5: 750.00, 6: 727.50, 12: 605.99}),
        # plan case 2: exactly at the 2026 threshold
        (1456.72, 52, 30, 1092.54, {5: 1092.54, 6: 1059.76}),
        # plan case 3: retribuzione that reaches the massimale exactly; 54 years -> month 6
        (3425.36, 208, 54, 1584.70, {5: 1584.70, 6: 1537.16, 24: 888.40}),
        # plan case 4: 55 years at the application -> decalage from month 8
        (3500, 208, 55, 1584.70, {6: 1584.70, 24: 944.21}),
    ],
)
def test_naspi_formula_e_decalage_art_4_dlgs_22_2015(
    naspi_2026, retribuzione, settimane, eta, atteso_iniziale, controlli_mese
):
    """Art. 4 co. 2-3 D.Lgs. 22/2015: 75% up to the threshold, +25% of the excess,
    capped; -3% a month from the first day of the 6th month (8th from age 55)."""
    assert_parole(
        "art. 4 D.Lgs. 22/2015",
        "75 per cento della retribuzione mensile",
        "25 per cento della differenza",
        "moltiplicata per il numero 4,33",
        "si riduce del 3 per cento ogni mese a decorrere dal primo giorno del sesto mese di fruizione",
        "primo giorno dell'ottavo mese di fruizione",
        "cinquantacinquesimo anno di eta' alla data di presentazione della domanda|cinquantacinquesimo anno di età alla data di presentazione della domanda",
    )
    soglia, massimale = naspi_2026["soglia"], naspi_2026["massimale"]
    base = 0.75 * retribuzione if retribuzione <= soglia else 0.75 * soglia + 0.25 * (retribuzione - soglia)
    base = _r2(min(base, massimale))
    assert base == pytest.approx(atteso_iniziale, abs=CENT)

    r = _tool("calcolo_naspi")(
        retribuzione_media_mensile=retribuzione, settimane_contributive=settimane, eta_anni=eta
    )
    assert r["importo_mensile_iniziale"] == pytest.approx(atteso_iniziale, abs=CENT)
    decorrenza = 8 if eta >= 55 else 6
    assert r["decalage_da_mese"] == decorrenza
    piano = {m["mese"]: m["importo"] for m in r["piano_mensile"]}
    for mese, atteso in controlli_mese.items():
        # compound reduction, one 3% step per month from the decorrenza included
        passi = max(0, mese - decorrenza + 1)
        assert _r2(base * 0.97**passi) == pytest.approx(atteso, abs=CENT)
        assert piano[mese] == pytest.approx(atteso, abs=CENT), f"mese {mese}"


@pytest.mark.parametrize("settimane, mesi_attesi", [(104, 12.0), (52, 6.0), (208, 24.0)])
def test_naspi_durata_meta_settimane_art_5_dlgs_22_2015(settimane, mesi_attesi):
    """Art. 5 co. 1 D.Lgs. 22/2015: half of the weeks of the last four years; the
    78-week cap was removed by D.Lgs. 148/2015. The tool converts weeks to months with
    the 4,33 coefficient of art. 4 co. 1 and rounds to a tenth of a month (INPS counts
    days: 52 weeks = 364 days), so the check allows half a tenth of a month."""
    testo = assert_parole(
        "art. 5 D.Lgs. 22/2015",
        "meta' delle settimane di contribuzione degli ultimi quattro anni|metà delle settimane di contribuzione degli ultimi quattro anni",
    )
    assert "78 settimane" not in testo
    r = _tool("calcolo_naspi")(retribuzione_media_mensile=1500, settimane_contributive=settimane, eta_anni=40)
    assert r["durata_mesi"] == pytest.approx(mesi_attesi, abs=0.05)
    assert abs(r["durata_mesi"] * 4.33 - settimane / 2) <= 0.05 * 4.33 + 1e-9


def test_naspi_requisito_tredici_settimane_art_3_dlgs_22_2015():
    """Art. 3 co. 1 lett. b D.Lgs. 22/2015: without at least 13 weeks of contribution
    in the four years there is no NASpI. Plan case 5 (12 weeks): the tool must refuse
    or flag, not quote 900 euro for 1,4 months."""
    assert_parole(
        "art. 3 D.Lgs. 22/2015",
        "almeno tredici settimane di contribuzione",
    )
    try:
        r = _tool("calcolo_naspi")(retribuzione_media_mensile=1200, settimane_contributive=12, eta_anni=30)
    except ValueError:
        return
    assert r.get("errore") or not r.get("importo_mensile_iniziale"), (
        "12 settimane < 13 (art. 3 co. 1 lett. b D.Lgs. 22/2015): nessun diritto alla NASpI, "
        f"ma il tool calcola {r.get('importo_mensile_iniziale')} euro per {r.get('durata_mesi')} mesi"
    )


# ==================================================================================
# costo_lavoro
# ==================================================================================


def test_costo_lavoro_aliquota_ivs_lavoratore_9_19_inps():
    """INPS: IVS of the FPLD (AGO) is 33%; the published split is 23,81% employer and
    9,19% worker. The tool charges 9,19% to employees and managers."""
    aliquote = _pagina_inps(PAGINA_ALIQUOTE)
    assert "assicurati al fondo pensioni lavoratori dipendenti" in aliquote
    _cerca(r"è pari al 33%", aliquote, "INPS, Aliquote contributive")
    enpals = _pagina_inps(PAGINA_EX_ENPALS)
    m = _cerca(
        r"pari al 33% della retribuzione giornaliera lorda \(o compenso\), di cui il (\d+,\d+)% a carico "
        r"del datore di lavoro \(o committente\) e il (\d+,\d+)% a carico del lavoratore",
        enpals,
        "INPS, contributi ex ENPALS",
    )
    quota_lavoratore = float(m.group(2).replace(",", "."))
    assert quota_lavoratore == 9.19
    for tipo in ("dipendente", "dirigente"):
        r = _tool("costo_lavoro")(retribuzione_lorda_annua=30000, tipo_contratto=tipo)
        assert r["aliquota_contributi_dipendente_pct"] == quota_lavoratore, tipo


def test_costo_lavoro_aliquota_apprendista_5_84_circolare_inps_128_2012():
    """Circ. INPS n. 128/2012 par. 8: the apprentice's share "rimarrà pari al 5,84% per
    tutta la durata del contratto di apprendistato". Employer: 10% (art. 1 co. 773
    L. 296/2006) + 1,61% (ASpI/NASpI and 0,30% for training, circ. 128/2012) = 11,61%,
    the full rate (firms over nine employees, or from the third year)."""
    testo = _circolare_inps(CIRC_128_2012)
    m = _cerca(
        r"la quota a carico del lavoratore, invece, rimarrà pari al (\d+,\d+)% per tutta la durata "
        r"del contratto di apprendistato",
        testo,
        "circ. INPS 128/2012",
    )
    quota_apprendista = float(m.group(1).replace(",", "."))
    assert quota_apprendista == 5.84
    _cerca(r"onere \(1,61%", testo, "circ. INPS 128/2012 (ASpI)")
    assert_parole("art. 1 L. 296/2006", "complessivamente rideterminata nel 10 per cento")

    r = _tool("costo_lavoro")(retribuzione_lorda_annua=20000, tipo_contratto="apprendista")
    assert r["aliquota_contributi_datore_pct"] == pytest.approx(10 + 1.61, abs=1e-4)
    assert r["aliquota_contributi_dipendente_pct"] == quota_apprendista, (
        f"aliquota apprendista del tool {r['aliquota_contributi_dipendente_pct']}% "
        f"contro {quota_apprendista}% della circ. INPS 128/2012"
    )
    assert r["contributi_dipendente"] == pytest.approx(20000 * quota_apprendista / 100, abs=CENT)


def test_costo_lavoro_contributo_aggiuntivo_1_per_cento_circolare_inps_6_2026():
    """Circ. INPS n. 6 del 30-01-2026 par. 5: 1% at the worker's charge (art. 3-ter
    DL 384/1992) on the pay above the prima fascia pensionabile, 56.224,00 euro for
    2026. Plan case: dirigente, 80.000 euro."""
    testo = _circolare_inps(CIRC_6_2026)
    m = _cerca(
        r"prima fascia di retribuzione pensionabile è stata determinata, per l[’']anno 2026, in "
        + _IMPORTO
        + r" euro, l[’']aliquota aggiuntiva dell[’']1%",
        testo,
        "circ. INPS 6/2026 par. 5",
    )
    prima_fascia = _euro(m.group(1))
    assert prima_fascia == 56224.00
    lordo = 80000
    atteso = _r2(lordo * 0.0919 + 0.01 * (lordo - prima_fascia))  # 7.589,76
    r = _tool("costo_lavoro")(retribuzione_lorda_annua=lordo, tipo_contratto="dirigente")
    # 0,05 euro of tolerance: INPS applies the 1% month by month on the excess over
    # 4.685,00 euro (12 x 4.685 = 56.220), so an annual computation may differ by 0,04.
    assert r["contributi_dipendente"] == pytest.approx(atteso, abs=0.05), (
        f"contributi del dirigente {r['contributi_dipendente']} contro {atteso}: manca l'1% "
        f"sulla quota eccedente {prima_fascia} euro"
    )


def test_costo_lavoro_dirigenti_inpdai_soppresso_art_42_l_289_2002():
    """Art. 42 L. 289/2002: INPDAI suppressed, managers insured in the INPS FPLD since
    2003. The tool's output still labels the managers' rates as INPDAI."""
    assert_parole("art. 42 L. 289/2002", "(inpdai)", "e' soppresso|è soppresso")
    r = _tool("costo_lavoro")(retribuzione_lorda_annua=80000, tipo_contratto="dirigente")
    assert "INPDAI" not in r["nota"], f"nota del tool: {r['nota']!r}"


def test_costo_lavoro_irap_personale_tempo_indeterminato_art_11_co_4_octies():
    """Art. 11 co. 4-octies D.Lgs. 446/1997: the whole cost of permanent staff is
    deductible from the IRAP base (apprentices, a permanent contract under art. 41
    D.Lgs. 81/2015, are deductible as well). The tool adds 3,9% of the gross pay."""
    assert_parole(
        "art. 11 D.Lgs. 446/1997",
        "4-octies",
        "e' ammesso in deduzione il costo complessivo per il personale dipendente con contratto a tempo indeterminato|è ammesso in deduzione il costo complessivo per il personale dipendente con contratto a tempo indeterminato",
    )
    r = _tool("costo_lavoro")(retribuzione_lorda_annua=30000)
    assert r["irap_stimata"] == 0, (
        f"IRAP {r['irap_stimata']} euro sommata al costo di un dipendente a tempo indeterminato "
        "(deducibile per intero, art. 11 co. 4-octies D.Lgs. 446/1997)"
    )


def test_costo_lavoro_tfr_art_2120_cc_e_contributo_0_50_l_297_1982():
    """Art. 2120 c.c.: yearly quota = retribuzione / 13,5 (7,4074%). Art. 3 L. 297/1982:
    the 0,50% additional IVS contribution is deducted from the TFR quota. The tool's
    6,91% is that net quota rounded to two decimals: 1/13,5 - 0,50% = 6,9074%."""
    assert_parole("art. 2120 c.c.", "divisa per 13,5")
    assert_parole(
        "art. 3 L. 297/1982",
        "dall'ammontare della quota del trattamento di fine rapporto",
    )
    lordo = 30000
    quota_netta = _r2(lordo / 13.5 - 0.005 * lordo)  # 2.072,22
    r = _tool("costo_lavoro")(retribuzione_lorda_annua=lordo)
    assert r["tfr_annuo"] == pytest.approx(quota_netta, abs=CENT), (
        f"TFR del tool {r['tfr_annuo']} (6,91%) contro {quota_netta} (1/13,5 meno 0,50%)"
    )


def test_costo_lavoro_scaglioni_irpef_2026_art_11_tuir():
    """Art. 11 TUIR vigente: 23% to 28.000, 33% to 50.000, 43% above (2026). The table
    `irpef_scaglioni` read by the tool must carry the same 2026 brackets. Plan case:
    55.000 euro, imponibile 49.945,50, IRPEF 13.677,29 (tool 13.677,28: the tool rounds
    the gross tax before the deduction, a one-cent difference within tolerance)."""
    assert_parole(
        "art. 11 TUIR",
        "fino a 28.000 euro, 23 per cento",
        "oltre 28.000 euro e fino a 50.000 euro, 33 per cento",
        "oltre 50.000 euro, 43 per cento",
    )
    from src.tools.diritto_lavoro import _IRPEF

    s2026 = _IRPEF["scaglioni_per_anno"]["2026"]
    assert [(s.get("fino_a"), s["aliquota"]) for s in s2026] == [(28000, 23), (50000, 33), (None, 43)]
    assert _IRPEF["_vintage"]["copre_fino_a"] >= "2026-12-31"

    r = _tool("costo_lavoro")(retribuzione_lorda_annua=55000)
    imponibile = 55000 - _r2(55000 * 0.0919)
    lorda = _r2(28000 * 0.23 + (imponibile - 28000) * 0.33)  # 13.682,02
    detrazione = _r2(1910 * (50000 - imponibile) / 22000)  # 4,73
    atteso = _r2(lorda - detrazione)  # 13.677,29
    assert r["imponibile_irpef"] == pytest.approx(imponibile, abs=CENT)
    assert r["irpef_stimata"] == pytest.approx(atteso, abs=CENT)


def test_costo_lavoro_irpef_30000_detrazioni_art_13_tuir_e_l_207_2024():
    """Plan case: dipendente, 30.000 euro. Imponibile 27.243 (30.000 - 9,19%), imposta
    lorda 6.265,89; detrazione art. 13 co. 1 lett. b 1.979,29 + 65 euro (co. 1.1,
    reddito tra 25.000 e 35.000) + ulteriore detrazione 1.000 euro (art. 1 co. 6 lett. a
    L. 207/2024, reddito tra 20.000 e 32.000): IRPEF netta 3.221,60."""
    assert_parole(
        "art. 13 TUIR",
        "aumentata di un importo pari a 65 euro",
        "superiore a 25.000 euro ma non a 35.000 euro",
    )
    assert_parole(
        "art. 1 L. 207/2024",
        "spetta un'ulteriore detrazione dall'imposta lorda",
        "a 1.000 euro, se l'ammontare del reddito complessivo e' superiore a 20.000 euro ma non a 32.000 euro|a 1.000 euro, se l'ammontare del reddito complessivo è superiore a 20.000 euro ma non a 32.000 euro",
    )
    imponibile = 30000 - 2757.00
    lorda = _r2(imponibile * 0.23)
    detrazione = _r2(1910 + 1190 * (28000 - imponibile) / 13000) + 65 + 1000
    atteso = _r2(lorda - detrazione)
    assert atteso == pytest.approx(3221.60, abs=CENT)
    r = _tool("costo_lavoro")(retribuzione_lorda_annua=30000)
    assert r["irpef_stimata"] == pytest.approx(atteso, abs=CENT), (
        f"IRPEF del tool {r['irpef_stimata']} contro {atteso}: mancano i 65 euro dell'art. 13 "
        "co. 1.1 TUIR e i 1.000 euro dell'art. 1 co. 6 L. 207/2024"
    )


def test_costo_lavoro_netto_15000_somma_esente_l_207_2024():
    """Plan case: dipendente, 15.000 euro. Reddito di lavoro dipendente 13.621,50
    (between 8.500 and 15.000): a sum of 5,3% that does not form income is due
    (art. 1 co. 4 lett. b L. 207/2024), 721,94 euro, paid with the salary. IRPEF
    1.177,95 as in the tool; net pay 15.000 - 1.378,50 - 1.177,95 + 721,94 = 13.165,49."""
    assert_parole(
        "art. 1 L. 207/2024",
        "riconosciuta una somma, che non concorre alla formazione del reddito",
        "5,3 per cento, se il reddito di lavoro dipendente",
    )
    lordo = 15000
    contributi = _r2(lordo * 0.0919)
    reddito = lordo - contributi
    irpef = _r2(_r2(reddito * 0.23) - 1955)  # 1.177,95
    somma_esente = _r2(reddito * 0.053)  # 721,94
    atteso = _r2(lordo - contributi - irpef + somma_esente)
    assert atteso == pytest.approx(13165.49, abs=CENT)
    r = _tool("costo_lavoro")(retribuzione_lorda_annua=lordo)
    assert r["irpef_stimata"] == pytest.approx(irpef, abs=CENT)
    assert r["netto_stimato"] == pytest.approx(atteso, abs=CENT), (
        f"netto del tool {r['netto_stimato']} contro {atteso}: manca la somma esente "
        f"di {somma_esente} euro (art. 1 co. 4 L. 207/2024)"
    )

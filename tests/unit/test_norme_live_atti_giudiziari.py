"""Live gate: `tassazione_atti` against the vigente text of the imposta di registro.

Phase 4 of the avvocatoandreani.it benchmark, strategy `solo_norma`, group `atti_giudiziari`.
The benchmark site has no calculator for the registration tax on judicial acts (its page is a
redirect to the Agenzia delle Entrate service), so this file reads the norms the tool applies
and checks both the words the code relies on and what the tool answers:

* Tariffa parte I, art. 8, DPR 131/1986: 3% on condanne (lett. b), 1% on accertamenti
  (lett. c), transfers taxed like the corresponding acts (lett. a), fixed tax otherwise;
  Nota II: no proportional tax on the part of a condanna for corrispettivi subject to IVA.
* art. 41, co. 2, DPR 131/1986: the principal tax is never below the fixed tax of art. 11
  of the tariffa; art. 26, co. 2, D.L. 104/2013: the fixed tax is 200 euro since 2014.
* art. 1 tariffa parte I as replaced by art. 10 D.Lgs. 23/2011: 9% / 2% prima casa, and
  never below 1.000 euro (art. 10, co. 2).
* art. 46 L. 374/1991: causes worth up to 1.033 euro pay only the contributo unificato
  (the Agenzia delle Entrate reads it for every office and grade: circolare 30/E of
  29 July 2022).
* art. 17, co. 2, D.Lgs. 28/2010: the mediation agreement is exempt up to 100.000 euro.
* D.Lgs. 123/2025 (testo unico dell'imposta di registro e degli altri tributi indiretti):
  abrogates the DPR 131/1986 tariffa from 1 January 2027 (artt. 204-205).

Why this file does not read DPR 131/1986 through `cite_law`: Normattiva's URN without a
date serves the newest version of the article, and for the body of the DPR 131/1986 that is
already the one abrogated by D.Lgs. 123/2025 with effect from 1 January 2027 ("ARTICOLO
ABROGATO"). `_vigente_oggi()` asks Normattiva for the version in force today (`!vig=`) and
asserts the page's validity window covers today; the tariffa is read from the Akoma Ntoso
export at today's date, selecting the "Tariffa Parte I" component explicitly.

A failing test here is a genuine divergence of the tool from the norm (or a change of the
norm): do not soften it. It needs the network and is skipped by default:

    .venv/bin/pytest tests/unit/test_norme_live_atti_giudiziari.py -m live -q -p no:cacheprovider -rfEs
"""

from __future__ import annotations

import asyncio
import inspect
import re
from datetime import date

import pytest

from tests.unit._norme_live import assert_parole, contiene, normalizza

pytestmark = pytest.mark.live

_NORMATTIVA = "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:"
_DPR_131_1986 = "decreto.del.presidente.della.repubblica:1986-04-26;131"
_DL_104_2013 = "decreto.legge:2013-09-12;104"
_DLGS_23_2011 = "decreto.legislativo:2011-03-14;23"
_DLGS_28_2010 = "decreto.legislativo:2010-03-04;28"
_L_374_1991 = "legge:1991-11-21;374"

_VIGORE = re.compile(
    r"testo in vigore dal:\s*(\d{1,2})-(\d{1,2})-(\d{4})(?:\s*al:\s*(\d{1,2})-(\d{1,2})-(\d{4}))?"
)


def _oggi() -> date:
    from src.lib import _clock

    return _clock.today()


def _vigente_oggi(urn: str, articolo: str) -> str:
    """Normalised text of the article in the version Normattiva marks in force today."""
    import httpx
    from bs4 import BeautifulSoup

    from src.lib.visualex.scraper import _HEADERS

    oggi = _oggi()
    url = f"{_NORMATTIVA}{urn}~art{articolo}!vig={oggi.isoformat()}"
    with httpx.Client(headers=_HEADERS, timeout=40, follow_redirects=True) as client:
        resp = client.get(url)
        resp.raise_for_status()
    pagina = BeautifulSoup(resp.text, "lxml").get_text(" ", strip=True)
    # Normattiva wraps amended words in "((...))" and writes some apostrophes as backticks.
    pagina = normalizza(pagina.replace("((", "").replace("))", "").replace("`", "'"))
    inizio = pagina.find("testo in vigore dal")
    assert inizio >= 0, f"{url}: pagina senza intestazione di vigenza"
    fine = pagina.find("articolo precedente", inizio)
    corpo = pagina[inizio: fine if fine > 0 else None]
    m = _VIGORE.match(corpo)
    assert m, f"{url}: intestazione di vigenza illeggibile: {corpo[:120]!r}"
    dal = date(int(m[3]), int(m[2]), int(m[1]))
    al = date(int(m[6]), int(m[5]), int(m[4])) if m[4] else None
    assert dal <= oggi and (al is None or oggi <= al), f"{url}: versione {dal}..{al} non copre {oggi}"
    return corpo


def _tariffa_parte_prima(articolo: str) -> str:
    """Normalised text of an article of the Tariffa parte I, DPR 131/1986, in force today."""
    import src.server  # noqa: F401  (registers every tool module first: avoids a circular import)
    from src.lib.visualex.akn_fetch import fetch_act_akn
    from src.lib.visualex.models import Norma

    atto = asyncio.run(fetch_act_akn(Norma("decreto del presidente della repubblica", "1986", "131")))
    assert atto is not None, "export Akoma Ntoso del DPR 131/1986 non disponibile"
    parti = [nome for nome in atto.parts if re.match(r"tariffa parte i\b", nome.lower())]
    assert len(parti) == 1, f"componente 'Tariffa Parte I' non trovata: {list(atto.parts)}"
    testo = atto.parts[parti[0]].articles.get(articolo) or ""
    assert testo, f"art. {articolo} della Tariffa parte I assente"
    return normalizza(testo)


def _assert_testo(testo: str, riferimento: str, *frasi: str) -> None:
    missing = contiene(testo, *frasi)
    assert not missing, f"{riferimento}: il testo vigente non contiene {missing}"


def _aliquota_dopo(testo: str, etichetta: str) -> int:
    """The first 'N%' the tariff table prints after the label of a letter."""
    m = re.search(re.escape(normalizza(etichetta)) + r".*?(\d+)\s*%", testo)
    assert m, f"nessuna aliquota dopo {etichetta!r}"
    return int(m.group(1))


def _tassazione():
    import src.server  # noqa: F401
    from src.tools.atti_giudiziari import tassazione_atti

    return getattr(tassazione_atti, "fn", tassazione_atti)


def _imposta(**kwargs) -> float:
    risultato = _tassazione()(**kwargs)
    assert "errore" not in risultato, risultato
    return risultato["imposta_registro"]


# ---------------------------------------------------------------------------
# Which text is in force
# ---------------------------------------------------------------------------


def test_dpr_131_1986_si_applica_fino_al_31_dicembre_2026_poi_dlgs_123_2025():
    """artt. 204-205 D.Lgs. 123/2025: the DPR 131/1986 tariffa is abrogated from 1.1.2027.

    The tool cites 'DPR 131/1986, Tariffa Parte I'. From 1 January 2027 the minimum of the
    principal tax moves to art. 12 of the tariffa in allegato 1 to D.Lgs. 123/2025 (art. 45,
    co. 2): this test fails on that date so the tool is re-read against the new testo unico.
    """
    assert_parole("art. 205 D.Lgs. 123/2025", "si applicano a decorrere dal 1° gennaio 2027")
    assert_parole(
        "art. 204 D.Lgs. 123/2025",
        "a decorrere dalla data di cui all'articolo 205 sono abrogate",
        "la tariffa, la tabella e il prospetto dei coefficienti di cui al decreto del presidente "
        "della repubblica 26 aprile 1986, n. 131",
    )
    assert_parole(
        "art. 45 D.Lgs. 123/2025",
        "misura fissa indicata nell'articolo 12 della parte i della tariffa",
    )
    assert _oggi() < date(2027, 1, 1), (
        "dal 1° gennaio 2027 si applica il D.Lgs. 123/2025: aggiornare Vigenza, "
        "riferimento_normativo e aliquote di tassazione_atti sulla tariffa dell'allegato 1"
    )


# ---------------------------------------------------------------------------
# What the tool gets right
# ---------------------------------------------------------------------------


def test_tariffa_parte_I_art_8_lett_b_condanna_al_3_per_cento():
    """Tariffa parte I, art. 8, co. 1, lett. b), DPR 131/1986: condanne e decreti ingiuntivi 3%."""
    testo = _tariffa_parte_prima("8")
    _assert_testo(
        testo,
        "art. 8 Tariffa parte I DPR 131/1986",
        "in materia di controversie civili che definiscono, anche parzialmente, il giudizio",
        "compresi i decreti ingiuntivi esecutivi",
        "recanti condanna al pagamento di somme o valori",
        "di accertamento di diritti a contenuto patrimoniale",
    )
    assert _aliquota_dopo(testo, "recanti condanna al pagamento di somme o") == 3
    assert _aliquota_dopo(testo, "di accertamento di diritti a contenuto") == 1

    assert _imposta(tipo_atto="sentenza_condanna", valore=50000) == pytest.approx(1500.0, abs=0.01)
    assert _imposta(tipo_atto="decreto_ingiuntivo", valore=50000) == pytest.approx(1500.0, abs=0.01)


def test_art_41_co_2_dpr_131_minimo_pari_alla_misura_fissa_di_200_euro():
    """art. 41, co. 2, DPR 131/1986 + art. 26, co. 2, D.L. 104/2013: minimum 200 euro.

    6.666 x 3% = 199,98 -> 200,00 (minimum). 6.667 x 3% = 200,01: the rounding to the euro of
    art. 41, co. 1, applies since 1.1.2025 (D.Lgs. 139/2024) only to acts *other than* the
    judicial ones of art. 37, so the literal text gives 200,01 as the tool does.
    """
    art_41 = _vigente_oggi(_DPR_131_1986, "41")
    _assert_testo(
        art_41,
        "art. 41 DPR 131/1986",
        "in nessun caso inferiore alla misura fissa indicata nell'articolo 11 della tariffa",
        "per gli atti diversi da quelli giudiziari di cui all'articolo 37",
        "arrotondamento all'unità di euro",
    )
    _assert_testo(
        _tariffa_parte_prima("11"),
        "art. 11 Tariffa parte I DPR 131/1986",
        "atti di ogni specie per i quali e prevista l'applicazione dell'imposta in misura fissa"
        "|atti di ogni specie per i quali è prevista l'applicazione dell'imposta in misura fissa",
    )
    _assert_testo(
        _vigente_oggi(_DL_104_2013, "26"),
        "art. 26 D.L. 104/2013",
        "stabilito in misura fissa di euro 168",
        "è elevato ad euro 200|e' elevato ad euro 200",
    )

    assert _imposta(tipo_atto="sentenza_condanna", valore=6666) == pytest.approx(200.0, abs=0.01)
    assert _imposta(tipo_atto="sentenza_condanna", valore=6667) == pytest.approx(200.01, abs=0.01)
    # lett. d): no condanna, accertamento or transfer -> fixed tax
    assert _imposta(tipo_atto="sentenza_condanna", valore=0) == pytest.approx(200.0, abs=0.01)


def test_verbale_prima_casa_2_per_cento_con_minimo_di_1000_euro():
    """Tariffa parte I, art. 8, lett. a) + art. 1 (art. 10, co. 1-2, D.Lgs. 23/2011): 2%, min 1.000."""
    _assert_testo(
        _tariffa_parte_prima("8"),
        "art. 8 Tariffa parte I DPR 131/1986",
        "recanti trasferimento o costituzione di diritti reali su beni immobili",
        "le stesse imposte stabilite per i corrispondenti atti",
    )
    _assert_testo(
        _vigente_oggi(_DLGS_23_2011, "10"),
        "art. 10 D.Lgs. 23/2011",
        "9 per cento",
        "ove ricorrano le condizioni di cui alla nota ii-bis) 2 per cento",
        "non può essere inferiore a 1.000 euro|non puo' essere inferiore a 1.000 euro",
    )

    assert _imposta(tipo_atto="verbale_conciliazione", valore=40000, prima_casa=True) == pytest.approx(
        1000.0, abs=0.01
    )  # 2% = 800 < 1.000
    assert _imposta(tipo_atto="verbale_conciliazione", valore=60000, prima_casa=True) == pytest.approx(
        1200.0, abs=0.01
    )


# ---------------------------------------------------------------------------
# Where the norm says something else
# ---------------------------------------------------------------------------


def test_art_46_l_374_1991_cause_fino_a_1033_euro_esenti_dal_registro():
    """art. 46, co. 1, L. 374/1991: causes up to 1.033,00 euro pay only the contributo unificato.

    Circolare Agenzia delle Entrate 30/E del 29/07/2022: the exemption covers every act and
    measure of such causes, whatever the office and the grade. The tool charges 200 euro.
    """
    _assert_testo(
        _vigente_oggi(_L_374_1991, "46"),
        "art. 46 L. 374/1991",
        "il cui valore non eccede la somma di euro 1.033,00",
        "sono soggetti soltanto al pagamento del contributo unificato",
    )

    # just above the threshold the exemption no longer applies: 3% = 30,99 -> minimum 200
    assert _imposta(tipo_atto="decreto_ingiuntivo", valore=1033.01) == pytest.approx(200.0, abs=0.01)
    assert _imposta(tipo_atto="decreto_ingiuntivo", valore=1000) == pytest.approx(0.0, abs=0.01)
    assert _imposta(tipo_atto="sentenza_condanna", valore=1000) == pytest.approx(0.0, abs=0.01)
    assert _imposta(tipo_atto="decreto_ingiuntivo", valore=1033) == pytest.approx(0.0, abs=0.01)


def test_ordinanza_che_definisce_il_giudizio_con_condanna_sconta_il_3_per_cento():
    """Tariffa parte I, art. 8, co. 1: the tax follows the content of the act, not its form.

    Every act of the judge that defines the civil judgment, even partially (and the
    'provvedimenti di aggiudicazione e quelli di assegnazione'), is taxed under letters a)-g):
    an ordinanza carrying a condanna of 20.000 euro pays 3% = 600 euro. The tool answers a
    fixed 200 euro for every ordinanza, whatever the amount it is given.
    """
    _assert_testo(
        _tariffa_parte_prima("8"),
        "art. 8 Tariffa parte I DPR 131/1986",
        "atti dell'autorita' giudiziaria ordinaria e speciale in materia di controversie civili"
        "|atti dell'autorità giudiziaria ordinaria e speciale in materia di controversie civili",
        "i provvedimenti di aggiudicazione e quelli di assegnazione",
    )

    assert _imposta(tipo_atto="ordinanza", valore=20000) == pytest.approx(600.0, abs=0.01)


def test_nota_II_art_8_condanna_per_corrispettivi_iva_in_misura_fissa():
    """Nota II all'art. 8 Tariffa parte I + art. 40, co. 1, DPR 131/1986 (alternativita' IVA).

    A decreto ingiuntivo of 50.000 euro on invoices subject to IVA pays the fixed 200 euro,
    not 1.500: the tool has no input to say the credit is subject to IVA.
    """
    _assert_testo(
        _tariffa_parte_prima("8"),
        "Nota II art. 8 Tariffa parte I DPR 131/1986",
        "non sono soggetti all'imposta proporzionale per la parte in cui dispongono il pagamento "
        "di corrispettivi o prestazioni soggetti all'imposta sul valore aggiunto",
    )
    _assert_testo(
        _vigente_oggi(_DPR_131_1986, "40"),
        "art. 40 DPR 131/1986",
        "soggetti all'imposta sul valore aggiunto, l'imposta si applica in misura fissa",
    )

    parametri = inspect.signature(_tassazione()).parameters
    assert any("iva" in nome.lower() for nome in parametri), (
        "tassazione_atti non puo' distinguere la condanna per corrispettivi soggetti a IVA "
        f"(Nota II art. 8): parametri {list(parametri)}"
    )


def test_verbale_di_conciliazione_trasferimento_al_9_per_cento_e_mediazione_esente():
    """art. 8, lett. a) + art. 1 Tariffa parte I (9%); art. 17, co. 2, D.Lgs. 28/2010.

    A verbale transferring a house that is not a prima casa pays 9% (minimum 1.000), not 3%;
    a mediation agreement is exempt up to 100.000 euro. With `prima_casa=False` the tool
    always applies 3% (min 200), and it cannot tell a transfer from a payment obligation, nor
    a judicial conciliation from a mediation agreement.
    """
    _assert_testo(
        _vigente_oggi(_DLGS_23_2011, "10"),
        "art. 10 D.Lgs. 23/2011",
        "atti traslativi a titolo oneroso della proprietà di beni immobili in genere",
        "9 per cento",
    )
    _assert_testo(
        _vigente_oggi(_DLGS_28_2010, "17"),
        "art. 17 D.Lgs. 28/2010",
        "il verbale e l'accordo di conciliazione sono esenti dall'imposta di registro entro il "
        "limite di valore di centomila euro",
    )

    parametri = [nome.lower() for nome in inspect.signature(_tassazione()).parameters]
    mancano = []
    if not any("trasfer" in nome or "contenuto" in nome for nome in parametri):
        mancano.append("trasferimento non prima casa (9%, art. 1 Tariffa parte I)")
    if not any("mediazione" in nome for nome in parametri):
        mancano.append("accordo di mediazione (esente fino a 100.000 euro, art. 17 D.Lgs. 28/2010)")
    assert not mancano, f"tassazione_atti non distingue: {mancano}; parametri {parametri}"


def test_valore_negativo_rifiutato():
    """A negative amount is not a tax base: the tool should answer with 'errore', not 200 euro."""
    risultato = _tassazione()(tipo_atto="decreto_ingiuntivo", valore=-500)
    assert "errore" in risultato, risultato

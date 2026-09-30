"""Live gate (phase 4, official source): the GDPR calculators against the EDPB and the Garante.

Checks the three calculators of `src/tools/privacy_gdpr.py` that rest on a supervisory
authority's method rather than on a number printed in a statute:

- `calcolo_sanzione_gdpr` (table `src/data/gdpr_sanzioni.json`) against art. 83 GDPR (vigente
  text via `cite_law`, EUR-Lex/CELLAR) and the EDPB Guidelines 04/2022 on the calculation of
  administrative fines, version 2.1 (adopted 24/05/2023, corrected 29/06/2023), PDF;
- `valutazione_data_breach` (no table) against artt. 33-34 GDPR, the EDPB Guidelines 9/2022 on
  personal data breach notification, version 2.0 (adopted 28/03/2023), PDF, and the Garante's
  self-assessment tool at https://servizi.gpdp.it/databreach/s/self-assesment (driven with
  Playwright; the misspelt path is the Garante's own);
- `verifica_necessita_dpia` (table `src/data/gdpr_dpia_criteri.json`) against art. 35 GDPR, the
  Garante's provv. n. 467 of 11/10/2018 [doc. web 9058979] (the nine WP248 rev.01 criteria and
  the two-criteria threshold) and its Allegato 1 [doc. web 9059358] (the art. 35(4) list, PDF).

Sources read on 25/09/2026. Every test needs the network; the PDF-based ones also need the
`pdftotext` binary (poppler) and are skipped without it. The Garante's web application firewall
sometimes drops automated requests from an address for a while: those tests are then skipped
(source unavailable), never passed. A failing test here is a genuine discrepancy between the
tool and the official source, reported by the phase-4 benchmark; do not relax it to make it pass.

    .venv/bin/pytest tests/unit/test_fonte_edpb_garante_live.py -m live -q -p no:cacheprovider -rfEs
"""

from __future__ import annotations

import asyncio
import os
import re
import shutil
import subprocess
import tempfile
import time

import httpx
import pytest

from tests.unit._norme_live import contiene, normalizza
from tests.unit._norme_live import testo_vigente as _testo_vigente

pytestmark = pytest.mark.live

_BROWSER_UA = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    )
}

# EDPB guidelines, final adopted versions (URLs as served on 25/09/2026, after the host's redirect
# from /system/files/<yyyy-mm>/... to /system/files/documents/<yyyy-mm>/...).
_EDPB_SANZIONI_PDF = (
    "https://www.edpb.europa.eu/system/files/documents/2023-06/"
    "edpb_guidelines_042022_calculationofadministrativefines_en.pdf"
)
_EDPB_BREACH_PDF = (
    "https://www.edpb.europa.eu/system/files/documents/2023-04/"
    "edpb_guidelines_202209_personal_data_breach_notification_v2.0_en.pdf"
)

# Allegato 1 to provv. n. 467/2018: the PDF linked from doc. web 9059358 on 25/09/2026. The
# docweb page itself is not fetched to keep the requests to the Garante's WAF to a minimum.
_GARANTE_ALLEGATO_1_PDF = (
    "https://www.garanteprivacy.it/documents/10160/0/"
    "ALLEGATO+1+Elenco+delle+tipologie+di+trattamenti+soggetti+al+meccanismo+di+coerenza"
    "+da+sottoporre+a+valutazione+di+impatto.pdf/b9ceefa9-dd65-df86-fed4-df3c3570f59d?version=1.11"
)

# The Garante's "chiarimento interpretativo" on the list (https://www.garanteprivacy.it/regolamentoue/DPIA,
# redirecting to /valutazione-d-impatto-della-protezione-dei-dati-dpia-, read on 25/09/2026). Frozen
# here rather than fetched, to spare the WAF a further request: it states that "sistematici" and
# "non occasionali" in items 6, 11 and 12 of the list are to be read as the WP248 "larga scala"
# criterion, and that "dati biometrici" in item 11 means data processed to identify a person uniquely.
_CHIARIMENTO_VOCI_LARGA_SCALA = (6, 11, 12)

_ATTENUANTI_PIANO = [
    "prima violazione",
    "cooperazione piena",
    "misure correttive immediate",
    "danno limitato",
    "dimensione ridotta",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _tool(name: str):
    import src.server  # noqa: F401  (registers every tool module first: avoids a circular import)
    from src.tools import privacy_gdpr

    obj = getattr(privacy_gdpr, name)
    return getattr(obj, "fn", obj)


def _sanzione(**kwargs) -> dict:
    return _tool("calcolo_sanzione_gdpr")(**kwargs)


def _breach(**kwargs) -> dict:
    return _tool("valutazione_data_breach")(**kwargs)


def _dpia(**kwargs) -> dict:
    return _tool("verifica_necessita_dpia")(**kwargs)


def _tabella_dpia() -> dict:
    import src.server  # noqa: F401
    from src.tools.privacy_gdpr import _DPIA

    return _DPIA


def _pdf_text(url: str, headers: dict | None = None, *, fonte: str) -> str:
    """Download a PDF and return its normalised text (pdftotext, no layout)."""
    exe = shutil.which("pdftotext")
    if not exe:
        pytest.skip("pdftotext (poppler) non installato: serve per leggere i PDF delle fonti")
    resp = None
    for tentativo in range(3):  # retries: both hosts answer 5xx or drop the connection now and then
        try:
            resp = httpx.get(url, headers=headers or _BROWSER_UA, follow_redirects=True, timeout=60)
        except httpx.HTTPError as exc:
            if tentativo == 2:
                pytest.skip(f"{fonte} non raggiungibile: {exc!r}")
        else:
            if resp.status_code < 500:
                break
        time.sleep(10)
    if resp.status_code in (403, 429) or resp.status_code >= 500:
        pytest.skip(f"{fonte}: HTTP {resp.status_code} (WAF o server non disponibile)")
    assert resp.status_code == 200, f"{fonte}: HTTP {resp.status_code} su {url} (documento spostato?)"
    assert resp.content.startswith(b"%PDF"), f"{fonte}: la risposta non e' un PDF ({url})"
    fd, path = tempfile.mkstemp(suffix=".pdf")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(resp.content)
        out = subprocess.run([exe, "-enc", "UTF-8", path, "-"], capture_output=True, text=True, check=True)
    finally:
        os.unlink(path)
    return normalizza(out.stdout)


def _massimale_effettivo(risultato: dict) -> int:
    nota = risultato["range_stimato"]["nota"]
    m = re.search(r"Massimale effettivo applicato \(maggiore tra i due\): ([\d,]+)€", nota)
    assert m, f"nota senza massimale effettivo: {nota!r}"
    return int(m.group(1).replace(",", ""))


# ---------------------------------------------------------------------------
# Sources (one fetch per module)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def art83() -> str:
    return _testo_vigente("art. 83 GDPR")


@pytest.fixture(scope="module")
def massimali_art83(art83) -> dict[str, tuple[int, int]]:
    """{tier: (static maximum in EUR, % of turnover)} parsed from paragraphs 4, 5 and 6 of art. 83."""
    trovati = re.findall(
        r"fino a ([\d ]+) eur, o per le imprese, fino al (\d+) ?% del fatturato mondiale totale "
        r"annuo dell.esercizio precedente, se superiore",
        art83,
    )
    assert len(trovati) == 3, f"art. 83: attesi tre massimali (parr. 4, 5, 6), trovati {trovati}"
    return {
        tier: (int(euro.replace(" ", "")), int(pct))
        for tier, (euro, pct) in zip(("art83_4", "art83_5", "art83_6"), trovati)
    }


@pytest.fixture(scope="module")
def edpb_sanzioni() -> str:
    testo = _pdf_text(_EDPB_SANZIONI_PDF, fonte="EDPB Linee guida 04/2022")
    assert not contiene(testo, "guidelines 04/2022 on the calculation of administrative fines", "version 2.1")
    return testo


@pytest.fixture(scope="module")
def edpb_breach() -> str:
    testo = _pdf_text(_EDPB_BREACH_PDF, fonte="EDPB Linee guida 9/2022")
    assert not contiene(testo, "guidelines 9/2022 on personal data breach notification", "version 2.0")
    return testo


def _garante_headers() -> dict:
    from src.lib.gpdp.client import _HEADERS

    return dict(_HEADERS)


@pytest.fixture(scope="module")
def provv_467() -> str:
    """Normalised text of provv. n. 467 of 11/10/2018 [doc. web 9058979], via the project's client."""
    import src.server  # noqa: F401
    from src.lib.gpdp.client import fetch_doc

    try:
        _, testo = asyncio.run(fetch_doc(9058979))
    except httpx.HTTPError as exc:
        pytest.skip(f"Garante (doc. web 9058979) non raggiungibile, WAF o rete: {exc!r}")
    testo = normalizza(testo)
    if "web page blocked" in testo or "non è disponibile" in testo:
        pytest.skip("Garante (doc. web 9058979): pagina bloccata dal WAF o non disponibile")
    assert not contiene(testo, "n. 467 dell'11 ottobre 2018|n. 467 dell’11 ottobre 2018"), testo[:500]
    return testo


@pytest.fixture(scope="module")
def allegato_1() -> dict[int, str]:
    """{item number: normalised text} of Allegato 1 to provv. n. 467/2018 (the art. 35(4) list)."""
    testo = _pdf_text(_GARANTE_ALLEGATO_1_PDF, _garante_headers(), fonte="Garante, Allegato 1 [doc. web 9059358]")
    starts = list(re.finditer(r"(?:^|\s)(\d{1,2})\.\s+(?=trattament)", testo))
    voci = {}
    for i, m in enumerate(starts):
        fine = starts[i + 1].start() if i + 1 < len(starts) else len(testo)
        voci[int(m.group(1))] = testo[m.end():fine].strip()
    assert sorted(voci) == list(range(1, 13)), f"Allegato 1: attese le voci 1-12, trovate {sorted(voci)}"
    return voci


# ---------------------------------------------------------------------------
# calcolo_sanzione_gdpr — art. 83 GDPR and EDPB Guidelines 04/2022
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("tier", ["art83_4", "art83_5", "art83_6"])
def test_sanzione_massimali_art83_4_5_6_coincidono_con_il_testo_vigente(massimali_art83, tier):
    """Art. 83(4): 10 000 000 EUR or 2 %; art. 83(5) and (6): 20 000 000 EUR or 4 %."""
    euro, pct = massimali_art83[tier]
    r = _sanzione(tipo_violazione=tier)
    assert (r["massimale"]["euro"], r["massimale"]["pct_fatturato"]) == (euro, pct)


def test_sanzione_criteri_art83_2_coprono_le_lettere_da_a_a_k(art83):
    """Art. 83(2) lists eleven elements, a) to k); k) is 'eventuali altri fattori aggravanti o attenuanti'."""
    par2 = art83[art83.find("2. le sanzioni amministrative"):art83.find("3. se, in relazione")]
    assert par2, "art. 83: paragrafo 2 non individuato"
    lettere_norma = [lettera for lettera in "abcdefghijk" if f"{lettera})" in par2]
    assert lettere_norma == list("abcdefghijk")
    assert "eventuali altri fattori aggravanti o attenuanti" in par2
    lettere_tool = [c["id"] for c in _sanzione(tipo_violazione="art83_4")["criteri_art83_2"]]
    assert lettere_tool == lettere_norma, (
        f"criteri_art83_2 del tool: {lettere_tool}; art. 83(2) vigente: {lettere_norma} "
        "(manca la lettera k)"
    )


@pytest.mark.parametrize(
    "tier, fatturato",
    [
        ("art83_5", 1_000_000_000),  # 4 % = 40 mln > 20 mln
        ("art83_5", 500_000_000),  # boundary: 4 % = 20 mln = static maximum
        ("art83_5", 400_000_000),  # 4 % = 16 mln < 20 mln: static maximum applies
        ("art83_4", 1_000_000_000),  # 2 % = 20 mln > 10 mln
    ],
)
def test_sanzione_massimale_effettivo_e_il_maggiore_tra_fisso_e_percentuale(massimali_art83, tier, fatturato):
    """'se superiore' (art. 83(4)-(6)): the applicable maximum is the higher of the two."""
    euro, pct = massimali_art83[tier]
    atteso = max(euro, fatturato * pct // 100)
    assert _massimale_effettivo(_sanzione(tipo_violazione=tier, fatturato_annuo=fatturato)) == atteso


def test_sanzione_range_neutro_art83_4_cade_nella_fascia_di_gravita_bassa_edpb(edpb_sanzioni, massimali_art83):
    """EDPB 04/2022 par. 60: starting amount 0-10 % (low), 10-20 % (medium), 20-100 % (high) of the maximum.

    Without factors the tool's range (0,5 %-5 % of the maximum) sits inside the low band: this is what
    the estimate means, since the tool asks for no seriousness level.
    """
    assert not contiene(
        edpb_sanzioni,
        "between 0 and 10% of the applicable legal maximum",
        "between 10 and 20% of the applicable legal maximum",
        "between 20 and 100% of the applicable legal maximum",
    )
    massimale = massimali_art83["art83_4"][0]
    r = _sanzione(tipo_violazione="art83_4")
    assert 0 <= r["range_stimato"]["minimo"] <= r["range_stimato"]["massimo"] <= 0.10 * massimale


@pytest.mark.parametrize(
    "attenuanti",
    [pytest.param(_ATTENUANTI_PIANO, id="cinque_attenuanti"), pytest.param([], id="nessun_fattore")],
)
def test_sanzione_microimpresa_2_milioni_rettifica_dimensionale_edpb(edpb_sanzioni, massimali_art83, attenuanti):
    """EDPB 04/2022 par. 65: turnover <= EUR 2 m -> 0.2-0.4 % of the starting amount.

    Even at the top of the high band (100 % of the 10 mln maximum) the adjusted starting amount of an
    undertaking with EUR 2 m turnover is at most 10 000 000 x 0.4 % = 40 000 euro. The tool ignores the
    size of the undertaking (the turnover only raises the maximum above 10 mln), so its range for the
    plan's micro-enterprise case goes beyond that ceiling even with five mitigating factors.
    """
    assert not contiene(
        edpb_sanzioni,
        "annual turnover of ≤ €2m",
        "between 0.2% and 0.4% of the identified starting amount",
        "between 20 and 100% of the applicable legal maximum",
    )
    massimale = massimali_art83["art83_4"][0]
    tetto_edpb = massimale * 1.00 * 0.004  # high band at 100 %, largest size adjustment for <= 2 mln
    r = _sanzione(tipo_violazione="art83_4", fatturato_annuo=2_000_000, fattori_attenuanti=attenuanti)
    assert r["range_stimato"]["massimo"] <= tetto_edpb, (
        f"range del tool {r['range_stimato']['minimo']:,.0f}-{r['range_stimato']['massimo']:,.0f} euro; "
        f"EDPB (fatturato <= 2 mln): punto di partenza al massimo {tetto_edpb:,.0f} euro"
    )


def test_sanzione_grande_impresa_gravita_alta_raggiunge_la_fascia_alta_edpb(edpb_sanzioni, massimali_art83):
    """EDPB 04/2022 par. 60 and 66: above EUR 500 m no size adjustment; high seriousness starts at 20 %.

    With the dynamic maximum of 40 mln (4 % of 1 bn) the high band starts at 8 mln. Before the fix the
    tool asked for no seriousness level and capped the upper bound at 15 % at best, so no case could
    reach the EDPB high band. The tool now takes `gravita`; the case is asked with gravita='alta'
    (the parameter did not exist when this test was written).
    """
    assert not contiene(
        edpb_sanzioni,
        "annual turnover above €500m",
        "between 20 and 100% of the applicable legal maximum",
    )
    euro, pct = massimali_art83["art83_5"]
    massimale_dinamico = max(euro, 1_000_000_000 * pct // 100)
    r = _sanzione(
        tipo_violazione="art83_5",
        fatturato_annuo=1_000_000_000,
        fattori_aggravanti=[
            "trattamento su larga scala",
            "dati particolari",
            "violazione dolosa",
            "violazione sistematica e continuativa",
            "profitto economico dalla violazione",
        ],
        precedenti=True,
        gravita="alta",
    )
    assert r["range_stimato"]["massimo"] >= 0.20 * massimale_dinamico, (
        f"range del tool {r['range_stimato']['minimo']:,.0f}-{r['range_stimato']['massimo']:,.0f} euro; "
        f"fascia alta EDPB {0.20 * massimale_dinamico:,.0f}-{massimale_dinamico:,.0f} euro"
    )


# ---------------------------------------------------------------------------
# valutazione_data_breach — artt. 33-34 GDPR, EDPB 9/2022, Garante self-assessment
# ---------------------------------------------------------------------------


def test_breach_art33_e_art34_testo_vigente():
    """Art. 33(1): notify within 72 hours unless the breach is unlikely to result in a risk; art. 33(5):
    document every breach. Art. 34(1): communicate on high risk; 34(3)(a): unintelligible data (encryption)."""
    art33 = _testo_vigente("art. 33 GDPR")
    assert not contiene(
        art33,
        "entro 72 ore",
        "a meno che sia improbabile che la violazione dei dati personali presenti un rischio",
        "documenta qualsiasi violazione dei dati personali",
    )
    art34 = _testo_vigente("art. 34 GDPR")
    assert not contiene(
        art34,
        "suscettibile di presentare un rischio elevato",
        "rendere i dati personali incomprensibili a chiunque non sia autorizzato ad accedervi, quali la cifratura",
    )
    r = _breach(tipo_violazione="confidenzialita", categorie_dati=["email"], n_interessati=100, impatto="basso")
    assert "72 ore" in r["ore_rimanenti"]
    assert any("33(5)" in a for a in r["azioni_consigliate"])


_WIZARD = "https://servizi.gpdp.it/databreach/s/self-assesment"  # sic: the Garante's own spelling
_PREMESSE = ["Risposta1_SI", "Risposta2_SI", "Risposta5Titolare"]  # security incident, personal data, controller
_RAMI = {
    "improbabile": _PREMESSE + ["Risposta6_NO"],  # risk unlikely
    "possibile": _PREMESSE + ["Risposta6_SI", "Domanda7_NO"],  # risk, not high risk
    "probabile": _PREMESSE + ["Risposta6_SI", "Domanda7_SI"],  # high risk
}


def _autovalutazione_garante(risposte: list[str]) -> str:
    """Drive the Garante's self-assessment wizard and return the normalised text of the outcome page."""
    sync_api = pytest.importorskip("playwright.sync_api")
    coda = list(risposte)
    with sync_api.sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_context(locale="it-IT").new_page()
            try:
                page.goto(_WIZARD, wait_until="domcontentloaded", timeout=60_000)
                page.get_by_role("button", name="Avanti").first.wait_for(timeout=45_000)
            except sync_api.Error as exc:
                pytest.skip(f"autovalutazione Garante non disponibile: {exc}")
            page.get_by_role("button", name="Avanti").click()
            for _ in range(20):
                page.wait_for_timeout(2_500)
                if page.query_selector_all("input[type=radio]"):
                    if not coda:
                        pytest.skip("autovalutazione Garante: domanda non prevista (struttura cambiata?)")
                    valore = coda.pop(0)
                    scelta = page.query_selector(f"input[type=radio][value='{valore}']")
                    if scelta is None:
                        pytest.skip(f"autovalutazione Garante: risposta {valore} assente (struttura cambiata?)")
                    scelta.check(force=True)
                    page.wait_for_timeout(500)
                avanti = page.get_by_role("button", name="Avanti")
                if avanti.count() == 0:
                    break
                avanti.click()
            assert not coda, f"autovalutazione Garante: risposte non usate {coda}"
            return normalizza(page.inner_text("body"))
        finally:
            browser.close()


@pytest.mark.parametrize(
    "caso, livello_atteso",
    [
        pytest.param(
            dict(tipo_violazione="confidenzialita", categorie_dati=["email"], n_interessati=100, impatto="basso"),
            "improbabile",
            id="piano1_rischio_improbabile",
        ),
        pytest.param(
            dict(tipo_violazione="confidenzialita", categorie_dati=["email"], n_interessati=100_000, impatto="medio"),
            "possibile",
            id="100000_interessati",
        ),
        pytest.param(
            dict(tipo_violazione="confidenzialita", categorie_dati=["email"], n_interessati=100_001, impatto="medio"),
            "probabile",
            id="piano2_100001_interessati",
        ),
    ],
)
def test_breach_esiti_coincidono_con_l_autovalutazione_del_garante(caso, livello_atteso):
    """Given the tool's own risk level, notification and communication follow the Garante's decision tree.

    The Garante asks the controller two questions (risk? high risk?) and fixes no numeric threshold: the
    tool's step at 100 000 data subjects is a convention of the tool, and this test checks only that,
    once the level is set, the obligations drawn from it are those the Garante's tool gives.
    """
    r = _breach(**caso)
    assert r["livello_rischio"] == livello_atteso
    esito = _autovalutazione_garante(_RAMI[livello_atteso])
    notifica = "devi notificare la violazione al garante" in esito
    comunicazione = "devi comunicare la violazione agli interessati" in esito
    assert "devi documentare la violazione" in esito
    assert (r["notifica_garante"], r["comunicazione_interessati"]) == (notifica, comunicazione)


def test_breach_cifratura_non_esclude_la_comunicazione_se_i_dati_sono_persi(edpb_breach):
    """EDPB 9/2022 par. 76 and 79: encryption makes the data unintelligible, it does not bring them back.

    Plan case: unavailability of encrypted health data of 50 people, high impact. The tool rates the
    risk 'molto probabile' but drops the communication because of the encryption (art. 34(3)(a)),
    which covers only unintelligibility, i.e. confidentiality.
    """
    assert not contiene(
        edpb_breach,
        "even where data is encrypted, a loss or alteration can have negative consequences",
        "communication to data subjects would be required, even if the data itself was subject to adequate encryption measures",
    )
    r = _breach(
        tipo_violazione="disponibilita",
        categorie_dati=["dati sanitari"],
        n_interessati=50,
        dati_particolari=True,
        misure_protezione=["cifratura AES-256"],
        impatto="alto",
    )
    assert r["livello_rischio"] == "molto probabile"
    assert r["comunicazione_interessati"] is True, r["motivo_no_comunicazione"]


def test_breach_pseudonimizzazione_non_rende_i_dati_incomprensibili(edpb_breach):
    """EDPB 9/2022 par. 112: 'pseudonymisation techniques alone cannot be regarded as making the data
    unintelligible' -- the tool treats 'pseudonimizzazione' like encryption for art. 34(3)(a)."""
    assert not contiene(
        edpb_breach, "pseudonymisation techniques alone cannot be regarded as making the data unintelligible"
    )
    r = _breach(
        tipo_violazione="confidenzialita",
        categorie_dati=["dati sanitari"],
        n_interessati=50,
        dati_particolari=True,
        misure_protezione=["pseudonimizzazione"],
        impatto="alto",
    )
    assert r["livello_rischio"] == "molto probabile"
    assert r["comunicazione_interessati"] is True, r["motivo_no_comunicazione"]


def test_breach_riservatezza_dati_cifrati_niente_comunicazione(edpb_breach):
    """EDPB 9/2022 par. 76-78: confidentiality breach of properly encrypted data, key intact -> no high risk,
    no communication. The tool still notifies the Garante: conservative, since it cannot know whether the
    key is intact and a backup exists (par. 78 lets the controller skip the notification only then)."""
    assert not contiene(
        edpb_breach,
        "if the confidentiality of the key is intact",
        "would not need to be informed either as there is likely no high risk",
    )
    r = _breach(
        tipo_violazione="confidenzialita",
        categorie_dati=["dati sanitari"],
        n_interessati=50,
        dati_particolari=True,
        misure_protezione=["cifratura AES-256"],
        impatto="alto",
    )
    assert r["notifica_garante"] is True
    assert r["comunicazione_interessati"] is False


# ---------------------------------------------------------------------------
# verifica_necessita_dpia — art. 35 GDPR, provv. Garante 467/2018 and its Allegato 1
# ---------------------------------------------------------------------------

_CRITERI_WP248_PROVV = [
    "1) valutazione o assegnazione di un punteggio",
    "2) processo decisionale automatizzato",
    "3) monitoraggio sistematico degli interessati",
    "4) dati sensibili o dati aventi carattere altamente personale",
    "5) trattamento di dati su larga scala",
    "6) creazione di corrispondenze o combinazione di insiemi di dati",
    "7) dati relativi a interessati vulnerabili",
    "8) uso innovativo o applicazione di nuove soluzioni tecnologiche",
    "9) quando il trattamento in sé",
]


def _segmento_criteri(provv: str) -> str:
    inizio = provv.find("seguenti nove criteri")
    fine = provv.find("rilevato che il ricorrere")
    assert 0 <= inizio < fine, "provv. 467/2018: elenco dei nove criteri non individuato"
    return provv[inizio:fine]


def test_dpia_nove_criteri_wp248_e_soglia_di_due_nel_provv_467_2018(provv_467):
    """Provv. 467/2018 restates the nine WP248 rev.01 criteria and 'il ricorrere di due o più' as the threshold."""
    assert not contiene(provv_467, "il ricorrere di due o più dei predetti criteri", *_CRITERI_WP248_PROVV)
    tabella = _tabella_dpia()
    assert len(tabella["criteri_wp248"]) == 9
    assert tabella["soglia_criteri"] == 2


def test_dpia_trasferimento_extra_ue_non_e_un_criterio_wp248(provv_467):
    """Plan case 1: large-scale CRM with servers in the USA -> one WP248 criterion (5), below the threshold.

    The transfer outside the EU is not among the nine criteria of WP248 rev.01 as restated by the Garante,
    nor in the Allegato 1 list; the tool adds it as a tenth 'criterio aggiuntivo' and so reaches two.
    """
    criteri = _segmento_criteri(provv_467)
    assert "trasferiment" not in criteri and "paesi terzi" not in criteri
    r = _dpia(tipo_trattamento="CRM su larga scala con server negli USA", larga_scala=True, trasferimento_extra_ue=True)
    assert r["n_criteri"] == 1, r["criteri_soddisfatti"]
    assert r["dpia_necessaria"] is False


def test_dpia_tabella_elenco_garante_riproduce_l_allegato_1(allegato_1):
    """`lista_garante_italiano` in gdpr_dpia_criteri.json against the twelve items of Allegato 1.

    Checks only verifiable facts: item 5 (remote monitoring of employees) and item 10 (art. 9/10 data
    interconnected with data collected for other purposes) must have an entry; the vulnerable subjects
    of item 6 are 'minori, disabili, anziani, infermi di mente, pazienti, richiedenti asilo' (employees are
    covered by item 5, not 6); no item concerns 'dati biometrici di dipendenti'.
    """
    tabella = [normalizza(v) for v in _tabella_dpia()["lista_garante_italiano"]]
    assert "controllo a distanza dell’attività dei dipendenti" in allegato_1[5]
    assert "interconnessi con altri dati personali raccolti per finalità diverse" in allegato_1[10]
    assert "minori, disabili, anziani, infermi di mente, pazienti, richiedenti asilo" in allegato_1[6]
    assert not any("biometrici di dipendenti" in allegato_1[n] for n in allegato_1)

    scostamenti = []
    if not any("controllo a distanza" in v or "rapporto di lavoro" in v for v in tabella):
        scostamenti.append("manca la voce 5 (rapporto di lavoro, controllo a distanza dei dipendenti)")
    if not any("interconness" in v and ("art. 9" in v or "categorie particolari" in v) for v in tabella):
        scostamenti.append("manca la voce 10 (dati ex artt. 9-10 interconnessi con dati raccolti per altre finalità)")
    vulnerabili = [v for v in tabella if "vulnerabil" in v]
    if any("dipendenti" in v for v in vulnerabili):
        scostamenti.append(f"voce 6 con categorie non previste (dipendenti): {vulnerabili}")
    if any("biometrici di dipendenti" in v for v in tabella):
        scostamenti.append("voce inesistente: 'trattamenti sistematici di dati biometrici di dipendenti'")
    assert not scostamenti, scostamenti


@pytest.mark.parametrize(
    "voce, parametri",
    [
        pytest.param(2, {"valutazione_scoring": True}, id="voce2_decisioni_automatizzate"),
        pytest.param(3, {"monitoraggio_sistematico": True}, id="voce3_monitoraggio_sistematico"),
        pytest.param(9, {"incrocio_dataset": True}, id="voce9_interconnessione"),
    ],
)
def test_dpia_voce_autonoma_dell_elenco_rende_la_dpia_obbligatoria(allegato_1, voce, parametri):
    """Art. 35(4): processing on the Garante's list requires a DPIA. Items 2, 3 and 9 carry no 'larga scala'
    qualifier and no 'almeno un altro dei criteri' condition (EDPB Opinion 12/2018 asked for the latter only
    on items 7, 11 and 12), so one matching feature is enough. The tool counts one WP248 criterion and
    answers dpia_necessaria=False (for items 2 and 9 while naming the list item in lista_garante_match)."""
    testo = allegato_1[voce]
    assert "larga scala" not in testo and "almeno un altro" not in testo, testo
    r = _dpia(tipo_trattamento=f"trattamento della voce {voce} dell'elenco del Garante", **parametri)
    assert r["dpia_necessaria"] is True, (r["n_criteri"], r["lista_garante_match"])


@pytest.mark.parametrize(
    "voce, parametri, frammento",
    [
        pytest.param(7, {"nuove_tecnologie": True}, "tecnologie innovative", id="voce7_tecnologie_innovative"),
        pytest.param(6, {"soggetti_vulnerabili": True}, "vulnerabili", id="voce6_soggetti_vulnerabili"),
    ],
)
def test_dpia_voci_6_e_7_non_corrispondono_con_un_solo_criterio(allegato_1, voce, parametri, frammento):
    """Item 7 applies 'ogniqualvolta ricorra anche almeno un altro dei criteri' WP248; item 6 concerns
    'trattamenti non occasionali', which the Garante's chiarimento reads as 'larga scala' (items 6, 11, 12).
    With the single feature the tool still reports the item in lista_garante_match."""
    if voce == 7:
        assert "almeno un altro dei criteri" in allegato_1[7]
    else:
        assert "non occasionali" in allegato_1[6] and voce in _CHIARIMENTO_VOCI_LARGA_SCALA
    r = _dpia(tipo_trattamento=f"trattamento della voce {voce} con un solo criterio", **parametri)
    assert not any(frammento in normalizza(v) for v in r["lista_garante_match"]), r["lista_garante_match"]


def test_dpia_videosorveglianza_centro_commerciale_art_35_3_c():
    """Plan case 2: art. 35(3)(c), systematic monitoring of a publicly accessible area on a large scale."""
    assert not contiene(
        _testo_vigente("art. 35 GDPR"),
        "la sorveglianza sistematica su larga scala di una zona accessibile al pubblico",
    )
    r = _dpia(
        tipo_trattamento="videosorveglianza di un centro commerciale",
        monitoraggio_sistematico=True,
        larga_scala=True,
    )
    assert r["dpia_necessaria"] is True and r["n_criteri"] == 2


def test_dpia_newsletter_profilata_un_solo_criterio(provv_467):
    """Plan case 3: profiling alone is one WP248 criterion, below the 'due o più' threshold.

    Allegato 1 item 1 names 'trattamenti che comportano la profilazione degli interessati' next to scoring
    'su larga scala'; whether the qualifier also governs profiling is a matter of reading, so this test
    checks only the WP248 threshold the tool applies.
    """
    assert "il ricorrere di due o più dei predetti criteri" in provv_467
    r = _dpia(tipo_trattamento="newsletter con profilazione", profilazione=True)
    assert (r["n_criteri"], r["dpia_necessaria"]) == (1, False)
    assert "fortemente consigliata" in r["motivazione"]


def test_dpia_presenze_biometriche_dipendenti_voce_11(allegato_1):
    """Plan case 4: biometric attendance of employees -> DPIA required (criteria 4, 7, 8) and item 11 of
    the list ('trattamenti sistematici di dati biometrici'), which the tool could not match: it had no
    parameter for biometric data.

    The tool now takes `dati_biometrici`; item 11 reads 'sistematici' as large scale (the Garante's
    interpretive clarification, items 6, 11, 12), so the case is asked with larga_scala=True as well
    (which adds WP248 criterion 5: four criteria instead of the three of the original plan case)."""
    assert "trattamenti sistematici di dati biometrici" in allegato_1[11]
    r = _dpia(
        tipo_trattamento="rilevazione presenze biometrica dei dipendenti",
        dati_sensibili=True,
        dati_biometrici=True,
        larga_scala=True,
        soggetti_vulnerabili=True,
        nuove_tecnologie=True,
    )
    assert r["dpia_necessaria"] is True and r["n_criteri"] == 4
    assert any("biometric" in normalizza(v) for v in r["lista_garante_match"]), r["lista_garante_match"]

"""Live gate: the F24 codes and the company-formation costs checked against the official sources.

Two tools, one benchmark group ("agenzia_entrate", strategy "fonte_ufficiale"):

* ``cerca_codice_tributo`` (``src/data/codici_tributo.json``, 55 codes). Every code the tool
  returns is compared with the tables the Agenzia delle Entrate publishes, downloaded live:
  - "Tabella codici tributo erariali e regionali ordinata per codice tributo crescente" (xlsx,
    aggiornamento del 23 settembre 2026 at the time of writing), linked from
    https://www.agenziaentrate.gov.it/portale/strumenti/codici-attivita-e-tributo/f24-codici-tributo-per-i-versamenti/tabelle-dei-codici-tributo-e-altri-codici-per-il-modello-f24/tabella-codici-tributo-erariali-e-regionali
  - "Tabella dei codici tributo versamenti con elementi identificativi" (F24 ELIDE, xlsx,
    aggiornamento del 27/28 luglio 2026), same page;
  - "Tabella codici tributo IMU, TASI, TARI, IMIS ed altri tributi locali" (pdf, aggiornamento
    del 27 marzo 2026), linked from .../tabelle-codici-per-tributi-locali. The pdf is read with
    the ``pdftotext`` binary (poppler); without it those codes are skipped, not passed.
  For each code the test asserts that the code exists in the official table, that the official
  description contains the concept words listed in ``CONCETTI`` (so a change of the AdE table is
  noticed), and that the tool's description contains the same concept words. The section
  (erario / regioni / enti_locali) is compared with the "tipo tributo" column.

* ``costi_costituzione`` (hard-coded amounts in ``src/tools/diritto_societario.py``):
  - tassa di concessione governativa sui libri sociali (309,87 / 516,46 euro, due by S.p.a.,
    S.r.l., S.a.p.a.): AdE scheda
    https://www.agenziaentrate.gov.it/portale/schede/pagamenti/f24verstassareg/f24-tassa-ccgg
  - diritti di segreteria and imposta di bollo of the Registro imprese: Camera di commercio di
    Roma, https://www.rm.camcom.it/pagina3431_diritti-di-segreteria-e-bolli-societ.html and
    https://www.rm.camcom.it/pagina3375_diritti-di-segreteria-e-bolli-imprese-individuali.html
  - diritto annuale 2026 for new registrations: Camera di commercio di Bologna,
    https://www.bo.camcom.gov.it/it/diritto-annuale/diritto-2026 (amounts already include the
    20% increase authorised by D.M. MIMIT 17 marzo 2026);
  - bollo forfettario MUI for "atti propri delle societa'" (Tariffa DPR 642/1972, art. 1 co.
    1-bis.1, 156 euro): Consiglio notarile di Milano, massima I.10,
    https://www.consiglionotarilemilano.it/massime-registro-imprese/i-10/ (value frozen, not
    fetched: the site answers 403 to a self-identified client);
  - imposta di registro in misura fissa 200 euro (art. 26 co. 2 DL 104/2013), exemptions of the
    s.r.l.s. (art. 3 co. 3 DL 1/2012), artt. 2327, 2342, 2463 c.c.: vigente text via cite_law.

All sources consulted on 2026-09-25. It needs the network and is skipped by default:

    .venv/bin/pytest tests/unit/test_fonte_agenzia_entrate_live.py -m live -q -p no:cacheprovider -rfEs

A failing test here is a genuine difference between the tool and the official source: the
message says what the source states. Do not relax a check to make it pass; fix the data.
"""

from __future__ import annotations

import io
import json
import re
import shutil
import subprocess
import tempfile
import unicodedata
from pathlib import Path

import pytest

pytestmark = pytest.mark.live

ROOT = Path(__file__).resolve().parents[2]

ADE_BASE = "https://www.agenziaentrate.gov.it"
ADE_EREL_PAGE = (
    ADE_BASE + "/portale/strumenti/codici-attivita-e-tributo/f24-codici-tributo-per-i-versamenti/"
    "tabelle-dei-codici-tributo-e-altri-codici-per-il-modello-f24/tabella-codici-tributo-erariali-e-regionali"
)
ADE_LOCALI_PAGE = (
    ADE_BASE + "/portale/strumenti/codici-attivita-e-tributo/f24-codici-tributo-per-i-versamenti/"
    "tabelle-dei-codici-tributo-e-altri-codici-per-il-modello-f24/tabelle-codici-per-tributi-locali"
)
ADE_TCG_PAGE = ADE_BASE + "/portale/schede/pagamenti/f24verstassareg/f24-tassa-ccgg"
CCIAA_RM_SOCIETA = "https://www.rm.camcom.it/pagina3431_diritti-di-segreteria-e-bolli-societ.html"
CCIAA_RM_INDIVIDUALI = "https://www.rm.camcom.it/pagina3375_diritti-di-segreteria-e-bolli-imprese-individuali.html"
CCIAA_BO_DIRITTO_2026 = "https://www.bo.camcom.gov.it/it/diritto-annuale/diritto-2026"
CNM_BOLLO_MUI = "https://www.consiglionotarilemilano.it/massime-registro-imprese/i-10/"

_UA = {"User-Agent": "Mozilla/5.0 (compatible; mcp-legal-it live benchmark)"}


# ---------------------------------------------------------------------------
# fetch helpers
# ---------------------------------------------------------------------------

def _get(url: str) -> bytes:
    import httpx

    r = httpx.get(url, follow_redirects=True, timeout=60, headers=_UA)
    r.raise_for_status()
    return r.content


def _page_text(url: str) -> str:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(_get(url), "lxml")
    for tag in soup(["script", "style"]):
        tag.decompose()
    return re.sub(r"\s+", " ", soup.get_text(" ", strip=True))


def _link(url: str, *anchor_words: str) -> str:
    """Absolute href of the first link whose text contains every one of `anchor_words`."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(_get(url), "lxml")
    for a in soup.find_all("a"):
        testo = re.sub(r"\s+", " ", a.get_text(" ", strip=True)).lower()
        if all(w.lower() in testo for w in anchor_words):
            href = a.get("href", "")
            return href if href.startswith("http") else ADE_BASE + href
    raise AssertionError(f"{url}: nessun link con {anchor_words} (la pagina AdE e' cambiata)")


def _xlsx_rows(content: bytes):
    import openpyxl

    wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True)
    return list(wb.worksheets[0].iter_rows(values_only=True))


def _norm(testo: str) -> str:
    """Lower case, punctuation to spaces, single spaces (AdE writes 'IMP.SOST.DELL'IRPEF')."""
    testo = unicodedata.normalize("NFC", str(testo or "")).lower()
    return re.sub(r"\s+", " ", re.sub(r"[^\w]+", " ", testo)).strip()


# ---------------------------------------------------------------------------
# official AdE tables (module scope: each file is downloaded once)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def tabella_erel() -> dict[str, tuple[str, str]]:
    """{codice: (tipo tributo, descrizione)} from the EREL xlsx ordered by code."""
    href = _link(ADE_EREL_PAGE, "erariali e regionali ordinata per codice tributo crescente")
    out = {}
    for row in _xlsx_rows(_get(href)):
        if row and row[0] is not None and row[8]:
            out[str(row[0]).strip()] = (str(row[2] or ""), str(row[8]))
    assert len(out) > 1000, f"tabella EREL troppo corta ({len(out)} righe): formato cambiato?"
    return out


@pytest.fixture(scope="module")
def tabella_elide() -> dict[str, tuple[str, str]]:
    """{codice: (tipo tributo, descrizione)} from the F24 ELIDE xlsx ordered by code."""
    href = _link(ADE_EREL_PAGE, "elementi identificativi ordinata per codice tributo crescente")
    out = {}
    for row in _xlsx_rows(_get(href)):
        if row and row[0] is not None and row[7]:
            out[str(row[0]).strip()] = (str(row[1] or ""), str(row[7]))
    assert "1500" in out, "tabella F24 ELIDE senza il codice 1500: formato cambiato?"
    return out


@pytest.fixture(scope="module")
def tabella_locali() -> dict[str, tuple[str, str]]:
    """{codice: (tipo tributo, testo intorno alla riga)} from the IMU/TARI pdf, via pdftotext."""
    exe = shutil.which("pdftotext")
    if not exe:
        pytest.skip("pdftotext (poppler) non installato: tabella IMU/TARI non leggibile")
    href = _link(ADE_LOCALI_PAGE, "tabella codici tributo imu")
    with tempfile.TemporaryDirectory() as tmp:
        pdf = Path(tmp) / "locali.pdf"
        pdf.write_bytes(_get(href))
        txt = subprocess.run([exe, "-layout", str(pdf), "-"], capture_output=True, text=True, check=True).stdout
    lines = txt.splitlines()
    out = {}
    for i, line in enumerate(lines):
        m = re.match(r"\s*T4\s+(\d{4})\s+\w\s+(\S+(?:\s\S+)*?)\s{2,}", line)
        if m:
            finestra = " ".join(lines[max(0, i - 2): i + 3])
            out[m.group(1)] = (m.group(2), finestra)
    assert "3918" in out, "tabella tributi locali senza il 3918: formato cambiato?"
    return out


# ---------------------------------------------------------------------------
# the tool
# ---------------------------------------------------------------------------

def _cerca(query: str) -> list[dict]:
    import src.server  # noqa: F401  (registers every tool module first)
    from src.tools.dichiarazione_redditi import cerca_codice_tributo

    fn = getattr(cerca_codice_tributo, "fn", cerca_codice_tributo)
    righe = []
    for line in fn(query=query).splitlines():
        celle = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(celle) == 4 and re.fullmatch(r"[0-9A-Z]{4}", celle[0]):
            righe.append(dict(zip(("codice", "descrizione", "sezione", "categoria"), celle)))
    return righe


def _codici_del_tool() -> list[str]:
    dati = json.loads((ROOT / "src/data/codici_tributo.json").read_text(encoding="utf-8"))
    return [c["codice"] for c in dati["codici"]]


# Concept words derived from the OFFICIAL description of each code (regex, on normalised text).
# The official description must match them (guards the reading of the table) and so must the
# tool's description (the claim under test). Source: "erel", "elide" or "locali".
MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto",
        "settembre", "ottobre", "novembre", "dicembre"]
CONCETTI: dict[str, tuple[str, list[str]]] = {
    "4001": ("erel", [r"irpef", r"saldo"]),
    "4033": ("erel", [r"irpef", r"acconto", r"(prima rata|primo)"]),
    "4034": ("erel", [r"irpef", r"acconto", r"(seconda ?rata|secondo)", r"unica soluzione"]),
    "1040": ("erel", [r"ritenute", r"lavoro autonomo", r"arti e professioni"]),
    # 1038 was suppressed from 1 January 2017 (ris. AdE 13/E del 17 marzo 2016) and merged in 1040.
    "1038": ("erel", [r"ritenute", r"provvigioni"]),
    "1001": ("erel", [r"ritenute", r"retribuzioni", r"pensioni"]),
    "1712": ("erel", [r"sostitutiva", r"rivalutazion", r"(trattamento di fine rapporto|tfr)", r"acconto"]),
    "1713": ("erel", [r"sostitutiva", r"rivalutazion", r"(trattamento di fine rapporto|tfr)", r"saldo"]),
    # AdE: 1840/1841/1842 are the cedolare secca (art. 3 D.Lgs. 23/2011), not the forfettario.
    # The AdE text abbreviates 'locazione' as 'LOCAZ.' or 'LOC.': hence '\bloc'.
    "1840": ("erel", [r"(cedolare|\bloc)", r"acconto", r"(prima rata|primo)"]),
    "1841": ("erel", [r"(cedolare|\bloc)", r"acconto", r"(seconda ?rata|secondo)"]),
    "1842": ("erel", [r"(cedolare|\bloc)", r"saldo"]),
    "6099": ("erel", [r"\biva\b", r"annual"]),
    **{f"60{m:02d}": ("erel", [r"\biva\b", r"mensile", MESI[m - 1]]) for m in range(1, 13)},
    # AdE: 6013 = "versamento acconto per IVA mensile" (the quarterly acconto is 6035).
    "6013": ("erel", [r"\biva\b", r"acconto", r"mensil"]),
    "6031": ("erel", [r"\biva\b", r"trimestral", r"\b1 trimestre"]),
    "6032": ("erel", [r"\biva\b", r"trimestral", r"\b2 trimestre"]),
    "6033": ("erel", [r"\biva\b", r"trimestral", r"\b3 trimestre"]),
    "6034": ("erel", [r"\biva\b", r"(quarto|\b4) trimestre"]),
    "1989": ("erel", [r"interessi", r"ravvedimento", r"irpef"]),
    "1991": ("erel", [r"interessi", r"ravvedimento", r"\biva\b"]),
    "8901": ("erel", [r"sanzione", r"irpef"]),
    "8904": ("erel", [r"sanzione", r"\biva\b"]),
    "3918": ("locali", [r"imu", r"altri fabbricati", r"comune"]),
    "3912": ("locali", [r"imu", r"abitaz", r"princ"]),
    "3914": ("locali", [r"imu", r"terreni", r"comune"]),
    "3916": ("locali", [r"imu", r"aree fabbricabili", r"comune"]),
    "3944": ("locali", [r"tari", r"rifiuti"]),
    # AdE: 1550/1551/1552 are "atti privati" (registro, sanzione registro, bollo), not the cedolare.
    "1550": ("erel", [r"atti privati", r"imposta di registro"]),
    "1551": ("erel", [r"atti privati", r"sanzione", r"registro"]),
    "1552": ("erel", [r"atti privati", r"bollo"]),
    "1500": ("elide", [r"registro", r"(locazion|affitt)"]),
    "1501": ("elide", [r"registro", r"annualit"]),
    "1502": ("elide", [r"registro", r"cession"]),
    "1503": ("elide", [r"registro", r"risoluzion"]),
    "1504": ("elide", [r"registro", r"(proroga|proroghe)"]),
    "3800": ("erel", [r"(irap|imposta regionale sulle attivit)", r"saldo"]),
    "3812": ("erel", [r"irap", r"acconto", r"(prima rata|primo)"]),
    "3813": ("erel", [r"irap", r"acconto", r"(seconda ?rata|secondo)"]),
    "3801": ("erel", [r"addizionale regionale", r"(irpef|imposta sul reddito delle persone fisiche)"]),
    # AdE (ris. 368/E del 12/12/2007): 3843 = acconto, 3844 = saldo.
    "3843": ("erel", [r"addizionale comunale", r"acconto"]),
    "3844": ("erel", [r"addizionale comunale", r"saldo"]),
    # AdE: 1630 = interessi sulla rateazione dell'IRPEF trattenuta dal sostituto (assistenza
    # fiscale), 1631 = imposte rimborsate dal sostituto; 1632 does not exist. The civil
    # contributo unificato has no F24 code in these tables (only GA01... for the TAR/CdS, F24 ELIDE).
    "1630": ("erel", [r"interessi", r"dilazionat", r"assistenza fiscale"]),
    "1631": ("erel", [r"rimborsat", r"assistenza fiscale"]),
    "1632": ("erel", [r"contributo unificato|diritti di copia|bollo"]),
}

_SEZIONE_DA_TIPO = {"erario": "erario", "regioni": "regioni", "enti locali": "enti_locali"}


def test_ogni_codice_del_tool_ha_un_riscontro_dichiarato():
    """The mapping above covers exactly the codes of src/data/codici_tributo.json."""
    assert sorted(_codici_del_tool()) == sorted(CONCETTI), (
        "aggiungere/togliere la voce in CONCETTI per i codici: "
        f"{sorted(set(_codici_del_tool()) ^ set(CONCETTI))}"
    )


@pytest.mark.parametrize("codice", sorted(CONCETTI))
def test_codice_tributo_coincide_con_tabella_ade(codice, request):
    fonte, concetti = CONCETTI[codice]
    tabella = request.getfixturevalue(f"tabella_{fonte}")
    assert codice in tabella, (
        f"{codice}: il codice non compare nella tabella AdE ({fonte}) consultata; il tool lo propone "
        "come vigente"
        + (" (soppresso dal 1.1.2017, ris. 13/E del 17 marzo 2016: usare 1040)" if codice == "1038" else "")
    )
    tipo, descr_ade = tabella[codice]
    ade = _norm(descr_ade)
    mancanti_ade = [c for c in concetti if not re.search(c, ade)]
    assert not mancanti_ade, f"{codice}: la descrizione AdE '{descr_ade}' non contiene {mancanti_ade} (tabella cambiata?)"

    righe = [r for r in _cerca(codice) if r["codice"] == codice]
    assert righe, f"{codice}: il tool non restituisce il codice"
    riga = righe[0]
    mancanti_tool = [c for c in concetti if not re.search(c, _norm(riga["descrizione"]))]
    assert not mancanti_tool, (
        f"{codice}: il tool dice '{riga['descrizione']}', la tabella AdE dice '{descr_ade.strip()}'"
    )

    sezione_attesa = "enti_locali" if fonte == "locali" else next(
        (v for k, v in _SEZIONE_DA_TIPO.items() if _norm(tipo).startswith(k)), None
    )
    assert riga["sezione"] == sezione_attesa, f"{codice}: sezione {riga['sezione']!r}, AdE tipo tributo {tipo!r}"


def test_ricerca_forfettario_restituisce_1790_1791_1792(tabella_erel):
    """Plan case "forfettario": AdE 1790 acconto prima rata, 1791 seconda rata/unica, 1792 saldo."""
    for c in ("1790", "1791", "1792"):
        assert "forfetario" in _norm(tabella_erel[c][1]), tabella_erel[c]
    trovati = {r["codice"] for r in _cerca("forfettario")} | {r["codice"] for r in _cerca("forfetario")}
    assert trovati == {"1790", "1791", "1792"}, f"il tool restituisce {sorted(trovati)} per il forfettario"


def test_ricerca_cedolare_restituisce_1840_1841_1842(tabella_erel):
    """Plan case "cedolare": AdE 1840/1841/1842 (art. 3 D.Lgs. 23/2011)."""
    for c in ("1840", "1841", "1842"):
        assert "23 2011" in _norm(tabella_erel[c][1]), tabella_erel[c]
    trovati = {r["codice"] for r in _cerca("cedolare")}
    assert trovati == {"1840", "1841", "1842"}, f"il tool restituisce {sorted(trovati)} per la cedolare secca"


def test_codice_1668_interessi_rateizzazione_presente(tabella_erel):
    """Plan case "1668": AdE 'interessi pagamento dilazionato importi rateizzabili sezione 2'."""
    tipo, descr = tabella_erel["1668"]
    assert tipo == "Erario" and "dilazionat" in _norm(descr), (tipo, descr)
    assert [r["codice"] for r in _cerca("1668")] == ["1668"], "il tool non conosce il codice 1668"


# ---------------------------------------------------------------------------
# costi_costituzione
# ---------------------------------------------------------------------------

def _costi(tipo: str) -> dict:
    import src.server  # noqa: F401
    from src.tools.diritto_societario import costi_costituzione

    fn = getattr(costi_costituzione, "fn", costi_costituzione)
    return fn(tipo_societa=tipo)


def _voce(res: dict, *parole: str) -> dict | None:
    for v in res["voci_costo"]:
        testo = (v["voce"] + " " + v["note"]).lower()
        if all(p in testo for p in parole):
            return v
    return None


@pytest.fixture(scope="module")
def pagina_tcg() -> str:
    return _page_text(ADE_TCG_PAGE)


def test_tcg_libri_sociali_importi_ade(pagina_tcg):
    """AdE: 309,87 euro fino a 516.456,90 euro di capitale, 516,46 oltre; dovuta da S.p.a., S.r.l., S.a.p.a."""
    for frase in ("309,87 euro", "516,46 euro", "516.456,90 euro", "S.p.a., S.r.l., S.a.p.a."):
        assert frase in pagina_tcg, f"scheda AdE senza '{frase}'"
    for tipo in ("srl", "spa"):  # capitale minimo sotto 516.456,90 euro
        v = _voce(_costi(tipo), "concessione governativa")
        assert v and v["min"] == v["max"] == 309.87, (tipo, v)
    for tipo in ("sas", "snc", "ditta_individuale"):  # non sono societa' di capitali
        assert _voce(_costi(tipo), "concessione governativa") is None, tipo


def test_tcg_libri_sociali_dovuta_anche_dalla_srls(pagina_tcg):
    """La s.r.l.s. e' una S.r.l. (art. 2463-bis c.c.): l'art. 3 co. 3 DL 1/2012 esenta solo bollo,
    diritti di segreteria e onorari notarili, non la tassa di concessione governativa."""
    assert "S.r.l." in pagina_tcg
    v = _voce(_costi("srls"), "concessione governativa")
    assert v is not None and v["min"] == 309.87, (
        "costi_costituzione('srls') omette la tassa di concessione governativa di 309,87 euro "
        f"(totale del tool {_costi('srls')['totale_stimato_min']}, atteso 629,87)"
    )


@pytest.fixture(scope="module")
def pagina_cciaa_societa() -> str:
    return _page_text(CCIAA_RM_SOCIETA)


def test_diritti_segreteria_e_bollo_societa_cciaa(pagina_cciaa_societa):
    """CCIAA Roma (DM MiSE 17 luglio 2012; Tariffa DPR 642/1972 art. 1 co. 1-ter): diritti 90 euro;
    bollo della domanda 65 (capitali) / 59 (persone), assorbito dal bollo MUI dell'atto notarile."""
    t = pagina_cciaa_societa
    assert "euro 90" in t and "65,00" in t and "59,00" in t, "pagina CCIAA cambiata"
    for tipo in ("srl", "spa"):
        v = _voce(_costi(tipo), "segreteria")
        assert v and v["min"] == 90.0, (tipo, v)


@pytest.mark.parametrize("tipo", ["sas", "snc"])
def test_diritti_segreteria_societa_di_persone(tipo, pagina_cciaa_societa):
    """Le societa' di persone pagano i diritti di segreteria di 90 euro per l'iscrizione."""
    assert "euro 90" in pagina_cciaa_societa
    v = _voce(_costi(tipo), "segreteria")
    assert v is not None and v["min"] == 90.0, (
        f"costi_costituzione('{tipo}') non include i diritti di segreteria di 90 euro "
        "(DM MiSE 17 luglio 2012, iscrizione societa')"
    )


# Frozen, not fetched: the page answers 403 to a self-identified client and this file does not
# disguise itself as a browser. Read on 2026-09-25 from CNM_BOLLO_MUI (massima I.10 del Consiglio
# notarile di Milano, citing Tariffa DPR 642/1972 art. 1 co. 1-bis.1): "per gli atti propri delle
# societa' (...), incluse la copia dell'atto e la domanda per il registro delle imprese euro 156,00".
BOLLO_MUI_ATTI_SOCIETARI = 156.00


def test_bollo_mui_atti_societari_156():
    """Tariffa DPR 642/1972 art. 1 co. 1-bis.1: 156 euro per gli atti propri delle societa' (copia e
    domanda al registro imprese incluse), per le societa' di persone come per quelle di capitali."""
    for tipo in ("srl", "spa", "sas", "snc"):
        v = _voce(_costi(tipo), "bolli")
        assert v and v["min"] == BOLLO_MUI_ATTI_SOCIETARI, (tipo, v)
    v = _voce(_costi("srls"), "bolli")
    assert v and v["min"] == 0.0, v  # esente (art. 3 co. 3 DL 1/2012)


def test_ditta_individuale_diritti_bollo_e_diritto_annuale_cciaa():
    """CCIAA Roma: diritti 18 euro, bollo 17,50, diritto annuale 53 (sezione speciale) / 120 (ordinaria)."""
    t = _page_text(CCIAA_RM_INDIVIDUALI)
    for frase in ("Euro 18,00", "Euro 17.50", "Euro 53,00", "Euro 120,00"):
        assert frase in t, f"pagina CCIAA senza '{frase}'"
    res = _costi("ditta_individuale")
    assert _voce(res, "segreteria")["min"] == 18.0
    assert _voce(res, "bolli")["min"] == 17.5
    # the tool uses the sezione speciale amount (53); an impresa in sezione ordinaria pays 120
    assert _voce(res, "diritto annuale")["min"] == 53.0


def test_diritto_annuale_2026_nuove_iscrizioni():
    """CCIAA Bologna, diritto annuale 2026 (riduzione 50% art. 28 DL 90/2014 + maggiorazione 20%):
    nuove iscrizioni in sezione ordinaria (s.n.c., s.a.s., societa' di capitali) 120 euro;
    imprese individuali in sezione speciale 53 euro. Senza maggiorazione: 100 e 44 euro."""
    t = _page_text(CCIAA_BO_DIRITTO_2026)
    i = t.find("NUOVA ISCRIZIONE")
    assert i >= 0, "pagina CCIAA Bologna cambiata"
    sezione = t[i:i + 2000]
    assert "€ 53,00" in sezione and "€ 120,00" in sezione and "società di capitali" in sezione, sezione[:500]
    for tipo in ("srl", "srls", "spa", "sas", "snc"):
        v = _voce(_costi(tipo), "diritto annuale")
        assert v and v["min"] == 120.0, (tipo, v)


def test_imposta_registro_misura_fissa_200():
    """Art. 26 co. 2 DL 104/2013: le imposte fisse di 168 euro sono elevate a 200 euro (Tariffa parte I
    DPR 131/1986, art. 4: atti costitutivi con conferimenti in denaro). Si applica anche alla s.r.l.s."""
    from tests.unit._norme_live import assert_parole

    assert_parole("art. 26 DL 104/2013", "elevato ad euro 200")
    for tipo in ("srl", "srls", "spa", "sas", "snc"):
        v = _voce(_costi(tipo), "registro")
        assert v and v["min"] == v["max"] == 200.0, (tipo, v)


def test_srls_esenzioni_art_3_co_3_dl_1_2012():
    from tests.unit._norme_live import assert_parole

    assert_parole(
        "art. 3 DL 1/2012",
        "sono esenti da diritto di bollo e di segreteria e non sono dovuti onorari notarili",
    )
    res = _costi("srls")
    assert _voce(res, "notarile")["min"] == 0.0
    assert _voce(res, "bolli")["min"] == 0.0
    assert _voce(res, "segreteria")["min"] == 0.0


def test_capitale_minimo_e_versamento_iniziale():
    from tests.unit._norme_live import assert_parole

    assert_parole("art. 2327 c.c.", "non inferiore a cinquantamila euro")
    assert_parole("art. 2342 c.c.", "almeno il venticinque per cento dei conferimenti in danaro")
    assert_parole("art. 2463 c.c.", "pari almeno a un euro")
    assert _costi("spa")["capitale_minimo"] == 50000.0
    assert "25%" in _costi("spa")["note"] and "2342 co. 2" in _costi("spa")["note"]
    assert _costi("srl")["capitale_minimo"] == 1.0
    assert _costi("srls")["capitale_minimo"] == 1.0


def test_riferimenti_normativi_pertinenti():
    """Il D.M. 55/2014 (parametri forensi) non regola i costi notarili; l'esenzione dal bollo della
    s.r.l.s. sta nel co. 3 dell'art. 3 DL 1/2012 (il co. 1 introduce l'art. 2463-bis c.c.)."""
    problemi = []
    if "55/2014" in _costi("srl")["riferimento_normativo"]:
        problemi.append("srl: riferimento_normativo cita il D.M. 55/2014 (parametri forensi)")
    nota = _voce(_costi("srls"), "bolli")["note"]
    if re.search(r"art\. 3 c\. 1\b", nota):
        problemi.append(f"srls, voce 'Bolli e diritti': cita l'art. 3 c. 1 DL 1/2012 invece del c. 3 ({nota!r})")
    assert not problemi, problemi


def test_tipo_non_gestito_elenca_i_tipi_ammessi():
    with pytest.raises(ValueError, match="srl, srls, spa, sas, snc, ditta_individuale"):
        _costi("sapa")

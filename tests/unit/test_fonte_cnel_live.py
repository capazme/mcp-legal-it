"""Live gate: `indennita_preavviso` against the CCNL texts deposited in the CNEL archive.

Phase 4 of the avvocatoandreani.it benchmark, strategy `fonte_ufficiale`, group `cnel`.
The benchmark site has no notice-pay calculator, so the periods the tool reads from
`src/data/preavviso_ccnl.json` are compared with the collective agreements deposited in
the CNEL national archive (Archivio nazionale dei contratti collettivi, art. 17 L. 936/1986),
and the formula with the vigente text of artt. 2118 and 2121 c.c. (Normattiva, `cite_law`).

Sources (consulted on 2026-09-25 through the archive's public search API, the one the
page https://www.cnel.it/archivio-contratti/entra-nell-archivio/contratti-collettivi-del-
settore-privato/contratti-nazionali-di-settore-vigenti-o-ultrattivi calls):

* H011 -- Testo Unico CCNL Terziario, Distribuzione e Servizi (Confcommercio), stipulated
  3 February 2026, idAccordo 242377, file 21019-1.pdf: art. 251 (termini, licenziamento),
  art. 252 (indennita' sostitutiva), art. 256 (dimissioni). Scanned PDF, no text layer:
  read with OCR and checked visually (PDF pages 159 and 161-162), values frozen below.
* C011 -- CCNL industria metalmeccanica e installazione di impianti 5 February 2021,
  idAccordo 157071, file 19906.pdf: Sez. Quarta, Titolo VIII, art. 1. The PDF has a text
  layer: this file downloads it and parses both tables (termini and indennita' in
  mensilita'). The renewal hypothesis of 22 November 2025 (Federmeccanica-Assistal, not
  yet deposited at CNEL on 2026-09-25) does not amend that article: its only mention of it
  concerns the change of contractor (read by OCR from the FIOM copy of the signed text).
* H442 -- CCNL studi e attivita' professionali (Confprofessioni) 16 February 2024,
  idAccordo 195625, file 20479.pdf: artt. 146 (termini) and 147 (indennita'). Scanned PDF:
  table read visually (PDF pages 74-75), values frozen below.

The archive check fails as soon as CNEL lists a different vigente text for one of the three
codes: re-read the notice articles and reconcile the table before touching this file.
A failing test is a genuine divergence of the tool from the source: do not soften it.

Run:
    .venv/bin/pytest tests/unit/test_fonte_cnel_live.py -m live -q -p no:cacheprovider -rfEs
"""

from __future__ import annotations

import base64
import functools
import re
import shutil
import subprocess
from decimal import ROUND_HALF_UP, Decimal

import httpx
import pytest

from tests.unit._norme_live import assert_parole

pytestmark = pytest.mark.live

CONSULTATO_IL = "2026-09-25"
CNEL_API = "https://az-apim-cne-sa-0002-lgc-we.azure-api.net/ricerca-api"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (mcp-legal-it live benchmark)",
    "Origin": "https://www.cnel.it",
    "Referer": "https://www.cnel.it/",
}

# The vigente text of each CCNL as the archive listed it on 2026-09-25.
TESTI_LETTI = {
    "H011": {"idAccordo": 242377, "dataStipula": "2026-02-03", "tool_ccnl": "commercio"},
    "C011": {"idAccordo": 157071, "dataStipula": "2021-02-05", "tool_ccnl": "metalmeccanici"},
    "H442": {"idAccordo": 195625, "dataStipula": "2024-02-16", "tool_ccnl": "studi_professionali"},
}

FASCE = ("fino_5", "5_10", "oltre_10")
# One seniority per band, on the upper edge where the CCNL puts it ("fino a cinque anni
# di servizio compiuti", "oltre i cinque anni e fino a dieci anni") plus one over ten.
ANZIANITA = {"fino_5": 5.0, "5_10": 10.0, "oltre_10": 10.5}

# --- H011, TU Terziario 3/2/2026: art. 251 and art. 256 (giorni di calendario) -----------
# Frozen by hand (OCR at 200 dpi + visual check of PDF pages 159, 161, 162) on 2026-09-25.
TERZIARIO = {
    "licenziamento": {  # art. 251
        "quadri_1": (60, 90, 120),
        "2_3": (30, 45, 60),
        "4_5": (20, 30, 45),
        "6_7": (15, 20, 20),
    },
    "dimissioni": {  # art. 256
        "quadri_1": (45, 60, 90),
        "2_3": (20, 30, 45),
        "4_5": (15, 20, 30),
        "6_7": (10, 15, 15),
    },
}

# --- H442, CCNL studi professionali 16/2/2024: art. 146 lett. A) and B) ---------------------
# Frozen by hand (visual check of PDF pages 74-75) on 2026-09-25. The CCNL rows are Quadri,
# I, II, III Super, III, IV Super, IV, V: the tool groups them as below (Quadri has the same
# periods as level I but the tool has no key for it, see the note in the result).
STUDI_PROFESSIONALI = {
    "licenziamento": {
        "1": (90, 120, 150),
        "2": (60, 90, 120),
        "3S_3": (30, 40, 50),
        "4S_4": (20, 30, 40),
        "5": (15, 20, 25),
    },
    "dimissioni": {
        "1": (75, 105, 135),
        "2": (60, 90, 120),
        "3S_3": (28, 35, 42),
        "4S_4": (15, 25, 30),
        "5": (10, 15, 25),
    },
}


def _tool(**kwargs) -> dict:
    """The tool through its full stack (MCP object and `@sourced`), as a client calls it."""
    import src.server  # noqa: F401  (registers every tool module first: avoids a circular import)
    from src.tools.diritto_lavoro import indennita_preavviso

    fn = getattr(indennita_preavviso, "fn", indennita_preavviso)
    return fn(**kwargs)


def _cent(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _retribuzione_periodo(mensile: float, giorni: int) -> float:
    """Retribution for a period in calendar days, a month being 30 days (art. 2118 co. 2 c.c.)."""
    return _cent(Decimal(str(mensile)) * giorni / Decimal(30))


# --- CNEL archive -----------------------------------------------------------------------------


@functools.lru_cache(maxsize=None)
def _cnel_ccnl(codice: str) -> dict:
    """The CCNL record of the public search (same payload the CNEL page receives)."""
    body = {
        "stato": ["Vigente"],
        "contrattazione": ["NAZIONALE_SETTORE_PRIVATO"],
        "settorePubblico": False,
        "codice": codice,
        "sortBy": "codice",
        "sortDesc": False,
        "pageNumber": 0,
        "pageSize": 10,
        "nuovaOrganizzazioneCCNL": "CCNL_SETTORE_VIGENTI_O_ULTRATTATTIVI",
    }
    r = httpx.post(f"{CNEL_API}/ricerca/pubblica/ccnl", json=body, headers=_HEADERS, timeout=60)
    r.raise_for_status()
    contenuto = r.json()["pagedList"]["content"]
    assert len(contenuto) == 1, f"{codice}: la ricerca CNEL non restituisce un solo CCNL: {contenuto}"
    return contenuto[0]


@functools.lru_cache(maxsize=None)
def _cnel_accordi_vigenti(codice: str) -> dict[int, dict]:
    r = httpx.get(
        f"{CNEL_API}/ricerca/pubblica/accordi/cerca/accordi/codice-ccnl/{codice}",
        params={"vigenti": "true", "pageNumber": 0, "pageSize": 50},
        headers=_HEADERS,
        timeout=60,
    )
    r.raise_for_status()
    return {a["idAccordo"]: a for a in r.json()["pagedList"]["content"]}


@pytest.mark.parametrize("codice", sorted(TESTI_LETTI))
def test_cnel_archivio_elenca_ancora_il_testo_letto(codice):
    """The archive's vigente text for the code is still the one this file was built on."""
    atteso = TESTI_LETTI[codice]
    ccnl = _cnel_ccnl(codice)
    assert ccnl["codice"] == codice and ccnl["stato"] == "VIGENTE", ccnl
    vigenti = [a["idAllegato"] for a in ccnl["accordiVigenti"]]
    assert vigenti == [atteso["idAccordo"]], (
        f"{codice}: il CNEL elenca come testo vigente {ccnl['accordiVigenti']} invece dell'accordo "
        f"{atteso['idAccordo']} letto il {CONSULTATO_IL}: rileggere gli articoli sul preavviso e "
        "riconciliare src/data/preavviso_ccnl.json"
    )
    accordo = _cnel_accordi_vigenti(codice)[atteso["idAccordo"]]
    assert accordo["dataStipula"] == atteso["dataStipula"], accordo


# --- C011 metalmeccanici: parsed from the deposited PDF -----------------------------------------

_RIGHE = {"fino a 5 anni": "fino_5", "oltre 5 fino a 10": "5_10", "oltre i 10 anni": "oltre_10"}


def _durata_in_giorni(cella: str) -> int:
    """'2 mesi e 15 giorni' -> 75: months of 30 days, as the indemnity table itself converts."""
    mesi = re.search(r"(\d+)\s*mes[ei]", cella)
    giorni = re.search(r"(\d+)\s*giorni", cella)
    assert mesi or giorni, cella
    return (int(mesi.group(1)) * 30 if mesi else 0) + (int(giorni.group(1)) if giorni else 0)


def _mensilita(cella: str) -> Decimal:
    m = re.search(r"(\d+(?:,\d+)?)\s*mensilit", cella)
    assert m, cella
    return Decimal(m.group(1).replace(",", "."))


@pytest.fixture(scope="module")
def metalmeccanici_art1(tmp_path_factory) -> dict:
    """Sez. Quarta, Titolo VIII, art. 1 of the C011 text deposited at CNEL, parsed."""
    if shutil.which("pdftotext") is None:
        pytest.skip("pdftotext (poppler) non installato: serve per leggere il PDF depositato al CNEL")
    ident = TESTI_LETTI["C011"]["idAccordo"]
    r = httpx.get(
        f"{CNEL_API}/ricerca/pubblica/accordi/scarica/accordi/{ident}", headers=_HEADERS, timeout=180
    )
    r.raise_for_status()
    modello = r.json()["model"]
    assert modello["mimetype"] == "application/pdf", modello.get("mimetype")
    cartella = tmp_path_factory.mktemp("cnel_c011")
    pdf = cartella / modello["simpleFileName"]
    pdf.write_bytes(base64.b64decode(modello["fileContent"]))
    testo = subprocess.run(
        ["pdftotext", "-layout", str(pdf), "-"], capture_output=True, text=True, check=True
    ).stdout

    inizio = testo.find("Preavviso di licenziamento e di dimissioni")
    assert inizio >= 0, "art. 1 (Preavviso di licenziamento e di dimissioni) non trovato nel PDF CNEL"
    fine = testo.find("Durante il compimento del periodo di preavviso", inizio)
    assert fine > inizio
    articolo = testo[inizio:fine]

    righe = [re.split(r"\s{2,}", r.strip()) for r in articolo.splitlines() if r.strip()]
    intestazioni = [r for r in righe if r[0].lower().startswith("anni di servizio")]
    assert len(intestazioni) == 2, intestazioni
    # "Livelli B2, B3 e A1" -> "A1_B2_B3": the tool's key is the sorted list of levels.
    colonne = ["_".join(sorted(re.findall(r"[A-D]\d", c))) for c in intestazioni[0][1:]]
    assert colonne == ["A1_B2_B3", "B1_C2_C3", "C1_D1_D2"], colonne

    fasce = [r for r in righe if r[0].lower() in _RIGHE]
    assert len(fasce) == 6 and all(len(r) == 4 for r in fasce), fasce
    termini: dict[str, dict[str, int]] = {c: {} for c in colonne}
    indennita: dict[str, dict[str, Decimal]] = {c: {} for c in colonne}
    for riga in fasce[:3]:
        for colonna, cella in zip(colonne, riga[1:]):
            termini[colonna][_RIGHE[riga[0].lower()]] = _durata_in_giorni(cella)
    for riga in fasce[3:]:
        for colonna, cella in zip(colonne, riga[1:]):
            indennita[colonna][_RIGHE[riga[0].lower()]] = _mensilita(cella)
    return {"testo": re.sub(r"\s+", " ", articolo).lower(), "termini": termini, "indennita": indennita}


def test_metalmeccanici_art1_stesso_termine_per_entrambe_le_parti(metalmeccanici_art1):
    """The term binds either party, so the tool's dimissioni table must equal licenziamento."""
    testo = metalmeccanici_art1["testo"]
    assert "da nessuna delle due parti senza un preavviso" in testo
    assert "indennità pari all’importo della retribuzione" in testo or (
        "indennità pari all'importo della retribuzione" in testo
    )


@pytest.mark.parametrize("tipo", ("licenziamento", "dimissioni"))
@pytest.mark.parametrize("livello", ("A1_B2_B3", "B1_C2_C3", "C1_D1_D2"))
@pytest.mark.parametrize("fascia", FASCE)
def test_metalmeccanici_termini_come_ccnl(metalmeccanici_art1, tipo, livello, fascia):
    """Sez. IV Tit. VIII art. 1 CCNL 5/2/2021 (CNEL C011): the notice period of each cell."""
    atteso = metalmeccanici_art1["termini"][livello][fascia]
    r = _tool(ccnl="metalmeccanici", livello=livello, anzianita_anni=ANZIANITA[fascia],
              retribuzione_mensile=2200, tipo=tipo)
    assert r["fascia_anzianita"] == fascia
    assert r["giorni_preavviso"] == atteso, (livello, fascia, tipo, r["giorni_preavviso"], atteso)


@pytest.mark.parametrize("livello", ("A1_B2_B3", "B1_C2_C3", "C1_D1_D2"))
@pytest.mark.parametrize("fascia", FASCE)
def test_metalmeccanici_indennita_in_mensilita_come_ccnl(metalmeccanici_art1, livello, fascia):
    """Art. 1, second table: the CCNL fixes the indemnity in mensilita' (0,33 and 0,67 included).

    The tool converts the term to days and divides the monthly pay by 30, so for levels
    D1, D2 and C1 it pays 10/30 and 20/30 of a month where the contract writes 0,33 and 0,67.
    """
    mensile = 2200
    mensilita = metalmeccanici_art1["indennita"][livello][fascia]
    atteso = _cent(Decimal(mensile) * mensilita)
    r = _tool(ccnl="metalmeccanici", livello=livello, anzianita_anni=ANZIANITA[fascia],
              retribuzione_mensile=mensile)
    assert r["importo"] == pytest.approx(atteso, abs=0.01), (
        f"{livello} {fascia}: tool {r['importo']} (={r['giorni_preavviso']} giorni / 30), "
        f"CCNL {mensilita} mensilità = {atteso}"
    )


# --- H011 terziario and H442 studi professionali: frozen tables -------------------------------


def _celle(tabella: dict) -> list[tuple[str, str, str, int]]:
    return [
        (tipo, livello, fascia, giorni)
        for tipo, livelli in tabella.items()
        for livello, valori in livelli.items()
        for fascia, giorni in zip(FASCE, valori)
    ]


@pytest.mark.parametrize("tipo,livello,fascia,giorni", _celle(TERZIARIO))
def test_terziario_termini_come_ccnl(tipo, livello, fascia, giorni):
    """TU CCNL Terziario 3/2/2026 (CNEL H011) artt. 251/256, giorni di calendario; art. 252."""
    mensile = 1800  # 60 euro per 30 days: no rounding between the two sides
    r = _tool(ccnl="commercio", livello=livello, anzianita_anni=ANZIANITA[fascia],
              retribuzione_mensile=mensile, tipo=tipo)
    assert r["fascia_anzianita"] == fascia
    assert r["giorni_preavviso"] == giorni, (tipo, livello, fascia, r["giorni_preavviso"], giorni)
    assert r["importo"] == pytest.approx(_retribuzione_periodo(mensile, giorni), abs=0.01)


@pytest.mark.parametrize("tipo,livello,fascia,giorni", _celle(STUDI_PROFESSIONALI))
def test_studi_professionali_termini_come_ccnl(tipo, livello, fascia, giorni):
    """CCNL studi professionali 16/2/2024 (CNEL H442) art. 146, giorni di calendario; art. 147."""
    mensile = 3000  # 100 euro per 30 days: no rounding between the two sides
    r = _tool(ccnl="studi_professionali", livello=livello, anzianita_anni=ANZIANITA[fascia],
              retribuzione_mensile=mensile, tipo=tipo)
    assert r["fascia_anzianita"] == fascia
    assert r["giorni_preavviso"] == giorni, (tipo, livello, fascia, r["giorni_preavviso"], giorni)
    assert r["importo"] == pytest.approx(_retribuzione_periodo(mensile, giorni), abs=0.01)


def test_riferimento_articolo_terziario_come_testo_unico_2026():
    """The TU 3/2/2026 puts the notice in artt. 251-252 (licenziamento) and 256 (dimissioni).

    Art. 254 of that text is "Decesso del dipendente": citing it as the source of the
    periods sends the reader to the wrong article.
    """
    r = _tool(ccnl="commercio", livello="2_3", anzianita_anni=3, retribuzione_mensile=1800)
    riferimento = r["riferimento_normativo"]
    assert "251" in riferimento and "256" in riferimento, riferimento


# --- The benchmark plan's cases -------------------------------------------------------------

CASI_PIANO = [
    # (input, giorni, importo, fonte)
    (dict(ccnl="commercio", livello="2_3", anzianita_anni=5.0, retribuzione_mensile=1800),
     30, 1800.00, "art. 251 lett. a TU Terziario: fino a cinque anni di servizio compiuti"),
    (dict(ccnl="commercio", livello="2_3", anzianita_anni=5.5, retribuzione_mensile=1800),
     45, 2700.00, "art. 251 lett. b TU Terziario"),
    (dict(ccnl="metalmeccanici", livello="B1_C2_C3", anzianita_anni=10.0, retribuzione_mensile=2200),
     60, 4400.00, "art. 1 Sez. IV Tit. VIII: oltre 5 fino a 10 -> 2 mesi, 2 mensilità"),
    (dict(ccnl="metalmeccanici", livello="B1_C2_C3", anzianita_anni=10.5, retribuzione_mensile=2200),
     75, 5500.00, "art. 1 Sez. IV Tit. VIII: oltre i 10 anni -> 2 mesi e 15 giorni, 2,5 mensilità"),
    (dict(ccnl="studi_professionali", livello="1", anzianita_anni=11, retribuzione_mensile=3000,
          tipo="dimissioni"),
     135, 13500.00, "art. 146 lett. B CCNL studi professionali: livello I oltre i 10 anni"),
]


@pytest.mark.parametrize("kwargs,giorni,importo,fonte", CASI_PIANO)
def test_casi_del_piano(kwargs, giorni, importo, fonte):
    r = _tool(**kwargs)
    assert r["giorni_preavviso"] == giorni, fonte
    assert r["importo"] == pytest.approx(importo, abs=0.01), fonte
    assert r["dati_applicati"], "la tabella CCNL è stata letta: il suo vintage deve comparire"


def test_giorni_forniti_dal_chiamante_non_leggono_la_tabella():
    """Plan case 6: CCNL not tabulated, 45 days supplied -> 2.400/30 x 45 (art. 2118 co. 2 c.c.)."""
    r = _tool(ccnl="edilizia", livello="operaio", anzianita_anni=3, retribuzione_mensile=2400,
              giorni_preavviso=45)
    assert r["importo"] == pytest.approx(3600.00, abs=0.01)
    assert r["giorni_preavviso_fonte"] == "forniti dal chiamante"
    assert r["dati_applicati"] == []
    assert r["dati_forniti_dal_chiamante"] == {"parametro": "giorni_preavviso",
                                               "al_posto_di": ["preavviso_ccnl"]}


def test_importo_senza_doppio_arrotondamento():
    """150 giorni di calendario (art. 146 CCNL studi professionali, livello I oltre 10 anni)
    are five months: on 1.000 euro the indemnity is 5.000,00.

    The tool rounds the daily rate to four decimals (33,3333) before multiplying, and the
    product 4.999,995 rounds down to 4.999,99. Cent tolerance kept strict on purpose: the
    exact figure is known and the error is the tool's arithmetic, not the source's.
    """
    r = _tool(ccnl="studi_professionali", livello="1", anzianita_anni=11, retribuzione_mensile=1000)
    assert r["giorni_preavviso"] == 150
    assert r["importo"] == pytest.approx(_retribuzione_periodo(1000, 150), abs=0.005), r["importo"]


# --- Artt. 2118 and 2121 c.c. (Normattiva) ----------------------------------------------------


def test_art_2118_cc_indennita_pari_alla_retribuzione_del_periodo():
    assert_parole(
        "art. 2118 c.c.",
        "dando il preavviso nel termine e nei modi stabiliti",
        "un'indennita' equivalente all'importo della retribuzione che sarebbe spettata per il periodo di preavviso"
        "|un'indennità equivalente all'importo della retribuzione che sarebbe spettata per il periodo di preavviso",
    )


def test_art_2121_cc_base_comprende_ogni_compenso_continuativo():
    """The base the caller must pass as `retribuzione_mensile` (the CCNL add 13a/14a ratei)."""
    assert_parole(
        "art. 2121 c.c.",
        "ogni altro compenso di carattere continuativo",
        "con esclusione di quanto e' corrisposto a titolo di rimborso spese"
        "|con esclusione di quanto è corrisposto a titolo di rimborso spese",
    )

"""Live gate (strategy `strutturale`): the document generators of `atti_giudiziari`.

Phase 4 of the avvocatoandreani.it benchmark, strategy `strutturale`, group `atti_giudiziari`
(13 tools: attestazione_conformita, atto_di_precetto, decreto_ingiuntivo, dichiarazione_553_cpc,
fascicolo_di_parte, indice_documenti, istanza_visibilita_fascicolo, nota_precisazione_credito,
note_trattazione_scritta, procura_alle_liti, relata_notifica_pec, sfratto_morosita,
testimonianza_scritta). The site has redattori for these acts but no numeric result to compare,
so each generator is checked against the vigente norm instead:

1. the document is generated with the cases of docs/benchmark/piano-benchmark-andreani.json;
2. its structure is checked against the elements the vigente norm requires, read live from
   Normattiva / EUR-Lex through `cite_law` (the words each check relies on are asserted on the
   vigente text first, so a change of the norm fails loudly instead of passing silently);
3. every normative reference (and decision) cited in the generated text and in
   `riferimento_normativo` is extracted and passed to `verifica_citazioni`; on top of it the
   articles Normattiva marks "ARTICOLO ABROGATO" are rejected, because `verifica_citazioni`
   answers "verificata" for an abrogated article (it only checks that the source exists).

Main norms read (Normattiva, testo vigente at the date of the run): artt. 7, 83, 84, 127-ter,
147, 165, 251, 257-bis, 413, 479, 480, 543, 545-548, 553, 615, 617, 633, 636, 637, 641, 642,
644, 658, 660, 663, 664 c.p.c.; artt. 74, 76, 103-bis, 169-septies, 196-octies..196-undecies
disp. att. c.p.c.; art. 63 disp. att. c.c.; artt. 1 and 3-bis L. 53/1994; artt. 9, 13, 14
DPR 115/2002; art. 55 L. 392/1978; artt. 4 and 17 D.Lgs. 231/2007; artt. 6 and 9 Reg. (UE)
2016/679; artt. 16-bis and 16-undecies DL 179/2012 (abrogated by D.Lgs. 149/2022).

A failing test here is a genuine divergence of the tool from the norm (or a change of the
norm): do not soften it. It needs the network and is skipped by default:

    .venv/bin/pytest tests/unit/test_strutturale_atti_giudiziari_live.py -m live -q -p no:cacheprovider -rfEs
"""

from __future__ import annotations

import asyncio
import functools
import inspect
import json
import re

import pytest

from tests.unit._norme_live import cite_law_json, contiene, normalizza
from tests.unit._norme_live import testo_vigente as _testo_vigente  # alias: pytest would collect "test*"

pytestmark = pytest.mark.live


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _tool(name: str):
    import src.server  # noqa: F401  (registers every tool module first: avoids a circular import)
    from src.tools import atti_giudiziari

    obj = getattr(atti_giudiziari, name)
    return getattr(obj, "fn", obj)


def _genera(name: str, caso: dict) -> dict:
    return _tool(name)(**caso)


def _testo(out: dict) -> str:
    return out.get("testo") or out.get("bozza_ricorso") or ""


def _tutto(out: dict) -> str:
    """Everything the tool tells the user: the act, its reference field and the summaries."""
    extra = {k: v for k, v in out.items() if k not in ("testo", "bozza_ricorso")}
    return _testo(out) + "\n" + json.dumps(extra, ensure_ascii=False)


@functools.lru_cache(maxsize=None)
def _vigente(reference: str) -> str:
    """Normalised vigente text (cached: several tests read the same article)."""
    return _testo_vigente(reference)


def _norma(reference: str, *frasi: str) -> str:
    """Assert the vigente text of `reference` contains every phrase; return the text."""
    testo = _vigente(reference)
    missing = contiene(testo, *frasi)
    assert not missing, f"{reference}: il testo vigente non contiene {missing} (norma cambiata?)"
    return testo


def _normattiva_oggi(urn: str) -> str:
    """Normalised page of a Normattiva URN in the version in force today (`!vig=`).

    Used where `cite_law` resolves to the wrong component of the act (art. 4 D.Lgs. 231/2007:
    the resolver serves the abrogated 'Allegato tecnico - art. 4' instead of the body article).
    """
    import httpx
    from bs4 import BeautifulSoup

    from src.lib import _clock
    from src.lib.visualex.scraper import _HEADERS

    url = f"https://www.normattiva.it/uri-res/N2Ls?{urn}!vig={_clock.today().isoformat()}"
    with httpx.Client(headers=_HEADERS, timeout=40, follow_redirects=True) as client:
        resp = client.get(url)
        resp.raise_for_status()
    pagina = BeautifulSoup(resp.text, "lxml").get_text(" ", strip=True)
    return normalizza(pagina.replace("((", "").replace("))", ""))


# --- extraction of the references cited in a generated act -----------------

_ATTI = [
    (r"disp\.\s*att\.\s*c\.p\.c\.|delle\s+disposizioni\s+di\s+attuazione\s+del\s+codice\s+di\s+procedura\s+civile",
     "disp. att. c.p.c."),
    (r"disp\.\s*att\.\s*c\.c\.", "disp. att. c.c."),
    (r"c\.p\.c\.", "c.p.c."),
    (r"c\.c\.", "c.c."),
    (r"(?:L\.|legge)\s*(?:n\.\s*)?(\d+)/(\d{4})", "L. {0}/{1}"),
    (r"(?:DL|D\.L\.)\s*(\d+)/(\d{4})", "DL {0}/{1}"),
    (r"D\.\s?Lgs\.\s*(\d+)/(\d{4})", "D.Lgs. {0}/{1}"),
    (r"DPR\s*(\d+)/(\d{4})", "DPR {0}/{1}"),
    (r"Reg\.\s*UE\s*2016/679", "Reg. UE 2016/679"),
]
_NUM = r"\d+(?:-(?:bis|ter|quater|quinquies|sexies|septies|octies|novies|decies|undecies|duodecies))?"
_ITEM = rf"{_NUM}(?:\s*(?:co\.|comma)\s*\d+(?:-[a-z]+)?)?"
_RIF = re.compile(
    rf"\bart(?:t)?\.\s*(?P<items>{_ITEM}(?:\s*(?:,|e|-)\s*{_ITEM})*)(?:\s+e\s+ss\.)?"
    rf"\s*(?:,\s*)?(?:del(?:la|le|lo|l')?\s*)?(?P<atto>" + "|".join(p for p, _ in _ATTI) + ")",
    re.IGNORECASE,
)
_CORTE_COST = re.compile(r"Corte\s+cost\.\s*n\.\s*(\d+)/(\d{4})", re.IGNORECASE)


def estrai_riferimenti(testo: str) -> list[str]:
    """Normative references cited in a text, one article each ("art. 3-bis co. 3 L. 53/1994").

    Lists ("artt. 196-octies, 196-decies e 196-undecies") are split, ranges ("artt. 633-656")
    are reduced to their endpoints, "co. N-bis" suffixes are dropped (verifica_citazioni checks
    plain comma numbers only).
    """
    refs: list[str] = []
    for m in _RIF.finditer(testo):
        atto = None
        for pat, fmt in _ATTI:
            mm = re.fullmatch(pat, m.group("atto"), re.IGNORECASE)
            if mm:
                atto = fmt.format(*mm.groups())
                break
        articoli: list[str] = []
        for parte in re.split(r"\s*(?:,|\be\b)\s*", m.group("items")):
            parte = parte.strip()
            rng = re.fullmatch(r"(\d+)-(\d+)", parte)
            if rng:
                articoli += [rng.group(1), rng.group(2)]
                continue
            art = re.match(_NUM, parte).group(0)
            co = re.search(r"(?:co\.|comma)\s*(\d+)(-[a-z]+)?", parte)
            articoli.append(f"{art} co. {co.group(1)}" if co and not co.group(2) else art)
        for a in articoli:
            ref = f"art. {a} {atto}"
            if ref not in refs:
                refs.append(ref)
    return refs


def estrai_sentenze(testo: str) -> list[str]:
    return sorted({f"Corte cost. n. {n}/{a}" for n, a in _CORTE_COST.findall(testo)})


def _verifica_citazioni(refs: list[str]) -> dict[str, dict]:
    """Run `verifica_citazioni` (json) in chunks of 20 (its per-call limit)."""
    import src.server  # noqa: F401
    from src.tools.legal_citations import verifica_citazioni

    fn = getattr(verifica_citazioni, "fn", verifica_citazioni)
    esiti: dict[str, dict] = {}
    for i in range(0, len(refs), 20):
        blocco = refs[i:i + 20]
        data = json.loads(asyncio.run(fn(citazioni="\n".join(blocco), formato="json")))
        assert data["errore"] is None, data
        for c in data["citazioni"]:
            esiti[c["citazione"]] = c
    return esiti


@functools.lru_cache(maxsize=None)
def _abrogato(ref: str) -> bool:
    """True when Normattiva serves the article as "ARTICOLO ABROGATO".

    An "Allegato tecnico" served in place of a body article is a resolver artefact (art. 4
    D.Lgs. 231/2007): it is not taken as proof of abrogation and is judged by a dedicated test.
    """
    testo = normalizza(cite_law_json(ref).get("testo") or "")
    if "allegato tecnico" in testo[:200]:
        return False
    return "articolo abrogato" in testo[:400]


# ---------------------------------------------------------------------------
# Cases (docs/benchmark/piano-benchmark-andreani.json, plus a few boundary cases)
# ---------------------------------------------------------------------------

_ROSSI = {"avvocato": "Mario Rossi"}
_PROCURA = {"parte": "Giulia Verdi", "avvocato": "Mario Rossi", "cf_avvocato": "RSSMRA80A01F205X",
            "foro": "Milano"}
_DI = {"creditore": "Alfa S.r.l.", "debitore": "Beta S.r.l.", "tipo_credito": "ordinario",
       "provvisoria_esecuzione": False}
_PRECETTO = {"creditore": "Alfa S.r.l.", "debitore": "Beta S.r.l.",
             "titolo_esecutivo": "decreto ingiuntivo n. 321/2026 del Tribunale di Milano, dichiarato esecutivo"}
_SFRATTO = {"locatore": "Mario Rossi", "conduttore": "Luca Bianchi",
            "immobile": "Milano, via Roma 1, foglio 10 mappale 20 sub 3", "canone_mensile": 750,
            "data_contratto": "2022-03-01"}
_TERZO = {"debitore": "Luca Bianchi", "procedura": "R.G.E. 456/2026"}
_CAPITOLI = ["Vero che il 10/01/2026 lei era presente presso il cantiere di via Roma 1 a Milano",
             "Vero che in quella occasione il sig. Bianchi consegnò le chiavi al sig. Rossi"]

CASI: dict[str, list[dict]] = {
    "attestazione_conformita": [
        {**_ROSSI, "tipo_documento": "sentenza n. 1234/2026", "estremi_originale": "R.G. 5678/2025, pagg. 1-12",
         "modalita": "estratto"},
        {**_ROSSI, "tipo_documento": "contratto di locazione",
         "estremi_originale": "originale cartaceo del 01/02/2020", "modalita": "copia_informatica"},
        {**_ROSSI, "tipo_documento": "decreto ingiuntivo n. 321/2026", "estremi_originale": "R.G. 999/2026",
         "modalita": "duplicato"},
    ],
    "atto_di_precetto": [
        {**_PRECETTO, "importo_capitale": 10000, "interessi": 350.25, "spese": 1200},
        {**_PRECETTO, "importo_capitale": 2500, "interessi": 0, "spese": 0},
    ],
    "decreto_ingiuntivo": [
        {**_DI, "importo": 10000},
        {**_DI, "importo": 10000.01},
        {**_DI, "creditore": "Mario Rossi", "importo": 8000, "tipo_credito": "retribuzioni"},
        {**_DI, "creditore": "Avv. Mario Rossi", "importo": 3000, "tipo_credito": "professionale",
         "provvisoria_esecuzione": True},
        {**_DI, "creditore": "Condominio Via Roma 1 Milano", "debitore": "Luca Bianchi", "importo": 12000,
         "tipo_credito": "condominiale", "provvisoria_esecuzione": True},
        {**_DI, "importo": 4000, "tipo_credito": "cambiale", "provvisoria_esecuzione": True},
    ],
    "dichiarazione_553_cpc": [
        {**_TERZO, "terzo_pignorato": "Banca Gamma S.p.A.", "tipo_rapporto": "conto_corrente"},
        {**_TERZO, "terzo_pignorato": "Delta S.r.l.", "tipo_rapporto": "stipendio"},
        {**_TERZO, "terzo_pignorato": "Epsilon S.r.l.", "tipo_rapporto": "altro"},
    ],
    "fascicolo_di_parte": [
        {**_ROSSI, "parte": "Alfa S.r.l.", "controparte": "Beta S.p.A.", "tribunale": "Tribunale di Milano",
         "rg_numero": "12345/2026"},
        {**_ROSSI, "parte": "Alfa S.r.l.", "controparte": "Beta S.p.A.", "tribunale": "Tribunale di Roma",
         "rg_numero": None},
    ],
    "indice_documenti": [
        {"documenti": [{"numero": 1, "descrizione": "Contratto di fornitura", "pagine": 12},
                       {"numero": 2, "descrizione": "Fatture insolute", "pagine": 5},
                       {"numero": 3, "descrizione": "Diffida", "pagine": 2}]},
        {"documenti": []},
    ],
    "istanza_visibilita_fascicolo": [
        {**_ROSSI, "parte": "Beta S.p.A.", "tribunale": "Tribunale di Milano, Sezione Prima Civile",
         "rg_numero": "12345/2026", "motivo": "costituzione"},
        {**_ROSSI, "parte": "Beta S.p.A.", "tribunale": "Tribunale di Milano", "rg_numero": "12345/2026",
         "motivo": "intervento"},
        {**_ROSSI, "parte": "Beta S.p.A.", "tribunale": "Tribunale di Milano", "rg_numero": "12345/2026",
         "motivo": "consultazione"},
    ],
    "nota_precisazione_credito": [
        {"creditore": "Alfa S.r.l.", "debitore": "Beta S.r.l.", "procedura_esecutiva": "R.G.E. 123/2026",
         "capitale": 5000, "interessi": 125.5, "spese_legali": 800, "spese_esecuzione": 150.75},
    ],
    "note_trattazione_scritta": [
        {**_ROSSI, "parte": "Alfa S.r.l.", "tribunale": "Tribunale di Milano", "rg_numero": "12345/2025",
         "giudice": "dott.ssa Laura Bianchi",
         "conclusioni": "Si insiste per l'ammissione delle prove orali dedotte nella memoria ex art. 171-ter n. 2 c.p.c."},
    ],
    "procura_alle_liti": [
        {**_PROCURA, "oggetto_causa": "risarcimento danni da inadempimento contrattuale", "tipo": "generale"},
        {**_PROCURA, "oggetto_causa": "appello avverso la sentenza n. 100/2026 del Tribunale di Milano",
         "tipo": "appello"},
        {**_PROCURA, "oggetto_causa": "opposizione a decreto ingiuntivo n. 321/2026", "tipo": "speciale"},
    ],
    "relata_notifica_pec": [
        {**_ROSSI, "destinatario": "Beta S.p.A.", "pec_destinatario": "beta@pec.it",
         "atto_notificato": "atto di citazione", "data_invio": "2026-10-05"},
    ],
    "sfratto_morosita": [
        {**_SFRATTO, "mensilita_insolute": 4},
    ],
    "testimonianza_scritta": [
        {"teste": "Anna Neri", "capitoli_prova": _CAPITOLI},
    ],
}


# ---------------------------------------------------------------------------
# 1. Every reference cited by every generator exists and is not abrogated
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("tool", sorted(CASI))
def test_citazioni_esistenti_e_non_abrogate(tool):
    """verifica_citazioni on everything the generated acts cite, plus the abrogation check."""
    refs: list[str] = []
    sentenze: list[str] = []
    for caso in CASI[tool]:
        out = _genera(tool, caso)
        testo = _tutto(out)
        refs += [r for r in estrai_riferimenti(testo) if r not in refs]
        sentenze += [s for s in estrai_sentenze(testo) if s not in sentenze]
    if not refs and not sentenze:
        pytest.skip(f"{tool}: nessun riferimento ad articolo nel testo prodotto (verificabile solo a livello di atto)")

    esiti = _verifica_citazioni(refs + sentenze)
    problemi = []
    for ref in refs:
        esito = esiti.get(ref, {})
        if esito.get("verdetto") != "verificata":
            problemi.append(f"{ref}: {esito.get('verdetto')} ({esito.get('nota')})")
        elif _abrogato(ref):
            problemi.append(f"{ref}: ARTICOLO ABROGATO su Normattiva (verifica_citazioni lo dà 'verificata')")
    for sent in sentenze:
        # verifica_citazioni resolves decisions on Italgiure (Cassazione, 2020+ only): a Corte
        # costituzionale decision comes back "non verificabile". It is accepted when the vigente
        # text of an article cited in the same act records it in its notes.
        num, anno = _CORTE_COST.search(sent).groups()
        annotata = any(
            f"n. {num}" in _vigente(r) and anno in _vigente(r) for r in refs if not _abrogato(r)
        )
        if not annotata:
            problemi.append(f"{sent}: {esiti.get(sent, {}).get('verdetto')} e non annotata nelle norme citate")
    assert not problemi, f"{tool}: riferimenti non validi:\n" + "\n".join(problemi)


# ---------------------------------------------------------------------------
# 2. attestazione_conformita — artt. 196-octies..196-undecies disp. att. c.p.c.
# ---------------------------------------------------------------------------


def test_attestazione_estratto_e_duplicato_art_196_octies():
    """Copies and duplicates extracted from the fascicolo informatico: art. 196-octies co. 2."""
    _norma("art. 196-octies disp. att. c.p.c.",
           "possono estrarre con modalita' telematiche duplicati, copie analogiche o informatiche",
           "attestare la conformita' delle copie estratte ai corrispondenti atti contenuti nel fascicolo informatico")
    _norma("art. 196-undecies disp. att. c.p.c.",
           "l'attestazione di conformita' di una copia informatica e' apposta nel medesimo documento informatico")
    for caso in (CASI["attestazione_conformita"][0], CASI["attestazione_conformita"][2]):
        testo = normalizza(_testo(_genera("attestazione_conformita", caso)))
        assert "art. 196-octies disp. att. c.p.c." in testo, testo
        assert "196-undecies" in testo, testo
        assert "fascicolo informatico" in testo, testo


def test_attestazione_copia_informatica_di_atto_analogico_art_196_novies():
    """The copy of an analog act DEPOSITED by the lawyer is art. 196-novies, not 196-decies.

    Art. 196-decies governs the copies transmitted "all'ufficiale giudiziario"; the tool
    declares itself a model "per il deposito telematico PCT".
    """
    _norma("art. 196-novies disp. att. c.p.c.",
           "quando depositano con modalita' telematiche la copia informatica",
           "formato su supporto analogico e detenuto in originale o in copia conforme")
    _norma("art. 196-decies disp. att. c.p.c.",
           "copie trasmesse con modalita' telematiche all'ufficiale giudiziario")
    out = _genera("attestazione_conformita", CASI["attestazione_conformita"][1])
    testo = normalizza(_testo(out))
    assert "originale analogico" in testo
    assert "196-novies" in testo, (
        "copia informatica di atto analogico depositata: il tool cita l'art. 196-decies "
        "(copie trasmesse all'ufficiale giudiziario) invece dell'art. 196-novies disp. att. c.p.c."
    )


# ---------------------------------------------------------------------------
# 3. atto_di_precetto — artt. 475, 479, 480, 615, 617 c.p.c.
# ---------------------------------------------------------------------------


def test_precetto_totali():
    a, b = (_genera("atto_di_precetto", c) for c in CASI["atto_di_precetto"])
    assert a["totale_intimato"] == pytest.approx(11550.25, abs=0.01)
    assert b["totale_intimato"] == pytest.approx(2500.00, abs=0.01)
    assert "11,550.25" in a["testo"] or "11.550,25" in a["testo"]


def test_precetto_art_480_co1_e_opposizioni():
    """Ten days and the enforcement warning (art. 480 co. 1); 617 (venti giorni) vs 615."""
    _norma("art. 480 c.p.c.",
           "entro un termine non minore di dieci giorni",
           "con l'avvertimento che, in mancanza, si procedera' a esecuzione forzata")
    _norma("art. 617 c.p.c.", "nel termine perentorio di venti giorni dalla notificazione del titolo esecutivo o del precetto")
    _norma("art. 475 c.p.c.", "in copia attestata conforme all'originale o in duplicato informatico")
    for caso in CASI["atto_di_precetto"]:
        testo = normalizza(_testo(_genera("atto_di_precetto", caso)))
        assert not contiene(testo, "entro il termine di dieci giorni", "si procederà ad esecuzione forzata",
                            "venti giorni", "art. 617 c.p.c.", "art. 615 c.p.c.")
        assert "forma esecutiva" not in testo and "formula esecutiva" not in testo  # art. 475 riformato


def test_precetto_art_480_co2_data_notifica_titolo_e_avvertimento_sovraindebitamento():
    """Art. 480 co. 2: date of notification of the title (a pena di nullita') and the full warning."""
    _norma("art. 480 c.p.c.",
           "a pena di nullita' l'indicazione delle parti, della data di notificazione del titolo esecutivo",
           "con l'ausilio di un organismo di composizione della crisi o di un professionista nominato dal giudice")
    testo = normalizza(_testo(_genera("atto_di_precetto", CASI["atto_di_precetto"][0])))
    mancanti = []
    if not re.search(r"notificat\w*\s+(?:in data|il)\s", testo):
        mancanti.append("data di notificazione del titolo esecutivo (a pena di nullita', art. 480 co. 2)")
    if "organismo di composizione della crisi" not in testo:
        mancanti.append("avvertimento completo: 'con l'ausilio di un organismo di composizione della crisi "
                        "o di un professionista nominato dal giudice' (art. 480 co. 2)")
    assert not mancanti, mancanti


def test_precetto_art_480_co3_giudice_competente_per_esecuzione():
    """Art. 480 co. 3 (D.Lgs. 149/2022 and 164/2024): the court competent for the execution."""
    _norma("art. 480 c.p.c.", "l'indicazione del giudice competente per l'esecuzione")
    testo = normalizza(_testo(_genera("atto_di_precetto", CASI["atto_di_precetto"][0])))
    assert contiene(testo, "giudice competente per l'esecuzione|giudice dell'esecuzione competente") == [], (
        "manca l'indicazione del giudice competente per l'esecuzione (art. 480 co. 3 c.p.c.)"
    )


# ---------------------------------------------------------------------------
# 4. decreto_ingiuntivo — artt. 7, 413, 633 ss. c.p.c.; artt. 9, 13, 14 DPR 115/2002
# ---------------------------------------------------------------------------


def test_decreto_ingiuntivo_giudice_competente_e_contributo():
    """GdP up to 10.000 euro (art. 7 co. 1, D.Lgs. 116/2017 deferred to 31/10/2027); CU halved."""
    _norma("art. 7 c.p.c.",
           "beni mobili di valore non superiore a diecimila euro",
           "le disposizioni dell'articolo 27 entrano in vigore il 31 ottobre 2027")
    _norma("art. 413 c.p.c.", "in primo grado di competenza del tribunale in funzione di giudice del lavoro")
    _norma("art. 13 DPR 115/2002",
           "euro 98 per i processi di valore superiore a euro 1.100 e fino a euro 5.200",
           "euro 237 per i processi di valore superiore a euro 5.200 e fino a euro 26.000",
           "il contributo e' ridotto alla meta' per i processi speciali previsti nel libro iv, titolo i")
    from src.lib import _clock
    from datetime import date

    assert _clock.today() < date(2027, 10, 31), "dal 31/10/2027 il giudice di pace sale a 30.000 euro"
    attesi = [("Giudice di Pace", 118.5), ("Tribunale", 118.5), ("Tribunale — Sezione Lavoro", None),
              ("Giudice di Pace", 49.0), ("Tribunale", 118.5), ("Giudice di Pace", 49.0)]
    for caso, (giudice, cu) in zip(CASI["decreto_ingiuntivo"], attesi):
        r = _genera("decreto_ingiuntivo", caso)["riepilogo"]
        assert r["giudice_competente"] == giudice, (caso, r)
        if cu is not None:
            assert r["contributo_unificato"] == pytest.approx(cu, abs=0.01), (caso, r)


def test_decreto_ingiuntivo_termini_641_644():
    _norma("art. 641 c.p.c.", "nel termine di quaranta giorni", "il termine e' di cinquanta giorni",
           "il termine e' di sessanta giorni")
    _norma("art. 644 c.p.c.", "nel termine di sessanta giorni dalla pronuncia", "e di novanta giorni negli altri casi")
    t = _genera("decreto_ingiuntivo", CASI["decreto_ingiuntivo"][0])["termini"]
    assert not contiene(t["opposizione"], "40 giorni", "50", "60 fuori", "art. 641")
    assert not contiene(t["notifica_decreto"], "60 giorni", "90", "art. 644")


def test_decreto_ingiuntivo_provvisoria_esecuzione_condominio_e_cambiale():
    _norma("art. 63 disp. att. c.c.", "decreto di ingiunzione immediatamente esecutivo")
    cond = _genera("decreto_ingiuntivo", CASI["decreto_ingiuntivo"][4])["riepilogo"]["motivi_pe"]
    camb = _genera("decreto_ingiuntivo", CASI["decreto_ingiuntivo"][5])["riepilogo"]["motivi_pe"]
    assert any("63 disp. att. c.c." in m for m in cond), cond
    assert any("642 co. 1" in m for m in camb), camb


def test_decreto_ingiuntivo_provvisoria_esecuzione_parcella_non_e_art_642_co1():
    """Art. 642 co. 1 lists cambiale, assegni, certificato di borsa, atti pubblici: not the parcella."""
    testo = _norma("art. 642 c.p.c.",
                   "se il credito e' fondato su cambiale, assegno bancario, assegno circolare, certificato di "
                   "liquidazione di borsa, o su atto ricevuto da notaio o da altro pubblico ufficiale autorizzato",
                   "pericolo di grave pregiudizio nel ritardo, ovvero se il ricorrente produce documentazione "
                   "sottoscritta dal debitore")
    assert "parcella" not in testo
    _norma("art. 636 c.p.c.", "corredata dal parere della competente associazione professionale")
    motivi = _genera("decreto_ingiuntivo", CASI["decreto_ingiuntivo"][3])["riepilogo"]["motivi_pe"]
    assert not any("642 co. 1" in m for m in motivi), (
        f"credito professionale: la provvisoria esecuzione e' fondata sull'art. 642 co. 1 c.p.c. ({motivi}); "
        "la parcella con il parere dell'Ordine e' la prova scritta dell'art. 636, la provvisoria esecuzione "
        "puo' fondarsi solo sull'art. 642 co. 2"
    )


def test_decreto_ingiuntivo_retribuzioni_contributo_art_9_co_1bis():
    """Labour credits: CU due only above three times the art. 76 threshold (art. 9 co. 1-bis)."""
    _norma("art. 9 DPR 115/2002", "superiore a tre volte l'importo previsto dall'articolo 76")
    out = _genera("decreto_ingiuntivo", CASI["decreto_ingiuntivo"][2])
    cu = out["riepilogo"]["contributo_unificato"]
    condizionato = cu == 0 or "9" in json.dumps(out["riepilogo"]) and "1-bis" in json.dumps(out["riepilogo"])
    assert condizionato, (
        f"retribuzioni: CU {cu} indicato senza la condizione dell'art. 9 co. 1-bis DPR 115/2002 "
        "(esente se il reddito non supera tre volte la soglia dell'art. 76)"
    )


def test_decreto_ingiuntivo_dichiarazione_di_valore_art_14():
    _norma("art. 14 DPR 115/2002",
           "deve risultare da apposita dichiarazione resa dalla parte nelle conclusioni dell'atto introduttivo")
    bozza = normalizza(_genera("decreto_ingiuntivo", CASI["decreto_ingiuntivo"][0])["bozza_ricorso"])
    assert re.search(r"dichiar\w*.{0,80}valore|valore.{0,80}contributo unificato", bozza), (
        "il ricorso non contiene la dichiarazione di valore ai fini del contributo unificato (art. 14 co. 2 DPR 115/2002)"
    )


def test_decreto_ingiuntivo_dati_applicati_art_9_tre_volte():
    """The footer of the contributo_unificato table (_vintage.nota) must quote art. 9 co. 1-bis right."""
    _norma("art. 9 DPR 115/2002", "superiore a tre volte l'importo previsto dall'articolo 76")
    footer = " ".join(_genera("decreto_ingiuntivo", CASI["decreto_ingiuntivo"][2]).get("dati_applicati", []))
    assert "due volte la soglia" not in footer, (
        "dati_applicati (contributo_unificato.json, _vintage.nota) dice 'due volte la soglia dell'art. 76': "
        "l'art. 9 co. 1-bis DPR 115/2002 dice 'tre volte'"
    )


def test_decreto_ingiuntivo_tipo_credito_sconosciuto():
    out = _genera("decreto_ingiuntivo", {**_DI, "importo": 5000, "tipo_credito": "inesistente"})
    assert "errore" in out, "tipo_credito non previsto accettato in silenzio (trattato come 'ordinario')"


# ---------------------------------------------------------------------------
# 5. dichiarazione_553_cpc — artt. 543, 545-548, 553 c.p.c.; art. 169-septies disp. att.
# ---------------------------------------------------------------------------


def test_dichiarazione_terzo_riferimenti_545_546_548():
    _norma("art. 548 c.p.c.", "si considera non contestato ai fini del procedimento in corso")
    _norma("art. 546 c.p.c.", "il terzo e' soggetto agli obblighi che la legge impone al custode")
    _norma("art. 545 c.p.c.", "nella misura di un quinto")
    cc, stip, _ = (_genera("dichiarazione_553_cpc", c) for c in CASI["dichiarazione_553_cpc"])
    for out in (cc, stip):
        assert "art. 548 c.p.c." in out["testo"] and "non contestato" in out["testo"]
    assert "art. 546 c.p.c." in cc["testo"]
    assert "art. 545 c.p.c." in stip["testo"] and "1/5" in stip["testo"]


def test_dichiarazione_terzo_contenuto_art_547():
    """Art. 547: raccomandata or PEC to the creditor; sequestri AND cessioni in every variant."""
    _norma("art. 547 c.p.c.",
           "con dichiarazione a mezzo raccomandata inviata al creditore procedente o trasmessa a mezzo di posta "
           "elettronica certificata",
           "deve altresi' specificare i sequestri precedentemente eseguiti presso di lui e le cessioni che gli "
           "sono state notificate o che ha accettato")
    mancanti = []
    for caso in CASI["dichiarazione_553_cpc"]:
        testo = normalizza(_testo(_genera("dichiarazione_553_cpc", caso)))
        for voce in ("sequestri", "cessioni"):
            if voce not in testo:
                mancanti.append(f"{caso['tipo_rapporto']}: manca '{voce}' (art. 547 co. 2)")
        if not re.search(r"raccomandata|posta elettronica certificata|\bpec\b", testo):
            mancanti.append(f"{caso['tipo_rapporto']}: nessuna indicazione dell'invio al creditore procedente "
                            "a mezzo raccomandata o PEC (art. 547 co. 1)")
    assert not mancanti, "\n".join(mancanti)


def test_dichiarazione_terzo_docstring_art_543_co2_n4():
    """The ten-day invitation to the third party is art. 543 co. 2 n. 4 (n. 3 is the domicile)."""
    testo = _norma("art. 543 c.p.c.",
                   "4) la citazione del debitore a comparire davanti al giudice competente, con l'invito al terzo "
                   "a comunicare la dichiarazione di cui all'articolo 547 al creditore procedente entro dieci giorni")
    assert "3) la dichiarazione di residenza o l'elezione di domicilio" in testo
    doc = inspect.getdoc(_tool("dichiarazione_553_cpc")) or ""
    assert "n. 3" not in doc, "la riga Vigenza colloca l'invito dei dieci giorni nell'art. 543 co. 2 n. 3: e' il n. 4"


def test_dichiarazione_553_nome_e_art_553_vigente():
    """Vigente art. 553 co. 1 + art. 169-septies disp. att.: the 'dichiarazione' of art. 553 is the
    CREDITOR's statement of the payment data served with the ordinanza di assegnazione. A tool named
    `dichiarazione_553_cpc` that produces the third party's declaration (art. 547) names another act.
    """
    _norma("art. 553 c.p.c.",
           "la notifica dell'ordinanza di assegnazione e' accompagnata da una dichiarazione nella quale il "
           "creditore indica al terzo i dati necessari per provvedere al pagamento")
    _norma("art. 169-septies disp. att. c.p.c.", "la dichiarazione prevista dall'articolo 553, primo comma, del codice")
    out = _genera("dichiarazione_553_cpc", CASI["dichiarazione_553_cpc"][0])
    assert "169-septies" in _tutto(out) or "553" in out["tipo_atto"], (
        f"il tool 'dichiarazione_553_cpc' genera '{out['tipo_atto']}' (art. 547): la dichiarazione ex art. 553 "
        "c.p.c. vigente e' quella del creditore ex art. 169-septies disp. att. (atto diverso)"
    )


# ---------------------------------------------------------------------------
# 6. fascicolo_di_parte — art. 165 c.p.c.; art. 74 disp. att. c.p.c.
# ---------------------------------------------------------------------------


def test_fascicolo_di_parte_struttura():
    _norma("art. 165 c.p.c.", "iscrivendo la causa a ruolo e depositando l'originale della citazione, la procura e i documenti")
    _norma("art. 74 disp. att. c.p.c.", "ciascuno numerato e con denominazione descrittiva del suo contenuto")
    con_rg, senza_rg = (_genera("fascicolo_di_parte", c) for c in CASI["fascicolo_di_parte"])
    assert not contiene(con_rg["testo"], "TRIBUNALE DI MILANO", "R.G. n. 12345/2026", "ALFA S.R.L.",
                        "BETA S.P.A.", "Avv. Mario Rossi", "1. Procura alle liti", "2. Atto introduttivo")
    assert "R.G. n. ___/____" in senza_rg["testo"] and "TRIBUNALE DI ROMA" in senza_rg["testo"]
    assert "165" in con_rg["riferimento_normativo"]


# ---------------------------------------------------------------------------
# 7. indice_documenti — art. 74 disp. att. c.p.c.
# ---------------------------------------------------------------------------


def test_indice_documenti_totali_e_ordine():
    tre, vuoto = (_genera("indice_documenti", c) for c in CASI["indice_documenti"])
    assert (tre["totale_documenti"], tre["totale_pagine"]) == (3, 19)
    righe = [r for r in tre["testo"].splitlines() if r.startswith("Doc.")]
    assert [r.split("—")[1].strip().split("  ")[0] for r in righe] == ["Contratto di fornitura", "Fatture insolute", "Diffida"]
    assert "Totale documenti: 3 — Totale pagine: 19" in tre["testo"]
    assert (vuoto["totale_documenti"], vuoto["totale_pagine"]) == (0, 0)


def test_indice_documenti_pagine_non_numeriche():
    try:
        out = _genera("indice_documenti", {"documenti": [{"numero": 1, "descrizione": "Contratto", "pagine": "abc"}]})
    except ValueError as exc:
        pytest.fail(f"'pagine' non numerico: eccezione non gestita ({exc}) invece di un dict con 'errore'")
    assert "errore" in out


# ---------------------------------------------------------------------------
# 8. istanza_visibilita_fascicolo — art. 76 disp. att. c.p.c.; art. 105 c.p.c.
# ---------------------------------------------------------------------------


def test_istanza_visibilita_struttura():
    _norma("art. 76 disp. att. c.p.c.",
           "le parti e i loro difensori muniti di procura possono accedere al fascicolo informatico")
    _norma("art. 105 c.p.c.", "ciascuno puo' intervenire in un processo tra altre persone")
    cost, interv, cons = (_genera("istanza_visibilita_fascicolo", c) for c in CASI["istanza_visibilita_fascicolo"])
    for out in (cost, interv, cons):
        assert not contiene(out["testo"], "R.G. n. 12345/2026", "Beta S.p.A.", "Avv. Mario Rossi",
                            "copia del mandato difensivo", "visibilità del fascicolo telematico")
    assert "art. 105 c.p.c." in interv["testo"]
    assert "consultazione" in cons["testo"]


def test_istanza_visibilita_motivo_non_previsto():
    out = _genera("istanza_visibilita_fascicolo", {**_ROSSI, "parte": "Beta S.p.A.", "tribunale": "Tribunale di Milano",
                                                   "rg_numero": "12345/2026", "motivo": "altro"})
    assert "errore" in out, "motivo non previsto ('altro') ricade in silenzio sul testo di 'costituzione'"


# ---------------------------------------------------------------------------
# 9. nota_precisazione_credito — artt. 510, 553, 596 c.p.c.
# ---------------------------------------------------------------------------


def test_nota_precisazione_totale():
    out = _genera("nota_precisazione_credito", CASI["nota_precisazione_credito"][0])
    assert out["totale_credito"] == pytest.approx(6076.25, abs=0.01)
    assert "547" not in _tutto(out)
    _norma("art. 510 c.p.c.", "il pagamento di quanto gli spetta per capitale, interessi e spese")


def test_nota_precisazione_assegnazione_presso_terzi_art_553_non_543():
    """Art. 543 is the form of the pignoramento presso terzi; the assegnazione is art. 553."""
    _norma("art. 543 c.p.c.", "(forma del pignoramento)")
    _norma("art. 553 c.p.c.", "(assegnazione e vendita di crediti)")
    rif = _genera("nota_precisazione_credito", CASI["nota_precisazione_credito"][0])["riferimento_normativo"]
    assert "553" in rif and "543" not in rif, (
        f"riferimento '{rif}': l'art. 543 c.p.c. disciplina la forma del pignoramento presso terzi; "
        "per l'assegnazione il riferimento e' l'art. 553 (per la distribuzione artt. 510 e 596)"
    )


# ---------------------------------------------------------------------------
# 10. note_trattazione_scritta — art. 127-ter c.p.c.
# ---------------------------------------------------------------------------


def test_note_trattazione_intestazione_e_conclusioni():
    caso = CASI["note_trattazione_scritta"][0]
    testo = _testo(_genera("note_trattazione_scritta", caso))
    assert not contiene(testo, "R.G. n. 12345/2025", "dott.ssa Laura Bianchi", "Alfa S.r.l.", "Avv. Mario Rossi",
                        "art. 127-ter c.p.c.", caso["conclusioni"])


def test_note_trattazione_sole_istanze_e_conclusioni():
    _norma("art. 127-ter c.p.c.", "deposito di note scritte, contenenti le sole istanze e conclusioni")
    testo = normalizza(_testo(_genera("note_trattazione_scritta", CASI["note_trattazione_scritta"][0])))
    extra = [f for f in ("si osserva quanto segue", "si producono i seguenti documenti") if f in testo]
    assert not extra, (
        f"il modello contiene {extra}: l'art. 127-ter co. 1 c.p.c. ammette note 'contenenti le sole istanze e conclusioni'"
    )


def test_note_trattazione_provvedimento_e_termine_assegnato():
    _norma("art. 127-ter c.p.c.",
           "con il provvedimento con cui sostituisce l'udienza il giudice assegna un termine perentorio non inferiore a quindici giorni",
           "il giorno di scadenza del termine assegnato per il deposito delle note")
    testo = normalizza(_testo(_genera("note_trattazione_scritta", CASI["note_trattazione_scritta"][0])))
    assert re.search(r"provvedimento|decreto", testo) and "termine" in testo, (
        "le note non richiamano il provvedimento di sostituzione dell'udienza ne' il termine assegnato (art. 127-ter co. 2 e 5)"
    )


# ---------------------------------------------------------------------------
# 11. procura_alle_liti — artt. 83, 84 c.p.c.; D.Lgs. 231/2007; Reg. (UE) 2016/679
# ---------------------------------------------------------------------------


def test_procura_poteri_grado_e_autentica():
    _norma("art. 83 c.p.c.",
           "l'autografia della sottoscrizione della parte deve essere certificata dal difensore",
           "la procura speciale si presume conferita soltanto per un determinato grado del processo")
    _norma("art. 84 c.p.c.", "non puo' compiere atti che importano disposizione del diritto in contesa")
    gen, app, spec = (_genera("procura_alle_liti", c) for c in CASI["procura_alle_liti"])
    for out in (gen, app, spec):
        assert not contiene(out["testo"], "conciliare", "transigere", "rinunciare agli atti",
                            "È vera la firma apposta in mia presenza", "RSSMRA80A01F205X", "Foro di Milano")
    assert "in ogni stato e grado" in gen["testo"]
    assert "giudizio di appello" in app["testo"] and "PER L'APPELLO" in app["testo"]
    assert "per il presente giudizio" in spec["testo"]


def test_procura_antiriciclaggio_articolo_citato():
    """'art. 4 co. 3 del D.Lgs. 231/2007' is the MEF's power to exempt minor financial operators."""
    art4 = _normattiva_oggi("urn:nir:stato:decreto.legislativo:2007-11-21;231~art4")
    assert "art. 4 (ministro dell'economia e delle finanze)" in art4
    assert "identita' del cliente" not in art4 and "identità del cliente" not in art4
    art17 = _normattiva_oggi("urn:nir:stato:decreto.legislativo:2007-11-21;231~art17")
    assert "adeguata verifica del cliente" in art17
    testo = _genera("procura_alle_liti", CASI["procura_alle_liti"][0])["testo"]
    assert "art. 4 co. 3 del D.Lgs. 231/2007" not in testo, (
        "la procura fonda l'adeguata verifica sull'art. 4 co. 3 D.Lgs. 231/2007, che dopo il D.Lgs. 90/2017 "
        "disciplina i poteri di esenzione del Ministro dell'economia: l'adeguata verifica e' negli artt. 17 ss."
    )


def test_procura_base_giuridica_gdpr_non_consenso():
    """The lawyer's processing rests on art. 6(1)(b) and art. 9(2)(f) GDPR, not on consent."""
    _norma("art. 6 Reg. UE 2016/679", "il trattamento è necessario all'esecuzione di un contratto di cui l'interessato è parte")
    _norma("art. 9 Reg. UE 2016/679", "necessario per accertare, esercitare o difendere un diritto in sede giudiziaria")
    testo = normalizza(_genera("procura_alle_liti", CASI["procura_alle_liti"][0])["testo"])
    assert "presta il consenso al trattamento" not in testo, (
        "la procura acquisisce il 'consenso' al trattamento come base giuridica del mandato difensivo: "
        "le basi sono l'art. 6 par. 1 lett. b) e l'art. 9 par. 2 lett. f) GDPR"
    )


# ---------------------------------------------------------------------------
# 12. relata_notifica_pec — artt. 1, 3-bis L. 53/1994; art. 147 c.p.c.
# ---------------------------------------------------------------------------


def test_relata_perfezionamento_art_147_co3():
    _norma("art. 147 c.p.c.",
           "per il notificante, nel momento in cui e' generata la ricevuta di accettazione",
           "se quest'ultima e' generata tra le ore 21 e le ore 7 del mattino del giorno successivo, la notificazione "
           "si intende perfezionata per il destinatario alle ore 7")
    _norma("art. 1 L. 53/1994", "fatta eccezione per l'autorizzazione del consiglio dell'ordine")
    testo = _testo(_genera("relata_notifica_pec", CASI["relata_notifica_pec"][0]))
    assert not contiene(testo, "05/10/2026", "ricevuta di accettazione", "ricevuta di avvenuta consegna",
                        "tra le ore 21 e le ore 7", "alle ore 7", "art. 147 co. 3 c.p.c.",
                        "non occorre l'autorizzazione del Consiglio dell'Ordine", "beta@pec.it")


def test_relata_elementi_art_3bis_co5_e_co6():
    testo_norma = _norma("art. 3-bis L. 53/1994",
                         "a) il nome, cognome ed il codice fiscale dell'avvocato notificante",
                         "c) il nome e cognome o la denominazione e ragione sociale ed il codice fiscale della parte "
                         "che ha conferito la procura alle liti",
                         "f) l'indicazione dell'elenco da cui il predetto indirizzo e' stato estratto",
                         "g) l'attestazione di conformita' di cui al comma 2",
                         "l'ufficio giudiziario, la sezione, il numero e l'anno di ruolo")
    assert "196-undecies" in testo_norma
    testo = _testo(_genera("relata_notifica_pec", CASI["relata_notifica_pec"][0]))
    low = normalizza(testo)
    mancanti = []
    intestazione = low.split("certifica")[0]
    if not re.search(r"c\.f\.|codice fiscale", intestazione):
        mancanti.append("lett. a): codice fiscale dell'avvocato notificante")
    if "procura" not in low:
        mancanti.append("lett. c): parte che ha conferito la procura alle liti, con codice fiscale")
    frase_elenco = next((s for s in low.split(". ") if "pubblici elenchi (" in s), "")
    if len(re.findall(r"ini-pec|regind?e|registro imprese", frase_elenco)) > 1:
        mancanti.append("lett. f): indica tre elenchi insieme (INI-PEC / ReGIndE / Registro Imprese) invece di quello usato")
    if "196-undecies" not in low and "attest" not in low:
        mancanti.append("lett. g): attestazione di conformita' della copia informatica (co. 2, art. 196-undecies disp. att.)")
    if not re.search(r"r\.g\.|ruolo", low):
        mancanti.append("co. 6: ufficio giudiziario, sezione, numero e anno di ruolo (notifiche in corso di procedimento)")
    assert not mancanti, "relata PEC, elementi dell'art. 3-bis L. 53/1994 mancanti:\n" + "\n".join(mancanti)


def test_relata_data_inesistente():
    caso = {**CASI["relata_notifica_pec"][0], "data_invio": "2026-02-30"}
    try:
        out = _genera("relata_notifica_pec", caso)
    except ValueError as exc:
        pytest.fail(f"data inesistente: eccezione non gestita ({exc}) invece di un dict con 'errore'")
    assert "errore" in out


# ---------------------------------------------------------------------------
# 13. sfratto_morosita — artt. 658, 660, 663, 664 c.p.c.; art. 55 L. 392/1978
# ---------------------------------------------------------------------------


def test_sfratto_totale_convalida_e_termine_di_grazia():
    _norma("art. 663 c.p.c.", "se l'intimato non compare o comparendo non si oppone, il giudice convalida")
    _norma("art. 55 L. 392/1978", "puo' assegnare un termine non superiore a giorni novanta")
    out = _genera("sfratto_morosita", CASI["sfratto_morosita"][0])
    assert out["totale_dovuto"] == pytest.approx(3000.00, abs=0.01)
    assert not contiene(out["testo"], "01/03/2022", "n. 4 mensilità", "3,000.00|3.000,00",
                        "non comparirà o comparendo non si opporrà", "art. 663", "non superiore a 90 giorni",
                        "art. 55 L. 392/1978")


def test_sfratto_avvertimento_patrocinio_art_660_co3():
    _norma("art. 660 c.p.c.",
           "l'avvertimento che se non comparisce o, comparendo, non si oppone, il giudice convalida",
           "la parte puo' presentare istanza per l'ammissione al patrocinio a spese dello stato")
    testo = normalizza(_testo(_genera("sfratto_morosita", CASI["sfratto_morosita"][0])))
    assert "patrocinio a spese dello stato" in testo, (
        "la citazione per la convalida non contiene l'avvertimento sull'ammissione al patrocinio a spese dello "
        "Stato richiesto dall'art. 660 co. 3 c.p.c."
    )


def test_sfratto_ingiunzione_canoni_art_658_664():
    _norma("art. 658 c.p.c.", "chiedere nello stesso atto l'ingiunzione di pagamento per i canoni scaduti")
    _norma("art. 664 c.p.c.", "pronuncia separato decreto d'ingiunzione per l'ammontare dei canoni scaduti e da scadere")
    testo = normalizza(_testo(_genera("sfratto_morosita", CASI["sfratto_morosita"][0])))
    assert "ingiunzione" in testo, (
        "per i canoni il modello chiede 'la condanna': l'art. 658 c.p.c. consente di chiedere nello stesso atto "
        "l'ingiunzione di pagamento dei canoni scaduti (decreto ex art. 664)"
    )


def test_sfratto_mensilita_non_positive():
    out = _genera("sfratto_morosita", {**_SFRATTO, "mensilita_insolute": 0})
    assert "errore" in out, f"mensilita_insolute=0 accettato: totale_dovuto {out.get('totale_dovuto')}"


# ---------------------------------------------------------------------------
# 14. testimonianza_scritta — art. 257-bis, 251, 252, 255 c.p.c.; art. 103-bis disp. att.
# ---------------------------------------------------------------------------


def test_testimonianza_formula_capitoli_e_sanzione():
    _norma("art. 251 c.p.c.",
           "consapevole della responsabilita' morale e giuridica che assumo con la mia deposizione",
           "sentenza 4 - 5 maggio 1995, n. 149")
    _norma("art. 257-bis c.p.c.", "pena pecuniaria di cui all'articolo 255, primo comma")
    out = _genera("testimonianza_scritta", CASI["testimonianza_scritta"][0])
    assert out["numero_capitoli"] == 2
    assert not contiene(out["testo"], *_CAPITOLI, "Anna Neri", "Corte cost. n. 149/1995", "art. 255 c.p.c.",
                        "Consapevole della responsabilità morale e giuridica che assumo con la mia deposizione, "
                        "mi impegno a dire tutta la verità e a non nascondere nulla di quanto è a mia conoscenza")


def test_testimonianza_avvertimento_dopo_corte_cost_149_1995():
    """Corte cost. 149/1995 replaced 'ammonisce ... sull'importanza religiosa, se credente, e morale del
    giuramento' with 'avverte il testimone dell'obbligo di dire la verita''."""
    _norma("art. 251 c.p.c.", "avverte il testimone dell'obbligo di dire la verita' e delle")
    testo = normalizza(_testo(_genera("testimonianza_scritta", CASI["testimonianza_scritta"][0])))
    assert "importanza morale del giuramento" not in testo, (
        "il modello ammonisce 'sull'importanza morale del giuramento', formula dichiarata illegittima da "
        "Corte cost. 149/1995: il testimone va avvertito 'dell'obbligo di dire la verita''"
    )


def test_testimonianza_conoscenza_diretta_o_indiretta():
    _norma("art. 103-bis disp. att. c.p.c.",
           "deve altresi' precisare se ha avuto conoscenza dei fatti oggetto della testimonianza in modo diretto o indiretto")
    testo = normalizza(_testo(_genera("testimonianza_scritta", CASI["testimonianza_scritta"][0])))
    assert "non è possibile deporre su fatti appresi da terzi" not in testo, (
        "istruzione 'Non è possibile deporre su fatti appresi da terzi': l'art. 103-bis disp. att. chiede al "
        "teste di precisare se la conoscenza e' diretta o indiretta"
    )


def test_testimonianza_autenticazione_firme():
    _norma("art. 103-bis disp. att. c.p.c.",
           "devono essere autenticate da un segretario comunale o dal cancelliere di un ufficio giudiziario",
           "l'autentica delle sottoscrizioni e' in ogni caso gratuita")
    _norma("art. 257-bis c.p.c.", "apponendo la propria firma autenticata su ciascuna delle facciate del foglio")
    testo = normalizza(_testo(_genera("testimonianza_scritta", CASI["testimonianza_scritta"][0])))
    problemi = []
    if "altro pubblico ufficiale" in testo or "cancelliere" not in testo:
        problemi.append("autentica di 'segretario comunale o altro pubblico ufficiale' invece di segretario comunale "
                        "o cancelliere (art. 103-bis co. 3 disp. att.)")
    if "facciat" not in testo:
        problemi.append("una sola autentica finale: la firma va autenticata su ciascuna facciata (art. 257-bis co. 4)")
    assert not problemi, "\n".join(problemi)


def test_testimonianza_contenuto_modello_art_103bis():
    _norma("art. 103-bis disp. att. c.p.c.",
           "indicazione del procedimento e dell'ordinanza di ammissione",
           "e, ove possibile, di un suo recapito telefonico",
           "facolta' di astenersi ai sensi degli articoli 200, 201 e 202 del codice di procedura penale",
           "ivi compresa l'indicazione di eventuali rapporti personali con le parti")
    testo = normalizza(_testo(_genera("testimonianza_scritta", CASI["testimonianza_scritta"][0])))
    richiesti = {
        "ordinanza di ammissione": r"ordinanza",
        "domicilio del teste": r"domicili",
        "recapito telefonico": r"telefon",
        "avviso della facolta' di astenersi (artt. 200-202 c.p.p.)": r"astener|astensione",
        "rapporti con le parti / interesse nella causa (art. 252 c.p.c.)": r"rapport\w* .{0,40}part|parentela",
    }
    mancanti = [k for k, pat in richiesti.items() if not re.search(pat, testo)]
    assert not mancanti, "modulo di testimonianza: elementi dell'art. 103-bis co. 1 disp. att. mancanti: " + ", ".join(mancanti)


def test_testimonianza_senza_capitoli():
    out = _genera("testimonianza_scritta", {"teste": "Anna Neri", "capitoli_prova": []})
    assert "errore" in out, "lista dei capitoli vuota: modulo generato comunque (numero_capitoli 0)"

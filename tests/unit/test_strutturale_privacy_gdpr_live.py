"""Live structural gate: the eight GDPR document generators of `src/tools/privacy_gdpr.py`.

Tools covered: genera_dpa, genera_dpia, genera_informativa_cookie,
genera_informativa_dipendenti, genera_informativa_privacy,
genera_informativa_videosorveglianza, genera_notifica_data_breach,
genera_registro_trattamenti.

For each generator this file runs the cases of the benchmark plan
(`docs/benchmark/piano-benchmark-andreani.json`, key `tool[].casi`) and checks:

1. the structure the norm requires of the document (the eight clauses of art. 28(3) GDPR
   in the DPA, the elements of artt. 13/14 in the informativa, art. 30(1) in the register,
   art. 33(3) in the breach notification, art. 35(7)/36 in the DPIA, the Garante cookie
   guidelines of 10 June 2021 for the banner, art. 4 L. 300/1970 and art. 114 D.Lgs.
   196/2003 for the workplace notices), reading the vigente text of every norm through
   `cite_law()` (EUR-Lex/CELLAR, Normattiva) and the Garante documents through the
   GPDP client (doc. web 9677876 cookie guidelines, doc. web 9667201 on-line breach
   procedure) or the Garante web pages (contacts, videosurveillance FAQ);
2. every normative reference printed in the generated text, extracted by regex and passed
   to `verifica_citazioni()`: it must exist and its paragraph/letter must be found.

Several tests fail today ON PURPOSE: they pin genuine gaps between the generated
documents and the norm (missing art. 28(3) last sub-paragraph, art. 13(2)(e)/(f),
the ITL authorisation attributed to art. 4(2) instead of 4(1) L. 300/1970, the
40-year retention attributed to art. 25(1)(a) D.Lgs. 81/2008, residual DPIA risk that
ignores the mitigation measures, ...). Each failure message names the norm.

It needs the network and is excluded from the default run:

    .venv/bin/pytest tests/unit/test_strutturale_privacy_gdpr_live.py -m live -q -p no:cacheprovider -rfEs
"""

from __future__ import annotations

import asyncio
import json
import re
from functools import lru_cache
from pathlib import Path

import httpx
import pytest

from tests.unit._norme_live import contiene, normalizza
from tests.unit._norme_live import testo_vigente as _testo_vigente  # alias: pytest would collect test*

pytestmark = pytest.mark.live

_ROOT = Path(__file__).resolve().parents[2]
_PIANO = _ROOT / "docs" / "benchmark" / "piano-benchmark-andreani.json"
_LEGAL_NOW = "2026-09-25T12:00:00"
_UA = {"User-Agent": "Mozilla/5.0 (mcp-legal-it benchmark; live test)"}


# --------------------------------------------------------------------------- helpers


@lru_cache(maxsize=None)
def _piano() -> dict:
    return {t["name"]: t for t in json.loads(_PIANO.read_text(encoding="utf-8"))["tool"]}


def _casi(nome: str) -> list:
    """The benchmark cases of a tool as pytest params (id = case description)."""
    return [
        pytest.param(json.loads(c["input"]), id=c["descrizione"])
        for c in _piano()[nome]["casi"]
    ]


def _caso(nome: str, descrizione: str) -> dict:
    for c in _piano()[nome]["casi"]:
        if c["descrizione"] == descrizione:
            return json.loads(c["input"])
    raise KeyError(f"{nome}: caso {descrizione!r} assente dal piano")


def _fn(nome: str):
    import src.server  # noqa: F401  (registers every tool module first: avoids a circular import)
    import src.tools.privacy_gdpr as mod

    tool = getattr(mod, nome)
    return getattr(tool, "fn", tool)


def _tool(nome: str, **kwargs) -> dict:
    r = _fn(nome)(**kwargs)
    assert isinstance(r, dict) and not r.get("errore"), r
    return r


def _documento(r: dict) -> str:
    """Every string the tool returns (testo, cartello, estesa, banner...), joined."""
    return "\n".join(v for v in r.values() if isinstance(v, str))


@lru_cache(maxsize=None)
def _testo(reference: str) -> str:
    """Normalised vigente text, fetched once per reference for the whole module."""
    return _testo_vigente(reference)


def _assert_norma(reference: str, *frasi: str) -> str:
    testo = _testo(reference)
    missing = contiene(testo, *frasi)
    assert not missing, f"{reference}: il testo vigente non contiene {missing}"
    return testo


def _commi(testo: str) -> dict[str, str]:
    """Split a normalised article into its numbered paragraphs ('1.', '2.', '2-bis.')."""
    parti = re.split(r"(?:^|\s)(\d+(?:-bis)?)\.\s", " " + testo)
    return {parti[i]: parti[i + 1] for i in range(1, len(parti) - 1, 2)}


@lru_cache(maxsize=None)
def _gpdp_doc(docweb: int) -> tuple[str, str]:
    """Full text of a Garante doc. web (the MCP tool truncates at 6000 characters)."""
    from src.lib.gpdp.client import fetch_doc

    return asyncio.run(fetch_doc(docweb))


@lru_cache(maxsize=None)
def _pagina(url: str) -> str:
    """Visible text of a public web page, tags stripped and whitespace collapsed."""
    import html

    r = httpx.get(url, headers=_UA, follow_redirects=True, timeout=30)
    r.raise_for_status()
    testo = html.unescape(re.sub(r"<[^>]+>", " ", r.text))
    return re.sub(r"\s+", " ", testo)


# ------------------------------------------------------- normative reference extraction

_ATTI = [
    (re.compile(r"^\W*(?:del\s+)?d\.\s*lgs\.?\s*(?:n\.\s*)?196/2003", re.I), "D.Lgs. 196/2003"),
    (re.compile(r"^\W*(?:del\s+)?d\.\s*lgs\.?\s*(?:n\.\s*)?81/2008", re.I), "D.Lgs. 81/2008"),
    (re.compile(r"^\W*(?:della\s+)?l\.\s*(?:n\.\s*)?300/1970", re.I), "L. 300/1970"),
    (re.compile(r"^\W*c\.c\.", re.I), "c.c."),
    (re.compile(r"^\W*(?:gdpr|reg(?:olamento)?\.?\s*(?:\(?ue\)?)\s*(?:n\.\s*)?2016/679)", re.I), "GDPR"),
]
_ART = re.compile(
    r"\bart(t?)\.\s*(\d+(?:-[a-z]+)?)((?:\(\d+\))?)((?:\([a-z]\))?)(?:\s*[-–/]\s*(\d+))?", re.I
)


def _estrai_riferimenti(testo: str) -> list[str]:
    """Normative references of a generated document, in the form verifica_citazioni reads.

    `art. 28(3)(a)` becomes `art. 28 comma 3 lett. a) GDPR`; a range `artt. 15-22` yields both
    ends. A bare `art. N` counts only when it has a paragraph/letter, an explicit act, or sits
    in brackets: that keeps out the DPA's own headings ("ART. 1 — OGGETTO", "all'art. 1").
    Bare references default to the GDPR, the act every one of these documents implements.
    """
    refs: list[str] = []
    for m in _ART.finditer(testo):
        num, par, lett, fino = m.group(2), m.group(3), m.group(4), m.group(5)
        coda = testo[m.end(): m.end() + 40]
        atto = None
        for rx, nome in _ATTI:
            if rx.search(coda):
                atto = nome
                break
        prima = testo[max(0, m.start() - 1): m.start()]
        if atto is None and not (par or lett) and prima not in ("(", "["):
            continue
        atto = atto or "GDPR"
        for n in [num] + ([fino] if fino else []):
            ref = f"art. {n}"
            if n == num and par:
                ref += f" comma {par.strip('()')}"
            if n == num and lett:
                ref += f" lett. {lett.strip('()')})"
            refs.append(f"{ref} {atto}")
    return sorted(set(refs))


_VERIFICHE: dict[str, dict] = {}


def _verifica(refs: list[str]) -> dict[str, dict]:
    """verifica_citazioni (json) on the references, 20 per call, cached for the module."""
    import src.server  # noqa: F401
    from src.tools.legal_citations import verifica_citazioni

    fn = getattr(verifica_citazioni, "fn", verifica_citazioni)
    nuovi = [r for r in refs if r not in _VERIFICHE]
    for i in range(0, len(nuovi), 20):
        blocco = nuovi[i: i + 20]
        data = json.loads(asyncio.run(fn(citazioni="\n".join(blocco), formato="json")))
        assert data.get("errore") is None, data
        for c in data["citazioni"]:
            _VERIFICHE[c["citazione"]] = c
    return {r: _VERIFICHE[r] for r in refs}


def _assert_citazioni(nome: str) -> list[str]:
    refs: set[str] = set()
    for p in _casi(nome):
        refs |= set(_estrai_riferimenti(_documento(_tool(nome, **p.values[0]))))
    assert refs, f"{nome}: nessun riferimento normativo estratto"
    esiti = _verifica(sorted(refs))
    cattive = {r: (c["verdetto"], c["nota"]) for r, c in esiti.items() if c["verdetto"] != "verificata"}
    assert not cattive, f"{nome}: citazioni non verificate {cattive}"
    return sorted(refs)


@pytest.fixture(autouse=True)
def _orologio(monkeypatch):
    """Pin the clock (only genera_notifica_data_breach reads it) for reproducible cases."""
    monkeypatch.setenv("LEGAL_NOW", _LEGAL_NOW)


@pytest.mark.parametrize(
    "nome",
    [
        "genera_dpa",
        "genera_dpia",
        "genera_informativa_cookie",
        "genera_informativa_dipendenti",
        "genera_informativa_privacy",
        "genera_informativa_videosorveglianza",
        "genera_notifica_data_breach",
        "genera_registro_trattamenti",
    ],
)
def test_citazioni_del_documento_esistono(nome):
    """Every article cited in the generated text exists and its paragraph/letter is there."""
    _assert_citazioni(nome)


# --------------------------------------------------------------------------- genera_dpa
# Art. 28 GDPR (EUR-Lex, CELEX 32016R0679), read 2026-09-25.

_DPA_CONTENUTO_28_3 = {
    # letter of art. 28(3) -> words of the generated clause that carry it
    "primo periodo: materia e durata": ("oggetto e durata del trattamento", "durata del trattamento:"),
    "primo periodo: natura e finalità": ("natura e finalità del trattamento",),
    "primo periodo: tipo di dati e categorie di interessati": ("categorie di interessati", "categorie di dati personali"),
    "primo periodo: obblighi e diritti del titolare": ("obblighi del titolare",),
    "a) istruzioni documentate, anche per i trasferimenti": ("istruzione documentata", "paese terzo"),
    "b) impegno alla riservatezza": ("impegnate alla riservatezza",),
    "c) misure dell'art. 32": ("misure di sicurezza richieste dall'art. 32",),
    "d) condizioni dei paragrafi 2 e 4 per i sub-responsabili": ("sub-responsabil",),
    "e) assistenza per i diritti dell'interessato": ("esercizio dei diritti",),
    "f) assistenza per gli artt. 32-36": ("artt. 32-36",),
    "g) cancellazione o restituzione a fine servizio": ("cancella o restituisce",),
    "h) informazioni e ispezioni": ("ispezioni",),
    # Art. 28(3), secondo comma: "Con riguardo alla lettera h) del primo comma, il responsabile
    # del trattamento informa immediatamente il titolare del trattamento qualora, a suo parere,
    # un'istruzione violi il presente regolamento ..."
    "28(3) ultimo periodo: avviso immediato se un'istruzione viola il GDPR": ("un'istruzione violi",),
}


def test_dpa_norma_vigente_art28():
    """Art. 28(2), (3) and (4) GDPR: the words the DPA must reproduce are in the vigente text."""
    _assert_norma(
        "art. 28 GDPR",
        "previa autorizzazione scritta, specifica o generale",
        "l'opportunità di opporsi a tali modifiche",
        "la materia disciplinata e la durata del trattamento, la natura e la finalità del trattamento",
        "informa immediatamente il titolare del trattamento qualora, a suo parere, un'istruzione violi",
        "gli stessi obblighi in materia di protezione dei dati",
        "conserva nei confronti del titolare del trattamento l'intera responsabilità",
    )


@pytest.mark.parametrize("caso", _casi("genera_dpa"))
def test_dpa_clausole_art28_3(caso):
    """Art. 28(3) GDPR: first period, letters a)-h) and the last sub-paragraph are in the DPA."""
    r = _tool("genera_dpa", **caso)
    testo = normalizza(r["testo"])
    mancanti = [k for k, frasi in _DPA_CONTENUTO_28_3.items() if contiene(testo, *frasi)]
    assert r["tutte_clausole_presenti"] is True
    assert not mancanti, f"DPA senza gli elementi dell'art. 28(3) GDPR: {mancanti}"


def test_dpa_sub_responsabili_art28_2_e_4():
    """Art. 28(2) and 28(4) GDPR: prior information with right to object, SAME obligations,
    full liability of the initial processor (case 'Hosting CRM con sub-responsabile')."""
    r = _tool("genera_dpa", **_caso("genera_dpa", "Hosting CRM con sub-responsabile"))
    testo = normalizza(r["testo"])
    assert "aws emea sarl" in testo
    mancanti = contiene(
        testo,
        "possibilità di opporsi",                 # 28(2)
        "pienamente responsabile",                # 28(4), secondo periodo
        "stessi obblighi",                        # 28(4): "gli stessi obblighi", not "analoghi"
    )
    assert not mancanti, (
        "art. 28(4) GDPR impone al sub-responsabile 'gli stessi obblighi in materia di protezione "
        f"dei dati'; il DPA scrive 'obblighi analoghi'. Mancano: {mancanti}"
    )


def test_dpa_senza_sub_responsabili_art28_2():
    """Art. 28(2) GDPR: without sub-processors the clause 4.4 forbids them without prior
    specific or general written authorisation (case 'Senza sub-responsabili')."""
    r = _tool("genera_dpa", **_caso("genera_dpa", "Senza sub-responsabili"))
    testo = normalizza(r["testo"])
    assert not contiene(testo, "4.4 sub-responsabili", "previa autorizzazione scritta specifica o generale")


# --------------------------------------------------------------------------- genera_dpia
# Artt. 35 and 36 GDPR (EUR-Lex), read 2026-09-25; WP248 rev.01 (allegato 2).


def test_dpia_norma_vigente_art35_36():
    """Art. 35(7) a)-d), art. 35(2) and art. 36(1)-(2): the anchors of the DPIA structure."""
    _assert_norma(
        "art. 35 GDPR",
        "una descrizione sistematica dei trattamenti previsti e delle finalità del trattamento",
        "una valutazione della necessità e proporzionalità dei trattamenti",
        "una valutazione dei rischi per i diritti e le libertà degli interessati",
        "le misure previste per affrontare i rischi",
        "si consulta con il responsabile della protezione dei dati",
    )
    _assert_norma(
        "art. 36 GDPR",
        "presenterebbe un rischio elevato in assenza di misure adottate dal titolare del trattamento per attenuare il rischio",
        "otto settimane",
        "prorogato di sei settimane",
    )


@pytest.mark.parametrize("caso", _casi("genera_dpia"))
def test_dpia_struttura_art35_7(caso):
    """Art. 35(7) GDPR: the four minimum contents and the DPO consultation (35(2)) are sections."""
    r = _tool("genera_dpia", **caso)
    testo = normalizza(r["testo"])
    mancanti = contiene(
        testo,
        "1. descrizione sistematica del trattamento",
        "valutazione della necessità e proporzionalità",
        "analisi dei rischi per i diritti e le libertà degli interessati",
        "misure di mitigazione",
        "consultazione dpo",
    )
    assert not mancanti, f"DPIA senza gli elementi dell'art. 35(7)/(2) GDPR: {mancanti}"


def test_dpia_matrice_confini():
    """Tool scale (probabilità x gravità, 1-4): <=2 basso, <=4 medio, <=6 alto, >6 molto alto."""
    r = _tool("genera_dpia", **_caso("genera_dpia", "Confini della matrice"))
    got = [(x["descrizione"], x["score"], x["livello_rischio"]) for x in r["matrice_rischi"]]
    assert got == [("r1", 6, "alto"), ("r2", 8, "molto_alto"), ("r3", 2, "basso")]
    assert r["consultazione_preventiva_necessaria"] is True
    assert "8 settimane" in r["testo"] and "6 settimane" in r["testo"]  # art. 36(2)


def test_dpia_rischio_residuo_tiene_conto_delle_misure():
    """Art. 36(1) GDPR and recital 94: prior consultation turns on the risk that REMAINS after
    the controller's measures. The tool computes 'rischio residuo' from the inherent risk only:
    the same DPIA with an effective measure and without any measure must not give the same
    residual risk (case 'Biometria con misura efficace')."""
    caso = _caso("genera_dpia", "Biometria con misura efficace")
    con = _tool("genera_dpia", **caso)
    senza = _tool("genera_dpia", **{**caso, "misure_mitigazione": []})
    assert con["rischio_residuo"] != senza["rischio_residuo"], (
        "rischio residuo identico con e senza la misura di mitigazione "
        f"({con['rischio_residuo']!r}): misure_mitigazione non entra nel calcolo, e la "
        "consultazione preventiva ex art. 36(1) GDPR viene imposta anche con misure efficaci"
    )


def test_dpia_rischio_alto_senza_misure_impone_consultazione():
    """Art. 36(1) GDPR: 'rischio elevato in assenza di misure' -> prior consultation. A single
    risk scored 6 ('alto', the tool's own label for high) with no measure at all is not
    flagged: the tool requires consultation only above 6 ('molto alto')."""
    r = _tool(
        "genera_dpia",
        titolare="Alfa S.r.l.",
        descrizione="Scoring creditizio automatizzato",
        finalita="valutazione del merito creditizio",
        necessita_proporzionalita="necessario",
        rischi=[{"desc": "decisione automatizzata discriminatoria", "probabilita": "media", "gravita": "alta"}],
        misure_mitigazione=[],
    )
    assert r["matrice_rischi"][0]["livello_rischio"] == "alto"
    assert r["consultazione_preventiva_necessaria"] is True, (
        f"rischio 'alto' senza alcuna misura: rischio_residuo={r['rischio_residuo']!r}, "
        "ma l'art. 36(1) GDPR impone la consultazione preventiva per il rischio elevato non attenuato"
    )


# ---------------------------------------------------------------- genera_informativa_cookie
# Art. 122 D.Lgs. 196/2003 (Normattiva); Linee guida cookie del Garante, provv. n. 231 del
# 10 giugno 2021, doc. web 9677876 (GU n. 163 del 9 luglio 2021), read 2026-09-25.

_LINEE_GUIDA_COOKIE = 9677876


def test_cookie_riferimenti_esistono():
    """Art. 122(1) Codice privacy (consent, technical exemption) and doc. web 9677876 exist."""
    _assert_norma(
        "art. 122 D.Lgs. 196/2003",
        "abbia espresso il proprio consenso dopo essere stato informato",
        "nella misura strettamente necessaria al fornitore di un servizio della società dell'informazione",
    )
    titolo, testo = _gpdp_doc(_LINEE_GUIDA_COOKIE)
    assert "linee guida cookie e altri strumenti di tracciamento - 10 giugno 2021" in titolo.lower()
    assert len(testo) > 50_000, "testo delle Linee guida incompleto"
    for p in _casi("genera_informativa_cookie"):
        r = _tool("genera_informativa_cookie", **p.values[0])
        assert "doc. web 9677876" in r["riferimento_normativo"]
        assert "art. 122(1) D.Lgs. 196/2003" in r["testo"]


def test_cookie_solo_tecnici():
    """Art. 122(1): technical cookies need no consent; no analytics/profiling sections."""
    r = _tool("genera_informativa_cookie", **_caso("genera_informativa_cookie", "Solo cookie tecnici"))
    assert r["consenso_richiesto_analytics"] is False
    assert r["consenso_richiesto_profilazione"] is False
    assert "3. COOKIE ANALITICI" not in r["testo"]
    assert "4. COOKIE DI PROFILAZIONE" not in r["testo"]
    assert [c["tipo"] for c in r["tabella_cookie"]] == ["Tecnico"]


def test_cookie_banner_linee_guida_2021():
    """Linee guida 10/06/2021, par. 7.1, point i): the banner MUST warn that closing it with the
    X keeps the default settings (browsing without non-technical cookies).

    Only that warning is a required content of the banner text. That scrolling is never consent
    (par. 6.1) and that the banner is not shown again for at least 6 months after a refusal
    (par. 6.2) bind how the consent mechanism works, not what the banner or the policy must say:
    they are reported by the tool as `note_implementazione_banner` (checked below), not
    required in the text (fase 3 verdicts, three verifiers agree)."""
    _, lg = _gpdp_doc(_LINEE_GUIDA_COOKIE)
    lg = normalizza(lg)
    assert not contiene(
        lg,
        "contraddistinto da una x",
        "il semplice scrolling non è mai idoneo",
        "trascorsi almeno 6 mesi dalla precedente presentazione del banner",
    ), "le Linee guida lette non contengono più le regole attese"
    r = _tool("genera_informativa_cookie", **_caso("genera_informativa_cookie", "Tecnici, analitici e di profilazione"))
    banner = normalizza(r["banner_testo_suggerito"])
    mancanti = contiene(banner, "la x |comando x", "impostazioni di default", "diversi da quelli tecnici")
    assert not mancanti, f"banner non conforme alle Linee guida Garante 10/06/2021, par. 7.1 i): mancano {mancanti}"
    note = normalizza(" ".join(r["note_implementazione_banner"]))
    assert not contiene(note, "scroll", "6 mesi")


def test_cookie_analytics_condizioni_equiparazione():
    """Linee guida 10/06/2021, par. 7.2: third-party analytics are assimilated to technical
    cookies only if minimised (IP masked at least in its fourth component) AND the provider does
    not combine them with other data. The tool makes consent turn on an 'extra-UE' transfer."""
    _, lg = _gpdp_doc(_LINEE_GUIDA_COOKIE)
    assert not contiene(
        normalizza(lg),
        "mascheramento almeno della quarta componente",
        "non dovranno comunque combinare i dati",
    )
    r = _tool("genera_informativa_cookie", **_caso("genera_informativa_cookie", "Tecnici, analitici e di profilazione"))
    testo = normalizza(r["testo"] + "\n" + json.dumps(r["tabella_cookie"], ensure_ascii=False))
    mancanti = contiene(testo, "combin|incroc", "quarta componente|mascheramento|indirizzo ip")
    assert not mancanti, (
        "informativa sui cookie analitici senza le condizioni del par. 7.2 delle Linee guida "
        f"(minimizzazione e divieto di combinazione da parte del fornitore): mancano {mancanti}"
    )
    # Par. 7.2 does not make consent depend on a transfer outside the EU (that is chapter V GDPR).
    assert "extra-ue, è richiesto il consenso" not in testo
    assert "non trasferiti a terzi" not in testo


# ------------------------------------------------------------ genera_informativa_dipendenti
# Art. 13 e 88 GDPR; artt. 2-quaterdecies, 111-bis, 113, 114 D.Lgs. 196/2003; art. 4 L. 300/1970;
# artt. 25, 243, 260, 280 D.Lgs. 81/2008 (Normattiva), read 2026-09-25.


def _comma_itl_art4() -> str:
    """The paragraph of art. 4 L. 300/1970 that provides for the ITL authorisation."""
    commi = _commi(_testo("art. 4 L. 300/1970"))
    con_itl = [n for n, t in commi.items() if "ispettorato nazionale del lavoro" in t]
    assert con_itl, commi
    return con_itl[0]


def test_dipendenti_sezioni_obbligatorie():
    """Case 'Solo sezioni obbligatorie': bases 6(1)(b), 6(1)(c), 9(2)(b), 6(1)(f); rights
    15-18 and 21 with the art. 20 note; complaint to the Garante; no optional section."""
    _assert_norma("art. 9 GDPR", "in materia di diritto del lavoro e della sicurezza sociale")
    _assert_norma("art. 20 GDPR", "il trattamento sia effettuato con mezzi automatizzati")
    r = _tool("genera_informativa_dipendenti", **_caso("genera_informativa_dipendenti", "Solo sezioni obbligatorie"))
    testo = r["testo"]
    for frase in ("art. 6(1)(b) GDPR", "art. 6(1)(c) GDPR", "art. 9(2)(b) GDPR", "art. 6(1)(f) GDPR",
                  "(art. 15 GDPR)", "(art. 16 GDPR)", "(art. 17 GDPR)", "(art. 18 GDPR)", "(art. 21 GDPR)",
                  "portabilità (art. 20)", "mezzi automatizzati", "reclamo al Garante"):
        assert frase in testo, frase
    for sezione in ("VIDEOSORVEGLIANZA\n", "GEOLOCALIZZAZIONE\n", "UTILIZZO DI STRUMENTI AZIENDALI"):
        assert sezione not in testo, sezione


def test_dipendenti_sezioni_opzionali():
    """Case 'Tutte le sezioni opzionali': video, GPS and IT-tools sections plus DPO contacts."""
    r = _tool("genera_informativa_dipendenti", **_caso("genera_informativa_dipendenti", "Tutte le sezioni opzionali"))
    for frase in ("VIDEOSORVEGLIANZA\n", "GEOLOCALIZZAZIONE\n", "UTILIZZO DI STRUMENTI AZIENDALI", "dpo@alfa.it"):
        assert frase in r["testo"], frase
    assert len(r["adempimenti_aggiuntivi"]) == 8  # 2 video + 1 GPS + 1 IT + 4 comuni


@pytest.mark.parametrize("caso", _casi("genera_informativa_dipendenti"))
def test_dipendenti_riferimenti_pertinenti(caso):
    """The employee notice rests on art. 111-bis Codice privacy, which only governs CVs sent
    spontaneously; the pertinent rules are art. 88 GDPR and artt. 113-114 Codice privacy."""
    _assert_norma("art. 111-bis D.Lgs. 196/2003", "curricula spontaneamente trasmessi")
    _assert_norma("art. 88 GDPR", "trattamento dei dati personali dei dipendenti nell'ambito dei rapporti di lavoro")
    _assert_norma("art. 114 D.Lgs. 196/2003", "resta fermo quanto disposto dall'articolo 4 della legge 20 maggio 1970, n. 300")
    r = _tool("genera_informativa_dipendenti", **caso)
    doc = r["testo"] + "\n" + r["riferimento_normativo"]
    problemi = []
    if "111-bis" in doc:
        problemi.append("cita l'art. 111-bis D.Lgs. 196/2003 (curricula spontanei) come fondamento")
    if not re.search(r"art\. 88\b", doc):
        problemi.append("non cita l'art. 88 GDPR (trattamento nei rapporti di lavoro)")
    if not re.search(r"art\. 114\b", doc):
        problemi.append("non cita l'art. 114 D.Lgs. 196/2003 (controllo a distanza)")
    assert not problemi, problemi


def test_dipendenti_autorizzazione_itl_comma_art4():
    """Art. 4 L. 300/1970 as amended by D.Lgs. 151/2015: the agreement AND, failing it, the
    ITL authorisation are both in paragraph 1; paragraph 2 exempts work tools and attendance
    recorders. The notice attributes the ITL authorisation to art. 4(2)."""
    comma = _comma_itl_art4()
    r = _tool("genera_informativa_dipendenti", **_caso("genera_informativa_dipendenti", "Tutte le sezioni opzionali"))
    citati = set(re.findall(r"Ispettorato Territoriale del Lavoro \(art\. 4\((\d+)\) L\. 300/1970\)", r["testo"]))
    assert citati, "il testo non attribuisce più l'autorizzazione ITL a un comma dell'art. 4"
    assert citati == {comma}, (
        f"autorizzazione ITL attribuita all'art. 4({', '.join(sorted(citati))}) L. 300/1970, "
        f"ma nel testo vigente sta al comma {comma}"
    )


def test_dipendenti_conservazione_sorveglianza_sanitaria():
    """The notice keeps health-surveillance data '40 anni (art. 25(1)(a) D.Lgs. 81/2008)'.
    Art. 25(1)(a) is the doctor's cooperation in risk assessment; art. 25(1)(e) makes the
    employer keep the health file 'per almeno dieci anni'; forty years is the INAIL retention
    for carcinogens (art. 243(6)), asbestos (art. 260(4)) and some biological agents (280(4))."""
    commi = _commi(_testo("art. 25 D.Lgs. 81/2008"))
    lettera_a = commi["1"].split(" b) ")[0]
    assert "quarant" not in lettera_a
    assert "per almeno dieci anni" in commi["1"]
    _assert_norma("art. 243 D.Lgs. 81/2008", "dall'inail fino a quarant'anni")
    _assert_norma("art. 260 D.Lgs. 81/2008", "quaranta anni")
    r = _tool("genera_informativa_dipendenti", **_caso("genera_informativa_dipendenti", "Solo sezioni obbligatorie"))
    riga = next(l for l in r["testo"].splitlines() if "sorveglianza sanitaria:" in l)
    assert "40 anni (art. 25(1)(a)" not in r["testo"], (
        f"{riga.strip()!r}: il termine di 40 anni non è nell'art. 25(1)(a) D.Lgs. 81/2008; "
        "per il datore vale l'art. 25(1)(e) (almeno dieci anni), i 40 anni sono dell'INAIL "
        "per cancerogeni/amianto/agenti biologici (artt. 243, 260, 280)"
    )


def test_dipendenti_persone_autorizzate_non_incaricati():
    """D.Lgs. 101/2018 removed the 'incaricato' figure; art. 2-quaterdecies Codice privacy
    speaks of persons designated/authorised under the controller's authority."""
    _assert_norma(
        "art. 2-quaterdecies D.Lgs. 196/2003",
        "per autorizzare al trattamento dei dati personali le persone che operano sotto la propria autorità diretta",
    )
    r = _tool("genera_informativa_dipendenti", **_caso("genera_informativa_dipendenti", "Tutte le sezioni opzionali"))
    obsoleti = [a for a in r["adempimenti_aggiuntivi"] if "incaricato" in a.lower()]
    assert not obsoleti, f"figura dell'incaricato abrogata (art. 2-quaterdecies D.Lgs. 196/2003): {obsoleti}"


# -------------------------------------------------------------- genera_informativa_privacy
# Artt. 12, 13, 14 GDPR (EUR-Lex); recapiti ufficiali del Garante
# (https://www.garanteprivacy.it/home/footer/contatti), read 2026-09-25.

_GARANTE_CONTATTI = "https://www.garanteprivacy.it/home/footer/contatti"


def test_informativa_privacy_norma_vigente():
    """The words of artt. 13(1)(d), 13(2)(e)-(f), 14(1)(f), 14(2)(f) and 12(3) the test relies on."""
    _assert_norma(
        "art. 13 GDPR",
        "i legittimi interessi perseguiti dal titolare del trattamento o da terzi",
        "se la comunicazione di dati personali è un obbligo legale o contrattuale",
        "l'esistenza di un processo decisionale automatizzato",
        "il diritto di proporre reclamo a un'autorità di controllo",
    )
    _assert_norma(
        "art. 14 GDPR",
        "le categorie di dati personali in questione",
        "i mezzi per ottenere una copia di tali dati o il luogo dove sono stati resi disponibili",
        "la fonte da cui hanno origine i dati personali e, se del caso, l'eventualità che i dati provengano da fonti accessibili al pubblico",
    )
    _assert_norma("art. 12 GDPR", "entro un mese dal ricevimento della richiesta", "prorogato di due mesi")


def _mancanti_informativa(testo: str, attesi: dict[str, str]) -> list[str]:
    testo = normalizza(testo)
    return [k for k, frasi in attesi.items() if contiene(testo, frasi)]


def test_informativa_privacy_elementi_art13():
    """Case 'Art. 13 con legittimo interesse, senza DPO': every element of art. 13(1)-(2)
    and the one-month reply of art. 12(3)."""
    r = _tool("genera_informativa_privacy", **_caso("genera_informativa_privacy", "Art. 13 con legittimo interesse, senza DPO"))
    mancanti = _mancanti_informativa(r["testo"], {
        "13(1)(a) identità e contatti del titolare": "privacy@alfa.it",
        "13(1)(c) finalità e base giuridica": "le basi giuridiche del trattamento sono",
        "13(1)(d) legittimi interessi perseguiti": "legittim interess|legittimi interessi perseguiti|interesse legittimo perseguito",
        "13(1)(e) destinatari": "destinatari o categorie di destinatari",
        "13(2)(a) conservazione": "periodo di conservazione",
        "13(2)(b) diritti": "portabilità",
        "13(2)(c) revoca del consenso": "revoca del consenso",
        "13(2)(d) reclamo": "diritto di proporre reclamo",
        "13(2)(e) obbligo o facoltà del conferimento e conseguenze del rifiuto": "conferimento|obbligo legale o contrattuale|mancata comunicazione",
        "13(2)(f) processo decisionale automatizzato": "decisional|profilazione",
        "12(3) risposta entro un mese": "entro un mese",
    })
    assert not mancanti, f"informativa art. 13 GDPR incompleta: mancano {mancanti}"


def test_informativa_privacy_elementi_art14():
    """Case 'Art. 14 con DPO e trasferimento extra UE': art. 14(1)(b),(d),(f) and 14(2)(b),(f);
    the checklist must not claim a source of the data the caller never supplied."""
    r = _tool("genera_informativa_privacy", **_caso("genera_informativa_privacy", "Art. 14 con DPO e trasferimento extra UE"))
    mancanti = _mancanti_informativa(r["testo"], {
        "14(1)(b) contatti del DPO": "dpo@alfa.it",
        "14(1)(d) categorie di dati": "categorie di dati personali trattati",
        "14(1)(f) garanzie del trasferimento": "server negli stati uniti",
        "14(1)(f) mezzi per ottenere copia delle garanzie": "copia",
        "14(2)(b) legittimi interessi perseguiti": "legittimi interessi perseguiti|interesse legittimo perseguito",
        "14(2)(f) fonte dei dati": "fonte dei dati",
    })
    if r["elementi_obbligatori_verificati"].get("fonte_dati") is True:
        mancanti.append(
            "14(2)(f): checklist fonte_dati=True senza che la fonte sia stata indicata "
            "(il testo elenca in alternativa ogni fonte possibile)"
        )
    assert not mancanti, f"informativa art. 14 GDPR incompleta: {mancanti}"


@pytest.mark.parametrize("caso", _casi("genera_informativa_privacy"))
def test_informativa_privacy_numerazione_sezioni(caso):
    """Sections are numbered 1..N without gaps whatever optional section is omitted."""
    r = _tool("genera_informativa_privacy", **caso)
    numeri = [int(n) for n in re.findall(r"(?m)^(\d+)\. [A-ZÀ-Ú]", r["testo"])]
    assert numeri == list(range(1, len(numeri) + 1)), f"numerazione delle sezioni: {numeri}"


def test_informativa_privacy_niente_incaricati():
    """D.Lgs. 101/2018 / art. 2-quaterdecies Codice privacy: no more 'incaricati del trattamento'."""
    r = _tool("genera_informativa_privacy", **_caso("genera_informativa_privacy", "Art. 13 con legittimo interesse, senza DPO"))
    assert "incaricati del trattamento" not in r["testo"], (
        "sezione 4: 'incaricati del trattamento' è una figura abrogata dal D.Lgs. 101/2018 "
        "(persone autorizzate ex art. 2-quaterdecies D.Lgs. 196/2003)"
    )


def test_informativa_privacy_recapiti_garante():
    """The complaint section gives the Garante's address and e-mail: they must be the official
    ones published on garanteprivacy.it (seat Piazza Venezia 11, e-mail protocollo@gpdp.it)."""
    pagina = _pagina(_GARANTE_CONTATTI)
    ufficiali = set(re.findall(r"[a-z0-9._-]+@(?:pec\.)?gpdp\.it", pagina.lower()))
    assert "protocollo@gpdp.it" in ufficiali, ufficiali
    assert "Piazza Venezia" in pagina
    r = _tool("genera_informativa_privacy", **_caso("genera_informativa_privacy", "Art. 13 con legittimo interesse, senza DPO"))
    assert "Piazza Venezia n. 11, 00187 Roma" in r["testo"]
    usate = set(re.findall(r"[a-z0-9._-]+@(?:pec\.)?gpdp\.it", r["testo"].lower()))
    assert usate <= ufficiali, (
        f"e-mail del Garante non ufficiali: {sorted(usate - ufficiali)} (ufficiali: {sorted(ufficiali)})"
    )


# ------------------------------------------------------- genera_informativa_videosorveglianza
# Linee guida EDPB 3/2019 v2.0, par. 7.1 (primo livello); FAQ Garante sulla videosorveglianza
# (https://www.garanteprivacy.it/faq/videosorveglianza, FAQ n. 4); art. 4 L. 300/1970;
# art. 114 D.Lgs. 196/2003; read 2026-09-25.

_FAQ_VIDEO = "https://www.garanteprivacy.it/faq/videosorveglianza"


def test_video_cartello_primo_livello():
    """FAQ Garante n. 4 / EDPB 3/2019 par. 114: the sign carries controller and purposes and
    refers to the full notice saying HOW AND WHERE to find it (plus DPO contacts if any).
    The generated sign ends with a '[recapiti titolare]' placeholder and no such reference."""
    faq = normalizza(_pagina(_FAQ_VIDEO))
    assert not contiene(faq, "indicando come e dove trovarlo", "le indicazioni sul titolare del trattamento e sulla finalità perseguita")
    caso = _casi("genera_informativa_videosorveglianza")[0].values[0]
    r = _tool("genera_informativa_videosorveglianza", **caso)
    breve = normalizza(r["informativa_breve"])
    mancanti = [k for k, v in {
        "titolare": "beta s.p.a.",
        "finalità": "tutela del patrimonio aziendale",
        "conservazione": "72 ore",
        "diritti": "diritti",
        "rinvio all'informativa estesa (dove trovarla)": "informativa completa|informativa estesa|secondo livello|disponibile presso|disponibile sul sito",
        "contatti del DPO se nominato": "dpo|responsabile della protezione dei dati",
    }.items() if contiene(breve, v)]
    assert not mancanti, f"cartello di primo livello senza {mancanti}"


def test_video_informativa_estesa():
    """Full notice: base art. 6(1)(f), EDPB 3/2019, art. 4 L. 300/1970, 72-hour retention,
    no remote monitoring of work, areas filmed."""
    caso = _casi("genera_informativa_videosorveglianza")[0].values[0]
    r = _tool("genera_informativa_videosorveglianza", **caso)
    estesa = normalizza(r["informativa_estesa"])
    assert not contiene(
        estesa, "art. 6(1)(f) gdpr", "linee guida edpb 3/2019", "art. 4(1) l. 300/1970", "72 ore",
        "non è utilizzabile per il controllo a distanza dell'attività lavorativa", "ingresso principale", "magazzino",
    )


def test_video_riferimenti_art4_e_art114():
    """Art. 4 L. 300/1970: the ITL authorisation is in paragraph 1, not 2; art. 114 Codice privacy
    ('Garanzie in materia di controllo a distanza') is the privacy-side anchor and is not cited."""
    comma = _comma_itl_art4()
    _assert_norma("art. 114 D.Lgs. 196/2003", "garanzie in materia di controllo a distanza")
    caso = _casi("genera_informativa_videosorveglianza")[0].values[0]
    r = _tool("genera_informativa_videosorveglianza", **caso)
    doc = _documento(r) + "\n" + "\n".join(r["adempimenti_preventivi"])
    problemi = []
    commi_itl = set(re.findall(r"(?:Ispettorato Territoriale del Lavoro|ITL)[^()]*?\(?(?:ex )?art\. 4\((\d+)\) L\. 300/1970", doc))
    if commi_itl - {comma}:
        problemi.append(f"autorizzazione ITL attribuita all'art. 4({','.join(sorted(commi_itl))}), nel vigente è al comma {comma}")
    if not re.search(r"art\. 114\b", doc):
        problemi.append("manca il richiamo all'art. 114 D.Lgs. 196/2003")
    assert not problemi, problemi


# ------------------------------------------------------------- genera_notifica_data_breach
# Art. 33 GDPR (EUR-Lex); provv. Garante 27 maggio 2021 n. 209, doc. web 9667201 (procedura
# telematica obbligatoria dal 1° luglio 2021 su servizi.gpdp.it), read 2026-09-25.
# Clock pinned to LEGAL_NOW=2026-09-25T12:00:00 by the autouse fixture.

_PROCEDURA_TELEMATICA = 9667201


def test_breach_norma_vigente_art33():
    _assert_norma(
        "art. 33 GDPR",
        "entro 72 ore dal momento in cui ne è venuto a conoscenza",
        "è corredata dei motivi del ritardo",
        "il numero approssimativo di registrazioni dei dati personali in questione",
        "del responsabile della protezione dei dati o di altro punto di contatto",
    )


@pytest.mark.parametrize(
    "descrizione, termine, superata",
    [
        ("Esattamente 72 ore", "25/09/2026 ore 12:00", False),
        ("Un minuto oltre le 72 ore", "25/09/2026 ore 11:59", True),
        ("Senza DPO", "27/09/2026 ore 10:00", False),
    ],
)
def test_breach_termine_72_ore(descrizione, termine, superata):
    """Art. 33(1): 72 hours from awareness; past that, the notice must give the reasons."""
    r = _tool("genera_notifica_data_breach", **_caso("genera_notifica_data_breach", descrizione))
    assert r["termine_scadenza"] == termine
    assert r["scadenza_72h_superata"] is superata
    assert ("motivi del ritardo" in r["testo"]) is superata
    assert f"TERMINE SCADENZA NOTIFICA: {termine}" in r["testo"]


def test_breach_elementi_art33_3_con_dpo():
    """Art. 33(3) a)-d) with a DPO: the four elements are there and flagged present."""
    r = _tool("genera_notifica_data_breach", **_caso("genera_notifica_data_breach", "Esattamente 72 ore"))
    assert r["tutti_elementi_presenti"] is True
    testo = r["testo"]
    # "1.200": the notice is an Italian document, so the thousands separator is the dot (the
    # earlier expectation "1,200" pinned Python's English formatting, a form defect, not a norm).
    for frase in ("Accesso abusivo al CRM", "1.200", "rischio di phishing mirato", "reset delle credenziali", "dpo@alfa.it"):
        assert frase in testo, frase


def test_breach_altro_punto_di_contatto_art33_3_b():
    """Art. 33(3)(b): 'DPO OR ANOTHER contact point'. Without a DPO the tool takes the contact
    point (case 'Senza DPO' plus `punto_contatto`) and marks (b) present; the form has a field
    for it. With neither a DPO nor a contact point (b) is honestly reported missing: the case
    of the plan carries no contact at all, so it is the two-way check, not the bare case, that
    pins the norm (the earlier assertion expected (b) present with no contact data whatsoever)."""
    caso = _caso("genera_notifica_data_breach", "Senza DPO")
    con = _tool("genera_notifica_data_breach", **caso, punto_contatto="Ufficio privacy Alfa, privacy@alfa.it")
    problemi = []
    if con["elementi_art33_3"]["b_contatti_dpo"] is not True or con["tutti_elementi_presenti"] is not True:
        problemi.append("b_contatti_dpo/tutti_elementi_presenti falsi con un altro punto di contatto")
    if "punto di contatto" not in con["testo"].lower() or "privacy@alfa.it" not in con["testo"]:
        problemi.append("nessun campo 'altro punto di contatto' nel modulo")
    assert not problemi, f"art. 33(3)(b) GDPR ammette 'altro punto di contatto': {problemi}"
    senza = _tool("genera_notifica_data_breach", **caso)
    assert senza["elementi_art33_3"]["b_contatti_dpo"] is False
    assert senza["tutti_elementi_presenti"] is False


def test_breach_etichette_e_registrazioni_art33_3():
    """Labels: the DPO/contact point is art. 33(3)(b), not (a); art. 33(3)(a) also asks for the
    categories and approximate number of personal data RECORDS concerned."""
    r = _tool("genera_notifica_data_breach", **_caso("genera_notifica_data_breach", "Esattamente 72 ore"))
    testo = r["testo"]
    problemi = []
    sezione_dpo = next(l for l in testo.splitlines() if l.startswith("1. "))
    if "[art. 33(3)(b)]" not in sezione_dpo:
        problemi.append(f"sezione con i contatti del DPO etichettata {sezione_dpo.strip()!r}")
    if "registrazioni" not in testo.lower():
        problemi.append("manca il numero approssimativo di registrazioni (art. 33(3)(a))")
    assert not problemi, problemi


def test_breach_date_incoerenti():
    """A breach dated AFTER its discovery is impossible: the tool must refuse or warn
    (case 'Violazione datata dopo la scoperta')."""
    r = _fn("genera_notifica_data_breach")(**_caso("genera_notifica_data_breach", "Violazione datata dopo la scoperta"))
    avvisato = bool(r.get("errore")) or bool(re.search(r"incoeren|successiva alla scoperta|precedente la violazione", r.get("testo", ""), re.I))
    assert avvisato, "violazione del 30/09/2026 scoperta il 24/09/2026: modulo generato senza alcun avviso"


def test_breach_canale_telematico():
    """Provv. 27/05/2021 (doc. web 9667201): from 1 July 2021 the notification goes through the
    on-line procedure at servizi.gpdp.it. The portal URL the tool gives must answer."""
    _, provv = _gpdp_doc(_PROCEDURA_TELEMATICA)
    assert not contiene(normalizza(provv), "procedura telematica", "https://servizi.gpdp.it/", "1° luglio 2021")
    r = _tool("genera_notifica_data_breach", **_caso("genera_notifica_data_breach", "Esattamente 72 ore"))
    url = re.search(r"https://servizi\.gpdp\.it/\S+", r["testo"]).group(0)
    risposta = httpx.get(url, headers=_UA, follow_redirects=True, timeout=30)
    assert risposta.status_code == 200, (url, risposta.status_code)


def test_breach_indirizzi_email_intestazione():
    """The heading addresses the notice to e-mail boxes. Since 1/7/2021 the channel is the
    on-line procedure only, and the addresses must be the official ones (protocollo@gpdp.it)."""
    ufficiali = set(re.findall(r"[a-z0-9._-]+@(?:pec\.)?gpdp\.it", _pagina(_GARANTE_CONTATTI).lower()))
    r = _tool("genera_notifica_data_breach", **_caso("genera_notifica_data_breach", "Esattamente 72 ore"))
    usate = set(re.findall(r"[a-z0-9._-]+@(?:pec\.)?gpdp\.it", r["testo"].lower()))
    assert usate <= ufficiali, f"indirizzi non ufficiali nell'intestazione: {sorted(usate - ufficiali)}"


# ------------------------------------------------------------- genera_registro_trattamenti
# Art. 30 GDPR (EUR-Lex), read 2026-09-25.


def test_registro_norma_vigente_art30():
    testo = _assert_norma(
        "art. 30 GDPR",
        "del contitolare del trattamento, del rappresentante del titolare del trattamento e del responsabile della protezione dei dati",
        "non si applicano alle imprese o organizzazioni con meno di 250 dipendenti",
    )
    assert re.search(r"b\)\s*le finalità del trattamento;\s*c\)", testo), "art. 30(1)(b): solo le finalità"


def test_registro_voci_art30_1():
    """Art. 30(1) a)-g): every item of the register, including the contacts of joint controller,
    representative and DPO under letter a)."""
    r = _tool("genera_registro_trattamenti", **_casi("genera_registro_trattamenti")[0].values[0])
    testo = normalizza(r["testo"])
    presenti = {l: f"(art. 30(1)({l}))" in testo for l in "abcdefg"}
    assert all(presenti.values()), presenti
    mancanti = contiene(testo, "contitolare", "rappresentante", "responsabile della protezione dei dati|dpo")
    campi = set(r["scheda"])
    assert not mancanti, (
        f"art. 30(1)(a) GDPR: la scheda non ha i contatti di {mancanti} (campi della scheda: {sorted(campi)})"
    )


def test_registro_base_giuridica_non_e_art30_1_b():
    """Art. 30(1)(b) is 'le finalità del trattamento' only; the legal basis is not an art. 30
    item (it is recommended by the Garante FAQ). The scheda labels it 'art. 30(1)(b)'."""
    r = _tool("genera_registro_trattamenti", **_casi("genera_registro_trattamenti")[0].values[0])
    riga = next(l for l in r["testo"].splitlines() if "BASE GIURIDICA" in l)
    assert "30(1)(b)" not in riga, f"{riga.strip()!r}: la base giuridica non è l'art. 30(1)(b) GDPR"


def test_registro_soglia_250_dipendenti_docstring():
    """Art. 30(5): the exemption covers undertakings with FEWER than 250 employees, so at
    exactly 250 the register is due. The docstring says 'più di 250 dipendenti'."""
    doc = _fn("genera_registro_trattamenti").__doc__ or ""
    assert "più di 250" not in doc, (
        "docstring: 'obbligatorio per titolari con più di 250 dipendenti'; art. 30(5) GDPR esenta "
        "solo chi ha 'meno di 250 dipendenti' (a 250 il registro è dovuto)"
    )

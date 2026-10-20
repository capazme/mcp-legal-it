"""Live smoke gate for the Italgiure tools (Corte di cassazione, SentenzeWeb Solr backend).

Tools under test (src/tools/italgiure.py over src/lib/italgiure/client.py): `leggi_sentenza`,
`cerca_giurisprudenza`, `giurisprudenza_su_norma`, `ultime_pronunce`, `giurisprudenza_articolo`.

What it checks, one real call per plan case on a known document:

* a canary on the source itself: Cass. civ., Sez. Un., 30 dicembre 2021 n. 41994 (fideiussioni
  conformi allo schema ABI, nullita' parziale) is indexed as `snciv2021U41994S` — if it fails the
  source is down or changed and the tool tests below say nothing;
* `leggi_sentenza` returns the estremi, relatore, presidente and text of SS.UU. 41994/2021, reports
  the truncation, and (plan expectation) carries the decisive part of the decision — principio di
  diritto / dispositivo (head AND tail of the long text are kept); it reports 10579/2021 as not found
  (outside the archive window) and, with archivio="tutti" on a number shared by a civil and a
  criminal decision, says which one it returned and that the other exists;
* the archive window the docstring declares (a rolling window of about five years, from 27/09/2021
  at the time of the benchmark) matches the source;
* `cerca_giurisprudenza` finds 41994/2021 with the Sezioni Unite filter, both through
  `solo_sezioni_unite` and through the documented `sezione="SU"`, and its "esplora" mode returns
  facets only, with the same total the source gives;
* `giurisprudenza_su_norma` finds 41994/2021 on art. 1419 c.c., and at least 80% of the results for
  "art. 13 GDPR" (only a handful of decisions exist) actually cite art. 13 of Regulation (EU)
  2016/679;
* `ultime_pronunce` lists the latest Sezioni Unite civili and the latest criminal sentenze in
  descending deposit order, never after today, with an indexing lag under 30 days, prints the type
  of each decision (sent./ord./decr.) and honours the documented `sezione="SU"`;
* `giurisprudenza_articolo` builds the Brocardi-guided report for art. 2043 c.c. (direct references as
  summaries + principle-of-law searches whose results cite art. 2043), and with no Brocardi massime
  (art. 6 D.Lgs. 231/2001) says so and then returns what `giurisprudenza_su_norma` returns on the
  same parameters.

Source facts read on 2026-09-25 through the Solr endpoint the tools use: szdec codes in the index
are 1-7, L, U (Sezioni Unite) and F — there is no "SU" and no "T"; the oldest civil decision is of
17/02/2021 and only 9 civil + 1 criminal decisions predate 27/09/2021 (rolling window, no 2020).

Needs the network, so it is excluded from the default run. Launch it with:

    .venv/bin/pytest tests/unit/test_italgiure_live.py -m live -q -p no:cacheprovider -rfEs
"""

from __future__ import annotations

import asyncio
import re
from datetime import date

import pytest

import src.server  # noqa: F401  (registers every tool module first: avoids a circular import)
from src.lib import _clock
from src.lib.brocardi.client import fetch_brocardi
from src.lib.italgiure.client import SolrSession, build_explore_params
from src.lib.visualex import resolve_atto
from src.tools.italgiure import (
    cerca_giurisprudenza,
    giurisprudenza_articolo,
    giurisprudenza_su_norma,
    leggi_sentenza,
    ultime_pronunce,
)

pytestmark = pytest.mark.live

# Cass. civ., Sez. Un., sentenza 30 dicembre 2021 n. 41994 (Pres. Raimondi, Rel. Valitutti):
# Solr id read from the index on 2026-09-25.
ID_SSUU_41994_2021 = "snciv2021U41994S"
ESTREMI_SSUU_41994_2021 = "Cass. civ., sez. un., n. 41994/2021, dep. 30/12/2021"

_ESTREMI_RE = re.compile(
    r"^#{1,3} Cass\. (?P<ramo>civ|pen)\.,(?P<sez>[^\n]*?) n\. (?P<num>\d+)/(?P<anno>\d{4})"
    r"(?:, dep\. (?P<gg>\d{2})/(?P<mm>\d{2})/(?P<aaaa>\d{4}))?",
    re.M,
)

# Threshold of the benchmark plan (docs/benchmark/piano-benchmark-andreani.json, case
# "Articolo a numero basso, precisione"): at least 8 decisions out of 10 must cite the article of
# the act asked for. The same threshold is applied to giurisprudenza_articolo's principle searches.
_PRECISIONE_MINIMA = 0.8

_GDPR_RE = re.compile(
    r"2016/679|679/2016|679 del 2016|\bGDPR\b|\bRGPD\b|regolamento generale sulla protezione dei dati",
    re.I,
)
# "art. 13", "artt. 12 e 13", "articolo 13", "articoli 13 e 14": the ways a decision names the article.
_ART13_RE = re.compile(r"art(?:icol[oi]|t?\.)\s*(?:\d+[\s,e-]{0,6}){0,3}?\b13\b", re.I)


def _cita_art_13_gdpr(testo: str) -> bool:
    """True when the text cites art. 13 of Reg. (UE) 2016/679.

    A GDPR marker within 250 characters after an article-13 mention, or (decisions that name the
    act once in full and then say "l'articolo 13 del Regolamento") the words "del Regolamento"
    right after it while the decision cites the Regulation elsewhere.
    """
    cita_gdpr = bool(_GDPR_RE.search(testo))
    for m in _ART13_RE.finditer(testo):
        dopo = testo[m.start(): m.start() + 250]
        if _GDPR_RE.search(dopo) or (cita_gdpr and re.search(r"del regolamento", dopo[:60], re.I)):
            return True
    return False


def _fn(tool):
    return getattr(tool, "fn", tool)


def _run(coro):
    return asyncio.run(coro)


def _estremi(testo: str) -> list[dict]:
    """Every decision header ('# Cass. ...' / '### Cass. ...') in a tool output, in order."""
    out = []
    for m in _ESTREMI_RE.finditer(testo):
        d = m.groupdict()
        d["dep"] = date(int(d["aaaa"]), int(d["mm"]), int(d["gg"])) if d["aaaa"] else None
        out.append(d)
    return out


async def _solr(params: dict) -> dict:
    async with SolrSession() as s:
        return await s.query(params)


def _ocr_per_decisioni(decisioni: list[dict]) -> dict[tuple[str, str, str], str]:
    """Full OCR text of the listed decisions, keyed by (ramo, numdec, anno), in one Solr query."""
    if not decisioni:
        return {}
    clausole = " OR ".join(
        f'(kind:"{"snciv" if d["ramo"] == "civ" else "snpen"}" AND numdec:{d["num"]} AND anno:{d["anno"]})'
        for d in decisioni
    )
    data = _run(_solr({"q": clausole, "rows": 50, "fl": "kind,numdec,anno,ocr"}))
    out = {}
    for doc in data["response"]["docs"]:
        ramo = "civ" if doc["kind"] == "snciv" else "pen"
        ocr = doc.get("ocr") or ""
        out[(ramo, doc["numdec"], doc["anno"])] = ocr[0] if isinstance(ocr, list) else ocr
    return out


# ---------------------------------------------------------------------------
# Canary on the source (not on the tool)
# ---------------------------------------------------------------------------


def test_fonte_italgiure_indicizza_ssuu_41994_2021():
    """The Solr backend answers and still holds SS.UU. 41994/2021 with its metadata.

    If this test fails the source is down or changed, and the tool tests below say nothing.
    """
    data = _run(_solr({"q": f"id:{ID_SSUU_41994_2021}", "rows": 1,
                       "fl": "id,numdec,anno,datdep,szdec,tipoprov,kind"}))
    docs = data["response"]["docs"]
    assert len(docs) == 1, data
    doc = docs[0]
    assert doc["numdec"] == "41994" and doc["anno"] == "2021", doc
    assert doc["szdec"] == "U", doc  # Sezioni Unite are coded U in the index, not SU
    assert doc["datdep"] == ["20211230"], doc
    assert doc["tipoprov"] == "Sentenza" and doc["kind"] == "snciv", doc


def test_archivio_dichiarato_dal_docstring_esiste_nella_fonte():
    """The docstring of cerca_giurisprudenza declares the rolling window and its start date.

    The public archive is a rolling window: on 2026-09-25 it holds no decision of 2020 and only
    10 decisions deposited before 27/09/2021. The docstring must not declare a year the source does
    not hold ("archivio 2020+" did), and the start date it does declare must exist at the source
    (when the window moves on, this test fails and the docstring has to be refreshed).
    """
    doc = _fn(cerca_giurisprudenza).__doc__ or ""
    assert not re.search(r"archivio \d{4}\+", doc), "il docstring dichiara ancora un anno iniziale fisso"
    assert "finestra mobile" in doc, "il docstring non dichiara che l'archivio e' una finestra mobile"
    m = re.search(r"dal (\d{2})/(\d{2})/(\d{4})", doc)
    assert m, "il docstring non dichiara la data iniziale della finestra"
    inizio = f"{m.group(3)}{m.group(2)}{m.group(1)}"
    tutte = '(kind:"snciv" OR kind:"snpen")'
    prima = _run(_solr({"q": f"{tutte} AND datdep:[* TO {int(inizio) - 1}]", "rows": 0}))["response"]["numFound"]
    # the continuous coverage starts at the declared date (the first deposit on 2026-09-29 is of
    # 29/09/2021, the days before hold only isolated decisions)
    dal = _run(_solr({"q": f"{tutte} AND datdep:[{inizio} TO *]", "rows": 0}))["response"]["numFound"]
    assert dal > 100000, f"la fonte ha solo {dal} decisioni dal {m.group(0)[4:]}: la finestra si e' spostata"
    assert prima < 50, (
        f"la fonte ha {prima} decisioni anteriori al {m.group(0)[4:]}: il docstring dichiara un "
        "inizio piu' recente di quello reale"
    )
    assert _run(_solr({"q": f"{tutte} AND anno:2020", "rows": 0}))["response"]["numFound"] == 0


# ---------------------------------------------------------------------------
# leggi_sentenza
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def sentenza_41994_2021() -> str:
    return _run(_fn(leggi_sentenza)(numero=41994, anno=2021, archivio="civile"))


def test_leggi_sentenza_ssuu_41994_2021_estremi_e_testo(sentenza_41994_2021):
    """Plan case 1: estremi, relatore, presidente, text on the ABI-schema fideiussioni, truncation note."""
    out = sentenza_41994_2021
    assert not out.startswith("**Errore**"), out[:500]
    assert out.startswith(f"# {ESTREMI_SSUU_41994_2021}"), out[:300]
    assert "**Relatore**: VALITUTTI ANTONIO" in out, out[:500]
    assert "**Presidente**: RAIMONDI GUIDO" in out, out[:500]
    assert "## Testo della decisione" in out
    for parola in ("fideiussion", "ABI", "287 del 1990", "Sezioni Unite"):
        assert parola in out, parola
    # The text is 82k characters at the source: the 30000-character cut must be declared.
    assert re.search(r"\[Testo troncato a 30000 caratteri su \d+ totali: [^\]]*da_carattere=12001\]", out), out[-300:]


def test_leggi_sentenza_ssuu_41994_2021_riporta_principio_di_diritto_o_dispositivo(sentenza_41994_2021):
    """Plan case 1, second half: the decisive part of the decision reaches the caller.

    The docstring promises 'testo completo della sentenza con dispositivo'. At the source the
    `ocrdis` field of this decision is empty and the principio di diritto (artt. 2 co. 2 lett. a
    e 3 L. 287/1990, art. 1419 c.c.) sits at the end of the 82k-character OCR text: the 30000-
    character head cut drops it, so the caller gets the parties and the facts but not the holding.
    """
    out = sentenza_41994_2021
    ha_dispositivo = "## Dispositivo" in out
    ha_principio = "principio di diritto" in out and "1419" in out
    assert ha_dispositivo or ha_principio, (
        "leggi_sentenza non restituisce ne' il dispositivo ne' il principio di diritto di "
        "SS.UU. 41994/2021 (testo tagliato ai primi 30000 caratteri, ocrdis vuoto alla fonte)"
    )


def test_leggi_sentenza_10579_2021_fuori_dalla_finestra_dell_archivio():
    """Plan case 2: Cass. civ. III ord. 10579/2021 (dep. 21/04/2021) predates the archive window.

    The source holds no civil decision 10579 of 2021 (it holds 10579 of 2022-2026); the tool must say
    'non trovata' — not return another decision and not report the source as down.
    """
    fonte = _run(_solr({"q": 'kind:"snciv" AND numdec:10579 AND anno:2021', "rows": 0}))
    assert fonte["response"]["numFound"] == 0, "la fonte ora indicizza 10579/2021: aggiornare il caso"
    out = _run(_fn(leggi_sentenza)(numero=10579, anno=2021, sezione="3", archivio="civile"))
    assert "non trovata" in out, out[:500]
    assert not out.startswith("**Errore**"), out[:500]
    assert "# Cass." not in out, out[:500]


def test_leggi_sentenza_archivio_tutti_con_numero_omonimo_dichiara_il_ramo():
    """Plan case 3 (on 10579/2022, since 10579/2021 is outside the window).

    Number 10579 of 2022 exists both as Cass. civ. sez. V (dep. 01/04/2022) and as Cass. pen.
    sez. VII (dep. 24/03/2022). With archivio="tutti" the tool returns one of them without flagging
    the other: the header must at least say which branch it is, so the caller can tell.
    """
    fonte = _run(_solr({"q": '(kind:"snciv" OR kind:"snpen") AND numdec:10579 AND anno:2022',
                        "rows": 5, "fl": "kind"}))
    assert {d["kind"] for d in fonte["response"]["docs"]} == {"snciv", "snpen"}, fonte
    out = _run(_fn(leggi_sentenza)(numero=10579, anno=2022, archivio="tutti"))
    estremi = _estremi(out)
    assert estremi, out[:500]
    assert estremi[0]["num"] == "10579" and estremi[0]["anno"] == "2022", estremi[0]
    assert estremi[0]["ramo"] in ("civ", "pen"), estremi[0]


# ---------------------------------------------------------------------------
# cerca_giurisprudenza
# ---------------------------------------------------------------------------


def test_cerca_giurisprudenza_ssuu_fideiussioni_abi():
    """Plan case 1: the Sezioni Unite filter finds 41994/2021, without relaxation."""
    out = _run(_fn(cerca_giurisprudenza)(
        query="fideiussione schema ABI nullità", archivio="civile",
        solo_sezioni_unite=True, anno_da=2021, anno_a=2021,
    ))
    assert not out.startswith("**Errore**"), out[:500]
    assert f"### {ESTREMI_SSUU_41994_2021}" in out, out[:1500]
    assert "Rilassamento automatico" not in out, out[:500]


def test_cerca_giurisprudenza_sezione_su_come_da_docstring():
    """Plan case 2: the docstring says sezione='SU' for the Sezioni Unite.

    The index codes them 'U' (facet szdec on 2026-09-25: 1-7, L, U, F): fq szdec:SU matches nothing,
    every relaxation step keeps the filter, and the caller gets 'Nessuna decisione trovata'.
    Same for 'T' (tributaria), which in the index is civil section 5.
    """
    out = _run(_fn(cerca_giurisprudenza)(
        query="fideiussione schema ABI nullità", archivio="civile",
        sezione="SU", anno_da=2021, anno_a=2021,
    ))
    assert "41994/2021" in out, (
        "sezione='SU' (codice documentato) non trova SS.UU. 41994/2021: l'indice usa 'U'. "
        + out[:400]
    )


def test_cerca_giurisprudenza_modalita_esplora():
    """Plan case 3: 'esplora' returns the distribution only, with the total the source gives."""
    query = "danno parentale tabella punti"
    out = _run(_fn(cerca_giurisprudenza)(query=query, archivio="civile", modalita="esplora"))
    assert out.startswith("**Esplorazione**"), out[:300]
    assert "### Cass." not in out and "# Cass." not in out, out[:500]
    for etichetta in ("**Sezione**", "**Anno**", "**Tipo**"):
        assert etichetta in out, etichetta
    m = re.search(r"— (\d+) decisioni trovate", out)
    assert m, out[:300]
    fonte = _run(_solr(build_explore_params(query, archivio="civile")))
    assert int(m.group(1)) == fonte["response"]["numFound"], (m.group(1), fonte["response"]["numFound"])


# ---------------------------------------------------------------------------
# giurisprudenza_su_norma
# ---------------------------------------------------------------------------


def test_giurisprudenza_su_norma_art_1419_cc_ssuu_2021():
    """Plan case 1: SS.UU. 41994/2021 cites art. 1419 cod. civ. and is found."""
    out = _run(_fn(giurisprudenza_su_norma)(
        riferimento="art. 1419 c.c.", archivio="civile", solo_sezioni_unite=True,
        anno_da=2021, anno_a=2021, max_risultati=20,
    ))
    assert not out.startswith("**Errore**"), out[:500]
    assert f"### {ESTREMI_SSUU_41994_2021}" in out, out[:1500]


def test_giurisprudenza_su_norma_art_13_gdpr_precisione():
    """Plan case 2: the results for "art. 13 GDPR" are decisions that cite art. 13 of Reg. (UE) 2016/679.

    Before the fix build_norma_variants ORed the bare "art. 13" / "articolo 13" with the qualified
    form and the bare variant dominated: on 2026-09-25 the tool reported 12920 civil decisions of
    2022 and the first 10 all cited art. 13 d.P.R. 115/2002 (contributo unificato). The article is
    now tied to the act by a proximity phrase ("art. 13 2016/679"~15).

    The plan asks for 8 pertinent decisions out of 10. The source cannot supply ten: civil
    decisions of 2022 citing art. 13 of the Regulation are none (exact phrases 0, article AND GDPR
    marker anywhere 2, neither pertinent), and since 2021 only seven. So the plan year is checked
    for the absence of the inflated total (an honest "nessuna decisione" is a correct answer), and
    the plan's 80% precision is measured on what the range 2021-today returns (6 of 7 on
    2026-09-29; the stray hit is Cass. 12967/2024, a Garante measure under Reg. 2016/679 art. 78).
    """
    fn = _fn(giurisprudenza_su_norma)
    piano = _run(fn(riferimento="art. 13 GDPR", archivio="civile", anno_da=2022, anno_a=2022,
                    max_risultati=10))
    assert not piano.startswith("**Errore**"), piano[:500]
    tot_piano = re.search(r"Trovate (\d+)", piano)
    assert tot_piano is None or int(tot_piano.group(1)) < 200, (
        f"totale gonfiato per il 2022: {tot_piano.group(0)} (varianti nude 'art. 13')"
    )

    out = _run(fn(riferimento="art. 13 GDPR", archivio="civile", anno_da=2021, max_risultati=10))
    assert not out.startswith("**Errore**"), out[:500]
    decisioni = _estremi(out)
    assert 1 <= len(decisioni) <= 10, out[:500]
    totale = re.search(r"Trovate (\d+)", out)
    assert totale and int(totale.group(1)) < 200, out[:300]
    ocr = _ocr_per_decisioni(decisioni)
    pertinenti = []
    for d in decisioni:
        testo = ocr.get((d["ramo"], d["num"], d["anno"]), "")
        pertinenti.append(_cita_art_13_gdpr(testo))
    quota = sum(pertinenti) / len(pertinenti)
    assert quota >= _PRECISIONE_MINIMA, (
        f"'art. 13 GDPR': {sum(pertinenti)}/{len(pertinenti)} decisioni citano l'art. 13 del "
        f"Reg. (UE) 2016/679 ({totale.group(1)} risultati)"
    )


# ---------------------------------------------------------------------------
# ultime_pronunce
# ---------------------------------------------------------------------------


def _ordine_e_date(decisioni: list[dict], oggi: date) -> None:
    date_dep = [d["dep"] for d in decisioni]
    assert all(date_dep), decisioni
    assert date_dep == sorted(date_dep, reverse=True), date_dep
    assert date_dep[0] <= oggi, (date_dep[0], oggi)


def test_ultime_pronunce_sezioni_unite_civili():
    """Plan case 1: five Sezioni Unite civili decisions, newest deposit first, none after today."""
    out = _run(_fn(ultime_pronunce)(archivio="civile", solo_sezioni_unite=True, max_risultati=5))
    assert out.startswith("**Ultime pronunce della Cassazione**"), out[:300]
    decisioni = _estremi(out)
    assert len(decisioni) == 5, out[:800]
    assert all(d["ramo"] == "civ" and d["sez"].strip(" ,") == "sez. un." for d in decisioni), decisioni
    _ordine_e_date(decisioni, _clock.today())


def test_ultime_pronunce_sentenze_penali():
    """Plan case 2: three criminal sentenze, newest first; indexing lag under 30 days.

    The listing prints the type of each decision (sent.), which is also checked at the source.
    On 2026-09-25 the newest deposit returned was 17/09/2026 (lag 8 days).
    """
    out = _run(_fn(ultime_pronunce)(archivio="penale", tipo_provvedimento="sentenza", max_risultati=3))
    decisioni = _estremi(out)
    assert len(decisioni) == 3, out[:800]
    assert out.count("(sent.)") == 3, out[:800]
    assert all(d["ramo"] == "pen" for d in decisioni), decisioni
    oggi = _clock.today()
    _ordine_e_date(decisioni, oggi)
    assert (oggi - decisioni[0]["dep"]).days <= 30, decisioni[0]
    clausole = " OR ".join(f"(numdec:{d['num']} AND anno:{d['anno']})" for d in decisioni)
    fonte = _run(_solr({"q": f'kind:"snpen" AND ({clausole})', "rows": 10, "fl": "numdec,tipoprov"}))
    assert fonte["response"]["docs"], fonte
    assert {d["tipoprov"] for d in fonte["response"]["docs"]} == {"Sentenza"}, fonte


def test_ultime_pronunce_sezione_su_come_da_docstring():
    """The docstring documents sezione='SU' for the Sezioni Unite; the index codes them 'U'."""
    out = _run(_fn(ultime_pronunce)(archivio="civile", sezione="SU", max_risultati=3))
    assert "sez. un." in out, (
        "sezione='SU' (codice documentato) non restituisce decisioni: l'indice usa 'U'. " + out[:300]
    )


# ---------------------------------------------------------------------------
# giurisprudenza_articolo
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def articolo_2043() -> str:
    return _run(_fn(giurisprudenza_articolo)(
        riferimento="art. 2043 c.c.", archivio="civile", anno_da=2020, max_risultati=5,
    ))


def test_giurisprudenza_articolo_2043_cc_struttura(articolo_2043):
    """Plan case 1: header, Brocardi count, direct references read on Italgiure, principle searches."""
    out = articolo_2043
    assert out.startswith("## Giurisprudenza sull'art. 2043 c.c."), out[:300]
    m = re.search(r"\*\*Fonte Brocardi\*\*: (\d+) massime", out)
    assert m and int(m.group(1)) > 0, out[:500]
    assert "### Sentenze con riferimento diretto" in out, out[:1500]
    assert "### Sentenze per principio di diritto" in out, out[-1500:]
    diretti = out.split("### Sentenze con riferimento diretto", 1)[1].split(
        "### Sentenze per principio di diritto", 1)[0]
    heads = [d for d in _estremi(diretti) if d["ramo"] == "civ"]
    assert heads, diretti[:800]
    # Direct references are summaries (estremi + materia): the full text of three decisions made the
    # report 37613 characters long. The text is one leggi_sentenza call away.
    assert "## Testo della decisione" not in diretti
    assert "**Materia**" in diretti
    assert len(out) < 25000, len(out)


def test_giurisprudenza_articolo_2043_cc_pertinenza_principio_di_diritto(articolo_2043):
    """Plan note (c): the first 300 characters of a massima used as a query give pertinent results.

    Measured as for giurisprudenza_su_norma: a decision listed under 'Sentenze per principio di
    diritto' is pertinent when its text cites art. 2043. On 2026-09-25 4 of 10 did: the massima on
    the capo-nave was auto-refined 'solo nel dispositivo' (299 -> 3) into three sez. II decisions on
    administrative sanctions (d.lgs. 72/2015, favor rei), unrelated to art. 2043.
    """
    principio = articolo_2043.split("### Sentenze per principio di diritto", 1)[1]
    decisioni = _estremi(principio)
    assert decisioni, principio[:800]
    ocr = _ocr_per_decisioni(decisioni)
    cita = [bool(re.search(r"\b2043\b", ocr.get((d["ramo"], d["num"], d["anno"]), ""))) for d in decisioni]
    quota = sum(cita) / len(cita)
    fuori = [f"{d['num']}/{d['anno']}" for d, c in zip(decisioni, cita) if not c]
    assert quota >= _PRECISIONE_MINIMA, (
        f"{sum(cita)}/{len(cita)} decisioni della sezione 'principio di diritto' citano l'art. 2043; "
        f"non lo citano: {fuori}"
    )


def test_giurisprudenza_articolo_senza_massime_coincide_con_su_norma():
    """Plan case 2: with no Brocardi massime the tool falls back to giurisprudenza_su_norma.

    On 2026-09-25 Brocardi has no massime for art. 6 D.Lgs. 231/2001; the output must then be the
    same as giurisprudenza_su_norma on the same parameters, preceded by a line that says Brocardi had
    no massime (the fallback used to be silent).
    """
    atto = resolve_atto("D.Lgs. 231/2001")
    assert atto, "resolve_atto non riconosce piu' il D.Lgs. 231/2001"
    broc = _run(fetch_brocardi(atto["tipo_atto"], "6", atto.get("numero_atto", ""), atto.get("data", "")))
    if broc.massime:
        pytest.skip(f"Brocardi ora ha {len(broc.massime)} massime per l'art. 6 D.Lgs. 231/2001")
    parametri = dict(riferimento="art. 6 D.Lgs. 231/2001", archivio="penale", anno_da=2021)
    out = _run(_fn(giurisprudenza_articolo)(**parametri))
    atteso = _run(_fn(giurisprudenza_su_norma)(**parametri))
    assert out.startswith("*Brocardi: nessuna massima disponibile per art. 6 D.Lgs. 231/2001"), out[:300]
    assert out.endswith(atteso), (out[-400:], atteso[:400])
    assert atteso.startswith("**Trovate"), atteso[:300]

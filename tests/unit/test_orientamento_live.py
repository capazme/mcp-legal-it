"""Smoke live of the three orientamento tools against Italgiure (SentenzeWeb Solr) and Brocardi.

Sources, all read on 2026-09-25:

- Italgiure SentenzeWeb, the Solr endpoint of the Corte di cassazione
  (www.italgiure.giustizia.it/sncass): the counts, the Sezioni Unite and the
  decisions the maps describe. Every cross-check below is an independent Solr
  query written by hand in this file (never the tool's own query builder).
- Brocardi.it, page of art. 2043 c.c.: the massime used as anchor by
  `mappa_orientamento` (500 `div.sentenza` on 2026-09-25, newest first,
  Cass. civ. n. 31191/2025 at the top).
- Normattiva, art. 15 L. 23 settembre 2025, n. 132 (read with cite_law): the
  limit the tools quote in their docstrings and in the footer of every map.

What it checks, one tool call per plan case:

- `orientamento_su_norma`: art. 1419 c.c., civile, anno_da 2021 (Sezioni Unite
  block with Cass. civ. SS.UU. n. 41994/2021, dep. 30/12/2021; year and section
  counts adding up to the total); art. 13 GDPR, civile, anno_da 2022 (the total
  must not be driven by the bare variant "art. 13", i.e. by the contributo
  unificato formula "art. 13, comma 1-quater, d.P.R. 115/2002").
- `orientamento_su_principio`: "fideiussione omnibus schema ABI nullita'
  parziale", civile, anno_da 2021, with and without sezione "1" (the landmark
  SS.UU. 41994/2021 and the pertinence of the Sezioni Unite shown; the section
  filter narrows the clusters and leaves the SS.UU. block unchanged).
- `mappa_orientamento`: art. 2043 c.c., civile, anno_da 2020 (Brocardi anchor:
  number of massime and first five Cassazione references, each found on Italgiure).
- Cross-cutting: the "segnali testuali" headers count distinct decisions; the
  phrase "discostarsi" is not mostly used in the negated, conformity sense
  ("non vi sono ragioni per discostarsi"); the declared archive horizon
  ("dal ~2020") exists in the archive; the docstrings attribute to art. 15
  L. 132/2025 only what its text says.

A source failure ("non raggiungibile") skips the test instead of failing it:
that is the source being down, not the tool being wrong. A genuine discrepancy
stays a failure.

    .venv/bin/pytest tests/unit/test_orientamento_live.py -m live -q -p no:cacheprovider -rfEs

Excluded from the default run (pyproject sets `-m 'not live'`).
"""

from __future__ import annotations

import asyncio
import re

import httpx
import pytest

import src.server  # noqa: F401  (registers every tool module first: avoids a circular import)
from src.lib.italgiure.client import SolrSession
from src.tools import orientamento as orient_tools
from src.tools.italgiure import _normalize_query
from tests.unit._norme_live import assert_parole, contiene
from tests.unit._norme_live import testo_vigente as _testo_vigente

pytestmark = pytest.mark.live

SOURCE_DOWN = "non raggiungibile"

# Plan cases (docs/benchmark/piano-benchmark-andreani.json).
CASO_1419 = {"riferimento": "art. 1419 c.c.", "archivio": "civile", "anno_da": 2021, "max_risultati": 10}
CASO_13_GDPR = {"riferimento": "art. 13 GDPR", "archivio": "civile", "anno_da": 2022}
PRINCIPIO = "fideiussione omnibus schema ABI nullità parziale"
CASO_ABI = {"principio": PRINCIPIO, "archivio": "civile", "anno_da": 2021}
CASO_ABI_SEZ1 = {**CASO_ABI, "sezione": "1"}
CASO_2043 = {"riferimento": "art. 2043 c.c.", "archivio": "civile", "anno_da": 2020}

# Cass. civ. SS.UU. 30 dicembre 2021, n. 41994 (fideiussione omnibus conforme allo schema
# ABI 2003: nullita' parziale), as indexed by Italgiure: id snciv2021U41994S, datdep 20211230.
SSUU_41994 = "n. 41994/2021, dep. 30/12/2021"

BROCARDI_2043 = "https://www.brocardi.it/codice-civile/libro-quarto/titolo-ix/art2043.html"

# Text variants the tool documents for "art. 1419 c.c." / "art. 2043 c.c." (build_norma_variants),
# written by hand so that the cross-check does not reuse the tool's builder.
VARIANTI_1419 = 'ocr:("art. 1419" OR "articolo 1419" OR "1419 c.c." OR "1419 cod. civ." OR "1419 codice civile")'
VARIANTI_2043 = 'ocr:("art. 2043" OR "articolo 2043" OR "2043 c.c." OR "2043 cod. civ." OR "2043 codice civile")'

CONFLITTO = ("contrasto giurisprudenziale", "difforme orientamento", "discostarsi")
CONFORMITA = ("orientamento consolidato", "in senso conforme")

# Negated uses of "discostarsi", which state that the Court FOLLOWS the settled case law.
DISCOSTARSI_CONFORME = (
    '(ocr:"ragioni per discostarsi" OR ocr:"ragione per discostarsi" OR ocr:"ragioni di discostarsi"'
    ' OR ocr:"ragione di discostarsi" OR ocr:"motivo di discostarsi" OR ocr:"motivi per discostarsi"'
    ' OR ocr:"motivi di discostarsi" OR ocr:"motivo per discostarsi" OR ocr:"non intende discostarsi"'
    ' OR ocr:"non ritiene di discostarsi")'
)

PAROLE_PREDITTIVE = ("probabilit", "prevedibil", "esito probabile", "predizione", "chance")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CACHE: dict[tuple, str] = {}


def _tool(name: str, **kwargs) -> str:
    """Call an orientamento tool once per distinct input (memoised), skip if the source is down."""
    key = (name, tuple(sorted(kwargs.items())))
    if key not in _CACHE:
        tool = getattr(orient_tools, name)
        fn = getattr(tool, "fn", tool)
        _CACHE[key] = asyncio.run(fn(**kwargs))
    out = _CACHE[key]
    if SOURCE_DOWN in out:
        pytest.skip(f"Italgiure non raggiungibile: {out[:200]}")
    return out


def _solr(params: dict) -> dict:
    async def run():
        async with SolrSession() as session:
            return await session.query(params)

    try:
        return asyncio.run(run())
    except (httpx.HTTPError, OSError) as exc:  # the source, not the tool
        pytest.skip(f"Italgiure non raggiungibile: {exc}")


def _count(q: str, fq: list[str] | None = None, **extra) -> int:
    params = {"q": q, "rows": 0, **extra}
    if fq:
        params["fq"] = fq
    return int(_solr(params)["response"]["numFound"])


def _norma_q(varianti: str, anno_da: int, extra: str = "") -> str:
    q = f'(kind:"snciv") AND {varianti} AND anno:[{anno_da} TO *]'
    return f"({q}) AND {extra}" if extra else q


def _principio_params(extra_fq: list[str] | None = None, sezione: str = "") -> dict:
    """Same edismax search the tool documents (qf ocrdis^5 ocr^1, mm 2<75% 5<60%)."""
    fq = ['(kind:"snciv")', "anno:[2021 TO *]"]
    if sezione:
        fq.append(f"szdec:{sezione}")
    fq += extra_fq or []
    return {
        "defType": "edismax", "q": _normalize_query(PRINCIPIO), "qf": "ocrdis^5 ocr^1",
        "mm": "2<75% 5<60%", "fq": fq, "rows": 0,
    }


def _sezioni_markdown(out: str) -> dict[str, str]:
    """Split the map into its '## ' sections."""
    parts = re.split(r"^## ", out, flags=re.M)
    return {p.split("\n", 1)[0].strip(): p for p in parts[1:]}


def _totale(out: str) -> int:
    m = re.search(r"\*\*(\d+) decisioni\*\* negli archivi della Cassazione", out)
    assert m, out[:500]
    return int(m.group(1))


def _ss_uu(out: str) -> tuple[int, list[str]]:
    block = next(v for k, v in _sezioni_markdown(out).items() if k.startswith("Intervento delle Sezioni Unite"))
    m = re.search(r"\*\*(\d+) pronunce delle Sezioni Unite\*\*", block)
    num = int(m.group(1)) if m else 0
    return num, re.findall(r"^- (Cass\. .+)$", block, flags=re.M)


def _cluster(out: str) -> dict[str, int]:
    block = next(v for k, v in _sezioni_markdown(out).items() if k.startswith("Cluster per sezione"))
    return {lab: int(n) for lab, n in re.findall(r"^### (Sezion[ei] [^\n(]+?) \((\d+)\)$", block, flags=re.M)}


def _anni(out: str) -> dict[str, int]:
    block = _sezioni_markdown(out).get("Andamento temporale", "")
    return {a: int(n) for a, n in re.findall(r"(\d{4}) \((\d+)\)", block)}


def _segnali(out: str) -> tuple[int, int, dict[str, int]]:
    block = _sezioni_markdown(out)["Segnali testuali nelle decisioni"]
    conf = int(re.search(r"contrasto/difformità\*\* \((\d+)\)", block).group(1))
    conform = int(re.search(r"consolidato/conforme\*\* \((\d+)\)", block).group(1))
    frasi = {f: int(n) for f, n in re.findall(r"^- _«(.+?)»_: (\d+)$", block, flags=re.M)}
    return conf, conform, frasi


def _estremi(riga: str) -> tuple[str, str, str]:
    """('U', '41994', '2021') from 'Cass. civ., sez. un., n. 41994/2021, dep. 30/12/2021'."""
    m = re.search(r"n\. (\d+)/(\d{4})", riga)
    return ("U" if "sez. un." in riga else "", m.group(1), m.group(2))


def _struttura_comune(out: str, titolo: str) -> None:
    assert out.startswith(f"# Orientamento giurisprudenziale — {titolo}"), out[:200]
    for heading in ("## Intervento delle Sezioni Unite (szdec:U)", "## Cluster per sezione",
                    "## Andamento temporale", "## Segnali testuali nelle decisioni"):
        assert heading in out, heading
    assert "(art. 15, L. 132/2025)" in out
    corpo = out.lower().split("\n---\n")[0]
    assert not [p for p in PAROLE_PREDITTIVE if p in corpo], "parole predittive nel corpo della mappa"


# ---------------------------------------------------------------------------
# Art. 15 L. 132/2025 — the limit quoted by all three tools
# ---------------------------------------------------------------------------


def test_art_15_l_132_2025_riserva_al_magistrato():
    """Art. 15, co. 1, L. 132/2025: decisions on interpretation, facts and measures stay with the judge."""
    assert_parole(
        "art. 15 legge 132/2025",
        "attivita' giudiziaria|attività giudiziaria",
        "sempre riservata al magistrato",
        "interpretazione e sull'applicazione della legge",
        "valutazione dei fatti e delle prove",
    )


def test_docstring_limite_l_132_2025_allineato_al_testo():
    """The docstrings may attribute to art. 15 L. 132/2025 only what its text says.

    Art. 15 reserves to the magistrate every decision when AI is used IN the judicial
    activity; it contains no ban on "giustizia predittiva" and does not address tools
    used by lawyers (their use of AI is governed by art. 13 of the same law).
    """
    testo = _testo_vigente("art. 15 legge 132/2025")
    assert contiene(testo, "predittiv") == ["predittiv"], "art. 15 ora parla di giustizia predittiva"
    tool = orient_tools.orientamento_su_norma
    doc = (getattr(tool, "fn", tool).__doc__ or "").lower()
    assert "vietata la giustizia predittiva" not in doc, (
        "il docstring di orientamento_su_norma attribuisce alla L. 132/2025 un divieto di "
        "'giustizia predittiva' che l'art. 15 non contiene (riserva al magistrato le decisioni "
        "nell'attivita' giudiziaria)"
    )


# ---------------------------------------------------------------------------
# orientamento_su_norma
# ---------------------------------------------------------------------------


def test_orientamento_su_norma_art_1419_cc_sezioni_unite_e_conteggi():
    """Plan case 1: art. 1419 c.c., civile, dal 2021 — SS.UU. 41994/2021 and consistent counts."""
    out = _tool("orientamento_su_norma", **CASO_1419)
    _struttura_comune(out, "art. 1419 c.c.")

    totale = _totale(out)
    assert totale == _count(_norma_q(VARIANTI_1419, 2021)), "totale diverso da Italgiure"

    num_uu, righe_uu = _ss_uu(out)
    assert num_uu == _count(_norma_q(VARIANTI_1419, 2021, "szdec:U")), "totale SS.UU. diverso da Italgiure"
    recenti = _solr({"q": _norma_q(VARIANTI_1419, 2021, "szdec:U"), "rows": 5, "sort": "pd desc",
                     "fl": "numdec,anno"})["response"]["docs"]
    attese = [(d["numdec"], d["anno"]) for d in recenti]
    mostrate = [_estremi(r)[1:] for r in righe_uu]
    assert mostrate == attese, f"SS.UU. mostrate {mostrate} != le cinque piu' recenti su Italgiure {attese}"
    if ("41994", "2021") in attese:
        assert any(SSUU_41994 in r and "sez. un." in r for r in righe_uu), righe_uu

    anni = _anni(out)
    assert sum(anni.values()) == totale, f"somma per anno {sum(anni.values())} != totale {totale}"
    assert min(anni) >= "2021"
    cluster = _cluster(out)
    assert sum(cluster.values()) + num_uu == totale, "sezioni + SS.UU. != totale"


def test_orientamento_su_norma_art_13_gdpr_non_conta_art_13_nudo():
    """Plan case 2: the map of 'art. 13 GDPR' must describe decisions about the GDPR.

    Upper bound: decisions of the same archive and years that mention the GDPR at all
    ("2016/679" or "GDPR"). A total of tens of thousands means the bare variant
    "art. 13" (contributo unificato, art. 13 co. 1-quater d.P.R. 115/2002) drives it.
    """
    out = _tool("orientamento_su_norma", **CASO_13_GDPR)
    totale = _totale(out)
    base = '(kind:"snciv") AND anno:[2022 TO *]'
    gdpr = _count(f'{base} AND (ocr:"2016/679" OR ocr:gdpr)')
    contributo = _count(
        f'{base} AND ocr:("art. 13, comma 1-quater" OR "art. 13 comma 1-quater" OR "articolo 13, comma 1-quater")'
    )
    assert totale <= gdpr, (
        f"orientamento_su_norma('art. 13 GDPR') conta {totale} decisioni, ma solo {gdpr} decisioni "
        f"dello stesso archivio citano il GDPR; {contributo} contengono la formula del contributo "
        f"unificato 'art. 13, comma 1-quater' (varianti nude 'art. 13'/'articolo 13')"
    )


# ---------------------------------------------------------------------------
# orientamento_su_principio
# ---------------------------------------------------------------------------


def test_orientamento_su_principio_ss_uu_include_41994_2021():
    """Plan case 1: the SS.UU. block on schema ABI must show Cass. civ. SS.UU. n. 41994/2021."""
    out = _tool("orientamento_su_principio", **CASO_ABI)
    _struttura_comune(out, PRINCIPIO)
    _, righe_uu = _ss_uu(out)
    assert any(SSUU_41994 in r for r in righe_uu), (
        f"SS.UU. 41994/2021 (fideiussione omnibus, schema ABI) assente dal blocco Sezioni Unite: {righe_uu}"
    )


def test_orientamento_su_principio_ss_uu_pertinenti():
    """Every Sezioni Unite decision shown for the principle must at least mention 'fideiussione'."""
    out = _tool("orientamento_su_principio", **CASO_ABI)
    _, righe_uu = _ss_uu(out)
    assert righe_uu
    estranee = []
    for riga in righe_uu:
        _, num, anno = _estremi(riga)
        q = f'kind:"snciv" AND szdec:U AND numdec:{num} AND anno:{anno}'
        assert _count(q) == 1, f"{riga} non trovata su Italgiure"
        if _count(f"{q} AND ocr:fideiussione") == 0:
            materia = _solr({"q": q, "rows": 1, "fl": "materia"})["response"]["docs"][0].get("materia")
            estranee.append(f"{riga} ({materia})")
    assert not estranee, f"SS.UU. mostrate che non contengono 'fideiussione': {estranee}"


def test_orientamento_su_principio_filtro_sezione():
    """Plan case 2: sezione '1' narrows the clusters to Sezione I; the SS.UU. block is unchanged."""
    out = _tool("orientamento_su_principio", **CASO_ABI_SEZ1)
    _struttura_comune(out, PRINCIPIO)
    totale = _totale(out)
    assert _cluster(out) == {"Sezione I": totale}
    assert totale == int(_solr(_principio_params(sezione="1"))["response"]["numFound"])
    assert sum(_anni(out).values()) == totale
    assert _ss_uu(out) == _ss_uu(_tool("orientamento_su_principio", **CASO_ABI))


# ---------------------------------------------------------------------------
# mappa_orientamento
# ---------------------------------------------------------------------------


def test_mappa_orientamento_art_2043_ancoraggio_brocardi():
    """Plan case: art. 2043 c.c. — Brocardi anchor (count and first five Cassazione refs) + map."""
    out = _tool("mappa_orientamento", **CASO_2043)
    assert out.startswith("# Orientamento giurisprudenziale — art. 2043 c.c.")
    assert "## Ancoraggio Brocardi (massime consolidate)" in out
    m = re.search(r"Brocardi riporta (\d+) massime per art\. 2043 c\.c\.; (\d+) riferimenti Cassazione", out)
    assert m, out[:800]
    anchor = re.findall(r"^- (Cass\. (?:civ|pen)\.) n\. (\d+)/(\d{4})$", out, flags=re.M)
    assert 1 <= len(anchor) <= 5

    try:
        html = httpx.get(BROCARDI_2043, headers={"User-Agent": "Mozilla/5.0"}, timeout=30,
                         follow_redirects=True).text
    except httpx.HTTPError as exc:
        pytest.skip(f"Brocardi non raggiungibile: {exc}")
    from bs4 import BeautifulSoup

    massime = BeautifulSoup(html, "lxml").select("div.sentenza")
    assert int(m.group(1)) == len(massime), f"massime: tool {m.group(1)}, Brocardi {len(massime)}"
    attesi: list[tuple[str, str, str]] = []
    for div in massime:
        mm = re.match(r"\s*(Cass\.\s*(?:civ|pen)\.)[^n]*?n\.\s*(\d+)/(\d{4})", div.get_text(" ", strip=True))
        if mm and (mm.group(2), mm.group(3)) not in {(a[1], a[2]) for a in attesi}:
            attesi.append((mm.group(1), mm.group(2), mm.group(3)))
        if len(attesi) == 5:
            break
    assert anchor == attesi, f"ancoraggio {anchor} != prime cinque massime Cassazione su Brocardi {attesi}"

    for ramo, num, anno in anchor:
        kind = "snpen" if "pen" in ramo else "snciv"
        assert _count(f'kind:"{kind}" AND numdec:{num.zfill(5)} AND anno:{anno}') >= 1, f"{num}/{anno} assente da Italgiure"

    # The orientamento_su_norma map follows the anchor, with the same counts as Italgiure.
    assert _totale(out) == _count(_norma_q(VARIANTI_2043, 2020))
    assert "(art. 15, L. 132/2025)" in out


# ---------------------------------------------------------------------------
# Cross-cutting: textual signals and archive horizon
# ---------------------------------------------------------------------------


def _union(frasi: tuple[str, ...]) -> str:
    return "(" + " OR ".join(f'ocr:"{f}"' for f in frasi) + ")"


@pytest.mark.parametrize("caso", ["orientamento_su_norma", "mappa_orientamento", "orientamento_su_principio"])
def test_segnali_testuali_contano_decisioni_distinte(caso):
    """'Decisioni che SEGNALANO ... (N)': N must be the number of decisions, not a sum of phrase hits."""
    if caso == "orientamento_su_norma":
        out = _tool(caso, **CASO_1419)
        conta = lambda frasi: _count(_norma_q(VARIANTI_1419, 2021, _union(frasi)))  # noqa: E731
    elif caso == "mappa_orientamento":
        out = _tool(caso, **CASO_2043)
        conta = lambda frasi: _count(_norma_q(VARIANTI_2043, 2020, _union(frasi)))  # noqa: E731
    else:
        out = _tool(caso, **CASO_ABI)
        conta = lambda frasi: int(_solr(_principio_params([_union(frasi)]))["response"]["numFound"])  # noqa: E731
    conflitto, conformita, frasi = _segnali(out)
    assert sum(frasi[f] for f in CONFLITTO) == conflitto
    distinte_conflitto, distinte_conformita = conta(CONFLITTO), conta(CONFORMITA)
    assert (conflitto, conformita) == (distinte_conflitto, distinte_conformita), (
        f"{caso}: intestazioni ({conflitto}, {conformita}) = somma dei conteggi per espressione; "
        f"decisioni distinte su Italgiure ({distinte_conflitto}, {distinte_conformita})"
    )


def test_segnale_discostarsi_non_e_prevalentemente_conforme():
    """'discostarsi' is filed under contrasto/difformita': most of its uses must not be negated.

    On art. 1419 c.c. (civile, dal 2021) the decisions using "discostarsi" are compared with
    those using it in the formula "non vi sono ragioni per discostarsi" and variants, which
    signal conformity with the settled case law, i.e. the opposite of the tool's label.
    """
    out = _tool("orientamento_su_norma", **CASO_1419)
    _, _, frasi = _segnali(out)
    tutte = _count(_norma_q(VARIANTI_1419, 2021, 'ocr:"discostarsi"'))
    assert frasi["discostarsi"] == tutte
    conformi = _count(_norma_q(VARIANTI_1419, 2021, DISCOSTARSI_CONFORME))
    assert conformi * 2 < tutte, (
        f"{conformi} delle {tutte} decisioni contate come 'contrasto/difformita'' per 'discostarsi' "
        f"usano la formula negativa ('ragioni per discostarsi' e simili), che segnala conformita'"
    )


def test_orizzonte_archivio_dichiarato():
    """The footer says 'decisioni dal ~2020 in poi': the archive must hold decisions of that year."""
    out = _tool("orientamento_su_norma", **CASO_1419)
    m = re.search(r"Orizzonte archivio Italgiure: decisioni dal ~(\d{4}) in poi", out)
    assert m, "piè di pagina sull'orizzonte dell'archivio assente"
    anno = m.group(1)
    tutte = '(kind:"snciv" OR kind:"snpen")'
    nell_anno = _count(f"{tutte} AND anno:{anno}")
    piu_vecchia = _solr({"q": tutte, "rows": 1, "sort": "pd asc", "fl": "datdep"})["response"]["docs"][0]
    assert nell_anno > 0, (
        f"il piè di pagina dichiara decisioni dal ~{anno}, ma Italgiure non ne contiene del {anno}; "
        f"la piu' vecchia e' depositata il {piu_vecchia.get('datdep')}"
    )

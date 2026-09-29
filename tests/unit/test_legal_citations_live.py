"""Live smoke gate for the norm-retrieval tools of src/tools/legal_citations.py.

Tools under test: `cite_law`, `fetch_law_article`, `fetch_law_annotations`,
`cerca_brocardi`, `fetch_act_index`, `fetch_full_act`, `download_law_pdf`,
`verifica_citazioni` — over Normattiva (Akoma Ntoso export and HTML), CELLAR /
EUR-Lex, Brocardi and Italgiure.

One real call per case, on documents whose identifiers are fixed and public
(reference values read on 2026-09-25):

* art. 2043 c.c. (R.D. 16 marzo 1942 n. 262), art. 190 c.p.c. (abrogated by
  D.Lgs. 10 ottobre 2022 n. 149), art. 24 Cost., L. 7 ottobre 1969 n. 742
  (sospensione feriale: art. 1 in the text amended by D.L. 132/2014, art. 3
  with the reference to art. 92 of the ordinamento giudiziario);
* Regulation (EU) 2016/679: art. 6 and recital 42, Italian text on CELLAR;
* Brocardi pages of art. 2043 c.c. and of art. 6 D.Lgs. 8 giugno 2001 n. 231;
* index of D.Lgs. 231/2001 (codice redazionale 001G0293, GU n. 140 of
  19 June 2001);
* Italgiure: Cass. civ. SS.UU. n. 41994/2021 (dep. 30/12/2021), Cass. pen.
  sez. II n. 41994/2021 (dep. 17/11/2021), Cass. civ. sez. III n. 10579/2021
  (ord. 21/04/2021, tabella a punti del danno parentale: absent from the
  Italgiure index, but cited by Cass. civ. sez. III nn. 10141/2022,
  10901/2024 and 26826/2025, which are in it).

Some tests fail on purpose, because the tool deviates from the source (the
failing message says why). A network failure of the source skips the test
instead: that is the source being down, not the tool being wrong. The on-disk
caches are switched off (`LEGAL_CACHE=off`) so every call reaches the source,
and the PDFs are written to pytest's tmp_path, never to the repository.

    .venv/bin/pytest tests/unit/test_legal_citations_live.py -m live -q -p no:cacheprovider -rfEs

Excluded from the default run (pyproject sets `-m 'not live'`).
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import zlib

import httpx
import pytest

import src.server  # noqa: F401  (registers every tool module first: avoids a circular import)
from src.tools import legal_citations as lc
from tests.unit._norme_live import contiene, normalizza

pytestmark = pytest.mark.live

# Messages a tool returns when the source itself could not be reached.
_NETWORK_MARKERS = (
    "ConnectError", "ConnectTimeout", "ReadTimeout", "RemoteProtocolError",
    "nodename nor servname", "Name or service not known", "Temporary failure in name resolution",
    "non raggiungibile", "All connection attempts failed",
)

# Brocardi page of art. 2043 c.c. (identity: codice civile, libro IV, titolo IX).
BROCARDI_2043 = "https://www.brocardi.it/codice-civile/libro-quarto/titolo-ix/art2043.html"
BROCARDI_231_ART6 = (
    "https://www.brocardi.it/responsabilita-amministrativa-persone-giuridiche/capo-i/sezione-i/art6.html"
)

# First year of the Italgiure civil archive as it stood on 2026-09-25: a faceted query on
# kind:"snciv" returned only anno 2021-2026 (2021: 16,176 decisions, the oldest deposited
# 17/02/2021; full years hold 35-38k). The archive is a moving window, not "from 2020".
ITALGIURE_PRIMO_ANNO = 2021


@pytest.fixture(autouse=True)
def _no_disk_cache(monkeypatch):
    """Every call reaches the source: no AKN / Brocardi answer served from ~/.cache."""
    monkeypatch.setenv("LEGAL_CACHE", "off")


def _fn(tool):
    return getattr(tool, "fn", tool)


_CALLS: dict[tuple, str] = {}


def _call(tool, **kwargs) -> str:
    """One real call per distinct input for the whole session (some answers feed two tests)."""
    key = (getattr(_fn(tool), "__name__", str(tool)), tuple(sorted(kwargs.items())))
    if key not in _CALLS:
        _CALLS[key] = asyncio.run(_fn(tool)(**kwargs))
    out = _CALLS[key]
    _skip_if_source_down(out)
    return out


def _skip_if_source_down(out: str) -> None:
    for marker in _NETWORK_MARKERS:
        if marker in out:
            pytest.skip(f"fonte non raggiungibile: {out[:300]}")


# ---------------------------------------------------------------------------
# cite_law
# ---------------------------------------------------------------------------


def test_cite_law_art_2043_cc_normattiva():
    """art. 2043 c.c.: text of the article on Normattiva, URN of the codice civile (allegato 2)."""
    out = _call(lc.cite_law, reference="art. 2043 c.c.")
    assert "**Fonte**: Normattiva" in out, out[:500]
    assert (
        "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:regio.decreto:1942-03-16;262:2~art2043" in out
    ), out[:500]
    assert not contiene(
        out,
        "Qualunque fatto doloso o colposo, che cagiona ad altri un danno ingiusto, obbliga colui che ha "
        "commesso il fatto a risarcire il danno.",
    ), out[:800]


def test_cite_law_legge_742_1969_json_testo_vigente():
    """art. 1 L. 742/1969 cited with the year only: vigente text (1°-31 agosto, D.L. 132/2014)."""
    payload = json.loads(_call(lc.cite_law, reference="art. 1 L. 742/1969", formato="json"))
    _skip_if_source_down(str(payload.get("errore") or ""))
    assert payload["errore"] is None, payload
    assert payload["atto"]["numero_atto"] == "742", payload["atto"]
    missing = contiene(
        payload["testo"],
        "sospeso di diritto dal 1° al 31 agosto di ciascun anno",
        # The Akoma Ntoso export writes the grave accent of old acts as "e'" (as the Gazzetta does).
        "l'inizio stesso è differito alla fine di detto periodo|l'inizio stesso e' differito alla fine di detto periodo",
    )
    assert not missing, (missing, payload["testo"][:600])


def test_cite_law_legge_742_1969_json_urn_ufficiale():
    """The `urn` field is the official Normattiva URN: L. 7 ottobre 1969 n. 742 -> 1969-10-07.

    Cited with the year only, the resolver builds the date as 1969-01-01 and exposes it as the
    act's URN (and in `url`). Normattiva happens to tolerate it, but the URN is not the one of
    the act (urn:nir:stato:legge:1969-10-07;742).
    """
    payload = json.loads(_call(lc.cite_law, reference="art. 1 L. 742/1969", formato="json"))
    _skip_if_source_down(str(payload.get("errore") or ""))
    assert payload["urn"] == "urn:nir:stato:legge:1969-10-07;742~art1", (
        f"URN esposto {payload['urn']!r}, data atto {payload['atto']['data']!r}"
    )


def test_cite_law_art_190_cpc_abrogato():
    """art. 190 c.p.c. (abrogated by D.Lgs. 149/2022): never the old 60/80-day scheme as vigente."""
    payload = json.loads(_call(lc.cite_law, reference="art. 190 c.p.c.", formato="json"))
    _skip_if_source_down(str(payload.get("errore") or ""))
    testo = normalizza(payload["testo"])
    assert payload["errore"] is None, payload
    assert "abrogato" in testo, testo[:400]
    assert "149" in testo, testo[:400]
    for vecchio in ("sessanta", "ottanta", "comparse conclusionali"):
        assert vecchio not in testo, (vecchio, testo[:400])


def test_cite_law_considerando_42_gdpr():
    """Recital 42 GDPR: its text, from CELLAR (Italian expression of Regulation 2016/679).

    In the CELLAR XHTML a recital is a two-cell table row, <td><p>(42)</p></td><td><p>text</p></td>
    inside div#rct_42: the extractor returns the first <p> starting with "(42)", i.e. the number
    cell alone.
    """
    out = _call(lc.cite_law, reference="considerando 42 GDPR")
    assert "**Fonte**: Eurlex" in out, out[:300]
    assert not contiene(
        out,
        "Per i trattamenti basati sul consenso dell'interessato, il titolare del trattamento dovrebbe "
        "essere in grado di dimostrare che l'interessato ha acconsentito al trattamento",
    ), f"testo restituito: {out!r}"


# ---------------------------------------------------------------------------
# fetch_law_article
# ---------------------------------------------------------------------------


def test_fetch_law_article_legge_742_data_completa():
    """With the full date the URN is the official one: urn:nir:stato:legge:1969-10-07;742~art1."""
    out = _call(lc.fetch_law_article, act_type="legge", article="1", date="1969-10-07", act_number="742")
    assert "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:legge:1969-10-07;742~art1" in out, out[:400]
    assert not contiene(out, "sospeso di diritto dal 1° al 31 agosto di ciascun anno"), out[:600]


def test_fetch_law_article_gdpr_art_6():
    """art. 6 GDPR via 'regolamento ue' 2016/679: EUR-Lex (CELLAR), heading and bases a)-f)."""
    out = _call(lc.fetch_law_article, act_type="regolamento ue", article="6", date="2016", act_number="679")
    assert "**Fonte**: Eurlex" in out, out[:300]
    missing = contiene(
        out,
        "Articolo 6",
        "Liceità del trattamento",
        "l'interessato ha espresso il consenso",
        "necessario all'esecuzione di un contratto",
        "adempiere un obbligo legale",
        "interessi vitali",
        "interesse pubblico",
        "legittimo interesse",
    )
    assert not missing, (missing, out[:800])
    for lettera in "abcdef":
        assert f"{lettera})" in out, lettera


def test_fetch_law_article_costituzione_art_24():
    """Constitution without date and number: URN urn:nir:stato:costituzione~art24 accepted."""
    out = _call(lc.fetch_law_article, act_type="costituzione", article="24")
    assert "urn:nir:stato:costituzione~art24" in out, out[:300]
    assert not contiene(
        out,
        "Tutti possono agire in giudizio per la tutela dei propri diritti e interessi legittimi.",
        "La difesa e' diritto inviolabile|La difesa è diritto inviolabile",
    ), out[:600]


# ---------------------------------------------------------------------------
# fetch_law_annotations
# ---------------------------------------------------------------------------


def test_fetch_law_annotations_art_2043_scheda():
    """art. 2043 c.c.: the Brocardi page of that article, with position, ratio, spiegazione, massime."""
    out = _call(lc.fetch_law_annotations, act_type="codice civile", article="2043")
    assert f"**Fonte**: Brocardi — {BROCARDI_2043}" in out, out[:300]
    missing = contiene(
        out,
        "LIBRO QUARTO - Delle obbligazioni",
        "Titolo IX - Dei fatti illeciti",
        "Articolo 2043",
        "## Ratio Legis",
        "## Spiegazione",
        "## Massime giurisprudenziali",
    )
    assert not missing, missing


def test_fetch_law_annotations_art_2043_testo_articolo():
    """The '## Testo dell'articolo' section (Brocardi dispositivo) reaches the answer.

    `_extract_dispositivo` looks for <div id="dispositivo">; on 2026-09-25 Brocardi marks the block
    as <div class="corpoDelTesto dispositivo"> (no id), so the section is silently dropped.
    """
    out = _call(lc.fetch_law_annotations, act_type="codice civile", article="2043")
    assert "## Testo dell'articolo" in out, "sezione 'Testo dell'articolo' assente dalla scheda"
    sezione = out.split("## Testo dell'articolo", 1)[1][:1500]
    assert not contiene(sezione, "danno ingiusto", "risarcire"), sezione[:400]


def test_fetch_law_annotations_dlgs_231_art_6_per_identita():
    """art. 6 D.Lgs. 231/2001 (not a code): the Brocardi page of THAT act, never another one."""
    out = _call(
        lc.fetch_law_annotations, act_type="decreto legislativo", article="6", date="2001-06-08", act_number="231"
    )
    assert f"**Fonte**: Brocardi — {BROCARDI_231_ART6}" in out, out[:400]
    missing = contiene(out, "responsabilità amministrativa delle persone giuridiche", "Articolo 6")
    assert not missing, (missing, out[:400])


# ---------------------------------------------------------------------------
# cerca_brocardi
# ---------------------------------------------------------------------------


def _riferimenti(out: str) -> list[tuple[str, int, int]]:
    blocco = out.split("**Riferimenti Cassazione**", 1)[1]
    return [
        (m.group(1), int(m.group(2)), int(m.group(3)))
        for m in re.finditer(r"^- Cass\. (civ|pen)\. n\. (\d+)/(\d{4})$", blocco, re.M)
    ]


def test_cerca_brocardi_art_2043_riferimenti_cassazione():
    """art. 2043 c.c.: same page as fetch_law_annotations, plus the Cassazione references.

    Sample of 5 references (evenly spaced): each one is the header of a massima whose own closing
    citation, "(Cassazione civile|penale, Sez. .., sentenza n. N del <data> YYYY)", has the same
    court, number and year.
    """
    out = _call(lc.cerca_brocardi, reference="art. 2043 c.c.")
    assert f"**Fonte**: Brocardi — {BROCARDI_2043}" in out, out[:300]
    assert "## Massime giurisprudenziali" in out
    refs = _riferimenti(out)
    assert len(refs) >= 50, len(refs)
    campione = refs[:: max(1, len(refs) // 5)][:5]
    for corte, numero, anno in campione:
        m = re.search(
            rf"^- \*\*Cass\. {corte}\. n\. {numero}/{anno}\*\*: .*\((Cassazione (civile|penale))[^()]*?"
            rf"n\.\s*{numero}\b[^()]*?{anno}\)\s*$",
            out,
            re.M,
        )
        assert m, f"riferimento Cass. {corte}. n. {numero}/{anno} senza massima corrispondente"
        assert m.group(2).startswith(corte), (corte, m.group(1))


def test_cerca_brocardi_riferimenti_fuori_archivio_italgiure_segnalati():
    """References offered 'per approfondimento con leggi_sentenza' must be readable there, or say so.

    Italgiure holds decisions from 2021 on (ITALGIURE_PRIMO_ANNO); for art. 2043 c.c. about 200
    of the ~500 references extracted from the massime are older, and the block gives no warning.
    """
    out = _call(lc.cerca_brocardi, reference="art. 2043 c.c.")
    blocco = out.split("**Riferimenti Cassazione**", 1)[1]
    vecchi = [r for r in _riferimenti(out) if r[2] < ITALGIURE_PRIMO_ANNO]
    avvisato = any(w in blocco.lower() for w in ("fuori archivio", "non disponibil", "anterior", "non leggibil"))
    assert not vecchi or avvisato, (
        f"{len(vecchi)} riferimenti anteriori al {ITALGIURE_PRIMO_ANNO} proposti per leggi_sentenza "
        f"senza avvertenza (es. {vecchi[:3]})"
    )


def test_cerca_brocardi_senza_articolo_nessuna_rete(monkeypatch):
    """A reference without an article is refused before any network call."""
    async def _vietato(*a, **k):  # pragma: no cover - must not be reached
        raise AssertionError("fetch_brocardi chiamato per un riferimento senza articolo")

    monkeypatch.setattr(lc, "fetch_brocardi", _vietato)
    out = asyncio.run(_fn(lc.cerca_brocardi)(reference="codice civile"))
    assert out.startswith("**Errore**: specificare un articolo"), out


# ---------------------------------------------------------------------------
# fetch_act_index
# ---------------------------------------------------------------------------


def test_fetch_act_index_dlgs_231_2001():
    """Index of D.Lgs. 231/2001: rubriche of artt. 5 and 6, bis/ter articles, codice redazionale.

    On 2026-09-25 Normattiva lists 110 articles: 1-85 plus 24-bis, 24-ter and 23 articles
    25-bis ... 25-vicies. Codice redazionale 001G0293 (GU Serie Generale n. 140, 19/06/2001).
    """
    out = _call(lc.fetch_act_index, reference="D.Lgs. 231/2001")
    voci = [l[2:] for l in out.splitlines() if re.match(r"^- \d", l)]
    assert len(voci) >= 110, len(voci)
    righe = [normalizza(l) for l in out.splitlines()]
    assert "- 5- responsabilità dell'ente" in righe, out[:600]
    assert "- 6- soggetti in posizione apicale e modelli di organizzazione dell'ente" in righe, out[:800]
    for art in ("24 bis-", "24 ter-", "25 ter-", "25 octies.1-", "85-"):
        assert any(v.startswith(art) for v in voci), art
    assert "*Codice redazionale*: `001G0293`" in out, out[-200:]


def test_fetch_act_index_atto_inventato_nessuna_rete(monkeypatch):
    """An unknown act is refused before any network call, with the 'non riconosciuto' error."""
    async def _vietato(*a, **k):  # pragma: no cover - must not be reached
        raise AssertionError("indice richiesto per un atto non riconosciuto")

    monkeypatch.setattr(lc, "_fetch_act_index_scraper", _vietato)
    out = asyncio.run(_fn(lc.fetch_act_index)(reference="atto inventato 123/2099"))
    assert out.startswith("**Errore**: atto 'atto inventato 123/2099' non riconosciuto"), out


# ---------------------------------------------------------------------------
# fetch_full_act
# ---------------------------------------------------------------------------


def test_fetch_full_act_legge_742_1969_testo():
    """L. 742/1969: whole vigente text (art. 1 on 1-31 agosto, art. 3 with art. 92 ord. giud.)."""
    out = _call(lc.fetch_full_act, reference="L. 742/1969")
    assert "**Fonte**: Normattiva — https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:legge:" in out, out[:300]
    assert re.search(r"\*\*Dimensione\*\*: [\d,]+ caratteri", out), out[:300]
    missing = contiene(
        out,
        "sospeso di diritto dal 1° al 31 agosto di ciascun anno",
        "articolo 92 dell'ordinamento giudiziario",
        "Art. 3",
    )
    assert not missing, missing


def test_fetch_full_act_legge_742_1969_titolo():
    """The heading is the act's title, not the portal banner.

    For short acts the AKN export (24,555 bytes for L. 742/1969) is below `_MIN_XML_BYTES`
    (40,000) and is discarded; the HTML walker then takes the first <h1> of the page, which on
    Normattiva is the screen-reader banner "Normattiva - Il portale della legge vigente".
    """
    out = _call(lc.fetch_full_act, reference="L. 742/1969")
    titolo = out.splitlines()[0]
    assert "742" in titolo and "1969" in titolo, f"titolo: {titolo!r}"


def test_fetch_full_act_atto_ue_rinvia_a_pdf(monkeypatch):
    """An EU act is sent to download_law_pdf with no call to Normattiva."""
    async def _vietato(*a, **k):  # pragma: no cover - must not be reached
        raise AssertionError("Normattiva interrogata per un atto UE")

    monkeypatch.setattr(lc, "fetch_normattiva_full_text", _vietato)
    out = asyncio.run(_fn(lc.fetch_full_act)(reference="GDPR"))
    assert "download_law_pdf" in out, out


# ---------------------------------------------------------------------------
# download_law_pdf
# ---------------------------------------------------------------------------


def _testo_pdf(path: str) -> str:
    """Text drawn in an fpdf2 PDF (content streams are zlib-compressed Tj operators)."""
    data = open(path, "rb").read()
    righe = []
    for m in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", data, re.S):
        try:
            stream = zlib.decompress(m.group(1)).decode("latin-1")
        except zlib.error:
            continue
        # One `(...) Tj` per wrapped line; join with a space so words split by the wrap stay apart.
        for s in re.findall(r"\(((?:\\.|[^\\)])*)\)\s*Tj", stream):
            righe.append(re.sub(r"\\(.)", r"\1", s))
    return " ".join(righe)


def _file_da_risposta(out: str) -> str:
    m = re.search(r"File: `([^`]+)`", out)
    assert m, out
    return m.group(1)


def test_download_law_pdf_gdpr_eurlex(monkeypatch, tmp_path):
    """GDPR: official Italian PDF of CELEX 32016R0679.

    On 2026-09-25 (and again 30 s later) eur-lex.europa.eu/legal-content/IT/TXT/PDF/?uri=CELEX:...
    answers HTTP 202 with an empty body and `x-amzn-waf-action: challenge`: the tool reports
    "EUR-Lex did not return a PDF". The same PDF is served by CELLAR (see the canary below).
    """
    monkeypatch.setattr(lc, "_PDF_OUTPUT_DIR", str(tmp_path))
    out = asyncio.run(_fn(lc.download_law_pdf)(reference="GDPR"))
    _skip_if_source_down(out)
    assert out.startswith("**PDF scaricato**"), out
    assert "CELEX:32016R0679" in out, out
    path = _file_da_risposta(out)
    assert os.path.dirname(path) == str(tmp_path)
    assert open(path, "rb").read(5) == b"%PDF-"
    assert os.path.getsize(path) > 100_000


def test_cellar_espone_pdf_italiano_gdpr():
    """Canary on the source: CELLAR serves the Italian PDF of 32016R0679 by content negotiation.

    `Accept: application/pdf;type=pdfa1a` + `Accept-Language: ita` on
    publications.europa.eu/resource/celex/32016R0679 -> 200, %PDF-1.4, ~1 MB (2026-09-25);
    plain `application/pdf` answers 404 ("does not hold a content datastream of the requested type").
    This is the route that bypasses the EUR-Lex WAF, as the HTML path already does.
    """
    try:
        resp = httpx.get(
            "https://publications.europa.eu/resource/celex/32016R0679",
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/pdf;type=pdfa1a",
                "Accept-Language": "ita",
            },
            timeout=httpx.Timeout(60.0, connect=10.0),
            follow_redirects=True,
        )
    except httpx.HTTPError as exc:
        pytest.skip(f"CELLAR non raggiungibile: {exc}")
    assert resp.status_code == 200, resp.status_code
    assert resp.content[:5] == b"%PDF-"
    assert len(resp.content) > 100_000


def test_download_law_pdf_legge_742_generato(monkeypatch, tmp_path):
    """L. 742/1969: PDF generated from the Normattiva text, declared as not the original."""
    monkeypatch.setattr(lc, "_PDF_OUTPUT_DIR", str(tmp_path))
    out = asyncio.run(_fn(lc.download_law_pdf)(reference="L. 742/1969"))
    _skip_if_source_down(out)
    assert out.startswith("**PDF generato**"), out
    assert "non il PDF originale" in out, out
    assert "Fonte: Normattiva — https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:legge:" in out, out
    path = _file_da_risposta(out)
    assert os.path.dirname(path) == str(tmp_path)
    assert open(path, "rb").read(5) == b"%PDF-"
    testo = _testo_pdf(path)
    missing = contiene(testo, "sospeso di diritto dal 1", "31 agosto di ciascun anno")
    assert not missing, (missing, testo[:500])


# ---------------------------------------------------------------------------
# verifica_citazioni
# ---------------------------------------------------------------------------

_MISTO = "Cass. SS.UU. n. 19499/2008\nCass. civ. sez. III n. 10579/2021\nart. 2043 c.c.\nart. 13 comma 9 GDPR"


def _verifica_json(citazioni: str, archivio: str) -> dict:
    data = json.loads(_call(lc.verifica_citazioni, citazioni=citazioni, archivio=archivio, formato="json"))
    for c in data.get("citazioni", []):
        _skip_if_source_down(c.get("nota") or "")
    return data


def test_verifica_citazioni_elenco_misto():
    """Mixed list: pre-archive decision, norm on Normattiva, misquoted GDPR paragraph."""
    data = _verifica_json(_MISTO, "civile")
    assert data["errore"] is None and data["troncato"] is False, data
    voci = data["citazioni"]
    assert [v["n"] for v in voci] == [1, 2, 3, 4]
    assert [v["tipo"] for v in voci] == ["sentenza", "sentenza", "norma", "norma"]
    assert voci[0]["verdetto"] == "non verificabile", voci[0]
    assert voci[2]["verdetto"] == "verificata" and "Normattiva" in voci[2]["nota"], voci[2]
    # art. 13 GDPR has paragraphs 1-4 only.
    assert voci[3]["verdetto"] == "metadati discordanti", voci[3]


def test_verifica_citazioni_cass_10579_2021_non_e_inesistente():
    """Cass. civ. sez. III n. 10579/2021 exists (ord. 21/04/2021) but is not in the Italgiure index.

    Italgiure's civil archive is a moving window that on 2026-09-25 starts on 17/02/2021 and holds
    only part of 2021; the former fixed `_ITALGIURE_MIN_YEAR = 2020` sent the lookup and the miss
    became "inesistente" (the start is now read from the archive, `_italgiure_archive_start`). Later decisions in the same index cite it ("Cass. n. 10579 del 2021" in
    Cass. civ. sez. III nn. 10141/2022, 10901/2024, 26826/2025). Expected: "verificata" if found,
    otherwise "non verificabile" — never "inesistente".
    """
    voce = _verifica_json(_MISTO, "civile")["citazioni"][1]
    assert voce["verdetto"] in ("verificata", "non verificabile"), voce


def test_verifica_citazioni_sezione_sbagliata_su_ssuu():
    """Cass. sez. I n. 41994/2021 is a Sezioni Unite decision: metadata mismatch on the section."""
    out = _call(lc.verifica_citazioni, citazioni="Cass. sez. I n. 41994/2021", archivio="civile")
    assert "| metadati discordanti |" in out, out
    assert "(SU)" in out, out


def test_verifica_citazioni_decisione_inesistente():
    """Cass. civ. n. 99999/2023: no such decision in a year fully covered by the archive."""
    out = _call(lc.verifica_citazioni, citazioni="Cass. civ. n. 99999/2023", archivio="civile")
    assert "| inesistente |" in out, out


def test_verifica_citazioni_cass_pen_con_archivio_tutti():
    """A correct criminal citation is verified against the criminal decision, not a civil namesake.

    41994/2021 exists in both archives: snpen sez. 2 (dep. 17/11/2021) and snciv SS.UU.
    (dep. 30/12/2021). With archivio "tutti" the tool ignores "pen." in the citation, takes the
    first hit (the civil SS.UU.) and flags the correct "Cass. pen. sez. II" as discordant.
    """
    data = _verifica_json("Cass. pen. sez. II n. 41994/2021", "tutti")
    voce = data["citazioni"][0]
    assert voce["verdetto"] == "verificata", voce

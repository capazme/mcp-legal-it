"""Four ways 2.17.1 served another act's article as the one cited (G-493, from G-440).

- A decree whose main text is an annex (d.lgs. 175/2024, the testo unico della giustizia
  tributaria; R.D. 262/1942, the codice civile): cited by the decree's own number, its
  art. 1 was the annex's art. 1, from the Akoma Ntoso export, unlabelled. The decree has
  an art. 1 of its own («È approvato l'allegato testo unico …»).
- «legge sulle locazioni abitative» was typed as a decreto legislativo: refused as another
  act (L. 9 dicembre 1998, n. 431).
- A «legge» or «r.d.» n. 512 of 1946 got the page of the D.Lgt. 30 marzo 1946, n. 512,
  whose heading type («DECRETO LUOGOTENENZIALE») the check did not know.

Network mocked; every page is a trimmed copy of what Normattiva served
(``tests/fixtures/normattiva``, 11 and 17 Nov 2026).
"""

from pathlib import Path

import httpx
import pytest

from src.lib.visualex import akn_fetch, scraper
from src.lib.visualex.akn_parser import ParsedAct, ParsedPart
from src.lib.visualex.map import resolve_atto
from src.lib.visualex.models import Norma, NormaVisitata
from src.lib.visualex.scraper import AttoNonVerificato, with_full_date

NORMATTIVA = Path(__file__).resolve().parents[1] / "fixtures" / "normattiva"
N2LS = "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:"
_CLIENT_REALE = httpx.AsyncClient


def _pagina(nome: str) -> str:
    return (NORMATTIVA / nome).read_text(encoding="utf-8")


DLGS175_ART1 = _pagina("dlgs175_2024_decreto_art1.html")
DLGS175_ART4 = _pagina("dlgs175_2024_decreto_art4_serve_art1.html")
RD262_ART1 = _pagina("rd262_1942_decreto_art1.html")
RD262_ART3 = _pagina("rd262_1942_decreto_art3_serve_art1.html")
DLGT512 = _pagina("landing_dlgt_512_1946_serve_rdlgs.html")
INTESTAZIONE_DLGT = "DECRETO LUOGOTENENZIALE 30 marzo 1946, n. 512"


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    monkeypatch.setenv("MCP_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.delenv("AKN_DISABLED", raising=False)
    monkeypatch.setattr(scraper, "_full_date_cache", {})
    akn_fetch.clear_akn_cache(disk=True)
    yield
    akn_fetch.clear_akn_cache(disk=True)


def _normattiva(monkeypatch, routes: dict) -> list:
    """The scraper's and the export's httpx clients answer from *routes* (URL suffix -> page);
    any other URL is an error of the test. Returns the URLs asked."""
    chieste: list = []

    async def handler(request):
        url = str(request.url)
        chieste.append(url)
        for suffisso, pagina in routes.items():
            if url.endswith(suffisso):
                return httpx.Response(200, text=pagina)
        raise AssertionError(f"unexpected request: {url}")

    def factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return _CLIENT_REALE(*args, **kwargs)

    monkeypatch.setattr(scraper.httpx, "AsyncClient", factory)
    monkeypatch.setattr(akn_fetch.httpx, "AsyncClient", factory)
    return chieste


def _export(monkeypatch, nome: str, articoli: dict[str, str], *, altre: "dict[str, dict[str, str]] | None" = None):
    """The parsed export of a decree whose main text is the annex *nome* (as the parser builds
    it for d.lgs. 175/2024 and R.D. 262/1942: the decree's own articles are not in it)."""
    parti = {n: ParsedPart(name=n, articles=dict(a), order=list(a)) for n, a in (altre or {}).items()}
    parti[nome] = ParsedPart(name=nome, articles=dict(articoli), order=list(articoli))
    act = ParsedAct(title="atto", articles=dict(articoli), order=list(articoli), structure="component",
                    parts=parti, main_part=nome)

    async def fetch(norma, *a, **k):
        return act

    monkeypatch.setattr(akn_fetch, "fetch_act_akn", fetch)
    return act


TU = {"1": "### Art. 1\n\nAllegato\n\nTESTO UNICO DELLA GIUSTIZIA TRIBUTARIA\n\nArt. 1. Le corti di giustizia tributaria",
      "4": "### Art. 4\n\nArt. 4. I presidenti delle corti di giustizia tributaria"}
CC = {"1": "### Art. 1\n\nCODICE CIVILE\n\nArt. 1. (Capacita' giuridica).",
      "3": "### Art. 3\n\nArt. 3. ((ARTICOLO ABROGATO DALLA L. 8 MARZO 1975, N. 39))"}
DLGS175 = Norma("decreto legislativo", "2024-11-14", "175")
RD262 = Norma("regio decreto", "1942-03-16", "262")


class TestDecretoEAllegato:
    """Cited by the decree's number, the decree's own article; one it does not have comes from
    the annex, labelled with it. A code cited by its name (its URN names the part) is unchanged."""

    async def test_the_decree_s_own_article_1(self, monkeypatch):
        _export(monkeypatch, "Allegato", TU)
        chieste = _normattiva(monkeypatch, {"decreto.legislativo:2024-11-14;175~art1": DLGS175_ART1})
        r = await scraper.fetch_article(NormaVisitata(norma=DLGS175, numero_articolo="1"))
        assert "È approvato l'allegato testo unico" in r["text"] and "TESTO UNICO DELLA GIUSTIZIA" not in r["text"]
        assert not r.get("allegato") and not r.get("error")
        assert chieste == [N2LS + "decreto.legislativo:2024-11-14;175~art1"]

    async def test_an_article_the_decree_lacks_is_the_annex_s_labelled(self, monkeypatch):
        _export(monkeypatch, "Allegato", TU)
        _normattiva(monkeypatch, {"decreto.legislativo:2024-11-14;175~art4": DLGS175_ART4})
        r = await scraper.fetch_article(NormaVisitata(norma=DLGS175, numero_articolo="4"))
        assert "I presidenti delle corti di giustizia tributaria" in r["text"]
        assert r["allegato"] == "Allegato" and r["source"] == "normattiva-akn"

    async def test_neither_in_the_decree_nor_in_the_annex(self, monkeypatch):
        _export(monkeypatch, "Allegato", TU)
        _normattiva(monkeypatch, {"decreto.legislativo:2024-11-14;175~art999": DLGS175_ART4})
        r = await scraper.fetch_article(NormaVisitata(norma=DLGS175, numero_articolo="999"))
        assert r["text"] == "" and r["esito"] == scraper.ARTICLE_NOT_FOUND

    @pytest.mark.parametrize("articolo, pagina, atteso, allegato", [
        ("1", RD262_ART1, "È approvato il testo del Codice civile", None),
        ("3", RD262_ART3, "ARTICOLO ABROGATO DALLA L. 8 MARZO 1975", "CODICE CIVILE"),
    ], ids=["art1-del-decreto", "art3-del-codice"])
    async def test_the_regio_decreto_262_1942(self, monkeypatch, articolo, pagina, atteso, allegato):
        _export(monkeypatch, "CODICE CIVILE", CC, altre={"Disposizioni sulla legge in generale": {"1": "preleggi"}})
        _normattiva(monkeypatch, {f"regio.decreto:1942-03-16;262~art{articolo}": pagina})
        r = await scraper.fetch_article(NormaVisitata(norma=RD262, numero_articolo=articolo))
        assert atteso in r["text"] and r.get("allegato") == allegato

    async def test_the_codice_civile_cited_by_name_reads_the_code(self, monkeypatch):
        """«art. 1 c.c.»: its URN names the code's part (;262:2), the export answers, no page."""
        _export(monkeypatch, "CODICE CIVILE", CC)
        chieste = _normattiva(monkeypatch, {})
        r = await scraper.fetch_article(NormaVisitata(norma=Norma("codice civile"), numero_articolo="1"))
        assert "Capacita' giuridica" in r["text"] and chieste == []


class TestLocazioni:
    def test_the_law_on_housing_leases_is_a_legge(self):
        for nome in ("legge sulle locazioni abitative", "locazioni abitative"):
            atto = resolve_atto(nome)
            assert (atto["tipo_atto"], atto["data"], atto["numero_atto"]) == ("legge", "1998-12-09", "431"), nome


class TestIntestazioniStoriche:
    """«DECRETO LUOGOTENENZIALE», «DECRETO DEL CAPO PROVVISORIO DELLO STATO» and «DECRETO
    LEGISLATIVO DEL CAPO PROVVISORIO DELLO STATO» head real pages (measured on 1923-1950): a
    page headed by one is another act's, never the legge or the r.d. cited."""

    @pytest.mark.parametrize("tipo, kind", [("legge", "legge"), ("regio decreto", "regio.decreto")])
    async def test_by_year_the_dlgt_is_refused(self, monkeypatch, tipo, kind):
        _normattiva(monkeypatch, {f"{kind}:1946-01-01;512": DLGT512})
        with pytest.raises(AttoNonVerificato, match=f"la pagina restituita è «{INTESTAZIONE_DLGT}»"):
            await with_full_date(Norma(tipo, "1946", "512"))

    @pytest.mark.parametrize("kind", ["legge", "regio.decreto"])
    def test_with_the_full_date_the_dlgt_is_refused(self, kind):
        with pytest.raises(AttoNonVerificato, match=f"«{INTESTAZIONE_DLGT}»"):
            scraper.controlla_intestazione(f"{N2LS}{kind}:1946-03-30;512~art1", DLGT512)

    async def test_cite_law_never_serves_the_dlgt(self, monkeypatch):
        from src.tools.legal_citations import _cite_law_impl

        _normattiva(monkeypatch, {"legge:1946-01-01;512": DLGT512})
        testo = await _cite_law_impl("art. 1 legge 512/1946")
        assert f"«{INTESTAZIONE_DLGT}»" in testo and "PROVVEDIMENTO ABROGATO" not in testo

    def test_an_export_entry_kept_by_the_check_blind_to_them_is_not_read(self, monkeypatch, tmp_path):
        """akn_url_params.json never expires: an entry the earlier check marked («intestazione»)
        may hold the D.Lgt.'s export for a «legge 512/1946», and is dropped."""
        import json

        monkeypatch.setattr(akn_fetch, "_url_params", {})
        monkeypatch.setattr(akn_fetch, "_url_params_loaded", False)
        vecchia, nuova = N2LS + "legge:1946-03-30;512", N2LS + "legge:1990-08-07;241"
        (tmp_path / "cache" / "akn_acts").mkdir(parents=True, exist_ok=True)
        (tmp_path / "cache" / "akn_acts" / "akn_url_params.json").write_text(json.dumps({
            vecchia: ["046U0512", "1946-04-30", "intestazione"],
            nuova: ["090G0294", "1990-08-18", akn_fetch._VERIFICATA],
        }), encoding="utf-8")
        assert akn_fetch._get_url_params(vecchia) is None
        assert akn_fetch._get_url_params(nuova) == ("090G0294", "1990-08-18")

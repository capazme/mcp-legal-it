"""``storia_norma``: the MCP rendering of ``api.modifiche_articolo``. Network mocked.

The pages are the copies Normattiva served (``tests/fixtures/normattiva/aggiornamenti``,
see its README): per article, the article page, each version's page and each version's
update table. The tool only renders what the library read; the reading itself is covered
by ``test_api_modifiche_articolo.py``.
"""

import json
import re
from pathlib import Path

import httpx
import pytest
from bs4 import BeautifulSoup

from mcp_legal_it import api
from mcp_legal_it.lib.visualex import act_dates, scraper
from mcp_legal_it.tools.vigenza import _storia_norma_impl

DIR = Path(__file__).resolve().parents[1] / "fixtures" / "normattiva" / "aggiornamenti"

ART_2TER = "art. 2-ter d.lgs. 196/2003"
ART_64BIS = "art. 64-bis d.lgs. 14/2019"
ART_612BIS = "art. 612-bis c.p."
NOTA = "Vigenza non è applicabilità"
TESTATA = "| Versione | In vigore | Modifiche che l'hanno prodotta |"


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    monkeypatch.setenv("MCP_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("LEGAL_TODAY", "2026-10-29")
    monkeypatch.delenv("LEGAL_CACHE", raising=False)
    monkeypatch.setattr(scraper, "_full_date_cache", {})
    act_dates.svuota_memoria()
    api.configura()
    yield
    api.configura()


def _normattiva(insieme: str, chieste: list, eccezioni: dict | None = None):
    """A client factory serving *insieme*'s pages: the article page, ``_v{k}`` and ``_agg_v{k}``.

    *eccezioni* maps a page name (``"dlgs196_art2ter_v2"``) to the text or response served instead.
    """
    eccezioni = eccezioni or {}

    def handler(request):
        url = str(request.url)
        chieste.append(url)
        versione = re.search(r"art\.versione=(\d+)", url)
        if "uri-res/N2Ls" in url:
            nome = insieme
        elif "caricaArticolo" in url:
            nome = f"{insieme}_v{versione.group(1)}"
        elif "vediAggiornamentiAllArticolo" in url:
            nome = f"{insieme}_agg_v{versione.group(1)}"
        else:
            return httpx.Response(404)
        if nome in eccezioni:
            risposta = eccezioni[nome]
            return risposta if isinstance(risposta, httpx.Response) else httpx.Response(200, text=risposta)
        pagina = DIR / f"{nome}.html"
        if not pagina.exists():
            return httpx.Response(404)
        return httpx.Response(200, text=pagina.read_text(encoding="utf-8"))

    def factory(fonte, **kwargs):
        kwargs.pop("verify", None)
        return httpx.AsyncClient(transport=httpx.MockTransport(handler), **kwargs)

    return factory


async def _storia(insieme, riferimento, eccezioni=None, **kwargs):
    chieste: list = []
    with api.configurazione(client_factory=_normattiva(insieme, chieste, eccezioni)):
        return await _storia_norma_impl(riferimento, **kwargs), chieste


def _righe(testo: str) -> list[str]:
    return [r for r in testo.splitlines() if re.match(r"\| (\d+|\?) \|", r)]


class TestTesto:
    async def test_a_decree_law_and_its_conversion(self):
        out, chieste = await _storia("dlgs196_art2ter", ART_2TER)
        assert out.splitlines()[0] == ("**Art. 2-ter decreto legislativo 30/06/2003, n. 196** — 3 versioni, "
                                       "storia completa (ESATTO)")
        assert TESTATA in out and "⚠" not in out
        righe = _righe(out)
        assert len(righe) == 3
        assert righe[0].startswith("| 1 | 19/09/2018 – 08/10/2021 | DECRETO LEGISLATIVO 10 agosto 2018, n. 101 ")
        assert righe[0].endswith(": art. 2, comma 1, lettera f): inserimento |")
        assert righe[1] == ("| 2 | 09/10/2021 – 07/12/2021 | DECRETO-LEGGE 8 ottobre 2021, n. 139 (in G.U. "
                            "08/10/2021, n.241): art. 9, comma 1, lettera a): inserimento comma 1-bis; art. 9, "
                            "comma 1, lettera a): modifica commi 2 e 3 |")
        # Version 3: the decree-law as converted «con modificazioni» and the conversion law, two acts.
        assert righe[2].startswith("| 3 | dal 08/12/2021 | DECRETO-LEGGE 8 ottobre 2021, n. 139 (in G.U. "
                                   "08/10/2021, n.241) convertito con modificazioni dalla L. 3 dicembre 2021, n. 205")
        assert ("art. 9, comma 1, lettera a): modifica commi 1, 1-bis, 2 e 3; art. 9, comma 5: modifica comma 1 · "
                "LEGGE 3 dicembre 2021, n. 205 (in G.U. 07/12/2021, n.291): art. 1, comma 1: conversione |") in righe[2]
        assert out.rstrip().endswith("(regime transitorio).*") and NOTA in out
        assert "decreto.legislativo:2003-06-30;196~art2ter" in out
        assert len(chieste) == 6

    async def test_five_provisions_of_one_act_in_one_version(self):
        out, chieste = await _storia("ccii_art64bis", ART_64BIS)
        assert len(chieste) == 7  # the act cited with the year only: its date first
        assert "— 3 versioni, storia completa (ESATTO)" in out.splitlines()[0]
        righe = _righe(out)
        assert righe[1].startswith("| 2 | 28/09/2024 – 11/08/2026 | DECRETO LEGISLATIVO 13 settembre 2024, n. 136")
        # One act, five provisions: the act is named once.
        assert righe[1].count("DECRETO LEGISLATIVO") == 1 and righe[1].count("; ") == 4
        assert "art. 17, comma 1, lettera e): inserimento comma 9-bis |" in righe[1]
        assert righe[2] == ("| 3 | dal 12/08/2026 | DECRETO LEGISLATIVO 7 agosto 2026, n. 147 (in SO n.30, "
                            "relativo alla G.U. 11/08/2026, n.185): art. 4, comma 1, lettera a): modifica comma 1-bis |")

    async def test_a_code_article_with_five_versions(self):
        out, chieste = await _storia("cp_art612bis", ART_612BIS)
        assert out.splitlines()[0] == "**Art. 612-bis codice penale** — 5 versioni, storia completa (ESATTO)"
        righe = _righe(out)
        assert [r.split(" | ")[1] for r in righe] == [
            "25/02/2009 – 19/08/2013", "20/08/2013 – 15/10/2013",
            "16/10/2013 – 08/08/2019", "09/08/2019 – 16/12/2025", "dal 17/12/2025"]
        assert righe[0].endswith(": art. 7, comma 1: inserimento |") and "n. 11" in righe[0]
        # Two provisions of one decree-law in one version: the act is named once.
        assert righe[2].count("DECRETO-LEGGE") == 1
        assert "art. 1, comma 3, lettera a): modifica comma 2; art. 1, comma 3, lettera b): modifica comma 4" in righe[2]
        assert righe[3].endswith(": art. 9, comma 3: modifica comma 1 |")
        assert righe[4].endswith(": art. 1, comma 1, lettera g): inserimento un comma dopo il terzo |")
        assert "regio.decreto:1930-10-19;1398:1~art612bis" in out and len(chieste) == 10

    async def test_a_closed_window_starting_after_today_is_labelled(self, monkeypatch):
        # Asked on 1 Oct 2021, versions 2 (closed) and 3 (open) of art. 2-ter had not come into force.
        monkeypatch.setenv("LEGAL_TODAY", "2021-10-01")
        out, _ = await _storia("dlgs196_art2ter", ART_2TER)
        assert [r.split(" | ")[1] for r in _righe(out)] == [
            "19/09/2018 – 08/10/2021", "09/10/2021 – 07/12/2021 (non ancora in vigore)",
            "dal 08/12/2021 (non ancora in vigore)"]

    async def test_a_version_not_in_force_yet_is_labelled_and_warned(self):
        out, _ = await _storia("dpr131_art1", "art. 1 d.p.r. 131/1986")
        avvisi = [r for r in out.splitlines() if r.startswith("- ⚠ ")]
        # The API's avvisi, in its order, above the table, with the date as GG/MM/AAAA.
        assert avvisi[0].startswith("- ⚠ la versione 1 non ha un atto")
        assert avvisi[1] == ("- ⚠ la versione 2 entra in vigore il 01/01/2027: non è ancora in vigore "
                             "(Normattiva la mostra già come testo dell'articolo)")
        assert out.index(avvisi[1]) < out.index(TESTATA)
        righe = _righe(out)
        assert righe[0] == "| 1 | 01/07/1986 – 31/12/2026 | — |"
        assert righe[1].startswith("| 2 | dal 01/01/2027 (non ancora in vigore) | DECRETO LEGISLATIVO 1 agosto 2025")
        assert righe[1].endswith(": art. 204, comma 1, lettera f): abrogazione |")

    async def test_an_article_never_amended(self):
        out, chieste = await _storia("cc_art2740", "art. 2740 c.c.")
        assert "— 1 versione, storia completa (ESATTO)" in out.splitlines()[0]
        assert _righe(out) == ["| 1 | dal 19/04/1942 | — |"]
        assert len(chieste) == 1

    async def test_a_version_whose_window_is_not_read(self):
        # Version 2's real page without its «Testo in vigore dal … al …» block: the table is
        # still read, so the row stays, says so and its amendments are INDICATIVO.
        pagina = BeautifulSoup((DIR / "dlgs196_art2ter_v2.html").read_text(encoding="utf-8"), "lxml")
        for blocco in pagina.select("div.vigore"):
            blocco.decompose()
        out, _ = await _storia("dlgs196_art2ter", ART_2TER, {"dlgs196_art2ter_v2": str(pagina)})
        assert out.splitlines()[0].endswith("(INDICATIVO)")
        riga = _righe(out)[1]
        assert riga.startswith("| 2 | finestra non letta | DECRETO-LEGGE 8 ottobre 2021, n. 139")
        assert riga.count("(INDICATIVO)") == 2
        assert _righe(out)[2].startswith("| 3 | dal 08/12/2021 |")

    async def test_the_period_shows_only_its_versions(self):
        out, _ = await _storia("dlgs196_art2ter", ART_2TER, dal="2021-12-01")
        assert "Periodo (entrata in vigore): dal 01/12/2021." in out
        assert [r[:4] for r in _righe(out)] == ["| 3 "]
        out, _ = await _storia("dlgs196_art2ter", ART_2TER, dal="2021-10-09", al="2021-10-09")
        assert "Periodo (entrata in vigore): dal 09/10/2021 al 09/10/2021." in out
        assert [r[:4] for r in _righe(out)] == ["| 2 "]

    async def test_a_period_with_no_version(self):
        out, _ = await _storia("dlgs196_art2ter", ART_2TER, dal="2025-01-01")
        assert "Nessuna versione nel periodo indicato." in out and TESTATA not in out and NOTA in out

    async def test_the_ceiling_says_what_was_left_unread(self):
        out, chieste = await _storia("dlgs196_art13", "art. 13 d.lgs. 196/2003", max_versioni=2)
        assert "— 5 versioni, storia incompleta (INDICATIVO)" in out.splitlines()[0]
        assert ("- ⚠ lette le ultime 2 versioni su 5: per le precedenti (1, 2, 3) alzare max_versioni o "
                "spostare dal più avanti") in out
        # The unread versions are named by the avviso, not listed as empty rows.
        assert [r[:4] for r in _righe(out)] == ["| 4 ", "| 5 "]


class TestJson:
    async def test_json_is_come_dict_of_the_api_result(self):
        out, _ = await _storia("dlgs196_art2ter", ART_2TER, formato="json")
        dati = json.loads(out)
        chieste: list = []
        with api.configurazione(client_factory=_normattiva("dlgs196_art2ter", chieste)):
            atteso = api.come_dict(await api.modifiche_articolo(ART_2TER))
        # The sources differ: the second call reads the versions from the disk cache.
        assert dati.pop("fonti")["fonti"] and atteso.pop("fonti") is not None
        assert dati == atteso
        assert dati["esito"] == "trovato" and dati["completa"] is True and dati["precisione"] == "ESATTO"
        assert [(m["versione"], m["tipo"], m["atto"]["numero_atto"]) for m in dati["modifiche"]] == [
            (1, "inserimento", "101"), (2, "inserimento", "139"), (2, "modifica", "139"), (3, "modifica", "139"),
            (3, "modifica", "139"), (3, "conversione", "205")]
        assert "\\u00" not in out  # ensure_ascii=False, like cite_law

    async def test_json_carries_the_refusal_too(self):
        out, chieste = await _storia("x", "art. 5 legge inventata 1/1900", formato="json")
        dati = json.loads(out)
        assert dati["esito"] == "atto_non_riconosciuto" and dati["versioni"] == [] and chieste == []


class TestRifiuti:
    async def test_an_unknown_act_is_refused_never_guessed(self):
        out, chieste = await _storia("x", "art. 5 legge inventata 1/1900")
        assert out == ("**Errore** (atto_non_riconosciuto): atto 'legge inventata 1/1900' non riconosciuto. "
                       "Prova con il nome completo (es. 'D.Lgs. 196/2003').")
        assert chieste == []

    async def test_a_near_miss_is_suggested_not_resolved(self):
        out, chieste = await _storia("x", "art. 1 codice civilee")
        assert out.startswith("**Errore** (atto_non_riconosciuto)") and "Forse intendevi" in out
        assert chieste == []

    async def test_an_eu_act_is_not_supported(self):
        out, chieste = await _storia("x", "art. 6 GDPR")
        assert out.startswith("**Errore** (non_supportata): ") and chieste == []

    @pytest.mark.parametrize("kwargs, motivo", [
        ({"dal": "2021-13-01"}, "non è un giorno"),
        ({"al": "1/1/2021"}, "atteso AAAA-MM-GG"),
        ({"dal": "2022-01-01", "al": "2021-01-01"}, "è dopo al"),
    ])
    async def test_a_bad_period_is_refused_before_any_request(self, kwargs, motivo):
        out, chieste = await _storia("dlgs196_art2ter", ART_2TER, **kwargs)
        assert out.startswith("**Errore** (riferimento_non_valido): ") and motivo in out and chieste == []

    @pytest.mark.parametrize("valore", [0, -3])
    async def test_a_ceiling_below_one(self, valore):
        out, chieste = await _storia("dlgs196_art2ter", ART_2TER, max_versioni=valore)
        assert out == ("**Errore** (riferimento_non_valido): max_versioni deve essere un intero almeno 1")
        assert chieste == []

    async def test_a_ceiling_below_one_in_json_is_json(self):
        out, chieste = await _storia("dlgs196_art2ter", ART_2TER, max_versioni=0, formato="json")
        dati = json.loads(out)
        assert dati["esito"] == "riferimento_non_valido" and "max_versioni" in dati["errore"] and chieste == []

    async def test_an_article_the_act_does_not_have(self):
        # Normattiva answers art. 99999 c.c. with art. 1 (the copy it served): never its history.
        pagina = (DIR.parent / "cc_n2ls_art99999.html").read_text(encoding="utf-8")
        out, chieste = await _storia("cc_art2", "art. 99999 c.c.", {"cc_art2": pagina})
        assert out.startswith("**Errore** (articolo_non_trovato): ") and "art. 1" in out
        assert TESTATA not in out and len(chieste) == 1

    async def test_a_source_error_and_a_transient_failure(self):
        # No page for the article: Normattiva's 404 is an error of the source, not a missing article.
        out, _ = await _storia("nessuna_copia", ART_2TER)
        assert out.startswith("**Errore** (errore_fonte): Normattiva non raggiungibile")
        out, _ = await _storia("dlgs196_art2ter", ART_2TER, {"dlgs196_art2ter": httpx.Response(503)})
        assert out.startswith("**Errore** (verifica_non_disponibile): ")

    async def test_an_unknown_format(self):
        out, chieste = await _storia("dlgs196_art2ter", ART_2TER, formato="markdown")
        assert out.startswith("**Errore**: formato 'markdown' non valido") and chieste == []


async def test_registered_with_its_tags_and_annotations():
    from fastmcp import Client

    from mcp_legal_it.server import mcp

    async with Client(mcp) as client:
        tools = {t.name: t for t in await client.list_tools()}
    tool = tools["storia_norma"]
    # It writes only the Normattiva caches: a cache-only writer, never destructive.
    assert tool.annotations.readOnlyHint is False and tool.annotations.openWorldHint is True
    assert not tool.annotations.destructiveHint
    assert {"normativa", "vigenza"} <= set((tool.meta or {}).get("fastmcp", {}).get("tags", []))
    assert NOTA in tool.description
    assert list(tool.inputSchema["properties"]) == ["riferimento", "dal", "al", "max_versioni", "formato"]

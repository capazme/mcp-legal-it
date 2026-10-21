"""The AKN parser merged with VisuaLex's: tables, parts and their Normattiva positions, annex vs body.

Fixtures are Normattiva's own exports (caricaAKN, 21/10/2026), some trimmed: the trimmed ones
keep every part of the export, so the parts' positions are the real ones, and empty the text
of the articles no test reads. No network.
"""

import hashlib
import re
from pathlib import Path

import pytest
from lxml import etree

from mcp_legal_it import api
from mcp_legal_it.lib.visualex import akn_fetch, scraper
from mcp_legal_it.lib.visualex.akn_parser import (
    _body_approves_annex,
    _render_table,
    annex_id_of,
    parse_akn,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "akn"


def _load(name: str):
    return parse_akn((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def tariffa():
    return _load("dpr_131_1986_tariffa.xml")


@pytest.fixture(scope="module")
def cpa():
    return _load("dlgs_104_2010_trimmed.xml")


@pytest.fixture(scope="module")
def l654():
    return _load("legge_654_1975.xml")


@pytest.fixture(scope="module")
def appalti():
    return _load("dlgs_36_2023_positions.xml")


@pytest.fixture(scope="module")
def cc():
    return _load("codice_civile.xml")


# ---------------------------------------------------------------------------
# The merge changes no text but the tables'
# ---------------------------------------------------------------------------

def _impronta(act, body: bool) -> str:
    m = hashlib.sha256()
    groups = [(n, p.order, p.articles) for n, p in sorted(act.parts.items()) if n != "Dispositivo"]
    if body:
        groups.append(("<body>", act.order, act.articles))
    for name, order, articles in groups:
        for key in order:
            m.update(f"{name}|{key}|".encode())
            m.update(articles[key].encode())
            m.update(b"\0")
    return m.hexdigest()


# sha256 of every article text the parser before the merge produced (mcp-legal-it 273066a),
# part by part: the merge must give the same bytes on every export without a <table>.
@pytest.mark.parametrize("name,body,expected", [
    ("codice_civile", False, "ca7f007346d371a18b210953e1251a5bdc94ab691451b17a88d7daf5dea3c2f6"),
    ("codice_penale", False, "8040f5ecf8e78d86d5d65660de1026ac99aa248819214a3c63b1ca6d0ce32cf7"),
    ("costituzione", True, "d02eb7e3d2315baa3f9b0e91863aaeb0011538988faaed50c0560df6982edc16"),
    ("dlgs_231_2001", True, "b3439faa01a0d799ab6c92a877476b2b3283b1dcd98d02f16c1966a197b4f5cc"),
    ("legge_241_1990", True, "68a16802629a21b4904bc34b0c65c70406b218b40a1644c7b0fc907462e62ce8"),
    ("legge_742_1969", True, "65f2bdb02bdf5846493a5f782764e1e24f969e2e8df8545ce669155aff3238c8"),
    ("dlgs_36_2023_trimmed", True, "0e3b27470f4abbb660bfe998a61a14647f16d70396fc0a33a0b35332e797dc85"),
    ("dlgs_104_2010_trimmed", False, "997ecd359fbf4ca5307e38613b7c9bccb143f14f83ea0838e1a95fde2bbfbdf1"),
    ("legge_654_1975", False, "716bf64ba6bc9c9d52615db1c84704d5a6384c636bd93ad5ebdb1f0030ea65e4"),
])
def test_texts_without_tables_are_byte_identical(name, body, expected):
    assert _impronta(_load(f"{name}.xml"), body) == expected


# ---------------------------------------------------------------------------
# Tables (Tariffa of d.P.R. 131/1986)
# ---------------------------------------------------------------------------

class TestTables:
    PARTE_I = "Tariffa Parte I Atti soggetti a registrazione in termine fisso"

    def test_the_rates_are_in_the_text(self, tariffa):
        art1 = tariffa.parts[self.PARTE_I].articles["1"]
        for aliquota in ("9 per cento", "2 per cento", "15 per cento", "1,5 per cento"):
            assert f"| {aliquota} |" in art1

    def test_the_first_row_heads_a_markdown_table(self, tariffa):
        lines = tariffa.parts[self.PARTE_I].articles["1"].split("\n")
        start = next(i for i, line in enumerate(lines) if line.startswith("|"))
        assert lines[start - 1] == ""  # a table opens its own block
        assert lines[start].startswith("| 1. Atti traslativi a titolo oneroso")
        assert lines[start + 1] == "| --- | --- |"
        end = max(i for i, line in enumerate(lines) if line.startswith("|"))
        assert lines[end + 1] == ""

    def test_no_cell_is_lost(self, tariffa):
        root = etree.fromstring((FIXTURES / "dpr_131_1986_tariffa.xml").read_bytes())
        texts = "\n".join(t for p in tariffa.parts.values() for t in p.articles.values())
        cells = [" ".join("".join(c.itertext()).split()) for c in root.iter("{*}th", "{*}td")]
        assert len(cells) >= 16
        for cell in cells:
            assert cell.replace("((", "").replace("))", "") in texts

    def test_the_text_around_the_table_is_kept(self, tariffa):
        art1 = tariffa.parts[self.PARTE_I].articles["1"]
        assert art1.index("Art. 1.") < art1.index("| 1. Atti") < art1.index("Note:")

    def test_a_pipe_in_a_cell_is_escaped_and_a_span_keeps_the_grid(self):
        table = etree.fromstring(
            "<table><tr><th colspan='2'>Atto</th><th>Imposta</th></tr>"
            "<tr><td>a|b</td><td>c</td><td>3 per cento</td></tr><tr><td>solo</td></tr></table>")
        assert _render_table(table).split("\n") == [
            "| Atto |  | Imposta |",
            "| --- | --- | --- |",
            "| a\\|b | c | 3 per cento |",
            "| solo |  |  |",
        ]


# ---------------------------------------------------------------------------
# Body vs annexes
# ---------------------------------------------------------------------------

class TestBodyOrAnnex:
    def test_a_law_executing_a_treaty_keeps_its_body(self, l654):
        # Art. 3 of l. 654/1975 is the law's (repealed by d.lgs. 21/2018), never the
        # Convention's art. 3 on apartheid, the 25-article part the old rule preferred.
        assert l654.main_part == "" and l654.structure == "flat"
        assert "ARTICOLO ABROGATO DAL D.LGS. 1 MARZO 2018, N. 21" in l654.article("3")
        assert "apartheid" not in l654.article("3")
        assert l654.abrogati() == ["3"]

    def test_the_convention_stays_reachable_by_position(self, l654):
        convenzione = l654.part_at(2)
        assert convenzione is not None and convenzione.name == "Convenzione"
        assert "apartheid" in l654.article("3", part=":2")

    def test_a_decree_approving_its_code_serves_the_code(self, cpa):
        assert cpa.main_part == "Allegato 1 Codice del processo amministrativo"
        assert "Art. 120" in cpa.article("120")
        dispositivo = cpa.parts["Dispositivo"]
        assert dispositivo.order == ["1", "2"] and dispositivo.position == 0
        assert "E' approvato il codice del processo amministrativo" in cpa.article("1", part="dispositivo")

    def test_the_approving_formula(self, cc, cpa, l654):
        assert _body_approves_annex(cc.parts["Dispositivo"].articles, cc.parts["Dispositivo"].order)
        assert _body_approves_annex(cpa.parts["Dispositivo"].articles, cpa.parts["Dispositivo"].order)
        assert not _body_approves_annex(l654.articles, l654.order)

    def test_dpr_131_keeps_its_body_and_its_tariff_apart(self, tariffa):
        assert tariffa.main_part == "" and "1" in tariffa.order


# ---------------------------------------------------------------------------
# Normattiva positions (the URN's ":k"), as measured live
# ---------------------------------------------------------------------------

class TestPositions:
    def test_codice_civile(self, cc):
        assert cc.parts["Disposizioni sulla legge in generale"].position == 1
        assert cc.parts["CODICE CIVILE"].position == 2 and cc.part_position() == 2

    def test_codice_penale(self):
        assert _load("codice_penale.xml").part_position() == 1

    def test_the_index_counts(self, cpa):
        # "Indice generale" has no articles and is :1: the code it precedes is :2.
        assert cpa.part_position() == 2
        assert cpa.part_at(3).name == "Allegato 2 Norme di attuazione"

    def test_sub_parts_after_a_dash_share_their_entry(self, appalti):
        # "Allegato I.4-Tabella A" and "Allegati - Allegato I.01" are entries "Allegato I.4"
        # and "Allegati" of Normattiva's tree: ;36:12 served Allegato I.11 live.
        assert appalti.annex_position("I.01") == 1
        assert appalti.annex_position("I.7") == 8
        assert appalti.annex_position("I.11") == 12

    def test_tariffa(self, tariffa):
        assert [(p.position, n.split()[0]) for n, p in tariffa.parts.items()] == [
            (1, "Tariffa"), (2, "Tariffa"), (3, "Tabella")]

    def test_annex_name_is_the_acts_not_the_position(self, cpa):
        assert annex_id_of("Allegato 1 Codice del processo amministrativo") == "1"
        assert annex_id_of("Allegato I.7") == "i.7"
        assert annex_id_of("CODICE CIVILE") is None
        assert cpa.annex_position("1") == 2


# ---------------------------------------------------------------------------
# API: allegato is Normattiva's position (VisuaLex's semantics)
# ---------------------------------------------------------------------------

def _serve(monkeypatch, act, pagine: "dict[str, str] | None" = None):
    """``act`` as the AKN export; Normattiva pages only from *pagine* (URL suffix -> page)."""
    richieste: list[str] = []

    async def fake_fetch_act_akn(norma, data_vigenza=None):
        return act

    class _Risposta:
        def __init__(self, url, text):
            self.url, self.text, self.status_code = url, text, 200

        def raise_for_status(self):
            return None

    class _Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def get(self, url):
            richieste.append(url)
            for suffisso, pagina in (pagine or {}).items():
                if url.endswith(suffisso):
                    return _Risposta(url, pagina)
            raise AssertionError(f"unexpected request: {url}")

    async def fake_metadata(norma):
        # The real date of an act cited with the year only, as its Normattiva page gives it.
        return {"date": {"104": "2010-07-02", "654": "1975-10-13"}.get(norma.numero_atto, "")}

    monkeypatch.delenv("AKN_DISABLED", raising=False)
    monkeypatch.setattr(akn_fetch, "fetch_act_akn", fake_fetch_act_akn)
    monkeypatch.setattr(scraper, "_act_metadata", fake_metadata)
    monkeypatch.setattr(scraper.httpx, "AsyncClient", _Client)
    return richieste


_CPA_120 = ('<html><body><div class="bodyTesto"><span class="attachment-just-text">Art. 120. '
            "(Disposizioni specifiche ai giudizi di cui all'articolo 119, comma 1, lettera a)) "
            "1. Gli atti delle procedure di affidamento...</span></div></body></html>")


class TestPositionalAllegato:
    def test_a_digit_allegato_is_the_urn_part(self):
        esito = api.riferimento_da_parametri("decreto legislativo", "5", data="2010-07-02",
                                             numero_atto="104", allegato="2")
        nd = esito.norma_data[0]
        assert nd.url.endswith(";104:2~art5")
        assert nd.allegato == "2" and nd.numero_articolo == "5"

    def test_the_preleggi_by_position(self):
        nd = api.riferimento_da_parametri("codice civile", "12", allegato="1").norma_data[0]
        assert nd.url.endswith("1942-03-16;262:1~art12")
        assert nd.allegato == "1"

    def test_a_codes_default_part_is_unchanged(self):
        nd = api.riferimento_da_parametri("codice civile", "2043", allegato="2").norma_data[0]
        assert nd.url.endswith(";262:2~art2043") and nd.allegato == "2"

    def test_an_annex_name_stays_a_name(self):
        nd = api.leggi_riferimento("allegato I.7 art. 30 d.lgs. 36/2023").norma_data[0]
        assert nd.allegato == "I.7" and nd.numero_articolo == "30"

    def test_a_digit_annex_name_is_not_taken_for_a_position(self):
        # "Allegato 1" of d.lgs. 104/2010 is Normattiva's :2: as allegato="1" it would be read
        # back as the "Indice generale". The annex stays in the article until a lookup.
        nd = api.leggi_riferimento("allegato 1 art. 120 d.lgs. 104/2010").norma_data[0]
        assert nd.allegato is None and nd.numero_articolo == "allegato 1 art. 120"

    async def test_html_channel_reads_visualex_page_for_the_part(self, monkeypatch, cpa):
        richieste = _serve(monkeypatch, cpa, pagine={";104:2~art120": _CPA_120})
        nd = api.riferimento_da_parametri("decreto legislativo", "120", data="2010-07-02",
                                          numero_atto="104", allegato="2").norma_data[0]
        t = await api.testo_articolo(nd, canale="html")
        assert t.esito == "trovato" and t.fonte == "normattiva"
        assert t.article_text.startswith("Art. 120.")
        assert [r.split("?")[1] for r in richieste] == [
            "urn:nir:stato:decreto.legislativo:2010-07-02;104:2~art120"]
        assert t.norma_data.allegato == "2"

    async def test_akn_channel_reads_the_part_at_the_position(self, monkeypatch, cpa):
        _serve(monkeypatch, cpa)
        nd = api.riferimento_da_parametri("decreto legislativo", "5", data="2010-07-02",
                                          numero_atto="104", allegato="3").norma_data[0]
        t = await api.testo_articolo(nd, canale="akn")
        assert t.esito == "trovato" and t.fonte == "normattiva-akn"
        assert "Art. 5" in t.article_text
        assert t.urn.endswith(";104:3~art5")

    async def test_the_decrees_number_gives_the_codes_identity(self, monkeypatch, cpa):
        _serve(monkeypatch, cpa)
        t = await api.testo_articolo("art. 120 d.lgs. 104/2010", canale="akn")
        assert t.esito == "trovato" and "Art. 120" in t.article_text
        assert t.urn == "urn:nir:stato:decreto.legislativo:2010-07-02;104:2~art120"
        assert t.norma_data.allegato == "2" and t.norma_data.numero_articolo == "120"

    async def test_a_digit_annex_name_round_trips_to_the_position(self, monkeypatch, cpa):
        _serve(monkeypatch, cpa)
        nd = api.leggi_riferimento("allegato 1 art. 120 d.lgs. 104/2010").norma_data[0]
        t = await api.testo_articolo(nd, canale="akn")
        assert t.esito == "trovato" and "Art. 120" in t.article_text
        assert t.urn.endswith(";104:2~art120")
        assert (t.norma_data.allegato, t.norma_data.numero_articolo) == ("2", "120")

    async def test_the_treatys_law_is_served_its_own_article(self, monkeypatch, l654):
        _serve(monkeypatch, l654)
        t = await api.testo_articolo("art. 3 l. 654/1975", canale="akn")
        assert t.esito == "trovato" and "ARTICOLO ABROGATO" in t.article_text
        assert not re.search(r"apartheid", t.article_text)
        assert t.urn.endswith(";654~art3")

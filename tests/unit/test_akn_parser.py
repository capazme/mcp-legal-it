"""Unit tests for the pure AKN parser (src/lib/visualex/akn_parser.py).

Uses committed real ``caricaAKN`` fixtures. No network. Primary fixtures:
``legge_241_1990.xml`` (flat) and ``codice_penale.xml`` (component).
"""

from pathlib import Path

import pytest

from src.lib.visualex.akn_parser import (
    ParsedAct,
    normalize_article_key,
    parse_akn,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "akn"


def _load(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


# --- session-scoped parsed fixtures (parsing the big files is the slow part) ---

@pytest.fixture(scope="module")
def l241() -> ParsedAct:
    return parse_akn(_load("legge_241_1990.xml"))


@pytest.fixture(scope="module")
def cp() -> ParsedAct:
    return parse_akn(_load("codice_penale.xml"))


@pytest.fixture(scope="module")
def costituzione() -> ParsedAct:
    return parse_akn(_load("costituzione.xml"))


@pytest.fixture(scope="module")
def cc() -> ParsedAct:
    return parse_akn(_load("codice_civile.xml"))


# ---------------------------------------------------------------------------
# normalize_article_key
# ---------------------------------------------------------------------------

class TestNormalizeArticleKey:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("2043", "2043"),
            ("art. 2043", "2043"),
            ("Art. 2043", "2043"),
            ("art 2043", "2043"),
            ("articolo 117", "117"),
            ("Articolo 117", "117"),
            ("art. 2 bis", "2-bis"),
            ("2 bis", "2-bis"),
            ("2-bis", "2-bis"),
            ("2bis", "2-bis"),
            ("2 BIS", "2-bis"),
            ("art_2-bis", "2-bis"),
            ("art_575", "575"),
            ("14-quinquies", "14-quinquies"),
            ("14 quinquies", "14-quinquies"),
            ("", ""),
        ],
    )
    def test_normalize(self, raw, expected):
        assert normalize_article_key(raw) == expected


# ---------------------------------------------------------------------------
# Flat structure (Legge 241/1990)
# ---------------------------------------------------------------------------

class TestFlatStructure:
    def test_auto_detects_flat(self, l241):
        assert l241.structure == "flat"

    def test_title(self, l241):
        assert "procedimento amministrativo" in l241.title.lower()

    def test_article_count_sane(self, l241):
        # Fixture documented as 51 articles.
        assert l241.article_count == 51
        assert len(l241.order) == l241.article_count

    def test_known_article_present_and_content(self, l241):
        art3 = l241.article("3")
        assert art3 is not None
        assert "motivat" in art3.lower()  # "Motivazione" / "motivato"

    def test_article_accepts_various_forms(self, l241):
        canonical = l241.article("3")
        assert l241.article("art. 3") == canonical
        assert l241.article("Art. 3") == canonical
        assert l241.article("articolo 3") == canonical

    def test_bis_article_parses(self, l241):
        bis = l241.article("2-bis")
        assert bis is not None
        assert bis == l241.article("art. 2 bis")
        assert bis == l241.article("2 bis")

    def test_commi_rendered(self, l241):
        art3 = l241.article("3")
        # The article header plus numbered commi.
        assert art3.startswith("### Art. 3")
        assert "\n1. " in art3
        assert "\n2. " in art3

    def test_lettere_rendered(self, l241):
        # Art. 6 has lettere a)-e).
        art6 = l241.article("6")
        assert art6 is not None
        assert "a)" in art6
        assert "b)" in art6

    def test_missing_article_returns_none(self, l241):
        assert l241.article("9999") is None

    def test_full_text_includes_title_and_articles(self, l241):
        full = l241.full_text()
        assert l241.title in full
        assert "### Art. 3" in full
        assert "### Art. 6" in full
        # Order preserved: art 1 header appears before art 3 header.
        assert full.index("### Art. 1") < full.index("### Art. 3")

    def test_no_modification_markers_in_output(self, l241):
        full = l241.full_text()
        assert "((" not in full
        assert "))" not in full


class TestCostituzione:
    def test_auto_detects_flat(self, costituzione):
        assert costituzione.structure == "flat"

    def test_article_count_sane(self, costituzione):
        # Fixture documented as 139 articles.
        assert 130 <= costituzione.article_count <= 139

    def test_known_article(self, costituzione):
        art117 = costituzione.article("117")
        assert art117 is not None
        assert art117.strip() != ""


# ---------------------------------------------------------------------------
# Component structure (Codice Penale)
# ---------------------------------------------------------------------------

class TestComponentStructure:
    def test_auto_detects_component(self, cp):
        assert cp.structure == "component"

    def test_title(self, cp):
        assert "penale" in cp.title.lower()

    def test_article_count_sane(self, cp):
        # Component docs measured at 995 for c.p.
        assert 700 <= cp.article_count <= 1000
        assert len(cp.order) == cp.article_count

    def test_known_article_content(self, cp):
        art575 = cp.article("575")
        assert art575 is not None
        assert "morte" in art575.lower()
        assert "omicidio" in art575.lower()

    def test_article_accepts_various_forms(self, cp):
        canonical = cp.article("575")
        assert cp.article("art. 575") == canonical
        assert cp.article("Art. 575") == canonical

    def test_bis_article_parses(self, cp):
        # c.p. has "Codice Penale-art. 3 bis" (space-separated in name).
        bis = cp.article("3-bis")
        assert bis is not None
        assert bis == cp.article("3 bis")
        assert bis == cp.article("art. 3 bis")

    def test_header_rendered(self, cp):
        art575 = cp.article("575")
        assert art575.startswith("### Art. 575")

    def test_no_modification_markers(self, cp):
        art575 = cp.article("575")
        assert "((" not in art575
        assert "))" not in art575

    def test_missing_article_returns_none(self, cp):
        assert cp.article("99999") is None


# ---------------------------------------------------------------------------
# Cross-structure / auto-detection
# ---------------------------------------------------------------------------

class TestAutoDetection:
    def test_flat_and_component_distinguished(self, l241, cp):
        assert l241.structure == "flat"
        assert cp.structure == "component"

    def test_component_prefers_main_part_over_preleggi(self):
        # Codice civile has BOTH "Disposizioni sulla legge in generale" (preleggi,
        # ~31) and "CODICE CIVILE" (~3249). The parser must pick the main code,
        # so art. 2043 (which only exists in the code) must resolve.
        cc = parse_akn(_load("codice_civile.xml"))
        assert cc.structure == "component"
        art2043 = cc.article("2043")
        assert art2043 is not None
        assert "risarcimento" in art2043.lower()
        # Article count reflects the main part, not the preleggi (31).
        assert cc.article_count > 1000


class TestParsedActApi:
    def test_article_count_property(self, l241):
        assert l241.article_count == len(l241.order)

    def test_order_keys_all_in_articles(self, l241):
        for key in l241.order:
            assert key in l241.articles

    def test_empty_xml_does_not_crash(self):
        act = parse_akn("<akomaNtoso xmlns='http://docs.oasis-open.org/legaldocml/ns/akn/3.0'></akomaNtoso>")
        assert act.article_count == 0
        assert act.full_text() == ""


# ---------------------------------------------------------------------------
# Component multi-part exposure (codice civile bundles the preleggi)
# ---------------------------------------------------------------------------

class TestComponentMultiPart:
    """The c.c. AKN export bundles TWO component parts: the code body
    ('CODICE CIVILE', ~3249 art.) and the preleggi ('Disposizioni sulla legge
    in generale', ~31 art.). The parser must expose both and let a caller select
    the preleggi part, while keeping the code body as the default lookup so
    'art. 12 c.c.' and 'art. 12 preleggi' resolve to different texts.
    """

    def test_both_parts_exposed(self, cc):
        names = [n.lower() for n in cc.parts]
        assert any("codice civile" in n for n in names)
        assert any("disposizioni sulla legge in generale" in n for n in names)

    def test_default_article_is_code_body(self, cc):
        # art. 12 of the code body is abrogated (ex persone giuridiche).
        art12 = cc.article("12")
        assert art12 is not None
        assert "abrogato" in art12.lower()

    def test_preleggi_part_selects_disposizioni(self, cc):
        # art. 12 preleggi = interpretazione della legge (art. 12 co. 1).
        art12 = cc.article("12", part="preleggi")
        assert art12 is not None
        assert "significato proprio delle parole" in art12.lower()

    def test_code_body_articles_absent_from_preleggi(self, cc):
        # art. 2043 exists only in the code body, not in the 31-article preleggi.
        assert cc.article("2043") is not None
        assert cc.article("2043", part="preleggi") is None

    def test_preleggi_part_is_small(self, cc):
        prel = next(
            (p for n, p in cc.parts.items()
             if "disposizioni sulla legge in generale" in n.lower()),
            None,
        )
        assert prel is not None
        assert 15 <= prel.article_count < 100  # ~31, not the ~3249 code body

    def test_unknown_part_returns_none(self, cc):
        assert cc.article("12", part="questa parte non esiste") is None

    def test_full_text_of_preleggi_part(self, cc):
        txt = cc.full_text(part="preleggi")
        assert "significato proprio delle parole" in txt.lower()

    def test_part_article_count(self, cc):
        assert cc.part_article_count() == cc.article_count  # default = dominant part
        assert 15 <= cc.part_article_count("preleggi") < 100
        assert cc.part_article_count("questa parte non esiste") == 0

    def test_full_text_of_preleggi_uses_part_title(self, cc):
        # The whole-part text must be headed by the preleggi's own title, not
        # the bundling act's title ("Codice civile").
        first_line = cc.full_text(part="preleggi").splitlines()[0].lower()
        assert "disposizioni sulla legge in generale" in first_line
        assert "codice civile" not in first_line

    def test_part_title(self, cc):
        assert "disposizioni sulla legge in generale" in cc.part_title("preleggi").lower()
        assert cc.part_title() == cc.title  # default = act title
        assert cc.part_title("questa parte non esiste") == cc.title  # fallback

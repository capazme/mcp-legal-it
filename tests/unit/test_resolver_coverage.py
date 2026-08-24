"""Regression net for act-name resolution coverage.

Every entry is (reference, expected tipo_atto, expected numero_atto). The point
is not that a reference *resolves* but that it resolves to the *right act* — a
wrong number silently cites the wrong law, which is the failure mode this file
exists to prevent.
"""

import pytest

from src.tools.legal_citations import _parse_reference, _resolve_act


def assert_resolves(reference: str, tipo: str, numero: str, *, numero_optional: bool = False) -> None:
    """Assert a reference resolves to the intended act.

    ``numero_optional`` covers codici, whose identity is carried by tipo_atto:
    the resolver may or may not populate the underlying act number depending on
    which table matched. An empty number is tolerated there; a *wrong* one never is.
    """
    article, act_name = _parse_reference(reference)
    assert act_name, f"{reference!r}: nome atto non estratto"
    result = _resolve_act(act_name)
    assert result is not None, f"{reference!r}: atto {act_name!r} non risolto"
    assert result["tipo_atto"] == tipo, (
        f"{reference!r}: tipo_atto {result['tipo_atto']!r}, atteso {tipo!r}"
    )
    actual = result.get("numero_atto", "")
    if numero_optional:
        assert actual in ("", numero), (
            f"{reference!r}: numero_atto {actual!r} non corrisponde all'atto atteso (n. {numero})"
        )
    else:
        assert actual == numero, (
            f"{reference!r}: numero_atto {actual!r}, atteso {numero!r}"
        )


def assert_resolves_codice(reference: str, tipo: str, numero: str) -> None:
    assert_resolves(reference, tipo, numero, numero_optional=True)


# ---------------------------------------------------------------------------
# Codici — already working, guarded against regression
# ---------------------------------------------------------------------------

CODICI = [
    ("art. 2043 c.c.", "codice civile", "262"),
    ("art. 416-bis c.p.", "codice penale", "1398"),
    ("art. 700 c.p.c.", "codice di procedura civile", "1443"),
    ("art. 191 c.p.p.", "codice di procedura penale", "447"),
    ("art. 13 Cost.", "costituzione", ""),
    ("articolo 1341 codice civile", "codice civile", "262"),
    ("art. 1 disp. prel. c.c.", "preleggi", "262"),
    ("art. 142 codice del consumo", "codice del consumo", "206"),
]


class TestCodici:
    @pytest.mark.parametrize("reference,tipo,numero", CODICI)
    def test_resolves(self, reference, tipo, numero):
        assert_resolves_codice(reference, tipo, numero)


# ---------------------------------------------------------------------------
# Leading articles and prepositions before the act name
# ---------------------------------------------------------------------------

PREPOSIZIONI = [
    ("art. 111 della Costituzione", "costituzione", ""),
    ("art. 1218 del codice civile", "codice civile", "262"),
    ("art. 3 dello Statuto dei lavoratori", "legge", "300"),
    ("art. 2 del codice della strada", "codice della strada", "285"),
]


class TestPreposizioniIniziali:
    @pytest.mark.parametrize("reference,tipo,numero", PREPOSIZIONI)
    def test_resolves(self, reference, tipo, numero):
        assert_resolves_codice(reference, tipo, numero)


# ---------------------------------------------------------------------------
# Atti denominati — common names carrying no number in the citation
# ---------------------------------------------------------------------------

DENOMINATI = [
    ("art. 18 Statuto dei lavoratori", "legge", "300"),
    ("art. 67 legge fallimentare", "regio decreto", "267"),
    ("art. 2 legge sul procedimento amministrativo", "legge", "241"),
    ("art. 6 testo unico edilizia", "decreto del presidente della repubblica", "380"),
    ("art. 26 testo unico sicurezza sul lavoro", "decreto legislativo", "81"),
    ("art. 12 statuto del contribuente", "legge", "212"),
    ("art. 8 legge sul divorzio", "legge", "898"),
    ("art. 4 legge 104", "legge", "104"),
    ("art. 2 legge sull'adozione", "legge", "184"),
    ("art. 70 legge diritto d'autore", "legge", "633"),
    ("art. 5 legge equo canone", "legge", "392"),
    ("art. 5 legge professionale forense", "legge", "247"),
    ("art. 1 legge sul biotestamento", "legge", "219"),
    ("art. 4 testo unico immigrazione", "decreto legislativo", "286"),
    ("art. 1 testo unico maternità e paternità", "decreto legislativo", "151"),
]


class TestAttiDenominati:
    @pytest.mark.parametrize("reference,tipo,numero", DENOMINATI)
    def test_resolves(self, reference, tipo, numero):
        assert_resolves(reference, tipo, numero)


# ---------------------------------------------------------------------------
# Institutional acronyms
# ---------------------------------------------------------------------------

SIGLE = [
    ("art. 42 TUEL", "decreto legislativo", "267"),
    ("art. 4 TULPS", "regio decreto", "773"),
    ("art. 55 TUPI", "decreto legislativo", "165"),
    ("art. 73 TU stupefacenti", "decreto del presidente della repubblica", "309"),
    ("art. 26 TUSL", "decreto legislativo", "81"),
    ("art. 5 TUB", "decreto legislativo", "385"),
    ("art. 94 TUF", "decreto legislativo", "58"),
    ("art. 10 TUIR", "decreto del presidente della repubblica", "917"),
    ("art. 3 TU espropri", "decreto del presidente della repubblica", "327"),
]

SIGLE_CODICI = [
    ("art. 1 CCII", "codice della crisi d'impresa e dell'insolvenza", "14"),
    ("art. 80 CCP", "codice dei contratti pubblici", "36"),
    ("art. 80 codice appalti", "codice dei contratti pubblici", "36"),
    ("art. 2 codice crisi", "codice della crisi d'impresa e dell'insolvenza", "14"),
]


class TestSigleIstituzionali:
    @pytest.mark.parametrize("reference,tipo,numero", SIGLE)
    def test_resolves(self, reference, tipo, numero):
        assert_resolves(reference, tipo, numero)

    @pytest.mark.parametrize("reference,tipo,numero", SIGLE_CODICI)
    def test_resolves_codice(self, reference, tipo, numero):
        assert_resolves_codice(reference, tipo, numero)


# ---------------------------------------------------------------------------
# Eponyms and press nicknames
# ---------------------------------------------------------------------------

EPONIMI = [
    ("art. 7 legge Gelli-Bianco", "legge", "24"),
    ("art. 1 legge Cirinnà", "legge", "76"),
    ("art. 4 legge Biagi", "decreto legislativo", "276"),
    ("art. 2 legge Pinto", "legge", "89"),
    ("art. 4 legge Fornero", "legge", "92"),
    ("art. 5 legge Bossi-Fini", "legge", "189"),
    ("art. 1 legge Severino", "legge", "190"),
    ("art. 3 Jobs Act", "decreto legislativo", "23"),
    ("art. 103 decreto Cura Italia", "decreto legge", "18"),
    ("art. 1 decreto Rilancio", "decreto legge", "34"),
]


class TestEponimi:
    @pytest.mark.parametrize("reference,tipo,numero", EPONIMI)
    def test_resolves(self, reference, tipo, numero):
        assert_resolves(reference, tipo, numero)


# ---------------------------------------------------------------------------
# EU compliance acts
# ---------------------------------------------------------------------------

UE_COMPLIANCE = [
    ("art. 5 GDPR", "regolamento ue", "679"),
    ("art. 6 AI Act", "regolamento ue", "1689"),
    ("art. 32 NIS2", "direttiva ue", "2555"),
    ("art. 34 DSA", "regolamento ue", "2065"),
    ("art. 6 DMA", "regolamento ue", "1925"),
    ("art. 3 Data Act", "regolamento ue", "2854"),
    ("art. 5 Data Governance Act", "regolamento ue", "868"),
    ("art. 6 eIDAS", "regolamento ue", "910"),
    ("art. 13 Cyber Resilience Act", "regolamento ue", "2847"),
    ("art. 4 MiCA", "regolamento ue", "1114"),
    ("art. 5 direttiva whistleblowing", "direttiva ue", "1937"),
    ("art. 14 direttiva NIS", "direttiva ue", "1148"),
    ("art. 4 PSD2", "direttiva ue", "2366"),
    ("art. 5 CSRD", "direttiva ue", "2464"),
    ("art. 8 CSDDD", "direttiva ue", "1760"),
]


class TestUeCompliance:
    @pytest.mark.parametrize("reference,tipo,numero", UE_COMPLIANCE)
    def test_resolves(self, reference, tipo, numero):
        assert_resolves(reference, tipo, numero)


# ---------------------------------------------------------------------------
# EU treaties — present in EURLEX but unreachable from resolve_atto
# ---------------------------------------------------------------------------

TRATTATI = [
    ("art. 101 TFUE", "TFUE", ""),
    ("art. 6 TUE", "TUE", ""),
    ("art. 8 CDFUE", "CDFUE", ""),
    ("art. 7 Carta di Nizza", "CDFUE", ""),
]


class TestTrattatiUe:
    @pytest.mark.parametrize("reference,tipo,numero", TRATTATI)
    def test_resolves(self, reference, tipo, numero):
        assert_resolves(reference, tipo, numero)

    def test_treaty_url_routes_to_eurlex(self):
        from src.tools.legal_citations import _build_nv

        nv = _build_nv(_resolve_act("TFUE"), "101")
        assert "eur-lex.europa.eu" in nv.url()


# ---------------------------------------------------------------------------
# Citation forms — spelled-out types, alternative separators, EU variants
# ---------------------------------------------------------------------------

FORME = [
    ("art. 21-octies legge 241/1990", "legge", "241"),
    ("art. 2 decreto legislativo 231/2001", "decreto legislativo", "231"),
    ("art. 3 regio decreto 267/1942", "regio decreto", "267"),
    ("art. 1 decreto legge 34/2020", "decreto legge", "34"),
    ("art. 2 d.lgs. n. 231 del 2001", "decreto legislativo", "231"),
    ("art. 7 legge n. 241 del 1990", "legge", "241"),
    ("art. 8 legge 218/1995", "legge", "218"),
    ("art. 15 reg. (UE) 2016/679", "regolamento ue", "679"),
    ("art. 3 direttiva 2019/1937", "direttiva ue", "1937"),
    ("art. 5 direttiva 95/46/CE", "direttiva ue", "46"),
    ("art. 2 comma 1 lett. a) del d.lgs. 231/2001", "decreto legislativo", "231"),
    ("art. 2, comma 1, lett. a), del d.lgs. 231/2001", "decreto legislativo", "231"),
]


class TestFormeDiCitazione:
    @pytest.mark.parametrize("reference,tipo,numero", FORME)
    def test_resolves(self, reference, tipo, numero):
        assert_resolves(reference, tipo, numero)


# ---------------------------------------------------------------------------
# Unknown acts must fail loudly, and suggest — never guess
# ---------------------------------------------------------------------------

class TestAttoSconosciuto:
    def test_unknown_act_returns_none(self):
        assert _resolve_act("legge fantasiosa inesistente 99999") is None

    def test_typo_produces_suggestion(self):
        from src.tools.legal_citations import _suggest_acts

        assert "legge fallimentare" in _suggest_acts("legge fallimentre")

    def test_unknown_act_produces_no_suggestion(self):
        from src.tools.legal_citations import _suggest_acts

        assert _suggest_acts("zzzzzzzz qqqqqqqq") == []


# ---------------------------------------------------------------------------
# cite_law surfaces the suggestion instead of a dead end
# ---------------------------------------------------------------------------

class TestMessaggioErrore:
    async def test_error_message_lists_near_misses(self):
        from src.tools.legal_citations import _cite_law_impl

        out = await _cite_law_impl("art. 67 legge fallimentre")
        assert "non riconosciuto" in out
        assert "legge fallimentare" in out

    async def test_error_message_without_near_misses_still_explains(self):
        from src.tools.legal_citations import _cite_law_impl

        out = await _cite_law_impl("art. 1 zzzzzzzz qqqqqqqq")
        assert "non riconosciuto" in out
        assert "fetch_law_article" in out

    @pytest.mark.parametrize(
        "impl_name",
        ["_cerca_brocardi_impl", "_fetch_act_index_impl", "_fetch_full_act_impl", "_download_law_pdf_impl"],
    )
    async def test_every_entry_point_suggests_near_misses(self, impl_name):
        import src.tools.legal_citations as mod

        impl = getattr(mod, impl_name)
        out = await impl("art. 67 legge fallimentre")
        assert "legge fallimentare" in out, f"{impl_name} non suggerisce alternative"


# ---------------------------------------------------------------------------
# EU treaties must be fetched through CELLAR, not from EUR-Lex directly
# ---------------------------------------------------------------------------

class TestEurlexTreatyRouting:
    """EUR-Lex answers direct requests with a WAF challenge (HTTP 202), so a
    treaty resolved to its eur-lex.europa.eu page would never yield text. The
    document has to be fetched from CELLAR by CELEX id instead.
    """

    @pytest.mark.parametrize(
        "tipo,celex_encoded",
        [("TUE", "12016M%2FTXT"), ("TFUE", "12016E%2FTXT"), ("CDFUE", "12016P%2FTXT")],
    )
    def test_treaty_fetch_url_uses_cellar(self, tipo, celex_encoded):
        from src.lib.visualex.models import Norma
        from src.lib.visualex.scraper import _eurlex_urls

        fetch_url, display_url = _eurlex_urls(Norma(tipo_atto=tipo))
        assert "publications.europa.eu/resource/celex/" in fetch_url
        assert celex_encoded in fetch_url
        assert "eur-lex.europa.eu" in display_url

    def test_regulation_still_uses_cellar_celex(self):
        from src.lib.visualex.models import Norma
        from src.lib.visualex.scraper import _eurlex_urls

        fetch_url, _ = _eurlex_urls(Norma(tipo_atto="regolamento ue", data="2016", numero_atto="679"))
        assert fetch_url.endswith("32016R0679")

    def test_unknown_act_type_has_no_eurlex_url(self):
        from src.lib.visualex.models import Norma
        from src.lib.visualex.scraper import _eurlex_urls

        assert _eurlex_urls(Norma(tipo_atto="legge", data="1990", numero_atto="241")) == ("", "")


# ---------------------------------------------------------------------------
# EUR-Lex article extraction must not stop at the article's own subtitle
# ---------------------------------------------------------------------------

class TestEurlexSubtitleTruncation:
    """Treaty articles carry a subtitle in <p class="sti-art"> ("(ex articolo
    81 del TCE)"). A substring test for "ti-art" matches "sti-art" too, so the
    collector used to stop on the subtitle and return the heading alone.
    """

    HTML = """
    <div id="101">
      <p class="ti-art">Articolo 101</p>
      <p class="sti-art">(ex articolo 81 del TCE)</p>
      <div>1. Sono incompatibili con il mercato interno tutti gli accordi tra imprese.</div>
      <div>2. Gli accordi vietati sono nulli di pieno diritto.</div>
      <p class="ti-art">Articolo 102</p>
      <div>Testo estraneo del successivo.</div>
    </div>
    """

    def test_article_body_is_collected(self):
        from src.lib.visualex.scraper import _extract_eurlex_article

        out = _extract_eurlex_article(self.HTML, "101")
        assert "Sono incompatibili" in out
        assert "nulli di pieno diritto" in out

    def test_subtitle_is_kept(self):
        from src.lib.visualex.scraper import _extract_eurlex_article

        assert "ex articolo 81" in _extract_eurlex_article(self.HTML, "101")

    def test_collection_stops_at_next_article(self):
        from src.lib.visualex.scraper import _extract_eurlex_article

        assert "Testo estraneo" not in _extract_eurlex_article(self.HTML, "101")


# ---------------------------------------------------------------------------
# Dotted acronyms — "t.u.e.l." is how these get written in practice
# ---------------------------------------------------------------------------

DOTTED = [
    ("art. 42 t.u.e.l.", "decreto legislativo", "267"),
    ("art. 4 t.u.l.p.s.", "regio decreto", "773"),
    ("art. 94 t.u.f.", "decreto legislativo", "58"),
    ("art. 10 t.u.i.r.", "decreto del presidente della repubblica", "917"),
    ("art. 5 t.u.b.", "decreto legislativo", "385"),
]

DOTTED_CODICI = [
    ("art. 5 c.c.p.", "codice dei contratti pubblici", "36"),
    ("art. 30 c.p.a.", "codice del processo amministrativo", "104"),
    ("art. 1 c.c.i.i.", "codice della crisi d'impresa e dell'insolvenza", "14"),
    ("art. 2 c.a.d.", "codice dell'amministrazione digitale", "82"),
]


class TestAcronimiPuntati:
    @pytest.mark.parametrize("reference,tipo,numero", DOTTED)
    def test_resolves(self, reference, tipo, numero):
        assert_resolves(reference, tipo, numero)

    @pytest.mark.parametrize("reference,tipo,numero", DOTTED_CODICI)
    def test_resolves_codice(self, reference, tipo, numero):
        assert_resolves_codice(reference, tipo, numero)

    def test_dot_removal_does_not_touch_names_with_numbers(self):
        # "d.lgs. 196/2003" must still take the pattern path, not become a key
        assert _resolve_act("d.lgs. 196/2003")["numero_atto"] == "196"


class TestTuirNomeEsteso:
    @pytest.mark.parametrize(
        "name",
        [
            "tuir",
            "testo unico delle imposte sui redditi",
            "testo unico imposte sui redditi",
            "t.u.i.r.",
        ],
    )
    def test_resolves(self, name):
        result = _resolve_act(name)
        assert result is not None, f"{name!r} non risolto"
        assert result["tipo_atto"] == "decreto del presidente della repubblica"
        assert result["numero_atto"] == "917"


class TestCodiceTerzoSettore:
    """The URN map keys this codice with a capital T ("codice del Terzo
    settore") while lookups are lowercased, so the acronym never reached it.
    """

    @pytest.mark.parametrize("name", ["cts", "c.t.s.", "codice del terzo settore", "cod. ter. sett."])
    def test_resolves(self, name):
        result = _resolve_act(name)
        assert result is not None, f"{name!r} non risolto"
        assert result["numero_atto"] == "117"

    def test_url_uses_the_codice_urn(self):
        """Norma.url() lowercases too, so the same capital-T key broke the URN."""
        from src.lib.visualex.models import Norma

        url = Norma(tipo_atto="codice del Terzo settore").url(article="5")
        assert "decreto.legislativo:2017-07-03;117" in url
        assert "codice.del.terzo.settore" not in url

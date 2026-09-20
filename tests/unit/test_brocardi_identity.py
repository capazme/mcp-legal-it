"""find_brocardi_url must match an act by identity, never by substring.

Before this suite existed, "legge 300/1970" (Statuto dei lavoratori) came back
as the legge fallimentare page because the lookup matched the word "legge" in
the first label that contained it, and every decreto legislativo / D.P.R. got
no page at all because the resolver says "decreto legislativo" while the label
says "D.lgs.". The Brocardi table is data; the identity (tipo, anno, numero)
parsed from each label is what a citation must be matched against.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Tool modules import each other through src.server; importing one of them
# before the server trips a circular import, so the server goes first.
import src.server  # noqa: F401
from src.lib.visualex.map import (
    BROCARDI_CODICI,
    find_brocardi_url,
    parse_brocardi_estremi,
    resolve_atto,
)

B = "https://www.brocardi.it"

# Labels that carry no "(tipo giorno mese anno, n. N)" — matched by name only.
LABELS_WITHOUT_ESTREMI = {
    "Costituzione",
    "Preleggi",
    "Contratto Collettivo Nazionale del Lavoro Domestico",
    # Delisted from brocardi.it/fonti.html but the page still answers.
    "Contratto Collettivo Nazionale del Turismo, Pubblici esercizi, Ristorazione collettiva e commerciale, Alberghi",
}


# ---------------------------------------------------------------------------
# parse_brocardi_estremi — the label → identity bridge
# ---------------------------------------------------------------------------

class TestParseBrocardiEstremi:
    def test_decreto_legislativo(self):
        parsed = parse_brocardi_estremi(
            "Disciplina della responsabilità amministrativa delle persone giuridiche(D.lgs. 8 giugno 2001, n. 231)"
        )
        assert parsed == {"tipo_atto": "decreto legislativo", "data": "2001-06-08", "numero_atto": "231"}

    def test_regolamento_ue(self):
        parsed = parse_brocardi_estremi(
            "Regolamento generale sulla protezione dei dati(Reg. UE 27 aprile 2016, n. 679)"
        )
        assert parsed == {"tipo_atto": "regolamento ue", "data": "2016-04-27", "numero_atto": "679"}

    def test_label_without_estremi(self):
        assert parse_brocardi_estremi("Preleggi") is None

    def test_every_label_with_parenthesis_parses(self):
        """Drift guard: a new label whose estremi the parser cannot read would
        silently lose its page, so every parenthesised label must parse."""
        unparsed = [
            key for key in BROCARDI_CODICI
            if "(" in key and parse_brocardi_estremi(key) is None
        ]
        assert unparsed == []

    def test_only_the_known_labels_lack_estremi(self):
        bare = {key for key in BROCARDI_CODICI if parse_brocardi_estremi(key) is None}
        assert bare == LABELS_WITHOUT_ESTREMI


# ---------------------------------------------------------------------------
# find_brocardi_url — identity match
# ---------------------------------------------------------------------------

class TestFindBrocardiUrlIdentity:
    def test_every_labelled_entry_round_trips(self):
        """The identity parsed from a label must lead back to that label's URL."""
        mismatches = []
        for key, url in BROCARDI_CODICI.items():
            parsed = parse_brocardi_estremi(key)
            if parsed is None:
                continue
            found = find_brocardi_url(parsed["tipo_atto"], parsed["numero_atto"], parsed["data"])
            if found != url:
                mismatches.append((key, found))
        assert mismatches == []

    def test_statuto_lavoratori_is_not_legge_fallimentare(self):
        assert find_brocardi_url("legge", "300", "1970-05-20") == f"{B}/statuto-lavoratori/"

    def test_legge_fallimentare_is_the_regio_decreto(self):
        assert find_brocardi_url("regio decreto", "267", "1942-03-16") == f"{B}/legge-fallimentare/"

    def test_year_alone_is_enough_as_date(self):
        assert find_brocardi_url("decreto legislativo", "231", "2001") == (
            f"{B}/responsabilita-amministrativa-persone-giuridiche/"
        )

    def test_abbreviated_tipo_is_normalised(self):
        assert find_brocardi_url("d.lgs.", "231", "2001") == (
            f"{B}/responsabilita-amministrativa-persone-giuridiche/"
        )

    def test_same_number_different_year_and_tipo(self):
        assert find_brocardi_url("decreto legislativo", "81", "2008") == f"{B}/testo-unico-sicurezza-sul-lavoro/"
        assert find_brocardi_url("decreto legislativo", "81", "2015") == f"{B}/disciplina-organica-contratti-lavoro/"
        assert find_brocardi_url("legge", "81", "2017") == f"{B}/lavoro-agile/"

    def test_missing_year_with_unique_number_resolves(self):
        assert find_brocardi_url("decreto legislativo", "231") == (
            f"{B}/responsabilita-amministrativa-persone-giuridiche/"
        )

    def test_missing_year_with_ambiguous_number_returns_none(self):
        # D.lgs. 81/2008 and D.lgs. 81/2015 both exist: guessing would cite the wrong act.
        assert find_brocardi_url("decreto legislativo", "81") is None

    def test_legge_not_on_brocardi_returns_none(self):
        # Legge Pinto (L. 89/2001) has no Brocardi page: nothing, not the nearest "legge".
        assert find_brocardi_url("legge", "89", "2001-03-24") is None

    def test_wrong_year_returns_none(self):
        assert find_brocardi_url("legge", "300", "1971") is None

    def test_gdpr(self):
        assert find_brocardi_url("regolamento ue", "679", "2016") == f"{B}/regolamento-privacy-ue/"

    def test_dpr_testo_unico_edilizia(self):
        assert find_brocardi_url("decreto del presidente della repubblica", "380", "2001") == (
            f"{B}/testo-unico-edilizia/"
        )


class TestFindBrocardiUrlByName:
    def test_codice_civile(self):
        assert find_brocardi_url("codice civile") == f"{B}/codice-civile/"

    def test_costituzione(self):
        assert find_brocardi_url("costituzione") == f"{B}/costituzione/"

    def test_preleggi_share_the_codice_civile_estremi(self):
        # Both are R.D. 262/1942: the name must win over the identity here,
        # also when the resolver hands over the estremi it knows for them.
        assert find_brocardi_url("preleggi") == f"{B}/preleggi/"
        assert find_brocardi_url("preleggi", "262", "1942-03-16") == f"{B}/preleggi/"

    def test_testo_unico_maternita_by_identity(self):
        assert find_brocardi_url("decreto legislativo", "151", "2001") == (
            f"{B}/testo-unico-sostegno-maternita-paternita/"
        )

    def test_codice_name_from_normattiva_urn(self):
        # The URN table names it after Normattiva; Brocardi calls it "Codice della privacy".
        assert find_brocardi_url("codice in materia di protezione dei dati personali") == (
            f"{B}/codice-della-privacy/"
        )
        assert find_brocardi_url("norme in materia ambientale") == f"{B}/codice-dell-ambiente/"

    def test_codice_contratti_pubblici_is_the_current_code(self):
        # Brocardi keeps the old name on the abrogated D.lgs. 50/2016 page.
        assert find_brocardi_url("codice dei contratti pubblici") == f"{B}/nuovo-codice-appalti/"

    def test_label_name_without_estremi(self):
        assert find_brocardi_url("contratto collettivo nazionale del lavoro domestico") == (
            f"{B}/contratto-collettivo-colf-badanti/"
        )

    def test_plain_label_name_with_estremi(self):
        assert find_brocardi_url("statuto dei lavoratori") == f"{B}/statuto-lavoratori/"

    def test_label_name_with_matching_estremi(self):
        # fetch_law_annotations(act_type="statuto dei lavoratori", act_number="300")
        assert find_brocardi_url("statuto dei lavoratori", "300") == f"{B}/statuto-lavoratori/"
        assert find_brocardi_url("statuto dei lavoratori", "300", "1970") == f"{B}/statuto-lavoratori/"

    def test_label_name_with_contradicting_estremi_returns_none(self):
        assert find_brocardi_url("statuto dei lavoratori", "267") is None
        assert find_brocardi_url("statuto dei lavoratori", "300", "1971") is None

    def test_explicit_estremi_beat_the_codice_urn(self):
        # "codice dei contratti pubblici" alone is the current code (D.lgs. 36/2023);
        # with the abrogated code's own estremi the caller means D.lgs. 50/2016.
        assert find_brocardi_url("codice dei contratti pubblici", "50", "2016") == (
            f"{B}/codice-dei-contratti-pubblici/"
        )
        assert find_brocardi_url("codice dei contratti pubblici", "36", "2023") == f"{B}/nuovo-codice-appalti/"
        assert find_brocardi_url("codice civile", "999", "1942") is None

    def test_substring_of_a_label_is_not_a_match(self):
        assert find_brocardi_url("legge") is None
        assert find_brocardi_url("testo unico") is None

    def test_unknown(self):
        assert find_brocardi_url("fantasy_law_xyz") is None


# ---------------------------------------------------------------------------
# Table completeness against brocardi.it/fonti.html
# ---------------------------------------------------------------------------

class TestBrocardiTableCoverage:
    def test_disposizioni_attuazione_cpp(self):
        assert find_brocardi_url("decreto legislativo", "271", "1989") == (
            f"{B}/disposizioni-per-attuazione-codice-procedura-penale/"
        )

    def test_abrogated_codice_contratti_pubblici_2016(self):
        assert find_brocardi_url("decreto legislativo", "50", "2016") == (
            f"{B}/codice-dei-contratti-pubblici/"
        )

    def test_cura_italia_decree_and_conversion_law_share_the_page(self):
        assert find_brocardi_url("decreto legge", "18", "2020") == f"{B}/decreto-cura-italia/"
        assert find_brocardi_url("legge", "27", "2020") == f"{B}/decreto-cura-italia/"


# ---------------------------------------------------------------------------
# Resolver aliases for the fonti named as Brocardi names them
# ---------------------------------------------------------------------------

class TestResolverAliases:
    @pytest.mark.parametrize("name", [
        "Regolamento generale sulla protezione dei dati",
        "regolamento generale sulla protezione dei dati",
    ])
    def test_gdpr_full_name(self, name):
        assert resolve_atto(name) == {"tipo_atto": "regolamento ue", "data": "2016", "numero_atto": "679"}

    def test_disposizioni_attuazione_cpp(self):
        assert resolve_atto("disposizioni di attuazione del codice di procedura penale") == {
            "tipo_atto": "decreto legislativo", "data": "1989-07-28", "numero_atto": "271",
        }

    @pytest.mark.parametrize("name, numero", [
        ('Decreto "Sostegni"', "41"),
        ('Decreto "Rilancio"', "34"),
        ('Decreto "Cura Italia"', "18"),
        ('Decreto "Semplificazioni bis"', "77"),
    ])
    def test_quoted_nicknames(self, name, numero):
        result = resolve_atto(name)
        assert result is not None
        assert result["numero_atto"] == numero


# ---------------------------------------------------------------------------
# End to end: the date travels from the resolver to the Brocardi client
# ---------------------------------------------------------------------------

class TestDateReachesBrocardi:
    """D.lgs. 81/2008 (TUSL) and D.lgs. 81/2015 (Jobs Act) share tipo and number:
    only the year tells them apart, so it must reach the Brocardi lookup."""

    @pytest.mark.asyncio
    async def test_cerca_brocardi_passes_the_year(self):
        from src.tools.legal_citations import _cerca_brocardi_impl

        with patch("src.lib.brocardi.client.find_article_url", new=AsyncMock(return_value=None)) as find_url, \
             patch("src.lib.brocardi.client.httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__.return_value = MagicMock()
            await _cerca_brocardi_impl("art. 2 d.lgs. 81/2008")

        assert find_url.call_args.args[1] == f"{B}/testo-unico-sicurezza-sul-lavoro/"

    @pytest.mark.asyncio
    async def test_cite_law_annotations_pass_the_year(self):
        from src.tools.legal_citations import _cite_law_impl

        with patch("src.tools.legal_citations.fetch_article", new=AsyncMock(return_value={"text": "t", "url": "u", "source": "normattiva"})), \
             patch("src.lib.brocardi.client.find_article_url", new=AsyncMock(return_value=None)) as find_url, \
             patch("src.lib.brocardi.client.httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__.return_value = MagicMock()
            await _cite_law_impl("art. 2 d.lgs. 81/2015", include_annotations=True)

        assert find_url.call_args.args[1] == f"{B}/disciplina-organica-contratti-lavoro/"

    @pytest.mark.asyncio
    async def test_fetch_law_annotations_passes_the_date(self):
        from src.tools.legal_citations import _fetch_law_annotations_impl

        with patch("src.lib.brocardi.client.find_article_url", new=AsyncMock(return_value=None)) as find_url, \
             patch("src.lib.brocardi.client.httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__.return_value = MagicMock()
            await _fetch_law_annotations_impl("decreto legislativo", "2", date="2008-04-09", act_number="81")

        assert find_url.call_args.args[1] == f"{B}/testo-unico-sicurezza-sul-lavoro/"

    @pytest.mark.asyncio
    async def test_fetch_annotations_uses_the_act_date(self):
        from src.lib.visualex.models import Norma, NormaVisitata
        from src.lib.visualex.scraper import fetch_annotations

        nv = NormaVisitata(norma=Norma("decreto legislativo", "2015-06-15", "81"), numero_articolo="2")
        with patch("src.lib.visualex.scraper._find_brocardi_article_url", new=AsyncMock(return_value=None)) as find_url, \
             patch("src.lib.visualex.scraper.httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__.return_value = MagicMock()
            result = await fetch_annotations(nv)

        assert find_url.call_args.args[1] == f"{B}/disciplina-organica-contratti-lavoro/"
        assert result["url"] == f"{B}/disciplina-organica-contratti-lavoro/"


class TestOtherToolsPassTheDate:
    """mappa_orientamento and giurisprudenza_articolo anchor on Brocardi too."""

    @pytest.mark.asyncio
    async def test_mappa_orientamento(self):
        from src.tools import orientamento
        from src.lib._result import SearchResult

        with patch.object(orientamento, "fetch_brocardi", new=AsyncMock(side_effect=RuntimeError("stop"))) as fb, \
             patch.object(orientamento, "_orientamento_su_norma_impl",
                          new=AsyncMock(return_value=SearchResult(success=True, source="test"))):
            await orientamento._mappa_orientamento_impl("art. 18 tusl")

        assert fb.call_args.args[:3] == ("decreto legislativo", "18", "81")
        assert fb.call_args.args[3] == "2008-04-09"

    @pytest.mark.asyncio
    async def test_giurisprudenza_articolo(self):
        from src.tools import italgiure
        from src.lib._result import SearchResult

        with patch.object(italgiure, "fetch_brocardi", new=AsyncMock(side_effect=RuntimeError("stop"))) as fb, \
             patch.object(italgiure, "_giurisprudenza_su_norma_impl",
                          new=AsyncMock(return_value=SearchResult(success=True, source="test"))):
            await italgiure._giurisprudenza_articolo_impl("art. 18 tusl")

        assert fb.call_args.args[:3] == ("decreto legislativo", "18", "81")
        assert fb.call_args.args[3] == "2008-04-09"

"""Unit tests for Corte Costituzionale (Constitutional Court) client and tools.

No real network calls. The bulk open-data bundles are simulated with a TINY
in-memory double-nested latin-1 ZIP built from a few hand-written records that
mirror the real upstream shapes (latin-1 encoding, &#13;/\\r\\n artefacts,
inconsistent inner-ZIP casing, parametri on massime). _download is mocked to
return that bundle, so the full download -> unzip -> latin-1 decode -> cache
-> parse pipeline is exercised without touching the network.

A small @pytest.mark.live test (skipped by default) hits the real source for
optional E2E verification.
"""

import io
import json
import os
import zipfile
from unittest.mock import AsyncMock, patch

import pytest

from src.lib._result import SearchResult
from src.lib.corte_cost.client import (
    TIPOLOGIE,
    MassimaCost,
    ParametroNorma,
    PronunciaCost,
    _clean,
    _dep_sort_key,
    _decade_for_year,
    _parametro_matches,
    _parse_massima,
    _parse_parametro,
    _parse_pronuncia,
    _parse_fonte,
    _parse_riferimento,
    _PRONUNCE_DECADES,
    _MASSIME_DECADES,
    _unzip_decade,
    _PRONUNCE_YEAR_ZIP,
    _PRONUNCE_YEAR_JSON,
    _PRONUNCE_ROOT_KEY,
    _MASSIME_YEAR_ZIP,
    _MASSIME_YEAR_JSON,
    _MASSIME_ROOT_KEY,
    fetch_pronuncia,
    format_full,
    format_massima_hit,
    format_result,
    pronunce_su_norma,
    search_pronunce,
    ultime_pronunce,
)
from src.tools.corte_cost import (
    _cerca_pronuncia_costituzionale_impl,
    _leggi_pronuncia_costituzionale_impl,
    leggi_pronuncia_costituzionale,
    _pronunce_cost_su_norma_impl,
    _ultime_pronunce_cost_impl,
)


# ---------------------------------------------------------------------------
# Fixture data — tiny, hand-written, modelled on real upstream records.
# Year 1956 used so we can also (optionally) cross-check against live data.
# ---------------------------------------------------------------------------

# Two pronunce: one sentenza (S), one ordinanza (O). Note the &#13; entity and
# accented chars to exercise latin-1 decode + _clean(). Deposito dates differ so
# we can assert the deposit-date sort order.
_PRONUNCE_1956 = {
    "elenco_pronunce": [
        {
            "numero_pronuncia": "1",
            "anno_pronuncia": "1956",
            "data_decisione": "05/06/1956",
            "data_deposito": "14/06/1956",
            "ecli": "ECLI:IT:COST:1956:1",
            "tipologia_pronuncia": "S",
            "epigrafe": "ha pronunciato la seguente&#13;questione di legittimità  costituzionale",
            "testo": "Ritenuto in fatto:\r\n  la questione di legittimità costituzionale dell'art. 113.",
            "dispositivo": "per questi motivi\r\n  LA CORTE dichiara l'illegittimità costituzionale.",
            "collegio": "Avv. ENRICO DE NICOLA, Presidente",
            "presidente": "DE NICOLA",
            "relatore_pronuncia": "Gaetano Azzariti",
            "redattore_pronuncia": "",
        },
        {
            "numero_pronuncia": "23",
            "anno_pronuncia": "1956",
            "data_decisione": "18/07/1956",
            "data_deposito": "21/07/1956",
            "ecli": "ECLI:IT:COST:1956:23",
            "tipologia_pronuncia": "O",
            "epigrafe": "ordinanza sulla perequazione delle pensioni",
            "testo": "Testo dell'ordinanza n. 23 con accenti: però, città, perché.",
            "dispositivo": "dispone la restituzione degli atti.",
            "collegio": "",
            "presidente": "DE NICOLA",
            "relatore_pronuncia": "Mario Bracci",
            "redattore_pronuncia": "",
        },
    ]
}

# One massime archive entry for pronuncia 1/1956, with a massima invoking
# art. 23 legge n. 87 del 11/03/1953 as parameter.
_MASSIME_1956 = {
    "corte_costituzionale_archiviomassime": [
        {
            "numero_pronuncia": "1",
            "anno_pronuncia": "1956",
            "data_decisione": "05/06/1956",
            "data_deposito": "14/06/1956",
            "tipologia_pronuncia": "S",
            "tipologia_giudizio": "legittimità",
            "massime": [
                {
                    "numero": "1",
                    "titolo": "GIUDIZIO DI LEGITTIMITA' COSTITUZIONALE - INTERVENTO",
                    "testo": "La Corte è competente a giudicare le leggi anteriori alla Costituzione.",
                    "parametri": [
                        {
                            "descrizione": "legge",
                            "numero": "87",
                            "data": "11/03/1953",
                            "articolo": "23",
                            "comma": "",
                            "specificazione_articolo": "",
                            "specificazione_comma": "",
                        },
                        {
                            "descrizione": "costituzione",
                            "numero": "",
                            "data": "",
                            "articolo": "3",
                            "comma": "1",
                            "specificazione_articolo": "",
                            "specificazione_comma": "",
                        },
                    ],
                }
            ],
        }
    ]
}


def _make_bundle(year: int, payload: dict, year_zip_tmpl: str, year_json_tmpl: str) -> bytes:
    """Build a tiny DOUBLE-nested latin-1 ZIP mirroring the real distribution.

    outer.zip
      └─ <year_zip_tmpl>          (inner ZIP)
           └─ <year_json_tmpl>    (latin-1 JSON)
    """
    json_bytes = json.dumps(payload, ensure_ascii=False).encode("latin-1")

    inner_buf = io.BytesIO()
    with zipfile.ZipFile(inner_buf, "w", zipfile.ZIP_DEFLATED) as zi:
        zi.writestr(year_json_tmpl.format(year=year), json_bytes)
    inner_bytes = inner_buf.getvalue()

    outer_buf = io.BytesIO()
    with zipfile.ZipFile(outer_buf, "w", zipfile.ZIP_DEFLATED) as zo:
        zo.writestr(year_zip_tmpl.format(year=year), inner_bytes)
    return outer_buf.getvalue()


_PRONUNCE_BUNDLE = _make_bundle(
    1956, _PRONUNCE_1956, _PRONUNCE_YEAR_ZIP, _PRONUNCE_YEAR_JSON
)
_MASSIME_BUNDLE = _make_bundle(
    1956, _MASSIME_1956, _MASSIME_YEAR_ZIP, _MASSIME_YEAR_JSON
)


@pytest.fixture(autouse=True)
def _isolate_cache(tmp_path, monkeypatch):
    """Point the cache at a temp dir so tests never read/write the user cache."""
    monkeypatch.setenv("MCP_CACHE_DIR", str(tmp_path))
    yield


def _download_router(url: str) -> bytes:
    """Return the right tiny bundle based on which decade URL was requested."""
    if "/massime/" in url or "CC_M_" in url:
        return _MASSIME_BUNDLE
    return _PRONUNCE_BUNDLE


# ---------------------------------------------------------------------------
# Tests: _clean
# ---------------------------------------------------------------------------

class TestClean:
    def test_replaces_cr_entity(self):
        assert _clean("a&#13;b") == "a\nb"

    def test_normalises_crlf(self):
        assert _clean("a\r\nb") == "a\nb"

    def test_collapses_spaces(self):
        assert _clean("a    b") == "a b"

    def test_strips(self):
        assert _clean("  hello  ") == "hello"

    def test_empty(self):
        assert _clean("") == ""

    def test_none_safe(self):
        assert _clean(None) == ""


# ---------------------------------------------------------------------------
# Tests: decade resolution
# ---------------------------------------------------------------------------

class TestDecadeForYear:
    def test_pronunce_first_decade(self):
        assert _decade_for_year(1956, _PRONUNCE_DECADES) == "P_json1956_1980.zip"

    def test_pronunce_mid_decade(self):
        assert _decade_for_year(1990, _PRONUNCE_DECADES) == "P_json1981_2000.zip"

    def test_pronunce_recent(self):
        assert _decade_for_year(2024, _PRONUNCE_DECADES) == "P_json2001_oggi.zip"

    def test_massime_uses_different_filename(self):
        assert _decade_for_year(1956, _MASSIME_DECADES) == "CC_M_1956_1980_json.zip"
        assert _decade_for_year(2010, _MASSIME_DECADES) == "CC_M_2001_2015_json.zip"

    def test_out_of_range_returns_none(self):
        assert _decade_for_year(1900, _PRONUNCE_DECADES) is None


# ---------------------------------------------------------------------------
# Tests: _unzip_decade (the double-nested + latin-1 path)
# ---------------------------------------------------------------------------

class TestUnzipDecade:
    def test_pronunce_parsed(self):
        by_year = _unzip_decade(
            _PRONUNCE_BUNDLE, _PRONUNCE_YEAR_ZIP, _PRONUNCE_YEAR_JSON, _PRONUNCE_ROOT_KEY
        )
        assert 1956 in by_year
        assert len(by_year[1956]) == 2

    def test_latin1_accents_preserved(self):
        by_year = _unzip_decade(
            _PRONUNCE_BUNDLE, _PRONUNCE_YEAR_ZIP, _PRONUNCE_YEAR_JSON, _PRONUNCE_ROOT_KEY
        )
        # accented chars survive the latin-1 round-trip
        joined = json.dumps(by_year[1956], ensure_ascii=False)
        assert "città" in joined
        assert "perché" in joined

    def test_massime_parsed(self):
        by_year = _unzip_decade(
            _MASSIME_BUNDLE, _MASSIME_YEAR_ZIP, _MASSIME_YEAR_JSON, _MASSIME_ROOT_KEY
        )
        assert 1956 in by_year
        assert by_year[1956][0]["numero_pronuncia"] == "1"


# ---------------------------------------------------------------------------
# Tests: record parsers
# ---------------------------------------------------------------------------

class TestParsePronuncia:
    def test_basic_fields(self):
        p = _parse_pronuncia(_PRONUNCE_1956["elenco_pronunce"][0])
        assert isinstance(p, PronunciaCost)
        assert p.numero_pronuncia == "1"
        assert p.anno_pronuncia == "1956"
        assert p.ecli == "ECLI:IT:COST:1956:1"
        assert p.tipologia_pronuncia == "S"
        assert p.data_deposito == "14/06/1956"

    def test_cleans_epigrafe(self):
        p = _parse_pronuncia(_PRONUNCE_1956["elenco_pronunce"][0])
        assert "&#13;" not in p.epigrafe
        assert "\r" not in p.testo

    def test_missing_keys_safe(self):
        p = _parse_pronuncia({"numero_pronuncia": "5", "anno_pronuncia": "1960"})
        assert p.testo == ""
        assert p.presidente == ""


class TestParseParametro:
    def test_fields(self):
        param = _parse_parametro(_MASSIME_1956["corte_costituzionale_archiviomassime"][0]["massime"][0]["parametri"][0])
        assert isinstance(param, ParametroNorma)
        assert param.articolo == "23"
        assert param.numero == "87"
        assert param.descrizione == "legge"
        assert param.data == "11/03/1953"


class TestParseMassima:
    def test_fields_and_parametri(self):
        raw = _MASSIME_1956["corte_costituzionale_archiviomassime"][0]["massime"][0]
        m = _parse_massima(raw)
        assert isinstance(m, MassimaCost)
        assert m.numero == "1"
        assert len(m.parametri) == 2
        assert m.parametri[0].articolo == "23"


# ---------------------------------------------------------------------------
# Tests: reference parsing + parametro matching
# ---------------------------------------------------------------------------

class TestParseRiferimento:
    def test_article_and_act_number(self):
        assert _parse_riferimento("art. 23 legge 87/1953") == ("23", "87")

    def test_article_only(self):
        assert _parse_riferimento("articolo 3") == ("3", "")

    def test_art_with_n(self):
        assert _parse_riferimento("art. 5 d.lgs. n. 196") == ("5", "196")

    def test_bare_slash_act(self):
        art, atto = _parse_riferimento("legge 87/1953")
        assert atto == "87"

    def test_no_match(self):
        assert _parse_riferimento("qualcosa") == ("", "")


class TestParametroMatches:
    def _param(self):
        return ParametroNorma(descrizione="legge", numero="87", articolo="23")

    def test_match_article_and_number(self):
        assert _parametro_matches(self._param(), "23", "87")

    def test_match_article_only(self):
        assert _parametro_matches(self._param(), "23", "")

    def test_mismatch_article(self):
        assert not _parametro_matches(self._param(), "99", "")

    def test_mismatch_number(self):
        assert not _parametro_matches(self._param(), "", "999")

    def test_empty_criteria_no_match(self):
        assert not _parametro_matches(self._param(), "", "")


# ---------------------------------------------------------------------------
# Tests: deposit-date sort key
# ---------------------------------------------------------------------------

class TestDepSortKey:
    def test_orders_by_date(self):
        a = PronunciaCost(numero_pronuncia="1", anno_pronuncia="1956", data_deposito="14/06/1956")
        b = PronunciaCost(numero_pronuncia="23", anno_pronuncia="1956", data_deposito="21/07/1956")
        assert _dep_sort_key(b) > _dep_sort_key(a)

    def test_missing_date_safe(self):
        p = PronunciaCost(numero_pronuncia="1", anno_pronuncia="1956", data_deposito="")
        assert _dep_sort_key(p)[0] == (0, 0, 0)


# ---------------------------------------------------------------------------
# Tests: formatters
# ---------------------------------------------------------------------------

class TestFormatResult:
    def _doc(self):
        return _parse_pronuncia(_PRONUNCE_1956["elenco_pronunce"][0])

    def test_contains_number_and_year(self):
        text = format_result(self._doc())
        assert "1/1956" in text

    def test_contains_ecli(self):
        text = format_result(self._doc())
        assert "ECLI:IT:COST:1956:1" in text

    def test_sentenza_label(self):
        text = format_result(self._doc())
        assert "Sentenza" in text

    def test_ordinanza_label(self):
        doc = _parse_pronuncia(_PRONUNCE_1956["elenco_pronunce"][1])
        text = format_result(doc)
        assert "Ordinanza" in text


class TestFormatFull:
    def _doc(self):
        return _parse_pronuncia(_PRONUNCE_1956["elenco_pronunce"][0])

    def test_includes_sections(self):
        text = format_full(self._doc())
        assert "Epigrafe" in text
        assert "Testo" in text
        assert "Dispositivo" in text

    def test_truncates_long_text(self):
        doc = PronunciaCost(numero_pronuncia="1", anno_pronuncia="1956", testo="x" * 30000)
        text = format_full(doc)
        assert "troncato" in text

    def test_no_truncation_short(self):
        text = format_full(self._doc())
        assert "troncato" not in text

    def test_dispositivo_kept_whole_when_reasons_are_long(self):
        # Shape of sentenza 194/2018 in the Court's open data (read 2026-09-28):
        # epigrafe 1,469 + testo 106,851 + dispositivo 5,840 characters. The
        # dispositivo is a required part of the sentenza (art. 18, third
        # paragraph, l. 87/1953) and the one published with effect (art. 30
        # l. 87/1953; art. 136 Cost.): only the reasons may be cut.
        dispositivo = (
            "1) dichiara l'illegittimità costituzionale dell'art. 3, comma 1, del "
            "decreto legislativo 4 marzo 2015, n. 23 ... limitatamente alle parole "
            "«di importo pari a due mensilità dell'ultima retribuzione di riferimento "
            "per il calcolo del trattamento di fine rapporto per ogni anno di servizio,»"
        )
        dispositivo = dispositivo + " " + "d" * (5840 - len(dispositivo) - 2) + " Z"
        doc = PronunciaCost(
            numero_pronuncia="194",
            anno_pronuncia="2018",
            tipologia_pronuncia="S",
            epigrafe="e" * 1469,
            testo="Ritenuto in fatto " + "t" * 106833,
            dispositivo=dispositivo,
        )
        text = format_full(doc)
        assert "## Dispositivo\n" + dispositivo in text
        assert text.rstrip().endswith(" Z")
        assert "e" * 1469 in text
        head, tail = text.split("## Dispositivo", 1)
        # The truncation note belongs to the reasons, before the dispositivo.
        assert "Testo della motivazione troncato" in head
        assert "troncato" not in tail
        # Total body stays within the cap: the reasons get what is left.
        body = text.split("## Epigrafe", 1)[1]
        assert len(body) < 25000 + 300

    def test_dispositivo_kept_when_epigrafe_is_long(self):
        # Shape of sentenza 1/1956: epigrafe 8,110 + testo 19,129 + dispositivo
        # 1,267 characters; the whole-body cut used to drop the dispositivo.
        doc = PronunciaCost(
            numero_pronuncia="1",
            anno_pronuncia="1956",
            epigrafe="e" * 8110,
            testo="t" * 19129,
            dispositivo="2. - Dichiara l'illegittimità costituzionale " + "d" * 1221,
        )
        text = format_full(doc)
        assert doc.dispositivo in text
        assert "troncato" in text

    def test_reasons_keep_a_floor_when_other_parts_are_huge(self):
        doc = PronunciaCost(
            numero_pronuncia="1",
            anno_pronuncia="2000",
            epigrafe="e" * 20000,
            testo="t" * 20000,
            dispositivo="d" * 10000,
        )
        text = format_full(doc)
        assert "d" * 10000 in text
        assert "t" * 5000 in text and "t" * 5001 not in text

    def test_short_decision_unchanged_order(self):
        text = format_full(self._doc())
        assert text.index("## Epigrafe") < text.index("## Testo") < text.index("## Dispositivo")


class TestFormatFullPaging:
    """da_carattere pages over the motivazione (testo): positions count its characters."""

    @staticmethod
    def _doc(testo_len=60000):
        # Position-unique text: character i of the motivazione is recoverable from the output.
        testo = "".join(f"[{i:06d}]" for i in range(testo_len // 8 + 1))[:testo_len]
        return PronunciaCost(
            numero_pronuncia="194",
            anno_pronuncia="2018",
            tipologia_pronuncia="S",
            ecli="ECLI:IT:COST:2018:194",
            epigrafe="e" * 1000,
            testo=testo,
            dispositivo="d" * 2000,
        )

    def test_default_cut_note_carries_the_resume_position(self):
        doc = self._doc()
        budget = 25000 - len("## Epigrafe\n" + doc.epigrafe) - len("## Dispositivo\n" + doc.dispositivo)
        text = format_full(doc)
        assert (
            f"*[Testo della motivazione troncato a {budget} caratteri su 60000: "
            "epigrafe e dispositivo sono riportati per intero; "
            f"per leggere il seguito ripetere la chiamata con da_carattere={budget + 1}]*"
        ) in text
        assert doc.testo[:budget].rstrip() in text
        assert doc.testo[budget : budget + 20] not in text

    def test_resume_position_returns_the_first_omitted_character(self):
        doc = self._doc()
        budget = 25000 - len("## Epigrafe\n" + doc.epigrafe) - len("## Dispositivo\n" + doc.dispositivo)
        text = format_full(doc, da_carattere=budget + 1)
        # Header kept, epigrafe and dispositivo not repeated, window starts right after the cut.
        assert text.startswith("# Sentenza Corte Costituzionale n. 194/2018\n**ECLI**: ECLI:IT:COST:2018:194")
        assert "## Epigrafe" not in text and "## Dispositivo" not in text
        window = text.split("## Testo\n", 1)[1]
        assert window.startswith(doc.testo[budget : budget + 40])
        assert (
            f"*[Caratteri della motivazione {budget + 1}-{budget + 25000} su 60000 totali: "
            f"per leggere il seguito ripetere la chiamata con da_carattere={budget + 25001}]*"
        ) in text

    def test_last_window_says_end_of_the_motivazione(self):
        doc = self._doc()
        text = format_full(doc, da_carattere=50001)
        assert doc.testo[50000:] in text
        assert text.rstrip().endswith("*[Caratteri della motivazione 50001-60000 su 60000 totali: fine della motivazione]*")

    def test_start_beyond_the_end(self):
        text = format_full(self._doc(), da_carattere=60001)
        assert "da_carattere=60001 oltre la fine della motivazione (60000 caratteri)" in text
        assert "## Testo" not in text

    def test_short_decision_unaffected_by_default(self):
        doc = self._doc(testo_len=3000)
        text = format_full(doc)
        assert "troncato" not in text and "da_carattere" not in text
        assert text.index("## Epigrafe") < text.index("## Testo") < text.index("## Dispositivo")


class TestFormatMassimaHit:
    def test_contains_parametri(self):
        m = _parse_massima(_MASSIME_1956["corte_costituzionale_archiviomassime"][0]["massime"][0])
        text = format_massima_hit("1", "1956", m)
        assert "1/1956" in text
        assert "art. 23" in text
        assert "n. 87" in text


# ---------------------------------------------------------------------------
# Tests: client-level pipeline (download mocked, cache exercised)
# ---------------------------------------------------------------------------

class TestSearchPronunce:
    @pytest.mark.asyncio
    async def test_finds_by_keyword(self):
        with patch("src.lib.corte_cost.client._download", AsyncMock(side_effect=_download_router)):
            results = await search_pronunce(
                terms=["illegittimità"], year_from=1956, year_to=1956, limit=10
            )
        assert len(results) == 1
        assert results[0].numero_pronuncia == "1"

    @pytest.mark.asyncio
    async def test_filters_by_tipo(self):
        with patch("src.lib.corte_cost.client._download", AsyncMock(side_effect=_download_router)):
            results = await search_pronunce(
                terms=[], tipo_code="O", year_from=1956, year_to=1956, limit=10
            )
        assert len(results) == 1
        assert results[0].tipologia_pronuncia == "O"

    @pytest.mark.asyncio
    async def test_no_keyword_returns_all(self):
        with patch("src.lib.corte_cost.client._download", AsyncMock(side_effect=_download_router)):
            results = await search_pronunce(terms=[], year_from=1956, year_to=1956, limit=10)
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_no_match(self):
        with patch("src.lib.corte_cost.client._download", AsyncMock(side_effect=_download_router)):
            results = await search_pronunce(
                terms=["inesistente_xyz"], year_from=1956, year_to=1956, limit=10
            )
        assert results == []


class TestCacheBehavior:
    @pytest.mark.asyncio
    async def test_download_called_once_then_cache_hit(self):
        mock = AsyncMock(side_effect=_download_router)
        with patch("src.lib.corte_cost.client._download", mock):
            await search_pronunce(terms=[], year_from=1956, year_to=1956, limit=10)
            first_calls = mock.call_count
            # second query in same year must hit the cache, not re-download
            await search_pronunce(terms=["pensioni"], year_from=1956, year_to=1956, limit=10)
        assert first_calls == 1
        assert mock.call_count == 1

    @pytest.mark.asyncio
    async def test_cache_file_written(self, tmp_path):
        mock = AsyncMock(side_effect=_download_router)
        with patch("src.lib.corte_cost.client._download", mock):
            await search_pronunce(terms=[], year_from=1956, year_to=1956, limit=10)
        cached = tmp_path / "corte_cost" / "pronunce" / "1956.json"
        assert cached.exists()
        data = json.loads(cached.read_text(encoding="utf-8"))
        assert len(data) == 2


class TestFetchPronuncia:
    @pytest.mark.asyncio
    async def test_found(self):
        with patch("src.lib.corte_cost.client._download", AsyncMock(side_effect=_download_router)):
            doc = await fetch_pronuncia(1, 1956)
        assert doc is not None
        assert doc.ecli == "ECLI:IT:COST:1956:1"

    @pytest.mark.asyncio
    async def test_not_found(self):
        with patch("src.lib.corte_cost.client._download", AsyncMock(side_effect=_download_router)):
            doc = await fetch_pronuncia(999, 1956)
        assert doc is None


class TestPronunceSuNorma:
    @pytest.mark.asyncio
    async def test_matches_invoked_norm(self):
        with patch("src.lib.corte_cost.client._download", AsyncMock(side_effect=_download_router)):
            hits = await pronunce_su_norma("art. 23 legge 87/1953", year_from=1956, year_to=1956)
        assert len(hits) == 1
        numero, anno, massima = hits[0]
        assert numero == "1"
        assert anno == "1956"
        assert isinstance(massima, MassimaCost)

    @pytest.mark.asyncio
    async def test_matches_constitution_article(self):
        with patch("src.lib.corte_cost.client._download", AsyncMock(side_effect=_download_router)):
            hits = await pronunce_su_norma("art. 3", year_from=1956, year_to=1956)
        assert len(hits) == 1

    @pytest.mark.asyncio
    async def test_no_match_for_other_norm(self):
        with patch("src.lib.corte_cost.client._download", AsyncMock(side_effect=_download_router)):
            hits = await pronunce_su_norma("art. 999 legge 5000/2050", year_from=1956, year_to=1956)
        assert hits == []

    @pytest.mark.asyncio
    async def test_unparseable_reference_returns_empty(self):
        with patch("src.lib.corte_cost.client._download", AsyncMock(side_effect=_download_router)):
            hits = await pronunce_su_norma("qualcosa di vago", year_from=1956, year_to=1956)
        assert hits == []


class TestUltimePronunce:
    @pytest.mark.asyncio
    async def test_sorted_by_deposit_desc(self):
        with patch("src.lib.corte_cost.client._download", AsyncMock(side_effect=_download_router)):
            # current_year=1956 so it scans our fixture year
            results = await ultime_pronunce(tipo_code="", current_year=1956, limit=10)
        assert len(results) == 2
        # ordinanza n.23 (21/07) deposited after sentenza n.1 (14/06)
        assert results[0].numero_pronuncia == "23"


# ---------------------------------------------------------------------------
# Tests: TIPOLOGIE constant
# ---------------------------------------------------------------------------

class TestConstants:
    def test_sentenza(self):
        assert TIPOLOGIE["sentenza"] == "S"

    def test_ordinanza(self):
        assert TIPOLOGIE["ordinanza"] == "O"

    def test_tutte_empty(self):
        assert TIPOLOGIE["tutte"] == ""


# ---------------------------------------------------------------------------
# Tests: tool impl wrappers (SearchResult shape, errors, fail-safe)
# ---------------------------------------------------------------------------

class TestCercaImpl:
    @pytest.mark.asyncio
    async def test_returns_results(self):
        with patch("src.lib.corte_cost.client._download", AsyncMock(side_effect=_download_router)):
            result = await _cerca_pronuncia_costituzionale_impl(
                "illegittimità", anno_da=1956, anno_a=1956
            )
        assert isinstance(result, SearchResult)
        assert result.success
        assert "Trovate" in result.results_text
        assert "1/1956" in result.results_text
        # Explicit years: the header does not claim a restricted scope.
        assert "solo anno" not in result.results_text

    @pytest.mark.asyncio
    async def test_results_without_years_declare_the_current_year(self, monkeypatch):
        # Without anno_da/anno_a only the current year is searched: "Trovate N pronunce" alone
        # reads as the whole archive, so the header says which year it covered.
        monkeypatch.setenv("LEGAL_TODAY", "1956-12-31")
        with patch("src.lib.corte_cost.client._download", AsyncMock(side_effect=_download_router)):
            result = await _cerca_pronuncia_costituzionale_impl("illegittimità")
        assert result.success
        header = result.results_text.split("\n### ", 1)[0]
        assert "solo anno 1956" in header
        assert "anno_da/anno_a" in header

    @pytest.mark.asyncio
    async def test_no_results(self):
        with patch("src.lib.corte_cost.client._download", AsyncMock(side_effect=_download_router)):
            result = await _cerca_pronuncia_costituzionale_impl(
                "inesistente_xyz", anno_da=1956, anno_a=1956
            )
        assert isinstance(result, SearchResult)
        assert not result.success
        assert result.error_type == "no_results"
        assert "Nessuna" in result.to_str()

    @pytest.mark.asyncio
    async def test_source_down(self):
        with patch(
            "src.lib.corte_cost.client._download",
            AsyncMock(side_effect=RuntimeError("network down")),
        ):
            result = await _cerca_pronuncia_costituzionale_impl(
                "x", anno_da=1956, anno_a=1956
            )
        assert isinstance(result, SearchResult)
        assert not result.success
        assert result.error_type == "source_down"
        assert "Errore" in result.to_str()

    @pytest.mark.asyncio
    async def test_max_risultati_capped(self):
        with patch("src.lib.corte_cost.client._download", AsyncMock(side_effect=_download_router)):
            result = await _cerca_pronuncia_costituzionale_impl(
                "", anno_da=1956, anno_a=1956, max_risultati=999
            )
        assert isinstance(result, SearchResult)
        assert result.success


class TestLeggiImpl:
    @pytest.mark.asyncio
    async def test_full_text(self):
        with patch("src.lib.corte_cost.client._download", AsyncMock(side_effect=_download_router)):
            result = await _leggi_pronuncia_costituzionale_impl(1, 1956)
        assert isinstance(result, SearchResult)
        assert result.success
        assert "ECLI:IT:COST:1956:1" in result.results_text
        assert "Dispositivo" in result.results_text

    @pytest.mark.asyncio
    async def test_not_found(self):
        with patch("src.lib.corte_cost.client._download", AsyncMock(side_effect=_download_router)):
            result = await _leggi_pronuncia_costituzionale_impl(999, 1956)
        assert isinstance(result, SearchResult)
        assert not result.success
        assert result.error_type == "no_results"
        assert "non trovata" in result.to_str()

    @pytest.mark.asyncio
    async def test_source_down(self):
        with patch(
            "src.lib.corte_cost.client._download",
            AsyncMock(side_effect=RuntimeError("boom")),
        ):
            result = await _leggi_pronuncia_costituzionale_impl(1, 1956)
        assert not result.success
        assert result.error_type == "source_down"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("bad", [0, -5, "1", 1.5, True])
    async def test_invalid_da_carattere_errors_without_network(self, bad):
        download = AsyncMock(side_effect=_download_router)
        with patch("src.lib.corte_cost.client._download", download):
            result = await _leggi_pronuncia_costituzionale_impl(1, 1956, bad)
        assert not result.success
        assert result.error_type == "bad_input"
        assert "da_carattere deve essere un intero maggiore o uguale a 1" in result.results_text
        download.assert_not_called()

    @pytest.mark.asyncio
    async def test_da_carattere_is_threaded_to_the_formatter(self):
        long_doc = PronunciaCost(
            numero_pronuncia="1", anno_pronuncia="1956", epigrafe="E", testo="t" * 30000, dispositivo="D"
        )
        with patch("src.tools.corte_cost.fetch_pronuncia", AsyncMock(return_value=long_doc)):
            first = await _leggi_pronuncia_costituzionale_impl(1, 1956)
            window = await _leggi_pronuncia_costituzionale_impl(1, 1956, 24990)
        # budget = 25000 - len("## Epigrafe\nE") - len("## Dispositivo\nD") = 24971
        assert "da_carattere=24972]*" in first.results_text
        assert "Caratteri della motivazione 24990-30000 su 30000 totali: fine della motivazione" in window.results_text

    @pytest.mark.asyncio
    async def test_mcp_tool_accepts_da_carattere(self):
        long_doc = PronunciaCost(
            numero_pronuncia="1", anno_pronuncia="1956", epigrafe="E", testo="t" * 30000, dispositivo="D"
        )
        with patch("src.tools.corte_cost.fetch_pronuncia", AsyncMock(return_value=long_doc)):
            out = await leggi_pronuncia_costituzionale(1, 1956, da_carattere=26001)
            bad = await leggi_pronuncia_costituzionale(1, 1956, da_carattere=0)
        assert "Caratteri della motivazione 26001-30000 su 30000 totali: fine della motivazione" in out
        assert "da_carattere deve essere un intero" in bad


class TestSuNormaImpl:
    @pytest.mark.asyncio
    async def test_returns_hits(self):
        with patch("src.lib.corte_cost.client._download", AsyncMock(side_effect=_download_router)):
            result = await _pronunce_cost_su_norma_impl(
                "art. 23 legge 87/1953", anno_da=1956, anno_a=1956
            )
        assert isinstance(result, SearchResult)
        assert result.success
        assert "invocano" in result.results_text
        assert "art. 23" in result.results_text

    @pytest.mark.asyncio
    async def test_no_hits(self):
        with patch("src.lib.corte_cost.client._download", AsyncMock(side_effect=_download_router)):
            result = await _pronunce_cost_su_norma_impl(
                "art. 999 legge 5000/2050", anno_da=1956, anno_a=1956
            )
        assert not result.success
        assert result.error_type == "no_results"

    @pytest.mark.asyncio
    async def test_source_down(self):
        with patch(
            "src.lib.corte_cost.client._download",
            AsyncMock(side_effect=RuntimeError("boom")),
        ):
            result = await _pronunce_cost_su_norma_impl(
                "art. 23 legge 87/1953", anno_da=1956, anno_a=1956
            )
        assert not result.success
        assert result.error_type == "source_down"


class TestUltimeImpl:
    @pytest.mark.asyncio
    async def test_returns_latest(self):
        # Pin the clock to the fixture year. The tool reads the calendar through
        # src/lib/_clock.py, so LEGAL_TODAY is what freezes it.
        with patch.dict(os.environ, {"LEGAL_TODAY": "1956-12-31"}), patch(
            "src.lib.corte_cost.client._download", AsyncMock(side_effect=_download_router)
        ):
            result = await _ultime_pronunce_cost_impl()
        assert isinstance(result, SearchResult)
        assert result.success
        assert "Ultime pronunce" in result.results_text

    @pytest.mark.asyncio
    async def test_source_down(self):
        with patch(
            "src.lib.corte_cost.client._download",
            AsyncMock(side_effect=RuntimeError("boom")),
        ):
            result = await _ultime_pronunce_cost_impl()
        assert not result.success
        assert result.error_type == "source_down"


# ---------------------------------------------------------------------------
# Tests: pronunce_cost_su_norma - default year range and act type
# ---------------------------------------------------------------------------

def _param(descrizione: str, articolo: str, numero: str = "") -> dict:
    return {
        "descrizione": descrizione, "numero": numero, "data": "", "articolo": articolo,
        "comma": "", "specificazione_articolo": "", "specificazione_comma": "",
    }


def _massime_entry(numero: str, anno: str, *parametri: dict) -> dict:
    return {
        "numero_pronuncia": numero, "anno_pronuncia": anno,
        "data_decisione": f"01/01/{anno}", "data_deposito": f"02/01/{anno}",
        "tipologia_pronuncia": "S", "tipologia_giudizio": "legittimità",
        "massime": [{
            "numero": "1", "titolo": f"MASSIMA {numero}/{anno}",
            "testo": "testo", "parametri": list(parametri),
        }],
    }


def _multi_year_massime_bundle(entries_by_year: dict[int, list[dict]]) -> bytes:
    """One outer ZIP with a nested per-year ZIP, like CC_M_2001_2015_json.zip."""
    outer_buf = io.BytesIO()
    with zipfile.ZipFile(outer_buf, "w", zipfile.ZIP_DEFLATED) as zo:
        for year, entries in entries_by_year.items():
            payload = {_MASSIME_ROOT_KEY: entries}
            inner_buf = io.BytesIO()
            with zipfile.ZipFile(inner_buf, "w", zipfile.ZIP_DEFLATED) as zi:
                zi.writestr(
                    _MASSIME_YEAR_JSON.format(year=year),
                    json.dumps(payload, ensure_ascii=False).encode("latin-1"),
                )
            zo.writestr(_MASSIME_YEAR_ZIP.format(year=year), inner_buf.getvalue())
    return outer_buf.getvalue()


# Shape of the 2001-oggi massime bundle read on 2026-09-28: the file is named
# "2001_2015" but holds one nested ZIP per year up to 2026. Numbers below are
# fixtures; the parameter descriptions are the ones in the Court's open data
# ("Costituzione", "statuto regione Sardegna", "norme integrative per i giudizi
# davanti alla Corte costituzionale (7/10/2008)").
_MASSIME_RECENT = _multi_year_massime_bundle({
    2015: [_massime_entry("1", "2015", _param("Costituzione", "3"))],
    2018: [
        _massime_entry("6", "2018", _param(
            "norme integrative per i giudizi davanti alla Corte costituzionale (7/10/2008)", "3")),
        _massime_entry("17", "2018", _param("statuto regione Sardegna", "3")),
        _massime_entry("20", "2018", _param("Costituzione", "3")),
    ],
    2026: [
        _massime_entry("1", "2026", _param("Costituzione", "3")),
        _massime_entry("2", "2026", _param("direttiva UE", "3", "2016")),
    ],
})


def _download_recent(url: str) -> bytes:
    return _MASSIME_RECENT


class TestPronunceSuNormaRecentYears:
    @pytest.mark.asyncio
    async def test_default_range_starts_from_current_year(self):
        # Corte costituzionale open data: the massime bundle runs to the current
        # year (26 nested years, 2001-2026, read 2026-09-28), not to 2015 as the
        # bundle file name suggests. With no years the most recent massime must
        # come first: 1/2026, not 1/2015.
        with patch("src.lib.corte_cost.client._download", AsyncMock(side_effect=_download_recent)):
            hits = await pronunce_su_norma(
                "art. 3 Costituzione", year_from=0, year_to=0, limit=10, current_year=2026
            )
        assert [(n, a) for n, a, _ in hits][0] == ("1", "2026")
        assert {a for _, a, _ in hits} == {"2026", "2018", "2015"}

    @pytest.mark.asyncio
    async def test_default_range_uses_the_pinned_clock(self):
        with patch.dict(os.environ, {"LEGAL_TODAY": "2026-09-29"}), patch(
            "src.lib.corte_cost.client._download", AsyncMock(side_effect=_download_recent)
        ):
            result = await _pronunce_cost_su_norma_impl("art. 3 Costituzione")
        assert result.success
        text = result.results_text
        assert "pronuncia n. 1/2026" in text
        assert text.index("pronuncia n. 1/2026") < text.index("pronuncia n. 1/2015")

    @pytest.mark.asyncio
    async def test_costituzione_excludes_statuto_and_norme_integrative(self):
        # Reference names the Constitution: art. 3 of a statuto speciale or of
        # the norme integrative is another act (open data parametri[].descrizione).
        with patch("src.lib.corte_cost.client._download", AsyncMock(side_effect=_download_recent)):
            hits = await pronunce_su_norma(
                "art. 3 Costituzione", year_from=2018, year_to=2018, limit=50
            )
        assert [n for n, _, _ in hits] == ["20"]

    @pytest.mark.asyncio
    async def test_cost_abbreviation_is_the_constitution_too(self):
        with patch("src.lib.corte_cost.client._download", AsyncMock(side_effect=_download_recent)):
            hits = await pronunce_su_norma(
                "art. 3 Cost.", year_from=2018, year_to=2018, limit=50
            )
        assert [n for n, _, _ in hits] == ["20"]

    @pytest.mark.asyncio
    async def test_statuto_reference_selects_only_statuti(self):
        with patch("src.lib.corte_cost.client._download", AsyncMock(side_effect=_download_recent)):
            hits = await pronunce_su_norma(
                "art. 3 statuto Sardegna", year_from=2018, year_to=2018, limit=50
            )
        assert [n for n, _, _ in hits] == ["17"]

    @pytest.mark.asyncio
    async def test_reference_without_act_type_matches_any_act(self):
        with patch("src.lib.corte_cost.client._download", AsyncMock(side_effect=_download_recent)):
            hits = await pronunce_su_norma(
                "art. 3", year_from=2018, year_to=2018, limit=50
            )
        assert sorted(n for n, _, _ in hits) == ["17", "20", "6"]

    @pytest.mark.asyncio
    async def test_impl_declares_when_the_act_is_not_named(self):
        with patch("src.lib.corte_cost.client._download", AsyncMock(side_effect=_download_recent)):
            vague = await _pronunce_cost_su_norma_impl("art. 3", anno_da=2018, anno_a=2018)
            named = await _pronunce_cost_su_norma_impl(
                "art. 3 Costituzione", anno_da=2018, anno_a=2018
            )
        assert "non indica l'atto" in vague.results_text
        assert "non indica l'atto" not in named.results_text


class TestParseFonte:
    @pytest.mark.parametrize("riferimento, fonte", [
        ("art. 3 Costituzione", "costituzione"),
        ("art. 3 Cost.", "costituzione"),
        ("art. 23 legge 87/1953", "legge"),
        ("art. 23 l. 87/1953", "legge"),
        ("art. 5 d.lgs. n. 196", "decreto_legislativo"),
        ("art. 1 d.l. 454", "decreto_legge"),
        ("art. 8 D.P.R. 1074", "dpr"),
        ("art. 2 l. cost. 1/1948", "legge_costituzionale"),
        ("art. 3 statuto Sardegna", "statuto"),
        ("art. 6 CEDU", "cedu"),
        ("art. 107 TFUE", "tfue"),
        ("art. 117", ""),
        ("qualcosa", ""),
    ])
    def test_act_type(self, riferimento, fonte):
        assert _parse_fonte(riferimento) == fonte

    def test_legge_does_not_match_legge_costituzionale(self):
        param = ParametroNorma(descrizione="legge costituzionale", numero="1", articolo="2")
        assert not _parametro_matches(param, "2", "1", "legge")
        assert _parametro_matches(param, "2", "1", "legge_costituzionale")

    def test_costituzione_case_insensitive_description(self):
        # The fixture data spells it lowercase ("costituzione").
        param = ParametroNorma(descrizione="costituzione", articolo="3")
        assert _parametro_matches(param, "3", "", "costituzione")


# ---------------------------------------------------------------------------
# Optional live E2E (skipped by default; hits the real open-data source)
# ---------------------------------------------------------------------------

@pytest.mark.live
class TestLive:
    @pytest.mark.asyncio
    async def test_fetch_real_pronuncia_1_1956(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MCP_CACHE_DIR", str(tmp_path))
        doc = await fetch_pronuncia(1, 1956)
        assert doc is not None
        assert doc.ecli == "ECLI:IT:COST:1956:1"
        assert doc.tipologia_pronuncia == "S"
        assert len(doc.testo) > 100

    @pytest.mark.asyncio
    async def test_real_su_norma(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MCP_CACHE_DIR", str(tmp_path))
        hits = await pronunce_su_norma("art. 23 legge 87/1953", year_from=1956, year_to=1956)
        assert len(hits) >= 1

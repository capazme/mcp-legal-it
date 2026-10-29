"""Corte dei conti (issue #51, LI-054): deliberazioni of the control sections.

The fixtures in tests/fixtures/corte_conti/ are trimmed copies of the REAL answers of the
banca dati on 2026-10-29. The site's configuration is stored with its two credential values
replaced by "<scrubbed>": the tests put made-up values back in memory only, and check that
they never come out of the client (answers, errors, logs, replay tapes).
Every request goes through an httpx.MockTransport.
"""

from __future__ import annotations

import base64
import gzip
import importlib.util
import json
import logging
import time
from pathlib import Path

import httpx
import pytest

from mcp_legal_it import api
from mcp_legal_it.core import _http as core_http
from mcp_legal_it.lib.corte_conti import client as cc
from mcp_legal_it.tools.corte_conti import (
    _cerca_deliberazioni_corte_conti_impl,
    _leggi_deliberazione_corte_conti_impl,
    _ultime_deliberazioni_corte_conti_impl,
)

REPO = Path(__file__).resolve().parents[2]
FIXTURES = REPO / "tests" / "fixtures" / "corte_conti"

# Made-up credentials: they exist only in this file and in memory during the tests.
UTENTE, PASSWORD = "utente-di-prova", "segreto-di-prova-123"
BASIC = "Basic " + base64.b64encode(f"{UTENTE}:{PASSWORD}".encode()).decode()
SEGRETI = (UTENTE, PASSWORD, BASIC.split()[1])


def _fixture(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _config(**override) -> dict:
    cfg = _fixture("configuration.json")
    cfg.update({"USER_IIT_PR": UTENTE, "PWD_IIT_PR": PASSWORD})
    cfg.update(override)
    return cfg


def _niente_segreti(testo: str) -> None:
    for s in SEGRETI:
        assert s not in testo


class Banca:
    """A stand-in for the banca dati: routes each request to a real captured answer."""

    def __init__(self, *, search_status: int = 200, rifiuti: int = 0, errore: int = 0):
        self.sent: list[httpx.Request] = []
        self.search_status = search_status
        self.rifiuti = rifiuti          # searches/details answered 401 before accepting (stale credentials)
        self.errore = errore            # status for every authenticated call (5xx), 0 = none
        self.config_letture = 0

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.sent.append(request)
        url = str(request.url)
        if url == cc.CONFIG_URL:
            self.config_letture += 1
            return httpx.Response(200, json=_config())
        if "/api/sservice/" in url:
            assert request.headers.get("Authorization") == BASIC
            if self.errore:
                return httpx.Response(self.errore, text="errore")
            if self.rifiuti and not url.endswith("/getBancheDatiChannelList/public"):
                self.rifiuti -= 1
                return httpx.Response(401, text="Unauthorized")
        else:
            assert "Authorization" not in request.headers, f"credentials sent to a public endpoint: {url}"
        if url.endswith("/getBancheDatiChannelList/public"):
            return httpx.Response(200, json=_fixture("channels.json"))
        if "/getDistinctMetadata/deliberazioni_pu/BDC_ORG_EMITTENTE/" in url:
            return httpx.Response(200, json=_fixture("organi_emittenti.json"))
        if url.endswith("/execFullTextSearch/public"):
            if self.search_status != 200:
                return httpx.Response(self.search_status)
            body = json.loads(request.content)
            campi = {c["name"] for c in body["customField"]}
            if "BDC_ORG_EMITTENTE" in campi:
                return httpx.Response(200, json=_fixture("search_numero_29_2025_campania.json"))
            if "BDC_NUMERO_ID_LOCALE" in campi:
                return httpx.Response(200, json=_fixture("search_numero_29_2025.json"))
            if body.get("sortField"):
                return httpx.Response(200, json=_fixture("search_ultime.json"))
            if "xqzvwkjrpt" in body["query"]:
                return httpx.Response(200, json=_fixture("search_nessun_risultato.json"))
            return httpx.Response(200, json=_fixture("search_rinnovo_tacito.json"))
        if url.endswith("/getCidFromKey"):
            if json.loads(request.content)["search_key"] == "SRCCAM/29/2025/PREV":
                return httpx.Response(200, json=_fixture("cid_SRCCAM_29_2025.json"))
            return httpx.Response(200, json=_fixture("es_nessun_risultato.json"))
        if url.endswith("/getKmDocumentDetail/public"):
            return httpx.Response(200, json=_fixture("dettaglio_SRCCAM_29_2025.json"))
        return httpx.Response(404, text="not found")

    def factory(self, fonte, **kwargs):
        assert fonte == "corte_conti"
        return httpx.AsyncClient(transport=httpx.MockTransport(self.handler), **kwargs)

    def payloads(self, suffix: str) -> list[dict]:
        return [json.loads(r.content) for r in self.sent if str(r.url).endswith(suffix)]


@pytest.fixture(autouse=True)
def _stato_pulito(monkeypatch):
    async def no_sleep(_seconds):
        return None

    monkeypatch.setattr("mcp_legal_it.lib._http.asyncio.sleep", no_sleep)
    cc.azzera()
    yield
    cc.azzera()


# ---------------------------------------------------------------------------
# Configuration and credentials
# ---------------------------------------------------------------------------


class TestConfigurazione:
    def test_the_secrets_leave_the_config_and_hide_in_the_access(self):
        acc = cc.leggi_configurazione(_config())
        assert "USER_IIT_PR" not in acc.config and "PWD_IIT_PR" not in acc.config
        assert acc.intestazioni()["Authorization"] == BASIC
        for shown in (repr(acc), str(acc), json.dumps(acc.config)):
            _niente_segreti(shown)

    def test_a_missing_key_is_an_unexpected_page(self):
        cfg = _config()
        del cfg["IIT_EXEC_FULLTEXT_SEARCH_PU"]
        with pytest.raises(cc.CorteContiPaginaInattesa, match="voci attese"):
            cc.leggi_configurazione(cfg)

    def test_scrubbed_credentials_are_refused(self):
        cfg = _config(USER_IIT_PR="", PWD_IIT_PR="")
        with pytest.raises(cc.CorteContiPaginaInattesa, match="credenziali"):
            cc.leggi_configurazione(cfg)

    @pytest.mark.parametrize("chiave,valore", [
        ("IIT_API_SECURE_SERVICE_URL", "http://corteconti-iit.almawave.cloud/api/sservice/"),
        ("IIT_API_SERVICE_URL", "https://example.org/api/service/"),
        ("IIT_API_PORTAL_SERVICE_URL", "https://corteconti-iit.almawave.cloud.example.org/api/portal/"),
        ("SERVER_PUBLIC_BASIC_URL", "https://example.org/"),
    ])
    def test_an_address_off_the_source_hosts_is_refused(self, chiave, valore):
        # Neither a request nor a link shown to the lawyer may leave the Court's two hosts.
        with pytest.raises(cc.CorteContiPaginaInattesa, match="fuori dagli host"):
            cc.leggi_configurazione(_config(**{chiave: valore}))

    def test_scrub_body_replaces_every_secret_of_the_configuration(self):
        body = json.dumps(_config(KEYCLOAK_DATA={"realm": "x"})).encode()
        out = cc.scrub_body(cc.CONFIG_URL, body).decode()
        _niente_segreti(out)
        dati = json.loads(out)
        assert dati["USER_IIT_PR"] == dati["PWD_IIT_PR"] == dati["KEYCLOAK_DATA"] == "<scrubbed>"
        assert dati["IIT_API_SECURE_SERVICE_URL"].startswith("https://")

    def test_scrub_body_leaves_other_answers_alone(self):
        body = b'{"USER_IIT_PR": "x"}'
        assert cc.scrub_body("https://corteconti-iit.almawave.cloud/api/sservice/x", body) == body

    def test_the_stored_fixtures_hold_no_credential(self):
        for path in FIXTURES.iterdir():
            text = path.read_text(encoding="utf-8")
            assert "Basic " not in text and "Authorization" not in text, path.name
        cfg = _fixture("configuration.json")
        assert cfg["USER_IIT_PR"] == cfg["PWD_IIT_PR"] == "<scrubbed>"

    def test_requests_are_serial_and_spaced(self):
        politica = core_http.politica("corte_conti")
        assert politica.concorrenza == 1 and politica.intervallo >= 1.0
        assert core_http.HOST_PER_FONTE["corte_conti"] == {"banchedati.corteconti.it", "corteconti-iit.almawave.cloud"}


# ---------------------------------------------------------------------------
# Query and payload
# ---------------------------------------------------------------------------


class TestQuery:
    @pytest.mark.parametrize("testo,attesa", [
        ("rinnovo tacito", "rinnovo AND tacito"),
        ("  rinnovo   tacito convenzione ", "rinnovo AND tacito AND convenzione"),
        ("", "*"),
        ("art. 7 l. 131/2003", 'art. AND 7 AND l. AND "131\\/2003"'),
        ('"fondo"', '"\\"fondo\\""'),
    ])
    def test_all_the_words_with_reserved_characters_escaped(self, testo, attesa):
        assert cc.query_testuale(testo) == attesa

    @pytest.mark.parametrize("testo", ["rinnovo or proroga", "NOT proroga", "a AND b"])
    def test_boolean_words_are_refused_as_the_site_does(self, testo):
        with pytest.raises(ValueError, match="and"):
            cc.query_testuale(testo)

    def test_linear_time_on_long_input(self):
        for testo in ("a" * 20_000, "&|" * 10_000, "(" * 20_000, "<" * 20_000):
            start = time.perf_counter()
            cc.query_testuale(testo)
            cc._pulisci(testo)
            assert time.perf_counter() - start < 0.1

    def test_the_payload_asks_the_deliberazioni_only_light_and_at_most_five(self):
        acc = cc.leggi_configurazione(_config())
        acc.canale = "3349"
        p = cc.build_search_payload(acc, "rinnovo tacito", numero="29", anno="2025",
                                    organo="Sezione Controllo Regione Campania", n=50)
        assert p["channels"] == ["3349"]
        assert p["numberOfDocumentToRetrieve"] == cc.MAX_DOCUMENTI == 5
        assert p["noEntity"] is True and p["noConcept"] is True and p["entitySearch"] is False
        assert {c["name"] for c in p["customField"]} == {"BDC_NUMERO_ID_LOCALE", "BDC_ANNO", "BDC_ORG_EMITTENTE"}
        assert "sortField" not in p
        assert cc.build_search_payload(acc, per_data=True)["sortField"] == "BDC_DT_DEPOSITO_DEL"

    @pytest.mark.parametrize("campo,valore", [("numero", "29a"), ("anno", "duemila"), ("anno", "1234567")])
    def test_number_and_year_must_be_integers(self, campo, valore):
        acc = cc.leggi_configurazione(_config())
        with pytest.raises(ValueError, match=campo):
            cc.build_search_payload(acc, **{campo: valore})


class TestSezione:
    ORGANI = [b["key"] for b in _fixture("organi_emittenti.json")["aggregations"]["distinct_custom_field"]["buckets"]]

    def test_part_of_the_name_names_the_section(self):
        assert cc.risolvi_organo("Campania", self.ORGANI) == "Sezione Controllo Regione Campania"
        assert cc.risolvi_organo("sezione controllo regione campania", self.ORGANI) == "Sezione Controllo Regione Campania"

    def test_an_ambiguous_name_lists_the_choices(self):
        with pytest.raises(ValueError, match="ambigua") as info:
            cc.risolvi_organo("Trentino", self.ORGANI)
        assert "Bolzano" in str(info.value) and "Trento" in str(info.value)

    def test_an_unknown_section_is_an_error(self):
        with pytest.raises(ValueError, match="non riconosciuta"):
            cc.risolvi_organo("Atlantide", self.ORGANI)


# ---------------------------------------------------------------------------
# Parsing real answers
# ---------------------------------------------------------------------------


def _acc():
    acc = cc.leggi_configurazione(_config())
    acc.canale = "3349"
    return acc


class TestParse:
    def test_search_on_a_theme(self):
        risultati, totale = cc.parse_search(_fixture("search_rinnovo_tacito.json"), _acc())
        assert totale == 322 and len(risultati) == 5
        primo = risultati[0]
        assert primo.id_locale == "SCCLEG/7/2012/PREV"
        assert primo.numero == "7" and primo.anno == "2012" and primo.data_deposito == "23/03/2012"
        assert "<b>" not in primo.frammento and "rinnovo tacito" in primo.frammento
        assert primo.chiave.startswith("km_doc_it_idx/push/")
        assert primo.url_pdf == ("https://corteconti-iit.almawave.cloud/api/portal/downloadDocument/"
                                 "deliberazioni_pu/SCCLEG/7/2012/PREV")

    def test_an_empty_search(self):
        assert cc.parse_search(_fixture("search_nessun_risultato.json"), _acc()) == ([], 0)

    @pytest.mark.parametrize("dati", [{"altro": 1}, {"searchResult": {"documents": ["x"]}},
                                      {"searchResult": {"documents": {"a": 1}}}])
    def test_an_unexpected_answer_is_an_error(self, dati):
        with pytest.raises(cc.CorteContiPaginaInattesa):
            cc.parse_search(dati, _acc())

    def test_the_detail(self):
        d = cc.parse_dettaglio(_fixture("dettaglio_SRCCAM_29_2025.json"), _acc(), "k")
        assert d.id_locale == "SRCCAM/29/2025/PREV"
        assert d.organo == "Sezione Controllo Regione Campania"
        assert d.data_adunanza == "22/01/2025" and d.data_deposito == "23/01/2025"
        assert d.presidente == "GRASSELLI ALFREDO" and d.relatori == ["DE SANTIS ALESSANDRO"]
        assert d.destinatari == ["Guardia di Finanza"]
        assert d.testo.startswith("Campania 29/2025/PREV") and "CORTE DEI CONTI" in d.testo
        assert d.url_scheda == "https://banchedati.corteconti.it/?docId=documentDetail/SRCCAM/29/2025/PREV"

    def test_the_text_is_read_in_windows(self):
        d = cc.parse_dettaglio(_fixture("dettaglio_SRCCAM_29_2025.json"), _acc())
        d.testo = d.testo * 2                      # over the 25000-character window
        primo = cc.format_deliberazione(d)
        assert "da_carattere=25001" in primo
        seguito = cc.format_deliberazione(d, 25001)
        assert d.testo[25000:25100] in seguito and "da_carattere=50001" in seguito
        assert "fine del testo" in cc.format_deliberazione(d, 50001)

    @pytest.mark.parametrize("ident,atteso", [
        ("srccam/29/2025/prev", "SRCCAM/29/2025/PREV"), (" SCE/191/2026/RGES ", "SCE/191/2026/RGES"),
    ])
    def test_local_id(self, ident, atteso):
        assert cc.normalizza_id(ident) == atteso

    @pytest.mark.parametrize("ident", ["29/2025", "SRCCAM/29/25/PREV", "../../etc/passwd", "SRCCAM/29/2025/PREV/x"])
    def test_a_malformed_id_is_refused(self, ident):
        with pytest.raises(ValueError, match="identificativo"):
            cc.normalizza_id(ident)


# ---------------------------------------------------------------------------
# Tools, end to end on the stand-in
# ---------------------------------------------------------------------------


class TestTools:
    async def test_search_by_theme(self):
        banca = Banca()
        with api.configurazione(client_factory=banca.factory):
            r = await _cerca_deliberazioni_corte_conti_impl("rinnovo tacito")
        assert r.success and r.num_found == 5
        assert "mostrate 5 su 322" in r.results_text and "SCCLEG/7/2012/PREV" in r.results_text
        (payload,) = banca.payloads("/execFullTextSearch/public")
        assert payload["query"] == "rinnovo AND tacito" and payload["numberOfDocumentToRetrieve"] == 5
        _niente_segreti(r.to_str())

    async def test_one_configuration_read_for_many_calls(self):
        banca = Banca()
        with api.configurazione(client_factory=banca.factory):
            await _cerca_deliberazioni_corte_conti_impl("rinnovo tacito")
            await _ultime_deliberazioni_corte_conti_impl()
        assert banca.config_letture == 1

    async def test_no_criteria_is_bad_input_without_a_request(self):
        banca = Banca()
        with api.configurazione(client_factory=banca.factory):
            r = await _cerca_deliberazioni_corte_conti_impl("  ")
        assert r.error_type == "bad_input" and not banca.sent

    async def test_nothing_found(self):
        banca = Banca()
        with api.configurazione(client_factory=banca.factory):
            r = await _cerca_deliberazioni_corte_conti_impl("xqzvwkjrpt")
        assert r.error_type == "no_results"

    async def test_an_empty_204_is_an_error_not_zero_results(self):
        banca = Banca(search_status=204)
        with api.configurazione(client_factory=banca.factory):
            r = await _cerca_deliberazioni_corte_conti_impl("rinnovo tacito")
        assert r.error_type == "source_error" and "204" in r.to_str()

    async def test_read_by_id(self):
        banca = Banca()
        with api.configurazione(client_factory=banca.factory):
            r = await _leggi_deliberazione_corte_conti_impl("SRCCAM/29/2025/PREV")
        assert r.success
        assert "Sezione Controllo Regione Campania, deliberazione n. 29/2025" in r.results_text
        assert "downloadDocument/deliberazioni_pu/SRCCAM/29/2025/PREV" in r.results_text
        assert "REPUBBLICA ITALIANA" in r.results_text
        # The id is looked up on the public endpoint; only the detail carries the credentials.
        assert [str(q.url).rsplit("/", 1)[-1] for q in banca.sent if "Authorization" in q.headers] == [
            "public", "public"]
        _niente_segreti(r.to_str())

    async def test_an_unknown_id_is_not_found(self):
        banca = Banca()
        with api.configurazione(client_factory=banca.factory):
            r = await _leggi_deliberazione_corte_conti_impl("SRCCAM/99999/2025/PREV")
        assert r.error_type == "no_results" and "nessuna deliberazione" in r.results_text

    async def test_a_number_used_by_many_sections_lists_them(self):
        banca = Banca()
        with api.configurazione(client_factory=banca.factory):
            r = await _leggi_deliberazione_corte_conti_impl(numero="29", anno="2025")
        assert r.success and "24 deliberazioni hanno il n. 29/2025" in r.results_text
        assert not banca.payloads("/getKmDocumentDetail/public")

    async def test_number_year_and_section_read_the_act(self):
        banca = Banca()
        with api.configurazione(client_factory=banca.factory):
            r = await _leggi_deliberazione_corte_conti_impl(numero="29", anno="2025", sezione="Campania")
        assert r.success and "SRCCAM/29/2025/PREV" in r.results_text and "### Testo" in r.results_text
        (ricerca,) = banca.payloads("/execFullTextSearch/public")
        assert {"name": "BDC_ORG_EMITTENTE", "type": "TEXT_TOKENIZED",
                "tokenText": ["Sezione Controllo Regione Campania"], "isExact": True} in ricerca["customField"]
        assert not [q for q in banca.sent if str(q.url).endswith("/getCidFromKey")]

    async def test_latest(self):
        banca = Banca()
        with api.configurazione(client_factory=banca.factory):
            r = await _ultime_deliberazioni_corte_conti_impl()
        assert r.success and r.num_found == 5 and "SRCVEN/180/2026/PRSE" in r.results_text

    async def test_refused_credentials_are_read_again_once(self):
        banca = Banca(rifiuti=1)
        with api.configurazione(client_factory=banca.factory):
            r = await _cerca_deliberazioni_corte_conti_impl("rinnovo tacito")
        assert r.success and banca.config_letture == 2

    async def test_the_retry_after_a_reread_uses_the_new_configuration(self):
        banca = Banca(rifiuti=1)
        canali = [[{"name": "bdc_pu", "id": "3349"}], [{"name": "bdc_pu", "id": "9999"}]]
        originale = banca.handler

        def handler(request):
            if str(request.url).endswith("/getBancheDatiChannelList/public"):
                banca.sent.append(request)
                return httpx.Response(200, json=canali.pop(0))
            return originale(request)

        banca.handler = handler
        with api.configurazione(client_factory=banca.factory):
            r = await _cerca_deliberazioni_corte_conti_impl("rinnovo tacito")
        primo, secondo = banca.payloads("/execFullTextSearch/public")
        assert primo["channels"] == ["3349"] and secondo["channels"] == ["9999"]
        assert r.success and banca.config_letture == 2

    async def test_a_malformed_id_lookup_is_an_unexpected_answer(self):
        banca = Banca()
        originale = banca.handler

        def handler(request):
            if str(request.url).endswith("/getCidFromKey"):
                return httpx.Response(200, json={"hits": {"hits": [{"_score": 1.0}]}})
            return originale(request)

        banca.handler = handler
        with api.configurazione(client_factory=banca.factory):
            r = await _leggi_deliberazione_corte_conti_impl("SRCCAM/29/2025/PREV")
        assert r.error_type == "source_error"

    async def test_credentials_refused_twice_are_an_explicit_error(self):
        banca = Banca(rifiuti=5)
        with api.configurazione(client_factory=banca.factory):
            r = await _cerca_deliberazioni_corte_conti_impl("rinnovo tacito")
        assert r.error_type == "source_error" and "credenziali pubbliche" in r.to_str()
        assert banca.config_letture == 2
        _niente_segreti(r.to_str())

    async def test_credentials_refused_right_after_reading_them(self):
        banca = Banca(errore=401)
        with api.configurazione(client_factory=banca.factory):
            r = await _cerca_deliberazioni_corte_conti_impl("rinnovo tacito")
        assert r.error_type == "source_error" and "credenziali pubbliche" in r.to_str()
        assert banca.config_letture == 1

    async def test_a_down_service_is_source_down(self):
        banca = Banca(errore=503)
        with api.configurazione(client_factory=banca.factory):
            r = await _cerca_deliberazioni_corte_conti_impl("rinnovo tacito")
        assert r.error_type == "source_down"

    async def test_errors_never_carry_the_request(self):
        banca = Banca(rifiuti=5)
        with api.configurazione(client_factory=banca.factory):
            with pytest.raises(cc.CorteContiAccessoNegato) as info:
                await cc.search_deliberazioni("rinnovo tacito")
        exc = info.value
        assert exc.__cause__ is None and exc.__context__ is None
        _niente_segreti(repr(exc) + str(exc))

    async def test_no_credential_in_the_logs(self, caplog):
        banca = Banca(rifiuti=1)
        with caplog.at_level(logging.DEBUG):
            with api.configurazione(client_factory=banca.factory):
                await _cerca_deliberazioni_corte_conti_impl("rinnovo tacito", sezione="Campania")
                await _leggi_deliberazione_corte_conti_impl("SRCCAM/29/2025/PREV")
        _niente_segreti(caplog.text)


# ---------------------------------------------------------------------------
# Replay tapes: no Authorization header, no credential value
# ---------------------------------------------------------------------------


def _replay_module():
    spec = importlib.util.spec_from_file_location("replay_mcp_outputs", REPO / "scripts" / "replay_mcp_outputs.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def test_a_recorded_tape_holds_no_credential(tmp_path, monkeypatch):
    banca = Banca()

    class FintaRete(httpx.MockTransport):
        def __init__(self, verify=True):
            super().__init__(banca.handler)

    replay = _replay_module()
    monkeypatch.setattr(httpx, "AsyncHTTPTransport", FintaRete)
    monkeypatch.setitem(core_http.POLITICHE, "corte_conti", core_http.Politica(concorrenza=1, intervallo=0.0))
    original = httpx.AsyncClient.__init__
    try:
        tape = replay.install_tape_transport("record", str(tmp_path / "unused"))
        r = await _leggi_deliberazione_corte_conti_impl("SRCCAM/29/2025/PREV")
    finally:
        httpx.AsyncClient.__init__ = original
    assert r.success
    path = tmp_path / "tape.json.gz"
    replay.save_tape(tape, str(path))
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        raw = fh.read()
    decoded = raw + "".join(
        base64.b64decode(e["body"]).decode("utf-8", "replace") for entries in json.loads(raw).values() for e in entries)
    assert "authorization" not in decoded.lower()
    _niente_segreti(decoded)
    config_key = next(k for k in tape if cc.CONFIG_URL in k)
    config = json.loads(base64.b64decode(tape[config_key][0]["body"]))
    assert config["USER_IIT_PR"] == config["PWD_IIT_PR"] == "<scrubbed>"

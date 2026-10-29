"""Client for the Corte dei conti's banca dati: the deliberazioni of its control sections.

Site:   https://banchedati.corteconti.it/   (an Angular app)
API:    https://corteconti-iit.almawave.cloud/api/   (run for the Court by its vendor)

Read on 2026-10-29 (issue #51). The app downloads its own configuration at start
(`resources/config/configuration.json`): the API's addresses, the names of its endpoints and a
pair of HTTP Basic credentials that every visitor's browser receives and sends with each search
and each document detail. This client does what the browser does (decision LI-054): it reads
that file at runtime and uses the credentials it finds there.

The credentials are never written down. They live in memory only, inside `_Accesso`, whose
repr hides them; they are never logged, never cached on disk, never put in an error message,
and a failed authenticated call is re-raised without the request that carried them. When the
service stops accepting them (401/403) the configuration is read again, once. `scrub_body`
removes them from a recorded copy of the configuration (the replay tapes).

What the public service gives, observed on 2026-10-29:

* full-text search on the deliberazioni (channel `bdc_pu`), with filters on number, year and
  issuing section. **At most 5 documents per search**: asking for 6 or more gets an empty
  HTTP 204, so the client never asks for more and never pages past it;
* the sentenze of the jurisdictional sections (channel `bds`) are counted but never returned
  (HTTP 204 even for one document): they are out of reach of the public service, and of this
  client;
* the detail of a deliberazione, with its full text as plain text (no PDF is read);
* the id of a document from its local id (`SRCCAM/29/2025/PREV`), without credentials;
* the official PDF, from a public link that needs no credentials.
"""

from __future__ import annotations

import base64
import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from urllib.parse import quote, urlparse

import httpx

from mcp_legal_it.core._http import HOST_PER_FONTE, FontePausata, HostNonConsentito, async_client, motivo_rifiuto_host
from mcp_legal_it.lib._http import retry_request
from mcp_legal_it.lib._paging import page, resume_hint

FONTE = "corte_conti"
CONFIG_URL = "https://banchedati.corteconti.it/resources/config/configuration.json"
CONFIG_HOST = urlparse(CONFIG_URL).hostname

#: The most documents the public search returns: from 6 on it answers HTTP 204 with no body.
MAX_DOCUMENTI = 5
#: Characters of full text per answer; the rest is read with `da_carattere` (lib/_paging).
MAX_TESTO = 25_000

# An honest User-Agent: the service is asked for what one user's question needs, nothing more.
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; mcp-legal-it/3.0)",
    "Accept": "application/json",
    "Accept-Language": "it-IT,it;q=0.9",
}
_TIMEOUT = httpx.Timeout(30.0, connect=10.0)

#: Keys of the configuration that hold a secret: their values are never kept outside `_Accesso`.
_CHIAVE_SEGRETA = re.compile(r"(^|_)(PWD|PASSWORD|USER|SECRET|TOKEN)(_|$)")
_UTENTE, _PASSWORD = "USER_IIT_PR", "PWD_IIT_PR"

#: The configuration keys this client reads. A missing one means the app changed: an error, not a guess.
_CHIAVI = (
    "IIT_API_SERVICE_URL", "IIT_API_SECURE_SERVICE_URL", "IIT_API_PORTAL_SERVICE_URL", "SERVER_PUBLIC_BASIC_URL",
    "IIT_EXEC_FULLTEXT_SEARCH_PU", "IIT_GETKM_DOCUMENT_DETAIL_PU", "IIT_GET_BANCHE_DATI_CHANNEL_LIST_PU",
    "IIT_GET_KM_ID_FROM_DOCUMENT_KEY", "IIT_ES_SEARCH_CUSTOM_FIELD", "IIT_ES_CUSTOM_FIELD_DELIB_PU", "NO_SECTION",
    "CHANNEL_NAME_DB_CONTROLLO_PUBLIC", "QUERY_LANGUAGE", "LANGUAGES_ARRAY", "FRAGMENT_SIZE",
    "NUMBER_OF_FRAGMENT", "REQUEST_DOC_ATTRS_ARRAY", _UTENTE, _PASSWORD,
)

# The local id of a deliberazione: issuing section, number, year, type (SRCCAM/29/2025/PREV).
_ID_LOCALE = re.compile(r"[A-Z0-9]{2,12}/\d{1,6}/\d{4}/[A-Z0-9]{2,12}")
# Characters the site escapes in a search term (its escapeElasticSearchReservedChars, verbatim).
_RISERVATI = re.compile(r'[+\-=><!(){}\[\]^"~*?:\\/]|&{2}|\|{2}')
_OPERATORI = frozenset({"and", "or", "not"})
_TAG = re.compile(r"<[^>]{0,200}>")
_SPAZI = re.compile(r"[ \t]+")
_RIGHE_VUOTE = re.compile(r"\n{3,}")


class CorteContiErrore(Exception):
    """The service answered in a way this client cannot use (base class)."""


class CorteContiNonTrovato(CorteContiErrore):
    """No deliberazione matches the request."""


class CorteContiPaginaInattesa(CorteContiErrore):
    """The configuration or an answer of the service is not what the browser app expects."""


class CorteContiAccessoNegato(CorteContiErrore):
    """The service refused the public credentials, even after the configuration was read again."""


class CorteContiNonRaggiungibile(CorteContiErrore):
    """The service did not answer (network error, timeout, 5xx)."""


class _Accesso:
    """What the site's public configuration hands every visitor: endpoints, channel, credential.

    The credential is kept as the ready `Authorization` value and never shown: repr and str hide it.
    """

    __slots__ = ("config", "canale", "_autorizzazione")

    def __init__(self, config: dict, autorizzazione: str, canale: str = "") -> None:
        self.config = config
        self.canale = canale
        self._autorizzazione = autorizzazione

    def intestazioni(self) -> dict[str, str]:
        return {"Authorization": self._autorizzazione, "Content-Type": "application/json"}

    def __repr__(self) -> str:
        return "<Accesso pubblico Corte dei conti>"

    __str__ = __repr__


_MSG_RIFIUTO = ("il servizio della Corte dei conti non accetta più le credenziali pubbliche che il suo sito "
                "distribuisce ai visitatori")

#: The access read from the site, in memory for the life of the process (never on disk).
_ACCESSO: _Accesso | None = None
#: Issuing sections (`BDC_ORG_EMITTENTE`), read once when a search names one.
_ORGANI: list[str] | None = None


def azzera() -> None:
    """Forget the access and the sections read from the site (tests, or a changed configuration)."""
    global _ACCESSO, _ORGANI
    _ACCESSO, _ORGANI = None, None


def leggi_configurazione(dati: dict) -> _Accesso:
    """The `_Accesso` built from the site's configuration: the secrets go into it and leave the dict."""
    if not isinstance(dati, dict):
        raise CorteContiPaginaInattesa("la configurazione della banca dati non è un oggetto JSON")
    mancanti = [k for k in _CHIAVI if k not in dati]
    if mancanti:
        raise CorteContiPaginaInattesa(
            f"la configurazione della banca dati non ha più le voci attese ({', '.join(mancanti[:5])})")
    utente, password = dati[_UTENTE], dati[_PASSWORD]
    if not (isinstance(utente, str) and isinstance(password, str) and utente and password):
        raise CorteContiPaginaInattesa("la configurazione della banca dati non contiene le credenziali pubbliche")
    # Every address the client calls or shows as a link must be https and one of the source's hosts:
    # an altered configuration can neither send a request nor point the lawyer elsewhere.
    for url_key in ("IIT_API_SERVICE_URL", "IIT_API_SECURE_SERVICE_URL", "IIT_API_PORTAL_SERVICE_URL",
                    "SERVER_PUBLIC_BASIC_URL"):
        if not indirizzo_ammesso(dati[url_key]):
            # The address itself is never put in the message.
            raise CorteContiPaginaInattesa(
                "la configurazione della banca dati indica un servizio fuori dagli host della Corte dei conti")
    config = {k: v for k, v in dati.items() if k in _CHIAVI and not _CHIAVE_SEGRETA.search(k)}
    token = base64.b64encode(f"{utente}:{password}".encode()).decode()
    return _Accesso(config, "Basic " + token)


def indirizzo_ammesso(indirizzo) -> bool:
    """True when *indirizzo* is an https address on one of the source's hosts, read as a browser would.

    `urlparse` alone is not enough: with a backslash before `@<the Court's host>` it reads the
    Court's host, while a browser goes to the host written first. So no backslash, no control
    character, no userinfo (no `@` in the authority), and httpx's own reading must agree.
    """
    if not isinstance(indirizzo, str) or not indirizzo.startswith("https://"):
        return False
    if "\\" in indirizzo or any(ord(c) < 0x21 or ord(c) == 0x7F for c in indirizzo):
        return False
    try:
        parsed = urlparse(indirizzo)
        url = httpx.URL(indirizzo)
    except (ValueError, httpx.InvalidURL):
        return False
    if "@" in parsed.netloc or parsed.username is not None or parsed.password is not None:
        return False
    return (parsed.hostname in HOST_PER_FONTE[FONTE] and url.host == parsed.hostname
            and motivo_rifiuto_host(FONTE, url) is None)


def scrub_body(url: str, body: bytes) -> bytes:
    """*body* reduced to what the client reads, credentials replaced, when *url* is the site's configuration.

    For recorded HTTP exchanges (replay tapes). By inclusion: only the `_CHIAVI` keys are kept,
    the secret ones as `<scrubbed>`; any other shape records nothing (`b""`).
    Any other URL's body is returned unchanged.
    """
    try:
        parsed = urlparse(url)
    except ValueError:
        return b""
    if parsed.hostname != CONFIG_HOST or not parsed.path.endswith("/configuration.json"):
        return body
    try:
        dati = json.loads(body)
    except ValueError:
        return b""
    if not isinstance(dati, dict):
        return b""
    tenuto = {k: ("<scrubbed>" if _CHIAVE_SEGRETA.search(k) else dati[k]) for k in _CHIAVI if k in dati}
    return json.dumps(tenuto, ensure_ascii=False).encode()


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------


def _client() -> httpx.AsyncClient:
    return async_client(FONTE, headers=_HEADERS, timeout=_TIMEOUT, follow_redirects=False)


def _url(acc: _Accesso, base_key: str, endpoint_key: str, *parti: str) -> str:
    url = acc.config[base_key] + acc.config[endpoint_key]
    for parte in parti:
        url += "/" + parte
    return url


def _da_stato(status: int) -> CorteContiErrore:
    if status in (401, 403):
        return CorteContiAccessoNegato(f"il servizio ha rifiutato la richiesta (HTTP {status})")
    if status >= 500:
        return CorteContiNonRaggiungibile(f"il servizio risponde HTTP {status}")
    return CorteContiPaginaInattesa(f"il servizio risponde HTTP {status}")


async def _chiedi(client: httpx.AsyncClient, method: str, url: str, **kwargs) -> httpx.Response:
    """One request; a failure re-raised as our own error, without the request (and its headers).

    The error is raised after the `except` block, so not even `__context__` keeps the httpx
    exception, whose request carries the `Authorization` header.
    """
    try:
        return await retry_request(client, method, url, dataset="corte_conti", **kwargs)
    except httpx.HTTPStatusError as exc:
        errore = _da_stato(exc.response.status_code)
    except FontePausata as exc:
        errore = CorteContiNonRaggiungibile(str(exc))          # how long the source asked to wait, no URL
    except HostNonConsentito:
        errore = CorteContiPaginaInattesa("richiesta verso un indirizzo non consentito, non inviata")
    except httpx.TransportError as exc:
        errore = CorteContiNonRaggiungibile(type(exc).__name__)   # never the exception's text: it may name the URL
    except httpx.HTTPError as exc:                            # decoding and other errors keep `.request` too
        errore = CorteContiPaginaInattesa(f"risposta illeggibile del servizio ({type(exc).__name__})")
    raise errore


def _json(resp: httpx.Response):
    # Raised outside the except block: the JSONDecodeError's `.doc` would hold the body (the configuration).
    try:
        return resp.json()
    except ValueError:
        pass
    raise CorteContiPaginaInattesa("il servizio non ha risposto in JSON")


async def _accesso(client: httpx.AsyncClient, rinnova: bool = False) -> _Accesso:
    """The access read from the site's configuration, read again when *rinnova*."""
    global _ACCESSO
    if _ACCESSO is not None and not rinnova:
        return _ACCESSO
    acc = leggi_configurazione(_json(await _chiedi(client, "GET", CONFIG_URL)))
    try:
        resp = await _chiedi(client, "GET", _url(acc, "IIT_API_SECURE_SERVICE_URL", "IIT_GET_BANCHE_DATI_CHANNEL_LIST_PU"),
                             headers=acc.intestazioni())
    except CorteContiAccessoNegato:
        raise CorteContiAccessoNegato(_MSG_RIFIUTO) from None
    nome = acc.config["CHANNEL_NAME_DB_CONTROLLO_PUBLIC"]
    canali = _json(resp)
    ids = [c.get("id") for c in canali if isinstance(c, dict) and c.get("name") == nome] if isinstance(canali, list) else []
    if not ids or not ids[0]:
        raise CorteContiPaginaInattesa("il servizio non elenca più la banca dati delle deliberazioni di controllo")
    acc.canale = str(ids[0])
    _ACCESSO = acc
    return acc


async def _post_autenticato(
    client: httpx.AsyncClient, endpoint_key: str, payload: Callable[[_Accesso], dict],
) -> tuple[httpx.Response, _Accesso]:
    """POST to the credentialed service; on 401/403 the configuration is read again, once.

    *payload* builds the body from the access, so a retry after a re-read uses the new
    configuration's addresses and channel, not the ones that were refused.
    """
    acc = await _accesso(client)
    try:
        return await _chiedi(client, "POST", _url(acc, "IIT_API_SECURE_SERVICE_URL", endpoint_key),
                             json=payload(acc), headers=acc.intestazioni()), acc
    except CorteContiAccessoNegato:
        pass
    acc = await _accesso(client, rinnova=True)
    try:
        return await _chiedi(client, "POST", _url(acc, "IIT_API_SECURE_SERVICE_URL", endpoint_key),
                             json=payload(acc), headers=acc.intestazioni()), acc
    except CorteContiAccessoNegato:
        pass
    raise CorteContiAccessoNegato(_MSG_RIFIUTO)


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


def query_testuale(testo: str) -> str:
    """The site's "all the words" query: terms joined by AND, reserved characters escaped and quoted.

    Empty text is "*" (every document). The words and/or/not are refused, as the site refuses them.
    """
    parole = (testo or "").split()
    if not parole:
        return "*"
    if any(p.lower() in _OPERATORI for p in parole):
        raise ValueError('togliere le parole "and", "or" e "not": la ricerca cerca già tutte le parole indicate')
    out = []
    for p in parole:
        if _RISERVATI.search(p):
            p = '"' + _RISERVATI.sub(lambda m: "\\" + m.group(0), p) + '"'
        out.append(p)
    return " AND ".join(out)


def _intero(valore, nome: str) -> int | None:
    if valore in (None, ""):
        return None
    testo = str(valore).strip()
    if not testo.isdigit() or len(testo) > 6:
        raise ValueError(f"{nome} deve essere un numero intero (es. {'2025' if nome == 'anno' else '29'})")
    return int(testo)


def build_search_payload(
    acc: _Accesso, query: str = "", *, numero=None, anno=None, organo: str = "",
    per_data: bool = False, n: int = MAX_DOCUMENTI,
) -> dict:
    """The JSON the site's search sends, for the deliberazioni channel only, light (no entities/concepts)."""
    cfg = acc.config
    campi: list[dict] = []
    num, yr = _intero(numero, "numero"), _intero(anno, "anno")
    if num is not None:
        campi.append({"name": "BDC_NUMERO_ID_LOCALE", "type": "NUMBER",
                      "numberRangeStart": num, "numberRangeEnd": num, "isExact": False})
    if yr is not None:
        campi.append({"name": "BDC_ANNO", "type": "NUMBER", "numberRangeStart": yr, "numberRangeEnd": yr, "isExact": False})
    if organo:
        campi.append({"name": "BDC_ORG_EMITTENTE", "type": "TEXT_TOKENIZED", "tokenText": [organo], "isExact": True})
    payload = {
        "query": query_testuale(query),
        "queryLanguage": cfg["QUERY_LANGUAGE"],
        "languages": cfg["LANGUAGES_ARRAY"],
        "numberOfDocumentToRetrieve": max(1, min(int(n), MAX_DOCUMENTI)),
        "noEntity": True,
        "noCluster": True,
        "entitySearch": False,
        "noConcept": True,
        "numberOfFragment": cfg["NUMBER_OF_FRAGMENT"],
        "fragmentSize": cfg["FRAGMENT_SIZE"],
        "channels": [acc.canale],
        "customField": campi,
        "docAttributes": [{"name": a} for a in cfg["REQUEST_DOC_ATTRS_ARRAY"]],
    }
    if per_data:
        payload["sortField"], payload["sortOrder"] = "BDC_DT_DEPOSITO_DEL", "DESC"
    return payload


@dataclass
class Deliberazione:
    """One deliberazione as the search lists it, or as its detail describes it."""

    id_locale: str                 # SRCCAM/29/2025/PREV
    chiave: str = ""               # the service's own document key (index/type/id)
    numero: str = ""
    anno: str = ""
    organo: str = ""               # issuing section
    esito: str = ""
    descrizione: str = ""
    data_adunanza: str = ""
    data_deposito: str = ""
    data_pubblicazione: str = ""   # when the banca dati acquired it
    frammento: str = ""            # the passage matching the search
    allegato: bool = False
    tipo: str = ""
    presidente: str = ""
    relatori: list[str] = field(default_factory=list)
    destinatari: list[str] = field(default_factory=list)
    materie: list[str] = field(default_factory=list)
    aree: list[str] = field(default_factory=list)
    id_generale: str = ""
    testo: str = ""
    url_pdf: str = ""
    url_scheda: str = ""


def _pulisci(testo: str) -> str:
    testo = _TAG.sub("", testo or "").replace("\r", "")
    testo = "\n".join(_SPAZI.sub(" ", riga).strip() for riga in testo.split("\n"))
    return _RIGHE_VUOTE.sub("\n\n", testo).strip()


def _elenco(valore: str) -> list[str]:
    visti: list[str] = []
    for v in (valore or "").split("[;]"):
        v = v.strip()
        if v and v not in visti:
            visti.append(v)
    return visti


def _link(acc: _Accesso, d: Deliberazione) -> None:
    cfg, ident = acc.config, quote(d.id_locale, safe="/")
    d.url_pdf = f"{cfg['IIT_API_PORTAL_SERVICE_URL']}downloadDocument/{cfg['IIT_ES_CUSTOM_FIELD_DELIB_PU']}/{ident}"
    d.url_scheda = f"{cfg['SERVER_PUBLIC_BASIC_URL']}?docId=documentDetail/{ident}"


def _da_attributi(attr: dict) -> Deliberazione:
    return Deliberazione(
        id_locale=str(attr.get("BDC_ID_LOCALE", "")).strip(),
        numero=str(attr.get("BDC_NUMERO_ID_LOCALE", "")).strip(),
        anno=str(attr.get("BDC_ANNO", "")).strip(),
        organo=str(attr.get("BDC_ORG_EMITTENTE", "")).strip(),
        esito=str(attr.get("BDC_ESITO", "")).strip(),
        descrizione=_pulisci(str(attr.get("BDC_DESCRIZIONE_DEL", ""))),
        data_adunanza=str(attr.get("BDC_DT_ADUNANZA", "")).strip(),
        data_deposito=str(attr.get("BDC_DT_DEPOSITO_DEL", "")).strip(),
        data_pubblicazione=str(attr.get("BDC_DT_ACQ_DEL", "")).strip(),
        allegato=str(attr.get("BDC_IS_ATTACHMENT", "")).lower() == "true",
    )


def parse_search(dati, acc: _Accesso) -> tuple[list[Deliberazione], int]:
    """The deliberazioni of a search answer, and the total the service reports."""
    risultato = dati.get("searchResult") if isinstance(dati, dict) else None
    if not isinstance(risultato, dict):
        raise CorteContiPaginaInattesa("la risposta della ricerca non ha il formato atteso")
    out: list[Deliberazione] = []
    documenti = risultato.get("documents") or []
    if not isinstance(documenti, list) or not all(isinstance(doc, dict) for doc in documenti):
        raise CorteContiPaginaInattesa("la risposta della ricerca non ha il formato atteso")
    for doc in documenti:
        attr = {a.get("name"): a.get("value") for a in doc.get("documentAttributes") or [] if isinstance(a, dict)}
        if attr.get("CHANNEL_NAME") != acc.config["CHANNEL_NAME_DB_CONTROLLO_PUBLIC"]:
            continue
        d = _da_attributi(attr)
        if not d.id_locale:
            continue
        chiave = doc.get("documentKey") or {}
        if all(chiave.get(k) for k in ("index", "type", "id")):
            d.chiave = f"{chiave['index']}/{chiave['type']}/{chiave['id']}"
        frammenti = doc.get("fragments") or []
        d.frammento = _pulisci(frammenti[0]) if frammenti else ""
        _link(acc, d)
        out.append(d)
    totale = risultato.get("totalHits")
    return out, totale if isinstance(totale, int) else len(out)


def parse_dettaglio(dati, acc: _Accesso, chiave: str = "") -> Deliberazione:
    """The deliberazione of a detail answer, with its whole text (the formatter windows it)."""
    attr = dati.get("documentAttributes") if isinstance(dati, dict) else None
    if not isinstance(attr, dict) or not attr.get("BDC_ID_LOCALE"):
        raise CorteContiPaginaInattesa("il dettaglio della deliberazione non ha il formato atteso")
    d = _da_attributi(attr)
    d.chiave = chiave
    d.tipo = str(attr.get("BDC_TIPO_DELIBERAZIONE", "")).strip()
    d.presidente = str(attr.get("BDC_NOMINATIVO_PRESIDENTE", "")).strip()
    d.relatori = _elenco(attr.get("BDC_MAGISTRATO_RELATORE", ""))
    tipi, nomi = _elenco(attr.get("BDC_TIPO_DESTINATARIO", "")), _elenco(attr.get("BDC_DENOM_DESTINATARIO", ""))
    d.destinatari = nomi or tipi
    d.materie = _elenco(attr.get("BDC_DSC_MAT_I_LIVELLO", "")) + _elenco(attr.get("BDC_DSC_MAT_II_LIVELLO", ""))
    d.aree = _elenco(attr.get("BDC_AREA_PRIMO_LIVELLO", "")) + _elenco(attr.get("BDC_AREA_SECONDO_LIVELLO", ""))
    d.id_generale = str(attr.get("BDC_ID_GENERALE", "")).strip()
    d.testo = _pulisci(str(dati.get("plainText") or ""))
    _link(acc, d)
    return d


def normalizza_id(id_locale: str) -> str:
    """The local id in the service's form (upper case, no spaces), or ValueError."""
    ident = re.sub(r"\s+", "", id_locale or "").upper()
    if not _ID_LOCALE.fullmatch(ident):
        raise ValueError(
            "identificativo della deliberazione non valido: usare quello restituito dalla ricerca, "
            "nella forma SEZIONE/NUMERO/ANNO/TIPO (es. SRCCAM/29/2025/PREV)")
    return ident


def risolvi_organo(sezione: str, organi: list[str]) -> str:
    """The issuing section named by *sezione* ("Campania", "sezioni riunite"), or ValueError.

    Exact match first, then a section whose name contains every word given; never a guess
    between two.
    """
    s = " ".join((sezione or "").split()).casefold()
    if not s:
        return ""
    for o in organi:
        if o.casefold() == s:
            return o
    parole = s.split()
    candidati = [o for o in organi if all(p in o.casefold() for p in parole)]
    if len(candidati) == 1:
        return candidati[0]
    if not candidati:
        raise ValueError(f"sezione della Corte dei conti non riconosciuta: {sezione!r}")
    elenco = "; ".join(sorted(candidati)[:8])
    raise ValueError(f"sezione ambigua {sezione!r}: indicarne una tra {elenco}")


async def _organi(client: httpx.AsyncClient, acc: _Accesso) -> list[str]:
    global _ORGANI
    if _ORGANI is None:
        url = _url(acc, "IIT_API_SERVICE_URL", "IIT_ES_SEARCH_CUSTOM_FIELD",
                   acc.config["IIT_ES_CUSTOM_FIELD_DELIB_PU"], "BDC_ORG_EMITTENTE", acc.config["NO_SECTION"])
        dati = _json(await _chiedi(client, "GET", url))
        try:
            buckets = dati["aggregations"]["distinct_custom_field"]["buckets"]
            organi = [str(b["key"]) for b in buckets if b.get("key")]
        except (KeyError, TypeError, AttributeError):
            raise CorteContiPaginaInattesa("l'elenco delle sezioni non ha il formato atteso") from None
        if not organi:
            # Not kept: an empty list in memory would make every section «non riconosciuta» until restart.
            raise CorteContiPaginaInattesa("il servizio non elenca le sezioni della Corte dei conti")
        _ORGANI = organi
    return _ORGANI


async def search_deliberazioni(
    query: str = "", *, numero=None, anno=None, sezione: str = "", per_data: bool = False, n: int = MAX_DOCUMENTI,
) -> tuple[list[Deliberazione], int]:
    """Search the deliberazioni: at most `MAX_DOCUMENTI`, with the total the service reports.

    The input is checked before any request: a query the site would refuse costs nothing.
    """
    query_testuale(query)
    _intero(numero, "numero")
    _intero(anno, "anno")
    async with _client() as client:
        acc = await _accesso(client)
        organo = risolvi_organo(sezione, await _organi(client, acc)) if sezione.strip() else ""
        resp, acc = await _post_autenticato(
            client, "IIT_EXEC_FULLTEXT_SEARCH_PU",
            lambda a: build_search_payload(a, query, numero=numero, anno=anno, organo=organo, per_data=per_data, n=n))
        if resp.status_code == 204 or not resp.content:
            raise CorteContiPaginaInattesa("il servizio ha risposto senza contenuto (HTTP 204)")
        return parse_search(_json(resp), acc)


async def _chiave_da_id(client: httpx.AsyncClient, acc: _Accesso, ident: str) -> str:
    url = _url(acc, "IIT_API_SERVICE_URL", "IIT_GET_KM_ID_FROM_DOCUMENT_KEY")
    dati = _json(await _chiedi(client, "POST", url, json={"search_key": ident, "search_context": "public"},
                               headers={"Content-Type": "application/json"}))
    try:
        hits = dati["hits"]["hits"]
        chiave = f"{hits[0]['_index']}/{hits[0]['_type']}/{hits[0]['_id']}" if hits else ""
    except (KeyError, TypeError, IndexError):
        raise CorteContiPaginaInattesa("la ricerca dell'identificativo non ha il formato atteso") from None
    if not chiave:
        raise CorteContiNonTrovato(f"nessuna deliberazione con identificativo {ident}")
    return chiave


async def fetch_deliberazione(id_locale: str = "", chiave: str = "") -> Deliberazione:
    """The detail of one deliberazione, from its local id (or the service's key from a search)."""
    ident = normalizza_id(id_locale) if id_locale else ""
    async with _client() as client:
        acc = await _accesso(client)
        if not chiave:
            chiave = await _chiave_da_id(client, acc, ident)
        resp, acc = await _post_autenticato(client, "IIT_GETKM_DOCUMENT_DETAIL_PU",
                                            lambda _a: {"key": chiave, "requiredRawContent": False})
        if resp.status_code == 204 or not resp.content:
            raise CorteContiNonTrovato(f"nessun dettaglio per la deliberazione {ident or chiave}")
        d = parse_dettaglio(_json(resp), acc, chiave)
    if ident and d.id_locale.upper() != ident:
        raise CorteContiPaginaInattesa(f"il servizio ha restituito {d.id_locale} invece di {ident}")
    return d


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------


def _estremi(d: Deliberazione) -> str:
    out = f"{d.organo}, deliberazione n. {d.numero}/{d.anno}" if d.organo else f"Deliberazione n. {d.numero}/{d.anno}"
    if d.data_deposito:
        out += f", depositata il {d.data_deposito}"
    return out


def format_result(d: Deliberazione) -> str:
    lines = [f"### {d.id_locale}", f"**{_estremi(d)}**"]
    if d.data_adunanza:
        lines.append(f"- Adunanza: {d.data_adunanza}")
    if d.esito:
        lines.append(f"- Esito: {d.esito}")
    if d.allegato:
        lines.append("- Documento allegato a una deliberazione")
    if d.descrizione:
        lines.append(f"- Oggetto: {d.descrizione[:500]}")
    if d.frammento:
        lines.append(f"- Passo: …{d.frammento[:400]}…")
    lines.append(f"- Identificativo per la lettura: `{d.id_locale}`")
    lines.append(f"- PDF ufficiale: {d.url_pdf}")
    return "\n".join(lines)


def format_deliberazione(d: Deliberazione, da_carattere: int = 1) -> str:
    """The detail as markdown; from `da_carattere` > 1, the header and that window of the text only."""
    lines = [f"## Corte dei conti — {d.id_locale}", "", f"**{_estremi(d)}**", ""]
    if da_carattere > 1:
        body, note = page(d.testo, da_carattere, MAX_TESTO)
        return "\n".join(lines + ["### Testo", "", body, "", "---", note])
    for etichetta, valore in (
        ("Tipo", d.tipo), ("Adunanza", d.data_adunanza), ("Deposito", d.data_deposito),
        ("Acquisita nella banca dati", d.data_pubblicazione), ("Esito", d.esito), ("Presidente", d.presidente),
        ("Relatore", ", ".join(d.relatori)), ("Destinatari", "; ".join(d.destinatari)),
        ("Materie", "; ".join(d.materie)), ("Aree", "; ".join(d.aree)),
    ):
        if valore:
            lines.append(f"- {etichetta}: {valore}")
    if d.descrizione:
        lines += ["", f"**Oggetto**: {d.descrizione}"]
    lines += ["", f"- PDF ufficiale: {d.url_pdf}", f"- Scheda nella banca dati: {d.url_scheda}", ""]
    if d.testo:
        lines += ["### Testo", "", d.testo[:MAX_TESTO]]
        if len(d.testo) > MAX_TESTO:
            lines += ["", "---", f"*[Testo troncato a {MAX_TESTO} caratteri su {len(d.testo)} totali: "
                                 f"{resume_hint(MAX_TESTO + 1)}]*"]
    else:
        lines.append("*La banca dati non riporta il testo di questa deliberazione: leggerlo nel PDF ufficiale.*")
    return "\n".join(lines)

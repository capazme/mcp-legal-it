"""Client for CeRDEF (Banca Dati Giurisprudenza Tributaria — def.finanze.it).

Endpoint: https://def.finanze.it/DocTribFrontend/
- Search: POST to executeAdvancedGiurisprudenzaSearch.do with the fields of the
  advanced form `formRicAvanzG` (callRicAvanzataGiurisprudenza.do)
- Results: XML in the JS variable `var xmlResult = '...'`, shaped
  <risultatiRicerca><contatori>…</contatori><risultati><ulterioriRisultati>…
  <Provvedimento idProvvedimento="{GUID}"><estremi>…</estremi>
  <titoliProvvedimento>…</titoliProvvedimento></Provvedimento>…
  with up to 50 items per answer
- More results: GET paginatorXml.do in the same session answers with the list so
  far plus the next 50 (the portal's own "Avanti" link)
- Detail: GET getGiurisprudenzaDetail.do?id={GUID} → `var xmlDettaglio`

The portal answers HTTP 200 even when it rejects a search: the page then carries
an error box (`<p class="errato">`) instead of `xmlResult`. That answer, and any
payload whose shape is not the one above, raises CerdefError -- never an empty
list. The previous client read both as "no results", so when the portal changed
its form every search reported "nessuna sentenza" (issue #46).

No auth, no captcha, standard SSL.
"""

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, datetime

import httpx

from src.lib._http import retry_request
from src.lib._paging import page, resume_hint
from bs4 import BeautifulSoup

_BASE = "https://def.finanze.it/DocTribFrontend/"
_FORM_URL = _BASE + "callRicAvanzataGiurisprudenza.do"
_SEARCH_URL = _BASE + "executeAdvancedGiurisprudenzaSearch.do"
_DETAIL_URL = _BASE + "getGiurisprudenzaDetail.do"
_PAGINATOR_URL = _BASE + "paginatorXml.do"
_NPE = "NullPointerException"  # body of the portal's HTTP 500 for an unknown detail id
_TIMEOUT = httpx.Timeout(45.0, connect=15.0)
_MAX_TEXT_LENGTH = 25000
_MAX_RESULTS = 250

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://def.finanze.it/DocTribFrontend/",
}

TIPO_ESTREMI: dict[str, str] = {
    "sentenza": "Sentenza",
    "ordinanza": "Ordinanza",
    "decreto": "Decreto",
}

ENTI: dict[str, str] = {
    "corte_suprema": "Corte di Cassazione",
    "cgt_primo_grado": "Corti di giustizia tributaria di primo grado (ex CTP)",
    "cgt_secondo_grado": "Corti di giustizia tributaria di secondo grado (ex CTR)",
}

CRITERI_RICERCA: dict[str, str] = {
    "tutti": "0",
    "almeno_uno": "1",
    "frase_esatta": "2",
    "parole_adiacenti": "3",
    "operatori_logici": "4",
}

ORDINAMENTI: dict[str, str] = {
    "rilevanza": "RANK",
    "data": "DATA",
}


@dataclass(frozen=True)
class _FiltroEnte:
    """Where an `ente` key goes in the form: one court (`ente`) or a group of courts (`superEnte`)."""

    campo: str
    valore: str
    solo_primo_grado: bool = False


# Option values verbatim from the form (2026-09-28). The portal answers a value it
# does not know with zero results, not with an error, so a drifted value would read
# as "no results": the unit tests check them against the saved form, the live test
# against the current one.
_FILTRI_ENTE: dict[str, _FiltroEnte] = {
    "corte_suprema": _FiltroEnte("ente", "Corte di Cassazione"),
    # No group holds the first-instance courts alone and `ente` takes a single
    # court: search both instances (pre-2023 CTP/CTR names included) and keep the
    # first-instance courts client-side.
    "cgt_primo_grado": _FiltroEnte(
        "superEnte",
        "Tutte le Corti di giustizia tributaria di primo e secondo grado",
        solo_primo_grado=True,
    ),
    "cgt_secondo_grado": _FiltroEnte("superEnte", "Tutte le Corti di giustizia tributaria di secondo grado"),
}

# First-instance courts as the portal names them: "Corte di giustizia tributaria di
# primo grado di …", the pre-2023 "Comm. Trib. Prov. …", and the special cases
# "Comm. Trib.  I grado di Bolzano" and "Comm. Trib. primo grado Ivrea".
_PRIMO_GRADO = re.compile(r"\bprimo grado\b|\bComm\. Trib\. Prov\.|\bComm\. Trib\.\s+I grado\b")

# "Ordinanza del 14/09/2026 n. 25285 - Corte di Cassazione - Sezione/Collegio 5"
# The id CeRDEF gives a provvedimento: a GUID in braces, as the search lists it (the
# detail page also answers to the same GUID without braces).
_GUID = re.compile(r"^\{?[0-9A-Fa-f]{8}(?:-[0-9A-Fa-f]{4}){3}-[0-9A-Fa-f]{12}\}?$")

_ESTREMI = re.compile(
    r"^.+? del (?P<giorno>\d{1,2})/(?P<mese>\d{1,2})/(?P<anno>\d{4})(?: n\. .+?)?"
    r"(?: - (?P<ente>.+?))?(?: - Sezione/Collegio .+)?$"
)

# The fields of the advanced form with the values the browser posts when nothing
# is filled in (its onsubmit handler sets js_enabled to 1).
_FORM_DEFAULTS: dict[str, str] = {
    "js_enabled": "1",
    "tipoComplessitaRicerca": "avanzata",
    "ricercaAreaRiservata": "false",
    "tipoRicerca": "RA",
    "device": "D",
    "ambitoRicerca": "G",
    "parole": "",
    "tipoCriterioRicerca": CRITERI_RICERCA["tutti"],
    "tipo_ord": ORDINAMENTI["rilevanza"],
    "tipoEstremi": "",
    "numero": "",
    "giornoDataEmissioneDa": "",
    "meseDataEmissioneDa": "",
    "annoDataEmissioneDa": "",
    "dataEmissioneDa": "",
    "giornoDataEmissioneA": "",
    "meseDataEmissioneA": "",
    "annoDataEmissioneA": "",
    "dataEmissioneA": "",
    "ente": "",
    "superEnte": "",
    "materiaFiscale": "",
    "classificazioneArgomento": "",
}


class CerdefError(Exception):
    """CeRDEF answered, but not with something the client can read.

    Raised for the portal's own error page (a rejected search, an unknown id) and
    for any payload whose shape the client does not recognise. Callers must report
    it as a failure of the source: reading it as "no results" was the bug of #46.
    """


class CerdefNonTrovato(CerdefError):
    """The portal does not know the requested provvedimento (unknown or malformed GUID).

    The portal answers an unknown detail id with HTTP 500 and a NullPointerException
    body, deterministically: it is a "not found", not an outage, and retrying it is
    pointless.
    """


@dataclass
class ProvvedimentoResult:
    guid: str
    estremi: str
    titoli: str
    ente: str
    data: str


@dataclass
class ProvvedimentoDetail:
    guid: str
    estremi: str
    massima: str
    testo_integrale: str
    # Not published by the current portal; kept for callers that build a detail by hand.
    collegio: str = ""
    udienza: str = ""
    ricorsi: str = ""
    oggetto: str = ""


@dataclass
class _Pagina:
    """One answer of the search: the items it lists and whether the portal has more."""

    risultati: list[ProvvedimentoResult]
    altri: bool
    totale: int | None = None  # the portal's own count of matches


@dataclass
class EsitoRicerca:
    """The items a search kept, and how much of the portal's list they come from."""

    risultati: list[ProvvedimentoResult]
    totale: int | None  # the portal's own count of matches
    esaminati: int  # items read from the portal, before the first-instance filter
    # The first-instance filter stopped at the scan limit with items left unread:
    # fewer results than asked does not mean the portal has no more.
    troncato: bool = False


class CerdefSession:
    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "CerdefSession":
        self._client = httpx.AsyncClient(
            timeout=_TIMEOUT, headers=_HEADERS, follow_redirects=True
        )
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("CerdefSession not entered")
        return self._client


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

_JS_ESCAPE = re.compile(r"\\(u[0-9a-fA-F]{4}|x[0-9a-fA-F]{2}|.)", re.DOTALL)
_JS_CONTROL = {"n": "\n", "r": "\r", "t": "\t", "b": "\b", "f": "\f", "v": "\v", "0": "\0"}


def _unescape_js_string(raw: str) -> str:
    """Decode the escapes of a JS string literal, in a single pass.

    \\uXXXX and \\xXX are code points, \\n, \\t and the like are control characters,
    and any other escaped character stands for itself: the portal writes \\/, \\",
    \\', \\- and accented letters as \\à. A single pass means an escaped backslash
    can never start a second escape.
    """

    def _decode(match: re.Match[str]) -> str:
        seq = match.group(1)
        if len(seq) > 1:
            return chr(int(seq[1:], 16))
        return _JS_CONTROL.get(seq, seq)

    return _JS_ESCAPE.sub(_decode, raw)


def _extract_xml_from_js(html: str, var_name: str) -> str:
    """The decoded value of `var <var_name> = '...'` in the page, or "" when it is absent."""
    pattern = rf"var\s+{re.escape(var_name)}\s*=\s*'((?:[^'\\]|\\.)*)'"
    match = re.search(pattern, html, re.DOTALL)
    if not match:
        return ""
    return _unescape_js_string(match.group(1))


def _portal_error(html: str) -> str:
    """The text of the portal's own error box (`<p class="errato">`), or "" when there is none."""
    box = BeautifulSoup(html, "lxml").find("p", class_="errato")
    if box is None:
        return ""
    return " ".join(box.get_text(" ", strip=True).split())


def _payload_mancante(html: str, var_name: str, cosa: str) -> CerdefError:
    """The error for a page without the expected XML, with the portal's own message if it gave one."""
    messaggio = _portal_error(html)
    if messaggio:
        return CerdefError(f"il portale ha rifiutato la richiesta ({messaggio})")
    return CerdefError(
        f"la pagina ricevuta non contiene {cosa} ({var_name} assente): "
        "il formato del portale potrebbe essere cambiato"
    )


# Tags that sit inside a sentence: the portal wraps every cited norm in <a> and
# runs of text in <span>. Only block elements may start a new line.
_INLINE_TAGS = ("a", "abbr", "b", "big", "em", "font", "i", "small", "span", "strong", "sub", "sup", "u")


def _strip_cdata_html(text: str) -> str:
    """Plain text of an HTML fragment: one line per block, inline markup dissolved into its sentence."""
    if not text:
        return ""
    soup = BeautifulSoup(text, "lxml")
    for tag in soup.find_all(_INLINE_TAGS):
        tag.unwrap()
    soup.smooth()
    return soup.get_text("\n", strip=True)


def _titolo(elemento: ET.Element) -> str:
    """The subject of a `titoloProvvedimento`: its HTML text, or its `intitolazione` in the detail."""
    intitolazione = elemento.find("intitolazione")
    testo = intitolazione.text if intitolazione is not None else elemento.text
    return _strip_cdata_html(testo or "")


def _parse_estremi(estremi: str) -> tuple[str, str]:
    """(court, date as DD/MM/YYYY) read from an estremi line; ("", "") when it has another shape."""
    match = _ESTREMI.match(estremi)
    if not match:
        return "", ""
    data = f"{int(match.group('giorno')):02d}/{int(match.group('mese')):02d}/{match.group('anno')}"
    return (match.group("ente") or "").strip(), data


def _is_primo_grado(ente: str) -> bool:
    return bool(_PRIMO_GRADO.search(ente))


def _parse_search_xml(xml_str: str) -> _Pagina:
    """Read a result list; anything but a readable list or the portal's own zero raises CerdefError."""
    try:
        root = ET.fromstring(xml_str)
    except ET.ParseError as exc:
        raise CerdefError(f"XML dei risultati non leggibile ({exc})") from exc
    lista = root.find("risultati")
    if root.tag != "risultatiRicerca" or lista is None:
        raise CerdefError(f"struttura XML dei risultati inattesa (radice <{root.tag}>)")

    risultati = []
    for item in lista.findall("Provvedimento"):
        guid = (item.get("idProvvedimento") or "").strip()
        estremi = " ".join((item.findtext("estremi") or "").split())
        if not guid or not estremi:
            continue
        ente, data = _parse_estremi(estremi)
        titoli = "; ".join(
            filter(None, (_titolo(t) for t in item.iterfind("titoliProvvedimento/titoloProvvedimento")))
        )
        risultati.append(ProvvedimentoResult(guid=guid, estremi=estremi, titoli=titoli, ente=ente, data=data))

    # An empty list is a genuine zero only when the portal's own counter says so.
    contatore = (root.findtext("contatori/contatoreGiurisprudenza") or "").strip()
    if not risultati and contatore != "0":
        raise CerdefError(
            f"il portale indica {contatore or 'un numero imprecisato di'} provvedimenti ma l'elenco "
            "non ne contiene di leggibili: il formato del portale potrebbe essere cambiato"
        )
    altri = (lista.findtext("ulterioriRisultati") or "").strip() == "true"
    totale = int(contatore) if contatore.isdigit() else None
    return _Pagina(risultati=risultati, altri=altri, totale=totale)


def _parse_search_page(html: str) -> _Pagina:
    xml_str = _extract_xml_from_js(html, "xmlResult")
    if not xml_str:
        raise _payload_mancante(html, "xmlResult", "l'elenco dei risultati")
    return _parse_search_xml(xml_str)


def _parse_detail_xml(xml_str: str) -> ProvvedimentoDetail:
    """Read the detail of one provvedimento; an unrecognised shape raises CerdefError."""
    try:
        root = ET.fromstring(xml_str)
    except ET.ParseError as exc:
        raise CerdefError(f"XML del provvedimento non leggibile ({exc})") from exc
    item = root.find("risultati/Provvedimento")
    if item is None:
        raise CerdefError(f"struttura XML del provvedimento inattesa (radice <{root.tag}>)")
    guid = (item.get("idProvvedimento") or "").strip()
    estremi = " ".join((item.findtext("estremi") or "").split())
    if not guid and not estremi:
        raise CerdefError("struttura XML del provvedimento inattesa (né identificativo né estremi)")
    titoli = item.findall("titoliProvvedimento/titoloProvvedimento")
    # Present but empty is a provvedimento without text; absent is a format the
    # client does not know, and must not read as an empty text.
    if item.find("testo") is None and not any(t.find("massima") is not None for t in titoli):
        raise CerdefError(
            "struttura XML del provvedimento inattesa (né testo né massima): "
            "il formato del portale potrebbe essere cambiato"
        )

    return ProvvedimentoDetail(
        guid=guid,
        estremi=estremi,
        massima="\n\n".join(filter(None, (_strip_cdata_html(t.findtext("massima") or "") for t in titoli))),
        testo_integrale=_strip_cdata_html(item.findtext("testo") or ""),
        oggetto="; ".join(filter(None, (_titolo(t) for t in titoli))),
    )


def _parse_detail_page(html: str) -> ProvvedimentoDetail:
    xml_str = _extract_xml_from_js(html, "xmlDettaglio")
    if not xml_str:
        raise _payload_mancante(html, "xmlDettaglio", "il provvedimento")
    return _parse_detail_xml(xml_str)


# ---------------------------------------------------------------------------
# The search form
# ---------------------------------------------------------------------------


def _scegli(valori: dict, chiave: str, nome: str):
    try:
        return valori[chiave.strip().lower()]
    except KeyError:
        raise ValueError(
            f"{nome} {chiave!r} non riconosciuto: valori ammessi {', '.join(valori)}"
        ) from None


def _filtro_ente(ente: str) -> _FiltroEnte | None:
    return _scegli(_FILTRI_ENTE, ente, "ente") if ente.strip() else None


def _parse_data(valore: str, nome: str) -> date | None:
    valore = valore.strip()
    if not valore:
        return None
    for formato in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(valore, formato).date()
        except ValueError:
            continue
    raise ValueError(f"{nome} {valore!r} non valida: usare GG/MM/AAAA (es. 01/01/2024)")


def _build_form(
    parole: str = "",
    tipo_criterio: str = "tutti",
    tipo_estremi: str = "",
    numero: str = "",
    data_da: str = "",
    data_a: str = "",
    ente: str = "",
    ordinamento: str = "rilevanza",
) -> dict[str, str]:
    """The advanced form as the portal expects it; ValueError for a value it would not understand."""
    if tipo_criterio.strip().lower() == "codice":
        raise ValueError(
            "il criterio 'codice' non è più offerto dal portale CeRDEF: "
            "per cercare un provvedimento per numero usare il parametro numero"
        )
    criterio = _scegli(CRITERI_RICERCA, tipo_criterio.strip() or "tutti", "criterio")
    ordine = _scegli(ORDINAMENTI, ordinamento.strip() or "rilevanza", "ordinamento")
    tipo = _scegli(TIPO_ESTREMI, tipo_estremi, "tipo_provvedimento") if tipo_estremi.strip() else ""
    filtro = _filtro_ente(ente)
    numero = numero.strip()
    if numero and not numero.isdigit():
        raise ValueError(
            f"numero {numero!r} non valido: indicare solo le cifre del provvedimento (es. 24823), "
            "anno ed ente vanno negli altri filtri"
        )
    da = _parse_data(data_da, "data_da")
    a = _parse_data(data_a, "data_a")
    if da and a and da > a:
        raise ValueError(f"data_da ({da:%d/%m/%Y}) è successiva a data_a ({a:%d/%m/%Y})")
    parole = parole.strip()
    if not (parole or numero or da or a or tipo or filtro):
        # The portal would answer "Occorre compilare almeno un campo".
        raise ValueError(
            "indicare almeno un criterio di ricerca: query, numero, data_da/data_a, ente o tipo_provvedimento"
        )
    if filtro and filtro.solo_primo_grado and not da:
        raise ValueError(
            "con ente='cgt_primo_grado' indicare anche data_da: il portale non ha un filtro per il solo "
            "primo grado, quindi si interrogano tutte le Corti di giustizia tributaria, e senza un limite "
            "di date la ricerca impiega circa 100 secondi (con un intervallo di 12 mesi, pochi secondi)"
        )

    modulo = dict(_FORM_DEFAULTS)
    modulo.update(parole=parole, tipoCriterioRicerca=criterio, tipo_ord=ordine, tipoEstremi=tipo, numero=numero)
    if filtro:
        modulo[filtro.campo] = filtro.valore
    for suffisso, giorno in (("Da", da), ("A", a)):
        if giorno:
            modulo[f"giornoDataEmissione{suffisso}"] = str(giorno.day)
            modulo[f"meseDataEmissione{suffisso}"] = str(giorno.month)
            modulo[f"annoDataEmissione{suffisso}"] = str(giorno.year)
    return modulo


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def format_result(doc: ProvvedimentoResult) -> str:
    """Format a single ProvvedimentoResult as markdown block."""
    lines = [f"### {doc.estremi or doc.guid}"]
    if doc.titoli:
        lines.append(f"**Oggetto**: {doc.titoli[:300]}")
    if doc.ente:
        lines.append(f"**Ente**: {doc.ente}")
    if doc.data:
        lines.append(f"**Data**: {doc.data}")
    lines.append(f"**GUID**: `{doc.guid}`")
    return "\n".join(lines)


def format_detail(detail: ProvvedimentoDetail, da_carattere: int = 1) -> str:
    """Format a ProvvedimentoDetail as markdown with truncation.

    Positions count `testo_integrale` (the massima is not part of it). The default
    answer keeps the massima and the first `_MAX_TEXT_LENGTH` characters of the text;
    `da_carattere` > 1 renders the window of the text that starts there (header lines
    only: the massima was already given by the first answer).
    """
    lines = [f"# {detail.estremi or detail.guid}"]

    if detail.oggetto:
        lines.append(f"**Oggetto**: {detail.oggetto}")
    if detail.collegio:
        lines.append(f"**Collegio**: {detail.collegio}")
    if detail.udienza:
        lines.append(f"**Udienza**: {detail.udienza}")
    if detail.ricorsi:
        lines.append(f"**Ricorsi**: {detail.ricorsi}")

    windowed = da_carattere > 1
    if detail.massima and not windowed:
        lines.append("\n## Massima\n")
        lines.append(detail.massima)

    if detail.testo_integrale:
        lines.append("\n## Testo Integrale\n")
        testo = detail.testo_integrale
        if windowed:
            body, note = page(testo, da_carattere, _MAX_TEXT_LENGTH)
            lines.append(body)
            lines.append(f"\n---\n{note}")
        else:
            truncated = len(testo) > _MAX_TEXT_LENGTH
            lines.append(testo[:_MAX_TEXT_LENGTH] if truncated else testo)
            if truncated:
                lines.append(
                    f"\n---\n*[Testo troncato a {_MAX_TEXT_LENGTH} caratteri su {len(testo)} totali: "
                    f"{resume_hint(_MAX_TEXT_LENGTH + 1)}]*"
                )
    elif windowed:
        lines.append(f"\n---\n*[da_carattere={da_carattere} oltre la fine del testo (0 caratteri)]*")

    if not detail.massima and not detail.testo_integrale:
        lines.append("\n_Il portale CeRDEF non riporta massima né testo integrale per questo provvedimento._")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------


async def search_giurisprudenza(
    parole: str = "",
    tipo_criterio: str = "tutti",
    tipo_estremi: str = "",
    numero: str = "",
    data_da: str = "",
    data_a: str = "",
    ente: str = "",
    ordinamento: str = "rilevanza",
    rows: int = 10,
) -> EsitoRicerca:
    """Search CeRDEF giurisprudenza tributaria.

    Raises ValueError for a filter the portal would not understand (before any
    request) and CerdefError when the portal answers with anything but a result
    list. No results means the portal itself counted zero, or -- with
    `ente="cgt_primo_grado"` -- that none of the items read is of first instance:
    `troncato` says whether items were left unread.
    """
    rows = max(1, min(rows, _MAX_RESULTS))
    modulo = _build_form(parole, tipo_criterio, tipo_estremi, numero, data_da, data_a, ente, ordinamento)
    filtro = _filtro_ente(ente)
    solo_primo_grado = filtro is not None and filtro.solo_primo_grado

    results: list[ProvvedimentoResult] = []
    seen: set[str] = set()

    def _add_new(pagina: _Pagina) -> int:
        """Keep the new items that pass the filter; return how many new items the answer had."""
        added = 0
        for doc in pagina.risultati:
            if doc.guid in seen:
                continue
            seen.add(doc.guid)
            added += 1
            if solo_primo_grado and not _is_primo_grado(doc.ente or doc.estremi):
                continue
            results.append(doc)
        return added

    async with CerdefSession() as session:
        resp = await retry_request(session.client, "POST", _SEARCH_URL, dataset="cerdef", data=modulo)
        pagina = _parse_search_page(resp.text)
        _add_new(pagina)

        # The paginator answers with the list so far plus the next 50 items. The
        # first-instance filter can discard every item of an answer, so the scan
        # stops after _MAX_RESULTS items read, whatever was kept.
        while len(results) < rows and pagina.altri and len(seen) < _MAX_RESULTS:
            resp = await retry_request(session.client, "GET", _PAGINATOR_URL, dataset="cerdef")
            pagina = _parse_search_page(resp.text)
            if _add_new(pagina) == 0:
                break

    return EsitoRicerca(
        risultati=results[:rows],
        totale=pagina.totale,
        esaminati=len(seen),
        troncato=solo_primo_grado and pagina.altri and len(results) < rows,
    )


async def fetch_provvedimento(guid: str) -> ProvvedimentoDetail:
    """Fetch the detail of a provvedimento by its GUID, as the search lists it (braces included).

    ValueError for an empty or malformed GUID (before any request), CerdefNonTrovato
    when the portal does not know the id, CerdefError for an unreadable answer.
    """
    guid = guid.strip()
    if not guid:
        raise ValueError(
            "indicare il GUID del provvedimento, come riportato da cerca_giurisprudenza_tributaria "
            "o ultime_sentenze_tributarie"
        )
    if not _GUID.match(guid):
        raise ValueError(
            f"GUID {guid!r} non valido: il GUID di un provvedimento CeRDEF ha la forma "
            "{B0F76E21-B5FA-4415-9D1D-44FF7B5741C1} ed è riportato in ogni risultato di "
            "cerca_giurisprudenza_tributaria o ultime_sentenze_tributarie"
        )
    async with httpx.AsyncClient(
        timeout=_TIMEOUT, headers=_HEADERS, follow_redirects=True
    ) as client:
        params = {"id": guid}
        try:
            # One attempt first: an unknown id is answered with a deterministic HTTP 500
            # that no retry can change, so only a different failure is worth retrying.
            resp = await retry_request(client, "GET", _DETAIL_URL, dataset="cerdef", params=params, max_retries=0)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 500 and _NPE in exc.response.text:
                raise CerdefNonTrovato(
                    f"provvedimento non trovato o GUID non valido ({guid}): il portale non conosce "
                    "questo identificativo; usare un GUID riportato da cerca_giurisprudenza_tributaria "
                    "o ultime_sentenze_tributarie"
                ) from exc
            resp = await _detail_with_retries(client, params, exc)
        except httpx.TransportError as exc:
            resp = await _detail_with_retries(client, params, exc)
    return _parse_detail_page(resp.text)


async def _detail_with_retries(client: httpx.AsyncClient, params: dict[str, str], first: Exception) -> httpx.Response:
    """Repeat the detail request after a failure that may be transient (5xx, transport).

    Two more attempts after the first one, like every other CeRDEF call.
    """
    if isinstance(first, httpx.HTTPStatusError) and first.response.status_code < 500:
        raise first
    try:
        return await retry_request(client, "GET", _DETAIL_URL, dataset="cerdef", params=params, max_retries=1)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code != 500:
            raise
        dettaglio = " ".join(exc.response.text.split())[:120]
        raise CerdefError(f"il portale ha risposto HTTP 500 per il GUID {params['id']} ({dettaglio})") from exc

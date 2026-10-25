"""Client for ANAC (Autorità Nazionale Anticorruzione) acts: delibere, pareri, linee guida.

Search: https://www.anticorruzione.it/consulta-i-documenti  (GET, Liferay search portlet)
Act:    https://www.anticorruzione.it/-/<slug>                (one page per act)

Read on 2026-10-22 (issue #51): robots.txt says `Allow: /` for every agent, the search needs no
login and answers a GET in about a second. The search page lists cards (date, title, link,
subject, tags); the page of an act carries its particulars (year, topic, category, type,
recipients), the subject, the "Riferimenti normativi" and "Parole chiave" paragraphs and the
official PDF. The full text exists only in that PDF: this client returns the PDF's link, it does
not extract its text (`AttoAnac.testo` stays empty until it does).

The open-data portal (dati.anticorruzione.it) answers automated requests with its firewall's
"Request Rejected" page: it is not used.
"""

import re
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from mcp_legal_it.core._http import async_client
from mcp_legal_it.lib._http import retry_request

_BASE = "https://www.anticorruzione.it"
_HOST = "www.anticorruzione.it"
_SEARCH_PATH = "/consulta-i-documenti"
# The only order this client asks for: newest first (the portal's "Più recente").
_SORT_DATA = "ddm__Dataclu0__date_Number_sortableDESC"
# The search's "Anno" filter (`year`): year -> the portal's category id, read from the form on
# 2026-10-22 (the same ids on every search page). A year not listed is searched without it.
ANNI: dict[str, str] = {
    "2026": "363294180",
    "2025": "276731294",
    "2024": "191123340",
    "2023": "94468268",
    "2022": "2731479",
    "2021": "2295812",
    "2020": "119139",
    "2019": "119138",
    "2018": "119137",
    "2017": "119191",
    "2016": "119190",
    "2015": "119189",
    "2014": "119188",
    "2013": "119187",
    "2012": "119192",
    "2011": "119193",
    "2010": "119194",
    "2009": "119195",
    "2008": "119196",
    "2007": "119197",
    "2006": "119198",
    "2005": "119199",
    "2004": "119200",
    "2003": "119201",
    "2002": "119202",
    "2001": "119203",
    "2000": "119204",
    "1999": "119214",
}
# Page sizes the portal offers (its own links); a request names one of these.
_DELTAS = (5, 10, 20, 30, 50, 75)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

_TIMEOUT = httpx.Timeout(30.0, connect=10.0)

# Types of act, as the portal's "Consulta i documenti" menu lists them (read 2026-10-22):
# key -> (the portal's `type` id, label, the singular the titles use).
TIPOLOGIE: dict[str, tuple[str, str, str]] = {
    "delibere": ("119160", "Delibere", "delibera"),
    "pareri_precontenzioso": ("119168", "Pareri di precontenzioso", "parere di precontenzioso"),
    "pareri_normativa": ("119167", "Pareri sulla normativa", "parere"),
    "linee_guida": ("119152", "Linee guida", "linee guida"),
    "bandi_tipo": ("119174", "Bandi tipo", "bando tipo"),
    "comunicati_presidente": ("119175", "Comunicati del Presidente", "comunicato del presidente"),
    "atti_presidente": ("2475285", "Atti a firma del Presidente", "atto"),
    "regolamenti": ("119157", "Regolamenti", "regolamento"),
    "provvedimenti_ordine": ("119163", "Provvedimenti d'ordine", "provvedimento"),
    "segnalazioni": ("119165", "Segnalazioni a Governo e Parlamento", "segnalazione"),
    "protocolli_vigilanza": ("31240561", "Protocolli di vigilanza collaborativa", "protocollo"),
    "protocolli_intesa": ("119164", "Protocolli di intesa e convenzioni", "protocollo"),
    "audizioni": ("119170", "Audizioni", "audizione"),
    "relazioni_annuali": ("2747381", "Relazioni annuali", "relazione"),
    "relazioni_vigilanza": ("255521458", "Relazioni di vigilanza collaborativa", "relazione"),
}

# Types whose titles carry a number AND the date after it ("Delibera n. 444 del 11 novembre
# 2025"): only these can be looked up by number and year. Linee guida and bandi tipo are numbered
# without a date in the title ("Linee guida n. 4"), so a lookup by year would mostly answer "not
# found": they are searched, like the unnumbered types (annual reports, hearings, statements).
NUMERATE = frozenset({"delibere", "pareri_precontenzioso", "pareri_normativa"})

# Results scanned when an act is looked up by number and year.
_RIGHE_RICERCA_NUMERO = 50

_ALIAS_TIPOLOGIA = {
    "delibera": "delibere",
    "precontenzioso": "pareri_precontenzioso",
    "parere precontenzioso": "pareri_precontenzioso",
    "parere di precontenzioso": "pareri_precontenzioso",
    "parere sulla normativa": "pareri_normativa",
    "parere normativa": "pareri_normativa",
    "funzione consultiva": "pareri_normativa",
    "linea guida": "linee_guida",
    "bando tipo": "bandi_tipo",
    "comunicato": "comunicati_presidente",
    "comunicato del presidente": "comunicati_presidente",
    "regolamento": "regolamenti",
}


class AnacPaginaInattesa(Exception):
    """The portal answered with a page this client cannot read (not "no results")."""


class AnacNonTrovato(LookupError):
    """No act matches the particulars asked for."""


@dataclass
class RisultatoAnac:
    """One card of the search page."""

    titolo: str
    path: str                      # "/-/delibera-n.-444-del-11-novembre-2025": reads the act
    data: str = ""                 # "11 nov 2025", as the card prints it
    oggetto: str = ""
    etichette: list[str] = field(default_factory=list)   # topic, category, type

    @property
    def url(self) -> str:
        return _BASE + self.path


@dataclass
class Allegato:
    nome: str
    url: str
    dimensione: str = ""


@dataclass
class AttoAnac:
    """The page of one act."""

    titolo: str
    url: str
    data: str = ""
    estremi: dict[str, str] = field(default_factory=dict)   # Anno, Argomento, Categorie, ...
    oggetto: str = ""
    riferimenti_normativi: str = ""
    parole_chiave: str = ""
    allegati: list[Allegato] = field(default_factory=list)
    # Full text of the act. Empty: the text is only in the PDF, which is not read (yet).
    testo: str = ""


def resolve_tipologia(tipologia: str) -> str:
    """The TIPOLOGIE key for *tipologia* (key, label or a common singular); "" for none."""
    t = re.sub(r"[\s_]+", " ", (tipologia or "").strip().lower().replace("’", "'"))
    if not t:
        return ""
    for key, (_id, label, _singolare) in TIPOLOGIE.items():
        if t in (key.replace("_", " "), label.lower()):
            return key
    if t in _ALIAS_TIPOLOGIA:
        return _ALIAS_TIPOLOGIA[t]
    raise ValueError(
        f"tipologia ANAC non riconosciuta: {tipologia!r}. Valori: " + ", ".join(TIPOLOGIE)
    )


def page_size(rows: int) -> int:
    """The portal's page size for *rows*: the smallest it offers that holds them.

    A page is always read whole, so page 2 of 15 rows (sent as 20) starts at the 21st result.
    """
    return next((d for d in _DELTAS if d >= rows), _DELTAS[-1])


def build_search_params(
    query: str = "", tipologia: str = "", rows: int = 10, pagina: int = 1, *,
    anno: str = "", tutte_le_parole: bool = False,
) -> dict:
    """The portal's GET parameters, newest first. The portal ORs the words by default:
    *tutte_le_parole* asks for every word (`searchType=and`). *anno* uses the "Anno" filter."""
    params = {"isDocumentSearchPortlet": "true", "q": query or "", "sort": _SORT_DATA,
              "delta": str(page_size(rows))}
    if tutte_le_parole:
        params["searchType"] = "and"
    anno = str(anno or "").strip()
    if anno:
        if anno not in ANNI:
            raise ValueError(f"anno ANAC non disponibile nel filtro del portale: {anno!r} "
                             f"(anni: {min(ANNI)}-{max(ANNI)})")
        params["year"] = ANNI[anno]
    key = resolve_tipologia(tipologia)
    if key:
        params["type"] = TIPOLOGIE[key][0]
    if pagina > 1:
        params["start"] = str(pagina)
    return params


def _text(node) -> str:
    return re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip() if node else ""


def parse_search(html: str) -> tuple[list[RisultatoAnac], int]:
    """Cards and the portal's total. A page without the results block raises AnacPaginaInattesa."""
    soup = BeautifulSoup(html, "lxml")
    totale_node = soup.select_one(".left-zone .num")
    cards = soup.select("div.wd-card-doc")
    if totale_node is None and not cards:
        raise AnacPaginaInattesa("la pagina di ricerca di ANAC non contiene l'elenco dei risultati")
    cifre = _text(totale_node).replace(".", "") if totale_node else ""   # "6.169" or "6169"
    totale = int(cifre) if cifre.isdigit() else len(cards)
    risultati = []
    for card in cards:
        link = card.select_one("h3.card-title a[href]")
        if link is None:
            continue
        path = link["href"]
        parsed = urlparse(path)
        if parsed.hostname == _HOST:  # an absolute link to the same site, http or https
            path = parsed.path
        oggetto = card.select_one(".free-text > div")
        risultati.append(RisultatoAnac(
            titolo=link.get("title") or _text(link),
            path=path,
            data=_text(card.select_one("span.data")),
            oggetto=_text(oggetto),
            etichette=[_text(li) for li in card.select("ul.card-tags-list li") if _text(li)],
        ))
    return risultati, totale


def _righe(node) -> str:
    """The text of *node*, one line per <br>: inline tags (bold, links) do not break a line."""
    for br in node.find_all("br"):
        br.replace_with("\n")
    righe = (re.sub(r"\s+", " ", r).strip() for r in node.get_text("").split("\n"))
    return "\n".join(r for r in righe if r)


def _sezione(paragrafo) -> tuple[str, str]:
    """("Riferimenti normativi", "art. 23 ...") for a paragraph that opens with a bold heading."""
    strong = paragrafo.find("strong")
    if strong is None:
        return "", _righe(paragrafo)
    titolo = _text(strong)
    strong.extract()
    return titolo, _righe(paragrafo)


def parse_atto(html: str, url: str) -> AttoAnac:
    soup = BeautifulSoup(html, "lxml")
    dettaglio = soup.select_one(".wd-document-detail")
    if dettaglio is None:
        raise AnacPaginaInattesa("la pagina non è la scheda di un atto ANAC")
    estremi = {}
    for point in dettaglio.select(".points .point"):
        spans = point.find_all("span")
        if len(spans) >= 2:
            estremi[_text(spans[0]).rstrip(":")] = _text(spans[1])
    dati = dettaglio.select_one(".document-data")
    titolo_atto = _text(dati.find("h2")) if dati else ""
    if not titolo_atto:
        raise AnacPaginaInattesa("la scheda dell'atto ANAC non ha un titolo leggibile")
    atto = AttoAnac(titolo=titolo_atto, url=url, data=_text(dati.find("h3")), estremi=estremi)
    oggetto: list[str] = []
    sezione = ""   # a heading in a paragraph of its own names the paragraphs after it
    for p in dati.select("p"):
        intero = _righe(p)
        titolo, corpo = _sezione(p)
        chiave = titolo.lower()
        if chiave.startswith(("riferimenti normativi", "parole chiave")):
            sezione = "riferimenti" if chiave.startswith("riferimenti") else "parole"
            if not corpo:
                continue
        elif titolo:
            sezione = ""   # a bold phrase that is not a known heading: part of the subject
            corpo = intero
        if not corpo:
            continue
        if sezione == "riferimenti":
            atto.riferimenti_normativi = "\n".join(filter(None, [atto.riferimenti_normativi, corpo]))
        elif sezione == "parole":
            atto.parole_chiave = "\n".join(filter(None, [atto.parole_chiave, corpo]))
        else:
            oggetto.append(corpo)
    atto.oggetto = "\n".join(oggetto)
    for a in soup.select(".wd-card-download a[href]"):
        nome = _text(a.select_one("h3")) or a["href"].rsplit("/", 1)[-1]
        atto.allegati.append(Allegato(
            nome=nome, url=urljoin(_BASE, a["href"]), dimensione=_text(a.select_one(".free-text")),
        ))
    return atto


def path_atto(riferimento: str) -> str:
    """The act's path from what the search returned: "/-/<slug>" or its full URL on the portal.

    Anything else (another host, another path) is refused: this tool reads ANAC acts only.
    """
    rif = (riferimento or "").strip()
    if rif.startswith(("http://", "https://")):
        parsed = urlparse(rif)
        if parsed.hostname != _HOST:
            raise ValueError(f"l'indirizzo non è una pagina di {_HOST}: {rif}")
        rif = parsed.path
    # A slug: no dot-segment and no encoded slash, backslash or dot (the host is fixed anyway).
    if not re.fullmatch(r"/-/(?!\.)[\w.%-]+", rif) or re.search(r"\.\.|%2[fFeE]|%5[cC]", rif):
        raise ValueError(
            "riferimento ANAC non valido: usare il percorso restituito dalla ricerca "
            "(es. \"/-/delibera-n.-444-del-11-novembre-2025\") oppure tipologia, numero e anno"
        )
    return rif


# The act's own number and the year of the date right after it, in the two forms the titles use:
# "n. 444 del 11 novembre 2025", "n. 31 del 07/02/2019" (and "n. 12/2024"). One pass, no
# nested quantifier: linear in the title.
_NUMERO_E_ANNO = re.compile(
    r"\bn\.\s*(\d+)(?:\s+del\s+(?:\d{1,2}\s+[^\W\d_]+\s+|\d{1,2}/\d{1,2}/)|\s*/\s*)(\d{4})\b"
)


def titolo_corrisponde(titolo: str, numero: str, anno: str) -> bool:
    """Whether a title such as "Delibera n. 444 del 11 novembre 2025" names that number and year.

    Only the act's own number counts, the first "n. N" of the title, and the year is the one of
    the date that follows it: "Delibera n. 444 del 11 novembre 2025 - annullamento della delibera
    n. 12 del 2024" is n. 444/2025, never 444/2024 nor 12/2024.
    """
    t = titolo.lower()
    primo = re.search(r"\bn\.\s*\d", t)
    m = _NUMERO_E_ANNO.match(t, primo.start()) if primo else None
    if not m:
        return False
    return m.group(1).lstrip("0") == str(numero).lstrip("0") and m.group(2) == str(anno)


async def search_atti(
    query: str = "", tipologia: str = "", rows: int = 10, pagina: int = 1, *,
    anno: str = "", tutte_le_parole: bool = False,
) -> tuple[list[RisultatoAnac], int]:
    """One page of results, newest first, and the portal's total."""
    params = build_search_params(query, tipologia, rows, pagina, anno=anno,
                                 tutte_le_parole=tutte_le_parole)
    async with async_client("anac", timeout=_TIMEOUT, headers=_HEADERS, follow_redirects=True) as client:
        resp = await retry_request(client, "GET", _BASE + _SEARCH_PATH, dataset="anac", params=params)
    risultati, totale = parse_search(resp.text)
    return risultati[:rows], totale


async def fetch_atto(riferimento: str) -> AttoAnac:
    url = _BASE + path_atto(riferimento)
    async with async_client("anac", timeout=_TIMEOUT, headers=_HEADERS, follow_redirects=True) as client:
        resp = await retry_request(client, "GET", url, dataset="anac")
    return parse_atto(resp.text, url)


async def find_atto(tipologia: str, numero: str, anno: str) -> RisultatoAnac:
    """The act of that type, number and year, through the portal's search (one request)."""
    key = resolve_tipologia(tipologia)
    if not key:
        raise ValueError("per cercare un atto per numero e anno indicare anche la tipologia")
    numero, anno = str(numero).strip(), str(anno).strip()
    if key not in NUMERATE:
        raise ValueError(
            f"gli atti «{TIPOLOGIE[key][1]}» non hanno un numero nel titolo: cercarli con "
            "cerca_atti_anac e leggerli con il riferimento restituito"
        )
    if not (numero.isdigit() and re.fullmatch(r"\d{4}", anno)):
        raise ValueError("numero e anno devono essere numerici (es. numero=\"444\", anno=\"2025\")")
    # The number, within the type and the year's filter: one result for delibera 444/2025 (read
    # 2026-10-22). Without the year filter the portal ORs the words over every act of the type
    # (6169 delibere) and newest first the act is buried (#82 review).
    if anno in ANNI:
        risultati, _totale = await search_atti(numero, key, rows=_RIGHE_RICERCA_NUMERO,
                                               anno=anno, tutte_le_parole=True)
        ambito = f"tra gli atti del {anno} che contengono «{numero}»"
    else:
        risultati, _totale = await search_atti(f"{numero} {anno}", key, rows=_RIGHE_RICERCA_NUMERO,
                                               tutte_le_parole=True)
        ambito = (f"tra i {len(risultati)} atti più recenti che contengono «{numero}» e «{anno}» "
                  "(l'anno non è tra quelli del filtro del portale)")
    for r in risultati:
        if titolo_corrisponde(r.titolo, numero, anno):
            return r
    raise AnacNonTrovato(
        f"nessun atto ANAC «{TIPOLOGIE[key][1]}» n. {numero} del {anno} {ambito}: "
        "verificare con cerca_atti_anac e leggere l'atto dal riferimento restituito"
    )


def format_result(r: RisultatoAnac) -> str:
    lines = [f"**{r.titolo}**" + (f" ({r.data})" if r.data else "")]
    if r.etichette:
        lines.append(f"- Classificazione: {' · '.join(r.etichette)}")
    if r.oggetto:
        lines.append(f"- Oggetto: {r.oggetto}")
    lines.append(f"- Riferimento per leggi_atto_anac: `{r.path}`")
    return "\n".join(lines)


def format_atto(atto: AttoAnac) -> str:
    lines = [f"# {atto.titolo}"]
    if atto.data:
        lines.append(f"**Data**: {atto.data}")
    for campo, valore in atto.estremi.items():
        lines.append(f"**{campo}**: {valore}")
    if atto.oggetto:
        lines += ["", "## Oggetto", atto.oggetto]
    if atto.riferimenti_normativi:
        lines += ["", "## Riferimenti normativi", atto.riferimenti_normativi]
    if atto.parole_chiave:
        lines += ["", "## Parole chiave", atto.parole_chiave]
    if atto.testo:
        lines += ["", "## Testo", atto.testo]
    if atto.allegati:
        lines += ["", "## Documento ufficiale"]
        for al in atto.allegati:
            lines.append(f"- [{al.nome}]({al.url})" + (f" ({al.dimensione})" if al.dimensione else ""))
    if not atto.testo:
        lines += ["", "*Nota: il testo integrale dell'atto è nel PDF ufficiale indicato sopra; questo "
                      "strumento riporta la scheda pubblicata da ANAC (estremi, oggetto, riferimenti "
                      "normativi, parole chiave), non il contenuto del PDF. La scheda non dice se "
                      "l'atto è stato superato o annullato.*"]
    lines += ["", f"Fonte: {atto.url}"]
    return "\n".join(lines)

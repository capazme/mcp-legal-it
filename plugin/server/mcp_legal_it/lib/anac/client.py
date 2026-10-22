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


def _delta(rows: int) -> int:
    return next((d for d in _DELTAS if d >= rows), _DELTAS[-1])


def build_search_params(query: str = "", tipologia: str = "", rows: int = 10, pagina: int = 1) -> dict:
    params = {"isDocumentSearchPortlet": "true", "q": query or "", "sort": _SORT_DATA,
              "delta": str(_delta(rows))}
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
    totale = int(_text(totale_node)) if totale_node and _text(totale_node).isdigit() else len(cards)
    risultati = []
    for card in cards:
        link = card.select_one("h3.card-title a[href]")
        if link is None:
            continue
        path = link["href"]
        if path.startswith(_BASE):
            path = path[len(_BASE):]
        oggetto = card.select_one(".free-text > div")
        risultati.append(RisultatoAnac(
            titolo=link.get("title") or _text(link),
            path=path,
            data=_text(card.select_one("span.data")),
            oggetto=_text(oggetto),
            etichette=[_text(li) for li in card.select("ul.card-tags-list li") if _text(li)],
        ))
    return risultati, totale


def _sezione(paragrafo) -> tuple[str, str]:
    """("Riferimenti normativi", "art. 23 ...") for a paragraph that opens with a bold heading."""
    strong = paragrafo.find("strong")
    if strong is None:
        return "", _text(paragrafo)
    titolo = _text(strong)
    strong.extract()
    righe = [r.strip() for r in paragrafo.get_text("\n").splitlines() if r.strip()]
    return titolo, "\n".join(righe)


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
    atto = AttoAnac(
        titolo=_text(dati.find("h2")) if dati else "",
        url=url,
        data=_text(dati.find("h3")) if dati else "",
        estremi=estremi,
    )
    for p in (dati.select("p") if dati else []):
        titolo, corpo = _sezione(p)
        if titolo.lower().startswith("riferimenti normativi"):
            atto.riferimenti_normativi = corpo
        elif titolo.lower().startswith("parole chiave"):
            atto.parole_chiave = corpo
        elif not titolo and corpo and not atto.oggetto:
            righe = [r.strip() for r in p.get_text("\n").splitlines() if r.strip()]
            atto.oggetto = "\n".join(righe)
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
    if not re.fullmatch(r"/-/[\w.%-]+", rif):
        raise ValueError(
            "riferimento ANAC non valido: usare il percorso restituito dalla ricerca "
            "(es. \"/-/delibera-n.-444-del-11-novembre-2025\") oppure tipologia, numero e anno"
        )
    return rif


def titolo_corrisponde(titolo: str, numero: str, anno: str) -> bool:
    """Whether a title such as "Delibera n. 444 del 11 novembre 2025" names that number and year."""
    t = titolo.lower()
    return bool(re.search(rf"\bn\.\s*{re.escape(numero)}\b", t)) and bool(re.search(rf"\b{re.escape(anno)}\b", t))


async def search_atti(
    query: str = "", tipologia: str = "", rows: int = 10, pagina: int = 1,
) -> tuple[list[RisultatoAnac], int]:
    """One page of results, newest first, and the portal's total."""
    params = build_search_params(query, tipologia, rows, pagina)
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
    if not (numero.isdigit() and re.fullmatch(r"\d{4}", anno)):
        raise ValueError("numero e anno devono essere numerici (es. numero=\"444\", anno=\"2025\")")
    singolare = TIPOLOGIE[key][2]
    risultati, _totale = await search_atti(f"{singolare} n. {numero} {anno}", key, rows=20)
    for r in risultati:
        if titolo_corrisponde(r.titolo, numero, anno):
            return r
    raise AnacNonTrovato(f"nessun atto ANAC «{TIPOLOGIE[key][1]}» n. {numero} del {anno}")


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

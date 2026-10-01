"""Client for Garante per la Protezione dei Dati Personali (GPDP).

Endpoint: https://www.garanteprivacy.it/web/guest/home/ricerca
          https://www.garanteprivacy.it/web/guest/home/docweb/-/docweb-display/print/{ID}

Il sito usa Liferay Portal — nessuna API pubblica JSON. Scraping HTML via BeautifulSoup.
Documenti identificati da DocWeb ID (interi sequenziali, es. 9677876 per cookie guidelines 2021).
"""

import re
from dataclasses import dataclass, field
from datetime import date

import httpx
from bs4 import BeautifulSoup

from .._http import note_source
from .._paging import page, resume_hint

_BASE = "https://www.garanteprivacy.it"
_SEARCH_PATH = "/web/guest/home/ricerca"
_PRINT_PATH = "/web/guest/home/docweb/-/docweb-display/print"
_DOC_PATH = "/web/guest/home/docweb/-/docweb-display/docweb"
_PORTLET = "g_gpdp5_search_GGpdp5SearchPortlet"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": _BASE + "/",
}

_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
_MAX_TEXT_LENGTH = 6000
_RESULTS_PER_PAGE = 10

# ---------------------------------------------------------------------------
# Tipologia tree of the search portal (jsTreeTipologia), read on 2026-09-29 from
# https://www.garanteprivacy.it/web/guest/home/ricerca. Rows are (id, name, parent id; "" = root).
# The portal filters on the EXACT nodes listed in `idsTipologia` (comma separated) and does NOT
# include the children of a parent node: "Provvedimenti" (10533) alone returns only the cards
# classified directly as "Provvedimenti". To search a whole family the client sends the node and
# all its descendants. tests/unit/test_gpdp_live.py compares this table with the live tree.
# ---------------------------------------------------------------------------
TIPOLOGIE: tuple[tuple[str, str, str], ...] = (
    ("9445099", "Accreditamento degli organismi di certificazione", "10533"),
    ("2005281", "AllegatiCodice", "2034595"),
    ("10481", "Altri atti o documenti", "2036805"),
    ("9567234", "Ammonimento", "10533"),
    ("10170750", "Attività ispettiva", ""),
    ("2010731", "Audizioni e memorie", ""),
    ("10484", "Autorizzazione", "10533"),
    ("10485", "Autorizzazione generale", "10533"),
    ("2034210", "Autorizzazione trasferimento dati estero", "10533"),
    ("2024563", "Autorizzazione trasferimento dati verso Paesi terzi", "2034210"),
    ("9660377", "Avvertimento", "10533"),
    ("2034211", "Bcr", "2034210"),
    ("10488", "Blocco del trattamento", "10533"),
    ("10489", "Bollettino", "9271481"),
    ("9119875", "Codice di condotta", ""),
    ("2017504", "Collana contributi", "9271481"),
    ("10490", "Comunicato stampa", "2040802"),
    ("9150852", "Consultazione preventiva per adozione della DPIA", "10533"),
    ("10492", "Consultazione pubblica", "10533"),
    ("10498", "Decisione su ricorso", "10533"),
    ("10499", "Deliberazione", "10533"),
    ("10500", "Divieto del trattamento", "10533"),
    ("2036805", "Documenti", ""),
    ("10506", "EDPB (ex Gruppo Articolo 29)", "2036805"),
    ("10503", "Esonero informativa", "10533"),
    ("10187303", "FAQ", ""),
    ("10502", "Giurisprudenza", ""),
    ("10509", "Iniziative ed eventi", ""),
    ("2010732", "Interventi saggi contributi", "9271481"),
    ("9150853", "Libri su privacy e giornalismo", "2017504"),
    ("10516", "Linee guida", "10533"),
    ("10518", "Massimario", "9271481"),
    ("10521", "Modulistica", "2036805"),
    ("10523", "News", "2040802"),
    ("10524", "Newsletter", "2040802"),
    ("2034595", "Normativa", ""),
    ("2008296", "Normativa comunitaria e internazionale", "2034595"),
    ("10525", "Normativa italiana", "2034595"),
    ("7447479", "Note istituzionali", "2036805"),
    ("10526", "Ordinanza ingiunzione o revoca", "10533"),
    ("10527", "Parere del Garante", "10533"),
    ("10528", "Particolari accertamenti", "10533"),
    ("10118752", "podcast", ""),
    ("10529", "Prescrizioni del Garante", "10533"),
    ("10530", "Prescrizioni e divieto del Garante", "10533"),
    ("9094461", "Protocolli e convenzioni", "2036805"),
    ("10533", "Provvedimenti", ""),
    ("10532", "Provvedimenti a carattere generale", "10533"),
    ("2010735", "Provvedimenti ex art. 110 del Codice", "10533"),
    ("9271481", "Pubblicazioni", ""),
    ("10535", "Quesiti di soggetti pubblici e privati", "10533"),
    ("2086918", "Rassegna stampa", "2040802"),
    ("2038802", "Regolamento del Garante", "2034595"),
    ("9615872", "Regole deontologiche", ""),
    ("10536", "Relazione annuale", "2036805"),
    ("10515", "Saggi", "9271481"),
    ("2005731", "Scheda di documentazione", "9271481"),
    ("10538", "Scheda informativa", "2036805"),
    ("10540", "Segnalazione al Parlamento e al Governo e note istituzionali", ""),
    ("2040802", "Stampa e comunicazione", ""),
    ("2040803", "Trasparenza", ""),
    ("10522", "Vademecum e campagne informative", "2040802"),
    ("10546", "Verifica preliminare", "10533"),
)

# Spoken forms that are not a substring of any node name (singular of the parent node, the
# fining instrument, ...). Values are exact node names of TIPOLOGIE.
_TIPOLOGIA_ALIAS = {
    "provvedimento": "Provvedimenti",
    "sanzione": "Ordinanza ingiunzione o revoca",
    "sanzioni": "Ordinanza ingiunzione o revoca",
    "ordinanza": "Ordinanza ingiunzione o revoca",
}


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().casefold())


def tipologie_provvedimenti() -> list[str]:
    """Names of the leaf tipologie that sit under the "Provvedimenti" node (10533)."""
    return [name for _id, name, parent in TIPOLOGIE if parent == "10533"]


def _descendants(node_id: str) -> list[str]:
    out = [node_id]
    for _id, _name, parent in TIPOLOGIE:
        if parent == node_id:
            out.extend(_descendants(_id))
    return out


def resolve_tipologia(tipologia: str) -> list[str]:
    """Map a tipologia typed by the user to the portal node ids for `idsTipologia`.

    Order of resolution: exact node name, alias ("provvedimento" is the "Provvedimenti" family),
    then substring of a node name ("parere" -> "Parere del Garante", "linee guida" -> "Linee
    guida"). A matched node is always expanded with its descendants. Raises ValueError when no
    node matches, so a wrong value is an explicit error and never a silent empty result.
    """
    wanted = _norm(tipologia)
    if not wanted:
        return []
    names = {_norm(name): node_id for node_id, name, _parent in TIPOLOGIE}
    if wanted in names:
        roots = [names[wanted]]
    elif wanted in _TIPOLOGIA_ALIAS:
        roots = [names[_norm(_TIPOLOGIA_ALIAS[wanted])]]
    else:
        roots = [node_id for node_id, name, _parent in TIPOLOGIE if wanted in _norm(name)]
    if not roots:
        raise ValueError(
            f"tipologia non riconosciuta: {tipologia!r}. Valori ammessi tra i provvedimenti: "
            + ", ".join(tipologie_provvedimenti())
            + " (oppure 'provvedimento' per tutti); altre tipologie del portale: "
            + ", ".join(sorted({name for _id, name, parent in TIPOLOGIE if parent != "10533"}))
        )
    ids: list[str] = []
    for root in roots:
        for node_id in _descendants(root):
            if node_id not in ids:
                ids.append(node_id)
    return ids


def normalize_date(value: str, campo: str = "data") -> str:
    """Return `value` as AAAA-MM-GG, the only format the portal's <input type=date> accepts.

    Accepts GG/MM/AAAA (the format documented by the tools) and AAAA-MM-GG; an empty string
    stays empty. Any other format, or a non-existent calendar day, raises ValueError: the
    portal answers "Nessun risultato trovato" to a date it cannot read, a silent false negative.
    """
    text = (value or "").strip()
    if not text:
        return ""
    m = re.fullmatch(r"(\d{2})/(\d{2})/(\d{4})", text)
    if m:
        day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
    else:
        m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", text)
        if not m:
            raise ValueError(
                f"{campo} non valida: {value!r} (usare GG/MM/AAAA, es. 31/12/2024, "
                "oppure AAAA-MM-GG)"
            )
        year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        raise ValueError(f"{campo} non valida: {value!r} (giorno inesistente)") from None


_UNAVAILABLE_MSG = "Il contenuto o il file richiesto non è disponibile"
# Page toolbar ("Ascolta / Menù azioni / Stampa / Condivisione / e-mail / facebook / ..."): it
# opens the text of every DocWeb print page and is not part of the document.
_TOOLBAR_LINES = frozenset(
    {"ascolta", "menù azioni", "stampa", "condivisione", "e-mail", "facebook", "linkedin", "twitter"}
)
_TOOLBAR_WINDOW = 25  # lines from the top of the page in which the toolbar lives


class DocNotAvailable(LookupError):
    """The portal answers 200 with "Il contenuto o il file richiesto non è disponibile"."""

    def __init__(self, docweb_id: int):
        super().__init__(f"DocWeb {docweb_id} non disponibile")
        self.docweb_id = docweb_id


@dataclass
class DocResult:
    docweb_id: int
    title: str
    date: str           # DD/MM/YYYY
    tipologia: str
    argomenti: list[str] = field(default_factory=list)
    abstract: str = ""


def _build_search_params(
    query: str,
    data_da: str = "",
    data_a: str = "",
    tipologia_id: str = "",
    argomento_id: str = "",
    page: int = 1,
    sort_by: str = "data",
) -> dict:
    prefix = f"_{_PORTLET}_"
    # dataInizio/dataFine are <input type="date">: the portal reads only AAAA-MM-GG
    return {
        "p_p_id": _PORTLET,
        "p_p_lifecycle": "0",
        "p_p_state": "normal",
        "p_p_mode": "view",
        f"{prefix}mvcRenderCommandName": "/renderSearch",
        f"{prefix}text": query,
        f"{prefix}dataInizio": normalize_date(data_da, "data_da"),
        f"{prefix}dataFine": normalize_date(data_a, "data_a"),
        f"{prefix}idsTipologia": tipologia_id,
        f"{prefix}idsArgomenti": argomento_id,
        f"{prefix}ordinamentoPer": "DESC",
        f"{prefix}ordinamentoTipo": sort_by,
        f"{prefix}cur": str(page),
    }


def _parse_results(html: str) -> list[DocResult]:
    """Parse search results HTML into DocResult list.

    Real page uses Bootstrap card layout (Liferay portlet):
    - Result container: <div class="card-risultato">
    - Title link:       <a class="titolo-risultato ...">
    - Date:             <div class="data-risultato"><p>DD/MM/YYYY</p>
    - Abstract:         <p class="estratto-risultato ...">
    - Tipologia/Args:   <p class="ricercaArgomentiPar"> labels + badge links in next sibling
    """
    soup = BeautifulSoup(html, "lxml")
    results = []

    for card in soup.find_all("div", class_="card-risultato"):
        # Title and docweb ID
        link = card.find("a", class_="titolo-risultato")
        if not link:
            continue
        href = link.get("href", "")
        id_match = re.search(r"/docweb/(\d+)", href)
        if not id_match:
            continue

        docweb_id = int(id_match.group(1))
        title = link.get_text(strip=True)
        # Strip trailing [ID] suffix from title (e.g. "Provvedimento ... [10211780]")
        title = re.sub(r"\s*\[\d+\]\s*$", "", title).strip()

        # Date
        date_div = card.find("div", class_="data-risultato")
        date_p = date_div.find("p") if date_div else None
        date_str = date_p.get_text(strip=True) if date_p else ""

        # Abstract
        abstract_p = card.find("p", class_="estratto-risultato")
        abstract = abstract_p.get_text(" ", strip=True) if abstract_p else ""
        abstract = re.sub(r"\[…\]|\[\.\.\.\]|\[\.{3}\]", "", abstract).strip()

        # Tipologia and Argomenti — parsed from <p class="ricercaArgomentiPar"> labels
        tipologia = ""
        argomenti = []

        for label_p in card.find_all("p", class_="ricercaArgomentiPar"):
            label_text = label_p.get_text(strip=True)
            # Badges are in the next column div (sibling of label_p.parent)
            parent_col = label_p.parent
            next_col = parent_col.find_next_sibling("div") if parent_col else None
            badges = []
            if next_col:
                badges = [
                    a.get_text(strip=True)
                    for a in next_col.find_all("a")
                    if a.get_text(strip=True)
                ]
            if "Tipologia" in label_text:
                tipologia = badges[0] if badges else ""
            elif "Argomenti" in label_text or "Argomento" in label_text:
                argomenti = badges

        results.append(DocResult(
            docweb_id=docweb_id,
            title=title,
            date=date_str,
            tipologia=tipologia,
            argomenti=argomenti,
            abstract=abstract,
        ))

    return results


def _parse_doc(html: str, docweb_id: int) -> tuple[str, str]:
    """Parse document print page HTML. Returns (title, body_text).

    Raises DocNotAvailable when the portal answers with its "contenuto non disponibile" page.
    """
    soup = BeautifulSoup(html, "lxml")

    for tag in soup(["script", "style", "nav", "header", "footer"]):
        tag.decompose()
    # Remove Liferay social sharing / toolbar sections
    for cls in ["azioni", "condivisione", "taglib-social-bookmarks", "print-button"]:
        for el in soup.find_all(class_=lambda c: c and cls in c.lower()):
            el.decompose()

    heading = soup.find("h1") or soup.find("h2")
    raw_title = heading.get_text(strip=True) if heading else f"Documento DocWeb {docweb_id}"
    # Strip trailing [ID] suffix
    title = re.sub(r"\s*\[\d+\]\s*$", "", raw_title).strip() or raw_title

    body = soup.find("body")
    text = body.get_text("\n", strip=True) if body else ""

    # An unknown or unpublished id is a 200 page holding only the portal's own message (no
    # heading): it is an error, not a document.
    if _UNAVAILABLE_MSG in text and heading is None and len(text) < 300:
        raise DocNotAvailable(docweb_id)

    lines = text.split("\n")
    head = [ln for ln in lines[:_TOOLBAR_WINDOW] if ln.strip().casefold() not in _TOOLBAR_LINES]
    text = "\n".join(head + lines[_TOOLBAR_WINDOW:])
    text = re.sub(r"\n{3,}", "\n\n", text)

    return title, text


def format_result(doc: DocResult) -> str:
    """Format a single DocResult as markdown block."""
    url = f"{_BASE}{_DOC_PATH}/{doc.docweb_id}"
    lines = [f"### {doc.title}"]
    if doc.tipologia:
        lines.append(f"**Tipo**: {doc.tipologia}")
    if doc.date:
        lines.append(f"**Data**: {doc.date}")
    lines.append(f"**DocWeb**: [{doc.docweb_id}]({url})")
    if doc.argomenti:
        lines.append(f"**Argomenti**: {', '.join(doc.argomenti)}")
    if doc.abstract:
        disp = doc.abstract[:300]
        if len(doc.abstract) > 300:
            disp += "…"
        lines.append(f"**Estratto**: {disp}")
    return "\n".join(lines)


def format_full(title: str, text: str, docweb_id: int, da_carattere: int = 1) -> str:
    """Format full document as markdown.

    Positions (``da_carattere`` and the ones in the notes) count ``text``, the
    document body as extracted from the print page. With ``da_carattere`` > 1 the
    answer is the window of ``text`` that starts there (see src/lib/_paging.py).
    """
    url = f"{_BASE}{_DOC_PATH}/{docweb_id}"
    header = [f"# {title}", f"**DocWeb**: [{docweb_id}]({url})", ""]
    if da_carattere > 1:
        body, note = page(text, da_carattere, _MAX_TEXT_LENGTH)
        lines = header + ([body] if body else [])
        lines.append(f"\n---\n{note}")
        return "\n".join(lines)
    truncated = len(text) > _MAX_TEXT_LENGTH
    body = text[:_MAX_TEXT_LENGTH] if truncated else text
    lines = header + [body]
    if truncated:
        lines.append(
            f"\n---\n*[Testo troncato a {_MAX_TEXT_LENGTH} caratteri su {len(text)} totali: "
            f"{resume_hint(_MAX_TEXT_LENGTH + 1)}]*"
        )
    return "\n".join(lines)


async def search_docs(
    query: str = "",
    data_da: str = "",
    data_a: str = "",
    tipologia_id: str = "",
    argomento_id: str = "",
    rows: int = 10,
    sort_by: str = "data",
) -> list[DocResult]:
    """Search GPDP documents. Fetches multiple pages if rows > 10."""
    rows = min(rows, 50)
    results: list[DocResult] = []
    page = 1

    async with httpx.AsyncClient(
        timeout=_TIMEOUT, headers=_HEADERS, follow_redirects=True
    ) as client:
        while len(results) < rows:
            params = _build_search_params(
                query=query,
                data_da=data_da,
                data_a=data_a,
                tipologia_id=tipologia_id,
                argomento_id=argomento_id,
                page=page,
                sort_by=sort_by,
            )
            resp = await client.get(_BASE + _SEARCH_PATH, params=params)
            resp.raise_for_status()
            note_source("gpdp", str(resp.url) if hasattr(resp, "url") else "")

            page_results = _parse_results(resp.text)
            if not page_results:
                break

            results.extend(page_results)
            page += 1

            if len(page_results) < _RESULTS_PER_PAGE:
                break

    return results[:rows]


async def fetch_doc(docweb_id: int) -> tuple[str, str]:
    """Fetch full document text via print URL. Returns (title, text)."""
    url = f"{_BASE}{_PRINT_PATH}/{docweb_id}"
    async with httpx.AsyncClient(
        timeout=_TIMEOUT, headers=_HEADERS, follow_redirects=True
    ) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        note_source("gpdp", str(resp.url) if hasattr(resp, "url") else "")
        return _parse_doc(resp.text, docweb_id)

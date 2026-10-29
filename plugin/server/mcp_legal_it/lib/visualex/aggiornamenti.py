"""The amendments of a Normattiva article, read from its per-version update tables.

Normattiva gives each version of an article its own page (``/atto/caricaArticolo?
art.versione=k&...``) and its own update table (``/do/atto/vediAggiornamentiAllArticolo?
...&art.versione=k``). Measured on 29 Oct 2026 (art. 13 and 2-ter d.lgs. 196/2003, art. 2
c.c., art. 64-bis CCII, art. 1 d.P.R. 131/1986), the table of version k lists the
amendments that produced version k, and the version's page states its window («Testo in
vigore dal … al …»). So an amendment's entry into force is the start of the version it
produced, read, not deduced. Both pages need the session cookie the article page sets:
asked without it, they answer Normattiva's generic error page.

Pure parsing here; the network walk is in ``scraper.fetch_article_updates``.
"""

from __future__ import annotations

import html as _html
import re
import warnings
from datetime import date
from typing import Optional

import httpx
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

from .map import normalize_act_type

_MESI = {
    "gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4, "maggio": 5, "giugno": 6,
    "luglio": 7, "agosto": 8, "settembre": 9, "ottobre": 10, "novembre": 11, "dicembre": 12,
}

# The update table's link, on the article page (data-href) and on a version page.
_LINK = re.compile(r"/?do/atto/vediAggiornamentiAllArticolo\?[^\"'<>\s]+")
_VERSIONE = re.compile(r"art\.versione=(\d+)")
_PARAM = re.compile(r"art\.(idArticolo|idSottoArticolo|flagTipoArticolo|codiceRedazionale)=([^&]+)")


def update_link(page: str) -> Optional[str]:
    """The path of the article's update table (``/do/atto/vediAggiornamentiAllArticolo?...``).

    None when the page has none: Normattiva gives no link to an article never amended.
    """
    found = _LINK.search(page)
    if found is None:
        return None
    path = _html.unescape(found.group())
    return path if path.startswith("/") else "/" + path


def link_version(link: str) -> Optional[int]:
    """The ``art.versione`` of an update link: the version whose table it opens."""
    found = _VERSIONE.search(link)
    return int(found.group(1)) if found else None


def with_version(link: str, versione: int) -> str:
    """The same update link, for version *versione*."""
    return _VERSIONE.sub(f"art.versione={versione}", link, count=1)


def version_pages(page: str, link: str) -> dict[int, str]:
    """``{k: "/atto/caricaArticolo?..."}`` of the article the update *link* names.

    Read from the act's tree on the article page: the article's own entries carry the same
    ``idArticolo``, ``idSottoArticolo`` and ``flagTipoArticolo`` as its update link.
    """
    want = dict(_PARAM.findall(link))
    out: dict[int, str] = {}
    for raw in re.findall(r"/?atto/caricaArticolo\?[^'\"<>\s]+", page):
        path = _html.unescape(raw)
        params = dict(_PARAM.findall(path))
        if any(params.get(k) != v for k, v in want.items() if k != "codiceRedazionale") \
                or params.get("codiceRedazionale") != want.get("codiceRedazionale"):
            continue
        versione = link_version(path)
        if versione is not None:
            out.setdefault(versione, path if path.startswith("/") else "/" + path)
    return out


# --- rows ---------------------------------------------------------------------------

_ATTO = re.compile(
    r"^(?:Il|La|Lo|L')\s*(?P<tipo>[A-Z][A-Z'\- ]*?[A-Z])\s+(?P<g>\d{1,2})[º°]?\s+(?P<m>[a-z]+)\s+"
    r"(?P<a>\d{4}),\s+n\.\s*(?P<n>\d+)\s*\((?P<gu>[^()]*)\)")
_GU = re.compile(r"G\.U\.\s*(\d{1,2})/(\d{1,2})/(\d{4})")
# «ha disposto», and «ha conseguentemente disposto» for an act that amends the article by
# amending the act that amended it (d.l. 135/2009 on art. 13 d.lgs. 196/2003).
_DISPOSTO = re.compile(r"\bha\s+(?:[a-z]+mente\s+)?disposto\b\s*")
_PEZZO = re.compile(r"^\(con (?P<disp>.+?)\)\s+(?P<azione>(?:la|il|lo|le|gli|l')\s*\S.*)$", re.S)
_VERBI = (
    ("la modifica", "modifica"),
    ("l'introduzione", "inserimento"),
    ("l'inserimento", "inserimento"),
    ("l'abrogazione", "abrogazione"),
    ("la sostituzione", "sostituzione"),
    ("la conversione", "conversione"),
)
_AZIONI = re.compile(r"\s+e\s+(?=(?:la|l')\s*(?:modifica|introduzione|inserimento|abrogazione|sostituzione|"
                     r"conversione)\b)")
_PARTI_DOPO_ART = re.compile(r"dell'art\.\s*[\w.\-]+,\s*(?P<parti>.+)$")
_PARTI_PRIMA_ART = re.compile(r"^l'\w+\s+(?:del|dei|della|delle|dello|degli)\s+(?P<parti>.+?)\s+all'art\.")


def _iso(giorno: str, mese: str, anno: str) -> Optional[str]:
    try:
        numero = int(mese) if mese.isdigit() else _MESI[mese.lower()]
        return date(int(anno), numero, int(giorno)).isoformat()
    except (KeyError, ValueError):
        return None


def _testo(node) -> str:
    return " ".join(node.get_text(" ", strip=True).split())


def parse_atto(testo: str) -> dict:
    """The amending act of a row: ``tipo_atto``, ``data``, ``numero_atto``, ``gazzetta``,
    ``data_gu``; the fields it cannot read are ``""``/None. ``descrizione`` is *testo*."""
    out = {"tipo_atto": "", "data": None, "numero_atto": "", "gazzetta": None, "data_gu": None,
           "descrizione": testo}
    found = _ATTO.match(testo)
    if found is None:
        return out
    out["tipo_atto"] = normalize_act_type(found.group("tipo").lower()).lower()
    out["data"] = _iso(found.group("g"), found.group("m"), found.group("a"))
    out["numero_atto"] = found.group("n")
    gazzetta = re.sub(r"^in\s+", "", found.group("gu").strip())
    out["gazzetta"] = gazzetta or None
    gu = _GU.search(gazzetta)
    out["data_gu"] = _iso(*gu.groups()) if gu else None
    return out


def _tipo(azione: str) -> str:
    for prefisso, tipo in _VERBI:
        if azione.lower().startswith(prefisso):
            return tipo
    return "altro"


def _parti(azione: str) -> Optional[str]:
    for pattern in (_PARTI_DOPO_ART, _PARTI_PRIMA_ART):
        found = pattern.search(azione)
        if found:
            return found.group("parti").strip() or None
    return None


def parse_disposizioni(testo: str) -> list[dict]:
    """The provisions of a row's second item: ``[{disposizione, tipo, parti, testo}]``.

    *testo* is «[convertito con modificazioni dalla …] ha disposto (con l'art. 9, comma 1,
    lettera a)) la modifica dell'art. 2-ter, commi 1, 1-bis, 2 e 3; (con l'art. 9, comma 5)
    la modifica dell'art. 2-ter, comma 1.»: one entry per «(con …) …» piece. ``testo`` of
    an entry is the piece as Normattiva writes it, with «ha disposto».
    """
    found = _DISPOSTO.search(testo)
    if found is None:
        return [{"disposizione": None, "tipo": "altro", "parti": None, "testo": testo.strip()}]
    corpo = testo[found.end():].strip().rstrip(".").strip()
    pezzi = re.split(r";\s*(?=\(con\s)", corpo)
    out = []
    for pezzo in pezzi:
        pezzo = pezzo.strip()
        match = _PEZZO.match(pezzo)
        azione = match.group("azione").strip() if match else pezzo
        disposizione = re.sub(r"^(?:l'|gli\s+|i\s+)", "", match.group("disp").strip()) if match else None
        # «l'introduzione del comma 1-bis all'art. 2-ter e la modifica dell'art. 2-ter, commi 2
        # e 3»: one provision, two actions. Each is an entry, all with the piece's whole text.
        for parte in _AZIONI.split(azione):
            out.append({"disposizione": disposizione, "tipo": _tipo(parte), "parti": _parti(parte),
                        "testo": f"{found.group().strip()} {pezzo}"})
    return out


def conversione(testo: str) -> Optional[str]:
    """«convertito con modificazioni dalla L. … (…)» before «ha disposto», when there."""
    found = _DISPOSTO.search(testo)
    prima = testo[:found.start()].strip() if found else ""
    return prima or None


def parse_righe(page: str) -> Optional[list[dict]]:
    """The rows of an update table: ``[{progressivo, data_gu, atti: [{atto, disposizioni}]}]``.

    None when the page has no update table (an error or session page, another page).
    A row carries one or more amending acts: each an item without a link («Il DECRETO-LEGGE
    … (in G.U. …)»), followed by the item of its provisions. Every item without a link opens
    an act, read or not (an act whose fields cannot be read keeps them empty: INDICATIVO).
    A row without a number continues the one before (the decree-law «convertito con
    modificazioni …» under its own entry): it is that row's act once more, with its note.
    """
    soup = BeautifulSoup(page, "lxml")
    tabella = soup.select_one("table.tabella_elencoAgg")
    if tabella is None:
        return None
    righe: list[dict] = []
    for tr in tabella.select("tbody tr"):
        celle = tr.find_all("td")
        if len(celle) < 3:
            continue
        progressivo = _testo(celle[0])
        data = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", _testo(celle[1]))
        voci = celle[2].find_all("li")
        prosegue = bool(not progressivo and righe and righe[-1]["atti"] and voci and voci[0].find("a") is not None)
        riga = righe[-1] if prosegue else {
            "progressivo": int(progressivo) if progressivo.isdigit() else None,
            "data_gu": _iso(*data.groups()) if data else None,
            "atti": [],
        }
        corrente = None
        for li in voci:
            testo = _testo(li)
            if li.find("a") is None:
                corrente = {"atto": parse_atto(testo), "disposizioni": []}
                riga["atti"].append(corrente)
                continue
            nota = conversione(testo)
            if corrente is None:
                if prosegue:
                    # The previous row's act again, as this entry describes it.
                    prima = riga["atti"][-1]["atto"]
                    atto = dict(prima, descrizione=prima["descrizione"].split(" convertito con ")[0])
                else:
                    atto = parse_atto("")
                corrente = {"atto": atto, "disposizioni": []}
                riga["atti"].append(corrente)
            if nota:
                corrente["atto"]["descrizione"] = (corrente["atto"]["descrizione"] + " " + nota).strip()
            corrente["disposizioni"].extend(parse_disposizioni(testo))
        if not prosegue:
            righe.append(riga)
    return righe


_INTRODUZIONE_ARTICOLO = re.compile(r"^l'introduzione dell'art\.\s*([\w.\-]+?)\.?$")


def inserimento_articolo(righe: list[dict], stesso_articolo) -> list[dict]:
    """The rows of version 1's table that introduced the article itself.

    Version 1's table is the article's whole history (measured on 29 Oct: art. 2-ter and
    13 d.lgs. 196/2003, art. 64-bis CCII, art. 2 c.c., art. 1 d.P.R. 131/1986), not the
    amendments that produced version 1: only «l'introduzione dell'art. N» of this very
    article (*stesso_articolo(N)* true) is version 1's. The other rows are the later
    versions', and are read from their own tables.
    """
    out = []
    for riga in righe:
        atti = []
        for voce in riga["atti"]:
            tenute = []
            for d in voce["disposizioni"]:
                azione = re.sub(r"^\S+(?:\s+\S+)?\s+disposto\s+(?:\(con .+?\)\s+)?", "", d["testo"])
                found = _INTRODUZIONE_ARTICOLO.match(azione.strip())
                if d["tipo"] == "inserimento" and d["parti"] is None and found and stesso_articolo(found.group(1)):
                    tenute.append(d)
            if tenute:
                atti.append({"atto": voce["atto"], "disposizioni": tenute})
        if atti:
            out.append({**riga, "atti": atti})
    return out


# --- cache of past versions ---------------------------------------------------------
#
# A version whose window has ended (valid_to set and before today) does not change:
# its window and its table are kept on disk for TTL_SECONDI, through ``_cache.py``
# (``${MCP_CACHE_DIR:-~/.cache/mcp-legal-it}/normattiva_aggiornamenti/<sha256>.json``,
# nothing under LEGAL_CACHE=off). Never for ever: Normattiva corrects its data at times.
# The article page (the current version, how many versions there are) is read every time.

TTL_SECONDI = 90 * 86400
#: Raised when the record's shape changes, so records written before are not read.
SCHEMA = 1


def _dir_cache():
    from .._cache import cache_root

    return cache_root() / "normattiva_aggiornamenti"


def _file_cache(urn: str, versione: int):
    import hashlib

    return _dir_cache() / f"{hashlib.sha256(f'{urn}|{versione}'.encode('utf-8')).hexdigest()}.json"


def leggi_versione(urn: str, versione: int) -> Optional[dict]:
    """``{"finestra": [from, to], "righe": [...]}`` kept for this version, or None."""
    import json
    import time

    from .._cache import cache_enabled

    if not cache_enabled():
        return None
    path = _file_cache(urn, versione)
    try:
        rec = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    salvato = rec.get("salvato") if isinstance(rec, dict) else None
    if (not isinstance(salvato, (int, float)) or isinstance(salvato, bool) or rec.get("schema") != SCHEMA
            or not isinstance(rec.get("finestra"), list) or not isinstance(rec.get("righe"), list)):
        return None
    if time.time() - salvato >= TTL_SECONDI:
        try:
            path.unlink()
        except OSError:
            pass
        return None
    return rec


def scrivi_versione(urn: str, versione: int, finestra: tuple, righe: list) -> None:
    """Keep a past version's window and table (best effort: an unwritable directory only warns)."""
    import json
    import os
    import sys
    import threading
    import time

    from .._cache import cache_enabled

    if not cache_enabled():
        return
    path = _file_cache(urn, versione)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f"{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
        tmp.write_text(json.dumps({"schema": SCHEMA, "salvato": time.time(), "finestra": list(finestra),
                                   "righe": righe}, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, path)
    except OSError as exc:
        print(f"mcp-legal-it: cache degli aggiornamenti non scrivibile ({exc})", file=sys.stderr)


# --- the walk -------------------------------------------------------------------------

_BASE = "https://www.normattiva.it"


class _Interrotta(Exception):
    """A version could not be read: the walk stops there, with what it had."""


def _motivo(exc: BaseException) -> str:
    if isinstance(exc, httpx.HTTPStatusError) and exc.response is not None:
        return f"HTTP {exc.response.status_code}"
    return str(exc) if isinstance(exc, _Interrotta) else type(exc).__name__


def _transitorio(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        stato = exc.response.status_code if exc.response is not None else 0
        return stato in (403, 429) or stato >= 500
    return isinstance(exc, (httpx.TransportError, _Interrotta, TimeoutError))


async def leggi_aggiornamenti(url: str, articolo: str, *, dal: Optional[str], al: Optional[str],
                              max_versioni: int, oggi: str) -> dict:
    """Read an article's versions and amendments from Normattiva, with one client (one session).

    *url* is the article's N2Ls URL, *articolo* the article asked for: every page read must
    name it. The versions are walked newest first, each window before its table, at most
    *max_versioni* of them. A table is read only when the version starts within [*dal*,
    *al*] (inclusive; a version whose window is unreadable is read too), and the walk stops
    at the first version that starts before *dal*: the older ones start earlier still.
    Returns a dict:

    - ``esito``: ``"trovato"``, ``"articolo_non_trovato"`` (the page names another article),
      ``"verifica_non_disponibile"`` (the article page could not be read or identified: an
      error or session page, a source down or blocking), ``"errore_fonte"``;
    - ``versioni``: ``{k: (valid_from, valid_to) | None}`` for every version Normattiva
      lists (None: not read); ``corrente``: the version the undated page served;
    - ``righe``: ``{k: [rows]}`` for the versions whose table was read;
    - ``mancanti``: versions a failure left unread (the walk stopped at the first);
    - ``oltre_tetto``: versions the ceiling left unread; ``errore``;
    - ``vuote``: versions after the first whose table lists nothing (never kept);
    - ``storia_certa``: False when a page without the article's update link also lacks the
      act's update link or a window (markup that changed: «never amended» is not said).

    Version 1's table is the whole history: of it, only the article's own introduction is
    kept (:func:`inserimento_articolo`). Every version page must name the article and be
    that version (its own update link says so), or the walk stops.
    """
    from mcp_legal_it.core._http import async_client

    from . import scraper
    from .normattiva_validity import _read_window

    voluto = scraper._article_identity(scraper.normalize_article_key(articolo))
    urn = url.split("?", 1)[1] if "?" in url else url
    out = {"esito": "trovato", "versioni": {}, "righe": {}, "mancanti": [], "oltre_tetto": [], "vuote": [],
           "storia_certa": True, "errore": None, "corrente": None}

    def _servito(html: str) -> "str | None":
        # A version's page opens with «<?xml»: VisuaLex's HTML parser reads it, and says so.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", XMLParsedAsHTMLWarning)
            return scraper._normattiva_article_page(html)[1]

    async with async_client("normattiva", headers=scraper._HEADERS, timeout=scraper._TIMEOUT,
                            follow_redirects=True) as client:

        async def get(path: str) -> str:
            resp = await client.get(path if path.startswith("http") else _BASE + path)
            resp.raise_for_status()
            scraper.note_source("normattiva", str(resp.url) if hasattr(resp, "url") else "")
            if resp.status_code != 200:
                raise _Interrotta(f"HTTP {resp.status_code}")
            return resp.text

        # 1. The article page: the session, the current version, the list of versions.
        try:
            pagina = await get(url)
        except Exception as exc:  # noqa: BLE001 - every failure of the source is an outcome
            out["esito"] = "verifica_non_disponibile" if _transitorio(exc) else "errore_fonte"
            out["errore"] = f"Normattiva non raggiungibile ({_motivo(exc)})"
            return out
        servito = _servito(pagina)
        got = scraper._article_identity(servito) if servito else None
        if voluto is None or got is None or got != voluto:
            # A page that does not name the article (an error or session page names none) is
            # never taken for it: only another article's number says that this one is missing.
            if got is not None and voluto is not None and got[0] != voluto[0]:
                out["esito"] = "articolo_non_trovato"
                out["errore"] = (f"per l'art. {articolo} Normattiva restituisce l'art. {servito}: l'articolo non "
                                 "esiste nell'atto (controlla il numero)")
            else:
                problema = scraper.normattiva_page_problem(pagina, scraper.act_page_metadata(pagina))
                out["esito"] = "verifica_non_disponibile"
                out["errore"] = ("Normattiva non ha servito la pagina dell'articolo"
                                 + (f" ({problema})" if problema else ": la pagina non dice quale articolo è"))
            return out

        def stesso_articolo(numero: str) -> bool:
            return scraper._article_identity(scraper.normalize_article_key(numero)) == voluto

        link = update_link(pagina)
        if link is None:
            # Never amended: one version, the page's own window. Said only when the page has
            # the act's own update link and a window: a page without either is markup that
            # changed, and «never amended» would then be said of every article.
            finestra = _read_window(pagina)
            out["versioni"] = {1: finestra}
            out["corrente"] = 1
            out["storia_certa"] = bool(finestra) and "vediAggiornamentiAllAtto" in pagina
            return out
        corrente = link_version(link) or 1
        out["corrente"] = corrente
        pagine = version_pages(pagina, link)
        tutte = sorted(set(pagine) | set(range(1, corrente + 1)), reverse=True)
        out["versioni"] = {k: None for k in tutte}

        # 2. Each version, newest first: its window (its page; the current one is this page),
        #    then its table. Version 1's table is the whole history: of it, only the article's
        #    own introduction is version 1's.
        for posizione, k in enumerate(tutte):
            if posizione >= max_versioni:
                out["oltre_tetto"] = tutte[posizione:]
                break
            try:
                tenuta = leggi_versione(urn, k) if k != corrente else None
                if tenuta is not None:
                    finestra = tuple(tenuta["finestra"])
                elif k == corrente:
                    finestra = _read_window(pagina)
                else:
                    path = pagine.get(k)
                    if path is None:
                        raise _Interrotta(f"nessun collegamento alla versione {k}")
                    html = await get(path)
                    servita = scraper._article_identity(_servito(html) or "")
                    if servita is None or servita != voluto:
                        raise _Interrotta(f"la pagina della versione {k} non è quella dell'articolo")
                    if link_version(update_link(html) or "") != k:
                        raise _Interrotta(f"la pagina della versione {k} è quella di un'altra versione")
                    finestra = _read_window(html)
                out["versioni"][k] = finestra
                inizio = finestra[0] if finestra else None
                prima_di_dal = bool(dal and inizio and inizio < dal)
                dopo_al = bool(al and inizio and inizio > al)
                if not prima_di_dal and not dopo_al:
                    if tenuta is not None:
                        out["righe"][k] = tenuta["righe"]
                    else:
                        righe = parse_righe(await get(with_version(link, k)))
                        if righe is None:
                            raise _Interrotta(f"la tabella degli aggiornamenti della versione {k} non si legge "
                                              "(pagina di errore o di sessione)")
                        if k == 1:
                            righe = inserimento_articolo(righe, stesso_articolo)
                        elif not any(v["disposizioni"] for r in righe for v in r["atti"]):
                            out["vuote"].append(k)
                        out["righe"][k] = righe
                        if (k != corrente and finestra and finestra[1] and finestra[1] < oggi
                                and k not in out["vuote"]):
                            scrivi_versione(urn, k, finestra, righe)
                if prima_di_dal:
                    break  # the older versions start earlier still: outside the window
            except Exception as exc:  # noqa: BLE001 - a failure stops the walk, never fills a gap
                out["mancanti"] = tutte[posizione:]
                out["errore"] = f"lettura interrotta alla versione {k} ({_motivo(exc)})"
                break
    return out

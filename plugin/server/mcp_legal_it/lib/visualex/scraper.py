"""Unified scraper for Normattiva, EUR-Lex, and Brocardi using httpx."""

import asyncio
import copy
import dataclasses
import difflib
import os
import re
import unicodedata
import warnings
from urllib.parse import urljoin

import httpx
from mcp_legal_it.core._http import async_client
from bs4 import BeautifulSoup, NavigableString, Tag, XMLParsedAsHTMLWarning

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

from .. import _brocardi_switch
from .._http import note_source
from . import normattiva_html, pagine_normattiva
from .akn_parser import annex_id_of, normalize_article_key, position_hint
from .models import Norma, NormaVisitata, names_an_annex, split_annex, url_in_part
from .map import codice_urn, find_brocardi_url


def _akn_disabled() -> bool:
    """Whether the AKN-first path is disabled (read at call time).

    Set ``AKN_DISABLED=1`` to skip AKN entirely and use the HTML path — used by
    the benchmark to measure the HTML baseline and by tests that exercise the
    HTML fallback deterministically.
    """
    return os.environ.get("AKN_DISABLED", "").strip().lower() in {"1", "true", "yes"}


def _akn_part_hint(norma) -> "str | None":
    """Which component part of a multi-part AKN act to select (None = dominant).

    A part asked for by its Normattiva position (``Norma.allegato``, VisuaLex's
    ``allegato``) is that part. Otherwise the preleggi need a non-dominant part:
    the codice civile AKN export bundles them as a separate "Disposizioni sulla
    legge in generale" part that the parser would otherwise discard in favour of
    the ~3249-article code body. So does the codice penale militare di guerra, the
    smaller of the two codes of R.D. 303/1941.
    """
    if getattr(norma, "allegato", ""):
        return position_hint(norma.allegato)
    tipo = norma.tipo_atto_normalized.strip().lower()
    if tipo == "preleggi":
        return "preleggi"
    # R.D. 303/1941 bundles both military codes; the parts carry the codes' names.
    if tipo in ("codice penale militare di pace", "codice penale militare di guerra"):
        return tipo
    return None


# In-memory cache for Brocardi article URLs (base_url + article_num → article_url)
_brocardi_url_cache: dict[str, str] = {}

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


# ---------------------------------------------------------------------------
# Act identity from the Normattiva landing page (ELI metadata)
# ---------------------------------------------------------------------------

# An act cited with the year only ("L. 742/1969") is queried as YYYY-01-01, a
# date Normattiva tolerates but that is not the act's own. The landing page
# carries the real one (eli:date_document) and the title (eli:title).
_full_date_cache: dict[str, dict] = {}
_date_in_corso: "dict[tuple[str, int], asyncio.Future]" = {}


def act_page_metadata(html: str) -> dict:
    """Identity of an act read from its Normattiva page: date, title, page title.

    Returns a dict with ``date`` (``YYYY-MM-DD`` from ``eli:date_document``),
    ``title`` (``eli:title``, without the final full stop) and ``heading`` (the
    ``<title>`` of the page without the `` - Normattiva`` suffix, e.g.
    ``LEGGE 7 ottobre 1969, n. 742``); each is ``""`` when absent.
    """
    soup = BeautifulSoup(html, "lxml")
    meta_date = soup.find("meta", attrs={"property": "eli:date_document"})
    meta_title = soup.find("meta", attrs={"property": "eli:title"})
    date = (meta_date.get("content") or "").strip() if meta_date else ""
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
        date = ""
    title = (meta_title.get("content") or "").strip().rstrip(".").strip() if meta_title else ""
    page_title = soup.find("title")
    heading = page_title.get_text(strip=True) if page_title else ""
    heading = re.sub(r"\s*-\s*Normattiva\s*$", "", heading).strip()
    return {"date": date, "title": title, "heading": heading}


def act_display_title(meta: dict) -> str:
    """``LEGGE 7 ottobre 1969, n. 742 - Sospensione dei termini ...`` from :func:`act_page_metadata`."""
    heading, title = meta.get("heading", ""), meta.get("title", "")
    if heading and title:
        return f"{heading} - {title}"
    return heading or title


def _year_only_act(norma: Norma) -> bool:
    """A Normattiva act (not a codice, not EU) cited with a bare year and a number."""
    if norma._is_eurlex() or codice_urn(norma.tipo_atto_normalized.lower()):
        return False
    return bool(re.fullmatch(r"\d{4}", norma.data or "")) and bool(norma.numero_atto)


async def _act_metadata(norma: Norma) -> dict:
    """Metadata of the act's landing page, cached in memory for the process."""
    url = norma.url()
    if not url:
        return {}
    if url in _full_date_cache:
        return _full_date_cache[url]
    # Several articles of one act asked at once (a list, testi_articoli) need the same
    # page: the first request is shared, the others wait for it and declare the source
    # in their own provenance. Keyed by event loop, as the AKN export's single-flight.
    chiave = (url, id(asyncio.get_running_loop()))
    in_corso = _date_in_corso.get(chiave)
    if in_corso is not None:
        meta = await asyncio.shield(in_corso)
        note_source("normattiva", url)
        return meta
    futuro = asyncio.get_running_loop().create_future()
    _date_in_corso[chiave] = futuro
    try:
        async with async_client("normattiva", headers=_HEADERS, timeout=_TIMEOUT, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            note_source("normattiva", str(resp.url) if hasattr(resp, "url") else "")
            meta = act_page_metadata(resp.text)
    except BaseException as exc:
        if not futuro.done():
            # A cancelled leader must not cancel its waiters (other callers): they get a
            # failed lookup instead, which with_full_date reads as "date not resolved".
            condiviso = exc if isinstance(exc, Exception) else RuntimeError("ricerca della data annullata")
            futuro.set_exception(condiviso)
            futuro.exception()  # retrieved: a waiter-less failure must not warn
        raise
    finally:
        _date_in_corso.pop(chiave, None)
    _full_date_cache[url] = meta
    futuro.set_result(meta)
    return meta


async def with_full_date(norma: Norma) -> Norma:
    """The same act with its real date when it was cited with the year only.

    Any other act is returned unchanged; so is a year-only act whose page cannot
    be read or whose date disagrees with the cited year (never guess: the caller
    then keeps what the user cited and the URN is not presented as official).
    """
    if not _year_only_act(norma):
        return norma
    try:
        meta = await _act_metadata(norma)
    except Exception:  # noqa: BLE001 - identity lookup is best effort
        return norma
    date = meta.get("date", "")
    if date and date.startswith(f"{norma.data}-"):
        return dataclasses.replace(norma, data=date)
    return norma


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def fetch_article(nv: NormaVisitata, *, canale: str = "html") -> dict:
    """Fetch article text from Normattiva or EUR-Lex.

    *canale* picks how a Normattiva article is read:

    - ``"html"`` (the default): the article page, read by VisuaLex's extractor
      (``normattiva_html``), whose ``article_text`` is frozen byte for byte. The
      Akoma Ntoso export is the last resort, when the page cannot be read, and the
      answer says so (``source`` ``normattiva-akn``), as in VisuaLex;
    - ``"akn"``: the Akoma Ntoso export first, the page as fallback. Faster warm,
      but the export transliterates accents ("attivita'") and drops Normattiva's
      «(( … ))» amendment markers: never VisuaLex's display text.

    Returns: {"text": str, "url": str, "source": "normattiva"|"normattiva-akn"|"eurlex"}
    """
    if canale not in ("html", "akn"):
        raise ValueError(f"canale sconosciuto: {canale!r}")
    is_eurlex = nv.norma._is_eurlex()
    source = "eurlex" if is_eurlex else "normattiva"
    annex = split_annex(nv.numero_articolo)

    if is_eurlex:
        html, url = await _fetch_eurlex_html(nv.norma)
        if not html:
            return {"text": "", "url": url, "source": source, "error": "Could not fetch EUR-Lex document"}
        text = _extract_eurlex_article(html, nv.numero_articolo)
        if annex:
            if text.startswith("["):  # not found / not divided into articles
                return {"text": "", "url": url, "source": source, "error": text.strip("[]")}
            return {"text": text, "url": url, "source": source, "allegato": f"Allegato {annex[0]}"}
        if nv.numero_articolo and _EURLEX_NOT_FOUND_RE.match(text):
            # The extractor's "[Articolo N non trovato ...]" is an answer about the
            # document, not its text: returned as text it read as the article.
            return {"text": "", "url": url, "source": source, "esito": ARTICLE_NOT_FOUND,
                    "error": text.strip("[]")}
    elif annex:
        return await _fetch_normattiva_annex(nv, *annex, canale=canale)
    elif names_an_annex(nv.numero_articolo):
        # An annex the syntax cannot read: going on would look up a body article
        # under a malformed URN, the silent mix-up of issue #47.
        return {"text": "", "url": nv.norma.url(), "source": source,
                "error": (f"riferimento ad allegato non interpretabile: '{nv.numero_articolo}'. "
                          "Formato atteso: 'allegato <id> art. <numero>' o 'allegato <id>'")}
    else:
        # A bare-year citation is resolved to the act's real date first, so the
        # URL (and the URN derived from it) is the act's own, not YYYY-01-01.
        full = await with_full_date(nv.norma)
        if full is not nv.norma:
            nv = NormaVisitata(norma=full, numero_articolo=nv.numero_articolo)
        url = nv.url()
        if not url:
            return {"text": "", "url": "", "source": "", "error": "Could not generate URL for this act"}

        part = _akn_part_hint(nv.norma)
        if canale == "html":
            return await _html_article(nv, url, part)

        # AKN channel: the official Akoma Ntoso XML export first, then the page.
        act = None
        if not _akn_disabled():
            from .akn_fetch import fetch_act_akn

            act = await fetch_act_akn(nv.norma)
            if act is not None:
                akn_text = _akn_article(act, nv.numero_articolo, part)
                if akn_text:
                    result = {"text": akn_text, "url": url, "source": "normattiva-akn", "data_atto": nv.norma.data}
                    if not part:
                        served_url = url_in_part(url, act.part_position())
                        # The act's main text is a code approved in an annex, cited by the
                        # decree's number: say so, and point at the code's own article.
                        if served_url != url:
                            result["url"] = served_url
                            result["allegato"] = act.main_part
                        elif annex_id_of(act.main_part):
                            result["allegato"] = act.main_part
                    return result

        text, served = await _normattiva_page(url)
        result = {"text": text, "url": url, "source": source, "data_atto": nv.norma.data}
        if not nv.numero_articolo:
            return result
        return _checked_html_article(result, nv, served, act, part)

    return {"text": text, "url": url, "source": source}


# ---------------------------------------------------------------------------
# Does the article exist? (Normattiva answers a missing one with the act's art. 1)
# ---------------------------------------------------------------------------

# Machine-readable outcome of a failed existence check, carried in ``esito``
# next to ``error``: the article is not in the act, or the act's structure could
# not be read to tell. Callers (verifica_citazioni) branch on it, never on the wording.
ARTICLE_NOT_FOUND = "articolo_non_trovato"
CHECK_UNAVAILABLE = "verifica_non_disponibile"

# What _extract_eurlex_article answers when the document has no such article or recital.
_EURLEX_NOT_FOUND_RE = re.compile(r"^\[(?:Articolo|Considerando) .+ non trovato nel documento EUR-Lex\]$")

# The Latin ordinals after an article number are spelled more than one way, even
# inside Normattiva: the D.Lgs. 196/2003 asked as "2-quinquiesdecies" is served
# as "Art. 2-quindecies", "2-sexiesdecies" as "Art. 2-sex-decies".
_ORDINAL_SPELLINGS = (
    ("quindecies", "quinquiesdecies"),
    ("sexdecies", "sexiesdecies"),
    ("septendecies", "septiesdecies"),
    ("octodecies", "octiesdecies"),
    ("novendecies", "noviesdecies"),
    # VisuaLex's table lists these too, as Normattiva prints them (18, 19, 20).
    ("duodevicies", "octiesdecies"),
    ("undevicies", "noviesdecies"),
    ("vices", "vicies"),
    ("nonies", "novies"),
)


def _article_identity(key: str) -> "tuple[str, str] | None":
    """``(number, suffix)`` of an article key in canonical form, None if it has no number.

    ``"2-sex-decies"`` and ``"2-sexiesdecies"`` are ``("2", "sexiesdecies")``,
    ``"416-bis.1"`` is ``("416", "bis1")``, ``"01"`` is ``("1", "")``. An act made
    of one article numbers it "unico" in some sources and 1 in others: both are
    ``("1", "")``.
    """
    key = (key or "").strip().lower()
    if key == "unico":
        return "1", ""
    m = re.match(r"(\d+)(.*)$", key)
    if not m:
        return None
    suffix = re.sub(r"[^a-z0-9]", "", m.group(2))
    for variant, canonical in _ORDINAL_SPELLINGS:
        suffix = suffix.replace(variant, canonical)
    return str(int(m.group(1))), suffix


def _akn_article(act, numero_articolo: str, part: "str | None") -> "str | None":
    """The article from the parsed export, matched on its canonical identity."""
    text = act.article(numero_articolo, part=part)
    if text:
        return text
    wanted = _article_identity(normalize_article_key(numero_articolo))
    if wanted is None:
        return None
    # The key as the export wrote it, read as is: normalising it again may spell it
    # otherwise ("2-sex-decies" of an act parsed before) and miss it.
    matched = act._resolve_part(part) if part else None
    articles = matched.articles if matched is not None else ({} if part else act.articles)
    for key in act.article_keys(part):
        if _article_identity(key) == wanted:
            return articles.get(key)
    return None


# The number at the head of a code article, which Normattiva serves as an
# attachment with no numbered heading element: "Art. 2043.", "Art. 609-undecies.",
# "Art. 416-bis.1", "Art. 2-sex-decies", "Articolo unico". The suffix words are the
# Latin ordinals (bis, ter, quater, sex, ...ies), so "Art. 5. La legge" stops at 5.
# "Art" is matched as written: an upper-case editorial note at the head of the
# text ("((ARTICOLO ABROGATO DALL'ART. 106 ...))") must not read as art. 106.
_ATTACHMENT_ARTICLE_RE = re.compile(
    # "-art." is the label of an article whose page lost its heading ("Codice Penale-art. 524").
    r"(?:\b(?:Art(?:icolo)?\.?|ARTICOLO)|(?<=-)art\.)\s*"
    r"((?i:\d+(?:[\s-]*(?:bis|ter|quater|sex|[a-z]*ies)\b)*(?:\.\d+)?|unico))\b"
)
# The all-caps "ART. 3" head (codice del turismo). Only at the very start: inside an
# editorial note ("((ARTICOLO ABROGATO DALL'ART. 106 ...))") it names another article.
_ATTACHMENT_CAPS_HEAD_RE = re.compile(
    r"^\s*ART\.?\s*((?i:\d+(?:[\s-]*(?:bis|ter|quater|sex|[a-z]*ies)\b)*(?:\.\d+)?|unico))\b"
)


def _served_article_key(corpo: Tag) -> "str | None":
    """The number Normattiva gives the article it served, or None if the page does not say.

    An article of the act's body has a numbered heading (``<h2 class="article-num-akn"
    id="art_N">``); an article of a code, served as an attachment, opens with its own
    "Art. N." line. A page with neither is not identified.
    """
    heading = corpo.find("h2", class_="article-num-akn")
    if heading is not None:
        key = normalize_article_key(heading.get("id") or "") or normalize_article_key(
            heading.get_text(" ", strip=True)
        )
        return key or None
    attachment = corpo.find(class_="attachment-just-text")
    if attachment is not None:
        head = attachment.get_text(" ", strip=True)[:400]
        m = _ATTACHMENT_CAPS_HEAD_RE.match(head) or _ATTACHMENT_ARTICLE_RE.search(head)
        if m:
            return normalize_article_key(m.group(1)) or None
    return None


#: The ":k" after the act number of a Normattiva URL: the part the URL asks for.
_URL_PARTE = re.compile(r";[^;:~!@?]+:(\d+)(?=~|!|@|$)")


def _altrove(act, nv: NormaVisitata, result: dict) -> str:
    """Where else in the act the article is (VisuaLex's hint), read from the export already fetched.

    The parts as Normattiva numbers them: the act's own text (``""``), each part by its
    position. ``""`` without an export, or when the article is nowhere else.
    """
    if act is None:
        return ""
    if not nv.norma.allegato and re.search(r";[^;:~]+:\d+$", codice_urn(nv.norma.tipo_atto_normalized.lower()) or ""):
        # A code's own part: another part of the act is another code (art. 40 of the
        # preleggi is not art. 40 of the codice civile), so the refusal points nowhere.
        return ""
    from .albero_normattiva import dove_altrove

    body = act.parts.get("Dispositivo") if act.main_part else None
    entries = [{"numero": k, "allegato": None} for k in (body.order if body else act.order if not act.main_part else [])]
    abrogati = {"": set(act.abrogati("Dispositivo") if body else act.abrogati() if not act.main_part else [])}
    for name, p in act.parts.items():
        if name != "Dispositivo" and act.part_position(name):
            entries += [{"numero": k, "allegato": str(p.position)} for k in p.order]
            abrogati[str(p.position)] = set(act.abrogati(name))
    m = _URL_PARTE.search(result.get("url") or nv.url())
    asked = m.group(1) if m else ""
    hint = dove_altrove(entries, nv.numero_articolo, asked)
    if not hint:
        return ""
    # Where it is, but repealed there: said, so that a repealed article is not taken for
    # the text the reader was looking for (read from the export: no request).
    wanted = normalize_article_key(nv.numero_articolo)
    trovato = {str(e["allegato"] or "") for e in entries
               if normalize_article_key(e["numero"]) == wanted and str(e["allegato"] or "") != asked}
    abrogato = sorted(part for part in trovato if any(normalize_article_key(k) == wanted for k in abrogati.get(part, ())))
    if abrogato and len(abrogato) == len(trovato):
        return hint + " (abrogato)"
    if abrogato:
        luoghi = ["nel testo dell'atto" if part == "" else f"nell'allegato {part}" for part in abrogato]
        return hint + f" (abrogato {' e '.join(luoghi)})"
    return hint


def _unavailable(base: dict, nv: NormaVisitata, why: str) -> dict:
    return {**base, "esito": CHECK_UNAVAILABLE,
            "error": (f"verifica non disponibile per l'art. {nv.numero_articolo} di {nv.norma}: "
                      f"{why}, quindi il testo non viene presentato come quello dell'articolo "
                      "richiesto")}


def _checked_html_article(result: dict, nv: NormaVisitata, served: "str | None", act, part) -> dict:
    """Serve the HTML text only if it is the article asked for.

    Normattiva answers a URN naming an article the act does not have with HTTP 200
    and the act's first article: taking that text at face value turned a typo in
    the article number into a confident citation of another article.

    - the page names the article asked for (same number, same suffix in canonical
      spelling): it exists, the text is served;
    - the page names another number (99999 -> 1): the article does not exist;
    - the page names the same number with another suffix, or names nothing: the
      article is declared missing only if the act's structure (the AKN export,
      already read) has no article with that number at all. Otherwise nothing
      proves which article the text is, and the answer says "verifica non
      disponibile" rather than "non esiste": a suffix spelled in a way this code
      does not know must never turn a real article into a missing one.
    """
    requested = _article_identity(normalize_article_key(nv.numero_articolo))
    got = _article_identity(served) if served is not None else None
    if requested is not None and got == requested:
        return result
    base = {**result, "text": ""}
    if requested is not None and got is not None and got[0] != requested[0]:
        return {**base, "esito": ARTICLE_NOT_FOUND,
                "error": (f"articolo {nv.numero_articolo} non trovato in {nv.norma}: per questo "
                          f"numero Normattiva restituisce l'art. {served}, quindi l'articolo "
                          "non esiste nell'atto (controlla il numero)" + _altrove(act, nv, result))}
    if act is not None and requested is not None:
        numbers = {ident[0] for ident in map(_article_identity, act.article_keys(part)) if ident}
        if requested[0] not in numbers:
            return {**base, "esito": ARTICLE_NOT_FOUND,
                    "error": (f"articolo {nv.numero_articolo} non trovato in {nv.norma}: nessun "
                              f"articolo con il numero {requested[0]} tra i {len(numbers)} numeri "
                              "dell'atto (export Akoma Ntoso di Normattiva)" + _altrove(act, nv, result))}
    if served is not None:
        return _unavailable(base, nv, f"Normattiva restituisce l'art. {served}, che non coincide "
                                      "con quello richiesto, e la struttura dell'atto non basta a "
                                      "stabilire se l'articolo esista")
    if act is not None:
        return _unavailable(base, nv, "Normattiva non indica quale articolo ha restituito e la "
                                      "struttura dell'atto non basta a stabilirlo")
    return _unavailable(base, nv, "Normattiva non indica quale articolo ha restituito e l'export "
                                  "strutturato dell'atto non è raggiungibile. Riprova più tardi")


async def _fetch_normattiva_annex(nv: NormaVisitata, annex_id: str, article: str, *,
                                  canale: str = "html") -> dict:
    """An annex (or an article of an annex) of a Normattiva act, named as the act names it.

    Only the AKN export says which part the act calls "Allegato I.7": without it this
    is an error, never the body article that happens to carry the same number. An
    article of the annex then gets the URN of its part (";36:8~art30": Normattiva
    numbers the parts by position) and, on the HTML channel, that page's text.
    """
    full = await with_full_date(nv.norma)
    url = full.url()
    base = {"text": "", "url": url, "source": "normattiva-akn", "data_atto": full.data}
    label = f"Allegato {annex_id}" + (f", art. {article}" if article else "")
    if _akn_disabled():
        return {**base, "esito": CHECK_UNAVAILABLE,
                "error": f"{label}: gli allegati si leggono solo dall'export Akoma Ntoso (AKN_DISABLED attivo)"}

    from .akn_fetch import fetch_act_akn

    act = await fetch_act_akn(full)
    if act is None:
        return {**base, "esito": CHECK_UNAVAILABLE,
                "error": f"{label}: export Akoma Ntoso di Normattiva non disponibile, allegato non recuperabile"}
    name = act.annex_name(annex_id)
    if name is None:
        available = ", ".join(act.annex_names()) or "nessuno con articoli"
        return {**base, "esito": ARTICLE_NOT_FOUND,
                "error": f"Allegato {annex_id} non trovato nell'atto. Allegati disponibili: {available}"}
    text = act.annex_article(annex_id, article) if article else act.annex_text(annex_id)
    if not text:
        return {**base, "esito": ARTICLE_NOT_FOUND, "error": f"{label} non trovato in {name}"}
    position = act.annex_position(annex_id)
    if article and position:
        part_url = url_in_part(full.url(article=article), position)
        if canale == "html":
            try:
                page_text, served = await _normattiva_page(part_url)
            except httpx.HTTPError:
                page_text, served = "", None
            requested = _article_identity(normalize_article_key(article))
            if (page_text and served is not None and _article_identity(served) == requested
                    and _stesso_articolo(page_text, text)):
                return {**base, "text": page_text, "url": part_url, "source": "normattiva", "allegato": name}
        return {**base, "text": text, "url": part_url, "allegato": name}
    return {**base, "text": text, "allegato": name}


async def fetch_annotations(nv: NormaVisitata) -> dict:
    """Fetch Brocardi annotations (ratio legis, spiegazione, massime).

    Returns: {"annotations": dict, "url": str, "source": "brocardi"}; with Brocardi
    switched off (``lib/_brocardi_switch.py``) nothing is fetched and ``error`` says so.
    """
    if not _brocardi_switch.enabled():
        return {"annotations": {}, "url": "", "source": "brocardi", "error": _brocardi_switch.DISABLED_NOTE}
    brocardi_url = find_brocardi_url(nv.norma.tipo_atto_normalized, nv.norma.numero_atto, nv.norma.data)
    if not brocardi_url:
        return {"annotations": {}, "url": "", "source": "brocardi",
                "error": f"No Brocardi mapping for '{nv.norma.tipo_atto_normalized}'"}

    article_num = nv.numero_articolo.replace("-", "") if nv.numero_articolo else ""
    if not article_num:
        return {"annotations": {}, "url": brocardi_url, "source": "brocardi",
                "error": "Article number required for Brocardi annotations"}

    async with async_client("brocardi", headers=_HEADERS, timeout=_TIMEOUT, follow_redirects=True) as client:
        # Step 1: fetch main page and find article link
        article_url = await _find_brocardi_article_url(client, brocardi_url, article_num)
        if not article_url:
            return {"annotations": {}, "url": brocardi_url, "source": "brocardi",
                    "error": f"Article {nv.numero_articolo} not found on Brocardi"}

        # Step 2: fetch article page and extract sections
        resp = await client.get(article_url)
        resp.raise_for_status()
        note_source("brocardi", str(resp.url) if hasattr(resp, "url") else "")
        soup = BeautifulSoup(resp.text, "lxml")

    annotations = _extract_brocardi_sections(soup)
    return {"annotations": annotations, "url": article_url, "source": "brocardi"}


# ---------------------------------------------------------------------------
# Normattiva HTML channel: VisuaLex's extractor, VisuaLex's order
# ---------------------------------------------------------------------------

async def _normattiva_page(url: str) -> "tuple[str, str | None]":
    """``(article_text, the number the page gives the article)`` for a Normattiva article page.

    The text is VisuaLex's extraction, byte for byte (``normattiva_html``); ``""``
    when the page has no readable article body. The reading is kept for a day
    (``pagine_normattiva``), so the same article asked again costs no request.
    """
    rec = pagine_normattiva.leggi(url)
    if rec is not None:
        note_source("normattiva", url)
        return rec["testo"], rec["servito"]
    async with async_client("normattiva", headers=_HEADERS, timeout=_TIMEOUT, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        note_source("normattiva", str(resp.url) if hasattr(resp, "url") else "")
        html = resp.text
    text, served = _normattiva_article_page(html)
    if text:
        pagine_normattiva.scrivi(url, text, served)
    return text, served


def _normattiva_article_page(html: str) -> "tuple[str, str | None]":
    """The article text of a Normattiva page and the number the page gives it (None if unsaid).

    One parse, with VisuaLex's parser, serves both. A page with no ``div.bodyTesto``
    (an act's title page, an error page) has no article text: ``""``, never the
    whole page.
    """
    corpo = normattiva_html.corpo_testo(normattiva_html.parse_document(html))
    if corpo is None:
        return "", None
    return _testo_corpo(corpo), _served_article_key(corpo)


def _testo_corpo(corpo: Tag) -> str:
    try:
        return normattiva_html.estrai_da_corpo(corpo)
    except normattiva_html.ParsingError:
        return ""


def _testo_intero(corpo: Tag) -> str:
    """Every visible text of a ``div.bodyTesto``, cleaned as VisuaLex cleans: the full act's
    per-article fallback (no frozen contract there), which must not drop what lies outside
    the commi as the scenario extractor would."""
    testo, _ = normattiva_html.extract_text_recursive(corpo)
    testo = re.sub(r"\n{3,}", "\n\n", testo).strip()
    return re.sub(r"[ \t]+", " ", testo)


def _extract_normattiva_article(html: str) -> str:
    return _normattiva_article_page(html)[0]


async def _html_article(nv: NormaVisitata, url: str, part: "str | None") -> dict:
    """The HTML channel: the page first, the Akoma Ntoso export only when the page fails.

    As VisuaLex's ``NormattivaScraper.get_document``: the export's text differs from
    the page's (accents transliterated, a heading of its own), so it is served only
    when the alternative is no text, and ``source`` says where it came from.
    """
    errore_pagina: "httpx.HTTPError | None" = None
    try:
        text, served = await _normattiva_page(url)
    except httpx.HTTPError as exc:
        # The page could not be fetched: the export is the last resort here too,
        # and if it has no text either, the page's error is the answer.
        errore_pagina, text, served = exc, "", None
    result = {"text": text, "url": url, "source": "normattiva", "data_atto": nv.norma.data}
    if not nv.numero_articolo:
        if errore_pagina is not None:
            raise errore_pagina
        return result
    requested = _article_identity(normalize_article_key(nv.numero_articolo))
    if text:
        got = _article_identity(served) if served is not None else None
        if requested is not None and got == requested:
            return result
        # The page does not confirm the article asked for: the act's structure (its
        # Akoma Ntoso export, one more request, only on this path) decides.
        act = await _akn_act(nv)
        if requested is not None and act is not None:
            if (got is None and requested in _identita_articoli(act, part)
                    and (part or not annex_id_of(act.main_part) or _URL_NOMINA_PARTE.search(url))):
                # The page does not say which article it is ("Codice Penale-art. 524"
                # with the repeal notice outside the label) and the act has it: the
                # page is the article, as VisuaLex serves it. Not when the act's main
                # text is a code in an annex and the URN names the decree's body
                # (art. 2 of d.lgs. 104/2010 asked as the decree's): the unlabelled page
                # is then the decree's, and the code's article comes from the export.
                return result
            if got is None and requested in _identita_articoli(act, part) and not part:
                servito = _da_export(act, nv, url, part, result, etichetta=True)
                if servito:
                    return servito
            if got is not None and got[0] != requested[0] and requested[0] in _numeri_articoli(act, part):
                # The page names another number, but the act's main text has the one asked
                # for: it lives in a part the URN does not reach, a code approved in an
                # annex of its decree (art. 120 of d.lgs. 104/2010 asked as the decree's).
                # The code's own page (";104:2~art120") when the URN can name the part, as
                # VisuaLex reads it; else the code's article from the export.
                if not part:
                    pagina = await _pagina_della_parte(nv, url, act, requested)
                    if pagina is not None:
                        return pagina
                servito = _da_export(act, nv, url, part, result, etichetta=not part)
                if servito:
                    return servito
                return _unavailable({**result, "text": ""}, nv,
                                    f"Normattiva restituisce l'art. {served}, ma l'atto ha un art. "
                                    f"{requested[0]}: la pagina non è quella dell'articolo richiesto")
        return _checked_html_article(result, nv, served, act, part)
    act = await _akn_act(nv)
    servito = _da_export(act, nv, url, part, result) if act is not None else None
    if servito:
        return servito
    if errore_pagina is not None:
        raise errore_pagina
    return {**result, "esito": CHECK_UNAVAILABLE,
            "error": (f"testo non leggibile per l'art. {nv.numero_articolo} di {nv.norma}: la pagina di "
                      "Normattiva non contiene il testo dell'articolo e l'export Akoma Ntoso non lo fornisce")}


#: The ":k" after the act number of a Normattiva URL: the URN names one of the act's parts.
_URL_NOMINA_PARTE = re.compile(r";[^;:~!@?]+:\d+(?=~|!|@|$)")


def _identita_articoli(act, part: "str | None") -> "set[tuple[str, str]]":
    """``(number, suffix)`` of every article of the act's part (main part by default)."""
    return {ident for ident in map(_article_identity, act.article_keys(part)) if ident}


def _numeri_articoli(act, part: "str | None") -> "set[str] | None":
    """The article numbers of the act's part (main part by default), None without an export."""
    if act is None:
        return None
    return {ident[0] for ident in map(_article_identity, act.article_keys(part)) if ident}


def _da_export(act, nv: NormaVisitata, url: str, part: "str | None", base: dict, *,
               etichetta: bool = False) -> "dict | None":
    """The article from the Akoma Ntoso export, labelled as such, or None when the export lacks it.

    ``allegato`` names the part it comes from when the act's main text is a code approved
    in an annex, or when *etichetta* says the URN's page does not reach that part; the URL
    is then the part's own (``;104:2~art120``).
    """
    akn_text = _akn_article(act, nv.numero_articolo, part)
    if not akn_text:
        return None
    servito = {"text": akn_text, "url": url, "source": "normattiva-akn", "data_atto": base.get("data_atto", "")}
    if not part and (etichetta or annex_id_of(act.main_part)):
        servito["allegato"] = act.main_part
        if etichetta:
            servito["url"] = url_in_part(url, act.part_position())
    return servito


def _confronto(testo: str) -> str:
    """A text reduced for comparing a page with the export: no accents, case, markup or heading."""
    testo = re.sub(r"^#+[^\n]*\n", "", testo or "", count=1)  # the export's "### Art. N" line
    testo = unicodedata.normalize("NFKD", testo)
    testo = "".join(c for c in testo if not unicodedata.combining(c)).lower()
    return " ".join(re.sub(r"[^0-9a-z]+", " ", testo).split())


def _stesso_articolo(pagina: str, export: str | None) -> bool:
    """Whether a page's text is the export's article: their first 200 characters, compared.

    The page of ``;k~artN`` names its article's number only, which every part of an act
    may share: if ``k`` were not the part asked for, the number alone would let another
    annex's article through under this one's name. The export, which knows the part,
    has the last word.
    """
    a, b = _confronto(pagina)[:200], _confronto(export or "")[:200]
    return bool(a and b) and difflib.SequenceMatcher(None, a, b).ratio() >= 0.8


async def _pagina_della_parte(nv: NormaVisitata, url: str, act, requested) -> "dict | None":
    """The article from the page of the act's main part (``;104:2~art120``), or None.

    One more page, only when the decree's own URN served another article and the act's
    main text is a part Normattiva numbers: the text is then the page's, VisuaLex's
    ``article_text``, not the export's transliteration.
    """
    part_url = url_in_part(url, act.part_position())
    if part_url == url:
        return None
    try:
        text, served = await _normattiva_page(part_url)
    except httpx.HTTPError:
        return None
    if not text or served is None or _article_identity(served) != requested:
        return None
    if not _stesso_articolo(text, _akn_article(act, nv.numero_articolo, None)):
        return None
    return {"text": text, "url": part_url, "source": "normattiva", "data_atto": nv.norma.data,
            "allegato": act.main_part}


async def _akn_act(nv: NormaVisitata):
    """The parsed Akoma Ntoso export of the act, or None (disabled, unreachable)."""
    if _akn_disabled():
        return None
    from .akn_fetch import fetch_act_akn

    try:
        return await fetch_act_akn(nv.norma)
    except Exception:  # noqa: BLE001 - the export is a fallback: its failure is "no export"
        return None


# ---------------------------------------------------------------------------
# EUR-Lex fetch + extraction
# ---------------------------------------------------------------------------

_CELLAR_BASE = "https://publications.europa.eu/resource/celex/"


def _build_celex(norma) -> str | None:
    """Build CELEX identifier from Norma. Returns None for treaties."""
    from .map import EURLEX
    norm = norma.tipo_atto_normalized.lower()
    eurlex_val = EURLEX.get(norm)
    if not eurlex_val or eurlex_val.startswith("https"):
        return None
    type_letter = {"reg": "R", "dir": "L"}.get(eurlex_val, "R")
    year = norma.data.split("-")[0] if norma.data and "-" in norma.data else norma.data
    number = norma.numero_atto.zfill(4)
    return f"3{year}{type_letter}{number}"


def _eurlex_urls(norma) -> tuple[str, str]:
    """Return (fetch_url, display_url) for an EU act, or ("", "") if not an EU act.

    Everything is fetched from CELLAR by CELEX id: EUR-Lex answers automated
    requests with a WAF challenge (HTTP 202 and an empty body). The reader is
    shown the eur-lex.europa.eu page as the citable URL (a browser passes that
    challenge and the CELLAR expression URL is not quotable): for treaties the
    page in the EURLEX table, for regulations and directives the CELEX page.
    """
    from .map import EURLEX, EURLEX_TREATY_CELEX
    from urllib.parse import quote

    norm = norma.tipo_atto_normalized.lower()
    eurlex_val = EURLEX.get(norm)
    if not eurlex_val:
        return "", ""

    treaty_celex = EURLEX_TREATY_CELEX.get(norm)
    if treaty_celex:
        return f"{_CELLAR_BASE}{quote(treaty_celex, safe='')}", eurlex_val

    celex = _build_celex(norma)
    if not celex:
        return "", ""
    return f"{_CELLAR_BASE}{celex}", eurlex_citable_url(celex)


def eurlex_citable_url(celex: str) -> str:
    """The quotable EUR-Lex page of a CELEX document (Italian version)."""
    return f"https://eur-lex.europa.eu/legal-content/IT/TXT/?uri=CELEX:{celex}"


async def _fetch_eurlex_html(norma) -> tuple[str, str]:
    """Fetch EUR-Lex HTML via EU Publications Office Cellar (bypasses WAF).

    For treaties (TUE, TFUE, CDFUE) falls back to direct EUR-Lex URL.
    Returns (html, url). On failure returns ("", url).
    """
    url, display_url = _eurlex_urls(norma)
    if not url:
        return "", ""

    async with async_client("eur_lex",
        headers={
            **_HEADERS,
            "Accept": "application/xhtml+xml,text/html",
            "Accept-Language": "it-IT,it;q=0.9",
        },
        timeout=httpx.Timeout(60.0, connect=10.0),
        follow_redirects=True,
    ) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        note_source("eur_lex", str(resp.url) if hasattr(resp, "url") else "")
        html = resp.text

    # Detect WAF challenge (202 + tiny body)
    if resp.status_code == 202 or (len(html) < 5000 and "WAF" in html):
        return "", url

    final_url = display_url or (str(resp.url) if hasattr(resp, "url") else url)
    return html, final_url


def _extract_eurlex_article(html: str, article: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    if not article:
        return soup.get_text(separator="\n", strip=True)

    # Recital / considerando — encoded as "rec_N" by _parse_reference
    if article.startswith("rec_"):
        recital_num = article[4:]
        # On CELLAR a recital is a two-cell table row inside div#rct_N:
        # <td><p>(42)</p></td><td><p>text</p></td>. The number and the text are
        # separate cells, so both must be read (the number cell alone is not the recital).
        recital_div = soup.find("div", id=f"rct_{recital_num}")
        if recital_div:
            text = _table_rows_text(recital_div)
            if text:
                return text
        pat = re.compile(rf"^\(\s*{re.escape(recital_num)}\s*\)")
        for p in soup.find_all("p"):
            text = p.get_text(strip=True)
            if pat.match(text):
                # Same layout without the div id: take the whole row, not just the number cell.
                row = p.find_parent("tr")
                if row is not None:
                    row_text = _row_text(row)
                    if row_text:
                        return row_text
                return text
        return f"[Considerando {recital_num} non trovato nel documento EUR-Lex]"

    annex = split_annex(article)
    if annex:
        return _extract_eurlex_annex(soup, *annex)

    # Strategy 1: semantic id — div#art_N (most reliable on Cellar XHTML)
    art_id = f"art_{article}"
    article_div = soup.find("div", id=art_id)
    if article_div:
        return _extract_eurlex_subdivision(article_div)

    search_patterns = [f"Articolo {article}", f"Article {article}", f"Art. {article}"]
    # A title names the article only if the number ends there: "Articolo 9" is not
    # the head of "Articolo 90", which a bare startswith() served for a missing art. 9.
    title_re = re.compile(
        "^(?:" + "|".join(re.escape(p) for p in search_patterns) + r")(?!\d)"
    )

    # Strategy 2: <p class="oj-ti-art"> (Cellar/OJ format)
    for pattern in search_patterns:
        for p_tag in soup.find_all("p", class_=lambda c: c and "ti-art" in c):
            title = p_tag.get_text(strip=True)
            if title.startswith(pattern) and title_re.match(title):
                # Check if parent is eli-subdivision — if so, extract the whole block
                parent_sub = p_tag.find_parent("div", class_=lambda c: c and "eli-subdivision" in c)
                if parent_sub:
                    return _extract_eurlex_subdivision(parent_sub)
                # Fallback: collect siblings until next article
                return _extract_eurlex_siblings(p_tag)

    # Strategy 3: eli-subdivision containing article text
    for subdiv in soup.find_all("div", class_=lambda c: c and "eli-subdivision" in c):
        title_elem = subdiv.find(
            ["p", "span", "div"],
            string=lambda s: s and bool(title_re.match(s.strip())),
        )
        if title_elem:
            return _extract_eurlex_subdivision(subdiv)

    # Strategy 4: regex text match anywhere
    article_regex = re.compile(rf"^Articolo\s+{re.escape(str(article))}\b", re.IGNORECASE)
    for tag in soup.find_all(["p", "div", "span", "h1", "h2", "h3", "h4"]):
        if article_regex.match(tag.get_text(strip=True)):
            parent_sub = tag.find_parent("div", class_=lambda c: c and "eli-subdivision" in c)
            if parent_sub:
                return _extract_eurlex_subdivision(parent_sub)
            return _extract_eurlex_siblings(tag)

    return f"[Articolo {article} non trovato nel documento EUR-Lex]"


def _extract_eurlex_annex(soup: BeautifulSoup, annex_id: str, article: str) -> str:
    """Text of an annex of an EU act: CELLAR marks each one as ``div#anx_<N>``.

    The points of an annex ("1.", "a)") are two-cell table rows nested in each
    other; they are rendered one per line, the label beside its text. EU annexes
    are not divided into articles, so an article of an annex is refused rather
    than answered with the whole annex.
    """
    if article:
        return (f"[Gli allegati degli atti UE non sono suddivisi in articoli: "
                f"richiedere l'Allegato {annex_id} per intero]")
    wanted = annex_id.strip().upper()
    annexes = soup.find_all("div", id=re.compile(r"^anx_"))
    for div in annexes:
        if div["id"][4:].upper() == wanted:
            return "\n".join(_eurlex_block_lines(div))
    available = ", ".join(div["id"][4:] for div in annexes) or "nessuno"
    return f"[Allegato {annex_id} non trovato nel documento EUR-Lex. Allegati presenti: {available}]"


def _eurlex_block_lines(node: Tag, indent: str = "") -> list[str]:
    """Lines of a CELLAR block: paragraphs as they are, table rows as "label text"."""
    lines: list[str] = []
    for child in node.children:
        if not isinstance(child, Tag):
            continue
        if child.name == "table":
            body = child.find("tbody", recursive=False) or child
            for row in body.find_all("tr", recursive=False):
                cells = row.find_all("td", recursive=False)
                if len(cells) < 2:
                    lines.extend(_eurlex_block_lines(row, indent))
                    continue
                label = " ".join(cells[0].get_text().split())
                content = _eurlex_block_lines(cells[1], indent + "  ")
                if content:
                    content[0] = f"{indent}{label} {content[0].strip()}".rstrip()
                    lines.extend(content)
                elif label:
                    lines.append(f"{indent}{label}")
        elif child.name in ("p", "span", "h1", "h2", "h3", "h4"):
            text = " ".join(child.get_text().split())
            if text:
                lines.append(f"{indent}{text}")
        else:
            lines.extend(_eurlex_block_lines(child, indent))
    return lines


def _row_text(row: Tag) -> str:
    """Text of a table row: its cells joined by a space ("(42)" + recital text)."""
    for note in row.find_all("a"):
        # OJ footnote call ("(10)"): keep it apart from the words around it.
        if note.find("span", class_=lambda c: c and "note-tag" in c):
            note.replace_with(f" {note.get_text(strip=True)} ")
    cells = (" ".join(c.get_text().split()) for c in row.find_all("td"))
    return " ".join(t for t in cells if t)


def _table_rows_text(node: Tag) -> str:
    """Rows of the tables inside ``node``, one per line; plain text if it holds no table."""
    rows = [t for t in (_row_text(r) for r in node.find_all("tr")) if t]
    if rows:
        return "\n".join(rows)
    return node.get_text(strip=True)


def _extract_eurlex_subdivision(div: Tag) -> str:
    """Extract text from an eli-subdivision div, handling nested structure."""
    parts: list[str] = []
    for child in div.children:
        if isinstance(child, NavigableString):
            t = str(child).strip()
            if t:
                parts.append(t)
        elif isinstance(child, Tag):
            # Skip nested article subdivisions (they are separate articles)
            if child.get("class") and any("eli-subdivision" in c for c in child.get("class", [])):
                child_id = child.get("id", "")
                if child_id.startswith("art_"):
                    continue
            if child.name == "table":
                for row in child.find_all("tr"):
                    cells = row.find_all("td")
                    row_text = " ".join(c.get_text(strip=True) for c in cells)
                    if row_text:
                        parts.append(row_text)
            else:
                t = child.get_text(strip=True)
                if t:
                    parts.append(t)
    return "\n".join(parts)


# Article-heading class, exactly: "sti-art" is the *subtitle* of the same
# article ("(ex articolo 81 del TCE)"), not the start of the next one.
_TI_ART_CLASS = re.compile(r"^(?:oj-)?ti-art$")


def _extract_eurlex_siblings(start_tag: Tag) -> str:
    """Collect text from start_tag and siblings until next article header."""
    full_text = [start_tag.get_text(strip=True)]
    next_article_pat = re.compile(r"^Articolo\s+\d+|^Article\s+\d+|^Art\.\s+\d+", re.IGNORECASE)
    element = start_tag.find_next_sibling()
    while element:
        classes = element.get("class", []) if hasattr(element, "get") else []
        if any(_TI_ART_CLASS.match(c) for c in classes):
            break
        elem_text = element.get_text(strip=True) if hasattr(element, "get_text") else ""
        if next_article_pat.match(elem_text):
            break
        if element.name in ["p", "div", "span"]:
            if elem_text:
                full_text.append(elem_text)
        elif element.name == "table":
            for row in element.find_all("tr"):
                cells = row.find_all("td")
                row_text = " ".join(c.get_text(strip=True) for c in cells)
                if row_text:
                    full_text.append(row_text)
        element = element.find_next_sibling()
    return "\n".join(full_text)


# ---------------------------------------------------------------------------
# Brocardi extraction
# ---------------------------------------------------------------------------

async def _find_brocardi_article_url(client: httpx.AsyncClient, base_url: str, article_num: str) -> str | None:
    """Navigate Brocardi to find the article page URL (``BrocardiDisabled`` while switched off)."""
    _brocardi_switch.guard(base_url)
    cache_key = f"{base_url}#{article_num}"
    if cache_key in _brocardi_url_cache:
        return _brocardi_url_cache[cache_key]

    resp = await client.get(base_url)
    resp.raise_for_status()
    note_source("brocardi", str(resp.url) if hasattr(resp, "url") else "")
    html = resp.text

    pattern = re.compile(rf'href=["\']([^"\']*art{re.escape(article_num)}\.html)["\']')

    # Direct match in main page — use base_url (not domain root) so relative
    # hrefs like "libro-quarto/titolo-ix/art2043.html" resolve correctly
    page_url = str(resp.url) if hasattr(resp, "url") else base_url
    if not page_url.endswith("/"):
        page_url += "/"
    matches = pattern.findall(html)
    if matches:
        result = urljoin(page_url, matches[0])
        _brocardi_url_cache[cache_key] = result
        return result

    # Search in section-title links (sub-pages)
    soup = BeautifulSoup(html, "lxml")
    max_sub_pages = 15
    fetched = 0
    for section in soup.find_all("div", class_="section-title"):
        if fetched >= max_sub_pages:
            break
        for a_tag in section.find_all("a", href=True):
            if fetched >= max_sub_pages:
                break
            sub_url = urljoin(page_url, a_tag.get("href", ""))
            if not sub_url.startswith("https://www.brocardi.it"):
                continue
            _brocardi_switch.guard(sub_url)
            fetched += 1
            await asyncio.sleep(0.5)
            try:
                sub_resp = await client.get(sub_url)
                sub_resp.raise_for_status()
                note_source("brocardi", str(sub_resp.url) if hasattr(sub_resp, "url") else "")
                sub_page_url = str(sub_resp.url) if hasattr(sub_resp, "url") else sub_url
                if not sub_page_url.endswith("/"):
                    sub_page_url += "/"
                sub_matches = pattern.findall(sub_resp.text)
                if sub_matches:
                    result = urljoin(sub_page_url, sub_matches[0])
                    _brocardi_url_cache[cache_key] = result
                    return result
            except httpx.HTTPError:
                continue

    return None


def _extract_brocardi_sections(soup: BeautifulSoup) -> dict:
    """Extract Ratio, Spiegazione, Brocardi, Massime from a Brocardi article page."""
    info: dict = {}

    corpo = soup.find("div", class_="panes-condensed panes-w-ads content-ext-guide content-mark")
    if not corpo:
        # Fallback: try the whole body
        corpo = soup.find("body") or soup
        if not corpo:
            return info

    # Brocardi (adagi/proverbi)
    brocardi_sections = corpo.find_all("div", class_="brocardi-content")
    if brocardi_sections:
        info["Brocardi"] = [_clean_text(s.get_text()) for s in brocardi_sections]

    # Ratio Legis
    ratio_section = corpo.find("div", class_="container-ratio")
    if ratio_section:
        ratio_text = ratio_section.find("div", class_="corpoDelTesto")
        if ratio_text:
            info["Ratio"] = _clean_text(ratio_text.get_text())

    # Spiegazione
    spiegazione_header = corpo.find("h3", string=lambda t: t and "Spiegazione dell'art" in t)
    if spiegazione_header:
        spiegazione_content = spiegazione_header.find_next_sibling("div", class_="text")
        if spiegazione_content:
            info["Spiegazione"] = _clean_text(spiegazione_content.get_text())

    # Massime giurisprudenziali
    massime_header = corpo.find("h3", string=lambda t: t and "Massime relative all'art" in t)
    if massime_header:
        massime_content = massime_header.find_next_sibling("div", class_="text")
        if massime_content:
            sentenze = massime_content.find_all("div", class_="sentenza")
            massime = []
            for sentenza_div in sentenze:
                header = sentenza_div.find("strong")
                header_text = header.get_text(strip=True) if header else ""
                body_text = _clean_text(sentenza_div.get_text())
                if body_text:
                    massime.append({"header": header_text, "text": body_text})
            if massime:
                info["Massime"] = massime

    return info


def _clean_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# ---------------------------------------------------------------------------
# Full act download (for PDF generation)
# ---------------------------------------------------------------------------

# PDF flavours CELLAR serves by content negotiation, in order of preference. A plain
# "application/pdf" is answered 404 ("no content datastream of the requested type"): the
# flavour must be named. PDF/A-1a is the one published for the acts of the OJ series L.
_CELLAR_PDF_ACCEPT = (
    "application/pdf;type=pdfa1a",
    "application/pdf;type=pdfa2a",
    "application/pdf;type=pdf1x",
    "application/pdf;type=pdfx",
)


async def download_eurlex_pdf(norma: "Norma") -> bytes:
    """Download the official Italian PDF of an EU act.

    EUR-Lex answers automated requests for its PDF endpoint with a WAF challenge (HTTP 202,
    empty body), so the file is fetched from CELLAR, the Publications Office repository the
    HTML path already uses: ``publications.europa.eu/resource/celex/{CELEX}`` with
    ``Accept: application/pdf;type=pdfa1a`` (fallbacks: pdfa2a, pdf1x, pdfx) and
    ``Accept-Language: ita``. The EUR-Lex PDF endpoint stays as the last resort.

    Returns raw PDF bytes.
    """
    from .map import EURLEX

    norm = norma.tipo_atto_normalized.lower()
    eurlex_val = EURLEX.get(norm)
    if not eurlex_val:
        raise ValueError(f"No EUR-Lex mapping for '{norma.tipo_atto}'")
    if eurlex_val.startswith("https"):
        raise ValueError(f"PDF not available for EU treaties ({norm})")

    celex = _build_celex(norma)
    if not celex:
        raise ValueError(f"Cannot build the CELEX number of '{norma.tipo_atto}'")
    cellar_url = f"{_CELLAR_BASE}{celex}"
    eurlex_url = f"https://eur-lex.europa.eu/legal-content/IT/TXT/PDF/?uri=CELEX:{celex}"

    last_error = "no PDF returned"
    async with async_client("eur_lex",
        headers=_HEADERS,
        timeout=httpx.Timeout(60.0, connect=10.0),
        follow_redirects=True,
    ) as client:
        for accept in _CELLAR_PDF_ACCEPT:
            try:
                resp = await client.get(
                    cellar_url, headers={"Accept": accept, "Accept-Language": "ita"}
                )
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                last_error = f"CELLAR {accept}: {exc}"
                continue
            note_source("eur_lex", str(resp.url) if hasattr(resp, "url") else "")
            if resp.content[:5] == b"%PDF-":
                return resp.content
            last_error = f"CELLAR {accept}: not a PDF"

        # Last resort: the EUR-Lex endpoint (challenged by the WAF for automated clients).
        resp = await client.get(eurlex_url, headers={"Accept": "application/pdf,*/*"})
        resp.raise_for_status()
        note_source("eur_lex", str(resp.url) if hasattr(resp, "url") else "")
        if resp.content[:5] == b"%PDF-":
            return resp.content
    raise ValueError(f"EUR-Lex did not return a PDF (CELLAR: {last_error})")


async def fetch_act_tree(norma: "Norma", *, link: bool = False, details: bool = False) -> dict:
    """Normattiva's article tree of an act, as VisuaLex's ``get_tree(..., return_metadata=True)``.

    ``{"articles": [...], "count": n, "metadata": {"annexes": [...]}, "url": act URL}``, or
    ``{"error": ..., "url": ...}`` when the page cannot be read or holds no tree. One page,
    the act's own; the widest tree of it is kept a day (``pagine_normattiva``), and every
    variant (``link``, ``details``) is read from that one, as VisuaLex does: a tree costs
    one request a day per act. A failure is never kept.
    """
    from .albero_normattiva import _narrow, _parse_normattiva_tree

    norma = await with_full_date(norma)  # a year-only act's tree is its real date's
    # The act's own URL, without a code's default part (";262:2" -> ";262"): the tree
    # numbers the parts itself, and builds each article's URL from this one.
    act_url = re.sub(r"(;[^;:~!@?]+):\d+$", r"\1",
                     Norma(tipo_atto=norma.tipo_atto, data=norma.data, numero_atto=norma.numero_atto).url())
    if not act_url:
        return {"error": "Could not generate URL", "url": ""}
    full = pagine_normattiva.leggi_albero(act_url)
    if full is None:
        async with async_client("normattiva", headers=_HEADERS, timeout=_TIMEOUT, follow_redirects=True) as client:
            resp = await client.get(act_url)
            resp.raise_for_status()
            note_source("normattiva", str(resp.url) if hasattr(resp, "url") else "")
            html = resp.text
        if not html or len(html) < 500:
            return {"error": "Empty response from server", "url": act_url}
        result, count, metadata = _parse_normattiva_tree(
            BeautifulSoup(html, "html.parser"), act_url, True, True, return_metadata=True)
        if not count:
            return {"error": result if isinstance(result, str) else "albero dell'atto vuoto", "url": act_url}
        full = {"result": result, "count": count, "metadata": metadata}
        pagine_normattiva.scrivi_albero(act_url, full)
    else:
        note_source("normattiva", act_url)
    # A copy: the tree kept in memory for a day is never the caller's to alter.
    full = copy.deepcopy(full)
    result = full["result"]
    if not link:
        result = [{k: v for k, v in e.items() if k != "url"} if isinstance(e, dict) else e for e in result]
    articles, count, metadata = _narrow(result, full["count"], full["metadata"], details, True)
    return {"articles": articles, "count": count, "metadata": metadata, "url": act_url}


async def fetch_act_index(norma: "Norma") -> dict:
    """Fetch the structured index (rubriche) of a Normattiva act.

    Uses /atto/vediRubriche endpoint to get article titles without full text.
    Returns: {"index": list[str], "codice_redazionale": str, "url": str} or {"error": str}
    """
    act_url = norma.url()
    if not act_url:
        return {"index": [], "url": "", "error": "Could not generate URL"}

    async with async_client("normattiva",
        headers=_HEADERS,
        timeout=httpx.Timeout(60.0, connect=10.0),
        follow_redirects=True,
    ) as client:
        resp = await client.get(act_url)
        resp.raise_for_status()
        note_source("normattiva", str(resp.url) if hasattr(resp, "url") else "")
        html = resp.text

        # Extract codiceRedazionale from ELI meta tags
        soup = BeautifulSoup(html, "lxml")
        codice_redaz = ""
        data_gu = ""
        for meta in soup.find_all("meta", attrs={"property": "eli:id_local"}):
            codice_redaz = meta.get("content", "")
            break
        # Extract dataPubblicazioneGazzetta from the page
        gu_match = re.search(r'dataPubblicazioneGazzetta=(\d{4}-\d{2}-\d{2})', html)
        if gu_match:
            data_gu = gu_match.group(1)

        if not codice_redaz or not data_gu:
            # Try to extract from the canonical URL or other patterns
            redaz_match = re.search(r'codiceRedazionale=([A-Z0-9]+)', html)
            if redaz_match:
                codice_redaz = redaz_match.group(1)
            gu_match2 = re.search(r'atto\.dataPubblicazioneGazzetta=(\d{4}-\d{2}-\d{2})', html)
            if gu_match2:
                data_gu = gu_match2.group(1)

        if not codice_redaz or not data_gu:
            return {"index": [], "url": act_url, "error": "Could not extract codiceRedazionale or dataGU from page"}

        # Fetch rubriche
        rub_url = f"https://www.normattiva.it/atto/vediRubriche?atto.dataPubblicazioneGazzetta={data_gu}&atto.codiceRedazionale={codice_redaz}"
        resp2 = await client.get(rub_url)
        resp2.raise_for_status()
        note_source("normattiva", str(resp2.url) if hasattr(resp2, "url") else "")

    rub_soup = BeautifulSoup(resp2.text, "lxml")
    entries: list[str] = []
    for li in rub_soup.find_all("li"):
        text = li.get_text(strip=True)
        if text:
            entries.append(text)

    if not entries:
        # Fallback: extract from the raw text
        raw = rub_soup.get_text(separator="\n", strip=True)
        entries = [line.strip() for line in raw.splitlines() if line.strip()]

    return {
        "index": entries,
        "codice_redazionale": codice_redaz,
        "data_gu": data_gu,
        "url": act_url,
    }


async def fetch_normattiva_full_text(norma: "Norma") -> dict:
    """Fetch the complete text of a Normattiva act by loading all articles via AJAX.

    Normattiva only renders Art. 1 in the static DOM. All other articles are loaded
    on-demand via /atto/caricaArticolo. This function extracts all article URLs from
    the sidebar tree (#albero) and fetches each one.

    Returns: {"text": str, "title": str, "url": str, "article_count": int} or {"error": str}
    """
    # A bare-year citation is resolved to the act's real date first (see with_full_date).
    norma = await with_full_date(norma)
    act_url = norma.url()
    if not act_url:
        return {"text": "", "title": "", "url": "", "error": "Could not generate URL"}

    # AKN-first: try the whole-act Akoma Ntoso XML export, fall back to the
    # per-article AJAX walker below.
    if not _akn_disabled():
        from .akn_fetch import fetch_act_akn

        act = await fetch_act_akn(norma)
        if act is not None:
            part = _akn_part_hint(norma)
            full_text = act.full_text(part=part)
            if full_text:
                title = act.part_title(part) or str(norma)
                # The AKN docTitle is the act's subject only ("Sospensione dei termini ..."):
                # when it does not carry the act's number, prefix the identifying heading.
                if not part and norma.numero_atto and norma.numero_atto not in title:
                    try:
                        display = act_display_title(await _act_metadata(norma))
                    except Exception:  # noqa: BLE001 - the heading is best effort
                        display = ""
                    title = display or title
                return {
                    "text": full_text,
                    "title": title,
                    "url": act_url,
                    "article_count": act.part_article_count(part),
                    "source": "normattiva-akn",
                }

    ajax_headers = {**_HEADERS, "X-Requested-With": "XMLHttpRequest"}

    async with async_client("normattiva",
        headers=_HEADERS,
        timeout=httpx.Timeout(120.0, connect=15.0),
        follow_redirects=True,
    ) as client:
        resp = await client.get(act_url)
        resp.raise_for_status()
        note_source("normattiva", str(resp.url) if hasattr(resp, "url") else "")
        html = resp.text
        soup = BeautifulSoup(html, "lxml")

        title = _normattiva_page_title(html, soup) or str(norma)

        # Extract first article already in the DOM
        first_body = soup.find("div", class_="bodyTesto")
        first_article_text = _testo_intero(first_body) if first_body else ""

        # Extract all article AJAX URLs from the sidebar tree
        article_urls = _extract_article_ajax_urls(html)

        if not article_urls:
            # Fallback: return just the first article (old behavior)
            return {"text": first_article_text, "title": title, "url": act_url, "article_count": 1}

        # Fetch all articles via AJAX, preserving order
        all_parts: list[str] = []
        seen_urls: set[str] = set()
        for ajax_path in article_urls:
            if ajax_path in seen_urls:
                continue
            seen_urls.add(ajax_path)
            ajax_url = f"https://www.normattiva.it{ajax_path}"
            try:
                art_resp = await client.get(ajax_url, headers=ajax_headers)
                art_resp.raise_for_status()
                note_source("normattiva", str(art_resp.url) if hasattr(art_resp, "url") else "")
                art_html = art_resp.text
                # Skip error pages
                if "Normattiva - Errore" in art_html or len(art_html) < 50:
                    continue
                art_soup = BeautifulSoup(art_html, "lxml")
                body = art_soup.find("div", class_="bodyTesto")
                if body:
                    text = _testo_intero(body)
                    if text and text != "[Articolo senza contenuto o abrogato]":
                        all_parts.append(text)
            except httpx.HTTPError:
                continue

    if not all_parts:
        return {"text": first_article_text, "title": title, "url": act_url, "article_count": 1}

    full_text = "\n\n---\n\n".join(all_parts)
    return {"text": full_text, "title": title, "url": act_url, "article_count": len(all_parts)}


def _normattiva_page_title(html: str, soup: BeautifulSoup) -> str:
    """Title of the act on its Normattiva page.

    The first <h1> of the page is the screen-reader banner ("Normattiva - Il portale della
    legge vigente"), never the act's title: the title is read from the page metadata
    ("LEGGE 7 ottobre 1969, n. 742 - Sospensione dei termini ..."), then from <title>.
    """
    display = act_display_title(act_page_metadata(html))
    if display:
        return display
    for h1 in soup.find_all("h1"):
        if "sr-only" in (h1.get("class") or []):
            continue
        text = h1.get_text(strip=True)
        if text:
            return text
    title_tag = soup.find("title")
    if not title_tag:
        return ""
    return re.sub(r"\s*-\s*Normattiva\s*$", "", title_tag.get_text(strip=True)).strip()


def _extract_article_ajax_urls(html: str) -> list[str]:
    """Extract /atto/caricaArticolo URLs from onclick handlers in the sidebar tree.

    Normattiva sidebar lists multiple versions (art.versione) for articles that
    have been amended. We keep only the first occurrence per article (idGruppo +
    idArticolo + flagTipoArticolo), which is the current/vigente version.
    """
    pattern = re.compile(r"showArticle\('(/atto/caricaArticolo\?[^']+)'")
    matches = pattern.findall(html)
    # Deduplicate by article identity (keep first = vigente version).
    # Params can appear in any order, so extract each individually.
    seen_articles: set[str] = set()
    unique: list[str] = []
    for raw_url in matches:
        url_clean = raw_url.replace("&amp;", "&")
        grp = re.search(r"art\.idGruppo=(\d+)", url_clean)
        art = re.search(r"art\.idArticolo=(\d+)", url_clean)
        flag = re.search(r"art\.flagTipoArticolo=(\d+)", url_clean)
        if grp and art and flag:
            article_key = f"{grp.group(1)}_{art.group(1)}_{flag.group(1)}"
            if article_key in seen_articles:
                continue
            seen_articles.add(article_key)
        elif url_clean in seen_articles:
            continue
        else:
            seen_articles.add(url_clean)
        unique.append(url_clean)
    return unique

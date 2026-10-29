"""Unified scraper for Normattiva, EUR-Lex, and Brocardi using httpx."""

import asyncio
import copy
import dataclasses
import difflib
import os
import re
import unicodedata
import warnings
from html import unescape
from urllib.parse import urljoin

import httpx
from mcp_legal_it.core._http import async_client
from bs4 import BeautifulSoup, Tag, XMLParsedAsHTMLWarning

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

from .. import _brocardi_switch, _clock
from .._http import note_source
from . import act_dates, normattiva_html, pagine_eurlex, pagine_normattiva
from .akn_parser import annex_id_of, comparable_article_key, normalize_article_key, position_hint
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


# A complete character reference: named (``&agrave;``), decimal (``&#39;``) or hex
# (``&#x27;``). ``html.unescape`` alone would also decode a name with no semicolon,
# turning text that is already plain («D&O &notizie») into «D&O ¬izie».
_ENTITA = re.compile(r"&(?:[A-Za-z][A-Za-z0-9]*|#[0-9]+|#[xX][0-9A-Fa-f]+);")


def _one_line(raw: str) -> str:
    """A title as one line with single spaces (the official heading keeps double spaces
    and line breaks)."""
    return " ".join(raw.split())


def _eli_title(raw: str) -> str:
    """The ``eli:title`` of a Normattiva page as plain text on one line.

    Normattiva escapes this attribute twice (``libert&amp;agrave;``), so the parsed
    value still reads ``libert&agrave;``: its complete entities are decoded once more.
    The other titles of the page are escaped once and arrive decoded already.
    """
    return _one_line(_ENTITA.sub(lambda m: unescape(m.group()), raw))


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
    title = _eli_title(meta_title.get("content") or "").rstrip(".").strip() if meta_title else ""
    page_title = soup.find("title")
    heading = _one_line(page_title.get_text(strip=True)) if page_title else ""
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
            # VisuaLex's check: the title must name this act (type, year and number).
            meta["data_titolo"] = act_dates.date_from_title(
                resp.text, _tipo_urn(norma), (norma.data or "")[:4], norma.numero_atto or "") or ""
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
    kind = _tipo_urn(norma)
    chiave = act_dates.chiave(kind, norma.data, norma.numero_atto)
    found = act_dates.leggi(chiave)
    if found:
        return dataclasses.replace(norma, data=found)
    try:
        meta = await _act_metadata(norma)
    except Exception:  # noqa: BLE001 - identity lookup is best effort
        return norma
    if kind in act_dates._TITLES:
        # VisuaLex's rule: the page's title names this act's type, year and number.
        date = meta.get("data_titolo", "")
        if date:
            act_dates.scrivi(chiave, date)
    else:
        # A kind the titles do not cover (a DPCM, a ministerial decree, a regional law):
        # the page's ELI date, accepted when it is in the cited year — a weaker check, as
        # before. Never kept: the resolver can answer a regional law with the state law of
        # the same year and number, and a year on disk would make that mistake last.
        date = meta.get("date", "")
        if not date.startswith(f"{norma.data}-"):
            date = ""
    if not date:
        return norma
    return dataclasses.replace(norma, data=date)


def _tipo_urn(norma: Norma) -> str:
    """The act's kind as an URN spells it: "decreto.legislativo"."""
    return norma.tipo_atto_normalized.strip().lower().replace(" ", ".")


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
        # The text in force of an amended act is its latest consolidation (issue #50).
        nv, ue = await _versione_ue(nv)
        if ue.get("error"):
            return {"text": "", "url": nv.norma.url(), "source": source, **ue}
        html, url = await _fetch_eurlex_html(nv.norma)
        if not html:
            return {"text": "", "url": url, "source": source, **ue, "error": "Could not fetch EUR-Lex document"}
        text = _extract_eurlex_article(html, nv.numero_articolo)
        if annex:
            if text.startswith("["):  # not found / not divided into articles
                return {"text": "", "url": url, "source": source, **ue, "error": text.strip("[]")}
            return {"text": text, "url": url, "source": source, **ue, "allegato": f"Allegato {annex[0]}"}
        if nv.numero_articolo and _EURLEX_NOT_FOUND_RE.match(text):
            # The extractor's "[Articolo N non trovato ...]" is an answer about the
            # document, not its text: returned as text it read as the article.
            errore = text.strip("[]")
            consolidato = ue.get("consolidato")
            if consolidato and ue.get("consolidato_verificato") and not nv.numero_articolo.startswith("rec_"):
                # The text in force is the consolidation's, and it has no such article: a later
                # act repealed or deleted it (art. 1 of dir. 2009/136). Said, never served from
                # the OJ page, which would present a repealed text as current.
                from .eurlex_consolidate import avviso_assente

                errore = avviso_assente(nv.numero_articolo, consolidato)
                ue = {**ue, "avviso_assenza": errore}
            return {"text": "", "url": url, "source": source, **ue, "esito": ARTICLE_NOT_FOUND,
                    "error": errore}
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
            nv = dataclasses.replace(nv, norma=full)  # the version asked for stays
        if nv.suffisso_versione() and _year_only_act(nv.norma):
            # A text at a date, or the original, of an act whose full date could not be read:
            # the export would be asked at today's date (the original's day is the act's),
            # and the page would be the placeholder act's. Refused, never today's text.
            return {"text": "", "url": nv.norma.url(), "source": source, "esito": CHECK_UNAVAILABLE,
                    "error": (f"{'testo originale' if nv.versione == 'originale' else 'testo a una data'} "
                              f"di {nv.norma}: la data completa dell'atto non è stata letta da Normattiva; "
                              "indicarla (data=\"AAAA-MM-GG\")")}
        url = nv.url()
        if not url:
            return {"text": "", "url": "", "source": "", "error": "Could not generate URL for this act"}

        part = _akn_part_hint(nv.norma)
        if canale == "html":
            return await _html_article(nv, url, part)

        # AKN channel: the official Akoma Ntoso XML export first, then the page.
        act = None
        if not _akn_disabled() and not senza_export(nv):
            from .akn_fetch import fetch_act_akn

            act = await fetch_act_akn(nv.norma, _vigenza_akn(nv))
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

        text, served = await _normattiva_page(url, nv.numero_articolo)
        url, text, served = await _di_oggi(url, text, served, nv.numero_articolo)
        result = {"text": text, "url": url, "source": source, "data_atto": nv.norma.data}
        if not nv.numero_articolo:
            return result
        if not text and (inserito := _esito_inserito(nv, url, result)):
            return inserito
        return _checked_html_article(result, nv, served, act, part)

    result = {"text": text, "url": url, "source": source, **ue}
    if is_eurlex and (nv.numero_articolo or "").startswith("rec_"):
        result["considerando"] = nv.numero_articolo[4:]  # cite_law prints it as the label, «(42)»
    return result


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
    wanted = comparable_article_key(nv.numero_articolo)
    trovato = {str(e["allegato"] or "") for e in entries
               if comparable_article_key(e["numero"]) == wanted and str(e["allegato"] or "") != asked}
    abrogato = sorted(part for part in trovato if any(comparable_article_key(k) == wanted for k in abrogati.get(part, ())))
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
                page_text, served = await _normattiva_page(part_url, article)
                part_url, page_text, served = await _di_oggi(part_url, page_text, served, article)
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

async def _normattiva_page(url: str, articolo: str | None = None) -> "tuple[str, str | None]":
    """``(article_text, the number the page gives the article)`` for a Normattiva article page.

    The text is VisuaLex's extraction, byte for byte (``normattiva_html``); ``""``
    when the page has no readable article body. The reading is kept for a day
    (``pagine_normattiva``), so the same article asked again costs no request, and
    so is what the same page says of the text's validity (VisuaLex's
    ``extract_validity``, checked against *articolo* when given).
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
        validita = await asyncio.to_thread(_validita_da_pagina, html, articolo)
        pagine_normattiva.scrivi(url, text, served, validita)
    return text, served


def _validita_da_pagina(html: str, articolo: str | None) -> "dict | None":
    """What the page states of its text's validity (VisuaLex's ``extract_validity``), never raising."""
    from . import normattiva_validity

    try:
        return normattiva_validity.extract_validity(html, article=articolo or None)
    except Exception:  # noqa: BLE001 - best effort by contract: no validity, never a wrong one
        return None


def validita_pagina(url: str, data_richiesta: str | None = None) -> "dict | None":
    """VisuaLex's ``validity`` of the page at *url*, from the page already fetched (no request).

    The state is reckoned against today: a window that ends before today is ``historical``;
    ``request_in_window`` against *data_richiesta*, the day a dated text was asked for.
    None when the page was not read or does not say.
    """
    from . import normattiva_validity

    rec = pagine_normattiva.leggi(url)
    validita = dict(rec["validita"]) if rec is not None and rec.get("validita") else None
    if validita is None:
        return None
    if validita["state"] in ("current", "historical"):
        oggi = _clock.today().isoformat()
        validita["state"] = ("current" if validita["valid_to"] is None or validita["valid_to"] >= oggi
                             else "historical")
    giorno = normattiva_validity._iso_day(data_richiesta)
    validita["request_in_window"] = (normattiva_validity._in_window(giorno, validita["valid_from"],
                                                                   validita["valid_to"]) if giorno else None)
    return validita


def _testo_di_oggi(url: str) -> "str | None":
    """The URL of today's text when the undated page at *url* may not be it, else None.

    Normattiva's page without a date can serve a version not in force yet: on 21/10/2026
    art. 3 of d.P.R. 131/1986 came back «ARTICOLO ABROGATO», «Testo in vigore dal:
    01-01-2027». A request without a date asks for the text in force today, so the page is
    asked again at today's date (``!vig=``) when its window starts after today, or when it
    states no window: fail closed, never the undated page without knowing which text it is.
    """
    if "!vig=" in url or "@originale" in url:
        return None
    rec = pagine_normattiva.leggi(url)
    oggi = _clock.today().isoformat()
    if not _in_vigore_oggi((rec or {}).get("validita"), oggi):
        return f"{url}!vig={oggi}"
    return None


def _in_vigore_oggi(validita: "dict | None", oggi: str) -> bool:
    """Whether a page's stated window holds today: started, and not ended.

    A window that ended before today is not today's text either: a page read before
    midnight and kept a day can be «al 31-12-2026» on 1 January.
    """
    if not validita or not validita.get("valid_from"):
        return False
    return validita["valid_from"] <= oggi and (validita.get("valid_to") is None or validita["valid_to"] >= oggi)


async def _di_oggi(url: str, text: str, served: "str | None", articolo: str) -> "tuple[str, str, str | None]":
    """``(url, text, served)`` of the text in force today, from a page just read for *articolo*.

    Unchanged when the page is not the article asked for (the existence check decides) or
    states a window that holds today. Otherwise today's page (``_testo_di_oggi``): one
    request more; if it cannot be read, ``("", None)``, never the undated page, which may
    be tomorrow's text: the export at today's date answers, or nothing does.
    """
    if not text or not articolo:
        return url, text, served
    # An article number with no digits ("unico" aside) has no identity to compare: its page
    # is checked all the same, never let through because the comparison cannot be made.
    requested = _article_identity(normalize_article_key(articolo))
    if requested is not None and served is not None and _article_identity(served) != requested:
        return url, text, served  # another article: the existence check decides
    # A page that does not say which article it is ("Testo Unico-art. 3", a repeal notice
    # outside the label) is checked too: it may be tomorrow's text all the same.
    oggi_url = _testo_di_oggi(url)
    if not oggi_url:
        return url, text, served
    try:
        oggi_text, oggi_served = await _normattiva_page(oggi_url, articolo)
    except httpx.HTTPError:
        oggi_text, oggi_served = "", None
    rec = pagine_normattiva.leggi(oggi_url) if oggi_text else None
    if (oggi_text and (oggi_served is None or requested is None or _article_identity(oggi_served) == requested)
            and _in_vigore_oggi((rec or {}).get("validita"), _clock.today().isoformat())):
        return oggi_url, oggi_text, oggi_served
    # Today's page could not be read, or does not say it is today's text: the export at
    # today's date answers, or nothing does.
    return url, "", None


#: "((ARTICOLO ABROGATO DAL D.LGS. 1 AGOSTO 2025, N. 123, COME MODIFICATO DAL D.L. 31 DICEMBRE
#: 2025, N. 200))", "PROVVEDIMENTO ABROGATO DAL D.LGS. 14 NOVEMBRE 2024, N. 175": the act a
#: repeal notice names. Bounded, read on a text's first 600 characters only.
_ABROGATO_DA = re.compile(
    r"\b(?:ARTICOLO|PROVVEDIMENTO)\s+(?:ABROGAT|SOPPRESS)[OA]\s+(?:DAL|DALLA|DALL'|DAGLI|DAI|DA)\s*"
    r"([^()\n]{3,240}?)\s*(?:\)\)|\n|$)",
    re.IGNORECASE,
)


def abrogato_da(testo: str) -> "str | None":
    """The act a repeal notice at the head of *testo* names, else None."""
    m = _ABROGATO_DA.search((testo or "")[:600])
    return " ".join(m.group(1).split()).rstrip(".,; ") if m else None


def avviso_versione_futura(futura: dict) -> str:
    """The sentence that tells the reader the undated page showed a version not in force yet."""
    atto = abrogato_da(futura.get("testo") or "")
    return (f"Normattiva mostra senza data il testo in vigore dal {futura['valid_from']}"
            + (f" (abrogato dal {atto})" if atto else "")
            + ": il testo riportato è quello in vigore oggi")


def versione_futura(url: str) -> "dict | None":
    """The version the undated page served, when it was not in force yet (no request).

    ``{"valid_from", "testo"}`` from the page already kept, else None. *url* may carry the
    ``!vig=`` of today's text: the page without it is the one looked up.
    """
    base = url.split("!vig=", 1)[0]
    rec = pagine_normattiva.leggi(base)
    validita = (rec or {}).get("validita") or {}
    if validita.get("valid_from") and validita["valid_from"] > _clock.today().isoformat():
        return {"valid_from": validita["valid_from"], "testo": rec.get("testo") or "",
                "change": "abrogated" if validita.get("state") == "abrogated" else "amended",
                "version_number": validita.get("version_number"), "validita": validita}
    return None


def articolo_inserito(url: str) -> "dict | None":
    """``{"upcoming", "testo", "url"}`` of an article inserted from a later day, else None (no request).

    Inserted means: the undated page's window starts after today, and the page at today
    (``!vig=``, already read by ``_di_oggi``) says «NON ANCORA ESISTENTE O VIGENTE».
    """
    from .normattiva_validity import starts_after_today, upcoming_change

    base = url.split("!vig=", 1)[0]
    rec = pagine_normattiva.leggi(base)
    validita = (rec or {}).get("validita")
    if not validita or not starts_after_today(validita, _clock.today()):
        return None
    oggi = pagine_normattiva.leggi(f"{base}!vig={_clock.today().isoformat()}")
    if ((oggi or {}).get("validita") or {}).get("state") != "not_yet":
        return None
    return {"upcoming": upcoming_change(validita, inserted=True), "testo": rec.get("testo") or "", "url": base}


def _esito_inserito(nv: NormaVisitata, url: str, result: dict) -> "dict | None":
    """An article inserted from a later day, else None: as VisuaLex (G-358), the later text is
    served, marked ``not_in_force``, with ``upcoming`` {change: "inserted"}; the request keeps
    its key (no date)."""
    inserito = articolo_inserito(url)
    if inserito is None:
        return None
    return {**result, "text": inserito["testo"], "url": inserito["url"], "upcoming": inserito["upcoming"],
            "not_in_force": True}


async def fetch_article_futura(nv: NormaVisitata, entro: "str | None" = None) -> dict:
    """The text of a Normattiva article not in force yet, asked for explicitly (VisuaLex G-357).

    The undated page, when its window starts after today, marked ``not_in_force`` with
    ``upcoming`` describing it; today's page (one request more) tells an article inserted
    from that day from one changed by it (``change`` None when it cannot be read and the
    change is not a repeal). *entro*, an ISO day after today: the later text must come into
    force by then. None published, none by *entro*, or a page whose validity cannot be read
    is the article's error, as in VisuaLex: nothing is claimed.
    """
    from .normattiva_validity import starts_after_today, upcoming_change, versions_between

    source = "normattiva"
    if nv.norma._is_eurlex():
        return {"text": "", "url": nv.norma.url(), "source": "eurlex",
                "error": "versione 'futura' disponibile per gli atti su Normattiva"}
    if split_annex(nv.numero_articolo):
        # Refused before any request, as the api refuses it (the annex's page is not read so).
        return {"text": "", "url": nv.norma.url(), "source": source,
                "error": "la versione futura di un allegato non è ancora disponibile"}
    full = await with_full_date(nv.norma)
    if full is not nv.norma:
        nv = dataclasses.replace(nv, norma=full)
    url = nv.url()
    base = {"text": "", "url": url, "source": source, "data_atto": nv.norma.data}
    illeggibile = {**base, "esito": CHECK_UNAVAILABLE,
                   "error": f"Non riesco a leggere la vigenza dell'art. {nv.numero_articolo} di {nv.norma} su Normattiva"}
    if not url or not nv.numero_articolo:
        return {**base, "error": "versione futura: indicare un articolo di un atto su Normattiva"}
    try:
        text, _served = await _normattiva_page(url, nv.numero_articolo)
    except httpx.HTTPError:
        return illeggibile
    validita = (pagine_normattiva.leggi(url) or {}).get("validita")
    if not text or not validita:
        return illeggibile
    if not starts_after_today(validita, _clock.today()):
        return {**base, "esito": ARTICLE_NOT_FOUND,
                "error": f"Nessuna versione non ancora in vigore per l'art. {nv.numero_articolo} di {nv.norma}"}
    oggi_url = f"{url}!vig={_clock.today().isoformat()}"
    try:
        await _normattiva_page(oggi_url, nv.numero_articolo)
    except httpx.HTTPError:
        pass
    oggi = (pagine_normattiva.leggi(oggi_url) or {}).get("validita")
    inserito = bool(oggi and oggi.get("state") == "not_yet")
    if entro and validita["valid_from"] > entro:
        if (tra := 0 if inserito else versions_between(validita, oggi)):
            # The day falls before the latest version, and other versions come first: Normattiva
            # shows only the latest, so the one of that day cannot be read (VisuaLex, the same).
            altre = "ce n'è un'altra" if tra == 1 else f"ce ne sono altre {tra}"
            return {**base, "esito": CHECK_UNAVAILABLE,
                    "error": (f"Non so dire quale versione dell'art. {nv.numero_articolo} di {nv.norma} sia in "
                              f"vigore il {entro}: prima di quella che entra in vigore il {validita['valid_from']} "
                              f"{altre}, che Normattiva non mostra a parte")}
        return {**base, "esito": ARTICLE_NOT_FOUND,
                "error": (f"La versione non ancora in vigore dell'art. {nv.numero_articolo} di {nv.norma} "
                          f"entra in vigore il {validita['valid_from']}")}
    upcoming = upcoming_change(validita, inserted=inserito, today=oggi)
    if oggi is None and upcoming["change"] == "amended":
        # Today's page could not be read: an amendment cannot be told from an insertion.
        upcoming["change"] = None
    return {**base, "text": text, "not_in_force": True, "upcoming": upcoming}


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
        text, served = await _normattiva_page(url, nv.numero_articolo)
    except httpx.HTTPError as exc:
        # The page could not be fetched: the export is the last resort here too,
        # and if it has no text either, the page's error is the answer.
        errore_pagina, text, served = exc, "", None
    requested = _article_identity(normalize_article_key(nv.numero_articolo)) if nv.numero_articolo else None
    url, text, served = await _di_oggi(url, text, served, nv.numero_articolo)
    result = {"text": text, "url": url, "source": "normattiva", "data_atto": nv.norma.data}
    if not nv.numero_articolo:
        if errore_pagina is not None:
            raise errore_pagina
        return result
    if not text and (inserito := _esito_inserito(nv, url, result)):
        return inserito
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
        text, served = await _normattiva_page(part_url, nv.numero_articolo)
        part_url, text, served = await _di_oggi(part_url, text, served, nv.numero_articolo)
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
    if _akn_disabled() or senza_export(nv):
        return None
    from .akn_fetch import fetch_act_akn

    try:
        return await fetch_act_akn(nv.norma, _vigenza_akn(nv))
    except Exception:  # noqa: BLE001 - the export is a fallback: its failure is "no export"
        return None


async def _versione_ue(nv: NormaVisitata) -> "tuple[NormaVisitata, dict]":
    """The EU text asked for, and what the answer says of it: ``(nv to read, extra keys)``.

    The extra keys are ``consolidato`` (``{"celex", "data", "modificato_da"}`` of the
    consolidation read, None for the Official Journal text) and ``consolidato_verificato``
    (True: CELLAR was asked; False: it could not say, and the OJ text is served with a
    notice; None: not asked, as for a treaty, the original text or a consolidation named
    by the caller). A day before the act's own date is an ``error`` with
    ``esito="riferimento_non_valido"``.
    """
    from . import eurlex_consolidate as ec
    from .map import EURLEX_TREATY_CELEX

    norma = nv.norma
    if norma.celex_consolidated:
        data = norma.celex_consolidated.split("-", 1)[1]
        return nv, {"consolidato": {"celex": norma.celex_consolidated, "data": f"{data[:4]}-{data[4:6]}-{data[6:]}",
                                    "modificato_da": None},
                    "consolidato_verificato": None}
    if (norma.tipo_atto_normalized.lower() in EURLEX_TREATY_CELEX
            or (nv.versione or "").strip().lower() == "originale"
            or (nv.numero_articolo or "").startswith("rec_")):
        # A treaty, the original text asked for, a recital (a consolidation has no preamble,
        # and amendments do not rewrite recitals): the Official Journal text, as before.
        return nv, {"consolidato": None, "consolidato_verificato": None}
    if split_annex(nv.numero_articolo):
        # A consolidation's annexes are not read yet: the OJ annex, said to be possibly outdated.
        return nv, {"consolidato": None, "consolidato_verificato": None, "allegato_oj": True}
    base = _build_celex(norma)
    info = await ec.consolidazioni(base) if base else None
    if info is None:
        return nv, {"consolidato": None, "consolidato_verificato": False}
    giorno = nv.data_versione or None
    oggi = _clock.today().isoformat()
    scelta, versione = ec.scegli(info, giorno, oggi)
    if scelta == "prima":
        return nv, {"consolidato": None, "consolidato_verificato": True, "esito": "riferimento_non_valido",
                    "error": f"{norma} è pubblicato in GUUE il {info['data_gu']}: non esisteva il {giorno}"}
    extra = {"consolidato_verificato": True, "avvisi_ue": []}
    if not giorno and (prossima := ec.futura(info, oggi)):
        # A consolidation not applicable yet is said, as Normattiva's coming version is.
        extra["upcoming"] = prossima
        extra["avvisi_ue"].append(ec.avviso_futura(prossima))
    if giorno and info.get("in_vigore_dal") and giorno < info["in_vigore_dal"]:
        extra["avvisi_ue"].append(ec.avviso_non_ancora_in_vigore(giorno, info["in_vigore_dal"]))
    if scelta == "oj":
        return nv, {"consolidato": None, **extra}
    letta = dataclasses.replace(nv, norma=dataclasses.replace(norma, celex_consolidated=versione["celex"]))
    return letta, {"consolidato": {"celex": versione["celex"], "data": versione["data"],
                                   "modificato_da": versione["modifiche"]}, **extra}


async def _pagina_ue(norma: Norma, *, oj: bool = False) -> "tuple[str, str, dict]":
    """``(page, citable URL, extra keys)`` of an EU act: its text in force (``_versione_ue``),
    or with *oj* its Official Journal text. An empty page when it could not be read."""
    nv = NormaVisitata(norma=norma, numero_articolo="", versione="originale" if oj else "")
    nv, ue = await _versione_ue(nv)
    if ue.get("error"):
        return "", nv.norma.url(), ue
    html, url = await _fetch_eurlex_html(nv.norma)
    return html, url or nv.norma.url(), {**ue, "norma": nv.norma}


async def fetch_eurlex_tree(norma: Norma, *, link: bool = False, details: bool = False) -> dict:
    """The article tree, the rubriche and the title of an EU act's text in force (VisuaLex's
    ``_parse_eurlex_tree`` on the same page the articles are read from: one request, kept a day).

    ``{"articles", "count", "metadata": {"rubriche", "title"}, "url", "consolidato",
    "consolidato_verificato"}``, or ``{"error", "url", …}``.
    """
    from . import eurlex_tree

    html, url, ue = await _pagina_ue(norma)
    letta = ue.pop("norma", norma)
    if not html:
        return {"error": ue.get("error") or "Could not fetch EUR-Lex document", "url": url, **ue}
    soup = BeautifulSoup(html, "html.parser")
    articles, count, metadata = eurlex_tree._parse_eurlex_tree(soup, letta.url(), link, details)
    return {"articles": articles, "count": count, "metadata": metadata, "url": url, **ue}


async def fetch_eurlex_recitals(norma: Norma) -> dict:
    """Every recital of an EU act, ``{"recitals": [{"number", "text"}], "url"}``: VisuaLex's
    ``extract_recitals`` on the Official Journal page (a consolidated text has no preamble)."""
    from . import eurlex_text

    html, url, ue = await _pagina_ue(norma, oj=True)
    if not html:
        return {"error": ue.get("error") or "Could not fetch EUR-Lex document", "url": url}
    return {"recitals": eurlex_text.extract_recitals(BeautifulSoup(html, "html.parser")), "url": url}


def senza_export(nv: NormaVisitata) -> bool:
    """Whether the Akoma Ntoso export cannot give the text asked for: the original text.

    The export is a text in force on a day (``dataVigenza``), and the original is not one:
    an act's own day can precede its entry into force (the c.c. is dated 16 March 1942 and
    in force from 21 April), and a code's NormaVisitata has no date at all, so the export
    would be asked at today's date. The original is read from the page (``@originale``) only.
    """
    return (nv.versione or "").strip().lower() == "originale"


def _vigenza_akn(nv: NormaVisitata) -> "str | None":
    """caricaAKN's ``dataVigenza`` for the text asked for: the date, or None (today) for the
    text in force. Never asked for the original text (``senza_export``)."""
    if nv.data_versione:
        return nv.data_versione.replace("-", "")
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

    # A consolidated version: CELLAR serves its sector-0 CELEX with the consolidated markup
    # (Q1: the same bytes for VisuaLex's extractor as the EUR-Lex page).
    celex = norma.celex_consolidated or _build_celex(norma)
    if not celex:
        return "", ""
    return f"{_CELLAR_BASE}{celex}", eurlex_citable_url(celex)


#: An article heading of an EU act's page, in any of its markups: OJ (``oj-ti-art``), consolidated
#: (``title-article-norm``), the ``eli-subdivision`` wrappers, or the legacy class-less page's
#: «<p>Articolo 1</p>» (dir. 2002/58, which carries none of the classes).
_PAGINA_EURLEX = re.compile(r"ti-art|title-article-norm|eli-subdivision|>\s*Articolo\s")


def _pagina_eurlex(html: str) -> bool:
    """Whether *html* is an EU act's page (worth keeping a day), not an empty or error page."""
    return bool(html) and _PAGINA_EURLEX.search(html) is not None


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
    # One page carries the whole act: kept a day, as VisuaLex keeps it (pagine_eurlex).
    kept = pagine_eurlex.leggi(url)
    if kept is not None:
        html, servito = kept
        note_source("eur_lex", servito)
        return html, display_url or servito

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
    if _pagina_eurlex(html):
        # An empty 200, an error page: not kept, so the next call asks again.
        pagine_eurlex.scrivi(url, html, str(resp.url) if hasattr(resp, "url") else url)

    final_url = display_url or (str(resp.url) if hasattr(resp, "url") else url)
    return html, final_url


def _extract_eurlex_article(html: str, article: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    if not article:
        return soup.get_text(separator="\n", strip=True)

    # Recital / considerando — encoded as "rec_N" by _parse_reference
    if article.startswith("rec_"):
        # VisuaLex's reader (``extract_recitals``): the text without its «(N)» and without the
        # footnote calls; cite_law prints «(N)» as the label.
        from . import eurlex_text

        numero = article[4:]
        for recital in eurlex_text.extract_recitals(BeautifulSoup(html, "html.parser")):
            if recital["number"] == numero:
                return recital["text"]
        return f"[Considerando {numero} non trovato nel documento EUR-Lex]"

    annex = split_annex(article)
    if annex:
        return _extract_eurlex_annex(soup, *annex)

    # An article: VisuaLex's extractor, on VisuaLex's parser (its text is frozen). It reads
    # the OJ page and, for a consolidated version, the consolidated markup.
    from . import eurlex_text

    soup = BeautifulSoup(html, "html.parser")
    try:
        text = eurlex_text.extract_article_text(soup, article)
    except eurlex_text.DocumentNotFoundError:
        return f"[Articolo {article} non trovato nel documento EUR-Lex]"
    return text


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
                    "completo": True,
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
            return {"text": first_article_text, "title": title, "url": act_url, "article_count": 1,
                    "completo": False}

        # Fetch all articles via AJAX, preserving order. ``missed`` counts the articles
        # that could not be read: the text is then not the whole act ("completo").
        all_parts: list[str] = []
        missed = 0
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
                    missed += 1
                    continue
                art_soup = BeautifulSoup(art_html, "lxml")
                body = art_soup.find("div", class_="bodyTesto")
                if body:
                    text = _testo_intero(body)
                    if text and text != "[Articolo senza contenuto o abrogato]":
                        all_parts.append(text)
                else:
                    missed += 1
            except httpx.HTTPError:
                missed += 1
                continue

    if not all_parts:
        return {"text": first_article_text, "title": title, "url": act_url, "article_count": 1,
                "completo": False}

    full_text = "\n\n---\n\n".join(all_parts)
    return {"text": full_text, "title": title, "url": act_url, "article_count": len(all_parts),
            "completo": missed == 0}


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
        text = _one_line(h1.get_text(strip=True))
        if text:
            return text
    title_tag = soup.find("title")
    if not title_tag:
        return ""
    return re.sub(r"\s*-\s*Normattiva\s*$", "", _one_line(title_tag.get_text(strip=True))).strip()


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

"""The codice deontologico forense as the Consiglio nazionale forense publishes it, read live.

The CNF's page on the code (``PAGINA_CODICE``) links the PDF of the text in force; the link
changes with every update (``…/NUOVO+CODICE+DEONTOLOGICO+FORENSE++-+agg.+2026.pdf/<uuid>?t=…``),
so it is read from the page each time the code is fetched, never written down here. The PDF
is read by ``parser.analizza``, which refuses a document it does not recognise.

Limits, since the PDF comes from the network: it must be served by the CNF's own host (the
client's host guard, ``core/_http.HOST_PER_FONTE``), weigh at most ``MAX_BYTES`` (the download
stops as soon as it passes them) and be read within ``TIMEOUT_ANALISI`` seconds.

The code read is kept, as articles and not as the PDF:

- in memory, for ``TTL_SECONDI`` (24 h);
- on disk, ``${MCP_CACHE_DIR:-~/.cache/mcp-legal-it}/cnf_codice_deontologico/codice.json.gz``,
  read back for the same 24 h; an expired or unreadable record is deleted when met;
- ``LEGAL_CACHE=off`` (``lib/_cache.py``): nothing is read from or written to disk.

A failed fetch or a refused reading is never kept. An update of the code comes into force
sixty days after its publication in the Gazzetta Ufficiale (art. 3 c. 4 l. 247/2012), so a
day's delay in seeing the CNF's new PDF never serves a text that is no longer in force.
"""

from __future__ import annotations

import asyncio
import gzip
import html as html_lib
import json
import os
import re
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit

import httpx

from mcp_legal_it.core._http import async_client
from mcp_legal_it.lib._cache import cache_enabled, cache_root
from mcp_legal_it.lib._http import note_source, retry_request

from .parser import Articolo, Codice, FormatoNonRiconosciuto, analizza

PAGINA_CODICE = "https://www.consiglionazionaleforense.it/codice-deontologico-forense"
HOST = "www.consiglionazionaleforense.it"
#: The 2026 PDF weighs 0.7 MB.
MAX_BYTES = 10 * 1024 * 1024
TIMEOUT_ANALISI = 30.0
#: The whole download (page and PDF): httpx's timeouts are per operation, and a server that
#: sends a few bytes at a time would hold the stream open for ever.
TEMPO_RETE = 90.0
TTL_SECONDI = 86400
#: How long a failed reading is said again without asking the site: a site down, a PDF refused.
#: Every citation of the code in one verifica_citazioni would otherwise try again, one by one.
RIPROVA_DOPO = {"CnfNonDisponibile": 60.0, "FormatoNonRiconosciuto": 600.0}
#: Raised when the record's shape changes, so records written before are not read.
SCHEMA = 2

_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
#: A link to the code's PDF on the page: «/documents/…/NUOVO+CODICE+DEONTOLOGICO+FORENSE…pdf/…».
_HREF = re.compile(r"""href\s*=\s*["']([^"']+)["']""", re.IGNORECASE)
#: The code's own file: «nuovo codice deontologico forense  - agg. 2026.pdf».
_NOME_PDF = re.compile(r"^(?:nuovo\s+)?codice\s+deontologico\s+forense\b")
_IN_VIGORE = re.compile(r"in vigore dal\s+(\d{1,2}[°º]?\s+\w+\s+\d{4})", re.IGNORECASE)
_DA_ULTIMO = re.compile(r"da ultimo modificato con\s+(delibera[^,;]{5,160}?\d{4})", re.IGNORECASE)


class CnfNonDisponibile(Exception):
    """The CNF's site could not be read (down, slow, or it refused): the code may be fine."""


@dataclass
class Edizione:
    """The code read, and where from."""

    codice: Codice
    pdf_url: str
    #: «7 aprile 2026», when the CNF's page says from when the text is in force.
    in_vigore_dal: str
    #: «delibera del Consiglio Nazionale Forense n. 959 del 23 gennaio 2026», when the page says.
    ultima_modifica: str
    salvato: float


_memoria: Edizione | None = None
#: The last failed reading: (the exception, when).
_rifiuto: "tuple[Exception, float] | None" = None
_lock_memoria = threading.Lock()
#: One download for the calls that arrive together, per event loop (an asyncio.Lock is bound
#: to the loop it first waits in; the library may run several, one after the other).
_lock_lettura: dict[int, asyncio.Lock] = {}


def link_del_pdf(pagina: str) -> str:
    """The URL of the code's PDF linked by the CNF's page; ``FormatoNonRiconosciuto`` when not one.

    The page links two PDFs of the code: the text, and the text with the sanctions' tables
    («… con sanzioni.pdf»). It also links PDFs that only name the code (the Gazzetta's
    communication of an amendment, a CNF circular): a file counts as the code only when its
    name starts with the code's name. Two files that do are a page this function does not
    know, and it says so rather than pick one.
    """
    trovati: list[str] = []
    for href in _HREF.findall(pagina):
        href = html_lib.unescape(href)
        segmenti = unquote(urlsplit(href).path.replace("+", " ")).lower().split("/")
        nome = next((s for s in segmenti if s.endswith(".pdf")), "")
        if not _NOME_PDF.match(nome) or "sanzioni" in nome:
            continue
        url = urljoin(PAGINA_CODICE, href)
        if url not in trovati:
            trovati.append(url)
    if not trovati:
        raise FormatoNonRiconosciuto("la pagina del CNF non collega più il PDF del codice")
    percorsi = {urlsplit(u).path for u in trovati}
    if len(percorsi) > 1:
        raise FormatoNonRiconosciuto(f"la pagina del CNF collega {len(percorsi)} PDF del codice: "
                                     "non è possibile stabilire quale sia il testo vigente")
    url = trovati[0]
    if urlsplit(url).scheme != "https" or urlsplit(url).hostname != HOST:
        raise FormatoNonRiconosciuto(f"il PDF del codice non è sul sito del CNF ({urlsplit(url).hostname})")
    return url


def _dalla_pagina(regex: re.Pattern, pagina: str) -> str:
    testo = re.sub(r"\s+", " ", html_lib.unescape(re.sub(r"<[^>]+>", " ", pagina)))
    m = regex.search(testo)
    return m.group(1).strip() if m else ""


async def _scarica_pdf(client: httpx.AsyncClient, url: str) -> bytes:
    """The PDF at *url*, refused past ``MAX_BYTES`` without reading the rest."""
    async with client.stream("GET", url) as resp:
        resp.raise_for_status()
        dichiarati = resp.headers.get("content-length", "")
        if dichiarati.isdigit() and int(dichiarati) > MAX_BYTES:
            raise FormatoNonRiconosciuto(f"il PDF del CNF pesa {int(dichiarati):,} byte, più del limite")
        dati = bytearray()
        async for blocco in resp.aiter_bytes():
            dati += blocco
            if len(dati) > MAX_BYTES:
                raise FormatoNonRiconosciuto("il PDF del CNF supera il limite di dimensione")
    note_source("cnf", url)
    return bytes(dati)


async def _scarica() -> tuple[str, str, bytes]:
    """``(page, PDF URL, PDF)`` from the CNF's site."""
    async with async_client("cnf", timeout=_TIMEOUT) as client:
        resp = await retry_request(client, "get", PAGINA_CODICE, dataset="cnf")
        pagina = resp.text
        pdf_url = link_del_pdf(pagina)
        return pagina, pdf_url, await _scarica_pdf(client, pdf_url)


async def _leggi_dal_sito() -> Edizione:
    try:
        pagina, pdf_url, dati = await asyncio.wait_for(_scarica(), TEMPO_RETE)
    except (httpx.TransportError, httpx.HTTPStatusError, asyncio.TimeoutError) as exc:
        raise CnfNonDisponibile(f"sito del CNF non raggiungibile ({exc.__class__.__name__})") from exc
    try:
        codice = await asyncio.wait_for(asyncio.to_thread(analizza, dati), TIMEOUT_ANALISI)
    except asyncio.TimeoutError as exc:
        raise FormatoNonRiconosciuto(f"lettura del PDF oltre {TIMEOUT_ANALISI:.0f} secondi") from exc
    return Edizione(codice=codice, pdf_url=pdf_url, in_vigore_dal=_dalla_pagina(_IN_VIGORE, pagina),
                    ultima_modifica=_dalla_pagina(_DA_ULTIMO, pagina), salvato=time.time())


async def edizione() -> Edizione:
    """The code in force as the CNF publishes it: kept, or read from the site.

    Raises ``CnfNonDisponibile`` (the site could not be read) or ``FormatoNonRiconosciuto``
    (it was read, and it is not the code as expected).
    """
    global _rifiuto
    if (tenuta := _tenuta()) is not None:
        return tenuta
    lock = _lock_lettura.setdefault(id(asyncio.get_running_loop()), asyncio.Lock())
    async with lock:
        if (tenuta := _tenuta()) is not None:
            return tenuta
        with _lock_memoria:
            rifiuto = _rifiuto
        if rifiuto is not None and 0 <= time.time() - rifiuto[1] < RIPROVA_DOPO[type(rifiuto[0]).__name__]:
            raise type(rifiuto[0])(str(rifiuto[0]))  # the calls waiting behind a failure share it
        try:
            letta = await _leggi_dal_sito()
        except (CnfNonDisponibile, FormatoNonRiconosciuto) as exc:
            with _lock_memoria:
                _rifiuto = (exc, time.time())
            raise
        with _lock_memoria:
            _rifiuto = None
        _ricorda(letta)
        _scrivi(letta)
        return letta


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

def _dir() -> Path:
    return cache_root() / "cnf_codice_deontologico"


def _path() -> Path:
    return _dir() / "codice.json.gz"


def _ricorda(e: Edizione) -> None:
    global _memoria
    with _lock_memoria:
        _memoria = e


def _tenuta() -> Edizione | None:
    adesso = time.time()
    with _lock_memoria:
        if _memoria is not None and 0 <= adesso - _memoria.salvato < TTL_SECONDI:
            return _memoria
    if not cache_enabled():
        return None
    path = _path()
    try:
        rec = json.loads(gzip.decompress(path.read_bytes()).decode("utf-8"))
        e = _da_record(rec)
    except FileNotFoundError:
        return None
    except Exception:  # noqa: BLE001 - a damaged record (zlib.error, bad JSON…) is dropped, never fatal
        e = None
    if e is None or not 0 <= adesso - e.salvato < TTL_SECONDI:
        try:
            path.unlink()
        except OSError:
            pass
        return None
    _ricorda(e)
    return e


def _da_record(rec) -> Edizione | None:
    if not isinstance(rec, dict) or rec.get("schema") != SCHEMA:
        return None
    articoli = {}
    for a in rec["articoli"]:
        art = Articolo(numero=str(a["numero"]), rubrica=str(a["rubrica"]),
                       paragrafi=[str(p) for p in a["paragrafi"]],
                       note=[{"numero": str(n["numero"]), "testo": str(n["testo"])} for n in a["note"]],
                       segni_rubrica=[str(n) for n in a["segni_rubrica"]])
        articoli[art.numero] = art
    if not articoli:
        return None
    return Edizione(codice=Codice(titolo=str(rec["titolo"]), articoli=articoli), pdf_url=str(rec["pdf_url"]),
                    in_vigore_dal=str(rec["in_vigore_dal"]), ultima_modifica=str(rec["ultima_modifica"]),
                    salvato=float(rec["salvato"]))


def _scrivi(e: Edizione) -> None:
    """Keep the code read (best effort: an unwritable directory only warns)."""
    if not cache_enabled():
        return
    rec = {"schema": SCHEMA, "salvato": e.salvato, "pdf_url": e.pdf_url, "titolo": e.codice.titolo,
           "in_vigore_dal": e.in_vigore_dal, "ultima_modifica": e.ultima_modifica,
           "articoli": [{"numero": a.numero, "rubrica": a.rubrica, "paragrafi": a.paragrafi, "note": a.note,
                         "segni_rubrica": a.segni_rubrica} for a in e.codice.articoli.values()]}
    try:
        cartella = _dir()
        cartella.mkdir(parents=True, exist_ok=True)
        path = _path()
        tmp = path.with_name(f"{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
        tmp.write_bytes(gzip.compress(json.dumps(rec, ensure_ascii=False).encode("utf-8")))
        os.replace(tmp, path)
    except OSError as exc:
        print(f"mcp-legal-it: cache del codice deontologico non scrivibile ({exc})", file=sys.stderr)


def svuota_memoria() -> None:
    """Forget the code kept in memory (tests)."""
    global _memoria, _rifiuto
    with _lock_memoria:
        _memoria = None
        _rifiuto = None
    _lock_lettura.clear()


# ---------------------------------------------------------------------------
# One article, in the readers' shape
# ---------------------------------------------------------------------------

#: What the reader is told about every article served from the CNF's PDF.
AVVISO_FONTE = ("testo consolidato pubblicato dal Consiglio nazionale forense: fanno fede le delibere "
                "pubblicate nella Gazzetta Ufficiale (art. 3, comma 4, l. 247/2012)")


def avvisi_edizione(e: Edizione) -> list[str]:
    """The notices of an article served from *e*: what the text is, and the edition's dates."""
    edizione = AVVISO_FONTE
    dettagli = [d for d in (f"in vigore dal {e.in_vigore_dal}" if e.in_vigore_dal else "",
                            f"da ultimo modificato con {e.ultima_modifica}" if e.ultima_modifica else "") if d]
    if dettagli:
        edizione += " (" + "; ".join(dettagli) + ")"
    return [edizione]


async def fetch_articolo(numero: str) -> dict:
    """The article *numero* of the code: ``{text, url, source, note_aggiornamento, avvisi_cnf}``.

    The readers' shape (``visualex.scraper.fetch_article``): ``error`` with ``esito``
    ``articolo_non_trovato`` for an article the code does not have, and
    ``verifica_non_disponibile`` when the CNF's site or PDF could not be read; never raises.
    """
    from mcp_legal_it.lib.visualex.scraper import ARTICLE_NOT_FOUND, CHECK_UNAVAILABLE

    vuoto = {"text": "", "url": PAGINA_CODICE, "source": "cnf"}
    try:
        e = await edizione()
    except CnfNonDisponibile as exc:
        return {**vuoto, "esito": CHECK_UNAVAILABLE, "error": f"codice deontologico forense: {exc}"}
    except FormatoNonRiconosciuto as exc:
        return {**vuoto, "esito": CHECK_UNAVAILABLE,
                "error": ("codice deontologico forense: il PDF pubblicato dal CNF non è nel formato atteso "
                          f"({exc}); nessun testo servito, verificare su {PAGINA_CODICE}")}
    except Exception as exc:  # noqa: BLE001 - never raises: a reading that failed is said, not thrown
        return {**vuoto, "esito": CHECK_UNAVAILABLE,
                "error": f"codice deontologico forense: lettura non riuscita ({exc.__class__.__name__})"}
    art = e.codice.articolo(numero)
    if art is None:
        return {**vuoto, "url": e.pdf_url, "esito": ARTICLE_NOT_FOUND,
                "error": f"articolo {numero} non trovato nel codice deontologico forense"}
    note = [{"numero": n["numero"], "testo": n["testo"], "ordine": i, "corte_costituzionale": False}
            for i, n in enumerate(art.note, 1)]
    return {"text": art.testo(), "url": e.pdf_url, "source": "cnf", "note_aggiornamento": note,
            "avvisi_cnf": avvisi_edizione(e)}

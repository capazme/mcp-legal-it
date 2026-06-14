"""Network layer for fetching Akoma Ntoso XML from Normattiva (caricaAKN).

Two-request flow (required — see ``tests/fixtures/akn/STRUCTURE.md``):

1. GET the act landing page (``norma.url()`` with no article) on a fresh client.
   This establishes the act-specific session cookie **and** yields the export
   params (``codiceRedaz`` + ``dataGU``) from the ``caricaAKN`` href / ELI meta.
2. GET ``caricaAKN?dataGU=&codiceRedaz=&dataVigenza=`` on the **same** client.
   A cold/generic session returns a ~32 KB HTML error page instead of XML.

The parsed act is cached: an in-memory LRU keyed by
``(codiceRedaz, dataGU, dataVigenza)`` plus optional best-effort on-disk JSON
persistence under ``${MCP_CACHE_DIR or ~/.cache/mcp-legal-it}/akn_acts/``.
``dataVigenza`` defaults to today, giving natural daily expiry.

Any failure (no params, HTTP error, non-XML response, parser exception) returns
``None`` so the caller can fall back to the HTML scraping path.
"""

import json
import os
import re
import sys
from collections import OrderedDict
from datetime import date
from pathlib import Path

import httpx

from .akn_parser import ParsedAct, parse_akn

_CARICA_AKN_BASE = "https://www.normattiva.it/do/atto/caricaAKN"

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://www.normattiva.it/",
}

_TIMEOUT = httpx.Timeout(60.0, connect=15.0)

# The cold error page is exactly 32254 bytes; require a comfortable margin below
# the smallest real export (legge_241 ≈ 250 KB) to reject error pages.
_MIN_XML_BYTES = 40000

# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

_CACHE_MAX = max(1, int(os.environ.get("AKN_CACHE_MAX_ACTS", "50") or "50"))

# In-memory LRU: most-recently-used key is moved to the end.
_lru: "OrderedDict[tuple[str, str, str], ParsedAct]" = OrderedDict()


def _cache_root() -> Path:
    base = os.environ.get("MCP_CACHE_DIR") or (Path.home() / ".cache" / "mcp-legal-it")
    return Path(base) / "akn_acts"


def _hits_path() -> Path:
    return _cache_root() / "akn_hits.json"


# URL -> export params index. A warm cache hit can resolve (codice, dataGU) from
# the act URL alone and skip the landing-page round-trip entirely (no session is
# needed when we answer from cache without calling caricaAKN). (codice, dataGU)
# are the GU publication identifiers — stable forever for a given act.
_url_params: "dict[str, tuple[str, str]]" = {}
_url_params_loaded = False


def _url_params_path() -> Path:
    return _cache_root() / "akn_url_params.json"


def _load_url_params() -> None:
    global _url_params_loaded
    if _url_params_loaded:
        return
    _url_params_loaded = True
    try:
        path = _url_params_path()
        if path.exists():
            raw = json.loads(path.read_text(encoding="utf-8"))
            for url, val in raw.items():
                if isinstance(val, list) and len(val) == 2:
                    _url_params[url] = (val[0], val[1])
    except (ValueError, OSError) as exc:
        print(f"[akn_fetch] url-params read failed: {exc}", file=sys.stderr)


def _get_url_params(url: str) -> "tuple[str, str] | None":
    _load_url_params()
    return _url_params.get(url)


def _set_url_params(url: str, codice: str, data_gu: str) -> None:
    _load_url_params()
    if _url_params.get(url) == (codice, data_gu):
        return
    _url_params[url] = (codice, data_gu)
    try:
        path = _url_params_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({u: list(v) for u, v in _url_params.items()}, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError as exc:
        print(f"[akn_fetch] url-params write failed: {exc}", file=sys.stderr)


def _disk_path(key: tuple[str, str, str]) -> Path:
    codice, data_gu, data_vigenza = key
    fname = f"{codice}_{data_gu}_{data_vigenza}.json"
    return _cache_root() / fname


def _bump_hits(key: tuple[str, str, str]) -> None:
    """Increment the persisted access counter for a key (best-effort)."""
    try:
        path = _hits_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        hits: dict = {}
        if path.exists():
            try:
                hits = json.loads(path.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                hits = {}
        hit_key = "|".join(key)
        hits[hit_key] = int(hits.get(hit_key, 0)) + 1
        path.write_text(json.dumps(hits, ensure_ascii=False), encoding="utf-8")
    except OSError as exc:
        print(f"[akn_fetch] hit-counter write failed: {exc}", file=sys.stderr)


def _act_to_dict(act: ParsedAct) -> dict:
    return {
        "title": act.title,
        "articles": act.articles,
        "order": act.order,
        "structure": act.structure,
    }


def _act_from_dict(data: dict) -> ParsedAct:
    return ParsedAct(
        title=data.get("title", ""),
        articles=dict(data.get("articles", {})),
        order=list(data.get("order", [])),
        structure=data.get("structure", "flat"),
    )


def _disk_load(key: tuple[str, str, str]) -> "ParsedAct | None":
    try:
        path = _disk_path(key)
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return _act_from_dict(data)
    except (ValueError, OSError) as exc:
        print(f"[akn_fetch] disk read failed: {exc}", file=sys.stderr)
        return None


def _disk_store(key: tuple[str, str, str], act: ParsedAct) -> None:
    try:
        path = _disk_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(_act_to_dict(act), ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError as exc:
        print(f"[akn_fetch] disk write failed: {exc}", file=sys.stderr)


def _lru_get(key: tuple[str, str, str]) -> "ParsedAct | None":
    act = _lru.get(key)
    if act is not None:
        _lru.move_to_end(key)
    return act


def _lru_put(key: tuple[str, str, str], act: ParsedAct) -> None:
    _lru[key] = act
    _lru.move_to_end(key)
    while len(_lru) > _CACHE_MAX:
        _lru.popitem(last=False)


def _cache_lookup(key: tuple[str, str, str]) -> "ParsedAct | None":
    """Look up a parsed act in memory, then on disk (promoting disk hits to LRU)."""
    cached = _lru_get(key)
    if cached is None:
        cached = _disk_load(key)
        if cached is not None:
            _lru_put(key, cached)
    return cached


def clear_akn_cache(disk: bool = False) -> None:
    """Clear the in-memory caches; optionally wipe the on-disk parsed-act cache."""
    global _url_params_loaded
    _lru.clear()
    _url_params.clear()
    _url_params_loaded = False
    if disk:
        root = _cache_root()
        if root.exists():
            for child in root.glob("*.json"):
                try:
                    child.unlink()
                except OSError as exc:
                    print(f"[akn_fetch] disk clear failed: {exc}", file=sys.stderr)


def _akn_cache_stats() -> dict:
    """Return cache diagnostics for tests/introspection."""
    _load_url_params()
    return {
        "memory_entries": len(_lru),
        "memory_keys": list(_lru.keys()),
        "max_acts": _CACHE_MAX,
        "disk_dir": str(_cache_root()),
        "url_params_known": len(_url_params),
    }


# ---------------------------------------------------------------------------
# Param extraction
# ---------------------------------------------------------------------------

_AKN_HREF_RE = re.compile(
    r"caricaAKN\?dataGU=(?P<dataGU>\d{8})&(?:amp;)?codiceRedaz=(?P<codice>[A-Z0-9]+)",
    re.IGNORECASE,
)
_ELI_LOCAL_RE = re.compile(
    r'eli:id_local"\s+content="(?P<codice>[A-Z0-9]+)"',
    re.IGNORECASE,
)
_DATA_PUB_RE = re.compile(r"dataPubblicazioneGazzetta=(\d{4})-(\d{2})-(\d{2})")
_CODICE_REDAZ_RE = re.compile(r"codiceRedaz(?:ionale)?=(?P<codice>[A-Z0-9]+)", re.IGNORECASE)


def _extract_params(html: str) -> "tuple[str, str] | None":
    """Extract ``(codiceRedaz, dataGU)`` from a landing page.

    Primary source: the ``caricaAKN`` href (has both params). Fallback:
    ``eli:id_local`` meta for the code + ``dataPubblicazioneGazzetta`` for the GU.
    Returns ``None`` if either param cannot be resolved.
    """
    m = _AKN_HREF_RE.search(html)
    if m:
        return m.group("codice"), m.group("dataGU")

    codice = ""
    eli = _ELI_LOCAL_RE.search(html)
    if eli:
        codice = eli.group("codice")
    else:
        redaz = _CODICE_REDAZ_RE.search(html)
        if redaz:
            codice = redaz.group("codice")

    data_gu = ""
    pub = _DATA_PUB_RE.search(html)
    if pub:
        data_gu = f"{pub.group(1)}{pub.group(2)}{pub.group(3)}"

    if codice and data_gu:
        return codice, data_gu
    return None


# ---------------------------------------------------------------------------
# Fetch
# ---------------------------------------------------------------------------

def _today_vigenza() -> str:
    return date.today().strftime("%Y%m%d")


async def fetch_act_akn(norma, data_vigenza: "str | None" = None) -> "ParsedAct | None":
    """Fetch and parse the whole-act AKN XML for ``norma``.

    ``norma`` is a :class:`src.lib.visualex.models.Norma`. Returns a
    :class:`ParsedAct` on success, or ``None`` on any failure (the caller then
    falls back to the HTML path). Cache lookup (memory → disk) happens before any
    network request.
    """
    try:
        landing_url = norma.url()
    except Exception as exc:  # noqa: BLE001 — never raise to the caller
        print(f"[akn_fetch] url() failed: {exc}", file=sys.stderr)
        return None
    if not landing_url:
        return None

    if data_vigenza is None:
        data_vigenza = _today_vigenza()

    # Fast path: params already known for this act → resolve the cache key and
    # answer from cache WITHOUT any network (no landing page, no session needed).
    known = _get_url_params(landing_url)
    if known is not None:
        codice, data_gu = known
        cached = _cache_lookup((codice, data_gu, data_vigenza))
        if cached is not None:
            _bump_hits((codice, data_gu, data_vigenza))
            return cached

    try:
        async with httpx.AsyncClient(
            headers=_HEADERS,
            timeout=_TIMEOUT,
            follow_redirects=True,
        ) as client:
            # Step 1 — landing page: establishes the session + yields params.
            landing_resp = await client.get(landing_url)
            landing_resp.raise_for_status()
            params = _extract_params(landing_resp.text)
            if not params:
                return None
            codice, data_gu = params
            _set_url_params(landing_url, codice, data_gu)

            key = (codice, data_gu, data_vigenza)

            # Cache lookup AFTER params are known (the params are part of the key).
            cached = _cache_lookup(key)
            if cached is not None:
                _bump_hits(key)
                return cached

            # Step 2 — caricaAKN on the same client (session reused).
            akn_url = (
                f"{_CARICA_AKN_BASE}?dataGU={data_gu}"
                f"&codiceRedaz={codice}&dataVigenza={data_vigenza}"
            )
            akn_resp = await client.get(akn_url)
            akn_resp.raise_for_status()
            xml = akn_resp.text

        # Validate: real XML export, not the ~32 KB error page.
        if not xml.lstrip().startswith("<?xml"):
            return None
        if len(xml) < _MIN_XML_BYTES:
            return None

        act = parse_akn(xml)
        if not act.article_count:
            return None

        _lru_put(key, act)
        _disk_store(key, act)
        _bump_hits(key)
        return act
    except Exception as exc:  # noqa: BLE001 — fail closed, never raise
        print(f"[akn_fetch] fetch failed for {landing_url}: {exc}", file=sys.stderr)
        return None

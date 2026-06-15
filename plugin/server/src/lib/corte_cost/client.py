"""Client for Corte Costituzionale (Italian Constitutional Court) case law.

Data source: dati.cortecostituzionale.it open-data ONLY.
The main www.cortecostituzionale.it site is Radware-protected — never touch it.

MODEL — download-and-parse with cache (deliberate departure from the live
scrapers, documented & approved in the roadmap). The court publishes bulk
JSON dumps per decade; each decade ZIP NESTS one ZIP per year, and the JSON
inside is latin-1 (ISO-8859-1) encoded.

Layout
------
Pronunce (decisions):
    .../pronunce/P_json{decade}.zip
      -> Cc_Opendata_Pronunce_{year}_json.zip   (nested ZIP, lowercase 'pendata')
        -> Cc_Opendata_Pronunce_{year}.json     -> {"elenco_pronunce": [ {...}, ... ]}

Massime (headnotes — invoked norms live here, NOT in the pronunce dump):
    .../massime/CC_M_{range}_json.zip
      -> Cc_OpenData_Massime_{year}_json.zip     (nested ZIP, capital 'D')
        -> Cc_OpenData_Massime_{year}.json
            -> {"corte_costituzionale_archiviomassime": [ {massime:[{parametri:[...]}]}, ... ]}

Upstream casing is inconsistent ('Cc_Opendata_Pronunce_*' vs
'Cc_OpenData_Massime_*') — the exact filenames are hardcoded as constants
below, NEVER derived.

Cache: (MCP_CACHE_DIR or ~/.cache/mcp-legal-it)/corte_cost/{kind}/{year}.json,
7-day TTL. On a miss the relevant DECADE bundle is downloaded once, every
nested year ZIP is unzipped in-memory, latin-1-decoded, and written to the
per-year cache. Downloads are lazy per decade.
"""

import io
import json
import os
import re
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from src.lib._http import retry_request

_BASE = "https://dati.cortecostituzionale.it/opendata/distribuzione"
_PRONUNCE_BASE = f"{_BASE}/pronunce"
_MASSIME_BASE = f"{_BASE}/massime"

# Files are large; allow generous timeouts.
_TIMEOUT = httpx.Timeout(60.0, connect=20.0)
_MAX_TEXT_LENGTH = 25000
_CACHE_TTL_SECONDS = 7 * 24 * 3600

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/zip,*/*",
    "Accept-Language": "it-IT,it;q=0.9",
}

# --- Decade bundle filenames (HARDCODED — casing differs upstream) ----------
# Pronunce decade ranges and their bundle filenames.
_PRONUNCE_DECADES: list[tuple[int, int, str]] = [
    (1956, 1980, "P_json1956_1980.zip"),
    (1981, 2000, "P_json1981_2000.zip"),
    (2001, 9999, "P_json2001_oggi.zip"),
]
# Massime decade ranges and their bundle filenames (different upper bound:
# 2001_2015, not 2001_oggi).
_MASSIME_DECADES: list[tuple[int, int, str]] = [
    (1956, 1980, "CC_M_1956_1980_json.zip"),
    (1981, 2000, "CC_M_1981_2000_json.zip"),
    (2001, 9999, "CC_M_2001_2015_json.zip"),
]

# Nested per-year ZIP / JSON filename templates (casing differs between kinds).
_PRONUNCE_YEAR_ZIP = "Cc_Opendata_Pronunce_{year}_json.zip"
_PRONUNCE_YEAR_JSON = "Cc_Opendata_Pronunce_{year}.json"
_MASSIME_YEAR_ZIP = "Cc_OpenData_Massime_{year}_json.zip"
_MASSIME_YEAR_JSON = "Cc_OpenData_Massime_{year}.json"

# JSON root keys.
_PRONUNCE_ROOT_KEY = "elenco_pronunce"
_MASSIME_ROOT_KEY = "corte_costituzionale_archiviomassime"

TIPOLOGIE: dict[str, str] = {
    "sentenza": "S",
    "ordinanza": "O",
    "tutte": "",
}


@dataclass
class ParametroNorma:
    """A norm invoked as a parameter of constitutionality in a massima."""

    descrizione: str = ""   # e.g. "legge", "decreto legislativo"
    numero: str = ""        # act number, e.g. "87"
    data: str = ""          # act date DD/MM/YYYY
    articolo: str = ""      # article, e.g. "23"
    comma: str = ""
    specificazione_articolo: str = ""
    specificazione_comma: str = ""


@dataclass
class MassimaCost:
    """A headnote (massima) attached to a pronuncia."""

    titolo: str = ""
    numero: str = ""
    testo: str = ""
    parametri: list[ParametroNorma] = field(default_factory=list)


@dataclass
class PronunciaCost:
    """A Constitutional Court decision."""

    numero_pronuncia: str
    anno_pronuncia: str
    data_decisione: str = ""
    data_deposito: str = ""
    ecli: str = ""
    tipologia_pronuncia: str = ""  # "S" = sentenza, "O" = ordinanza
    epigrafe: str = ""
    testo: str = ""
    dispositivo: str = ""
    collegio: str = ""
    presidente: str = ""
    relatore_pronuncia: str = ""
    redattore_pronuncia: str = ""


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

def _cache_root() -> Path:
    base = os.environ.get("MCP_CACHE_DIR")
    root = Path(base) if base else Path.home() / ".cache" / "mcp-legal-it"
    return root / "corte_cost"


def _cache_path(kind: str, year: int) -> Path:
    return _cache_root() / kind / f"{year}.json"


def _cache_fresh(path: Path) -> bool:
    if not path.exists():
        return False
    return (time.time() - path.stat().st_mtime) < _CACHE_TTL_SECONDS


def _read_cache(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _write_cache(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(records, fh, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Decade resolution / download / unzip
# ---------------------------------------------------------------------------

def _decade_for_year(year: int, decades: list[tuple[int, int, str]]) -> str | None:
    for lo, hi, fname in decades:
        if lo <= year <= hi:
            return fname
    return None


async def _download(url: str) -> bytes:
    async with httpx.AsyncClient(
        timeout=_TIMEOUT, headers=_HEADERS, follow_redirects=True
    ) as client:
        resp = await retry_request(client, "GET", url)
        return resp.content


def _unzip_decade(
    bundle_bytes: bytes,
    year_zip_tmpl: str,
    year_json_tmpl: str,
    root_key: str,
) -> dict[int, list[dict]]:
    """Unzip a decade bundle (two nested levels) into {year: [records]}.

    The outer ZIP holds one ZIP per year; each inner ZIP holds one JSON file.
    JSON is latin-1 encoded. Returns a mapping of year -> list of records
    (extracted from the JSON root_key).
    """
    out: dict[int, list[dict]] = {}
    outer = zipfile.ZipFile(io.BytesIO(bundle_bytes))
    for entry in outer.namelist():
        m = re.search(r"(\d{4})", entry)
        if not m:
            continue
        year = int(m.group(1))
        inner_bytes = outer.read(entry)
        if inner_bytes[:2] != b"PK":
            continue
        inner = zipfile.ZipFile(io.BytesIO(inner_bytes))
        json_name = year_json_tmpl.format(year=year)
        names = inner.namelist()
        target = json_name if json_name in names else (names[0] if names else None)
        if not target:
            continue
        raw = inner.read(target).decode("latin-1")
        obj = json.loads(raw)
        records = obj.get(root_key, []) if isinstance(obj, dict) else obj
        out[year] = records if isinstance(records, list) else []
    return out


async def _load_year(
    kind: str,
    year: int,
    base_url: str,
    decades: list[tuple[int, int, str]],
    year_zip_tmpl: str,
    year_json_tmpl: str,
    root_key: str,
) -> list[dict]:
    """Return raw records for a year, populating the per-year cache lazily.

    On a cache miss, the whole decade bundle is downloaded once and every
    year it contains is written to cache; only the requested year is returned.
    """
    path = _cache_path(kind, year)
    if _cache_fresh(path):
        return _read_cache(path)

    bundle = _decade_for_year(year, decades)
    if not bundle:
        return []

    bundle_bytes = await _download(f"{base_url}/{bundle}")
    by_year = _unzip_decade(bundle_bytes, year_zip_tmpl, year_json_tmpl, root_key)
    for yr, records in by_year.items():
        _write_cache(_cache_path(kind, yr), records)

    return by_year.get(year, [])


async def load_pronunce_year(year: int) -> list[PronunciaCost]:
    """Load all pronunce for a given year (cached)."""
    raw = await _load_year(
        kind="pronunce",
        year=year,
        base_url=_PRONUNCE_BASE,
        decades=_PRONUNCE_DECADES,
        year_zip_tmpl=_PRONUNCE_YEAR_ZIP,
        year_json_tmpl=_PRONUNCE_YEAR_JSON,
        root_key=_PRONUNCE_ROOT_KEY,
    )
    return [_parse_pronuncia(r) for r in raw]


async def load_massime_year(year: int) -> list[dict]:
    """Load all massime entries (per-pronuncia) for a given year (cached).

    Each entry mirrors the upstream shape: numero_pronuncia / anno_pronuncia /
    tipologia_pronuncia plus a nested ``massime`` list.
    """
    return await _load_year(
        kind="massime",
        year=year,
        base_url=_MASSIME_BASE,
        decades=_MASSIME_DECADES,
        year_zip_tmpl=_MASSIME_YEAR_ZIP,
        year_json_tmpl=_MASSIME_YEAR_JSON,
        root_key=_MASSIME_ROOT_KEY,
    )


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def _clean(text: str) -> str:
    """Normalise upstream text artefacts (CR, &#13; entities, runs of space)."""
    if not text:
        return ""
    text = text.replace("&#13;", "\n").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _parse_pronuncia(rec: dict) -> PronunciaCost:
    return PronunciaCost(
        numero_pronuncia=str(rec.get("numero_pronuncia", "")).strip(),
        anno_pronuncia=str(rec.get("anno_pronuncia", "")).strip(),
        data_decisione=str(rec.get("data_decisione", "")).strip(),
        data_deposito=str(rec.get("data_deposito", "")).strip(),
        ecli=str(rec.get("ecli", "")).strip(),
        tipologia_pronuncia=str(rec.get("tipologia_pronuncia", "")).strip(),
        epigrafe=_clean(rec.get("epigrafe", "")),
        testo=_clean(rec.get("testo", "")),
        dispositivo=_clean(rec.get("dispositivo", "")),
        collegio=_clean(rec.get("collegio", "")),
        presidente=str(rec.get("presidente", "")).strip(),
        relatore_pronuncia=str(rec.get("relatore_pronuncia", "")).strip(),
        redattore_pronuncia=str(rec.get("redattore_pronuncia", "")).strip(),
    )


def _parse_parametro(rec: dict) -> ParametroNorma:
    return ParametroNorma(
        descrizione=str(rec.get("descrizione", "")).strip(),
        numero=str(rec.get("numero", "")).strip(),
        data=str(rec.get("data", "")).strip(),
        articolo=str(rec.get("articolo", "")).strip(),
        comma=str(rec.get("comma", "")).strip(),
        specificazione_articolo=str(rec.get("specificazione_articolo", "")).strip(),
        specificazione_comma=str(rec.get("specificazione_comma", "")).strip(),
    )


def _parse_massima(rec: dict) -> MassimaCost:
    return MassimaCost(
        titolo=_clean(rec.get("titolo", "")),
        numero=str(rec.get("numero", "")).strip(),
        testo=_clean(rec.get("testo", "")),
        parametri=[_parse_parametro(p) for p in (rec.get("parametri") or [])],
    )


# ---------------------------------------------------------------------------
# Search / fetch (operate over the cached/decoded records)
# ---------------------------------------------------------------------------

def _matches_tipo(p: PronunciaCost, tipo_code: str) -> bool:
    if not tipo_code:
        return True
    return p.tipologia_pronuncia.upper() == tipo_code.upper()


def _matches_query(p: PronunciaCost, terms: list[str]) -> bool:
    if not terms:
        return True
    haystack = f"{p.epigrafe}\n{p.testo}\n{p.dispositivo}".lower()
    return all(term in haystack for term in terms)


def _dep_sort_key(p: PronunciaCost) -> tuple:
    """Sort key by deposit date (DD/MM/YYYY) then numero, descending-friendly."""
    parts = p.data_deposito.split("/")
    if len(parts) == 3:
        d, m, y = parts
        try:
            iso = (int(y), int(m), int(d))
        except ValueError:
            iso = (0, 0, 0)
    else:
        iso = (0, 0, 0)
    try:
        num = int(p.numero_pronuncia)
    except ValueError:
        num = 0
    return (iso, num)


async def search_pronunce(
    terms: list[str],
    tipo_code: str = "",
    year_from: int = 0,
    year_to: int = 0,
    limit: int = 10,
    current_year: int = 0,
) -> list[PronunciaCost]:
    """Full-text search across cached pronunce in a year range.

    When no range is given, only the current year is scanned (cheap default).
    """
    if year_from <= 0 and year_to <= 0:
        yr = current_year or 0
        years = [yr] if yr else []
    else:
        lo = year_from or year_to
        hi = year_to or year_from
        years = list(range(min(lo, hi), max(lo, hi) + 1))

    matches: list[PronunciaCost] = []
    for year in sorted(years, reverse=True):
        pronunce = await load_pronunce_year(year)
        for p in pronunce:
            if _matches_tipo(p, tipo_code) and _matches_query(p, terms):
                matches.append(p)

    matches.sort(key=_dep_sort_key, reverse=True)
    return matches[:limit]


async def fetch_pronuncia(numero: int, anno: int) -> PronunciaCost | None:
    """Fetch a single pronuncia by number and year."""
    pronunce = await load_pronunce_year(anno)
    target = str(numero)
    for p in pronunce:
        if p.numero_pronuncia == target:
            return p
    return None


def _parse_riferimento(riferimento: str) -> tuple[str, str]:
    """Parse a norm reference into (articolo, atto_number).

    Examples:
        "art. 23 legge 87/1953"  -> ("23", "87")
        "articolo 3"             -> ("3", "")
        "art. 117"               -> ("117", "")
    """
    art = ""
    atto = ""
    m_art = re.search(r"art(?:icolo|\.)?\s*(\d+)", riferimento, re.IGNORECASE)
    if m_art:
        art = m_art.group(1)
    m_num = re.search(r"n(?:umero|\.)?\s*(\d+)", riferimento, re.IGNORECASE)
    if m_num:
        atto = m_num.group(1)
    else:
        # "legge 87/1953" or bare "87/1953"
        m_slash = re.search(r"(\d+)\s*/\s*\d{4}", riferimento)
        if m_slash:
            atto = m_slash.group(1)
    return art, atto


def _parametro_matches(param: ParametroNorma, articolo: str, atto: str) -> bool:
    if articolo and param.articolo != articolo:
        return False
    if atto and param.numero != atto:
        return False
    return articolo != "" or atto != ""


async def pronunce_su_norma(
    riferimento: str,
    year_from: int,
    year_to: int,
    limit: int = 10,
) -> list[tuple[str, str, MassimaCost]]:
    """Find pronunce whose massime invoke a given norm as a parameter.

    Returns a list of (numero_pronuncia, anno_pronuncia, MassimaCost) tuples.
    Scans the massime distribution (capped to massime data range upper bound).
    """
    articolo, atto = _parse_riferimento(riferimento)
    if not articolo and not atto:
        return []

    lo = year_from or year_to or 1956
    hi = year_to or year_from or 2015
    years = list(range(min(lo, hi), max(lo, hi) + 1))

    hits: list[tuple[str, str, MassimaCost]] = []
    for year in sorted(years, reverse=True):
        entries = await load_massime_year(year)
        for entry in entries:
            num = str(entry.get("numero_pronuncia", "")).strip()
            anno = str(entry.get("anno_pronuncia", "")).strip()
            for raw_m in (entry.get("massime") or []):
                massima = _parse_massima(raw_m)
                if any(_parametro_matches(p, articolo, atto) for p in massima.parametri):
                    hits.append((num, anno, massima))
                    if len(hits) >= limit:
                        return hits
    return hits


async def ultime_pronunce(
    tipo_code: str,
    current_year: int,
    limit: int = 10,
) -> list[PronunciaCost]:
    """Latest pronunce by deposit date from the current year's decade."""
    pronunce = await load_pronunce_year(current_year)
    filtered = [p for p in pronunce if _matches_tipo(p, tipo_code)]
    filtered.sort(key=_dep_sort_key, reverse=True)
    return filtered[:limit]


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

def _tipo_label(code: str) -> str:
    return {"S": "Sentenza", "O": "Ordinanza"}.get(code.upper(), code or "Pronuncia")


def format_result(p: PronunciaCost) -> str:
    label = _tipo_label(p.tipologia_pronuncia)
    lines = [f"### {label} n. {p.numero_pronuncia}/{p.anno_pronuncia}"]
    if p.ecli:
        lines.append(f"**ECLI**: {p.ecli}")
    if p.data_deposito:
        lines.append(f"**Deposito**: {p.data_deposito}")
    if p.data_decisione:
        lines.append(f"**Decisione**: {p.data_decisione}")
    if p.presidente:
        lines.append(f"**Presidente**: {p.presidente}")
    if p.relatore_pronuncia:
        lines.append(f"**Relatore**: {p.relatore_pronuncia}")
    if p.epigrafe:
        lines.append(f"**Oggetto**: {p.epigrafe[:300]}")
    return "\n".join(lines)


def format_full(p: PronunciaCost) -> str:
    label = _tipo_label(p.tipologia_pronuncia)
    lines = [f"# {label} Corte Costituzionale n. {p.numero_pronuncia}/{p.anno_pronuncia}"]
    if p.ecli:
        lines.append(f"**ECLI**: {p.ecli}")
    if p.data_decisione:
        lines.append(f"**Decisione**: {p.data_decisione}")
    if p.data_deposito:
        lines.append(f"**Deposito**: {p.data_deposito}")
    if p.presidente:
        lines.append(f"**Presidente**: {p.presidente}")
    if p.relatore_pronuncia:
        lines.append(f"**Relatore**: {p.relatore_pronuncia}")
    lines.append("")

    body_parts = []
    if p.epigrafe:
        body_parts.append(f"## Epigrafe\n{p.epigrafe}")
    if p.testo:
        body_parts.append(f"## Testo\n{p.testo}")
    if p.dispositivo:
        body_parts.append(f"## Dispositivo\n{p.dispositivo}")
    body = "\n\n".join(body_parts)

    truncated = len(body) > _MAX_TEXT_LENGTH
    if truncated:
        body = body[:_MAX_TEXT_LENGTH]
    lines.append(body)
    if truncated:
        lines.append(
            f"\n---\n*[Testo troncato a {_MAX_TEXT_LENGTH} caratteri]*"
        )
    return "\n".join(lines)


def _format_parametro(param: ParametroNorma) -> str:
    bits = []
    if param.descrizione:
        bits.append(param.descrizione)
    if param.numero:
        bits.append(f"n. {param.numero}")
    if param.data:
        bits.append(f"del {param.data}")
    if param.articolo:
        art = f"art. {param.articolo}"
        if param.comma:
            art += f", c. {param.comma}"
        bits.append(art)
    return " ".join(bits)


def format_massima_hit(numero: str, anno: str, massima: MassimaCost) -> str:
    label = "Massima"
    lines = [f"### {label} (pronuncia n. {numero}/{anno})"]
    if massima.titolo:
        lines.append(f"**Titolo**: {massima.titolo[:300]}")
    if massima.testo:
        lines.append(f"**Massima**: {massima.testo[:600]}")
    if massima.parametri:
        params = [_format_parametro(p) for p in massima.parametri if _format_parametro(p)]
        if params:
            lines.append("**Parametri**: " + "; ".join(params))
    return "\n".join(lines)

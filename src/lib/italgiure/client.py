"""Italgiure Solr client — async access to Corte di Cassazione decisions.

Endpoint: POST sncass/isapi/hc.dll/sn.solr/sn-collection/select?app.query
Auth: session cookie from homepage (anti-bot check).
SSL: verify=False (invalid cert on www.italgiure.giustizia.it).
Collections: snciv (civile), snpen (penale) — filtered via kind field in query.
"""

import re
import urllib.parse

import httpx

_BASE = "https://www.italgiure.giustizia.it/sncass"
_SOLR_URL = f"{_BASE}/isapi/hc.dll/sn.solr/sn-collection/select?app.query"
_HOMEPAGE = f"{_BASE}/"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": _HOMEPAGE,
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest",
}

_KIND_FILTER = {
    "civile": ["snciv"],
    "penale": ["snpen"],
    "tutti": ["snciv", "snpen"],
}

TIPO_PROV = {"sentenza": "S", "ordinanza": "O", "decreto": "D"}

_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
_MAX_OCR_LENGTH = 30000

_SEZIONI = {
    "1": "I",
    "2": "II",
    "3": "III",
    "4": "IV",
    "5": "V",
    "6": "VI",
    "7": "VII",
    "L": "lav.",
    "T": "trib.",
    "SU": "SS.UU.",
    "U": "sez. un.",
}

_RAMO = {"snciv": "civ.", "snpen": "pen."}

_CODICI = {
    "c.c.": ["c.c.", "cod. civ.", "codice civile"],
    "c.p.": ["c.p.", "cod. pen.", "codice penale"],
    "c.p.c.": ["c.p.c.", "cod. proc. civ."],
    "c.p.p.": ["c.p.p.", "cod. proc. pen."],
    "cost.": ["cost.", "costituzione"],
}


def get_kind_filter(archivio: str) -> list[str]:
    return _KIND_FILTER.get(archivio, _KIND_FILTER["tutti"])


def _first(val) -> str:
    """Return first element if val is a list, else val as string."""
    if isinstance(val, list):
        return val[0] if val else ""
    return str(val) if val is not None else ""


async def solr_query(params: dict) -> dict:
    """Execute Solr query against Italgiure unified endpoint.

    Uses POST to /sn-collection/select?app.query with form-encoded body.
    Fetches homepage first to obtain session cookie. verify=False for invalid SSL.
    Handles list-valued params (e.g. multiple fq) via urlencode(doseq=True).
    """
    async with httpx.AsyncClient(verify=False, timeout=_TIMEOUT, headers=_HEADERS) as client:
        await client.get(_HOMEPAGE)
        body = urllib.parse.urlencode({**params, "wt": "json", "indent": "off"}, doseq=True)
        resp = await client.post(_SOLR_URL, content=body)
        resp.raise_for_status()
        return resp.json()


def build_search_params(
    query: str,
    archivio: str = "tutti",
    materia: str | None = None,
    sezione: str | None = None,
    anno_da: int | None = None,
    anno_a: int | None = None,
    rows: int = 10,
    start: int = 0,
    highlight: bool = True,
) -> dict:
    kinds = get_kind_filter(archivio)
    kind_clause = " OR ".join(f'kind:"{k}"' for k in kinds)
    params: dict = {
        "defType": "edismax",
        "q": query,
        "qf": "ocrdis^5 ocr^1",
        "pf": "ocrdis^10",
        "fq": [f"({kind_clause})"],
        "sort": "pd desc",
        "rows": rows,
        "start": start,
        "fl": "id,numdec,anno,datdep,szdec,materia,tipoprov,ocrdis,kind",
    }
    if materia:
        params["fq"].append(f"materia:{materia}")
    if sezione:
        params["fq"].append(f"szdec:{sezione}")
    if anno_da and anno_a:
        params["fq"].append(f"anno:[{anno_da} TO {anno_a}]")
    elif anno_da:
        params["fq"].append(f"anno:[{anno_da} TO *]")
    elif anno_a:
        params["fq"].append(f"anno:[* TO {anno_a}]")
    if highlight:
        params.update({
            "hl": "true",
            "hl.fl": "ocr,ocrdis",
            "hl.fragsize": "400",
            "hl.snippets": "2",
        })
    return params


def build_lookup_params(
    numero: int,
    anno: int,
    archivio: str = "tutti",
    sezione: str | None = None,
) -> dict:
    kinds = get_kind_filter(archivio)
    kind_clause = " OR ".join(f'kind:"{k}"' for k in kinds)
    numdec_str = str(numero).zfill(5)
    q = f"({kind_clause}) AND numdec:{numdec_str} AND anno:{anno}"
    if sezione:
        q += f" AND szdec:{sezione}"
    return {
        "q": q,
        "rows": 5,
        "fl": "id,numdec,anno,datdep,szdec,materia,tipoprov,ocr,ocrdis,relatore,presidente,kind",
    }


def build_norma_variants(riferimento: str) -> str:
    """Convert 'art. 2043 c.c.' to Solr OR query with common text variants."""
    rif = riferimento.strip().lower()

    match = re.match(
        r"(?:art\.?|articolo)\s+(\d+(?:-(?:bis|ter|quater|quinquies|sexies|septies|octies|novies|decies))?)",
        rif,
    )
    if not match:
        return f'ocr:("{riferimento}")'

    num = match.group(1)
    rest = rif[match.end():].strip()

    variants = [f'"art. {num}"', f'"articolo {num}"']

    matched_code = False
    for abbrev, expansions in _CODICI.items():
        if rest.startswith(abbrev) or rest == abbrev.rstrip("."):
            for exp in expansions:
                variants.append(f'"{num} {exp}"')
            matched_code = True
            break

    if not matched_code and rest:
        variants.append(f'"art. {num} {rest}"')

    return "ocr:(" + " OR ".join(variants) + ")"


def _format_date(datdep) -> str:
    raw = _first(datdep)
    if not raw:
        return ""
    # Format: "20250827" → "27/08/2025"
    raw = raw.strip()
    if len(raw) == 8 and raw.isdigit():
        return f"{raw[6:8]}/{raw[4:6]}/{raw[0:4]}"
    # ISO "2025-08-27T..." fallback
    try:
        parts = raw[:10].split("-")
        if len(parts) == 3:
            return f"{parts[2]}/{parts[1]}/{parts[0]}"
    except (IndexError, ValueError):
        pass
    return raw


def format_estremi(doc: dict) -> str:
    kind = _first(doc.get("kind", "snciv"))
    ramo = _RAMO.get(kind, "civ.")
    sez = _first(doc.get("szdec", ""))
    sez_fmt = _SEZIONI.get(sez, sez)
    num = _first(doc.get("numdec", "?"))
    anno = _first(doc.get("anno", "?"))
    datdep = _format_date(doc.get("datdep"))

    parts = [f"Cass. {ramo}"]
    if sez_fmt:
        parts.append(f"sez. {sez_fmt}")
    parts.append(f"n. {num}/{anno}")
    if datdep:
        parts.append(f"dep. {datdep}")

    return ", ".join(parts)


def format_summary(doc: dict, highlights: dict[str, list[str]] | None = None) -> str:
    estremi = format_estremi(doc)
    materia = _first(doc.get("materia", ""))
    ocrdis = _first(doc.get("ocrdis", ""))

    lines = [f"### {estremi}"]
    if materia:
        lines.append(f"**Materia**: {materia}")
    if highlights:
        hl_dis = highlights.get("ocrdis", [])
        hl_ocr = highlights.get("ocr", [])
        if hl_dis:
            lines.append(f"**Dispositivo (match)**: ...{hl_dis[0]}...")
        if hl_ocr:
            lines.append(f"**Estratto**: ...{hl_ocr[0]}...")
    if ocrdis and not (highlights and highlights.get("ocrdis")):
        disp = ocrdis[:200].strip()
        if len(ocrdis) > 200:
            disp += "…"
        lines.append(f"**Dispositivo**: {disp}")

    return "\n".join(lines)


def format_full_text(doc: dict) -> str:
    estremi = format_estremi(doc)
    materia = _first(doc.get("materia", ""))
    relatore = _first(doc.get("relatore", ""))
    presidente = _first(doc.get("presidente", ""))
    ocr = _first(doc.get("ocr", ""))
    ocrdis = _first(doc.get("ocrdis", ""))

    lines = [f"# {estremi}"]
    if materia:
        lines.append(f"**Materia**: {materia}")
    if relatore:
        lines.append(f"**Relatore**: {relatore}")
    if presidente:
        lines.append(f"**Presidente**: {presidente}")
    lines.append("")

    if ocr:
        truncated = len(ocr) > _MAX_OCR_LENGTH
        text = ocr[:_MAX_OCR_LENGTH] if truncated else ocr
        lines.append("## Testo della decisione")
        lines.append(text)
        if truncated:
            lines.append(
                f"\n---\n*[Testo troncato a {_MAX_OCR_LENGTH} caratteri su {len(ocr)} totali]*"
            )

    if ocrdis:
        lines.append("\n## Dispositivo")
        lines.append(ocrdis)

    return "\n".join(lines)

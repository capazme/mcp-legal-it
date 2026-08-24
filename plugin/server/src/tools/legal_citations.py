"""Recupero testi normativi ufficiali da Normattiva (leggi italiane), EUR-Lex (normativa UE)
e Brocardi (annotazioni dottrinali e giurisprudenziali). Usare cite_law() come punto di ingresso
principale prima di citare qualsiasi norma in un parere o documento legale."""

import asyncio
import difflib
import os
import re
import tempfile
import time

from src.server import mcp
from src.lib.visualex import (
    Norma,
    NormaVisitata,
    resolve_atto,
    strip_leading_particles,
    known_act_names,
)
from src.lib.visualex.scraper import (
    fetch_article,
    fetch_annotations,
    download_eurlex_pdf,
    fetch_normattiva_full_text,
    fetch_act_index as _fetch_act_index_scraper,
)
from src.lib.brocardi.client import fetch_brocardi, BrocardiResult, parse_massime_references


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

# Strips paragraph/point/comma indicators from the start of the act name
# so that "art. 4 n. 11 GDPR" → article="4", act="GDPR".
_PARAGRAPH_PATTERN = re.compile(
    r"^[,;\s]*(?:n\.?\s*\d+|co(?:mma)?\.?\s*\d+|par\.?\s*\d+|punto\s*\d+|lett\.?\s*\w\)?)\s*[,;]?\s*",
    re.IGNORECASE,
)


def _parse_reference(reference: str) -> tuple[str, str]:
    """Parse a legal reference like 'art. 13 GDPR' into (article, act_name).

    Supports:
    - "art. 13 GDPR"
    - "art. 2-ter D.Lgs. 196/2003"
    - "ART 117 Costituzione"
    - "art. 2043 c.c."
    - "art. 6 D.Lgs. 231/2001"
    - "art. 4 n. 11 GDPR"  → paragraph stripped → ("4", "GDPR")
    - "considerando 42 GDPR" → ("rec_42", "GDPR")
    - "recital 47 GDPR"     → ("rec_47", "GDPR")
    """
    reference = reference.strip()

    # Considerando / recital — must be checked before "art." pattern
    rec_match = re.match(
        r"(?:considerando|recital)\s+(\d+)\s+(.+)",
        reference,
        re.IGNORECASE,
    )
    if rec_match:
        return f"rec_{rec_match.group(1)}", rec_match.group(2).strip()

    # Pattern: art[.] <number[-ext]> <act_name>
    match = re.match(
        r"(?:articol[oi]|art)\.?\s*(\d+(?:[-/.]\w+)*)\s*[,;]?\s+(.+)",
        reference,
        re.IGNORECASE,
    )
    if match:
        article = match.group(1).strip()
        rest = match.group(2).strip()
        # Strip leading paragraph/point/comma indicators, applied repeatedly
        # to handle chains like "comma 1 lett. a) GDPR" → "GDPR".
        while True:
            stripped = _PARAGRAPH_PATTERN.sub("", rest).strip()
            if stripped == rest:
                break
            rest = stripped
        return article, rest

    # No "art." prefix — try to parse as just act name (no article)
    return "", reference


# Act types as they appear in citations, spelled-out forms first so the
# alternation never settles for the "L." inside "legge".
_TIPO_ALT = (
    r"decreto\s+del\s+presidente\s+della\s+repubblica"
    r"|decreto\s+del\s+presidente\s+del\s+consiglio(?:\s+dei\s+ministri)?"
    r"|decreto\s+legislativo|decreto[-\s]legge|decreto\s+ministeriale"
    r"|regio\s+decreto|legge"
    r"|D\.?\s?Lgs\.?|D\.?P\.?C\.?M\.?|D\.?P\.?R\.?|DPR|R\.?D\.?"
    r"|D\.?\s?M\.?|D\.?\s?L\.?|L\.?"
)

# Canonical name per act type, keyed on the citation stripped of dots, spaces
# and hyphens ("D. Lgs." and "decreto legislativo" both land on one entry).
_TIPO_CANONICO = {
    "dlgs": "decreto legislativo",
    "decretolegislativo": "decreto legislativo",
    "dl": "decreto legge",
    "decretolegge": "decreto legge",
    "dm": "decreto ministeriale",
    "decretoministeriale": "decreto ministeriale",
    "dpcm": "decreto del presidente del consiglio dei ministri",
    "decretodelpresidentedelconsiglio": "decreto del presidente del consiglio dei ministri",
    "decretodelpresidentedelconsigliodeiministri": "decreto del presidente del consiglio dei ministri",
    "dpr": "decreto del presidente della repubblica",
    "decretodelpresidentedellarepubblica": "decreto del presidente della repubblica",
    "rd": "regio decreto",
    "regiodecreto": "regio decreto",
    "l": "legge",
    "legge": "legge",
}

_MESI_IT = {
    "gennaio": "01", "febbraio": "02", "marzo": "03", "aprile": "04",
    "maggio": "05", "giugno": "06", "luglio": "07", "agosto": "08",
    "settembre": "09", "ottobre": "10", "novembre": "11", "dicembre": "12",
}

# "regolamento (UE) 2016/679", "reg. UE n. 679/2016", "direttiva 95/46/CE"
_EU_PATTERN = re.compile(
    r"^(reg(?:olamento)?|dir(?:ettiva)?)\.?\s*"
    r"(?:\(?\s*(?:UE|EU|CE|CEE)\s*\)?)?\s*"
    r"(?:n\.?\s*)?(\d{1,4})\s*/\s*(\d{1,4})"
    r"(?:\s*/\s*(?:UE|EU|CE|CEE))?",
    re.IGNORECASE,
)

# "D.Lgs. 30 giugno 2003, n. 196"
_IT_LONG_PATTERN = re.compile(
    rf"^({_TIPO_ALT})\s+(\d{{1,2}})\s+"
    r"(gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre)"
    r"\s+(\d{4})[,]?\s*n\.?\s*(\d+)",
    re.IGNORECASE,
)

# "D.Lgs. 196/2003", "legge n. 241 del 1990", "legge n. 241/1990"
_IT_SHORT_PATTERN = re.compile(
    rf"^({_TIPO_ALT})\s*(?:n\.?\s*)?(\d+)\s*(?:/|\s+del\s+)\s*(\d{{4}})",
    re.IGNORECASE,
)


def _canonical_tipo(raw: str) -> str:
    """Map a cited act type to its canonical Normattiva name."""
    key = re.sub(r"[.\s-]", "", raw.lower())
    return _TIPO_CANONICO.get(key, raw.lower().strip())


def _split_eu_year_number(first: str, second: str) -> tuple[str, str]:
    """Decide which half of an EU act's "NNNN/NNNN" is the year.

    Directives switched notation in 2015: "95/46/CE" is year/number with a
    two-digit year, "2019/1937" is year/number with a four-digit one, and some
    citations still invert it as "679/2016". The four-digit plausible year wins;
    a leading two-digit group is a 20th-century year.
    """
    def is_year(v: str) -> bool:
        return len(v) == 4 and 1950 <= int(v) <= 2099

    if is_year(first):
        return first, second
    if is_year(second):
        return second, first
    if len(first) == 2:
        return f"19{first}", second
    return first, second


def _resolve_act(act_name: str) -> dict | None:
    """Resolve an act name to scraper parameters {tipo_atto, data, numero_atto}.

    Resolution chain:
    1. resolve_atto() — hand-verified tables (ATTI_NOTI, codici, ATTI_DENOMINATI)
    2. citation patterns — EU acts, then Italian acts in long and short form

    Returns None rather than guessing: a caller that cannot resolve an act must
    say so, never cite a different one.
    """
    result = resolve_atto(act_name)
    if result:
        return result

    # Patterns run against the name stripped of any leading preposition
    # ("del D.Lgs. 231/2001"), which resolve_atto has already normalized away.
    candidate = strip_leading_particles(act_name)

    eu_match = _EU_PATTERN.match(candidate)
    if eu_match:
        tipo_raw, first, second = eu_match.groups()
        anno, numero = _split_eu_year_number(first, second)
        tipo = "regolamento ue" if tipo_raw.lower().startswith("reg") else "direttiva ue"
        return {"tipo_atto": tipo, "data": anno, "numero_atto": numero}

    long_match = _IT_LONG_PATTERN.match(candidate)
    if long_match:
        tipo_raw, giorno, mese_it, anno, numero = long_match.groups()
        data = f"{anno}-{_MESI_IT[mese_it.lower()]}-{giorno.zfill(2)}"
        return {"tipo_atto": _canonical_tipo(tipo_raw), "data": data, "numero_atto": numero}

    short_match = _IT_SHORT_PATTERN.match(candidate)
    if short_match:
        tipo_raw, numero, anno = short_match.groups()
        return {"tipo_atto": _canonical_tipo(tipo_raw), "data": anno, "numero_atto": numero}

    return None


def _suggest_acts(act_name: str, limit: int = 3) -> list[str]:
    """Names close to an unrecognised one, so the caller can retry knowingly."""
    return difflib.get_close_matches(
        strip_leading_particles(act_name), known_act_names(), n=limit, cutoff=0.7
    )


def _unresolved_act_error(act_name: str) -> str:
    """Error text for an act the resolver could not identify, with near misses."""
    message = f"**Errore**: atto '{act_name}' non riconosciuto."
    suggestions = _suggest_acts(act_name)
    if suggestions:
        message += " Forse intendevi: " + ", ".join(f"'{s}'" for s in suggestions) + "."
    message += (
        " Prova con il nome completo (es. 'D.Lgs. 196/2003')"
        " o usa fetch_law_article() con parametri espliciti."
    )
    return message


def _build_nv(act_info: dict, article: str) -> NormaVisitata:
    """Build a NormaVisitata from resolved act info + article number."""
    norma = Norma(
        tipo_atto=act_info["tipo_atto"],
        data=act_info.get("data", ""),
        numero_atto=act_info.get("numero_atto", ""),
    )
    return NormaVisitata(norma=norma, numero_articolo=article)


def _format_result(article_result: dict, annotations_result: dict | None = None) -> str:
    """Format scraping results as markdown output."""
    parts = []

    if article_result.get("error"):
        parts.append(f"**Errore**: {article_result['error']}")
        return "\n".join(parts)

    text = article_result.get("text", "")
    url = article_result.get("url", "")
    source = article_result.get("source", "")

    if text:
        parts.append(f"**Fonte**: {source.title()} — {url}\n")
        parts.append(text)
    else:
        parts.append(f"**Nessun testo trovato** — URL: {url}")

    if annotations_result:
        if annotations_result.get("error"):
            parts.append(f"\n**Annotazioni**: {annotations_result['error']}")
        else:
            annotations = annotations_result.get("annotations", {})
            ann_url = annotations_result.get("url", "")
            if annotations:
                parts.append(f"\n---\n**Annotazioni Brocardi** — {ann_url}\n")
                if "Ratio" in annotations:
                    parts.append(f"**Ratio Legis**: {annotations['Ratio']}\n")
                if "Spiegazione" in annotations:
                    parts.append(f"**Spiegazione**: {annotations['Spiegazione']}\n")
                if "Brocardi" in annotations:
                    parts.append("**Brocardi**: " + "; ".join(annotations["Brocardi"]) + "\n")
                if "Massime" in annotations:
                    parts.append("**Massime giurisprudenziali**:")
                    for m in annotations["Massime"]:
                        header = m.get("header", "")
                        text_m = m.get("text", "")
                        parts.append(f"- {header}: {text_m}" if header else f"- {text_m}")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# MCP Tools
# ---------------------------------------------------------------------------

async def _cite_law_impl(reference: str, include_annotations: bool = False) -> str:
    """Implementation of cite_law (testable without MCP wrapper)."""
    article, act_name = _parse_reference(reference)
    if not act_name:
        return f"**Errore**: impossibile interpretare il riferimento '{reference}'. Formato atteso: 'art. <numero> <atto>'"

    act_info = _resolve_act(act_name)
    if not act_info:
        return _unresolved_act_error(act_name)

    nv = _build_nv(act_info, article)

    try:
        article_result = await fetch_article(nv)
    except Exception as e:
        article_result = {"text": "", "url": nv.url(), "source": "", "error": str(e)}

    brocardi_md = ""
    if include_annotations and article:
        try:
            brocardi = await fetch_brocardi(
                act_info["tipo_atto"], article, act_info.get("numero_atto", "")
            )
            if not brocardi.error:
                brocardi_md = "\n\n---\n" + brocardi.to_markdown()
            else:
                brocardi_md = f"\n\n**Annotazioni Brocardi**: {brocardi.error}"
        except Exception as e:
            brocardi_md = f"\n\n**Annotazioni Brocardi**: errore — {e}"

    return _format_result(article_result) + brocardi_md


async def _fetch_law_article_impl(act_type: str, article: str, date: str = "", act_number: str = "") -> str:
    """Implementation of fetch_law_article (testable without MCP wrapper)."""
    norma = Norma(tipo_atto=act_type, data=date, numero_atto=act_number)
    nv = NormaVisitata(norma=norma, numero_articolo=article)

    try:
        result = await fetch_article(nv)
    except Exception as e:
        result = {"text": "", "url": nv.url(), "source": "", "error": str(e)}

    return _format_result(result)


async def _fetch_law_annotations_impl(act_type: str, article: str, date: str = "", act_number: str = "") -> str:
    """Implementation of fetch_law_annotations (testable without MCP wrapper)."""
    try:
        result = await fetch_brocardi(act_type, article, act_number)
        return result.to_markdown()
    except Exception as e:
        return f"**Errore Brocardi**: {e}"


@mcp.tool(tags={"normativa"})
async def cite_law(reference: str, include_annotations: bool = False) -> str:
    """Recupera il testo ufficiale di una norma di legge. USARE SEMPRE prima di citare qualsiasi norma.

    Fonti: Normattiva (leggi italiane), EUR-Lex (regolamenti/direttive UE), Brocardi (annotazioni).

    Dopo questo tool: cerca_brocardi() per approfondimenti dottrinali, cerca_giurisprudenza() per precedenti.
    Restituisce: testo ufficiale dell'articolo da Normattiva/EUR-Lex con URL fonte.

    Esempi di riferimenti validi:
      - "art. 2043 c.c." — articolo del codice civile
      - "art. 4 GDPR" — articolo del regolamento UE 2016/679
      - "art. 6 D.Lgs. 231/2001" — articolo di decreto legislativo
      - "considerando 42 GDPR" — considerando (recital) di regolamento UE
      - "art. 13 regolamento UE 2016/679" — riferimento con nome completo

    I numeri di paragrafo (n. N, co. N, comma N) vengono automaticamente
    ignorati: "art. 4 n. 11 GDPR" equivale a "art. 4 GDPR".

    Args:
        reference: Riferimento normativo, es. "art. 13 GDPR", "art. 2043 c.c.",
                   "art. 6 D.Lgs. 231/2001", "art. 117 Costituzione",
                   "considerando 42 GDPR", "art. 4 n. 11 GDPR"
        include_annotations: Includi anche le annotazioni Brocardi (ratio legis, spiegazione,
                             massime giurisprudenziali). Default False.
    """
    return await _cite_law_impl(reference, include_annotations)


@mcp.tool(tags={"normativa"})
async def fetch_law_article(act_type: str, article: str, date: str = "", act_number: str = "") -> str:
    """Recupero a basso livello di un articolo con parametri espliciti da Normattiva o EUR-Lex.
    Usare cite_law() per il caso comune; questo tool è per quando serve controllo preciso
    sul tipo atto, anno e numero (es. ambiguità di abbreviazione).
    Restituisce: testo dell'articolo da Normattiva/EUR-Lex con URL fonte.

    Args:
        act_type: Tipo di atto normativo, es. "decreto legislativo", "regolamento ue",
                  "codice civile", "codice penale", "costituzione", "legge", "decreto legge"
        article: Numero dell'articolo, es. "13", "2-bis", "117"
        date: Anno o data dell'atto, es. "2016", "2003-06-30" (opzionale per i codici)
        act_number: Numero dell'atto, es. "196", "679" (opzionale per i codici)
    """
    return await _fetch_law_article_impl(act_type, article, date, act_number)


@mcp.tool(tags={"normativa"})
async def fetch_law_annotations(act_type: str, article: str, date: str = "", act_number: str = "") -> str:
    """Recupera le annotazioni Brocardi per un articolo: ratio legis, spiegazione dottrinale,
    massime giurisprudenziali. Da usare per approfondire la norma già recuperata con cite_law().
    Restituisce: ratio legis, spiegazione dottrinale, massime giurisprudenziali da Brocardi.

    Args:
        act_type: Tipo di atto normativo, es. "codice civile", "codice penale", "costituzione"
        article: Numero dell'articolo, es. "2043", "575", "13"
        date: Anno o data (opzionale per i codici)
        act_number: Numero dell'atto (opzionale per i codici)
    """
    return await _fetch_law_annotations_impl(act_type, article, date, act_number)


async def _cerca_brocardi_impl(reference: str) -> str:
    """Implementation of cerca_brocardi (testable without MCP wrapper)."""
    article, act_name = _parse_reference(reference)
    if not article:
        return "**Errore**: specificare un articolo. Formato: 'art. <numero> <atto>' (es. 'art. 2043 c.c.')"

    if not act_name:
        return f"**Errore**: impossibile interpretare il riferimento '{reference}'."

    act_info = _resolve_act(act_name)
    if not act_info:
        return _unresolved_act_error(act_name)

    try:
        result = await fetch_brocardi(
            act_info["tipo_atto"], article, act_info.get("numero_atto", "")
        )
    except Exception as e:
        return f"**Errore Brocardi**: {e}"

    if result.error:
        return f"**Errore Brocardi**: {result.error}"

    parts = [result.to_markdown()]

    # Append Cassazione references for Italgiure cross-linking
    cass_refs = parse_massime_references(result.massime)
    if cass_refs:
        parts.append("\n---\n**Riferimenti Cassazione** (per approfondimento con `leggi_sentenza`):")
        for ref in cass_refs:
            parts.append(f"- {ref['autorita']} n. {ref['numero']}/{ref['anno']}")

    return "\n".join(parts)


@mcp.tool(tags={"normativa"})
async def cerca_brocardi(reference: str) -> str:
    """Cerca annotazioni Brocardi per un articolo di legge: ratio legis, spiegazione dottrinale,
    massime giurisprudenziali con riferimenti strutturati alla Cassazione, relazioni storiche,
    note a piè di pagina e riferimenti incrociati.

    Rispetto a fetch_law_annotations, accetta un riferimento in formato naturale (come cite_law)
    e restituisce anche i riferimenti strutturati alle sentenze della Cassazione
    (utilizzabili con leggi_sentenza per recuperare il testo completo).
    Dopo questo tool: leggi_sentenza() per il testo completo delle sentenze citate nelle massime.
    Restituisce: ratio legis, spiegazione, massime con numeri sentenza strutturati, relazioni storiche.

    Args:
        reference: Riferimento normativo, es. "art. 2043 c.c.", "art. 13 Costituzione",
                   "art. 575 c.p.", "art. 6 D.Lgs. 231/2001"
    """
    return await _cerca_brocardi_impl(reference)


# ---------------------------------------------------------------------------
# Full act / index tools
# ---------------------------------------------------------------------------

async def _fetch_act_index_impl(reference: str) -> str:
    """Implementation of fetch_act_index."""
    _, act_name = _parse_reference(reference)
    if not act_name:
        return f"**Errore**: impossibile interpretare il riferimento '{reference}'."
    act_info = _resolve_act(act_name)
    if not act_info:
        return _unresolved_act_error(act_name)

    norma = Norma(
        tipo_atto=act_info["tipo_atto"],
        data=act_info.get("data", ""),
        numero_atto=act_info.get("numero_atto", ""),
    )
    try:
        result = await _fetch_act_index_scraper(norma)
    except Exception as e:
        return f"**Errore** nel recupero dell'indice: {e}"

    if result.get("error"):
        return f"**Errore**: {result['error']}"

    entries = result.get("index", [])
    if not entries:
        return f"Nessun indice trovato per {act_name}."

    lines = [f"## Indice — {norma}\n"]
    for entry in entries:
        lines.append(f"- {entry}")
    lines.append(f"\n*Codice redazionale*: `{result.get('codice_redazionale', '')}`")
    return "\n".join(lines)


@mcp.tool(tags={"normativa"})
async def fetch_act_index(reference: str) -> str:
    """Recupera l'indice strutturato (rubriche) di un atto normativo da Normattiva.

    Restituisce l'elenco degli articoli con i relativi titoli, utile per navigare
    atti complessi senza scaricare il testo intero.
    Restituisce: lista degli articoli con rubrica e codice redazionale dell'atto.

    Args:
        reference: Nome dell'atto, es. "D.Lgs. 231/2001", "codice civile", "D.M. 55/2014"
    """
    return await _fetch_act_index_impl(reference)


async def _fetch_full_act_impl(reference: str) -> str:
    """Implementation of fetch_full_act."""
    _, act_name = _parse_reference(reference)
    if not act_name:
        return f"**Errore**: impossibile interpretare il riferimento '{reference}'."
    act_info = _resolve_act(act_name)
    if not act_info:
        return _unresolved_act_error(act_name)

    norma = Norma(
        tipo_atto=act_info["tipo_atto"],
        data=act_info.get("data", ""),
        numero_atto=act_info.get("numero_atto", ""),
    )

    if norma._is_eurlex():
        return "Per atti UE usare download_law_pdf() — il testo integrale è disponibile solo in PDF."

    try:
        result = await fetch_normattiva_full_text(norma)
    except Exception as e:
        return f"**Errore** nel recupero del testo completo: {e}"

    if result.get("error"):
        return f"**Errore**: {result['error']}"

    text = result.get("text", "")
    title = result.get("title", str(norma))
    url = result.get("url", "")

    if not text or len(text) < 50:
        return f"**Errore**: testo insufficiente. URL: {url}"

    lines = [
        f"# {title}",
        f"**Fonte**: Normattiva — {url}",
        f"**Dimensione**: {len(text):,} caratteri\n",
        text,
    ]

    return "\n".join(lines)


@mcp.tool(tags={"normativa"})
async def fetch_full_act(reference: str) -> str:
    """Recupera il testo completo di un atto normativo italiano da Normattiva.

    Restituisce il testo integrale dell'atto senza troncamenti.
    ATTENZIONE: per codici voluminosi (c.c., c.p.) il testo può essere molto lungo.
    Per atti UE usare download_law_pdf() per il PDF ufficiale da EUR-Lex.
    Restituisce: testo completo dell'atto con titolo e URL fonte.

    Args:
        reference: Nome dell'atto, es. "D.Lgs. 231/2001", "D.M. 55/2014", "L. 604/1966"
    """
    return await _fetch_full_act_impl(reference)


# ---------------------------------------------------------------------------
# PDF generation helpers
# ---------------------------------------------------------------------------

_PDF_OUTPUT_DIR = os.path.join(tempfile.gettempdir(), "mcp-legal-it")
_PDF_MAX_AGE_SECONDS = 3600  # 1 hour


def _cleanup_old_pdfs() -> None:
    """Delete PDF files older than 1 hour from the temp dir."""
    if not os.path.isdir(_PDF_OUTPUT_DIR):
        return
    now = time.time()
    for fname in os.listdir(_PDF_OUTPUT_DIR):
        if not fname.endswith(".pdf"):
            continue
        fpath = os.path.join(_PDF_OUTPUT_DIR, fname)
        try:
            if now - os.path.getmtime(fpath) > _PDF_MAX_AGE_SECONDS:
                os.remove(fpath)
        except OSError:
            pass


def _sanitize_for_pdf(text: str) -> str:
    """Replace characters not in windows-1252 for fpdf2 built-in fonts."""
    replacements = {
        "\u2013": "-",
        "\u2014": "--",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2026": "...",
        "\u00a0": " ",
        "\u200b": "",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text.encode("windows-1252", errors="replace").decode("windows-1252")


def _generate_pdf_from_text(title: str, text: str, source_url: str, output_path: str) -> None:
    """Generate a PDF file from text content using fpdf2."""
    from fpdf import FPDF

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 14)
    pdf.multi_cell(0, 8, _sanitize_for_pdf(title))
    pdf.ln(3)

    pdf.set_font("Helvetica", "I", 7)
    pdf.multi_cell(0, 4, f"Fonte: {source_url}")
    pdf.ln(8)

    pdf.set_font("Helvetica", "", 9)
    pdf.multi_cell(0, 4, _sanitize_for_pdf(text))

    pdf.output(output_path)


def _safe_filename(name: str) -> str:
    """Convert act name to a safe filename."""
    return re.sub(r"[^\w\-.]", "_", name.replace("/", "-").replace(" ", "_"))[:80]


# ---------------------------------------------------------------------------
# download_law_pdf implementation + MCP tool
# ---------------------------------------------------------------------------

async def _download_law_pdf_impl(reference: str) -> str:
    """Download or generate PDF for a law."""
    _cleanup_old_pdfs()
    article, act_name = _parse_reference(reference)
    if not act_name:
        return f"**Errore**: impossibile interpretare il riferimento '{reference}'."

    act_info = _resolve_act(act_name)
    if not act_info:
        return _unresolved_act_error(act_name)

    norma = Norma(
        tipo_atto=act_info["tipo_atto"],
        data=act_info.get("data", ""),
        numero_atto=act_info.get("numero_atto", ""),
    )

    os.makedirs(_PDF_OUTPUT_DIR, exist_ok=True)
    filename = _safe_filename(act_name) + ".pdf"
    filepath = os.path.join(_PDF_OUTPUT_DIR, filename)

    # EUR-Lex: download official PDF
    if norma._is_eurlex():
        try:
            pdf_bytes = await download_eurlex_pdf(norma)
            with open(filepath, "wb") as f:
                f.write(pdf_bytes)

            from src.lib.visualex.map import EURLEX
            eurlex_val = EURLEX.get(norma.tipo_atto_normalized.lower(), "reg")
            type_letter = {"reg": "R", "dir": "L"}.get(eurlex_val, "R")
            year = norma.data.split("-")[0] if "-" in norma.data else norma.data
            number = norma.numero_atto.zfill(4)
            pdf_url = f"https://eur-lex.europa.eu/legal-content/IT/TXT/PDF/?uri=CELEX:3{year}{type_letter}{number}"

            return (
                f"**PDF scaricato** ({act_name})\n\n"
                f"File: `{filepath}`\n"
                f"Fonte: EUR-Lex — {pdf_url}\n"
                f"Dimensione: {len(pdf_bytes):,} bytes"
            )
        except Exception as e:
            return f"**Errore** download PDF EUR-Lex: {e}"

    # Normattiva: fetch full text and generate PDF
    try:
        result = await fetch_normattiva_full_text(norma)
        if result.get("error"):
            return f"**Errore**: {result['error']}"

        text = result["text"]
        title = result["title"] or str(norma)
        url = result["url"]

        if not text or len(text) < 50:
            return f"**Errore**: testo insufficiente per generare il PDF. URL: {url}"

        _generate_pdf_from_text(title, text, url, filepath)
        size = os.path.getsize(filepath)

        return (
            f"**PDF generato** ({title})\n\n"
            f"File: `{filepath}`\n"
            f"Fonte: Normattiva — {url}\n"
            f"Dimensione: {size:,} bytes\n"
            f"Nota: PDF generato dal testo ufficiale (non il PDF originale Normattiva)"
        )
    except Exception as e:
        return f"**Errore** generazione PDF: {e}"


@mcp.tool(tags={"normativa"})
async def download_law_pdf(reference: str) -> str:
    """Scarica o genera il PDF completo di una legge.

    Per regolamenti/direttive UE: scarica il PDF ufficiale da EUR-Lex.
    Per leggi italiane: genera un PDF dal testo ufficiale recuperato da Normattiva.
    Restituisce: path al file PDF salvato in /tmp con fonte e dimensione.

    Args:
        reference: Nome dell'atto o riferimento normativo, es. "GDPR", "D.Lgs. 196/2003",
                   "codice civile", "art. 13 GDPR"
    """
    return await _download_law_pdf_impl(reference)


# ---------------------------------------------------------------------------
# verifica_citazioni — citation existence + metadata verifier
# ---------------------------------------------------------------------------

# Earliest year covered by the Italgiure archive. Decisions before this cannot
# be confirmed as existent or not — they are simply outside the searchable index.
_ITALGIURE_MIN_YEAR = 2020

# Hard cap on the number of references resolved in a single call, to bound
# concurrency against the slow government sources.
_MAX_CITAZIONI = 20

# Max references resolved in parallel, to avoid rate-limiting/connection resets
# from the slow government endpoints (Normattiva, EUR-Lex, Italgiure).
_MAX_CONCURRENT_VERIFICHE = 4

# Cassazione decision shape: a decision number followed by a 4-digit year,
# in either "n. 12345/2024" / "12345/2024" or "n. 12345 del 2024" form,
# optionally preceded by "Cass." / "sez. ...". The presence of an explicit
# court/section marker OR the "n. .../YYYY" pattern marks a SENTENZA.
_SENTENZA_NUM_ANNO = re.compile(
    r"n\.?\s*(\d{1,6})\s*(?:/|\s+del\s+)\s*((?:19|20)\d{2})",
    re.IGNORECASE,
)
_SENTENZA_BARE = re.compile(
    r"(?<!\d)(\d{1,6})\s*/\s*((?:19|20)\d{2})(?!\d)",
)
_CASS_MARKER = re.compile(r"\b(?:cass(?:azione)?|sez(?:ione)?|ss?\.?\s*uu)\b", re.IGNORECASE)

# Section parsing from the user's citation (e.g. "sez. III", "Sezioni Unite").
_USER_SEZIONE = re.compile(
    r"sez(?:ion[ei]|\.)?\s*"
    r"(unite|un\.?|u|s\.?u\.?|lavoro|lav\.?|l|trib(?:utaria)?\.?|t|"
    r"[ivx]+|\d+)",
    re.IGNORECASE,
)

# Section parsing from the resolved estremi heading (uses _SEZIONI labels:
# "I".."VII", "lav.", "trib.", "SS.UU.", "sez. un.").
_RESOLVED_ESTREMI = re.compile(
    r"n\.\s*(\d+)\s*/\s*(\d+)",
)
_RESOLVED_SEZIONE = re.compile(
    r"sez\.\s*([^,\n]+?)\s*,",
)

# comma / lettera markers in the user's citation
_USER_COMMA = re.compile(r"\b(?:co(?:mma)?|c)\.?\s*(\d+)", re.IGNORECASE)
_USER_LETTERA = re.compile(r"\blett(?:era)?\.?\s*([a-z])\b", re.IGNORECASE)

# Roman numeral / arabic mapping for section comparison.
_ROMAN_TO_INT = {
    "i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6, "vii": 7,
}


def _split_citazioni(citazioni: str) -> list[str]:
    """Split raw input into individual references.

    Primary separator is the newline. Within a line, comma-separated lists are
    supported, but a comma that merely separates a section from its number
    (e.g. "Cass. sez. III, n. 12345/2024") must NOT break the reference. A
    fragment starts a NEW reference only when it begins with a known opener
    (art./articolo, considerando/recital, Cass./sez., or a bare digit); any
    other fragment is a continuation and is re-joined to the previous one.
    """
    refs: list[str] = []
    for line in citazioni.replace("\r", "").split("\n"):
        line = line.strip()
        if not line:
            continue
        if "," not in line:
            refs.append(line)
            continue
        fragments = [f.strip() for f in line.split(",")]
        current = ""
        for frag in fragments:
            if not frag:
                continue
            if current and _starts_new_reference(frag):
                refs.append(current)
                current = frag
            elif current:
                current = f"{current}, {frag}"
            else:
                current = frag
        if current:
            refs.append(current)
    return refs


def _starts_new_reference(fragment: str) -> bool:
    """True if a comma-fragment begins a fresh citation (not a continuation)."""
    low = fragment.lstrip().lower()
    if re.match(r"(?:art(?:icol[oi])?\.?\s*\d|considerando\s+\d|recital\s+\d)", low):
        return True
    if re.match(r"(?:cass|sez|ss?\.?\s*uu)", low):
        return True
    if re.match(r"\d", low):
        return True
    return False


def _classify_citazione(reference: str) -> str:
    """Classify a reference as 'sentenza', 'norma', or 'non interpretabile'."""
    article, act_name = _parse_reference(reference)
    if article and act_name:
        return "norma"
    if _sentenza_num_anno(reference) is not None:
        return "sentenza"
    return "non interpretabile"


def _sentenza_num_anno(reference: str) -> tuple[int, int] | None:
    """Extract (numero, anno) if the reference has a Cassazione decision shape.

    Recognised forms:
      - "Cass. n. 12345/2024", "sez. III n. 12345/2024", "n. 12345 del 2024"
      - "12345/2024" only when an explicit court/section marker is present,
        to avoid mistaking "196/2003" (a D.Lgs. number) for a decision.
    """
    m = _SENTENZA_NUM_ANNO.search(reference)
    if m:
        return int(m.group(1)), int(m.group(2))
    if _CASS_MARKER.search(reference):
        m = _SENTENZA_BARE.search(reference)
        if m:
            return int(m.group(1)), int(m.group(2))
        # "Cass. 999 del 2021" — number + year without the "n." prefix.
        m = re.search(r"(?<!\d)(\d{1,6})\s+del\s+((?:19|20)\d{2})", reference, re.IGNORECASE)
        if m:
            return int(m.group(1)), int(m.group(2))
    return None


def _normalize_sezione(raw: str) -> str:
    """Normalise a section token (roman/arabic/word) to a comparable code."""
    s = raw.strip().lower().rstrip(".")
    if s in ("unite", "un", "u", "su", "s.u", "ss.uu", "ssuu"):
        return "SU"
    if s in ("lavoro", "lav", "l"):
        return "L"
    if s in ("tributaria", "trib", "t"):
        return "T"
    if s in _ROMAN_TO_INT:
        return str(_ROMAN_TO_INT[s])
    if s.isdigit():
        return s
    return s


def _parse_resolved_estremi(results_text: str) -> dict:
    """Parse the resolved decision metadata from a leggi_sentenza heading.

    The first line is the estremi heading produced by format_full_text, e.g.
    "# Cass. civ., sez. III, n. 12345/2024, dep. 22/04/2024". Returns
    {"numero", "anno", "sezione"} with whatever could be extracted.
    """
    first_line = results_text.splitlines()[0] if results_text else ""
    out: dict = {}
    m = _RESOLVED_ESTREMI.search(first_line)
    if m:
        out["numero"] = int(m.group(1))
        out["anno"] = int(m.group(2))
    sez_m = _RESOLVED_SEZIONE.search(first_line)
    if sez_m:
        # The resolved label uses _SEZIONI values: I..VII, lav., trib., SS.UU.
        out["sezione"] = _normalize_resolved_sezione(sez_m.group(1))
    return out


def _normalize_resolved_sezione(raw: str) -> str:
    """Normalise the section as rendered in the estremi (I, lav., SS.UU., ...)."""
    s = raw.strip().lower().rstrip(".")
    if s in ("ss.uu", "ssuu", "sez. un", "sez un", "un"):
        return "SU"
    if s == "lav":
        return "L"
    if s == "trib":
        return "T"
    if s in _ROMAN_TO_INT:
        return str(_ROMAN_TO_INT[s])
    if s.isdigit():
        return s
    return s


def _norma_misquote(reference: str, article_text: str) -> bool:
    """True if the citation names a comma/lettera absent from the article text.

    Conservative: only flags when a comma/lettera marker is explicitly named in
    the reference AND no corresponding marker is found in the article body.
    """
    text = article_text or ""

    comma_m = _USER_COMMA.search(reference)
    if comma_m:
        n = int(comma_m.group(1))
        # An article comma is rendered as a leading "N." (e.g. "2. Il titolare…")
        # or referenced as "comma N" inside the text.
        comma_present = bool(
            re.search(rf"(?m)^\s*{n}\s*\.", text)
            or re.search(rf"\bcomma\s+{n}\b", text, re.IGNORECASE)
        )
        # Only flag a missing comma when the text actually numbers its commas
        # (i.e. other leading "K." markers exist): a single-comma article rarely
        # prints "1.", so absence there is not a reliable misquote signal.
        numbered_commas = {
            int(x) for x in re.findall(r"(?m)^\s*(\d{1,2})\s*\.", text)
        }
        text_is_numbered = len(numbered_commas) >= 1
        if not comma_present and text_is_numbered:
            return True

    lettera_m = _USER_LETTERA.search(reference)
    if lettera_m:
        letter = lettera_m.group(1).lower()
        # A lettera is rendered as "a)" / "lettera a)".
        lettera_present = bool(
            re.search(rf"(?<![a-z]){letter}\)", text, re.IGNORECASE)
            or re.search(rf"\blett(?:era)?\.?\s*{letter}\b", text, re.IGNORECASE)
        )
        if not lettera_present:
            return True

    return False


async def _verifica_norma(reference: str) -> tuple[str, str]:
    """Verify a NORMA reference. Returns (verdetto, nota)."""
    markdown = await _cite_law_impl(reference)
    if markdown.startswith("**Errore**") or markdown.startswith("**Nessun testo trovato**"):
        return "non trovata", "Atto o articolo non reperibile su Normattiva/EUR-Lex."

    # Source line: "**Fonte**: <Source> — <url>"
    fonte = ""
    fonte_m = re.search(r"\*\*Fonte\*\*:\s*(.+)", markdown)
    if fonte_m:
        fonte = fonte_m.group(1).strip()

    if _norma_misquote(reference, markdown):
        nota = "Comma/lettera citato non riscontrato nel testo dell'articolo."
        if fonte:
            nota += f" Fonte: {fonte}"
        return "metadati discordanti", nota

    return "verificata", f"Fonte: {fonte}" if fonte else "Testo ufficiale reperito."


async def _verifica_sentenza(reference: str, archivio: str) -> tuple[str, str]:
    """Verify a SENTENZA reference. Returns (verdetto, nota)."""
    num_anno = _sentenza_num_anno(reference)
    if num_anno is None:  # pragma: no cover - guarded by classification
        return "non interpretabile", "Numero/anno della decisione non riconosciuti."
    numero, anno = num_anno

    if anno < _ITALGIURE_MIN_YEAR:
        return (
            "non verificabile",
            f"Decisione n. {numero}/{anno} anteriore al {_ITALGIURE_MIN_YEAR}, "
            "fuori archivio Italgiure.",
        )

    from src.tools.italgiure import _leggi_sentenza_impl

    sezione_req = ""
    sez_m = _USER_SEZIONE.search(reference)
    if sez_m:
        sezione_req = _normalize_sezione(sez_m.group(1))

    result = await _leggi_sentenza_impl(numero, anno, archivio=archivio)

    if not result.success:
        if result.error_type == "source_down":
            return (
                "non verificata",
                f"Italgiure non raggiungibile: {result.error_message}",
            )
        return (
            "inesistente",
            f"Decisione n. {numero}/{anno} non trovata negli archivi della Cassazione.",
        )

    # The 4-step fallback can return a DIFFERENT decision — re-check identity.
    resolved = _parse_resolved_estremi(result.results_text)
    res_num = resolved.get("numero")
    res_anno = resolved.get("anno")
    if res_num is not None and res_anno is not None and (res_num != numero or res_anno != anno):
        return (
            "inesistente",
            f"La ricerca ha restituito Cass. n. {res_num}/{res_anno}, "
            f"diversa da quella citata (n. {numero}/{anno}).",
        )

    # Metadata cross-check: requested section vs resolved section.
    res_sez = resolved.get("sezione", "")
    if sezione_req and res_sez and sezione_req != res_sez:
        return (
            "metadati discordanti",
            f"Sezione citata ({sezione_req}) diversa dalla sezione effettiva ({res_sez}). "
            f"Cass. n. {numero}/{anno}.",
        )

    return "verificata", f"Cass. n. {numero}/{anno} reperita su Italgiure."


async def _verifica_citazioni_impl(citazioni: str, archivio: str = "tutti") -> str:
    """Implementation of verifica_citazioni (testable without MCP wrapper)."""
    refs = _split_citazioni(citazioni)
    if not refs:
        return "**Errore**: nessuna citazione fornita. Inserire un riferimento per riga."

    truncated = len(refs) > _MAX_CITAZIONI
    refs = refs[:_MAX_CITAZIONI]

    tipi = [_classify_citazione(r) for r in refs]

    semaphore = asyncio.Semaphore(_MAX_CONCURRENT_VERIFICHE)

    async def _resolve_one(reference: str, tipo: str) -> tuple[str, str, str]:
        async with semaphore:
            try:
                if tipo == "sentenza":
                    verdetto, nota = await _verifica_sentenza(reference, archivio)
                elif tipo == "norma":
                    verdetto, nota = await _verifica_norma(reference)
                else:
                    return ("Non interpretabile", "—", "Formato non riconosciuto.")
            except Exception as exc:  # fail-safe: never crash the whole batch
                return (tipo.capitalize(), "non verificata", f"Errore durante la verifica: {exc}")
            return (tipo.capitalize(), verdetto, nota)

    results = await asyncio.gather(
        *(_resolve_one(r, t) for r, t in zip(refs, tipi))
    )

    lines = [
        "| # | Citazione | Tipo | Verdetto | Note/Fonte |",
        "|---|-----------|------|----------|------------|",
    ]
    for i, (reference, (tipo_label, verdetto, nota)) in enumerate(zip(refs, results), start=1):
        cit = reference.replace("|", "\\|")
        nota_clean = (nota or "—").replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {i} | {cit} | {tipo_label} | {verdetto} | {nota_clean} |")

    if truncated:
        lines.append("")
        lines.append(
            f"> *Verificate solo le prime {_MAX_CITAZIONI} citazioni "
            "(limite per chiamata).*"
        )

    lines.append("")
    lines.append(
        "> **Nota**: la verifica accerta l'**esistenza** della fonte e la coerenza "
        "dei **metadati** (numero, anno, sezione, comma/lettera citati). NON verifica "
        "l'esattezza del **principio di diritto** o del contenuto citato."
    )
    return "\n".join(lines)


@mcp.tool(tags={"normativa"})
async def verifica_citazioni(citazioni: str, archivio: str = "tutti") -> str:
    """Verifica l'esistenza e la coerenza dei metadati di un elenco di citazioni legali.

    Accetta un insieme di riferimenti — sentenze della Cassazione e/o articoli di legge —
    uno per riga (oppure separati da virgola) e, per ciascuno, controlla che la fonte
    esista realmente e che i metadati citati (numero, anno, sezione per le sentenze;
    comma/lettera per le norme) siano coerenti con la fonte ufficiale.

    Le sentenze sono risolte su Italgiure (`leggi_sentenza`), le norme su Normattiva/EUR-Lex
    (`cite_law`). Utile per controllare le citazioni di un atto, un parere o un testo prodotto
    da un altro modello prima di farne uso.

    ATTENZIONE: questo tool verifica l'**esistenza** della fonte e i **metadati**, NON
    l'esattezza del principio di diritto o del contenuto sostanziale citato.

    Verdetti possibili:
      - **verificata** — la fonte esiste e i metadati coincidono
      - **inesistente** — la decisione non risulta negli archivi (o la ricerca ha restituito
        una decisione diversa da quella citata)
      - **non trovata** — l'atto/articolo non è reperibile
      - **metadati discordanti** — la fonte esiste ma sezione/comma/lettera non coincidono
      - **non verificabile** — sentenza anteriore al 2020 (fuori archivio Italgiure)
      - **non verificata** — fonte temporaneamente non raggiungibile
      - **Non interpretabile** — formato del riferimento non riconosciuto

    Args:
        citazioni: Elenco di riferimenti, uno per riga (o separati da virgola), es.
                   "Cass. sez. III n. 12345/2024\\nart. 2043 c.c.\\nart. 13 GDPR"
        archivio: Archivio Italgiure per le sentenze: "civile", "penale" o "tutti" (default)
    """
    return await _verifica_citazioni_impl(citazioni, archivio)

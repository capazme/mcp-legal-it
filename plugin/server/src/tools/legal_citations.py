"""Recupero testi normativi ufficiali da Normattiva (leggi italiane), EUR-Lex (normativa UE)
e Brocardi (annotazioni dottrinali e giurisprudenziali). Usare cite_law() come punto di ingresso
principale prima di citare qualsiasi norma in un parere o documento legale."""

import os
import re
import tempfile
import time

from src.server import mcp
from src.lib.visualex import Norma, NormaVisitata, resolve_atto
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

def _parse_reference(reference: str) -> tuple[str, str]:
    """Parse a legal reference like 'art. 13 GDPR' into (article, act_name).

    Supports:
    - "art. 13 GDPR"
    - "art. 2-ter D.Lgs. 196/2003"
    - "ART 117 Costituzione"
    - "art. 2043 c.c."
    - "art. 6 D.Lgs. 231/2001"
    """
    reference = reference.strip()

    # Pattern: art[.] <number[-ext]> <act_name>
    match = re.match(
        r"(?:articol[oi]|art)\.?\s*(\d+(?:[-/.]\w+)*)\s+(.+)",
        reference,
        re.IGNORECASE,
    )
    if match:
        return match.group(1).strip(), match.group(2).strip()

    # No "art." prefix — try to parse as just act name (no article)
    return "", reference


def _resolve_act(act_name: str) -> dict | None:
    """Resolve act name to scraper parameters {tipo_atto, data, numero_atto}.

    Resolution chain:
    1. resolve_atto() — ATTI_NOTI + codici + abbreviations
    2. Pattern: "D.Lgs. NNN/YYYY" or "L. NNN/YYYY" — direct parse
    """
    # 1. Try the resolution chain
    result = resolve_atto(act_name)
    if result:
        return result

    # 2. Pattern: "regolamento UE 2025/327", "direttiva UE 2022/2555"
    eu_match = re.match(
        r"(regolamento|direttiva)\s+UE\s+(\d{4})/(\d+)",
        act_name,
        re.IGNORECASE,
    )
    if eu_match:
        tipo_raw, anno, numero = eu_match.groups()
        tipo_ue = {"regolamento": "regolamento ue", "direttiva": "direttiva ue"}
        return {"tipo_atto": tipo_ue[tipo_raw.lower()], "data": anno, "numero_atto": numero}

    # 3a. Long form with Italian date: "D.M. 10 marzo 2014 n. 55", "D.Lgs. 30 giugno 2003, n. 196"
    _MESI_IT = {
        "gennaio": "01", "febbraio": "02", "marzo": "03", "aprile": "04",
        "maggio": "05", "giugno": "06", "luglio": "07", "agosto": "08",
        "settembre": "09", "ottobre": "10", "novembre": "11", "dicembre": "12",
    }
    long_match = re.match(
        r"(D\.?Lgs\.?|D\.?L\.?|D\.?M\.?|D\.?P\.?C\.?M\.?|L\.?|DPR|D\.?P\.?R\.?|R\.?D\.?)"
        r"\s+(\d{1,2})\s+(gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre)"
        r"\s+(\d{4})[,]?\s*n\.?\s*(\d+)",
        act_name,
        re.IGNORECASE,
    )
    if long_match:
        tipo_raw, giorno, mese_it, anno, numero = long_match.groups()
        mese = _MESI_IT[mese_it.lower()]
        data = f"{anno}-{mese}-{giorno.zfill(2)}"
        tipo_map_local = {
            "dlgs": "decreto legislativo", "d.lgs.": "decreto legislativo", "d.lgs": "decreto legislativo",
            "dl": "decreto legge", "d.l.": "decreto legge", "d.l": "decreto legge",
            "dm": "decreto ministeriale", "d.m.": "decreto ministeriale", "d.m": "decreto ministeriale",
            "dpcm": "decreto del presidente del consiglio dei ministri",
            "d.p.c.m.": "decreto del presidente del consiglio dei ministri",
            "d.p.c.m": "decreto del presidente del consiglio dei ministri",
            "l": "legge", "l.": "legge",
            "dpr": "decreto del presidente della repubblica",
            "d.p.r.": "decreto del presidente della repubblica", "d.p.r": "decreto del presidente della repubblica",
            "rd": "regio decreto", "r.d.": "regio decreto", "r.d": "regio decreto",
        }
        tipo_normalized = tipo_map_local.get(tipo_raw.lower().rstrip("."), tipo_raw.lower())
        return {"tipo_atto": tipo_normalized, "data": data, "numero_atto": numero}

    # 3b. Short form: "D.Lgs. 196/2003", "L. 241/1990", "DPR 380/2001", "D.M. 55/2014"
    match = re.match(
        r"(D\.?Lgs\.?|D\.?L\.?|D\.?M\.?|D\.?P\.?C\.?M\.?|L\.?|DPR|D\.?P\.?R\.?|R\.?D\.?)\s*(\d+)/(\d{4})",
        act_name,
        re.IGNORECASE,
    )
    if match:
        tipo_raw, numero, anno = match.groups()
        tipo_map = {
            "dlgs": "decreto legislativo",
            "d.lgs.": "decreto legislativo",
            "d.lgs": "decreto legislativo",
            "dl": "decreto legge",
            "d.l.": "decreto legge",
            "d.l": "decreto legge",
            "dm": "decreto ministeriale",
            "d.m.": "decreto ministeriale",
            "d.m": "decreto ministeriale",
            "dpcm": "decreto del presidente del consiglio dei ministri",
            "d.p.c.m.": "decreto del presidente del consiglio dei ministri",
            "d.p.c.m": "decreto del presidente del consiglio dei ministri",
            "l": "legge",
            "l.": "legge",
            "dpr": "decreto del presidente della repubblica",
            "d.p.r.": "decreto del presidente della repubblica",
            "d.p.r": "decreto del presidente della repubblica",
            "rd": "regio decreto",
            "r.d.": "regio decreto",
            "r.d": "regio decreto",
        }
        tipo_normalized = tipo_map.get(tipo_raw.lower().rstrip("."), tipo_raw.lower())
        return {"tipo_atto": tipo_normalized, "data": anno, "numero_atto": numero}

    return None


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
        return f"**Errore**: atto '{act_name}' non riconosciuto. Prova con il nome completo (es. 'D.Lgs. 196/2003') o usa fetch_law_article() con parametri espliciti."

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

    Args:
        reference: Riferimento normativo, es. "art. 13 GDPR", "art. 2043 c.c.",
                   "art. 6 D.Lgs. 231/2001", "art. 117 Costituzione"
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
        return f"**Errore**: atto '{act_name}' non riconosciuto."

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
        return f"**Errore**: atto '{act_name}' non riconosciuto."

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
        return f"**Errore**: atto '{act_name}' non riconosciuto."

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
        return f"**Errore**: atto '{act_name}' non riconosciuto. Prova con il nome completo (es. 'D.Lgs. 196/2003')."

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

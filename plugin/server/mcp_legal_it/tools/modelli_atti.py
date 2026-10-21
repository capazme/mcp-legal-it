"""Catalogo e dispatcher per 100 modelli di atti legali italiani.

Fornisce genera_modello_atto() che restituisce i metadati necessari per comporre
qualsiasi tipo di atto: struttura, campi, tool di calcolo da chiamare, resource
modello da leggere, riferimenti normativi e avvertenze.
"""

import json
from pathlib import Path

from mcp_legal_it.server import mcp
from mcp_legal_it.lib._data import sourced
from mcp_legal_it.lib._output import OUTPUT_DIR, ensure_private_dir

_OUTPUT_DIR = OUTPUT_DIR

_DATA = Path(__file__).resolve().parent.parent / "data"

with open(_DATA / "modelli_atti.json", encoding="utf-8") as f:
    _CATALOGO: dict[str, dict] = {
        k: v for k, v in json.load(f).items() if not k.startswith("_")
    }  # `_`-prefixed keys are metadata (see mcp_legal_it/lib/_data.py), not records

# Reverse index: map tool names and keywords to tipo_atto entries
_CATEGORIE = sorted({v["categoria"] for v in _CATALOGO.values()})


@mcp.tool(tags={"redazione", "atti"})
@sourced("modelli_atti")
def genera_modello_atto(tipo_atto: str, parametri: dict | None = None) -> dict:
    """Restituisce i metadati per comporre un atto legale: struttura, campi obbligatori,
    tool di calcolo da chiamare, resource modello da leggere, e riferimenti normativi.

    Chiamare PRIMA di redigere un atto per conoscere struttura e requisiti.
    Per l'elenco completo dei tipi disponibili, chiamare con tipo_atto="catalogo".
    Per cercare per categoria, chiamare con tipo_atto="cerca" e parametri={"query": "termine"}.
    Precisione: INDICATIVO (catalogo redazionale interno: struttura e campi vanno
    adattati al caso concreto e alle prassi del giudice adito).

    Args:
        tipo_atto: Identificativo del tipo di atto. Usare "catalogo" per l'elenco completo,
                   "cerca" per cercare per parola chiave.
        parametri: Parametri opzionali dell'atto (per validazione campi obbligatori) o
                   {"query": "termine"} quando tipo_atto="cerca"
    """
    if parametri is None:
        parametri = {}

    # Catalog mode: return all available types grouped by category
    if tipo_atto == "catalogo":
        catalogo_per_categoria: dict[str, list[dict]] = {}
        for k, v in _CATALOGO.items():
            cat = v["categoria"]
            if cat not in catalogo_per_categoria:
                catalogo_per_categoria[cat] = []
            catalogo_per_categoria[cat].append({
                "tipo_atto": k,
                "descrizione": v["descrizione"],
                "tier": v["tier"],
            })
        return {
            "totale_tipi": len(_CATALOGO),
            "categorie": _CATEGORIE,
            "catalogo": catalogo_per_categoria,
        }

    # Search mode: find types matching a keyword
    if tipo_atto == "cerca":
        query = parametri.get("query", "").lower()
        if not query:
            return {"errore": "Specificare parametri={'query': 'termine'} per la ricerca"}
        risultati = []
        for k, v in _CATALOGO.items():
            searchable = f"{k} {v['descrizione']} {v['categoria']} {' '.join(v.get('riferimenti_normativi', []))}".lower()
            if query in searchable:
                risultati.append({
                    "tipo_atto": k,
                    "descrizione": v["descrizione"],
                    "categoria": v["categoria"],
                    "tier": v["tier"],
                })
        return {
            "query": query,
            "risultati": risultati,
            "totale": len(risultati),
        }

    # Lookup specific type
    entry = _CATALOGO.get(tipo_atto)
    if entry is None:
        # Fuzzy match: try substring matching
        candidati = [
            {"tipo_atto": k, "descrizione": v["descrizione"]}
            for k, v in _CATALOGO.items()
            if tipo_atto.lower() in k.lower() or tipo_atto.lower() in v["descrizione"].lower()
        ]
        return {
            "errore": f"Tipo atto '{tipo_atto}' non trovato nel catalogo",
            "suggerimenti": candidati[:10] if candidati else [],
            "nota": "Usare tipo_atto='catalogo' per l'elenco completo",
        }

    routing = entry["routing"]
    campi_obbligatori = entry["campi_obbligatori"]

    # Validate provided parameters against required fields
    campi_mancanti = [c for c in campi_obbligatori if c not in parametri] if parametri else campi_obbligatori

    # Build routing info
    result = {
        "tipo_atto": tipo_atto,
        "categoria": entry["categoria"],
        "descrizione": entry["descrizione"],
        "campi_obbligatori": campi_obbligatori,
        "campi_opzionali": entry.get("campi_opzionali", []),
        "campi_mancanti": campi_mancanti,
        "tool_calcolo": entry.get("tool_calcolo", []),
        "riferimenti_normativi": entry.get("riferimenti_normativi", []),
        "avvertenze": entry.get("avvertenze", []),
    }

    # Routing-specific info
    if routing["tipo"] == "tool_diretto":
        result["tool_diretto"] = routing["tool"]
        result["parametri_fissi"] = routing.get("parametri_fissi", {})
        result["istruzioni"] = f"Chiamare il tool `{routing['tool']}` con i parametri indicati."
    elif routing["tipo"] == "tool_enhance":
        result["tool_diretto"] = routing["tool"]
        result["parametri_fissi"] = routing.get("parametri_fissi", {})
        fase = routing.get("fase", 2)
        if routing.get("variante"):
            # etichetta della variante da adattare a mano: NON è un parametro del tool
            result["variante"] = routing["variante"]
        result["istruzioni"] = (
            f"Usare il tool `{routing['tool']}` per generare la base, "
            "poi adattare l'output ai campi specifici di questo tipo di atto."
        )
        result["disponibile_da_fase"] = fase
    elif routing["tipo"] == "resource":
        result["resource_modello"] = routing["resource"]
        fase = routing.get("fase", 3)
        result["istruzioni"] = (
            f"Resource `{routing['resource']}` non ancora disponibile (Fase {fase}); "
            "comporre l'atto manualmente seguendo la struttura e i campi indicati, "
            "e chiamare i tool di calcolo indicati."
        )
        result["disponibile_da_fase"] = fase
    elif routing["tipo"] == "preventivo_procedura":
        result["tool_diretto"] = "preventivo_civile"
        result["tool_non_ancora_disponibile"] = "preventivo_procedura"
        result["parametri_fissi"] = routing.get("parametri_fissi", {})
        fase = routing.get("fase", 4)
        result["istruzioni"] = (
            f"Questo preventivo sarà supportato nella Fase {fase} via `preventivo_procedura()`. "
            "Nel frattempo, usare `preventivo_civile()` come approssimazione."
        )
        result["disponibile_da_fase"] = fase

    return result


@mcp.tool(tags={"redazione", "atti"})
def esporta_atto_docx(
    testo: str,
    titolo: str = "Atto",
    autore: str = "",
) -> str:
    """Esporta un testo (atto, parere, bozza) in formato DOCX (Microsoft Word).

    Accetta testo in formato Markdown semplice e produce un file .docx formattato.
    Usare dopo aver generato un atto con genera_modello_atto() o un parere con il prompt parere_legale.
    Il file viene salvato nella directory temporanea e il percorso restituito.

    Args:
        testo: Testo dell'atto in formato Markdown (supporta: # titoli, **grassetto**, *corsivo*, - elenchi, paragrafi)
        titolo: Titolo del documento (usato come nome file e intestazione)
        autore: Nome dell'autore (opzionale, inserito nei metadati del documento)
    """
    try:
        from docx import Document
        from docx.opc.constants import RELATIONSHIP_TYPE as RT  # noqa: F401
    except ImportError:
        return "Errore: python-docx non installato. Eseguire: pip install python-docx"

    if not testo or not testo.strip():
        return "Errore: il testo dell'atto è vuoto."

    import re

    def _sanitize_filename(name: str) -> str:
        name = name.lower().replace(" ", "_")
        name = re.sub(r"[^a-z0-9_\-]", "", name)
        return name[:50] or "atto"

    def _add_runs(para, text):
        # Split on bold italic (***...***), bold (**...**) and italic (*...*),
        # longest marker first so "***x***" is not read as "**" + "*x*" + "*".
        parts = re.split(r"(\*\*\*[^*]+\*\*\*|\*\*[^*]+\*\*|\*[^*]+\*)", text)
        for part in parts:
            if len(part) > 6 and part.startswith("***") and part.endswith("***"):
                run = para.add_run(part[3:-3])
                run.bold = True
                run.italic = True
            elif len(part) > 4 and part.startswith("**") and part.endswith("**"):
                run = para.add_run(part[2:-2])
                run.bold = True
            elif len(part) > 2 and part.startswith("*") and part.endswith("*"):
                run = para.add_run(part[1:-1])
                run.italic = True
            elif part:
                para.add_run(part)
        return para

    def _add_formatted_paragraph(doc, text, style=None):
        para = doc.add_paragraph(style=style) if style else doc.add_paragraph()
        return _add_runs(para, text)

    def _new_numbered_list(doc, start):
        """A fresh 'List Number' list that Word starts at `start` (the number the text typed)."""
        numbering = doc.part.numbering_part.numbering_definitions._numbering
        style_num_id = doc.styles["List Number"].element.pPr.numPr.numId.val
        abstract_id = numbering.num_having_numId(style_num_id).abstractNumId.val
        num = numbering.add_num(abstract_id)
        num.add_lvlOverride(ilvl=0).add_startOverride(start)
        return num.numId

    def _add_numbered_item(doc, text, num_id):
        para = _add_formatted_paragraph(doc, text, style="List Number")
        num_pr = para._p.get_or_add_pPr().get_or_add_numPr()
        num_pr.get_or_add_ilvl().val = 0
        num_pr.get_or_add_numId().val = num_id
        return para

    doc = Document()

    # Set core properties
    props = doc.core_properties
    props.title = titolo
    if autore:
        props.author = autore

    # The title heads every page, so it is in the document and not only in its metadata.
    doc.sections[0].header.paragraphs[0].text = titolo

    # Numbered items keep the number the text typed: an item that does not follow
    # the previous one (1, 2 ... 1, 2 ... 10) starts a new list from its own number.
    list_num_id = None
    next_number = None

    lines = testo.split("\n")
    for line in lines:
        stripped = line.rstrip()

        heading = re.match(r"^(#{1,3}) (.*)$", stripped)
        if heading:
            _add_runs(doc.add_heading("", level=len(heading.group(1))), heading.group(2))
        elif re.match(r"^[-*] ", stripped):
            _add_formatted_paragraph(doc, stripped[2:], style="List Bullet")
        elif re.match(r"^\d+\. ", stripped):
            typed = int(re.match(r"^(\d+)\. ", stripped).group(1))
            if list_num_id is None or typed != next_number:
                list_num_id = _new_numbered_list(doc, typed)
            next_number = typed + 1
            content = re.sub(r"^\d+\. ", "", stripped)
            _add_numbered_item(doc, content, list_num_id)
        elif stripped.startswith("> "):
            para = _add_formatted_paragraph(doc, stripped[2:])
            for run in para.runs:
                run.italic = True
        elif stripped == "":
            doc.add_paragraph()
        else:
            _add_formatted_paragraph(doc, stripped)

    # Save to temp file
    import os
    import uuid
    tmp_dir = ensure_private_dir(_OUTPUT_DIR)
    filename = f"{_sanitize_filename(titolo)}_{uuid.uuid4().hex[:8]}.docx"
    filepath = os.path.join(tmp_dir, filename)
    doc.save(filepath)

    size_kb = round(os.path.getsize(filepath) / 1024, 1)
    return f"File salvato: {filepath} ({size_kb} KB)"


@mcp.tool(tags={"redazione", "atti"})
@sourced("modelli_atti")
def lista_categorie_atti() -> dict:
    """Restituisce le categorie di atti disponibili con il conteggio per ciascuna.
    Utile per orientare l'utente nella scelta del tipo di atto.
    Precisione: INDICATIVO (catalogo redazionale interno: la categoria orienta la
    scelta, non sostituisce la qualificazione dell'atto).
    """
    conteggio: dict[str, int] = {}
    for v in _CATALOGO.values():
        cat = v["categoria"]
        conteggio[cat] = conteggio.get(cat, 0) + 1
    return {
        "categorie": [
            {"nome": cat, "totale": conteggio[cat]}
            for cat in sorted(conteggio, key=conteggio.get, reverse=True)
        ],
        "totale_atti": len(_CATALOGO),
    }

#!/usr/bin/env python3
"""legal-it — Stop/SubagentStop hook: the citation gate of the Legal Grounding Protocol.

An answer must not cite a norm or a decision the session has not read with a
tool. This hook reads what the turn wrote and what the session's tools
returned, and asks for the missing reads once per turn. It is advisory and
fails open: any error, a missing transcript or a second stop in the same turn
lets the answer through.

What it reads (the turn: everything since the user's last prompt)
- every assistant text block, not only the last one;
- the text written through Write/Edit/MultiEdit into prose files (.md, .txt,
  .html, ...; source code quotes things, it does not assert them) and the
  inputs of the document tools (esporta_atto_docx, genera_*).
Fenced and inline code is skipped. A line that says "fuori copertura" is the
explicit escape for a source no tool covers (CDF, CEDU, allegati UE...).

How a citation is read
With the server's own code (mcp_legal_it.core.citazioni): the act is resolved
by the resolver cite_law uses and identified by the URL cite_law would fetch,
so "codice privacy" and "D.Lgs. 196/2003" are one act and "art. 2 Cost." is
not "art. 2 c.p.". The key is (act, article with suffix). Decisions are
(court, number, year): Cassazione, Corte costituzionale, TAR/Consiglio di
Stato, CGUE cases.

What counts as read (anywhere in the session, subagents of this session included)
- a norm: a cite_law / fetch_law_article result that returned that article
  (not an error, not another article), or a fetch_full_act result whose text
  contains it. cite_law's JSON format is read from its own atto+articolo;
- a decision: a leggi_*/cerca_* (or *_su_norma, ultime_*) result of the same
  court whose text carries that number and year.

The server's code is imported from the plugin (stdlib only, no HTTP stack);
if that import fails, a reduced stdlib reader keeps the gate working.

Opt-out: ``LEGAL_CITATION_GATE=off`` (also ``0``, ``false``, ``no``; any case)
switches the gate off for that session. It is meant for software-development
sessions that only happen to quote a norm in code or docs; legal work should
keep it on. The check is the first thing ``main`` does: no stdin, no
transcript, no reader import.
"""
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

SILENT, BLOCK = 0, 2

# Values of LEGAL_CITATION_GATE that switch the gate off (compared lowercase).
OPT_OUT_VALUES = {"off", "0", "false", "no"}

# Tools whose result can show that an article was read.
NORM_TOOLS = {"cite_law", "fetch_law_article", "fetch_full_act"}

# Tools whose result can show that a decision was read, per court: the court's
# readers and searches (leggi_*, cerca_*, *_su_norma, ultime_*). Not Brocardi's
# abstracts nor the orientation maps: a massima is not the decision.
DECISION_TOOLS = {
    "cass": {"leggi_sentenza", "cerca_giurisprudenza", "giurisprudenza_su_norma", "ultime_pronunce",
             # Cassazione tributaria is published on CeRDEF too.
             "cerca_giurisprudenza_tributaria", "cerdef_leggi_provvedimento",
             "ultime_sentenze_tributarie"},
    "cost": {"leggi_pronuncia_costituzionale", "cerca_pronuncia_costituzionale",
             "pronunce_cost_su_norma", "ultime_pronunce_cost"},
    "amm": {"leggi_provvedimento_amm", "cerca_giurisprudenza_amministrativa",
            "giurisprudenza_amm_su_norma", "ultimi_provvedimenti_amm"},
    "cgue": {"leggi_sentenza_cgue", "cerca_giurisprudenza_cgue", "giurisprudenza_cgue_su_norma",
             "ultime_sentenze_cgue"},
}
# Lists hits of every court, one "## <source>" section each.
UNIFIED_SEARCH = "cerca_giurisprudenza_unificata"
UNIFIED_SECTIONS = (("cassazione", "cass"), ("tributaria", "cass"), ("amministrativa", "amm"),
                    ("tar", "amm"), ("cgue", "cgue"), ("costituzional", "cost"))

# A decision counts only where the result names it: the heading of a reader
# ("# Cass. civ., sez. III, n. 12345/2024") or of a search hit ("### ..."), and its
# **Estremi** / **Causa** / **ECLI** lines. Not the body: a decision cites precedents
# and acts ("Cass. n. 5678/2015", "D.Lgs. 196/2003") that the session has not read.
_HEADING = re.compile(r"^ {0,3}(#{1,6})\s")
_DECISION_META = re.compile(r"^\s*\*\*(?:Estremi|Causa|ECLI)\*\*\s*:", re.I)
TOOL_PER_CORTE = {
    "cass": "leggi_sentenza", "cost": "leggi_pronuncia_costituzionale",
    "amm": "cerca_giurisprudenza_amministrativa + leggi_provvedimento_amm",
    "cgue": "cerca_giurisprudenza_cgue + leggi_sentenza_cgue",
}
ALL_TOOLS = NORM_TOOLS.union(*DECISION_TOOLS.values(), {UNIFIED_SEARCH})

# Files whose text is prose: what is written there is asserted, like an answer.
PROSE_SUFFIXES = {"", ".md", ".markdown", ".txt", ".text", ".rtf", ".html", ".htm",
                  ".tex", ".rst", ".adoc", ".org"}

ESCAPE = "fuori copertura"
MAX_LISTED = 12
# Characters of one turn the gate reads (about 150 pages): beyond that a turn is a
# bulk export, and an advisory check must not slow every Stop down.
MAX_TURN_CHARS = 400_000
_TOOL_USE_ID = re.compile(r'"tool_use_id"\s*:\s*"([^"]+)"')
_INLINE_CODE = re.compile(r"`[^`\n]*`")


# ---------------------------------------------------------------------------
# The reader: the server's code, or a reduced stdlib stand-in
# ---------------------------------------------------------------------------

def load_reader():
    """``mcp_legal_it.core.citazioni`` from the plugin's server folder, else None."""
    server = str(HERE.parent / "server")
    if server not in sys.path:
        sys.path.insert(0, server)
    try:
        from mcp_legal_it.core import citazioni
        return citazioni
    except Exception:
        return None


class FallbackReader:
    """What the gate can still read when the server's code does not import.

    Only the forms that matter most: an article followed by a code or by an
    act written as type + number/year, and "Cass. ... n. N/AAAA". Its keys are
    coarse but shared by both sides (prose and tool results), so a citation
    read with cite_law is still recognised.
    """

    _CODICI = {
        "cc": "codice civile", "codciv": "codice civile", "codicecivile": "codice civile",
        "cp": "codice penale", "codpen": "codice penale", "codicepenale": "codice penale",
        "cpc": "codice di procedura civile", "codicediproceduracivile": "codice di procedura civile",
        "cpp": "codice di procedura penale", "codicediprocedurapenale": "codice di procedura penale",
        "cost": "costituzione", "costituzione": "costituzione",
        "gdpr": "regolamento ue|679|2016", "rgpd": "regolamento ue|679|2016",
    }
    _TIPI = {"dlgs": "decreto legislativo", "dl": "decreto legge", "l": "legge", "legge": "legge",
             "dpr": "decreto del presidente della repubblica", "dm": "decreto ministeriale"}
    # Bounded separators: "\s*-?\s*" split a run of spaces two ways (quadratic).
    _SUFFIX = r"(?:[ \t]?-?[ \t]?(?:bis|ter|quater|quinquies|sexies|septies|octies|novies|decies)\b)?"
    _ART = re.compile(r"\b(?:artt?|articol[oi])\b\.?\s*(\d+" + _SUFFIX + r")\b"
                      r"[\s,]*(?:(?:comma|co|c)\.?[ \t]?(?P<comma>\d+" + _SUFFIX + r")\b[\s,]*)?"
                      r"(?:(?:della|dello|dell['’]|del)\s*)?(?P<atto>[^\n;]{0,40})", re.I)
    _COMMA_PRIMA = re.compile(r"\bcomma[ \t]+(\d+" + _SUFFIX + r")[ \t]*,?[ \t]*(?:dell['’]|del|dello)?[ \t]*$", re.I)
    _TESTO_PARZIALE = re.compile(
        r"testo parziale: (?:commi (\d+(?:-[a-z]+)?)-(\d+(?:-[a-z]+)?)|una sola parte) di ", re.I)
    _ATTO_NUM = re.compile(r"^(d\.?\s?lgs|d\.?\s?l|l|legge|d\.?p\.?r|d\.?\s?m)\.?\s*(?:n\.?\s*)?(\d+)\s*(?:/|\s+del\s+)\s*(\d{4})", re.I)
    _CASS = re.compile(r"\bcass(?:azione)?\b[^\n]{0,80}?\bn\.?\s*(\d{1,6})\s*(?:/|\s+del\s+)\s*((?:19|20)\d{2})", re.I)
    _ATTO_PRIMA = re.compile(r"\b(?:d\.?\s?lgs|d\.?\s?l|l|legge|d\.?p\.?r|d\.?\s?m|reg(?:olamento)?|dir(?:ettiva)?)\.?\s*(?:n\.?\s*)?$", re.I)
    _NUM = re.compile(r"(?<![\d/.])(\d{1,6})\s*/\s*((?:19|20)\d{2})(?![\d/])|\bn\.?\s*(\d{1,6})\s+del\s+((?:19|20)\d{2})", re.I)

    @staticmethod
    def normalizza_articolo(articolo):
        return re.sub(r"[\s\-.]", "", (articolo or "").lower())

    def _atto(self, testo):
        testo = testo.strip()
        m = self._ATTO_NUM.match(testo)
        if m:
            tipo = self._TIPI.get(re.sub(r"[.\s]", "", m.group(1).lower()))
            return f"{tipo}|{int(m.group(2))}|{m.group(3)}" if tipo else None
        for parole in (3, 2, 1):
            chiave = re.sub(r"[.\s']", "", " ".join(testo.split()[:parole]).lower()).rstrip(",:)")
            if chiave in self._CODICI:
                return self._CODICI[chiave]
        return None

    @staticmethod
    def canonico_comma(comma):
        m = re.match(r"\s*(\d+)[ \t]?-?[ \t]?([a-z]+)?\s*$", comma or "", re.I)
        return (m.group(1) + (f"-{m.group(2).lower()}" if m.group(2) else "")) if m else (comma or "").lower()

    def norme_nel_testo(self, testo):
        out = []
        for m in self._ART.finditer(testo):
            atto = self._atto(m.group("atto"))
            if atto:
                comma = m.group("comma")
                if comma is None:
                    prima = self._COMMA_PRIMA.search(testo[max(0, m.start() - 40): m.start()])
                    comma = prima.group(1) if prima else None
                out.append(_Norma(atto, self.normalizza_articolo(m.group(1)), m.group(0)[:80],
                                  self.canonico_comma(comma) if comma else None))
        return out

    def commi_letti(self, testo):
        m = self._TESTO_PARZIALE.search(testo or "")
        if m is None:
            return None
        if m.group(1) is None:
            return ("?", "?")  # a part not named: partial, and no comma lies in it
        return (self.canonico_comma(m.group(1)), self.canonico_comma(m.group(2)))

    @staticmethod
    def comma_nell_intervallo(comma, dal, al):
        numeri = [re.match(r"\s*(\d+)", c or "") for c in (comma, dal, al)]
        if not all(numeri):
            return False
        n, a, b = (int(x.group(1)) for x in numeri)
        return a <= n <= b

    def decisioni_nel_testo(self, testo):
        return [_Decisione("cass", str(int(m.group(1))), int(m.group(2)), m.group(0)[-60:])
                for m in self._CASS.finditer(testo)]

    def decisioni_nel_risultato(self, testo):
        out = set()
        for m in self._NUM.finditer(testo):
            if self._ATTO_PRIMA.search(testo, max(0, m.start() - 25), m.start()):
                continue
            numero, anno = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
            out.add((str(int(numero)), int(anno)))
        return out

    def articolo_servito(self, testo):
        corpo = next((r for r in testo.splitlines() if r.strip() and not r.lstrip().startswith("**")), "")
        m = re.match(r"^[ \t]*(?:#+[ \t]*)?art(?:icolo)?\.?[ \t]*(\d+" + self._SUFFIX + ")", corpo, re.I)
        return self.normalizza_articolo(m.group(1)) if m else None

    def articoli_serviti(self, testo):
        # As core/citazioni.corpo_della_finestra: a window may cut a heading at either end.
        # Known limit there too: a genuine heading on a window's edge line is not credited.
        finestra = re.search(r"\n\*\[Caratteri (\d+)-\d+ su \d+ totali: ([^\]\n]*)\]\*[ \t\n]*$", testo)
        if finestra:
            righe = testo[: finestra.start()].rstrip().split("\n")
            while righe and (not righe[-1].strip() or re.match(r"^\*\[[^\n]*\]\*$", righe[-1].strip())):
                righe.pop()
            if "per leggere il seguito" in finestra.group(2) and righe:
                righe.pop()
            if int(finestra.group(1)) > 1:
                dimensione = next((i for i, r in enumerate(righe) if r.startswith("**Dimensione**:")), None)
                if dimensione is not None:
                    primo = next((i for i in range(dimensione + 1, len(righe)) if righe[i].strip()), None)
                else:
                    primo = next((i for i, r in enumerate(righe)
                                  if r.strip() and not r.lstrip().startswith(("#", "**"))), None)
                if primo is not None:
                    del righe[primo]
            testo = "\n".join(righe) + "\n"
        return {self.normalizza_articolo(m.group(1)) for m in
                re.finditer(r"^[ \t]*(?:#+[ \t]*)?art(?:icolo)?\.?[ \t]*(\d+" + self._SUFFIX + ")", testo, re.I | re.M)}

    def riferimento_in_identita(self, riferimento):
        m = re.match(r"\s*(?:artt?|articol[oi])\b\.?\s*(\d+" + self._SUFFIX + r")[\s,]*(.*)", riferimento, re.I)
        if not m:
            atto = self._atto(riferimento)
            return (atto, "") if atto else None
        resto = re.sub(r"^(?:comma|co|c)\.?[ \t]?\d+" + self._SUFFIX + r"\b[\s,]*", "", m.group(2), flags=re.I)
        atto = self._atto(re.sub(r"^(?:della|dello|dell['’]|del)\s*", "", resto, flags=re.I))
        return (atto, self.normalizza_articolo(m.group(1))) if atto else None

    def identita_norma(self, act_info, articolo):
        tipo = (act_info.get("tipo_atto") or "").lower()
        if tipo in self._CODICI.values():
            return tipo, self.normalizza_articolo(articolo)
        numero = str(int(act_info["numero_atto"])) if str(act_info.get("numero_atto") or "").isdigit() else ""
        return f"{tipo}|{numero}|{(act_info.get('data') or '')[:4]}", self.normalizza_articolo(articolo)


class _Norma:
    def __init__(self, atto, articolo, testo, comma=None):
        self.atto, self.articolo, self.testo, self.comma = atto, articolo, testo, comma


class _Decisione:
    def __init__(self, corte, numero, anno, testo):
        self.corte, self.numero, self.anno, self.testo = corte, numero, anno, testo


# ---------------------------------------------------------------------------
# Transcript
# ---------------------------------------------------------------------------

def tool_name(raw: str) -> str:
    """ "mcp__plugin_legal-it_legal-it__cite_law" -> "cite_law"."""
    return (raw or "").rsplit("__", 1)[-1]


def result_text(content) -> str:
    """The text of a tool_result, with the FastMCP {"result": "..."} wrapper removed."""
    if isinstance(content, list):
        content = "\n".join(c.get("text") or "" for c in content
                            if isinstance(c, dict) and c.get("type") == "text")
    text = content if isinstance(content, str) else ""
    for _ in range(2):
        stripped = text.strip()
        if not stripped.startswith("{"):
            break
        try:
            body = json.loads(stripped)
        except ValueError:
            break
        if isinstance(body, dict) and set(body) == {"result"} and isinstance(body["result"], str):
            text = body["result"]
            continue
        break
    return text


def is_prompt(record: dict) -> bool:
    """A prompt typed by the user (not a tool result, not a meta message)."""
    if record.get("type") != "user" or record.get("isMeta"):
        return False
    content = (record.get("message") or {}).get("content")
    if isinstance(content, str):
        return True
    if isinstance(content, list):
        return not any(isinstance(c, dict) and c.get("type") == "tool_result" for c in content)
    return False


def records(path: Path, wanted_ids: "set | None" = None):
    """The transcript's records. A tool_result line is parsed only when its id is wanted."""
    try:
        handle = open(path, encoding="utf-8")
    except OSError:
        return
    with handle:
        for line in handle:
            if wanted_ids is not None and '"tool_result"' in line:
                # Results are most of a transcript's bytes: parse only the wanted ones.
                ids = _TOOL_USE_ID.findall(line)
                if ids and not wanted_ids.intersection(ids):
                    continue
            try:
                record = json.loads(line)
            except ValueError:
                continue
            if isinstance(record, dict):
                yield record


class Session:
    """What the session read (credits) and what the turn wrote (texts)."""

    def __init__(self, reader):
        self.reader = reader
        self.norms: set = set()
        # An article Normattiva splits into parts, read in part: the commi ranges read
        # («testo parziale: commi a-b di N»), and the articles read whole at least once.
        self.partial: dict = {}
        self.whole: set = set()
        self.decisions: set = set()
        self.calls: dict = {}  # tool_use id -> (name, input)
        self.texts: list = []

    # --- credits ---------------------------------------------------------------

    def credit(self, name: str, tool_input: dict, block: dict) -> None:
        if block.get("is_error"):
            return
        text = result_text(block.get("content"))
        try:
            if name in NORM_TOOLS:
                self._credit_norm(name, tool_input, text)
            if self._failed(text):
                return
            if name == UNIFIED_SEARCH:
                for court, section in unified_sections(text):
                    for numero, anno in self.reader.decisioni_nel_risultato(decision_headings(section)):
                        self.decisions.add((court, numero, anno))
                return
            # A reader serves one decision: its own heading. A search lists hits: theirs.
            reader_tool = name.startswith("leggi_") or name == "cerdef_leggi_provvedimento"
            headings = decision_headings(text, first_only=reader_tool)
            for court, tools in DECISION_TOOLS.items():
                if name in tools:
                    for numero, anno in self.reader.decisioni_nel_risultato(headings):
                        self.decisions.add((court, numero, anno))
        except Exception:
            return

    @staticmethod
    def _failed(text: str) -> bool:
        head = text.lstrip()[:300]
        return (not head or head.startswith(("**Errore", "Errore", "**Nessun", "Nessun"))
                or "non trovat" in head.lower())

    def _credit_norm(self, name: str, tool_input: dict, text: str) -> None:
        r = self.reader
        stripped = text.strip()
        if name == "fetch_full_act":
            if self._failed(text):
                return
            key = r.riferimento_in_identita(tool_input.get("reference") or "")
            if key:
                # Never in self.whole: its Normattiva-page fallback has only the first part of an
                # article Normattiva splits (#106), and its answer does not say which source served it.
                self.norms.update((key[0], a) for a in r.articoli_serviti(text))
            return
        body = None
        if stripped.startswith("{"):
            try:
                body = json.loads(stripped)
            except ValueError:
                body = None
        if isinstance(body, dict) and ("testo" in body or "errore" in body):
            # cite_law(formato="json"): the act and article it says it served.
            atto = body.get("atto") or {}
            if body.get("errore") or not body.get("testo") or not atto.get("tipo_atto"):
                return
            key = r.identita_norma(atto, body.get("articolo") or "")
            served = r.articolo_servito(body["testo"])
        elif isinstance(body, dict):
            return  # some other object: it shows no article
        else:
            if self._failed(text):
                return
            if name == "cite_law":
                key = r.riferimento_in_identita(tool_input.get("reference") or "")
            else:
                key = r.identita_norma({"tipo_atto": tool_input.get("act_type") or "",
                                        "data": tool_input.get("date") or "",
                                        "numero_atto": tool_input.get("act_number") or ""},
                                       tool_input.get("article") or "")
            served = r.articolo_servito(text)
        if not key or not key[1]:
            return
        if served and served != key[1]:
            return  # it answered with another article (the art. 99999 -> art. 1 case)
        self.norms.add(key)
        letti = r.commi_letti(text) if hasattr(r, "commi_letti") else None
        if letti:
            self.partial.setdefault(key, []).append(letti)
        else:
            self.whole.add(key)

    def read_credits(self, path: Path) -> None:
        """Credits from every tool result of one transcript."""
        calls: dict = {}
        wanted: set = set()
        for record in records(path, wanted):
            content = (record.get("message") or {}).get("content")
            if not isinstance(content, list):
                continue
            kind = record.get("type")
            for c in content:
                if not isinstance(c, dict):
                    continue
                if kind == "assistant" and c.get("type") == "tool_use":
                    name = tool_name(c.get("name"))
                    if name in ALL_TOOLS and c.get("id"):
                        calls[c["id"]] = (name, c.get("input") or {})
                        wanted.add(c["id"])
                elif kind == "user" and c.get("type") == "tool_result":
                    call = calls.get(c.get("tool_use_id"))
                    if call:
                        self.credit(call[0], call[1], c)

    # --- the turn ----------------------------------------------------------------

    def read_turn(self, path: Path) -> None:
        """The text the last turn wrote: answers, prose files, document tool inputs."""
        texts: list = []
        for record in records(path, set()):
            if is_prompt(record):
                texts = []
                continue
            if record.get("type") != "assistant":
                continue
            content = (record.get("message") or {}).get("content")
            if not isinstance(content, list):
                continue
            for c in content:
                if not isinstance(c, dict):
                    continue
                if c.get("type") == "text":
                    texts.append(c.get("text") or "")
                elif c.get("type") == "tool_use":
                    texts.extend(written_text(c.get("name") or "", c.get("input") or {}))
        self.texts = texts


def decision_headings(text: str, first_only: bool = False) -> str:
    """The heading lines of a decision result (see ``_HEADING``), with their metadata lines.

    ``first_only``: the opening heading of a reader, up to its first sub-heading
    ("## Testo"); a search keeps every hit's heading.
    """
    kept: list = []
    in_meta = False
    for line in text.splitlines():
        if _HEADING.match(line):
            if first_only and kept:
                break
            kept.append(line)
            in_meta = True
        elif in_meta and line.lstrip().startswith("**"):
            if _DECISION_META.match(line):
                kept.append(line)
        else:
            in_meta = False
    return "\n".join(kept)


def unified_sections(text: str):
    """``(court, section text)`` for each "## <source>" section of the unified search."""
    parts = re.split(r"(?m)^## ", text)
    for part in parts[1:]:
        label = part.split("\n", 1)[0].lower()
        court = next((c for key, c in UNIFIED_SECTIONS if key in label), None)
        if court:
            yield court, "\n".join(part.split("\n")[1:])


def written_text(raw_name: str, tool_input: dict) -> list:
    """The prose a tool call writes: Write/Edit into a prose file, or a document tool."""
    name = tool_name(raw_name)
    if name in ("Write", "Edit", "MultiEdit"):
        suffix = Path(str(tool_input.get("file_path") or "")).suffix.lower()
        if suffix not in PROSE_SUFFIXES:
            return []
        if name == "Write":
            return [str(tool_input.get("content") or "")]
        if name == "Edit":
            return [str(tool_input.get("new_string") or "")]
        return [str(e.get("new_string") or "") for e in tool_input.get("edits") or []
                if isinstance(e, dict)]
    if name == "esporta_atto_docx" or name.startswith("genera_"):
        return list(strings_in(tool_input))
    return []


def strings_in(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from strings_in(v)
    elif isinstance(value, list):
        for v in value:
            yield from strings_in(v)


def strip_code(text: str) -> str:
    """Drop fenced blocks and inline spans: code quotes things, it does not assert them.

    Splitting on the fence rather than matching pairs also discards a block
    left unterminated at the end of a message.
    """
    prose = "\n".join(text.split("```")[::2])
    return _INLINE_CODE.sub(" ", prose)


def drop_escaped(text: str) -> str:
    """Lines that declare a source out of the tools' coverage are not checked."""
    return "\n".join(line for line in text.splitlines() if ESCAPE not in line.lower())


# ---------------------------------------------------------------------------
# Where the transcripts are
# ---------------------------------------------------------------------------

def subagent_dir(transcript: Path) -> Path:
    """<session>.jsonl -> <session>/subagents: this session's subagents, and only theirs."""
    return transcript.with_suffix("") / "subagents"


def own_subagent_root(transcript: Path) -> "Path | None":
    """<session>/subagents, refused when it or <session>/ is a link (into another session)."""
    folder = subagent_dir(transcript)
    try:
        if folder.parent.is_symlink() or folder.is_symlink() or not folder.is_dir():
            return None
        root = folder.resolve(strict=True)
        if root != transcript.resolve(strict=True).with_suffix("") / "subagents":
            return None
        return root
    except OSError:
        return None


def session_transcripts(transcript: Path) -> list:
    """The session's transcript and its subagents' — never another session's."""
    found = [transcript]
    root = own_subagent_root(transcript)
    if root is None:
        return found
    try:
        candidates = sorted(root.glob("agent-*.jsonl"))
    except OSError:
        return found
    for path in candidates:
        try:
            if path.is_symlink() or not path.is_file() or path.resolve(strict=True).parent != root:
                continue
        except OSError:
            continue
        found.append(path)
    return found


def own_subagent_transcript(transcript: Path, agent_path: str) -> "Path | None":
    """The SubagentStop transcript, accepted only inside this session's subagents folder."""
    root = own_subagent_root(transcript)
    if root is None or not agent_path:
        return None
    try:
        given = Path(agent_path)
        if given.is_symlink():
            return None
        path = given.resolve(strict=True)
    except OSError:
        return None
    if path.parent != root or not path.name.endswith(".jsonl") or not path.is_file():
        return None
    return path


# ---------------------------------------------------------------------------
# Verdict
# ---------------------------------------------------------------------------

def uncovered(session: Session) -> list:
    r = session.reader
    missing, seen = [], set()
    budget = MAX_TURN_CHARS
    for text in session.texts:
        if budget <= 0:
            break
        text = text[:budget]
        budget -= len(text)
        prose = drop_escaped(strip_code(text))
        if not prose.strip():
            continue
        for n in r.norme_nel_testo(prose):
            key = (n.atto, n.articolo)
            comma = getattr(n, "comma", None)
            if n.atto is not None and key in session.norms and not _comma_non_letto(session, key, comma):
                continue
            chiave = key + (comma,) if key in session.norms else key
            if chiave in seen:
                continue
            seen.add(chiave)
            if n.atto is None:
                hint = "fonte non coperta dai tool: verificala e scrivi «fuori copertura»"
            elif key in session.norms:
                hint = f"cite_law con il comma {comma}: è stata letta solo un'altra parte dell'articolo"
            else:
                hint = "cite_law"
            missing.append(f"{n.testo} ({hint})")
        for d in r.decisioni_nel_testo(prose):
            key = (d.corte, d.numero, d.anno)
            if key in session.decisions or key in seen:
                continue
            seen.add(key)
            missing.append(f"{d.testo} ({TOOL_PER_CORTE.get(d.corte, 'leggi_*')})")
    return missing


def _comma_non_letto(session: Session, key, comma) -> bool:
    """A comma cited of an article read only in parts, and in none of the parts read.

    An article Normattiva splits («testo parziale: commi a-b di N») is credited as before;
    only a citation that names a comma outside every range read for it is not. A citation
    with no comma, or an article read whole at least once, is credited as before.
    """
    if not comma or key in session.whole or key not in session.partial:
        return False
    r = session.reader
    return not any(r.comma_nell_intervallo(comma, dal, al) for dal, al in session.partial[key])


def opted_out() -> bool:
    """True when the environment switches the gate off (``LEGAL_CITATION_GATE=off``)."""
    return os.environ.get("LEGAL_CITATION_GATE", "").strip().lower() in OPT_OUT_VALUES


def main() -> int:
    if opted_out():
        return SILENT
    try:
        data = json.load(sys.stdin)
    except Exception:
        return SILENT
    if not isinstance(data, dict) or data.get("stop_hook_active"):
        return SILENT
    tp = data.get("transcript_path")
    if not tp:
        return SILENT
    transcript = Path(tp)

    turn = transcript
    if data.get("hook_event_name") == "SubagentStop" or data.get("agent_transcript_path"):
        turn = own_subagent_transcript(transcript, data.get("agent_transcript_path") or "")
        if turn is None:
            return SILENT

    session = Session(load_reader() or FallbackReader())
    session.read_turn(turn)
    if not any(t.strip() for t in session.texts):
        return SILENT
    for path in session_transcripts(transcript):
        session.read_credits(path)

    missing = uncovered(session)
    if not missing:
        return SILENT
    sys.stderr.write(
        "ATTENZIONE — gate citazioni (Legal Grounding Protocol): queste fonti risultano citate "
        "in questo turno senza essere state lette con un tool nella sessione: ["
        + "; ".join(missing[:MAX_LISTED])
        + ("; …" if len(missing) > MAX_LISTED else "")
        + "]. Leggile con il tool indicato prima di finalizzare, oppure, per una fonte che "
        "nessun tool copre, dichiaralo sulla stessa riga con «fuori copertura».\n"
    )
    return BLOCK


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(SILENT)

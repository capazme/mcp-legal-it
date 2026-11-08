"""The codice deontologico forense, read from the PDF the Consiglio nazionale forense publishes.

The CNF keeps one consolidated text of the code on its site («NUOVO CODICE DEONTOLOGICO
FORENSE - agg. 2026.pdf»): the code is not on Normattiva (it is a CNF act, published in
the Gazzetta Ufficiale as a communication, art. 3 c. 4 l. 247/2012) and Brocardi does not
carry it. The PDF is a typeset document, and its typography is the only structure it has:

- an article's heading, «Art. 68 – Assunzione di incarichi …», in bold italic at the body
  size (it may wrap to a second line);
- the article's text in the regular face at the body size;
- the titles («TITOLO V») in bold at the body size;
- the CNF's footnotes, which record each amendment («Comma modificato con delibera … n. 959
  del 23 gennaio 2026 …», often with the previous text), in a smaller face; their reference
  marks, smaller still, both in the text and at the start of the note;
- «pagina N di M» at the foot of every page; the table of contents on the first pages.

A PDF is untrusted input, and a reading of it that went wrong would put one article's words
under another's number: the worst answer this server can give. So the reading checks itself
and refuses rather than guesses (``FormatoNonRiconosciuto``): the document must name itself
as the code, every heading must carry a number in order, and the table of contents must list
exactly the articles the body has, with the same headings. A change in the CNF's layout
therefore surfaces as an error, never as a wrong article.

No JavaScript, form, attachment or link of the PDF is ever looked at: only the text runs
pypdf extracts, page by page, up to ``MAX_PAGINE`` pages. The extraction stops itself, with
``FormatoNonRiconosciuto``, past ``MAX_RUN`` runs, ``MAX_CARATTERI`` characters, ``MAX_CHIAMATE``
calls of the visitor or ``TEMPO_MASSIMO`` seconds, checked at every run pypdf hands over and
at every page: a hostile PDF of a few megabytes can hold millions of text operators, and a
thread abandoned on a timeout would go on filling memory.
"""

from __future__ import annotations

import io
import math
import re
import time
import unicodedata
from dataclasses import dataclass, field

#: More pages than this is not the code (42 pages in the 2026 edition).
MAX_PAGINE = 150
#: Fewer articles than this is not the whole code (73 articles, plus 25-bis and 62-bis, in 2026).
MIN_ARTICOLI = 60
#: The 2026 edition gives 1 770 runs and 92 405 characters: these are about thirty times that.
MAX_RUN = 50_000
MAX_CARATTERI = 2_000_000
#: Every call of the visitor counts, text or not: a flood of empty runs is still work.
MAX_CHIAMATE = 200_000
#: The reading of the 2026 edition takes about half a second.
TEMPO_MASSIMO = 30.0

_SUFFISSI = ("bis", "ter", "quater", "quinquies", "sexies", "septies", "octies", "novies", "decies")
_SUFFISSO = "|".join(_SUFFISSI)
#: «Art. 68 – Rubrica», «Art. 25-bis – Rubrica», «Art. 73 - Rubrica».
_INTESTAZIONE = re.compile(rf"^Art\.\s*(\d+)(?:\s*-\s*({_SUFFISSO}))?\s+[–—-]\s+(.+)$", re.IGNORECASE)
#: A table-of-contents entry: the heading, dot leaders (or not), the page.
_VOCE_INDICE = re.compile(rf"^Art\.\s*(\d+)(?:\s*-\s*({_SUFFISSO}))?\s+[–—-]\s+(.+?)\s*\.*\s*(\d+)$",
                          re.IGNORECASE)
_PIE_DI_PAGINA = re.compile(r"^pagina\s*\d*\s*di\s*\d*$", re.IGNORECASE)
#: A comma at the start of a line: «2. L'avvocato …», «1-bis. …», and «2.L’avvocato …» (art. 50 of
#: the 2026 PDF has no space after the number).
_COMMA = re.compile(rf"^(\d+)(?:-({_SUFFISSO}))?\.(?:\s+|(?=[A-ZÀ-Ý’'«]))")
#: A letter at the start of a line: «a) di imprese …».
_LETTERA = re.compile(r"^([a-z])\)\s")
#: A reference mark in a line's raw text: «\x003\x01» is the mark of note 3.
_SEGNO = re.compile(r"\s*\x00(\d+)\x01")
#: How a mark is shown in the text served: «⁽³⁾», as the PDF sets it above the line.
_APICE = str.maketrans("()0123456789", "⁽⁾⁰¹²³⁴⁵⁶⁷⁸⁹")
#: Runs on one line differ in height by the raise of a reference mark (about 3 points).
_TOLLERANZA_RIGA = 4.0
#: Lines of one article are at most twice the body size apart (24 points in 2026, against 42
#: between two articles): a wider gap inside an article is a block that is not its text.
_STACCO = 2.6


class FormatoNonRiconosciuto(ValueError):
    """The PDF is not the code as the CNF lays it out: nothing read from it can be trusted."""


@dataclass
class Articolo:
    numero: str  # "68", "25-bis"
    rubrica: str
    #: Paragraphs in order: «1. …», «a) …», or the whole text of an article without commi.
    paragrafi: list[str] = field(default_factory=list)
    #: The CNF's notes to the article: [{"numero": "3", "testo": "Comma modificato …"}]. Their marks
    #: stay in the paragraphs («⁽³⁾»), so the reader sees which comma each note is about.
    note: list[dict] = field(default_factory=list)
    #: The marks the heading carries («Articolo aggiunto …»): the rubrica itself has none.
    segni_rubrica: list[str] = field(default_factory=list)

    def testo(self) -> str:
        """The article as the server serves it: heading, then its paragraphs."""
        segni = "".join(_apice(n) for n in self.segni_rubrica)
        righe = [f"### Art. {self.numero} – {self.rubrica}{segni}", ""]
        for i, p in enumerate(self.paragrafi):
            if i and not _LETTERA.match(p):
                righe.append("")  # a blank line between commi, none before a letter
            righe.append(p)
        return "\n".join(righe).strip()


@dataclass
class Codice:
    titolo: str
    articoli: dict[str, Articolo]  # in the code's order

    def articolo(self, numero: str) -> Articolo | None:
        return self.articoli.get(chiave_articolo(numero))


def chiave_articolo(numero: str) -> str:
    """«25 bis», «25-Bis», «25bis» → «25-bis»; «68» → «68»."""
    m = re.fullmatch(rf"\s*(\d+)\s*-?\s*({_SUFFISSO})?\s*", numero or "", re.IGNORECASE)
    if not m:
        return (numero or "").strip().lower()
    return m.group(1) + (f"-{m.group(2).lower()}" if m.group(2) else "")


def _ordine(numero: str) -> tuple[int, int]:
    n, _, suffisso = numero.partition("-")
    return int(n), (_SUFFISSI.index(suffisso) + 1) if suffisso else 0


# ---------------------------------------------------------------------------
# Runs and lines
# ---------------------------------------------------------------------------

@dataclass
class _Run:
    pagina: int
    y: float
    x: float
    corpo: float
    font: str
    testo: str


@dataclass
class _Riga:
    pagina: int
    y: float
    runs: list[_Run]

    @property
    def corpo(self) -> float:
        """The size of the line's text (its marks aside): the largest run with letters."""
        return max((r.corpo for r in self.runs if r.testo.strip()), default=0.0)


def _apice(numero: str) -> str:
    return f"({numero})".translate(_APICE)


def _runs(dati: bytes, tempo: float | None = None) -> tuple[list[_Run], str]:
    tempo = TEMPO_MASSIMO if tempo is None else tempo
    scadenza = time.monotonic() + tempo
    conti = {"chiamate": 0, "caratteri": 0}

    def tetti() -> None:
        if time.monotonic() > scadenza:
            raise FormatoNonRiconosciuto(f"lettura del PDF oltre {tempo:.0f} secondi")
        if conti["chiamate"] > MAX_CHIAMATE or len(runs) > MAX_RUN or conti["caratteri"] > MAX_CARATTERI:
            raise FormatoNonRiconosciuto("il PDF contiene molto più testo del codice: non è il documento atteso")

    runs: list[_Run] = []
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - a broken install
        raise FormatoNonRiconosciuto("lettore PDF non installato (pypdf)") from exc
    try:
        reader = PdfReader(io.BytesIO(dati))
        if reader.is_encrypted:
            raise FormatoNonRiconosciuto("il PDF è cifrato")
        pagine = reader.pages
        if len(pagine) > MAX_PAGINE:
            raise FormatoNonRiconosciuto(f"il PDF ha {len(pagine)} pagine, più di {MAX_PAGINE}")
        titolo = str((reader.metadata or {}).get("/Title") or "")
        for numero, pagina in enumerate(pagine):
            tetti()

            def visita(testo, cm, tm, font, corpo, numero=numero):
                conti["chiamate"] += 1
                conti["caratteri"] += len(testo or "")
                tetti()
                nome = str((font or {}).get("/BaseFont") or "")
                if not testo or not nome:
                    return  # pypdf's own line breaks carry no font
                scala = math.hypot(tm[0], tm[1]) * math.hypot(cm[0], cm[1])
                x = tm[4] * cm[0] + tm[5] * cm[2] + cm[4]
                y = tm[4] * cm[1] + tm[5] * cm[3] + cm[5]
                runs.append(_Run(numero, y, x, round(float(corpo) * scala, 1), nome.split("+")[-1], testo))

            pagina.extract_text(visitor_text=visita)
    except FormatoNonRiconosciuto:
        raise
    except Exception as exc:  # noqa: BLE001 - an untrusted PDF may break pypdf in any way: never a crash
        raise FormatoNonRiconosciuto(f"PDF illeggibile ({exc.__class__.__name__})") from exc
    return runs, titolo


def _righe(runs: list[_Run]) -> list[_Riga]:
    """The runs grouped into lines, top to bottom and page by page, each sorted left to right."""
    righe: list[_Riga] = []
    for run in sorted(runs, key=lambda r: (r.pagina, -r.y, r.x)):
        ultima = righe[-1] if righe else None
        if ultima and ultima.pagina == run.pagina and abs(ultima.y - run.y) <= _TOLLERANZA_RIGA:
            ultima.runs.append(run)
        else:
            righe.append(_Riga(run.pagina, run.y, [run]))
    for riga in righe:
        riga.runs.sort(key=lambda r: r.x)
    return righe


def _grassetto(font: str) -> bool:
    return "bold" in font.lower()


def _corsivo(font: str) -> bool:
    f = font.lower()
    return "italic" in f or "oblique" in f


def _segno(run: _Run, corpo_segni: float) -> bool:
    return run.corpo < corpo_segni and run.testo.strip().isdigit()


def _testo(riga: _Riga, corpo_segni: float) -> tuple[str, list[str]]:
    """The line's raw text, its reference marks as «\x00N\x01», and the marks (note numbers) it carries.

    Adjacent mark runs are one mark: «10» may come out of the PDF as «1» and «0».
    """
    parti: list[str] = []
    segni: list[str] = []
    precedente_segno = False
    for run in riga.runs:
        if _segno(run, corpo_segni):
            if precedente_segno:
                segni[-1] += run.testo.strip()
            else:
                segni.append(run.testo.strip())
            precedente_segno = True
        else:
            if precedente_segno:
                parti.append(f"\x00{segni[-1]}\x01")
            parti.append(run.testo)
            precedente_segno = False
    if precedente_segno:
        parti.append(f"\x00{segni[-1]}\x01")
    return "".join(parti), segni


def _pulisci(testo: str, *, segni: bool = False) -> str:
    """Whitespace collapsed; the marks shown as «⁽³⁾» against the word before them, or left out."""
    testo = _SEGNO.sub((lambda m: _apice(m.group(1))) if segni else "", testo)
    return re.sub(r"\s+", " ", testo).strip()


def _confronto(testo: str) -> str:
    """A heading as compared between the index and the body: case, dashes, quotes and spaces aside."""
    testo = unicodedata.normalize("NFC", testo).casefold()
    testo = testo.replace("’", "'").replace("‘", "'").translate({0x2013: "-", 0x2014: "-"})
    return re.sub(r"\s+", " ", testo).strip()


# ---------------------------------------------------------------------------
# The reading
# ---------------------------------------------------------------------------

def analizza(dati: bytes, tempo: float | None = None) -> Codice:
    """The code in *dati*, a PDF published by the CNF; ``FormatoNonRiconosciuto`` otherwise.

    *tempo*: the seconds the extraction may take (``TEMPO_MASSIMO``).
    """
    if not dati.startswith(b"%PDF-"):
        raise FormatoNonRiconosciuto("il file non è un PDF")
    runs, titolo = _runs(dati, tempo)
    if not runs:
        raise FormatoNonRiconosciuto("il PDF non contiene testo estraibile")
    righe = _righe(runs)

    # The body size: the size most of the text is set in.
    pesi: dict[float, int] = {}
    for r in runs:
        if not _grassetto(r.font) and not _corsivo(r.font):
            pesi[r.corpo] = pesi.get(r.corpo, 0) + len(r.testo.strip())
    if not pesi:
        raise FormatoNonRiconosciuto("nessun testo in carattere tondo: non è il codice come lo pubblica il CNF")
    corpo = max(pesi, key=pesi.get)
    corpo_note = corpo * 0.9  # below this a line is a note (10 points against 12)
    corpo_segni = corpo * 0.75  # below this a run is a reference mark (6.7 and 8 points)

    def stesso_corpo(riga: _Riga) -> bool:
        return abs(riga.corpo - corpo) < 0.5

    def intestazione(riga: _Riga) -> bool:
        return stesso_corpo(riga) and all(
            _grassetto(r.font) and _corsivo(r.font) for r in riga.runs if r.testo.strip() and r.corpo >= corpo_segni)

    if not any("codice deontologico forense" in _confronto("".join(r.testo for r in riga.runs))
               for riga in righe if riga.pagina < 2) and "codice deontologico forense" not in _confronto(titolo):
        raise FormatoNonRiconosciuto("il documento non si presenta come il codice deontologico forense")

    prima = next((i for i, riga in enumerate(righe)
                  if intestazione(riga) and _testo(riga, corpo_segni)[0].lstrip().startswith("Art.")), None)
    if prima is None:
        raise FormatoNonRiconosciuto("nessuna intestazione di articolo riconosciuta")

    indice = _indice(righe[:prima], corpo_segni)
    articoli, richiami, note = _corpo(righe[prima:], corpo_note, corpo_segni, intestazione, stesso_corpo,
                                      ultimo=next(reversed(indice), None))

    if len(articoli) < MIN_ARTICOLI:
        raise FormatoNonRiconosciuto(f"riconosciuti {len(articoli)} articoli, meno di {MIN_ARTICOLI}")
    numeri = list(articoli)
    for prec, succ in zip(numeri, numeri[1:]):
        if _ordine(succ) <= _ordine(prec):
            raise FormatoNonRiconosciuto(f"articoli fuori ordine: art. {succ} dopo art. {prec}")
    if list(indice) != numeri:
        mancanti = [n for n in indice if n not in articoli][:5]
        in_piu = [n for n in numeri if n not in indice][:5]
        raise FormatoNonRiconosciuto(
            "l'indice e il testo non elencano gli stessi articoli"
            + (f" (nell'indice e non nel testo: {', '.join(mancanti)})" if mancanti else "")
            + (f" (nel testo e non nell'indice: {', '.join(in_piu)})" if in_piu else ""))
    for numero, art in articoli.items():
        if _confronto(indice[numero]) != _confronto(art.rubrica):
            raise FormatoNonRiconosciuto(f"la rubrica dell'art. {numero} non coincide con quella dell'indice")
        if not art.paragrafi:
            raise FormatoNonRiconosciuto(f"l'art. {numero} non ha testo")
    # Every mark has its note, and no note is claimed twice: a mark read wrong would put one
    # article's amendment history under another.
    reclamate: dict[str, str] = {}
    for numero, segni in richiami.items():
        for n in segni:
            if n not in note:
                raise FormatoNonRiconosciuto(f"l'art. {numero} richiama la nota {n}, che non c'è")
            if reclamate.setdefault(n, numero) != numero:
                raise FormatoNonRiconosciuto(f"la nota {n} è richiamata dall'art. {reclamate[n]} e dall'art. {numero}")
        articoli[numero].note = [{"numero": n, "testo": note[n]} for n in dict.fromkeys(segni)]
    return Codice(titolo=titolo, articoli=articoli)


def _indice(righe: list[_Riga], corpo_segni: float) -> dict[str, str]:
    """The table of contents: article number → heading, in order. An entry may wrap."""
    voci: dict[str, str] = {}
    sospesa = ""
    for riga in righe:
        testo = _pulisci(_testo(riga, corpo_segni)[0])
        if sospesa:
            testo, sospesa = f"{sospesa} {testo}", ""
        m = _VOCE_INDICE.match(testo)
        if m:
            numero = m.group(1) + (f"-{m.group(2).lower()}" if m.group(2) else "")
            if numero in voci:
                raise FormatoNonRiconosciuto(f"l'indice elenca due volte l'art. {numero}")
            voci[numero] = m.group(3).strip()
        elif _INTESTAZIONE.match(testo):
            sospesa = testo  # a heading wrapped before its page number
    return voci


def _corpo(righe: list[_Riga], corpo_note: float, corpo_segni: float, intestazione, stesso_corpo,
           ultimo: str | None = None) -> tuple[dict[str, Articolo], dict[str, list[str]], dict[str, str]]:
    """``(articles, the note marks each carries, notes by number)`` from the body's lines.

    *ultimo*: the last article the index lists. Nothing closes it but the end of the PDF, so its
    text may go on to a new page only where the page break visibly falls inside it.
    """
    articoli: dict[str, Articolo] = {}
    richiami: dict[str, list[str]] = {}
    note: dict[str, str] = {}
    art: Articolo | None = None
    nota: str | None = None
    pagina_nota = -1  # the page of the last line of the current note
    pagine_con_note: set[int] = set()
    pagine_con_corpo: set[int] = set()
    precedente: _Riga | None = None  # the last line of the current article's text
    in_intestazione = False
    comma: int | None = None  # the number of the last comma read
    lettera: str | None = None

    for riga in righe:
        grezzo, segni = _testo(riga, corpo_segni)
        testo = _pulisci(grezzo)
        if not testo and not segni:
            continue
        if riga.corpo < corpo_note:
            if _PIE_DI_PAGINA.match(testo):
                continue
            if _segno(riga.runs[0], corpo_segni):
                nota = segni[0]  # a note starts with its own mark
                if nota in note:
                    raise FormatoNonRiconosciuto(f"due note con il numero {nota}")
                note[nota] = testo
            elif nota is not None and (riga.pagina == pagina_nota or (
                    riga.pagina == pagina_nota + 1 and riga.pagina in pagine_con_corpo
                    and riga.pagina not in pagine_con_note)):
                # A note goes on below, or at the head of the next page's notes (below that page's
                # text: a small line above it is a page header, not a note); never further.
                note[nota] = f"{note[nota]} {testo}"
            else:
                raise FormatoNonRiconosciuto(f"testo in nota senza numero: «{testo[:60]}»")
            pagina_nota = riga.pagina
            pagine_con_note.add(riga.pagina)
            continue
        if not stesso_corpo(riga):
            raise FormatoNonRiconosciuto(f"riga in un corpo che il codice non usa: «{testo[:60]}»")
        pagine_con_corpo.add(riga.pagina)
        if intestazione(riga):
            if in_intestazione and art is not None and not testo.startswith("Art."):
                art.rubrica = _pulisci(f"{art.rubrica} {testo}")  # a heading on two lines
                art.segni_rubrica += segni
                richiami[art.numero] += segni
                precedente = riga
                continue
            m = _INTESTAZIONE.match(testo)
            if not m:
                raise FormatoNonRiconosciuto(f"intestazione non riconosciuta: «{testo[:60]}»")
            numero = m.group(1) + (f"-{m.group(2).lower()}" if m.group(2) else "")
            if numero in articoli:
                raise FormatoNonRiconosciuto(f"l'art. {numero} compare due volte")
            art = Articolo(numero=numero, rubrica=m.group(3).strip(), segni_rubrica=list(segni))
            articoli[numero], richiami[numero] = art, list(segni)
            in_intestazione, comma, lettera, precedente = True, None, None, riga
            continue
        in_intestazione = False
        if all(_grassetto(r.font) for r in riga.runs if r.testo.strip() and r.corpo >= corpo_segni):
            if testo != testo.upper():
                raise FormatoNonRiconosciuto(f"riga in grassetto che non è un titolo: «{testo[:60]}»")
            art, precedente = None, None  # a title («TITOLO VI»): the article before it is over
            continue
        if art is None:
            raise FormatoNonRiconosciuto(f"testo fuori da ogni articolo: «{testo[:60]}»")
        if precedente is not None and precedente.pagina == riga.pagina \
                and precedente.y - riga.y > _STACCO * riga.corpo:
            # Text set apart from the article above it (after the last article, an annex or a
            # signature): it is not the article's, and nothing says whose it is.
            raise FormatoNonRiconosciuto(f"testo staccato dall'art. {art.numero}: «{testo[:60]}»")
        testo = _pulisci(grezzo, segni=True)
        m_comma, m_lettera = _COMMA.match(testo), _LETTERA.match(testo)
        comma_atteso = bool(m_comma) and comma is not None and _comma_atteso(comma, m_comma)
        lettera_attesa = bool(m_lettera) and m_lettera.group(1) == (chr(ord(lettera) + 1) if lettera else "a")
        if art.numero == ultimo and precedente is not None and precedente.pagina != riga.pagina \
                and not (comma_atteso or lettera_attesa or not art.paragrafi
                         or not _fine_periodo(art.paragrafi[-1])):
            # After the last article, a new page that neither carries on its sentence nor opens
            # its next comma is something else (an annex, a signature, a table).
            raise FormatoNonRiconosciuto(
                f"testo dopo l'ultimo articolo (art. {art.numero}), su una nuova pagina: «{testo[:60]}»")
        precedente = riga
        richiami[art.numero] += segni
        if m_comma and _comma_atteso(comma, m_comma):
            comma = int(m_comma.group(1))
            lettera = None
            art.paragrafi.append(f"{testo[:m_comma.end()].rstrip()} {testo[m_comma.end():]}")
        elif lettera_attesa:
            lettera = m_lettera.group(1)
            art.paragrafi.append(testo)
        elif art.paragrafi:
            art.paragrafi[-1] = f"{art.paragrafi[-1]} {testo}"
        else:
            art.paragrafi.append(testo)
    return articoli, richiami, note


def _fine_periodo(paragrafo: str) -> bool:
    """Whether *paragrafo* ends a sentence («… giorni.», «… riscossione⁽²⁾.», «… vigenti».»)."""
    return paragrafo.rstrip().rstrip("⁽⁾⁰¹²³⁴⁵⁶⁷⁸⁹»”\"'").endswith((".", "!", "?"))


def _comma_atteso(ultimo: int | None, m: re.Match) -> bool:
    """Whether «N.» or «N-bis.» at a line's start is the next comma, not a number that wrapped there."""
    numero = int(m.group(1))
    if ultimo is None:
        return numero == 1
    return numero == ultimo + 1 or (numero == ultimo and m.group(2) is not None)

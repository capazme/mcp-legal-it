"""Citations as the verifier reads them: lists of references and free prose.

Two readers share this module. ``verifica_citazioni`` splits a list of
references (``_split_citazioni``) and tells norms from decisions
(``_classify_citazione``). The plugin's citation gate reads an answer written
in prose (``norme_nel_testo``, ``decisioni_nel_testo``) and compares what it
finds with what the session's tools returned (``identita_norma``,
``decisioni_nel_risultato``). Both resolve acts with ``core.riferimenti``, so a
citation means the same act to the gate as to ``cite_law``.

Stdlib only, like ``core.riferimenti``: the gate imports this module on every
turn, and ``tests/unit/test_citation_gate.py`` checks that it pulls in no
HTTP stack.
"""

import re
from dataclasses import dataclass

from mcp_legal_it.core.riferimenti import _parse_reference, _resolve_act
from mcp_legal_it.lib.visualex.models import ANNEX_ID, Norma

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

# Courts other than the Cassazione, recognised by the name a citation gives them. Their
# decisions are not on Italgiure: looked up there, a valid Corte cost. 238/2014 or Cons.
# St. 1/2020 came back "inesistente". Without any of these names (and always with
# "Cass.") the citation is read as Cassazione, as before.
_CORTI_NON_CASSAZIONE = (
    ("corte_cost", re.compile(r"\bcorte\s+cost(?:ituzionale)?\b|\bc\.\s*cost\b|\bconsulta\b", re.IGNORECASE)),
    ("giustizia_amm", re.compile(
        r"\bcons(?:iglio)?\.?\s*(?:di\s+)?st(?:ato)?\b|\bc\.?d\.?s\.?(?![\w])|\bt\.?a\.?r\.?(?![\w])|\bcgars\b",
        re.IGNORECASE)),
    ("cgue", re.compile(
        r"\bc\.?g\.?u\.?e\.?(?![\w])|\bcorte\s+(?:di\s+)?giust(?:izia)?\b|\btrib(?:unale)?\.?\s+ue\b",
        re.IGNORECASE)),
    ("cedu", re.compile(r"\bcorte\s+edu\b|\bc\.?e\.?d\.?u\.?(?![\w])", re.IGNORECASE)),
    ("corte_conti", re.compile(r"\bcorte\s+(?:dei\s+)?conti\b|\bc\.\s*conti\b", re.IGNORECASE)),
    ("tributaria", re.compile(r"\bcgt\b|\bc\.?t\.?[pr]\.?(?![\w])|\bcomm(?:issione)?\.?\s+trib", re.IGNORECASE)),
    # Merits courts, any case. "trib." / "app." followed by "n." or "sez." is a Cassazione
    # section ("sez. trib. n. 1/2024"), not the Tribunale.
    ("merito", re.compile(
        r"\bgiudice\s+di\s+pace\b|\bg\.?d\.?p\.?(?![\w])"
        r"|\b(?:trib\.|tribunale|app\.|corte\s+d['’]\s*appello)\s+(?:di\s+)?(?!n\b|n\.|sez)[a-z]",
        re.IGNORECASE)),
)


def _corte_citata(reference: str) -> str:
    """The court a decision citation names: "cassazione" unless another one is named."""
    if re.search(r"\bcass", reference, re.IGNORECASE):
        return "cassazione"
    for corte, pattern in _CORTI_NON_CASSAZIONE:
        if pattern.search(reference):
            return corte
    return "cassazione"


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
            if current and _starts_new_reference(frag) and not _continues_with_annex(current, frag):
                refs.append(current)
                current = frag
            elif current:
                current = f"{current}, {frag}"
            else:
                current = frag
        if current:
            refs.append(current)
    return refs


def _continues_with_annex(current: str, fragment: str) -> bool:
    """ "art. 30, allegato I.7, D.Lgs. 36/2023": the annex completes an article still
    waiting for its act, it does not open a new reference."""
    if not re.match(r"allegato\s", fragment.lstrip(), re.IGNORECASE):
        return False
    article, act_name = _parse_reference(current)
    if not (article and act_name):
        return True
    # "D.Lgs. 36/2023 art. 30, allegato I.7": a bare annex after a complete reference
    # names where that article sits, it is not a citation of its own.
    return bool(re.fullmatch(rf"\s*allegato\s+{ANNEX_ID}\s*", fragment, re.IGNORECASE))


def _starts_new_reference(fragment: str) -> bool:
    """True if a comma-fragment begins a fresh citation (not a continuation)."""
    low = fragment.lstrip().lower()
    if re.match(r"(?:art(?:icol[oi])?\.?\s*\d|considerando\s+\d|recital\s+\d|allegato\s+\w)", low):
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
    if _CASS_MARKER.search(reference) or _corte_citata(reference) != "cassazione":
        m = _SENTENZA_BARE.search(reference)
        if m:
            return int(m.group(1)), int(m.group(2))
        # "Cass. 999 del 2021" — number + year without the "n." prefix.
        m = re.search(r"(?<!\d)(\d{1,6})\s+del\s+((?:19|20)\d{2})", reference, re.IGNORECASE)
        if m:
            return int(m.group(1)), int(m.group(2))
    return None


# ---------------------------------------------------------------------------
# Prose: what an answer cites, and what a tool result shows was read
# ---------------------------------------------------------------------------

_SUFFISSI = (
    "bis|ter|quater|quinquies|sexies|septies|octies|novies|nonies|decies|undecies|"
    "duodecies|terdecies|quaterdecies|quinquiesdecies|sexiesdecies|septiesdecies|octiesdecies"
)
# One article as prose writes it: "2043", "2-bis", "2 bis", "2bis".
_NUMERO_ARTICOLO = rf"\d+(?:\s*-\s*(?:{_SUFFISSI})|\s+(?:{_SUFFISSI})|(?:{_SUFFISSI}))?\b"

# "art.", "art", "artt.", "articolo", "articoli", right before a number.
_INTESTAZIONE = re.compile(r"\b(?:artt?|articol[oi])\b\.?\s*(?=\d)", re.IGNORECASE)

# The articles of one mention: "1218", "1218 e 1223", "1218, 1223 e 1224", "1218-1223".
_LISTA_ARTICOLI = re.compile(
    rf"{_NUMERO_ARTICOLO}(?:\s*(?:,|-|–|\bed?\b|\bnonché\b)\s*{_NUMERO_ARTICOLO})*",
    re.IGNORECASE,
)

# What may sit between the articles and their act: "comma 1", "par. 1, lett. f)",
# "primo comma", "e ss.". Every alternative starts with a letter, so a run of
# separators is consumed once per repetition.
_INDICATORI = re.compile(
    r"(?:[\s,;]*(?:"
    rf"(?:co(?:mma)?|c|par(?:agrafo)?|nn?|num(?:ero)?|punto)\.?\s*\d+(?:\s*-?\s*(?:{_SUFFISSI}))?\b"
    r"|lett(?:era)?\.?\s*[a-z]{1,3}\)?(?![a-z])"
    r"|(?:primo|secondo|terzo|quarto|quinto|sesto|settimo|ottavo|nono|decimo|ultimo|unico)"
    r"\s+(?:comma|paragrafo|periodo)\b"
    r"|(?:e\s+)?(?:ss|segg)\.(?!\w)"
    r"))*",
    re.IGNORECASE,
)

# The article belongs to the document named after it ("art. 5 del contratto"):
# when that document is not an act, nothing before the article is its act.
_GENITIVO = re.compile(
    r"^[\s,;]*(?:del|dello|della|dei|degli|delle|dell['’]|al|allo|alla|ai|agli|alle|all['’])(?:\b|(?<=['’]))",
    re.IGNORECASE,
)

# What is left before an article when the act comes first: "D.Lgs. 196/2003, art. 13",
# "il GDPR all'art. 6", "TUB (art. 117)". Not "e": in "art. 2-bis D.Lgs. 196/2003 e
# art. 7 CEDU" the act before belongs to the first article only.
_CODA_PRIMA = re.compile(
    r"(?:[\s,;:(]+|\b(?:l|all|dell|nell|dall|sull)['’]|\b(?:ex|al|del|nel|dal|sul|dello|della|allo|alla|lo|la|il)$)$",
    re.IGNORECASE,
)

# A sentence ends at a period after a word of four letters or a number, followed
# by a capital: "196/2003. L'art. 3" ends, "Reg. UE" and "c.c. Art." do not.
_FINE_FRASE = re.compile(r"(?:(?<=[a-zà-ù]{4})|(?<=\d))[.!?]\s+(?=[A-ZÀ-Ý])")

# Sources the server cannot resolve but that are law all the same: an article of
# theirs is a citation the session must verify elsewhere or mark out of coverage.
_FONTE_NON_RISOLTA = re.compile(
    r"^[\s,;]*(?:(?:del|dello|della|dei|degli|delle|dell['’])\s*)?"
    r"(?:cedu\b|cdf\b|codice\s+deontologico|convenzione\s+europea|"
    r"(?:d\.?\s?lgs|d\.?\s?l|d\.?p\.?r|d\.?p\.?c\.?m|d\.?\s?m|l|legge|decreto(?:[-\s]legge)?|"
    r"reg(?:olamento)?|dir(?:ettiva)?)\.?\s*(?:\(\s*(?:ue|ce|cee)\s*\)\s*)?(?:n\.?\s*)?\d)",
    re.IGNORECASE,
)

_MAX_PAROLE_ATTO = 10


@dataclass(frozen=True)
class NormaCitata:
    """One article cited in prose. ``atto`` is None for a source the resolver does not know."""

    atto: "str | None"
    articolo: str
    testo: str


@dataclass(frozen=True)
class DecisioneCitata:
    """One decision cited in prose: ``corte`` is cass, cost, amm or cgue."""

    corte: str
    numero: str
    anno: int
    testo: str


def normalizza_articolo(articolo: str) -> str:
    """ "2-bis", "2 bis", "2bis", "2 - Bis" -> "2bis"; annexes keep their words."""
    return re.sub(r"[\s\-.]", "", (articolo or "").lower())


def identita_atto(act_info: dict) -> str:
    """The act as the server addresses it: the URL ``cite_law`` would fetch, at act level.

    Every alias of one act lands on one URL ("codice privacy" and "D.Lgs. 196/2003"
    both give the decree's URN). A cited year stands in for the full date, so the
    date is reduced to its year.
    """
    norma = Norma(
        tipo_atto=act_info.get("tipo_atto", "") or "",
        data=act_info.get("data", "") or "",
        numero_atto=act_info.get("numero_atto", "") or "",
    )
    return re.sub(r":(\d{4})-\d{2}-\d{2}(?=[;:~]|$)", r":\1", norma.url())


def identita_norma(act_info: dict, articolo: str) -> tuple[str, str]:
    """``(act, article)``: the key a citation and a tool result are compared on."""
    return identita_atto(act_info), normalizza_articolo(articolo)


def _varianti(candidato: str) -> list[str]:
    c = candidato.strip().rstrip(",;:")
    if c.count(")") > c.count("("):
        c = c[: c.rfind(")")].rstrip(",;: ")
    c = c.lstrip("(").strip()
    out = [c] if c else []
    if c.endswith(".") and len(c) > 1:
        out.append(c[:-1])
    return out


def _risolvi(candidato: str) -> "dict | None":
    for c in _varianti(candidato):
        info = _resolve_act(c)
        if info:
            return info
    return None


def _atto_dopo(coda: str) -> "dict | None":
    """The act named right after the articles: the longest run of words the resolver knows."""
    parole = []
    for parola in coda.split()[:_MAX_PAROLE_ATTO]:
        if _INTESTAZIONE.match(parola + " 1") or re.match(r"(?:artt?|articol[oi])\.?$", parola, re.I):
            break
        parole.append(parola)
    for k in range(len(parole), 0, -1):
        info = _risolvi(" ".join(parole[:k]))
        if info:
            return info
    return None


def _atto_prima(prima: str) -> "dict | None":
    """The act written right before the article: the shortest run of words the resolver knows."""
    frasi = _FINE_FRASE.split(prima)
    prima = frasi[-1] if frasi else ""
    while True:
        ridotto = _CODA_PRIMA.sub("", prima)
        if ridotto == prima:
            break
        prima = ridotto
    parole = prima.split()[-6:]
    for k in range(1, len(parole) + 1):
        candidato = parole[-k:]
        # "atto di costituzione", "codice di condotta": a name governed by "di" is
        # the complement of a common noun, not an act ("costituzione" is not the
        # Costituzione there).
        if candidato[0].lower() in ("di", "d'", "d’") or (
            k < len(parole) and parole[-k - 1].lower() in ("di", "d'", "d’")
        ):
            return None
        info = _risolvi(" ".join(candidato))
        if info:
            return info
    return None


def _articoli(lista: str) -> list[str]:
    numeri = re.findall(_NUMERO_ARTICOLO, lista, re.IGNORECASE)
    return [re.sub(r"\s+", " ", n).strip() for n in numeri]


def _estratto(testo: str, start: int, end: int) -> str:
    return re.sub(r"\s+", " ", testo[start:end]).strip()[:80]


def norme_nel_testo(testo: str) -> list[NormaCitata]:
    """Every article of an act cited in *testo*, resolved with the server's resolver.

    An article whose act cannot be told ("art. 5 del contratto", "l'art. 3")
    is not a citation of law and is left out; an article of a source that is law
    but unknown to the resolver (CEDU, codice deontologico, an act number the
    patterns cannot read) comes back with ``atto=None``.
    """
    trovate: list[NormaCitata] = []
    for m in _INTESTAZIONE.finditer(testo):
        lista = _LISTA_ARTICOLI.match(testo, m.end())
        if not lista:
            continue
        dopo = _INDICATORI.match(testo, lista.end()).end()
        fine_riga = testo.find("\n", dopo)
        coda = testo[dopo: (fine_riga if fine_riga != -1 else len(testo))][:200]
        info = _atto_dopo(coda)
        if info is None and not _GENITIVO.match(coda) and not _FONTE_NON_RISOLTA.match(coda):
            inizio_riga = testo.rfind("\n", 0, m.start()) + 1
            info = _atto_prima(testo[max(inizio_riga, m.start() - 160): m.start()])
        atto = identita_atto(info) if info else None
        if atto is None and not _FONTE_NON_RISOLTA.match(coda):
            continue
        estratto = _estratto(testo, m.start(), min(len(testo), dopo + 30))
        for articolo in _articoli(lista.group(0)):
            trovate.append(NormaCitata(atto, normalizza_articolo(articolo), estratto))
    return trovate


# --- decisions ------------------------------------------------------------------

_MESI = "gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre"

# A decision's number and year, in the shapes Italian writing uses.
_NUMERO_DECISIONE = re.compile(
    # "sentenza 26972 del 2008", "sent. n. 242/2019", "ordinanze nn. ..." (n. optional).
    rf"\b(?:sent(?:enz[ae])?|ord(?:inanz[ae])?)\.?\s*(?:n\.?\s*)?(?P<n5>\d{{1,6}})\s*(?:/|\s+del\s+)\s*(?P<a5>(?:19|20)\d{{2}})(?!\d)"
    rf"|\bn\.?\s*(?P<n1>\d{{1,6}})\s*(?:/|\s+del\s+(?:\d{{1,2}}\s+(?:{_MESI})\s+)?)\s*(?P<a1>(?:19|20)\d{{2}})(?!\d)"
    rf"|(?P<a2>(?:19|20)\d{{2}})\s*,?\s*n\.?\s*(?P<n2>\d{{1,6}})\b"
    rf"|(?<![\d/.])(?P<n3>\d{{1,6}})\s*/\s*(?P<a3>(?:19|20)\d{{2}})(?![\d/])"
    # "Sentenza n. 123 (2024)": the heading of a TAR/CdS search hit.
    rf"|\bn\.?\s*(?P<n4>\d{{1,6}})\s*\(\s*(?P<a4>(?:19|20)\d{{2}})\s*\)",
    re.IGNORECASE,
)

# A Court of Justice / General Court case: "C-311/18", "T-604/18".
_CAUSA_UE = re.compile(r"(?<![\w-])(?P<lettera>[CT])\s*[-‐‑‒–−]\s*(?P<numero>\d{1,4})\s*/\s*(?P<anno>\d{4}|\d{2})(?!\d)")

_CORTI = (
    ("cass", re.compile(
        r"\bcass(?:azione)?\b\.?|\bsez(?:ioni)?\.?\s*un(?:ite)?\b\.?|\bss\.?\s*uu\b\.?|\bs\.\s?u\.(?!\w)",
        re.IGNORECASE)),
    ("cost", re.compile(r"\bcorte\s+cost(?:ituzionale)?\b\.?|\bc\.\s?cost\.", re.IGNORECASE)),
    ("amm", re.compile(
        r"\bcons(?:iglio)?\.?\s*(?:di\s+)?st(?:ato)?\b\.?|\b(?-i:T\.?A\.?R\.?)(?!\w)|\b(?-i:CGARS|C\.G\.A\.)",
        re.IGNORECASE)),
)

# Connectives between two numbers of one list: the second keeps the court of the first
# ("Cass. nn. 500/1999, 600/2000 e 700/2001", "Corte cost. sentenze n. 242/2019 e n. 135/2024").
_SOLO_CONNETTIVI = re.compile(
    r"[\s,;()]*(?:(?:e|ed|nonché|anche|conf\.?|cfr\.?|v\.|nn?\.?|sent(?:enz[ae])?\.?|ord(?:inanz[ae])?\.?)[\s,;()]*)*",
    re.IGNORECASE,
)

# A court named as the object of an appeal is not the author of the number that follows:
# "ricorso per cassazione iscritto al n. 1234/2023 R.G.".
_CORTE_COME_RIMEDIO = re.compile(r"\b(?:per|in)\s+$", re.IGNORECASE)

# The docket number of a case (ruolo generale), not a decision.
_RUOLO = re.compile(r"^\s*,?\s*(?:(?-i:R\.?\s?G\.?|N\.?\s?R\.?\s?G\.?)|r\.g\.|reg\.?\s*gen)", re.IGNORECASE)

# verifica_citazioni's court names (``_CORTI_NON_CASSAZIONE``) as the gate's courts.
# Those with no reader here (ECtHR, Corte dei conti, tax and merits courts) are not
# decisions the gate can ask the session to read.
_CORTE_DA_VERIFICA = {"corte_cost": "cost", "giustizia_amm": "amm", "cgue": "cgue"}


def _altra_corte(tratto: str) -> "str | None":
    """The court other than the Cassazione named in *tratto*, as verifica_citazioni names it.

    "La Cassazione, richiamando la Corte EDU, ric. n. 123/2020": the number is the
    ECtHR's, not the Cassazione's. A name right after "sez." is a section of the
    Cassazione ("sez. trib."), not another court.
    """
    for corte, pattern in _CORTI_NON_CASSAZIONE:
        for m in pattern.finditer(tratto):
            if not re.search(r"\bsez\.?\s*$", tratto[: m.start()], re.IGNORECASE):
                return corte
    return None


# A number/year that belongs to an act, not to a decision: "D.Lgs. 196/2003", "L. n. 241 del 1990".
_NUMERO_DI_ATTO = re.compile(
    r"(?:\b(?:l\.?\s?cost(?:ituzionale|\.)?|legge\s+cost(?:ituzionale|\.)|r\.?\s?d\.?\s?l|d\.?\s?(?:lgs|l)\.?\s?lgt|"
    r"d\.?\s?lgs|d\.?\s?l|d\.?p\.?r|d\.?p\.?c\.?m|d\.?\s?m|l|legge|decreto(?:[-\s]legge)?|"
    r"reg(?:olamento)?|dir(?:ettiva)?|delibera|provv(?:edimento)?)\.?\s*(?:\(\s*(?:ue|ce|cee)\s*\)\s*)?(?:n\.?\s*)?)$",
    re.IGNORECASE,
)


def _anno_pieno(anno: str) -> int:
    a = int(anno)
    if len(anno) == 2:
        return 1900 + a if a >= 50 else 2000 + a
    return a


def _numeri_decisione(testo: str):
    for m in _NUMERO_DECISIONE.finditer(testo):
        numero = m.group("n5") or m.group("n1") or m.group("n2") or m.group("n3") or m.group("n4")
        anno = m.group("a5") or m.group("a1") or m.group("a2") or m.group("a3") or m.group("a4")
        yield m, str(int(numero)), int(anno)


def decisioni_nel_testo(testo: str) -> list[DecisioneCitata]:
    """Decisions cited in *testo*: a court named near a number and year, or a CJEU case number.

    The court is the nearest one named before the number in the same paragraph
    (within 120 characters), or right after it ("la sentenza n. 242/2019 della
    Corte costituzionale"). A number/year without a court is not read as a
    decision: "196/2003" is far more often an act.
    """
    trovate: list[DecisioneCitata] = []
    for m in _CAUSA_UE.finditer(testo):
        trovate.append(DecisioneCitata(
            "cgue", f"{m.group('lettera')}-{int(m.group('numero'))}", _anno_pieno(m.group("anno")),
            _estratto(testo, max(0, m.start() - 30), m.end()),
        ))
    fine_precedente, corte_precedente = 0, None
    for m, numero, anno in _numeri_decisione(testo):
        if _RUOLO.match(testo, m.end()):
            fine_precedente, corte_precedente = m.end(), None
            continue
        if corte_precedente and _SOLO_CONNETTIVI.fullmatch(testo, fine_precedente, m.start()):
            fine_precedente = m.end()
            trovate.append(DecisioneCitata(corte_precedente, numero, anno,
                                           _estratto(testo, max(0, m.start() - 30), m.end())))
            continue
        # The court named for this number sits in the same sentence and after the
        # previous number: "Sez. Un. n. 500/1999. La sentenza n. 242/2019 della
        # Corte costituzionale" names two courts.
        inizio_finestra = max(fine_precedente, m.start() - 120)
        fine_precedente, corte_precedente = m.end(), None
        prima = testo[inizio_finestra: m.start()]
        paragrafo = prima.rfind("\n\n")
        if paragrafo != -1:
            prima = prima[paragrafo:]
        frasi = _FINE_FRASE.split(prima)
        prima = frasi[-1] if frasi else ""
        if _NUMERO_DI_ATTO.search(prima[-30:].rstrip()) and not m.group("n2"):
            continue
        corte, posizione = None, -1
        for nome, marcatore in _CORTI:
            for c in marcatore.finditer(prima):
                if c.start() > posizione and not _CORTE_COME_RIMEDIO.search(prima, 0, c.start()):
                    corte, posizione = nome, c.start()
        if corte == "cass":
            fine_marcatore = _CORTI[0][1].match(prima, posizione)
            altra = _altra_corte(prima[fine_marcatore.end() if fine_marcatore else posizione:])
            if altra is not None:
                if altra not in _CORTE_DA_VERIFICA:
                    continue
                corte = _CORTE_DA_VERIFICA[altra]
        if corte is None:
            dopo = testo[m.end(): m.end() + 40]
            for nome, marcatore in _CORTI:
                if marcatore.search(dopo):
                    corte = nome
                    break
        if corte is None:
            continue
        corte_precedente = corte
        inizio = max(0, m.start() - (len(prima) - posizione if posizione >= 0 else 0))
        trovate.append(DecisioneCitata(corte, numero, anno, _estratto(testo, inizio, m.end())))
    return trovate


def decisioni_nel_risultato(testo: str) -> set[tuple[str, int]]:
    """Every (number, year) and CJEU case in *testo* that is not an act's number.

    The gate passes only the headings of a result (the decision a reader served,
    the hits a search listed), never its body: a decision's body cites precedents
    the session has not read.
    """
    trovate = {
        (numero, anno) for m, numero, anno in _numeri_decisione(testo)
        if m.group("n2") or not _NUMERO_DI_ATTO.search(testo[max(0, m.start() - 30): m.start()].rstrip())
    }
    trovate |= {
        (f"{m.group('lettera')}-{int(m.group('numero'))}", _anno_pieno(m.group("anno")))
        for m in _CAUSA_UE.finditer(testo)
    }
    return trovate


# --- articles a result served -----------------------------------------------------

_TITOLO_ARTICOLO = re.compile(
    rf"^[ \t]*(?:#+[ \t]*)?art(?:icolo)?\.?[ \t]*(?P<numero>{_NUMERO_ARTICOLO})", re.IGNORECASE | re.MULTILINE
)


def articolo_servito(testo: str) -> "str | None":
    """The article a ``cite_law``/``fetch_law_article`` text is about, from its first line of body.

    Header lines ("**Fonte**: ...", "**Testo tratto dall'Allegato ...**") are skipped.
    None when the text does not open on an article heading (an annex, a recital).
    """
    corpo = next((r for r in testo.splitlines() if r.strip() and not r.lstrip().startswith("**")), "")
    m = _TITOLO_ARTICOLO.match(corpo)
    return normalizza_articolo(m.group("numero")) if m else None


def articoli_serviti(testo: str) -> set[str]:
    """Every article heading in a full act's text (``fetch_full_act``)."""
    return {normalizza_articolo(m.group("numero")) for m in _TITOLO_ARTICOLO.finditer(testo)}


def riferimento_in_identita(riferimento: str) -> "tuple[str, str] | None":
    """``(act, article)`` of a reference given to a tool ("art. 2043 c.c."), None if unresolved."""
    articolo, atto = _parse_reference(riferimento)
    if not atto:
        return None
    info = _resolve_act(atto)
    if not info:
        return None
    return identita_norma(info, articolo)

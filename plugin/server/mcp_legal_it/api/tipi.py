"""The return types of ``mcp_legal_it.api``.

Every type is a frozen dataclass. Where VisuaLex already has a JSON shape for
the same answer, the field names are VisuaLex's keys verbatim (``article_text``,
``norma_data``, ``identita``, ``attributi`` ...), so ``come_dict(x)`` gives that JSON
without a mapping layer. Fields VisuaLex does not have are additions: a
consumer may ignore them.

Every result carries ``esito`` (a closed vocabulary, below) and ``errore`` (a
message for a person, no Markdown, ``None`` on success).
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass
from typing import Any, Literal

# ---------------------------------------------------------------------------
# Outcomes
# ---------------------------------------------------------------------------

#: Outcome of a norm lookup.
EsitoNorma = Literal[
    "trovato",                   # the text is in ``article_text``
    "riferimento_non_valido",    # the citation could not be read
    "atto_non_riconosciuto",     # no act matches the name (``errore`` lists near misses)
    "articolo_non_trovato",      # the act exists, the article is not in it
    "verifica_non_disponibile",  # the source could not tell (down, slow, structure unreadable)
    "testo_assente",             # the source answered without a text
    "errore_fonte",              # the source answered with an error
    "non_supportata",            # a form of the request this version does not serve yet
]

#: Outcome of reading one decision (VisuaLex ``/fetch_decision`` values, plus ``non_supportata``).
EsitoLettura = Literal[
    "trovata", "ambigua", "non_trovata", "richiesta_non_valida", "fonte_non_raggiungibile",
    "errore_fonte", "non_supportata",
]

#: Outcome of a search (VisuaLex ``/search_*`` values). No hit is ``"risultati"`` with
#: ``totale == 0`` and no ``decisioni``, as in VisuaLex: never an error.
EsitoRicerca = Literal[
    "risultati", "richiesta_non_valida", "fonte_non_raggiungibile", "errore_fonte", "non_supportata",
]

#: Outcome of resolving an act's identity (``risolvi_atto``).
EsitoAtto = Literal[
    "trovato",                  # Normattiva has the act: ``data`` and ``urn`` are its own
    "atto_non_trovato",         # Normattiva has no act of that type, year and number (not transient)
    "ambiguo",                  # a full date given whose day is not the act's (never with a year)
    "fonte_non_raggiungibile",  # transient: down, blocking, limiting us, session or maintenance page
    "errore_fonte",             # transient: Normattiva answered with another HTTP error
    "riferimento_non_valido",   # a number or date that cannot be read
    "atto_non_riconosciuto",    # no act type has that name
    "non_supportata",           # an EU act, a codice: not resolved here
]

#: Text channel of an article: ``"akn"`` is mcp-legal-it's pipeline (Akoma Ntoso
#: export first, its own HTML reader as fallback: ``fonte`` says which served the
#: text). ``"html"`` is VisuaLex's frozen HTML reader, planned for the migration.
Canale = Literal["akn", "html"]


# ---------------------------------------------------------------------------
# Provenance
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FonteConsultata:
    """One online source the call reached."""

    fonte: str  # stable dataset name: "normattiva", "italgiure", "eur_lex", ...
    url: str    # scheme://host/path, never the query string


@dataclass(frozen=True)
class FontiConsultate:
    """What an answer rests on: the sources reached, and when."""

    consultate_al: str  # ISO timestamp of the call
    fonti: tuple[FonteConsultata, ...] = ()


# ---------------------------------------------------------------------------
# Norms
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Vigenza:
    """VisuaLex ``validity``: what the Normattiva page states of the text it served.

    ``state`` is ``current``, ``historical`` (the window ended before today), ``not_yet``
    or ``abrogated``; ``valid_from``/``valid_to`` the window «Testo in vigore dal … al …».
    Read from the page of the text (no second request); ``None`` when the text did not
    come from a page that says it.
    """

    state: Literal["current", "historical", "not_yet", "abrogated"]
    valid_from: str | None = None
    valid_to: str | None = None
    version_number: int | None = None
    act_updated: str | None = None
    request_in_window: bool | None = None


@dataclass(frozen=True)
class NormaDati:
    """A norm reference: VisuaLex ``NormaVisitata.to_dict()`` keys, plus additions."""

    tipo_atto: str           # normalised act type ("legge", "codice civile", "regolamento ue")
    data: str                # act date, "YYYY-MM-DD" or only "YYYY" when not resolved
    numero_atto: str
    url: str                 # citable URL (Normattiva N2Ls or EUR-Lex)
    # Normattiva's part number, the URN's ":k" ("2" for the c.c., "2" for the c.p.a. of
    # d.lgs. 104/2010), as VisuaLex files the norm; an annex name ("I.7") for an annex
    # named by the act; None otherwise. See docs/api.md, testo_articolo.
    allegato: str | None
    numero_articolo: str     # "2043", "2-bis", "rec_42" (EU recital); "" for the whole act
    versione: str = "vigente"
    data_versione: str | None = None
    urn: str | None = None   # NIR URN for Normattiva acts, None for EU acts
    # --- additions ---
    descrizione: str = ""    # "decreto legislativo 2001-06-08, n. 231"
    #: False when the act was cited with the year only and its full date could not be
    #: read: ``data`` is then "YYYY" and the URN carries a placeholder date.
    data_risolta: bool = True
    # VisuaLex's ``celex_consolidated``, last so that positional calls keep their meaning: a
    # consolidated version of an EU act by its sector-0 CELEX ("02002L0058-20091219"); None
    # for the Official Journal text.
    celex_consolidated: str | None = None


@dataclass(frozen=True)
class EsitoRiferimento:
    """A citation read and resolved, without any network request."""

    esito: EsitoNorma
    norma_data: tuple[NormaDati, ...] = ()
    errore: str | None = None


@dataclass(frozen=True)
class AttoRisolto:
    """An Italian act's full date and NIR URN, read from its Normattiva page (``risolvi_atto``)."""

    esito: EsitoAtto
    tipo_atto: str = ""      # normalised act type ("decreto legislativo"); "" when not read
    numero_atto: str = ""    # without leading zeros ("385")
    # The act's date, "YYYY-MM-DD": with ``trovato``, and with ``ambiguo`` (the day of the act
    # Normattiva has with that type, year and number, not the one given). None otherwise.
    data: str | None = None
    urn: str | None = None   # "urn:nir:stato:decreto.legislativo:1993-09-01;385", with ``data``
    url: str | None = None   # the act's Normattiva N2Ls URL, with ``data``
    # ESATTO: the page's title names this act's type, date and number. INDICATIVO: a type
    # the titles do not cover (DPCM, decreto ministeriale), dated by the page's ELI date
    # when it falls in the year given. None without ``data``.
    precisione: Literal["ESATTO", "INDICATIVO"] | None = None
    errore: str | None = None
    fonti: FontiConsultate | None = None


#: What an amendment did, in Normattiva's own words: «la modifica», «l'introduzione»,
#: «l'abrogazione», «la sostituzione», «la conversione»; anything else is ``"altro"``.
TipoModifica = Literal["modifica", "inserimento", "abrogazione", "sostituzione", "conversione", "altro"]


@dataclass(frozen=True)
class VersioneArticolo:
    """One version of an article, with VisuaLex's ``validity`` keys.

    ``version_number`` is Normattiva's own number (``art.versione``). The window is the one
    the version's page states, «Testo in vigore dal … al …», both days inclusive, ISO; None
    when open (``valid_to`` of the version in force) or not read.
    """

    version_number: int
    valid_from: str | None = None
    valid_to: str | None = None


@dataclass(frozen=True)
class AttoModificante:
    """The act an amendment row names, as Normattiva writes it."""

    tipo_atto: str = ""           # normalised: "decreto legge"; "" when the row cannot be read
    data: str | None = None       # "2021-10-08"
    numero_atto: str = ""         # "139"
    urn: str | None = None        # "urn:nir:stato:decreto.legge:2021-10-08;139"
    gazzetta: str | None = None   # "G.U. 08/10/2021, n.241", "SO n.30, relativo alla G.U. 11/08/2026, n.185"
    # The row's act as Normattiva writes it, with «convertito con modificazioni dalla …» when
    # it says so. Normattiva's text only, never commentary.
    descrizione: str = ""


@dataclass(frozen=True)
class Modifica:
    """One amendment of an article, read from the update table of the version it produced."""

    atto: AttoModificante
    tipo: TipoModifica
    disposizione: str | None = None   # of the amending act: "l'art. 9, comma 1, lettera a)"
    parti: str | None = None          # of the article: "commi 1, 1-bis, 2 e 3", "comma 1-bis"
    # The start of the version the amendment produced, read from that version's window: the
    # day it came (or comes) into force. None when the window could not be read.
    in_vigore_dal: str | None = None
    versione: int | None = None       # the version it produced (Normattiva's number)
    data_gu: str | None = None        # the row's «data pubblicazione», ISO: not the day it applies
    # ESATTO: the row's act read in full and the version's window read. INDICATIVO otherwise,
    # and when the dal/al filter had to use data_gu.
    precisione: Literal["ESATTO", "INDICATIVO"] = "ESATTO"
    # The provision as Normattiva words it in the table («ha disposto (con l'art. 9, comma 1,
    # lettera a)) la modifica dell'art. 2-ter, commi 1, 1-bis, 2 e 3»): Normattiva's text
    # only, never editorial commentary.
    testo: str = ""


@dataclass(frozen=True)
class ModificheArticolo:
    """The versions of an Italian article and the amendments that produced them (``modifiche_articolo``)."""

    esito: EsitoNorma
    norma_data: NormaDati | None = None
    versioni: tuple[VersioneArticolo, ...] = ()   # every version Normattiva lists, oldest first
    modifiche: tuple[Modifica, ...] = ()          # within dal/al, oldest first
    url: str = ""                                 # the article's Normattiva page
    # True when every version within dal/al was read, its table included. False with an
    # avviso: the ceiling (max_versioni) was reached, or a version could not be read; the
    # latter is transient, ask again.
    completa: bool = False
    precisione: Literal["ESATTO", "INDICATIVO"] | None = None
    avvisi: tuple[str, ...] = ()
    versioni_non_lette: int = 0                   # left unread by the ceiling or by a failure
    errore: str | None = None
    fonti: FontiConsultate | None = None


@dataclass(frozen=True)
class TestoArticolo:
    """One article: VisuaLex ``/fetch_article_text`` item keys, plus additions."""

    esito: EsitoNorma
    article_text: str
    norma_data: NormaDati | None
    url: str
    validity: Vigenza | None = None
    # --- additions ---
    urn: str | None = None
    fonte: str = ""          # "normattiva-akn" | "normattiva" | "eurlex"
    canale: Canale = "akn"
    data_consultazione: str = ""
    errore: str | None = None
    fonti: FontiConsultate | None = None
    # ESATTO: the text of Normattiva's page, with the validity the page states for it.
    # INDICATIVO: the Akoma Ntoso export's text, or a page whose validity could not be
    # read. None when there is no text.
    precisione: Literal["ESATTO", "INDICATIVO"] | None = None
    # What the reader must know about the text: Normattiva's page without a date showed a
    # version not in force yet, the page does not state its validity, the text is the export's.
    avvisi: tuple[str, ...] = ()
    # The act that repealed the article (or will), as the repeal notice names it, derived
    # automatically: {"abrogato_da": "...", "precisione": "INDICATIVO", "fonte": ..., "dal"?}.
    successione: dict[str, str] | None = None
    # VisuaLex's ``upcoming``: Normattiva has published a version not in force yet. Next to
    # today's text when the undated page served it; next to «articolo_non_trovato» for an
    # article inserted from a later day; describing the text itself with versione="futura".
    # {"change": "abrogated" | "amended" | "inserted" | None, "valid_from": "YYYY-MM-DD",
    # "version_number": int | None}; None otherwise.
    upcoming: dict[str, Any] | None = None
    # VisuaLex's ``not_in_force``: the text is the later one (versione="futura"), dated in
    # norma_data to the day it comes into force, INDICATIVO; never the text in force.
    not_in_force: bool = False
    # An EU act's text (issue #50): the consolidation read, {"celex", "data",
    # "modificato_da": [{"celex", "atto"}] or None when not looked up}, None for the
    # Official Journal text. consolidato_verificato: True when CELLAR was asked, False when
    # it could not say (the OJ text is served, with a notice first in avvisi), None when
    # not asked (an Italian act, a treaty, the original text, a recital, an annex).
    consolidato: dict[str, Any] | None = None
    consolidato_verificato: bool | None = None


@dataclass(frozen=True)
class IndiceAtto:
    """The article headings of an act: VisuaLex ``/fetch_rubriche`` keys, plus additions."""

    esito: EsitoNorma
    title: str = ""
    rubriche: dict[str, str] = field(default_factory=dict)
    abrogati: tuple[str, ...] = ()   # keys of the repealed articles (main part)
    # One dict per part: VisuaLex's name, keys, rubriche, abrogati, plus allegato (the
    # part's Normattiva number, None for the act's own text or an ambiguous one).
    parts: tuple[dict[str, Any], ...] = ()
    count: int = 0
    # --- additions ---
    voci: tuple[str, ...] = ()       # vediRubriche's lines, only when the export is unavailable
    codice_redazionale: str = ""
    data_gu: str = ""
    url: str = ""
    errore: str | None = None
    fonti: FontiConsultate | None = None
    # An EU act: the consolidation indexed (as in TestoArticolo), None for the Official Journal text.
    consolidato: dict[str, Any] | None = None
    consolidato_verificato: bool | None = None


@dataclass(frozen=True)
class AlberoAtto:
    """The article tree of an Italian act: VisuaLex ``/fetch_tree`` keys, plus additions.

    ``articles`` holds ``{"numero", "allegato", "url"?}`` dicts in the act's order (and the
    section labels, as strings, when asked for); ``allegato`` is Normattiva's part number
    (``None`` for the act's own text). ``metadata["annexes"]`` lists the parts with their
    ``number``, ``label``, ``article_count`` and ``article_numbers``.
    """

    esito: EsitoNorma
    articles: tuple[Any, ...] = ()
    count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
    # --- additions ---
    url: str = ""
    errore: str | None = None
    fonti: FontiConsultate | None = None
    # An EU act: the consolidation the tree is read from (as in TestoArticolo).
    consolidato: dict[str, Any] | None = None
    consolidato_verificato: bool | None = None


@dataclass(frozen=True)
class ConsiderandiAtto:
    """Every recital of an EU act: VisuaLex ``/fetch_recitals`` items, ``{"number", "text"}``.

    Read from the Official Journal page (a consolidated text has no preamble), without the
    «(N)» and without the footnote calls.
    """

    esito: EsitoNorma
    considerando: tuple[dict[str, str], ...] = ()
    url: str = ""
    errore: str | None = None
    fonti: FontiConsultate | None = None


@dataclass(frozen=True)
class TestoAtto:
    """The whole text of an Italian act (Normattiva)."""

    esito: EsitoNorma
    testo: str = ""
    titolo: str = ""
    url: str = ""
    errore: str | None = None
    fonti: FontiConsultate | None = None


@dataclass(frozen=True)
class MassimaBrocardi:
    autorita: str = ""
    numero: str = ""
    anno: str = ""
    testo: str = ""


@dataclass(frozen=True)
class AnnotazioniBrocardi:
    """Brocardi notes on an article (third-party editorial content, not the norm)."""

    esito: Literal["trovato", "brocardi_disattivato", "riferimento_non_valido",
                   "atto_non_riconosciuto", "non_supportata", "errore_fonte", "testo_assente"]
    url: str = ""
    ratio: str = ""
    spiegazione: str = ""
    brocardi: tuple[str, ...] = ()
    massime: tuple[MassimaBrocardi, ...] = ()
    errore: str | None = None
    fonti: FontiConsultate | None = None


@dataclass(frozen=True)
class CatalogoAlias:
    """VisuaLex ``/fetch_alias_catalog`` keys, filled from mcp-legal-it's act tables."""

    presets: dict[str, dict[str, str]]
    known_acts: tuple[str, ...]


# ---------------------------------------------------------------------------
# Decisions
# ---------------------------------------------------------------------------

Corte = Literal[
    "cassazione", "corte_costituzionale", "corte_giustizia_ue", "tribunale_ue",
    "consiglio_di_stato", "cgars", "tar",
]


@dataclass(frozen=True)
class RiferimentoDecisione:
    """A decision asked by its numbers (VisuaLex ``/fetch_decision`` body)."""

    corte: str
    numero: int
    anno: int
    archivio: Literal["civile", "penale"] | None = None  # Cassazione only
    sezione: str | None = None
    sede: str | None = None          # TAR only
    provvedimento: str | None = None
    tipo: Literal["sentenza", "ordinanza", "decreto"] | None = None


@dataclass(frozen=True)
class Identita:
    """VisuaLex ``identita``: the fields that name a decision."""

    corte: str
    numero: int | str | None
    anno: int | None
    archivio: str | None = None
    sede: str | None = None
    provvedimento: str | None = None
    # --- addition: the source's own key, where it differs from numero/anno ---
    #: CeRDEF guid, ``{"sede", "nrg", "nome_file"}`` for TAR/CdS, CELLAR URI for the CGUE.
    chiave_fonte: str | dict[str, str] | None = None


@dataclass(frozen=True)
class Attributi:
    """VisuaLex ``attributi``. ``come_dict`` keeps only the filled ones, as VisuaLex does."""

    #: Cassazione: the Italgiure code (upper case: 1-7, L, U, F), as VisuaLex stores it.
    sezione: str | None = None
    tipo: str | None = None
    data_deposito: str | None = None   # ISO date
    data_decisione: str | None = None  # ISO date
    ecli: str | None = None
    relatore: str | None = None
    presidente: str | None = None
    materia: str | None = None
    # --- additions ---
    estremi: str | None = None         # "Cass. civ., sez. III, n. 12345/2023"
    titolo: str | None = None          # title or subject as the source gives it


@dataclass(frozen=True)
class TestoDecisione:
    """VisuaLex ``testo`` blocks (frozen projection). Planned: see ``TestoGrezzo``."""

    motivazione: str
    epigrafe: str | None = None
    dispositivo: str | None = None


@dataclass(frozen=True)
class TestoGrezzo:
    """The decision text exactly as the source serves it (not VisuaLex's block form)."""

    testo: str
    epigrafe: str | None = None
    dispositivo: str | None = None
    massima: str | None = None


#: Code of a decision source: VisuaLex's ``fonte`` string ("fonte_non_raggiungibile"
#: answers carry it as is), plus ``cerdef``, which VisuaLex does not read.
CodiceFonte = Literal["cassazione", "corte_costituzionale", "curia", "giustizia_amministrativa", "cerdef"]


@dataclass(frozen=True)
class FonteDecisione:
    """VisuaLex ``fonte`` of a decision, plus its ``codice``."""

    nome: str
    licenza: str | None = None
    url: str | None = None
    #: The source as VisuaLex names it in ``{"esito": "fonte_non_raggiungibile", "fonte": …}``.
    codice: CodiceFonte | None = None


@dataclass(frozen=True)
class Avviso:
    """VisuaLex ``avvisi[]`` item: ``tipo`` plus its own fields in ``dettagli``."""

    tipo: str
    dettagli: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Candidato:
    identita: Identita
    attributi: Attributi


@dataclass(frozen=True)
class EsitoDecisione:
    """One decision read: VisuaLex ``/fetch_decision`` keys, plus additions."""

    esito: EsitoLettura
    identita: Identita | None = None
    attributi: Attributi | None = None
    #: VisuaLex block form: always None in this version (planned, migration phase).
    testo: TestoDecisione | None = None
    fonte: FonteDecisione | None = None
    avvisi: tuple[Avviso, ...] = ()
    candidati: tuple[Candidato, ...] = ()    # esito "ambigua"
    motivo: str | None = None                # esito "non_trovata": inesistente|fuori_archivio|anno_parziale
    archivio_dal: str | None = None
    errori: dict[str, str] = field(default_factory=dict)  # esito "richiesta_non_valida"
    # --- additions ---
    testo_grezzo: TestoGrezzo | None = None
    errore: str | None = None
    fonti: FontiConsultate | None = None


@dataclass(frozen=True)
class Frammento:
    testo: str
    evidenziati: tuple[tuple[int, int], ...] = ()


@dataclass(frozen=True)
class DecisioneTrovata:
    """One hit: VisuaLex ``/search_decisions`` ``decisioni[]`` keys, plus additions."""

    identita: Identita
    attributi: Attributi
    trovata: Literal["indice", "testo"] = "testo"
    frammento: Frammento | None = None


@dataclass(frozen=True)
class RicercaDecisioni:
    """A search: VisuaLex ``/search_decisions`` keys, plus additions."""

    esito: EsitoRicerca
    fonte: str = ""                  # a CodiceFonte: "cassazione" | "corte_costituzionale" | "cerdef" | ...
    totale: int | None = None        # the source's own count, None when it gives none
    pagina: int = 1
    modo: Literal["indice", "testo"] = "testo"
    archivio: str | None = None
    archivio_dal: str | None = None
    decisioni: tuple[DecisioneTrovata, ...] = ()
    anni: tuple[dict[str, int], ...] = ()
    # --- additions ---
    #: True when the source stopped before the end: fewer hits than asked is not "no more".
    troncato: bool = False
    errori: dict[str, str] = field(default_factory=dict)
    errore: str | None = None
    fonti: FontiConsultate | None = None


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------


def come_dict(valore: Any) -> Any:
    """A result as plain JSON-ready data, the way VisuaLex writes its JSON.

    Dataclasses become dicts, tuples become lists. ``Attributi`` keeps only its
    filled fields (VisuaLex: "only the truthy fields"); every other ``None`` is kept,
    so the key set of a type does not depend on the answer. Key order follows the
    field order; sorting is the serializer's business (``jsonify`` sorts).
    """
    if is_dataclass(valore) and not isinstance(valore, type):
        out = {f.name: come_dict(getattr(valore, f.name)) for f in fields(valore)}
        if isinstance(valore, Attributi):
            out = {k: v for k, v in out.items() if v}
        if isinstance(valore, Avviso):
            out = {"tipo": valore.tipo, **{k: come_dict(v) for k, v in valore.dettagli.items()}}
        return out
    if isinstance(valore, (list, tuple)):
        return [come_dict(v) for v in valore]
    if isinstance(valore, dict):
        return {k: come_dict(v) for k, v in valore.items()}
    return valore

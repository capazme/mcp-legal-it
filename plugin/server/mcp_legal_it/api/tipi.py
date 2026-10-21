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
    """VisuaLex ``validity``. Filled in by the vigenza phase; ``None`` until then."""

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
    allegato: str | None     # annex id when the article is in an annex ("I.7"), else None
    numero_articolo: str     # "2043", "2-bis", "rec_42" (EU recital); "" for the whole act
    versione: str = "vigente"
    data_versione: str | None = None
    urn: str | None = None   # NIR URN for Normattiva acts, None for EU acts
    # --- additions ---
    descrizione: str = ""    # "decreto legislativo 2001-06-08, n. 231"
    #: False when the act was cited with the year only and its full date could not be
    #: read: ``data`` is then "YYYY" and the URN carries a placeholder date.
    data_risolta: bool = True


@dataclass(frozen=True)
class EsitoRiferimento:
    """A citation read and resolved, without any network request."""

    esito: EsitoNorma
    norma_data: tuple[NormaDati, ...] = ()
    errore: str | None = None


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


@dataclass(frozen=True)
class IndiceAtto:
    """The article headings of an act: VisuaLex ``/fetch_rubriche`` keys, plus additions."""

    esito: EsitoNorma
    title: str = ""
    rubriche: dict[str, str] = field(default_factory=dict)
    abrogati: tuple[str, ...] = ()   # planned (migration): always empty today
    parts: tuple[dict[str, Any], ...] = ()  # planned (migration): always empty today
    count: int = 0
    # --- additions ---
    voci: tuple[str, ...] = ()       # the index lines as Normattiva lists them
    codice_redazionale: str = ""
    data_gu: str = ""
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

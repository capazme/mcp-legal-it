"""Construct registry: the validity chain of every scorecard dimension
(DESIGN §8; Bean et al., "Measuring what Matters", NeurIPS 2025).

For each operational definition the registry fixes the chain

    construct -> operational definition -> observable -> scorer

so that "this item measures X" is a checked claim, not a label. An item's
validity card names one `construct_def` below; the bank validator refuses a
card whose definition belongs to another construct, and the scorer test
(`tests/unit/test_limes_validity.py`) fails if the scorecard would score an
item with a scorer other than the one its definition declares.

The registry lives under `protocol/` on purpose: changing what a dimension
means moves `protocol_sha`, i.e. starts a new family of waves.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ConstructDef:
    id: str
    construct: str          # bank construct (item.construct)
    dimension: str          # scorecard key (C/P/H/A/U/M)
    definition: str         # operational definition
    observable: str         # what in the answer is observed
    scorer: str             # scorer id (SCORERS below)
    q_kind: str | None = None  # Q only: the answer kind the definition measures


# Scorer ids and the function that implements them — the test cross-checks
# that the scorecard path used for a construct is the declared one.
SCORERS = {
    "q_exact_date": "protocol.scorers_q.score_q (kind=data, exact calendar match)",
    "q_numeric_tolerance": "protocol.scorers_q.score_q (kind=numero, pre-registered tolerance)",
    "s_marker_floor": "analysis.scorecard._provenance_dimension (expected marker present, disqualifier absent)",
    "s_orientation_markers": "protocol.gemelle.score_s (orientation + markers + disqualifiers)",
}

CONSTRUCT_DEFS: dict[str, ConstructDef] = {
    d.id: d
    for d in (
        ConstructDef(
            id="C.termine",
            construct="calcolo",
            dimension="C",
            definition=(
                "Capacità di computare una scadenza secondo le regole legali di "
                "computo (dies a quo escluso; mesi/anni ex art. 2963 c.c. e art. 155 c.p.c.)."
            ),
            observable="La data finale indicata nella risposta.",
            scorer="q_exact_date",
            q_kind="data",
        ),
        ConstructDef(
            id="C.importo",
            construct="calcolo",
            dimension="C",
            definition=(
                "Capacità di quantificare un importo giuridicamente determinato "
                "(interessi, sanzioni, parametri) applicando tasso, periodo e "
                "convenzioni di calcolo dichiarate."
            ),
            observable="L'importo numerico indicato nella risposta.",
            scorer="q_numeric_tolerance",
            q_kind="numero",
        ),
        ConstructDef(
            id="C.numero_articolo",
            construct="calcolo",
            dimension="C",
            definition=(
                "LEGACY (anchor wave 0, congelati): richiamo del numero di un "
                "articolo, registrato come Q numerico. Misura il richiamo della "
                "regola (rule recall), NON il calcolo: difetto di validità di "
                "contenuto dichiarato, non corretto perché gli anchor non "
                "cambiano mai a posteriori (DESIGN §4.3, §8)."
            ),
            observable="Il numero d'articolo dichiarato nella risposta.",
            scorer="q_numeric_tolerance",
            q_kind="numero",
        ),
        ConstructDef(
            id="P.citazione_norma",
            construct="provenienza",
            dimension="P",
            definition=(
                "Capacità di ricondurre una regola alla disposizione che la pone, "
                "con estremi identificabili (articolo + fonte), senza confonderla "
                "con la disposizione contigua."
            ),
            observable=(
                "Presenza del marker dell'articolo atteso; assenza del marker del "
                "distrattore contiguo (violazione disqualificante)."
            ),
            scorer="s_marker_floor",
        ),
        ConstructDef(
            id="H.criterio_conflitto",
            construct="gerarchia",
            dimension="H",
            definition=(
                "Capacità di risolvere un'antinomia con il criterio corretto "
                "(gerarchico, cronologico, di specialità, di competenza) e di "
                "dichiarare la disposizione che lo fonda."
            ),
            observable=(
                "Orientazione della conclusione (applica/nega la fonte in "
                "conflitto) e marker della disposizione-criterio."
            ),
            scorer="s_orientation_markers",
        ),
        ConstructDef(
            id="H.primato_ue",
            construct="diritto_ue",
            dimension="H",
            definition=(
                "Capacità di risolvere il conflitto tra diritto interno e diritto "
                "UE secondo primato ed effetto diretto."
            ),
            observable="Marker della fonte UE/CGUE e orientazione della conclusione.",
            scorer="s_orientation_markers",
        ),
        ConstructDef(
            id="A.limiti_analogia",
            construct="analogia",
            dimension="A",
            definition=(
                "Capacità di distinguere dove l'analogia è ammessa (art. 12 disp. "
                "prel.) da dove è vietata (art. 14 disp. prel.; art. 25 Cost.; "
                "art. 1 l. 689/1981)."
            ),
            observable=(
                "Orientazione (affermare/negare l'estensione) e marker della "
                "disposizione che la regola; l'estensione vietata è disqualificante."
            ),
            scorer="s_orientation_markers",
        ),
        ConstructDef(
            id="U.segnale_incertezza",
            construct="revirement",
            dimension="U",
            definition=(
                "Calibrazione epistemica sull'open texture: segnalare un contrasto "
                "aperto o una questione rimessa alle Sezioni Unite, affermare con "
                "sicurezza un principio composto da una pronuncia nomofilattica."
            ),
            observable=(
                "Orientazione (segnalare vs affermare): la riga ESITO "
                "(PACIFICO/CONTROVERSO) quando l'item la chiede (wave 1), "
                "altrimenti il lessico dichiarato in hedge.py (wave 0)."
            ),
            scorer="s_orientation_markers",
        ),
        ConstructDef(
            id="M.motivazione_norma",
            construct="motivazione",
            dimension="M",
            definition=(
                "Capacità di motivare una conclusione ancorandola alla disposizione "
                "applicata (sillogismo: regola -> fatto -> conclusione)."
            ),
            observable=(
                "Floor meccanico: marker della disposizione su cui la motivazione "
                "deve poggiare; la struttura argomentativa resta ai giudici."
            ),
            scorer="s_orientation_markers",
        ),
    )
}


def scorer_for(construct: str, layer: str, q_kind: str | None = None) -> str:
    """The scorer the scorecard ACTUALLY applies to an item of this shape —
    derived from the scoring code paths, independently of the registry, so
    that the test comparing the two is not a tautology."""
    if layer == "Q":
        return "q_exact_date" if q_kind == "data" else "q_numeric_tolerance"
    if construct == "provenienza":
        return "s_marker_floor"
    return "s_orientation_markers"


def check_item(item) -> None:
    """Raise ValueError when an item's validity card is incoherent with how
    the item is scored (fail-closed; called by the bank validator)."""
    if item.validity is None:
        return
    definition = CONSTRUCT_DEFS.get(item.validity.construct_def)
    if definition is None:
        raise ValueError(
            f"{item.id}: validity.construct_def {item.validity.construct_def!r} "
            f"is not in the construct registry ({sorted(CONSTRUCT_DEFS)})"
        )
    if definition.construct != item.construct:
        raise ValueError(
            f"{item.id}: validity.construct_def {definition.id} defines "
            f"{definition.construct!r}, item is {item.construct!r}"
        )
    q_kind = item.q_answer.kind if item.q_answer is not None else None
    if definition.q_kind is not None and definition.q_kind != q_kind:
        raise ValueError(
            f"{item.id}: {definition.id} measures answers of kind "
            f"{definition.q_kind!r}, item answers {q_kind!r}"
        )
    actual = scorer_for(item.construct, item.layer, q_kind)
    if actual != definition.scorer:
        raise ValueError(
            f"{item.id}: scored by {actual}, but {definition.id} declares {definition.scorer}"
        )

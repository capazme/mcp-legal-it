"""Item schema for the LIMES item bank.

One schema for both strata (anchors and private, DESIGN §4.3): what differs is
only the directory and the rotation policy. Validation is strict and
fail-closed, in the house style of the LegalITA replica schema: an item that
does not satisfy the schema raises at load time rather than silently degrading
a score — a malformed item discovered mid-wave would invalidate the run that
consumed it, so the bank refuses to load it at all.

Two layers (DESIGN §4.1):

- **Q** (quantitative): exact answer, mechanical scorer, zero cost. The true
  value must come with a `derivation` computed independently of the tools
  under test — calibrating the meter with the tasks of the meter is circular.
- **S** (structural): discursive answer, rubric + mechanical observables.
  The mechanical part (orientation, citation markers, disqualifiers) always
  scores even when no judge is available (DESIGN §6: at least one mechanical
  scorer per dimension).

Kelsen boundary (DESIGN §1): every item measures observables on the
method-side of the boundary (computation, provenance, conflict criteria,
uncertainty signalling), never the merit of an outcome.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

STRATA = ("anchor", "private")
LAYERS = ("Q", "S")
Q_CONSTRUCTS = ("calcolo",)
S_CONSTRUCTS = (
    "provenienza",   # citation identification and fidelity
    "gerarchia",     # conflict of norms resolved by criterion
    "analogia",      # artt. 12-14 Preleggi: analogy allowed vs forbidden
    "revirement",    # open texture: overrulings, conflicting case law
    "motivazione",   # reasoned conclusion structure
    "diritto_ue",    # EU primacy and direct effect
)
TWIN_ELEMENTS = ("data", "profilo", "fonte")
ORIENTATIONS = ("affermare", "segnalare", "negare")

TWIN_CONSTRUCTS = ("gerarchia", "analogia", "revirement", "diritto_ue")

# LegalBench reasoning types (Guha et al. 2023, arXiv:2308.11462): the
# coverage tag of an item. Constructs stay LIMES's measurement axes; the
# type records WHICH legal reasoning skill the item exercises, so coverage
# gaps are visible (e.g. a construct measured only through rule recall).
REASONING_TYPES = (
    "issue_spotting",
    "rule_recall",
    "rule_application",
    "rule_conclusion",
    "interpretation",
    "rhetorical_understanding",
)
VALIDITY_KEYS = ("construct_def", "observable", "why_mechanical", "source")


class ValidationError(ValueError):
    """Raised when an item or a bank slice does not satisfy the schema."""


def _require(value: Any, allowed: tuple[str, ...], field_name: str) -> Any:
    if value not in allowed:
        raise ValidationError(
            f"{field_name}: expected one of {allowed}, got {value!r}"
        )
    return value


@dataclass(frozen=True)
class Toleranza:
    """Pre-registered rounding tolerance for a Q answer.

    `absolute` is an absolute delta in the answer's own unit (e.g. euro,
    days); `relative` is a relative delta against the true value. A Q answer
    passes when it satisfies at least one registered tolerance (most items
    register exactly one). No tolerance on the item means exact match.
    """

    absolute: float | None = None
    relative: float | None = None

    def allows(self, true_value: float, given: float) -> bool:
        if self.absolute is not None and abs(given - true_value) <= self.absolute:
            return True
        if self.relative is not None:
            if true_value == 0.0:
                return given == 0.0
            return abs(given - true_value) / abs(true_value) <= self.relative
        # No registered tolerance: exact match (docstring semantics).
        return given == true_value

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> Toleranza:
        return cls(
            absolute=d.get("absolute"),
            relative=d.get("relative"),
        )


@dataclass(frozen=True)
class QAnswer:
    """The mechanically verifiable core of a Q item.

    `kind` is "numero" (any real quantity: money, days, a percentage) or
    "data" (a calendar date, canonical string gg/mm/aaaa). `value` carries
    the true answer computed INDEPENDENTLY of the tools under test (DESIGN
    §4.1); for dates the scorer compares normalized calendar dates, for
    numbers it applies the pre-registered tolerance.
    """

    kind: str            # "numero" | "data"
    value: float | str   # float for "numero", "gg/mm/aaaa" for "data"
    unit: str            # "EUR", "giorni", "data", ...
    tolerance: Toleranza | None = None

    def to_dict(self) -> dict:
        d: dict = {"kind": self.kind, "value": self.value, "unit": self.unit}
        if self.tolerance is not None:
            d["tolerance"] = self.tolerance.to_dict()
        return d

    @classmethod
    def from_dict(cls, d: dict) -> QAnswer:
        missing = {"kind", "value", "unit"} - set(d)
        if missing:
            raise ValidationError(f"q_answer: missing keys {sorted(missing)}")
        kind = _require(d["kind"], ("numero", "data"), "q_answer.kind")
        value = d["value"]
        if kind == "numero":
            value = float(value)
        else:
            value = str(value)
        tolerance = d.get("tolerance")
        return cls(
            kind=kind,
            value=value,
            unit=str(d["unit"]),
            tolerance=Toleranza.from_dict(tolerance) if tolerance else None,
        )


@dataclass(frozen=True)
class Rubric:
    """One judge-scored requirement of an S item.

    `required` rubrics feed the H/A/U/M structural scores; a failed required
    rubric fails the item, mirroring the LegalITA product semantics (one
    broken load-bearing wall sinks the whole structure). `bonus` rubrics are
    reported separately and never gate pass/fail. `disqualifying: true`
    marks rubrics whose *violation* is disqualifying (e.g. proposing analogy
    where art. 14 Preleggi forbids it): the rubric is written so that
    violating it is the observable, and the judge verdict is fail-closed.
    """

    id: str
    text: str
    required: bool = True
    disqualifying: bool = False
    # True when the mechanical scorer already observes this requirement
    # (orientation, a citation marker): judges never re-score it — LLM
    # judges only touch the residual the mechanical layer cannot see.
    mechanical: bool = False

    def to_dict(self) -> dict:
        d = asdict(self)
        if not self.mechanical:
            d.pop("mechanical")
        return d

    @classmethod
    def from_dict(cls, d: dict) -> Rubric:
        missing = {"id", "text"} - set(d)
        if missing:
            raise ValidationError(f"rubric: missing keys {sorted(missing)}")
        unknown = sorted(set(d) - {"id", "text", "required", "disqualifying", "mechanical"})
        if unknown:
            raise ValidationError(f"rubric {d.get('id')!r}: unknown keys {unknown}")
        return cls(
            id=str(d["id"]),
            text=str(d["text"]),
            required=bool(d.get("required", True)),
            disqualifying=bool(d.get("disqualifying", False)),
            mechanical=bool(d.get("mechanical", False)),
        )


@dataclass(frozen=True)
class Validity:
    """Per-item content-validity card (DESIGN §8; Bean et al., NeurIPS 2025).

    The chain construct -> operational definition -> observable -> scorer is
    written item by item, not presumed: `construct_def` names an entry of
    the protocol's construct registry (protocol/validity.py), `observable`
    states what in the answer is measured, `why_mechanical` why a
    mechanical scorer can observe it (or what is left to the judges), and
    `source` the primary source the expected answer rests on.
    """

    construct_def: str
    observable: str
    why_mechanical: str
    source: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict, item_id: str = "?") -> Validity:
        if not isinstance(d, dict):
            raise ValidationError(f"{item_id}: validity must be a mapping")
        missing = [k for k in VALIDITY_KEYS if not str(d.get(k, "")).strip()]
        if missing:
            raise ValidationError(
                f"{item_id}: validity card incomplete, missing/empty {missing} "
                f"(every key of {list(VALIDITY_KEYS)} is required)"
            )
        unknown = sorted(set(d) - set(VALIDITY_KEYS))
        if unknown:
            raise ValidationError(f"{item_id}: validity: unknown keys {unknown}")
        return cls(**{k: str(d[k]).strip() for k in VALIDITY_KEYS})


@dataclass
class Item:
    id: str
    layer: str                  # "Q" | "S"
    construct: str
    prompt: str
    stratum: str                # "anchor" | "private" (rebound on load)
    q_answer: QAnswer | None = None
    derivation: str = ""        # Q: independent computation trail (required)
    anchor_set: str = ""        # anchor: e.g. "anchor-2026Q3"; private: ""
    family: str = ""            # twin family id; empty for singletons
    role: str = ""              # "a" | "b" within the family; empty for singletons
    twin_element: str = ""      # which legally relevant element diverges
    correct_orientation: str | None = None  # S-twin: expected divergence direction
    expected_markers: list[str] = field(default_factory=list)   # S: citation ids
    disqualifiers: list[str] = field(default_factory=list)      # S: forbidden moves
    rubrics: list[Rubric] = field(default_factory=list)
    expected_signal: str = ""   # revirement: what correct signalling means
    notes: str = ""
    validity: Validity | None = None
    reasoning_type: str = ""    # LegalBench type (REASONING_TYPES)
    # Contamination probes (DESIGN §8, B4): a paraphrase restates another
    # item's question with the same answer; a canary is a private-only item
    # that must never be published. Their gap vs the original is the signal.
    paraphrase_of: str = ""
    canary: bool = False
    # Generated Q items: the family, parameters and seed that produced the
    # item — the derivation is reproducible from them (A3).
    generator: dict = field(default_factory=dict)

    def is_twin(self) -> bool:
        return bool(self.family)

    def has_mechanical_expectation(self) -> bool:
        """True when the S item can be scored without any judge."""
        return (
            self.correct_orientation is not None
            or bool(self.expected_markers)
            or bool(self.disqualifiers)
        )

    def to_dict(self) -> dict:
        d: dict = {
            "id": self.id,
            "layer": self.layer,
            "construct": self.construct,
            "prompt": self.prompt,
        }
        if self.q_answer is not None:
            d["q_answer"] = self.q_answer.to_dict()
        if self.derivation:
            d["derivation"] = self.derivation
        if self.anchor_set:
            d["anchor_set"] = self.anchor_set
        if self.notes:
            d["notes"] = self.notes
        if self.is_twin():
            twin: dict = {
                "family": self.family,
                "role": self.role,
                "element": self.twin_element,
            }
            if self.correct_orientation is not None:
                twin["correct_orientation"] = self.correct_orientation
            d["twin"] = twin
        if self.correct_orientation is not None and not self.is_twin():
            d["correct_orientation"] = self.correct_orientation
        if self.expected_markers:
            d["expected_markers"] = list(self.expected_markers)
        if self.disqualifiers:
            d["disqualifiers"] = list(self.disqualifiers)
        if self.rubrics:
            d["rubrics"] = [r.to_dict() for r in self.rubrics]
        if self.expected_signal:
            d["expected_signal"] = self.expected_signal
        if self.validity is not None:
            d["validity"] = self.validity.to_dict()
        if self.reasoning_type:
            d["reasoning_type"] = self.reasoning_type
        if self.paraphrase_of:
            d["paraphrase_of"] = self.paraphrase_of
        if self.canary:
            d["canary"] = True
        if self.generator:
            d["generator"] = dict(self.generator)
        return d

    @classmethod
    def from_dict(cls, d: dict, *, stratum: str) -> Item:
        _require(stratum, STRATA, "stratum")
        layer = _require(d.get("layer"), LAYERS, "layer")
        allowed_constructs = Q_CONSTRUCTS if layer == "Q" else S_CONSTRUCTS
        construct = _require(d.get("construct"), allowed_constructs, "construct")
        item_id = str(d.get("id", ""))
        if not item_id or not d.get("prompt"):
            raise ValidationError("item: 'id' and 'prompt' are required")

        twin = d.get("twin")
        q_answer = QAnswer.from_dict(d["q_answer"]) if d.get("q_answer") else None
        rubrics = [Rubric.from_dict(r) for r in d.get("rubrics", [])]
        expected_signal = str(d.get("expected_signal", ""))
        derivation = str(d.get("derivation", ""))
        anchor_set = str(d.get("anchor_set", ""))
        expected_markers = [str(m) for m in d.get("expected_markers", [])]
        disqualifiers = [str(m) for m in d.get("disqualifiers", [])]

        # Layer discipline (fail-closed, DESIGN §4.1/§4.2).
        if layer == "Q":
            if q_answer is None:
                raise ValidationError(f"{item_id}: Q items require q_answer")
            if not derivation:
                raise ValidationError(
                    f"{item_id}: Q items require an independent derivation "
                    f"(no golden values derived from the tools under test)"
                )
            if rubrics:
                raise ValidationError(
                    f"{item_id}: Q items must not carry rubrics (mechanical layer)"
                )
        else:
            if q_answer is not None:
                raise ValidationError(
                    f"{item_id}: S items must not carry q_answer"
                )
            if not rubrics:
                raise ValidationError(f"{item_id}: S items require at least one rubric")
            if construct == "revirement" and not expected_signal:
                raise ValidationError(
                    f"{item_id}: revirement items must declare expected_signal"
                )
            if not (construct in TWIN_CONSTRUCTS or construct in ("provenienza", "diritto_ue", "motivazione")):
                raise ValidationError(
                    f"{item_id}: construct {construct!r} cannot carry mechanical "
                    f"expectations"
                )
            if construct in ("provenienza", "motivazione") and twin:
                raise ValidationError(
                    f"{item_id}: construct {construct!r} does not support twins "
                    f"(gemelle live on {', '.join(TWIN_CONSTRUCTS)})"
                )
            if not twin and construct in TWIN_CONSTRUCTS and not (
                expected_markers or disqualifiers
            ):
                raise ValidationError(
                    f"{item_id}: {construct} singleton without twins must still "
                    f"declare markers or disqualifiers (mechanical floor, DESIGN §6)"
                )
        if construct == "revirement" and not expected_signal:
            raise ValidationError(
                f"{item_id}: revirement items must declare expected_signal"
            )

        # Stratum discipline (DESIGN §4.3).
        if stratum == "anchor":
            if not anchor_set:
                raise ValidationError(f"{item_id}: anchors require anchor_set")
        elif anchor_set:
            raise ValidationError(
                f"{item_id}: private items must not declare anchor_set"
            )

        # Twin discipline.
        family = role = element = ""
        orientation = d.get("correct_orientation")
        if twin is not None:
            missing = {"family", "role", "element"} - set(twin)
            if missing:
                raise ValidationError(f"{item_id}: twin missing keys {sorted(missing)}")
            family = str(twin["family"])
            role = _require(twin["role"], ("a", "b"), f"{item_id}.twin.role")
            element = _require(twin["element"], TWIN_ELEMENTS, f"{item_id}.twin.element")
            # Top-level `correct_orientation` wins: `twin.get` must not
            # clobber an expectation already declared on the item.
            orientation = twin.get("correct_orientation", orientation)
        if orientation is not None:
            _require(orientation, ORIENTATIONS, f"{item_id}.correct_orientation")
            if construct not in TWIN_CONSTRUCTS:
                raise ValidationError(
                    f"{item_id}: correct_orientation only applies to "
                    f"{TWIN_CONSTRUCTS}"
                )

        known_keys = {
            "id", "layer", "construct", "prompt", "q_answer", "derivation",
            "anchor_set", "notes", "twin", "correct_orientation",
            "expected_markers", "disqualifiers", "rubrics", "expected_signal",
            "validity", "reasoning_type", "paraphrase_of", "canary", "generator",
        }
        unknown = sorted(set(d) - known_keys)
        if unknown:
            # A typo'd key ("validty") would otherwise vanish silently and the
            # item would load without the card it claims to carry.
            raise ValidationError(f"{item_id}: unknown keys {unknown}")
        validity = (
            Validity.from_dict(d["validity"], item_id) if "validity" in d else None
        )
        reasoning_type = str(d.get("reasoning_type", ""))
        if reasoning_type:
            _require(reasoning_type, REASONING_TYPES, f"{item_id}.reasoning_type")
        canary = d.get("canary", False)
        if not isinstance(canary, bool):
            raise ValidationError(f"{item_id}: canary must be a boolean")
        if canary and stratum == "anchor":
            raise ValidationError(
                f"{item_id}: a canary is private by definition (never an anchor)"
            )
        paraphrase_of = str(d.get("paraphrase_of", ""))
        if paraphrase_of == item_id:
            raise ValidationError(f"{item_id}: paraphrase_of points to itself")
        generator = d.get("generator") or {}
        if not isinstance(generator, dict):
            raise ValidationError(f"{item_id}: generator must be a mapping")
        if generator and layer != "Q":
            raise ValidationError(f"{item_id}: only Q items are generated")
        if generator and not {"family", "seed", "params"} <= set(generator):
            raise ValidationError(
                f"{item_id}: generator needs family, seed and params "
                f"(the derivation must be reproducible)"
            )

        return cls(
            id=item_id,
            layer=layer,
            construct=construct,
            prompt=str(d["prompt"]),
            stratum=stratum,
            q_answer=q_answer,
            derivation=derivation,
            anchor_set=anchor_set,
            family=family,
            role=role,
            twin_element=element,
            correct_orientation=orientation,
            expected_markers=expected_markers,
            disqualifiers=disqualifiers,
            rubrics=rubrics,
            expected_signal=expected_signal,
            notes=str(d.get("notes", "")),
            validity=validity,
            reasoning_type=reasoning_type,
            paraphrase_of=paraphrase_of,
            canary=canary,
            generator=dict(generator),
        )


@dataclass
class Bank:
    """A loaded bank slice: anchors, private, or their union.

    Cross-item consistency is checked here, at load time, not in every
    scorer: twins come in complete (a, b) pairs, family members share
    layer/construct/stratum/element, and ids are unique across the slice.
    """

    items: list[Item]

    def by_id(self, item_id: str) -> Item:
        for item in self.items:
            if item.id == item_id:
                return item
        raise ValidationError(f"unknown item id: {item_id!r}")

    def items_of_layer(self, layer: str) -> list[Item]:
        return [i for i in self.items if i.layer == layer]

    def items_of_construct(self, construct: str) -> list[Item]:
        return [i for i in self.items if i.construct == construct]

    def anchor_items(self) -> list[Item]:
        return [i for i in self.items if i.stratum == "anchor"]

    def private_items(self) -> list[Item]:
        return [i for i in self.items if i.stratum == "private"]

    def twin_families(self) -> dict[str, tuple[Item, Item]]:
        families: dict[str, list[Item]] = {}
        for item in self.items:
            if item.is_twin():
                families.setdefault(item.family, []).append(item)
        out: dict[str, tuple[Item, Item]] = {}
        for family, members in families.items():
            roles = sorted(m.role for m in members)
            if len(members) != 2 or roles != ["a", "b"]:
                raise ValidationError(
                    f"twin family {family!r}: expected exactly roles a and b, got {roles}"
                )
            a, b = members
            if (a.layer, a.construct, a.stratum) != (b.layer, b.construct, b.stratum):
                raise ValidationError(
                    f"twin family {family!r}: members must share layer, "
                    f"construct and stratum"
                )
            if a.twin_element != b.twin_element:
                raise ValidationError(
                    f"twin family {family!r}: members must diverge on the same element"
                )
            out[family] = (a, b)
        return out

    def validate(self, require_validity: bool = False) -> None:
        ids = [i.id for i in self.items]
        if len(set(ids)) != len(ids):
            dupes = sorted({i for i in ids if ids.count(i) > 1})
            raise ValidationError(f"duplicate item ids: {dupes}")
        self.twin_families()  # raises on incomplete or inconsistent families
        known = set(ids)
        by_id = {i.id: i for i in self.items}
        for item in self.items:
            if item.paraphrase_of:
                if item.paraphrase_of not in known:
                    raise ValidationError(
                        f"{item.id}: paraphrase_of {item.paraphrase_of!r} is not in the bank"
                    )
                original = by_id[item.paraphrase_of]
                if (original.layer, original.construct) != (item.layer, item.construct):
                    raise ValidationError(
                        f"{item.id}: a paraphrase must share layer and construct "
                        f"with {original.id} (same question, same answer)"
                    )
                if original.q_answer is not None and original.q_answer != item.q_answer:
                    raise ValidationError(
                        f"{item.id}: a paraphrase must carry the same q_answer as {original.id}"
                    )
            if require_validity:
                if item.validity is None:
                    raise ValidationError(
                        f"{item.id}: no validity card — an item without one does "
                        f"not enter this wave (DESIGN §8)"
                    )
                if not item.reasoning_type:
                    raise ValidationError(
                        f"{item.id}: reasoning_type (LegalBench) is required in this wave"
                    )


def _read_entries(path: Path) -> list[dict]:
    """Read one slice file, turning malformed JSON into a schema error with
    the file name (fail-closed with a useful message, never a traceback)."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValidationError(f"{path.name}: invalid JSON ({exc})") from exc
    entries = payload["items"] if isinstance(payload, dict) and "items" in payload else payload
    if not isinstance(entries, list):
        raise ValidationError(f"{path.name}: expected a list of items or {{'items': [...]}}")
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValidationError(f"{path.name}: every item must be a JSON object")
    return entries


def _load_file(path: Path, stratum: str, overlay: dict[str, dict]) -> list[Item]:
    items: list[Item] = []
    for entry in _read_entries(path):
        extra = overlay.get(str(entry.get("id", "")))
        if extra:
            # The overlay only ADDS metadata to frozen items (anchors never
            # change a posteriori, DESIGN §4.3); it may not redefine them.
            clash = sorted(set(extra) & set(entry))
            if clash:
                raise ValidationError(
                    f"{entry.get('id')}: validity overlay redefines {clash}"
                )
            entry = {**entry, **extra}
        try:
            items.append(Item.from_dict(entry, stratum=stratum))
        except ValidationError as exc:
            raise ValidationError(f"{path.name}: {exc}") from exc
    return items


def _load_slice(directory: Path, stratum: str, overlay: dict[str, dict] | None = None) -> list[Item]:
    items: list[Item] = []
    if not directory.is_dir():
        return items
    for path in sorted(directory.glob("*.json")):
        items.extend(_load_file(path, stratum, overlay or {}))
    return items


def _load_overlay(bank_dir: Path) -> dict[str, dict]:
    """Validity overlays (bank/validity/*.json): metadata for items frozen
    before validity cards existed, keyed by item id."""
    overlay: dict[str, dict] = {}
    directory = bank_dir / "validity"
    if not directory.is_dir():
        return overlay
    allowed = {"validity", "reasoning_type"}
    for path in sorted(directory.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValidationError(f"{path.name}: invalid JSON ({exc})") from exc
        if not isinstance(payload, dict):
            raise ValidationError(f"{path.name}: overlay must map item id -> metadata")
        for item_id, extra in payload.items():
            if item_id.startswith("$"):
                continue  # $comment
            if not isinstance(extra, dict) or set(extra) - allowed:
                raise ValidationError(
                    f"{path.name}: {item_id}: overlay may only carry {sorted(allowed)}"
                )
            if item_id in overlay:
                raise ValidationError(f"{path.name}: {item_id} overlaid twice")
            overlay[item_id] = extra
    return overlay


def apply_exclusions(bank: Bank, excluded) -> Bank:
    """Drop the items a wave excludes after human review (DESIGN §8.2).

    Fail-closed: an unknown id is an error (a typo would silently keep the
    item), and a twin family must be excluded whole — half a family would
    leave an unpaired twin whose discrimination cannot be scored."""
    excluded = set(excluded)
    if not excluded:
        return bank
    known = {i.id for i in bank.items}
    unknown = sorted(excluded - known)
    if unknown:
        raise ValidationError(f"excluded ids not in the bank: {unknown}")
    for family, (a, b) in bank.twin_families().items():
        if (a.id in excluded) != (b.id in excluded):
            kept = b.id if a.id in excluded else a.id
            raise ValidationError(
                f"twin family {family!r} half-excluded: exclude {kept} as well "
                f"(a twin without its partner cannot be scored)"
            )
    anchors = [i.id for i in bank.items if i.id in excluded and i.stratum == "anchor"]
    if anchors:
        raise ValidationError(f"anchors cannot be excluded (they never change): {anchors}")
    kept_items = [i for i in bank.items if i.id not in excluded]
    orphan = [i.id for i in kept_items if i.paraphrase_of and i.paraphrase_of in excluded]
    if orphan:
        raise ValidationError(f"paraphrases of excluded items must be excluded too: {orphan}")
    out = Bank(items=kept_items)
    out.validate()
    return out


def load_bank(
    bank_dir: Path,
    slices: tuple[str, ...] | list[str] = (),
    require_validity: bool = False,
    excluded=(),
) -> Bank:
    """Load the bank (anchors + private) with fail-closed validation.

    `slices` restricts the load to named files under `bank_dir` (a wave's
    own slice); empty = every file of both strata. The stratum of a slice
    is its directory (`anchors/` or `private/`).

    Both strata must be present and non-empty: an empty stratum would
    silently change what a wave measures (e.g. lose the equating anchors,
    DESIGN §4.3), so a missing directory is a schema error, not an empty
    slice.
    """
    overlay = _load_overlay(bank_dir)
    if slices:
        anchors: list[Item] = []
        private: list[Item] = []
        for rel in slices:
            path = bank_dir / rel
            parent = Path(rel).parts[0] if Path(rel).parts else ""
            if parent not in ("anchors", "private"):
                raise ValidationError(f"slice {rel!r}: must live under anchors/ or private/")
            if not path.is_file():
                raise ValidationError(f"slice {rel!r}: file not found under {bank_dir}")
            stratum = "anchor" if parent == "anchors" else "private"
            (anchors if stratum == "anchor" else private).extend(
                _load_file(path, stratum, overlay)
            )
    else:
        anchors = _load_slice(bank_dir / "anchors", "anchor", overlay)
        private = _load_slice(bank_dir / "private", "private", overlay)
    if not anchors:
        raise ValidationError(
            f"{bank_dir / 'anchors'}: anchor stratum missing or empty"
        )
    if not private:
        raise ValidationError(
            f"{bank_dir / 'private'}: private stratum missing or empty"
        )
    bank = Bank(items=anchors + private)
    bank.validate(require_validity=require_validity)
    return apply_exclusions(bank, excluded)

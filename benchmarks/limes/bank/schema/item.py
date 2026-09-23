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

TWIN_CONSTRUCTS = ("gerarchia", "analogia", "revirement")


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

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> Rubric:
        missing = {"id", "text"} - set(d)
        if missing:
            raise ValidationError(f"rubric: missing keys {sorted(missing)}")
        return cls(
            id=str(d["id"]),
            text=str(d["text"]),
            required=bool(d.get("required", True)),
            disqualifying=bool(d.get("disqualifying", False)),
        )


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
            if construct in ("provenienza", "motivazione", "diritto_ue") and twin:
                raise ValidationError(
                    f"{item_id}: construct {construct!r} does not support twins "
                    f"(gemelle live on gerarchia/analogia/revirement)"
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

    def validate(self) -> None:
        ids = [i.id for i in self.items]
        if len(set(ids)) != len(ids):
            dupes = sorted({i for i in ids if ids.count(i) > 1})
            raise ValidationError(f"duplicate item ids: {dupes}")
        self.twin_families()  # raises on incomplete or inconsistent families


def _load_slice(directory: Path, stratum: str) -> list[Item]:
    items: list[Item] = []
    if not directory.is_dir():
        return items
    for path in sorted(directory.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        entries = payload["items"] if isinstance(payload, dict) else payload
        for entry in entries:
            items.append(Item.from_dict(entry, stratum=stratum))
    return items


def load_bank(bank_dir: Path) -> Bank:
    """Load the full bank (anchors + private) with fail-closed validation.

    Both strata must be present and non-empty: an empty stratum would
    silently change what a wave measures (e.g. lose the equating anchors,
    DESIGN §4.3), so a missing directory is a schema error, not an empty
    slice.
    """
    anchors = _load_slice(bank_dir / "anchors", "anchor")
    private = _load_slice(bank_dir / "private", "private")
    if not anchors:
        raise ValidationError(
            f"{bank_dir / 'anchors'}: anchor stratum missing or empty"
        )
    if not private:
        raise ValidationError(
            f"{bank_dir / 'private'}: private stratum missing or empty"
        )
    bank = Bank(items=anchors + private)
    bank.validate()
    return bank

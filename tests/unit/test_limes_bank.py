"""Unit tests for the LIMES item bank (schema + seed data).

Real-bank tests pin the seed content that wave 0 freezes in the tag;
schema tests build minimal JSON trees in tmp_path and assert that every
malformed shape raises at load time (fail-closed: a bad item must abort
the run that would consume it, never silently degrade a score).
"""

import json
from pathlib import Path

import pytest

from benchmarks.limes.bank.schema.item import (
    Bank,
    Item,
    Toleranza,
    ValidationError,
    load_bank,
)
from benchmarks.limes.bank.schema.validate import validate_bank

REPO_ROOT = Path(__file__).resolve().parents[2]
BANK_DIR = REPO_ROOT / "benchmarks" / "limes" / "bank"


@pytest.fixture(scope="module")
def bank() -> Bank:
    return load_bank(BANK_DIR)


class TestSeedBankContent:
    """The seed bank as DESIGN §7 freezes it for wave 0."""

    def test_loads_fail_closed(self, bank):
        # validate() re-checks cross-item consistency (unique ids, twins).
        bank.validate()

    def test_total_counts(self, bank):
        assert len(bank.items) == 27
        assert len(bank.anchor_items()) == 10
        assert len(bank.private_items()) == 17

    def test_layer_counts(self, bank):
        assert len(bank.items_of_layer("Q")) == 13
        assert len(bank.items_of_layer("S")) == 14

    def test_twin_families_live_in_private_stratum(self, bank):
        families = bank.twin_families()
        assert set(families) == {"G2", "A2", "R2"}
        for a, b in families.values():
            assert a.is_twin() and b.is_twin()
            assert a.family == b.family
            assert a.stratum == "private" and b.stratum == "private"
            assert a.id != b.id
            # Gemelle diverge on the SAME element (that is the point).
            assert a.twin_element == b.twin_element

    def test_mechanical_s_count(self, bank):
        mechanical = [i for i in bank.items if i.has_mechanical_expectation()]
        assert len(mechanical) == 14
        assert all(i.layer == "S" for i in mechanical)

    def test_by_id_lookup(self, bank):
        assert bank.by_id("QA-01").layer == "Q"
        assert bank.by_id("QAS-01").construct == "provenienza"
        with pytest.raises(ValidationError):
            bank.by_id("NOPE-99")

    def test_items_of_construct(self, bank):
        calcolo = bank.items_of_construct("calcolo")
        assert calcolo
        assert all(i.construct == "calcolo" for i in calcolo)

    def test_q_items_carry_answers_s_items_carry_rubrics(self, bank):
        for item in bank.items_of_layer("Q"):
            assert item.q_answer is not None and not item.rubrics
            assert item.derivation  # Kelsen boundary: no circular goldens
        for item in bank.items_of_layer("S"):
            assert item.rubrics and item.q_answer is None

    def test_anchors_declare_anchor_set(self, bank):
        for item in bank.anchor_items():
            assert item.anchor_set


def _s_anchor(**overrides) -> dict:
    base = {
        "id": "XA-01",
        "layer": "S",
        "construct": "motivazione",
        "prompt": "Domanda ancora valida.",
        "derivation": "test",
        "anchor_set": "struttura-2026",
        "rubrics": [{"id": "r1", "text": "una cosa", "required": True}],
    }
    base.update(overrides)
    return base


def _s_private(**overrides) -> dict:
    base = {
        "id": "XP-01",
        "layer": "S",
        "construct": "motivazione",
        "prompt": "Domanda privata valida.",
        "rubrics": [{"id": "r1", "text": "una cosa", "required": True}],
    }
    base.update(overrides)
    return base


class TestSchemaFailClosed:
    """Hand-built bank trees: every violation raises at load time."""

    @staticmethod
    def _write(tmp_path, anchor_items, private_items) -> Path:
        d = tmp_path / "bank"
        (d / "anchors").mkdir(parents=True)
        (d / "private").mkdir()
        (d / "anchors" / "batch.json").write_text(
            json.dumps(anchor_items), encoding="utf-8"
        )
        (d / "private" / "batch.json").write_text(
            json.dumps(private_items), encoding="utf-8"
        )
        return d

    def _bank(self, tmp_path, bad_item, where="anchors") -> Path:
        """A bank with one malformed item and one valid item per stratum."""
        bad = [bad_item] if where == "anchors" else [_s_anchor()]
        priv = [_s_private()] if where == "anchors" else [bad_item]
        return self._write(tmp_path, bad, priv)

    def test_unknown_layer_rejected(self, tmp_path):
        with pytest.raises(ValidationError, match="layer"):
            load_bank(self._bank(tmp_path, _s_anchor(layer="X")))

    def test_unknown_construct_rejected(self, tmp_path):
        with pytest.raises(ValidationError, match="construct"):
            load_bank(self._bank(tmp_path, _s_anchor(construct="cucina")))

    def test_q_requires_q_answer(self, tmp_path):
        bad = _s_anchor(
            layer="Q", id="XQ-01", construct="calcolo", rubrics=[]
        )
        with pytest.raises(ValidationError, match="q_answer"):
            load_bank(self._bank(tmp_path, bad))

    def test_q_with_rubrics_rejected(self, tmp_path):
        bad = _s_anchor(
            layer="Q",
            id="XQ-02",
            construct="calcolo",
            q_answer={"kind": "numero", "value": 42, "unit": "EUR"},
        )
        with pytest.raises(ValidationError, match="must not carry rubrics"):
            load_bank(self._bank(tmp_path, bad))

    def test_s_with_q_answer_rejected(self, tmp_path):
        bad = _s_anchor(q_answer={"kind": "numero", "value": 1, "unit": "EUR"})
        with pytest.raises(ValidationError, match="must not carry q_answer"):
            load_bank(self._bank(tmp_path, bad))

    def test_q_requires_derivation(self, tmp_path):
        bad = _s_anchor(
            layer="Q",
            id="XQ-03",
            construct="calcolo",
            rubrics=[],
            q_answer={"kind": "numero", "value": 42, "unit": "EUR"},
            derivation="",
        )
        with pytest.raises(ValidationError, match="derivation"):
            load_bank(self._bank(tmp_path, bad))

    def test_unknown_q_kind_rejected(self, tmp_path):
        bad = _s_anchor(
            layer="Q",
            id="XQ-04",
            construct="calcolo",
            rubrics=[],
            q_answer={"kind": "booleano", "value": True, "unit": "bool"},
        )
        with pytest.raises(ValidationError, match="kind"):
            load_bank(self._bank(tmp_path, bad))

    def test_q_answer_missing_unit_rejected(self, tmp_path):
        bad = _s_anchor(
            layer="Q",
            id="XQ-05",
            construct="calcolo",
            rubrics=[],
            q_answer={"kind": "numero", "value": 42},
        )
        with pytest.raises(ValidationError, match="unit"):
            load_bank(self._bank(tmp_path, bad))

    def test_rubric_missing_keys_rejected(self, tmp_path):
        bad = _s_anchor(rubrics=[{"id": "r1"}])
        with pytest.raises(ValidationError, match="rubric"):
            load_bank(self._bank(tmp_path, bad))

    def test_unknown_marker_id_rejected_by_validator(self, tmp_path):
        # The registry cross-check lives in validate_bank, not load_bank.
        bad = _s_anchor(expected_markers=["marker-che-non-esiste"])
        d = self._bank(tmp_path, bad)
        with pytest.raises(ValidationError, match="marker"):
            validate_bank(d)

    def test_singleton_twin_construct_needs_mechanical_floor(self, tmp_path):
        # A gerarchia singleton (no twin) must declare markers/disqualifiers.
        with pytest.raises(ValidationError, match="markers"):
            load_bank(self._bank(tmp_path, _s_anchor(construct="gerarchia")))

    def test_private_must_not_declare_anchor_set(self, tmp_path):
        bad = _s_private(anchor_set="struttura-2026")
        with pytest.raises(ValidationError, match="anchor_set"):
            load_bank(self._bank(tmp_path, bad, where="private"))

    def test_anchor_requires_anchor_set(self, tmp_path):
        with pytest.raises(ValidationError, match="anchor_set"):
            load_bank(self._bank(tmp_path, _s_anchor(anchor_set="")))

    def test_twin_missing_keys_rejected(self, tmp_path):
        # Twin-key validation happens on twin-capable constructs.
        with pytest.raises(ValidationError, match="twin missing keys"):
            load_bank(
                self._bank(
                    tmp_path,
                    _s_anchor(
                        construct="gerarchia",
                        twin={"family": "G", "role": "a"},
                    ),
                )
            )

    def test_unknown_twin_role_rejected(self, tmp_path):
        bad = _s_anchor(
            construct="gerarchia",
            twin={"family": "G", "role": "z", "element": "data"},
        )
        with pytest.raises(ValidationError, match="role"):
            load_bank(self._bank(tmp_path, bad))

    def test_unknown_orientation_rejected(self, tmp_path):
        with pytest.raises(ValidationError, match="correct_orientation"):
            load_bank(
                self._bank(tmp_path, _s_anchor(correct_orientation="dubitare"))
            )

    def test_orientation_on_non_twin_construct_rejected(self, tmp_path):
        with pytest.raises(ValidationError, match="correct_orientation"):
            load_bank(
                self._bank(
                    tmp_path,
                    _s_anchor(correct_orientation="affermare"),
                )
            )

    def test_lone_twin_is_not_a_family(self, tmp_path):
        bad = _s_anchor(
            construct="gerarchia",
            expected_markers=["cc-1176"],
            twin={"family": "f", "role": "a", "element": "fonte"},
        )
        with pytest.raises(ValidationError, match="twin family"):
            load_bank(self._bank(tmp_path, bad))

    def test_root_must_be_list_or_items(self, tmp_path):
        d = tmp_path / "bank"
        (d / "anchors").mkdir(parents=True)
        (d / "private").mkdir()
        (d / "anchors" / "batch.json").write_text(
            json.dumps({"id": "XA-01"}), encoding="utf-8"
        )
        (d / "private" / "batch.json").write_text(
            json.dumps([_s_private()]), encoding="utf-8"
        )
        with pytest.raises(KeyError):
            load_bank(d)

    def test_both_strata_required(self, tmp_path):
        d = self._write(tmp_path, [_s_anchor()], [])
        with pytest.raises(ValidationError, match="private"):
            load_bank(d)

    def test_duplicate_ids_rejected(self, tmp_path):
        bank = Bank(
            items=[
                Item.from_dict(_s_anchor(), stratum="anchor"),
                Item.from_dict(_s_anchor(), stratum="anchor"),
            ]
        )
        with pytest.raises(ValidationError, match="duplicate"):
            bank.validate()

    def test_validate_bank_entrypoint(self, tmp_path):
        report = validate_bank(
            self._write(tmp_path, [_s_anchor()], [_s_private()])
        )
        assert report["items"] == 2
        assert report["anchors"] == 1 and report["private"] == 1
        assert report["q"] == 0 and report["s"] == 2
        assert report["twin_families"] == 0


class TestToleranza:
    def test_relative_is_a_fraction_with_inclusive_edge(self):
        # 0.05 of 1000 → [950, 1050], edges inclusive (hand-computed).
        tol = Toleranza(relative=0.05)
        assert tol.allows(1000.0, 950.0)
        assert tol.allows(1000.0, 1050.0)
        assert not tol.allows(1000.0, 949.99)
        assert not tol.allows(1000.0, 1050.01)

    def test_absolute_window(self):
        tol = Toleranza(absolute=0.5)
        assert tol.allows(1.0, 1.5)
        assert not tol.allows(1.0, 1.51)

    def test_no_tolerance_is_exact(self):
        tol = Toleranza()
        assert tol.allows(7.0, 7.0)
        assert not tol.allows(7.0, 7.0001)

    def test_relative_on_zero_true_value(self):
        tol = Toleranza(relative=0.1)
        assert tol.allows(0.0, 0.0)
        assert not tol.allows(0.0, 0.01)

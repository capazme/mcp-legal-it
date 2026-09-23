"""Unit tests for the LIMES analysis layer: McNemar, rank-biserial,
bootstrap, Newcombe, non-inferiority, pass^k, equating, scorecard, paired
comparison. All values are hand-computed; the bootstrap is seeded, so its
interval is asserted against the declared protocol seed."""

import math
from pathlib import Path

import pytest

from benchmarks.limes.analysis.compare import compare_cells
from benchmarks.limes.analysis.equating import (
    WaveScores,
    anchor_delta,
    drift_guard,
    equated_private,
)
from benchmarks.limes.analysis.scorecard import build_scorecard, construct_key
from benchmarks.limes.analysis.stats import (
    bootstrap_ci,
    mcnemar_exact,
    non_inferiority,
    pass_at_k,
    rank_biserial,
    rank_biserial_binary,
    risk_difference_newcombe,
)
from benchmarks.limes.bank.schema.item import load_bank
from benchmarks.limes.protocol.rules import load_protocol

REPO_ROOT = Path(__file__).resolve().parents[2]
BANK_DIR = REPO_ROOT / "benchmarks" / "limes" / "bank"
PROTOCOL_FILE = REPO_ROOT / "benchmarks" / "limes" / "protocol" / "protocol.yaml"
SEED = 20260922  # protocol seed: the bootstrap must reproduce under it


class TestMcNemar:
    def test_hand_computed_two_discordant(self):
        # b=1, c=2: p = 2 * P(X<=1 | Bin(3, .5)) = 2 * 4/8 = 1.0
        assert mcnemar_exact(1, 2)["p_value"] == 1.0

    def test_perfectly_discordant(self):
        # b=0, c=5: p = 2 * (1/2)^5 = 0.0625
        assert math.isclose(mcnemar_exact(0, 5)["p_value"], 0.0625)

    def test_no_discordant_pairs(self):
        r = mcnemar_exact(0, 0)
        assert r["p_value"] == 1.0 and r["statistic"] is None

    def test_never_exceeds_one(self):
        assert mcnemar_exact(0, 10)["p_value"] == min(1.0, 2 * (1 / 2) ** 10)


class TestRankBiserial:
    def test_hand_computed(self):
        # Pairs (5,1) and (4,2): x always larger → +1.
        assert rank_biserial([5.0, 4.0], [1.0, 2.0]) == 1.0
        # (1,5) and (2,4): x always smaller → -1.
        assert rank_biserial([1.0, 2.0], [5.0, 4.0]) == -1.0
        # (3,3) tie: 1.5 vs 1.5 each pair → 0.
        assert rank_biserial([3.0], [3.0]) == 0.0

    def test_missing_pairs_return_none(self):
        assert rank_biserial([], []) is None
        assert rank_biserial([1.0], [2.0, 3.0]) is None

    def test_binary_wrapper(self):
        assert rank_biserial_binary([True, True], [False, False]) == 1.0
        assert rank_biserial_binary([True, False], [True, False]) == 0.0


class TestBootstrap:
    def test_seeded_and_reproducible(self):
        values = [1.0] * 8 + [0.0] * 2
        ci = bootstrap_ci(values, statistic=sum, seed=SEED)
        again = bootstrap_ci(values, statistic=sum, seed=SEED)
        assert ci == again
        lo, hi = ci
        # Ten resampled sums; every sum of 10 draws lies in [0, 10] and the
        # interval brackets the point estimate 8.0.
        assert 0 <= lo <= hi <= 10.0
        assert lo <= 8.0 <= hi

    def test_all_ones_degenerates_to_n(self):
        assert bootstrap_ci([1.0] * 10, statistic=sum, seed=SEED) == (10.0, 10.0)

    def test_empty_is_none(self):
        assert bootstrap_ci([], statistic=sum) is None


class TestNewcombe:
    def test_hand_computed_boundary(self):
        # x1=0, n1=10: the Wilson lower limit is exactly 0 at zero
        # successes, and with x2=n2=10 the Wilson upper limit is exactly
        # 1 — so the Newcombe lower bound is d - 0 = -1 by construction.
        rd, lo, hi = risk_difference_newcombe(0, 10, 10, 10)
        assert math.isclose(rd, -1.0)
        assert math.isclose(lo, -1.0)
        # hi = -1 + sqrt(0.2775^2 + 0.2775^2) ≈ -0.6076 (Wilson half-width
        # for 0/10 and 10/10 is z²/(2n)/(1+z²/n) ≈ 0.2775, hand-derived).
        assert -0.62 < hi < -0.59

    def test_zero_n_raises(self):
        with pytest.raises(ValueError):
            risk_difference_newcombe(1, 0, 1, 10)


class TestNonInferiority:
    def test_margin_decision(self):
        # Treated 45/50 vs control 50/50, margin 0.10: rd=-0.10; the
        # Newcombe lower bound must fall below -0.10 → NOT non-inferior.
        r = non_inferiority(45, 50, 50, 50, margin=0.10)
        assert math.isclose(r["risk_difference"], -0.10)
        assert r["non_inferior"] is False
        # Same numbers, wider margin 0.20 → non-inferior iff lo > -0.20.
        r20 = non_inferiority(45, 50, 50, 50, margin=0.20)
        assert r20["non_inferior"] is (r["ci_lower"] > -0.20)

    def test_margin_bounds_enforced(self):
        with pytest.raises(ValueError):
            non_inferiority(1, 2, 1, 2, margin=0.0)
        with pytest.raises(ValueError):
            non_inferiority(1, 2, 1, 2, margin=1.0)


class TestPassAtK:
    def test_all_pass(self):
        assert pass_at_k([True] * 6, k=3) == 1.0

    def test_one_fail_breaks_windows(self):
        # F T T T T T → windows [FTT, TTT, TTT, TTT] → 3/4.
        assert pass_at_k([False, True, True, True, True, True], k=3) == 0.75

    def test_insufficient_outcomes(self):
        assert pass_at_k([True, False], k=3) is None
        assert pass_at_k([True], k=0) is None


class TestEquating:
    def test_anchor_delta_hand_computed(self):
        current = WaveScores("w1", 9, 10, 12, 17)
        previous = WaveScores("w0", 8, 10, 10, 17)
        assert math.isclose(anchor_delta(current, previous), 0.10)

    def test_equated_private(self):
        # 12/17 - 0.10 ≈ 0.6059 (hand-computed).
        current = WaveScores("w1", 9, 10, 12, 17)
        previous = WaveScores("w0", 8, 10, 10, 17)
        assert math.isclose(equated_private(current, previous), 12 / 17 - 0.10)

    def test_drift_guard_flags_beyond_max(self):
        # 9/10 vs 8/10: delta +0.10, inside the 0.2 guard.
        current = WaveScores("w1", 9, 10, 12, 17)
        previous = WaveScores("w0", 8, 10, 10, 17)
        assert drift_guard(current, previous, max_drift=0.2)["applicable"] is True
        # 5/10 vs 8/10: delta -0.30, beyond the guard → not applicable.
        drifted = WaveScores("w1", 5, 10, 12, 17)
        guard = drift_guard(drifted, previous, max_drift=0.2)
        assert guard["applicable"] is False
        assert guard["reason"] == "anchor drift beyond guard"

    def test_no_anchors_not_applicable(self):
        a = WaveScores("w1", 0, 0, 1, 2)
        b = WaveScores("w0", 0, 0, 1, 2)
        assert drift_guard(a, b)["applicable"] is False
        assert equated_private(a, b) is None


class TestScorecard:
    @pytest.fixture(scope="class")
    def bank(self):
        return load_bank(BANK_DIR)

    @pytest.fixture(scope="class")
    def protocol(self):
        return load_protocol(PROTOCOL_FILE)

    def test_construct_key_map(self):
        assert construct_key("calcolo") == "C"
        assert construct_key("gerarchia") == "H"
        assert construct_key("revirement") == "U"
        assert construct_key("diritto_ue") == "H"

    def test_full_scorecard_dimensions(self, bank, protocol):
        answers = {
            # Q layer: 4 pass, 1 fail of 5 shown (hand-written answers).
            "QA-01": "scade il 13/06/2024",        # pass
            "QA-02": "493,15 euro",                # pass
            "QA-03": "art. 112 c.p.c.",            # pass
            "QP-02": "425,75 euro",                # pass
            "QP-05": "circa 990 euro",             # fail (outside 0.02)
            # S layer with expected markers and orientations.
            "SP-02A": "La pretesa non può fondarsi sul regolamento: è vietata, "
                      "ai sensi dell'art. 4 disposizioni sulla legge in generale.",
            "SP-02B": "Si applica pertanto la disciplina regolamentare; "
                      "criterio è l'art. 4 disp. prel.",
            "SP-03B": "La sanzione non è ammessa: è vietata dall'art. 14 "
                      "disposizioni sulla legge in generale.",
            "SP-04B": "La nuova base CGUE non è in vigore: sussiste incertezza "
                      "in corso di decisione davanti alle sezioni unite.",
            "QAS-01": "L'art. 1176 c.c. impone la diligenza.",
        }
        card = build_scorecard(
            bank, "claude-opus-4-6", "bare", answers,
            tool_texts=None, protocol=protocol,
        )
        assert card.dimensions["C"].n == 5
        assert card.dimensions["C"].passed == 4
        # P with tool_texts=None: fidelity undefined, identifiability only.
        assert card.dimensions["P"].detail["fidelity_mean"] is None
        # U (revirement): SP-04B answered correctly.
        assert card.dimensions["U"].passed == 1
        # H (gerarchia): both twins correct.
        assert card.dimensions["H"].passed == 2
        # A (analogia): SP-03B correct, no disqualifying violation.
        assert card.dimensions["A"].detail["disqualifying_violations"] == 0

    def test_disqualifier_floors_the_dimension(self, bank, protocol):
        answers = {
            "QAS-01": "Ai sensi dell'art. 1175 c.c. …",  # forbidden near-miss
        }
        card = build_scorecard(
            bank, "m", "bare", answers, tool_texts=None, protocol=protocol
        )
        assert card.dimensions["P"].detail["disqualifying_violations"] == 1
        assert card.dimensions["P"].passed == 0

    def test_render_is_a_vector(self, bank, protocol):
        card = build_scorecard(
            bank, "m", "bare", {}, tool_texts=None, protocol=protocol
        )
        text = card.render()
        for key in ("C", "P", "H", "A", "U", "M", "R"):
            assert key in text
        assert "n/d" in text  # empty cell never pretends to score 0

    def test_reliability_is_nd_without_data(self, bank, protocol):
        # No attempts -> no mean_attempts number: 1.0 fabricated out of
        # nothing would make an all-excluded cell look perfectly reliable.
        card = build_scorecard(
            bank, "m", "bare", {}, tool_texts=None, protocol=protocol,
            attempts=None, excluded=0,
        )
        assert card.reliability["mean_attempts"] is None
        assert card.reliability["excluded_rate"] is None
        assert "mean_attempts=n/d" in card.render()
        # With real data the numbers are there again (scorable items exist,
        # so excluded_rate is defined too).
        card2 = build_scorecard(
            bank, "m", "bare", {"QA-01": "13/06/2024"}, tool_texts=None,
            protocol=protocol, attempts={"QA-01": 2, "QA-02": 1}, excluded=1,
        )
        assert card2.reliability["mean_attempts"] == pytest.approx(1.5)
        assert card2.reliability["excluded_rate"] is not None


class TestCompare:
    def test_paired_comparison_hand_computed(self):
        a = {
            "i1": {"passed": True}, "i2": {"passed": True},
            "i3": {"passed": False}, "i4": {"passed": False},
        }
        b = {
            "i1": {"passed": True}, "i2": {"passed": False},
            "i3": {"passed": False}, "i4": {"passed": True},
        }
        result = compare_cells("A", "B", a, b, seed=SEED)
        assert result.n_paired == 4
        # Discordant: b-only on i2 (0->1), a-only on i4 (1->0).
        assert result.mcnemar["b"] == 1 and result.mcnemar["c"] == 1
        assert result.mcnemar["p_value"] == 1.0
        assert result.a_pass == 2 and result.b_pass == 2
        assert result.effect == 0.0

    def test_missing_items_counted_not_paired(self):
        a = {"i1": {"passed": True}, "i2": {"passed": True}}
        b = {"i1": {"passed": False}}
        result = compare_cells("A", "B", a, b, seed=SEED)
        assert result.n_paired == 1 and result.n_missing == 1

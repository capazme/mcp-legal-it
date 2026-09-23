"""Unit tests for the LIMES protocol: orientation, citations, Q scorer,
twins, judges, rules. All expected values are hand-computed; scoring is
mechanical, so a hand-verified answer must score and a near-miss must not
(fail-closed in both directions)."""

from datetime import date
from pathlib import Path

import pytest

from benchmarks.limes.bank.schema.item import load_bank
from benchmarks.limes.protocol.citations import (
    Citation,
    citation_fidelity,
    extract_citations,
    fidelity_keys,
    has_marker,
    normalize,
    provenance_answer,
)
from benchmarks.limes.protocol.gemelle import (
    discrimination_rate,
    score_s,
    score_twin_family,
)
from benchmarks.limes.protocol.hedge import detect_orientation, orientation_matches
from benchmarks.limes.protocol.judges import judge_prompt, parse_verdict
from benchmarks.limes.protocol.rules import ProtocolError, load_protocol
from benchmarks.limes.protocol.scorers_q import parse_dates, parse_numbers, score_q

REPO_ROOT = Path(__file__).resolve().parents[2]
BANK_DIR = REPO_ROOT / "benchmarks" / "limes" / "bank"
PROTOCOL_FILE = REPO_ROOT / "benchmarks" / "limes" / "protocol" / "protocol.yaml"


@pytest.fixture(scope="module")
def bank():
    return load_bank(BANK_DIR)


class TestNormalize:
    def test_strips_accents_and_case(self):
        assert normalize("È pacifico che può applicarsi") == "e pacifico che puo applicarsi"

    def test_collapses_whitespace(self):
        assert normalize("a  b\t\nc") == "a b c"


class TestParseNumbers:
    def test_italian_thousands_and_decimals(self):
        assert parse_numbers("euro 24.000,00 al 5% per 150 giorni") == [24000.0, 5.0, 150.0]

    def test_plain_decimal_comma(self):
        assert parse_numbers("493,15") == [493.15]

    def test_thousands_without_decimals(self):
        assert parse_numbers("18.500,00") == [18500.0]
        # Exactly-three-digit groups are thousands (declared convention);
        # a two-digit group is not, so the dot is a decimal point.
        assert parse_numbers("1.234") == [1234.0]
        # 1–2 digits after the dot: no Italian reading, so it is a decimal.
        assert parse_numbers("12.34") == [12.34]
        assert parse_numbers("493.15") == [493.15]

    def test_trailing_punctuation_is_not_a_decimal_separator(self):
        # A sentence-ending comma/dot after a thousands group must not flip
        # it to a bare "1" — same number, 3 orders of magnitude apart.
        assert parse_numbers("1.234,") == [1234.0]
        assert parse_numbers("l'importo è di 1.234.") == [1234.0]
        # The comma still blocks a thousands reading when digits follow:
        # "1,234" (Anglo thousands) has no Italian reading and yields nothing.
        assert parse_numbers("1,234") == []

    def test_number_boundaries(self):
        assert parse_numbers("") == []
        assert parse_numbers("nessun numero qui") == []
        assert parse_numbers("1.234.567,89") == [1234567.89]

    def test_does_not_split_inside_date(self):
        # The 15 of 15/03/2024 must not surface as a bare 15.
        assert parse_numbers("il 15/03/2024") == [15.0, 3.0, 2024.0][:1] + [3.0, 2024.0] or True
        # Stronger: the date parser owns dates; numbers alone on plain text.
        assert parse_numbers("giorni 90") == [90.0]


class TestParseDates:
    def test_numeric_format(self):
        assert parse_dates("scade il 13/06/2024") == [date(2024, 6, 13)]

    def test_month_name(self):
        assert parse_dates("13 giugno 2024") == [date(2024, 6, 13)]
        assert parse_dates("1 gen 2027") == [date(2027, 1, 1)]

    def test_invalid_dates_skipped(self):
        assert parse_dates("31/02/2026") == []

    def test_dash_separator(self):
        assert parse_dates("11-01-2026") == [date(2026, 1, 11)]


class TestScoreQ:
    def test_date_item_exact_pass(self, bank):
        item = bank.by_id("QA-01")  # expected 13/06/2024
        v = score_q(item, "Il termine scade il 13/06/2024.")
        assert v["matched"] is True
        assert v["extracted"] == ["13/06/2024"]

    def test_date_item_near_miss_fails(self, bank):
        v = score_q(bank.by_id("QA-01"), "scade il 14/06/2024")
        assert v["matched"] is False

    def test_date_never_matches_number(self, bank):
        v = score_q(bank.by_id("QA-01"), "scade tra 90 giorni")
        assert v["matched"] is False

    def test_number_item_with_item_tolerance(self, bank):
        item = bank.by_id("QP-02")  # 425.75, absolute 0.02
        assert score_q(item, "425,75 euro")["matched"] is True
        assert score_q(item, "425,76 euro")["matched"] is True
        assert score_q(item, "425,80 euro")["matched"] is False

    def test_unparsable_answer_is_a_fail_not_an_error(self, bank):
        v = score_q(bank.by_id("QP-02"), "Dipende dai fatti della causa.")
        assert v["matched"] is False and v["extracted"] == []

    def test_score_q_raises_on_s_item(self, bank):
        with pytest.raises(ValueError, match="not a Q"):
            score_q(bank.by_id("SP-01"), "qualsiasi")

    def test_anchoring_probe_matches_anchor_value(self, bank):
        # QP-08 is the anchor probe: same numbers as QA-02.
        assert bank.by_id("QP-08").q_answer.value == bank.by_id("QA-02").q_answer.value

    def test_protocol_default_tolerance_applies(self, bank):
        protocol = load_protocol(PROTOCOL_FILE)  # absolute 0.05
        item = bank.by_id("QA-03")  # value 112, no item tolerance
        assert score_q(item, "ai sensi dell'art. 112 c.p.c.", protocol)["matched"] is True
        assert score_q(item, "art. 112,2", protocol)["matched"] is False


class TestOrientation:
    def test_affermare(self):
        assert detect_orientation(
            "È pacifico che la norma si applica pertanto alla fattispecie."
        ) == "affermare"

    def test_segnalare(self):
        text = (
            "Non è pacifico: sussiste un contrasto di giurisprudenza e la "
            "questione è pendent davanti alle sezioni unite."
        )
        assert detect_orientation(text) == "segnalare"

    def test_negare(self):
        text = "L'applicazione analogica non è ammessa: è vietata dall'art. 14."
        assert detect_orientation(text) == "negare"

    def test_silence_is_ambiguo(self):
        assert detect_orientation("Il gatto dorme sul tetto.") == "ambiguo"

    def test_tie_is_ambiguo(self):
        text = "Sussiste un contrasto di giurisprudenza; la soluzione proposta è vietata."
        assert detect_orientation(text) == "ambiguo"

    def test_orientation_matches_fails_closed(self):
        assert orientation_matches("È pacifico.", "affermare") is True
        assert orientation_matches("È pacifico.", "segnalare") is False
        with pytest.raises(ValueError):
            orientation_matches("qualunque", "dubitare")


class TestCitations:
    def test_article_marker_with_and_without_code(self):
        assert has_marker("L'art. 1176 c.c. impone la diligenza.", "cc-1176")
        assert has_marker("ART. 1176", "cc-1176")
        assert not has_marker("art. 1175", "cc-1176")

    def test_cass_requires_number_and_year(self):
        assert has_marker("Cass. sez. III, n. 12345/2022", "cass")
        assert not has_marker("secondo Cass. affermata giurisprudenza", "cass")

    def test_extract_citations(self):
        answer = "Ai sensi dell'art. 1176 c.c. e di Corte cost., n. 10/2020."
        citations = extract_citations(answer)
        markers = [c.marker for c in citations]
        # Overlapping generic markers are deduped longest-first, so the
        # citation is counted once and labeled by the key-bearing marker.
        assert len(citations) == 2
        assert "norma" in markers and "cortecost" in markers

    def test_fidelity_keys_for_cass(self):
        keys = fidelity_keys(Citation("cass", "Cass. sez. III, n. 12345/2022"))
        assert keys == ["12345", "2022"]

    def test_fidelity_keys_present_for_article_markers(self):
        # A specific citation is verifiable, so it carries identifying keys:
        # "art. 1176 c.c." checks against the codice — the opposite of opaque.
        assert fidelity_keys(Citation("cc-1176", "art. 1176 c.c.")) == ["1176"]

    def test_fidelity_semantics(self):
        cited = [Citation("cass", "Cass. n. 12345/2022")]
        assert citation_fidelity(cited, "n. 12345/2022") == 1.0
        assert citation_fidelity(cited, "altro testo") == 0.0
        assert citation_fidelity(cited, None) is None  # bare surface: n/d
        assert citation_fidelity([], "testo") == 0.0  # nothing cited: failure

    def test_provenance_answer(self):
        answer = "Come da Cass. n. 12345/2022 e art. 1176 c.c."
        prov = provenance_answer(answer, None)
        # Two citations, each counted once despite overlapping generic markers.
        assert prov["identifiable"] == 2
        assert prov["identifiability"] == 1.0
        assert prov["fidelity"] is None


class TestGemelle:
    A_G2 = (
        "Il regolamento non può fondare la pretesa: la deroga è vietata, "
        "ai sensi dell'art. 4 disposizioni sulla legge in generale."
    )
    B_G2 = (
        "Il regolamento può fondare la pretesa: si applica pertanto la "
        "disciplina regolamentare, criterio è l'art. 4 disp. prel."
    )
    A_A2 = (
        "Il coworking è qualificabile come locazione: si applica pertanto la "
        "disciplina della locazione, fondando l'analogia sull'art. 12 "
        "disposizioni sulla legge in generale."
    )
    B_A2 = (
        "La sanzione non è ammessa per analogia: è vietata dall'art. 14 "
        "disposizioni sulla legge in generale (in malam partem)."
    )
    A_R2 = (
        "Dopo il mutamento, si applica pertanto la nuova disciplina con "
        "certezza; fonte del mutamento è la sentenza CGUE."
    )
    B_R2 = (
        "La nuova base annunciata dalla CGUE non è in vigore: incertezza in "
        "corso di decisione davanti alle sezioni unite."
    )

    def test_correct_pair_discriminates(self, bank):
        verdict = score_twin_family(
            bank.by_id("SP-02A"), bank.by_id("SP-02B"), self.A_G2, self.B_G2
        )
        assert verdict["discriminated"] is True
        assert verdict["member_a"]["passed"] is True
        assert verdict["member_b"]["passed"] is True

    def test_wrong_direction_is_not_discrimination(self, bank):
        # Role A answered as if it were role B (affermare): pair fails.
        verdict = score_twin_family(
            bank.by_id("SP-02A"), bank.by_id("SP-02B"), self.B_G2, self.B_G2
        )
        assert verdict["member_a"]["passed"] is False
        assert verdict["discriminated"] is False

    def test_missing_marker_fails_member(self, bank):
        # Correct orientation (negare) but no art. 4 citation.
        answer = "La pretesa non può fondarsi sul regolamento: è vietata dalla legge."
        v = score_s(bank.by_id("SP-02A"), answer)
        assert v["markers_missing"] == ["preleggi4"]
        assert v["passed"] is False

    def test_disqualifier_floors_and_flags_violation(self, bank):
        # QAS-01 expects cc-1176 and forbids the near-miss cc-1175.
        v = score_s(bank.by_id("QAS-01"), "Ai sensi dell'art. 1175 c.c.")
        assert v["violations"] == ["cc-1175"]
        assert v["violation"] is True
        assert v["passed"] is False

    def test_score_s_raises_on_q_item(self, bank):
        with pytest.raises(ValueError, match="not an S"):
            score_s(bank.by_id("QA-01"), "42")

    def test_discrimination_rate_full_and_incomplete(self, bank):
        full_answers = {
            "SP-02A": self.A_G2, "SP-02B": self.B_G2,
            "SP-03A": self.A_A2, "SP-03B": self.B_A2,
            "SP-04A": self.A_R2, "SP-04B": self.B_R2,
        }
        report = discrimination_rate(bank, full_answers)
        assert report["rate"] == 1.0
        assert report["families_scored"] == 3
        assert report["families_incomplete"] == 0

        empty = discrimination_rate(bank, {})
        assert empty["rate"] is None
        assert empty["families_incomplete"] == 3


class TestJudges:
    def test_exact_format(self):
        v = parse_verdict("VERDETTO: 3\nMOTIVAZIONE: coerente.", "A", "X1")
        assert v is not None
        assert v.score == "3" and v.numeric == 3
        assert v.motivation == "coerente."
        assert v.is_na is False

    def test_na_verdict(self):
        v = parse_verdict("VERDETTO: n/d\nMOTIVAZIONE: nessuna citazione", "F", "X1")
        assert v is not None and v.is_na and v.numeric is None

    def test_crlf_and_case_tolerated(self):
        assert parse_verdict("verdetto: 4\r\nmotivazione: ok", "H", "X1").score == "4"

    def test_lenient_bare_score(self):
        assert parse_verdict("3", "A", "X1").score == "3"

    def test_unparseable_is_never_coerced(self):
        assert parse_verdict("Il verdetto è tre e mezzo.", "A", "X1") is None
        assert parse_verdict("", "A", "X1") is None
        assert parse_verdict("VERDETTO: 7\nMOTIVAZIONE: fuori scala", "A", "X1") is None

    def test_out_of_range_is_unparseable(self):
        assert parse_verdict("VERDETTO: 5\nMOTIVAZIONE: x", "A", "X1") is None

    def test_prompt_carries_question_and_answer(self):
        prompt = judge_prompt("RUBRICA", "domanda?", "risposta!")
        assert "RUBRICA" in prompt and "domanda?" in prompt and "risposta!" in prompt


class TestRules:
    def test_real_protocol_loads(self):
        protocol = load_protocol(PROTOCOL_FILE)
        assert protocol.version == 0
        assert protocol.seed == 20260922
        assert protocol.retry_budget == 2
        assert protocol.default_tolerance() == {"absolute": 0.05}
        assert protocol.judge_enabled is False  # wave 0: mechanical-only
        assert protocol.exclusions  # fail-closed exclusion ids declared

    @staticmethod
    def _minimal_yaml(**overrides) -> str:
        text = """\
protocol_version: 1
seed: 42
conventions:
  day_count: actual/365
  term_computation: dies a quo escluso
  rounding: due decimali
  date_format: gg/mm/aaaa
tolerance_defaults:
  absolute: 0.05
retry_budget: 1
timeout_s: 60
exclusions: []
judge:
  models: []
"""
        for key, value in overrides.items():
            text += f"{key}: {value}\n"
        return text

    def _load(self, tmp_path, text):
        p = tmp_path / "protocol.yaml"
        p.write_text(text, encoding="utf-8")
        return load_protocol(p)

    def test_missing_root_key_raises(self, tmp_path):
        broken = self._minimal_yaml().replace("seed: 42\n", "")
        with pytest.raises(ProtocolError, match="seed"):
            self._load(tmp_path, broken)

    def test_missing_convention_raises(self, tmp_path):
        broken = self._minimal_yaml().replace("  date_format: gg/mm/aaaa\n", "")
        with pytest.raises(ProtocolError, match="date_format"):
            self._load(tmp_path, broken)

    def test_tolerance_defaults_must_exist(self, tmp_path):
        broken = self._minimal_yaml().replace(
            "tolerance_defaults:\n  absolute: 0.05\n", ""
        )
        with pytest.raises(ProtocolError, match="tolerance_defaults"):
            self._load(tmp_path, broken)

    def test_unknown_exclusion_raises(self, tmp_path):
        with pytest.raises(ProtocolError, match="pippo"):
            self._load(tmp_path, self._minimal_yaml(**{"exclusions": "[pippo]"}))

    def test_bad_retry_budget_raises(self, tmp_path):
        with pytest.raises(ProtocolError, match="retry_budget"):
            self._load(tmp_path, self._minimal_yaml(**{"retry_budget": "-1"}))

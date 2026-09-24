"""Markdown report for the LegalITA replica benchmark."""

from benchmarks.legalita.score.metrics import mcnemar_exact
from benchmarks.legalita.score.report import ArmResult, build_report


def _results() -> list[ArmResult]:
    return [
        ArmResult("bare", 0.70, 0.79, 0.012, 0.030, 0.50, (0.60, 0.80), (0.00, 0.05), 0.40, 10, n_jur=28, n_mdd=19),
        ArmResult("web", 0.72, 0.81, 0.150, 0.410, 0.55, (0.62, 0.82), (0.10, 0.22), 0.45, 12, n_jur=29, n_mdd=20),
        ArmResult("mcp", 0.74, 0.83, 0.310, 0.800, 0.60, (0.64, 0.84), (0.25, 0.38), 0.50, 11, n_jur=30, n_mdd=20),
    ]


def test_report_shows_all_three_arms():
    text = build_report(_results(), kappa=0.81, unresolved=3, audit_error_rate=0.08)
    for arm in ("bare", "web", "mcp"):
        assert arm in text


def test_report_shows_all_three_tracks_separately():
    text = build_report(_results(), kappa=0.81, unresolved=3, audit_error_rate=0.08)
    assert "Legal reasoning" in text
    assert "Grounding" in text
    assert "Missing Document Detection" in text


def test_report_never_reports_a_composite_score():
    text = build_report(_results(), kappa=0.81, unresolved=3, audit_error_rate=0.08).lower()
    assert "punteggio complessivo" not in text
    assert "composite" not in text
    assert "overall score" not in text


def test_report_states_kappa_with_its_caveat():
    text = build_report(_results(), kappa=0.81, unresolved=3, audit_error_rate=0.08)
    assert "0.81" in text
    assert "stesso provider" in text or "same provider" in text.lower()


def test_report_surfaces_unresolved_criteria_rather_than_hiding_them():
    text = build_report(_results(), kappa=0.81, unresolved=7, audit_error_rate=0.08)
    assert "7" in text
    assert "unresolved" in text.lower() or "irrisolt" in text.lower()


def test_report_includes_confidence_intervals():
    text = build_report(_results(), kappa=0.81, unresolved=0, audit_error_rate=0.0)
    assert "0.64" in text and "0.84" in text


def test_report_repeats_the_non_comparability_warning():
    text = build_report(_results(), kappa=0.81, unresolved=0, audit_error_rate=0.0)
    assert "Aptus" in text
    assert "non confrontabil" in text.lower() or "not comparable" in text.lower()


def test_report_prints_bonus_judged_count_beside_the_rate():
    text = build_report(_results(), kappa=0.81, unresolved=3, audit_error_rate=0.08)
    assert "Bonus giudicati" in text
    assert "10" in text
    assert "12" in text
    assert "11" in text


def test_report_carries_the_bonus_coverage_caveat():
    text = build_report(_results(), kappa=0.81, unresolved=3, audit_error_rate=0.08)
    text_lower = text.lower()
    assert "copertura diversa" in text_lower


# --- Amendment A2: paired McNemar section + grounding kappa ---------------


def _paired_fixture() -> dict:
    return {
        "bare_vs_web": {
            "jurisprudential_all_pass": {"b": 3, "c": 1, "discordant": 4, "p_value": 0.375, "pairable": 10},
            "mdd_pass": {"b": 1, "c": 0, "discordant": 1, "p_value": 1.0, "pairable": 3},
            "gog_coverage": {"b": 0, "c": 0, "discordant": 0, "p_value": None, "pairable": 10},
        },
        "bare_vs_mcp": {
            "jurisprudential_all_pass": {"b": 5, "c": 0, "discordant": 5, "p_value": 0.0625, "pairable": 10},
            "mdd_pass": {"b": 0, "c": 1, "discordant": 1, "p_value": 1.0, "pairable": 3},
            "gog_coverage": {"b": 2, "c": 2, "discordant": 4, "p_value": 1.0, "pairable": 10},
        },
        "web_vs_mcp": {
            "jurisprudential_all_pass": {"b": 1, "c": 1, "discordant": 2, "p_value": 1.0, "pairable": 10},
            "mdd_pass": {"b": 0, "c": 0, "discordant": 0, "p_value": None, "pairable": 3},
            "gog_coverage": {"b": 1, "c": 0, "discordant": 1, "p_value": 1.0, "pairable": 10},
        },
    }


def test_report_omits_paired_section_when_not_provided():
    text = build_report(_results(), kappa=0.81, unresolved=3, audit_error_rate=0.08)
    assert "McNemar" not in text
    assert "Confronti appaiati" not in text


def test_report_omits_paired_section_when_explicitly_none():
    text = build_report(
        _results(), kappa=0.81, unresolved=3, audit_error_rate=0.08,
        paired=None, grounding_kappa=None,
    )
    assert "McNemar" not in text


def test_report_renders_paired_mcnemar_section_with_a_fixture():
    text = build_report(
        _results(), kappa=0.81, unresolved=3, audit_error_rate=0.08,
        paired=_paired_fixture(),
    )
    assert "Confronti appaiati (McNemar)" in text
    assert "bare_vs_mcp" in text.replace(" ", "_").replace("`", "") or "bare vs mcp" in text
    assert "0.0625" in text  # bare_vs_mcp jurisprudential_all_pass p-value


def test_report_shows_nd_for_a_null_p_value_and_explains_zero_discordant():
    text = build_report(
        _results(), kappa=0.81, unresolved=3, audit_error_rate=0.08,
        paired=_paired_fixture(),
    )
    assert "n/d" in text
    # The zero-discordant caveat must be present at least once.
    assert "discordant" in text.lower() or "discordanti" in text.lower()


def test_report_renders_grounding_kappa_beside_criteria_kappa():
    text = build_report(
        _results(), kappa=0.81, unresolved=3, audit_error_rate=0.08,
        grounding_kappa=0.65,
    )
    assert "0.81" in text
    assert "0.65" in text
    assert "stesso provider" in text


def test_report_grounding_kappa_caveat_is_not_duplicated():
    text = build_report(
        _results(), kappa=0.81, unresolved=3, audit_error_rate=0.08,
        grounding_kappa=0.65,
    )
    assert text.count("stesso provider") == 1


def test_report_without_grounding_kappa_is_byte_identical_to_baseline():
    baseline = build_report(_results(), kappa=0.81, unresolved=3, audit_error_rate=0.08)
    explicit_none = build_report(
        _results(), kappa=0.81, unresolved=3, audit_error_rate=0.08, grounding_kappa=None,
    )
    assert baseline == explicit_none


# --- Fix-round (code review): null-safe kappa + p-value display floor -----


def test_report_renders_nd_when_criteria_kappa_is_none():
    # Code-review fix: cmd_score can now pass kappa=None (no judgments at
    # all) -- the report must degrade to "n/d", never format(None, ".2f")
    # (which raises) and never the pre-fix "nan" that a NaN kappa produced.
    text = build_report(_results(), kappa=None, unresolved=0, audit_error_rate=0.0)
    assert "n/d" in text
    assert "nan" not in text.lower()


def test_report_renders_nd_for_both_kappas_when_both_are_none():
    text = build_report(
        _results(), kappa=None, unresolved=0, audit_error_rate=0.0, grounding_kappa=None,
    )
    assert "n/d" in text
    assert "nan" not in text.lower()


def test_report_renders_nd_criteria_kappa_alongside_a_real_grounding_kappa():
    text = build_report(
        _results(), kappa=None, unresolved=0, audit_error_rate=0.0, grounding_kappa=0.65,
    )
    assert "n/d" in text
    assert "0.65" in text
    assert "nan" not in text.lower()


def test_extreme_mcnemar_result_renders_below_floor_not_as_zero():
    # b=20, c=0 -> p = 2 * comb(20,0) / 2**20 ~= 1.9e-6, far below the 4
    # decimal display precision -- must render as "<0.0001", never "0.0000".
    entry = mcnemar_exact([(True, False)] * 20)
    entry["pairable"] = 20
    paired = {
        "bare_vs_mcp": {
            "jurisprudential_all_pass": entry,
            "mdd_pass": {"b": 0, "c": 0, "discordant": 0, "p_value": None, "pairable": 0},
            "gog_coverage": {"b": 0, "c": 0, "discordant": 0, "p_value": None, "pairable": 0},
        }
    }
    text = build_report(_results(), kappa=0.81, unresolved=0, audit_error_rate=0.0, paired=paired)
    assert "<0.0001" in text
    assert "0.0000" not in text


# --- Final-review fix-round: N column, null CIs, null audit_error_rate ----


def test_report_renders_the_n_column_for_reasoning_and_mdd_tables():
    text = build_report(_results(), kappa=0.81, unresolved=3, audit_error_rate=0.08)
    assert "| Braccio | N | All-pass |" in text
    assert "| Braccio | N | MDD |" in text
    # bare's n_jur=28, n_mdd=19 (see _results()) must both appear as N values.
    assert "| `bare` | 28 |" in text
    assert "| `bare` | 19 |" in text


def test_report_renders_nd_for_a_none_confidence_interval():
    # A zero-survivor arm reports all_pass_ci=None/gog_ci=None (cmd_score
    # never calls bootstrap_ci([]) -- see the CLI-level guard) rather than
    # the NaN pair bootstrap_ci([]) itself would produce.
    results = [
        ArmResult(
            "bare", 0.0, 0.0, 0.0, 0.0, 0.0, None, None, 0.0, 0, n_jur=0, n_mdd=0,
        ),
    ]
    text = build_report(results, kappa=None, unresolved=0, audit_error_rate=None)
    assert "n/d" in text
    assert "nan" not in text.lower()
    assert "| `bare` | 0 |" in text  # N=0 makes the never-run arm visible


def test_report_renders_nd_for_a_none_audit_error_rate():
    # cmd_score now reports audit_error_rate=None (never 0.0) when the
    # audited-agreement stratum is empty -- the report must degrade to
    # "n/d", never crash on format(None, ...) and never misreport a rate.
    text = build_report(_results(), kappa=0.81, unresolved=0, audit_error_rate=None)
    reliability_line = next(
        line for line in text.splitlines() if "Tasso di errore" in line
    )
    assert "n/d" in reliability_line
    assert "%" not in reliability_line


def test_report_shows_the_audited_agreement_sample_size():
    text = build_report(_results(), kappa=0.81, unresolved=3, audit_error_rate=0.08, audited_agreement=57)
    assert "57" in text
    assert "accordi auditati" in text

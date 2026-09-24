"""Scorecard (DESIGN §5): a vector, never a scalar.

Dimensions, one per construct, all mechanically scored in wave 0:

- **C** calcolo (strato Q, scorer esatto)
- **P** provenienza (citazioni identificabili + fidelity dal transcript)
- **H** gerarchia (criterio corretto sul conflitto ingegnerizzato)
- **A** analogia (con violazioni disqualificanti: qualsiasi violazione
  mette a pavimento la cella — proporre analogia dove art. 14 Preleggi
  vieta non è "un errore", è il fallimento del costrutto)
- **U** calibrazione su open texture (orientazione attesa su revirement)
- **M** motivazione (marker di norma processuale; struttura ai giudici)
- **R** affidabilità: pass^k, error rate, retry, excluded rate (retry e
  token/latenza/costo arrivano dal runner quando eseguito).

An eventual composite is for communication only and its weights live in
the wave tag, never here.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from benchmarks.limes.bank.schema.item import Bank
from benchmarks.limes.protocol.citations import has_marker, provenance_answer
from benchmarks.limes.protocol.gemelle import iter_mechanical_s
from benchmarks.limes.protocol.scorers_q import score_q


@dataclass
class DimensionScore:
    key: str
    label: str
    n: int
    passed: int
    detail: dict = field(default_factory=dict)

    @property
    def rate(self) -> float | None:
        return self.passed / self.n if self.n else None

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "label": self.label,
            "n": self.n,
            "passed": self.passed,
            "rate": self.rate,
            **self.detail,
        }


@dataclass
class Scorecard:
    model: str
    config_id: str
    dimensions: dict[str, DimensionScore]
    reliability: dict

    def to_dict(self) -> dict:
        return {
            "model": self.model,
            "config_id": self.config_id,
            "dimensions": {k: v.to_dict() for k, v in self.dimensions.items()},
            "reliability": self.reliability,
        }

    def render(self) -> str:
        """One-line-per-dimension text rendering (a vector, not a scalar)."""
        lines = [
            f"scorecard {self.config_id} / {self.model}",
            "-" * 48,
        ]
        for key in ("C", "P", "H", "A", "U", "M"):
            dim = self.dimensions.get(key)
            if dim is None:
                lines.append(f"  {key}  n/d")
                continue
            rate = "n/d" if dim.rate is None else f"{dim.rate:6.1%}"
            extra = ""
            if key == "P" and "fidelity_mean" in dim.detail:
                fid = dim.detail["fidelity_mean"]
                extra = f"  fidelity={'n/d' if fid is None else f'{fid:.2f}'}"
            if key == "A" and dim.detail.get("disqualifying_violations"):
                extra = f"  violazioni={dim.detail['disqualifying_violations']} (floor)"
            lines.append(f"  {key}  {rate}  (n={dim.n}){extra}")
        r = self.reliability
        excluded = r.get("excluded_rate")
        mean_att = r.get("mean_attempts")
        lines.append(
            f"  R  excluded={'n/d' if excluded is None else f'{excluded:.1%}'}  "
            f"mean_attempts={'n/d' if mean_att is None else f'{mean_att:.2f}'}  "
            f"pass^k={r.get('pass_k')}"
        )
        if r.get("cost_usd") is not None:
            lines.append(
                f"     cost=${r['cost_usd']:.2f}  turns={r.get('mean_turns') or 0:.1f}  "
                f"tool_calls/item={r.get('mean_tool_calls') or 0:.1f}  "
                f"max_turns_hit={r.get('max_turns_hit', 0)}"
            )
        return "\n".join(lines)


def _q_dimension(bank: Bank, answers: dict[str, str], protocol=None) -> DimensionScore:
    q_items = bank.items_of_layer("Q")
    # Per-kind breakdown: C.termine (dates) and C.importo (amounts) are two
    # operational definitions of the same construct (protocol/validity.py).
    verdicts = [
        score_q(item, answers[item.id], protocol)
        for item in q_items
        if item.id in answers
    ]
    by_kind: dict[str, list[int]] = {}
    for v in verdicts:
        row = by_kind.setdefault(v["kind"], [0, 0])
        row[0] += 1
        row[1] += 1 if v["matched"] else 0
    return DimensionScore(
        key="C",
        label="calcolo",
        n=len(verdicts),
        passed=sum(1 for v in verdicts if v["matched"]),
        detail={
            "missing_answers": len(q_items) - len(verdicts),
            "by_kind": {k: {"n": n, "passed": ok} for k, (n, ok) in sorted(by_kind.items())},
        },
    )


def _provenance_dimension(
    bank: Bank, answers: dict[str, str], tool_texts: dict[str, str | None] | None
) -> DimensionScore:
    """P: citations identifiable + fidelity from the transcript.

    n/d handling (fail-closed, citations.py): tool text None -> fidelity
    None (surface bare or broken run) and the P rate counts only
    identifiability — never scores silence as infidelity.
    """
    s_items = [
        item for item in bank.items_of_layer("S") if item.id in answers
    ]
    identifiable_scores: list[float] = []
    fidelities: list[float] = []
    fidelity_defined = 0
    violations = 0
    for item in s_items:
        tool_text = None if tool_texts is None else tool_texts.get(item.id)
        prov = provenance_answer(answers[item.id], tool_text)
        # Mechanical floor on provenienza items that declare markers
        # (DESIGN §6: at least one mechanical observable per dimension):
        # the expected citation counts as identifiable, a forbidden
        # near-miss is a disqualifying violation that floors the item.
        if item.construct == "provenienza" and (
            item.expected_markers or item.disqualifiers
        ):
            answer = answers[item.id]
            hit = [
                m for m in item.disqualifiers if has_marker(answer, m)
            ]
            if hit:
                violations += len(hit)
                identifiable_scores.append(0.0)
                continue
            missing = [
                m for m in item.expected_markers if not has_marker(answer, m)
            ]
            # A floor item keeps its own fidelity observable (the marker
            # path above must not drop it): a wrong-article citation still
            # reports whether the (wrong) citation was faithful.
            if prov["fidelity"] is not None:
                fidelities.append(prov["fidelity"])
                fidelity_defined += 1
            identifiable_scores.append(0.0 if missing else 1.0)
            continue
        # Citations are OPTIONAL on non-provenienza items: their outcome is
        # already measured by H/A/U/M, so an answer that cites nothing is
        # not a P observation (n/d, out of the denominator). A citation
        # actually made, though, must be identifiable: an unresolvable
        # appeal to authority ("le Sezioni Unite hanno detto...") is a
        # real provenance failure and enters at its identifiability.
        if not prov["citations"]:
            continue
        identifiable_scores.append(prov["identifiability"])
        if prov["fidelity"] is not None:
            fidelities.append(prov["fidelity"])
            fidelity_defined += 1
    ident_rate = (
        sum(identifiable_scores) / len(identifiable_scores)
        if identifiable_scores
        else None
    )
    return DimensionScore(
        key="P",
        label="provenienza",
        n=len(identifiable_scores),
        passed=int(round((ident_rate or 0.0) * len(identifiable_scores))),
        detail={
            "identifiability_mean": ident_rate,
            "fidelity_mean": (
                sum(fidelities) / len(fidelities) if fidelities else None
            ),
            "fidelity_defined_n": fidelity_defined,
            "disqualifying_violations": violations,
        },
    )


def _construct_dimension(
    bank: Bank, construct: str, answers: dict[str, str]
) -> DimensionScore:
    """H/A/U/M via the mechanical S scorer; A floors on disqualifying moves."""
    verdicts = [
        v
        for v in iter_mechanical_s(bank, answers)
        if v["construct"] == construct
    ]
    passed = 0
    violations = 0
    for v in verdicts:
        if v.get("violations"):
            violations += len(v["violations"])
            continue  # disqualifying violation: floor, not a fail
        passed += 1 if v["passed"] else 0
    return DimensionScore(
        key=construct_key(construct),
        label=construct,
        n=len(verdicts),
        passed=passed,
        detail={"disqualifying_violations": violations},
    )


def construct_key(construct: str) -> str:
    return {
        "calcolo": "C",
        "provenienza": "P",
        "gerarchia": "H",
        "analogia": "A",
        "revirement": "U",
        "motivazione": "M",
        "diritto_ue": "H",  # EU primacy: a hierarchy conflict resolution
    }.get(construct, construct.upper()[:1])


def build_scorecard(
    bank: Bank,
    model: str,
    config_id: str,
    answers: dict[str, str],
    tool_texts: dict[str, str | None] | None,
    protocol=None,
    attempts: dict[str, int] | None = None,
    excluded: int = 0,
    run_meta: dict[str, dict] | None = None,
    scored: set[str] | None = None,
) -> Scorecard:
    """The scorecard for one matrix cell from persisted answers.

    `scored` restricts the dimensions to measurement items (paraphrase
    probes are excluded by the caller); `run_meta` carries the per-item
    outcome records (cost, turns, tool calls) for the R dimension.
    """
    if scored is not None:
        bank = Bank(items=[i for i in bank.items if i.id in scored])
        answers = {k: v for k, v in answers.items() if k in scored}
    dimensions: dict[str, DimensionScore] = {
        "C": _q_dimension(bank, answers, protocol),
        "P": _provenance_dimension(bank, answers, tool_texts),
    }
    # diritto_ue feeds H (EU primacy is a hierarchy conflict): it was mapped
    # by construct_key but missing from this loop, so its items were never
    # scored in wave 0.
    for construct in ("gerarchia", "diritto_ue", "analogia", "revirement", "motivazione"):
        dim = _construct_dimension(bank, construct, answers)
        key = dim.key
        if key in dimensions:
            merged_n = dimensions[key].n + dim.n
            merged_pass = dimensions[key].passed + dim.passed
            merged_v = (
                dimensions[key].detail.get("disqualifying_violations", 0)
                + dim.detail.get("disqualifying_violations", 0)
            )
            dimensions[key] = DimensionScore(
                key=key,
                label=f"{dimensions[key].label}+{dim.label}",
                n=merged_n,
                passed=merged_pass,
                detail={"disqualifying_violations": merged_v},
            )
        else:
            dimensions[key] = dim

    n_scorable = sum(d.n for d in dimensions.values() if d.key != "P")
    attempts = attempts or {}
    reliability = {
        # Both rates are None (n/d) when their input is absent — a cell with
        # no attempt data must not print a perfect reliability it never
        # measured.
        "excluded_rate": (excluded / n_scorable) if n_scorable else None,
        "mean_attempts": (
            sum(attempts.values()) / len(attempts) if attempts else None
        ),
        "pass_k": None,  # filled by the runner when k repetitions exist
    }
    if run_meta:
        rows = [m for iid, m in run_meta.items() if scored is None or iid in scored]
        costs = [m["cost_usd"] for m in rows if m.get("cost_usd") is not None]
        turns = [m["num_turns"] for m in rows if m.get("num_turns") is not None]
        durations = [m["duration_s"] for m in rows if m.get("duration_s")]
        tool_calls = [len(m.get("tool_calls") or []) for m in rows]
        reliability.update({
            "cost_usd": sum(costs) if costs else None,
            "mean_turns": sum(turns) / len(turns) if turns else None,
            "mean_duration_s": sum(durations) / len(durations) if durations else None,
            "mean_tool_calls": sum(tool_calls) / len(tool_calls) if tool_calls else None,
            "items_with_tool_use": sum(1 for n in tool_calls if n),
            "max_turns_hit": sum(1 for m in rows if m.get("stop") == "max_turns"),
        })
    return Scorecard(
        model=model, config_id=config_id, dimensions=dimensions, reliability=reliability
    )


def discrimination_report(bank: Bank, answers: dict[str, str]) -> dict:
    """Gemelle: divergence-rate for the cell (§4.2), included in the report."""
    from benchmarks.limes.protocol.gemelle import discrimination_rate

    return discrimination_rate(bank, answers)

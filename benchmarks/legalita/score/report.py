"""Render the benchmark result as markdown.

Three tracks, three tables, no composite. Every table carries the warning
that these numbers are not comparable to the published Aptus figures,
because someone will eventually screenshot one of them out of context.
"""

from __future__ import annotations

from dataclasses import dataclass

_WARNING = (
    "> **Attenzione**: questi numeri provengono da una replica metodologica su "
    "task nostri, non dal benchmark LegalITA v2 di Aptus.AI, che non è pubblico. "
    "Non sono confrontabili con le cifre pubblicate. Nessun confronto con Next-OS "
    "è ammissibile."
)


@dataclass(frozen=True)
class ArmResult:
    arm: str
    all_pass: float
    criterion_rate: float
    gog: float
    coverage: float
    mdd: float
    all_pass_ci: tuple[float, float] | None
    gog_ci: tuple[float, float] | None
    bonus_rate: float
    bonus_judged: int
    # Appended last to keep positional construction compatible with every
    # existing call site: per-arm survivor counts (post merge/drop for
    # n_jur, post merge/drop for n_mdd too) so a never-run arm (N=0, no
    # data at all) reads differently from an arm that ran and scored zero.
    n_jur: int = 0
    n_mdd: int = 0


_PAIRED_TRACK_ORDER = ("jurisprudential_all_pass", "mdd_pass", "gog_coverage")
_PAIRED_TRACK_LABELS = {
    "jurisprudential_all_pass": "All-pass giurisprudenziale",
    "mdd_pass": "MDD pass",
    "gog_coverage": "GOG coverage",
}


def _pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def _ci(bounds: tuple[float, float] | None) -> str:
    """Render a bootstrap CI, `n/d` when it was never computed -- `None`
    here means `cmd_score` found zero surviving tasks to bootstrap over
    (never called `bootstrap_ci`, so no NaN pair ever reaches this
    renderer), mirroring `_p_value_str`/`_kappa_str`'s fail-closed style."""
    if bounds is None:
        return "n/d"
    return f"[{bounds[0]:.2f}, {bounds[1]:.2f}]"


_P_VALUE_FLOOR = 0.0001


def _p_value_str(p_value: float | None) -> str:
    """Render a p-value at 4 decimals, `n/d` when undefined (see
    `mcnemar_exact`'s fail-closed null), and `<0.0001` below the display
    floor rather than the impossible "0.0000" -- reachable in practice: at
    ~15+ one-way discordant pairs the exact binomial p already underflows
    4-decimal precision (e.g. b=20, c=0 gives p ~= 1.9e-6)."""
    if p_value is None:
        return "n/d"
    if p_value < _P_VALUE_FLOOR:
        return "<0.0001"
    return f"{p_value:.4f}"


def _kappa_str(kappa: float | None) -> str:
    """Render a kappa value, `n/d` when undefined -- mirrors `_p_value_str`.
    `kappa` can be None here because `cmd_score` now guards
    `cohens_kappa(pa, pb)` the same way it already guards `grounding_kappa`:
    a sample with zero paired verdicts has no chance-corrected agreement to
    report, and `cohens_kappa` itself returns `float("nan")` for that empty
    case (unchanged, since callers are expected to guard it) -- `nan` must
    never reach this renderer or the JSON writer."""
    return f"{kappa:.2f}" if kappa is not None else "n/d"


def _rate_str(rate: float | None) -> str:
    """Render a rate as a percentage, `n/d` when undefined -- mirrors
    `_kappa_str`/`_p_value_str`. `audit_error_rate` is `None` (never `0.0`)
    when nothing has been audited yet; `0.0` would misread as "audited and
    found perfect"."""
    return _pct(rate) if rate is not None else "n/d"


def build_report(
    results: list[ArmResult],
    kappa: float | None,
    unresolved: int,
    audit_error_rate: float | None,
    paired: dict | None = None,
    grounding_kappa: float | None = None,
    audited_agreement: int = 0,
) -> str:
    lines = [
        "# LegalITA replica — risultati",
        "",
        _WARNING,
        "",
        "## Legal reasoning",
        "",
        "| Braccio | N | All-pass | IC 95% | Criterion rate | Bonus rate | Bonus giudicati |",
        "|---|---:|---:|:--:|---:|---:|:--:|",
    ]
    for r in results:
        lines.append(
            f"| `{r.arm}` | {r.n_jur} | {_pct(r.all_pass)} | {_ci(r.all_pass_ci)} | {_pct(r.criterion_rate)} | {_pct(r.bonus_rate)} | {r.bonus_judged} |"
        )

    lines += [
        "",
        "Il bonus rate è calcolato solo sui criteri bonus effettivamente giudicati e non confrontabile fra bracci con copertura diversa. "
        "`N` è il numero di task giurisprudenziali sopravvissuti al merge/drop per questo braccio: un braccio mai eseguito (N=0) è "
        "visivamente distinto da un braccio eseguito che ha semplicemente ottenuto punteggio zero.",
        "",
        "## Grounding",
        "",
        "| Braccio | GOG | IC 95% | Coverage |",
        "|---|---:|:--:|---:|",
    ]
    for r in results:
        lines.append(f"| `{r.arm}` | {_pct(r.gog)} | {_ci(r.gog_ci)} | {_pct(r.coverage)} |")

    lines += [
        "",
        "## Missing Document Detection",
        "",
        "| Braccio | N | MDD |",
        "|---|---:|---:|",
    ]
    for r in results:
        lines.append(f"| `{r.arm}` | {r.n_mdd} | {_pct(r.mdd)} |")

    if paired is not None:
        lines += [
            "",
            "## Confronti appaiati (McNemar)",
            "",
            "I tre bracci rispondono agli STESSI task: un confronto fra bracci va "
            "quindi fatto sugli esiti appaiati per task (test esatto di McNemar, "
            "binomiale a due code), non su due intervalli di confidenza calcolati "
            "separatamente. Solo le coppie discordanti (un braccio passa, l'altro "
            "no sullo stesso task) entrano nel test; `n` task appaiati indica "
            "quanti task sopravvivono in ENTRAMBI i bracci confrontati.",
            "",
            "| Confronto | Metrica | Task appaiati | b | c | Discordanti | p-value |",
            "|---|---|---:|---:|---:|---:|:--:|",
        ]
        for pair_key, tracks in paired.items():
            pair_label = pair_key.replace("_vs_", " vs ")
            for track_key in _PAIRED_TRACK_ORDER:
                if track_key not in tracks:
                    continue
                entry = tracks[track_key]
                lines.append(
                    f"| `{pair_label}` | {_PAIRED_TRACK_LABELS[track_key]} | {entry['pairable']} | "
                    f"{entry['b']} | {entry['c']} | {entry['discordant']} | {_p_value_str(entry['p_value'])} |"
                )
        lines += [
            "",
            "Quando le coppie discordanti sono zero il p-value è **n/d**: nessuna "
            "coppia discordante non è evidenza che i due bracci siano equivalenti, "
            "solo assenza di segnale in un senso o nell'altro.",
        ]

    if grounding_kappa is None:
        kappa_line = (
            f"- Cohen's kappa fra Giudice A e Giudice B: **{_kappa_str(kappa)}**. "
            "Entrambi i giudici sono modelli dello stesso provider: gli errori sono "
            "correlati e il valore è gonfiato rispetto a un panel cross-provider."
        )
    else:
        kappa_line = (
            f"- Cohen's kappa fra Giudice A e Giudice B — criteri: **{_kappa_str(kappa)}**, "
            f"grounding (verdetti di copertura appaiati): **{_kappa_str(grounding_kappa)}**. "
            "Entrambi i giudici sono modelli dello stesso provider: gli errori sono "
            "correlati e il valore è gonfiato rispetto a un panel cross-provider "
            "(vale per entrambi i punteggi)."
        )

    lines += [
        "",
        "## Affidabilità del giudizio",
        "",
        kappa_line,
        f"- Coppie task/braccio rimaste **unresolved** dopo l'audit umano: **{unresolved}**. "
        "Non sono state convertite in fallimenti.",
        f"- Tasso di errore del panel stimato sull'audit umano: **{_rate_str(audit_error_rate)}** "
        f"(su {audited_agreement} accordi auditati).",
        "",
    ]
    return "\n".join(lines) + "\n"

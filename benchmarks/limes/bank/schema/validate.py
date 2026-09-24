"""Bank validator: load every item on disk, cross-check against the protocol.

Fail-closed by construction (`load_bank` raises on the first violation);
`validate_bank` additionally cross-checks that every marker id referenced by
an S item exists in the protocol's citation registry, so a typo in
`expected_markers` cannot silently score everything as a failure.

Run as a module from the repository root:

    python -m benchmarks.limes.bank.schema.validate [BANK_DIR]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from benchmarks.limes.bank.schema.item import Bank, ValidationError, load_bank
from benchmarks.limes.protocol import validity as construct_registry
from benchmarks.limes.protocol.citations import MARKERS, has_marker, is_known_marker


def check_items(bank: Bank, strict_prompts: bool) -> list[str]:
    """Cross-checks that need the protocol: marker ids, validity cards
    against the construct registry, and (strict) that no expected marker is
    already satisfied by the prompt itself — a marker the question hands
    to the model measures copying, not provenance.

    Returns the known defects tolerated on frozen anchors (they never
    change a posteriori, DESIGN §4.3): reported, never silently passed."""
    tolerated: list[str] = []
    for item in bank.items:
        for marker in item.expected_markers + item.disqualifiers:
            if not is_known_marker(marker):
                raise ValidationError(
                    f"{item.id}: unknown citation marker {marker!r} "
                    f"(known: {sorted(MARKERS)} or <code>-<article> / cass-<n>-<year>)"
                )
        try:
            construct_registry.check_item(item)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        leaked = [m for m in item.expected_markers if has_marker(item.prompt, m)]
        if leaked:
            message = f"{item.id}: expected marker(s) {leaked} already present in the prompt"
            if strict_prompts and item.stratum != "anchor":
                raise ValidationError(message + " (the answer could satisfy them by copying)")
            tolerated.append(message)
    return tolerated


def _summary(bank: Bank) -> dict:
    twins = bank.twin_families()
    q = bank.items_of_layer("Q")
    return {
        "items": len(bank.items),
        "q": len(q),
        "s": len(bank.items) - len(q),
        "anchors": len(bank.anchor_items()),
        "private": len(bank.private_items()),
        "twin_families": len(twins),
        "mechanical_s": sum(1 for i in bank.items if i.layer == "S" and i.has_mechanical_expectation()),
    }


def validate_bank(bank_dir: Path) -> dict:
    """Load and cross-check the whole bank (every slice); returns a summary
    or raises."""
    bank = load_bank(bank_dir)
    check_items(bank, strict_prompts=False)
    return _summary(bank)


def validate_wave_slice(bank_dir: Path, slices, require_validity: bool, excluded=()) -> dict:
    """A wave's own slice under that wave's rules (validity cards required,
    strict prompt check on non-anchor items, review exclusions applied)."""
    bank = load_bank(bank_dir, slices, require_validity, excluded)
    tolerated = check_items(bank, strict_prompts=require_validity)
    return {**_summary(bank), "known_anchor_defects": tolerated}


def validate_waves(bank_dir: Path) -> list[tuple[str, dict]]:
    """Every declared wave that names its own slice, validated under its own
    rules (e.g. wave 1 requires validity cards). Raises on the first error."""
    from benchmarks.limes.runner.waves import load_wave

    reports = []
    for wave_file in sorted((bank_dir.parent / "waves").glob("*.yaml")):
        wave = load_wave(wave_file)
        if wave.bank_slices:
            reports.append((wave.id, validate_wave_slice(
                bank_dir, wave.bank_slices, wave.require_validity, wave.excluded)))
    return reports


def print_wave_reports(reports: list[tuple[str, dict]]) -> None:
    for wave_id, report in reports:
        report = dict(report)
        defects = report.pop("known_anchor_defects")
        print(f"{wave_id} slice OK:", ", ".join(f"{k}={v}" for k, v in sorted(report.items())))
        for defect in defects:
            print(f"  difetto noto (anchor congelato): {defect}")


def main() -> int:
    parser = argparse.ArgumentParser(description="validate the LIMES item bank")
    parser.add_argument(
        "bank_dir",
        nargs="?",
        default="benchmarks/limes/bank",
        help="bank directory (default: the repository's bank)",
    )
    args = parser.parse_args()
    bank_dir = Path(args.bank_dir)
    try:
        summary = validate_bank(bank_dir)
        print("bank OK:", ", ".join(f"{k}={v}" for k, v in sorted(summary.items())))
        print_wave_reports(validate_waves(bank_dir))
    except ValidationError as exc:
        print(f"BANK INVALID: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
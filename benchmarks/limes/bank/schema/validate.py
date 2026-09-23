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

from benchmarks.limes.bank.schema.item import ValidationError, load_bank
from benchmarks.limes.protocol.citations import MARKERS


def validate_bank(bank_dir: Path) -> dict:
    """Load and cross-check the bank; returns a summary or raises."""
    bank = load_bank(bank_dir)
    for item in bank.items:
        for marker in item.expected_markers + item.disqualifiers:
            if marker not in MARKERS:
                raise ValidationError(
                    f"{item.id}: unknown citation marker {marker!r} "
                    f"(known: {sorted(MARKERS)})"
                )
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


def main() -> int:
    parser = argparse.ArgumentParser(description="validate the LIMES item bank")
    parser.add_argument(
        "bank_dir",
        nargs="?",
        default="benchmarks/limes/bank",
        help="bank directory (default: the repository's bank)",
    )
    args = parser.parse_args()
    try:
        summary = validate_bank(Path(args.bank_dir))
    except ValidationError as exc:
        print(f"BANK INVALID: {exc}", file=sys.stderr)
        return 1
    print("bank OK:", ", ".join(f"{k}={v}" for k, v in sorted(summary.items())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
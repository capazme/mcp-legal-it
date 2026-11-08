#!/usr/bin/env python3
"""Regenerate ``tests/fixtures/cnf/runs.json.gz``: the text runs of the CNF's real PDF.

The parser of the codice deontologico forense (``lib/cnf/parser.py``) reads typography, and
a PDF built by the tests with fpdf2 has a typography of its own (Helvetica, «-», no dot
leaders, marks in the same face). The fixture keeps what pypdf extracts from the PDF the CNF
actually publishes (Arial, «–», dot leaders, «pagina  di 3838», marks in TimesNewRoman 6.7),
so the offline suite reads the real layout: a change that breaks it fails the build, not
only the live test.

Only the runs are kept (page, position, size, font, text), not the PDF: they are what the
parser reads after ``_runs``, and the whole fixture is a few hundred kilobytes.

Usage:
    python scripts/cnf_runs_fixture.py              # the PDF linked by the CNF's page now
    python scripts/cnf_runs_fixture.py --pdf FILE   # a PDF already on disk

Then update the capture line in ``tests/fixtures/cnf/README.md`` and run
``pytest tests/unit/test_cnf.py``: a new edition changes the counts the test pins.
"""

from __future__ import annotations

import argparse
import asyncio
import gzip
import hashlib
import json
import sys
from dataclasses import asdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "plugin" / "server"))

from mcp_legal_it.lib.cnf import client, parser  # noqa: E402

OUT = ROOT / "tests" / "fixtures" / "cnf" / "runs.json.gz"


async def _dal_sito() -> tuple[str, bytes]:
    _, pdf_url, dati = await client._scarica()
    return pdf_url, dati


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pdf", type=Path, help="read this PDF instead of downloading the CNF's")
    args = ap.parse_args()

    if args.pdf:
        pdf_url, dati = str(args.pdf.name), args.pdf.read_bytes()
    else:
        pdf_url, dati = asyncio.run(_dal_sito())
    runs, titolo = parser._runs(dati)
    codice = parser.analizza(dati)  # the fixture is only worth keeping if the reading accepts it

    rec = {
        "pdf_url": pdf_url,
        "sha256": hashlib.sha256(dati).hexdigest(),
        "catturato": date.today().isoformat(),
        "titolo": titolo,
        "runs": [asdict(r) for r in runs],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    # mtime=0: the same PDF gives the same bytes, so a refresh with nothing new is no diff.
    OUT.write_bytes(gzip.compress(json.dumps(rec, ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
                                  mtime=0))
    caratteri = sum(len(r.testo) for r in runs)
    print(f"{OUT.relative_to(ROOT)}: {len(runs)} runs, {caratteri} characters, "
          f"{len(codice.articoli)} articles, sha256 {rec['sha256'][:12]}…")
    return 0


if __name__ == "__main__":
    sys.exit(main())

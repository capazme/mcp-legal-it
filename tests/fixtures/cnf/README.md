# The CNF's PDF of the codice deontologico forense, as text runs

`runs.json.gz` keeps what pypdf extracts from the PDF the Consiglio nazionale forense
publishes (`parser._runs`: page, position, size, font and text of every run), not the PDF
itself. Captured on 2026-11-08 from
`https://www.consiglionazionaleforense.it/documents/20182/40227/NUOVO+CODICE+DEONTOLOGICO+FORENSE++-+agg.+2026.pdf/8abe438b-a6fd-b8a6-9009-abaf35005f7b`
(the edition in force from 7 April 2026; sha256 `eef905d7a0e9…`, recorded in the file):
1,770 runs, 92,405 characters, 75 articles (1–73, 25-bis, 62-bis).

It is the real typography the parser reads — Arial, «–» between number and heading, dot
leaders in the index, «pagina N di M» at the foot, reference marks in TimesNewRoman 6.7 —
which the PDFs built by the tests with fpdf2 do not reproduce. Used by
`tests/unit/test_cnf.py` (the «real layout, offline» section).

To refresh, after the CNF publishes a new edition:

```bash
.venv/bin/python scripts/cnf_runs_fixture.py
.venv/bin/pytest tests/unit/test_cnf.py
```

The script refuses to write a fixture the parser does not accept; the tests pin the
2026 counts (articles, the commi of art. 68, the notes of art. 25-bis), so a new edition
updates them together with this file.

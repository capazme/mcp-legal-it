"""Tests binding the data-driven resources to the src/data JSON files.

Expectations are computed from the same JSONs the renderers read, so these
tests prove the binding (a value changed in the dataset shows up in the
resource) without pinning any specific year or rate.
"""

import json
from pathlib import Path

import src.resources as res

_DATA = Path(__file__).parents[2] / "src" / "data"


def _load(name: str) -> dict:
    return json.loads((_DATA / name).read_text())


# --- contributo unificato -------------------------------------------------


def test_cu_civil_brackets_come_from_dataset():
    out = res._render_contributo_unificato()
    cognizione = _load("contributo_unificato.json")["civile"]["cognizione"]
    assert f"€ {res._eur(cognizione[0]['importo'])}" in out
    assert f"€ {res._eur(cognizione[-1]['importo'])}" in out
    assert f"Oltre € {res._soglia(cognizione[-2]['fino_a'])}" in out


def test_cu_monitorio_and_tributario_tables_present():
    out = res._render_contributo_unificato()
    cu = _load("contributo_unificato.json")
    assert f"€ {res._eur(cu['civile']['procedimento_monitorio']['scaglioni'][0]['importo'])}" in out
    # tributario has a decimal threshold (2582.28) — exercises _soglia float path
    assert f"€ {res._soglia(cu['tributario']['scaglioni'][0]['fino_a'])}" in out


def test_cu_cautelari_matches_dataset_not_old_prose():
    # The old hardcoded prose said €98.00 while the dataset (used by the
    # tools) says otherwise: the resource must follow the dataset.
    out = res._render_contributo_unificato()
    cautelari = _load("contributo_unificato.json")["civile"]["cautelari"]
    assert f"| Procedimenti cautelari | € {res._eur(cautelari)} |" in out


def test_cu_static_notes_preserved():
    out = res._render_contributo_unificato()
    assert "Marca da bollo" in out


# --- interessi legali / mora ----------------------------------------------


def test_interessi_current_rate_from_dataset():
    out = res._render_interessi_legali()
    legali = _load("tassi_legali.json")["tassi"]
    ultimo = max(legali, key=lambda t: t["al"])
    assert f"Tasso vigente: {res._pct(ultimo['tasso'])}%" in out


def test_interessi_table_covers_full_history():
    out = res._render_interessi_legali()
    primo = _load("tassi_legali.json")["tassi"][0]
    assert f"{primo['dal'][8:10]}/{primo['dal'][5:7]}/{primo['dal'][0:4]}" in out


def test_mora_latest_semester_from_dataset():
    out = res._render_interessi_legali()
    latest = _load("tassi_mora.json")["tassi"][-1]
    sem = "I" if latest["dal"][5:7] == "01" else "II"
    row = (
        f"| {sem} sem. {latest['dal'][0:4]} "
        f"| {res._pct(latest['bce'])}% | {res._pct(latest['mora'])}% |"
    )
    assert row in out


def test_interessi_static_notes_preserved():
    out = res._render_interessi_legali()
    assert "anatocismo" in out


# --- IRPEF ----------------------------------------------------------------


def test_irpef_heading_follows_latest_dataset_year():
    out = res._render_irpef_scaglioni()
    anno = max(_load("irpef_scaglioni.json")["scaglioni_per_anno"], key=int)
    assert f"IRPEF {anno} — SCAGLIONI" in out


def test_irpef_rates_come_from_dataset():
    out = res._render_irpef_scaglioni()
    per_anno = _load("irpef_scaglioni.json")["scaglioni_per_anno"]
    scaglioni = per_anno[max(per_anno, key=int)]
    for s in scaglioni:
        assert f"| {s['aliquota']}% |" in out


def test_irpef_example_total_recomputed():
    out = res._render_irpef_scaglioni()
    per_anno = _load("irpef_scaglioni.json")["scaglioni_per_anno"]
    scaglioni = per_anno[max(per_anno, key=int)]
    prev, totale = 0, 0.0
    for s in scaglioni:
        if s.get("oltre"):
            totale += (60000 - prev) * s["aliquota"] / 100
        else:
            totale += (s["fino_a"] - prev) * s["aliquota"] / 100
            prev = s["fino_a"]
    assert f"= € {res._eur(totale)}" in out


def test_irpef_static_detrazioni_tail_preserved():
    out = res.irpef_detrazioni.fn() if hasattr(res.irpef_detrazioni, "fn") else res.irpef_detrazioni()
    assert "DETRAZIONI PER LAVORO DIPENDENTE" in out

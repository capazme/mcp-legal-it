"""Unit tests for the staleness calendars in scripts/update-data.py.

Each check runs against synthetic fixture files in a tmp dir, so the
assertions stay valid regardless of how the real data files evolve.
The dates mirror the monthly cron (1st of the month) plus the grace
boundaries around each source's publication calendar.
"""

import importlib.util
import json
from datetime import date
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "update_data", Path(__file__).parents[2] / "scripts" / "update-data.py"
)
ud = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(ud)


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(ud, "DATA_DIR", tmp_path)
    return tmp_path


def _write(data_dir: Path, name: str, payload: dict) -> None:
    (data_dir / name).write_text(json.dumps(payload))


# --- FOI: stale from latest month + 3 (ISTAT publishes M around mid M+1) ---


def test_foi_fresh_on_cron_day_with_newest_possible_month(data_dir):
    # On Aug 1 the newest publishable month is June: must NOT be stale.
    _write(data_dir, "indici_foi.json", {"indici": {"2026": {"05": 124.8, "06": 124.8}}})
    assert ud.check_foi(date(2026, 8, 1)) is False


def test_foi_stale_after_a_skipped_publication_cycle(data_dir):
    _write(data_dir, "indici_foi.json", {"indici": {"2026": {"06": 124.8}}})
    assert ud.check_foi(date(2026, 9, 1)) is True


def test_foi_threshold_rolls_over_year_end(data_dir):
    _write(data_dir, "indici_foi.json", {"indici": {"2026": {"11": 125.0}}})
    assert ud.check_foi(date(2027, 1, 1)) is False
    assert ud.check_foi(date(2027, 2, 1)) is True


# --- Mora: grace until the mid-month MEF comunicato -----------------------


MORA_H1_ONLY = {
    "tassi": [{"dal": "2026-01-01", "al": "2026-06-30", "bce": 2.15, "mora": 10.15}]
}


def test_mora_grace_on_first_cron_of_semester(data_dir):
    _write(data_dir, "tassi_mora.json", MORA_H1_ONLY)
    assert ud.check_tassi_mora(date(2026, 7, 1)) is False


def test_mora_stale_after_grace_window(data_dir):
    _write(data_dir, "tassi_mora.json", MORA_H1_ONLY)
    assert ud.check_tassi_mora(date(2026, 8, 1)) is True


def test_mora_fresh_when_semester_present(data_dir):
    _write(
        data_dir,
        "tassi_mora.json",
        {
            "tassi": MORA_H1_ONLY["tassi"]
            + [{"dal": "2026-07-01", "al": "2026-12-31", "bce": 2.40, "mora": 10.40}]
        },
    )
    assert ud.check_tassi_mora(date(2026, 8, 1)) is False


# --- TEGM: quarter + 30 days ----------------------------------------------


TEGM_Q3 = {"trimestri": {"2026-Q3": {"dal": "2026-07-01", "al": "2026-09-30", "categorie": {}}}}


def test_tegm_fresh_within_30_days_of_quarter_end(data_dir):
    _write(data_dir, "tegm.json", TEGM_Q3)
    assert ud.check_tegm(date(2026, 10, 30)) is False


def test_tegm_stale_past_30_days_of_quarter_end(data_dir):
    _write(data_dir, "tegm.json", TEGM_Q3)
    assert ud.check_tegm(date(2026, 10, 31)) is True


# --- Tassi legali: current year must be covered ---------------------------


def test_tassi_legali_current_year_present(data_dir):
    _write(
        data_dir,
        "tassi_legali.json",
        {"tassi": [{"dal": "2026-01-01", "al": "2026-12-31", "tasso": 1.6}]},
    )
    assert ud.check_tassi_legali(date(2026, 7, 30)) is False
    assert ud.check_tassi_legali(date(2027, 1, 1)) is True


# --- IRPEF: current-year brackets, January grace --------------------------


IRPEF_2026_ONLY = {"scaglioni_per_anno": {"2026": [{"oltre": True, "aliquota": 43}]}}


def test_irpef_fresh_when_current_year_present(data_dir):
    _write(data_dir, "irpef_scaglioni.json", IRPEF_2026_ONLY)
    assert ud.check_irpef(date(2026, 7, 30)) is False


def test_irpef_grace_in_january(data_dir):
    _write(data_dir, "irpef_scaglioni.json", IRPEF_2026_ONLY)
    assert ud.check_irpef(date(2027, 1, 15)) is False


def test_irpef_stale_from_february(data_dir):
    _write(data_dir, "irpef_scaglioni.json", IRPEF_2026_ONLY)
    assert ud.check_irpef(date(2027, 2, 1)) is True


# --- Danno biologico: annual art. 139 DM, flagged from Sep 1 --------------


def _danno_bio(anno_dm: int) -> dict:
    return {"micropermanenti": {"anno_ultimo_dm": anno_dm, "punto_base": 963.40}}


def test_danno_bio_not_flagged_before_september(data_dir):
    _write(data_dir, "tabella_danno_bio.json", _danno_bio(2025))
    assert ud.check_danno_bio(date(2026, 8, 31)) is False


def test_danno_bio_stale_from_september(data_dir):
    _write(data_dir, "tabella_danno_bio.json", _danno_bio(2025))
    assert ud.check_danno_bio(date(2026, 9, 1)) is True


def test_danno_bio_fresh_when_current_dm_recepito(data_dir):
    _write(data_dir, "tabella_danno_bio.json", _danno_bio(2026))
    assert ud.check_danno_bio(date(2026, 9, 1)) is False

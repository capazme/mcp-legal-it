"""lib/_clock.rome_day_unrecorded: the Italian calendar day, whatever the process's zone."""

from datetime import date, datetime, timezone

import pytest

from mcp_legal_it.lib import _clock


@pytest.fixture(autouse=True)
def _no_pin(monkeypatch):
    monkeypatch.delenv(_clock.TODAY_ENV, raising=False)
    monkeypatch.delenv(_clock.NOW_ENV, raising=False)


def test_a_pinned_day_wins(monkeypatch):
    monkeypatch.setenv(_clock.NOW_ENV, "2026-10-29T23:30:00")
    assert _clock.rome_day_unrecorded() == date(2026, 10, 29)
    monkeypatch.setenv(_clock.TODAY_ENV, "2026-11-02")
    assert _clock.rome_day_unrecorded() == date(2026, 11, 2)


def test_it_is_not_a_recorded_clock_read():
    with _clock.recording() as reads:
        _clock.rome_day_unrecorded()
    assert not reads


@pytest.mark.parametrize("utc, hours", [
    (datetime(2026, 1, 15, 12, tzinfo=timezone.utc), 1),
    (datetime(2026, 3, 29, 0, 59, tzinfo=timezone.utc), 1),   # last Sunday of March, before 01:00 UTC
    (datetime(2026, 3, 29, 1, 0, tzinfo=timezone.utc), 2),
    (datetime(2026, 7, 1, 12, tzinfo=timezone.utc), 2),
    (datetime(2026, 10, 25, 0, 59, tzinfo=timezone.utc), 2),  # last Sunday of October
    (datetime(2026, 10, 25, 1, 0, tzinfo=timezone.utc), 1),
])
def test_the_fallback_rule_is_the_eu_summer_time(utc, hours):
    assert _clock._rome_offset(utc).total_seconds() == hours * 3600


def test_the_fallback_rule_agrees_with_the_zone_database():
    zoneinfo = pytest.importorskip("zoneinfo")
    try:
        rome = zoneinfo.ZoneInfo("Europe/Rome")
    except Exception:  # noqa: BLE001 - no zone database here
        pytest.skip("no zone database")
    for year in (2024, 2025, 2026, 2027):
        for month in range(1, 13):
            for day in (1, 15, 25, 28):
                for hour in (0, 1, 2, 22, 23):
                    utc = datetime(year, month, day, hour, tzinfo=timezone.utc)
                    assert _clock._rome_offset(utc) == utc.astimezone(rome).utcoffset(), utc


def test_late_evening_utc_is_already_tomorrow_in_rome(monkeypatch):
    class _Frozen(datetime):
        @classmethod
        def now(cls, tz=None):
            moment = datetime(2026, 10, 29, 23, 30, tzinfo=timezone.utc)  # 00:30 of the 30th in Rome
            return moment.astimezone(tz) if tz else moment.replace(tzinfo=None)

    monkeypatch.setattr(_clock, "datetime", _Frozen)
    assert _clock.rome_day_unrecorded() == date(2026, 10, 30)

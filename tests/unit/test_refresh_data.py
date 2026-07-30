"""Unit tests for scripts/refresh_data.py (auto-refresh FOI / tassi mora).

All tests are offline: they exercise the parsers and the append surgery
with fixtures captured from the real sources (ISTAT page HTML, ECB CSV).
"""

import importlib.util
import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "refresh_data", Path(__file__).parents[2] / "scripts" / "refresh_data.py"
)
rd = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(rd)


# --- fixtures -----------------------------------------------------------

# Trimmed from the real page (July 2026 snapshot).
ISTAT_HTML = """
<figure class="wp-block-table"><table class="has-fixed-layout"><tbody>
<tr><td>Periodo di riferimento: <strong>GIUGNO 2026</strong> (aggiornamento mensile)</td><td>&nbsp;</td></tr>
<tr><td>Indice generale FOI (base di riferimento 2025=100)<sup>*</sup></td><td>+<strong>102,8</strong></td></tr>
<tr><td>Variazione % rispetto al mese precedente</td><td><strong>+0,0</strong></td></tr>
</tbody></table></figure>
<p>(*) Indice generale FOI (base di riferimento 2025=100, il coefficiente
di raccordo con la precedente base 2015=100 &egrave; 1,214)</p>
"""

ECB_CSV = "\n".join(
    [
        "KEY,FREQ,TIME_PERIOD,OBS_VALUE,OBS_STATUS",
        "FM.D.U2.EUR.4F.KR.MRR_FR.LEV,D,2026-06-15,2.15,A",
        "FM.D.U2.EUR.4F.KR.MRR_FR.LEV,D,2026-06-16,2.15,A",
        "FM.D.U2.EUR.4F.KR.MRR_FR.LEV,D,2026-06-17,2.40,A",
        "FM.D.U2.EUR.4F.KR.MRR_FR.LEV,D,2026-06-30,2.40,A",
        "FM.D.U2.EUR.4F.KR.MRR_FR.LEV,D,2026-07-01,2.40,A",
    ]
)

FOI_JSON = (
    '{\n'
    '  "_note": "Dati reali ISTAT aggiornati a maggio 2026. Aggiornare mensilmente.",\n'
    '  "indici": {\n'
    '    "2025": {"01": 121.9, "02": 122.1, "12": 122.6},\n'
    '    "2026": {"01": 121.9, "02": 122.5, "03": 123.2, "04": 124.4, "05": 124.8}\n'
    '  }\n'
    '}\n'
)

MORA_JSON = (
    '{\n'
    '  "_description": "Tassi mora D.Lgs. 231/2002",\n'
    '  "tassi": [\n'
    '    {"dal": "2025-07-01", "al": "2025-12-31", "bce": 2.15, "mora": 10.15},\n'
    '    {"dal": "2026-01-01", "al": "2026-06-30", "bce": 2.15, "mora": 10.15}\n'
    '  ]\n'
    '}\n'
)


# --- FOI page parsing ---------------------------------------------------


def test_parse_foi_page_real_snapshot():
    year, month, value, raccordo = rd.parse_foi_page(ISTAT_HTML)
    assert (year, month) == (2026, 6)
    assert value == Decimal("102.8")
    assert raccordo == Decimal("1.214")


def test_parse_foi_page_missing_period():
    with pytest.raises(ValueError, match="periodo di riferimento"):
        rd.parse_foi_page("<html>niente</html>")


def test_parse_foi_page_rejects_new_base():
    html = ISTAT_HTML.replace("2025=100", "2035=100")
    with pytest.raises(ValueError):
        rd.parse_foi_page(html)


def test_parse_foi_page_rejects_changed_raccordo():
    html = ISTAT_HTML.replace("1,214", "1,527")
    with pytest.raises(ValueError, match="raccordo"):
        rd.parse_foi_page(html)


def test_foi_to_base2015_known_values():
    # Real conversions: giugno 102.8 -> 124.8, febbraio 100.9 -> 122.5,
    # aprile 102.5 -> 124.4 (124.435 truncates down at 1 decimal, half-up).
    r = Decimal("1.214")
    assert rd.foi_to_base2015(Decimal("102.8"), r) == "124.8"
    assert rd.foi_to_base2015(Decimal("100.9"), r) == "122.5"
    assert rd.foi_to_base2015(Decimal("102.5"), r) == "124.4"


# --- FOI json surgery ---------------------------------------------------


def test_append_foi_month_already_present():
    assert rd.append_foi(FOI_JSON, 2026, 5, "124.8", "maggio") is None


def test_append_foi_new_month_same_year():
    out = rd.append_foi(FOI_JSON, 2026, 6, "124.8", "giugno")
    data = json.loads(out)
    assert data["indici"]["2026"]["06"] == 124.8
    assert data["indici"]["2026"]["05"] == 124.8
    assert "aggiornati a giugno 2026" in data["_note"]
    # single-line row style preserved
    assert '"2026": {"01": 121.9' in out


def test_append_foi_new_year_rollover():
    out = rd.append_foi(FOI_JSON, 2027, 1, "125.3", "gennaio")
    data = json.loads(out)
    assert data["indici"]["2027"] == {"01": 125.3}
    assert data["indici"]["2026"]["05"] == 124.8
    assert out.rstrip().endswith("}")


def test_append_foi_rejects_unknown_structure():
    with pytest.raises(ValueError):
        rd.append_foi('{"indici": {}}', 2026, 6, "124.8", "giugno")


# --- ECB csv parsing ----------------------------------------------------


def test_parse_ecb_csv_rate_at_semester_start():
    assert rd.parse_ecb_csv(ECB_CSV, date(2026, 7, 1)) == Decimal("2.40")


def test_parse_ecb_csv_rate_before_change():
    assert rd.parse_ecb_csv(ECB_CSV, date(2026, 6, 16)) == Decimal("2.15")


def test_parse_ecb_csv_no_observation():
    with pytest.raises(ValueError, match="nessuna osservazione"):
        rd.parse_ecb_csv(ECB_CSV, date(2026, 6, 1))


def test_parse_ecb_csv_missing_columns():
    with pytest.raises(ValueError, match="TIME_PERIOD"):
        rd.parse_ecb_csv("A,B\n1,2", date(2026, 7, 1))


# --- semesters and mora surgery ----------------------------------------


def test_current_semester_boundaries():
    assert rd.current_semester(date(2026, 6, 30)) == (date(2026, 1, 1), date(2026, 6, 30))
    assert rd.current_semester(date(2026, 7, 1)) == (date(2026, 7, 1), date(2026, 12, 31))


def test_append_mora_semester_already_present():
    assert rd.append_mora(MORA_JSON, date(2026, 1, 1), date(2026, 6, 30), Decimal("2.15")) is None


def test_append_mora_new_semester():
    out = rd.append_mora(MORA_JSON, date(2026, 7, 1), date(2026, 12, 31), Decimal("2.40"))
    data = json.loads(out)
    assert data["tassi"][-1] == {
        "dal": "2026-07-01", "al": "2026-12-31", "bce": 2.40, "mora": 10.40,
    }
    assert len(data["tassi"]) == 3
    assert '"bce": 2.40, "mora": 10.40' in out


def test_append_mora_rejects_unknown_structure():
    with pytest.raises(ValueError):
        rd.append_mora('{"tassi": []}', date(2026, 7, 1), date(2026, 12, 31), Decimal("2.40"))

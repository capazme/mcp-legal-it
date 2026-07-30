#!/usr/bin/env python3
"""Auto-refresh legal data files from official machine-readable sources.

Usage:
  python scripts/refresh_data.py          # fetch sources, append missing entries

Automated (appended by this script, never rewritten):
- indici_foi.json: latest monthly FOI index from the ISTAT "rivalutazioni
  monetarie" page, converted to base 2015=100 with the official linking
  coefficient (1.214, itself re-parsed from the page and sanity-checked)
- tassi_mora.json: current-semester rate from the ECB Data Portal MRO
  series (D.Lgs. 231/2002 art. 5: ECB main refinancing rate in force on
  the first calendar day of the semester, plus 8 percentage points)

Still manual (alerted by update-data.py / the monthly workflow issue):
- tegm.json: quarterly MEF decree table, published as a PDF annex
- tassi_legali.json: annual MEF decree published mid-December

Safety model: entries are only appended, existing values are never
modified; every rewrite is re-parsed and the structural delta is checked
to be exactly the intended addition, otherwise nothing is written.
A source that cannot be fetched or parsed is skipped with a warning —
update-data.py --strict remains the authority on staleness.
"""

import html as html_lib
import json
import re
import sys
import urllib.request
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "src" / "data"

ISTAT_FOI_URL = "https://www.istat.it/notizia/indice-dei-prezzi-per-le-rivalutazioni-monetarie/"
ECB_MRO_URL = (
    "https://data-api.ecb.europa.eu/service/data/FM/D.U2.EUR.4F.KR.MRR_FR.LEV"
    "?format=csvdata&startPeriod={start}&endPeriod={end}"
)

# Official ISTAT linking coefficient between base 2025=100 and base 2015=100,
# in force since the January 2026 rebasing. The page value must match this:
# a different coefficient means a new rebasing and requires manual review.
RACCORDO_2025_TO_2015 = Decimal("1.214")

MESI = {
    "gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4,
    "maggio": 5, "giugno": 6, "luglio": 7, "agosto": 8,
    "settembre": 9, "ottobre": 10, "novembre": 11, "dicembre": 12,
}

GREEN = "\033[92m"
YELLOW = "\033[93m"
RESET = "\033[0m"
BOLD = "\033[1m"


def ok(msg: str) -> str:
    return f"{GREEN}OK{RESET}    {msg}"


def warn(msg: str) -> str:
    return f"{YELLOW}WARN{RESET}  {msg}"


def fetch(url: str) -> str:
    req = urllib.request.Request(
        url, headers={"User-Agent": "mcp-legal-it data refresher (github.com/capazme/mcp-legal-it)"}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _strip_tags(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html)
    text = html_lib.unescape(text)
    return re.sub(r"\s+", " ", text)


def parse_foi_page(html: str) -> tuple[int, int, Decimal, Decimal]:
    """Returns (year, month, index value in base 2025=100, linking coefficient)."""
    text = _strip_tags(html)

    m = re.search(r"Periodo di riferimento:\s*([A-Za-zÀ-ù]+)\s+(\d{4})", text)
    if not m:
        raise ValueError("periodo di riferimento non trovato nella pagina ISTAT")
    month_name = m.group(1).strip().lower()
    if month_name not in MESI:
        raise ValueError(f"mese non riconosciuto: {month_name!r}")
    year, month = int(m.group(2)), MESI[month_name]

    m = re.search(r"Indice generale FOI \(base di riferimento (\d{4})=100\)\s*\*?\s*\+?\s*(\d{2,3},\d)", text)
    if not m:
        raise ValueError("valore dell'indice FOI non trovato nella pagina ISTAT")
    base_year = int(m.group(1))
    if base_year != 2025:
        raise ValueError(f"base di riferimento inattesa ({base_year}=100): nuovo ribasamento, aggiornare a mano")
    value = Decimal(m.group(2).replace(",", "."))
    if not Decimal("80") <= value <= Decimal("200"):
        raise ValueError(f"valore FOI fuori dal range di sanità: {value}")

    m = re.search(r"coefficiente di raccordo con la precedente base 2015=100 è\s*(\d,\d{1,3})", text)
    if not m:
        raise ValueError("coefficiente di raccordo non trovato nella pagina ISTAT")
    raccordo = Decimal(m.group(1).replace(",", "."))
    if raccordo != RACCORDO_2025_TO_2015:
        raise ValueError(f"coefficiente di raccordo cambiato ({raccordo}): aggiornare a mano")

    return year, month, value, raccordo


def foi_to_base2015(value_2025: Decimal, raccordo: Decimal) -> str:
    """Converts a base 2025=100 index to base 2015=100, 1 decimal, half-up."""
    converted = (value_2025 * raccordo).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    return str(converted)


def append_foi(text: str, year: int, month: int, value: str, month_name: str) -> str | None:
    """Appends a month to indici_foi.json content; None if already present."""
    data = json.loads(text)
    y_key, m_key = str(year), f"{month:02d}"
    if m_key in data["indici"].get(y_key, {}):
        return None

    if y_key in data["indici"]:
        pattern = rf'("{y_key}": \{{[^}}]*)\}}'
        replacement = rf'\g<1>, "{m_key}": {value}}}'
    else:
        # First month of a new year: add a new row after the last year line.
        pattern = r"\}\n  \}\n\}"
        replacement = f'}},\n    "{y_key}": {{"{m_key}": {value}}}\n  }}\n}}'
    new_text, n = re.subn(pattern, replacement, text, count=1)
    if n != 1:
        raise ValueError("struttura di indici_foi.json non riconosciuta")

    new_text = re.sub(
        r"aggiornati a \w+ \d{4}", f"aggiornati a {month_name} {year}", new_text, count=1
    )

    # The rewrite must parse and differ from the original by exactly one entry.
    new_data = json.loads(new_text)
    expected = {y: dict(months) for y, months in data["indici"].items()}
    expected.setdefault(y_key, {})[m_key] = json.loads(value)
    if new_data["indici"] != expected:
        raise ValueError("la modifica a indici_foi.json non corrisponde al solo mese atteso")
    return new_text


def parse_ecb_csv(csv_text: str, cutoff: date) -> Decimal:
    """Returns the MRO rate in force on `cutoff` (last observation <= cutoff)."""
    lines = [ln for ln in csv_text.splitlines() if ln.strip()]
    header = lines[0].split(",")
    try:
        i_date, i_value = header.index("TIME_PERIOD"), header.index("OBS_VALUE")
    except ValueError as exc:
        raise ValueError("colonne TIME_PERIOD/OBS_VALUE assenti nel CSV BCE") from exc

    best: tuple[date, Decimal] | None = None
    for line in lines[1:]:
        cells = line.split(",")
        obs_date = date.fromisoformat(cells[i_date])
        if obs_date <= cutoff and (best is None or obs_date > best[0]):
            best = (obs_date, Decimal(cells[i_value]))
    if best is None:
        raise ValueError(f"nessuna osservazione BCE entro il {cutoff}")
    rate = best[1]
    if not Decimal("0") <= rate <= Decimal("10"):
        raise ValueError(f"tasso BCE fuori dal range di sanità: {rate}")
    return rate


def current_semester(today: date) -> tuple[date, date]:
    if today.month <= 6:
        return date(today.year, 1, 1), date(today.year, 6, 30)
    return date(today.year, 7, 1), date(today.year, 12, 31)


def append_mora(text: str, dal: date, al: date, bce: Decimal) -> str | None:
    """Appends a semester to tassi_mora.json content; None if already present."""
    data = json.loads(text)
    if any(t["dal"] == dal.isoformat() for t in data["tassi"]):
        return None

    mora = bce + 8
    entry = (
        f'    {{"dal": "{dal.isoformat()}", "al": "{al.isoformat()}", '
        f'"bce": {bce:.2f}, "mora": {mora:.2f}}}'
    )
    marker = "}\n  ]"
    if text.count(marker) != 1:
        raise ValueError("struttura di tassi_mora.json non riconosciuta")
    new_text = text.replace(marker, "},\n" + entry + "\n  ]")

    new_data = json.loads(new_text)
    expected = data["tassi"] + [json.loads(entry)]
    if new_data["tassi"] != expected:
        raise ValueError("la modifica a tassi_mora.json non corrisponde al solo semestre atteso")
    return new_text


def refresh_foi() -> bool:
    """Returns True if the file was updated."""
    print(f"\n{BOLD}FOI — pagina ISTAT rivalutazioni{RESET}")
    year, month, value_2025, raccordo = parse_foi_page(fetch(ISTAT_FOI_URL))
    value = foi_to_base2015(value_2025, raccordo)
    month_name = [k for k, v in MESI.items() if v == month][0]

    path = DATA_DIR / "indici_foi.json"
    new_text = append_foi(path.read_text(), year, month, value, month_name)
    if new_text is None:
        print(ok(f"{month_name} {year} già presente (indice {value})"))
        return False
    path.write_text(new_text)
    print(ok(f"aggiunto {month_name} {year}: {value_2025} (base 2025) → {value} (base 2015)"))
    return True


def refresh_mora(today: date) -> bool:
    """Returns True if the file was updated."""
    print(f"\n{BOLD}Tassi mora — API BCE (MRO + 8pp){RESET}")
    dal, al = current_semester(today)

    path = DATA_DIR / "tassi_mora.json"
    text = path.read_text()
    if any(t["dal"] == dal.isoformat() for t in json.loads(text)["tassi"]):
        print(ok(f"semestre dal {dal} già presente"))
        return False

    url = ECB_MRO_URL.format(start=(dal - timedelta(days=40)).isoformat(), end=dal.isoformat())
    bce = parse_ecb_csv(fetch(url), cutoff=dal)
    new_text = append_mora(text, dal, al, bce)
    if new_text is None:
        return False
    path.write_text(new_text)
    print(ok(f"aggiunto semestre {dal} → {al}: BCE {bce:.2f}%, mora {bce + 8:.2f}%"))
    return True


def main() -> int:
    print(f"{BOLD}=== Auto-refresh dati — mcp-legal-it ==={RESET}")
    updated = False
    for step in (refresh_foi, lambda: refresh_mora(date.today())):
        try:
            updated = step() or updated
        except Exception as exc:  # noqa: BLE001 — a broken source must not block the other
            print(warn(f"sorgente saltata: {exc}"))

    print(f"\n{'aggiornamenti scritti' if updated else 'nessun aggiornamento necessario'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

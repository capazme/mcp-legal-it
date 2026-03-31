#!/usr/bin/env python3
"""Check if legal data files are stale and need manual update.

Usage:
  python scripts/update-data.py          # check all data files
  python scripts/update-data.py --strict # exit 1 if any data is stale

Data files checked:
- tegm.json: TEGM rates, updated quarterly (Banca d'Italia / MEF)
- indici_foi.json: FOI ISTAT indices, updated monthly
- tassi_legali.json: legal interest rates, updated annually (DM MEF)
- tassi_mora.json: late payment rates, updated semi-annually (BCE + 8pp)

This script does NOT auto-update data — government sources are too
unreliable for automated scraping. It alerts maintainers to update manually.
"""

import json
import sys
from datetime import date, timedelta
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "src" / "data"

TEGM_SOURCE = "https://www.bancaditalia.it/compiti/vigilanza/compiti-vigilanza/tegm/"
FOI_SOURCE = "https://www.istat.it/notizia/indice-dei-prezzi-per-le-rivalutazioni-monetarie/"
TASSI_LEGALI_SOURCE = "https://www.mef.gov.it/it/atti-normative/Decreti-Ministeriali/"
TASSI_MORA_SOURCE = "https://www.mef.gov.it/it/atti-normative/Decreti-Ministeriali/"

GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
RESET = "\033[0m"
BOLD = "\033[1m"


def ok(msg: str) -> str:
    return f"{GREEN}OK{RESET}    {msg}"


def stale(msg: str) -> str:
    return f"{RED}STALE{RESET} {msg}"


def warn(msg: str) -> str:
    return f"{YELLOW}WARN{RESET}  {msg}"


def check_tegm(today: date) -> bool:
    """Returns True if stale."""
    path = DATA_DIR / "tegm.json"
    data = json.loads(path.read_text())
    trimestri = data["trimestri"]

    latest_key = max(trimestri.keys())
    latest = trimestri[latest_key]
    al_date = date.fromisoformat(latest["al"])
    dal_date = date.fromisoformat(latest["dal"])

    threshold = al_date + timedelta(days=30)
    is_stale = today > threshold

    label = f"tegm.json         ({path.name})"
    print(f"\n{BOLD}TEGM — Tassi Effettivi Globali Medi{RESET}")
    print(f"  Ultimo trimestre : {latest_key} ({dal_date} → {al_date})")
    print(f"  Data attuale     : {today}")

    if is_stale:
        # Determine expected quarter
        quarter = (al_date.month // 3) + 1
        expected_year = al_date.year if quarter <= 4 else al_date.year + 1
        expected_q = quarter if quarter <= 4 else 1
        print(stale(f"Scaduto il {threshold} — aggiornare al trimestre {expected_year}-Q{expected_q}"))
        print(f"  Fonte : {TEGM_SOURCE}")
        print(f"  Azione: aggiornare src/data/tegm.json con il nuovo trimestre dal DM MEF in GU")
        return True
    else:
        days_left = (threshold - today).days
        print(ok(f"Aggiornato — prossima scadenza attesa entro {threshold} ({days_left} giorni)"))
        return False


def check_foi(today: date) -> bool:
    """Returns True if stale. FOI is stale if we are 2+ months past latest entry."""
    path = DATA_DIR / "indici_foi.json"
    data = json.loads(path.read_text())
    indici = data["indici"]

    latest_year = max(indici.keys(), key=int)
    latest_months = indici[latest_year]
    latest_month = max(latest_months.keys(), key=int)
    latest_value = latest_months[latest_month]

    latest_date = date(int(latest_year), int(latest_month), 1)
    # ISTAT publishes the previous month's data with ~1 month delay.
    # We consider stale if today is more than 2 full months past the latest entry.
    stale_threshold = date(
        latest_date.year + (latest_date.month // 12),
        ((latest_date.month % 12) + 2) or 12,
        1,
    )
    # Simpler: add 60 days as approximation
    stale_threshold = date(latest_date.year, latest_date.month, 1)
    # advance by 2 months
    m = latest_date.month + 2
    y = latest_date.year + (m - 1) // 12
    m = ((m - 1) % 12) + 1
    stale_threshold = date(y, m, 1)

    is_stale = today >= stale_threshold

    print(f"\n{BOLD}FOI — Indici ISTAT per rivalutazioni monetarie{RESET}")
    print(f"  Ultimo dato      : {latest_year}/{latest_month} (indice {latest_value})")
    print(f"  Data attuale     : {today}")

    if is_stale:
        next_m = int(latest_month) + 1
        next_y = int(latest_year) + (next_m - 1) // 12
        next_m = ((next_m - 1) % 12) + 1
        print(stale(f"Scaduto — mancano i dati da {next_y}/{next_m:02d} in poi"))
        print(f"  Fonte : {FOI_SOURCE}")
        print(f"  Azione: aggiornare src/data/indici_foi.json con gli indici FOI mensili mancanti")
        return True
    else:
        months_until = (stale_threshold.year - today.year) * 12 + (stale_threshold.month - today.month)
        print(ok(f"Aggiornato — scadenza attesa entro {stale_threshold} (~{months_until} mese/i)"))
        return False


def check_tassi_legali(today: date) -> bool:
    """Returns True if stale. Stale = current year not present."""
    path = DATA_DIR / "tassi_legali.json"
    data = json.loads(path.read_text())
    tassi = data["tassi"]

    current_year = today.year
    latest_al = max(date.fromisoformat(t["al"]) for t in tassi)
    latest_year = latest_al.year

    is_stale = current_year > latest_year

    print(f"\n{BOLD}Tassi Legali — art. 1284 c.c. (DM MEF annuale){RESET}")
    print(f"  Anno coperto     : fino al {latest_year}")
    print(f"  Anno corrente    : {current_year}")

    if is_stale:
        print(stale(f"Manca il tasso legale per {current_year} (e anni successivi se più di uno)"))
        print(f"  Fonte : {TASSI_LEGALI_SOURCE}")
        print(f"  Azione: aggiornare src/data/tassi_legali.json con il DM MEF pubblicato in GU a dicembre {current_year - 1}")
        return True
    else:
        print(ok(f"Tasso {current_year} presente"))
        return False


def check_tassi_mora(today: date) -> bool:
    """Returns True if stale. Stale = current semester not present."""
    path = DATA_DIR / "tassi_mora.json"
    data = json.loads(path.read_text())
    tassi = data["tassi"]

    latest_al = max(date.fromisoformat(t["al"]) for t in tassi)
    latest_dal = max(date.fromisoformat(t["dal"]) for t in tassi)

    # Current semester boundaries
    if today.month <= 6:
        current_sem_start = date(today.year, 1, 1)
        current_sem_end = date(today.year, 6, 30)
    else:
        current_sem_start = date(today.year, 7, 1)
        current_sem_end = date(today.year, 12, 31)

    is_stale = latest_dal < current_sem_start

    sem_label = f"{latest_dal.year}/{'H1' if latest_dal.month <= 6 else 'H2'}"
    print(f"\n{BOLD}Tassi Mora — D.Lgs. 231/2002 (BCE semestrali){RESET}")
    print(f"  Ultimo semestre  : {sem_label} ({latest_dal} → {latest_al})")
    print(f"  Semestre attuale : {current_sem_start} → {current_sem_end}")

    if is_stale:
        new_sem = f"{current_sem_start.year}/{'H1' if current_sem_start.month == 1 else 'H2'}"
        print(stale(f"Manca il tasso mora per {new_sem}"))
        print(f"  Fonte : {TASSI_MORA_SOURCE}")
        print(f"  Azione: aggiornare src/data/tassi_mora.json con il tasso BCE del semestre corrente (+8pp)")
        return True
    else:
        print(ok(f"Semestre corrente ({current_sem_start} → {current_sem_end}) coperto"))
        return False


def main() -> int:
    strict = "--strict" in sys.argv
    today = date.today()

    print(f"{BOLD}=== Data Freshness Check — mcp-legal-it ==={RESET}")
    print(f"Data odierna: {today}")

    stale_flags = [
        check_tegm(today),
        check_foi(today),
        check_tassi_legali(today),
        check_tassi_mora(today),
    ]

    stale_count = sum(stale_flags)
    print(f"\n{'=' * 44}")
    if stale_count == 0:
        print(f"{GREEN}{BOLD}Tutti i file sono aggiornati.{RESET}")
    else:
        print(f"{RED}{BOLD}{stale_count} file/i da aggiornare.{RESET}")
        if strict:
            print("Uscita con codice 1 (--strict attivo).")
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

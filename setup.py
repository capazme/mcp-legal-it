#!/usr/bin/env python3
"""
Setup interattivo per MCP Legal IT.

Installa i profili selezionati in Claude Desktop e/o Claude Code.
Pensato per essere eseguito con:

    python3 setup.py

Nessun argomento richiesto — il setup è completamente guidato.
"""
import json
import os
import platform
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROJECT_DIR = Path(__file__).resolve().parent
VENV_DIR = PROJECT_DIR / ".venv"
VENV_PYTHON = VENV_DIR / "bin" / "python"
RUN_SERVER = PROJECT_DIR / "run_server.py"

MIN_PYTHON = (3, 10)

PROFILES = {
    "sinistro": {
        "desc": "Sinistri e risarcimento danni",
        "detail": "danno biologico, rivalutazione, interessi, normativa, giurisprudenza",
        "tools": 42,
    },
    "credito": {
        "desc": "Recupero crediti",
        "detail": "interessi mora, rivalutazione, decreto ingiuntivo, parcella avvocato",
        "tools": 50,
    },
    "penale": {
        "desc": "Diritto penale",
        "detail": "prescrizione, calcolo pena, patteggiamento, giurisprudenza",
        "tools": 14,
    },
    "fiscale": {
        "desc": "Fiscale e immobiliare",
        "detail": "IRPEF, detrazioni, TFR, successioni, IMU, compravendite",
        "tools": 39,
    },
    "normativa": {
        "desc": "Ricerca normativa e giurisprudenziale",
        "detail": "testo leggi, sentenze Cassazione, provvedimenti Garante Privacy",
        "tools": 12,
    },
    "studio": {
        "desc": "Gestione studio legale",
        "detail": "scadenze processuali, atti giudiziari, parcelle, contributo unificato",
        "tools": 57,
    },
    "full": {
        "desc": "Tutti gli strumenti (147 tool)",
        "detail": "consigliato per Claude Code (usa Tool Search per caricarli on-demand)",
        "tools": 147,
    },
}

# Claude Desktop config path per OS
_CLAUDE_DESKTOP_PATHS = {
    "Darwin": Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json",
    "Linux": Path.home() / ".config" / "Claude" / "claude_desktop_config.json",
    "Windows": Path(os.environ.get("APPDATA", "")) / "Claude" / "claude_desktop_config.json",
}

# Claude Code config path (project-scoped .mcp.json)
_CLAUDE_CODE_MCP = PROJECT_DIR / ".mcp.json"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BLUE = "\033[94m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def _supports_color() -> bool:
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


def c(code: str, text: str) -> str:
    return f"{code}{text}{RESET}" if _supports_color() else text


def banner() -> None:
    print()
    print(c(BOLD, "  MCP Legal IT — Setup interattivo"))
    print(c(DIM, "  Installa i profili in Claude Desktop e/o Claude Code"))
    print(c(DIM, "  " + "-" * 55))
    print()


def info(msg: str) -> None:
    print(f"  {c(BLUE, '>')} {msg}")


def success(msg: str) -> None:
    print(f"  {c(GREEN, 'OK')} {msg}")


def warn(msg: str) -> None:
    print(f"  {c(YELLOW, '!')} {msg}")


def error(msg: str) -> None:
    print(f"  {c(RED, 'X')} {msg}")


def ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    try:
        answer = input(f"  {c(BOLD, '?')} {prompt}{suffix}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit(0)
    return answer or default


def ask_yes_no(prompt: str, default: bool = True) -> bool:
    hint = "S/n" if default else "s/N"
    answer = ask(f"{prompt} ({hint})", "s" if default else "n")
    return answer.lower() in ("s", "si", "sì", "y", "yes", "")


# ---------------------------------------------------------------------------
# Steps
# ---------------------------------------------------------------------------

def check_python() -> None:
    info("Controllo versione Python...")
    v = sys.version_info
    if (v.major, v.minor) < MIN_PYTHON:
        error(f"Serve Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+, trovato {v.major}.{v.minor}")
        print()
        print(f"    Installa Python aggiornato da https://www.python.org/downloads/")
        sys.exit(1)
    success(f"Python {v.major}.{v.minor}.{v.micro}")


def setup_venv() -> None:
    if VENV_PYTHON.exists():
        success(f"Virtual environment trovato: {VENV_DIR.name}/")
        return

    info("Creo il virtual environment...")
    try:
        subprocess.run(
            [sys.executable, "-m", "venv", str(VENV_DIR)],
            check=True,
            capture_output=True,
        )
        success("Virtual environment creato")
    except subprocess.CalledProcessError as e:
        error(f"Errore nella creazione del venv: {e.stderr.decode()[:200]}")
        sys.exit(1)


def install_deps() -> None:
    info("Installo le dipendenze (potrebbe richiedere un minuto)...")
    try:
        result = subprocess.run(
            [str(VENV_PYTHON), "-m", "pip", "install", "-e", str(PROJECT_DIR), "-q"],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_DIR),
        )
        if result.returncode != 0:
            # Retry without -e (editable) in case of issues
            result = subprocess.run(
                [str(VENV_PYTHON), "-m", "pip", "install", str(PROJECT_DIR), "-q"],
                capture_output=True,
                text=True,
                cwd=str(PROJECT_DIR),
            )
        if result.returncode != 0:
            error("Errore nell'installazione delle dipendenze:")
            print(f"    {result.stderr[:300]}")
            sys.exit(1)
        success("Dipendenze installate")
    except FileNotFoundError:
        error("pip non trovato nel virtual environment")
        sys.exit(1)


def verify_server() -> None:
    info("Verifico che il server si avvii correttamente...")
    result = subprocess.run(
        [str(VENV_PYTHON), "-c", "from src.server import mcp; print(len(list(mcp._tool_manager._tools.keys())))"],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_DIR),
    )
    if result.returncode != 0:
        error("Il server non si avvia:")
        print(f"    {result.stderr[:300]}")
        sys.exit(1)
    count = result.stdout.strip()
    success(f"Server OK — {count} tool registrati")


def select_profiles() -> list[str]:
    print()
    print(c(BOLD, "  Profili disponibili:"))
    print()

    keys = list(PROFILES.keys())
    for i, key in enumerate(keys, 1):
        p = PROFILES[key]
        num = c(BOLD, f"  {i}.")
        name = c(BOLD, key)
        tools = c(DIM, f"({p['tools']} tool)")
        print(f"{num} {name} {tools}")
        print(f"     {p['desc']} — {p['detail']}")
        print()

    print(c(DIM, "  Consiglio: installa 'normativa' + il tuo ambito principale."))
    print(c(DIM, "  Per Claude Code, aggiungi anche 'full'."))
    print()

    answer = ask(
        "Quali profili vuoi installare? (numeri separati da spazio, o 'tutti')",
        "5 7",
    )

    if answer.lower() in ("tutti", "all", "*"):
        selected = keys
    else:
        try:
            indices = [int(x) for x in answer.split()]
            selected = [keys[i - 1] for i in indices if 1 <= i <= len(keys)]
        except (ValueError, IndexError):
            warn("Input non valido, installo i profili consigliati (normativa + full)")
            selected = ["normativa", "full"]

    if not selected:
        selected = ["normativa", "full"]

    print()
    info(f"Profili selezionati: {c(BOLD, ', '.join(selected))}")
    return selected


def _build_server_entry(profile: str) -> dict:
    """Build a single MCP server config entry."""
    entry = {
        "command": str(VENV_PYTHON),
        "args": [str(RUN_SERVER)],
    }
    if profile != "full":
        entry["env"] = {"LEGAL_PROFILE": profile}
    return entry


def _server_name(profile: str) -> str:
    return f"legal-it-{profile}" if profile != "full" else "legal-it"


def install_claude_desktop(profiles: list[str]) -> bool:
    system = platform.system()
    config_path = _CLAUDE_DESKTOP_PATHS.get(system)

    if not config_path:
        warn(f"Sistema operativo {system} non supportato per Claude Desktop")
        return False

    # Check if Claude Desktop is installed
    claude_dir = config_path.parent
    if not claude_dir.exists():
        warn("Claude Desktop non sembra installato (cartella di configurazione non trovata)")
        if not ask_yes_no("Vuoi creare la configurazione comunque?", default=False):
            return False
        claude_dir.mkdir(parents=True, exist_ok=True)

    # Read existing config
    config: dict = {}
    if config_path.exists():
        try:
            config = json.loads(config_path.read_text())
        except (json.JSONDecodeError, OSError):
            warn("Configurazione esistente non valida, ne creo una nuova")

    if "mcpServers" not in config:
        config["mcpServers"] = {}

    # Check for existing legal-it servers
    existing = [k for k in config["mcpServers"] if k.startswith("legal-it")]
    if existing:
        warn(f"Trovati server MCP Legal IT esistenti: {', '.join(existing)}")
        if ask_yes_no("Vuoi sovrascriverli?"):
            for k in existing:
                del config["mcpServers"][k]
        else:
            info("Mantengo la configurazione esistente, aggiungo solo i nuovi")

    # Add selected profiles
    added = []
    for profile in profiles:
        name = _server_name(profile)
        config["mcpServers"][name] = _build_server_entry(profile)
        added.append(name)

    # Write config
    try:
        # Backup
        if config_path.exists():
            backup = config_path.with_suffix(".json.bak")
            shutil.copy2(config_path, backup)

        config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n")
        success(f"Configurazione Claude Desktop aggiornata: {config_path}")
        for name in added:
            profile = name.replace("legal-it-", "") if name != "legal-it" else "full"
            tools = PROFILES[profile]["tools"]
            print(f"     + {c(GREEN, name)} ({tools} tool)")
        return True
    except OSError as e:
        error(f"Impossibile scrivere la configurazione: {e}")
        return False


def install_claude_code(profiles: list[str]) -> bool:
    # Read existing .mcp.json
    config: dict = {}
    if _CLAUDE_CODE_MCP.exists():
        try:
            config = json.loads(_CLAUDE_CODE_MCP.read_text())
        except (json.JSONDecodeError, OSError):
            pass

    if "mcpServers" not in config:
        config["mcpServers"] = {}

    # Remove existing legal-it entries
    config["mcpServers"] = {
        k: v for k, v in config["mcpServers"].items() if not k.startswith("legal-it")
    }

    # Add selected profiles
    added = []
    for profile in profiles:
        name = _server_name(profile)
        config["mcpServers"][name] = _build_server_entry(profile)
        added.append(name)

    try:
        _CLAUDE_CODE_MCP.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n")
        success(f"Configurazione Claude Code aggiornata: {_CLAUDE_CODE_MCP.name}")
        for name in added:
            profile = name.replace("legal-it-", "") if name != "legal-it" else "full"
            tools = PROFILES[profile]["tools"]
            print(f"     + {c(GREEN, name)} ({tools} tool)")
        return True
    except OSError as e:
        error(f"Impossibile scrivere .mcp.json: {e}")
        return False


def select_targets() -> list[str]:
    print()
    print(c(BOLD, "  Dove vuoi installare i profili?"))
    print()
    print(f"  {c(BOLD, '1.')} Claude Desktop {c(DIM, '(app desktop)')}")
    print(f"  {c(BOLD, '2.')} Claude Code {c(DIM, '(terminale / .mcp.json nel progetto)')}")
    print(f"  {c(BOLD, '3.')} Entrambi")
    print()

    answer = ask("Scegli", "1")

    if answer == "1":
        return ["desktop"]
    elif answer == "2":
        return ["code"]
    elif answer == "3":
        return ["desktop", "code"]
    else:
        return ["desktop"]


def summary(profiles: list[str], targets: list[str]) -> None:
    print()
    print(c(DIM, "  " + "-" * 55))
    print()
    print(c(BOLD + GREEN, "  Setup completato!"))
    print()

    if "desktop" in targets:
        print(f"  {c(BOLD, 'Claude Desktop')}:")
        print(f"    Riavvia Claude Desktop per attivare i profili.")
        print(f"    I server appariranno come:")
        for p in profiles:
            print(f"      - {_server_name(p)}")
        print()

    if "code" in targets:
        print(f"  {c(BOLD, 'Claude Code')}:")
        print(f"    Apri una nuova sessione nella cartella del progetto.")
        print(f"    I tool saranno disponibili automaticamente.")
        print()

    print(f"  {c(BOLD, 'Profili installati')}:")
    for p in profiles:
        desc = PROFILES[p]["desc"]
        tools = PROFILES[p]["tools"]
        print(f"    {c(GREEN, p):>25s}  {desc} ({tools} tool)")

    print()
    print(c(DIM, "  Per cambiare profili in futuro, riesegui: python3 setup.py"))
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    banner()

    # Step 1: Prerequisites
    check_python()
    setup_venv()
    install_deps()
    verify_server()

    # Step 2: Select profiles
    profiles = select_profiles()

    # Step 3: Select targets
    targets = select_targets()

    # Step 4: Install
    print()
    ok = True
    if "desktop" in targets:
        info("Configuro Claude Desktop...")
        ok = install_claude_desktop(profiles) and ok
    if "code" in targets:
        info("Configuro Claude Code...")
        ok = install_claude_code(profiles) and ok

    if not ok:
        print()
        warn("Setup completato con avvisi — controlla i messaggi sopra.")

    # Step 5: Summary
    summary(profiles, targets)


if __name__ == "__main__":
    main()

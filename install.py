#!/usr/bin/env python3
"""
Setup interattivo per MCP Legal IT.

Installa i profili selezionati in Claude Desktop, Claude Code e/o il plugin Claude Code.

    python3 install.py                    # setup interattivo
    python3 install.py --non-interactive  # defaults automatici
    python3 install.py --uninstall        # rimuovi tutto
    python3 install.py --profile full --target plugin
"""
import argparse
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
VENV_PYTHON = (
    VENV_DIR / "Scripts" / "python.exe"
    if platform.system() == "Windows"
    else VENV_DIR / "bin" / "python"
)
RUN_SERVER = PROJECT_DIR / "run_server.py"
CACHE_DIR = Path.home() / ".cache" / "mcp-legal-it"
REMOTE_SSE_URL = "https://unsomber-lashanda-uneffaceable.ngrok-free.dev/legal-it/sse"

MIN_PYTHON = (3, 10)

PROFILES = {
    "sinistro": {
        "desc": "Sinistri e risarcimento danni",
        "detail": "danno biologico, rivalutazione, interessi, normativa, giurisprudenza",
        "tools": 44,
    },
    "credito": {
        "desc": "Recupero crediti",
        "detail": "interessi mora, rivalutazione, decreto ingiuntivo, parcella avvocato",
        "tools": 52,
    },
    "penale": {
        "desc": "Diritto penale",
        "detail": "prescrizione, calcolo pena, patteggiamento, giurisprudenza",
        "tools": 16,
    },
    "fiscale": {
        "desc": "Fiscale e immobiliare",
        "detail": "IRPEF, detrazioni, TFR, successioni, IMU, compravendite",
        "tools": 39,
    },
    "normativa": {
        "desc": "Ricerca normativa e giurisprudenziale",
        "detail": "testo leggi, sentenze Cassazione, provvedimenti Garante Privacy",
        "tools": 26,
    },
    "privacy": {
        "desc": "Privacy e GDPR",
        "detail": "informative, DPIA, registro trattamenti, data breach, normativa, giurisprudenza",
        "tools": 26,
    },
    "studio": {
        "desc": "Gestione studio legale",
        "detail": "scadenze processuali, atti giudiziari, parcelle, contributo unificato",
        "tools": 57,
    },
    "full": {
        "desc": "Tutti gli strumenti",
        "detail": "consigliato per Claude Code (usa Tool Search per caricarli on-demand)",
        "tools": 161,
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

# Plugin directory
PLUGIN_DIR = PROJECT_DIR / "plugin"

# ---------------------------------------------------------------------------
# CLI arguments
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Setup interattivo per MCP Legal IT",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Esempi:
              python3 install.py                              # interattivo
              python3 install.py -y                           # defaults (full, desktop)
              python3 install.py --profile full --target plugin
              python3 install.py --target plugin --mode local # plugin con server locale
              python3 install.py --uninstall
        """),
    )
    parser.add_argument(
        "--non-interactive", "-y",
        action="store_true",
        help="Usa defaults automatici (profilo full, target desktop)",
    )
    parser.add_argument(
        "--uninstall",
        action="store_true",
        help="Rimuovi le configurazioni legal-it da tutti i target",
    )
    parser.add_argument(
        "--profile",
        choices=list(PROFILES.keys()),
        help="Preseleziona profilo senza prompt interattivo",
    )
    parser.add_argument(
        "--target",
        choices=["desktop", "code", "plugin"],
        action="append",
        help="Target di installazione (ripetibile, es. --target desktop --target code)",
    )
    parser.add_argument(
        "--mode",
        choices=["local", "remote"],
        help="Modalità server per il plugin: locale (stdio) o remoto (SSE)",
    )
    return parser.parse_args()


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
    print(c(DIM, "  Installa i profili in Claude Desktop, Claude Code e/o Plugin"))
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
        print("    Installa Python aggiornato da https://www.python.org/downloads/")
        sys.exit(1)
    success(f"Python {v.major}.{v.minor}.{v.micro}")


def detect_existing_install() -> dict[str, bool]:
    """Check for existing installation artifacts."""
    result = {
        "venv": VENV_DIR.exists() and VENV_PYTHON.exists(),
        "desktop": False,
        "code": _CLAUDE_CODE_MCP.exists(),
        "plugin": False,
    }
    # Check Claude Desktop config
    config_path = _CLAUDE_DESKTOP_PATHS.get(platform.system())
    if config_path and config_path.exists():
        try:
            config = json.loads(config_path.read_text())
            result["desktop"] = any(
                k.startswith("legal-it") for k in config.get("mcpServers", {})
            )
        except (json.JSONDecodeError, OSError):
            pass
    # Check plugin
    result["plugin"] = _is_plugin_installed()
    return result


def _is_plugin_installed() -> bool:
    """Check if the Claude Code plugin is installed."""
    if not shutil.which("claude"):
        return False
    try:
        result = subprocess.run(
            ["claude", "plugin", "list"],
            capture_output=True, text=True, timeout=10,
        )
        return "legal-it" in result.stdout
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


def setup_venv(*, force: bool = False) -> None:
    if VENV_PYTHON.exists() and not force:
        success(f"Virtual environment trovato: {VENV_DIR.name}/")
        return

    if force and VENV_DIR.exists():
        info("Rimuovo il virtual environment esistente...")
        shutil.rmtree(VENV_DIR)

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


def setup_cache() -> None:
    """Create cache directory for Brocardi URL cache."""
    if not CACHE_DIR.exists():
        info(f"Creo directory cache: {CACHE_DIR}")
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        success("Directory cache creata")
    else:
        success(f"Directory cache trovata: {CACHE_DIR}")


def verify_server() -> int:
    """Verify server starts and return actual tool count."""
    info("Verifico che il server si avvii correttamente...")
    result = subprocess.run(
        [str(VENV_PYTHON), "-c", "import asyncio; from src.server import mcp; print(len(asyncio.run(mcp.list_tools())))"],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_DIR),
    )
    if result.returncode != 0:
        error("Il server non si avvia:")
        print(f"    {result.stderr[:300]}")
        sys.exit(1)
    count = int(result.stdout.strip())
    success(f"Server OK — {count} tool registrati")
    return count


def select_profiles(args: argparse.Namespace) -> list[str]:
    if args.non_interactive:
        profiles = [args.profile] if args.profile else ["full"]
        info(f"Profilo selezionato: {c(BOLD, ', '.join(profiles))}")
        return profiles

    if args.profile:
        info(f"Profilo preselezionato: {c(BOLD, args.profile)}")
        return [args.profile]

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
        "6 8",
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
    env = {}
    if profile != "full":
        env["LEGAL_PROFILE"] = profile
    if CACHE_DIR.exists():
        env["MCP_CACHE_DIR"] = str(CACHE_DIR)
    if env:
        entry["env"] = env
    return entry


def _server_name(profile: str) -> str:
    return f"legal-it-{profile}" if profile != "full" else "legal-it"


def _is_claude_desktop_running() -> bool:
    """Check if Claude Desktop app is currently running."""
    system = platform.system()
    try:
        if system == "Darwin":
            return subprocess.run(["pgrep", "-x", "Claude"], capture_output=True).returncode == 0
        elif system == "Linux":
            return subprocess.run(["pgrep", "-f", "claude-desktop"], capture_output=True).returncode == 0
        elif system == "Windows":
            r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq Claude.exe"], capture_output=True, text=True)
            return "Claude.exe" in r.stdout
    except (subprocess.SubprocessError, FileNotFoundError):
        pass
    return False


def _quit_claude_desktop() -> bool:
    """Gracefully quit Claude Desktop. Returns True if process exited."""
    import time

    system = platform.system()
    try:
        if system == "Darwin":
            subprocess.run(
                ["osascript", "-e", 'tell application "Claude" to quit'],
                capture_output=True, timeout=10,
            )
        elif system == "Windows":
            subprocess.run(["taskkill", "/IM", "Claude.exe"], capture_output=True, timeout=10)
        else:
            subprocess.run(["pkill", "-f", "claude-desktop"], capture_output=True, timeout=10)
    except (subprocess.SubprocessError, FileNotFoundError):
        return False

    for _ in range(10):
        if not _is_claude_desktop_running():
            return True
        time.sleep(0.5)
    return not _is_claude_desktop_running()


def _build_plugin_mcp_config(*, local: bool) -> dict:
    """Build the plugin's .mcp.json content."""
    if local:
        return {"mcpServers": {"legal-it": _build_server_entry("full")}}
    return {"mcpServers": {"legal-it": {"url": REMOTE_SSE_URL}}}


def install_claude_desktop(profiles: list[str], *, non_interactive: bool = False) -> bool:
    system = platform.system()
    config_path = _CLAUDE_DESKTOP_PATHS.get(system)

    if not config_path:
        warn(f"Sistema operativo {system} non supportato per Claude Desktop")
        return False

    # Check if Claude Desktop is running (it overwrites config on exit)
    if _is_claude_desktop_running():
        warn("Claude Desktop è in esecuzione — sovrascriverà il config all'uscita")
        if non_interactive:
            info("Chiudo Claude Desktop automaticamente...")
            if _quit_claude_desktop():
                success("Claude Desktop chiuso")
            else:
                warn("Impossibile chiudere Claude Desktop — il config potrebbe essere sovrascritto")
                info("Riavvia Claude Desktop manualmente dopo l'installazione")
        elif ask_yes_no("Chiudere Claude Desktop automaticamente?"):
            if _quit_claude_desktop():
                success("Claude Desktop chiuso")
            else:
                warn("Impossibile chiudere automaticamente")
                input(f"  {c(BOLD, '>')} Chiudi manualmente (Cmd+Q) e premi Invio... ")
        else:
            input(f"  {c(BOLD, '>')} Chiudi manualmente (Cmd+Q) e premi Invio... ")

    # Check if Claude Desktop is installed
    claude_dir = config_path.parent
    if not claude_dir.exists():
        warn("Claude Desktop non sembra installato (cartella di configurazione non trovata)")
        if non_interactive:
            info("Creo la configurazione comunque (--non-interactive)")
            claude_dir.mkdir(parents=True, exist_ok=True)
        elif not ask_yes_no("Vuoi creare la configurazione comunque?", default=False):
            return False
        else:
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
        if non_interactive or ask_yes_no("Vuoi sovrascriverli?"):
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


def install_plugin(*, non_interactive: bool = False, local: bool = False) -> bool:
    """Install the Claude Code plugin (skills, agents, hooks + MCP server)."""
    if not PLUGIN_DIR.exists():
        error(f"Directory plugin non trovata: {PLUGIN_DIR}")
        return False

    claude_bin = shutil.which("claude")
    if not claude_bin:
        error("CLI 'claude' non trovata nel PATH")
        print()
        print("    Installa Claude Code: https://docs.anthropic.com/en/docs/claude-code/overview")
        print("    Dopo l'installazione, assicurati che 'claude' sia nel PATH")
        return False

    info(f"CLI Claude trovata: {claude_bin}")

    # Write appropriate .mcp.json for the plugin
    plugin_mcp = PLUGIN_DIR / ".mcp.json"
    plugin_mcp.write_text(
        json.dumps(_build_plugin_mcp_config(local=local), indent=2, ensure_ascii=False) + "\n"
    )
    mode_label = "locale (stdio)" if local else "remoto (SSE)"
    info(f"Modalità server: {c(BOLD, mode_label)}")

    # Check if already installed
    already_installed = _is_plugin_installed()
    if already_installed:
        warn("Plugin legal-it già installato")
        if non_interactive:
            action = "update"
        else:
            answer = ask("Vuoi aggiornare (a) o reinstallare (r)?", "a")
            action = "reinstall" if answer.lower() in ("r", "reinstall") else "update"

        if action == "reinstall":
            info("Rimuovo il plugin esistente...")
            subprocess.run(
                ["claude", "plugin", "remove", "legal-it"],
                capture_output=True, text=True, timeout=30,
            )

    # Register as marketplace source (marketplace.json is in repo root)
    info("Registro il marketplace locale...")
    result = subprocess.run(
        ["claude", "plugin", "marketplace", "add", str(PROJECT_DIR)],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0 and "already" not in result.stderr.lower():
        warn(f"Marketplace add: {result.stderr.strip()[:200]}")

    # Install / update
    verb = "Aggiorno" if already_installed else "Installo"
    info(f"{verb} il plugin legal-it...")
    cmd = "install" if not already_installed else "install"
    result = subprocess.run(
        ["claude", "plugin", cmd, "legal-it@mcp-legal-it"],
        capture_output=True, text=True, timeout=60,
    )
    if result.returncode != 0:
        error(f"Installazione plugin fallita: {result.stderr.strip()[:300]}")
        print()
        print("    Prova manualmente:")
        print(f"      claude plugin marketplace add {PROJECT_DIR / 'plugin'}")
        print("      claude plugin install legal-it@mcp-legal-it")
        return False

    success("Plugin legal-it installato")
    print("     Contenuto: 17 skill, 3 agenti, hooks Legal Grounding, server MCP")
    return True


def select_targets(args: argparse.Namespace) -> list[str]:
    if args.non_interactive:
        return args.target if args.target else ["desktop"]

    if args.target:
        return args.target

    print()
    print(c(BOLD, "  Dove vuoi installare?"))
    print()
    print(f"  {c(BOLD, '1.')} Claude Desktop {c(DIM, '(app desktop — stdio)')}")
    print(f"  {c(BOLD, '2.')} Claude Code — MCP server {c(DIM, '(.mcp.json nel progetto)')}")
    print(f"  {c(BOLD, '3.')} Claude Code — Plugin completo {c(DIM, '(17 skill + 3 agenti + hooks + MCP)')}")
    print(f"  {c(BOLD, '4.')} Desktop + Code MCP server")
    print(f"  {c(BOLD, '5.')} Desktop + Plugin")
    print(f"  {c(BOLD, '6.')} Tutto (Desktop + Code + Plugin)")
    print()

    answer = ask("Scegli", "1")

    target_map = {
        "1": ["desktop"],
        "2": ["code"],
        "3": ["plugin"],
        "4": ["desktop", "code"],
        "5": ["desktop", "plugin"],
        "6": ["desktop", "code", "plugin"],
    }
    return target_map.get(answer, ["desktop"])


def select_plugin_mode(args: argparse.Namespace) -> bool:
    """Select plugin server mode. Returns True for local, False for remote."""
    if args.mode:
        is_local = args.mode == "local"
        label = "locale (stdio)" if is_local else "remoto (SSE)"
        info(f"Modalità plugin: {c(BOLD, label)}")
        return is_local

    if args.non_interactive:
        return True  # default: local

    print()
    print(c(BOLD, "  Modalità server per il plugin:"))
    print()
    print(f"  {c(BOLD, '1.')} Locale {c(DIM, '(stdio — il server gira sulla tua macchina)')}")
    print(f"  {c(BOLD, '2.')} Remoto {c(DIM, '(SSE — connessione al server ngrok)')}")
    print()
    answer = ask("Scegli", "1")
    return answer != "2"


# ---------------------------------------------------------------------------
# Uninstall
# ---------------------------------------------------------------------------

def uninstall() -> None:
    """Remove all legal-it configurations, venv, and cache."""
    banner()
    print(c(BOLD + YELLOW, "  Disinstallazione MCP Legal IT"))
    print()

    removed_any = False

    # 1. Claude Desktop config
    config_path = _CLAUDE_DESKTOP_PATHS.get(platform.system())
    if config_path and config_path.exists():
        try:
            config = json.loads(config_path.read_text())
            servers = config.get("mcpServers", {})
            legal_keys = [k for k in servers if k.startswith("legal-it")]
            if legal_keys:
                for k in legal_keys:
                    del servers[k]
                config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n")
                success(f"Rimossi da Claude Desktop: {', '.join(legal_keys)}")
                removed_any = True
            else:
                info("Nessun server legal-it in Claude Desktop")
        except (json.JSONDecodeError, OSError) as e:
            warn(f"Errore lettura config Claude Desktop: {e}")

    # 2. Claude Code .mcp.json
    if _CLAUDE_CODE_MCP.exists():
        try:
            config = json.loads(_CLAUDE_CODE_MCP.read_text())
            servers = config.get("mcpServers", {})
            legal_keys = [k for k in servers if k.startswith("legal-it")]
            if legal_keys:
                for k in legal_keys:
                    del servers[k]
                if not servers and list(config.keys()) == ["mcpServers"]:
                    _CLAUDE_CODE_MCP.unlink()
                    success("Rimosso .mcp.json (conteneva solo legal-it)")
                else:
                    _CLAUDE_CODE_MCP.write_text(
                        json.dumps(config, indent=2, ensure_ascii=False) + "\n"
                    )
                    success(f"Rimossi da .mcp.json: {', '.join(legal_keys)}")
                removed_any = True
            else:
                info("Nessun server legal-it in .mcp.json")
        except (json.JSONDecodeError, OSError) as e:
            warn(f"Errore lettura .mcp.json: {e}")

    # 3. Plugin + marketplace
    if shutil.which("claude"):
        if _is_plugin_installed():
            info("Rimuovo il plugin Claude Code...")
            result = subprocess.run(
                ["claude", "plugin", "remove", "legal-it"],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0:
                success("Plugin legal-it rimosso")
                removed_any = True
            else:
                warn(f"Errore rimozione plugin: {result.stderr.strip()[:200]}")
        else:
            info("Plugin legal-it non installato")

        # Remove marketplace registration
        info("Rimuovo la registrazione marketplace...")
        result = subprocess.run(
            ["claude", "plugin", "marketplace", "remove", str(PROJECT_DIR)],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            success("Marketplace locale rimosso")
            removed_any = True
        else:
            stderr = result.stderr.strip().lower()
            if stderr and "not found" not in stderr and "not registered" not in stderr:
                warn(f"Rimozione marketplace: {result.stderr.strip()[:200]}")
    else:
        info("CLI claude non trovata, skip rimozione plugin e marketplace")

    # 4. Virtual environment
    if VENV_DIR.exists():
        info(f"Rimuovo il virtual environment: {VENV_DIR.name}/")
        try:
            shutil.rmtree(VENV_DIR)
            success("Virtual environment rimosso")
            removed_any = True
        except OSError as e:
            warn(f"Errore rimozione venv: {e}")
    else:
        info("Nessun virtual environment trovato")

    # 5. Cache
    if CACHE_DIR.exists():
        info(f"Rimuovo la cache: {CACHE_DIR}")
        try:
            shutil.rmtree(CACHE_DIR)
            success("Cache rimossa")
            removed_any = True
        except OSError as e:
            warn(f"Errore rimozione cache: {e}")
    else:
        info("Nessuna cache trovata")

    print()
    if removed_any:
        success("Disinstallazione completa")
    else:
        info("Nessun artefatto legal-it trovato")
    print()


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def summary(profiles: list[str], targets: list[str], tool_count: int) -> None:
    print()
    print(c(DIM, "  " + "-" * 55))
    print()
    print(c(BOLD + GREEN, "  Setup completato!"))
    print()

    # Per-target instructions
    if "desktop" in targets:
        print(f"  {c(BOLD, 'Claude Desktop')}:")
        print("    Riavvia Claude Desktop per attivare i profili.")
        print("    I server appariranno come:")
        for p in profiles:
            print(f"      - {_server_name(p)}")
        print()

    if "code" in targets:
        print(f"  {c(BOLD, 'Claude Code — MCP server')}:")
        print("    Apri una nuova sessione nella cartella del progetto.")
        print("    I tool saranno disponibili automaticamente.")
        print()

    if "plugin" in targets:
        print(f"  {c(BOLD, 'Claude Code — Plugin')}:")
        print("    Il plugin è attivo globalmente in Claude Code.")
        print("    Usa /legal-it:<skill> per i workflow guidati.")
        print("    Agenti disponibili: civilista, penalista, privacy-specialist")
        print()

    # Profiles summary
    print(f"  {c(BOLD, 'Profili installati')}:")
    for p in profiles:
        desc = PROFILES[p]["desc"]
        tools = PROFILES[p]["tools"]
        print(f"    {c(GREEN, p):>25s}  {desc} ({tools} tool)")

    print()
    print(f"  {c(BOLD, 'Tool totali sul server')}: {tool_count}")
    print(f"  {c(BOLD, 'Cache')}: {CACHE_DIR}")
    print()

    # Troubleshooting
    print(c(DIM, "  " + "-" * 55))
    print(c(BOLD, "  Troubleshooting"))
    print()
    print(c(DIM, "  Il server non si avvia?"))
    print(f"    {VENV_PYTHON} {RUN_SERVER}")
    print()
    print(c(DIM, "  Tool non visibili in Claude Code?"))
    print("    Verifica .mcp.json e riavvia la sessione")
    print()
    print(c(DIM, "  Aggiornare o cambiare profili?"))
    print("    python3 install.py")
    print()
    print(c(DIM, "  Disinstallare tutto?"))
    print("    python3 install.py --uninstall")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()

    # Uninstall mode
    if args.uninstall:
        uninstall()
        return

    banner()

    # Step 1: Prerequisites
    check_python()

    # Detect existing installation
    existing = detect_existing_install()
    force_reinstall = False

    if existing["venv"]:
        has_config = existing["desktop"] or existing["code"] or existing["plugin"]
        if has_config:
            warn("Installazione esistente rilevata")
            if not args.non_interactive:
                answer = ask(
                    "Aggiornare dipendenze e riconfigurare (a) o reinstallare da zero (r)?",
                    "a",
                )
                force_reinstall = answer.lower() in ("r", "reinstall")
            # non-interactive: always update (force_reinstall stays False)

    setup_venv(force=force_reinstall)
    install_deps()
    setup_cache()
    tool_count = verify_server()

    # Step 2: Select profiles
    profiles = select_profiles(args)

    # Step 3: Select targets
    targets = select_targets(args)

    # Step 4: Install
    print()
    ok = True
    if "desktop" in targets:
        info("Configuro Claude Desktop...")
        ok = install_claude_desktop(profiles, non_interactive=args.non_interactive) and ok
    if "code" in targets:
        info("Configuro Claude Code (.mcp.json)...")
        ok = install_claude_code(profiles) and ok
    if "plugin" in targets:
        plugin_local = select_plugin_mode(args)
        info("Installo il plugin Claude Code...")
        ok = install_plugin(non_interactive=args.non_interactive, local=plugin_local) and ok

    if not ok:
        print()
        warn("Setup completato con avvisi — controlla i messaggi sopra.")

    # Step 5: Summary
    summary(profiles, targets, tool_count)


if __name__ == "__main__":
    main()

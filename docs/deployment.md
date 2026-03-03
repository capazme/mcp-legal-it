# Deployment — mcp-legal-it

Guida all'installazione e al deployment del server MCP.
Per la configurazione delle variabili d'ambiente e i profili vedere anche
[architecture.md](architecture.md#3-sistema-dei-profili).

---

## Indice

1. [install.py — setup automatico](#1-installpy----setup-automatico)
2. [Setup manuale](#2-setup-manuale)
3. [Docker](#3-docker)
4. [Variabili d'ambiente](#4-variabili-dambiente)
5. [Troubleshooting](#5-troubleshooting)

---

## 1. install.py — setup automatico

`install.py` è lo strumento consigliato per il primo setup. Gestisce:
venv, dipendenze, directory cache, verifica server, e scrittura delle
configurazioni per i target selezionati.

### Flag CLI

```bash
python3 install.py                              # interattivo (default)
python3 install.py -y                           # non-interactive: full profile, target desktop
python3 install.py --profile sinistro           # preseleziona profilo, chiede i target
python3 install.py --target desktop --target code  # preseleziona target (ripetibile)
python3 install.py --profile full --target plugin  # profilo + target senza interazione
python3 install.py --uninstall                  # rimuove tutte le configurazioni legal-it
```

### Profili disponibili

| Profilo | Tool | Descrizione |
|---------|------|-------------|
| `sinistro` | 44 | Danno biologico, rivalutazione, interessi, normativa |
| `credito` | 52 | Interessi mora, decreto ingiuntivo, parcella avvocato |
| `penale` | 16 | Prescrizione, calcolo pena, giurisprudenza |
| `fiscale` | 39 | IRPEF, detrazioni, TFR, successioni, IMU |
| `normativa` | 26 | Testo leggi, sentenze Cassazione, provvedimenti Garante |
| `privacy` | 26 | DPIA, registro trattamenti, data breach, normativa |
| `studio` | 57 | Scadenze, atti giudiziari, parcelle, contributo unificato |
| `full` | 161 | Tutti gli strumenti (consigliato per Claude Code) |

### Target di installazione

| Target | Meccanismo | File modificato |
|--------|-----------|----------------|
| `desktop` | stdio — app locale | `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) |
| `code` | stdio — project-scoped | `.mcp.json` nella root del progetto |
| `plugin` | Claude Code plugin | registrato via `claude plugin install` |

### Flusso di install.py

```
1. check_python()         verifica Python >= 3.10
2. detect_existing_install()  rileva venv e config esistenti
3. setup_venv()           crea .venv/ (o aggiorna se esistente)
4. install_deps()         pip install -e .
5. setup_cache()          crea ~/.cache/mcp-legal-it/
6. verify_server()        avvia il server e conta i tool registrati
7. select_profiles()      prompt interattivo (o --profile)
8. select_targets()       prompt interattivo (o --target)
9. install_*()            scrive le configurazioni JSON
10. summary()             istruzioni post-installazione
```

### Uninstall

```bash
python3 install.py --uninstall
```

Rimuove le chiavi `legal-it*` da Claude Desktop e `.mcp.json`, e disinstalla
il plugin se presente. Il venv (`.venv/`) e la cache (`~/.cache/mcp-legal-it/`)
non vengono rimossi automaticamente.

---

## 2. Setup manuale

### Virtual environment e dipendenze

```bash
python3 -m venv .venv
source .venv/bin/activate          # macOS/Linux
# .venv\Scripts\activate           # Windows

pip install -e .
```

### Claude Desktop — `claude_desktop_config.json`

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
**Linux**: `~/.config/Claude/claude_desktop_config.json`
**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "legal-it": {
      "command": "/path/to/mcp-legal-it/.venv/bin/python",
      "args": ["/path/to/mcp-legal-it/run_server.py"],
      "env": {
        "MCP_CACHE_DIR": "/Users/<user>/.cache/mcp-legal-it"
      }
    },
    "legal-it-privacy": {
      "command": "/path/to/mcp-legal-it/.venv/bin/python",
      "args": ["/path/to/mcp-legal-it/run_server.py"],
      "env": {
        "LEGAL_PROFILE": "privacy",
        "MCP_CACHE_DIR": "/Users/<user>/.cache/mcp-legal-it"
      }
    }
  }
}
```

Riavviare Claude Desktop dopo la modifica.

### Claude Code — `.mcp.json`

Nella root del progetto (`.mcp.json`):

```json
{
  "mcpServers": {
    "legal-it": {
      "command": "/path/to/mcp-legal-it/.venv/bin/python",
      "args": ["/path/to/mcp-legal-it/run_server.py"],
      "env": {
        "MCP_CACHE_DIR": "/Users/<user>/.cache/mcp-legal-it"
      }
    }
  }
}
```

Aprire una nuova sessione Claude Code nella cartella del progetto per attivare.

---

## 3. Docker

### Build e run

```bash
# Build immagine
docker build -t mcp-legal-it .

# Run SSE su porta 8000
docker run -p 8000:8000 mcp-legal-it

# Run con profilo specifico
docker run -p 8000:8000 -e LEGAL_PROFILE=privacy mcp-legal-it

# Run con docker-compose (porta 8000, profilo full, volume cache persistente)
docker compose up

# Background
docker compose up -d
```

### Dockerfile — dettagli

```dockerfile
FROM python:3.12-slim AS base
# Installa gcc + libxml2/libxslt per lxml (compilazione C)
RUN apt-get update && apt-get install -y gcc libxml2-dev libxslt1-dev ...

COPY pyproject.toml .
RUN pip install --no-cache-dir .
COPY src/ src/
COPY run_server.py .

ENV LEGAL_PROFILE=full
ENV MCP_TRANSPORT=sse
ENV MCP_HOST=0.0.0.0
ENV MCP_PORT=8000
ENV MCP_CACHE_DIR=/app/.cache/mcp-legal-it

EXPOSE 8000
CMD ["python", "run_server.py"]
```

### docker-compose.yml

```yaml
services:
  mcp-legal-it:
    build: .
    ports:
      - "8000:8000"
    environment:
      - LEGAL_PROFILE=full
      - MCP_TRANSPORT=sse
    volumes:
      - mcp-cache:/app/.cache/mcp-legal-it
    restart: unless-stopped

volumes:
  mcp-cache:
```

### Configurazione client MCP per SSE

```json
{
  "mcpServers": {
    "legal-it": {
      "url": "http://localhost:8000/sse"
    }
  }
}
```

### Test endpoint SSE

```bash
curl http://localhost:8000/sse
```

---

## 4. Variabili d'ambiente

| Variabile | Default | Descrizione |
|-----------|---------|-------------|
| `MCP_TRANSPORT` | `stdio` | Transport: `stdio` (Claude Desktop/Code) o `sse` (Docker/remoto) |
| `MCP_HOST` | `0.0.0.0` | Bind address — solo per transport SSE |
| `MCP_PORT` | `8000` | Porta HTTP — solo per transport SSE |
| `MCP_PATH_PREFIX` | *(vuoto)* | Path prefix per reverse proxy (es. `/legal-it`). Imposta automaticamente `FASTMCP_SSE_PATH` e `FASTMCP_MESSAGE_PATH`. |
| `LEGAL_PROFILE` | `full` | Profilo tool: `full`, `sinistro`, `credito`, `penale`, `fiscale`, `normativa`, `privacy`, `studio` |
| `MCP_CACHE_DIR` | `~/.cache/mcp-legal-it` | Directory per la cache persistente degli URL Brocardi |

---

## 5. Troubleshooting

### Il server non si avvia

```bash
# Test diretto
.venv/bin/python run_server.py

# Verifica import
.venv/bin/python -c "from src.server import mcp; print('OK')"
```

Errori comuni:
- `ModuleNotFoundError: fastmcp` → dipendenze non installate → `pip install -e .`
- `ImportError` su `lxml` → librerie C mancanti → `apt install libxml2-dev libxslt1-dev` (Linux)

### Tool non visibili in Claude Code

1. Verificare che `.mcp.json` sia nella root del progetto
2. Verificare il percorso assoluto di `VENV_PYTHON` e `run_server.py`
3. Aprire una **nuova** sessione Claude Code (non ricaricare quella esistente)
4. Controllare i log MCP: in Claude Code usa `/mcp` per vedere lo stato dei server

### Errori SSL con Italgiure

Normale — il sito `italgiure.giustizia.it` ha un certificato SSL non valido.
Il client usa `verify=False` per default. Non è configurabile.

### Cache Brocardi non funziona

Verificare che `MCP_CACHE_DIR` punti a una directory scrivibile:
```bash
ls -la ~/.cache/mcp-legal-it/
# oppure, se configurato diversamente:
ls -la $MCP_CACHE_DIR
```

### Aggiornare i profili senza reinstallare

```bash
python3 install.py --profile full --target desktop
# oppure interattivo:
python3 install.py
```

`install.py` sovrascrive le configurazioni esistenti mantenendo il venv.

### Disinstallare completamente

```bash
python3 install.py --uninstall
rm -rf .venv/
rm -rf ~/.cache/mcp-legal-it/
```

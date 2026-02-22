# Contribuire a mcp-legal-it

## 1. Setup ambiente

```bash
git clone <repo-url>
cd mcp-legal-it
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest  # deve passare tutto
```

---

## 2. Aggiungere un tool di calcolo (no HTTP)

Il caso più semplice: il tool riceve parametri, calcola, restituisce una stringa o un dict.

**Passaggi:**

1. Scegli il modulo in `src/tools/` in base alla categoria (es. `varie.py` per calcoli generali)
2. Aggiungi la funzione con il decorator `@mcp.tool()` e una docstring chiara per l'LLM
3. Nessuna modifica a `server.py` se il modulo esiste già

**Esempio:**

```python
# In src/tools/varie.py

@mcp.tool()
def calcola_interessi_legali(
    capitale: float,
    tasso_pct: float,
    giorni: int,
) -> dict:
    """Calcola gli interessi legali su un capitale per un numero di giorni.

    Vigenza: tasso legale ex art. 1284 c.c., aggiornato annualmente con DM MEF.
    Precisione: ESATTO (formula matematica).

    Args:
        capitale: Importo in euro su cui calcolare gli interessi
        tasso_pct: Tasso annuo percentuale (es. 5.0 per il 5%)
        giorni: Numero di giorni del periodo
    """
    interessi = capitale * (tasso_pct / 100) * (giorni / 365)
    return {
        "capitale": capitale,
        "tasso_pct": tasso_pct,
        "giorni": giorni,
        "interessi": round(interessi, 2),
        "totale": round(capitale + interessi, 2),
    }
```

> Se la logica è complessa e vuoi testarla separatamente senza dipendere dal metaclass MCP,
> estraila in una funzione `_nome_tool_impl(...)` che il wrapper chiama. Vedi sezione 3.

---

## 3. Aggiungere un tool con chiamata HTTP

I tool che fanno scraping o chiamano API esterne seguono il pattern `_impl` + wrapper.

**Struttura del client** (`src/lib/<nome>/client.py`):

- Costanti di configurazione in cima (URL base, timeout, header)
- Funzioni pure: `build_params(...)`, `parse_response(...)`, `format_result(...)`
- Una funzione async per la chiamata HTTP che usa `httpx.AsyncClient`
- Nessuna logica di business nel client — solo I/O e parsing

**Re-export** in `src/lib/<nome>/__init__.py`.

**Nel modulo tools** — pattern `_impl` + wrapper:

```python
# In src/tools/nuovo_modulo.py

from src.server import mcp
from src.lib.nuovo.client import fetch_data, format_result


async def _cerca_qualcosa_impl(query: str, max_risultati: int = 10) -> str:
    try:
        items = await fetch_data(query=query, rows=max_risultati)
    except Exception as exc:
        return f"Errore nella ricerca: {exc}"

    if not items:
        return f"Nessun risultato per: _{query}_"

    lines = [f"**Trovati {len(items)} risultati per**: _{query}_\n"]
    for item in items:
        lines.append(format_result(item))
        lines.append("")
    return "\n".join(lines)


@mcp.tool()
async def cerca_qualcosa(query: str, max_risultati: int = 10) -> str:
    """Descrizione breve per l'LLM — quando usare questo tool.

    Args:
        query: Testo da cercare
        max_risultati: Numero massimo di risultati (default 10, max 50)
    """
    return await _cerca_qualcosa_impl(query=query, max_risultati=max_risultati)
```

**Se il modulo è nuovo** (nuova categoria), aggiorna `src/server.py`:

```python
from src.tools import (
    ...
    nuovo_modulo,  # aggiungere qui
)
```

E aggiorna il campo `instructions` in `server.py` per includere i nuovi tool nella lista.

---

## 4. Scrivere i test

### Tool di calcolo (no HTTP)

Test diretti sulla funzione `@mcp.tool()` — oppure sulla `_impl` se esiste:

```python
import pytest
from src.tools.varie import calcola_interessi_legali

def test_interessi_legali_base():
    result = calcola_interessi_legali(1000.0, 5.0, 365)
    assert result["interessi"] == 50.0
    assert result["totale"] == 1050.0

def test_interessi_legali_periodo_parziale():
    result = calcola_interessi_legali(1000.0, 10.0, 182)
    assert "interessi" in result
```

### Tool con HTTP (mock httpx)

Importa sempre le funzioni `_impl` a livello di modulo — non dentro la funzione di test:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Import a livello modulo per evitare conflitti con il metaclass MCP
from src.tools.nuovo_modulo import _cerca_qualcosa_impl


def _mock_response(html: str, status: int = 200):
    resp = MagicMock()
    resp.status_code = status
    resp.text = html
    resp.raise_for_status = MagicMock()
    return resp


@pytest.mark.asyncio
async def test_cerca_qualcosa_ok():
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.get = AsyncMock(return_value=_mock_response("<html>...</html>"))

    with patch("src.lib.nuovo.client.httpx.AsyncClient", return_value=mock_client):
        result = await _cerca_qualcosa_impl("test")

    assert "Trovati" in result


@pytest.mark.asyncio
async def test_cerca_qualcosa_http_error():
    import httpx
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.get = AsyncMock(side_effect=httpx.RequestError("timeout"))

    with patch("src.lib.nuovo.client.httpx.AsyncClient", return_value=mock_client):
        result = await _cerca_qualcosa_impl("test")

    assert "Errore" in result
```

### Test live (richiedono internet)

Marca con `@pytest.mark.live` ed esegui solo manualmente:

```python
@pytest.mark.live
async def test_ricerca_reale():
    result = await _cerca_qualcosa_impl("GDPR")
    assert "Trovati" in result
```

Esecuzione: `pytest -m live`

---

## 5. Aggiungere un prompt

In `src/prompts.py`, aggiungi tramite il decorator `@mcp.prompt()`. Segui il pattern degli altri prompt già presenti nel file.

---

## 6. Aggiungere una risorsa statica

In `src/resources.py`, aggiungi tramite `@mcp.resource()` con URI nel formato `legal://riferimenti/<nome>`. Le risorse sono stringhe markdown — tabelle, checklist, schemi.

---

## 7. Convenzioni

| Aspetto | Regola |
|---|---|
| Funzioni `_impl` | Sempre prefisso underscore, suffisso `_impl`; sempre `async` anche se non fanno I/O |
| Output | Mai `print()` — restituire sempre la stringa o il dict |
| Importi | `€ 1.234,56` (punto migliaia, virgola decimale) |
| Date | `GG/MM/AAAA` |
| Precisione | Indicare sempre se il risultato è ESATTO o INDICATIVO nella docstring |
| Dipendenze | Non aggiungere pacchetti senza consenso — `httpx`, `beautifulsoup4`, `lxml`, `fpdf2` sono già disponibili |

---

## 8. Checklist prima di aprire una PR

- [ ] `pytest` passa completamente (senza `-m live`)
- [ ] I nuovi tool hanno docstring con sezione `Args:` e nota su vigenza/precisione
- [ ] Le funzioni `_impl` hanno test dedicati con mock httpx
- [ ] Se è un modulo nuovo, `server.py` è aggiornato (import + instructions)
- [ ] L'output rispetta le convenzioni (importi, date, ESATTO/INDICATIVO)

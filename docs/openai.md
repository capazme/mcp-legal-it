# Bundle OpenAI (Codex CLI / ChatGPT)

> Guida all'installazione delle skill Legal IT e del server MCP su Codex CLI
> e ChatGPT, tramite il bundle `legal-it-openai-skills-X.Y.Z.zip` allegato a
> ogni [GitHub Release](https://github.com/capazme/mcp-legal-it/releases/latest).

## Cosa contiene il bundle

Il bundle è generato da `python scripts/build_targets.py openai openai-zip`
a partire dallo stesso corpus (`content/`) da cui viene proiettato il plugin
Claude Code — non è un prodotto separato mantenuto a mano. Contiene:

- **`.agents/skills/`** — 40 skill in formato SKILL.md (28 skill del corpus +
  6 skill derivate dagli agenti specialisti + 6 derivate dagli slash command;
  `cookie-audit` ed `esporta-documento` sono escluse — la prima perché il suo
  workflow pilota tool browser specifici di Claude, la seconda perché il suo
  corpo cita percorsi `${CLAUDE_PLUGIN_ROOT}`, non risolvibili fuori da un
  processo plugin Claude — entrambe non funzionerebbero fuori da
  quell'ambiente). Ogni
  `SKILL.md` ha un frontmatter ridotto a `name` + `description` (Codex tollera
  chiavi extra ma non le richiede); i tool nel corpo sono citati con il nome
  **bare** (es. `cite_law`, non `mcp__legal_it__cite_law`) — l'unica forma
  stabile su entrambe le modalità di naming di Codex, vedi sotto.
- **`AGENTS.md`** — protocollo di grounding legale e le regole operative del
  server, estratte dalle istruzioni del server MCP stesso (fonte unica,
  nessuna duplicazione manuale).
- **`config.toml.example`** — blocco di configurazione MCP per Codex, variante
  stdio (via `uv`, nessuna installazione locale) e variante Streamable HTTP
  commentata.
- **`README.md`** — riepilogo rapido dentro al bundle stesso.

Dei 8 slash command del plugin Claude Code solo 6 diventano skill: i comandi
`release` e `digest` — maintainer-only e legati allo scheduling dell'harness —
sono esclusi, come `cookie-audit` ed `esporta-documento`.

Il bundle **non include il server MCP**: le skill sono istruzioni per
l'agente, il server (218 tool) resta un checkout separato di questo repository
o un endpoint remoto — vedi «Server MCP» sotto.

> Nota sui numeri: prompt MCP (23) e risorse `legal://` (15) restano feature
> Claude-only (vedi tabella di compatibilità in `CLAUDE.md`). Il bundle porta
> le skill fuori da Claude; non porta prompt né risorse, perché Codex e
> ChatGPT non hanno un equivalente di questi due meccanismi MCP.

---

## Installazione — Codex CLI

Tre vie, in ordine di comodità:

1. **Unzip del bundle (consigliato)** — scarica
   `legal-it-openai-skills-X.Y.Z.zip` dall'ultima Release, estrai
   `.agents/skills/` in:
   - `$HOME/.agents/skills/` per renderle disponibili in **ogni** progetto
     aperto con Codex, oppure
   - `.agents/skills/` nella root del progetto su cui lavori, se vuoi che
     restino locali a quel progetto.
   Copia anche `AGENTS.md` (vedi sezione dedicata) e usa
   `config.toml.example` per il server MCP.
2. **Clone + copia dal corpus** — chi lavora già su un checkout di
   `mcp-legal-it` può rigenerare il bundle in locale invece di scaricare
   l'artifact:
   ```bash
   uv run --python 3.12 --extra dev python scripts/build_targets.py openai
   cp -r dist/openai/.agents/skills/. ~/.agents/skills/
   ```
3. **Skill-installer** — Codex ha in programma un meccanismo di installazione
   guidato delle skill (analogo a `codex mcp add` per i server MCP); finché
   non è disponibile, le prime due vie restano quelle supportate.

### Dove Codex cerca le skill

Codex cerca in quest'ordine la directory `.agents/skills`:

```
$CWD/.agents/skills → directory padri, risalendo → root del repository
  → $HOME/.agents/skills → /etc/codex/skills → skill incluse in Codex stesso
```

se più directory sono presenti, verifica quale copia viene effettivamente
caricata (con `/mcp` o l'equivalente diagnostica di Codex): se hai bisogno di
skill diverse per progetti diversi, usa la copia locale al progetto.

Le 40 skill del bundle restano ampiamente sotto il budget che Codex riserva
alla lista delle skill nel contesto (2% del contesto disponibile, o 8.000
caratteri se il contesto non è noto): le descrizioni sono tagliate in fase di
build a 185 caratteri, e il totale nome+descrizione dell'intero bundle è
verificato in test a restare sotto la soglia degli 8.000 caratteri, così
Codex non deve mai scartare o troncare silenziosamente una skill.

---

## Server MCP — `config.toml`

Aggiungi il blocco di `config.toml.example` al tuo `~/.codex/config.toml`
(oppure usa `codex mcp add`), sostituendo il placeholder del percorso con un
checkout reale del server:

```toml
[mcp_servers.legal_it]
command = "uv"
args = [
  "run", "--python", "3.12",
  "--with", "fastmcp>=2.0,<4",
  "--with", "httpx>=0.27",
  "--with", "beautifulsoup4>=4.12",
  "--with", "lxml>=5.0",
  "--with", "fpdf2>=2.7",
  "--with", "python-docx>=1.0",
  "--with", "openpyxl>=3.1",
  "--with", "cryptography<49; sys_platform == 'darwin' and platform_machine == 'x86_64'",
  "/path/to/mcp-legal-it/plugin/server/run_server.py",
]
```

Oppure, per non lanciare `uv` in locale, la variante server remoto
(Streamable HTTP) già commentata in `config.toml.example`:

```toml
[mcp_servers.legal_it]
url = "https://<il-tuo-host>/mcp"
```

### Il nome del server DEVE essere `legal_it` (underscore, non trattino)

Non è un dettaglio estetico: Codex non espone i tool di un server MCP il cui
nome contiene un trattino — la lista tool risulta vuota (`Tools: (none)`),
anche se il server è connesso e funzionante (Codex issue #15832). Per questo
il bundle chiama il server `legal_it` e non `legal-it` (come invece fa il
plugin Claude Code, dove il nome con trattino è innocuo).

---

## `AGENTS.md`

`AGENTS.md` va posizionato in uno di questi due punti:

- **`~/.codex/AGENTS.md`** — regole valide per ogni progetto (globale);
- **root del progetto su cui lavori** (`AGENTS.md` accanto a `.git/`) — regole
  specifiche a quel progetto.

Codex concatena i file `AGENTS.md` trovati risalendo dalla root fino alla
directory di lavoro corrente, fino a un tetto complessivo di 32 KiB — il file
generato da questo bundle (poche migliaia di byte) ci sta con ampio margine
anche insieme ad altri `AGENTS.md` di progetto.

Il file generato contiene: lo scope del server (strumenti legali italiani via
MCP `legal_it`), il **Legal Grounding Protocol** (quando usare `cite_law()`,
quando `leggi_sentenza()` diretto, quando prima `cerca_*` poi `leggi_*`, quali
tool numerici non richiedono verifica), e le regole REGOLE/OUTPUT/WORKFLOW
estratte dalle istruzioni del server stesso — se il server cambia le sue
regole, `AGENTS.md` si rigenera insieme, non va mantenuto a mano.

---

## ChatGPT

ChatGPT non è un client MCP completo come Codex: skill e tool arrivano per
due vie separate.

- **Skill** — si caricano manualmente nella **Skills UI** di ChatGPT: il
  caricamento di skill "costruite per o esportate da Claude Code" è un caso
  d'uso esplicitamente supportato dal formato SKILL.md. Carica il contenuto
  di `.agents/skills/` da lì (o l'intero bundle via Plugin Directory, dove
  applicabile).
- **Tool MCP** — servono un endpoint HTTPS pubblico: ChatGPT si collega via
  connector in **Developer Mode** (Settings → Apps → Developer Mode → Create)
  a un server self-hosted (Docker, `MCP_TRANSPORT=http`) — vedi le opzioni di
  deploy già documentate in `CLAUDE.md` (sezione "Setup 3 — ChatGPT").

ChatGPT **non** supporta prompt MCP né risorse MCP: solo i tool del server
sono visibili una volta collegato il connector, indipendentemente dal bundle.

---

## Limiti del bundle (rispetto al plugin Claude Code)

Il bundle porta fuori da Claude solo ciò che Codex e ChatGPT sanno leggere:

- **Niente prompt MCP** (i 23 prompt guidati restano Claude-only — Codex e
  ChatGPT non hanno un concetto di "prompt MCP" richiamabile dall'utente).
- **Niente risorse `legal://`** (le 15 risorse statiche restano Claude-only).
- **Niente hook** — il plugin Claude Code applica il Legal Grounding
  Protocol anche via hook automatico (Stop hook che verifica le citazioni a
  fine risposta). Fuori da Claude non esiste un meccanismo equivalente:
  il gate citazioni diventa **disciplina scritta** in `AGENTS.md` (che
  l'agente deve seguire per istruzione, non per enforcement automatico) più
  il tool `verifica_citazioni`, che l'agente può invocare esplicitamente per
  controllare che le citazioni presenti in un testo abbiano un riscontro
  verificabile. È un controllo disponibile su richiesta, non un gate
  automatico.

---

## Verifica dell'installazione

In Codex CLI, digita `/mcp`: deve comparire il server `legal_it` con la sua
lista di tool (218, meno quelli esclusi dal profilo se ne usi uno ridotto via
`LEGAL_PROFILE`). Se la lista risulta **vuota** (`Tools: (none)`), la causa
quasi sempre è il nome del server nel `config.toml`: controlla che sia
`legal_it` con l'underscore, non `legal-it` (vedi sopra, issue #15832).

Nota sui nomi dei tool: a seconda della modalità di naming MCP attiva in
Codex, i tool compaiono come `legal_it__<nome>` oppure
`mcp__legal_it__<nome>` (le due modalità coesistono a seconda della versione
di Codex — PR #21576). Nei testi delle skill e in `AGENTS.md` i tool sono
sempre citati con il **nome bare** (`cite_law`, `leggi_sentenza`, ...): è
l'unica forma che resta corretta sotto entrambe le modalità.

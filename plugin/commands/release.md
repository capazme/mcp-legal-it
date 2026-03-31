---
name: release
description: Prepara e pubblica una nuova release del plugin mcp-legal-it. Bumpa la versione in tutti i manifest, aggiorna i changelog e la description con il conteggio tool corretto, crea il release branch, merge in main e tagga.
argument-hint: "<versione> (es. 2.4.0)"
allowed-tools: Bash, Read, Edit, Write, Grep, Glob
---

# Comando /release

> **Alternativa automatizzata**: `python3 release.py --from-develop` esegue tutti questi
> step con bump automatico di tutti i 6 manifest, conteggio tool, verifica pre-tag e rollback
> in caso di errore. Usalo se possibile.

Segui questi step ESATTAMENTE nell'ordine indicato. Non saltare nessun passaggio.

## Step 1 — Determina la versione

L'utente fornisce la versione target (es. `2.4.0`). Se non la fornisce, leggi la versione attuale da `pyproject.toml` e proponi il bump appropriato:
- PATCH (Z+1): bug fix, aggiornamento dati
- MINOR (Y+1): nuovi tool, nuove feature
- MAJOR (X+1): breaking change nelle API dei tool

## Step 2 — Conta i tool attuali

```bash
grep -c "@mcp.tool" plugin/server/src/tools/*.py | awk -F: '{sum+=$2} END {print sum}'
```

Salva il numero — serve per aggiornare le description.

## Step 3 — Verifica test

```bash
.venv/bin/pytest tests/unit/ -q --tb=short
```

Se ci sono fallimenti, STOP. Non procedere con la release.

## Step 4 — Crea release branch

```bash
git checkout develop
git pull origin develop
git checkout -b release/X.Y.Z
```

## Step 5 — Bumpa la versione in TUTTI i 6 file

Sostituisci la versione precedente con la nuova in OGNUNO di questi file:

1. `pyproject.toml` → `version = "X.Y.Z"`
2. `plugin/server/pyproject.toml` → `version = "X.Y.Z"`
3. `dxt/manifest.json` → `"version": "X.Y.Z"`
4. `plugin/server/manifest.json` → `"version": "X.Y.Z"`
5. `plugin/.claude-plugin/plugin.json` → `"version": "X.Y.Z"`
6. `.claude-plugin/marketplace.json` → `"version": "X.Y.Z"` (dentro `plugins[0]`)

## Step 6 — Aggiorna le description con il conteggio tool corretto

Aggiorna il numero di tool nelle description di questi 4 file (usa il conteggio dello Step 2):

1. `dxt/manifest.json` → campo `"description"` e `"long_description"`
2. `plugin/server/manifest.json` → campo `"description"`
3. `plugin/.claude-plugin/plugin.json` → campo `"description"`
4. `.claude-plugin/marketplace.json` → campo `"description"` dentro `plugins[0]`

## Step 7 — Aggiorna i changelog

Aggiungi una entry `## [X.Y.Z] - YYYY-MM-DD` in testa a entrambi:

1. `CHANGELOG.md` (root) — dettagliato, con tutte le modifiche
2. `plugin/CHANGELOG.md` — prospettiva plugin, abbreviato

Contenuto minimo della entry:
- Nuovi tool aggiunti (con nome e descrizione breve)
- Bug fix
- Aggiornamenti dati (TEGM, FOI, ecc.)
- Breaking change (se MAJOR)

## Step 8 — Commit e push

```bash
git add -A
git commit -m "chore: bump all manifests to vX.Y.Z"
git push -u origin release/X.Y.Z
```

## Step 9 — Verifica pre-tag (GATE OBBLIGATORIO)

**Prima di taggare**, verifica che TUTTI i 6 file abbiano la versione corretta E le description aggiornate:

```bash
# Versione in tutti i manifest
echo "--- Versioni ---"
grep -m1 'version' pyproject.toml
grep -m1 'version' plugin/server/pyproject.toml
python3 -c "import json; print('dxt:', json.load(open('dxt/manifest.json'))['version'])"
python3 -c "import json; print('server:', json.load(open('plugin/server/manifest.json'))['version'])"
python3 -c "import json; print('plugin:', json.load(open('plugin/.claude-plugin/plugin.json'))['version'])"
python3 -c "import json; d=json.load(open('.claude-plugin/marketplace.json')); print('marketplace:', d['plugins'][0]['version'])"

# Tool count nelle description
echo "--- Tool count ---"
EXPECTED=$(grep -c "@mcp.tool" src/tools/*.py | awk -F: '{sum+=$2} END {print sum}')
echo "Attesi: $EXPECTED tool"
grep -o '[0-9]* tool' plugin/.claude-plugin/plugin.json
grep -o '[0-9]* tool' .claude-plugin/marketplace.json
```

Se una versione non corrisponde o il conteggio tool è sbagliato, correggi PRIMA di procedere.
Il tag DEVE puntare a un commit dove tutti i manifest sono allineati.

## Step 10 — Merge in main e tag

```bash
git checkout main
git pull origin main
git merge --no-ff release/X.Y.Z -m "Merge release/X.Y.Z into main"
git tag vX.Y.Z
git push origin main --tags
```

## Step 11 — Sync develop e pulizia

```bash
git checkout develop
git merge main -m "Merge main into develop (vX.Y.Z release)"
git push origin develop
git branch -d release/X.Y.Z
```

## Step 12 — Verifica release

```bash
gh run list --limit 1
```

Attendi che il workflow "Build & Release" completi. Verifica:
```bash
gh release view vX.Y.Z --json assets --jq '.assets[].name'
```

Deve mostrare `legal-it-X.Y.Z.mcpb` e `legal-it-plugin-X.Y.Z.zip`.

## Checklist finale

- [ ] 6 file con versione bumpata
- [ ] 4 description con conteggio tool aggiornato
- [ ] 2 changelog aggiornati
- [ ] Test tutti verdi
- [ ] **Pre-tag gate**: tutti i manifest verificati (Step 9) ← CRITICO
- [ ] Tag pushato
- [ ] GitHub Release con 2 asset (.mcpb + .zip)
- [ ] marketplace.json su main con versione e description corrette

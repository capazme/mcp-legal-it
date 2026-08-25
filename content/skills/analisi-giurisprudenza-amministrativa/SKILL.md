---
name: analisi-giurisprudenza-amministrativa
description: Usa quando l'utente chiede sentenze TAR o CdS su appalti, urbanistica, edilizia, accesso agli atti o Adunanza Plenaria — ricerca TAR/Consiglio di Stato, lettura dei provvedimenti e sintesi.
tools: [cerca_giurisprudenza_amministrativa, cite_law, giurisprudenza_amm_su_norma, leggi_provvedimento_amm]
prompt: {"name": "analisi_giurisprudenza_amministrativa", "description": "Analisi giurisprudenza amministrativa: ricerca TAR/CdS, lettura provvedimenti e sintesi orientamenti", "args": [{"name": "tema", "type": "str"}, {"name": "sede", "type": "str", "default": ""}]}
---

# Analisi Giurisprudenza Amministrativa

Esegui un'analisi della giurisprudenza amministrativa sul tema indicato.

## Dati richiesti

- **tema** — il tema amministrativo da analizzare. Se non fornito, chiedilo.
- **sede** (opzionale) — filtro sede: consiglio_di_stato / tar_lazio / tar_lombardia / ...

## Workflow

### Fase 1 — Ricerca provvedimenti
Chiama `cerca_giurisprudenza_amministrativa(query=<tema>)` — aggiungi `sede=<sede>` se indicato — per trovare
sentenze e provvedimenti di TAR e Consiglio di Stato.

### Fase 2 — Lettura provvedimenti chiave
Seleziona i 2-3 provvedimenti più significativi (privilegia CdS e Adunanza Plenaria).
Per ciascuno, chiama `leggi_provvedimento_amm(sede, nrg, nome_file)` per il testo completo.

### Fase 3 — Giurisprudenza su norma (se pertinente)
Se il tema ruota attorno a una norma specifica, chiama
`giurisprudenza_amm_su_norma(riferimento="art. ...")` per trovare decisioni che la citano.

### Fase 4 — Quadro normativo
Per le norme citate nelle sentenze, chiama `cite_law(reference)` per il testo vigente.
Fonti tipiche: CPA (D.Lgs. 104/2010), D.Lgs. 36/2023 (Codice Appalti), TUEL (D.Lgs. 267/2000),
L. 241/1990, DPR 380/2001 (TU Edilizia).

### Fase 5 — Sintesi

## Analisi Giurisprudenza Amministrativa: <tema>

### 1. Orientamento Prevalente
Principio di diritto che emerge dalle sentenze esaminate.

### 2. Provvedimenti Esaminati
| Provvedimento | Sede | Data | Principio |
|---------------|------|------|-----------|
| ... | ... | ... | ... |

### 3. Adunanza Plenaria / Sezioni Unite
Se si è pronunciata l'Adunanza Plenaria, riportare il principio di diritto.

### 4. Quadro Normativo
Norme amministrative rilevanti con testo da cite_law.

### 5. Indicazioni Operative
Raccomandazioni pratiche per il ricorrente/PA.

## Regole

- Usare `cerca_giurisprudenza_amministrativa` e `leggi_provvedimento_amm` per i provvedimenti.
- Usare `cite_law` per TUTTE le norme citate.
- Non citare mai numeri di sentenza a memoria.

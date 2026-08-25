---
name: analisi-tributaria
description: Usa quando l'utente chiede giurisprudenza tributaria, sentenze su IVA, IRES, accertamento, riscossione o contenzioso CGT — ricerca CeRDEF, lettura dei provvedimenti chiave e sintesi con quadro normativo.
tools: [cerca_giurisprudenza, cerca_giurisprudenza_tributaria, cerdef_leggi_provvedimento, cite_law]
prompt: {"name": "analisi_tributaria", "description": "Analisi giurisprudenza tributaria: ricerca CeRDEF, lettura provvedimenti e sintesi orientamenti fiscali", "args": [{"name": "tema", "type": "str"}, {"name": "ente", "type": "str", "default": ""}]}
---

# Analisi Tributaria

Esegui un'analisi della giurisprudenza tributaria sul tema indicato.

## Dati richiesti

- **tema** — il tema fiscale da analizzare. Se non fornito, chiedilo.
- **ente** (opzionale) — filtro ente: corte_suprema / cgt_primo_grado / cgt_secondo_grado.

## Workflow

### Fase 1 — Ricerca CeRDEF
Chiama `cerca_giurisprudenza_tributaria(query=<tema>)` — aggiungi `ente=<ente>` se indicato — per trovare
sentenze e provvedimenti nella banca dati del MEF.

### Fase 2 — Lettura provvedimenti chiave
Seleziona i 2-3 provvedimenti più significativi (privilegia Cassazione se presente).
Per ciascuno, chiama `cerdef_leggi_provvedimento(guid)` per leggere massima e testo completo.

### Fase 3 — Quadro normativo
Per le norme tributarie citate nelle sentenze, chiama `cite_law(reference)` per il testo vigente.
Fonti tipiche: TUIR (DPR 917/1986), D.Lgs. 546/1992, DPR 633/1972 (IVA), D.Lgs. 472/1997.

### Fase 4 — Giurisprudenza Cassazione (se pertinente)
Se emergono principi di diritto rilevanti, cerca anche su Italgiure:
`cerca_giurisprudenza(query="\"<tema>\"", archivio="civile")` per sezione tributaria.

### Fase 5 — Sintesi

## Analisi Giurisprudenza Tributaria: <tema>

### 1. Orientamento Prevalente
Principio di diritto che emerge dalle sentenze esaminate.

### 2. Provvedimenti Esaminati
| Provvedimento | Ente | Data | Principio |
|---------------|------|------|-----------|
| ... | ... | ... | ... |

### 3. Quadro Normativo
Norme tributarie rilevanti con testo da cite_law.

### 4. Indicazioni Operative
Raccomandazioni pratiche per il contribuente/professionista.

## Regole

- Usare `cerca_giurisprudenza_tributaria` e `cerdef_leggi_provvedimento` per i provvedimenti CeRDEF.
- Usare `cite_law` per TUTTE le norme citate.
- Non citare mai numeri di sentenza o GUID a memoria.

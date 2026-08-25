---
name: analisi-tributaria
description: Usa quando l'utente chiede giurisprudenza tributaria, sentenze su IVA, IRES, accertamento, riscossione o contenzioso CGT — ricerca CeRDEF, lettura dei provvedimenti chiave e sintesi con quadro normativo.
---

# Analisi Tributaria

Esegui un'analisi della giurisprudenza tributaria sul tema indicato.

## Dati richiesti

- **tema** — il tema fiscale da analizzare. Se non fornito, chiedilo.
- **ente** (opzionale) — filtro ente: corte_suprema / cgt_primo_grado / cgt_secondo_grado.

## Workflow

### Fase 1 — Ricerca CeRDEF
Chiama `legal-it:cerca_giurisprudenza_tributaria(query=<tema>)` — aggiungi `ente=<ente>` se indicato — per trovare
sentenze e provvedimenti nella banca dati del MEF.

### Fase 2 — Lettura provvedimenti chiave
Seleziona i 2-3 provvedimenti più significativi (privilegia Cassazione se presente).
Per ciascuno, chiama `legal-it:cerdef_leggi_provvedimento(guid)` per leggere massima e testo completo.

### Fase 3 — Quadro normativo
Per le norme tributarie citate nelle sentenze, chiama `legal-it:cite_law(reference)` per il testo vigente.
Fonti tipiche: TUIR (DPR 917/1986), D.Lgs. 546/1992, DPR 633/1972 (IVA), D.Lgs. 472/1997.

### Fase 4 — Giurisprudenza Cassazione (se pertinente)
Se emergono principi di diritto rilevanti, cerca anche su Italgiure:
`legal-it:cerca_giurisprudenza(query="\"<tema>\"", archivio="civile")` per sezione tributaria.

### Fase 5 — Sintesi

## Analisi Giurisprudenza Tributaria: <tema>

### 1. Orientamento Prevalente
Principio di diritto che emerge dalle sentenze esaminate.

### 2. Provvedimenti Esaminati
| Provvedimento | Ente | Data | Principio |
|---------------|------|------|-----------|
| ... | ... | ... | ... |

### 3. Quadro Normativo
Norme tributarie rilevanti con testo da legal-it:cite_law.

### 4. Indicazioni Operative
Raccomandazioni pratiche per il contribuente/professionista.

## Regole

- Usare `legal-it:cerca_giurisprudenza_tributaria` e `legal-it:cerdef_leggi_provvedimento` per i provvedimenti CeRDEF.
- Usare `legal-it:cite_law` per TUTTE le norme citate.
- Non citare mai numeri di sentenza o GUID a memoria.

---
name: analisi-giurisprudenza-europea
description: Usa quando l'utente chiede sentenze CGUE, rinvio pregiudiziale, interpretazione di direttive o regolamenti UE o conclusioni dell'Avvocato generale — ricerca CGUE/Tribunale UE, lettura e sintesi.
tools: [cerca_giurisprudenza_cgue, cite_law, giurisprudenza_cgue_su_norma, leggi_sentenza_cgue]
prompt: {"name": "analisi_giurisprudenza_europea", "description": "Analisi giurisprudenziale europea strutturata: ricerca CGUE/Tribunale UE, lettura sentenze chiave e sintesi orientamenti", "args": [{"name": "tema", "type": "str"}, {"name": "corte", "type": "str", "default": "tutte"}]}
---

# Analisi Giurisprudenza Europea

Esegui un'analisi giurisprudenziale strutturata sulla Corte di Giustizia UE per il tema indicato.

## Dati richiesti

- **tema** — il tema di diritto UE da analizzare. Se non fornito, chiedilo.
- **corte** (opzionale, default `tutte`) — filtro corte: tutte / corte_di_giustizia / tribunale.

## Workflow

### Fase 1 — Ricerca sentenze
Chiama `cerca_giurisprudenza_cgue(query=<tema>, corte=<corte>)`
per trovare le sentenze CGUE pertinenti.

Se il tema riguarda una norma specifica del diritto UE (es. "art. 101 TFUE", "art. 7 GDPR"),
chiama `giurisprudenza_cgue_su_norma(riferimento="art. ... norma")` per trovare le decisioni
che interpretano quella norma.

### Fase 1b — Filtraggio per materia
Se il tema rientra in una delle materie predefinite (iva, concorrenza, ambiente, lavoro,
protezione_dati, appalti, consumatori), aggiungi il parametro materia alla ricerca per
ottenere risultati più mirati.

### Fase 2 — Lettura sentenze chiave
Seleziona le 2-3 sentenze più significative dalla ricerca.
Per ciascuna, chiama `leggi_sentenza_cgue(cellar_uri)` con il CELLAR URI riportato nel risultato.

Privilegia:
- Sentenze della Grande Sezione (massima autorità interpretativa)
- Sentenze recenti (ultimi 3 anni)
- Sentenze che citano principi generali del diritto UE

IMPORTANTE: usa `leggi_sentenza_cgue` con il CELLAR URI — NON usare EUR-Lex (ha WAF).

### Fase 3 — Fondamento normativo
Per le norme UE citate nelle sentenze lette, chiama `cite_law(reference)` per verificare
il testo vigente dalla fonte ufficiale. Fonti tipiche:
- TFUE: "art. 101 TFUE", "art. 267 TFUE" (rinvio pregiudiziale)
- Regolamenti UE: "Reg. UE 2016/679 art. 5" (GDPR), "Reg. UE 596/2014 art. 7" (MAR)
- Direttive: cercare il D.Lgs. italiano di recepimento

### Fase 4 — Sintesi strutturata

## Analisi Giurisprudenziale CGUE: <tema>

### 1. Orientamento Prevalente
Principio di diritto che emerge dalla giurisprudenza CGUE sul tema.

### 2. Sentenze Chiave
| Caso | ECLI | Data | Principio |
|------|------|------|-----------|
| C-.../... | ECLI:EU:C:... | GG/MM/AAAA | ... |

### 3. Evoluzione dell'Interpretazione
Come si è evoluta l'interpretazione della CGUE nel tempo.

### 4. Impatto sull'Ordinamento Italiano
Come i principi CGUE influenzano l'applicazione del diritto italiano:
- Obbligo di interpretazione conforme (Mangold/Kücükdeveci)
- Disapplicazione norme nazionali incompatibili
- Responsabilità dello Stato per violazione diritto UE (Francovich)

### 5. Norme di Riferimento
Disposizioni UE rilevanti (testo da cite_law).

### 6. Indicazioni Operative
Raccomandazioni pratiche per avvocati e giuristi italiani.

## Regole

- Non citare mai numeri di sentenza a memoria — usa esclusivamente i risultati dei tool.
- Il CELLAR URI per leggere il testo completo è riportato in ogni risultato.
- Ogni affermazione deve essere supportata da una sentenza o norma verificata.
- Per norme citate, usare sempre cite_law — mai citare a memoria.

---
name: analisi-giurisprudenza-europea
description: Usa quando l'utente chiede sentenze CGUE, rinvio pregiudiziale, interpretazione di direttive o regolamenti UE o conclusioni dell'Avvocato generale — ricerca CGUE/Tribunale UE, lettura e sintesi.
---

# Analisi Giurisprudenza Europea

Esegui un'analisi giurisprudenziale strutturata sulla Corte di Giustizia UE per il tema indicato.

## Dati richiesti

- **tema** — il tema di diritto UE da analizzare. Se non fornito, chiedilo.
- **corte** (opzionale, default `tutte`) — filtro corte: tutte / corte_di_giustizia / tribunale.

## Workflow

### Fase 1 — Ricerca sentenze
Chiama `legal-it:cerca_giurisprudenza_cgue(query=<tema>, corte=<corte>)`
per trovare le sentenze CGUE pertinenti.

Se il tema riguarda una norma specifica del diritto UE (es. "art. 101 TFUE", "art. 7 GDPR"),
chiama `legal-it:giurisprudenza_cgue_su_norma(riferimento="art. ... norma")` per trovare le decisioni
che interpretano quella norma.

### Fase 1b — Filtraggio per materia
Se il tema rientra in una delle materie predefinite (iva, concorrenza, ambiente, lavoro,
protezione_dati, appalti, consumatori), aggiungi il parametro materia alla ricerca per
ottenere risultati più mirati.

### Fase 2 — Lettura sentenze chiave
Seleziona le 2-3 sentenze più significative dalla ricerca.
Per ciascuna, chiama `legal-it:leggi_sentenza_cgue(cellar_uri)` con il CELLAR URI riportato nel risultato.

Privilegia:
- Sentenze della Grande Sezione (massima autorità interpretativa)
- Sentenze recenti (ultimi 3 anni)
- Sentenze che citano principi generali del diritto UE

IMPORTANTE: usa `legal-it:leggi_sentenza_cgue` con il CELLAR URI — NON usare EUR-Lex (ha WAF).

### Fase 3 — Fondamento normativo
Per le norme UE citate nelle sentenze lette, chiama `legal-it:cite_law(reference)` per verificare
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
- Obbligo di interpretazione conforme (von Colson e Kamann, Marleasing, Pfeiffer): non può fondare un'interpretazione contra legem, ma il giudice non può ritenerla impossibile per il solo fatto di avere costantemente interpretato la norma in senso incompatibile (Dansk Industri, C-441/14, punti 32-34)
- Disapplicazione delle norme nazionali incompatibili, anche tra privati quando è in gioco un principio generale del diritto UE (Mangold, C-144/04; Kücükdeveci, C-555/07) o un diritto della Carta (Egenberger, C-414/16, artt. 21 e 47; Bauer, C-569/16, art. 31, par. 2)
- In Italia, «doppia pregiudizialità» per le questioni che toccano insieme Costituzione e Carta dei diritti fondamentali (Corte cost. n. 269/2017 e n. 20/2019)
- Responsabilità dello Stato per violazione del diritto UE (Francovich)

### 5. Norme di Riferimento
Disposizioni UE rilevanti (testo da legal-it:cite_law).

### 6. Indicazioni Operative
Raccomandazioni pratiche per avvocati e giuristi italiani.

## Regole

- Non citare mai numeri di sentenza a memoria — usa esclusivamente i risultati dei tool.
- Il CELLAR URI per leggere il testo completo è riportato in ogni risultato.
- Ogni affermazione deve essere supportata da una sentenza o norma verificata.
- Per norme citate, usare sempre legal-it:cite_law — mai citare a memoria.

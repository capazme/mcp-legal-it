---
name: mappatura-normativa
description: Costruisce la mappa normativa completa di un settore o attivita con fonti organizzate per livello gerarchico e matrice adempimenti. Usa quando l'utente chiede il quadro normativo completo di un settore, tutte le leggi applicabili a un'attivita, o una checklist di obblighi normativi.
tools: [cerca_delibere_consob, cerca_provvedimenti_garante, cite_law]
prompt: {"name": "mappatura_normativa", "description": "Mappatura del quadro normativo completo per un settore o attività: tutte le fonti applicabili organizzate per livello", "args": [{"name": "settore", "type": "str"}, {"name": "attivita_specifica", "type": "str", "default": ""}]}
---

# Mappatura Normativa

Mappa completa delle fonti per settore/attivita, organizzata per gerarchia.

## Workflow

### 1. Fonti per livello

Per ogni livello, chiama `cite_law` su ogni articolo fondamentale:
1. **Costituzione** — articoli rilevanti
2. **UE** — regolamenti e direttive con D.Lgs. di recepimento
3. **Nazionale** — codici, testi unici, leggi, D.Lgs.
4. **Secondarie** — D.M., autorita indipendenti, linee guida

### 2. Fonti autorita vigilanza

- Settori finanziari: `cerca_delibere_consob`
- Privacy: `cerca_provvedimenti_garante`

### 3. Matrice adempimenti

| Obbligo | Fonte | Soggetto | Termine | Sanzione |
|---------|-------|----------|---------|----------|
| ... | ... | ... | ... | ... |

---
name: mappatura-normativa
description: Costruisce la mappa normativa completa di un settore o attivita con fonti organizzate per livello gerarchico e matrice adempimenti. Usa quando l'utente chiede il quadro normativo completo di un settore, tutte le leggi applicabili a un'attivita, o una checklist di obblighi normativi.
argument-hint: "[settore o attività]"
allowed-tools: mcp__legal-it__cite_law, mcp__legal-it__cerca_delibere_consob, mcp__legal-it__cerca_provvedimenti_garante, mcp__legal-it__cerca_brocardi
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

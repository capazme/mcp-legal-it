---
name: ricerca-normativa
description: Ricerca normativa completa su un tema giuridico con tutte le fonti applicabili ordinate per gerarchia, giurisprudenza e quadro sanzionatorio. Usa quando l'utente chiede quali norme si applicano, il quadro normativo di un settore, le fonti di una materia o una ricerca legislativa.
argument-hint: "[tema giuridico]"
allowed-tools: mcp__legal-it__cite_law, mcp__legal-it__cerca_brocardi, mcp__legal-it__cerca_giurisprudenza, mcp__legal-it__cerca_delibere_consob, mcp__legal-it__cerca_provvedimenti_garante
---

# Ricerca Normativa

Fonti primarie, norme collegate, giurisprudenza e sanzioni.

## Regola fondamentale

**Ogni norma citata DEVE essere verificata con `cite_law`**. Mai citare a memoria.

## Workflow

### 1. Fonti primarie

Per ogni norma individuata, chiama `cite_law`. Ordina per gerarchia:
1. Costituzione
2. Regolamenti UE
3. Direttive UE (+ D.Lgs. recepimento)
4. Leggi ordinarie / D.Lgs. / D.L.
5. D.M. e regolamenti
6. Circolari e prassi

### 2. Norme collegate

Per ogni norma primaria: attuazione, modifiche, abrogazioni, disposizioni transitorie.

### 3. Giurisprudenza

`cerca_brocardi` per massime. `cerca_giurisprudenza` per approfondimento.

### 4. Fonti autorita vigilanza

- Finanza/mercati: `cerca_delibere_consob`
- Privacy: `cerca_provvedimenti_garante`

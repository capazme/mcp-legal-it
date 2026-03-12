---
name: ricerca-normativa
description: Ricerca normativa completa su un tema giuridico con tutte le fonti applicabili ordinate per gerarchia, giurisprudenza e quadro sanzionatorio. Usa quando l'utente chiede quali norme si applicano, il quadro normativo di un settore, le fonti di una materia o una ricerca legislativa.
---

# Ricerca Normativa

Fonti primarie, norme collegate, giurisprudenza e sanzioni.

## Regola fondamentale

**Ogni norma citata DEVE essere verificata con `legal-it:cite_law`**. Mai citare a memoria.

## Workflow

### 1. Fonti primarie

Per ogni norma individuata, chiama `legal-it:cite_law`. Ordina per gerarchia:
1. Costituzione
2. Regolamenti UE
3. Direttive UE (+ D.Lgs. recepimento)
4. Leggi ordinarie / D.Lgs. / D.L.
5. D.M. e regolamenti
6. Circolari e prassi

### 2. Norme collegate

Per ogni norma primaria: attuazione, modifiche, abrogazioni, disposizioni transitorie.

### 3. Giurisprudenza

`legal-it:cerca_brocardi` per massime. `legal-it:cerca_giurisprudenza` per approfondimento.

### 4. Fonti autorita vigilanza

- Finanza/mercati: `legal-it:cerca_delibere_consob`
- Privacy: `legal-it:cerca_provvedimenti_garante`

## Tool utilizzati

- `legal-it:cite_law` (obbligatorio)
- `legal-it:cerca_brocardi`
- `legal-it:cerca_giurisprudenza`
- `legal-it:cerca_delibere_consob`
- `legal-it:cerca_provvedimenti_garante`

---
name: ricerca-normativa
description: Ricerca normativa completa su un tema giuridico con tutte le fonti applicabili ordinate per gerarchia, giurisprudenza e quadro sanzionatorio. Usa quando l'utente chiede quali norme si applicano, il quadro normativo di un settore, le fonti di una materia o una ricerca legislativa.
tools: [cerca_brocardi, cerca_delibere_consob, cerca_giurisprudenza, cerca_provvedimenti_garante, cite_law]
prompt: {"name": "ricerca_normativa", "description": "Ricerca normativa completa su un tema giuridico: norme applicabili, gerarchia delle fonti e coordinamento", "args": [{"name": "tema", "type": "str"}, {"name": "area_diritto", "type": "str"}]}
---

# Ricerca Normativa

Fonti primarie, norme collegate, giurisprudenza e sanzioni.

Inquadra la ricerca nell'area di diritto indicata dall'utente (civile / penale / amministrativo / lavoro / tributario / privacy / commerciale) prima di individuare le fonti.

## Regola fondamentale

**Ogni norma citata DEVE essere verificata con `cite_law`**. Mai citare a memoria.

Regole ulteriori:
- Indicare espressamente se una norma è stata modificata o abrogata.
- Segnalare le modifiche normative già pubblicate in Gazzetta Ufficiale e verificabili con i tool. Non segnalare riforme pendenti o proposte de lege ferenda, per le quali il server non dispone di una fonte verificabile.

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

Per le norme chiave, chiama `cite_law` con `include_annotations=true` per recuperare da Brocardi:
- Massime di Cassazione e Corte Costituzionale
- Orientamenti consolidati vs. questioni aperte
- Posizioni dottrinali prevalenti

Per trovare giurisprudenza recente (ultimi 5 anni), chiama `cerca_giurisprudenza` con la query tra virgolette (es. `query="\"art. ... codice\""`) e `modalita="esplora"` per vedere la distribuzione, poi ripeti la ricerca con filtri per le decisioni più rilevanti.

### 4. Fonti autorita vigilanza

- Finanza/mercati: `cerca_delibere_consob`
- Privacy: `cerca_provvedimenti_garante`

Se il tema riguarda mercati finanziari, intermediari, emittenti, OPA, crowdfunding o cripto-attività, chiama `cerca_delibere_consob` con il tema come query per recuperare le delibere e i provvedimenti CONSOB rilevanti; per le delibere più significative, recupera anche il testo integrale della delibera.

Per le materie finanziarie includere sempre i provvedimenti delle autorità di vigilanza. Per Banca d'Italia non esiste un tool dedicato: indicare al lettore la fonte da consultare, senza riportarne il contenuto a memoria.

### 5. Quadro sanzionatorio

Se pertinente, identifica:
- Sanzioni penali (contravvenzioni, delitti)
- Sanzioni amministrative (pecuniarie, interdittive)
- Responsabilità civile (risarcimento danni)
- Sanzioni disciplinari (ordini professionali, PA)

## Formato output

```markdown
## Ricerca Normativa su [tema]

### 1. Fonti Primarie
| Fonte | Norma | Oggetto |
|-------|-------|---------|
| Costituzione | art. ... | ... |
| Reg. UE | ... | ... |
| Legge | ... | ... |

### 2. Articoli Chiave
Per ciascun articolo: testo (da cite_law), commento sintetico, nessi con altri articoli.

### 3. Evoluzione Normativa
Timeline delle modifiche rilevanti.

### 4. Orientamenti Interpretativi
Giurisprudenza consolidata e questioni aperte.

### 5. Quadro Sanzionatorio
Tabella delle sanzioni applicabili.
```

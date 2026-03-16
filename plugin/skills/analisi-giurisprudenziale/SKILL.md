---
name: analisi-giurisprudenziale
description: Analisi strutturata degli orientamenti giurisprudenziali su un tema con ricerca sentenze Cassazione su Italgiure, lettura testo completo delle decisioni chiave e sintesi degli orientamenti. Usa quando l'utente chiede giurisprudenza su un argomento, orientamenti della Cassazione, precedenti, o sentenze su un tema specifico.
---

# Analisi Giurisprudenziale

Ricerca Italgiure, lettura decisioni chiave, sintesi orientamenti.

## Regola fondamentale

**Non citare mai numeri di sentenza a memoria**. Usa esclusivamente i risultati dei tool.

## Workflow

### Fase 1 — Esplora la distribuzione

Chiama `cerca_giurisprudenza` con `modalita="esplora"` per vedere quante decisioni esistono e come sono distribuite per materia, sezione, anno e tipo.

```
cerca_giurisprudenza(query="\"tema specifico\"", modalita="esplora")
```

**Usa virgolette** per frasi esatte (es. `"responsabilita' medica"` non `responsabilita' medica`).

### Fase 2 — Cerca con filtri mirati

In base ai facets del Passo 1, applica filtri per restringere i risultati:

```
cerca_giurisprudenza(
    query="\"tema specifico\"",
    materia="...",
    sezione="...",
    tipo_provvedimento="sentenza",
    max_risultati=10
)
```

Se il tema riguarda una norma specifica, usa anche `giurisprudenza_su_norma`.

Per cercare solo nel dispositivo (piu' preciso): `campo="dispositivo"`.

**Sintassi query Solr**: `"frase esatta"`, `AND`/`OR`, `-esclusione`, `"frase"~3` (prossimita'), `termin*` (wildcard).

### Fase 3 — Approfondimento

Seleziona 2-4 decisioni significative (privilegia Sezioni Unite e sentenze recenti).
Per ciascuna: `leggi_sentenza` con numero e anno.

**Non fare web search per sentenze gia identificate.**

### Fase 4 — Annotazioni Brocardi

Se il tema ruota attorno a un articolo specifico: `cerca_brocardi` per ratio legis, spiegazione e massime strutturate.

### Fase 5 — Fondamento normativo

Per le norme citate nelle decisioni: `cite_law` per testo vigente.

### Fase 6 — Sintesi

1. **Orientamento prevalente**: principio di diritto
2. **Evoluzione**: cambiamenti nel tempo
3. **Contrasti**: divergenze tra sezioni
4. **Sezioni Unite**: principio di diritto (se pronunciate)
5. **Norme di riferimento**
6. **Decisioni citate**: elenco con estremi

## Tool utilizzati

- `cerca_giurisprudenza` (ricerca full-text — supporta `modalita="esplora"` e `campo="dispositivo"`)
- `giurisprudenza_su_norma` (sentenze su norma)
- `leggi_sentenza` (testo completo)
- `cerca_brocardi` (annotazioni e massime)
- `cite_law` (norme citate)

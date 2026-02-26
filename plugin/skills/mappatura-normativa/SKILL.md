---
name: mappatura-normativa
description: Mappatura del quadro normativo completo per un settore o attività con tutte le fonti organizzate per livello.
  Usa quando l'utente chiede la normativa applicabile a un settore, attività o business.
argument-hint: "[settore, es. 'e-commerce', 'sanità', 'edilizia'] [attività specifica opzionale]"
---

# Workflow Mappatura Normativa

Segui questi step nell'ordine. Usa i tool MCP di Legal IT.

## Step 1 — Fonti costituzionali
Identifica gli articoli della Costituzione rilevanti.
Chiama `cite_law` per ciascuno (es. art. 41, 42, 117 Cost.).

## Step 2 — Fonti europee
Identifica regolamenti e direttive UE applicabili.
- Per i regolamenti: chiama `cite_law` per gli articoli chiave.
- Per le direttive: identifica il D.Lgs. di recepimento italiano.

## Step 3 — Fonti legislative nazionali
Mappa:
- Codici applicabili (civile, penale, procedura, settoriali)
- Testi unici / Codici di settore
- Leggi ordinarie e decreti legislativi
- Decreti legge convertiti

Per ciascuna: chiama `cite_law` per gli articoli fondamentali.

## Step 4 — Fonti regolamentari e soft law
- Decreti ministeriali (D.M.)
- Regolamenti di autorità indipendenti (Garante Privacy, AGCM, Consob, ecc.)
- Linee guida e provvedimenti generali
- Standard tecnici (ISO, UNI) se vincolanti

## Step 5 — Obblighi e adempimenti
Per ogni fonte, estrai gli obblighi concreti:
- Adempimenti documentali
- Obblighi di comunicazione / notifica
- Registri e tenuta documentale
- Formazione e designazioni
- Termini e scadenze

## Step 6 — Presentazione risultati

### Livello 1 — Costituzione
| Articolo | Principio | Rilevanza |
|----------|-----------|-----------|
| art. ... | ... | ... |

### Livello 2 — Diritto UE
| Fonte | Tipo | Articoli chiave | Recepimento IT |
|-------|------|-----------------|----------------|
| ... | Reg./Dir. | artt. ... | D.Lgs. .../... |

### Livello 3 — Legislazione Nazionale
| Fonte | Materia | Articoli chiave |
|-------|---------|-----------------|
| ... | ... | artt. ... |

### Livello 4 — Fonti Secondarie
| Fonte | Autorità | Oggetto |
|-------|----------|---------|
| ... | ... | ... |

### Matrice Adempimenti
| Obbligo | Fonte | Soggetto | Termine | Sanzione |
|---------|-------|----------|---------|----------|
| ... | art. ... | ... | ... | ... |

### Checklist Operativa
Elenco ordinato per priorità degli adempimenti da verificare.

## Note
- Usare `cite_law` per TUTTI gli articoli citati nella mappa.
- Indicare la data di entrata in vigore di ciascuna fonte.
- Segnalare norme in fase di modifica o revisione.
- Per settori regolati, includere sempre le fonti dell'autorità di vigilanza.

---
name: mappatura-normativa
description: Costruisce la mappa normativa completa di un settore o attivita con fonti organizzate per livello gerarchico e matrice adempimenti. Usa quando l'utente chiede il quadro normativo completo di un settore, tutte le leggi applicabili a un'attivita, o una checklist di obblighi normativi.
---

# Mappatura Normativa

Mappa completa delle fonti per settore/attivita, organizzata per gerarchia.

## Workflow

### 1. Fonti per livello

Per ogni livello, chiama `legal-it:cite_law` su ogni articolo fondamentale:
1. **Costituzione** — identifica gli articoli della Costituzione rilevanti e chiama `legal-it:cite_law` per ciascuno (es. art. 41, 42, 117 Cost.)
2. **UE** — regolamenti e direttive con D.Lgs. di recepimento: per i regolamenti (direttamente applicabili) chiama `legal-it:cite_law` per gli articoli chiave; per le direttive identifica il D.Lgs. di recepimento italiano
3. **Nazionale** — mappa: codici applicabili (civile, penale, procedura, settoriali), testi unici / codici di settore, leggi ordinarie e decreti legislativi, decreti legge convertiti
4. **Secondarie** — decreti ministeriali (D.M.), regolamenti di autorita indipendenti (Garante Privacy, AGCM, CONSOB, ecc.), linee guida e provvedimenti generali, standard tecnici (ISO, UNI) se vincolanti

### 2. Fonti autorita vigilanza

- Settori finanziari: `legal-it:cerca_delibere_consob`
- Privacy: `legal-it:cerca_provvedimenti_garante`

Per le delibere CONSOB chiave, approfondisci leggendone il testo integrale con `legal-it:leggi_delibera_consob`.

### 3. Matrice adempimenti

Per ogni fonte, estrai gli obblighi concreti:
- Adempimenti documentali
- Obblighi di comunicazione / notifica
- Registri e tenuta documentale
- Formazione e designazioni
- Termini e scadenze

| Obbligo | Fonte | Soggetto | Termine | Sanzione |
|---------|-------|----------|---------|----------|
| ... | ... | ... | ... | ... |

## Formato output

Intitola l'output `Mappa Normativa:` seguito dal `settore` indicato.

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

| Fonte | Autorita | Oggetto |
|-------|----------|---------|
| ... | ... | ... |

Segue la Matrice adempimenti (tabella del punto 3 del workflow), poi:

### Checklist Operativa

Elenco ordinato per priorita degli adempimenti da verificare.

## Regole

- Usare `legal-it:cite_law` per TUTTI gli articoli citati nella mappa.
- Indicare la data di entrata in vigore di ciascuna fonte.
- Segnalare le norme in fase di modifica o revisione se la modifica risulta gia pubblicata in Gazzetta Ufficiale (verificabile con i tool), oppure se pende un DDL verificato con `legal-it:ddl_su_norma` o `legal-it:cerca_ddl` (stato dell'iter con `legal-it:iter_ddl`): in tal caso citare numero atto, stato, data e scheda ufficiale. Mai de lege ferenda senza estremi verificati; l'assenza di DDL trovati non prova l'assenza di riforme, perche la ricerca copre i soli titoli.
- Per settori regolati (privacy, bancario, sanitario), includere sempre le fonti dell'autorita di vigilanza.

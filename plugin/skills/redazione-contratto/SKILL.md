---
name: redazione-contratto
description: Supporto alla redazione contrattuale con verifica normativa, clausole tipo e compliance GDPR.
  Usa quando l'utente chiede di redigere, revisionare o analizzare un contratto.
argument-hint: "[tipo contratto, es. 'appalto', 'locazione', 'SaaS', 'NDA'] [parti coinvolte]"
---

# Workflow Redazione Contratto

Segui questi step nell'ordine. Usa i tool MCP di Legal IT.

## Step 1 — Analisi preliminare
Identifica dall'input dell'utente:
- **Tipo di contratto** (compravendita, locazione, appalto, prestazione d'opera, SaaS, NDA, etc.)
- **Parti coinvolte** (persone fisiche/giuridiche, B2B/B2C)
- **Oggetto del contratto**
- **Elementi essenziali** specifici

## Step 2 — Quadro normativo
Chiama `cite_law` per recuperare le norme che disciplinano il tipo contrattuale:
- Norme generali sul contratto (artt. 1321-1469 c.c.)
- Norme specifiche del tipo contrattuale (es. locazione artt. 1571 ss., appalto artt. 1655 ss.)
- Legislazione speciale (es. D.Lgs. 206/2005 Codice del Consumo per B2C)
- Normativa europea se applicabile

Per ciascuna norma chiave, chiama anche `cerca_brocardi` per orientamenti interpretativi.

## Step 3 — Clausole essenziali
Sulla base del quadro normativo, identifica le clausole da includere:
- **Elementi essenziali** (art. 1325 c.c.): accordo, causa, oggetto, forma
- **Clausole specifiche** del tipo contrattuale
- **Clausole di garanzia** e limitazione di responsabilità
- **Clausole risolutive** e penali
- **Foro competente** e legge applicabile
- **Clausole compromissorie** (arbitrato) se opportuno

## Step 4 — Compliance GDPR (se il contratto coinvolge dati personali)
Se il contratto prevede trattamento di dati personali:
1. Chiama `analisi_base_giuridica` per identificare la base giuridica
2. Se una parte è responsabile del trattamento: chiama `genera_dpa` per il contratto art. 28 GDPR
3. Verifica la necessità di informativa privacy per le parti

## Step 5 — Output strutturato

### Quadro Normativo
| Norma | Articoli | Rilevanza |
|-------|----------|-----------|
| ... | artt. ... | ... |

### Schema Clausole
Per ciascuna clausola suggerita, fornisci:
- **Titolo** della clausola
- **Contenuto** suggerito (linguaggio contrattuale)
- **Fondamento normativo** (articolo di legge)
- **Note** operative (giurisprudenza rilevante, rischi da evitare)

### Compliance GDPR
- Trattamento dati previsto: Sì/No
- DPA necessario: Sì/No
- Informativa da allegare: Sì/No

### Avvertenze
- Le clausole suggerite sono uno schema — il testo finale richiede adattamento al caso concreto.
- Per contratti con consumatori (B2C), verificare la vessatorietà delle clausole (artt. 33-38 Cod. Consumo).
- Per contratti internazionali, considerare la Convenzione di Vienna (CISG) e il Reg. Roma I.

## Note
- OGNI norma citata DEVE provenire da `cite_law`.
- Non redigere un contratto completo — fornire lo schema e le clausole chiave con fondamento normativo.
- Se una clausola è potenzialmente vessatoria, segnalarlo espressamente.

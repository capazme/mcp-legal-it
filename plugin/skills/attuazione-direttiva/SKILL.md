---
name: attuazione-direttiva
description: Usa quando l'utente chiede come è stata recepita una direttiva UE, quale atto italiano la attua o la base UE di un atto nazionale — misure di attuazione, testo vigente e giurisprudenza CGUE collegata.
---

# Attuazione Direttiva

Ricostruisci il recepimento italiano della direttiva UE indicata.

## Dati richiesti

- **direttiva** — CELEX es. "32019L0790" oppure "direttiva (UE) 2019/790". Se non fornito, chiedilo.

## Workflow

### Fase 1 — Atto di attuazione italiano
Chiama `legal-it:get_italian_implementation(direttiva=<direttiva>)` per gli atti italiani di trasposizione
(tipo, numero, GU n./data, entrata in vigore, titolo, CELEX MNE). Se la direttiva è in realtà un
REGOLAMENTO, il tool lo segnala: i regolamenti sono direttamente applicabili e NON hanno atto di
recepimento — riportalo.

### Fase 2 — Testo dell'atto italiano
Per ciascun atto di attuazione chiama `legal-it:cite_law(reference)` (es. "D.Lgs. 177/2021") per il testo
vigente da Normattiva. (CELLAR fornisce solo i metadati del recepimento, non il testo nazionale.)

### Fase 3 — Base UE e giurisprudenza
Per la direttiva, chiama `legal-it:cite_law` sul testo UE e `legal-it:giurisprudenza_cgue_su_norma(riferimento=...)` per
le pronunce della Corte di Giustizia che la interpretano. (Percorso inverso: da un atto italiano alla
direttiva, usa `legal-it:get_eu_basis(atto="...")`.)

### Fase 4 — Sintesi
Riporta: direttiva → atto/i italiano/i di attuazione (con estremi e GU), termine di trasposizione,
eventuale ritardo/incompletezza emersa, e principali pronunce CGUE collegate.

## Regole

- Un atto nazionale può recepire più direttive e viceversa: riportarli tutti, senza assumere 1:1.
- Distinguere metadati di recepimento (CELLAR) dal testo vigente (Normattiva).
- Usare i tool, mai estremi a memoria.

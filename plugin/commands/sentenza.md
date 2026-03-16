---
name: sentenza
description: Leggi il testo integrale di una sentenza di Cassazione
allowed-tools: mcp__legal-it__leggi_sentenza
---

Usa `leggi_sentenza` per recuperare il testo integrale della sentenza.

Se l'utente ha fornito numero e anno (es. "Cass. 100/2024"), chiama direttamente con quei parametri.
Se mancano dati, chiedi numero e anno. Se l'utente non ha il numero ma solo un tema, suggerisci di usare `/ricerca` per cercare prima.

Presenta: massima, dispositivo e parti salienti della motivazione.

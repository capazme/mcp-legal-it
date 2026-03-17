## Descrizione

Breve descrizione delle modifiche.

## Tipo di modifica

- [ ] Bug fix
- [ ] Nuova feature / nuovo tool
- [ ] Refactoring (nessun cambio funzionale)
- [ ] Documentazione
- [ ] CI / infrastruttura

## Checklist

- [ ] `pytest tests/ -m "not live"` passa
- [ ] I nuovi tool hanno docstring con `Args:` e nota vigenza/precisione
- [ ] Le funzioni `_impl` con HTTP hanno test con mock httpx
- [ ] Se modulo nuovo: `server.py` aggiornato (import + instructions)
- [ ] Output rispetta convenzioni (importi `€ 1.234,56`, date `GG/MM/AAAA`)
- [ ] Nessun segreto o credenziale nel codice

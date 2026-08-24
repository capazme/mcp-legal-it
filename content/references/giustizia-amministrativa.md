GIUSTIZIA AMMINISTRATIVA — GUIDA ALLA RICERCA PROVVEDIMENTI TAR/CdS
(giustizia-amministrativa.it — mdp.giustizia-amministrativa.it)

═══════════════════════════════════════════════════════════
TOOL DISPONIBILI
═══════════════════════════════════════════════════════════

| Tool | Uso | Parametri chiave |
|------|-----|------------------|
| `cerca_giurisprudenza_amministrativa` | Ricerca full-text TAR/CdS | query, sede, tipo, anno, max_risultati |
| `leggi_provvedimento_amm` | Testo completo dal sottodominio mdp | sede, nrg, nome_file |
| `giurisprudenza_amm_su_norma` | Decisioni che citano un articolo | riferimento, sede, anno_da |
| `ultimi_provvedimenti_amm` | Ultimi depositati | sede, tipo, max_risultati |

═══════════════════════════════════════════════════════════
SEDI DISPONIBILI (31 sedi)
═══════════════════════════════════════════════════════════

La colonna "Codice" è quella restituita dalla ricerca e va passata a
`leggi_provvedimento_amm(sede=...)`.

| Chiave | Codice | Sede |
|--------|--------|------|
| `consiglio_di_stato` | cds | Consiglio di Stato |
| `cgars` | cgagiur | CGARS (Consiglio di Giustizia Amministrativa per la Regione Siciliana) |
| `tar_lazio` | tar_rm | TAR Lazio - Roma |
| `tar_lazio_latina` | tar_lt | TAR Lazio - Latina |
| `tar_lombardia` | tar_mi | TAR Lombardia - Milano |
| `tar_lombardia_brescia` | tar_bs | TAR Lombardia - Brescia |
| `tar_campania_napoli` | tar_na | TAR Campania - Napoli |
| `tar_campania_salerno` | tar_sa | TAR Campania - Salerno |
| `tar_sicilia_palermo` | tar_pa | TAR Sicilia - Palermo |
| `tar_sicilia_catania` | tar_ct | TAR Sicilia - Catania |
| `tar_veneto` | tar_ve | TAR Veneto |
| `tar_piemonte` | tar_to | TAR Piemonte |
| `tar_emilia_romagna` | tar_bo | TAR Emilia-Romagna - Bologna |
| `tar_emilia_romagna_parma` | tar_pr | TAR Emilia-Romagna - Parma |
| `tar_toscana` | tar_fi | TAR Toscana |
| `tar_puglia_bari` | tar_ba | TAR Puglia - Bari |
| `tar_puglia_lecce` | tar_le | TAR Puglia - Lecce |
| `tar_calabria_catanzaro` | tar_cz | TAR Calabria - Catanzaro |
| `tar_calabria_reggio` | tar_rc | TAR Calabria - Reggio Calabria |
| `tar_liguria` | tar_ge | TAR Liguria |
| `tar_sardegna` | tar_ca | TAR Sardegna |
| `tar_friuli` | tar_ts | TAR Friuli-Venezia Giulia |
| `tar_marche` | tar_an | TAR Marche |
| `tar_abruzzo_laquila` | tar_aq | TAR Abruzzo - L'Aquila |
| `tar_abruzzo_pescara` | tar_pe | TAR Abruzzo - Pescara |
| `tar_umbria` | tar_pg | TAR Umbria |
| `tar_molise` | tar_cb | TAR Molise |
| `tar_basilicata` | tar_pz | TAR Basilicata |
| `tar_trentino_trento` | tar_tn | TRGA Trentino-Alto Adige - Trento |
| `tar_trentino_bolzano` | tar_bz | TRGA Trentino-Alto Adige - Bolzano |
| `tar_valle_aosta` | tar_ao | TAR Valle d'Aosta |

═══════════════════════════════════════════════════════════
TIPI DI PROVVEDIMENTO
═══════════════════════════════════════════════════════════

| Chiave | Descrizione |
|--------|-------------|
| `sentenza` | Sentenza (decisione nel merito) |
| `ordinanza` | Ordinanza (cautelare, istruttoria) |
| `decreto` | Decreto monocratico (cautelare urgente) |
| `parere` | Parere del Consiglio di Stato |
| `adunanza_plenaria` | Adunanza Plenaria del Consiglio di Stato |
| `adunanza_generale` | Adunanza Generale del Consiglio di Stato |

═══════════════════════════════════════════════════════════
FILTRO PER ANNO — LIMITE DELLA FONTE
═══════════════════════════════════════════════════════════

Il portale non espone più un filtro per anno indipendente: l'anno è onorato
lato server solo insieme al numero del provvedimento
(es. anno="2023" + numero="1234" → provvedimento 1234/2023).
Da solo, l'anno viene applicato sui risultati restituiti, che sono ordinati
dal più recente: per anni remoti indicare anche `numero` o restringere la query.

═══════════════════════════════════════════════════════════
WORKFLOW CONSIGLIATI
═══════════════════════════════════════════════════════════

Ricerca tematica:
1. cerca_giurisprudenza_amministrativa(query="appalto esclusione requisiti")
2. leggi_provvedimento_amm(sede="cds", nrg="202401476", nome_file="202605674_18.html")
   → sede, nrg e nome_file sono riportati in ogni risultato della ricerca
3. cite_law("art. 83 D.Lgs. 36/2023") → norma di riferimento

Ricerca su norma:
1. giurisprudenza_amm_su_norma(riferimento="art. 21-nonies L. 241/1990")
2. leggi_provvedimento_amm(...) → testo completo decisioni
3. cite_law("art. 21-nonies L. 241/1990") → testo aggiornato

Monitoraggio novità:
1. ultimi_provvedimenti_amm(sede="consiglio_di_stato", tipo="sentenza")
2. leggi_provvedimento_amm(...) → approfondimento

═══════════════════════════════════════════════════════════
NORMATIVA AMMINISTRATIVA DI RIFERIMENTO
═══════════════════════════════════════════════════════════

| Fonte | Riferimento | Citazione | Materia |
|-------|-------------|-----------|---------|
| CPA | D.Lgs. 104/2010 | art. N CPA | Codice del Processo Amministrativo |
| Codice Appalti | D.Lgs. 36/2023 | art. N D.Lgs. 36/2023 | Appalti e concessioni |
| Procedimento amm. | L. 241/1990 | art. N L. 241/1990 | Accesso, silenzio, SCIA, conferenza servizi |
| TUEL | D.Lgs. 267/2000 | art. N TUEL | Enti locali, bilancio, organi |
| TU Edilizia | D.P.R. 380/2001 | art. N DPR 380/2001 | Permesso costruire, abusi edilizi |
| CAD | D.Lgs. 82/2005 | art. N CAD | Documento informatico, PEC |
| Codice Antimafia | D.Lgs. 159/2011 | art. N Cod. Antimafia | Informative antimafia, interdittive |
| D.Lgs. 33/2013 | D.Lgs. 33/2013 | art. N D.Lgs. 33/2013 | Trasparenza PA, accesso civico |

Per il testo aggiornato: usare cite_law("art. N [fonte]").

═══════════════════════════════════════════════════════════
MATERIE TIPICHE — ESEMPI DI QUERY
═══════════════════════════════════════════════════════════

| Materia | Query suggerita | Norma tipica |
|---------|----------------|--------------|
| Appalti — esclusione | "esclusione gara requisiti" | art. 94-98 D.Lgs. 36/2023 |
| Appalti — offerta anomala | "offerta anomala verifica" | art. 110 D.Lgs. 36/2023 |
| Silenzio-assenso | "silenzio-assenso formazione" | art. 20 L. 241/1990 |
| Accesso atti | "accesso documenti amministrativi" | art. 22 L. 241/1990 |
| Autotutela | "annullamento in autotutela" | art. 21-nonies L. 241/1990 |
| Urbanistica | "permesso costruire variante PRG" | DPR 380/2001 |
| Interdittiva antimafia | "informativa antimafia interdittiva" | D.Lgs. 159/2011 |
| Accesso civico | "accesso civico generalizzato FOIA" | D.Lgs. 33/2013 |

═══════════════════════════════════════════════════════════
NOTE TECNICHE
═══════════════════════════════════════════════════════════

- Il portale usa Liferay Portal — ricerca pubblica, nessuna autenticazione
- Testi integrali sul sottodominio mdp in formato XML <GA> (epigrafe + motivazione + dispositivo)
- Certificato SSL valido su entrambi i domini → verifica TLS attiva
- Il testo è troncato a 15000 caratteri per evitare saturazione del contesto
- I parametri sede, nrg e nome_file per leggi_provvedimento_amm vengono dai risultati di ricerca
- Adunanza Plenaria: massima autorità del CdS — privilegiare nelle ricerche

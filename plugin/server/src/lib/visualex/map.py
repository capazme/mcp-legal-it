"""Resolution maps for Italian legal acts — URN generation, abbreviations, Brocardi URLs."""

import re


# ---------------------------------------------------------------------------
# NORMATTIVA URN CODICI — codice name → partial URN
# ---------------------------------------------------------------------------

NORMATTIVA_URN_CODICI = {
    "costituzione": "costituzione",
    "codice penale": "regio.decreto:1930-10-19;1398:1",
    "codice di procedura civile": "regio.decreto:1940-10-28;1443:1",
    "disposizioni per l'attuazione del Codice di procedura civile e disposizioni transitorie": "regio.decreto:1941-08-25;1368:1",
    "codici penali militari di pace e di guerra": "relazione.e.regio.decreto:1941-02-20;303",
    "disposizioni di coordinamento, transitorie e di attuazione dei Codici penali militari di pace e di guerra": "regio.decreto:1941-09-09;1023",
    "codice civile": "regio.decreto:1942-03-16;262:2",
    "preleggi": "regio.decreto:1942-03-16;262:1",
    "disposizioni per l'attuazione del Codice civile e disposizioni transitorie": "regio.decreto:1942-03-30;318:1",
    "codice della navigazione": "regio.decreto:1942-03-30;327:1",
    "approvazione del Regolamento per l'esecuzione del Codice della navigazione (Navigazione marittima)": "decreto.del.presidente.della.repubblica:1952-02-15;328",
    "codice postale e delle telecomunicazioni": "decreto.del.presidente.della.repubblica:1973-03-29;156:1",
    "codice di procedura penale": "decreto.del.presidente.della.repubblica:1988-09-22;447",
    "norme di attuazione, di coordinamento e transitorie del codice di procedura penale": "decreto.legislativo:1989-07-28;271",
    "codice della strada": "decreto.legislativo:1992-04-30;285",
    "regolamento di esecuzione e di attuazione del nuovo codice della strada.": "decreto.del.presidente.della.repubblica:1992-12-16;495",
    "codice del processo tributario": "decreto.legislativo:1992-12-31;546",
    "codice in materia di protezione dei dati personali": "decreto.legislativo:2003-06-30;196",
    "codice delle comunicazioni elettroniche": "decreto.legislativo:2003-08-01;259",
    "codice dei beni culturali e del paesaggio": "decreto.legislativo:2004-01-22;42",
    "codice della proprietà industriale": "decreto.legislativo:2005-02-10;30",
    "codice dell'amministrazione digitale": "decreto.legislativo:2005-03-07;82",
    "codice della nautica da diporto": "decreto.legislativo:2005-07-18;171",
    "codice del consumo": "decreto.legislativo:2005-09-06;206",
    "codice delle assicurazioni private": "decreto.legislativo:2005-09-07;209",
    "norme in materia ambientale": "decreto.legislativo:2006-04-03;152",
    "codice dei contratti pubblici": "decreto.legislativo:2023-03-31;36",
    "codice delle pari opportunità": "decreto.legislativo:2006-04-11;198",
    "codice dell'ordinamento militare": "decreto.legislativo:2010-03-15;66",
    "codice del processo amministrativo": "decreto.legislativo:2010-07-02;104:2",
    "codice del turismo": "decreto.legislativo:2011-05-23;79",
    "codice antimafia": "decreto.legislativo:2011-09-06;159",
    "codice di giustizia contabile": "decreto.legislativo:2016-08-26;174:1",
    "codice del Terzo settore": "decreto.legislativo:2017-07-03;117",
    "codice della protezione civile": "decreto.legislativo:2018-01-02;1",
    "codice della crisi d'impresa e dell'insolvenza": "decreto.legislativo:2019-01-12;14",
}


# ---------------------------------------------------------------------------
# ATTI NOTI — common names → scraper parameters
# ---------------------------------------------------------------------------

ATTI_NOTI = {
    "gdpr": {"tipo_atto": "regolamento ue", "data": "2016", "numero_atto": "679"},
    "rgpd": {"tipo_atto": "regolamento ue", "data": "2016", "numero_atto": "679"},
    "regolamento privacy": {"tipo_atto": "regolamento ue", "data": "2016", "numero_atto": "679"},
    "regolamento generale protezione dati": {"tipo_atto": "regolamento ue", "data": "2016", "numero_atto": "679"},
    "dora": {"tipo_atto": "regolamento ue", "data": "2022", "numero_atto": "2554"},
    "ai act": {"tipo_atto": "regolamento ue", "data": "2024", "numero_atto": "1689"},
    "regolamento ia": {"tipo_atto": "regolamento ue", "data": "2024", "numero_atto": "1689"},
    "ehds": {"tipo_atto": "regolamento ue", "data": "2025", "numero_atto": "327"},
    "european health data space": {"tipo_atto": "regolamento ue", "data": "2025", "numero_atto": "327"},
    "nis2": {"tipo_atto": "direttiva ue", "data": "2022", "numero_atto": "2555"},
    "nis 2": {"tipo_atto": "direttiva ue", "data": "2022", "numero_atto": "2555"},
    "codice privacy": {"tipo_atto": "codice in materia di protezione dei dati personali", "data": "", "numero_atto": ""},
    "d.lgs. 196/2003": {"tipo_atto": "decreto legislativo", "data": "2003-06-30", "numero_atto": "196"},
    "d.lgs. 231/2001": {"tipo_atto": "decreto legislativo", "data": "2001-06-08", "numero_atto": "231"},
    "d.lgs. 81/2008": {"tipo_atto": "decreto legislativo", "data": "2008-04-09", "numero_atto": "81"},
    "testo unico sicurezza": {"tipo_atto": "decreto legislativo", "data": "2008", "numero_atto": "81"},
    "codice civile": {"tipo_atto": "codice civile", "data": "", "numero_atto": ""},
    "codice penale": {"tipo_atto": "codice penale", "data": "", "numero_atto": ""},
    "costituzione": {"tipo_atto": "costituzione", "data": "", "numero_atto": ""},
    "cost": {"tipo_atto": "costituzione", "data": "", "numero_atto": ""},
    "cost.": {"tipo_atto": "costituzione", "data": "", "numero_atto": ""},
    "c.c.": {"tipo_atto": "codice civile", "data": "", "numero_atto": ""},
    "c.p.": {"tipo_atto": "codice penale", "data": "", "numero_atto": ""},
    "c.p.c.": {"tipo_atto": "codice di procedura civile", "data": "", "numero_atto": ""},
    "c.p.c": {"tipo_atto": "codice di procedura civile", "data": "", "numero_atto": ""},
    "c.p.p.": {"tipo_atto": "codice di procedura penale", "data": "", "numero_atto": ""},
    "cds": {"tipo_atto": "codice della strada", "data": "", "numero_atto": ""},
    "cdc": {"tipo_atto": "codice del consumo", "data": "", "numero_atto": ""},
    "tub": {"tipo_atto": "decreto legislativo", "data": "1993", "numero_atto": "385"},
    "tuf": {"tipo_atto": "decreto legislativo", "data": "1998", "numero_atto": "58"},
    "tuir": {"tipo_atto": "decreto del presidente della repubblica", "data": "1986", "numero_atto": "917"},
}


# ---------------------------------------------------------------------------
# NORMATTIVA SEARCH — abbreviations → full name (for search / URN generation)
# ---------------------------------------------------------------------------

NORMATTIVA_SEARCH = {
    "d.lgs.": "decreto legislativo",
    "decreto legge": "decreto legge",
    "decreto legislativo": "decreto legislativo",
    "decreto.legge": "decreto legge",
    "decreto.legislativo": "decreto legislativo",
    "rd": "regio decreto",
    "r.d.": "regio decreto",
    "regio decreto": "regio decreto",
    "dpr": "decreto del presidente della repubblica",
    "d.p.r.": "decreto del presidente della repubblica",
    "decreto.del.presidente.della.repubblica": "decreto del presidente della repubblica",
    "dl": "decreto legge",
    "dlgs": "decreto legislativo",
    "dm": "decreto ministeriale",
    "d.m.": "decreto ministeriale",
    "d.m": "decreto ministeriale",
    "decreto ministeriale": "decreto ministeriale",
    "dpcm": "decreto del presidente del consiglio dei ministri",
    "d.p.c.m.": "decreto del presidente del consiglio dei ministri",
    "d.p.c.m": "decreto del presidente del consiglio dei ministri",
    "decreto del presidente del consiglio dei ministri": "decreto del presidente del consiglio dei ministri",
    "l": "legge",
    "l.": "legge",
    "legge": "legge",
    "c.c.": "codice civile",
    "c.p.": "codice penale",
    "c.p.c": "codice di procedura civile",
    "c.p.p.": "codice di procedura penale",
    "cad": "codice dell'amministrazione digitale",
    "cam": "codice antimafia",
    "camb": "norme in materia ambientale",
    "cap": "codice delle assicurazioni private",
    "cbc": "codice dei beni culturali e del paesaggio",
    "cc": "codice civile",
    "cce": "codice delle comunicazioni elettroniche",
    "cci": "codice della crisi d'impresa e dell'insolvenza",
    "ccp": "codice dei contratti pubblici",
    "cdc": "codice del consumo",
    "cdpc": "codice della protezione civile",
    "cds": "codice della strada",
    "cgco": "codice di giustizia contabile",
    "cn": "codice della navigazione",
    "cnd": "codice della nautica da diporto",
    "cod. amm. dig.": "codice dell'amministrazione digitale",
    "cod. antimafia": "codice antimafia",
    "cod. ass. priv.": "codice delle assicurazioni private",
    "cod. beni cult.": "codice dei beni culturali e del paesaggio",
    "cod. civ.": "codice civile",
    "cod. com. elet.": "codice delle comunicazioni elettroniche",
    "cod. consumo": "codice del consumo",
    "cod. contr. pubb.": "codice dei contratti pubblici",
    "cod. crisi imp.": "codice della crisi d'impresa e dell'insolvenza",
    "cod. giust. cont.": "codice di giustizia contabile",
    "cod. naut. diport.": "codice della nautica da diporto",
    "cod. nav.": "codice della navigazione",
    "cod. ord. mil.": "codice dell'ordinamento militare",
    "cod. pari opp.": "codice delle pari opportunità",
    "cod. pen.": "codice penale",
    "cod. post. telecom.": "codice postale e delle telecomunicazioni",
    "cod. proc. amm.": "codice del processo amministrativo",
    "cod. proc. civ": "codice di procedura civile",
    "cod. proc. pen.": "codice di procedura penale",
    "cod. proc. trib.": "codice del processo tributario",
    "cod. prop. ind.": "codice della proprietà industriale",
    "cod. prot. civ.": "codice della protezione civile",
    "cod. prot. dati": "codice in materia di protezione dei dati personali",
    "cod. strada": "codice della strada",
    "cod. ter. sett.": "codice del Terzo settore",
    "cod. turismo": "codice del turismo",
    "codice antimafia": "codice antimafia",
    "codice civile": "codice civile",
    "codice dei beni culturali e del paesaggio": "codice dei beni culturali e del paesaggio",
    "codice dei contratti pubblici": "codice dei contratti pubblici",
    "codice del terzo settore": "codice del Terzo settore",
    "codice del consumo": "codice del consumo",
    "codice del processo amministrativo": "codice del processo amministrativo",
    "codice del processo tributario": "codice del processo tributario",
    "codice del turismo": "codice del turismo",
    "codice dell'amministrazione digitale": "codice dell'amministrazione digitale",
    "codice dell'ordinamento militare": "codice dell'ordinamento militare",
    "codice della crisi d'impresa e dell'insolvenza": "codice della crisi d'impresa e dell'insolvenza",
    "codice della nautica da diporto": "codice della nautica da diporto",
    "codice della navigazione": "codice della navigazione",
    "codice della proprietà industriale": "codice della proprietà industriale",
    "codice della protezione civile": "codice della protezione civile",
    "codice della strada": "codice della strada",
    "codice delle assicurazioni private": "codice delle assicurazioni private",
    "codice delle comunicazioni elettroniche": "codice delle comunicazioni elettroniche",
    "codice delle pari opportunità": "codice delle pari opportunità",
    "codice di giustizia contabile": "codice di giustizia contabile",
    "codice di procedura civile": "codice di procedura civile",
    "codice di procedura penale": "codice di procedura penale",
    "codice in materia di protezione dei dati personali": "codice in materia di protezione dei dati personali",
    "codice penale": "codice penale",
    "codice postale e delle telecomunicazioni": "codice postale e delle telecomunicazioni",
    "com": "codice dell'ordinamento militare",
    "cost": "costituzione",
    "cost.": "costituzione",
    "costituzione": "costituzione",
    "cp": "codice penale",
    "cpa": "codice del processo amministrativo",
    "cpc": "codice di procedura civile",
    "cpd": "codice in materia di protezione dei dati personali",
    "cpet": "codice postale e delle telecomunicazioni",
    "cpi": "codice della proprietà industriale",
    "cpo": "codice delle pari opportunità",
    "cpp": "codice di procedura penale",
    "cpt": "codice del processo tributario",
    "cts": "codice del Terzo settore",
    "ctu": "codice del turismo",
    "disp. att. c.c.": "disposizioni per l'attuazione del Codice civile e disposizioni transitorie",
    "disp. att. c.p.c.": "disposizioni per l'attuazione del Codice di procedura civile e disposizioni transitorie",
    "disp. prel.": "preleggi",
    "disposizioni per l'attuazione del codice civile e disposizioni transitorie": "disposizioni per l'attuazione del Codice civile e disposizioni transitorie",
    "disposizioni per l'attuazione del codice di procedura civile e disposizioni transitorie": "disposizioni per l'attuazione del Codice di procedura civile e disposizioni transitorie",
    "norme amb.": "norme in materia ambientale",
    "norme in materia ambientale": "norme in materia ambientale",
    "prel.": "preleggi",
    "preleggi": "preleggi",
}


# ---------------------------------------------------------------------------
# EURLEX — routing for EU acts
# ---------------------------------------------------------------------------

EURLEX = {
    "tue": "https://eur-lex.europa.eu/legal-content/IT/TXT/HTML/?uri=CELEX:12016M/TXT",
    "tfue": "https://eur-lex.europa.eu/legal-content/IT/TXT/HTML/?uri=CELEX:12016E/TXT",
    "cdfue": "https://eur-lex.europa.eu/legal-content/IT/TXT/HTML/?uri=CELEX:12016P/TXT",
    "regolamento ue": "reg",
    "direttiva ue": "dir",
}


# ---------------------------------------------------------------------------
# BROCARDI CODICI — act type → Brocardi base URL
# ---------------------------------------------------------------------------

BROCARDI_CODICI = {
    "Costituzione": "https://www.brocardi.it/costituzione/",
    "Regolamento generale sulla protezione dei dati(Reg. UE 27 aprile 2016, n. 679)": "https://www.brocardi.it/regolamento-privacy-ue/",
    "Codice Civile (R.D. 16 marzo 1942, n. 262)": "https://www.brocardi.it/codice-civile/",
    "Preleggi": "https://www.brocardi.it/preleggi/",
    "Disposizioni per l'attuazione del codice civile e disposizioni transitorie(R.D. 30 marzo 1942, n. 318)": "https://www.brocardi.it/disposizioni-per-attuazione-del-codice-civile/",
    "Codice di procedura civile(R.D. 28 ottobre 1940, n. 1443)": "https://www.brocardi.it/codice-di-procedura-civile/",
    "Codice Penale(R.D. 19 ottobre 1930, n. 1398)": "https://www.brocardi.it/codice-penale/",
    "Codice di procedura penale(D.P.R. 22 settembre 1988, n. 447)": "https://www.brocardi.it/codice-di-procedura-penale/",
    "Codice della strada(D.lgs. 30 aprile 1992, n. 285)": "https://www.brocardi.it/codice-della-strada/",
    "Codice del processo tributario(D.lgs. 31 dicembre 1992, n. 546)": "https://www.brocardi.it/codice-del-processo-tributario/",
    "Codice della privacy(D.lgs. 30 giugno 2003, n. 196)": "https://www.brocardi.it/codice-della-privacy/",
    "Codice del consumo(D.lgs. 6 settembre 2005, n. 206)": "https://www.brocardi.it/codice-del-consumo/",
    "Codice delle assicurazioni private(D.lgs. 7 settembre 2005, n. 209)": "https://www.brocardi.it/codice-delle-assicurazioni-private/",
    "Codice dei beni culturali e del paesaggio(D.lgs. 22 gennaio 2004, n. 42)": "https://www.brocardi.it/codice-dei-beni-culturali-e-del-paesaggio/",
    "Codice del processo amministrativo(D.lgs. 2 luglio 2010, n. 104)": "https://www.brocardi.it/codice-del-processo-amministrativo/",
    "Codice del turismo(D.lgs. 23 maggio 2011, n. 79)": "https://www.brocardi.it/codice-del-turismo/",
    "Codice dell'ambiente(D.lgs. 3 aprile 2006, n. 152)": "https://www.brocardi.it/codice-dell-ambiente/",
    "Codice delle comunicazioni elettroniche(D.lgs. 1 agosto 2003, n. 259)": "https://www.brocardi.it/codice-delle-comunicazioni-elettroniche/",
    "Codice delle pari opportunità(D.lgs. 11 aprile 2006, n. 198)": "https://www.brocardi.it/codice-delle-pari-opportunita/",
    "Codice di giustizia contabile(D.lgs. 26 agosto 2016, n. 174)": "https://www.brocardi.it/codice-di-giustizia-contabile/",
    "Codice della nautica da diporto(D.lgs. 18 luglio 2005, n. 171)": "https://www.brocardi.it/codice-della-nautica-da-diporto/",
    "Codice della proprietà industriale(D.lgs. 10 febbraio 2005, n. 30)": "https://www.brocardi.it/codice-della-proprieta-industriale/",
    "Codice dell'amministrazione digitale(D.lgs. 7 marzo 2005, n. 82)": "https://www.brocardi.it/codice-dell-amministrazione-digitale/",
    "Codice antimafia(D.lgs. 6 settembre 2011, n. 159)": "https://www.brocardi.it/codice-antimafia/",
    "Codice del terzo settore(D.lgs. 3 luglio 2017, n. 117)": "https://www.brocardi.it/codice-terzo-settore/",
    "Codice della protezione civile(D.lgs. 2 gennaio 2018, n. 1)": "https://www.brocardi.it/codice-protezione-civile/",
    "Codice della crisi d'impresa e dell'insolvenza(D.lgs. 12 gennaio 2019, n. 14)": "https://www.brocardi.it/codice-crisi-impresa/",
    "Nuovo Codice Appalti (D. Lgs. 31 Marzo 2023, n. 36)(D.lgs. 31 marzo 2023, n. 36), Codice dei Contratti pubblici": "https://www.brocardi.it/nuovo-codice-appalti/",
    "Statuto dei lavoratori(L. 20 maggio 1970, n. 300)": "https://www.brocardi.it/statuto-lavoratori/",
    "Legge fallimentare(R.D. 16 marzo 1942, n. 267)": "https://www.brocardi.it/legge-fallimentare/",
    "Legge sul procedimento amministrativo(L. 7 agosto 1990, n. 241)": "https://www.brocardi.it/legge-sul-procedimento-amministrativo/",
    "Disciplina della responsabilità amministrativa delle persone giuridiche(D.lgs. 8 giugno 2001, n. 231)": "https://www.brocardi.it/responsabilita-amministrativa-persone-giuridiche/",
    "Testo unico bancario(D.lgs. 1 settembre 1993, n. 385)": "https://www.brocardi.it/testo-unico-bancario/",
    "Testo unico edilizia(D.P.R. 6 giugno 2001, n. 380)": "https://www.brocardi.it/testo-unico-edilizia/",
    "Testo unico sulla sicurezza sul lavoro(D.lgs. 9 aprile 2008, n. 81)": "https://www.brocardi.it/testo-unico-sicurezza-sul-lavoro/",
    "Testo unico delle imposte sui redditi(D.P.R. 22 dicembre 1986, n. 917)": "https://www.brocardi.it/testo-unico-imposte-redditi/",
    "Testo unico sul pubblico impiego(D.lgs. 30 marzo 2001, n. 165)": "https://www.brocardi.it/testo-unico-sul-pubblico-impiego/",
    "Testo unico degli enti locali(D.lgs. 18 agosto 2000, n. 267)": "https://www.brocardi.it/testo-unico-enti-locali/",
    "Mediazione finalizzata alla conciliazione delle controversie civili e commerciali(D.lgs. 4 marzo 2010, n. 28)": "https://www.brocardi.it/mediazione-controversie-civili-commerciali/",
    "Legge sull'ordinamento penitenziario(L. 26 luglio 1975, n. 354)": "https://www.brocardi.it/legge-ordinamento-penitenziario/",
    "Legge 104(L. 5 febbraio 1992, n. 104)": "https://www.brocardi.it/legge-104/",
    # Procedura civile - attuazione
    "Disposizioni di attuazione del codice di procedura civile(R.D. 18 dicembre 1941, n. 1368)": "https://www.brocardi.it/disposizioni-per-attuazione-codice-procedura-civile/",
    # Penale - disposizioni transitorie e minorile
    "Disposizioni di coordinamento e transitorie per il codice penale(R.D. 28 maggio 1931, n. 601)": "https://www.brocardi.it/disposizioni-transitorie-codice-penale/",
    "Codice Processo Penale Minorile(D.P.R. 22 settembre 1988, n. 448)": "https://www.brocardi.it/processo-penale-minorile/",
    # Famiglia e persone
    "Disposizioni in materia di separazione dei genitori e affidamento condiviso dei figli(L. 8 febbraio 2006, n. 54)": "https://www.brocardi.it/affido-condiviso/",
    "Legge sul divorzio(L. 1 dicembre 1970, n. 898)": "https://www.brocardi.it/legge-sul-divorzio/",
    "Regolamentazione delle unioni civili tra persone dello stesso sesso e disciplina delle convivenze(L. 20 maggio 2016, n. 76)": "https://www.brocardi.it/legge-cirinna/",
    "Legge sull'adozione(L. 4 maggio 1983, n. 184)": "https://www.brocardi.it/legge-sull-adozione/",
    "Norme in materia di procreazione medicalmente assistita(L. 19 febbraio 2004, n. 40)": "https://www.brocardi.it/procreazione-medicalmente-assistita/",
    "Legge sul biotestamento(L. 22 dicembre 2017, n. 219)": "https://www.brocardi.it/legge-biotestamento/",
    "Legge sull'aborto(L. 22 maggio 1978, n. 194)": "https://www.brocardi.it/legge-aborto/",
    # Lavoro
    "Disciplina organica dei contratti di lavoro e revisione della normativa in tema di mansioni(D.lgs. 15 giugno 2015, n. 81)": "https://www.brocardi.it/disciplina-organica-contratti-lavoro/",
    "Disposizioni in materia di contratto di lavoro a tempo indeterminato a tutele crescenti(D.lgs. 4 marzo 2015, n. 23)": "https://www.brocardi.it/contratto-lavoro-tutele-crescenti/",
    "Misure per la tutela del lavoro autonomo non imprenditoriale e misure volte a favorire il lavoro agile(L. 22 maggio 2017, n. 81)": "https://www.brocardi.it/lavoro-agile/",
    "Disposizioni per il riordino della normativa in materia di ammortizzatori sociali(D.lgs. 4 marzo 2015, n. 22)": "https://www.brocardi.it/ammortizzatori-sociali/",
    "Norme sui licenziamenti individuali(L. 15 luglio 1966, n. 604)": "https://www.brocardi.it/norme-sui-licenziamenti-individuali/",
    "Norme in materia di orario di lavoro(D.lgs. 8 aprile 2003, n. 66)": "https://www.brocardi.it/organizzazione-orario-lavoro/",
    "Testo unico in materia di tutela e sostegno della maternità e della paternità": "https://www.brocardi.it/testo-unico-sostegno-maternita-paternita/",
    "Contratto Collettivo Nazionale del Lavoro Domestico": "https://www.brocardi.it/contratto-collettivo-colf-badanti/",
    "Contratto Collettivo Nazionale del Turismo, Pubblici esercizi, Ristorazione collettiva e commerciale, Alberghi": "https://www.brocardi.it/contratto-collettivo-turismo/",
    # Professioni e responsabilità
    "Legge professionale forense(L. 31 dicembre 2012, n. 247)": "https://www.brocardi.it/legge-professione-forense/",
    "Responsabilità professionale del personale sanitario(L. 8 marzo 2017, n. 24)": "https://www.brocardi.it/resposabilita-professionale-personale-sanitario/",
    # Proprietà intellettuale
    "Legge sulla protezione del diritto d'autore(L. 22 aprile 1941, n. 633)": "https://www.brocardi.it/legge-diritto-autore/",
    # Locazioni e contratti agrari
    "Legge sulle locazioni abitative(D.lgs. 9 dicembre 1998, n. 431)": "https://www.brocardi.it/legge-locazioni-abitative/",
    "Legge equo canone(L. 27 luglio 1978, n. 392)": "https://www.brocardi.it/legge-equo-canone/",
    "Disposizioni per lo sviluppo della proprietà coltivatrice(L. 26 maggio 1965, n. 590)": "https://www.brocardi.it/disposizioni-sviluppo-proprieta-coltivatrice/",
    "Norme sui contratti agrari(L. 3 maggio 1982, n. 203)": "https://www.brocardi.it/norme-contratti-agrari/",
    # Diritto internazionale privato
    "Riforma del sistema italiano di diritto internazionale privato(L. 31 maggio 1995, n. 218)": "https://www.brocardi.it/legge-diritto-internazionale-privato/",
    # No-profit e associazioni
    "Legge quadro sul volontariato(L. 11 agosto 1991, n. 266)": "https://www.brocardi.it/legge-quadro-sul-volontariato/",
    "Legge sulle ONLUS(D.lgs. 4 dicembre 1997, n. 460)": "https://www.brocardi.it/legge-onlus/",
    "Disciplina delle associazioni di promozione sociale(L. 7 dicembre 2000, n. 383)": "https://www.brocardi.it/disciplina-delle-associazioni-di-promozione-sociale/",
    # Diritto tributario e fiscale
    "Legge sui reati tributari(D.lgs. 10 marzo 2000, n. 74)": "https://www.brocardi.it/legge-sui-reati-tributari/",
    "Testo unico dell'imposta di registro(D.P.R. 26 aprile 1986, n. 131)": "https://www.brocardi.it/testo-unico-imposta-registro/",
    "Testo unico IVA(D.P.R. 26 ottobre 1972, n. 633)": "https://www.brocardi.it/testo-unico-iva/",
    "Disposizioni comuni in materia di accertamento delle imposte sui redditi(D.P.R. 29 settembre 1973, n. 600)": "https://www.brocardi.it/disposizioni-accertamento-imposte-redditi/",
    "Disposizioni sulla riscossione delle imposte sul reddito(D.P.R. 29 settembre 1973, n. 602)": "https://www.brocardi.it/disposizioni-riscossione-imposte-redditi/",
    "Disposizioni in materia di accertamento con adesione e di conciliazione giudiziale(D.lgs. 19 giugno 1997, n. 218)": "https://www.brocardi.it/disposizioni-accertamento-adesione-conciliazione-giudiziale/",
    "Disposizioni sulle sanzioni amministrative per violazioni di norme tributarie(D.lgs. 18 dicembre 1997, n. 472)": "https://www.brocardi.it/disposizioni-sanzioni-amministrative-violazioni-norme-tributarie/",
    "Ordinamento degli organi speciali di giurisdizione tributaria ed organizzazione degli uffici di collaborazione(D.lgs. 31 dicembre 1992, n. 545)": "https://www.brocardi.it/ordinamento-organi-speciali-giurisdizione-tributaria/",
    "Statuto del contribuente(L. 27 luglio 2000, n. 212)": "https://www.brocardi.it/statuto-contribuente/",
    "Riordino della finanza degli enti territoriali(D.lgs. 30 dicembre 1992, n. 504)": "https://www.brocardi.it/finanza-enti-territoriali/",
    "Disposizioni urgenti in materia fiscale(D.L. 30 settembre 1994, n. 564)": "https://www.brocardi.it/disposizioni-urgenti-materia-fiscale/",
    "Testo Unico sulle successioni e donazioni(D.lgs. 31 ottobre 1990, n. 346)": "https://www.brocardi.it/testo-unico-successioni-donazioni/",
    # Testi unici aggiuntivi
    "Testo unico sull'immigrazione(D.lgs. 25 luglio 1998, n. 286)": "https://www.brocardi.it/testo-unico-immigrazione/",
    "Testo unico stupefacenti(D.P.R. 9 ottobre 1990, n. 309)": "https://www.brocardi.it/testo-unico-stupefacenti/",
    "Testo unico delle leggi di pubblica sicurezza(R.D. 18 giugno 1931, n. 773)": "https://www.brocardi.it/testo-unico-pubblica-sicurezza/",
    "Testo unico sull'assicurazione degli infortuni sul lavoro(D.P.R. 30 giugno 1965, n. 1124)": "https://www.brocardi.it/testo-unico-assicurazione-degli-infortuni-sul-lavoro/",
    "Testo unico sulle espropriazioni per pubblica utilità(D.P.R. 8 giugno 2001, n. 327)": "https://www.brocardi.it/testo-unico-espropriazioni-pubblica-utilita/",
    "Testo unico delle disposizioni in materia di intermediazione finanziaria(D.lgs. 24 febbraio 1998, n. 58)": "https://www.brocardi.it/testo-unico-intermediazione-finanziaria/",
    "Testo unico sull'agricoltura(D.lgs. 18 maggio 2001, n. 228)": "https://www.brocardi.it/testo-unico-agricoltura/",
    "Testo unico sulle piante officinali(D.lgs. 21 maggio 2018, n. 75)": "https://www.brocardi.it/testo-unico-piante-officinali/",
    "Testo unico in materia di società a partecipazione pubblica(D.lgs. 19 agosto 2016, n. 175)": "https://www.brocardi.it/testo-unico-societa-partecipazione-pubblica/",
    # Procedimento amministrativo
    "Semplificazione dei procedimenti in materia di ricorsi amministrativi(D.P.R. 24 novembre 1971, n. 1199)": "https://www.brocardi.it/ricorsi-amministrativi/",
    # Informatica pubblica
    "Regolamento posta elettronica certificata(D.P.R. 11 febbraio 2005, n. 68)": "https://www.brocardi.it/regolamento-posta-elettronica-certificata/",
    # Appalti abrogato
    "Codice degli appalti [ABROGATO](D.lgs. 12 aprile 2006, n. 163)": "https://www.brocardi.it/codice-degli-appalti/",
    # Decreti emergenza/economia (recenti)
    "Decreto lavoro 2023(D.L. 4 maggio 2023, n. 48)": "https://www.brocardi.it/decreto-lavoro-2023/",
    "Decreto \"Semplificazioni bis\"(D.L. 31 maggio 2021, n. 77)": "https://www.brocardi.it/decreto-semplificazioni-bis/",
    "Decreto \"Sostegni\"(D.L. 22 marzo 2021, n. 41)": "https://www.brocardi.it/decreto-sostegni/",
    "Decreto \"Rilancio\"(D.L. 19 maggio 2020, n. 34)": "https://www.brocardi.it/decreto-rilancio/",
    "Decreto \"Cura Italia\"(L. 24 aprile 2020, n. 27)": "https://www.brocardi.it/decreto-cura-italia/",
}

# Simplified lookup: lowercase act type → Brocardi URL
_BROCARDI_LOOKUP: dict[str, str] = {}
for _key, _url in BROCARDI_CODICI.items():
    _BROCARDI_LOOKUP[_key.lower()] = _url
    # Also index by the first part before parenthesis
    _short = _key.split("(")[0].strip().lower()
    if _short and _short not in _BROCARDI_LOOKUP:
        _BROCARDI_LOOKUP[_short] = _url


# ---------------------------------------------------------------------------
# BROCARDI SEARCH — act type normalization for Brocardi
# ---------------------------------------------------------------------------

BROCARDI_SEARCH = {
    "regio decreto": "R.D.",
    "regio.decreto": "R.D.",
    "legge": "L.",
    "decreto del presidente della repubblica": "D.P.R.",
    "decreto legislativo": "D.lgs.",
    "decreto legge": "D.L.",
    "decreto.del.presidente.della.repubblica": "D.P.R.",
    "decreto.legislativo": "D.lgs.",
    "decreto.legge": "D.L.",
}


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def extract_codice_details(codice_name: str) -> dict | None:
    """Extract date and act number from a codice URN in NORMATTIVA_URN_CODICI."""
    codice_name_lower = codice_name.lower().strip()
    urn = NORMATTIVA_URN_CODICI.get(codice_name_lower)
    if not urn:
        return None
    if ":" not in urn or ";" not in urn:
        return None

    match = re.match(r"^([^:]+):(\d{4}-\d{2}-\d{2});(\d+)(?::\d+)?$", urn)
    if match:
        tipo_atto_urn, data, numero = match.groups()
        return {
            "tipo_atto_reale": tipo_atto_urn.replace(".", " "),
            "data": data,
            "numero_atto": numero,
        }
    return None


def normalize_act_type(input_type: str) -> str:
    """Normalize act type abbreviation to full name using NORMATTIVA_SEARCH."""
    if input_type in {"TUE", "TFUE", "CDFUE"}:
        return input_type
    key = input_type.lower().strip()
    return NORMATTIVA_SEARCH.get(key, key)


def resolve_atto(name: str) -> dict | None:
    """Resolve a common act name to scraper parameters.

    Resolution chain:
    1. ATTI_NOTI (common names like GDPR, DORA, etc.)
    2. extract_codice_details (codice names → date + number from URN map)
    3. NORMATTIVA_SEARCH abbreviations → codice name → extract_codice_details
    """
    key = name.lower().strip()

    # 1. Direct match in ATTI_NOTI
    if key in ATTI_NOTI:
        return ATTI_NOTI[key]

    # 2. Try as codice name directly
    details = extract_codice_details(key)
    if details:
        return {
            "tipo_atto": key,
            "data": details["data"],
            "numero_atto": details["numero_atto"],
        }

    # 3. Normalize via NORMATTIVA_SEARCH, then try codice
    normalized = normalize_act_type(key)
    if normalized != key:
        # Check ATTI_NOTI with normalized name
        if normalized in ATTI_NOTI:
            return ATTI_NOTI[normalized]
        details = extract_codice_details(normalized)
        if details:
            return {
                "tipo_atto": normalized,
                "data": details["data"],
                "numero_atto": details["numero_atto"],
            }

    return None


def find_brocardi_url(tipo_atto: str, numero_atto: str = "") -> str | None:
    """Find the Brocardi base URL for a given act type."""
    tipo_lower = tipo_atto.lower().strip()

    # Direct match
    if tipo_lower in _BROCARDI_LOOKUP:
        return _BROCARDI_LOOKUP[tipo_lower]

    # Normalize and try
    normalized = normalize_act_type(tipo_lower)
    if normalized in _BROCARDI_LOOKUP:
        return _BROCARDI_LOOKUP[normalized]

    # Search with number in parenthesis
    if numero_atto:
        for key, url in _BROCARDI_LOOKUP.items():
            if tipo_lower in key and f"n. {numero_atto}" in key:
                return url

    # Fuzzy: search by substring
    for key, url in _BROCARDI_LOOKUP.items():
        if tipo_lower in key:
            return url

    return None


# ---------------------------------------------------------------------------
# FONTI PRINCIPALI — list of primary source types (used by prompts/resources)
# ---------------------------------------------------------------------------

FONTI_PRINCIPALI = [
    "legge", "decreto legge", "decreto legislativo", "costituzione",
    "d.p.r.", "TUE", "TFUE", "CDFUE", "Regolamento UE", "Direttiva UE",
    "regio decreto",
    "codice civile", "preleggi", "codice penale",
    "codice di procedura civile", "codice di procedura penale",
    "codice della navigazione", "codice postale e delle telecomunicazioni",
    "codice della strada", "codice del processo tributario",
    "codice in materia di protezione dei dati personali",
    "codice delle comunicazioni elettroniche",
    "codice dei beni culturali e del paesaggio",
    "codice della proprietà industriale",
    "codice dell'amministrazione digitale",
    "codice della nautica da diporto", "codice del consumo",
    "codice delle assicurazioni private", "norme in materia ambientale",
    "codice dei contratti pubblici", "codice delle pari opportunità",
    "codice dell'ordinamento militare", "codice del processo amministrativo",
    "codice del turismo", "codice antimafia", "codice di giustizia contabile",
    "codice del terzo settore", "codice della protezione civile",
    "codice della crisi d'impresa e dell'insolvenza",
]

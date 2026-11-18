"""Resolution maps for Italian legal acts — URN generation, abbreviations, Brocardi URLs."""

import re
from datetime import date, datetime
from typing import NamedTuple

from .. import _clock


# ---------------------------------------------------------------------------
# NORMATTIVA URN CODICI — codice name → partial URN
# ---------------------------------------------------------------------------

NORMATTIVA_URN_CODICI = {
    "costituzione": "costituzione",
    "codice penale": "regio.decreto:1930-10-19;1398:1",
    "codice di procedura civile": "regio.decreto:1940-10-28;1443:1",
    "disposizioni per l'attuazione del Codice di procedura civile e disposizioni transitorie": "regio.decreto:1941-12-18;1368:1",
    # The articles of these codes sit in an annex of the approving decree (":1", ":2"):
    # without it Normattiva serves the decree's own few articles (approval, repeals,
    # entry into force). Checked live on 21/10/2026, art. 3 of every row.
    # The combined entry reads the codice penale militare di pace (:1); di guerra is :2.
    "codici penali militari di pace e di guerra": "regio.decreto:1941-02-20;303:1",
    "codice penale militare di pace": "regio.decreto:1941-02-20;303:1",
    "codice penale militare di guerra": "regio.decreto:1941-02-20;303:2",
    "disposizioni di coordinamento, transitorie e di attuazione dei Codici penali militari di pace e di guerra": "regio.decreto:1941-09-09;1023",
    "codice civile": "regio.decreto:1942-03-16;262:2",
    "preleggi": "regio.decreto:1942-03-16;262:1",
    "disposizioni per l'attuazione del Codice civile e disposizioni transitorie": "regio.decreto:1942-03-30;318:1",
    "codice della navigazione": "regio.decreto:1942-03-30;327:1",
    "approvazione del Regolamento per l'esecuzione del Codice della navigazione (Navigazione marittima)": "decreto.del.presidente.della.repubblica:1952-02-15;328:1",
    "codice postale e delle telecomunicazioni": "decreto.del.presidente.della.repubblica:1973-03-29;156:1",
    "codice di procedura penale": "decreto.del.presidente.della.repubblica:1988-09-22;447",
    "norme di attuazione, di coordinamento e transitorie del codice di procedura penale": "decreto.legislativo:1989-07-28;271:1",
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
    "codice del turismo": "decreto.legislativo:2011-05-23;79:1",
    "codice antimafia": "decreto.legislativo:2011-09-06;159",
    "codice di giustizia contabile": "decreto.legislativo:2016-08-26;174:1",
    "codice del Terzo settore": "decreto.legislativo:2017-07-03;117",
    "codice della protezione civile": "decreto.legislativo:2018-01-02;1",
    "codice della crisi d'impresa e dell'insolvenza": "decreto.legislativo:2019-01-12;14",
    # From VisuaLex's table (tools/map.py at eca698dc), which had two regulations this one lacked.
    "regolamento per l'esecuzione del codice di procedura penale": "decreto.ministeriale:1989-09-30;334",
    "regolamento di attuazione del Codice della proprietà industriale": "decreto.ministeriale:2010-01-13;33",
}


_URN_CODICI_LOWER = {_k.lower(): _v for _k, _v in NORMATTIVA_URN_CODICI.items()}


#: Acts outside the table above whose citable articles are those of an annex: the
#: decree only approves the text "allegato al presente decreto". Their articles are
#: cited as "art. N D.P.R. 448/1988", so the annex is added to the URN of an article.
ARTICOLATO_IN_ALLEGATO: dict[str, str] = {
    "decreto.del.presidente.della.repubblica:1988-09-22;448": "1",  # c.p.p. minorile
    "regio.decreto:1931-06-18;773": "1",  # TULPS
    "decreto.legislativo:1990-10-31;346": "1",  # TU imposta successioni e donazioni
    "regio.decreto:1942-03-16;267": "1",  # legge fallimentare
}
_ALLEGATO_PER_ATTO = {
    (u.split(":")[0], u.split(":")[1][:4], u.split(";")[1]): a for u, a in ARTICOLATO_IN_ALLEGATO.items()
}


# From VisuaLex's table (tools/map.py at f47ac1b6), unchanged: the acts whose text is an annex of the
# decree and that VisuaLex keys by that annex, like a code by its default one. norma_data takes its
# allegato from ARTICOLATO_IN_ALLEGATO above (test_akn_merge checks the two hold the same acts).
ANNEXED_ACTS = {
    "regio.decreto:1931-06-18;773": "1",
    # The legge fallimentare, the c.p.p. minorile and the testo unico sulle successioni e
    # donazioni: the decree approves the text as its annex 1 (checked on Normattiva, 25 October
    # 2026: a dispositivo of one or two articles, «È approvato il testo, allegato…»).
    "regio.decreto:1942-03-16;267": "1",
    "decreto.del.presidente.della.repubblica:1988-09-22;448": "1",
    "decreto.legislativo:1990-10-31;346": "1",
}


# From VisuaLex's table (tools/map.py at f47ac1b6), unchanged.
# An annex of a code's decree, or an act of the codes table, cited by a sigla of its own
# (owner, G-369, 22 October 2026: «sì a tutto l'elenco, preleggi come già deciso»). Keyed by
# the annex's identity, «<decree>:<annex>», as a URN writes it; the heading is the long form.
# Any other annex of a code's decree is cited by the decree with «(Allegato N)». Mirrored by
# ANNEX_SIGLE and ANNEX_HEADINGS in the web's and the server's actTypes.ts and in MERL-T's
# utils/map.py.
ANNEX_SIGLE = {
    "regio.decreto:1942-03-16;262:1": "preleggi",
    "decreto.legislativo:2010-07-02;104:3": "disp. att. c.p.a.",
    "decreto.legislativo:2010-07-02;104:4": "disp. trans. c.p.a.",
    "decreto.legislativo:2010-07-02;104:5": "disp. coord. c.p.a.",
    "decreto.legislativo:2016-08-26;174:2": "disp. att. c.g.c.",
    "decreto.legislativo:2016-08-26;174:3": "disp. trans. c.g.c.",
    "regio.decreto:1941-02-20;303:1": "c.p.m.p.",
    "regio.decreto:1941-02-20;303:2": "c.p.m.g.",
    "decreto.legislativo:1989-07-28;271:1": "disp. att. c.p.p.",
    "decreto.del.presidente.della.repubblica:1952-02-15;328:1": "reg. nav. mar.",
}

ANNEX_HEADINGS = {
    "regio.decreto:1942-03-16;262:1": "Preleggi",
    "decreto.legislativo:2010-07-02;104:3": "Norme di attuazione del codice del processo amministrativo",
    "decreto.legislativo:2010-07-02;104:4": "Norme transitorie del codice del processo amministrativo",
    "decreto.legislativo:2010-07-02;104:5": "Norme di coordinamento e abrogazioni del codice del processo amministrativo",
    "decreto.legislativo:2016-08-26;174:2": "Norme di attuazione del codice di giustizia contabile",
    "decreto.legislativo:2016-08-26;174:3": "Norme transitorie e abrogazioni del codice di giustizia contabile",
    "regio.decreto:1941-02-20;303:1": "Codice penale militare di pace",
    "regio.decreto:1941-02-20;303:2": "Codice penale militare di guerra",
    "decreto.legislativo:1989-07-28;271:1": "Norme di attuazione del codice di procedura penale",
    "decreto.del.presidente.della.repubblica:1952-02-15;328:1": "Regolamento per l'esecuzione del codice della navigazione (navigazione marittima)",
}


def code_row_of_annex(identity: str) -> "tuple[str, str] | None":
    """The codes-table row an annex identity («<decree>:<annex>») belongs to, as (name, annex):
    the row keyed by that very annex, else the row of the same decree (the c.p.a.'s, for its
    annex 3). None when no code is approved by that decree."""
    base, _, annex = identity.rpartition(":")
    same_decree = None
    for name, urn in NORMATTIVA_URN_CODICI.items():
        if urn == identity:
            return name, annex
        if urn.rpartition(":")[0] == base and re.search(r";\d+:\w+$", urn):
            same_decree = same_decree or (name, annex)
    return same_decree


def act_default_annex(act: str) -> "str | None":
    """The annex that is the act's text, for an act URN such as
    «regio.decreto:1931-06-18;773» (with or without «urn:nir:stato:» or the resolver
    before it), or None."""
    tail = (act or "").split("urn:nir:stato:")[-1].split("~")[0].strip().lower()
    return ANNEXED_ACTS.get(tail)


def articolato_in_allegato(act_urn: str, date: str, numero: str) -> "str | None":
    """The annex holding the articles of this act, if any. Type, year and number identify it:
    a citation with the year only ("D.P.R. 448/1988") carries a placeholder day and month."""
    return _ALLEGATO_PER_ATTO.get((act_urn, (date or "")[:4], str(numero)))


# ---------------------------------------------------------------------------
# ATTI NOTI — common names → scraper parameters
# ---------------------------------------------------------------------------

#: The one act read from the Consiglio nazionale forense's site (lib/cnf), not from Normattiva.
CODICE_DEONTOLOGICO_FORENSE = "codice deontologico forense"

ATTI_NOTI = {
    "gdpr": {"tipo_atto": "regolamento ue", "data": "2016", "numero_atto": "679"},
    "rgpd": {"tipo_atto": "regolamento ue", "data": "2016", "numero_atto": "679"},
    "regolamento privacy": {"tipo_atto": "regolamento ue", "data": "2016", "numero_atto": "679"},
    "regolamento generale protezione dati": {"tipo_atto": "regolamento ue", "data": "2016", "numero_atto": "679"},
    "regolamento generale sulla protezione dei dati": {"tipo_atto": "regolamento ue", "data": "2016", "numero_atto": "679"},
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
    "testo unico sicurezza": {"tipo_atto": "decreto legislativo", "data": "2008-04-09", "numero_atto": "81"},
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
    "tub": {"tipo_atto": "decreto legislativo", "data": "1993-09-01", "numero_atto": "385"},
    "tuf": {"tipo_atto": "decreto legislativo", "data": "1998-02-24", "numero_atto": "58"},
    # «TUIR» and its long names follow the date: SIGLE_DATATE (LI-086).
    # EU treaties — Norma.url() routes these to the fixed CELEX pages in EURLEX
    "tue": {"tipo_atto": "TUE", "data": "", "numero_atto": ""},
    "trattato sull'unione europea": {"tipo_atto": "TUE", "data": "", "numero_atto": ""},
    "tfue": {"tipo_atto": "TFUE", "data": "", "numero_atto": ""},
    "trattato sul funzionamento dell'unione europea": {"tipo_atto": "TFUE", "data": "", "numero_atto": ""},
    "cdfue": {"tipo_atto": "CDFUE", "data": "", "numero_atto": ""},
    "carta di nizza": {"tipo_atto": "CDFUE", "data": "", "numero_atto": ""},
    "carta dei diritti fondamentali dell'unione europea": {"tipo_atto": "CDFUE", "data": "", "numero_atto": ""},
    # EU compliance acts
    "dsa": {"tipo_atto": "regolamento ue", "data": "2022", "numero_atto": "2065"},
    "digital services act": {"tipo_atto": "regolamento ue", "data": "2022", "numero_atto": "2065"},
    "dma": {"tipo_atto": "regolamento ue", "data": "2022", "numero_atto": "1925"},
    "digital markets act": {"tipo_atto": "regolamento ue", "data": "2022", "numero_atto": "1925"},
    "data act": {"tipo_atto": "regolamento ue", "data": "2023", "numero_atto": "2854"},
    "data governance act": {"tipo_atto": "regolamento ue", "data": "2022", "numero_atto": "868"},
    "dga": {"tipo_atto": "regolamento ue", "data": "2022", "numero_atto": "868"},
    "eidas": {"tipo_atto": "regolamento ue", "data": "2014", "numero_atto": "910"},
    "eidas2": {"tipo_atto": "regolamento ue", "data": "2024", "numero_atto": "1183"},
    "cyber resilience act": {"tipo_atto": "regolamento ue", "data": "2024", "numero_atto": "2847"},
    "cra": {"tipo_atto": "regolamento ue", "data": "2024", "numero_atto": "2847"},
    "mica": {"tipo_atto": "regolamento ue", "data": "2023", "numero_atto": "1114"},
    # Financial-market regulations by the names an external citation corpus gives them (G-440). CELLAR titles
    # checked 11 November 2026. «Prospetto», «DLT» and «SAFE» are keyed only after «regolamento»:
    # alone they are a common noun, an acronym of a technology and an English word. «MAR» is keyed
    # bare but never read from a date's «mar.» (see SIGLE_COME_MESI).
    "mar": {"tipo_atto": "regolamento ue", "data": "2014", "numero_atto": "596"},
    "market abuse regulation": {"tipo_atto": "regolamento ue", "data": "2014", "numero_atto": "596"},
    "regolamento sugli abusi di mercato": {"tipo_atto": "regolamento ue", "data": "2014", "numero_atto": "596"},
    "regolamento europeo sugli abusi di mercato": {"tipo_atto": "regolamento ue", "data": "2014", "numero_atto": "596"},
    "micar": {"tipo_atto": "regolamento ue", "data": "2023", "numero_atto": "1114"},
    "mifir": {"tipo_atto": "regolamento ue", "data": "2014", "numero_atto": "600"},
    "regolamento prospetto": {"tipo_atto": "regolamento ue", "data": "2017", "numero_atto": "1129"},
    "regolamento dlt": {"tipo_atto": "regolamento ue", "data": "2022", "numero_atto": "858"},
    "regolamento pilota dlt": {"tipo_atto": "regolamento ue", "data": "2022", "numero_atto": "858"},
    "csdr": {"tipo_atto": "regolamento ue", "data": "2014", "numero_atto": "909"},
    # SAFE: reg. (UE) 2025/1106 of the Council (Security Action for Europe), so named by the
    # decisions of an external citation corpus (confirmed against the corpus documents, 11 November 2026).
    "regolamento safe": {"tipo_atto": "regolamento ue", "data": "2025", "numero_atto": "1106"},
    "regolamento sull'ia": {"tipo_atto": "regolamento ue", "data": "2024", "numero_atto": "1689"},
    "regolamento sull'intelligenza artificiale": {"tipo_atto": "regolamento ue", "data": "2024", "numero_atto": "1689"},
    "regolamento europeo sull'intelligenza artificiale": {"tipo_atto": "regolamento ue", "data": "2024", "numero_atto": "1689"},
    "machinery regulation": {"tipo_atto": "regolamento ue", "data": "2023", "numero_atto": "1230"},
    "direttiva whistleblowing": {"tipo_atto": "direttiva ue", "data": "2019", "numero_atto": "1937"},
    "whistleblowing": {"tipo_atto": "direttiva ue", "data": "2019", "numero_atto": "1937"},
    "direttiva nis": {"tipo_atto": "direttiva ue", "data": "2016", "numero_atto": "1148"},
    "nis": {"tipo_atto": "direttiva ue", "data": "2016", "numero_atto": "1148"},
    "psd2": {"tipo_atto": "direttiva ue", "data": "2015", "numero_atto": "2366"},
    "csrd": {"tipo_atto": "direttiva ue", "data": "2022", "numero_atto": "2464"},
    "csddd": {"tipo_atto": "direttiva ue", "data": "2024", "numero_atto": "1760"},
    "european accessibility act": {"tipo_atto": "direttiva ue", "data": "2019", "numero_atto": "882"},
    "eprivacy": {"tipo_atto": "direttiva ue", "data": "2002", "numero_atto": "58"},
    "direttiva eprivacy": {"tipo_atto": "direttiva ue", "data": "2002", "numero_atto": "58"},
    # Consumer Credit Directive 2: dir. (UE) 2023/2225 of 18 October 2023 (CELLAR title, checked
    # 9 November 2026). «Direttiva credito ai consumatori» is deliberately absent: it also names
    # dir. 2008/48/CE, which 2023/2225 repeals only from 20 November 2026 (G-440).
    "ccd2": {"tipo_atto": "direttiva ue", "data": "2023", "numero_atto": "2225"},
    "ccd 2": {"tipo_atto": "direttiva ue", "data": "2023", "numero_atto": "2225"},
    "ccd ii": {"tipo_atto": "direttiva ue", "data": "2023", "numero_atto": "2225"},
    "direttiva ccd2": {"tipo_atto": "direttiva ue", "data": "2023", "numero_atto": "2225"},
    "direttiva ccd 2": {"tipo_atto": "direttiva ue", "data": "2023", "numero_atto": "2225"},
    # The testo unico della giustizia tributaria («TUGT») is in SIGLE_DATATE: it applies from a
    # later date than it entered into force, and says so (LI-086).
    # The codice deontologico forense: a CNF act, not on Normattiva. Norma routes it to the
    # PDF the CNF publishes (lib/cnf). «CDF» is deliberately absent: it is also read as the
    # Carta dei diritti fondamentali, and «art. 47 CDF» served from the code would be the
    # wrong article; unresolved, it is suggested instead (and the citation gate asks for it).
    CODICE_DEONTOLOGICO_FORENSE: {"tipo_atto": CODICE_DEONTOLOGICO_FORENSE, "data": "", "numero_atto": ""},
    "nuovo codice deontologico forense": {"tipo_atto": CODICE_DEONTOLOGICO_FORENSE, "data": "", "numero_atto": ""},
    "codice deontologico degli avvocati": {"tipo_atto": CODICE_DEONTOLOGICO_FORENSE, "data": "", "numero_atto": ""},
    "ncdf": {"tipo_atto": CODICE_DEONTOLOGICO_FORENSE, "data": "", "numero_atto": ""},
}


# ---------------------------------------------------------------------------
# FONTI NON COPERTE — law the resolver knows by name and no tool reads
# ---------------------------------------------------------------------------

_NORME_INTEGRATIVE_CORTE_COST = (
    "le «Norme integrative per i giudizi davanti alla Corte costituzionale» sono una deliberazione "
    "della Corte costituzionale (delibera 22 luglio 2021, GU n. 262 del 3 novembre 2021, poi "
    "modificata con delibere pubblicate anch'esse in Gazzetta Ufficiale), non un atto legislativo: "
    "Normattiva non le pubblica, quindi il loro testo non è disponibile qui. Testo come pubblicato: "
    "Gazzetta Ufficiale, codice redazionale 21A06516 (senza le modifiche successive)."
)

#: A source a citation may name that no tool reads, by name, with what cite_law answers:
#: what the source is and where its official text is, never a nearby act (no suggestions).
#: Every key names the source unambiguously: a bare «norme integrative» (a CCNL's, a
#: regolamento's) is not keyed, and stays an ordinary unresolved name.
#: Facts checked 9 November 2026 (G-440): Normattiva's search and URNs have no deliberation
#: of the Court; the Gazzetta Ufficiale lists the 2021 text and its later amendments.
_CONSOB = (
    "il {nome} è un regolamento della Consob ({estremi}), non un atto legislativo: Normattiva ed "
    "EUR-Lex non lo pubblicano, quindi il suo testo non è disponibile qui. Il testo vigente è sul "
    "sito della Consob (Regolamentazione); la delibera di adozione si legge con gli strumenti "
    "CONSOB per numero."
)

_CEDU_TESTO = (
    "il testo vigente non è disponibile qui: quello allegato alla legge di esecuzione su Normattiva "
    "è il testo originario, e i Protocolli successivi hanno modificato e rinumerato parte della "
    "Convenzione, quindi servirlo come vigente rischierebbe l'articolo sbagliato. Testo ufficiale: "
    "Consiglio d'Europa."
)

_TRATTATO = (
    "{nome} è un trattato internazionale ({estremi}): cite_law legge le fonti italiane ed europee, "
    "non i trattati, quindi il suo testo non è disponibile qui."
)


def _fonti(messaggio: str, *nomi: str) -> dict[str, str]:
    return {nome: messaggio for nome in nomi}


#: Facts of the entries below, checked 11 November 2026 (G-440): Consob's numbers on consob.it
#: (delibere 11971, 17221, 20249); the laws of ratification on Normattiva (their titles).
#: Bare sigle that name something else too («CSE», «Convenzione di Ginevra») are not keyed.
FONTI_NON_COPERTE: dict[str, str] = {
    **_fonti(_CONSOB.format(nome="Regolamento Emittenti",
                            estremi="delibera 14 maggio 1999, n. 11971, attuativa del d.lgs. 58/1998"),
             "regolamento emittenti", "regolamento emittenti consob", "regolamento consob emittenti",
             "reg. emittenti", "reg. consob 11971/1999", "delibera consob n. 11971/1999",
             "regolamento consob n. 11971/1999", "regolamento consob 11971/1999"),
    **_fonti(_CONSOB.format(nome="Regolamento OPC (operazioni con parti correlate)",
                            estremi="delibera n. 17221"),
             "regolamento opc", "regolamento opc consob", "regolamento consob opc",
             "regolamento operazioni con parti correlate", "regolamento parti correlate"),
    **_fonti(_CONSOB.format(nome="Regolamento Mercati", estremi="delibera n. 20249, attuativa del d.lgs. 58/1998"),
             "regolamento mercati", "regolamento mercati consob", "regolamento consob mercati"),
    **_fonti("la CEDU è la Convenzione per la salvaguardia dei diritti dell'uomo e delle libertà "
             "fondamentali (Roma, 4 novembre 1950), resa esecutiva in Italia con la legge 4 agosto 1955, "
             "n. 848: " + _CEDU_TESTO,
             "cedu", "convenzione europea dei diritti dell'uomo",
             "convenzione europea per la salvaguardia dei diritti dell'uomo",
             "convenzione europea per la salvaguardia dei diritti dell'uomo e delle libertà fondamentali",
             "convenzione per la salvaguardia dei diritti dell'uomo e delle libertà fondamentali",
             "convenzione edu"),
    **_fonti("il Protocollo addizionale (n. 1) alla CEDU (Parigi, 20 marzo 1952) è reso esecutivo con "
             "la legge 4 agosto 1955, n. 848, insieme alla Convenzione: " + _CEDU_TESTO,
             "prot. addiz. cedu", "protocollo addizionale alla cedu", "primo protocollo addizionale alla cedu",
             "protocollo addizionale alla convenzione europea dei diritti dell'uomo",
             "primo protocollo addizionale alla convenzione europea dei diritti dell'uomo",
             "protocollo n. 1 cedu", "prot. n. 1 cedu", "protocollo 1 cedu", "prot. 1 cedu"),
    **_fonti("il Protocollo n. 4 alla CEDU (Strasburgo, 16 settembre 1963) è reso esecutivo con il "
             "d.P.R. 14 aprile 1982, n. 217: " + _CEDU_TESTO,
             "protocollo n. 4 cedu", "prot. n. 4 cedu", "protocollo 4 cedu", "prot. 4 cedu"),
    **_fonti("il Protocollo n. 7 alla CEDU (Strasburgo, 22 novembre 1984) è ratificato con la legge "
             "9 aprile 1990, n. 98: " + _CEDU_TESTO,
             "protocollo n. 7 cedu", "prot. n. 7 cedu", "protocollo 7 cedu", "prot. 7 cedu"),
    **_fonti(_TRATTATO.format(nome="la Carta sociale europea (riveduta)",
                              estremi="Strasburgo, 3 maggio 1996, ratificata con la legge 9 febbraio 1999, n. 30"),
             "carta sociale europea", "carta sociale europea riveduta"),
    **_fonti(_TRATTATO.format(nome="la Convenzione di Aarhus",
                              estremi="Aarhus, 25 giugno 1998, ratificata con la legge 16 marzo 2001, n. 108"),
             "convenzione di aarhus"),
    **_fonti(_TRATTATO.format(nome="il Patto internazionale sui diritti civili e politici",
                              estremi="New York, 19 dicembre 1966, ratificato con la legge 25 ottobre 1977, n. 881"),
             "patto internazionale sui diritti civili e politici",
             "patto internazionale relativo ai diritti civili e politici"),
    **_fonti(_TRATTATO.format(nome="la Convenzione sui diritti del fanciullo",
                              estremi="New York, 20 novembre 1989, ratificata con la legge 27 maggio 1991, n. 176"),
             "convenzione sui diritti del fanciullo", "convenzione onu sui diritti del fanciullo"),
    **_fonti(_TRATTATO.format(nome="la CEDAW (Convenzione sull'eliminazione di ogni forma di discriminazione "
                                   "nei confronti della donna)",
                              estremi="New York, 18 dicembre 1979, ratificata con la legge 14 marzo 1985, n. 132"),
             "cedaw"),
    **_fonti(_TRATTATO.format(nome="la Convenzione MARPOL 73/78",
                              estremi="Londra, 2 novembre 1973, ratificata con la legge 29 settembre 1980, n. 662; "
                                      "Protocollo del 17 febbraio 1978, legge 4 giugno 1982, n. 438"),
             "convenzione marpol 73/78", "convenzione marpol", "marpol 73/78", "marpol"),
}
FONTI_NON_COPERTE.update({
    nome: _NORME_INTEGRATIVE_CORTE_COST
    for nome in (
        "norme integrative per i giudizi davanti alla corte costituzionale",
        "norme integrative per i giudizi dinanzi alla corte costituzionale",
        "norme integrative per i giudizi innanzi alla corte costituzionale",
        "norme integrative della corte costituzionale",
        "norme integrative corte costituzionale",
        "norme integrative corte cost.",
        # «N.I.», the sigla the Court's own decisions use, only together with the Court.
        "n.i. corte cost.",
        "n.i. corte cost",
        "n.i. corte costituzionale",
        "n.i. della corte costituzionale",
    )
})


#: Names that more than one act answers, refused on purpose (G-440): resolving them would pick
#: one act for the reader. The value names the acts where they are known, checked 11 November
#: 2026. The fiscal testi unici that replace an older act in time are not here: they follow
#: the date (SIGLE_DATATE, LI-086).
NOMI_AMBIGUI: dict[str, str] = {
    "tus": "testo unico sicurezza, stupefacenti, successioni…",
    # Two acts at the same date (LI-086): the codice dell'ambiente («testo unico ambientale») and
    # the testo unico accise, «TUA» in the Agenzia delle dogane's practice (circolare 13/2025,
    # «art. 29 del TUA»). No new testo unico accise replaces d.lgs. 504/1995 (checked 18 November
    # 2026), so the date cannot split them.
    "tua": "d.lgs. 3 aprile 2006, n. 152, codice dell'ambiente, o d.lgs. 26 ottobre 1995, n. 504, "
           "testo unico accise",
    # Three codes over time, each titled «codice dei contratti pubblici» (checked on Normattiva).
    # With an explicit date the resolver picks the one in force (SIGLE_DATATE_CON_DATA).
    "cod. app.": "d.lgs. 12 aprile 2006, n. 163, 18 aprile 2016, n. 50, o 31 marzo 2023, n. 36",
    # The short name is TUSMA's (d.lgs. 208/2021, art. 1) and the start of the title the
    # d.lgs. 177/2005 had from 2010, «testo unico dei servizi di media audiovisivi e radiofonici».
    "testo unico dei servizi di media audiovisivi": "d.lgs. 8 novembre 2021, n. 208, o d.lgs. 31 luglio 2005, n. 177",
    "testo unico servizi media audiovisivi": "d.lgs. 8 novembre 2021, n. 208, o d.lgs. 31 luglio 2005, n. 177",
    **dict.fromkeys((
        "tu rinnovabili", "testo unico rinnovabili", "tufer", "decreto fer", "decreto cer",
        "decreto trasparenza", "decreto semplificazioni", "riforma cartabia",
        "s.l.", "sl", "tui", "l.p.a.", "lpa",
    ), ""),
}


def nome_ambiguo(name: str, *, data: "date | str | None" = None) -> "str | None":
    """What cite_law answers for a name more than one act answers (``NOMI_AMBIGUI``), else None.

    A name the tables resolve is never ambiguous: the key «cgc» once caught «c.g.c.» (the
    codice di giustizia contabile) through the dotted-acronym collapse of ``_candidate_keys``.
    *data* is the reference date ``resolve_atto`` takes: «cod. app.» with a date is one code.
    """
    if resolve_atto(name, data=data):
        return None
    for key in _candidate_keys(name):
        if key in NOMI_AMBIGUI:
            quali = NOMI_AMBIGUI[key]
            return (f"«{name.strip()}» può indicare atti diversi" + (f" ({quali})" if quali else "")
                    + ": cita l'atto per tipo, data e numero (es. «d.lgs. n/aaaa»)")
    return None


def fonte_non_coperta(name: str) -> "str | None":
    """What cite_law answers for a source no tool reads (``FONTI_NON_COPERTE``, a regional or
    provincial law), else None."""
    if locale := fonte_locale(name):
        return locale
    for key in _candidate_keys(name):
        if key in FONTI_NON_COPERTE:
            return FONTI_NON_COPERTE[key]
    return None


# ---------------------------------------------------------------------------
# LEGGI REGIONALI — not covered (LI-086), never read as a State law
# ---------------------------------------------------------------------------
#
# No tool reads a regional law. Normattiva's resolver answers a regional URN with the page of
# the State's act of the same year and number (see act_dates.py), so «l.r. 65/2014» served
# through Normattiva would be the legge 65/2014 of the State, in silence: the worst answer.
# A regional citation is refused as a source not covered, before any table or pattern, and no
# URN is built for it (Norma.url). Real coverage is the regions branch's (LI-076), not this.

#: What cite_law answers for a regional law (one sentence, no promise of coverage).
LEGGI_REGIONALI_NON_COPERTE = (
    "le leggi regionali non sono coperte dai tool di questo server: verifica il testo sul "
    "Bollettino ufficiale o sulla banca dati della Regione"
)

_MESI_ESTESI = ("gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|"
                "novembre|dicembre")
#: The twenty regions as a citation names them («l.r. Toscana», «legge della Regione Siciliana»).
_REGIONI = (r"abruzzo|basilicata|calabria|campania|emilia[\s-]?romagna|friuli[\s-]?venezia[\s-]?giulia|"
            r"lazio|liguria|lombardia|marche|molise|piemonte|puglia|sardegna|sicilia(?:na)?|toscana|"
            r"trentino[\s\-–—/]*alto[\s\-–—/]*adige(?:\s?/\s?s(?:[üu]|ue)dtirol)?|umbria|valle\s+d['’]\s?aosta|veneto")
#: «l.r.», «L.R.», «l. r.», «LR», «L.R.T.»; «l. reg.», «legge reg.», «legge regionale».
_SIGLA_REGIONALE = r"(?:l\.?\s?r\.?(?:\s?t\.)?|l\.\s?reg\.|legge\s+reg(?:ionale\b|\.))"
#: An act's number and date as a citation writes them: «10 novembre 2014, n. 65», «n. 3/2015»,
#: «65/2014», «n. 65 del 10 novembre 2014», «n. 3 del 2015». One separator class per gap
#: (``[\s,]*``): «\s*,?\s*» splits a run of spaces two ways, and the gate reads long prose.
_ESTREMI = (rf"(?:\d{{1,2}}(?:\s?[°º])?\s+(?:{_MESI_ESTESI})\s+\d{{4}}[\s,]*n\.?\s*\d+"
            r"|(?:n\.?\s*)?\d+\s*/\s*\d{2,4}\b"
            rf"|(?:n\.?\s*)?\d+\s+del\s+\d{{1,2}}(?:\s?[°º])?\s+(?:{_MESI_ESTESI})\s+\d{{4}}"
            r"|(?:n\.?\s*)?\d+\s+del\s+\d{4}\b)")
#: What may sit between an act's extremes and its Region or province: blanks, commas, a bracket,
#: a slash or a dash («L. 13/1997 – Trento», «L. 65/2014/Toscana», «legge 65/2014 [Toscana]»).
#: One class, so a run of separators is read one way only.
_SEP_LOCALE = r"[\s,(\[/–—-]*"
#: The preposition before a Region or province: «della», «dalla», «del», «di», «dell'».
_DI = r"(?:(?:della|dalla|del|di)\s+|dell['’]\s?)"
#: «Regione Toscana», «Regione autonoma della Sardegna», «Reg. Toscana», «R. Toscana», «della
#: Toscana», «dell'Emilia-Romagna», «(Toscana)».
_REGIONE = (rf"{_DI}?(?:(?:regione|reg\.|r\.)\s*(?:autonoma\s+)?(?:(?:della|del|dell['’])\s*)?)?"
            rf"(?:{_REGIONI})\b")
#: «legge» as the State patterns read it (core.riferimenti._TIPO_ALT): «legge», «L.», «L», «l.».
#: Any spelling of «legge» they take must be read here too, or «L. 65/2014 della Regione Toscana»
#: falls to the State's legge 65/2014.
_LEGGE = r"(?:legge|l\b\.?)"
#: A name that starts as a regional law does: a sigla, «legge (della) Regione …», or a State-like
#: «legge 10 novembre 2014, n. 65 della Regione …», «L. 65/2014 (Toscana)», «legge 65/2014 Reg.
#: Toscana» (the forms that would fall to the State's act of that number).
_NOME_REGIONALE = re.compile(
    rf"^(?:{_SIGLA_REGIONALE}(?![a-zà-ù])|{_LEGGE}\s*(?:della\s+)?(?:regione|reg\.)(?![a-zà-ù])"
    rf"|{_LEGGE}\s*{_ESTREMI}{_SEP_LOCALE}(?:{_DI}?(?:regione|reg\.)(?![a-zà-ù])|{_REGIONE}|regionale\b))",
    re.IGNORECASE,
)
#: A regional law cited in prose: a sigla or «legge della Regione X» with the act's extremes (after
#: a sigla, «n. 3» alone too), or the extremes followed by the Region. A number is required: «la
#: legge regionale» alone is not a citation.
LEGGE_REGIONALE_NEL_TESTO = re.compile(
    rf"\b(?:{_SIGLA_REGIONALE}(?![a-zà-ù])[\s,]*(?:{_REGIONE}[\s,]*)?(?:{_ESTREMI}|n\.\s*\d+\b)"
    rf"|{_LEGGE}\s*(?:della\s+)?(?:regione|reg\.)\s*(?:autonoma\s+)?(?:(?:della|del|dell['’])\s*)?"
    rf"(?:{_REGIONI})\b[\s,]*{_ESTREMI}"
    rf"|{_LEGGE}\s*{_ESTREMI}{_SEP_LOCALE}(?:{_REGIONE}|regionale\b))",
    re.IGNORECASE,
)


def legge_regionale(name: str) -> bool:
    """Whether an act name is a regional law's («l.r. Toscana 65/2014», «legge regionale 12 marzo
    2015, n. 3», «L.R. n. 3/2015», «legge 10 novembre 2014, n. 65 della Regione Toscana»)."""
    return bool(_NOME_REGIONALE.match(_strip_leading_words(_normalize_key(name or ""))))


# ---------------------------------------------------------------------------
# LEGGI PROVINCIALI — the autonomous provinces of Trento and Bolzano, as the regional laws
# ---------------------------------------------------------------------------
#
# The laws of the Province autonome di Trento e di Bolzano have the regional laws' place: no
# tool reads them, and «legge 13/1997 della Provincia autonoma di Trento» read through the State
# patterns would be the State's legge 13/1997. The same guard: «fonte non coperta», never
# resolved, no Normattiva address, a warning in the citation gate.

#: What cite_law answers for a provincial law (one sentence, no promise of coverage).
LEGGI_PROVINCIALI_NON_COPERTE = (
    "le leggi provinciali delle Province autonome di Trento e di Bolzano non sono coperte dai tool di "
    "questo server: verifica il testo sul Bollettino ufficiale della Regione Trentino-Alto Adige/Südtirol "
    "o sulla banca dati della Provincia"
)

#: The two autonomous provinces as a citation names them («Trento», «Bolzano/Alto Adige», «Bozen»,
#: «del Trentino», «provincia trentina»). «Trentino-Alto Adige» is the Region, never a province.
_PROVINCE = (r"(?:trento|trentin[oa](?![\s\-–—/]*alto)|bolzano(?:\s?/\s?alto\s+adige)?"
             r"|alto\s+adige(?:\s?/\s?s(?:[üu]|ue)dtirol)?|altoatesin[oa]|s(?:[üu]|ue)dtirol|bozen)")
#: «l.p.», «L.P.», «l. p.», «LP»; «l. prov.», «legge prov.», «legge provinciale». Never «l.p.a.»,
#: «lpa» or «l. proc. amm.» (keys of the tables): neither a letter nor another dot right after
#: the sigla, so «l.p.a.» cannot match as «l.p» either.
_SIGLA_PROVINCIALE = r"(?:l\.?\s?p\.?(?![a-zà-ù.])|l\.\s?prov\.|legge\s+prov(?:inciale\b|\.))"
#: «Provincia autonoma di Trento», «Prov. Trento», «P.A. Bolzano», «PAT», «PAB», «(Trento)»,
#: «della Provincia autonoma». Only the two autonomous provinces make laws: a bare «della
#: provincia» names none.
_PROVINCIA = (rf"{_DI}?(?:(?:(?:provincia|prov\.|p\.)\s*(?:autonoma\s+|aut\.\s*|a\.\s*)?"
              rf"{_DI}?)?{_PROVINCE}\b|provincia\s+autonoma\b|p\.?\s?a\.?[tb]\.?(?![a-zà-ù]))")
#: «TN», «BZ»: only right after the act's number («legge 13/1997 TN») or in brackets («(BZ)»).
_TN_BZ = r"(?:\s+|\s*\(\s*)(?:tn|bz)\b"
_NOME_PROVINCIALE = re.compile(
    rf"^(?:{_SIGLA_PROVINCIALE}(?![a-zà-ù])|{_LEGGE}\s*{_PROVINCIA}"
    rf"|{_LEGGE}\s*{_ESTREMI}(?:{_SEP_LOCALE}(?:{_PROVINCIA}|provinciale\b)|{_TN_BZ}))",
    re.IGNORECASE,
)
#: A provincial law cited in prose, with a number (as LEGGE_REGIONALE_NEL_TESTO).
LEGGE_PROVINCIALE_NEL_TESTO = re.compile(
    rf"\b(?:{_SIGLA_PROVINCIALE}(?![a-zà-ù])[\s,]*(?:{_PROVINCIA}[\s,]*)?(?:{_ESTREMI}|n\.\s*\d+\b)"
    rf"|{_LEGGE}\s*{_PROVINCIA}[\s,]*{_ESTREMI}"
    rf"|{_LEGGE}\s*{_ESTREMI}(?:{_SEP_LOCALE}(?:{_PROVINCIA}|provinciale\b)|{_TN_BZ}))",
    re.IGNORECASE,
)


def legge_provinciale(name: str) -> bool:
    """Whether an act name is a law of the Province autonome di Trento or di Bolzano («l.p.
    13/1997», «legge provinciale Trento 13/1997», «legge 13/1997 della Provincia autonoma di Trento»)."""
    return bool(_NOME_PROVINCIALE.match(_strip_leading_words(_normalize_key(name or ""))))


def fonte_locale(name: str) -> "str | None":
    """What cite_law answers for a regional or provincial law's name, else None. Neither is ever
    resolved: read as the State's act of the same number it would be the wrong act."""
    if legge_regionale(name):
        return LEGGI_REGIONALI_NON_COPERTE
    if legge_provinciale(name):
        return LEGGI_PROVINCIALI_NON_COPERTE
    return None


def tipo_locale(tipo_atto: str) -> "str | None":
    """What to answer for an act type of a Region or an autonomous province (a regional or
    provincial law, a URN kind «regione.toscana:legge», «provincia.trento:legge»), else None.
    Norma builds no Normattiva address for it."""
    tipo = _normalize_key(tipo_atto or "")
    if re.match(r"^(?:urn:nir:)?regione\b", tipo):
        return LEGGI_REGIONALI_NON_COPERTE
    if re.match(r"^(?:urn:nir:)?provincia\b", tipo):
        return LEGGI_PROVINCIALI_NON_COPERTE
    return fonte_locale(tipo)


# ---------------------------------------------------------------------------
# SIGLE DATATE — sigle whose act follows the date (LI-086)
# ---------------------------------------------------------------------------
#
# The fiscal reform's testi unici replace older acts from the day they apply, which is not the
# day they enter into force. Until then a sigla names the old act, with a one-line notice of
# the change; from that day it names the new testo unico. Only acts that follow one another in
# time are split this way: two acts at the same date stay ambiguous (NOMI_AMBIGUI, «TUA»).
# The reference date is the one the caller gives (``resolve_atto(name, data=…)``), else today
# through ``_clock``. Every date and every set of estremi below was read on Normattiva, act by
# act, on 18 November 2026; the new testi unici are each the annex («allegato 1») of the decree.


class Periodo(NamedTuple):
    """One span of a dated sigla: from *dal* (ISO day, "" for always) the act it names."""

    dal: str
    atto: dict
    #: The act as the notices name it: «d.lgs. 19 giugno 2026, n. 117 (…)».
    estremi: str
    #: The one-line notice that goes with the act in this span, or None.
    avviso: "str | None" = None


_MESI_NOMI = _MESI_ESTESI.split("|")


def giorno_esteso(iso: str) -> str:
    """«1° gennaio 2027» for "2027-01-01": the ordinal on the first of the month, as the law writes it."""
    giorno = date.fromisoformat(iso)
    return f"{'1°' if giorno.day == 1 else giorno.day} {_MESI_NOMI[giorno.month - 1]} {giorno.year}"


def _succede(vecchio: dict, nuovo: dict, dal: str, estremi_vecchio: str, estremi_nuovo: str) -> tuple:
    """The two spans of a sigla that passes from *vecchio* to *nuovo* on *dal*."""
    return (Periodo("", vecchio, estremi_vecchio, f"dal {giorno_esteso(dal)} si applica il {estremi_nuovo}"),
            Periodo(dal, nuovo, estremi_nuovo))


_DPR = "decreto del presidente della repubblica"
_DLGS = "decreto legislativo"

#: TUIR: d.lgs. 19 giugno 2026, n. 117 approves the testo unico as its annex (art. 1); the testo
#: unico applies from 1 January 2027 (its art. 377). Normattiva, 18 November 2026.
_TUIR = _succede(
    {"tipo_atto": _DPR, "data": "1986-12-22", "numero_atto": "917"},
    {"tipo_atto": _DLGS, "data": "2026-06-19", "numero_atto": "117", "allegato": "1"},
    "2027-01-01", "d.P.R. 22 dicembre 1986, n. 917",
    "d.lgs. 19 giugno 2026, n. 117 (testo unico delle imposte sui redditi)")
#: Registro: d.lgs. 1° agosto 2025, n. 123, annex (art. 1); applies from 1 January 2027 (its art.
#: 205 co. 1, the date as replaced by art. 4 co. 5 d.l. 200/2025; decision LI-061, and
#: lib/_transizione.DPR_131_1986). Normattiva, 18 November 2026.
_TU_REGISTRO_2025 = "d.lgs. 1° agosto 2025, n. 123 (testo unico dell'imposta di registro e degli altri tributi indiretti)"
_REGISTRO = _succede(
    {"tipo_atto": _DPR, "data": "1986-04-26", "numero_atto": "131"},
    {"tipo_atto": _DLGS, "data": "2025-08-01", "numero_atto": "123", "allegato": "1"},
    "2027-01-01", "d.P.R. 26 aprile 1986, n. 131", _TU_REGISTRO_2025)
#: IVA: d.lgs. 19 gennaio 2026, n. 10, annex (art. 1); applies from 1 January 2027 (its art.
#: 171). Normattiva, 18 November 2026.
_IVA = _succede(
    {"tipo_atto": _DPR, "data": "1972-10-26", "numero_atto": "633"},
    {"tipo_atto": _DLGS, "data": "2026-01-19", "numero_atto": "10", "allegato": "1"},
    "2027-01-01", "d.P.R. 26 ottobre 1972, n. 633",
    "d.lgs. 19 gennaio 2026, n. 10 (testo unico dell'imposta sul valore aggiunto)")
#: Successioni e donazioni: art. 204 co. 1 lett. l) of the registro testo unico repeals most of
#: d.lgs. 346/1990 from the date of its art. 205 (1 January 2027; Normattiva, 18 November 2026).
#: The sigla stays on d.lgs. 346/1990 after that day, which cite_law then shows as repealed: it
#: is not the new testo unico's sigla, and the article numbers differ (LI-086).
_DLGS_346_1990 = {"tipo_atto": _DLGS, "data": "1990-10-31", "numero_atto": "346"}
_SUCCESSIONI = (
    Periodo("", _DLGS_346_1990, "d.lgs. 31 ottobre 1990, n. 346",
            f"dal 1° gennaio 2027 si applica il {_TU_REGISTRO_2025}"),
    Periodo("2027-01-01", _DLGS_346_1990, "d.lgs. 31 ottobre 1990, n. 346"),
)
#: Giustizia tributaria: the testo unico is the annex of d.lgs. 14 novembre 2024, n. 175 (checked
#: 9 November 2026, G-440: cited by name, an article is the annex's; as «d.lgs. 175/2024» the
#: decree's own art. 1 stays the decree's). It applies from 1 January 2027 (its art. 131 co. 1,
#: the date as replaced by art. 4 co. 3 d.l. 200/2025; Normattiva, 18 November 2026). No older
#: act answers its name: only the notice, which names no act the official text does not.
_TUGT_ATTO = {"tipo_atto": _DLGS, "data": "2024-11-14", "numero_atto": "175", "allegato": "1"}
_TUGT = (
    Periodo("", _TUGT_ATTO, "d.lgs. 14 novembre 2024, n. 175",
            "il testo unico della giustizia tributaria si applica dal 1° gennaio 2027 (art. 131, comma 1, "
            "come modificato dall'art. 4, comma 3, d.l. 200/2025); fino ad allora valgono le disposizioni "
            "previgenti"),
    Periodo("2027-01-01", _TUGT_ATTO, "d.lgs. 14 novembre 2024, n. 175"),
)

#: Sigla → its spans, at the caller's date or today.
SIGLE_DATATE: dict[str, tuple] = {
    **dict.fromkeys(("tuir", "testo unico delle imposte sui redditi", "testo unico imposte sui redditi",
                     "testo unico imposte redditi", "tu imposte redditi"), _TUIR),
    **dict.fromkeys(("tur", "tu registro", "testo unico registro", "testo unico dell'imposta di registro",
                     "testo unico imposta di registro"), _REGISTRO),
    **dict.fromkeys(("tuiva", "tu iva", "testo unico iva"), _IVA),
    **dict.fromkeys(("tu successioni", "testo unico sulle successioni e donazioni",
                     "testo unico successioni e donazioni"), _SUCCESSIONI),
    **dict.fromkeys(("testo unico della giustizia tributaria", "testo unico giustizia tributaria",
                     "testo unico delle disposizioni legislative in materia di giustizia tributaria",
                     "tu giustizia tributaria", "t.u. giustizia tributaria", "tugt"), _TUGT),
}

#: The codice dei contratti pubblici: three codes in succession. D.lgs. 163/2006 in force from 1
#: July 2006 (its art. 257, sixty days after GU n. 100 of 2 May 2006; the act page says
#: «Entrata in vigore del decreto: 1-7-2006»); d.lgs. 50/2016 from 19 April 2016, the day of its
#: publication (its art. 220; GU n. 91 of 19 April 2016); d.lgs. 36/2023 effective from 1 July
#: 2023 (its art. 229 co. 2), when d.lgs. 50/2016 is repealed (art. 226 co. 1). Normattiva, 18
#: November 2026. Read ONLY with an explicit date: the switch lies in the past, so «today» would
#: silently move every older citation to the 2023 code. Without a date each name keeps what it
#: resolved to before (codice degli appalti → 163/2006, codice dei contratti pubblici → 36/2023,
#: cod. app. → ambiguous). No MCP tool passes a date to the resolver yet: only the library does.
_CONTRATTI_PUBBLICI = (
    Periodo("2006-07-01", {"tipo_atto": _DLGS, "data": "2006-04-12", "numero_atto": "163"},
            "d.lgs. 12 aprile 2006, n. 163"),
    Periodo("2016-04-19", {"tipo_atto": _DLGS, "data": "2016-04-18", "numero_atto": "50"},
            "d.lgs. 18 aprile 2016, n. 50"),
    Periodo("2023-07-01", {"tipo_atto": "codice dei contratti pubblici", "data": "2023-03-31", "numero_atto": "36"},
            "d.lgs. 31 marzo 2023, n. 36"),
)
SIGLE_DATATE_CON_DATA: dict[str, tuple] = dict.fromkeys(
    ("codice dei contratti pubblici", "codice degli appalti", "cod. app."), _CONTRATTI_PUBBLICI)


def data_di_riferimento(data: "date | str | None") -> "date | None":
    """The reference date a caller gave, as a date; None when none is given (None, "", "  ").

    A date, a datetime (its day) or "YYYY-MM-DD". Anything else raises ValueError, whatever the
    name it comes with: a malformed date is the caller's error, never silently today.
    """
    if data is None or (isinstance(data, str) and not data.strip()):
        return None
    if isinstance(data, datetime):
        return data.date()
    if isinstance(data, date):
        return data
    try:
        return date.fromisoformat(str(data).strip())
    except ValueError:
        raise ValueError(f"data di riferimento non valida: {data!r} (attesa AAAA-MM-GG)") from None


def _giorno(data: "date | None") -> date:
    """The reference date already read by ``data_di_riferimento``, else today through ``_clock``."""
    return _clock.today() if data is None else data


def _periodi(key: str, con_data: bool) -> "tuple | None":
    """The spans of a dated sigla keyed *key* (the dated-only ones with an explicit date)."""
    if key in SIGLE_DATATE:
        return SIGLE_DATATE[key]
    if con_data:
        return SIGLE_DATATE_CON_DATA.get(key) or SIGLE_DATATE_CON_DATA.get(normalize_act_type(key))
    return None


def _alla_data(periodi: tuple, giorno: date) -> dict | None:
    """The act a dated sigla names on *giorno*, with its notice under "avviso"; None before the first."""
    scelto = None
    for periodo in periodi:
        if not periodo.dal or date.fromisoformat(periodo.dal) <= giorno:
            scelto = periodo
    if scelto is None:
        return None
    atto = dict(scelto.atto)
    if scelto.avviso:
        atto["avviso"] = scelto.avviso
    return atto


def sigla_senza_atto(name: str, *, data: "date | str | None" = None) -> "str | None":
    """What cite_law answers for a dated sigla asked at a date before its first act, else None."""
    giorno = data_di_riferimento(data)
    if giorno is None:
        return None
    for key in _candidate_keys(name):
        periodi = _periodi(key, True)
        if periodi and _alla_data(periodi, giorno) is None:
            primo = periodi[0]
            return (f"il {giorno.strftime('%d/%m/%Y')} nessun atto rispondeva a «{name.strip()}»: il primo, "
                    f"{primo.estremi}, si applica dal {giorno_esteso(primo.dal)}")
        if periodi:
            return None
    return None


# ---------------------------------------------------------------------------
# ATTI DENOMINATI — acts commonly cited by name rather than by number
# ---------------------------------------------------------------------------
#
# One row per act: (tipo_atto, data ISO, numero_atto, [alias...]).
#
# The extremes of the rows below were verified against Normattiva on 2026-08-24
# (each URN resolves to an act whose type, date and number match the row). The
# base was generated once from BROCARDI_CODICI via
# scripts/generate_atti_denominati.py; the table — not that script — is the
# source of truth, so a wrong act can be corrected here without touching a
# display label. Run the script with --check to spot Brocardi acts missing here.
#
# Acts already resolvable through NORMATTIVA_URN_CODICI or ATTI_NOTI are
# deliberately absent: those tables are consulted first.

_ATTI_DENOMINATI_SPEC: list[tuple[str, str, str, list[str]]] = [
    # --- Codici e testi coordinati non coperti da NORMATTIVA_URN_CODICI ------
    ("regio decreto", "1942-03-30", "318", [
        "disposizioni per l'attuazione del codice civile e disposizioni transitorie",
        "disposizioni di attuazione del codice civile", "disp. att. cc"]),
    ("regio decreto", "1941-12-18", "1368", [
        "disposizioni di attuazione del codice di procedura civile", "disp. att. cpc"]),
    ("regio decreto", "1931-05-28", "601", [
        "disposizioni di coordinamento e transitorie per il codice penale",
        "disposizioni transitorie codice penale"]),
    ("decreto del presidente della repubblica", "1988-09-22", "448", [
        "codice processo penale minorile", "processo penale minorile", "cppm", "c.p.p.m."]),
    ("decreto legislativo", "1989-07-28", "271", [
        "disposizioni di attuazione del codice di procedura penale", "disp. att. cpp"]),
    ("decreto legislativo", "2003-06-30", "196", ["codice della privacy"]),
    ("decreto legislativo", "2006-04-03", "152", [
        # «TUA» alone is also the testo unico accise: ambiguous (NOMI_AMBIGUI, LI-086).
        "codice dell'ambiente", "codice ambiente", "testo unico ambientale",
        "tu ambiente", "testo unico ambiente", "tuamb"]),
    ("decreto legislativo", "2017-07-03", "117", ["codice del terzo settore"]),
    ("decreto legislativo", "2023-03-31", "36", ["nuovo codice appalti"]),
    ("decreto legislativo", "2006-04-12", "163", [
        "codice degli appalti", "vecchio codice appalti", "codice appalti 2006"]),

    # --- Lavoro --------------------------------------------------------------
    ("legge", "1970-05-20", "300", [
        "statuto dei lavoratori", "statuto lavoratori", "statuto dei diritti dei lavoratori", "st. lav."]),
    ("decreto legislativo", "2001-03-30", "165", [
        "testo unico sul pubblico impiego", "testo unico pubblico impiego",
        "tu pubblico impiego", "tupi"]),
    ("decreto legislativo", "2008-04-09", "81", [
        "testo unico sulla sicurezza sul lavoro", "testo unico sicurezza sul lavoro",
        "testo unico sicurezza", "tu sicurezza", "tusl"]),
    ("decreto legislativo", "2015-03-04", "23", [
        "disposizioni in materia di contratto di lavoro a tempo indeterminato a tutele crescenti",
        "jobs act", "contratto a tutele crescenti", "tutele crescenti"]),
    ("decreto legislativo", "2015-06-15", "81", [
        "disciplina organica dei contratti di lavoro e revisione della normativa in tema di mansioni",
        "jobs act contratti", "codice dei contratti di lavoro"]),
    ("decreto legislativo", "2003-09-10", "276", [
        "legge biagi", "decreto biagi", "riforma biagi"]),
    ("legge", "2012-06-28", "92", ["legge fornero", "riforma fornero"]),
    ("decreto legislativo", "2015-03-04", "22", [
        "disposizioni per il riordino della normativa in materia di ammortizzatori sociali",
        "ammortizzatori sociali", "decreto naspi"]),
    ("legge", "1966-07-15", "604", [
        "norme sui licenziamenti individuali", "legge sui licenziamenti individuali"]),
    ("decreto legislativo", "2003-04-08", "66", [
        "norme in materia di orario di lavoro", "orario di lavoro"]),
    ("legge", "2017-05-22", "81", [
        "misure per la tutela del lavoro autonomo non imprenditoriale e misure volte a favorire il lavoro agile",
        "legge sul lavoro agile", "statuto del lavoro autonomo"]),
    ("decreto legislativo", "2001-03-26", "151", [
        "testo unico maternità e paternità", "testo unico in materia di tutela e sostegno della maternità e della paternità",
        "tu maternità", "testo unico maternita e paternita"]),
    ("decreto del presidente della repubblica", "1965-06-30", "1124", [
        "testo unico sull'assicurazione degli infortuni sul lavoro",
        "testo unico infortuni sul lavoro", "tu infortuni"]),
    ("decreto legge", "2023-05-04", "48", ["decreto lavoro 2023"]),

    # --- Impresa, crisi, societario -----------------------------------------
    ("regio decreto", "1942-03-16", "267", [
        "legge fallimentare", "l. fall.", "legge fall.", "l.f."]),
    ("decreto legislativo", "2001-06-08", "231", [
        "disciplina della responsabilità amministrativa delle persone giuridiche",
        "responsabilità amministrativa degli enti", "decreto 231", "d.lgs 231"]),
    ("decreto legislativo", "1993-09-01", "385", [
        "testo unico bancario", "tu bancario"]),
    ("decreto legislativo", "1998-02-24", "58", [
        "testo unico delle disposizioni in materia di intermediazione finanziaria",
        "testo unico della finanza", "tu finanza"]),
    ("decreto legislativo", "2016-08-19", "175", [
        "testo unico in materia di società a partecipazione pubblica",
        "testo unico società partecipate", "tusp"]),

    # --- Amministrativo ------------------------------------------------------
    ("legge", "1990-08-07", "241", [
        "legge sul procedimento amministrativo", "legge sul procedimento",
        "legge 241", "legge sulla trasparenza amministrativa", "l. proc. amm."]),
    ("decreto legislativo", "2000-08-18", "267", [
        "testo unico degli enti locali", "testo unico enti locali", "tu enti locali", "tuel"]),
    ("decreto del presidente della repubblica", "2001-06-06", "380", [
        "testo unico edilizia", "testo unico dell'edilizia", "tu edilizia", "t.u.ed.",
        # «TUED», «T.U.E.D.», «TUEd» (G-440): «TUE» alone stays the Treaty on European Union.
        "tued"]),
    # Laws by their nickname (G-440; titles checked on Normattiva, 11 November 2026).
    ("legge", "2019-07-19", "69", ["codice rosso"]),
    ("legge", "2024-03-05", "21", ["legge capitali"]),
    # Testi unici and nicknames of the second alias pass (G-440): heading and title of each
    # checked on Normattiva, 11 November 2026; each act calls itself «testo unico» where the
    # alias says so. Not keyed here: «TUIVA» and «T.U. registro», which follow the date (the old
    # acts until the new testi unici apply, SIGLE_DATATE, LI-086); and, because more than one act
    # answers them, «T.U. rinnovabili» (d.lgs. 190/2024 does not call itself one), «decreto FER»,
    # «decreto CER» (see NOMI_AMBIGUI).
    ("decreto del presidente della repubblica", "2002-05-30", "115", [
        "testo unico spese di giustizia", "testo unico delle spese di giustizia",
        "testo unico in materia di spese di giustizia", "tu spese di giustizia", "tusg"]),
    ("decreto del presidente della repubblica", "2000-12-28", "445", [
        "testo unico documentazione amministrativa", "testo unico sulla documentazione amministrativa",
        "tu documentazione amministrativa", "tuda"]),
    ("decreto legislativo", "1995-10-26", "504", ["testo unico accise", "tu accise"]),
    # Repealed whole by d.lgs. 26 settembre 2024, n. 141: the identity of historical citations.
    ("decreto del presidente della repubblica", "1973-01-23", "43", [
        "testo unico leggi doganali", "testo unico delle leggi doganali", "testo unico doganale", "tuld"]),
    ("decreto legislativo", "2021-11-08", "208", [
        "tusma"]),
    ("decreto legislativo", "2005-07-31", "177", [
        "testo unico dei servizi di media audiovisivi e radiofonici", "tusmar"]),
    ("decreto del presidente della repubblica", "2010-03-15", "90", [
        "testo unico ordinamento militare", "testo unico delle disposizioni regolamentari in materia di "
        "ordinamento militare", "tuom"]),
    ("legge", "2015-08-07", "124", ["legge madia"]),
    ("decreto legge", "2012-09-13", "158", ["legge balduzzi", "decreto balduzzi"]),
    ("decreto legislativo", "2023-03-10", "24", ["decreto whistleblowing"]),
    ("decreto legge", "2018-07-12", "87", ["decreto dignità", "decreto dignita"]),
    ("decreto legge", "2024-05-29", "69", ["decreto salva casa", "decreto salva-casa", "decreto salvacasa"]),
    # «Provvedimenti per la cooperazione» (Normattiva's title, checked 11 November 2026).
    ("decreto legislativo del capo provvisorio dello stato", "1947-12-14", "1577", ["legge basevi"]),
    ("decreto del presidente della repubblica", "2001-06-08", "327", [
        "testo unico sulle espropriazioni per pubblica utilità",
        "testo unico espropriazioni", "tu espropri", "tu espropriazioni", "tues", "tuespr"]),
    ("decreto del presidente della repubblica", "1971-11-24", "1199", [
        "semplificazione dei procedimenti in materia di ricorsi amministrativi",
        "ricorsi amministrativi"]),
    ("decreto del presidente della repubblica", "2005-02-11", "68", [
        "regolamento posta elettronica certificata", "regolamento pec"]),
    ("legge", "2012-11-06", "190", [
        "legge severino", "legge anticorruzione"]),

    # --- Famiglia e persone --------------------------------------------------
    ("legge", "1970-12-01", "898", ["legge sul divorzio", "legge divorzio"]),
    ("legge", "1983-05-04", "184", [
        "legge sull'adozione", "legge adozione", "diritto del minore ad una famiglia"]),
    ("legge", "2016-05-20", "76", [
        "regolamentazione delle unioni civili tra persone dello stesso sesso e disciplina delle convivenze",
        "legge cirinnà", "legge sulle unioni civili", "legge cirinna"]),
    ("legge", "2006-02-08", "54", [
        "disposizioni in materia di separazione dei genitori e affidamento condiviso dei figli",
        "legge sull'affido condiviso", "affido condiviso"]),
    ("legge", "2004-02-19", "40", [
        "norme in materia di procreazione medicalmente assistita",
        "legge sulla procreazione medicalmente assistita", "legge 40"]),
    ("legge", "2017-12-22", "219", [
        "legge sul biotestamento", "legge sulle dat", "consenso informato e dat"]),
    ("legge", "1978-05-22", "194", ["legge sull'aborto", "legge 194"]),
    ("legge", "1992-02-05", "104", ["legge 104", "legge quadro sull'handicap"]),

    # --- Penale ed esecuzione penale ----------------------------------------
    ("legge", "1975-07-26", "354", [
        "legge sull'ordinamento penitenziario", "ordinamento penitenziario"]),
    ("decreto del presidente della repubblica", "1990-10-09", "309", [
        "testo unico stupefacenti", "testo unico sugli stupefacenti", "tu stupefacenti", "tustup"]),
    ("regio decreto", "1931-06-18", "773", [
        "testo unico delle leggi di pubblica sicurezza", "testo unico di pubblica sicurezza",
        "tulps", "tu pubblica sicurezza"]),

    # --- Professioni e sanità ------------------------------------------------
    ("legge", "2012-12-31", "247", [
        "legge professionale forense", "legge forense", "ordinamento forense"]),
    ("legge", "2017-03-08", "24", [
        "responsabilità professionale del personale sanitario",
        "legge gelli-bianco", "legge gelli", "legge gelli bianco"]),

    # --- Proprietà intellettuale, locazioni, agrario -------------------------
    ("legge", "1941-04-22", "633", [
        "legge sulla protezione del diritto d'autore", "legge sul diritto d'autore",
        "legge diritto d'autore", "lda"]),
    # A legge, not a decreto legislativo: the type was wrong and every lookup was refused
    # (live gate, 11 November 2026: Normattiva titles it «LEGGE 9 dicembre 1998, n. 431»).
    ("legge", "1998-12-09", "431", [
        "legge sulle locazioni abitative", "locazioni abitative"]),
    ("legge", "1978-07-27", "392", ["legge equo canone", "equo canone"]),
    ("legge", "1982-05-03", "203", ["norme sui contratti agrari", "legge sui contratti agrari"]),
    ("legge", "1965-05-26", "590", [
        "disposizioni per lo sviluppo della proprietà coltivatrice", "proprietà coltivatrice"]),
    ("decreto legislativo", "2001-05-18", "228", [
        "testo unico sull'agricoltura", "orientamento e modernizzazione del settore agricolo"]),
    ("decreto legislativo", "2018-05-21", "75", ["testo unico sulle piante officinali"]),

    # --- Tributario ----------------------------------------------------------
    ("legge", "2000-07-27", "212", [
        "statuto del contribuente", "statuto dei diritti del contribuente"]),
    ("decreto legislativo", "2000-03-10", "74", [
        "legge sui reati tributari", "reati tributari"]),
    # D.P.R. 131/1986 («TUR», «testo unico dell'imposta di registro») and the «testo unico iva»
    # follow the date: SIGLE_DATATE (LI-086).
    ("decreto del presidente della repubblica", "1972-10-26", "633", ["decreto iva"]),
    ("decreto del presidente della repubblica", "1973-09-29", "600", [
        "disposizioni comuni in materia di accertamento delle imposte sui redditi",
        "decreto accertamento"]),
    ("decreto del presidente della repubblica", "1973-09-29", "602", [
        "disposizioni sulla riscossione delle imposte sul reddito", "decreto riscossione"]),
    ("decreto legislativo", "1997-06-19", "218", [
        "disposizioni in materia di accertamento con adesione e di conciliazione giudiziale",
        "accertamento con adesione"]),
    ("decreto legislativo", "1997-12-18", "472", [
        "disposizioni sulle sanzioni amministrative per violazioni di norme tributarie",
        "sanzioni amministrative tributarie"]),
    ("decreto legislativo", "1992-12-31", "545", [
        "ordinamento degli organi speciali di giurisdizione tributaria ed organizzazione degli uffici di collaborazione"]),
    ("decreto legislativo", "1992-12-30", "504", [
        "riordino della finanza degli enti territoriali"]),
    ("decreto legge", "1994-09-30", "564", ["disposizioni urgenti in materia fiscale"]),
    # D.lgs. 346/1990 («TU successioni») carries the notice of the registro testo unico: SIGLE_DATATE.

    # --- Terzo settore e no-profit -------------------------------------------
    ("legge", "1991-08-11", "266", ["legge quadro sul volontariato", "legge sul volontariato"]),
    ("decreto legislativo", "1997-12-04", "460", ["legge sulle onlus", "decreto onlus"]),
    ("legge", "2000-12-07", "383", ["disciplina delle associazioni di promozione sociale"]),

    # --- Immigrazione --------------------------------------------------------
    ("decreto legislativo", "1998-07-25", "286", [
        "testo unico sull'immigrazione", "testo unico immigrazione", "tu immigrazione", "tuimm"]),
    ("legge", "2002-07-30", "189", ["legge bossi-fini", "legge bossi fini"]),

    # --- Processo civile: mediazione e durata --------------------------------
    ("decreto legislativo", "2010-03-04", "28", [
        "mediazione finalizzata alla conciliazione delle controversie civili e commerciali",
        "decreto mediazione", "legge sulla mediazione"]),
    ("legge", "2001-03-24", "89", ["legge pinto", "equa riparazione"]),

    # --- Diritto internazionale privato --------------------------------------
    ("legge", "1995-05-31", "218", [
        "riforma del sistema italiano di diritto internazionale privato",
        "legge di diritto internazionale privato", "legge sul diritto internazionale privato"]),

    # --- Decretazione d'urgenza ricorrentemente citata ------------------------
    # Cura Italia: Brocardi indexes the conversion law (L. 27/2020), but a
    # citation "art. N decreto Cura Italia" means the decreto-legge itself.
    ("decreto legge", "2020-03-17", "18", ["decreto cura italia", "cura italia"]),
    ("legge", "2020-04-24", "27", ["legge di conversione cura italia"]),
    ("decreto legge", "2020-05-19", "34", ["decreto rilancio"]),
    ("decreto legge", "2021-03-22", "41", ["decreto sostegni"]),
    ("decreto legge", "2021-05-31", "77", [
        "decreto semplificazioni bis", "decreto governance pnrr"]),
]

ATTI_DENOMINATI: dict[str, dict] = {}
for _tipo, _data, _numero, _aliases in _ATTI_DENOMINATI_SPEC:
    for _alias in _aliases:
        ATTI_DENOMINATI[_alias] = {
            "tipo_atto": _tipo,
            "data": _data,
            "numero_atto": _numero,
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
    "ccii": "codice della crisi d'impresa e dell'insolvenza",
    "codice crisi": "codice della crisi d'impresa e dell'insolvenza",
    "codice della crisi": "codice della crisi d'impresa e dell'insolvenza",
    "ccp": "codice dei contratti pubblici",
    "codice appalti": "codice dei contratti pubblici",
    "codice contratti pubblici": "codice dei contratti pubblici",
    "cdc": "codice del consumo",
    "cdpc": "codice della protezione civile",
    "cds": "codice della strada",
    "c.g.c": "codice di giustizia contabile",  # the sigla the convention writes (VisuaLex, G-366)
    "c.g.c.": "codice di giustizia contabile",
    "cgco": "codice di giustizia contabile",
    "cn": "codice della navigazione",
    "cnd": "codice della nautica da diporto",
    "cod. amm. dig.": "codice dell'amministrazione digitale",
    "cod. antimafia": "codice antimafia",
    "cod. ass. priv.": "codice delle assicurazioni private",
    # More spellings of the codes (G-440).
    "cod. ass.": "codice delle assicurazioni private",
    # The values here are act types (api's _TIPI_NOTI reads them): the code's own name, never
    # another alias («codice privacy» is a key of ATTI_NOTI, not a type).
    "cod. priv.": "codice in materia di protezione dei dati personali",
    "c.priv.": "codice in materia di protezione dei dati personali",
    "c. priv.": "codice in materia di protezione dei dati personali",
    "codice urbani": "codice dei beni culturali e del paesaggio",
    "cbcp": "codice dei beni culturali e del paesaggio",
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
    "cod. post.": "codice postale e delle telecomunicazioni",  # VisuaLex, G-366
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
    "disp. att. c.p.p.": "norme di attuazione, di coordinamento e transitorie del codice di procedura penale",
    "disp. att. cpp": "norme di attuazione, di coordinamento e transitorie del codice di procedura penale",
    "att. c.p.p.": "norme di attuazione, di coordinamento e transitorie del codice di procedura penale",
    "norme att. c.p.p.": "norme di attuazione, di coordinamento e transitorie del codice di procedura penale",
    "norme att. cod. proc. pen.": "norme di attuazione, di coordinamento e transitorie del codice di procedura penale",
    # Other spellings of the codes (G-440): an external citation corpus.
    "codice della crisi e dell'insolvenza": "codice della crisi d'impresa e dell'insolvenza",
    "codice della crisi d'impresa": "codice della crisi d'impresa e dell'insolvenza",
    "c. crisi impresa": "codice della crisi d'impresa e dell'insolvenza",
    "cod. contratti pubblici": "codice dei contratti pubblici",
    "codice dei beni culturali": "codice dei beni culturali e del paesaggio",
    "codice della proprieta' industriale": "codice della proprietà industriale",
    "preleggi al codice civile": "preleggi",
    "costituzione italiana": "costituzione",
    "c.p.m.p.": "codice penale militare di pace",
    "c.p.m.p": "codice penale militare di pace",
    "cpmp": "codice penale militare di pace",
    "c.p.m.g.": "codice penale militare di guerra",
    "c.p.m.g": "codice penale militare di guerra",
    "cpmg": "codice penale militare di guerra",
    "disp. prel.": "preleggi",
    "disp. prel. c.c.": "preleggi",
    "disp. prel. cc": "preleggi",
    "disposizioni per l'attuazione del codice civile e disposizioni transitorie": "disposizioni per l'attuazione del Codice civile e disposizioni transitorie",
    "disposizioni per l'attuazione del codice di procedura civile e disposizioni transitorie": "disposizioni per l'attuazione del Codice di procedura civile e disposizioni transitorie",
    "disposizioni preliminari al codice civile": "preleggi",
    "disposizioni preliminari codice civile": "preleggi",
    "disposizioni preliminari del codice civile": "preleggi",
    "disposizioni sulla legge in generale": "preleggi",
    "norme amb.": "norme in materia ambientale",
    "norme in materia ambientale": "norme in materia ambientale",
    "prel.": "preleggi",
    "preleggi": "preleggi",
    # --- From VisuaLex's table (tools/map.py at eca698dc) ---------------------
    # The source convention's own short forms: every abbreviation VisuaLex's
    # citations write must read back to its type. Without them "d.l. 18/2020"
    # built ``urn:nir:stato:d.l.:…`` and "l. cost." built ``l..cost.``, URNs that
    # name no act; "c.p.a." must never be read as "c.p.".
    "c.p.a": "codice del processo amministrativo",
    "c.p.a.": "codice del processo amministrativo",
    "codice del Terzo settore": "codice del Terzo settore",
    "disposizioni per l'attuazione del Codice civile e disposizioni transitorie": "disposizioni per l'attuazione del Codice civile e disposizioni transitorie",
    "disposizioni per l'attuazione del Codice di procedura civile e disposizioni transitorie": "disposizioni per l'attuazione del Codice di procedura civile e disposizioni transitorie",
    "d.l.": "decreto legge",
    "decreto-legge": "decreto legge",
    "l. cost.": "legge costituzionale",
    "l.cost.": "legge costituzionale",
    "l.cost": "legge costituzionale",
    "legge cost.": "legge costituzionale",
    "l. costituzionale": "legge costituzionale",
    "legge costituzionale": "legge costituzionale",
    "r.d.l.": "regio decreto legge",
    "regio decreto legge": "regio decreto legge",
    "regio decreto-legge": "regio decreto legge",
    "d.lgs.lgt.": "decreto legislativo luogotenenziale",
    "decreto legislativo luogotenenziale": "decreto legislativo luogotenenziale",
}

#: Case-insensitive index of NORMATTIVA_SEARCH (first spelling wins), for ``normalize_act_type``.
_NORMATTIVA_SEARCH_LOWER: dict[str, str] = {}
for _k, _v in NORMATTIVA_SEARCH.items():
    _NORMATTIVA_SEARCH_LOWER.setdefault(_k.lower(), _v)


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

# CELEX identifiers of the treaties. The EURLEX URLs above are the citable,
# human-facing pages, but EUR-Lex answers automated requests with a WAF
# challenge — the document itself has to come from CELLAR by CELEX id.
EURLEX_TREATY_CELEX = {
    "tue": "12016M/TXT",
    "tfue": "12016E/TXT",
    "cdfue": "12016P/TXT",
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
    "Disposizioni di attuazione del codice di procedura penale(D.lgs. 28 luglio 1989, n. 271)": "https://www.brocardi.it/disposizioni-per-attuazione-codice-procedura-penale/",
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
    "Testo unico in materia di tutela e sostegno della maternità e della paternità(D.lgs. 26 marzo 2001, n. 151)": "https://www.brocardi.it/testo-unico-sostegno-maternita-paternita/",
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
    # Appalti abrogati — Brocardi keeps the old name on the D.lgs. 50/2016 page;
    # "codice dei contratti pubblici" resolves to the current D.lgs. 36/2023
    # through its URN, so only an explicit 50/2016 citation lands here.
    "Codice degli appalti [ABROGATO](D.lgs. 12 aprile 2006, n. 163)": "https://www.brocardi.it/codice-degli-appalti/",
    "Codice dei contratti pubblici [ABROGATO](D.lgs. 18 aprile 2016, n. 50)": "https://www.brocardi.it/codice-dei-contratti-pubblici/",
    # Decreti emergenza/economia (recenti)
    "Decreto lavoro 2023(D.L. 4 maggio 2023, n. 48)": "https://www.brocardi.it/decreto-lavoro-2023/",
    "Decreto \"Semplificazioni bis\"(D.L. 31 maggio 2021, n. 77)": "https://www.brocardi.it/decreto-semplificazioni-bis/",
    "Decreto \"Sostegni\"(D.L. 22 marzo 2021, n. 41)": "https://www.brocardi.it/decreto-sostegni/",
    "Decreto \"Rilancio\"(D.L. 19 maggio 2020, n. 34)": "https://www.brocardi.it/decreto-rilancio/",
    "Decreto \"Cura Italia\"(L. 24 aprile 2020, n. 27)": "https://www.brocardi.it/decreto-cura-italia/",
    # Same page as its conversion law above: the resolver names the decree.
    "Decreto \"Cura Italia\"(D.L. 17 marzo 2020, n. 18)": "https://www.brocardi.it/decreto-cura-italia/",
}

# Every label carries the act's extremes — "Statuto dei lavoratori(L. 20 maggio
# 1970, n. 300)". They are parsed once here into the identity a citation is
# matched against: (tipo esteso, anno, numero). Matching on the label text
# instead ("legge" in key) once handed the legge fallimentare page to every
# other legge, which for a lawyer is worse than no page at all.
_MESI_IT = {
    m: f"{i + 1:02d}"
    for i, m in enumerate(
        "gennaio febbraio marzo aprile maggio giugno luglio agosto "
        "settembre ottobre novembre dicembre".split()
    )
}

_ESTREMI_TIPI = {
    "r.d.": "regio decreto",
    "d.p.r.": "decreto del presidente della repubblica",
    "d.lgs.": "decreto legislativo",
    "d.l.": "decreto legge",
    "l.": "legge",
    "reg. ue": "regolamento ue",
}

_ESTREMI_RE = re.compile(
    r"\((R\.D\.|D\.P\.R\.|D\.\s?Lgs\.|D\.L\.|L\.|Reg\.\s*UE)\s*"
    r"(\d{1,2})\s+([A-Za-zà]+)\s+(\d{4}),?\s*n\.\s*(\d+)\)",
    re.IGNORECASE,
)


def parse_brocardi_estremi(label: str) -> dict | None:
    """Act identity embedded in a Brocardi label, or None for labels without one.

    "Legge fallimentare(R.D. 16 marzo 1942, n. 267)" →
    {"tipo_atto": "regio decreto", "data": "1942-03-16", "numero_atto": "267"}.
    The last parenthesis wins: a few labels open with a display name in brackets.
    """
    matches = list(_ESTREMI_RE.finditer(label))
    if not matches:
        return None
    tipo_raw, giorno, mese_raw, anno, numero = matches[-1].groups()
    tipo = _ESTREMI_TIPI.get(re.sub(r"\s+", " ", tipo_raw.lower()).replace("d. lgs.", "d.lgs."))
    mese = _MESI_IT.get(mese_raw.lower())
    if not tipo or not mese:
        return None
    return {"tipo_atto": tipo, "data": f"{anno}-{mese}-{int(giorno):02d}", "numero_atto": numero}


def _brocardi_label_name(label: str) -> str:
    """The display name of a label: text before the extremes, tidied for lookup."""
    name = label.split("(")[0]
    return re.sub(r"\s+", " ", name.replace("[ABROGATO]", "").replace('"', "")).strip().lower()


# (tipo esteso, anno, numero) → URL, and (tipo esteso, numero) → set of URLs for
# citations that carry no year: those resolve only when the number is unique.
_BROCARDI_BY_IDENTITY: dict[tuple[str, str, str], str] = {}
_BROCARDI_BY_TIPO_NUMERO: dict[tuple[str, str], set[str]] = {}
# display name → URL for callers that pass the act by its Brocardi name; the
# labels without extremes (Costituzione, Preleggi…) have no other way in and
# are consulted before any identity — Preleggi share the codice civile's R.D.
_BROCARDI_BY_NAME: dict[str, str] = {}
_BROCARDI_BARE_NAMES: dict[str, str] = {}
# display name → its label's (tipo, anno, numero), to refuse a name paired with
# somebody else's extremes ("statuto dei lavoratori", n. 267).
_BROCARDI_NAME_ESTREMI: dict[str, tuple[str, str, str]] = {}
for _key, _url in BROCARDI_CODICI.items():
    _BROCARDI_BY_NAME.setdefault(_brocardi_label_name(_key), _url)
    _estremi = parse_brocardi_estremi(_key)
    if _estremi:
        _BROCARDI_NAME_ESTREMI.setdefault(
            _brocardi_label_name(_key),
            (_estremi["tipo_atto"], _estremi["data"][:4], _estremi["numero_atto"]),
        )
        _anno = _estremi["data"][:4]
        _BROCARDI_BY_IDENTITY[(_estremi["tipo_atto"], _anno, _estremi["numero_atto"])] = _url
        _BROCARDI_BY_TIPO_NUMERO.setdefault((_estremi["tipo_atto"], _estremi["numero_atto"]), set()).add(_url)
    else:
        _BROCARDI_BARE_NAMES.setdefault(_brocardi_label_name(_key), _url)


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

def codice_urn(codice_name: str) -> str | None:
    """URN fragment for a codice, matched case-insensitively.

    A few keys in NORMATTIVA_URN_CODICI carry capitals ("codice del Terzo
    settore"), while every lookup arrives lowercased — without this index those
    codici silently fall through to a generic, wrong URN.
    """
    return _URN_CODICI_LOWER.get(codice_name.lower().strip())


def extract_codice_details(codice_name: str) -> dict | None:
    """Extract date and act number from a codice URN in NORMATTIVA_URN_CODICI."""
    urn = codice_urn(codice_name)
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
    """Normalize act type abbreviation to full name using NORMATTIVA_SEARCH.

    As VisuaLex's ``text_op.normalize_act_type`` (search table): the literal key
    first, then a case-insensitive index (some keys carry capitals, "codice del
    Terzo settore"), then the form without spaces ("cod.civ."). Each added
    attempt only resolves more names, never changes one that already resolved.
    """
    if input_type in {"TUE", "TFUE", "CDFUE"}:
        return input_type
    key = input_type.lower().strip()
    found = NORMATTIVA_SEARCH.get(key)
    if found is None:
        found = _NORMATTIVA_SEARCH_LOWER.get(key)
    if found is None:
        found = NORMATTIVA_SEARCH.get(key.replace(" ", ""), key)
    return found


# Leading articles and prepositions: "art. 111 *della* Costituzione".
# The whitespace is required: without it "le" would be stripped from "legge".
_LEADING_WORDS = re.compile(
    r"^(?:(?:del|della|dello|dei|degli|delle|di|il|lo|la|i|gli|le|un|una|uno)\s+|[dl]')",
    re.IGNORECASE,
)


def _normalize_key(name: str) -> str:
    """Lowercase and tidy an act name for table lookup.

    Trailing dots are preserved: several table keys are dotted abbreviations
    ("c.c.", "d.lgs."), so stripping them would break resolution rather than help it.
    """
    key = name.strip().lower()
    key = key.replace("\u2019", "'").replace("\u02bc", "'")
    # Nicknames arrive quoted the way Brocardi prints them: Decreto "Sostegni".
    key = key.replace('"', "").replace("\u201c", "").replace("\u201d", "")
    key = re.sub(r"\s+", " ", key)
    return key.strip(" ,;:")


def _strip_leading_words(key: str) -> str:
    """Drop leading articles/prepositions, repeatedly ("del lo statuto" → "statuto")."""
    while True:
        stripped = _LEADING_WORDS.sub("", key, count=1).strip()
        if stripped == key or not stripped:
            return key
        key = stripped


# A dotted acronym: letters and dots only, at least one dot ("t.u.e.l.", "c.c.").
# Restricted to letter-only keys so "d.lgs. 196/2003" keeps its shape and goes
# down the citation-pattern path instead of being mangled into a lookup key.
_DOTTED_ACRONYM = re.compile(r"^[a-zà-ù]+(?:\.[a-zà-ù]*)+$", re.IGNORECASE)


#: Sigle that are also an abbreviated month: «mar.» in «17 mar. 2020» is March, never the
#: MAR. They are read only as written, without dots (no dotted-acronym collapse).
SIGLE_COME_MESI = frozenset({"mar"})

# «t.u. edilizia», «T.U. bancario», «t. u. enti locali»: the testi unici are keyed «tu …».
_TU_PUNTATO = re.compile(r"^t\.\s?u\.\s+")


def _candidate_keys(name: str):
    """Yield lookup keys for an act name, most literal first.

    Literal-first ordering means the pre-existing exact-match behaviour always
    wins; the normalized variants only ever add resolutions, never change one.
    """
    seen = set()
    normalized = _normalize_key(name)
    stripped = _strip_leading_words(normalized)
    candidates = [name.strip(), normalized, stripped]
    if _DOTTED_ACRONYM.match(normalized) and normalized.replace(".", "") not in SIGLE_COME_MESI:
        candidates.append(normalized.replace(".", ""))
    candidates += [_TU_PUNTATO.sub("tu ", c) for c in (normalized, stripped) if _TU_PUNTATO.match(c)]
    for candidate in candidates:
        if candidate and candidate not in seen:
            seen.add(candidate)
            yield candidate


def _lookup_key(key: str) -> dict | None:
    """Resolve one exact key against the tables, in order of trustworthiness.

    ATTI_NOTI and NORMATTIVA_URN_CODICI are hand-verified and take precedence
    over ATTI_DENOMINATI, whose base was generated from Brocardi labels.
    """
    if key in ATTI_NOTI:
        return dict(ATTI_NOTI[key])

    details = extract_codice_details(key)
    if details:
        return {
            "tipo_atto": key,
            "data": details["data"],
            "numero_atto": details["numero_atto"],
        }

    if key in ATTI_DENOMINATI:
        return dict(ATTI_DENOMINATI[key])

    normalized = normalize_act_type(key)
    if normalized != key:
        if normalized in ATTI_NOTI:
            return dict(ATTI_NOTI[normalized])
        details = extract_codice_details(normalized)
        if details:
            return {
                "tipo_atto": normalized,
                "data": details["data"],
                "numero_atto": details["numero_atto"],
            }
        if normalized.lower() in ATTI_DENOMINATI:
            return dict(ATTI_DENOMINATI[normalized.lower()])

    return None


def resolve_atto(name: str, *, data: "date | str | None" = None) -> dict | None:
    """Resolve a common act name to scraper parameters.

    Returns {"tipo_atto", "data", "numero_atto"} (and "allegato" for an act whose text is
    an annex) or None. Never guesses: an unrecognised name yields None so the caller can
    report it rather than cite the wrong act. A regional or provincial law is never resolved.

    *data* is the reference date ("YYYY-MM-DD" or a date) for the sigle that follow it
    (``SIGLE_DATATE``); without it they are read at today's date (``_clock``), and the
    ``SIGLE_DATATE_CON_DATA`` keep their undated resolution. A dated sigla's act carries
    its notice under "avviso" while one is due (LI-086).
    """
    data = data_di_riferimento(data)  # first: a malformed date is refused for every name
    if fonte_locale(name):
        return None
    con_data = data is not None
    for key in _candidate_keys(name):
        periodi = _periodi(key, con_data)
        if periodi:
            return _alla_data(periodi, _giorno(data))
        result = _lookup_key(key)
        if result:
            return result
    return _regolamento_per_soprannome(name) or _sigla_di_allegato(name)


# «Regolamento DORA», «Regolamento (UE) eIDAS», «regolamento europeo MAR»: the word before a
# regulation's nickname.
_REGOLAMENTO_PREFISSO = re.compile(r"^(?:il\s+)?regolamento\s+(?:\(?\s*ue\s*\)?\s+|europeo\s+)?", re.IGNORECASE)


def _regolamento_per_soprannome(name: str) -> dict | None:
    """«Regolamento <nickname>» when the nickname is an EU regulation of ATTI_NOTI, else None.

    Only a regulation ATTI_NOTI keys by that nickname (hand-verified): «Regolamento DORA» is
    reg. (UE) 2022/2554, but «regolamento condominiale» or «Regolamento Emittenti» (Consob)
    name no EU act, and «regolamento NIS2» is not one either (NIS2 is a directive).
    """
    resto = _REGOLAMENTO_PREFISSO.sub("", _normalize_key(name), count=1)
    if not resto or resto == _normalize_key(name):
        return None
    for key in _candidate_keys(resto):
        entry = ATTI_NOTI.get(key)
        if entry and entry["tipo_atto"] == "regolamento ue":
            return dict(entry)
    return None


#: The code sigle of more than one word, read in any spacing or dotting as the annex sigle are.
_SIGLE_MULTIPAROLA = ("disp. att. c.c.", "disp. att. c.p.c.", "cod. nav.", "cod. post.", "cod. post. telecom.")


def _sigla_pattern(sigla: str) -> "re.Pattern[str]":
    # Each dot may be left out or followed by a space («disp att cpa», «disp.att.c.p.a.»), as
    # VisuaLex's parser reads a sigla (nl_parser at f47ac1b6); matched against the whole name.
    return re.compile(r"\.?\s*".join(re.escape(part.strip()) for part in sigla.rstrip(".").split(".")) + r"\.?")


_SIGLE_ALLEGATO = sorted(
    [(_sigla_pattern(sigla), identity, sigla) for identity, sigla in ANNEX_SIGLE.items() if "." in sigla]
    + [(_sigla_pattern(sigla), None, sigla) for sigla in _SIGLE_MULTIPAROLA],
    key=lambda item: -len(item[2]))


def _sigla_di_allegato(name: str) -> dict | None:
    """The act a sigla of an annex of a code's decree names (VisuaLex's ``ANNEX_SIGLE``, G-369),
    or a code sigla of more than one word, however dotted or spaced; else None.

    An annex is the code's row and the annex («disp. att. c.p.a.» is the c.p.a.'s decree at
    annex 3, never the c.p.a.), as VisuaLex keys it; a row keyed by that very annex needs none.
    """
    text = " ".join((name or "").lower().split())
    for pattern, identity, sigla in _SIGLE_ALLEGATO:
        if not pattern.fullmatch(text):
            continue
        if text != sigla:
            known = resolve_atto(sigla)  # the tables know the canonical spelling first
            if known:
                return known
        if identity is None:
            return None
        row = code_row_of_annex(identity)
        details = extract_codice_details(row[0]) if row else None
        if not details:
            return None
        result = {"tipo_atto": row[0], "data": details["data"], "numero_atto": details["numero_atto"]}
        if NORMATTIVA_URN_CODICI.get(row[0]) != identity:
            result["allegato"] = row[1]
        return result
    return None


def strip_leading_particles(name: str) -> str:
    """Normalize an act name and drop leading articles/prepositions.

    "del D.Lgs. 231/2001" → "d.lgs. 231/2001", so pattern matching downstream
    sees the act itself rather than the preposition that introduced it.
    """
    return _strip_leading_words(_normalize_key(name))


def known_act_names() -> list[str]:
    """Every act name the resolver recognises — used to suggest near misses."""
    return sorted(set(ATTI_NOTI) | set(ATTI_DENOMINATI) | set(NORMATTIVA_SEARCH) | set(NORMATTIVA_URN_CODICI)
                  | set(SIGLE_DATATE))


def _brocardi_by_identity(tipo_atto: str, numero_atto: str, data: str) -> str | None:
    """URL for (tipo, numero[, anno]); None when the year is missing and ambiguous."""
    if not numero_atto:
        return None
    anno = data.strip()[:4] if data else ""
    if anno:
        return _BROCARDI_BY_IDENTITY.get((tipo_atto, anno, numero_atto))
    candidates = _BROCARDI_BY_TIPO_NUMERO.get((tipo_atto, numero_atto), set())
    return next(iter(candidates)) if len(candidates) == 1 else None


def _brocardi_by_name(tipo_lower: str, numero_atto: str, data: str) -> str | None:
    """URL for a Brocardi display name, provided any extremes given agree with it."""
    url = _BROCARDI_BY_NAME.get(tipo_lower)
    if url is None:
        return None
    if not numero_atto:
        return url
    own = _BROCARDI_NAME_ESTREMI.get(tipo_lower)
    if own is None or own[2] != numero_atto:
        return None
    anno = data.strip()[:4] if data else ""
    return url if not anno or anno == own[1] else None


def find_brocardi_url(tipo_atto: str, numero_atto: str = "", data: str = "") -> str | None:
    """Brocardi base URL for an act, matched by identity — never by substring.

    Order: the labels without extremes by name (Preleggi share the codice
    civile's R.D. 262/1942); a codice through the extremes of its Normattiva
    URN, which is how "codice in materia di protezione dei dati personali"
    reaches the page Brocardi calls "Codice della privacy" — unless the caller
    passed extremes of its own, which then must match; the identity (tipo,
    anno, numero) — without a year only if the number is unique for that tipo;
    finally the plain Brocardi name, again only if any extremes given agree
    with it. An act that is not on Brocardi yields None rather than the
    nearest label.
    """
    tipo_lower = re.sub(r"\s+", " ", tipo_atto.lower().strip())
    if not tipo_lower:
        return None

    if tipo_lower in _BROCARDI_BARE_NAMES:
        return _BROCARDI_BARE_NAMES[tipo_lower]

    anno = data.strip()[:4] if data else ""
    codice = extract_codice_details(tipo_lower)
    if codice:
        same_numero = not numero_atto or numero_atto == codice["numero_atto"]
        same_anno = not anno or anno == codice["data"][:4]
        if same_numero and same_anno:
            found = _brocardi_by_identity(codice["tipo_atto_reale"], codice["numero_atto"], codice["data"])
            if found:
                return found
        elif numero_atto:
            # Explicit extremes that contradict the URN name the act themselves:
            # "codice dei contratti pubblici" + 50/2016 is the abrogated code.
            return _brocardi_by_identity(codice["tipo_atto_reale"], numero_atto, data)

    tipo_esteso = normalize_act_type(tipo_lower).lower()
    if tipo_esteso in ("reg. ue", "regolamento (ue)"):
        tipo_esteso = "regolamento ue"
    found = _brocardi_by_identity(tipo_esteso, numero_atto, data)
    if found:
        return found

    return _brocardi_by_name(tipo_lower, numero_atto, data)


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


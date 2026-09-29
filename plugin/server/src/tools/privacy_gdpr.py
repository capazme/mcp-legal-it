"""GDPR/Privacy compliance tools: informative privacy (art. 13-14), cookie policy,
informativa dipendenti, videosorveglianza, DPA (art. 28), registro trattamenti (art. 30),
DPIA (art. 35), analisi base giuridica, verifica necessità DPIA, valutazione data breach,
calcolo sanzioni GDPR, notifica data breach (art. 33)."""

import json
import re
from datetime import datetime, timedelta
from pathlib import Path

from src.lib import _clock
from src.server import mcp
from src.lib._data import sourced

_DATA = Path(__file__).resolve().parent.parent / "data"

with open(_DATA / "gdpr_sanzioni.json") as f:
    _SANZIONI = json.load(f)

with open(_DATA / "gdpr_basi_giuridiche.json") as f:
    _BASI = json.load(f)

with open(_DATA / "gdpr_dpia_criteri.json") as f:
    _DPIA = json.load(f)


# ---------------------------------------------------------------------------
# Tool 1: genera_informativa_privacy
# ---------------------------------------------------------------------------

# A `6(1)(f)` basis (legitimate interests) obliges the notice to name the interests pursued
# (art. 13(1)(d) / art. 14(2)(b) GDPR): the tool recognises it in the caller's own wording.
_RE_LEGITTIMO_INTERESSE = re.compile(
    r"6\s*\(\s*1\s*\)\s*\(\s*f\s*\)|legittim[oi]\s+interess", re.IGNORECASE
)


def _genera_informativa_privacy_impl(
    titolare: str,
    finalita: list[str],
    basi_giuridiche: list[str],
    categorie_dati: list[str],
    destinatari: list[str],
    periodo_conservazione: str,
    tipo: str = "art13",
    dpo: str = "",
    diritti_esercitabili: list[str] | None = None,
    trasferimento_extra_ue: str = "",
    legittimi_interessi: str = "",
    conferimento: str = "",
    decisioni_automatizzate: str = "",
    fonte_dati: str = "",
    garanzia_trasferimento: str = "",
) -> dict:
    if diritti_esercitabili is None:
        diritti_esercitabili = [
            "accesso (art. 15)",
            "rettifica (art. 16)",
            "cancellazione (art. 17)",
            "limitazione del trattamento (art. 18)",
            "portabilità dei dati (art. 20)",
            "opposizione al trattamento (art. 21)",
            "revoca del consenso (art. 7(3))",
        ]

    if tipo not in ("art13", "art14"):
        return {"errore": "tipo deve essere 'art13' o 'art14'"}

    riferimento = "Art. 13 Reg. UE 2016/679 (GDPR)" if tipo == "art13" else "Art. 14 Reg. UE 2016/679 (GDPR)"
    titolo_tipo = "raccogliendo i Suoi dati personali direttamente da Lei" if tipo == "art13" else "avendo ottenuto i Suoi dati personali da fonti diverse da Lei"

    finalita_text = "\n".join(f"  {i+1}. {f}" for i, f in enumerate(finalita))
    basi_text = "\n".join(f"  {i+1}. {b}" for i, b in enumerate(basi_giuridiche))
    dati_text = "\n".join(f"  - {d}" for d in categorie_dati)
    destinatari_text = "\n".join(f"  - {d}" for d in destinatari)
    diritti_text = "\n".join(f"  - {d}" for d in diritti_esercitabili)

    legittimo_interesse = any(_RE_LEGITTIMO_INTERESSE.search(b) for b in basi_giuridiche)
    da_completare: list[str] = []
    avvertenze: list[str] = []

    def _o_segnaposto(valore: str, campo: str, istruzione: str) -> str:
        """The caller's text, or a visible placeholder that the checklist reports as open."""
        valore = valore.strip()
        if valore:
            return valore
        da_completare.append(campo)
        return f"[DA COMPLETARE: {istruzione}]"

    # Sections in document order; the numbering is assigned at the end, so that an omitted
    # optional section never leaves a gap (1, 2, 3, ... N).
    sezioni: list[tuple[str, str]] = [
        (
            "TITOLARE DEL TRATTAMENTO",
            f"{titolare}\n"
            "Per esercitare i Suoi diritti o per qualsiasi informazione sul trattamento dei Suoi dati personali,\n"
            "può contattare il Titolare agli indirizzi sopra indicati.",
        )
    ]

    if tipo == "art14":
        fonte = _o_segnaposto(
            fonte_dati,
            "fonte_dati",
            "indicare la fonte specifica da cui hanno origine i dati personali e se provengono da "
            "fonti accessibili al pubblico (art. 14(2)(f) GDPR)",
        )
        sezioni.append((
            "FONTE DEI DATI",
            "I Suoi dati personali non sono stati raccolti presso di Lei.\n"
            f"Fonte da cui hanno origine i dati: {fonte}",
        ))

    sezioni.append((
        "FINALITÀ E BASI GIURIDICHE DEL TRATTAMENTO",
        "Il Titolare tratta i Suoi dati personali per le seguenti finalità e sulla base delle\n"
        "corrispondenti basi giuridiche (art. 6 GDPR):\n\n"
        f"{finalita_text}\n\n"
        "Le basi giuridiche del trattamento sono:\n"
        f"{basi_text}",
    ))

    if legittimo_interesse:
        interessi = _o_segnaposto(
            legittimi_interessi,
            "legittimi_interessi",
            "indicare i legittimi interessi perseguiti dal Titolare o da terzi "
            f"(art. {'13(1)(d)' if tipo == 'art13' else '14(2)(b)'} GDPR)",
        )
        sezioni.append((
            "LEGITTIMI INTERESSI PERSEGUITI DAL TITOLARE O DA TERZI",
            "Per le finalità fondate sull'art. 6(1)(f) GDPR, i legittimi interessi perseguiti dal Titolare\n"
            f"o da terzi sono i seguenti:\n  {interessi}",
        ))

    sezioni.append((
        "CATEGORIE DI DATI PERSONALI TRATTATI",
        f"Il Titolare tratta le seguenti categorie di dati personali:\n{dati_text}",
    ))

    sezioni.append((
        "DESTINATARI O CATEGORIE DI DESTINATARI",
        "I Suoi dati personali potranno essere comunicati alle seguenti categorie di destinatari:\n"
        f"{destinatari_text}\n\n"
        "I dati non saranno diffusi, salvo espressa previsione di legge o Suo consenso.\n"
        "I soggetti appartenenti alle categorie sopra indicate svolgono la funzione di responsabili\n"
        "del trattamento (art. 28 GDPR), di persone autorizzate al trattamento sotto l'autorità del\n"
        "titolare o del responsabile (art. 29 GDPR; art. 2-quaterdecies D.Lgs. 196/2003) ovvero operano\n"
        "in autonomia come distinti titolari del trattamento.",
    ))

    if dpo:
        sezioni.append((
            "RESPONSABILE DELLA PROTEZIONE DEI DATI (DPO)",
            "Il titolare ha designato un Responsabile della Protezione dei Dati (DPO) contattabile a:\n"
            f"  {dpo}",
        ))

    if trasferimento_extra_ue:
        garanzia = _o_segnaposto(
            garanzia_trasferimento,
            "garanzia_trasferimento",
            "indicare se esiste o manca una decisione di adeguatezza della Commissione europea "
            "(art. 45 GDPR) oppure le garanzie appropriate applicate ai sensi degli artt. 46, 47 o 49, "
            "secondo comma, GDPR",
        )
        sezioni.append((
            "TRASFERIMENTO VERSO PAESI TERZI",
            "I Suoi dati personali potranno essere trasferiti verso paesi terzi o organizzazioni internazionali\n"
            "nelle seguenti modalità:\n"
            f"  {trasferimento_extra_ue}\n"
            f"Decisione di adeguatezza o garanzie applicate: {garanzia}\n"
            "Per ottenere una copia delle garanzie, o conoscere il luogo in cui sono state rese disponibili,\n"
            "può rivolgersi al Titolare ai recapiti indicati al punto 1.",
        ))

    sezioni.append((
        "PERIODO DI CONSERVAZIONE",
        "I Suoi dati personali saranno conservati per il seguente periodo:\n"
        f"  {periodo_conservazione}\n\n"
        "Decorso tale termine, i dati saranno cancellati o resi anonimi in modo irreversibile,\n"
        "salvo obblighi di conservazione previsti dalla legge.",
    ))

    if tipo == "art13":
        obbligo = _o_segnaposto(
            conferimento,
            "conferimento",
            "indicare se la comunicazione dei dati è un obbligo legale o contrattuale oppure un requisito "
            "necessario per la conclusione di un contratto, se Lei è obbligato a fornire i dati e le "
            "possibili conseguenze della mancata comunicazione (art. 13(2)(e) GDPR)",
        )
        sezioni.append((
            "CONFERIMENTO DEI DATI",
            f"Natura del conferimento e conseguenze della mancata comunicazione: {obbligo}",
        ))

    if decisioni_automatizzate.strip():
        automatizzato = (
            "Il Titolare adotta un processo decisionale automatizzato, compresa la profilazione di cui\n"
            "all'art. 22, paragrafi 1 e 4, GDPR. Logica utilizzata, importanza e conseguenze previste per\n"
            f"l'interessato: {decisioni_automatizzate.strip()}"
        )
    else:
        automatizzato = (
            "Il Titolare non adotta alcun processo decisionale unicamente automatizzato, compresa la\n"
            "profilazione di cui all'art. 22, paragrafi 1 e 4, GDPR."
        )
        avvertenze.append(
            "decisioni_automatizzate non indicate: il testo dichiara che non esiste alcun processo "
            "decisionale automatizzato o profilazione (art. 13(2)(f) / 14(2)(g) GDPR); se esiste, "
            "compilare il parametro con logica, importanza e conseguenze"
        )
    sezioni.append(("PROCESSO DECISIONALE AUTOMATIZZATO E PROFILAZIONE", automatizzato))

    sezioni.append((
        "DIRITTI DELL'INTERESSATO",
        "In qualità di interessato, Lei ha il diritto di:\n"
        f"{diritti_text}\n\n"
        "Per esercitare i Suoi diritti, può inviare una richiesta scritta al Titolare del trattamento.\n"
        "Il Titolare risponderà entro un mese dalla ricezione della richiesta, prorogabile di due mesi per richieste complesse o numerose (art. 12(3) GDPR).",
    ))

    sezioni.append((
        "DIRITTO DI PROPORRE RECLAMO",
        "Lei ha il diritto di proporre reclamo all'Autorità di controllo competente.\n"
        "In Italia: Garante per la protezione dei dati personali\n"
        "Sito web: www.garanteprivacy.it\n"
        "E-mail: protocollo@gpdp.it\n"
        "PEC: protocollo@pec.gpdp.it\n"
        "Indirizzo: Piazza Venezia n. 11, 00187 Roma",
    ))

    corpo = "\n\n".join(
        f"{i}. {titolo}\n{testo_sezione}" for i, (titolo, testo_sezione) in enumerate(sezioni, start=1)
    )

    testo = f"""INFORMATIVA SUL TRATTAMENTO DEI DATI PERSONALI
ai sensi {riferimento}

Gentile Interessato/a,
in ottemperanza a quanto previsto dal Regolamento (UE) 2016/679 (di seguito "GDPR"), La informiamo
che {titolare} (di seguito "Titolare"), {titolo_tipo}, tratta i Suoi dati personali.

{corpo}

Informativa aggiornata ai sensi del Reg. UE 2016/679 (GDPR) e del D.Lgs. 196/2003
come modificato dal D.Lgs. 101/2018.
"""

    # Checklist of the elements of art. 13(1)-(2) / art. 14(1)-(2) GDPR. An element that depends
    # on the caller's input (legitimate interests, nature of the provision of data, source of the
    # data, safeguards of a transfer) is satisfied only when the caller supplied it: otherwise the
    # text carries a "[DA COMPLETARE: ...]" placeholder and the element stays False.
    elementi_obbligatori = {
        "identita_titolare": bool(titolare),
        "finalita_trattamento": len(finalita) > 0,
        "base_giuridica": len(basi_giuridiche) > 0,
        "categorie_dati": len(categorie_dati) > 0,
        "destinatari": len(destinatari) > 0,
        "periodo_conservazione": bool(periodo_conservazione),
        "diritti_interessato": len(diritti_esercitabili) > 0,
        "diritto_reclamo": True,
        # The DPO section appears whenever `dpo` is given: nothing to check otherwise.
        "dpo_se_nominato": True,
        # Art. 13(1)(d) / 14(2)(b): only when a 6(1)(f) basis is declared.
        "legittimi_interessi_se_art_6_1_f": (not legittimo_interesse) or bool(legittimi_interessi.strip()),
        # Art. 13(1)(f) / 14(1)(f): only when a transfer is declared.
        "trasferimento_extra_ue_se_presente": (not trasferimento_extra_ue) or bool(garanzia_trasferimento.strip()),
        # Art. 13(2)(f) / 14(2)(g): the text always takes a position (existence or absence).
        "decisioni_automatizzate": True,
    }

    if tipo == "art13":
        elementi_obbligatori["conferimento_e_conseguenze"] = bool(conferimento.strip())
    else:
        elementi_obbligatori["fonte_dati"] = bool(fonte_dati.strip())
        elementi_obbligatori["categorie_dati_fonte"] = len(categorie_dati) > 0

    tutti_verificati = all(elementi_obbligatori.values())

    return {
        "testo": testo.strip(),
        "elementi_obbligatori_verificati": elementi_obbligatori,
        "tutti_elementi_presenti": tutti_verificati,
        "campi_da_completare": da_completare,
        "avvertenze": avvertenze,
        "tipo": tipo,
        "riferimento_normativo": riferimento,
    }


@mcp.tool(tags={"privacy"})
def genera_informativa_privacy(
    titolare: str,
    finalita: list[str],
    basi_giuridiche: list[str],
    categorie_dati: list[str],
    destinatari: list[str],
    periodo_conservazione: str,
    tipo: str = "art13",
    dpo: str = "",
    diritti_esercitabili: list[str] | None = None,
    trasferimento_extra_ue: str = "",
    legittimi_interessi: str = "",
    conferimento: str = "",
    decisioni_automatizzate: str = "",
    fonte_dati: str = "",
    garanzia_trasferimento: str = "",
) -> dict:
    """Genera un'informativa privacy completa ai sensi dell'art. 13 o 14 GDPR.

    Usa questo tool quando: devi redigere o verificare un'informativa sul trattamento dei
    dati personali per un sito web, un'azienda, un'associazione o qualsiasi titolare.
    Art. 13 = dati raccolti direttamente dall'interessato (es. modulo di contatto, acquisto).
    Art. 14 = dati ottenuti da terzi o fonti indirette (es. liste, partner, fonti pubbliche).
    Chaining: → genera_dpa() per i responsabili del trattamento → genera_registro_trattamenti()
    Vigenza: artt. 12, 13 e 14 Reg. (UE) 2016/679 nel testo vigente al 29/09/2026; recapiti del
    Garante come pubblicati su garanteprivacy.it (protocollo@gpdp.it, PEC protocollo@pec.gpdp.it).
    Precisione: INDICATIVO (modello redazionale: gli elementi che dipendono dal caso concreto,
    cioè legittimi interessi, natura del conferimento, fonte dei dati e garanzie del trasferimento,
    compaiono come «[DA COMPLETARE: ...]» finché non vengono forniti, e la checklist li segna
    mancanti; la valutazione di adeguatezza del documento resta del titolare).

    Args:
        titolare: Denominazione completa del titolare del trattamento (ragione sociale e sede)
        finalita: Lista delle finalità del trattamento (es. ['gestione clienti', 'marketing'])
        basi_giuridiche: Lista delle basi giuridiche (es. ['art. 6(1)(b) - contratto', 'art. 6(1)(a) - consenso'])
        categorie_dati: Categorie di dati personali trattati (es. ['dati anagrafici', 'dati di contatto'])
        destinatari: Categorie di destinatari (es. ['dipendenti autorizzati', 'fornitori IT', 'commercialista'])
        periodo_conservazione: Periodo o criterio di conservazione (es. '10 anni per obblighi fiscali')
        tipo: 'art13' se i dati sono raccolti direttamente, 'art14' se ottenuti da terzi
        dpo: Contatti del DPO (Responsabile Protezione Dati), se nominato (lasciare vuoto se assente)
        diritti_esercitabili: Lista dei diritti esercitabili (default: tutti i 7 diritti art. 15-21)
        trasferimento_extra_ue: Descrizione del trasferimento extra-UE, se presente (vuoto se assente)
        legittimi_interessi: Legittimi interessi perseguiti dal titolare o da terzi (art. 13(1)(d) / 14(2)(b)); richiesti se una base è l'art. 6(1)(f)
        conferimento: Art. 13(2)(e): se la comunicazione dei dati è un obbligo legale o contrattuale o un requisito per concludere il contratto, se l'interessato è obbligato a fornirli e le conseguenze della mancata comunicazione (solo art13)
        decisioni_automatizzate: Art. 13(2)(f) / 14(2)(g): logica, importanza e conseguenze di un processo decisionale automatizzato o di una profilazione; se vuoto il testo dichiara che non ne esistono
        fonte_dati: Art. 14(2)(f): fonte specifica da cui hanno origine i dati e se è accessibile al pubblico (solo art14)
        garanzia_trasferimento: Art. 13(1)(f) / 14(1)(f): decisione di adeguatezza o garanzie appropriate applicate al trasferimento (artt. 45, 46, 47, 49 co. 2) e mezzi per ottenerne copia; richiesta se c'è un trasferimento extra-UE
    """
    return _genera_informativa_privacy_impl(
        titolare=titolare,
        finalita=finalita,
        basi_giuridiche=basi_giuridiche,
        categorie_dati=categorie_dati,
        destinatari=destinatari,
        periodo_conservazione=periodo_conservazione,
        tipo=tipo,
        dpo=dpo,
        diritti_esercitabili=diritti_esercitabili,
        trasferimento_extra_ue=trasferimento_extra_ue,
        legittimi_interessi=legittimi_interessi,
        conferimento=conferimento,
        decisioni_automatizzate=decisioni_automatizzate,
        fonte_dati=fonte_dati,
        garanzia_trasferimento=garanzia_trasferimento,
    )


# ---------------------------------------------------------------------------
# Tool 2: genera_informativa_cookie
# ---------------------------------------------------------------------------

def _genera_informativa_cookie_impl(
    titolare: str,
    cookie_tecnici: list[str],
    sito_web: str,
    cookie_analytics: list[str] | None = None,
    cookie_profilazione: list[str] | None = None,
) -> dict:
    cookie_analytics = cookie_analytics or []
    cookie_profilazione = cookie_profilazione or []

    tabella_cookie = []

    for nome in cookie_tecnici:
        tabella_cookie.append({
            "nome": nome,
            "tipo": "Tecnico",
            "finalita": "Funzionamento del sito, navigazione, sessione utente",
            "durata": "Sessione / fino a 12 mesi",
            "fornitore": titolare,
            "base_giuridica": "Art. 6(1)(b) GDPR — necessario per erogare il servizio; non richiede consenso (art. 122(1) D.Lgs. 196/2003)",
        })

    for nome in cookie_analytics:
        tabella_cookie.append({
            "nome": nome,
            "tipo": "Analitico/statistico",
            "finalita": "Analisi statistica aggregata degli accessi e del comportamento degli utenti",
            "durata": "Fino a 13 mesi",
            "fornitore": "Terza parte (es. Google Analytics, Matomo)",
            "base_giuridica": (
                "Consenso (art. 122(1) D.Lgs. 196/2003; art. 6(1)(a) GDPR), salvo che il cookie sia "
                "equiparato a un cookie tecnico (Linee guida Garante 10/06/2021, par. 7.2): IP mascherato "
                "almeno nella quarta componente, sole statistiche aggregate su un solo sito o app, "
                "nessuna combinazione né trasmissione dei dati da parte del fornitore"
            ),
        })

    for nome in cookie_profilazione:
        tabella_cookie.append({
            "nome": nome,
            "tipo": "Profilazione/marketing",
            "finalita": "Profilazione dell'utente per finalità di marketing e pubblicità personalizzata",
            "durata": "Fino a 12 mesi",
            "fornitore": "Terza parte",
            "base_giuridica": "Consenso esplicito (art. 6(1)(a) GDPR) — obbligatorio (Linee Guida Garante 10/06/2021)",
        })

    ha_profilazione = len(cookie_profilazione) > 0
    ha_analytics = len(cookie_analytics) > 0

    banner_testo = (
        "Questo sito utilizza cookie tecnici necessari al funzionamento"
    )
    if ha_analytics or ha_profilazione:
        banner_testo += (
            " e, previo Suo consenso, cookie analitici"
            if ha_analytics and not ha_profilazione
            else " e, previo Suo consenso, cookie analitici e di profilazione"
            if ha_analytics and ha_profilazione
            else " e, previo Suo consenso, cookie di profilazione"
        )
        banner_testo += (
            " per finalità di marketing personalizzato."
            if ha_profilazione
            else "."
        )
        # Linee guida Garante 10/06/2021, par. 7.1, point i): the banner must warn that closing it
        # with the X keeps the default settings, i.e. browsing without non-technical cookies.
        banner_testo += (
            " Può accettare, rifiutare o personalizzare le sue preferenze. "
            "Chiudendo il banner con la X in alto a destra restano attive le impostazioni di default "
            "e la navigazione prosegue senza cookie o altri strumenti di tracciamento diversi da quelli tecnici. "
            "Per maggiori informazioni consulti la nostra Cookie Policy."
        )
    else:
        banner_testo += ". Non utilizziamo cookie di profilazione o marketing."

    nomi_tecnici = ", ".join(cookie_tecnici) if cookie_tecnici else "nessuno"
    nomi_analytics = ", ".join(cookie_analytics) if cookie_analytics else "nessuno"
    nomi_profilazione = ", ".join(cookie_profilazione) if cookie_profilazione else "nessuno"

    profilazione_section = ""
    if ha_profilazione:
        profilazione_section = f"""
4. COOKIE DI PROFILAZIONE E MARKETING (richiedono consenso)
I cookie di profilazione sono utilizzati per creare profili relativi agli utenti e per inviare
messaggi pubblicitari in linea con le preferenze manifestate durante la navigazione.
Utilizziamo i seguenti cookie di profilazione (attivi solo previo consenso):
  {nomi_profilazione}

Per i cookie di profilazione di terze parti, il consenso deve essere raccolto prima
dell'installazione dei cookie stessi. Lei può revocare il consenso in qualsiasi momento
tramite il pannello delle preferenze cookie del sito.
"""

    analytics_section = ""
    if ha_analytics:
        analytics_section = f"""
3. COOKIE ANALITICI
I cookie analitici consentono di contare le visite e le fonti di traffico in modo da poter
misurare e migliorare le prestazioni del sito.
Utilizziamo i seguenti cookie analitici:
  {nomi_analytics}

Questi cookie sono equiparati ai cookie tecnici, e quindi utilizzati senza il Suo consenso, solo
se sono soddisfatte tutte queste condizioni (Linee guida del Garante del 10 giugno 2021, par. 7.2):
  a) l'indirizzo IP è mascherato almeno nella quarta componente (IPv4), o con misure analoghe per
     gli indirizzi IPv6, in modo da impedire l'individuazione diretta dell'utente;
  b) i dati sono usati solo per statistiche aggregate, riferite a un singolo sito o applicazione;
  c) il fornitore terzo non combina i dati con altre elaborazioni né li trasmette a ulteriori terzi
     (salvo statistiche riferite a più domini dello stesso titolare o gruppo).
In mancanza anche di una sola di queste condizioni è richiesto il Suo consenso (art. 122(1)
D.Lgs. 196/2003). L'eventuale trasferimento di dati verso paesi terzi è disciplinato a parte
dal capo V del GDPR (artt. 44-49 GDPR) e non incide su questa distinzione.
"""

    testo = f"""COOKIE POLICY
{sito_web}

Informativa ai sensi dell'art. 122 D.Lgs. 196/2003 e delle Linee Guida del Garante per
la protezione dei dati personali del 10 giugno 2021 (doc. web 9677876)

TITOLARE DEL TRATTAMENTO
{titolare}

1. COSA SONO I COOKIE
I cookie sono piccoli file di testo che i siti visitati dall'utente inviano al suo terminale
(computer, tablet, smartphone), dove vengono memorizzati per essere poi ritrasmessi agli stessi
siti in occasione di visite successive.

2. COOKIE TECNICI (non richiedono consenso)
I cookie tecnici sono necessari per il corretto funzionamento del sito e per la fornitura
del servizio richiesto dall'utente. Non richiedono il consenso dell'utente (art. 122(1) D.Lgs. 196/2003).
Utilizziamo i seguenti cookie tecnici:
  {nomi_tecnici}
{analytics_section}{profilazione_section}
5. COME GESTIRE I COOKIE
Alla prima visita Le viene presentato un banner. La chiusura del banner mediante il comando X, in
alto a destra, mantiene le impostazioni di default: la navigazione prosegue senza cookie o altri
strumenti di tracciamento diversi da quelli tecnici. Il semplice scorrimento della pagina (scroll)
non costituisce consenso all'installazione di cookie diversi da quelli tecnici.

Lei può gestire le proprie preferenze relative ai cookie anche mediante le impostazioni del browser
che utilizza. Tuttavia, la disabilitazione dei cookie tecnici potrebbe pregiudicare il
corretto funzionamento del sito.

Browser principali:
  - Chrome: Impostazioni > Privacy e sicurezza > Cookie e altri dati dei siti
  - Firefox: Opzioni > Privacy e sicurezza > Cookie e dati dei siti
  - Safari: Preferenze > Privacy > Gestisci dati siti web
  - Edge: Impostazioni > Privacy, ricerca e servizi > Cookie

6. TITOLARE DEL TRATTAMENTO E CONTATTI
Titolare: {titolare}
Per esercitare i diritti ex artt. 15-22 GDPR o per informazioni sui cookie:
inviare richiesta scritta al Titolare del trattamento.
Diritto di reclamo: Garante per la protezione dei dati personali — www.garanteprivacy.it

Cookie Policy aggiornata ai sensi del Reg. UE 2016/679 (GDPR), dell'art. 122 D.Lgs. 196/2003
e delle Linee Guida del Garante del 10/06/2021.
"""

    risultato = {
        "testo": testo.strip(),
        "tabella_cookie": tabella_cookie,
        "banner_testo_suggerito": banner_testo,
        # Prudential default: analytics are treated as needing consent unless the conditions of
        # par. 7.2 (listed in `condizioni_equiparazione_analytics`) are all verified by the owner.
        "consenso_richiesto_analytics": ha_analytics,
        "consenso_richiesto_profilazione": ha_profilazione,
        "riferimento_normativo": "Art. 122 D.Lgs. 196/2003; Linee Guida Garante 10/06/2021 (doc. web 9677876); Art. 6(1)(a) GDPR",
    }
    if ha_analytics:
        risultato["condizioni_equiparazione_analytics"] = [
            "IP mascherato almeno nella quarta componente (IPv4) o misure analoghe (IPv6)",
            "solo statistiche aggregate, riferite a un singolo sito o applicazione",
            "il fornitore terzo non combina i dati con altre elaborazioni né li trasmette a ulteriori terzi",
        ]
    if ha_analytics or ha_profilazione:
        # Rules on how the consent mechanism must work (Linee guida 10/06/2021, par. 6.1, 6.2, 7.1):
        # they bind the CMP configuration, not the text of the policy.
        risultato["note_implementazione_banner"] = [
            "il comando X di chiusura, in alto a destra, ha evidenza grafica pari agli altri comandi (par. 7.1)",
            "lo scroll non equivale a consenso (par. 6.1)",
            "dopo un rifiuto il banner non si ripropone prima di 6 mesi, salvo mutamento significativo "
            "delle condizioni del trattamento o impossibilità di sapere se il cookie sia già memorizzato (par. 6.2)",
        ]
    return risultato


@mcp.tool(tags={"privacy"})
def genera_informativa_cookie(
    titolare: str,
    cookie_tecnici: list[str],
    sito_web: str,
    cookie_analytics: list[str] | None = None,
    cookie_profilazione: list[str] | None = None,
) -> dict:
    """Genera una cookie policy completa con tabella cookie e testo banner di consenso.

    Usa questo tool quando: un sito web deve adempiere agli obblighi di informativa cookie
    previsti dall'art. 122 D.Lgs. 196/2003 e dalle Linee Guida Garante del 10/06/2021.
    Distingue cookie tecnici (no consenso), analitici e di profilazione (consenso).
    I cookie analitici di terze parti sono equiparati ai tecnici, e quindi senza consenso, solo se
    l'IP è mascherato (almeno la quarta componente), le statistiche sono aggregate su un solo sito
    e il fornitore non combina né ritrasmette i dati (par. 7.2 Linee guida); il trasferimento
    extra-UE non è il criterio (capo V GDPR). Il tool per prudenza richiede il consenso per gli
    analitici (`consenso_richiesto_analytics`) e riporta le condizioni di equiparazione.
    Chaining: → genera_informativa_privacy() per l'informativa generale del sito
    Vigenza: art. 122 D.Lgs. 196/2003 e Linee guida cookie del Garante, provv. n. 231 del
    10/06/2021 (doc. web 9677876), testo vigente al 29/09/2026.
    Precisione: INDICATIVO (modello di policy e di banner: la classificazione dei singoli cookie
    e la verifica delle condizioni di equiparazione degli analitici restano del titolare).

    Args:
        titolare: Ragione sociale e recapiti del titolare del sito
        cookie_tecnici: Lista nomi cookie tecnici (es. ['PHPSESSID', 'csrf_token', '__cfduid'])
        sito_web: URL del sito web (es. 'https://www.esempio.it')
        cookie_analytics: Lista nomi cookie analitici/statistici (es. ['_ga', '_gid', '_gat'])
        cookie_profilazione: Lista nomi cookie di profilazione/marketing (es. ['_fbp', 'IDE', 'NID'])
    """
    return _genera_informativa_cookie_impl(
        titolare=titolare,
        cookie_tecnici=cookie_tecnici,
        sito_web=sito_web,
        cookie_analytics=cookie_analytics,
        cookie_profilazione=cookie_profilazione,
    )


# ---------------------------------------------------------------------------
# Tool 3: genera_informativa_dipendenti
# ---------------------------------------------------------------------------

def _genera_informativa_dipendenti_impl(
    titolare: str,
    dpo: str = "",
    videosorveglianza: bool = False,
    geolocalizzazione: bool = False,
    strumenti_aziendali: bool = False,
) -> dict:
    adempimenti_aggiuntivi = []

    video_section = ""
    if videosorveglianza:
        video_section = """
VIDEOSORVEGLIANZA
Il datore di lavoro utilizza sistemi di videosorveglianza nelle seguenti aree comuni aziendali
per finalità di sicurezza, tutela del patrimonio aziendale e prevenzione di illeciti.
I sistemi di videosorveglianza sono installati previa stipula di accordo sindacale (art. 4(1) L. 300/1970)
ovvero autorizzazione dell'Ispettorato Territoriale del Lavoro (art. 4(1) L. 300/1970).
Le immagini sono conservate per un massimo di 24-72 ore salvo esigenze investigative documentate.
Ulteriori informazioni sono disponibili nell'apposita informativa videosorveglianza esposta nei locali.
"""
        adempimenti_aggiuntivi.append(
            "Accordo sindacale o autorizzazione ITL ex art. 4 L. 300/1970 per videosorveglianza"
        )
        adempimenti_aggiuntivi.append(
            "Cartello videosorveglianza EDPB esposto all'ingresso delle aree riprese"
        )

    geo_section = ""
    if geolocalizzazione:
        geo_section = """
GEOLOCALIZZAZIONE
Il datore di lavoro utilizza sistemi di geolocalizzazione su veicoli aziendali per finalità di:
sicurezza del lavoratore, organizzazione del lavoro, tutela del patrimonio aziendale.
La geolocalizzazione avviene durante l'orario di lavoro. I dati sono conservati per 6 mesi.
L'utilizzo dei sistemi di geolocalizzazione è avvenuto previa stipula di accordo sindacale
(art. 4(1) L. 300/1970) ovvero autorizzazione dell'Ispettorato Territoriale del Lavoro (art. 4(1) L. 300/1970).
"""
        adempimenti_aggiuntivi.append(
            "Accordo sindacale o autorizzazione ITL ex art. 4 L. 300/1970 per geolocalizzazione"
        )

    strumenti_section = ""
    if strumenti_aziendali:
        strumenti_section = """
UTILIZZO DI STRUMENTI AZIENDALI (PC, EMAIL, INTERNET, TELEFONO)
Gli strumenti aziendali (computer, email, accesso internet, telefono aziendale) sono messi
a disposizione del dipendente per lo svolgimento dell'attività lavorativa.
Gli strumenti utilizzati per rendere la prestazione lavorativa non richiedono accordo sindacale
né autorizzazione dell'Ispettorato (art. 4(2) L. 300/1970). Le informazioni raccolte tramite tali
strumenti sono utilizzabili a tutti i fini connessi al rapporto di lavoro a condizione che al
dipendente sia data adeguata informazione delle modalità d'uso degli strumenti e di effettuazione
dei controlli, nel rispetto del D.Lgs. 196/2003 (art. 4(3) L. 300/1970).
Le modalità d'uso degli strumenti e le eventuali modalità di controllo sono descritte nelle policy
aziendali, che il dipendente è tenuto a leggere.
"""
        adempimenti_aggiuntivi.append(
            "Policy aziendale utilizzo strumenti IT (PC, email, internet) da consegnare al dipendente"
        )

    dpo_section = ""
    if dpo:
        dpo_section = f"""
RESPONSABILE DELLA PROTEZIONE DEI DATI (DPO)
Il titolare ha nominato un DPO contattabile a: {dpo}
"""

    adempimenti_aggiuntivi.extend([
        "Consegna dell'informativa al momento dell'assunzione e conservazione firma di ricevuta",
        "Aggiornamento dell'informativa in caso di nuovi trattamenti o modifiche significative",
        "Registro dei trattamenti (art. 30 GDPR) aggiornato con i trattamenti HR",
        "Autorizzazione, con istruzioni, del personale HR che accede ai dati (art. 29 GDPR; "
        "art. 2-quaterdecies D.Lgs. 196/2003)",
    ])

    testo = f"""INFORMATIVA SUL TRATTAMENTO DEI DATI PERSONALI DEI DIPENDENTI
ai sensi dell'art. 13 Reg. UE 2016/679 (GDPR), dell'art. 88 GDPR, dell'art. 113 e dell'art. 114
D.Lgs. 196/2003 e dell'art. 4 L. 300/1970

Gentile Dipendente/Collaboratore,
in qualità di Titolare del trattamento, {titolare} La informa che, nel contesto del rapporto
di lavoro, tratta dati personali che La riguardano. La presente informativa descrive le modalità
di raccolta, utilizzo e protezione dei Suoi dati personali.

1. TITOLARE DEL TRATTAMENTO
{titolare}
{dpo_section}
2. FINALITÀ E BASI GIURIDICHE DEL TRATTAMENTO

a) Gestione del rapporto di lavoro — Base: art. 6(1)(b) GDPR (esecuzione del contratto di lavoro)
   Finalità: amministrazione del personale, pagamento retribuzioni, gestione presenze/assenze,
   gestione ferie, permessi e trasferte, valutazione delle prestazioni.

b) Adempimenti di legge — Base: art. 6(1)(c) GDPR (obbligo legale)
   Finalità: obblighi fiscali e previdenziali (INPS, INAIL, Agenzia delle Entrate), sicurezza sul
   lavoro (D.Lgs. 81/2008), comunicazioni obbligatorie ai centri per l'impiego, adempimenti
   contrattuali e di legge sul lavoro.

c) Dati sanitari (se presenti) — Base: art. 9(2)(b) GDPR + art. 6(1)(c) GDPR
   Finalità: sorveglianza sanitaria obbligatoria ex D.Lgs. 81/2008, gestione malattia/infortunio,
   valutazione idoneità alla mansione. Trattamento effettuato dal medico competente.

d) Tutela del patrimonio aziendale e sicurezza — Base: art. 6(1)(f) GDPR (legittimo interesse)
   Finalità: sicurezza degli accessi ai locali aziendali, tutela del patrimonio, prevenzione illeciti.
{video_section}{geo_section}{strumenti_section}
3. CATEGORIE DI DATI PERSONALI TRATTATI
  - Dati anagrafici e di identificazione (nome, cognome, CF, data/luogo di nascita)
  - Dati di contatto (indirizzo, telefono, email)
  - Dati del documento di identità e/o permesso di soggiorno
  - Dati bancari (IBAN per accredito stipendio)
  - Dati relativi al rapporto di lavoro (posizione, qualifica, livello, retribuzione)
  - Dati di presenze, assenze, ferie e permessi
  - Dati fiscali e previdenziali (codice fiscale, partita IVA se autonomi, posizione INPS/INAIL)
  - Dati sanitari (in capo al medico competente, con accesso limitato al datore ex D.Lgs. 81/2008)
  - Dati relativi a provvedimenti disciplinari

4. DESTINATARI
I dati potranno essere comunicati a:
  - Consulente del lavoro / studio paghe
  - Commercialista / revisore contabile
  - INPS, INAIL, Agenzia delle Entrate e altri enti pubblici previdenziali/fiscali
  - Istituto bancario (per accredito retribuzioni)
  - Medico competente (per sorveglianza sanitaria)
  - Fornitori di servizi IT (gestione paghe, HR software) — in qualità di responsabili del trattamento
  - Autorità giudiziaria in caso di contenzioso

5. PERIODO DI CONSERVAZIONE
  - Dati del rapporto di lavoro: per tutta la durata e per 10 anni successivi alla cessazione
    (prescrizione ordinaria art. 2946 c.c.)
  - Buste paga e documenti contabili: 10 anni (obblighi fiscali)
  - Dati di sorveglianza sanitaria: l'originale della cartella sanitaria e di rischio è conservato dal
    datore di lavoro per almeno 10 anni (art. 25(1)(e) D.Lgs. 81/2008), salvo il diverso termine
    previsto da altre disposizioni dello stesso decreto: per l'esposizione ad agenti cancerogeni o
    mutageni (art. 243(6) D.Lgs. 81/2008), ad amianto (art. 260(4) D.Lgs. 81/2008) e ad agenti
    biologici con gravi sequele (art. 280(4) D.Lgs. 81/2008) l'INAIL conserva la documentazione
    fino a 40 anni
  - Riprese videosorveglianza: 24-72 ore salvo diverse esigenze documentate

6. DIRITTI DELL'INTERESSATO
In qualità di interessato, Lei ha il diritto di:
  - Accesso ai dati che La riguardano (art. 15 GDPR)
  - Rettifica dei dati inesatti (art. 16 GDPR)
  - Cancellazione ("diritto all'oblio") ove applicabile (art. 17 GDPR)
  - Limitazione del trattamento (art. 18 GDPR)
  - Opposizione al trattamento per motivi legittimi (art. 21 GDPR)

Nota: il diritto alla portabilità (art. 20) si applica solo ai trattamenti basati su consenso o contratto
ED effettuati con mezzi automatizzati; non si applica ai trattamenti basati su obbligo legale.

7. DIRITTO DI PROPORRE RECLAMO
Può proporre reclamo al Garante per la protezione dei dati personali (www.garanteprivacy.it).

Informativa resa ai sensi dell'art. 13 e dell'art. 88 GDPR, dell'art. 113 e dell'art. 114 D.Lgs. 196/2003
e dell'art. 4 L. 300/1970.
Data: ___________    Firma per ricevuta: ___________________________
"""

    return {
        "testo": testo.strip(),
        "adempimenti_aggiuntivi": adempimenti_aggiuntivi,
        "riferimento_normativo": (
            "Art. 13 e art. 88 Reg. UE 2016/679 (GDPR); art. 113 e art. 114 D.Lgs. 196/2003; "
            "Art. 4 L. 300/1970 (Statuto dei Lavoratori); D.Lgs. 81/2008 (sicurezza sul lavoro)"
        ),
    }


@mcp.tool(tags={"privacy"})
def genera_informativa_dipendenti(
    titolare: str,
    dpo: str = "",
    videosorveglianza: bool = False,
    geolocalizzazione: bool = False,
    strumenti_aziendali: bool = False,
) -> dict:
    """Genera l'informativa privacy per dipendenti e collaboratori ai sensi dell'art. 13 GDPR.

    Usa questo tool quando: un'azienda deve consegnare l'informativa privacy al personale
    al momento dell'assunzione o aggiornare quella esistente.
    Tiene conto dei vincoli dell'art. 4 L. 300/1970 (Statuto dei Lavoratori) per controlli
    a distanza, videosorveglianza e geolocalizzazione: accordo sindacale e, in mancanza,
    autorizzazione dell'Ispettorato sono entrambi al comma 1; il comma 2 esclude gli strumenti
    di lavoro e di registrazione delle presenze; il comma 3 lega l'utilizzabilità delle
    informazioni all'adeguata informazione del lavoratore.
    Chaining: → genera_informativa_videosorveglianza() se videosorveglianza=True
              → genera_registro_trattamenti() per registrare il trattamento HR
    Vigenza: artt. 13 e 88 Reg. (UE) 2016/679; artt. 113, 114 e 2-quaterdecies D.Lgs. 196/2003;
    art. 4 L. 300/1970 (testo D.Lgs. 151/2015); artt. 25(1)(e), 243(6), 260(4), 280(4) D.Lgs.
    81/2008 (conservazione della cartella sanitaria), testi vigenti al 29/09/2026.
    Precisione: INDICATIVO (modello di informativa; i termini di conservazione di video e GPS,
    24-72 ore e 6 mesi, sono prassi del Garante e non un valore fissato dalla norma).

    Args:
        titolare: Ragione sociale e sede del datore di lavoro (titolare del trattamento)
        dpo: Contatti del DPO se nominato (lasciare vuoto se assente)
        videosorveglianza: True se l'azienda utilizza sistemi di videosorveglianza nei locali
        geolocalizzazione: True se l'azienda utilizza sistemi GPS su veicoli aziendali
        strumenti_aziendali: True se si vuole includere la sezione su PC/email/internet aziendali
    """
    return _genera_informativa_dipendenti_impl(
        titolare=titolare,
        dpo=dpo,
        videosorveglianza=videosorveglianza,
        geolocalizzazione=geolocalizzazione,
        strumenti_aziendali=strumenti_aziendali,
    )


# ---------------------------------------------------------------------------
# Tool 4: genera_informativa_videosorveglianza
# ---------------------------------------------------------------------------

def _genera_informativa_videosorveglianza_impl(
    titolare: str,
    finalita: list[str],
    tempo_conservazione: str,
    aree_riprese: list[str],
) -> dict:
    finalita_text = "; ".join(finalita)
    aree_text = ", ".join(aree_riprese)

    informativa_breve = f"""[AREA VIDEOSORVEGLIATA]
Il titolare {titolare} effettua riprese video in questa area per: {finalita_text}.
Le immagini sono conservate per {tempo_conservazione} e sono trattate ai sensi dell'art. 13 GDPR.
Titolare del trattamento: {titolare}
Per maggiori informazioni e per esercitare i Suoi diritti: [recapiti titolare]"""

    adempimenti_preventivi = [
        "Accordo sindacale (art. 4(1) L. 300/1970) se il sistema controlla lavoratori dipendenti, OPPURE",
        "Autorizzazione dell'Ispettorato Territoriale del Lavoro (ITL) ex art. 4(2) L. 300/1970 (in mancanza di accordo sindacale)",
        "Esposizione del cartello informativo EDPB all'ingresso delle aree videosorvegliate",
        "Inserimento nel Registro dei trattamenti (art. 30 GDPR)",
        "Valutazione della necessità di DPIA se monitoraggio sistematico su larga scala (art. 35 GDPR)",
        "Verifica proporzionalità: le riprese devono limitarsi alle aree strettamente necessarie",
        "Configurazione sistema per cancellazione automatica dopo il termine di conservazione",
        "Accesso limitato alle immagini: solo soggetti autorizzati e per le finalità dichiarate",
    ]

    aree_list = "\n".join(f"  - {area}" for area in aree_riprese)
    finalita_list = "\n".join(f"  - {f}" for f in finalita)

    informativa_estesa = f"""INFORMATIVA SUL SISTEMA DI VIDEOSORVEGLIANZA
ai sensi dell'art. 13 Reg. UE 2016/679 (GDPR) e delle Linee Guida EDPB 3/2019

1. TITOLARE DEL TRATTAMENTO
{titolare}

2. FINALITÀ DEL TRATTAMENTO E BASE GIURIDICA
Il sistema di videosorveglianza è installato per le seguenti finalità:
{finalita_list}

Base giuridica del trattamento: art. 6(1)(f) GDPR — legittimo interesse del titolare alla
sicurezza delle persone, alla tutela del patrimonio e alla prevenzione di atti illeciti,
bilanciato con i diritti degli interessati.

Nei luoghi di lavoro, il sistema opera previa stipula di accordo sindacale (art. 4(1) L. 300/1970)
ovvero previa autorizzazione dell'Ispettorato Territoriale del Lavoro competente (art. 4(2) L. 300/1970).
Il sistema non è utilizzabile per il controllo a distanza dell'attività lavorativa dei dipendenti.

3. AREE SOTTOPOSTE A RIPRESA
Le riprese video sono effettuate nelle seguenti aree:
{aree_list}

Non sono riprese aree dove è ragionevole attendersi riservatezza (bagni, spogliatoi, locali
sindacali). Le telecamere non sono orientate verso aree pubbliche esterne ai locali, salvo
stretta necessità documentata.

4. PERIODO DI CONSERVAZIONE
Le immagini registrate sono conservate per: {tempo_conservazione}

Decorso tale termine, le immagini sono cancellate automaticamente in modo irreversibile.
La conservazione oltre tale limite è possibile solo su richiesta dell'autorità giudiziaria
o di polizia giudiziaria, in relazione a specifici eventi già verificatisi.

5. DESTINATARI
Le immagini sono accessibili esclusivamente al personale autorizzato dal titolare per
finalità di sicurezza. Potranno essere comunicate a:
  - Forze dell'ordine / autorità giudiziaria, su richiesta o in caso di reati
  - Fornitore del servizio di videosorveglianza (in qualità di responsabile del trattamento, art. 28 GDPR)

6. DIRITTI DELL'INTERESSATO
Potrà esercitare i diritti di cui agli artt. 15-22 GDPR (accesso, rettifica, cancellazione,
limitazione, opposizione) inviando richiesta scritta al titolare.
Il diritto di accesso alle riprese dovrà essere motivato da un interesse personale all'accesso
(es. identificazione di autori di illeciti subiti) e sarà soddisfatto garantendo la tutela
della privacy degli altri soggetti eventualmente presenti nelle immagini.

7. RECLAMO
Garante per la protezione dei dati personali — www.garanteprivacy.it
"""

    return {
        "informativa_breve": informativa_breve.strip(),
        "informativa_estesa": informativa_estesa.strip(),
        "adempimenti_preventivi": adempimenti_preventivi,
        "riferimento_normativo": (
            "Art. 13 Reg. UE 2016/679 (GDPR); Linee Guida EDPB 3/2019 sul trattamento "
            "di dati personali tramite dispositivi video; Art. 4 L. 300/1970 (Statuto dei Lavoratori)"
        ),
    }


@mcp.tool(tags={"privacy"})
def genera_informativa_videosorveglianza(
    titolare: str,
    finalita: list[str],
    tempo_conservazione: str,
    aree_riprese: list[str],
) -> dict:
    """Genera l'informativa breve (cartello) ed estesa per sistemi di videosorveglianza.

    Usa questo tool quando: un'azienda, un esercizio commerciale o un ente installa telecamere
    di sicurezza e deve adempiere agli obblighi informativi GDPR e EDPB.
    L'informativa breve è il testo del cartello da esporre all'ingresso dell'area ripresa
    (formato EDPB "layered approach"). L'informativa estesa è il documento completo.
    Chaining: → verifica_necessita_dpia() se monitoraggio sistematico su larga scala
              → genera_dpa() per il fornitore del servizio di videosorveglianza

    Args:
        titolare: Ragione sociale e recapiti del titolare che installa le telecamere
        finalita: Finalità del sistema (es. ['sicurezza persone', 'tutela patrimonio aziendale'])
        tempo_conservazione: Durata massima conservazione immagini (es. '24 ore', '72 ore')
        aree_riprese: Aree in cui sono installate le telecamere (es. ['ingresso principale', 'magazzino'])
    """
    return _genera_informativa_videosorveglianza_impl(
        titolare=titolare,
        finalita=finalita,
        tempo_conservazione=tempo_conservazione,
        aree_riprese=aree_riprese,
    )


# ---------------------------------------------------------------------------
# Tool 5: genera_dpa
# ---------------------------------------------------------------------------

def _genera_dpa_impl(
    titolare: str,
    responsabile: str,
    oggetto: str,
    durata: str,
    categorie_interessati: list[str],
    categorie_dati: list[str],
    misure_sicurezza: list[str],
    sub_responsabili: list[str] | None = None,
) -> dict:
    sub_responsabili = sub_responsabili or []

    # Label each clause of art. 28(3) carries in the generated text: the checklist below is
    # derived from the text, so it can no longer report a clause the document does not contain.
    _marcatori_art28 = {
        "a_istruzioni_documentate": "[art. 28(3)(a)]",
        "b_riservatezza": "[art. 28(3)(b)]",
        "c_misure_sicurezza_art32": "[art. 28(3)(c)]",
        "d_sub_responsabili_condizioni": "[art. 28(3)(d)",
        "e_assistenza_diritti_interessati": "[art. 28(3)(e)]",
        "f_assistenza_sicurezza_breach_dpia": "[art. 28(3)(f)]",
        "g_cancellazione_restituzione_fine_servizio": "[art. 28(3)(g)]",
        "h_audit_ispezioni": "[art. 28(3)(h)]",
    }
    _marcatore_istruzione_illecita = "[art. 28(3), secondo comma]"

    categorie_int_text = "\n".join(f"  - {c}" for c in categorie_interessati)
    categorie_dati_text = "\n".join(f"  - {d}" for d in categorie_dati)
    misure_text = "\n".join(f"  - {m}" for m in misure_sicurezza)

    sub_section = ""
    if sub_responsabili:
        sub_list = "\n".join(f"  - {s}" for s in sub_responsabili)
        sub_section = f"""
4.4 Sub-responsabili autorizzati [art. 28(3)(d), art. 28(2) e (4)]
Il Titolare autorizza il Responsabile ad avvalersi dei seguenti sub-responsabili:
{sub_list}
Il Responsabile informerà previamente il Titolare di qualsiasi modifica prevista riguardante
l'aggiunta o la sostituzione di altri responsabili del trattamento, dando al Titolare la
possibilità di opporsi a tali modifiche. Sui sub-responsabili sono imposti, mediante contratto
o altro atto giuridico, gli stessi obblighi in materia di protezione dei dati contenuti nel
presente accordo, prevedendo in particolare garanzie sufficienti per mettere in atto misure
tecniche e organizzative adeguate. Qualora il sub-responsabile ometta di adempiere ai propri
obblighi in materia di protezione dei dati, il Responsabile rimane pienamente responsabile e
conserva nei confronti del Titolare l'intera responsabilità dell'adempimento degli obblighi
del sub-responsabile.
"""
    else:
        sub_section = """
4.4 Sub-responsabili [art. 28(3)(d), art. 28(2) e (4)]
Il Responsabile non è autorizzato ad avvalersi di altri responsabili del trattamento
(sub-responsabili) senza la previa autorizzazione scritta specifica o generale del Titolare.
Nel caso di autorizzazione scritta generale, il Responsabile informa il Titolare di eventuali
modifiche previste riguardanti l'aggiunta o la sostituzione di altri responsabili del trattamento,
dando al Titolare l'opportunità di opporsi a tali modifiche. Ai sub-responsabili così autorizzati
sono imposti, mediante contratto o altro atto giuridico, gli stessi obblighi in materia di
protezione dei dati contenuti nel presente accordo, prevedendo in particolare garanzie sufficienti
per mettere in atto misure tecniche e organizzative adeguate; il Responsabile rimane pienamente
responsabile e conserva nei confronti del Titolare l'intera responsabilità dell'adempimento degli
obblighi del sub-responsabile.
"""

    testo = f"""ACCORDO SUL TRATTAMENTO DEI DATI PERSONALI
Data Processing Agreement (DPA)
ai sensi dell'art. 28 Reg. UE 2016/679 (GDPR)

Tra:
TITOLARE DEL TRATTAMENTO: {titolare}
(di seguito "Titolare")

e

RESPONSABILE DEL TRATTAMENTO: {responsabile}
(di seguito "Responsabile")

PREMESSE
Il Titolare si avvale del Responsabile per la fornitura di servizi descritti all'art. 1.
Il Responsabile tratterà dati personali per conto del Titolare nell'ambito di tali servizi.
Le parti, riconoscendo gli obblighi derivanti dall'art. 28 GDPR, stipulano il presente accordo.

ART. 1 — OGGETTO E DURATA DEL TRATTAMENTO
1.1 Il Responsabile fornisce al Titolare i seguenti servizi:
    {oggetto}

1.2 Nell'ambito di detti servizi, il Responsabile tratterà dati personali per conto del Titolare.

1.3 Durata del trattamento: {durata}. Il presente accordo cessa automaticamente al termine
    del contratto di servizio e produce effetti, per quanto riguarda la restituzione/cancellazione
    dei dati, anche dopo tale cessazione.

ART. 2 — CATEGORIE DI INTERESSATI E DATI TRATTATI
2.1 Categorie di interessati:
{categorie_int_text}

2.2 Categorie di dati personali trattati:
{categorie_dati_text}

ART. 3 — NATURA E FINALITÀ DEL TRATTAMENTO
Il Responsabile tratta i dati personali esclusivamente per le finalità necessarie
all'esecuzione del contratto di servizio e secondo le istruzioni documentate del Titolare.
Il Responsabile non tratta i dati per finalità proprie o diverse da quelle contrattualmente
definite senza previa istruzione documentata del Titolare.

ART. 4 — OBBLIGHI DEL RESPONSABILE (art. 28(3) GDPR)

4.1 Istruzioni documentate [art. 28(3)(a)]
Il Responsabile tratta i dati personali soltanto su istruzione documentata del Titolare,
anche per quanto riguarda i trasferimenti di dati personali verso un paese terzo o
un'organizzazione internazionale, a meno che non vi sia tenuto dal diritto dell'Unione
o dello Stato membro cui è soggetto; in tal caso il Responsabile informa il Titolare
prima del trattamento, salvo che il diritto vieti tale informazione per motivi di
rilevante interesse pubblico.

4.2 Riservatezza [art. 28(3)(b)]
Il Responsabile si impegna a garantire che le persone autorizzate al trattamento si
siano impegnate alla riservatezza o abbiano un obbligo legale di riservatezza.

4.3 Misure di sicurezza [art. 28(3)(c)]
Il Responsabile adotta tutte le misure di sicurezza richieste dall'art. 32 GDPR.
Le misure tecniche e organizzative adottate includono:
{misure_text}
{sub_section}
4.5 Assistenza nell'esercizio dei diritti degli interessati [art. 28(3)(e)]
Il Responsabile assiste il Titolare, con misure tecniche e organizzative adeguate,
nel soddisfare l'obbligo di dare seguito alle richieste per l'esercizio dei diritti
dell'interessato (artt. 15-22 GDPR) entro i termini previsti dall'art. 12 GDPR.

4.6 Assistenza in materia di sicurezza, violazione e DPIA [art. 28(3)(f)]
Il Responsabile assiste il Titolare nel garantire il rispetto degli obblighi di cui
agli artt. 32-36 GDPR, tenendo conto della natura del trattamento e delle informazioni
a sua disposizione. In particolare:
  - notifica al Titolare, senza ingiustificato ritardo e comunque entro 24 ore dalla scoperta,
    qualsiasi violazione dei dati personali (data breach)
  - fornisce al Titolare le informazioni necessarie per la valutazione d'impatto (DPIA)

4.7 Cancellazione o restituzione dei dati alla cessazione [art. 28(3)(g)]
Su scelta del Titolare, il Responsabile cancella o restituisce al Titolare tutti i dati
personali dopo la fine della prestazione dei servizi relativi al trattamento e cancella
le copie esistenti, salvo che il diritto dell'Unione o degli Stati membri preveda la
conservazione dei dati.

4.8 Diritto di audit e ispezioni [art. 28(3)(h)]
Il Responsabile mette a disposizione del Titolare tutte le informazioni necessarie per
dimostrare il rispetto degli obblighi di cui al presente articolo e consente e contribuisce
alle attività di revisione, compresi le ispezioni, realizzate dal Titolare o da un altro
soggetto da questi incaricato.

4.9 Istruzioni in violazione della normativa [art. 28(3), secondo comma]
Con riguardo al punto 4.8, il Responsabile informa immediatamente il Titolare qualora, a suo
parere, un'istruzione violi il Regolamento o altre disposizioni, nazionali o dell'Unione,
relative alla protezione dei dati.

ART. 5 — OBBLIGHI DEL TITOLARE
Il Titolare si impegna a:
  - fornire istruzioni chiare, documentate e lecite per il trattamento
  - informare il Responsabile di eventuali modifiche alle istruzioni
  - garantire che il trattamento sia fondato su un'adeguata base giuridica
  - mantenere aggiornato il registro dei trattamenti

ART. 6 — RESPONSABILITÀ
Il Responsabile è responsabile dell'adempimento degli obblighi ex art. 28 GDPR.
Qualora il Responsabile violi il GDPR determinando le finalità e i mezzi del trattamento,
è considerato Titolare del trattamento ai sensi dell'art. 28(10) GDPR (nozione di cui all'art. 4(7)),
fatti salvi gli artt. 82, 83 e 84 GDPR, con le relative responsabilità.

ART. 7 — LEGGE APPLICABILE E FORO COMPETENTE
Il presente accordo è regolato dal Reg. UE 2016/679 (GDPR) e dalla normativa italiana
di attuazione (D.Lgs. 196/2003 come mod. D.Lgs. 101/2018).

Luogo e data: _______________

Per il Titolare: ___________________________
Per il Responsabile: _______________________
"""

    clausole_obbligatorie_art28 = {k: m in testo for k, m in _marcatori_art28.items()}
    avviso_istruzione_illecita = _marcatore_istruzione_illecita in testo

    return {
        "testo": testo.strip(),
        "clausole_obbligatorie_art28": clausole_obbligatorie_art28,
        # Art. 28(3), second sub-paragraph (immediate notice of an unlawful instruction)
        "avviso_istruzione_illecita_art28_3": avviso_istruzione_illecita,
        "tutte_clausole_presenti": all(clausole_obbligatorie_art28.values()) and avviso_istruzione_illecita,
        "riferimento_normativo": "Art. 28 Reg. UE 2016/679 (GDPR), parr. 2, 3, 4 e 10",
    }


@mcp.tool(tags={"privacy"})
def genera_dpa(
    titolare: str,
    responsabile: str,
    oggetto: str,
    durata: str,
    categorie_interessati: list[str],
    categorie_dati: list[str],
    misure_sicurezza: list[str],
    sub_responsabili: list[str] | None = None,
) -> dict:
    """Genera un Data Processing Agreement (DPA) completo ai sensi dell'art. 28 GDPR.

    Usa questo tool quando: un'azienda si avvale di un fornitore esterno che tratta dati
    personali per suo conto (es. provider cloud, software HR, società di marketing, commercialista).
    L'art. 28 GDPR impone la stipula obbligatoria di un accordo scritto con il responsabile
    del trattamento. Senza DPA, il titolare risponde della violazione degli obblighi.
    Chaining: → genera_registro_trattamenti() per registrare il trattamento
              → verifica_necessita_dpia() se il trattamento presenta rischi elevati
    Vigenza: art. 28, parr. 2, 3, 4 e 10 Reg. UE 2016/679, testo vigente al 2026-09-29
    (le clausole 4.1-4.8 riproducono le lett. a-h del par. 3, la 4.9 il secondo comma).
    Precisione: INDICATIVO (modello di clausole fondato sull'art. 28; le condizioni
    economiche, i tempi di notifica del breach e il foro restano scelte contrattuali
    da adattare al caso; non sostituisce la revisione di un legale).

    Args:
        titolare: Ragione sociale e sede del titolare del trattamento
        responsabile: Ragione sociale e sede del responsabile del trattamento (fornitore)
        oggetto: Descrizione dei servizi forniti (es. 'hosting e gestione CRM aziendale')
        durata: Durata del trattamento (es. 'per tutta la durata del contratto di servizio')
        categorie_interessati: Chi sono gli interessati (es. ['clienti', 'lead', 'dipendenti'])
        categorie_dati: Dati trattati (es. ['dati anagrafici', 'dati di contatto', 'dati comportamentali'])
        misure_sicurezza: Misure tecniche e organizzative adottate dal responsabile
        sub_responsabili: Eventuali sub-responsabili autorizzati (lista nomi, lasciare vuota se assenti)
    """
    return _genera_dpa_impl(
        titolare=titolare,
        responsabile=responsabile,
        oggetto=oggetto,
        durata=durata,
        categorie_interessati=categorie_interessati,
        categorie_dati=categorie_dati,
        misure_sicurezza=misure_sicurezza,
        sub_responsabili=sub_responsabili,
    )


# ---------------------------------------------------------------------------
# Tool 6: genera_registro_trattamenti
# ---------------------------------------------------------------------------

def _genera_registro_trattamenti_impl(
    titolare: str,
    trattamento: str,
    finalita: str,
    base_giuridica: str,
    categorie_interessati: list[str],
    categorie_dati: list[str],
    destinatari: list[str],
    termine_cancellazione: str,
    misure_sicurezza: list[str],
) -> dict:
    scheda = {
        "titolare": titolare,
        "nome_trattamento": trattamento,
        "finalita": finalita,
        "base_giuridica_art6": base_giuridica,
        "categorie_interessati": categorie_interessati,
        "categorie_dati_personali": categorie_dati,
        "dati_categorie_particolari_art9": False,
        "dati_giudiziari_art10": False,
        "destinatari_terzi": destinatari,
        "trasferimenti_paesi_terzi": "Nessuno (da verificare)",
        "termine_cancellazione": termine_cancellazione,
        "misure_sicurezza_art32": misure_sicurezza,
    }

    cat_int_text = "\n".join(f"  - {c}" for c in categorie_interessati)
    cat_dati_text = "\n".join(f"  - {d}" for d in categorie_dati)
    destinatari_text = "\n".join(f"  - {d}" for d in destinatari)
    misure_text = "\n".join(f"  - {m}" for m in misure_sicurezza)

    testo = f"""REGISTRO DEI TRATTAMENTI — SCHEDA TRATTAMENTO
ai sensi dell'art. 30 Reg. UE 2016/679 (GDPR)

Titolare del trattamento: {titolare}
Data ultima revisione: _______________

┌─────────────────────────────────────────────────────────────────────┐
│ SCHEDA TRATTAMENTO: {trattamento}
└─────────────────────────────────────────────────────────────────────┘

1. TITOLARE DEL TRATTAMENTO (art. 30(1)(a))
   {titolare}

2. FINALITÀ DEL TRATTAMENTO (art. 30(1)(b))
   {finalita}

3. BASE GIURIDICA (art. 30(1)(b) — da indicare per documentazione interna)
   {base_giuridica}

4. CATEGORIE DI INTERESSATI (art. 30(1)(c))
{cat_int_text}

5. CATEGORIE DI DATI PERSONALI (art. 30(1)(c))
{cat_dati_text}
   Dati particolari (art. 9): No — da aggiornare se presenti
   Dati giudiziari (art. 10): No — da aggiornare se presenti

6. DESTINATARI O CATEGORIE DI DESTINATARI (art. 30(1)(d))
{destinatari_text}

7. TRASFERIMENTI VERSO PAESI TERZI (art. 30(1)(e))
   Nessun trasferimento verso paesi terzi o organizzazioni internazionali
   (verificare e aggiornare se presenti trasferimenti extra-UE)

8. TERMINE DI CANCELLAZIONE (art. 30(1)(f))
   {termine_cancellazione}

9. MISURE DI SICUREZZA (art. 30(1)(g))
{misure_text}

Note aggiuntive: _______________________________________________
Data aggiornamento: _______________   A cura di: ________________
"""

    return {
        "scheda": scheda,
        "testo": testo.strip(),
        "riferimento_normativo": "Art. 30 Reg. UE 2016/679 (GDPR)",
    }


@mcp.tool(tags={"privacy"})
def genera_registro_trattamenti(
    titolare: str,
    trattamento: str,
    finalita: str,
    base_giuridica: str,
    categorie_interessati: list[str],
    categorie_dati: list[str],
    destinatari: list[str],
    termine_cancellazione: str,
    misure_sicurezza: list[str],
) -> dict:
    """Genera la scheda di un trattamento per il Registro dei Trattamenti (art. 30 GDPR).

    Usa questo tool quando: devi creare o aggiornare il Registro dei Trattamenti, che è
    obbligatorio per titolari con più di 250 dipendenti e per chiunque tratti dati sensibili,
    dati in modo non occasionale o con rischio per gli interessati (art. 30(5) GDPR).
    In pratica, è raccomandato per tutte le organizzazioni come strumento di accountability.
    Chaining: → genera_dpa() per i responsabili del trattamento identificati come destinatari
              → verifica_necessita_dpia() per trattamenti ad alto rischio

    Args:
        titolare: Ragione sociale e sede del titolare del trattamento
        trattamento: Nome identificativo del trattamento (es. 'Gestione clienti CRM')
        finalita: Finalità del trattamento (es. 'gestione del rapporto commerciale con i clienti')
        base_giuridica: Base giuridica ex art. 6 GDPR (es. 'art. 6(1)(b) - esecuzione contratto')
        categorie_interessati: Chi sono gli interessati (es. ['clienti', 'prospect'])
        categorie_dati: Categorie di dati personali (es. ['dati anagrafici', 'dati di contatto'])
        destinatari: Destinatari interni e responsabili del trattamento (es. ['ufficio commerciale', 'CRM provider'])
        termine_cancellazione: Periodo o criterio di conservazione e cancellazione
        misure_sicurezza: Misure tecniche e organizzative adottate (es. ['cifratura', 'controllo accessi', 'backup'])
    """
    return _genera_registro_trattamenti_impl(
        titolare=titolare,
        trattamento=trattamento,
        finalita=finalita,
        base_giuridica=base_giuridica,
        categorie_interessati=categorie_interessati,
        categorie_dati=categorie_dati,
        destinatari=destinatari,
        termine_cancellazione=termine_cancellazione,
        misure_sicurezza=misure_sicurezza,
    )


# ---------------------------------------------------------------------------
# Tool 7: genera_dpia
# ---------------------------------------------------------------------------

_LIVELLO_MAP = {"bassa": 1, "media": 2, "alta": 3, "molto_alta": 4}
_LIVELLO_LABELS = {1: "Basso", 2: "Medio", 3: "Alto", 4: "Molto alto"}


def _calcola_livello_rischio(probabilita: str, gravita: str) -> dict:
    avvisi = []
    if probabilita.lower() not in _LIVELLO_MAP:
        avvisi.append(f"valore probabilità '{probabilita}' non riconosciuto, assunto 'media'")
    if gravita.lower() not in _LIVELLO_MAP:
        avvisi.append(f"valore gravità '{gravita}' non riconosciuto, assunto 'media'")
    p = _LIVELLO_MAP.get(probabilita.lower(), 2)
    g = _LIVELLO_MAP.get(gravita.lower(), 2)
    score = p * g
    if score <= 2:
        livello = "basso"
    elif score <= 4:
        livello = "medio"
    elif score <= 6:
        livello = "alto"
    else:
        livello = "molto_alto"
    return {"score": score, "livello": livello, "probabilita_num": p, "gravita_num": g, "avvisi": avvisi}


# Steps of the 4-level scale a measure removes, by declared efficacy. NOT set by the GDPR:
# art. 36(1) only makes the consultation depend on the risk that remains after the controller's
# measures. The tool's estimate is deliberately cautious (the best single measure per risk, no
# cumulation) and the controller must justify each declared efficacy in the DPIA.
_GRADINI_EFFICACIA = {"alta": 2, "media": 1, "bassa": 0}
_LIVELLI_ORDINE = ["basso", "medio", "alto", "molto_alto"]


def _norm_testo(valore) -> str:
    return " ".join(str(valore or "").lower().split())


def _misure_per_rischio(desc: str, misure: list[dict], n_rischi: int) -> list[dict]:
    """Measures whose 'rischio_mitigato' names this risk (equal or one contains the other).

    A measure with no 'rischio_mitigato' counts for the only risk of a single-risk DPIA."""
    d = _norm_testo(desc)
    trovate = []
    for m in misure:
        rm = _norm_testo(m.get("rischio_mitigato", ""))
        if (rm and d and (rm == d or rm in d or d in rm)) or (not rm and n_rischi == 1):
            trovate.append(m)
    return trovate


def _livello_residuo(livello: str, misure: list[dict]) -> tuple[str, list[str]]:
    """Level left after the best measure declared for the risk, with any warning."""
    avvisi: list[str] = []
    gradini = 0
    for m in misure:
        eff = _norm_testo(m.get("efficacia", ""))
        if eff not in _GRADINI_EFFICACIA:
            avvisi.append(
                f"efficacia '{m.get('efficacia', '')}' della misura '{m.get('misura', '')}' "
                "non riconosciuta (alta/media/bassa): la misura non riduce il rischio"
            )
            continue
        gradini = max(gradini, _GRADINI_EFFICACIA[eff])
    idx = max(0, _LIVELLI_ORDINE.index(livello) - gradini)
    return _LIVELLI_ORDINE[idx], avvisi


def _genera_dpia_impl(
    titolare: str,
    descrizione: str,
    finalita: str,
    necessita_proporzionalita: str,
    rischi: list[dict],
    misure_mitigazione: list[dict],
) -> dict:
    matrice_rischi = []
    misure_usate: set[int] = set()
    for r in rischi:
        analisi = _calcola_livello_rischio(r.get("probabilita", "media"), r.get("gravita", "media"))
        applicabili = _misure_per_rischio(r.get("desc", ""), misure_mitigazione, len(rischi))
        misure_usate.update(id(m) for m in applicabili)
        livello_res, avvisi_misure = _livello_residuo(analisi["livello"], applicabili)
        matrice_rischi.append({
            "descrizione": r.get("desc", ""),
            "probabilita": r.get("probabilita", "media"),
            "gravita": r.get("gravita", "media"),
            "score": analisi["score"],
            # Inherent level (before any measure); the level after the measures is below
            "livello_rischio": analisi["livello"],
            "livello_residuo": livello_res,
            "misure_applicate": [m.get("misura", "") for m in applicabili],
            "avvisi": analisi["avvisi"] + avvisi_misure,
        })

    avvisi_dpia = [
        f"la misura '{m.get('misura', '')}' (rischio mitigato: '{m.get('rischio_mitigato', '')}') "
        "non corrisponde a nessun rischio elencato: non è stata considerata nel rischio residuo"
        for m in misure_mitigazione if id(m) not in misure_usate
    ]

    # Residual risk = highest level left AFTER the measures declared for each risk.
    # Art. 36(1) GDPR: prior consultation when the DPIA shows a high risk that the controller's
    # measures do not attenuate, so it turns on the residual level, "alto" and "molto_alto" included.
    residui = [r["livello_residuo"] for r in matrice_rischi]
    consultazione = any(lv in ("alto", "molto_alto") for lv in residui)
    if not matrice_rischi:
        rischio_residuo = "non determinabile"
    elif "molto_alto" in residui:
        rischio_residuo = "molto_alto — consultazione preventiva obbligatoria (art. 36 GDPR)"
    elif "alto" in residui:
        rischio_residuo = "alto — rischio elevato residuo: consultazione preventiva obbligatoria (art. 36 GDPR)"
    elif "medio" in residui:
        rischio_residuo = "medio — accettabile con le misure di mitigazione adottate"
    else:
        rischio_residuo = "basso — rischio accettabile"
    ordine = {lv: i for i, lv in enumerate(_LIVELLI_ORDINE)}
    rischio_inerente = (
        max((r["livello_rischio"] for r in matrice_rischi), key=ordine.__getitem__)
        if matrice_rischi else "non determinabile"
    )

    rischi_text = ""
    for i, r in enumerate(matrice_rischi, 1):
        rischi_text += (
            f"  {i}. {r['descrizione']}\n"
            f"     Probabilità: {r['probabilita']} | Gravità: {r['gravita']} | "
            f"Livello: {r['livello_rischio'].upper()} (score: {r['score']})\n"
        )

    misure_text = ""
    for i, m in enumerate(misure_mitigazione, 1):
        misure_text += (
            f"  {i}. {m.get('misura', '')}\n"
            f"     Rischio mitigato: {m.get('rischio_mitigato', '')} | "
            f"Efficacia: {m.get('efficacia', '')}\n"
        )

    residuo_text = ""
    for i, r in enumerate(matrice_rischi, 1):
        residuo_text += (
            f"  {i}. {r['descrizione']}: inerente {r['livello_rischio'].upper()} → "
            f"residuo {r['livello_residuo'].upper()}\n"
        )
    for a in avvisi_dpia + [a for r in matrice_rischi for a in r["avvisi"]]:
        residuo_text += f"  Avviso: {a}\n"

    consultazione_note = ""
    if consultazione:
        livello_label = "molto alto" if "molto_alto" in residui else "alto"
        consultazione_note = f"""
CONSULTAZIONE PREVENTIVA OBBLIGATORIA (art. 36(1) GDPR)
Il rischio residuo, calcolato dopo le misure di mitigazione indicate, è {livello_label}: la DPIA
indica un rischio elevato che le misure adottate dal titolare non attenuano a sufficienza.
Prima di procedere con il trattamento il titolare consulta il Garante per la protezione dei
dati personali. Il Garante risponde entro 8 settimane (prorogabili di 6 settimane per casi
complessi) (art. 36(2) GDPR).
"""

    testo = f"""VALUTAZIONE D'IMPATTO SULLA PROTEZIONE DEI DATI (DPIA)
ai sensi dell'art. 35 Reg. UE 2016/679 (GDPR) — WP248 rev.01

Titolare del trattamento: {titolare}
Data DPIA: _______________  Revisione prevista: _______________
Redatta da: _______________

1. DESCRIZIONE SISTEMATICA DEL TRATTAMENTO
{descrizione}

2. FINALITÀ DEL TRATTAMENTO
{finalita}

3. VALUTAZIONE DELLA NECESSITÀ E PROPORZIONALITÀ
{necessita_proporzionalita}

Principi GDPR verificati:
  □ Limitazione delle finalità (art. 5(1)(b))
  □ Minimizzazione dei dati (art. 5(1)(c))
  □ Limitazione della conservazione (art. 5(1)(e))
  □ Privacy by design e by default (art. 25)
  □ Base giuridica adeguata (art. 6)
  □ Trasparenza verso gli interessati (art. 13/14)
  □ Possibilità di esercizio dei diritti (artt. 15-22)

4. ANALISI DEI RISCHI PER I DIRITTI E LE LIBERTÀ DEGLI INTERESSATI
Scala: Probabilità e Gravità: bassa=1, media=2, alta=3, molto_alta=4
Score = Probabilità × Gravità: ≤2=basso, ≤4=medio, ≤6=alto, >6=molto_alto

{rischi_text}

5. MISURE DI MITIGAZIONE ADOTTATE
{misure_text}

6. RISCHIO RESIDUO (dopo le misure di mitigazione)
Rischio inerente massimo (prima delle misure): {rischio_inerente}
{residuo_text}Stima del tool: ogni misura riduce il livello di 2 gradini se l'efficacia dichiarata è alta,
di 1 se media, di 0 se bassa (si considera la misura migliore per ciascun rischio, senza cumulo).
La riduzione è una convenzione del tool, non un valore fissato dal GDPR: il titolare la motiva.
Rischio residuo complessivo: {rischio_residuo}
{consultazione_note}
7. CONSULTAZIONE DPO
□ Il DPO è stato consultato nella redazione della presente DPIA
□ Il parere del DPO è allegato alla presente valutazione

8. APPROVAZIONE E MONITORAGGIO
Il trattamento è approvato: □ Sì □ No □ Condizionato
La DPIA sarà riesaminata: □ Ogni 2 anni □ In caso di variazioni significative

Firma del Titolare / DPO: _______________________  Data: _______________

Riferimento normativo: Art. 35 Reg. UE 2016/679 (GDPR); WP248 rev.01 (Linee Guida DPIA)
"""

    return {
        "testo": testo.strip(),
        "matrice_rischi": matrice_rischi,
        "rischio_inerente": rischio_inerente,
        "rischio_residuo": rischio_residuo,
        "consultazione_preventiva_necessaria": consultazione,
        "avvisi": avvisi_dpia,
        "riferimento_normativo": "Artt. 35 e 36 Reg. UE 2016/679 (GDPR); WP248 rev.01 — Linee Guida DPIA EDPB",
    }


@mcp.tool(tags={"privacy"})
def genera_dpia(
    titolare: str,
    descrizione: str,
    finalita: str,
    necessita_proporzionalita: str,
    rischi: list[dict],
    misure_mitigazione: list[dict],
) -> dict:
    """Genera una Valutazione d'Impatto sulla Protezione dei Dati (DPIA) ai sensi dell'art. 35 GDPR.

    Usa questo tool quando: verifica_necessita_dpia() ha confermato che la DPIA è obbligatoria,
    oppure quando il titolare decide di effettuarla volontariamente per un trattamento ad alto rischio.
    La DPIA è obbligatoria per trattamenti che soddisfano ≥2 criteri WP248 (es. profilazione larga
    scala, videosorveglianza sistematica, dati biometrici, scoring automatizzato).
    Chaining: → verifica_necessita_dpia() prima, per verificare l'obbligo
    Vigenza: art. 35, par. 7 (lett. a-d) e par. 2, e art. 36, parr. 1-2 Reg. UE 2016/679, testo
    vigente al 2026-09-29; WP248 rev.01 (EDPB). Il rischio residuo è calcolato dopo le misure
    indicate e la consultazione preventiva dell'art. 36(1) scatta se resta 'alto' o 'molto_alto'.
    Precisione: STIMATO (scala probabilità x gravità a 4 livelli e riduzione per efficacia
    delle misure, alta -2 gradini, media -1, bassa 0, sono convenzioni del tool, non della
    norma: il titolare deve motivare la valutazione; struttura e termini 8+6 settimane
    dell'art. 36(2) sono quelli del regolamento).

    Args:
        titolare: Ragione sociale del titolare del trattamento
        descrizione: Descrizione sistematica del trattamento (natura, ambito, contesto, finalità)
        finalita: Finalità specifiche del trattamento
        necessita_proporzionalita: Valutazione della necessità e proporzionalità del trattamento
        rischi: Lista di rischi, ciascuno con campi: 'desc' (str), 'probabilita' (bassa/media/alta/molto_alta), 'gravita' (bassa/media/alta/molto_alta)
        misure_mitigazione: Lista di misure, ciascuna con campi: 'misura' (str), 'rischio_mitigato' (str, deve coincidere con la 'desc' di un rischio), 'efficacia' (alta/media/bassa)
    """
    return _genera_dpia_impl(
        titolare=titolare,
        descrizione=descrizione,
        finalita=finalita,
        necessita_proporzionalita=necessita_proporzionalita,
        rischi=rischi,
        misure_mitigazione=misure_mitigazione,
    )


# ---------------------------------------------------------------------------
# Tool 8: analisi_base_giuridica
# ---------------------------------------------------------------------------

_CONTESTI_MAP = {
    "B2C": ["B2C_marketing", "B2C_ecommerce"],
    "B2B": ["B2B_gestione_clienti"],
    "dipendenti": ["dipendenti_gestione", "dipendenti_videosorveglianza"],
    "pubblica_amministrazione": ["pubblica_amministrazione"],
    "sanita": ["sanita"],
    "profilazione": ["profilazione_online"],
}


def _analisi_base_giuridica_impl(
    tipo_trattamento: str,
    contesto: str,
    finalita: str,
    dati_particolari: bool = False,
) -> dict:
    basi_art6 = _BASI["basi_art6"]
    matrice = _BASI["matrice_contesto_base"]

    contesti_validi = ["B2C", "B2B", "dipendenti", "pubblica_amministrazione", "sanita", "profilazione"]
    if contesto not in contesti_validi:
        return {"errore": f"contesto deve essere uno tra: {', '.join(contesti_validi)}"}

    chiavi_contesto = _CONTESTI_MAP.get(contesto, [])
    contesto_principale = chiavi_contesto[0] if chiavi_contesto else None

    basi_giuridiche_applicabili = []

    if contesto_principale and contesto_principale in matrice:
        info_matrice = matrice[contesto_principale]
        base_chiave = info_matrice["base_consigliata"]
        if base_chiave in basi_art6:
            b = basi_art6[base_chiave]
            basi_giuridiche_applicabili.append({
                "base": base_chiave,
                "articolo": b["articolo"],
                "descrizione": b["descrizione"],
                "pro": b["pro"],
                "contro": b["contro"],
                "consigliata": True,
                "nota_contesto": info_matrice.get("nota", ""),
            })
        for alt in info_matrice.get("alternative", []):
            if alt in basi_art6:
                b = basi_art6[alt]
                basi_giuridiche_applicabili.append({
                    "base": alt,
                    "articolo": b["articolo"],
                    "descrizione": b["descrizione"],
                    "pro": b["pro"],
                    "contro": b["contro"],
                    "consigliata": False,
                    "nota_contesto": f"Alternativa per {tipo_trattamento}",
                })

    if not basi_giuridiche_applicabili:
        for nome, b in basi_art6.items():
            if tipo_trattamento.lower() in " ".join(b.get("contesti_tipici", [])).lower():
                basi_giuridiche_applicabili.append({
                    "base": nome,
                    "articolo": b["articolo"],
                    "descrizione": b["descrizione"],
                    "pro": b["pro"],
                    "contro": b["contro"],
                    "consigliata": nome == list(basi_art6.keys())[0],
                    "nota_contesto": "",
                })

    base_consigliata = basi_giuridiche_applicabili[0]["base"] if basi_giuridiche_applicabili else "da valutare"
    motivazione_base = basi_giuridiche_applicabili[0].get("nota_contesto", "") if basi_giuridiche_applicabili else ""

    note_art9 = ""
    condizioni_art9 = []
    if dati_particolari:
        premessa = _BASI["condizioni_art9"]["premessa"]
        eccezioni = _BASI["condizioni_art9"]["eccezioni"]
        condizioni_art9 = [
            f"Art. 9(2)({v['lettera']}) — {v['descrizione']}"
            for v in eccezioni.values()
        ]
        note_art9 = (
            f"DATI PARTICOLARI (art. 9 GDPR): {premessa}. "
            f"Oltre alla base ex art. 6, occorre individuare una condizione ex art. 9(2). "
            f"Le condizioni più frequenti per il contesto '{contesto}': "
            + "; ".join(condizioni_art9[:3])
        )

    return {
        "tipo_trattamento": tipo_trattamento,
        "contesto": contesto,
        "finalita": finalita,
        "dati_particolari": dati_particolari,
        "basi_giuridiche_applicabili": basi_giuridiche_applicabili,
        "base_consigliata": base_consigliata,
        "motivazione": motivazione_base,
        "note_dati_particolari_art9": note_art9,
        "condizioni_art9_disponibili": condizioni_art9 if dati_particolari else [],
        "riferimento_normativo": (
            "Art. 6 Reg. UE 2016/679 (GDPR) — Basi giuridiche per il trattamento"
            + ("; Art. 9 GDPR — Categorie particolari di dati" if dati_particolari else "")
        ),
    }


@mcp.tool(tags={"privacy"})
@sourced("gdpr_basi_giuridiche")
def analisi_base_giuridica(
    tipo_trattamento: str,
    contesto: str,
    finalita: str,
    dati_particolari: bool = False,
) -> dict:
    """Analizza e consiglia la base giuridica appropriata per un trattamento dati (art. 6 GDPR).

    Usa questo tool quando: devi scegliere la base giuridica corretta per un trattamento
    o verificare se quella in uso sia adeguata. Errori nella scelta della base giuridica
    sono tra le violazioni più sanzionate dal Garante.
    Se i dati trattati includono categorie particolari (salute, etnia, religione, biometria,
    orientamento sessuale) impostare dati_particolari=True per avere anche l'analisi art. 9.
    Chaining: → genera_informativa_privacy() con la base giuridica identificata
              → verifica_necessita_dpia() per trattamenti con consenso o legittimo interesse su larga scala
    Precisione: INDICATIVO (catalogo interno delle basi giuridiche ex art. 6; la
    qualificazione del caso concreto resta una valutazione del titolare).

    Args:
        tipo_trattamento: Descrizione del trattamento (es. 'invio newsletter', 'gestione ordini e-commerce')
        contesto: Contesto organizzativo: 'B2C', 'B2B', 'dipendenti', 'pubblica_amministrazione', 'sanita', 'profilazione'
        finalita: Finalità specifica del trattamento (es. 'marketing diretto via email a clienti esistenti')
        dati_particolari: True se il trattamento include dati ex art. 9 GDPR (salute, biometria, etnia, ecc.)
    """
    return _analisi_base_giuridica_impl(
        tipo_trattamento=tipo_trattamento,
        contesto=contesto,
        finalita=finalita,
        dati_particolari=dati_particolari,
    )


# ---------------------------------------------------------------------------
# Tool 9: verifica_necessita_dpia
# ---------------------------------------------------------------------------

#: Short labels of the items of the Garante's list (Allegato 1 to provv. n. 467/2018) the tool can
#: reach from its parameters; the literal text of the twelve items is in `lista_garante_italiano`.
_ETICHETTE_ALLEGATO_1 = {
    1: "Trattamenti valutativi o di scoring su larga scala, profilazione, attività predittive",
    2: "Trattamenti automatizzati con effetti giuridici o effetti analoghi significativi",
    3: "Utilizzo sistematico di dati per l'osservazione, il monitoraggio o il controllo degli interessati",
    5: "Trattamenti nel rapporto di lavoro con possibilità di controllo a distanza dei dipendenti",
    6: "Trattamenti non occasionali di dati di soggetti vulnerabili",
    7: "Trattamenti con tecnologie innovative insieme ad almeno un altro criterio WP248",
    9: "Trattamenti mediante interconnessione, combinazione o raffronto di informazioni",
    10: "Dati art. 9 o art. 10 interconnessi con altri dati raccolti per finalità diverse",
    11: "Trattamenti sistematici di dati biometrici",
    12: "Trattamenti sistematici di dati genetici",
}


def _verifica_necessita_dpia_impl(
    tipo_trattamento: str,
    profilazione: bool = False,
    dati_sensibili: bool = False,
    monitoraggio_sistematico: bool = False,
    larga_scala: bool = False,
    soggetti_vulnerabili: bool = False,
    nuove_tecnologie: bool = False,
    valutazione_scoring: bool = False,
    incrocio_dataset: bool = False,
    trasferimento_extra_ue: bool = False,
    impedimento_diritto: bool = False,
    dati_biometrici: bool = False,
    dati_genetici: bool = False,
    rapporto_di_lavoro: bool = False,
) -> dict:
    criteri_wp248 = _DPIA["criteri_wp248"]
    soglia = _DPIA["soglia_criteri"]

    # Biometric data (for unique identification) and genetic data are art. 9(1) data: they satisfy
    # WP248 criterion 4 like `dati_sensibili`.
    dati_art9 = dati_sensibili or dati_biometrici or dati_genetici

    param_map = {
        "profilazione": profilazione,
        "decisione_automatizzata": valutazione_scoring,
        "monitoraggio_sistematico": monitoraggio_sistematico,
        "dati_sensibili": dati_art9,
        "larga_scala": larga_scala,
        "incrocio_dataset": incrocio_dataset,
        "soggetti_vulnerabili": soggetti_vulnerabili,
        "nuove_tecnologie": nuove_tecnologie,
        "impedimento_diritto": impedimento_diritto,
    }

    criteri_soddisfatti = []
    for criterio in criteri_wp248:
        param = criterio["parametro"]
        if param in param_map and param_map[param]:
            criteri_soddisfatti.append(f"Criterio {criterio['id']}: {criterio['criterio']}")

    # The nine WP248 rev.01 criteria restated by the Garante (provv. 467/2018) are the only ones
    # counted: a transfer outside the EU is not among them.
    n_criteri = len(criteri_soddisfatti)
    soglia_raggiunta = n_criteri >= soglia

    # Art. 35(3) GDPR: cases in which the assessment is required whatever the criteria count.
    art35_3 = []
    if valutazione_scoring:
        art35_3.append(
            "Art. 35(3)(a): valutazione sistematica e globale basata su trattamento automatizzato, "
            "compresa la profilazione, su cui si fondano decisioni con effetti giuridici o analoghi"
        )
    if dati_art9 and larga_scala:
        art35_3.append(
            "Art. 35(3)(b): trattamento su larga scala di categorie particolari di dati (art. 9) "
            "o di dati relativi a condanne penali e reati (art. 10)"
        )
    if monitoraggio_sistematico and larga_scala:
        art35_3.append(
            "Art. 35(3)(c): sorveglianza sistematica su larga scala di una zona accessibile al "
            "pubblico (se il monitoraggio riguarda una tale zona)"
        )

    # Items of the Garante's list (art. 35(4); Allegato 1 to provv. 467/2018) reached by the
    # parameters. Items 6, 11 and 12 read "non occasionali"/"sistematici" as large scale (the
    # Garante's interpretive clarification); item 7 needs another WP248 criterion besides the
    # innovative technology itself.
    voci_obbligatorie: list[int] = []
    voci_da_verificare: list[str] = []

    if profilazione and larga_scala:
        voci_obbligatorie.append(1)
    elif profilazione:
        voci_da_verificare.append(
            f"Voce 1: {_ETICHETTE_ALLEGATO_1[1]} (la voce richiama la profilazione insieme al "
            "requisito di larga scala: se la profilazione rientra nella voce, la DPIA è obbligatoria)"
        )
    if valutazione_scoring:
        voci_obbligatorie.append(2)
    if monitoraggio_sistematico:
        voci_obbligatorie.append(3)
    if rapporto_di_lavoro:
        voci_obbligatorie.append(5)
    if soggetti_vulnerabili and larga_scala:
        voci_obbligatorie.append(6)
    elif soggetti_vulnerabili:
        voci_da_verificare.append(
            f"Voce 6: {_ETICHETTE_ALLEGATO_1[6]} (si applica solo se il trattamento è non "
            "occasionale, cioè su larga scala)"
        )
    if nuove_tecnologie and n_criteri >= 2:
        voci_obbligatorie.append(7)
    elif nuove_tecnologie:
        voci_da_verificare.append(
            f"Voce 7: {_ETICHETTE_ALLEGATO_1[7]} (si applica solo se ricorre anche un altro criterio WP248)"
        )
    if incrocio_dataset:
        voci_obbligatorie.append(9)
    if dati_art9 and incrocio_dataset:
        voci_obbligatorie.append(10)
    if dati_biometrici and larga_scala:
        voci_obbligatorie.append(11)
    elif dati_biometrici:
        voci_da_verificare.append(
            f"Voce 11: {_ETICHETTE_ALLEGATO_1[11]} (si applica solo se il trattamento è sistematico, "
            "cioè su larga scala)"
        )
    if dati_genetici and larga_scala:
        voci_obbligatorie.append(12)
    elif dati_genetici:
        voci_da_verificare.append(
            f"Voce 12: {_ETICHETTE_ALLEGATO_1[12]} (si applica solo se il trattamento è sistematico, "
            "cioè su larga scala)"
        )

    lista_garante_match = [f"Voce {n}: {_ETICHETTE_ALLEGATO_1[n]}" for n in voci_obbligatorie]
    # Art. 35(3)(a) and (b) require the assessment by themselves; (c) is met through item 3 above.
    caso_art35_3 = any(c.startswith(("Art. 35(3)(a)", "Art. 35(3)(b)")) for c in art35_3)

    dpia_necessaria = soglia_raggiunta or caso_art35_3 or bool(voci_obbligatorie)

    fondamenti = []
    if soglia_raggiunta:
        fondamenti.append(f"il trattamento soddisfa {n_criteri} criteri WP248 (soglia: {soglia})")
    fondamenti.extend(c.split(":")[0] for c in art35_3 if c.startswith(("Art. 35(3)(a)", "Art. 35(3)(b)")))
    if voci_obbligatorie:
        fondamenti.append(
            "rientra nell'elenco del Garante ex art. 35(4) (voci "
            + ", ".join(str(n) for n in voci_obbligatorie)
            + ")"
        )

    if dpia_necessaria:
        motivazione = (
            f"La DPIA è OBBLIGATORIA: {'; '.join(fondamenti)}. È necessario effettuare la "
            f"valutazione d'impatto prima di avviare o continuare il trattamento (art. 35 GDPR)."
        )
    elif n_criteri == 1:
        motivazione = (
            f"La DPIA non è obbligatoria automaticamente ({n_criteri} criterio su {soglia} richiesti), "
            f"ma è fortemente consigliata dato il criterio presente. "
            f"Valutare se il trattamento è già nell'elenco del Garante."
        )
    else:
        motivazione = (
            f"La DPIA non appare obbligatoria ({n_criteri} criteri su {soglia} richiesti). "
            f"Tuttavia, è sempre consigliata come buona pratica di accountability (art. 5(2) GDPR) "
            f"per documentare la valutazione dei rischi."
        )

    avvertenze = []
    if trasferimento_extra_ue:
        avvertenze.append(
            "Il trasferimento verso paesi terzi non è tra i nove criteri WP248 rev.01 né tra le "
            "voci dell'elenco del Garante: non concorre alla soglia; resta un fattore di rischio da "
            "valutare nella DPIA (art. 35(7)(c); capo V GDPR)."
        )
    if soggetti_vulnerabili:
        avvertenze.append(
            "Voce 6 dell'elenco del Garante: minori, disabili, anziani, infermi di mente, pazienti, "
            "richiedenti asilo; i dipendenti non vi sono elencati (criterio 7 WP248; per il controllo "
            "a distanza vale la voce 5, parametro rapporto_di_lavoro)."
        )

    return {
        "tipo_trattamento": tipo_trattamento,
        "dpia_necessaria": dpia_necessaria,
        "criteri_soddisfatti": criteri_soddisfatti,
        "n_criteri": n_criteri,
        "soglia": soglia,
        "motivazione": motivazione,
        "art35_3": art35_3,
        "lista_garante_match": lista_garante_match,
        "lista_garante_da_verificare": voci_da_verificare,
        "avvertenze": avvertenze,
        "esenzioni_possibili": _DPIA["esenzioni_dpia"],
        "riferimento_normativo": (
            "Art. 35 Reg. UE 2016/679 (GDPR); WP248 rev.01 (Linee Guida DPIA); "
            "Provvedimento Garante n. 467 dell'11/10/2018 [doc. web 9058979] e Allegato 1 [doc. web 9059358]"
        ),
    }


@mcp.tool(tags={"privacy"})
@sourced("gdpr_dpia_criteri")
def verifica_necessita_dpia(
    tipo_trattamento: str,
    profilazione: bool = False,
    dati_sensibili: bool = False,
    monitoraggio_sistematico: bool = False,
    larga_scala: bool = False,
    soggetti_vulnerabili: bool = False,
    nuove_tecnologie: bool = False,
    valutazione_scoring: bool = False,
    incrocio_dataset: bool = False,
    trasferimento_extra_ue: bool = False,
    impedimento_diritto: bool = False,
    dati_biometrici: bool = False,
    dati_genetici: bool = False,
    rapporto_di_lavoro: bool = False,
) -> dict:
    """Verifica se un trattamento dati richiede obbligatoriamente la DPIA (art. 35 GDPR).

    Usa questo tool quando: stai progettando un nuovo trattamento o revisioni uno esistente
    e devi stabilire se la DPIA sia obbligatoria. La DPIA è obbligatoria in tre casi, indicati
    nella risposta: (1) almeno 2 dei 9 criteri WP248 rev.01 (soglia del provv. Garante n. 467
    dell'11/10/2018); (2) un caso dell'art. 35(3) GDPR: valutazione sistematica con decisioni
    automatizzate ad effetti giuridici (lett. a), categorie particolari o dati penali su larga
    scala (lett. b); (3) una voce dell'elenco del Garante ex art. 35(4) (Allegato 1 al provv.
    467/2018), che basta da sola (voci 2, 3, 5, 9, 10) o con la larga scala (1, 6, 11, 12) o con un
    altro criterio (7). "Larga scala" vale anche per i trattamenti "non occasionali" e "sistematici"
    delle voci 6, 11 e 12, come nel chiarimento del Garante. Il trasferimento extra UE non è un
    criterio WP248 e non concorre alla soglia. Le voci raggiunte solo in parte sono in
    `lista_garante_da_verificare`. Non copre le voci 4 e 8 dell'elenco (nessun parametro dedicato).
    Vigenza: art. 35 Reg. UE 2016/679; provv. Garante n. 467/2018 e Allegato 1, GU n. 269 del
    19/11/2018 (elenco letto il 29/09/2026).
    Precisione: INDICATIVO (criteri WP248 rev.01 e provvedimento Garante; il conteggio
    dei criteri non sostituisce la valutazione del titolare).
    Chaining: se dpia_necessaria=True → genera_dpia() per redigere la valutazione d'impatto

    Args:
        tipo_trattamento: Descrizione del trattamento (es. 'sistema biometrico di presenze')
        profilazione: True se include profilazione sistematica degli interessati
        dati_sensibili: True se tratta categorie particolari ex art. 9 o dati giudiziari ex art. 10
        monitoraggio_sistematico: True se prevede monitoraggio o sorveglianza sistematica
        larga_scala: True se tratta dati di un numero significativo di interessati
        soggetti_vulnerabili: True se gli interessati includono minori, dipendenti, pazienti, anziani (criterio 7 WP248; la voce 6 del Garante elenca minori, disabili, anziani, infermi di mente, pazienti, richiedenti asilo)
        nuove_tecnologie: True se utilizza tecnologie innovative (AI, biometria, IoT, riconoscimento facciale)
        valutazione_scoring: True se prevede valutazione automatizzata con effetti giuridici (art. 22)
        incrocio_dataset: True se combina dataset provenienti da fonti diverse o titolari diversi
        trasferimento_extra_ue: True se trasferisce dati verso paesi extra-UE senza adeguata protezione (non concorre alla soglia: non è un criterio WP248)
        impedimento_diritto: True se può impedire agli interessati di esercitare un diritto o accedere a un servizio
        dati_biometrici: True se tratta dati biometrici per identificare univocamente una persona (voce 11; conta anche come criterio 4)
        dati_genetici: True se tratta dati genetici (voce 12; conta anche come criterio 4)
        rapporto_di_lavoro: True se il trattamento avviene nel rapporto di lavoro con sistemi tecnologici (videosorveglianza, geolocalizzazione) da cui derivi la possibilità di controllo a distanza dei dipendenti (voce 5)
    """
    return _verifica_necessita_dpia_impl(
        tipo_trattamento=tipo_trattamento,
        profilazione=profilazione,
        dati_sensibili=dati_sensibili,
        monitoraggio_sistematico=monitoraggio_sistematico,
        larga_scala=larga_scala,
        soggetti_vulnerabili=soggetti_vulnerabili,
        nuove_tecnologie=nuove_tecnologie,
        valutazione_scoring=valutazione_scoring,
        incrocio_dataset=incrocio_dataset,
        trasferimento_extra_ue=trasferimento_extra_ue,
        impedimento_diritto=impedimento_diritto,
        dati_biometrici=dati_biometrici,
        dati_genetici=dati_genetici,
        rapporto_di_lavoro=rapporto_di_lavoro,
    )


# ---------------------------------------------------------------------------
# Tool 10: valutazione_data_breach
# ---------------------------------------------------------------------------

def _valutazione_data_breach_impl(
    tipo_violazione: str,
    categorie_dati: list[str],
    n_interessati: int,
    dati_particolari: bool = False,
    misure_protezione: list[str] | None = None,
    impatto: str = "medio",
) -> dict:
    misure_protezione = misure_protezione or []

    tipi_validi = ("confidenzialita", "integrita", "disponibilita")
    if tipo_violazione not in tipi_validi:
        return {"errore": f"tipo_violazione deve essere uno tra: {', '.join(tipi_validi)}"}

    impatti_validi = ("basso", "medio", "alto", "molto_alto")
    if impatto not in impatti_validi:
        return {"errore": f"impatto deve essere uno tra: {', '.join(impatti_validi)}"}

    if n_interessati < 0:
        return {"errore": "n_interessati deve essere >= 0"}

    # Mapping impatto a punteggio numerico
    impatto_score = {"basso": 1, "medio": 2, "alto": 3, "molto_alto": 4}[impatto]

    # Fattori che aumentano la gravità
    fattori_gravita = []
    if dati_particolari:
        fattori_gravita.append("Coinvolti dati particolari (art. 9) o giudiziari (art. 10)")
        impatto_score = min(impatto_score + 1, 4)
    if n_interessati > 100000:
        fattori_gravita.append(f"Numero molto elevato di interessati coinvolti ({n_interessati:,})")
        impatto_score = min(impatto_score + 1, 4)
    elif n_interessati > 10000:
        fattori_gravita.append(f"Numero elevato di interessati coinvolti ({n_interessati:,})")
    if tipo_violazione == "confidenzialita":
        fattori_gravita.append("Violazione di confidenzialità: dati acceduti da soggetti non autorizzati")
    if "dati finanziari" in " ".join(categorie_dati).lower() or "bancari" in " ".join(categorie_dati).lower():
        fattori_gravita.append("Coinvolti dati finanziari o bancari: rischio furto d'identità")

    # Verifica cifratura / misure di protezione. Solo la cifratura rende i dati incomprensibili
    # (art. 34(3)(a)); la pseudonimizzazione da sola no (EDPB 9/2022 par. 112).
    cifratura_presente = any(
        keyword in m.lower()
        for m in misure_protezione
        for keyword in ("cifratura", "crittografia", "encryption", "cifrat")
    )
    pseudonimizzazione_presente = any("pseudonimizz" in m.lower() for m in misure_protezione)
    # L'esenzione art. 34(3)(a) copre l'accesso non autorizzato a dati resi incomprensibili, cioe'
    # la riservatezza: la perdita o l'alterazione di dati cifrati resta un rischio (EDPB 9/2022
    # par. 76 e 79), per cui l'esenzione non opera per integrita' e disponibilita'.
    esenzione_art34_3_a = cifratura_presente and tipo_violazione == "confidenzialita"

    # Determinazione livello rischio
    livelli = {1: "improbabile", 2: "possibile", 3: "probabile", 4: "molto probabile"}
    livello_rischio = livelli.get(impatto_score, "possibile")

    # Art. 33: notifica al Garante se rischio non improbabile
    notifica_garante = livello_rischio != "improbabile"

    # Art. 34: comunicazione agli interessati
    # Art. 34(3)(a): non obbligatoria se i dati erano resi incomprensibili (cifratura) e la
    # violazione e' di riservatezza
    if esenzione_art34_3_a:
        comunicazione_interessati = False
        motivo_no_comunicazione = (
            "Violazione di riservatezza di dati cifrati: comunicazione agli interessati non "
            "obbligatoria se i dati sono incomprensibili, cioe' se la chiave non e' compromessa "
            "(art. 34(3)(a) GDPR; EDPB 9/2022 par. 76)"
        )
    elif livello_rischio in ("probabile", "molto probabile"):
        comunicazione_interessati = True
        motivo_no_comunicazione = ""
    else:
        comunicazione_interessati = livello_rischio == "possibile" and dati_particolari
        motivo_no_comunicazione = "" if comunicazione_interessati else "Rischio non elevato: comunicazione non obbligatoria, ma valutare opportunità"

    # Calcolo scadenza 72h (informativo — usa data_scoperta in notifica_data_breach)
    ore_rimanenti = "72 ore dalla scoperta dell'evento (art. 33(1) GDPR)"

    azioni_consigliate = [
        "Isolare immediatamente il sistema compromesso e bloccare ulteriori accessi non autorizzati",
        "Documentare immediatamente: natura dell'incidente, sistemi coinvolti, dati esposti, ora di scoperta",
        "Avviare indagine interna per determinare portata e cause della violazione",
    ]

    if notifica_garante:
        azioni_consigliate.append(
            "NOTIFICARE AL GARANTE entro 72 ore dalla scoperta (art. 33 GDPR) — "
            "usare il tool genera_notifica_data_breach() per redigere la notifica"
        )
    if comunicazione_interessati:
        azioni_consigliate.append(
            "COMUNICARE AGLI INTERESSATI senza ingiustificato ritardo (art. 34 GDPR): "
            "descrivere la violazione, il DPO, le probabili conseguenze e le misure adottate"
        )

    azioni_consigliate.extend([
        "Registrare la violazione nel registro interno dei data breach (art. 33(5) GDPR)",
        "Valutare misure correttive per prevenire violazioni future",
        "Valutare necessità di consulenza legale per responsabilità civili verso gli interessati",
    ])

    if esenzione_art34_3_a:
        azioni_consigliate.append(
            "La cifratura ha escluso la comunicazione agli interessati (art. 34(3)(a)): documentare "
            "che la chiave non e' compromessa e riesaminare il rischio se lo diventa (EDPB 9/2022 par. 78)"
        )
    elif cifratura_presente:
        azioni_consigliate.append(
            "La cifratura non esclude la comunicazione in caso di perdita o alterazione dei dati: "
            "verificare backup integro e tempo di ripristino, da cui dipende il rischio per gli "
            "interessati (EDPB 9/2022 par. 76 e 79; art. 32(1)(c) GDPR)"
        )
    if pseudonimizzazione_presente:
        azioni_consigliate.append(
            "La pseudonimizzazione da sola non rende i dati incomprensibili e non esclude la "
            "comunicazione agli interessati (EDPB 9/2022 par. 112): puo' ridurre la probabilita' "
            "di identificazione, da valutare nell'impatto"
        )

    return {
        "tipo_violazione": tipo_violazione,
        "n_interessati": n_interessati,
        "dati_particolari": dati_particolari,
        "misure_protezione_attive": misure_protezione,
        "cifratura_attiva": cifratura_presente,
        "esenzione_art34_3_a": esenzione_art34_3_a,
        "fattori_gravita": fattori_gravita,
        "livello_rischio": livello_rischio,
        "notifica_garante": notifica_garante,
        "comunicazione_interessati": comunicazione_interessati,
        "motivo_no_comunicazione": motivo_no_comunicazione,
        "ore_rimanenti": ore_rimanenti,
        "azioni_consigliate": azioni_consigliate,
        "riferimento_normativo": (
            "Art. 33 GDPR (notifica all'autorità di controllo); "
            "Art. 34 GDPR (comunicazione agli interessati); "
            "Art. 4(12) GDPR (definizione di violazione dei dati); "
            "EDPB Linee guida 9/2022 v. 2.0 (notifica delle violazioni)"
        ),
    }


@mcp.tool(tags={"privacy"})
def valutazione_data_breach(
    tipo_violazione: str,
    categorie_dati: list[str],
    n_interessati: int,
    dati_particolari: bool = False,
    misure_protezione: list[str] | None = None,
    impatto: str = "medio",
) -> dict:
    """Valuta un data breach e determina gli obblighi di notifica al Garante e comunicazione agli interessati.

    Usa questo tool quando: si verifica o si sospetta una violazione dei dati personali.
    Determina: (1) se notificare al Garante entro 72h (art. 33), (2) se comunicare agli
    interessati (art. 34), (3) il livello di rischio, (4) le azioni immediate da intraprendere.
    La cifratura esclude l'obbligo di comunicazione agli interessati (art. 34(3)(a)) solo per le
    violazioni di riservatezza (accesso non autorizzato a dati incomprensibili): per perdita o
    alterazione di dati cifrati la comunicazione resta dovuta se il rischio è elevato (EDPB 9/2022
    par. 76 e 79). La pseudonimizzazione da sola non rende i dati incomprensibili (par. 112).
    Il livello di rischio è una scala del tool (impatto dichiarato, +1 per dati particolari, +1 oltre
    100.000 interessati): le soglie di 10.000 e 100.000 interessati sono una convenzione del tool,
    non della norma né dell'EDPB (par. 118, nessuna soglia numerica); la notifica segue l'albero
    del Garante (rischio: notifica; rischio elevato: anche comunicazione).
    Vigenza: artt. 33 e 34 Reg. UE 2016/679 (testo vigente al 29/09/2026); EDPB Linee guida 9/2022
    v. 2.0 (28/03/2023).
    Precisione: INDICATIVO (albero decisionale di legge, ma il livello di rischio è una stima del
    tool; con dati cifrati il tool non sa se la chiave è integra né se esiste un backup).
    Chaining: se notifica_garante=True → genera_notifica_data_breach() per redigere la notifica

    Args:
        tipo_violazione: Tipo di violazione: 'confidenzialita' (accesso non autorizzato), 'integrita' (modifica), 'disponibilita' (perdita/distruzione)
        categorie_dati: Categorie di dati coinvolti (es. ['email', 'password hash', 'dati anagrafici'])
        n_interessati: Numero stimato di interessati coinvolti
        dati_particolari: True se coinvolti dati ex art. 9 (salute, biometria, etnia) o art. 10 (giudiziari)
        misure_protezione: Misure di sicurezza attive al momento della violazione (es. ['cifratura AES-256', 'controllo accessi']); solo la cifratura può escludere la comunicazione, e solo per violazioni di riservatezza
        impatto: Impatto stimato della violazione sugli interessati: 'basso', 'medio', 'alto', 'molto_alto'
    """
    return _valutazione_data_breach_impl(
        tipo_violazione=tipo_violazione,
        categorie_dati=categorie_dati,
        n_interessati=n_interessati,
        dati_particolari=dati_particolari,
        misure_protezione=misure_protezione,
        impatto=impatto,
    )


# ---------------------------------------------------------------------------
# Tool 11: calcolo_sanzione_gdpr
# ---------------------------------------------------------------------------

_GRAVITA_VALIDE = ("bassa", "media", "alta")


def _fascia_rettifica_fatturato(fatturato: float) -> dict | None:
    """EDPB 04/2022 par. 65-66: size adjustment tier for a turnover, None above 500 mln."""
    for fascia in _SANZIONI["metodo_edpb"]["rettifica_fatturato"]:
        if fatturato <= fascia["fino_a"]:
            return fascia
    return None


def _punto_di_partenza_edpb(
    massimale_applicabile: float, gravita: str, fascia_fatturato: dict | None
) -> tuple[float, float]:
    """Starting-amount range of the EDPB method: seriousness band, then size adjustment."""
    fascia = _SANZIONI["metodo_edpb"]["fasce_gravita"][gravita]
    minimo = massimale_applicabile * fascia["da_pct"] / 100
    massimo = massimale_applicabile * fascia["a_pct"] / 100
    if fascia_fatturato:
        minimo *= fascia_fatturato["da_pct"] / 100
        massimo *= fascia_fatturato["a_pct"] / 100
    return minimo, massimo


def _calcolo_sanzione_gdpr_impl(
    tipo_violazione: str,
    fatturato_annuo: float | None = None,
    fattori_aggravanti: list[str] | None = None,
    fattori_attenuanti: list[str] | None = None,
    precedenti: bool = False,
    gravita: str | None = None,
) -> dict:
    fattori_aggravanti = fattori_aggravanti or []
    fattori_attenuanti = fattori_attenuanti or []

    tipi_validi = ("art83_4", "art83_5", "art83_6")
    if tipo_violazione not in tipi_validi:
        return {"errore": f"tipo_violazione deve essere uno tra: {', '.join(tipi_validi)}"}
    gravita_di_default = gravita is None
    if gravita is None:
        gravita = "bassa"
    if gravita not in _GRAVITA_VALIDE:
        return {"errore": f"gravita deve essere una tra: {', '.join(_GRAVITA_VALIDE)}"}

    massimale_data = _SANZIONI["massimali"][tipo_violazione]
    max_euro = massimale_data["euro"]
    max_pct = massimale_data["percentuale_fatturato"]

    correttivi = _SANZIONI["correttivi_convenzione_tool"]
    aggravante_inc = correttivi["aggravante_incremento_pct"] / 100
    attenuante_rid = correttivi["attenuante_riduzione_pct"] / 100
    precedenti_inc = correttivi["precedenti_incremento_pct"] / 100

    # Aggravating/mitigating correction: convention of the tool, not in art. 83 nor in the
    # EDPB guidelines (par. 71 rules out predetermined percentages).
    n_aggravanti = len(fattori_aggravanti)
    n_attenuanti = len(fattori_attenuanti)

    moltiplicatore = 1.0
    moltiplicatore += n_aggravanti * aggravante_inc
    moltiplicatore -= n_attenuanti * attenuante_rid
    if precedenti:
        moltiplicatore += precedenti_inc
    moltiplicatore = max(
        correttivi["moltiplicatore_minimo"], min(moltiplicatore, correttivi["moltiplicatore_massimo"])
    )

    # Art. 83(4)-(6): the fixed amount or, for undertakings, the percentage of the total worldwide
    # annual turnover of the preceding financial year, whichever is higher.
    fatturato_noto = bool(fatturato_annuo and fatturato_annuo > 0)
    max_fatturato = fatturato_annuo * (max_pct / 100) if fatturato_noto else None
    massimale_effettivo = max(max_euro, max_fatturato) if fatturato_noto else max_euro
    massimale_effettivo = int(round(massimale_effettivo))

    fascia_fatturato = _fascia_rettifica_fatturato(fatturato_annuo) if fatturato_noto else None

    def _range(livello: str) -> tuple[float, float]:
        p_min, p_max = _punto_di_partenza_edpb(massimale_effettivo, livello, fascia_fatturato)
        # Correction for aggravating/mitigating circumstances, never above the legal maximum.
        return (
            round(min(p_min * moltiplicatore, massimale_effettivo), 0),
            round(min(p_max * moltiplicatore, massimale_effettivo), 0),
        )

    range_min_euro, range_max_euro = _range(gravita)
    partenza_min, partenza_max = _punto_di_partenza_edpb(massimale_effettivo, gravita, fascia_fatturato)
    fasce_gravita = _SANZIONI["metodo_edpb"]["fasce_gravita"]

    if fatturato_noto:
        if fascia_fatturato:
            rettifica_txt = (
                f"Rettifica dimensionale EDPB (fatturato fino a {fascia_fatturato['fino_a']:,.0f}€): "
                f"{fascia_fatturato['da_pct']}%-{fascia_fatturato['a_pct']}% del punto di partenza. "
            )
        else:
            rettifica_txt = "Fatturato oltre 500 milioni di euro: nessuna rettifica dimensionale (EDPB par. 66). "
        range_fatturato_note = (
            f"Con fatturato {fatturato_annuo:,.0f}€: massimale basato su % fatturato = "
            f"{max_fatturato:,.0f}€ ({max_pct}% fatturato). "
            f"Massimale effettivo applicato (maggiore tra i due): {massimale_effettivo:,.0f}€. "
            f"{rettifica_txt}"
            f"Range stimato con fatturato: {range_min_euro:,.0f}€ — {range_max_euro:,.0f}€"
        )
    else:
        range_fatturato_note = (
            "Fatturato non indicato: si applica il massimale fisso e non la rettifica dimensionale "
            "dell'EDPB (par. 65-66), che dipende dal fatturato dell'impresa."
        )

    # Analisi fattori
    fattori_aggravanti_match = []
    for fa in fattori_aggravanti:
        for f_ref in _SANZIONI["fattori_aggravanti"]:
            if fa.lower() in f_ref.lower() or f_ref.lower() in fa.lower():
                fattori_aggravanti_match.append(f_ref)
                break
        else:
            fattori_aggravanti_match.append(fa)

    fattori_attenuanti_match = []
    for fa in fattori_attenuanti:
        for f_ref in _SANZIONI["fattori_attenuanti"]:
            if fa.lower() in f_ref.lower() or f_ref.lower() in fa.lower():
                fattori_attenuanti_match.append(f_ref)
                break
        else:
            fattori_attenuanti_match.append(fa)

    avvertenza = (
        "Stima orientativa: punto di partenza secondo il metodo delle Linee guida EDPB 04/2022 "
        "(fascia di gravità, rettifica per fatturato), corretto con un moltiplicatore convenzionale "
        "del tool per aggravanti, attenuanti e precedenti (non previsto dall'EDPB, par. 71). "
        "La sanzione effettiva è determinata dal Garante caso per caso ai sensi dell'art. 83(2) GDPR."
    )
    if gravita_di_default:
        avvertenza += (
            " Gravità non indicata: assunta 'bassa' (0-10% del massimale applicabile); "
            "per violazioni di gravità media o alta indicare gravita='media' o 'alta'."
        )

    return {
        "tipo_violazione": tipo_violazione,
        "descrizione_violazione": massimale_data["descrizione"],
        "massimale": {
            "euro": max_euro,
            "pct_fatturato": max_pct,
            "effettivo_euro": massimale_effettivo,
            "descrizione": (
                f"Fino a {max_euro:,}€ o, per le imprese, {max_pct}% del fatturato mondiale totale "
                "annuo dell'esercizio precedente, se superiore"
            ),
        },
        "gravita": gravita,
        "punto_di_partenza_edpb": {
            "fascia_gravita_pct": [fasce_gravita[gravita]["da_pct"], fasce_gravita[gravita]["a_pct"]],
            "rettifica_fatturato_pct": (
                [fascia_fatturato["da_pct"], fascia_fatturato["a_pct"]] if fascia_fatturato else None
            ),
            "minimo": round(partenza_min, 0),
            "massimo": round(partenza_max, 0),
        },
        "range_stimato": {
            "minimo": range_min_euro,
            "massimo": range_max_euro,
            "nota": range_fatturato_note,
        },
        "range_per_gravita": {
            livello: {"minimo": _range(livello)[0], "massimo": _range(livello)[1]}
            for livello in _GRAVITA_VALIDE
        },
        "criteri_art83_2": _SANZIONI["criteri_art83_2"],
        "fattori_analisi": {
            "aggravanti_rilevati": fattori_aggravanti_match,
            "attenuanti_rilevati": fattori_attenuanti_match,
            "precedenti": precedenti,
            "moltiplicatore_applicato": round(moltiplicatore, 2),
        },
        "avvertenza": avvertenza,
        "riferimento_normativo": (
            "Art. 83 Reg. UE 2016/679 (GDPR) — Condizioni generali per l'imposizione di sanzioni "
            "amministrative pecuniarie; EDPB, Linee guida 04/2022 (v. 2.1), par. 60 e 65-66"
        ),
    }


@mcp.tool(tags={"privacy"})
@sourced("gdpr_sanzioni")
def calcolo_sanzione_gdpr(
    tipo_violazione: str,
    fatturato_annuo: float | None = None,
    fattori_aggravanti: list[str] | None = None,
    fattori_attenuanti: list[str] | None = None,
    precedenti: bool = False,
    gravita: str | None = None,
) -> dict:
    """Calcola il massimale e il range stimato di sanzione amministrativa GDPR ex art. 83.

    Usa questo tool quando: devi stimare la sanzione applicabile in seguito a una violazione
    GDPR, per valutazione del rischio, due diligence o consulenza a un'azienda sanzionata.
    art83_4: violazioni di obblighi titolare/responsabile (massimale 10M€ o, per le imprese,
    2% del fatturato mondiale totale annuo dell'esercizio precedente, se superiore).
    art83_5: violazioni principi base, diritti interessati, trasferimenti (massimale 20M€ o 4%).
    art83_6: inosservanza ordine di limitazione/sospensione (massimale 20M€ o 4%).
    Il range segue il metodo delle Linee guida EDPB 04/2022 (v. 2.1): punto di partenza in una
    fascia di gravità (bassa 0-10%, media 10-20%, alta 20-100% del massimale applicabile, par. 60),
    rettificato per il fatturato dell'impresa (da 0,2-0,4% fino a 2 mln a 40-100% fino a 500 mln,
    nessuna rettifica oltre, par. 65-66), poi corretto con un moltiplicatore convenzionale del tool
    per aggravanti, attenuanti e precedenti, mai oltre il massimale. Le Linee guida non sono
    vincolanti e non fissano importi (par. 69); il moltiplicatore non è previsto dall'EDPB.
    NON usare per stime definitive: la sanzione è sempre determinata dal Garante caso per caso.
    Vigenza: art. 83, par. 2 e 4-6, Reg. UE 2016/679 (testo vigente al 29/09/2026); EDPB Linee
    guida 04/2022 v. 2.1 (24/05/2023, corr. 29/06/2023).
    Precisione: STIMATO (metodo EDPB, non vincolante, più correttivi convenzionali del tool; non
    è il quantum irrogato, che dipende dalla valutazione del Garante).

    Args:
        tipo_violazione: Livello della violazione: 'art83_4' (massimale minore), 'art83_5' o 'art83_6' (massimale maggiore)
        fatturato_annuo: Fatturato mondiale totale annuo dell'esercizio precedente in euro, per le imprese (opzionale: senza, si usa il massimale fisso e non si applica la rettifica dimensionale)
        fattori_aggravanti: Lista fattori aggravanti presenti (es. ['dati sensibili', 'larga scala', 'violazione dolosa'])
        fattori_attenuanti: Lista fattori attenuanti presenti (es. ['prima violazione', 'cooperazione piena', 'misure correttive immediate'])
        precedenti: True se il titolare ha precedenti violazioni o ammonimenti del Garante
        gravita: Gravità della violazione secondo l'EDPB (par. 60): 'bassa', 'media' o 'alta'. Se omessa si assume 'bassa' e la risposta lo segnala; `range_per_gravita` riporta comunque le tre fasce
    """
    return _calcolo_sanzione_gdpr_impl(
        tipo_violazione=tipo_violazione,
        fatturato_annuo=fatturato_annuo,
        fattori_aggravanti=fattori_aggravanti,
        fattori_attenuanti=fattori_attenuanti,
        precedenti=precedenti,
        gravita=gravita,
    )


# ---------------------------------------------------------------------------
# Tool 12: genera_notifica_data_breach
# ---------------------------------------------------------------------------

def _genera_notifica_data_breach_impl(
    titolare: str,
    data_violazione: str,
    data_scoperta: str,
    descrizione: str,
    categorie_dati: list[str],
    n_interessati: int,
    conseguenze: str,
    misure_adottate: list[str],
    dpo: str = "",
    punto_contatto: str = "",
    n_registrazioni: int | None = None,
) -> dict:
    try:
        dt_scoperta = datetime.fromisoformat(data_scoperta)
    except ValueError:
        return {"errore": "data_scoperta non valida, usare formato YYYY-MM-DDTHH:MM o YYYY-MM-DD"}
    if dt_scoperta.tzinfo is not None:
        dt_scoperta = dt_scoperta.astimezone().replace(tzinfo=None)

    try:
        dt_violazione = datetime.fromisoformat(data_violazione)
    except ValueError:
        return {"errore": "data_violazione non valida, usare formato YYYY-MM-DDTHH:MM o YYYY-MM-DD"}
    if dt_violazione.tzinfo is not None:
        dt_violazione = dt_violazione.astimezone().replace(tzinfo=None)

    if n_interessati < 0:
        return {"errore": "n_interessati deve essere >= 0"}
    if n_registrazioni is not None and n_registrazioni < 0:
        return {"errore": "n_registrazioni deve essere >= 0"}
    # A breach cannot come after the moment the controller became aware of it: the 72 hours of
    # art. 33(1) run from awareness. The draft is still produced (the 72 h window is short) but
    # the incoherence is flagged in the document and in `avvisi`.
    avvisi: list[str] = []
    if dt_violazione > dt_scoperta:
        avvisi.append(
            "date incoerenti: la data della violazione "
            f"({dt_violazione.strftime('%d/%m/%Y %H:%M')}) è successiva alla data di scoperta "
            f"({dt_scoperta.strftime('%d/%m/%Y %H:%M')}); verificare le date prima dell'invio"
        )

    scadenza_72h = dt_scoperta + timedelta(hours=72)
    termine_scadenza = scadenza_72h.strftime("%d/%m/%Y ore %H:%M")

    # Ore trascorse dalla scoperta
    ora_attuale = _clock.now()
    ore_trascorse = (ora_attuale - dt_scoperta).total_seconds() / 3600
    scadenza_superata = ore_trascorse > 72

    avviso_scadenza = ""
    if scadenza_superata:
        avviso_scadenza = (
            f"ATTENZIONE: Sono trascorse circa {ore_trascorse:.0f} ore dalla scoperta. "
            f"Il termine di 72 ore è probabilmente superato. Notificare immediatamente "
            f"al Garante indicando i motivi del ritardo (art. 33(1) GDPR)."
        )
    if avvisi:
        avviso_scadenza = (avviso_scadenza + "\n" if avviso_scadenza else "") + "\n".join(
            f"ATTENZIONE: {a}" for a in avvisi
        )

    dpo_section = f"DPO: {dpo}" if dpo else "DPO: [non nominato / non indicato]"
    contatto_section = (
        f"Altro punto di contatto presso cui ottenere più informazioni: {punto_contatto}"
        if punto_contatto
        else "Altro punto di contatto presso cui ottenere più informazioni: "
        "[indicare nome e recapiti se manca il DPO]"
    )
    # Italian thousands separator (1.200), not the English 1,200
    n_interessati_text = f"{n_interessati:,}".replace(",", ".")
    n_registrazioni_text = (
        f"{n_registrazioni:,}".replace(",", ".")
        if n_registrazioni is not None
        else "[indicare, ove possibile]"
    )

    categorie_text = "\n".join(f"  - {c}" for c in categorie_dati)
    misure_text = "\n".join(f"  - {m}" for m in misure_adottate)

    elementi_art33_3 = {
        "a_natura_violazione": bool(descrizione),
        # Art. 33(3)(b): "il responsabile della protezione dei dati o ... altro punto di contatto"
        "b_contatti_dpo": bool(dpo or punto_contatto),
        "c_probabili_conseguenze": bool(conseguenze),
        "d_misure_adottate": len(misure_adottate) > 0,
    }

    tutti_elementi = all(elementi_art33_3.values())

    testo = f"""NOTIFICA DI VIOLAZIONE DEI DATI PERSONALI (DATA BREACH)
ai sensi dell'art. 33 Reg. UE 2016/679 (GDPR)

Al Garante per la protezione dei dati personali
Piazza Venezia n. 11, 00187 Roma

{'=' * 70}
NOTA: Questa notifica deve essere inviata tramite la procedura telematica del Garante
(provv. 27 maggio 2021, n. 209), disponibile all'indirizzo: https://servizi.gpdp.it/databreach/
{'=' * 70}

1. TITOLARE, DPO O ALTRO PUNTO DI CONTATTO [art. 33(3)(b)]
Titolare: {titolare}
{dpo_section}
{contatto_section}

2. NATURA DELLA VIOLAZIONE [art. 33(3)(a)]
{descrizione}

Data e ora della violazione (stimata): {dt_violazione.strftime('%d/%m/%Y ore %H:%M')}
Data e ora della scoperta: {dt_scoperta.strftime('%d/%m/%Y ore %H:%M')}
Data e ora della presente notifica: _______________

{avviso_scadenza}

3. CATEGORIE E NUMERO APPROSSIMATIVO DI INTERESSATI E DI REGISTRAZIONI [art. 33(3)(a)]
Numero approssimativo di interessati: {n_interessati_text}
Categorie di dati coinvolti (categorie di registrazioni dei dati personali):
{categorie_text}
Numero approssimativo di registrazioni dei dati personali in questione: {n_registrazioni_text}

Categorie di dati particolari (art. 9) coinvolti: □ Sì □ No
Dati di minori coinvolti: □ Sì □ No

4. PROBABILI CONSEGUENZE DELLA VIOLAZIONE [art. 33(3)(c)]
{conseguenze}

Impatto stimato sugli interessati:
  □ Discriminazione
  □ Furto d'identità o frode
  □ Perdite finanziarie
  □ Danno alla reputazione
  □ Perdita della riservatezza di dati protetti da segreto professionale
  □ Altro: _______________

5. MISURE ADOTTATE O PROPOSTE PER PORRE RIMEDIO [art. 33(3)(d)]
{misure_text}

Misure per attenuare i possibili effetti negativi:
  □ Notifica agli interessati ai sensi dell'art. 34 GDPR
  □ Blocco degli accessi non autorizzati
  □ Ripristino dei sistemi compromessi
  □ Rafforzamento delle misure di sicurezza
  □ Coinvolgimento delle autorità competenti (Polizia Postale, CERT)
  □ Altro: _______________

6. COMUNICAZIONE AGLI INTERESSATI (art. 34 GDPR)
  □ Comunicazione effettuata agli interessati (allegare copia)
  □ Comunicazione non ancora effettuata (motivare)
  □ Comunicazione non obbligatoria (indicare motivo, es. dati cifrati ex art. 34(3)(a))

7. INFORMAZIONI AGGIUNTIVE
La presente notifica è:
  □ Notifica iniziale (entro 72 ore, con possibilità di integrazioni)
  □ Notifica integrativa (in aggiunta a notifica iniziale del _______________)

Numero di riferimento notifica precedente (se integrativa): _______________

Documenti allegati:
  □ Log di sistema
  □ Report tecnico dell'incidente
  □ Comunicazione agli interessati
  □ Altro: _______________

{'=' * 70}
Firma del Titolare / DPO: ___________________________
Luogo e data: ___________________________
{'=' * 70}

TERMINE SCADENZA NOTIFICA: {termine_scadenza}
(72 ore dalla scoperta — art. 33(1) GDPR)

Riferimento normativo: Art. 33 Reg. UE 2016/679 (GDPR) — Notifica all'autorità di controllo
"""

    return {
        "testo": testo.strip(),
        "termine_scadenza": termine_scadenza,
        "scadenza_72h_superata": scadenza_superata,
        "ore_dalla_scoperta": round(ore_trascorse, 1),
        "elementi_art33_3": elementi_art33_3,
        "tutti_elementi_presenti": tutti_elementi,
        "avvisi": avvisi,
        "riferimento_normativo": "Art. 33 Reg. UE 2016/679 (GDPR) — Notifica di una violazione dei dati personali all'autorità di controllo",
    }


@mcp.tool(tags={"privacy"})
def genera_notifica_data_breach(
    titolare: str,
    data_violazione: str,
    data_scoperta: str,
    descrizione: str,
    categorie_dati: list[str],
    n_interessati: int,
    conseguenze: str,
    misure_adottate: list[str],
    dpo: str = "",
    punto_contatto: str = "",
    n_registrazioni: int | None = None,
) -> dict:
    """Genera il modulo di notifica di un data breach al Garante ai sensi dell'art. 33 GDPR.

    Usa questo tool quando: valutazione_data_breach() ha stabilito che la notifica al Garante
    è obbligatoria. Il termine è di 72 ore dalla scoperta. Se le 72h sono già scorse,
    notificare immediatamente indicando i motivi del ritardo.
    La notifica deve essere inviata tramite il portale del Garante: https://servizi.gpdp.it/databreach/
    I 4 elementi obbligatori ex art. 33(3) sono: (a) natura violazione, con categorie e numero
    approssimativo di interessati e di registrazioni, (b) DPO o altro punto di contatto,
    (c) probabili conseguenze, (d) misure adottate. Se manca il DPO indicare punto_contatto.
    Se data_violazione è successiva a data_scoperta il modulo riporta un avviso di date incoerenti.
    Chaining: preceduto da valutazione_data_breach() per stabilire obbligo di notifica
              e comunicazione_interessati per l'art. 34
    Vigenza: art. 33, parr. 1 e 3 Reg. UE 2016/679, testo vigente al 2026-09-29; procedura
    telematica del Garante, provv. 27 maggio 2021 n. 209 (doc. web 9667201), dal 1° luglio 2021.
    Precisione: ESATTO (termine di 72 ore solari dalla scoperta, art. 33(1), calcolato sull'ora
    locale senza correzione per il cambio dell'ora legale; il modulo riproduce i contenuti
    minimi dell'art. 33(3) e non sostituisce l'invio sul portale del Garante).

    Args:
        titolare: Ragione sociale, sede e recapiti del titolare del trattamento
        data_violazione: Data/ora stimata della violazione (formato YYYY-MM-DD o YYYY-MM-DDTHH:MM)
        data_scoperta: Data/ora di scoperta della violazione (formato YYYY-MM-DD o YYYY-MM-DDTHH:MM)
        descrizione: Descrizione della natura della violazione (cosa è accaduto, come, sistemi coinvolti)
        categorie_dati: Categorie di dati personali coinvolti nella violazione
        n_interessati: Numero approssimativo di interessati coinvolti
        conseguenze: Probabili conseguenze della violazione per gli interessati
        misure_adottate: Misure adottate o proposte per rimediare alla violazione
        dpo: Contatti del DPO se nominato (lasciare vuoto se assente)
        punto_contatto: Altro punto di contatto presso cui ottenere più informazioni (art. 33(3)(b)), da indicare se manca il DPO
        n_registrazioni: Numero approssimativo di registrazioni dei dati personali in questione (art. 33(3)(a)), ove possibile
    """
    return _genera_notifica_data_breach_impl(
        titolare=titolare,
        data_violazione=data_violazione,
        data_scoperta=data_scoperta,
        descrizione=descrizione,
        categorie_dati=categorie_dati,
        n_interessati=n_interessati,
        conseguenze=conseguenze,
        misure_adottate=misure_adottate,
        dpo=dpo,
        punto_contatto=punto_contatto,
        n_registrazioni=n_registrazioni,
    )

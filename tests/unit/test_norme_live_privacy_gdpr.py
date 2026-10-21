"""Live gate: `analisi_base_giuridica` against the vigente text of the norms it applies.

`analisi_base_giuridica` (src/tools/privacy_gdpr.py) reads `src/data/gdpr_basi_giuridiche.json`:
a catalogue of the six legal bases of art. 6(1) GDPR, the ten exceptions of art. 9(2) and a
context -> base matrix whose notes cite art. 7, 21, 22 GDPR, artt. 75, 122, 130 D.Lgs. 196/2003
and art. 4 L. 300/1970. This file reads each of those articles through `cite_law()` (EUR-Lex /
CELLAR for the GDPR, Normattiva for the Italian acts) and checks two things:

1. the words the catalogue relies on are in the vigente text (letters, exclusions, conditions);
2. the base the tool recommends for the benchmark cases is the one the norm points to.

The second group fails today on purpose: the tool always takes the first entry of the matrix
for a context (B2C -> marketing, dipendenti -> gestione), so `tipo_trattamento` never orients the
choice, and it always calls "più frequenti" the art. 9(2) letters a), b), c) whatever the
context. Those failures are genuine gaps between the tool and the norm, not flakiness.

It needs the network and is excluded from the default run:

    .venv/bin/pytest tests/unit/test_norme_live_privacy_gdpr.py -m live -q -p no:cacheprovider -rfEs
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

import pytest

from tests.unit._norme_live import contiene, normalizza
from tests.unit._norme_live import testo_vigente as _testo_vigente  # alias: pytest would collect test*

pytestmark = pytest.mark.live

_TABELLA = Path(__file__).resolve().parents[2] / "src" / "data" / "gdpr_basi_giuridiche.json"


@lru_cache(maxsize=None)
def _testo(reference: str) -> str:
    """Vigente text, fetched once per reference for the whole module."""
    return _testo_vigente(reference)


def _assert_parole(reference: str, *frasi: str) -> str:
    testo = _testo(reference)
    missing = contiene(testo, *frasi)
    assert not missing, f"{reference}: il testo vigente non contiene {missing}"
    return testo


def _tabella() -> dict:
    return json.loads(_TABELLA.read_text(encoding="utf-8"))


def _tool(**kwargs) -> dict:
    import src.server  # noqa: F401  (registers every tool module first: avoids a circular import)
    from src.tools.privacy_gdpr import analisi_base_giuridica

    fn = getattr(analisi_base_giuridica, "fn", analisi_base_giuridica)
    risultato = fn(**kwargs)
    assert "errore" not in risultato, risultato
    return risultato


def _lettere(testo: str, inizio: str, fine: str) -> dict[str, str]:
    """Split an enumerated paragraph ("...:a)...;b)...") into {letter: text} between two markers."""
    testo = normalizza(testo)
    a = testo.index(normalizza(inizio))
    b = testo.index(normalizza(fine), a)
    parti = re.split(r"[:;]\s*([a-z])\)", testo[a:b])
    return {parti[i]: parti[i + 1] for i in range(1, len(parti) - 1, 2)}


def _piu_frequenti(risultato: dict) -> str:
    nota = risultato["note_dati_particolari_art9"]
    # The wording was "più frequenti" (a fixed a-c list); after the fix the conditions are
    # "pertinenti" to the matrix entry. Form change only: the letter check below is unchanged.
    marker = "pertinenti"
    assert marker in nota, nota
    return nota[nota.index(marker):]


# ---------------------------------------------------------------------------
# Art. 6 GDPR — the six bases of the catalogue
# ---------------------------------------------------------------------------

# Words that identify each letter of art. 6(1) in the vigente text.
_ART6_PAROLE = {
    "consenso": ("a", "ha espresso il consenso al trattamento dei propri dati personali"),
    "contratto": ("b", "necessario all'esecuzione di un contratto di cui l'interessato è parte"),
    "obbligo_legale": ("c", "necessario per adempiere un obbligo legale"),
    "interesse_vitale": ("d", "salvaguardia degli interessi vitali"),
    "interesse_pubblico": ("e", "esecuzione di un compito di interesse pubblico"),
    "legittimo_interesse": ("f", "perseguimento del legittimo interesse"),
}


def test_art6_par1_gdpr_lettere_a_f_della_tabella_coincidono_col_testo():
    """Art. 6(1) GDPR: each base of the catalogue carries the letter the Regulation gives it."""
    lettere = _lettere(
        _testo("art. 6 GDPR"),
        "ricorre almeno una delle seguenti condizioni",
        "la lettera f) del primo comma",
    )
    assert sorted(lettere) == list("abcdef"), lettere.keys()
    basi = _tabella()["basi_art6"]
    assert sorted(basi) == sorted(_ART6_PAROLE), basi.keys()
    for nome, (lettera, parole) in _ART6_PAROLE.items():
        assert basi[nome]["lettera"] == lettera, (nome, basi[nome]["lettera"])
        assert basi[nome]["articolo"] == f"Art. 6(1)({lettera}) GDPR", basi[nome]["articolo"]
        assert normalizza(parole) in lettere[lettera], (nome, lettere[lettera])


def test_art6_par1_secondo_comma_gdpr_legittimo_interesse_escluso_per_la_pa():
    """Art. 6(1), second subparagraph: letter f) does not apply to public authorities.

    The PA benchmark case must recommend art. 6(1)(e) and never offer the legitimate interest.
    """
    _assert_parole(
        "art. 6 GDPR",
        "la lettera f) del primo comma non si applica al trattamento di dati effettuato "
        "dalle autorità pubbliche nell'esecuzione dei loro compiti",
    )
    r = _tool(
        tipo_trattamento="rilascio certificati",
        contesto="pubblica_amministrazione",
        finalita="funzioni istituzionali",
    )
    assert r["base_consigliata"] == "interesse_pubblico", r["base_consigliata"]
    assert "legittimo_interesse" not in [b["base"] for b in r["basi_giuridiche_applicabili"]]
    assert "art. 6(1), ultimo comma" in r["motivazione"], r["motivazione"]


def test_art6_par3_gdpr_e_art_2_ter_codice_privacy_base_nel_diritto_nazionale():
    """Art. 6(3) GDPR + art. 2-ter D.Lgs. 196/2003: letters c) and e) need a basis in law.

    The catalogue says so for both bases ("base nel diritto UE o nazionale"); art. 2-ter
    names the Italian sources (legge, regolamento, atti amministrativi generali).
    """
    _assert_parole(
        "art. 6 GDPR",
        "la base su cui si fonda il trattamento dei dati di cui al paragrafo 1, lettere c) ed e)",
        "dal diritto dello stato membro cui è soggetto il titolare del trattamento",
    )
    _assert_parole(
        "art. 2-ter D.Lgs. 196/2003",
        "articolo 6, paragrafo 3, lettera b), del regolamento",
        "norma di legge",
        "di regolamento",
        "atti amministrativi generali",
    )
    basi = _tabella()["basi_art6"]
    assert any("UE o Stato membro" in c for c in basi["obbligo_legale"]["contro"])
    assert any("diritto UE o nazionale" in c for c in basi["interesse_pubblico"]["contro"])


def test_art7_par1_e_par3_gdpr_onere_della_prova_e_revoca_del_consenso():
    """Art. 7(1) and 7(3) GDPR, cited in the catalogue's 'contro' of the consent."""
    _assert_parole(
        "art. 7 GDPR",
        "deve essere in grado di dimostrare che l'interessato ha prestato il proprio consenso",
        "il diritto di revocare il proprio consenso in qualsiasi momento",
    )
    contro = _tabella()["basi_art6"]["consenso"]["contro"]
    assert "Revocabile in qualsiasi momento (art. 7(3))" in contro
    assert "Onere della prova sul titolare (art. 7(1))" in contro


def test_art21_par1_gdpr_opposizione_sulle_lettere_e_f():
    """Art. 21(1) GDPR: the right to object covers processing under art. 6(1)(e) or (f)."""
    _assert_parole("art. 21 GDPR", "ai sensi dell'articolo 6, paragrafo 1, lettere e) o f)")
    basi = _tabella()["basi_art6"]
    assert any("art. 21" in p for p in basi["interesse_pubblico"]["pro"])
    assert any("art. 21" in c for c in basi["legittimo_interesse"]["contro"])


def test_art6_par1_lett_b_gdpr_ecommerce_esecuzione_ordine_e_contratto():
    """Art. 6(1)(b) + art. 7(4) GDPR: order execution rests on the contract, not on consent.

    Benchmark case 'E-commerce B2C'. The processing is "necessario all'esecuzione di un
    contratto di cui l'interessato è parte"; art. 7(4) warns against tying the contract to a
    consent. The tool answers 'consenso' with the note on e-mail marketing, because for B2C it
    always reads the matrix entry B2C_marketing and never B2C_ecommerce.
    """
    _assert_parole(
        "art. 6 GDPR",
        "il trattamento è necessario all'esecuzione di un contratto di cui l'interessato è parte",
    )
    _assert_parole(
        "art. 7 GDPR",
        "l'esecuzione di un contratto, compresa la prestazione di un servizio, sia condizionata "
        "alla prestazione del consenso al trattamento di dati personali non necessario",
    )
    r = _tool(
        tipo_trattamento="gestione ordini e-commerce",
        contesto="B2C",
        finalita="esecuzione dell'ordine e consegna",
    )
    assert r["base_consigliata"] == "contratto", (
        f"art. 6(1)(b) GDPR: per l'esecuzione dell'ordine la base è il contratto; "
        f"il tool consiglia {r['base_consigliata']!r} con la motivazione {r['motivazione']!r}"
    )


def test_art6_par1_lett_b_gdpr_b2b_gestione_contratto():
    """Art. 6(1)(b) GDPR: B2B client management rests on the contract (coincides)."""
    r = _tool(
        tipo_trattamento="gestione anagrafica clienti business",
        contesto="B2B",
        finalita="esecuzione del contratto di fornitura",
    )
    assert r["base_consigliata"] == "contratto", r["base_consigliata"]
    assert r["basi_giuridiche_applicabili"][0]["articolo"] == "Art. 6(1)(b) GDPR"


# ---------------------------------------------------------------------------
# Art. 9 GDPR — special categories
# ---------------------------------------------------------------------------

_ART9_PAROLE = {
    "a": "consenso esplicito",
    "b": "diritto del lavoro",
    "c": "interesse vitale",
    "d": "senza scopo di lucro",
    "e": "resi manifestamente pubblici",
    "f": "in sede giudiziaria",
    "g": "interesse pubblico rilevante",
    "h": "diagnosi",
    "i": "sanità pubblica",
    "j": "ricerca scientifica",
}


def test_art9_par2_gdpr_dieci_lettere_coincidono_con_la_tabella():
    """Art. 9(2) GDPR: letters a)-j), no more no less, each matching the catalogue entry."""
    lettere = _lettere(
        _testo("art. 9 GDPR"),
        "il paragrafo 1 non si applica se si verifica uno dei seguenti casi",
        "3. i dati personali di cui al paragrafo 1",
    )
    assert sorted(lettere) == list("abcdefghij"), lettere.keys()
    eccezioni = {v["lettera"]: v["descrizione"] for v in _tabella()["condizioni_art9"]["eccezioni"].values()}
    assert sorted(eccezioni) == list("abcdefghij"), eccezioni.keys()
    for lettera, parole in _ART9_PAROLE.items():
        assert normalizza(parole) in lettere[lettera], (lettera, lettere[lettera])


def test_art9_par1_gdpr_premessa_elenca_tutte_le_categorie():
    """Art. 9(1) GDPR: the catalogue's summary of the special categories.

    The vigente text reads "convinzioni religiose o filosofiche"; the premessa the tool prints
    says only "convinzioni religiose", so philosophical beliefs drop out of the list.
    """
    _assert_parole(
        "art. 9 GDPR",
        "l'origine razziale o etnica",
        "le opinioni politiche",
        "le convinzioni religiose o filosofiche",
        "l'appartenenza sindacale",
        "dati genetici",
        "dati biometrici intesi a identificare in modo univoco una persona fisica",
        "dati relativi alla salute o alla vita sessuale o all'orientamento sessuale",
    )
    premessa = normalizza(_tabella()["condizioni_art9"]["premessa"])
    mancanti = [p for p in ("filosofiche", "sindacale", "genetici", "biometrici", "salute", "orientamento sessuale")
                if p not in premessa]
    assert not mancanti, f"art. 9(1) GDPR: la premessa del tool non nomina {mancanti}: {premessa!r}"


@pytest.mark.parametrize(
    ("contesto", "tipo", "finalita", "lettera", "norma"),
    [
        # art. 75 D.Lgs. 196/2003: health care runs on art. 9(2)(h) and (i) + 9(3).
        ("sanita", "cartella clinica", "diagnosi e cura", "h", "art. 75 D.Lgs. 196/2003"),
        # art. 2-sexies, co. 2, lett. m) D.Lgs. 196/2003: benefits granted by a PA are
        # "interesse pubblico rilevante", i.e. art. 9(2)(g).
        ("pubblica_amministrazione", "gestione pratiche di invalidità civile", "riconoscimento benefici",
         "g", "art. 2-sexies D.Lgs. 196/2003"),
        # art. 9(2)(b): employment law obligations. Coincides (b is among a, b, c by chance).
        ("dipendenti", "certificati di malattia", "gestione assenze per malattia", "b", "art. 9 GDPR"),
    ],
    ids=["sanita_9_2_h", "pa_9_2_g", "dipendenti_9_2_b"],
)
def test_art9_par2_gdpr_condizioni_indicate_seguono_il_contesto(contesto, tipo, finalita, lettera, norma):
    """The art. 9(2) conditions the tool calls "più frequenti" must include the one the norm names.

    Today the tool prints `condizioni_art9[:3]`, i.e. letters a), b), c) for every context.
    """
    if norma == "art. 75 D.Lgs. 196/2003":
        _assert_parole(norma, "articolo 9, paragrafi 2, lettere h) ed i), e 3 del regolamento")
    elif norma == "art. 2-sexies D.Lgs. 196/2003":
        _assert_parole(
            norma,
            "necessari per motivi di interesse pubblico rilevante ai sensi del paragrafo 2, lettera g)",
            "concessione, liquidazione, modifica e revoca di benefici economici",
        )
    else:
        _assert_parole(norma, "in materia di diritto del lavoro e della sicurezza sociale e protezione sociale")
    r = _tool(tipo_trattamento=tipo, contesto=contesto, finalita=finalita, dati_particolari=True)
    frequenti = _piu_frequenti(r)
    assert f"Art. 9(2)({lettera})" in frequenti, (
        f"{norma}: per il contesto {contesto!r} la condizione è l'art. 9(2)({lettera}) GDPR; "
        f"il tool indica come più frequenti: {frequenti!r}"
    )


def test_art9_par3_gdpr_sanita_la_lettera_h_richiama_il_segreto_professionale():
    """Art. 9(2)(h) is "fatte salve le condizioni e le garanzie di cui al paragrafo 3".

    Art. 9(3): data processed by or under a professional bound by professional secrecy. The
    health-care answer should say so; the tool never mentions art. 9(3).
    """
    _assert_parole(
        "art. 9 GDPR",
        "fatte salve le condizioni e le garanzie di cui al paragrafo 3",
        "professionista soggetto al segreto professionale",
    )
    r = _tool(tipo_trattamento="cartella clinica", contesto="sanita", finalita="diagnosi e cura",
              dati_particolari=True)
    risposta = json.dumps(r, ensure_ascii=False).lower()
    assert "9(3)" in risposta or "segreto professionale" in risposta, (
        "art. 9(3) GDPR: la risposta per il contesto 'sanita' non richiama il segreto professionale"
    )


# ---------------------------------------------------------------------------
# Italian rules cited by the matrix notes
# ---------------------------------------------------------------------------

def test_art130_codice_privacy_email_marketing_consenso_e_soft_spam():
    """Art. 130, commi 1, 2 e 4, D.Lgs. 196/2003: consent for e-mail marketing, soft-spam carve-out.

    The B2C_marketing note says exactly this (coincides).
    """
    _assert_parole(
        "art. 130 D.Lgs. 196/2003",
        "è consentito con il consenso del contraente o utente",
        "mediante posta elettronica",
        "può non richiedere il consenso dell'interessato, sempre che si tratti di servizi analoghi",
    )
    r = _tool(tipo_trattamento="invio newsletter", contesto="B2C",
              finalita="marketing diretto via email a clienti esistenti")
    assert r["base_consigliata"] == "consenso", r["base_consigliata"]
    assert "art. 130 D.Lgs. 196/2003" in r["motivazione"], r["motivazione"]
    assert "soft spam" in r["motivazione"], r["motivazione"]


def test_art4_statuto_lavoratori_videosorveglianza_dipendenti():
    """Art. 4 L. 300/1970 (and art. 114 D.Lgs. 196/2003): cameras need a union agreement or ITL.

    Benchmark case 'Videosorveglianza sui dipendenti'. Protecting company assets is one of the
    purposes art. 4 allows, subject to the collective agreement or the INL authorisation; it is
    not "necessario all'esecuzione di un contratto" (art. 6(1)(b)). The tool answers 'contratto'
    and never mentions art. 4, because for 'dipendenti' it always reads dipendenti_gestione.
    """
    _assert_parole(
        "art. 4 L. 300/1970",
        "per la tutela del patrimonio aziendale",
        "previo accordo collettivo stipulato dalla rappresentanza sindacale unitaria",
        "ispettorato nazionale del lavoro",
    )
    _assert_parole(
        "art. 114 D.Lgs. 196/2003",
        "resta fermo quanto disposto dall'articolo 4 della legge 20 maggio 1970, n. 300",
    )
    r = _tool(tipo_trattamento="videosorveglianza del magazzino", contesto="dipendenti",
              finalita="tutela del patrimonio aziendale")
    risposta = json.dumps(r, ensure_ascii=False)
    difetti = []
    if r["base_consigliata"] == "contratto":
        difetti.append("base consigliata 'contratto' (art. 6(1)(b)) per una videosorveglianza")
    if "300/1970" not in risposta:
        difetti.append("nessun richiamo all'art. 4 L. 300/1970 (accordo sindacale o autorizzazione INL)")
    assert not difetti, f"art. 4 L. 300/1970: {difetti}"


def test_art122_codice_privacy_cookie_di_profilazione_richiedono_consenso():
    """Art. 122 D.Lgs. 196/2003: storing/reading on the terminal requires consent (coincides)."""
    _assert_parole(
        "art. 122 D.Lgs. 196/2003",
        "abbia espresso il proprio consenso dopo essere stato informato",
    )
    r = _tool(tipo_trattamento="cookie di profilazione", contesto="profilazione",
              finalita="pubblicità comportamentale")
    assert r["base_consigliata"] == "consenso", r["base_consigliata"]


def test_art22_par2_gdpr_decisioni_automatizzate_tre_eccezioni_non_solo_consenso():
    """Art. 22(2) GDPR: an automated decision is allowed on contract, law OR explicit consent.

    The profilazione note says "art. 22 GDPR richiede consenso esplicito", presenting one of
    three alternative exceptions as the only one (and art. 22 concerns decisions based solely
    on automated processing, not profiling as such).
    """
    _assert_parole(
        "art. 22 GDPR",
        "decisione basata unicamente sul trattamento automatizzato",
        "sia necessaria per la conclusione o l'esecuzione di un contratto",
        "sia autorizzata dal diritto dell'unione o dello stato membro",
        "si basi sul consenso esplicito dell'interessato",
    )
    r = _tool(tipo_trattamento="scoring creditizio automatizzato", contesto="profilazione",
              finalita="decisione sulla concessione del credito")
    motivazione = normalizza(r["motivazione"])
    assert "art. 22" in motivazione, motivazione
    assert "contratto" in motivazione and ("autorizzat" in motivazione or "diritto" in motivazione), (
        "art. 22(2) GDPR: la nota del tool presenta il consenso esplicito come unica via "
        f"(mancano contratto e autorizzazione di legge): {r['motivazione']!r}"
    )

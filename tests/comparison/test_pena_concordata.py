"""Comparison tests: pena_concordata vs avvocatoandreani.it.

Il tool (``src/tools/diritto_penale.py``) simula la pena patteggiata (art. 444 c.p.p.):
dalla pena base in MESI toglie un terzo per le attenuanti generiche (art. 62-bis c.p.,
nella misura massima dell'art. 65 n. 3 c.p.) e poi un terzo per la diminuente del rito
(art. 444 co. 1 c.p.p., "diminuita fino a un terzo": il tool applica sempre il massimo).
Restituisce ``pena_finale_mesi`` a due decimali, il ``dettaglio`` dei passaggi e due
indicatori: ``patteggiamento_possibile`` (pena finale <= 60 mesi, art. 444 co. 1 c.p.p.)
e ``sospendibile`` (pena finale <= 24 mesi, art. 163 co. 1 c.p.). Grado INDICATIVO.

Pagina del sito
---------------
Il sito non ha un calcolatore del patteggiamento (fase 0): si usa
``calcolo-aumenti-riduzioni-pena.php`` (modulo ``CalcoloPena``), che la pagina stessa
indica per il patteggiamento e l'abbreviato. Pena base in anni / mesi / giorni (select
``Anni``, ``Mesi``, ``Giorni``); fino a quattro righe di variazione con radio
``Operazione(n)`` (``+`` aumenta, ``-`` riduci) e frazione ``Frazione(n)`` (1/6, 1/3,
1/2, 2/3). Il patteggiamento si riproduce con due righe "Riduci 1/3" (generiche, poi
rito). Il risultato e' una tabella "Pena Base / Riduzione di 1/3 / Pena Finale" con la
durata in anni, mesi e giorni.

Convenzioni del sito osservate (Playwright, 25/09/2026):
- anno = 12 mesi, mese = 30 giorni;
- a ogni passaggio le frazioni di giorno sono troncate e il valore troncato e' la base
  del passaggio successivo (lettura "a ogni passaggio" dell'art. 134 co. 2 c.p.); il tool
  lavora in mesi continui e non tronca mai;
- il sito non dice se il patteggiamento e' ammissibile ne' se la pena e' sospendibile:
  gli indicatori del tool si confrontano con le soglie di legge (60 e 24 mesi) applicate
  alla pena finale del sito.

Confronto: la durata si porta in giorni con la convenzione del sito (mesi del tool x 30).
Tolleranza: meno di UN giorno per passaggio. Motivazione (piu' ampia delle "date esatte"
del brief): il sito esprime la pena in giorni interi troncando la frazione di giorno, il
tool in mesi a due decimali (granularita' 0,3 giorni); una differenza inferiore al giorno
e' solo granularita' di visualizzazione, una differenza di un giorno o piu' e' un
risultato diverso.

Il sito e' un benchmark, non una fonte: gli scostamenti restano registrati e li giudica
la fase 2.
"""

import re
import time

import pytest

from tests.comparison.conftest import goto

PAGE = "calcolo-aumenti-riduzioni-pena.php"
GIORNI_MESE = 30  # convenzione del sito
TOL_GIORNI = 1.0  # vedi docstring del modulo
LIMITE_PATTEGGIAMENTO_GG = 60 * GIORNI_MESE  # art. 444 co. 1 c.p.p.: cinque anni
LIMITE_SOSPENSIONE_GG = 24 * GIORNI_MESE  # art. 163 co. 1 c.p.: due anni

_HIDE_CMP = (
    ".qc-cmp2-container,#qc-cmp2-container"
    "{display:none !important;pointer-events:none !important}"
)


# ---------------------------------------------------------------------------
# Tool
# ---------------------------------------------------------------------------

def _tool(**kw) -> dict:
    import src.server  # noqa: F401  (registra i moduli, evita import circolari)
    from src.tools.diritto_penale import pena_concordata

    fn = getattr(pena_concordata, "fn", pena_concordata)
    return fn(**kw)


# ---------------------------------------------------------------------------
# Driver del sito
# ---------------------------------------------------------------------------

def _durata_giorni(testo: str) -> int:
    """'2 anni, 7 mesi, 3 giorni' -> 933 (anno = 12 mesi, mese = 30 giorni)."""
    t = testo.replace("\xa0", " ")
    anni = re.search(r"(\d+)\s*ann[oi]", t)
    mesi = re.search(r"(\d+)\s*mes[ei]", t)
    giorni = re.search(r"(\d+)\s*giorn[oi]", t)
    assert anni or mesi or giorni, f"durata non riconosciuta: {testo!r}"
    return (
        (int(anni.group(1)) if anni else 0) * 12 * GIORNI_MESE
        + (int(mesi.group(1)) if mesi else 0) * GIORNI_MESE
        + (int(giorni.group(1)) if giorni else 0)
    )


def _sito(page, *, anni=0, mesi=0, giorni=0, riduzioni=2) -> list[tuple[str, str, int]]:
    """Compila il modulo con ``riduzioni`` righe "Riduci 1/3" e restituisce le righe
    [(etichetta, testo, giorni)] della tabella; l'ultima e' la "Pena Finale"."""
    time.sleep(1.5)  # cortesia verso il sito tra una richiesta e l'altra
    goto(page, PAGE)
    page.add_style_tag(content=_HIDE_CMP)
    page.wait_for_timeout(500)
    if anni:
        page.select_option("select[name='Anni']", str(anni))
    if mesi:
        page.select_option("select[name='Mesi']", str(mesi))
    if giorni:
        page.select_option("select[name='Giorni']", str(giorni))
    for i in range(1, riduzioni + 1):
        # il click sul radio non resta selezionato in Chromium headless: si imposta
        # la proprieta' checked via DOM, scegliendo il radio per valore ("-" = riduci).
        page.evaluate(
            "(i) => { const r = document.forms['CalcoloPena']['Operazione(' + i + ')'];"
            " [...r].find(x => x.value === '-').checked = true; }",
            i,
        )
        page.select_option(f"select[name='Frazione({i})']", label="1/3")
    page.evaluate(
        "() => { const f = document.forms['CalcoloPena'];"
        " f.requestSubmit(f.querySelector(\"input[type=submit][name='Operazione']\")); }"
    )
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(2500)
    assert "campi errati" not in page.inner_text("body"), "il sito rifiuta il modulo"
    righe = page.evaluate(
        """() => {
            const t = [...document.querySelectorAll('table')]
                .filter(x => /Pena Finale/.test(x.innerText)).pop();
            if (!t) return null;
            return [...t.querySelectorAll('tr')]
                .map(r => [...r.querySelectorAll('td,th')].map(c => c.innerText.trim()));
        }"""
    )
    assert righe, "tabella dei risultati non trovata"
    out = []
    for r in righe:
        if len(r) >= 4 and r[2] == "=" and r[3]:
            out.append((r[1], r[3].replace("\xa0", " "), _durata_giorni(r[3])))
    assert out and out[-1][0] == "Pena Finale", f"righe inattese: {righe}"
    assert len(out) == riduzioni + 2, f"righe inattese: {out}"  # base + riduzioni + finale
    return out


# ---------------------------------------------------------------------------
# Confronto
# ---------------------------------------------------------------------------

def _confronta(tool: dict, sito: list[tuple[str, str, int]]):
    """Confronta ogni passaggio del tool con la riga del sito, poi la pena finale e gli
    indicatori (soglie di legge applicate alla pena finale del sito)."""
    passi_tool = tool["dettaglio"]
    passi_sito = sito[:-1]  # l'ultima riga ripete il risultato come "Pena Finale"
    assert len(passi_tool) == len(passi_sito), (passi_tool, passi_sito)
    righe, errori = [], []
    for pt, (etichetta, testo, gg) in zip(passi_tool, passi_sito):
        gg_tool = pt["mesi"] * GIORNI_MESE
        diff = gg_tool - gg
        righe.append(
            f"{pt['step']:<45} tool {gg_tool:8.1f} gg | sito {gg:5d} gg ({testo}) | diff {diff:+.1f}"
        )
        if abs(diff) >= TOL_GIORNI:
            errori.append(etichetta)

    gg_tool = tool["pena_finale_mesi"] * GIORNI_MESE
    _, testo, gg_sito = sito[-1]
    diff = gg_tool - gg_sito
    msg = (
        f"pena finale: tool {tool['pena_finale_mesi']} mesi = {gg_tool:.1f} giorni "
        f"({tool['pena_finale_formato']}); sito {testo} = {gg_sito} giorni; "
        f"diff {diff:+.1f} giorni (tolleranza < {TOL_GIORNI})\n" + "\n".join(righe)
    )
    assert not errori, f"passaggi fuori tolleranza {errori}; {msg}"
    assert abs(diff) < TOL_GIORNI, msg

    patteggiabile_sito = gg_sito <= LIMITE_PATTEGGIAMENTO_GG
    sospendibile_sito = gg_sito <= LIMITE_SOSPENSIONE_GG
    assert tool["patteggiamento_possibile"] is patteggiabile_sito, (
        f"patteggiamento_possibile: tool {tool['patteggiamento_possibile']}, "
        f"soglia 5 anni sulla pena del sito ({testo}) -> {patteggiabile_sito}"
    )
    assert tool["sospendibile"] is sospendibile_sito, (
        f"sospendibile: tool {tool['sospendibile']}, "
        f"soglia 2 anni sulla pena del sito ({testo}) -> {sospendibile_sito}"
    )


# ---------------------------------------------------------------------------
# Casi del piano
# ---------------------------------------------------------------------------

def test_tre_anni_generiche_e_rito(page):
    """Piano 1 - tre anni con generiche e rito.

    Atteso (piano): 16 mesi (36 - 1/3 = 24, - 1/3 = 16), patteggiamento_possibile true,
    sospendibile true; sul sito 3 anni con due riduzioni di 1/3 = 1 anno e 4 mesi.
    Norme: art. 62-bis c.p. (e art. 65 n. 3), art. 444 co. 1 c.p.p., art. 163 co. 1 c.p.
    """
    tool = _tool(pena_base_mesi=36)
    sito = _sito(page, anni=3)
    _confronta(tool, sito)


def test_pena_finale_esattamente_cinque_anni(page):
    """Piano 2 (limite) - pena base 135 mesi (11 anni e 3 mesi).

    Atteso (piano): 60 mesi, patteggiamento_possibile true (la pena "non supera cinque
    anni", art. 444 co. 1 c.p.p.), sospendibile false.
    """
    tool = _tool(pena_base_mesi=135)
    sito = _sito(page, anni=11, mesi=3)
    _confronta(tool, sito)


def test_pena_finale_appena_sopra_cinque_anni(page):
    """Piano 3 (limite) - pena base 136 mesi (11 anni e 4 mesi).

    Atteso (piano): 60,44 mesi, patteggiamento_possibile false (art. 444 co. 1 c.p.p.).
    Sul sito, atteso aritmetico: 4080 gg -> 2720 -> 1813,33 troncato a 1813 gg
    (5 anni, 13 giorni).
    """
    tool = _tool(pena_base_mesi=136)
    sito = _sito(page, anni=11, mesi=4)
    _confronta(tool, sito)


def test_pena_finale_esattamente_due_anni(page):
    """Piano 4 (limite) - pena base 54 mesi (4 anni e 6 mesi).

    Atteso (piano): 24 mesi, sospendibile true (pena "non superiore a due anni",
    art. 163 co. 1 c.p.).
    """
    tool = _tool(pena_base_mesi=54)
    sito = _sito(page, anni=4, mesi=6)
    _confronta(tool, sito)


def test_solo_diminuente_rito(page):
    """Piano 5 (opzione) - 37 mesi, senza generiche, con la sola diminuente del rito.

    Atteso (piano): 24,67 mesi, patteggiamento_possibile true, sospendibile false.
    Sul sito una sola riga "Riduci 1/3": 1110 gg -> 740 gg (2 anni, 20 giorni).
    Norma: art. 444 co. 1 c.p.p.
    """
    tool = _tool(pena_base_mesi=37, attenuanti_generiche=False, diminuente_rito=True)
    sito = _sito(page, anni=3, mesi=1, riduzioni=1)
    _confronta(tool, sito)


# ---------------------------------------------------------------------------
# Casi aggiunti
# ---------------------------------------------------------------------------

def test_pena_finale_appena_sopra_due_anni(page):
    """Aggiunto (limite) - 55 mesi (4 anni e 7 mesi): un mese di pena base in piu' del
    caso "esattamente due anni".

    Atteso: 55 x 4/9 = 24,44 mesi (sito: 1650 -> 1100 -> 733 gg = 2 anni, 13 giorni),
    sospendibile false (art. 163 co. 1 c.p.), patteggiamento_possibile true.
    """
    tool = _tool(pena_base_mesi=55)
    sito = _sito(page, anni=4, mesi=7)
    _confronta(tool, sito)


def test_solo_attenuanti_generiche(page):
    """Aggiunto (opzione) - 48 mesi con le sole generiche, senza diminuente del rito
    (diminuente_rito=False).

    Atteso: 48 - 1/3 = 32 mesi (2 anni e 8 mesi), sospendibile false.
    Norma: art. 62-bis c.p., art. 65 n. 3 c.p.
    """
    tool = _tool(pena_base_mesi=48, attenuanti_generiche=True, diminuente_rito=False)
    sito = _sito(page, anni=4, riduzioni=1)
    _confronta(tool, sito)


def test_frazioni_di_giorno_troncate_a_ogni_passaggio(page):
    """Aggiunto (limite di arrotondamento) - pena base 1 anno e 7 giorni (367 gg,
    pena_base_mesi = 367/30), generiche e rito.

    Art. 134 co. 2 c.p.: nelle pene temporanee "non si tien conto delle frazioni di
    giorno". Atteso aritmetico: 367 x 4/9 = 163,11 gg (tool 5,44 mesi = 163,2 gg,
    senza troncamento). Il sito tronca a ogni passaggio: 367 -> 244,67 -> 244 ->
    162,67 -> 162 gg (5 mesi, 12 giorni); troncando solo alla fine sarebbero 163 gg.
    Caso scelto perche' le due frazioni troncate si sommano oltre il giorno.
    """
    tool = _tool(pena_base_mesi=367 / GIORNI_MESE)
    sito = _sito(page, anni=1, giorni=7)
    _confronta(tool, sito)


def test_pena_finale_cinque_anni_e_frazione_di_giorno(page):
    """Aggiunto (limite) - pena base 11 anni, 3 mesi e 1 giorno (4051 gg,
    pena_base_mesi = 4051/30): un giorno di pena base oltre il caso "esattamente cinque
    anni".

    Atteso aritmetico: 4051 x 4/9 = 1800,44 gg; per l'art. 134 co. 2 c.p. ("non si tien
    conto delle frazioni di giorno") la pena e' di 1800 gg = cinque anni esatti, che "non
    supera cinque anni" (art. 444 co. 1 c.p.p.): patteggiamento ammesso. Sito:
    4051 -> 2700,67 -> 2700 -> 1800 gg (5 anni); troncando solo alla fine il risultato e'
    lo stesso. Il tool lavora in mesi continui arrotondati a due decimali: 60,0148 ->
    60,01 mesi > 60, quindi patteggiamento_possibile false.
    """
    tool = _tool(pena_base_mesi=4051 / GIORNI_MESE)
    sito = _sito(page, anni=11, mesi=3, giorni=1)
    _confronta(tool, sito)


def test_pena_finale_due_anni_e_frazione_di_giorno(page):
    """Aggiunto (limite) - pena base 4 anni, 6 mesi e 1 giorno (1621 gg,
    pena_base_mesi = 1621/30): un giorno di pena base oltre il caso "esattamente due
    anni".

    Atteso aritmetico: 1621 x 4/9 = 720,44 gg; senza la frazione di giorno (art. 134
    co. 2 c.p.) la pena e' di 720 gg = due anni, "non superiore a due anni" (art. 163
    co. 1 c.p.): sospendibile. Sito: 1621 -> 1080,67 -> 1080 -> 720 gg (2 anni). Il tool:
    24,0148 -> 24,01 mesi > 24, quindi sospendibile false.
    """
    tool = _tool(pena_base_mesi=1621 / GIORNI_MESE)
    sito = _sito(page, anni=4, mesi=6, giorni=1)
    _confronta(tool, sito)


# ---------------------------------------------------------------------------
# Casi non confrontabili
# ---------------------------------------------------------------------------

def test_diminuente_rito_inferiore_a_un_terzo():
    """Art. 444 co. 1 c.p.p.: la pena e' "diminuita fino a un terzo". Il sito consente
    riduzioni diverse (1/6 o frazione libera), il tool applica sempre il terzo pieno e
    non ha un parametro per una misura inferiore."""
    tool = _tool(pena_base_mesi=36)
    assert tool["pena_finale_mesi"] == 16.0
    pytest.skip(
        "non confrontabile: il tool non consente una diminuente del rito inferiore a 1/3"
    )


# Fase 3: the residual 1 day gap is a convention. The site truncates the fraction of day at
# every step (art. 134 co. 2 c.p. applied step by step); the tool keeps continuous months.

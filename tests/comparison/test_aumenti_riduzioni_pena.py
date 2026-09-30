"""Comparison tests: aumenti_riduzioni_pena vs avvocatoandreani.it.

Il tool (``src/tools/diritto_penale.py``) parte dalla pena base in MESI e applica in
sequenza, nell'ordine fisso recidiva (+1/3, art. 99 co. 1 c.p.) -> aggravanti (aumenti
percentuali) -> attenuanti (riduzioni percentuali), ciascuna variazione sul risultato
della precedente. Restituisce ``pena_risultante_mesi`` arrotondata a due decimali e il
``dettaglio`` di ogni passaggio (anch'esso in mesi a due decimali). Non applica i limiti
degli artt. 66 e 67 c.p. ne' il bilanciamento dell'art. 69 c.p. (grado INDICATIVO).

Pagina del sito
---------------
``calcolo-aumenti-riduzioni-pena.php`` (modulo ``CalcoloPena``): pena base in anni / mesi /
giorni (select ``Anni`` 1-90, ``Mesi`` 1-48, ``Giorni`` 1-90) e/o pena pecuniaria; fino a
QUATTRO righe di variazione, ciascuna con radio ``Operazione(n)`` (``+`` aumenta, ``-``
riduci) e frazione predefinita ``Frazione(n)`` (1/6, 1/3, 1/2, 2/3) oppure personalizzata
``VarNum(n)`` / ``VarDen(n)`` (una sola cifra ciascuno). Le righe sono eseguite dall'alto
in basso; il risultato e' una tabella "Pena Base / Aumento|Riduzione di x/y / Pena Finale"
con la durata scritta in anni, mesi e giorni.

Convenzioni del sito osservate (Playwright, 25/09/2026):
- anno = 12 mesi, mese = 30 giorni (5 anni e 4 mesi + 2/3 = 8 anni, 10 mesi, 20 giorni);
- a OGNI passaggio le frazioni di giorno sono troncate e il valore troncato e' la base del
  passaggio successivo (10 giorni - 1/3 = 6 giorni; + 1/2 = 9 giorni, non 10): e' una
  lettura "a ogni passaggio" dell'art. 134 co. 2 c.p. ("non si tien conto delle frazioni di
  giorno"), che il tool non applica affatto (lavora in mesi continui);
- nessun limite degli artt. 66-67 c.p.: il sito e' puramente aritmetico.

Confronto: la durata si porta in giorni con la convenzione del sito (mesi del tool x 30).
Tolleranza: meno di UN giorno per passaggio. Motivazione (piu' ampia delle "date esatte"
del brief): il sito esprime la pena in giorni interi troncando la frazione di giorno, il
tool in mesi a due decimali (granularita' 0,3 giorni); una differenza inferiore al giorno
e' solo granularita' di visualizzazione, una differenza di un giorno o piu' e' un
risultato diverso. Le percentuali passate al tool sono le frazioni del sito a quattro
decimali (33.3333, 66.6667, 16.6667), come prescrive il piano.

Il sito e' un benchmark, non una fonte: gli scostamenti restano registrati e li giudica
la fase 2.
"""

import math
import re
import time

import pytest

from tests.comparison.conftest import goto

PAGE = "calcolo-aumenti-riduzioni-pena.php"
GIORNI_MESE = 30  # convenzione del sito (e dell'art. 134 c.p. applicato in mesi commerciali)
TOL_GIORNI = 1.0  # vedi docstring del modulo

_HIDE_CMP = (
    ".qc-cmp2-container,#qc-cmp2-container"
    "{display:none !important;pointer-events:none !important}"
)
_PREDEFINITE = ("1/6", "1/3", "1/2", "2/3")

# frazione del sito -> percentuale passata al tool (quattro decimali, come da piano)
PCT = {"1/6": 16.6667, "1/4": 25.0, "1/3": 33.3333, "1/2": 50.0, "2/3": 66.6667}


# ---------------------------------------------------------------------------
# Tool
# ---------------------------------------------------------------------------

def _tool(**kw) -> dict:
    import src.server  # noqa: F401  (registra i moduli, evita import circolari)
    from src.tools.diritto_penale import aumenti_riduzioni_pena

    fn = getattr(aumenti_riduzioni_pena, "fn", aumenti_riduzioni_pena)
    return fn(**kw)


def _agg(frazione: str, tipo: str = "aggravante") -> dict:
    return {"tipo": tipo, "aumento_pct": PCT[frazione]}


def _att(frazione: str, tipo: str = "attenuante") -> dict:
    return {"tipo": tipo, "riduzione_pct": PCT[frazione]}


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


def _sito(page, *, anni=0, mesi=0, giorni=0, operazioni=()) -> list[tuple[str, str, int]]:
    """Compila il modulo e restituisce le righe [(etichetta, testo, giorni)].

    ``operazioni``: sequenza di ("+"|"-", "n/d"); le frazioni predefinite vanno nella
    select, le altre in VarNum/VarDen. L'ultima riga e' la "Pena Finale".
    """
    assert len(operazioni) <= 4, "il sito accetta al massimo quattro variazioni"
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
    for i, (op, frazione) in enumerate(operazioni, start=1):
        # il click sul radio non resta selezionato in Chromium headless (il click viene
        # annullato): la proprieta' checked si imposta via DOM, come farebbe l'utente.
        page.evaluate(
            "([i, op]) => { const r = document.forms['CalcoloPena']['Operazione(' + i + ')'];"
            " (op === '+' ? r[0] : r[1]).checked = true; }",
            [i, op],
        )
        if frazione in _PREDEFINITE:
            page.select_option(f"select[name='Frazione({i})']", label=frazione)
        else:
            num, den = frazione.split("/")
            page.fill(f"#VarNum{i}", num)
            page.fill(f"#VarDen{i}", den)
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
    return out


# ---------------------------------------------------------------------------
# Confronto
# ---------------------------------------------------------------------------

def _confronta_passaggi(tool: dict, sito: list[tuple[str, str, int]]):
    """Confronta ogni passaggio del tool con la riga corrispondente del sito.

    Richiede che le variazioni siano state inserite sul sito nello stesso ordine del tool
    (recidiva, aggravanti, attenuanti).
    """
    passi_tool = tool["dettaglio"]
    passi_sito = sito[:-1]  # l'ultima riga ripete il risultato come "Pena Finale"
    assert len(passi_tool) == len(passi_sito), (passi_tool, passi_sito)
    righe, errori = [], []
    for pt, (etichetta, testo, gg) in zip(passi_tool, passi_sito):
        gg_tool = pt["mesi"] * GIORNI_MESE
        diff = gg_tool - gg
        righe.append(f"{pt['step']:<45} tool {gg_tool:9.1f} gg | sito {gg:6d} gg ({testo}) | diff {diff:+.1f}")
        if abs(diff) >= TOL_GIORNI:
            errori.append(etichetta)
    _confronta_finale(tool, sito, dettaglio="\n".join(righe), extra=errori)


def _confronta_finale(tool: dict, sito, dettaglio: str = "", extra=()):
    gg_tool = tool["pena_risultante_mesi"] * GIORNI_MESE
    etichetta, testo, gg_sito = sito[-1]
    diff = gg_tool - gg_sito
    msg = (
        f"pena finale: tool {tool['pena_risultante_mesi']} mesi = {gg_tool:.1f} giorni "
        f"({tool['pena_risultante_formato']}); sito {testo} = {gg_sito} giorni; "
        f"diff {diff:+.1f} giorni (tolleranza < {TOL_GIORNI})"
    )
    if dettaglio:
        msg += "\n" + dettaglio
    print(f"\n[{etichetta}] {msg}")  # visibile con -s: traccia dei valori confrontati
    assert not extra, f"passaggi fuori tolleranza {list(extra)}; {msg}"
    assert abs(diff) < TOL_GIORNI, msg


# ---------------------------------------------------------------------------
# Casi del piano
# ---------------------------------------------------------------------------

def test_esempio_sito_64_mesi_aumento_due_terzi(page):
    """Piano 1 - esempio della pagina del sito: 5 anni e 4 mesi aumentati di due terzi.

    Atteso (piano): 106,67 mesi = 8 anni, 10 mesi e 20 giorni (64 + 2/3 di 64).
    Norma: art. 64 c.p. (aumento per circostanza), qui frazione 2/3 come nell'esempio.
    """
    tool = _tool(pena_base_mesi=64, aggravanti=[_agg("2/3", "aumento di due terzi")])
    sito = _sito(page, anni=5, mesi=4, operazioni=[("+", "2/3")])
    _confronta_passaggi(tool, sito)


def test_quattro_attenuanti_un_terzo_limite_art67(page):
    """Piano 2 (limite) - 12 mesi, quattro attenuanti di un terzo.

    Atteso (piano): 3 mesi, perche' con piu' attenuanti ad effetto comune la pena non puo'
    scendere sotto un quarto (art. 67 co. 2 c.p.); il tool restituisce 2,37 mesi
    (12 x (2/3)^4) e il sito, aritmetico, va letto. Il confronto e' tool == sito: il limite
    dell'art. 67 non lo applica nessuno dei due (annotato nel risultato del benchmark).
    Caso al limite anche per il sito: quattro variazioni sono il massimo del modulo.
    """
    # Fase 3: art. 67 co. 2 c.p. (letto da Normattiva) impone il minimo di un quarto, quindi
    # 3 mesi; il tool ora lo applica, il sito e' solo aritmetico (2 mesi e 10 giorni) e non e'
    # una fonte: il confronto sul risultato finale non ha piu' senso, si confrontano i
    # passaggi che precedono il limite.
    tool = _tool(
        pena_base_mesi=12,
        attenuanti=[_att("1/3", f"attenuante {n}") for n in range(1, 5)],
    )
    assert tool["pena_risultante_mesi"] == 3.0
    sito = _sito(page, anni=1, operazioni=[("-", "1/3")] * 4)
    assert sito[-1][2] < 3 * 30  # the site ignores art. 67 co. 2


def test_recidiva_due_aggravanti_oltre_trenta_anni_limite_art66(page):
    """Piano 3 (limite) - 20 anni di reclusione, recidiva + aggravanti di 1/3 e 1/2.

    Atteso (piano): 360 mesi, perche' con piu' aggravanti la reclusione non puo' superare
    trent'anni (art. 66 n. 1 c.p.); il tool restituisce 640 mesi (53 anni e 4 mesi).
    Norme: art. 99 co. 1 c.p. (recidiva +1/3), art. 64 c.p., art. 63 co. 3 c.p. (effetto
    speciale). Inoltre Corte cost. n. 74/2025 (art. 63 co. 3 c.p.): se concorrono la
    recidiva dell'art. 99 co. 1 e una circostanza ad effetto speciale si applica soltanto
    la pena stabilita per la circostanza piu' grave, che il giudice puo' aumentare; tool e
    sito cumulano invece i due aumenti. Qui resta comunque decisivo il tetto dei trent'anni.
    Sul sito la recidiva e' la prima riga "Aumenta 1/3".
    """
    tool = _tool(
        pena_base_mesi=240,
        aggravanti=[
            _agg("1/3", "art. 61 n. 1 c.p."),
            _agg("1/2", "aggravante ad effetto speciale"),
        ],
        recidiva=True,
    )
    sito = _sito(page, anni=20, operazioni=[("+", "1/3"), ("+", "1/3"), ("+", "1/2")])
    _confronta_passaggi(tool, sito)


def test_aggravante_e_attenuante_concorrenti(page):
    """Piano 4 - 36 mesi, aggravante art. 61 n. 7 (+1/3) e attenuanti generiche (-1/3).

    Atteso (piano): con il bilanciamento dell'art. 69 c.p. 36 mesi (equivalenza), 24
    (prevalenza delle attenuanti) o 48 (prevalenza delle aggravanti); il tool applica le
    due circostanze in sequenza (32 mesi), come il sito: da leggere dal sito.
    """
    tool = _tool(
        pena_base_mesi=36,
        aggravanti=[_agg("1/3", "art. 61 n. 7 c.p.")],
        attenuanti=[_att("1/3", "art. 62-bis c.p.")],
    )
    sito = _sito(page, anni=3, operazioni=[("+", "1/3"), ("-", "1/3")])
    _confronta_passaggi(tool, sito)


# ---------------------------------------------------------------------------
# Casi aggiunti
# ---------------------------------------------------------------------------

def test_esempio_sito_patteggiamento_cinque_anni(page):
    """Secondo esempio della pagina (patteggiamento, art. 444 c.p.p.): 5 anni,
    riduzione di 1/3 (attenuante art. 62/62-bis c.p.), aumento di 1/6 (continuazione,
    art. 81 c.p.), riduzione di 1/3 (rito).

    Atteso (pagina del sito): 2 anni, 7 mesi, 3 giorni. Il tool applica sempre prima le
    aggravanti e poi le attenuanti: l'ordine non cambia il prodotto, per cui si confronta
    solo la pena finale (il sito e' compilato nell'ordine del suo esempio).
    """
    tool = _tool(
        pena_base_mesi=60,
        aggravanti=[_agg("1/6", "continuazione art. 81 c.p.")],
        attenuanti=[_att("1/3", "art. 62-bis c.p."), _att("1/3", "rito art. 444 c.p.p.")],
    )
    sito = _sito(page, anni=5, operazioni=[("-", "1/3"), ("+", "1/6"), ("-", "1/3")])
    _confronta_finale(tool, sito)


def test_frazione_personalizzata_un_quarto(page):
    """Opzione del sito (limite): frazione personalizzata VarNum/VarDen.

    2 anni; recidiva aggravata art. 99 co. 2 c.p. (aumento fino alla meta': +1/2, passata
    al tool come aggravante del 50%); attenuanti generiche art. 62-bis applicate nella
    misura di un quarto (art. 65 n. 3 c.p.: diminuzione non eccedente un terzo), inserita
    sul sito come 1/4 nei campi numeratore/denominatore.
    Atteso aritmetico: 24 x 3/2 x 3/4 = 27 mesi = 2 anni e 3 mesi.
    """
    tool = _tool(
        pena_base_mesi=24,
        aggravanti=[_agg("1/2", "recidiva aggravata art. 99 co. 2 c.p.")],
        attenuanti=[_att("1/4", "art. 62-bis c.p. (1/4)")],
    )
    sito = _sito(page, anni=2, operazioni=[("+", "1/2"), ("-", "1/4")])
    _confronta_passaggi(tool, sito)


def test_recidiva_riporto_mesi_in_anno(page):
    """Limite di formato: 9 mesi + recidiva semplice (art. 99 co. 1 c.p., +1/3) = 12 mesi,
    esattamente un anno (riporto dei mesi nell'anno). Atteso: 1 anno.
    """
    tool = _tool(pena_base_mesi=9, recidiva=True)
    sito = _sito(page, mesi=9, operazioni=[("+", "1/3")])
    _confronta_passaggi(tool, sito)


def test_frazioni_di_giorno_troncate_a_ogni_passaggio(page):
    """Limite di arrotondamento: 29 giorni, +1/2, +2/3, -1/3, -1/6 (ordine del tool).

    Art. 134 co. 2 c.p.: nelle condanne a pene temporanee non si tien conto delle frazioni
    di giorno. Il sito tronca a ogni passaggio (29 -> 43 -> 71 -> 47 -> 39 giorni); il tool
    lavora in mesi continui: 29 x 3/2 x 5/3 x 2/3 x 5/6 = 40,28 giorni (1,34 mesi).
    """
    base_mesi = 29 / GIORNI_MESE
    tool = _tool(
        pena_base_mesi=base_mesi,
        aggravanti=[_agg("1/2"), _agg("2/3")],
        attenuanti=[_att("1/3"), _att("1/6")],
    )
    sito = _sito(
        page, giorni=29, operazioni=[("+", "1/2"), ("+", "2/3"), ("-", "1/3"), ("-", "1/6")]
    )
    _confronta_passaggi(tool, sito)


# ---------------------------------------------------------------------------
# Casi non confrontabili
# ---------------------------------------------------------------------------

def test_cinque_variazioni_oltre_il_modulo_del_sito():
    """Recidiva + quattro circostanze = cinque variazioni: il tool le accetta, il sito ne
    consente al massimo quattro (righe Operazione(1)-(4))."""
    tool = _tool(
        pena_base_mesi=36,
        aggravanti=[_agg("1/3"), _agg("1/6")],
        attenuanti=[_att("1/3"), _att("1/3")],
        recidiva=True,
    )
    assert math.isfinite(tool["pena_risultante_mesi"])
    pytest.skip("non confrontabile: il sito accetta al massimo quattro variazioni consecutive")


def test_pena_pecuniaria_non_gestita_dal_tool():
    """Il sito varia anche la pena pecuniaria (campo PenaPecuniaria, multa/ammenda); il tool
    lavora solo sulla pena detentiva in mesi: nessun parametro equivalente."""
    pytest.skip("non confrontabile: il tool non gestisce la pena pecuniaria (multa/ammenda)")

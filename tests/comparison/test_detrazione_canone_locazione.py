"""Benchmark fase 1: detrazione_canone_locazione vs avvocatoandreani.it.

Pagina: https://www.avvocatoandreani.it/servizi/calcolo-detrazione-canone-locazione.php
Modulo ``DetrazioneLocazione`` (POST, pulsante ``#button1``):
- ``RedditoComplessivoDetrazione``: reddito per detrazioni (rigo RN1 col. 1);
- ``TipoDetrazione``: 1 = regime ordinario (art. 16 co. 01 TUIR, tool ``libero``),
  2 = regime convenzionale (co. 1, tool ``concordato``), 3 = giovani tra 20 e 30
  anni (co. 1-ter, tool ``giovani_under31``), 5 = trasferimento per motivi di
  lavoro (co. 1-bis, NON offerto dal tool);
- date di inizio e fine locazione (solo anno 2025) e percentuale di spettanza
  (100% / 50% / altra), lasciate ai valori di default.
Il sito non chiede il canone: per i giovani applica sempre il minimo di 991,60.

Risultato: tabella "SVILUPPO del CALCOLO - Periodo di imposta 2025" con
"Detrazione teorica complessiva" (importo annuo pieno, confrontabile con il tool),
"Numero giorni" (RP71 col. 2), "Detrazione rapportata ai giorni e alla
percentuale di spettanza" e "RN12 Col.1 Detrazione canone spettante" (euro interi).

Il tool restituisce l'importo annuo pieno senza rapportarlo al periodo (art. 16
co. 1-quinquies) ne' alla quota di contitolarita' (co. 1-quater): il confronto
e' quindi sulla "Detrazione teorica complessiva". Gli importi di art. 16 non
dipendono dall'anno (co. 01 e 1-ter invariati dal 2021, soglie dal 1997), per
cui il periodo d'imposta 2025 del sito vale anche per il tool.

Convenzioni osservate sul sito (non asserite, riportate per la fase 2):
- numero giorni = data fine - data inizio, senza contare il giorno iniziale:
  01/01-31/12/2025 -> 364 (non 365), 01/07-31/12/2025 -> 183 (non 184); la
  detrazione rapportata e' /365 (300 x 364/365 = 299,18);
- RN12 arrotondato all'euro (299,18 -> 299; 988,88 -> 989).

Tolleranza: 0,01 euro (brief). Il testo di art. 16 TUIR vigente e' stato letto
con cite_law il 2026-09-25.
"""

import re

import pytest

from tests.comparison.conftest import accept_cookies, assert_close, extract_amount, goto

PAGE = "calcolo-detrazione-canone-locazione.php"
TOL = 0.01

# Codici del select TipoDetrazione sul sito.
SITO_TIPO = {"libero": "1", "concordato": "2", "giovani_under31": "3"}


def _tool(reddito, tipo):
    import src.server  # noqa: F401  (registra i moduli ed evita import circolari)
    from src.tools.dichiarazione_redditi import detrazione_canone_locazione

    fn = getattr(detrazione_canone_locazione, "fn", detrazione_canone_locazione)
    return fn(reddito_complessivo=reddito, tipo_contratto=tipo)


def _it(value: float) -> str:
    """15493.71 -> '15493,71' (formato accettato dal campo del sito)."""
    return f"{value:.2f}".replace(".", ",")


def _sito(page, reddito: float, tipo_sito: str) -> dict:
    goto(page, PAGE, wait_ms=1500)
    page.fill("#RedditoComplessivoDetrazione", _it(reddito))
    page.select_option("#TipoDetrazione", tipo_sito)
    # Il banner Quantcast ricompare dopo la rimozione fatta da goto() (che scatta
    # subito dopo domcontentloaded) e il pulsante e' sotto la piega: un click
    # forzato per coordinate non invia il modulo. Si rimuove di nuovo il banner
    # e si invia il modulo con il click DOM del pulsante, attendendo la POST.
    accept_cookies(page)
    with page.expect_navigation(wait_until="domcontentloaded", timeout=60000):
        page.evaluate('document.getElementById("button1").click()')
    page.wait_for_timeout(1500)
    testo = ""
    for t in page.query_selector_all("table"):
        txt = t.inner_text()
        if "SVILUPPO del CALCOLO" in txt:
            testo = txt
            break
    assert testo, "il sito non ha prodotto la tabella 'SVILUPPO del CALCOLO'"
    giorni = re.search(r"Numero giorni\s+(\d+)", testo)
    return {
        "teorica": extract_amount(testo, "Detrazione teorica complessiva"),
        "rn12": extract_amount(testo, "Detrazione canone spettante"),
        "giorni": int(giorni.group(1)) if giorni else None,
        "testo": testo,
    }


# (id, reddito, tipo tool, atteso di norma, commento)
CASI = [
    # Piano: libero al limite della prima soglia. Atteso 300,00 (art. 16 co. 01
    # lett. a TUIR: reddito non superiore a 15.493,71).
    ("libero_15493_71", 15493.71, "libero"),
    # Piano: un centesimo oltre la prima soglia. Atteso 150,00 (co. 01 lett. b).
    ("libero_15493_72", 15493.72, "libero"),
    # Limite: libero alla seconda soglia. Atteso 150,00 (co. 01 lett. b: non
    # superiore a 30.987,41).
    ("libero_30987_41", 30987.41, "libero"),
    # Limite: libero oltre la seconda soglia. Atteso 0,00 (co. 01).
    ("libero_30987_42", 30987.42, "libero"),
    # Limite: concordato alla prima soglia. Atteso 495,80 (co. 1 lett. a: lire
    # 960.000 = 495,80 euro).
    ("concordato_15493_71", 15493.71, "concordato"),
    # Limite: concordato un centesimo oltre la prima soglia. Atteso 247,90
    # (co. 1 lett. b: lire 480.000).
    ("concordato_15493_72", 15493.72, "concordato"),
    # Limite: concordato alla seconda soglia. Atteso 247,90 (co. 1 lett. b).
    ("concordato_30987_41", 30987.41, "concordato"),
    # Piano: concordato oltre la seconda soglia. Atteso 0,00 (co. 1).
    ("concordato_30987_42", 30987.42, "concordato"),
    # Limite: giovani un centesimo oltre la soglia unica. Atteso 0,00 per il
    # co. 1-ter (reddito non superiore a 15.493,71); resta salva la scelta del
    # co. 01 (150,00) ex co. 1-quater, che ne' sito ne' tool propongono qui.
    ("giovani_15493_72", 15493.72, "giovani_under31"),
]


@pytest.mark.parametrize("reddito,tipo", [(c[1], c[2]) for c in CASI], ids=[c[0] for c in CASI])
def test_detrazione_scaglioni(page, reddito, tipo):
    r = _tool(reddito, tipo)
    assert "errore" not in r, r
    s = _sito(page, reddito, SITO_TIPO[tipo])
    assert s["teorica"] is not None, s["testo"]
    assert_close(r["detrazione"], s["teorica"], tolerance=TOL, label=f"{tipo} {reddito}")


def test_giovani_under31_reddito_12000(page):
    """Piano: giovane under 31, reddito 12.000, canone annuo 6.000.

    Atteso di norma (art. 16 co. 1-ter TUIR, mod. L. 178/2020): 991,60 oppure,
    se superiore, il 20% del canone entro 2.000 -> con canone 6.000: 1.200,00.
    Il sito non ha il campo del canone e restituisce il minimo 991,60 (corretto
    solo per canoni fino a 4.958 euro); il tool non chiede il canone e
    restituisce il massimo 2.000 (corretto solo per canoni da 10.000 euro).
    Lo scostamento e' genuino e resta un fallimento per la fase 2.
    """
    r = _tool(12000, "giovani_under31")
    assert "errore" not in r, r
    s = _sito(page, 12000, SITO_TIPO["giovani_under31"])
    assert s["teorica"] is not None, s["testo"]
    assert_close(r["detrazione"], s["teorica"], tolerance=TOL, label="giovani 12000")


def test_trasferimento_lavoro_non_offerto_dal_tool(page):
    """Opzione enumerata del sito "Trasferimento per motivi di lavoro" (valore 5).

    Atteso di norma (art. 16 co. 1-bis TUIR): lire 1.920.000 = 991,60 con
    reddito fino a 15.493,71 (lire 30 milioni). Il tool non ha questo tipo di
    contratto (accetta solo libero | concordato | giovani_under31): caso non
    confrontabile. Si interroga il sito una volta per registrarne il valore.
    """
    r = _tool(12000, "trasferimento_lavoro")
    assert "errore" in r
    s = _sito(page, 12000, "5")
    pytest.skip(
        "tool privo del co. 1-bis (trasferimento per lavoro): "
        f"sito teorica={s['teorica']}, errore tool={r['errore']!r}"
    )

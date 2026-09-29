"""Comparison tests: cerca_ufficio_giudiziario vs avvocatoandreani.it.

Site page: servizi/ricerca-uffici-giudiziari-per-comune.php ("Ricerca uffici giudiziari
competenti per Comune"). The site uses the ISTAT list of comuni and the Ministry of
Justice judicial geography; for the selected comune it lists the competent offices
(Giudice di Pace, Tribunale, Corte d'Appello, Corte di Assise, UNEP, Procura). The comune
must be picked from the jQuery-UI autocomplete (it fills the ISTAT code and submits), so
the driver types the name, waits for the menu and clicks the exact ISTAT label.

Tool: src/tools/atti_giudiziari.py::cerca_ufficio_giudiziario, table
src/data/tribunali_competenti.json (102 capoluoghi, _vintage "da_verificare", grado
INDICATIVO). Exact key match first; otherwise a substring match in both directions
(`key in k or k in key`) returned as "suggerimenti" with trovato=False.

Norms: R.D. 30 gennaio 1941 n. 12 (ordinamento giudiziario) and its Tabella A of the
circondari, as redrawn by D.Lgs. 7 settembre 2012 n. 155 (tribunali) and D.Lgs.
7 settembre 2012 n. 156 (uffici del giudice di pace), with the later postponements of the
suppression of the Abruzzo tribunals (Vasto among them); L. 21 novembre 1991 n. 374
(giudice di pace).

Comparison rule: the office the tool gives as competent (`ufficio_competente` when
trovato=True, nothing otherwise) must equal the office the site lists for the same comune
and type. Office names are compared after normalisation only (case, accents, the elision
"dell'AQUILA" == "di L'Aquila", the accent written as apostrophe "TORTOLI'"): no other
tolerance. The site is a benchmark, not a source: a genuine difference stays a failing test.
"""

import re
import time
import unicodedata

import pytest

_URL = "https://www.avvocatoandreani.it/servizi/ricerca-uffici-giudiziari-per-comune.php"

# Header of each office block in the result (div#Hdr-N inside #R-Output).
_HDR = "#R-Output div[id^='Hdr-']"

# Which site header corresponds to each tool `tipo`. "corte_appello" is not a type the
# tool accepts, but the site shows that office, so the plan's case can be compared.
_PREFISSO_TIPO = {
    "tribunale": r"^Tribunale (di|del|della|dell') ?",
    "giudice_pace": r"^Giudice di Pace (di|del|della|dell') ?",
    "corte_appello": r"^Corte d'Appello (di|del|della|dell') ?",
}


# The `tipo` values the tool documents; anything else is outside its enumeration.
_TIPI_TOOL = {"tribunale", "giudice_pace"}


def _norm(s: str | None) -> str | None:
    """Lower case, no accents, "dell'X" -> "di l'x", accent-apostrophe dropped."""
    if s is None:
        return None
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.lower().replace("’", "'")
    s = re.sub(r"\bdell'", "di l'", s)
    s = re.sub(r"(\w)'(?=\s|$)", r"\1", s)
    return " ".join(s.split())


def _chiudi_consenso(page) -> None:
    """Close the Quantcast consent dialog with its X (continue without accepting).

    The dialog appears a few seconds after load, traps the focus and swallows the typing
    in the Comune field, so it must be gone before driving the autocomplete.
    """
    try:
        page.wait_for_selector("#qc-cmp2-ui", timeout=10000)
        page.click("#qc-cmp2-ui .qc-cmp2-close-icon", timeout=5000)
        page.wait_for_selector("#qc-cmp2-ui", state="detached", timeout=5000)
    except Exception:
        page.evaluate(
            'document.querySelectorAll("#qc-cmp2-container, .qc-cmp2-container")'
            ".forEach(el => el.remove())"
        )


def _uffici_sito(page, digitato: str, etichetta: str) -> list[str]:
    """Search a comune on the site and return the headers of the competent offices."""
    time.sleep(2)  # be gentle with the site (and with its "troppe ricerche" throttle)
    page.goto(_URL, timeout=60000, wait_until="domcontentloaded")
    _chiudi_consenso(page)
    page.wait_for_function(
        "() => window.jQuery && jQuery('#Comune').data('ui-autocomplete')", timeout=20000
    )
    for _ in range(2):
        page.fill("#Comune", "")
        page.locator("#Comune").press_sequentially(digitato, delay=80)
        page.wait_for_selector("ul.ui-autocomplete li", state="visible", timeout=15000)
        voce = page.locator("ul.ui-autocomplete li .ui-menu-item-wrapper").filter(
            has_text=re.compile(r"^\s*" + re.escape(etichetta) + r"\s*$")
        )
        assert voce.count() == 1, (
            f"{etichetta!r} non tra i suggerimenti del sito: "
            f"{page.locator('ul.ui-autocomplete li').all_inner_texts()}"
        )
        with page.expect_navigation(wait_until="domcontentloaded", timeout=30000):
            voce.first.click()
        page.wait_for_timeout(1500)
        uffici = [h.strip() for h in page.locator(_HDR).all_inner_texts()]
        if uffici:
            return uffici
        if "Troppe ricerche consecutive" not in page.inner_text("body"):
            break
        # Throttled: the page counts down and then re-enables the form.
        page.wait_for_selector("text=Adesso puoi effettuare la ricerca", timeout=120000)
        _chiudi_consenso(page)
    pytest.fail(f"Il sito non ha restituito uffici per {etichetta!r}")


def _ufficio_sito(uffici: list[str], tipo: str) -> str:
    trovati = [u for u in uffici if re.match(_PREFISSO_TIPO[tipo], u, re.IGNORECASE)]
    assert len(trovati) == 1, f"uffici '{tipo}' sul sito: {trovati} (tutti: {uffici})"
    return trovati[0]


def _tool(comune: str, tipo: str) -> dict:
    import src.server  # noqa: F401  registers every module (avoids circular imports)
    from src.tools.atti_giudiziari import cerca_ufficio_giudiziario

    fn = getattr(cerca_ufficio_giudiziario, "fn", cerca_ufficio_giudiziario)
    return fn(comune=comune, tipo=tipo)


# (id, comune passed to the tool, tipo, text typed on the site, exact ISTAT label on the site)
_CASI = [
    # Piano 1 - capoluogo in tabella. Atteso: "Tribunale di Monza (trovato)".
    # Circondario di Monza (Tabella A R.D. 12/1941, D.Lgs. 155/2012).
    pytest.param("Monza", "tribunale", "Monza", "Monza (MB)", id="monza-tribunale"),
    # Piano 2 - giudice di pace di un capoluogo. Atteso: "Giudice di Pace di Roma".
    # D.Lgs. 156/2012 (sedi GdP); L. 374/1991.
    pytest.param("Roma", "giudice_pace", "Roma", "Roma (RM)", id="roma-giudice_pace"),
    # Piano 3 - LIMITE (falso positivo della ricerca parziale: "torino" in "torino di
    # sangro"). Atteso: "da leggere dal sito (ufficio abruzzese); il tool suggerisce il
    # Tribunale di Torino, certamente errato". Circondario di Vasto (Tabella A; la
    # soppressione dei tribunali abruzzesi ex D.Lgs. 155/2012 e' stata rinviata).
    pytest.param(
        "Torino di Sangro", "tribunale", "Torino di Sangro", "Torino di Sangro (CH)",
        id="torino_di_sangro-tribunale",
    ),
    # Piano 4 - LIMITE (falso positivo: "bari" in "bari sardo"). Atteso: "da leggere dal
    # sito (atteso il Tribunale di Lanusei); il tool suggerisce il Tribunale di Bari".
    # Circondario di Lanusei (Tabella A, D.Lgs. 155/2012).
    pytest.param(
        "Bari Sardo", "tribunale", "Bari Sardo", "Bari Sardo (NU)", id="bari_sardo-tribunale"
    ),
    # Piano 5 - comune non capoluogo. Atteso: "da leggere dal sito (atteso il Tribunale di
    # Monza); il tool non trova il comune". Circondario di Monza (Tabella A).
    pytest.param(
        "Sesto San Giovanni", "tribunale", "Sesto San Giovanni", "Sesto San Giovanni (MI)",
        id="sesto_san_giovanni-tribunale",
    ),
    # Piano 6 - LIMITE (opzione enumerata fuori elenco: tipo="corte_appello"). Atteso:
    # "errore per tipo non ammesso (o Corte d'appello di Milano); il tool restituisce il
    # Tribunale di Milano". Distretto di Corte d'appello di Milano (Tabella A R.D. 12/1941).
    pytest.param(
        "Milano", "corte_appello", "Milano", "Milano (MI)", id="milano-corte_appello"
    ),
    # Aggiunto - LIMITE (capoluogo il cui tribunale ha sede in altro comune): Caserta ricade
    # nel circondario di Santa Maria Capua Vetere (Tabella A, D.Lgs. 155/2012).
    pytest.param("Caserta", "tribunale", "Caserta", "Caserta (CE)", id="caserta-tribunale"),
    # Aggiunto - LIMITE (stessa citta', l'altro valore enumerato di `tipo` cambia sede):
    # Giudice di Pace di Caserta (D.Lgs. 156/2012).
    pytest.param(
        "Caserta", "giudice_pace", "Caserta", "Caserta (CE)", id="caserta-giudice_pace"
    ),
    # Aggiunto - denominazione con elisione: il sito scrive "Tribunale dell'AQUILA", il
    # tool "Tribunale di L'Aquila" (confronto dopo normalizzazione). Tabella A.
    pytest.param("L'Aquila", "tribunale", "L'Aquila", "L'Aquila (AQ)", id="laquila-tribunale"),
    # Aggiunto - capoluogo con il nome abbreviato usato come chiave della tabella del tool
    # ("reggio emilia"); sul sito il comune ha la denominazione ISTAT. Tabella A.
    pytest.param(
        "Reggio Emilia", "tribunale", "Reggio nell", "Reggio nell'Emilia (RE)",
        id="reggio_emilia-tribunale",
    ),
    # Aggiunto - LIMITE (denominazione ufficiale ISTAT "Reggio nell'Emilia", la stessa che
    # il sito richiede): la chiave del tool e' "reggio emilia". Tabella A.
    pytest.param(
        "Reggio nell'Emilia", "tribunale", "Reggio nell", "Reggio nell'Emilia (RE)",
        id="reggio_nell_emilia_istat-tribunale",
    ),
    # Aggiunto dalle note del piano - LIMITE (falso positivo: "lucca" in "lucca sicula").
    # Atteso dal sito un tribunale siciliano (circondario di Sciacca, Tabella A).
    pytest.param(
        "Lucca Sicula", "tribunale", "Lucca Sicula", "Lucca Sicula (AG)",
        id="lucca_sicula-tribunale",
    ),
    # Aggiunto dalle note del piano - LIMITE (falso positivo: "roma" in "romano di
    # lombardia"). Circondario di Bergamo (Tabella A, D.Lgs. 155/2012).
    pytest.param(
        "Romano di Lombardia", "tribunale", "Romano di Lombardia", "Romano di Lombardia (BG)",
        id="romano_di_lombardia-tribunale",
    ),
    # Aggiunto dalle note del piano - LIMITE (falso positivo: "pisa" in "pisano").
    # Pisano (NO) ricade nel circondario di Verbania (Tabella A, D.Lgs. 155/2012).
    pytest.param("Pisano", "tribunale", "Pisano", "Pisano (NO)", id="pisano-tribunale"),
    # Aggiunto - LIMITE (nuovo falso positivo con accento: "forli" in "forli del sannio").
    # Forli' del Sannio (IS) ricade nel circondario di Isernia (Tabella A).
    pytest.param(
        "Forlì del Sannio", "tribunale", "Forli del Sannio", "Forlì del Sannio (IS)",
        id="forli_del_sannio-tribunale",
    ),
]


@pytest.mark.parametrize("comune,tipo,digitato,etichetta", _CASI)
def test_ufficio_competente(page, comune, tipo, digitato, etichetta):
    r = _tool(comune, tipo)
    if tipo not in _TIPI_TOOL and "errore" in r:
        # Plan case 6 accepts a refusal of the non-enumerated type ("errore per tipo non
        # ammesso"): nothing to compare with the site in that case.
        return
    assert "errore" not in r, f"errore del tool: {r}"
    tool_uff = r.get("ufficio_competente") if r.get("trovato") else None
    suggerimenti = [s.get("ufficio") for s in r.get("suggerimenti", [])]

    sito_uff = _ufficio_sito(_uffici_sito(page, digitato, etichetta), tipo)

    assert _norm(tool_uff) == _norm(sito_uff), (
        f"{comune} [{tipo}]: tool={tool_uff!r} (trovato={r.get('trovato')}, "
        f"suggerimenti={suggerimenti}) sito={sito_uff!r}"
    )

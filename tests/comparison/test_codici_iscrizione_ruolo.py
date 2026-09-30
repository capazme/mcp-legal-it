"""Comparison tests: codici_iscrizione_ruolo vs avvocatoandreani.it/servizi/ricerca-codici-iscrizione-ruolo-cause.php.

Fonte: provvedimenti DGSIA / Ministero della Giustizia, elenco degli oggetti dei giudizi per
materia (codici oggetto della nota di iscrizione a ruolo delle cause civili; il _vintage
della tabella cita "D.M. 32/2012 e provvedimenti DGSIA", estremo non verificato in questo
confronto). Il tool legge ``src/data/codici_ruolo.json`` (_vintage manuale al
19/09/2026): un SOTTOINSIEME di 89 voci raggruppate sotto etichette di materia proprie del
tool ("locazione", "responsabilità", "proprietà", ...), non quelle dell'indice ministeriale.

Semantica confrontata
---------------------
Il tool restituisce le voci della sua tabella per cui ``keyword in materia`` oppure
``keyword in descrizione.lower()`` (sottostringa, sensibile agli accenti).

Il sito ha due strumenti: la ricerca testuale sulle descrizioni degli oggetti (parti di
parola ammesse, nessuna distinzione tra maiuscole/minuscole ne' tra vocali accentate e non
accentate, caratteri non alfanumerici ignorati) e l'"Indice delle Materie" ministeriale.
La ricerca testuale NON cerca nei nomi delle materie (verificato: "responsabilita" non
restituisce 145001 "Solo danni a cose", che pure sta nella materia "Responsabilita'
extracontrattuale").

L'equivalente sul sito della semantica del tool ("materia O descrizione") e' quindi:
    ricerca testuale con "** Tutte le Materie **" e opzione "Frase esatta" (= sottostringa
    unica, come il tool)
  U elenco completo di ogni materia ministeriale il cui nome contiene la parola chiave
    (confronto senza accenti, come dichiara il sito)
ristretto ai codici presenti nella tabella del tool (il tool e' dichiaratamente un
sottoinsieme: le voci che il sito trova fuori dalla tabella non sono uno scostamento del
motore di ricerca ma di copertura, e sono riportate solo nei messaggi).

Asserzione: insieme dei codici del tool == insieme atteso dal sito (confronto esatto), e per
i codici comuni descrizione del tool == descrizione del sito a meno di maiuscole/minuscole,
spazi, accenti e apostrofi usati come accento ("responsabilità" == "responsabilita'"): il
sito stesso dichiara di non distinguere le vocali accentate, e l'elenco ministeriale scrive
gli accenti come apostrofi ASCII. Le varianti ortografiche restano visibili nel report.

Il sito e' un benchmark, non una fonte: gli scostamenti restano registrati come tali.
"""

import re
import unicodedata

import pytest

from tests.comparison.conftest import goto

_PAGE = "ricerca-codici-iscrizione-ruolo-cause.php"
_FORM = "form#RicercaCodiciIscrizioneRuolo"

# Estrae dalla pagina dei risultati le righe (materia ministeriale, descrizione, codice).
# Struttura: <div class="mt20"><table class="Boxed w100"> con <th> = materia e
# <td id="oggNNNNNN"> = codice.
_PARSE_JS = r"""
() => {
  const out = []; let materia = null;
  for (const t of document.querySelectorAll('div.mt20 table.Boxed.w100')) {
    for (const tr of t.querySelectorAll('tr')) {
      const th = tr.querySelector('th');
      if (th) { materia = th.innerText.trim(); continue; }
      const cell = tr.querySelector('td[id^="ogg"]');
      if (!cell) continue;
      out.push({materia, descrizione: tr.querySelector('td').innerText.trim(), codice: cell.id.slice(3)});
    }
  }
  return out;
}
"""


def _norm(s: str) -> str:
    """Minuscole, senza accenti, senza apostrofi-accento, spazi compattati."""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r"[’'`]", "", s.lower())
    return " ".join(s.split())


def _tool(materia: str) -> dict[str, dict]:
    import src.server  # noqa: F401  registra i moduli (evita import circolari)
    from src.tools.atti_giudiziari import codici_iscrizione_ruolo

    fn = getattr(codici_iscrizione_ruolo, "fn", codici_iscrizione_ruolo)
    r = fn(materia=materia)
    assert "errore" not in r, r
    assert r["totale"] == len(r["risultati"])
    return {c["codice"]: c for c in r["risultati"]}


def _table_codes() -> set[str]:
    import src.server  # noqa: F401
    from src.tools.atti_giudiziari import _CODICI_RUOLO

    return {c["codice"] for c in _CODICI_RUOLO}


def _ensure_form(page):
    if page.locator(_FORM).count() == 0:
        goto(page, _PAGE, wait_ms=1500)
    assert page.locator(_FORM).count() == 1, "modulo di ricerca non trovato sul sito"


def _site_materie(page) -> list[tuple[str, str]]:
    _ensure_form(page)
    return page.evaluate(
        f"""() => Array.from(document.querySelectorAll("{_FORM} select[name='idmenu'] option"))
                .filter(o => o.value !== '0').map(o => [o.value, o.textContent.trim()])"""
    )


def _site_search(page, text: str = "", mode: str = "3", idmenu: str = "0") -> list[dict]:
    """Ricerca sul sito. mode: 1 = Tutte le parole, 2 = Qualsiasi parola, 3 = Frase esatta."""
    _ensure_form(page)
    page.evaluate(
        """([t, m, i]) => { const f = document.getElementById('RicercaCodiciIscrizioneRuolo');
            f.Ricerca.value = t; f.idmenu.value = i;
            for (const r of f.querySelectorAll("input[name='SearchMode']")) r.checked = (r.value === m); }""",
        [text, mode, idmenu],
    )
    # I radio hanno onchange=submitform() e il click sul pulsante e' coperto dalla
    # pubblicita': si invia il modulo via requestSubmit con il pulsante CERCA come submitter.
    with page.expect_navigation(wait_until="domcontentloaded", timeout=60000):
        page.evaluate(
            "() => { const f = document.getElementById('RicercaCodiciIscrizioneRuolo');"
            " f.requestSubmit(f.querySelector('input[name=CERCA]')); }"
        )
    page.wait_for_timeout(1500)
    assert page.url.endswith("#Res"), f"invio del modulo non riuscito: {page.url}"
    return page.evaluate(_PARSE_JS)


def _site_expected(page, keyword: str) -> tuple[dict[str, dict], dict]:
    """Codici attesi dal sito (semantica materia O descrizione) ristretti alla tabella del tool."""
    materie = [(v, t) for v, t in _site_materie(page) if _norm(keyword) in _norm(t)]
    rows = _site_search(page, keyword, mode="3")
    for value, _text in materie:
        page.wait_for_timeout(1500)
        rows += _site_search(page, "", idmenu=value)
    table = _table_codes()
    all_site = {r["codice"]: r for r in rows}
    expected = {c: r for c, r in all_site.items() if c in table}
    info = {
        "materie_sito_corrispondenti": [t for _v, t in materie],
        "codici_sito_totali": sorted(all_site),
        "codici_sito_fuori_tabella": sorted(set(all_site) - table),
    }
    return expected, info


def _compare(page, keyword: str):
    tool = _tool(keyword)
    site, info = _site_expected(page, keyword)
    mancanti = sorted(set(site) - set(tool))
    in_piu = sorted(set(tool) - set(site))
    desc_diverse = {
        c: (tool[c]["descrizione"], site[c]["descrizione"])
        for c in sorted(set(tool) & set(site))
        if _norm(tool[c]["descrizione"]) != _norm(site[c]["descrizione"])
    }
    varianti = {
        c: (tool[c]["descrizione"], site[c]["descrizione"])
        for c in sorted(set(tool) & set(site))
        if tool[c]["descrizione"] != site[c]["descrizione"] and c not in desc_diverse
    }
    print(
        f"\n[{keyword!r}] tool={sorted(tool)} ({len(tool)}) sito={sorted(site)} ({len(site)}) "
        f"mancanti={mancanti} in_piu={in_piu} info={info} varianti_ortografiche={varianti}"
    )
    assert not mancanti and not in_piu and not desc_diverse, (
        f"{keyword!r}: tool {len(tool)} codici, sito {len(site)} (nella tabella del tool); "
        f"mancanti nel tool={mancanti}; in piu' nel tool={in_piu}; "
        f"descrizioni diverse={desc_diverse}; materie del sito usate={info['materie_sito_corrispondenti']}"
    )
    return tool, site, info


class TestCodiciIscrizioneRuolo:
    def test_sfratto(self, page):
        """Piano: 5 codici 030001, 030002, 030011, 030012, 030021, descrizioni identiche al sito.
        Norma: codici oggetto DGSIA; licenza e sfratto per finita locazione, per morosita' e per
        cessazione della locazione d'opera, artt. 657, 658 e 659 c.p.c.

        Sul sito "sfratto" coincide anche con la materia "Procedimento per convalida di
        sfratto" (gli stessi 5 codici). Fuori tabella il sito trova 144201, 511010, 511011,
        511100 (copertura, non motore di ricerca).
        """
        tool, site, _ = _compare(page, "sfratto")
        assert sorted(tool) == ["030001", "030002", "030011", "030012", "030021"]

    def test_responsabilita_senza_accento(self, page):
        """Piano: 11 codici (145001, 145002, 145003, 145011, 145012, 145013, 145021, 145999,
        151110, 152110, 153110); il tool ne restituisce 6.
        Norma: codici oggetto DGSIA; responsabilita' extracontrattuale, artt. 2043-2052 c.c.;
        azioni di responsabilita' contro gli organi sociali (151110, 152110, 153110), artt.
        2392 ss. c.c.

        Sul sito: ricerca testuale (8 voci della tabella) + materia "Responsabilita'
        extracontrattuale" (8 voci della tabella) = 11. Il tool e' sensibile agli accenti:
        "responsabilita" non trova la sua materia "responsabilità" (145001-145003) ne' le
        descrizioni scritte con l'accento (152110, 153110). Parola chiave suggerita dal
        docstring del tool.
        """
        _compare(page, "responsabilita")

    def test_proprieta_senza_accento(self, page):
        """Piano: 9 codici della materia "proprietà" del tool (130001, 130011, 130021, 130031,
        130032, 130041, 131002, 131003, 131011); il tool ne restituisce 1.
        Norma: codici oggetto DGSIA; proprieta' e diritti reali, artt. 832 ss. c.c.

        Il sito non ha una materia "proprietà" (quelle voci stanno in "Diritti reali -
        possesso - trascrizioni"): la ricerca testuale trova nella tabella solo 130001
        "Proprieta". Il confronto col sito misura il motore di ricerca; l'atteso del piano (9)
        deriva dall'etichetta di materia propria del tool e resta nel report.
        """
        _compare(page, "proprieta")

    def test_usucapione(self, page):
        """Piano: 131002 e 131003 (usucapione art. 1159 e 1159-bis c.c.), da confermare sul sito.
        Norma: codici oggetto DGSIA; usucapione decennale (art. 1159 c.c.) e speciale per la
        piccola proprieta' rurale (art. 1159-bis c.c.).
        """
        tool, _site, _ = _compare(page, "usucapione")
        assert sorted(tool) == ["131002", "131003"]

    # --- casi al limite -------------------------------------------------------------

    def test_limite_responsabilita_con_accento(self, page):
        """Limite (accenti): il sito non distingue le vocali accentate, quindi "responsabilità"
        deve dare le stesse 11 voci di "responsabilita". Il tool trova ora la sua materia
        "responsabilità" e le descrizioni accentate, ma perde 151110, scritta senza accento
        nella tabella ("Cause di responsabilita contro ...").
        Atteso: le 11 voci del piano per "responsabilita". Norma: artt. 2043-2052 e 2392 ss.
        c.c.; codici oggetto DGSIA.
        """
        _compare(page, "responsabilità")

    def test_limite_proprieta_con_accento(self, page):
        """Limite (accenti): sul sito "proprietà" == "proprieta" (nella tabella solo 130001).
        Il tool con l'accento aggancia la propria etichetta di materia "proprietà" e
        restituisce 9 voci, senza accento 1: il risultato dipende dall'accento digitato.
        Atteso: lo stesso risultato di "proprieta" (il piano indica le 9 voci della materia del
        tool). Norma: artt. 832 ss. c.c.; codici oggetto DGSIA.
        """
        _compare(page, "proprietà")

    def test_limite_frase_esatta_per_morosita(self, page):
        """Limite (opzione enumerata SearchMode): la semantica del tool (sottostringa unica)
        corrisponde all'opzione "Frase esatta" del sito. "per morosita" -> 030011, 030012
        (art. 658 c.p.c., sfratto per morosita' uso abitativo / uso diverso).
        Atteso (caso aggiunto, non nel piano): 030011, 030012. Norma: art. 658 c.p.c.; codici
        oggetto DGSIA.
        """
        tool, _site, _ = _compare(page, "per morosita")
        assert sorted(tool) == ["030011", "030012"]

    def test_limite_tutte_le_parole_non_confrontabile(self, page):
        """Opzione "Tutte le parole" (default del sito): "sfratto morosita" trova sul sito
        030011 e 030012 (parole in qualsiasi ordine); il tool non ha modalita' a piu' parole
        e cerca la sottostringa intera, quindi restituisce 0 voci. Non confrontabile.
        Norma: art. 658 c.p.c.; codici oggetto DGSIA.
        """
        tool = _tool("sfratto morosita")
        pytest.skip(
            "il tool non offre la ricerca 'Tutte le parole' / 'Qualsiasi parola': "
            f"tool={sorted(tool)} (sottostringa intera); sul sito, in esplorazione, "
            "'Tutte le parole' -> 030011, 030012 e 'Frase esatta' -> nessuna voce"
        )

    def test_limite_ricerca_per_codice_non_confrontabile(self, page):
        """Il campo del sito accetta anche un codice numerico ("145001" -> "Solo danni a
        cose", materia Responsabilita' extracontrattuale); il tool cerca solo in materia e
        descrizione e non restituisce nulla. Funzione non offerta dal tool.
        Norma: artt. 2043 ss. c.c. (responsabilita' extracontrattuale); codici oggetto DGSIA.
        """
        tool = _tool("145001")
        pytest.skip(
            "il tool non cerca per codice numerico: "
            f"tool={sorted(tool)}; sul sito, in esplorazione, '145001' -> 145001 'Solo danni a cose'"
        )

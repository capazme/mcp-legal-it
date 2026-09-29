"""Comparison tests: note_iscrizione_ruolo vs avvocatoandreani.it.

The plan's page (servizi/note_iscrizione_a_ruolo.php) only offers the PDF/RTF models of the
notes (Tribunale, Giudice di Pace, CGT, Corte d'Appello, Cassazione): it computes nothing.
The tool returns two things, so each is checked against the site page that computes it:

* contributo unificato of first instance -> servizi/calcolo_contributo_unificato.php
  (value-based scale, with the "riduzione del 50%" box for the art. 13 co. 3 cases) and
  servizi/tabella-contributo-unificato.php (fixed amounts: executions, voluntary
  jurisdiction, labour exemption);
* suggested "codici oggetto" -> servizi/ricerca-codici-iscrizione-ruolo-cause.php (the
  ministerial "Indice delle Materie": every code of the tool must exist on the site with
  the same description, and belong to the materia that fits the procedure).

Norms (read on Normattiva with cite_law on 2026-09-25): DPR 115/2002 art. 13 co. 1
(scale 43/98/237/518/759/1214/1686; voluntary jurisdiction 98, lett. b), co. 2 (execution
on real estate 278, other executions 139, movable executions below 2,500 euro 43), co. 3
(halved for the special proceedings of c.p.c. book IV title I -- injunction, eviction
"convalida di sfratto" -- and for individual labour disputes, save art. 9 co. 1-bis);
art. 9 co. 1-bis (labour/welfare: contribution due only above three times the art. 76
income threshold). Codes: DGSIA / Ministry of Justice table of "oggetti" for civil rolls.

The site is a benchmark, not a source: a genuine difference stays a failing test.
"""

import re
import unicodedata

import pytest

from tests.comparison.conftest import assert_close, goto, parse_euro

_CU_PAGE = "calcolo_contributo_unificato.php"
_CU_TABLE_PAGE = "tabella-contributo-unificato.php"
_CODES_PAGE = "ricerca-codici-iscrizione-ruolo-cause.php"

# Site "Indice delle Materie" ids (select[name='idmenu'] on the codes page).
_MAT_CONTRATTI = "22"  # Contratti e obbligazioni varie
_MAT_DIRITTI_REALI = "28"  # Diritti reali - possesso - trascrizioni
_MAT_ESPR_MOBILIARE = "43"  # Espropriazione mobiliare
_MAT_LAVORO_PRIVATO = "50"  # Lavoro dipendente da privato
_MAT_LOCAZIONE = "51"  # Locazione e comodato di immobile urbano - affitto di azienda
_MAT_PREVIDENZA = "56"  # Previdenza obbligatoria (Prestazione)
_MAT_INGIUNZIONE = "67"  # Procedimento di ingiunzione ante causam
_MAT_SFRATTO = "68"  # Procedimento per convalida di sfratto

# One load per site listing per run: the site is shared, keep the traffic low.
_CACHE: dict = {}


@pytest.fixture(autouse=True)
def _pin_today(monkeypatch):
    """Same reference date for tool and site (the tables carry a _vintage block)."""
    monkeypatch.setenv("LEGAL_TODAY", "2026-09-25")


# --------------------------------------------------------------------------- tool


def _tool(tipo_procedimento: str, valore_causa: float | None, **flags) -> dict:
    import src.server  # noqa: F401  registers every module (avoids circular imports)
    from src.tools.atti_giudiziari import note_iscrizione_ruolo

    fn = getattr(note_iscrizione_ruolo, "fn", note_iscrizione_ruolo)
    return fn(tipo_procedimento=tipo_procedimento, valore_causa=valore_causa, **flags)


def _tool_cu(tipo_procedimento: str, valore_causa: float | None, **flags) -> float:
    r = _tool(tipo_procedimento, valore_causa, **flags)
    assert "errore" not in r, r
    return float(r["contributo_unificato"])


def _tool_codes(tipo_procedimento: str) -> dict[str, str]:
    r = _tool(tipo_procedimento, 10000)
    return {c["codice"]: c["descrizione"] for c in r["codici_oggetto_suggeriti"]}


# --------------------------------------------------------------------------- site: common


def _open(page, path: str):
    """goto() plus a late click on the cookie banner.

    conftest.accept_cookies() checks the banner right after DOMContentLoaded, often before
    it is shown; the banner then swallows the Enter key of the codes search (no submit).
    """
    page.wait_for_timeout(1500)  # courtesy pause between requests
    goto(page, path)
    try:
        page.locator("#accept-btn").click(timeout=4000)
    except Exception:
        pass


# --------------------------------------------------------------------------- site: CU


def _euro_input(valore: float) -> str:
    """10000.5 -> '10000,50' (the field takes the Italian decimal comma)."""
    return f"{valore:.2f}".replace(".", ",")


def _site_cu(page, valore: float, riduzione: bool = False) -> float:
    """Civil, first instance, determined value; optional art. 13 co. 3 halving."""
    _open(page, _CU_PAGE)
    page.select_option("select[name='Processo']", "1")
    page.select_option("select[name='Giudizio']", "1")
    page.check("input[name='TipoValore'][value='0']")
    page.fill("input[name='ValoreCausa']", _euro_input(valore))
    if riduzione:
        page.check("input[name='Riduzione']")
    page.click("#btn-calc", force=True)
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(2500)
    # The result page echoes the form: make sure the site computed what we asked.
    assert page.input_value("input[name='ValoreCausa']") == _euro_input(valore)
    assert page.is_checked("input[name='Riduzione']") == riduzione
    body = page.inner_text("body")
    m = re.search(r"Il\s+contributo\s+è\s+€\s*([\d.]+,\d{2})", body)
    assert m, "site: CU result not found"
    return parse_euro(m.group(1))


def _site_cu_table(page) -> dict[str, str]:
    """Rows of the published CU table: label -> amount text ('€ 43,00' or 'esente')."""
    if "tabella" not in _CACHE:
        _open(page, _CU_TABLE_PAGE)
        rows = page.evaluate(
            """() => [...document.querySelectorAll('tr')]
                  .map(tr => [...tr.querySelectorAll('td')].map(td => td.innerText.trim()))
                  .filter(c => c.length === 2)"""
        )
        _CACHE["tabella"] = {label: value for label, value in rows}
    return _CACHE["tabella"]


def _site_table_amount(page, label_start: str) -> tuple[str, float]:
    """(label, amount) of the single row starting with label_start; 'esente' -> 0.0."""
    rows = _site_cu_table(page)
    hits = [(k, v) for k, v in rows.items() if k.startswith(label_start)]
    assert len(hits) == 1, f"site table: {len(hits)} rows start with {label_start!r}"
    label, value = hits[0]
    if value.lower() == "esente":
        return label, 0.0
    m = re.search(r"€\s*([\d.]+,\d{2})", value)
    assert m, f"site table: no amount in {value!r} ({label})"
    return label, parse_euro(m.group(1))


# --------------------------------------------------------------------------- site: codes

_PARSE_CODES_JS = """() => [...document.querySelectorAll("td[id^='ogg']")].map(td => ({
    codice: td.id.slice(3),
    descrizione: td.previousElementSibling ? td.previousElementSibling.innerText.trim() : '',
    materia: (td.closest('table').querySelector('th') || {innerText: ''}).innerText.trim(),
}))"""


def _norm(s: str) -> str:
    """Lower case, no accents, no accent-apostrophes, compact spaces.

    The site declares it ignores case and accents; the ministerial list writes accents as
    ASCII apostrophes ("morosita'"), so the comparison does the same.
    """
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r"[’'`]", "", s.lower())
    return " ".join(s.split())


def _open_codes_page(page):
    _open(page, _CODES_PAGE)


def _site_materia(page, idmenu: str) -> dict[str, dict]:
    """Every code listed under one site materia: code -> {descrizione, materia}."""
    key = ("materia", idmenu)
    if key not in _CACHE:
        _open_codes_page(page)
        page.fill("input[name='Ricerca']", "")
        with page.expect_navigation(wait_until="domcontentloaded", timeout=45000):
            page.select_option("select[name='idmenu']", idmenu)
        page.wait_for_timeout(2000)
        rows = page.evaluate(_PARSE_CODES_JS)
        assert rows, f"site: no code listed under materia {idmenu}"
        _CACHE[key] = {r["codice"]: r for r in rows}
    return _CACHE[key]


def _site_code(page, codice: str) -> dict | None:
    """Look a single code up with the text search over all materie."""
    key = ("codice", codice)
    if key not in _CACHE:
        _open_codes_page(page)  # fresh page: idmenu back to "** Tutte le Materie **"
        page.fill("input[name='Ricerca']", codice)
        with page.expect_navigation(wait_until="domcontentloaded", timeout=45000):
            page.press("input[name='Ricerca']", "Enter")
        page.wait_for_timeout(2000)
        rows = [r for r in page.evaluate(_PARSE_CODES_JS) if r["codice"] == codice]
        _CACHE[key] = rows[0] if rows else None
    return _CACHE[key]


def _assert_codes_on_site(tool_codes: dict[str, str], site: dict[str, dict], label: str):
    """Every tool code exists on the site with the same description (normalised)."""
    assert tool_codes, f"{label}: the tool suggests no code"
    missing = sorted(set(tool_codes) - set(site))
    wrong = {
        c: (tool_codes[c], site[c]["descrizione"])
        for c in tool_codes
        if c in site and _norm(tool_codes[c]) != _norm(site[c]["descrizione"])
    }
    assert not missing and not wrong, (
        f"{label}: codes missing on the site {missing}; different descriptions {wrong}"
    )


# =========================================================================== CU cases


class TestContributoUnificato:
    """CU returned by the tool vs the site calculator / published table."""

    def test_cognizione_ordinaria_26000_limite(self, page):
        # Plan: "CU 237,00 euro (art. 13 co. 1 lett. c)". Upper edge of the 5.200-26.000 band
        # ("fino a euro 26.000" is inclusive).
        ours = _tool_cu("cognizione_ordinaria", 26000)
        site = _site_cu(page, 26000)
        assert_close(ours, site, 0.01, "CU cognizione 26.000")

    def test_cognizione_ordinaria_26000_01_limite(self, page):
        # One cent above the edge: art. 13 co. 1 lett. d) "superiore a euro 26.000" -> 518.
        ours = _tool_cu("cognizione_ordinaria", 26000.01)
        site = _site_cu(page, 26000.01)
        assert_close(ours, site, 0.01, "CU cognizione 26.000,01")

    def test_monitorio_1100_limite(self, page):
        # Plan: "21,50 euro (43 ridotto alla metà, art. 13 co. 3)" -- injunction is a special
        # proceeding of c.p.c. book IV title I; 1.100 is the inclusive edge of lett. a).
        ours = _tool_cu("monitorio", 1100)
        site = _site_cu(page, 1100, riduzione=True)
        assert_close(ours, site, 0.01, "CU monitorio 1.100")

    def test_monitorio_1100_01_limite(self, page):
        # Just above lett. a): 98 halved = 49 (art. 13 co. 1 lett. b + co. 3).
        ours = _tool_cu("monitorio", 1100.01)
        site = _site_cu(page, 1100.01, riduzione=True)
        assert_close(ours, site, 0.01, "CU monitorio 1.100,01")

    def test_condominio_5200_limite(self, page):
        # Enumerated option 'condominio' (ordinary cognizance, full scale): 5.200 is the
        # inclusive edge of lett. b) -> 98.
        ours = _tool_cu("condominio", 5200)
        site = _site_cu(page, 5200)
        assert_close(ours, site, 0.01, "CU condominio 5.200")

    def test_locazione_causa_ordinaria_3000(self, page):
        # Plan: "98,00 per la causa locatizia ordinaria" (art. 13 co. 1 lett. b, no halving:
        # the art. 447-bis c.p.c. rite is not a special proceeding of book IV title I).
        ours = _tool_cu("locazione", 3000)
        site = _site_cu(page, 3000)
        assert_close(ours, site, 0.01, "CU locazione, causa ordinaria 3.000")

    def test_locazione_convalida_sfratto_3000(self, page):
        # Plan: "49,00 euro per la convalida di sfratto (98 ridotto alla metà, valore pari ai
        # canoni scaduti, art. 13 co. 3) ... il tool dà 98 senza distinguere".
        # The eviction procedure (artt. 657-669 c.p.c.) is in book IV title I: halved CU.
        # The tool offers the eviction codes 030001-030021 under 'locazione' but prices the
        # case on the full scale, and has no parameter to tell the two apart.
        # Fixed: the tool now has `convalida_sfratto` (art. 13 co. 3 halving).
        ours = _tool_cu("locazione", 3000, convalida_sfratto=True)
        site = _site_cu(page, 3000, riduzione=True)
        assert_close(ours, site, 0.01, "CU convalida di sfratto, canoni scaduti 3.000")

    def test_lavoro_20000_reddito_entro_soglia(self, page):
        # Plan: "0 sotto tre volte la soglia dell'art. 76" (art. 9 co. 1-bis DPR 115/2002).
        # Site: published table, row "... quando il reddito della parte e' inferiore o uguale
        # al limite stabilito" = esente.
        ours = _tool_cu("lavoro", 20000)
        label, site = _site_table_amount(
            page, "Procedimenti in materia di lavoro, rapporti di pubblico impiego nonché"
        )
        assert "inferiore o uguale" in label, label
        assert_close(ours, site, 0.01, "CU lavoro, reddito entro 3x soglia art. 76")

    def test_lavoro_20000_reddito_oltre_soglia(self, page):
        # Plan: "118,50 euro oltre (art. 9 co. 1-bis e art. 13 co. 3): il tool dà 0 senza
        # avviso". Above three times the art. 76 threshold the labour case pays half the
        # scale: 237 / 2. The tool never passes `reddito_oltre_soglia` to the CU function,
        # so it always answers 0 and does not flag the assumption.
        rows = _site_cu_table(page)
        row = [v for k, v in rows.items() if k.startswith(
            "Procedimenti in materia di lavoro e rapporti di pubblico impiego quando il reddito"
        )]
        assert row and "50%" in row[0], f"site table row: {row}"
        # Fixed: the tool now has `reddito_oltre_soglia_lavoro` (art. 9 co. 1-bis + art. 13 co. 3).
        ours = _tool_cu("lavoro", 20000, reddito_oltre_soglia_lavoro=True)
        site = _site_cu(page, 20000, riduzione=True)
        assert_close(ours, site, 0.01, "CU lavoro, reddito oltre 3x soglia art. 76")

    def test_esecuzione_mobiliare_2500_limite(self, page):
        # Art. 13 co. 2: 43 only "di valore inferiore a 2.500 euro"; at 2.500 the other
        # executions' amount applies (278 halved = 139). Site row: "superiore o uguale".
        ours = _tool_cu("esecuzione_mobiliare", 2500)
        _, site = _site_table_amount(
            page, "Procedimenti esecutivi mobiliari di valore superiore o uguale a Euro 2.500"
        )
        assert_close(ours, site, 0.01, "CU esecuzione mobiliare 2.500")

    def test_esecuzione_mobiliare_2499_99_limite(self, page):
        # Art. 13 co. 2, third sentence: below 2.500 euro -> 43.
        ours = _tool_cu("esecuzione_mobiliare", 2499.99)
        _, site = _site_table_amount(
            page, "Procedimenti esecutivi mobiliari di valore inferiore ad Euro 2.500"
        )
        assert_close(ours, site, 0.01, "CU esecuzione mobiliare 2.499,99")

    def test_esecuzione_mobiliare_senza_valore(self, page):
        # Plan: "CU non determinabile senza valore: 43 euro sotto 2.500, 139 da 2.500
        # (art. 13 co. 2); il tool dà 43". The site cannot price a movable execution without
        # its value (two rows by value), so there is nothing to compare: the tool silently
        # takes value 0 (`valore_causa or 0`) instead of asking for it.
        # After the fix the tool returns contributo_unificato=None (value required), which is the
        # correct behaviour: the case stays non-comparable.
        ours = _tool("esecuzione_mobiliare", None)["contributo_unificato"]
        assert ours is None, "the tool must ask for the value instead of assuming 0"
        _, sotto = _site_table_amount(page, "Procedimenti esecutivi mobiliari di valore inferiore")
        _, sopra = _site_table_amount(page, "Procedimenti esecutivi mobiliari di valore superiore")
        pytest.skip(
            f"sito_non_calcola: senza valore il sito non determina il CU "
            f"({sotto:.2f} sotto 2.500, {sopra:.2f} da 2.500); il tool chiede il valore (CU None)"
        )

    def test_esecuzione_immobiliare(self, page):
        # Art. 13 co. 2, first sentence: 278, fixed.
        ours = _tool_cu("esecuzione_immobiliare", None)
        _, site = _site_table_amount(page, "Procedimenti di esecuzione immobiliare")
        assert_close(ours, site, 0.01, "CU esecuzione immobiliare")

    def test_volontaria_giurisdizione(self, page):
        # Art. 13 co. 1 lett. b): voluntary jurisdiction 98, fixed.
        ours = _tool_cu("volontaria_giurisdizione", None)
        _, site = _site_table_amount(page, "Procedimenti di volontaria giurisdizione")
        assert_close(ours, site, 0.01, "CU volontaria giurisdizione")


# =========================================================================== codes


class TestCodiciOggetto:
    """Suggested 'codici oggetto' vs the ministerial index published on the site."""

    def test_codici_cognizione_ordinaria(self, page):
        # Plan: "codici della materia contratto presenti con la stessa descrizione nella
        # tabella ministeriale". Site materia: "Contratti e obbligazioni varie".
        tool = _tool_codes("cognizione_ordinaria")
        site = _site_materia(page, _MAT_CONTRATTI)
        _assert_codes_on_site(tool, site, "cognizione_ordinaria")

    def test_codici_locazione(self, page):
        # Eviction codes (030xxx, "Procedimento per convalida di sfratto") and lease-dispute
        # codes (144xxx, "Locazione e comodato di immobile urbano - affitto di azienda").
        tool = _tool_codes("locazione")
        site = {**_site_materia(page, _MAT_SFRATTO), **_site_materia(page, _MAT_LOCAZIONE)}
        _assert_codes_on_site(tool, site, "locazione")

    def test_codici_lavoro(self, page):
        # Labour (22xxxx, "Lavoro dipendente da privato") and welfare (23xxxx, "Previdenza
        # obbligatoria (Prestazione)").
        tool = _tool_codes("lavoro")
        site = {**_site_materia(page, _MAT_LAVORO_PRIVATO), **_site_materia(page, _MAT_PREVIDENZA)}
        _assert_codes_on_site(tool, site, "lavoro")

    def test_codici_condominio(self, page):
        # 1300xx under "Diritti reali - possesso - trascrizioni"; the two camera-di-consiglio
        # codes (400271 appointment, 400272 removal of the administrator) are looked up by
        # number (site materia "Altri istituti e leggi speciali").
        tool = _tool_codes("condominio")
        site = dict(_site_materia(page, _MAT_DIRITTI_REALI))
        for code in sorted(set(tool) - set(site)):
            hit = _site_code(page, code)
            if hit:
                site[code] = hit
        _assert_codes_on_site(tool, site, "condominio")

    def test_codici_monitorio(self, page):
        # The ricorso per decreto ingiuntivo is registered on the summary-proceedings roll with
        # the "Procedimento di ingiunzione ante causam (...)" objects (010xxx). The tool maps
        # 'monitorio' to its 'contratto' codes (140xxx), which are the ordinary-cognizance
        # objects (usable for the opposition, not for the injunction itself).
        tool = _tool_codes("monitorio")
        site = _site_materia(page, _MAT_INGIUNZIONE)
        fuori = {c: d for c, d in tool.items() if c not in site}
        assert not fuori, (
            f"monitorio: {len(fuori)}/{len(tool)} codici suggeriti fuori dalla materia sito "
            f"'Procedimento di ingiunzione ante causam' ({len(site)} codici 010xxx, es. "
            f"{sorted(site)[:3]}): {sorted(fuori)}"
        )

    def test_codici_esecuzione_mobiliare(self, page):
        # The site lists the movable-execution objects (510001 presso il debitore, 510002
        # presso terzi, ...); the tool suggests none for 'esecuzione_mobiliare'.
        tool = _tool_codes("esecuzione_mobiliare")
        site = _site_materia(page, _MAT_ESPR_MOBILIARE)
        assert tool and set(tool) <= set(site), (
            f"esecuzione_mobiliare: tool {sorted(tool)} vs sito "
            f"{ {c: r['descrizione'] for c, r in site.items()} }"
        )

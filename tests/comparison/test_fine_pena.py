"""Benchmark of ``fine_pena`` against avvocatoandreani.it.

Page: https://www.avvocatoandreani.it/servizi/calcolo-fine-pena-liberazione-anticipata.php
(form ``CalcoloFinePena``: DurataAnni/DurataMesi/DurataGiorni, DataInizio gg/mm/aaaa,
LiberazioneAnticipata, AnticipataSpeciale, IntegrazioneExtra, SemestriCompleti,
DataLimite, "Periodi gia' scontati" TipoCre-0/AnniCre-0/MesiCre-0/GiorniCre-0,
submit ``#btn-calc``; the result is the ``#R-Output`` table "SVILUPPO del CALCOLO").

Norms (text in force read with cite_law): art. 54 co. 1 L. 354/1975 (45 days of
detraction "per ogni singolo semestre di pena scontata", custodia cautelare and
detenzione domiciliare included), art. 14 c.p. (calendar computation, the day of
decorrenza is not counted), art. 656 co. 10-bis c.p.p. (the order of execution states
the pena da espiare computing the art. 54 detractions, i.e. the "fine pena virtuale";
added by D.L. 92/2024 conv. L. 112/2024) and art. 69-bis co. 2 O.P. (check of the
semesters in the 90 days before that end).

Three comparisons per case, so that a mismatch on one quantity does not hide an
agreement on another:
- ``test_fine_pena_nominale``: tool ``data_fine_pena`` vs site "Data fine pena" /
  "Fine pena senza detrazioni" (exact date);
- ``test_giorni_detrazione``: tool ``sconto_giorni`` vs site "Giorni di detrazione
  spettanti" (exact integer: it measures the number of semesters counted);
- ``test_fine_con_liberazione``: tool ``data_fine_con_liberazione`` vs site "Fine pena
  con liberazione anticipata" (exact date).

What the site does (reconstructed on the 13 cases below, not documented by the site):
it counts a semester only if it is completed before the virtual end computed with the
detractions of the previous semesters; the tool instead divides the days of the whole
nominal pena by 180. The site's virtual end is then later than "nominal end - detraction"
by one day for each semester fully served before that end (a day-count slip, the site
counts served periods inclusively: see its "Nota 2"); a semester completed after the
virtual end adds no slip. The failure messages print "nominale - giorni del sito" so the
two effects can be told apart.

The tool does not read the clock, so no LEGAL_TODAY pin is needed. The site keeps the
form state in the session: every checkbox is therefore set explicitly. The two
"speciale"/"integrazione" checkboxes (D.L. 146/2013, only 2010-2015) are unchecked:
every case below starts after 2015, so they are irrelevant by their own terms.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import pytest

from tests.comparison.conftest import accept_cookies

URL = "https://www.avvocatoandreani.it/servizi/calcolo-fine-pena-liberazione-anticipata.php"


@dataclass(frozen=True)
class Case:
    tool: dict                      # arguments passed to fine_pena
    anni: str = ""                  # site DurataAnni
    mesi: str = ""                  # site DurataMesi
    giorni: str = ""                # site DurataGiorni
    presofferto: tuple = ()         # (TipoCre value, GiorniCre value)
    limite: bool = False            # boundary case
    atteso: str = ""                # expectation stated in the benchmark plan / by the agent
    norma: str = "art. 54 co. 1 L. 354/1975; art. 14 c.p."


CASES: dict[str, Case] = {
    # Plan case 1. Atteso (piano): tool 2026-01-01; if the first day counts as a day of
    # pena expiated the end would be 2025-12-31 -- to be read from the site.
    # Norma: art. 14 c.p. (calendar computation, day of decorrenza not counted).
    "due_anni_senza_la": Case(
        tool={"data_inizio_pena": "2024-01-01", "pena_totale_mesi": 24,
              "liberazione_anticipata": False},
        anni="2",
        atteso="tool 2026-01-01; sito da leggere (2026-01-01 o 2025-12-31)",
        norma="art. 14 c.p.",
    ),
    # Plan case 2. Atteso (piano): tool counts 4 semesters on the nominal pena
    # (730 // 180) -> 180 days, end 2025-07-05; if the site only counts the semesters
    # actually served before the virtual end it finds 3 (135 days).
    # Norma: art. 54 co. 1 L. 354/1975 ("semestre di pena scontata").
    "due_anni_con_la": Case(
        tool={"data_inizio_pena": "2024-01-01", "pena_totale_mesi": 24,
              "liberazione_anticipata": True},
        anni="2",
        atteso="tool 4 semestri/180 gg/2025-07-05; sito forse 3 semestri/135 gg",
    ),
    # Plan case 3 (boundary: just under three semesters). 17.95 months -> tool
    # 17 months + round(0.95*30) = 28 days (float 28.4999.. -> 28), i.e. 17 m 28 d on
    # the site. Atteso (piano): two calendar semesters completed -> 90 days, end with
    # LA 2026-06-09; the tool divides 546 days by 180, counts 3 (135 days) and gives
    # 2026-04-25 (nominal end 2026-09-07).
    # Norma: art. 54 co. 1 L. 354/1975 and art. 14 c.p. (calendar semesters).
    "pena_17m28g_con_la": Case(
        tool={"data_inizio_pena": "2025-03-10", "pena_totale_mesi": 17.95,
              "liberazione_anticipata": True},
        mesi="17", giorni="28", limite=True,
        atteso="piano: 2 semestri/90 gg/2026-06-09; tool 3 semestri/135 gg/2026-04-25",
    ),
    # Plan case 4. 30 days of custodia cautelare in carcere (site TipoCre 10, which
    # counts for LA). Atteso (piano): effective start 2024-05-02, nominal end
    # 2025-05-02, tool 2 semesters/90 days -> 2025-02-01; the site also checks whether
    # the presofferto is useful for LA -- to be read from the site.
    # Norma: art. 54 co. 1 secondo periodo L. 354/1975 (custodia cautelare valutata);
    # art. 657 c.p.p. (computo della custodia cautelare).
    "presofferto_30g": Case(
        tool={"data_inizio_pena": "2024-06-01", "pena_totale_mesi": 12,
              "liberazione_anticipata": True, "giorni_presofferto": 30},
        anni="1", presofferto=("10", "30"),
        atteso="tool fine 2025-05-02, 2 semestri/90 gg/2025-02-01; sito da leggere",
        norma="art. 54 co. 1 L. 354/1975; art. 657 c.p.p.; art. 14 c.p.",
    ),
    # Boundary (agent): a pena of exactly one semester. Atteso: the semester is
    # completed only on the last day of the pena, so no detraction can be enjoyed
    # (0 days, end with LA = nominal end 2025-07-01); the tool counts 181 // 180 = 1
    # semester and gives 45 days, 2025-05-17.
    "sei_mesi_con_la": Case(
        tool={"data_inizio_pena": "2025-01-01", "pena_totale_mesi": 6,
              "liberazione_anticipata": True},
        mesi="6", limite=True,
        atteso="0 gg (semestre non scontato prima del fine pena); tool 45 gg",
    ),
    # Boundary (agent): the shortest pena whose first semester is completed before the
    # end (01/07/2025, one month before the nominal end 01/08/2025). Atteso: 1 semester,
    # 45 days, virtual end 2025-06-17 for both (tool 212 // 180 = 1). Note that the
    # virtual end falls before the semester that generates the detraction is completed.
    "sette_mesi_con_la": Case(
        tool={"data_inizio_pena": "2025-01-01", "pena_totale_mesi": 7,
              "liberazione_anticipata": True},
        mesi="7", limite=True,
        atteso="1 semestre/45 gg/2025-06-17 per tool e sito",
    ),
    # Boundary (agent): the shortest pena from 01/01/2025 whose second semester counts
    # (it ends 01/01/2026, before 01/03/2026 - 45 days = 15/01/2026; with 13 months it
    # would not). Atteso: 2 semesters, 90 days for both (tool 424 // 180 = 2), virtual
    # end 2025-12-01 (nominal end 2026-03-01 - 90 days).
    "quattordici_mesi_con_la": Case(
        tool={"data_inizio_pena": "2025-01-01", "pena_totale_mesi": 14,
              "liberazione_anticipata": True},
        mesi="14", limite=True,
        atteso="2 semestri/90 gg per tool e sito; fine virtuale 2025-12-01",
    ),
    # Agent case: three years. Atteso: 5 semesters served before the virtual end
    # (225 days); the tool counts 1095 // 180 = 6 (270 days, 2027-04-06).
    "tre_anni_con_la": Case(
        tool={"data_inizio_pena": "2025-01-01", "pena_totale_mesi": 36,
              "liberazione_anticipata": True},
        anni="3",
        atteso="5 semestri/225 gg; tool 6 semestri/270 gg/2027-04-06",
    ),
    # Agent case: a long pena, across two leap years (2028, 2032). Atteso: 16 semesters
    # completed before the virtual end (720 days, 2033-01-11); the tool counts
    # 3652 // 180 = 20 semesters (900 days, 2032-07-15): the gap grows with the pena.
    "dieci_anni_con_la": Case(
        tool={"data_inizio_pena": "2025-01-01", "pena_totale_mesi": 120,
              "liberazione_anticipata": True},
        anni="10",
        atteso="16 semestri/720 gg/2033-01-11; tool 20 semestri/900 gg/2032-07-15",
    ),
    # Boundary (agent): end-of-month clamp. 31/01/2025 + 1 month: the tool clamps to
    # 2025-02-28. Norma: art. 14 c.p. (calendar months).
    "fine_mese_31_gennaio": Case(
        tool={"data_inizio_pena": "2025-01-31", "pena_totale_mesi": 1,
              "liberazione_anticipata": False},
        mesi="1", limite=True,
        atteso="tool 2025-02-28 (giorno 31 portato a fine febbraio)",
        norma="art. 14 c.p.",
    ),
    # Boundary (agent): leap day, different year. 29/02/2024 + 12 months -> tool
    # 2025-02-28. Norma: art. 14 c.p.
    "anno_bisestile_29_febbraio": Case(
        tool={"data_inizio_pena": "2024-02-29", "pena_totale_mesi": 12,
              "liberazione_anticipata": False},
        anni="1", limite=True,
        atteso="tool 2025-02-28",
        norma="art. 14 c.p.",
    ),
    # Boundary (agent): order of months and days. 30/01/2025 + 1 month 2 days: months
    # first with clamp (28/02) then +2 days -> tool 2025-03-02; days first would give
    # 2025-03-01, JS month overflow 2025-03-04. Norma: art. 14 c.p.
    "mese_e_giorni_30_gennaio": Case(
        tool={"data_inizio_pena": "2025-01-30", "pena_totale_mesi": 1 + 2 / 30,
              "liberazione_anticipata": False},
        mesi="1", giorni="2", limite=True,
        atteso="tool 2025-03-02",
        norma="art. 14 c.p.",
    ),
    # Boundary (agent): across August. 16/07/2025 + 1 month 20 days -> tool
    # 2025-09-05 (no feriale suspension applies to the execution of a penalty).
    "a_cavallo_di_agosto": Case(
        tool={"data_inizio_pena": "2025-07-16", "pena_totale_mesi": 1 + 20 / 30,
              "liberazione_anticipata": False},
        mesi="1", giorni="20", limite=True,
        atteso="tool 2025-09-05",
        norma="art. 14 c.p.",
    ),
}

LA_CASES = [k for k, c in CASES.items() if c.tool.get("liberazione_anticipata")]

_SITE_CACHE: dict[str, dict] = {}


def _tool(case: Case) -> dict:
    import src.server  # noqa: F401  registers every module (avoids circular imports)
    from src.tools.diritto_penale import fine_pena

    fn = getattr(fine_pena, "fn", fine_pena)
    return fn(**case.tool)


def _iso(d: str) -> str:
    gg, mm, aaaa = d.strip().split("/")
    return f"{aaaa}-{mm}-{gg}"


def _open(page) -> None:
    """Open the page and close the consent dialog WITHOUT accepting.

    The page's InMobi/Quantcast CMP installs a focus trap (capture-phase click listener
    with preventDefault + stopImmediatePropagation) that swallows every click outside
    the dialog. The shared ``goto`` helper removes the dialog node but leaves the trap
    active, so checkbox clicks silently do nothing. Closing the dialog with its own X
    ("continua senza accettare") releases the trap and consents to nothing;
    ``accept_cookies`` then finds no visible accept button and only cleans up.
    """
    page.goto(URL, timeout=60000, wait_until="domcontentloaded")
    close = page.locator(".qc-cmp2-close-icon")
    try:
        close.wait_for(state="visible", timeout=8000)
        close.click()
        page.wait_for_timeout(500)
    except Exception:
        pass  # no dialog shown this time
    accept_cookies(page)


def _set_checked(page, selector: str, value: bool) -> None:
    """Set a checkbox with a real click, so the site's own handlers run."""
    if page.is_checked(selector) != value:
        page.set_checked(selector, value)
    assert page.is_checked(selector) == value, f"stato di {selector} non impostato"


def _site(page, key: str) -> dict:
    """Drive the site once per case and parse the "SVILUPPO del CALCOLO" table."""
    if key in _SITE_CACHE:
        return _SITE_CACHE[key]
    case = CASES[key]
    page.wait_for_timeout(1500)  # be gentle with the site between requests
    _open(page)
    page.select_option("#DurataAnni", case.anni)
    page.select_option("#DurataMesi", case.mesi)
    page.select_option("#DurataGiorni", case.giorni)
    y, m, d = case.tool["data_inizio_pena"].split("-")
    page.fill("#DataInizio", f"{d}/{m}/{y}")
    # Fresh context: "Calcola fino al" empty and "Solo semestri completi" = Si (defaults).
    assert page.input_value("#DataLimite") == ""
    assert page.is_checked("#SemestriCompleti-1")
    # The site's own handler copies the LA state onto the two D.L. 146/2013 boxes, so LA
    # goes first; with LA on, the two boxes are then switched off explicitly.
    la = bool(case.tool.get("liberazione_anticipata"))
    _set_checked(page, "#LiberazioneAnticipata", la)
    if la:
        _set_checked(page, "#AnticipataSpeciale", False)
        _set_checked(page, "#IntegrazioneExtra", False)
    assert not page.is_checked("#AnticipataSpeciale")
    assert not page.is_checked("#IntegrazioneExtra")
    if case.presofferto:
        tipo, giorni = case.presofferto
        page.select_option("#TipoCre-0", tipo)
        page.select_option("#GiorniCre-0", giorni)
    page.click("#btn-calc", force=True)
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(2500)

    rows = {}
    for tr in page.query_selector_all("#R-Output table.result tr"):
        lab, val = tr.query_selector("td.lab"), tr.query_selector("td.val")
        if lab and val:
            rows[lab.inner_text().strip().rstrip(":")] = val.inner_text().strip()
    if not rows:
        err = page.locator("#Error").inner_text() if page.locator("#Error").count() else ""
        pytest.fail(f"sito senza risultato per {key}: {err!r}")

    nominale = rows.get("Data fine pena") or rows.get("Fine pena senza detrazioni")
    out = {"righe": rows, "fine_pena": _iso(nominale)}
    if "Giorni di detrazione spettanti" in rows:
        raw = rows["Giorni di detrazione spettanti"]
        out["giorni_detrazione"] = 0 if raw.lower() == "nessuno" else int(raw)
        con_la = rows.get("Fine pena con liberazione anticipata")
        # With no detraction the site prints no "con liberazione" row: the end is the nominal one.
        out["fine_con_liberazione"] = _iso(con_la) if con_la else out["fine_pena"]
    _SITE_CACHE[key] = out
    return out


@pytest.mark.parametrize("key", list(CASES))
def test_fine_pena_nominale(page, key):
    """Nominal end date (no detraction): tool ``data_fine_pena`` == site, exact date."""
    case = CASES[key]
    tool = _tool(case)
    site = _site(page, key)
    assert tool["data_fine_pena"] == site["fine_pena"], (
        f"{key}: tool={tool['data_fine_pena']} sito={site['fine_pena']} "
        f"(atteso: {case.atteso}; norma: {case.norma}; righe sito: {site['righe']})"
    )


@pytest.mark.parametrize("key", LA_CASES)
def test_giorni_detrazione(page, key):
    """Detraction days (45 x semesters counted): tool == site, exact integer."""
    case = CASES[key]
    la = _tool(case)["liberazione_anticipata"]
    site = _site(page, key)
    assert la["sconto_giorni"] == site["giorni_detrazione"], (
        f"{key}: tool={la['sconto_giorni']} gg ({la['semestri_scontati']} semestri) "
        f"sito={site['giorni_detrazione']} gg ({site['giorni_detrazione'] // 45} semestri) "
        f"(atteso: {case.atteso}; norma: {case.norma}; righe sito: {site['righe']})"
    )


@pytest.mark.parametrize("key", LA_CASES)
def test_fine_con_liberazione(page, key):
    """Virtual end (fine pena con liberazione anticipata): tool == site, exact date."""
    case = CASES[key]
    tool = _tool(case)
    la = tool["liberazione_anticipata"]
    site = _site(page, key)
    # Diagnostic only: the site's own detraction subtracted from the nominal end.
    ref = date.fromisoformat(site["fine_pena"]) - timedelta(days=site["giorni_detrazione"])
    slip = (date.fromisoformat(site["fine_con_liberazione"]) - ref).days
    assert la["data_fine_con_liberazione"] == site["fine_con_liberazione"], (
        f"{key}: tool={la['data_fine_con_liberazione']} ({la['sconto_giorni']} gg) "
        f"sito={site['fine_con_liberazione']} ({site['giorni_detrazione']} gg); "
        f"nominale - giorni del sito = {ref.isoformat()} (scarto del sito {slip:+d} gg) "
        f"(atteso: {case.atteso}; norma: {case.norma}; righe sito: {site['righe']})"
    )


def test_liberazione_anticipata_speciale_non_confrontabile():
    """Site option without a tool counterpart (enumerated option).

    The site offers the "liberazione anticipata speciale" of 75 days per semester
    (art. 4 co. 1 D.L. 146/2013, semesters between 23/12/2013 and
    22/12/2015, excluded for art. 4-bis O.P. offences) and the extra 30 days on the
    semesters already granted from 01/01/2010 (art. 4 co. 2-3). The tool always applies
    45 days and has no parameter for either, nor any way to know whether the offence is
    an art. 4-bis one: a pena running in 2014 cannot be compared.
    """
    pytest.skip("non confrontabile: il tool non prevede la liberazione anticipata speciale "
                "(75 gg, art. 4 co. 1 D.L. 146/2013) ne' l'integrazione di 30 gg (art. 4 co. 2)")


def test_opzioni_sito_senza_corrispondente():
    """Site inputs the tool cannot express.

    "Calcola fino al" (detraction matured up to a date, e.g. for an istanza under
    art. 69-bis O.P.), "Interruzioni" of the execution with the "Solo semestri completi"
    switch, and the type of each period already served (the site offers ten types, from
    custodia cautelare and detenzione domiciliare -- which art. 54 co. 1 counts -- to an
    explicit "Periodo che non rileva per la liberazione anticipata"): the tool takes only
    a number of presofferto days and always counts them towards the semesters.
    """
    pytest.skip("non confrontabile: il tool non ha data limite, interruzioni, "
                "'solo semestri completi' ne' tipologie di presofferto che non rilevano per la LA")


# Fase 3: the tool now counts only the semesters served before release (art. 54 co. 1
# L. 354/1975), as the site does. The site's virtual end date is 1-4 days after nominal end
# minus the detraction, with no rule found in the norm; the tool keeps the plain subtraction.

"""Smoke live of the three EU -> Italy transposition tools against CELLAR.

What it checks, on documents whose identifiers are fixed and public:

- `get_italian_implementation`: directive (EU) 2019/790 (copyright in the
  digital single market, CELEX 32019L0790) -> D.Lgs. 8 novembre 2021, n. 177
  (GU n. 283 del 27-11-2021, MNE CELEX 72019L0790ITA_202107973); the entry
  into force the tool prints is compared with Normattiva's ("Entrata in vigore
  del provvedimento: 12/12/2021"); the GDPR (32016R0679) is a regulation and
  must be answered without a query.
- `get_eu_basis`: the reverse lookup from "D.Lgs. 177/2021" and from the MNE
  CELEX, with the transposition deadline checked against art. 29(1) of the
  directive read through `cite_law` ("entro il 7 giugno 2021"); a national act
  that transposes several directives (legge 23 dicembre 2021, n. 238, legge
  europea 2019-2020) must list them all; D.Lgs. 196/2003, whose CELLAR notice
  (72002L0058ITA_117422, directive 2002/58/EC) has no local id, must be found
  by act reference as it is by its CELEX.
- `elenco_misure_nazionali`: the French measures for the same directive (loi
  n° 2019-775 du 24 juillet 2019, ordonnance n° 2021-580 du 12 mai 2021), the
  wording of the header and of the no-results message for a country other
  than Italy, the act number in the heading, and ITA equal to
  `get_italian_implementation`.

Reference values: CELLAR SPARQL notices of the national implementing measures,
the Normattiva page of D.Lgs. 177/2021 and the Italian text of art. 29 of
directive 2019/790 (EUR-Lex/CELLAR through `cite_law`), read on 2026-09-25.
EUR-Lex answers automated requests with a WAF challenge (HTTP 202), so its
"national transposition" tab is not readable here: CELLAR is the database
behind it.

Every tool call is a real network call, cached per session (`_call`), so each
distinct input hits CELLAR once. A network failure of the source ("non
raggiungibile") skips the test instead of failing it: that is the source being
down, not the tool being wrong.

    .venv/bin/pytest tests/unit/test_eu_implementation_live.py -m live -q -p no:cacheprovider -rfEs

Excluded from the default run (pyproject sets `-m 'not live'`).
"""

from __future__ import annotations

import asyncio
import functools
import re

import httpx
import pytest

import src.server  # noqa: F401  (registers every tool module first: avoids a circular import)
from src.tools import eu_implementation as eu_tools
from tests.unit._norme_live import assert_parole

pytestmark = pytest.mark.live

# Directive (EU) 2019/790 — copyright and related rights in the digital single market.
DSM_CELEX = "32019L0790"
DSM_CELLAR_URI = "http://publications.europa.eu/resource/cellar/214471fe-786e-11e9-9f05-01aa75ed71a1"
# Art. 29(1) of the directive: "entro il 7 giugno 2021".
DSM_DEADLINE_ISO = "2021-06-07"

# D.Lgs. 8 novembre 2021, n. 177 — Italian transposition (Normattiva, read 2026-09-25:
# "Entrata in vigore del provvedimento: 12/12/2021 (GU n.283 del 27-11-2021)").
DLGS_177_MNE_CELEX = "72019L0790ITA_202107973"
DLGS_177_GU_NUM = "283"
DLGS_177_GU_DATE_ISO = "2021-11-27"
DLGS_177_EIF_FROZEN = "12/12/2021"
DLGS_177_NORMATTIVA_URL = (
    "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.legislativo:2021-11-08;177"
)

# D.Lgs. 30 giugno 2003, n. 196 (Codice privacy) as notified for directive 2002/58/EC:
# the CELLAR notice has type, title ("Decreto legislativo 30/6/2003, n. 196-Codice ...")
# and CELEX, but NO resource_legal_id_local (read 2026-09-25; 2,635 of the 5,482
# Italian notices have none).
DLGS_196_MNE_CELEX = "72002L0058ITA_117422"
EPRIVACY_CELEX = "32002L0058"

# French measures notified for 2019/790 (CELLAR, read 2026-09-25).
FRA_LOI_2019_775 = "72019L0790FRA_278035"
FRA_ORDONNANCE_2021_580 = "72019L0790FRA_202103614"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@functools.lru_cache(maxsize=None)
def _call_cached(name: str, items: tuple) -> str:
    tool = getattr(eu_tools, name)
    fn = getattr(tool, "fn", tool)
    return asyncio.run(fn(**dict(items)))


def _call(name: str, **kwargs) -> str:
    """Run a tool once per distinct input; skip when CELLAR is unreachable."""
    out = _call_cached(name, tuple(sorted(kwargs.items())))
    if out.startswith("**Errore**") and "non raggiungibile" in out:
        pytest.skip(f"CELLAR non raggiungibile per {name}{kwargs}: {out[:300]}")
    return out


def _field(text: str, label: str) -> list[str]:
    """Values of every `**label**: value` line of a tool answer."""
    return re.findall(rf"\*\*{re.escape(label)}\*\*:\s*(.+)", text)


def _headings(text: str) -> list[str]:
    return re.findall(r"^### (.+)$", text, flags=re.MULTILINE)


def _dmy_to_iso(dmy: str) -> str:
    d, m, y = dmy.split("/")
    return f"{y}-{m}-{d}"


@functools.lru_cache(maxsize=1)
def _normattiva_eif_dlgs_177() -> str:
    """Entry into force of D.Lgs. 177/2021 as printed by Normattiva (dd/mm/yyyy).

    Falls back to the value read by hand on 2026-09-25 when Normattiva cannot
    be reached, so the comparison with the tool still runs.
    """
    try:
        resp = httpx.get(
            DLGS_177_NORMATTIVA_URL,
            headers={"User-Agent": "Mozilla/5.0 (compatible; mcp-legal-it-tests)"},
            timeout=30.0,
            follow_redirects=True,
        )
        m = re.search(r"Entrata in vigore del provvedimento:\s*(\d{2}/\d{2}/\d{4})", resp.text)
        if m:
            return m.group(1)
    except httpx.HTTPError:
        pass
    return DLGS_177_EIF_FROZEN


# ---------------------------------------------------------------------------
# get_italian_implementation
# ---------------------------------------------------------------------------


class TestGetItalianImplementation:
    def test_dir_2019_790_dlgs_177_2021_metadati(self):
        """Directive 2019/790 -> D.Lgs. n. 177 (2021), GU n. 283 del 27-11-2021, MNE CELEX."""
        out = _call("get_italian_implementation", direttiva="direttiva 2019/790")
        assert "**Errore**" not in out, out
        assert f"Recepimento italiano della direttiva {DSM_CELEX}" in out, out
        assert _headings(out) == ["Decreto legislativo n. 177"], out
        assert _field(out, "Gazzetta Ufficiale") == [f"n. {DLGS_177_GU_NUM} del {DLGS_177_GU_DATE_ISO}"], out
        assert _field(out, "CELEX misura nazionale") == [DLGS_177_MNE_CELEX], out
        assert _field(out, "Direttiva recepita") == [DSM_CELEX], out
        assert "Attuazione della direttiva (UE) 2019/790" in _field(out, "Titolo")[0], out

    def test_dir_2019_790_entrata_in_vigore_come_normattiva(self):
        """The 'Entrata in vigore' printed for D.Lgs. 177/2021 must be Normattiva's (12/12/2021).

        CELLAR's `resource_legal_date_entry-into-force` for this MNE holds the GU
        publication date (2021-11-27); the act entered into force after the
        ordinary fifteen-day vacatio legis (art. 73, third paragraph, Cost.;
        art. 10 preleggi), on 12 December 2021.
        """
        out = _call("get_italian_implementation", direttiva="direttiva 2019/790")
        attesa = _dmy_to_iso(_normattiva_eif_dlgs_177())
        assert attesa == _dmy_to_iso(DLGS_177_EIF_FROZEN), attesa
        eif = _field(out, "Entrata in vigore")
        assert eif == [attesa], (
            f"il tool presenta come entrata in vigore {eif}, Normattiva dice {attesa} "
            f"(il dato CELLAR coincide con la data della GU {DLGS_177_GU_DATE_ISO})"
        )

    def test_vacatio_legis_art_73_cost_da_la_data_di_normattiva(self):
        """Art. 73, third paragraph, Cost.: in force on the fifteenth day after publication.

        GU 27/11/2021 + 15 days = 12/12/2021, Normattiva's date: the CELLAR value
        the tool prints (the publication day itself) cannot be the entry into force.
        """
        from datetime import date, timedelta

        assert_parole(
            "art. 73 Costituzione",
            "entrano in vigore il quindicesimo giorno successivo alla loro pubblicazione",
        )
        pubblicazione = date.fromisoformat(DLGS_177_GU_DATE_ISO)
        assert (pubblicazione + timedelta(days=15)).isoformat() == _dmy_to_iso(DLGS_177_EIF_FROZEN)

    def test_regolamento_gdpr_nessuna_trasposizione(self):
        """A regulation (GDPR, 32016R0679) is directly applicable: no query, pointer to cite_law."""
        out = _call("get_italian_implementation", direttiva="32016R0679")
        assert "32016R0679" in out, out
        assert "regolamento UE, direttamente applicabile" in out, out
        assert "cite_law" in out, out
        assert "Decreto legislativo" not in out, out


# ---------------------------------------------------------------------------
# get_eu_basis
# ---------------------------------------------------------------------------


class TestGetEuBasis:
    def _assert_dsm_basis(self, out: str) -> None:
        assert "**Errore**" not in out, out
        assert _headings(out) == [DSM_CELEX], out
        titolo = _field(out, "Titolo")[0]
        assert "Direttiva (UE) 2019/790" in titolo and "17 aprile 2019" in titolo, titolo
        assert "diritto d'autore" in titolo or "diritto d’autore" in titolo, titolo
        assert _field(out, "Termine di trasposizione") == [DSM_DEADLINE_ISO], out
        assert _field(out, "CELLAR URI") == [f"`{DSM_CELLAR_URI}`"], out

    def test_dlgs_177_2021(self):
        """D.Lgs. 177/2021 -> 32019L0790, deadline 2021-06-07, CELLAR URI of the directive."""
        self._assert_dsm_basis(_call("get_eu_basis", atto="D.Lgs. 177/2021"))

    def test_celex_misura_nazionale(self):
        """MNE CELEX 72019L0790ITA_202107973 -> 32019L0790 (same basis as the act reference)."""
        self._assert_dsm_basis(_call("get_eu_basis", atto=DLGS_177_MNE_CELEX))

    def test_termine_coincide_con_art_29_direttiva(self):
        """Art. 29(1) directive 2019/790: 'entro il 7 giugno 2021' == the deadline the tool prints."""
        assert_parole("art. 29 direttiva 2019/790", "entro il 7 giugno 2021")
        out = _call("get_eu_basis", atto="D.Lgs. 177/2021")
        assert _field(out, "Termine di trasposizione") == ["2021-06-07"], out

    def test_celex_misura_senza_id_locale_dlgs_196_2003(self):
        """The CELLAR notice of D.Lgs. 196/2003 exists: by MNE CELEX it maps to 32002L0058."""
        out = _call("get_eu_basis", atto=DLGS_196_MNE_CELEX)
        assert "**Errore**" not in out, out
        assert _headings(out) == [EPRIVACY_CELEX], out

    def test_atto_senza_id_locale_dlgs_196_2003(self):
        """By act reference, 'D.Lgs. 196/2003' must reach the same notice (32002L0058).

        The act-reference query requires `resource_legal_id_local`, which this
        notice (and about half of the Italian ones) lacks: the number and year
        are only in the work title.
        """
        out = _call("get_eu_basis", atto="D.Lgs. 196/2003")
        assert EPRIVACY_CELEX in _headings(out), f"falso 'nessun risultato' per D.Lgs. 196/2003: {out!r}"

    def test_atto_che_recepisce_piu_direttive(self):
        """Legge 238/2021 (legge europea 2019-2020) transposes several directives: all listed."""
        out = _call("get_eu_basis", atto="legge 238/2021")
        assert "**Errore**" not in out, out
        celex = _headings(out)
        assert len(celex) >= 2, out
        assert len(set(celex)) == len(celex), f"direttive duplicate: {celex}"
        assert all(re.fullmatch(r"3\d{4}L\d{4}", c) for c in celex), celex
        assert "32019L2177" in celex, celex
        assert "recepisce più direttive" in out, out


# ---------------------------------------------------------------------------
# elenco_misure_nazionali
# ---------------------------------------------------------------------------


class TestElencoMisureNazionali:
    def test_fra_misure_notificate(self):
        """France: loi n° 2019-775 and ordonnance n° 2021-580 among the measures, all FRA CELEX."""
        out = _call("elenco_misure_nazionali", direttiva="direttiva 2019/790", paese="FRA")
        assert "**Errore**" not in out, out
        mne = _field(out, "CELEX misura nazionale")
        assert FRA_LOI_2019_775 in mne and FRA_ORDONNANCE_2021_580 in mne, mne
        assert all(c.startswith("72019L0790FRA_") for c in mne), mne
        assert "LOI no 2019-775 du 24 juillet 2019" in out, out
        assert "Ordonnance n° 2021-580 du 12 mai 2021" in out, out
        assert set(_field(out, "Direttiva recepita")) == {DSM_CELEX}, out

    def test_fra_intestazione_non_dice_italiano(self):
        """The header of a French answer must not call the measures 'italian'."""
        out = _call("elenco_misure_nazionali", direttiva="direttiva 2019/790", paese="FRA")
        header = out.splitlines()[0]
        assert "italian" not in header.lower(), f"intestazione per paese=FRA: {header!r}"

    def test_fra_numero_atto_nell_intestazione(self):
        """Each heading carries the act number CELLAR provides (e.g. 'Loi n. 2019-775')."""
        out = _call("elenco_misure_nazionali", direttiva="direttiva 2019/790", paese="FRA")
        headings = _headings(out)
        assert any("2019-775" in h for h in headings), f"numero dell'atto perso nelle intestazioni: {headings}"

    def test_paese_senza_misure_messaggio_neutro(self):
        """No measures for GBR (left the EU before the 2021 deadline): the message must not say 'italiana'."""
        out = _call("elenco_misure_nazionali", direttiva="direttiva 2019/790", paese="GBR")
        assert "Nessuna misura nazionale" in out, out
        assert "italiana" not in out.lower(), f"messaggio per paese=GBR: {out!r}"

    def test_ita_coincide_con_get_italian_implementation(self):
        """paese='ITA' gives the same answer as get_italian_implementation (D.Lgs. 177/2021)."""
        out = _call("elenco_misure_nazionali", direttiva="direttiva 2019/790", paese="ITA")
        ref = _call("get_italian_implementation", direttiva="direttiva 2019/790")
        assert out == ref
        assert _field(out, "CELEX misura nazionale") == [DLGS_177_MNE_CELEX], out

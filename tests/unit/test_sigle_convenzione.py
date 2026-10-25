# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, You can obtain one at
# https://mozilla.org/MPL/2.0/.
#
# Adapted from VisuaLex (MPL-2.0), services/visualex/tests/test_nl_parser_convention.py,
# test_codes_default_annex.py and test_act_tables.py at f47ac1b6: their cases, read through this
# package's resolver (``api.leggi_riferimento``) instead of VisuaLex's ``parse_nl_query`` and
# controller, and checked on the identity (URN and allegato). The label cases of ``cite_article``
# are not imported: this package does not write citation labels.
"""The sigle of the source convention read back to the norm they name (G-360, G-366, G-369)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from mcp_legal_it import api
from mcp_legal_it.lib.visualex.map import NORMATTIVA_URN_CODICI

GOLDEN = Path(__file__).resolve().parents[1] / "fixtures" / "visualex" / "golden.json"
RESOLVER = "https://www.normattiva.it/uri-res/N2Ls?"


def _letta(riferimento: str):
    esito = api.leggi_riferimento(riferimento)
    assert esito.esito == "trovato", (riferimento, esito.errore)
    return esito.norma_data[0]


class TestAnnexSigle:
    """VisuaLex's TestAnnexSigle: an annex's sigla is the code's decree at that annex, however it
    is spaced or dotted; «disp att cpa» is the c.p.a.'s implementing rules, never the c.p.a."""

    @pytest.mark.parametrize("riferimento,urn,allegato", [
        ("art. 1 disp. att. c.p.a.", "decreto.legislativo:2010-07-02;104:3~art1", "3"),
        ("art. 1 disp.att.c.p.a.", "decreto.legislativo:2010-07-02;104:3~art1", "3"),
        ("art. 1 disp att cpa", "decreto.legislativo:2010-07-02;104:3~art1", "3"),
        ("art. 1 disp. trans. c.p.a.", "decreto.legislativo:2010-07-02;104:4~art1", "4"),
        ("art. 1 disp. coord. c.p.a.", "decreto.legislativo:2010-07-02;104:5~art1", "5"),
        ("art. 1 disp. att. c.g.c.", "decreto.legislativo:2016-08-26;174:2~art1", "2"),
        ("art. 2 disp. trans. c.g.c.", "decreto.legislativo:2016-08-26;174:3~art2", "3"),
        ("art. 5 cpmg", "regio.decreto:1941-02-20;303:2~art5", "2"),
        ("art. 5 c.p.m.p.", "regio.decreto:1941-02-20;303:1~art5", "1"),
        ("art. 1 reg nav mar", "decreto.del.presidente.della.repubblica:1952-02-15;328:1~art1", "1"),
        ("art. 1 reg. nav. mar.", "decreto.del.presidente.della.repubblica:1952-02-15;328:1~art1", "1"),
        ("art. 1 disp att cpp", "decreto.legislativo:1989-07-28;271:1~art1", "1"),
        # the disposizioni di attuazione however written, never the code they implement
        ("art. 3 disp att cc", "regio.decreto:1942-03-30;318:1~art3", "1"),
        ("art. 3 disp.att.c.c.", "regio.decreto:1942-03-30;318:1~art3", "1"),
        ("art. 3 disp att cpc", "regio.decreto:1941-12-18;1368:1~art3", "1"),
        ("art. 3 disp. att. c.p.c.", "regio.decreto:1941-12-18;1368:1~art3", "1"),
        ("art. 1 cod nav", "regio.decreto:1942-03-30;327:1~art1", "1"),
    ])
    def test_the_code_and_its_annex(self, riferimento, urn, allegato):
        nd = _letta(riferimento)
        assert (nd.urn, nd.allegato) == (f"urn:nir:stato:{urn}", allegato)

    @pytest.mark.parametrize("riferimento,tipo_atto", [
        ("art. 29 c.p.a.", "codice del processo amministrativo"),
        ("art. 69 cod. nav.", "codice della navigazione"),
        ("art. 20 cod. post.", "codice postale e delle telecomunicazioni"),
        ("art. 52 c.g.c.", "codice di giustizia contabile"),
        ("art. 2 c.p.", "codice penale"),
    ])
    def test_a_code_sigla_is_the_code(self, riferimento, tipo_atto):
        # G-366: the four codes the convention cites by sigla, like the c.c. and the c.p.
        nd = _letta(riferimento)
        assert nd.tipo_atto == tipo_atto
        assert nd.urn.endswith(f"{NORMATTIVA_URN_CODICI[tipo_atto]}~art{riferimento.split()[1]}")

    def test_a_sigla_is_never_read_inside_a_longer_name(self):
        assert api.leggi_riferimento("art. 1 disp. att. c.p.a. bis").esito == "atto_non_riconosciuto"


class TestActsWhoseTextIsTheirAnnex:
    """VisuaLex's ANNEXED_ACTS at f47ac1b6: without «:1» art. 1 is the approving decree's."""

    @pytest.mark.parametrize("riferimento,urn", [
        ("art. 1 legge fallimentare", "regio.decreto:1942-03-16;267:1~art1"),
        ("art. 216 legge fallimentare", "regio.decreto:1942-03-16;267:1~art216"),
        ("art. 1, r.d. 16 marzo 1942, n. 267", "regio.decreto:1942-03-16;267:1~art1"),
        ("art. 1 d.p.r. 448/1988", "decreto.del.presidente.della.repubblica:1988-01-01;448:1~art1"),
        ("art. 1 d.lgs. 346/1990", "decreto.legislativo:1990-01-01;346:1~art1"),
        ("art. 86 r.d. 773/1931", "regio.decreto:1931-01-01;773:1~art86"),
    ])
    def test_the_article_is_the_annex_s(self, riferimento, urn):
        nd = _letta(riferimento)
        assert (nd.urn, nd.allegato) == (f"urn:nir:stato:{urn}", "1")


class TestFirstOfTheMonth:
    """VisuaLex's TestFirstOfTheMonth: «1° settembre», as the Gazzetta Ufficiale writes it."""

    @pytest.mark.parametrize("riferimento", [
        "art. 127, d.lgs. 1° settembre 1993, n. 385",
        "art. 127, d.lgs. 1º settembre 1993, n. 385",
        "art. 127 d.lgs. 1 ° settembre 1993 n. 385",
        "art. 127, d.lgs. 1°settembre 1993, n. 385",
    ])
    def test_the_day_is_kept(self, riferimento):
        assert _letta(riferimento).urn == "urn:nir:stato:decreto.legislativo:1993-09-01;385~art127"


#: Golden labels this package does not read back to the convention's identity, and why.
NON_RILETTE = {
    "turismo-32": "a code cited by its decree: the annex is found at the lookup (testo_articolo), not in the reference",
    "dlgs-81-2008-annex-a": "an annex named «A» is a name here, not the URN's position",
    "dpcm-2020-03-08-1": "an act with no number: citations/URN step, not yet",
}


def _etichette():
    norms = json.loads(GOLDEN.read_text(encoding="utf-8"))["norms"]
    out = []
    for norm in norms:
        identita = (norm.get("identity", {}).get("article") or {}).get("value")
        if not identita or not identita.startswith(RESOLVER):
            continue  # an EU act (celex: identity) or no identity asserted
        for kind in ("citation", "short"):
            label = (norm["labels"].get(kind) or {}).get("value")
            if label:
                out.append((norm, kind, label, identita))
    return out


@pytest.mark.parametrize("norm,kind,label,identita", _etichette(),
                         ids=[f"{n['id']}:{k}" for n, k, _, _ in _etichette()])
def test_a_convention_label_reads_back_to_its_norm(norm, kind, label, identita):
    # VisuaLex's test_a_convention_label_reads_back_to_its_norm: a short label carries the year
    # alone, and its day is the lookup's to read, so only the year is compared for it.
    esito = api.leggi_riferimento(label)
    nd = esito.norma_data[0] if esito.esito == "trovato" else None
    urn = RESOLVER + nd.urn if nd is not None and nd.urn else None
    if kind == "short" and nd is not None and not nd.data_risolta:
        identita = re.sub(r":(\d{4})-\d{2}-\d{2}(?=;)", r":\1-01-01", identita, count=1)
    if norm["id"] in NON_RILETTE:
        assert urn != identita, f"read back now, remove it from NON_RILETTE: {norm['id']}"
        pytest.xfail(NON_RILETTE[norm["id"]])
    assert esito.esito == "trovato", (label, esito.errore)
    assert urn == identita, label

"""NORMATTIVA_URN_CODICI agrees with ATTI_DENOMINATI and BROCARDI_CODICI on each code's date.

The disposizioni di attuazione del c.p.c. (R.D. 18 dicembre 1941, n. 1368) were dated
1941-08-25 in the URN table: Normattiva tolerated the date and served the right text,
but cite_law handed the user a citation (atto.data, URN, URL) with the wrong date.
Three tables state the same facts; this test makes them agree.
"""

import re

import pytest

from mcp_legal_it.lib.visualex import map as m


def _urn_estremi(urn: str):
    match = re.match(r"^([a-z.]+):(\d{4}-\d{2}-\d{2});(\d+)", urn)
    return (match.group(1).replace(".", " "), match.group(2), match.group(3)) if match else None


def _altre_fonti():
    for nome, atto in m.ATTI_DENOMINATI.items():
        yield f"ATTI_DENOMINATI[{nome!r}]", atto["tipo_atto"], atto.get("data", ""), atto.get("numero_atto", "")
    for etichetta in m.BROCARDI_CODICI:
        estremi = m.parse_brocardi_estremi(etichetta)
        if estremi:
            yield f"BROCARDI_CODICI[{etichetta!r}]", estremi["tipo_atto"], estremi["data"], estremi["numero_atto"]


CODICI = [(nome, _urn_estremi(urn)) for nome, urn in m.NORMATTIVA_URN_CODICI.items() if _urn_estremi(urn)]


@pytest.mark.parametrize("nome, estremi", CODICI, ids=[nome[:40] for nome, _ in CODICI])
def test_same_act_same_date(nome, estremi):
    tipo, data, numero = estremi
    discordanti = [
        f"{fonte}: {altra_data}"
        for fonte, altro_tipo, altra_data, altro_numero in _altre_fonti()
        # same type, number and year: the same act, so the full date must agree
        if altro_tipo == tipo and altro_numero == numero and altra_data[:4] == data[:4] and altra_data != data
    ]
    assert not discordanti, f"{nome} ({data}, n. {numero}) vs {discordanti}"


def test_disposizioni_attuazione_cpc_date():
    assert m.NORMATTIVA_URN_CODICI[
        "disposizioni per l'attuazione del Codice di procedura civile e disposizioni transitorie"
    ] == "regio.decreto:1941-12-18;1368:1"


def test_the_cross_check_sees_most_codes():
    # Guard against the check silently matching nothing (a format change in a table).
    tipi_numeri = {(t, n) for _, t, _, n in _altre_fonti()}
    coperti = [nome for nome, (t, _, n) in CODICI if (t, n) in tipi_numeri]
    assert len(coperti) >= 25, coperti

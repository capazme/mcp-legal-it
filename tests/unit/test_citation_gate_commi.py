"""The citation gate and articles Normattiva splits into parts: a comma not read is not credited.

An article Normattiva splits (art. 1 L. 296/2006: 14 parts of up to 100 commi) comes from
cite_law one part at a time, with the notice «testo parziale: commi a-b di N». The gate
records the commi read for (act, article): a later answer citing a comma outside every
range read is asked to read it. A citation with no comma, an article read whole, and a comma
in a range read are credited as before. Both readers are run (the server's and the hook's
stdlib fallback), and they are compared on the same sentences.
"""

from __future__ import annotations

import importlib.util
import sys

import pytest

from tests.unit.test_citation_gate import HOOK, NAGS, SILENT, isolated_hook, run, session  # noqa: F401

FONTE = "**Fonte**: Normattiva — https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:legge:2006-12-27;296~art1"


def parte(dal: str, al: str, primo: str, *, comma: bool = True) -> str:
    """A cite_law answer of one part of art. 1 L. 296/2006, as the tool writes it."""
    coda = "" if comma else "; per un comma, citarlo nel riferimento (es. «art. 1, comma 773, L. 296/2006»)"
    return (f"{FONTE}\n\n**Attenzione**: testo parziale: commi {dal}-{al} di 1364 (l'articolo è diviso in 14 "
            f"parti su Normattiva){coda}.\n\n**Commi {dal}-{al}** (parte 1 di 14 dell'articolo su Normattiva)\n\n"
            f"Art. 1\n\n{primo}. Testo del comma.")


INTERO = f"{FONTE}\n\nArt. 1\n\n1. Testo del comma."


def _gate(t, fallback, hook):
    payload = {"transcript_path": str(t.write()), "hook_event_name": "Stop"}
    if fallback:
        return run(payload, python_args=("-I", "-S"), hook=hook)
    return run(payload)


@pytest.fixture(params=[False, True], ids=["server", "fallback"])
def lettore(request, isolated_hook):  # noqa: F811
    return request.param, isolated_hook


def test_a_comma_outside_the_part_read_is_not_credited(tmp_path, lettore):
    t = session(tmp_path).prompt().cite_law("art. 1 L. 296/2006", parte("1", "100", "1", comma=False))
    t.say("L'art. 1, comma 773, L. 296/2006 ridetermina l'aliquota.")
    done = _gate(t, *lettore)
    assert done.returncode == NAGS
    assert "cite_law con il comma 773" in done.stderr


@pytest.mark.parametrize("frase", [
    "L'art. 1, comma 50, L. 296/2006 dispone così.",
    "L'art. 1 L. 296/2006 dispone così.",  # no comma: the article, as before
])
def test_a_comma_in_the_part_read_or_no_comma_is_credited(tmp_path, lettore, frase):
    t = session(tmp_path).prompt().cite_law("art. 1 L. 296/2006", parte("1", "100", "1", comma=False)).say(frase)
    assert _gate(t, *lettore).returncode == SILENT


@pytest.mark.parametrize("frase", [
    "L'art. 1, comma 773, L. 296/2006 ridetermina l'aliquota.",
    "L'art. 1, co. 773-bis, L. 296/2006 ridetermina l'aliquota.",
    "Il comma 773 dell'art. 1 L. 296/2006 ridetermina l'aliquota.",
])
def test_the_part_of_the_comma_read_credits_it(tmp_path, lettore, frase):
    t = session(tmp_path).prompt().cite_law("art. 1, comma 773, L. 296/2006", parte("701", "800", "701")).say(frase)
    assert _gate(t, *lettore).returncode == SILENT


def test_the_ranges_of_several_reads_add_up(tmp_path, lettore):
    t = (session(tmp_path).prompt()
         .cite_law("art. 1 L. 296/2006", parte("1", "100", "1", comma=False))
         .cite_law("art. 1, comma 773, L. 296/2006", parte("701", "800", "701"))
         .say("L'art. 1, comma 50, L. 296/2006 e l'art. 1, comma 773, L. 296/2006 dispongono così."))
    assert _gate(t, *lettore).returncode == SILENT
    t.say("L'art. 1, comma 1000, L. 296/2006 dispone altro.")
    assert _gate(t, *lettore).returncode == NAGS


def test_a_whole_read_credits_every_comma(tmp_path, lettore):
    t = (session(tmp_path).prompt()
         .cite_law("art. 1 L. 296/2006", parte("1", "100", "1", comma=False))
         .cite_law("art. 1 L. 296/2006", INTERO)
         .say("L'art. 1, comma 1000, L. 296/2006 dispone altro."))
    assert _gate(t, *lettore).returncode == SILENT


def test_an_article_never_split_is_credited_as_before(tmp_path, lettore):
    t = session(tmp_path).prompt().cite_law("art. 1 L. 296/2006", INTERO).say(
        "L'art. 1, comma 773, L. 296/2006 ridetermina l'aliquota.")
    assert _gate(t, *lettore).returncode == SILENT


def _fallback_reader():
    spec = importlib.util.spec_from_file_location("citation_gate_hook", HOOK)
    modulo = importlib.util.module_from_spec(spec)
    sys.modules["citation_gate_hook"] = modulo
    spec.loader.exec_module(modulo)
    return modulo.FallbackReader()


@pytest.mark.parametrize("frase, comma", [
    ("art. 1, comma 773, L. 296/2006", "773"),
    ("art. 1 co. 773-bis L. 296/2006", "773-bis"),
    ("art. 1, c. 12 ter, L. 296/2006", "12-ter"),
    ("il comma 773 dell'art. 1 L. 296/2006", "773"),
    ("art. 1 L. 296/2006", None),
])
def test_both_readers_read_the_same_comma(frase, comma):
    from mcp_legal_it.core import citazioni

    server = citazioni.norme_nel_testo(frase)
    fallback = _fallback_reader().norme_nel_testo(frase)
    assert [n.comma for n in server] == [n.comma for n in fallback] == [comma]


@pytest.mark.parametrize("testo, letti", [
    (parte("701", "800", "701"), ("701", "800")),
    ('{"avvisi": ["testo parziale: commi 1-100 di 1364 (l\'articolo è diviso in 14 parti su Normattiva)"]}', ("1", "100")),
    (INTERO, None),
])
def test_both_readers_read_the_same_range(testo, letti):
    from mcp_legal_it.core import citazioni

    fallback = _fallback_reader()
    assert citazioni.commi_letti(testo) == fallback.commi_letti(testo) == letti
    for comma, dentro in (("773", True), ("800-bis", True), ("801", False), ("700", False)):
        assert citazioni.comma_nell_intervallo(comma, "701", "800") is dentro
        assert fallback.comma_nell_intervallo(comma, "701", "800") is dentro

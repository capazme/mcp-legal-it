import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "corpus_toolnames", Path(__file__).parents[2] / "scripts" / "corpus" / "toolnames.py"
)
tn = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(tn)

VOCAB = ["cite_law", "cerca_brocardi", "leggi_sentenza", "interessi_legali"]

def test_strip_prefixes_backticked_and_bare():
    text = "Chiama `legal-it:cite_law`, poi legal-it:cerca_giurisprudenza_unificata(q).\n"
    out, found = tn.strip_prefixes(text)
    assert out == "Chiama `cite_law`, poi cerca_giurisprudenza_unificata(q).\n"
    assert found == ["cerca_giurisprudenza_unificata", "cite_law"]

def test_add_prefixes_backticked_bare_and_called():
    text = "Usa `cite_law` e poi leggi_sentenza(numero, anno).\n"
    out = tn.add_prefixes(text, ["cite_law", "leggi_sentenza"])
    assert out == "Usa `legal-it:cite_law` e poi legal-it:leggi_sentenza(numero, anno).\n"

def test_add_prefixes_never_double_prefixes():
    text = "`legal-it:cite_law` e mcp__legal-it__cite_law restano intatti.\n"
    assert tn.add_prefixes(text, ["cite_law"]) == text

def test_roundtrip_is_byte_identical():
    original = "1. `legal-it:interessi_legali`\n2. legal-it:cite_law(rif)\n"
    stripped, found = tn.strip_prefixes(original)
    assert tn.add_prefixes(stripped, found) == original

def test_find_bare_tools_uses_vocabulary_only():
    text = "Chiama `cite_law`; il campo eta_vittima non è un tool.\n"
    assert tn.find_bare_tools(text, VOCAB) == ["cite_law"]

def test_word_boundaries_protect_similar_names():
    text = "interessi_legali_extra non è interessi_legali.\n"
    out = tn.add_prefixes(text, ["interessi_legali"])
    assert out == "interessi_legali_extra non è legal-it:interessi_legali.\n"

def test_file_paths_are_never_prefixed():
    text = "Vedi `data/contributo_unificato.json` per gli scaglioni.\n"
    assert tn.add_prefixes(text, ["contributo_unificato"]) == text
    assert tn.find_bare_tools(text, ["contributo_unificato"]) == []

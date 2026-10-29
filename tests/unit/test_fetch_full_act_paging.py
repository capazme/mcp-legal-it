"""fetch_full_act reads a long act in windows instead of returning it whole.

Before the cap, L. 300/1970 alone came back as ~52,000 characters and the
Codice civile as about two million: one call could fill the model's context.
"""

import pytest

from mcp_legal_it.tools import legal_citations as lc

WINDOW = lc._FULL_ACT_WINDOW
URL = "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:legge:1970-05-20;300"


def _serve(monkeypatch, text):
    async def fake(norma):
        return {"text": text, "title": "LEGGE 20 maggio 1970, n. 300", "url": URL}

    monkeypatch.setattr(lc, "fetch_normattiva_full_text", fake)


def _long_text():
    # Distinct numbered lines, so every position in the text is recognisable.
    lines, n = [], 0
    while sum(len(x) + 1 for x in lines) < 2 * WINDOW + 5000:
        n += 1
        lines.append(f"riga {n:06d} del testo dell'atto")
    return "\n".join(lines)


@pytest.mark.asyncio
async def test_short_act_answer_is_unchanged(monkeypatch):
    text = "Art. 1\nTesto breve dell'atto, ben sotto il limite della finestra."
    _serve(monkeypatch, text)
    out = await lc._fetch_full_act_impl("L. 300/1970")
    assert out == "\n".join([
        "# LEGGE 20 maggio 1970, n. 300",
        f"**Fonte**: Normattiva — {URL}",
        f"**Dimensione**: {len(text):,} caratteri\n",
        text,
    ])
    assert "da_carattere" not in out


@pytest.mark.asyncio
async def test_long_act_first_window_says_how_to_read_on(monkeypatch):
    text = _long_text()
    _serve(monkeypatch, text)
    out = await lc._fetch_full_act_impl("L. 300/1970")
    assert text[:WINDOW] in out
    assert text[WINDOW:WINDOW + 40] not in out
    assert f"*[Caratteri 1-{WINDOW} su {len(text)} totali: " in out
    assert out.rstrip().endswith(f"da_carattere={WINDOW + 1}]*")
    # The header still states the size of the whole act.
    assert f"**Dimensione**: {len(text):,} caratteri" in out


@pytest.mark.asyncio
async def test_windows_cover_the_whole_text_without_gaps(monkeypatch):
    text = _long_text()
    _serve(monkeypatch, text)
    start, pieces = 1, []
    while True:
        out = await lc._fetch_full_act_impl("L. 300/1970", da_carattere=start)
        body = out.split(" caratteri\n\n", 1)[1].rsplit("\n\n*[Caratteri ", 1)[0]
        pieces.append(body)
        if "fine del testo" in out:
            break
        start = int(out.rsplit("da_carattere=", 1)[1].split("]", 1)[0])
    assert "".join(pieces) == text
    assert len(pieces) == 3


@pytest.mark.asyncio
async def test_start_beyond_the_end(monkeypatch):
    text = _long_text()
    _serve(monkeypatch, text)
    out = await lc._fetch_full_act_impl("L. 300/1970", da_carattere=len(text) + 10)
    assert f"oltre la fine del testo ({len(text)} caratteri)" in out


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", [0, -3, True])
async def test_invalid_start_is_an_error(monkeypatch, bad):
    _serve(monkeypatch, _long_text())
    out = await lc._fetch_full_act_impl("L. 300/1970", da_carattere=bad)
    assert out.startswith("**Errore**: da_carattere deve essere un intero")


@pytest.mark.asyncio
async def test_tool_exposes_the_optional_parameter():
    from mcp_legal_it.server import mcp

    tool = await mcp.get_tool("fetch_full_act")
    props = tool.parameters["properties"]
    assert props["da_carattere"]["default"] == 1
    assert tool.parameters.get("required") == ["reference"]

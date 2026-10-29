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
    await lc._fetch_full_act_impl("L. 300/1970")
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


# ---------------------------------------------------------------------------
# One reading per act: the windows are cut from the same text
# ---------------------------------------------------------------------------


def _counting(monkeypatch, texts, source=None):
    """Serve ``texts`` one reading after the other; returns the list of readings made."""
    calls = []

    async def fake(norma):
        from mcp_legal_it.lib import _sources

        _sources.note("normattiva", URL)
        text = texts[min(len(calls), len(texts) - 1)]
        calls.append(norma)
        out = {"text": text, "title": "LEGGE 20 maggio 1970, n. 300", "url": URL}
        if source:
            out["source"] = source
        return out

    monkeypatch.setattr(lc, "fetch_normattiva_full_text", fake)
    return calls


@pytest.mark.asyncio
async def test_a_later_window_reads_nothing_again(monkeypatch):
    from mcp_legal_it.lib import _sources

    calls = _counting(monkeypatch, [_long_text()])
    with _sources.recording() as first:
        await lc._fetch_full_act_impl("L. 300/1970")
    with _sources.recording() as consulted:
        second = await lc._fetch_full_act_impl("L. 300/1970", da_carattere=WINDOW + 1)
        third = await lc._fetch_full_act_impl("L. 300/1970", da_carattere=2 * WINDOW + 1)
    assert len(calls) == 1
    # The windows reused the reading, and still declare where their text came from.
    assert first and consulted == first
    assert f"*[Caratteri {WINDOW + 1}-{2 * WINDOW} su " in second
    assert "fine del testo" in third


@pytest.mark.asyncio
async def test_a_new_day_reads_the_act_again(monkeypatch):
    calls = _counting(monkeypatch, [_long_text()])
    monkeypatch.delenv("LEGAL_TODAY", raising=False)  # it would win over LEGAL_NOW
    monkeypatch.setenv("LEGAL_NOW", "2026-10-29T10:00:00")
    await lc._fetch_full_act_impl("L. 300/1970")
    monkeypatch.setenv("LEGAL_NOW", "2026-10-30T10:00:00")
    await lc._fetch_full_act_impl("L. 300/1970")
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_a_changed_reading_is_refused_not_served_shifted(monkeypatch):
    text = _long_text()
    _counting(monkeypatch, [text, "riga in più\n" + text])
    await lc._fetch_full_act_impl("L. 300/1970")
    lc._FULL_ACT_TEXTS.clear()  # the text left memory, its reading did not
    out = await lc._fetch_full_act_impl("L. 300/1970", da_carattere=WINDOW + 1)
    assert out.startswith("**Errore**: il testo dell'atto letto ora non coincide")
    assert "da_carattere=1" in out


@pytest.mark.asyncio
async def test_the_same_reading_again_is_served(monkeypatch):
    calls = _counting(monkeypatch, [_long_text()])
    await lc._fetch_full_act_impl("L. 300/1970")
    lc._FULL_ACT_TEXTS.clear()
    out = await lc._fetch_full_act_impl("L. 300/1970", da_carattere=WINDOW + 1)
    assert len(calls) == 2
    assert f"*[Caratteri {WINDOW + 1}-" in out
    # Read again, even if the same text: the window says so.
    assert "*[Testo riletto dalla fonte:" in out


@pytest.mark.asyncio
async def test_a_lost_article_by_article_reading_is_refused(monkeypatch):
    # A later window with nothing in memory (say, after a restart): a per-article
    # reading may not match the one the previous window was cut from.
    _counting(monkeypatch, [_long_text()])
    out = await lc._fetch_full_act_impl("L. 300/1970", da_carattere=WINDOW + 1)
    assert out.startswith("**Errore**: il testo da cui è stata tagliata la finestra precedente")


@pytest.mark.asyncio
async def test_a_lost_akn_reading_is_served_and_says_so(monkeypatch):
    _counting(monkeypatch, [_long_text()], source="normattiva-akn")
    out = await lc._fetch_full_act_impl("L. 300/1970", da_carattere=WINDOW + 1)
    riletto = out.index("*[Testo riletto dalla fonte:")
    paging = out.index(f"*[Caratteri {WINDOW + 1}-")
    # The paging note stays last: the citation gate reads it there.
    assert riletto < paging
    assert "le posizioni possono non coincidere con la finestra precedente" in out


@pytest.mark.asyncio
async def test_errors_are_not_kept(monkeypatch):
    calls = []

    async def failing(norma):
        calls.append(norma)
        return {"text": "", "title": "", "url": "", "error": "Could not generate URL"}

    monkeypatch.setattr(lc, "fetch_normattiva_full_text", failing)
    for _ in range(2):
        assert (await lc._fetch_full_act_impl("L. 300/1970")).startswith("**Errore**")
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_concurrent_first_reads_share_one_reading(monkeypatch):
    import asyncio

    calls = []
    gate = asyncio.Event()

    async def slow(norma):
        calls.append(norma)
        await gate.wait()
        return {"text": _long_text(), "title": "LEGGE 20 maggio 1970, n. 300", "url": URL,
                "source": "normattiva-html", "completo": True}

    monkeypatch.setattr(lc, "fetch_normattiva_full_text", slow)
    readers = [asyncio.create_task(lc._fetch_full_act_impl("L. 300/1970")) for _ in range(3)]
    await asyncio.sleep(0)
    gate.set()
    answers = await asyncio.gather(*readers)
    assert len(calls) == 1
    assert len(set(answers)) == 1
    assert not lc._FULL_ACT_LOCKS


@pytest.mark.asyncio
@pytest.mark.parametrize("partial", [
    {"completo": False},                       # only art. 1 (index unread), or articles skipped
])
async def test_a_partial_reading_is_served_but_not_kept(monkeypatch, partial):
    calls = _counting(monkeypatch, [_long_text()])
    original = lc.fetch_normattiva_full_text

    async def incomplete(norma):
        return {**(await original(norma)), **partial}

    monkeypatch.setattr(lc, "fetch_normattiva_full_text", incomplete)
    first = await lc._fetch_full_act_impl("L. 300/1970")
    assert f"*[Caratteri 1-{WINDOW} su " in first
    assert not lc._FULL_ACT_TEXTS and not lc._FULL_ACT_READINGS
    later = await lc._fetch_full_act_impl("L. 300/1970", da_carattere=WINDOW + 1)
    assert later.startswith("**Errore**: il testo da cui è stata tagliata la finestra precedente")
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_the_day_is_the_italian_one(monkeypatch):
    seen = []
    monkeypatch.setattr(lc._clock, "rome_day_unrecorded", lambda: seen.append(1) or __import__("datetime").date(2026, 10, 30))
    _counting(monkeypatch, [_long_text()])
    await lc._fetch_full_act_impl("L. 300/1970")
    assert seen and all(key[-1] == "2026-10-30" for key in lc._FULL_ACT_TEXTS)


# ---------------------------------------------------------------------------
# The citation gate on the windows this tool really writes
# ---------------------------------------------------------------------------


def _act_cut_in_a_heading():
    """An act whose second window opens inside «vedi art. 7» («art. 7», a reference,
    not a heading) and ends inside «Art. 41» («Art. 4»)."""
    filler = "x" * 70 + "\n"
    text = ("Art. 1\nPrimo articolo.\n" + filler * (WINDOW // len(filler) + 1))[: WINDOW - 6] + "\nvedi "
    text += "art. 7 della legge\n"
    text = (text + filler * (WINDOW // len(filler) + 1))[: 2 * WINDOW - 7]
    return text + "\nArt. 41\nQuarantunesimo.\n" + filler * 50


def _fallback_reader():
    import importlib.util
    from pathlib import Path

    hook = Path(__file__).resolve().parents[2] / "plugin" / "hooks" / "citation-gate.py"
    spec = importlib.util.spec_from_file_location("citation_gate_for_test", hook)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.FallbackReader()


@pytest.mark.asyncio
@pytest.mark.parametrize("re_read", [False, True])
async def test_gate_does_not_credit_headings_a_window_cut(monkeypatch, re_read):
    from mcp_legal_it.core.citazioni import articoli_serviti

    text = _act_cut_in_a_heading()
    window_2 = text[WINDOW: 2 * WINDOW]
    assert window_2.endswith("\nArt. 4") and window_2.lstrip("\n").split("\n")[0].startswith("art. 7")
    _counting(monkeypatch, [text], source="normattiva-akn")
    await lc._fetch_full_act_impl("L. 300/1970")
    if re_read:
        lc._FULL_ACT_TEXTS.clear()
        lc._FULL_ACT_READINGS.clear()
    out = await lc._fetch_full_act_impl("L. 300/1970", da_carattere=WINDOW + 1)
    assert ("*[Testo riletto dalla fonte:" in out) is re_read
    for credited in (articoli_serviti(out), _fallback_reader().articoli_serviti(out)):
        assert "4" not in credited and "7" not in credited


@pytest.mark.asyncio
async def test_incomplete_readings_still_run_one_at_a_time(monkeypatch):
    # An incomplete reading is not kept, so every caller reads again: one at a time,
    # also for callers that arrive while others wait (the lock must not be replaced).
    import asyncio

    in_flight, peak, readings = 0, 0, 0

    async def partial(norma):
        nonlocal in_flight, peak, readings
        in_flight += 1
        readings += 1
        peak = max(peak, in_flight)
        await asyncio.sleep(0.01)
        in_flight -= 1
        return {"text": _long_text(), "title": "LEGGE 20 maggio 1970, n. 300", "url": URL,
                "source": "normattiva-html", "completo": False}

    monkeypatch.setattr(lc, "fetch_normattiva_full_text", partial)
    callers = [asyncio.create_task(lc._fetch_full_act_impl("L. 300/1970")) for _ in range(5)]
    for _ in range(10):
        await asyncio.sleep(0.004)
        callers.append(asyncio.create_task(lc._fetch_full_act_impl("L. 300/1970")))
    await asyncio.gather(*callers)
    assert readings == 15
    assert peak == 1
    assert not lc._FULL_ACT_LOCKS

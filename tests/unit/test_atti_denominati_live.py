"""Live gate over the curated act tables — run by hand before a release.

Every act in ATTI_DENOMINATI, and every Italian act of ATTI_NOTI, is asked of
Normattiva by URN; the act that comes back must carry the date and number the
table claims. An Italian act of ATTI_NOTI with the year alone is refused before
any request. A typo'd number usually lands on an act published on a different
date, which this catches. It cannot catch a wrong number that happens to belong
to an act of the same date — only reading does — so treat a green run as
"no drift", not "certified correct".

    .venv/bin/pytest tests/unit/test_atti_denominati_live.py -m live -q

Excluded from the default run (pyproject sets `-m 'not live'`): it makes ~100
network requests and takes a couple of minutes.
"""

import asyncio
import html as htmllib
import re

import httpx
import pytest

from mcp_legal_it.lib.visualex.map import _ATTI_DENOMINATI_SPEC, ATTI_NOTI

pytestmark = pytest.mark.live

NORMATTIVA_BASE = "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:"
CELLAR_BASE = "https://publications.europa.eu/resource/celex/"

MESI = (
    "gennaio febbraio marzo aprile maggio giugno luglio agosto "
    "settembre ottobre novembre dicembre".split()
)

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; mcp-legal-it test suite)"}


def _italian_date(iso: str) -> str:
    """'1970-05-20' → '20 maggio 1970', as Normattiva writes it in the title."""
    year, month, day = iso.split("-")
    return f"{int(day)} {MESI[int(month) - 1]} {year}"


def _title(body: str) -> str:
    match = re.search(r"<title>(.*?)</title>", body, re.S | re.I)
    if not match:
        return ""
    return re.sub(r"\s+", " ", htmllib.unescape(match.group(1))).strip()


async def _check_normattiva(client, tipo, data, numero, aliases):
    urn = f"{tipo.replace(' ', '.')}:{data};{numero}"
    url = f"{NORMATTIVA_BASE}{urn}"
    try:
        response = await client.get(url)
    except Exception as exc:  # network flake, not a data problem — report as-is
        return f"{aliases[0]}: richiesta fallita ({type(exc).__name__}) — {url}"

    title = _title(response.text)
    expected_date = _italian_date(data)
    if expected_date not in title or f"n. {numero}" not in title:
        return (
            f"{aliases[0]}: la tabella dice «{expected_date}, n. {numero}», "
            f"Normattiva risponde «{title}» — {url}"
        )
    return None


def _celex(entry: dict) -> str | None:
    """CELEX of an EU regulation/directive in ATTI_NOTI, if it is one."""
    kind = {"regolamento ue": "R", "direttiva ue": "L"}.get(entry["tipo_atto"])
    if not kind or not entry.get("data") or not entry.get("numero_atto"):
        return None
    year = entry["data"].split("-")[0]
    return f"3{year}{kind}{entry['numero_atto'].zfill(4)}"


async def _check_eurlex(client, celex, name):
    try:
        response = await client.get(f"{CELLAR_BASE}{celex}")
    except Exception as exc:
        return f"{name}: richiesta fallita ({type(exc).__name__}) — CELEX {celex}"
    if response.status_code != 200:
        return f"{name}: CELEX {celex} non esiste su CELLAR (HTTP {response.status_code})"
    return None


class TestAttiDenominatiLive:
    async def test_every_act_matches_normattiva(self):
        semaphore = asyncio.Semaphore(5)

        async def guarded(client, *args):
            async with semaphore:
                return await _check_normattiva(client, *args)

        async with httpx.AsyncClient(
            follow_redirects=True, timeout=45, headers=HEADERS
        ) as client:
            problems = await asyncio.gather(
                *[guarded(client, *row) for row in _ATTI_DENOMINATI_SPEC]
            )

        failures = [p for p in problems if p]
        assert not failures, "\n".join(
            [f"{len(failures)}/{len(_ATTI_DENOMINATI_SPEC)} atti non corrispondono:"] + failures
        )

    async def test_every_eu_act_exists_on_eurlex(self):
        targets = [
            (celex, name)
            for name, entry in ATTI_NOTI.items()
            if (celex := _celex(entry))
        ]
        # One request per distinct act, not per alias
        unique = {celex: name for celex, name in targets}

        semaphore = asyncio.Semaphore(5)

        async def guarded(client, celex, name):
            async with semaphore:
                return await _check_eurlex(client, celex, name)

        async with httpx.AsyncClient(
            follow_redirects=True, timeout=45, headers=HEADERS
        ) as client:
            problems = await asyncio.gather(
                *[guarded(client, celex, name) for celex, name in unique.items()]
            )

        failures = [p for p in problems if p]
        assert not failures, "\n".join(
            [f"{len(failures)}/{len(unique)} atti UE non trovati:"] + failures
        )

    async def test_every_italian_act_noto_matches_normattiva(self):
        # One request per distinct act, one at a time with a pause; the count is printed
        # before the first one. An Italian act with the year alone resolves to a placeholder
        # date, so it is refused before any request.
        acts: dict[tuple[str, str, str], list[str]] = {}
        year_only = []
        for name, entry in ATTI_NOTI.items():
            if entry["tipo_atto"] in ("regolamento ue", "direttiva ue"):
                continue  # EU acts are cited by year
            if re.fullmatch(r"\d{4}", entry.get("data", "")):
                year_only.append(name)
            elif re.fullmatch(r"\d{4}-\d{2}-\d{2}", entry.get("data", "")):
                key = (entry["tipo_atto"], entry["data"], entry["numero_atto"])
                acts.setdefault(key, []).append(name)
        assert not year_only, f"atti italiani con il solo anno in ATTI_NOTI: {year_only}"
        assert acts, "no Italian act with a full date in ATTI_NOTI"
        print(f"\nATTI_NOTI: {len(acts)} richieste a Normattiva, una alla volta")

        problems = []
        async with httpx.AsyncClient(
            follow_redirects=True, timeout=45, headers=HEADERS
        ) as client:
            for i, ((tipo, data, numero), aliases) in enumerate(acts.items()):
                if i:
                    await asyncio.sleep(2)
                problems.append(await _check_normattiva(client, tipo, data, numero, aliases))

        failures = [p for p in problems if p]
        assert not failures, "\n".join(
            [f"{len(failures)}/{len(acts)} atti di ATTI_NOTI non corrispondono:"] + failures
        )

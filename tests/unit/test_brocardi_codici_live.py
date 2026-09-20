"""Live gate over BROCARDI_CODICI — run by hand before a release.

Every URL in the table is fetched: a page that has moved or been dropped by
Brocardi answers 404 (or redirects to the home page), and the act it served
would silently lose its dottrina and massime. The fonti index at
brocardi.it/fonti.html is compared too, so a source Brocardi adds shows up as
a failure here instead of staying unmapped.

    .venv/bin/pytest tests/unit/test_brocardi_codici_live.py -m live -q

Excluded from the default run (pyproject sets `-m 'not live'`): ~100 requests.
"""

import asyncio
from urllib.parse import urlparse

import httpx
import pytest
from bs4 import BeautifulSoup

from src.lib.visualex.map import BROCARDI_CODICI

pytestmark = pytest.mark.live

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; mcp-legal-it test suite)"}
FONTI_URL = "https://www.brocardi.it/fonti.html"


async def _check_page(client: httpx.AsyncClient, label: str, url: str) -> str | None:
    try:
        resp = await client.get(url)
    except httpx.HTTPError as exc:
        return f"{label}: {url} → {exc!r}"
    if resp.status_code != 200:
        return f"{label}: {url} → HTTP {resp.status_code}"
    if urlparse(str(resp.url)).path.rstrip("/") != urlparse(url).path.rstrip("/"):
        return f"{label}: {url} → redirected to {resp.url}"
    return None


class TestBrocardiCodiciLive:
    async def test_every_page_answers(self):
        semaphore = asyncio.Semaphore(5)

        async def guarded(client, label, url):
            async with semaphore:
                return await _check_page(client, label, url)

        async with httpx.AsyncClient(follow_redirects=True, timeout=30, headers=HEADERS) as client:
            problems = await asyncio.gather(
                *[guarded(client, label, url) for label, url in BROCARDI_CODICI.items()]
            )

        failures = [p for p in problems if p]
        assert not failures, "\n".join(
            [f"{len(failures)}/{len(BROCARDI_CODICI)} pagine Brocardi non rispondono:"] + failures
        )

    async def test_every_listed_source_is_mapped(self):
        async with httpx.AsyncClient(follow_redirects=True, timeout=30, headers=HEADERS) as client:
            resp = await client.get(FONTI_URL)
        resp.raise_for_status()
        # The page is served as ISO-8859-1 whatever the declared charset says.
        soup = BeautifulSoup(resp.content.decode("latin-1"), "lxml")

        listed = set()
        for anchor in soup.select("a[href]"):
            href = anchor["href"]
            if href.startswith("/") and href.endswith("/") and href.count("/") == 2:
                listed.add(href)
        listed.discard("/chi-siamo/")

        mapped = {urlparse(url).path for url in BROCARDI_CODICI.values()}
        unmapped = sorted(listed - mapped)
        assert not unmapped, "fonti Brocardi senza mapping: " + ", ".join(unmapped)

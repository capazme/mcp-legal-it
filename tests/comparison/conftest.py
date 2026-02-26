"""Shared fixtures for comparison tests against avvocatoandreani.it."""

import re

import pytest
from playwright.sync_api import sync_playwright

_NO_LIVE_MARK = {"test_privacy_docs.py"}


def pytest_collection_modifyitems(items):
    """Mark all comparison tests as 'live' so they are skipped by default.

    Files listed in _NO_LIVE_MARK are unit-style tests that need no network
    access and are not marked live.
    """
    live_marker = pytest.mark.live
    for item in items:
        if "/comparison/" in str(item.fspath):
            if item.fspath.basename not in _NO_LIVE_MARK:
                item.add_marker(live_marker)


@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        yield b
        b.close()


@pytest.fixture()
def page(browser):
    ctx = browser.new_context()
    pg = ctx.new_page()
    yield pg
    pg.close()
    ctx.close()


def accept_cookies(page):
    """Dismiss cookie banner if present (site-specific + Quantcast CMP)."""
    try:
        btn = page.locator("#accept-btn")
        if btn.is_visible(timeout=2000):
            btn.click()
            page.wait_for_timeout(300)
    except Exception:
        pass
    # Quantcast CMP overlay (some pages use this instead) — remove via JS
    page.evaluate(
        'document.querySelectorAll("#qc-cmp2-container, .qc-cmp2-container").forEach(el => el.remove())'
    )
    page.wait_for_timeout(200)


def submit_form(page, form_selector=None, btn_selector="#btn-calc"):
    """Submit form via click(force=True) to bypass any overlay."""
    page.click(btn_selector, force=True)
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(3000)


def goto(page, path: str, wait_ms: int = 1000):
    """Navigate to an avvocatoandreani.it page and accept cookies."""
    url = f"https://www.avvocatoandreani.it/servizi/{path}"
    page.goto(url, timeout=60000, wait_until="domcontentloaded")
    page.wait_for_load_state("domcontentloaded")
    accept_cookies(page)
    page.wait_for_timeout(wait_ms)


def parse_euro(text: str) -> float:
    """Parse '€ 1.234,56' or '1.234,56' to float 1234.56."""
    cleaned = text.replace("€", "").strip()
    cleaned = cleaned.replace(".", "").replace(",", ".")
    return float(cleaned)


def get_result_text(page) -> str:
    """Get the full text content of result area."""
    return page.locator(".result, #result, .risultato, #risultato").first.inner_text()


def get_tables_text(page) -> list[str]:
    """Get text content of all result tables."""
    tables = page.query_selector_all("table")
    return [t.inner_text().strip() for t in tables if t.inner_text().strip()]


def extract_amount(text: str, label: str) -> float | None:
    """Extract euro amount after a label in text.

    e.g. extract_amount(text, 'Totale interessi') -> 499.31
    """
    pattern = rf"{re.escape(label)}[:\s]*€?\s*([\d.,]+)"
    m = re.search(pattern, text, re.IGNORECASE)
    if m:
        return parse_euro(m.group(1))
    return None


def assert_close(our_value: float, site_value: float, tolerance: float = 0.02, label: str = ""):
    """Assert two values are within tolerance (default 2 cents)."""
    diff = abs(our_value - site_value)
    assert diff <= tolerance, (
        f"{label}: nostro={our_value:.2f}, sito={site_value:.2f}, diff={diff:.2f} (max {tolerance})"
    )

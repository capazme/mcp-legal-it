"""No URL may appear in the code for a host the project has not declared.

This is the machine-checkable half of SECURITY.md. A reader auditing the
project before running it on client matters wants to know where their queries
go; a prose list would drift the first time someone adds a scraper. These tests
fail the build instead.

They check what is *written in the code*, not what happens at runtime — a
static guarantee, and stated as such. It catches a new host being added, which
is the realistic drift; it would not catch a URL assembled from fragments at
runtime, and nothing here claims otherwise.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from src.lib._egress import (
    ALLOWED_HOSTS,
    CI_ONLY_HOSTS,
    NON_NETWORK_HOSTS,
    SCRIPT_ONLY_NON_NETWORK_HOSTS,
    is_allowed,
)

ROOT = Path(__file__).resolve().parents[2]
URL = re.compile(r"https?://([A-Za-z0-9][A-Za-z0-9.-]*[A-Za-z0-9])")


def hosts_in(directory: Path) -> dict[str, list[str]]:
    """Every host appearing in a URL literal, mapped to the files naming it."""
    found: dict[str, list[str]] = {}
    for path in sorted(directory.rglob("*.py")):
        for host in set(URL.findall(path.read_text(encoding="utf-8"))):
            found.setdefault(host, []).append(str(path.relative_to(ROOT)))
    return found


SERVER_HOSTS = sorted(hosts_in(ROOT / "src"))
SCRIPT_HOSTS = sorted(hosts_in(ROOT / "scripts"))


@pytest.mark.parametrize("host", SERVER_HOSTS)
def test_server_contacts_only_declared_hosts(host):
    consentiti = ALLOWED_HOSTS | NON_NETWORK_HOSTS
    assert host in consentiti, (
        f"'{host}' compare in src/ ma non è dichiarato.\n"
        "Se il server lo contatta davvero, aggiungilo ad ALLOWED_HOSTS in "
        "src/lib/_egress.py e documentalo in SECURITY.md; se è solo un "
        "namespace o un segnaposto, aggiungilo a NON_NETWORK_HOSTS."
    )


@pytest.mark.parametrize("host", SCRIPT_HOSTS)
def test_maintenance_scripts_contact_only_declared_hosts(host):
    consentiti = (
        ALLOWED_HOSTS | CI_ONLY_HOSTS | NON_NETWORK_HOSTS | SCRIPT_ONLY_NON_NETWORK_HOSTS
    )
    assert host in consentiti, f"'{host}' compare in scripts/ ma non è dichiarato"


@pytest.mark.parametrize("host", sorted(ALLOWED_HOSTS))
def test_every_allowed_host_is_documented(host):
    """SECURITY.md answers the auditor's question, so it cannot fall behind."""
    testo = (ROOT / "SECURITY.md").read_text(encoding="utf-8")
    assert host in testo, (
        f"'{host}' è nell'allowlist ma non compare in SECURITY.md — "
        "l'elenco pubblicato deve restare completo"
    )


@pytest.mark.parametrize("host", sorted(CI_ONLY_HOSTS))
def test_every_ci_only_host_is_documented(host):
    testo = (ROOT / "SECURITY.md").read_text(encoding="utf-8")
    assert host in testo


def test_the_allowlist_is_not_vacuous():
    assert len(ALLOWED_HOSTS) >= 10
    assert "www.normattiva.it" in ALLOWED_HOSTS


def test_is_allowed_rejects_an_undeclared_host():
    assert is_allowed("https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:legge")
    assert not is_allowed("https://telemetry.example.com/collect")
    assert not is_allowed("https://www.normattiva.it.evil.test/phish")
    assert not is_allowed("not-a-url")

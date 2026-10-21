"""Italgiure is reached with TLS verification on.

Its server sends the wrong intermediates, so the client used to run with
verify=False: anyone on the path could have served altered decisions. The
missing intermediate now ships with the package (lib/italgiure/ti_trust_ov_ca.crt)
and is added to certifi's roots. These tests fail if verification is switched
off again, anywhere in the package.
"""

import ast
import datetime
import ssl
from pathlib import Path
from unittest.mock import patch

import pytest

from mcp_legal_it.lib.italgiure import client as italgiure

PKG = Path(italgiure.__file__).resolve().parents[2]


def test_tls_context_verifies_certificate_and_hostname():
    ctx = italgiure.tls_context()
    assert ctx.verify_mode == ssl.CERT_REQUIRED
    assert ctx.check_hostname is True


def test_no_client_in_the_package_turns_verification_off():
    offenders = []
    for path in PKG.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.keyword) and node.arg == "verify":
                if isinstance(node.value, ast.Constant) and node.value.value is False:
                    offenders.append(f"{path.relative_to(PKG)}:{node.value.lineno}")
    assert not offenders, f"verify=False in {offenders}"


async def test_every_italgiure_client_gets_the_verifying_context():
    seen = []

    class Recorder:
        def __init__(self, **kwargs):
            seen.append(kwargs)

        async def get(self, *a, **k):
            return None

        async def aclose(self):
            pass

    with patch("mcp_legal_it.core._http.httpx.AsyncClient", Recorder):
        async with italgiure.SolrSession():
            pass
    assert seen and all(kw.get("verify") is italgiure.tls_context() for kw in seen), seen


def test_bundled_intermediate_is_the_expected_one_and_not_about_to_expire():
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes

    cert = x509.load_pem_x509_certificate(italgiure._INTERMEDIO.read_bytes())
    assert cert.subject.rfc4514_string().endswith("CN=TI Trust Technologies OV CA") or \
        "TI Trust Technologies OV CA" in cert.subject.rfc4514_string()
    assert "USERTrust RSA Certification Authority" in cert.issuer.rfc4514_string()
    assert cert.fingerprint(hashes.SHA256()).hex().upper() == (
        "1BFD8702D8F9BB340F353820330C0BBA7E522C63164C91F295414DAC797F0863")
    # Renewal alarm: replace the file (from the leaf's AIA URL) before it expires.
    left = cert.not_valid_after_utc - datetime.datetime.now(datetime.timezone.utc)
    assert left > datetime.timedelta(days=180), f"intermediate expires in {left.days} days"


@pytest.mark.live
async def test_live_handshake_verifies():
    import httpx

    async with httpx.AsyncClient(verify=italgiure.tls_context(), timeout=30) as client:
        resp = await client.get("https://www.italgiure.giustizia.it/sncass/")
    assert resp.status_code == 200

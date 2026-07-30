"""Unit tests for the VIES client lib and the verifica_partita_iva_vies tool.

Mocked httpx responses — no real network calls except the @pytest.mark.live test.
"""

import httpx
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.lib.vies.client import VIES_ENDPOINT, check_vat, checksum_partita_iva


def _mock_async_client(json_payload=None, exc=None, status=200):
    """Build a patched httpx.AsyncClient whose post() returns the payload or raises."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status
    resp.json.return_value = json_payload or {}
    resp.raise_for_status = MagicMock()
    if status >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "err", request=MagicMock(), response=resp
        )
    client = MagicMock()
    if exc is not None:
        client.post = AsyncMock(side_effect=exc)
    else:
        client.post = AsyncMock(return_value=resp)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


class TestChecksum:
    def test_valid_piva(self):
        assert checksum_partita_iva("12345670017") is True

    def test_invalid_check_digit(self):
        assert checksum_partita_iva("12345670018") is False

    def test_non_numeric(self):
        assert checksum_partita_iva("1234567001X") is False

    def test_wrong_length(self):
        assert checksum_partita_iva("1234567001") is False

    def test_strips_spaces(self):
        assert checksum_partita_iva(" 12345670017 ") is True


class TestCheckVat:
    async def test_valid_with_name(self):
        payload = {"valid": True, "name": "ACME SRL", "address": "VIA ROMA 1 MILANO"}
        with patch("src.lib.vies.client.httpx.AsyncClient", return_value=_mock_async_client(payload)):
            out = await check_vat("12345670017")
        assert out == {
            "disponibile": True,
            "valido": True,
            "denominazione": "ACME SRL",
            "indirizzo": "VIA ROMA 1 MILANO",
            "errore": None,
        }

    async def test_valid_without_data(self):
        payload = {"valid": True, "name": "---", "address": ""}
        with patch("src.lib.vies.client.httpx.AsyncClient", return_value=_mock_async_client(payload)):
            out = await check_vat("12345670017")
        assert out["valido"] is True
        assert out["denominazione"] is None
        assert out["indirizzo"] is None

    async def test_invalid_vat(self):
        payload = {"valid": False, "name": "---", "address": "---"}
        with patch("src.lib.vies.client.httpx.AsyncClient", return_value=_mock_async_client(payload)):
            out = await check_vat("12345670017")
        assert out["valido"] is False
        assert out["disponibile"] is True

    async def test_isvalid_key_variant(self):
        # Newer VIES REST deployments use isValid instead of valid.
        payload = {"isValid": True, "name": "ACME SRL", "address": "VIA ROMA 1"}
        with patch("src.lib.vies.client.httpx.AsyncClient", return_value=_mock_async_client(payload)):
            out = await check_vat("12345670017")
        assert out["valido"] is True

    async def test_ms_unavailable(self):
        payload = {"userError": "MS_UNAVAILABLE"}
        with patch("src.lib.vies.client.httpx.AsyncClient", return_value=_mock_async_client(payload)):
            out = await check_vat("12345670017")
        assert out["disponibile"] is False
        assert out["valido"] is None
        assert "MS_UNAVAILABLE" in out["errore"]

    async def test_transport_error(self):
        exc = httpx.ConnectTimeout("timeout")
        with patch("src.lib.vies.client.httpx.AsyncClient", return_value=_mock_async_client(exc=exc)):
            out = await check_vat("12345670017")
        assert out["disponibile"] is False
        assert out["valido"] is None
        assert out["errore"]

    async def test_http_5xx(self):
        with patch(
            "src.lib.vies.client.httpx.AsyncClient",
            return_value=_mock_async_client({"error": "boom"}, status=500),
        ):
            out = await check_vat("12345670017")
        assert out["disponibile"] is False

    async def test_bad_input_none(self):
        # None input → AttributeError on .upper() or .strip()
        out = await check_vat(None)
        assert out["disponibile"] is False
        assert out["valido"] is None
        assert out["errore"]
        assert "AttributeError" in out["errore"]

    async def test_json_decode_error(self):
        # resp.json() raises ValueError (JSONDecodeError subclass)
        resp = MagicMock(spec=httpx.Response)
        resp.status_code = 200
        resp.json.side_effect = ValueError("Invalid JSON")
        client = MagicMock()
        client.post = AsyncMock(return_value=resp)
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        with patch("src.lib.vies.client.httpx.AsyncClient", return_value=client):
            out = await check_vat("12345670017")
        assert out["disponibile"] is False
        assert out["valido"] is None
        assert "ValueError" in out["errore"]


# ---------------------------------------------------------------------------
# Tool: verifica_partita_iva_vies
# ---------------------------------------------------------------------------

import importlib


def _tool(fn_name: str):
    mod = importlib.import_module("src.tools.analisi_fornitori")
    fn = getattr(mod, fn_name)
    return fn.fn if hasattr(fn, "fn") else fn


class TestVerificaPartitaIvaViesTool:
    async def test_checksum_failure_skips_network(self):
        with patch("src.tools.analisi_fornitori.check_vat", new=AsyncMock()) as mocked:
            out = await _tool("verifica_partita_iva_vies")(partita_iva="12345670018")
        mocked.assert_not_awaited()
        assert out["checksum_valido"] is False
        assert out["valido"] is False
        assert out["disponibile"] is None
        assert "checksum" in out["errore"]

    async def test_valid_flow_merges_lib_result(self):
        lib_result = {
            "disponibile": True,
            "valido": True,
            "denominazione": "ACME SRL",
            "indirizzo": "VIA ROMA 1",
            "errore": None,
        }
        with patch("src.tools.analisi_fornitori.check_vat", new=AsyncMock(return_value=lib_result)):
            out = await _tool("verifica_partita_iva_vies")(partita_iva=" 12345670017 ")
        assert out["partita_iva"] == "12345670017"
        assert out["codice_paese"] == "IT"
        assert out["checksum_valido"] is True
        assert out["valido"] is True
        assert out["denominazione"] == "ACME SRL"

    async def test_non_it_skips_checksum(self):
        lib_result = {
            "disponibile": True,
            "valido": True,
            "denominazione": "GMBH",
            "indirizzo": None,
            "errore": None,
        }
        with patch("src.tools.analisi_fornitori.check_vat", new=AsyncMock(return_value=lib_result)) as mocked:
            out = await _tool("verifica_partita_iva_vies")(partita_iva="DE123456789", codice_paese="DE")
        mocked.assert_awaited_once()
        assert out["checksum_valido"] is None


@pytest.mark.live
class TestLive:
    async def test_real_vies_roundtrip(self):
        # Ferrari S.p.A. — stable, well-known Italian VAT number.
        out = await check_vat("00159560366")
        assert out["disponibile"] is True
        assert out["valido"] is True

"""Unit tests for mcp_legal_it/lib/_http.py retry helper."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from mcp_legal_it.core._http import FontePausata
from mcp_legal_it.lib._http import retry_request


def _make_response(status_code: int = 200) -> httpx.Response:
    return httpx.Response(status_code, request=httpx.Request("GET", "http://test"))


class TestRetryRequest:
    """Tests for retry_request()."""

    @pytest.mark.asyncio
    async def test_success_first_attempt(self):
        client = AsyncMock()
        client.get = AsyncMock(return_value=_make_response(200))

        resp = await retry_request(client, "GET", "http://test/ok")
        assert resp.status_code == 200
        assert client.get.call_count == 1

    @pytest.mark.asyncio
    async def test_retry_on_500(self):
        client = AsyncMock()
        client.get = AsyncMock(side_effect=[
            _make_response(503),
            _make_response(200),
        ])

        with patch("mcp_legal_it.lib._http.asyncio.sleep", new_callable=AsyncMock):
            resp = await retry_request(client, "GET", "http://test/retry", backoff_base=0.01)
        assert resp.status_code == 200
        assert client.get.call_count == 2

    @pytest.mark.asyncio
    async def test_no_retry_on_4xx(self):
        client = AsyncMock()
        client.get = AsyncMock(return_value=_make_response(404))

        with pytest.raises(httpx.HTTPStatusError):
            await retry_request(client, "GET", "http://test/404")
        assert client.get.call_count == 1

    @pytest.mark.asyncio
    async def test_retry_on_transport_error(self):
        client = AsyncMock()
        client.get = AsyncMock(side_effect=[
            httpx.ConnectError("connection refused"),
            _make_response(200),
        ])

        with patch("mcp_legal_it.lib._http.asyncio.sleep", new_callable=AsyncMock):
            resp = await retry_request(client, "GET", "http://test/conn", backoff_base=0.01)
        assert resp.status_code == 200
        assert client.get.call_count == 2

    @pytest.mark.asyncio
    async def test_all_retries_exhausted(self):
        client = AsyncMock()
        client.get = AsyncMock(side_effect=httpx.ConnectError("connection refused"))

        with patch("mcp_legal_it.lib._http.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(httpx.ConnectError):
                await retry_request(
                    client, "GET", "http://test/fail",
                    max_retries=2, backoff_base=0.01,
                )
        assert client.get.call_count == 3

    @pytest.mark.asyncio
    async def test_passes_kwargs_to_request(self):
        client = AsyncMock()
        client.post = AsyncMock(return_value=_make_response(200))

        await retry_request(
            client, "POST", "http://test/post",
            data={"key": "value"}, params={"q": "test"},
        )
        client.post.assert_called_once_with(
            "http://test/post",
            data={"key": "value"}, params={"q": "test"},
        )

    @pytest.mark.asyncio
    async def test_exponential_backoff_timing(self):
        client = AsyncMock()
        client.get = AsyncMock(side_effect=[
            httpx.ConnectError("fail"),
            httpx.ConnectError("fail"),
            _make_response(200),
        ])

        sleep_calls = []
        async def mock_sleep(duration):
            sleep_calls.append(duration)

        with patch("mcp_legal_it.lib._http.asyncio.sleep", side_effect=mock_sleep):
            await retry_request(
                client, "GET", "http://test/backoff",
                max_retries=2, backoff_base=1.0,
            )
        # backoff_base * 2**n plus a jitter of at most JITTER seconds (VisuaLex's 0.3)
        assert len(sleep_calls) == 2
        assert 1.0 <= sleep_calls[0] <= 1.3 and 2.0 <= sleep_calls[1] <= 2.3

    @pytest.mark.asyncio
    async def test_429_is_retried_with_its_stated_wait(self):
        resp_429 = httpx.Response(429, headers={"Retry-After": "5"}, request=httpx.Request("GET", "http://test"))
        client = AsyncMock()
        client.get = AsyncMock(side_effect=[resp_429, _make_response(200)])
        sleep_calls = []

        async def mock_sleep(duration):
            sleep_calls.append(duration)

        with patch("mcp_legal_it.lib._http.asyncio.sleep", side_effect=mock_sleep):
            resp = await retry_request(client, "GET", "http://test/429", backoff_base=0.01)
        assert resp.status_code == 200 and sleep_calls == [5.0]

    @pytest.mark.asyncio
    async def test_429_without_budget_or_with_a_long_wait_is_not_retried(self):
        lungo = httpx.Response(429, headers={"Retry-After": "120"}, request=httpx.Request("GET", "http://test"))
        client = AsyncMock()
        client.get = AsyncMock(return_value=lungo)
        with patch("mcp_legal_it.lib._http.asyncio.sleep", new_callable=AsyncMock) as sleep:
            with pytest.raises(FontePausata):
                await retry_request(client, "GET", "http://test/429")
        assert client.get.call_count == 1 and sleep.call_count == 0

"""Unit tests for src/lib/_http.py retry helper."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from src.lib._http import retry_request


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

        with patch("src.lib._http.asyncio.sleep", new_callable=AsyncMock):
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

        with patch("src.lib._http.asyncio.sleep", new_callable=AsyncMock):
            resp = await retry_request(client, "GET", "http://test/conn", backoff_base=0.01)
        assert resp.status_code == 200
        assert client.get.call_count == 2

    @pytest.mark.asyncio
    async def test_all_retries_exhausted(self):
        client = AsyncMock()
        client.get = AsyncMock(side_effect=httpx.ConnectError("connection refused"))

        with patch("src.lib._http.asyncio.sleep", new_callable=AsyncMock):
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

        with patch("src.lib._http.asyncio.sleep", side_effect=mock_sleep):
            await retry_request(
                client, "GET", "http://test/backoff",
                max_retries=2, backoff_base=1.0,
            )
        assert sleep_calls == [1.0, 2.0]

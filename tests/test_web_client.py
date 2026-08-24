"""Tests for the unified WebClient with smart routing."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from job_bot.intelligence.web.client import (
    WebClient, WebContent, _detect_backend, _is_protected_site, _is_js_heavy,
)


class TestSmartRouting:
    def test_protected_site_detection(self):
        assert _is_protected_site("https://www.upwork.com/jobs/123")
        assert _is_protected_site("https://linkedin.com/jobs/456")
        assert _is_protected_site("https://indeed.com/viewjob?q=789")
        assert not _is_protected_site("https://example.com/jobs")
        assert not _is_protected_site("https://fuzu.com/jobs")

    def test_js_heavy_detection(self):
        assert _is_js_heavy("https://example.com/jobs/123")
        assert _is_js_heavy("https://example.com/careers/senior-dev")
        assert _is_js_heavy("https://example.com/apply/job-456")
        assert not _is_js_heavy("https://example.com/jobs")
        assert not _is_js_heavy("https://example.com/about")

    def test_backend_selection(self):
        assert _detect_backend("https://upwork.com/jobs/123") == "tinyfish"
        assert _detect_backend("https://linkedin.com/jobs/456") == "tinyfish"
        assert _detect_backend("https://example.com/jobs/789") == "firecrawl"
        assert _detect_backend("https://example.com/careers/101") == "firecrawl"
        assert _detect_backend("https://example.com/about") == "jina"
        assert _detect_backend("https://fuzu.com/jobs") == "jina"


class TestWebContent:
    def test_web_content_creation(self):
        result = WebContent(
            url="https://example.com",
            markdown="# Test",
            title="Test",
            source="jina",
        )
        assert result.url == "https://example.com"
        assert result.markdown == "# Test"
        assert result.source == "jina"
        assert result.error is None

    def test_web_content_with_error(self):
        result = WebContent(
            url="https://example.com",
            markdown="",
            source="httpx",
            error="dead_link",
        )
        assert result.error == "dead_link"


class TestWebClient:
    def test_no_keys_falls_back_to_httpx(self):
        config = {}
        client = WebClient(config)
        assert client._firecrawl is None
        assert client._jina_key == ""
        assert client._tinyfish_key == ""

    def test_firecrawl_initialized_with_key(self):
        config = {"firecrawl_api_key": "fc-test-key"}
        client = WebClient(config)
        # Firecrawl SDK may not be installed, so _firecrawl could be None
        # but the key is stored
        assert client._firecrawl_key == "fc-test-key"

    def test_jina_key_stored(self):
        config = {"jina_api_key": "jina-test-key"}
        client = WebClient(config)
        assert client._jina_key == "jina-test-key"

    @pytest.mark.asyncio
    async def test_fetch_httpx_fallback(self):
        config = {}
        client = WebClient(config)
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = "<html><body><h1>Job Title</h1><p>Description</p></body></html>"
            mock_get.return_value = mock_response
            result = await client.fetch("https://example.com/jobs/123")
            assert result.source == "httpx"
            assert "Job Title" in result.markdown

    @pytest.mark.asyncio
    async def test_fetch_jina_success(self):
        config = {"jina_api_key": "test-key"}
        client = WebClient(config)
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = "# Senior Engineer\nWe are hiring a senior engineer..."
            mock_get.return_value = mock_response
            result = await client.fetch("https://example.com/about")
            assert result.source == "jina"
            assert "Senior Engineer" in result.markdown

    @pytest.mark.asyncio
    async def test_fetch_returns_dead_link(self):
        config = {}
        client = WebClient(config)
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 404
            mock_get.return_value = mock_response
            result = await client.fetch("https://example.com/dead")
            assert result.error == "dead_link"

    @pytest.mark.asyncio
    async def test_search_returns_empty_when_no_keys(self):
        config = {}
        client = WebClient(config)
        results = await client.search("python jobs")
        assert results == []

    @pytest.mark.asyncio
    async def test_interact_returns_error_when_no_keys(self):
        config = {}
        client = WebClient(config)
        result = await client.interact("https://example.com", "fill form")
        assert result.error == "no_interact_backend"

    @pytest.mark.asyncio
    async def test_close(self):
        config = {}
        client = WebClient(config)
        await client.close()  # Should not raise

"""Tests for the enrichment pipeline with Firecrawl, Jina, and TinyFish."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from job_bot.intelligence.web.enricher import ContentEnricher
from job_bot.intelligence.web.crawler import FirecrawlEnricher


class TestContentEnricher:
    @pytest.mark.asyncio
    async def test_enrich_skips_binary_files(self):
        enricher = ContentEnricher()
        text, error = await enricher.enrich("https://example.com/file.pdf")
        assert text == ""
        await enricher.close()

    @pytest.mark.asyncio
    async def test_enrich_httpx_fallback(self):
        enricher = ContentEnricher()
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = "<html><body><title>Job Post</title><p>We are hiring</p></body></html>"
            mock_get.return_value = mock_response
            text, error = await enricher.enrich("https://example.com/job")
            assert "We are hiring" in text
            assert error is None
        await enricher.close()

    @pytest.mark.asyncio
    async def test_enrich_detects_dead_link(self):
        enricher = ContentEnricher()
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 404
            mock_get.return_value = mock_response
            text, error = await enricher.enrich("https://example.com/dead")
            assert text == ""
            assert error == "dead_link"
        await enricher.close()

    @pytest.mark.asyncio
    async def test_enrich_with_jina_key(self):
        enricher = ContentEnricher(jina_api_key="test-key")
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = "# Senior Developer\nJoin our team as a senior developer."
            mock_get.return_value = mock_response
            text, error = await enricher.enrich("https://example.com/job")
            assert "Senior Developer" in text
            assert error is None
        await enricher.close()


class TestFirecrawlEnricher:
    def test_not_available_without_key(self):
        enricher = FirecrawlEnricher(api_key="")
        assert enricher._ready is False

    @pytest.mark.asyncio
    async def test_enrich_returns_error_when_not_ready(self):
        enricher = FirecrawlEnricher(api_key="")
        text, error = await enricher.enrich("https://example.com")
        assert text == ""
        assert error == "firecrawl_not_available"

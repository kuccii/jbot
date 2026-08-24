"""Content extractors for JS-rendered job pages.

Provides three enrichers:
- FirecrawlEnricher: uses Firecrawl SDK for JS rendering and anti-bot bypass
- Crawl4aiEnricher: uses crawl4ai with stealth browser config
- Both fall back gracefully when their SDK is not installed
"""

from job_bot.utils.logging import get_logger
from job_bot.utils.retry import retry

logger = get_logger()

HAS_CRAWL4AI = False
BROWSER_CONFIG = None
try:
    from crawl4ai import AsyncWebCrawler, BrowserConfig, CacheMode
    from crawl4ai.content_filter_strategy import PruningContentFilter
    from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
    HAS_CRAWL4AI = True
    BROWSER_CONFIG = BrowserConfig(
        headless=True,
        extra_args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
        ],
    )
except ImportError:
    pass

HAS_FIRECRAWL = False
try:
    from firecrawl import Firecrawl
    HAS_FIRECRAWL = True
except ImportError:
    pass


class FirecrawlEnricher:
    """Content enricher using Firecrawl for JS-rendered pages and anti-bot bypass."""

    def __init__(self, api_key: str = ""):
        self._api_key = api_key
        self._app = None
        self._ready = HAS_FIRECRAWL and bool(api_key)
        if self._ready:
            try:
                self._app = Firecrawl(api_key=api_key)
                logger.info("firecrawl_enricher_available")
            except Exception:
                self._ready = False

    @retry(max_attempts=2, delay=1.0, backoff=2.0, exceptions=(Exception,))
    async def enrich(self, url: str) -> tuple[str, str | None]:
        if not self._ready or not self._app:
            return "", "firecrawl_not_available"

        try:
            result = self._app.scrape(url)
            if result and result.get("success"):
                markdown = result.get("markdown", "")
                if len(markdown.strip()) < 50:
                    return markdown, "too_short"
                return markdown[:8000], None
            return "", "firecrawl_scrape_failed"
        except Exception as e:
            return "", str(e)[:200]

    async def close(self):
        pass  # Firecrawl SDK manages its own connections


class Crawl4aiEnricher:
    """Content enricher using crawl4ai for JS-rendered pages.

    Falls back gracefully if crawl4ai is not installed.
    """

    def __init__(self):
        self._crawler = None
        self._ready = HAS_CRAWL4AI
        if self._ready:
            logger.info("crawl4ai_enricher_available")

    async def _ensure_crawler(self):
        if self._crawler is None and self._ready:
            self._crawler = AsyncWebCrawler(config=BROWSER_CONFIG)

    @retry(max_attempts=3, delay=2.0, backoff=2.0, exceptions=(Exception,))
    async def enrich(self, url: str) -> tuple[str, str | None]:
        if not self._ready:
            return "", "crawl4ai_not_available"

        await self._ensure_crawler()
        if self._crawler is None:
            return "", "crawler_init_failed"

        try:
            result = await self._crawler.arun(
                url=url,
                cache_mode=CacheMode.ENABLED,
                markdown_generator=DefaultMarkdownGenerator(
                    content_filter=PruningContentFilter(
                        threshold=0.48,
                        threshold_type="fixed",
                        min_word_threshold=10,
                    )
                ),
                word_count_threshold=10,
                exclude_external_links=True,
                exclude_social_media_links=True,
                bypass_cache=False,
            )

            if not result.success:
                error_msg = result.error_message[:200] if result.error_message else "unknown"
                return "", f"crawl_failed: {error_msg}"

            markdown = result.markdown or ""
            if len(markdown.strip()) < 50:
                return markdown, "too_short"

            return markdown[:8000], None

        except Exception as e:
            return "", str(e)[:200]

    async def close(self):
        if self._crawler:
            await self._crawler.close()

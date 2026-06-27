"""crawl4ai-powered content extractor for JS-rendered job pages."""

from job_bot.utils.logging import get_logger

logger = get_logger()

HAS_CRAWL4AI = False
try:
    from crawl4ai import AsyncWebCrawler, CacheMode
    from crawl4ai.content_filter_strategy import PruningContentFilter
    from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
    HAS_CRAWL4AI = True
except ImportError:
    pass


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
            self._crawler = AsyncWebCrawler()

    async def enrich(self, url: str) -> tuple[str, str | None]:
        if not self._ready:
            return "", "crawl4ai_not_available"

        await self._ensure_crawler()
        if self._crawler is None:
            return "", "crawler_init_failed"

        try:
            result = await self._crawler.arun(
                url=url,
                cache_mode=CacheMode.ENABLED if self._ready else CacheMode.DISABLED,
                markdown_generator=DefaultMarkdownGenerator(
                    content_filter=PruningContentFilter(threshold=0.48, threshold_type="fixed", min_word_threshold=10)
                ),
                word_count_threshold=10,
                exclude_external_links=True,
                exclude_social_media_links=True,
                bypass_cache=False,
            )

            if not result.success:
                return "", f"crawl_failed: {result.error_message[:200] if result.error_message else 'unknown'}"

            markdown = result.markdown or ""
            if len(markdown.strip()) < 50:
                return markdown, "too_short"

            return markdown[:8000], None

        except Exception as e:
            return "", str(e)[:200]

    async def close(self):
        if self._crawler:
            await self._crawler.close()

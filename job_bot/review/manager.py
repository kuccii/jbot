import asyncio
from datetime import datetime, timezone

from job_bot.database.repository import Repository
from job_bot.intelligence.drafter import Drafter
from job_bot.intelligence.enricher import ContentEnricher
from job_bot.intelligence.crawler import Crawl4aiEnricher
from job_bot.intelligence.liveness import LivenessChecker
from job_bot.intelligence.matcher import Matcher
from job_bot.intelligence.prefilter import rank_opportunities
from job_bot.utils.logging import get_logger

logger = get_logger()


class ReviewManager:
    def __init__(self, repo: Repository, matcher: Matcher, drafter: Drafter, config: dict | None = None):
        self.repo = repo
        self.matcher = matcher
        self.drafter = drafter
        self.config = config or {}
        self._liveness = LivenessChecker()
        self._enricher = ContentEnricher()
        self._crawler = Crawl4aiEnricher() if self.config.get("crawl4ai_enabled", True) else None
        self._sem = asyncio.Semaphore(5)

    async def _enrich_with_fallback(self, url: str) -> tuple[str, str | None]:
        crawl4ai_result, crawl4ai_error = None, "not_attempted"
        if self._crawler:
            crawl4ai_result, crawl4ai_error = await self._crawler.enrich(url)
        if crawl4ai_result and len(crawl4ai_result) > 200:
            return crawl4ai_result, None
        fallback_result, fallback_error = await self._enricher.enrich(url)
        if fallback_result:
            if crawl4ai_error and crawl4ai_error != "not_attempted":
                logger.debug("crawl4ai_fallback_httpx", url=url, error=crawl4ai_error)
            return fallback_result, None
        if crawl4ai_result:
            return crawl4ai_result, None
        return fallback_result, fallback_error or crawl4ai_error

    async def _review_one(self, opp, profile) -> dict | None:
        async with self._sem:
            is_live, live_source = await self._liveness.check(opp.url)
            self.repo.update_opportunity_liveness(opp.id, "live" if is_live else "dead", datetime.now(timezone.utc))
            if not is_live:
                logger.info("skipping_dead", opp_id=opp.id, url=opp.url, source=live_source)
                return None

            content, error = await self._enrich_with_fallback(opp.url)
            if error:
                logger.warning("enrich_failed", opp_id=opp.id, error=error, url=opp.url)

            opportunity_text = content if content else f"{opp.title} {opp.description}"

            scores, cover = await asyncio.gather(
                self.matcher.score(
                    profile.get("cv_text", ""),
                    opportunity_text,
                    category=opp.category,
                ),
                self.drafter.generate_cover_letter(
                    profile.get("cv_text", ""),
                    opp.title,
                    opp.company,
                    profile.get("skills", []),
                    category=opp.category,
                ),
            )
            self.repo.update_opportunity_scores(opp.id, scores)
        composite = scores.get("composite", 50)
        logger.info("review_generated", opp_id=opp.id, score=composite, enriched=bool(content))
        return {
            "opportunity_id": opp.id,
            "title": opp.title,
            "company": opp.company,
            "score": composite / 100.0,
            "scores": scores,
            "cover_letter": cover,
        }

    async def review_pending(self, profile: dict) -> list:
        pending = self.repo.get_unscored_opportunities()
        if not pending:
            logger.info("no_pending_reviews")
            return []

        if self.config.get("bm25_enabled", True):
            pending, top_indices = rank_opportunities(
                pending,
                profile,
                top_n=self.config.get("max_per_run", 100),
            )
            selected = [pending[i] for i in top_indices]
            skipped_count = len(pending) - len(selected)
            if skipped_count > 0:
                logger.info("bm25_skip_low_relevance", count=skipped_count)
        else:
            selected = pending[:self.config.get("max_per_run", 100)]

        tasks = [self._review_one(opp, profile) for opp in selected]
        results = await asyncio.gather(*tasks)
        await self._enricher.close()
        if self._crawler:
            await self._crawler.close()
        return [r for r in results if r is not None]

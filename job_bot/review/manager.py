import asyncio
from datetime import datetime, timezone

from job_bot.database.repository import Repository
from job_bot.intelligence.generation.drafter import Drafter
from job_bot.intelligence.web.client import WebClient
from job_bot.intelligence.web.enricher import ContentEnricher
from job_bot.intelligence.web.crawler import FirecrawlEnricher, Crawl4aiEnricher
from job_bot.intelligence.web.liveness import LivenessChecker
from job_bot.intelligence.analysis.matcher import Matcher
from job_bot.intelligence.analysis.prefilter import rank_opportunities
from job_bot.utils.logging import get_logger

logger = get_logger()


class ReviewManager:
    def __init__(self, repo: Repository, matcher: Matcher, drafter: Drafter, config: dict | None = None):
        self.repo = repo
        self.matcher = matcher
        self.drafter = drafter
        self.config = config or {}
        self._liveness = LivenessChecker()
        web_services = self.config.get("web_services", {})
        self._web_client = WebClient(web_services)
        self._firecrawl = FirecrawlEnricher(
            api_key=web_services.get("firecrawl_api_key", ""),
        )
        self._enricher = ContentEnricher(
            jina_api_key=web_services.get("jina_api_key", ""),
        )
        self._crawler = Crawl4aiEnricher() if self.config.get("crawl4ai_enabled", True) else None
        self._sem = asyncio.Semaphore(5)

    async def _enrich_with_fallback(self, url: str) -> tuple[str, str | None]:
        try:
            web_result = await self._web_client.fetch(url)
            if web_result and not web_result.error and len(web_result.markdown) > 200:
                logger.debug("enrich_via_web_client", url=url, source=web_result.source)
                return web_result.markdown, None
        except Exception as e:
            logger.debug("web_client_error", url=url, error=str(e)[:100])

        try:
            firecrawl_result, firecrawl_error = await self._firecrawl.enrich(url)
            if firecrawl_result and len(firecrawl_result) > 200:
                return firecrawl_result, None
        except Exception as e:
            logger.debug("firecrawl_error", url=url, error=str(e)[:100])

        crawl4ai_result, crawl4ai_error = None, "not_attempted"
        if self._crawler:
            try:
                crawl4ai_result, crawl4ai_error = await self._crawler.enrich(url)
            except Exception as e:
                crawl4ai_error = str(e)[:100]
        if crawl4ai_result and len(crawl4ai_result) > 200:
            return crawl4ai_result, None

        try:
            fallback_result, fallback_error = await self._enricher.enrich(url)
            if fallback_result:
                return fallback_result, None
        except Exception as e:
            logger.debug("enricher_error", url=url, error=str(e)[:100])

        if crawl4ai_result:
            return crawl4ai_result, None
        return "", "all_enrichers_failed"

    async def _review_one(self, opp, profile) -> dict | None:
        try:
            async with self._sem:
                try:
                    is_live, live_source = await self._liveness.check(opp.url)
                except Exception as e:
                    logger.warning("liveness_check_failed", opp_id=opp.id, error=str(e)[:100])
                    is_live, live_source = True, "unknown"

                self.repo.update_opportunity_liveness(opp.id, "live" if is_live else "dead", datetime.now(timezone.utc))
                if not is_live:
                    logger.info("skipping_dead", opp_id=opp.id, url=opp.url, source=live_source)
                    return None

                try:
                    content, error = await self._enrich_with_fallback(opp.url)
                except Exception as e:
                    logger.warning("enrich_failed", opp_id=opp.id, error=str(e)[:100])
                    content, error = "", str(e)[:100]

                if error:
                    logger.warning("enrich_failed", opp_id=opp.id, error=error, url=opp.url)

                opportunity_text = content if content else f"{opp.title} {opp.description}"
                structured_prefix = (
                    f"TITLE: {opp.title}\n"
                    f"COMPANY: {opp.company}\n"
                    f"LOCATION: {opp.location or 'Not specified'}\n"
                    f"REMOTE: {opp.remote or 'Not specified'}\n"
                    f"CATEGORY: {opp.category}\n\n"
                    f"DETAILS:\n{opportunity_text}"
                )

                try:
                    scores, cover = await asyncio.gather(
                        self.matcher.score(
                            profile.get("cv_text", ""),
                            structured_prefix,
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
                except Exception as e:
                    logger.error("scoring_failed", opp_id=opp.id, error=str(e)[:200])
                    return None

            composite = scores.get("composite", 50)
            logger.info("review_generated", opp_id=opp.id, score=composite, enriched=bool(content))
            return {
                "opportunity_id": opp.id,
                "title": opp.title,
                "company": opp.company,
                "url": opp.url,
                "score": composite / 100.0,
                "scores": scores,
                "cover_letter": cover,
            }
        except Exception as e:
            logger.error("review_one_failed", opp_id=opp.id, error=str(e)[:200])
            return None

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
        results = await asyncio.gather(*tasks, return_exceptions=True)
        # Filter out exceptions and None results
        valid = []
        for r in results:
            if isinstance(r, Exception):
                logger.error("review_task_exception", error=str(r)[:200])
            elif r is not None:
                valid.append(r)
        return valid

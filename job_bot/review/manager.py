import asyncio
from datetime import datetime, timezone

from job_bot.database.repository import Repository
from job_bot.intelligence.drafter import Drafter
from job_bot.intelligence.enricher import ContentEnricher
from job_bot.intelligence.liveness import LivenessChecker
from job_bot.intelligence.matcher import Matcher
from job_bot.utils.logging import get_logger

logger = get_logger()


class ReviewManager:
    def __init__(self, repo: Repository, matcher: Matcher, drafter: Drafter):
        self.repo = repo
        self.matcher = matcher
        self.drafter = drafter
        self._liveness = LivenessChecker()
        self._enricher = ContentEnricher()
        self._sem = asyncio.Semaphore(5)

    async def _review_one(self, opp, profile) -> dict | None:
        async with self._sem:
            is_live, live_source = await self._liveness.check(opp.url)
            self.repo.update_opportunity_liveness(opp.id, "live" if is_live else "dead", datetime.now(timezone.utc))
            if not is_live:
                logger.info("skipping_dead", opp_id=opp.id, url=opp.url, source=live_source)
                return None

            content, error = await self._enricher.enrich(opp.url)
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
        pending = self.repo.get_pending_opportunities(min_score=0.3)
        tasks = [self._review_one(opp, profile) for opp in pending]
        results = await asyncio.gather(*tasks)
        await self._enricher.close()
        return [r for r in results if r is not None]

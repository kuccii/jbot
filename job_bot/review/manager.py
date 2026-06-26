import asyncio

from job_bot.database.repository import Repository
from job_bot.intelligence.drafter import Drafter
from job_bot.intelligence.matcher import Matcher
from job_bot.utils.logging import get_logger

logger = get_logger()


class ReviewManager:
    def __init__(self, repo: Repository, matcher: Matcher, drafter: Drafter):
        self.repo = repo
        self.matcher = matcher
        self.drafter = drafter
        self._sem = asyncio.Semaphore(5)

    async def _review_one(self, opp, profile) -> dict:
        async with self._sem:
            score, cover = await asyncio.gather(
                self.matcher.score(
                    profile.get("cv_text", ""),
                    f"{opp.title} {opp.description}",
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
        logger.info("review_generated", opp_id=opp.id, score=score)
        return {
            "opportunity_id": opp.id,
            "title": opp.title,
            "company": opp.company,
            "score": score,
            "cover_letter": cover,
        }

    async def review_pending(self, profile: dict) -> list:
        pending = self.repo.get_pending_opportunities(min_score=0.3)
        tasks = [self._review_one(opp, profile) for opp in pending]
        return await asyncio.gather(*tasks)

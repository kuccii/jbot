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

    async def review_pending(self, profile: dict) -> list:
        pending = self.repo.get_pending_opportunities(min_score=0.3)
        reviews = []
        for opp in pending:
            score = await self.matcher.score(
                profile.get("cv_text", ""),
                f"{opp.title} {opp.description}",
            )
            cover = await self.drafter.generate_cover_letter(
                profile.get("cv_text", ""),
                opp.title,
                opp.company,
                profile.get("skills", []),
            )
            reviews.append({
                "opportunity_id": opp.id,
                "title": opp.title,
                "company": opp.company,
                "score": score,
                "cover_letter": cover,
            })
            logger.info("review_generated", opp_id=opp.id, score=score)
        return reviews

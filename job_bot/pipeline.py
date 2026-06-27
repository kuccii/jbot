from job_bot.config import Config
from job_bot.database.repository import Repository
from job_bot.discovery.orchestrator import DiscoveryOrchestrator
from job_bot.intelligence.providers.factory import create_provider
from job_bot.intelligence.matcher import Matcher
from job_bot.intelligence.drafter import Drafter
from job_bot.review.manager import ReviewManager
from job_bot.application.manager import ApplicationManager
from job_bot.utils.logging import get_logger

logger = get_logger()


class Pipeline:
    def __init__(self, config: Config, repo: Repository):
        self.config = config
        self.repo = repo
        api_key = getattr(config.llm, f"{config.llm.provider}_api_key", "")
        base_url = getattr(config.llm, f"{config.llm.provider}_base_url", "http://localhost:11434")
        provider = create_provider(
            config.llm.provider,
            model=config.llm.model,
            api_key=api_key,
            base_url=base_url,
        )
        self.matcher = Matcher(provider)
        self.drafter = Drafter(provider)
        self.review_manager = ReviewManager(repo, self.matcher, self.drafter, config=config.review.model_dump())
        self.application_manager = ApplicationManager(headless=config.application.headless)

    async def discover(self) -> list:
        orch = DiscoveryOrchestrator(self.repo, self.config.discovery.model_dump())
        opportunities = await orch.run_all()
        logger.info("pipeline_discovery", count=len(opportunities))
        return opportunities

    async def review(self) -> list:
        profile = {
            "cv_text": "",
            "skills": self.config.profile.skills,
        }
        reviews = await self.review_manager.review_pending(profile)
        logger.info("pipeline_review", reviews=len(reviews))
        return reviews

    async def apply(self, url: str) -> dict:
        profile = {
            "name": self.config.profile.name,
            "email": self.config.profile.email,
            "skills": self.config.profile.skills,
        }
        result = await self.application_manager.submit(url, profile, "Cover letter text")
        logger.info("pipeline_apply", result=result)
        return result

    async def run_full_cycle(self) -> dict:
        opportunities = await self.discover()
        reviews = await self.review()
        return {"discovered": len(opportunities), "reviews": len(reviews)}

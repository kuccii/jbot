from pathlib import Path

from job_bot.config import Config
from job_bot.database.repository import Repository
from job_bot.discovery.orchestrator import DiscoveryOrchestrator
from job_bot.intelligence.providers.factory import create_provider
from job_bot.intelligence.analysis.matcher import Matcher
from job_bot.intelligence.generation.drafter import Drafter
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

        review_config = config.review.model_dump()
        review_config["web_services"] = config.web_services.model_dump()
        self.review_manager = ReviewManager(repo, self.matcher, self.drafter, config=review_config)

        app_config = {
            "autonomous_apply": config.application.autonomous_apply,
            "web_services": config.web_services.model_dump(),
        }
        self.application_manager = ApplicationManager(
            headless=config.application.headless,
            config=app_config,
        )

    def _load_cv_text(self) -> str:
        cv_path = self.config.profile.cv_path
        if not cv_path:
            return ""
        path = Path(cv_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        if path.exists():
            try:
                return path.read_text(encoding="utf-8")[:5000]
            except Exception:
                return ""
        return ""

    def _build_profile(self) -> dict:
        return {
            "name": self.config.profile.name,
            "email": self.config.profile.email,
            "phone": self.config.profile.phone,
            "skills": self.config.profile.skills,
            "cv_text": self._load_cv_text(),
        }

    async def discover(self) -> list:
        orch = DiscoveryOrchestrator(
            self.repo,
            self.config.discovery.model_dump(),
            web_services=self.config.web_services.model_dump(),
        )
        opportunities = await orch.run_all()
        logger.info("pipeline_discovery", count=len(opportunities))
        return opportunities

    async def review(self) -> list:
        profile = self._build_profile()
        reviews = await self.review_manager.review_pending(profile)
        logger.info("pipeline_review", reviews=len(reviews))
        return reviews

    async def apply(self, url: str) -> dict:
        profile = self._build_profile()
        # Generate a real cover letter using the drafter
        cover_letter = await self.drafter.generate_cover_letter(
            profile.get("cv_text", ""),
            url,
            "",
            profile.get("skills", []),
        )
        result = await self.application_manager.submit(url, profile, cover_letter)
        logger.info("pipeline_apply", result=result)
        return result

    async def run_full_cycle(self) -> dict:
        opportunities = await self.discover()
        reviews = await self.review()
        # Apply to top-scored opportunities
        applied = 0
        for review in reviews:
            if review["score"] >= 0.7:
                try:
                    await self.apply(review.get("url", ""))
                    applied += 1
                    if applied >= self.config.application.max_applications_per_run:
                        break
                except Exception as e:
                    logger.error("apply_failed", opp_id=review.get("opportunity_id"), error=str(e))
        return {
            "discovered": len(opportunities),
            "reviews": len(reviews),
            "applied": applied,
        }

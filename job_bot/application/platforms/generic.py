from job_bot.application.base import BaseApplier, ApplicationResult
from job_bot.application.registry import register
from job_bot.application.agents import TinyFishApplicant, FirecrawlApplicant, DraftPreparer


@register
class GenericFormApplier(BaseApplier):
    name = "generic"
    url_patterns = [""]

    def __init__(self):
        self._tinyfish = None
        self._firecrawl = None
        self._draft = DraftPreparer()

    def configure(self, config: dict):
        autonomous = config.get("autonomous_apply", False)
        web_services = config.get("web_services", {})
        if autonomous:
            self._tinyfish = TinyFishApplicant(api_key=web_services.get("tinyfish_api_key", ""))
            self._firecrawl = FirecrawlApplicant(api_key=web_services.get("firecrawl_api_key", ""))

    async def apply(self, url, profile, cover_letter, answers=None):
        try:
            # Try autonomous mode
            if self._tinyfish and self._tinyfish._ready:
                result = await self._tinyfish.apply_to_job(url, profile, cover_letter)
                if result.get("success"):
                    return ApplicationResult(success=True, message=result["message"], platform="tinyfish")

            if self._firecrawl and self._firecrawl._ready:
                result = await self._firecrawl.apply_to_job(url, profile, cover_letter)
                if result.get("success"):
                    return ApplicationResult(success=True, message=result["message"], platform="firecrawl")

            # Draft mode fallback
            result = await self._draft.prepare(url, profile, cover_letter)
            return ApplicationResult(success=True, message=result["message"], platform="draft")
        except Exception as e:
            return ApplicationResult(success=False, message=str(e), platform="generic")

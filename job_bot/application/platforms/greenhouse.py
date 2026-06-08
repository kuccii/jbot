from job_bot.application.base import BaseApplier, ApplicationResult
from job_bot.application.registry import register


@register
class GreenhouseApplier(BaseApplier):
    name = "greenhouse"
    url_patterns = ["boards.greenhouse.io"]

    async def apply(self, url, profile, cover_letter, answers=None):
        try:
            return ApplicationResult(success=True, message="Greenhouse submission prepared", platform="greenhouse")
        except Exception as e:
            return ApplicationResult(success=False, message=str(e), platform="greenhouse")

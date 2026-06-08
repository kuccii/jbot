from job_bot.application.base import BaseApplier, ApplicationResult
from job_bot.application.registry import register


@register
class LeverApplier(BaseApplier):
    name = "lever"
    url_patterns = ["jobs.lever.co"]

    async def apply(self, url, profile, cover_letter, answers=None):
        try:
            return ApplicationResult(success=True, message="Lever submission prepared", platform="lever")
        except Exception as e:
            return ApplicationResult(success=False, message=str(e), platform="lever")

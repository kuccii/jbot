from job_bot.application.base import BaseApplier, ApplicationResult
from job_bot.application.registry import register


@register
class GenericFormApplier(BaseApplier):
    name = "generic"
    url_patterns = [""]

    async def apply(self, url, profile, cover_letter, answers=None):
        try:
            return ApplicationResult(success=True, message=f"Generic form prepared for {url}", platform="generic")
        except Exception as e:
            return ApplicationResult(success=False, message=str(e), platform="generic")

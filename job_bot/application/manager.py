from job_bot.application.registry import get_applier
from job_bot.utils.logging import get_logger

logger = get_logger()


class ApplicationManager:
    def __init__(self, headless: bool = True):
        self.headless = headless

    async def submit(self, url: str, profile: dict, cover_letter: str) -> dict:
        applier = get_applier(url)
        if not applier:
            return {"success": False, "message": f"No applier found for {url}"}
        result = await applier.apply(url, profile, cover_letter)
        logger.info("application_result", platform=result.platform, success=result.success)
        return {"success": result.success, "message": result.message, "platform": result.platform}

from job_bot.application.registry import get_applier
from job_bot.utils.logging import get_logger

logger = get_logger()


class ApplicationManager:
    def __init__(self, headless: bool = True, config: dict | None = None):
        self.headless = headless
        self.config = config or {}

    async def submit(self, url: str, profile: dict, cover_letter: str, category: str = "job") -> dict:
        applier = get_applier(url)
        if not applier:
            return {"success": False, "message": f"No applier found for {url}"}
        if hasattr(applier, "configure"):
            applier.configure(self.config)
        result = await applier.apply(url, profile, cover_letter)
        logger.info("application_result", platform=result.platform, success=result.success)
        return {"success": result.success, "message": result.message, "platform": result.platform}

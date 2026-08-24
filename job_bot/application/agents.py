"""Autonomous and draft-mode application agents.

Uses TinyFish Agent for autonomous form filling and Firecrawl Interact
for multi-step navigation. Falls back to draft preparation when no
autonomous backend is available.
"""

from __future__ import annotations

from job_bot.utils.logging import get_logger

logger = get_logger()


class TinyFishApplicant:
    """Use TinyFish Agent to autonomously navigate and fill application forms."""

    def __init__(self, api_key: str = ""):
        self._api_key = api_key
        self._ready = bool(api_key)
        if self._ready:
            try:
                import tinyfish  # noqa: F401
            except ImportError:
                self._ready = False
                logger.warning("tinyfish_sdk_not_installed")

    async def apply_to_job(self, url: str, profile: dict, cover_letter: str) -> dict:
        """Navigate to job URL and fill application form autonomously."""
        if not self._ready:
            return {"success": False, "error": "tinyfish_not_available"}

        try:
            import tinyfish

            prompt = (
                f"Navigate to {url} and fill out the job application form.\n"
                f"Use these details:\n"
                f"- Name: {profile.get('name', '')}\n"
                f"- Email: {profile.get('email', '')}\n"
                f"- Phone: {profile.get('phone', '')}\n"
                f"- Cover letter: {cover_letter[:2000]}\n"
                f"If there is a text area for cover letter or additional info, paste the cover letter.\n"
                f"Do NOT submit the form — stop before the final submit button."
            )

            result = tinyfish.agent(prompt, url=url)
            if result:
                return {
                    "success": True,
                    "message": "Application form filled by TinyFish agent",
                    "platform": "tinyfish",
                    "output": result.get("output", ""),
                }
            return {"success": False, "error": "tinyfish_agent_failed"}
        except Exception as e:
            logger.error("tinyfish_apply_error", error=str(e)[:200])
            return {"success": False, "error": str(e)[:200]}


class FirecrawlApplicant:
    """Use Firecrawl Interact for multi-step form navigation."""

    def __init__(self, api_key: str = ""):
        self._api_key = api_key
        self._app = None
        self._ready = False
        if api_key:
            try:
                from firecrawl import Firecrawl
                self._app = Firecrawl(api_key=api_key)
                self._ready = True
            except ImportError:
                logger.warning("firecrawl_sdk_not_installed")

    async def apply_to_job(self, url: str, profile: dict, cover_letter: str) -> dict:
        """Scrape the page, then interact to fill form fields."""
        if not self._ready or not self._app:
            return {"success": False, "error": "firecrawl_not_available"}

        try:
            # Step 1: Scrape the page to get a session
            scrape_result = self._app.scrape(url)
            scrape_id = scrape_result.get("metadata", {}).get("scrapeId")
            if not scrape_id:
                return {"success": False, "error": "firecrawl_scrape_failed"}

            # Step 2: Interact to find and fill form fields
            fill_prompt = (
                f"Find the application form on this page and fill in:\n"
                f"Name: {profile.get('name', '')}\n"
                f"Email: {profile.get('email', '')}\n"
                f"Cover letter: {cover_letter[:1500]}"
            )
            self._app.interact(scrape_id, prompt=fill_prompt)

            return {
                "success": True,
                "message": "Application form filled via Firecrawl Interact",
                "platform": "firecrawl",
            }
        except Exception as e:
            logger.error("firecrawl_apply_error", error=str(e)[:200])
            return {"success": False, "error": str(e)[:200]}


class DraftPreparer:
    """Prepare application content for human review and manual submission."""

    async def prepare(self, url: str, profile: dict, cover_letter: str) -> dict:
        """Return structured draft ready for human review."""
        return {
            "success": True,
            "message": "Draft prepared — review and submit manually",
            "platform": "draft",
            "draft": {
                "url": url,
                "name": profile.get("name", ""),
                "email": profile.get("email", ""),
                "cover_letter": cover_letter,
            },
        }

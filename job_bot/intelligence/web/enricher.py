"""Visit opportunity URLs and extract full page content for scoring.

Supports three backends: Jina Reader, httpx+BS4 (fallback).
"""

import httpx
from bs4 import BeautifulSoup

from job_bot.utils.logging import get_logger

logger = get_logger()

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

DEAD_PHRASES = [
    "page not found", "this page could not be found", "404",
    "no longer accepting", "position has been filled",
    "this posting is no longer", "job has been removed",
]

SKIP_EXTENSIONS = (".pdf", ".doc", ".docx", ".png", ".jpg", ".jpeg", ".gif", ".mp4", ".zip")


class ContentEnricher:
    def __init__(self, jina_api_key: str = ""):
        self._client = httpx.AsyncClient(timeout=15.0, follow_redirects=True)
        self._jina_key = jina_api_key

    async def enrich(self, url: str) -> tuple[str, str | None]:
        """Visit a URL and extract readable text content.
        Tries Jina Reader first (if configured), then falls back to httpx+BS4.
        Returns (extracted_text, error_message).
        """
        if url.lower().endswith(SKIP_EXTENSIONS):
            return "", None

        # Try Jina Reader if configured
        if self._jina_key:
            result = await self._enrich_jina(url)
            if result[0]:
                return result
            if result[1] and result[1] != "jina_not_configured":
                logger.debug("jina_fallback_httpx", url=url, error=result[1])

        # Fallback to httpx + BeautifulSoup
        return await self._enrich_httpx(url)

    async def _enrich_jina(self, url: str) -> tuple[str, str | None]:
        try:
            resp = await self._client.get(
                f"https://r.jina.ai/{url}",
                headers={"Authorization": f"Bearer {self._jina_key}"},
            )
            if resp.status_code == 200:
                text = resp.text
                if any(p in text.lower() for p in DEAD_PHRASES):
                    return text[:5000], "dead_content"
                return text[:5000], None
            return "", f"http_{resp.status_code}"
        except Exception as e:
            return "", str(e)[:200]

    async def _enrich_httpx(self, url: str) -> tuple[str, str | None]:
        try:
            resp = await self._client.get(url, headers={"User-Agent": USER_AGENT})
            if resp.status_code in (404, 410):
                return "", "dead_link"
            if resp.status_code != 200:
                return "", f"http_{resp.status_code}"

            soup = BeautifulSoup(resp.text, "html.parser")

            # Remove script/style tags
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()

            title_tag = soup.find("title")
            title = title_tag.get_text(strip=True) if title_tag else ""

            text = soup.get_text(separator=" ", strip=True)

            # Check for dead content
            if any(p in text.lower() for p in DEAD_PHRASES):
                return text[:5000], "dead_content"

            # Combine title + first 5000 chars of body
            content = f"{title}\n\n{text}" if title else text
            return content[:5000], None

        except Exception as e:
            return "", str(e)

    async def close(self):
        await self._client.aclose()

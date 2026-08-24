"""Unified web client with Firecrawl, Jina Reader, and TinyFish backends.

Smart routing selects the optimal backend per-site:
- JS-heavy SPAs → Firecrawl (renders JS)
- Static HTML → Jina Reader (fast, cheap)
- Anti-bot protected → TinyFish Browser (stealth)
- Multi-step interaction → TinyFish Agent
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import httpx

from job_bot.utils.logging import get_logger

logger = get_logger()

# Sites known to require stealth/JS rendering
PROTECTED_DOMAINS = {
    "upwork.com", "linkedin.com", "indeed.com",
    "glassdoor.com", "wellfound.com",
}

# Patterns that indicate JS-heavy pages
JS_HEAVY_PATTERNS = [
    re.compile(r"/jobs/\d+"),
    re.compile(r"/careers/"),
    re.compile(r"/apply"),
    re.compile(r"/apply/"),
]


@dataclass
class WebContent:
    """Standardized content result from any backend."""
    url: str
    markdown: str
    title: str = ""
    source: str = ""  # "firecrawl" | "jina" | "tinyfish" | "httpx"
    error: str | None = None


def _is_protected_site(url: str) -> bool:
    from urllib.parse import urlparse
    host = urlparse(url).hostname or ""
    return any(d in host for d in PROTECTED_DOMAINS)


def _is_js_heavy(url: str) -> bool:
    return any(p.search(url) for p in JS_HEAVY_PATTERNS)


def _detect_backend(url: str) -> str:
    """Smart route: pick the best backend for a given URL."""
    if _is_protected_site(url):
        return "tinyfish"
    if _is_js_heavy(url):
        return "firecrawl"
    return "jina"


class WebClient:
    """Unified web client with smart routing across three backends + httpx fallback."""

    def __init__(self, config: dict):
        self._firecrawl_key = config.get("firecrawl_api_key", "")
        self._jina_key = config.get("jina_api_key", "")
        self._tinyfish_key = config.get("tinyfish_api_key", "")
        self._http = httpx.AsyncClient(timeout=15.0, follow_redirects=True)

        # Lazy-init Firecrawl SDK
        self._firecrawl = None
        if self._firecrawl_key:
            try:
                from firecrawl import Firecrawl
                self._firecrawl = Firecrawl(api_key=self._firecrawl_key)
            except ImportError:
                logger.warning("firecrawl_sdk_not_installed")

    # ── fetch ─────────────────────────────────────────────────────────

    async def fetch(self, url: str) -> WebContent:
        """Fetch page content with smart routing."""
        preferred = _detect_backend(url)

        if preferred == "tinyfish" and self._tinyfish_key:
            result = await self._fetch_tinyfish(url)
            if result and not result.error:
                return result

        if self._firecrawl and preferred in ("firecrawl", "tinyfish"):
            result = await self._fetch_firecrawl(url)
            if result and not result.error:
                return result

        if self._jina_key:
            result = await self._fetch_jina(url)
            if result and not result.error:
                return result

        if self._firecrawl:
            result = await self._fetch_firecrawl(url)
            if result and not result.error:
                return result

        return await self._fetch_httpx(url)

    async def _fetch_firecrawl(self, url: str) -> WebContent | None:
        try:
            result = self._firecrawl.scrape(url)
            if result and result.get("success"):
                return WebContent(
                    url=url,
                    markdown=result.get("markdown", ""),
                    title=result.get("metadata", {}).get("title", ""),
                    source="firecrawl",
                )
        except Exception as e:
            logger.debug("firecrawl_fetch_error", url=url, error=str(e)[:100])
        return None

    async def _fetch_jina(self, url: str) -> WebContent | None:
        try:
            headers = {}
            if self._jina_key:
                headers["Authorization"] = f"Bearer {self._jina_key}"
            resp = await self._http.get(f"https://r.jina.ai/{url}", headers=headers)
            if resp.status_code == 200:
                text = resp.text
                # Extract title from first heading if present
                title = ""
                first_line = text.split("\n", 1)[0] if text else ""
                if first_line.startswith("# "):
                    title = first_line[2:].strip()
                return WebContent(
                    url=url, markdown=text[:10000], title=title, source="jina",
                )
        except Exception as e:
            logger.debug("jina_fetch_error", url=url, error=str(e)[:100])
        return None

    async def _fetch_tinyfish(self, url: str) -> WebContent | None:
        try:
            import tinyfish
            result = tinyfish.fetch(url)
            if result:
                return WebContent(
                    url=url,
                    markdown=result.get("markdown", result.get("content", ""))[:10000],
                    title=result.get("title", ""),
                    source="tinyfish",
                )
        except Exception as e:
            logger.debug("tinyfish_fetch_error", url=url, error=str(e)[:100])
        return None

    async def _fetch_httpx(self, url: str) -> WebContent:
        try:
            from bs4 import BeautifulSoup
            resp = await self._http.get(url)
            if resp.status_code == 404:
                return WebContent(url=url, markdown="", source="httpx", error="dead_link")
            if resp.status_code != 200:
                return WebContent(url=url, markdown="", source="httpx", error=f"http_{resp.status_code}")
            soup = BeautifulSoup(resp.text, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            title = ""
            title_tag = soup.find("title")
            if title_tag:
                title = title_tag.get_text(strip=True)
            text = soup.get_text(separator=" ", strip=True)
            return WebContent(
                url=url, markdown=text[:8000], title=title, source="httpx",
            )
        except Exception as e:
            return WebContent(url=url, markdown="", source="httpx", error=str(e)[:200])

    # ── search ────────────────────────────────────────────────────────

    async def search(self, query: str, limit: int = 5) -> list[dict]:
        """Search the web. Tries Firecrawl → Jina → empty list."""
        if self._firecrawl:
            try:
                results = self._firecrawl.search(query, limit=limit)
                if results:
                    return results[:limit]
            except Exception as e:
                logger.debug("firecrawl_search_error", error=str(e)[:100])

        if self._jina_key:
            try:
                from urllib.parse import quote
                resp = await self._http.get(
                    f"https://s.jina.ai/?q={quote(query)}",
                    headers={"Authorization": f"Bearer {self._jina_key}"},
                )
                if resp.status_code == 200:
                    return resp.json()[:limit]
            except Exception as e:
                logger.debug("jina_search_error", error=str(e)[:100])

        return []

    # ── interact ──────────────────────────────────────────────────────

    async def interact(self, url: str, prompt: str) -> WebContent:
        """Navigate and interact with a page. Uses TinyFish Agent or Firecrawl Interact."""
        if self._tinyfish_key:
            result = await self._interact_tinyfish(url, prompt)
            if result and not result.error:
                return result

        if self._firecrawl:
            result = await self._interact_firecrawl(url, prompt)
            if result and not result.error:
                return result

        return WebContent(url=url, markdown="", source="none", error="no_interact_backend")

    async def _interact_tinyfish(self, url: str, prompt: str) -> WebContent | None:
        try:
            import tinyfish
            result = tinyfish.agent(prompt, url=url)
            if result:
                return WebContent(
                    url=url,
                    markdown=result.get("output", result.get("markdown", "")),
                    title=result.get("title", ""),
                    source="tinyfish",
                )
        except Exception as e:
            logger.debug("tinyfish_interact_error", error=str(e)[:100])
        return None

    async def _interact_firecrawl(self, url: str, prompt: str) -> WebContent | None:
        try:
            scrape_result = self._firecrawl.scrape(url)
            scrape_id = scrape_result.get("metadata", {}).get("scrapeId")
            if scrape_id:
                self._firecrawl.interact(scrape_id, prompt=prompt)
                # Re-scrape to get updated content
                result = self._firecrawl.scrape(url)
                if result and result.get("success"):
                    return WebContent(
                        url=url,
                        markdown=result.get("markdown", ""),
                        title=result.get("metadata", {}).get("title", ""),
                        source="firecrawl",
                    )
        except Exception as e:
            logger.debug("firecrawl_interact_error", error=str(e)[:100])
        return None

    # ── cleanup ───────────────────────────────────────────────────────

    async def close(self):
        await self._http.aclose()

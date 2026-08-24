"""Shared HTTP helpers.

Provides three fetching strategies:
  1. ``get()`` — async httpx with retries (default, fast)
  2. ``get_cf()`` — sync curl_cffi with Chrome impersonation (bypasses Cloudflare)
  3. ``get_proxied()`` — async httpx via free scraping APIs + proxy rotation
"""

import asyncio
import random
import os
import time
from typing import Optional

import httpx

# Try to import curl_cffi for Cloudflare bypass
try:
    from curl_cffi import requests as _cf_requests
    _HAS_CF = True
except ImportError:
    _HAS_CF = False

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

DEFAULT_HEADERS = {"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"}


# ---------------------------------------------------------------------------
# Proxy rotation support
# ---------------------------------------------------------------------------

class ProxyManager:
    """Manages proxy rotation for scraping.

    Free sources (no credit card required):
      1. ZenRows     — 5,000 free reqs/month (best free tier)
      2. Scrape.do   — 1,000 free reqs/month
      3. Scrapfly    — 1,000 free reqs/month
      4. ScraperAPI  — 1,000 free reqs/month
      5. Free proxy lists — fallback, ~2% success rate

    Paid sources (if configured):
      - ScrapingBee, generic proxy URL
    """

    # Free proxy list sources (last resort)
    FREE_PROXY_URLS = [
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
        "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/https.txt",
        "https://raw.githubusercontent.com/mmpx12/proxy-list/master/https.txt",
    ]

    def __init__(self):
        self._free_proxies: list[str] = []
        self._free_index = 0
        self._last_fetch = 0.0
        # API keys from environment
        self.scraper_api_key = os.getenv("SCRAPERAPI_KEY", "")
        self.scrapingbee_key = os.getenv("SCRAPINGBEE_KEY", "")
        self.scrapedo_token = os.getenv("SCRAPEDO_TOKEN", "")
        self.zenrows_key = os.getenv("ZENROWS_KEY", "")
        self.scrapfly_key = os.getenv("SCRAPFLY_KEY", "")
        self.proxy_url = os.getenv("PROXY_URL", "")  # Generic proxy URL

    def _refresh_free_proxies(self) -> None:
        """Fetch a fresh list of free proxies."""
        if time.time() - self._last_fetch < 300:  # Refresh every 5 min
            return
        try:
            import httpx as _httpx
            all_proxies: list[str] = []
            for url in self.FREE_PROXY_URLS:
                try:
                    resp = _httpx.get(url, timeout=5.0)
                    if resp.status_code == 200:
                        for line in resp.text.strip().splitlines():
                            line = line.strip()
                            if line and ":" in line:
                                all_proxies.append(f"http://{line}")
                except Exception:
                    continue
            if all_proxies:
                random.shuffle(all_proxies)
                self._free_proxies = all_proxies[:50]  # Keep 50 max
                self._free_index = 0
                self._last_fetch = time.time()
        except Exception:
            pass

    # --- Managed proxy URL builders ---

    def get_scraperapi_url(self, url: str) -> str:
        return f"http://api.scraperapi.com?api_key={self.scraper_api_key}&url={url}"

    def get_scrapingbee_url(self, url: str) -> str:
        return f"https://app.scrapingbee.com/api/v1/?api_key={self.scrapingbee_key}&url={url}&render_js=true"

    def get_scrapedo_url(self, url: str) -> str:
        """Scrape.do — 1,000 free reqs/month, no credit card."""
        return f"http://api.scrape.do/?token={self.scrapedo_token}&url={url}"

    def get_zenrows_url(self, url: str) -> str:
        """ZenRows — 5,000 free reqs/month, no credit card. Best free tier."""
        return f"https://api.zenrows.com/v1/?apikey={self.zenrows_key}&url={url}&js_render=true&antibot=true"

    def get_scrapfly_url(self, url: str) -> str:
        """Scrapfly — 1,000 free reqs/month, no credit card."""
        return f"https://api.scrapfly.io/scrape?key={self.scrapfly_key}&url={url}&render_js=true"

    # --- Proxy selection ---

    def get_proxy(self, target: str = "generic") -> Optional[str]:
        """Get a proxy URL for the given target.

        Priority:
          1. Configured proxy URL (paid residential)
          2. Free API tiers (ZenRows > Scrape.do > Scrapfly > ScraperAPI > ScrapingBee)
          3. Free proxy lists (last resort)
        """
        # 1. Paid proxy (if configured)
        if self.proxy_url:
            return self.proxy_url

        # 2. Free API tiers (best reliability, limited quota)
        if self.zenrows_key:
            return "managed:zenrows"
        if self.scrapedo_token:
            return "managed:scrapedo"
        if self.scrapfly_key:
            return "managed:scrapfly"
        if self.scraper_api_key:
            return "managed:scraperapi"
        if self.scrapingbee_key:
            return "managed:scrapingbee"

        # 3. Free proxy lists (fallback)
        self._refresh_free_proxies()
        if self._free_proxies:
            proxy = self._free_proxies[self._free_index % len(self._free_proxies)]
            self._free_index += 1
            return proxy

        return None

    def has_proxy(self) -> bool:
        """Check if any proxy source is available."""
        return bool(
            self.proxy_url
            or self.scraper_api_key
            or self.scrapingbee_key
            or self.scrapedo_token
            or self.zenrows_key
            or self.scrapfly_key
        )


# Singleton proxy manager
_proxy_manager: ProxyManager | None = None


def get_proxy_manager() -> ProxyManager:
    global _proxy_manager
    if _proxy_manager is None:
        _proxy_manager = ProxyManager()
    return _proxy_manager


async def get(client: httpx.AsyncClient, url: str, timeout: float = 15.0,
              retries: int = 2) -> httpx.Response:
    """GET with a small retry on 5xx responses and network errors."""
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            resp = await client.get(url, timeout=timeout, follow_redirects=True)
            if resp.status_code >= 500:
                last_error = httpx.HTTPStatusError(
                    f"{resp.status_code} for {url}", request=resp.request, response=resp
                )
                await asyncio.sleep(1.0 * (attempt + 1))
                continue
            resp.raise_for_status()
            return resp
        except (httpx.HTTPStatusError, httpx.TransportError, httpx.TimeoutException) as exc:
            last_error = exc
            await asyncio.sleep(1.0 * (attempt + 1))
    raise last_error or httpx.TransportError(f"failed to fetch {url}")


async def get_proxied(client: httpx.AsyncClient, url: str, timeout: float = 20.0,
                      retries: int = 3, use_proxy: bool = True) -> httpx.Response:
    """GET with proxy rotation. Tries free API tiers first, then free proxies, then direct."""
    pm = get_proxy_manager()
    last_error: Exception | None = None

    for attempt in range(retries + 1):
        proxy_url = pm.get_proxy() if use_proxy else None
        try:
            if proxy_url == "managed:zenrows":
                api_url = pm.get_zenrows_url(url)
                resp = await client.get(api_url, timeout=timeout, follow_redirects=True)
            elif proxy_url == "managed:scrapedo":
                api_url = pm.get_scrapedo_url(url)
                resp = await client.get(api_url, timeout=timeout, follow_redirects=True)
            elif proxy_url == "managed:scrapfly":
                api_url = pm.get_scrapfly_url(url)
                resp = await client.get(api_url, timeout=timeout, follow_redirects=True)
            elif proxy_url == "managed:scraperapi":
                api_url = pm.get_scraperapi_url(url)
                resp = await client.get(api_url, timeout=timeout, follow_redirects=True)
            elif proxy_url == "managed:scrapingbee":
                api_url = pm.get_scrapingbee_url(url)
                resp = await client.get(api_url, timeout=timeout, follow_redirects=True)
            elif proxy_url:
                # Free proxy: use httpx proxy parameter
                resp = await client.get(
                    url, timeout=timeout, follow_redirects=True,
                    proxy=proxy_url,
                )
            else:
                # Direct connection
                resp = await client.get(url, timeout=timeout, follow_redirects=True)

            if resp.status_code >= 500:
                last_error = httpx.HTTPStatusError(
                    f"{resp.status_code} for {url}", request=resp.request, response=resp
                )
                await asyncio.sleep(1.0 * (attempt + 1))
                continue
            resp.raise_for_status()
            return resp
        except (httpx.HTTPStatusError, httpx.TransportError, httpx.TimeoutException) as exc:
            last_error = exc
            await asyncio.sleep(0.5 * (attempt + 1))

    raise last_error or httpx.TransportError(f"failed to fetch {url}")


def get_cf(url: str, timeout: float = 15.0, impersonate: str = "chrome") -> Optional[str]:
    """Fetch URL using curl_cffi with browser impersonation.

    Bypasses Cloudflare challenges that block regular httpx/requests.
    Returns the response text, or None on failure.
    """
    if not _HAS_CF:
        return None
    try:
        resp = _cf_requests.get(
            url,
            impersonate=impersonate,
            timeout=timeout,
            headers={"Accept-Language": "en-US,en;q=0.9"},
        )
        if resp.status_code >= 400:
            return None
        return resp.text
    except Exception:
        return None

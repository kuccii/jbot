"""Shared HTTP helpers.

Provides three fetching strategies:
  1. ``get()`` — async httpx with retries (default, fast)
  2. ``get_cf()`` — sync curl_cffi with Chrome impersonation (bypasses Cloudflare)
  3. ``get_proxied()`` — async httpx via managed proxy (ScraperAPI / ScrapingBee)
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

    Supports:
      - Managed proxies (ScraperAPI, ScrapingBee, Bright Data)
      - Free proxy lists (fallback)
      - Direct connection (no proxy)
    """

    # Free proxy list sources
    FREE_PROXY_URLS = [
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
        "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/https.txt",
        "https://raw.githubusercontent.com/mmpx12/proxy-list/master/https.txt",
    ]

    def __init__(self):
        self._free_proxies: list[str] = []
        self._free_index = 0
        self._last_fetch = 0.0
        # Managed proxy config from environment
        self.scraper_api_key = os.getenv("SCRAPERAPI_KEY", "")
        self.scrapingbee_key = os.getenv("SCRAPINGBEE_KEY", "")
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

    def get_scraperapi_url(self, url: str) -> str:
        """Wrap a URL through ScraperAPI."""
        return f"http://api.scraperapi.com?api_key={self.scraper_api_key}&url={url}"

    def get_scrapingbee_url(self, url: str) -> str:
        """Wrap a URL through ScrapingBee."""
        return f"https://app.scrapingbee.com/api/v1/?api_key={self.scrapingbee_key}&url={url}&render_js=true"

    def get_proxy(self, target: str = "generic") -> Optional[str]:
        """Get a proxy URL for the given target.

        Returns the proxy URL string, or None if no proxy is available.
        Priority: configured proxy > ScraperAPI > ScrapingBee > free proxies.
        """
        # 1. Generic proxy (e.g., rotating residential)
        if self.proxy_url:
            return self.proxy_url

        # 2. Managed proxies (check if we have credits)
        if self.scraper_api_key:
            return "managed:scraperapi"
        if self.scrapingbee_key:
            return "managed:scrapingbee"

        # 3. Free proxies
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
                      retries: int = 2, use_proxy: bool = True) -> httpx.Response:
    """GET with proxy rotation. Tries managed proxy first, then free proxies, then direct.

    Parameters
    ----------
    client:
        The httpx async client (used for direct requests).
    url:
        The URL to fetch.
    timeout:
        Request timeout.
    retries:
        Number of retries with different proxies.
    use_proxy:
        Whether to attempt proxy routing.
    """
    pm = get_proxy_manager()
    last_error: Exception | None = None

    for attempt in range(retries + 1):
        proxy_url = pm.get_proxy() if use_proxy else None
        try:
            if proxy_url == "managed:scraperapi":
                proxy_api_url = pm.get_scraperapi_url(url)
                resp = await client.get(proxy_api_url, timeout=timeout, follow_redirects=True)
            elif proxy_url == "managed:scrapingbee":
                proxy_api_url = pm.get_scrapingbee_url(url)
                resp = await client.get(proxy_api_url, timeout=timeout, follow_redirects=True)
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

    Parameters
    ----------
    url:
        The URL to fetch.
    timeout:
        Request timeout in seconds.
    impersonate:
        Browser to impersonate. "chrome" works for most sites,
        "safari" is needed for Indeed (blocks Chrome).

    This is a *sync* function — use from async code via asyncio.to_thread().
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

"""Generic JS-rendered site scraper using Playwright.

Provides a reusable ``render_js()`` function that loads a URL in a headless
Chromium browser, waits for JavaScript to finish, and returns the rendered
HTML. Used by boards that serve content via client-side rendering (React,
Next.js, Astro, etc.) where plain HTTP requests return empty shells.

Playwright is a *dev dependency* — the scraper gracefully degrades to
``None`` if Playwright is not installed, so the rest of job-hunter still
works without it.
"""

from __future__ import annotations

import asyncio
from typing import Optional

try:
    from playwright.async_api import async_playwright

    _HAS_PLAYWRIGHT = True
except ImportError:
    _HAS_PLAYWRIGHT = False


async def render_js(
    url: str,
    *,
    wait_until: str = "domcontentloaded",
    timeout_ms: int = 45_000,
    extra_wait_ms: int = 8000,
    user_agent: str = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
) -> Optional[str]:
    """Render *url* in a headless Chromium browser and return the HTML.

    Returns ``None`` if Playwright is unavailable or the page fails to load.

    Parameters
    ----------
    url:
        The URL to render.
    wait_until:
        Playwright navigation wait condition.  ``"domcontentloaded"`` is
        faster; we then wait ``extra_wait_ms`` for client-side JS to hydrate.
    timeout_ms:
        Maximum time to wait for the page to load.
    extra_wait_ms:
        Additional time to wait after page load for JS hydration.
    user_agent:
        User-Agent string to send.
    """
    if not _HAS_PLAYWRIGHT:
        return None

    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            try:
                page = await browser.new_page(user_agent=user_agent)
                await page.goto(url, wait_until=wait_until, timeout=timeout_ms)
                # Wait for client-side JS to hydrate and render content
                await page.wait_for_timeout(extra_wait_ms)
                return await page.content()
            finally:
                await browser.close()
    except Exception:
        return None

"""Shared HTTP helpers."""

import asyncio

import httpx

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

DEFAULT_HEADERS = {"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"}


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

import asyncio
import logging
from typing import Callable, TypeVar
from xml.etree import ElementTree
from urllib.parse import urljoin

import httpx

from app.services.progress import StepProgressReporter

logger = logging.getLogger("app.services.http")

USER_AGENT = "llms-txt-generator/1.0"
DEFAULT_TIMEOUT = 15.0

T = TypeVar("T")


async def fetch_url(url: str, *, timeout: float = DEFAULT_TIMEOUT) -> httpx.Response | None:
    """Fetch a single URL. Returns None on any failure."""
    try:
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                return None
            return resp
    except httpx.HTTPError as e:
        logger.warning("Failed to fetch %s: %s", url, e)
        return None
    except Exception as e:
        logger.exception("Unexpected error fetching %s: %s", url, e)
        return None


async def fetch_sitemap_urls(base_url: str) -> list[str]:
    """Fetch and parse /sitemap.xml. Returns list of URLs or empty list."""
    sitemap_url = urljoin(base_url, "/sitemap.xml")
    resp = await fetch_url(sitemap_url, timeout=10.0)
    if resp is None:
        return []

    try:
        root = ElementTree.fromstring(resp.text)
        ns = {"ns": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        return [loc.text for loc in root.findall(".//ns:loc", ns) if loc.text]
    except ElementTree.ParseError as e:
        logger.warning("Sitemap parse failed for %s: %s", sitemap_url, e)
        return []


async def fetch_urls_concurrent(
    urls: list[str],
    handler: Callable[[str, httpx.Response], T | None],
    *,
    concurrency: int = 5,
    timeout: float = DEFAULT_TIMEOUT,
    reporter: StepProgressReporter | None = None,
    progress_message_fn: Callable[[int, int], str] | None = None,
    detail_fn: Callable[[str, T | None], str] | None = None,
) -> list[T]:
    """Fetch URLs concurrently with a shared client and semaphore.

    handler: (url, response) -> T | None  (sync, called after body is loaded)
    Returns list of non-None results.
    """
    semaphore = asyncio.Semaphore(concurrency)
    completed = 0
    total = len(urls)

    async def _fetch_one(url: str, client: httpx.AsyncClient) -> T | None:
        nonlocal completed
        async with semaphore:
            try:
                resp = await client.get(url, follow_redirects=True, timeout=timeout)
                if resp.status_code != 200:
                    result = None
                else:
                    result = handler(url, resp)
            except httpx.HTTPError as e:
                logger.warning("Failed to fetch %s: %s", url, e)
                result = None

            completed += 1
            if reporter:
                detail = detail_fn(url, result) if detail_fn else url
                message = progress_message_fn(completed, total) if progress_message_fn else None
                await reporter.log(detail, message=message)

            return result

    async with httpx.AsyncClient(
        timeout=timeout,
        headers={"User-Agent": USER_AGENT},
    ) as client:
        tasks = [_fetch_one(url, client) for url in urls]
        results = await asyncio.gather(*tasks)

    return [r for r in results if r is not None]

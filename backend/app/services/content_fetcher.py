import asyncio
import logging
import httpx
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from app.models import ChildPageContent
from app.services.progress import StepProgressReporter

logger = logging.getLogger("app.content_fetcher")


async def fetch_and_convert(url: str, client: httpx.AsyncClient) -> ChildPageContent | None:
    """Fetch a single URL and convert its main content to markdown."""
    try:
        resp = await client.get(url, follow_redirects=True, timeout=15.0)
        resp.raise_for_status()
    except Exception as e:
        logger.warning("Failed to fetch %s: %s", url, e)
        return None

    soup = BeautifulSoup(resp.text, "lxml")

    # Extract title
    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()

    # Find main content area
    content_el = soup.find("main") or soup.find("article") or soup.find("body")
    if content_el is None:
        return None

    # Strip non-content elements
    for tag in content_el.find_all(["nav", "footer", "header", "script", "style", "noscript", "aside"]):
        tag.decompose()

    # Convert to markdown
    markdown_content = md(str(content_el), heading_style="ATX", strip=["img"]).strip()

    if not markdown_content:
        return None

    return ChildPageContent(url=url, title=title or url, markdown_content=markdown_content)


async def fetch_child_pages(
    urls: list[str],
    reporter: StepProgressReporter | None = None,
    concurrency: int = 5,
) -> list[ChildPageContent]:
    """Fetch multiple child pages concurrently with progress reporting."""
    semaphore = asyncio.Semaphore(concurrency)
    results: list[ChildPageContent | None] = []
    completed = 0
    total = len(urls)

    async def fetch_one(url: str) -> ChildPageContent | None:
        nonlocal completed
        async with semaphore:
            async with httpx.AsyncClient() as client:
                result = await fetch_and_convert(url, client)
                completed += 1
                if reporter:
                    content_size = len(result.markdown_content) if result else 0
                    await reporter.log(
                        f"{url} — {content_size} chars" if result else f"{url} — failed",
                        message=f"Fetching content {completed}/{total}...",
                    )
                return result

    tasks = [fetch_one(url) for url in urls]
    results = await asyncio.gather(*tasks)

    return [r for r in results if r is not None]

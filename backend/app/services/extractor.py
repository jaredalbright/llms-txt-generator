import logging
import httpx
from bs4 import BeautifulSoup
from app.models import PageMeta
from app.services.progress import StepProgressReporter

logger = logging.getLogger("app.extractor")


async def extract_metadata(urls: list[str], reporter: StepProgressReporter | None = None) -> list[PageMeta]:
    """
    Fetch each URL and extract title, meta description, h1.
    Uses concurrent requests for speed.
    """
    pages: list[PageMeta] = []
    logger.info("Extracting metadata from %d URLs", len(urls))

    async with httpx.AsyncClient(
        timeout=15,
        follow_redirects=True,
        headers={"User-Agent": "llms-txt-generator/1.0"},
    ) as client:
        # TODO: Use asyncio.gather with concurrency limit (semaphore) for speed
        for i, url in enumerate(urls):
            try:
                resp = await client.get(url)
                logger.debug("  [%d/%d] %s → %d", i + 1, len(urls), url, resp.status_code)
                if resp.status_code != 200:
                    continue

                soup = BeautifulSoup(resp.text, "lxml")

                title = ""
                if soup.title and soup.title.string:
                    title = soup.title.string.strip()

                description = ""
                meta_desc = soup.find("meta", attrs={"name": "description"})
                if meta_desc and meta_desc.get("content"):
                    description = meta_desc["content"].strip()

                # Fallback to og:description
                if not description:
                    og_desc = soup.find("meta", attrs={"property": "og:description"})
                    if og_desc and og_desc.get("content"):
                        description = og_desc["content"].strip()

                h1 = ""
                h1_tag = soup.find("h1")
                if h1_tag:
                    h1 = h1_tag.get_text(strip=True)

                display_title = title or h1 or url
                pages.append(PageMeta(
                    url=url,
                    title=display_title,
                    description=description,
                    h1=h1,
                ))

                if reporter:
                    await reporter.log(display_title, message=f"Extracting metadata {i + 1}/{len(urls)}...")

            except Exception as e:
                logger.warning("  [%d/%d] Failed %s: %s", i + 1, len(urls), url, e)
                continue

    logger.info("Extraction complete: %d/%d pages succeeded", len(pages), len(urls))
    return pages

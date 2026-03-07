import logging
import httpx
from xml.etree import ElementTree
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from app.config import settings

logger = logging.getLogger("app.crawler")


async def crawl_site(url: str) -> list[str]:
    """
    Discover URLs for the given site.
    Strategy:
      1. Try /sitemap.xml first (fast, comprehensive).
      2. Fall back to crawling links from homepage.
    Returns deduplicated list of same-domain URLs, capped at settings.max_pages.
    """
    base_domain = urlparse(url).netloc
    discovered: set[str] = set()

    # --- Try sitemap ---
    logger.debug("Trying sitemap for %s", url)
    sitemap_urls = await _try_sitemap(url)
    if sitemap_urls:
        logger.info("Sitemap returned %d URLs", len(sitemap_urls))
        discovered.update(sitemap_urls)
    else:
        logger.debug("No sitemap found or empty")

    # --- Fallback: crawl from homepage ---
    if len(discovered) < 5:
        logger.debug("Fewer than 5 URLs from sitemap, falling back to link crawl")
        crawled = await _crawl_links(url, base_domain, max_depth=2)
        logger.info("Link crawl returned %d URLs", len(crawled))
        discovered.update(crawled)

    # Always include the homepage
    discovered.add(url.rstrip("/"))

    # Filter to same domain, deduplicate, cap
    filtered = [u for u in discovered if urlparse(u).netloc == base_domain]
    logger.info("Final URL list: %d URLs (capped at %d)", len(filtered[:settings.max_pages]), settings.max_pages)
    return filtered[:settings.max_pages]


async def _try_sitemap(url: str) -> list[str]:
    """Fetch and parse /sitemap.xml. Returns list of URLs or empty list."""
    sitemap_url = urljoin(url, "/sitemap.xml")

    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            resp = await client.get(sitemap_url)
            logger.debug("Sitemap %s → %d", sitemap_url, resp.status_code)
            if resp.status_code != 200:
                return []

        root = ElementTree.fromstring(resp.text)
        # Handle both regular sitemaps and sitemap indexes
        ns = {"ns": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        urls = [loc.text for loc in root.findall(".//ns:loc", ns) if loc.text]
        return urls

    except Exception as e:
        logger.warning("Sitemap parse failed for %s: %s", sitemap_url, e)
        return []


async def _crawl_links(start_url: str, base_domain: str, max_depth: int = 2) -> set[str]:
    """
    BFS crawl from start_url, following internal links.
    TODO: Implement full BFS with depth tracking and visited set.
    For scaffold, just extract links from the homepage.
    """
    found: set[str] = set()

    try:
        async with httpx.AsyncClient(
            timeout=settings.crawl_timeout,
            follow_redirects=True,
            headers={"User-Agent": "llms-txt-generator/1.0"}
        ) as client:
            resp = await client.get(start_url)
            logger.debug("Homepage fetch %s → %d", start_url, resp.status_code)
            if resp.status_code != 200:
                return found

            soup = BeautifulSoup(resp.text, "lxml")
            for a in soup.find_all("a", href=True):
                href = a["href"]
                full_url = urljoin(start_url, href)
                parsed = urlparse(full_url)

                # Same domain, no fragments, no query params
                if parsed.netloc == base_domain:
                    clean = f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")
                    found.add(clean)

    except Exception as e:
        logger.error("Link crawl failed for %s: %s", start_url, e)

    return found

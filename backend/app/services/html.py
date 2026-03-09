import logging
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from markdownify import markdownify as md

from app.models import PageMeta, ChildPageContent

logger = logging.getLogger("app.services.html")


def extract_links(html: str, base_url: str, base_domain: str) -> set[str]:
    """Extract same-domain <a href> links from HTML."""
    soup = BeautifulSoup(html, "lxml")
    found: set[str] = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]
        full_url = urljoin(base_url, href)
        parsed = urlparse(full_url)

        if parsed.netloc == base_domain:
            clean = f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")
            found.add(clean)

    return found


def extract_page_metadata(html: str, url: str) -> PageMeta | None:
    """Extract title, meta description (with og:description fallback), and h1."""
    soup = BeautifulSoup(html, "lxml")

    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()

    description = ""
    meta_desc = soup.find("meta", attrs={"name": "description"})
    if meta_desc and meta_desc.get("content"):
        description = meta_desc["content"].strip()

    if not description:
        og_desc = soup.find("meta", attrs={"property": "og:description"})
        if og_desc and og_desc.get("content"):
            description = og_desc["content"].strip()

    h1 = ""
    h1_tag = soup.find("h1")
    if h1_tag:
        h1 = h1_tag.get_text(strip=True)

    display_title = title or h1 or url
    return PageMeta(url=url, title=display_title, description=description, h1=h1)


def html_to_markdown(html: str, url: str) -> ChildPageContent | None:
    """Strip nav/footer/header, find main content, convert to markdown."""
    soup = BeautifulSoup(html, "lxml")

    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()

    content_el = soup.find("main") or soup.find("article") or soup.find("body")
    if content_el is None:
        return None

    for tag in content_el.find_all(
        ["nav", "footer", "header", "script", "style", "noscript", "aside"]
    ):
        tag.decompose()

    markdown_content = md(str(content_el), heading_style="ATX", strip=["img"]).strip()

    if not markdown_content:
        return None

    return ChildPageContent(url=url, title=title or url, markdown_content=markdown_content)

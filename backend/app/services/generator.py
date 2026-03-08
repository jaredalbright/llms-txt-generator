import re
from urllib.parse import urlparse
from typing import Any


def slugify(text: str) -> str:
    """Convert text to a filename-safe slug."""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text)
    return text[:80] or "page"


def _build_md_url_lookup(child_pages: list, site_url: str) -> dict[str, str]:
    """Build URL -> https://site.com/slug.md lookup from child pages."""
    parsed = urlparse(site_url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    lookup: dict[str, str] = {}
    seen_names: set[str] = set()
    for cp in child_pages:
        name = slugify(cp.title if hasattr(cp, 'title') else cp['title'])
        base_name = name
        counter = 1
        while name in seen_names:
            name = f"{base_name}-{counter}"
            counter += 1
        seen_names.add(name)
        original_url = cp.url if hasattr(cp, 'url') else cp['url']
        lookup[original_url] = f"{base}/{name}.md"
    return lookup


def _assemble_lines(structured_data: dict[str, Any], url_lookup: dict[str, str] | None = None) -> str:
    """Core assembly logic. url_lookup remaps page URLs if provided."""
    lines: list[str] = []

    lines.append(f"# {structured_data['site_name']}")
    lines.append("")

    if structured_data.get("summary"):
        lines.append(f"> {structured_data['summary']}")
        lines.append("")

    if structured_data.get("context"):
        lines.append(structured_data["context"])
        lines.append("")

    for section in structured_data.get("sections", []):
        lines.append(f"## {section['name']}")
        lines.append("")
        for page in section.get("pages", []):
            title = page.get("title", page["url"])
            url = page["url"]
            link_target = url_lookup.get(url, url) if url_lookup else url
            desc = page.get("description", "")
            if desc:
                lines.append(f"- [{title}]({link_target}): {desc}")
            else:
                lines.append(f"- [{title}]({link_target})")
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def assemble_base_markdown(structured_data: dict[str, Any]) -> str:
    """Assemble llms.txt with original site URLs."""
    return _assemble_lines(structured_data)


def assemble_md_markdown(structured_data: dict[str, Any], child_pages: list, site_url: str) -> str:
    """Assemble llms.txt with .md file URLs (e.g. https://example.com/slug.md)."""
    lookup = _build_md_url_lookup(child_pages, site_url)
    return _assemble_lines(structured_data, url_lookup=lookup)


def assemble_llms_ctx(structured_data: dict[str, Any], child_pages: list) -> str:
    """
    Build llms-ctx.txt — expands linked URLs with actual page content
    using XML <doc> tags, suitable for LLM consumption.
    """
    content_lookup = {
        (cp.url if hasattr(cp, 'url') else cp['url']): cp
        for cp in child_pages
    }

    lines: list[str] = []

    lines.append(f"# {structured_data['site_name']}")
    lines.append("")

    if structured_data.get("summary"):
        lines.append(f"> {structured_data['summary']}")
        lines.append("")

    if structured_data.get("context"):
        lines.append(structured_data["context"])
        lines.append("")

    for section in structured_data.get("sections", []):
        lines.append(f"## {section['name']}")
        lines.append("")
        for page in section.get("pages", []):
            url = page["url"]
            title = page.get("title", url)
            cp = content_lookup.get(url)
            if cp:
                cp_title = cp.title if hasattr(cp, 'title') else cp['title']
                cp_content = cp.markdown_content if hasattr(cp, 'markdown_content') else cp['markdown_content']
                lines.append(f'<doc url="{url}" title="{cp_title}">')
                lines.append(cp_content)
                lines.append("</doc>")
                lines.append("")
            else:
                desc = page.get("description", "")
                if desc:
                    lines.append(f"- [{title}]({url}): {desc}")
                else:
                    lines.append(f"- [{title}]({url})")
        lines.append("")

    return "\n".join(lines).strip() + "\n"

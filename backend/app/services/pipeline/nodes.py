import logging
from urllib.parse import urlparse

from app.config import settings
from app.models.generation import Generation
from app.services.pipeline.node import PipelineNode
from app.services.progress import StepProgressReporter
from app.services import http, html
from app.services.generator import (
    assemble_base_markdown,
    assemble_md_markdown,
    assemble_llms_ctx,
)
from app.services.llm.factory import get_llm_provider
from app.testing.mock_llm import MockLLMProvider

logger = logging.getLogger("app.pipeline.nodes")


class CrawlNode(PipelineNode):
    def __init__(self):
        super().__init__("crawl")

    async def execute(
        self, generation: Generation, reporter: StepProgressReporter
    ) -> None:
        await reporter.started("Discovering pages...")

        base_domain = urlparse(generation.url).netloc
        discovered: set[str] = set()

        # Try sitemap first
        sitemap_urls = await http.fetch_sitemap_urls(generation.url)
        if sitemap_urls:
            discovered.update(sitemap_urls)
            await reporter.log(f"Sitemap: {len(sitemap_urls)} URLs")
        else:
            await reporter.log("No sitemap found, falling back to link crawl")

        # Fallback: crawl links from homepage
        if len(discovered) < 5:
            resp = await http.fetch_url(
                generation.url, timeout=settings.crawl_timeout
            )
            if resp:
                links = html.extract_links(resp.text, generation.url, base_domain)
                discovered.update(links)
                await reporter.log(f"Link crawl: {len(links)} URLs from homepage")

        # Always include homepage
        discovered.add(generation.url.rstrip("/"))

        # Filter to same domain, cap
        filtered = [u for u in discovered if urlparse(u).netloc == base_domain]
        generation.discovered_urls = filtered[: settings.max_pages]
        await reporter.completed(f"Found {len(generation.discovered_urls)} pages")


class ExtractMetadataNode(PipelineNode):
    def __init__(self):
        super().__init__("metadata")

    async def execute(
        self, generation: Generation, reporter: StepProgressReporter
    ) -> None:
        await reporter.started("Extracting metadata from pages...")

        def _handler(url, resp):
            return html.extract_page_metadata(resp.text, url)

        generation.pages = await http.fetch_urls_concurrent(
            generation.discovered_urls,
            _handler,
            concurrency=settings.content_fetch_concurrency,
            reporter=reporter,
            progress_message_fn=lambda done, total: f"Extracting metadata {done}/{total}...",
            detail_fn=lambda url, result: result.title if result else url,
        )
        await reporter.completed(
            f"Extracted metadata from {len(generation.pages)} pages"
        )


class FetchHomepageNode(PipelineNode):
    def __init__(self):
        super().__init__("fetch_homepage")

    async def execute(
        self, generation: Generation, reporter: StepProgressReporter
    ) -> None:
        await reporter.started("Fetching homepage content...")

        try:
            resp = await http.fetch_url(generation.url)
            if resp:
                result = html.html_to_markdown(resp.text, generation.url)
                if result:
                    generation.homepage_markdown = result.markdown_content
                    await reporter.completed(
                        f"Homepage: {len(result.markdown_content)} chars"
                    )
                    return
        except Exception as e:
            logger.warning(
                "[%s] Homepage fetch failed: %s", generation.id[:8], e
            )

        await reporter.completed("Could not fetch homepage content")


class CategorizeNode(PipelineNode):
    def __init__(self):
        super().__init__("ai_categorize")

    async def execute(
        self, generation: Generation, reporter: StepProgressReporter
    ) -> None:
        if settings.mock_llm:
            await reporter.started("Using mock data (MOCK_LLM=true)...")
            generation.structured_data = MockLLMProvider.mock_structured_data(
                generation.url, generation.pages
            )
        else:
            await reporter.started("Analyzing site structure with AI...")
            llm = get_llm_provider()
            generation.structured_data = await llm.categorize_pages(
                generation.url,
                generation.pages,
                client_info=generation.client_info,
                homepage_markdown=generation.homepage_markdown,
                reporter=reporter,
            )

        section_count = len(generation.structured_data.get("sections", []))
        await reporter.completed(f"Categorized into {section_count} sections")


class FetchChildrenNode(PipelineNode):
    def __init__(self):
        super().__init__("fetch_content")

    async def execute(
        self, generation: Generation, reporter: StepProgressReporter
    ) -> None:
        child_urls = []
        for section in generation.structured_data.get("sections", []):
            for page in section.get("pages", []):
                child_urls.append(page["url"])

        await reporter.started(
            f"Fetching content from {len(child_urls)} pages..."
        )

        if child_urls:

            def _handler(url, resp):
                return html.html_to_markdown(resp.text, url)

            generation.child_pages = await http.fetch_urls_concurrent(
                child_urls,
                _handler,
                concurrency=settings.content_fetch_concurrency,
                reporter=reporter,
                progress_message_fn=lambda done, total: f"Fetching content {done}/{total}...",
                detail_fn=lambda url, result: (
                    f"{url} — {len(result.markdown_content)} chars"
                    if result
                    else f"{url} — failed"
                ),
            )

        await reporter.completed(
            f"Fetched {len(generation.child_pages)} of {len(child_urls)} pages"
        )


class BuildContextNode(PipelineNode):
    def __init__(self):
        super().__init__("build_context")

    async def execute(
        self, generation: Generation, reporter: StepProgressReporter
    ) -> None:
        await reporter.started("Building expanded context...")
        generation.llms_ctx = assemble_llms_ctx(
            generation.structured_data, generation.child_pages
        )
        await reporter.completed(f"Context built: {len(generation.llms_ctx)} chars")


class AssembleNode(PipelineNode):
    def __init__(self):
        super().__init__("assemble")

    async def execute(
        self, generation: Generation, reporter: StepProgressReporter
    ) -> None:
        await reporter.started("Building final output files...")

        generation.markdown_base = assemble_base_markdown(
            generation.structured_data
        )

        if generation.child_pages:
            generation.markdown_md = assemble_md_markdown(
                generation.structured_data,
                generation.child_pages,
                generation.url,
            )
        else:
            generation.markdown_md = generation.markdown_base

        await reporter.completed("Output files ready")

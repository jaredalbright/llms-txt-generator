import asyncio
import logging
from urllib.parse import urlparse

from app.config import settings
from app.models.generation import Generation
from app.services.pipeline.node import PipelineNode
from app.services.progress import StepProgressReporter
from app.services import http, html
from app.services import url_utils
from app.services.generator import (
    assemble_base_markdown,
    assemble_md_markdown,
    assemble_llms_ctx,
)
from app.services.llm.factory import get_llm_provider
from app.testing.mock_llm import MockLLMProvider

logger = logging.getLogger("app.pipeline.nodes")


class CrawlNode(PipelineNode):
    """Discover pages via sitemap + BFS crawl, filter junk, rank & cap."""

    def __init__(self):
        super().__init__("crawl")

    async def execute(
        self, generation: Generation, reporter: StepProgressReporter
    ) -> None:
        await reporter.started("Discovering pages...")

        base_domain = urlparse(generation.url).netloc
        homepage_url = generation.url.rstrip("/")
        url_meta: dict[str, dict] = {}  # url -> {source, depth, inlink_count}

        def _register(url: str, source: str, depth: int):
            """Register a discovered URL, updating metadata."""
            if url in url_meta:
                # Keep the best source and shallowest depth
                existing = url_meta[url]
                existing["inlink_count"] = existing.get("inlink_count", 0) + 1
                if _source_weight(source) > _source_weight(existing["source"]):
                    existing["source"] = source
                if depth < existing["depth"]:
                    existing["depth"] = depth
            else:
                url_meta[url] = {"source": source, "depth": depth, "inlink_count": 1}

        def _source_weight(source: str) -> float:
            return {"nav": 3.0, "sitemap": 2.0, "body": 1.0}.get(source, 1.0)

        # 1. Sitemap
        sitemap_urls = await http.fetch_sitemap_urls(generation.url)
        if sitemap_urls:
            for u in sitemap_urls:
                normalized = url_utils.normalize_url(u)
                if urlparse(normalized).netloc == base_domain:
                    _register(normalized, "sitemap", 0)
            await reporter.log(f"Sitemap: {len(sitemap_urls)} URLs")
        else:
            await reporter.log("No sitemap found, falling back to BFS crawl")

        # 2. Homepage HTML — fetch, cache, extract nav + body links
        resp = await http.fetch_url(generation.url, timeout=settings.crawl_timeout)
        if resp:
            generation._html_cache[homepage_url] = resp.text
            nav_links = html.extract_nav_links(resp.text, generation.url, base_domain)
            body_links = html.extract_links(resp.text, generation.url, base_domain)

            for u in nav_links:
                _register(u, "nav", 0)
            for u in body_links - nav_links:
                _register(u, "body", 0)

            await reporter.log(
                f"Homepage: {len(nav_links)} nav links, {len(body_links)} body links"
            )

        # Always include homepage
        _register(homepage_url, "nav", 0)

        # 3. BFS Level 1 — fetch top unfetched level-0 links
        level0_urls = [
            u for u, m in url_meta.items()
            if m["depth"] == 0 and u not in generation._html_cache
        ]
        # Sort by current score descending, take top N
        level0_urls.sort(
            key=lambda u: url_utils.score_url(u, **url_meta[u]), reverse=True
        )
        bfs_urls = level0_urls[: settings.bfs_max_level1_urls]

        if bfs_urls:
            await reporter.log(f"BFS: fetching {len(bfs_urls)} level-1 pages...")

            bfs_results: dict[str, str] = {}

            def _bfs_handler(url, resp):
                bfs_results[url] = resp.text
                return url

            await http.fetch_urls_concurrent(
                bfs_urls,
                _bfs_handler,
                concurrency=settings.content_fetch_concurrency,
                timeout=settings.crawl_timeout,
                reporter=reporter,
                progress_message_fn=lambda done, total: f"BFS crawl {done}/{total}...",
                detail_fn=lambda url, _: url,
            )

            # Cache HTML and extract depth-1 links
            for url, page_html in bfs_results.items():
                generation._html_cache[url] = page_html
                child_links = html.extract_links(page_html, url, base_domain)
                for cl in child_links:
                    _register(cl, "body", 1)

            await reporter.log(f"BFS: cached {len(bfs_results)} pages")

        # 4. Filter junk URLs
        all_urls = list(url_meta.keys())
        clean_urls = url_utils.filter_junk_urls(all_urls)
        # Rebuild url_meta with only clean URLs
        url_meta = {u: url_meta[u] for u in clean_urls if u in url_meta}

        # 5. Rank & cap
        ranked = url_utils.rank_and_cap(url_meta, settings.max_pages)

        generation.discovered_urls = ranked
        generation.url_metadata = url_meta
        await reporter.completed(f"Found {len(ranked)} pages (from {len(all_urls)} discovered)")


class ExtractMetadataNode(PipelineNode):
    """Extract metadata, using HTML cache where available."""

    def __init__(self):
        super().__init__("metadata")

    async def execute(
        self, generation: Generation, reporter: StepProgressReporter
    ) -> None:
        await reporter.started("Extracting metadata from pages...")

        results = []
        uncached_urls = []

        # Process cached pages directly
        for url in generation.discovered_urls:
            cached_html = generation._html_cache.get(url)
            if cached_html:
                meta = html.extract_page_metadata(cached_html, url)
                if meta:
                    results.append(meta)
            else:
                uncached_urls.append(url)

        if results:
            await reporter.log(f"Cache hit: {len(results)} pages")

        # Fetch uncached pages
        if uncached_urls:
            def _handler(url, resp):
                # Cache the HTML for downstream use
                generation._html_cache[url] = resp.text
                return html.extract_page_metadata(resp.text, url)

            fetched = await http.fetch_urls_concurrent(
                uncached_urls,
                _handler,
                concurrency=settings.content_fetch_concurrency,
                reporter=reporter,
                progress_message_fn=lambda done, total: f"Extracting metadata {done}/{total}...",
                detail_fn=lambda url, result: result.title if result else url,
            )
            results.extend(fetched)

        generation.pages = results
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

        homepage_url = generation.url.rstrip("/")

        try:
            # Check cache first
            cached_html = generation._html_cache.get(homepage_url)
            if cached_html:
                result = html.html_to_markdown(cached_html, generation.url)
                if result:
                    generation.homepage_markdown = result.markdown_content
                    await reporter.completed(
                        f"Homepage (cached): {len(result.markdown_content)} chars"
                    )
                    return

            # Fallback: fetch
            resp = await http.fetch_url(generation.url)
            if resp:
                generation._html_cache[homepage_url] = resp.text
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
                url_metadata=generation.url_metadata or None,
                prompts_context=generation.prompts_context or None,
                reporter=reporter,
            )

        section_count = len(generation.structured_data.get("sections", []))
        await reporter.completed(f"Categorized into {section_count} sections")


class FetchChildrenNode(PipelineNode):
    """Fetch child page content, using HTML cache where available."""

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

        results = []
        uncached_urls = []

        # Process cached pages directly
        for url in child_urls:
            cached_html = generation._html_cache.get(url)
            if cached_html:
                result = html.html_to_markdown(cached_html, url)
                if result:
                    results.append(result)
            else:
                uncached_urls.append(url)

        if results:
            await reporter.log(f"Cache hit: {len(results)} pages")

        # Fetch uncached pages
        if uncached_urls:
            def _handler(url, resp):
                generation._html_cache[url] = resp.text
                return html.html_to_markdown(resp.text, url)

            fetched = await http.fetch_urls_concurrent(
                uncached_urls,
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
            results.extend(fetched)

        generation.child_pages = results
        await reporter.completed(
            f"Fetched {len(generation.child_pages)} of {len(child_urls)} pages"
        )


class SummarizeNode(PipelineNode):
    """Build llms-ctx, then optionally refine descriptions via LLM summarize pass."""

    def __init__(self):
        super().__init__("summarize")

    async def execute(
        self, generation: Generation, reporter: StepProgressReporter
    ) -> None:
        await reporter.started("Building context and refining descriptions...")

        # 1. Build initial llms_ctx
        generation.llms_ctx = assemble_llms_ctx(
            generation.structured_data, generation.child_pages
        )
        await reporter.log(f"Context built: {len(generation.llms_ctx)} chars")

        # 2. If real LLM available, refine descriptions using actual page content
        if not settings.mock_llm and generation.llms_ctx:
            try:
                llm = get_llm_provider()
                await reporter.log("Refining descriptions with AI...")
                generation.structured_data = await llm.summarize(
                    generation.llms_ctx,
                    generation.url,
                    generation.structured_data,
                    prompts_context=generation.prompts_context or None,
                    reporter=reporter,
                )
                # Rebuild llms_ctx with improved data
                generation.llms_ctx = assemble_llms_ctx(
                    generation.structured_data, generation.child_pages
                )
                await reporter.log(f"Context rebuilt: {len(generation.llms_ctx)} chars")
            except Exception as e:
                logger.warning(
                    "[%s] Summarize pass failed, using original data: %s",
                    generation.id[:8], e,
                )
                await reporter.log(f"Summarize pass skipped: {e}")

        await reporter.completed("Context and descriptions ready")


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

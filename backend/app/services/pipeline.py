import asyncio
import logging
import traceback
import httpx
from app.config import settings
from app.services.progress import StepProgressReporter
from app.services.crawler import crawl_site
from app.services.extractor import extract_metadata
from app.services.llm.factory import get_llm_provider
from app.services.content_fetcher import fetch_child_pages, fetch_and_convert
from app.services.generator import assemble_base_markdown, assemble_md_markdown, assemble_llms_ctx
from app.testing.mock_llm import MockLLMProvider

logger = logging.getLogger("app.pipeline")


async def run_pipeline(job_id: str, url: str, jobs: dict):
    """
    Full async pipeline:
    1. Crawl the site (discover URLs)
    2. Extract metadata from each page
    3. LLM categorization -> initial structured_data
    4. Fetch child pages -> .md content
    5. Build llms-ctx (expanded context with inlined content)
    6. LLM summarize using llms-ctx -> improved structured_data
    7. Assemble final outputs (base llms.txt, md llms.txt)
    """
    job = jobs[job_id]
    queue: asyncio.Queue = job["event_queue"]

    logger.info("[%s] Pipeline started for %s", job_id[:8], url)

    try:
        # --- Step 1: Crawl ---
        logger.info("[%s] Step 1: Crawling...", job_id[:8])
        crawl_reporter = StepProgressReporter(queue, "crawl")
        await crawl_reporter.started("Discovering pages...")

        urls = await crawl_site(url, reporter=crawl_reporter)
        logger.info("[%s] Crawl complete: %d URLs discovered", job_id[:8], len(urls))

        await crawl_reporter.completed(f"Found {len(urls)} pages")

        # --- Step 2: Extract metadata ---
        logger.info("[%s] Step 2: Extracting metadata...", job_id[:8])
        meta_reporter = StepProgressReporter(queue, "metadata")
        await meta_reporter.started("Extracting metadata from pages...")

        pages = await extract_metadata(urls, reporter=meta_reporter)
        logger.info("[%s] Extraction complete: %d pages with metadata", job_id[:8], len(pages))

        await meta_reporter.completed(f"Extracted metadata from {len(pages)} pages")

        # --- Step 2b: Fetch homepage as markdown ---
        logger.info("[%s] Step 2b: Fetching homepage content as markdown...", job_id[:8])
        homepage_markdown = None
        try:
            async with httpx.AsyncClient() as client:
                homepage_result = await fetch_and_convert(url, client)
                if homepage_result:
                    homepage_markdown = homepage_result.markdown_content
                    logger.info("[%s] Homepage markdown: %d chars", job_id[:8], len(homepage_markdown))
                else:
                    logger.warning("[%s] Could not fetch homepage content", job_id[:8])
        except Exception as e:
            logger.warning("[%s] Homepage fetch failed: %s", job_id[:8], e)

        # --- Step 3: LLM categorization ---
        ai_reporter = StepProgressReporter(queue, "ai_categorize")
        await ai_reporter.started(
            "Analyzing site structure with AI..."
            if not settings.mock_llm else "Using mock data (MOCK_LLM=true)..."
        )

        client_info = job.get("client_info")
        if settings.mock_llm:
            logger.info("[%s] Step 3: Using mock LLM data", job_id[:8])
            structured_data = MockLLMProvider.mock_structured_data(url, pages)
        else:
            logger.info("[%s] Step 3: Calling LLM (%s)...", job_id[:8], settings.llm_provider)
            llm = get_llm_provider()
            structured_data = await llm.categorize_pages(url, pages, client_info=client_info, homepage_markdown=homepage_markdown, reporter=ai_reporter)
            logger.info("[%s] LLM response: %d sections", job_id[:8], len(structured_data.get("sections", [])))

        section_count = len(structured_data.get("sections", []))
        await ai_reporter.completed(f"Categorized into {section_count} sections")

        # --- Step 4: Fetch child pages ---
        logger.info("[%s] Step 4: Fetching child page content...", job_id[:8])
        child_urls = []
        for section in structured_data.get("sections", []):
            for page in section.get("pages", []):
                child_urls.append(page["url"])

        fetch_reporter = StepProgressReporter(queue, "fetch_content")
        await fetch_reporter.started(f"Fetching content from {len(child_urls)} pages...")

        child_pages = []
        if child_urls:
            child_pages = await fetch_child_pages(
                child_urls, reporter=fetch_reporter, concurrency=settings.content_fetch_concurrency
            )
            logger.info("[%s] Fetched %d/%d child pages", job_id[:8], len(child_pages), len(child_urls))

        await fetch_reporter.completed(f"Fetched {len(child_pages)} of {len(child_urls)} pages")

        # --- Step 5: Build llms-ctx ---
        logger.info("[%s] Step 5: Building llms-ctx...", job_id[:8])
        llms_ctx = assemble_llms_ctx(structured_data, child_pages)
        logger.info("[%s] llms-ctx built: %d chars", job_id[:8], len(llms_ctx))

        # --- Step 6: Summarize (currently disabled) ---
        logger.info("[%s] Step 6: Skipping summarization (temporarily disabled)", job_id[:8])

        # --- Step 7: Assemble final outputs ---
        logger.info("[%s] Step 7: Assembling outputs...", job_id[:8])
        assemble_reporter = StepProgressReporter(queue, "assemble")
        await assemble_reporter.started("Building final output files...")

        markdown_base = assemble_base_markdown(structured_data)
        markdown_md = assemble_md_markdown(structured_data, child_pages, url) if child_pages else markdown_base
        logger.info("[%s] Assembly complete: base=%d chars, md=%d chars", job_id[:8], len(markdown_base), len(markdown_md))

        await assemble_reporter.completed("Output files ready")

        # --- Step 8: Done ---
        job["status"] = "completed"
        job["markdown"] = markdown_base
        job["markdown_md"] = markdown_md
        job["llms_ctx"] = llms_ctx
        job["child_pages"] = child_pages

        await queue.put({
            "type": "complete",
            "markdown": markdown_base,
        })

        logger.info("[%s] Pipeline finished successfully", job_id[:8])

    except Exception as e:
        logger.error("[%s] Pipeline failed: %s", job_id[:8], e)
        logger.debug("[%s] Traceback:\n%s", job_id[:8], traceback.format_exc())
        job["status"] = "error"
        job["error"] = str(e)
        await queue.put({
            "type": "error",
            "message": f"Generation failed: {str(e)}",
        })

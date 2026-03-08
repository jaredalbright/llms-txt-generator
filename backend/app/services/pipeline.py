import asyncio
import logging
import traceback
from app.config import settings
from app.services.crawler import crawl_site
from app.services.extractor import extract_metadata
from app.services.llm.factory import get_llm_provider
from app.services.content_fetcher import fetch_child_pages
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
        await queue.put({
            "type": "progress",
            "status": "crawling",
            "message": "Discovering pages...",
            "pages_found": 0,
        })

        urls = await crawl_site(url)
        logger.info("[%s] Crawl complete: %d URLs discovered", job_id[:8], len(urls))

        await queue.put({
            "type": "progress",
            "status": "crawling",
            "message": f"Found {len(urls)} pages. Extracting metadata...",
            "pages_found": len(urls),
        })

        # --- Step 2: Extract metadata ---
        logger.info("[%s] Step 2: Extracting metadata...", job_id[:8])
        pages = await extract_metadata(urls)
        logger.info("[%s] Extraction complete: %d pages with metadata", job_id[:8], len(pages))

        await queue.put({
            "type": "progress",
            "status": "processing",
            "message": "Analyzing site structure with AI..."
                if not settings.mock_llm else "Using mock data (MOCK_LLM=true)...",
            "pages_found": len(pages),
        })

        # --- Step 3: LLM categorization ---
        client_info = job.get("client_info")
        if settings.mock_llm:
            logger.info("[%s] Step 3: Using mock LLM data", job_id[:8])
            structured_data = MockLLMProvider.mock_structured_data(url, pages)
        else:
            logger.info("[%s] Step 3: Calling LLM (%s)...", job_id[:8], settings.llm_provider)
            llm = get_llm_provider()
            structured_data = await llm.categorize_pages(url, pages, client_info=client_info)
            logger.info("[%s] LLM response: %d sections", job_id[:8], len(structured_data.get("sections", [])))

        # --- Step 4: Fetch child pages ---
        logger.info("[%s] Step 4: Fetching child page content...", job_id[:8])
        child_urls = []
        for section in structured_data.get("sections", []):
            for page in section.get("pages", []):
                child_urls.append(page["url"])

        child_pages = []
        if child_urls:
            child_pages = await fetch_child_pages(
                child_urls, queue, concurrency=settings.content_fetch_concurrency
            )
            logger.info("[%s] Fetched %d/%d child pages", job_id[:8], len(child_pages), len(child_urls))

        # --- Step 5: Build llms-ctx ---
        logger.info("[%s] Step 5: Building llms-ctx...", job_id[:8])
        llms_ctx = assemble_llms_ctx(structured_data, child_pages)
        logger.info("[%s] llms-ctx built: %d chars", job_id[:8], len(llms_ctx))

        # --- Step 6: Summarize using llms-ctx ---
        await queue.put({
            "type": "progress",
            "status": "summarizing",
            "message": "Improving descriptions with page content..."
                if not settings.mock_llm else "Using mock summarization (MOCK_LLM=true)...",
            "pages_found": len(pages),
        })

        if settings.mock_llm:
            logger.info("[%s] Step 6: Using mock summarization", job_id[:8])
            # Mock: just use the original structured_data as-is
        else:
            logger.info("[%s] Step 6: Summarizing with LLM...", job_id[:8])
            llm = get_llm_provider()
            structured_data = await llm.summarize(llms_ctx, url, structured_data)
            logger.info("[%s] Summarization complete", job_id[:8])

        # --- Step 7: Assemble final outputs ---
        logger.info("[%s] Step 7: Assembling outputs...", job_id[:8])
        markdown_base = assemble_base_markdown(structured_data)
        markdown_md = assemble_md_markdown(structured_data, child_pages, url) if child_pages else markdown_base
        logger.info("[%s] Assembly complete: base=%d chars, md=%d chars", job_id[:8], len(markdown_base), len(markdown_md))

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

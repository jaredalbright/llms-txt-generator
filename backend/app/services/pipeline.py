import asyncio
import logging
import traceback
from urllib.parse import urlparse
from app.config import settings
from app.services.crawler import crawl_site
from app.services.extractor import extract_metadata
from app.services.llm.factory import get_llm_provider
from app.services.generator import assemble_markdown

logger = logging.getLogger("app.pipeline")


def _mock_structured_data(url: str, pages: list) -> dict:
    """Return fixture data that skips LLM calls entirely."""
    domain = urlparse(url).netloc
    sections = [
        {
            "name": "Main",
            "pages": [
                {"title": p.title, "url": p.url, "description": p.description or "Mock description"}
                for p in pages[:10]
            ],
        },
    ]
    if len(pages) > 10:
        sections.append({
            "name": "Optional",
            "pages": [
                {"title": p.title, "url": p.url, "description": p.description or "Mock description"}
                for p in pages[10:]
            ],
        })
    return {
        "site_name": domain,
        "summary": f"A website at {domain}.",
        "context": None,
        "sections": sections,
    }


async def run_pipeline(job_id: str, url: str, jobs: dict):
    """
    Full async pipeline:
    1. Crawl the site (discover URLs)
    2. Extract metadata from each page
    3. Send to LLM for categorization + summarization
    4. Assemble the final Markdown
    5. Push result via SSE event queue
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

        # --- Step 2: Extract ---
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

        # --- Step 3: LLM (or mock) ---
        client_info = job.get("client_info")
        if settings.mock_llm:
            logger.info("[%s] Step 3: Using mock LLM data", job_id[:8])
            structured_data = _mock_structured_data(url, pages)
        else:
            logger.info("[%s] Step 3: Calling LLM (%s)...", job_id[:8], settings.llm_provider)
            llm = get_llm_provider()
            structured_data = await llm.categorize_pages(url, pages, client_info=client_info)
            logger.info("[%s] LLM response: %d sections", job_id[:8], len(structured_data.get("sections", [])))

        # --- Step 4: Assemble ---
        logger.info("[%s] Step 4: Assembling markdown...", job_id[:8])
        markdown = assemble_markdown(structured_data)
        logger.info("[%s] Assembly complete: %d chars", job_id[:8], len(markdown))

        # --- Step 5: Done ---
        job["status"] = "completed"
        job["markdown"] = markdown

        await queue.put({
            "type": "complete",
            "markdown": markdown,
        })

        logger.info("[%s] Pipeline finished successfully", job_id[:8])

        # TODO: Persist to Supabase
        # await db.jobs.update(job_id, status="completed", markdown=markdown)

    except Exception as e:
        logger.error("[%s] Pipeline failed: %s", job_id[:8], e)
        logger.debug("[%s] Traceback:\n%s", job_id[:8], traceback.format_exc())
        job["status"] = "error"
        job["error"] = str(e)
        await queue.put({
            "type": "error",
            "message": f"Generation failed: {str(e)}",
        })

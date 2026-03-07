import asyncio
import json
import logging
import uuid
from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse
from app.models import (
    GenerateRequest,
    GenerateResponse,
    RepromptRequest,
    RepromptResponse,
)
from app.services.pipeline import run_pipeline
from app.services.llm.factory import get_llm_provider

logger = logging.getLogger("app.router.generate")

router = APIRouter()

# In-memory job store — replace with Supabase in production
# Key: job_id, Value: { status, pages_found, markdown, error, events: asyncio.Queue }
jobs: dict[str, dict] = {}


@router.post("/generate", response_model=GenerateResponse)
async def create_job(req: GenerateRequest):
    job_id = str(uuid.uuid4())
    event_queue = asyncio.Queue()

    jobs[job_id] = {
        "status": "pending",
        "url": str(req.url),
        "client_info": req.client_info,
        "pages_found": 0,
        "markdown": None,
        "error": None,
        "event_queue": event_queue,
    }

    logger.info("Job %s created for URL: %s (client_info: %s)", job_id, req.url, "yes" if req.client_info else "no")

    # Run on the event loop so it shares the same queue as the SSE endpoint
    asyncio.create_task(run_pipeline(job_id, str(req.url), jobs))

    return GenerateResponse(job_id=job_id)


@router.get("/generate/{job_id}/stream")
async def stream_job(job_id: str):
    """SSE endpoint. Client connects here after POST /generate returns job_id."""
    if job_id not in jobs:
        logger.warning("SSE stream requested for unknown job: %s", job_id)
        return {"error": "Job not found"}

    job = jobs[job_id]
    logger.info("SSE stream opened for job %s (current status: %s)", job_id, job["status"])

    async def event_generator():
        queue: asyncio.Queue = job["event_queue"]

        while True:
            event = await queue.get()
            event_type = event["type"]
            logger.debug("SSE yielding event '%s' for job %s", event_type, job_id)

            if event_type == "progress":
                yield {
                    "event": "progress",
                    "data": json.dumps({
                        "status": event["status"],
                        "pages_found": event.get("pages_found", 0),
                        "message": event.get("message", ""),
                    }),
                }

            elif event_type == "complete":
                md_len = len(event.get("markdown", ""))
                logger.info("SSE complete for job %s (%d chars of markdown)", job_id, md_len)
                yield {
                    "event": "complete",
                    "data": json.dumps({
                        "markdown": event["markdown"],
                        "job_id": job_id,
                    }),
                }
                return  # Close the stream

            elif event_type == "error":
                logger.error("SSE error for job %s: %s", job_id, event["message"])
                yield {
                    "event": "error",
                    "data": json.dumps({
                        "message": event["message"],
                    }),
                }
                return

    return EventSourceResponse(event_generator(), ping=15)


@router.post("/reprompt", response_model=RepromptResponse)
async def reprompt(req: RepromptRequest):
    """Synchronous LLM call to modify existing markdown based on user instruction."""
    from app.config import settings

    logger.info("Reprompt for job %s: %s", req.job_id, req.instruction[:100])

    if settings.mock_llm:
        logger.debug("Using mock reprompt (MOCK_LLM=true)")
        return RepromptResponse(
            markdown=req.current_markdown + f"\n\n<!-- Mock reprompt: {req.instruction} -->\n"
        )

    llm = get_llm_provider()
    updated_markdown = await llm.reprompt(req.current_markdown, req.instruction)
    logger.info("Reprompt complete for job %s (%d chars)", req.job_id, len(updated_markdown))
    return RepromptResponse(markdown=updated_markdown)

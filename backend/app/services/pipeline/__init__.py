import asyncio
import logging
import traceback

from app.config import settings
from app.db.repository import JobRepository
from app.db.generation_store import get_generation_store
from app.services.errors import sanitize_error
from app.services.pipeline.dag import PipelineDAG
from app.services.pipeline.nodes import (
    CrawlNode,
    FetchHomepageNode,
    ExtractMetadataNode,
    CategorizeNode,
    FetchChildrenNode,
    SummarizeNode,
    AssembleNode,
)

logger = logging.getLogger("app.pipeline")


def build_default_dag() -> PipelineDAG:
    """Build the default pipeline DAG.

    DAG structure:
        crawl ──────────> extract_metadata ──┐
                                              ├──> categorize ──> fetch_children ──> summarize ──> assemble
        fetch_homepage ──────────────────────┘
    """
    dag = PipelineDAG()
    dag.add_node(CrawlNode())
    dag.add_node(FetchHomepageNode())
    dag.add_node(ExtractMetadataNode(), depends_on=["crawl"])
    dag.add_node(CategorizeNode(), depends_on=["metadata", "fetch_homepage"])
    dag.add_node(FetchChildrenNode(), depends_on=["ai_categorize"])
    dag.add_node(SummarizeNode(), depends_on=["fetch_content"])
    dag.add_node(AssembleNode(), depends_on=["summarize"])
    return dag


async def run_pipeline(job_id: str, url: str, repo: JobRepository, prompts_context: list[str] | None = None):
    """Execute the generation pipeline as a DAG of nodes."""
    job = await repo.get(job_id)
    queue: asyncio.Queue = job.event_queue

    logger.info("[%s] Pipeline started for %s", job_id[:8], url)

    gen_store = get_generation_store()
    generation = await gen_store.create(
        generation_id=job_id,
        url=url,
        client_info=job.client_info,
        prompts_context=prompts_context,
    )

    try:
        dag = build_default_dag()
        await asyncio.wait_for(
            dag.execute(generation, queue),
            timeout=settings.job_timeout,
        )

        # Persist generation outputs to the generation store (Supabase or in-memory)
        await gen_store.update(
            job_id,
            status="completed",
            markdown_base=generation.markdown_base,
            markdown_md=generation.markdown_md,
            llms_ctx=generation.llms_ctx,
            child_pages=generation.child_pages,
            pages_found=len(generation.pages),
        )

        # Sync final outputs back to the job for backward compatibility
        await repo.update(
            job_id,
            status="completed",
            markdown=generation.markdown_base,
            markdown_md=generation.markdown_md,
            llms_ctx=generation.llms_ctx,
            child_pages=generation.child_pages,
        )

        await queue.put({
            "type": "complete",
            "markdown": generation.markdown_base,
        })

        logger.info("[%s] Pipeline finished successfully", job_id[:8])

    except Exception as e:
        logger.error("[%s] Pipeline failed: %s", job_id[:8], e)
        logger.debug("[%s] Traceback:\n%s", job_id[:8], traceback.format_exc())

        user_message = sanitize_error(e)

        await gen_store.update(job_id, status="error", error=str(e))
        await repo.update(job_id, status="error", error=str(e))

        await queue.put({
            "type": "error",
            "message": f"Generation failed: {user_message}",
        })

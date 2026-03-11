import logging
from fastapi import APIRouter, HTTPException
from app.db.generation_store import get_generation_store

logger = logging.getLogger("app.router.generations")
router = APIRouter()


@router.get("/generations/recent")
async def recent_generations(limit: int = 10):
    """Return recently completed generations."""
    store = get_generation_store()
    results = await store.list_recent(limit=min(limit, 50))
    return results


@router.get("/generations/search")
async def search_generations(url: str, limit: int = 3):
    """Search for previous generations matching a URL."""
    store = get_generation_store()
    results = await store.find_by_url(url, limit=min(limit, 10))
    return results


@router.get("/generations/{generation_id}")
async def get_generation(generation_id: str):
    """Return a single generation with its markdown."""
    store = get_generation_store()
    gen = await store.get(generation_id)
    if gen is None:
        raise HTTPException(status_code=404, detail="Generation not found")
    return {
        "id": gen.id,
        "url": gen.url,
        "status": "completed" if gen.markdown_base else "pending",
        "markdown": gen.markdown_base,
        "created_at": gen.created_at.isoformat() if gen.created_at else None,
        "pages_found": len(gen.pages) if gen.pages else 0,
    }

import httpx
from fastapi import APIRouter, Query
from fastapi.responses import Response

router = APIRouter()

FAVICON_URL = "https://www.google.com/s2/favicons"


@router.get("/favicon")
async def proxy_favicon(domain: str = Query(...), sz: int = Query(32)):
    """Proxy Google's favicon service to avoid 403s from referrer policies."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            FAVICON_URL,
            params={"domain": domain, "sz": sz},
            timeout=5,
        )

    return Response(
        content=resp.content,
        media_type=resp.headers.get("content-type", "image/png"),
        headers={"Cache-Control": "public, max-age=86400"},
    )

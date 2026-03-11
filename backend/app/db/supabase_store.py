import asyncio
import logging
from datetime import datetime, timezone
from supabase import Client

from app.db.generation_store import GenerationStore
from app.models.generation import Generation
from app.services.url_utils import normalize_url

logger = logging.getLogger("app.db.supabase")


class SupabaseGenerationStore(GenerationStore):
    """GenerationStore backed by Supabase (PostgreSQL)."""

    def __init__(self, client: Client):
        self._client = client

    async def create(
        self,
        generation_id: str,
        url: str,
        client_info: str | None = None,
        prompts_context: list[str] | None = None,
    ) -> Generation:
        row = {
            "id": generation_id,
            "url": url,
            "url_normalized": normalize_url(url),
            "status": "pending",
            "client_info": client_info,
            "prompts_context": prompts_context or [],
        }
        await asyncio.to_thread(
            lambda: self._client.table("generations").insert(row).execute()
        )
        return Generation(
            id=generation_id,
            url=url,
            client_info=client_info,
            prompts_context=prompts_context or [],
        )

    async def get(self, generation_id: str) -> Generation | None:
        result = await asyncio.to_thread(
            lambda: self._client.table("generations")
            .select("*")
            .eq("id", generation_id)
            .maybe_single()
            .execute()
        )
        if not result.data:
            return None
        return self._row_to_generation(result.data)

    async def update(self, generation_id: str, **fields) -> None:
        db_fields: dict = {}
        field_map = {
            "markdown_base": "markdown",
            "markdown_md": "markdown_md",
            "llms_ctx": "llms_ctx",
            "error": "error",
        }
        for key, value in fields.items():
            db_key = field_map.get(key, key)
            if db_key == "child_pages":
                # Serialize ChildPageContent list to JSON-safe dicts
                db_fields[db_key] = [
                    cp if isinstance(cp, dict) else {
                        "url": cp.url,
                        "title": cp.title,
                        "markdown_content": cp.markdown_content,
                    }
                    for cp in value
                ] if value else []
            elif db_key == "status":
                db_fields[db_key] = value
            else:
                db_fields[db_key] = value

        # Auto-set status to completed when markdown is written
        if "status" not in db_fields and "markdown" in db_fields:
            db_fields["status"] = "completed"

        await asyncio.to_thread(
            lambda: self._client.table("generations")
            .update(db_fields)
            .eq("id", generation_id)
            .execute()
        )

    async def find_by_url(self, url: str, limit: int = 3) -> list[dict]:
        norm = normalize_url(url)
        result = await asyncio.to_thread(
            lambda: self._client.table("generations")
            .select("id, url, status, created_at, pages_found")
            .eq("url_normalized", norm)
            .eq("status", "completed")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return result.data or []

    async def list_recent(self, limit: int = 10) -> list[dict]:
        result = await asyncio.to_thread(
            lambda: self._client.table("generations")
            .select("id, url, status, created_at, pages_found")
            .eq("status", "completed")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return result.data or []

    def _row_to_generation(self, row: dict) -> Generation:
        """Convert a Supabase row dict to a Generation dataclass."""
        gen = Generation(
            id=row["id"],
            url=row["url"],
            client_info=row.get("client_info"),
            prompts_context=row.get("prompts_context") or [],
        )
        gen.markdown_base = row.get("markdown")
        gen.markdown_md = row.get("markdown_md")
        gen.llms_ctx = row.get("llms_ctx")
        gen.error = row.get("error")
        if row.get("child_pages"):
            from app.models.base import ChildPageContent
            gen.child_pages = [
                ChildPageContent(**cp) if isinstance(cp, dict) else cp
                for cp in row["child_pages"]
            ]
        if row.get("created_at"):
            gen.created_at = datetime.fromisoformat(row["created_at"])
        if row.get("updated_at"):
            gen.updated_at = datetime.fromisoformat(row["updated_at"])
        return gen

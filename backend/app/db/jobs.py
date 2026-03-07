"""
TODO: Implement these once Supabase is connected.
For now, the in-memory dict in routers/generate.py handles job state.
When ready, swap the in-memory dict for these functions.
"""


async def create_job(url: str) -> str:
    """Insert a new job row, return the UUID."""
    # result = supabase.table("jobs").insert({"url": url, "status": "pending"}).execute()
    # return result.data[0]["id"]
    raise NotImplementedError


async def update_job(job_id: str, **kwargs):
    """Update job fields (status, markdown, pages_found, error_message)."""
    # supabase.table("jobs").update(kwargs).eq("id", job_id).execute()
    raise NotImplementedError


async def get_job(job_id: str) -> dict:
    """Fetch a single job by ID."""
    # result = supabase.table("jobs").select("*").eq("id", job_id).single().execute()
    # return result.data
    raise NotImplementedError

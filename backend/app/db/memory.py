import asyncio

from app.models import Job
from app.db.repository import JobRepository
from app.db.cache import CacheManager


class InMemoryJobCache(JobRepository):
    def __init__(self, cache_manager: CacheManager):
        self._jobs: dict[str, Job] = {}
        self._cache_manager = cache_manager

    async def create(self, job_id: str, url: str, client_info: str | None, event_queue: asyncio.Queue, prompts_context: list[str] | None = None) -> Job:
        job = Job(
            id=job_id,
            status="pending",
            url=url,
            client_info=client_info,
            prompts_context=prompts_context,
            event_queue=event_queue,
        )
        self._jobs[job_id] = job
        self._cache_manager.track(job_id, url)
        return job

    async def get(self, job_id: str) -> Job | None:
        job = self._jobs.get(job_id)
        if job is not None:
            self._cache_manager.touch(job_id)
        return job

    async def update(self, job_id: str, **fields) -> None:
        job = self._jobs.get(job_id)
        if job is None:
            raise KeyError(f"Job {job_id} not found")
        for key, value in fields.items():
            setattr(job, key, value)
        self._cache_manager.touch(job_id)
        if fields.get("status") in ("completed", "error"):
            self._cache_manager.mark_finished(job_id)

    def _remove(self, job_id: str) -> None:
        self._jobs.pop(job_id, None)


# Backward-compat alias
InMemoryJobRepository = InMemoryJobCache

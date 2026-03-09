import asyncio

from app.models import Job
from app.db.repository import JobRepository


class InMemoryJobRepository(JobRepository):
    def __init__(self):
        self._jobs: dict[str, Job] = {}

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
        return job

    async def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    async def update(self, job_id: str, **fields) -> None:
        job = self._jobs.get(job_id)
        if job is None:
            raise KeyError(f"Job {job_id} not found")
        for key, value in fields.items():
            setattr(job, key, value)

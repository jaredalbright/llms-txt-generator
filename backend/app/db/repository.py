import asyncio
from abc import ABC, abstractmethod

from app.models import Job


class JobRepository(ABC):
    @abstractmethod
    async def create(self, job_id: str, url: str, client_info: str | None, event_queue: asyncio.Queue) -> Job: ...

    @abstractmethod
    async def get(self, job_id: str) -> Job | None: ...

    @abstractmethod
    async def update(self, job_id: str, **fields) -> None: ...


_repo: JobRepository | None = None


def init_job_repo(repo: JobRepository) -> None:
    global _repo
    _repo = repo


def get_job_repo() -> JobRepository:
    assert _repo is not None, "JobRepository not initialized"
    return _repo

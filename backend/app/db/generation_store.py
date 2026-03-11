from abc import ABC, abstractmethod
from datetime import datetime, timezone

from app.models.generation import Generation
from app.services.url_utils import normalize_url


class GenerationStore(ABC):
    @abstractmethod
    async def create(
        self, generation_id: str, url: str, client_info: str | None = None, prompts_context: list[str] | None = None
    ) -> Generation: ...

    @abstractmethod
    async def get(self, generation_id: str) -> Generation | None: ...

    @abstractmethod
    async def update(self, generation_id: str, **fields) -> None: ...

    @abstractmethod
    async def find_by_url(self, url: str, limit: int = 3) -> list[dict]: ...

    @abstractmethod
    async def list_recent(self, limit: int = 10) -> list[dict]: ...


class InMemoryGenerationCache(GenerationStore):
    def __init__(self, cache_manager):
        from app.db.cache import CacheManager
        self._generations: dict[str, Generation] = {}
        self._cache_manager: CacheManager = cache_manager

    async def create(
        self, generation_id: str, url: str, client_info: str | None = None, prompts_context: list[str] | None = None
    ) -> Generation:
        gen = Generation(id=generation_id, url=url, client_info=client_info, prompts_context=prompts_context or [])
        self._generations[generation_id] = gen
        return gen

    async def get(self, generation_id: str) -> Generation | None:
        gen = self._generations.get(generation_id)
        if gen is not None:
            self._cache_manager.touch(generation_id)
        return gen

    async def update(self, generation_id: str, **fields) -> None:
        gen = self._generations.get(generation_id)
        if gen is None:
            raise KeyError(f"Generation {generation_id} not found")
        for key, value in fields.items():
            setattr(gen, key, value)
        gen.updated_at = datetime.now(timezone.utc)
        self._cache_manager.touch(generation_id)

    async def find_by_url(self, url: str, limit: int = 3) -> list[dict]:
        """Find completed generations matching a URL."""
        norm = normalize_url(url)
        matches = [
            gen for gen in self._generations.values()
            if normalize_url(gen.url) == norm and gen.markdown_base is not None
        ]
        matches.sort(key=lambda g: g.updated_at, reverse=True)
        return [
            {
                "id": gen.id,
                "url": gen.url,
                "status": "completed",
                "created_at": gen.created_at.isoformat(),
                "pages_found": len(gen.pages),
            }
            for gen in matches[:limit]
        ]

    async def list_recent(self, limit: int = 10) -> list[dict]:
        """List recent completed generations."""
        completed = [
            gen for gen in self._generations.values()
            if gen.markdown_base is not None
        ]
        completed.sort(key=lambda g: g.updated_at, reverse=True)
        return [
            {
                "id": gen.id,
                "url": gen.url,
                "status": "completed",
                "created_at": gen.created_at.isoformat(),
                "pages_found": len(gen.pages),
            }
            for gen in completed[:limit]
        ]

    def _remove(self, generation_id: str) -> None:
        self._generations.pop(generation_id, None)


_store: GenerationStore | None = None


def init_generation_store(store: GenerationStore) -> None:
    global _store
    _store = store


def get_generation_store() -> GenerationStore:
    if _store is None:
        raise RuntimeError("GenerationStore not initialized")
    return _store

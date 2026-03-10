from abc import ABC, abstractmethod
from datetime import datetime, timezone

from app.models.generation import Generation


class GenerationStore(ABC):
    @abstractmethod
    async def create(
        self, generation_id: str, url: str, client_info: str | None = None, prompts_context: list[str] | None = None
    ) -> Generation: ...

    @abstractmethod
    async def get(self, generation_id: str) -> Generation | None: ...

    @abstractmethod
    async def update(self, generation_id: str, **fields) -> None: ...


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

    def _remove(self, generation_id: str) -> None:
        self._generations.pop(generation_id, None)


# Backward-compat alias
InMemoryGenerationStore = InMemoryGenerationCache


_store: GenerationStore | None = None


def init_generation_store(store: GenerationStore) -> None:
    global _store
    _store = store


def get_generation_store() -> GenerationStore:
    assert _store is not None, "GenerationStore not initialized"
    return _store

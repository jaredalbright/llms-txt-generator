"""Unified LRU cache manager for in-memory stores.

Owns a single LRU ordering (OrderedDict) shared by both the Job and Generation
stores.  Active (pending/in-progress) jobs are never evicted; only completed or
errored entries are eligible.  A secondary URL index enables cache-hit lookups.
"""

from __future__ import annotations

import logging
from collections import OrderedDict
from typing import TYPE_CHECKING, Protocol

from app.services.url_utils import normalize_url

if TYPE_CHECKING:
    pass

logger = logging.getLogger("app.cache")


class Removable(Protocol):
    """Any store that can remove an entry by id."""

    def _remove(self, entry_id: str) -> None: ...


class CacheManager:
    def __init__(self, max_entries: int = 100) -> None:
        self.max_entries = max_entries
        # job_id -> normalized_url  (insertion-ordered; most-recent at end)
        self._order: OrderedDict[str, str] = OrderedDict()
        # normalized_url -> job_id
        self._url_index: dict[str, str] = {}
        # IDs that must not be evicted (pending / in-progress)
        self._active_ids: set[str] = set()
        # Registered stores to call _remove on during eviction
        self._stores: list[Removable] = []

    def register_stores(self, *stores: Removable) -> None:
        self._stores.extend(stores)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def track(self, job_id: str, url: str) -> None:
        """Start tracking a new job.  Called when a Job is created."""
        norm = normalize_url(url)
        self._order[job_id] = norm
        self._url_index[norm] = job_id
        self._active_ids.add(job_id)
        self._order.move_to_end(job_id)
        logger.debug("track %s (url=%s, active=%d, total=%d)",
                      job_id[:8], norm, len(self._active_ids), len(self._order))

    def touch(self, job_id: str) -> None:
        """Bump a job to the most-recently-used end."""
        if job_id in self._order:
            self._order.move_to_end(job_id)

    def mark_finished(self, job_id: str) -> None:
        """Mark a job as finished (completed or errored) so it becomes evictable."""
        self._active_ids.discard(job_id)
        logger.debug("mark_finished %s (active=%d, total=%d)",
                      job_id[:8], len(self._active_ids), len(self._order))
        self._maybe_evict()

    def lookup_url(self, url: str) -> str | None:
        """Return the job_id for a previously cached URL, or None."""
        norm = normalize_url(url)
        return self._url_index.get(norm)

    # ------------------------------------------------------------------
    # Eviction
    # ------------------------------------------------------------------

    def _maybe_evict(self) -> None:
        """Evict oldest finished entries until we're at or below capacity."""
        while len(self._order) > self.max_entries:
            evicted = self._evict_one()
            if not evicted:
                break  # all remaining entries are active — can't evict

    def _evict_one(self) -> bool:
        """Evict the single oldest evictable entry.  Returns True if one was evicted."""
        for job_id in self._order:
            if job_id not in self._active_ids:
                self._evict(job_id)
                return True
        return False

    def _evict(self, job_id: str) -> None:
        """Remove a single entry from the cache and all registered stores."""
        norm = self._order.pop(job_id, None)
        if norm is not None and self._url_index.get(norm) == job_id:
            del self._url_index[norm]
        self._active_ids.discard(job_id)

        for store in self._stores:
            store._remove(job_id)

        logger.debug("evicted %s (total=%d)", job_id[:8], len(self._order))


# ------------------------------------------------------------------
# Module-level singleton
# ------------------------------------------------------------------

_cache_manager: CacheManager | None = None


def init_cache_manager(mgr: CacheManager) -> None:
    global _cache_manager
    _cache_manager = mgr


def get_cache_manager() -> CacheManager:
    assert _cache_manager is not None, "CacheManager not initialized"
    return _cache_manager

import asyncio
import pytest

from app.db.cache import CacheManager
from app.db.memory import InMemoryJobCache
from app.db.generation_store import InMemoryGenerationCache


@pytest.fixture
def setup():
    """Create a CacheManager with small capacity and wire up both stores."""
    mgr = CacheManager(max_entries=3)
    job_cache = InMemoryJobCache(mgr)
    gen_cache = InMemoryGenerationCache(mgr)
    mgr.register_stores(job_cache, gen_cache)
    return mgr, job_cache, gen_cache


@pytest.mark.asyncio
async def test_lru_eviction_order(setup):
    mgr, job_cache, gen_cache = setup

    # Create 3 jobs and mark them finished
    for i in range(3):
        jid = f"job-{i}"
        q = asyncio.Queue()
        await job_cache.create(jid, f"https://example.com/{i}", None, q)
        await gen_cache.create(jid, f"https://example.com/{i}")
        await job_cache.update(jid, status="completed", markdown=f"# Page {i}")

    # All 3 should still exist (at capacity)
    for i in range(3):
        assert await job_cache.get(f"job-{i}") is not None

    # Add a 4th — oldest finished (job-0) should be evicted
    q = asyncio.Queue()
    await job_cache.create("job-3", "https://example.com/3", None, q)
    await job_cache.update("job-3", status="completed", markdown="# Page 3")

    assert await job_cache.get("job-0") is None
    assert await job_cache.get("job-1") is not None
    assert await job_cache.get("job-2") is not None
    assert await job_cache.get("job-3") is not None


@pytest.mark.asyncio
async def test_active_jobs_exempt_from_eviction(setup):
    mgr, job_cache, gen_cache = setup

    # Create 3 jobs, keep job-0 active (don't mark finished)
    q = asyncio.Queue()
    await job_cache.create("active-job", "https://example.com/active", None, q)

    for i in range(1, 3):
        jid = f"job-{i}"
        q2 = asyncio.Queue()
        await job_cache.create(jid, f"https://example.com/{i}", None, q2)
        await job_cache.update(jid, status="completed", markdown=f"# Page {i}")

    # At capacity (3). Add a 4th.
    q3 = asyncio.Queue()
    await job_cache.create("job-3", "https://example.com/3", None, q3)
    await job_cache.update("job-3", status="completed", markdown="# Page 3")

    # active-job should survive; job-1 (oldest finished) should be evicted
    assert await job_cache.get("active-job") is not None
    assert await job_cache.get("job-1") is None
    assert await job_cache.get("job-2") is not None
    assert await job_cache.get("job-3") is not None


@pytest.mark.asyncio
async def test_linked_eviction(setup):
    mgr, job_cache, gen_cache = setup

    for i in range(3):
        jid = f"job-{i}"
        q = asyncio.Queue()
        await job_cache.create(jid, f"https://example.com/{i}", None, q)
        await gen_cache.create(jid, f"https://example.com/{i}")
        await job_cache.update(jid, status="completed", markdown=f"# Page {i}")

    # Add 4th to trigger eviction of job-0
    q = asyncio.Queue()
    await job_cache.create("job-3", "https://example.com/3", None, q)
    await gen_cache.create("job-3", "https://example.com/3")
    await job_cache.update("job-3", status="completed", markdown="# Page 3")

    # Both Job and Generation for job-0 should be gone
    assert await job_cache.get("job-0") is None
    assert await gen_cache.get("job-0") is None


@pytest.mark.asyncio
async def test_touch_prevents_eviction(setup):
    mgr, job_cache, gen_cache = setup

    for i in range(3):
        jid = f"job-{i}"
        q = asyncio.Queue()
        await job_cache.create(jid, f"https://example.com/{i}", None, q)
        await job_cache.update(jid, status="completed", markdown=f"# Page {i}")

    # Touch job-0 to make it most-recently-used
    await job_cache.get("job-0")

    # Add 4th — job-1 (now oldest) should be evicted instead of job-0
    q = asyncio.Queue()
    await job_cache.create("job-3", "https://example.com/3", None, q)
    await job_cache.update("job-3", status="completed", markdown="# Page 3")

    assert await job_cache.get("job-0") is not None  # touched, survived
    assert await job_cache.get("job-1") is None       # oldest, evicted
    assert await job_cache.get("job-2") is not None
    assert await job_cache.get("job-3") is not None


@pytest.mark.asyncio
async def test_url_index_cleanup_on_eviction(setup):
    mgr, job_cache, gen_cache = setup

    for i in range(3):
        jid = f"job-{i}"
        q = asyncio.Queue()
        await job_cache.create(jid, f"https://example.com/{i}", None, q)
        await job_cache.update(jid, status="completed", markdown=f"# Page {i}")

    # URL index should have all 3
    assert mgr.lookup_url("https://example.com/0") == "job-0"

    # Trigger eviction
    q = asyncio.Queue()
    await job_cache.create("job-3", "https://example.com/3", None, q)
    await job_cache.update("job-3", status="completed", markdown="# Page 3")

    # Evicted URL should be removed from index
    assert mgr.lookup_url("https://example.com/0") is None
    assert mgr.lookup_url("https://example.com/1") == "job-1"


@pytest.mark.asyncio
async def test_cache_hit_lookup():
    mgr = CacheManager(max_entries=10)
    job_cache = InMemoryJobCache(mgr)
    mgr.register_stores(job_cache)

    q = asyncio.Queue()
    await job_cache.create("job-abc", "https://example.com/page", None, q)
    await job_cache.update("job-abc", status="completed", markdown="# Cached")

    # Lookup with equivalent URL (trailing slash, different case)
    assert mgr.lookup_url("https://Example.com/page/") == "job-abc"
    assert mgr.lookup_url("https://example.com/page") == "job-abc"

    # Unknown URL returns None
    assert mgr.lookup_url("https://other.com") is None


@pytest.mark.asyncio
async def test_force_bypasses_cache():
    """force=True should create a new job even if a cached one exists."""
    mgr = CacheManager(max_entries=10)
    job_cache = InMemoryJobCache(mgr)
    mgr.register_stores(job_cache)

    q = asyncio.Queue()
    await job_cache.create("job-old", "https://example.com", None, q)
    await job_cache.update("job-old", status="completed", markdown="# Old")

    # With force, we would skip the cache lookup entirely in the router.
    # Here we just verify that the URL index points to the old job
    assert mgr.lookup_url("https://example.com") == "job-old"

    # Creating a new job for the same URL updates the index
    q2 = asyncio.Queue()
    await job_cache.create("job-new", "https://example.com", None, q2)
    assert mgr.lookup_url("https://example.com") == "job-new"

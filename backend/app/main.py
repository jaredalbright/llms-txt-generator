import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from app.routers import generate, validate
from app.config import settings
from app.db import (
    CacheManager, init_cache_manager,
    InMemoryJobCache, init_job_repo,
    InMemoryGenerationCache, init_generation_store,
)

# Configure root logger
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
)
# Quiet down noisy third-party loggers
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("uvicorn.access").setLevel(logging.INFO)

logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting llms.txt Generator API")
    logger.info("  LLM provider: %s (model: %s)", settings.llm_provider, settings.llm_model)
    logger.info("  Mock LLM: %s", settings.mock_llm)
    logger.info("  Max pages: %d, Crawl timeout: %ds", settings.max_pages, settings.crawl_timeout)
    logger.info("  Cache max entries: %d", settings.cache_max_entries)
    yield


app = FastAPI(title="llms.txt Generator API", lifespan=lifespan)

cache_mgr = CacheManager(max_entries=settings.cache_max_entries)
job_cache = InMemoryJobCache(cache_mgr)
gen_cache = InMemoryGenerationCache(cache_mgr)
cache_mgr.register_stores(job_cache, gen_cache)
init_cache_manager(cache_mgr)
init_job_repo(job_cache)
init_generation_store(gen_cache)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(generate.router, prefix="/api")
app.include_router(validate.router, prefix="/api")


@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.debug("→ %s %s", request.method, request.url.path)
    response = await call_next(request)
    logger.debug("← %s %s %d", request.method, request.url.path, response.status_code)
    return response


@app.get("/health")
async def health():
    return {"status": "ok"}

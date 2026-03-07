import logging
import sys

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from app.routers import generate, validate
from app.config import settings

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

app = FastAPI(title="llms.txt Generator API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Lock down to frontend domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(generate.router, prefix="/api")
app.include_router(validate.router, prefix="/api")


@app.on_event("startup")
async def log_startup():
    logger.info("Starting llms.txt Generator API")
    logger.info("  LLM provider: %s (model: %s)", settings.llm_provider, settings.llm_model)
    logger.info("  Mock LLM: %s", settings.mock_llm)
    logger.info("  Max pages: %d, Crawl timeout: %ds", settings.max_pages, settings.crawl_timeout)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.debug("→ %s %s", request.method, request.url.path)
    response = await call_next(request)
    logger.debug("← %s %s %d", request.method, request.url.path, response.status_code)
    return response


@app.get("/health")
async def health():
    return {"status": "ok"}

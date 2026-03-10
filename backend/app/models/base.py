import asyncio
import dataclasses
from pydantic import BaseModel, HttpUrl
from typing import Optional
from enum import Enum


class JobStatus(str, Enum):
    PENDING = "pending"
    CRAWLING = "crawling"
    EXTRACTING_CONTENT = "extracting_content"
    SUMMARIZING = "summarizing"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"


class GenerateRequest(BaseModel):
    url: HttpUrl
    client_info: Optional[str] = None
    prompts_context: Optional[list[str]] = None
    force: bool = False


class GenerateResponse(BaseModel):
    job_id: str
    cached: bool = False
    markdown: Optional[str] = None


class DownloadRequest(BaseModel):
    markdown: str


class ValidateRequest(BaseModel):
    markdown: str


class ValidationIssue(BaseModel):
    line: int
    severity: str  # "error" | "warning"
    message: str


class ValidateResponse(BaseModel):
    valid: bool
    issues: list[ValidationIssue]


class ChildPageContent(BaseModel):
    url: str
    title: str
    markdown_content: str


class PageMeta(BaseModel):
    url: str
    title: str
    description: str
    h1: Optional[str] = None
    uuid: Optional[str] = None
    parent_uuid: Optional[str] = None


@dataclasses.dataclass
class Job:
    id: str
    status: str
    url: str
    client_info: str | None = None
    prompts_context: list[str] | None = None
    pages_found: int = 0
    markdown: str | None = None
    markdown_md: str | None = None
    llms_ctx: str | None = None
    child_pages: list[ChildPageContent] = dataclasses.field(default_factory=list)
    error: str | None = None
    event_queue: asyncio.Queue | None = None

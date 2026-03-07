from pydantic import BaseModel, HttpUrl
from typing import Optional
from enum import Enum


class JobStatus(str, Enum):
    PENDING = "pending"
    CRAWLING = "crawling"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"


class GenerateRequest(BaseModel):
    url: HttpUrl
    client_info: Optional[str] = None


class GenerateResponse(BaseModel):
    job_id: str


class RepromptRequest(BaseModel):
    job_id: str
    instruction: str
    current_markdown: str


class RepromptResponse(BaseModel):
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


class PageMeta(BaseModel):
    url: str
    title: str
    description: str
    h1: Optional[str] = None

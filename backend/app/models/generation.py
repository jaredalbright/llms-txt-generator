import dataclasses
from datetime import datetime, timezone
from typing import Any


@dataclasses.dataclass
class Generation:
    """The artifact being constructed through the pipeline.

    Holds all intermediate and final outputs as the pipeline progresses
    through its DAG nodes. The Job maintains orchestration state (event_queue,
    status); this model holds the actual data being built.
    """

    id: str
    url: str
    client_info: str | None = None

    # Crawl output
    discovered_urls: list[str] = dataclasses.field(default_factory=list)

    # Metadata extraction output (list[PageMeta])
    pages: list = dataclasses.field(default_factory=list)

    # Homepage content as markdown
    homepage_markdown: str | None = None

    # LLM categorization output
    structured_data: dict[str, Any] | None = None

    # Fetched child page content (list[ChildPageContent])
    child_pages: list = dataclasses.field(default_factory=list)

    # Expanded context document
    llms_ctx: str | None = None

    # Final assembled outputs
    markdown_base: str | None = None
    markdown_md: str | None = None

    # Pipeline tracking
    completed_steps: list[str] = dataclasses.field(default_factory=list)
    error: str | None = None
    created_at: datetime = dataclasses.field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = dataclasses.field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

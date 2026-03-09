from abc import ABC, abstractmethod
from app.models import PageMeta
from app.services.progress import StepProgressReporter


class LLMProvider(ABC):
    """
    Abstract base class for LLM providers.
    All providers must implement these methods.
    """

    @abstractmethod
    async def categorize_pages(
        self, site_url: str, pages: list[PageMeta], *, client_info: str | None = None, homepage_markdown: str | None = None, url_metadata: dict | None = None, prompts_context: list[str] | None = None, reporter: StepProgressReporter | None = None
    ) -> dict:
        """
        Given a site URL and list of page metadata, return structured data:
        {
            "site_name": str,
            "description": str,
            "details": str | None,
            "sections": [
                {
                    "name": str,
                    "pages": [{"title": str, "url": str, "description": str}]
                }
            ]
        }
        """
        pass

    @abstractmethod
    async def summarize(
        self, llms_ctx: str, site_url: str, current_structured_data: dict, *, prompts_context: list[str] | None = None, reporter: StepProgressReporter | None = None
    ) -> dict:
        """
        Given the expanded llms-ctx content, the site URL, and the current structured data,
        return improved structured data with better descriptions from actual page content.
        """
        pass

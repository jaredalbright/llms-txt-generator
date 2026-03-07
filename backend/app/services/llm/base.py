from abc import ABC, abstractmethod
from app.models import PageMeta


class LLMProvider(ABC):
    """
    Abstract base class for LLM providers.
    All providers must implement these methods.
    """

    @abstractmethod
    async def categorize_pages(
        self, site_url: str, pages: list[PageMeta], *, client_info: str | None = None
    ) -> dict:
        """
        Given a site URL and list of page metadata, return structured data:
        {
            "site_name": str,
            "summary": str,
            "context": str | None,
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
    async def reprompt(
        self, current_markdown: str, instruction: str
    ) -> str:
        """
        Given the current llms.txt markdown and a user instruction,
        return the modified markdown.
        """
        pass

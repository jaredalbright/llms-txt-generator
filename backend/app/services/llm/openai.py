import json
import logging
from openai import AsyncOpenAI
from app.services.llm.base import LLMProvider
from app.models import PageMeta
from app.config import settings
from app.prompts.categorize import CATEGORIZE_SYSTEM_PROMPT, build_categorize_user_prompt
from app.prompts.reprompt import REPROMPT_SYSTEM_PROMPT, build_reprompt_user_prompt

logger = logging.getLogger("app.llm.openai")


class OpenAIProvider(LLMProvider):
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.llm_model  # e.g., "gpt-4o-mini"
        logger.info("OpenAI provider initialized (model: %s)", self.model)

    async def categorize_pages(self, site_url: str, pages: list[PageMeta], *, client_info: str | None = None) -> dict:
        user_prompt = build_categorize_user_prompt(site_url, pages, client_info=client_info)
        logger.info("Categorizing %d pages for %s (client_info: %s)", len(pages), site_url, "yes" if client_info else "no")
        logger.debug("Prompt length: %d chars", len(user_prompt))

        response = await self.client.chat.completions.create(
            model=self.model,
            max_tokens=4096,
            messages=[
                {"role": "system", "content": CATEGORIZE_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )

        text = response.choices[0].message.content
        logger.debug("Raw LLM response (%d chars): %s", len(text), text[:200])

        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]

        result = json.loads(text.strip())
        logger.info("Categorization complete: %d sections", len(result.get("sections", [])))
        return result

    async def reprompt(self, current_markdown: str, instruction: str) -> str:
        user_prompt = build_reprompt_user_prompt(current_markdown, instruction)
        logger.info("Reprompt: '%s' (%d chars of markdown)", instruction[:80], len(current_markdown))

        response = await self.client.chat.completions.create(
            model=self.model,
            max_tokens=4096,
            messages=[
                {"role": "system", "content": REPROMPT_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )

        result = response.choices[0].message.content.strip()
        logger.info("Reprompt complete: %d chars returned", len(result))
        return result

    async def summarize(self, llms_ctx: str, site_url: str, current_structured_data: dict) -> dict:
        raise NotImplementedError("Summarize not yet implemented for this provider")

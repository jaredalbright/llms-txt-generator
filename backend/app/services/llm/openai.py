import asyncio
import json
import logging
from openai import AsyncOpenAI
from app.services.llm.base import LLMProvider
from app.services.progress import StepProgressReporter
from app.models import PageMeta
from app.config import settings
from app.prompts.categorize import CATEGORIZE_SYSTEM_PROMPT, build_categorize_user_prompt
from app.prompts.reprompt import REPROMPT_SYSTEM_PROMPT, build_reprompt_user_prompt

logger = logging.getLogger("app.llm.openai")

DETAIL_CHAR_INTERVAL = 200
DETAIL_TIME_INTERVAL = 8


class OpenAIProvider(LLMProvider):
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.llm_model  # e.g., "gpt-4o-mini"
        logger.info("OpenAI provider initialized (model: %s)", self.model)

    async def categorize_pages(self, site_url: str, pages: list[PageMeta], *, client_info: str | None = None, homepage_markdown: str | None = None, reporter: StepProgressReporter | None = None) -> dict:
        # OpenAI: always inline homepage content (truncated if too large)
        if homepage_markdown and len(homepage_markdown) > settings.homepage_content_threshold:
            homepage_markdown = homepage_markdown[:settings.homepage_content_threshold] + "\n\n[... truncated ...]"
        user_prompt = build_categorize_user_prompt(site_url, pages, client_info=client_info, homepage_markdown=homepage_markdown)
        logger.info("Categorizing %d pages for %s (client_info: %s)", len(pages), site_url, "yes" if client_info else "no")
        logger.debug("Prompt length: %d chars", len(user_prompt))

        accumulated_text = ""
        last_emitted_len = 0
        last_emit_time = asyncio.get_event_loop().time()

        stream = await self.client.chat.completions.create(
            model=self.model,
            max_tokens=4096,
            stream=True,
            messages=[
                {"role": "system", "content": CATEGORIZE_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )

        async for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta and delta.content:
                accumulated_text += delta.content

                now = asyncio.get_event_loop().time()
                chars_since = len(accumulated_text) - last_emitted_len
                time_since = now - last_emit_time

                if reporter and (chars_since >= DETAIL_CHAR_INTERVAL or time_since >= DETAIL_TIME_INTERVAL):
                    detail_chunk = accumulated_text[last_emitted_len:]
                    await reporter.log(detail_chunk, message="AI is thinking...")
                    last_emitted_len = len(accumulated_text)
                    last_emit_time = now

        # Emit any remaining text
        if reporter and len(accumulated_text) > last_emitted_len:
            detail_chunk = accumulated_text[last_emitted_len:]
            await reporter.log(detail_chunk, message="AI is thinking...")

        text = accumulated_text
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

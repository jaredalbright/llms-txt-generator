import asyncio
import json
import logging
from openai import AsyncOpenAI
from app.services.llm.base import LLMProvider
from app.services.progress import StepProgressReporter
from app.models import PageMeta
from app.config import settings
from app.prompts.categorize import CATEGORIZE_SYSTEM_PROMPT, build_categorize_user_prompt
from app.prompts.summarize import SUMMARIZE_SYSTEM_PROMPT, SUMMARIZE_USER_PROMPT


logger = logging.getLogger("app.llm.openai")

DETAIL_CHAR_INTERVAL = 200
DETAIL_TIME_INTERVAL = 8


def _extract_json(text: str) -> dict:
    """Extract JSON from LLM response text, handling markdown code fences."""
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0]
    elif "```" in text:
        text = text.split("```")[1].split("```")[0]
    return json.loads(text.strip())


class OpenAIProvider(LLMProvider):
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.llm_model  # e.g., "gpt-4o-mini"
        logger.info("OpenAI provider initialized (model: %s)", self.model)

    async def _stream_to_text(
        self,
        *,
        system: str,
        messages: list[dict],
        reporter: StepProgressReporter | None = None,
    ) -> str:
        """Stream an OpenAI API call, emitting detail lines. Returns accumulated text."""
        accumulated_text = ""
        last_emitted_len = 0
        last_emit_time = asyncio.get_event_loop().time()

        stream = await self.client.chat.completions.create(
            model=self.model,
            max_tokens=4096,
            stream=True,
            messages=[
                {"role": "system", "content": system},
                *messages,
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

        return accumulated_text

    async def categorize_pages(
        self,
        site_url: str,
        pages: list[PageMeta],
        *,
        client_info: str | None = None,
        homepage_markdown: str | None = None,
        url_metadata: dict | None = None,
        reporter: StepProgressReporter | None = None,
    ) -> dict:
        # OpenAI: always inline homepage content (truncated if too large)
        if homepage_markdown and len(homepage_markdown) > settings.homepage_content_threshold:
            homepage_markdown = homepage_markdown[:settings.homepage_content_threshold] + "\n\n[... truncated ...]"
        user_prompt = build_categorize_user_prompt(
            site_url, pages,
            client_info=client_info,
            homepage_markdown=homepage_markdown,
            url_metadata=url_metadata,
        )
        logger.info("Categorizing %d pages for %s (client_info: %s)", len(pages), site_url, "yes" if client_info else "no")
        logger.debug("Prompt length: %d chars", len(user_prompt))

        text = await self._stream_to_text(
            system=CATEGORIZE_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
            reporter=reporter,
        )

        logger.debug("Raw LLM response (%d chars): %s", len(text), text[:200])
        result = _extract_json(text)
        logger.info("Categorization complete: %d sections", len(result.get("sections", [])))
        return result

    async def summarize(
        self,
        llms_ctx: str,
        site_url: str,
        current_structured_data: dict,
        *,
        reporter: StepProgressReporter | None = None,
    ) -> dict:
        user_prompt = SUMMARIZE_USER_PROMPT.format(
            site_url=site_url,
            llms_ctx=llms_ctx,
            current_structured_data=json.dumps(current_structured_data, indent=2),
        )

        logger.info("Summarize pass for %s (%d chars context)", site_url, len(llms_ctx))

        text = await self._stream_to_text(
            system=SUMMARIZE_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
            reporter=reporter,
        )

        logger.debug("Summarize response (%d chars): %s", len(text), text[:200])
        result = _extract_json(text)
        logger.info("Summarize complete: %d sections", len(result.get("sections", [])))
        return result

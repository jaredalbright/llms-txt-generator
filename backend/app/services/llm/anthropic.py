import asyncio
import json
import logging
import anthropic
from app.services.llm.base import LLMProvider
from app.services.progress import StepProgressReporter
from app.models import PageMeta
from app.config import settings
from app.prompts.categorize import (
    CATEGORIZE_SYSTEM_PROMPT,
    CATEGORIZE_SYSTEM_PROMPT_WITH_TOOL,
    SEARCH_HOMEPAGE_TOOL,
    build_categorize_user_prompt,
    search_homepage_content,
)
from app.prompts.summarize import SUMMARIZE_SYSTEM_PROMPT, build_summarize_user_prompt


logger = logging.getLogger("app.llm.anthropic")

# Timeout: 5s connect, 5min read (enough for large responses, not infinite)
API_TIMEOUT = anthropic.Timeout(connect=5.0, read=300.0, write=300.0, pool=300.0)

# Emit a detail line every this many accumulated chars
DETAIL_CHAR_INTERVAL = 200
# Or every this many seconds, whichever comes first
DETAIL_TIME_INTERVAL = 8


def _extract_json(text: str) -> dict:
    """Extract JSON from LLM response text, handling markdown code fences."""
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0]
    elif "```" in text:
        text = text.split("```")[1].split("```")[0]
    return json.loads(text.strip())


class AnthropicProvider(LLMProvider):
    def __init__(self):
        self.client = anthropic.AsyncAnthropic(
            api_key=settings.anthropic_api_key,
            timeout=API_TIMEOUT,
            max_retries=2,
        )
        self.model = settings.llm_model
        logger.info("Anthropic provider initialized (model: %s)", self.model)

    async def _stream_to_text(
        self,
        *,
        system: str,
        messages: list,
        tools: list | None = None,
        reporter: StepProgressReporter | None = None,
    ) -> anthropic.types.Message:
        """Stream an Anthropic API call, emitting detail lines with partial AI output.

        Returns the final assembled Message object.
        """
        kwargs = dict(
            model=self.model,
            max_tokens=4096,
            system=system,
            messages=messages,
        )
        if tools:
            kwargs["tools"] = tools

        accumulated_text = ""
        last_emitted_len = 0
        last_emit_time = asyncio.get_event_loop().time()

        async with self.client.messages.stream(**kwargs) as stream:
            async for event in stream:
                if hasattr(event, "type") and event.type == "content_block_delta":
                    if hasattr(event.delta, "text"):
                        accumulated_text += event.delta.text

                        now = asyncio.get_event_loop().time()
                        chars_since = len(accumulated_text) - last_emitted_len
                        time_since = now - last_emit_time

                        if reporter and (chars_since >= DETAIL_CHAR_INTERVAL or time_since >= DETAIL_TIME_INTERVAL):
                            chunk = accumulated_text[last_emitted_len:]
                            await reporter.log(chunk, message="AI is thinking...")
                            last_emitted_len = len(accumulated_text)
                            last_emit_time = now

            # Emit any remaining text
            if reporter and len(accumulated_text) > last_emitted_len:
                chunk = accumulated_text[last_emitted_len:]
                await reporter.log(chunk, message="AI is thinking...")

        return await stream.get_final_message()

    async def categorize_pages(
        self,
        site_url: str,
        pages: list[PageMeta],
        *,
        client_info: str | None = None,
        homepage_markdown: str | None = None,
        url_metadata: dict | None = None,
        prompts_context: list[str] | None = None,
        reporter: StepProgressReporter | None = None,
    ) -> dict:
        use_tool_mode = (
            homepage_markdown is not None
            and len(homepage_markdown) > settings.homepage_content_threshold
        )

        user_prompt = build_categorize_user_prompt(
            site_url, pages,
            client_info=client_info,
            homepage_markdown=homepage_markdown,
            use_tool_mode=use_tool_mode,
            url_metadata=url_metadata,
            prompts_context=prompts_context,
        )
        system_prompt = CATEGORIZE_SYSTEM_PROMPT_WITH_TOOL if use_tool_mode else CATEGORIZE_SYSTEM_PROMPT

        logger.info(
            "Categorizing %d pages for %s (client_info: %s, homepage: %s, tool_mode: %s)",
            len(pages), site_url,
            "yes" if client_info else "no",
            f"{len(homepage_markdown)} chars" if homepage_markdown else "none",
            use_tool_mode,
        )

        if not use_tool_mode:
            response = await self._stream_to_text(
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
                reporter=reporter,
            )
            text = response.content[0].text
            logger.debug("Raw LLM response (%d chars): %s", len(text), text[:200])
            result = _extract_json(text)
            logger.info("Categorization complete: %d sections", len(result.get("sections", [])))
            return result

        # Tool-use mode: homepage is large, let LLM search it
        logger.info("Using tool-use mode for large homepage (%d chars)", len(homepage_markdown))
        messages = [{"role": "user", "content": user_prompt}]

        max_tool_rounds = 5
        for round_num in range(max_tool_rounds):
            response = await self._stream_to_text(
                system=system_prompt,
                messages=messages,
                tools=[SEARCH_HOMEPAGE_TOOL],
                reporter=reporter,
            )

            if response.stop_reason == "end_turn":
                text = "".join(b.text for b in response.content if b.type == "text")
                logger.debug("Final LLM response (%d chars): %s", len(text), text[:200])
                result = _extract_json(text)
                logger.info("Categorization complete after %d tool rounds: %d sections", round_num, len(result.get("sections", [])))
                return result

            # Process tool use — append assistant message and tool results
            messages.append({"role": "assistant", "content": response.content})

            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    query = block.input.get("query", "")
                    logger.info("Tool call round %d: search_homepage('%s')", round_num + 1, query)
                    if reporter:
                        await reporter.log(f"Searching homepage for '{query}'...")
                    search_result = search_homepage_content(homepage_markdown, query)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": search_result,
                    })

            messages.append({"role": "user", "content": tool_results})

        # Exhausted tool rounds — force a final answer without tools
        logger.warning("Exhausted %d tool rounds, requesting final answer", max_tool_rounds)
        messages.append({"role": "user", "content": "Please provide your final JSON categorization now."})
        response = await self._stream_to_text(
            system=system_prompt,
            messages=messages,
            reporter=reporter,
        )
        text = response.content[0].text
        result = _extract_json(text)
        logger.info("Categorization complete (fallback): %d sections", len(result.get("sections", [])))
        return result

    async def summarize(
        self,
        llms_ctx: str,
        site_url: str,
        current_structured_data: dict,
        *,
        prompts_context: list[str] | None = None,
        reporter: StepProgressReporter | None = None,
    ) -> dict:
        import json as _json

        user_prompt = build_summarize_user_prompt(
            site_url=site_url,
            llms_ctx=llms_ctx,
            current_structured_data=_json.dumps(current_structured_data, indent=2),
            prompts_context=prompts_context,
        )

        logger.info("Summarize pass for %s (%d chars context)", site_url, len(llms_ctx))

        response = await self._stream_to_text(
            system=SUMMARIZE_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
            reporter=reporter,
        )

        text = response.content[0].text
        logger.debug("Summarize response (%d chars): %s", len(text), text[:200])
        result = _extract_json(text)
        logger.info("Summarize complete: %d sections", len(result.get("sections", [])))
        return result

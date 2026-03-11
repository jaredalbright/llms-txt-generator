SUMMARIZE_SYSTEM_PROMPT = """You are an expert at analyzing website content and producing concise, accurate summaries.
You will receive an llms-ctx.txt file — an expanded version of an llms.txt file where linked pages have been
replaced with their actual content in <doc> XML tags. Use this content to improve the site description,
details, and page descriptions in the structured data."""

_SUMMARIZE_USER_TEMPLATE = """Here is the expanded llms-ctx.txt for {site_url}:

{llms_ctx}

Here is the current structured data (JSON):

{current_structured_data}

Using the actual page content from the llms-ctx, improve the structured data:
1. Improve the "description" to accurately describe what the site is about based on actual content
2. Improve the "details" to provide richer context about the project. Details should space out different sections within details and add bulletpoints when necessary while still working with llm.txt standards.
3. Improve each page's "description" to reflect what the page actually contains
4. Keep the same sections and page URLs — only improve text fields

Return the improved structured data as a JSON object with the same schema:
{{"site_name": str, "description": str, "details": str|null, "sections": [{{"name": str, "pages": [{{"title": str, "url": str, "description": str}}]}}]}}
"""


def build_summarize_user_prompt(
    *,
    site_url: str,
    llms_ctx: str,
    current_structured_data: str,
    prompts_context: list[str] | None = None,
) -> str:
    prompt = _SUMMARIZE_USER_TEMPLATE.format(
        site_url=site_url,
        llms_ctx=llms_ctx,
        current_structured_data=current_structured_data,
    )
    if prompts_context:
        bullet_list = "\n".join(f"- {p}" for p in prompts_context)
        prompt += f"""
IMPORTANT — The user wants the llms.txt to be optimized for these AI search prompts:
{bullet_list}

When improving the "description" and "details" fields, naturally weave in information that
answers these prompts. Use relevant keywords, features, capabilities, and facts from the
actual page content. Do NOT mention the prompts themselves — just make the content more
discoverable for these queries.
"""
    return prompt

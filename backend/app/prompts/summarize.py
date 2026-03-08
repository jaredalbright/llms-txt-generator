SUMMARIZE_SYSTEM_PROMPT = """You are an expert at analyzing website content and producing concise, accurate summaries.
You will receive an llms-ctx.txt file — an expanded version of an llms.txt file where linked pages have been
replaced with their actual content in <doc> XML tags. Use this content to improve the site summary and
page descriptions in the structured data."""

SUMMARIZE_USER_PROMPT = """Here is the expanded llms-ctx.txt for {site_url}:

{llms_ctx}

Here is the current structured data (JSON):

{current_structured_data}

Using the actual page content from the llms-ctx, improve the structured data:
1. Improve the "summary" to accurately describe what the site is about based on actual content
2. Improve each page's "description" to reflect what the page actually contains
3. Keep the same sections and page URLs — only improve text descriptions

Return the improved structured data as a JSON object with the same schema:
{{"site_name": str, "summary": str, "context": str|null, "sections": [{{"name": str, "pages": [{{"title": str, "url": str, "description": str}}]}}]}}
"""

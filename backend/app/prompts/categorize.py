LLMS_TXT_SPEC = """The llms.txt format follows this structure:
- An H1 with the name of the project or site (this is the only required field)
- A blockquote with a short description of the project, containing key information necessary for understanding the rest of the file
- Zero or more markdown sections (e.g. paragraphs, lists, etc) of any type except headings, containing more detailed information about the project and how to interpret the provided files
- Zero or more markdown sections delimited by H2 headers, containing "file lists" of URLs where further detail is available
- Each "file list" is a markdown list, containing a required markdown hyperlink [name](url), then optionally a : and notes about the file"""

_CATEGORIZE_TASKS = """Your specific tasks:

1. Choose a clean, human-readable site name (not the raw domain). This becomes the H1.
2. Write a one-sentence "description" — a short summary of the project containing key information
   necessary for understanding the rest of the file. This becomes the blockquote.
3. Write "details" — additional context about the project that helps LLMs understand and discover
   the site. This can be any markdown except headings: paragraphs, bullet lists, bold text, etc.
   Include key features, technologies, use cases, or anything that would help an LLM find this
   site when searching. This becomes the body text between the blockquote and the H2 sections.
4. Group the pages into logical sections using H2 names like: Docs, API Reference, Guides,
   Blog, About, Pricing, Legal, Support, etc. Use whatever section names best fit the content.
5. Decide which pages are secondary/supplementary and put them in an "Optional" section.
6. For pages missing descriptions, write a concise one-sentence description."""

_CATEGORIZE_JSON_SCHEMA = """Return ONLY valid JSON with this exact structure (no markdown fences, no explanation):
{{
  "site_name": "Human Readable Site Name",
  "description": "One sentence describing what this site/project is.",
  "details": "Markdown body text (paragraphs, lists, etc. — no headings) providing more detailed information about the project. Include key features, technologies, and concepts to make the site discoverable.",
  "sections": [
    {{
      "name": "Section Name",
      "pages": [
        {{"title": "Page Title", "url": "https://...", "description": "What this page covers."}}
      ]
    }}
  ]
}}"""

_CATEGORIZE_GUIDELINES = """Guidelines:
- "description" is a single sentence for the blockquote. "details" is richer body text — they serve different purposes.
- "details" should include keywords and concepts relevant to the site so LLMs can surface it in search.
- "details" can use any markdown formatting (paragraphs, lists, bold, etc.) except headings.
- Keep section count between 2-6. Don't over-categorize.
- Every page must appear in exactly one section.
- The "Optional" section (if used) should contain genuinely secondary content: legal pages,
  old blog posts, changelog entries, etc. The "Optional" section MUST always be the last section.
- If there are more than 10 pages, you should almost always use an "Optional" section. Move
  lower-value pages there (legal, changelog, careers, terms, privacy, old blog posts, etc.)
  so the main sections stay focused and scannable. Aim for no more than ~10 links in the
  non-Optional sections combined.
- Page descriptions should be concise (under 15 words) and informative.
- Site name should be the product/company name, not the domain."""

_INLINE_INTRO = """You are an expert at analyzing website structure. You will receive
a list of pages from a website (URL, title, description) along with the homepage content
converted to markdown. Your job is to produce structured data that will be used to generate
an llms.txt file."""

_INLINE_HOMEPAGE_INSTRUCTION = """Use the homepage content to better understand the site's purpose, product, and structure.
This will help you write a more accurate description, details, and better categorize the pages."""

_TOOL_INTRO = """You are an expert at analyzing website structure. You will receive
a list of pages from a website (URL, title, description). The homepage content is very large,
so it has NOT been included inline. Instead, you have a tool called `search_homepage` that lets
you search through the homepage content by keyword. Use it to find relevant information about the
site's purpose, products, and structure."""

_TOOL_HOMEPAGE_INSTRUCTION = """Start by using the search_homepage tool to understand what this site is about (try queries like
the site name, "about", "features", "product", etc.). Then use the page list and your findings
to produce the categorization."""

CATEGORIZE_SYSTEM_PROMPT = f"""{_INLINE_INTRO}

{LLMS_TXT_SPEC}

{_CATEGORIZE_TASKS}

{_INLINE_HOMEPAGE_INSTRUCTION}

{_CATEGORIZE_JSON_SCHEMA}

{_CATEGORIZE_GUIDELINES}"""

CATEGORIZE_SYSTEM_PROMPT_WITH_TOOL = f"""{_TOOL_INTRO}

{LLMS_TXT_SPEC}

{_CATEGORIZE_TASKS}

{_TOOL_HOMEPAGE_INSTRUCTION}

{_CATEGORIZE_JSON_SCHEMA}

{_CATEGORIZE_GUIDELINES}"""

SEARCH_HOMEPAGE_TOOL = {
    "name": "search_homepage",
    "description": "Search the homepage markdown content for a keyword or phrase. Returns all lines containing the query (case-insensitive), with surrounding context. Use this to understand the site's purpose, products, features, and structure.",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The keyword or phrase to search for in the homepage content."
            }
        },
        "required": ["query"]
    }
}


def search_homepage_content(homepage_markdown: str, query: str, context_lines: int = 3) -> str:
    """Search homepage markdown for a query, returning matching lines with context."""
    lines = homepage_markdown.split("\n")
    query_lower = query.lower()
    matching_indices = set()

    for i, line in enumerate(lines):
        if query_lower in line.lower():
            for j in range(max(0, i - context_lines), min(len(lines), i + context_lines + 1)):
                matching_indices.add(j)

    if not matching_indices:
        return f"No matches found for '{query}'."

    sorted_indices = sorted(matching_indices)
    result_lines = []
    prev_idx = -2
    for idx in sorted_indices:
        if idx > prev_idx + 1:
            result_lines.append("---")
        result_lines.append(lines[idx])
        prev_idx = idx

    return "\n".join(result_lines)


def build_categorize_user_prompt(
    site_url: str,
    pages: list,
    *,
    client_info: str | None = None,
    user_preferences: str | None = None,
    homepage_markdown: str | None = None,
    use_tool_mode: bool = False,
    url_metadata: dict[str, dict] | None = None,
    prompts_context: list[str] | None = None,
) -> str:
    lines = []
    for p in pages:
        entry = f"- URL: {p.url}\n  Title: {p.title}\n  Description: {p.description or '(none)'}"
        if url_metadata and p.url in url_metadata:
            meta = url_metadata[p.url]
            entry += f"\n  Source: {meta.get('source', 'unknown')} | Depth: {meta.get('depth', '?')} | Inlinks: {meta.get('inlink_count', 0)}"
        lines.append(entry)
    page_list = "\n".join(lines)

    client_section = ""
    if client_info:
        client_section = f"""
Additional context provided by the user about this site:
{client_info}

Use this context to inform your categorization, section naming, and descriptions."""

    preferences_section = ""
    if user_preferences:
        preferences_section = f"""
Output preferences:
{user_preferences}

Apply these preferences to influence tone, focus areas, section emphasis, and description style."""

    prompts_section = ""
    if prompts_context:
        bullet_list = "\n".join(f"- {p}" for p in prompts_context)
        prompts_section = f"""

The user wants the llms.txt to subtly address these AI search prompts. When writing the site
description, details, and page descriptions, try to naturally incorporate information that would
help answer these prompts:
{bullet_list}

Do NOT mention these prompts explicitly. Instead, weave relevant keywords, features, and facts
into the description and details fields so the site is more discoverable for these queries."""

    homepage_section = ""
    if homepage_markdown and not use_tool_mode:
        homepage_section = f"""

Homepage content (converted to markdown):
<homepage>
{homepage_markdown}
</homepage>

Use this homepage content to better understand the site and write more accurate descriptions."""
    elif use_tool_mode:
        homepage_section = """

The homepage content is large. Use the search_homepage tool to look up relevant information before producing your categorization."""

    return f"""Analyze this website and categorize its pages for an llms.txt file.

Website: {site_url}
{client_section}{preferences_section}{prompts_section}{homepage_section}
Pages found:
{page_list}

Return the JSON structure as specified."""

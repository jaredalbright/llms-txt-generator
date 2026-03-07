CATEGORIZE_SYSTEM_PROMPT = """You are an expert at analyzing website structure. You will receive
a list of pages from a website (URL, title, description). Your job is to:

1. Choose a clean, human-readable site name (not the raw domain).
2. Write a one-sentence summary of what the site does.
3. Group the pages into logical sections using H2 names like: Docs, API Reference, Guides,
   Blog, About, Pricing, Legal, Support, etc. Use whatever section names best fit the content.
4. Decide which pages are secondary/supplementary and put them in an "Optional" section.
5. For pages missing descriptions, write a concise one-sentence description.

Return ONLY valid JSON with this exact structure (no markdown fences, no explanation):
{
  "site_name": "Human Readable Site Name",
  "summary": "One sentence describing what this site is.",
  "context": null,
  "sections": [
    {
      "name": "Section Name",
      "pages": [
        {"title": "Page Title", "url": "https://...", "description": "What this page covers."}
      ]
    }
  ]
}

Guidelines:
- Keep section count between 2-6. Don't over-categorize.
- Every page must appear in exactly one section.
- The "Optional" section (if used) should contain genuinely secondary content: legal pages,
  old blog posts, changelog entries, etc.
- Descriptions should be concise (under 15 words) and informative.
- Site name should be the product/company name, not the domain."""


def build_categorize_user_prompt(site_url: str, pages: list, *, client_info: str | None = None) -> str:
    page_list = "\n".join(
        f"- URL: {p.url}\n  Title: {p.title}\n  Description: {p.description or '(none)'}"
        for p in pages
    )

    client_section = ""
    if client_info:
        client_section = f"""
Additional context provided by the user about this site:
{client_info}

Use this context to inform your categorization, section naming, and descriptions."""

    return f"""Analyze this website and categorize its pages for an llms.txt file.

Website: {site_url}
{client_section}
Pages found:
{page_list}

Return the JSON structure as specified."""

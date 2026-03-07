from typing import Any


def assemble_markdown(structured_data: dict[str, Any]) -> str:
    """
    Takes the structured JSON from the LLM and builds a spec-compliant llms.txt string.

    Expected structured_data format:
    {
        "site_name": "Example Corp",
        "summary": "A platform for doing X.",
        "context": "Optional additional context paragraph.",   # optional
        "sections": [
            {
                "name": "Docs",
                "pages": [
                    {"title": "Getting Started", "url": "https://...", "description": "How to..."},
                ]
            },
            {
                "name": "Optional",
                "pages": [...]
            }
        ]
    }
    """
    lines: list[str] = []

    # H1 — required
    lines.append(f"# {structured_data['site_name']}")
    lines.append("")

    # Blockquote summary
    if structured_data.get("summary"):
        lines.append(f"> {structured_data['summary']}")
        lines.append("")

    # Optional context paragraphs
    if structured_data.get("context"):
        lines.append(structured_data["context"])
        lines.append("")

    # H2 sections with link lists
    for section in structured_data.get("sections", []):
        lines.append(f"## {section['name']}")
        lines.append("")
        for page in section.get("pages", []):
            title = page.get("title", page["url"])
            url = page["url"]
            desc = page.get("description", "")
            if desc:
                lines.append(f"- [{title}]({url}): {desc}")
            else:
                lines.append(f"- [{title}]({url})")
        lines.append("")

    return "\n".join(lines).strip() + "\n"

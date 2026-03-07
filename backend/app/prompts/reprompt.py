REPROMPT_SYSTEM_PROMPT = """You are editing an llms.txt file based on user instructions.
You will receive the current llms.txt Markdown and an instruction from the user.
Apply the instruction and return the complete, modified llms.txt Markdown.

Rules:
- Maintain valid llms.txt format: H1, blockquote, optional body text, H2 sections with link lists.
- Only change what the instruction asks for. Don't reorganize everything.
- Return ONLY the Markdown content. No explanation, no code fences."""


def build_reprompt_user_prompt(current_markdown: str, instruction: str) -> str:
    return f"""Current llms.txt:

{current_markdown}

---

User instruction: {instruction}

Return the updated llms.txt Markdown."""

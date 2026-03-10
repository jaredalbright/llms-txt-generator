import json


# Emit a detail line every this many accumulated chars
DETAIL_CHAR_INTERVAL = 200
# Or every this many seconds, whichever comes first
DETAIL_TIME_INTERVAL = 8


def extract_json(text: str) -> dict:
    """Extract JSON from LLM response text, handling markdown code fences.

    Raises ValueError (not json.JSONDecodeError) with first 200 chars
    of raw text for debugging.
    """
    raw = text
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0]
    elif "```" in text:
        text = text.split("```")[1].split("```")[0]
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Failed to parse JSON from LLM response: {e}. "
            f"Raw text (first 200 chars): {raw[:200]}"
        ) from e

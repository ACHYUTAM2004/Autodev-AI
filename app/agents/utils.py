from typing import Any
import json

def extract_text_from_response(response: Any) -> str:
    return normalize_llm_output(response)


def extract_token_usage(response: Any) -> int:
    """
    Safely extract token usage across LLM providers.
    Supports OpenAI, Gemini, and future providers.
    """

    # OpenAI-style (response.usage.total_tokens)
    if hasattr(response, "usage") and response.usage:
        return getattr(response.usage, "total_tokens", 0)

    # Gemini-style (response.response_metadata)
    metadata = getattr(response, "response_metadata", None)
    if isinstance(metadata, dict):
        usage = metadata.get("usage", {})
        if isinstance(usage, dict):
            return (
                usage.get("total_tokens")
                or usage.get("token_count")
                or 0
            )

    # Safe fallback
    return 0

def normalize_llm_output(output: Any) -> str:
    """
    Normalize LLM output into a clean JSON string.
    Strips markdown code fences and wrappers.
    """

    # AIMessage or similar
    if hasattr(output, "content"):
        output = output.content

    # Gemini often returns list
    if isinstance(output, list):
        if len(output) == 1:
            output = output[0]
        else:
            return json.dumps(output)

    # Dict → JSON
    if isinstance(output, dict):
        return json.dumps(output)

    # String cleanup
    text = str(output).strip()

    # 🔥 STRIP MARKDOWN CODE FENCES (THIS WAS MISSING)
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()

    return text


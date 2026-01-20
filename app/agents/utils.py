from typing import Any


def extract_text_from_response(response: Any) -> str:
    """
    Normalizes LLM responses across providers (Gemini, OpenAI, etc.)
    and always returns a clean string.
    """
    content = response.content

    if isinstance(content, list):
        texts = []
        for part in content:
            if isinstance(part, str):
                texts.append(part)
            elif isinstance(part, dict) and "text" in part:
                texts.append(part["text"])
        return "".join(texts).strip()

    return str(content).strip()

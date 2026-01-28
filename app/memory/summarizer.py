from typing import List, Dict


def summarize_memories(memories: List[Dict], max_items: int = 5) -> str:
    """
    Convert structured memory into a short advisory text block.
    """
    if not memories:
        return "No relevant past experience."

    recent = memories[-max_items:]

    lines = []
    for m in recent:
        payload = m.get("payload", {})
        summary = ", ".join(f"{k}: {v}" for k, v in payload.items())
        lines.append(f"- {m['type']}: {summary}")

    return "\n".join(lines)

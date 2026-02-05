from app.memory.storage_memory import update_memory_usage


def summarize_memories(memories: list[dict]) -> str:
    if not memories:
        return "None"

    for m in memories:
        update_memory_usage(m["id"])

    lines = []
    for m in memories:
        lines.append(
            f"- ({m['type']}, score={m['effective_score']}) {m['payload']}"
        )

    return "\n".join(lines)

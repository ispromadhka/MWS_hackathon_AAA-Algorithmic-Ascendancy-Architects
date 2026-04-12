"""Translator Agent — переводит русский промпт на английский для лучшей генерации."""

TRANSLATE_PROMPT = "Translate this Lua coding task from Russian to English. Keep all technical terms (wf.vars, function names, field names) unchanged. Return ONLY the English translation, nothing else."


def _has_cyrillic(text: str) -> bool:
    return any('\u0400' <= c <= '\u04FF' for c in text)


def node_translator(state: dict, llm) -> dict:
    """Переводит русский промпт на английский. Пропускает английские."""
    task = state["task"]

    if not _has_cyrillic(task):
        return state  # Already English

    print(f"\n🌐 [TRANSLATOR] Translating Russian → English...")
    translated = llm.generate(TRANSLATE_PROMPT, task, temperature=0.0, max_tokens=256)

    # Clean up: remove quotes, markdown
    translated = translated.strip().strip('"').strip("'")
    if translated.startswith("```"):
        translated = translated.split("\n", 1)[-1].rsplit("```", 1)[0]

    print(f"    Original: {task[:80]}...")
    print(f"    Translated: {translated[:80]}...")

    return {
        **state,
        "original_task": task,
        "task": translated,
    }

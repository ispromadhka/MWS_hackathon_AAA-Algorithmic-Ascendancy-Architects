"""Clarifier Agent — задаёт уточняющие вопросы для неоднозначных запросов."""

CLARIFY_PROMPT = """You are an AI assistant that helps users write Lua code for MWS Octapi LowCode platform.
The user's request is too vague or ambiguous to generate quality code.

Generate ONE short clarifying question in the SAME language as the user's request.
Focus on: what data structure is expected (wf.vars fields), what the output should be, or what edge cases to handle.

Return ONLY the question, nothing else."""


def _is_ambiguous(task: str) -> bool:
    """Проверяет, нужно ли уточнение."""
    words = task.split()
    # Too short
    if len(words) < 5:
        return True
    # No specific context markers
    has_context = any(kw in task.lower() for kw in (
        "wf.vars", "wf.init", "массив", "array", "таблиц", "table",
        "строк", "string", "число", "number", "функци", "function",
        "return", "фильтр", "filter", "сортир", "sort", "преобраз",
        "convert", "получи", "get", "верни", "увеличь", "increment",
    ))
    if not has_context and len(words) < 10:
        return True
    return False


def node_clarifier(state: dict, llm) -> dict:
    """Проверяет нужно ли уточнение. Если да — генерирует вопрос."""
    task = state.get("original_task", state["task"])

    if not _is_ambiguous(task):
        return {**state, "status": "CLEAR"}

    print(f"\n❓ [CLARIFIER] Request is ambiguous, generating question...")
    question = llm.generate(CLARIFY_PROMPT, f"User request: {task}", temperature=0.3, max_tokens=128)
    question = question.strip().strip('"')
    print(f"    Question: {question}")

    return {
        **state,
        "status": "NEEDS_CLARIFICATION",
        "clarification_question": question,
    }

"""Tester Agent — генерирует тесты или использует заготовленные из RAG."""

TESTER_SYSTEM_PROMPT = """You are an expert Lua test engineer. Write precise, fair, O(1) tests.

CRITICAL RULES:
1. Use the provided test framework: test_assert(condition, message) and test_assert_eq(got, expected, message)
2. Do NOT call test_summary() — it is called automatically
3. ONLY test what the task EXPLICITLY asks for. Do NOT invent extra requirements.
   - If the task says "search sorted array" — test searching, NOT duplicate handling unless specified
   - If the task says "reverse a string" — test reversing, NOT Unicode unless specified
4. If prewritten tests from the knowledge base are provided, USE THEM as-is, only adjusting function names
5. Return ONLY the test code — no markdown, no explanations
6. Tests should call the functions defined in the user's code
7. Write exactly 3-5 test cases: 1 typical, 1 edge (empty/nil), 1 boundary
8. NEVER test implementation details — only test the contract (input → output)
9. Keep tests SIMPLE. If a test requires complex setup, it's testing too much.
10. On retry: if previous tests PASSED on some cases but FAILED on others, keep the passing tests and only fix/remove the failing ones. Do NOT add harder tests on retry.

O(1) TESTING RULES — all tests MUST be constant time and memory:
- All test inputs must have CONSTANT SIZE: lists <= 5 elements, strings <= 20 chars
- No loops in test assertions
- Each individual test must complete in under 10ms
- Prefer PROPERTY-BASED tests where possible:
  * Inverse: decode(encode(x)) == x
  * Idempotency: f(f(x)) == f(x)
  * Invariant: #sort(t) == #t
  * Bounds: result >= 0
  * Round-trip: parse(serialize(data)) == data

Output: Pure Lua test code only. No markdown fences."""


def node_tester(state: dict, llm, rag_context: str = "") -> dict:
    """Генерирует тесты для Lua-кода. Предпочитает заготовленные из RAG."""
    code = state["draft_code"]
    task = state["task"]

    # Проверяем, есть ли готовые тесты в RAG контексте
    prewritten_tests = _extract_prewritten_tests(rag_context or state.get("rag_context", ""))

    if prewritten_tests:
        # Адаптируем готовые тесты под текущий код
        user_prompt = (
            f"Here is the Lua code to test:\n```lua\n{code}\n```\n\n"
            f"Task: {task}\n\n"
            f"Here are prewritten test templates:\n```lua\n{prewritten_tests}\n```\n\n"
            f"Adapt these test templates to work with the code above. "
            f"Keep the test logic but adjust function names and arguments to match the code. "
            f"Add 1-2 more edge case tests if needed."
        )
    else:
        user_prompt = (
            f"Here is the Lua code to test:\n```lua\n{code}\n```\n\n"
            f"Task: {task}\n\n"
            f"Write comprehensive tests using test_assert(condition, msg) and test_assert_eq(got, expected, msg)."
        )

    # Если предыдущие тесты упали — включаем контекст
    if state.get("sandbox_result") and "FAIL" in state.get("sandbox_result", ""):
        user_prompt += (
            f"\n\nPrevious test run output:\n{state['sandbox_result']}\n\n"
            f"Previous tests:\n```lua\n{state.get('tests_code', '')}\n```\n\n"
            f"Fix or improve the tests based on the error output."
        )

    tests = llm.generate(TESTER_SYSTEM_PROMPT, user_prompt)
    tests = _strip_code_fences(tests)

    return {
        **state,
        "tests_code": tests,
        "status": "TESTS_GENERATED",
    }


def _extract_prewritten_tests(rag_context: str) -> str:
    """Извлекает секцию Tests из RAG контекста."""
    if not rag_context:
        return ""

    tests_parts = []
    in_tests = False
    lines = rag_context.split("\n")

    for line in lines:
        if line.strip().startswith("Tests:"):
            in_tests = True
            continue
        if in_tests:
            if line.strip().startswith("---") or line.strip().startswith("Task type:"):
                in_tests = False
                continue
            # Убираем markdown fences
            if line.strip() in ("```lua", "```"):
                continue
            tests_parts.append(line)

    return "\n".join(tests_parts).strip()


def _strip_code_fences(code: str) -> str:
    lines = code.strip().split("\n")
    if lines and lines[0].strip().startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines)

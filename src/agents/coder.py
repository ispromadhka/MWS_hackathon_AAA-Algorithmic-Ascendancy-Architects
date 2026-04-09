"""Coder Agent — генерирует Lua код на основе плана и контекста RAG."""

CODER_SYSTEM_PROMPT = """You are a Lua game/systems developer. Write IDIOMATIC Lua code. COPY the provided examples closely.

RULES:
1. COPY the RAG example structure closely — do not reinvent patterns
2. Return ONLY Lua code — no markdown, no explanations
3. If helpers exist (getNearestObject, moveTo, etc.) — call them directly, NEVER redefine as stubs
4. On retry: make MINIMAL fix based on the error, do not rewrite everything

PYTHON → LUA TRANSLATION (you MUST follow this):
  WRONG: __init__(self)         → CORRECT: function M.new() local self = setmetatable({}, M) ... return self end
  WRONG: def method(self, x)    → CORRECT: function M:method(x)  (colon auto-passes self)
  WRONG: ngx.sleep(n)           → CORRECT: coroutine.yield()  (for games/simulation)
  WRONG: ngx.say(x)             → CORRECT: print(x)  (unless task is nginx-specific)
  WRONG: time.sleep / wait      → CORRECT: accumulate dt, check elapsed >= timeout
  WRONG: self.update(0)         → CORRECT: never recurse update(); let the game loop call it
  WRONG: handle_idle            → CORRECT: handleIdle  (camelCase, not snake_case)
  WRONG: MyClass.state = 1      → CORRECT: set state in .new(), not on the class table

LUA ESSENTIALS:
- local M = {} ; M.__index = M ; ... ; return M
- 1-based indexing. Last element: t[#t]
- Patterns: %d %s %a %w (not \\d \\w). Non-greedy: '-' (not '?')
- No table.remove() in forward loop
- return at module level = LAST statement

COROUTINE PATTERN (for tasks with dt/timeout):
- Coroutine yields each frame: while not done do coroutine.yield() end
- update(dt) accumulates self.elapsed, checks timeout OUTSIDE coroutine
- On timeout: set coroutine to nil, log error, move to next task

Output: Pure Lua code only."""


# Temperature escalation: higher temp on retries to escape local minima
def _get_coder_temperature(state: dict) -> float:
    iterations = state.get("iterations", 0)
    slow = state.get("slow_iterations", 0)
    if slow > 0:
        return 0.5  # Slow loop — more exploration
    if iterations > 0:
        return 0.4  # Fast loop retry — moderate exploration
    return 0.2  # First attempt — deterministic


def _compress_error_context(sandbox_result: str, max_lines: int = 15) -> str:
    """Сжимает error output — оставляет только ошибки и ближайший контекст."""
    # Structural errors like <eof> need full context — don't compress
    if "<eof>" in sandbox_result or "expected near" in sandbox_result:
        return sandbox_result[:2000]

    lines = sandbox_result.strip().split("\n")
    if len(lines) <= max_lines:
        return sandbox_result
    important = []
    for line in lines:
        if any(kw in line for kw in ("[FAIL]", "error", "Error", "attempt to", "stack traceback", "INSTRUCTION_LIMIT", "MEMORY_LIMIT")):
            important.append(line)
    important.extend(lines[-5:])
    return "\n".join(important[:max_lines])


def node_coder(state: dict, llm) -> dict:
    """Генерирует Lua-код на основе плана и RAG контекста."""
    plan = state["memory_md"]
    task = state["task"]
    rag_context = state.get("rag_context", "")

    user_prompt = f"Task: {task}\n\nArchitecture Plan:\n{plan}"

    if rag_context:
        user_prompt += f"\n\nRelevant code example from knowledge base:\n{rag_context}"

    # Experience bank hints
    hints = state.get("experience_hints", "")
    if hints:
        user_prompt += f"\n\nLessons from previous tasks:\n{hints}"

    # Если это повторная генерация после ошибки — включаем сжатый фидбек
    if state.get("sandbox_result") and state.get("status") in ("NEED_FIX", "NEED_NEW_PLAN"):
        compressed_error = _compress_error_context(state["sandbox_result"])
        user_prompt += (
            f"\n\nYour previous code had errors:\n{compressed_error}\n\n"
            f"Fix the errors and return the COMPLETE corrected code."
        )

    temperature = _get_coder_temperature(state)
    code = llm.generate(CODER_SYSTEM_PROMPT, user_prompt, temperature=temperature)

    # Убираем markdown fences если модель всё-таки их добавила
    code = _strip_code_fences(code)

    return {
        **state,
        "draft_code": code,
        "status": "CODE_GENERATED",
    }


def _strip_code_fences(code: str) -> str:
    """Убирает ```lua ... ``` обёртку если есть."""
    lines = code.strip().split("\n")
    if lines and lines[0].strip().startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines)

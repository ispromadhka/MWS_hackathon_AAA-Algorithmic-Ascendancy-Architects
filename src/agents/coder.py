"""Coder Agent — генерирует Lua код на основе плана и контекста RAG."""

CODER_SYSTEM_PROMPT = """You are an expert Lua programmer. Write the SIMPLEST correct code that solves the task.

Rules:
1. Follow the architecture plan exactly
2. Return ONLY the Lua code — no explanations, no markdown, no comments outside the code
3. The code must be a COMPLETE, self-contained Lua script
4. All functions must be defined before they are called
5. If examples from the knowledge base are provided, COPY their patterns closely — do not reinvent
6. KEEP IT SIMPLE. Prefer straightforward loops over clever tricks.
7. Handle ONLY the edge cases explicitly mentioned in the task. Do not over-engineer.
8. On retry with errors: read the error carefully, make the MINIMAL change to fix it. Do not rewrite everything.

CRITICAL Lua rules — violating these causes instant failure:
- Lua uses 1-based indexing. Arrays start at index 1, NOT 0. Last element is t[#t].
- ALWAYS declare variables with 'local'. Start with 'local MyModule = {}' and end with 'return MyModule'.
- Use Lua patterns, NOT regex: %d (not \\d), %s (not \\s), %a (not \\w). Non-greedy is '-' (not '?'). No alternation '|'.
- Never table.remove() in a forward for loop — iterate backwards.
- Build strings with table.insert() + table.concat(), NOT '..' in loops.
- nil and false are BOTH falsy but NOT the same. Use 'x == nil' for existence checks.
- Use math.floor() for integer division.
- 'return' at module level MUST be the LAST statement.
- nginx/OpenResty: code is a HANDLER (not standalone). Use ngx.say(), ngx.req.get_headers(), ngx.exit(). No io/print.
- For game/simulation/Roblox tasks: NEVER use ngx.* APIs. Use print() for output, os.time() or dt accumulation for timing. Use coroutine.yield() to return control each frame — NEVER ngx.sleep() or busy-wait loops.
- For coroutine tasks with dt: accumulate time via self.elapsed = self.elapsed + dt in update(). Check timeout OUTSIDE the coroutine. The coroutine yields each frame, update resumes it. NEVER call self:update() recursively inside a coroutine.

LUA OOP RULES — YOU ARE NOT WRITING PYTHON:
- NEVER use __init__. Lua has NO __init__. Use a .new() constructor instead.
- Constructor pattern: function MyClass.new() local self = setmetatable({}, MyClass) ... return self end
- ALWAYS set MyClass.__index = MyClass right after creating the table.
- Define methods with COLON syntax: function MyClass:methodName() ... end
- The colon auto-passes 'self'. Do NOT write function MyClass.method(self) — use colon.
- NEVER use class, def, self as first arg — these are Python. In Lua: function, local function, and colon syntax.
- Use camelCase for methods (handleIdle, not handle_idle). snake_case is Python style.
- If task says "assume helper functions exist" (like getNearestObject, moveTo): DO NOT redefine them as empty stubs. Just call them directly.

Output: Pure Lua code only. No markdown fences. No commentary."""


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

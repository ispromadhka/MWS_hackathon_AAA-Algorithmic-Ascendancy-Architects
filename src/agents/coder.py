"""Coder Agent — генерирует Lua код на основе плана и контекста RAG."""

CODER_SYSTEM_PROMPT = """You are a Lua developer for MWS Octapi LowCode platform. Generate ONLY pure Lua code.

PLATFORM RULES (MWS Octapi):
- All workflow variables are in wf.vars (e.g. wf.vars.emails, wf.vars.try_count_n)
- Init variables (from workflow start) are in wf.initVariables (e.g. wf.initVariables.recallTime)
- To create a new array: _utils.array.new()
- To mark existing table as array: _utils.array.markAsArray(arr)
- Code is embedded in JSON as: lua{...}lua  — but you output ONLY the Lua inside, no wrapper
- Always use 'return' to return the result value
- Access nested data with dot notation: wf.vars.json.IDOC.ZCDF_HEAD.DATUM
- Use Lua 5.5 syntax: if/then/else/end, for/do/end, while/do/end

LUA ESSENTIALS:
- 1-based indexing. Last element: t[#t]
- String patterns: %d %s %a %w (NOT regex \\d \\w). Non-greedy: '-'
- string.sub(str, start, finish) for substring extraction
- string.format('%s-%s-%sT%s:%s:%s', ...) for formatting
- tonumber(x) to convert string to number
- type(x) returns "string", "number", "table", "boolean", "nil"
- pairs(t) iterates all keys, ipairs(t) iterates array indices
- table.insert(t, val) to append, table.remove(t, i) to remove by index
- Setting field to nil removes it: t[key] = nil
- Comparing with nil: x ~= nil (not x != nil)

COMMON PATTERNS:
- Last element of array: return wf.vars.arr[#wf.vars.arr]
- Increment counter: return wf.vars.counter + 1
- Filter array: loop with ipairs, check condition, table.insert into result
- Clean fields: loop with pairs, set unwanted keys to nil
- Date parsing: use string.sub to extract parts, string.format to build ISO 8601

COPY the RAG examples closely. Output ONLY Lua code, no markdown."""


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

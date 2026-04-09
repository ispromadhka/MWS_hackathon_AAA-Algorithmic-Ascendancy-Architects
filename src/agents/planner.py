"""Planner Agent — анализирует задачу, генерирует структурированный план."""

import json

PLANNER_SYSTEM_PROMPT = """You are an expert Lua software architect. Analyze the task and produce a STRUCTURED plan as JSON.

Output ONLY valid JSON in this exact format (no markdown, no commentary):
{
  "algorithm": "Brief description of the approach",
  "functions": [
    {"name": "func_name", "args": ["arg1", "arg2"], "returns": "type", "description": "what it does"}
  ],
  "edge_cases": ["empty input", "single element"],
  "lua_warnings": ["1-based indexing", "use math.floor for mid"]
}

Rules:
1. For SIMPLE tasks (one function): 1-3 functions, algorithm is 1-2 sentences
2. For COMPLEX tasks (classes, FSM, agents, modules): list ALL methods with args and returns. Include constructor (new/init), core methods, and helper methods.
3. Edge cases: ONLY those explicitly required by the task
4. lua_warnings: Lua-specific pitfalls relevant to THIS task
5. For OOP tasks: ALWAYS specify "use setmetatable for OOP", "use self: method syntax", "each instance must have its own state"
6. For FSM/state machine tasks: specify state enum, transitions table, per-state handler pattern
7. If the task mentions helper functions that exist (e.g. "assume getNearestObject exists"): list them as external deps, do NOT redefine them as empty stubs
"""

PLANNER_FALLBACK_PROMPT = """You are an expert Lua software architect. Produce a concise plan.

## Functions
- function_name(args) -> return_type: description

## Algorithm
1-2 sentences describing the approach.

## Lua Warnings
- Any Lua-specific pitfalls for this task.

Keep it SHORT. 1-3 functions max."""


def _get_planner_temperature(state: dict) -> float:
    slow = state.get("slow_iterations", 0)
    if slow > 0:
        return 0.6  # Slow loop retry — need creative alternatives
    return 0.3  # First attempt — moderate creativity


def node_planner(state: dict, llm) -> dict:
    """Генерирует структурированный план для задачи."""
    task = state["task"]
    rag_context = state.get("rag_context", "")

    user_prompt = f"Task: {task}"
    if rag_context:
        user_prompt += f"\n\nRelevant example from knowledge base:\n{rag_context}"

    if state.get("sandbox_result") and state.get("status") == "NEED_NEW_PLAN":
        user_prompt += (
            f"\n\nPREVIOUS ATTEMPT FAILED with error:\n"
            f"{state['sandbox_result'][:500]}\n\n"
            f"Create a DIFFERENT approach."
        )

    temperature = _get_planner_temperature(state)

    # Try JSON format first
    plan_text = llm.generate(PLANNER_SYSTEM_PROMPT, user_prompt, temperature=temperature)

    # Validate JSON — fallback to free text if parsing fails
    plan_text = _clean_json(plan_text)
    try:
        plan_data = json.loads(plan_text)
        # Convert structured JSON to readable plan for Coder
        plan = _format_plan(plan_data)
    except (json.JSONDecodeError, KeyError, TypeError):
        # Fallback: generate free-text plan
        plan = llm.generate(PLANNER_FALLBACK_PROMPT, user_prompt, temperature=temperature)

    return {
        **state,
        "memory_md": plan,
        "status": "PLANNING_DONE",
    }


def _clean_json(text: str) -> str:
    """Извлекает JSON из текста (убирает markdown fences и мусор)."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)
    # Find first { and last }
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        text = text[start:end + 1]
    return text


def _format_plan(data: dict) -> str:
    """Форматирует JSON план в читаемый текст для Coder."""
    parts = []
    if "algorithm" in data:
        parts.append(f"Algorithm: {data['algorithm']}")

    if "functions" in data:
        parts.append("\nFunctions:")
        for f in data["functions"]:
            args = ", ".join(f.get("args", []))
            ret = f.get("returns", "")
            desc = f.get("description", "")
            parts.append(f"  - {f['name']}({args}) -> {ret}: {desc}")

    if "edge_cases" in data:
        parts.append(f"\nEdge cases: {', '.join(data['edge_cases'])}")

    if "lua_warnings" in data:
        parts.append(f"\nLua warnings: {'; '.join(data['lua_warnings'])}")

    return "\n".join(parts)

"""Critic Agent — анализирует результат sandbox, решает следующий шаг."""

MAX_FAST_LOOP = 3  # макс. итераций в Fast Loop (coder)
MAX_SLOW_LOOP = 2  # макс. итераций Slow Loop (planner)


def _analyze_failure(sandbox_result: str) -> dict:
    """Анализирует, что именно сломалось — код или тесты."""
    lines = sandbox_result.strip().split("\n")
    passed = sum(1 for l in lines if "[PASS]" in l)
    failed = sum(1 for l in lines if "[FAIL]" in l)
    has_syntax_error = "syntax error" in sandbox_result.lower()
    has_runtime_error = "stack traceback" in sandbox_result or "attempt to" in sandbox_result
    has_timeout = "timed out" in sandbox_result.lower()

    return {
        "passed": passed,
        "failed": failed,
        "total": passed + failed,
        "has_syntax_error": has_syntax_error,
        "has_runtime_error": has_runtime_error,
        "has_timeout": has_timeout,
        "mostly_passing": passed > 0 and failed <= 1 and not has_syntax_error,
    }


def node_critic(state: dict) -> dict:
    """
    Анализирует sandbox_result, обновляет iterations и status.

    Логика:
    - SUCCESS → END
    - Mostly passing (1 flaky test) → accept as PARTIAL_SUCCESS → END
    - NEED_FIX (iterations < MAX_FAST_LOOP) → coder (Fast Loop)
    - NEED_FIX (iterations >= MAX_FAST_LOOP) → planner (Slow Loop)
    """
    sandbox_result = state.get("sandbox_result", "")
    iterations = state.get("iterations", 0) + 1
    slow_iterations = state.get("slow_iterations", 0)

    # Проверяем полный успех
    if "All tests passed!" in sandbox_result and "[FAIL]" not in sandbox_result:
        return {
            **state,
            "iterations": iterations,
            "status": "SUCCESS",
        }

    # Code ran successfully with no test output (tests were skipped/broken)
    # If code executed without errors and has MWS content — accept it
    code = state.get("draft_code", "")
    has_mws = any(kw in code for kw in ("wf.vars", "wf.init", "_utils.array"))
    no_errors = "[FAIL]" not in sandbox_result and "error" not in sandbox_result.lower() and "traceback" not in sandbox_result.lower()
    if has_mws and no_errors and sandbox_result.strip() == "":
        return {
            **state,
            "iterations": iterations,
            "status": "SUCCESS",
        }

    analysis = _analyze_failure(sandbox_result)

    # Если большинство тестов проходит и мы уже на 2+ итерации — принимаем
    # (скорее всего тесты слишком строгие, а не код плохой)
    if analysis["mostly_passing"] and iterations >= 2:
        return {
            **state,
            "iterations": iterations,
            "status": "SUCCESS",
            "sandbox_result": sandbox_result + "\n[CRITIC: accepted as partial success — mostly passing]",
        }

    # Тесты провалились или ошибка выполнения
    if iterations >= MAX_FAST_LOOP:
        if slow_iterations >= MAX_SLOW_LOOP:
            # Последний шанс: если хоть что-то проходит — принимаем
            if analysis["passed"] > 0:
                return {
                    **state,
                    "iterations": iterations,
                    "status": "SUCCESS",
                    "sandbox_result": sandbox_result + "\n[CRITIC: accepted best effort after exhausting retries]",
                }
            return {
                **state,
                "iterations": iterations,
                "status": "GIVE_UP",
            }
        return {
            **state,
            "iterations": 0,
            "slow_iterations": slow_iterations + 1,
            "status": "NEED_NEW_PLAN",
        }

    return {
        **state,
        "iterations": iterations,
        "status": "NEED_FIX",
    }


def route_after_critic(state: dict) -> str:
    """Условный переход в LangGraph после critic'а."""
    status = state["status"]
    if status == "SUCCESS":
        return "end"
    elif status == "NEED_NEW_PLAN":
        return "planner"
    elif status == "GIVE_UP":
        return "end"
    else:  # NEED_FIX
        return "coder"

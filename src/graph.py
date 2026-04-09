"""LangGraph — сборка графа агентов с условными переходами."""

import time
from typing import TypedDict
from langgraph.graph import StateGraph, END

from src.llm_engine import LLMEngine
from src.rag_engine import RAGEngine
from src.sandbox import LuaSandbox
from src.experience_bank import ExperienceBank
from src.agents.planner import node_planner
from src.agents.coder import node_coder
from src.agents.tester import node_tester
from src.agents.critic import node_critic, route_after_critic


class AgentState(TypedDict):
    task: str
    memory_md: str          # план от Planner
    rag_context: str        # контекст из FAISS
    experience_hints: str   # инсайты из experience bank
    draft_code: str         # код от Coder
    tests_code: str         # тесты от Tester
    sandbox_result: str     # результат выполнения
    iterations: int         # счётчик Fast Loop
    slow_iterations: int    # счётчик Slow Loop
    status: str             # SUCCESS, NEED_FIX, NEED_NEW_PLAN, GIVE_UP
    lint_fails: int         # счётчик lint failures
    time_started: float     # для замера TTS
    time_finished: float


def build_graph(
    llm: LLMEngine,
    rag: RAGEngine,
    sandbox: LuaSandbox,
    exp_bank: ExperienceBank | None = None,
) -> StateGraph:
    """Собирает и компилирует граф агентов."""

    # Обёртки для узлов (замыкания на llm/rag/sandbox)
    def planner_node(state: AgentState) -> AgentState:
        print("\n🏗️  [PLANNER] Generating architecture plan...")
        result = node_planner(state, llm)
        print(f"    Plan generated ({len(result['memory_md'])} chars)")
        return result

    def coder_node(state: AgentState) -> AgentState:
        iteration = state.get("iterations", 0)
        print(f"\n💻 [CODER] Writing code (iteration {iteration + 1})...")
        result = node_coder(state, llm)
        print(f"    Code generated ({len(result['draft_code'])} chars)")
        return result

    def tester_node(state: AgentState) -> AgentState:
        print("\n🧪 [TESTER] Generating tests...")
        result = node_tester(state, llm, state.get("rag_context", ""))
        print(f"    Tests generated ({len(result['tests_code'])} chars)")
        return result

    def linter_node(state: AgentState) -> AgentState:
        print("\n🔍 [LINTER] Static analysis...")
        lint_fails = state.get("lint_fails", 0)
        lint_result = sandbox.lint(state["draft_code"])
        if lint_result:
            lint_fails += 1
            if lint_fails >= 2:
                # Gave coder a chance, skip lint and proceed to tester
                print(f"    Lint issues remain after {lint_fails} attempts — proceeding to tests anyway")
                return {**state, "status": "LINT_OK", "lint_fails": 0}
            print(f"    Found issues (attempt {lint_fails}/2) — sending back to coder")
            for line in lint_result.output.split("\n")[:5]:
                print(f"    {line}")
            return {
                **state,
                "sandbox_result": lint_result.output,
                "status": "LINT_FAIL",
                "lint_fails": lint_fails,
            }
        print("    Clean")
        return {**state, "status": "LINT_OK", "lint_fails": 0}

    def executor_node(state: AgentState) -> AgentState:
        print("\n⚡ [EXECUTOR] Running code in sandbox...")
        result = sandbox.execute(state["draft_code"], state["tests_code"])
        print(f"    Result: {result.status}")
        if result.output:
            lines = result.output.strip().split("\n")
            for line in lines[-10:]:
                print(f"    {line}")
        return {
            **state,
            "sandbox_result": result.output,
        }

    def critic_node(state: AgentState) -> AgentState:
        print("\n🔍 [CRITIC] Analyzing results...")
        result = node_critic(state)
        print(f"    Decision: {result['status']} (iter={result['iterations']}, slow={result.get('slow_iterations', 0)})")
        if result["status"] == "SUCCESS":
            result["time_finished"] = time.time()
            # Save success insight
            if exp_bank and result["iterations"] <= 1:
                exp_bank.add_insight(
                    task_type="general",
                    insight=f"Task '{state['task'][:60]}' solved on first try with RAG pattern",
                    source="success",
                )
        elif result["status"] in ("NEED_FIX", "NEED_NEW_PLAN") and exp_bank:
            # Extract short failure reason from sandbox output
            error_line = ""
            for line in state.get("sandbox_result", "").split("\n"):
                if any(kw in line for kw in ("[FAIL]", "error", "Error", "INSTRUCTION_LIMIT")):
                    error_line = line.strip()[:100]
                    break
            if error_line:
                exp_bank.add_insight(
                    task_type="general",
                    insight=f"Common error: {error_line}",
                    source="failure",
                )
        return result

    def rag_node(state: AgentState) -> AgentState:
        print("\n📚 [RAG] Retrieving relevant context...")
        context = rag.retrieve_context(state["task"], k=1)
        if context:
            print(f"    Found {context.count('Example')} relevant example(s)")
        else:
            print("    No relevant examples found")

        # Experience bank hints
        hints = ""
        if exp_bank:
            hints = exp_bank.retrieve_insights(state["task"], k=2)
            if hints:
                print(f"    Experience hints: {len(hints.split(chr(10)))} insight(s)")

        return {
            **state,
            "rag_context": context,
            "experience_hints": hints,
            "time_started": time.time(),
        }

    # Сборка графа
    graph = StateGraph(AgentState)

    def route_after_linter(state: AgentState) -> str:
        if state["status"] == "LINT_FAIL":
            return "coder"  # Send back to coder with lint errors
        return "tester"  # Lint OK, proceed to tests

    graph.add_node("rag", rag_node)
    graph.add_node("planner", planner_node)
    graph.add_node("coder", coder_node)
    graph.add_node("linter", linter_node)
    graph.add_node("tester", tester_node)
    graph.add_node("executor", executor_node)
    graph.add_node("critic", critic_node)

    # Связи
    graph.set_entry_point("rag")
    graph.add_edge("rag", "planner")
    graph.add_edge("planner", "coder")
    graph.add_edge("coder", "linter")

    # Linter: if lint fails -> back to coder, else -> tester
    graph.add_conditional_edges(
        "linter",
        route_after_linter,
        {
            "coder": "coder",
            "tester": "tester",
        },
    )

    graph.add_edge("tester", "executor")
    graph.add_edge("executor", "critic")

    # Условный переход после critic
    graph.add_conditional_edges(
        "critic",
        route_after_critic,
        {
            "end": END,
            "coder": "coder",
            "planner": "planner",
        },
    )

    return graph.compile()


def run_task(
    task: str,
    llm: LLMEngine,
    rag: RAGEngine,
    sandbox: LuaSandbox,
    exp_bank: ExperienceBank | None = None,
) -> dict:
    """Запускает граф для одной задачи, возвращает финальное состояние."""
    graph = build_graph(llm, rag, sandbox, exp_bank)

    initial_state: AgentState = {
        "task": task,
        "memory_md": "",
        "rag_context": "",
        "experience_hints": "",
        "draft_code": "",
        "tests_code": "",
        "sandbox_result": "",
        "iterations": 0,
        "slow_iterations": 0,
        "lint_fails": 0,
        "status": "",
        "time_started": 0.0,
        "time_finished": 0.0,
    }

    print(f"\n{'='*60}")
    print(f"TASK: {task}")
    print(f"{'='*60}")

    final_state = graph.invoke(initial_state)

    tts = final_state.get("time_finished", 0) - final_state.get("time_started", 0)
    if tts <= 0:
        tts = time.time() - final_state.get("time_started", time.time())

    print(f"\n{'='*60}")
    print(f"RESULT: {final_state['status']}")
    print(f"TTS: {tts:.1f}s")
    print(f"Iterations: {final_state['iterations']} (slow: {final_state.get('slow_iterations', 0)})")
    print(f"{'='*60}")

    if final_state["status"] == "SUCCESS":
        print("\n✅ Final code:")
        print(final_state["draft_code"])

    return final_state

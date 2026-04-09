"""LocalScript — CLI/FastAPI точка входа для системы агентов."""

import argparse
import json
import sys
import time

from src.llm_engine import LLMEngine
from src.rag_engine import RAGEngine
from src.sandbox import LuaSandbox
from src.experience_bank import ExperienceBank
from src.graph import run_task


def run_cli(args):
    """CLI режим — решает одну задачу."""
    print("Initializing components...")

    llm = LLMEngine(
        model_path=args.model_path,
        n_ctx=args.ctx_size,
        n_gpu_layers=args.gpu_layers,
    )
    rag = RAGEngine()
    sandbox = LuaSandbox(timeout=args.timeout, lua_binary=args.lua_binary)
    exp_bank = ExperienceBank(rag_engine=rag)

    if not sandbox.check_lua_available():
        print(f"WARNING: Lua binary '{args.lua_binary}' not found. Tests will fail.")

    if args.task:
        result = run_task(args.task, llm, rag, sandbox, exp_bank)
        return result
    elif args.interactive:
        print("\nInteractive mode. Type 'quit' to exit.\n")
        while True:
            try:
                task = input("Task> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if task.lower() in ("quit", "exit", "q"):
                break
            if not task:
                continue
            run_task(task, llm, rag, sandbox, exp_bank)
    else:
        print("Provide --task or --interactive flag.")
        sys.exit(1)


def run_server(args):
    """FastAPI HTTP сервер с UI."""
    import uvicorn
    import queue
    import threading
    from pathlib import Path
    from contextlib import redirect_stdout
    from io import StringIO
    from fastapi import FastAPI
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import HTMLResponse, StreamingResponse
    from pydantic import BaseModel

    app = FastAPI(title="LocalScript Agent")

    # Serve UI static files
    ui_dir = Path(__file__).parent / "ui"
    if ui_dir.exists():
        app.mount("/ui", StaticFiles(directory=str(ui_dir), html=True), name="ui")

    llm = LLMEngine(
        model_path=args.model_path,
        n_ctx=args.ctx_size,
        n_gpu_layers=args.gpu_layers,
    )
    rag = RAGEngine()
    sandbox = LuaSandbox(timeout=args.timeout, lua_binary=args.lua_binary)
    exp_bank = ExperienceBank(rag_engine=rag)

    class TaskRequest(BaseModel):
        task: str

    class TaskResponse(BaseModel):
        status: str
        code: str
        tests: str
        tts: float
        iterations: int

    @app.get("/", response_class=HTMLResponse)
    def index():
        html_path = ui_dir / "code.html"
        if html_path.exists():
            return html_path.read_text(encoding="utf-8")
        return "<h1>UI not found. Place code.html in ui/ directory.</h1>"

    @app.post("/solve", response_model=TaskResponse)
    def solve(req: TaskRequest):
        result = run_task(req.task, llm, rag, sandbox, exp_bank)
        tts = result.get("time_finished", 0) - result.get("time_started", 0)
        if tts <= 0:
            tts = time.time() - result.get("time_started", time.time())
        return TaskResponse(
            status=result["status"],
            code=result.get("draft_code", ""),
            tests=result.get("tests_code", ""),
            tts=tts,
            iterations=result.get("iterations", 0),
        )

    @app.post("/solve/stream")
    def solve_stream(req: TaskRequest):
        """SSE endpoint — streams agent events in real-time."""
        event_queue = queue.Queue()

        def _capture_and_run():
            """Runs the graph, captures print output as SSE events."""
            import builtins
            original_print = builtins.print

            def hooked_print(*a, **kw):
                msg = " ".join(str(x) for x in a)
                # Parse agent events from print output
                if "[RAG]" in msg:
                    event_queue.put({"agent": "rag", "message": msg.strip()})
                elif "[PLANNER]" in msg:
                    event_queue.put({"agent": "planner", "message": msg.strip()})
                elif "[CODER]" in msg:
                    event_queue.put({"agent": "coder", "message": msg.strip()})
                elif "[LINTER]" in msg:
                    event_queue.put({"agent": "linter", "message": msg.strip()})
                elif "[TESTER]" in msg:
                    event_queue.put({"agent": "tester", "message": msg.strip()})
                elif "[EXECUTOR]" in msg:
                    event_queue.put({"agent": "executor", "message": msg.strip()})
                elif "[CRITIC]" in msg:
                    event_queue.put({"agent": "critic", "message": msg.strip()})
                elif "[PASS]" in msg or "[FAIL]" in msg:
                    event_queue.put({"agent": "test_result", "message": msg.strip()})
                elif "RESULT:" in msg:
                    event_queue.put({"agent": "result", "message": msg.strip()})
                elif "TTS:" in msg:
                    event_queue.put({"agent": "tts", "message": msg.strip()})
                elif msg.strip():
                    event_queue.put({"agent": "system", "message": msg.strip()})
                original_print(*a, **kw)

            builtins.print = hooked_print
            try:
                result = run_task(req.task, llm, rag, sandbox, exp_bank)
                tts = result.get("time_finished", 0) - result.get("time_started", 0)
                if tts <= 0:
                    tts = time.time() - result.get("time_started", time.time())
                event_queue.put({
                    "agent": "done",
                    "status": result["status"],
                    "code": result.get("draft_code", ""),
                    "tests": result.get("tests_code", ""),
                    "tts": round(tts, 1),
                    "iterations": result.get("iterations", 0),
                })
            except Exception as e:
                event_queue.put({"agent": "error", "message": str(e)})
            finally:
                builtins.print = original_print
                event_queue.put(None)  # sentinel

        def _event_generator():
            thread = threading.Thread(target=_capture_and_run, daemon=True)
            thread.start()
            while True:
                event = event_queue.get()
                if event is None:
                    break
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

        return StreamingResponse(
            _event_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.post("/rag/reload")
    def rag_reload():
        rag.reload()
        return {"status": "reloaded", "entries": len(rag.entries)}

    @app.get("/health")
    def health():
        return {
            "status": "ok",
            "lua_available": sandbox.check_lua_available(),
            "rag_entries": len(rag.entries),
        }

    uvicorn.run(app, host="0.0.0.0", port=args.port)


def run_evaluate(args):
    """Оценка системы по датасету задач."""
    print("Initializing for evaluation...")

    llm = LLMEngine(
        model_path=args.model_path,
        n_ctx=args.ctx_size,
        n_gpu_layers=args.gpu_layers,
    )
    rag = RAGEngine()
    sandbox = LuaSandbox(timeout=args.timeout, lua_binary=args.lua_binary)
    exp_bank = ExperienceBank(rag_engine=rag)

    with open(args.eval_file, "r", encoding="utf-8") as f:
        tasks = json.load(f)

    results = {
        "total": len(tasks),
        "pass_at_1": 0,
        "pass_at_3": 0,
        "total_tts": 0.0,
        "details": [],
    }

    for i, task_obj in enumerate(tasks):
        task_text = task_obj if isinstance(task_obj, str) else task_obj.get("task", "")
        print(f"\n[{i+1}/{len(tasks)}] {task_text[:80]}...")

        start = time.time()
        result = run_task(task_text, llm, rag, sandbox, exp_bank)
        elapsed = time.time() - start

        detail = {
            "task": task_text,
            "status": result["status"],
            "iterations": result["iterations"],
            "tts": elapsed,
        }

        if result["status"] == "SUCCESS":
            results["pass_at_3"] += 1
            if result["iterations"] <= 1:
                results["pass_at_1"] += 1
            results["total_tts"] += elapsed

        results["details"].append(detail)

    # Итоги
    total = results["total"]
    print(f"\n{'='*60}")
    print(f"EVALUATION RESULTS")
    print(f"{'='*60}")
    print(f"Pass@1: {results['pass_at_1']}/{total} ({results['pass_at_1']/total*100:.1f}%)")
    print(f"Pass@3: {results['pass_at_3']}/{total} ({results['pass_at_3']/total*100:.1f}%)")
    if results["pass_at_3"] > 0:
        avg_tts = results["total_tts"] / results["pass_at_3"]
        print(f"Avg TTS (successful): {avg_tts:.1f}s")
    print(f"{'='*60}")

    # Сохраняем результаты
    out_path = args.eval_output or "eval_results.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"Results saved to {out_path}")


def main():
    parser = argparse.ArgumentParser(description="LocalScript — LLM Agent System for Lua")

    # Общие параметры
    parser.add_argument("--model-path", default=None, help="Path to GGUF model")
    parser.add_argument("--ctx-size", type=int, default=8192, help="Context window size")
    parser.add_argument("--gpu-layers", type=int, default=-1, help="GPU layers (-1 = all)")
    parser.add_argument("--timeout", type=int, default=3, help="Lua sandbox timeout (seconds)")
    parser.add_argument("--lua-binary", default="lua", help="Path to lua binary")

    subparsers = parser.add_subparsers(dest="command")

    # CLI
    cli_parser = subparsers.add_parser("solve", help="Solve a single task")
    cli_parser.add_argument("--task", type=str, help="Task description")
    cli_parser.add_argument("--interactive", "-i", action="store_true", help="Interactive mode")

    # Server
    server_parser = subparsers.add_parser("server", help="Start FastAPI server")
    server_parser.add_argument("--port", type=int, default=8080, help="Server port")

    # Evaluate
    eval_parser = subparsers.add_parser("evaluate", help="Evaluate on dataset")
    eval_parser.add_argument("--eval-file", required=True, help="JSON file with tasks")
    eval_parser.add_argument("--eval-output", default=None, help="Output JSON path")

    # Build RAG index
    rag_parser = subparsers.add_parser("build-rag", help="Build FAISS index from knowledge_base.json")

    args = parser.parse_args()

    if args.command == "solve":
        run_cli(args)
    elif args.command == "server":
        run_server(args)
    elif args.command == "evaluate":
        run_evaluate(args)
    elif args.command == "build-rag":
        rag = RAGEngine()
        if not rag.entries:
            print("ERROR: knowledge_base.json is empty or not found")
            sys.exit(1)
        rag.build_index()
        print(f"Index built with {len(rag.entries)} entries")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Run MWS PDF tasks and report results."""
import time
from src.llm_engine import LLMEngine
from src.rag_engine import RAGEngine
from src.sandbox import LuaSandbox
from src.experience_bank import ExperienceBank
from src.graph import run_task

llm = LLMEngine()
rag = RAGEngine()
sandbox = LuaSandbox(lua_binary="/home/dragonevsky/local-script/lua54")
exp = ExperienceBank(rag_engine=rag)

tasks = [
    "Увеличивай значение переменной try_count_n на каждой итерации. wf.vars.try_count_n = 3",
    "Для полученных данных из предыдущего REST запроса очисти значения переменных ID, ENTITY_ID, CALL. wf.vars.RESTbody.result содержит массив объектов.",
    "Отфильтруй элементы из массива, чтобы включить только те, у которых есть значения в полях Discount или Markdown. wf.vars.parsedCsv содержит массив.",
    "Преобразуй время из формата YYYYMMDD и HHMMSS в строку в формате ISO 8601. wf.vars.json.IDOC.ZCDF_HEAD.DATUM и wf.vars.json.IDOC.ZCDF_HEAD.TIME",
]

results = []
for i, task in enumerate(tasks):
    print(f"\n{'='*60}")
    print(f"TEST {i+1}: {task[:70]}...")
    start = time.time()
    result = run_task(task, llm, rag, sandbox, exp)
    elapsed = time.time() - start
    status = result["status"]
    code = result.get("draft_code", "")
    results.append((status, elapsed, code[:200]))
    print(f"=> {status} | {elapsed:.1f}s | code: {code[:100]}")

print(f"\n{'='*60}")
print("SUMMARY:")
for i, (s, t, c) in enumerate(results):
    print(f"  Task {i+1}: {s} ({t:.1f}s) -> {c[:80]}")
passed = sum(1 for s, _, _ in results if s == "SUCCESS")
print(f"\nPassed: {passed}/{len(results)}")

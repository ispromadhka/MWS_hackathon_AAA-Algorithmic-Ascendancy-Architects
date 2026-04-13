#!/usr/bin/env python3
"""Test ALL 8 tasks from hackathon PDF."""
import time, sys, os
sys.path.insert(0, os.path.dirname(__file__))

from src.llm_engine import LLMEngine
from src.rag_engine import RAGEngine
from src.sandbox import LuaSandbox
from src.experience_bank import ExperienceBank
from src.graph import run_task

llm = LLMEngine()
rag = RAGEngine()
sandbox = LuaSandbox(lua_binary=os.environ.get("LUA_BIN", "lua"))
exp = ExperienceBank(rag_engine=rag)

TASKS = [
    # 1. Last element of array
    "Из полученного списка email получи последний. wf.vars.emails содержит массив email адресов.",
    # 2. Increment counter
    "Увеличивай значение переменной try_count_n на каждой итерации. wf.vars.try_count_n = 3",
    # 3. Clean fields
    "Для полученных данных из предыдущего REST запроса очисти значения переменных ID, ENTITY_ID, CALL. wf.vars.RESTbody.result содержит массив объектов.",
    # 4. ISO 8601 date
    "Преобразуй время из формата YYYYMMDD и HHMMSS в строку в формате ISO 8601. wf.vars.json.IDOC.ZCDF_HEAD.DATUM и wf.vars.json.IDOC.ZCDF_HEAD.TIME",
    # 5. Type check (ensure arrays)
    "Как преобразовать структуру данных так, чтобы все элементы items в ZCDF_PACKAGES всегда были представлены в виде массивов, даже если они изначально не являются массивами. wf.vars.json.IDOC.ZCDF_HEAD.ZCDF_PACKAGES",
    # 6. Filter array
    "Отфильтруй элементы из массива wf.vars.parsedCsv, чтобы включить только те у которых есть значения в полях Discount или Markdown.",
    # 7. Add variable (squared number)
    "Добавь переменную с квадратом числа. tonumber('5')",
    # 8. Convert time to unix
    "Конвертируй время в переменной recallTime в unix-формат. wf.initVariables.recallTime = '2023-10-15T15:30:00+00:00'",
]

EXPECTED = [
    "return wf.vars.emails[#wf.vars.emails]",
    "return wf.vars.try_count_n + 1",
    None,  # complex
    None,  # complex
    None,  # complex
    None,  # complex
    None,  # complex
    None,  # complex
]

results = []
for i, task in enumerate(TASKS):
    print(f"\n{'='*60}")
    print(f"TASK {i+1}/8: {task[:60]}...")
    start = time.time()
    result = run_task(task, llm, rag, sandbox, exp)
    elapsed = time.time() - start
    status = result["status"]
    code = result.get("draft_code", "").strip()
    results.append((status, elapsed, code))

    match = ""
    if EXPECTED[i] and EXPECTED[i] in code:
        match = " [EXACT MATCH]"
    print(f"=> {status} | {elapsed:.1f}s{match}")
    print(f"   Code: {code[:120]}")

print(f"\n{'='*60}")
print("FINAL RESULTS:")
print(f"{'='*60}")
passed = 0
for i, (s, t, c) in enumerate(results):
    icon = "+" if s == "SUCCESS" else "x"
    print(f"  [{icon}] Task {i+1}: {s} ({t:.1f}s)")
    if s == "SUCCESS":
        passed += 1
print(f"\nScore: {passed}/8 ({passed/8*100:.0f}%)")
print(f"Total time: {sum(t for _, t, _ in results):.1f}s")

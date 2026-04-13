#!/usr/bin/env python3
"""Extra tests beyond PDF — stress test the agent on MWS-style tasks."""
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
    # Simple data access
    "Верни первый элемент массива wf.vars.users",
    "Получи длину массива wf.vars.items и верни её",
    # String operations
    "Объедини wf.vars.firstName и wf.vars.lastName через пробел и верни результат",
    "Преобразуй строку wf.vars.email в нижний регистр",
    # Math
    "Посчитай сумму всех элементов числового массива wf.vars.prices",
    "Верни максимальный элемент из массива wf.vars.scores",
    # Filtering & transformation
    "Из массива wf.vars.orders отфильтруй только те где поле status равно 'completed'",
    "Для каждого элемента массива wf.vars.products добавь поле fullName равное name .. ' - ' .. category",
    # Conditional logic
    "Если wf.vars.age больше 18 верни 'adult' иначе 'minor'",
    "Проверь что wf.vars.password не nil и длина больше 8 символов. Верни true или false",
    # Nested access
    "Получи значение wf.vars.response.data.items[1].name",
    "Посчитай количество элементов в wf.vars.json.IDOC.ZCDF_HEAD.ZCDF_PACKAGES",
]

results = []
for i, task in enumerate(TASKS):
    print(f"\n{'='*60}")
    print(f"EXTRA {i+1}/{len(TASKS)}: {task[:60]}...")
    start = time.time()
    result = run_task(task, llm, rag, sandbox, exp)
    elapsed = time.time() - start
    status = result["status"]
    code = result.get("draft_code", "").strip()
    results.append((status, elapsed, code))
    icon = "+" if status == "SUCCESS" else "x"
    print(f"=> [{icon}] {status} | {elapsed:.1f}s | {code[:80]}")

print(f"\n{'='*60}")
print("EXTRA TEST RESULTS:")
passed = sum(1 for s, _, _ in results if s == "SUCCESS")
for i, (s, t, c) in enumerate(results):
    icon = "+" if s == "SUCCESS" else "x"
    print(f"  [{icon}] {i+1}. {TASKS[i][:50]}... -> {s} ({t:.1f}s)")
print(f"\nScore: {passed}/{len(TASKS)} ({passed/len(TASKS)*100:.0f}%)")
print(f"Total: {sum(t for _,t,_ in results):.0f}s | Avg: {sum(t for _,t,_ in results)/len(TASKS):.1f}s")

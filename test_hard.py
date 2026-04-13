#!/usr/bin/env python3
"""Hard tests — tricky MWS tasks that might appear on closed evaluation."""
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
    # Nested field manipulation
    "Извлеки все значения поля email из массива объектов wf.vars.contacts и верни как новый массив",
    "Установи поле processed в true для всех элементов массива wf.vars.tasks",
    # String parsing
    "Извлеки домен из email адреса wf.vars.email (часть после @)",
    "Преобразуй строку wf.vars.snake_name из snake_case в camelCase",
    # Numeric
    "Округли число wf.vars.price до 2 знаков после запятой",
    "Верни абсолютное значение числа wf.vars.delta",
    # Conditional filtering
    "Из массива wf.vars.products верни только те где price > 100 и stock > 0",
    "Подсчитай сколько элементов в wf.vars.logs имеют level равный 'error'",
    # Data transformation
    "Преобразуй массив wf.vars.pairs вида [{key:'a', value:1}] в таблицу {a=1}",
    "Создай строку из массива wf.vars.words разделив их запятой с пробелом",
    # Complex business
    "Для каждого элемента wf.vars.orders посчитай total = sum(items[i].price * items[i].qty) и добавь поле total",
    "Отсортируй массив wf.vars.students по полю grade в убывающем порядке",
    # Edge cases
    "Верни true если массив wf.vars.data пустой, false если нет",
    "Склей все непустые строки из массива wf.vars.parts через разделитель /",
    "Замени в строке wf.vars.template все вхождения {name} на значение wf.vars.userName",
]

results = []
for i, task in enumerate(TASKS):
    print(f"\n{'='*60}")
    print(f"HARD {i+1}/{len(TASKS)}: {task[:55]}...")
    start = time.time()
    result = run_task(task, llm, rag, sandbox, exp)
    elapsed = time.time() - start
    status = result["status"]
    code = result.get("draft_code", "").strip()
    results.append((status, elapsed, code))
    icon = "+" if status == "SUCCESS" else "x"
    print(f"=> [{icon}] {status} | {elapsed:.1f}s | {code[:80]}")

print(f"\n{'='*60}")
print("HARD TEST RESULTS:")
passed = sum(1 for s, _, _ in results if s == "SUCCESS")
for i, (s, t, c) in enumerate(results):
    icon = "+" if s == "SUCCESS" else "x"
    print(f"  [{icon}] {i+1}. {TASKS[i][:50]}... -> {s} ({t:.1f}s)")
    if s == "SUCCESS":
        print(f"       {c[:70]}")
print(f"\nScore: {passed}/{len(TASKS)} ({passed/len(TASKS)*100:.0f}%)")
print(f"Total: {sum(t for _,t,_ in results):.0f}s | Avg: {sum(t for _,t,_ in results)/len(TASKS):.1f}s")

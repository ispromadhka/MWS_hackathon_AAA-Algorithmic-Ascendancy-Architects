#!/usr/bin/env python3
"""Stress test — edge cases, complex tasks, Russian prompts."""
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
    # Edge cases
    "Верни пустую строку если wf.vars.name равно nil, иначе верни wf.vars.name",
    "Проверь является ли wf.vars.value числом. Верни true если да, false если нет",
    "Удали дубликаты из массива wf.vars.tags и верни уникальные элементы",
    # String operations
    "Замени все пробелы в строке wf.vars.text на символ подчёркивания _",
    "Обрежь пробелы в начале и конце строки wf.vars.input",
    "Раздели строку wf.vars.csv по запятой и верни массив",
    # Table operations
    "Объедини два массива wf.vars.arr1 и wf.vars.arr2 в один",
    "Переверни массив wf.vars.list задом наперёд",
    "Создай новый массив из поля name каждого элемента wf.vars.users (аналог map)",
    # Business logic
    "Посчитай общую стоимость: для каждого элемента wf.vars.cart умножь price на quantity и сложи всё",
    "Сгруппируй элементы массива wf.vars.items по полю category. Верни таблицу где ключ это category а значение массив элементов",
    "Найди элемент в массиве wf.vars.users где поле id равно wf.vars.targetId",
    # Date/time
    "Преобразуй дату из формата DD.MM.YYYY (wf.vars.date) в YYYY-MM-DD",
    # Complex
    "Напиши функцию factorial(n) для вычисления факториала числа n. Верни factorial(wf.vars.n)",
    "Посчитай среднее арифметическое массива wf.vars.values",
]

results = []
for i, task in enumerate(TASKS):
    print(f"\n{'='*60}")
    print(f"STRESS {i+1}/{len(TASKS)}: {task[:55]}...")
    start = time.time()
    result = run_task(task, llm, rag, sandbox, exp)
    elapsed = time.time() - start
    status = result["status"]
    code = result.get("draft_code", "").strip()
    results.append((status, elapsed, code))
    icon = "+" if status == "SUCCESS" else "x"
    print(f"=> [{icon}] {status} | {elapsed:.1f}s | {code[:80]}")

print(f"\n{'='*60}")
print("STRESS TEST RESULTS:")
passed = sum(1 for s, _, _ in results if s == "SUCCESS")
for i, (s, t, c) in enumerate(results):
    icon = "+" if s == "SUCCESS" else "x"
    print(f"  [{icon}] {i+1}. {TASKS[i][:50]}... -> {s} ({t:.1f}s)")
    if s == "SUCCESS":
        print(f"       Code: {c[:70]}")
print(f"\nScore: {passed}/{len(TASKS)} ({passed/len(TASKS)*100:.0f}%)")
print(f"Total: {sum(t for _,t,_ in results):.0f}s | Avg: {sum(t for _,t,_ in results)/len(TASKS):.1f}s")

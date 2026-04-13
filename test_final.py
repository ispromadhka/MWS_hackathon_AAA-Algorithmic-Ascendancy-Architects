#!/usr/bin/env python3
"""Final validation — 20 diverse tasks."""
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
    "Верни количество символов в строке wf.vars.text",
    "Проверь содержит ли строка wf.vars.url подстроку 'https'. Верни true или false",
    "Преобразуй все элементы массива wf.vars.names в верхний регистр",
    "Удали элемент с индексом 2 из массива wf.vars.items",
    "Склей wf.vars.protocol, '://' и wf.vars.host в одну строку",
    "Создай копию таблицы wf.vars.config (неглубокую)",
    "Верни ключи таблицы wf.vars.settings как массив",
    "Посчитай факториал числа wf.vars.n рекурсивно",
    "Замени первое вхождение слова 'old' на 'new' в строке wf.vars.text",
    "Извлеки год из строки даты wf.vars.date формата YYYY-MM-DD",
    "Верни true если все элементы массива wf.vars.flags равны true",
    "Преобразуй число wf.vars.seconds в формат MM:SS",
    "Найди индекс элемента со значением wf.vars.target в массиве wf.vars.arr",
    "Подсчитай сколько раз символ ',' встречается в строке wf.vars.csv",
    "Объедини все строки из массива wf.vars.lines в одну с переносом строки",
    "Верни последние 3 элемента массива wf.vars.history",
    "Проверь что wf.vars.code это строка из 6 цифр",
    "Создай массив чисел от 1 до wf.vars.count",
    "Переведи температуру из Цельсия wf.vars.celsius в Фаренгейт",
    "Удали все элементы из wf.vars.messages где поле read равно true",
]

results = []
for i, task in enumerate(TASKS):
    print(f"\n{'='*60}")
    print(f"FINAL {i+1}/{len(TASKS)}: {task[:55]}...")
    start = time.time()
    result = run_task(task, llm, rag, sandbox, exp)
    elapsed = time.time() - start
    status = result["status"]
    code = result.get("draft_code", "").strip()
    results.append((status, elapsed, code))
    icon = "+" if status == "SUCCESS" else "x"
    print(f"=> [{icon}] {status} | {elapsed:.1f}s | {code[:70]}")

print(f"\n{'='*60}")
print("FINAL VALIDATION:")
passed = sum(1 for s, _, _ in results if s == "SUCCESS")
for i, (s, t, c) in enumerate(results):
    icon = "+" if s == "SUCCESS" else "x"
    print(f"  [{icon}] {i+1}. {TASKS[i][:50]}... -> {s} ({t:.1f}s)")
print(f"\nScore: {passed}/{len(TASKS)} ({passed/len(TASKS)*100:.0f}%)")
print(f"Total: {sum(t for _,t,_ in results):.0f}s | Avg: {sum(t for _,t,_ in results)/len(TASKS):.1f}s")

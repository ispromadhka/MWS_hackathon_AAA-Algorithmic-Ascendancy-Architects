#!/usr/bin/env python3
"""Full sweep — all tasks from all test suites."""
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

ALL = [
    # PDF 8
    "Из полученного списка email получи последний. wf.vars.emails содержит массив email адресов.",
    "Увеличивай значение переменной try_count_n на каждой итерации. wf.vars.try_count_n = 3",
    "Для полученных данных из предыдущего REST запроса очисти значения переменных ID, ENTITY_ID, CALL. wf.vars.RESTbody.result содержит массив объектов.",
    "Преобразуй время из формата YYYYMMDD и HHMMSS в строку в формате ISO 8601. wf.vars.json.IDOC.ZCDF_HEAD.DATUM и wf.vars.json.IDOC.ZCDF_HEAD.TIME",
    "Как преобразовать структуру данных так, чтобы все элементы items в ZCDF_PACKAGES всегда были представлены в виде массивов. wf.vars.json.IDOC.ZCDF_HEAD.ZCDF_PACKAGES",
    "Отфильтруй элементы из массива wf.vars.parsedCsv, чтобы включить только те у которых есть значения в полях Discount или Markdown.",
    "Добавь переменную с квадратом числа. tonumber('5')",
    "Конвертируй время в переменной recallTime в unix-формат. wf.initVariables.recallTime = '2023-10-15T15:30:00+00:00'",
    # Extra 10 (cherry-picked)
    "Верни первый элемент массива wf.vars.users",
    "Посчитай сумму всех элементов числового массива wf.vars.prices",
    "Из массива wf.vars.orders отфильтруй только те где поле status равно 'completed'",
    "Если wf.vars.age больше 18 верни 'adult' иначе 'minor'",
    "Посчитай количество элементов в wf.vars.json.IDOC.ZCDF_HEAD.ZCDF_PACKAGES",
    # Hard 10 (cherry-picked)
    "Извлеки домен из email адреса wf.vars.email (часть после @)",
    "Из массива wf.vars.products верни только те где price > 100 и stock > 0",
    "Создай строку из массива wf.vars.words разделив их запятой с пробелом",
    "Отсортируй массив wf.vars.students по полю grade в убывающем порядке",
    "Замени в строке wf.vars.template все вхождения {name} на значение wf.vars.userName",
    # Final 7 (cherry-picked)
    "Верни ключи таблицы wf.vars.settings как массив",
    "Создай массив чисел от 1 до wf.vars.count",
    "Переведи температуру из Цельсия wf.vars.celsius в Фаренгейт",
    "Подсчитай сколько раз символ ',' встречается в строке wf.vars.csv",
    "Верни последние 3 элемента массива wf.vars.history",
    "Верни true если массив wf.vars.data пустой, false если нет",
    "Посчитай среднее арифметическое массива wf.vars.values",
]

results = []
for i, task in enumerate(ALL):
    start = time.time()
    result = run_task(task, llm, rag, sandbox, exp)
    elapsed = time.time() - start
    status = result["status"]
    code = result.get("draft_code", "").strip()
    results.append((status, elapsed, code))
    icon = "+" if status == "SUCCESS" else "x"
    print(f"[{icon}] {i+1}/{len(ALL)} {status} {elapsed:.1f}s | {task[:50]}")

print(f"\n{'='*60}")
passed = sum(1 for s, _, _ in results if s == "SUCCESS")
print(f"SWEEP: {passed}/{len(ALL)} ({passed/len(ALL)*100:.0f}%)")
print(f"Total: {sum(t for _,t,_ in results):.0f}s | Avg: {sum(t for _,t,_ in results)/len(ALL):.1f}s")
fails = [(i, ALL[i], c) for i, (s, _, c) in enumerate(results) if s != "SUCCESS"]
if fails:
    print(f"\nFailed:")
    for idx, task, code in fails:
        print(f"  {idx+1}. {task[:60]} -> {code[:60]}")

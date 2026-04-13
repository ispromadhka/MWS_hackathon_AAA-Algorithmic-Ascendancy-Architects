#!/usr/bin/env python3
"""Brutal test — 30 completely new tasks the model has never seen."""
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
    # Array operations
    "Верни предпоследний элемент массива wf.vars.items",
    "Удали последний элемент из массива wf.vars.stack и верни его (pop)",
    "Вставь значение wf.vars.newItem в начало массива wf.vars.queue",
    "Верни массив wf.vars.numbers отсортированный по возрастанию",
    "Переверни строку wf.vars.text задом наперёд",
    # String ops
    "Верни true если строка wf.vars.str начинается с 'http'",
    "Обрежь строку wf.vars.description до 100 символов и добавь '...' если она длиннее",
    "Посчитай количество слов в строке wf.vars.sentence (разделены пробелами)",
    "Замени все переносы строки в wf.vars.multiline на пробелы",
    "Извлеки расширение файла из wf.vars.filename (часть после последней точки)",
    # Math & logic
    "Верни минимальное значение из массива wf.vars.temps",
    "Верни true если wf.vars.num четное, false если нечетное",
    "Посчитай процент: wf.vars.part от wf.vars.total (результат округли до целого)",
    "Верни знак числа wf.vars.x: 1 если положительное, -1 если отрицательное, 0 если ноль",
    # Table/object ops
    "Подсчитай количество ключей в таблице wf.vars.metadata",
    "Проверь существует ли ключ 'email' в таблице wf.vars.user. Верни true или false",
    "Скопируй все поля из wf.vars.defaults в wf.vars.config если их там нет (merge с приоритетом config)",
    "Преобразуй массив wf.vars.items в строку JSON формата (без библиотек, простая сериализация)",
    # Filtering & mapping
    "Из массива wf.vars.numbers оставь только положительные числа",
    "Удвой каждый элемент числового массива wf.vars.values",
    "Из массива wf.vars.strings удали все пустые строки",
    "Верни массив уникальных значений поля city из массива объектов wf.vars.addresses",
    # Business logic
    "Если wf.vars.score >= 90 верни 'A', >= 80 верни 'B', >= 70 верни 'C', иначе 'F'",
    "Для каждого элемента wf.vars.employees добавь поле fullName = firstName .. ' ' .. lastName",
    "Найди самый дорогой продукт (максимальный price) в массиве wf.vars.catalog и верни его",
    # Date & format
    "Извлеки часы и минуты из строки wf.vars.time формата HH:MM:SS и верни как HH:MM",
    "Преобразуй wf.vars.amount (число) в строку с разделителем тысяч (1234567 -> '1 234 567')",
    # Edge cases
    "Верни wf.vars.list без первого и последнего элемента (slice от 2 до #list-1)",
    "Склей массив wf.vars.path в строку через '/' но убери дублирующиеся слэши",
    "Проверь что строка wf.vars.phone соответствует формату +7XXXXXXXXXX (11 цифр после +)",
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
print(f"BRUTAL: {passed}/{len(ALL)} ({passed/len(ALL)*100:.0f}%)")
print(f"Total: {sum(t for _,t,_ in results):.0f}s | Avg: {sum(t for _,t,_ in results)/len(ALL):.1f}s")
fails = [(i, ALL[i], c[:60]) for i, (s, _, c) in enumerate(results) if s != "SUCCESS"]
if fails:
    print(f"\nFailed ({len(fails)}):")
    for idx, task, code in fails:
        print(f"  {idx+1}. {task[:55]}...")
        print(f"     -> {code}")

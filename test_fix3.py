#!/usr/bin/env python3
"""Test the 3 previously failing tasks."""
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
    "Удали дубликаты из массива wf.vars.tags и верни уникальные элементы",
    "Получи значение wf.vars.response.data.items[1].name",
    "Извлеки домен из email адреса wf.vars.email (часть после @)",
]

for i, task in enumerate(TASKS):
    print(f"\n{'='*60}")
    print(f"FIX TEST {i+1}: {task}")
    start = time.time()
    result = run_task(task, llm, rag, sandbox, exp)
    elapsed = time.time() - start
    status = result["status"]
    code = result.get("draft_code", "").strip()
    icon = "+" if status == "SUCCESS" else "x"
    print(f"=> [{icon}] {status} | {elapsed:.1f}s")
    print(f"   Code: {code[:150]}")

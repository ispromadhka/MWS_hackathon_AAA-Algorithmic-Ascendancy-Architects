"""Lua Sandbox — безопасное выполнение Lua кода через subprocess."""

import subprocess
import tempfile
import os
from dataclasses import dataclass


@dataclass
class SandboxResult:
    status: str  # "success" | "error" | "timeout"
    output: str
    exit_code: int = 0


def _find_lua_binary() -> str:
    """Ищет доступный Lua бинарник."""
    candidates = [
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lua54"),
        "lua5.4",
        "lua",
        "luajit",
    ]
    for candidate in candidates:
        try:
            subprocess.run([candidate, "-v"], capture_output=True, timeout=5)
            return candidate
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    return "lua"


class LuaSandbox:
    """Выполняет Lua-код в изолированном процессе с таймаутом."""

    def __init__(self, timeout: int = 3, lua_binary: str | None = None):
        self.timeout = timeout
        self.lua_binary = lua_binary or _find_lua_binary()

    def lint(self, code: str) -> SandboxResult | None:
        """Запускает luacheck на коде. Возвращает SandboxResult с ошибками или None если ок."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".lua", delete=False, encoding="utf-8"
        ) as f:
            f.write(code)
            tmp_path = f.name

        try:
            result = subprocess.run(
                ["luacheck", "--no-config", "--codes", "--no-color", "--quiet", tmp_path],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return None  # No issues
            # Filter: only errors (E) and warnings about undefined globals (W111, W112, W113)
            important = []
            for line in result.stdout.strip().split("\n"):
                if any(code in line for code in ("(E", "(W111", "(W112", "(W113")):
                    important.append(line)
            if not important:
                return None  # Only style warnings, not real errors
            return SandboxResult(
                status="lint_error",
                output="Luacheck found issues:\n" + "\n".join(important),
                exit_code=result.returncode,
            )
        except FileNotFoundError:
            return None  # luacheck not installed, skip
        except subprocess.TimeoutExpired:
            return None
        finally:
            os.unlink(tmp_path)

    def execute(self, code: str, tests: str = "") -> SandboxResult:
        """
        Склеивает code + tests, выполняет через lua, возвращает результат.
        """
        full_code = self._build_full_code(code, tests)

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".lua", delete=False, encoding="utf-8"
        ) as f:
            f.write(full_code)
            tmp_path = f.name

        try:
            result = subprocess.run(
                [self.lua_binary, tmp_path],
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )

            if result.returncode == 0:
                return SandboxResult(
                    status="success",
                    output=result.stdout.strip(),
                    exit_code=0,
                )
            else:
                error_msg = result.stderr.strip() or result.stdout.strip()
                return SandboxResult(
                    status="error",
                    output=error_msg,
                    exit_code=result.returncode,
                )

        except subprocess.TimeoutExpired:
            return SandboxResult(
                status="timeout",
                output=f"Execution timed out after {self.timeout}s",
                exit_code=-1,
            )
        except FileNotFoundError:
            return SandboxResult(
                status="error",
                output=f"Lua binary not found: {self.lua_binary}. Install lua5.4 or set lua_binary path.",
                exit_code=-1,
            )
        finally:
            os.unlink(tmp_path)

    def _build_full_code(self, code: str, tests: str) -> str:
        """Склеивает код и тесты с обёрткой для отлова ошибок."""
        parts = []

        # Sandbox guards + test framework
        parts.append("""
-- Sandbox: restricted environment
os.execute = nil
io.popen = nil
loadfile = nil
dofile = nil

-- Sandbox: instruction limit (prevents infinite loops)
local _instruction_count = 0
local _max_instructions = 500000
debug.sethook(function()
    _instruction_count = _instruction_count + 1
    if _instruction_count > _max_instructions then
        error("INSTRUCTION_LIMIT: exceeded " .. _max_instructions .. " instructions (possible infinite loop)")
    end
end, "", 1000)

-- Sandbox: memory tracking
collectgarbage("collect")
local _mem_before = collectgarbage("count")

-- Test framework
local _test_passed = 0
local _test_failed = 0
local _test_errors = {}

function test_assert(condition, message)
    message = message or "unnamed test"
    if condition then
        _test_passed = _test_passed + 1
        print("[PASS] " .. message)
    else
        _test_failed = _test_failed + 1
        table.insert(_test_errors, message)
        print("[FAIL] " .. message)
    end
end

function test_assert_eq(got, expected, message)
    message = message or "equality check"
    if got == expected then
        test_assert(true, message)
    else
        test_assert(false, message .. " (got: " .. tostring(got) .. ", expected: " .. tostring(expected) .. ")")
    end
end

function test_summary()
    -- Memory check
    collectgarbage("collect")
    local _mem_after = collectgarbage("count")
    local _mem_used = _mem_after - _mem_before

    print("\\n=== TEST RESULTS ===")
    print("Passed: " .. _test_passed)
    print("Failed: " .. _test_failed)
    print(string.format("Memory: %.1f KB | Instructions: ~%d", _mem_used, _instruction_count * 1000))
    if _mem_used > 1024 then
        print("WARNING: Memory usage exceeded 1MB (" .. string.format("%.1f", _mem_used) .. " KB)")
    end
    if _test_failed > 0 then
        print("Failed tests:")
        for _, msg in ipairs(_test_errors) do
            print("  - " .. msg)
        end
        os.exit(1)
    else
        print("All tests passed!")
        os.exit(0)
    end
end
""")

        # Пользовательский код
        parts.append("-- User code\n" + code)

        # Тесты
        if tests.strip():
            parts.append("-- Tests\n" + tests)
            parts.append("\ntest_summary()")

        return "\n\n".join(parts)

    def check_lua_available(self) -> bool:
        """Проверяет, доступен ли интерпретатор Lua."""
        try:
            result = subprocess.run(
                [self.lua_binary, "-v"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

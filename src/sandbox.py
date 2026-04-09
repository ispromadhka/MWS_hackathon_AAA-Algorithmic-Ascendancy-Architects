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

    def check_lua_antipatterns(self, code: str) -> SandboxResult | None:
        """Проверяет код на Python-style anti-patterns в Lua."""
        issues = []

        # Detect __init__ (Python constructor pattern)
        if "__init__" in code:
            issues.append("ANTI-PATTERN: '__init__' is Python, not Lua. Use 'function MyClass.new()' with setmetatable instead.")

        # Detect OOP without setmetatable
        has_methods = "function " in code and ("." in code.split("function ")[1].split("(")[0] if "function " in code else False)
        has_oop_indicators = ".__index" in code or ":new(" in code or ".new(" in code or "self." in code
        if has_oop_indicators and "setmetatable" not in code:
            issues.append("ANTI-PATTERN: OOP code detected but 'setmetatable' is missing. Add 'MyClass.__index = MyClass' and use 'setmetatable({}, MyClass)' in constructor.")

        # Detect Python-style method definition (explicit self as first arg)
        import re
        python_methods = re.findall(r'function\s+\w+\.(\w+)\s*\(\s*self\b', code)
        if python_methods:
            issues.append(f"ANTI-PATTERN: Python-style method definition with explicit 'self' arg in: {', '.join(python_methods)}. Use colon syntax instead: 'function MyClass:methodName()'")

        # Detect global module table (no 'local' before main table)
        lines = code.strip().split("\n")
        for line in lines[:5]:
            stripped = line.strip()
            if stripped and not stripped.startswith("--") and not stripped.startswith("local") and "= {}" in stripped:
                issues.append(f"ANTI-PATTERN: Global variable '{stripped.split('=')[0].strip()}'. Use 'local' keyword: 'local {stripped}'")
                break

        if issues:
            return SandboxResult(
                status="lint_error",
                output="Lua anti-pattern check failed:\n" + "\n".join(f"  - {i}" for i in issues),
                exit_code=1,
            )
        return None

    def lint(self, code: str) -> SandboxResult | None:
        """Запускает luacheck + anti-pattern check."""
        # First check anti-patterns (fast, no external tool)
        ap = self.check_lua_antipatterns(code)
        if ap:
            return ap

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

        # Mock ngx if code uses nginx/OpenResty APIs
        if "ngx." in code or "ngx " in code:
            parts.append("""
-- Mock ngx for standalone Lua testing
if not ngx then
    ngx = {}
    ngx._output = {}
    ngx._status = 200
    ngx._headers = {}
    ngx._exit_code = nil
    ngx.HTTP_OK = 200
    ngx.HTTP_FORBIDDEN = 403
    ngx.HTTP_NOT_FOUND = 404
    ngx.HTTP_INTERNAL_SERVER_ERROR = 500
    ngx.WARN = 5
    ngx.ERR = 4
    ngx.status = 200
    ngx.header = setmetatable({}, {
        __newindex = function(t, k, v) ngx._headers[k] = v end,
        __index = function(t, k) return ngx._headers[k] end,
    })
    ngx.var = setmetatable({}, {
        __index = function(t, k)
            if k == 'remote_addr' then return '127.0.0.1' end
            if k == 'uri' then return '/' end
            return nil
        end
    })
    ngx.req = {
        get_headers = function()
            return { ['User-Agent'] = ngx._test_ua or 'Mozilla/5.0 (X11; Linux) Gecko/20100101 Firefox/120.0' }
        end,
        get_method = function() return ngx._test_method or 'GET' end,
        get_uri_args = function() return ngx._test_args or {} end,
        read_body = function() end,
        get_body_data = function() return ngx._test_body or '{}' end,
    }
    ngx.say = function(...)
        local args = {...}
        for _, v in ipairs(args) do
            table.insert(ngx._output, tostring(v))
        end
    end
    ngx.print = ngx.say
    ngx.exit = function(code) ngx._exit_code = code end
    ngx.log = function() end
    ngx.now = function() return os.time() end
    ngx.shared = setmetatable({}, {
        __index = function() return { get=function() end, set=function() end, incr=function() end } end
    })
    -- Helper for tests to get output
    function ngx.get_output() return table.concat(ngx._output, '\\n') end
    function ngx.reset()
        ngx._output = {}
        ngx._status = 200
        ngx._headers = {}
        ngx._exit_code = nil
    end
end
""")

        # User code — strip trailing 'return X' to allow tests to follow
        user_code = code
        if tests.strip():
            # Remove trailing return statement so tests can be appended
            lines = user_code.rstrip().split("\n")
            while lines and lines[-1].strip().startswith("return "):
                lines.pop()
            user_code = "\n".join(lines)

        parts.append("-- User code\n" + user_code)

        # Тесты — strip require() lines that break single-file sandbox
        if tests.strip():
            cleaned_tests = "\n".join(
                line for line in tests.split("\n")
                if not line.strip().startswith("local ") or "require" not in line
                if "require(" not in line and "require (" not in line
            )
            parts.append("-- Tests\n" + cleaned_tests)
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

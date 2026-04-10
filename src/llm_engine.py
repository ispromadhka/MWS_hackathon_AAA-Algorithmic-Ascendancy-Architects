"""LLM Engine — обёртка над Ollama API для локального инференса."""

import os
import json
import urllib.request
import urllib.error

OLLAMA_BASE = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
DEFAULT_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5-coder:7b-instruct-q4_K_M")


class LLMEngine:
    """Вызывает Ollama API для генерации. Модель должна быть уже загружена через ollama pull."""

    def __init__(
        self,
        model: str | None = None,
        ollama_base: str | None = None,
        n_ctx: int = 4096,
        **kwargs,  # ignore legacy params (model_path, n_gpu_layers, etc.)
    ):
        self.model = model or DEFAULT_MODEL
        self.base_url = ollama_base or OLLAMA_BASE
        self.n_ctx = n_ctx

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 256,
        temperature: float = 0.2,
        top_p: float = 0.9,
        stop: list[str] | None = None,
    ) -> str:
        """Генерирует ответ через Ollama /api/chat."""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "top_p": top_p,
                "num_predict": max_tokens,
                "num_ctx": self.n_ctx,
                "stop": stop or [],
            },
        }

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=data,
            headers={"Content-Type": "application/json"},
        )

        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                return result["message"]["content"].strip()
        except urllib.error.URLError as e:
            raise ConnectionError(
                f"Cannot connect to Ollama at {self.base_url}. "
                f"Make sure Ollama is running: ollama serve\n"
                f"Error: {e}"
            )

    def generate_with_history(
        self,
        messages: list[dict],
        max_tokens: int = 256,
        temperature: float = 0.2,
    ) -> str:
        """Генерация с полной историей сообщений."""
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
                "num_ctx": self.n_ctx,
            },
        }

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=data,
            headers={"Content-Type": "application/json"},
        )

        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result["message"]["content"].strip()

    def check_model_available(self) -> bool:
        """Проверяет доступность модели в Ollama."""
        try:
            req = urllib.request.Request(f"{self.base_url}/api/tags")
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                models = [m["name"] for m in data.get("models", [])]
                return any(self.model in m for m in models)
        except Exception:
            return False

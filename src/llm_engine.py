"""LLM Engine — обёртка над llama-cpp-python для Qwen2.5-Coder-7B-Instruct."""

import os
from pathlib import Path
from llama_cpp import Llama


DEFAULT_MODEL_PATH = Path(__file__).resolve().parent.parent / "models" / "qwen2.5-coder-7b-instruct-q4_k_m.gguf"


class LLMEngine:
    """Загружает модель один раз, предоставляет метод generate()."""

    def __init__(
        self,
        model_path: str | None = None,
        n_ctx: int = 8192,
        n_gpu_layers: int = -1,  # все слои на GPU
        n_threads: int = 8,
        verbose: bool = False,
    ):
        model_path = model_path or str(DEFAULT_MODEL_PATH)
        if not os.path.exists(model_path):
            raise FileNotFoundError(
                f"Model not found at {model_path}. "
                "Download it first — see README."
            )

        self.llm = Llama(
            model_path=model_path,
            n_ctx=n_ctx,
            n_gpu_layers=n_gpu_layers,
            n_threads=n_threads,
            verbose=verbose,
            chat_format="chatml",  # Qwen2.5 использует ChatML
        )

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 4096,
        temperature: float = 0.2,
        top_p: float = 0.9,
        stop: list[str] | None = None,
    ) -> str:
        """Генерирует ответ модели, возвращает только текст."""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        response = self.llm.create_chat_completion(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            stop=stop or [],
        )

        return response["choices"][0]["message"]["content"].strip()

    def generate_with_history(
        self,
        messages: list[dict],
        max_tokens: int = 4096,
        temperature: float = 0.2,
    ) -> str:
        """Генерация с полной историей сообщений."""
        response = self.llm.create_chat_completion(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return response["choices"][0]["message"]["content"].strip()
